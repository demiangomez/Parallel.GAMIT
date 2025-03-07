from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("pgamit")
except PackageNotFoundError:
    # package is not installed
    pass

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
