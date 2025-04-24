"""Various utilities and functions to help ParallelGamit."""

# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: August 2024 (clustering functions)

import warnings
import numpy as np
import pandas as pd
import scipy.sparse as sp
import heapq
import networkx as nx
from tqdm import tqdm

from scipy.spatial.distance import pdist, squareform

from sklearn.neighbors import NearestNeighbors
from sklearn.base import _fit_context
from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
from sklearn.utils._param_validation import Integral, Interval, StrOptions
from sklearn.utils.extmath import row_norms
from sklearn.utils.validation import (_check_sample_weight, check_random_state)
from sklearn.cluster._k_means_common import _inertia_dense, _inertia_sparse
from sklearn.cluster._kmeans import (_BaseKMeans, _kmeans_single_elkan,
                                     _kmeans_single_lloyd)


def prune(OC, central_points, method='minsize'):
    """Prune redundant clusters from over cluster (OC) and other arrays

    Parameters
    ----------

    OC : bool array of shape (n_clusters, n_coordinates)
    method : ["linear", "minsize:]; "linear" is a row-by-row scan through the
        cluster matrix, "minsize" will sort matrix rows (i.e., the clusters)
        according to size and prioritize pruning the smallest clusters first.

    Returns

    OC : Pruned bool array of shape (n_clusters - N, n_coordinates)
    central_points : Pruned int array of shape (n_clusters -N,)
    """
    subset = []
    rowlength = len(OC[0,:])
    if method == "linear":
        indices = list(range(len(OC)))
    elif method == "minsize":
        indices = np.argsort(OC.sum(axis=1))
    else:
        raise ValueError("Unknown method '" + method + "'")
    for i in indices:
        mod = OC.copy()
        mod[i, :] = np.zeros(rowlength)
        counts = mod.sum(axis=0)
        problems = np.sum(counts == 0)
        if problems == 0:
            subset.append(i)
            OC[i, :] = np.zeros(rowlength)
    # Cast subset list to pandas index
    dfIndex = pd.Index(subset)
    # Cast OC to pandas dataframe
    dfOC = pd.DataFrame(OC)
    # Apply the 'inverse' index; pruned is boolean numpy index array
    pruned = ~dfOC.index.isin(dfIndex)
    return OC[pruned], central_points[pruned]


def select_central_point(coordinates, centroids, metric='euclidean'):
    """Select the nearest central point in a given neighborhood

    Note this code explicitly assumes that centroids are passed from a
    sklearn clustering result (i.e., kmeans, or bisecting kmeans); those
    centroids are ordered as monotonically increasing labels. In other words,
    the output indices will match the labeling order of the input centroids.
    Note that `n_features` refers to the dimensionality of coordinate system,
    i.e., 2 for lat/lon, 3 for ECEF (Earth-Centered Earth-Fixed), etc.

    Parameters
    ----------

    coordinates : ndarray of shape (n_samples, n_features)
        Coordinates do not need to match what was used for the prior
        clustering; i.e., if 'Euclidean' was used to calculate the prior
        clustering in an X,Y,Z projection, those coordinates can be provided in
        spherical coordinates, provided that 'haversine' is selected for the
        `metric` parameter.
    centroids : ndarray of shape (n_clusters, n_features)
        Coordinates of the cluster centroids; distance metric for centroids
        should match both `coordinates` and the `metric` parameter.
    metric : str or callable, default='euclidean'
        Metric to use for distance computation. Any metric from scikit-learn or
        scipy.spatial.distance can be used. If metric is a callable function,
        it is called on each pair of instances (rows) and the resulting value
        recorded. See scikit-learn documentation for additional details.

    Returns
    -------
    central_points_idxs : int array of shape (n_clusters,)
        Indices of the central most point for each cluster; indices match the
        `labels` ordering.
    """
    nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree',
                            metric=metric).fit(coordinates)
    idxs = nbrs.kneighbors(centroids, return_distance=False)
    return idxs.squeeze()


