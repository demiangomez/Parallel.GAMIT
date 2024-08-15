"""Various utilities and functions to help ParallelGamit."""

# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: August 2024 (clustering functions)

import warnings
import numpy as np
import scipy.sparse as sp

from sklearn.neighbors import NearestNeighbors

from sklearn.base import _fit_context
from sklearn.utils._openmp_helpers import _openmp_effective_n_threads
from sklearn.utils._param_validation import Integral, Interval, StrOptions
from sklearn.utils.extmath import row_norms
from sklearn.utils.validation import (_check_sample_weight, check_is_fitted,
                                      check_random_state)
from sklearn.cluster._k_means_common import _inertia_dense, _inertia_sparse
from sklearn.cluster._kmeans import (_labels_inertia_threadpool_limit,
                                     _BaseKMeans, _kmeans_single_elkan,
                                     _kmeans_single_lloyd)


def select_central_point(labels, coordinates, centroids,
                         metric='euclidean'):
    """Select the nearest central point in a given nieghborhood

    Note this code explicitly assumes that centroids are passed from an
    sklearn clustering result (i.e., kmeans, or bisecting kmeans); those
    centroids are ordered as monotonically increasing labels. In other words,
    the output indices will match the labeling order of the input centroids.
    """
    nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree',
                            metric=metric).fit(coordinates)
    idxs = nbrs.kneighbors(centroids, return_distance=False)
    return idxs.squeeze()
    # return labels[I], I #coordinates[I].squeeze()


