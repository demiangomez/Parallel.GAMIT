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
from Utils import rotct2lg
from Utils import rotlg2ct
from Utils import ecef2lla
from os.path import getmtime
from itertools import repeat
from pyBunch import Bunch
from pprint import pprint

import traceback
import warnings
import sys

LIMIT = 2.5

NO_EFFECT = None
CO_SEISMIC_DECAY = 0
ANTENNA_CHANGE = 1
CO_SEISMIC_JUMP_DECAY = 2
FRAME_CHANGE = 3
GENERIC_JUMP = 4
UNDETERMINED = -1

EQ_MIN_DAYS = 15
JP_MIN_DAYS = 5

DEFAULT_DECAY = 0.5


class pyPPPETMException(Exception):

    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class pyPPPETMException_NoDesignMatrix(pyPPPETMException):
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


def not_equal(t, jump1, jump2):

    if jump1.type == CO_SEISMIC_DECAY or jump2.type == CO_SEISMIC_DECAY:
        return True

    if jump1.type == CO_SEISMIC_JUMP_DECAY:
        # depending on the type of decay
        vect1 = jump1.eval(t)[:, 0]
    else:
        vect1 = jump1.eval(t)

    if jump2.type == CO_SEISMIC_JUMP_DECAY:
        # depending on the type of decay
        vect2 = jump2.eval(t)[:, 0]
    else:
        vect2 = jump2.eval(t)

    return any(np.logical_xor(vect1, vect2))


