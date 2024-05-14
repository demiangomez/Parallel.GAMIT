"""
Project: Parallel.PPP
Date: 2/21/17 3:34 PM
Author: Demian D. Gomez

Python wrapper for PPP. It runs the NRCAN PPP and loads the information from
the summary file. Can be used without a database connection, except for 
PPPSpatialCheck

"""
from shutil import copyfile, rmtree
from math import isnan
import os
import uuid
import re

# deps
import numpy

import pyBrdc
# app
import pyRinex
import pySp3
import pyEOP
import pyClk
import pyEvents
import pyRunWithRetry
from pyDate import Date
from Utils import lg2ct, ecef2lla, determine_frame, file_write, file_readlines

OBSERV_CODE_ONLY  = '1'
OBSERV_CODE_PHASE = '2'


def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end   = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""


class pyRunPPPException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class pyRunPPPExceptionCoordConflict    (pyRunPPPException): pass
class pyRunPPPExceptionTooFewAcceptedObs(pyRunPPPException): pass
class pyRunPPPExceptionNaN              (pyRunPPPException): pass
class pyRunPPPExceptionZeroProcEpochs   (pyRunPPPException): pass
class pyRunPPPExceptionEOPError         (pyRunPPPException): pass


class PPPSpatialCheck:

    def __init__(self, lat=None, lon=None, h=None, epoch=None):
        self.lat   = lat
        self.lon   = lon
        self.h     = h
        self.epoch = epoch

    def verify_spatial_coherence(self, cnn, StationCode, search_in_new=False):
        # checks the spatial coherence of the resulting coordinate
        # will not make any decisions, just output the candidates
        # if ambiguities are found, the rinex StationCode is used to solve them
        # third output arg is used to return a list with the closest station/s if no match is found
        # or if we had to disambiguate using station name
        # DDG Mar 21 2018: Added the velocity of the station to account for fast moving stations (on ice)
        # the logic is as follows:
        # 1) if etm data is available, then use it to bring the coordinate to self.epoch
        # 2) if no etm parameters are available, default to the coordinate reported in the stations table

        if not search_in_new:
            where_clause = 'WHERE "NetworkCode" not like \'?%%\''
        else:
            where_clause = ''

        # start by reducing the number of stations filtering everything beyond 100 km from the point of interest
        # rs = cnn.query("""
        #     SELECT * FROM
        #     (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * cos(radians(%.8f)) *
        #     sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
        #     FROM stations %s) as DD
        #     WHERE distance <= %f
        #     """ % (self.lat[0], self.lat[0], self.lon[0], where_clause, 1e3))  # DO NOT RETURN RESULTS
        #     WITH NetworkCode = '?%'

        rs = cnn.query("""
            SELECT st1."NetworkCode", st1."StationCode", st1."StationName", st1."DateStart", st1."DateEnd",
             st1."auto_x", st1."auto_y", st1."auto_z", st1."Harpos_coeff_otl", st1."lat", st1."lon", st1."height",
             st1."max_dist", st1."dome", st1.distance FROM
            (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * 
            cos(radians(%.8f)) * sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
            FROM stations %s) as st1 left join stations as st2 ON 
                st1."StationCode" = st2."StationCode" and
                st1."NetworkCode" = st2."NetworkCode" and
                st1.distance < coalesce(st2.max_dist, 20)
                WHERE st2."NetworkCode" is not NULL
            """ % (self.lat[0], self.lat[0], self.lon[0], where_clause))  # DO NOT RETURN RESULTS NetworkCode = '?%'

        stn_match = rs.dictresult()

        # using the list of coordinates, check if StationCode exists in the list
        if len(stn_match) == 0:
            # no match, find closest station
            # get the closest station and distance in km to help the caller function
            rs = cnn.query("""
                SELECT * FROM
                    (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * 
                    cos(radians(%.8f)) * sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
                        FROM stations %s) as DD ORDER BY distance
                """ % (self.lat[0], self.lat[0], self.lon[0], where_clause))

            stn = rs.dictresult()

            return False, [], stn

        elif len(stn_match) == 1:
            if stn_match[0]['StationCode'] == StationCode:
                # one match, same name (return a dictionary)
                return True, stn_match, []
            else:
                # one match, not the same name (return a list, not a dictionary)
                return False, stn_match, []

        elif len(stn_match) > 1:
            # more than one match, same name
            # this is most likely a station that got moved a few meters and renamed
            # or a station that just got renamed.
            # disambiguation might be possible using the name of the station
            min_stn = [stni for stni in stn_match if stni['StationCode'] == StationCode]

            if len(min_stn) > 0:
                # the minimum distance if to a station with same name, we are good:
                # does the name match the closest station to this solution? yes
                return True, min_stn, []
            else:
                return False, stn_match, []


