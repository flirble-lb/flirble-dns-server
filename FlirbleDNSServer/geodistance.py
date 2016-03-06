#!/usr/bin/env python
# Flirble DNS Server
# Lat/long distance functions
#
#    Copyright 2016 Chris Luke
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

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