class PppSoln:
    """"class to extract the PPP solutions from the database"""

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        # DDG: modified to get a linear trend in X Y Z using all the available solutions
        tppp = cnn.query('SELECT PPP.* FROM (SELECT p1.* FROM ppp_soln p1 '
            'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' AND '
            'NOT EXISTS (SELECT * FROM ppp_soln_excl p2'
            '  WHERE p2."NetworkCode" = p1."NetworkCode" AND'
            '        p2."StationCode" = p1."StationCode" AND'
            '        p2."Year"        = p1."Year"        AND'
            '        p2."DOY"         = p1."DOY") ORDER BY "Year", "DOY") as PPP' % (NetworkCode, StationCode))

        table = tppp.dictresult()

        if len(table) >= 2:

            T = (pyDate.Date(year=item.get('Year'), doy=item.get('DOY')).fyear for item in table)
            X = [float(item['X']) for item in table]
            Y = [float(item['Y']) for item in table]
            Z = [float(item['Z']) for item in table]
            x = np.array(X)
            y = np.array(Y)
            z = np.array(Z)
            t = np.array(list(T))

            # solve a simple LSQ linear problem
            # offset
            c = np.ones((t.size, 1))

            # velocity
            v = (t - t.min())

            A = np.column_stack((c, v))

            cx = np.linalg.lstsq(A, x, rcond=-1)[0]
            cy = np.linalg.lstsq(A, y, rcond=-1)[0]
            cz = np.linalg.lstsq(A, z, rcond=-1)[0]

            # load all the PPP coordinates available for this station
            # exclude ppp solutions in the exclude table and any solution that is more than 20 meters from the simple
            # linear trend calculated above

            ppp = cnn.query(
                'SELECT PPP.* FROM (SELECT p1.*, sqrt((p1."X" - (' + str(cx[0]) + ' + ' + str(cx[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2 + '
                                                     '(p1."Y" - (' + str(cy[0]) + ' + ' + str(cy[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2 + '
                                                     '(p1."Z" - (' + str(cz[0]) + ' + ' + str(cz[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2) as dist FROM ppp_soln p1 '
                'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' AND '
                'NOT EXISTS (SELECT * FROM ppp_soln_excl p2'
                '  WHERE p2."NetworkCode" = p1."NetworkCode" AND'
                '        p2."StationCode" = p1."StationCode" AND'
                '        p2."Year"        = p1."Year"        AND'
                '        p2."DOY"         = p1."DOY") ORDER BY "Year", "DOY") as PPP WHERE PPP.dist <= 30 ORDER BY PPP."Year", PPP."DOY"' % (
                NetworkCode, StationCode))

            ppp_blu = cnn.query(
                'SELECT PPP.* FROM (SELECT p1.*, sqrt((p1."X" - (' + str(cx[0]) + ' + ' + str(cx[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2 + '
                                                     '(p1."Y" - (' + str(cy[0]) + ' + ' + str(cy[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2 + '
                                                     '(p1."Z" - (' + str(cz[0]) + ' + ' + str(cz[1]) + '*(fyear(p1."Year", p1."DOY") - ' + str(t.min()) + ')))^2) as dist FROM ppp_soln p1 '
                'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' AND '
                'NOT EXISTS (SELECT * FROM ppp_soln_excl p2'
                '  WHERE p2."NetworkCode" = p1."NetworkCode" AND'
                '        p2."StationCode" = p1."StationCode" AND'
                '        p2."Year"        = p1."Year"        AND'
                '        p2."DOY"         = p1."DOY") ORDER BY "Year", "DOY") as PPP WHERE PPP.dist > 30 ORDER BY PPP."Year", PPP."DOY"' % (
                    NetworkCode, StationCode))

            self.table     = ppp.dictresult()
            self.solutions = len(self.table)
            # blunders
            self.blunders = ppp_blu.dictresult()
            self.ts_blu = np.array([pyDate.Date(year=item['Year'], doy=item['DOY']).fyear for item in self.blunders])

            if self.solutions >= 1:
                X = [float(item['X']) for item in self.table]
                Y = [float(item['Y']) for item in self.table]
                Z = [float(item['Z']) for item in self.table]

                T = (pyDate.Date(year=item.get('Year'),doy=item.get('DOY')).fyear for item in self.table)
                MJD = (pyDate.Date(year=item.get('Year'),doy=item.get('DOY')).mjd for item in self.table)

                self.x = np.array(X)
                self.y = np.array(Y)
                self.z = np.array(Z)
                self.t = np.array(list(T))
                self.mjd = np.array(list(MJD))

                # continuous time vector for plots
                ts = np.arange(np.min(self.mjd), np.max(self.mjd) + 1, 1)
                ts = np.array([pyDate.Date(mjd=tts).fyear for tts in ts])

                self.ts = ts

                self.lat, self.lon, self.height = ecef2lla([np.mean(self.x).tolist(),np.mean(self.y).tolist(),np.mean(self.z).tolist()])
            else:
                if len(self.blunders) >= 1:
                    raise pyPPPETMException('No viable PPP solutions available for %s.%s (all blunders!)' % (NetworkCode, StationCode))
                else:
                    raise pyPPPETMException('No PPP solutions available for %s.%s' % (NetworkCode, StationCode))

            # get a list of the epochs with files but no solutions. This will be shown in the outliers plot as a special marker
            rnx = cnn.query(
                'SELECT r.* FROM rinex_proc as r '
                'LEFT JOIN ppp_soln as p ON '
                'r."NetworkCode" = p."NetworkCode" AND '
                'r."StationCode" = p."StationCode" AND '
                'r."ObservationYear" = p."Year"    AND '
                'r."ObservationDOY"  = p."DOY"'
                'WHERE r."NetworkCode" = \'%s\' AND r."StationCode" = \'%s\' AND '
                'p."NetworkCode" IS NULL' % (NetworkCode, StationCode))

            self.rnx_no_ppp = rnx.dictresult()
            self.ts_ns = np.array([float(item['ObservationFYear']) for item in self.rnx_no_ppp])

            self.completion = 100. - float(len(self.ts_ns)) / float(len(self.ts_ns) + len(self.t)) * 100.

        else:
            raise pyPPPETMException('Less than 3 PPP solutions available for %s.%s' % (NetworkCode, StationCode))


class GamitSoln:
    """"class to extract the GAMIT polyhedrons from the database"""

    def __init__(self, cnn, polyhedrons, NetworkCode, StationCode):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        self.solutions = len(polyhedrons)
        # blunders
        self.blunders = []
        self.ts_blu = np.array([])

        if self.solutions >= 1:
            X = [float(item['X']) for item in polyhedrons]
            Y = [float(item['Y']) for item in polyhedrons]
            Z = [float(item['Z']) for item in polyhedrons]

            T = (pyDate.Date(year=item.get('Year'), doy=item.get('DOY')).fyear for item in polyhedrons)
            MJD = (pyDate.Date(year=item.get('Year'), doy=item.get('DOY')).mjd for item in polyhedrons)

            self.x = np.array(X)
            self.y = np.array(Y)
            self.z = np.array(Z)
            self.t = np.array(list(T))
            self.mjd = np.array(list(MJD))

            self.date = [pyDate.Date(year=item.get('Year'),doy=item.get('DOY')) for item in polyhedrons]

            # continuous time vector for plots
            ts = np.arange(np.min(self.mjd), np.max(self.mjd) + 1, 1)
            ts = np.array([pyDate.Date(mjd=tts).fyear for tts in ts])

            self.ts = ts

            self.lat, self.lon, self.height = ecef2lla([np.mean(self.x).tolist(), np.mean(self.y).tolist(), np.mean(self.z).tolist()])
        else:
            if len(self.blunders) >= 1:
                raise pyPPPETMException('No viable PPP solutions available for %s.%s (all blunders!)' % (NetworkCode, StationCode))
            else:
                raise pyPPPETMException('No PPP solutions available for %s.%s' % (NetworkCode, StationCode))

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


class Jump:
    """
    Co-seismic or antenna change jump class
    """
    def __init__(self, date, decay, t, frame_change=False):
        """"
        Possible types:
            0 = ongoing decay before the start of the data
            1 = Antenna jump with no decay
            2 = Co-seismic jump with decay
        """
        self.a = np.array([])  # log decay amplitude
        self.b = np.array([])  # jump amplitude
        self.sigmab = np.array([])  # jump amplitude sigma
        self.sigmaa = np.array([])  # log decay amplitude sigma
        self.T = decay          # relaxation time
        self.date = date        # save the date object
        self.year = date.fyear  # fyear of jump

        if self.year <= t.min() and decay == 0:
            # antenna change or some other jump BEFORE the start of the data
            self.type = NO_EFFECT
            self.params = 0

        elif self.year >= t.max():
            # antenna change or some other jump AFTER the end of the data
            self.type   = NO_EFFECT
            self.params = 0

        elif self.year <= t.min() and decay != 0:
            # earthquake before the start of the data, leave the decay but not the jump
            self.type   = CO_SEISMIC_DECAY
            self.params = 1

        elif self.year > t.min() and self.year < t.max() and decay == 0:
            self.type   = ANTENNA_CHANGE
            self.params = 1

        elif self.year > t.min() and self.year < t.max() and decay != 0:
            self.type   = CO_SEISMIC_JUMP_DECAY
            self.params = 2

        if frame_change:
            self.type = FRAME_CHANGE

    def remove(self):
        # this method will make this jump type = 0 and adjust its params
        self.type = NO_EFFECT
        self.params = 0

    def eval(self, t):
        # given a time vector t, return the design matrix column vector(s)

        if self.type is NO_EFFECT:
            return np.array([])

        hl = np.zeros((t.shape[0],))
        ht = np.zeros((t.shape[0],))

        if self.type in (CO_SEISMIC_DECAY, CO_SEISMIC_JUMP_DECAY):
            hl[t > self.year] = np.log10(1 + (t[t > self.year] - self.year) / self.T)

        if self.type in (ANTENNA_CHANGE, CO_SEISMIC_JUMP_DECAY, FRAME_CHANGE):
            ht[t > self.year] = 1

        if self.type == CO_SEISMIC_JUMP_DECAY and ht[t > self.year].size == 1:
            # too few observations to fit the decay
            self.remove()
            return np.array([])

        if np.any(hl) and np.any(ht):
            return np.column_stack((ht, hl))

        elif np.any(hl) and not np.any(ht):
            return hl

        elif not np.any(hl) and np.any(ht):
            return ht

        else:
            return np.array([])

    def __str__(self):
        return str(self.year)+', '+str(self.type)+', '+str(self.T)

    def __repr__(self):
        return 'pyPPPETM.Jump('+str(self.year)+', '+str(self.type)+', '+str(self.T)+')'


class JumpsTable:
    """"class to determine the jump table based on distance to earthquakes and receiver/antenna changes"""
    def __init__(self, cnn, NetworkCode, StationCode, t, add_antenna_jumps=1, frame_changes=True, metadata_jumps=True):

        self.t = t
        self.A = None
        self.params = None
        self.constrains = None

        self.StationCode = StationCode
        self.NetworkCode = NetworkCode

        # station location
        stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

        stn = stn.dictresult()[0]

        # get all the antenna and receiver changes from the station info
        StnInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        # frame changes
        if frame_changes:
            frames = cnn.query('SELECT distinct on ("ReferenceFrame") "ReferenceFrame", "Year", "DOY" from ppp_soln WHERE '
                              '"NetworkCode" = \'%s\' AND "StationCode" = \'%s\' order by "ReferenceFrame", "Year", "DOY"' %
                              (NetworkCode, StationCode))

            frames = frames.dictresult()
        else:
            frames = []

        # get the earthquakes based on Mike's expression
        jumps = cnn.query('SELECT * FROM earthquakes ORDER BY date')
        jumps = jumps.dictresult()

        eq = [[float(jump['lat']), float(jump['lon']), float(jump['mag']),
               int(jump['date'].year), int(jump['date'].month), int(jump['date'].day),
               int(jump['date'].hour), int(jump['date'].minute), int(jump['date'].second)] for jump in jumps]
        eq = np.array(list(eq))

        dist = distance(float(stn['lon']), float(stn['lat']), eq[:, 1], eq[:, 0])

        m = -0.8717 * (np.log10(dist) - 2.25) + 0.4901 * (eq[:, 2] - 6.6928)
        # build the earthquake jump table
        # remove event events that happened the same day

        eq_jumps = list(set(pyDate.Date(year=int(eq[0]), month=int(eq[1]), day=int(eq[2]), hour=int(eq[3]), minute=int(eq[4]), second=int(eq[5])) for eq in eq[m > 0, 3:9]))

        eq_jumps.sort()

        self.table = []
        skip_i = []

        for i, jump in enumerate(eq_jumps):
            if i in skip_i:
                continue

            if i < len(eq_jumps)-1 and len(eq_jumps) > 1:
                while True:
                    nxjump = eq_jumps[i+1]
                    if jump.fyear < t.min() < nxjump.fyear:
                        # if the eq jump occurred before the start date and the next eq jump is within the data, add it
                        # otherwise, we would be adding multiple decays to the beginning of the time series
                        self.table.append(Jump(jump, 0.5, t))
                        break

                    elif jump.fyear >= t.min():
                        # if there is another earthquake within 10 days of this earthquake, i.e.
                        # if eq_jumps[i+1] - jump < 6 days, don't add the log transient of the next jump
                        # a log transient with less than 6 days if not worth adding the log decay
                        # (which destabilizes the sys. of eq.)

                        if (nxjump.fyear - jump.fyear)*365 < 10: #or t[np.where((t <= nxjump) & (t > jump))].size < 10:
                            i += 1
                            skip_i += [i]
                            # add the jump but just as an offset. Will be removed if makes the matrix singular
                            self.table.append(Jump(nxjump, 0, t))
                            if i == len(eq_jumps)-1:
                                # we are out of jumps!
                                self.table.append(Jump(jump, 0.5, t))
                                break
                        else:
                            self.table.append(Jump(jump, 0.5, t))
                            break
                    else:
                        # a jump outside the time window, go to next
                        break
            else:
                if t.min() < jump.fyear < t.max():
                    self.table.append(Jump(jump, 0.5, t))

        # antenna and receiver changes
        if add_antenna_jumps != 0 and metadata_jumps is True:
            for i, jump in enumerate(StnInfo.records):
                if i > 0:
                    date = pyDate.Date(datetime=jump['DateStart'])
                    if i > 1 and len(self.table) > 0:
                        # check if this jump should be added (maybe no data to constrain the last one!)
                        if self.table[-1].eval(t).size and Jump(date, 0, t).eval(t).size:
                            if not_equal(t, self.table[-1], Jump(date, 0, t)):
                                self.table.append(Jump(date, 0, t))
                    else:
                        if Jump(date, 0, t).eval(t).size:
                            self.table.append(Jump(date, 0, t))

        if len(frames) > 1:
            # more than one frame, add a jump
            frames.sort(key=lambda k: k['Year'])

            for frame in frames[1:]:
                date = pyDate.Date(Year=frame['Year'], doy=frame['DOY'])
                self.table.append(Jump(date, 0, t, frame_change=True))

        # sort jump table (using the key year)
        self.table.sort(key=lambda jump: jump.year)

        self.lat = float(stn['lat'])
        self.lon = float(stn['lon'])

        self.UpdateTable()

    def UpdateTable(self):
        # build the design matrix
        self.A = self.GetDesignTs(self.t)

        if self.A.size:
            self.params = self.A.shape[1]
        else:
            self.params = 0

        if self.A.size:
            # dilution of precision of the adjusted parameters
            try:
                if len(self.A.shape) > 1:
                    DOP = np.diag(np.linalg.inv(np.dot(self.A.transpose(), self.A)))
                    self.constrains = np.zeros((np.argwhere(DOP > 5).size, self.A.shape[1]))
                else:
                    DOP = np.diag(np.linalg.inv(np.dot(self.A[:, np.newaxis].transpose(), self.A[:, np.newaxis])))
                    self.constrains = np.zeros((np.argwhere(DOP > 5).size, 1))
            except np.linalg.LinAlgError:
                # matrix is singular, not possible to add constrain
                self.constrains = np.zeros((self.A.shape[0], 1))
                DOP = np.zeros((self.A.shape[0], 1))

            # apply constrains
            if np.any(DOP > 5):
                for i, dop in enumerate(np.argwhere(DOP > 5)):
                    self.constrains[i, dop] = 1
        else:
            self.constrains = np.array([])

    def RemoveJump(self, cjump):
        for jump in self.table:
            if cjump == jump:
                jump.remove()
                self.UpdateTable()
                break

    def ForceConstrain(self, cjump):
        # force a constrain condition equation on the specified jump
        pos = 0
        for jump in self.table:
            if cjump == jump:
                if len(self.A.shape) > 1:
                    self.constrains = np.append(self.constrains, np.zeros((cjump.params, self.A.shape[1])), axis=0)
                else:
                    self.constrains = np.append(self.constrains, np.zeros((cjump.params, 1)))

                for i in range(cjump.params):
                    self.constrains[-1-i, pos+i] = 1
                break
            else:
                pos = pos + jump.params

    def GetDesignTs(self, t):

        A = np.array([])

        # get the design matrix for the jump table
        for jump in self.table:
            if not jump.type is NO_EFFECT:
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
                    else:
                        A = a

        if A.size:
            if len(A.shape) == 1:
                A = A[:, np.newaxis]

        return A

    def LoadParameters(self, x, s, L, J):

        C = x[L.params:L.params + J.params]
        S = s[L.params:L.params + J.params]

        s = 0
        for jump in self.table:
            if jump.type is not NO_EFFECT:
                if jump.params == 1 and jump.T != 0:
                    jump.a = np.append(jump.a, C[s:s + 1])
                    jump.sigmaa = np.append(jump.sigmaa, S[s:s + 1])

                elif jump.params == 1 and jump.T == 0:
                    jump.b = np.append(jump.b, C[s:s + 1])
                    jump.sigmab = np.append(jump.sigmab, S[s:s + 1])

                elif jump.params == 2:
                    jump.b = np.append(jump.b, C[s:s + 1])
                    jump.a = np.append(jump.a, C[s + 1:s + 2])
                    jump.sigmab = np.append(jump.sigmab, S[s:s + 1])
                    jump.sigmaa = np.append(jump.sigmaa, S[s + 1:s + 2])

                s = s + jump.params

    @staticmethod
    def return_xs(x, s, L, J):
        """ function used to return the X and sigma vectors in one continuous vector """

        C = x[L.params:L.params + J.params]
        S = s[L.params:L.params + J.params]

        return zip(C, S)

    def PrintParams(self, lat, lon):

        output_n = ['Year     Relx    [mm]']
        output_e = ['Year     Relx    [mm]']
        output_u = ['Year     Relx    [mm]']

        for jump in self.table:

            a = [None, None, None]
            b = [None, None, None]

            if jump.type is not NO_EFFECT:

                if (jump.params == 1 and jump.T != 0) or jump.params == 2:
                    a[0], a[1], a[2] = ct2lg(jump.a[0], jump.a[1], jump.a[2], lat, lon)

                if (jump.params == 1 and jump.T == 0) or jump.params == 2:
                    b[0], b[1], b[2] = ct2lg(jump.b[0], jump.b[1], jump.b[2], lat, lon)

                if not b[0] is None:
                    output_n.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[0][0] * 1000.0))
                    output_e.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[1][0] * 1000.0))
                    output_u.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[2][0] * 1000.0))

                if not a[0] is None:
                    output_n.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[0][0] * 1000.0))
                    output_e.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[1][0] * 1000.0))
                    output_u.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[2][0] * 1000.0))

        if len(output_n) > 22:
            output_n = output_n[0:22] + ['Table too long to print!']
            output_e = output_e[0:22] + ['Table too long to print!']
            output_u = output_u[0:22] + ['Table too long to print!']

        return '\n'.join(output_n), '\n'.join(output_e), '\n'.join(output_u)


