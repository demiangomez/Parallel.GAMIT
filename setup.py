# A minimal setup.py file to make a Python project installable.
#
# Stolen from https://github.com/fperez/mytoy/blob/main/setup.py
#
# Note that while we are following modern packaging practices
# with setuptools metadata being declaratively stored in setup.cfg
# and build configuration listed in pyproj.toml, pip/setuptools
# as of this writing (early 2022) still require a minimal setup.py
# file in order to support editable development installs (pip install -e .)

from setuptools import setup

import os

lib_folder = os.path.dirname(os.path.realpath(__file__))
requirement_path = f"{lib_folder}/requirements.txt"
install_requires = []

if os.path.isfile(requirement_path):
    with open(requirement_path) as f:
        install_requires = f.read().splitlines()

if __name__ == "__main__":
    setup(install_requires=install_requires,
          scripts=['com/StationInfoEdit.py',
                   'com/ArchiveService.py',
                   'com/GenerateKml.py',
                   'com/PlotETM.py',
                   'com/AlterETM.py',
                   'com/CloseStationInfo.py',
                   'com/ConvertDate.py',
                   'com/ConvertTrimble.py',
                   'com/DownloadSources.py',
                   'com/DownloadSourcesFill.py',
                   'com/DRA.py',
                   'com/FixPlate.py',
                   'com/GenerateSinex.py',
                   'com/IntegrityCheck.py',
                   'com/LocateRinex.py',
                   'com/NEQStack.py',
                   'com/OTL_FES2014b.py',
                   'com/ParallelGamit.py',
                   'com/PlotMapView.py',
                   'com/QueryETM.py',
                   'com/S-score.py',
                   'com/ScanArchive.py',
                   'com/Stacker.py',
                   'com/StationInfoEdit.py',
                   'com/SyncOrbits.py',
                   'com/TrajectoryFit.py',
                   'com/UpdateEarthquakes.py',
                   'com/WeeklyCombination.py',
                   'com/Ztd2trp.py',
                   # these are scripts that are outside dependencies but added for convenience
                   'scripts/crz2rnx',
                   'scripts/rnx2crz',
                   'scripts/rename_crinex.sh',
                   'scripts/rename_with_logs.sh',
                   'scripts/rename_crinex2lower.sh'])
