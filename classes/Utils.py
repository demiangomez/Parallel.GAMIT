
import os, re, subprocess, sys, pyDate, numpy, filecmp, argparse

class UtilsException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

def required_length(nmin,nmax):
    class RequiredLength(argparse.Action):
        def __call__(self, parser, args, values, option_string=None):
            if not nmin<=len(values)<=nmax:
                msg='argument "{f}" requires between {nmin} and {nmax} arguments'.format(
                    f=self.dest,nmin=nmin,nmax=nmax)
                raise argparse.ArgumentTypeError(msg)
            setattr(args, self.dest, values)
    return RequiredLength

def parse_crinex_rinex_filename(filename):
    # parse a crinex filename
    sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([d]\.[Z])$', filename)

    if sfile:
        return sfile[0]
    else:
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([o])$', filename)

        if sfile:
            return sfile[0]
        else:
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

    sessions = [0,1,2,3,4,5,6,7,8,9] + [chr(x) for x in xrange(ord('a'), ord('z')+1)]

    path = os.path.dirname(filename)
    filename = os.path.basename(filename)
    fileparts = parse_crinex_rinex_filename(filename)

    if not fileparts:
        raise ValueError('Invalid file naming convention: {}'.format(filename))

    # Check if there's a counter in the filename already - if not, start a new
    # counter at 0.
    value = 0

    filename = os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(), int(fileparts[1]), sessions[value], int(fileparts[3]), fileparts[4]))

    # The counter is just an integer, so we can increment it indefinitely.
    while True:
        if value == 0:
            yield filename

        value += 1

        if value == len(sessions):
            raise ValueError('Maximum number of sessions reached: %s%03i%s.%02i%s' % (fileparts[0].lower(), int(fileparts[1]), sessions[value-1], int(fileparts[3]), fileparts[4]))

        yield os.path.join(path, '%s%03i%s.%02i%s' % (fileparts[0].lower(), int(fileparts[1]), sessions[value], int(fileparts[3]), fileparts[4]))


def copyfile(src, dst):
    """
    Copies a file from path src to path dst.
    If a file already exists at dst, it will not be overwritten, but:
     * If it is the same as the source file, do nothing
     * If it is different to the source file, pick a new name for the copy that
       is distinct and unused, then copy the file there.
    Returns the path to the copy.
    """
    if not os.path.exists(src):
        raise ValueError('Source file does not exist: {}'.format(src))

    # make the folders if they don't exist
    # careful! racing condition between different workers
    try:
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
    except OSError:
        # some other process created the folder an instant before
        pass

    # Keep trying to copy the file until it works
    dst_gen = _increment_filename(dst)

    while True:

        dst = next(dst_gen)

        # Check if there is a file at the destination location
        if os.path.exists(dst):

            # If the namesake is the same as the source file, then we don't
            # need to do anything else.
            if filecmp.cmp(src, dst):
                return dst

        else:

            # If there is no file at the destination, then we attempt to write
            # to it. There is a risk of a race condition here: if a file
            # suddenly pops into existence after the `if os.path.exists()`
            # check, then writing to it risks overwriting this new file.
            #
            # We write by transferring bytes using os.open(). Using the O_EXCL
            # flag on the dst file descriptor will cause an OSError to be
            # raised if the file pops into existence; the O_EXLOCK stops
            # anybody else writing to the dst file while we're using it.
            try:
                src_fd = os.open(src, os.O_RDONLY)
                dst_fd = os.open(dst, os.O_WRONLY | os.O_EXCL | os.O_CREAT)

                # Read 100 bytes at a time, and copy them from src to dst
                while True:
                    data = os.read(src_fd, 100)
                    os.write(dst_fd, data)

                    # When there are no more bytes to read from the source
                    # file, 'data' will be an empty string
                    if not data:
                        break

                os.close(src_fd)
                os.close(dst_fd)
                # If we get to this point, then the write has succeeded
                return dst

            # An OSError errno 17 is what happens if a file pops into existence
            # at dst, so we print an error and try to copy to a new location.
            # Any other exception is unexpected and should be raised as normal.
            except OSError as e:
                if e.errno != 17 or e.strerror != 'File exists':
                    raise


def move(src, dst):
    """
    Moves a file from path src to path dst.
    If a file already exists at dst, it will not be overwritten, but:
     * If it is the same as the source file, do nothing
     * If it is different to the source file, pick a new name for the copy that
       is distinct and unused, then copy the file there.
    Returns the path to the new file.
    """
    dst = copyfile(src, dst)
    os.remove(src)
    return dst


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

    b = numpy.sqrt(asq * (1 - esq))
    bsq = numpy.power(b, 2)

    ep = numpy.sqrt((asq - bsq) / bsq)
    p = numpy.sqrt(numpy.power(x, 2) + numpy.power(y, 2))
    th = numpy.arctan2(a * z, b * p)

    lon = numpy.arctan2(y, x)
    lat = numpy.arctan2((z + numpy.power(ep, 2) * b * numpy.power(numpy.sin(th), 3)),
                     (p - esq * a * numpy.power(numpy.cos(th), 3)))
    N = a / (numpy.sqrt(1 - esq * numpy.power(numpy.sin(lat), 2)))
    alt = p / numpy.cos(lat) - N

    lon = lon * 180 / numpy.pi
    lat = lat * 180 / numpy.pi

    return numpy.array([lat]), numpy.array([lon]), numpy.array([alt])


