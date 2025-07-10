
import os
import re
import subprocess
import sys
import filecmp
import argparse
import stat
import shutil
import io
import base64
from datetime import datetime
from zlib import crc32 as zlib_crc32
from pathlib import Path


# deps
import numpy
import numpy as np
from importlib.metadata import version

# app
from pgamit import pyRinexName
from pgamit import pyDate


class UtilsException(Exception):
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return str(self.value)


def add_version_argument(parser):
    __version__ = version('pgamit')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    return parser


def cart2euler(x, y, z):
    alt = numpy.rad2deg(numpy.sqrt(x**2 + y**2 + z**2) * 1e-9 * 1e6)
    lat = numpy.rad2deg(numpy.arctan2(z, numpy.sqrt(x**2 + y**2)))
    lon = numpy.rad2deg(numpy.arctan2(y, x))
    return lat, lon, alt


def get_field_or_attr(obj, f):
    try:
        return obj[f]
    except:
        return getattr(obj, f)


def stationID(s):
    return "%s.%s" % (get_field_or_attr(s, 'NetworkCode'),
                      get_field_or_attr(s, 'StationCode'))


def get_stack_stations(cnn, name):
    rs = cnn.query_float(f'SELECT DISTINCT "NetworkCode", "StationCode", auto_x, auto_y, auto_z '
                         f'FROM stacks INNER JOIN stations '
                         f'USING ("NetworkCode", "StationCode")'
                         f'WHERE "name" = \'{name}\'', as_dict=True)

    # since we require spherical lat lon for the Euler pole, I compute it from the xyz values
    for i, stn in enumerate(rs):
        lla = xyz2sphere_lla(numpy.array([stn['auto_x'], stn['auto_y'], stn['auto_z']]))
        rs[i]['lat'] = lla[0][0]
        rs[i]['lon'] = lla[0][1]

    return rs


def parse_atx_antennas(atx_file):

    output = file_readlines(atx_file)

    # return re.findall(r'START OF ANTENNA\s+(\w+[.-\/+]?\w*[.-\/+]?\w*)\s+(\w+)', ''.join(output), re.MULTILINE)
    # do not return the RADOME
    return re.findall(r'START OF ANTENNA\s+([\S]+)', ''.join(output), re.MULTILINE)


def smallestN_indices(a, N):
    """
    Function to return the row and column of the N smallest values
    :param a: array to search (any dimension)
    :param N: number of values to search
    :return: array with the rows-cols of min values
    """
    idx = a.ravel().argsort()[:N]
    return numpy.stack(numpy.unravel_index(idx, a.shape)).T


def ll2sphere_xyz(ell):
    r = 6371000.0
    x = []
    for lla in ell:
        x.append((r * numpy.cos(lla[0] * numpy.pi / 180) * numpy.cos(lla[1] * numpy.pi / 180),
                  r * numpy.cos(lla[0] * numpy.pi / 180) * numpy.sin(lla[1] * numpy.pi / 180),
                  r * numpy.sin(lla[0] * numpy.pi / 180)))

    return numpy.array(x)


def xyz2sphere_lla(xyz):
    """
    function to turn xyz coordinates to lat lon using spherical earth
    output is lat, lon, radius
    """
    if isinstance(xyz, list):
        xyz = numpy.array(xyz)

    if xyz.ndim == 1:
        xyz = xyz[np.newaxis, :]

    g = numpy.zeros(xyz.shape)
    for i, x in enumerate(xyz):
        g[i, 0] = numpy.rad2deg(numpy.arctan2(x[2], numpy.sqrt(x[0]**2 + x[1]**2)))
        g[i, 1] = numpy.rad2deg(numpy.arctan2(x[1], x[0]))
        g[i, 2] = numpy.sqrt(x[0]**2 + x[1]**2 + x[2]**2)

    return g


