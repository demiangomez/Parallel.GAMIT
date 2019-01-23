"""
Project: Parallel.Archive
Date: 3/3/17 11:27 AM
Author: Demian D. Gomez
"""

import numpy as np
import pyStationInfo
import pyDate
from numpy import sin
from numpy import cos
from numpy import pi
from scipy.stats import chi2
import pyEvents
from zlib import crc32
from Utils import ct2lg
from Utils import lg2ct
from Utils import rotlg2ct
from os.path import getmtime
from itertools import repeat
from pyBunch import Bunch
from pprint import pprint
import traceback
import warnings
import sys
import os
from time import time
from matplotlib.widgets import Button
import matplotlib
if 'DISPLAY' in os.environ.keys():
    if not os.environ['DISPLAY']:
        matplotlib.use('Agg')
else:
    matplotlib.use('Agg')


def tic():

    global tt
    tt = time()


def toc(text):

    global tt
    print text + ': ' + str(time() - tt)


LIMIT = 2.5

NO_EFFECT = None
UNDETERMINED = -1
GENERIC_JUMP = 0
CO_SEISMIC_DECAY = 1
CO_SEISMIC_JUMP_DECAY = 2

EQ_MIN_DAYS = 15
JP_MIN_DAYS = 5

DEFAULT_RELAXATION = np.array([0.5])
DEFAULT_POL_TERMS = 2
DEFAULT_FREQUENCIES = np.array((1/365.25, 1/(365.25/2)))  # (1 yr, 6 months) expressed in 1/days (one year = 365.25)

SIGMA_FLOOR_H = 0.10
SIGMA_FLOOR_V = 0.15

VERSION = '1.0.0'


class pyETMException(Exception):

    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class pyETMException_NoDesignMatrix(pyETMException):
    pass


def distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """

    # convert decimal degrees to radians
    lon1 = lon1*pi/180
    lat1 = lat1*pi/180
    lon2 = lon2*pi/180
    lat2 = lat2*pi/180
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km


def to_postgres(dictionary):

    if isinstance(dictionary, dict):
        for key, val in dictionary.items():
            if isinstance(val, np.ndarray):
                dictionary[key] = str(val.flatten().tolist()).replace('[', '{').replace(']', '}')
    else:
        dictionary = str(dictionary.flatten().tolist()).replace('[', '{').replace(']', '}')

    return dictionary


def to_list(dictionary):

    for key, val in dictionary.items():
        if isinstance(val, np.ndarray):
            dictionary[key] = val.tolist()

        if isinstance(val, pyDate.datetime):
            dictionary[key] = val.strftime('%Y-%m-%d %H:%M:%S')

    return dictionary


class PppSoln:
    """"class to extract the PPP solutions from the database"""

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode
        self.hash = 0

        self.type = 'ppp'

        # get the station from the stations table
        stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                        % (NetworkCode, StationCode))

        stn = stn.dictresult()[0]

        if stn['lat'] is not None:
            self.lat = np.array([float(stn['lat'])])
            self.lon = np.array([float(stn['lon'])])
            self.height = np.array([float(stn['height'])])
            self.auto_x = np.array([float(stn['auto_x'])])
            self.auto_y = np.array([float(stn['auto_y'])])
            self.auto_z = np.array([float(stn['auto_z'])])

            x = np.array([float(stn['auto_x'])])
            y = np.array([float(stn['auto_y'])])
            z = np.array([float(stn['auto_z'])])

            if stn['max_dist'] is not None:
                self.max_dist = stn['max_dist']
            else:
                self.max_dist = 20

            # load all the PPP coordinates available for this station
            # exclude ppp solutions in the exclude table and any solution that is more than 20 meters from the simple
            # linear trend calculated above

            self.excluded = cnn.query_float('SELECT "Year", "DOY" FROM ppp_soln_excl '
                                            'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                                            % (NetworkCode, StationCode))

            self.table = cnn.query_float(
                'SELECT "X", "Y", "Z", "Year", "DOY" FROM ppp_soln p1 '
                'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' ORDER BY "Year", "DOY"'
                % (NetworkCode, StationCode))

            self.table = [item for item in self.table
                          if np.sqrt(np.square(item[0] - x) + np.square(item[1] - y) + np.square(item[2] - z)) <=
                          self.max_dist and item[3:] not in self.excluded]

            self.blunders = [item for item in self.table
                             if np.sqrt(np.square(item[0] - x) + np.square(item[1] - y) + np.square(item[2] - z)) >
                             self.max_dist and item[3:] not in self.excluded]

            self.solutions = len(self.table)

            self.ts_blu = np.array([pyDate.Date(year=item[3], doy=item[4]).fyear for item in self.blunders])

            if self.solutions >= 1:
                a = np.array(self.table)

                self.x = a[:, 0]
                self.y = a[:, 1]
                self.z = a[:, 2]
                self.t = np.array([pyDate.Date(year=item[0], doy=item[1]).fyear for item in a[:, 3:5]])
                self.mjd = np.array([pyDate.Date(year=item[0], doy=item[1]).mjd for item in a[:, 3:5]])

                # continuous time vector for plots
                ts = np.arange(np.min(self.mjd), np.max(self.mjd) + 1, 1)
                self.mjds = ts
                self.ts = np.array([pyDate.Date(mjd=tts).fyear for tts in ts])
            else:
                if len(self.blunders) >= 1:
                    raise pyETMException('No viable PPP solutions available for %s.%s (all blunders!)\n'
                                         '  -> min distance to station coordinate is %.1f meters'
                                         % (NetworkCode, StationCode, np.array([item[5] for item in self.blunders]).min()))
                else:
                    raise pyETMException('No PPP solutions available for %s.%s' % (NetworkCode, StationCode))

            # get a list of the epochs with files but no solutions.
            # This will be shown in the outliers plot as a special marker

            rnx = cnn.query(
                'SELECT r."ObservationFYear" FROM rinex_proc as r '
                'LEFT JOIN ppp_soln as p ON '
                'r."NetworkCode" = p."NetworkCode" AND '
                'r."StationCode" = p."StationCode" AND '
                'r."ObservationYear" = p."Year"    AND '
                'r."ObservationDOY"  = p."DOY"'
                'WHERE r."NetworkCode" = \'%s\' AND r."StationCode" = \'%s\' AND '
                'p."NetworkCode" IS NULL' % (NetworkCode, StationCode))

            self.rnx_no_ppp = rnx.getresult()

            self.ts_ns = np.array([item for item in self.rnx_no_ppp])

            self.completion = 100. - float(len(self.ts_ns)) / float(len(self.ts_ns) + len(self.t)) * 100.

            self.hash = crc32(str(len(self.t) + len(self.blunders)) + ' ' + str(ts[0]) + ' ' + str(ts[-1]))

        else:
            raise pyETMException('Station %s.%s has no valid metadata in the stations table.'
                                 % (NetworkCode, StationCode))


class GamitSoln:
    """"class to extract the GAMIT polyhedrons from the database"""

    def __init__(self, cnn, polyhedrons, NetworkCode, StationCode):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode
        self.hash = 0

        self.type = 'gamit'

        # get the station from the stations table
        stn = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                              % (NetworkCode, StationCode), as_dict=True)[0]

        if stn['lat'] is not None:
            self.lat = np.array([float(stn['lat'])])
            self.lon = np.array([float(stn['lon'])])
            self.height = np.array([stn['height']])
            self.auto_x = np.array([float(stn['auto_x'])])
            self.auto_y = np.array([float(stn['auto_y'])])
            self.auto_z = np.array([float(stn['auto_z'])])

            if stn['max_dist'] is not None:
                self.max_dist = stn['max_dist']
            else:
                self.max_dist = 20

            self.solutions = len(polyhedrons)

            # blunders
            self.blunders = []
            self.ts_blu = np.array([])

            if self.solutions >= 1:
                a = np.array(polyhedrons, dtype=float)

                if np.sqrt(np.square(np.sum(np.square(a[0, 0:3])))) > 6.3e3:
                    # coordinates given in XYZ
                    nb = np.sqrt(np.square(np.sum(
                        np.square(a[:, 0:3] - np.array([stn['auto_x'], stn['auto_y'], stn['auto_z']])), axis=1))) \
                         <= self.max_dist
                else:
                    # coordinates are differences
                    nb = np.sqrt(np.square(np.sum(np.square(a[:, 0:3]), axis=1))) <= self.max_dist

                if np.any(nb):
                    self.x = a[nb, 0]
                    self.y = a[nb, 1]
                    self.z = a[nb, 2]
                    self.t = np.array([pyDate.Date(year=item[0], doy=item[1]).fyear for item in a[nb, 3:5]])
                    self.mjd = np.array([pyDate.Date(year=item[0], doy=item[1]).mjd for item in a[nb, 3:5]])

                    self.date = [pyDate.Date(year=item[0], doy=item[1]) for item in a[nb, 3:5]]

                    # continuous time vector for plots
                    ts = np.arange(np.min(self.mjd), np.max(self.mjd) + 1, 1)
                    self.mjds = ts
                    self.ts = np.array([pyDate.Date(mjd=tts).fyear for tts in ts])
                else:
                    dd = np.sqrt(np.square(np.sum(
                        np.square(a[:, 0:3] - np.array([stn['auto_x'], stn['auto_y'], stn['auto_z']])), axis=1)))

                    raise pyETMException('No viable GAMIT solutions available for %s.%s (all blunders!)\n'
                                         '  -> min distance to station coordinate is %.1f meters'
                                         % (NetworkCode, StationCode, dd.min()))
            else:
                raise pyETMException('No GAMIT polyhedrons vertices available for %s.%s' % (NetworkCode, StationCode))

            # get a list of the epochs with files but no solutions.
            # This will be shown in the outliers plot as a special marker
            rnx = cnn.query(
                'SELECT r.* FROM rinex_proc as r '
                'LEFT JOIN gamit_soln as p ON '
                'r."NetworkCode" = p."NetworkCode" AND '
                'r."StationCode" = p."StationCode" AND '
                'r."ObservationYear" = p."Year"    AND '
                'r."ObservationDOY"  = p."DOY"'
                'WHERE r."NetworkCode" = \'%s\' AND r."StationCode" = \'%s\' AND '
                'p."NetworkCode" IS NULL' % (NetworkCode, StationCode))

            self.rnx_no_ppp = rnx.dictresult()
            self.ts_ns = np.array([float(item['ObservationFYear']) for item in self.rnx_no_ppp])

            self.completion = 100. - float(len(self.ts_ns)) / float(len(self.ts_ns) + len(self.t)) * 100.

            self.hash = crc32(str(len(self.t) + len(self.blunders)) + ' ' + str(ts[0]) + ' ' + str(ts[-1]))

        else:
            raise pyETMException('Station %s.%s has no valid metadata in the stations table.'
                                 % (NetworkCode, StationCode))