def over_cluster(labels, coordinates, metric='haversine', neighbors=5,
                 overlap_points=2, rejection_threshold=None, method='static'):
    """Expand cluster membership to include edge points of neighbor clusters

    Expands an existing clustering to create overlapping membership between
    clusters. Existing clusters are processed sequentially by looking up
    nearest neighbors as an intersection of the current cluster membership and
    all cluster's point membership.  Once the `overlap_points` for a given
    neighbor cluster have been determined and added to current cluster, the
    remainder of that neighboring cluster is removed from consideration and
    distance query is rerun, with the process repeating until a number of
    clusters equal to the `neighborhood` parameter is reached. For stability,
    only original points are included for subsequent neighborhood searches;
    that is, Nearest neighbor distances are run as the shortest distance from
    all **original** members of the current cluster.

    Function requires an initial vector of cluster labels from a prior
    clustering, and coordinates in an ordering that matches the labels. This
    function also assumes that all points have been assigned a label (i.e.,
    there are no unlabeled points, or points labeled as 'noise').

    Parameters
    ----------

    labels : ndarray of type int, and shape (n_samples,)
        Cluster labels for each point in the dataset from prior clustering.
    coordinates : ndarray of shape (n_samples, n_features)
        Coordinates do not need to match what was used for the prior
        clustering; i.e., if 'Euclidean' was used to calculate the prior
        clustering in an X,Y,Z projection, those coordinates can be provided in
        spherical coordinates, provided that 'haversine' is selected for the
        `metric` parameter.
    metric : str or callable, default='haversine'
        Metric to use for distance computation. Any metric from scikit-learn or
        scipy.spatial.distance can be used. Note that latitude and longitude
        values will need to be converted to radians if using the default
        'haversine' distance metric.

        If metric is a callable function, it is called on each pair of
        instances (rows) and the resulting value recorded. The callable should
        take two arrays as input and return one value indicating the distance
        between them. This works for Scipy's metrics, but is less efficient
        than passing the metric name as a string.

        Use of "precomputed", i.e., a N-by-N distance matrix, has not been
        tested, nor have sparse matrices. These may or may not work.

        Valid values for metric are:

        - from scikit-learn: ['cityblock', 'cosine', 'euclidean', 'l1', 'l2',
          'manhattan']

        - from scipy.spatial.distance: ['braycurtis', 'canberra', 'chebyshev',
          'correlation', 'dice', 'hamming', 'jaccard', 'mahalanobis',
          'minkowski', 'rogerstanimoto', 'russellrao', 'seuclidean',
          'sokalmichener', 'sokalsneath', 'sqeuclidean', 'yule']

        Sparse matrices are only supported by scikit-learn metrics.  See the
        documentation for scipy.spatial.distance for details on these metrics.

    neighbors: int greater than or equal to 1, default=3
        For method='static', this is total number of points that will be added
        to the seed clusters during cluster expansion.
        For method='dynamic', this is the (zero-indexed) number of adjacent
        clusters to include when adding cluster membership overlap. Should be
        less than the number of unique cluster labels - 1.

    overlap_points : int greater than or equal to 1, default=2
        Should not exceed the size of the smallest cluster in `labels`.

    rejection_threshold : float, default=None
        Determines if any potential overlapping points should be rejected for
        being too far (from source centroid or nearest source edge point).
        Default of 'None' is equivalent to setting the threshold to infinity.
        Note that if value other than 'None' is used, there is no guarantee
        that all clusters will have overlap points added.

    method : 'static' (default) or 'dynamic'
        The 'static' method will always produce an overcluster equal to the
        `neighbors` parameter; 'dynamic' will produce an overcluster ceiling
        of (neighbors - 1) * overlap_points, with a floor of neighbors.

    Returns
    -------
    expanded_clusters : bool array of shape (n_clusters, n_coordinates)
        The updated labels, one-hot encoded. Each row is a boolean index to
        extract cluster membership for a given label. If labels are continuous
        integers starting at 0, then the row number will match the cluster
        label; if not, rows are ordered to monotonically increase from the
        smallest cluster label.
"""

    # Returns already sorted
    clusters = np.unique(labels)
    n_clusters = len(clusters)

    if (n_clusters - 1) < neighbors:
        neighbors = (n_clusters - 1)

    # reference index for reverse lookups
    ridx = np.array(list(range(len(labels))))
    output = np.zeros((n_clusters, len(labels)), dtype=np.bool_)

    for cluster in clusters:
        # Define current cluster membership (and non-membership)
        members = labels == cluster
        output[cluster, members] = True
        nonmembers = ~members

        # Implements 'edge' method of overlap expansion
        # Build index tree on members
        nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree',
                                metric=metric).fit(coordinates[members])
        if method == 'dynamic':
            coverage = len(np.unique(labels[output[cluster, :]]))
        elif method == 'static':
            coverage = 0
        while coverage <= neighbors:
            # intersect search tree with non-members
            D, _ = nbrs.kneighbors(coordinates[nonmembers, :])
            # Rejection threshold is lightly tested...
            if rejection_threshold:
                if np.min(D) > rejection_threshold:
                    break
            # Select closest external point to add to member cluster
            new_member = ridx[nonmembers][np.argmin(D)]
            # Remove point from future coordinate distance queries
            nonmembers[new_member] = 0
            # Add to member label array
            output[cluster, new_member] = 1
            if method == 'dynamic':
                # Update current count of over-clustered neighbors
                coverage = len(np.unique(labels[output[cluster, :]]))
            elif method == 'static':
                # Update current point expansion count
                coverage += 1
            # Grab label of new member for overlap check
            nm_label = labels[new_member]
            # Check if we've exceeded our overlap allotment...
            if sum(labels[output[cluster, :]] == nm_label) >= overlap_points:
                # ...if so, remove entire neighboring cluster
                remove = nm_label == labels
                nonmembers[remove] = False

    return output


