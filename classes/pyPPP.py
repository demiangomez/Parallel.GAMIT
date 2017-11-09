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
import re
from math import isnan
from Utils import ecef2lla

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


class pyRunPPPExceptionCoordConflict(pyRunPPPException):
    pass


class pyRunPPPExceptionTooFewAcceptedObs(pyRunPPPException):
    pass


class pyRunPPPExceptionNaN(pyRunPPPException):
    pass


class pyRunPPPExceptionZeroProcEpochs(pyRunPPPException):
    pass

class pyRunPPPExceptionEOPError(pyRunPPPException):
    pass

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
    def __init__(self,rinexobj,otl_coeff,options,sp3types,sp3altrn,antenna_height,strict=True,apply_met=True,kinematic=False, clock_interpolation=False, hash=0):
        assert isinstance(rinexobj,pyRinex.ReadRinex)

        PPPSpatialCheck.__init__(self)

        self.rinex = rinexobj
        self.antH = antenna_height
        self.ppp_path = options['ppp_path']
        self.ppp = options['ppp_exe']
        self.options = options
        self.kinematic = kinematic
        self.clock_interpolation = clock_interpolation

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

        self.processed_obs = None
        self.rejected_obs = None

        self.orbit_type = None
        self.orbits1    = None
        self.orbits2    = None
        self.clocks1    = None
        self.clocks2    = None
        self.eop_file   = None
        self.sp3altrn   = sp3altrn
        self.sp3types   = sp3types
        self.otl_coeff  = otl_coeff
        self.strict     = strict
        self.apply_met  = apply_met
        self.out        = ''
        self.summary    = ''
        self.pos        = ''

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

            try:
                self.get_orbits(self.sp3types)

            except (pySp3.pySp3Exception, pyClk.pyClkException, pyEOP.pyEOPException):

                if sp3altrn:
                    self.get_orbits(self.sp3altrn)
                else:
                    raise

            self.write_otl()
            self.copyfiles()
            self.config_session()

            # make a local copy of the rinex file
            # decimate the rinex file if the interval is < 15 sec.
            if self.rinex.interval < 15:
                self.rinex.decimate(30)

            copyfile(self.rinex.rinex_path, os.path.join(self.rootdir, self.rinex.rinex))

        else:
            raise pyRunPPPException('The file ' + self.rinex.rinex_path + ' could not be found. PPP was not executed.')

        return

    def copyfiles(self):
        # prepare all the files required to run PPP
        if self.apply_met:
            copyfile(os.path.join(self.ppp_path, 'gpsppp.met'), os.path.join(self.rootdir, 'gpsppp.met'))

        copyfile(os.path.join(self.ppp_path, 'gpsppp.stc'), os.path.join(self.rootdir, 'gpsppp.stc'))
        copyfile(os.path.join(self.ppp_path, 'gpsppp.svb_gps_yrly'), os.path.join(self.rootdir, 'gpsppp.svb_gps_yrly'))
        copyfile(os.path.join(self.ppp_path, 'gpsppp.flt'), os.path.join(self.rootdir, 'gpsppp.flt'))
        copyfile(os.path.join(self.ppp_path, 'gpsppp.stc'), os.path.join(self.rootdir, 'gpsppp.stc'))
        copyfile(os.path.join(self.options['atx']), os.path.join(self.rootdir, self.options['atx'].split('/')[-1]))

        return

    def write_otl(self):

        otl_file = open(os.path.join(self.rootdir, self.rinex.StationCode + '.olc'), 'w')
        otl_file.write(self.otl_coeff)
        otl_file.close()

        return

    def config_session(self):

        options = self.options

        # create the def file
        def_file = open(os.path.join(self.rootdir,'gpsppp.def'), 'w')

        def_file_cont = ("'LNG' 'ENGLISH'\n"
                         "'TRF' 'gpsppp.trf'\n"
                         "'SVB' 'gpsppp.svb_gps_yrly'\n"
                         "'PCV' '%s'\n"
                         "'FLT' 'gpsppp.flt'\n"
                         "'OLC' '%s.olc'\n"
                         "'MET' 'gpsppp.met'\n"
                         "'ERP' '%s'\n"
                         "'GSD' '%s'\n"
                         "'GSD' '%s'\n"
                         % (options['atx'].split('/')[-1],
                            self.rinex.StationCode,
                            self.eop_file,
                            options['institution'],
                            options['info']))

        def_file.write(def_file_cont)
        def_file.close()

        cmd_file = open(os.path.join(self.rootdir,'commands.cmd'), 'w')

        cmd_file_cont = ("' UT DAYS OBSERVED                      (1-45)'               1\n"
                         "' USER DYNAMICS         (1=STATIC,2=KINEMATIC)'               %s\n"
                         "' OBSERVATION TO PROCESS         (1=COD,2=C&P)'               2\n"
                         "' FREQUENCY TO PROCESS        (1=L1,2=L2,3=L3)'               3\n"
                         "' SATELLITE EPHEMERIS INPUT     (1=BRD ,2=SP3)'               2\n"
                         "' SATELLITE PRODUCT (1=NO,2=Prc,3=RTCA,4=RTCM)'               2\n"
                         "' SATELLITE CLOCK INTERPOLATION   (1=NO,2=YES)'               %s\n"
                         "' IONOSPHERIC GRID INPUT          (1=NO,2=YES)'               1\n"
                         "' SOLVE STATION COORDINATES       (1=NO,2=YES)'               2\n"
                         "' SOLVE TROP. (1=NO,2-5=RW MM/HR) (+100=grad) '             105\n"
                         "' BACKWARD SUBSTITUTION           (1=NO,2=YES)'               1\n"
                         "' REFERENCE SYSTEM            (1=NAD83,2=ITRF)'               2\n"
                         "' COORDINATE SYSTEM(1=ELLIPSOIDAL,2=CARTESIAN)'               2\n"
                         "' A-PRIORI PSEUDORANGE SIGMA               (m)'           2.000\n"
                         "' A-PRIORI CARRIER PHASE SIGMA             (m)'           0.015\n"
                         "' LATITUDE  (ddmmss.sss,+N) or ECEF X      (m)'          0.0000\n"
                         "' LONGITUDE (ddmmss.sss,+E) or ECEF Y      (m)'          0.0000\n"
                         "' HEIGHT (m)                or ECEF Z      (m)'          0.0000\n"
                         "' ANTENNA HEIGHT                           (m)'          %6.4f\n"
                         "' CUTOFF ELEVATION                       (deg)'          10.000\n"
                         "' GDOP CUTOFF                                 '          20.000\n"
                         % ('1' if not self.kinematic else '2', '1' if not self.clock_interpolation else '2', self.antH))

        cmd_file.write(cmd_file_cont)

        cmd_file.close()

        inp_file = open(os.path.join(self.rootdir, 'input.inp'), 'w')

        inp_file_cont = ("%s\n"
            "commands.cmd\n"
            "0 0\n"
            "0 0\n"
            "orbits/%s\n"
            "orbits/%s\n"
            "orbits/%s\n"
            "orbits/%s\n"
            % (self.rinex.rinex,
               self.orbits1.sp3_filename,
               self.clocks1.clk_filename,
               self.orbits2.sp3_filename,
               self.clocks2.clk_filename))

        inp_file.write(inp_file_cont)

        inp_file.close()

        return

    def get_orbits(self, type):

        options = self.options

        orbits1 = pySp3.GetSp3Orbits(options['sp3'],self.rinex.date, type, os.path.join(self.rootdir,'orbits'),True)
        orbits2 = pySp3.GetSp3Orbits(options['sp3'],self.rinex.date+1, type, os.path.join(self.rootdir,'orbits'),True)

        clocks1 = pyClk.GetClkFile(options['sp3'],self.rinex.date, type, os.path.join(self.rootdir,'orbits'),True)
        clocks2 = pyClk.GetClkFile(options['sp3'],self.rinex.date+1, type, os.path.join(self.rootdir,'orbits'),True)

        try:
            eop_file = pyEOP.GetEOP(options['sp3'],self.rinex.date, type, self.rootdir)
            eop_file = eop_file.eop_filename
        except pyEOP.pyEOPException:
            # no eop, continue with out one
            eop_file = 'dummy.eop'

        self.orbits1 = orbits1
        self.orbits2 = orbits2
        self.clocks1 = clocks1
        self.clocks2 = clocks2
        self.eop_file = eop_file
        # get the type of orbit
        self.orbit_type = orbits1.type

    def get_text(self, summary, start, end):
        copy = False

        if type(summary) is str:
            summary = summary.split('\n')

        out = []
        for line in summary:
            if start in line.strip():
                copy = True
            elif end in line.strip():
                copy = False
            elif copy:
                out += [line]

        return '\n'.join(out)

    @staticmethod
    def get_xyz(section):

        x = re.findall('X\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]
        y = re.findall('Y\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]
        z = re.findall('Z\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]

        if '*' not in x and '*' not in y and '*' not in z:
            x = float(x)
            y = float(y)
            z = float(z)
        else:
            raise pyRunPPPExceptionNaN('One or more coordinate is NaN')

        if isnan(x) or isnan(y) or isnan(z):
            raise pyRunPPPExceptionNaN('One or more coordinate is NaN')

        return x, y, z

    @staticmethod
    def get_sigmas(section, kinematic):

        if kinematic:

            sx = re.findall('X\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sy = re.findall('Y\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sz = re.findall('Z\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]

            if '*' not in sx and '*' not in sy and '*' not in sz:
                sx = float(sx)
                sy = float(sy)
                sz = float(sz)
                sxy = 0.0
                sxz = 0.0
                syz = 0.0
            else:
                raise pyRunPPPExceptionNaN('One or more sigma is NaN')

        else:
            sx, sxy, sxz = re.findall('X\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sy, syz      = re.findall('Y\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sz           = re.findall('Z\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]

            if '*' in sx or '*' in sy or '*' in sz or '*' in sxy or '*' in sxz or '*' in syz:
                raise pyRunPPPExceptionNaN('One or more sigma is NaN')
            else:
                sx = float(sx)
                sy = float(sy)
                sz = float(sz)
                sxy = float(sxy)
                sxz = float(sxz)
                syz = float(syz)

        if isnan(sx) or isnan(sy) or isnan(sz) or isnan(sxy) or isnan(sxz) or isnan(syz):
            raise pyRunPPPExceptionNaN('One or more sigma is NaN')

        return sx, sy, sz, sxy, sxz, syz

    @staticmethod
    def get_pr_observations(section, kinematic):

        processed = re.findall('Number of epochs processed\s+\:\s+(\d+)', section)[0]

        if kinematic:
            rejected = re.findall('Number of epochs rejected\s+\:\s+(\d+)', section)

            if len(rejected) > 0:
                rejected = int(rejected[0])
            else:
                rejected = 0
        else:
            #processed = re.findall('Number of observations processed\s+\:\s+(\d+)', section)[0]

            rejected = re.findall('Number of observations rejected\s+\:\s+(\d+)', section)

            if len(rejected) > 0:
                rejected = int(rejected[0])
            else:
                rejected = 0

        return int(processed), int(rejected)

    @staticmethod
    def check_phase_center(section):

        if len(re.findall('Antenna phase center.+NOT AVAILABLE', section)) > 0:
            return False
        else:
            return True

    @staticmethod
    def check_otl(section):

        if len(re.findall('Ocean loading coefficients.+NOT FOUND', section)) > 0:
            return False
        else:
            return True

    @staticmethod
    def check_eop(section):
        pole = re.findall('Pole X\s+.\s+(-?\d+\.\d+|nan)\s+(-?\d+\.\d+|nan)', section)
        if len(pole) > 0:
            if 'nan' not in pole[0]:
                return True
            else:
                return False
        else:
            return True

    @staticmethod
    def get_frame(section):
        return re.findall('\s+ITRF\s\((\s*\w+\s*)\)', section)[0].strip()

    def parse_summary(self):

        self.summary = ''.join(self.out)

        self.file_summary = self.get_text(self.summary, 'SECTION 1.', 'SECTION 2.')
        self.proc_parameters = self.get_text(self.summary, 'SECTION 2. ', ' SECTION 3. ')
        self.observation_session = self.get_text(self.summary, '3.2 Observation Session', '3.3 Coordinate estimates')
        self.coordinate_estimate = self.get_text(self.summary, '3.3 Coordinate estimates', '3.4 Coordinate differences ITRF')

        if self.strict and not self.check_phase_center(self.proc_parameters):
            raise pyRunPPPException(
                'Error while running PPP: could not find the antenna and radome in antex file. Check RINEX header for formatting issues in the ANT # / TYPE field. RINEX header follows:\n' + ''.join(
                    self.rinex.get_header()))

        if self.strict and not self.check_otl(self.proc_parameters):
            raise pyRunPPPException(
                'Error while running PPP: could not find the OTL coefficients. Check RINEX header for formatting issues in the APPROX ANT POSITION field')

        if not self.check_eop(self.file_summary):
            raise pyRunPPPExceptionEOPError('EOP returned NaN in Pole XYZ.')

        # parse rejected and accepted observations
        self.processed_obs, self.rejected_obs = self.get_pr_observations(self.observation_session, self.kinematic)

        if self.processed_obs == 0:
            raise pyRunPPPExceptionZeroProcEpochs('PPP returned zero processed epochs')

        #if self.strict and (self.processed_obs == 0 or self.rejected_obs > 0.95 * self.processed_obs):
        #    raise pyRunPPPExceptionTooFewAcceptedObs('The processed observations (' + str(self.processed_obs) +
        #                                             ') is zero or more than 95% of the observations were rejected (' +
        #                                             str(self.rejected_obs) + ')')

        self.frame = self.get_frame(self.coordinate_estimate)

        self.x, self.y, self.z = self.get_xyz(self.coordinate_estimate)

        self.sigmax, self.sigmay, self.sigmaz, \
        self.sigmaxy, self.sigmaxz, self.sigmayz = self.get_sigmas(self.coordinate_estimate, self.kinematic)


    def __exec_ppp__(self, raise_error=True):

        try:
            # DDG: handle the error found in PPP (happens every now and then)
            # Fortran runtime error: End of file
            for i in range(2):
                cmd = pyRunWithRetry.RunCommand(self.ppp, 45, self.rootdir, 'input.inp')
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

        return True, ''

    def exec_ppp(self):

        while True:
            # execute PPP but do not raise an error if timed out
            result, message = self.__exec_ppp__(False)

            if result:
                try:
                    self.parse_summary()
                    break

                except pyRunPPPExceptionEOPError:
                    # problem with EOP!
                    if self.eop_file != 'dummy.eop':
                        self.eop_file = 'dummy.eop'
                        self.config_session()
                    else:
                        raise

                except (pyRunPPPExceptionNaN, pyRunPPPExceptionTooFewAcceptedObs, pyRunPPPExceptionZeroProcEpochs):
                    # Nan in the result
                    if not self.kinematic:
                        # first retry, turn to kinematic mode
                        self.kinematic = True
                        self.config_session()
                    elif self.kinematic and self.sp3altrn and self.orbit_type not in self.sp3altrn:
                        # second retry, kinematic and alternative orbits (if exist)
                        self.get_orbits(self.sp3altrn)
                        self.config_session()
                    else:
                        # it didn't work in kinematic mode either! raise error
                        raise
            else:
                # maybe a bad orbit, fall back to alternative
                if self.sp3altrn and self.orbit_type not in self.sp3altrn:
                    self.get_orbits(self.sp3altrn)
                    self.config_session()
                else:
                    raise pyRunPPPException(message)

        self.load_record()
        self.lat, self.lon, self.h = ecef2lla([self.x, self.y, self.z])

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