class JumpTable:

    def __init__(self, cnn, NetworkCode, StationCode, solution, t, FitEarthquakes=True, FitGenericJumps=True):

        self.table = []

        # get earthquakes for this station
        self.earthquakes = Earthquakes(cnn, NetworkCode, StationCode, solution, t, FitEarthquakes)

        self.generic_jumps = GenericJumps(cnn, NetworkCode, StationCode, solution, t, FitGenericJumps)

        jumps = self.earthquakes.table + self.generic_jumps.table

        jumps.sort()

        # add the relevant jumps, make sure none are incompatible
        for jump in jumps:
            self.insert_jump(jump)

        # add the "NO_EFFECT" jumps and resort the table
        ne_jumps = [j for j in jumps if j.p.jump_type == NO_EFFECT
                    and j.date > pyDate.Date(fyear=t.min()) < j.date < pyDate.Date(fyear=t.max())]

        self.table += ne_jumps

        self.table.sort()

        self.param_count = sum([jump.param_count for jump in self.table])

        self.constrains = np.array([])

    def insert_jump(self, jump):

        if len(self.table) == 0:
            if jump.p.jump_type != NO_EFFECT:
                self.table.append(jump)
        else:
            # take last jump and compare to adding jump
            jj = self.table[-1]

            if jump.p.jump_type != NO_EFFECT:
                result, decision = jj == jump

                if not result:
                    # jumps are not equal, add it
                    self.table.append(jump)
                else:
                    # decision branches:
                    # 1) decision == jump, remove previous; add jump
                    # 2) decision == jj  , do not add jump (i.e. do nothing)
                    if decision is jump:
                        self.table.pop(-1)
                        self.table.append(jump)

    def get_design_ts(self, t):
        # if function call NOT for inversion, return the columns even if the design matrix is unstable

        A = np.array([])

        # get the design matrix for the jump table
        for jump in self.table:
            if jump.p.jump_type is not NO_EFFECT:
                a = jump.eval(t)

                if a.size:
                    if A.size:
                        # if A is not empty, verify that this jump will not make the matrix singular
                        tA = np.column_stack((A, a))
                        # getting the condition number might trigger divide_zero warning => turn off
                        np.seterr(divide='ignore', invalid='ignore')
                        if np.linalg.cond(tA) < 1e10:
                            # adding this jumps doesn't make the matrix singular
                            A = tA
                        else:
                            # flag this jump by setting its type = None
                            jump.remove()
                            warnings.warn('%s had to be removed due to high condition number' % str(jump))
                    else:
                        A = a

        return A

    def load_parameters(self, params, sigmas):

        for jump in self.table:
            jump.load_parameters(params=params, sigmas=sigmas)

    def print_parameters(self):

        output_n = ['Year     Relx    [mm]']
        output_e = ['Year     Relx    [mm]']
        output_u = ['Year     Relx    [mm]']

        for jump in self.table:

            if jump.p.jump_type is not NO_EFFECT:

                # relaxation counter
                rx = 0

                for j, p in enumerate(np.arange(jump.param_count)):
                    psc = jump.p.params[:, p]

                    if j == 0 and jump.p.jump_type in (GENERIC_JUMP, CO_SEISMIC_JUMP_DECAY):
                        output_n.append('{}      {:>7.1f}'.format(jump.date.yyyyddd(), psc[0] * 1000.0))
                        output_e.append('{}      {:>7.1f}'.format(jump.date.yyyyddd(), psc[1] * 1000.0))
                        output_u.append('{}      {:>7.1f}'.format(jump.date.yyyyddd(), psc[2] * 1000.0))
                    else:

                        output_n.append('{} {:4.2f} {:>7.1f}'.format(jump.date.yyyyddd(), jump.p.relaxation[rx],
                                                                     psc[0] * 1000.0))
                        output_e.append('{} {:4.2f} {:>7.1f}'.format(jump.date.yyyyddd(), jump.p.relaxation[rx],
                                                                     psc[1] * 1000.0))
                        output_u.append('{} {:4.2f} {:>7.1f}'.format(jump.date.yyyyddd(), jump.p.relaxation[rx],
                                                                     psc[2] * 1000.0))
                        # relaxation counter
                        rx += 1

        if len(output_n) > 22:
            output_n = output_n[0:22] + ['Table too long to print!']
            output_e = output_e[0:22] + ['Table too long to print!']
            output_u = output_u[0:22] + ['Table too long to print!']

        return '\n'.join(output_n), '\n'.join(output_e), '\n'.join(output_u)


class EtmFunction(object):

    def __init__(self, **kwargs):

        self.p = Bunch()

        self.p.NetworkCode = kwargs['NetworkCode']
        self.p.StationCode = kwargs['StationCode']
        self.p.soln = kwargs['solution']

        self.p.params = np.array([])
        self.p.sigmas = np.array([])
        self.p.object = ''
        self.p.metadata = None
        self.p.hash = 0

        self.param_count = 0
        self.column_index = np.array([])
        self.format_str = ''

    def load_parameters(self, **kwargs):

        params = kwargs['params']
        sigmas = kwargs['sigmas']

        if params.ndim == 1:
            # parameters coming from the database, reshape
            params = params.reshape((3, params.shape[0] / 3))

        if sigmas.ndim == 1:
            # parameters coming from the database, reshape
            sigmas = sigmas.reshape((3, sigmas.shape[0] / 3))

        # determine if parameters are coming from the X vector (LSQ) or from the database (solution for self only)
        if params.shape[1] > self.param_count:
            # X vector
            self.p.params = params[:, self.column_index]
            self.p.sigmas = sigmas[:, self.column_index]
        else:
            # database (solution for self only; no need for column_index)
            self.p.params = params
            self.p.sigmas = sigmas


class Jump(EtmFunction):
    """
    generic jump (mechanic jump, frame change, etc) class
    """
    def __init__(self, NetworkCode, StationCode, solution, t, date, metadata, dtype=UNDETERMINED):

        super(Jump, self).__init__(NetworkCode=NetworkCode, StationCode=StationCode, solution=solution)

        # in the future, can load parameters from the db
        self.p.object = 'jump'

        # define initial state variables
        self.date = date

        self.p.jump_date = date.datetime()
        self.p.metadata = metadata
        self.p.jump_type = dtype

        self.design = Jump.eval(self, t)

        if np.any(self.design) and not np.all(self.design):
            self.p.jump_type = GENERIC_JUMP
            self.param_count = 1
        else:
            self.p.jump_type = NO_EFFECT
            self.param_count = 0

        self.p.hash = crc32(str(self.date))

    def remove(self):
        # this method will make this jump type = 0 and adjust its params
        self.p.jump_type = NO_EFFECT
        self.param_count = 0

    def eval(self, t):
        # given a time vector t, return the design matrix column vector(s)
        if self.p.jump_type == NO_EFFECT:
            return np.array([])

        ht = np.zeros((t.shape[0], 1))

        ht[t > self.date.fyear] = 1.

        return ht

    def __eq__(self, jump):

        if not isinstance(jump, Jump):
            raise pyETMException('type: ' + str(type(jump)) + ' invalid. Can compare two Jump objects')

        # compare two jumps together and make sure they will not generate a singular (or near singular) system of eq
        c = np.sum(np.logical_xor(self.design[:, 0], jump.design[:, 0]))

        if self.p.jump_type in (CO_SEISMIC_JUMP_DECAY,
                              CO_SEISMIC_DECAY) and jump.p.jump_type in (CO_SEISMIC_JUMP_DECAY, CO_SEISMIC_DECAY):

            # if self is a co-seismic jump and next jump is also co-seismic
            # and there are less than two weeks of data to constrain params, return false
            if c <= EQ_MIN_DAYS:
                return True, jump
            else:
                return False, None

        elif self.p.jump_type in (CO_SEISMIC_JUMP_DECAY,
                                CO_SEISMIC_DECAY, GENERIC_JUMP) and jump.p.jump_type == GENERIC_JUMP:

            if c <= JP_MIN_DAYS:
                # can't fit the co-seismic or generic jump AND the generic jump after, remove "jump" generic jump
                return True, self
            else:
                return False, None

        elif self.p.jump_type == GENERIC_JUMP and jump.p.jump_type == (CO_SEISMIC_JUMP_DECAY, CO_SEISMIC_DECAY):

            if c <= JP_MIN_DAYS:
                # if generic jump before an earthquake jump and less than 5 days, co-seismic prevails
                return True, jump
            else:
                return False, None

        elif self.p.jump_type == NO_EFFECT and jump.p.jump_type != NO_EFFECT:
            # if comparing to a self that has NO_EFFECT, remove and keep jump
            return True, jump

        elif self.p.jump_type != NO_EFFECT and jump.p.jump_type == NO_EFFECT:
            # if comparing against a jump that has NO_EFFECT, remove jump keep self
            return True, self

        elif self.p.jump_type == NO_EFFECT and jump.p.jump_type == NO_EFFECT:
            # no jump has an effect, return None. This will be interpreted as False (if not result)
            return None, None

    def __str__(self):
        return '(' + str(self.date)+'), '+str(self.p.jump_type) + ', "' + str(self.p.jump_type) + '"'

    def __repr__(self):
        return 'pyPPPETM.Jump(' + str(self) + ')'

    def __lt__(self, jump):

        if not isinstance(jump, Jump):
            raise pyETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear < jump.date.fyear

    def __le__(self, jump):

        if not isinstance(jump, Jump):
            raise pyETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear <= jump.date.fyear

    def __gt__(self, jump):

        if not isinstance(jump, Jump):
            raise pyETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear > jump.date.fyear

    def __ge__(self, jump):

        if not isinstance(jump, Jump):
            raise pyETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear >= jump.date.fyear

    def __hash__(self):
        # to make the object hashable
        return hash(self.date.fyear)


