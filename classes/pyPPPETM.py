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
import matplotlib.pyplot as plt
import sys

def ecef2lla(ecefArr):
    # convert ECEF coordinates to LLA
    # test data : test_coord = [2297292.91, 1016894.94, -5843939.62]
    # expected result : -66.8765400174 23.876539914 999.998386689

    x = ecefArr[0]
    y = ecefArr[1]
    z = ecefArr[2]

    a = 6378137
    e = 8.1819190842622e-2

    asq = np.power(a, 2)
    esq = np.power(e, 2)

    b = np.sqrt(asq * (1 - esq))
    bsq = np.power(b, 2)

    ep = np.sqrt((asq - bsq) / bsq)
    p = np.sqrt(np.power(x, 2) + np.power(y, 2))
    th = np.arctan2(a * z, b * p)

    lon = np.arctan2(y, x)
    lat = np.arctan2((z + np.power(ep, 2) * b * np.power(np.sin(th), 3)),
                        (p - esq * a * np.power(np.cos(th), 3)))
    N = a / (np.sqrt(1 - esq * np.power(np.sin(lat), 2)))
    alt = p / np.cos(lat) - N

    lon = lon * 180 / np.pi
    lat = lat * 180 / np.pi

    return np.array([lat]), np.array([lon]), np.array([alt])


def ct2lg(dX, dY, dZ, lat, lon):

    n = dX.size
    R = np.zeros((3, 3, n))

    R[0, 0, :] = -np.multiply(np.sin(np.deg2rad(lat)), np.cos(np.deg2rad(lon)))
    R[0, 1, :] = -np.multiply(np.sin(np.deg2rad(lat)), np.sin(np.deg2rad(lon)))
    R[0, 2, :] = np.cos(np.deg2rad(lat))
    R[1, 0, :] = -np.sin(np.deg2rad(lon))
    R[1, 1, :] = np.cos(np.deg2rad(lon))
    R[1, 2, :] = np.zeros((1, n))
    R[2, 0, :] = np.multiply(np.cos(np.deg2rad(lat)), np.cos(np.deg2rad(lon)))
    R[2, 1, :] = np.multiply(np.cos(np.deg2rad(lat)), np.sin(np.deg2rad(lon)))
    R[2, 2, :] = np.sin(np.deg2rad(lat))

    dxdydz = np.column_stack((np.column_stack((dX, dY)), dZ))

    RR = np.reshape(R[0, :, :], (3, n))
    dx = np.sum(np.multiply(RR, dxdydz.transpose()), axis=0)
    RR = np.reshape(R[1, :, :], (3, n))
    dy = np.sum(np.multiply(RR, dxdydz.transpose()), axis=0)
    RR = np.reshape(R[2, :, :], (3, n))
    dz = np.sum(np.multiply(RR, dxdydz.transpose()), axis=0)

    return dx, dy, dz

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

class PPP_soln():
    """"class to extract the PPP solutions from the database"""

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        # load all the PPP coordinates available for this station
        # exclude ppp solutions in the exclude table and any solution that is more than 100 meters from the auto coord
        ppp = cnn.query(
            'SELECT PPP.* FROM (SELECT p1.*, sqrt((p1."X" - st.auto_x)^2 + (p1."Y" - st.auto_y)^2 + (p1."Z" - st.auto_z)^2) as dist FROM ppp_soln p1 '
            'LEFT JOIN stations st ON p1."NetworkCode" = st."NetworkCode" AND p1."StationCode" = st."StationCode" '
            'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' AND '
            'NOT EXISTS (SELECT * FROM ppp_soln_excl p2'
            '  WHERE p2."NetworkCode" = p1."NetworkCode" AND'
            '        p2."StationCode" = p1."StationCode" AND'
            '        p2."Year"        = p1."Year"        AND'
            '        p2."DOY"         = p1."DOY") ORDER BY "Year", "DOY") as PPP WHERE PPP.dist <= 100 ORDER BY PPP."Year", PPP."DOY"' % (
            NetworkCode, StationCode))

        self.table     = ppp.dictresult()
        self.solutions = len(self.table)

        if self.solutions > 1:
            X = [float(item['X']) for item in self.table]
            Y = [float(item['Y']) for item in self.table]
            Z = [float(item['Z']) for item in self.table]

            T = (pyDate.Date(year=item.get('Year'),doy=item.get('DOY')).fyear for item in self.table)
            MDJ = (pyDate.Date(year=item.get('Year'),doy=item.get('DOY')).mjd for item in self.table)

            self.x = np.array(X)
            self.y = np.array(Y)
            self.z = np.array(Z)
            self.t = np.array(list(T))
            self.mdj = np.array(list(MDJ))

            # continuous time vector for plots
            ts = np.arange(np.min(self.mdj), np.max(self.mdj) + 1, 1)
            ts = np.array([pyDate.Date(mjd=tts).fyear for tts in ts])

            self.ts = ts

            self.lat, self.lon, self.height = ecef2lla([np.mean(self.x).tolist(),np.mean(self.y).tolist(),np.mean(self.z).tolist()])


