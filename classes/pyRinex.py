"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

from shutil import copyfile
from shutil import copy
from shutil import move
from shutil import rmtree
from pyEvents import Event
from Utils import ecef2lla
import os
import pyDate
import pyRunWithRetry
import pyStationInfo
import datetime
import Utils
import uuid
import re
import struct

TYPE_CRINEZ = 0
TYPE_RINEX = 1
TYPE_RINEZ = 2
TYPE_CRINEX = 3


def check_year(year):
    # to check for wrong dates in RinSum

    if int(year) - 1900 < 80 and int(year) >= 1900:
        year = int(year) - 1900 + 2000

    elif int(year) < 1900 and int(year) >= 80:
        year = int(year) + 1900

    elif int(year) < 1900 and int(year) < 80:
        year = int(year) + 2000

    return year


def create_unzip_script(run_file_path):
    # temporary script to uncompress o.Z files
    # requested by RS issue #13
    try:
        run_file = open(run_file_path, 'w')
    except (OSError, IOError):
        raise Exception('could not open file ' + run_file_path)

    contents = """#!/bin/csh -f
        # set default mode
        set out_current = 0
        set del_input = 0
        unset verbose
        set ovrewrite = 0

        set PROGRAM = CRX2RNX

        unset noclobber

        # check options
        foreach var ($argv[*])
        switch ($var)
        case '-c':
        set out_current = 1
        shift; breaksw
        case '-d':
        set del_input = 1
        shift; breaksw
        case '-f':
        set ovrewrite = 1
        shift; breaksw
        case '-v':
        set verbose = 1
        shift; breaksw
        default:
        break
        endsw
        end


        # process files
        foreach file ($argv[*])

        # make command to be issued and name of output file
        set file2 = $file
        set ext   = $file:e
        if ( $out_current ) set file2 = $file2:t
        if( $ext == Z || $ext == gz ) set file2 = $file2:r
        if( $file2 =~ *.??[oO] ) then
        set file2 = `echo $file2 | sed -e 's/d$/o/' -e 's/D$/O/' `
        else if( $file2 !~ *.??[oOnNgGlLpPhHbBmMcC] || ! ($ext == Z || $ext == gz) ) then
        # This is not a compressed RINEX file ... skip it
        continue
        endif
        set file_save = $file2

        # check if the output file is preexisting
        if ( -e "$file_save" && ! $ovrewrite ) then
        echo "The file $file_save already exists. Overwrite?(y/n,default:n)"
        if ( $< !~ [yY] ) continue
        endif

        # issue the command
        if( $file =~ *.??[oO] ) then
            cat $file - > $file_save
        else if( $file =~ *.??[oO].Z || $file =~ *.??[oO].gz ) then
          file $file | grep -q "Zip"
          if ( "$status" == "0" ) then
             unzip -p $file - > $file_save
          else
             file $file | grep -q "ASCII"
             if ( "$status" == "0" ) then
                cat $file > $file_save
             else
                zcat $file > $file_save
             endif
          endif
        else
        zcat $file > $file_save
        endif

        # remove the input file
        if ( $status == 0 && $del_input ) rm $file

        end
    """
    run_file.write(contents)
    run_file.close()

    os.system('chmod +x ' + run_file_path)


class pyRinexException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = Event(Description=value, EventType='error')
    def __str__(self):
        return str(self.value)


class pyRinexExceptionBadFile(pyRinexException):
    pass


class pyRinexExceptionSingleEpoch(pyRinexException):
    pass


class pyRinexExceptionNoAutoCoord(pyRinexException):
    pass


class RinexRecord():

    def __init__(self, NetworkCode=None, StationCode=None):

        self.StationCode = StationCode
        self.NetworkCode = NetworkCode

        self.firstObs = None
        self.datetime_firstObs = None
        self.datetime_lastObs = None
        self.lastObs = None
        self.antType = None
        self.marker_number = None
        self.marker_name = StationCode
        self.recType = None
        self.recNo = None
        self.recVers = None
        self.antNo = None
        self.antDome = None
        self.antOffset = None
        self.interval = None
        self.size = None
        self.x = None
        self.y = None
        self.z = None
        self.lat = None
        self.lon = None
        self.h = None
        self.date = None
        self.rinex = None
        self.crinez = None
        self.crinez_path = None
        self.rinex_path = None
        self.origin_type = None
        self.obs_types = None
        self.system = None
        self.no_cleanup = None
        self.multiday = False
        self.multiday_rnx_list = []
        self.epochs = None
        self.completion = None
        self.rel_completion = None
        self.rinex_version = None

        # log list to append all actions performed to rinex file
        self.log = []

        # list of required header records and a flag to know if they were found or not in the current header
        # also, have a tuple of default values in case there is a missing record
        self.required_records = {'RINEX VERSION / TYPE':
                                     {'format_tuple': ('%9.2f', '%11s', '%1s', '%19s', '%1s', '%19s'),
                                      'found': False,
                                      'default': ('',)},

                                 'PGM / RUN BY / DATE':
                                     {'format_tuple': ('%-20s', '%-20s', '%-20s'),
                                      'found': False,
                                      'default': ('pyRinex: 1.00 000', 'Parallel.PPP', '21FEB17 00:00:00')},

                                 'MARKER NAME':
                                     {'format_tuple': ('%-60s',),
                                      'found': False,
                                      'default': (self.StationCode.upper(),)},

                                 'MARKER NUMBER':
                                     {'format_tuple': ('%-20s',),
                                      'found': False,
                                      'default': (self.StationCode.upper(),)},

                                 'OBSERVER / AGENCY':
                                     {'format_tuple': ('%-20s', '%-40s'),
                                      'found': False,
                                      'default': ('UNKNOWN', 'UNKNOWN')},

                                 'REC # / TYPE / VERS':
                                     {'format_tuple': ('%-20s', '%-20s', '%-20s'),
                                      'found': False,
                                      'default': ('0000000', 'ASHTECH Z-XII3', 'CC00')},

                                 'ANT # / TYPE':
                                     {'format_tuple': ('%-20s', '%-20s'),
                                      'found': False,
                                      'default': ('0000', 'ASH700936C_M SNOW')},

                                 'ANTENNA: DELTA H/E/N':
                                     {'format_tuple': ('%14.4f', '%14.4f', '%14.4f'),
                                      'found': False,
                                      'default': (0.0, 0.0, 0.0)},

                                 'APPROX POSITION XYZ':
                                     {'format_tuple': ('%14.4f', '%14.4f', '%14.4f'),
                                      'found': False,
                                      'default': (0.0, 0.0, 6371000.0)},
                                    # '# / TYPES OF OBSERV' : [('%6i',), False, ('',)],
                                 'TIME OF FIRST OBS':
                                     {'format_tuple': ('%6i', '%6i', '%6i', '%6i', '%6i', '%13.7f', '%8s'),
                                      'found': False,
                                      'default': (1, 1, 1, 1, 1, 0, 'GPS')},
                                 'INTERVAL':
                                     {'format_tuple': ('%10.3f',),
                                      'found': False,
                                      'default': (30,)},  # put a wrong interval when first reading the file so that RinSum does not fail to read RINEX if interval record is > 60 chars
                                    # DDG: remove time of last observation all together. It just creates problems and is not mandatory
                                    # 'TIME OF LAST OBS'    : [('%6i','%6i','%6i','%6i','%6i','%13.7f','%8s'), True, (int(first_obs.year), int(first_obs.month), int(first_obs.day), int(23), int(59), float(59), 'GPS')],
                                 'COMMENT':
                                     {'format_tuple': ('%-60s',), 'found': True, 'default': ('',)}}

        fieldnames = ['NetworkCode','StationCode','ObservationYear','ObservationMonth','ObservationDay',
                      'ObservationDOY','ObservationFYear','ObservationSTime','ObservationETime','ReceiverType',
                      'ReceiverSerial','ReceiverFw','AntennaType','AntennaSerial','AntennaDome','Filename','Interval',
                      'AntennaOffset', 'Completion']

        self.record = dict.fromkeys(fieldnames)

    def load_record(self):

        self.record['NetworkCode'] = self.NetworkCode
        self.record['StationCode'] = self.StationCode
        self.record['ObservationYear'] = self.date.year
        self.record['ObservationMonth'] = self.date.month
        self.record['ObservationDay'] = self.date.day
        self.record['ObservationDOY'] = self.date.doy
        self.record['ObservationFYear'] = self.date.fyear
        self.record['ObservationSTime'] = self.firstObs
        self.record['ObservationETime'] = self.lastObs
        self.record['ReceiverType'] = self.recType
        self.record['ReceiverSerial'] = self.recNo
        self.record['ReceiverFw'] = self.recVers
        self.record['AntennaType'] = self.antType
        self.record['AntennaSerial'] = self.antNo
        self.record['AntennaDome'] = self.antDome
        self.record['Filename'] = self.rinex
        self.record['Interval'] = self.interval
        self.record['AntennaOffset'] = self.antOffset
        self.record['Completion'] = self.completion


