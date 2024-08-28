# -*- coding: utf-8 -*-
"""
Project: Parallel.GAMIT
Date: 6/18/20 14:28
Author: Demian D. Gomez
"""

# deps
import numpy as np
from scipy.stats import chi2

# app
from pyETM import Polynomial
from pyETM import Periodic
from pyDate import Date


LIMIT = 2.5


class ZtdSoln(object):
    def __init__(self, cnn, NetworkCode, StationCode, project):
        self.rs = cnn.query_float('SELECT "Year", "DOY", "Date", "ZTD" FROM gamit_ztd '
                                  'WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                  '"StationCode" = \'%s\' '
                                  'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                  % (project, NetworkCode, StationCode), as_dict=True)

        self.date = [Date(datetime=r['Date']) for r in self.rs]
        self.t = np.array([d.fyear for d in self.date])
        ts = np.arange(np.min(self.date[0].mjd), np.max(self.date[-1].mjd) + 1, 1)
        self.ts = np.array([Date(mjd=tts).fyear for tts in ts])
        self.ztd = np.array([r['ZTD'] for r in self.rs])

        self.type = 'ztd'
        self.stack_name = None


class Ztd(object):
    def __init__(self, cnn, NetworkCode, StationCode, project, plotit=False):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode
        self.soln = ZtdSoln(cnn, NetworkCode, StationCode, project)

        # fit linear and periodic
        self.polynomial = Polynomial(cnn, NetworkCode, StationCode, self.soln, self.soln.t)
        self.periodic = Periodic(cnn, NetworkCode, StationCode, self.soln, self.soln.t)

        shape = (self.polynomial.design.shape[0], self.polynomial.param_count + self.periodic.param_count)

        self.A = np.ndarray(shape)
        self.A[:, self.polynomial.column_index] = self.polynomial.design
        # determine the column_index for all objects
        col_index = self.polynomial.param_count
        self.periodic.column_index = np.arange(col_index, col_index + self.periodic.param_count)
        self.A[:, self.periodic.column_index] = self.periodic.design

        x, sigma, index, residuals, fact, _ = self.adjust_lsq(self.A, self.soln.ztd)

        self.C = np.array(x)
        self.F = np.array(index)
        self.R = np.array(residuals)
        self.factor = np.array(fact)

        # continuous solution
        shape = (self.soln.ts.shape[0], self.polynomial.param_count + self.periodic.param_count)
        self.As = np.ndarray(shape)
        self.As[:, self.polynomial.column_index] = self.polynomial.get_design_ts(self.soln.ts)
        self.As[:, self.periodic.column_index] = self.periodic.get_design_ts(self.soln.ts)

        if plotit:
            self.plot()

    def plot(self, pngfile=None, t_win=None, residuals=False, plot_missing=True,
             ecef=False, plot_outliers=True, fileio=None):

        import matplotlib.pyplot as plt

        # determine the window of the plot, if requested
        if t_win is not None:
            if type(t_win) is tuple:
                # data range, with possibly a final value
                if len(t_win) == 1:
                    t_win = (t_win[0], self.soln.t.max())
            else:
                # approximate a day in fyear
                t_win = (self.soln.t.max() - t_win / 365.25, self.soln.t.max())

        fig, ax = plt.subplots(figsize=(15, 7))
        ax.set_title('Zenith total delay %s.%s' % (self.NetworkCode, self.StationCode))
        if residuals:
            ax.plot(self.soln.t, self.soln.ztd - np.dot(self.A, self.C), 'ob', markersize=2)
        else:
            ax.plot(self.soln.t, self.soln.ztd, 'ob', markersize=2)
            ax.plot(self.soln.ts, np.dot(self.As, self.C), 'r')
        ax.set_ylabel('ZTD [m]')
        ax.grid(True)
        # window data
        self.set_lims(t_win, plt, ax)

        plt.savefig('test.png')
        plt.close()

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

    @staticmethod
    def autoscale_y(ax, margin=0.1):
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

    def adjust_lsq(self, A, L):

        cst_pass = False
        iteration = 0
        factor = 1
        So = 1
        dof = (A.shape[0] - A.shape[1])
        X1 = chi2.ppf(1 - 0.05 / 2, dof)
        X2 = chi2.ppf(0.05 / 2, dof)

        s = np.array([])
        v = np.array([])
        C = np.array([])

        P = np.ones((A.shape[0]))

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
                sw[sw < np.finfo(float).eps] = np.finfo(float).eps
                f[s > LIMIT] = sw

                P = np.square(np.divide(f, factor))
            else:
                cst_pass = True

            iteration += 1

        # make sure there are no values below eps. Otherwise matrix becomes singular
        P[P < np.finfo(float).eps] = 1e-6

        # some statistics
        SS = np.linalg.inv(np.dot(A.transpose(), np.multiply(P[:, None], A)))

        sigma = So*np.sqrt(np.diag(SS))

        # mark observations with sigma <= LIMIT
        index = s <= LIMIT

        return C, sigma, index, v, factor, P


if __name__ == '__main__':
    import dbConnection

    cnn = dbConnection.Cnn('gnss_data.cfg')
    ztd = Ztd(cnn, 'cap', 'ecgm', 'igs-sirgas')
    ztd.plot('test.png', residuals=True)
