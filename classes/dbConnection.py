"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class is used to connect to the database and handles inserts, updates and selects
It also handles the error, info and warning messages
"""

import pg
import platform
import ConfigParser
import inspect

class dbErrInsert(Exception):
    pass

class dbErrUpdate(Exception):
    pass

class dbErrConnect(Exception):
    pass

class dbErrDelete(Exception):
    pass

class Cnn(pg.DB):

    def __init__(self,configfile):

        options = {'hostname': 'localhost',
           'username': 'postgres' ,
           'password': 'f8749hel' ,
           'database': 'gnss_data'}

        self.active_transaction = False

        # parse session config file
        config = ConfigParser.ConfigParser()
        config.readfp(open(configfile))

        # get the database config
        for iconfig,val in dict(config.items('postgres')).iteritems():
            options[iconfig] = val

        # open connection to server
        tries = 0
        while True:
            try:
                pg.DB.__init__(self,host=options['hostname'], user=options['username'], passwd=options['password'], dbname=options['database'])
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

    def insert_event(self,type,module,desc):

        # do not insert if record exists
        desc = '%s%s' % (module, desc.replace('\'', ''))
        warn = self.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        if warn.ntuples() == 0:
            self.insert('events', EventType=type, EventDescription=desc)

        return

    def insert_warning(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        # get the module calling for insert_warning to make clear how is logging this message
        self.insert_event('warn', module, desc)

    def insert_error(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        # get the module calling for insert_warning to make clear how is logging this message
        self.insert_event('error', module, desc)

    def insert_info(self, desc):
        line = inspect.stack()[1][2]
        caller = inspect.stack()[1][3]

        mod = platform.node()

        module = '[%s:%s(%s)]\n' % (mod, caller, str(line))

        self.insert_event('info', module, desc)

    def __del__(self):
        if self.active_transaction:
            self.rollback()
