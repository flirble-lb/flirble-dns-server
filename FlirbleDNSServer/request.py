#!/usr/bin/env python
# Flirble DNS Server
# Request handler

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, json
import dnslib

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

DEFAULT_TTL = 30


class ZoneLoggingFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'zone') and len(record.zone) > 0:
            lines = map(lambda x: "    "+x, record.zone.split("\n"))
            record.msg = record.msg + "\n" + "\n".join(lines)
        return super(ZoneLoggingFilter, self).filter(record)

log.addFilter(ZoneLoggingFilter())


class Request(object):

    zones_file = None
    servers_file = None
    geo = None

    zones = None
    servers = None

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


    def handle_static(self, zone, request, reply):
        qtype = dnslib.QTYPE[request.q.qtype]

        ttl = DEFAULT_TTL
        if "ttl" in zone:
            ttl = int(zone['ttl'])

        for rr in zone['rr']:
            if qtype in ('*', 'ANY', rr['type']):
                rdata = self.construct_rdata(rr)
                rtype = getattr(dnslib.QTYPE, rr['type'])
                reply.add_answer(dnslib.RR(rname=request.q.qname, rtype=rtype, ttl=ttl, rdata=rdata))

        return True


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
            # check if we get an ipv6-ebcoded-as-ipv6 address
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
                            reply.add_answer(dnslib.RR(rname=request.q.qname, rtype=dnslib.QTYPE.A, ttl=ttl, rdata=dnslib.A(addr)))

                    if 'ipv6' in server and qtype in ('*', 'ANY', 'AAAA'):
                        addrs = server['ipv6']
                        if not isinstance(addrs, (list, tuple)):
                            addrs = [addrs]
                        for addr in addrs:
                            reply.add_answer(dnslib.RR(rname=request.q.qname, rtype=dnslib.QTYPE.AAAA, ttl=ttl, rdata=dnslib.AAAA(addr)))

                return True

        # Fallthrough if geo stuff doesn't work...
        if 'rr' in zone:
            return self.handle_static(zone, request, reply)

        # Fallthrough on failure...
        return False


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
