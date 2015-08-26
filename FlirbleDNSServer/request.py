#!/usr/bin/env python
# Flirble DNS Server
# Request handler

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, json
import dnslib

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

"""Default DNS record TTL, if one is not given in the zone definition."""
DEFAULT_TTL = 30


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

    zones_file = None
    servers_file = None
    geo = None

    zones = None
    servers = None

    """
    @param zones str The name of the zones configuration file. This must exist
                at instance creation and be a valid JSON file.
    @param servers str The name of the servers configuration file. This mys
                exist at instance creation and be a valid JSON file.
    @param geo Geo An instance of a Geo object that can be used to perform
                geographic lookups and calculations.
    """
    def __init__(self, zones=None, servers=None, geo=None):
        super(Request, self).__init__()

        if zones is not None:
            if not os.path.exists(zones):
                log.error("Zones file '%s' does not exist." % zones)
                raise Exception("Zones file '%s' does not exist." % zones)

            self.zones_file = zones

            with open(zones, 'r') as f:
                self.zones = json.load(f)

        if servers is not None:
            if not os.path.exists(servers):
                log.error("Servers file '%s' does not exist." % servers)
                raise Exception("Servers file '%s' does not exist." % servers)

            self.servers_file = servers

            with open(servers, 'r') as f:
                self.servers = json.load(f)

        if geo is not None:
            self.geo = geo


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

        qname = str(request.q.qname)

        header = dnslib.DNSHeader(id=request.header.id, qr=1, aa=1, ra=1)
        reply = dnslib.DNSRecord(header, q=request.q)

        status = None
        if qname in self.zones:
            zone = self.zones[qname]
            if zone['type'] == 'static':
                status = self.handle_static(zone, request, reply)
            elif zone['type'] == 'geo-dist':
                status = self.handle_geo_dist(zone, request, reply, address)
        else:
            # indicate an error.
            # in an ideal world we'd say we didn't find it (NXDOMAIN)
            # but to indicate that we don't allow any recursion it's
            # better to reply DENIED, if at all.
            status = None

        if status is None:
            # Add the denied message
            header.rcode = dnslib.RCODE.REFUSED
            pass
        elif status is False:
            # Add an error status
            header.rcode = dnslib.RCODE.SERVFAIL
            pass

        if fdns.debug:
            log.debug("Reply to send:", extra={'zone': str(reply)})

        return reply.pack()


    """
    Handles a request for a static DNS zone.

    This uses zone record details in the zone to formulate a reply to the
    query. The supported DNS resource records are documented in the method
    construct_rdata().

    @param zone str The zone name for which we are to construct a reply.
    @param request DNSRecord The parsed DNS request.
    @param reply DNSRecord The DNS reply to which we add our records.
    @return bool This function always returns True.
    """
    def handle_static(self, zone, request, reply):
        qtype = dnslib.QTYPE[request.q.qtype]

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        for rr in zone['rr']:
            if qtype in ('*', 'ANY', rr['type']):
                rdata = self.construct_rdata(rr)
                rtype = getattr(dnslib.QTYPE, rr['type'])
                reply.add_auth(dnslib.RR(rname=request.q.qname, rtype=rtype, ttl=ttl, rdata=rdata))
                self.check_additional(rdata, reply)

        return True


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

    @param zone str The zone name for which we are to construct a reply.
    @param request DNSRecord The parsed DNS request.
    @param reply DNSRecord The DNS reply to which we add our records.
    @params address str The IP address from which the datagram originated.
                This can be either an IPv4 or an IPv6 address. It can also be
                an IPv4-encoded-as-IPv6 address like "::ffff:a.b.c.d".
    @return bool Returns True on success and False if we were unable to find
                a winning set of servers and no static fallback was
                available.
    """
    def handle_geo_dist(self, zone, request, reply, address):
        qtype = dnslib.QTYPE[request.q.qtype]

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        servers = None

        if 'servers' in zone:
            s = zone['servers']
            if s in self.servers:
                servers = self.servers[s]

        if servers is None and 'default' in self.servers:
            servers = self.servers['default']

        if self.geo is not None and servers is not None:
            # check if we were given an ipv6-encoded-as-ipv6 address
            client = address[0]
            if client.startswith('::ffff:'):
                # strip the ipv6 part
                client = client[7:]

            # if we have paramaters, use them
            if 'params' in zone:
                params = zone['params']
            else:
                params = {}

            # go find the closest set of servers to the client address
            servers = self.geo.find_closest_server(servers, client, params)

            # Only process the response if it's a list and it has entries
            if isinstance(servers, list) and len(servers) > 0:
                for server in servers:
                    # Construct A and AAAA replies for this server
                    if 'ipv4' in server and qtype in ('*', 'ANY', 'A'):
                        addrs = server['ipv4']
                        if not isinstance(addrs, (list, tuple)):
                            addrs = [addrs]
                        for addr in addrs:
                            reply.add_auth(dnslib.RR(rname=request.q.qname, rtype=dnslib.QTYPE.A, ttl=ttl, rdata=dnslib.A(addr)))

                    if 'ipv6' in server and qtype in ('*', 'ANY', 'AAAA'):
                        addrs = server['ipv6']
                        if not isinstance(addrs, (list, tuple)):
                            addrs = [addrs]
                        for addr in addrs:
                            reply.add_auth(dnslib.RR(rname=request.q.qname, rtype=dnslib.QTYPE.AAAA, ttl=ttl, rdata=dnslib.AAAA(addr)))

                return True

        # Fallthrough if geo stuff doesn't work...
        if 'rr' in zone:
            return self.handle_static(zone, request, reply)

        # Fallthrough on failure...
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

    @param rr hash The input zone information for a single resource record.
    @returns RD Returns a subclassed RD (rdata) of the appropriate
                type or None if the type provided in rr is not supported.
    """
    def construct_rdata(self, rr):
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

    This also only returns static data currently.

    @param rdata RD An rdata object of the resource record to check.
    @param reply DNSRecord into which any additional resource records are
                added.
    """
    def check_additional(self, rdata, reply):
        rtype = rdata.__class__.__name__
        if rtype in ('MX', 'CNAME', 'NS'):
            # Get the label
            name = str(rdata.label)
            if name in self.zones:
                self.add_additional(name, self.zones[name], reply)


    """
    Add additional records to a DNSRecord reply.

    @param name str The record name to add.
    @param zone dict The zone data to extract details from.
    @param reply DNSRecord into which additional resource records are added.
    """
    def add_additional(self, name, zone, reply):
        if zone['type'] != 'static':
            return

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        for rr in zone['rr']:
            if rr['type'] in ('A', 'AAAA'):
                rdata = self.construct_rdata(rr)
                rtype = getattr(dnslib.QTYPE, rr['type'])
                reply.add_ar(dnslib.RR(rname=name, rtype=rtype, ttl=ttl, rdata=rdata))
