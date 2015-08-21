#!/usr/bin/env python

"""
Flirble DNS Server
------------------

A DNS server that does some sort of crude loadbalancing.
"""

version = "0.1"

debug = False

from server import *
from handler import *
from request import *
