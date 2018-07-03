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
from pyDate import Date
from tqdm import tqdm
import traceback
from pprint import pprint
import os
import numpy as np
from scipy.stats import chi2

LIMIT = 2.5


def helmert_stack(name, date, exclude):

    from pyDRA import adjust_lsq

    eq_count = 0

    cnn = dbConnection.Cnn("gnss_data.cfg", use_float=True)

    # exclude the solutions declared in "exclude"
    sql_where = ','.join(["'" + stn['NetworkCode'] + '.' + stn['StationCode'] + "'" for stn in exclude])

    try:

        if sql_where is not '':
            sql_where = ' AND "NetworkCode" || \'.\' || "StationCode" NOT IN (%s)' % sql_where

        x = cnn.query(
            'SELECT 0, -"Z", "Y", "X", 1, 0, 0 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        y = cnn.query(
            'SELECT "Z", 0, -"X", "Y", 0, 1, 0 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        z = cnn.query(
            'SELECT -"Y", "X", 0, "Z", 0, 0, 1 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        r = cnn.query(
            'SELECT x, y, z FROM stack_residuals WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        s = cnn.query(
            'SELECT sigmax, sigmay, sigmaz FROM stack_residuals WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        # X vector has ALL the stations, not only the ones involved in the adjustment
        X = cnn.query(
            'SELECT "X", "Y", "Z" FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        # metadata also should include ALL stations
        metadata = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_dra '
                             'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
                             % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        metadata = metadata.dictresult()

        x = x.getresult()
        y = y.getresult()
        z = z.getresult()
        X = X.getresult()
        # r = [(item[0], item[1], item[2]) for item in residuals if item[8] == date.year and item[9] == date.doy]
        # s = [(item[3], item[4], item[5]) for item in residuals if item[8] == date.year and item[9] == date.doy]
        r = r.getresult()
        s = s.getresult()

        # done getting data from the DB, now run the adjustment

        Ax = numpy.array(x)
        Ay = numpy.array(y)
        Az = numpy.array(z)

        # save the number of stations used in the adjustment
        eq_count = Ax.shape[0]

        X = numpy.array(X).transpose().flatten()
        r = numpy.array(r).transpose().flatten()
        s = numpy.array(s).transpose().flatten()

        A = numpy.row_stack((Ax, Ay, Az))

        P = numpy.divide(1, numpy.square(s))

        c, _, _, _, _, _, it = adjust_lsq(A, r, P)

        # rebuild A to include all stations
        x = cnn.query(
            'SELECT 0, -"Z", "Y", "X", 1, 0, 0 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        y = cnn.query(
            'SELECT "Z", 0, -"X", "Y", 0, 1, 0 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        z = cnn.query(
            'SELECT -"Y", "X", 0, "Z", 0, 0, 1 FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        Ax = numpy.array(x.getresult())
        Ay = numpy.array(y.getresult())
        Az = numpy.array(z.getresult())

        A = numpy.row_stack((Ax, Ay, Az))

        X = (numpy.dot(A, c) + X).reshape(3, len(metadata)).transpose()

        # build the polyhedron dictionary
        polyhedron = []

        for i, stn in enumerate(metadata):
            polyhedron += [{'NetworkCode': stn['NetworkCode'],
                            'StationCode': stn['StationCode'],
                            'X': X[i][0], 'Y': X[i][1], 'Z': X[i][2],
                            'Year': date.year, 'DOY': date.doy, 'FYear': date.fyear}]

        return c, polyhedron, date, eq_count

    except Exception as e:

        gamit = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_dra '
                             'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
                             % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        gamit = gamit.dictresult()

        print ' -- ' + traceback.format_exc() + 'Error during ' + date.yyyyddd() + ': ' + str(e) + '\n' + \
            'Stations in meta : ' + ','.join([stn['NetworkCode'] + '.' + stn['StationCode'] for stn in metadata]) + '\n' + \
            'Stations in gamit: ' + ','.join([stn['NetworkCode'] + '.' + stn['StationCode'] for stn in gamit])

        return [0, 0, 0, 0, 0, 0, 0], [], date, eq_count


class AlignClass:
    def __init__(self):
        self.date = None
        self.polyhedron = None
        self.stations_used = None
        self.x = None

    def finalize(self, args):
        self.x = args[0]
        self.polyhedron = args[1]
        self.date = args[2]
        self.stations_used = args[3]
        print ' -- %s (%3i): translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e' % \
              (self.date.yyyyddd(), self.stations_used, self.x[-3] * 1000, self.x[-2] * 1000, self.x[-1] * 1000, self.x[-4])


class Station:

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode  = NetworkCode
        self.StationCode  = StationCode
        self.StationAlias = StationCode  # upon creation, Alias = StationCode
        self.dictionary   = {'NetworkCode': NetworkCode, 'StationCode': StationCode}
        self.record       = None
        self.etm          = None
        self.StationInfo  = None
        self.lat          = None
        self.lon          = None
        self.height       = None
        self.X            = None
        self.Y            = None
        self.Z            = None
        self.otl_H        = None

        try:
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                           % (NetworkCode, StationCode))

            if rs.ntuples() != 0:
                self.record = rs.dictresult() # type: dict

                self.lat = float(self.record[0]['lat'])
                self.lon = float(self.record[0]['lon'])
                self.height = float(self.record[0]['height'])
                self.X      = float(self.record[0]['auto_x'])
                self.Y      = float(self.record[0]['auto_y'])
                self.Z      = float(self.record[0]['auto_z'])

        except Exception:
            raise

    def __str__(self):
        return self.NetworkCode + '.' + self.StationCode

    def __repr__(self):
        return 'pyStack.Station(' + str(self) + ')'


class Project:

    def __init__(self, cnn, name, max_iters=4, plot_iters=(), exclude=(), use=()):

        self.name = name

        # incorporate the list of stations to remove from the stacking process
        self.exclude = [{'NetworkCode': item[0], 'StationCode': item[1]}
                        for item in [item.lower().split('.')
                                     for item in exclude]]

        self.use = [{'NetworkCode': item[0], 'StationCode': item[1]}
                        for item in [item.lower().split('.')
                                     for item in use]]

        self.max_iters = max_iters
        self.iter = 0
        self.plot_iters = plot_iters
        self.ts = []
        self.cnn = cnn

        # get the station list
        rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_dra '
                       'WHERE "Project" = \'%s\' GROUP BY "NetworkCode", "StationCode" '
                       'ORDER BY "NetworkCode", "StationCode"' % name)

        self.stnlist = [Station(cnn, item['NetworkCode'], item['StationCode']) for item in rs.dictresult()]

        # if none selected, use all
        if not self.use:
            self.use = self.stnlist
        else:
            # if stations are included in the use list, then exclude the other
            for stn in self.stnlist:
                if stn.dictionary not in self.use and stn.dictionary not in self.exclude:
                    self.exclude += [stn.dictionary]

        # get the epochs
        rs = cnn.query('SELECT "Year", "DOY" FROM gamit_dra '
                       'WHERE "Project" = \'%s\' GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % name)

        rs = rs.dictresult()
        self.epochs = [Date(year=item['Year'], doy=item['DOY']) for item in rs]

        # load the polyhedrons
        self.polyhedrons = []

        print ' >> Loading polyhedrons. Please wait...'

        self.polyhedrons = cnn.query_float('SELECT * FROM gamit_dra WHERE "Project" = \'%s\' '
                                           'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"' % name, as_dict=True)

        self.calculate_etms(cnn)

        # load the transformations, if any

        # load the metadata (stabilization sites)

    def calculate_etms(self, cnn):

        # get the ts of each station
        qbar = tqdm(total=len(self.stnlist), desc=' >> Calculating ETMs', ncols=160)

        # remove previous version of ETMs and TS

        # delete the stack residuals for this project
        cnn.query('DELETE FROM stack_residuals WHERE "Project" = \'%s\'' % self.name)

        # delete all the solutions from the ETMs table
        cnn.query('DELETE FROM etmsv2 WHERE "soln" = \'gamit\'')

        sql = 'INSERT INTO stack_residuals ' \
              '("NetworkCode", "StationCode", "Project", x, y, z, sigmax, sigmay, sigmaz, "Year", "DOY") VALUES ' \
              '(%s, %s, %s, %f, %f, %f, %f, %f, %f, %i, %i)'

        for stn in self.stnlist:

            if stn.dictionary in self.use or self.iter in self.plot_iters:
                # extract the time series from the polyhedron data
                stn_ts = [[item['X'], item['Y'], item['Z'], item['Year'], item['DOY']] for item in self.polyhedrons
                          if item['NetworkCode'] == stn.NetworkCode and item['StationCode'] == stn.StationCode]

                # make sure it is sorted by date
                stn_ts.sort(key=lambda k: (k[3], k[4]))

                # display information
                qbar.set_postfix(station=str(stn))

                try:
                    # save the time series
                    ts = pyETM.GamitSoln(cnn, stn_ts, stn.NetworkCode, stn.StationCode)

                    # create the ETM object
                    etm = pyETM.GamitETM(cnn, stn.NetworkCode, stn.StationCode, False, False, ts)

                    if etm.A is None:
                        if stn.dictionary not in self.exclude:
                            # no contribution to stack, remove from the station list
                            qbar.write(' -- Auto excluding %s.%s from stack: no ETM' % (stn.NetworkCode, stn.StationCode))
                            self.exclude += [stn.dictionary]
                    else:
                        if stn.dictionary not in self.exclude:
                            # insert the residuals for the station in stack_residuals
                            # these values will be used later on in helmert_stack
                            cnn.executemany(sql, etm.get_residuals_dict(self.name))

                            etm.plot(pngfile='%s/%s.%s_%02i.png'
                                             % (self.name, etm.NetworkCode, etm.StationCode, self.iter),
                                     residuals=True, plot_missing=False)
                        else:
                            qbar.write(' -- %s.%s manually excluded from stack' % (stn.NetworkCode, stn.StationCode))

                            if stn.dictionary not in self.exclude:
                                self.exclude += [stn.dictionary]

                except pyETM.pyETMException as e:
                    qbar.write(' -- %s.%s excluded from stack: %s' % (stn.NetworkCode, stn.StationCode, str(e)))

                    if stn.dictionary not in self.exclude:
                        self.exclude += [stn.dictionary]

            qbar.update()

        qbar.close()

    def align_stack(self, JobServer):

        for i in range(self.max_iters):

            # add one to the iteration count
            self.iter += 1

            # list for aligned polyhedron objects
            AlignedList = []
            # updated polyhedrons list
            updated_poly = []

            for date in self.epochs:

                if JobServer is not None:

                    JobServer.SubmitJob(helmert_stack, (self.name, date, self.exclude), (),
                                        ('numpy', 'pyDate', 'dbConnection', 'traceback'),
                                        AlignedList, AlignClass(), 'finalize')

                    if JobServer.process_callback:
                        JobServer.process_callback = False
                else:
                    x, poly, _ = helmert_stack(self.name, date, self.exclude)
                    print ' -- %s: translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e' % \
                               (date.yyyyddd(), x[-3] * 1000, x[-2] * 1000, x[-1] * 1000, x[-4])
                    updated_poly += poly

            if JobServer is not None:
                print ' -- Waiting for alignments to finish...'
                JobServer.job_server.wait()
                print ' -- Done.'

                for doy in AlignedList:
                    updated_poly += doy.polyhedron

            # sort the polyhedrons by date
            updated_poly.sort(key=lambda k: k['FYear'])

            # replace with new polyhedrons
            self.polyhedrons = updated_poly

            self.calculate_etms(self.cnn)


class Polyhedron:

    def __init__(self, cnn, project, date):

        self.epoch = date

        fieldnames = ['NetworkCode', 'StationCode', 'X', 'Y', 'Z', 'Year', 'DOY', 'sigmax', 'sigmay', 'sigmaz',
                      'sigmaxy', 'sigmaxz', 'sigmayz']

        self.geometry = dict.fromkeys(fieldnames)

        rs = cnn.query('SELECT * FROM gamit_dra WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                       % (project, date.year, date.doy))

        for record in rs.dictresult():
            for key in self.geometry.keys():
                self.geometry[key] = record[key]


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")
    parser.add_argument('-plot', '--plot_iters',  nargs='+', metavar='{step}',
                        help="Plot alignment intermediate steps, indicate as 0, 1, 2, etc. Final result is always plotted.")
    parser.add_argument('-max', '--max_iters', nargs=1, type=int, metavar='{max_iter}',
                        help="Specify maximum number of iterations. Default is 4.")
    parser.add_argument('-exclude', '--exclude_stations', nargs='+', type=str, metavar='{net.stnm}',
                        help="Manually specify stations to remove from the stacking process.")
    parser.add_argument('-use', '--use_stations', nargs='+', type=str, metavar='{net.stnm}',
                        help="Manually specify stations to use for the stacking process.")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")
    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    if not args.noparallel:
        JobServer = pyJobServer.JobServer(Config, run_node_test=False)  # type: pyJobServer.JobServer
    else:
        JobServer = None
        Config.run_parallel = False

    # create the execution log
    # cnn.insert('executions', script='pyStack.py')

    if args.max_iters:
        max_iters = int(args.max_iters[0])
    else:
        max_iters = 4

    if args.plot_iters:
        plot_iters = [int(i) for i in args.plot_iters]
    else:
        plot_iters = []

    if args.exclude_stations:
        exclude_stn = args.exclude_stations
    else:
        exclude_stn = []

    if args.use_stations:
        use_stn = args.use_stations
    else:
        use_stn = []

    # create folder for plots

    if not os.path.isdir(args.project[0]):
        os.makedirs(args.project[0])

    ########################################
    # load polyhedrons

    project = Project(cnn, args.project[0], max_iters, plot_iters=plot_iters, use=use_stn, exclude=exclude_stn)

    project.align_stack(JobServer)

    tqdm.write(' -- Plotting final ETMs (aligned)...')

    project.plot_etms('RR', residuals=True)
    project.plot_etms('FF', residuals=False)


if __name__ == '__main__':
    main()