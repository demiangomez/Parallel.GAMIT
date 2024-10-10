"""Common utilities for testing clustering."""

# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: September 2024

import numpy as np

def gen_variable_density_clusters(n_points_per_cluster=250, seed=0):
    """Generates 6 cluster blobs of varying density as synthetic continents 

    Modified from the sklearn OPTICS example and unit tests. (see
    https://scikit-learn.org/stable/auto_examples/cluster/plot_optics.html)"""

    np.random.seed(seed)

    C1 = [-5, -2] + 0.8 * np.random.randn(n_points_per_cluster, 2)
    C2 = [4, -1] + 0.1 * np.random.randn(n_points_per_cluster, 2)
    C3 = [1, -2] + 0.2 * np.random.randn(n_points_per_cluster, 2)
    C4 = [-2, 3] + 0.3 * np.random.randn(n_points_per_cluster, 2)
    C5 = [3, -2] + 1.6 * np.random.randn(n_points_per_cluster, 2)
    C6 = [5, 6] + 2 * np.random.randn(n_points_per_cluster, 2)
    X = np.vstack((C1, C2, C3, C4, C5, C6))

    return X

def generate_clustered_data(seed=0, n_clusters=3, n_features=2, 
                            n_samples_per_cluster=20, std=0.4):
    """Generic cluster generator (taken from sklearn common cluster tests)"""

    prng = np.random.RandomState(seed)

    # the data is voluntary shifted away from zero to check clustering
    # algorithm robustness with regards to non centered data
    means = (
        np.array(
            [
                [1, 1, 1, 0],
                [-1, -1, 0, 1],
                [1, -1, 1, 1],
                [-1, 1, 1, 0],
            ]
        )
        + 10
    )

    X = np.empty((0, n_features))
    for i in range(n_clusters):
        X = np.r_[
            X,
            means[i][:n_features] + std * prng.randn(n_samples_per_cluster, n_features),
        ]
    return X
