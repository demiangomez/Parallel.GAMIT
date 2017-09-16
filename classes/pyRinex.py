"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

from shutil import copyfile
from shutil import move
import os
import pyDate
import pyRunWithRetry
import pyStationInfo
import datetime
import sys
import uuid
from shutil import rmtree
import re
import numpy
import struct

def find_between(s, first, last):
    try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

class pyRinexException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class RinexRecord():

    def __init__(self):

        self.firstObs = None
        self.lastObs = None
        self.antType = None
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
        self.StationCode = None
        self.NetworkCode = None
        self.no_cleanup = None
        self.multiday = False
        self.multiday_rnx_list = []

        fieldnames = ['NetworkCode','StationCode','ObservationYear','ObservationMonth','ObservationDay',
                      'ObservationDOY','ObservationFYear','ObservationSTime','ObservationETime','ReceiverType',
                      'ReceiverSerial','ReceiverFw','AntennaType','AntennaSerial','AntennaDome','Filename','Interval',
                      'AntennaOffset']

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



class ReadRinex(RinexRecord):

    def read_fields(self, line, data, format_tuple):

        # create the parser object
        formatstr = re.sub(r'\..', '',' '.join(format_tuple).replace('%', '').replace('f', 's').replace('i', 's').replace('-', ''))

        fs = struct.Struct(formatstr)
        parse = fs.unpack_from

        if len(data) < fs.size:
            # line too short, add padding zeros
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

        return fields

    def check_header(self):

        # list of required header records and a flag to know if they were found or not in the current header
        # also, have a tuple of default values in case there is a missing record
        required_records = {'RINEX VERSION / TYPE': [('%9.2f','%11s','%1s','%19s','%1s','%19s'), False, ('',)],
                            'PGM / RUN BY / DATE' : [('%-20s','%-20s','%-20s'), False, ('pyRinex: 1.00 000', 'Parallel.PPP', '21FEB17 00:00:00')],
                            'MARKER NAME'         : [('%-60s',), False, (self.StationCode,)],
                            'MARKER NUMBER'       : [('%-20s',), False, (self.StationCode,)],
                            'OBSERVER / AGENCY'   : [('%-20s','%-40s'), False, ('UNKNOWN','UNKNOWN')],
                            'REC # / TYPE / VERS' : [('%-20s','%-20s','%-20s'), False, ('LP00785','ASHTECH Z-XII3','CC00')],
                            'ANT # / TYPE'        : [('%-20s','%-20s'), False,('12129', 'ASH700936C_M SNOW')],
                            'ANTENNA: DELTA H/E/N': [('%14.4f','%14.4f','%14.4f'), False, (float(0), float(0), float(0))],
                            'APPROX POSITION XYZ' : [('%14.4f','%14.4f','%14.4f'), False, (float(0), float(0), float(6371000))],
                             #'# / TYPES OF OBSERV' : [('%6i',), False, ('',)],
                            'TIME OF FIRST OBS'   : [('%6i','%6i','%6i','%6i','%6i','%13.7f','%8s'), False, (int(2000), int(1), int(1),  int(0),  int(0),  float(0), 'GPS')],
                            'TIME OF LAST OBS'    : [('%6i','%6i','%6i','%6i','%6i','%13.7f','%8s'), True, (int(2000), int(1), int(1), int(23), int(59), float(59), 'GPS')],
                            'COMMENT'             : [('%60s',), True, ('',)]}

        header = self.get_header()
        new_header = []
        system = ''

        for line in header:

            if any(key in line for key in required_records.keys()):
                # get the first occurrence only!
                record = [key for key in required_records.keys() if key in line][0]

                # mark the record as found
                required_records[record] = [required_records[record][0], True, required_records[record][2]]

                # get the data section by spliting the line using the record text
                data = line.split(record)[0]

                fields = self.read_fields(line, data, required_records[record][0])

                if record == 'RINEX VERSION / TYPE':
                    # read the information about the RINEX type
                    # save the system to use during TIME OF FIRST OBS
                    system = fields[4].strip()

                    if not system in (' ', 'G', 'R', 'S', 'E', 'M'):
                        # assume GPS
                        system = 'G'
                        fields[4] = 'G'

                else:
                    # reformat the header line
                    if record == 'TIME OF FIRST OBS' or record == 'TIME OF LAST OBS':
                        if system == 'M' and not fields[6].strip():
                            fields[6] = 'GPS'

                #if record == '# / TYPES OF OBSERV':
                # re-read this time with the correct number of fields
                #    required_records[record][0] += ('%6s',)*fields[0]
                #    fields = self.read_fields(line, data, required_records[record][0])

                # regenerate the fields
                data = ''.join (required_records[record][0]) % tuple(fields)
                data = '%-60s' % data + record

                # save to new header
                new_header += [data + '\n']
            else:
                # not a critical field, just put it back in
                if not 'END OF HEADER' in line:
                    # leave END OF HEADER until the end to add possible missing records
                    new_header += [line]

        if system == '':
            # if we are out of the loop and we could not determine the system, raise error
            raise pyRinexException('Unfixable RINEX header: could not find RINEX VERSION / TYPE')

        # now check that all the records where included! there's missing ones, then force them
        if not all([item[1] for item in required_records.values()]):
            # get the keys of the missing records
            missing_records = {item[0]:item[1] for item in required_records.items() if item[1][1] == False}

            for record in missing_records:
                if '# / TYPES OF OBSERV' in record:
                    raise pyRinexException('Unfixable RINEX header: could not find # / TYPES OF OBSERV')

                data = ''.join(missing_records[record][0]) % missing_records[record][2]
                data = '%-60s' % data + record
                new_header = new_header + [data + '\n']
                data = '%-60s' % 'pyRinex: WARN! dummy record inserted to fix file!' + 'COMMENT'
                new_header = new_header + [data + '\n']

        new_header += [''.ljust(60,' ') + 'END OF HEADER\n']

        if new_header != header:

            try:
                with open(self.rinex_path, 'r') as fileio:
                    rinex = fileio.readlines()
            except:
                raise

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
            except:
                raise

    def __init__(self, NetworkCode, StationCode, origin_file, no_cleanup=False):

        RinexRecord.__init__(self)

        self.StationCode = StationCode
        self.NetworkCode = NetworkCode
        self.no_cleanup = no_cleanup

        self.origin_file = origin_file

        self.rootdir = os.path.join('production', 'rinex')
        self.rootdir = os.path.join(self.rootdir, str(uuid.uuid4()))

        try:
            # create a production folder to analyze the rinex file
            if not os.path.exists(self.rootdir):
                os.makedirs(self.rootdir)
        except OSError as e:
            # folder exists from a concurring instance, ignore the error
            sys.exc_clear()
        except:
            raise

        # get the crinex and rinex names
        self.crinex = origin_file.split('/')[-1]

        if self.crinex.endswith('d.Z'):
            self.rinex = self.crinex.replace('d.Z', 'o')
            run_crz2rnx = True
        else:
            # file is not compressed, rinex = crinex
            # I should also add a condition to open just hatanaked files
            self.rinex = self.crinex
            # create the crinex name even if we got a rinex as the input file
            self.crinex = self.crinex_from_rinex(self.crinex)
            run_crz2rnx = False

        # get the paths
        self.crinex_path = os.path.join(self.rootdir, self.crinex)
        self.rinex_path = os.path.join(self.rootdir, self.rinex)

        # copy the rinex file from the archive
        try:
            # copy the file. If the origin name if a crinex, use crinex_path as destiny
            # if it's a rinex, use rinex_path as destiny
            if origin_file.endswith('d.Z'):
                copyfile(origin_file, self.crinex_path)
            else:
                copyfile(origin_file, self.rinex_path)
        except:
            raise

        if run_crz2rnx:

            crinex_size = os.path.getsize(self.crinex_path)

            # run crz2rnx with timeout structure
            cmd = pyRunWithRetry.RunCommand('crz2rnx -f -d ' + self.crinex_path, 30)
            try:
                _, err = cmd.run_shell()
            except pyRunWithRetry.RunCommandWithRetryExeception as e:
                # catch the timeout except and pass it as a pyRinexException
                raise pyRinexException(e)
            except:
                raise

            # the uncompressed-unhatanaked file size must be at least > than the crinex
            if err and os.path.getsize(self.rinex_path) <= crinex_size:
                raise pyRinexException("Error in ReadRinex.__init__ -- crz2rnx (error and empty file): " + err)


        # check basic infor in the rinex header to avoid problems with RinSum
        self.check_header()

        # run RinSum to get file information
        cmd = pyRunWithRetry.RunCommand('RinSum --notable ' + self.rinex_path, 21)
        try:
            out,_ = cmd.run_shell()
        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(e)
        except:
            raise

        # write RinSum output to a log file (debug purposes)
        info = open(self.rinex_path + '.log', 'w')
        info.write(out)
        info.close()

        # process the output
        self.process(out)

        if (not self.firstObs or not self.lastObs):
            # first and lastobs cannot be None
            raise pyRinexException(self.rinex_path + ': error in ReadRinex.process: the output for first/last obs is empty. The output from RinSum was:\n' + out)
        else:
            # rinsum return dates that are 19xx (1916, for example) when they should be 2016
            # also, some dates from 199x are reported as 0091!
            # handle data format problems seen in the Cluster (only)

            if int(self.firstObs.split('/')[0]) - 1900 < 80 and int(self.firstObs.split('/')[0]) >= 1900:
                # wrong date
                self.firstObs = self.firstObs.replace(self.firstObs.split('/')[0], str(int(self.firstObs.split('/')[0]) - 1900 + 2000))

            elif int(self.firstObs.split('/')[0]) < 1900 and int(self.firstObs.split('/')[0]) >= 80:

                self.firstObs = self.firstObs.replace(self.firstObs.split('/')[0], str(int(self.firstObs.split('/')[0]) + 1900))

            elif int(self.firstObs.split('/')[0]) < 1900 and int(self.firstObs.split('/')[0]) < 80:

                self.firstObs = self.firstObs.replace(self.firstObs.split('/')[0], str(int(self.firstObs.split('/')[0]) + 2000))


            if int(self.lastObs.split('/')[0]) - 1900 < 80 and int(self.lastObs.split('/')[0]) >= 1900:
                # wrong date
                self.lastObs = self.lastObs.replace(self.lastObs.split('/')[0], str(int(self.lastObs.split('/')[0]) - 1900 + 2000))

            elif int(self.lastObs.split('/')[0]) < 1900 and int(self.lastObs.split('/')[0]) >= 80:

                self.lastObs = self.lastObs.replace(self.lastObs.split('/')[0], str(int(self.lastObs.split('/')[0]) + 1900))

            elif int(self.lastObs.split('/')[0]) < 1900 and int(self.lastObs.split('/')[0]) < 80:

                self.lastObs = self.lastObs.replace(self.lastObs.split('/')[0], str(int(self.lastObs.split('/')[0]) + 2000))

            try:
                self.datetime_firstObs = datetime.datetime.strptime(self.firstObs,'%Y/%m/%d %H:%M:%S')
                self.datetime_lastObs = datetime.datetime.strptime(self.lastObs,'%Y/%m/%d %H:%M:%S')
            except ValueError:
                self.datetime_firstObs = datetime.datetime.strptime(self.firstObs, '%y/%m/%d %H:%M:%S')
                self.datetime_lastObs = datetime.datetime.strptime(self.lastObs, '%y/%m/%d %H:%M:%S')
            except:
                raise

            # check for files that have more than one day inside (yes, there are some like this... amazing)
            # condition is: the start and end date don't match AND
            # either there is more than two hours in the second day OR
            # there is more than one day of data
            if self.datetime_lastObs.date() != self.datetime_firstObs.date() and \
                    (self.datetime_lastObs.time().hour > 2 or (self.datetime_lastObs - self.datetime_firstObs).days > 1):
                # the file has more than one day in it...
                # use teqc to window the data
                self.tbin()
                self.multiday = True

            # reported date for this file is session/2
            self.date = pyDate.Date(datetime=self.datetime_firstObs+(self.datetime_lastObs-self.datetime_firstObs)/2)

            self.firstObs = self.datetime_firstObs.strftime('%Y/%m/%d %H:%M:%S')
            self.lastObs = self.datetime_lastObs.strftime('%Y/%m/%d %H:%M:%S')

            # load the RinexRecord class
            self.load_record()

        return

    def tbin(self):

        # run in the local folder to get the files inside rootdir
        cmd = pyRunWithRetry.RunCommand('teqc -tbin 1d rnx ' + self.rinex, 45, self.rootdir)
        try:
            _, err = cmd.run_shell()
        except pyRunWithRetry.RunCommandWithRetryExeception as e:
            # catch the timeout except and pass it as a pyRinexException
            raise pyRinexException(e)
        except:
            raise

        # successfully tbinned the file
        # delete current file and rename the new files
        os.remove(self.rinex_path)

        # now we should have as many files named rnxDDD0.??o as there where inside the RINEX
        for file in os.listdir(self.rootdir):
            if file.endswith('o') and file[0:3] == 'rnx':
                # rename file
                move(os.path.join(self.rootdir,file),os.path.join(self.rootdir,file.replace('rnx', self.StationCode)))
                # get the info for this file
                rnx = ReadRinex(self.NetworkCode,self.StationCode,os.path.join(self.rootdir,file.replace('rnx', self.StationCode)))
                # append this rinex object to the multiday list
                self.multiday_rnx_list.append(rnx)

        return


    def process(self,output):

        for line in output.split('\n'):
            if r'Rec#:' in line:
                self.recNo = find_between(line, 'Rec#: ','Type:').replace(',','').strip()
                self.recType = find_between(line, 'Type:', 'Vers:').replace(',','').strip()
                try:
                    self.recVers = line.split('Vers:')[1].strip()
                except:
                    self.recVers = ''

            if r'Antenna # :' in line:
                self.antNo = find_between(line, 'Antenna # : ','Type :').replace(',','').strip()
                try:
                    self.antType = line.split('Type :')[1].strip()
                    if ' ' in self.antType:
                        self.antDome = self.antType.split(' ')[-1]
                        self.antType = self.antType.split(' ')[0]
                    else:
                        self.antDome = 'NONE'
                except:
                    self.antType = ''
                    self.antDome = ''

            if r'Antenna Delta (HEN,m) :' in line:
                try:
                    self.antOffset = float(find_between(line, 'Antenna Delta (HEN,m) : (',',').strip())
                except:
                    self.antOffset = []

            if r'Computed interval' in line:
                try:
                    self.interval = float(find_between(line, 'Computed interval','seconds.').strip())
                except:
                    self.interval = 0

            if r'Computed first epoch:' in line:
                self.firstObs = find_between(line, 'Computed first epoch:','=').strip()

            if r'Computed last  epoch:' in line:
                self.lastObs = find_between(line, 'Computed last  epoch:','=').strip()

            if r'Computed file size: ' in line:
                self.size = find_between(line, 'Computed file size:','bytes.').strip()

            if r'Warning : Failed to read header: text 0:Incomplete or invalid header' in line:
                # there is a warning in the output, save it
                raise pyRinexException("Warning in ReadRinex.process: " + line)

            if r'unexpected exception' in line:
                raise pyRinexException("unexpected exception in ReadRinex.process: " + line)

            if r'Exception:' in line:
                raise pyRinexException("Exception in ReadRinex.process: " + line)

            if r'no data found. Are time limits wrong' in line:
                raise pyRinexException('RinSum no data found. Are time limits wrong for file ' + self.rinex + ' details:' + line)

        # remove non-utf8 chars
        if self.recNo:
            self.recNo = re.sub(r'[^\x00-\x7f]+','', self.recNo).strip()
        if self.recType:
            self.recType = re.sub(r'[^\x00-\x7f]+', '', self.recType).strip()
        if self.recVers:
            self.recVers = re.sub(r'[^\x00-\x7f]+', '', self.recVers).strip()
        if self.antNo:
            self.antNo = re.sub(r'[^\x00-\x7f]+', '', self.antNo).strip()
        if self.antType:
            self.antType = re.sub(r'[^\x00-\x7f]+', '', self.antType).strip()
        if self.antDome:
            self.antDome = re.sub(r'[^\x00-\x7f]+', '', self.antDome).strip()


    def get_header(self):

        header = []
        with open(self.rinex_path,'r') as fileio:

            for line in fileio:
                header.append(line)
                if 'END OF HEADER' in line:
                    break

        return header

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

    def auto_coord(self, brdc):
        # use gamit's sh_rx2apr to obtain a coordinate of the station

        cmd = pyRunWithRetry.RunCommand('sh_rx2apr -site ' + self.rinex + ' -nav ' + brdc.brdc_filename, 10, self.rootdir)
        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if err != '':
            return None, None, err + '\n' + out
        else:
            # check that the Final chi**2 is < 3
            for line in out.split('\n'):
                if '* Final sqrt(chi**2/n)' in line:
                    chi = line.split()[-1]

                    if chi == 'NaN':
                        return None, None
                    elif float(chi) < 3:
                        # open the APR file and read the coordinates
                        if os.path.isfile(os.path.join(self.rootdir, self.rinex[0:4] + '.apr')):
                            with open(os.path.join(self.rootdir, self.rinex[0:4] + '.apr')) as apr:
                                line = apr.readline().split()

                                self.x = float(line[1])
                                self.y = float(line[2])
                                self.z = float(line[3])

                                self.lat, self.lon, self.h = self.ecef2lla([self.x, self.y, self.z])

                            return (float(line[1]), float(line[2]), float(line[3])), (self.lat, self.lon, self.h), None

            return None, None, out + '\nLIMIT FOR CHI**2 is 3!'

    def auto_coord_teqc(self,brdc):
        # calculate an autonomous coordinate using broadcast orbits
        # expects to find the orbits next to the file in question

        cmd = pyRunWithRetry.RunCommand('teqc +qcq -nav ' + brdc.brdc_path + ' ' + self.rinex_path, 5)
        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if err:
            # this part needs to handle all possible outcomes of teqc
            for line in err.split('\n'):
                # find if the err is saying there was a large antenna change
                if r'! Warning ! ... antenna position change of ' in line:
                    # bad coordinate
                    change = float(find_between(line,'! Warning ! ... antenna position change of ',' meters'))
                    if change > 100:
                        # don't trust this RINEX for coordinates!
                        return None

                if r'currently cannot deal with an applied clock offset in QC mode' in line:
                    # handle clock stuff (see rufi)
                    # remove RCV CLOCK OFFS APPL from header and rerun
                    return None

        # if no significant problem was found, continue
        for line in out.split('\n'):
            if r'  antenna WGS 84 (xyz)  :' in line:
                xyz = find_between(line,'  antenna WGS 84 (xyz)  : ',' (m)').split(' ')
                x = xyz[0].strip(); y = xyz[1].strip(); z = xyz[2].strip()
                self.x = x; self.y = y; self.z = z
                return (float(x),float(y),float(z))

        return None

    def decimate(self, decimate_rate):

        cmd = pyRunWithRetry.RunCommand('teqc -igs -O.dec %i +obs %s.t %s' % (decimate_rate, self.rinex_path, self.rinex_path), 5)
        # leave errors un-trapped on purpose (will raise an error to the parent)
        out, err = cmd.run_shell()

        if not 'teqc: failure to read' in str(err):
            # delete the original file and replace with .t
            os.remove(self.rinex_path)
            move(self.rinex_path + '.t', self.rinex_path)

            self.interval = decimate_rate
        else:
            raise pyRinexException(err)

        return

    def normalize_header(self, StationInfo, brdc=None, x=None, y=None, z=None):
        assert isinstance(StationInfo, pyStationInfo.StationInfo)
        # this function gets rid of the heaer information and replaces it with the station info (trusted)
        # should be executed before calling PPP or before rebuilding the Archive

        if StationInfo.date != self.date:
            raise pyRinexException('The StationInfo object was initialized for a different date than that of the RINEX file')

        if StationInfo.AntennaCode is not None and StationInfo.ReceiverCode is not None:
            # make sure that there is infornation in the provided StationInfo object
            try:
                with open(self.rinex_path, 'r') as fileio:
                    rinex = fileio.readlines()
            except:
                raise

            insert_comment_antcode = False
            insert_comment_antheight = False
            insert_comment_receiever = False
            del_lines = []

            # remove all comments from the header
            for i, line in enumerate(rinex):
                if line.strip().endswith('COMMENT'):
                    del_lines.append(i)
                if line.strip().endswith('END OF HEADER'):
                    break

            rinex = [i for j, i in enumerate(rinex) if j not in del_lines]

            for i, line in enumerate(rinex):
                if line.strip().endswith('ANT # / TYPE'):
                    AntNo = line[0:20].strip()
                    AntCode = line[20:35].strip()
                    AntDome = line[36:60].strip()
                    # make sure that the ANTENNA and DOME fields are correctly separated
                    # (antenna should take 15 chars and DOME should start after the 16th place)
                    # otherwise PPP won't read the ANTENNA MODEL and DOME correctly (piece of sh.t)
                    if (StationInfo.AntennaCode != AntCode or StationInfo.AntennaSerial != AntNo or StationInfo.RadomeCode != AntDome):
                        del rinex[i]
                        rinex.insert(i,str(StationInfo.AntennaSerial).ljust(20) + str(StationInfo.AntennaCode).ljust(15) + ' ' + str(StationInfo.RadomeCode).ljust(24) + 'ANT # / TYPE\n')
                        insert_comment_antcode = True
                    break

            if (StationInfo.ReceiverCode != self.recType or StationInfo.ReceiverSerial != self.recNo or StationInfo.ReceiverVers != self.recVers):
                for i, line in enumerate(rinex):
                    if line.strip().endswith('REC # / TYPE / VERS'):
                        del rinex[i]
                        rinex.insert(i,str(StationInfo.ReceiverSerial).ljust(20) + str(StationInfo.ReceiverCode).ljust(20) + str(StationInfo.ReceiverVers).ljust(20) + 'REC # / TYPE / VERS\n')
                        insert_comment_receiever = True
                        break

            if StationInfo.AntennaHeight != self.antOffset:
                for i, line in enumerate(rinex):
                    if line.strip().endswith('ANTENNA: DELTA H/E/N'):
                        del rinex[i]
                        rinex.insert(i, ("{0:.4f}".format(StationInfo.AntennaHeight).rjust(14) + "{0:.4f}".format(StationInfo.AntennaEast).rjust(14) + "{0:.4f}".format(StationInfo.AntennaNorth).rjust(14)).ljust(60) + 'ANTENNA: DELTA H/E/N\n')
                        insert_comment_antheight = True
                        break

            # always replace the APPROX POSITION XYZ
            if x is None and brdc is None:
                raise pyRinexException('Cannot normalize the header\'s APPROX POSITION XYZ without a coordinate or a valid broadcast ephemeris object')
            else:
                if x is None:
                    self.auto_coord(brdc)
                else:
                    self.x = x; self.y = y; self.z = z

            for i, line in enumerate(rinex):
                if line.strip().endswith('APPROX POSITION XYZ'):
                    del rinex[i]
                    rinex.insert(i, ("{0:.4f}".format(self.x).rjust(14) + "{0:.4f}".format(self.y).rjust(14) + "{0:.4f}".format(self.z).rjust(14)).ljust(60) + 'APPROX POSITION XYZ\n')
                    break

            for i, line in enumerate(rinex):
                if line.strip().endswith('END OF HEADER'):
                    if insert_comment_antcode:
                        rinex.insert(i, ('PREV ANT    #: ' + str(self.antNo)).ljust(60) + 'COMMENT\n')
                        rinex.insert(i, ('PREV ANT TYPE: ' + str(self.antType)).ljust(60) + 'COMMENT\n')
                        rinex.insert(i, ('PREV ANT RADM: ' + str(self.antDome)).ljust(60) + 'COMMENT\n')

                    if insert_comment_antheight:
                        rinex.insert(i, ('PREV DELTAS: ' + "{0:.4f}".format(self.antOffset).rjust(14) + "{0:.4f}".format(0).rjust(14) + "{0:.4f}".format(0).rjust(14)).ljust(60) + 'COMMENT\n')

                    if insert_comment_receiever:
                        rinex.insert(i, ('PREV REC    #: ' + str(self.recNo)).ljust(60) + 'COMMENT\n')
                        rinex.insert(i, ('PREV REC TYPE: ' + str(self.recType)).ljust(60) + 'COMMENT\n')
                        rinex.insert(i, ('PREV REC VERS: ' + str(self.recVers)).ljust(60) + 'COMMENT\n')

                    rinex.insert(i, 'APPROX POSITION SET TO AUTONOMOUS COORDINATE'.ljust(60) + 'COMMENT\n')

                    rinex.insert(i, ('HEADER NORMALIZED BY PARALLEL.ARCHIVE ON ' + datetime.datetime.now().strftime(
                        '%Y/%m/%d %H:%M')).ljust(60) + 'COMMENT\n')
                    break

            try:
                f = open(self.rinex_path, 'w')
                f.writelines(rinex)
                f.close()
            except:
                raise
        else:
            raise pyRinexException('The StationInfo object was not initialized correctly.')

        return

    def move_origin_file(self, path):
        # this function moves the ARCHIVE file out to another location indicated by path
        # it also makes sure that it doesn' overwrite any existing file
        try:
            # make the folders if they don't exist
            if not os.path.isdir(path):
                os.makedirs(path)

            index = 0
            # make sure that the destiny filename is in lowercase.
            filename = self.crinex.lower().replace('d.z','d.Z')
            while os.path.isfile(os.path.join(path, filename)):
                filename_parts = filename.split('.')
                filename = filename_parts[0][0:-1] + str(index) + '.' + filename_parts[1] + '.' + filename_parts[2]
                index += 1

            # to keep everything consistent, also change the local copies of the file
            self.rename_crinex_rinex(filename)

            move(self.origin_file, os.path.join(path, filename))

        except pyRinexException as e:
            raise

        except Exception as e:
            raise pyRinexException(e)

        return

    def compress_local_copyto(self, path):
        # this function compresses and moves the local copy of the rinex
        # meant to be used when a multiday rinex file is encountered and we need to move it to the repository
        try:
            # make the folders if they don't exist
            if not os.path.isdir(path):
                os.makedirs(path)

            # compress the rinex into crinex. Make the filename
            crinex = self.crinex_from_rinex(self.rinex)

            # we make the crinex again (don't use the existing from the database) to apply any corrections
            # made during the __init__ stage. Notice the -f in rnx2crz
            cmd = pyRunWithRetry.RunCommand('rnx2crz -f ' + self.rinex_path, 45)
            try:
                _, err = cmd.run_shell()

                if os.path.getsize(os.path.join(self.rootdir, crinex)) == 0:
                    raise pyRinexException('Error in compress_local_copyto: compressed version of ' + self.rinex_path + ' has zero size!')
            except pyRunWithRetry.RunCommandWithRetryExeception as e:
                # catch the timeout except and pass it as a pyRinexException
                raise pyRinexException(e)
            except:
                raise

            index = 1
            # if the parent process could not read the name of the station, year and doy, then it created a uuid folder
            # in that case, it will not try to parse the filename since it will be the only file in the folder
            filename = crinex
            while os.path.isfile(os.path.join(path, filename)):
                filename_parts = filename.split('.')
                filename = filename_parts[0][0:-1] + str(index) + '.' + filename_parts[1] + '.' + filename_parts[2]
                index += 1

            copyfile(os.path.join(self.rootdir, crinex), os.path.join(path, filename))

        except pyRinexException as e:
            raise pyRinexException(e)
        except Exception as e:
            raise pyRinexException(e)

        return


    def rename_crinex_rinex(self, new_name, NetworkCode=None, StationCode=None):

        # function that renames the local crinex and rinex file based on the provided information
        # it also changes the variables in the object to reflect this change
        # new name can be either a d.Z or .??o

        if new_name.endswith('d.Z'):
            crinex_new_name = new_name
            rinex_new_name = self.rinex_from_crinex(new_name)
        elif new_name.endswith('o'):
            crinex_new_name = self.crinex_from_rinex(new_name)
            rinex_new_name = new_name
        else:
            raise pyRinexException('%s: Invalid name for rinex or crinex file.' % (new_name))

        # rename the files
        # check if local crinex exists (possibly made by compress_local_copyto)
        if os.path.isfile(self.crinex_path):
            move(self.crinex_path, os.path.join(self.rootdir, crinex_new_name))
        # update the crinex record
        self.crinex_path = os.path.join(self.rootdir, crinex_new_name)
        self.crinex = crinex_new_name

        move(self.rinex_path, os.path.join(self.rootdir, rinex_new_name))
        self.rinex_path = os.path.join(self.rootdir, rinex_new_name)
        self.rinex = rinex_new_name

        # update the database dictionary record
        self.record['Filename'] = self.rinex

        # we don't touch the metadata StationCode and NetworkCode unless explicitly passed
        if NetworkCode:
            self.NetworkCode = NetworkCode.lower()
            self.record['NetworkCode'] = NetworkCode.lower()

        if StationCode:
            self.StationCode = StationCode.lower()
            self.record['StationCode'] = StationCode.lower()

        return

    def crinex_from_rinex(self, name):

        return name.replace(name.split('.')[-1], name.split('.')[-1].replace('o', 'd.Z'))

    def rinex_from_crinex(self, name):

        return name.replace('d.Z', 'o')

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

