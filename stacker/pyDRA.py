"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import argparse
import os
from datetime import datetime
import json

# deps
import numpy as np
from tqdm import tqdm
import matplotlib
if not os.environ.get('DISPLAY', None):
    matplotlib.use('Agg')
import matplotlib.pyplot as plt

# app
import dbConnection
import pyETM
import pyDate
from Utils import process_date
from pyStack import Polyhedron, np_array_vertices
from pyDate import Date
from Utils import file_write, json_converter

LIMIT = 2.5


def sql_select(project, fields, date2):
    return '''SELECT %s from gamit_soln
          WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i
          ORDER BY "NetworkCode", "StationCode"''' % (fields, project, date2.year, date2.doy)



class DRA(list):

    def __init__(self, cnn, project, end_date, verbose=False):

        super(DRA, self).__init__()

        self.project = project
        self.cnn = cnn
        self.transformations = []
        self.verbose = verbose

        if end_date is None:
            end_date = Date(datetime=datetime.now())

        print(' >> Loading GAMIT solutions for project %s...' % project)

        gamit_vertices = self.cnn.query_float(
            'SELECT "NetworkCode" || \'.\' || "StationCode", "X", "Y", "Z", "Year", "DOY", "FYear" '
            'FROM gamit_soln WHERE "Project" = \'%s\' AND ("Year", "DOY") <= (%i, %i)'
            'ORDER BY "NetworkCode", "StationCode"' % (project, end_date.year, end_date.doy))


        self.gamit_vertices = np_array_vertices(gamit_vertices)

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

        for j in tqdm(list(range(len(self) - 1)), desc=' >> Daily repetitivity analysis progress', ncols=160):

            # should only attempt to align a polyhedron that is unaligned
            # do not set the polyhedron as aligned unless we are in the max iteration step
            self[j + 1].align(self[j], scale=False, verbose=self.verbose)
            # write info to the screen
            tqdm.write(' -- %s (%3i) %2i it wrms: %4.1f T %6.1f %6.1f %6.1f '
                       'R (%6.1f %6.1f %6.1f)*1e-9 D-W: %3i' %
                       (self[j + 1].date.yyyyddd(),
                        self[j + 1].stations_used,
                        self[j + 1].iterations,
                        self[j + 1].wrms * 1000,
                        self[j + 1].helmert[3] * 1000,
                        self[j + 1].helmert[4] * 1000,
                        self[j + 1].helmert[5] * 1000,
                        self[j + 1].helmert[0],
                        self[j + 1].helmert[1],
                        self[j + 1].helmert[2],
                        self[j + 1].downweighted
                        ))

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
                ts.append([p['x'][0],
                           p['y'][0],
                           p['z'][0],
                           p['yr'][0],
                           p['dd'][0],
                           p['fy'][0]])

        return np.array(ts)

    def to_json(self, json_file):
        # print(repr(self.transformations))
        file_write(json_file,
                   json.dumps({ 'transformations' : self.transformations },
                              indent=4, sort_keys=False, default=json_converter
                              ))


def main():

    parser = argparse.ArgumentParser(description='GNSS daily repetitivities analysis (DRA)')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")

    parser.add_argument('-d', '--date_filter', nargs='+', metavar='date',
                        help='Date range filter. Can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')

    parser.add_argument('-w', '--plot_window', nargs='+', metavar='date',
                        help='Date window range to plot. Can be specified in yyyy/mm/dd yyyy_doy  wwww-d format')
    parser.add_argument('-hist', '--histogram', action='store_true',
                        help="Plot a histogram of the daily repetitivities")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Provide additional information during the alignment process (for debugging purposes)")

    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Provide additional information during the alignment process (for debugging purposes)")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    project = args.project[0]

    dates = [pyDate.Date(year=1980, doy=1),
             pyDate.Date(year=2100, doy=1)]
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
            pdates = (pdates[0].fyear,
                      pdates[1].fyear)

    # create folder for plots
    path_plot = project + '_dra'
    if not os.path.isdir(path_plot):
        os.makedirs(path_plot)

    ########################################
    # load polyhedrons
    # create the DRA object
    dra = DRA(cnn, args.project[0], dates[1], args.verbose)

    dra.stack_dra()

    dra.to_json(project + '_dra.json')

    wrms_n = []
    wrms_e = []
    wrms_u = []

    # plot each DRA
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

                    if etm.A is not None:
                        etm.plot(pngfile='%s/%s.%s_DRA.png' % (project + '_dra', NetworkCode, StationCode),
                                 plot_missing=False, t_win=pdates)
                        if args.histogram:
                            etm.plot_hist(pngfile='%s/%s.%s_DRA_hist.png' %
                                                  (project + '_dra', NetworkCode, StationCode))

                        # save the wrms
                        wrms_n.append(etm.factor[0] * 1000)
                        wrms_e.append(etm.factor[1] * 1000)
                        wrms_u.append(etm.factor[2] * 1000)

            except Exception as e:
                tqdm.write(' --> while working on %s.%s' % (NetworkCode, StationCode) + '\n' + traceback.format_exc())

    wrms_n = np.array(wrms_n)
    wrms_e = np.array(wrms_e)
    wrms_u = np.array(wrms_u)

    # plot the WRM of the DRA stack and number of stations
    f, axis = plt.subplots(nrows=3, ncols=2, figsize=(15, 10))  # type: plt.subplots

    # WRMS
    ax = axis[0][0]
    ax.plot([t['fyear']       for t in dra.transformations[0]],
            [t['wrms'] * 1000 for t in dra.transformations[0]], 'ob', markersize=2)
    ax.set_ylabel('WRMS [mm]')
    ax.grid(True)
    ax.set_ylim(0, 10)

    # station count
    ax = axis[1][0]
    ax.plot([t['fyear']         for t in dra.transformations[0]],
            [t['stations_used'] for t in dra.transformations[0]], 'ob', markersize=2)
    ax.set_ylabel('Station count')
    ax.grid(True)

    # d-w fraction
    ax = axis[2][0]
    ax.plot([t['fyear']                 for t in dra.transformations[0]],
            [t['downweighted_fraction'] for t in dra.transformations[0]], 'ob', markersize=2)
    ax.set_ylabel('DW fraction')
    ax.grid(True)

    ax = axis[0][1]
    ax.hist(wrms_n[wrms_n <= 8], 40, alpha=0.75, facecolor='blue')
    ax.grid(True)
    ax.set_ylabel('# stations')
    ax.set_xlabel('WRMS misfit N [mm]')
    ax.set_title('Daily repetitivities NEU')

    ax = axis[1][1]
    ax.hist(wrms_e[wrms_e <= 8], 40, alpha=0.75, facecolor='blue')
    ax.grid(True)
    ax.set_xlim(0, 8)
    ax.set_ylabel('# stations')
    ax.set_xlabel('WRMS misfit E [mm]')

    ax = axis[2][1]
    ax.hist(wrms_u[wrms_u <= 10], 40, alpha=0.75, facecolor='blue')
    ax.grid(True)
    ax.set_xlim(0, 10)
    ax.set_ylabel('# stations')
    ax.set_xlabel('WRMS misfit U [mm]')

    f.suptitle('Daily repetitivity analysis for project %s\n'
               'Solutions with WRMS > 10 mm are not shown' % project,
               fontsize=12, family='monospace')
    plt.savefig(project + '_dra.png')
    plt.close()


    ax.set_xlim(0, 8)
if __name__ == '__main__':
    main()
