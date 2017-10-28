"""
Project:
Date: 2/21/17 3:34 PM
Author: Demian D. Gomez

Python wrapper for PPP. It runs the NRCAN PPP and loads the information from the summary file. Can be used without a
database connection, except for PPPSpatialCheck

"""

import pyRinex
import pyRunWithRetry
import pySp3
import pyEOP
import pyClk
import os
import uuid
from shutil import copyfile
from shutil import rmtree
import numpy
from math import isnan
import pyEvents

def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

class pyRunPPPException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error')
    def __str__(self):
        return str(self.value)

class PPPSpatialCheck():

    def __init__(self, lat=None, lon=None, h=None):

        self.lat   = lat
        self.lon   = lon
        self.h     = h

        return

    def verify_spatial_coherence(self, cnn, StationCode, search_in_new=False):
        # checks the spatial coherence of the resulting coordinate
        # will not make any decisions, just output the candidates
        # if ambiguities are found, the rinex StationCode is used to solve them
        # third argument is used to return a list with the closest station/s if no match is found
        # or if we had to disambiguate using station name

        if not search_in_new:
            where_clause = 'WHERE "NetworkCode" not like \'?%%\''
        else:
            where_clause = ''

        for dist in [100, 500, 1000, 2000, 5000]:
            rs = cnn.query("""
                            SELECT * FROM
                                (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * cos(radians(%.8f)) * sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
                                    FROM stations %s) as DD
                                WHERE distance <= %f
                            """ % (
            self.lat[0], self.lat[0], self.lon[0], where_clause, dist))  # DO NOT RETURN RESULTS OF A STATION WITH NetworkCode = '?%'

            stn = rs.dictresult()

            if rs.ntuples() == 1:
                # found a match
                return True, stn[0], []

            elif rs.ntuples() > 1:
                # this is most likely a station that got moved a few meters and renamed
                # or a station that just got renamed.
                # disambiguation might be possible using the name of the station
                min_stn = [stni for stni in stn if stni['distance'] == min([x['distance'] for x in stn])][0]

                if min_stn['StationCode'] == StationCode:
                    # the minimum distance if to a station with same name, we are good:
                    # does the name match the closest station to this solution? yes
                    return True, min_stn, []
                else:
                    stn_match = [stni for stni in stn if stni['StationCode'] == StationCode]

                    if len(stn_match) > 0:
                        # The stationcode is not the closest one (maybe screwy PPP solution?),
                        # but its in the list and return the closest one in the third arg
                        if len(stn_match) == 1 and abs(stn_match[0]['distance'] - min_stn['distance']) < 1:
                            # two stations, A and B, rinex belongs by station code to A but distance says it's from
                            # B and distance difference is < 1 m.
                            # This is a station rename. The solution is closer to B, but just because of noise
                            # When the difference between distances (rinex - A) - (rinex - B) is < 1 m,
                            # we can safely assume that the station was renamed.
                            # So we stick to the name the rinex came in with
                            return True, stn_match[0], []

                        elif len(stn_match) == 1 and abs(stn_match[0]['distance'] - min_stn['distance']) >= 1:
                            # two stations, A and B, rinex belongs by station code to A but distance says it's from
                            # B and distance difference is >= 1 m.
                            # We can still assume that the solution is from A, but return min_stn for the user to decide
                            return True, stn_match[0], min_stn

                        elif len(stn_match) > 1:
                            # more than one station with this station code (very rare)
                            # but... gaucho precavido vale por dos
                            # return all rows of stn_match
                            return False, stn_match, []

                    else:
                        # could not find a unique stni['StationCode'] = argin stationcode within X m
                        # return false and the possible candidates
                        return False, stn, []


        # the for loop ended. No match at all found
        # get the closest station and distance in km to help the caller function
        rs = cnn.query("""
                    SELECT * FROM
                        (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * cos(radians(%.8f)) * sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
                            FROM stations %s) as DD ORDER BY distance
                    """ % (self.lat[0], self.lat[0], self.lon[0], where_clause))

        stn = rs.dictresult()

        return False, [], stn[0]


