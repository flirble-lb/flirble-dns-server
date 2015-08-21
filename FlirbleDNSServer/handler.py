#!/usr/bin/env python
# Flirble DNS Server
# Handlers for data from clients

import sys, time, datetime
import traceback
import SocketServer

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns


class BaseRequestHandler(SocketServer.BaseRequestHandler):
    def __init__(self, request, client_address, server, response=None):
        SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)
        self.allow_reuse_address = True
        self.response = response

    def get_data(self):
        raise NotImplementedError

    def send_data(self, data):
        raise NotImplementedError

    def handle(self):
        if fdns.debug:
            now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            print "\n\n%s request %s (%s %s):" % (self.__class__.__name__[:3],
                now, self.client_address[0],
                self.client_address[1])
        try:
            data = self.get_data()
            if fdns.debug:
                print len(data), data.encode('hex')
            if self.server.response is not None:
                reply = self.server.response.handler(data, self.client_address)
                self.send_data(reply)
        except Exception:
            traceback.print_exc(file=sys.stderr)


class UDPRequestHandler(BaseRequestHandler):

    def get_data(self):
        return self.request[0]

    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


class TCPRequestHandler(BaseRequestHandler):

    max_packet_size = 8192

    def get_data(self):
        data = self.request.recv(self.max_packet_size)
        sz = int(data[:2].encode('hex'), 16)
        while len(data) - 2 < sz:
            data += self.request.recv(self.max_packet_size)
        if sz < len(data) - 2:
            raise Exception("TCP packet larger than expected (%d > %d)" % (sz, len(data)-2))
        return data[2:]

    def send_data(self, data):
        sz = hex(len(data))[2:].zfill(4).decode('hex')
        return self.request.sendall(sz + data)


class UDPServer(SocketServer.ThreadingUDPServer):

    response = None

    def __init__(self, server_address, RequestHandlerClass, response=None):
        SocketServer.ThreadingUDPServer.__init__(self, server_address, RequestHandlerClass)

        self.response = response


class TCPServer(SocketServer.ThreadingTCPServer):

    response = None

    def __init__(self, server_address, RequestHandlerClass, response=None):
        SocketServer.ThreadingTCPServer.__init__(self, server_address, RequestHandlerClass)

        self.response = response


