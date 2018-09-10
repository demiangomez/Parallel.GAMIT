"""
Project: Parallel.GAMIT
Date: Mar-31-2017
Author: Demian D. Gomez
"""

from pyGamitSession import GamitSession
from tqdm import tqdm
import numpy as np
import glob
import re
from scipy.spatial import ConvexHull

NET_LIMIT = 40
MIN_CORE_NET = 10


class NetworkException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Network(object):

    def __init__(self, cnn, archive, GamitConfig, stations, date):

        self.name = GamitConfig.NetworkConfig.network_id.lower()
        self.org = GamitConfig.gamitopt['org']
        self.GamitConfig = GamitConfig

        if GamitConfig.NetworkConfig.type == 'regional':
            # determine the core network by getting a convex hull and centroid
            core_network = self.determine_core_network(stations, date)
        else:
            raise ValueError('Global network logic not implemented!')

        self.sessions = self.create_gamit_sessions(cnn, archive, core_network, stations, date)

        return

    @staticmethod
    def determine_core_network(stations, date):

        if len(stations) > NET_LIMIT:
            # this session will require be split into more than one subnet

            points = np.array([[stn.record.lat, stn.record.lon] for stn in stations if date in stn.good_rinex])

            stn_candidates = [stn for stn in stations if date in stn.good_rinex]

            # create a convex hull
            hull = ConvexHull(points)

            # build a list of the stations in the convex hull
            core_network = [stn_candidates[vertex] for vertex in hull.vertices]

            # create a mask so that the centroid is not a point in the hull
            mask = np.ones(points.shape[0], dtype=bool)
            mask[hull.vertices] = False

            if np.any(mask):
                # also add the centroid of the figure
                mean_ll = np.mean(points, axis=0)

                # find the closest stations to the centroid
                centroid = int(np.argmin(np.sum(np.abs(points[mask]-mean_ll), axis=1)))

                core_network += [stn_candidates[centroid]]

            return core_network

        else:

            return []

    def create_gamit_sessions(self, cnn, archive, core_network, stations, date):
        """
        analyzes the core NetClass and secondary NetClass for the processing day and makes sure that:
        1) the total station count is <= NET_LIMIT. If it's > NET_LIMIT, splits the stations into two or more
           sub networks both containing the Core stations.
        2) If the stations were split into sub networks, then it verifies that there are at least 10 Core stations for
           that day. If there aren't, it promotes stations from the Secondary as Core

        :return: list
        """

        secondary = [stn for stn in stations if date in stn.good_rinex and stn not in core_network]

        partition, ready = self.recover_subnets(core_network, stations, date)

        if len(core_network) > 0:
            # it was determined that this network requires partitioning
            # if the partition list is empty, it's because recover_subnets failed to read the monitor files
            if not partition:
                stn_count = len(secondary + core_network)
                subnet_count = int(np.ceil(float(float(stn_count) / float(NET_LIMIT))))

                partition = self.partition(secondary, subnet_count)

                for p in partition:
                    p += core_network
                    ready += [False]

            sessions = [GamitSession(cnn, archive, '%s.%s%02i' % (self.name, self.org, i), date,
                                     self.GamitConfig, part[0], core_network, part[1])
                        for i, part in enumerate(zip(partition, ready))]
        else:
            if not partition:
                partition = [secondary]
                ready = [False]

            # all stations fit in a single run
            sessions = [GamitSession(cnn, archive, self.name, date, self.GamitConfig,
                                     partition[0], core_network, ready[0])]

        return sessions

    def recover_subnets(self, core_network, stations, date):

        opt = self.GamitConfig.gamitopt

        partition = []
        ready = []

        pattern = re.compile('.*-> fetching rinex for (\w+.\w+)\s(\w+)')

        if len(core_network) > 0:
            # multiple networks per day
            # get the folder names
            pwds = glob.glob(opt['solutions_dir'].rstrip('/') + '/%s/%s/%s.*' % (date.yyyy(), date.ddd(), self.name))

        else:
            pwds = glob.glob(opt['solutions_dir'].rstrip('/') + '/%s/%s/%s' % (date.yyyy(), date.ddd(), self.name))

        for pwd in pwds:

            stn_list = []

            with open(pwd + '/monitor.log', 'r') as monitor:
                for line in monitor:
                    stn = pattern.findall(line)

                    if stn:
                        # get the station
                        sta = None
                        for s in stations:
                            if s.NetworkCode + '.' + s.StationCode == stn[0][0]:
                                sta = s
                                break

                        # if station was found:
                        if sta:
                            stn_list.append(sta)

                            # check that the alias of the station is the same, if not, change it!
                            if sta.StationAlias != stn[0][1]:
                                sta.StationAlias = stn[0][1]
                        else:
                            tqdm.write(' -- WARNING: Station %s could not be found in existing processing folder (%s). '
                                       'Check you are using the same station set' % (stn[0][1], pwd))

                    if '-> executing GAMIT' in line:
                        # it reached to execute GAMIT, use the net config
                        partition.append(stn_list)
                        break

            # if the glx file is present, then the all the processes should be ready
            if glob.glob(pwd + '/glbf/*.glx*'):
                ready += [True]
            else:
                ready += [False]

        return partition, ready

    @staticmethod
    def partition(lst, n):
        division = len(lst) / float(n)
        return [lst[int(round(division * i)): int(round(division * (i + 1)))] for i in xrange(n)]