class Jump():
    """
    Co-seismic or antenna change jump class
    """
    def __init__(self, year, decay, t):
        """"
        Possible types:
            0 = ongoing decay before the start of the data
            1 = Antenna jump with no decay
            2 = Co-seismic jump with decay
        """
        self.a = np.array([]) # log decay amplitude
        self.b = np.array([]) # jump amplitude
        self.T = decay        # relaxation time
        self.year = year      # fyear of jump

        if year <= t.min() and decay == 0:
            # antenna change or some other jump BEFORE the start of the data
            self.type = None
            self.params = 0

        elif year >= t.max():
            # antenna change or some other jump AFTER the end of the data
            self.type   = None
            self.params = 0

        elif year <= t.min() and decay != 0:
            # earthquake before the start of the data, leave the decay but not the jump
            self.type   = 0
            self.params = 1

        elif year > t.min() and year < t.max() and decay == 0:
            self.type   = 1
            self.params = 1

        elif year > t.min() and year < t.max() and decay != 0:
            self.type   = 2
            self.params = 2

    def remove(self):
        # this method will make this jump type = 0 and adjust its params
        self.type = None
        self.params = 0

    def eval(self, t):
        # given a time vector t, return the design matrix column vector(s)

        if self.type is None:
            return np.array([])

        hl = np.zeros((t.shape[0],))
        ht = np.zeros((t.shape[0],))

        if self.type in (0,2):
            hl[t > self.year] = np.log10(1 + (t[t > self.year] - self.year) / self.T)

        if self.type in (1,2):
            ht[t > self.year] = 1

        if np.any(hl) and np.any(ht):
            return np.column_stack((ht, hl))

        elif np.any(hl) and not np.any(ht):
            return hl

        elif not np.any(hl) and np.any(ht):
            return ht

        else:
            return np.array([])


