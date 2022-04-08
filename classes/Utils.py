
import os
import re
import subprocess
import sys
import filecmp
import argparse
import stat
import shutil
from datetime import datetime
from zlib import crc32 as zlib_crc32
from pathlib import Path


# deps
import numpy

# app
import pyRinexName
import pyDate


class UtilsException(Exception):
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return str(self.value)


def get_field_or_attr(obj, f):
    try:
        return obj[f]
    except:
        return getattr(obj, f)

def stationID(s):
    return "%s.%s" % (get_field_or_attr(s, 'NetworkCode'),
                      get_field_or_attr(s, 'StationCode'))

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


def required_length(nmin,nmax):
    class RequiredLength(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not nmin <= len(values) <= nmax:
                msg = 'argument "{f}" requires between {nmin} and {nmax} arguments'.format(
                       f = self.dest, nmin = nmin, nmax = nmax)
                raise argparse.ArgumentTypeError(msg)

            setattr(args, self.dest, values)

    return RequiredLength


def parse_crinex_rinex_filename(filename):
    # parse a crinex filename
    sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([d]\.[Z])$', filename)
    if sfile:
        return sfile[0]

    sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([o])$', filename)
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

    sessions = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] + [chr(x) for x in range(ord('a'), ord('z')+1)]

    path      = os.path.dirname(filename)
    filename  = os.path.basename(filename)
    fileparts = parse_crinex_rinex_filename(filename)

    if not fileparts:
        raise ValueError('Invalid file naming convention: {}'.format(filename))

    # Check if there's a counter in the filename already - if not, start a new
    # counter at 0.
    value = 0

    filename = os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(),
                                                       int(fileparts[1]),
                                                       sessions[value],
                                                       int(fileparts[3]),
                                                       fileparts[4]))

    # The counter is just an integer, so we can increment it indefinitely.
    while True:
        if value == 0:
            yield filename

        value += 1

        if value == len(sessions):
            raise ValueError('Maximum number of sessions reached: %s%03i%s.%02i%s'
                             % (fileparts[0].lower(),
                                int(fileparts[1]),
                                sessions[value-1],
                                int(fileparts[3]),
                                fileparts[4]))

        yield os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(),
                                                      int(fileparts[1]),
                                                      sessions[value],
                                                      int(fileparts[3]),
                                                      fileparts[4]))


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

    x = float(ecefArr[0])
    y = float(ecefArr[1])
    z = float(ecefArr[2])

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

    return numpy.array([lat]), numpy.array([lon]), numpy.array([alt])


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

    if len(stnlist_in) == 1 and os.path.isfile(stnlist_in[0]):
        print(' >> Station list read from file: ' + stnlist_in[0])
        stnlist_in = [line.strip() for line in file_readlines(stnlist_in[0])]

    stnlist = []

    if len(stnlist_in) == 1 and stnlist_in[0] == 'all':
        # all stations
        rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' '
                       'ORDER BY "NetworkCode", "StationCode"')

        stnlist += [{'NetworkCode': rstn['NetworkCode'],
                     'StationCode': rstn['StationCode']}
                    for rstn in rs.dictresult() ]
    else:
        for stn in stnlist_in:
            rs = None
            if '.' in stn and '-' not in stn:
                # a net.stnm given
                if stn.split('.')[1] == 'all':
                    # all stations from a network
                    rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND '
                                   '"NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"'
                                   % (stn.split('.')[0]))

                else:
                    rs = cnn.query(
                        'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND "NetworkCode" = \'%s\' '
                        'AND "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"'
                        % (stn.split('.')[0], stn.split('.')[1]))

            elif '.' not in stn and '-' not in stn:
                # just a station name
                rs = cnn.query(
                    'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND '
                    '"StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % stn)

            if rs is not None:
                for rstn in rs.dictresult():
                    if {'NetworkCode': rstn['NetworkCode'],
                        'StationCode': rstn['StationCode']} not in stnlist:
                        stnlist.append({'NetworkCode': rstn['NetworkCode'],
                                        'StationCode': rstn['StationCode']})

    # deal with station removals (-)
    for stn in [stn.replace('-', '').lower() for stn in stnlist_in if '-' in stn]:
        # if netcode not given, remove everybody with that station code
        if '.' in stn:
            stnlist = [stnl for stnl in stnlist if stationID(stnl) != stn]
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
    if time > 60 and time < 3600:
        time = time / 60.0
        unit = 'mins'
    elif time > 3600:
        time = time / 3600.0
        unit = 'hours';
        
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
    return x - ((x & 0x80000000) <<1)


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
        
