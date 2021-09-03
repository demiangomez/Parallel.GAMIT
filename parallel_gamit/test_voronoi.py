"""
Project: Parallel.GAMIT
Date: 7/18/18 10:28 AM
Author: Demian D. Gomez

Program to generate a KML with the stations in a project and the stations out of a project
"""

import argparse
import time
import sys


# deps
from tqdm import tqdm
from scipy.spatial import SphericalVoronoi
from scipy.spatial import Delaunay
from scipy.spatial import distance
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import sklearn.cluster as cluster


# app
import dbConnection
from Utils import process_stnlist
from pyGamitConfig import GamitConfiguration
from pyDate import Date
import pyNetwork
import pyArchiveStruct
from pyParallelGamit import generate_kml
from pyETM import pyETMException
from pyVoronoi import calculate_surface_area_of_a_spherical_Voronoi_polygon
from pyStation import Station
from Utils import ll2sphere_xyz
from Utils import ecef2lla


BACKBONE_NET = 60
NET_LIMIT    = 40
MAX_DIST     = 5000
MIN_DIST     = 20


def station_list(cnn, NetworkConfig, dates):

    stations = process_stnlist(cnn, NetworkConfig['stn_list'].split(','))
    stn_obj = []

    # use the connection to the db to get the stations
    for Stn in tqdm(sorted(stations), ncols=80):

        NetworkCode = Stn['NetworkCode']
        StationCode = Stn['StationCode']

        # apply date -1 and date + 1 to avoid problems with files ending at 00:00 of date + 1
        rs = cnn.query(
            'SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
            '"ObservationSTime" >= \'%s\' AND "ObservationETime" <= \'%s\''
            % (NetworkCode, StationCode, (dates[0] - 1).first_epoch(), (dates[1] + 1).last_epoch()))

        if rs.ntuples() > 0:

            tqdm.write(' -- %s.%s -> adding...' % (NetworkCode, StationCode))
            try:
                stn_obj.append(Station(cnn, NetworkCode, StationCode, dates))

            except pyETMException:
                tqdm.write('    %s.%s -> station exists, but there was a problem initializing ETM.'
                           % (NetworkCode, StationCode))
        else:
            tqdm.write(' -- %s.%s -> no data for requested time window' % (NetworkCode, StationCode))

        sys.stdout.flush()

    # analyze duplicate names in the list of stations
    stn_obj = check_station_codes(stn_obj)

    return stn_obj


def check_station_codes(stn_obj):

    for i, stn1 in enumerate(stn_obj[:-1]):

        for stn2 in stn_obj[i+1:]:
            if stn1.NetworkCode != stn2.NetworkCode and stn1.StationCode == stn2.StationCode:
                # duplicate StationCode (different Network), produce Alias
                unique = False
                while not unique:
                    stn1.generate_alias()
                    # compare again to make sure this name is unique
                    unique = compare_aliases(stn1, stn_obj)

    return stn_obj


def compare_aliases(Station, AllStations):

    # make sure alias does not exists as alias and station code

    for stn in AllStations:

        # this if prevents comparing against myself, although the station is not added until after
        # the call to CompareAliases. But, just in case...
        if stn.StationCode != Station.StationCode and stn.NetworkCode != Station.NetworkCode and \
                        Station.StationAlias == stn.StationAlias or Station.StationAlias == stn.StationCode:
            # not unique!
            return False

    return True


def main():

    parser = argparse.ArgumentParser(description='GNSS time series stacker')

    parser.add_argument('project_file', type=str, nargs=1, metavar='{project cfg file}',
                        help="Project CFG file with all the stations being processed in Parallel.GAMIT")

    args = parser.parse_args()

    cnn = dbConnection.Cnn("gnss_data.cfg")

    GamitConfig = GamitConfiguration(args.project_file[0], check_config=False)  # type: GamitConfiguration

    stations = station_list(cnn, GamitConfig.NetworkConfig, [Date(year=1999, doy=100), Date(year=1999, doy=128)])

    # split the stations into subnet_count subnetworks

    archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct

    net_object = pyNetwork.Network(cnn, archive, GamitConfig, stations, Date(year=1999, doy=128))

    generate_kml([Date(year=1999, doy=128)], net_object.sessions, GamitConfig)

    # for subnet in range(len(centroids)):
    #     ts = len([la for la in labels if la == subnet])
    #     if ts > NET_LIMIT:
    #         print ' -- should subdivide %i (%i)' % (subnet, ts)
    #
    #     if ts == 1:
    #         print ' -- isolated network %i' % subnet
    #
    # ff = open('voronoi.txt', 'w')
    #
    # for i, stn in enumerate(stns):
    #     ff.write('%s %3.8f %3.8f %i\n' % (stn[0], lla[i][0], lla[i][1], int(labels[i])))
    #
    # ff.close()
    #
    # ff = open('backbone.txt', 'w')
    #
    # for i, stn in enumerate(stns):
    #     if backbone[i]:
    #         ff.write('%s %3.8f %3.8f\n' % (stn[0], lla[i][0], lla[i][1]))
    #
    # ff.close()


