#!/usr/bin/env python
"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import argparse
import os
import re
from datetime import datetime
import json
import traceback

# deps
import numpy as np
from tqdm import tqdm

# app
from pgamit import dbConnection
from pgamit import pyOptions
from pgamit import pyETM
from pgamit import pyJobServer
from pgamit.pyDate import Date
from pgamit import pyStack
from pgamit.Utils import (process_date,
                          file_write,
                          file_readlines,
                          file_open,
                          stationID,
                          add_version_argument,
                          process_stnlist)


pi = 3.141592653589793
etm_vertices = []


def plot_etm(cnn, stack, station, directory):
    try:
        ts = stack.get_station(station['NetworkCode'], station['StationCode'])

        ts  = pyETM.GamitSoln(cnn, ts, station['NetworkCode'], station['StationCode'], stack.project)
        etm = pyETM.GamitETM(cnn, station['NetworkCode'], station['StationCode'], gamit_soln=ts)

        pngfile  = os.path.join(directory, stationID(etm) + '_gamit.png')
        jsonfile = os.path.join(directory, stationID(etm) + '_gamit.json')

        etm.plot(pngfile, plot_missing=False)
        file_write(os.path.join(jsonfile),
                   json.dumps(etm.todictionary(False), indent=4, sort_keys=False))

    except pyETM.pyETMException as e:
        tqdm.write(str(e))


def station_etm(station, stn_ts, stack_name, iteration=0):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    vertices = None

    try:
        # save the time series
        ts = pyETM.GamitSoln(cnn, stn_ts, station['NetworkCode'], station['StationCode'], stack_name)

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

    #print("NAH-RESULT %s" % repr(job.result))

    if job.exception:
        tqdm.write(' -- Fatal error on node %s message from node follows -> \n%s' % (job.ip_addr, job.exception))
    elif job.result is not None:
        etm_vertices += job.result


def calculate_etms(cnn, stack, JobServer, iterations, create_target=True, exclude_stn=()):
    """
    Parallel calculation of ETMs to save some time
    :param cnn: connection to the db
    :param stack: object with the list of polyhedrons
    :param JobServer: parallel.python object
    :param iterations: current iteration number
    :param create_target: indicate if function should create and return target polyhedrons
    :param exclude_stn: list of stations to exclude from the stacking process
    :return: the target polyhedron list that will be used for alignment (if create_target = True)
    """
    global etm_vertices

    # DD: remove from the station count the number of excluded stations
    # so that the progress bar ends in the right number
    qbar = tqdm(total=len(stack.stations)-len(exclude_stn), desc=' >> Calculating ETMs', ncols=160, disable=None)

    modules = ('pgamit.pyETM', 'pgamit.pyDate', 'pgamit.dbConnection', 'traceback')

    JobServer.create_cluster(station_etm, progress_bar=qbar, callback=callback_handler, modules=modules)

    # delete all the solutions from the ETMs table
    cnn.query('DELETE FROM etms WHERE "soln" = \'gamit\' AND "stack" = \'%s\'' % stack.name)
    # reset the etm_vertices list
    etm_vertices = []

    for station in stack.stations:
        # extract the time series from the polyhedron data
        if stationID(station) in [stationID(s) for s in exclude_stn]:
            tqdm.write(' -- Station %s.%s has been manually excluded from the stacking process'
                       % (station['NetworkCode'], station['StationCode']))
        else:
            stn_ts = stack.get_station(station['NetworkCode'], station['StationCode'])
            JobServer.submit(station, stn_ts, stack.name, iterations)

    JobServer.wait()

    qbar.close()

    JobServer.close_cluster()

    # etm_vertices was mutated by the job callback_handler
    vertices = pyStack.np_array_vertices(etm_vertices)

    if create_target:
        target = []
        for i in tqdm(list(range(len(stack.dates))), ncols=160,
                      desc=' >> Initializing the target polyhedrons', disable=None):
            dd = stack.dates[i]
            # DDG: to avoid getting disconnected
            cnn.query('SELECT 1')
            if not stack[i].aligned:
                # not aligned, put in a target polyhedron
                target.append(pyStack.Polyhedron(vertices, 'etm', dd))
            else:
                # already aligned, no need for a target polyhedron
                target.append([])

        return target
    else:
        return None


