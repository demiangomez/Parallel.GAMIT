"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Ocean loading coefficients class. It runs and reads grdtab (from GAMIT).
"""

import os
import uuid
import pyRunWithRetry
import pyEvents

class pyOTLException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)
    def __str__(self):
        return str(self.value)

class OceanLoading():

    def __init__(self,StationCode,grdtab,otlgrid,x=None,y=None,z=None):

        self.x = None
        self.y = None
        self.z = None

        self.rootdir = os.path.join('production', 'otl_calc')
        # generate a unique id for this instance
        self.rootdir = os.path.join(self.rootdir, str(uuid.uuid4()))
        self.StationCode = StationCode

        try:
            # create a production folder to analyze the rinex file
            if not os.path.exists(self.rootdir):
                os.makedirs(self.rootdir)
        except Exception as excep:
            # could not create production dir! FATAL
            raise

        # verify of link to otl.grid exists
        if not os.path.isfile(os.path.join(self.rootdir, 'otl.grid')):
            # should be configurable
            try:
                os.symlink(otlgrid, os.path.join(self.rootdir, 'otl.grid'))
            except Exception as e:
                raise pyOTLException(e)

        if not os.path.isfile(grdtab):
            raise pyOTLException('grdtab could not be found at the specified location: ' + grdtab)
        else:
            self.grdtab = grdtab

        if not (x is None and y is None and z is None):
            self.x = x; self.y = y; self.z = z
        return

    def calculate_otl_coeff(self,x=None,y=None,z=None):

        if not self.x and (x is None or y is None or z is None):
            raise pyOTLException('Cartesian coordinates not initialized and not provided in calculate_otl_coef')
        else:
            if not self.x:
                self.x = x
            if not self.y:
                self.y = y
            if not self.z:
                self.z = z

            cmd = pyRunWithRetry.RunCommand(self.grdtab + ' ' + str(self.x) + ' ' + str(self.y) + ' ' + str(self.z) + ' ' + self.StationCode, 5, self.rootdir)
            out,err = cmd.run_shell()

            if err or os.path.isfile(os.path.join(self.rootdir, 'GAMIT.fatal')) and not os.path.isfile(os.path.join(self.rootdir, 'harpos.' + self.StationCode)):
                if err:
                    raise pyOTLException('grdtab returned an error: ' + err)
                else:
                    with open(os.path.join(self.rootdir, 'GAMIT.fatal'), 'r') as fileio:
                        raise pyOTLException('grdtab returned an error:\n' +  fileio.read())
            else:
                # open otl file
                with open(os.path.join(self.rootdir,'harpos.' + self.StationCode), 'r') as fileio:
                    return fileio.read()

    def __del__(self):
        if os.path.isfile(os.path.join(self.rootdir, 'GAMIT.status')):
            os.remove(os.path.join(self.rootdir, 'GAMIT.status'))

        if os.path.isfile(os.path.join(self.rootdir, 'GAMIT.fatal')):
            os.remove(os.path.join(self.rootdir, 'GAMIT.fatal'))

        if os.path.isfile(os.path.join(self.rootdir, 'grdtab.out')):
            os.remove(os.path.join(self.rootdir, 'grdtab.out'))

        if os.path.isfile(os.path.join(self.rootdir, 'harpos.' + self.StationCode)):
            os.remove(os.path.join(self.rootdir, 'harpos.' + self.StationCode))

        if os.path.isfile(os.path.join(self.rootdir, 'otl.grid')):
            os.remove(os.path.join(self.rootdir, 'otl.grid'))

        if os.path.isfile(os.path.join(self.rootdir, 'ufile.' + self.StationCode)):
            os.remove(os.path.join(self.rootdir, 'ufile.' + self.StationCode))

        if os.path.isdir(self.rootdir):
            os.rmdir(self.rootdir)
