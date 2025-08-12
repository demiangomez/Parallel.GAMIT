#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 05/30/19 10:44 AM
Author: Demian D. Gomez
"""

import argparse
import os
from shutil import copyfile, move, rmtree
import glob
import subprocess
import re
import random
import string

# deps

# app
from pgamit import dbConnection
from pgamit import Utils
from pgamit import pyDate
from pgamit import snxParse
from pgamit import pyGamitConfig
from pgamit.Utils import split_string, file_open, file_readlines, stationID, chmod_exec, add_version_argument


def replace_in_sinex(sinex, observations, unknowns, new_val):

    new_unknowns = \
""" NUMBER OF UNKNOWNS%22i
 NUMBER OF DEGREES OF FREEDOM%12i
 PHASE MEASUREMENTS SIGMA          0.0015
 SAMPLING INTERVAL (SECONDS)           30
""" % (new_val, observations - new_val)

    snx_path = os.path.basename(os.path.splitext(sinex)[0]) + '_MOD.snx'
    with file_open(snx_path, 'w') as nsnx:
        with file_open(sinex, 'r') as osnx:
            for line in osnx:
                if ' NUMBER OF UNKNOWNS%22i' % unknowns in line:
                    # empty means local directory! LA RE PU...
                    nsnx.write(new_unknowns)
                else:
                    nsnx.write(line)

    # rename file
    os.remove(sinex)
    os.renames(snx_path, sinex)


def add_domes(sinex, stations):

    for stn in stations:
        if stn['dome'] is not None:
            # " BATF  A ---------"
            os.system("sed -i 's/ %s  A ---------/ %s  A %s/g' %s"
                      % (stn['StationCode'].upper(), stn['StationCode'].upper(), stn['dome'], sinex))


def process_sinex(cnn, project, dates, sinex):

    # parse the SINEX to get the station list
    snx = snxParse.snxFileParser(sinex)
    snx.parse()

    stnlist = ('\'' + '\',\''.join(snx.stationDict.keys()) + '\'').lower()

    # insert the statistical data

    zg = cnn.query_float('SELECT count("Year")*2 as ss FROM gamit_soln '
                         'WHERE "Project" = \'%s\' AND "FYear" BETWEEN %.4f AND %.4f AND "StationCode" IN (%s) '
                         'GROUP BY "Year", "DOY"'
                         % (project, dates[0].first_epoch('fyear'), dates[1].last_epoch('fyear'), stnlist))

    zg = sum(s[0] for s in zg)

    zd = cnn.query_float('SELECT count("ZTD") + %i as implicit FROM gamit_ztd '
                         'WHERE "Date" BETWEEN \'%s\' AND \'%s\' '
                         % (zg, dates[0].first_epoch(), dates[1].last_epoch()))

    zd = zd[0][0]

    print(' >> Adding NUMBER OF UNKNOWNS: %i (previous value: %i)' % (zd, snx.unknowns))

    replace_in_sinex(sinex, snx.observations, snx.unknowns, snx.unknowns + zg + zd)

    rs = cnn.query('SELECT "NetworkCode", "StationCode", dome FROM stations '
                   'WHERE "StationCode" IN (%s) '
                   'ORDER BY "NetworkCode", "StationCode"'
                   % stnlist)

    stations = rs.dictresult()

    print(' >> Adding DOMES')
    # add domes
    add_domes(sinex, stations)


class GlobkException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Globk:

    def __init__(self, pwd_comb, org, glx_list, gpsweek, gpsweekday, sites):

        self.pwd_comb = pwd_comb
        self.stdout   = None
        self.stderr   = None
        self.p        = None

        # try to create the folder
        if not os.path.exists(pwd_comb):
            os.makedirs(pwd_comb)

        # see if there is any FATAL in the sessions to be combined
        for glx in glx_list:
            dst_filename = pwd_comb + '/' + org + glx['gpsweek'] + '.GLX'
            if glx['file'].endswith('gz'):
                os.system('gunzip -c ' + glx['file'] + ' > ' + dst_filename)
            else:
                copyfile(glx['file'], dst_filename)

        self.create_combination_script(org, gpsweek, gpsweekday, sites)
        self.execute()

    def execute(self):
        # loop through the folders and execute the script
        self.p = subprocess.Popen('./globk.sh', shell=False, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=self.pwd_comb)

        self.stdout, self.stderr = self.p.communicate()

        # check if any files where not used
        out   = file_readlines(os.path.join(self.pwd_comb + '/globk.log'))
        error = re.findall(r'.*will not be used', ''.join(out))
        if error:
            print(' >> WARNING!')
            print('\n'.join(error))

    def create_combination_script(self, org, gpsweek, gpsweekday, sites):

        # set the path and name for the run script
        run_file_path = os.path.join(self.pwd_comb, 'globk.sh')

        try:
            run_file = file_open(run_file_path, 'w')
        except:
            raise GlobkException('could not open file '+run_file_path)

        sites = split_string(sites, 80)
        site_list_string = []
        for s in sites:
            site_list_string.append('echo " use_site %s"                                     >> globk.cmd' % s)

        site_string = '\n'.join(site_list_string)

        contents = \
        """#!/bin/bash

        export INSTITUTE=%s
        export GPSWEEK=%s
        export GPSWEEKDAY=%i
        
        # data product file names
        OUT_FILE=${INSTITUTE}${GPSWEEK}${GPSWEEKDAY};

        # create global directory listing for globk
        for file in $(find . -name "*.GLX" -print | sort);do echo "$file";done | grep    "\/n0\/"  > globk.gdl
        for file in $(find . -name "*.GLX" -print | sort);do echo "$file";done | grep -v "\/n0\/" >> globk.gdl

        # create the globk cmd file
        echo " eq_file eq_rename.txt"                            >  globk.cmd
        echo " use_site clear"                                   >> globk.cmd
        %s
        echo " prt_opt GDLF MIDP CMDS PLST "                     >> globk.cmd
        echo " out_glb $OUT_FILE.GLX"                            >> globk.cmd
        echo " in_pmu /opt/gamit_globk/tables/pmu.usno"          >> globk.cmd
        echo " descript Weekly combined solution at $INSTITUTE"  >> globk.cmd
        echo " max_chii  3. 0.6"                                 >> globk.cmd
        echo " apr_site  all 1 1 1 0 0 0"                        >> globk.cmd
        # DO NOT ACTIVATE ATM COMBINATION BECAUSE IT WILL NOT WORK!
        echo "#apr_atm   all 1 1 1"                              >> globk.cmd

        # create the sinex header file
        echo "+FILE/REFERENCE                               " >  head.snx
        echo " DESCRIPTION   Instituto Geografico Nacional  " >> head.snx
        echo " OUTPUT        Solucion GPS combinada         " >> head.snx
        echo " CONTACT       gna@ign.gob.ar                 " >> head.snx
        echo " SOFTWARE      glbtosnx Version               " >> head.snx
        echo " HARDWARE      .                              " >> head.snx
        echo " INPUT         Archivos binarios Globk        " >> head.snx
        echo "-FILE/REFERENCE                               " >> head.snx

        # run globk
        globk 0 file.prt globk.log globk.gdl globk.cmd 2>&1 > globk.out

        # convert the GLX file into sinex
        glbtosnx . head.snx $OUT_FILE.GLX ${OUT_FILE}.snx 2>&1 > glbtosnx.out

        # figure out where the parameters start in the prt file
        LINE=`grep -n "PARAMETER ESTIMATES" file.prt | cut -d ":" -f1`

        # reduce line by one to make a little cleaner
        let LINE--;

        # print prt header
        sed -n 1,${LINE}p file.prt > ${OUT_FILE}.out

        # append the log file
        cat globk.log >> ${OUT_FILE}.out

        # create the fsnx file which contains only the solution estimate
        lineNumber=`grep --binary-file=text -m 1 -n "\-SOLUTION/ESTIMATE" ${OUT_FILE}.snx | cut -d : -f 1`

        # extract the solution estimate
        head -$lineNumber ${OUT_FILE}.snx > ${OUT_FILE}.fsnx;

        """ % (org, gpsweek, gpsweekday, site_string)

        run_file.write(contents)

        # all done
        run_file.close()

        # add executable permissions
        chmod_exec(run_file_path)


def id_generator(size=4, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def main():

    parser = argparse.ArgumentParser(description='Program to perform weekly loosely-constrained solutions. Combination '
                                                 'is performed using GLOBK. Result is output in SINEX format.')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to include in the solution.")

    parser.add_argument('-s', '--session_config', type=str, nargs=1, metavar='session.cfg',
                        help="Filename with the session configuration to run Parallel.GAMIT")

    parser.add_argument('-w', '--gpsweek', nargs=1,
                        help="GPS week to combine.")

    parser.add_argument('-e', '--exclude', type=str, nargs='+', metavar='station',
                        help="List of stations to exclude (e.g. -e igm1 lpgs vbca)")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # get the working dates
    date_s = pyDate.Date(gpsWeek=int(args.gpsweek[0]), gpsWeekDay=0)
    date_e = pyDate.Date(gpsWeek=int(args.gpsweek[0]), gpsWeekDay=6)

    print(' >> Working with GPS week ' + args.gpsweek[0] + ' (%s to %s)' % (date_s.yyyyddd(), date_e.yyyyddd()))

    exclude = args.exclude
    if exclude is not None:
        print(' >> User selected list of stations to exclude:')
        Utils.print_columns(exclude)
        args.stnlist += ['-' + exc for exc in exclude]

    # get the station list
    stnlist = Utils.process_stnlist(cnn, args.stnlist)

    # check that the selected stations have all different station codes
    # otherwise, exit with error
    for i in range(len(stnlist) - 1):
        for j in range(i + 1, len(stnlist)):
            if stnlist[i]['StationCode'] == stnlist[j]['StationCode']:
                print('During station selection, two identical station codes were found. '
                      'Please remove one and try again.')
                exit()

    GamitConfig = pyGamitConfig.GamitConfiguration(args.session_config[0])  # type: pyGamitConfig.GamitConfiguration

    project = GamitConfig.NetworkConfig.network_id.lower()
    org     = GamitConfig.gamitopt['org']

    print(' >> REMINDER: To automatically remove outliers during the weekly combination, '
          'first run DRA.py to analyze the daily repetitivities')

    soln_pwd = GamitConfig.gamitopt['solutions_dir']

    # create a globk directory in production
    if not os.path.exists('production/globk'):
        os.makedirs('production/globk')

    # check if week folder exists
    globk_pwd = 'production/globk/' + args.gpsweek[0]
    if os.path.exists(globk_pwd):
        rmtree(globk_pwd)

    # create the directory
    os.makedirs(globk_pwd)

    glx_list = []

    # make a list of the h files that need to be combined
    for day in range(0, 7):
        date = pyDate.Date(gpsWeek    = int(args.gpsweek[0]),
                           gpsWeekDay = day)

        soln_dir = os.path.join(soln_pwd, "%s/%s/%s/glbf" % (date.yyyy(), date.ddd(), project))

        if os.path.exists(soln_dir):
            glx = glob.glob(os.path.join(soln_dir, '*.GLX.*'))
            if not glx:
                glx = glob.glob(os.path.join(soln_dir, '*.glx'))
                
            glx_list.append({'file': glx[0], 'gpsweek': date.wwwwd()})

    # create the earthquakes.txt file to remove outliers
    with file_open(globk_pwd + '/eq_rename.txt', 'w') as fd:
        rename   = []
        remove   = []
        use_site = []
        fd.write('# LIST OF OUTLIERS DETECTED BY DRA\n')
        for stn in stnlist:
            # obtain the filtered solutions
            rm = cnn.query_float('SELECT * FROM gamit_soln_excl WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\''
                                 ' AND "StationCode" = \'%s\' AND ("Year", "DOY") BETWEEN (%i, %i) AND (%i, %i) '
                                 'ORDER BY residual' %
                                 (project, stn['NetworkCode'], stn['StationCode'], date_s.year, date_s.doy,
                                  date_e.year, date_e.doy), as_dict=True)

            # obtain the total number of solutions
            sl = cnn.query_float('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\''
                                 ' AND "StationCode" = \'%s\' AND ("Year", "DOY") BETWEEN (%i, %i) AND (%i, %i) ' %
                                 (project, stn['NetworkCode'], stn['StationCode'], date_s.year, date_s.doy,
                                  date_e.year, date_e.doy), as_dict=True)
            for i, r in enumerate(rm):
                date = pyDate.Date(year=r['Year'], doy=r['DOY'])
                # if the number of rejected solutions is equal to the number of total solutions,
                # leave out the first one (i == 0) which is the one with the lowest residual (see ORDER BY in rm)
                if len(rm) < len(sl) or (len(rm) == len(sl) and i != 0):
                    fd.write(' rename %s_gps %s_xcl %-20s %s %02i %02i 0 0 %s %02i %02i 24 0\n' %
                             (stn['StationCode'], stn['StationCode'], org + date.wwwwd() + '.GLX', date.yyyy()[2:],
                              date.month, date.day, date.yyyy()[2:], date.month, date.day))

            # check for renames that might not agree between days
            mv = cnn.query_float('SELECT * FROM gamit_subnets WHERE "Project" = \'%s\' AND ("Year", "DOY") '
                                 'BETWEEN (%i, %i) AND (%i, %i) AND \'%s.%s\' = ANY(stations)' %
                                 (project, date_s.year, date_s.doy, date_e.year, date_e.doy,
                                  stn['NetworkCode'], stn['StationCode']), as_dict=True)

            for m in mv:
                date = pyDate.Date(year=m['Year'], doy=m['DOY'])
                # check on each day to see if alias agrees with station code
                for i, s in enumerate(m['stations']):
                    if s.split('.')[1] != m['alias'][i] and s == stationID(stn):

                        print(' -- %s alias for %s = %s: renaming' \
                              % (date.yyyyddd(), stationID(stn), m['alias'][i]))

                        # change the name of the station to the original name
                        rename.append(' rename %s_gps %s_dup %-20s %s %02i %02i 0 0 %s %02i %02i 24 0\n' %
                                      (m['alias'][i], stn['StationCode'], org + date.wwwwd() + '.GLX', date.yyyy()[2:],
                                       date.month, date.day, date.yyyy()[2:], date.month, date.day))
                        use_site.append('%s_dup' % stn['StationCode'])

                    elif s not in [stationID(st) for st in stnlist]:
                        # print ' -- Removing %s: not selected' % s
                        # just in case, remove any other occurrences of this station code
                        remove.append(' rename %s_gps %s_xcl %-20s %s %02i %02i 0 0 %s %02i %02i 24 0\n' %
                                      (m['alias'][i], m['alias'][i], org + date.wwwwd() + '.GLX', date.yyyy()[2:],
                                       date.month, date.day, date.yyyy()[2:], date.month, date.day))
                    else:
                        use_site.append('%s_gps' % stn['StationCode'])

        fd.write('# LIST OF STATIONS TO BE REMOVED\n')
        fd.write(''.join(remove))
        fd.write('# LIST OF STATIONS TO BE RENAMED\n')
        fd.write(''.join(rename))

    print(' >> Converting to SINEX the daily solutions')

    for day, glx in enumerate(glx_list):
        date = pyDate.Date(gpsWeek    = int(args.gpsweek[0]),
                           gpsWeekDay = day)

        print(' -- Working on %s' % date.wwwwd())
        # delete the existing GLX files
        for ff in glob.glob(globk_pwd + '/*.GLX'):
            os.remove(ff)

        Globk(globk_pwd, org, [glx], date.wwww(), date.gpsWeekDay + 8, ' '.join(set(use_site)))
        # convert the file to a valid gpsweek day
        move(globk_pwd + '/' + org + date.wwww() + '%i.snx' % (date.gpsWeekDay + 8),
             globk_pwd + '/' + org + date.wwww() + '%i.snx' % date.gpsWeekDay)

        process_sinex(cnn, project, [date, date], globk_pwd + '/' + org + date.wwww() + '%i.snx' % date.gpsWeekDay)

    # delete the existing GLX files: get ready for weekly combination
    for ff in glob.glob(globk_pwd + '/*.GLX'):
        os.remove(ff)
    # ready to pass list to globk object
    Globk(globk_pwd, org, glx_list, date_s.wwww(), 7, ' '.join(set(use_site)))
    print(' >> Formatting the SINEX file')

    process_sinex(cnn, project, [date_s, date_e], globk_pwd + '/' + org + date_s.wwww() + '7.snx')


if __name__ == '__main__':
    main()

