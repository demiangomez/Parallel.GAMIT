"""
Project: Parallel.PPP
Date: 10/10/17 9:10 AM
Author: Demian D. Gomez

User interface to plot and save JSON files of ETM objects.
Type python pyPlotETM.py -h for usage help
"""
import pyETM
import pyOptions
import argparse
import dbConnection
import os
import traceback
import json
import Utils
from Utils import process_date
import numpy as np
import pyDate


def main():

    parser = argparse.ArgumentParser(description='Plot ETM for stations in the database')

    parser.add_argument('stnlist', type=str, nargs='+',
                        help="List of networks/stations to plot given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be plotted). Use keyword 'all' to plot all stations in all networks. "
                             "If [net].all is given, all stations from network [net] will be plotted")
    parser.add_argument('-nop', '--no_plots', action='store_true', help="Do not produce plots", default=False)
    parser.add_argument('-nom', '--no_missing_data', action='store_true', help="Do not show missing days", default=False)
    parser.add_argument('-nm', '--no_model', action='store_true', help="Plot time series without fitting a model")
    parser.add_argument('-r', '--residuals', action='store_true', help="Plot time series residuals", default=False)
    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory")
    parser.add_argument('-json', '--json', type=int, help="Export ETM adjustment to JSON. Append '0' to just output "
                                                          "the ETM parameters, '1' to export time series without "
                                                          "model and '2' to export both time series and model.")
    parser.add_argument('-gui', '--interactive', action='store_true',
                        help="Interactive mode: allows to zoom and view the plot interactively")
    parser.add_argument('-win', '--time_window', nargs='+', metavar='interval',
                        help='Date range to window data. Can be specified in yyyy/mm/dd, yyyy.doy or as a single '
                             'integer value (N) which shall be interpreted as last epoch-N')
    parser.add_argument('-gamit', '--gamit', type=str, nargs=2, metavar='{project} {type}',
                        help="Plot the GAMIT time series. Specify project and type = \'stack\' to plot the time "
                             "series after stacking or \'gamit\' to just plot the coordinates of the polyhedron")
    parser.add_argument('-lang', '--language', type=str, help="Change the language of the plots. Default is English. "
                                                              "Use ESP to select Spanish. To add more languages, "
                                                              "include the ISO 639-1 code in pyETM.py", default='ENG')
    parser.add_argument('-hist', '--histogram', action='store_true',
                        help="Plot histogram of residuals")
    parser.add_argument('-outliers', '--plot_outliers', action='store_true',
                        help="Plot an additional panel with the outliers")

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')

    if len(args.stnlist) == 1 and os.path.isfile(args.stnlist[0]):
        print ' >> Station list read from ' + args.stnlist[0]
        stnlist = [line.strip() for line in open(args.stnlist[0], 'r')]
        stnlist = [{'NetworkCode': item.split('.')[0], 'StationCode': item.split('.')[1]} for item in stnlist]
    else:
        stnlist = Utils.process_stnlist(cnn, args.stnlist)

    # define the language
    pyETM.LANG = args.language.lower()

    #####################################
    # date filter

    dates = None
    if args.time_window is not None:
        if len(args.time_window) == 1:
            try:
                dates = process_date(args.time_window, missing_input=None, allow_days=False)
                dates = (dates[0].fyear, )
            except ValueError:
                # an integer value
                dates = float(args.time_window[0])
        else:
            dates = process_date(args.time_window)
            dates = (dates[0].fyear, dates[1].fyear)

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

                if args.gamit is None:
                    etm = pyETM.PPPETM(cnn, stn['NetworkCode'], stn['StationCode'], False, args.no_model)
                else:
                    if args.gamit[1] == 'stack':
                        polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM stacks '
                                                      'WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                                      '"StationCode" = \'%s\' '
                                                      'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                                      % (args.gamit[0], stn['NetworkCode'], stn['StationCode']))

                        soln = pyETM.GamitSoln(cnn, polyhedrons, stn['NetworkCode'], stn['StationCode'], args.gamit[0])

                        etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], False,
                                             args.no_model, gamit_soln=soln)

                        # print ' > %5.2f %5.2f %5.2f %i %i' % \
                        #      (etm.factor[0]*1000, etm.factor[1]*1000, etm.factor[2]*1000, etm.soln.t.shape[0],
                        #       etm.soln.t.shape[0] -
                        #       np.sum(np.logical_and(np.logical_and(etm.F[0], etm.F[1]), etm.F[2])))

                        # print two largest outliers
                        if etm.A is not None:
                            lres = np.sqrt(np.sum(np.square(etm.R), axis=0))
                            slres = lres[np.argsort(-lres)]

                            print ' >> Two largest residuals:'
                            for i in [0, 1]:
                                print(' %s %6.3f %6.3f %6.3f'
                                      % (pyDate.Date(mjd=etm.soln.mjd[lres == slres[i]]).yyyyddd(),
                                         etm.R[0, lres == slres[i]],
                                         etm.R[1, lres == slres[i]],
                                         etm.R[2, lres == slres[i]]))

                    elif args.gamit[1] == 'gamit':
                        etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], False,
                                             args.no_model, project=args.gamit[0])
                    else:
                        parser.error('Invalid option for -gamit switch')
                        etm = None

                if args.interactive:
                    xfile = None
                else:
                    if args.gamit is None:
                        xfile = os.path.join(args.directory, '%s.%s_ppp' % (etm.NetworkCode, etm.StationCode))
                    else:
                        xfile = os.path.join(args.directory, '%s.%s_gamit' % (etm.NetworkCode, etm.StationCode))

                # leave pngfile empty to enter interactive mode (GUI)
                if not args.no_plots:
                    etm.plot(xfile + '.png', t_win=dates, residuals=args.residuals,
                             plot_missing=not args.no_missing_data, plot_outliers=args.plot_outliers)

                    if args.histogram:
                        etm.plot_hist(xfile + '_hist.png')

                if args.json is not None:
                    with open(xfile + '.json', 'w') as f:
                        if args.json == 1:
                            json.dump(etm.todictionary(time_series=True), f, indent=4, sort_keys=False)
                        elif args.json == 2:
                            json.dump(etm.todictionary(time_series=True, model=True), f, indent=4, sort_keys=False)
                        else:
                            json.dump(etm.todictionary(False), f, indent=4, sort_keys=False)

                print 'Successfully plotted ' + stn['NetworkCode'] + '.' + stn['StationCode']

            except pyETM.pyETMException as e:
                print str(e)

            except Exception:
                print 'Error during processing of ' + stn['NetworkCode'] + '.' + stn['StationCode']
                print traceback.format_exc()
                pass


if __name__ == '__main__':

    main()