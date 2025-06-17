#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 10/28/2022
Author: Demian D. Gomez
Script to convert T0x files to RINEX
"""

import argparse
import os

# app
from pgamit.ConvertRaw import ConvertRaw
from pgamit.Utils import required_length, add_version_argument


def main():
    parser = argparse.ArgumentParser(
        description='Script to convert T0x files to RINEX')

    parser.add_argument('path', type=str, nargs=1, metavar='[path to dir]',
                        help="Path to directory with T0x files")

    parser.add_argument('path_out', type=str, nargs=1, metavar='[path to dir]',
                        help='''Path to directory with resulting RINEX
                             (a folder with station name will be created)''')

    parser.add_argument('-stnm', '--station_name', type=str, default='dftl',
                        help="Name of the station to form that RINEX files")

    parser.add_argument('-ant', '--antenna_name', type=str, nargs='+',
                        action=required_length(2, 3),
                        metavar='{atx_file} {antenna_name} [SN]', default=None,
                        help='''Replace the antenna name/type in the raw file
                             with name provided in {antenna_name}.
                             Antenna has to exist in ATX file provided in
                             {atx_file}. Radome will be set to NONE by
                             default. Antenna name can have wildcards but
                             a single match is expected (otherwise an
                             exception will be raised). Optionally,
                             provide the antenna serial number.''')

    add_version_argument(parser)

    args = parser.parse_args()
    path = os.path.abspath(args.path[0])
    print('Working on %s' % path)

    stnm = args.station_name
    out_path = args.path_out[0]

    atx_file = None
    antenna = None
    antenna_serial = None

    if args.antenna_name is not None:
        atx_file = args.antenna_name[0]
        antenna = args.antenna_name[1]
        antenna_serial = args.antenna_name[2]

    convert = ConvertRaw(stnm, path, out_path, atx_file=atx_file, antenna=antenna, ant_serial=antenna_serial)

    convert.process_files()
    convert.merge_rinex()

    convert.print_events()


if __name__ == '__main__':
    main()
