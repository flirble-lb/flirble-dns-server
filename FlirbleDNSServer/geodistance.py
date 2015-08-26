#!/usr/bin/env python
# Flirble DNS Server
# Lat/long distance functions

import logging
log = logging.getLogger(__file__)

import math

"""Default precision with which to return distance calculations."""
GCS_DISTANCE_PRECISION = 50.0


"""
Given two global coordinates, calculate the surface distance between
them in miles, bounded by the optional precision parameter.

@param a list A tuple of (lat, long) coordinates.
@param b list A tuple of (lat, long) coordinates.
@param precision float The rounding to apply to the result. Default is 50.0.
@returns float The distance between the two coordinates, in miles, rounded
			down to the given precision.
"""
def gcs_distance(a, b, precision=GCS_DISTANCE_PRECISION):

    (lat1, lon1) = a
    (lat2, lon2) = b

    theta = lon1 - lon2;
    dist = math.sin(math.radians(lat1)) * math.radians(math.radians(lat2)) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(theta));
    dist = math.degrees(math.acos(dist));
    miles = dist * 60 * 1.1515;

    miles = (miles // precision) * precision

    return miles;
