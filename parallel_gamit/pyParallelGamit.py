"""
Project: Parallel.GAMIT
Date: 3/31/17 6:33 PM
Author: Demian D. Gomez
"""

import pyGamitConfig
import re
import sys
import pyDate
import signal
import Utils
import os
from tqdm import tqdm
import pp
import pyGamitTask
import pyGlobkTask
from pyNetwork import Network
from datetime import datetime
import dbConnection
import time
from math import sqrt
from shutil import rmtree
from math import ceil
import argparse
import glob
import pyJobServer


def signal_handler(signal, frame):
    print '\nProcess interruptued by user\n'
    raise KeyboardInterrupt


def parseIntSet(nputstr=""):

    selection = []
    invalid = []
    # tokens are comma seperated values
    tokens = [x.strip() for x in nputstr.split(',')]
    for i in tokens:
        if len(i) > 0:
            if i[:1] == "<":
                i = "1-%s"%(i[1:])
        try:
            # typically tokens are plain old integers
            selection.append(int(i))
        except Exception:
            # if not, then it might be a range
            try:
                token = [int(k.strip()) for k in i.split('-')]
                if len(token) > 1:
                    token.sort()
                    # we have items seperated by a dash
                    # try to build a valid range
                    first = token[0]
                    last = token[len(token)-1]
                    for x in range(first, last+1):
                        selection.append(x)
            except:
                # not an int and not a range...
                invalid.append(i)
    # Report invalid tokens before returning valid selection
    if len(invalid) > 0:
        print "Invalid set: " + str(invalid)
        sys.exit(2)
    return selection


def print_summary(Project, all_missing_data):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Core network stations (%i):' % (len(Project.Core.StationList)))
    Utils.print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in Project.Core.StationList])

    print('')
    print(' -- Secondary stations (%i):' % (len(Project.Secondary.StationList)))
    Utils.print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in Project.Secondary.StationList])

    # output a summary of the missing days per station:
    print('')
    sys.stdout.write(' >> Summary of data per station (' + unichr(0x258C) + ' = 1 DOY)\n')

    if len(Project.doys)/2. > 120:
        cut_len = int(ceil(len(Project.doys)/4.))
    else:
        cut_len = len(Project.doys)

    for Stn in Project.AllStations:
        missing_dates = [missing_data['date'].doy for missing_data in all_missing_data if missing_data['StationCode'] == Stn['StationCode'] and missing_data['NetworkCode'] == Stn['NetworkCode']]

        sys.stdout.write('\n -- %s.%s:\n    %03i>' % (Stn['NetworkCode'], Stn['StationCode'], Project.doys[0]))

        for i, doy in enumerate(zip(Project.doys[0:-1:2], Project.doys[1::2])):
            if doy[0] not in missing_dates and doy[1] not in missing_dates:
                sys.stdout.write(unichr(0x2588))

            elif doy[0] not in missing_dates and doy[1] in missing_dates:
                sys.stdout.write(unichr(0x258C))

            elif doy[0] in missing_dates and doy[1] not in missing_dates:
                sys.stdout.write(unichr(0x2590))

            elif doy[0] in missing_dates and doy[1] in missing_dates:
                sys.stdout.write(' ')

            if i+1 == cut_len:
                sys.stdout.write('<%03i\n' % doy[0])
                sys.stdout.write('    %03i>' % (doy[0]+1))

        if len(Project.doys) % 2 != 0:
            # last one missing
            if Project.doys[-1] not in missing_dates:
                sys.stdout.write(unichr(0x258C))
            elif Project.doys[-1] in missing_dates:
                sys.stdout.write(' ')

            if cut_len < len(Project.doys):
                sys.stdout.write('< %03i\n' % (Project.doys[-1]))
            else:
                sys.stdout.write('<%03i\n' % (Project.doys[-1]))
        else:
            sys.stdout.write('<%03i\n' % (Project.doys[-1]))

        sys.stdout.flush()

    print ''

    return


