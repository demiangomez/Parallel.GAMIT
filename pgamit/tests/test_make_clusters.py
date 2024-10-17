# Author: Shane Grigsby (espg) <refuge@rocktalus.com>
# Created: September 2024

import pytest
import numpy as np

from .common import gen_variable_density_clusters, generate_clustered_data
from ..cluster import BisectingQMeans, over_cluster


@pytest.mark.parametrize(
    ("max_size", "clust_size"),
    [
        [5, 10],
        [7, 10],
        [10, 50],
        [15, 50],
        [10, 250],
        [20, 250],
        [30, 250],
    ],
)
def test_ceiling_variable_density(max_size, clust_size):
    """Test algorithmic guarantee of BisectingQMeans on variable density data
    
    Verify that when `min_size=2`, that the max per cluster membership is
    under (<, less than) what parameter `opt_cluster_size` is set to"""

    data = gen_variable_density_clusters(clust_size)
    clust = BisectingQMeans(min_size=1, opt_size=max_size,
                            init='random', n_init=50, algorithm='lloyd',
                            max_iter=8000, random_state=42)
    clust.fit(data)

    _, counts = np.unique(clust.labels_, return_counts=True)
    assert np.max(counts) < max_size

@pytest.mark.parametrize(
    ("min_clust", "max_clust", "neighbors", "overlap"),
    [
        [1, 5, 5, 2],
        [1, 10, 2, 5],
        [1, 10, 5, 2],
        [3, 15, 2, 5],
        [3, 20, 1, 10],
        [2, 17, 10, 1],
    ],
)
def test_max_clust_expansion(min_clust, max_clust, neighbors, overlap):
    """Test algorithmic guarantee of `over_cluster`

    Verify that expanded cluster size is under (<=, less than or equal to):
    [initial cluster size + (neighbors * overlap)]"""
    
    data = gen_variable_density_clusters()
    clust = BisectingQMeans(min_size=min_clust, opt_size=max_clust,
                            init='random', n_init=50, algorithm='lloyd',
                            max_iter=8000, random_state=42)
    clust.fit(data)
 
    OC = over_cluster(clust.labels_, data, metric='euclidean',
                      neighborhood=neighbors, overlap_points=overlap)

    expanded_sizes = np.sum(OC, axis=1)
    _, original_sizes = np.unique(clust.labels_, return_counts=True)
    assert np.all((expanded_sizes - original_sizes) <= neighbors*overlap)