class DeterministicClustering(object):
    def __init__(self, target_size=15, tolerance=4, num_tie_points=4, max_dist_to_centroid=5_000_000):
        self.target_size     = target_size
        self.num_tie_points  = num_tie_points
        self.tolerance       = tolerance
        self.max_dist        = max_dist_to_centroid
        self.points          = np.array([])
        self.OC              = np.array([])
        # variables to store results
        self.centroid_ids    = []
        self.clustered_ids   = []
        self.tie_ids         = []

    def constrained_agglomerative(self, points, tie_clusters=True):
        """
        Perform spatially-constrained agglomerative clustering with centroid snapping.
        Parameters:
            points (np.ndarray): Nx3 ECEF coordinates.
            tie_clusters (bool): to tie clusters together using neighbors, pass True

        Returns:
            clustered_points (List[List[np.ndarray]]): Points per cluster.
            labels (np.ndarray): Cluster label for each point.
            final_centroids (List[np.ndarray]): Snapped centroids from points for each cluster.
        """
        target_size = self.target_size
        margin      = self.tolerance
        max_dist_to_centroid = self.max_dist

        points = np.array(points)
        self.points = points

        min_size = target_size - margin
        max_size = target_size + margin

        clusters = {i: [i] for i in range(len(points))}
        centroids = {i: points[i] for i in range(len(points))}
        next_cluster_id = len(points)

        # Vectorized pairwise distance computation
        pairwise_dists = squareform(pdist(points))
        i_idx, j_idx = np.triu_indices(len(points), k=1)
        dists = pairwise_dists[i_idx, j_idx]
        valid_mask = dists <= max_dist_to_centroid * 2
        i_valid = i_idx[valid_mask]
        j_valid = j_idx[valid_mask]
        d_valid = dists[valid_mask]

        heap = list(zip(d_valid, i_valid, j_valid))
        heapq.heapify(heap)

        while heap:
            dist, ci, cj = heapq.heappop(heap)
            if ci not in clusters or cj not in clusters:
                continue

            merged_cluster = clusters[ci] + clusters[cj]
            if len(merged_cluster) > max_size:
                continue

            merged_points = points[merged_cluster]
            centroid = merged_points.mean(axis=0)
            # compare to square distance to avoid computing the sqrt and save some computation time
            if np.any(np.einsum('ij,ij->i', merged_points - centroid,
                                merged_points - centroid) > max_dist_to_centroid ** 2):
                continue

            clusters[next_cluster_id] = merged_cluster
            centroids[next_cluster_id] = centroid
            del clusters[ci], clusters[cj]
            del centroids[ci], centroids[cj]
            self.update_heap_vectorized(heap, clusters, centroids, centroid, merged_cluster,
                                        next_cluster_id, max_size, max_dist_to_centroid)

            next_cluster_id += 1

        # Precompute centroids and classify clusters
        cluster_items = list(clusters.values())
        cluster_lens = np.array([len(c) for c in cluster_items])
        is_final = cluster_lens >= min_size

        # Split clusters
        final_clusters = [cluster_items[i] for i in range(len(cluster_items)) if is_final[i]]
        leftovers = [cluster_items[i] for i in range(len(cluster_items)) if not is_final[i]]

        # Compute centroids for final clusters
        centroids_arr = np.array([points[c].mean(axis=0) for c in final_clusters])
        # Snap to closest input point in cluster
        snapped_idxs = [
            c[np.argmin(np.linalg.norm(points[c] - centroid, axis=1))]
            for c, centroid in zip(final_clusters, centroids_arr)
        ]
        final_centroids = list(points[snapped_idxs])
        centroid_ids = snapped_idxs

        for cluster in leftovers:
            if len(cluster) == 1:
                idx = cluster[0]
                point = points[idx]
                dists = np.linalg.norm(np.array(final_centroids) - point, axis=1)
                valid = [i for i in range(len(final_clusters)) if
                         len(final_clusters[i]) < max_size and dists[i] <= max_dist_to_centroid]
                if valid:
                    best_fit = valid[np.argmin(dists[valid])]
                else:
                    best_fit = np.argmin(dists)
                final_clusters[best_fit].append(idx)
                cluster_points = points[final_clusters[best_fit]]
                centroid = cluster_points.mean(axis=0)
                snapped_idx = final_clusters[best_fit][np.argmin(np.linalg.norm(cluster_points - centroid, axis=1))]
                final_centroids[best_fit] = points[snapped_idx]
                centroid_ids[best_fit]  = snapped_idx
            else:
                centroid = points[cluster].mean(axis=0)
                dists = np.linalg.norm(np.array(final_centroids) - centroid, axis=1)
                best_fit = None
                for i in np.argsort(dists):
                    potential = final_clusters[i] + cluster
                    if len(potential) <= max_size:
                        test_points = points[potential]
                        test_centroid = test_points.mean(axis=0)
                        if np.all(np.linalg.norm(test_points - test_centroid, axis=1) <= max_dist_to_centroid):
                            best_fit = i
                            break
                if best_fit is not None:
                    final_clusters[best_fit].extend(cluster)
                    cluster_points = points[final_clusters[best_fit]]
                    centroid = cluster_points.mean(axis=0)
                    snapped_idx = final_clusters[best_fit][np.argmin(np.linalg.norm(cluster_points - centroid, axis=1))]
                    final_centroids[best_fit] = points[snapped_idx]
                    centroid_ids[best_fit]  = snapped_idx
                else:
                    # tqdm.write(' -- cluster %i ended up with %i stations (min was %i)' % (len(final_clusters),
                    #                                                                 len(cluster), min_size))
                    final_clusters.append(cluster)
                    snapped_idx = cluster[np.argmin(np.linalg.norm(points[cluster] - centroid, axis=1))]
                    final_centroids.append(points[snapped_idx])
                    centroid_ids.append(snapped_idx)

        labels = np.zeros(len(points), dtype=int)
        for idx, cluster in enumerate(final_clusters):
            for i in cluster:
                labels[i] = idx

        self.clustered_ids  = final_clusters
        self.centroid_ids   = centroid_ids

        # ties clusters together
        if tie_clusters:
            self.add_tie_points(labels, self.num_tie_points, self.max_dist)

        return final_clusters, labels, centroid_ids

    def update_heap_vectorized(self, heap, clusters, centroids, centroid, merged_cluster, next_cluster_id, max_size,
                               max_dist_to_centroid):
        """
        Vectorized version to update the heap with valid cluster pairs after a merge.

        Parameters:
            heap (List[Tuple[float, int, int]]): The heap to update.
            clusters (Dict[int, List[int]]): Dictionary of cluster_id -> list of point indices.
            centroids (Dict[int, np.ndarray]): Dictionary of cluster_id -> centroid coordinates.
            centroid (np.ndarray): The centroid of the newly merged cluster.
            merged_cluster (List[int]): Indices of points in the new cluster.
            next_cluster_id (int): The ID of the new cluster.
            max_size (int): Maximum allowed cluster size.
            max_dist_to_centroid (float): Maximum allowed distance for a valid connection.
        """
        # Extract existing cluster IDs and their centroids
        existing_ids = np.array(list(clusters.keys()))
        existing_centroids = np.array([centroids[k] for k in existing_ids])
        existing_sizes = np.array([len(clusters[k]) for k in existing_ids])

        # Compute distance from new centroid to all others
        dists = np.linalg.norm(existing_centroids - centroid, axis=1)

        # Evaluate which existing clusters are valid for merging
        size_sum = existing_sizes + len(merged_cluster)
        valid = (existing_ids != next_cluster_id) & (size_sum <= max_size) & (dists <= max_dist_to_centroid * 2)

        # Push valid merge pairs into heap
        for other_id, dist in zip(existing_ids[valid], dists[valid]):
            heapq.heappush(heap, (dist, next_cluster_id, other_id))

    def add_tie_points(self, cluster_labels, num_neighbors=4, max_tie_distance=5_000_000):
        """
        Add reciprocal tie points to each cluster from its nearest neighbors,
        then ensure every disconnected cluster component (island) is connected
        to at least `num_neighbors` external clusters.

        Parameters:
            cluster_labels (np.ndarray): Cluster index (0..K-1) for each station.
            num_neighbors (int): Minimum number of external links each island must have.
            max_tie_distance (float): Max allowable tie distance in meters.

        Returns:
            new_clusters (List[List[int]]): Cluster station indices including added tie points.
            tie_points (List[List[int]]): Tie point indices added to each cluster.
        """

        points = self.points
        labels = cluster_labels
        centroids = self.get_centroid_coordinates()

        n_clusters = len(centroids)
        n_stations = points.shape[0]

        # === Step 1: Initialize cluster structure ===
        clusters = [[] for _ in range(n_clusters)]
        for idx, label in enumerate(labels):
            clusters[label].append(idx)

        new_clusters = [list(cluster) for cluster in clusters]
        tie_points = [[] for _ in range(n_clusters)]
        used_points = set()
        tie_log = np.zeros((n_clusters, n_clusters), dtype=bool)

        # === Step 2: Initial connections to nearby neighbors using centroids ===
        nbrs = NearestNeighbors(n_neighbors=num_neighbors + 1).fit(centroids)
        _, neighbors = nbrs.kneighbors(centroids)

        def add_reciprocal_tie(i, j, pi_idx, pj_idx):
            new_clusters[i].append(pj_idx)
            new_clusters[j].append(pi_idx)
            tie_points[i].append(pj_idx)
            tie_points[j].append(pi_idx)
            used_points.update({pi_idx, pj_idx})
            tie_log[i, j] = True
            tie_log[j, i] = True

        for i in range(n_clusters):
            for j in neighbors[i][1:]:
                if tie_log[i, j] or tie_log[j, i]:
                    continue
                pi = [idx for idx in clusters[i] if idx not in used_points]
                pj = [idx for idx in clusters[j] if idx not in used_points]
                if not pi or not pj:
                    continue
                dist_matrix = np.linalg.norm(points[pi][:, None, :] - points[pj][None, :, :], axis=2)
                min_idx = np.unravel_index(np.argmin(dist_matrix), dist_matrix.shape)
                min_dist = dist_matrix[min_idx]
                if min_dist <= max_tie_distance:
                    add_reciprocal_tie(i, j, pi[min_idx[0]], pj[min_idx[1]])


        # === Step 3: Build the graph from current tie connections ===
        G = nx.Graph()
        G.add_nodes_from(range(n_clusters))
        for i in range(n_clusters):
            for j in range(i + 1, n_clusters):
                if set(tie_points[i]) & set(clusters[j]) or set(tie_points[j]) & set(clusters[i]):
                    G.add_edge(i, j)

        # === Step 4: Ensure every disconnected component connects to at least `num_neighbors` others ===
        components = sorted(list(nx.connected_components(G)), key=len)

        while len(components) > 1:
            updated = False  # Flag to break early if no valid connections were made

            for comp in components:
                external_nodes = set(range(n_clusters)) - comp
                connection_candidates = []

                for i in comp:
                    for j in external_nodes:
                        if tie_log[i, j] or tie_log[j, i]:
                            continue
                        pi = [idx for idx in clusters[i] if idx not in used_points]
                        pj = [idx for idx in clusters[j] if idx not in used_points]
                        if not pi or not pj:
                            continue
                        dist_matrix = np.linalg.norm(points[pi][:, None, :] - points[pj][None, :, :], axis=2)
                        min_idx = np.unravel_index(np.argmin(dist_matrix), dist_matrix.shape)
                        dist = dist_matrix[min_idx]
                        if dist <= max_tie_distance:
                            connection_candidates.append((dist, i, j, pi[min_idx[0]], pj[min_idx[1]]))

                # Sort connections by shortest distance
                connection_candidates.sort()
                added = 0
                for conn in connection_candidates:
                    _, i, j, pi_idx, pj_idx = conn
                    if not G.has_edge(i, j):
                        add_reciprocal_tie(i, j, pi_idx, pj_idx)
                        G.add_edge(i, j)
                        added += 1
                        updated = True
                    if added >= num_neighbors:
                        break

                if added < num_neighbors:
                    pass
                    # tqdm.write(f" -- WARNING: Component containing clusters {sorted(comp)} "
                    #      f"was only connected to {added} external clusters under the distance constraint.")

            if not updated:
                # tqdm.write(" -- WARNING: Some disconnected components could not be joined with the rest of the graph.")
                break

            components = list(nx.connected_components(G))

        # create matrix with clusters and stations
        matrix = np.zeros((n_clusters, n_stations), dtype=bool)
        for i, cluster in enumerate(new_clusters):
            matrix[i, cluster] = True

        self.OC = np.array(matrix)

        self.clustered_ids = new_clusters
        self.tie_ids       = tie_points

        return new_clusters, tie_points

    def get_cluster_coordinates(self):
        return [[self.points[i] for i in cluster] for cluster in self.clustered_ids]

    def get_centroid_coordinates(self):
        return [self.points[i] for i in self.centroid_ids]

    def get_tie_coordinates(self):
        return [[self.points[i] for i in cluster] for cluster in self.tie_ids]


