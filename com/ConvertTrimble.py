"""
Project: Parallel.GAMIT
Date: 10/28/2022
Author: Demian D. Gomez
Script to convert T0x files to RINEX
"""

import argparse
import os
from pyTrimbleT0x import convert_trimble


def main():
    parser = argparse.ArgumentParser(description='Script to convert T0x files to RINEX')

    parser.add_argument('path', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with T0x files")

    parser.add_argument('path_out', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with resulting RINEX (a folder with station name will be created)")

    parser.add_argument('-stnm', '--station_name', type=str, default='dftl',
                        help="Name of the station to form that RINEX files")

    args = parser.parse_args()
    path = os.path.abspath(args.path[0])
    print('Working on %s' % path)

    stnm = args.station_name
    out_path = args.path_out[0]
    convert_trimble(path, stnm, out_path)


if __name__ == '__main__':
    main()

