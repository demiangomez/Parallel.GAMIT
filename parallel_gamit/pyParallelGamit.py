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
from shutil import rmtree
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


def print_summary(stations, sessions, dates):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Selected stations (%i):' % (len(stations)))
    Utils.print_columns([item.NetworkCode + '.' + item.StationCode for item in stations])

    min_stn = 99999
    min_date = pyDate.Date(year=1980,doy=1)
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


def purge_solutions(cnn, args, dates, GamitConfig):

    if args.purge:

        print(' >> Purging selected year-doys before run:')

        for date in tqdm(dates, ncols=80):

            # base dir for the GAMIT session directories
            pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

            # delete the main solution dir (may be entire GAMIT run or combination directory)
            if os.path.isdir(os.path.join(pwd, GamitConfig.NetworkConfig.network_id.lower())):
                rmtree(os.path.join(pwd, GamitConfig.NetworkConfig.network_id.lower()))

            # possible subnetworks
            for sub in glob.glob(os.path.join(pwd, GamitConfig.NetworkConfig.network_id.lower() + '.*')):
                rmtree(sub)

            # now remove the database entries
            cnn.query('DELETE FROM gamit_soln WHERE "Year" = %i AND "DOY" = %i '
                      'AND "Project" = \'%s\'' % (date.year, date.doy, GamitConfig.NetworkConfig.network_id.lower()))


def station_list(cnn, NetworkConfig, dates):

    stations = process_stnlist(cnn, NetworkConfig['stn_list'].split(','))
    stn_obj = []

    # use the connection to the db to get the stations
    for Stn in tqdm(sorted(stations), ncols=80):

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

        sys.stdout.flush()

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
    parser.add_argument('-kml', '--kml_only', action='store_true', help="Generate KML and exit without running GAMIT.")

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
                                      check_gamit_tables=(pyDate.Date(year=drange[1].year,doy=drange[1].doy),
                                                          GamitConfig.gamitopt['eop_type']))

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
        purge_solutions(cnn, args, dates, GamitConfig)

    # initialize stations in the project
    stations = station_list(cnn, GamitConfig.NetworkConfig, drange)

    tqdm.write(' >> Creating GAMIT session instances, please wait...')

    sessions = []
    archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct

    for date in tqdm(dates, ncols=80):

        # make the dir for these sessions
        # this avoids a racing condition when starting each process
        pwd = GamitConfig.gamitopt['solutions_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        if not os.path.exists(pwd):
            os.makedirs(pwd)

        net_object = Network(cnn, archive, GamitConfig, stations, date)

        sessions += net_object.sessions

    # generate a KML of the sessions
    generate_kml(dates, sessions, GamitConfig)

    if args.kml_only:
        # user requested to just generate the KML file for the run. Exit if so.
        return

    # print a summary of the current project
    print_summary(stations, sessions, drange)

    # run the job server
    ExecuteGamit(GamitConfig, sessions, JobServer, dry_run)

    # execute globk on doys that had to be divided into subnets
    if not args.dry_run:
        ExecuteGlobk(cnn, GamitConfig, sessions, dates)

        # parse the zenith delay outputs
        ParseZTD(cnn, GamitConfig.NetworkConfig.network_id, sessions, GamitConfig)

    print(' >> Done processing and parsing information. Successful exit from Parallel.GAMIT')


def generate_kml(dates, sessions, GamitConfig):

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    for date in tqdm(dates, ncols=80):

        folder = kml.newfolder(name=date.yyyyddd())

        sess = []
        for session in sessions:
            if session.date == date:
                sess.append(session)

        if len(sess) > 1:
            for session in sess:
                folder_net = folder.newfolder(name=session.NetName)

                if len(session.core_dict) > 1:
                    folder_core = folder_net.newfolder(name='core network')

                    for stn in session.core_dict:
                        pt = folder_core.newpoint(**stn)
                        pt.style.iconstyle.scale = 2
                        pt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/' \
                                                       'placemark_square_highlight.png'

                folder_stn = folder_net.newfolder(name='all stations')

                for stn in session.stations_dict:
                    pt = folder_stn.newpoint(**stn)
                    pt.style.iconstyle.scale = 2
                    pt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

        elif len(sess) == 1:
            for stn in sess[0].stations_dict:
                pt = folder.newpoint(**stn)
                pt.style.iconstyle.scale = 2
                pt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + GamitConfig.NetworkConfig.network_id.lower() + '.kmz')


def ParseZTD(cnn, project, Sessions, GamitConfig):

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
                stn = [{'NetworkCode': StnIns.NetworkCode, 'StationCode': StnIns.StationCode} for StnIns in GamitSession.StationInstances if StnIns.StationAlias.upper() == zd[0]][0]

                # see if ZND exists
                rs = cnn.query('SELECT * FROM gamit_ztd WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                               '"Date" = \'%s\' AND "Project" = \'%s\''
                               % (stn['NetworkCode'], stn['StationCode'],
                                  date.strftime('%Y/%m/%d %H:%M:%S'), project.lower()))

                if rs.ntuples() == 0:
                    cnn.query('INSERT INTO gamit_ztd ("NetworkCode", "StationCode", "Date", "ZTD", "Project") VALUES '
                              '(\'%s\', \'%s\', \'%s\', %f, \'%s\')'
                              % (stn['NetworkCode'], stn['StationCode'], date.strftime('%Y/%m/%d %H:%M:%S'),
                                 float(zd[6]), project.lower()))


def ExecuteGlobk(cnn, GamitConfig, sessions, dates):

    project = GamitConfig.NetworkConfig.network_id.lower()

    tqdm.write(' >> Combining with GLOBK sessions with more than one subnetwork...')

    for date in tqdm(dates, ncols=80):

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
                        tqdm.write('    --> Error inserting ' + key + ' -> ' + str(e))
                else:
                    tqdm.write(' >> Invalid key found in session %s -> %s' % (date.yyyyddd(), key))
    return


def ExecuteGamit(Config, Sessions, JobServer, dry_run=False):

    def update_gamit_progress_bar(result):

        gamit_pbar.update(1)

        if 'error' not in result.keys():
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
        else:
            tqdm.write(' -- Error in session ' + result['Session'] + ' message from node follows -> \n%s'
                       % result['error'])

    gamit_pbar = tqdm(total=len([GamitSession for GamitSession in Sessions if not GamitSession.ready]),
                      desc=' >> GAMIT sessions completion', ncols=100)  # type: tqdm

    tqdm.write(' >> Initializing %i GAMIT sessions' % (len(Sessions)))

    # For debugging parallel python runs
    # console = logging.FileHandler('pp.log')
    # console.setLevel(logging.DEBUG)
    # JobServer.job_server.logger.setLevel(logging.DEBUG)
    # formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)-8s %(message)s')
    # console.setFormatter(formatter)
    # JobServer.job_server.logger.addHandler(console)

    for GamitSession in Sessions:

        if Config.run_parallel:
            if not GamitSession.ready:
                # do not submit the task if the session is ready!
                GamitSession.initialize()

                task = pyGamitTask.GamitTask(GamitSession.remote_pwd, GamitSession.params, GamitSession.solution_pwd)

                JobServer.job_server.submit(task.start, args=(dry_run, ),
                                            modules=(
                                            'pyRinex', 'datetime', 'os', 'shutil', 'pyBrdc', 'pySp3', 'subprocess',
                                            're', 'pyETM', 'glob', 'platform', 'traceback'),
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


if __name__ == '__main__':
    main()

