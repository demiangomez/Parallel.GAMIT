"""
Project: Parallel.GAMIT 
Date: 5/15/24 9:08 AM 
Author: Demian D. Gomez

Translated from Matlab to Python. Original by Michael Bevis based on Okada 1985
OKADA  surface displacements due to dislocation in an elastic half-space
This is a matlab implementation of Okada's fortran code SRECTF except
that only surface displacements are computed, not strains or tilts.
See document OkadaCoordSystem.pdf by M. Bevis for graphics describing
of Okada's (1985) coordinate systems and sign conventions

USAGE:    [ux,uy,uz] = okada(alpha,x,y,d,L1,L2,W1,W2,snd,csd,B1,B2,B3)

A rectangular dislocation is located in an elastic halfspace. The
right-handed coordinate system {X,Y,Z} has Z positive upwards,
and the X and Y axes lie on the surface of the halfspace. The
upper and lower edges of the rectangle are horizontal and
parallel to the X axis, which constitutes the 'strike direction'.
The rectangular dislocation is located within a dipping plane
which intersects the Z axis at -d (so d is a positive
number coinciding with 'depth').  The dip of this plane is
the angle delta which is measured positive anticlockwise from
horizontal looking in the -X direction, as seen in Figure 1 of
Okada's 1985 BSSA paper. The user must specify sd = sin(delta)
and cd = cos(delta) rather than delta itself, since this convention
allows a general treatment of the vertical fault (switching sd
between +1 and -1 when cd = 0, changes which side of the
fault is going up). The position of the dislocation within
the dipping plane is specified using a cartesian axis system {L,W}
confined to the plane of the dislocation, with the L axis being
parallel to and located beneath the X axis. The origin of the {L,W}
system is at X=Y=0, Z=-d. The actual dislocation is located in the
rectangle L1 <= L <= L2, W1 <= W <= W2.

With reference to Okada (1985) Figure 2, the fault outlined with
a solid line has L1=0,L2=L, W1=0, W2=W. To specify the extended
fault shown with the dashed line, change L1 to -L.

The Burgers vector B for the dislocation has three components B1,B2 and
B3 where B1 is the L component, B2 is the W component, and B3 is the
component normal to the dislocation surface.

The elastic half-space (Z<0) is uniform and isotropic. The displacement
field produced by the dislocation depends only on scalar alpha, where
alpha = mu/(lambda+mu). When the Lamé parameters lambda and mu are
equal, the elastic is said to be a Poisson solid and alpha=0.5

The stations where displacememts are to be computed have coordinates
x and y (which can be scalars, vectors or matrices, but must have the
same sizes. THe output arguments ux, uy and uz, which have the sames
sizes as input arguments x and y, are the X, Y and Z components of
displacement at each station.

Okada.m uses internal matlab function okadakernel.m to peform the
indefinite integrals.

version 1.0               Michael Bevis                  4 Nov 99
version 1.1                                             26 Feb 04
version 1.2  (change argument names, new header)        11 Oct 13
version 1.3  (changed sd,cd too)                         3 Apr 14

"""
import numpy as np

# from Gómez et al 2024
a = 0.5261
b = -1.1478


class Score(object):
    def __init__(self, event_lat, event_lon, depth, magnitude, strike, dip, rake):

        self.lat    = event_lat
        self.lon    = event_lon
        self.depth  = depth
        self.mag    = magnitude
        self.strike = strike
        self.dip    = dip
        self.rake   = rake
        # compute dmax based on parameters
        self.dmax   = 10. ** b + a

        # compute fault dimensions from Wells and Coppersmith 1994
        # all lengths and displacements reported in m
        self.along_strike_l = 10. ** (-3.22 + 0.69 * self.mag) * 1000  # [m]
        self.downdip_l      = 10. ** (-1.01 + 0.32 * self.mag) * 1000  # [m]
        self.avg_disp       = 10. ** (-4.80 + 0.69 * self.mag)         # [m]
        self.rupture_area   = 10. ** (-3.49 + 0.91 * self.mag)         # [km ** 2]
        self.maximum_disp   = 10. ** (-5.46 + 0.82 * self.mag)         # [m]

        # to compute okada
        rup_scale = 18
        xmax = np.ceil(self.along_strike_l) * rup_scale
        self.gx, self.gy = np.meshgrid(np.linspace(-xmax, xmax, 500))

        self.compute_disp_field()

    def compute_disp_field(self):
        # source dimensions L is horizontal, and W is depth
        L1 = -self.along_strike_l / 2
        L2 =  -L1
        W1 = -self.downdip_l / 2
        W2 = -W1



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
