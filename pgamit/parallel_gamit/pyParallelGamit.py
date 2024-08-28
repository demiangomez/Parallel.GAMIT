"""
Project: Parallel.GAMIT
Date: 3/31/17 6:33 PM
Author: Demian D. Gomez
"""

import sys
import os
import math
import shutil
import argparse
import glob
import logging
import time
import threading
from datetime import datetime
import random
import string

# deps
from tqdm import tqdm
import simplekml

# app
import pyGamitConfig
import pyDate
import Utils
import pyGamitTask
import pyGlobkTask
import pyGamitSession
import dbConnection
import pyJobServer
import pyParseZTD
import pyArchiveStruct
from pyETM import pyETMException
from pyNetwork import Network
from pyStation import (Station,
                       StationCollection)
from Utils import (process_date,
                   process_stnlist,
                   parseIntSet,
                   indent,
                   file_append,
                   stationID
                   )


def prYellow(skk):
    if os.fstat(0) == os.fstat(1):
        return "\033[93m{}\033[00m" .format(skk)
    else:
        return skk


def prRed(skk):
    if os.fstat(0) == os.fstat(1):
        return "\033[91m{}\033[00m" .format(skk)
    else:
        return skk


def prGreen(skk):
    if os.fstat(0) == os.fstat(1):
        return "\033[92m{}\033[00m" .format(skk)
    else:
        return skk


class DbAlive(object):
    def __init__(self, cnn, increment):
        self.next_t    = time.time()
        self.done      = False
        self.increment = increment
        self.cnn       = cnn
        self.run()

    def run(self):
        _ = self.cnn.query('SELECT * FROM networks')
        # tqdm.write('%s -> keeping db alive' % print_datetime())
        self.next_t += self.increment
        if not self.done:
            threading.Timer(self.next_t - time.time(), self.run).start()

    def stop(self):
        self.done = True


def print_summary(stations, sessions, dates):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Selected stations (%i):' % (len(stations)))
    Utils.print_columns([stationID(item) for item in stations])

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
    sys.stdout.write(' >> Summary of data per station (' + chr(0x258C) + ' = 1 DOY)\n')

    if (dates[1] - dates[0]) / 2.0 > 120:
        cut_len = int(math.ceil((dates[1] - dates[0])/4.0))
    else:
        cut_len = dates[1] - dates[0]

    for stn in stations:
        # make a group per year
        for year in sorted(set(d.year for d in stn.good_rinex)):

            sys.stdout.write('\n -- %s:\n' % stationID(stn))

            missing_dates = set(m.doy for m in stn.missing_rinex if m.year == year)
            p_doys        = [m.doy for m in stn.good_rinex    if m.year == year]

            sys.stdout.write('\n%i:\n    %03i>' % (year, p_doys[0]))

            for i, doy in enumerate(zip(p_doys[0:-1:2], p_doys[1::2])):

                if doy[0] in missing_dates:
                    if doy[1] in missing_dates:
                        c = ' '
                    else:
                        c = chr(0x2590)
                else:
                    if doy[1] in missing_dates:
                        c = chr(0x258C)
                    else:
                        c = chr(0x2588)

                sys.stdout.write(c)

                if i + 1 == cut_len:
                    sys.stdout.write('<%03i\n' % doy[0])
                    sys.stdout.write('    %03i>' % (doy[0] + 1))

            if len(p_doys) % 2 != 0:
                # last one missing
                if p_doys[-1] in missing_dates:
                    sys.stdout.write(' ')
                else:
                    sys.stdout.write(chr(0x258C))

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
    project_path = os.path.join(pwd, project)
    if os.path.isdir(project_path):
        shutil.rmtree(project_path)

    # possible subnetworks
    for sub in glob.glob(project_path +  '.*'):
        shutil.rmtree(sub)

    # now remove the database entries
    for table in ('gamit_soln_excl', 'stacks', 'gamit_soln', 'gamit_stats',
                  'gamit_subnets', 'gamit_ztd'):
        cnn.query('DELETE FROM %s WHERE "Year" = %i AND "DOY" = %i '
                  'AND "Project" = \'%s\'' % (table, date.year, date.doy, project))

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


