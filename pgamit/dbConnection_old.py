"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class is used to connect to the database and handles inserts, updates and selects
It also handles the error, info and warning messages
"""

import platform
import configparser
import inspect
import re
from datetime import datetime
from decimal import Decimal

# deps
import pg
import pgdb

# app
from pgamit.Utils import file_read_all, file_append, create_empty_cfg


DB_HOST = 'localhost'
DB_USER = 'postgres'
DB_PASS = ''
DB_NAME = 'gnss_data'


DEBUG = False


def debug(s):
    if DEBUG:
        file_append('/tmp/db.log', "DB: %s\n" % s)


class dbErrInsert (Exception): pass


class dbErrUpdate (Exception): pass


class dbErrConnect(Exception): pass


class dbErrDelete (Exception): pass


class IntegrityError(pg.IntegrityError): pass


class Cnn(pg.DB):

    def __init__(self, configfile, use_float=False, write_cfg_file=False):

        # set casting of numeric to floats
        pg.set_typecast('Numeric', float)

        options = {'hostname': DB_HOST,
                   'username': DB_USER,
                   'password': DB_PASS,
                   'database': DB_NAME}

        self.active_transaction = False
        self.options            = options
        
        # parse session config file
        config = configparser.ConfigParser()

        try:
            config.read_string(file_read_all(configfile))
        except FileNotFoundError:
            if write_cfg_file:
                create_empty_cfg()
                print(' >> No gnss_data.cfg file found, an empty one has been created. Replace all the necessary '
                      'config and try again.')
                exit(1)
            else:
                raise
        # get the database config
        options.update(dict(config.items('postgres')))

        # open connection to server
        err = None
        for i in range(3):
            try:
                pg.DB.__init__(self,
                               host   = options['hostname'],
                               user   = options['username'],
                               passwd = options['password'],
                               dbname = options['database'])
                # set casting of numeric to floats
                pg.set_typecast('Numeric', float)
                pg.set_decimal(float if use_float else
                               Decimal)
            except pg.InternalError as e:
                err = e
                if 'Operation timed out' in str(e) or \
                   'Connection refused'  in str(e):
                    continue
                else:
                    raise e
            else:
                break
        else:
            raise dbErrConnect(err)

        # open a conenction to a cursor
        self.cursor_conn = pgdb.connect(host     = options['hostname'],
                                        user     = options['username'],
                                        password = options['password'],
                                        database = options['database'])

        self.cursor = self.cursor_conn.cursor()

    def query(self, command, *args):
        err = None
        for i in range(3):
            try:
                #print('log-db-query', command, args)
                rs = pg.DB.query(self, command, *args)
            except ValueError as e:
                # connection lost, attempt to reconnect
                self.reopen()
                err = e
            else:
                break
        else:
            raise Exception('dbConnection.query failed after 3 retries. Last error was: ' + str(err))

        debug(" QUERY: command=%r args=%r" % (command, args))
        # debug(" ->RES: %s" % repr(rs))

        return rs

    def query_float(self, command, as_dict=False):

        pg.set_typecast('Numeric', float)
        pg.set_decimal(float)

        err = None
        for i in range(3):
            try:
                rs = self.query(command)
            except ValueError as e:
                # connection lost, attempt to reconnect
                self.reopen()
                err = e
            else:
                break
        else:
            raise Exception('dbConnection.query_float failed after 3 retries. Last error was: ' + str(err))

        recordset = rs.dictresult() if as_dict else rs.getresult()

        pg.set_typecast('Numeric', Decimal)
        pg.set_decimal(Decimal)

        debug("QUERY_FLOAT: command=%s" % repr(command))
        # debug("      ->RES: %s" % repr(recordset))
        return recordset

    def get_columns(self, table):
        tblinfo = self.query('select column_name, data_type from information_schema.columns where table_name=\'%s\''
                             % table).dictresult()

        return { field['column_name'] : field['data_type']
                 for field in tblinfo }

    def begin_transac(self):
        # do not begin a new transaction with another one active.
        if self.active_transaction:
            self.rollback_transac()

        self.active_transaction = True
        self.begin()

    def commit_transac(self):
        self.active_transaction = False
        self.commit()

    def rollback_transac(self):
        self.active_transaction = False
        self.rollback()

    def insert(self, table, row=None, **kw):
        debug("INSERT: table=%r row=%r kw=%r" % (table,row,kw))

        err = None
        for i in range(3):
            try:
                #print('log-db-insert', table, row, kw)
                pg.DB.insert(self, table, row, **kw)
            except ValueError as e:
                # connection lost, attempt to reconnect
                self.reopen()
                err = e
            except Exception as e:
                raise dbErrInsert(e)
            else:
                break
        else:
            raise dbErrInsert('dbConnection.insert failed after 3 retries. Last error was: ' + str(err))

    def executemany(self, sql, parameters):
        debug("EXECUTEMANY: sql=%r parameters=%r" % (sql, parameters))

        try:
            self.begin_transac()
            self.cursor_conn.executemany(sql, parameters)
            self.cursor_conn.commit()
        except pg.Error:
            self.rollback_transac()
            raise

    def update(self, table, row=None, **kw):
        debug("UPDATE: table=%r row=%r kw=%r" % (table, row, kw))

        err = None
        for i in range(3):
            try:
                #print('log-db-update', table, row, kw)
                pg.DB.update(self, table, row, **kw)
            except ValueError as e:
                # connection lost, attempt to reconnect
                self.reopen()
                err = e
            except Exception as e:
                raise dbErrUpdate(e)
            else:
                break
        else:
            raise dbErrUpdate('dbConnection.update failed after 3 retries. Last error was: ' + str(err))

    def delete(self, table, row=None, **kw):
        debug("DELETE: table=%r row=%r kw=%r" % (table, row, kw))

        err = None
        for i in range(3):
            try:
                #print('log-db-delete', table, row, kw)
                pg.DB.delete(self, table, row, **kw)
            except ValueError as e:
                # connection lost, attempt to reconnect
                self.reopen()
                err = e
            except Exception as e:
                raise dbErrDelete(e)
            else:
                break
        else:
            raise dbErrDelete('dbConnection.delete failed after 3 retries. Last error was: ' + str(err))

    def insert_event(self, event):
        debug("EVENT: event=%r" % (event.db_dict()))

        self.insert('events', event.db_dict())

    def insert_event_bak(self, type, module, desc):
        debug("EVENT_BAK: type=%r module=%r desc=%r" % (type, module, desc))

        # do not insert if record exists
        desc = '%s%s' % (module, desc.replace('\'', ''))
        desc = re.sub(r'[^\x00-\x7f]+', '', desc)
        # remove commands from events
        # modification introduced by DDG (suggested by RS)
        desc = re.sub(r'BASH.*', '', desc)
        desc = re.sub(r'PSQL.*', '', desc)

        # warn = self.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        # if warn.ntuples() == 0:
        self.insert('events', EventType=type, EventDescription=desc)

    def insert_warning(self, desc):
        self.insert_event_bak('warn', _caller_str(), desc)

    def insert_error(self, desc):
        self.insert_event_bak('error', _caller_str(), desc)

    def insert_info(self, desc):
        self.insert_event_bak('info', _caller_str(), desc)

    def __del__(self):
        if self.active_transaction:
            self.rollback()


def _caller_str():
    # get the module calling to make clear how is logging this message
    frame = inspect.stack()[2]
    line   = frame[2]
    caller = frame[3]
    
    return '[%s:%s(%s)]\n' % (platform.node(), caller, str(line))

