# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Parallel.GAMIT'
copyright = '2024, Demián D. Gómez'
author = 'Demián D. Gómez'
release = '1.0.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
import os
import sys
from unittest.mock import MagicMock # for mock importing for autodoc and argparse
from unittest.mock import Mock
sys.path.insert(0, os.path.abspath(".."))

extensions = ['sphinx.ext.viewcode','sphinx.ext.autodoc', 'sphinx_argparse_cli', 'sphinx.ext.napoleon']

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
# remove mock import of classes later
MOCK_MODULES = ['numpy', 'pg', 'scandir', 'magic', 'tqdm', 'scipy','xmltodict','matplotlib','simplekml','snxParse','pgdb','dispy','country_converter','paramiko','DownloadSources','mpl_toolkits','libcomcat','hdf5storage','sklearn','seaborn','scipy.interpolate','matplotlib.pyplot','mpl_toolkits.basemap','matplotlib.dates','matplotlib.collections','scipy.spatial','sklearn.cluster','scipy.stats','matplotlib.widgets','dispy.httpd','numpy.linalg','geopy.geocoders','numpy.random', 'pyOkada','libcomcat.search','libcomcat.exceptions', 'scipy.sparse', 'sklearn.neighbors', 'sklearn.base', 'sklearn.utils', 'sklearn.utils._openmp_helpers', 'sklearn.utils._param_validation', 'sklearn.utils.extmath','sklearn.utils.validation','sklearn.cluster._k_means_common','sklearn.cluster._kmeans', 'geopy.extra','scipy.io', 'geopy.extra.rate_limiter','psycopg2','psycopg2.extras','psycopg2.extensions','networkx', 'pyOptions']

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = MagicMock(return_value = "")


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
# html_static_path = ['_static']