class ReadRinex(RinexRecord):

    def read_fields(self, line, record, format_tuple):

        # create the parser object
        formatstr = re.sub(r'\..', '',' '.join(format_tuple).replace('%', '').replace('f', 's').replace('i', 's').replace('-', ''))

        fs = struct.Struct(formatstr)
        parse = fs.unpack_from

        # get the data section by spliting the line using the record text
        data = line.split(record)[0]

        if len(data) < fs.size:
            # line too short, add padding spaces
            f = '%-' + str(fs.size) + 's'
            data = f % line
        elif len(data) > fs.size:
            # line too long! cut
            data = line[0:fs.size]

        fields = list(parse(data))

        # convert each element in the list to float if necessary
        for i, field in enumerate(fields):
            if 'f' in format_tuple[i]:
                try:
                    fields[i] = float(fields[i])
                except ValueError:
                    # invalid number in the field!, replace with something harmless
                    fields[i] = float(2.11)
            elif 'i' in format_tuple[i]:
                try:
                    fields[i] = int(fields[i])
                except ValueError:
                    # invalid number in the field!, replace with something harmless
                    fields[i] = int(1)
            elif 's' in format_tuple[i]:
                fields[i] = fields[i].strip()

        return fields, data

    def format_record(self, record_dict, record, values):

        if type(values) is not list and type(values) is not tuple:
            values = [values]

        data = ''.join(record_dict[record]['format_tuple']) % tuple(values)

        if len('%-60s' % data) > 60:
            # field is too long!! cut to 60 chars
            data = data[0:60]
            self.log_event('Found that record data for ' + record + ' was too long (> 60 chars). Replaced with: ' + data)

        data = '%-60s' % data + record

        return data

    def write_rinex(self, header, new_header):

        if new_header != header:
            try:
                with open(self.rinex_path, 'r') as fileio:
                    rinex = fileio.readlines()
            except Exception:
                raise

            if not any("END OF HEADER" in s for s in rinex):
                raise pyRinexExceptionBadFile('Invalid header: could not find END OF HEADER tag.')

            # find the end of header
            index = [i for i, item in enumerate(rinex) if 'END OF HEADER' in item][0]
            # delete header
            del rinex[0:index+1]
            # add new header
            rinex = new_header + rinex

            try:
                f = open(self.rinex_path, 'w')
                f.writelines(rinex)
                f.close()
            except Exception:
                raise

    def replace_record(self, header, record, new_values):

        if record not in self.required_records.keys():
            raise pyRinexException('Record ' + record + ' not implemented!')

        new_header = []
        for line in header:
            if line.strip().endswith(record):
                new_header += [self.format_record(self.required_records, record, new_values) + '\n']
            else:
                new_header += [line]

        if type(new_values) is not list and type(new_values) is not tuple:
            new_values = [new_values]

        self.log_event('RINEX record replaced: ' + record + ' value: ' + ','.join(map(str, new_values)))

        return new_header

    def log_event(self, desc):

        self.log += [Event(StationCode=self.StationCode, NetworkCode=self.NetworkCode, Description=desc)]

    def insert_comment(self, header, comment):

        # remove the end or header
        index = [i for i, item in enumerate(header) if 'END OF HEADER' in item][0]
        del header[index]

        new_header = header + [self.format_record(self.required_records, 'COMMENT', comment) + '\n']

        new_header += [''.ljust(60, ' ') + 'END OF HEADER\n']

        self.log_event('RINEX COMMENT inserted: ' + comment)

        return new_header

    def check_interval(self):

        interval_record = {'INTERVAL': {'format_tuple': ('%10.3f',), 'found': False, 'default': (30,)}}

        header = self.get_header()
        new_header = []

        for line in header:

            if line.strip().endswith('INTERVAL'):
                # get the first occurrence only!
                record = [key for key in interval_record.keys() if key in line][0]

                interval_record[record]['found'] = True

                fields, _ = self.read_fields(line, 'INTERVAL', interval_record['INTERVAL']['format_tuple'])

                if fields[0] != self.interval:
                    # interval not equal. Replace record
                    new_header += [self.format_record(interval_record, 'INTERVAL', self.interval) + '\n']
                    self.log_event('Wrong INTERVAL record, setting to %i' % self.interval)
                else:
                    # record matches, leave it untouched
                    new_header += [line]
            else:
                # not a critical field, just put it back in
                if not line.strip().endswith('END OF HEADER'):
                    # leave END OF HEADER until the end to add possible missing records
                    new_header += [line]

        # now check that all the records where included! there's missing ones, then force them
        if not interval_record['INTERVAL']['found']:
            new_header += [self.format_record(interval_record, 'INTERVAL', self.interval) + '\n']
            new_header += [self.format_record(self.required_records, 'COMMENT', 'pyRinex: WARN! added interval to fix file!') + '\n']
            self.log_event('INTERVAL record not found, setting to %i' % self.interval)

        new_header += [''.ljust(60, ' ') + 'END OF HEADER\n']

        self.write_rinex(header, new_header)

        return

    def check_header(self):

        header = self.get_header()
        new_header = []

        self.system = ''

        for line in header:

            if any(line.strip().endswith(key) for key in self.required_records.keys()):
                # get the first occurrence only!
                record = [key for key in self.required_records.keys() if key in line][0]

                # mark the record as found
                self.required_records[record]['found'] = True

                fields, _ = self.read_fields(line, record, self.required_records[record]['format_tuple'])

                if record == 'RINEX VERSION / TYPE':
                    # read the information about the RINEX type
                    # save the system to use during TIME OF FIRST OBS
                    self.system = fields[4].strip()

                    self.rinex_version = float(fields[0])

                    # now that we know the version, we can get the first obs
                    first_obs = self.get_firstobs()

                    if first_obs is None:
                        raise pyRinexExceptionBadFile(
                            'Could not find a first observation in RINEX file. Truncated file? Header follows:\n' + ''.join(header))

                    if not self.system in (' ', 'G', 'R', 'S', 'E', 'M'):
                        # assume GPS
                        self.system = 'G'
                        fields[4] = 'G'
                        self.log_event('System set to (G)PS')

                else:
                    # reformat the header line
                    if record == 'TIME OF FIRST OBS' or record == 'TIME OF LAST OBS':
                        if self.system == 'M' and not fields[6].strip():
                            fields[6] = 'GPS'
                            self.log_event('Adding TIME SYSTEM to TIME OF FIRST OBS')
                        # check if the first observation is meaningful or not
                        if record == 'TIME OF FIRST OBS' and (fields[0] != first_obs.year or
                                        fields[1] != first_obs.month or
                                        fields[2] != first_obs.day or
                                        fields[3] != first_obs.hour or
                                        fields[4] != first_obs.minute or
                                        fields[5] != first_obs.second):
                            # bad first observation! replace with the real one
                            fields[0] = first_obs.year
                            fields[1] = first_obs.month
                            fields[2] = first_obs.day
                            fields[3] = first_obs.hour
                            fields[4] = first_obs.minute
                            fields[5] = first_obs.second

                            self.log_event('Bad TIME OF FIRST OBS found -> fixed')

                    if record == 'MARKER NAME':
                        # load the marker name, which RinSum does not return
                        self.marker_name = fields[0].strip().lower()

                # regenerate the fields
                # save to new header
                new_header += [self.format_record(self.required_records, record, fields) + '\n']
            else:
                # not a critical field, just put it back in
                if not line.strip().endswith('END OF HEADER') and not line.strip().endswith('TIME OF LAST OBS') and line.strip() != '':
                    if line.strip().endswith('COMMENT'):
                        # reformat comments (some come in wrong positions!)
                        fields, _ = self.read_fields(line, 'COMMENT', self.required_records['COMMENT']['format_tuple'])
                        new_header += [self.format_record(self.required_records, 'COMMENT', fields) + '\n']
                    else:
                        # leave END OF HEADER until the end to add possible missing records
                        new_header += [line]

        if self.system == '':
            # if we are out of the loop and we could not determine the system, raise error
            raise pyRinexExceptionBadFile('Unfixable RINEX header: could not find RINEX VERSION / TYPE')

        # now check that all the records where included! there's missing ones, then force them
        if not all([item['found'] for item in self.required_records.values()]):
            # get the keys of the missing records
            missing_records = {item: self.required_records[item] for item in self.required_records if self.required_records[item]['found'] == False}

            for record in missing_records.keys():
                if '# / TYPES OF OBSERV' in record:
                    raise pyRinexExceptionBadFile('Unfixable RINEX header: could not find # / TYPES OF OBSERV')

                new_header += [self.format_record(missing_records, record, missing_records[record]['default']) + '\n']
                new_header += [self.format_record(self.required_records, 'COMMENT', 'pyRinex: WARN! default value to fix file!') + '\n']
                self.log_event('Missing required RINEX record added: ' + record)

        new_header += [''.ljust(60,' ') + 'END OF HEADER\n']

        self.write_rinex(header, new_header)

    def IdentifyFile(self, input_file):

        # get the crinez and rinex names
        filename = os.path.basename(input_file)

        self.origin_file = input_file
        self.origin_type = self.identify_type(filename)
        self.local_copy = os.path.abspath(os.path.join(self.rootdir, filename))

        self.rinex = self.to_format(filename, TYPE_RINEX)
        self.crinez = self.to_format(filename, TYPE_CRINEZ)

        # get the paths
        self.crinez_path = os.path.join(self.rootdir, self.crinez)
        self.rinex_path = os.path.join(self.rootdir, self.rinex)

        self.log_event('Origin type is %i' % self.origin_type)

        return

    def CreateTempDirs(self):

        self.rootdir = os.path.join('production', 'rinex')
        self.rootdir = os.path.join(self.rootdir, str(uuid.uuid4()))

        # create a production folder to analyze the rinex file
        if not os.path.exists(self.rootdir):
            os.makedirs(self.rootdir)

        return

    def Uncompress(self):

        if self.origin_type in (TYPE_CRINEZ, TYPE_CRINEX):

            size = os.path.getsize(self.local_copy)

            # run crz2rnx with timeout structure
            cmd = pyRunWithRetry.RunCommand('crz2rnx -f -d ' + self.local_copy, 30)
            try:
                _, err = cmd.run_shell()
            except pyRunWithRetry.RunCommandWithRetryExeception as e:
                # catch the timeout except and pass it as a pyRinexException
                raise pyRinexException(str(e))

            # the uncompressed-unhatanaked file size must be at least > than the crinez
            if os.path.isfile(self.rinex_path):
                if err and os.path.getsize(self.rinex_path) <= size:
                    raise pyRinexExceptionBadFile("Error in ReadRinex.__init__ -- crz2rnx: error and empty file: " + self.origin_file + ' -> ' + err)
            else:
                if err:
                    raise pyRinexException('Could not create RINEX file. crz2rnx stderr follows: ' + err)
                else:
                    raise pyRinexException('Could not create RINEX file. Unknown reason. Possible problem with crz2rnx?')

        elif self.origin_type is TYPE_RINEZ:
            # create an unzip script
            create_unzip_script(os.path.join(self.rootdir, 'uncompress.sh'))

            cmd = pyRunWithRetry.RunCommand('./uncompress.sh -f -d ' + self.local_copy, 30, self.rootdir)
            try:
                _, _ = cmd.run_shell()
            except pyRunWithRetry.RunCommandWithRetryExeception as e:
                # catch the timeout except and pass it as a pyRinexException
                raise pyRinexException(str(e))

    def ConvertRinex3to2(self):

        # most programs still don't support RINEX 3 (partially implemented in this code)
        # convert to RINEX 2.11 using RinEdit
        cmd = pyRunWithRetry.RunCommand('RinEdit --IF %s --OF %s.t --ver2' % (self.rinex, self.rinex), 15, self.rootdir)

        try:
            out, _ = cmd.run_shell()

            if 'exception' in out.lower():
                raise pyRinexExceptionBadFile('RinEdit returned error converting to RINEX 2.11:\n' + out)

            if not os.path.exists(self.rinex_path + '.t'):
                raise pyRinexExceptionBadFile('RinEdit failed to convert to RINEX 2.11:\n' + out)

            # if all ok, move converted file to rinex_path
            os.remove(self.rinex_path)
            move(self.rinex_path + '.t', self.rinex_path)
            # change version
            self.rinex_version = 2.11

            self.log_event('Origin file was RINEX 3 -> Converted to 2.11')

        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(str(e))

    def RunRinSum(self):
        # run RinSum to get file information
        cmd = pyRunWithRetry.RunCommand('RinSum --notable ' + self.rinex_path, 45)  # DDG: increased from 21 to 45.
        try:
            output, _ = cmd.run_shell()
        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(str(e))

        # write RinSum output to a log file (debug purposes)
        info = open(self.rinex_path + '.log', 'w')
        info.write(output)
        info.close()

        return output

    def isValidRinexName(self, filename):

        filename = os.path.basename(filename)
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([do]\.[Z])$', filename)

        if sfile:
            return True
        else:
            sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([od])$', filename)

            if sfile:
                return True
            else:
                return False

    def __init__(self, NetworkCode, StationCode, origin_file, no_cleanup=False, allow_multiday=False):
        """
        pyRinex initialization
        if file is multiday, DO NOT TRUST date object for initial file. Only use pyRinex objects contained in the multiday list
        """
        RinexRecord.__init__(self, NetworkCode, StationCode)

        self.no_cleanup = no_cleanup

        # check that the rinex file name is valid!
        if not self.isValidRinexName(origin_file):
            raise pyRinexException('File name does not follow the RINEX(Z)/CRINEX(Z) naming convention: %s' % (os.path.basename(origin_file)))

        self.CreateTempDirs()

        self.IdentifyFile(origin_file)

        copy(origin_file, self.rootdir)

        if self.origin_type in (TYPE_CRINEZ, TYPE_CRINEX, TYPE_RINEZ):
            self.Uncompress()

        # check basic infor in the rinex header to avoid problems with RinSum
        self.check_header()

        if self.rinex_version >= 3:
            self.ConvertRinex3to2()

        # process the output
        self.parse_output(self.RunRinSum())

        # DDG: new interval checking after running RinSum
        # check the sampling interval
        self.check_interval()

        # check for files that have more than one day inside (yes, there are some like this... amazing)
        # condition is: the start and end date don't match AND
        # either there is more than two hours in the second day OR
        # there is more than one day of data
        if self.datetime_lastObs.date() != self.datetime_firstObs.date() and not allow_multiday:
            # more than one day in this file. Is there more than one hour? (at least in principle, based on the time)
            first_obs = datetime.datetime(self.datetime_lastObs.date().year, self.datetime_lastObs.date().month, self.datetime_lastObs.date().day)
            if (self.datetime_lastObs - first_obs).seconds >= 3600:
                # the file has more than one day in it...
                # use teqc to window the data
                if not self.multiday_handle(origin_file):
                    return
            else:
                # window the data to remove superfluous epochs
                last_obs = datetime.datetime(self.datetime_firstObs.date().year, self.datetime_firstObs.date().month, self.datetime_firstObs.date().day, 23, 59, 59)
                self.window_data(end=last_obs)
                self.log_event('RINEX had incomplete epochs (or < 1 hr) outside of the corresponding UTC day -> Data windowed to one UTC day.')

        # reported date for this file is session/2
        self.date = pyDate.Date(datetime=self.datetime_firstObs+(self.datetime_lastObs-self.datetime_firstObs)/2)

        # DDG: calculate the completion of the file (at sampling rate)
        # completion of day
        # done after binning so that if the file is a multiday we don't get a bad completion
        self.completion = self.epochs * self.interval / 86400
        # completion of time window in file
        self.rel_completion = self.epochs * self.interval / ((self.datetime_lastObs - self.datetime_firstObs).total_seconds() + self.interval)

        # load the RinexRecord class
        self.load_record()

        return

    def multiday_handle(self, origin_file):
        # split the file
        self.split_file()

        continue_statements = True

        if len(self.multiday_rnx_list) > 1:
            # truly a multiday file
            self.multiday = True
            # self.log_event('RINEX file is multiday -> generated $i RINEX files' % len(self.multiday_rnx_list))
            continue_statements = True

        elif len(self.multiday_rnx_list) == 1:
            # maybe one of the files has a single epoch in it. Drop the current rinex and use the binned version
            self.cleanup()
            temp_path = self.multiday_rnx_list[0].rootdir
            # keep the log
            self.log_event('RINEX appeared to be multiday but had incomplete epochs (or < 1 hr) -> Data windowed to one UTC day.')
            temp_log = self.log
            # set to no cleanup so that the files survive the __init__ statement
            self.multiday_rnx_list[0].no_cleanup = True
            # reinitialize self
            self.__init__(self.multiday_rnx_list[0].NetworkCode, self.multiday_rnx_list[0].StationCode,
                          self.multiday_rnx_list[0].rinex_path)
            # the origin file should still be the rinex passed to init the object, not the multiday file
            self.origin_file = origin_file
            # remove the temp directory
            self.log += temp_log

            rmtree(temp_path)
            # now self points the the binned version of the rinex
            continue_statements = False

        return continue_statements

    def split_file(self):

        # run in the local folder to get the files inside rootdir
        cmd = pyRunWithRetry.RunCommand('teqc -n_GLONASS 30 -tbin 1d rnx ' + self.rinex, 45, self.rootdir)
        try:
            _, err = cmd.run_shell()
        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(str(e))

        # successfully binned the file
        # delete current file and rename the new files
        os.remove(self.rinex_path)

        # now we should have as many files named rnxDDD0.??o as days inside the RINEX
        for file in os.listdir(self.rootdir):
            if file[0:3] == 'rnx' and self.identify_type(file) is TYPE_RINEX:
                # rename file
                move(os.path.join(self.rootdir, file), os.path.join(self.rootdir, file.replace('rnx', self.StationCode)))
                # get the info for this file
                try:
                    rnx = ReadRinex(self.NetworkCode, self.StationCode, os.path.join(self.rootdir, file.replace('rnx', self.StationCode)))
                    # append this rinex object to the multiday list
                    self.multiday_rnx_list.append(rnx)
                except (pyRinexException, pyRinexExceptionBadFile):
                    # there was a problem with one of the multiday files. Do not append
                    pass

        return

    def parse_output(self, output):

        try:
            self.x, self.y, self.z = [float(x) for x in re.findall('Position\s+\(XYZ,m\)\s:\s\(\s*(\-?\d+\.\d+)\,\s*(-?\d+\.\d+)\,\s*(-?\d+\.\d+)', output, re.MULTILINE)[0]]
            self.lat, self.lon, self.h = ecef2lla([self.x, self.y, self.z])
        except Exception:
            self.x, self.y, self.z = (None, None, None)

        try:
            self.antOffset, self.antOffsetN, self.antOffsetE = [float(x) for x in re.findall('Antenna\sDelta\s+\(HEN,m\)\s:\s\(\s*(\-?\d+\.\d+)\,\s*(-?\d+\.\d+)\,\s*(-?\d+\.\d+)', output, re.MULTILINE)[0]]
        except Exception:
            self.antOffset, self.antOffsetN, self.antOffsetE = (0, 0, 0)
            self.log_event('Problem parsing ANTENNA OFFSETS, setting to 0')

        try:
            self.recNo, self.recType, self.recVers = [x.strip() for x in re.findall('Rec#:([^,]*),\s*Type:([^,]*),\s*Vers:(.*)', output, re.MULTILINE)[0]]
        except Exception:
            self.recNo, self.recType, self.recVers = ('', '', '')
            self.log_event('Problem parsing REC # / TYPE / VERS, setting to EMPTY')

        try:
            self.marker_number = re.findall('^Marker number\s*:\s*(.*)', output, re.MULTILINE)[0]
        except Exception:
            self.marker_number = 'NOT FOUND'
            self.log_event('No MARKER NUMBER found, setting to NOT FOUND')

        try:
            self.antNo, AntDome = [x.strip() for x in re.findall('Antenna\s*#\s*:([^,]*),\s*Type\s*:\s*(.*)', output, re.MULTILINE)[0]]

            if ' ' in AntDome:
                self.antType = AntDome.split()[0]
                self.antDome = AntDome.split()[1]
            else:
                self.antType = AntDome
                self.antDome = 'NONE'
                self.log_event('No dome found, set to NONE')

        except Exception:
            self.antNo, self.antType, self.antDome = ('UNKNOWN', 'UNKNOWN', 'NONE')
            self.log_event('Problem parsing ANT # / TYPE, setting to UNKNOWN NONE')

        try:
            self.interval = float(re.findall('^Computed interval\s*(\d+\.\d+)', output, re.MULTILINE)[0])
        except Exception:
            self.interval = 0
            self.log_event('Problem interval, setting to 0')

        try:
            self.epochs = float(re.findall('^There were\s*(\d+)\s*epochs', output, re.MULTILINE)[0])
        except Exception:
            self.epochs = 0
            self.log_event('Problem parsing epochs, setting to 0')

        # stop here is epochs of interval is invalid
        if self.interval == 0:
            if self.epochs > 0:
                raise pyRinexExceptionSingleEpoch('RINEX interval equal to zero. Single epoch or bad RINEX file. Reported epochs in file were %s' % (self.epochs))
            else:
                raise pyRinexExceptionSingleEpoch('RINEX interval equal to zero. Single epoch or bad RINEX file. No epoch information to report. The output from RinSum was:\n' + output)

        elif self.interval > 120:
            raise pyRinexExceptionBadFile('RINEX sampling interval > 120s. The output from RinSum was:\n' + output)

        elif self.epochs * self.interval < 3600:
                raise pyRinexExceptionBadFile('RINEX file with < 1 hr of observation time. The output from RinSum was:\n' + output)

        try:
            yy, mm, dd, hh, MM, ss = [int(x) for x in re.findall('^Computed first epoch:\s*(\d+)\/(\d+)\/(\d+)\s(\d+):(\d+):(\d+)', output, re.MULTILINE)[0]]
            yy = check_year(yy)
            self.datetime_firstObs = datetime.datetime(yy, mm, dd, hh, MM, ss)
            self.firstObs = self.datetime_firstObs.strftime('%Y/%m/%d %H:%M:%S')

            yy, mm, dd, hh, MM, ss = [int(x) for x in re.findall('^Computed last\s*epoch:\s*(\d+)\/(\d+)\/(\d+)\s(\d+):(\d+):(\d+)', output, re.MULTILINE)[0]]
            yy = check_year(yy)
            self.datetime_lastObs = datetime.datetime(yy, mm, dd, hh, MM, ss)
            self.lastObs = self.datetime_lastObs.strftime('%Y/%m/%d %H:%M:%S')

            if self.datetime_lastObs <= self.datetime_firstObs:
                # bad rinex! first obs > last obs
                raise pyRinexExceptionBadFile('Last observation (' + self.lastObs + ') <= first observation (' + self.firstObs + ')')

        except Exception:
            raise pyRinexException(self.rinex_path + ': error in ReadRinex.parse_output: the output for first/last obs is invalid. The output from RinSum was:\n' + output)

        try:
            self.size = int(re.findall('^Computed file size:\s*(\d+)', output, re.MULTILINE)[0])
        except Exception:
            self.size = 0
            self.log_event('Problem parsing size, setting to 0')

        try:
            self.obs_types = int(re.findall('GPS Observation types\s*\((\d+)\)', output, re.MULTILINE)[0])
        except Exception:
            self.obs_types = 0
            self.log_event('Problem parsing observation types, setting to 0')

        warn = re.findall('(.*Warning : Failed to read header: text 0:Incomplete or invalid header.*)', output, re.MULTILINE)
        if warn:
            raise pyRinexException("Warning in ReadRinex.parse_output: " + warn[0])

        warn = re.findall('(.*unexpected exception.*)', output, re.MULTILINE)
        if warn:
            raise pyRinexException("unexpected exception in ReadRinex.parse_output: " + warn[0])

        warn = re.findall('(.*Exception.*)', output, re.MULTILINE)
        if warn:
            raise pyRinexException("Exception in ReadRinex.parse_output: " + warn[0])

        warn = re.findall('(.*no data found. Are time limits wrong.*)', output, re.MULTILINE)
        if warn:
            raise pyRinexException('RinSum: no data found. Are time limits wrong for file ' + self.rinex + ' details:' + warn[0])

        # remove non-utf8 chars
        self.recNo   = self.recNo.decode('utf-8', 'ignore').encode('utf-8')
        self.recType = self.recType.decode('utf-8', 'ignore').encode('utf-8')
        self.recVers = self.recVers.decode('utf-8', 'ignore').encode('utf-8')
        self.antNo   = self.antNo.decode('utf-8', 'ignore').encode('utf-8')
        self.antType = self.antType.decode('utf-8', 'ignore').encode('utf-8')
        self.antDome = self.antDome.decode('utf-8', 'ignore').encode('utf-8')

    def get_firstobs(self):

        if self.rinex_version < 3:
            fs = struct.Struct('1s2s1s2s1s2s1s2s1s2s11s2s1s3s')
        else:
            fs = struct.Struct('2s4s1s2s1s2s1s2s1s2s11s2s1s3s')

        parse = fs.unpack_from

        date = None
        with open(self.rinex_path,'r') as fileio:

            found = False
            for line in fileio:
                if 'END OF HEADER' in line:
                    found = True
                    break

            if found:
                skip = 0
                for line in fileio:
                    if skip == 0:
                        fields = list(parse(line))

                        if int(fields[12]) <= 1: # OK FLAG
                            # read first observation
                            year = int(fields[1])
                            month = int(fields[3])
                            day = int(fields[5])
                            hour = int(fields[7])
                            minute = int(fields[9])
                            second = float(fields[10])

                            try:
                                date = pyDate.Date(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
                            except pyDate.pyDateException as e:
                                raise pyRinexExceptionBadFile(str(e))

                            break
                        elif int(fields[12]) > 1:
                            # event, skip lines indicated in next field
                            skip = int(fields[13])
                    else:
                        skip -= 1

        return date

    def get_header(self):

        header = []
        # retry reading. Every now and then there is a problem during file read.
        for i in range(2):
            try:
                with open(self.rinex_path,'r') as fileio:

                    for line in fileio:
                        header.append(line)
                        if 'END OF HEADER' in line:
                            break
                    break
            except IOError:
                # try again
                if i == 0:
                    continue
                else:
                    raise

        return header

    def auto_coord(self, brdc, chi_limit=3):
        # use gamit's sh_rx2apr to obtain a coordinate of the station

        # do not work with the original file. Decimate and remove other systems (to increase speed)
        try:
            # make a copy to decimate and remove systems to help sh_rx2apr
            rnx = ReadRinex(self.NetworkCode, self.StationCode, self.rinex_path)

            if rnx.interval < 15:
                rnx.decimate(30)
                self.log_event('Decimating to 30 seconds to run auto_coord')

            # remove the other systems that sh_rx2apr does not use
            if rnx.system is 'M':
                rnx.remove_systems()
                self.log_event('Removing systems S, R and E to run auto_coord')

            # copy brdc orbit
            copyfile(brdc.brdc_path, os.path.join(rnx.rootdir, brdc.brdc_filename))

        except pyRinexException as e:
            print str(e)
            # ooops, something went wrong, try with local file (without removing systems or decimating)
            rnx = self
            # raise pyRinexExceptionBadFile('During decimation or remove_systems (to run auto_coord), teqc returned: %s' + str(e))

        cmd = pyRunWithRetry.RunCommand('sh_rx2apr -site ' + rnx.rinex + ' -nav ' + brdc.brdc_filename + ' -chi ' + str(chi_limit), 40, rnx.rootdir)
        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if err != '':
            raise pyRinexExceptionNoAutoCoord(err + '\n' + out)
        else:
            # check that the Final chi**2 is < 3
            for line in out.split('\n'):
                if '* Final sqrt(chi**2/n)' in line:
                    chi = line.split()[-1]

                    if chi == 'NaN':
                        raise pyRinexExceptionNoAutoCoord('chi2 = NaN! ' + err + '\n' + out)

                    elif float(chi) < chi_limit:
                        # open the APR file and read the coordinates
                        if os.path.isfile(os.path.join(rnx.rootdir, rnx.rinex[0:4] + '.apr')):
                            with open(os.path.join(rnx.rootdir, rnx.rinex[0:4] + '.apr')) as apr:
                                line = apr.readline().split()

                                self.x = float(line[1])
                                self.y = float(line[2])
                                self.z = float(line[3])

                                self.lat, self.lon, self.h = ecef2lla([self.x, self.y, self.z])

                            return (float(line[1]), float(line[2]), float(line[3])), (self.lat, self.lon, self.h)

            raise pyRinexExceptionNoAutoCoord(out + '\nLIMIT FOR CHI**2 was %i' % chi_limit)

    def window_data(self, start=None, end=None, copyto=None):
        """
        Window the RINEX data using TEQC
        :param start: a start datetime or self.firstObs if None
        :param end: a end datetime or self.lastObs if None
        :return:
        """
        if start is None:
            start = self.datetime_firstObs
            self.log_event('Setting start = first obs in window_data')

        if end is None:
            end = self.datetime_lastObs
            self.log_event('Setting end = last obs in window_data')

        cmd = pyRunWithRetry.RunCommand('teqc -n_GLONASS 30 -igs -st %i%02i%02i%02i%02i%02i -e %i%02i%02i%02i%02i%02i +obs %s.t %s' % (
                start.year, start.month, start.day, start.hour, start.minute, start.second,
                end.year, end.month, end.day, end.hour, end.minute, end.second, self.rinex_path, self.rinex_path), 5)

        out, err = cmd.run_shell()

        if not 'teqc: failure to read' in str(err):
            # delete the original file and replace with .t
            if copyto is None:
                os.remove(self.rinex_path)
                move(self.rinex_path + '.t', self.rinex_path)
                self.datetime_firstObs = start
                self.datetime_lastObs = end
                self.firstObs = self.datetime_firstObs.strftime('%Y/%m/%d %H:%M:%S')
                self.lastObs = self.datetime_lastObs.strftime('%Y/%m/%d %H:%M:%S')
            else:
                move(self.rinex_path + '.t', copyto)
        else:
            raise pyRinexException(err)

        return

    def decimate(self, decimate_rate, copyto=None):
        # if copy to is passed, then the decimation is done on the copy of the file, not on the current rinex.
        # otherwise, decimation is done in current rinex
        if copyto is not None:
            copyfile(self.rinex_path, copyto)
        else:
            copyto = self.rinex_path
            self.interval = decimate_rate

        if self.rinex_version < 3:
            cmd = pyRunWithRetry.RunCommand('teqc -n_GLONASS 30 -igs -O.dec %i +obs %s.t %s' % (decimate_rate, copyto, copyto), 5)
            # leave errors un-trapped on purpose (will raise an error to the parent)
        else:
            cmd = pyRunWithRetry.RunCommand('RinEdit --IF %s --OF %s.t --TN %i --TB %i,%i,%i,%i,%i,%i' % (os.path.basename(copyto), os.path.basename(copyto), decimate_rate, self.date.year, self.date.month, self.date.day, 0, 0, 0), 15, self.rootdir)
        out, err = cmd.run_shell()

        if not 'teqc: failure to read' in str(err):
            # delete the original file and replace with .t
            os.remove(copyto)
            move(copyto + '.t', copyto)
        else:
            raise pyRinexException(err)

        self.log_event('RINEX decimated to %is (applied to %s)' % (decimate_rate, str(copyto)))

        return

    def remove_systems(self, systems=('R', 'E', 'S'), copyto=None):
        # if copy to is passed, then the system removal is done on the copy of the file, not on the current rinex.
        # other wise, system removal is done to current rinex
        if copyto is not None:
            copyfile(self.rinex_path, copyto)
        else:
            copyto = self.rinex_path

        if self.rinex_version < 3:
            rsys = '-' + ' -'.join(systems)
            cmd = pyRunWithRetry.RunCommand('teqc -n_GLONASS 30 -igs %s +obs %s.t %s' % (rsys, copyto, copyto), 5)
        else:
            rsys = ' --DS '.join(systems)
            cmd = pyRunWithRetry.RunCommand('RinEdit --IF %s --OF %s.t --DS %s' % (os.path.basename(copyto), os.path.basename(copyto), rsys), 15, self.rootdir)

        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if not 'teqc: failure to read' in str(err):
            # delete the original file and replace with .t
            os.remove(copyto)
            move(copyto + '.t', copyto)
            # if working on local copy, reload the rinex information
            if copyto == self.rinex_path:
                # reload information from this file
                self.parse_output(self.RunRinSum())
        else:
            raise pyRinexException(err)

        self.log_event('Removed systems %s (applied to %s)' % (','.join(systems), str(copyto)))

        return

    def normalize_header(self, NewValues, brdc=None, x=None, y=None, z=None):
        # this function gets rid of the heaer information and replaces it with the station info (trusted)
        # should be executed before calling PPP or before rebuilding the Archive
        # new function now accepts a dictionary OR a station info object

        if type(NewValues) is pyStationInfo.StationInfo:
            if NewValues.date is not None and NewValues.date != self.date:
                raise pyRinexException('The StationInfo object was initialized for a different date than that of the RINEX file')
            else:
                NewValues = NewValues.currentrecord

        fieldnames = ['AntennaHeight', 'AntennaNorth', 'AntennaEast', 'ReceiverCode', 'ReceiverVers', 'ReceiverSerial', 'AntennaCode', 'RadomeCode', 'AntennaSerial']
        rinex_field = ['AntennaOffset', None, None, 'ReceiverType', 'ReceiverFw', 'ReceiverSerial', 'AntennaType', 'AntennaDome', 'AntennaSerial']

        header = self.get_header()
        new_header = header

        # set values
        for i, field in enumerate(fieldnames):
            if field not in NewValues.keys():
                if rinex_field[i] is not None:
                    NewValues[field] = self.record[rinex_field[i]]
                else:
                    NewValues[field] = 0.0

        if self.marker_name != self.StationCode:
            new_header = self.replace_record(new_header, 'MARKER NAME', self.StationCode.upper())
            new_header = self.insert_comment(new_header, 'PREV MARKER NAME: ' + self.marker_name.upper())
            self.marker_name = self.StationCode

        if (NewValues['ReceiverCode'] != self.recType or
            NewValues['ReceiverVers'] != self.recVers or
            NewValues['ReceiverSerial'] != self.recNo):

            new_header = self.replace_record(new_header, 'REC # / TYPE / VERS', (NewValues['ReceiverSerial'], NewValues['ReceiverCode'], NewValues['ReceiverVers']))

            if NewValues['ReceiverSerial'] != self.recNo:
                new_header = self.insert_comment(new_header, 'PREV REC #   : ' + self.recNo)
                self.recNo = NewValues['ReceiverSerial']
            if NewValues['ReceiverCode'] != self.recType:
                new_header = self.insert_comment(new_header, 'PREV REC TYPE: ' + self.recType)
                self.recType = NewValues['ReceiverCode']
            if NewValues['ReceiverVers'] != self.recVers:
                new_header = self.insert_comment(new_header, 'PREV REC VERS: ' + self.recVers)
                self.recVers = NewValues['ReceiverVers']

        if (NewValues['AntennaCode'] != self.antType or
            NewValues['AntennaSerial'] != self.antNo or
            NewValues['RadomeCode'] != self.antDome):

            new_header = self.replace_record(new_header, 'ANT # / TYPE', (NewValues['AntennaSerial'], '%-15s' % NewValues['AntennaCode'] + ' ' + NewValues['RadomeCode']))

            if NewValues['AntennaCode'] != self.antType:
                new_header = self.insert_comment(new_header, 'PREV ANT #   : ' + self.antType)
                self.antType = NewValues['AntennaCode']
            if NewValues['AntennaSerial'] != self.antNo:
                new_header = self.insert_comment(new_header, 'PREV ANT TYPE: ' + self.antNo)
                self.antNo = NewValues['AntennaSerial']
            if NewValues['RadomeCode'] != self.antDome:
                new_header = self.insert_comment(new_header, 'PREV ANT DOME: ' + self.antDome)
                self.antDome = NewValues['RadomeCode']

        if (NewValues['AntennaHeight'] != self.antOffset or
            NewValues['AntennaNorth'] != self.antOffsetN or
            NewValues['AntennaEast'] != self.antOffsetE):

            new_header = self.replace_record(new_header, 'ANTENNA: DELTA H/E/N', (NewValues['AntennaHeight'], NewValues['AntennaEast'], NewValues['AntennaNorth']))

            if NewValues['AntennaHeight'] != self.antOffset:
                new_header = self.insert_comment(new_header, 'PREV DELTA H: %.3f' % self.antOffset)
                self.antOffset = float(NewValues['AntennaHeight'])
            if NewValues['AntennaNorth'] != self.antOffsetN:
                new_header = self.insert_comment(new_header, 'PREV DELTA N: %.3f' % self.antOffsetN)
                self.antOffsetN = float(NewValues['AntennaNorth'])
            if NewValues['AntennaEast'] != self.antOffsetE:
                new_header = self.insert_comment(new_header, 'PREV DELTA E: %.3f' % self.antOffsetE)
                self.antOffsetE = float(NewValues['AntennaEast'])

        # always replace the APPROX POSITION XYZ
        if x is None and brdc is None and self.x is None:
            raise pyRinexException(
                'Cannot normalize the header\'s APPROX POSITION XYZ without a coordinate or a valid broadcast ephemeris object')

        elif self.x is None and brdc is not None:
            self.auto_coord(brdc)

        elif x is not None:
            self.x = x
            self.y = y
            self.z = z

        new_header = self.replace_record(new_header, 'APPROX POSITION XYZ', (self.x, self.y, self.z))

        new_header = self.insert_comment(new_header, 'APPROX POSITION SET TO AUTONOMOUS SOLUTION')
        new_header = self.insert_comment(new_header, 'HEADER NORMALIZED BY pyRinex ON ' + datetime.datetime.now().strftime('%Y/%m/%d %H:%M'))

        self.write_rinex(header, new_header)

        return

    def apply_file_naming_convention(self):
        """
        function to rename a file to make it consistent with the RINEX naming convention
        :return:
        """
        # is the current rinex filename valid?
        fileparts = Utils.parse_crinex_rinex_filename(self.rinex)

        if fileparts:
            doy = int(fileparts[1])
            year = int(Utils.get_norm_year_str(fileparts[3]))
        else:
            # invalid RINEX filename! Assign some values to the variables
            doy = 0
            year = 1900

        if self.record['ObservationDOY'] != doy or self.record['ObservationYear'] != year:
            # this if still remains here but we do not allow this condition any more to happen. See process_crinex_file -> if Result...
            # NO! rename the file before moving to the archive
            filename = self.StationCode + self.date.ddd() + '0.' + self.date.yyyy()[2:4] + 'o'
            # rename file
            self.rename(filename)

    def move_origin_file(self, path, destiny_type=TYPE_CRINEZ):
        # this function moves the ARCHIVE file (or repository) to another location indicated by path
        # can also specify other types, but assumed to be CRINEZ by default
        # it also makes sure that it doesn' overwrite any existing file

        if not os.path.isabs(path):
            raise pyRinexException('Destination must be an absolute path')

        if destiny_type is TYPE_CRINEZ:
            dst = self.crinez
        elif destiny_type is TYPE_RINEX:
            dst = self.rinex
        else:
            dst = self.to_format(self.rinex, destiny_type)

        filename = ''
        # determine action base on origin type
        if self.origin_type == destiny_type:
            # intelligent move (creates folder and checks for file existence)
            # origin and destiny match, do the thing directly
            filename = Utils.move(self.origin_file, os.path.join(path, dst))
        else:
            # if other types are requested, or origin is not the destiny type, then use local file and delete the
            if destiny_type is TYPE_RINEX:
                filename = Utils.move(self.rinex_path, os.path.join(path, dst))

            elif destiny_type is TYPE_CRINEZ:
                filename = self.compress_local_copyto(path)

            elif destiny_type is TYPE_CRINEX:
                cmd = pyRunWithRetry.RunCommand('rnx2crx -f ' + self.rinex_path, 45)
                try:
                    _, err = cmd.run_shell()

                    if os.path.getsize(os.path.join(self.rootdir, self.to_format(self.rinex, TYPE_CRINEX))) == 0:
                        raise pyRinexException('Error in move_origin_file: compressed version of ' + self.rinex_path + ' has zero size!')
                except pyRunWithRetry.RunCommandWithRetryExeception as e:
                    # catch the timeout except and pass it as a pyRinexException
                    raise pyRinexException(str(e))

            elif destiny_type is TYPE_RINEZ:
                raise pyRinexException('pyRinex will not natively generate a RINEZ file.')

        # to keep everything consistent, also change the local copies of the file
        if filename != '':
            self.rename(filename)
            # delete original (if the dest exists!)
            if os.path.isfile(self.origin_file):
                if os.path.isfile(os.path.join(path, dst)):
                    os.remove(self.origin_file)
                else:
                    raise pyRinexException('New \'origin_file\' (%s) does not exist!' % os.path.isfile(os.path.join(path, dst)))

            # change origin file reference
            self.origin_file = os.path.join(path, dst)
            self.origin_type = destiny_type

            self.log_event('Origin moved to %s and converted to %i' % (self.origin_file, destiny_type))

        return filename

    def compress_local_copyto(self, path):
        # this function compresses and moves the local copy of the rinex
        # meant to be used when a multiday rinex file is encountered and we need to move it to the repository

        # compress the rinex into crinez. Make the filename
        crinez = self.to_format(self.rinex, TYPE_CRINEZ)

        # we make the crinez again (don't use the existing from the database) to apply any corrections
        # made during the __init__ stage. Notice the -f in rnx2crz
        cmd = pyRunWithRetry.RunCommand('rnx2crz -f ' + self.rinex_path, 45)
        try:
            _, err = cmd.run_shell()

            if os.path.getsize(os.path.join(self.rootdir, crinez)) == 0:
                raise pyRinexException('Error in compress_local_copyto: compressed version of ' + self.rinex_path + ' has zero size!')
        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(str(e))

        filename = Utils.copyfile(os.path.join(self.rootdir, crinez), os.path.join(path, crinez))

        self.log_event('Created CRINEZ from local copy and copied to %s' % path)

        return filename

    def rename(self, new_name=None, NetworkCode=None, StationCode=None):

        # function that renames the local crinez and rinex file based on the provided information
        # it also changes the variables in the object to reflect this change
        # new name can be any valid format (??d.Z, .??o, ??d, ??o.Z)

        if new_name:
            rinex = os.path.basename(self.to_format(new_name, TYPE_RINEX))
            # do not continue executing unless there is a REAL change!
            if rinex != self.rinex:
                crinez = os.path.basename(self.to_format(new_name, TYPE_CRINEZ))

                # rename the rinex
                if os.path.isfile(self.rinex_path):
                    move(self.rinex_path, os.path.join(self.rootdir, rinex))

                self.rinex_path = os.path.join(self.rootdir, rinex)

                # rename the files
                # check if local crinez exists (possibly made by compress_local_copyto)
                if os.path.isfile(self.crinez_path):
                    move(self.crinez_path, os.path.join(self.rootdir, crinez))

                self.crinez_path = os.path.join(self.rootdir, crinez)

                # rename the local copy of the origin file (if exists)
                # only cases that need to be renamed (again, IF they exist; they shouldn't, but just in case)
                # are RINEZ and CRINEX since RINEX and CRINEZ are renamed above
                if os.path.isfile(self.local_copy):
                    if self.origin_type is TYPE_RINEZ:
                        local = os.path.basename(self.to_format(new_name, TYPE_RINEZ))
                        move(self.local_copy, os.path.join(self.rootdir, local))
                    elif self.origin_type is TYPE_CRINEX:
                        local = os.path.basename(self.to_format(new_name, TYPE_CRINEX))
                        move(self.local_copy, os.path.join(self.rootdir, local))

                self.crinez = crinez
                self.rinex = rinex

                self.log_event('RINEX/CRINEZ renamed to %s' % rinex)

                # update the database dictionary record
                self.record['Filename'] = self.rinex

        # we don't touch the metadata StationCode and NetworkCode unless explicitly passed
        if NetworkCode:
            self.NetworkCode = NetworkCode.strip().lower()
            self.record['NetworkCode'] = NetworkCode.strip().lower()

        if StationCode:
            self.StationCode = StationCode.strip().lower()
            self.record['StationCode'] = StationCode.strip().lower()

        return

    @staticmethod
    def identify_type(filename):

        # get the type of file passed
        filename = os.path.basename(filename)

        if filename.endswith('d.Z'):
            return TYPE_CRINEZ
        elif filename.endswith('o'):
            return TYPE_RINEX
        elif filename.endswith('o.Z'):
            return TYPE_RINEZ
        elif filename.endswith('d'):
            return TYPE_CRINEX
        else:
            raise pyRinexException('Invalid filename format: ' + filename)

    def to_format(self, filename, to_type):

        path = os.path.dirname(filename)
        filename = os.path.basename(filename)
        type = self.identify_type(filename)

        if type in (TYPE_RINEX, TYPE_CRINEX):
            filename = filename[0:-1]
        elif type in (TYPE_CRINEZ, TYPE_RINEZ):
            filename = filename[0:-3]
        else:
            raise pyRinexException('Invalid filename format: ' + filename)

        # join the path to the file again
        filename = os.path.join(path, filename)

        if to_type is TYPE_CRINEX:
            return filename + 'd'
        elif to_type is TYPE_CRINEZ:
            return filename + 'd.Z'
        elif to_type is TYPE_RINEX:
            return filename + 'o'
        elif to_type is TYPE_RINEZ:
            return filename + 'o.Z'
        else:
            raise pyRinexException('Invalid to_type format. Accepted formats: CRINEX (.??d), CRINEZ (.??d.Z), RINEX (.??o) and RINEZ (.??o.Z)')

    def cleanup(self):
        if self.rinex_path and not self.no_cleanup:
            # remove all the directory contents
            try:
                rmtree(self.rootdir)
            except OSError:
                # something was not found, ignore (we are deleting anyways)
                pass

            # if it's a multiday rinex, delete the multiday objects too
            if self.multiday:
                for Rnx in self.multiday_rnx_list:
                    Rnx.cleanup()

        return

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self

    def __add__(self, other):

        if not isinstance(other, ReadRinex):
            raise pyRinexException('type: '+type(other)+' invalid.  Can only splice two RINEX objects.')

        if self.StationCode != other.StationCode:
            raise pyRinexException('Cannot splice together two different stations!')

        # determine which one goes first
        if other.datetime_firstObs > self.datetime_firstObs:
            f1 = self
            f2 = other
        else:
            f1 = other
            f2 = self

        # now splice files
        cmd = pyRunWithRetry.RunCommand('teqc -n_GLONASS 30 -igs +obs %s.t %s %s' % (f1.rinex_path, f1.rinex_path, f2.rinex_path), 5)

        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if not 'teqc: failure to read' in str(err):
            filename = Utils.move(f1.rinex_path + '.t', f1.rinex_path)
            return ReadRinex(self.NetworkCode, self.StationCode, filename, allow_multiday=True)
        else:
            raise pyRinexException(err)

    def __repr__(self):
        return 'pyRinex.ReadRinex(' + self.NetworkCode + ', ' + self.StationCode + ', ' + str(self.date.year) + ', ' + str(self.date.doy) + ')'

def main():
    # for testing purposes
    rnx = ReadRinex('RNX','chac','chac0010.17o')

if __name__ == '__main__':
    main()