def main():
    # for testing purposes
    rnx = ReadRinex('RNX','chac','chac0010.17o')

if __name__ == '__main__':

    main()

    # BACK UP OF OLD check_time_sys
    # print ''.join(new_header)
    #
    # add_time_sys = False
    # check_time_sys = False
    # add_obs_agen = True
    # add_marker_name = True
    # add_pgm_runby = True
    # replace_pgm_runby = False
    # replace_ant_type = False
    # bad_header = False
    #
    # for line in header:
    #
    #     if len(line) < 60:
    #         if 'TIME OF FIRST OBS' in line or 'TIME OF LAST OBS' in line:
    #             bad_header = True
    #
    #     if 'RINEX VERSION / TYPE' in line:
    #         if line[40:41] == 'M':
    #             # mixed system, should check for GPS in time of first obs
    #             check_time_sys = True
    #
    #     if 'TIME OF FIRST OBS' in line and check_time_sys:
    #         if line[48:51].strip() == '':
    #             add_time_sys = True
    #
    #     if 'OBSERVER / AGENCY' in line:
    #         add_obs_agen = False
    #
    #     if 'PGM / RUN BY / DATE' in line:
    #         # an error detected in some rinex files:
    #         # 04JAN100 18:03:33 GTMPGM / RUN BY / DATE
    #         # the M of GTM moves one char the PGM / RUN BY / DATE
    #         if line[60:].strip() != 'PGM / RUN BY / DATE':
    #             replace_pgm_runby = True
    #         add_pgm_runby = False
    #
    #     if 'MARKER NAME' in line:
    #         add_marker_name = False
    #
    #     if 'ANT # / TYPE' in line:
    #         if line[60:71].strip() != 'ANT # / TYPE':
    #             # bad header in some RINEX files
    #             # fix it
    #             replace_ant_type = True
    #
    # if add_time_sys or add_obs_agen or add_marker_name or add_pgm_runby or replace_pgm_runby or replace_ant_type or bad_header:
    #     try:
    #         with open(self.rinex_path, 'r') as fileio:
    #             rinex = fileio.readlines()
    #     except:
    #         raise
    #
    #     for i, line in enumerate(rinex):
    #         if len(line) < 60:
    #             # if the line is < 60 chars, replace with a bogus time and date (RinSum ignores it anyways)
    #             # but requires it to continue
    #             # notice that the code only arrives here if non-compulsory bad fields are found e.g. TIME OF FIRST OBS
    #             if 'TIME OF FIRST OBS' in line:
    #                 rinex[i] = '  2000    12    27    00    00    0.000                     TIME OF FIRST OBS\n'
    #
    #             if 'TIME OF LAST OBS' in line:
    #                 rinex[i] = '  2000    12    27    23    59   59.000                     TIME OF LAST OBS\n'
    #
    #         if 'TIME OF FIRST OBS' in line and add_time_sys:
    #             rinex[i] = line.replace('            TIME OF FIRST OBS', 'GPS         TIME OF FIRST OBS')
    #
    #         if 'PGM / RUN BY / DATE' in line and replace_pgm_runby:
    #             rinex[i] = line.replace(line,
    #                                     'pyRinex: 1.00 000   Parallel.Archive    21FEB17 00:00:00    PGM / RUN BY / DATE\n')
    #
    #         if 'ANT # / TYPE' in line and replace_ant_type:
    #             rinex[i] = rinex[i].replace(rinex[i][60:], 'ANT # / TYPE\n')
    #
    #         if 'END OF HEADER' in line:
    #             if add_obs_agen:
    #                 rinex.insert(i, 'IGN                 IGN                                     OBSERVER / AGENCY\n')
    #             if add_marker_name:
    #                 rinex.insert(i,
    #                              self.StationCode + '                                                        MARKER NAME\n')
    #             if add_pgm_runby:
    #                 rinex.insert(i, 'pyRinex: 1.00 000   Parallel.Archive    21FEB17 00:00:00    PGM / RUN BY / DATE\n')
    #             break
    #
    #     try:
    #         f = open(self.rinex_path, 'w')
    #         f.writelines(rinex)
    #         f.close()
    #     except:
    #         raise