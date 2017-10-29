
import os, re, subprocess, sys, pyDate, numpy


class UtilsException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)


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

    if '.' in arg:
        date = pyDate.Date(year=arg.split('.')[0], doy=arg.split('.')[1])
    else:
        date = pyDate.Date(year=arg.split('/')[0], month=arg.split('/')[1], day=arg.split('/')[2])

    return date


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
        year = int(year);
    except:
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
        doy = int(doy);
    except:
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
        num_cpu = int(nstr);
    except:
        # nothing else we can do here
        num_cpu = None;
        
    # that's all folks
    # return the number of PHYSICAL CORES, not the logical number (usually double)
    return num_cpu/2;
    
    
def human_readable_time(secs):
    
    # start with work time in seconds
    unit = 'secs'; time = secs;
    
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
    
    
        