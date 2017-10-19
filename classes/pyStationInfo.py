"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

import struct
import datetime
import pyDate
import zlib

class pyStationInfoException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class StationInfoRecord():
    def __init__(self, NetworkCode=None,StationCode=None):

        self.NetworkCode = NetworkCode
        self.StationCode = StationCode
        self.ReceiverCode = None
        self.ReceiverSerial = None
        self.ReceiverFirmware = None
        self.AntennaCode = None
        self.AntennaSerial = None
        self.AntennaHeight = None
        self.AntennaNorth = None
        self.HeightCode = None
        self.RadomeCode = None
        self.DateStart = None
        self.DateEnd = None
        self.ReceiverVers = None
        self.records = None
        self.currentrecord = None
        self.hash = None

    def load_data(self, record):

        if isinstance(record,str):
            # parse the text record
            record = self.parse_station_record(record)

        # loads the object from a database object
        self.ReceiverCode = record['ReceiverCode']
        self.ReceiverSerial = record['ReceiverSerial']
        self.ReceiverFirmware = record['ReceiverFirmware']
        self.AntennaCode = record['AntennaCode']
        self.AntennaSerial = record['AntennaSerial']
        self.AntennaHeight = float(record['AntennaHeight'])
        self.AntennaNorth = float(record['AntennaNorth'])
        self.AntennaEast = float(record['AntennaEast'])
        self.HeightCode = record['HeightCode']
        self.RadomeCode = record['RadomeCode']
        self.ReceiverVers = record['ReceiverVers']

        # create a hash record using the station information
        # use only the information that can actually generate a change in the antenna position
        self.hash = zlib.crc32('%.3f %.3f %.3f %s %s' % (self.AntennaNorth, self.AntennaEast, self.AntennaHeight, self.AntennaCode, self.RadomeCode))

        return

    def parse_station_record(self, line):

        fieldnames = ['StationCode', 'StationName', 'DateStart', 'DateEnd', 'AntennaHeight', 'HeightCode', 'AntennaNorth', 'AntennaEast',
                      'ReceiverCode', 'ReceiverVers', 'ReceiverFirmware', 'ReceiverSerial', 'AntennaCode', 'RadomeCode', 'AntennaSerial']

        fieldwidths = (
        1, 6, 18, 19, 19, 9, 7, 9, 9, 22, 22, 7, 22, 17, 7, 20)  # negative widths represent ignored padding fields
        fmtstring = ' '.join('{}{}'.format(abs(fw), 'x' if fw < 0 else 's') for fw in fieldwidths)

        fieldstruct = struct.Struct(fmtstring)
        parse = fieldstruct.unpack_from

        if line[0] == ' ' and len(line) >= 77:
            record = dict(zip(fieldnames, map(str.strip, parse(line.ljust(fieldstruct.size))[1:])))
        else:
            return None

        # convert to datetime object
        DateStart, DateEnd = self.stninfodate2datetime(record['DateStart'], record['DateEnd'])
        record['DateStart'] = DateStart
        record['DateEnd'] = DateEnd
        record['StationCode'] = record['StationCode'].lower()

        return record

    def parse_station_info(self, stninfo_file):

        if isinstance(stninfo_file,list):
            # a list is comming in
            stninfo = stninfo_file
        else:
            # a file is comming in
            with open(stninfo_file, 'r') as fileio:
                stninfo = fileio.readlines()


        fields = []
        for line in stninfo:

            if line[0] == ' ' and len(line) >= 77:
                record = self.parse_station_record(line)

                if record:
                    fields.append(record)

        return fields

    def stninfodate2datetime(self, srtDateStart, strDateEnd):

        sdate1 = srtDateStart.split()
        if int(sdate1[2]) > 23:
            sdate1[2] = '23'
            sdate1[3] = '59'
            sdate1[4] = '59'
        date_start = pyDate.Date(year=sdate1[0], doy=sdate1[1])
        date_start = datetime.datetime(int(date_start.year), date_start.month, date_start.day, int(sdate1[2]),
                                       int(sdate1[3]), int(sdate1[4]))

        sdate2 = strDateEnd.split()
        if sdate2[0] == '9999':
            date_end = None
        else:
            date_end = pyDate.Date(year=sdate2[0], doy=sdate2[1])
            if int(sdate2[2]) > 23:
                sdate2[2] = '23'
                sdate2[3] = '59'
                sdate2[4] = '59'
            date_end = datetime.datetime(int(date_end.year), date_end.month, date_end.day, int(sdate2[2]),
                                         int(sdate2[3]), int(sdate2[4]))

        return date_start, date_end

    def datetime2stninfodate(self, pDateStart, pDateEnd):

        if isinstance(pDateStart, datetime.datetime):
            DateStart = pDateStart
        else:
            DateStart = datetime.datetime.strptime(pDateStart, '%Y-%m-%d %H:%M:%S')

        pyDateStart = pyDate.Date(year=DateStart.year, month=DateStart.month, day=DateStart.day)
        strDataStart = str(pyDateStart.year).ljust(5) + str(pyDateStart.doy).rjust(3, '0').ljust(4) + str(
            DateStart.hour).rjust(2, '0').ljust(3) + str(DateStart.minute).rjust(2, '0').ljust(3) + str(
            DateStart.second).rjust(2, '0').ljust(4)

        if pDateEnd is not None:
            # difference in execution mode between linux and Mac
            if isinstance(pDateEnd, datetime.datetime):
                DateEnd = pDateEnd
            else:
                DateEnd = datetime.datetime.strptime(pDateEnd, '%Y-%m-%d %H:%M:%S')

            pyDateEnd = pyDate.Date(year=DateEnd.year, month=DateEnd.month, day=DateEnd.day)

            strDateEnd = str(pyDateEnd.year).ljust(5) + str(pyDateEnd.doy).rjust(3, '0').ljust(4) + str(
                DateEnd.hour).rjust(2, '0').ljust(3) + str(DateEnd.minute).rjust(2, '0').ljust(3) + str(
                DateEnd.second).rjust(2, '0').ljust(4)
        else:
            strDateEnd = '9999 999 00 00 00  '

        return strDataStart, strDateEnd






