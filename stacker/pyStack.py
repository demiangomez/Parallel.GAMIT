
import numpy as np
import dbConnection
from pyDate import Date
from tqdm import tqdm
from pyDRA import adjust_lsq
from Utils import lg2ct
from pyETM import pi
import pyETM


class Stack(list):

    def __init__(self, cnn, project, redo=False):

        super(Stack, self).__init__()

        self.project = project
        self.cnn = cnn

        if redo:
            # if redoing the stack, ignore the contents of the stacks table
            print ' >> Redoing stack'

            self.cnn.query('DELETE FROM stacks WHERE "Project" = \'%s\'' % self.project)

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
                                                 'WHERE "Project" = \'%s\' '
                                                 'ORDER BY "NetworkCode", "StationCode"'
                                                 % (project, project), as_dict=True)

            for d in tqdm(self.dates, ncols=160, desc=' >> Initializing the stack polyhedrons'):
                try:
                    # try to append the stack vertices
                    self.append(Polyhedron(self.stack_vertices, project, d, aligned=True))

                except ValueError:
                    # if value error is risen, then append the gamit vertices
                    tqdm.write(' -- Appending %s from GAMIT solutions' % d.yyyyddd())
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

                ts = pyETM.GamitSoln(self.cnn, ts, s['NetworkCode'], s['StationCode'], self.project)

            except pyETM.pyETMException as e:
                tqdm.write(' -- ' + str(e))

    def remove_common_modes(self, target_periods=None, use_stations=None):

        if target_periods is None:
            tqdm.write(' >> Removing periodic common modes...')

            # load all the periodic terms
            etm_objects = self.cnn.query_float('SELECT etmsv2."NetworkCode", etmsv2."StationCode", stations.lat, '
                                               'stations.lon, '
                                               'frequencies as freq, params FROM etmsv2 '
                                               'LEFT JOIN stations ON '
                                               'etmsv2."NetworkCode" = stations."NetworkCode" AND '
                                               'etmsv2."StationCode" = stations."StationCode" '
                                               'WHERE "object" = \'periodic\' AND soln = \'gamit\' '
                                               'AND frequencies <> \'{}\' '
                                               'ORDER BY etmsv2."NetworkCode", etmsv2."StationCode"', as_dict=True)
        else:
            tqdm.write(' >> Inheriting periodic components...')

            # load the periodic terms of the stations that will produce the inheritance
            etm_objects = self.cnn.query_float('SELECT etmsv2."NetworkCode", etmsv2."StationCode", stations.lat, '
                                               'stations.lon, '
                                               'frequencies as freq, params FROM etmsv2 '
                                               'LEFT JOIN stations ON '
                                               'etmsv2."NetworkCode" = stations."NetworkCode" AND '
                                               'etmsv2."StationCode" = stations."StationCode" '
                                               'WHERE "object" = \'periodic\' AND soln = \'gamit\' '
                                               'AND frequencies <> \'{}\' AND etmsv2."NetworkCode" || \'.\' || '
                                               'etmsv2."StationCode" IN (\'%s\') '
                                               'ORDER BY etmsv2."NetworkCode", etmsv2."StationCode"'
                                               % '\', \''.join(use_stations), as_dict=True)

        # load the frequencies to subtract
        frequencies = self.cnn.query_float('SELECT frequencies FROM etmsv2 WHERE soln = \'gamit\' AND '
                                           'object = \'periodic\' '
                                           'AND frequencies <> \'{}\' GROUP BY frequencies', as_dict=True)

        # get the unique list of frequencies
        f_vector = []

        for freq in frequencies:
            f_vector += [f for f in freq['frequencies']]

        f_vector = np.array(list(set(f_vector)))

        # initialize the vectors
        ox = np.zeros((len(f_vector), len(etm_objects), 2))
        oy = np.zeros((len(f_vector), len(etm_objects), 2))
        oz = np.zeros((len(f_vector), len(etm_objects), 2))

        for s, p in enumerate(etm_objects):

            tqdm.write(' -- Periodic parameters for %s.%s' % (p['NetworkCode'], p['StationCode']))

            if target_periods:
                n = []
                e = []
                u = []
                # inheritance invoked! we want to remove the difference between current periodic terms and target
                # terms from the parent frame
                for i in (0, 1):
                    # i is a var to select the sin and cos terms from the target_periods structure
                    for f in p['freq']:
                        t = target_periods[p['StationCode']]['%.3f' % (1 / f)]
                        n.append(t['n'][i])
                        e.append(t['e'][i])
                        u.append(t['u'][i])

                params = np.array(p['params']) - np.array([n, e, u]).flatten()
            else:
                # no inheritance: make a vector of current periodic terms to be removed as common modes
                params = np.array(p['params'])

            params = params.reshape((3, params.shape[0] / 3))
            param_count = params.shape[1] / 2

            # convert from NEU to XYZ
            for j in range(params.shape[1]):
                params[:, j] = np.array(lg2ct(params[0, j], params[1, j], params[2, j],
                                              p['lat'], p['lon'])).flatten()

            for i, f in enumerate(p['freq']):
                ox[f_vector == f, s] = params[0, i:i + param_count + 1:param_count]
                oy[f_vector == f, s] = params[1, i:i + param_count + 1:param_count]
                oz[f_vector == f, s] = params[2, i:i + param_count + 1:param_count]

        # build the design matrix using the stations involved in inheritance or all stations if no inheritance
        sql_where = ','.join(["'" + stn['NetworkCode'] + '.' + stn['StationCode'] + "'" for stn in etm_objects])

        x = self.cnn.query_float('SELECT 0, -auto_z*1e-9, auto_y*1e-9, 1, 0, 0 FROM stations WHERE '
                                 '"NetworkCode" || \'.\' || "StationCode" '
                                 'IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)

        y = self.cnn.query_float('SELECT auto_z*1e-9, 0, -auto_x*1e-9, 0, 1, 0 FROM stations WHERE '
                                 '"NetworkCode" || \'.\' || "StationCode" '
                                 'IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)

        z = self.cnn.query_float('SELECT -auto_y*1e-9, auto_x*1e-9, 0, 0, 0, 1 FROM stations WHERE '
                                 '"NetworkCode" || \'.\' || "StationCode" '
                                 'IN (%s) ORDER BY "NetworkCode", "StationCode"' % sql_where)
        Ax = np.array(x)
        Ay = np.array(y)
        Az = np.array(z)

        A = np.row_stack((Ax, Ay, Az))

        # loop through the frequencies
        for freq in f_vector:
            for i, cs in enumerate((np.sin, np.cos)):
                L = np.row_stack((ox[f_vector == freq, :, i].flatten(),
                                  oy[f_vector == freq, :, i].flatten(),
                                  oz[f_vector == freq, :, i].flatten())).flatten()

                c = np.linalg.lstsq(A, L, rcond=-1)[0]

                # loop through all the polyhedrons
                for poly in tqdm(self, ncols=160, desc=' -- Applying transformation -> %s(2 * pi * 1/%.2f)' %
                                                       (cs.__name__, np.divide(1., freq))):

                    # subtract the inverted common modes
                    poly.vertices['x'] = poly.vertices['x'] - cs(2 * pi * freq * 365.25 * poly.date.fyear) * \
                                         np.dot(poly.Ax, c)
                    poly.vertices['y'] = poly.vertices['y'] - cs(2 * pi * freq * 365.25 * poly.date.fyear) * \
                                         np.dot(poly.Ay, c)
                    poly.vertices['z'] = poly.vertices['z'] - cs(2 * pi * freq * 365.25 * poly.date.fyear) * \
                                         np.dot(poly.Az, c)

        tqdm.write(' -- Done!')

    def save(self):
        """
        save the polyhedrons to the database
        :return: nothing
        """
        for poly in tqdm(self, ncols=160, desc='Saving ' + self.project):
            for vert in poly.vertices:
                self.cnn.insert('stacks', {'Project': self.project,
                                           'NetworkCode': vert['stn'].split('.')[0],
                                           'StationCode': vert['stn'].split('.')[1],
                                           'X': vert['x'],
                                           'Y': vert['y'],
                                           'Z': vert['z'],
                                           'FYear': vert['fy'],
                                           'Year': vert['yr'],
                                           'DOY': vert['dd'],
                                           'sigmax': 0.000,
                                           'sigmay': 0.000,
                                           'sigmaz': 0.000})


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
        # sort using network code station code to make sure that intersect (in align) will get the data in the correct
        # order, otherwise the differences in X Y Z don't make sense...
        self.vertices.sort(order='stn')

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

    ts = pyETM.GamitSoln(cnn, dts, net, stn, 'igs-sirgas')

    pyETM.GamitETM(cnn, net, stn, True, gamit_soln=ts)


if __name__ == '__main__':

    main()
