import json
import logging
from functools import partial

import pyproj
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union, transform
from shapely.geometry.polygon import Polygon
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry.collection import GeometryCollection
from shapely.geometry.point import Point



def dissolve(featureset):
    '''
    Dissolve a set of geometries on a field, or dissolve fully to a single
    feature if no field is provided
    '''

    new_features = []
    dissolve_id = 0
    try:
        assert isinstance(featureset, dict)
        assert 'features' in featureset.keys()
        assert isinstance(featureset['features'], list)
    except Exception as e:
        raise ValueError((str(e),featureset))
    if len(featureset['features']) > 0:

        geoms = [f['geometry'] if f['geometry'].is_valid else
                 f['geometry'].buffer(0) for f in featureset['features']]
        new_properties = condense_properties([f['properties'] for f in
                                              featureset['features']])
        new_properties['dissolve_id'] = dissolve_id
        dissolve_id += 1
        new_features.append(dict(type='Feature',
                                     geometry=unary_union(geoms),
                                     properties=new_properties))

    new_featureset = dict(type=featureset['type'],
                          features=new_features)
    if 'crs' in featureset.keys():
        new_featureset['crs'] = featureset['crs']

    return new_featureset


def condense_properties(properties):
    '''
    Combine common properties with duplicate values from all features
    being dissolved
    '''
    return {key: val for key, val in properties[0].items()
            if all(key in p.keys() and val == p[key] for p in properties)}


def json2ogr(in_json):
    '''
    Convert geojson object to GDAL geometry
    '''

    if isinstance(in_json, str):
        in_json = json.loads(in_json)

    if not isinstance(in_json, dict):
        raise ValueError('input json must be dictionary')

    if 'features' not in in_json.keys():
        raise ValueError('input json must contain features property')

    for f in in_json['features']:
        f['geometry'] = shape(f['geometry'])
        if not f['geometry'].is_valid:
            f['geometry'] = f['geometry'].buffer(0)

    for i in range(len(in_json['features'])):
        in_json['features'][i]['properties']['id'] = i

    return in_json


def ogr2json(featureset):
    '''
    Convert GDAL geometry to geojson object
    '''

    new_features = []
    for f in featureset['features']:
        new_features.append(dict(geometry=mapping(f['geometry']),
                                 properties=f['properties'],
                                 type=f['type']))
        # f['geometry'] = mapping(f['geometry'])

    new_featureset = dict(type=featureset['type'],
                          features=new_features)
    if 'crs' in featureset.keys():
        new_featureset['crs'] = featureset['crs']
    return json.dumps(new_featureset)


def get_area(featureset):
    if featureset['features']:
        area = sum([f['geometry'].area / 10000
                    for f in featureset['features']])
    else:
        area = 0

    return area


def split_multipolygon(f):
    '''
    Split multipolygon into coterminous polygons
    '''
    new_features = [{'type': 'Feature',
                     'properties': f['properties'],
                     'geometry': poly} for poly in f['geometry']]
    return new_features


def split_polygon(f):
    '''
    Split complex geometry in half until they are below vertex and bounding
    box size constraints
    '''
    bbs = get_split_boxes(f)
    new_features = []
    if bbs:
        for bb in bbs:
            geom = f['geometry']
            if not geom.is_valid:
                geom = geom.buffer(0)
            split_feat = {'type': 'Feature',
                        'properties': f['properties'],
                        'geometry': geom.intersection(bb)}
            if split_feat['geometry'].type == 'MultiPolygon':
                poly_feats = split_multipolygon(split_feat)
                for h in poly_feats:
                    new_features.extend(split_polygon(h))
            else:
                new_features.extend(split_polygon(split_feat))
    else:
        new_features.append(f)

    return new_features

def split(featureset):
    '''
    First split all multipolygons into coterminous polygons. Then check each
    against vertex and bounding box size constraints, and split into multiple
    polygons using recursive halving if necessary
    '''
    new_features = []
    split_id = 0
    for f in featureset['features']:
        f['properties']['split_id'] = split_id
        split_id += 1
        if f['geometry'].type == 'MultiPolygon':
            poly_feats = split_multipolygon(f)
            for h in poly_feats:
                new_features.extend(split_polygon(h))
        elif f['geometry'].type == 'Polygon':
            new_features.extend(split_polygon(f))

    new_featureset = dict(type=featureset['type'],
                          features=new_features)
    if 'crs' in featureset.keys():
        new_featureset['crs'] = featureset['crs']

    return new_featureset

