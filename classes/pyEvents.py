"""
Project: Parallel.PPP
Date: 10/25/17 8:53 AM
Author: Demian D. Gomez

Class to manage (insert, create and query) events produced by the Parallel.PPP wrapper
"""
import datetime
import platform
import traceback
import inspect
import re


class Event(dict):

    def __init__(self, **kwargs):

        dict.__init__(self)

        self['EventDate']   = datetime.datetime.now()
        self['EventType']   = 'info'
        self['NetworkCode'] = None
        self['StationCode'] = None
        self['Year']        = None
        self['DOY']         = None
        self['Description'] = ''
        self['node']        = platform.node()
        self['stack']       = None

        module = inspect.getmodule(inspect.stack()[1][0])
        stack  = traceback.extract_stack()[0:-2]

        if module is None:
            self['module'] = inspect.stack()[1][3]  # just get the calling module
        else:
            # self['module'] = module.__name__ + '.' + inspect.stack()[1][3]  # just get the calling module
            self['module'] = module.__name__ + '.' + stack[-1][2]  # just get the calling module

        # initialize the dictionary based on the input
        for key in kwargs:
            if key not in self.keys():
                raise Exception('Provided key not in list of valid fields.')

            arg = kwargs[key]
            self[key] = arg

        if self['EventType'] == 'error':
            self['stack'] = ''.join(traceback.format_stack()[0:-2])  # print the traceback until just before this call
        else:
            self['stack'] = None

        

    def db_dict(self):
        # remove any invalid chars that can cause problems in the database
        # also, remove the timestamp so that we use the default now() in the databasae
        # out of sync clocks in nodes can cause problems.
        val = self.copy()
        val.pop('EventDate')

        for key in val:
            s = val[key]
            if type(s) is str:
                s = re.sub(r'[^\x00-\x7f]+', '', s)
                s = s.replace('\'', '"')
                s = re.sub(r'BASH.*', '', s)
                s = re.sub(r'PSQL.*', '', s)
                val[key] = s

        return val

    def __repr__(self):
        return 'pyEvent.Event(%s)' % str(self['Description'])

    def __str__(self):
        return str(self['Description'])

