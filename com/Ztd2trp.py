#!/usr/bin/env python
"""
Original author: Federico Fernandez (IGN)
Project: Parallel.GAMIT
Date: Jul 31 2023 12:24 PM
Modified by: Demian D. Gomez

Script to download zenith tropospheric delays from database and save them in TRP BERNESE format.
Limited functionality, need to implement compression, read of model types (codes), etc.
"""

import argparse
import os
from Utils import required_length, process_date
import pyDate
import dbConnection
from tqdm import tqdm

CONFIG_FILE = 'gnss_data.cfg'


def main():

    parser = argparse.ArgumentParser(description='Zenith tropospheric delays to BERNESE TRP format')

    parser.add_argument('project', metavar='project_name',
                        help="GAMIT processing project name")

    parser.add_argument('-z', '--compress', action='store_true',
                        help="Compress resulting files (gz format)")

    parser.add_argument('-c', '--produce_here', action='store_true',
                        help="Bandera para indicar que se produzcan los archivos en el mismo directorio")

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1, 2),
                        metavar='date_start|date_end',
                        help="Date range to get from database given as [date_start] or [date_start] "
                             "and [date_end]. Allowed formats are yyyy/mm/dd, yyyy_doy, or wwww-d.")

    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting ZTD files. If not specified, assumed to be the "
                             "production directory")

    args = parser.parse_args()

    dates = process_date(args.date_range)

    cnn = dbConnection.Cnn(CONFIG_FILE)

    if args.directory:
        if not os.path.exists(args.directory):
            os.mkdir(args.directory)
    else:
        if not os.path.exists('production'):
            os.mkdir('production')
        args.directory = 'production'

    # print options
    print(' >> Generating ZTD for project %s between dates %s %s' % (args.project,
                                                                     dates[0].yyyyddd(), dates[1].yyyyddd()))

    for x in tqdm(range(dates[0].mjd, dates[1].mjd), ncols=80, disable=None):

        dd = pyDate.Date(mjd=x)

        # execute a statement
        query = "SELECT gamit_ztd.\"NetworkCode\", gamit_ztd.\"StationCode\", gamit_ztd.\"Date\", " \
                "gamit_ztd.\"Year\", gamit_ztd.\"DOY\", gamit_ztd.\"ZTD\", " \
                "stations.dome, gamit_ztd.model, gamit_ztd.sigma  "\
                "FROM gamit_ztd "\
                "INNER JOIN stations "\
                "ON stations.\"NetworkCode\"=gamit_ztd.\"NetworkCode\" and " \
                "stations.\"StationCode\"=gamit_ztd.\"StationCode\" "\
                "WHERE \"Project\" = \'{project}\' "\
                "AND \"DOY\" = {doy} "\
                "AND \"Year\" = {year} "\
                "ORDER BY \"StationCode\" asc, gamit_ztd.\"Date\" asc"\
                "".format(project=args.project, doy=dd.doy, year=dd.year)

        rows = cnn.query_float(query)
        if len(rows) == 0:
            continue

        filename = os.path.join(args.directory, args.project.upper() + dd.wwwwd() + '.TRP')

        with open(filename, "w") as fp:
            tqdm.write('Generating ' + filename)

            station_len = 5
            dome_len = 13
            date_len = 23

            varios = '0.00000'.ljust(8)
            hdr_1 = "Daily solution (GPS) for " + dd.wwwwd() + " (CRD+TRP)                     \n"
            hdr_2 = "-".ljust(133, "-") + '\n'
            hdr_3 = ' A PRIORI MODEL:  -17   MAPPING FUNCTION:    8   GRADIENT MODEL:    4   MIN. ELEVATION:    10   ' \
                    'TABULAR INTERVAL:  3600 / 86400\n\n'
            hdr_4 = " STATION NAME     FLG   YYYY MM DD HH MM SS   YYYY MM DD HH MM SS   MOD_U   CORR_U  SIGMA_U " \
                    "TOTAL_U  CORR_N  SIGMA_N  CORR_E  SIGMA_E\n\n"

            fp.write(hdr_1)
            fp.write(hdr_2)
            fp.write(hdr_3)
            fp.write(hdr_4)
            # fp.close()
            for data in rows:
                if not data[6]:
                    dome = ' '.ljust(dome_len)
                else:
                    dome = data[6].ljust(dome_len)
                mod_u = data[7]
                sigma = data[8]
                corr_u = data[5] - mod_u
                date_ = str(data[2]).replace('-', ' ')
                date_ = date_.replace(':', ' ')
                fp.write(" {stnm}{dome_number}{flag}{date}{spaces}{mod_u} {corr_u}{sigma_u}{total_u}  {corr_n}"
                         "{sigma_n} {corr_e}{sigma_e}\n".format(stnm = data[1].ljust(station_len).upper(),
                                                                dome_number = dome,
                                                                flag = 'A',
                                                                date = date_.rjust(date_len),
                                                                spaces = ' '.ljust(25),
                                                                mod_u = '{:.4f}'.format(mod_u).ljust(6),
                                                                corr_u = '{:7.5f}'.format(corr_u).rjust(8),
                                                                sigma_u = '{:7.5f}'.format(sigma).rjust(8),
                                                                total_u = "{:7.5f}".format(data[5]).rjust(8),
                                                                corr_n = varios.rjust(7),
                                                                sigma_n =varios.rjust(7),
                                                                corr_e = varios.rjust(7),
                                                                sigma_e = varios.rjust(7)))
            fp.close()


if __name__ == '__main__':
    main()
