#!/usr/bin/env python
#!/usr/bin/env python
# Flirble DNS Server
# Lat/long distance functions

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, time
import threading
import geoip2.database

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

class Geo(object):

    geodb_file = None
    geodb = None

    lock = None

    def __init__(self, geodb=None):
        super(Geo, self).__init__()

        self.lock = threading.Lock()

        if geodb is not None:
            self.geodb_file = geodb
            with self.lock:
                self.geodb = geoip2.database.Reader(geodb)


    def reopen(self):
        with self.lock:
            self.geodb.close()
            self.geodb = geoip2.database.Reader(self.geodb_file)


    def find_closest_server(self, servers, client, params=None):
        if params is None:
            params = {}

        if self.geodb is None:
            return None

        # Lookup the client address
        try:
            with self.lock:
                city = self.geodb.city(client)
        except:
            log.error("Can't do city lookup on '%s'" % client)
            return False

        lat = city.location.latitude
        lon = city.location.longitude

        # The shortest distance discovered
        mindist = 9999999
        # List of servers found at the shortest distance
        ranked = []

        for server in servers:
            dist = fdns.gcs_distance((lat, lon), (server['lat'], server['lon']))

            if dist <= mindist:
                if dist < mindist:
                    mindist = dist
                    ranked = []
                ranked.append(server)

        # Nothing found? Drop out now.
        if len(ranked) == 0:
            return False

        # If we have more than one server we need to choose one
        if len(ranked) > 1:
            # Build a hash from the last octect of the client address
            if ':' in client:
                val = int(client.split(':')[-1], 16)
            elif '.' in client:
                val = int(client.split('.')[-1])
            else:
                raise Exception("Badly formatted IP address: '%s'" % client)

            idx = val % len(ranked)
            ranked = [ranked[idx]]

        return ranked[0]

