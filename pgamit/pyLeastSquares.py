"""
Project: Parallel.Archive
Date: 3/3/17 11:27 AM
Author: Demian D. Gomez

module for robust least squares operations
"""

# deps
import numpy as np
from scipy.stats import chi2

# app
from pgamit.Utils import ct2lg

LIMIT = 2.5


def adjust_lsq(A, L, limit=LIMIT):

    factor = 1.
    So = 1.
    dof = (A.shape[0] - A.shape[1])
    X1 = chi2.ppf(1 - 0.05 / 2., dof)
    X2 = chi2.ppf(0.05 / 2., dof)

    s = np.array([])
    v = np.array([])
    C = np.array([])

    P = np.ones_like(L)

    for _ in range(11):
        W = np.sqrt(P)

        Aw = np.multiply(W, A)
        Lw = np.multiply(W, L)

        C = np.linalg.lstsq(Aw, Lw, rcond=-1)[0]

        v = L - A @ C

        # unit variance
        So = np.sqrt(np.dot(v.transpose(), np.multiply(P, v)) / dof)

        x = np.power(So, 2) * dof

        # obtain the overall uncertainty predicted by lsq
        factor = factor * So

        # calculate the normalized sigmas
        s = np.abs(np.divide(v, factor))

        if x < X2 or x > X1:
            # if it falls in here it's because it didn't pass the Chi2 test

            # reweigh by Mike's method of equal weight until 2 sigma
            f = np.ones_like(v)

            # f[s > LIMIT] = 1. / (np.power(10, LIMIT - s[s > LIMIT]))
            # do not allow sigmas > 100 m, which is basically not putting
            # the observation in. Otherwise, due to a model problem
            # (missing jump, etc) you end up with very unstable inversions
            # f[f > 500] = 500
            sw = np.power(10, limit - s[s > limit])
            sw[sw < np.finfo(float).eps] = np.finfo(float).eps
            f[s > limit] = sw

            P = np.square(np.divide(f, factor))
        else:
            break  # cst_pass = True

    # make sure there are no values below eps. Otherwise, matrix becomes singular
    P[P < np.finfo(float).eps] = np.finfo(float).eps

    # some statistics
    SS = np.linalg.inv(A.transpose() @ np.multiply(P, A))

    sigma = So * np.sqrt(np.diag(SS))

    # mark observations with sigma <= LIMIT
    index = s <= limit

    # DDG: output the full covariance matrix too
    return C, sigma, index, v, factor, P, np.square(So) * SS


def rotate_vector(ecef, lat, lon):

    return ct2lg(ecef[0], ecef[1], ecef[2], lat, lon)