class StationInfo(StationInfoRecord):

    def __init__(self, cnn, NetworkCode=None, StationCode=None, date=None, allow_empty=False):

        StationInfoRecord.__init__(self, NetworkCode, StationCode)

        self.record_count = 0
        self.allow_empty = allow_empty
        self.header = '*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  Ant N    Ant E    Receiver Type         Vers                  SwVer  Receiver SN           Antenna Type     Dome   Antenna SN          '
        self.date = None

        # connect to the db and load the station info table
        if NetworkCode is not None and StationCode is not None:

            self.cnn = cnn

            if self.load_stationinfo_records():
                # find the record that matches the given date
                if date is not None:
                    self.date = date
                    pDate = date.datetime()
                    for record in self.records:

                        # DDG: problem with some versions of Python. TypeError: can't compare datetime.datetime to str
                        # seems like there are some instances of record where DateStart comes as a string not as a datetime object

                        if not record['DateEnd']:

                            if type(record['DateStart']) is str:
                                DateStart = datetime.datetime.strptime(record['DateStart'],'%Y-%m-%d %H:%M:%S')
                            else:
                                DateStart = record['DateStart']

                            if pDate >= DateStart:
                                self.load_data(record)
                                self.currentrecord = record
                                break
                        else:
                            if type(record['DateStart']) is str:
                                DateStart = datetime.datetime.strptime(record['DateStart'],'%Y-%m-%d %H:%M:%S')
                            else:
                                DateStart = record['DateStart']

                            if type(record['DateEnd']) is str:
                                DateEnd = datetime.datetime.strptime(record['DateEnd'],'%Y-%m-%d %H:%M:%S')
                            else:
                                DateEnd = record['DateEnd']

                            if pDate >= DateStart and pDate <= DateEnd:
                                self.load_data(record)
                                self.currentrecord = record
                                break

                    if self.AntennaCode is None:
                        raise pyStationInfoException('Could not find a matching station.info record for ' + NetworkCode + '.' + StationCode + ' ' + date.yyyymmdd() + ' (' + date.yyyyddd() + ')')


        return

    def load_stationinfo_records(self):
        # function to load the station info records in the database
        # returns true if records found
        # returns false if none found, unless allow_empty = False in which case it raises an error.
        stninfo = self.cnn.query(
            'SELECT * FROM stationinfo WHERE "NetworkCode" = \'' + self.NetworkCode + '\' AND "StationCode" = \'' + self.StationCode + '\' ORDER BY "DateStart"')

        if stninfo.ntuples() == 0:
            if not self.allow_empty:
                # allow no station info if explicitly requested by the user.
                # Purpose: insert a station info for a new station!
                raise pyStationInfoException('Could not find a station info entry for ' + self.NetworkCode + ' ' + self.StationCode)
            self.record_count = 0
            return False
        else:
            self.records = stninfo.dictresult()
            self.record_count = stninfo.ntuples()
            return True

    def return_stninfo(self, record=None):
        stninfo = []
        # from the records struct, return a station info file
        if not record is None:
            records = [record]
        else:
            records = self.records

        if not records is None:
            for record in records:

                strDateStart,strDateEnd = self.datetime2stninfodate(record['DateStart'],record['DateEnd'])

                stninfo.append(' ' + str(record['StationCode']).ljust(6).upper() + ''.ljust(18) + strDateStart + strDateEnd + str(record['AntennaHeight']).rjust(7) + '  ' +
                               str(record['HeightCode']).ljust(7)      +        str(record['AntennaNorth']).rjust(7)     + '  ' +
                               str(record['AntennaEast']).rjust(7)     + '  ' + str(record['ReceiverCode']).ljust(22)    +
                               str(record['ReceiverVers']).ljust(23)   +        str(record['ReceiverFirmware']).ljust(5) + ' ' +
                               str(record['ReceiverSerial']).ljust(22) +        str(record['AntennaCode']).ljust(17)     +
                               str(record['RadomeCode']).ljust(7)      +        str(record['AntennaSerial']).ljust(20))

        return '\n'.join(stninfo)

    def return_stninfo_short(self, record=None):

        stninfo_lines = self.return_stninfo(record=record).split('\n')

        stninfo_lines = [' ' + self.NetworkCode.upper() + '.' + line[1:110] + ' [...] ' + line[160:] for line in stninfo_lines]

        return '\n'.join(stninfo_lines)

    def overlaps(self, qrecord):
        # check if the incoming record is between any existing record
        overlaps = []

        if not qrecord['DateEnd']:
            q_end = datetime.datetime(2100,1,1)
        else:
            q_end = qrecord['DateEnd']

        q_start = qrecord['DateStart']

        if self.records:
            for record in self.records:

                if not record['DateEnd']:
                    r_end = datetime.datetime(2100, 1, 1)
                else:
                    r_end = record['DateEnd']

                r_start = record['DateStart']

                earliest_end = min(q_end, r_end)
                latest_start = max(q_start, r_start)

                if (earliest_end - latest_start).total_seconds() > 0:
                    overlaps.append(record)

        return overlaps

    def DeleteStationInfo(self, record):

        self.cnn.insert_info('The station information record for ' + self.NetworkCode + '.' + self.StationCode + ': ' +
                record['DateStart'].strftime('%Y-%m-%d %H:%M:%S') + ' has been deleted:\n' +
                self.return_stninfo(record))

        self.cnn.delete('stationinfo', record)
        self.load_stationinfo_records()

    def UpdateStationInfo(self, record, new_record):

        # load the record
        if isinstance(record, str):
            # parse the text record
            record = self.parse_station_record(record)

        if isinstance(new_record, str):
            # parse the text record
            new_record = self.parse_station_record(new_record)

        # avoid problems with trying to insert records from other stations. Force this NetworkCode
        record['NetworkCode'] = self.NetworkCode
        new_record['NetworkCode'] = self.NetworkCode

        if self.NetworkCode and self.StationCode:

            # check the possible overlaps. This record will probably overlap with itself, so check that the overlap has
            # the same DateStart as the original record (that way we know it's an overlap with itself)
            overlaps = self.overlaps(new_record)

            for overlap in overlaps:
                if overlap['DateStart'] != record['DateStart']:
                    # it's overlapping with another record, raise error
                    ds1, de1 = self.datetime2stninfodate(record['DateStart'], record['DateEnd'])
                    ds2, de2 = self.datetime2stninfodate(overlap['DateStart'], overlap['DateEnd'])

                    raise pyStationInfoException('Record %s -> %s overlaps with existing station.info records: %s -> %s' % (ds1.strip(), de1.strip(), ds2.strip(), de2.strip()))

            # insert event (before updating to save all information)
            self.cnn.insert_info(
                'The station information record for ' + self.NetworkCode + '.' + self.StationCode + ': ' +
                record['DateStart'].strftime('%Y-%m-%d %H:%M:%S') + ' has been updated:\n' +
                self.return_stninfo(new_record) +
                '\n+++++++++++++++++++++++++++++++++++++\n' +
                'Previous record:\n' +
                self.return_stninfo(record))

            if new_record['DateStart'] != record['DateStart']:
                self.cnn.query('UPDATE stationinfo SET "DateStart" = \'%s\' WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' %
                               (new_record['DateStart'].strftime('%Y-%m-%d %H:%M:%S'), self.NetworkCode, self.StationCode, record['DateStart'].strftime('%Y-%m-%d %H:%M:%S')))

            self.cnn.update('stationinfo', new_record, NetworkCode=self.NetworkCode, StationCode=self.StationCode, DateStart=new_record['DateStart'])

            self.load_stationinfo_records()

    def InsertStationInfo(self, record):

        # load the record
        if isinstance(record, str):
            # parse the text record
            record = self.parse_station_record(record)

        # avoid problems with trying to insert records from other stations. Force this NetworkCode
        record['NetworkCode'] = self.NetworkCode

        if self.NetworkCode and self.StationCode:
            # check existence of station in the db
            rs = self.cnn.query(
                'SELECT * FROM stationinfo WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' % (
                self.NetworkCode, self.StationCode, record['DateStart'].strftime('%Y-%m-%d %H:%M:%S')))

            if rs.ntuples() == 0:
                # can insert because it's not the same record
                # 1) verify the record is not between any two existing records
                overlaps = self.overlaps(record)

                if overlaps:
                    # if it overlaps all records and the DateStart < self.records[0]['DateStart']
                    # see if we have to extend the initial date
                    if len(overlaps) == len(self.records) and record['DateStart'] < self.records[0]['DateStart']:
                        if self.records_are_equal(record, self.records[0]):
                            # just modify the start date to match the incoming record
                            # self.cnn.update('stationinfo', self.records[0], DateStart=record['DateStart'])
                            # the previous statement seems not to work because it updates a primary key!
                            self.cnn.query(
                                'UPDATE stationinfo SET "DateStart" = \'%s\' WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "DateStart" = \'%s\'' % (
                                record['DateStart'].strftime('%Y-%m-%d %H:%M:%S'), self.NetworkCode, self.StationCode,
                                self.records[0]['DateStart'].strftime('%Y-%m-%d %H:%M:%S')))

                            # insert event
                            self.cnn.insert_info('The start date of the station information record for ' + self.NetworkCode + '.' + self.StationCode + ': ' + self.records[0]['DateStart'].strftime('%Y-%m-%d %H:%M:%S') + ' has been been modified to ' + record['DateStart'].strftime('%Y-%m-%d %H:%M:%S'))
                        else:
                            # new and different record, stop the Session with
                            # EndDate = self.records[0]['DateStart'] - datetime.timedelta(seconds=1) and insert
                            record['DateEnd'] = self.records[0]['DateStart'] - datetime.timedelta(seconds=1)
                            self.cnn.insert('stationinfo', record)

                            # insert event
                            self.cnn.insert_info(
                                'A new station information record was added for ' + self.NetworkCode + '.' + self.StationCode + ':\n' + self.return_stninfo(record))

                    elif len(overlaps) == 1 and overlaps[0] == self.records[-1] and not self.records[-1]['DateEnd']:
                        # overlap with the last session
                        # stop the current valid session
                        self.cnn.update('stationinfo', self.records[-1],
                                       DateEnd=record['DateStart'] - datetime.timedelta(seconds=1))
                        # create the incoming session
                        self.cnn.insert('stationinfo', record)

                        # insert event
                        self.cnn.insert_info(
                            'A new station information record was added for ' + self.NetworkCode + '.' + self.StationCode + ':\n' +
                            self.return_stninfo(record) + '\nThe last record`s DateEnd value was updated to ' + self.records[-1]['DateEnd'].strftime('%Y-%m-%d %H:%M:%S'))

                    else:
                        ds1, de1 = self.datetime2stninfodate(record['DateStart'], record['DateEnd'])

                        stroverlap = []
                        for overlap in overlaps:
                            ds2, de2 = self.datetime2stninfodate(overlap['DateStart'], overlap['DateEnd'])
                            stroverlap.append(' -> '.join([ds2.strip(), de2.strip()]))

                        raise pyStationInfoException('Record %s -> %s overlaps with existing station.info records: %s' % (ds1.strip(), de1.strip(),' '.join(stroverlap)))

                else:
                    # no overlaps, insert the record
                    self.cnn.insert('stationinfo', record)

                    # insert event
                    self.cnn.insert_info(
                        'A new station information record was added for ' + self.NetworkCode + '.' + self.StationCode +
                        ':\n' + self.return_stninfo(record))

                # reload the records
                self.load_stationinfo_records()
            else:
                ds1, de1 = self.datetime2stninfodate(record['DateStart'], record['DateEnd'])
                raise pyStationInfoException('Record %s -> %s already exists in station.info' % (ds1.strip(), de1.strip()))
        else:
            raise pyStationInfoException('Cannot insert record without initializing pyStationInfo with NetworkCode and StationCode')


    def stninfo_record(self, StationCode, strDateStart, strDateEnd, AntennaHeight, HeightCode, AntennaNorth, AntennaEast, ReceiverCode, ReceiverVers, ReceiverFirmware, ReceiverSerial, AntennaCode, RadomeCode, AntennaSerial):

        return ' ' + str(StationCode).ljust(6).upper() + ''.ljust(18) + strDateStart + strDateEnd + str(AntennaHeight).rjust(7) + '  ' +str(HeightCode).ljust(7) + str(AntennaNorth).rjust(7) + '  ' +str(AntennaEast).rjust(7) + '  ' + str(ReceiverCode).ljust(22) +str(ReceiverVers).ljust(23) + str(ReceiverFirmware).ljust(5) + ' ' +str(ReceiverSerial).ljust(22) + str(AntennaCode).ljust(17) + str(RadomeCode).ljust(7) + str(AntennaSerial).ljust(20)

    def rinex_based_stninfo(self, ignore):
        # build a station info based on the information from the RINEX headers
        rs = self.cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'' + self.NetworkCode + '\' AND "StationCode" = \'' + self.StationCode + '\' ORDER BY "ObservationSTime"')

        rnxtbl = rs.dictresult()

        rnx = rnxtbl[0]

        RecCode = rnx['ReceiverType']
        AntCode = rnx['AntennaType']
        RecSerial = rnx['ReceiverSerial']
        AntSerial = rnx['AntennaSerial']
        AntHeig = rnx['AntennaOffset']
        Vers = rnx['ReceiverFw'][:22] # no ReceiverVers in RINEX
        SwVer = Vers[:5]              # no ReceiverVers in RINEX
        RadCode = rnx['AntennaDome']
        StartDate = rnx['ObservationSTime']

        stninfo = []
        count = 0
        for i,rnx in enumerate(rnxtbl):

            if RecSerial != rnx['ReceiverSerial'] or AntSerial != rnx['AntennaSerial'] or AntHeig != rnx['AntennaOffset'] or RadCode != rnx['AntennaDome']:
                # start the counter
                count += 1

                if count > ignore:
                    # make station info line
                    strDateStart, strDateEnd = self.datetime2stninfodate(StartDate, rnxtbl[i-count]['ObservationETime'])

                    stninfo.append(self.stninfo_record(self.StationCode,strDateStart, strDateEnd,AntHeig,'DHARP',0.0,0.0,RecCode,Vers,SwVer,RecSerial,AntCode,RadCode,AntSerial))

                    RecCode = rnx['ReceiverType']
                    AntCode = rnx['AntennaType']
                    RecSerial = rnx['ReceiverSerial']
                    AntSerial = rnx['AntennaSerial']
                    AntHeig = rnx['AntennaOffset']
                    Vers = rnx['ReceiverFw'][:22]
                    SwVer = Vers[:5]
                    RadCode = rnx['AntennaDome']
                    StartDate = rnxtbl[i-count+1]['ObservationSTime']

                    count = 0
            elif RecSerial == rnx['ReceiverSerial'] and AntSerial == rnx['AntennaSerial'] and AntHeig == rnx['AntennaOffset'] and RadCode == rnx['AntennaDome'] and count > 0:
                # we started counting records that where different, but we didn't make it past > ignore, reset counter
                count = 0

        #insert the last record with 9999
        strDateStart, strDateEnd = self.datetime2stninfodate(StartDate, None)
        stninfo.append(self.stninfo_record(self.StationCode, strDateStart, strDateEnd, AntHeig, 'DHARP', 0.0, 0.0, RecCode, Vers, SwVer, RecSerial, AntCode, RadCode, AntSerial))

        return '\n'.join(stninfo) + '\n'

    def records_are_equal(self, record1, record2):

        if record1['ReceiverCode'] != record2['ReceiverCode']:
            return False

        if record1['ReceiverSerial'] != record2['ReceiverSerial']:
            return False

        if record1['AntennaCode'] != record2['AntennaCode']:
            return False

        if record1['AntennaSerial'] != record2['AntennaSerial']:
            return False

        if record1['AntennaHeight'] != record2['AntennaHeight']:
            return False

        if record1['AntennaNorth'] != record2['AntennaNorth']:
            return False

        if record1['AntennaEast'] != record2['AntennaEast']:
            return False

        if record1['HeightCode'] != record2['HeightCode']:
            return False

        if record1['RadomeCode'] != record2['RadomeCode']:
            return False

        return True

    def __eq__(self,stninfo):

        if not isinstance(stninfo,StationInfo):
            raise pyStationInfoException('type: '+str(type(stninfo))+' is invalid. Can only compare pyStationInfo.StationInfo objects')

        if self.AntennaCode != stninfo.AntennaCode:
            return False

        if self.AntennaHeight != stninfo.AntennaHeight:
            return False

        if self.AntennaNorth != stninfo.AntennaNorth:
            return False

        if self.AntennaEast != stninfo.AntennaEast:
            return False

        if self.AntennaSerial != stninfo.AntennaSerial:
            return False

        if self.ReceiverCode != stninfo.ReceiverCode:
            return False

        if self.ReceiverSerial != stninfo.ReceiverSerial:
            return False

        if self.RadomeCode != stninfo.RadomeCode:
            return False

        return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.records = None

    def __enter__(self):
        return self