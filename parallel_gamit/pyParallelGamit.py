"""
Project: Parallel.GAMIT
Date: 3/31/17 6:33 PM
Author: Demian D. Gomez
"""

import pyGamitConfig
import re
import sys
import pyDate
import Utils
import os
from tqdm import tqdm
import pyGamitTask
import pyGlobkTask
from pyNetwork import Network
from datetime import datetime
import dbConnection
from math import sqrt
import shutil
from math import ceil
import argparse
import glob
import pyJobServer
from Utils import process_date
from Utils import process_stnlist
from Utils import parseIntSet
from pyStation import Station
from pyETM import pyETMException
import pyArchiveStruct
import logging
import simplekml
import numpy as np
from itertools import repeat

cnn = None


def print_summary(stations, sessions, dates):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Selected stations (%i):' % (len(stations)))
    Utils.print_columns([item.NetworkCode + '.' + item.StationCode for item in stations])

    min_stn = 99999
    min_date = pyDate.Date(year=1980, doy=1)
    for session in sessions:
        if min_stn > len(session.stations_dict):
            min_stn = len(session.stations_dict)
            min_date = session.date

    print('')
    print(' >> Minimum number of stations (%i) on day %s' % (min_stn, min_date.yyyyddd()))

    # output a summary of the missing days per station:
    print('')
    sys.stdout.write(' >> Summary of data per station (' + unichr(0x258C) + ' = 1 DOY)\n')

    if (dates[1] - dates[0]) / 2. > 120:
        cut_len = int(ceil((dates[1] - dates[0])/4.))
    else:
        cut_len = dates[1] - dates[0]

    for stn in stations:
        # make a group per year
        for year in sorted(set([d.year for d in stn.good_rinex])):

            sys.stdout.write('\n -- %s.%s:\n' % (stn.NetworkCode, stn.StationCode))

            missing_dates = [m.doy for m in stn.missing_rinex if m.year == year]
            p_doys = [m.doy for m in stn.good_rinex if m.year == year]

            sys.stdout.write('\n%i:\n    %03i>' % (year, p_doys[0]))

            for i, doy in enumerate(zip(p_doys[0:-1:2], p_doys[1::2])):

                if doy[0] not in missing_dates and doy[1] not in missing_dates:
                    sys.stdout.write(unichr(0x2588))

                elif doy[0] not in missing_dates and doy[1] in missing_dates:
                    sys.stdout.write(unichr(0x258C))

                elif doy[0] in missing_dates and doy[1] not in missing_dates:
                    sys.stdout.write(unichr(0x2590))

                elif doy[0] in missing_dates and doy[1] in missing_dates:
                    sys.stdout.write(' ')

                if i + 1 == cut_len:
                    sys.stdout.write('<%03i\n' % doy[0])
                    sys.stdout.write('    %03i>' % (doy[0] + 1))

            if len(p_doys) % 2 != 0:
                # last one missing
                if p_doys[-1] not in missing_dates:
                    sys.stdout.write(unichr(0x258C))
                elif p_doys[-1] in missing_dates:
                    sys.stdout.write(' ')

                if cut_len < len(p_doys):
                    sys.stdout.write('< %03i\n' % (p_doys[-1]))
                else:
                    sys.stdout.write('<%03i\n' % (p_doys[-1]))
            else:
                sys.stdout.write('<%03i\n' % (p_doys[-1]))

    return


