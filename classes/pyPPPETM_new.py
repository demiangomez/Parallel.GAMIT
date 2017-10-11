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

    def __init__(self, year, decay, t):
        """"
        Possible types:
            0 = ongoing decay before the start of the data
            1 = Antenna jump with no decay
            2 = Co-seismic jump with decay
        """
        self.a = None      # log decay amplitude
        self.b = None      # jump amplitude
        self.T = decay     # relaxation time
        self.year = year   # fyear of jump

        if year <= t.min() and decay == 0:
            # antenna change or some other jump BEFORE the start of the data
            self.type = None

        elif year > t.max():
            # antenna change or some other jump AFTER the end of the data
            self.type = None

        elif year <= t.min() and decay != 0:
            # earthquake before the start of the data, leave the decay but not the jump
            self.type = 0

        elif year > t.min() and year <= t.max() and decay == 0:
            self.type = 1

        elif year > t.min() and year <= t.max() and decay != 0:
            self.type = 2

    def eval(self, t):
        # given a time vector t, return the design matrix column vector(s)

        if self.type is None:
            return np.array([])

        hl = np.zeros((t.shape[0],))
        ht = np.zeros((t.shape[0],))

        if self.type in (0,2):
            hl[t >= self.year] = np.log10(1 + (t[t >= self.year] - self.year) / self.T)

        if self.type in (1,2):
            ht[t >= self.year] = 1

        return np.append(ht,hl) if np.any(hl) else ht


class JumpsTable():
    """"class to determine the jump table based on distance to earthquakes and receiver/antenna changes"""
    def __init__(self, cnn, NetworkCode, StationCode):

        # station location
        stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

        stn = stn.dictresult()[0]

        # get all the antenna and receiver changes from the station info
        StnInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        # get the earthquakes based on Mike's expression
        jumps = cnn.query('SELECT * FROM earthquakes')
        jumps = jumps.dictresult()

        eq = [[float(jump.get('lat')), float(jump.get('lon')), float(jump.get('mag')), float(jump.get('date').year), float(jump.get('date').month), float(jump.get('date').day)] for jump in jumps]
        eq = np.array(list(eq))

        dist = self.distance(float(stn['lon']), float(stn['lat']), eq[:, 1], eq[:, 0])

        m = -0.8717 * (np.log10(dist) - 2.25) + 0.4901 * (eq[:, 2] - 6.6928)
        # build the earthquake jump table
        # remove event events that happened the same day

        j = list(set(pyDate.Date(year=eq[0], month=eq[1], day=eq[2]).fyear for eq in eq[m > 0, 3:6]))

        self.jump_table = [[jump, 0.5] for jump in j]

        # antenna and receiver changes
        for i, jump in enumerate(StnInfo.records):
            if i > 0:
                date = pyDate.Date(year=jump.get('DateStart').year, month=jump.get('DateStart').month,
                                   day=jump.get('DateStart').day)
                self.jump_table.append([date.fyear, 0])

        # sort jump table
        self.jump_table.sort()

        self.np_jumps = np.array(self.jump_table)
        self.lat = float(stn['lat'])
        self.lon = float(stn['lon'])

    def distance(self, lon1, lat1, lon2, lat2):
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

        self.terms = self.frequencies * 2

        return

    def GetDesignTs(self, ts):

        if self.frequencies == 0:
            # no adjustment of periodic terms
            return np.array([])
        elif self.frequencies == 2:
            return np.array([sin(2 * pi * ts), cos(2 * pi * ts), sin(4 * pi * ts), cos(4 * pi * ts)]).transpose()
        elif self.frequencies == 1:
            return np.array([sin(2 * pi * ts), cos(2 * pi * ts)]).transpose()


class Linear():
    """"class to build the linear portion of the design matrix"""

    def __init__(self, cnn=None, NetworkCode=None, StationCode=None, tref=0, t=None):

        self.c = np.array([])
        self.v = np.array([])

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

    def GetDesignTs(self, ts):

        return np.column_stack((np.ones((ts.size, 1)), (ts - self.tref)))

    def LoadParameters(self, C, component):

        self.c = np.append(self.c, C[0])
        self.v = np.append(self.v, C[1])

    def PrintParams(self, lat, lon):

        vn, ve, vu = ct2lg(self.v[0], self.v[1], self.v[2], lat, lon)

        return 'Velocity N: %.2f E: %.2f U: %.2f [mm/yr]' % (vn[0]*1000.0, ve[0]*1000.0, vu[0]*1000.0)