def over_cluster(labels, coordinates, metric='haversine', neighborhood=5,
                 overlap_points=2,  method='edge', include_centroid=False,
                 rejection_threshold=None, centriod_labels=None):
    """Expand cluster membership to include edge points of neighbor clusters

    Expands an existing clustering to create overlapping membership between
    clusters. Existing clusters are processed sequentially by removing
    the current cluster, and looking up nearest neighbors from adjacent
    clusters. Once the `overlapping_points` for the first neighbor have
    been determined and added to current cluster, the first neighbor is
    removed and distance query is rerun, repeating the process N times as
    set by the `neighborhood` parameter. For stability, only original points
    are included for subsequent neighborhood searches. Nearest neighbor
    distances are either from the most central point of the current cluster,
    or the shortest distance of all original members of the current cluster.

    Function requires an initial vector of cluster labels from a prior
    clustering, and coordinates in an ordering that matches the labels. This
    function also assumes that all points have been assigned a label (i.e.,
    there are no unlabeled points, or points labeled as 'noise').

    For method 'center', the algorithm will build a reachability graph using
    the corresponding OPTICS method, select point with the shortest
    reachability value as the central point for distance queries; this
    approximates the densest portion of the cluster, rather than the
    geometric center. For method 'user', a vector of indices corresponding
    to central cluster points will be used. The `include_centroid` flag
    will add the central most point of a neighbor cluster to output
    groupings, and uses the previously mentioned OPTICS logic to determine
    centrality, unless `method` is set to 'user'.

    Parameters
    ----------

    labels : ndarray of type int, and shape (n_samples,)
        Cluster labels for each point in the dataset from prior clustering.
    coordinates : ndarray of shape (n_samples, n_features)
        Coordinates do not need to match what was used for the prior
        clustering; i.e., if 'Euclidean' was used to calculate the prior
        clustering in an X,Y,Z projection, those coordinates can be provided
        in spherical coordinates, provided that 'haversine' is selected for
        the `metric` parameter.
    metric : str or callable, default='haversine'
        Metric to use for distance computation. Any metric from scikit-learn
        or scipy.spatial.distance can be used. Note that latitude and
        longitude values will need to be converted to radians if using
        the default 'haversine' distance metric.

        If metric is a callable function, it is called on each
        pair of instances (rows) and the resulting value recorded. The callable
        should take two arrays as input and return one value indicating the
        distance between them. This works for Scipy's metrics, but is less
        efficient than passing the metric name as a string.

        Use of "precomputed", i.e., a N-by-N distance matrix, has not been
        tested, nor have sparse matrices. These may or may not work, but
        are likely to break if OPTICS is being used to calculate centrality
        of either the source or neighbor cluster.

        Valid values for metric are:

        - from scikit-learn: ['cityblock', 'cosine', 'euclidean', 'l1', 'l2',
          'manhattan']

        - from scipy.spatial.distance: ['braycurtis', 'canberra', 'chebyshev',
          'correlation', 'dice', 'hamming', 'jaccard', 'mahalanobis',
          'minkowski', 'rogerstanimoto', 'russellrao', 'seuclidean',
          'sokalmichener', 'sokalsneath', 'sqeuclidean', 'yule']

        Sparse matrices are only supported by scikit-learn metrics.
        See the documentation for scipy.spatial.distance for details on these
        metrics.

    neighborhood : int greater than or equal to 1, default=3
        Number of adjacent clusters to include when adding cluster membership
        overlap. Should be less than the number of unique cluster labels - 1.

    overlap_points : int greater than or equal to 1, default=2
        Should not exceed the size of the smallest cluster in `labels`, or
        one less than that when `include_centroid` is set to 'True'.

    method : {'edge', 'center', 'user'}, str, default='edge'
        The method used to determine distance when selecting nearest points
        of overlap. The default 'edge' will use the shortest distance
        considering all points in the source cluster; 'center' will determine
        the point in source cluster occupying the densest area of the cluster,
        and select the shortest distance from that point to any point outside
        of the source cluster. If selecting 'user', `centroid_labels` must be
        provided, and will be used for minimizing distances.

    include_centroids : bool, default=False
        Whether or not the most central point of adjacent clusters should be
        added as overlap points. If this option is set to 'True', returned
        cluster membership will be original cluster sizes + `overlap_points`
        + 1. Centroid points will be determined by OPTICS unless `method` is
        set to 'user' .

    rejection_threshold : float, default=None
        Determines if any potential overlapping points should be rejected for
        being too far (from source centroid or nearest source edge point).
        Default of 'None' is equivalent to setting the threshold to infinity.
        Note that if value other than 'None' is used, there is no guarantee
        that all clusters will have overlap points added.

    centroid_labels : ndarray of type int, shape (n_clusters,), default=None
        The indices corresponding to centroid points of each labeled cluster.
        Used only when ``method='user'``.

    Returns
    -------
    expanded_clusters : bool array of shape (n_clusters, n_coordinates)
        The updated labels, one-hot encoded. Each row is a boolean index to
        extract cluster membership for a given label. If labels are
        continuous integers starting at 0, then the row number will match the
        cluster label; if not, rows are ordered to monotonically increase
        from the smallest cluster label.
"""

    # Returns already sorted
    clusters = np.unique(labels)
    n_clusters = len(clusters)

    # reference index for reverse lookups
    ridx = np.array(list(range(len(labels))))
    output = np.zeros((n_clusters, len(labels)), dtype=np.bool_)

    for cluster in clusters:
        # Define current cluster membership (and non-membership)
        members = labels == cluster
        output[cluster, members] = True
        nonmembers = ~members

        if method == 'edge':
            # Build index tree on members
            nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree',
                                    metric=metric).fit(coordinates[members])
            # Could be set to '1';
            # using same check as while loop for consistency
            coverage = len(np.unique(labels[output[cluster, :]]))
            while coverage <= neighborhood:
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
                # Update current count of over-clustered nieghbors
                coverage = len(np.unique(labels[output[cluster, :]]))
                # Grab label of new member for overlap check
                nm_label = labels[new_member]
                # Check if we've exceeded our overlap allotment...
                if sum(labels[output[cluster, :]] == nm_label) >= overlap_points:
                    # ...if so, remove entire nieghboring cluster
                    remove = nm_label == labels
                    nonmembers[remove] = False
    return output

"""Bisecting Q-means clustering."""