class RunPPP(PPPSpatialCheck):
    def __init__(self,rinexobj,otl_coeff,options,sp3types,sp3altrn,antenna_height,strict=True,apply_met=True,kinematic=False,hash=0):
        assert isinstance(rinexobj,pyRinex.ReadRinex)

        PPPSpatialCheck.__init__(self)

        self.rinex = rinexobj
        self.antH = antenna_height
        self.ppp_path = options['ppp_path']
        self.ppp = options['ppp_exe']
        self.options = options
        self.kinematic = kinematic

        self.frame     = None
        self.x         = None
        self.y         = None
        self.z         = None
        self.lat       = None
        self.lon       = None
        self.h         = None
        self.sigmax    = None
        self.sigmay    = None
        self.sigmaz    = None
        self.sigmaxy   = None
        self.sigmaxz   = None
        self.sigmayz   = None
        self.hash      = hash

        self.sp3altrn  = sp3altrn
        self.sp3types  = sp3types
        self.otl_coeff = otl_coeff
        self.strict    = strict
        self.apply_met = apply_met
        self.out       = ''
        self.summary   = ''
        self.pos       = ''

        fieldnames = ['NetworkCode', 'StationCode', 'X', 'Y', 'Z', 'Year', 'DOY', 'ReferenceFrame', 'sigmax', 'sigmay',
                      'sigmaz', 'sigmaxy', 'sigmaxz', 'sigmayz', 'hash']

        self.record = dict.fromkeys(fieldnames)

        if os.path.isfile(self.rinex.rinex_path):

            self.rootdir = os.path.join('production', 'ppp')
            # generate a unique id for this instance
            self.rootdir = os.path.join(self.rootdir, str(uuid.uuid4()))

            try:
                # create a production folder to analyze the rinex file
                if not os.path.exists(self.rootdir):
                    os.makedirs(self.rootdir)
                    os.makedirs(os.path.join(self.rootdir,'orbits'))
            except Exception as excep:
                # could not create production dir! FATAL
                raise

            self.config_session(self.options, sp3types, sp3altrn)

        else:
            raise pyRunPPPException('The file ' + self.rinex.rinex_path + ' could not be found. PPP was not executed.')

        return

    def config_session(self, options, sp3types, sp3altrn):

        # make a local copy of the rinex file
        # decimate the rinex file if the interval is < 15 sec.
        if self.rinex.interval < 15:
            self.rinex.decimate(30)

        copyfile(self.rinex.rinex_path, os.path.join(self.rootdir, self.rinex.rinex))

        try:
            orbit1 = pySp3.GetSp3Orbits(options['sp3'],self.rinex.date,sp3types,os.path.join(self.rootdir,'orbits'),True)
            orbit2 = pySp3.GetSp3Orbits(options['sp3'],self.rinex.date+1,sp3types,os.path.join(self.rootdir,'orbits'),True)
            clock1 = pyClk.GetClkFile(options['sp3'],self.rinex.date,sp3types,os.path.join(self.rootdir,'orbits'),True)
            clock2 = pyClk.GetClkFile(options['sp3'],self.rinex.date+1,sp3types,os.path.join(self.rootdir,'orbits'),True)
            eop_file = pyEOP.GetEOP(options['sp3'],self.rinex.date,sp3types,self.rootdir)
        except pySp3.pySp3Exception:
            if sp3altrn:
                # maybe orbit file was not found. Switch to alternative orbits
                orbit1 = pySp3.GetSp3Orbits(options['sp3'], self.rinex.date, sp3altrn, os.path.join(self.rootdir, 'orbits'),True)
                orbit2 = pySp3.GetSp3Orbits(options['sp3'], self.rinex.date + 1, sp3altrn, os.path.join(self.rootdir, 'orbits'), True)
                clock1 = pyClk.GetClkFile(options['sp3'], self.rinex.date, sp3altrn, os.path.join(self.rootdir, 'orbits'), True)
                clock2 = pyClk.GetClkFile(options['sp3'], self.rinex.date + 1, sp3altrn,os.path.join(self.rootdir, 'orbits'), True)
                eop_file = pyEOP.GetEOP(options['sp3'], self.rinex.date, sp3altrn, self.rootdir)
            else:
                raise
        except:
            raise

        otl_file = open(os.path.join(self.rootdir, self.rinex.StationCode + '.olc'), 'w')
        otl_file.write(self.otl_coeff)
        otl_file.close()

        # create the def file
        def_file = open(os.path.join(self.rootdir,'gpsppp.def'),'w')

        def_file_cont = \
        """'LNG' 'ENGLISH'
'TRF' 'gpsppp.trf'
'SVB' 'gpsppp.svb_gps_yrly'
'PCV' '%s'
'FLT' 'gpsppp.flt'
'OLC' '%s.olc'
'MET' 'gpsppp.met'
'ERP' '%s'
'GSD' '%s'
'GSD' '%s'
        """ % (options['atx'].split('/')[-1],self.rinex.StationCode, eop_file.eop_filename, options['institution'], options['info'])

        def_file.write(def_file_cont)
        def_file.close()

        cmd_file = open(os.path.join(self.rootdir,'commands.cmd'),'w')

        if self.kinematic:
            kin = '2'
        else:
            kin = '1'

        cmd_file_cont = \
        """' UT DAYS OBSERVED                      (1-45)'               1
' USER DYNAMICS         (1=STATIC,2=KINEMATIC)'               %s
' OBSERVATION TO PROCESS         (1=COD,2=C&P)'               2
' FREQUENCY TO PROCESS        (1=L1,2=L2,3=L3)'               3
' SATELLITE EPHEMERIS INPUT     (1=BRD ,2=SP3)'               2
' SATELLITE PRODUCT (1=NO,2=Prc,3=RTCA,4=RTCM)'               2
' SATELLITE CLOCK INTERPOLATION   (1=NO,2=YES)'               1
' IONOSPHERIC GRID INPUT          (1=NO,2=YES)'               1
' SOLVE STATION COORDINATES       (1=NO,2=YES)'               2
' SOLVE TROP. (1=NO,2-5=RW MM/HR) (+100=grad) '             105
' BACKWARD SUBSTITUTION           (1=NO,2=YES)'               1
' REFERENCE SYSTEM            (1=NAD83,2=ITRF)'               2
' COORDINATE SYSTEM(1=ELLIPSOIDAL,2=CARTESIAN)'               2
' A-PRIORI PSEUDORANGE SIGMA               (m)'           2.000
' A-PRIORI CARRIER PHASE SIGMA             (m)'            .015
' LATITUDE  (ddmmss.sss,+N) or ECEF X      (m)'          0.0000
' LONGITUDE (ddmmss.sss,+E) or ECEF Y      (m)'          0.0000
' HEIGHT (m)                or ECEF Z      (m)'          0.0000
' ANTENNA HEIGHT                           (m)'          %s
' CUTOFF ELEVATION                       (deg)'          10.000
' GDOP CUTOFF                                 '          20.000
        """ % (kin, self.antH)

        cmd_file.write(cmd_file_cont)
        cmd_file.close()

        inp_file = open(os.path.join(self.rootdir, 'input.inp'), 'w')
        inp_file_cont = \
            """%s
commands.cmd
0 0
0 0
orbits/%s
orbits/%s
orbits/%s
orbits/%s
            """ % (self.rinex.rinex, orbit1.sp3_filename, clock1.clk_filename, orbit2.sp3_filename, clock2.clk_filename)
        inp_file.write(inp_file_cont)
        inp_file.close()

        #run_script = open(os.path.join(self.rootdir, 'run.sh'), 'w')
        #run_script.write('#!/bin/bash\n')
        #run_script.write(self.ppp + ' < input.inp\n')
        #run_script.close()

        # prepare all the files required to run PPP
        try:
            if self.apply_met:
                copyfile(os.path.join(self.ppp_path, 'gpsppp.met'), os.path.join(self.rootdir, 'gpsppp.met'))

            copyfile(os.path.join(self.ppp_path, 'gpsppp.stc'), os.path.join(self.rootdir, 'gpsppp.stc'))
            copyfile(os.path.join(self.ppp_path, 'gpsppp.svb_gps_yrly'), os.path.join(self.rootdir, 'gpsppp.svb_gps_yrly'))
            copyfile(os.path.join(self.ppp_path, 'gpsppp.flt'), os.path.join(self.rootdir, 'gpsppp.flt'))
            copyfile(os.path.join(self.ppp_path, 'gpsppp.stc'), os.path.join(self.rootdir, 'gpsppp.stc'))
            copyfile(os.path.join(options['atx']), os.path.join(self.rootdir, options['atx'].split('/')[-1]))

        except:
            raise

        return

    def parse_summary(self):

        coord_est = []
        sigma_cor = []
        lcount = 0
        read_cartesian = False
        read_sigmas = False

        self.summary = ''.join(self.out)

        for line in self.out:

            if ' 3.3 Coordinate estimates' in line or lcount > 0:
                lcount += 1
                if 'CARTESIAN' in line or read_cartesian:
                    read_cartesian = True
                    coord_est.append(line.strip())
                if 'SIGMA/CORRELATIONS' in line or read_sigmas:
                    read_sigmas = True
                    read_cartesian = False
                    sigma_cor.append(line.strip())
                if 'ELLIPSOIDAL' in line:
                    break

        # read coordinates and sigmas
        for line in coord_est:
            if 'ITRF (' in line:
                # extract the RF of the solution
                self.frame = find_between(line, 'ITRF (', 'Sigma(m)').strip().replace(')', '').strip()
            if 'X (m)' in line:
                self.x = float(line.split()[3])
                self.sigmax = float(line.split()[4])
            if 'Y (m)' in line:
                self.y = float(line.split()[3])
                self.sigmay = float(line.split()[4])
            if 'Z (m)' in line:
                self.z = float(line.split()[3])
                self.sigmaz = float(line.split()[4])
                break

        # read the correlation values
        for line in sigma_cor:
            if 'X(m)' in line and 'Y(m)' not in line:
                self.sigmaxy = float(line.split()[2])
                self.sigmaxz = float(line.split()[3])
            if 'Y(m)' in line and 'X(m)' not in line:
                self.sigmayz = float(line.split()[2])

        proc_obs = 0
        reje_obs = 0
        for line in self.out:
            if ' 2.3 Antenna phase center (APC) offsets - MM             NOT AVAILABLE' in line and self.strict:
                raise pyRunPPPException('Error while running PPP: could not find the antenna and radome in antex file. Check RINEX header for formatting issues in the ANT # / TYPE field. RINEX header follows:\n' + ''.join(self.rinex.get_header()))

            if ' 2.5 Ocean loading coefficients                           NOT FOUND' in line and self.strict:
                raise  pyRunPPPException('Error while running PPP: could not find the OTL coefficients. Check RINEX header for formatting issues in the APPROX ANT POSITION field')

            if 'Number of observations processed  :' in line:
                proc_obs = float(find_between(line,'Number of observations processed  :','GPS').strip())

            if 'Number of observations rejected   :' in line:
                reje_obs = float(find_between(line,'Number of observations rejected   :','GPS').strip())

        if (proc_obs == 0 or proc_obs < reje_obs * 0.1) and self.strict:
            return False, (proc_obs,reje_obs)

        if isnan(self.x) or isnan(self.y) or isnan(self.z):
            # sometimes, the summary file comes with NaNs in the X Y Z coordinates but the pos files did actually converge
            # try to open the pos file and parse the last line in the file
            try:
                position = self.pos[-1]
                xyz = position[193:].split()
                self.x = float(xyz[0])
                self.y = float(xyz[1])
                self.z = float(xyz[2])
            except:
                return False, (None, None)

        if self.kinematic:
            # no covariance information in kinematic mode
            if isnan(self.sigmax) or isnan(self.sigmay) or isnan(self.sigmaz):
                return False, (None, None)
        else:
            if isnan(self.sigmax) or isnan(self.sigmay) or isnan(self.sigmaz) \
                    or isnan(self.sigmaxy) or isnan(self.sigmaxz) or isnan(self.sigmayz):
                return False, (None, None)

        return True, (None, None)

    def __exec_ppp__(self, raise_error=True):

        # make the script executable
        #os.system('chmod +x ' + os.path.join(self.rootdir, 'run.sh'))
        #cmd = pyRunWithRetry.RunCommand('./run.sh', 45, self.rootdir)

        cmd = pyRunWithRetry.RunCommand(self.ppp, 45, self.rootdir, 'input.inp')
        try:
            # DDG: handle the error found in PPP (happens every now and then)
            # Fortran runtime error: End of file
            for i in range(2):
                out, err = cmd.run_shell()

                if not '*END - NORMAL COMPLETION' in out:

                    if 'Fortran runtime error: End of file' in err and i == 0:
                        # error detected, try again!
                        continue

                    msg = 'PPP ended abnormally for ' + self.rinex.rinex_path + ':\n' + err
                    if raise_error:
                        raise pyRunPPPException(msg)
                    else:
                        return False, msg
                else:
                    f = open(os.path.join(self.rootdir, self.rinex.rinex[:-3] + 'sum'), 'r')
                    self.out = f.readlines()
                    f.close()

                    f = open(os.path.join(self.rootdir, self.rinex.rinex[:-3] + 'pos'), 'r')
                    self.pos = f.readlines()
                    f.close()
                    break

        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            msg = str(e)
            if raise_error:
                raise pyRunPPPException(e)
            else:
                return False, msg
        except IOError as e:
            raise pyRunPPPException(e)
        except:
            raise

        return True, ''

    def exec_ppp(self):

        sucess = False
        proc_obs = (None, None)

        if self.sp3altrn:
            for i in range(2):
                # execute PPP but do not raise an error if timed out
                result, message = self.__exec_ppp__(False)

                if result:
                    # parse the output from the summary file
                    sucess, proc_obs = self.parse_summary()

                    if sucess:
                        break
                    elif not sucess and i == 0:
                        self.config_session(self.options, self.sp3altrn, None)
                elif not result and i == 0:
                    # when a timeout happens, tries to rerun PPP using the alternative orbits
                    self.config_session(self.options, self.sp3altrn, None)
                elif not result and i == 1:
                    # execution with alternative orbits, still result = False
                    raise pyRunPPPException(message + ' - principal and alternative orbits.')
        else:
            self.__exec_ppp__(True)
            sucess, proc_obs = self.parse_summary()

        if not sucess and not proc_obs[0]:
            if self.sp3altrn:
                raise pyRunPPPException('PPP returned invalid numbers for the coordinates/sigmas of the station after trying with both principal and the alternative orbits.')
            else:
                raise pyRunPPPException('PPP returned invalid numbers for the coordinates/sigmas of the station (no alternative orbit types specified.)')
        elif not sucess and proc_obs[0]:
            if self.sp3altrn:
                raise pyRunPPPException('The processed observations (' + str(proc_obs[0]) + ') is zero or < 10 % of rejected observations (' + str(proc_obs[1]) + ')! Both principal and alternative orbits used. No coordinates were returned.')
            else:
                raise pyRunPPPException('The processed observations (' + str(proc_obs[0]) + ') is zero or < 10 % of rejected observations (' + str(proc_obs[1]) + ')! No alternative orbits specified. No coordinates were returned.')
        else:
            # load the database record dictionary
            self.load_record()
            self.lat, self.lon, self.h = self.ecef2lla([self.x, self.y, self.z])

        return

    def load_record(self):

        self.record['NetworkCode'] = self.rinex.NetworkCode
        self.record['StationCode'] = self.rinex.StationCode
        self.record['X'] = self.x
        self.record['Y'] = self.y
        self.record['Z'] = self.z
        self.record['Year'] = self.rinex.date.year
        self.record['DOY'] =self.rinex.date.doy
        self.record['ReferenceFrame'] = self.frame
        self.record['sigmax'] = self.sigmax
        self.record['sigmay'] = self.sigmay
        self.record['sigmaz'] = self.sigmaz
        self.record['sigmaxy'] = self.sigmaxy
        self.record['sigmaxz'] = self.sigmaxz
        self.record['sigmayz'] = self.sigmayz
        self.record['hash']    = self.hash

        return

    def ecef2lla(self, ecefArr):
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

    def cleanup(self):
        if os.path.isdir(self.rootdir):
            # remove all the directory contents
            rmtree(self.rootdir)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
