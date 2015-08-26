#!/usr/bin/env python

"""
Flirble DNS Server
------------------

A DNS server that does some sort of crude Gepgraphically-aware loadbalancing.
"""

"""Flirble DNS Server version number."""
version = "0.1"

"""Whether to emit extra diagnostic output."""
debug = False

from server import *
from handler import *
from request import *
from geo import *
from geodistance import *
