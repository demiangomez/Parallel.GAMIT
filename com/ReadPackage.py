#!/usr/bin/env python

from zipfile import ZipFile
import argparse
import json
import shutil
import os

# app
from pgamit import pyStationInfo
from pgamit.Utils import file_read_all, add_version_argument


def main():

    parser = argparse.ArgumentParser(description='Program to read package contents created by another '
                                                 'Parallel.GAMIT system')

    parser.add_argument('zipfiles', type=str, nargs='+', metavar='zipfiles',
                        help="List of zipfiles to extract information from and print to screen. "
                             "See option switches to see printing options.")

    parser.add_argument('-stninfo', '--station_info', action='store_true',
                        help="Print the station information content (in GAMIT format) to the screen.")

    parser.add_argument('-ins', '--insert_sql', action='store_true',
                        help="Produce a SQL INSERT statement for this station including OTL and coordinates.")

    add_version_argument(parser)

    args = parser.parse_args()

    for zipfile in args.zipfiles:
        # extract the json for this station
        json_path = extract_json(zipfile)
        station   = json.loads(file_read_all(json_path))

        if args.station_info:
            print_station_info(station['NetworkCode'],
                               station['StationCode'],
                               station['StationInfo'])

        if args.insert_sql:
            print_insert_sql(station)

    if os.path.exists('production/import'):
        shutil.rmtree('production/import')


def print_insert_sql(station):

    print('INSERT INTO stations ("NetworkCode", "StationCode", "auto_x", "auto_y", "auto_z", ' \
          '"Harpos_coeff_otl", lat, lon, height) VALUES ' \
          '(\'???\', \'%s\', %.4f, %.4f, %.4f, \'%s\', %.8f, %.8f, %.3f)' \
          % (station['StationCode'],
             station['x'],
             station['y'],
             station['z'],
             station['otl'],
             station['lat'],
             station['lon'],
             station['height']))


def print_station_info(NetworkCode, StationCode, stninfo):

    for record in stninfo:
        import_record = pyStationInfo.StationInfoRecord(NetworkCode, StationCode, record)

        print(import_record)


def extract_json(zipfile):

    # Create a ZipFile Object and load sample.zip in it
    with ZipFile(zipfile, 'r') as zipObj:
        # Get a list of all archived file names from the zip
        list_of_names = zipObj.namelist()
        # Iterate over the file names
        for fileName in list_of_names:
            # Check filename endswith csv
            if fileName.endswith('.json'):
                # Extract a single file from zip
                zipObj.extract(fileName, 'production/import')
                return 'production/import/' + fileName


if __name__ == '__main__':
    main()

