"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class is used to connect to the database and handles inserts, updates and selects
It also handles the error, info and warning messages
"""

import pg
import pgdb
import platform
import ConfigParser
import inspect
import re
from datetime import datetime
from decimal import Decimal


class dbErrInsert(Exception):
    pass


class dbErrUpdate(Exception):
    pass


class dbErrConnect(Exception):
    pass


class dbErrDelete(Exception):
    pass


class Cnn(pg.DB):

    def __init__(self, configfile, use_float=False):

        # set casting of numeric to floats
        pg.set_typecast('Numeric', float)

        options = {'hostname': 'localhost',
           'username': 'postgres' ,
           'password': '' ,
           'database': 'gnss_data'}

        self.active_transaction = False
        self.options = options
        # parse session config file
        config = ConfigParser.ConfigParser()
        config.readfp(open(configfile))

        # get the database config
        for iconfig, val in dict(config.items('postgres')).iteritems():
            options[iconfig] = val

        # open connection to server
        tries = 0
        while True:
            try:
                pg.DB.__init__(self, host=options['hostname'], user=options['username'], passwd=options['password'], dbname=options['database'])
                # set casting of numeric to floats
                pg.set_typecast('Numeric', float)
                if use_float:
                    pg.set_decimal(float)
                else:
                    pg.set_decimal(Decimal)
                break
            except pg.InternalError as e:
                if 'Operation timed out' in str(e) or 'Connection refused' in str(e):
                    if tries < 4:
                        tries += 1
                        continue
                    else:
                        raise dbErrConnect(e)
                else:
                    raise e
            except Exception as e:
                raise e

    def query_float(self, command, as_dict=False):

        pg.set_typecast('Numeric', float)
        pg.set_decimal(float)

        rs = self.query(command)

        if as_dict:
            recordset = rs.dictresult()
        else:
            recordset = rs.getresult()

        pg.set_typecast('Numeric', Decimal)
        pg.set_decimal(Decimal)

        return recordset

    def get_columns(self, table):
        tblinfo = self.query('select column_name, data_type from information_schema.columns where table_name=\'%s\'' % table)

        field_dict = dict()

        for field in tblinfo.dictresult():
            field_dict[field['column_name']] = field['data_type']

        return field_dict

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

        try:
            pg.DB.insert(self, table, row, **kw)
        except Exception as e:
            raise dbErrInsert(e)

    def executemany(self, sql, parameters):

        con = pgdb.connect(host=self.options['hostname'],
                           user=self.options['username'],
                           password=self.options['password'],
                           database=self.options['database'])

        cur = con.cursor()
        cur.executemany(sql, parameters)
        con.commit()

    def update(self, table, row=None, **kw):

        try:
            pg.DB.update(self, table, row, **kw)
        except Exception as e:
            raise dbErrUpdate(e)

    def delete(self, table, row=None, **kw):

        try:
            pg.DB.delete(self, table, row, **kw)
        except Exception as e:
            raise dbErrDelete(e)

    def insert_event(self, event):

        self.insert('events', event.db_dict())

        return

    def insert_event_bak(self, type, module,desc):

        # do not insert if record exists
        desc = '%s%s' % (module, desc.replace('\'', ''))
        desc = re.sub(r'[^\x00-\x7f]+', '', desc)
        # remove commands from events
        # modification introduced by DDG (suggested by RS)
        desc = re.sub(r'BASH.*', '', desc)
        desc = re.sub(r'PSQL.*', '', desc)

        #warn = self.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        #if warn.ntuples() == 0:
        self.insert('events', EventType=type, EventDescription=desc)

        return

    def insert_warning(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        # get the module calling for insert_warning to make clear how is logging this message
        self.insert_event_bak('warn', module, desc)

    def insert_error(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        # get the module calling for insert_warning to make clear how is logging this message
        self.insert_event_bak('error', module, desc)

    def insert_info(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        self.insert_event_bak('info', module, desc)

    def __del__(self):
        if self.active_transaction:
            self.rollback()
