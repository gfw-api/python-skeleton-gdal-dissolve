# python-skeleton-gdal-dissolve

This endpoint performs naive geometry dissolve calculations. It uses shapely's unary_union for these analyses.

It does not use dask or numpy.

### Endpoint
Please send POST requests to: /v1/test-gdal-dissolve/dissolve

### Payload
The payload must be in the following format:

{"geojson": <feature collection>}

For initial testing, please use this feature collection: https://gist.github.com/mappingvermont/3980b2e096b9aac91e7f7636549c6228

### Development
1. Run the ps.sh shell script in development mode.

```ssh
./ps.sh develop
```
