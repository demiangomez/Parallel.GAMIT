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

        self['EventDate'] = datetime.datetime.now()
        self['EventType'] = 'info'
        self['NetworkCode'] = None
        self['StationCode'] = None
        self['Year'] = None
        self['DOY'] = None
        self['Description'] = ''
        self['node'] = platform.node()
        self['stack'] = None

        module = inspect.getmodule(inspect.stack()[1][0])

        if module is None:
            self['module'] = inspect.stack()[1][3]  # just get the calling module
        else:
            self['module'] = module.__name__ + '.' + inspect.stack()[1][3]  # just get the calling module

        # initialize the dictionary based on the input
        for key in kwargs:
            if key not in self.keys():
                raise Exception('Provided key not in list of valid fields.')

            arg = kwargs[key]
            self[key] = arg

        if self['EventType'] == 'error':
            self['stack'] = ''.join(traceback.format_stack()[0:-1])  # print the traceback until just before this call
        else:
            self['stack'] = None

    def db_dict(self):
        # remove any invalid chars that can cause problems in the database
        val = self

        for key in val:
            if type(val[key]) is str:
                val[key] = re.sub(r'[^\x00-\x7f]+', '', val[key])
                val[key] = val[key].replace('\'', '"')
                val[key] = re.sub(r'BASH.*', '', val[key])
                val[key] = re.sub(r'PSQL.*', '', val[key])

        return val

