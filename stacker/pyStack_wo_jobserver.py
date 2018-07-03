"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import dbConnection
import pyOptions
import argparse
import pyPPPETM
import pyJobServer
import numpy as np
from pyDate import Date
from tqdm import tqdm


class AlignClass:
    def __init__(self, pbar):
        self.pbar = pbar
        self.date = None
        self.polyhedron = None

    def finalize(self, args):
        self.polyhedron = args[0]
        self.date = args[1]
        self.pbar.update(1)


class Station:

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode  = NetworkCode
        self.StationCode  = StationCode
        self.StationAlias = StationCode  # upon creation, Alias = StationCode
        self.record       = None
        self.etm          = None
        self.StationInfo  = None
        self.lat          = None
        self.lon          = None
        self.height       = None
        self.X            = None
        self.Y            = None
        self.Z            = None
        self.otl_H        = None

        try:
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                           % (NetworkCode, StationCode))

            if rs.ntuples() != 0:
                self.record = rs.dictresult() # type: dict

                self.lat = float(self.record[0]['lat'])
                self.lon = float(self.record[0]['lon'])
                self.height = float(self.record[0]['height'])
                self.X      = float(self.record[0]['auto_x'])
                self.Y      = float(self.record[0]['auto_y'])
                self.Z      = float(self.record[0]['auto_z'])

        except Exception:
            raise

    def __str__(self):
        return self.NetworkCode + '.' + self.StationCode

    def __repr__(self):
        return 'pyStack.Station(' + str(self) + ')'


