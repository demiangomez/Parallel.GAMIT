"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to generate a KML with the stations in a project and the stations out of a project
"""

import argparse
import dbConnection
from Utils import process_stnlist
import os
from pyGamitConfig import GamitConfiguration
from tqdm import tqdm
import simplekml


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project_file', type=str, nargs=1, metavar='{project cfg file}',
                        help="Project CFG file with all the stations being processed in Parallel.GAMIT")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    GamitConfig = GamitConfiguration(args.project_file[0])  # type: GamitConfiguration

    stations = process_stnlist(cnn, GamitConfig.NetworkConfig['stn_list'].split(','))

    generate_kml(cnn, GamitConfig.NetworkConfig.network_id.lower(), stations)


def generate_kml(cnn, project, stations):

    tqdm.write('  >> Generating KML for this run (see production directory)...')

    kml = simplekml.Kml()

    folder = kml.newfolder(name=project)

    tqdm(' >> Adding stations in project')
    for stn in tqdm(stations, ncols=80):

        rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                             % (stn['NetworkCode'], stn['StationCode']), as_dict=True)

        pt = folder.newpoint(name=stn['NetworkCode'] + '.' + stn['StationCode'], coords=[(rs[0]['lon'], rs[0]['lat'])])

        pt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/' \
                                       'placemark_square_highlight.png'

    rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%\' '
                         'ORDER BY "NetworkCode", "StationCode" ', as_dict=True)

    tqdm(' >> Adding ALL stations in database')

    folder = kml.newfolder(name='all stations')

    for stn in tqdm(rs, ncols=80):
        pt = folder.newpoint(name=stn['NetworkCode'] + '.' + stn['StationCode'], coords=[(stn['lon'], stn['lat'])])

        pt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/' \
                                       'placemark_circle.png'

    if not os.path.exists('production'):
        os.makedirs('production')

    kml.savekmz('production/' + project + '.kmz')


if __name__ == '__main__':
    main()