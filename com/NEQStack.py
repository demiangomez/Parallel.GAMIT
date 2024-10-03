#!/usr/bin/env python
"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import argparse
import traceback
from pprint import pprint
import os

# deps
import numpy as np
from tqdm import tqdm
from scipy.stats import chi2


# app
from pgamit import dbConnection
from pgamit import pyOptions
from pgamit import pyETM
from pgamit import pyJobServer
from pgamit import pyDate
from pgamit.pyDate import Date
from pgamit.Utils import process_date, ct2lg, ecef2lla, rotct2lg

LIMIT = 2.5


def adjust_lsq(A, L, P=None):

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

    if P is None:
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
            f = np.ones((v.shape[0],))

            sw = np.power(10, LIMIT - s[s > LIMIT])
            sw[sw < np.finfo(float).eps] = np.finfo(float).eps

            f[s > LIMIT] = sw

            P = np.square(np.divide(f, factor))
        else:
            cst_pass = True

        iteration += 1

    # some statistics
    SS = np.linalg.inv(np.dot(A.transpose(), np.multiply(P[:, None], A)))

    sigma = So * np.sqrt(np.diag(SS))

    # mark observations with sigma <= LIMIT
    index = s <= LIMIT

    return C, sigma, index, v, factor, P, iteration


def sql_select_union(project, fields, date1, date2, stn_filter=None):

    ff = []
    for f in fields.split(','):
        if f.strip() not in ('0', '1'):
            if '-' in f.strip():
                ff.append('-g2.' + f.strip().replace('-', ''))
            else:
                ff.append('g2.' + f.strip())
        else:
            ff.append(f.strip())

    fields = ','.join(ff)

    if stn_filter:
        for stn in stn_filter:
            # @todo bug here? string not appended, filters by a single stn
            where = ' AND g1."NetworkCode" || \'.\' || g1."StationCode" IN (\'' + '\',\''.join(stn_filter) + '\')'
    else:
        where = ''

    sql = '''SELECT %s from gamit_soln g1
          LEFT JOIN gamit_soln g2 on
          g1."NetworkCode" = g2."NetworkCode" and 
          g1."StationCode" = g2."StationCode" and 
          g1."Project" = g2."Project" and 
          g1."Year" = %i and 
          g1."DOY"  = %i and 
          g2."Year" = %i and 
          g2."DOY"  = %i 
          WHERE g1."Year" = %i and g1."DOY" = %i AND g2."Year" IS NOT NULL
          AND g1."Project" =  \'%s\' %s ORDER BY g2."NetworkCode", g2."StationCode"''' % \
          (fields, date1.year, date1.doy, date2.year, date2.doy, date1.year, date1.doy, project, where)

    return sql


def sql_select(project, fields, date2):

    sql = '''SELECT %s from gamit_soln
          WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i
          ORDER BY "NetworkCode", "StationCode"''' % (fields, project, date2.year, date2.doy)

    return sql


def rotate_sigmas(ecef, lat, lon):

    R = rotct2lg(lat, lon)
    sd = np.diagflat(ecef)
    sneu = np.dot(np.dot(R[:, :, 0], sd), R[:, :, 0].transpose())
    dneu = np.diag(sneu)

    return dneu


def dra(cnn, project, dates):

    rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                   'WHERE "Project" = \'%s\' AND "FYear" BETWEEN %.4f AND %.4f GROUP BY "NetworkCode", "StationCode" '
                   'ORDER BY "NetworkCode", "StationCode"' % (project, dates[0].fyear, dates[1].fyear))

    stnlist = rs.dictresult()

    # get the epochs
    ep = cnn.query('SELECT "Year", "DOY" FROM gamit_soln '
                   'WHERE "Project" = \'%s\' AND "FYear" BETWEEN %.4f AND %.4f'
                   'GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % (project, dates[0].fyear, dates[1].fyear))

    ep = ep.dictresult()

    epochs = [Date(year=item['Year'], doy=item['DOY'])
              for item in ep]

    A = np.array([])
    Ax = []
    Ay = []
    Az = []

    for station in stnlist:

        print('stacking %s.%s' % (station['NetworkCode'], station['StationCode']))

        try:
            etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'], project=project)
        except Exception as e:
            print(" Exception: " + str(e))
            continue

        x = etm.soln.x
        y = etm.soln.y
        z = etm.soln.z

        Ax.append(np.array([np.zeros(x.shape), -z, y, np.ones(x.shape), np.zeros(x.shape), np.zeros(x.shape)]).transpose())
        Ay.append(np.array([z, np.zeros(x.shape), -x, np.zeros(x.shape), np.ones(x.shape), np.zeros(x.shape)]).transpose())
        Az.append(np.array([-y, x, np.zeros(x.shape), np.zeros(x.shape), np.zeros(x.shape), np.ones(x.shape)]).transpose())

        x = np.column_stack((Ax, etm.A, np.zeros(etm.A.shape), np.zeros(etm.A.shape)))
        y = np.column_stack((Ay, np.zeros(etm.A.shape), etm.A, np.zeros(etm.A.shape)))
        z = np.column_stack((Az, np.zeros(etm.A.shape), np.zeros(etm.A.shape), etm.A))

        A = np.row_stack((x, y, z))



def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")
    parser.add_argument('-d', '--date_filter', nargs='+', metavar='date',
                        help='Date range filter Can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")
    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    # create the execution log

    dates = [pyDate.Date(year=1980, doy=1),
             pyDate.Date(year=2100, doy=1)]
    try:
        dates = process_date(args.date_filter)
    except ValueError as e:
        parser.error(str(e))

    # create folder for plots

    if not os.path.isdir(args.project[0]):
        os.makedirs(args.project[0])

    ########################################
    # load polyhedrons

    project = dra(cnn, args.project[0], dates)


if __name__ == '__main__':
    main()
