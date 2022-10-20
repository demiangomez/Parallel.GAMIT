"""
Project: Parallel.GAMIT
Date: 08/30/22 12:44 PM
Author: Demian D. Gomez

Script to close the StationInfo of a station that has not been collecting data for X time
"""

import argparse

import pyDate
import pyOptions
import dbConnection
import pyStationInfo
import Utils
from Utils import stationID

CONFIG_FILE = 'gnss_data.cfg'


def main():
    parser = argparse.ArgumentParser(description='Close an opened station information record for a station using the'
                                                 'last available RINEX file date time')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to process given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be processed). Use keyword 'all' to process all stations in the database. "
                             "If [net].all is given, all stations from network [net] will be processed. "
                             "Alternatively, a file with the station list can be provided.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn(CONFIG_FILE)

    stnlist = Utils.process_stnlist(cnn, args.stnlist)
    stnlist.sort(key=stationID)

    for stn in stnlist:
        fd = cnn.query_float('SELECT max("ObservationFYear") FROM rinex '
                             'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                             % (stn['NetworkCode'], stn['StationCode']))

        dd = fd[0][0]

        if not dd:
            print(' -- No RINEX files found for %s.%s' % (stn['NetworkCode'], stn['StationCode']))
        else:
            print(' -- Closing station information for %s.%s using %.3f from last RINEX file'
                  % (stn['NetworkCode'], stn['StationCode'], dd))

            stninfo = pyStationInfo.StationInfo(cnn, stn['NetworkCode'], stn['StationCode'])
            record = pyStationInfo.StationInfoRecord(stn['NetworkCode'], stn['StationCode'], stninfo.records[-1])
            # change the time to the end of the day to avoid problems with GAMIT and other
            # RINEX files (with different end times)
            date = pyDate.Date(fyear=dd)
            date.hour = 23
            date.minute = 59
            date.second = 59
            record.DateEnd = date
            stninfo.UpdateStationInfo(stninfo.records[-1], record)


if __name__ == '__main__':
    main()
