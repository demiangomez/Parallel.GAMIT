#!/usr/bin/env python
"""
Project: Parallel.GAMIT 
Date: 9/25/24 11:29AM
Author: Demian D. Gomez

Description goes here

"""

import argparse
import math

# app
from pgamit import pyOkada
from pgamit import dbConnection
from pgamit.Utils import add_version_argument, stationID, print_columns


def main():
    parser = argparse.ArgumentParser(description='Output S-score kmz files for a set of earthquakes. Output is produced'
                                                 ' on the current folder with a kmz file named using the USGS code.')

    parser.add_argument('earthquakes', type=str, nargs='+',
                        help='USGS codes of specific earthquake to produce kmz files')

    parser.add_argument('-post', '--postseismic', action='store_true',
                        help="Include the postseismic S-score", default=False)

    parser.add_argument('-disp', '--output_displacements', nargs='?', type=str,
                        metavar='[stack_name]', const='ppp',
                        help="Output the displacements produced by the requested earthquake. "
                             "By default, the ppp ETM solution is printed. To output another stack ETM, specify "
                             "provide a stack_name.")

    parser.add_argument('-table', '--output_table', action='store_true',
                        help="Output the list of stations affected by the requested earthquake.", default=False)

    parser.add_argument('-density', '--mask_density', nargs=1, type=int,
                        metavar='{mask_density}', default=[750],
                        help="A value to control the quality of the output mask. "
                             "Recommended for high quality is 1000. For low quality use 250. Default is 750.")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')

    for eq in args.earthquakes:
        event = cnn.query('SELECT * FROM earthquakes WHERE id = \'%s\'' % eq)
        if len(event):
            event = event.dictresult()[0]

            mask = pyOkada.Mask(cnn, event['id'])
            mask.save_masks(kmz_file=eq + '.kmz', include_postseismic=args.postseismic)

            if args.output_table:
                table = pyOkada.EarthquakeTable(cnn, event['id'], args.postseismic)
                print(' >> Stations affected by %s (id %s, co+post-seismic)' % (event['location'], event['id']))
                print_columns([stationID(stn) for stn in table.c_stations])

                if args.postseismic:
                    print(' >> Stations affected by %s (id %s, post-seismic only)' % (event['location'], event['id']))
                    print_columns([stationID(stn) for stn in table.p_stations])
                else:
                    print(' >> Post-seismic affected stations not requested')

            if args.output_displacements:
                table = pyOkada.EarthquakeTable(cnn, event['id'], args.postseismic)
                print(' >> Co-seismic displacements produced by %s '
                      '(id %s, NEU, stack name %s)' % (event['location'], event['id'], args.output_displacements))

                for stn in table.get_coseismic_displacements(args.output_displacements):
                    print('%s : %6.3f %6.3f %6.3f' % (stationID(stn), stn['n'], stn['e'], stn['u']))

        else:
            print(' -- Event %s not found' % eq)


if __name__ == '__main__':
    main()