"""Bisecting Q-means clustering."""

# Modified from sklearn _bisecting_k_means.py
# Original bisecting_k_means author: Michal Krawczyk <mkrwczyk.1@gmail.com>
# Modifications by: Shane Grigsby <refuge@rocktalus.com>


class BisectingQMeans(_BaseKMeans):
    """Bisecting Q-Means clustering; modified from sklearn Bisecting K-means.

    In contrast to Bisecting K-Means, Bisecting Q-Means clustering will infer
    the number of clusters based on a termination condition. For this
    implementation the bisecting termination occurs according to the minimum
    and optimum cluster sizes, which are set by the `opt_size` and
    `min_size` parameters respectively. The child cluster of the bisected
    root cluster with the biggest inertia as determined by SSE (Sum of Squared
    Errors) will be selected bisection-- provided that the child cluster
    exceeds the set `*clust_size` boundary conditions. Cluster bisection
    terminates when there are no child clusters remaining that fulfill the user
    set boundary conditions.

    Parameters
    ----------
    max_size: int, default=25
        Hard cutoff to bypass the heuristic when bisecting clusters; no
        clusters greater than this size will be produced.

    init : {'k-means++', 'random'} or callable, default='random'
        Method for initialization:

        'k-means++' : selects initial cluster centers for k-mean
        clustering in a smart way to speed up convergence. See section
        Notes in k_init for more details.

        'random': choose `n_clusters` observations (rows) at random from data
        for the initial centroids.

        If a callable is passed, it should take arguments X, n_clusters and a
        random state and return an initialization.

    n_init : int, default=1
        Number of time the inner k-means algorithm will be run with different
        centroid seeds in each bisection.
        That will result producing for each bisection best output of n_init
        consecutive runs in terms of inertia.

    random_state : int, RandomState instance or None, default=None
        Determines random number generation for centroid initialization
        in inner K-Means. Use an int to make the randomness deterministic.
        See :term:`Glossary <random_state>`.

    max_iter : int, default=300
        Maximum number of iterations of the inner k-means algorithm at each
        bisection.

    verbose : int, default=0
        Verbosity mode.

    tol : float, default=1e-4
        Relative tolerance with regards to Frobenius norm of the difference
        in the cluster centers of two consecutive iterations  to declare
        convergence. Used in inner k-means algorithm at each bisection to pick
        best possible clusters.

    copy_x : bool, default=True
        When pre-computing distances it is more numerically accurate to center
        the data first. If copy_x is True (default), then the original data is
        not modified. If False, the original data is modified, and put back
        before the function returns, but small numerical differences may be
        introduced by subtracting and then adding the data mean. Note that if
        the original data is not C-contiguous, a copy will be made even if
        copy_x is False. If the original data is sparse, but not in CSR format,
        a copy will be made even if copy_x is False.

    algorithm : {"lloyd", "elkan"}, default="lloyd"
        Inner K-means algorithm used in bisection.
        The classical EM-style algorithm is `"lloyd"`.
        The `"elkan"` variation can be more efficient on some datasets with
        well-defined clusters, by using the triangle inequality. However it's
        more memory intensive due to the allocation of an extra array of shape
        `(n_samples, n_clusters)`.

    n_clusters : int, default=2
        The number of clusters to seed prior to recursively bisecting. This
        parameter is updated at inference time and will reflect the number of
        clusters identified after calling `fit`.

    Attributes
    ----------
    cluster_centers_ : ndarray of shape (n_clusters, n_features)
        Coordinates of cluster centers. If the algorithm stops before fully
        converging (see ``tol`` and ``max_iter``), these will not be
        consistent with ``labels_``.

    labels_ : ndarray of shape (n_samples,)
        Labels of each point.

    inertia_ : float
        Sum of squared distances of samples to their closest cluster center,
        weighted by the sample weights if provided.

    n_features_in_ : int
        Number of features seen during :term:`fit`.

    feature_names_in_ : ndarray of shape (`n_features_in_`,)
        Names of features seen during :term:`fit`. Defined only when `X`
        has feature names that are all strings.

    See Also
    --------
    KMeans : Original implementation of K-Means algorithm.

    """

    _parameter_constraints: dict = {
        **_BaseKMeans._parameter_constraints,
        "init": [StrOptions({"k-means++", "random"}), callable],
        "n_init": [Interval(Integral, 1, None, closed="left")],
        "copy_x": ["boolean"],
        "algorithm": [StrOptions({"lloyd", "elkan"})], }

    def __init__(
        self,
        max_size=25,
        *,
        init="random",
        n_init=1,
        random_state=None,
        max_iter=300,
        verbose=0,
        tol=1e-4,
        copy_x=True,
        algorithm="elkan",
        n_clusters=2,      # needed for base class, do not remove
    ):
        super().__init__(
            init=init,
            n_clusters=n_clusters,
            max_iter=max_iter,
            verbose=verbose,
            random_state=random_state,
            tol=tol,
            n_init=n_init,
        )

        self.max_size = max_size
        self.copy_x = copy_x
        self.algorithm = algorithm
        self.bisect = True

    def _warn_mkl_vcomp(self, n_active_threads):
        """Warn when vcomp and mkl are both present"""
        warnings.warn(
            "BisectingKMeans is known to have a memory leak on Windows "
            "with MKL, when there are less chunks than available "
            "threads. You can avoid it by setting the environment"
            f" variable OMP_NUM_THREADS={n_active_threads}."
        )

    def _bisect(self, X, x_squared_norms, sample_weight, cluster_to_bisect):
        """Split a cluster into 2 subsclusters.

        Parameters
        ----------
        X : {ndarray, csr_matrix} of shape (n_samples, n_features)
            Training instances to cluster.

        x_squared_norms : ndarray of shape (n_samples,)
            Squared euclidean norm of each data point.

        sample_weight : ndarray of shape (n_samples,)
            The weights for each observation in X.

        cluster_to_bisect : _BisectingTree node object
            The cluster node to split.
        """
        X = X[cluster_to_bisect.indices]
        x_squared_norms = x_squared_norms[cluster_to_bisect.indices]
        sample_weight = sample_weight[cluster_to_bisect.indices]

        best_inertia = None

        # Split samples in X into 2 clusters.
        # Repeating `n_init` times to obtain best clusters
        for _ in range(self.n_init):
            centers_init = self._init_centroids(
                X,
                x_squared_norms=x_squared_norms,
                init=self.init,
                random_state=self._random_state,
                n_centroids=2,
                sample_weight=sample_weight,
            )

            labels, inertia, centers, _ = self._kmeans_single(
                X,
                sample_weight,
                centers_init,
                max_iter=self.max_iter,
                verbose=self.verbose,
                tol=self.tol,
                n_threads=self._n_threads,
            )

            # allow small tolerance on the inertia to accommodate for
            # non-deterministic rounding errors due to parallel computation
            if best_inertia is None or inertia < best_inertia * (1 - 1e-6):
                best_labels = labels
                best_centers = centers
                best_inertia = inertia

        if self.verbose:
            print(f"New centroids from bisection: {best_centers}")

        counts = np.bincount(best_labels, minlength=2)
        scores = counts
        if (counts[0] + counts[1] >= self.max_size):
            cluster_to_bisect.split(best_labels, best_centers, scores)
        else:
            self.bisect = False

    @_fit_context(prefer_skip_nested_validation=True)
    def fit(self, X, y=None, sample_weight=None):
        """Compute bisecting k-means clustering.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)

            Training instances to cluster.

            .. note:: The data will be converted to C ordering,
                which will cause a memory copy
                if the given data is not C-contiguous.

        y : Ignored
            Not used, present here for API consistency by convention.

        sample_weight : array-like of shape (n_samples,), default=None
            The weights for each observation in X. If None, all observations
            are assigned equal weight. `sample_weight` is not used during
            initialization if `init` is a callable.

        Returns
        -------
        self
            Fitted estimator.
        """
        X = self._validate_data(
            X,
            accept_sparse="csr",
            dtype=[np.float64, np.float32],
            order="C",
            copy=self.copy_x,
            accept_large_sparse=False,
        )

        self._check_params_vs_input(X)

        self._random_state = check_random_state(self.random_state)
        sample_weight = _check_sample_weight(sample_weight, X, dtype=X.dtype)
        self._n_threads = _openmp_effective_n_threads()

        if self.algorithm == "lloyd" or self.n_clusters == 1:
            self._kmeans_single = _kmeans_single_lloyd
            self._check_mkl_vcomp(X, X.shape[0])
        else:
            self._kmeans_single = _kmeans_single_elkan

        # Subtract of mean of X for more accurate distance computations
        if not sp.issparse(X):
            self._X_mean = X.mean(axis=0)
            X -= self._X_mean

        # Initialize the hierarchical clusters tree
        self._bisecting_tree = _BisectingTree(
            indices=np.arange(X.shape[0]),
            center=X.mean(axis=0),
            score=0,
        )

        x_squared_norms = row_norms(X, squared=True)

        # run first bisection out of loop to avoid 0-count early termination
        cluster_to_bisect = self._bisecting_tree.get_cluster_to_bisect()
        self._bisect(X, x_squared_norms, sample_weight, cluster_to_bisect)
        while self.bisect:
            # Chose cluster to bisect
            cluster_to_bisect = self._bisecting_tree.get_cluster_to_bisect()

            # Split this cluster into 2 subclusters
            #if cluster_to_bisect is not None:
            if cluster_to_bisect.score > self.max_size:
                self._bisect(X, x_squared_norms, sample_weight,
                             cluster_to_bisect)
            else:
                self.bisect = False
                break

        # Aggregate final labels and centers from the bisecting tree
        self.labels_ = np.full(X.shape[0], -1, dtype=np.int32)
        self.cluster_centers_ = []

        for i, cluster_node in enumerate(self._bisecting_tree.iter_leaves()):
            self.labels_[cluster_node.indices] = i
            self.cluster_centers_.append(cluster_node.center)
            # label final clusters for future prediction
            cluster_node.label = i
            cluster_node.indices = None  # release memory

        self.n_clusters = len(self.cluster_centers_)
        cluster_centers_ = np.empty((self.n_clusters, X.shape[1]),
                                    dtype=X.dtype)
        for i, center in enumerate(self.cluster_centers_):
            cluster_centers_[i] = center[:]
        self.cluster_centers_ = cluster_centers_

        # Restore original data
        if not sp.issparse(X):
            X += self._X_mean
            self.cluster_centers_ += self._X_mean

        _inertia = _inertia_sparse if sp.issparse(X) else _inertia_dense
        self.inertia_ = _inertia(X, sample_weight, self.cluster_centers_,
                                 self.labels_, self._n_threads)

        self._n_features_out = self.cluster_centers_.shape[0]

        return self

    def _more_tags(self):
        return {"preserves_dtype": [np.float64, np.float32]}