def get_split_boxes(f):
    '''
    Check if number of vertices or width or height of bounding box exceed
    thresholds. If they do, returns two revised bounding boxes (Left/Upper
    and Right/Bottom) for intersecting with the geometry
    '''
    x1, y1, x2, y2 = bounds(f)
    COMPLEXITY_THRESHOLD = 1.2
    if (x2 - x1 > COMPLEXITY_THRESHOLD or y2 - y1 > COMPLEXITY_THRESHOLD):
        if x2 - x1 > y2 - y1:
            x_split = x1 + (x2 - x1) / 2
            return [box(x1, y1, x_split, y2), box(x_split, y1, x2, y2)]
        else:
            y_split = y1 + (y2 - y1) / 2
            return [box(x1, y1, x2, y_split), box(x1, y_split, x2, y2)]

    return None


def bounds(f):
    if isinstance(f['geometry'], dict):
        geom = f['geometry']['coordinates']
    else:
        try:
            geom = mapping(f['geometry'])['coordinates']
        except Exception as e:
            raise ValueError((str(e),f['geometry'],mapping(f['geometry'])))
    x, y = zip(*list(explode(geom)))
    return min(x), min(y), max(x), max(y)


def explode(coords):
    """Explode a GeoJSON geometry's coordinates object and yield coordinate
    tuples. As long as the input is conforming, the type of the geometry
    doesn't matter.
    https://gis.stackexchange.com/questions/90553/fiona-get-each-feature-
    extent-bounds"""
    for e in coords:
        if isinstance(e, (float, int)):
            yield coords
            break
        else:
            for f in explode(e):
                yield f


def project_local(featureset):

    if ('crs' in featureset.keys() and
            featureset['crs']['properties']['name'] ==
            'urn:ogc:def:uom:EPSG::9102'):
        return featureset

    name = 'urn:ogc:def:uom:EPSG::9102'

    # get cumulative centroid of all features
    # x, y = 0, 0
    new_features = []
    for f in featureset['features']:
        if isinstance(f['geometry'], GeometryCollection):
            x = np.mean([geom_item.centroid.x for geom_item in f['geometry']])
            y = np.mean([geom_item.centroid.y for geom_item in f['geometry']])
        else:
            x = f['geometry'].centroid.x
            y = f['geometry'].centroid.y
    # x = x / len(featureset['features']) if featureset['features'] else 0
    # y = y / len(featureset['features']) if featureset['features'] else 0

        # define local projection
        proj4 = '+proj=aeqd +lat_0={} +lon_0={} +x_0=0 +y_0=0 +datum=WGS84 \
                 +units=m +no_defs +R=6371000 '.format(y, x)
        # define projection transformation
        project = partial(pyproj.transform,
                          pyproj.Proj(init='epsg:4326'),
                          pyproj.Proj(proj4))

        # peoject features and add projection info
        new_feat = project_feature(f, project)
        new_feat['properties']['centroid'] = (x,y)
        new_features.append(new_feat)

    new_featureset = dict(type=featureset['type'],
                          features=new_features,
                          crs=dict(type="name",
                                   properties=dict(name=name)))

    return new_featureset


def project_feature(f, project):
    if isinstance(f['geometry'], Polygon):
        geom = Polygon(f['geometry'])
    elif isinstance(f['geometry'], MultiPolygon):
        geom = MultiPolygon(f['geometry'])
    elif isinstance(f['geometry'], GeometryCollection):
        geom = GeometryCollection(f['geometry'])
    elif isinstance(f['geometry'], Point):
        geom = Point(f['geometry'])

    projected_geom = transform(project, geom)
    new_feat = dict(properties=f['properties'],
                    geometry=projected_geom,
                    type='Feature')

    return new_feat