class JumpsTable():
    """"class to determine the jump table based on distance to earthquakes and receiver/antenna changes"""
    def __init__(self, cnn, NetworkCode, StationCode, t=None, add_antenna_jumps=1):

        if t is None:
            ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)
            t = ppp_soln.t

        # station location
        stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

        stn = stn.dictresult()[0]

        # get all the antenna and receiver changes from the station info
        StnInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        # get the earthquakes based on Mike's expression
        jumps = cnn.query('SELECT * FROM earthquakes ORDER BY date')
        jumps = jumps.dictresult()

        eq = [[float(jump.get('lat')), float(jump.get('lon')), float(jump.get('mag')), float(jump.get('date').year), float(jump.get('date').month), float(jump.get('date').day)] for jump in jumps]
        eq = np.array(list(eq))

        dist = distance(float(stn['lon']), float(stn['lat']), eq[:, 1], eq[:, 0])

        m = -0.8717 * (np.log10(dist) - 2.25) + 0.4901 * (eq[:, 2] - 6.6928)
        # build the earthquake jump table
        # remove event events that happened the same day

        eq_jumps = list(set(pyDate.Date(year=eq[0], month=eq[1], day=eq[2]).fyear for eq in eq[m > 0, 3:6]))

        eq_jumps.sort()

        self.table = []
        for i, jump in enumerate(eq_jumps):
            if i < len(eq_jumps)-1 and len(eq_jumps) > 1:
                nxjump = eq_jumps[i+1]
                if jump < t.min() and nxjump > t.min():
                    # if the eq jump occurred before the start date and the next eq jump is within the data, add it
                    # otherwise, we would be adding multiple decays to the beginning of the time series
                    self.table.append(Jump(jump, 0.5, t))

                elif jump >= t.min():
                    # if there is another earthquake within 10 days of this earthquake, i.e.
                    # if eq_jumps[i+1] - jump < 6 days, add an offset but don't allow the log transient
                    # a log transient with less than 6 days if not worth adding the log decay
                    # (which destabilizes the sys. of eq.)
                    if (nxjump - jump)*365 < 10: #or t[np.where((t <= nxjump) & (t > jump))].size < 10:
                        self.table.append(Jump(jump, 0, t))
                    else:
                        self.table.append(Jump(jump, 0.5, t))

            else:
                self.table.append(Jump(jump, 0.5, t))

        # antenna and receiver changes
        if add_antenna_jumps != 0:
            for i, jump in enumerate(StnInfo.records):
                if i > 0:
                    date = pyDate.Date(year=jump.get('DateStart').year, month=jump.get('DateStart').month, day=jump.get('DateStart').day)
                    self.table.append(Jump(date.fyear, 0, t))

        # sort jump table (using the key year)
        self.table.sort(key=lambda jump: jump.year)

        self.lat = float(stn['lat'])
        self.lon = float(stn['lon'])

        # build the design matrix
        self.A = self.GetDesignTs(t)

        if self.A.size:
            self.params = self.A.shape[1]
        else:
            self.params = 0

        if self.A.size:
            # dilution of precision of the adjusted parameters
            if len(self.A.shape) > 1:
                DOP = np.diag(np.linalg.inv(np.dot(self.A.transpose(), self.A)))
                self.constrains = np.zeros((np.argwhere(DOP > 5).size, self.A.shape[1]))
            else:
                DOP = np.diag(np.linalg.inv(np.dot(self.A[:,np.newaxis].transpose(), self.A[:,np.newaxis])))
                self.constrains = np.zeros((np.argwhere(DOP > 5).size,1))

            # apply constrains
            if np.any(DOP > 5):
                for i, dop in enumerate(np.argwhere(DOP > 5)):
                    self.constrains[i, dop] = 1
        else:
            self.constrains = np.array([])


    def GetDesignTs(self, t):

        A = np.array([])

        # get the design matrix for the jump table
        for jump in self.table:
            if not jump.type is None:
                a = jump.eval(t)

                if a.size:
                    if A.size:
                        # if A is not empty, verify that this jump will not make the matrix singular
                        tA = np.column_stack((A, a))

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
                A = A[:,np.newaxis]

        return A

    def LoadParameters(self, C):

        s = 0
        for jump in self.table:
            if not jump.type is None:
                if jump.params == 1 and jump.T != 0:
                    jump.a = np.append(jump.a, C[s:s + 1])

                elif jump.params == 1 and jump.T == 0:
                    jump.b = np.append(jump.b, C[s:s + 1])

                elif jump.params == 2:
                    jump.b = np.append(jump.b, C[s:s + 1])
                    jump.a = np.append(jump.a, C[s + 1:s + 2])

                s = s + jump.params

    def PrintParams(self, lat, lon):

        output_n = ['Year     Relx    [mm]']
        output_e = ['Year     Relx    [mm]']
        output_u = ['Year     Relx    [mm]']

        for jump in self.table:

            a = [None, None, None]
            b = [None, None, None]

            if not jump.type is None:

                if (jump.params == 1 and jump.T != 0) or jump.params == 2 :
                    a[0], a[1], a[2] = ct2lg(jump.a[0], jump.a[1], jump.a[2], lat, lon)

                if (jump.params == 1 and jump.T == 0) or jump.params == 2 :
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


class Periodic():
    """"class to determine the periodic terms to be included in the ETM"""

    def __init__(self, cnn=None, NetworkCode=None, StationCode=None, t=None):

        if t is None:
            ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)
            t = ppp_soln.t

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

        # variables to store the periodic amplitudes
        self.sin = np.zeros([])
        self.cos = np.array([])

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

    def LoadParameters(self, C):
        # load the amplitude parameters
        self.sin = np.append(self.sin, C[0::2])
        self.cos = np.append(self.cos, C[1::2])

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