class Jumps_co_lg():
    """"class to determine the co-seismic/antenna changes jumps and logaritmic decays"""

    def __init__(self, cnn=None, NetworkCode=None, StationCode=None, jumps=None, t=None):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        self.jumps = np.array([])
        self.A     = np.array([])

        self.offsets        = []
        self.log_amplitudes = []

        self.jump_lg = 0
        self.jump_co = 0

        if t is None:
            ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)

            t = ppp_soln.t

        if jumps is None:
            jumps = JumpsTable(cnn, NetworkCode, StationCode).np_jumps

        if jumps.size > 0:
            # remove jumps before and after the start of the data if they are just co-seismic of antenna changes (with no data)
            jumps = np.delete(jumps, np.where((jumps[:, 1] == 0) & ((jumps[:, 0] < t.min()) | (jumps[:, 0] > t.max()))), axis=0)
            # remove log decays that happened after max(t)
            jumps = np.delete(jumps, np.where((jumps[:, 1] != 0) & (jumps[:, 0] > t.max())), axis=0)

            # log decays < t(start) are more complicated. There are a few
            # possibilities:
            # 1) The jump happened before the data started, but the decay
            # will continue. The decay needs to be added but not the jump
            # 2) Idem before but the decay is stopped by another decay that
            # happened < t(start) => remove all together
            #    find all jumps < min(t)
            jlog_b4_start = jumps[(jumps[:, 1] != 0) & (jumps[:, 0] < t.min())]
            # delete everything < jlog_b4_start[-1]
            if jlog_b4_start.size > 1:
                # only enter here if there is more than one jump
                jumps = np.delete(jumps, np.where((jumps[:, 1] != 0) & (jumps[:, 0] < jlog_b4_start[-1, 0])),
                                     axis=0)

            # heavy-side functions
            ht = np.zeros((t.shape[0], jumps.shape[0]))

            for i, jump in enumerate(jumps):
                # the jumps has to be within the t range to be applied
                if jump[0] > t.min() and jump[0] < t.max():
                    ht[t>= jump[0], i] = 1

                    # if 2 or more jumps happen inside a gap, the (t >= Ht(i,1))
                    # will return identical columns creating a singular matrix.
                    # Verify that the new column is different than the rest
                    if i > 0:
                        for j in range(i):
                            # compare col j with col i
                            if np.sum(np.logical_xor(ht[:, j], ht[:, i])) < 2:
                                # identical columns (oh, well, only different by 2 elements)
                                # remove column j
                                ht[:, i] = 0
                                jumps[j, :] = 0

            # loop over the log decays
            hl = np.zeros((t.shape[0], jumps[jumps[:, 1] != 0].shape[0]))

            for i, jump in enumerate(jumps[jumps[:, 1] != 0]):

                if jump[1] != 0:
                    hl[t >= jump[0], i] = np.log10(1 + (t[t >= jump[0]] - jump[0]) / jump[1])

                    # check for previous log decays. Stop them if necessary
                    if i > 0:
                        for j in range(i):
                            hl[t >= jump[0], j] = 0

                            if np.sum(hl[:, j]) == 0:
                                # no data to constrain this decay, remove from jumps all together
                                # log decay cannot be constrained by data
                                # removing this jump allows to use this function with a full vector is time to get
                                # the same design matrix as with the observation vector
                                k = np.where(jumps[:, 0] == jumps[jumps[:, 1] != 0, 0][j])
                                jumps[k, :] = 0

            # remove any cols will all zeros
            ht = ht[:, (ht != 0).sum(axis=0) > 0]
            hl = hl[:, (hl != 0).sum(axis=0) > 0]

            self.jumps = jumps[jumps[:, 0] != 0, :]

            self.A = np.column_stack((ht, hl))

            self.jump_count = ht.shape[1] + hl.shape[1]
            self.jump_lg    = hl.shape[1]
            self.jump_co    = ht.shape[1]

    def GetDesignTs(self, ts):

        return Jumps_co_lg(jumps=self.jumps, t=ts).A

    def LoadParameters(self, C):

        # check what is the
        self.offsets.append(C[2:self.jump_co])
        self.log_amplitudes.append(C[2+self.jump_co:self.jump_lg])