class _BisectingTree:
    """Tree structure representing the hierarchical clusters from bisecting"""

    def __init__(self, center, indices, score):
        """Create a new cluster node in the tree.

        The node holds the center of this cluster and the indices of the data
        points that belong to it.
        """
        self.center = center
        self.indices = indices
        self.score = score

        self.left = None
        self.right = None

    def split(self, labels, centers, scores):
        """Split the cluster node into two subclusters."""
        self.left = _BisectingTree(indices=self.indices[labels == 0],
                                   center=centers[0], score=scores[0])
        self.right = _BisectingTree(indices=self.indices[labels == 1],
                                    center=centers[1], score=scores[1])

        # reset the indices attribute to save memory
        self.indices = None

    def get_cluster_to_bisect(self):
        """Return the cluster node to bisect next.

        It's based on the score of the cluster, which can be either the number
        of data points assigned to that cluster or the inertia of that cluster.
        """
        max_score = None

        for cluster_leaf in self.iter_leaves():
            if max_score is None or cluster_leaf.score > max_score:
                max_score = cluster_leaf.score
                best_cluster_leaf = cluster_leaf

        #if max_score >= self.opt_size: 
        if np.isneginf(max_score):
            self.bisect = False
        else:
            return best_cluster_leaf

    def iter_leaves(self):
        """Iterate over all the cluster leaves in the tree."""
        if self.left is None:
            yield self
        else:
            yield from self.left.iter_leaves()
            yield from self.right.iter_leaves()
