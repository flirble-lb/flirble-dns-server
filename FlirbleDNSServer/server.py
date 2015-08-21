#!/usr/bin/env python
# Flirble DNS Server
# Main server

import sys, threading, time
import SocketServer

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

ADDRESS = ''
PORT = 8053


class Server(object):

    servers = None

    def __init__(self, address=ADDRESS, port=PORT, zones=None, servers=None):
        super(Server, self).__init__()

        request = fdns.Request(zones=zones, servers=servers)

        self.servers = []
        self.servers.append(fdns.UDPServer((address, port), fdns.UDPRequestHandler, request))
        self.servers.append(fdns.TCPServer((address, port), fdns.TCPRequestHandler, request))


    def run(self):
        for s in self.servers:
            thread = threading.Thread(target=s.serve_forever)
            thread.daemon = True
            thread.start()

        try:
            while 1:
                time.sleep(1)
                sys.stderr.flush()
                sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            for s in self.servers:
                s.shutdown()


if __name__ == '__main__':
    print "Running test DNS server on port %d" % (PORT)
    fdns.debug = True
    server = Server()
    server.run()

