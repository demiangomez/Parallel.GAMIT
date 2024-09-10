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

sys.path.insert(0, os.path.abspath(".."))
sys.path.append("../classes")
extensions = ['sphinx.ext.viewcode','sphinx.ext.autodoc', 'sphinx_argparse_cli', 'sphinx.ext.napoleon']

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

MOCK_MODULES = ['numpy', 'pg', 'scandir', 'pyProducts','magic', 'pyDate', 'tqdm', 'pyRunWithRetry', 'pyEvents', 'scipy','dbConnection','pyTrimbleT0x','pyOptions','pyETM','pyStationInfo','xmltodict','matplotlib','simplekml','pyRinex','snxParse','pyRinexName','pgdb','pyBunch','dispy','pyBrdc','country_converter','pyJobServer','pyPPP','paramiko','DownloadSources','pyArchiveStruct','mpl_toolkits','libcomcat','hdf5storage','pyGamitConfig','pySp3','sklearn','seaborn','pyEOP','pyOTL','ScanArchive','pyStation','pyGamitSession','pyGamitTask','pyNetwork','pyStack','pyClk','pyGlobkTask','pyParallelGamit','pyParseZTD','pyVoronoi','scipy.interpolate','matplotlib.pyplot','mpl_toolkits.basemap','matplotlib.dates','matplotlib.collections','scipy.spatial','sklearn.cluster','scipy.stats','matplotlib.widgets','dispy.httpd','numpy.linalg','geopy.geocoders','numpy.random', 'pyOkada','libcomcat.search','libcomcat.exceptions']

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = MagicMock(return_value = "")


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
