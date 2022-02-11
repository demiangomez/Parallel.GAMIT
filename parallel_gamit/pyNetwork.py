"""
Project: Parallel.GAMIT
Date: Mar-31-2017
Author: Demian D. Gomez

pom170921: Added new global subnet methods.
pom210921:
- Added comments
- Changed the brackets around the dist variable, instead of checking the truth of dist it was checking that the list
  contained a value instead. Should fix far away stations from being added.
- Added a distance check to the tie station assignment. Only stations within 1 Earth radius linear distance will be
  added to the ties.
- When checking for stations that weren’t assigned to a subnet, I mistakenly included the backbone stations which caused
  duplicate entries in some subnets.
pom220921:
- Changed 'if not iterate or len(points) <= BACKBONE_NET:' to 'if not iterate or len(points[n_mask]) <= BACKBONE_NET:'
  so only the masked stations are counted when comparing against the desired number of backbone stations.
- Added the geocenter to the backbone delaunay triangulation.
pom011021:
- Set a minimum number of subnets, the program will reduce the minimum number of stations per subnet until the minimum
  number of subnets is created. All changes are in the subnets_delaunay routine.
"""

from datetime import datetime
import time
import copy
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


BACKBONE_NET = 45
NET_LIMIT    = 40
SUBNET_LIMIT = 35
MAX_DIST     = 5000
MIN_DIST     = 20
MIN_STNS_PER_SUBNET = 1


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
            tqdm.write(' --  Processing type is %s with %i active stations'
                       % (GamitConfig.NetworkConfig['type'], len(stn_active)))

            if GamitConfig.NetworkConfig['type'] == 'regional':
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
            else:
                # DDG: if active stations is greater than BACKBONE_NET + 5, then we need to split the processing
                # into smaller subnets. If not, then we just use all stations as the processing network
                # We add 5 to BACKBONE_NET to create a hysteresis behavior in subnets_delaunay
                # In other words, the backbone net will have BACKBONE_NET stations and 6 stations will be available to
                # create some subnets. A single network solution will have a max size of BACKBONE_NET + 5
                if len(stn_active) > BACKBONE_NET + 5:
                    backbone = self.backbone_delauney(stations.get_active_coordinates(date), stn_active)
                    subnets = self.subnets_delaunay(backbone, stations.get_active_coordinates(date), stn_active)
                    clusters, ties = self.global_sel(subnets, stn_active)
                else:
                    # no need to create a set of clusters, just use them all
                    clusters = {'stations': [stn_active]}
                    backbone = []
                    ties = []

        self.sessions = self.create_gamit_sessions(cnn, archive, clusters, backbone, ties, date)

    @staticmethod
    def global_sel(subnets1, stn_active):
        """
        inputs:
        subnets1: list of dict with keys 'centroid', 'ties', 'stations', 'cent_stns', 'net_num'
        stn_active: StationCollection, all active stations on the given day.

        outputs:
        clusters: dict with keys: 'centroids', 'labels', 'stations'
        ties: list of lists with Station objects

        Explanation:
        loops through each delaunay subnet, splits it into N sub-subnets (based on number of non-tie stations) then loops
        through each non-tie station to find the the sub-subnet centroid it is furthest from and adds that non-tie station
        to that sub-subnet. After adding to that sub-subnet, the sub-subnet centroid is adjusted to include the newly added
        non-tie station. Loop continues until all stations have been assigned a sub-subnet. Then those sub-subnets are added
        to the 'networks' list. Inspired by the global_sel GAMIT routine.
        :return:
        """

        def arclen(sit1, sit2):
            return np.arccos(np.dot(sit1, sit2) / (np.linalg.norm(sit1) * np.linalg.norm(sit2)))

        # Initialize intermediate variables.
        networks = list()
        net_num = 0

        # Loop over the list of subnets to break down into smaller subnets.
        for sn in subnets1:
            # Initialize variables for the loop
            # nsubs: number of subnetworks to break into.
            # nrefs: number of reference stations (ties) for each sub-subnet
            # nstns: number of non-tie stations
            # stn_persub: number of stations per sub-subnetwork (including ties)
            # allstns: a useful array containing all the non-tie stations in the subnet
            # refxyz: an np.ndarray of the xyz coordinates for the tie stations.
            nsubs = int(np.ceil(float(float(len(sn['stns'])) / float(SUBNET_LIMIT))))
            nrefs = len(sn['vertices']) + len(sn['ties'])
            nstns = len(sn['stns'])
            stn_persub = nstns // 2 + nrefs
            allstns = np.array(sn['stns'])
            refxyz = np.zeros((nrefs, 3))
            # Loop over the tie stations (vertices of Delaunay triangle and tie stations) to assign X,Y,Z coordinates.
            for n1, r in enumerate(sn['vertices'] + list(sn['ties'])):
                refxyz[n1, ::] = [r.X, r.Y, r.Z]
            # Initialize the sub-subnets as dicts and update the total subnetwork number for that day.
            subs = list()
            for i in range(nsubs):
                subs.append({'centroid': np.mean(refxyz, axis=0), 'ties': list(sn['ties']) + sn['vertices'],
                             'stations': list(), 'cent_stns': refxyz.copy(), 'net_num': net_num})
                net_num = net_num + 1
            # Loop over the non-tie stations in that subnet and initialize the xyz position as an np.ndarray and the
            # distance as an np.ndarray with length of the number of sub-subnets in this subnet.
            for s1 in allstns:
                spos = np.array([s1.X, s1.Y, s1.Z])
                sdist = np.zeros(nsubs)
                # Loop over the sub-subnets and find the distance from the station to the sub-subnet centroid.
                for n1, net in enumerate(subs):
                    # If there are already the maximum number of stations in a sub-subnet then skip that sub-subnet.
                    if len(net['cent_stns']) >= stn_persub:
                        continue
                    ncent = np.mean(net['cent_stns'], axis=0)
                    # sdist[n] = np.linalg.norm(spos - ncent)
                    sdist[n1] = arclen(ncent, spos) * 6378e3
                # Find the sub-subnet centroid that is furthest away from the station and add the station to that
                # sub-subnet
                maxnet = np.argmax(sdist)
                subs[maxnet]['cent_stns'] = np.vstack((subs[maxnet]['cent_stns'], spos))
                subs[maxnet]['stations'].append(s1)
            # Add those sub-subnets to the list of all sub-subnets
            networks.extend(subs)
        # Create variables for use in the create_gamit_sessions routine.
        # Convert stn_active from a StationCollection to a list.
        stn_list = [s1 for s1 in stn_active]
        # Initialize the station to subnet number mapping.
        labels = np.zeros(len(stn_active))
        # Create a list of lists that contain the tie stations for the subnet at the elements index.
        ties1 = [n1['ties'] for n1 in networks]
        # Loop over the subnets.
        for n1 in networks:
            # Get the centroid defined by ALL stations in that subnet (ties and vertices included)
            n1['centroids'] = np.mean(n1['cent_stns'], axis=0)
            # Loop over the stations assigned to that subnet.
            for s1 in n1['stations']:
                # Find the element id (index) of the station and add change the label value at that same index to the
                # subnet number.
                idx = stn_list.index(s1)
                labels[idx] = n1['net_num']
        # Create an np.ndarray of the network centroids (only defined by the vertices).
        centroids = np.vstack([n1['centroids'] for n1 in networks])
        # Create a list of lists containing the non-tie, non-vertex stations in each subnet.
        stations = [n1['stations'] for n1 in networks]
        # Assign to the clusters variable for input to the create_gamit_sessions routine.
        clusters1 = {'centroids': centroids, 'labels': labels, 'stations': stations}
        return clusters1, ties1

    @staticmethod
    def subnets_delaunay(backbone1, points, stations):
        """
        Explanation:
        Given a backbone network, xyz coordinates of stations and a list of station objects, return a list of
        subnetworks bound by triangles with backbone stations as vertices.

        Algorithm:
        Create a new Delaunay triangulation with the backbone stations and the geocenter. Find the (3) backbone stations
        defining open tetrahedron faces. Go through each point/station and see which of the open faces (triangles)
        it is contained by.

        :param backbone1: list or stationcollection of the backbone stations for that day.
        :param points: list of all station coordinates in xyz for that day.
        :param stations: list or stationcollection with all available stations for a given day.
        :return:
        """

        def arclen(sit1, sit2):
            return np.arccos(np.dot(sit1, sit2) / (np.linalg.norm(sit1) * np.linalg.norm(sit2)))

        # Max arclength in radians
        maxratio = MAX_DIST / 6378

        # Create a list of station aliases from the stations object.
        stnnames = list()
        for n1, s1 in enumerate(stations):
            stnnames.append(s1.StationAlias)
        # Collect the backbone stations XYZ coordinates into an np.ndarray.
        backxyz1 = np.zeros((len(backbone1), 3))
        for n1, s1 in enumerate(backbone1):
            backxyz1[n1, 0] = s1.X
            backxyz1[n1, 1] = s1.Y
            backxyz1[n1, 2] = s1.Z
        # Add the geocenter (0,0,0) to the backbone station coordinate array.
        backxyz1 = np.vstack([backxyz1, np.zeros((1, 3))])
        # Create a copy of the backbone object (otherwise it gets overwritten).
        mbackbone = backbone1.copy()
        # Create a dummy Station object for the geocenter. Coordinates don't have to be defined since the backxyz object
        # uses the geocenter in it already.
        geocenter = copy.deepcopy(backbone1[0])
        geocenter.StationCode = 'geoc'
        geocenter.NetworkCode = 'nan'
        mbackbone.append(geocenter)
        # Generate a Delaunay triangulation of the backbone + geocenter.
        d_xyz1 = Delaunay(backxyz1)
        # Get the Station objects from the backbone network that were used in the triangulation into the correct order.
        # Since we're dealing with tetrahedrons there are 4 stations defining the vertices so it can get a bit
        # complicated when trying to organize the station names and coordinates
        bbstns = np.array(mbackbone)[d_xyz1.simplices]
        # Also organize the xyz coordinates of the vertices of each tetrahedron in the triangulation.
        verts = backxyz1[d_xyz1.simplices]
        # Get the neighbors object.
        neighbors = d_xyz1.neighbors
        # Initialize return variable and the subnet label.
        subnets1 = list()
        lab = 0
        # Loop over each tetrahedron in the triangulation.
        for zstn in zip(bbstns, verts, neighbors):
            # Get the stations, xyz coordinates and neighbors (corollary for open faces) defining the tetrahedron.
            stn1, vert, neigh = zstn
            # Find out how many open faces are on the tetrahedron. Since we are including the geocenter, most
            # tetrahedrons should include that station so there should be just 1 open face defined by 3 backbone
            # stations.
            open_faces = neigh.tolist().count(-1)
            # If there aren't any open faces move onto the next tetrahedron.
            if open_faces == 0:
                continue
            # Loop through the open faces.
            for nv in range(open_faces):
                # Initialize variable to pick out the stations defining the open face.
                vind = [True] * 4
                # Get the index of the first open face in the tetrahedron.
                find = neigh.tolist().index(-1)
                # Set the open face neighbor to 0 so it doesn't get selected again in the next loop.
                neigh[find] = 0
                # Set the station in the tetrahedron opposite the open face to false so it doesn't get added to the
                # subnet vertices.
                vind[find] = False
                # Initialize the subnet object.
                subnet_ref = dict()
                # Add the label to the subnet object.
                subnet_ref['label'] = lab
                lab = lab + 1
                # Add the Station objects defining the vertices for the open face triangle.
                subnet_ref['vertices'] = stn1[vind].tolist()
                # Add the XYZ coordinates of the open face vertices.
                subnet_ref['coords'] = np.array(vert[vind, ::])
                # Initialize the list to contain the stations contained within the triangle.
                subnet_ref['stns'] = list()
                # Initialize the set containing the tie stations (defined later).
                subnet_ref['ties'] = set()
                # Add the subnet to the list of subnets.
                subnets1.append(subnet_ref)
        # Start a loop over all the subnets to find out what the tie stations should be.
        for sn in subnets1:
            # Loop over all the subnets again.
            for sn2 in subnets1:
                # If a vertex of sn is in the list of vertices for sn2 then set the list entry to True. We want to find
                # out which triangles share a vertex so we can add all of that triangles vertices to the ties variable.
                a = [True if x.StationAlias in [y.StationAlias for y in sn2['vertices']] else False
                     for x in sn['vertices']]
                # If at least 1 vertex is common between subnets sn and sn2 but not all of them (that would be the
                # same subnet) then continue.
                if np.any(a) and not np.all(a):
                    # Loop over the vertices in the subnet sn2 and add them to the ties for the subnet sn as long as the
                    # vertex isn't already in subnet sn vertices.
                    for y in sn2['vertices']:
                        if y in sn['vertices'] or y == geocenter:
                            continue
                        ycoord = np.array([y.X, y.Y, y.Z])
                        ratios = np.zeros(len(sn['coords']))
                        for n1, cor in enumerate(sn['coords']):
                            ratios[n1] = arclen(ycoord, cor)
                        if any(ratios < maxratio):
                            sn['ties'].add(y)
        # Now start a loop over all the stations available for that day to find out which subnet they should be added
        # to.
        for stn1 in stations:
            # Skip if the station is in the backbone network.
            if stn1 in mbackbone:
                continue
            # Get the stations xyz coordinates into an np.ndarray.
            P = np.array([stn1.X, stn1.Y, stn1.Z])
            # Loop over all the subnets and find which subnet contains the station in XYZ coordinates.
            for subnet in subnets1:
                if stn1 in list(subnet['ties']) + subnet['vertices']:
                    continue
                # Begin algorithm...
                # Explanation of the algorithm here:
                # https://math.stackexchange.com/questions/544946/determine-if-projection-of-3d-point-onto-plane-is-within-a-triangle
                reftri1 = subnet['coords']
                P1 = reftri1[0, :]
                P2 = reftri1[1, :]
                P3 = reftri1[2, :]
                u = P2 - P1
                v = P3 - P1
                w = P - P1
                dists = arclen(P, np.mean(reftri1, axis=0)) < maxratio
                n1 = np.cross(u, v)
                nhat = n1 / np.linalg.norm(n1) ** 2
                gamma = np.dot(np.cross(u, w), nhat)
                beta = np.dot(np.cross(w, v), nhat)
                alpha = 1 - gamma - beta
                intri = np.all([(0 <= alpha) & (alpha <= 1), (0 <= beta) & (beta <= 1), (0 <= gamma) & (gamma <= 1)])
                # End algorithm...
                # If the station is contained by that subnet then add it to that subnet and stop looping over the
                # subnets. That way each station only belongs to one subnet.
                if intri and dists:
                    subnet['stns'].append(stn1)
                    break

        # Get rid of subnets with less than MIN_STNS_PER_SUBNET stations inside of it
        mask = np.ones(len(subnets1), dtype=bool)
        for n1, s1 in enumerate(subnets1):
            if len(s1['stns']) >= MIN_STNS_PER_SUBNET:
                continue
            mask[n1] = False

        # Count the number of subnets via the remaining True values in the mask array.
        if np.count_nonzero(mask) is 0:
            # DDG: if the result was zero subnets, then none of the subnets has at least one station
            raise ValueError('No subnets contained more than one station. This day should be run without invoking '
                             'the subnets_delaunay function.')

        # Finally, update the actual list of subnets so the ones with less than minstns are deleted.
        subnets1 = np.array(subnets1)[mask].tolist()
        # If the number of stations added to subnets isn't equal to the number of points...
        if sum([len(x['stns']) for x in subnets1]) != len(points):
            a = list()
            # Get a list of all the stations added to any subnet.
            for x in subnets1:
                for y in x['stns']:
                    a.append(y)
            b = set(a)
            c1 = list()
            # Find out which stations weren't added to a subnet.
            for x in stations:
                if x not in b:
                    c1.append(x)
            # Loop over the stations not already added to a subnet.
            for s1 in c1:
                if s1 in mbackbone:
                    continue
                # Initialize list for the distance to different subnets.
                nearness = list()
                # Loop over the subnets and find out how far away the station is from the subnet centroid
                # defined by the vertices.
                for sub in subnets1:
                    reftri1 = sub['coords']
                    P = np.array([s1.X, s1.Y, s1.Z])
                    centroid = np.mean(reftri1, axis=0)
                    dist = np.linalg.norm(P - centroid)
                    nearness.append(dist)
                # Pick out the closest subnet and add the station to that subnet.
                mindist = np.argmin(nearness)
                subnets1[mindist]['stns'].append(s1)
            # Check again that all points were assigned to a subnet, raise an error if they weren't.
            if sum([len(x['stns']) for x in subnets1]) != len(points) - len(backbone1):
                raise ValueError('Not all stations put into subnets.')
        # Return the list of subnet dicts.
        return subnets1

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
        stations2 = [stn for stn in stations]
        geocenter = copy.deepcopy(stations2[0])
        geocenter.NetworkCode = 'nan'
        geocenter.StationCode = 'geoc'
        stations2.append(geocenter)
        points = np.vstack((points, np.zeros((1, 3))))
        dt = Delaunay(points)

        # start distance to remove stations
        max_dist = 5

        # create a mask with all the stations
        mask = np.ones(points.shape[0], dtype=bool)

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
        if geocenter in backbone:
            backbone.pop(geocenter)
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
