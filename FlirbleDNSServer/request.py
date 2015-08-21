#!/usr/bin/env python
# Flirble DNS Server
# Request handler

import sys
import dnslib

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

TTL = 30

records = {
    "test.l.flirble.org.": [ dnslib.A('1.2.3.4') ]
}

class Request(object):

    def __init__(self):
        super(Request, self).__init__()


    def handler(self, data, address):
        request = dnslib.DNSRecord.parse(data)

        if fdns.debug:
            print "Request:\n", request

        qname = str(request.q.qname)
        qtype = dnslib.QTYPE[request.q.qtype]

        reply = dnslib.DNSRecord(dnslib.DNSHeader(id=request.header.id, qr=1, aa=1, ra=1), q=request.q)

        if qname in records:
            for rdata in records[qname]:
                qt = rdata.__class__.__name__
                if qtype in ('*', qt):
                    reply.add_answer(dnslib.RR(rname=request.q.qname, ttl=TTL, rdata=rdata))

        if fdns.debug:
            print "Reply:\n", reply

        return reply.pack()