def process_date(arg):

    dates = [pyDate.Date(year=1980, doy=1), pyDate.Date(year=2100, doy=1)]

    if arg:
        for i, arg in enumerate(arg):
            try:
                if '.' in arg:
                    dates[i] = pyDate.Date(year=arg.split('.')[0], doy=arg.split('.')[1])
                else:
                    dates[i] = pyDate.Date(year=arg.split('/')[0], month=arg.split('/')[1], day=arg.split('/')[2])
            except Exception as e:
                raise ValueError('Error while reading the date start/end parameters: ' + str(e))

    return dates


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

def process_stnlist(cnn, stnlist_in):

    stnlist = []

    if 'all' in stnlist_in:
        # plot all stations
        rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"')

        for rstn in rs.dictresult():
            stnlist += [{'NetworkCode': rstn['NetworkCode'], 'StationCode': rstn['StationCode']}]

    else:
        for stn in stnlist_in:
            if '.' in stn:
                # a net.stnm given
                if 'all' in stn.split('.')[1]:
                    # all stations from a network
                    rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (stn.split('.')[0]))

                else:
                    rs = cnn.query(
                        'SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (stn.split('.')[0], stn.split('.')[1]))

            else:
                # just a station name
                rs = cnn.query(
                    'SELECT * FROM stations WHERE "StationCode" = \'%s\' ORDER BY "NetworkCode", "StationCode"' % (stn))

            for rstn in rs.dictresult():
                stnlist += [{'NetworkCode': rstn['NetworkCode'], 'StationCode': rstn['StationCode']}]

    return stnlist

def get_norm_year_str(year):
    
    # mk 4 digit year
    try:
        year = int(year)
    except Exception:
        raise UtilsException('must provide a positive integer year YY or YYYY');
    
    # defensively, make sure that the year is positive
    if year < 0:
        raise UtilsException('must provide a positive integer year YY or YYYY');
    
    if 80 <= year <= 99:
        year += 1900
    elif 0 <= year < 80:
        year += 2000        

    return str(year)


def get_norm_doy_str(doy):
    
    try:
        doy = int(doy)
    except Exception:
        raise UtilsException('must provide an integer day of year'); 
       
    # create string version up fround
    doy = str(doy);
       
    # mk 3 diit doy
    if len(doy) == 1:
        doy = "00"+doy
    elif len(doy) == 2:
        doy = "0"+doy
    return doy


def parse_stnId(stnId):
    
    # parse the station id
    parts = re.split('\.',stnId);
    
    # make sure at least two components here
    if len(parts) < 2:
        raise UtilsException('invalid station id: '+stnId);
    
    # get station name space
    ns = '.'.join(parts[:-1]);
    
    # get the station code
    code = parts[-1];
    
    # that's it
    return ns,code;


def get_platform_id():
    
    # ask the os for platform information
    uname = os.uname();
    
    # combine to form the platform identification
    return '.'.join((uname[0],uname[2],uname[4]));
    
    
def get_processor_count():
    
    # init to null
    num_cpu = None;
    
    # ok, lets get some operating system info
    uname = os.uname();
            
    if uname[0].lower() == 'linux':
        
        # open the system file and read the lines
        with open('/proc/cpuinfo') as fid:
            nstr = sum([ l.strip().replace('\t','').split(':')[0] == 'core id' for l in fid.readlines()]);
            
    elif uname[0].lower() == 'darwin':
        nstr = subprocess.Popen(['sysctl','-n','hw.ncpu'],stdout=subprocess.PIPE).communicate()[0];
    else:
        raise UtilsException('Unrecognized/Unsupported operating system');  
    
    # try to turn the process response into an integer
    try:
        num_cpu = int(nstr)
    except Exception:
        # nothing else we can do here
        num_cpu = None
        
    # that's all folks
    # return the number of PHYSICAL CORES, not the logical number (usually double)
    return num_cpu/2
    
    
def human_readable_time(secs):
    
    # start with work time in seconds
    unit = 'secs'; time = secs
    
    # make human readable work time with units
    if time > 60 and time < 3600:
        time = time / 60.0; unit = 'mins'
    elif time > 3600:
        time = time /3600.0; unit = 'hours';
        
    return time,unit

def fix_gps_week(file_path):
    
    # example:  g017321.snx.gz --> g0107321.snx.gz
    
    # extract the full file name
    path,full_file_name = os.path.split(file_path);    
    
    # init 
    file_name = full_file_name;  file_ext = ''; ext = None;
    
    # remove all file extensions
    while ext != '':
        file_name, ext = os.path.splitext(file_name);
        file_ext = ext + file_ext;
    
    # if the name is short 1 character then add zero
    if len(file_name) == 7:
        file_name = file_name[0:3]+'0'+file_name[3:];
    
    # reconstruct file path
    return  os.path.join(path,file_name+file_ext);
    
if __name__ == '__main__':
    
    file = '/some/path/g0107321.snx.gz';
    print file, fix_gps_week(file)
    
    
        