def required_length(nmin, nmax):
    class RequiredLength(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not nmin <= len(values) <= nmax:
                msg = 'argument "{f}" requires between {nmin} and {nmax} arguments'.format(
                       f = self.dest, nmin = nmin, nmax = nmax)
                raise argparse.ArgumentTypeError(msg)

            setattr(args, self.dest, values)

    return RequiredLength


def station_list_help():

    desc = ("List of networks/stations to process given in [net].[stnm] format or just [stnm] "
            "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
            "name will be processed). Use keyword 'all' to process all stations in the database. "
            "If [net].all is given, all stations from network [net] will be processed. Three letter ISO 3166 "
            "international standard codes can be provided (always in upper case) to select all stations within a "
            "country. If a station name is given using a * in front (e.g. *igs.pwro or *pwro) then the station will be "
            "removed from the list. If *net.all or ISO country code was used (e.g. *igs.all or *ARG), then remove the "
            "stations within this group. Wildcards are accepted using the regex "
            "postgres convention. Use [] to provide character ranges (e.g. ars.at1[3-5] or ars.[a-b]x01). Char %% "
            "matches any string (e.g. ars.at%%). Char | represents "
            "the OR operator that can be used to select one string or another (e.g. ars.at1[1|2] to choose at11 and "
            "at12). To specify a wildcard using a single character, use _ (equivalent to ? in POSIX regular "
            "expressions). Alternatively, a file with the station list can be provided (using all the same "
            "conventions described above). When using a file, * can be replaced with - for clarity "
            "in removing stations from .all lists")

    return desc


def parse_crinex_rinex_filename(filename):
    # DDG: DEPRECATED
    # this function only accepts .Z as extension. Replaced with RinexName.split_filename which also includes .gz
    # parse a crinex filename
    sfile = re.findall(r'(\w{4})(\d{3})(\w{1})\.(\d{2})([d]\.[Z])$', filename)
    if sfile:
        return sfile[0]

    sfile = re.findall(r'(\w{4})(\d{3})(\w{1})\.(\d{2})([o])$', filename)
    if sfile:
        return sfile[0]

    return []


def _increment_filename(filename):
    """
    Returns a generator that yields filenames with a counter. This counter
    is placed before the file extension, and incremented with every iteration.
    For example:
        f1 = increment_filename("myimage.jpeg")
        f1.next() # myimage-1.jpeg
        f1.next() # myimage-2.jpeg
        f1.next() # myimage-3.jpeg
    If the filename already contains a counter, then the existing counter is
    incremented on every iteration, rather than starting from 1.
    For example:
        f2 = increment_filename("myfile-3.doc")
        f2.next() # myfile-4.doc
        f2.next() # myfile-5.doc
        f2.next() # myfile-6.doc
    The default marker is an underscore, but you can use any string you like:
        f3 = increment_filename("mymovie.mp4", marker="_")
        f3.next() # mymovie_1.mp4
        f3.next() # mymovie_2.mp4
        f3.next() # mymovie_3.mp4
    Since the generator only increments an integer, it is practically unlimited
    and will never raise a StopIteration exception.
    """
    # First we split the filename into three parts:
    #
    #  1) a "base" - the part before the counter
    #  2) a "counter" - the integer which is incremented
    #  3) an "extension" - the file extension

    sessions = ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9] + [chr(x) for x in range(ord('a'), ord('x')+1)] +
                [chr(x) for x in range(ord('A'), ord('X')+1)])

    path      = os.path.dirname(filename)
    filename  = os.path.basename(filename)
    # replace with parse_crinex_rinex_filename (deprecated)
    # fileparts = parse_crinex_rinex_filename(filename)
    fileparts = pyRinexName.RinexNameFormat(filename).split_filename(filename)

    # Check if there's a counter in the filename already - if not, start a new
    # counter at 0.
    value = 0

    filename = os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(), int(fileparts[1]), sessions[value],
                                                       int(fileparts[3]), fileparts[4]))

    # The counter is just an integer, so we can increment it indefinitely.
    while True:
        if value == 0:
            yield filename

        value += 1

        if value == len(sessions):
            raise ValueError('Maximum number of sessions reached: %s%03i%s.%02i%s'
                             % (fileparts[0].lower(), int(fileparts[1]), sessions[value-1],
                                int(fileparts[3]), fileparts[4]))

        yield os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(), int(fileparts[1]), sessions[value],
                                                      int(fileparts[3]), fileparts[4]))


def copyfile(src, dst, rnx_ver=2):
    """
    Copies a file from path src to path dst.
    If a file already exists at dst, it will not be overwritten, but:
     * If it is the same as the source file, do nothing
     * If it is different to the source file, pick a new name for the copy that
       is different and unused, then copy the file there (if rnx_ver=2)
     * If because rinex 3 files have names that are more comprehensive (include start time and duration)
       if a rnx_ver == 3 then copy the file unless it already exists (in which case it does nothing)
    Returns the path to the copy.
    """
    if not os.path.exists(src):
        raise ValueError('Source file does not exist: {}'.format(src))

    # make the folders if they don't exist
    # careful! racing condition between different workers
    try:
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
    except OSError:
        # some other process created the folder an instant before
        pass

    # Keep trying to copy the file until it works
    if rnx_ver < 3:
        # only use this method for RINEX 2
        # RINEX 3 files should have distinct names as a default if the files are different
        dst_gen = _increment_filename(dst)

    while True:
        if rnx_ver < 3:
            dst = next(dst_gen)

        # Check if there is a file at the destination location
        if os.path.exists(dst):

            # If the namesake is the same as the source file, then we don't
            # need to do anything else.
            if filecmp.cmp(src, dst):
                return dst
            else:
                # DDG: if the rinex version is == 3 and the files have the same name:
                # 1) if dst size is < than src, replace file
                # 2) if dst size is > than src, do nothing
                # for RINEX 2 files, loop over and find a different filename
                if rnx_ver >= 3:
                    if os.path.getsize(src) > os.path.getsize(dst):
                        os.remove(dst)
                        if do_copy_op(src, dst):
                            return dst
                        else:
                            raise OSError('File exists during copy of RINEX 3 file: ' + dst)
                    else:
                        return dst
        else:
            if do_copy_op(src, dst):
                # If we get to this point, then the write has succeeded
                return dst
            else:
                if rnx_ver >= 3:
                    raise OSError('Problem while copying RINEX 3 file: ' + dst)