class Project:

    def __init__(self, cnn, name):

        self.name = name

        # get the station list
        rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                       'WHERE "Project" = \'%s\' GROUP BY "NetworkCode", "StationCode" '
                       'ORDER BY "NetworkCode", "StationCode"' % name)

        self.stnlist = [Station(cnn, item['NetworkCode'], item['StationCode']) for item in rs.dictresult()]

        # get the epochs
        rs = cnn.query('SELECT "Year", "DOY" FROM gamit_soln '
                       'WHERE "Project" = \'%s\' GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % name)

        rs = rs.dictresult()
        self.epochs = [Date(year=item['Year'], doy=item['DOY']) for item in rs]

        # load the polyhedrons
        self.polyhedrons = []

        print ' >> Loading polyhedrons. Please wait...'

        rs = cnn.query('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' '
                       'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"' % name)

        self.polyhedrons = rs.dictresult()
        self.ts = []
        self.etms = []

        self.calculate_etms(cnn)
        self.cnn = cnn

        # load the transformations, if any

        # load the metadata (stabilization sites)

    def calculate_etms(self, cnn):

        self.ts = []
        self.etms = []

        # get the ts of each station
        qbar = tqdm(total=len(self.stnlist), desc=' >> Calculating ETMs', ncols=160)

        removestn = []

        for stn in self.stnlist:
            # extract this station from the dictionary
            rs = cnn.query('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' AND "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                           'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"' % (self.name, stn.NetworkCode, stn.StationCode))

            stn_ts = rs.dictresult()

            qbar.set_postfix(station=str(stn))

            self.ts += [pyPPPETM.GamitSoln(cnn, stn_ts, stn.StationCode, stn.NetworkCode)]

            self.etms += [pyPPPETM.GamitETM(cnn, stn.NetworkCode, stn.StationCode, False, False, self.ts[-1])]

            if self.etms[-1].A is None:
                # no contribution to stack, remove from the station list
                qbar.write(' -- Removing %s.%s: no ETM' % (stn.NetworkCode, stn.StationCode))
                removestn += [stn]

            qbar.update()

        # remove stations without ETM
        for rstn in removestn:
            # remove from station list
            self.stnlist = [stn for stn in self.stnlist
                            if stn.NetworkCode != rstn.NetworkCode and stn.StationCode != rstn.StationCode]
            # remove from polyhedrons
            self.polyhedrons = [item for item in self.polyhedrons if
                                item['NetworkCode'] != rstn.NetworkCode and item['StationCode'] != rstn.StationCode]
            # remove ETM
            self.etms = [item for item in self.etms if
                                item.NetworkCode != rstn.NetworkCode and item.StationCode != rstn.StationCode]
        qbar.close()

    def align_stack(self):

        updated_poly = []

        qbar = tqdm(total=len(self.epochs), desc=' >> Aligning polyhedrons', ncols=160)

        for date in self.epochs:

            qbar.set_postfix(day=str(date.yyyyddd()))

            residuals = [{'NetworkCode': item.NetworkCode,
                          'StationCode': item.StationCode,
                          'residuals': item.get_residual(date.year, date.doy)} for item in self.etms]

            p, x = self.helmert_trans(residuals, date)
            updated_poly += p

            # qbar.write(' -- %s: translation (mm mm mm) scale: (%6.1f %6.1f %6.1f) %10.2e' % (date.yyyyddd(), x[-3]*1000, x[-2]*1000, x[-1]*1000, x[-4]))
            qbar.update()

        qbar.close()

        self.polyhedrons = updated_poly
        self.calculate_etms(self.cnn)

    def helmert_trans(self, residuals, date):

        x = self.cnn.query('SELECT 0, -"Z", "Y", "X", 1, 0, 0 FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i ORDER BY "NetworkCode", "StationCode"' % (self.name, date.year, date.doy))
        y = self.cnn.query('SELECT "Z", 0, -"X", "Y", 0, 1, 0 FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i ORDER BY "NetworkCode", "StationCode"' % (self.name, date.year, date.doy))
        z = self.cnn.query('SELECT -"Y", "X", 0, "Z", 0, 0, 1 FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i ORDER BY "NetworkCode", "StationCode"' % (self.name, date.year, date.doy))

        X = self.cnn.query('SELECT "X", "Y", "Z" FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i ORDER BY "NetworkCode", "StationCode"' % (self.name, date.year, date.doy))

        x = x.getresult()
        y = y.getresult()
        z = z.getresult()
        X = X.getresult()

        Ax = np.array(x)
        Ay = np.array(y)
        Az = np.array(z)

        X  = np.array(X)

        return [], []


class Polyhedron:

    def __init__(self, cnn, project, date):

        self.epoch = date

        fieldnames = ['NetworkCode', 'StationCode', 'X', 'Y', 'Z', 'Year', 'DOY', 'sigmax', 'sigmay', 'sigmaz',
                      'sigmaxy', 'sigmaxz', 'sigmayz']

        self.geometry = dict.fromkeys(fieldnames)

        rs = cnn.query('SELECT * FROM gamit_soln WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                       % (project, date.year, date.doy))

        for record in rs.dictresult():
            for key in self.geometry.keys():
                self.geometry[key] = record[key]


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project', type=str, nargs=1, metavar='{project name}',
                        help="Specify the project name used to process the GAMIT solutions in Parallel.GAMIT.")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")
    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    if not args.noparallel:
        JobServer = pyJobServer.JobServer(Config, run_node_test=False)  # type: pyJobServer.JobServer
    else:
        JobServer = None
        Config.run_parallel = False

    # create the execution log
    # cnn.insert('executions', script='pyStack.py')

    # load polyhedrons
    project = Project(cnn, args.project[0])

    # plot initial state
    tqdm.write(' -- Plotting initial ETMs (unaligned)...')

    #for etm in tqdm(project.etms, ncols=160):
    #    etm.plot(pngfile=args.project[0] + '/' + etm.NetworkCode + '.' + etm.StationCode + '_0.png', residuals=True)

    project.align_stack()

    tqdm.write(' -- Plotting intermediate step ETMs (aligned)...')

    #for etm in tqdm(project.etms, ncols=160):
    #    etm.plot(pngfile=args.project[0] + '/' + etm.NetworkCode + '.' + etm.StationCode + '_1.png')



if __name__ == '__main__':
    main()