class JumpTablev2:

    def __init__(self, cnn, NetworkCode, StationCode, solution, t):

        self.table = []

        # get earthquakes for this station
        self.earthquakes = Earthquakes(cnn, NetworkCode, StationCode, solution, t)

        self.generic_jumps = GenericJumps(cnn, NetworkCode, StationCode, solution, t)

        jumps = self.earthquakes.table + self.generic_jumps.table

        jumps.sort()

        # add the relevant jumps, make sure none are incompatible
        for jump in jumps:
            self.insert_jump(jump)

        # add the "NO_EFFECT" jumps and resort the table
        ne_jumps = [j for j in jumps if j.par.type == NO_EFFECT
                    and j.date > pyDate.Date(fyear=t.min()) < j.date < pyDate.Date(fyear=t.max())]

        self.table += ne_jumps

        self.table.sort()

    def insert_jump(self, jump):

        if len(self.table) == 0:
            if jump.par.type != NO_EFFECT:
                self.table.append(jump)
        else:
            # take last jump and compare to adding jump
            jj = self.table[-1]

            if jump.par.type != NO_EFFECT:
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

    def GetDesignTs(self, t):

        A = np.array([])

        # get the design matrix for the jump table
        for jump in self.table:
            if jump.par.type is not NO_EFFECT:
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

    def LoadParameters(self, x, s, L, J):

        # new behavior, load all axis at the same time
        C = []
        S = []

        for i in range(3):
            C[i] = x[L.params:L.params + J.params]
            S[i] = s[L.params:L.params + J.params]

        s = 0
        for jump in self.table:

            if jump.type is not NO_EFFECT:

                if jump.par.type in (CO_SEISMIC_DECAY, CO_SEISMIC_JUMP_DECAY):
                    for i in jump.par.nr:
                        jump.par.decays[i,:] = C[s:s + 1]
                        jump.par.sigmas_j
                else:
                    pass

                if jump.params == 1 and jump.T != 0:
                    jump.a = np.append(jump.a, C[s:s + 1])
                    jump.sigmaa = np.append(jump.sigmaa, S[s:s + 1])

                elif jump.params == 1 and jump.T == 0:
                    jump.b = np.append(jump.b, C[s:s + 1])
                    jump.sigmab = np.append(jump.sigmab, S[s:s + 1])

                elif jump.params == 2:
                    jump.b = np.append(jump.b, C[s:s + 1])
                    jump.a = np.append(jump.a, C[s + 1:s + 2])
                    jump.sigmab = np.append(jump.sigmab, S[s:s + 1])
                    jump.sigmaa = np.append(jump.sigmaa, S[s + 1:s + 2])

                s = s + jump.params

    @staticmethod
    def return_xs(x, s, L, J):
        """ function used to return the X and sigma vectors in one continuous vector """

        C = x[L.params:L.params + J.params]
        S = s[L.params:L.params + J.params]

        return zip(C, S)

    def PrintParams(self, lat, lon):

        output_n = ['Year     Relx    [mm]']
        output_e = ['Year     Relx    [mm]']
        output_u = ['Year     Relx    [mm]']

        for jump in self.table:

            a = [None, None, None]
            b = [None, None, None]

            if jump.type is not NO_EFFECT:

                if (jump.params == 1 and jump.T != 0) or jump.params == 2:
                    a[0], a[1], a[2] = ct2lg(jump.a[0], jump.a[1], jump.a[2], lat, lon)

                if (jump.params == 1 and jump.T == 0) or jump.params == 2:
                    b[0], b[1], b[2] = ct2lg(jump.b[0], jump.b[1], jump.b[2], lat, lon)

                if not b[0] is None:
                    output_n.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[0][0] * 1000.0))
                    output_e.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[1][0] * 1000.0))
                    output_u.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, 0, b[2][0] * 1000.0))

                if not a[0] is None:
                    output_n.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[0][0] * 1000.0))
                    output_e.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[1][0] * 1000.0))
                    output_u.append('{:8.3f} {:4.2f} {:>7.1f}'.format(jump.year, jump.T, a[2][0] * 1000.0))

        if len(output_n) > 22:
            output_n = output_n[0:22] + ['Table too long to print!']
            output_e = output_e[0:22] + ['Table too long to print!']
            output_u = output_u[0:22] + ['Table too long to print!']

        return '\n'.join(output_n), '\n'.join(output_e), '\n'.join(output_u)

