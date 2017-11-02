"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class handles the interface between the directory structure of the rinex archive and the databased records.
It can be used to retrieve a rinex path based on a rinex database record
It can also scan the dirs of a supplied path for d.Z and station.info files (the directories and files have to match the
declared directory structure and {stmn}{doy}{session}.{year}d.Z, respectively)
"""

import os
import sys
import scandir
import re
import pyDate
import pyOptions
import pyEvents
import Utils

class RinexStruct():

    def __init__(self, cnn):

        self.cnn = cnn

        # read the structure definition table
        levels = cnn.query('SELECT rinex_tank_struct.*, keys.* FROM rinex_tank_struct LEFT JOIN keys ON keys."KeyCode" = rinex_tank_struct."KeyCode" ORDER BY "Level"')
        self.levels = levels.dictresult()

        keys = cnn.query('SELECT * FROM keys')
        self.keys = keys.dictresult()

        # read the station and network tables
        networks = cnn.query('SELECT * FROM networks')
        self.networks = networks.dictresult()

        stations = cnn.query('SELECT * FROM stations')
        self.stations = stations.dictresult()

        self.Config = pyOptions.ReadOptions('gnss_data.cfg')

    def insert_rinex(self, record=None, rinexobj=None):
        """
        Insert a RINEX record and file into the database and archive. If only record is provided, only insert into db
        If only rinexobj is provided, then RinexRecord of rinexobj is used for the insert. If both are given, then
        RinexRecord overrides the passed record.
        :param record: a RinexRecord dictionary to make the insert to the db
        :param rinexobj: the pyRinex object containing the file being processed
        :param rnxaction: accion to perform to rinexobj.
        :return: True if insertion was successful. False if no insertion was done.
        """

        if record is None and rinexobj is None:
            raise ValueError('insert_rinex exception: both record and rinexobj cannot be None.')

        if rinexobj is not None:
            record = rinexobj.record

        copy_succeeded = False
        archived_crinex = ''

        # check if record exists in the database
        if not self.get_rinex_record(NetworkCode=record['NetworkCode'],
                                     StationCode=record['StationCode'],
                                     ObservationYear=record['ObservationYear'],
                                     ObservationDOY=record['ObservationDOY'],
                                     Interval=record['Interval'],
                                     Completion=float('%.3f' % record['Completion'])):
            # no record, proceed

            # check if we need to perform any rinex operations. We might be inserting a new record, but it may just be
            # a ScanRinex op where we don't copy the file into the archive
            if rinexobj is not None:
                # is the rinex object correctly named?
                rinexobj.apply_file_naming_convention()
                # update the record to the (possible) new name
                record['Filename'] = rinexobj.rinex

            self.cnn.begin_transac()

            try:
                # insert the record in the db
                self.cnn.insert('rinex', record)

                if rinexobj is not None:
                    # a rinexobj was passed, copy it into the archive.

                    path2archive = os.path.join(self.Config.archive_path,
                                                    self.build_rinex_path(record['NetworkCode'], record['StationCode'],
                                                                          record['ObservationYear'], record['ObservationDOY'],
                                                                          with_filename=False, rinexobj=rinexobj))

                    # copy fixed version into the archive
                    archived_crinex = rinexobj.compress_local_copyto(path2archive)
                    copy_succeeded = True
                    # get the rinex filename to update the database
                    archived_rinex = rinexobj.rinex_from_crinex(os.path.basename(archived_crinex))

                    if archived_rinex != rinexobj.rinex:
                        # update the table with the filename (always force with step)
                        self.cnn.query('UPDATE rinex SET "Filename" = \'%s\' '
                                       'WHERE "NetworkCode" = \'%s\ '
                                       'AND "StationCode" = \'%s\' '
                                       'AND "ObservationYear" = %i '
                                       'AND "ObservationDOY" = %i '
                                       'AND "Interval" = %i '
                                       'AND "Completion = %.3f'
                                       'AND "Filename" = \'%s\'' %
                                       (archived_rinex,
                                        record['NetworkCode'],
                                        record['StationCode'],
                                        record['ObservationYear'],
                                        record['ObservationDOY'],
                                        record['Interval'],
                                        record['Completion'],
                                        record['Filename']))

                    event = pyEvents.Event(Description='A new RINEX was added to the archive: %s' % record['Filename'],
                                           NetworkCode=record['NetworkCode'],
                                           StationCode=record['StationCode'],
                                           Year=record['ObservationYear'],
                                           DOY=record['ObservationDOY'])
                else:
                    event = pyEvents.Event(Description='Archived CRINEX file %s added to the database.' % (record['Filename']),
                                           NetworkCode=record['NetworkCode'],
                                           StationCode=record['StationCode'],
                                           Year=record['ObservationYear'],
                                           DOY=record['ObservationDOY'])

                self.cnn.insert_event(event)

            except Exception as e:
                self.cnn.rollback_transac()

                if rinexobj and copy_succeeded:
                    # transaction rolled back due to error. If file made into the archive, delete it.
                    os.remove(archived_crinex)

                raise e

            self.cnn.commit_transac()

            return True
        else:
            # record already existed
            return False

    def remove_rinex(self, record, move_to_dir=None):
        # function to remove a file from the archive
        # should receive a rinex record
        # if move_to is None, file is deleted
        # otherwise, moves file to specified location
        try:
            self.cnn.begin_transac()
            # propagate the deletes
            # check if this rinex file is the file that was processed and used for solutions
            rs = self.cnn.query(
                    'SELECT * FROM rinex_proc WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i AND "Filename" = \'%s\''
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY'], record['Filename']))

            if rs.ntuples() > 0:
                self.cnn.query(
                    'DELETE FROM gamit_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))
                self.cnn.query(
                    'DELETE FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))

            # get the filename
            rinex_path = self.build_rinex_path(record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY'], filename=record['Filename'])
            rinex_path = os.path.join(self.Config.archive_path, rinex_path)

            # delete the rinex record
            self.cnn.query(
                'DELETE FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i AND "Filename" = \'%s\''
                % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY'], record['Filename']))

            if os.path.isfile(rinex_path):
                if move_to_dir:

                    filename = Utils.move(rinex_path, os.path.join(move_to_dir, os.path.basename(rinex_path)))
                    description = 'RINEX %s was removed from the database and archive. File moved to %s. See next events for reason.' % (record['Filename'], filename)
                else:

                    os.remove(rinex_path)
                    description = 'RINEX %s was removed from the database and archive. File was deleted. See next events for reason.' % (record['Filename'])

            else:
                description = 'RINEX %s was removed from the database and archive. File was NOT found so no deletion was performed. See next events for reason.' % (record['Filename'])

            # insert an event
            event = pyEvents.Event(
                Description=description,
                NetworkCode=record['NetworkCode'],
                StationCode=record['StationCode'],
                EventType='info',
                Year=record['ObservationYear'],
                DOY=record['ObservationDOY'])

            self.cnn.insert_event(event)

            self.cnn.commit_transac()
        except Exception:
            self.cnn.rollback_transac()
            raise

    def get_rinex_record(self, **kwargs):
        """
        Retrieve a single or multiple records from the rinex table given a set parameters. If parameters are left empty,
        it wil return all records matching the specified criteria. Each parameter acts like a filter, narrowing down the
        records returned by the function. The default behavior is to use tables rinex or rinex_proc depending on the
        provided parameters. E.g. if Interval, Completion and Filename are all left blank, the function will return the
        records using rinex_proc. Otherwise, the rinex table will be used.
        :param NetworkCode: filter
        :param StationCode: filter
        :param ObservationYear: filter
        :param ObservationDOY: filter
        :param Interval: filter
        :param Completion: filter
        :param Filename: filter
        :return: a dictionary will the records matching the provided parameters
        """

        if any(param in ['Interval', 'Completion', 'Filename'] for param in kwargs.keys()):
            table = 'rinex'
        else:
            table = 'rinex_proc'

        # get table fields
        fields = self.cnn.get_columns(table)
        psql = []

        # parse args
        for key in kwargs:

            if key not in [field for field in fields.keys()]:
                raise ValueError('Parameter ' + key + ' is not a field in table ' + table)

            if key is not 'ObservationFYear':
                # avoid FYear due to round off problems
                arg = kwargs[key]

                if 'character' in fields[key]:
                    psql += ['"%s" = \'%s\'' % (key, arg)]

                elif 'numeric' in fields[key]:
                    psql += ['"%s" = %f' % (key, arg)]


        sql = 'SELECT * FROM %s ' % table
        sql += 'WHERE ' + ' AND '.join(psql) if psql else ''

        return self.cnn.query(sql).dictresult()

    def check_directory_struct(self, ArchivePath, NetworkCode, StationCode, date):

        path = self.build_rinex_path(NetworkCode,StationCode,date.year,date.doy,False)

        try:
            if not os.path.isdir(os.path.join(ArchivePath,path)):
                os.makedirs(os.path.join(ArchivePath,path))
        except OSError:
            # race condition: two prcesses trying to create the same folder
            pass

        return

    def parse_crinex_filename(self, filename):
        # parse a crinex filename
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([d])\.[Z]$', filename)

        if sfile:
            return sfile[0]
        else:
            return []

    def parse_rinex_filename(self, filename):
        # parse a rinex filename
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([o])$', filename)

        if sfile:
            return sfile[0]
        else:
            return []

    def scan_archive_struct(self, rootdir, progress_bar=None):

        self.archiveroot = rootdir

        rnx = []
        path2rnx = []
        fls = []
        for path, _, files in scandir.walk(rootdir):
            for file in files:
                # DDG issue #15: match the name of the file to a valid rinex filename
                if self.parse_crinex_filename(file):
                    # only add valid rinex compressed files
                    fls.append(file)
                    rnx.append(os.path.join(path,file).rsplit(rootdir+'/')[1])
                    path2rnx.append(os.path.join(path,file))

                    if progress_bar is not None:
                        progress_bar.set_postfix(CRINEX=rnx[-1])
                        progress_bar.update()
                else:
                    if file.endswith('DS_Store') or file[0:2] == '._':
                        # delete the stupid mac files
                        try:
                            os.remove(os.path.join(path, file))
                        except Exception:
                            sys.exc_clear()

        return rnx, path2rnx, fls

    def scan_archive_struct_stninfo(self,rootdir):

        # same as scan archive struct but looks for station info files
        self.archiveroot = rootdir

        stninfo = []
        path2stninfo = []
        for path, dirs, files in scandir.walk(rootdir):
            for file in files:
                if file.endswith(".info"):
                    # only add valid rinex compressed files
                    stninfo.append(os.path.join(path,file).rsplit(rootdir+'/')[1])
                    path2stninfo.append(os.path.join(path,file))
                else:
                    if file.endswith('DS_Store') or file[0:2] == '._':
                        # delete the stupid mac files
                        try:
                            os.remove(os.path.join(path, file))
                        except Exception:
                            sys.exc_clear()

        return stninfo,path2stninfo

    def build_rinex_path(self, NetworkCode, StationCode, ObservationYear, ObservationDOY, with_filename=True, filename=None, rinexobj=None):
        """
        Function to get the location in the archive of a rinex file. It has two modes of operation:
        1) retrieve an existing rinex file, either specific or the rinex for processing
        (most complete, largest interval) or a specific rinex file (already existing in the rinex table).
        2) To get the location of a potential file (probably used for injecting a new file in the archive. No this mode,
        filename has no effect.
        :param NetworkCode: NetworkCode of the station being retrieved
        :param StationCode: StationCode of the station being retrieved
        :param ObservationYear: Year of the rinex file being retrieved
        :param ObservationDOY: DOY of the rinex file being retrieved
        :param with_filename: if set, returns a path including the filename. Otherwise, just returns the path
        :param filename: name of a specific file to search in the rinex table
        :param rinexobj: a pyRinex object to pull the information from (to fill the achive keys).
        :return: a path with or without filename
        """
        if not rinexobj:
            # not an insertion (user wants the rinex path of existing file)
            # build the levels struct
            sql_list = []
            for level in self.levels:
                sql_list.append('"' + level['rinex_col_in'] + '"')

            sql_list.append('"Filename"')

            sql_string = ", ".join(sql_list)

            if filename:
                if self.parse_crinex_filename(filename):
                    filename = filename.replace('d.Z','o')

                # if filename is set, user requesting a specific file: query rinex table
                rs = self.cnn.query('SELECT ' + sql_string + ' FROM rinex WHERE "NetworkCode" = \'' + NetworkCode + '\' AND "StationCode" = \'' + StationCode + '\' AND "ObservationYear" = ' + str(
                    ObservationYear) + ' AND "ObservationDOY" = ' + str(ObservationDOY) + ' AND "Filename" = \'' + filename + '\'')
            else:
                # if filename is NOT set, user requesting a the processing file: query rinex_proc
                rs = self.cnn.query(
                    'SELECT ' + sql_string + ' FROM rinex_proc WHERE "NetworkCode" = \'' + NetworkCode + '\' AND "StationCode" = \'' + StationCode + '\' AND "ObservationYear" = ' + str(
                        ObservationYear) + ' AND "ObservationDOY" = ' + str(ObservationDOY))

            if rs.ntuples() != 0:
                field = rs.dictresult()[0]
                keys = []
                for level in self.levels:
                    keys.append(str(field[level['rinex_col_in']]).zfill(level['TotalChars']))

                if with_filename:
                    # database stores rinex, we want crinex
                    return "/".join(keys) + "/" + field['Filename'].replace(field['Filename'].split('.')[-1], field['Filename'].split('.')[-1].replace('o', 'd.Z'))
                else:
                    return "/".join(keys)
            else:
                return None
        else:
            # new file (get the path where it's supposed to go)
            keys = []
            for level in self.levels:
                if level['isnumeric'] == '1':
                    kk = str(rinexobj.record[level['rinex_col_in']]).zfill(level['TotalChars'])
                else:
                    kk = str(rinexobj.record[level['rinex_col_in']])

                if len(kk) != level['TotalChars']:
                    raise ValueError('Invalid record \'%s\' for key \'%s\'' % (kk, level['KeyCode']))

                keys += [kk]

            path = '/'.join(keys)
            valid, _ = self.parse_archive_keys(os.path.join(path, rinexobj.crinex), tuple([item['KeyCode'] for item in self.levels]))

            if valid:
                if with_filename:
                    return os.path.join(path, rinexobj.crinex)
                else:
                    return path
            else:
                raise ValueError('Invalid path result: %s' % path)

    def parse_archive_keys(self, path, key_filter=()):

        try:
            pathparts = path.split('/')
            filename = path.split('/')[-1]

            # check the number of levels in pathparts against the number of expected levels
            # subtract one for the filename
            if len(pathparts) - 1 != len(self.levels):
                return False, {}

            if not filename.endswith('.info'):
                fileparts = self.parse_crinex_filename(filename)
            else:
                # parsing a station info file, fill with dummy the doy and year
                fileparts = ('dddd', '1', '0', '80')

            if fileparts:
                keys = dict()

                # fill in all the possible keys using the crinex file info
                keys['station'] = fileparts[0]
                keys['doy'] = int(fileparts[1])
                keys['session'] = fileparts[2]
                keys['year'] = int(fileparts[3])
                keys['network'] = 'rnx'

                # now look in the different levels to match more data (or replace filename keys)
                for key in self.levels:

                    if len(pathparts[key['Level'] - 1]) != key['TotalChars']:
                        return False, {}

                    if key['isnumeric'] == '1':
                        keys[key['KeyCode']] = int(pathparts[key['Level']-1])
                    else:
                        keys[key['KeyCode']] = pathparts[key['Level'] - 1].lower()

                # check date is valid and also fill day and month keys
                date = pyDate.Date(year=keys['year'], doy=keys['doy'])
                keys['day'] = date.day
                keys['month'] = date.month

                return True, {key: keys[key] for key in keys.keys() if key in key_filter}
            else:
                return False, {}

        except Exception as e:
            return False, {}