def do_copy_op(src, dst):
    # If there is no file at the destination, then we attempt to write
    # to it. There is a risk of a race condition here: if a file
    # suddenly pops into existence after the `if os.path.exists()`
    # check, then writing to it risks overwriting this new file.
    #
    # We write by transferring bytes using os.open(). Using the O_EXCL
    # flag on the dst file descriptor will cause an OSError to be
    # raised if the file pops into existence; the O_EXLOCK stops
    # anybody else writing to the dst file while we're using it.
    src_fd = None
    dst_fd = None
    try:
        src_fd = os.open(src, os.O_RDONLY)
        dst_fd = os.open(dst, os.O_WRONLY | os.O_EXCL | os.O_CREAT)

        # Read 65536 bytes at a time, and copy them from src to dst
        while True:
            data = os.read(src_fd, 65536)
            if not data:
                # When there are no more bytes to read from the source
                # file, 'data' will be an empty string
                return True
            os.write(dst_fd, data)

    # An OSError errno 17 is what happens if a file pops into existence
    # at dst, so we print an error and try to copy to a new location.
    # Any other exception is unexpected and should be raised as normal.
    except OSError as e:
        if e.errno != 17 or e.strerror != 'File exists':
            raise
        return False
    finally:
        if src_fd != None:
            os.close(src_fd)
        if dst_fd != None:
            os.close(dst_fd)


def move(src, dst):
    """
    Moves a file from path src to path dst.
    If a file already exists at dst, it will not be overwritten, but:
     * If it is the same as the source file, do nothing
     * If it is different to the source file, pick a new name for the copy that
       is distinct and unused, then copy the file there.
    Returns the path to the new file.
    """
    rnx_ver = pyRinexName.RinexNameFormat(dst).version
    dst = copyfile(src, dst, rnx_ver)
    os.remove(src)
    return dst


def ct2lg(dX, dY, dZ, lat, lon):

    n = dX.size

    R = rotct2lg(lat, lon, n)

    dxdydz = numpy.column_stack((numpy.column_stack((dX, dY)), dZ))

    RR = numpy.reshape(R[0, :, :], (3, n))
    dx = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
    RR = numpy.reshape(R[1, :, :], (3, n))
    dy = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
    RR = numpy.reshape(R[2, :, :], (3, n))
    dz = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)

    return dx, dy, dz


