#!/usr/bin/env python

"""
Project: Parallel.PPP
Date: 10/10/17 9:10 AM
Author: Demian D. Gomez

User interface to plot and save JSON files of ETM objects.
Type python pyPlotETM.py -h for usage help
"""
import argparse
import os
import traceback
import json

# deps
import numpy as np
import zipfile
from io import BytesIO
import xml.etree.ElementTree as ET

# app
from pgamit import pyETM
from pgamit import dbConnection
from pgamit import pyDate
from pgamit.Utils import (process_date,
                          process_stnlist,
                          file_write,
                          station_list_help,
                          stationID,
                          print_columns,
                          add_version_argument)


def read_kml_or_kmz(file_path):
    # Check if the file is a KMZ (by its extension)
    if file_path.endswith('.kmz'):
        # Open the KMZ file and read it in memory
        with zipfile.ZipFile(file_path, 'r') as kmz:
            # List all files in the KMZ archive
            kml_file = None
            for file_name in kmz.namelist():
                if file_name.endswith(".kml"):
                    kml_file = file_name
                    break

            if not kml_file:
                raise Exception("No KML file found in the KMZ archive")

            # Extract the KML file into memory (as a BytesIO object)
            kml_content = kmz.read(kml_file)
            kml_file = BytesIO(kml_content)

    else:
        # If the file is a regular KML, process it directly
        kml_file = open(file_path, 'r')

    # Extract coordinates from the KML file
    placemarks = extract_placemarks(kml_file)

    # Close the file if it was opened from the filesystem
    if isinstance(kml_file, BytesIO) == False:
        kml_file.close()

    return placemarks


# Helper function to extract placemark and coordinates from a KML file
def extract_placemarks(kml_file):
    tree = ET.parse(kml_file)
    root = tree.getroot()

    # Define the KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    # Initialize list to store placemark names and coordinates
    placemarks = []

    # Loop through all placemarks
    for placemark in root.findall('.//kml:Placemark', ns):
        # Extract the placemark name (if available)
        name_element = placemark.find('kml:name', ns)
        name = name_element.text if name_element is not None else "Unnamed"

        # Extract the coordinates for the placemark
        coordinates_list = []
        for coord in placemark.findall('.//kml:coordinates', ns):
            coords = coord.text.strip().split()
            for coord_str in coords:
                lon, lat, height = coord_str.split(',')  # Ignore the altitude (third value)
                coordinates_list.append((float(lon), float(lat), float(height)))

        # Store the placemark name and its coordinates
        for coord in coordinates_list:
            placemarks.append((name, coord))

    return placemarks


def gamit_soln(args, cnn, stn):
    polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM stacks '
                                  'WHERE "name" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                  '"StationCode" = \'%s\' '
                                  'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                  % (args.gamit[0], stn['NetworkCode'], stn['StationCode']))

    soln = pyETM.GamitSoln(cnn, polyhedrons, stn['NetworkCode'], stn['StationCode'], args.gamit[0])

    etm = pyETM.GamitETM(cnn, stn['NetworkCode'], stn['StationCode'], False,
                         args.no_model, gamit_soln=soln, plot_remove_jumps=args.remove_jumps,
                         plot_polynomial_removed=args.remove_polynomial)
    #   postseismic=[{'date': pyDate.Date(year=2010,doy=58),
    #  'relaxation': [0.5],
    #  'amplitude': [[-0.0025, -0.0179, -0.005]]}])

    # print ' > %5.2f %5.2f %5.2f %i %i' % \
    #      (etm.factor[0]*1000, etm.factor[1]*1000, etm.factor[2]*1000, etm.soln.t.shape[0],
    #       etm.soln.t.shape[0] -
    #       np.sum(np.logical_and(np.logical_and(etm.F[0], etm.F[1]), etm.F[2])))

    # print two largest outliers
    if etm.A is not None:
        lres = np.sqrt(np.sum(np.square(etm.R), axis=0))
        slres = lres[np.argsort(-lres)]

        print(' >> Two largest residuals:')
        for i in [0, 1]:
            print(' %s %6.3f %6.3f %6.3f'
                  % (pyDate.Date(mjd=etm.soln.mjd[lres == slres[i]]).yyyyddd(),
                     etm.R[0, lres == slres[i]][0],
                     etm.R[1, lres == slres[i]][0],
                     etm.R[2, lres == slres[i]][0]))

    return etm