def print_summary2(Project, all_missing_data):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Core network stations (%i):' % (len(Project.Core.StationList)))
    Utils.print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in Project.Core.StationList])

    print('')
    print(' -- Secondary stations (%i):' % (len(Project.Secondary.StationList)))
    Utils.print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in Project.Secondary.StationList])

    # output a summary of the missing days per station:
    print('')
    sys.stdout.write(' >> Summary of missing data per station')

    for Stn in Project.AllStations:
        missing_dates = [missing_data['date'] for missing_data in all_missing_data if missing_data['StationCode'] == Stn['StationCode'] and missing_data['NetworkCode'] == Stn['NetworkCode']]

        if len(missing_dates) > 0:
            sys.stdout.write('\n -- %s.%s: ' % (Stn['NetworkCode'], Stn['StationCode']))
            begin = missing_dates[0]
            ds = begin
            days = 1
            for i, md in enumerate(missing_dates):

                if i > 0:
                    if md.mjd - ds.mjd == 1:
                        days += 1
                    elif md.mjd - ds.mjd > 1:
                        if days == 1:
                            sys.stdout.write('%s ' % (begin.ddd()))
                        else:
                            sys.stdout.write('%s-%s ' % (begin.ddd(), ds.ddd()))
                        begin = md
                        days = 1
                ds = md

            if days > 1:
                sys.stdout.write('%s-%s ' % (begin.ddd(), ds.ddd()))
            elif len(missing_dates) == 1:
                sys.stdout.write('%s ' % (begin.ddd()))

        sys.stdout.flush()

    sys.stdout.write('\n')

    return


def purge_solutions(cnn, args, year, doys, GamitConfig):

    if args.purge:
        print(' >> Purging selected year-doys before run:')
        for doy in tqdm(doys, ncols=80):
            date = pyDate.Date(year=year, doy=doy)  # type: pyDate.Date

            # base dir for the GAMIT session directories
            pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

            # delete the main solution dir (may be entire GAMIT run or combination directory)
            if os.path.isdir(os.path.join(pwd, GamitConfig.NetworkConfig['network_id'].lower())):
                rmtree(os.path.join(pwd, GamitConfig.NetworkConfig['network_id'].lower()))

            # possible subnetworks
            for sub in glob.glob(os.path.join(pwd, GamitConfig.NetworkConfig['network_id'].lower() + '.*')):
                rmtree(sub)

            # now remove the database entries
            cnn.query('DELETE FROM gamit_soln WHERE "Year" = %i AND "DOY" = %i' % (year, doy))


def main():
    parser = argparse.ArgumentParser(description='Parallel.GAMIT main execution program')

    parser.add_argument('session_cfg', type=str, nargs=1, metavar='session.cfg', help="Filename with the session configuration to run Parallel.GAMIT")
    parser.add_argument('-y', '--year', type=int, nargs=1, metavar='{year}', help="Year to execute Parallel.GAMIT using provided cfg file.")
    parser.add_argument('-d', '--doys', type=str, nargs=1, metavar='{doys}', help="DOYs interval given in a comma separated list or intervals (e.g. 1-57,59-365)")
    parser.add_argument('-e', '--exclude', type=str, nargs='+', metavar='station', help="List of stations to exclude from this processing (e.g. -e igm1 lpgs vbca)")
    parser.add_argument('-p', '--purge', action='store_true', help="Purge year doys from the database and directory structure and re-run the solution.")

    args = parser.parse_args()

    year = args.year[0]
    doys = parseIntSet(args.doys[0])

    # check if doys are correct
    if any([doy for doy in doys if doy < 1]):
        parser.error('DOYs cannot start with zero. Please selected a DOY range between 1-365/366')

    if any([doy for doy in doys if doy == 366]):
        if year % 4 != 0:
            parser.error('Year ' + str(year) + ' is not a leap year: DOY 366 does not exist.')

    print(' >> Reading configuration files and creating project network, please wait...')
    GamitConfig = pyGamitConfig.GamitConfiguration(args.session_cfg[0]) # type: pyGamitConfig.GamitConfiguration

    print(' >> Checing GAMIT tables for requested config and year, please wait...')
    JobServer = pyJobServer.JobServer(GamitConfig, check_gamit_tables=(pyDate.Date(year=year,doy=max(doys)), GamitConfig.gamitopt['eop_type']))

    cnn = dbConnection.Cnn(GamitConfig.gamitopt['gnss_data']) # type: dbConnection.Cnn

    # to exclude stations, append them to GamitConfig.NetworkConfig with a - in front
    exclude = args.exclude
    if exclude is not None:
        print(' >> User selected list of stations to exclude:')
        Utils.print_columns(exclude)
        GamitConfig.NetworkConfig['stn_list'] += ',-' + ',-'.join(exclude)

    # purge solutions if requested
    purge_solutions(cnn, args, year, doys, GamitConfig)

    # initialize project
    Project = Network(cnn, GamitConfig.NetworkConfig, year, doys)  # type: Network

    # done with Gamit config and network
    # generate the GamitSession instances
    Sessions = []
    AllMissingData = []

    tqdm.write(' >> Creating Session Instances, please wait...')
    for doy in tqdm(doys, ncols=80):

        date = pyDate.Date(year=year,doy=doy) # type: pyDate.Date

        # make the dir for these sessions
        # this avoids a racing condition when starting each process
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        if not os.path.exists(pwd):
            os.makedirs(pwd)

        Session_list, Missing_data = Project.CreateGamitSessions(cnn, date, GamitConfig)

        AllMissingData += Missing_data

        Sessions += Session_list

    # print a summary of the current project
    print_summary(Project, AllMissingData)

    # run the job server
    ExecuteGamit(GamitConfig, Sessions, JobServer)

    # execute globk on doys that had to be divided into subnets
    ExecuteGlobk(cnn, GamitConfig, Project, year, doys, Sessions)

    # parse the zenith delay outputs
    ParseZTD(cnn, Sessions, GamitConfig)

    return