def backbone_delauney(points, type='regional'):

    if isinstance(points, list):
        # make a numpy array with the points if list passed
        points = np.array(points)

    dt = Delaunay(points)

    max_dist = 5

    mask = np.ones(points.shape[0], dtype=np.bool)

    while len(points[mask]) > BACKBONE_NET:
        print(len(points[mask]), max_dist)
        n_mask = mask.copy()
        removed = True

        while removed:
            removed = False

            for v in dt.simplices:
                # find edges

                d = distance.cdist(points[mask][v], points[mask][v]) / 1e3
                d[d == 0] = np.inf

                if np.any(d <= max_dist):
                    rp = v[np.where((d <= max_dist))[0]][0]

                    n_mask[np.where(mask)[0][rp]] = False
                    removed = True

            mask = n_mask.copy()
            dt = Delaunay(points[mask])

        max_dist = max_dist * 2

    return mask


def backbone_network(vstations, points, stns, ties):

    if isinstance(ties, list):
        # make a numpy array with the points if list passed
        ties = np.array(ties)

    flt = np.ones(len(ties), dtype=np.bool)

    # get xyz of the stations
    pc = ll2sphere_xyz(ties)
    print(pc)
    while len(pc[flt]) - BACKBONE_NET > 0:
        # calculate the spherical voronoi
        sv = SphericalVoronoi(pc[flt], radius=6371000, threshold=1e-9)
        #vor = Voronoi(lla)

        #fig = voronoi_plot_2d(vor, show_vertices=False, line_colors='orange',
        #                      line_width = 2, line_alpha = 0.6, point_size = 2)
        #plt.show()

        sv.sort_vertices_of_regions()

        area   = np.zeros(len(sv.regions))
        weight = np.zeros(len(sv.regions))
        for i, region in enumerate(sv.regions):
            area[i]   = calculate_surface_area_of_a_spherical_Voronoi_polygon(sv.vertices[region], 6371)
            weight[i] = 0.3 * area[i]  # also needs the stations weight (to do)

        # rank stations by weight
        minw = np.argsort(weight)
        #for m in minw:
        #    print stns[m][0], area[m]

        # remove the first one on the list
        flt[np.where(flt)[0][minw[0]]] = False

        print('iterating %i' % len(pc[flt]))

    plot_v(pc[flt], sv)
    return flt


def plot_v(pc, sv):

    from matplotlib import colors
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import proj3d

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    # plot the unit sphere for reference (optional)
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x = np.outer(np.cos(u), np.sin(v))
    y = np.outer(np.sin(u), np.sin(v))
    z = np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_surface(x, y, z, color='y', alpha=0.1)
    # plot generator points
    # ax.scatter(points[:, 0], points[:, 1], points[:, 2], c='b')
    ax.scatter(pc[:, 0], pc[:, 1], pc[:, 2], c='b')
    # plot Voronoi vertices
    ax.scatter(sv.vertices[:, 0], sv.vertices[:, 1], sv.vertices[:, 2], c='g')
    # indicate Voronoi regions (as Euclidean polygons)

    for region in sv.regions:
        random_color = colors.rgb2hex(np.random.rand(3))
        polygon      = Poly3DCollection([sv.vertices[region]], alpha=1.0)
        polygon.set_color(random_color)
        ax.add_collection3d(polygon)
    set_axes_equal(ax)
    plt.show()


def set_axes_equal(ax):
    '''Make axes of 3D plot have equal scale so that spheres appear as spheres,
    cubes as cubes, etc..  This is one possible solution to Matplotlib's
    ax.set_aspect('equal') and ax.axis('equal') not working for 3D.

    Input
      ax: a matplotlib axis, e.g., as output from plt.gca().
    '''

    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range  = abs(x_limits[1] - x_limits[0])
    x_middle = np.mean(x_limits)
    y_range  = abs(y_limits[1] - y_limits[0])
    y_middle = np.mean(y_limits)
    z_range  = abs(z_limits[1] - z_limits[0])
    z_middle = np.mean(z_limits)

    # The plot bounding box is a sphere in the sense of the infinity
    # norm, hence I call half the max range the plot radius.
    plot_radius = 0.5*max([x_range, y_range, z_range])

    ax.set_xlim3d([x_middle - plot_radius, x_middle + plot_radius])
    ax.set_ylim3d([y_middle - plot_radius, y_middle + plot_radius])
    ax.set_zlim3d([z_middle - plot_radius, z_middle + plot_radius])