class RunPPP(PPPSpatialCheck):
    def __init__(self, in_rinex, otl_coeff, options, sp3types, sp3altrn, antenna_height, strict=True, apply_met=True,
                 kinematic=False, clock_interpolation=False, hash=0, erase=True, decimate=True, solve_coordinates=True,
                 solve_troposphere=105, back_substitution=False, elev_mask=10, x=0, y=0, z=0,
                 observations=OBSERV_CODE_PHASE):

        assert isinstance(in_rinex, pyRinex.ReadRinex)

        # DDG: if RINEX 3 version, convert to RINEX 2 (no PPP support)
        if in_rinex.rinex_version >= 3:
            # DDG: make a new object and convert to RINEX 3 to leave the other one untouched
            rinexobj = pyRinex.ReadRinex(in_rinex.NetworkCode, in_rinex.StationCode, in_rinex.origin_file,
                                         no_cleanup=in_rinex.no_cleanup, allow_multiday=in_rinex.allow_multiday)
            rinexobj.ConvertRinex(2)
        else:
            # file is in RINEX 2 format, use file as is
            rinexobj = in_rinex

        PPPSpatialCheck.__init__(self)

        self.rinex     = rinexobj
        self.epoch     = rinexobj.date
        self.antH      = antenna_height
        self.ppp_path  = options['ppp_path']
        self.ppp       = options['ppp_exe']
        self.options   = options
        self.kinematic = kinematic

        self.ppp_version = None

        self.file_summary        = None
        self.proc_parameters     = None
        self.observation_session = None
        self.coordinate_estimate = None
        self.clock_estimates     = None

        # DDG: do not allow clock interpolation before May 1 2001
        # DDG: unless it is a code-only request, then MUST be turned on
        if observations == OBSERV_CODE_PHASE:
            self.clock_interpolation = clock_interpolation if rinexobj.date > Date(year=2001, month=5, day=1) else False
        else:
            # override user's decision, must be on to run
            self.clock_interpolation = True

        self.frame             = None
        self.atx               = None
        # DDG: now can choose between code and code+phase observations
        self.observations      = observations
        # DDG: now accepts solving for a fixed coordinate PPP
        self.solve_coordinates = solve_coordinates
        # do not allow back_substitution or troposphere if code-only observations
        self.solve_troposphere = 1     if observations == OBSERV_CODE_ONLY else solve_troposphere
        self.back_substitution = False if observations == OBSERV_CODE_ONLY else back_substitution
        self.elev_mask         = elev_mask
        self.x                 = x
        self.y                 = y
        self.z                 = z
        self.lat               = None
        self.lon               = None
        self.h                 = None
        self.sigmax            = None
        self.sigmay            = None
        self.sigmaz            = None
        self.sigmaxy           = None
        self.sigmaxz           = None
        self.sigmayz           = None
        self.clock_phase       = None
        self.clock_phase_sigma = None
        self.phase_drift       = None
        self.phase_drift_sigma = None
        self.clock_rms         = None
        self.clock_rms_number  = None
        self.hash              = hash

        self.processed_obs = None
        self.rejected_obs  = None

        self.orbit_type    = None
        self.orbits1       = None
        self.orbits2       = None
        self.clocks1       = None
        self.clocks2       = None
        self.eop_file      = None
        self.sp3altrn      = sp3altrn
        self.sp3types      = sp3types
        self.otl_coeff     = otl_coeff
        self.strict        = strict
        self.apply_met     = apply_met
        self.erase         = erase
        self.out           = ''
        self.summary       = ''
        self.pos           = ''

        self.rootdir = os.path.join('production', 'ppp')

        fieldnames = ('NetworkCode', 'StationCode', 'X', 'Y', 'Z', 'Year', 'DOY',
                      'ReferenceFrame', 'sigmax', 'sigmay',
                      'sigmaz', 'sigmaxy', 'sigmaxz', 'sigmayz', 'hash')

        self.record = dict.fromkeys(fieldnames)

        # determine the atx to use
        self.frame, self.atx = determine_frame(self.options['frames'], self.epoch)

        if os.path.isfile(self.rinex.rinex_path):

            # generate a unique id for this instance
            self.rootdir = os.path.join(self.rootdir, str(uuid.uuid4()))

            path = os.path.join(self.rootdir, self.rinex.rinex[:-3])
            self.path_sum_file = path + 'sum'
            self.path_pos_file = path + 'pos'
            self.path_ses_file = path + 'ses'
            self.path_res_file = path + 'res'

            try:
                # create a production folder to analyze the rinex file
                if not os.path.exists(self.rootdir):
                    os.makedirs(self.rootdir)
                    os.makedirs(os.path.join(self.rootdir, 'orbits'))
            except Exception:
                # could not create production dir! FATAL
                raise

            try:
                self.get_orbits(self.sp3types)

            except (pySp3.pySp3Exception,
                    pyClk.pyClkException,
                    pyEOP.pyEOPException) as e:

                if sp3altrn:
                    self.get_orbits(self.sp3altrn)
                else:
                    raise type(e)(type(e)(e.message + ' -> This exception usually occurs due to the need of having '
                                                      'the orbit for the day being processed and the orbit of the '
                                                      'next day.'))

            self.write_otl()
            self.copyfiles()
            self.config_session()

            # make a local copy of the rinex file
            # decimate the rinex file if the interval is < 15 sec.
            # DDG: only decimate when told by caller
            if self.rinex.interval < 15 and decimate:
                self.rinex.decimate(30)

            copyfile(self.rinex.rinex_path,
                     os.path.join(self.rootdir, self.rinex.rinex))

        else:
            raise pyRunPPPException('The file ' + self.rinex.rinex_path +
                                    ' could not be found. PPP was not executed.')

    def copyfiles(self):
        # prepare all the files required to run PPP
        files = ('gpsppp.stc', 'gpsppp.svb_gnss_yrly', 'gpsppp.flt')
        if self.apply_met:
            files = ('gpsppp.met',) + files

        for f in files:
            if os.path.exists(os.path.join(self.ppp_path, f)):
                copyfile(os.path.join(self.ppp_path, f),
                         os.path.join(self.rootdir,  f))
            else:
                if f == 'gpsppp.svb_gnss_yrly':
                    raise pyRunPPPException(f'Missing gpsppp.svb_gnss_yrly for PPP processing.')

        copyfile(os.path.join(self.atx),
                 os.path.join(self.rootdir, os.path.basename(self.atx)))

    def write_otl(self):
        file_write(os.path.join(self.rootdir, self.rinex.StationCode + '.olc'),
                   self.otl_coeff)

    def config_session(self):

        options = self.options

        # create the def file
        file_write(os.path.join(self.rootdir, 'gpsppp.def'), 
                   "'LNG' 'ENGLISH'\n"
                   "'TRF' 'gpsppp.trf'\n"
                   "'SVB' 'gpsppp.svb_gnss_yrly'\n"
                   "'PCV' '%s'\n"
                   "'FLT' 'gpsppp.flt'\n"
                   "'OLC' '%s.olc'\n"
                   "'MET' 'gpsppp.met'\n"
                   "'ERP' '%s'\n"
                   "'GSD' '%s'\n"
                   "'GSD' '%s'\n"
                   % (os.path.basename(self.atx),
                      self.rinex.StationCode,
                      self.eop_file,
                      options['institution'],
                      options['info']))

        file_write(os.path.join(self.rootdir, 'commands.cmd'),
                   "' UT DAYS OBSERVED                      (1-45)'                   1\n"
                   "' USER DYNAMICS         (1=STATIC,2=KINEMATIC)'                   %s\n"
                   "' OBSERVATION TO PROCESS         (1=COD,2=C&P)'                   %s\n"
                   "' FREQUENCY TO PROCESS        (1=L1,2=L2,3=L3)'                   %s\n"
                   "' SATELLITE EPHEMERIS INPUT     (1=BRD ,2=SP3)'                   %s\n"
                   "' SATELLITE PRODUCT (1=NO,2=Prc,3=RTCA,4=RTCM)'                   2\n"
                   "' SATELLITE CLOCK INTERPOLATION   (1=NO,2=YES)'                   %s\n"
                   "' IONOSPHERIC GRID INPUT          (1=NO,2=YES)'                   1\n"
                   "' SOLVE STATION COORDINATES       (1=NO,2=YES)'                   %s\n"
                   "' SOLVE TROP. (1=NO,2-5=RW MM/HR) (+100=grad) '                   %i\n"
                   "' BACKWARD SUBSTITUTION           (1=NO,2=YES)'                   %s\n"
                   "' REFERENCE SYSTEM            (1=NAD83,2=ITRF)'                   2\n"
                   "' COORDINATE SYSTEM(1=ELLIPSOIDAL,2=CARTESIAN)'                   2\n"
                   "' A-PRIORI PSEUDORANGE SIGMA               (m)'              2.0000   9.00\n"
                   "' A-PRIORI CARRIER PHASE SIGMA             (m)'              0.0150   9.00\n"
                   "' LATITUDE  (ddmmss.sss,+N) or ECEF X      (m)'      %14.4f   0.000\n"
                   "' LONGITUDE (ddmmss.sss,+E) or ECEF Y      (m)'      %14.4f   0.000\n"
                   "' HEIGHT (m)                or ECEF Z      (m)'      %14.4f   0.000\n"
                   "' ANTENNA HEIGHT                           (m)'      %14.4f\n"
                   "' CUTOFF ELEVATION                       (deg)'      %14.4f\n"
                   "' GDOP CUTOFF                                 '             20.0000\n"
                   % ('1' if not self.kinematic else '2',
                      self.observations,
                      '1' if self.observations == OBSERV_CODE_ONLY else '3',
                      '1' if self.observations == OBSERV_CODE_ONLY else '2',
                      '1' if not self.clock_interpolation else '2',
                      '1' if not self.solve_coordinates else '2',
                      self.solve_troposphere,
                      '1' if not self.back_substitution else '2',
                      self.x, self.y, self.z,
                      self.antH, self.elev_mask))

        file_write(os.path.join(self.rootdir, 'input.inp'), 
                   "%s\n"
                   "commands.cmd\n"
                   "0 0\n"
                   "0 0\n"
                   "orbits/%s\n"
                   "orbits/%s\n"
                   "orbits/%s\n"
                   "orbits/%s\n"
                   % (self.rinex.rinex, self.orbits1.filename, self.clocks1.filename,
                      self.orbits2.filename, self.clocks2.filename))

    def get_orbits(self, orbit_type):

        options = self.options

        orbits_path = os.path.join(self.rootdir, 'orbits')

        if self.observations == OBSERV_CODE_PHASE:
            orbits1 = pySp3.GetSp3Orbits(options['sp3'], self.rinex.date,     orbit_type, orbits_path, True)
            orbits2 = pySp3.GetSp3Orbits(options['sp3'], self.rinex.date + 1, orbit_type, orbits_path, True)

            clocks1 = pyClk.GetClkFile(  options['sp3'], self.rinex.date,     orbit_type, orbits_path, True)
            clocks2 = pyClk.GetClkFile(  options['sp3'], self.rinex.date + 1, orbit_type, orbits_path, True)
        else:
            # for code-only solution we get the BRDC orbit and we use the same information for all files.
            orbits1 = pyBrdc.GetBrdcOrbits(options['brdc'], self.rinex.date, orbits_path, True)
            orbits2 = orbits1
            clocks1 = orbits1
            clocks2 = orbits1
        try:
            eop_file = pyEOP.GetEOP(options['sp3'], self.rinex.date, orbit_type, self.rootdir)
            eop_file = eop_file.filename
        except pyEOP.pyEOPException:
            # no eop, continue with out one
            eop_file = 'dummy.eop'

        self.orbits1    = orbits1
        self.orbits2    = orbits2
        self.clocks1    = clocks1
        self.clocks2    = clocks2
        self.eop_file   = eop_file
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

        x = re.findall(r'X\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]
        y = re.findall(r'Y\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]
        z = re.findall(r'Z\s\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0][1]

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
    def get_clock(section, kinematic):
        # DDG: TODO -> read if ms or ns and scale output accordingly
        try:
            clock_phase = re.findall(r'Clock Phase\s*\([nm]s\)\s*:\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)',     section)[0]
            phase_drift = re.findall(r'Phase Drift\s*\([nm]s/day\)\s*:\s*(-?\d+\.\d+)\s*(-?\d+\.\d+)', section)[0]
            clock_resid = re.findall(r'RMS residuals\s*\([nm]s\)\s*:\s*(-?\d+\.\d+)\s*(\d+)',          section)[0]

        except IndexError:
            clock_phase = [0, 0]
            phase_drift = [0, 0]
            clock_resid = [0, 0]

        return float(clock_phase[0]), float(clock_phase[1]), \
               float(phase_drift[0]), float(phase_drift[1]), \
               float(clock_resid[0]), int(clock_resid[1])

    @staticmethod
    def get_sigmas(section, kinematic):

        if kinematic:

            sx = re.findall(r'X\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sy = re.findall(r'Y\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sz = re.findall(r'Z\s\(m\)\s+-?\d+\.\d+\s+-?\d+\.\d+\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]

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
            sx, sxy, sxz = re.findall(r'X\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)'
                                      r'\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sy, syz      = re.findall(r'Y\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]
            sz           = re.findall(r'Z\(m\)\s+(-?\d+\.\d+|[nN]a[nN]|\*+)', section)[0]

            if '*' in sx  or '*' in sy  or '*' in sz or \
               '*' in sxy or '*' in sxz or '*' in syz:
                raise pyRunPPPExceptionNaN('Sigmas are NaN')
            else:
                sx = float(sx)
                sy = float(sy)
                sz = float(sz)
                sxy = float(sxy)
                sxz = float(sxz)
                syz = float(syz)

        if isnan(sx)  or isnan(sy)  or isnan(sz) or \
           isnan(sxy) or isnan(sxz) or isnan(syz):
            raise pyRunPPPExceptionNaN('Sigmas are NaN')

        return sx, sy, sz, sxy, sxz, syz

    def get_pr_observations(self, section, kinematic):

        if self.ppp_version == '1.05':
            processed = re.findall(r'Number of epochs processed\s+\:\s+(\d+)', section)[0]
        else:
            processed = re.findall(r'Number of epochs processed \(%fix\)\s+\:\s+(\d+)', section)[0]

        if kinematic:
            rejected = re.findall(r'Number of epochs rejected\s+\:\s+(\d+)', section)
        else:
            # processed = re.findall('Number of observations processed\s+\:\s+(\d+)', section)[0]
            rejected = re.findall(r'Number of observations rejected\s+\:\s+(\d+)', section)

        if len(rejected) > 0:
            rejected = int(rejected[0])
        else:
            rejected = 0

        return int(processed), rejected

    @staticmethod
    def check_phase_center(section):
        return not len(re.findall(r'Antenna phase center.+NOT AVAILABLE', section)) > 0

    @staticmethod
    def check_otl(section):
        return not len(re.findall(r'Ocean loading coefficients.+NOT FOUND', section)) > 0

    @staticmethod
    def check_eop(section):
        pole = re.findall(r'Pole X\s+.\s+(-?\d+\.\d+|[nN]a[nN])\s+(-?\d+\.\d+|[nN]a[nN])', section)
        return len(pole) <= 0 or \
            (type(pole[0]) is tuple and 'nan' not in pole[0][0].lower())

    @staticmethod
    def get_frame(section):
        return re.findall(r'\s+ITRF\s\((\s*\w+\s*)\)', section)[0].strip()

    def parse_summary(self):

        self.summary = ''.join(self.out)

        self.ppp_version = re.findall(r'.*Version\s+(\d.\d+)\/', self.summary)

        if len(self.ppp_version) == 0:
            self.ppp_version = re.findall(r'.*CSRS-PPP ver.\s+(\d.\d+)\/', self.summary)[0]
        else:
            self.ppp_version = self.ppp_version[0]

        self.file_summary        = self.get_text(self.summary,
                                                 'SECTION 1.',
                                                 'SECTION 2.')
        self.proc_parameters     = self.get_text(self.summary,
                                                 'SECTION 2. ',
                                                 ' SECTION 3. ')
        self.observation_session = self.get_text(self.summary,
                                                 '3.2 Observation Session',
                                                 '3.3 Coordinate estimates')
        self.coordinate_estimate = self.get_text(self.summary,
                                                 '3.3 Coordinate estimates',
                                                 '3.4 Coordinate differences ITRF')
        self.clock_estimates     = self.get_text(self.summary,
                                                 '3.5 Receiver clock estimates',
                                                 '3.6 Observation rejection table')
        if self.strict:
            if not self.check_phase_center(self.proc_parameters):
                raise pyRunPPPException(
                    'Error while running PPP: could not find the antenna and radome in antex file. '
                    'Check RINEX header for formatting issues in the ANT # / TYPE field. RINEX header follows:\n' + ''.join(
                        self.rinex.get_header()))

            if not self.check_otl(self.proc_parameters):
                raise pyRunPPPException(
                    'Error while running PPP: could not find the OTL coefficients. '
                    'Check RINEX header for formatting issues in the APPROX ANT POSITION field. If APR is too far '
                    'from OTL coordinates (declared in the HARPOS or BLQ format) NRCAN will reject the coefficients. '
                    'OTL coefficients record follows:\n' + self.otl_coeff)

        if not self.check_eop(self.file_summary):
            raise pyRunPPPExceptionEOPError('EOP returned NaN in Pole XYZ.')

        # parse rejected and accepted observations
        self.processed_obs, self.rejected_obs = self.get_pr_observations(self.observation_session, self.kinematic)

        if self.processed_obs == 0:
            raise pyRunPPPExceptionZeroProcEpochs('PPP returned zero processed epochs')

        # if self.strict and (self.processed_obs == 0 or self.rejected_obs > 0.95 * self.processed_obs):
        #    raise pyRunPPPExceptionTooFewAcceptedObs('The processed observations (' + str(self.processed_obs) +
        #                                             ') is zero or more than 95% of the observations were rejected (' +
        #                                             str(self.rejected_obs) + ')')

        # FRAME now comes from the startup process, where the function Utils.determine_frame is called
        # self.frame = self.get_frame(self.coordinate_estimate)

        self.x, self.y, self.z     = self.get_xyz(self.coordinate_estimate)
        self.lat, self.lon, self.h = ecef2lla([self.x, self.y, self.z])

        self.sigmax,  \
        self.sigmay,  \
        self.sigmaz,  \
        self.sigmaxy, \
        self.sigmaxz, \
        self.sigmayz = self.get_sigmas(self.coordinate_estimate, self.kinematic)

        self.clock_phase,       \
        self.clock_phase_sigma, \
        self.phase_drift,       \
        self.phase_drift_sigma, \
        self.clock_rms,         \
        self.clock_rms_number = self.get_clock(self.clock_estimates, self.kinematic)

        # not implemented in PPP: apply NE offset if is NOT zero
        if self.rinex.antOffsetN != 0.0 or \
           self.rinex.antOffsetE != 0.0:
            
            dx, dy, dz = lg2ct(numpy.array(self.rinex.antOffsetN),
                               numpy.array(self.rinex.antOffsetE),
                               numpy.array([0]),
                               self.lat, self.lon)
            # reduce coordinates
            self.x -= dx[0]
            self.y -= dy[0]
            self.z -= dz[0]
            self.lat, self.lon, self.h = ecef2lla([self.x, self.y, self.z])

    def __exec_ppp__(self, raise_error=True):

        try:
            # DDG: handle the error found in PPP (happens every now and then)
            # Fortran runtime error: End of file
            for i in range(2):
                out, err = pyRunWithRetry.RunCommand(self.ppp, 60, self.rootdir, 'input.inp').run_shell()

                if '*END - NORMAL COMPLETION' not in out:

                    if 'Fortran runtime error: End of file' in err and i == 0:
                        # error detected, try again!
                        continue

                    msg = 'PPP ended abnormally for ' + self.rinex.rinex_path + ':\n' + err + '\n' + out
                    if raise_error:
                        raise pyRunPPPException(msg)
                    else:
                        return False, msg
                else:
                    self.out = file_readlines(self.path_sum_file)
                    self.pos = file_readlines(self.path_pos_file)
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
                    else:
                        raise

                except (pyRunPPPExceptionNaN,
                        pyRunPPPExceptionTooFewAcceptedObs,
                        pyRunPPPExceptionZeroProcEpochs):

                    # DDG: only attempt reruns if OBSERV_CODE_PHASE
                    if self.observations == OBSERV_CODE_PHASE:
                        # Nan in the result
                        if not self.kinematic:
                            # first retry, turn to kinematic mode
                            self.kinematic = True

                        elif self.rinex.date.fyear >= 2001.33287 and not self.clock_interpolation:
                            # date has to be > 2001 May 1 (SA deactivation date)
                            self.clock_interpolation = True

                        elif self.sp3altrn and self.orbit_type not in self.sp3altrn:
                            # second retry, kinematic and alternative orbits (if exist)
                            self.get_orbits(self.sp3altrn)

                        else:
                            # it didn't work in kinematic mode either! raise error
                            raise
                    else:
                        raise
            elif self.sp3altrn and self.orbit_type not in self.sp3altrn:
                # maybe a bad orbit, fall back to alternative
                self.get_orbits(self.sp3altrn)
            else:
                raise pyRunPPPException(message)

            # reconfig and try again
            self.config_session()

        self.load_record()

    def load_record(self):

        self.record['NetworkCode']    = self.rinex.NetworkCode
        self.record['StationCode']    = self.rinex.StationCode
        self.record['X']              = self.x
        self.record['Y']              = self.y
        self.record['Z']              = self.z
        self.record['Year']           = self.rinex.date.year
        self.record['DOY']            = self.rinex.date.doy
        self.record['ReferenceFrame'] = self.frame
        self.record['sigmax']         = self.sigmax
        self.record['sigmay']         = self.sigmay
        self.record['sigmaz']         = self.sigmaz
        self.record['sigmaxy']        = self.sigmaxy
        self.record['sigmaxz']        = self.sigmaxz
        self.record['sigmayz']        = self.sigmayz
        self.record['hash']           = self.hash

    def cleanup(self):
        if os.path.isdir(self.rootdir) and self.erase:
            # remove all the directory contents
            rmtree(self.rootdir)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
