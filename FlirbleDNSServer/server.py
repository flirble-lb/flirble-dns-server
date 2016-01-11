#!/usr/bin/env python
# Flirble DNS Server
# Main server

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, threading, time
import SocketServer

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

"""Default local bind address."""
ADDRESS = '::'
"""Default local bind port."""
PORT = 8053


"""
The DNS Server.

Initializes various things then spawns a thread each for the UDP and TCP
services.
"""
class Server(object):

    """The list of SocketServer instances to launch threads for."""
    servers = None

    """
    Initializes the DNS server.

    Creates a Geo object with the path to the GeoIP database.

    Creates a Request handler with the zones and servers files, and the
                Geo reference.

    Then creates TCP and UDP servers, which opens sockets and binds them
    to the given address and port.

    @param rdb FlirbleDNSServer.Data The database object to use.
    @param address str The local address to bind to. Default is "::".
    @param port int The local port number to vind to. Default is "8053".
    @param zones str The zones table to fetch zone data from.
    @param server str The servers table to fetch server data from.
    @param geodb str The Maxmind GeoIP database that the Geo class should
                load. Default is None.
    """
    def __init__(self, rdb, address=ADDRESS, port=PORT, zones=None,
        servers=None, geodb=None):
        super(Server, self).__init__()

        log.debug("Initializing Geo module.")
        geo = fdns.Geo(geodb=geodb)

        log.debug("Initializing Request module.")
        request = fdns.Request(rdb=rdb, zones=zones, servers=servers, geo=geo)

        self.servers = []
        log.debug("Initializing UDP server for '%s' port %d." %
            (address, port))
        self.servers.append(fdns.UDPServer((address, port),
            fdns.UDPRequestHandler, request))
        log.debug("Initializing TCP server for '%s' port %d." %
            (address, port))
        self.servers.append(fdns.TCPServer((address, port),
            fdns.TCPRequestHandler, request))

        self.request = request
        self.geo = geo
        self.rdb = rdb

    """
    Starts the threads and runs the servers. Returns once all services have
    been stopped, either by Exception or ^C.
    """
    def run(self):
        log.debug("Starting TCP and UDP servers.")

        # Start the threads.
        for s in self.servers:
            thread = threading.Thread(target=s.serve_forever)
            thread.daemon = True
            thread.start()

        log.debug("DNS server started.")

        try:
            while True:
                # This is the idle loop.
                time.sleep(30)
                self.request.idle()

        except KeyboardInterrupt:
            pass
        finally:
            log.debug("Shutting down DNS server.")
            for s in self.servers:
                s.shutdown()
            self.rdb.stop()


        self.request = None
        self.geo = None
        self.servers = None
        self.rdb = None


if __name__ == '__main__':
    log.info("Running test DNS server on port %d" % (PORT))
    fdns.debug = True
    server = Server(rdb=None)
    server.run()

