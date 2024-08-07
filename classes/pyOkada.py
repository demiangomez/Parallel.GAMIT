"""
Project: Parallel.GAMIT 
Date: 5/15/24 9:08 AM 
Author: Demian D. Gomez

Seismic-score (s-score) class that allows testing if a latitude longitude locations requires co-seismic
displacement parameters on its ETM. The class includes the formulations from Wells and Coppersmith (1994) to
estimate the fault dimensions of the event and calculate the level-2 s-score. If the nodal planes of the event
are not available, then the class returns the level-1 (isotropic) s-score.

##########################################################################################
Okada code Translated from Matlab to Python. Original by Michael Bevis based on Okada 1985
##########################################################################################

OKADA surface displacements due to dislocation in an elastic half-space This is a matlab implementation of Okada's
fortran code SRECTF except that only surface displacements are computed, not strains or tilts. See document
OkadaCoordSystem.pdf by M. Bevis for graphics describing of Okada's (1985) coordinate systems and sign conventions

USAGE:    [ux,uy,uz] = okada(alpha,x,y,d,L1,L2,W1,W2,snd,csd,B1,B2,B3)

A rectangular dislocation is located in an elastic halfspace. The right-handed coordinate system {X,Y,Z} has Z positive
upwards, and the X and Y axes lie on the surface of the halfspace. The upper and lower edges of the rectangle are
horizontal and parallel to the X axis, which constitutes the 'strike direction'. The rectangular dislocation is located
within a dipping plane which intersects the Z axis at -d (so d is a positive number coinciding with 'depth'). The dip
of this plane is the angle delta which is measured positive anticlockwise from horizontal looking in the -X direction,
as seen in Figure 1 of Okada's 1985 BSSA paper. The user must specify sd = sin(delta) and cd = cos(delta) rather than
delta itself, since this convention allows a general treatment of the vertical fault (switching sd between +1 and -1
when cd = 0, changes which side of the fault is going up). The position of the dislocation within the dipping plane is
specified using a cartesian axis system {L,W} confined to the plane of the dislocation, with the L axis being parallel
to and located beneath the X axis. The origin of the {L,W} system is at X=Y=0, Z=-d. The actual dislocation is located
in the rectangle L1 <= L <= L2, W1 <= W <= W2.

With reference to Okada (1985) Figure 2, the fault outlined with a solid line has L1=0,L2=L, W1=0, W2=W. To specify the
extended fault shown with the dashed line, change L1 to -L.

The Burgers vector B for the dislocation has three components B1,B2 and B3 where B1 is the L component, B2 is the W
component, and B3 is the component normal to the dislocation surface.

The elastic half-space (Z<0) is uniform and isotropic. The displacement field produced by the dislocation depends only
on scalar alpha, where alpha = mu/(lambda+mu). When the Lamé parameters lambda and mu are equal, the elastic is said to
be a Poisson solid and alpha=0.5

The stations where displacememts are to be computed have coordinates x and y (which can be scalars, vectors or
matrices, but must have the same sizes. THe output arguments ux, uy and uz, which have the sames sizes as input
arguments x and y, are the X, Y and Z components of displacement at each station.

Okada.m uses internal matlab function okadakernel.m to peform the indefinite integrals.

version 1.0               Michael Bevis                  4 Nov 99
version 1.1                                             26 Feb 04
version 1.2  (change argument names, new header)        11 Oct 13
version 1.3  (changed sd,cd too)                         3 Apr 14
version 1.0  (PYTHON) translated by Demian Gomez        15 May 24

"""
import numpy as np
import math
from scipy.interpolate import griddata
from scipy.spatial     import KDTree
from datetime          import timedelta

from pyDate import Date
import pyETM as etm

cosd  = lambda x : np.cos(np.deg2rad(x))
sind  = lambda x : np.sin(np.deg2rad(x))
acosd = lambda x : np.rad2deg(np.arccos(x))
asind = lambda x : np.rad2deg(np.arcsin(x))
atand = lambda x : np.rad2deg(np.arctan(x))