def from_file(args, cnn, stn, placemarks):

    # replace any variables with the station name
    filename = args.filename.replace('{net}', stn['NetworkCode']).replace('{stn}', stn['StationCode'])

    # execute on a file with wk XYZ coordinates
    ts = np.genfromtxt(filename)

    # read the format options
    if args.format is None:
        raise Exception('A format should be specified using the -format switch')

    dd = []
    x = []
    y = []
    z = []
    for k in ts:
        d = {}
        for i, f in enumerate(args.format):
            if f in ('gpsWeek', 'gpsWeekDay', 'year', 'doy', 'fyear', 'month', 'day', 'mjd'):
                d[f] = k[i]

            if f == 'x':
                x.append(k[i])
            elif f == 'y':
                y.append(k[i])
            elif f == 'z':
                z.append(k[i])
        dd.append(d)

    dd = [pyDate.Date(**d) for d in dd]

    polyhedrons = np.array((x, y, z, [d.year for d in dd], [d.doy for d in dd])).transpose()

    if args.override_database:
        placemark = [pl for pl in placemarks if stationID(stn) == pl[0]]
        soln = pyETM.ListSoln(cnn, polyhedrons.tolist(), stn['NetworkCode'], stn['StationCode'],
                              station_metadata=placemark[0])
    else:
        soln = pyETM.ListSoln(cnn, polyhedrons.tolist(), stn['NetworkCode'], stn['StationCode'])

    etm  = pyETM.FileETM(cnn, soln, False, args.no_model, args.remove_jumps, args.remove_polynomial)

    return etm


