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
import os
from Utils import lg2ct
from pyDRA import adjust_lsq

pi = 3.141592653589793


def station_etm(project, station, stn_ts, exclude, insert_only, iteration=0):

    msg = None
    add_exclude = []

    cnn = dbConnection.Cnn("gnss_data.cfg")

    sql_r = 'INSERT INTO stack_residuals ' \
            '("NetworkCode", "StationCode", "Project", x, y, z, sigmax, sigmay, sigmaz, "Year", "DOY") ' \
            'VALUES (%s, %s, \'' + project + '\', %f, %f, %f, %f, %f, %f, %i, %i)'

    sql_s = 'INSERT INTO stacks ' \
            '("NetworkCode", "StationCode", "Project", "X", "Y", "Z", sigmax, sigmay, sigmaz, "Year", "DOY", "FYear") ' \
            'VALUES (\'' + station.NetworkCode + '\', \'' + station.StationCode + '\', \'' \
            + project + '\', %f, %f, %f, 0, 0, 0, %i, %i, %f)'

    # make sure it is sorted by date
    stn_ts.sort(key=lambda k: (k[3], k[4]))

    cnn.executemany(sql_s, stn_ts)

    if not exclude and not insert_only:
        try:
            # save the time series
            ts = pyETM.GamitSoln(cnn, stn_ts, station.NetworkCode, station.StationCode)

            # create the ETM object
            etm = pyETM.GamitETM(cnn, station.NetworkCode, station.StationCode, False, False, ts)

            if etm.A is None:
                # no contribution to stack, remove from the station list
                add_exclude = [station.dictionary]
            else:
                # insert the residuals for the station in stack_residuals
                # these values will be used later on in helmert_stack
                if iteration == 0:
                    # if iteration is == 0, then the target frame has to be the PPP ETMs
                    cnn.executemany(sql_r, etm.get_residuals_dict(use_ppp_model=True, cnn=cnn))
                else:
                    # on next iters, the target frame is the inner geometry of the stack
                    cnn.executemany(sql_r, etm.get_residuals_dict())

        except Exception as e:

            add_exclude = [station.dictionary]
            msg = 'Error while producing ETM for %s.%s: ' % (station.NetworkCode, station.StationCode) + str(e)

    return add_exclude, msg