# from Gómez et al 2024
a = 0.5261
b = -1.1478

POST_SEISMIC_SCALE_FACTOR = 1.5


def distance(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)
    """

    # convert decimal degrees to radians
    lon1 = lon1 * np.pi / 180
    lat1 = lat1 * np.pi / 180
    lon2 = lon2 * np.pi / 180
    lat2 = lat2 * np.pi / 180
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    d = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(d))
    km = 6371 * c
    return km


class ScoreTable(object):
    """
    Given a connection to the database, lat and lon of point of interest, and date range, find all the seismic events
    with level-2 s-score = 1. If no strike, dip, and rake parameters available, return events with level-1 s-score > 0
    Returns a list with [mag, date, lon, lat] ordered by ascending date and descending magnitude.
    """
    def __init__(self, cnn, lat, lon, sdate, edate):
        self.table = []

        # get the earthquakes based on Mike's expression
        # earthquakes before the start data: only magnitude 7+
        jumps = cnn.query_float('SELECT * FROM earthquakes '
                                'WHERE date BETWEEN \'%s\' AND \'%s\' UNION '
                                'SELECT * FROM earthquakes '
                                'WHERE date BETWEEN \'%s\' AND \'%s\' AND mag >= 7 '
                                'ORDER BY date ASC, mag DESC'
                                % (sdate.yyyymmdd(), edate.yyyymmdd(),
                                   (sdate.datetime() - timedelta(days=5*365)), sdate.yyyymmdd()), as_dict=True)

        for j in jumps:
            strike = [float(j['strike1']), float(j['strike2'])] if not math.isnan(j['strike1']) else []
            dip    = [float(j['dip1']), float(j['dip2'])]       if not math.isnan(j['strike1']) else []
            rake   = [float(j['rake1']), float(j['rake2'])]     if not math.isnan(j['strike1']) else []

            dist = distance(lon, lat, j['lon'], j['lat'])
            # Obtain level-1 s-score to make the process faster: do not use events outside of level-1 s-score
            # inflate the score to also include postseismic events
            s = a * j['mag'] - np.log10(dist) + b + np.log10(POST_SEISMIC_SCALE_FACTOR)

            if s > 0:

                score = Score(float(j['lat']), float(j['lon']), float(j['depth']), float(j['mag']),
                              strike, dip, rake, j['date'])

                # capture co-seismic and post-seismic scores
                s_score, p_score = score.score(lat, lon)
                # print(j['date'], s, s_score, p_score, dist)
                if s_score > 0:
                    # seismic score came back > 0, add jump
                    self.table.append([j['mag'], Date(datetime=j['date']), j['lon'], j['lat'],
                                       etm.CO_SEISMIC_JUMP_DECAY])
                elif p_score > 0:
                    # seismic score came back == 0, but post-seismic score > 0 add jump
                    self.table.append([j['mag'], Date(datetime=j['date']), j['lon'], j['lat'],
                                       etm.CO_SEISMIC_DECAY])


class Score(object):
    def __init__(self, event_lat, event_lon, depth_km, magnitude, strike=(), dip=(), rake=(), event_date=None):
        """
        Seismic-score (s-score) class that allows testing if a latitude longitude locations requires co-seismic
        displacement parameters on its ETM. The class includes the formulations from Wells and Coppersmith (1994) to
        estimate the fault dimensions of the event and calculate the level-2 s-score. If the nodal planes of the event
        are not available, then the class returns the level-1 (isotropic) s-score. Input data is as follows:
        event_lat: latitude (in decimal degrees) of the event's hypocenter.
        event_lon: longitude (in decimal degrees) of the event's hypocenter.
        depth_km : depth of the hypocenter, expressed in km.
        magnitude: moment-magnitude of the event.
        strike   : one or two value vector with the nodal planes of the event. Can be empty in which case the clss will
                   return the level-1 (isotropic) s-score.
        dip      : one or two value vector with the nodal planes of the event. Can be empty in which case the clss will
                   return the level-1 (isotropic) s-score.
        rake     : one or two value vector with the nodal planes of the event. Can be empty in which case the clss will
                   return the level-1 (isotropic) s-score.
        """
        self.lat    = float(event_lat)
        self.lon    = float(event_lon)
        self.depth  = [0, depth_km*1000]
        self.mag    = float(magnitude)
        self.strike = strike if type(strike) in (list, tuple) else [strike]
        self.dip    = dip    if type(dip)    in (list, tuple) else [dip]
        self.rake   = rake   if type(rake)   in (list, tuple) else [rake]
        # compute dmax based on parameters
        self.dmax   = 10. ** (a * self.mag + b)
        self.date   = event_date

        # compute fault dimensions from Wells and Coppersmith 1994
        # all lengths and displacements reported in m
        self.along_strike_l = 10. ** (-3.22 + 0.69 * self.mag) * 1000  # [m]
        self.downdip_l      = 10. ** (-1.01 + 0.32 * self.mag) * 1000  # [m]
        self.avg_disp       = 10. ** (-4.80 + 0.69 * self.mag)         # [m]
        self.rupture_area   = 10. ** (-3.49 + 0.91 * self.mag)         # [km ** 2]
        self.maximum_disp   = 10. ** (-5.46 + 0.82 * self.mag)         # [m]

        # to compute okada
        self.c_mx = np.array([])
        self.c_my = np.array([])
        self.c_mask = np.array([])

        self.p_mx = np.array([])
        self.p_my = np.array([])
        self.p_mask = np.array([])

        if len(self.strike):
            far_field_scale = 18
            xmax = np.ceil(self.along_strike_l) * far_field_scale
            self.gx, self.gy = np.meshgrid(np.linspace(-xmax, xmax, 250), np.linspace(-xmax, xmax, 250))

            self.c_mx, self.c_my, self.c_mask = self.compute_disp_field()
            self.p_mx, self.p_my, self.p_mask = self.compute_disp_field(POST_SEISMIC_SCALE_FACTOR)

    def compute_disp_field(self, scale_factor=1., limit=1e-3):
        # source dimensions L is horizontal, and W is depth
        L1 = -self.along_strike_l / 2
        L2 =  -L1
        W1 = -self.downdip_l / 2
        W2 = -W1
        ad = self.avg_disp

        ref_scale = []
        U = np.zeros_like(self.gx, dtype=bool)

        for depth in self.depth:
            # no need to save the mask for the zero depth, since it is only for the reference scale
            U = np.zeros_like(self.gx, dtype=bool)

            for strike, dip, rake in zip(self.strike, self.dip, self.rake):
                # check depth of fault edge
                d2 = depth - W2 * cosd(dip)

                if d2 < 0:
                    # fault is sticking out of the ground! reduce depth
                    depth = depth - d2

                # clockwise rotation
                R = np.array([[cosd(90 - strike), sind(90 - strike)],
                             [-sind(90 - strike), cosd(90 - strike)]])

                # compute the transformed station coordinates
                T = R @ np.array([self.gx.flatten(), self.gy.flatten()])
                tx = T[0, :]
                ty = T[1, :]
                n, e, u = okada(0.5, tx, ty, depth, L1, L2, W1, W2,
                                sind(dip), cosd(dip), ad*cosd(rake), ad*sind(rake), 0)

                n = np.reshape(n, self.gx.shape)
                e = np.reshape(e, self.gx.shape)
                u = np.reshape(u, self.gx.shape)

                # create the mask
                U = np.logical_or((np.sqrt(np.square(n) + np.square(e) + np.square(u)) >= limit), U)
            # print(U)
            # print(np.max(np.sqrt(np.square(self.gx[U]) + np.square(self.gy[U]))))
            # compute the deformation field scale
            try:
                ref_scale.append(np.max(np.sqrt(np.square(self.gx[U]) + np.square(self.gy[U]))))
            except ValueError:
                # no True values in the mask
                ref_scale.append(0)

        mx = self.gx / np.max(ref_scale) * self.dmax * scale_factor
        my = self.gy / np.max(ref_scale) * self.dmax * scale_factor

        return mx, my, U

    def score(self, lat, lon):
        # determine if lat lon within the mask, or determine score for station
        # convert lat lon to mask coordinates
        c = np.arccos(sind(self.lat) * sind(lat) + cosd(self.lat) * cosd(lat) * cosd(lon - self.lon))
        if c != 0:
            k = c / np.sin(c) * 6371
        else:
            k = 0
        x = k * cosd(lat) * sind(lon - self.lon)
        y = k * (cosd(self.lat) * sind(lat) - sind(self.lat) * cosd(lat) * cosd(lon - self.lon))

        if self.c_mask.size > 0:
            # if mask is available, use mask
            kd = KDTree(np.column_stack((self.c_mx.flatten(), self.c_my.flatten())))
            _, i = kd.query((x, y))
            s_score = self.c_mask.flatten()[i] + 0

            # repeat, this time inflating the level-2 mask to get the postseismic
            kd = KDTree(np.column_stack((self.p_mx.flatten(), self.p_my.flatten())))
            _, i = kd.query((x, y))
            p_score = self.p_mask.flatten()[i] + 0
        else:
            s_score = a * self.mag - np.log10(np.sqrt(np.square(x) + np.square(y))) + b
            p_score = 0

        return s_score, p_score

    def save_mask(self):
        # inverse azimuthal equidistant
        r = np.sqrt(np.square(self.c_mx) + np.square(self.c_my)).flatten()
        c = r / 6371.

        lat = asind(np.cos(c) * sind(self.lat) + self.c_my.flatten() * np.sin(c) * cosd(self.lat) / r)
        lon = self.lon + atand((self.c_mx.flatten() * np.sin(c)) /
                               (r * cosd(self.lat) * np.cos(c) - self.c_my.flatten() * sind(self.lat) * np.sin(c)))

        np.savetxt('event.txt', np.column_stack((lon, lat, self.c_mask.flatten())))


def okada(alpha, x, y, d, L1, L2, W1, W2, snd, csd, B1, B2, B3):
    # A rectangular dislocation is located in an elastic halfspace.
    # Right-handed coordinate system {X,Y,Z} has Z positive upwards.
    # Upper and lower edges of the rectangle are horizontal and parallel to the X axis.
    # The rectangular dislocation is located within a dipping plane.
    # The elastic half-space (Z<0) is uniform and isotropic.

    ####################################################################
    # switch between our variable names and those used in Okada's code
    alp = alpha
    al1 = L1
    al2 = L2
    aw1 = W1
    aw2 = W2
    dep = d
    disl1 = B1
    disl2 = B2
    disl3 = B3
    sd = snd
    cd = csd

    # check if input is np array, if not convert
    if type(x) is not np.array:
        x = np.array([x])
        y = np.array([y])

    p = y * cd + dep * sd
    q = y * sd - dep * cd

    et = p - aw1  # K=1   J=1   JK=2
    xi = x - al1
    ux, uy, uz = okadakernel(alp, xi, et, q, sd, cd, disl1, disl2, disl3)

    xi = x - al2  # K=1   J=2   JK=3
    u1, u2, u3 = okadakernel(alp, xi, et, q, sd, cd, disl1, disl2, disl3)
    ux -= u1
    uy -= u2
    uz -= u3

    et = p - aw2  # K=2   J=1   JK=3
    xi = x - al1
    u1, u2, u3 = okadakernel(alp, xi, et, q, sd, cd, disl1, disl2, disl3)
    ux -= u1
    uy -= u2
    uz -= u3

    xi = x - al2  # K=2   J=2   JK=4
    u1, u2, u3 = okadakernel(alp, xi, et, q, sd, cd, disl1, disl2, disl3)
    ux += u1
    uy += u2
    uz += u3

    return ux, uy, uz


def okadakernel(alp, xi, et, q, sd, cd, disl1, disl2, disl3):

    pi2 = 2 * np.pi

    f2 = 2 * np.ones_like(xi)
    xi2 = xi ** 2
    et2 = et ** 2
    q2 = q ** 2
    r2 = xi2 + et2 + q2
    r = np.sqrt(r2)
    d = et * sd - q * cd
    y = et * cd + q * sd
    ret = r + et
    ret[ret < 0] = 0
    rd = r + d
    tt = np.arctan(xi * et / (q * r))
    re = np.zeros_like(ret)
    re[ret != 0] = 1 / ret[ret != 0]
    dle = np.zeros_like(ret)
    dle[ret == 0] = -np.log(r[ret == 0] - et[ret == 0])
    dle[ret != 0] = np.log(ret[ret != 0])
    rrx = 1 / (r * (r + xi))
    rre = re / r

    u1 = np.zeros_like(xi)
    u2 = np.zeros_like(xi)
    u3 = np.zeros_like(xi)

    if abs(cd) > 1e-6:  # if not vertical fault
        td = sd / cd
        x = np.sqrt(xi2 + q2)
        a5 = np.zeros_like(xi)
        a5[xi != 0] = alp * f2[xi != 0] / cd * np.arctan(
            (et[xi != 0] * (x[xi != 0] + q[xi != 0] * cd) + x[xi != 0] * (r[xi != 0] + x[xi != 0]) * sd) /
            (xi[xi != 0] * (r[xi != 0] + x[xi != 0]) * cd)
        )
        a4 = alp / cd * (np.log(rd) - sd * dle)
        a3 = alp * (y / rd / cd - dle) + td * a4
        a1 = -alp / cd * xi / rd - td * a5
    else:  # if vertical fault
        a1 = -alp / f2 * xi * q / rd ** 2
        a3 = alp / f2 * (et / rd + y * q / rd ** 2 - dle)
        if disl1 != 0:
            a4 = -alp * q / rd
        a5 = -alp * xi * sd / rd

    if disl1 != 0:
        a2 = -alp * dle - a3

    if disl1 != 0:
        un = disl1 / pi2
        req = rre * q
        u1 -= un * (req * xi + tt + a1 * sd)
        u2 -= un * (req * y + q * cd * re + a2 * sd)
        u3 -= un * (req * d + q * sd * re + a4 * sd)

    if disl2 != 0:
        un = disl2 / pi2
        sdcd = sd * cd
        u1 -= un * (q / r - a3 * sdcd)
        u2 -= un * (y * q * rrx + cd * tt - a1 * sdcd)
        u3 -= un * (d * q * rrx + sd * tt - a5 * sdcd)

    if disl3 != 0:
        un = disl3 / pi2
        sdsd = sd * sd
        u1 += un * (q2 * rre - a3 * sdsd)
        u2 += un * (-d * q * rrx - sd * (xi * q * rre - tt) - a1 * sdsd)
        u3 += un * (y * q * rrx + cd * (xi * q * rre - tt) - a5 * sdsd)

    return u1, u2, u3


if __name__ == '__main__':
    import dbConnection
    conn = dbConnection.Cnn('gnss_data.cfg')
    st = ScoreTable(conn, -34, -58, Date(year=1995, doy=1), Date(year=2024, doy=1))
    print(' -- Done')
    for e in st.table:
        print(e)

    _score = Score(-3.6122000e+01, -7.2898000e+01, 22.9, 8.8, [178, 17], [77, 14], [86, 108])
    _score.save_mask()

