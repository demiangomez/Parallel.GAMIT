from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("package-name")
except PackageNotFoundError:
    # package is not installed
    pass

#__version__ = "1.2.3"

__all__ = [
    'cluster',
    'network',
    'plots',
    'pyRinexName',
    'Utils',
    'pyJobServer',
    'pyParseAntex',
    'pyStatic1d',
    'snxParse',
    'pyLeastSquares',
    'pyProducts',
    'pyStationInfo',
    'dbConnection',
    'pyDate',
    'pyOTL',
    'pyRinex',
    'pyTerminal',
    'pyArchiveStruct',
    'pyOkada',
    'pyTrimbleT0x',
    'pyETM',
    'pyOptions',
    'pyRunWithRetry',
    'pyVoronoi',
    'pyBunch',
    'pyEvents',
    'pyPPP',
    'pyProducts',
    'pyZTD',
    'pyStack',
    'pyGamitConfig',
    'pyGamitSession',
    'pyGamitTask',
    'pyGlobkTask',
    'pyParseZTD',
    'pyStation'
]

from pgamit import *