def helmert_stack(name, date, exclude):

    eq_count = 0
    it = 0

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # exclude the solutions declared in "exclude"
    sql_where = ','.join(["'" + stn['NetworkCode'] + '.' + stn['StationCode'] + "'" for stn in exclude])

    try:

        if sql_where is not '':
            sql_where = ' AND "NetworkCode" || \'.\' || "StationCode" NOT IN (%s)' % sql_where

        x = cnn.query_float(
            'SELECT 0, -"Z", "Y", "X", 1, 0, 0 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        y = cnn.query_float(
            'SELECT "Z", 0, -"X", "Y", 0, 1, 0 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        z = cnn.query_float(
            'SELECT -"Y", "X", 0, "Z", 0, 0, 1 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        r = cnn.query_float(
            'SELECT x, y, z FROM stack_residuals WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        # X vector has ALL the stations, not only the ones involved in the adjustment
        X = cnn.query_float(
            'SELECT "X", "Y", "Z" FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        # metadata also should include ALL stations
        metadata = cnn.query('SELECT "NetworkCode", "StationCode" FROM stacks '
                             'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
                             % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        metadata = metadata.dictresult()

        # done getting data from the DB, now run the adjustment

        Ax = numpy.array(x)
        Ay = numpy.array(y)
        Az = numpy.array(z)

        # save the number of stations used in the adjustment
        eq_count = Ax.shape[0]

        X = numpy.array(X).transpose().flatten()
        r = numpy.array(r).transpose().flatten()

        A = numpy.row_stack((Ax, Ay, Az))

        c, _, _, _, _, _, it = adjust_lsq(A, r)

        # rebuild A to include all stations
        x = cnn.query_float(
            'SELECT 0, -"Z", "Y", "X", 1, 0, 0 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        y = cnn.query_float(
            'SELECT "Z", 0, -"X", "Y", 0, 1, 0 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        z = cnn.query_float(
            'SELECT -"Y", "X", 0, "Z", 0, 0, 1 FROM stacks WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
            % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        Ax = numpy.array(x)
        Ay = numpy.array(y)
        Az = numpy.array(z)

        A = numpy.row_stack((Ax, Ay, Az))

        X = (numpy.dot(A, c) + X).reshape(3, len(metadata)).transpose()

        # build the polyhedron dictionary
        polyhedron = []

        for i, stn in enumerate(metadata):
            polyhedron += [{'NetworkCode': stn['NetworkCode'],
                            'StationCode': stn['StationCode'],
                            'X': X[i][0], 'Y': X[i][1], 'Z': X[i][2],
                            'Year': date.year, 'DOY': date.doy, 'FYear': date.fyear}]

        return c, polyhedron, date, eq_count, it, None

    except Exception as e:

        metadata = cnn.query('SELECT "NetworkCode", "StationCode" FROM stacks '
                             'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
                             % (name, date.year, date.doy) + ' ORDER BY "NetworkCode", "StationCode"')

        metadata = ['%s.%s' % (ns['NetworkCode'], ns['StationCode']) for ns in metadata.dictresult()]

        gamit = cnn.query('SELECT "NetworkCode", "StationCode" FROM stacks '
                          'WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i '
                          % (name, date.year, date.doy) + sql_where + ' ORDER BY "NetworkCode", "StationCode"')

        gamit = ['%s.%s' % (ns['NetworkCode'], ns['StationCode']) for ns in gamit.dictresult()]

        msg = ' -- ' + traceback.format_exc() + 'Error during ' + date.yyyyddd() + ': ' + str(e) + '\n' + \
              'Stations in meta not in gamit: ' + str(list(set(metadata) - set(gamit))) + '\n' + \
              'Stations in gamit not in meta: ' + str(list(set(gamit) - set(metadata)))

        return [0, 0, 0, 0, 0, 0, 0], [], date, eq_count, it, msg


class AlignClass:
    def __init__(self, qbar):
        self.date = None
        self.polyhedron = None
        self.stations_used = None
        self.iterations = None
        self.qbar = qbar
        self.x = None

    def finalize(self, args):
        self.x = args[0]
        self.polyhedron = args[1]
        self.date = args[2]
        self.stations_used = args[3]
        self.iterations = args[4]
        self.qbar.update()

        if args[5] is None:
            self.qbar.write(' -- %s (%3i) %2i it: translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e' % \
                            (self.date.yyyyddd(), self.stations_used, self.iterations, self.x[-3] * 1000,
                             self.x[-2] * 1000, self.x[-1] * 1000, self.x[-4]))
        else:
            self.qbar.write(' -- %s' % args[5])


class EtmClass:
    def __init__(self, qbar):
        self.exclude = None
        self.msg = None
        self.qbar = qbar

    def finalize(self, args):
        self.exclude = args[0]
        self.msg = args[1]
        self.qbar.update()

        if self.msg is not None:
            self.qbar.write(' -- %s' % self.msg)


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

    def __eq__(self, other):

        return self.NetworkCode == self.NetworkCode and self.StationCode == other.StationCode

    def __repr__(self):
        return 'pyStack.Station(' + str(self) + ')'


class Project(object):

    def __init__(self, cnn, name, max_iters=4, exclude=(), use=()):

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
        self.ts = []
        self.cnn = cnn

        # get the station list
        rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                       'WHERE "Project" = \'%s\' AND "Year" between 1999 and 2011 GROUP BY "NetworkCode", "StationCode" '
                       'ORDER BY "NetworkCode", "StationCode"' % name)

        self.stnlist = [Station(cnn, item['NetworkCode'], item['StationCode']) for item in rs.dictresult()]

        # if none selected, use all
        if not self.use:
            for stn in self.stnlist:
                if stn.dictionary not in self.use and stn.dictionary not in self.exclude:
                    self.use += [stn.dictionary]
        else:
            # if stations are included in the use list, then exclude the other
            for stn in self.stnlist:
                if stn.dictionary not in self.use and stn.dictionary not in self.exclude:
                    self.exclude += [stn.dictionary]

        # get the epochs
        rs = cnn.query('SELECT "Year", "DOY" FROM gamit_soln '
                       'WHERE "Project" = \'%s\' AND "Year" between 1999 and 2011 GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % name)

        rs = rs.dictresult()
        self.epochs = [Date(year=item['Year'], doy=item['DOY']) for item in rs]

        # load the polyhedrons
        self.polyhedrons = []

        print ' >> Loading polyhedrons. Please wait...'

        self.polyhedrons = cnn.query_float('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" between 1999 and 2011 '
                                           'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"' % name, as_dict=True)

        # load the transformations, if any

        # load the metadata (stabilization sites)

    def plot_etms(self):

        qbar = tqdm(total=len(self.stnlist), desc=' >> Plotting ETMs', ncols=160)

        for station in self.stnlist:

            qbar.set_postfix(station=str(station))
            qbar.update()

            try:
                stn_ts = [[item['X'], item['Y'], item['Z'], item['Year'], item['DOY']] for item in self.polyhedrons
                          if item['NetworkCode'] == station.NetworkCode and item['StationCode'] == station.StationCode]

                # make sure it is sorted by date
                stn_ts.sort(key=lambda k: (k[3], k[4]))

                # save the time series
                ts = pyETM.GamitSoln(self.cnn, stn_ts, station.NetworkCode, station.StationCode)

                # create the ETM object
                etm = pyETM.GamitETM(self.cnn, station.NetworkCode, station.StationCode, False, False, ts)

                etm.plot(pngfile='%s/%s.%s_RR.png' % (self.name, etm.NetworkCode, etm.StationCode),
                         residuals=True, plot_missing=False)

                etm.plot(pngfile='%s/%s.%s_FF.png' % (self.name, etm.NetworkCode, etm.StationCode),
                         residuals=False, plot_missing=False)

            except pyETM.pyETMException as e:

                qbar.write(' -- %s %s' % (str(station), str(e)))

        qbar.close()

    def remove_common_modes(self, cnn):

        tqdm.write(' >> Removing periodic common modes...')

        # load all the periodic terms
        etm_objects = cnn.query_float('SELECT etmsv2."NetworkCode", etmsv2."StationCode", stations.lat, stations.lon, '
                                      'frequencies as freq, params FROM etmsv2 '
                                      'LEFT JOIN stations ON '
                                      'etmsv2."NetworkCode" = stations."NetworkCode" AND '
                                      'etmsv2."StationCode" = stations."StationCode" '
                                      'WHERE "object" = \'periodic\' AND soln = \'gamit\' '
                                      'AND frequencies <> \'{}\' '
                                      'ORDER BY etmsv2."NetworkCode", etmsv2."StationCode"', as_dict=True)

        # load the frequencies to subtract
        frequencies = cnn.query_float('SELECT frequencies FROM etmsv2 WHERE soln = \'gamit\' AND object = \'periodic\' '
                                      'AND frequencies <> \'{}\' GROUP BY frequencies', as_dict=True)

        # get the unique list of frequencies
        f_vector = []

        for freq in frequencies:
            f_vector += [f for f in freq['frequencies']]

        f_vector = numpy.array(list(set(f_vector)))

        ox = numpy.zeros((len(f_vector), len(etm_objects), 2))
        oy = numpy.zeros((len(f_vector), len(etm_objects), 2))
        oz = numpy.zeros((len(f_vector), len(etm_objects), 2))

        for s, p in enumerate(etm_objects):
            params = numpy.array(p['params'])
            params = params.reshape((3, params.shape[0] / 3))
            param_count = params.shape[1] / 2

            # convert from NEU to XYZ
            for j in range(params.shape[1]):
                params[:, j] = numpy.array(lg2ct(params[0, j], params[1, j], params[2, j],
                                                 p['lat'], p['lon'])).flatten()

            for i, f in enumerate(p['freq']):
                ox[f_vector == f, s] = params[0, i:i+param_count+1:param_count]
                oy[f_vector == f, s] = params[1, i:i+param_count+1:param_count]
                oz[f_vector == f, s] = params[2, i:i+param_count+1:param_count]

        # build the design matrix
        sql_where = ','.join(["'" + stn['NetworkCode'] + '.' + stn['StationCode'] + "'" for stn in etm_objects])

        x = cnn.query_float('SELECT 0, -auto_z, auto_y, 1, 0, 0 FROM stations WHERE "NetworkCode" || \'.\' || '
                            '"StationCode" IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)

        y = cnn.query_float('SELECT auto_z, 0, -auto_x, 0, 1, 0 FROM stations WHERE "NetworkCode" || \'.\' || '
                            '"StationCode" IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)

        z = cnn.query_float('SELECT -auto_y, auto_x, 0, 0, 0, 1 FROM stations WHERE "NetworkCode" || \'.\' || '
                            '"StationCode" IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)
        Ax = numpy.array(x)
        Ay = numpy.array(y)
        Az = numpy.array(z)

        A = numpy.row_stack((Ax, Ay, Az))

        # select everybody (not just the stations with ETMs)
        x = cnn.query_float('SELECT 0, -"Z", "Y", 1, 0, 0 FROM stacks WHERE "Project" = \'%s\' '
                            'ORDER BY "NetworkCode", "StationCode", "FYear"' % self.name)

        y = cnn.query_float('SELECT "Z", 0, -"X", 0, 1, 0 FROM stacks WHERE "Project" = \'%s\' '
                            'ORDER BY "NetworkCode", "StationCode", "FYear"' % self.name)

        z = cnn.query_float('SELECT -"Y", "X", 0, 0, 0, 1 FROM stacks WHERE "Project" = \'%s\' '
                            'ORDER BY "NetworkCode", "StationCode", "FYear"' % self.name)

        t = cnn.query_float('SELECT "FYear", "X", "Y", "Z" FROM stacks WHERE "Project" = \'%s\' '
                            'ORDER BY "NetworkCode", "StationCode", "FYear"' % self.name)

        metadata = cnn.query('SELECT "NetworkCode", "StationCode", "Year", "DOY" FROM stacks '
                             'WHERE "Project" = \'%s\' ORDER BY "NetworkCode", "StationCode", "FYear"'
                             % self.name)

        metadata = metadata.dictresult()
        AX = numpy.array(x)
        AY = numpy.array(y)
        AZ = numpy.array(z)

        t = numpy.array(t)

        for freq in f_vector:
            for i, cs in enumerate((numpy.sin, numpy.cos)):
                L = numpy.row_stack((ox[f_vector == freq, :, i].flatten(),
                                     oy[f_vector == freq, :, i].flatten(),
                                     oz[f_vector == freq, :, i].flatten())).flatten()

                c = numpy.linalg.lstsq(A, L, rcond=-1)[0]

                # subtract the inverted common modes
                t[:, 1] = t[:, 1] - cs(2 * pi * freq * 365.25 * t[:, 0]) * numpy.dot(AX, c)
                t[:, 2] = t[:, 2] - cs(2 * pi * freq * 365.25 * t[:, 0]) * numpy.dot(AY, c)
                t[:, 3] = t[:, 3] - cs(2 * pi * freq * 365.25 * t[:, 0]) * numpy.dot(AZ, c)

        polyhedron = []

        for i, stn in enumerate(metadata):
            polyhedron += [{'NetworkCode': stn['NetworkCode'],
                            'StationCode': stn['StationCode'],
                            'X': t[i][1], 'Y': t[i][2], 'Z': t[i][3],
                            'Year': stn['Year'], 'DOY': stn['DOY'], 'FYear': t[i][0]}]

        return polyhedron


class Polyhedron:

    def __init__(self, cnn, project, date):

        self.epoch = date

        fieldnames = ['NetworkCode', 'StationCode', 'X', 'Y', 'Z', 'Year', 'DOY', 'sigmax', 'sigmay', 'sigmaz',
                      'sigmaxy', 'sigmaxz', 'sigmayz']

        self.geometry = dict.fromkeys(fieldnames)

        rs = cnn.query('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                       % (project, date.year, date.doy))

        for record in rs.dictresult():
            for key in self.geometry.keys():
                self.geometry[key] = record[key]


def align_stack(cnn, project, JobServer):

    for i in range(project.max_iters):

        qbar = tqdm(total=len(project.epochs), desc=' >> Aligning polyhedrons', ncols=160)

        # add one to the iteration count
        project.iter += 1

        # list for aligned polyhedron objects
        AlignedList = []
        # updated polyhedrons list
        updated_poly = []

        for date in project.epochs:

            if JobServer is not None:

                JobServer.SubmitJob(helmert_stack, (project.name, date, project.exclude), (adjust_lsq,),
                                    ('numpy', 'pyDate', 'dbConnection', 'traceback'),
                                    AlignedList, AlignClass(qbar), 'finalize')

                if JobServer.process_callback:
                    JobServer.process_callback = False
            else:

                x, poly, dd, stations_used, iterations, msg = helmert_stack(project.name, date, project.exclude)

                if msg is None:
                    qbar.write(' -- %s (%3i) %2i it: translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e' %
                               (date.yyyyddd(), stations_used, iterations, x[-3] * 1000,
                                x[-2] * 1000, x[-1] * 1000, x[-4]))
                else:
                    qbar.write(' -- %s' % msg)

                updated_poly += poly

        if JobServer is not None:
            qbar.write(' -- Waiting for alignments to finish...')
            JobServer.job_server.wait()
            qbar.write(' -- Done.')

            for doy in AlignedList:
                updated_poly += doy.polyhedron

        # sort the polyhedrons by date
        updated_poly.sort(key=lambda k: k['FYear'])

        # replace with new polyhedrons
        project.polyhedrons = updated_poly

        qbar.close()

        calculate_etms(cnn, project, JobServer)


def calculate_etms(cnn, project, JobServer, insert_only=False):

    qbar = tqdm(total=len(project.stnlist), desc=' >> Calculating ETMs', ncols=160)

    etm_list = []

    # delete the stack residuals for this project
    cnn.query('DELETE FROM stack_residuals WHERE "Project" = \'%s\'' % project.name)
    cnn.query('DELETE FROM stacks WHERE "Project" = \'%s\'' % project.name)

    # delete all the solutions from the ETMs table
    cnn.query('DELETE FROM etmsv2 WHERE "soln" = \'gamit\'')

    for station in project.stnlist:

        if station.dictionary in project.exclude or station.dictionary not in project.use:
            exclude = True
        else:
            exclude = False

        # extract the time series from the polyhedron data
        stn_ts = [[item['X'], item['Y'], item['Z'], item['Year'], item['DOY'],
                   item['FYear']] for item in project.polyhedrons
                  if item['NetworkCode'] == station.NetworkCode and item['StationCode'] == station.StationCode]

        if JobServer is not None:

            JobServer.SubmitJob(station_etm, (project.name, station, stn_ts, exclude, insert_only, project.iter), (),
                                ('pyETM', 'pyDate', 'dbConnection', 'traceback'),
                                etm_list, EtmClass(qbar), 'finalize')

            if JobServer.process_callback:
                JobServer.process_callback = False
        else:

            etm_list += [EtmClass(qbar)]

            etm_list[-1].finalize(station_etm(project.name, station, stn_ts, exclude, insert_only, project.iter))

    if JobServer is not None:
        qbar.write(' -- Waiting for jobs to finish...')
        JobServer.job_server.wait()
        qbar.write(' -- Done.')

    for etm in etm_list:
        project.exclude += etm.exclude

    qbar.close()


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")
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

    project = Project(cnn, args.project[0], max_iters, use=use_stn, exclude=exclude_stn)

    #project.remove_common_modes(cnn)
    #exit()

    calculate_etms(cnn, project, JobServer)

    align_stack(cnn, project, JobServer)

    # remove common modes
    updated_poly = project.remove_common_modes(cnn)
    updated_poly.sort(key=lambda k: k['FYear'])

    # replace with new polyhedrons
    project.polyhedrons = updated_poly
    # last call to calculate ETMs
    calculate_etms(cnn, project, JobServer)

    tqdm.write(' -- Plotting final ETMs (aligned)...')

    project.plot_etms()


if __name__ == '__main__':
    main()