class Linear():
    """"class to build the linear portion of the design matrix"""

    def __init__(self, cnn=None, NetworkCode=None, StationCode=None, tref=0, t=None):

        self.values = np.array([])

        if t is None:
            ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)
            t = ppp_soln.t

        # t ref (just the beginning of t vector)
        if tref==0:
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

    def LoadParameters(self, C):

        self.values = np.append(self.values, np.array([C[0], C[1]]))

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

        obj[:,0:Linear.params] = Linear.A

        if Jumps.params > 0:
            obj[:, Linear.params:Linear.params + Jumps.params] = Jumps.A

        if Periodic.params > 0:
            obj[:, Linear.params + Jumps.params:Linear.params + Jumps.params + Periodic.params] = Periodic.A

        # set the new attributes to the values passed
        obj.L = Linear
        obj.J = Jumps
        obj.P = Periodic
        # save the number of total parameters
        obj.params = Linear.params + Jumps.params + Periodic.params

        # Finally, we must return the newly created object:
        return obj

    def __call__(self, ts=None, constrains=False):

        if ts is None:
            if constrains:
                if self.J.constrains.size:
                    A = np.resize(self, (self.shape[0] + self.J.constrains.shape[0], self.shape[1]))
                    A[-self.J.constrains.shape[0] - 1:-1,self.L.params:self.L.params + self.J.params] = self.J.constrains
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
                return np.resize(L, (L.shape[0] + self.J.constrains.shape[0]))

            else:
                return L

        else:
            return L

    def GetP(self, constrains=False):
        # return a weight matrix full of ones with or without the extra elements for the constrains
        return np.diag(np.ones((self.shape[0]))) if not constrains else np.diag(np.ones((self.shape[0] + self.J.constrains.shape[0])))

    def SaveParameters(self, x):

        self.L.LoadParameters(x[0:self.L.params])
        self.J.LoadParameters(x[self.L.params:self.L.params + self.J.params])
        self.P.LoadParameters(x[self.L.params + self.J.params:self.L.params + self.J.params + self.P.params])

    def RemoveConstrains(self, V):
        # remove the constrains to whatever vector is passed
        if self.J.constrains.size:
            return V[0:-self.J.constrains.shape[0]]
        else:
            return V


