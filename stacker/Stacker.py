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
import pyStack
import os
from Utils import lg2ct

pi = 3.141592653589793
etm_vertices = []


def station_etm(station, stn_ts, iteration=0):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    vertices = None

    try:
        # save the time series
        ts = pyETM.GamitSoln(cnn, stn_ts, station['NetworkCode'], station['StationCode'])

        # create the ETM object
        etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'], False, False, ts)

        if etm.A is not None:
            if iteration == 0:
                # if iteration is == 0, then the target frame has to be the PPP ETMs
                vertices = etm.get_etm_soln_list(use_ppp_model=True, cnn=cnn)
            else:
                # on next iters, the target frame is the inner geometry of the stack
                vertices = etm.get_etm_soln_list()

    except pyETM.pyETMException:

        vertices = None

    return vertices if vertices else None


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
        self.json = dict()

        # get the station list
        rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                       'WHERE "Project" = \'%s\' GROUP BY "NetworkCode", "StationCode" '
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
                       'WHERE "Project" = \'%s\' GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % name)

        rs = rs.dictresult()
        self.epochs = [Date(year=item['Year'], doy=item['DOY']) for item in rs]

        # load the polyhedrons
        self.polyhedrons = []

        print ' >> Loading polyhedrons. Please wait...'

        self.polyhedrons = cnn.query_float('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' '
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


def callback_handler(job):

    global etm_vertices

    if job.exception:
        tqdm.write(' -- Fatal error on node %s message from node follows -> \n%s' % (job.ip_addr, job.exception))
    else:
        if job.result is not None:
            etm_vertices += job.result


def calculate_etms(cnn, stack, JobServer, iterations):
    """
    Parallelized calculation of ETMs to save some time
    :param cnn: connection to the db
    :param stack: object with the list of polyhedrons
    :param JobServer: parallel.python object
    :param iterations: current iteration number
    :return: the target polyhedron list that will be used for alignment
    """
    global etm_vertices

    qbar = tqdm(total=len(stack.stations), desc=' >> Calculating ETMs', ncols=160)

    modules = ('pyETM', 'pyDate', 'dbConnection', 'traceback')

    JobServer.create_cluster(station_etm, callback_handler, qbar, modules=modules)

    # delete all the solutions from the ETMs table
    cnn.query('DELETE FROM etmsv2 WHERE "soln" = \'gamit\'')
    # reset the etm_vertices list
    etm_vertices = []

    for station in stack.stations:

        # extract the time series from the polyhedron data
        stn_ts = stack.get_station(station['NetworkCode'], station['StationCode'])

        JobServer.submit(station, stn_ts, iterations)

    JobServer.wait()

    qbar.close()

    JobServer.close_cluster()

    vertices = numpy.array(etm_vertices, dtype=[('stn', 'S8'), ('x', 'float64'), ('y', 'float64'),
                                                ('z', 'float64'), ('yr', 'i4'), ('dd', 'i4'),
                                                ('fy', 'float64')])

    target = []
    for dd in tqdm(stack.dates, ncols=160, desc=' >> Initializing the target polyhedrons'):
        target.append(pyStack.Polyhedron(vertices, 'etm', dd))

    return target


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
    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")
    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    JobServer = pyJobServer.JobServer(Config, run_parallel=not args.noparallel)  # type: pyJobServer.JobServer

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

    if args.directory:
        if not os.path.exists(args.directory):
            os.mkdir(args.directory)
    else:
        if not os.path.exists('production'):
            os.mkdir('production')
        args.directory = 'production'

    # create the stack object
    stack = pyStack.Stack(cnn, args.project[0], True)

    for i in range(max_iters):
        # create the target polyhedrons based on iteration number (i == 0: PPP)

        target = calculate_etms(cnn, stack, JobServer, i)

        qbar = tqdm(total=len(stack), ncols=160, desc=' >> Aligning polyhedrons (%i of %i)' % (i+1, max_iters))

        # work on each polyhedron of the stack
        for j in range(len(stack)):

            qbar.update()

            if stack[j].date != target[j].date:
                # raise an error if dates don't agree!
                raise StandardError('Error processing %s: dates don\'t agree (target date %s)'
                                    % (stack[j].date.yyyyddd(), target[j].date.yyyyddd()))
            else:
                if not stack[j].aligned:
                    # should only attempt to align a polyhedron that is unaligned
                    # do not set the polyhedron as aligned unless we are in the max iteration step
                    stack[j].align(target[j], True if i == max_iters - 1 else False)
                    # write info to the screen
                    qbar.write(' -- %s (%3i) %2i it: wrms: %6.1f T %6.1f %6.1f %6.1f '
                               'R (%6.1f %6.1f %6.1f)*1e-9' %
                               (stack[j].date.yyyyddd(), stack[j].stations_used, stack[j].iterations,
                                stack[j].wrms * 1000, stack[j].helmert[-3] * 1000, stack[j].helmert[-2] * 1000,
                                stack[j].helmert[-1] * 1000, stack[j].helmert[-6], stack[j].helmert[-5],
                                stack[j].helmert[-4]))

        qbar.close()

    qbar = tqdm(total=len(stack.stations), ncols=160)

    for stn in stack.stations:
        # plot the ETMs
        qbar.update()
        qbar.postfix = '%s.%s' % (stn['NetworkCode'], stn['StationCode'])
        try:
            ts = stack.get_station(stn['NetworkCode'], stn['StationCode'])

            ts = pyETM.GamitSoln(cnn, ts, stn['NetworkCode'], stn['StationCode'])

            etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], gamit_soln=ts)

            pngfile = os.path.join(args.directory, etm.NetworkCode + '.' + etm.StationCode + '.png')

            etm.plot(pngfile, plot_missing=False)

        except pyETM.pyETMException as e:
            tqdm.write(str(e))

    qbar.close()


if __name__ == '__main__':
    main()