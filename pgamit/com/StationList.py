"""
Project: Parallel.GAMIT
Date: Dic-03-2016
Author: Demian D. Gomez
"""

import configparser
import sys
import os
import getopt
import re


class StationListException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class StationList:

    def __init__(self,src=None):

        self.stn_list = []
        self.src      = []

        # parse station list string into the station list
        try:
            if src != None:
                self.stn_list += re.split(',', src)
        except StationListException as err:
            raise StationListException('Could not parse: '+src+' to a station Python list')

        self._normalize()

    def to_string(self):
        # put station list back to string format
        return ','.join(self.stn_list)

    def addStation(self,stn):
        if isinstance(stn, str):
            self.stn_list += re.split(',', stn)
        elif all(isinstance(item, str) for item in stn):
            # check iterable for stringness of all items. Will raise TypeError if some_object is not iterable
            self.stn_list.append(item for item in stn)
        else:
            raise StationListException('Station input type not recognized')
        
        self._normalize()

    def _normalize(self):
        # remove duplicates
        self.stn_list = list(set(self.stn_list))
        # sort the stations
        self.stn_list.sort()

    def __getitem__(self, item):
        return self.stn_list[item]