def purge_solution(pwd, project, date):

    cnn = dbConnection.Cnn('gnss_data.cfg')

    # delete the main solution dir (may be entire GAMIT run or combination directory)
    if os.path.isdir(os.path.join(pwd, project)):
        shutil.rmtree(os.path.join(pwd, project))

    # possible subnetworks
    for sub in glob.glob(os.path.join(pwd, project + '.*')):
        shutil.rmtree(sub)

    # now remove the database entries
    cnn.query('DELETE FROM gamit_soln_excl WHERE "Year" = %i AND "DOY" = %i '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.query('DELETE FROM stacks WHERE "Year" = %i AND "DOY" = %i '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.query('DELETE FROM gamit_soln WHERE "Year" = %i AND "DOY" = %i '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.query('DELETE FROM gamit_stats WHERE "Year" = %i AND "DOY" = %i '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.query('DELETE FROM gamit_subnets WHERE "Year" = %i AND "DOY" = %i '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.query('DELETE FROM gamit_ztd WHERE "Year" = %i AND "DOY" = %i  '
              'AND "Project" = \'%s\'' % (date.year, date.doy, project))

    cnn.close()


def purge_solutions(JobServer, args, dates, GamitConfig):

    if args.purge:

        print(' >> Purging selected year-doys before run:')

        pbar = tqdm(total=len(dates), ncols=80, desc=' -- Purge progress', disable=None)

        modules = ('pyDate', 'dbConnection', 'os', 'glob')

        JobServer.create_cluster(purge_solution, progress_bar=pbar, modules=modules)

        for date in dates:

            # base dir for the GAMIT session directories
            pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

            JobServer.submit(pwd, GamitConfig.NetworkConfig.network_id.lower(), date)

        JobServer.wait()

        pbar.close()

        JobServer.close_cluster()


def station_list(cnn, NetworkConfig, dates):

    stations = process_stnlist(cnn, NetworkConfig['stn_list'].split(','))
    stn_obj = []

    # use the connection to the db to get the stations
    for Stn in tqdm(sorted(stations), ncols=80, disable=None):

        NetworkCode = Stn['NetworkCode']
        StationCode = Stn['StationCode']

        # apply date -1 and date + 1 to avoid problems with files ending at 00:00 of date + 1
        rs = cnn.query(
            'SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
            '"ObservationSTime" >= \'%s\' AND "ObservationETime" <= \'%s\''
            % (NetworkCode, StationCode, (dates[0] - 1).first_epoch(), (dates[1] + 1).last_epoch()))

        if rs.ntuples() > 0:

            tqdm.write(' -- %s.%s -> adding...' % (NetworkCode, StationCode))
            try:
                stn_obj.append(Station(cnn, NetworkCode, StationCode, dates))

            except pyETMException:
                tqdm.write('    %s.%s -> station exists, but there was a problem initializing ETM.'
                           % (NetworkCode, StationCode))
        else:
            tqdm.write(' -- %s.%s -> no data for requested time window' % (NetworkCode, StationCode))

    # analyze duplicate names in the list of stations
    stn_obj = check_station_codes(stn_obj)

    return stn_obj


def check_station_codes(stn_obj):

    for i, stn1 in enumerate(stn_obj[:-1]):

        for stn2 in stn_obj[i+1:]:
            if stn1.NetworkCode != stn2.NetworkCode and stn1.StationCode == stn2.StationCode:
                # duplicate StationCode (different Network), produce Alias
                unique = False
                while not unique:
                    stn1.generate_alias()
                    # compare again to make sure this name is unique
                    unique = compare_aliases(stn1, stn_obj)

    return stn_obj


def compare_aliases(Station, AllStations):

    # make sure alias does not exists as alias and station code

    for stn in AllStations:

        # this if prevents comparing against myself, although the station is not added until after
        # the call to CompareAliases. But, just in case...
        if stn.StationCode != Station.StationCode and stn.NetworkCode != Station.NetworkCode and \
                        Station.StationAlias == stn.StationAlias or Station.StationAlias == stn.StationCode:
            # not unique!
            return False

    return True


def main():

    global cnn

    parser = argparse.ArgumentParser(description='Parallel.GAMIT main execution program')

    parser.add_argument('session_cfg', type=str, nargs=1, metavar='session.cfg',
                        help="Filename with the session configuration to run Parallel.GAMIT")
    parser.add_argument('-d', '--date', type=str, nargs=2, metavar='{date}',
                        help="Date range to process. Can be specified in yyyy/mm/dd yyyy_doy wwww-d format")
    parser.add_argument('-dp', '--date_parser', type=str, nargs=2, metavar='{year} {doys}',
                        help="Parse date using ranges and commas (e.g. 2018 1,3-6). "
                             "Cannot cross year boundaries")
    parser.add_argument('-e', '--exclude', type=str, nargs='+', metavar='station',
                        help="List of stations to exclude from this processing (e.g. -e igm1 lpgs vbca)")
    parser.add_argument('-p', '--purge', action='store_true',
                        help="Purge year doys from the database and directory structure and re-run the solution.")
    parser.add_argument('-dry', '--dry_run', action='store_true',
                        help="Generate the directory structures (locally) but do not run GAMIT. "
                             "Output is left in the production directory.")
    parser.add_argument('-kml', '--generate_kml', action='store_true',
                        help="Generate KML and exit without running GAMIT.")

    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    dates = None
    drange = None
    try:
        if args.date_parser:
            year = int(args.date_parser[0])
            doys = parseIntSet(args.date_parser[1])

            if any([doy for doy in doys if doy < 1]):
                parser.error('DOYs cannot start with zero. Please selected a DOY range between 1-365/366')

            if 366 in doys:
                if year % 4 != 0:
                    parser.error('Year ' + str(year) + ' is not a leap year: DOY 366 does not exist.')

            dates = [pyDate.Date(year=year, doy=i) for i in doys]
            drange = [dates[0], dates[-1]]
        else:
            drange = process_date(args.date, missing_input=None)

            if not all(drange):
                parser.error('Must specify a start and end date for the processing.')

            # get the dates to purge
            dates = [pyDate.Date(mjd=i) for i in range(drange[0].mjd, drange[1].mjd + 1)]

    except ValueError as e:
        parser.error(str(e))

    print(' >> Reading configuration files and creating project network, please wait...')

    GamitConfig = pyGamitConfig.GamitConfiguration(args.session_cfg[0])  # type: pyGamitConfig.GamitConfiguration

    print(' >> Checing GAMIT tables for requested config and year, please wait...')

    JobServer = pyJobServer.JobServer(GamitConfig,
                                      check_gamit_tables=(pyDate.Date(year=drange[1].year, doy=drange[1].doy),
                                                          GamitConfig.gamitopt['eop_type']),
                                      run_parallel=not args.noparallel,
                                      software_sync=GamitConfig.gamitopt['gamit_remote_local'])

    cnn = dbConnection.Cnn(GamitConfig.gamitopt['gnss_data'])  # type: dbConnection.Cnn

    # to exclude stations, append them to GamitConfig.NetworkConfig with a - in front
    exclude = args.exclude
    if exclude is not None:
        print(' >> User selected list of stations to exclude:')
        Utils.print_columns(exclude)
        GamitConfig.NetworkConfig['stn_list'] += ',-' + ',-'.join(exclude)

    if args.dry_run is not None:
        dry_run = args.dry_run
    else:
        dry_run = False

    if not dry_run:
        # ignore if calling a dry run
        # purge solutions if requested
        purge_solutions(JobServer, args, dates, GamitConfig)

    # initialize stations in the project
    stations = station_list(cnn, GamitConfig.NetworkConfig, drange)

    tqdm.write(' >> Creating GAMIT session instances, please wait...')

    sessions = []
    archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct

    for date in tqdm(dates, ncols=80, disable=None):

        # make the dir for these sessions
        # this avoids a racing condition when starting each process
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        if not os.path.exists(pwd):
            os.makedirs(pwd)

        net_object = Network(cnn, archive, GamitConfig, stations, date)

        sessions += net_object.sessions

    if args.generate_kml:
        # generate a KML of the sessions
        generate_kml(dates, sessions, GamitConfig)
        exit()

    # print a summary of the current project (NOT VERY USEFUL AFTER ALL)
    # print_summary(stations, sessions, drange)

    # run the job server
    ExecuteGamit(sessions, JobServer, dry_run)

    # execute globk on doys that had to be divided into subnets
    if not args.dry_run:
        ExecuteGlobk(GamitConfig, sessions, dates)

        # parse the zenith delay outputs
        ParseZTD(GamitConfig.NetworkConfig.network_id, sessions, GamitConfig)

    print(' >> Done processing and parsing information. Successful exit from Parallel.GAMIT')


def generate_kml(dates, sessions, GamitConfig):

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    # define styles
    styles_stn = simplekml.StyleMap()
    styles_stn.normalstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_stn.normalstyle.iconstyle.color = 'ff00ff00'
    styles_stn.normalstyle.labelstyle.scale = 0
    styles_stn.highlightstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_stn.highlightstyle.iconstyle.color = 'ff00ff00'
    styles_stn.highlightstyle.labelstyle.scale = 2

    styles_tie = simplekml.StyleMap()
    styles_tie.normalstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_tie.normalstyle.iconstyle.color = 'ff0000ff'
    styles_tie.normalstyle.labelstyle.scale = 0
    styles_tie.highlightstyle.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'
    styles_tie.highlightstyle.iconstyle.color = 'ff0000ff'
    styles_tie.highlightstyle.labelstyle.scale = 2

    for date in tqdm(dates, ncols=80, disable=None):

        folder = kml.newfolder(name=date.yyyyddd())

        sess = []
        for session in sessions:
            if session.date == date:
                sess.append(session)

        if len(sess) > 1:
            for session in sess:
                folder_net = folder.newfolder(name=session.NetName)

                for stn in session.stations_dict:
                    pt = folder_net.newpoint(**stn)
                    if stn in session.tie_dict:
                        pt.stylemap = styles_tie
                    else:
                        pt.stylemap = styles_stn

        elif len(sess) == 1:
            for stn in sess[0].stations_dict:
                pt = folder.newpoint(**stn)
                pt.stylemap = styles_stn

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + GamitConfig.NetworkConfig.network_id.lower() + '.kmz')


def ParseZTD(project, Sessions, GamitConfig):

    global cnn

    tqdm.write(' >> Parsing the zenith tropospheric delays...')

    # atmospheric zenith delay list
    atmzen = []
    # a dictionary for the station aliases lookup table
    alias = dict()

    for GamitSession in tqdm(Sessions, ncols=80, disable=None):
        try:
            znd = os.path.join(GamitSession.pwd_glbf, GamitConfig.gamitopt['org'] + GamitSession.date.wwwwd() + '.znd')

            if os.path.isfile(znd):
                # read the content of the file
                f = open(znd, 'r')
                output = f.readlines()
                f.close()
                v = re.findall(r'ATM_ZEN X (\w+) .. (\d+)\s*(\d*)\s*(\d*)\s*(\d*)\s*(\d*)\s*\d*\s*([- ]?'
                               r'\d*.\d+)\s*[+-]*\s*(\d*.\d*)\s*(\d*.\d*)', ''.join(output), re.MULTILINE)
                # add the year doy tuple to the result
                atmzen += [i + (GamitSession.date.year, GamitSession.date.doy) for i in v]
            else:
                v = []

            # create a lookup table for station aliases
            for zd in v:
                for StnIns in GamitSession.StationInstances:
                    if StnIns.StationAlias.upper() == zd[0]:
                        alias[zd[0]] = [StnIns.NetworkCode, StnIns.StationCode]

        except Exception as e:
            tqdm.write(' -- Error parsing zenith delays for session %s: %s' % (GamitSession.NetName, str(e)))

    if not len(atmzen):
        tqdm.write(' -- No sessions with usable atmospheric zenith delays were found!')
        return

    # all station days are in the atmzen
    # convert to numpy to sort and average

    atmzen = np.array(atmzen, dtype=[('stn', 'S4'), ('y', 'i4'), ('m', 'i4'), ('d', 'i4'), ('h', 'i4'), ('mm', 'i4'),
                                     ('mo', 'float64'), ('s', 'float64'), ('z', 'float64'),
                                     ('yr', 'i4'), ('doy', 'i4')])

    atmzen.sort(order=['stn', 'y', 'm', 'd', 'h', 'mm'])

    tqdm.write(' -- Averaging zenith delays from stations in multiple sessions...')
    # get the stations in the processing
    stations = np.unique(atmzen['stn'])
    # get the unique dates for this process
    date_vec = np.unique(np.array([atmzen['yr'], atmzen['doy']]).transpose(), axis=0)
    # unique ztd
    uztd = []
    for stn in stations:
        for date in date_vec:
            # select the station and date
            zd = atmzen[np.logical_and.reduce((atmzen['stn'] == stn,
                                               atmzen['yr'] == date[0], atmzen['doy'] == date[1]))]
            # careful, don't do anything if there is no data for this station-day
            if zd.size > 0:
                # find the unique days
                days = np.unique(np.array([zd['y'], zd['m'], zd['d'], zd['h'], zd['mm']]).transpose(), axis=0)
                # average over the existing records
                for d in days:
                    rows = zd[np.logical_and.reduce((zd['y'] == d[0], zd['m'] == d[1],
                                                     zd['d'] == d[2], zd['h'] == d[3], zd['mm'] == d[4]))]

                    uztd.append(alias[stn] + [datetime(d[0], d[1], d[2], d[3], d[4]).strftime('%Y-%m-%d %H:%M:%S')] +
                                [project.lower()] +
                                [np.mean(rows['z']) - np.mean(rows['mo']), np.mean(rows['s']), np.mean(rows['z'])] +
                                date.tolist())

    # drop all records from the database to make sure there will be no problems with massive insert
    tqdm.write(' -- Deleting previous zenith tropospheric delays from the database...')
    for date in date_vec:
        cnn.query('DELETE FROM gamit_ztd WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                  % (project.lower(), date[0], date[1]))

    # now do a bulk insert
    try:
        tqdm.write(' -- Inserting zenith tropospheric delays (%i) into the database...' % len(uztd))

        for ztd in uztd:
            cnn.insert('gamit_ztd',
                       NetworkCode=ztd[0],
                       StationCode=ztd[1],
                       Date=ztd[2],
                       Project=ztd[3],
                       model=ztd[4],
                       sigma=ztd[5],
                       ZTD=ztd[6],
                       Year=ztd[7],
                       DOY=ztd[8])
        # cnn.executemany('INSERT INTO gamit_ztd ("NetworkCode", "StationCode", "Date", "Project", "model", "sigma", '
        #                '                       "ZTD", "Year", "DOY") VALUES (%s, %s, %s, %s, %f, %f, %f, %i, %i)',
        #                uztd)
    except Exception as e:
        tqdm.write(' -- Error inserting parsed zenith delays: %s' % str(e))


def ExecuteGlobk(GamitConfig, sessions, dates):

    global cnn

    project = GamitConfig.NetworkConfig.network_id.lower()

    tqdm.write(' >> Combining with GLOBK sessions with more than one subnetwork...')

    for date in tqdm(dates, ncols=80, disable=None):

        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        GlobkComb = []
        Fatal = False

        for GamitSession in sessions:

            if GamitSession.date == date:
                # add to combination
                GlobkComb.append(GamitSession)

                cmd = 'grep -q \'FATAL\' ' + os.path.join(GamitSession.solution_pwd, 'monitor.log')
                fatal = os.system(cmd)

                if fatal == 0:
                    Fatal = True
                    tqdm.write(' >> GAMIT FATAL found in monitor of session %s %s. This combined solution will not be '
                               'added to the database.' % (GamitSession.NetName, GamitSession.date.yyyyddd()))

        if not Fatal:
            if len(GlobkComb) > 1:
                # create the combination folder
                pwd_comb = os.path.join(pwd, project + '/glbf')
                if not os.path.exists(pwd_comb):
                    os.makedirs(pwd_comb)
                else:
                    # delete and recreate
                    shutil.rmtree(pwd_comb)
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
                                   NetworkCode=key.split('.')[0],
                                   StationCode=key.split('.')[1],
                                   Project=project,
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
                        # tqdm.write('    --> Error inserting ' + key + ' -> ' + str(e))
                        pass
                else:
                    tqdm.write(' >> Invalid key found in session %s -> %s' % (date.yyyyddd(), key))
    return


def callback_handle(job):

    global cnn

    result = job.result

    if result is not None:
        msg = []
        if 'error' not in result.keys():
            if result['nrms'] > 1:
                msg.append('    > NRMS > 1.0 (%.3f)' % result['nrms'])

            if result['wl'] < 60:
                msg.append('    > WL fixed < 60 (%.1f)' % result['wl'])

            if result['missing']:
                msg.append('    > Missing sites in solution: ' + ', '.join(result['missing']))

            # DDG: only show sessions with problems to facilitate debugging.
            if result['success']:
                if len(msg) > 0:
                    tqdm.write(' -- Done processing: %s -> WARNINGS:\n%s' % (result['session'], '\n'.join(msg)))

                # insert information in gamit_stats
                try:
                    cnn.insert('gamit_stats', result)
                except dbConnection.dbErrInsert as e:
                    tqdm.write(' -- Error while inserting GAMIT stat for %s: ' % result['session'] + str(e))

            else:
                tqdm.write(' -- Done processing: %s -> FATAL:\n%s' % (result['session'],
                                                                      '    > Failed to complete. Check monitor.log'))
                # write FATAL to file
                f = open('FATAL.log', 'a')
                f.write('ON %s session %s -> FATAL: Failed to complete. Check monitor.log\n'
                        % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), result['session']))
                f.close()
        else:
            tqdm.write(' -- Error in session %s message from node follows -> \n%s'
                       % (result['session'], result['error']))

    else:
        tqdm.write(' -- Fatal error on node %s message from node follows -> \n%s' % (job.ip_addr, job.exception))


def run_gamit_session(gamit_task, dir_name, year, doy, dry_run):

    return gamit_task.start(dir_name, year, doy, dry_run)


def ExecuteGamit(Sessions, JobServer, dry_run=False):

    gamit_pbar = tqdm(total=len([GamitSession for GamitSession in Sessions if not GamitSession.ready]),
                      desc=' >> GAMIT sessions completion', ncols=100, disable=None)  # type: tqdm

    tqdm.write(' >> Initializing %i GAMIT sessions' % (len(Sessions)))

    # For debugging parallel python runs
    # console = logging.FileHandler('pp.log')
    # console.setLevel(logging.DEBUG)
    # JobServer.job_server.logger.setLevel(logging.DEBUG)
    # formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)-8s %(message)s')
    # console.setFormatter(formatter)
    # JobServer.job_server.logger.addHandler(console)

    modules = ('pyRinex', 'datetime', 'os', 'shutil', 'pyBrdc', 'pySp3', 'subprocess', 're', 'pyETM', 'glob',
               'platform', 'traceback')

    JobServer.create_cluster(run_gamit_session, (pyGamitTask.GamitTask,), callback_handle, gamit_pbar, modules=modules)

    gtasks = []

    for GamitSession in Sessions:
        if not GamitSession.ready:
            # do not submit the task if the session is ready!
            GamitSession.initialize()
            task = pyGamitTask.GamitTask(GamitSession.remote_pwd, GamitSession.params, GamitSession.solution_pwd)

            JobServer.submit(task, task.params['DirName'], task.date.year, task.date.doy, dry_run)

            # save it just in case...
            gtasks.append(task)
        else:
            tqdm.write(' -- Session already processed: ' + GamitSession.NetName + ' ' + GamitSession.date.yyyyddd())

    tqdm.write(' -- Done initializing and submitting GAMIT sessions')

    JobServer.wait()

    gamit_pbar.close()

    JobServer.close_cluster()


if __name__ == '__main__':
    main()

