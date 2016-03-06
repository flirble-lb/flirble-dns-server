#!/usr/bin/env python
# Flirble DNS Server
# Handlers for data from clients
#
#    Copyright 2016 Chris Luke
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, time, datetime, socket, threading
import traceback
import SocketServer

import __init__ as fdns

"""Default number of concurrent handler threads to run."""
MAXIMUM_HANDLER_THREADS = 128

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
            raise Exception("TCP packet larger than expected (%d > %d)" %
                (sz, len(data)-2))
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
Mix-in class to handle each request in a new thread. Based on the
class of the same name in SocketServer.
"""
class ThreadingMixIn:

    """Decides how threads will act upon termination of the
    main process."""
    daemon_threads = False

    """Maximum number of concurrent handler threads to spawn."""
    maximum_handler_threads = None

    """A lock to wrap thread count variables."""
    _clock = threading.Lock()

    """The current thread counter."""
    _handler_count = 0


    """
    Same as in BaseServer but as a thread.
    In addition, exception handling is done here.
    """
    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
            self.shutdown_request(request)
        except:
            self.handle_error(request, client_address)
            self.shutdown_request(request)

        # Work is done, lower the tide mark
        with self._clock:
            self._handler_count -= 1

            if fdns.debug:
                log.debug("Completed request from %s port %d decreases " \
                    "thread count to %d." %
                    (client_address[0], client_address[1],
                        self._handler_count))


    """
    Request handler. Checks the thread count and if not too high then spawns
    a thread to handle the request.
    """
    def process_request(self, request, client_address):
        with self._clock:
            if self.maximum_handler_threads is None:
                self.maximum_handler_threads = fdns.MAXIMUM_HANDLER_THREADS

            if self._handler_count >= self.maximum_handler_threads:
                # Too many threads, ignore this request
                # TODO: account for this
                if fdns.debug:
                    log.warning("Dropping request from (%s %d) because " \
                        "thread count is at maximum of %d." %
                        (client_address[0], client_address[1],
                            self.maximum_handler_threads))
                return

            # We can spawn the thread, raise the tide
            self._handler_count += 1

            if fdns.debug:
                log.debug("New request from (%s %d) increases thread " \
                    "count to %d." %
                    (client_address[0], client_address[1],
                        self._handler_count))

        # Start a new thread to process the request.
        t = threading.Thread(target = self.process_request_thread,
                             args = (request, client_address))
        t.daemon = self.daemon_threads
        t.start()

class ThreadingUDPServer(ThreadingMixIn, SocketServer.UDPServer): pass
class ThreadingTCPServer(ThreadingMixIn, SocketServer.TCPServer): pass

"""
A subclass of SocketServer.ThreadingUDPServer that sets the parameters for
our UDP server, including enabling IPv6.
"""
class UDPServer(ThreadingUDPServer):
    """Bind to the IPv6 socket. On most systems this will also accept IPv4."""
    address_family = socket.AF_INET6
    """Allows the server to ignore lingering data from a previous socket."""
    allow_reuse_address = True
    """Let threads die peacefully when the process dies."""
    daemon_threads = True

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
        ThreadingUDPServer.__init__(self, server_address, RequestHandlerClass)

        if response is not None:
            self.response = response


"""
A subclass of SocketServer.ThreadingTCPServer that sets the parameters for
our UDP server, including enabling IPv6.
"""
class TCPServer(ThreadingTCPServer):
    """Bind to the IPv6 socket. On most systems this will also accept IPv4."""
    address_family = socket.AF_INET6
    """Allows the server to ignore lingering data from a previous socket."""
    allow_reuse_address = True
    """Let threads die peacefully when the process dies."""
    daemon_threads = True

    """The DNS handler that will handle requests."""
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
        ThreadingTCPServer.__init__(self, server_address, RequestHandlerClass)

        if response is not None:
            self.response = response