def ParseZTD(cnn, Sessions, GamitConfig):

    tqdm.write(' >> Parsing the zenith tropospheric delays...')

    for GamitSession in tqdm(Sessions, ncols=80):

        znd = os.path.join(GamitSession.pwd_glbf, GamitConfig.gamitopt['org'] + GamitSession.date.wwwwd() + '.znd')

        if os.path.isfile(znd):
            # read the content of the file
            f = open(znd, 'r')
            output = f.readlines()
            f.close()

            atmzen = re.findall('ATM_ZEN X (\w+) .. (\d+)\s*(\d*)\s*(\d*)\s*(\d*)\s*(\d*)\s*\d*\s*[- ]?\d*.\d+\s*[+-]*\s*\d*.\d*\s*(\d*.\d*)', ''.join(output), re.MULTILINE)

            for zd in atmzen:

                date = datetime(int(zd[1]), int(zd[2]), int(zd[3]), int(zd[4]), int(zd[5]))

                # translate alias to network.station
                stn = [{'NetworkCode': StnIns.Station.NetworkCode, 'StationCode': StnIns.Station.StationCode} for StnIns in GamitSession.StationInstances if StnIns.Station.StationAlias.upper() == zd[0]][0]

                # see if ZND exists
                rs = cnn.query('SELECT * FROM gamit_ztd WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Date" = \'%s\'' % (stn['NetworkCode'], stn['StationCode'], date.strftime('%Y/%m/%d %H:%M:%S')))

                if rs.ntuples() == 0:
                    cnn.query('INSERT INTO gamit_ztd ("NetworkCode", "StationCode", "Date", "ZTD") VALUES (\'%s\', \'%s\', \'%s\', %f)' % (stn['NetworkCode'], stn['StationCode'], date.strftime('%Y/%m/%d %H:%M:%S'), float(zd[6])))


