#!/usr/bin/env python
# Flirble DNS Server
# Lat/long distance functions

import logging
log = logging.getLogger(__file__)

import math

GCS_DISTANCE_PRECISION = 50.0


def gcs_distance(a, b, precision=GCS_DISTANCE_PRECISION):

    (lat1, lon1) = a
    (lat2, lon2) = b

    theta = lon1 - lon2;
    dist = math.sin(math.radians(lat1)) * math.radians(math.radians(lat2)) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(theta));
    dist = math.degrees(math.acos(dist));
    miles = dist * 60 * 1.1515;

    miles = miles / precision;
    miles = int(miles) * precision;

    return int(miles);