class Jumpv2(object):
    """
    Co-seismic or antenna change jump class
    """
    def __init__(self, t, date, metadata, dtype=UNDETERMINED):
        """"
        """
        # define initial state variables
        self.date = date
        self.par = Bunch()

        self.par.jump = np.zeros(3)
        self.par.sigmas_j = np.zeros(3)
        self.par.date = date.datetime()
        self.par.metadata = metadata
        self.par.params = 0
        self.par.type = dtype

        self.design = Jumpv2.eval(self, t)

        if np.any(self.design) and not np.all(self.design):
            self.par.type = GENERIC_JUMP
            self.par.params = 1
        else:
            self.par.type = NO_EFFECT
            self.par.params = 0

    def remove(self):
        # this method will make this jump type = 0 and adjust its params
        self.par.type = NO_EFFECT
        self.par.params = 0

    def eval(self, t):
        # given a time vector t, return the design matrix column vector(s)
        if self.par.type == NO_EFFECT:
            return np.array([])

        ht = np.zeros((t.shape[0], 1))

        ht[t > self.date.fyear] = 1.

        return ht

    def __eq__(self, jump):

        if not isinstance(jump, Jumpv2):
            raise pyPPPETMException('type: ' + str(type(jump)) + ' invalid. Can compare two Jump objects')

        # compare two jumps together and make sure they will not generate a singular (or near singular) system of eq
        c = np.sum(np.logical_xor(self.design[:, 0], jump.design[:, 0]))

        if self.par.type in (CO_SEISMIC_JUMP_DECAY,
                              CO_SEISMIC_DECAY) and jump.par.type in (CO_SEISMIC_JUMP_DECAY, CO_SEISMIC_DECAY):

            # if self is a co-seismic jump and next jump is also co-seismic
            # and there are less than two weeks of data to constrain params, return false
            if c <= EQ_MIN_DAYS:
                return True, jump
            else:
                return False, None

        elif self.par.type in (CO_SEISMIC_JUMP_DECAY,
                                CO_SEISMIC_DECAY, GENERIC_JUMP) and jump.par.type == GENERIC_JUMP:

            if c <= JP_MIN_DAYS:
                # can't fit the co-seismic or generic jump AND the generic jump after, remove "jump" generic jump
                return True, self
            else:
                return False, None

        elif self.par.type == GENERIC_JUMP and jump.par.type == (CO_SEISMIC_JUMP_DECAY, CO_SEISMIC_DECAY):

            if c <= JP_MIN_DAYS:
                # if generic jump before an earthquake jump and less than 5 days, co-seismic prevails
                return True, jump
            else:
                return False, None

        elif self.par.type == NO_EFFECT and jump.par.type != NO_EFFECT:
            # if comparing to a self that has NO_EFFECT, remove and keep jump
            return True, jump

        elif self.par.type != NO_EFFECT and jump.par.type == NO_EFFECT:
            # if comparing against a jump that has NO_EFFECT, remove jump keep self
            return True, self

        elif self.par.type == NO_EFFECT and jump.par.type == NO_EFFECT:
            # no jump has an effect, return None. This will be interpreted as False (if not result)
            return None, None

    def __str__(self):
        return '(' + str(self.date)+'), '+str(self.par.type) + ', "' + str(self.par.metadata) + '"'

    def __repr__(self):
        return 'pyPPPETM.Jump(' + str(self) + ')'

    def __lt__(self, jump):

        if not isinstance(jump, Jumpv2):
            raise pyPPPETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear < jump.date.fyear

    def __le__(self, jump):

        if not isinstance(jump, Jumpv2):
            raise pyPPPETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear <= jump.date.fyear

    def __gt__(self, jump):

        if not isinstance(jump, Jumpv2):
            raise pyPPPETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear > jump.date.fyear

    def __ge__(self, jump):

        if not isinstance(jump, Jumpv2):
            raise pyPPPETMException('type: '+str(type(jump))+' invalid.  Can only compare Jump objects')

        return self.date.fyear >= jump.date.fyear

    def __hash__(self):
        # to make the object hashable
        return hash(self.date.fyear)


class CoSeisJump(Jumpv2):

    def __init__(self, t, date, relaxation, metadata, dtype=UNDETERMINED):

        # super-class initialization
        Jumpv2.__init__(self, t, date, metadata, dtype)

        if dtype is NO_EFFECT:
            # passing default_type == NO_EFFECT, add the jump but make it NO_EFFECT by default
            self.par.type = NO_EFFECT
            self.par.params = 0
            self.par.decays = None
            self.par.sigmas_d = None
            self.par.relaxation = None

            self.design = np.array([])
            return

        if self.par.type == NO_EFFECT:
            # came back from init as NO_EFFECT. May be a jump before t.min()
            # assign just the decay
            self.par.type = CO_SEISMIC_DECAY
        else:
            self.par.type = CO_SEISMIC_JUMP_DECAY

        # if T is an array, it contains the corresponding decays
        # otherwise, it is a single decay
        if not isinstance(relaxation, np.ndarray):
            relaxation = np.array([relaxation])

        self.par.params += relaxation.shape[0]
        self.par.decays = np.zeros((relaxation.shape[0], 3))
        self.par.sigmas_d = np.zeros((relaxation.shape[0], 3))
        self.par.nr = relaxation.shape[0]
        self.par.relaxation = relaxation

        self.design = self.eval(t)

        # test if earthquake generates at least 10 days of data to adjust
        if self.design.size:
            if np.count_nonzero(self.design[:, -1]) < 10:
                if self.par.type == CO_SEISMIC_JUMP_DECAY:
                    # was a jump and decay, leave the jump
                    self.par.type = GENERIC_JUMP
                    self.par.params -= 1
                else:
                    self.par.type = NO_EFFECT
                    self.par.params = 0
        else:
            self.par.type = NO_EFFECT
            self.par.params = 0

    def eval(self, t):

        ht = Jumpv2.eval(self, t)

        # if there is nothing in ht, then there is no expected output, return none
        if not np.any(ht):
            return np.array([])

        # if it was determined that this is just a generic jump, return ht
        if self.par.type == GENERIC_JUMP:
            return ht

        # support more than one decay
        hl = np.zeros((t.shape[0], self.par.nr))

        for i, T in enumerate(self.par.relaxation):
            hl[t > self.date.fyear, i] = np.log10(1. + (t[t > self.date.fyear] - self.date.fyear) / T)

        # if it's both jump and decay, return ht + hl
        if np.any(hl) and self.par.type == CO_SEISMIC_JUMP_DECAY:
            return np.column_stack((ht, hl))

        # if decay only, return hl
        elif np.any(hl) and self.par.type == CO_SEISMIC_DECAY:
            return hl

    def __str__(self):
        return '(' + str(self.date)+'), ' + str(self.par.type) + ', ' + str(self.par.relaxation) + ', "' + str(self.par.metadata) + '"'

    def __repr__(self):
        return 'pyPPPETM.CoSeisJump(' + str(self) + ')'


