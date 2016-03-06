#!/usr/bin/env python
# Flirble DNS Server
# RethinkDB handler
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

import sys, threading, time, traceback
import rethinkdb as r

import __init__ as fdns

"""
Manages the connection with a RethinkDB.

There is at least one connection to the DB, used to queries and updates.
Further connections may be initiated and managed from their own threads
to monitor tables for changes; any such changes are delivered to callback
functions.
"""
class Data(object):
    r = None
    rlock = None
    _table_threads = None
    _tlock = None
    _running = None

    """
    Configure the database manager.

    This does not start any connections, it only configures the object.

    @param remote str The remote database to connect to in the format
            "host:port". ':port' is optional and will the RethinkDB client
            driver will default to '28015'.
    @param name str The name of the database on the host to use.
    @param auth str An authentication key. Defaults to an empty string.
    @param ssl dict SSL options. See RethinkDB 'connect' for details.
    """
    def __init__(self, remote, name, auth=None, ssl=dict()):
        super(Data, self).__init__()

        if auth is None:
            auth = ""

        self._table_threads = {}

        if ':' in remote:
            (host, port) = remote.split(':')
        else:
            host = remote
            port = None

        self._host = host
        self._port = port
        self._name = name
        self._auth = auth
        self._ssl = ssl

        self.rlock = threading.Lock()
        self._tlock = threading.Lock()

        self.running = False


    """
    Start the primary database connection.

    @returns bool True on success, False otherwise.
    """
    def start(self):
        log.info("Connecting to RethinkDB at '%s:%s' db '%s'." %
            (self._host, self._port, self._name))
        try:
            self.r = r.connect(host=self._host, port=self._port,
                db=self._name, auth_key=self._auth, ssl=self._ssl)
        except r.ReqlDriverError as e:
            log.error("Unable to connect to RethinkDB at '%s:%s' " \
                "db '%s': %s." %
                (self._host, self._port, self._name, e.message))
            log.debug("%s." % traceback.format_exc())
            return False

        self.running = True


    """
    Adds a thread monitoring a table for changes, calling the cb when
    a change is made.

    The thread is a daemon thread so it will does not block the process
    from exiting.

    @param table str The name of the table to monitor.
    @param cb function A function to call when changes arrive. This should
        match the signature 'def _cb(self, rdb, change)' where 'rdb' is
        a reference to this calling object and 'change' is a dictionary
        containing the change. See RethinkDB documentation for the contents
        of 'chamge'.
    @returns bool True on success, False otherwise. Reasons to fail include
        failing to connect to the database or trying to monitor a table
        we're monitoring.
    """
    def register_table(self, table, cb):
        # create _monitor_thread

        if table in self._table_threads:
            return False

        log.info("Connecting to RethinkDB at '%s:%s' db '%s' to monitor " \
            "table '%s'." % (self._host, self._port, self._name, table))
        try:
            connection = r.connect(host=self._host, port=self._port,
                db=self._name, auth_key=self._auth, ssl=self._ssl)
        except r.ReqlDriverError as e:
            log.error("Unable to connect to RethinkDB at '%s:%s' " \
                "db '%s': %s." %
                (self._host, self._port, self._name, e.message))
            log.debug("%s." % traceback.format_exc())
            return False

        args = {
            'table': table,
            'cb': cb,
            'connection': connection
        }

        try:
            t = threading.Thread(target=self._monitor_thread, kwargs=args)
        except Exception as e:
            log.error("Unable to start monitoring thread for " \
                "table '%s': %s." % (table, e.message))
            log.debug("%s." % traceback.format_exc())
            connection.close()
            return False

        with self._tlock:
            self._table_threads[table] = {
                "thread": t,
                "connection": connection
            }

        t.daemon = True
        t.start()

        return True


    """
    The thread target that monitors a table for changes.

    @param table str The name of the table to monitor.
    @param cb function The callback function that will be called.
    @param connection rethinkdb.Connection The database connection to use
        for the monitoring.
    """
    def _monitor_thread(self, table, cb, connection):
        log.info("Monitoring table '%s' for changes." % table)
        feed = r.table(table).changes(include_initial=True).run(connection)

        # TODO need to find a way to make this interruptible for a cleaner
        # exit when we're asked to stop running
        for change in feed:
            cb(self, change)

            if not self.running:
                break

        log.info("Closing RethinkDB connection for " \
            "monitoring table '%s'." % table)

        with self._tlock:
            del(self._table_threads[table])

        try:
            connection.close()
        except:
            pass


    """
    Stop all running data monitoring threads and shutdown connections
    to the database.
    """
    def stop(self):
        log.info("Shutting down table monitoring threads...")
        self.running = False

        for table in self._table_threads:
            tt = self._table_threads[table]
            log.debug("Waiting for thread monitoring " \
                "table '%s' to stop..." % table)
            tt['thread'].join(1)

        log.info("Closing main RethinkDB connection...")
        self.r.close()

        # Cleanup
        self._table_threads = {}
        self.r = None