def load_periodic_space(periodic_file):
    """
    Load the periodic space parameters from an ITRF file
    :param periodic_file:
    :return: dictionary with the periodic terms
    """
    lines   = file_readlines(periodic_file)
    periods = {}

    for l in lines:
        if l.startswith('F'):
            per = re.findall(r'Frequency\s+.\s:\s*(\d+.\d+)', l)[0]
        else:
            # parse the NEU and convert to XYZ
            neu = re.findall(r'\s(\w+)\s+\w\s.{9}\s*\d*\s(\w)\s+(.{7})\s+.{7}\s+(.{7})', l)[0]

            stn = neu[0].lower().strip()
            com = neu[1].lower().strip()

            if stn not in periods.keys():
                periods[stn] = {}

            if per not in periods[stn].keys():
                periods[stn][per] = {}

            if com not in periods[stn][per].keys():
                periods[stn][per][com] = []

            # neu[3] and then neu[2] to arrange it as we have it in the database (sin cos)
            # while Altamimi uses cos sin
            periods[stn][per][com].append([np.divide(float(neu[3]), 1000.),
                                           np.divide(float(neu[2]), 1000.)])

    # average the values (multiple fits for a single station??)
    for stn in periods.keys():
        for per in periods[stn].keys():
            for com in periods[stn][per].keys():
                periods[stn][per][com] = np.mean(np.array(periods[stn][per][com]), axis=0).tolist()

    return periods


