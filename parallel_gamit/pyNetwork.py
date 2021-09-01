"""
Project: Parallel.GAMIT
Date: Mar-31-2017
Author: Demian D. Gomez
"""

from datetime import datetime
import time

# deps
from tqdm import tqdm
import numpy as np
from sklearn.cluster import k_means
from scipy.spatial import (ConvexHull,
                           Delaunay,
                           distance)

# app
from pyGamitSession import GamitSession
from Utils import smallestN_indices


BACKBONE_NET = 40
NET_LIMIT    = 40
SUBNET_LIMIT = 35
MAX_DIST     = 5000
MIN_DIST     = 20


def tic():
    global tt
    tt = time.time()


def toc(text):
    global tt
    tqdm.write(text + ': ' + str(time.time() - tt))


class NetworkException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Network(object):

    def __init__(self, cnn, archive, GamitConfig, stations, date, check_stations=None, ignore_missing=False):

        self.name        = GamitConfig.NetworkConfig.network_id.lower()
        self.org         = GamitConfig.gamitopt['org']
        self.GamitConfig = GamitConfig
        self.date        = date

        # find out if this project-day has been processed before
        db_subnets = cnn.query_float('SELECT * FROM gamit_subnets '
                                     'WHERE "Project" = \'%s\' AND "Year" = %i AND '
                                     '"DOY" = %i ORDER BY "subnet"' % (self.name, date.year, date.doy), as_dict=True)

        stn_active = stations.get_active_stations(date)
        chk_active = check_stations.get_active_stations(date)

        if len(db_subnets) > 0:
            tqdm.write(' >> %s %s %s -> Processing already exists' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                                      self.name, date.yyyyddd()))

            # sub-network already exist, put information in lists
            dba_stn   = [stn   for net in db_subnets for stn   in net['stations']]
            dba_alias = [alias for net in db_subnets for alias in net['alias']]

            # make the necessary changes to the stations aliases (so they match those in the database)
            stations.replace_alias(dba_stn, dba_alias)

            # build the sub-networks using the information in the database
            clusters, backbone, ties = self.recover_subnets(db_subnets, stn_active)

            if check_stations:
                for stn in chk_active:
                    if stn.netstn not in dba_stn:
                        # add station to StationCollection to make sure there's no name collisions
                        stations.append(stn)
                        # determine the closest sub-network (cluster) to this station and add it
                        clusters = self.add_missing_station(cnn, clusters, stn)

            # find if there are any incomplete sub-networks or stations without solution
            for subnet in db_subnets:
                stat = cnn.query_float('SELECT * FROM gamit_stats WHERE "Project" = \'%s\' AND "Year" = %i AND '
                                       '"DOY" = %i AND "subnet" = %i'
                                       % (self.name, date.year, date.doy, subnet['subnet']), as_dict=True)

                if not len(stat):
                    # sub-network didn't finish properly, GamitSession will detect this condition and flag session for
                    # reprocessing. Generate message alerting the user
                    tqdm.write(' -- Sub-network %s%02i did not finish successfully and will be reprocessed'
                               % (self.org, subnet['subnet']))
                else:
                    # loop through the stations in this sub-network and find it in the StationsCollection
                    # if exists and there is no gamit_soln, trigger reprocessing
                    for stn in subnet['stations']:
                        # logic here is that, if the station in the database is still in the list to be processed and
                        # ignore_missing is turned off OR station is part of the check stations, then verify
                        # the solution is in the database. Otherwise, skip the station
                        if stn in stn_active and \
                           (not ignore_missing or stn in chk_active) and \
                           not stations[stn].check_gamit_soln(cnn, self.name, date):
                            # stations is in the database but there was no solution for this day, rerun

                            for table in ('gamit_stats', 'gamit_subnets'):
                                cnn.delete(table, Project=self.name, Year=self.date.year, DOY=self.date.doy,
                                           subnet=subnet['subnet'])

                            tqdm.write(' -- %s in sub-network %s%02i did not produce a solution and will be '
                                       'reprocessed' % (stn, self.org, subnet['subnet']))

        else:
            tqdm.write(' >> %s %s %s -> Creating network clusters' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                                      self.name, date.yyyyddd()))

            # create station clusters
            # cluster centroids will be used later to tie the networks
            clusters = self.make_clusters(stations.get_active_coordinates(date), stn_active)

            if len(clusters['stations']) > 1:
                # get the ties between subnetworks
                ties = self.tie_subnetworks(stations.get_active_coordinates(date), clusters, stn_active)

                # build the backbone network
                backbone = self.backbone_delauney(stations.get_active_coordinates(date), stn_active)
            else:
                ties = []
                backbone = []

        self.sessions = self.create_gamit_sessions(cnn, archive, clusters, backbone, ties, date)

    def make_clusters(self, points, stations, net_limit=NET_LIMIT):

        stn_count = points.shape[0]
        subnet_count = int(np.ceil(float(float(stn_count) / float(SUBNET_LIMIT))))

        if float(stn_count) > net_limit:
            centroids, labels, _ = k_means(points, subnet_count)

            # array for centroids
            cc = np.array([]).reshape((0, 3))

            # array for labels
            ll    = np.zeros(points.shape[0])
            ll[:] = np.nan

            # index
            save_i = 0
            # list to process at the end (to merge points in subnets with < 3 items
            merge = []

            for i in range(len(centroids)):
                labels_len = len([la for la in labels if la == i])

                if labels_len > SUBNET_LIMIT:
                    # rerun this cluster to make it smaller
                    tpoints = points[labels == i]
                    # make a selection of the stations
                    tstations = [st for la, st in zip(labels.tolist(), stations) if la == i]
                    # run make_clusters
                    tclusters = self.make_clusters(tpoints, tstations, SUBNET_LIMIT)
                    # save the ouptput
                    tcentroids = tclusters['centroids']
                    tlabels    = tclusters['labels']

                    for j in range(len(tcentroids)):
                        # don't do anything with empty centroids
                        if len(tpoints[tlabels == j]) > 0:
                            cc, ll, save_i = self.save_cluster(points, tpoints[tlabels == j], cc,
                                                               tcentroids[j], ll, save_i)

                elif 0 < labels_len <= 3:
                    # this subnet is made of only two elements: merge to closest subnet
                    merge.append(i)

                elif labels_len == 0:
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
                        dc   = distance.cdist(np.array([pp[idx[0]]]), cc_p) / 1e3

                        min_centroid = np.argmin(dc, axis=1)

                        # next line finds the centroid index in the global centroid variable cc
                        centroid_index = np.argmax((cc == cc_p[min_centroid[0]]).all(axis=1))
                        # assign the centroid_index to the label of the point in question
                        ll[np.where(ll == i)[0][idx[0]]] = centroid_index

                        # calculate again without this point
                        pp   = points[ll == i]
                        dist = distance.cdist(pp, pp) / 1e3
                        # remove zeros
                        dist[dist == 0] = np.inf
        else:
            # not necessary to split the network
            cc = np.array([np.mean(points, axis=0)])
            ll = np.zeros(len(stations))

        # put everything in a dictionary
        clusters = { 'centroids'  : cc,
                     'labels'     : ll,
                     'stations'   : [] }

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
        labels    = clusters['labels']

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
        if len(stations) <= NET_LIMIT:
            return []
        else:
            # this session will require be split into more than one subnet

            active_stations = stations.get_active_stations(date)

            points = np.array([[stn.record.lat, stn.record.lon] for stn in active_stations])

            stn_candidates = list(active_stations)

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
                centroid = int(np.argmin(np.sum(np.abs(points[mask] - mean_ll), axis=1)))

                core_network += [stn_candidates[centroid]]

            return core_network

    @staticmethod
    def recover_subnets(db_subnets, stations):
        # this method does not update the labels because they are not used
        # labels are only used to tie station
        clusters = {'centroids': [],
                    'labels'   : [],
                    'stations' : []}

        backbone = []
        ties     = []

        # check if there is more than one sub-network
        if len(db_subnets) == 1:
            # single network reported as sub-network zero
            # no backbone and no ties, single network processing
            clusters = {'centroids': np.array([db_subnets[0]['centroid']]),
                        'labels'   : np.zeros(len(stations)),
                        'stations' : [stations]
                        }
        else:
            # multiple sub-networks: 0 contains the backbone; 1 contains cluster 1; 2 contains...
            for subnet in db_subnets[1:]:
                clusters['centroids'].append(subnet['centroid'])
                # labels start at zero, but zero subnet is backbone
                # clusters['labels'] += np.ones(len(subnet['stations'])) * (subnet['subnet'] - 1)
                # DDG: clusters['stations'] should not have the ties! this is because ties are merged to each
                #      sub-network in GamitSession
                clusters['stations'].append([stations[stn] for stn in subnet['stations'] if stn not in subnet['ties']])
                # add the corresponding ties
                ties.append([stations[stn] for stn in subnet['ties']])

            clusters['centroids'] = np.array(clusters['centroids'])

            # now recover the backbone
            backbone = [stations[stn] for stn in db_subnets[0]['stations']]

        return clusters, backbone, ties

    def add_missing_station(self, cnn, clusters, add_station):

        # this method does not update the labels because they are not used
        # labels are only used to tie station

        if len(clusters['centroids']) == 1:
            # single station network, just add the missing station
            clusters['stations'][0].append(add_station)
            clusters['labels'] = np.zeros(len(clusters['stations'][0]))

            # because a station was added, delete the gamit_stats record to force reprocessing
            for table in ('gamit_stats', 'gamit_subnets'):
                cnn.delete(table, Project=self.name, Year=self.date.year, DOY=self.date.doy, subnet=0)

            tqdm.write(' -- %s was not originally in the processing, will be added to sub-network %s00'
                       % (add_station.netstn, self.org))
        else:
            # find the closest centroid to this station
            xyz = np.zeros((1, 3))
            xyz[0] = np.array([add_station.X, add_station.Y, add_station.Z])
            # find distances between stations and clusters
            dist = distance.cdist(xyz, clusters['centroids']) / 1e3
            # sort distances
            min_i = np.argsort(dist)[0][0]

            # can add the station to this sub-network
            clusters['stations'][min_i].append(add_station)
            # because a station was added, delete the gamit_stats and subnets record to force reprocessing
            for table in ('gamit_stats', 'gamit_subnets'):
                cnn.delete(table, Project=self.name, Year=self.date.year, DOY=self.date.doy, subnet=min_i + 1)

            tqdm.write(' -- %s was not originally in the processing, will be added to sub-network %s%02i'
                       % (add_station.netstn, self.org, min_i + 1))
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