class ETM():

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False):

        self.C = []
        self.S = []
        self.F = []
        self.D = []
        self.factor = []
        self.A = None
        self.jump_table = None

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode

        # load all the PPP coordinates available for this station
        # exclude ppp solutions in the exclude table and any solution that is more than 100 meters from the auto coord
        self.ppp_soln = PPP_soln(cnn, NetworkCode, StationCode)

        # to work locally
        ppp = self.ppp_soln

        if ppp.solutions > 1:

            self.jump_table = JumpsTable(cnn, NetworkCode, StationCode)

            linear   = Linear(t=ppp.t)
            jumps    = Jumps_co_lg(jumps=self.jump_table.np_jumps,t=ppp.t)
            periodic = Periodic(t=ppp.t)

            # replace the numpy jumps
            self.jump_table.np_jumps = jumps.jumps

            # save the function objects
            self.linear   = linear
            self.periodic = periodic
            self.jumps_lg = jumps

            # to obtain the parameters
            self.A = np.column_stack((linear.A, jumps.A))  if jumps.A.size else linear.A
            self.A = np.column_stack((self.A, periodic.A)) if periodic.A.size else self.A

            self.As = np.column_stack((linear.GetDesignTs(ppp.ts), jumps.GetDesignTs(ppp.ts)))  if jumps.GetDesignTs(ppp.ts).size else linear.GetDesignTs(ppp.ts)
            self.As = np.column_stack((self.As, periodic.GetDesignTs(ppp.ts))) if periodic.GetDesignTs(ppp.ts).size else self.As

            for i in range(3):
                P = np.diag(np.ones(self.A.shape[0]))

                if i == 0:
                    L = ppp.x
                elif i == 1:
                    L = ppp.y
                else:
                    L = ppp.z

                x, sigma, index, dev, f, P = self.adjust_lsq(self.A, P, L)

                # save the parameters in each object
                self.jumps_lg.LoadParameters(x)
                self.linear.LoadParameters(x,i)

                self.C.append(x)
                self.S.append(sigma)
                self.F.append(index)
                self.D.append(dev)
                self.factor.append(f)
                self.P = P

            if plotit:
                self.plot()

    def plot(self, file=None):

        if self.A is not None:
            f, axis = plt.subplots(nrows=3, ncols=2, sharex=True, figsize=(15,10)) # type: plt.subplots
            f.suptitle('Station: ' + self.NetworkCode + '.' + self.StationCode + '\n' +
                       self.linear.PrintParams(self.ppp_soln.lat, self.ppp_soln.lon))

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
                elif i == 1:
                    ax.set_ylabel('East [m]')
                elif i == 2:
                    ax.set_ylabel('Up [m]')

                ax.grid(True)
                for j in self.jump_table.np_jumps:
                    if j[0] >= self.ppp_soln.t.min():
                        # the post-seismic jumps that happened before t.min() should not be plotted
                        if j[1] == 0:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'b:')
                        else:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'r:')

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
                for j in self.jump_table.np_jumps:
                    if j[0] >= self.ppp_soln.t.min():
                        # the post-seismic jumps that happened before t.min() should not be plotted
                        if j[1] == 0:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'b:')
                        else:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'r:')

            if not file:
                plt.show()
            else:
                plt.savefig(file)
                plt.close()


    def get_xyz_s(self, year, doy):
        # this function find the requested epochs and returns an X Y Z and sigmas
        # find this epoch in the t vector
        date = pyDate.Date(year=year,doy=doy)

        index, _ = np.where(self.ppp_soln.t == date.fyear)

        s = np.zeros((3, 1))
        x = np.zeros((3, 1))

        if index:
            # found a valid epoch in the t vector
            # now see if this epoch was filtered
            for i in range(3):
                if self.F[i][index]:
                    # the coordinate is good
                    if self.D[i][index] >= 0.005:
                        # do not allow uncertainties lower than 5 mm
                        s[i,0] = self.D[i][index]
                    else:
                        s[i,0] = 0.005

                    x[i,0] = self.L[index,i]
                else:
                    # the coordinate is marked as bad
                    idt = np.argmin(np.abs(self.ts - date.fyear))

                    x[i,0] = np.dot(self.A[idt,:],self.C[i])
                    # since there is no way to estimate the error, use 10 cm (which will be multiplied by 2.5 later)
                    s[i,0] = 0.1
        else:
            # the coordinate doesn't exist, get it from the ETM
            idt = np.argmin(np.abs(self.ts - date.fyear))

            for i in range(3):
                x[i, 0] = np.dot(self.A[idt, :], self.C[i])
                # since there is no way to estimate the error, use 10 cm (which will be multiplied by 2.5 later)
                s[i, 0] = 0.1

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

    def adjust_lsq(self, Ai, Pi, Li):

        limit = 2.5

        A = Ai
        L = Li

        cst_pass = False
        iteration = 0
        factor = 1
        dof = (Ai.shape[0] - Ai.shape[1])
        X1 = chi2.ppf(1 - 0.05 / 2, dof)
        X2 = chi2.ppf(0.05 / 2, dof)

        s = np.array([])
        v = np.array([])
        C = np.array([])

        while not cst_pass and iteration <= 10:

            # REBUILD the P matrix. Inside the loop to reweigh after adjustment
            P = Pi

            W = np.sqrt(P)
            Aw = np.dot(W, A)
            Lw = np.dot(W, L)

            C = np.linalg.lstsq(Aw, Lw)[0]

            v = Li - np.dot(Ai, C)

            # unit variance
            So = np.sqrt(np.dot(np.dot(v.transpose(),Pi),v)/dof)

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

                Pi = np.diag(np.divide(1,np.square(factor * f)))

            else:
                cst_pass = True

            iteration += 1

        # some statistics
        sigma = 1/np.sqrt(np.diag(Pi))

        # mark observations with sigma <= limit
        index = s <= limit

        return C, sigma, index, v, factor, Pi

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
