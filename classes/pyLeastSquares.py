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
from Utils import ct2lg

def robust_lsq(A, P, L, max_iter=10, gcc=True, limit=2.5, lat=0, lon=0):

    # goodness of fit test variable
    cst_pass = False
    # iteration count
    iteration = 0
    # current sigma zero
    So = 1
    # degrees of freedom
    dof = (A.shape[0] - A.shape[1])
    # chi2 limits
    X1 = chi2.ppf(1 - 0.05 / 2, dof)
    X2 = chi2.ppf(0.05 / 2, dof)

    # multiplication factor / sigma estimation
    factor = np.ones(3)

    # lists to store the variables of each component
    nsig = [None, None, None]
    v    = [None, None, None]
    C    = [None, None, None]

    while not cst_pass and iteration <= max_iter:

        # each iteration fits the three axis: x y z
        for i in range(3):

            W = np.sqrt(P)

            Aw = np.multiply(W[:, None], A)
            Lw = np.multiply(W, L[i])

            # adjust
            C[i] = np.linalg.lstsq(Aw, Lw, rcond=-1)[0]

            v[i] = L[i] - np.dot(A, C[i])

        if not gcc:
            # rotate residuals to NEU
            v[0], v[1], v[2] = rotate_vector(v, lat, lon)

        # unit variance
        So = np.sqrt(np.dot(v, np.multiply(P, v)) / dof)

        x = np.power(So, 2) * dof

        # obtain the overall uncertainty predicted by lsq
        factor[i] = factor[i] * So

        # calculate the normalized sigmas
        nsig[i] = np.abs(np.divide(v[i], factor[i]))

        if x < X2 or x > X1:
            # if it falls in here it's because it didn't pass the Chi2 test
            cst_pass = False

            # reweigh by Mike's method of equal weight until 2 sigma
            f = np.ones((v.shape[0],))
            # f[s > LIMIT] = 1. / (np.power(10, LIMIT - s[s > LIMIT]))
            # do not allow sigmas > 100 m, which is basically not putting
            # the observation in. Otherwise, due to a model problem
            # (missing jump, etc) you end up with very unstable inversions
            # f[f > 500] = 500
            sw = np.power(10, LIMIT - s[s > LIMIT])
            sw[sw < np.finfo(float).eps] = np.finfo(float).eps
            f[s > LIMIT] = 1. / sw

            P = np.diag(np.divide(1, np.square(factor * f)))
        else:
            cst_pass = True

        iteration += 1

    # make sure there are no values below eps. Otherwise matrix becomes singular
    P[P < np.finfo(float).eps] = 1e-6
    # some statistics
    SS = np.linalg.inv(np.dot(np.dot(A.transpose(), P), A))

    sigma = So * np.sqrt(np.diag(SS))

    # mark observations with sigma <= LIMIT
    index = Ai.remove_constrains(s <= LIMIT)

    v = Ai.remove_constrains(v)

    return C, sigma, index, v, factor, np.diag(P)


def rotate_vector(ecef, lat, lon):

    return ct2lg(ecef[0], ecef[1], ecef[2], lat, lon)
