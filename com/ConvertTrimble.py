"""
Project: Parallel.GAMIT
Date: 10/28/2022
Author: Demian D. Gomez
Script to convert T0x files to RINEX
"""

import argparse
import os
from pyTrimbleT0x import convert_trimble
from Utils import required_length

def main():
    parser = argparse.ArgumentParser(description='Script to convert T0x files to RINEX')

    parser.add_argument('path', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with T0x files")

    parser.add_argument('path_out', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with resulting RINEX (a folder with station name will be created)")

    parser.add_argument('-stnm', '--station_name', type=str, default='dftl',
                        help="Name of the station to form that RINEX files")

    parser.add_argument('-ant', '--antenna_name', type=str, nargs='+',
                        action=required_length(2, 3), metavar='{atx_file} {antenna_name} [SN]', default=None,
                        help="Replace the antenna name/type in the raw file with name provided in {antenna_name}. "
                             "Antenna has to exist in ATX file provided in {atx_file}. Radome will be set to NONE by "
                             "default. Antenna name can have wildcards but a single match is expected (otherwise an "
                             "exception will be raised). Optionally, provide the antenna serial number.")

    args = parser.parse_args()
    path = os.path.abspath(args.path[0])
    print('Working on %s' % path)

    stnm = args.station_name
    out_path = args.path_out[0]
    convert_trimble(path, stnm, out_path, antenna=args.antenna_name)


if __name__ == '__main__':
    main()