# Modified from sklearn _bisecting_k_means.py
# Original bisecting_k_means author: Michal Krawczyk <mkrwczyk.1@gmail.com>
# Modifications by: Shane Grigsby <refuge@rocktalus.com>


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
        of data points assigned to that cluster or the inertia of that cluster
        (see `bisecting_strategy` for details).
        """
        max_score = None

        for cluster_leaf in self.iter_leaves():
            if max_score is None or cluster_leaf.score > max_score:
                max_score = cluster_leaf.score
                best_cluster_leaf = cluster_leaf

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


class BisectingQMeans(_BaseKMeans):
    """Bisecting Q-Means clustering; modified from sklearn Bisecting K-means.

    In contrast to Bisecting K-Means, Bisecting Q-Means clustering will infer
    the number of clustered based on a termination condition. For this
    implementation, bisecting termination occurs according to minimum and
    optimum cluster sizes.

    Parameters
    ----------
    n_clusters : int, default=2
        The number of clusters to seed prior to recursively bisecting. This
        parameter is updated at inference time and will reflect the number of
        clusters identified after calling `fit`.

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

    bisecting_strategy : {"biggest_inertia", "largest_cluster"},\
            default="biggest_inertia"
        Defines how bisection should be performed:

         - "biggest_inertia" means that BisectingKMeans will always check
            all calculated cluster for cluster with biggest SSE
            (Sum of squared errors) and bisect it. This approach concentrates
            on precision, but may be costly in terms of execution time
            (especially for larger amount of data points).

         - "largest_cluster" - BisectingKMeans will always split cluster with
            largest amount of points assigned to it from all clusters
            previously calculated. That should work faster than picking by SSE
            ('biggest_inertia') and may produce similar results in most cases.

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

    Notes
    -----
    It might be inefficient when n_cluster is less than 3, due to unnecessary
    calculations for that case.

    Examples
    --------
    >>> from overcluster import BisectingQMeans
    >>> import numpy as np
    >>> X = np.array([[1, 1], [10, 1], [3, 1],
    ...               [10, 0], [2, 1], [10, 2],
    ...               [10, 8], [10, 9], [10, 10]])
    >>> bisect_means = BisectingQMeans(random_state=0).fit(X)
    >>> bisect_means.labels_
    array([0, 2, 0, 2, 0, 2, 1, 1, 1], dtype=int32)
    >>> bisect_means.predict([[0, 0], [12, 3]])
    array([0, 2], dtype=int32)
    >>> bisect_means.cluster_centers_
    array([[ 2., 1.],
           [10., 9.],
           [10., 1.]])
    """

    _parameter_constraints: dict = {
        **_BaseKMeans._parameter_constraints,
        "init": [StrOptions({"k-means++", "random"}), callable],
        "n_init": [Interval(Integral, 1, None, closed="left")],
        "copy_x": ["boolean"],
        "algorithm": [StrOptions({"lloyd", "elkan"})],
        "bisecting_strategy": [StrOptions({"biggest_inertia",
                                           "largest_cluster"})], }

    def __init__(
        self,
        n_clusters=8,
        *,
        init="random",
        n_init=1,
        random_state=None,
        max_iter=300,
        verbose=0,
        tol=1e-4,
        copy_x=True,
        algorithm="lloyd",
        bisecting_strategy="biggest_inertia",
    ):
        super().__init__(
            n_clusters=n_clusters,
            init=init,
            max_iter=max_iter,
            verbose=verbose,
            random_state=random_state,
            tol=tol,
            n_init=n_init,
        )

        self.copy_x = copy_x
        self.algorithm = algorithm
        self.bisecting_strategy = bisecting_strategy
        self.bisect = True

    def _warn_mkl_vcomp(self, n_active_threads):
        """Warn when vcomp and mkl are both present"""
        warnings.warn(
            "BisectingKMeans is known to have a memory leak on Windows "
            "with MKL, when there are less chunks than available "
            "threads. You can avoid it by setting the environment"
            f" variable OMP_NUM_THREADS={n_active_threads}."
        )

    def _inertia_per_cluster(self, X, centers, labels, sample_weight):
        """Calculate the sum of squared errors (inertia) per cluster.

        Parameters
        ----------
        X : {ndarray, csr_matrix} of shape (n_samples, n_features)
            The input samples.

        centers : ndarray of shape (n_clusters=2, n_features)
            The cluster centers.

        labels : ndarray of shape (n_samples,)
            Index of the cluster each sample belongs to.

        sample_weight : ndarray of shape (n_samples,)
            The weights for each observation in X.

        Returns
        -------
        inertia_per_cluster : ndarray of shape (n_clusters=2,)
            Sum of squared errors (inertia) for each cluster.
        """
        # n_clusters = 2 since centers comes from a bisection
        n_clusters = centers.shape[0]
        _inertia = _inertia_sparse if sp.issparse(X) else _inertia_dense

        inertia_per_cluster = np.empty(n_clusters)
        for label in range(n_clusters):
            inertia_per_cluster[label] = _inertia(X, sample_weight, centers,
                                                  labels, self._n_threads,
                                                  single_label=label)

        return inertia_per_cluster

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

        if self.bisecting_strategy == "biggest_inertia":
            scores = self._inertia_per_cluster(
                X, best_centers, best_labels, sample_weight
            )
            counts = np.bincount(best_labels, minlength=2)
            # scores = np.bincount(best_labels, minlength=2)
            scores[np.where(counts < 16)] = -np.inf
        else:  # bisecting_strategy == "largest_cluster"
            # Using minlength to make sure that we have the counts for both
            # labels even if all samples are labelled 0.
            scores = np.bincount(best_labels, minlength=2)
        # case where bisecting is not optimum
        if (counts[0] + counts[1]) < 20:
            cluster_to_bisect.score = -np.inf
        # bisect as long as the smallest child has membership of at least 4
        elif (counts[0] > 3) and (counts[1] > 3):
            cluster_to_bisect.split(best_labels, best_centers, scores)
        # one child will have membership of 3 or less; don't split
        else:
            cluster_to_bisect.score = -np.inf

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

        while self.bisect:
            # Chose cluster to bisect
            cluster_to_bisect = self._bisecting_tree.get_cluster_to_bisect()

            # Split this cluster into 2 subclusters
            if cluster_to_bisect is not None:
                self._bisect(X, x_squared_norms, sample_weight,
                             cluster_to_bisect)
            else:
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

    def predict(self, X):
        """Predict which cluster each sample in X belongs to.

        Prediction is made by going down the hierarchical tree
        in searching of closest leaf cluster.

        In the vector quantization literature, `cluster_centers_` is called
        the code book and each value returned by `predict` is the index of
        the closest code in the code book.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            New data to predict.

        Returns
        -------
        labels : ndarray of shape (n_samples,)
            Index of the cluster each sample belongs to.
        """
        check_is_fitted(self)

        X = self._check_test_data(X)
        x_squared_norms = row_norms(X, squared=True)

        # sample weights are unused but necessary in cython helpers
        sample_weight = np.ones_like(x_squared_norms)

        labels = self._predict_recursive(X, sample_weight,
                                         self._bisecting_tree)

        return labels

    def _predict_recursive(self, X, sample_weight, cluster_node):
        """Predict recursively by going down the hierarchical tree.

        Parameters
        ----------
        X : {ndarray, csr_matrix} of shape (n_samples, n_features)
            The data points, currently assigned to `cluster_node`, to predict
            between the subclusters of this node.

        sample_weight : ndarray of shape (n_samples,)
            The weights for each observation in X.

        cluster_node : _BisectingTree node object
            The cluster node of the hierarchical tree.

        Returns
        -------
        labels : ndarray of shape (n_samples,)
            Index of the cluster each sample belongs to.
        """
        if cluster_node.left is None:
            # This cluster has no subcluster.
            # Labels are just the label of the cluster.
            return np.full(X.shape[0], cluster_node.label, dtype=np.int32)

        # Determine if data points belong to the left or right subcluster
        centers = np.vstack((cluster_node.left.center,
                             cluster_node.right.center))
        if hasattr(self, "_X_mean"):
            centers += self._X_mean

        cluster_labels = _labels_inertia_threadpool_limit(
            X,
            sample_weight,
            centers,
            self._n_threads,
            return_inertia=False,
        )
        mask = cluster_labels == 0

        # Compute the labels for each subset of the data points.
        labels = np.full(X.shape[0], -1, dtype=np.int32)

        labels[mask] = self._predict_recursive(
            X[mask], sample_weight[mask], cluster_node.left
        )

        labels[~mask] = self._predict_recursive(
            X[~mask], sample_weight[~mask], cluster_node.right
        )

        return labels

    def _more_tags(self):
        return {"preserves_dtype": [np.float64, np.float32]}
