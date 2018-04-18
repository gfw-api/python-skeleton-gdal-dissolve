"""API ROUTER"""

import logging
import json

from flask import request, jsonify, Blueprint
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

psone_endpoints = Blueprint('psone_endpoints', __name__)


@psone_endpoints.route('/dissolve', strict_slashes=False, methods=['POST'])
def say_hello():
    geojson = request.json['geojson']
    geojson = json.dumps(geojson) if isinstance(geojson, dict) else geojson

    # read string geojson into shapely geometries
    geojson_geom_obj = json2ogr(geojson)

    # run the actual dissolve
    dissolved_features = dissolve(geojson_geom_obj)

    return ogr2json(dissolved_features), 200



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
