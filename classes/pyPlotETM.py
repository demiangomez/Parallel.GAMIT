"""
Project: Parallel.PPP
Date: 10/10/17 9:10 AM
Author: Demian D. Gomez

User interface to plot and save JSON files of ETM objects.
Type python pyPlotETM.py -h for usage help
"""

import pyPPPETM
import pyOptions
import pyJobServer
import argparse
import dbConnection
import os
import traceback
import json
import Utils

def main():

    parser = argparse.ArgumentParser(description='Plot ETM for stations in the database')

    parser.add_argument('stnlist', type=str, nargs='+', help="List of networks/stations to plot given in [net].[stnm] format or just [stnm] (separated by spaces; if [stnm] is not unique in the database, all stations with that name will be plotted). Use keyword 'all' to plot all stations in all networks. If [net].all is given, all stations from network [net] will be plotted")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization")
    parser.add_argument('-dir', '--directory', type=str, help="Directory to save the resulting PNG files. If not specified, assumed to be the production directory")
    parser.add_argument('-json', '--json', type=int, help="Export ETM adjustment to JSON. Append '1' to export time series or append '0' to just output the ETM parameters.")

    args = parser.parse_args()

    Config = pyOptions.ReadOptions("gnss_data.cfg") # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn('gnss_data.cfg')

    stnlist = Utils.process_stnlist(cnn, args.stnlist)

    if not args.noparallel:
        pyJobServer.JobServer(Config)

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
                etm = pyPPPETM.ETM(cnn, stn['NetworkCode'], stn['StationCode'], False)
                etm.plot(os.path.join(args.directory, etm.NetworkCode + '.' + etm.StationCode + '.png'))

                if not args.json is None:
                    with open(os.path.join(args.directory, etm.NetworkCode + '.' + etm.StationCode + '.json'), 'w') as f:
                        if args.json != 0:
                            json.dump(etm.todictionary(True), f, indent=4, sort_keys=False)
                        else:
                            json.dump(etm.todictionary(False), f, indent=4, sort_keys=False)

                print 'Successfully plotted ' + stn['NetworkCode'] + '.' + stn['StationCode']

            except Exception:
                print 'Error during processing of ' + stn['NetworkCode'] + '.' + stn['StationCode']
                print traceback.format_exc()
                pass


if __name__ == '__main__':

    main()