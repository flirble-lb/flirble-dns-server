#!/usr/bin/env python
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

"""
Flirble DNS Server
------------------

A DNS server that does some sort of crude Gepgraphically-aware loadbalancing.
"""

"""Flirble DNS Server version number."""
version = "0.2"

"""Whether to emit extra diagnostic output."""
debug = False

"""Whether certain operations within a lock take a copy of an object or
just a reference for use outside the lock. Might have performance versus
robustness implications."""
paranoid = True

from server import *
from handler import *
from request import *
from geo import *
from geodistance import *
from data import *
