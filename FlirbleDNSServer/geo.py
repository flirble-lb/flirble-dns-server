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
        mindist = sys.maxsize
        # List of servers found at the shortest distance
        ranked = []

        for server in servers:
            # check server load, if applicable
            if 'maxload' in params and 'load' in server:
                if server['load'] > params['maxload']:
                    # server load exceeds allowable maximum, don't
                    # consider it as a candidate
                    continue

            # calculate the distance between two lat,long pairs
            dist = fdns.gcs_distance((lat, lon), (server['lat'], server['lon']))

            # see if we keep this server
            if dist <= mindist:
                if dist < mindist:
                    # this result is closer, start a new list
                    mindist = dist
                    ranked = []
                # keep this server
                ranked.append(server)

        # Nothing found? Drop out now.
        if len(ranked) == 0:
            return False

        # If we have more than one server we may need to choose one or a subset
        if len(ranked) > 1:
            # Build a hash from the last octect of the client address
            if ':' in client: # ipv6
                val = int(client.split(':')[-1], 16)
            elif '.' in client: # ipv4
                val = int(client.split('.')[-1])
            else:
                raise Exception("Badly formatted IP address: '%s'" % client)

            # simple modulo for the hash
            idx = val % len(ranked)

            # How many we can keep
            if 'maxreplies' in params:
                maxreplies = params['maxreplies']
            else:
                maxreplies = 1

            if maxreplies >= len(ranked):
                # small optimization when the number we keep and the number
                # of replies is the same - just keep the whole list as is!
                pass
            elif idx + maxreplies > len(ranked):
                # If the number we keep means we wrap at the end of the list,
                # we have to splice the end and the start tofether.
                r = len(ranked) - idx
                r = idx - r
                ranked = ranked[idx:] + ranked[:r]
            else:
                # retain the allowed number of entries, starting from the
                # hashed index
                r = idx + maxreplies
                ranked = ranked[idx:r]

        return ranked