class Earthquakes:

    def __init__(self, cnn, NetworkCode, StationCode, solution, t):

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

        eq = [[float(jump['lat']), float(jump['lon']), float(jump['mag']),
               int(jump['date'].year), int(jump['date'].month), int(jump['date'].day),
               int(jump['date'].hour), int(jump['date'].minute), int(jump['date'].second)] for jump in jumps]
        eq = np.array(list(eq))

        dist = distance(lon, lat, eq[:, 1], eq[:, 0])

        m = -0.8717 * (np.log10(dist) - 2.25) + 0.4901 * (eq[:, 2] - 6.6928)
        # build the earthquake jump table
        # remove event events that happened the same day

        eq_jumps = list(set((float(eq[2]), pyDate.Date(year=int(eq[3]), month=int(eq[4]), day=int(eq[5]),
                                                       hour=int(eq[6]), minute=int(eq[7]), second=int(eq[8])))
                            for eq in eq[m > 0, :]))

        eq_jumps.sort(key=lambda x: (x[1], x[0]))

        # open the jumps table
        jp = cnn.query('SELECT * FROM etm_jumps WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                       'AND soln = \'%s\' AND type <> 0' % (NetworkCode, StationCode, solution))

        jp = jp.dictresult()

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

            # filter only jumps for EQ_MIN_DAYS period
            jumps = [(m, d) for m, d in eq_jumps if d.year == date.year and date.doy <= d.doy <= date.doy + EQ_MIN_DAYS]

            if len(jumps) > 1:
                # if more than one jump, get the max magnitude
                mmag = max([m for m, _ in jumps])

                # only keep the earthquake with the largest magnitude
                for m, d in jumps:

                    table = [j['action'] for j in jp if j['Year'] == d.year and j['DOY'] == d.doy]

                    # add unless marked in the jump table as '-'
                    if m == mmag and '-' not in table:
                        f_jumps += [CoSeisJump(t, d, DEFAULT_DECAY, 'mag=%.1f' % m)]
                        # once the jump was added, exit for loop
                        break
                    else:
                        # add only if in jump list with a '+'
                        if '+' in table:
                            f_jumps += [CoSeisJump(t, d, DEFAULT_DECAY, 'mag=%.1f' % m)]
                            # once the jump was added, exit for loop
                            break
                        else:
                            f_jumps += [CoSeisJump(t, d, DEFAULT_DECAY, 'mag=%.1f' % m, NO_EFFECT)]
            else:
                # add, unless marked in table with '-'
                table = [j['action'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]

                if '-' not in table:
                    f_jumps += [CoSeisJump(t, date, DEFAULT_DECAY, 'mag=%.1f' % mag)]
                else:
                    # add it with NO_EFFECT for display purposes
                    f_jumps += [CoSeisJump(t, date, DEFAULT_DECAY, 'mag=%.1f' % mag, NO_EFFECT)]

            next_date = date + EQ_MIN_DAYS

        # final jump table
        self.table = f_jumps


class GenericJumps(object):

    def __init__(self, cnn, NetworkCode, StationCode, solution, t):

        self.solution = solution
        self.table = []

        # analyze if it is possible to add the antenna jumps (base on the data available)
        wt = np.sort(np.unique(t - np.fix(t)))
        # analyze the gaps in the data
        dt = np.diff(wt)
        # max dt (internal)
        dtmax = np.max(dt)
        # dt wrapped around
        dt_interyr = 1 - wt[-1] + wt[0]
        if dt_interyr > dtmax:
            dtmax = dt_interyr

        if dtmax <= 0.2465:
            # put jumps in
            if solution == 'ppp':
                # only add the jumps by default when using PPP solutions
                self.add_metadata_jumps = True
            else:
                self.add_metadata_jumps = False
        else:
            # no jumps
            self.add_metadata_jumps = False

        # open the jumps table
        jp = cnn.query('SELECT * FROM etm_jumps WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                       'AND soln = \'%s\' AND type = 0' % (NetworkCode, StationCode, solution))

        jp = jp.dictresult()

        # get station information
        self.stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        for stninfo in self.stninfo.records[1:]:

            date = pyDate.Date(datetime=stninfo['DateStart'])

            table = [j['action'] for j in jp if j['Year'] == date.year and j['DOY'] == date.doy]

            # add to list only if:
            # 1) add_meta = True AND there is no '-' OR
            # 2) add_meta = False AND there is a '+'

            if (not self.add_metadata_jumps and '+' in table) or (self.add_metadata_jumps and '-' not in table):
                self.table.append(Jumpv2(t, date, 'Ant-Rec: %s-%s' % (stninfo['AntennaCode'], stninfo['ReceiverCode'])))

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
                        self.table.append(Jumpv2(t, date, 'Frame Change: %s' % frame['ReferenceFrame']))

        # now check the jump table to add specific jumps
        jp = cnn.query('SELECT * FROM etm_jumps WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                       'AND soln = \'%s\' AND type = 0 AND action = \'+\'' % (NetworkCode, StationCode, solution))

        jp = jp.dictresult()

        table = [j.date for j in self.table]

        for j in jp:
            date = pyDate.Date(Year=j['Year'], doy=j['DOY'])

            if date not in table:
                self.table.append(Jumpv2(t, date, 'JUMP'))


class Periodic:
    """"class to determine the periodic terms to be included in the ETM"""

    def __init__(self, t):

        if t.size > 1:
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

            # if dtmax < 3 months (90 days = 0.1232), then we can fit the annual
            # if dtmax < 1.5 months (45 days = 0.24657), then we can fit the semi-annual too

            if dtmax <= 0.1232:
                # all components (annual and semi-annual)
                self.A = np.array([sin(2 * pi * t), cos(2 * pi * t), sin(4 * pi * t), cos(4 * pi * t)]).transpose()
                self.frequencies = 2

            elif dtmax <= 0.2465:
                # only annual
                self.A = np.array([sin(2 * pi * t), cos(2 * pi * t)]).transpose()
                self.frequencies = 1

            else:
                # no periodic terms
                self.A = np.array([])
                self.frequencies = 0
        else:
            # no periodic terms
            self.A = np.array([])
            self.frequencies = 0

        # variables to store the periodic amplitudes
        self.sin = np.array([])
        self.cos = np.array([])
        self.sigmasin = np.array([])
        self.sigmacos = np.array([])

        self.params = self.frequencies * 2

    def GetDesignTs(self, ts):
        # return the design matrix given a time vector
        if self.frequencies == 0:
            # no adjustment of periodic terms
            return np.array([])

        elif self.frequencies == 2:
            return np.array([sin(2 * pi * ts), cos(2 * pi * ts), sin(4 * pi * ts), cos(4 * pi * ts)]).transpose()

        elif self.frequencies == 1:
            return np.array([sin(2 * pi * ts), cos(2 * pi * ts)]).transpose()

    def LoadParameters(self, x, s, L, J, P):

        C = x[L.params + J.params:L.params + J.params + P.params]
        S = s[L.params + J.params:L.params + J.params + P.params]

        # load the amplitude parameters
        self.sin = np.append(self.sin, C[0::2])
        self.sigmasin = np.append(self.sigmasin, S[0::2])
        self.cos = np.append(self.cos, C[1::2])
        self.sigmacos = np.append(self.sigmacos, S[1::2])

    @ staticmethod
    def return_xs(x, s, L, J, P):
        """ function used to return the X and sigma vectors in one continuous vector """

        C = x[L.params + J.params:L.params + J.params + P.params]
        S = s[L.params + J.params:L.params + J.params + P.params]

        return zip(C, S)

    def PrintParams(self, lat, lon):

        sn, se, su = ct2lg(self.sin[0:self.frequencies], self.sin[self.frequencies:self.frequencies * 2], self.sin[self.frequencies * 2:self.frequencies * 3], lat, lon)
        cn, ce, cu = ct2lg(self.cos[0:self.frequencies], self.cos[self.frequencies:self.frequencies * 2], self.cos[self.frequencies * 2:self.frequencies * 3], lat, lon)

        # calculate the amplitude of the components
        an = np.sqrt(np.square(sn) + np.square(cn))
        ae = np.sqrt(np.square(se) + np.square(ce))
        au = np.sqrt(np.square(su) + np.square(cu))

        return 'Periodic amp [annual semi] N: %s E: %s U: %s [mm]' % (
            np.array_str(an * 1000.0, precision=1), np.array_str(ae * 1000.0, precision=1),
            np.array_str(au * 1000.0, precision=1))


class Linear:
    """"class to build the linear portion of the design matrix"""

    def __init__(self, t, tref=0):

        self.values = np.array([])
        self.sigmas = np.array([])

        # t ref (just the beginning of t vector)
        if tref == 0:
            tref = np.min(t)

        # offset
        c = np.ones((t.size, 1))

        # velocity
        v = (t - tref)

        self.A = np.column_stack((c, v))
        self.tref = tref
        self.params = 2

    def GetDesignTs(self, ts):

        return np.column_stack((np.ones((ts.size, 1)), (ts - self.tref)))

    def LoadParameters(self, x, s, tref, L):

        C = x[0:L.params]
        S = s[0:L.params]

        self.values = np.append(self.values, np.array([C[0], C[1]]))
        self.sigmas = np.append(self.sigmas, np.array([S[0], S[1]]))
        self.tref = tref

    @staticmethod
    def return_xs(x, s, L):
        """ function used to return the X and sigma vectors in one continuous vector """

        C = x[0:L.params]
        S = s[0:L.params]

        return zip(C, S)

    def PrintParams(self, lat, lon):

        vn, ve, vu = ct2lg(self.values[1], self.values[self.params+1], self.values[2*self.params+1], lat, lon)

        return 'Velocity N: %.2f E: %.2f U: %.2f [mm/yr]' % (vn[0]*1000.0, ve[0]*1000.0, vu[0]*1000.0)


class Design(np.ndarray):

    def __new__(subtype, Linear, Jumps, Periodic, dtype=float, buffer=None, offset=0, strides=None, order=None):
        # Create the ndarray instance of our type, given the usual
        # ndarray input arguments.  This will call the standard
        # ndarray constructor, but return an object of our type.
        # It also triggers a call to InfoArray.__array_finalize__

        shape = (Linear.A.shape[0], Linear.params + Jumps.params + Periodic.params)
        obj = super(Design, subtype).__new__(subtype, shape, dtype, buffer, offset, strides, order)

        obj[:, 0:Linear.params] = Linear.A

        if Jumps.params > 0:
            obj[:, Linear.params:Linear.params + Jumps.params] = Jumps.A

        if Periodic.params > 0:
            obj[:, Linear.params + Jumps.params:Linear.params + Jumps.params + Periodic.params] = Periodic.A

        # set the new attributes to the values passed
        obj.L = Linear  # type: Linear
        obj.J = Jumps  # type: JumpsTable
        obj.P = Periodic  # type: Periodic

        # save the number of total parameters
        obj.params = Linear.params + Jumps.params + Periodic.params

        # Finally, we must return the newly created object:
        return obj

    def __call__(self, ts=None, constrains=False):

        if ts is None:
            if constrains:
                if self.J.constrains.size:
                    A = self.copy()
                    # resize matrix (use A.resize so that it fills with zeros)
                    A.resize((self.shape[0] + self.J.constrains.shape[0], self.shape[1]), refcheck=False)
                    # apply constrains
                    A[-self.J.constrains.shape[0]:, self.L.params:self.L.params + self.J.params] = self.J.constrains
                    return A

                else:
                    return self

            else:
                return self

        else:
            Al = self.L.GetDesignTs(ts)
            Aj = self.J.GetDesignTs(ts)
            Ap = self.P.GetDesignTs(ts)

            As = np.column_stack((Al, Aj)) if Aj.size else Al
            As = np.column_stack((As, Ap)) if Ap.size else As

            return As

    def GetL(self, L, constrains=False):

        if constrains:
            if self.J.constrains.size:
                tL = L.copy()
                tL.resize((L.shape[0] + self.J.constrains.shape[0]), refcheck=False)
                return tL

            else:
                return L

        else:
            return L

    def GetP(self, constrains=False):
        # return a weight matrix full of ones with or without the extra elements for the constrains
        return np.diag(np.ones((self.shape[0]))) if not constrains else np.diag(np.ones((self.shape[0] + self.J.constrains.shape[0])))

    def RemoveConstrains(self, V):
        # remove the constrains to whatever vector is passed
        if self.J.constrains.size:
            return V[0:-self.J.constrains.shape[0]]
        else:
            return V


class ETM:

    def __init__(self, cnn, soln, NetworkCode, StationCode, no_model=False, frame_changes=True, metadata_jumps=True):

        # to display more verbose warnings
        # warnings.showwarning = self.warn_with_traceback

        self.C = []
        self.S = []
        self.F = []
        self.R = []
        self.P = []
        self.factor = []
        self.A = None
        self.soln = soln

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        # save the function objects
        self.Periodic = Periodic(t=soln.t)
        self.Jumps = JumpsTable(cnn, NetworkCode, StationCode, soln.t,
                                add_antenna_jumps=self.Periodic.params, frame_changes=frame_changes,
                                metadata_jumps=metadata_jumps)
        self.Linear = Linear(t=soln.t)

        # calculate the hash value for this station
        # now hash also includes the timestamp of the last time pyPPPETM was modified.
        self.hash = crc32(str(soln.solutions) + ' ' +
                          str(soln.mjd[0]) + ' ' +
                          str(soln.mjd[-1]) + ' ' +
                          str(self.Periodic.params) + ' ' +
                          str(self.Jumps.params) + ' ' +
                          '.'.join([str(j.type) for j in self.Jumps.table]) + ' ' +
                          str(getmtime(__file__)))

        # anything less than four is not worth it
        if soln.solutions > 4 and not no_model:

            # to obtain the parameters
            self.A = Design(self.Linear, self.Jumps, self.Periodic)

            # check if problem can be solved!
            if self.A.shape[1] >= soln.solutions:
                self.A = None
                return

            self.As = self.A(soln.ts)

    def plot(self, pngfile=None, t_win=None, residuals=False):

        import matplotlib.pyplot as plt

        # definitions
        L = [self.soln.x, self.soln.y, self.soln.z]
        p = []
        m = []
        labels = ('North [mm]', 'East [mm]', 'Up [mm]')
        yoffset = 0.001
        xoffset = 0.01

        # get filtered observations
        if self.A is not None:
            filt = self.F[0] * self.F[1] * self.F[2]
        else:
            filt = None

        # find the mean of the observations
        for i in range(3):
            if filt is not None:
                p.append(np.mean(L[i][filt]))
                # calculate the modeled ts and remove mean (in mm)
                m.append((np.dot(self.As, self.C[i]) - p[i])*1000)
            else:
                p.append(np.mean(L[i]))

        # get geocentric difference w.r.t. the mean in mm
        L = [(self.soln.x - p[0])*1000, (self.soln.y - p[1])*1000, (self.soln.z - p[2])*1000]

        # rotate to NEU
        lneu = self.rotate_vector(L)

        # determine the window of the plot, if requested
        if t_win is not None:
            if type(t_win) is tuple:
                # data range, with possibly a final value
                if len(t_win) == 1:
                    t_win = (t_win[0], self.soln.t.max())
            else:
                # approximate a day in fyear
                t_win = (self.soln.t.max() - t_win/365.25, self.soln.t.max())
        #else:
        #    t_win = (self.soln.t.min(), self.soln.t.max())

        # new behaviour: plots the time series even if there is no ETM fit

        if self.A is not None:

            # create the axis
            f, axis = plt.subplots(nrows=3, ncols=2, sharex=True, figsize=(15, 10))  # type: plt.subplots

            # rotate modeled ts
            mneu = self.rotate_vector(m)
            # rotate residuals
            rneu = self.rotate_vector(self.R)

            # ################# FILTERED PLOT #################
            fneu = self.rotate_sigmas(self.factor)*1000

            f.suptitle('Station: %s.%s lat: %8.4f lon: %9.4f\nPPP Completion: %.2f%%\n%s\n%s\nNEU sigmas [mm]: %5.2f %5.2f %5.2f' %
                       (self.NetworkCode, self.StationCode, self.soln.lat, self.soln.lon,
                        self.soln.completion,
                        self.Linear.PrintParams(self.soln.lat, self.soln.lon),
                        self.Periodic.PrintParams(self.soln.lat, self.soln.lon),
                        fneu[0], fneu[1], fneu[2]), fontsize=9, family='monospace')

            table_n, table_e, table_u = self.Jumps.PrintParams(self.soln.lat, self.soln.lon)
            tables = (table_n, table_e, table_u)

            for i, ax in enumerate((axis[0][0], axis[1][0], axis[2][0])):

                # plot filtered time series
                if not residuals:
                    ax.plot(self.soln.t[filt], lneu[i][filt], 'ob', markersize=2)
                    ax.plot(self.soln.ts, mneu[i], 'r')
                    # error bars
                    ax.fill_between(self.soln.ts, mneu[i] - fneu[i] * LIMIT, mneu[i] + fneu[i] * LIMIT, antialiased=True, alpha=0.2)
                else:
                    ax.plot(self.soln.t[filt], rneu[i][filt]*1000, 'ob', markersize=2)
                    # error bars
                    ax.fill_between(self.soln.ts, -fneu[i] * LIMIT, fneu[i] * LIMIT, antialiased=True, alpha=0.2)

                ax.grid(True)

                # labels
                ax.set_ylabel(labels[i])
                p = ax.get_position()
                f.text(0.005, p.y0, tables[i], fontsize=8, family='monospace')

                # window data
                if not residuals:
                    self.set_lims(t_win, plt, ax, lneu[i][filt], filt)
                else:
                    self.set_lims(t_win, plt, ax, rneu[i][filt]*1000, filt)

                # plot jumps
                self.plot_jumps(ax)

            # ################# OUTLIERS PLOT #################

            for i, ax in enumerate((axis[0][1],axis[1][1], axis[2][1])):
                ax.plot(self.soln.t, lneu[i], 'oc', markersize=2)
                ax.plot(self.soln.t[filt], lneu[i][filt], 'ob', markersize=2)
                ax.plot(self.soln.ts, mneu[i], 'r')
                # error bars
                ax.fill_between(self.soln.ts, mneu[i] - fneu[i]*LIMIT, mneu[i] + fneu[i]*LIMIT, antialiased=True, alpha=0.2)

                self.set_lims(t_win, plt, ax, lneu[i])

                ax.set_ylabel(labels[i])

                ax.grid(True)

                self.plot_missing_soln(ax)

            f.subplots_adjust(left=0.16)

        else:

            f, axis = plt.subplots(nrows=3, ncols=1, sharex=True, figsize=(15, 10))  # type: plt.subplots

            f.suptitle('Station: %s.%s lat: %9.4f lon: %9.4f' % (self.NetworkCode, self.StationCode, self.soln.lat, self.soln.lon) +
                       '\nNot enough solutions to fit an ETM.', fontsize=9, family='monospace')

            for i, ax in enumerate((axis[0], axis[1], axis[2])):
                ax.plot(self.soln.t, lneu[i], 'ob', markersize=2)

                ax.set_ylabel(labels[i])

                ax.grid(True)

                self.set_lims(t_win, plt, ax, lneu[i], offset=yoffset)

                self.plot_jumps(ax)

                self.plot_missing_soln(ax)

        if not pngfile:
            plt.show()
        else:
            plt.savefig(pngfile)
            plt.close()

    def plot_hist(self):

        import matplotlib.pyplot as plt
        import matplotlib.mlab as mlab
        from scipy.stats import norm

        L = [self.soln.x, self.soln.y, self.soln.z]

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

    def set_lims(self, t_win, plt, ax, data, filt=None, offset=None):

        if t_win is None:
            # turn on to adjust the limits, then turn off to plot jumps
            ax.autoscale(enable=True, axis='x', tight=True)
            ax.autoscale(enable=False, axis='x', tight=True)
            ax.autoscale(enable=True, axis='y', tight=True)
            ax.autoscale(enable=False, axis='y', tight=True)
        else:
            if t_win[0] == t_win[1]:
                t_win[0] = t_win[0] - 1./365.25
                t_win[1] = t_win[1] + 1./365.25

            plt.xlim(t_win)
            if filt is not None:
                y_lim = (data[np.logical_and(t_win[0] <= self.soln.t[filt], self.soln.t[filt] <= t_win[1])].min(),
                         data[np.logical_and(t_win[0] <= self.soln.t[filt], self.soln.t[filt] <= t_win[1])].max())
            else:
                y_lim = (data[np.logical_and(t_win[0] <= self.soln.t, self.soln.t <= t_win[1])].min(),
                         data[np.logical_and(t_win[0] <= self.soln.t, self.soln.t <= t_win[1])].max())

            if offset is not None:
                ax.set_ylim(ymin=y_lim[0] - offset, ymax=y_lim[1] + offset)
            else:
                ax.set_ylim(ymin=y_lim[0], ymax=y_lim[1])

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
            if jump.year >= self.soln.t.min() and jump.type is not NO_EFFECT:
                # the post-seismic jumps that happened before t.min() should not be plotted
                if jump.T == 0 and jump.type != FRAME_CHANGE:
                    ax.plot((jump.year, jump.year), ax.get_ylim(), 'b:')
                elif jump.T == 0 and jump.type == FRAME_CHANGE:
                    ax.plot((jump.year, jump.year), ax.get_ylim(), ':', color='tab:green')
                else:
                    ax.plot((jump.year, jump.year), ax.get_ylim(), 'r:')

    def todictionary(self, time_series=False):
        # convert the ETM adjustment into a dirtionary
        # optionally, output the whole time series as well

        # start with the parameters
        etm = dict()
        etm['Network'] = self.NetworkCode
        etm['Station'] = self.StationCode
        etm['lat'] = self.soln.lat[0]
        etm['lon'] = self.soln.lon[0]
        etm['Jumps'] = [{'type': jump.type,
                         'year': jump.year,
                         'a': jump.a.tolist(),
                         'b': jump.b.tolist(),
                         'T': jump.T,
                         'sigma_a': jump.sigmaa.tolist(),
                         'sigma_b': jump.sigmab.tolist()}
                         for jump in self.Jumps.table]

        if self.A is not None:

            etm['Linear'] = {'tref': self.Linear.tref,
                             'params': self.Linear.values.tolist(),
                             'sigmas': self.Linear.sigmas.tolist()}

            etm['Periodic'] = {'frequencies': self.Periodic.frequencies,
                               'sin': self.Periodic.sin.tolist(),
                               'cos': self.Periodic.cos.tolist(),
                               'sigma_sin': self.Periodic.sigmasin.tolist(),
                               'sigma_cos': self.Periodic.sigmacos.tolist()}

            etm['unit_variance'] = {'x': self.factor[0], 'y': self.factor[1], 'z': self.factor[2]}

        if time_series:
            ts = dict()
            ts['t'] = self.soln.t.tolist()
            ts['x'] = self.soln.x.tolist()
            ts['y'] = self.soln.y.tolist()
            ts['z'] = self.soln.z.tolist()
            ts['filter'] = np.logical_and(np.logical_and(self.F[0], self.F[1]), self.F[2]).tolist()

            etm['time_series'] = ts

        return etm

    def get_xyz_s(self, year, doy, jmp=None):
        # this function find the requested epochs and returns an X Y Z and sigmas
        # jmp = 'pre' returns the coordinate immediately before a jump
        # jmp = 'post' returns the coordinate immediately after a jump
        # jmp = None returns either the coordinate before or after, depending on the time of the jump.

        # find this epoch in the t vector
        date = pyDate.Date(year=year, doy=doy)
        window = None

        for jump in self.Jumps.table:
            if jump.date == date and jump.type in (ANTENNA_CHANGE, CO_SEISMIC_JUMP_DECAY):
                if np.sqrt(np.sum(np.square(jump.b))) > 0.02:
                    window = jump.date
                    # if no pre or post specified, then determine using the time of the jump
                    if jmp is None:
                        if (jump.date.datetime().hour + jump.date.datetime().minute / 60.0) < 12:
                            jmp = 'post'
                        else:
                            jmp = 'pre'
                    # now use what it was determined
                    if jmp == 'pre':
                        date -= 1
                    else:
                        date += 1

        index = np.where(self.soln.mjd == date.mjd)
        index = index[0]

        s = np.zeros((3, 1))
        x = np.zeros((3, 1))

        dneu = [None, None, None]
        source = '?'
        if index.size:
            # found a valid epoch in the t vector
            # now see if this epoch was filtered
            for i in range(3):
                if i == 0:
                    L = self.soln.x
                elif i == 1:
                    L = self.soln.y
                else:
                    L = self.soln.z

                if self.A is not None:
                    if self.F[i][index]:
                        # the coordinate is good
                        if np.abs(self.R[i][index]) >= 0.005:
                            # do not allow uncertainties lower than 5 mm (it's just unrealistic)
                            s[i,0] = self.R[i][index]
                        else:
                            s[i,0] = 0.005

                        x[i,0] = L[index]
                        source = 'PPP with ETM solution: good'
                    else:
                        # the coordinate is marked as bad
                        # get the requested epoch from the ETM
                        idt = np.argmin(np.abs(self.soln.ts - date.fyear))

                        Ax = np.dot(self.As[idt, :], self.C[i])
                        x[i,0] = Ax
                        # Use the deviation from the ETM to estimate the error (which will be multiplied by 2.5 later)
                        s[i,0] = L[index] - Ax
                        source = 'PPP with ETM solution: filtered'
                else:
                    # no ETM (too few points), but we have a solution for the requested day
                    x[i, 0] = L[index]
                    dneu[i] = 9.99
                    source = 'PPP no ETM solution'

        else:
            if self.A is not None:
                # the coordinate doesn't exist, get it from the ETM
                idt = np.argmin(np.abs(self.soln.ts - date.fyear))
                As = self.As[idt, :]
                source = 'No PPP solution: ETM'

                for i in range(3):
                    x[i, 0] = np.dot(As, self.C[i])
                    # since there is no way to estimate the error,
                    # use the nominal sigma (which will be multiplied by 2.5 later)
                    s[i, 0] = np.std(self.R[i][self.F[i]])
                    dneu[i] = 9.99
            else:
                # no ETM (too few points), get average
                source = 'No PPP solution, no ETM: mean coordinate'
                for i in range(3):
                    if i == 0:
                        x[i, 0] = np.mean(self.soln.x)
                    elif i == 1:
                        x[i, 0] = np.mean(self.soln.y)
                    else:
                        x[i, 0] = np.mean(self.soln.z)
                    # set the uncertainties in NEU by hand
                    dneu[i] = 9.99

        # crude transformation from XYZ to NEU
        if dneu[0] is None:
            R = rotct2lg(self.soln.lat, self.soln.lon)
            sd = np.diagflat(s)
            sneu = np.dot(np.dot(R[:, :, 0], sd), R[:, :, 0].transpose())
            dneu = np.diag(sneu)
            # dneu[0], dneu[1], dneu[2] = ct2lg(s[0],s[1],s[2], self.ppp_soln.lat, self.ppp_soln.lon)

            # careful with zeros in the sittbl. file

        if np.sqrt(np.square(self.Linear.values[1]) +
                   np.square(self.Linear.values[self.Linear.params + 1]) +
                   np.square(self.Linear.values[2*self.Linear.params + 1])) > 0.2:
            sigma_h = 99.9
            sigma_v = 99.9
        else:
            sigma_h = 0.1
            sigma_v = 0.15

        oneu = np.zeros(3)
        # apply floor sigmas
        #if np.abs(dneu[0]) < 0.015:
        oneu[0] = np.sqrt(np.square(dneu[0]) + np.square(sigma_h))
        #if np.abs(dneu[1]) < 0.015:
        oneu[1] = np.sqrt(np.square(dneu[1]) + np.square(sigma_h))
        #if np.abs(dneu[2]) < 0.030:
        oneu[2] = np.sqrt(np.square(dneu[2]) + np.square(sigma_v))

        s = np.row_stack((oneu[0], oneu[1], oneu[2]))

        return x, s, window, source

    def sigmas_neu2xyz(self, sigmas):
        # function to convert a given sigma from NEU to XYZ
        # convert sigmas to XYZ
        R = rotlg2ct(self.soln.lat, self.soln.lon)
        sd = np.diagflat(sigmas)
        sxyz = np.dot(np.dot(R[:, :, 0], sd), R[:, :, 0].transpose())

        return np.diag(sxyz)

    def rotate_vector(self, ecef):

        return ct2lg(ecef[0], ecef[1], ecef[2], self.soln.lat, self.soln.lon)

    def rotate_sigmas(self, ecef):

        R = rotct2lg(self.soln.lat, self.soln.lon)
        sd = np.diagflat(ecef)
        sneu = np.dot(np.dot(R[:, :, 0], sd), R[:, :, 0].transpose())
        dneu = np.diag(sneu)

        return dneu

    @ staticmethod
    def load_params(params, comp, A, L):
        s = []
        ss = []
        j = []
        sj = []
        v = []
        sv = []
        factor = 1
        tref = 0

        for param in params:
            if param['Name'].startswith('lin_' + comp):
                v += [float(param['Value'])]

            if param['Name'].startswith('sig_lin_' + comp):
                sv += [float(param['Value'])]

            if param['Name'].startswith('sincos_' + comp):
                s += [float(param['Value'])]

            if param['Name'].startswith('sig_sincos_' + comp):
                ss += [float(param['Value'])]

            if param['Name'].startswith('jump_' + comp):
                j += [float(param['Value'])]

            if param['Name'].startswith('sig_jump_' + comp):
                sj += [float(param['Value'])]

            if param['Name'].startswith('factor_' + comp):
                factor = [float(param['Value'])]

            if param['Name'].startswith('tref_' + comp):
                # tref are all the same (for all components)
                tref = [float(param['Value'])]

        x = np.array(v + j + s)
        sigma = np.array(sv + sj + ss)

        residuals = L - np.dot(A(constrains=False), x)

        s = np.abs(np.divide(residuals, factor))
        s[s > 40] = 40  # 40 times sigma in 10^(2.5-40) yields 3x10^-38! small enough. Limit s to avoid an overflow
        index = s <= LIMIT

        # determine weights
        f = np.ones((residuals.shape[0],))
        f[s > LIMIT] = 1. / (np.power(10, LIMIT - s[s > LIMIT]))
        # do not allow sigmas > 100 m, which is basically not putting
        # the observation in. Otherwise, due to a model problem
        # (missing jump, etc) you end up with very unstable inversions
        f[f > 100] = 100

        P = np.diag(np.divide(1, np.square(factor * f)))

        return x, sigma, index, residuals, factor, P, tref

    @staticmethod
    def adjust_lsq(Ai, Li):

        A = Ai(constrains=True)
        L = Ai.GetL(Li,constrains=True)

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

        P = Ai.GetP(constrains=True)

        while not cst_pass and iteration <= 10:

            W = np.sqrt(P)
            Aw = np.dot(W, A)
            Lw = np.dot(W, L)

            C = np.linalg.lstsq(Aw, Lw, rcond=-1)[0]

            v = L - np.dot(A, C)

            # unit variance
            So = np.sqrt(np.dot(np.dot(v.transpose(), P), v)/dof)

            x = np.power(So, 2) * dof

            # obtain the overall uncertainty predicted by lsq
            factor = factor * So

            # calculate the normalized sigmas

            s = np.abs(np.divide(v, factor))
            s[s > 40] = 40  # 40 times sigma in 10^(2.5-40) yields 3x10^-38! small enough. Limit s to avoid an overflow

            if x < X2 or x > X1:
                # if it falls in here it's because it didn't pass the Chi2 test
                cst_pass = False

                # reweigh by Mike's method of equal weight until 2 sigma
                f = np.ones((v.shape[0], ))
                f[s > LIMIT] = 1. / (np.power(10, LIMIT - s[s > LIMIT]))
                # do not allow sigmas > 100 m, which is basically not putting
                # the observation in. Otherwise, due to a model problem
                # (missing jump, etc) you end up with very unstable inversions
                f[f > 100] = 100

                P = np.diag(np.divide(1, np.square(factor * f)))

            else:
                cst_pass = True

            iteration += 1

        # some statistics
        SS = np.linalg.inv(np.dot(np.dot(A.transpose(), P), A))

        sigma = So*np.sqrt(np.diag(SS))

        # mark observations with sigma <= LIMIT
        index = Ai.RemoveConstrains(s <= LIMIT)

        v = Ai.RemoveConstrains(v)

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

        ETM.__init__(self, cnn, self.ppp_soln, NetworkCode, StationCode, no_model)

        if self.A is not None:
            # try to load the last ETM solution from the database
            rs = cnn.query('SELECT * FROM etms WHERE "NetworkCode" = \'%s\' '
                           'AND "StationCode" = \'%s\' ORDER BY "Name"' % (NetworkCode, StationCode))

            params = rs.dictresult()
            comp = ['x', 'y', 'z']

            if len(params) > 0 and params[0]['hash'] == self.hash:
                load_from_db = True
            else:
                load_from_db = False

                # purge table
                cnn.query('DELETE FROM etms WHERE "NetworkCode" = \'%s\' AND '
                          '"StationCode" = \'%s\'' % (NetworkCode, StationCode))

            L = [self.ppp_soln.x, self.ppp_soln.y, self.ppp_soln.z]

            for i in range(3):

                if load_from_db:
                    # solution valid, load parameters instead of calculating them
                    x, sigma, index, residuals, factor, P, tref = self.load_params(params, comp[i], self.A, L[i])
                else:
                    x, sigma, index, residuals, factor, P = self.adjust_lsq(self.A, L[i])

                    tref = self.Linear.tref

                # save the parameters in each object
                self.SaveParameters(NetworkCode, StationCode, x, sigma, tref, factor, cnn, comp[i], self.hash, not load_from_db)

                self.C.append(x)
                self.S.append(sigma)
                self.F.append(index)
                self.R.append(residuals)
                self.factor.append(factor)

                self.P.append(P)

            if plotit:
                self.plot()

    def SaveParameters(self, NetworkCode, StationCode, x, sigma, tref, factor, cnn, comp, hash, save_to_db=False):

        _ = self.A

        _.L.LoadParameters(x, sigma, tref, _.L)
        _.J.LoadParameters(x, sigma, _.L, _.J)
        _.P.LoadParameters(x, sigma, _.L, _.J, _.P)

        if save_to_db:
            for i, param in enumerate(_.L.return_xs(x, sigma, _.L)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'lin_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))

                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_lin_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            for i, param in enumerate(_.J.return_xs(x, sigma, _.L, _.J)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'jump_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))

                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_jump_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            for i, param in enumerate(_.P.return_xs(x, sigma, _.L, _.J, _.P)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sincos_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_sincos_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                      '(\'%s\', \'%s\', \'factor_%s\', %f, %i)' % (NetworkCode, StationCode, comp, factor, hash))

            # save the reference fyear
            cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                      '(\'%s\', \'%s\', \'tref_%s\', %f, %i)' % (NetworkCode, StationCode, comp, tref, hash))


class GamitETM(ETM):

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False,
                 no_model=False, gamit_soln=None, project=None):

        if gamit_soln is None:
            rs = cnn.query('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' '
                           'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"' % project)

            self.polyhedrons = rs.dictresult()

            stn_ts = [item for item in self.polyhedrons
                      if item['NetworkCode'] == NetworkCode and item['StationCode'] == StationCode]

            self.gamit_soln = GamitSoln(cnn, stn_ts, NetworkCode, StationCode)

        else:
            # load the GAMIT polyhedrons
            self.gamit_soln = gamit_soln

        ETM.__init__(self, cnn, self.gamit_soln, NetworkCode, StationCode, no_model, frame_changes=False,
                     metadata_jumps=False)

        if self.A is not None:

            comp = ['x', 'y', 'z']
            L = [self.gamit_soln.x, self.gamit_soln.y, self.gamit_soln.z]
            np.savetxt('test.txt', self.A)
            for i in range(3):

                x, sigma, index, residuals, factor, P = self.adjust_lsq(self.A, L[i])

                tref = self.Linear.tref

                self.SaveParameters(NetworkCode, StationCode, x, sigma, tref, factor, cnn, comp[i], self.hash, False)

                self.C.append(x)
                self.S.append(sigma)
                self.F.append(index)
                self.R.append(residuals)
                self.factor.append(factor)

                self.P.append(P)

            if plotit:
                self.plot()

    def SaveParameters(self, NetworkCode, StationCode, x, sigma, tref, factor, cnn, comp, hash, save_to_db=False):

        _ = self.A

        _.L.LoadParameters(x, sigma, tref, _.L)
        _.J.LoadParameters(x, sigma, _.L, _.J)
        _.P.LoadParameters(x, sigma, _.L, _.J, _.P)

        if save_to_db:
            for i, param in enumerate(_.L.return_xs(x, sigma, _.L)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'lin_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))

                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_lin_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            for i, param in enumerate(_.J.return_xs(x, sigma, _.L, _.J)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'jump_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))

                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_jump_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            for i, param in enumerate(_.P.return_xs(x, sigma, _.L, _.J, _.P)):
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sincos_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[0], hash))
                cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                          '(\'%s\', \'%s\', \'sig_sincos_%s_%02i\', %f, %i)' %
                          (NetworkCode, StationCode, comp, i, param[1], hash))

            cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                      '(\'%s\', \'%s\', \'factor_%s\', %f, %i)' % (NetworkCode, StationCode, comp, factor, hash))

            # save the reference fyear
            cnn.query('INSERT INTO etms ("NetworkCode", "StationCode", "Name", "Value", hash) VALUES '
                      '(\'%s\', \'%s\', \'tref_%s\', %f, %i)' % (NetworkCode, StationCode, comp, tref, hash))

    def get_residuals_dict(self, project):
        # this function return the values of the ETM ONLY

        dict_o = []
        if self.A is not None:
            # find this epoch in the t vector
            # negative to use with stacker
            px = np.divide(1, np.sqrt(np.diag(self.P[0])))
            py = np.divide(1, np.sqrt(np.diag(self.P[1])))
            pz = np.divide(1, np.sqrt(np.diag(self.P[2])))

            # dict_o += [{'x': -x, 'y': -y, 'z': -z,
            #             'sigmax': sigx, 'sigmay': sigy, 'sigmaz': sigz,
            #             'NetworkCode': net, 'StationCode': stn, 'Year': year, 'DOY': doy, 'Project': prj}
            #             for x, y, z, sigx, sigy, sigz, net, stn, year, doy, prj in
            #                 zip(self.R[0].tolist(), self.R[1].tolist(), self.R[2].tolist(),
            #                     px.tolist(), py.tolist(), pz.tolist(),
            #                     repeat(self.NetworkCode), repeat(self.StationCode),
            #                     [date.year for date in self.gamit_soln.date],
            #                     [date.doy for date in self.gamit_soln.date],
            #                     repeat(project))]
            dict_o += [(net, stn, prj, -x, -y, -z, sigx, sigy, sigz, year, doy)
                       for x, y, z, sigx, sigy, sigz, net, stn, year, doy, prj in
                       zip(self.R[0].tolist(), self.R[1].tolist(), self.R[2].tolist(),
                           px.tolist(), py.tolist(), pz.tolist(),
                           repeat(self.NetworkCode), repeat(self.StationCode),
                           [date.year for date in self.gamit_soln.date],
                           [date.doy for date in self.gamit_soln.date],
                           repeat(project))]
        else:
            raise pyPPPETMException_NoDesignMatrix('No design matrix available for %s.%s' %
                                                   (self.NetworkCode, self.StationCode))

        return dict_o