def rotct2lg(lat, lon, n=1):

    R = numpy.zeros((3, 3, n))

    R[0, 0, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
    R[0, 1, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
    R[0, 2, :] = numpy.cos(numpy.deg2rad(lat))
    R[1, 0, :] = -numpy.sin(numpy.deg2rad(lon))
    R[1, 1, :] = numpy.cos(numpy.deg2rad(lon))
    R[1, 2, :] = numpy.zeros((1, n))
    R[2, 0, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
    R[2, 1, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
    R[2, 2, :] = numpy.sin(numpy.deg2rad(lat))

    return R


def lg2ct(dN, dE, dU, lat, lon):

    n = dN.size

    R = rotlg2ct(lat, lon, n)

    dxdydz = numpy.column_stack((numpy.column_stack((dN, dE)), dU))

    RR = numpy.reshape(R[0, :, :], (3, n))
    dx = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
    RR = numpy.reshape(R[1, :, :], (3, n))
    dy = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)
    RR = numpy.reshape(R[2, :, :], (3, n))
    dz = numpy.sum(numpy.multiply(RR, dxdydz.transpose()), axis=0)

    return dx, dy, dz


def rotlg2ct(lat, lon, n=1):

    R = numpy.zeros((3, 3, n))

    R[0, 0, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
    R[1, 0, :] = -numpy.multiply(numpy.sin(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
    R[2, 0, :] = numpy.cos(numpy.deg2rad(lat))
    R[0, 1, :] = -numpy.sin(numpy.deg2rad(lon))
    R[1, 1, :] = numpy.cos(numpy.deg2rad(lon))
    R[2, 1, :] = numpy.zeros((1, n))
    R[0, 2, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.cos(numpy.deg2rad(lon)))
    R[1, 2, :] = numpy.multiply(numpy.cos(numpy.deg2rad(lat)), numpy.sin(numpy.deg2rad(lon)))
    R[2, 2, :] = numpy.sin(numpy.deg2rad(lat))

    return R


def ecef2lla(ecefArr):
    # convert ECEF coordinates to LLA
    # test data : test_coord = [2297292.91, 1016894.94, -5843939.62]
    # expected result : -66.8765400174 23.876539914 999.998386689

    # force what input (list, tuple, etc) to be a numpy array
    ecefArr = numpy.atleast_1d(ecefArr)

    # transpose to work on both vectors and scalars
    x = ecefArr.T[0]
    y = ecefArr.T[1]
    z = ecefArr.T[2]

    a = 6378137
    e = 8.1819190842622e-2

    asq = numpy.power(a, 2)
    esq = numpy.power(e, 2)

    b   = numpy.sqrt(asq * (1 - esq))
    bsq = numpy.power(b, 2)

    ep = numpy.sqrt((asq - bsq) / bsq)
    p  = numpy.sqrt(numpy.power(x, 2) + numpy.power(y, 2))
    th = numpy.arctan2(a * z, b * p)

    lon = numpy.arctan2(y, x)
    lat = numpy.arctan2((z + numpy.power(ep, 2) * b * numpy.power(numpy.sin(th), 3)),
                        (p - esq * a * numpy.power(numpy.cos(th), 3)))
    N   = a / (numpy.sqrt(1 - esq * numpy.power(numpy.sin(lat), 2)))
    alt = p / numpy.cos(lat) - N

    lon = lon * 180 / numpy.pi
    lat = lat * 180 / numpy.pi

    return lat.ravel(), lon.ravel(), alt.ravel()


def lla2ecef(llaArr):
    # convert LLA coordinates to ECEF
    # test data : test_coord = [-66.8765400174 23.876539914 999.998386689]
    # expected result : 2297292.91, 1016894.94, -5843939.62

    llaArr = numpy.atleast_1d(llaArr)

    # transpose to work on both vectors and scalars
    lat = llaArr.T[0]
    lon = llaArr.T[1]
    alt = llaArr.T[2]

    rad_lat = lat * (numpy.pi / 180.0)
    rad_lon = lon * (numpy.pi / 180.0)

    # WGS84
    a = 6378137.0
    finv = 298.257223563
    f = 1 / finv
    e2 = 1 - (1 - f) * (1 - f)
    v = a / numpy.sqrt(1 - e2 * numpy.sin(rad_lat) * numpy.sin(rad_lat))

    x = (v + alt) * numpy.cos(rad_lat) * numpy.cos(rad_lon)
    y = (v + alt) * numpy.cos(rad_lat) * numpy.sin(rad_lon)
    z = (v * (1 - e2) + alt) * numpy.sin(rad_lat)

    return numpy.round(x, 4).ravel(), numpy.round(y, 4).ravel(), numpy.round(z, 4).ravel()


def process_date_str(arg, allow_days=False):

    rdate = pyDate.Date(datetime=datetime.now())

    try:
        if '.' in arg:
            rdate = pyDate.Date(fyear=float(arg))
        elif '_' in arg:
            rdate = pyDate.Date(year=int(arg.split('_')[0]),
                                doy=int(arg.split('_')[1]))
        elif '/' in arg:
            rdate = pyDate.Date(year=int(arg.split('/')[0]),
                                month=int(arg.split('/')[1]),
                                day=int(arg.split('/')[2]))
        elif '-' in arg:
            rdate = pyDate.Date(gpsWeek=int(arg.split('-')[0]),
                                gpsWeekDay=int(arg.split('-')[1]))
        elif len(arg) > 0:
            if allow_days:
                rdate = pyDate.Date(datetime=datetime.now()) - int(arg)
            else:
                raise ValueError('Invalid input date: allow_days was set to False.')

    except Exception as e:
        raise ValueError('Could not decode input date (valid entries: '
                         'fyear, yyyy_ddd, yyyy/mm/dd, gpswk-wkday). '
                         'Error while reading the date start/end parameters: ' + str(e))

    return rdate


def process_date(arg, missing_input='fill', allow_days=True):
    # function to handle date input from PG.
    # Input: arg = arguments from command line
    #        missing_input = a string specifying if vector should be filled when something is missing
    #        allow_day = allow a single argument which represents an integer N expressed in days, to compute now()-N

    now = datetime.now()
    if missing_input == 'fill':
        dates = [pyDate.Date(year=1980, doy=1),
                 pyDate.Date(datetime = now)]
    else:
        dates = [None, None]

    if arg:
        for i, arg in enumerate(arg):
            dates[i] = process_date_str(arg, allow_days)

    return tuple(dates)


def determine_frame(frames, date):

    for frame in frames:
        if frame['dates'][0] <= date <= frame['dates'][1]:
            return frame['name'], frame['atx']

    raise Exception('No valid frame was found for the specified date.')


def print_columns(l):

    for a, b, c, d, e, f, g, h in zip(l[::8], l[1::8], l[2::8], l[3::8], l[4::8], l[5::8], l[6::8], l[7::8]):
        print('    {:<10}{:<10}{:<10}{:<10}{:<10}{:<10}{:<10}{:<}'.format(a, b, c, d, e, f, g, h))

    if len(l) % 8 != 0:
        sys.stdout.write('    ')
        for i in range(len(l) - len(l) % 8, len(l)):
            sys.stdout.write('{:<10}'.format(l[i]))
        sys.stdout.write('\n')


def get_resource_delimiter():
    return '.'


def process_stnlist(cnn, stnlist_in, print_summary=True, summary_title=None):
    """
    Now the station list parser handles postgres regular expressions in the station list
    everything behaves as before, but also now support * and - to remove a station from the list (rather than only -)
    this is to support removal from the command line
    DDG June 21 2024: Now the file read accepts additional parameters in the station lines that are passed back in the
                      params key of the dictionary. This is to support, for example, passing velocities. Example:
                      arg.igm1 1.00
                      arg.lpgs 1.20
                      ...
    """
    if len(stnlist_in) == 1 and os.path.isfile(stnlist_in[0]):
        print(' >> Station list read from file: ' + stnlist_in[0])
        # DDG: if len(line.strip()) > 0 avoids any empty lines
        stnlist_in = [line.strip() for line in file_readlines(stnlist_in[0]) if len(line.strip()) > 0]

    stnlist = []
    # accepted wildcards for station names
    wildc = '[]%_|'

    for rstn in stnlist_in:
        # to allow for more parameters in station list text files
        sstn = rstn.split()
        stn = sstn[0]
        if len(sstn) > 1:
            par = sstn[1:]
        else:
            par = []

        rs = None
        if stn == 'all':
            # keyword all for all stations in list
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' '
                           'ORDER BY "NetworkCode", "StationCode"')

        elif stn.isupper() and stn[0] not in ('-', '*'):
            # country code
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND country_code = \'%s\' '
                           'ORDER BY "NetworkCode", "StationCode"' % stn)

        elif '.' in stn and stn[0] not in ('-', '*'):
            net, stnm = stn.split('.')
            # a net.stnm given
            if stnm == 'all':
                # all stations from a network
                rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND '
                               '"NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"' % net)
            elif any(c in set(wildc) for c in stnm):
                # DDG: wildcard
                rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" '
                               ' SIMILAR TO \'%s\' AND '
                               '"NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"'
                               % (net, stnm))
            else:
                # just a net.stnm
                rs = cnn.query(
                    'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND "NetworkCode" = \'%s\' '
                    'AND "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (net, stnm))

        elif '.' not in stn and stn[0] not in ('-', '*'):
            # just a station name (check for wildcards)
            if any(c in set(wildc) for c in stn):
                # wildcard
                rs = cnn.query(
                    'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND '
                    '"StationCode" SIMILAR TO \'%s\' ORDER BY "NetworkCode", "StationCode"' % stn)
            else:
                # just a station name
                rs = cnn.query(
                    'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND '
                    '"StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % stn)

        if rs is not None:
            for rstn in rs.dictresult():
                if {'NetworkCode': rstn['NetworkCode'], 'StationCode': rstn['StationCode']} not in stnlist:
                    stnlist.append({'NetworkCode' : rstn['NetworkCode'],
                                    'StationCode' : rstn['StationCode'],
                                    'marker'      : rstn['marker'] if rstn['marker'] else 0,
                                    'country_code': rstn['country_code'] if rstn['country_code'] else '',
                                    'parameters'  : par})

    # deal with station removals (- or *)
    for stn in [stn[1:] for stn in stnlist_in if stn[0] in ('-', '*')]:
        # if netcode not given, remove everybody with that station code
        if '.' in stn:
            net, stnm = stn.split('.')
            # a net.stnm given
            if stnm == 'all':
                # remove all stations in the provided network
                rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND '
                               '"NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"' % net)
                if rs is not None:
                    for rstn in rs.dictresult():
                        stnlist = [stnl for stnl in stnlist if stationID(stnl) != stationID(rstn)]
            else:
                stnlist = [stnl for stnl in stnlist if stationID(stnl) != stn]

        elif stn.isupper():
            # country code
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND country_code = \'%s\' '
                           'ORDER BY "NetworkCode", "StationCode"' % stn)
            if rs is not None:
                for rstn in rs.dictresult():
                    stnlist = [stnl for stnl in stnlist if stationID(stnl) != stationID(rstn)]
        else:
            stnlist = [stnl for stnl in stnlist if stnl['StationCode'] != stn]

    # sort the dictionary
    stnlist = sorted(stnlist, key=lambda i: i['StationCode'])

    if print_summary:
        if summary_title is None:
            print(' >> Selected station list:')
        else:
            print(' >> ' + summary_title)
        print_columns([stationID(item) for item in stnlist])

    return stnlist


def get_norm_year_str(year):
    
    # mk 4 digit year
    try:
        year = int(year)
        # defensively, make sure that the year is positive
        assert year >= 0 
    except:
        raise UtilsException('must provide a positive integer year YY or YYYY');
    
    if 80 <= year <= 99:
        year += 1900
    elif 0 <= year < 80:
        year += 2000        

    return str(year)


def get_norm_doy_str(doy):
    try:
        doy = int(doy)
        # create string version up fround
        return "%03d" % doy
    except:
        raise UtilsException('must provide an integer day of year'); 


def parseIntSet(nputstr=""):

    selection = []
    invalid   = []
    # tokens are comma separated values
    tokens    = [x.strip() for x in nputstr.split(';')]
    for i in tokens:
        if len(i) > 0:
            if i[:1] == "<":
                i = "1-%s" % (i[1:])
        try:
            # typically tokens are plain old integers
            selection.append(int(i))
        except:
            # if not, then it might be a range
            try:
                token = [int(k.strip()) for k in i.split('-')]
                if len(token) > 1:
                    token.sort()
                    # we have items seperated by a dash
                    # try to build a valid range
                    first = token[0]
                    last  = token[-1]
                    for x in range(first, last+1):
                        selection.append(x)
            except:
                # not an int and not a range...
                invalid.append(i)
    # Report invalid tokens before returning valid selection
    if len(invalid) > 0:
        print("Invalid set: " + str(invalid))
        sys.exit(2)
    return selection


def get_platform_id():
    # ask the os for platform information
    uname = os.uname()
    
    # combine to form the platform identification
    return '.'.join((uname[0], uname[2], uname[4]))
    

# @todo this function is not used, remove it?
def get_processor_count():
    # ok, lets get some operating system info
    uname = os.uname()[0].lower()
            
    if uname == 'linux':
        # open the system file and read the lines
        nstr = sum(l.strip().replace('\t','').split(':')[0] == 'core id'
                   for l in file_readlines('/proc/cpuinfo'))
            
    elif uname == 'darwin':
        nstr = subprocess.Popen(['sysctl','-n','hw.ncpu'],stdout=subprocess.PIPE).communicate()[0];
    else:
        raise UtilsException('Unrecognized/Unsupported operating system');  
    
    # try to turn the process response into an integer
    try:
        num_cpu = int(nstr)
    except:
        # nothing else we can do here
        return None
        
    # that's all folks
    # return the number of PHYSICAL CORES, not the logical number (usually double)
    return num_cpu/2
    
    
def human_readable_time(secs):
    
    # start with work time in seconds
    time = secs
    unit = 'secs'
    
    # make human readable work time with units
    if 60 < time < 3600:
        time = time / 60.0
        unit = 'mins'
    elif time > 3600:
        time = time / 3600.0
        unit = 'hours'
        
    return time, unit


def fix_gps_week(file_path):
    
    # example:  g017321.snx.gz --> g0107321.snx.gz
    
    # extract the full file name
    path,full_file_name = os.path.split(file_path);    
    
    # init 
    file_name = full_file_name
    file_ext  = ''
    ext       = None
    
    # remove all file extensions
    while ext != '':
        file_name, ext = os.path.splitext(file_name)
        file_ext       = ext + file_ext
    
    # if the name is short 1 character then add zero
    if len(file_name) == 7:
        file_name = file_name[0:3]+'0'+file_name[3:]
    
    # reconstruct file path
    return  os.path.join(path,file_name+file_ext);


def split_string(str, limit, sep=" "):
    words = str.split()
    if max(list(map(len, words))) > limit:
        raise ValueError("limit is too small")
    res, part, others = [], words[0], words[1:]
    for word in others:
        if len(sep)+len(word) > limit-len(part):
            res.append(part)
            part = word
        else:
            part += sep+word
    if part:
        res.append(part)
    return res


def indent(text, amount, ch=' '):
    padding = amount * ch
    return ''.join(padding + line for line in text.splitlines(True))


# python 3 unpack_from returns bytes instead of strings
def struct_unpack(fs, data):
    return [(f.decode('utf-8', 'ignore') if isinstance(f, (bytes, bytearray)) else f)
            for f in fs.unpack_from(bytes(data, 'utf-8'))]


# python 3 zlib.crc32 requires bytes instead of strings
# also returns a positive int (ints are bignums on python 3)
def crc32(s):
    x = zlib_crc32(bytes(s, 'utf-8'))
    return x - ((x & 0x80000000) << 1)


# Text files

def file_open(path, mode='r'):
    return open(path, mode+'t', encoding='utf-8', errors='ignore')


def file_write(path, data):
    with file_open(path, 'w') as f:
        f.write(data)


def file_append(path, data):
    with file_open(path, 'a') as f:
        f.write(data)


def file_readlines(path):
    with file_open(path) as f:
        return f.readlines()


def file_read_all(path):
    with file_open(path) as f:
        return f.read()


def file_try_remove(path):
    try:
        os.remove(path)
        return True
    except:
        return False


def dir_try_remove(path, recursive=False):
    try:
        if recursive:
            shutil.rmtree(path)
        else:
            os.rmdir(path)
        return True
    except:
        return False

    
def chmod_exec(path):
    # chmod +x path
    f = Path(path)
    f.chmod(f.stat().st_mode | stat.S_IEXEC)


# A custom json converter is needed to fix this exception:
# TypeError: Object of type 'int64' is not JSON serializable
# See https://github.com/automl/SMAC3/issues/453
def json_converter(obj):
    if isinstance(obj, numpy.integer):
        return int(obj)
    elif isinstance(obj, numpy.floating):
        return float(obj)
    elif isinstance(obj, numpy.ndarray):
        return obj.tolist()
        

def create_empty_cfg():
    """
    function to create an empty cfg file with all the parts that are needed
    """
    cfg = """[postgres]
# information to connect to the database (self explanatory)
# replace the keywords in []
hostname = [fqdm]
username = [user]
password = [pass]
database = [gnss_data]

# keys for brdc and sp3 tanks
# $year, $doy, $month, $day, $gpsweek, $gpswkday
#
[archive]
# absolute location of the rinex archive
path = [absolute_path]
repository = [absolute_path]

# parallel execution of certain tasks. If set to false, everything runs in series.
parallel = True

# absolute location of the broadcast orbits, can use keywords declared above
#brdc = [absolute_path]
brdc = [absolute_path]

# absolute location of the sp3 orbits
sp3 = [absolute_path]

# orbit center to use for processing. Separate by commas to try more than one.
sp3_ac = IGS
# precedence of orbital reprocessing campaign
sp3_cs = R03,R02,R01,OPS
# precedence of orbital solution types
sp3_st = FIN,SNX,RAP

[otl]
# location of grdtab to compute OTL
grdtab = [absolute_path]/gamit/gamit/bin/grdtab
# location of the grid to be used by grdtab
otlgrid = [absolute_path]/gamit/tables/otl.grid

[ppp]
ppp_path = [absolute_path]/PPP_NRCAN
ppp_exe = [absolute_path]/PPP_NRCAN/source/ppp34613
# ppp_remote_local are the locations, remote and local on each node, where the PPP software lives
institution = [institution]
info = [Address, zip code, etc]
# comma separated frames, defined with time interval (see below)
frames = IGb08, IGS14
IGb08 = 1992_1, 2017_28
IGS14 = 2017_29,
atx = /example/igs08_1930.atx, /example/igs08_1930.atx
"""

    file_write('gnss_data.cfg', cfg)


# The 'fqdn' stored in the db is really fqdn + [:port]
def fqdn_parse(fqdn, default_port=None):
    if ':' in fqdn:
        fqdn, port = fqdn.split(':')
        return fqdn, int(port[1])
    else:
        return fqdn, default_port


def plot_rinex_completion(cnn, NetworkCode, StationCode, landscape=False):

    import matplotlib.pyplot as plt

    # find the available data
    rinex = numpy.array(cnn.query_float("""
    SELECT "ObservationYear", "ObservationDOY",
    "Completion" FROM rinex_proc WHERE
    "NetworkCode" = '%s' AND "StationCode" = '%s'""" % (NetworkCode,
                                                        StationCode)))

    if landscape:
        fig, ax = plt.subplots(figsize=(25, 10))
        x = 1
        y = 0
    else:
        fig, ax = plt.subplots(figsize=(10, 25))
        x = 0
        y = 1

    fig.tight_layout(pad=5)
    ax.set_title('RINEX and missing data for %s.%s'
                 % (NetworkCode, StationCode))

    if rinex.size:
        # create a continuous vector for missing data
        md = numpy.arange(1, 367)
        my = numpy.unique(rinex[:, 0])
        for yr in my:

            if landscape:
                ax.plot(md, numpy.repeat(yr, 366), 'o', fillstyle='none',
                        color='silver', markersize=4, linewidth=0.1)
            else:
                ax.plot(numpy.repeat(yr, 366), md, 'o', fillstyle='none',
                        color='silver', markersize=4, linewidth=0.1)

        ax.scatter(rinex[:, x], rinex[:, y],
                   c=['tab:blue' if c >= 0.5 else 'tab:orange'
                      for c in rinex[:, 2]], s=10, zorder=10)

        ax.tick_params(top=True, labeltop=True, labelleft=True,
                       labelright=True, left=True, right=True)
        if landscape:
            plt.yticks(numpy.arange(my.min(), my.max() + 1, step=1))  # Set label locations.
        else:
            plt.xticks(numpy.arange(my.min(), my.max()+1, step=1),
                       rotation='vertical')  # Set label locations.

    ax.grid(True)
    ax.set_axisbelow(True)

    if landscape:
        plt.xlim([0, 367])
        plt.xticks(numpy.arange(0, 368, step=5))  # Set label locations.

        ax.set_xlabel('DOYs')
        ax.set_ylabel('Years')
    else:
        plt.ylim([0, 367])
        plt.yticks(numpy.arange(0, 368, step=5))  # Set label locations.

        ax.set_ylabel('DOYs')
        ax.set_xlabel('Years')

    figfile = io.BytesIO()

    try:
        plt.savefig(figfile, format='png')
        # plt.show()
        figfile.seek(0)  # rewind to beginning of file

        figdata_png = base64.b64encode(figfile.getvalue()).decode()
    except Exception:
        # either no rinex or no station info
        figdata_png = ''

    plt.close()

    return figdata_png


def import_blq(blq_str, NetworkCode=None, StationCode=None):

    if blq_str[0:2] != '$$':
        raise UtilsException('Input string does not appear to be in BLQ format!')

    # header as defined in the new version of the holt.oso.chalmers.se service
    header = """$$ Ocean loading displacement
$$
$$ OTL provider: http://holt.oso.chalmers.se/loading/
$$ Created by Scherneck & Bos
$$
$$ WARNING: All your longitudes were within -90 to +90 degrees
$$ There is a risk that longitude and latitude were swapped
$$ Please verify for yourself that this has not been the case
$$
$$ COLUMN ORDER:  M2  S2  N2  K2  K1  O1  P1  Q1  MF  MM SSA
$$
$$ ROW ORDER:
$$ AMPLITUDES (m)
$$   RADIAL
$$   TANGENTL    EW
$$   TANGENTL    NS
$$ PHASES (degrees)
$$   RADIAL
$$   TANGENTL    EW
$$   TANGENTL    NS
$$
$$ Displacement is defined positive in upwards, South and West direction.
$$ The phase lag is relative to Greenwich and lags positive. The PREM
$$ Green's function is used. The deficit of tidal water mass in the tide
$$ model has been corrected by subtracting a uniform layer of water with
$$ a certain phase lag globally.
$$
$$ CMC:  NO (corr.tide centre of mass)
$$
$$ A constant seawater density of 1030 kg/m^3 is used.
$$
$$ A thin tidal layer is subtracted to conserve water mass.
$$
$$ FES2014b: m2 s2 n2 k2 k1 o1
$$ FES2014b: p1 q1 Mf Mm Ssa
$$
$$ END HEADER
$$"""
    # it's BLQ alright
    pattern = re.compile(r'(?m)(^\s{2}(\w{3}_\w{4})[\s\S]*?^\$\$(?=\s*(?:END TABLE)?$))', re.MULTILINE)
    matches = pattern.findall(blq_str)

    # create a list with the matches
    otl_records = []
    for match in matches:
        net, stn = match[1].split('_')
        # add the match to the list if none requested or if a specific station was requested
        if NetworkCode is None or StationCode is None or (net == NetworkCode and stn == StationCode):
            otl = header + '\n' + match[0].replace('$$ ' + match[1], '$$ %-8s' % stn).replace(match[1], stn)
            otl_records.append({'StationCode': stn,
                                'NetworkCode': net,
                                'otl': otl})

    return otl_records
