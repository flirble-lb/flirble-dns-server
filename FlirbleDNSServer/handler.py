#!/usr/bin/env python
# Flirble DNS Server
# Handlers for data from clients

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, time, datetime, socket
import traceback
import SocketServer

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

"""
Base DNS handling SocketServer request handler.
"""
class BaseRequestHandler(SocketServer.BaseRequestHandler):

    """
    This should be implemented by subclases and will attempt to retrieve the
    next complete raw DNS packet.

    @return str A raw, complete DNS packet.
    """
    def get_data(self):
        raise NotImplementedError

    """
    This should be implemented by subclases and will attempt to send a
    complete raw DNS packet to our configured destination.

    @return int The number of bytes sent.
    """
    def send_data(self, data):
        raise NotImplementedError

    """
    Called when an incoming packet is detected on a socket. This method
    invokes the get_data() method on the subclassed object to retrieve the
    packet and then dispatches it to the handler in self.response.
    """
    def handle(self):
        if fdns.debug:
            now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            log.debug("%s request %s (%s %s):" % (self.__class__.__name__[:3],
                now, self.client_address[0],
                self.client_address[1]))
        try:
            data = self.get_data()
            if self.server.response is not None:
                reply = self.server.response.handler(data, self.client_address)
                self.send_data(reply)
        except Exception:
            log.error("Exception handling data: %s" % traceback.format_exc())


"""
Subclass of BaseRequestHandler that implements UDP packet sending and
reception.
"""
class UDPRequestHandler(BaseRequestHandler):

    """
    Attempts to retrieve the next complete raw DNS packet.

    @return str A raw, complete DNS packet.
    """
    def get_data(self):
        return self.request[0]

    """
    Attempts to send a complete raw DNS packet to our configured destination.

    @return int The number of bytes sent.
    """
    def send_data(self, data):
        return self.request[1].sendto(data, self.client_address)


"""
Subclass of BaseRequestHandler that implements TCP packet sending and
reception.
"""
class TCPRequestHandler(BaseRequestHandler):

    """Number of bytes to attempt to receive at a time."""
    max_packet_size = 8192

    """
    Attempts to retrieve the next complete raw DNS packet. In particular,
    for TCP, it reads the DNS "length" value that is expected at the start of
    a TCP DNS packet and will wait for all the anticipated data to arrive,
    returning a only complete DNS packet.

    @return str A raw, complete DNS packet.
    """
    def get_data(self):
        data = self.request.recv(self.max_packet_size)
        sz = int(data[:2].encode('hex'), 16)
        while len(data) - 2 < sz:
            data += self.request.recv(self.max_packet_size)
        if sz < len(data) - 2:
            raise Exception("TCP packet larger than expected (%d > %d)" % (sz, len(data)-2))
        return data[2:]

    """
    Attempts to send a complete raw DNS packet to our configured destination.
    TCP connections encode a 16-bit word on the front indicating the size of
    the DNS payload, which this method adds.

    @return int The number of bytes sent.
    """
    def send_data(self, data):
        sz = hex(len(data))[2:].zfill(4).decode('hex')
        return self.request.sendall(sz + data)


"""
A subclass of SocketServer.ThreadingUDPServer that sets the parameters for
our UDP server, including enabling IPv6.
"""
class UDPServer(SocketServer.ThreadingUDPServer):
    """Bind to the IPv6 socket. On most systems this will also accept IPv4."""
    address_family = socket.AF_INET6
    """Allows the server to ignore lingering data from a previous socket."""
    allow_reuse_address = True

    response = None

    """
    This constructor override adds the response parameter which is a reference
    to a DNS handling Request object.

    @param server_address list A tuple of (ip_address, protocol_port) that
                indicates the local bound endpoint address and port.
    @param RequestHandlerClass RequestHandler The request handler class
                to to instantiate for each request.
    @param response Request The DNS processor that will interpret requests
                presented to this handler.
    """
    def __init__(self, server_address, RequestHandlerClass, response=None):
        SocketServer.ThreadingUDPServer.__init__(self, server_address, RequestHandlerClass)

        if response is not None:
            self.response = response


"""
A subclass of SocketServer.ThreadingTCPServer that sets the parameters for
our UDP server, including enabling IPv6.
"""
class TCPServer(SocketServer.ThreadingTCPServer):
    """Bind to the IPv6 socket. On most systems this will also accept IPv4."""
    address_family = socket.AF_INET6
    """Allows the server to ignore lingering data from a previous socket."""
    allow_reuse_address = True

    response = None

    """
    This constructor override adds the response parameter which is a reference
    to a DNS handling Request object.

    @param server_address list A tuple of (ip_address, protocol_port) that
                indicates the local bound endpoint address and port.
    @param RequestHandlerClass RequestHandler The request handler class
                to to instantiate for each request.
    @param response Request The DNS processor that will interpret requests
                presented to this handler.
    """
    def __init__(self, server_address, RequestHandlerClass, response=None):
        SocketServer.ThreadingTCPServer.__init__(self, server_address, RequestHandlerClass)

        if response is not None:
            self.response = response


