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
import re
from Utils import lg2ct
import numpy as np
import json

pi = 3.141592653589793
etm_vertices = []


def plot_etm(cnn, stack, station, directory):
    try:
        ts = stack.get_station(station['NetworkCode'], station['StationCode'])

        ts = pyETM.GamitSoln(cnn, ts, station['NetworkCode'], station['StationCode'], stack.project)

        etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'], gamit_soln=ts)

        pngfile = os.path.join(directory, etm.NetworkCode + '.' + etm.StationCode + '.png')
        jsonfile = os.path.join(directory, etm.NetworkCode + '.' + etm.StationCode + '.json')

        etm.plot(pngfile, plot_missing=False)
        with open(os.path.join(jsonfile), 'w') as f:
            json.dump(etm.todictionary(False), f, indent=4, sort_keys=False)

    except pyETM.pyETMException as e:
        tqdm.write(str(e))


def station_etm(station, stn_ts, project, iteration=0):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    vertices = None

    try:
        # save the time series
        ts = pyETM.GamitSoln(cnn, stn_ts, station['NetworkCode'], station['StationCode'], project)

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

    JobServer.create_cluster(station_etm, progress_bar=qbar, callback=callback_handler, modules=modules)

    # delete all the solutions from the ETMs table
    cnn.query('DELETE FROM etmsv2 WHERE "soln" = \'gamit\'')
    # reset the etm_vertices list
    etm_vertices = []

    for station in stack.stations:

        # extract the time series from the polyhedron data
        stn_ts = stack.get_station(station['NetworkCode'], station['StationCode'])

        JobServer.submit(station, stn_ts, stack.project, iterations)

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


def load_periodic_space(periodic_file):
    """
    Load the periodic space parameters from an ITRF file
    :param periodic_file:
    :return: dictionary with the periodic terms
    """

    with open(periodic_file, 'r') as f:
        lines = f.readlines()

        periods = dict()

        for l in lines:
            if l.startswith('F'):
                per = re.findall(r'Frequency\s+.\s:\s*(\d+.\d+)', l)[0]
            else:
                # parse the NEU and convert to XYZ
                neu = re.findall(r'\s(\w+)\s+\w\s.{9}\s*\d*\s(\w)\s+(.{7})\s+.{7}\s+(.{7})', l)[0]

                stn = neu[0].lower().strip()
                com = neu[1].lower().strip()

                if stn not in periods.keys():
                    periods[stn] = dict()

                if per not in periods[stn].keys():
                    periods[stn][per] = dict()

                if com not in periods[stn][per].keys():
                    periods[stn][per][com] = []
                # neu[3] and then neu[2] to arrange it as we have it in the database (sin cos)
                # while Altamimi uses cos sin
                periods[stn][per][com].append([np.divide(float(neu[3]), 1000.), np.divide(float(neu[2]), 1000.)])

        # average the values (multiple fits for a single station??)
        for stn in periods.keys():
            for per in periods[stn].keys():
                for com in periods[stn][per].keys():
                    periods[stn][per][com] = np.mean(np.array(periods[stn][per][com]), axis=0).tolist()

        return periods


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
    parser.add_argument('-redo', '--redo_stack', action='store_true',
                        help="Delete the stack and redo it from scratch")
    parser.add_argument('-itrf', '--itrf', nargs='+',
                        help="File with the ITRF periodic space parameters as given by Zuheir Altamimi and the list "
                             "of stations to inherit the periodic terms from. Example: -itrf periodic.dat igs.braz "
                             "rms.autf rms.igm1 rms.sant ...")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    JobServer = pyJobServer.JobServer(Config, run_parallel=not args.noparallel)  # type: pyJobServer.JobServer

    if args.max_iters:
        max_iters = int(args.max_iters[0])
    else:
        max_iters = 4
        print ' >> Defaulting to 4 iterations'

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

    # load the ITRF dat file with the periodic space components
    if args.itrf:
        periodic = load_periodic_space(args.itrf[0])
    else:
        periodic = None

    # create the stack object
    stack = pyStack.Stack(cnn, args.project[0], args.redo_stack)

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
                    qbar.write(' -- %s (%3i) %2i it: wrms: %4.1f T %5.1f %5.1f %5.1f '
                               'R (%5.1f %5.1f %5.1f)*1e-9' %
                               (stack[j].date.yyyyddd(), stack[j].stations_used, stack[j].iterations,
                                stack[j].wrms * 1000, stack[j].helmert[-3] * 1000, stack[j].helmert[-2] * 1000,
                                stack[j].helmert[-1] * 1000, stack[j].helmert[-6], stack[j].helmert[-5],
                                stack[j].helmert[-4]))

        qbar.close()

    # before removing common modes (or inheriting periodic terms), calculate ETMs with final aligned solutions
    calculate_etms(cnn, stack, JobServer, iterations=None)

    if args.redo_stack:
        # only apply common mode removal if redoing the stack
        if args.itrf:
            stack.remove_common_modes(periodic, args.itrf[1:])
        else:
            stack.remove_common_modes()

        # here, we also align the stack in velocity and coordinate space
        # TODO: include alignment to velocity and coordinate space

    # calculate the etms again, after removing or inheriting parameters
    calculate_etms(cnn, stack, JobServer, iterations=None)

    # save polyhedrons to the database
    stack.save()

    qbar = tqdm(total=len(stack.stations), ncols=160)

    for stn in stack.stations:
        # plot the ETMs
        qbar.update()
        qbar.postfix = '%s.%s' % (stn['NetworkCode'], stn['StationCode'])
        plot_etm(cnn, stack, stn, args.directory)

    qbar.close()


if __name__ == '__main__':
    main()
