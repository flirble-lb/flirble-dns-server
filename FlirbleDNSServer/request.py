#!/usr/bin/env python
# Flirble DNS Server
# Request handler

import sys, json
import dnslib

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

DEFAULT_TTL = 30

class Request(object):

    zones_file = None
    servers_file = None

    zones = None
    servers = None

    def __init__(self, zones=None, servers=None):
        super(Request, self).__init__()

        if zones is not None:
            self.zones_file = zones
            with open(zones, 'r') as f:
                self.zones = json.load(f)

        if servers is not None:
            self.servers_file = servers
            with open(servers, 'r') as f:
                self.servers = json.load(f)


    def handler(self, data, address):
        request = dnslib.DNSRecord.parse(data)

        if fdns.debug:
            print "Request:\n", request

        qname = str(request.q.qname)

        reply = dnslib.DNSRecord(dnslib.DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)

        if qname in self.zones:
            zone = self.zones[qname]
            if zone['type'] == 'static':
                self.handle_static(zone, request, reply)
            elif zone['type'] == 'geo-dist':
                self.handle_geo_dist(zone, request, reply)

        if fdns.debug:
            print "Reply:\n", reply

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


    def handle_geo_dist(self, zone, request, reply):
        qtype = dnslib.QTYPE[request.q.qtype]

        return True


    def construct_rdata(self, rr):
        t = rr['type']
        if t == "SOA":
            return dnslib.SOA(mname=rr['mname'], rname=rr['rname'], times=rr['times'])
        if t in ('A', 'AAAA', 'NS', 'CNAME', 'TXT'):
            cls = dnslib.RDMAP[t]
            print "Class is ", cls.__name__
            return cls(rr['value'])

        return None
