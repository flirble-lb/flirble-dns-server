#!/usr/bin/env python
# Flirble DNS Server
# Request handler

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, json, threading, collections, time
import dnslib

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

"""Default DNS record TTL, if one is not given in the zone definition."""
DEFAULT_TTL = 1800

"""Time to cache Geo results for."""
GEO_CACHE_TTL = 5

"""A logging filter used when dumping the received and sent DNS packets; this
   filter handes the multiline output of dnslib when serializing such data."""
class ZoneLoggingFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'zone') and len(record.zone) > 0:
            lines = map(lambda x: "    "+x, record.zone.split("\n"))
            record.msg = record.msg + "\n" + "\n".join(lines)
        return super(ZoneLoggingFilter, self).filter(record)

log.addFilter(ZoneLoggingFilter())


"""
Handles a DNS request.

This parses a DNS packet and then answers the query it contains.

Each instance is configured with a zones file and a servers file, both
JSON encoded, that supply information about the DNS zones we will return
replies for.

This supports two types of zone currently:

* A static zone that serves up fixed data. This supports most common DNS
  records.
* A dynamic geo-distance zone. The zone definition indicates a set of servers
  whose geographic coordinates are compared with those of a GeoIP lookup
  of the IP address of the requesting DNS client. With this method, the
  servers are ranked into a group of the closest and then one or more of that
  group are selected and used in the reply.
"""
class Request(object):

    zlock = None
    slock = None
    """A lock around self.geo_cache."""
    glock = None

    rdb = None
    zones_table = None
    servers_table = None
    geo = None
    """A cache of servers returned by geo lookups for a client."""
    geo_cache = None

    zones = None
    servers = None


    """
    @param rdb FlirbleDNSServer.Data The database handle.
    @param zones str The zones table to fetch zone data from.
    @param servers str The servers table to fetch server data from.
    @param geo Geo An instance of a Geo object that can be used to perform
                geographic lookups and calculations.
    """
    def __init__(self, rdb, zones, servers, geo=None):
        super(Request, self).__init__()

        self.zlock = threading.Lock()
        self.slock = threading.Lock()

        self.rdb = rdb
        self.zones_table = zones
        self.servers_table = servers

        self.zones = {}
        self.servers = {}

        if rdb is not None:
            rdb.register_table(zones, self._zones_cb)
            rdb.register_table(servers, self._servers_cb)

        if geo is not None:
            self.geo = geo
            self.geo_cache = {}
            self.glock = threading.Lock()


    """
    Callback for initial and updates to the distributed Zones database.
    """
    def _zones_cb(self, rdb, change):
        with self.zlock:
            log.debug("Zones change: %s" % repr(change))
            new = change["new_val"]
            for k in new:
                self.zones[k] = new[k]


    """
    Callback for initial and updates to the distributed Servers database.
    """
    def _servers_cb(self, rdb, change):
        with self.slock:
            log.debug("Servers change: %s" % repr(change))
            new = change["new_val"]
            for k in new:
                self.servers[k] = new[k]


    """
    Process a DNS query by parsing a DNS packet and, depending on the
    zone the request is for, process it and return a DNS packet to be used
    as the reply.

    @params data str A raw, complete DNS datagram.
    @params address str The IP address from which the datagram originated.
                This can be either an IPv4 or an IPv6 address. It can also be
                an IPv4-encoded-as-IPv6 address like "::ffff:a.b.c.d".
    @returns str A raw, complete DNS reply packet.
    """
    def handler(self, data, address):
        request = dnslib.DNSRecord.parse(data)

        if fdns.debug:
            log.debug("Request received:", extra={'zone': str(request)})

        # Create a state-tracking object for this request.
        state = RequestState()

        state.address = address
        state.qname = str(request.q.qname)
        state.qtype = dnslib.QTYPE[request.q.qtype]

        state.header = dnslib.DNSHeader(id=request.header.id, qr=1, aa=1, ra=0)
        state.reply = dnslib.DNSRecord(state.header, q=request.q)

        status = self.handle_zone(state.qname, state.qtype, state)

        if status is None:
            # Add the denied message
            state.header.rcode = dnslib.RCODE.REFUSED
        else:
            # Look for authority data
            if status == False:
                # No error but no answer? Search for a parent zone SOA.
                q = 'SOA'
            else:
                # If we had answers, look for additional useful data.
                q = 'NS'

            fn = state.reply.add_auth
            parts = collections.deque(state.qname.split('.'))
            status = False
            while status is False and len(parts) > 0:
                name = '.'.join(parts)
                if len(name) == 0:
                    name = '.'

                status = self.handle_zone(name, q, state, fn=fn)
                if status is None:
                    status = False

                parts.popleft()

            if status is False:
                state.header.rcode = dnslib.RCODE.REFUSED

        if fdns.debug:
            log.debug("Reply to send:", extra={'zone': str(state.reply)})

        return state.reply.pack()


    """
    If the zone 'qname' exists, dispatches to the correct method to handle it.

    @param qname str The record name.
    @param qtype str|tuple The record type(s) being asked for.
    @param state RequestState The state tracking object for this request.
    @param fn function_pointer Override the function passed to methods to
                add records to the reply.
    @return bool Returns True on success and False if we were unable to find
                matching reply records. None is returned on any error.
    """
    def handle_zone(self, qname, qtype, state, fn=None):
        if fdns.debug:
            log.debug("handle_zone qname=%s qtype=%s" % (qname, qtype))

        # handle recursion checking
        if (qname, qtype) in state.chain:
            if fdns.debug:
                log.debug("handle_zone qname,qtype in chain, ignoring. qname=%s qtype=%s" % (qname, qtype))
            return None
        state.chain.append(qname)

        # Assume that if otherwise unspecified, we add answers
        if fn is None:
            fn = state.reply.add_answer

        # Do we awnser for such a zone?
        with self.zlock:
            if qname in self.zones:
                zone = self.zones[qname]
            else:
                zone = None

        # Dispatch appropriately.
        if zone is not None:
            if zone['type'] == 'static':
                return self.handle_static(qname, qtype, zone, state, fn)

            if zone['type'] == 'geo-dist':
                return self.handle_geo_dist(qname, qtype, zone, state, fn)

        if fdns.debug:
            log.debug("handle_zone qname=%s qtype=%s not found" % (qname, qtype))

        return False


    """
    Handles a request for a static DNS zone.

    This uses zone record details in the zone to formulate a reply to the
    query. The supported DNS resource records are documented in the method
    _construct_rdata().

    @param qname str The record name.
    @param qtype str|tuple The record type(s) being asked for.
    @param state RequestState The state tracking object for this request.
    @return bool This function returns True if any records were added, False
                otherwise.
    """
    def handle_static(self, qname, qtype, zone, state, fn):
        if fdns.debug:
            log.debug("handle_static qname=%s qtype=%s" % (qname, qtype))

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        # if we're looking for A or AAAA specifically then also look for CNAME
        q = (qtype, 'CNAME') if qtype in ('A', 'AAAA') else qtype

        found = False

        for rr in zone['rr']:
            if self._check_qtype(q, ('ANY', rr['type'])):
                found = True
                rdata = self._construct_rdata(rr)
                rtype = getattr(dnslib.QTYPE, rr['type'])
                self._add(state, fn, dnslib.RR(rname=qname, rtype=rtype, ttl=ttl, rdata=rdata))

                # If we were asking for A/AAAA, and got something else, this
                # will effectively query the A/AAAA of that thing.
                # NS is included since we use that to fill in the additional
                # section if we have authority records.
                if self._check_qtype(qtype, ('A', 'AAAA', 'NS', 'ANY')):
                    self._check_additional(rdata, qtype, state)

        return found


    """
    Handles a request for a Geo-distance dynamic DNS zone.

    The zone indicates which set of servers it should use as candidate
    destinations to fulfil the request with.

    Much of the server selection is performed by the find_closest_server()
    method in the Geo class.

    For each winning servers addresses an IPv4 (A record) and IPv6 (AAAA
    record) are then assembled into the response. No other resource types are
    currently supported.

    If for whatever reason no dynamic response was achievable (such as the
    GeoIP lookup failing or all candidate servers are filtered because of
    load issues) then, if the zone configuration provides them, fallback
    a static response will occur using the handle_static() method.

    @param qname str The record name.
    @param qtype str|tuple The record type(s) being asked for.
    @param state RequestState The state tracking object for this request.
    @return bool Returns True on success and False if we were unable to find
                a winning set of servers and no static fallback was
                available.
    """
    def handle_geo_dist(self, qname, qtype, zone, state, fn):
        if fdns.debug:
            log.debug("handle_geo_dist qname=%s qtype=%s" % (qname, qtype))

        # Before doing anything, check the query is a type we can respond to
        if not self._check_qtype(qtype, ('A', 'AAAA', 'ANY')):
            return False

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        geo_cache_ttl = GEO_CACHE_TTL
        if 'geo_cache_ttl' in zone:
            geo_cache_ttl = int(zone['geo_cache_ttl'])

        # Determine the set of servers to look at
        servers = None
        with self.slock:
            if 'servers' in zone:
                servers_set = zone['servers']
                if servers_set in self.servers:
                    servers = self.servers[servers_set]

            if servers is None and 'default' in self.servers:
                servers_set = 'default'
                servers = self.servers[servers_set]

        # if we have servers to look at...
        if self.geo is not None and servers is not None:
            # check if we were given an ipv6-encoded-as-ipv6 address
            client = state.address[0]
            if client.startswith('::ffff:'):
                # strip the ipv6 part
                client = client[7:]

            # if we have paramaters, use them
            if 'params' in zone:
                params = zone['params']
            else:
                params = {}

            selected = None

            # do we have a cached entry?
            # build a composite key that includes the selection parameters
            spar = tuple(sorted((key,value) for (key,value) in params.items()))
            skey = (client, servers_set, spar)
            with self.glock:
                if skey in self.geo_cache:
                    s = self.geo_cache[skey]
                    # check the entry age - only use if not expired
                    if time.time() < s[0]:
                        selected = s[1]
                        if fdns.debug:
                            log.debug('handle_geo_dist using cached result for %s' % repr(skey))

            if selected is None:
                # go find the closest set of servers to the client address
                if fdns.debug:
                    log.debug('handle_geo_dist using calculated result for %s' % repr(skey))

                selected = self.geo.find_closest_server(servers, client, params)

                with self.glock:
                    self.geo_cache[skey] = (
                        time.time() + geo_cache_ttl,
                        selected
                    )

            del(skey, spar, servers)


            # Only process the response if it's a list and it has entries
            found = False
            if isinstance(selected, list) and len(selected) > 0:
                for server in selected:
                    # Construct A and AAAA replies for this server
                    if 'ipv4' in server and self._check_qtype(qtype, ('ANY', 'A')):
                        addrs = server['ipv4']
                        if not isinstance(addrs, (list, tuple)):
                            addrs = [addrs]
                        for addr in addrs:
                            found = True
                            self._add(state, fn, dnslib.RR(rname=qname, rtype=dnslib.QTYPE.A, ttl=ttl, rdata=dnslib.A(addr)))

                    if 'ipv6' in server and self._check_qtype(qtype, ('ANY', 'AAAA')):
                        addrs = server['ipv6']
                        if not isinstance(addrs, (list, tuple)):
                            addrs = [addrs]
                        for addr in addrs:
                            found = True
                            self._add(state, fn, dnslib.RR(rname=qname, rtype=dnslib.QTYPE.AAAA, ttl=ttl, rdata=dnslib.AAAA(addr)))

                    if (fdns.debug or ('debug' in zone and zone['debug'] == True)) and self._check_qtype(qtype, ('ANY', 'TXT')):
                        txt = []
                        for item in ('name', 'city'):
                            if item in server:
                                txt.append('%s: %s' % (item, server[item]))

                        for item in txt:
                            self._add(state, fn, dnslib.RR(rname=qname, rtype=dnslib.QTYPE.TXT, ttl=ttl, rdata=dnslib.TXT(item)))

                return found

        # Fallthrough if geo stuff doesn't work...
        if 'rr' in zone:
            return self.handle_static(qname, qtype, zone, state, fn)

        # Fallthrough on failure...
        return False


    """
    Called periodically to take care of various housekeeping.
    """
    def idle(self):
        # Remove any aged cached geo lookups
        with self.glock:
            zap = []
            for k in self.geo_cache:
                if self.geo_cache[k][0] < time.time():
                    zap.append(k)
            for k in zap:
                del(self.geo_cache[k])



    """
    Helper method to check whether a requested qtype is in a list of those
    we answer to.

    @param qtype str|list List of query types to check for.
    @param dtype list List of query types to check against.
    @return bool True if one of qtype is in dtype, False otherwise.
    """
    def _check_qtype(self, qtype, dtype):
        if isinstance(qtype, str):
            return qtype in dtype
        if isinstance(qtype, tuple) or isinstance(qtype, list):
            for t in qtype:
                if t in dtype:
                    return True
        return False


    """
    Constructs a dnslib RD (rdata) resource record object from zone
    information.

    This method supports these DNS resource records:
    * SOA
    * A
    * AAAA
    * NS
    * CNAME
    * TXT
    * PTR
    * MX

    Any other RR type will elicit a return value of None.

    @param rr dict The input zone information for a single resource record.
    @returns RD Returns a subclassed RD (rdata) of the appropriate
                type or None if the type provided in rr is not supported.
    """
    def _construct_rdata(self, rr):
        t = rr['type']
        if t == "SOA":
            return dnslib.SOA(mname=rr['mname'], rname=rr['rname'], times=rr['times'])

        if t == "MX":
            return dnslib.MX(label=rr['value'], preference=rr['pref'])

        if t in ('A', 'AAAA', 'NS', 'CNAME', 'TXT', 'PTR'):
            cls = dnslib.RDMAP[t]
            return cls(rr['value'])

        return None


    """
    Given an RD (rdata) object, check if it refers to some detail we have
    stored locally. If so, add that as an additional record; it may save
    a futher roundtrip between the client and us to fetch it.

    This currently applies to 'MX', 'CNAME' and 'NS' records.

    @param rdata RD An rdata object of the resource record to check.
    @param qtype str|tuple The original query type from the client, or None
                if unavailable. Broadly this is to limit recursion to only
                the same type as requested if it was A or AAAA.
    @param state RequestState The state tracking object for this request.
    """
    def _check_additional(self, rdata, qtype, state):
        rtype = rdata.__class__.__name__
        if rtype in ('MX', 'CNAME', 'NS'):
            # Get the label
            name = str(rdata.label)
            if name in self.zones:
                fn = None
                # If we're adding the A/AAAA for an NS record, those are
                # additional. Otherwise we're adding normal answers.
                # Also, for NS queries, we override what the search is for.
                if rtype == 'NS':
                    fn = state.reply.add_ar
                    qtype = None

                # If no qtype given (or NS overrides it) then do A,AAAA lookups
                if qtype is None:
                    qtype = ('A', 'AAAA')

                # Use handle_zone to work out if we have the local records
                self.handle_zone(name, qtype, state, fn)


    """
    Helper function to add records to the reply but without allowing
    duplicates.

    It stores a simple hash of the record in a list and checks for that hash
    before calling the given function to add new entries to the reply.
    Specifically, the hash() function is called on the string representation
    of rr.rdata.

    @param state RequestState The state tracking object for this request.
    @param fn function_pointer The function to call to add the record to the
                reply.
    @param rr DNSRecord The DNS record to attempt to add to the reply.
    @return object Returns None if the entry is a duplicate, otherwise returns
                with whatever fn() returned.
    """
    def _add(self, state, fn, rr):
        h = hash(str(rr.rdata))
        if h in state.added:
            return None
        state.added.append(h)
        return fn(rr)


"""
A class for storing the state associated with each request.
"""
class RequestState(object):
    """
    A chain of (qname, qtype) tuples that have been queried already in this
    recursion tree.
    """
    chain = None

    """
    A tracker of the records added to a reply. A list of hash values
    """
    added = None

    """
    The IP address from which the datagram originated.
    This can be either an IPv4 or an IPv6 address. It can also be
    an IPv4-encoded-as-IPv6 address like "::ffff:a.b.c.d".
    """
    address = None

    """
    String representation of the original name being queried.
    """
    qname = None

    """
    String representation of the original query type (A, AAAA, ANY, etc)
    """
    qtype = None

    """
    The DNSHeader object of the reply being assembled.
    """
    header = None

    """
    The DNS reply to which records to respond with are added.
    """
    reply = None


    def __init__(self):
        super(RequestState, self).__init__()

        self.chain = []
        self.added = []

