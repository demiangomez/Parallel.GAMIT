# Plotting and helper functions for ParallelGamit

# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Date: August 2024

import time
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap

# from ..classes.Utils import ecef2lla


def ecef2lla(ecefArr):
    # convert ECEF coordinates to LLA
    # test data : test_coord = [2297292.91, 1016894.94, -5843939.62]
    # expected result : -66.8765400174 23.876539914 999.998386689

    # force what input (list, tuple, etc) to be a np array
    ecefArr = np.atleast_1d(ecefArr)

    # transpose to work on both vectors and scalars
    x = ecefArr.T[0]
    y = ecefArr.T[1]
    z = ecefArr.T[2]

    a = 6378137
    e = 8.1819190842622e-2

    asq = np.power(a, 2)
    esq = np.power(e, 2)

    b = np.sqrt(asq * (1 - esq))
    bsq = np.power(b, 2)

    ep = np.sqrt((asq - bsq) / bsq)
    p = np.sqrt(np.power(x, 2) + np.power(y, 2))
    th = np.arctan2(a * z, b * p)

    lon = np.arctan2(y, x)
    lat = np.arctan2((z + np.power(ep, 2) * b * np.power(np.sin(th), 3)),
                     (p - esq * a * np.power(np.cos(th), 3)))
    N = a / (np.sqrt(1 - esq * np.power(np.sin(lat), 2)))
    alt = p / np.cos(lat) - N

    lon = lon * 180 / np.pi
    lat = lat * 180 / np.pi

    return lat.ravel(), lon.ravel(), alt.ravel()


def plot_global_network(central_points, OC, labels, points,
                        output_path, lat_lon=False):
    """Plot global GNSS station clustering and subnetwork connections

    Plots six views of the GNSS station clustering segmentation: polar
    stereographic north & south, and four views of the goid disk centered
    on the equator and rotated in 90 degree increments. Label colors for
    clusters are stable between subplots, and always refer to the same
    subnetwork. Overlapping tie points plotted twice, so that whichever
    subnetwork was plotter first will have that tie station over-plotted
    when the later subnetwork is plotted.

    Parameters
    ----------
    central_points : ndarray of type int, and shape (n_clusters,)
        Indices of the central most point (station) for each subnetwork.
        This is the output from `utils.select_central_point`
    OC : bool array of shape (n_clusters, n_coordinates)
        The expanded cluster labels, one-hot encoded. Each row is a boolean
        index to extract cluster membership for a given label. This is the
        output from `utils.over_cluster`
    labels : ndarray of type int, and shape (n_samples,)
        Cluster labels for each point in the dataset from prior clustering.
    points : ndarray of shape (n_samples, n_features)
        Coordinates of the station data, as either ECEF or Lat / Lon
    output_path : str
        File path to write the output plot to. Note that matplotlib infers
        the image output format from the file path suffix, so a path ending
        in '.png' will produce a png, and a '.jpeg' suffix will produce a jpg.
    lat_lon : boolean, default=False
        If the input parameter `points` is already in lat / lon coordinates.
        When set to (the default) `False`, input ECEF coordinates are assumed
        for `points`, and these are transformed to lat / lon for plotting.
    """

    # determine lat/lon coordinates, if needed
    if lat_lon:
        LL = points
    else:
        LL = np.zeros((len(labels), 2))
        lat, lon, _ = ecef2lla(points)
        LL[:, 0], LL[:, 1] = lon, lat  # x,y ordering for plotting convention

    fig = plt.figure(figsize=(8, 12))

    # empty lists (to fill in loop)
    nodes = []
    pos1, pos2, pos3, pos4, pos5, pos6 = [], [], [], [], [], []
    positions = [pos1, pos2, pos3, pos4, pos5, pos6]

    # define number and layout of subplots
    subs = [321, 322, 323, 324, 325, 326]

    # define projections, stack into list for iteration
    ref_r = (6378137.00, 6356752.3142)
    m1 = Basemap(projection='npstere', boundinglat=10, lon_0=270,
                 resolution='l')
    m2 = Basemap(projection='geos', lon_0=0, resolution='l', rsphere=ref_r)
    m3 = Basemap(projection='geos', lon_0=90, resolution='l', rsphere=ref_r)
    m4 = Basemap(projection='geos', lon_0=180, resolution='l', rsphere=ref_r)
    m5 = Basemap(projection='geos', lon_0=-90, resolution='l', rsphere=ref_r)
    m6 = Basemap(projection='spstere', boundinglat=-10, lon_0=270,
                 resolution='l')
    projs = [m1, m2, m3, m4, m5, m6]

    # for estimating start of plot run-time...
    t0 = time.time()
    for label in np.unique(labels):
        nodes.append(nx.Graph())
        # Select Cluster
        points = np.where(OC[label])[0]
        # Flag centroid point
        remove = np.where(points == central_points[label])[0]
        points = points.tolist()
        # remove centroid point so it's not repeated
        points.pop(remove[0])
        # add central point to beginning so it's the central connection point
        points.insert(0, central_points[label])
        nx.add_star(nodes[label], points)
        for position, proj in zip(positions, projs):
            mxy = np.zeros_like(LL[points])
            mxy[:, 0], mxy[:, 1] = proj(LL[points, 0], LL[points, 1])
            position.append(dict(zip(nodes[label].nodes, mxy)))

    colors = [plt.cm.prism(each) for each in np.linspace(0, 1, len(nodes))]
    for position, proj, sub in zip(positions, projs, subs):
        fig.add_subplot(sub)
        proj.drawcoastlines()
        proj.fillcontinents(color='grey', lake_color='aqua', alpha=0.3)
        for i, node in enumerate(nodes):
            # need reshape to squash warning
            r, g, b, a = colors[i]
            nx.draw(node, position[i], node_size=4, alpha=0.95, width=.2,
                    node_color=np.array([r, g, b, a]).reshape(1, 4))

    # end of plot run-time...
    t1 = time.time()
    fig.supxlabel("Figure runtime:  " + ("%.2fs" % (t1 - t0)).lstrip("0"))
    plt.savefig(output_path)
