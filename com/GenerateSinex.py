#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to load a SINEX solution created using glbtosnx and add the missing unknown parameters (tropospheric delays
and gradients)
"""

import argparse
import os

# app
from pgamit import pyOptions
from pgamit import dbConnection
from pgamit import pyDate
from pgamit import snxParse
from pgamit.Utils import (process_date, process_stnlist, file_open, add_version_argument)


def replace_in_sinex(sinex, observations, unknowns, new_val):

    new_unknowns = \
""" NUMBER OF UNKNOWNS%22i
 NUMBER OF DEGREES OF FREEDOM%12i
 PHASE MEASUREMENTS SIGMA          0.0025
 SAMPLING INTERVAL (SECONDS)           30
""" % (new_val, observations - new_val)

    sinex_path = os.path.basename(os.path.splitext(sinex)[0]) + '_MOD.snx'
    with file_open(sinex_path, 'w') as nsnx:
        with file_open(sinex, 'r') as osnx:
            for line in osnx:
                if ' NUMBER OF UNKNOWNS%22i' % unknowns in line:
                    # empty means local directory! LA RE PU...
                    nsnx.write(new_unknowns)
                else:
                    nsnx.write(line)

    # rename file
    os.remove(sinex)
    os.renames(sinex_path, sinex)


def add_domes(sinex, stations):

    for stn in stations:
        if stn['dome'] is not None:
            # " BATF  A ---------"
            os.system("sed -i 's/ %s  A ---------/ %s  A %s/g' %s"
                      % (stn['StationCode'].upper(),
                         stn['StationCode'].upper(), stn['dome'], sinex))


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


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")

    parser.add_argument('sinex', type=str, nargs=1, metavar='{project name}',
                        help="SINEX file to update.")

    parser.add_argument('-d', '--date_filter', nargs='+', metavar='date',
                        help='Date range filter can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')

    add_version_argument(parser)

    args = parser.parse_args()

    cnn    = dbConnection.Cnn("gnss_data.cfg")
    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    dates = [pyDate.Date(year=1980, doy=1),
             pyDate.Date(year=2100, doy=1)]
    try:
        dates = process_date(args.date_filter)
    except ValueError as e:
        parser.error(str(e))

    sinex   = args.sinex[0]
    project = args.project[0]

    process_sinex(cnn, project, dates, sinex)

    # generate REP file


if __name__ == '__main__':
    main()
