"""
Project: Parallel.Stacker
Date: 6/12/18 10:28 AM
Author: Demian D. Gomez
"""

import dbConnection
import pyOptions
from tqdm import tqdm
import argparse
from pyDate import Date
import pyPPPETM
import pyJobServer
import numpy as np


def helmert_trans(p_poly, p_etms, date):

    # get day polyhedron
    poly = [item for item in p_poly if item['Year'] == date.year and item['DOY'] == date.doy]

    # get ETM predictions
    etms = []
    etms += [np.array([etm['X'], etm['Y'], etm['Z']]) for etm in p_etms if etm['mjd'] == date.mjd]

    Ax = np.zeros((len(poly), 7))
    Ay = np.zeros((len(poly), 7))
    Az = np.zeros((len(poly), 7))

    Ax[:, 1] = np.array([-item['Z'] for item in poly])
    Ax[:, 2] = np.array([item['Y'] for item in poly])
    Ax[:, 3] = np.array([item['X'] for item in poly])
    Ax[:, 4] = np.ones(len(poly))

    Ay[:, 0] = np.array([item['Z'] for item in poly])
    Ay[:, 2] = np.array([-item['X'] for item in poly])
    Ay[:, 3] = np.array([item['Y'] for item in poly])
    Ay[:, 5] = np.ones(len(poly))

    Az[:, 0] = np.array([-item['Y'] for item in poly])
    Az[:, 1] = np.array([item['X'] for item in poly])
    Az[:, 3] = np.array([item['Z'] for item in poly])
    Az[:, 6] = np.ones(len(poly))

    A = np.row_stack((Ax, Ay, Az))

    X = np.array([np.array([float(item['X']), float(item['Y']), float(item['Z'])]) for item in poly])
    L = (np.array(etms)).transpose().flatten()

    x = np.linalg.lstsq(A, L, rcond=None)[0]

    # update coordinates by applying transformation and reshape to 3 x n
    u_poly = (np.dot(A, x) + X.transpose().flatten()).reshape(3, len(poly))

    for i, item in enumerate(poly):
        item['X'] = u_poly[0, i]
        item['Y'] = u_poly[1, i]
        item['Z'] = u_poly[2, i]

    return poly, date


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

        self.polyhedrons += rs.dictresult()
        self.ts = []
        self.etms = []
        self.residuals = []

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
            stn_ts = [item for item in self.polyhedrons if
                      item['NetworkCode'] == stn.NetworkCode and item['StationCode'] == stn.StationCode]

            qbar.set_postfix(station=str(stn))

            self.ts += [pyPPPETM.GamitSoln(cnn, stn_ts, stn.StationCode, stn.NetworkCode)]

            self.etms += [pyPPPETM.GamitETM(cnn, stn.NetworkCode, stn.StationCode, False, False, self.ts[-1])]

            if self.etms[-1].A is not None:
                self.residuals += self.etms[-1].residuals
            else:
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
        qbar.close()

    def align_stack(self, JobServer):

        updated_poly = []
        temp_updated_poly = []

        qbar = tqdm(total=len(self.epochs), desc=' >> Aligning polyhedrons', ncols=160)

        for date in self.epochs:

            qbar.set_postfix(day=str(date.yyyyddd()))

            if JobServer is not None:

                JobServer.SubmitJob(helmert_trans, (self.polyhedrons, self.residuals, date), (), (),
                                    updated_poly, AlignClass(qbar), 'finalize')

                if JobServer.process_callback:
                    JobServer.process_callback = False
            else:
                updated_poly += [helmert_trans(self.polyhedrons, self.residuals, date)[0]]
                qbar.update()

        if JobServer is not None:
            tqdm.write(' -- Waiting for alignments to finish...')
            JobServer.job_server.wait()
            tqdm.write(' -- Done.')

            for date in self.epochs:
                temp_updated_poly += [poly for poly in updated_poly if poly.date == date]

            updated_poly = temp_updated_poly

        qbar.close()

        self.polyhedrons = updated_poly
        self.calculate_etms(self.cnn)


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

    # load polyhedrons
    project = Project(cnn, args.project[0])

    # plot initial state
    tqdm.write(' -- Plotting initial ETMs (unaligned)...')

    #for etm in tqdm(project.etms, ncols=160):
    #    etm.plot(pngfile=args.project[0] + '/' + etm.NetworkCode + '.' + etm.StationCode + '_0.png')

    project.align_stack(JobServer)

    tqdm.write(' -- Plotting intermediate step ETMs (aligned)...')

    for etm in tqdm(project.etms, ncols=160):
        etm.plot(pngfile=args.project[0] + '/' + etm.NetworkCode + '.' + etm.StationCode + '_1.png')



if __name__ == '__main__':
    main()