def tie_subnetworks(vstations, centroids, labels, points, stns):

    if isinstance(points, list):
        # make a numpy array with the points if list passed
        points = np.array(points)

    dist = distance.cdist(centroids, centroids) / 1e3

    ties = np.zeros(centroids.shape[0])

    # make self distance infinite
    dist[dist == 0] = np.inf
    vties = [[] for _ in range(len(vstations))]

    for c in range(len(centroids)):
        # get the closest three centroids to find the closest subnetworks
        neighbors = np.argsort(dist[:, c])

        if ties[c] < 3:
            for n in neighbors:

                # only enter if less than 3 ties and if not tying to self
                # also, allow a 4th tie to a network if ties[c] is only 1
                if (ties[n] < 3 or ties[c] < 2) and n != c:
                    # to link to this neighbor, it has to have less then 3 ties. Otherwise continue to bext
                    print('working on net ' + str(c) + ' - ' + str(n))

                    # get all stations from current subnet and dist to each station of neighbor n
                    sd = distance.cdist(points[labels == c], points[labels == n]) / 1e3
                    # station names
                    st1 = np.array([s[0] for s in stns])[labels == c].tolist()
                    st2 = np.array([s[0] for s in stns])[labels == n].tolist()

                    # find the 4 closest stations
                    tie_stns = 0
                    tie_c = []
                    tie_n = []
                    for i in range(len(sd)):
                        s = smallestN_indices(sd, 1)[0]
                        # ONLY ALLOW TIES BETWEEN MIN_DIST AND MAX_DIST
                        if MIN_DIST <= sd[s[0], s[1]] <= MAX_DIST:
                            print(' pair: ' + st1[s[0]] + ' - ' + st2[s[1]] + ' ( %.1f' % sd[s[0], s[1]] + ' km)')
                            tie_c += [st2[s[1]]]
                            tie_n += [st1[s[0]]]
                            sd[s[0], :] = np.inf
                            sd[:, s[1]] = np.inf
                            tie_stns = tie_stns + 1

                            if tie_stns == 4:
                                break

                    # if successfully added 3 or more tie stations, then declared it tied
                    if tie_stns >= 3:
                        # add a tie to c and n subnets
                        ties[n] += 1
                        ties[c] += 1
                        vstations[c] += tie_c
                        vties[c] += tie_c
                        vstations[n] += tie_n
                        vties[n] += tie_n
                    else:
                        print(' no suitable ties found between these two networks')

                if ties[c] == 3:
                    # if current subnet already has 3 ties, continue to next one
                    break

    return vstations, vties


def smallestN_indices(a, N):
    """
    Function to return the row and column of the N smallest values
    :param a: array to search (any dimension)
    :param N: number of values to search
    :return: array with the rows-cols of min values
    """
    idx = a.ravel().argsort()[:N]
    return np.stack(np.unravel_index(idx, a.shape)).T


def make_clusters(points, p_filter=None):

    if isinstance(points, list):
        # make a numpy array with the points if list passed
        points = np.array(points)

    stn_count = points.shape[0]
    subnet_count = int(np.ceil(float(float(stn_count) / float(NET_LIMIT))))

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

        if len([la for la in labels if la == i]) > NET_LIMIT:
            # rerun this cluster to make it smaller
            tpoints = points[labels == i]
            tcentroids, tlabels = make_clusters(tpoints, labels == i)

            if p_filter is None:
                print(' >> calling make_clusters recursively on %i' % i)
                print(' -- divided into %i' % len(tcentroids))

            for j in range(len(tcentroids)):
                # don't do anything with empty centroids
                if len(tpoints[tlabels == j]) > 0:
                    cc, ll, save_i = save_cluster(points, tpoints[tlabels == j], cc, tcentroids[j], ll, save_i)

        elif 0 < len([la for la in labels if la == i]) <= 3:
            # this subnet is made of only two elements: merge to closest subnet
            merge.append(i)

        elif len([la for la in labels if la == i]) == 0:
            # nothing to do if length == 0
            pass

        else:
            # everything is good! save the cluster
            cc, ll, save_i = save_cluster(points, points[labels == i], cc, centroids[i], ll, save_i)

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

    return cc, ll


def save_cluster(all_points, c_points, cc, centroid, ll, save_i):

    cc = np.vstack((cc, centroid))
    for p in c_points:
        # find in all_points the location where all elements in axis 1 match p (the passed centroid)
        ll[(all_points == p).all(axis=1)] = save_i
    save_i += 1

    return cc, ll, save_i


def plot_clusters(data, algorithm, args, kwds):
    start_time = time.time()
    labels     = algorithm(*args, **kwds).fit_predict(data)
    end_time   = time.time()
    palette    = sns.color_palette('deep', np.unique(labels).max() + 1)
    colors     = [palette[x] if x >= 0 else (0.0, 0.0, 0.0) for x in labels]

    plt.scatter(data.T[0], data.T[1], c=colors, **plot_kwds)
    frame = plt.gca()
    frame.axes.get_xaxis().set_visible(False)
    frame.axes.get_yaxis().set_visible(False)
    plt.title('Clusters found by {}'.format(str(algorithm.__name__)), fontsize=24)
    plt.text(-0.5, 0.7, 'Clustering took {:.2f} s'.format(end_time - start_time), fontsize=14)


if __name__ == '__main__':
    main()
