#!/usr/bin/env python
# Flirble DNS Server
# Main server

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, threading, time
import SocketServer

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

ADDRESS = ''
PORT = 8053


class Server(object):

    servers = None

    def __init__(self, address=ADDRESS, port=PORT, zones=None, servers=None, geodb=None):
        super(Server, self).__init__()

        geo = fdns.Geo(geodb=geodb)
        request = fdns.Request(zones=zones, servers=servers, geo=geo)

        self.servers = []
        log.debug("Initializing UDP server for %s port %s." % (address, port))
        self.servers.append(fdns.UDPServer((address, port), fdns.UDPRequestHandler, request))
        log.debug("Initializing TCP server for %s port %s." % (address, port))
        self.servers.append(fdns.TCPServer((address, port), fdns.TCPRequestHandler, request))


    def run(self):
        log.debug("Starting TCP and UDP servers.")
        for s in self.servers:
            thread = threading.Thread(target=s.serve_forever)
            thread.daemon = True
            thread.start()

        log.debug("DNS server started.")

        try:
            while 1:
                time.sleep(1)
                sys.stderr.flush()
                sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            log.debug("Shutting down DNS server.")
            for s in self.servers:
                s.shutdown()


if __name__ == '__main__':
    log.info("Running test DNS server on port %d" % (PORT))
    fdns.debug = True
    server = Server()
    server.run()

