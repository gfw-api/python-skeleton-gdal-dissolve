"""API ROUTER"""

import logging
import json

from flask import request, jsonify, Blueprint
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

import ps.micro_functions.poly_intersect as analysis_funcs

psone_endpoints = Blueprint('psone_endpoints', __name__)


@psone_endpoints.route('/dissolve', strict_slashes=False, methods=['POST'])
def say_hello():
    geojson = request.json['geojson']
    geojson = json.dumps(geojson) if isinstance(geojson, dict) else geojson

    # read string geojson into shapely geometries
    geojson_geom_obj = analysis_funcs.json2ogr(geojson)

    # run the actual dissolve
    dissolved_features = analysis_funcs.dissolve(geojson_geom_obj)

    # also calc area
    # first split the polygon to make this easier
    #split_poly = analysis_funcs.split(dissolved_features)

    # project all to an azimuthal projection
    #azi_proj = analysis_funcs.project_local(split_poly)

    # calculate the total area of each piece
    #aoi_area = analysis_funcs.get_area(azi_proj)

    #results = [dissolved_features, aoi_area]

    #return package_output(results), 200

    return jsonify(analysis_funcs.ogr2json(dissolved_features)), 200


def package_output(results):

    final_output = {}
    outputs = ['dissolved-geom', 'aoi-area']

    for result, name in zip(results, outputs):
        if isinstance(result, dict) and 'features' in result.keys():
            final_output[name] = analysis_funcs.ogr2json(result)
        else:
            final_output[name] = result

    return jsonify(final_output)