def load_constrains(constrains_file, exclude_stn=()):
    """
    Load the frame parameters
    :param constrains_file: file with the parameters to inherit from primary frame
    :param exclude_stn:     station list to exclude from the inheritance process
    :return: dictionary with the parameters for the given frame
    """
    params = dict()

    with file_open(constrains_file) as f:
        lines = f.read()

        stn = re.findall(r'^\s(\w+.\w+)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)'
                         r'\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)'
                         r'\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)'
                         r'\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)'
                         r'\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)\s*(-?\d*\.\d+|NaN)', lines, re.MULTILINE)

        for s in stn:
            if s[0] in [stationID(stn) for stn in exclude_stn]:
                tqdm.write(' -- Loading constraints: station %s has been manually excluded' % s[0])
            else:
                params[s[0]] = {
                    'x'       : float(s[1]),
                    'y'       : float(s[2]),
                    'z'       : float(s[3]),
                    'epoch'   : float(s[4]),
                    'vx'      : float(s[5]),
                    'vy'      : float(s[6]),
                    'vz'      : float(s[7]),

                    # sin and cos to arranged as [n:sin, n:cos] ... it as we have it in the database
                    '365.250' : { 'n' :  [np.divide(float(s[8]),  1000.), np.divide(float(s[10]), 1000.)],
                                  'e' :  [np.divide(float(s[12]), 1000.), np.divide(float(s[14]), 1000.)],
                                  'u' :  [np.divide(float(s[16]), 1000.), np.divide(float(s[18]), 1000.)]},

                    '182.625' : { 'n' :  [np.divide(float(s[9]),  1000.), np.divide(float(s[11]), 1000.)],
                                  'e' :  [np.divide(float(s[13]), 1000.), np.divide(float(s[15]), 1000.)],
                                  'u' :  [np.divide(float(s[17]), 1000.), np.divide(float(s[19]), 1000.)] }
                }

    return params


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")

    parser.add_argument('stack_name', type=str, nargs=1, metavar='{stack name}',
                        help="Specify a name for the stack: eg. itrf2014 or posgar07b. This name should be unique "
                             "and cannot be repeated for any other solution project")

    parser.add_argument('-max', '--max_iters', nargs=1, type=int, metavar='{max_iter}',
                        help="Specify maximum number of iterations. Default is 4.")

    parser.add_argument('-exclude', '--exclude_stations', nargs='+', type=str, metavar='{net.stnm}',
                        help="Manually specify stations to remove from the stacking process.")

    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory")

    parser.add_argument('-redo', '--redo_stack', action='store_true',
                        help="Delete the stack and redo it from scratch")

    parser.add_argument('-preserve', '--preserve_stack', action='store_true',
                        help="When calling without --rede_stack, reuse the stack and apply inheritance to the stack "
                             "as is. This is useful to try different parameters and stations during the inheritance "
                             "process")

    parser.add_argument('-plot', '--plot_stack_etms', action='store_true', default=False,
                        help="Plot the stack ETMs after computation is done")

    parser.add_argument('-constraints', '--external_constraints', nargs='+',
                        help="File with external constraints parameters (position, velocity and periodic). These may "
                             "br from a parent frame such as ITRF. "
                             "Inheritance will occur with stations on the list whenever a parameter exists. "
                             "Example: -constraints itrf14.txt "
                             "Format is: net.stn x y z epoch vx vy vz sn_1y sn_6m cn_1y cn_6m se_1y se_6m ce_1y ce_6m "
                             "su_1y su_6m cu_1y cu_6m ")

    parser.add_argument('-d', '--date_end', nargs=1, metavar='date',
                        help='Limit the polyhedrons to the specified date. Can be in wwww-d, yyyy_ddd, yyyy/mm/dd '
                             'or fyear format')

    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    JobServer = pyJobServer.JobServer(Config, check_archive=False, check_executables=False, check_atx=False,
                                      run_parallel=not args.noparallel)  # type: pyJobServer.JobServer

    if args.max_iters:
        max_iters = int(args.max_iters[0])
    else:
        max_iters = 4
        print(' >> Defaulting to 4 iterations')

    if args.exclude_stations:
        exclude_stn = process_stnlist(cnn, args.exclude_stations,
                                      summary_title='User selected list of stations to exclude:')
    else:
        exclude_stn = []

    dates = [Date(year=1980, doy=1), Date(datetime=datetime.now())]
    if args.date_end is not None:
        try:
            dates = process_date([str(Date(year=1980, doy=1).fyear), args.date_end[0]])
        except ValueError as e:
            parser.error(str(e))

    # create folder for plots

    if args.directory:
        if not os.path.exists(args.directory):
            os.mkdir(args.directory)
    else:
        if not os.path.exists('production'):
            os.mkdir('production')
        args.directory = 'production'

    # load the ITRF dat file with the periodic space components
    if args.external_constraints:
        constraints = load_constrains(args.external_constraints[0], exclude_stn)
        if len(constraints) == 0 :
            print(' >> WARNING: Empty constraints file passed. Check that the lines start with a space.')
            exit(1)
        elif len(constraints) < 3:
            print(' >> WARNING: A constraints file was passed but %i stations where found. The number of '
                  'stations in the constraints file might be insufficient to align all spaces.' % len(constraints))
    else:
        constraints = None

    # check if stack does not exist and redo = False
    try:
        _ = cnn.get('stacks', {'name': args.stack_name[0]}, limit=1)
    except dbConnection.DatabaseError:
        # if stack does not exist, then force a redo
        args.redo_stack = True

    # create the stack object
    stack = pyStack.Stack(cnn, args.project[0], args.stack_name[0], args.redo_stack, end_date=dates[1])

    # stack.align_spaces(frame_params)
    # stack.to_json('alignment.json')
    # exit()

    for i in range(max_iters):
        # create the target polyhedrons based on iteration number (i == 0: PPP)

        target = calculate_etms(cnn, stack, JobServer, i, exclude_stn=exclude_stn)

        qbar = tqdm(total=len(stack), ncols=160,
                    desc=' >> Aligning polyhedrons (%i of %i)' % (i+1, max_iters), disable=None)

        # work on each polyhedron of the stack
        for j in range(len(stack)):

            qbar.update()

            if not stack[j].aligned:
                # do not move this if up one level: to speed up the target polyhedron loading process, the target is
                # set to an empty list when the polyhedron is already aligned
                if stack[j].date != target[j].date:
                    # raise an error if dates don't agree!
                    raise Exception("Error processing %s: dates don't agree (target date %s)"
                                        % (stack[j].date.yyyyddd(),
                                           target[j].date.yyyyddd()))
                else:
                    # should only attempt to align a polyhedron that is unaligned
                    # do not set the polyhedron as aligned unless we are in the max iteration step
                    stack[j].align(target[j], True if i == max_iters - 1 else False)
                    # write info to the screen
                    qbar.write(' -- %s (%04i) %2i it: wrms: %4.1f T %5.1f %5.1f %5.1f '
                               'R (%5.1f %5.1f %5.1f)*1e-9' %
                               (stack[j].date.yyyyddd(),
                                stack[j].stations_used,
                                stack[j].iterations,
                                stack[j].wrms * 1000,
                                stack[j].helmert[-3] * 1000,
                                stack[j].helmert[-2] * 1000,
                                stack[j].helmert[-1] * 1000,
                                stack[j].helmert[-6],
                                stack[j].helmert[-5],
                                stack[j].helmert[-4]))

        stack.transformations.append([poly.info() for poly in stack])
        qbar.close()

    # todo: remove the requirement of redo_stack to enter the external constraints
    if args.redo_stack or args.preserve_stack:
        # before removing common modes (or inheriting periodic terms), calculate ETMs with final aligned solutions
        calculate_etms(cnn, stack, JobServer, iterations=None, create_target=False)
        # only apply common mode removal if redoing the stack
        if args.external_constraints:
            stack.remove_common_modes(constraints)
            # here, we also align the stack in velocity and position space
            stack.align_spaces(constraints)
        else:
            stack.remove_common_modes()

    # calculate the etms again, after removing or inheriting parameters
    calculate_etms(cnn, stack, JobServer, iterations=None, create_target=False)

    # save the json with the information about the alignment
    stack.to_json(args.stack_name[0] + '_alignment.json')
    # save polyhedrons to the database
    stack.save(erase=args.preserve_stack)

    if args.plot_stack_etms:
        qbar = tqdm(total=len(stack.stations), ncols=160, disable=None)
        for stn in stack.stations:
            # plot the ETMs
            qbar.update()
            qbar.postfix = stationID(stn)
            plot_etm(cnn, stack, stn, args.directory)

        qbar.close()


if __name__ == '__main__':
    main()