class ETM():

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False):

        self.C = []
        self.S = []
        self.F = []
        self.R = []
        self.factor = []
        self.A = None

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        # load all the PPP coordinates available for this station
        # exclude ppp solutions in the exclude table and any solution that is more than 100 meters from the auto coord
        self.ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)

        # to work locally
        ppp = self.ppp_soln

        # anything less than four is not worth it
        if ppp.solutions > 4:

            # save the function objects
            self.Periodic = Periodic(t=ppp.t)
            self.Jumps    = JumpsTable(cnn, NetworkCode, StationCode, ppp.t, add_antenna_jumps=self.Periodic.params)
            self.Linear   = Linear(t=ppp.t)

            # to obtain the parameters
            self.A = Design(self.Linear, self.Jumps, self.Periodic)

            # check if problem can be solved!
            if self.A.shape[1] > ppp.solutions:
                self.A = None
                return

            self.As = self.A(ppp.ts)

            for i in range(3):

                if i == 0:
                    L = ppp.x
                elif i == 1:
                    L = ppp.y
                else:
                    L = ppp.z

                x, sigma, index, residuals, f, P = self.adjust_lsq(self.A, L)

                # save the parameters in each object
                self.A.SaveParameters(x)

                self.C.append(x)
                self.S.append(sigma)
                self.F.append(index)
                self.R.append(residuals)
                self.factor.append(f)
                self.P = P

            if plotit:
                self.plot()

    def plot(self, file=None):

        if self.A is not None:
            f, axis = plt.subplots(nrows=3, ncols=2, sharex=True, figsize=(15,10)) # type: plt.subplots
            f.suptitle('Station: ' + self.NetworkCode + '.' + self.StationCode + '\n' +
                       self.Linear.PrintParams(self.ppp_soln.lat, self.ppp_soln.lon) + '\n' +
                       self.Periodic.PrintParams(self.ppp_soln.lat, self.ppp_soln.lon), fontsize=9, family='monospace')

            table_n, table_e, table_u = self.Jumps.PrintParams(self.ppp_soln.lat, self.ppp_soln.lon)

            filt = self.F[0] * self.F[1] * self.F[2]
            m = []
            for i in range(3):
                if i == 0:
                    L = self.ppp_soln.x
                elif i == 1:
                    L = self.ppp_soln.y
                else:
                    L = self.ppp_soln.z

                m.append(np.mean(L[filt]))

            oneu = ct2lg(self.ppp_soln.x[filt] - m[0], self.ppp_soln.y[filt] - m[1], self.ppp_soln.z[filt] - m[2], self.ppp_soln.lat, self.ppp_soln.lon)
            rneu = ct2lg(self.ppp_soln.x - m[0], self.ppp_soln.y - m[1], self.ppp_soln.z - m[2], self.ppp_soln.lat, self.ppp_soln.lon)
            tneu = ct2lg(np.dot(self.As, self.C[0]) - m[0], np.dot(self.As, self.C[1]) - m[1], np.dot(self.As, self.C[2]) - m[2], self.ppp_soln.lat, self.ppp_soln.lon)

            for i, ax in enumerate((axis[0][0],axis[1][0], axis[2][0])):
                ax.plot(self.ppp_soln.t[filt], oneu[i], 'ob', markersize=2)
                ax.plot(self.ppp_soln.ts, tneu[i], 'r')
                ax.autoscale(enable=True, axis='x', tight=True)
                ax.autoscale(enable=True, axis='y', tight=True)

                if i == 0:
                    ax.set_ylabel('North [m]')
                    p = ax.get_position()
                    f.text(0.005, p.y0, table_n, fontsize=8, family='monospace')
                elif i == 1:
                    ax.set_ylabel('East [m]')
                    p = ax.get_position()
                    f.text(0.005, p.y0, table_e, fontsize=8, family='monospace')
                elif i == 2:
                    ax.set_ylabel('Up [m]')
                    p = ax.get_position()
                    f.text(0.005, p.y0, table_u, fontsize=8, family='monospace')

                ax.grid(True)
                for jump in self.Jumps.table:
                    if jump.year >= self.ppp_soln.t.min() and not jump.type is None:
                        # the post-seismic jumps that happened before t.min() should not be plotted
                        if jump.T == 0:
                            ax.plot((jump.year, jump.year), ax.get_ylim(), 'b:')
                        else:
                            ax.plot((jump.year, jump.year), ax.get_ylim(), 'r:')

            for i, ax in enumerate((axis[0][1],axis[1][1], axis[2][1])):
                ax.plot(self.ppp_soln.t, rneu[i], 'oc', markersize=2)
                ax.plot(self.ppp_soln.t[filt], oneu[i], 'ob', markersize=2)
                ax.plot(self.ppp_soln.ts, tneu[i], 'r')
                ax.autoscale(enable=True, axis='x', tight=True)
                ax.autoscale(enable=True, axis='y', tight=True)

                if i == 0:
                    ax.set_ylabel('North [m]')
                elif i == 1:
                    ax.set_ylabel('East [m]')
                elif i == 2:
                    ax.set_ylabel('Up [m]')

                ax.grid(True)
                for jump in self.Jumps.table:
                    if jump.year >= self.ppp_soln.t.min() and not jump.type is None:
                        # the post-seismic jumps that happened before t.min() should not be plotted
                        if jump.T == 0:
                            ax.plot((jump.year, jump.year), ax.get_ylim(), 'b:')
                        else:
                            ax.plot((jump.year, jump.year), ax.get_ylim(), 'r:')

            f.subplots_adjust(left=0.16)

            if not file:
                plt.show()
            else:
                plt.savefig(file)
                plt.close()

    def todictionary(self, time_series=False):
        # convert the ETM adjustment into a dirtionary
        # optionally, output the whole time series as well

        # start with the parameters
        etm = dict()
        etm['Linear'] = {'tref': self.Linear.tref, 'params': self.Linear.values.tolist()}
        etm['Jumps'] = [{'type':jump.type, 'year': jump.year, 'a': jump.a.tolist(), 'b': jump.b.tolist(), 'T': jump.T} for jump in self.Jumps.table]
        etm['Periodic'] = {'frequencies': self.Periodic.frequencies, 'sin': self.Periodic.sin.tolist(), 'cos': self.Periodic.cos.tolist()}

        if time_series:
            ts = dict()
            ts['t'] = self.ppp_soln.t.tolist()
            ts['x'] = self.ppp_soln.x.tolist()
            ts['y'] = self.ppp_soln.y.tolist()
            ts['z'] = self.ppp_soln.z.tolist()

            etm['time_series'] = ts

        return etm

    def get_xyz_s(self, year, doy):
        # this function find the requested epochs and returns an X Y Z and sigmas
        # find this epoch in the t vector
        date = pyDate.Date(year=year,doy=doy)

        index, _ = np.where(self.ppp_soln.mdj == date.mjd)

        s = np.zeros((3, 1))
        x = np.zeros((3, 1))

        if index:
            # found a valid epoch in the t vector
            # now see if this epoch was filtered
            for i in range(3):
                if i == 0:
                    L = self.ppp_soln.x
                elif i == 1:
                    L = self.ppp_soln.y
                else:
                    L = self.ppp_soln.z

                if self.F[i][index]:
                    # the coordinate is good
                    if self.R[i][index] >= 0.005:
                        # do not allow uncertainties lower than 5 mm
                        s[i,0] = self.R[i][index]
                    else:
                        s[i,0] = 0.005

                    x[i,0] = L[index]
                else:
                    # the coordinate is marked as bad
                    idt = np.argmin(np.abs(self.ppp_soln.ts - date.fyear))

                    Ax = np.dot(self.A()[idt, :], self.C[i])
                    x[i,0] = Ax
                    # since there is no way to estimate the error, use 10 cm (which will be multiplied by 2.5 later)
                    s[i,0] = L[index] - Ax
        else:
            # the coordinate doesn't exist, get it from the ETM
            idt = np.argmin(np.abs(self.ppp_soln.ts - date.fyear))

            for i in range(3):
                x[i, 0] = np.dot(self.A()[idt, :], self.C[i])
                # since there is no way to estimate the error,
                # use the nominal sigma (which will be multiplied by 2.5 later)
                s[i, 0] = np.std(self.R[i][self.F[i]])

        # crude transformation from XYZ to NEU
        dn,de,du = ct2lg(s[0],s[1],s[2], self.ppp_soln.lat, self.ppp_soln.lon)

        # careful with zeros in the sittbl. file
        if np.abs(dn) < 0.005:
            dn = 0.005
        if np.abs(de) < 0.005:
            de = 0.005
        if np.abs(du) < 0.005:
            du = 0.005

        s = np.row_stack((np.abs(dn),np.abs(de),np.abs(du)))

        return x, s

    def adjust_lsq(self, Ai, Li):

        limit = 2.5

        A = Ai(constrains=True)
        L = Ai.GetL(Li,constrains=True)

        cst_pass = False
        iteration = 0
        factor = 1
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

            C = np.linalg.lstsq(Aw, Lw)[0]

            v = L - np.dot(A, C)

            # unit variance
            So = np.sqrt(np.dot(np.dot(v.transpose(),P),v)/dof)

            x = np.power(So,2) * dof

            # obtain the overall uncertainty predicted by lsq
            factor = factor * So

            # calculate the normalized sigmas
            s = np.abs(np.divide(v, factor))
            s[s > 40] = 40 # 40 times sigma in 10^(2.5-40) yields 3x10^-38! small enough. Limit s to avoid an overflow

            if x < X2 or x > X1:
                # if it falls in here it's because it didn't pass the Chi2 test
                cst_pass = False

                # reweigh by Mike's method of equal weight until 2 sigma
                f = np.ones((v.shape[0],))
                f[s > limit] = 1. /(np.power(10,limit - s[s > limit]))
                # do not allow sigmas > 100 m, which is basicaly not putting
                # the observation in. Otherwise, due to a model problem
                # (missing jump, etc) you end up with very unstable inversions
                f[f > 100] = 100

                P = np.diag(np.divide(1,np.square(factor * f)))

            else:
                cst_pass = True

            iteration += 1

        # some statistics
        sigma = Ai.RemoveConstrains(1/np.sqrt(np.diag(P)))

        # mark observations with sigma <= limit
        index = Ai.RemoveConstrains(s <= limit)

        v = Ai.RemoveConstrains(v)

        return C, sigma, index, v, factor, P

    def chi2inv(self, chi, df):
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
