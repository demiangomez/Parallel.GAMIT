"""
project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Ocean loading coefficients class. It runs and reads grdtab (from GAMIT).
"""

import os
import uuid

# app
from pgamit import pyRunWithRetry
from pgamit import pyEvents
from pgamit.Utils import file_read_all


class pyOTLException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)
    def __str__(self):
        return str(self.value)

class OceanLoading():

    def __init__(self, StationCode, grdtab, otlgrid, x=None, y=None, z=None):

        self.x = None
        self.y = None
        self.z = None

        # generate a unique id for this instance
        self.rootdir     = os.path.join('production', 'otl_calc', str(uuid.uuid4()))
        self.StationCode = StationCode

        try:
            # create a production folder to analyze the rinex file
            if not os.path.exists(self.rootdir):
                os.makedirs(self.rootdir)
        except:
            # could not create production dir! FATAL
            raise

        # verify of link to otl.grid exists
        grid_path = os.path.join(self.rootdir, 'otl.grid')
        if not os.path.isfile(grid_path):
            # should be configurable
            try:
                os.symlink(otlgrid, grid_path)
            except Exception as e:
                raise pyOTLException(e)

        if not os.path.isfile(grdtab):
            raise pyOTLException('grdtab could not be found at the specified location: ' + grdtab)
        else:
            self.grdtab = grdtab

        if not (x is None and y is None and z is None):
            self.x = x
            self.y = y
            self.z = z

    def calculate_otl_coeff(self,x=None,y=None,z=None):

        if not self.x and (x is None or y is None or z is None):
            raise pyOTLException('Cartesian coordinates not initialized and not provided in calculate_otl_coef')

        if not self.x:
            self.x = x
        if not self.y:
            self.y = y
        if not self.z:
            self.z = z

        out, err = pyRunWithRetry.RunCommand(self.grdtab +
                                             ' ' + str(self.x) + ' ' + str(self.y) +
                                             ' ' + str(self.z) + ' ' + self.StationCode,
                                             5,
                                             self.rootdir).run_shell()
        if err:
            raise pyOTLException('grdtab returned an error: ' + err)

        fatal_path  = os.path.join(self.rootdir, 'GAMIT.fatal')
        harpos_path = os.path.join(self.rootdir, 'harpos.' + self.StationCode)

        if os.path.isfile(fatal_path) and not os.path.isfile(harpos_path):
            raise pyOTLException('grdtab returned an error:\n' + file_read_all(fatal_path))

        # open otl file
        return file_read_all(harpos_path)

    def __del__(self):
        for f in ('GAMIT.status',
                  'GAMIT.fatal',
                  'grdtab.out',
                  'harpos.' + self.StationCode,
                  'otl.grid',
                  'ufile.' + self.StationCode):
            f = os.path.join(self.rootdir, f)
            if os.path.isfile(f):
                os.remove(f)

        if os.path.isdir(self.rootdir):
            os.rmdir(self.rootdir)
