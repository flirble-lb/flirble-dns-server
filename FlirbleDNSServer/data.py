#!/usr/bin/env python
# Flirble DNS Server
# RethinkDB handler

import os, logging
log = logging.getLogger(os.path.basename(__file__))

import sys, threading, time, traceback
import rethinkdb as r

try: import FlirbleDNSServer as fdns
except: import __init__ as fdns

class Data(object):
    r = None
    rlock = None
    _table_threads = None
    _running = None

    def __init__(self, remote=None, name=None, auth=None, ssl=None):
        super(Data, self).__init__()

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

        self.rlock = threading.RLock()

        self.running = False


    def start(self):
        log.info("Connecting to RethinkDB at '%s:%d' db '%s'." % (self._host, self._port, self._name))
        try:
            self.r = r.connect(host=self._host, port=self._port, db=self._name, auth_key=self._auth, ssl=self._ssl)
        except r.ReqlDriverError as e:
            log.error("Unable to connect to RethinkDB at '%s:%d' db '%s': %s." % (self._host, self._port, self._name, e.strerror))
            log.debug("Traceback:\n%s." % traceback.format_exc())
            return False

        self.running = True


    """
    Adds a thread monitoring a table for changes, calling the cb when
    a change is made.
    """
    def register_table(self, table, cb):
        # create _monitor_thread

        if table in self._table_threads:
            return False

        log.info("Connecting to RethinkDB at '%s:%d' db '%s' to monitor table '%s'." % (self._host, self._port, self._name, table))
        try:
            connection = r.connect(host=self._host, port=self._port, db=self._name, auth_key=self._auth, ssl=self._ssl)
        except r.ReqlDriverError as e:
            log.error("Unable to connect to RethinkDB at '%s:%d' db '%s': %s." % (self._host, self._port, self._name, e.strerror))
            log.debug("Traceback:\n%s." % traceback.format_exc())
            return False

        args = {
            'table': table,
            'cb': cb,
            'connection': connection
        }

        try:
            t = threading.Thread(target=self._monitor_thread, kwargs=args)
        except Exception as e:
            log.error("Unable to start monitoring thread for table '%s': %s." % (table, e.strerror))
            log.debug("Traceback:\n%s." % traceback.format_exc())
            connection.close()
            return False

        self._table_threads[table] = {
            "thread": t,
            "connection": connection
        }

        t.start()

        return True


    """
    Creates a new connection to the database and monitors a table for changes.
    """
    def _monitor_thread(self, table, cb, connection):
        log.info("Monitoring table '%s' for changes." % table)
        feed = r.table(table).changes(include_initial=True).run(connection)

        # TODO need to find a way to make this interruptible when we're asked to stop running
        for change in feed:
            cb(self, change)

            if not self.running:
                break

        log.info("Closing RethinkDB connection for monitoring table '%s'." % table)

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
            log.debug("Waiting for thread monitoring table '%s' to stop..." % table)
            tt['thread'].join()

        log.info("Closing main RethinkDB connection...")
        self.r.close()

        # Cleanup
        self._table_threads = {}
        self.r = None