def main():
    parser = argparse.ArgumentParser(description='Plot ETM for stations in the database')

    parser.add_argument('stnlist', type=str, nargs='+',
                        help=station_list_help())

    parser.add_argument('-nop', '--no_plots', action='store_true',
                        help="Do not produce plots", default=False)

    parser.add_argument('-pm', '--plot_missing_data', action='store_true',
                        help="Show missing days as magenta lines in the plot", default=False)

    parser.add_argument('-nm', '--no_model', action='store_true',
                        help="Plot time series without fitting a model")

    parser.add_argument('-r', '--residuals', action='store_true',
                        help="Plot time series residuals", default=False)

    parser.add_argument('-dir', '--directory', type=str,
                        help="Directory to save the resulting PNG files. If not specified, assumed to be the "
                             "production directory")

    parser.add_argument('-json', '--json', type=int,
                        help="Export ETM adjustment to JSON. Append '0' to just output "
                        "the ETM parameters, '1' to export time series without "
                        "model and '2' to export both time series and model.")

    parser.add_argument('-gui', '--interactive', action='store_true',
                        help="Interactive mode: allows to zoom and view the plot interactively")

    parser.add_argument('-rj', '--remove_jumps', action='store_true', default=False,
                        help="Remove jumps from model and time series before plotting")

    parser.add_argument('-rp', '--remove_polynomial', action='store_true', default=False,
                        help="Remove polynomial terms from model and time series before plotting")

    parser.add_argument('-win', '--time_window', nargs='+', metavar='interval',
                        help='Date range to window data. Can be specified in yyyy/mm/dd, yyyy.doy or as a single '
                             'integer value (N) which shall be interpreted as last epoch-N')

    parser.add_argument('-q', '--query', nargs=2, metavar='{type} {date}', type=str,
                        help='Dates to query the ETM. Specify "model" or "solution" to get the ETM value or the value '
                             'of the daily solution (if exists). Output is in XYZ.')

    parser.add_argument('-gamit', '--gamit', type=str, nargs=1, metavar='{stack}',
                        help="Plot the GAMIT time series specifying which stack name to plot.")

    parser.add_argument('-lang', '--language', type=str,
                        help="Change the language of the plots. Default is English. "
                        "Use ESP to select Spanish. To add more languages, "
                        "include the ISO 639-1 code in pyETM.py", default='ENG')

    parser.add_argument('-hist', '--histogram', action='store_true',
                        help="Plot histogram of residuals")

    parser.add_argument('-file', '--filename', type=str,
                        help="Obtain data from an external source (filename). This name accepts variables for {net} "
                             "and {stn} to specify more than one file based on a list of stations. If a single file is "
                             "used (no variables), then only the first station is processed. File column format should "
                             "be specified with -format (required).")

    parser.add_argument('-format', '--format', nargs='+', type=str,
                        help="To be used together with --filename. Specify order of the fields as found in the input "
                             "file. Format strings are gpsWeek, gpsWeekDay, year, doy, fyear, month, day, mjd, "
                             "x, y, z, na. Use 'na' to specify a field that should be ignored. If fields to be ignored "
                             "are at the end of the line, then there is no need to specify those.")

    parser.add_argument('-no_db', '--override_database', nargs=1, type=str, default=None,
                        help="To be used together with --filename and --format. Do not fetch station metadata from "
                             "the database but rather use the provided kmz/kml file to obtain station coordinates "
                             "and other relevant metadata. When using this option, the station list is ignored and "
                             "only one station is processed.")

    parser.add_argument('-outliers', '--plot_outliers', action='store_true',
                        help="Plot an additional panel with the outliers")

    parser.add_argument('-dj', '--detected_jumps', action='store_true',
                        help="Plot unmodeled detected jumps")

    parser.add_argument('-vel', '--velocity', action='store_true',
                        help="During query, output the velocity in XYZ.")

    parser.add_argument('-seasonal', '--seasonal_terms', action='store_true',
                        help="During query, output the seasonal terms in NEU.")

    parser.add_argument('-quiet', '--suppress_messages', action='store_true',
                        help="Quiet mode: suppress information messages")

    add_version_argument(parser)

    args = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg', write_cfg_file=True)

    if args.override_database:
        # user selected database override
        placemarks = read_kml_or_kmz(args.override_database[0])
        stnlist = [{'NetworkCode': stnm.split('.')[0], 'StationCode': stnm.split('.')[1]} for stnm, _ in placemarks]

        print(' >> Station from kml/kmz file %s' % args.override_database[0])
        print_columns([stationID(item) for item in stnlist])
    else:
        placemarks = []
        stnlist = process_stnlist(cnn, args.stnlist)

    # define the language
    pyETM.LANG = args.language.lower()
    # set the logging level
    if not args.suppress_messages:
        pyETM.logger.setLevel(pyETM.INFO)
    #####################################
    # date filter

    dates = None
    if args.time_window is not None:
        if len(args.time_window) == 1:
            try:
                dates = process_date(args.time_window, missing_input=None, allow_days=False)
                dates = (dates[0].fyear,)
            except ValueError:
                # an integer value
                dates = float(args.time_window[0])
        else:
            dates = process_date(args.time_window)
            dates = (dates[0].fyear,
                     dates[1].fyear)

    if stnlist:
        # do the thing
        if args.directory:
            if not os.path.exists(args.directory):
                os.mkdir(args.directory)
        else:
            if not os.path.exists('production'):
                os.mkdir('production')
            args.directory = 'production'

        # flag to stop plotting time series when using external files
        stop = False

        for stn in stnlist:
            try:

                if args.gamit is None and args.filename is None:
                    etm = pyETM.PPPETM(cnn, stn['NetworkCode'], stn['StationCode'], False, args.no_model,
                                       plot_remove_jumps=args.remove_jumps,
                                       plot_polynomial_removed=args.remove_polynomial)

                elif args.filename is not None:
                    if '{stn}' in args.filename or '{net}' in args.filename:
                        # repeat the process for each station
                        stop = False
                    else:
                        # stop on the first station since no variables were passed
                        stop = True

                    etm = from_file(args, cnn, stn, placemarks)
                else:
                    etm = gamit_soln(args, cnn, stn)

                if args.interactive:
                    xfile = None
                else:
                    postfix = "gamit"
                    if args.gamit is None:
                        postfix = "ppp" if args.filename is None else "file"

                    xfile = os.path.join(args.directory, '%s.%s_%s' % (etm.NetworkCode,
                                                                       etm.StationCode,
                                                                       postfix))

                # leave pngfile empty to enter interactive mode (GUI)
                if not args.no_plots:
                    etm.plot(xfile + '.png',
                             t_win          = dates,
                             residuals      = args.residuals,
                             plot_missing   = args.plot_missing_data,
                             plot_outliers  = args.plot_outliers,
                             plot_auto_jumps= args.detected_jumps)

                    if args.histogram:
                        etm.plot_hist(xfile + '_hist.png')

                if args.json is not None:
                    if args.json == 1:
                        obj = etm.todictionary(time_series=True)
                    elif args.json == 2:
                        obj = etm.todictionary(time_series=True, model=True)
                    else:
                        obj = etm.todictionary(False)

                    file_write(xfile + '.json',
                               json.dumps(obj, indent=4, sort_keys=False))

                if args.query is not None:
                    model  = (args.query[0] == 'model')
                    q_date = pyDate.Date(fyear = float(args.query[1]))

                    xyz, _, _, txt = etm.get_xyz_s(q_date.year, q_date.doy, force_model=model)

                    strp = ''
                    # if user requests velocity too, output it
                    if args.velocity:
                        if etm.A is not None:
                            vxyz = etm.rotate_2xyz(etm.Linear.p.params[:, 1])
                            strp = '%8.5f %8.5f %8.5f ' \
                                   % (vxyz[0, 0], vxyz[1, 0], vxyz[2, 0])

                    # also output seasonal terms, if requested
                    if args.seasonal_terms and etm.Periodic.frequency_count > 0:
                        strp += ' '.join(['%8.5f' % (x * 1000) for x in etm.Periodic.p.params.flatten().tolist()])

                    print(' %s.%s %14.5f %14.5f %14.5f %8.3f %s -> %s' \
                          % (etm.NetworkCode, etm.StationCode, xyz[0], xyz[1], xyz[2], q_date.fyear, strp, txt))

                print('Successfully plotted ' + stn['NetworkCode'] + '.' + stn['StationCode'])
                # print(etm.pull_params())
                # if the stop flag is true, stop processing after the first station
                if stop:
                    break

            except pyETM.pyETMException as e:
                print(str(e))

            except Exception:
                print('Error during processing of ' + stn['NetworkCode'] + '.' + stn['StationCode'])
                print(traceback.format_exc())


if __name__ == '__main__':
    main()
