"""
Project: Parallel.GAMIT
Date: Mar-31-2017
Author: Demian D. Gomez
"""

from pyGamitSession import GamitSession
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial import Delaunay
from Utils import smallestN_indices
import sklearn.cluster as cluster
from scipy.spatial import distance
from glob import glob
from shutil import rmtree
from tqdm import tqdm

BACKBONE_NET = 40
NET_LIMIT = 40
SUBNET_LIMIT = 35
MAX_DIST = 5000
MIN_DIST = 20


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
        self.date = date

        # start by dividing up the stations into clusters
        # get all the coordinates of valid stations for this date
        points = np.array([[stn.X, stn.Y, stn.Z] for stn in stations if date in stn.good_rinex])

        # create a list that only has the active stations for this day
        active_stations = [stn for stn in stations if date in stn.good_rinex]

        # find out if this project-day has been processed before
        db_subnets = cnn.query_float('SELECT * FROM gamit_subnets '
                                     'WHERE "Project" = \'%s\' AND "Year" = %i AND '
                                     '"DOY" = %i' % (self.name, date.year, date.doy), as_dict=True)

        if len(db_subnets) > 0:
            tqdm.write(' >> Processing for %s already exists, attempting to recover it...' % date.yyyyddd())

            # subnetworks already exist. Check that the station set is the same
            cfg_stations = [stn.NetworkCode + '.' + stn.StationCode for stn in active_stations]
            dba_stations = [s for stn in db_subnets for s in stn['stations']]
            dba_alias = [s for stn in db_subnets for s in stn['alias']]

            # get the station difference (do not consider stationed REMOVED from the CFG still present in the processing
            stn_diff = list(set(cfg_stations) - set(dba_stations))

            # apply database aliases
            self.apply_db_aliases(dba_stations, stations, dba_alias)

            # build the sub-networks using the information in the database
            clusters, backbone, ties = self.recover_subnets(db_subnets, active_stations)

            if 0 < len(stn_diff) <= len(clusters['centroids']) * 4:
                # there are some stations not originally in the processing
                # add them to the best cluster
                # the number of stations should not be such that there's more than 4 new stations per cluster
                clusters = self.add_missing_station(cnn, clusters, active_stations, stn_diff)
                self.check_stn_diff_aliases(stn_diff, cfg_stations, active_stations)

            elif len(stn_diff) > len(clusters['centroids']) * 4 or len(stations) < len(dba_stations) - 5:

                tqdm.write(' -- Too many new stations to add. Redoing the whole thing')

                # is condition not satisfied, redo eveything
                cnn.query('DELETE FROM gamit_subnets WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                          % (self.name, date.year, date.doy))
                cnn.query('DELETE FROM gamit_stats   WHERE "Project" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                          % (self.name, date.year, date.doy))

                # delete folders
                project = glob(GamitConfig.gamitopt['solutions_dir'].rstrip('/') +
                               '/%s/%s/%s*' % (date.yyyy(), date.ddd(), self.name))

                for f in project:
                    rmtree(f)

                clusters = self.make_clusters(points, active_stations)

                if len(clusters['stations']) > 1:
                    # get the ties between subnetworks
                    ties = self.tie_subnetworks(points, clusters, active_stations)

                    # build the backbone network
                    backbone = self.backbone_delauney(points, active_stations)
                else:
                    ties = []
                    backbone = []
        else:
            tqdm.write(' >> Creating network clusters for %s...' % date.yyyyddd())

            # create station clusters
            # cluster centroids will be used later to tie the networks
            clusters = self.make_clusters(points, active_stations)

            if len(clusters['stations']) > 1:
                # get the ties between subnetworks
                ties = self.tie_subnetworks(points, clusters, active_stations)

                # build the backbone network
                backbone = self.backbone_delauney(points, active_stations)
            else:
                ties = []
                backbone = []

        self.sessions = self.create_gamit_sessions(cnn, archive, clusters, backbone, ties, date)

    def check_stn_diff_aliases(self, stn_diff, cfg_stations, stations):

        # for each station in the difference vector
        for stn in stn_diff:
            # get the codes except for stn
            cfg_stncodes = [s.split('.')[1] for s in cfg_stations if s != stn]

            if stn.split('.')[1] in cfg_stncodes:
                # if stn stationcode in cfg_stations, generate alias
                stno = [s for s in stations if s.NetworkCode + '.' + s.StationCode == stn]

                if stno:
                    # if object exists, replace it's alias
                    stno[0].generate_alias()

    def apply_db_aliases(self, dba_stations, stations, dba_alias):

        # apply database list of aliases
        for i, stn in enumerate(dba_stations):
            stno = [s for s in stations if s.NetworkCode + '.' + s.StationCode == stn]
            # careful: a station in the database might not be present in the station list because a station removal
            # from the CFG does not have any effect in the processing
            if stno:
                # if object exists, replace it's alias
                stno[0].StationAlias = dba_alias[i]

    def make_clusters(self, points, stations, net_limit=NET_LIMIT):

        stn_count = points.shape[0]
        subnet_count = int(np.ceil(float(float(stn_count) / float(SUBNET_LIMIT))))

        if float(stn_count) > net_limit:
            centroids, labels, _ = cluster.k_means(points, subnet_count)

            # array for centroids
            cc = np.array([]).reshape((0, 3))

            # array for labels
            ll = np.zeros(points.shape[0])
            ll[:] = np.nan

            # index
            save_i = 0
            # list to process at the end (to merge points in subnets with < 3 items
            merge = []

            for i in range(len(centroids)):

                if len([la for la in labels if la == i]) > SUBNET_LIMIT:
                    # rerun this cluster to make it smaller
                    tpoints = points[labels == i]
                    # make a selection of the stations
                    tstations = [st for la, st in zip(labels.tolist(), stations) if la == i]
                    # run make_clusters
                    tclusters = self.make_clusters(tpoints, tstations, SUBNET_LIMIT)
                    # save the ouptput
                    tcentroids = tclusters['centroids']
                    tlabels = tclusters['labels']

                    for j in range(len(tcentroids)):
                        # don't do anything with empty centroids
                        if len(tpoints[tlabels == j]) > 0:
                            cc, ll, save_i = self.save_cluster(points, tpoints[tlabels == j], cc,
                                                               tcentroids[j], ll, save_i)

                elif 0 < len([la for la in labels if la == i]) <= 3:
                    # this subnet is made of only two elements: merge to closest subnet
                    merge.append(i)

                elif len([la for la in labels if la == i]) == 0:
                    # nothing to do if length == 0
                    pass

                else:
                    # everything is good! save the cluster
                    cc, ll, save_i = self.save_cluster(points, points[labels == i], cc, centroids[i], ll, save_i)

            # now process the subnets with < 3 stations
            for i in merge:
                # find the distance to the centroids (excluding itself, which is not in cc)
                dist = distance.cdist(points[labels == i], cc) / 1e3
                # get the closest
                min_centroid = np.argmin(dist, axis=1).tolist()
                # assign the closest cluster to the point
                for centroid, label in zip(min_centroid, np.where(labels == i)[0].tolist()):
                    ll[label] = centroid

            # final check: for each subnetwork, check that the distances between stations is at least 20 km
            # if distance less than 20 km, move the station to the closest subnetwork
            # this avoids problems during GAMIT LC run
            if len(cc) > 1:  # otherwise if doesn't make any sense to do this
                for i in range(len(cc)):
                    pp = points[ll == i]
                    # find the distance between stations
                    dist = distance.cdist(pp, pp) / 1e3
                    # remove zeros
                    dist[dist == 0] = np.inf

                    # some stations are too close to each other
                    while np.any(dist < MIN_DIST):
                        # row col of the pair of stations too close to each other
                        idx = np.unravel_index(np.argmin(dist), dist.shape)
                        # move the "row" station to closest subnetwork
                        cc_p = cc[np.arange(len(cc)) != i]  # all centroids but the centroid we are working with (i)
                        dc = distance.cdist(np.array([pp[idx[0]]]), cc_p) / 1e3

                        min_centroid = np.argmin(dc, axis=1)

                        # next line finds the centroid index in the global centroid variable cc
                        centroid_index = np.argmax((cc == cc_p[min_centroid[0]]).all(axis=1))
                        # assign the centroid_index to the label of the point in question
                        ll[np.where(ll == i)[0][idx[0]]] = centroid_index

                        # calculate again without this point
                        pp = points[ll == i]
                        dist = distance.cdist(pp, pp) / 1e3
                        # remove zeros
                        dist[dist == 0] = np.inf
        else:
            # not necessary to split the network
            cc = np.array([np.mean(points, axis=0)])
            ll = np.zeros(len(stations))

        # put everything in a dictionary
        clusters = dict()
        clusters['centroids'] = cc
        clusters['labels'] = ll
        clusters['stations'] = []

        for l in range(len(clusters['centroids'])):
            clusters['stations'].append([s for i, s in zip(ll.tolist(), stations) if i == l])

        return clusters

    @staticmethod
    def save_cluster(all_points, c_points, cc, centroid, ll, save_i):

        cc = np.vstack((cc, centroid))
        for p in c_points:
            # find in all_points the location where all elements in axis 1 match p (the passed centroid)
            ll[(all_points == p).all(axis=1)] = save_i
        save_i += 1

        return cc, ll, save_i

    @staticmethod
    def tie_subnetworks(points, clusters, stations):

        # get centroids and lables
        centroids = clusters['centroids']
        labels = clusters['labels']

        # calculate distance between centroids
        dist = distance.cdist(centroids, centroids) / 1e3

        # variable to keep track of the number of ties for each subnetwork
        ties = np.zeros((centroids.shape[0], centroids.shape[0]))

        # make distance to self centroid infinite
        dist[dist == 0] = np.inf

        ties_vector = [[] for _ in range(len(centroids))]

        for c in range(len(centroids)):
            # get the closest three centroids to find the closest subnetworks
            neighbors = np.argsort(dist[:, c])

            # check that there are less than 3 ties
            if sum(ties[c, :]) < 3:
                # for each neighbor
                for n in neighbors:

                    # only enter if not already tied AND ties of n < 3, unless ties c < 2 AND n != c
                    if ties[n, c] == 0 and (np.sum(ties[n, :]) < 3 or np.sum(ties[c, :]) < 2) and n != c:
                        # to link to this neighbor, it has to have less then 3 ties. Otherwise continue to next
                        # print 'working on net ' + str(c) + ' - ' + str(n)

                        # get all stations from current subnet and dist to each station of neighbor n
                        sd = distance.cdist(points[labels == c], points[labels == n]) / 1e3

                        # find the 4 closest stations
                        tie_c = []
                        tie_n = []
                        for i in range(len(sd)):
                            s = smallestN_indices(sd, len(sd))[i]
                            # ONLY ALLOW TIES BETWEEN MIN_DIST AND MAX_DIST. Also, tie stations should be > MIN_DIST
                            # from stations on the other subnetwork
                            if MIN_DIST <= sd[s[0], s[1]] <= MAX_DIST and np.all(sd[s[0], :] > MIN_DIST) \
                                    and np.all(sd[:, s[1]] > MIN_DIST):

                                # print ' pair: ' + str([st for la, st in zip(labels.tolist(), stations)
                                # if la == n][s[1]])\
                                #       + ' - ' + str([st for la, st in zip(labels.tolist(),
                                #       stations) if la == c][s[0]]) + ' ( %.1f' % sd[s[0], s[1]] + ' km)'

                                # station objects:
                                # find the stations that have labels == (c, n) and from that subset, find the row (c)
                                # and col (n) obtained by smallestN_indices
                                tie_c += [[st for la, st in zip(labels.tolist(), stations) if la == n][s[1]]]
                                tie_n += [[st for la, st in zip(labels.tolist(), stations) if la == c][s[0]]]

                                # make these distances infinite to avoid selecting again
                                sd[s[0], :] = np.inf
                                sd[:, s[1]] = np.inf

                                if len(tie_c) == 4:
                                    break

                        # if successfully added 3 or more tie stations, then declared it tied
                        if len(tie_c) >= 3:
                            # add a tie to c and n subnets
                            ties[n, c] += 1
                            ties[c, n] += 1
                            ties_vector[c] += tie_c
                            ties_vector[n] += tie_n
                            # print ties
                        else:
                            # print ' no suitable ties found between these two networks'
                            pass

                    if sum(ties[c, :]) >= 3:
                        # if current subnet already has 3 ties, continue to next one
                        break

        # return the vector with the station objects representing the ties
        return ties_vector

    @staticmethod
    def backbone_delauney(points, stations):

        dt = Delaunay(points)

        # start distance to remove stations
        max_dist = 5

        # create a mask with all the stations
        mask = np.ones(points.shape[0], dtype=np.bool)

        while len(points[mask]) > BACKBONE_NET:
            # make a copy of the mask
            n_mask = mask.copy()

            while True:
                # create variable to check if should iterate
                iterate = False

                # loop through each simplex
                for v in dt.simplices:
                    # get the distance of each edge
                    d = distance.cdist(points[mask][v], points[mask][v]) / 1e3
                    # make the zeros infinite
                    d[d == 0] = np.inf
                    # if any pair is closer than max_dist, remove point
                    if np.any(d <= max_dist):
                        rp = v[np.where((d <= max_dist))[0]][0]

                        n_mask[np.where(mask)[0][rp]] = False
                        # if mask was updated, then iterate
                        iterate = True

                        if len(points[n_mask]) <= BACKBONE_NET:
                            break

                mask = n_mask.copy()
                dt = Delaunay(points[mask])

                if not iterate or len(points[mask]) <= BACKBONE_NET:
                    break

            # make the distance double from the last run
            max_dist = max_dist * 2

        backbone = [s for i, s in enumerate(stations) if mask[i]]

        return backbone

    @staticmethod
    def determine_core_network(stations, date):
        """
        Deprecated function to create the core network
        :param stations: list of station objects
        :param date: date to be processed
        :return: a list of stations that make up the core network or empty is no need to split the processing
        """
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

    @staticmethod
    def recover_subnets(db_subnets, stations):
        # this method does not update the labels because they are not used
        # labels are only used to tie station
        clusters = dict()
        # init the centroids array
        clusters['centroids'] = []
        clusters['labels'] = []
        clusters['stations'] = []

        backbone = []
        ties = []

        # check if there is more than one sub-network
        if len(db_subnets) == 1:
            # single network reported as sub-network zero
            # no backbone and no ties, single network processing
            clusters['centroids'] = np.array([db_subnets[0]['centroid']])
            clusters['labels'] = np.zeros(len(stations))
            clusters['stations'].append(stations)
        else:
            # multiple sub-networks: 0 contains the backbone; 1 contains cluster 1; 2 contains...
            for subnet in db_subnets[1:]:
                clusters['centroids'].append(subnet['centroid'])
                # labels start at zero, but zero subnet is backbone
                # clusters['labels'] += np.ones(len(subnet['stations'])) * (subnet['subnet'] - 1)
                clusters['stations'].append([s for s in stations
                                             if s.NetworkCode + '.' + s.StationCode in subnet['stations']])
                # add the corresponding ties
                ties.append([s for s in stations if s.NetworkCode + '.' + s.StationCode in subnet['ties']])

            clusters['centroids'] = np.array(clusters['centroids'])

            # now recover the backbone
            backbone = [s for s in stations if s.NetworkCode + '.' + s.StationCode in db_subnets[0]['stations']]

        return clusters, backbone, ties

    def add_missing_station(self, cnn, clusters, stations, stn_diff):

        # this method does not update the labels because they are not used
        # labels are only used to tie station

        # find the station objects for the elements listed in stn_diff
        stnobj_diff = [s for s in stations if s.NetworkCode + '.' + s.StationCode in stn_diff]

        tqdm.write(' -- Adding missing stations %s' % ' '.join(stn_diff))

        if len(clusters['centroids']) == 1:
            # single station network, just add the missing station
            clusters['stations'][0] += stnobj_diff
            clusters['labels'] = np.zeros(len(clusters['stations'][0]))

            # because a station was added, delete the gamit_stats record to force reprocessing
            cnn.delete('gamit_stats', Project=self.name, Year=self.date.year, DOY=self.date.doy, subnet=0)
            cnn.delete('gamit_subnets', Project=self.name, Year=self.date.year, DOY=self.date.doy, subnet=0)
        else:
            for stn in stnobj_diff:
                # find the closest centroid to this station
                xyz = np.zeros((1, 3))
                xyz[0] = np.array([stn.X, stn.Y, stn.Z])

                sd = distance.cdist(xyz, clusters['centroids']) / 1e3

                for i in range(len(clusters['centroids'])):
                    s = smallestN_indices(sd, len(clusters['centroids']))[i]

                    if sd[s[0], s[1]] <= MAX_DIST:
                        # can add the station to this sub-network
                        clusters['stations'][i].append(stn)
                        # because a station was added, delete the gamit_stats and subnets record to force reprocessing
                        cnn.delete('gamit_stats', Project=self.name, Year=self.date.year, DOY=self.date.doy,
                                   subnet=i + 1)
                        cnn.delete('gamit_subnets', Project=self.name, Year=self.date.year, DOY=self.date.doy,
                                   subnet=i + 1)
        return clusters

    def create_gamit_sessions(self, cnn, archive, clusters, backbone, ties, date):

        sessions = []

        if len(backbone):
            # a backbone network was created: at least two or more clusters
            # backbone if always network 00
            sessions.append(GamitSession(cnn, archive, self.name, self.org, 0, date, self.GamitConfig, backbone))

            for c in range(len(clusters['centroids'])):
                # create a session for each cluster
                sessions.append(GamitSession(cnn, archive, self.name, self.org, c + 1, date, self.GamitConfig,
                                             clusters['stations'][c], ties[c], clusters['centroids'][c].tolist()))

        else:
            sessions.append(GamitSession(cnn, archive, self.name, self.org, None, date, self.GamitConfig,
                                         clusters['stations'][0]))

        return sessions
