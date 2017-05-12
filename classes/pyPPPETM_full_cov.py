"""
Project: Parallel.Archive
Date: 3/3/17 11:27 AM
Author: Demian D. Gomez
"""

import numpy
import pyStationInfo
import pyDate
from numpy import sin
from numpy import cos
from numpy import pi
from scipy.stats import chi2

class ETM():

    def __init__(self, cnn, NetworkCode, StationCode, plotit=False):

        self.jump_table = []
        # load all the PPP coordinates available for this station
        # exclude ppp solutions in the exclude table and any solution that is more than 100 meters from the auto coord
        ppp = cnn.query('SELECT PPP.* FROM (SELECT p1.*, sqrt((p1."X" - st.auto_x)^2 + (p1."Y" - st.auto_y)^2 + (p1."Z" - st.auto_z)^2) as dist FROM ppp_soln p1 '
                        'LEFT JOIN stations st ON p1."NetworkCode" = st."NetworkCode" AND p1."StationCode" = st."StationCode" '
                        'WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\' AND '
                        'NOT EXISTS (SELECT * FROM ppp_soln_excl p2'
                        '  WHERE p2."NetworkCode" = p1."NetworkCode" AND'
                        '        p2."StationCode" = p1."StationCode" AND'
                        '        p2."Year"        = p1."Year"        AND'
                        '        p2."DOY"         = p1."DOY") ORDER BY "Year", "DOY") as PPP WHERE PPP.dist <= 100' % (NetworkCode, StationCode))

        ppp = ppp.dictresult()
        # take the first PPP XYZ ccordinate (here we assume that all wrong coordinates are already out)
        xyz = [ppp[0].get('X'), ppp[0].get('Y'), ppp[0].get('Z')]

        # get all the antenna and receiver changes from the station info
        StnInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)

        # get the earthquakes based on Mike's expression
        jumps = cnn.query('SELECT * FROM earthquakes')
        jumps = jumps.dictresult()

        # station lat lon
        self.slat, self.slon, _ = self.ecef2lla(xyz)
        eq = [[float(jump.get('lat')), float(jump.get('lon')), float(jump.get('mag')), float(jump.get('date').year), float(jump.get('date').month), float(jump.get('date').day)] for jump in jumps]
        eq = numpy.array(list(eq))

        dist = self.distance(self.slon, self.slat, eq[:,1], eq[:,0])
        m = -0.8717 * (numpy.log10(dist) - 2.25) + 0.4901 * (eq[:,2] - 6.6928)
        # build the earthquake jump table
        self.jump_table = [[pyDate.Date(year=eq[0], month=eq[1], day=eq[2]).fyear, 0.5] for eq in eq[m > 0,3:6]]

        # antenna and receiver changes
        for i, jump in enumerate(StnInfo.records):
            if i > 0:
                date = pyDate.Date(year=jump.get('DateStart').year, month=jump.get('DateStart').month, day=jump.get('DateStart').day)
                self.jump_table.append([date.fyear, 0])

        # sort jump table
        self.jump_table.sort()

        np_jumps = numpy.array(self.jump_table)

        # estimate the ETM parameters
        fyr = (pyDate.Date(year=item.get('Year'),doy=item.get('DOY')).fyear for item in ppp)
        t = numpy.array(list(fyr))
        t.sort()
        t = t[:,numpy.newaxis]

        # instead of doing:
        #ts = numpy.arange(t.min(), t.max(), 1 / 365.)
        # use MJD to prevent problems with leap years
        ts = numpy.arange(pyDate.Date(fyear=t.min()).mjd, pyDate.Date(fyear=t.max()).mjd+1, 1)
        ts = numpy.array([pyDate.Date(mjd=tts).fyear for tts in ts])
        ts = ts[:,numpy.newaxis]

        Ao, p_jumps, const_h, const_s = self.design_matrix(t, np_jumps)
        As, _, _, _                  = self.design_matrix(ts, p_jumps)

        # build the hypermatrix with all the axis together
        Am = numpy.zeros((Ao.shape[0] * 3, Ao.shape[1] * 3))

        Am[0:Ao.shape[0], 0:Ao.shape[1]] = Ao
        Am[Ao.shape[0]:Ao.shape[0] * 2, Ao.shape[1]:Ao.shape[1]*2] = Ao
        Am[Ao.shape[0] * 2:Ao.shape[0] * 3, Ao.shape[1] * 2:Ao.shape[1] * 3] = Ao

        sigmax  = [float(item['sigmax' ]) for item in ppp]
        sigmay  = [float(item['sigmay' ]) for item in ppp]
        sigmaz  = [float(item['sigmaz' ]) for item in ppp]
        sigmaxy = [float(item['sigmaxy']) for item in ppp]
        sigmaxz = [float(item['sigmaxz']) for item in ppp]
        sigmayz = [float(item['sigmayz']) for item in ppp]

        P = numpy.diag(numpy.square(sigmax + sigmay + sigmaz))

        P[0:Ao.shape[0], Ao.shape[0]:Ao.shape[0] * 2] = numpy.diag(numpy.multiply(sigmaxy, numpy.multiply(sigmax,sigmay)))
        P[0:Ao.shape[0], Ao.shape[0] * 2:Ao.shape[0] * 3] = numpy.diag(numpy.multiply(sigmaxz, numpy.multiply(sigmax,sigmaz)))
        P[Ao.shape[0]:Ao.shape[0] * 2, Ao.shape[0] * 2:Ao.shape[0] * 3] = numpy.diag(numpy.multiply(sigmayz, numpy.multiply(sigmay,sigmaz)))

        P[Ao.shape[0]:Ao.shape[0] * 2, 0:Ao.shape[0]] = numpy.diag(numpy.multiply(sigmaxy, numpy.multiply(sigmax,sigmay)))
        P[Ao.shape[0] * 2: Ao.shape[0] * 3, 0:Ao.shape[0]] = numpy.diag(numpy.multiply(sigmaxz, numpy.multiply(sigmax,sigmaz)))
        P[Ao.shape[0] * 2: Ao.shape[0] * 3, Ao.shape[0]:Ao.shape[0] * 2] = numpy.diag(numpy.multiply(sigmayz, numpy.multiply(sigmay,sigmaz)))

        x = [float(item['X']) for item in ppp]
        y = [float(item['Y']) for item in ppp]
        z = [float(item['Z']) for item in ppp]

        L = numpy.array(x + y + z)

        X, sigma, index, dev, f, P = self.adjust_lsq(Am, P, L, numpy.array([]), numpy.array([]))

        self.C = []
        self.S = []
        self.F = []
        self.D = []
        self.factor = []
        self.Ao = Ao
        self.A = As
        self.ts = ts
        self.t = t
        self.L = numpy.array([x,y,z])
        self.jumps = p_jumps

        for i in range(3):

            self.C.append(X[i*Ao.shape[1]:(i+1)*Ao.shape[1]])
            self.S.append(sigma[i*Ao.shape[1]:(i+1)*Ao.shape[1]])
            self.F.append(index[i*Ao.shape[0]:(i+1)*Ao.shape[0]])
            self.D.append(dev[i*Ao.shape[1]:(i+1)*Ao.shape[1]])
            #self.factor.append(f[i*Ao.shape[1]:(i+1)*Ao.shape[1]])
            self.P = P

        # check the APR coords table and add the data that is missing
        #apr = cnn.query('SELECT * FROM apr_coords WHERE p1."NetworkCode" = \'%s\' AND p1."StationCode" = \'%s\'' % (NetworkCode,StationCode))

        if plotit:
            import matplotlib.pyplot as plt

            f, axis = plt.subplots(nrows=3,ncols=1,sharex=True)
            f.suptitle('Station: ' + NetworkCode + '.' + StationCode)

            filt = self.F[0]*self.F[1]*self.F[2]
            mX = numpy.mean(self.L[0,filt])
            mY = numpy.mean(self.L[1,filt])
            mZ = numpy.mean(self.L[2,filt])
            oneu = self.ct2lg(self.L[0,filt]-mX, self.L[1,filt]-mY, self.L[2,filt]-mZ, self.slat, self.slon)
            tneu = self.ct2lg(numpy.dot(As, self.C[0])-mX, numpy.dot(As, self.C[1])-mY, numpy.dot(As, self.C[2])-mZ, self.slat, self.slon)

            for i,ax in enumerate(axis):
                ax.plot(t[filt], oneu[i],'ob')
                ax.plot(ts, tneu[i], 'r')
                ax.autoscale(enable=True, axis='x', tight=True)
                ax.autoscale(enable=True, axis='y', tight=True)

                if i == 0:
                    ax.set_ylabel('N [m]')
                elif i == 1:
                    ax.set_ylabel('E [m]')
                elif i == 2:
                    ax.set_ylabel('U [m]')

                ax.grid(True)
                for j in p_jumps:
                    if j[0] >= t.min():
                        # the post-seismic jumps that happened before t.min() should not be plotted
                        if j[1] == 0:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'b:')
                        else:
                            ax.plot((j[0], j[0]), ax.get_ylim(), 'r:')

            plt.show()

    def get_xyz_s(self, year, doy):
        # this function find the requested epochs and returns an X Y Z and sigmas
        # find this epoch in the t vector
        date = pyDate.Date(year=year,doy=doy)

        index, _ = numpy.where(self.t == date.fyear)

        s = numpy.zeros((3,1))
        x = numpy.zeros((3, 1))

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
                    idt = numpy.argmin(numpy.abs(self.ts - date.fyear))

                    x[i,0] = numpy.dot(self.A[idt,:],self.C[i])
                    # since there is no way to estimate the error, use the variance of unit weight
                    s[i,0] = self.factor[i]
        else:
            # the coordinate doesn't exist, get it from the ETM
            idt = numpy.argmin(numpy.abs(self.ts - date.fyear))

            for i in range(3):
                x[i, 0] = numpy.dot(self.A[idt, :], self.C[i])
                # since there is no way to estimate the error, use the variance of unit weight
                s[i, 0] = self.factor[i]

        # crude transformation from XYZ to NEU
        dn,de,du = self.ct2lg(s[0],s[1],s[2],self.slat,self.slon)

        # careful with zeros in the sittbl. file
        if numpy.abs(dn) < 0.005:
            dn = 0.005
        if numpy.abs(de) < 0.005:
            de = 0.005
        if numpy.abs(du) < 0.005:
            du = 0.005

        s = numpy.row_stack((numpy.abs(dn),numpy.abs(de),numpy.abs(du)))

        return x, s

    def ct2lg(self, dX, dY, dZ, lat, lon):

        n = dX.size
        R = numpy.zeros((3, 3, n))

        R[0, 0, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
        R[0, 1, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
        R[0, 2, :] = numpy.cos(numpy.deg2rad(lat))
        R[1, 0, :] = -numpy.sin(numpy.deg2rad(lon))
        R[1, 1, :] = numpy.cos(numpy.deg2rad(lon))
        R[1, 2, :] = numpy.zeros((1, n))
        R[2, 0, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
        R[2, 1, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
        R[2, 2, :] = numpy.sin(numpy.deg2rad(lat))

        dxdydz = numpy.column_stack((numpy.column_stack((dX, dY)), dZ))

        RR = numpy.reshape(R[0, :, :], (3, n))
        dx = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
        RR = numpy.reshape(R[1, :, :], (3, n))
        dy = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
        RR = numpy.reshape(R[2, :, :], (3, n))
        dz = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)

        return dx, dy, dz

    def adjust_lsq(self, Ai, Wi, Li, constrains_h, constrains_s):

        limit = 2.5

        # "Smart" stabilization inversion
        # try 4 combinations of A:
        # 1) without any condition equations
        # 2) with jumps condition equations
        # 3) with sine and coside condition equations
        # 4) with jump and sine and cosine condition equations
        # pick the design matrix that yields the best stability
        A = Ai

        cst_pass = False
        iteration = 0
        factor = 1
        dof = (Ai.shape[0] - Ai.shape[1])
        X1 = chi2.ppf(1 - 0.05 / 2, dof)
        X2 = chi2.ppf(0.05 / 2, dof)

        s = numpy.array([])
        v = numpy.array([])
        C = numpy.array([])

        P = numpy.linalg.inv(Wi)

        while not cst_pass and iteration <= 10:

            Q = numpy.linalg.inv(numpy.dot(numpy.dot(A.transpose(), P), A))
            d = numpy.dot(numpy.dot(A.transpose(), P), Li)

            C = numpy.dot(Q,d)

            v = Li - numpy.dot(Ai, C)

            # unit variance
            So = numpy.sqrt(numpy.dot(numpy.dot(v.transpose(),P),v)/dof)

            x = numpy.power(So,2) * dof

            # obtain the overall uncertainty predicted by lsq
            factor = factor * So

            # calculate the normalized sigmas
            s = numpy.abs(numpy.divide(v, factor))
            s[s > 40] = 40 # 40 times sigma in 10^(2.5-40) yields 3x10^-38! small enough. Limit s to avoid an overflow

            if x < X2 or x > X1:
                # if it falls in here it's because it didn't pass the Chi2 test
                cst_pass = False

                # reweigh by Mike's method of equal weight until 2 sigma
                f = numpy.ones(v.shape)
                f[s > limit] = 1. /(numpy.power(10,limit - s[s > limit]))
                # do not allow sigmas > 100 m, which is basicaly not putting
                # the observation in. Otherwise, due to a model problem
                # (missing jump, etc) you end up with very unstable inversions
                f[f > 100] = 100

                a = numpy.diag(numpy.divide(1,(factor * f)))

                P = numpy.dot(numpy.dot(a,P),a.transpose())

            else:
                cst_pass = True

            iteration += 1

        # some statistics
        sigma = 1/numpy.sqrt(numpy.diag(P))

        # mark observations with sigma <= limit
        W = numpy.linalg.inv(P)
        index = numpy.abs(v)/numpy.sqrt(numpy.diag(W)) <= limit

        return C, sigma, index, v, factor, P

    def find_stable_a(self, A, cond_h, cond_s):

        # build the different combinations of
        # condition equations
        condeq = []
        if cond_h.size > 0:
            condeq.append(cond_h)
        condeq.append(cond_s)
        if cond_h.size > 0:
            condeq.append(numpy.row_stack((cond_s,cond_h)))

        condnum = []
        condnum.append(numpy.linalg.cond(A))

        for cond in condeq:
            condnum.append(numpy.linalg.cond(numpy.row_stack((A,cond))))

        i = numpy.argmin(numpy.array(condnum))

        if i == 0:
            return numpy.array([])
        else:
            return condeq[i-1]

    def chi2inv(self, chi, df):
        """Return prob(chisq >= chi, with df degrees of
        freedom).

        df must be even.
        """
        assert df & 1 == 0
        # XXX If chi is very large, exp(-m) will underflow to 0.
        m = chi / 2.0
        sum = term = numpy.exp(-m)
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
        return numpy.min(sum)

    def ecef2lla(self,ecefArr):
        # convert ECEF coordinates to LLA
        # test data : test_coord = [2297292.91, 1016894.94, -5843939.62]
        # expected result : -66.8765400174 23.876539914 999.998386689

        x = float(ecefArr[0])
        y = float(ecefArr[1])
        z = float(ecefArr[2])

        a = 6378137
        e = 8.1819190842622e-2

        asq = numpy.power(a, 2)
        esq = numpy.power(e, 2)

        b = numpy.sqrt(asq * (1 - esq))
        bsq = numpy.power(b, 2)

        ep = numpy.sqrt((asq - bsq) / bsq)
        p = numpy.sqrt(numpy.power(x, 2) + numpy.power(y, 2))
        th = numpy.arctan2(a * z, b * p)

        lon = numpy.arctan2(y, x)
        lat = numpy.arctan2((z + numpy.power(ep, 2) * b * numpy.power(numpy.sin(th), 3)),
                         (p - esq * a * numpy.power(numpy.cos(th), 3)))
        N = a / (numpy.sqrt(1 - esq * numpy.power(numpy.sin(lat), 2)))
        alt = p / numpy.cos(lat) - N

        lon = lon * 180 / numpy.pi
        lat = lat * 180 / numpy.pi

        return numpy.array([lat]), numpy.array([lon]), numpy.array([alt])

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
        a = numpy.sin(dlat/2)**2 + numpy.cos(lat1) * numpy.cos(lat2) * numpy.sin(dlon/2)**2
        c = 2 * numpy.arcsin(numpy.sqrt(a))
        km = 6371 * c
        return km

    def design_matrix(self, t, jumps):

        if t.size > 1:

            # t ref (just the beginning of t vector)
            Tr = numpy.min(t)
            # offset
            c = numpy.ones((t.size,1))

            # velocity
            v = (t - Tr)

            # periodic terms
            s = numpy.array([sin(2 * pi * t[:,0]), sin(4 * pi * t[:,0]), cos(2 * pi * t[:,0]), cos(4 * pi * t[:,0])]).transpose()

            if jumps.size > 0:
                # remove jumps before and after the start of the data if they are just co-seismic of antenna changes (with no data)
                jumps = numpy.delete(jumps, numpy.where([(jumps[:, 1] == 0) & ((jumps[:, 0] < t.min()) | (jumps[:, 0] > t.max()))]), axis=0)
                # remove log decays that happened after max(t)
                jumps = numpy.delete(jumps, numpy.where([(jumps[:, 1] != 0) & (jumps[:, 0] > t.max())]), axis=0)

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
                    jumps = numpy.delete(jumps, numpy.where([(jumps[:, 1] != 0) & (jumps[:, 0] < jlog_b4_start[-1, 0])]),axis=0)

                # heavy-side functions
                ht = numpy.zeros((t.shape[0], jumps.shape[0]))

                for i,jump in enumerate(jumps):
                    # the jumps has to be within the t range to be applied
                    if jump[0] > t.min() and jump[0] < t.max():
                        ht[t[:,0] >= jump[0],i] = 1

                        # if 2 or more jumps happen inside a gap, the (t >= Ht(i,1))
                        # will return identical columns creating a singular matrix.
                        # Verify that the new column is different than the rest
                        if i > 0:
                            for j in range(i):
                                # compare col j with col i
                                if numpy.sum(numpy.logical_xor(ht[: ,j], ht[:, i])) < 2:
                                    # identical columns (oh, well, only different by 2 elements)
                                    # remove column j
                                    ht[:, i] = 0
                                    jumps[j,:] = 0

                # loop over the log decays
                hl = numpy.zeros((t.shape[0], jumps[jumps[:, 1] != 0].shape[0]))

                for i,jump in enumerate(jumps[jumps[:, 1] != 0]):

                    if jump[1] != 0:
                        hl[t[:,0] >= jump[0], i] = numpy.log10(1 + (t[t >= jump[0]] - jump[0])/jump[1])

                        # check for previous log decays. Stop them if necessary
                        if i > 0:
                            for j in range(i):
                                hl[t[:,0] >= jump[0], j] = 0

                                if numpy.sum(hl[:,j]) == 0:
                                    # no data to constrain this decay, remove from jumps all together
                                    # log decay cannot be constrained by data
                                    # removing this jump allows to use this function with a full vector is time to get
                                    # the same design matrix as with the observation vector
                                    k = numpy.where(jumps[:,0] == jumps[jumps[:, 1] != 0,0][j])
                                    jumps[k,:] = 0

                # remove any cols will all zeros
                ht = ht[:, (ht != 0).sum(axis=0) > 0]
                hl = hl[:, (hl != 0).sum(axis=0) > 0]

                jumps = jumps[jumps[:,0] != 0,:]

                A = numpy.column_stack((c, v, ht, hl, s))

                # build the constrains matrix
                hs = hl.shape[1] + ht.shape[1]
                ss = s.shape[1]
                constrains_h = numpy.column_stack((numpy.zeros((hs, 2)), numpy.diag(numpy.ones(hs)), numpy.zeros((hs, ss))))
                constrains_s = numpy.column_stack((numpy.zeros((ss, 2 + hs)), numpy.diag(numpy.ones(ss))))

            else:
                ss = s.shape[1]

                constrains_h = numpy.array([])
                constrains_s = numpy.column_stack((numpy.zeros((ss, 2)), numpy.diag(numpy.ones(ss))))

                A = numpy.column_stack((c, v, s))



            return A, jumps, constrains_h, constrains_s


