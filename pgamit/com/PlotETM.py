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
import pyETM
import pyOptions
import dbConnection
import pyDate
from Utils import (process_date,
                   process_stnlist,
                   file_write,
                   station_list_help)


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
        dd.append(d)

    dd = [pyDate.Date(**d) for d in dd]

    polyhedrons = np.array((x, y, z, [d.year for d in dd], [d.doy for d in dd])).transpose()

    soln = pyETM.ListSoln(cnn, polyhedrons.tolist(), stn['NetworkCode'], stn['StationCode'])
    etm  = pyETM.FileETM(cnn, soln, False, args.no_model, args.remove_jumps, args.remove_polynomial)

    return etm


def main():
    parser = argparse.ArgumentParser(description='Plot ETM for stations in the database')

    parser.add_argument('stnlist', type=str, nargs='+',
                        help=station_list_help())

    parser.add_argument('-nop', '--no_plots', action='store_true',
                        help="Do not produce plots", default=False)

    parser.add_argument('-nom', '--no_missing_data', action='store_true',
                        help="Do not show missing days", default=False)

    parser.add_argument('-nm', '--no_model', action='store_true',
                        help="Plot time series without fitting a model")

    parser.add_argument('-r', '--residuals', action='store_true',
                        help="Plot time series residuals", default=False)

    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory")

    parser.add_argument('-json', '--json', type=int,
                        help="Export ETM adjustment to JSON. Append '0' to just output "
                        "the ETM parameters, '1' to export time series without "
                        "model and '2' to export both time series and model.")

    parser.add_argument('-gui', '--interactive', action='store_true',
                        help="Interactive mode: allows to zoom and view the plot interactively")

    parser.add_argument('-rj', '--remove_jumps', action='store_true', default=False,
                        help="Remove jumps from model and time series before plotting")

    parser.add_argument('-rp', '--remove_polynomial', action='store_true', default=False,
                        help="Remove polynomial terms from model and time series before plotting")

    parser.add_argument('-win', '--time_window', nargs='+', metavar='interval',
                        help='Date range to window data. Can be specified in yyyy/mm/dd, yyyy.doy or as a single '
                             'integer value (N) which shall be interpreted as last epoch-N')

    parser.add_argument('-q', '--query', nargs=2, metavar='{type} {date}', type=str,
                        help='Dates to query the ETM. Specify "model" or "solution" to get the ETM value or the value '
                             'of the daily solution (if exists). Output is in XYZ.')

    parser.add_argument('-gamit', '--gamit', type=str, nargs=1, metavar='{stack}',
                        help="Plot the GAMIT time series specifying which stack name to plot.")

    parser.add_argument('-lang', '--language', type=str,
                        help="Change the language of the plots. Default is English. "
                        "Use ESP to select Spanish. To add more languages, "
                        "include the ISO 639-1 code in pyETM.py", default='ENG')

    parser.add_argument('-hist', '--histogram', action='store_true',
                        help="Plot histogram of residuals")

    parser.add_argument('-file', '--filename', type=str,
                        help="Obtain data from an external source (filename). "
                        "Format should be specified with -format.")

    parser.add_argument('-format', '--format', nargs='+', type=str,
                        help="To be used together with --filename. Specify order of the fields as found in the input "
                             "file. Format strings are gpsWeek, gpsWeekDay, year, doy, fyear, month, day, mjd, "
                             "x, y, z, na. Use 'na' to specify a field that should be ignored. If fields to be ignored "
                             "are at the end of the line, then there is no need to specify those.")

    parser.add_argument('-outliers', '--plot_outliers', action='store_true',
                        help="Plot an additional panel with the outliers")

    parser.add_argument('-vel', '--velocity', action='store_true',
                        help="During query, output the velocity in XYZ.")

    parser.add_argument('-seasonal', '--seasonal_terms', action='store_true',
                        help="During query, output the seasonal terms in NEU.")

    parser.add_argument('-quiet', '--suppress_messages', action='store_true',
                        help="Quiet mode: suppress information messages")

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')

    stnlist = process_stnlist(cnn, args.stnlist)

    # define the language
    pyETM.LANG = args.language.lower()
    # set the logging level
    if not args.suppress_messages:
        pyETM.logger.setLevel(pyETM.INFO)
    #####################################
    # date filter

    dates = None
    if args.time_window is not None:
        if len(args.time_window) == 1:
            try:
                dates = process_date(args.time_window, missing_input=None, allow_days=False)
                dates = (dates[0].fyear,)
            except ValueError:
                # an integer value
                dates = float(args.time_window[0])
        else:
            dates = process_date(args.time_window)
            dates = (dates[0].fyear,
                     dates[1].fyear)

    if stnlist:
        # do the thing
        if args.directory:
            if not os.path.exists(args.directory):
                os.mkdir(args.directory)
        else:
            if not os.path.exists('production'):
                os.mkdir('production')
            args.directory = 'production'

        for stn in stnlist:
            try:

                if args.gamit is None and args.filename is None:
                    etm = pyETM.PPPETM(cnn, stn['NetworkCode'], stn['StationCode'], False, args.no_model,
                                       plot_remove_jumps=args.remove_jumps,
                                       plot_polynomial_removed=args.remove_polynomial)
                elif args.filename is not None:
                    etm = from_file(args, cnn, stn)
                else:
                    polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM stacks '
                                                  'WHERE "name" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                                  '"StationCode" = \'%s\' '
                                                  'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                                  % (args.gamit[0], stn['NetworkCode'], stn['StationCode']))

                    soln = pyETM.GamitSoln(cnn, polyhedrons, stn['NetworkCode'], stn['StationCode'], args.gamit[0])

                    etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], False,
                                         args.no_model, gamit_soln=soln, plot_remove_jumps=args.remove_jumps,
                                         plot_polynomial_removed=args.remove_polynomial)
                                      #   postseismic=[{'date': pyDate.Date(year=2010,doy=58),
                                      #  'relaxation': [0.5],
                                      #  'amplitude': [[-0.0025, -0.0179, -0.005]]}])

                    # print ' > %5.2f %5.2f %5.2f %i %i' % \
                    #      (etm.factor[0]*1000, etm.factor[1]*1000, etm.factor[2]*1000, etm.soln.t.shape[0],
                    #       etm.soln.t.shape[0] -
                    #       np.sum(np.logical_and(np.logical_and(etm.F[0], etm.F[1]), etm.F[2])))

                    # print two largest outliers
                    if etm.A is not None:
                        lres  = np.sqrt(np.sum(np.square(etm.R), axis=0))
                        slres = lres[np.argsort(-lres)]

                        print(' >> Two largest residuals:')
                        for i in [0, 1]:
                            print(' %s %6.3f %6.3f %6.3f'
                                  % (pyDate.Date(mjd = etm.soln.mjd[lres == slres[i]]).yyyyddd(),
                                     etm.R[0, lres == slres[i]][0],
                                     etm.R[1, lres == slres[i]][0],
                                     etm.R[2, lres == slres[i]][0]))

                if args.interactive:
                    xfile = None
                else:
                    postfix = "gamit"
                    if args.gamit is None:
                        postfix = "ppp" if args.filename is None else "file"

                    xfile = os.path.join(args.directory, '%s.%s_%s' % (etm.NetworkCode,
                                                                       etm.StationCode,
                                                                       postfix))

                # leave pngfile empty to enter interactive mode (GUI)
                if not args.no_plots:
                    etm.plot(xfile + '.png',
                             t_win         = dates,
                             residuals     = args.residuals,
                             plot_missing  = not args.no_missing_data,
                             plot_outliers = args.plot_outliers)

                    if args.histogram:
                        etm.plot_hist(xfile + '_hist.png')

                if args.json is not None:
                    if args.json == 1:
                        obj = etm.todictionary(time_series=True)
                    elif args.json == 2:
                        obj = etm.todictionary(time_series=True, model=True)
                    else:
                        obj = etm.todictionary(False)

                    file_write(xfile + '.json',
                               json.dumps(obj, indent=4, sort_keys=False))

                if args.query is not None:
                    model  = (args.query[0] == 'model')
                    q_date = pyDate.Date(fyear = float(args.query[1]))

                    xyz, _, _, txt = etm.get_xyz_s(q_date.year, q_date.doy, force_model=model)

                    strp = ''
                    # if user requests velocity too, output it
                    if args.velocity:
                        if etm.A is not None:
                            vxyz = etm.rotate_2xyz(etm.Linear.p.params[:, 1])
                            strp = '%8.5f %8.5f %8.5f ' \
                                   % (vxyz[0, 0], vxyz[1, 0], vxyz[2, 0])

                    # also output seasonal terms, if requested
                    if args.seasonal_terms and etm.Periodic.frequency_count > 0:
                        strp += ' '.join(['%8.5f' % (x * 1000) for x in etm.Periodic.p.params.flatten().tolist()])

                    print(' %s.%s %14.5f %14.5f %14.5f %8.3f %s -> %s' \
                          % (etm.NetworkCode, etm.StationCode, xyz[0], xyz[1], xyz[2], q_date.fyear, strp, txt))

                print('Successfully plotted ' + stn['NetworkCode'] + '.' + stn['StationCode'])

            except pyETM.pyETMException as e:
                print(str(e))

            except Exception:
                print('Error during processing of ' + stn['NetworkCode'] + '.' + stn['StationCode'])
                print(traceback.format_exc())


if __name__ == '__main__':
    main()
