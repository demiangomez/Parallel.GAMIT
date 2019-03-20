
import numpy as np
import dbConnection
from pyDate import Date
from tqdm import tqdm
from pyDRA import adjust_lsq
import pyETM


class Stack(list):

    def __init__(self, cnn, project, redo=False):

        super(Stack, self).__init__()

        self.project = project
        self.cnn = cnn

        if redo:
            # if redoing the stack, ignore the contents of the stacks table
            print ' >> Redoing stack'
            print ' >> Loading GAMIT solutions for project %s...' % project

            gamit_vertices = self.cnn.query_float(
                'SELECT "NetworkCode" || \'.\' || "StationCode", "X", "Y", "Z", "Year", "DOY", "FYear" '
                'FROM gamit_soln WHERE "Project" = \'%s\' '
                'ORDER BY "NetworkCode", "StationCode"' % project)

            self.gamit_vertices = np.array(gamit_vertices, dtype=[('stn', 'S8'), ('x', 'float64'), ('y', 'float64'),
                                                                  ('z', 'float64'), ('yr', 'i4'), ('dd', 'i4'),
                                                                  ('fy', 'float64')])

            dates = self.cnn.query_float('SELECT "Year", "DOY" FROM gamit_soln WHERE "Project" = \'%s\' '
                                         'GROUP BY "Year", "DOY" ORDER BY "Year", "DOY"' % project)

            self.dates = [Date(year=int(d[0]), doy=int(d[1])) for d in dates]

            self.stations = self.cnn.query_float('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                                                 'WHERE "Project" = \'%s\' '
                                                 'GROUP BY "NetworkCode", "StationCode" '
                                                 'ORDER BY "NetworkCode", "StationCode"' % project, as_dict=True)

            for d in tqdm(self.dates, ncols=160, desc=' >> Initializing the stack polyhedrons'):
                self.append(Polyhedron(self.gamit_vertices, project, d))

        else:
            print ' >> Preserving the existing stack'
            print ' >> Determining differences between current stack and GAMIT solutions for project %s...' % project

            # load the vertices that don't have differences wrt to the GAMIT solution
            stack_vertices = self.cnn.query_float(
                'SELECT "NetworkCode" || \'.\' || "StationCode", "X", "Y", "Z", "Year", "DOY", "FYear" FROM stacks '
                'WHERE ("Year", "DOY") NOT IN ('
                ' SELECT "Year", "DOY" FROM ('
                ' SELECT "NetworkCode", "StationCode", "Year", "DOY", \'not in stack\' '
                '  AS note FROM gamit_soln WHERE "Project" = \'%s\' EXCEPT '
                ' SELECT "NetworkCode", "StationCode", "Year", "DOY", \'not in stack\' '
                '  AS note FROM stacks WHERE "Project" = \'%s\''
                ' ) AS missing_stack GROUP BY "Year", "DOY" ORDER BY "Year", "DOY") AND '
                '"Project" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (project, project, project))

            print ' >> Loading pre-existing stack for project %s' % project

            # load the vertices that were different
            gamit_vertices = self.cnn.query_float(
                'SELECT "NetworkCode" || \'.\' || "StationCode", "X", "Y", "Z", "Year", "DOY", "FYear" FROM gamit_soln '
                'WHERE ("Year", "DOY") IN ('
                ' SELECT "Year", "DOY" FROM ('
                ' SELECT "NetworkCode", "StationCode", "Year", "DOY", \'not in stack\' '
                '  AS note FROM gamit_soln WHERE "Project" = \'%s\' EXCEPT '
                ' SELECT "NetworkCode", "StationCode", "Year", "DOY", \'not in stack\' '
                '  AS note FROM stacks WHERE "Project" = \'%s\''
                ' ) AS missing_stack GROUP BY "Year", "DOY" ORDER BY "Year", "DOY") AND '
                '"Project" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (project, project, project))

            self.stack_vertices = np.array(stack_vertices, dtype=[('stn', 'S8'), ('x', 'float64'), ('y', 'float64'),
                                                                  ('z', 'float64'), ('yr', 'i4'), ('dd', 'i4'),
                                                                  ('fy', 'float64')])

            self.gamit_vertices = np.array(gamit_vertices, dtype=[('stn', 'S8'), ('x', 'float64'), ('y', 'float64'),
                                                                  ('z', 'float64'), ('yr', 'i4'), ('dd', 'i4'),
                                                                  ('fy', 'float64')])

            dates = self.cnn.query_float('SELECT "Year", "DOY" FROM stacks WHERE "Project" = \'%s\' UNION '
                                         'SELECT "Year", "DOY" FROM gamit_soln WHERE "Project" = \'%s\' '
                                         'ORDER BY "Year", "DOY"' % (project, project))

            self.dates = [Date(year=d[0], doy=d[1]) for d in dates]

            self.stations = self.cnn.query_float('SELECT "NetworkCode", "StationCode" FROM gamit_soln '
                                                 'WHERE "Project" = \'%s\' UNION '
                                                 'SELECT "NetworkCode", "StationCode" FROM stacks '
                                                 'WHERE "Project" = \'%s\' UNION '
                                                 'ORDER BY "NetworkCode", "StationCode"'
                                                 % (project, project), as_dict=True)

            for d in tqdm(self.dates, ncols=160, desc=' >> Initializing the stack polyhedrons'):
                try:
                    self.append(Polyhedron(self.stack_vertices, project, d, aligned=True))

                except ValueError:
                    self.append(Polyhedron(self.gamit_vertices, project, d, aligned=False))

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

    def calculate_etms(self):
        """
        Estimates the trajectory models for all stations in the stack
        :return:
        """
        print ' >> Calculating ETMs for %s...' % self.project

        for s in tqdm(self.stations, ncols=160, desc=self.project):

            ts = self.get_station(s['NetworkCode'], s['StationCode'])
            try:
                tqdm.postfix = s['NetworkCode'] + '.' + s['StationCode']

                ts = pyETM.GamitSoln(self.cnn, ts, s['NetworkCode'], s['StationCode'])

            except pyETM.pyETMException as e:
                tqdm.write(' -- ' + str(e))


class Polyhedron(object):
    def __init__(self, vertices, project, date, rot=True, scale=False, aligned=False):

        self.project = project
        self.date = date
        self.aligned = aligned
        self.helmert = None
        self.wrms = None
        self.stations_used = None
        self.iterations = None
        # initialize the vertices of the polyhedron
        # self.vertices = [v for v in vertices if v[5] == date.year and v[6] == date.doy]

        self.vertices = vertices[np.logical_and(vertices['yr'] == date.year, vertices['dd'] == date.doy)]

        if not self.vertices.size:
            raise ValueError('No polyhedron data found for ' + str(date))

        self.rows = self.vertices.shape[0]

        # create the design matrix for this day
        rx = np.array([np.zeros(self.rows), -self.vertices['z'], self.vertices['y']]).transpose() * 1e-9
        ry = np.array([self.vertices['z'], np.zeros(self.rows), -self.vertices['x']]).transpose() * 1e-9
        rz = np.array([-self.vertices['y'], self.vertices['x'], np.zeros(self.rows)]).transpose() * 1e-9

        tx = np.array([np.ones(self.rows), np.zeros(self.rows), np.zeros(self.rows)]).transpose()
        ty = np.array([np.zeros(self.rows), np.ones(self.rows), np.zeros(self.rows)]).transpose()
        tz = np.array([np.zeros(self.rows), np.zeros(self.rows), np.ones(self.rows)]).transpose()

        if rot:
            self.Ax = np.concatenate((rx, tx), axis=1)
            self.Ay = np.concatenate((ry, ty), axis=1)
            self.Az = np.concatenate((rz, tz), axis=1)
        else:
            self.Ax = tx
            self.Ay = ty
            self.Az = tz

        if scale:
            self.Ax = np.concatenate((self.Ax, self.vertices['x'][np.newaxis].transpose() * 1e-9), axis=1)
            self.Ay = np.concatenate((self.Ay, self.vertices['y'][np.newaxis].transpose() * 1e-9), axis=1)
            self.Az = np.concatenate((self.Az, self.vertices['z'][np.newaxis].transpose() * 1e-9), axis=1)

    def align(self, target, set_aligned=True):
        """
        Align to another polyhedron object using a Helmert transformation defined
        during the initialization of the object
        :param target: polyhedron object
        :param set_aligned: determine whether the polyhedron should be marked as aligned or not after performing the
        Helmert transformation
        :return: aligned polyhedron and residuals
        """

        # figure out common stations
        intersect = np.intersect1d(target.vertices['stn'], self.vertices['stn'])

        # target filter
        ft = np.isin(target.vertices['stn'], intersect)
        # local filter
        fl = np.isin(self.vertices['stn'], intersect)
        # get vertices
        st = target.vertices[ft]
        sl = self.vertices[fl]

        # obtain residuals
        rx = st['x'] - sl['x']
        ry = st['y'] - sl['y']
        rz = st['z'] - sl['z']

        # get the design matrix portion
        Ax = self.Ax[fl]
        Ay = self.Ay[fl]
        Az = self.Az[fl]

        A = np.concatenate((Ax, Ay, Az), axis=0)
        r = np.concatenate((rx, ry, rz), axis=0)

        # invert
        c, _, index, v, wrms, P, it = adjust_lsq(A, r)

        # apply result to everyone
        x = np.dot(np.concatenate((self.Ax, self.Ay, self.Az), axis=0), c).reshape((3, self.rows)).transpose()

        self.vertices['x'] += x[:, 0]
        self.vertices['y'] += x[:, 1]
        self.vertices['z'] += x[:, 2]

        self.aligned = set_aligned
        self.helmert = c
        self.wrms = wrms
        self.stations_used = len(intersect)
        self.iterations = it


def main():

    cnn = dbConnection.Cnn("gnss_data.cfg")

    stack = Stack(cnn, 'igs-sirgas', redo=True)

    stack.calculate_etms()

    for i in tqdm(range(1, len(stack)), ncols=160):
        stack[i].align(stack[i - 1])

    net = 'igs'
    stn = 'braz'

    ts = stack.get_station(net, stn)

    dts = np.append(np.diff(ts[:, 0:3], axis=0), ts[1:, -3:], axis=1)

    ts = pyETM.GamitSoln(cnn, dts, net, stn)

    pyETM.GamitETM(cnn, net, stn, True, gamit_soln=ts)


if __name__ == '__main__':

    main()
