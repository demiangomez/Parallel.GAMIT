#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: Jul 20 2023 11:40 AM
Author: Demian D. Gomez
Script to convert from one date type to others
"""

import argparse

from pgamit.Utils import process_date, add_version_argument


def main():
    parser = argparse.ArgumentParser(
        description='Convert from one date type to others')

    parser.add_argument('date', type=str, nargs=1, metavar='date to convert',
                        help='''Date to convert from. Allowable formats
                        are yyyy/mm/dd yyyy_doy wwww-d format''')

    add_version_argument(parser)

    args = parser.parse_args()

    dates = process_date(args.date)
    print('  ISO %s' % dates[0].iso_date())
    print('  DOY %s' % dates[0].yyyyddd())
    print('FYEAR %.3f' % dates[0].fyear)
    print('GPSWK %s %s' % (dates[0].wwww(), str(dates[0].gpsWeekDay)))


if __name__ == '__main__':
    main()
