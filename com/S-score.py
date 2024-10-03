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


def main():
    parser = argparse.ArgumentParser(description='Output S-score kmz files for a set of earthquakes. Output is produced'
                                                 ' on the current folder with a kmz file named using the USGS code.')

    parser.add_argument('earthquakes', type=str, nargs='+',
                        help='USGS codes of specific earthquake to produce kmz files')

    parser.add_argument('-post', '--postseismic', action='store_true',
                        help="Include the postseismic S-score", default=False)

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')

    for eq in args.earthquakes:
        event = cnn.query('SELECT * FROM earthquakes WHERE id = \'%s\'' % eq)
        if len(event):
            event = event.dictresult()[0]

            strike = [float(event['strike1']), float(event['strike2'])] if not math.isnan(event['strike1']) else []
            dip = [float(event['dip1']), float(event['dip2'])] if not math.isnan(event['strike1']) else []
            rake = [float(event['rake1']), float(event['rake2'])] if not math.isnan(event['strike1']) else []

            score = pyOkada.Score(event['lat'], event['lon'], event['depth'], event['mag'], strike, dip, rake,
                                  event['date'], density=1000, location=event['location'])

            score.save_masks(kmz_file=eq + '.kmz', include_postseismic=args.postseismic)
        else:
            print(' -- Event %s not found' % eq)


if __name__ == '__main__':
    main()