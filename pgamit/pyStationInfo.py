"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

import struct
import datetime
from json import JSONEncoder
import os

# deps
import numpy as np

# app
from pgamit import pyDate
from pgamit.pyBunch import Bunch
from pgamit import pyEvents
from pgamit.Utils import struct_unpack, file_readlines, crc32, stationID, determine_frame, parse_atx_antennas
from pgamit import igslog


def _default(self, obj):
    return getattr(obj.__class__, "to_json", _default.default)(obj)


_default.default = JSONEncoder().default
JSONEncoder.default = _default


class pyStationInfoException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class pyStationInfoHeightCodeNotFound(pyStationInfoException):
    pass


class StationInfoRecord(Bunch):
    def __init__(self, NetworkCode=None, StationCode=None, record=None):

        Bunch.__init__(self)

        self.NetworkCode      = NetworkCode
        self.StationCode      = StationCode
        self.ReceiverCode     = ''
        self.ReceiverSerial   = None
        self.ReceiverFirmware = None
        self.AntennaCode      = ''
        self.AntennaSerial    = None
        self.AntennaHeight    = 0
        self.AntennaNorth     = 0
        self.AntennaEast      = 0
        self.HeightCode       = ''
        self.RadomeCode       = ''
        self.DateStart        = None
        self.DateEnd          = None
        self.ReceiverVers     = None
        self.Comments         = None
        self.hash             = None

        if record is not None:
            self.parse_station_record(record)

        # create a hash record using the station information
        # use only the information that can actually generate a change in the antenna position
        self.hash = crc32('%.4f %.4f %.4f %s %s %s %s' %
                          (self.AntennaNorth, self.AntennaEast, self.AntennaHeight, self.HeightCode,
                           self.AntennaCode, self.RadomeCode, self.ReceiverCode))

        # self.record_format = ' %-4s  %-16s  %-19s%-19s%7.4f  %-5s  %7.4f  %7.4f  %-20s  ' \
        #                      '%-20s  %5s  %-20s  %-15s  %-5s  %-20s'

        self.record_format = ' {:4.4}  {:16.16}  {:19.19}{:19.19}{:7.4f}  {:5.5}  {:7.4f}  {:7.4f}  {:20.20}  ' \
                             '{:20.20}  {:>5.5}  {:20.20}  {:15.15}  {:5.5}  {:20.20}'

    def database(self):
        r = {}

        for field in ('StationCode', 'NetworkCode', 'DateStart', 'DateEnd',
                      'AntennaHeight', 'HeightCode', 'AntennaNorth', 'AntennaEast',
                      'ReceiverCode', 'ReceiverVers', 'ReceiverFirmware', 'ReceiverSerial',
                      'AntennaCode', 'RadomeCode', 'AntennaSerial', 'Comments'):

            if field == 'DateStart':
                r[field] = self[field].datetime()
            elif field == 'DateEnd':
                if self[field].year is None:
                    r[field] = None
                else:
                    r[field] = self[field].datetime()
            else:
                r[field] = self[field]

        return r

    def to_json(self):
        fields = self.database()
        fields['DateStart'] = str(self.DateStart)
        fields['DateEnd']   = str(self.DateEnd)

        return fields

    def parse_station_record(self, record):

        if isinstance(record, str):

            fieldnames = ('StationCode', 'StationName', 'DateStart', 'DateEnd', 'AntennaHeight', 'HeightCode',
                          'AntennaNorth', 'AntennaEast', 'ReceiverCode', 'ReceiverVers', 'ReceiverFirmware',
                          'ReceiverSerial', 'AntennaCode', 'RadomeCode', 'AntennaSerial')

            fieldwidths = (1, 6, 18, 19, 19, 9, 7, 9, 9, 22, 22, 7, 22, 17, 7, 20)  # negative widths represent ignored padding fields
            fmtstring = ' '.join('{}{}'.format(abs(fw), 'x' if fw < 0 else 's') for fw in fieldwidths)

            fieldstruct = struct.Struct(fmtstring)

            if record[0] == ' ' and len(record) >= 77:
                record = dict(zip(fieldnames, map(str.strip,
                                                  struct_unpack(fieldstruct,
                                                                record.ljust(fieldstruct.size))[1:])))
            else:
                return

        for key in list(self.keys()):
            try:
                if key in ('AntennaNorth', 'AntennaEast', 'AntennaHeight'):
                    self[key] = float(record[key])
                else:
                    self[key] = record[key]
            except KeyError:
                # if key not found in the record, may be an added field (like hash)
                pass

        try:
            # if initializing with a RINEX record, some of these may not exist in the dictionary
            self.DateStart   = pyDate.Date(stninfo = record['DateStart'])
            self.DateEnd     = pyDate.Date(stninfo = record['DateEnd'])
            self.StationCode = record['StationCode'].lower()
        except KeyError:
            pass

    def __repr__(self):
        return 'pyStationInfo.StationInfoRecord(%s)' % str(self) 

    def __str__(self):

        return self.record_format.format(self.StationCode.upper(),
                                         '',
                                         str(self.DateStart),
                                         str(self.DateEnd),
                                         self.AntennaHeight,
                                         str(self.HeightCode),
                                         self.AntennaNorth,
                                         self.AntennaEast,
                                         str(self.ReceiverCode),
                                         str(self.ReceiverVers),
                                         str(self.ReceiverFirmware),
                                         str(self.ReceiverSerial),
                                         str(self.AntennaCode),
                                         str(self.RadomeCode),
                                         str(self.AntennaSerial))