def station_list(cnn, stations, dates):

    stations = process_stnlist(cnn, stations)
    stn_obj  = StationCollection()

    # use the connection to the db to get the stations
    for Stn in tqdm(sorted(stations, key = lambda s : (s['NetworkCode'], s['StationCode'])), 
                    ncols=80, disable=None):

        NetworkCode = Stn['NetworkCode']
        StationCode = Stn['StationCode']

        rs = cnn.query(
            'SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
            '("ObservationYear", "ObservationDOY") BETWEEN (%s) AND (%s)'
            % (NetworkCode, StationCode,
               dates[0].yyyy() + ', ' + dates[0].ddd(),
               dates[1].yyyy() + ', ' + dates[1].ddd()))

        if rs.ntuples() > 0:
            tqdm.write(prGreen(' -- %s -> adding...' % stationID(Stn)))
            try:
                stn_obj.append(Station(cnn, NetworkCode, StationCode, dates))
            except pyETMException:
                tqdm.write(prRed('    %s -> station exists, but there was a problem initializing ETM.'
                                 % stationID(Stn)))
        else:
            tqdm.write(prYellow(' -- %s -> no data for requested time window' % stationID(Stn)))

    return stn_obj


def print_datetime():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def id_generator(size=4, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def check_station_alias(cnn):
    # this method takes all stations, ordered by first RINEX file, and checks if other stations with same StationCode
    # exist in the database. If there are and have no alias, then assign fixed alias to it

    rs = cnn.query('SELECT "StationCode", count(*) FROM stations WHERE "NetworkCode" not like \'?%\' '
                   'GROUP BY "StationCode" HAVING count(*) > 1')

    if rs is not None:
        for rec in rs.dictresult():
            StationCode = rec['StationCode']

            stn = cnn.query(f'SELECT * FROM stations WHERE "StationCode" = \'{StationCode}\' AND alias IS NULL '
                            f'ORDER BY "DateStart"')
            # loop through each one except the first, which will keep its original name
            for i, s in enumerate(stn.dictresult()):
                if i > 0:
                    # make sure the id is unique
                    unique = False
                    stn_id = id_generator()
                    while not unique:
                        if len(cnn.query(f'SELECT * FROM stations WHERE "alias" = \'{stn_id}\' OR '
                                         f'"StationCode" = \'{stn_id}\'').dictresult()) == 0:
                            unique = True
                        else:
                            stn_id = id_generator()

                    NetworkCode = s['NetworkCode']
                    print(f' -- Duplicate station code without alias: {NetworkCode}.{StationCode} -> {stn_id}')
                    cnn.update('stations', {'alias': stn_id}, StationCode=StationCode, NetworkCode=NetworkCode)


def main():

    parser = argparse.ArgumentParser(description='Parallel.GAMIT main execution program')

    parser.add_argument('session_cfg', type=str, nargs=1, metavar='session.cfg',
                        help="Filename with the session configuration to run Parallel.GAMIT")

    parser.add_argument('-d', '--date', type=str, nargs=2, metavar='{date}',
                        help="Date range to process. Can be specified in yyyy/mm/dd yyyy_doy wwww-d format")

    parser.add_argument('-dp', '--date_parser', type=str, nargs=2, metavar='{year} {doys}',
                        help="Parse date using ranges and commas (e.g. 2018 1,3-6). "
                             "Cannot cross year boundaries")

    parser.add_argument('-e', '--exclude', type=str, nargs='+', metavar='{station}',
                        help="List of stations to exclude from this processing (e.g. -e igm1 lpgs vbca)")

    parser.add_argument('-c', '--check_mode', type=str, nargs='+', metavar='{station}',
                        help="Check station(s) mode. If station(s) are not present in the GAMIT polyhedron, "
                             "(i.e. the RINEX file(s) were missing at the time of the processing) Parallel.GAMIT will "
                             "add the station to the closest subnetwork(s) and reprocess them. If station(s) were "
                             "present at the time of the processing but failed to process (i.e. they are in the "
                             "missing stations list), these subnetworks will be reprocessed to try to obtain a "
                             "solution. Station list provided in the cfg is ignored in this mode. Therefore, changes "
                             "in the station list will not produce any changes in network configuration. Purge not "
                             "allowed when using this mode. (Syntax: -c igm1 lpgs rms.vbca)")

    parser.add_argument('-i', '--ignore_missing', action='store_true',
                        help="When using check mode or processing existing sessions, ignore missing stations. In other "
                             "words, do not try to reprocess sessions that have missing solutions.")

    parser.add_argument('-p', '--purge', action='store_true', default=False,
                        help="Purge year doys from the database and directory structure and re-run the solution.")

    parser.add_argument('-dry', '--dry_run', action='store_true',
                        help="Generate the directory structures (locally) but do not run GAMIT. "
                             "Output is left in the production directory.")

    parser.add_argument('-kml', '--create_kml', action='store_true',
                        help="Create a KML with everything processed in this run.")

    parser.add_argument('-np', '--noparallel', action='store_true',
                        help="Execute command without parallelization.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')  # type: dbConnection.Cnn

    # DDG: new station alias check is run every time we start GAMIT. Station with duplicate names are assigned a unique
    # alias that is used for processing
    print(' >> Checking station duplicates and assigning aliases if needed')
    check_station_alias(cnn)

    dates = None
    drange = None
    try:
        if args.date_parser:
            year = int(args.date_parser[0])
            doys = parseIntSet(args.date_parser[1])

            if any(doy for doy in doys if doy < 1):
                parser.error('DOYs cannot start with zero. Please selected a DOY range between 1-365/366')

            if 366 in doys:
                if year % 4 != 0:
                    parser.error('Year ' + str(year) + ' is not a leap year: DOY 366 does not exist.')

            dates  = [pyDate.Date(year=year, doy=i) for i in doys]
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

    print(' >> Checking GAMIT tables for requested config and year, please wait...')

    JobServer = pyJobServer.JobServer(GamitConfig,
                                      check_gamit_tables = (pyDate.Date(year=drange[1].year, doy=drange[1].doy),
                                                           GamitConfig.gamitopt['eop_type']),
                                      run_parallel = not args.noparallel,
                                      software_sync = GamitConfig.gamitopt['gamit_remote_local'])

    # to exclude stations, append them to GamitConfig.NetworkConfig with a - in front
    exclude = args.exclude
    if exclude is not None:
        print(' >> User selected list of stations to exclude:')
        Utils.print_columns(exclude)
        GamitConfig.NetworkConfig['stn_list'] += ',-' + ',-'.join(exclude)

    # initialize stations in the project
    stations = station_list(cnn, GamitConfig.NetworkConfig['stn_list'].split(','), drange)

    check_station_list = args.check_mode
    if check_station_list is not None:
        print(' >> Check mode. List of stations to check for selected days:')
        Utils.print_columns(check_station_list)
        check_stations = station_list(cnn, check_station_list, drange)
    else:
        check_stations = StationCollection()

    dry_run = False if args.dry_run is None else args.dry_run

    if not dry_run and not len(check_stations):
        # ignore if calling a dry run
        # purge solutions if requested
        purge_solutions(JobServer, args, dates, GamitConfig)
    elif args.purge:
        tqdm.write(' >> Dry run or check mode activated. Cannot purge solutions in this mode.')

    # run the job server
    sessions = ExecuteGamit(cnn, JobServer, GamitConfig, stations, check_stations, args.ignore_missing, dates,
                            args.dry_run, args.create_kml)

    # execute globk on doys that had to be divided into subnets
    if not args.dry_run:
        ExecuteGlobk(cnn, JobServer, GamitConfig, sessions, dates)

        # parse the zenith delay outputs
        ParseZTD(GamitConfig.NetworkConfig.network_id.lower(), dates, sessions, GamitConfig, JobServer)

    tqdm.write(' >> %s Successful exit from Parallel.GAMIT' % print_datetime())


def generate_kml(dates, sessions, GamitConfig):

    tqdm.write(' >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    # define styles
    ICON = 'http://maps.google.com/mapfiles/kml/shapes/placemark_square.png'

    styles_stn = simplekml.StyleMap()
    styles_stn.normalstyle.iconstyle.icon.href    = ICON
    styles_stn.normalstyle.iconstyle.color        = 'ff00ff00'
    styles_stn.normalstyle.labelstyle.scale       = 0
    styles_stn.highlightstyle.iconstyle.icon.href = ICON
    styles_stn.highlightstyle.iconstyle.color     = 'ff00ff00'
    styles_stn.highlightstyle.labelstyle.scale    = 2

    styles_tie = simplekml.StyleMap()
    styles_tie.normalstyle.iconstyle.icon.href    = ICON
    styles_tie.normalstyle.iconstyle.color        = 'ff0000ff'
    styles_tie.normalstyle.labelstyle.scale       = 0
    styles_tie.highlightstyle.iconstyle.icon.href = ICON
    styles_tie.highlightstyle.iconstyle.color     = 'ff0000ff'
    styles_tie.highlightstyle.labelstyle.scale    = 2

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


def ParseZTD(project, dates, Sessions, GamitConfig, JobServer):

    tqdm.write(' >> %s Parsing the tropospheric zenith delays...' % print_datetime())

    modules = ('numpy', 'os', 're', 'datetime', 'traceback', 'dbConnection')

    pbar = tqdm(total=len(dates), disable=None, desc=' >> Zenith total delay parsing', ncols=100)

    JobServer.create_cluster(run_parse_ztd, (pyParseZTD.ParseZtdTask, pyGamitSession.GamitSession),
                             job_callback, pbar, modules=modules)

    # parse and insert one day at the time, otherwise, the process becomes too slow for long runs
    for date in dates:
        # get all the session of this day
        sessions = [s for s in Sessions if s.date == date]
        task = pyParseZTD.ParseZtdTask(GamitConfig, project, sessions, date)
        JobServer.submit(task)

    JobServer.wait()
    pbar.close()
    JobServer.close_cluster()


def ExecuteGlobk(cnn, JobServer, GamitConfig, sessions, dates):

    project = GamitConfig.NetworkConfig.network_id.lower()

    tqdm.write(' >> %s Combining with GLOBK sessions with more than one subnetwork...'
               % print_datetime())

    modules = ('os', 'shutil', 'snxParse', 'subprocess', 'platform', 'traceback', 'glob', 'dbConnection', 'math',
               'datetime', 'pyDate')

    pbar = tqdm(total=len(dates), disable=None, desc=' >> GLOBK combinations completion', ncols=100)

    JobServer.create_cluster(run_globk, (pyGlobkTask.Globk, pyGamitSession.GamitSession),
                             job_callback, progress_bar=pbar, modules=modules)

    net_type = GamitConfig.NetworkConfig.type

    for date in dates:
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        GlobkComb = []
        Fatal = False

        for GamitSession in sessions:

            if GamitSession.date == date:
                # add to combination
                GlobkComb.append(GamitSession)

                #if os.path.isfile(os.path.join(GamitSession.solution_pwd, 'monitor.log')):
                #    cmd = 'grep -q \'FATAL\' ' + os.path.join(GamitSession.solution_pwd, 'monitor.log')
                #    fatal = os.system(cmd)
                #else:
                #    fatal = 0

                # check the database to see that the solution was successful
                rn = cnn.query_float('SELECT * from gamit_stats WHERE "Project" = \'%s\' AND "Year" = %i AND '
                                     '"DOY" = %i AND "subnet" = %i'
                                     % (GamitSession.NetName, 
                                        GamitSession.date.year, 
                                        GamitSession.date.doy,
                                        GamitSession.subnet if GamitSession.subnet is not None else 0))
                # if fatal == 0:
                if not len(rn):
                    Fatal = True
                    tqdm.write(' >> GAMIT FATAL found in monitor of session %s %s (or no monitor.log file). '
                               'This combined solution will not be added to the database.'
                               % (GamitSession.date.yyyyddd(), 
                                  GamitSession.DirName))
                    break

        if not Fatal:
            # folder where the combination (or final solution if single network) should be written to
            pwd_comb = os.path.join(pwd, project + '/glbf')
            # globk combination object
            globk = pyGlobkTask.Globk(pwd_comb, date, GlobkComb, net_type)
            JobServer.submit(globk, project, date)

    JobServer.wait()
    pbar.close()
    JobServer.close_cluster()

    tqdm.write(' >> %s Done combining subnetworks' % print_datetime())


def gamit_callback(job):

    results = job.result

    if results is not None:
        for result in results:
            msg = []
            if 'error' not in result.keys():
                if result['nrms'] > 1:
                    msg.append(f'    > NRMS > 1.0 ({result["nrms"]:.3f}) in solution {result["session"]}')

                if result['wl'] < 60:
                    msg.append(f'    > WL fixed < 60 ({result["wl"]:.1f}) in solution {result["session"]}')

                # do not display missing stations anymore, at least for now
                # if result['missing']:
                #    msg.append(f'    > Missing sites in {result["session"]}: {", ".join(result["missing"])}')

                # DDG: only show sessions with problems to facilitate debugging.
                if result['success']:
                    if len(msg) > 0:
                        tqdm.write(prYellow(f' -- {print_datetime()} finished: {result["session"]} '
                                            f'system {result["system"]} -> WARNINGS:\n' + '\n'.join(msg) + '\n'))

                    # insert information in gamit_stats
                    try:
                        cnn = dbConnection.Cnn('gnss_data.cfg')  # type: dbConnection.Cnn
                        cnn.insert('gamit_stats', result)
                        cnn.close()
                    except dbConnection.dbErrInsert as e:
                        tqdm.write(prRed(f' -- {print_datetime()} Error while inserting GAMIT stat for '
                                         f'{result["session"]} system: {result["system"]}' + str(e)))

                else:
                    tqdm.write(prRed(f' -- {print_datetime()} finished: {result["session"]} system {result["system"]} '
                                     f'-> FATAL:\n'
                                     f'    > Failed to complete. Check monitor.log:\n'
                                     + indent("\n".join(result["fatals"]), 4) + '\n'))

                    # write FATAL to file
                    file_append('FATAL.log',
                                f'ON {print_datetime()} session {result["session"]} system {result["system"]} '
                                f'-> FATAL: Failed to complete. Check monitor.log\n'
                                + indent("\n".join(result["fatals"]), 4) + '\n')
            else:
                tqdm.write(prRed(f' -- {print_datetime()} Error in session {result["session"]} '
                                 f'system {result["system"]} message from node follows -> \n{result["error"]}'))

                file_append('FATAL.log',
                            f'ON {print_datetime()} error in session {result["session"]} '
                            f'system {result["system"]} message from node follows -> \n{result["error"]}')

    else:
        tqdm.write(' -- %s Fatal error on node %s message from node follows -> \n%s'
                   % (print_datetime(), job.ip_addr, job.exception))


def job_callback(job):
    result = job.result

    if result is not None:
        for e in result:
            tqdm.write(e)
    else:
        tqdm.write(' -- %s Fatal error on node %s message from node follows -> \n%s'
                   % (print_datetime(), job.ip_addr, job.exception))


def run_gamit_session(gamit_task, dir_name, year, doy, dry_run):

    return gamit_task.start(dir_name, year, doy, dry_run)


def run_globk(globk_task, project, date):

    from datetime import datetime
    polyhedron, variance = globk_task.execute()
    # open a database connection (this is on the node)
    cnn = dbConnection.Cnn('gnss_data.cfg')
    err = []

    # kill the existing polyhedron to make sure all the new vertices get in
    # this is because when adding a station, only the
    cnn.query('DELETE FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
              % (project, date.year, date.doy))

    # insert polyherdon in gamit_soln table
    for key, value in polyhedron.items():
        if '.' in key:
            try:
                sqrt_variance = math.sqrt(variance)
                cnn.insert('gamit_soln',
                           NetworkCode    = key.split('.')[0],
                           StationCode    = key.split('.')[1],
                           Project        = project,
                           Year           = date.year,
                           DOY            = date.doy,
                           FYear          = date.fyear,
                           X              = value.X,
                           Y              = value.Y,
                           Z              = value.Z,
                           sigmax         = value.sigX  * sqrt_variance,
                           sigmay         = value.sigY  * sqrt_variance,
                           sigmaz         = value.sigZ  * sqrt_variance,
                           sigmaxy        = value.sigXY * sqrt_variance,
                           sigmaxz        = value.sigXZ * sqrt_variance,
                           sigmayz        = value.sigYZ * sqrt_variance,
                           VarianceFactor = variance)
            except dbConnection.dbErrInsert as e:
                # tqdm.write('    --> Error inserting ' + key + ' -> ' + str(e))
                pass
        else:
            err.append(' -- %s Error while combining with GLOBK -> Invalid key found in session %s -> %s '
                       'polyhedron in database may be incomplete.'
                       % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), date.yyyyddd(), key))
    cnn.close()
    return err


def run_parse_ztd(parse_task):

    return parse_task.execute()


def ExecuteGamit(cnn, JobServer, GamitConfig, stations, check_stations, ignore_missing, dates,
                 dry_run=False, create_kml=False):

    modules = ('pyRinex', 'datetime', 'os', 'shutil', 'pyBrdc', 'pySp3', 'subprocess', 're', 'pyETM', 'glob',
               'platform', 'traceback')

    tqdm.write(' >> %s Creating GAMIT session instances and executing GAMIT, please wait...' % print_datetime())

    sessions = []
    archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct

    for date in tqdm(dates, ncols=80, disable=None):

        # make the dir for these sessions
        # this avoids a racing condition when starting each process
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        if not os.path.exists(pwd):
            os.makedirs(pwd)

        net_object = Network(cnn, archive, GamitConfig, stations, date, check_stations, ignore_missing)

        sessions += net_object.sessions

        # Network outputs the sessions to be processed
        # submit them if they are not ready
        tqdm.write(' -- %s %i GAMIT sessions to submit (%i already processed)'
                   % (print_datetime(),
                      len([sess for sess in net_object.sessions if not sess.ready]),
                      len([sess for sess in net_object.sessions if     sess.ready])))

    pbar = tqdm(total=len(sessions), disable=None, desc=' >> GAMIT sessions completion', ncols=100)
    # create the cluster for the run
    JobServer.create_cluster(run_gamit_session, (pyGamitTask.GamitTask,), gamit_callback, pbar, modules=modules)

    for GamitSession in sessions:
        if not GamitSession.ready:
            # do not submit the task if the session is ready!
            # tqdm.write(' >> %s Init' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            GamitSession.initialize()
            # tqdm.write(' >> %s Done Init' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            task = pyGamitTask.GamitTask(GamitSession.remote_pwd, GamitSession.params, GamitSession.solution_pwd)
            # tqdm.write(' >> %s Done task' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            JobServer.submit(task, task.params['DirName'], task.date.year, task.date.doy, dry_run)

            msg = 'Submitting for processing'
        else:
            msg = 'Session already processed'
            pbar.update()

        tqdm.write(' -- %s %s %s %s%02i -> %s' % (print_datetime(),
                                                  GamitSession.NetName,
                                                  GamitSession.date.yyyyddd(),
                                                  GamitSession.org,
                                                  GamitSession.subnet if GamitSession.subnet is not None else 0, 
                                                  msg))

    if create_kml:
        # generate a KML of the sessions
        generate_kml(dates, sessions, GamitConfig)

    tqdm.write(' -- %s Done initializing and submitting GAMIT sessions' % print_datetime())

    # DDG: because of problems with keeping the database connection open (in some platforms), we invoke a class
    # that just performs a select on the database
    timer = DbAlive(cnn, 120)
    JobServer.wait()
    pbar.close()
    timer.stop()

    JobServer.close_cluster()

    return sessions


if __name__ == '__main__':
    main()