class CoSeisJump(Jump):

    def __init__(self, NetworkCode, StationCode, solution, t, date, relaxation, metadata, dtype=UNDETERMINED):

        # super-class initialization
        Jump.__init__(self, NetworkCode, StationCode, solution, t, date, metadata, dtype)

        if dtype is NO_EFFECT:
            # passing default_type == NO_EFFECT, add the jump but make it NO_EFFECT by default
            self.p.jump_type = NO_EFFECT
            self.params_count = 0
            self.p.relaxation = None

            self.design = np.array([])
            return

        if self.p.jump_type == NO_EFFECT:
            # came back from init as NO_EFFECT. May be a jump before t.min()
            # assign just the decay
            self.p.jump_type = CO_SEISMIC_DECAY
        else:
            self.p.jump_type = CO_SEISMIC_JUMP_DECAY

        # if T is an array, it contains the corresponding decays
        # otherwise, it is a single decay
        if not isinstance(relaxation, np.ndarray):
            relaxation = np.array([relaxation])

        self.param_count += relaxation.shape[0]
        self.nr = relaxation.shape[0]
        self.p.relaxation = relaxation

        self.design = self.eval(t)

        # test if earthquake generates at least 10 days of data to adjust
        if self.design.size:
            if np.count_nonzero(self.design[:, -1]) < 10:
                if self.p.jump_type == CO_SEISMIC_JUMP_DECAY:
                    # was a jump and decay, leave the jump
                    self.p.jump_type = GENERIC_JUMP
                    self.p.params = np.zeros((3, 1))
                    self.p.sigmas = np.zeros((3, 1))
                    self.param_count -= 1
                    # reevaluate the design matrix!
                    self.design = self.eval(t)
                else:
                    self.p.jump_type = NO_EFFECT
                    self.p.params = np.array([])
                    self.p.sigmas = np.array([])
                    self.param_count = 0
        else:
            self.p.jump_type = NO_EFFECT
            self.p.params = np.array([])
            self.p.sigmas = np.array([])
            self.param_count = 0

        self.p.hash += crc32(str(self.param_count) + ' ' + str(self.p.jump_type) + ' ' + str(self.p.relaxation))

    def eval(self, t):

        ht = Jump.eval(self, t)

        # if there is nothing in ht, then there is no expected output, return none
        if not np.any(ht):
            return np.array([])

        # if it was determined that this is just a generic jump, return ht
        if self.p.jump_type == GENERIC_JUMP:
            return ht

        # support more than one decay
        hl = np.zeros((t.shape[0], self.nr))

        for i, T in enumerate(self.p.relaxation):
            hl[t > self.date.fyear, i] = np.log10(1. + (t[t > self.date.fyear] - self.date.fyear) / T)

        # if it's both jump and decay, return ht + hl
        if np.any(hl) and self.p.jump_type == CO_SEISMIC_JUMP_DECAY:
            return np.column_stack((ht, hl))

        # if decay only, return hl
        elif np.any(hl) and self.p.jump_type == CO_SEISMIC_DECAY:
            return hl

    def __str__(self):
        return '(' + str(self.date)+'), ' + str(self.p.jump_type) + ', ' + str(self.p.relaxation) + ', "' + str(self.p.metadata) + '"'

    def __repr__(self):
        return 'pyPPPETM.CoSeisJump(' + str(self) + ')'


