"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import dbConnection
import pyOptions
import argparse
import pyETM
import pyJobServer
import numpy
import pyDate
from pyDate import Date
from tqdm import tqdm
import traceback
from pprint import pprint
import os
import numpy as np
from Utils import process_date
from Utils import ct2lg
from Utils import ecef2lla
from Utils import rotct2lg

LIMIT = 2.5


def adjust_lsq(A, L, P=None):

    LIMIT = 2.5

    from scipy.stats import chi2

    cst_pass = False
    iteration = 0
    factor = 1
    So = 1
    dof = (A.shape[0] - A.shape[1])
    X1 = chi2.ppf(1 - 0.05 / 2, dof)
    X2 = chi2.ppf(0.05 / 2, dof)

    s = numpy.array([])
    v = numpy.array([])
    C = numpy.array([])

    if P is None:
        P = numpy.ones((A.shape[0]))

    while not cst_pass and iteration <= 10:

        W = numpy.sqrt(P)

        Aw = numpy.multiply(W[:, None], A)
        Lw = numpy.multiply(W, L)

        C = numpy.linalg.lstsq(Aw, Lw, rcond=-1)[0]

        v = L - numpy.dot(A, C)

        # unit variance
        So = numpy.sqrt(numpy.dot(v, numpy.multiply(P, v)) / dof)

        x = numpy.power(So, 2) * dof

        # obtain the overall uncertainty predicted by lsq
        factor = factor * So

        # calculate the normalized sigmas

        s = numpy.abs(numpy.divide(v, factor))

        if x < X2 or x > X1:
            # if it falls in here it's because it didn't pass the Chi2 test
            cst_pass = False

            # reweigh by Mike's method of equal weight until 2 sigma
            f = numpy.ones((v.shape[0],))

            sw = numpy.power(10, LIMIT - s[s > LIMIT])
            sw[sw < numpy.finfo(numpy.float).eps] = numpy.finfo(numpy.float).eps

            f[s > LIMIT] = sw

            P = numpy.square(numpy.divide(f, factor))
        else:
            cst_pass = True

        iteration += 1

    # some statistics
    SS = numpy.linalg.inv(numpy.dot(A.transpose(), numpy.multiply(P[:, None], A)))

    sigma = So * numpy.sqrt(numpy.diag(SS))

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

    epochs = [Date(year=item['Year'], doy=item['DOY']) for item in ep]

    # delete DRA starting from the first requested epoch
    cnn.query('DELETE FROM gamit_dra WHERE "Project" = \'%s\' AND "FYear" >= %f' % (project, epochs[0].fyear))

    # query the first polyhedron in the line, which should be the last polyhedron in gamit_dra
    poly = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY", "NetworkCode", "StationCode" FROM gamit_dra '
                           'WHERE "Project" = \'%s\' AND "FYear" = (SELECT max("FYear") FROM gamit_dra)'
                           'ORDER BY "NetworkCode", "StationCode"' % project)

    if len(poly) == 0:
        print ' -- Using gamit_soln: no pre-existent DRA found'
        # no last entry found in gamit_dra, use gamit_soln
        poly = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY", "NetworkCode", "StationCode" FROM gamit_soln '
                               'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                               'ORDER BY "NetworkCode", "StationCode"'
                               % (project, epochs[0].year, epochs[0].doy))
    else:
        print ' -- Pre-existent DRA found. Attaching.'

    polyhedrons = poly

    bar = tqdm(total=len(epochs)-1, ncols=160)

    for date1, date2 in zip(epochs[0:-1], epochs[1:]):

        poly1 = []

        # get the stations common stations between day i and day i+1 (in A format)
        s = cnn.query_float(sql_select_union(project, '"X", "Y", "Z", "NetworkCode", "StationCode"', date1, date2))

        x = cnn.query_float(sql_select_union(project, '0, -"Z", "Y", 1, 0, 0', date1, date2))
        y = cnn.query_float(sql_select_union(project, '"Z", 0, -"X", 0, 1, 0', date1, date2))
        z = cnn.query_float(sql_select_union(project, '-"Y", "X", 0, 0, 0, 1', date1, date2))

        # polyhedron of the common stations
        Xx = cnn.query_float(sql_select_union(project, '"X", "Y", "Z"', date1, date2))

        X = numpy.array(Xx).transpose().flatten()

        # for vertex in stations
        for v in s:
            poly1 += [np.array(pp[0:3], dtype=float) - np.array(v[0:3]) for pp in poly if pp[-2] == v[-2] and pp[-1] == v[-1]]

        # residuals for adjustment
        L = np.array(poly1)

        A = numpy.row_stack((np.array(x), np.array(y), np.array(z)))
        A[:, 0:3] = A[:, 0:3]*1e-9
        # find helmert transformation
        c, _, _, v, _, p, it = adjust_lsq(A, L.flatten())

        # write some info to the screen
        tqdm.write(' -- %s (%3i): translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e ' %
                   (date2.yyyyddd(), it, c[-3] * 1000, c[-2] * 1000, c[-1] * 1000, c[-4]))

        # make A again with all stations
        s = cnn.query_float(sql_select(project, '"Year", "DOY", "NetworkCode", "StationCode"', date2))

        x = cnn.query_float(sql_select(project, '0, -"Z", "Y", 1, 0, 0', date2))
        y = cnn.query_float(sql_select(project, '"Z", 0, -"X", 0, 1, 0', date2))
        z = cnn.query_float(sql_select(project, '-"Y", "X", 0, 0, 0, 1', date2))

        A = numpy.row_stack((np.array(x), np.array(y), np.array(z)))
        A[:, 0:3] = A[:, 0:3] * 1e-9

        Xx = cnn.query_float(sql_select(project, '"X", "Y", "Z"', date2))
        X = numpy.array(Xx).transpose().flatten()

        X = (numpy.dot(A, c) + X).reshape(3, len(x)).transpose()

        # save current transformed polyhedron to use in the next iteration
        polyhedrons += poly
        poly = [x.tolist() + list(s) for x, s in zip(X, s)]

        # insert results in gamit_dra
        for pp in poly:
            cnn.insert('gamit_dra', NetworkCode=pp[-2], StationCode=pp[-1], Project=project, X=pp[0], Y=pp[1],
                       Z=pp[2], Year=date2.year, DOY=date2.doy, FYear=date2.fyear)

        bar.update()

    bar.close()

    # plot the residuals
    for stn in tqdm(stnlist):
        NetworkCode = stn['NetworkCode']
        StationCode = stn['StationCode']

        # load from the db
        ts = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM gamit_dra '
                             'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                             '"Project" = \'%s\' ORDER BY "Year", "DOY"' % (NetworkCode, StationCode, project))

        ts = np.array(ts)

        if ts.size:
            try:
                # save the time series
                gsoln = pyETM.GamitSoln(cnn, ts, NetworkCode, StationCode, project)

                # create the ETM object
                etm = pyETM.GamitETM(cnn, NetworkCode, StationCode, False, False, gsoln)

                etm.plot(pngfile='%s/%s.%s_SOL.png' % (project, NetworkCode, StationCode), residuals=True,
                         plot_missing=False)

                if ts.shape[0] > 2:
                    dts = np.append(np.diff(ts[:,0:3], axis=0), ts[1:, -2:], axis=1)
                    dra = pyETM.GamitSoln(cnn, dts, NetworkCode, StationCode, project)

                    etm = pyETM.DailyRep(cnn, NetworkCode, StationCode, False, False, dra)

                    etm.plot(pngfile='%s/%s.%s_DRA.png' % (project, NetworkCode, StationCode), residuals=True,
                             plot_missing=False)

            except Exception as e:
                tqdm.write(' -->' + str(e))


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

    dates = [pyDate.Date(year=1980, doy=1), pyDate.Date(year=2100, doy=1)]
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