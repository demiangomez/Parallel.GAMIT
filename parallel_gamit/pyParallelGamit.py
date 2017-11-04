"""
Project: Parallel.GAMIT
Date: 3/31/17 6:33 PM
Author: Demian D. Gomez
"""

import pyGamitConfig
import getopt
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
import dbConnection
import time
from math import sqrt
from shutil import rmtree

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
        except:
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


def print_columns(l):

    for a, b, c, d, e, f in zip(l[::6], l[1::6], l[2::6], l[3::6], l[4::6], l[5::6]):
        print('    {:<10}{:<10}{:<10}{:<10}{:<10}{:<}'.format(a, b, c, d, e, f))

    if len(l) % 6 != 0:
        sys.stdout.write('    ')
        for i in range(len(l) - len(l) % 6, len(l)):
            sys.stdout.write('{:<10}'.format(l[i]))
        sys.stdout.write('\n')


def print_summary(Project, all_missing_data):
    # output a summary of each network
    print('')
    print(' >> Summary of stations in this project')
    print(' -- Core network stations (%i):' % (len(Project.Core.StrStns)))
    print_columns(Project.Core.StrStns)

    print('')
    print(' -- Secondary stations (%i):' % (len(Project.Secondary.StrStns)))
    print_columns(Project.Secondary.StrStns)

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


def print_help():

    print ' Parallel.GAMIT input arguments'
    print ' --session_cfg [file] : file with the configuration for the session'
    print ' --year [yyyy]        : year to process'
    print ' --doy  [ddd-ddd,ddd] : day of year in interval format (ddd-ddd) and/or comma separated values'


def parse_arguments(argv):

    if not argv:
        print "Parallel.GAMIT allows the execution of multiple instances of GAMIT in parallel"
        print_help()
        exit()

    year          = None
    session_cfg   = None
    doys          = None

    try:
        aoptions, arguments = getopt.getopt(argv,'',['session_cfg=', 'year=','doys='])
    except getopt.GetoptError:
        print "invalid argument/s"
        print_help()
        sys.exit(2)

    try:
        for opt, args in aoptions:
            if opt == '--session_cfg':
                session_cfg = args
            if opt == '--year':
                year = int(args)
            if opt == '--doys':
                doys = parseIntSet(args)
    except:
        print "invalid argument/s"
        print_help()
        sys.exit(2)

    return session_cfg, year, doys


def main(argv):

    session_cfg, year, doys = parse_arguments(argv)

    print(' >> Reading configuration files and creating project network, please wait...')
    GamitConfig = pyGamitConfig.GamitConfiguration(session_cfg) # type: pyGamitConfig.GamitConfiguration

    cnn = dbConnection.Cnn(GamitConfig.gamitopt['gnss_data']) # type: dbConnection.Cnn

    Project = Network(cnn, GamitConfig.NetworkConfig, year, doys) # type: Network

    # done with Gamit config and network
    # generate the GamitSession instances
    Sessions = []
    AllMissingData = []

    tqdm.write(' >> Creating Session Instances, please wait...')
    for doy in tqdm(doys, ncols=80):

        date = pyDate.Date(year=year,doy=doy) # type: pyDate.Date

        # make the dir for these sessions
        # this avoids a racing condition when starting each process
        pwd = GamitConfig.gamitopt['working_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        if not os.path.exists(pwd):
            os.makedirs(pwd)

        Session_list, Missing_data = Project.CreateGamitSessions(cnn, date, GamitConfig)

        AllMissingData += Missing_data

        Sessions += Session_list

    # print a summary of the current project
    print_summary(Project, AllMissingData)

    # run the job server
    ExecuteGamit(GamitConfig, Sessions)

    # execute globk on doys that had to be divided into subnets
    ExecuteGlobk(cnn, GamitConfig, Project, year, doys, Sessions)

    return


def ExecuteGlobk(cnn, GamitConfig, Project, year, doys, Sessions):

    tqdm.write(' >> Combining with GLOBK sessions with more than one subnetwork...')

    for doy in tqdm(doys, ncols=80):

        date = pyDate.Date(year=year, doy=doy)  # type: pyDate.Date
        pwd = GamitConfig.gamitopt['working_dir'].rstrip('/') + '/' + date.yyyy() + '/' + date.ddd()

        GlobkComb = []
        Fatal = False

        for GamitSession in Sessions:

            if GamitSession.date == date:
                # add to combination
                GlobkComb.append(GamitSession)

                cmd = 'grep -q \'FATAL\' ' + os.path.join(GamitSession.pwd, 'monitor.log')
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
                    tqdm.write(' >> Invalid key found in session %s -> %s' % (date.yyyyddd(),key))
    return

def ExecuteGamit(Config, Sessions):

    def update_gamit_progress_bar(result):
        gamit_pbar.update(1)

        if result['NRMS'] > 0.5:
            msg_nrms = 'WARNING! NRMS > 0.5 (%.3f)' % (result['NRMS'])
        else:
            msg_nrms = ''

        if result['WL'] < 70 :
            if msg_nrms:
                msg_wl = ' AND WL fixed < 70%% (%.1f)' % (result['WL'])
            else:
                msg_wl = 'WARNING! WL fixed %.1f' % (result['WL'])
        else:
            msg_wl = ''

        if result['Success']:
            if not msg_nrms + msg_wl:
                gamit_pbar.write(' -- Done processing: ' + result['Session'])
            else:
                gamit_pbar.write(' -- Done processing: ' + result['Session'] + ' -> ' + msg_nrms + msg_wl)
        else:
            gamit_pbar.write(' -- Done processing: ' + result['Session'] + ' -> Failed to complete. Check monitor.log')

        sys.stdout.flush()
        sys.stderr.flush()

    if Config.run_parallel:
        ppservers = ('*',)

        cpus = Utils.get_processor_count()
        if cpus:
            if cpus >= Config.gamitopt['max_cores']:
                job_server = pp.Server(ncpus=int(Config.gamitopt['max_cores']), ppservers=ppservers)
            else:
                job_server = pp.Server(ncpus=cpus, ppservers=ppservers)
        else:
            raise Exception('Could not determine the number of CPUs for this OS.')
        time.sleep(3)
        print "\n >> Starting pp with", job_server.get_active_nodes(), "workers\n"
    else:
        job_server = None

    gamit_pbar = tqdm(total=len([GamitSession for GamitSession in Sessions if not GamitSession.ready]), desc='GAMIT processes completion progress', ncols=100, position=2) # type: tqdm

    for GamitSession in tqdm(Sessions,total=len(Sessions), desc='GAMIT tasks initialization progress', ncols=100, position=1):

        if Config.run_parallel:
            if not GamitSession.ready:

                GamitSession.initialize()

                Task = pyGamitTask.GamitTask(GamitSession.pwd, GamitSession.params)

                GamitSession.GamitTask = Task

                # do not submit the task if the session is ready!
                job_server.submit(Task.start, args=(),
                              modules=('pyRinex', 'datetime', 'os', 'shutil', 'pyBrdc', 'pySp3', 'subprocess', 're', 'pyPPPETM'),
                              callback=(update_gamit_progress_bar))
            else:
                gamit_pbar.write(' -- Session already processed: ' + GamitSession.NetName + ' ' + GamitSession.date.yyyyddd())


    # once we finnish walking the dir, wait and, handle the output messages
    if Config.run_parallel:
        job_server.wait()

    gamit_pbar.close()

    return

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main(sys.argv[1:])

