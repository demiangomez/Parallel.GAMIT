#!/usr/bin/env python

"""
Project: Parallel.PPP
Date: 10/10/17 9:10 AM
Author: Demian D. Gomez

User interface to plot and save JSON files of ETM objects.
Type python pyPlotETM.py -h for usage help
"""
import argparse
import os
import traceback
import json

# deps
import numpy as np

# app
from pgamit import pyDate
from pgamit import Utils
from pgamit.Utils import file_readlines, add_version_argument
from pgamit import dbConnection
from pgamit import pyETM
from pgamit import pyOptions


def from_file(args, cnn, stn):
    # execute on a file with wk XYZ coordinates
    ts = np.genfromtxt(args.filename)

    # read the format options
    if args.format is None:
        raise Exception('A format should be specified using the -format switch')

    dd = []
    x = []
    y = []
    z = []
    for k in ts:
        d = {}
        for i, f in enumerate(args.format):
            if f in ('gpsWeek', 'gpsWeekDay', 'year', 'doy', 'fyear', 'month', 'day', 'mjd'):
                d[f] = k[i]
                
            if f == 'x':
                x.append(k[i])
            elif f == 'y':
                y.append(k[i])
            elif f == 'z':
                z.append(k[i])
        dd.append(pyDate.Date(**d))

    polyhedrons = np.array((x, y, z,
                            [d.year for d in dd], 
                            [d.doy  for d in dd])).transpose()

    soln = pyETM.ListSoln(cnn, polyhedrons.tolist(), stn['NetworkCode'], stn['StationCode'])
    etm  = pyETM.FileETM(cnn, soln, False, args.no_model)

    return etm


def main():
    parser = argparse.ArgumentParser(description='Query ETM for stations in the database. Default is PPP ETMs.')

    parser.add_argument('stnlist', type=str, nargs='+',
                        help="List of networks/stations to plot given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be plotted). Use keyword 'all' to plot all stations in all networks. "
                             "If [net].all is given, all stations from network [net] will be plotted")

    parser.add_argument('-q', '--query', nargs=2, metavar='{type} {date}', type=str,
                        help='Dates to query the ETM. Specify "model" or "solution" to get the ETM value or the value '
                             'of the daily solution (if exists). Output is in XYZ.')

    parser.add_argument('-gamit', '--gamit', type=str, nargs=1, metavar='{stack}',
                        help="Plot the GAMIT time series specifying which stack name to plot.")

    parser.add_argument('-file', '--filename', type=str,
                        help="Obtain data from an external source (filename). Format should be specified with -format.")

    parser.add_argument('-format', '--format', nargs='+', type=str,
                        help="To be used together with --filename. Specify order of the fields as found in the input "
                             "file. Format strings are gpsWeek, gpsWeekDay, year, doy, fyear, month, day, mjd, "
                             "x, y, z, na. Use 'na' to specify a field that should be ignored. If fields to be ignored "
                             "are at the end of the line, then there is no need to specify those.")

    parser.add_argument('-quiet', '--quiet', action='store_true',
                        help="Do not print message when no solutions are available.")

    parser.add_argument('-vel', '--velocity', action='store_true',
                        help="Output the velocity in XYZ.")

    parser.add_argument('-seasonal', '--seasonal_terms', action='store_true',
                        help="Output the seasonal terms in NEU.")

    add_version_argument(parser)

    args = parser.parse_args()

    ##
    cnn = dbConnection.Cnn('gnss_data.cfg')

    if len(args.stnlist) == 1 and os.path.isfile(args.stnlist[0]):
        print(' >> Station list read from ' + args.stnlist[0])
        stnlist = [{'NetworkCode': items[0],
                    'StationCode': items[1]}
                   for items in
                   (line.strip().split('.') for line in file_readlines(args.stnlist[0]))]
    else:
        stnlist = Utils.process_stnlist(cnn, args.stnlist)


    for stn in stnlist:
        try:

            if args.gamit is None and args.filename is None:
                etm = pyETM.PPPETM(cnn, stn['NetworkCode'], stn['StationCode'], False)

            elif args.filename is not None:
                etm = from_file(args, cnn, stn)

            else:
                polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM stacks '
                                              'WHERE "name" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                              '"StationCode" = \'%s\' '
                                              'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                              % (args.gamit[0], stn['NetworkCode'], stn['StationCode']))

                soln = pyETM.GamitSoln(cnn, polyhedrons, stn['NetworkCode'], stn['StationCode'], args.gamit[0])

                etm  = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], False, gamit_soln=soln)



            if args.query is not None:
                model  = (args.query[0] == 'model')
                q_date = pyDate.Date(fyear=float(args.query[1]))

                # get the coordinate
                xyz, _, _, txt = etm.get_xyz_s(q_date.year, q_date.doy, force_model=model)

                strp = ''
                # if user requests velocity too, output it
                if args.velocity and etm.A is not None:
                    vxyz = etm.rotate_2xyz(etm.Linear.p.params[:, 1])
                    strp = '%8.5f %8.5f %8.5f ' % (vxyz[0, 0],
                                                   vxyz[1, 0],
                                                   vxyz[2, 0])

                # also output seasonal terms, if requested
                if args.seasonal_terms and etm.Periodic.frequency_count > 0:
                    strp += ' '.join('%8.5f' % (x * 1000)
                                     for x in etm.Periodic.p.params.flatten())

                print(' %s.%s %14.5f %14.5f %14.5f %8.3f %s -> %s' \
                      % (etm.NetworkCode, etm.StationCode, xyz[0], xyz[1], xyz[2], q_date.fyear, strp, txt))

        except pyETM.pyETMException as e:
            if not args.quiet:
                print(str(e))

        except:
            print('Error during processing of ' + stn['NetworkCode'] + '.' + stn['StationCode'])
            print(traceback.format_exc())


if __name__ == '__main__':
    main()