def ExecuteGlobk(cnn, GamitConfig, Project, year, doys, Sessions):

    tqdm.write(' >> Combining with GLOBK sessions with more than one subnetwork...')

    for doy in tqdm(doys, ncols=80):

        date = pyDate.Date(year=year, doy=doy)  # type: pyDate.Date
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        GlobkComb = []
        Fatal = False

        for GamitSession in Sessions:

            if GamitSession.date == date:
                # add to combination
                GlobkComb.append(GamitSession)

                cmd = 'grep -q \'FATAL\' ' + os.path.join(GamitSession.solution_pwd, 'monitor.log')
                fatal = os.system(cmd)

                if fatal == 0:
                    Fatal = True
                    tqdm.write(' >> GAMIT FATAL found in monitor of session %s %s. This combined solution will not be added to the database.' % (GamitSession.NetName, GamitSession.date.yyyyddd()))

        if not Fatal:
            if len(GlobkComb) > 1:
                # create the combination folder
                pwd_comb = os.path.join(pwd, Project.Name + '/glbf')
                if not os.path.exists(pwd_comb):
                    os.makedirs(pwd_comb)
                else:
                    # delete and recreate
                    rmtree(pwd_comb)
                    os.makedirs(pwd_comb)

                Globk = pyGlobkTask.Globk(pwd_comb, date, GlobkComb)
                Globk.execute()

                # after combining the subnetworks, parse the resulting SINEX
                polyhedron, variance = Globk.parse_sinex()
            else:
                # parse the sinex for the only session for this doy
                polyhedron, variance = GlobkComb[0].parse_sinex()

            # insert polyherdon in gamit_soln table
            for key, value in polyhedron.iteritems():
                if '.' in key:
                    try:
                        cnn.insert('gamit_soln',
                                   NetworkCode = key.split('.')[0],
                                   StationCode = key.split('.')[1],
                                   Project=Project.Name.lower(),
                                   Year=date.year,
                                   DOY=date.doy,
                                   FYear=date.fyear,
                                   X=value.X,
                                   Y=value.Y,
                                   Z=value.Z,
                                   sigmax=value.sigX * sqrt(variance),
                                   sigmay=value.sigY * sqrt(variance),
                                   sigmaz=value.sigZ * sqrt(variance),
                                   sigmaxy=value.sigXY * sqrt(variance),
                                   sigmaxz=value.sigXZ * sqrt(variance),
                                   sigmayz=value.sigYZ * sqrt(variance),
                                   VarianceFactor=variance)
                    except dbConnection.dbErrInsert as e:
                        tqdm.write('    --> Error inserting ' + key + ' -> ' + str(e))
                else:
                    tqdm.write(' >> Invalid key found in session %s -> %s' % (date.yyyyddd(), key))
    return


def ExecuteGamit(Config, Sessions, JobServer):

    def update_gamit_progress_bar(result):
        gamit_pbar.update(1)

        if result['NRMS'] > 0.5:
            msg_nrms = 'WARNING! NRMS > 0.5 (%.3f)' % (result['NRMS'])
        else:
            msg_nrms = ''

        if result['WL'] < 70:
            if msg_nrms:
                msg_wl = ' AND WL fixed < 70%% (%.1f)' % (result['WL'])
            else:
                msg_wl = 'WARNING! WL fixed %.1f' % (result['WL'])
        else:
            msg_wl = ''

        if result['Missing']:
            msg_missing = '\n    Missing sites in solution: ' + ', '.join(result['Missing'])
        else:
            msg_missing = ''

        # DDG: only show sessions with problems to facilitate debugging.
        if result['Success']:
            if msg_nrms + msg_wl + msg_missing:
                tqdm.write(' -- Done processing: ' + result['Session'] + ' -> ' + msg_nrms + msg_wl + msg_missing)

        else:
            tqdm.write(' -- Done processing: ' + result['Session'] + ' -> Failed to complete. Check monitor.log')

    gamit_pbar = tqdm(total=len([GamitSession for GamitSession in Sessions if not GamitSession.ready]),
                      desc='GAMIT sessions completion', ncols=100)  # type: tqdm

    tqdm.write(' >> Initializing %i GAMIT sessions' % (len(Sessions)))

    for GamitSession in Sessions:

        if Config.run_parallel:
            if not GamitSession.ready:

                GamitSession.initialize()

                Task = pyGamitTask.GamitTask(GamitSession.remote_pwd, GamitSession.params, GamitSession.solution_pwd)

                GamitSession.GamitTask = Task

                # do not submit the task if the session is ready!
                JobServer.job_server.submit(Task.start, args=(),
                                    modules=('pyRinex', 'datetime', 'os', 'shutil', 'pyBrdc', 'pySp3', 'subprocess',
                                             're', 'pyPPPETM', 'glob', 'platform', 'traceback'),
                                    callback=update_gamit_progress_bar)
            else:
                tqdm.write(' -- Session already processed: ' + GamitSession.NetName + ' ' + GamitSession.date.yyyyddd())

    tqdm.write(' -- Done initializing GAMIT sessions')

    # once we finnish walking the dir, wait and, handle the output messages
    if Config.run_parallel:
        tqdm.write(' -- Waiting for GAMIT sessions to finish...')
        JobServer.job_server.wait()
        tqdm.write(' -- Done.')

    # handle any output messages during this batch
    gamit_pbar.close()

    if Config.run_parallel:
        print "\n"
        JobServer.job_server.print_stats()

    return


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()