class Earthquakes:

    def __init__(self, cnn, NetworkCode, StationCode, solution, t, FitEarthquakes=True):

        self.StationCode = StationCode
        self.NetworkCode = NetworkCode

        # station location
        stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                        % (NetworkCode, StationCode))

        stn = stn.dictresult()[0]

        # load metadata
        lat = float(stn['lat'])
        lon = float(stn['lon'])

        # establish the limit dates. Ignore jumps before 5 years from the earthquake
        sdate = pyDate.Date(fyear=t.min() - 5)
        edate = pyDate.Date(fyear=t.max())

        # get the earthquakes based on Mike's expression
        jumps = cnn.query('SELECT * FROM earthquakes WHERE date BETWEEN \'%s\' AND \'%s\' ORDER BY date'
                          % (sdate.yyyymmdd(), edate.yyyymmdd()))
        jumps = jumps.dictresult()

        # check if data range returned any jumps
        if jumps and FitEarthquakes:
            eq = [[float(jump['lat']), float(jump['lon']), float(jump['mag']),
                   int(jump['date'].year), int(jump['date'].month), int(jump['date'].day),
                   int(jump['date'].hour), int(jump['date'].minute), int(jump['date'].second)] for jump in jumps]

            eq = np.array(list(eq))

            dist = distance(lon, lat, eq[:, 1], eq[:, 0])

            m = -0.8717 * (np.log10(dist) - 2.25) + 0.4901 * (eq[:, 2] - 6.6928)
            # build the earthquake jump table
            # remove event events that happened the same day

            eq_jumps = list(set((float(eqs[2]), pyDate.Date(year=int(eqs[3]), month=int(eqs[4]), day=int(eqs[5]),
                                                            hour=int(eqs[6]), minute=int(eqs[7]), second=int(eqs[8])))
                                for eqs in eq[m > 0, :]))

            eq_jumps.sort(key=lambda x: (x[1], x[0]))

            # open the jumps table
            jp = cnn.query_float('SELECT * FROM etm_params WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                                 'AND soln = \'%s\' AND jump_type <> 0 AND object = \'jump\''
                                 % (NetworkCode, StationCode, solution), as_dict=True)

            # start by collapsing all earthquakes for the same day.
            # Do not allow more than one earthquake on the same day
            f_jumps = []
            next_date = None

            for mag, date in eq_jumps:

                # jumps are analyzed in windows that are EQ_MIN_DAYS long
                # a date should not be analyzed is it's < next_date
                if next_date is not None:
                    if date < next_date:
                        continue

                # obtain jumps in a EQ_MIN_DAYS window
                jumps = [(m, d) for m, d in eq_jumps if date <= d < date + EQ_MIN_DAYS]

                if len(jumps) > 1:
                    # if more than one jump, get the max magnitude
                    mmag = max([m for m, _ in jumps])

                    # only keep the earthquake with the largest magnitude
                    for m, d in jumps:

                        table = [j['action'] for j in jp if j['Year'] == d.year and j['DOY'] == d.doy]

                        # get a different relaxation for this date
                        relax = [j['relaxation'] for j in jp if j['Year'] == d.year and j['DOY'] == d.doy]

                        if relax:
                            if relax[0] is not None:
                                relaxation = np.array(relax[0])
                            else:
                                relaxation = DEFAULT_RELAXATION
                        else:
                            relaxation = DEFAULT_RELAXATION

                        # if present in jump table, with either + of -, don't use default decay
                        if m == mmag and '-' not in table:
                            f_jumps += [CoSeisJump(NetworkCode, StationCode, solution, t, d, relaxation,
                                                   'mag=%.1f' % m)]
                            # once the jump was added, exit for loop
                            break
                        else:
                            # add only if in jump list with a '+'
                            if '+' in table:
                                f_jumps += [CoSeisJump(NetworkCode, StationCode, solution, t, d,
                                                       relaxation, 'mag=%.1f' % m)]
                                # once the jump was added, exit for loop
                                break
                            else:
                                f_jumps += [CoSeisJump(NetworkCode, StationCode, solution, t, d,
                                                       relaxation, 'mag=%.1f' % m, NO_EFFECT)]
                else:
                    # add, unless marked in table with '-'
                    table = [j['action'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]
                    # get a different relaxation for this date
                    relax = [j['relaxation'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]

                    if relax:
                        if relax[0] is not None:
                            relaxation = np.array(relax[0])
                        else:
                            relaxation = DEFAULT_RELAXATION
                    else:
                        relaxation = DEFAULT_RELAXATION

                    if '-' not in table:
                        f_jumps += [CoSeisJump(NetworkCode, StationCode, solution, t, date,
                                               relaxation, 'mag=%.1f' % mag)]
                    else:
                        # add it with NO_EFFECT for display purposes
                        f_jumps += [CoSeisJump(NetworkCode, StationCode, solution, t, date,
                                               relaxation, 'mag=%.1f' % mag, NO_EFFECT)]

                next_date = date + EQ_MIN_DAYS

            # final jump table
            self.table = f_jumps
        else:
            self.table = []


class GenericJumps(object):

    def __init__(self, cnn, NetworkCode, StationCode, solution, t, FitGenericJumps=True):

        self.solution = solution
        self.table = []

        if t.size >= 2:
            # analyze if it is possible to add the jumps (based on the available data)
            wt = np.sort(np.unique(t - np.fix(t)))
            # analyze the gaps in the data
            dt = np.diff(wt)
            # max dt (internal)
            dtmax = np.max(dt)
            # dt wrapped around
            dt_interyr = 1 - wt[-1] + wt[0]

            if dt_interyr > dtmax:
                dtmax = dt_interyr

            if dtmax <= 0.2465 and FitGenericJumps:
                # put jumps in
                self.add_metadata_jumps = True
            else:
                # no jumps
                self.add_metadata_jumps = False
        else:
            self.add_metadata_jumps = False

        # open the jumps table
        jp = cnn.query('SELECT * FROM etm_params WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                       'AND soln = \'%s\' AND jump_type = 0 AND object = \'jump\''
                       % (NetworkCode, StationCode, solution))

        jp = jp.dictresult()

        # get station information
        self.stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        for stninfo in self.stninfo.records[1:]:

            date = stninfo['DateStart']

            table = [j['action'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]

            # add to list only if:
            # 1) add_meta = True AND there is no '-' OR
            # 2) add_meta = False AND there is a '+'

            if (not self.add_metadata_jumps and '+' in table) or (self.add_metadata_jumps and '-' not in table):
                self.table.append(Jump(NetworkCode, StationCode, solution, t, date,
                                       'Ant-Rec: %s-%s' % (stninfo['AntennaCode'], stninfo['ReceiverCode'])))

        # frame changes if ppp
        if solution == 'ppp':
            frames = cnn.query(
                'SELECT distinct on ("ReferenceFrame") "ReferenceFrame", "Year", "DOY" from ppp_soln WHERE '
                '"NetworkCode" = \'%s\' AND "StationCode" = \'%s\' order by "ReferenceFrame", "Year", "DOY"' %
                (NetworkCode, StationCode))

            frames = frames.dictresult()

            if len(frames) > 1:
                # more than one frame, add a jump
                frames.sort(key=lambda k: k['Year'])

                for frame in frames[1:]:
                    date = pyDate.Date(Year=frame['Year'], doy=frame['DOY'])

                    table = [j['action'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]

                    if '-' not in table:
                        self.table.append(Jump(NetworkCode, StationCode, solution, t, date,
                                               'Frame Change: %s' % frame['ReferenceFrame']))

        # now check the jump table to add specific jumps
        jp = cnn.query('SELECT * FROM etm_params WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                       'AND soln = \'%s\' AND jump_type = 0 AND object = \'jump\' '
                       'AND action = \'+\'' % (NetworkCode, StationCode, solution))

        jp = jp.dictresult()

        table = [j.date for j in self.table]

        for j in jp:
            date = pyDate.Date(Year=j['Year'], doy=j['DOY'])

            if date not in table:
                self.table.append(Jump(NetworkCode, StationCode, solution, t, date, 'mechanic-jump'))


class Periodic(EtmFunction):
    """"class to determine the periodic terms to be included in the ETM"""

    def __init__(self, NetworkCode, StationCode, solution, t, FitPeriodic=True):

        super(Periodic, self).__init__(NetworkCode=NetworkCode, StationCode=StationCode, solution=solution)

        # in the future, can load parameters from the db
        self.p.frequencies = DEFAULT_FREQUENCIES
        self.p.object = 'periodic'

        if t.size > 1 and FitPeriodic:
            # wrap around the solutions
            wt = np.sort(np.unique(t - np.fix(t)))

            # analyze the gaps in the data
            dt = np.diff(wt)

            # max dt (internal)
            dtmax = np.max(dt)

            # dt wrapped around
            dt_interyr = 1 - wt[-1] + wt[0]

            if dt_interyr > dtmax:
                dtmax = dt_interyr

            # save the value of the max wrapped delta time
            self.dt_max = dtmax

            # get the 50 % of Nyquist for each component (and convert to average fyear)
            self.nyquist = ((1 / self.p.frequencies) / 2.) * 0.5 * 1 / 365.25

            # frequency count
            self.frequency_count = int(np.sum(self.dt_max <= self.nyquist))

            # redefine the frequencies vector to accommodate only the frequencies that can be fit
            self.p.frequencies = self.p.frequencies[self.dt_max <= self.nyquist]

        else:
            # no periodic terms
            self.frequency_count = 0
            self.dt_max = 1  # one year of delta t

        self.design = self.get_design_ts(t)
        self.param_count = self.frequency_count * 2
        # declare the location of the answer (to be filled by Design object)
        self.column_index = np.array([])

        self.format_str = 'Periodic amp (' + \
                          ', '.join(['%.1f yr' % i for i in (1 / (self.p.frequencies * 365.25)).tolist()]) + \
                          ') N: %s E: %s U: %s [mm]'

        self.p.hash = crc32(str(self.p.frequencies))

    def get_design_ts(self, ts):
        # if dtmax < 3 months (90 days = 0.1232), then we can fit the annual
        # if dtmax < 1.5 months (45 days = 0.24657), then we can fit the semi-annual too

        if self.frequency_count > 0:
            f = self.p.frequencies
            f = np.tile(f, (ts.shape[0], 1))

            As = np.array(sin(2 * pi * f * 365.25 * np.tile(ts[:, np.newaxis], (1, f.shape[1]))))
            Ac = np.array(cos(2 * pi * f * 365.25 * np.tile(ts[:, np.newaxis], (1, f.shape[1]))))

            A = np.column_stack((As, Ac))
        else:
            # no periodic terms
            A = np.array([])

        return A

    def print_parameters(self):

        n = np.array([])
        e = np.array([])
        u = np.array([])

        for p in np.arange(self.param_count):
            psc = self.p.params[:, p]

            sn = psc[0]
            se = psc[1]
            su = psc[2]

            n = np.append(n, sn)
            e = np.append(e, se)
            u = np.append(u, su)

        n = n.reshape((2, self.param_count / 2))
        e = e.reshape((2, self.param_count / 2))
        u = u.reshape((2, self.param_count / 2))

        # calculate the amplitude of the components
        an = np.sqrt(np.square(n[0, :]) + np.square(n[1, :]))
        ae = np.sqrt(np.square(e[0, :]) + np.square(e[1, :]))
        au = np.sqrt(np.square(u[0, :]) + np.square(u[1, :]))

        return self.format_str % (np.array_str(an * 1000.0, precision=1),
                                  np.array_str(ae * 1000.0, precision=1),
                                  np.array_str(au * 1000.0, precision=1))


class Polynomial(EtmFunction):
    """"class to build the linear portion of the design matrix"""

    def __init__(self, NetworkCode, StationCode, solution, t, t_ref=0):

        super(Polynomial, self).__init__(NetworkCode=NetworkCode, StationCode=StationCode, solution=solution)

        # t ref (just the beginning of t vector)
        if t_ref == 0:
            t_ref = np.min(t)

        self.p.object = 'polynomial'
        self.p.t_ref = t_ref

        # in the future, can load parameters from the db
        self.terms = DEFAULT_POL_TERMS

        if self.terms == 1:
            self.format_str = 'Ref Position (' + '%.3f' % t_ref + ') X: {:.3f} Y: {:.3f} Z: {:.3f} [m]'

        elif self.terms == 2:
            self.format_str = 'Ref Position (' + '%.3f' % t_ref + ') X: {:.3f} Y: {:.3f} Z: {:.3f} [m]\n' \
                              'Velocity N: {:.2f} E: {:.2f} U: {:.2f} [mm/yr]'

        elif self.terms == 3:
            self.format_str = 'Ref Position (' + '%.3f' % t_ref + ') X: {:.3f} Y: {:.3f} Z: {:.3f} [m]\n' \
                              'Velocity N: {:.3f} E: {:.3f} U: {:.3f} [mm/yr]\n' \
                              'Acceleration N: {:.2f} E: {:.2f} U: {:.2f} [mm/yr^2]'

        self.design = self.get_design_ts(t)

        # always first in the list of A, index columns are fixed
        self.column_index = np.arange(self.terms)
        # param count is the same as terms
        self.param_count = self.terms
        # save the hash of the object
        self.p.hash = crc32(str(self.terms))

    def load_parameters(self, params, sigmas, t_ref):

        super(Polynomial, self).load_parameters(params=params, sigmas=sigmas)

        self.p.t_ref = t_ref

    def print_parameters(self, ref_xyz, lat, lon):

        params = np.zeros((3, 1))

        for p in np.arange(self.terms):
            if p == 0:
                params[0], params[1], params[2] = lg2ct(self.p.params[0, 0],
                                                        self.p.params[1, 0],
                                                        self.p.params[2, 0], lat, lon)
                params += ref_xyz

            elif p > 0:
                n = self.p.params[0, p]
                e = self.p.params[1, p]
                u = self.p.params[2, p]

                params = np.append(params, (n*1000, e*1000, u*1000))

        return self.format_str.format(*params.tolist())

    def get_design_ts(self, ts):

        A = np.zeros((ts.size, self.terms))

        for p in np.arange(self.terms):
            A[:, p] = np.power(ts - self.p.t_ref, p)

        return A


class Design(np.ndarray):

    def __new__(subtype, Linear, Jumps, Periodic, dtype=float, buffer=None, offset=0, strides=None, order=None):
        # Create the ndarray instance of our type, given the usual
        # ndarray input arguments.  This will call the standard
        # ndarray constructor, but return an object of our type.
        # It also triggers a call to InfoArray.__array_finalize__

        shape = (Linear.design.shape[0], Linear.param_count + Jumps.param_count + Periodic.param_count)
        A = super(Design, subtype).__new__(subtype, shape, dtype, buffer, offset, strides, order)

        A[:, Linear.column_index] = Linear.design

        # determine the column_index for all objects
        col_index = Linear.param_count

        for jump in Jumps.table:
            # save the column index
            jump.column_index = np.arange(col_index, col_index + jump.param_count)
            # assign the portion of the design matrix
            A[:, jump.column_index] = jump.design
            # increment the col_index
            col_index += jump.param_count

        Periodic.column_index = np.arange(col_index, col_index + Periodic.param_count)

        A[:, Periodic.column_index] = Periodic.design

        # save the object list
        A.objects = (Linear, Jumps, Periodic)

        # save the number of total parameters
        A.linear_params = Linear.param_count
        A.jump_params = Jumps.param_count
        A.periodic_params = Periodic.param_count

        A.params = Linear.param_count + Jumps.param_count + Periodic.param_count

        # save the constrains matrix
        A.constrains = Jumps.constrains

        # Finally, we must return the newly created object:
        return A

    def __call__(self, ts=None, constrains=False):

        if ts is None:
            if constrains:
                if self.constrains.size:
                    A = self.copy()
                    # resize matrix (use A.resize so that it fills with zeros)
                    A.resize((self.shape[0] + self.constrains.shape[0], self.shape[1]), refcheck=False)
                    # apply constrains
                    A[-self.constrains.shape[0]:, self.jump_params] = self.constrains
                    return A

                else:
                    return self

            else:
                return self

        else:

            A = np.array([])

            for obj in self.objects:
                tA = obj.get_design_ts(ts)
                if A.size:
                    A = np.column_stack((A, tA)) if tA.size else A
                else:
                    A = tA

            return A

    def get_l(self, L, constrains=False):

        if constrains:
            if self.constrains.size:
                tL = L.copy()
                tL.resize((L.shape[0] + self.constrains.shape[0]), refcheck=False)
                return tL

            else:
                return L

        else:
            return L

    def get_p(self, constrains=False):
        # return a weight matrix full of ones with or without the extra elements for the constrains
        return np.ones((self.shape[0])) if not constrains else \
            np.ones((self.shape[0] + self.constrains.shape[0]))

    def remove_constrains(self, v):
        # remove the constrains to whatever vector is passed
        if self.constrains.size:
            return v[0:-self.constrains.shape[0]]
        else:
            return v


class ETM:

    def __init__(self, cnn, soln, no_model=False, FitEarthquakes=True, FitGenericJumps=True, FitPeriodic=True):

        # to display more verbose warnings
        # warnings.showwarning = self.warn_with_traceback

        self.C = np.array([])
        self.S = np.array([])
        self.F = np.array([])
        self.R = np.array([])
        self.P = np.array([])
        self.factor = np.array([])
        self.covar = np.zeros((3, 3))
        self.A = None
        self.soln = soln
        self.no_model = no_model
        self.FitEarthquakes = FitEarthquakes
        self.FitGenericJumps = FitGenericJumps
        self.FitPeriodic = FitPeriodic

        self.NetworkCode = soln.NetworkCode
        self.StationCode = soln.StationCode

        # save the function objects
        self.Linear = Polynomial(soln.NetworkCode, soln.StationCode, self.soln.type, soln.t)
        self.Periodic = Periodic(soln.NetworkCode, soln.StationCode, self.soln.type, soln.t, FitPeriodic)
        self.Jumps = JumpTable(cnn, soln.NetworkCode, soln.StationCode, soln.type, soln.t,
                               FitEarthquakes, FitGenericJumps)
        # calculate the hash value for this station
        # now hash also includes the timestamp of the last time pyETM was modified.
        self.hash = soln.hash + crc32(VERSION)

        # anything less than four is not worth it
        if soln.solutions > 4 and not no_model:

            # to obtain the parameters
            self.A = Design(self.Linear, self.Jumps, self.Periodic)

            # check if problem can be solved!
            if self.A.shape[1] >= soln.solutions:
                self.A = None
                return

            self.As = self.A(soln.ts)

    def run_adjustment(self, cnn, l, plotit=False):

        c = []
        f = []
        s = []
        r = []
        p = []
        factor = []

        if self.A is not None:
            # try to load the last ETM solution from the database

            etm_objects = cnn.query_float('SELECT * FROM etmsv2 WHERE "NetworkCode" = \'%s\' '
                                          'AND "StationCode" = \'%s\' AND soln = \'%s\''
                                          % (self.NetworkCode, self.StationCode, self.soln.type), as_dict=True)

            db_hash_sum = sum([obj['hash'] for obj in etm_objects])
            ob_hash_sum = sum([o.p.hash for o in self.Jumps.table + [self.Periodic] + [self.Linear]]) + self.hash
            cn_object_sum = len(self.Jumps.table) + 2

            # -1 to account for the var_factor entry
            if len(etm_objects) - 1 == cn_object_sum and db_hash_sum == ob_hash_sum:
                # load the parameters from th db
                self.load_parameters(etm_objects, l)
            else:
                # purge table and recompute
                cnn.query('DELETE FROM etmsv2 WHERE "NetworkCode" = \'%s\' AND '
                          '"StationCode" = \'%s\' AND soln = \'%s\''
                          % (self.NetworkCode, self.StationCode, self.soln.type))

                # use the default parameters from the objects
                t_ref = self.Linear.p.t_ref

                for i in range(3):

                    x, sigma, index, residuals, fact, w = self.adjust_lsq(self.A, l[i])

                    c.append(x)
                    s.append(sigma)
                    f.append(index)
                    r.append(residuals)
                    factor.append(fact)
                    p.append(w)

                self.C = np.array(c)
                self.S = np.array(s)
                self.F = np.array(f)
                self.R = np.array(r)
                self.factor = np.array(factor)
                self.P = np.array(p)

                # load_parameters to the objects
                self.Linear.load_parameters(self.C, self.S, t_ref)
                self.Jumps.load_parameters(self.C, self.S)
                self.Periodic.load_parameters(params=self.C, sigmas=self.S)

                # save the parameters in each object to the db
                self.save_parameters(cnn)

            # load the covariances using the correlations
            self.process_covariance()

            if plotit:
                self.plot()

    def process_covariance(self):

        cov = np.zeros((3, 1))

        # save the covariance between N-E, E-U, N-U
        f = self.F[0] * self.F[1] * self.F[2]

        # load the covariances using the correlations
        cov[0] = np.corrcoef(self.R[0][f], self.R[1][f])[0, 1] * self.factor[0] * self.factor[1]
        cov[1] = np.corrcoef(self.R[1][f], self.R[2][f])[0, 1] * self.factor[1] * self.factor[2]
        cov[2] = np.corrcoef(self.R[0][f], self.R[2][f])[0, 1] * self.factor[0] * self.factor[2]

        # build a variance-covariance matrix
        self.covar = np.diag(np.square(self.factor))

        self.covar[0, 1] = cov[0]
        self.covar[1, 0] = cov[0]
        self.covar[2, 1] = cov[1]
        self.covar[1, 2] = cov[1]
        self.covar[0, 2] = cov[2]
        self.covar[2, 0] = cov[2]

        if not self.isPD(self.covar):
            self.covar = self.nearestPD(self.covar)

    def save_parameters(self, cnn):

        # insert linear parameters
        cnn.insert('etmsv2', row=to_postgres(self.Linear.p.toDict()))

        # insert jumps
        for jump in self.Jumps.table:
            cnn.insert('etmsv2', row=to_postgres(jump.p.toDict()))

        # insert periodic params
        cnn.insert('etmsv2', row=to_postgres(self.Periodic.p.toDict()))

        cnn.query('INSERT INTO etmsv2 ("NetworkCode", "StationCode", soln, object, params, hash) VALUES '
                  '(\'%s\', \'%s\', \'ppp\', \'var_factor\', \'%s\', %i)'
                  % (self.NetworkCode, self.StationCode, to_postgres(self.factor), self.hash))

    def plot(self, pngfile=None, t_win=None, residuals=False, plot_missing=True, ecef=False):

        import matplotlib.pyplot as plt

        L = self.l * 1000

        # definitions
        m = []
        if ecef:
            labels = ('X [mm]', 'Y [mm]', 'Z [mm]')
        else:
            labels = ('North [mm]', 'East [mm]', 'Up [mm]')

        # get filtered observations
        if self.A is not None:
            filt = self.F[0] * self.F[1] * self.F[2]

            for i in range(3):
                m.append((np.dot(self.As, self.C[i])) * 1000)

        else:
            filt = np.ones(self.soln.x.shape[0], dtype=bool)

        # rotate to NEU
        if ecef:
            lneu = self.rotate_2xyz(L)
        else:
            lneu = L

        # determine the window of the plot, if requested
        if t_win is not None:
            if type(t_win) is tuple:
                # data range, with possibly a final value
                if len(t_win) == 1:
                    t_win = (t_win[0], self.soln.t.max())
            else:
                # approximate a day in fyear
                t_win = (self.soln.t.max() - t_win/365.25, self.soln.t.max())

        # new behaviour: plots the time series even if there is no ETM fit

        if self.A is not None:

            # create the axis
            f, axis = plt.subplots(nrows=3, ncols=2, sharex=True, figsize=(15, 10))  # type: plt.subplots

            # rotate modeled ts
            if not ecef:
                mneu = m
                rneu = self.R
                fneu = self.factor * 1000
            else:
                mneu = self.rotate_2xyz(m)
                # rotate residuals
                rneu = self.rotate_2xyz(self.R)
                fneu = np.sqrt(np.diag(self.rotate_sig_cov(covar=self.covar))) * 1000

            # ################# FILTERED PLOT #################

            f.suptitle('Station: %s.%s lat: %.5f lon: %.5f\n'
                       '%s completion: %.2f%%\n%s\n%s\n'
                       'NEU wrms [mm]: %5.2f %5.2f %5.2f' %
                       (self.NetworkCode, self.StationCode, self.soln.lat, self.soln.lon, self.soln.type.upper(),
                        self.soln.completion,
                        self.Linear.print_parameters(np.array([self.soln.auto_x, self.soln.auto_y, self.soln.auto_z]),
                                                     self.soln.lat, self.soln.lon),
                        self.Periodic.print_parameters(),
                        fneu[0], fneu[1], fneu[2]), fontsize=9, family='monospace')

            table_n, table_e, table_u = self.Jumps.print_parameters()
            tables = (table_n, table_e, table_u)

            for i, ax in enumerate((axis[0][0], axis[1][0], axis[2][0])):

                # plot filtered time series
                if not residuals:
                    ax.plot(self.soln.t[filt], lneu[i][filt], 'ob', markersize=2)
                    ax.plot(self.soln.ts, mneu[i], 'r')
                    # error bars
                    ax.plot(self.soln.ts, mneu[i] - fneu[i] * LIMIT, 'b', alpha=0.1)
                    ax.plot(self.soln.ts, mneu[i] + fneu[i] * LIMIT, 'b', alpha=0.1)
                    ax.fill_between(self.soln.ts, mneu[i] - fneu[i] * LIMIT, mneu[i] + fneu[i] * LIMIT,
                                    antialiased=True, alpha=0.2)
                else:
                    ax.plot(self.soln.t[filt], rneu[i][filt]*1000, 'ob', markersize=2)
                    # error bars
                    ax.plot(self.soln.ts, - np.repeat(fneu[i], self.soln.ts.shape[0]) * LIMIT, 'b', alpha=0.1)
                    ax.plot(self.soln.ts,   np.repeat(fneu[i], self.soln.ts.shape[0]) * LIMIT, 'b', alpha=0.1)
                    ax.fill_between(self.soln.ts, -fneu[i] * LIMIT, fneu[i] * LIMIT, antialiased=True, alpha=0.2)

                ax.grid(True)

                # labels
                ax.set_ylabel(labels[i])
                p = ax.get_position()
                f.text(0.005, p.y0, tables[i], fontsize=8, family='monospace')

                # window data
                self.set_lims(t_win, plt, ax)

                # plot jumps
                self.plot_jumps(ax)

            # ################# OUTLIERS PLOT #################

            for i, ax in enumerate((axis[0][1],axis[1][1], axis[2][1])):
                ax.plot(self.soln.t, lneu[i], 'oc', markersize=2)
                ax.plot(self.soln.t[filt], lneu[i][filt], 'ob', markersize=2)
                ax.plot(self.soln.ts, mneu[i], 'r')
                # error bars
                ax.plot(self.soln.ts, mneu[i] - fneu[i] * LIMIT, 'b', alpha=0.1)
                ax.plot(self.soln.ts, mneu[i] + fneu[i] * LIMIT, 'b', alpha=0.1)
                ax.fill_between(self.soln.ts, mneu[i] - fneu[i]*LIMIT, mneu[i] + fneu[i]*LIMIT,
                                antialiased=True, alpha=0.2)

                self.set_lims(t_win, plt, ax)

                ax.set_ylabel(labels[i])

                ax.grid(True)

                if plot_missing:
                    self.plot_missing_soln(ax)

            f.subplots_adjust(left=0.16)

        else:

            f, axis = plt.subplots(nrows=3, ncols=1, sharex=True, figsize=(15, 10))  # type: plt.subplots

            f.suptitle('Station: %s.%s lat: %.5f lon: %.5f'
                       % (self.NetworkCode, self.StationCode, self.soln.lat, self.soln.lon) +
                       '\nNot enough solutions to fit an ETM.', fontsize=9, family='monospace')

            for i, ax in enumerate((axis[0], axis[1], axis[2])):
                ax.plot(self.soln.t, lneu[i], 'ob', markersize=2)

                ax.set_ylabel(labels[i])

                ax.grid(True)

                self.set_lims(t_win, plt, ax)

                self.plot_jumps(ax)

                if plot_missing:
                    self.plot_missing_soln(ax)

        if not pngfile:
            self.f = f
            self.picking = False
            self.plt = plt
            axprev = plt.axes([0.85, 0.01, 0.08, 0.055])
            bcut = Button(axprev, 'Add jump', color='red', hovercolor='green')
            bcut.on_clicked(self.enable_picking)
            plt.show()
            plt.close()
        else:
            plt.savefig(pngfile)
            plt.close()

    def onpick(self, event):

        import dbConnection

        self.f.canvas.mpl_disconnect(self.cid)
        self.picking = False
        print 'Epoch: %s' % pyDate.Date(fyear=event.xdata).yyyyddd()
        jtype = int(input(' -- Enter type of jump (0 = mechanic; 1 = geophysical): '))
        if jtype == 1:
            relx = input(' -- Enter relaxation (e.g. 0.5, 0.5,0.01): ')
        operation = str(raw_input(' -- Enter operation (+, -): '))
        print ' >> Jump inserted'

        # now insert the jump into the db
        cnn = dbConnection.Cnn('gnss_data.cfg')

        self.plt.close()

        # reinitialize ETM

        # wait for 'keep' or 'undo' command

    def enable_picking(self, event):
        if not self.picking:
            print 'Entering picking mode'
            self.picking = True
            self.cid = self.f.canvas.mpl_connect('button_press_event', self.onpick)
        else:
            print 'Disabling picking mode'
            self.picking = False
            self.f.canvas.mpl_disconnect(self.cid)

    def plot_hist(self):

        import matplotlib.pyplot as plt
        import matplotlib.mlab as mlab
        from scipy.stats import norm

        L = self.l * 1000

        if self.A is not None:

            residuals = np.sqrt(np.square(L[0]) + np.square(L[1]) + np.square(L[2])) - \
                        np.sqrt(np.square(np.dot(self.A, self.C[0])) + np.square(np.dot(self.A, self.C[1])) +
                                np.square(np.dot(self.A, self.C[2])))

            (mu, sigma) = norm.fit(residuals)

            n, bins, patches = plt.hist(residuals, 200, normed=1, alpha=0.75, facecolor='blue')

            y = mlab.normpdf(bins, mu, sigma)
            plt.plot(bins, y, 'r--', linewidth=2)
            plt.title(r'$\mathrm{Histogram\ of\ residuals (mm):}\ \mu=%.3f,\ \sigma=%.3f$' % (mu*1000, sigma*1000))
            plt.grid(True)

            plt.show()

    @staticmethod
    def autoscale_y( ax, margin=0.1):
        """This function rescales the y-axis based on the data that is visible given the current xlim of the axis.
        ax -- a matplotlib axes object
        margin -- the fraction of the total height of the y-data to pad the upper and lower ylims"""

        def get_bottom_top(line):
            xd = line.get_xdata()
            yd = line.get_ydata()
            lo, hi = ax.get_xlim()
            y_displayed = yd[((xd > lo) & (xd < hi))]
            h = np.max(y_displayed) - np.min(y_displayed)
            bot = np.min(y_displayed) - margin * h
            top = np.max(y_displayed) + margin * h
            return bot, top

        lines = ax.get_lines()
        bot, top = np.inf, -np.inf

        for line in lines:
            new_bot, new_top = get_bottom_top(line)
            if new_bot < bot:
                bot = new_bot
            if new_top > top:
                top = new_top
        if bot == top:
            ax.autoscale(enable=True, axis='y', tight=False)
            ax.autoscale(enable=False, axis='y', tight=False)
        else:
            ax.set_ylim(bot, top)

    def set_lims(self, t_win, plt, ax):

        if t_win is None:
            # turn on to adjust the limits, then turn off to plot jumps
            ax.autoscale(enable=True, axis='x', tight=False)
            ax.autoscale(enable=False, axis='x', tight=False)
            ax.autoscale(enable=True, axis='y', tight=False)
            ax.autoscale(enable=False, axis='y', tight=False)
        else:
            if t_win[0] == t_win[1]:
                t_win[0] = t_win[0] - 1./365.25
                t_win[1] = t_win[1] + 1./365.25

            plt.xlim(t_win)
            self.autoscale_y(ax)

    def plot_missing_soln(self, ax):

        # plot missing solutions
        for missing in self.soln.ts_ns:
            ax.plot((missing, missing), ax.get_ylim(), color=(1, 0, 1, 0.2), linewidth=1)

        # plot the position of the outliers
        for blunder in self.soln.ts_blu:
            ax.quiver((blunder, blunder), ax.get_ylim(), (0, 0), (-0.01, 0.01), scale_units='height',
                      units='height', pivot='tip', width=0.008, edgecolors='r')

    def plot_jumps(self, ax):

        for jump in self.Jumps.table:
            if jump.p.jump_type == GENERIC_JUMP and 'Frame Change' not in jump.p.metadata:
                ax.plot((jump.date.fyear, jump.date.fyear), ax.get_ylim(), 'b:')

            elif jump.p.jump_type == GENERIC_JUMP and 'Frame Change' in jump.p.metadata:
                ax.plot((jump.date.fyear, jump.date.fyear), ax.get_ylim(), ':', color='tab:green')

            elif jump.p.jump_type == CO_SEISMIC_JUMP_DECAY:
                ax.plot((jump.date.fyear, jump.date.fyear), ax.get_ylim(), 'r:')

            elif jump.p.jump_type == NO_EFFECT:
                ax.plot((jump.date.fyear, jump.date.fyear), ax.get_ylim(), ':', color='tab:gray')

    def todictionary(self, time_series=False):
        # convert the ETM adjustment into a dictionary
        # optionally, output the whole time series as well

        L = self.l

        # start with the parameters
        etm = dict()
        etm['Network'] = self.NetworkCode
        etm['Station'] = self.StationCode
        etm['lat'] = self.soln.lat[0]
        etm['lon'] = self.soln.lon[0]
        etm['ref_x'] = self.soln.auto_x[0]
        etm['ref_y'] = self.soln.auto_y[0]
        etm['ref_z'] = self.soln.auto_z[0]
        etm['Jumps'] = [to_list(jump.p.toDict()) for jump in self.Jumps.table]

        if self.A is not None:

            etm['Polynomial'] = to_list(self.Linear.p.toDict())

            etm['Periodic'] = to_list(self.Periodic.p.toDict())

            etm['wrms'] = {'n': self.factor[0], 'e': self.factor[1], 'u': self.factor[2]}

            etm['xyz_covariance'] = self.rotate_sig_cov(covar=self.covar).tolist()

            etm['neu_covariance'] = self.covar.tolist()

        if time_series:
            ts = dict()
            ts['t'] = np.array([self.soln.t.tolist(), self.soln.mjd.tolist()]).transpose().tolist()
            ts['mjd'] = self.soln.mjd.tolist()
            ts['x'] = self.soln.x.tolist()
            ts['y'] = self.soln.y.tolist()
            ts['z'] = self.soln.z.tolist()
            ts['n'] = L[0].tolist()
            ts['e'] = L[1].tolist()
            ts['u'] = L[2].tolist()
            ts['weights'] = self.P.transpose().tolist()

            if self.A is not None:
                ts['filter'] = np.logical_and(np.logical_and(self.F[0], self.F[1]), self.F[2]).tolist()
            else:
                ts['filter'] = []

            etm['time_series'] = ts

        return etm

    def get_xyz_s(self, year, doy, jmp=None, sigma_h=SIGMA_FLOOR_H, sigma_v=SIGMA_FLOOR_V):
        # this function find the requested epochs and returns an X Y Z and sigmas
        # jmp = 'pre' returns the coordinate immediately before a jump
        # jmp = 'post' returns the coordinate immediately after a jump
        # jmp = None returns either the coordinate before or after, depending on the time of the jump.

        # find this epoch in the t vector
        date = pyDate.Date(year=year, doy=doy)
        window = None

        for jump in self.Jumps.table:
            if jump.date == date and jump.p.jump_type in (GENERIC_JUMP, CO_SEISMIC_JUMP_DECAY):
                if np.sqrt(np.sum(np.square(jump.p.params[:, 0]))) > 0.02:
                    window = jump.date
                    # if no pre or post specified, then determine using the time of the jump
                    if jmp is None:
                        if (jump.date.datetime().hour + jump.date.datetime().minute / 60.0) < 12:
                            jmp = 'post'
                        else:
                            jmp = 'pre'
                    # use the previous or next date to get the APR
                    # if jmp == 'pre':
                    #    date -= 1
                    # else:
                    #    date += 1

        index = np.where(self.soln.mjd == date.mjd)
        index = index[0]

        neu = np.zeros((3, 1))

        L = self.L
        ref_pos = np.array([self.soln.auto_x, self.soln.auto_y, self.soln.auto_z])

        if index.size and self.A is not None:
            # found a valid epoch in the t vector
            # now see if this epoch was filtered
            if np.all(self.F[:, index]):
                # the coordinate is good
                xyz = L[:, index]
                sig = self.R[:, index]
                source = 'PPP with ETM solution: good'

            else:
                # the coordinate is marked as bad
                # get the requested epoch from the ETM
                idt = np.argmin(np.abs(self.soln.ts - date.fyear))

                for i in range(3):
                    neu[i] = np.dot(self.As[idt, :], self.C[i])

                xyz = self.rotate_2xyz(neu) + ref_pos
                # Use the deviation from the ETM multiplied by 2.5 to estimate the error
                sig = 2.5 * self.R[:, index]
                source = 'PPP with ETM solution: filtered'

        elif not index.size and self.A is not None:

            # the coordinate doesn't exist, get it from the ETM
            idt = np.argmin(np.abs(self.soln.ts - date.fyear))
            source = 'No PPP solution: ETM'

            for i in range(3):
                neu[i] = np.dot(self.As[idt, :], self.C[i])

            xyz = self.rotate_2xyz(neu) + ref_pos
            # since there is no way to estimate the error,
            # use the nominal sigma multiplied by 2.5
            sig = 2.5 * self.factor[:, np.newaxis]

        elif index.size and self.A is None:

            # no ETM (too few points), but we have a solution for the requested day
            xyz = L[:, index]
            # set the uncertainties in NEU by hand
            sig = np.array([[9.99], [9.99], [9.99]])
            source = 'PPP solution, no ETM'

        else:
            # no ETM (too few points) and no solution for this day, get average
            source = 'No PPP solution, no ETM: mean coordinate'
            xyz = np.mean(L, axis=1)[:, np.newaxis]
            # set the uncertainties in NEU by hand
            sig = np.array([[9.99], [9.99], [9.99]])

        if self.A is not None:
            # get the velocity of the site
            if np.sqrt(np.square(self.Linear.p.params[0, 1]) +
                       np.square(self.Linear.p.params[1, 1]) +
                       np.square(self.Linear.p.params[2, 1])) > 0.2:
                # fast moving station! bump up the sigma floor
                sigma_h = 99.9
                sigma_v = 99.9
                source += '. fast moving station, bumping up sigmas'

        # apply floor sigmas
        sig = np.sqrt(np.square(sig) + np.square(np.array([[sigma_h], [sigma_h], [sigma_v]])))

        return xyz, sig, window, source

    def rotate_2neu(self, ecef):

        return np.array(ct2lg(ecef[0], ecef[1], ecef[2], self.soln.lat, self.soln.lon))

    def rotate_2xyz(self, neu):

        return np.array(lg2ct(neu[0], neu[1], neu[2], self.soln.lat, self.soln.lon))

    def rotate_sig_cov(self, sigmas=None, covar=None):

        if sigmas is None and covar is None:
            raise pyETMException('Error in rotate_sig_cov: must provide either sigmas or covariance matrix')

        R = rotlg2ct(self.soln.lat, self.soln.lon)

        if sigmas is not None:
            # build a covariance matrix based on sigmas
            sd = np.diagflat(np.square(sigmas))

            sd[0, 1] = self.covar[0, 1]
            sd[1, 0] = self.covar[1, 0]
            sd[2, 1] = self.covar[2, 1]
            sd[1, 2] = self.covar[1, 2]
            sd[0, 2] = self.covar[0, 2]
            sd[2, 0] = self.covar[2, 0]

            # check that resulting matrix is PSD:
            if not self.isPD(sd):
                sd = self.nearestPD(sd)

            sneu = np.dot(np.dot(R[:, :, 0], sd), R[:, :, 0].transpose())

            dneu = np.sqrt(np.diag(sneu))

        else:
            # covariance matrix given, assume it is a covariance matrix
            dneu = np.dot(np.dot(R[:, :, 0], covar), R[:, :, 0].transpose())

        return dneu

    def nearestPD(self, A):
        """Find the nearest positive-definite matrix to input

        A Python/Numpy port of John D'Errico's `nearestSPD` MATLAB code [1], which
        credits [2].

        [1] https://www.mathworks.com/matlabcentral/fileexchange/42885-nearestspd

        [2] N.J. Higham, "Computing a nearest symmetric positive semidefinite
        matrix" (1988): https://doi.org/10.1016/0024-3795(88)90223-6
        """

        B = (A + A.T) / 2
        _, s, V = np.linalg.svd(B)

        H = np.dot(V.T, np.dot(np.diag(s), V))

        A2 = (B + H) / 2

        A3 = (A2 + A2.T) / 2

        if self.isPD(A3):
            return A3

        spacing = np.spacing(np.linalg.norm(A))
        # The above is different from [1]. It appears that MATLAB's `chol` Cholesky
        # decomposition will accept matrixes with exactly 0-eigenvalue, whereas
        # Numpy's will not. So where [1] uses `eps(mineig)` (where `eps` is Matlab
        # for `np.spacing`), we use the above definition. CAVEAT: our `spacing`
        # will be much larger than [1]'s `eps(mineig)`, since `mineig` is usually on
        # the order of 1e-16, and `eps(1e-16)` is on the order of 1e-34, whereas
        # `spacing` will, for Gaussian random matrixes of small dimension, be on
        # othe order of 1e-16. In practice, both ways converge, as the unit test
        # below suggests.
        I = np.eye(A.shape[0])
        k = 1

        while not self.isPD(A3):
            mineig = np.min(np.real(np.linalg.eigvals(A3)))
            A3 += I * (-mineig * k ** 2 + spacing)
            k += 1

        return A3

    @staticmethod
    def isPD(B):
        """Returns true when input is positive-definite, via Cholesky"""
        try:
            _ = np.linalg.cholesky(B)
            return True
        except np.linalg.LinAlgError:
            return False

    def load_parameters(self, params, l):

        factor = 1
        index = []
        residuals = []
        p = []

        for param in params:
            par = np.array(param['params'])
            sig = np.array(param['sigmas'])

            if param['object'] == 'polynomial':
                self.Linear.load_parameters(par, sig, param['t_ref'])

            if param['object'] == 'periodic':
                self.Periodic.load_parameters(params=par, sigmas=sig)

            if param['object'] == 'jump':
                for jump in self.Jumps.table:
                    if jump.p.hash == param['hash']:
                        jump.load_parameters(params=par, sigmas=sig)

            if param['object'] == 'var_factor':
                # already a vector in the db
                factor = par

        x = self.Linear.p.params
        s = self.Linear.p.sigmas

        for jump in self.Jumps.table:
            x = np.append(x, jump.p.params, axis=1)
            s = np.append(s, jump.p.sigmas, axis=1)

        x = np.append(x, self.Periodic.p.params, axis=1)
        s = np.append(s, self.Periodic.p.sigmas, axis=1)

        for i in range(3):

            residuals.append(l[i] - np.dot(self.A(constrains=False), x[i, :]))

            ss = np.abs(np.divide(residuals[i], factor[i]))
            index.append(ss <= LIMIT)

            f = np.ones((l.shape[1],))

            sw = np.power(10, LIMIT - ss[ss > LIMIT])
            sw[sw < np.finfo(np.float).eps] = np.finfo(np.float).eps
            f[ss > LIMIT] = sw

            p.append(np.square(np.divide(f, factor[i])))

        self.C = x
        self.S = s
        self.F = np.array(index)
        self.R = np.array(residuals)
        self.factor = factor
        self.P = np.array(p)

    def adjust_lsq(self, Ai, Li):

        A = Ai(constrains=True)
        L = Ai.get_l(Li, constrains=True)

        cst_pass = False
        iteration = 0
        factor = 1
        So = 1
        dof = (Ai.shape[0] - Ai.shape[1])
        X1 = chi2.ppf(1 - 0.05 / 2, dof)
        X2 = chi2.ppf(0.05 / 2, dof)

        s = np.array([])
        v = np.array([])
        C = np.array([])

        P = Ai.get_p(constrains=True)

        while not cst_pass and iteration <= 10:

            W = np.sqrt(P)

            Aw = np.multiply(W[:, None], A)
            Lw = np.multiply(W, L)

            C = np.linalg.lstsq(Aw, Lw, rcond=-1)[0]

            v = L - np.dot(A, C)

            # unit variance
            So = np.sqrt(np.dot(v, np.multiply(P, v)) / dof)

            x = np.power(So, 2) * dof

            # obtain the overall uncertainty predicted by lsq
            factor = factor * So

            # calculate the normalized sigmas
            s = np.abs(np.divide(v, factor))

            if x < X2 or x > X1:
                # if it falls in here it's because it didn't pass the Chi2 test
                cst_pass = False

                # reweigh by Mike's method of equal weight until 2 sigma
                f = np.ones((v.shape[0], ))
                # f[s > LIMIT] = 1. / (np.power(10, LIMIT - s[s > LIMIT]))
                # do not allow sigmas > 100 m, which is basically not putting
                # the observation in. Otherwise, due to a model problem
                # (missing jump, etc) you end up with very unstable inversions
                # f[f > 500] = 500
                sw = np.power(10, LIMIT - s[s > LIMIT])
                sw[sw < np.finfo(np.float).eps] = np.finfo(np.float).eps
                f[s > LIMIT] = sw

                P = np.square(np.divide(f, factor))
            else:
                cst_pass = True

            iteration += 1

        # make sure there are no values below eps. Otherwise matrix becomes singular
        P[P < np.finfo(np.float).eps] = 1e-6

        # some statistics
        SS = np.linalg.inv(np.dot(A.transpose(), np.multiply(P[:, None], A)))

        sigma = So*np.sqrt(np.diag(SS))

        # mark observations with sigma <= LIMIT
        index = Ai.remove_constrains(s <= LIMIT)

        v = Ai.remove_constrains(v)

        return C, sigma, index, v, factor, P

    @staticmethod
    def chi2inv(chi, df):
        """Return prob(chisq >= chi, with df degrees of
        freedom).

        df must be even.
        """
        assert df & 1 == 0
        # XXX If chi is very large, exp(-m) will underflow to 0.
        m = chi / 2.0
        sum = term = np.exp(-m)
        for i in range(1, df // 2):
            term *= m / i
            sum += term
        # With small chi and large df, accumulated
        # roundoff error, plus error in
        # the platform exp(), can cause this to spill
        # a few ULP above 1.0. For
        # example, chi2P(100, 300) on my box
        # has sum == 1.0 + 2.0**-52 at this
        # point.  Returning a value even a teensy
        # bit over 1.0 is no good.
        return np.min(sum)

    @staticmethod
    def warn_with_traceback(message, category, filename, lineno, file=None, line=None):

        log = file if hasattr(file, 'write') else sys.stderr
        traceback.print_stack(file=log)
        log.write(warnings.formatwarning(message, category, filename, lineno, line))


class PPPETM(ETM):

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False, no_model=False):

        # load all the PPP coordinates available for this station
        # exclude ppp solutions in the exclude table and any solution that is more than 100 meters from the auto coord

        self.ppp_soln = PppSoln(cnn, NetworkCode, StationCode)

        ETM.__init__(self, cnn, self.ppp_soln, no_model)

        # no offset applied
        self.L = np.array([self.soln.x,
                           self.soln.y,
                           self.soln.z])

        # reduced to x y z coordinate of the station
        self.l = self.rotate_2neu(np.array([self.ppp_soln.x - self.ppp_soln.auto_x,
                                            self.ppp_soln.y - self.ppp_soln.auto_y,
                                            self.ppp_soln.z - self.ppp_soln.auto_z]))

        self.run_adjustment(cnn, self.l, plotit)


class GamitETM(ETM):

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False,
                 no_model=False, gamit_soln=None, project=None):

        if gamit_soln is None:
            self.polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM gamit_soln '
                                               'WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                               '"StationCode" = \'%s\' '
                                               'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                               % (project, NetworkCode, StationCode))

            self.gamit_soln = GamitSoln(cnn, self.polyhedrons, NetworkCode, StationCode)

        else:
            # load the GAMIT polyhedrons
            self.gamit_soln = gamit_soln

        ETM.__init__(self, cnn, self.gamit_soln, no_model)

        # no offset applied
        self.L = np.array([self.gamit_soln.x,
                           self.gamit_soln.y,
                           self.gamit_soln.z])

        # reduced to x y z coordinate of the station
        self.l = self.rotate_2neu(np.array([self.gamit_soln.x - self.gamit_soln.auto_x,
                                            self.gamit_soln.y - self.gamit_soln.auto_y,
                                            self.gamit_soln.z - self.gamit_soln.auto_z]))

        self.run_adjustment(cnn, self.l, plotit)

    def get_residuals_dict(self, use_ppp_model=False, cnn=None):
        # this function return the values of the ETM ONLY

        dict_o = []
        if self.A is not None:

            neu = []

            if not use_ppp_model:
                # get residuals from GAMIT solutions to GAMIT model
                for i in range(3):
                    neu.append(np.dot(self.A, self.C[i]))
            else:
                # get residuals from GAMIT solutions to PPP model
                etm = PPPETM(cnn, self.NetworkCode, self.StationCode)
                # DDG: 20-SEP-2018 compare using MJD not FYEAR to avoid round off errors
                index = np.isin(etm.soln.mjds, self.soln.mjd)
                for i in range(3):
                    # use the etm object to obtain the design matrix that matches the dimensions of self.soln.t
                    neu.append(np.dot(etm.As[index, :], etm.C[i]))

                del etm

            xyz = self.rotate_2xyz(np.array(neu)) + np.array([self.soln.auto_x, self.soln.auto_y, self.soln.auto_z])

            rxyz = xyz - self.L

            px = np.ones(self.P[0].shape)
            py = np.ones(self.P[1].shape)
            pz = np.ones(self.P[2].shape)

            dict_o += [(net, stn, x, y, z, sigx, sigy, sigz, year, doy)
                       for x, y, z, sigx, sigy, sigz, net, stn, year, doy in
                       zip(rxyz[0].tolist(), rxyz[1].tolist(), rxyz[2].tolist(),
                           px.tolist(), py.tolist(), pz.tolist(),
                           repeat(self.NetworkCode), repeat(self.StationCode),
                           [date.year for date in self.gamit_soln.date],
                           [date.doy for date in self.gamit_soln.date])]
        else:
            raise pyETMException_NoDesignMatrix('No design matrix available for %s.%s' %
                                                   (self.NetworkCode, self.StationCode))

        return dict_o


class DailyRep(ETM):

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False,
                 no_model=False, gamit_soln=None, project=None):

        if gamit_soln is None:
            self.polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM gamit_soln '
                                               'WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                               '"StationCode" = \'%s\' '
                                               'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                               % (project, NetworkCode, StationCode))

            self.gamit_soln = GamitSoln(cnn, self.polyhedrons, NetworkCode, StationCode)

        else:
            # load the GAMIT polyhedrons
            self.gamit_soln = gamit_soln

        ETM.__init__(self, cnn, self.gamit_soln, no_model, False, False, False)

        # for repetitivities, vector with difference
        self.l = self.rotate_2neu(np.array([self.gamit_soln.x,
                                            self.gamit_soln.y,
                                            self.gamit_soln.z]))

        # for repetitivities, same vector for both
        self.L = self.l

        self.run_adjustment(cnn, self.l, plotit)

    def get_residuals_dict(self):
        # this function return the values of the ETM ONLY

        dict_o = []
        if self.A is not None:

            neu = []

            for i in range(3):
                neu.append(np.dot(self.A, self.C[i]))

            xyz = self.rotate_2xyz(np.array(neu)) + np.array([self.soln.auto_x, self.soln.auto_y, self.soln.auto_z])

            rxyz = xyz - self.L

            px = np.ones(self.P[0].shape)
            py = np.ones(self.P[1].shape)
            pz = np.ones(self.P[2].shape)

            dict_o += [(net, stn, x, y, z, sigx, sigy, sigz, year, doy)
                       for x, y, z, sigx, sigy, sigz, net, stn, year, doy in
                       zip(rxyz[0].tolist(), rxyz[1].tolist(), rxyz[2].tolist(),
                           px.tolist(), py.tolist(), pz.tolist(),
                           repeat(self.NetworkCode), repeat(self.StationCode),
                           [date.year for date in self.gamit_soln.date],
                           [date.doy for date in self.gamit_soln.date])]
        else:
            raise pyETMException_NoDesignMatrix('No design matrix available for %s.%s' %
                                                   (self.NetworkCode, self.StationCode))

        return dict_o