class StationInfo:
    """
    New parameter: h_tolerance makes the station info more tolerant to gaps. This is because station info in the old
    days had a break in the middle and the average epoch was falling right in between the gap
    """
    def __init__(self, cnn, NetworkCode=None, StationCode=None, date=None, allow_empty=False, h_tolerance=0):

        self.record_count = 0
        self.NetworkCode  = NetworkCode
        self.StationCode  = StationCode
        self.allow_empty  = allow_empty
        self.date         = None
        self.records      = []
        self.currentrecord = StationInfoRecord(NetworkCode, StationCode)

        self.header = '*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  Ant N    ' \
                      'Ant E    Receiver Type         Vers                  SwVer  Receiver SN           ' \
                      'Antenna Type     Dome   Antenna SN          '

        # connect to the db and load the station info table
        if NetworkCode is not None and StationCode is not None:

            self.cnn = cnn

            if self.load_stationinfo_records():
                # find the record that matches the given date
                if date is not None:
                    self.date = date

                    pDate = date.datetime()

                    for record in self.records:

                        DateStart = record['DateStart'].datetime()
                        DateEnd   = record['DateEnd'].datetime()

                        # make the gap-tolerant comparison
                        tolerance = datetime.timedelta(hours=h_tolerance)
                        if DateStart - tolerance <= pDate <= DateEnd + tolerance:
                            # found the record that corresponds to this date
                            self.currentrecord = record
                            break

                    if self.currentrecord.DateStart is None:
                        raise pyStationInfoException('Could not find a matching station.info record for ' +
                                                     stationID(self) + ' ' +
                                                     date.yyyymmdd() + ' (' + date.yyyyddd() + ')')

    def load_stationinfo_records(self):
        # function to load the station info records in the database
        # returns true if records found
        # returns false if none found, unless allow_empty = False in which case it raises an error.
        stninfo = self.cnn.query('SELECT * FROM stationinfo WHERE "NetworkCode" = \'' + self.NetworkCode +
                                 '\' AND "StationCode" = \'' + self.StationCode + '\' ORDER BY "DateStart"')

        if stninfo.ntuples() == 0:
            if not self.allow_empty:
                # allow no station info if explicitly requested by the user.
                # Purpose: insert a station info for a new station!
                raise pyStationInfoException('Could not find ANY valid station info entry for ' + stationID(self))
            self.record_count = 0
            return False
        else:
            for record in stninfo.dictresult():
                self.records.append(StationInfoRecord(self.NetworkCode, self.StationCode, record))

            self.record_count = stninfo.ntuples()
            return True

    def antenna_check(self, frames):
        missing = []
        atx = dict()
        for frame in frames:
            # read all the available atx files
            atx[frame['name']] = parse_atx_antennas(frame['atx'])

        # check that the antennas declared in this station information record exist in the ATX file
        for i, record in enumerate(self.records):
            # check existence of ANTENNA in ATX
            # determine the reference frame using the start date
            frame, atx_file = determine_frame(frames, record['DateStart'])
            # check if antenna in atx, if not, produce a warning
            if record['AntennaCode'] not in atx[frame]:
                missing.append({'record': record, 'atx_file': os.path.basename(atx_file), 'frame': frame})

        return missing

    def station_info_gaps(self):
        # this function checks any missing station info (gaps) or any data outside the first and last station info
        gaps = []
        if len(self.records) > 1:
            # get gaps between stninfo records
            for erecord, srecord in zip(self.records[0:-1], self.records[1:]):

                sdate = srecord['DateStart']
                edate = erecord['DateEnd']

                # if the delta between previous and current session exceeds one second, check if any rinex falls
                # in that gap
                if (sdate.datetime() - edate.datetime()).total_seconds() > 1:
                    count = self.cnn.query('SELECT count(*) as rcount FROM rinex_proc '
                                           'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                                           '"ObservationETime" > \'%s\' AND "ObservationSTime" < \'%s\' AND '
                                           '"Completion" >= 0.5' % (self.NetworkCode, self.StationCode,
                                                                    edate.strftime(),
                                                                    sdate.strftime())).dictresult()[0]['rcount']
                    if count != 0:
                        gaps.append({'rinex_count': count, 'record_start': srecord, 'record_end': erecord})

        # there should not be RINEX data outside the station info window
        rs = self.cnn.query('SELECT min("ObservationSTime") as first_obs, max("ObservationETime") as last_obs '
                            'FROM rinex_proc WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                            'AND "Completion" >= 0.5'
                            % (self.NetworkCode, self.StationCode))  # only check RINEX with more than 12 hours of data

        rnxtbl = rs.dictresult()

        if rnxtbl[0]['first_obs'] is not None and len(self.records) > 0:
            # to avoid empty stations (no rinex data)
            if rnxtbl[0]['first_obs'] < self.records[0]['DateStart'].datetime():
                gaps.append({'rinex_count': 1, 'record_start': self.records[0], 'record_end': None})

            if rnxtbl[0]['last_obs'] > self.records[-1]['DateEnd'].datetime():
                gaps.append({'rinex_count': 1, 'record_start': None, 'record_end': self.records[-1]})

        return gaps

    def parse_station_info(self, stninfo_file_list):
        """
        function used to parse a station information file
        :param stninfo_file_list: a station information file or list containing station info records
        :return: a list of StationInformationRecords
        """

        if isinstance(stninfo_file_list, list):
            # a list is comming in
            stninfo = stninfo_file_list
        else:
            # a file is comming in, it is an IGS log file
            _, ext = os.path.splitext(stninfo_file_list)
            if ext.lower() == '.log':
                fs = ' {:4.4}  {:16.16}  {:19.19}{:19.19}{:7.4f}  {:5.5}  {:7.4f}  {:7.4f}  {:20.20}  ' \
                     '{:20.20}  {:>5.5}  {:20.20}  {:15.15}  {:5.5}  {:20.20}'
                logfile = igslog.parse_igs_log_file(stninfo_file_list)
                stninfo = []
                for row in logfile:
                    stninfo.append(fs.format(
                        row[0],  # station code
                        row[1],  # station name
                        str(pyDate.Date(datetime=row[2])),  # session start
                        str(pyDate.Date(datetime=row[3])) if row[3].year < 2100 else '9999 999 00 00 00',  # session end
                        float(row[4]) if type(row[4]) is float else 0.000,  # antenna height
                        row[5],  # height code
                        float(row[6]) if type(row[6]) is float else 0.000,  # antenna north offset
                        float(row[7]) if type(row[7]) is float else 0.000,  # antenna east offset
                        row[8],  # receiver type
                        row[9],  # receiver firmware version
                        row[10],  # software version
                        row[11],  # receiver serial number
                        row[12],  # antenna type
                        row[13],  # radome
                        row[14],  # antenna serial number
                        row[15],  # comment
                    ))
            else:
                stninfo = file_readlines(stninfo_file_list)

        records = []
        for line in stninfo:

            if line[0] == ' ' and len(line) >= 77:
                record = StationInfoRecord(self.NetworkCode, self.StationCode, line)

                if record.DateStart is not None:
                    records.append(record)

        return records

    def to_dharp(self, record):
        """
        function to convert the current height code to DHARP
        :return: DHARP height
        """

        if record.HeightCode == 'DHARP':
            return record
        else:
            htc = self.cnn.query_float('SELECT * FROM gamit_htc WHERE "AntennaCode" = \'%s\' AND "HeightCode" = \'%s\''
                                       % (record.AntennaCode, record.HeightCode), as_dict=True)

            if len(htc):

                record.AntennaHeight = np.sqrt(np.square(float(record.AntennaHeight)) -
                                               np.square(float(htc[0]['h_offset']))) - float(htc[0]['v_offset'])
                if record.Comments is not None:
                    record.Comments = record.Comments + '\nChanged from %s to DHARP by pyStationInfo.\n' \
                                      % record.HeightCode
                else:
                    record.Comments = 'Changed from %s to DHARP by pyStationInfo.\n' % record.HeightCode

                record.HeightCode = 'DHARP'

                return record
            else:
                raise pyStationInfoHeightCodeNotFound('%s: %s -> Could not translate height code %s to DHARP. '
                                                      'Check the height codes table.'
                                                      % (stationID(self),
                                                         record.AntennaCode,
                                                         record.HeightCode))

    def return_stninfo(self, record=None, no_dharp_translate=False):
        """
        return a station information string to write to a file (without header
        :param record: to print a specific record, pass a record, otherwise, leave empty to print all records
        :param no_dharp_translate: specify if DHARP translation should be done or not
        :return: a string in station information format
        """
        stninfo = []

        # from the records struct, return a station info file
        if record is not None:
            records = [record]
        else:
            records = self.records

        if records is not None:
            for record in records:
                if no_dharp_translate:
                    stninfo.append(str(record))
                else:
                    stninfo.append(str(self.to_dharp(record)))

        return '\n'.join(stninfo)

    def return_stninfo_short(self, record=None):
        """
        prints a simplified version of the station information to better fit screens
        :param record: to print a specific record, pass a record, otherwise, leave empty to print all records
        :return: a string in station information format. It adds the NetworkCode dot StationCode
        """
        stninfo_lines = self.return_stninfo(record=record).split('\n')

        return '\n'.join(' %s.%s [...] %s' % (self.NetworkCode.upper(), l[1:110], l[160:])
                         for l in stninfo_lines)

    def overlaps(self, qrecord):

        # check if the incoming record is between any existing record
        overlaps = []

        q_start = qrecord['DateStart'].datetime()
        q_end   = qrecord['DateEnd']  .datetime()

        if self.records:
            for record in self.records:

                r_start = record['DateStart'].datetime()
                r_end   = record['DateEnd'].datetime()

                earliest_end = min(q_end, r_end)
                latest_start = max(q_start, r_start)

                if (earliest_end - latest_start).total_seconds() > 0:
                    overlaps.append(record)

        return overlaps

    def DeleteStationInfo(self, record):

        event = pyEvents.Event(Description=record['DateStart'].strftime() +
                               ' has been deleted:\n' + str(record),
                               StationCode=self.StationCode,
                               NetworkCode=self.NetworkCode)

        self.cnn.insert_event(event)

        self.cnn.delete('stationinfo', **record.database())
        self.load_stationinfo_records()

    def UpdateStationInfo(self, record, new_record):

        # avoid problems with trying to insert records from other stations. Force this NetworkCode
        record    ['NetworkCode'] = \
        new_record['NetworkCode'] = self.NetworkCode

        if self.NetworkCode and self.StationCode:

            # check the possible overlaps. This record will probably overlap with itself, so check that the overlap has
            # the same DateStart as the original record (that way we know it's an overlap with itself)
            overlaps = self.overlaps(new_record)

            for overlap in overlaps:
                if overlap['DateStart'].datetime() != record['DateStart'].datetime():
                    # it's overlapping with another record, raise error

                    raise pyStationInfoException('Record %s -> %s overlaps with existing station.info records: %s -> %s'
                                                 % (str(record['DateStart']),
                                                    str(record['DateEnd']),
                                                    str(overlap['DateStart']),
                                                    str(overlap['DateEnd'])))

            # insert event (before updating to save all information)
            event = pyEvents.Event(Description=record['DateStart'].strftime() +
                                   ' has been updated:\n' + str(new_record) +
                                   '\n+++++++++++++++++++++++++++++++++++++\n' +
                                   'Previous record:\n' +
                                   str(record) + '\n',
                                   NetworkCode=self.NetworkCode,
                                   StationCode=self.StationCode)

            self.cnn.insert_event(event)

            if (new_record['DateStart'].datetime() - record['DateStart'].datetime()).seconds != 0:
                self.cnn.query('UPDATE stationinfo SET "DateStart" = \'%s\' '
                               'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' %
                               (new_record['DateStart'].strftime(),
                                self.NetworkCode,
                                self.StationCode,
                                record['DateStart'].strftime()))

            self.cnn.update('stationinfo', new_record.database(), NetworkCode=self.NetworkCode,
                            StationCode=self.StationCode, DateStart=new_record['DateStart'].datetime())

            self.load_stationinfo_records()

    def InsertStationInfo(self, record):

        # avoid problems with trying to insert records from other stations. Force this NetworkCode
        record['NetworkCode'] = self.NetworkCode

        if self.NetworkCode and self.StationCode:
            # check existence of station in the db
            rs = self.cnn.query(
                'SELECT * FROM stationinfo WHERE "NetworkCode" = \'%s\' '
                'AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' %
                (self.NetworkCode, self.StationCode, record['DateStart'].strftime()))

            if rs.ntuples() == 0:
                # can insert because it's not the same record
                # 1) verify the record is not between any two existing records
                overlaps = self.overlaps(record)

                if overlaps:
                    # if it overlaps all records and the DateStart < self.records[0]['DateStart']
                    # see if we have to extend the initial date
                    if len(overlaps) == len(self.records) and \
                            record['DateStart'].datetime() < self.records[0]['DateStart'].datetime():
                        if self.records_are_equal(record, self.records[0]):
                            # just modify the start date to match the incoming record
                            # self.cnn.update('stationinfo', self.records[0], DateStart=record['DateStart'])
                            # the previous statement seems not to work because it updates a primary key!
                            self.cnn.query(
                                'UPDATE stationinfo SET "DateStart" = \'%s\' WHERE "NetworkCode" = \'%s\' '
                                'AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' %
                                (record['DateStart'].strftime(),
                                 self.NetworkCode,
                                 self.StationCode,
                                 self.records[0]['DateStart'].strftime()))

                            # insert event
                            event = pyEvents.Event(Description='The start date of the station information record ' +
                                                               self.records[0]['DateStart'].strftime() +
                                                               ' has been been modified to ' +
                                                               record['DateStart'].strftime(),
                                                   StationCode=self.StationCode,
                                                   NetworkCode=self.NetworkCode)
                            self.cnn.insert_event(event)
                        else:
                            # new and different record, stop the Session with
                            # EndDate = self.records[0]['DateStart'] - datetime.timedelta(seconds=1) and insert
                            record['DateEnd'] = pyDate.Date(datetime=self.records[0]['DateStart'].datetime() -
                                                            datetime.timedelta(seconds=1))

                            self.cnn.insert('stationinfo', **record.database())

                            # insert event
                            event = pyEvents.Event(
                                        Description='A new station information record was added:\n'
                                                    + str(record),
                                        StationCode=self.StationCode,
                                        NetworkCode=self.NetworkCode)

                            self.cnn.insert_event(event)

                    elif len(overlaps) == 1 and overlaps[0] == self.records[-1] and \
                            not self.records[-1]['DateEnd'].year:
                        # overlap with the last session
                        # stop the current valid session
                        new_end_date = record['DateStart'].datetime() - datetime.timedelta(seconds=1)
                        self.cnn.update('stationinfo', {'DateEnd': new_end_date}, **self.records[-1].database())

                        # create the incoming session
                        self.cnn.insert('stationinfo', **record.database())

                        # insert event
                        event = pyEvents.Event(
                                    Description='A new station information record was added:\n' +
                                                self.return_stninfo(record) +
                                                '\nThe DateEnd value of previous last record was updated to ' +
                                                str(new_end_date),
                                    StationCode=self.StationCode,
                                    NetworkCode=self.NetworkCode)
                        self.cnn.insert_event(event)

                        # TODO: RELOAD THE RECORDS??

                    else:
                        stroverlap = []
                        for overlap in overlaps:
                            stroverlap.append(' -> '.join([str(overlap['DateStart']), str(overlap['DateEnd'])]))

                        raise pyStationInfoException('Record %s -> %s overlaps with existing station.info records: %s'
                                                     % (str(record['DateStart']), str(record['DateEnd']),
                                                        ' '.join(stroverlap)))

                else:
                    # no overlaps, insert the record
                    self.cnn.insert('stationinfo', **record.database())

                    # insert event
                    event = pyEvents.Event(Description='A new station information record was added:\n' +
                                                       str(record),
                                           StationCode=self.StationCode,
                                           NetworkCode=self.NetworkCode)
                    self.cnn.insert_event(event)

                # reload the records
                self.load_stationinfo_records()
            else:
                raise pyStationInfoException('Record %s -> %s already exists in station.info' %
                                             (str(record['DateStart']), 
                                              str(record['DateEnd'])))
        else:
            raise pyStationInfoException('Cannot insert record without initializing pyStationInfo '
                                         'with NetworkCode and StationCode')

    def rinex_based_stninfo(self, ignore):
        # build a station info based on the information from the RINEX headers
        rs = self.cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'' + self.NetworkCode +
                            '\' AND "StationCode" = \'' + self.StationCode + '\' ORDER BY "ObservationSTime"')

        rnxtbl = rs.dictresult()

        rnx = rnxtbl[0]

        RecSerial = rnx['ReceiverSerial']
        AntSerial = rnx['AntennaSerial']
        AntHeig   = rnx['AntennaOffset']
        RadCode   = rnx['AntennaDome']
        StartDate = rnx['ObservationSTime']

        stninfo = []
        count = 0
        for i, rnx in enumerate(rnxtbl):

            if RecSerial != rnx['ReceiverSerial'] or AntSerial != rnx['AntennaSerial'] or \
                    AntHeig != rnx['AntennaOffset'] or RadCode != rnx['AntennaDome']:
                # start the counter
                count += 1

                if count > ignore:
                    Vers = rnx['ReceiverFw'][:22]

                    record                  = StationInfoRecord(self.NetworkCode, self.StationCode, rnx)
                    record.DateStart        = pyDate.Date(datetime=StartDate)
                    record.DateEnd          = pyDate.Date(datetime=rnxtbl[i-count]['ObservationETime'])
                    record.HeightCode       = 'DHARP'
                    record.ReceiverVers     = Vers[:5]
                    record.ReceiverFirmware = '-----'
                    record.ReceiverCode     = rnx['ReceiverType']
                    record.AntennaCode      = rnx['AntennaType']

                    stninfo.append(str(record))

                    RecSerial = rnx['ReceiverSerial']
                    AntSerial = rnx['AntennaSerial']
                    AntHeig   = rnx['AntennaOffset']
                    RadCode   = rnx['AntennaDome']
                    StartDate = rnxtbl[i - count + 1]['ObservationSTime']
                    count = 0
            elif RecSerial == rnx['ReceiverSerial'] and AntSerial == rnx['AntennaSerial'] and \
                    AntHeig == rnx['AntennaOffset'] and RadCode == rnx['AntennaDome'] and count > 0:
                # we started counting records that where different, but we didn't make it past > ignore, reset counter
                count = 0

        # insert the last record with 9999
        record                  = StationInfoRecord(self.NetworkCode, self.StationCode, None)
        record.DateStart        = pyDate.Date(datetime=StartDate)
        record.DateEnd          = pyDate.Date(stninfo=None)
        record.HeightCode       = 'DHARP'
        record.ReceiverFirmware = '-----'
        record.ReceiverCode = rnx['ReceiverType']
        record.AntennaCode = rnx['AntennaType']

        stninfo.append(str(record))

        return '\n'.join(stninfo) + '\n'

    def to_json(self):
        return [r.to_json() for r in self.records]

    @staticmethod
    def records_are_equal(record1, record2):
        return (record1['ReceiverCode']   == record2['ReceiverCode']   and 
                record1['ReceiverSerial'] == record2['ReceiverSerial'] and 
                record1['AntennaCode']    == record2['AntennaCode']    and 
                record1['AntennaSerial']  == record2['AntennaSerial']  and
                record1['AntennaHeight']  == record2['AntennaHeight']  and
                record1['AntennaNorth']   == record2['AntennaNorth']   and 
                record1['AntennaEast']    == record2['AntennaEast']    and 
                record1['HeightCode']     == record2['HeightCode']     and
                record1['RadomeCode']     == record2['RadomeCode'])

    def __eq__(self, stninfo):

        if not isinstance(stninfo, StationInfo):
            raise pyStationInfoException('type: ' + str(type(stninfo))
                                         + ' is invalid. Can only compare pyStationInfo.StationInfo objects')

        return (self.currentrecord.AntennaCode    == stninfo.currentrecord.AntennaCode    and
                self.currentrecord.AntennaHeight  == stninfo.currentrecord.AntennaHeight  and
                self.currentrecord.AntennaNorth   == stninfo.currentrecord.AntennaNorth   and 
                self.currentrecord.AntennaEast    == stninfo.currentrecord.AntennaEast    and 
                self.currentrecord.AntennaSerial  == stninfo.currentrecord.AntennaSerial  and
                self.currentrecord.ReceiverCode   == stninfo.currentrecord.ReceiverCode   and 
                self.currentrecord.ReceiverSerial == stninfo.currentrecord.ReceiverSerial and
                self.currentrecord.RadomeCode     == stninfo.currentrecord.RadomeCode)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.records = None

    def __enter__(self):
        return self

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        # Remove the unpicklable entries.
        del state['cnn']
        return state

    def __setstate__(self, state):
        # Restore instance attributes
        self.__dict__.update(state)
        # do not restore the connection after unpickling
        self.cnn = None
