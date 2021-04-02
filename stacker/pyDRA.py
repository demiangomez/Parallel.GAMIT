"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import dbConnection
import argparse
import pyETM
import pyDate
import os
import numpy as np
from Utils import process_date
from pyStack import Polyhedron
from datetime import datetime
from tqdm import tqdm
from pyDate import Date
import json

LIMIT = 2.5


def sql_select(project, fields, date2):

    sql = '''SELECT %s from gamit_soln
          WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i
          ORDER BY "NetworkCode", "StationCode"''' % (fields, project, date2.year, date2.doy)

    return sql


class DRA(list):

    def __init__(self, cnn, project, end_date):

        super(DRA, self).__init__()

        self.project = project
        self.cnn = cnn
        self.transformations = []

        if end_date is None:
            end_date = Date(datetime=datetime.now())

        print ' >> Loading GAMIT solutions for project %s...' % project

        gamit_vertices = self.cnn.query_float(
            'SELECT "NetworkCode" || \'.\' || "StationCode", "X", "Y", "Z", "Year", "DOY", "FYear" '
            'FROM gamit_soln WHERE "Project" = \'%s\' AND ("Year", "DOY") <= (%i, %i)'
            'ORDER BY "NetworkCode", "StationCode"' % (project, end_date.year, end_date.doy))

        self.gamit_vertices = np.array(gamit_vertices, dtype=[('stn', 'S8'), ('x', 'float64'), ('y', 'float64'),
                                                              ('z', 'float64'), ('yr', 'i4'), ('dd', 'i4'),
                                                              ('fy', 'float64')])

        dates = self.cnn.query_float('SELECT "Year", "DOY" FROM gamit_soln WHERE "Project" = \'%s\' '
                                     'AND ("Year", "DOY") <= (%i, %i) '
                                     'GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"'
                                     % (project, end_date.year, end_date.doy))

        self.dates = [Date(year=int(d[0]), doy=int(d[1])) for d in dates]

        self.stations = self.cnn.query_float('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                                             'WHERE "Project" = \'%s\' AND ("Year", "DOY") <= (%i, %i) '
                                             'GROUP BY "NetworkCode", "StationCode" '
                                             'ORDER BY "NetworkCode", "StationCode"'
                                             % (project, end_date.year, end_date.doy), as_dict=True)

        for d in tqdm(self.dates, ncols=160, desc=' >> Initializing the stack polyhedrons'):
            self.append(Polyhedron(self.gamit_vertices, project, d))

    def stack_dra(self):

        for j in tqdm(range(len(self) - 1), desc=' >> Daily repetitivity analysis progress', ncols=160):

            # should only attempt to align a polyhedron that is unaligned
            # do not set the polyhedron as aligned unless we are in the max iteration step
            self[j + 1].align(self[j], scale=False)
            # write info to the screen
            tqdm.write(' -- %s (%3i) %2i it wrms: %4.1f T %6.1f %6.1f %6.1f '
                       'R (%6.1f %6.1f %6.1f)*1e-9' %
                       (self[j + 1].date.yyyyddd(), self[j + 1].stations_used, self[j + 1].iterations,
                        self[j + 1].wrms * 1000, self[j + 1].helmert[3] * 1000, self[j + 1].helmert[4] * 1000,
                        self[j + 1].helmert[5] * 1000, self[j + 1].helmert[0], self[j + 1].helmert[1],
                        self[j + 1].helmert[2]))

        self.transformations.append([poly.info() for poly in self[1:]])

    def get_station(self, NetworkCode, StationCode):
        """
        Obtains the time series for a given station
        :param NetworkCode:
        :param StationCode:
        :return: a numpy array with the time series [x, y, z, yr, doy, fyear]
        """

        stnstr = NetworkCode + '.' + StationCode

        ts = []

        for poly in self:
            p = poly.vertices[poly.vertices['stn'] == stnstr]
            if p.size:
                ts.append([p['x'][0], p['y'][0], p['z'][0], p['yr'][0], p['dd'][0], p['fy'][0]])

        return np.array(ts)

    def to_json(self, json_file):
        json_dump = dict()
        json_dump['transformations'] = self.transformations

        with open(json_file, 'w') as f:
            json.dump(json_dump, f, indent=4, sort_keys=False)


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")
    parser.add_argument('-d', '--date_filter', nargs='+', metavar='date',
                        help='Date range filter. Can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')
    parser.add_argument('-w', '--plot_window', nargs='+', metavar='date',
                        help='Date window range to plot. Can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    project = args.project[0]

    dates = [pyDate.Date(year=1980, doy=1), pyDate.Date(year=2100, doy=1)]
    try:
        dates = process_date(args.date_filter)
    except ValueError as e:
        parser.error(str(e))

    pdates = None
    if args.plot_window is not None:
        if len(args.plot_window) == 1:
            try:
                pdates = process_date(args.plot_window, missing_input=None, allow_days=False)
                pdates = (pdates[0].fyear,)
            except ValueError:
                # an integer value
                pdates = float(args.plot_window[0])
        else:
            pdates = process_date(args.plot_window)
            pdates = (pdates[0].fyear, pdates[1].fyear)

    # create folder for plots

    if not os.path.isdir(project + '_dra'):
        os.makedirs(project + '_dra')

    ########################################
    # load polyhedrons

    dra = DRA(cnn, args.project[0], dates[1])

    dra.stack_dra()

    for stn in tqdm(dra.stations):
        NetworkCode = stn['NetworkCode']
        StationCode = stn['StationCode']

        # load from the db
        ts = dra.get_station(NetworkCode, StationCode)

        if ts.size:
            try:
                if ts.shape[0] > 2:
                    dts = np.append(np.diff(ts[:, 0:3], axis=0), ts[1:, -3:], axis=1)

                    dra_ts = pyETM.GamitSoln(cnn, dts, NetworkCode, StationCode, project)

                    etm = pyETM.DailyRep(cnn, NetworkCode, StationCode, False, False, dra_ts)

                    etm.plot(pngfile='%s/%s.%s_DRA.png' % (project + '_dra', NetworkCode, StationCode),
                             plot_missing=False, t_win=pdates)

            except Exception as e:
                tqdm.write(' -->' + str(e))

    dra.to_json(project + '_dra.json')


if __name__ == '__main__':
    main()
