#!/usr/bin/env python
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

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, time
import threading
import geoip2.database

import FlirbleDNSServer as fdns

"""
Handles Geographic lookup and related operations.

This class uses a lock to serialize all database operations in order to
ensure threadsafe operation.
"""
class Geo(object):

    geodb_file = None
    geodb = None

    lock = None

    """
    @param geodb str The path to a Maxmind GeoIP2 Cities database. This must
                exist at instantiation otherwise this class will not function.
    """
    def __init__(self, geodb=None):
        super(Geo, self).__init__()

        self.lock = threading.Lock()

        if geodb is not None:
            self.geodb_file = geodb
            with self.lock:
                self.geodb = geoip2.database.Reader(geodb)


    """
    Closes and reopens the Maxmind GeoIP2 database. Typically this is
    performed to access a newer version of the database. If reopening the
    database fails this class is rendered inoperable.
    """
    def reopen(self):
        with self.lock:
            self.geodb.close()
            self.geodb = geoip2.database.Reader(self.geodb_file)


    """
    Attempts to find the server closest to the client.

    If load data is available and the zone specifies a limit, the set of
    servers is filtered based on their reported load.

    A GeoIP lookup is performed on the client address and then the distance
    between it and the coordinates of each of a set of servers is used to
    determine which of those servers are closest.


    The precision parameter is used to deliberately reduce precision of the
    distance value to allow servers that are of similar distance to be
    included in the selection.

    The configuration may also specify how many servers in the winning
    group should be included in the reply. The default is one, but if the
    round-robin heuristic of DNS client resolvers is desired then more can
    be included.

    A simple hash is calculated from the client address so that when there is
    more than one server in the final list, a client is generally given the
    same server, or subset of servers, in subsequent queries. This is
    probably considered a desirable trait.

    @param servers hash A set of candidate servers. Each should provide
                their lat and lon coordinates.
    @param client str The IPv4 or IPv6 address of the client on which a GeoIP
                lookup will be performed.
    @param params hash A set of optional parameters used to influence the
                selection process.
                * maxload When load information is available, the maximum
                    load for a server to be retained in the candidate list.
                * precision The precision at which distances are calculated.
                    In effect, distances are rounded down by this value, for
                    example "50" would mean that distances are rounded down
                    to the nearest 50. The default is 50.
                * maxreplies Sets the number of servers to include in a reply.
                    The default is 1.
    """
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
            # if the server reports a negative value for load then consider
            # it unavailable
            if 'load' in server:
                if float(server['load']) < 0.0:
                    continue

                # now compare it with any maxload we're given by the zone.
                # if the reported load is higher, it's not a candidate
                if 'maxload' in params:
                    if float(server['load']) > float(params['maxload']):
                        # server load exceeds allowable maximum, don't
                        # consider it as a candidate
                        continue


            # check the timestamp of when we received the last update
            # if it's too old, the server's not a candidate since it's not
            # keeping us informed (and therefore probably dead)
            if 'maxage' in params and 'ts' in server:
                ts = float(server['ts'])
                # if the timestamp is negative then we can assume this is
                # a static entry and does not age out
                if ts >= 0.0:
                    age = time.time() - ts
                    if age > float(params['maxage']):
                        continue

            # use default precision unless one is given in the parameters
            precision = fdns.GCS_DISTANCE_PRECISION
            if 'precision' in params:
                precision = params['precision']

            # calculate the distance between two lat,long pairs
            dist = fdns.gcs_distance((lat, lon), (server['lat'], server['lon']))

            # see if the zone specifies a maximum distance; a negative value
            # (or the value is not present) means no limit
            if 'maxdist' in params:
                maxdist = float(params['maxdist'])
                if maxdist >= 0.0 and dist > maxdist:
                    continue

            # check if the server is closer than (or the same distance as)
            # previous servers. if not, it's not a candidate.
            # if it's closer then we remove previous candidates.
            # remember that this value is rounded by the "precision" value
            # above.
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

