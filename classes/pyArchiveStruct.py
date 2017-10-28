"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

This class handles the interface between the directory structure of the rinex archive and the databased records.
It can be used to retrieve a rinex path based on a rinex database record
It can also scan the dirs of the archive for d.Z and station.info files
"""

import os
import sys
import scandir
import re
import pyDate

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

    def archive_dict(self,rootdir):
        """
        Creates a nested dictionary that represents the folder structure of rootdir
        """
        dir = {}
        rootdir = rootdir.rstrip(os.sep)
        start = rootdir.rfind(os.sep) + 1
        for path, dirs, files in os.walk(rootdir):
            folders = path[start:].split(os.sep)
            subdir = dict.fromkeys(files)
            parent = reduce(dict.get, folders[:-1], dir)
            parent[folders[-1]] = subdir

        # the first item in the dict is the root folder (e.g. rinex), we just return the folders inside the root,
        # which should be the level 1 information
        return dir.values()[0]

    def check_directory_struct(self, ArchivePath, NetworkCode, StationCode, date):

        path = self.build_rinex_path(NetworkCode,StationCode,date.year,date.doy,False)

        try:
            if not os.path.isdir(os.path.join(ArchivePath,path)):
                os.makedirs(os.path.join(ArchivePath,path))
        except OSError:
            # racing condition: two prcesses trying to create the same folder
            pass
        except:
            raise

        return

    def parse_crinex_filename(self, filename):
        # parse a crinex filename
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([d])\.[Z]', filename)

        if sfile:
            return sfile[0]
        else:
            return []

    def parse_rinex_filename(self, filename):
        # parse a rinex filename
        sfile = re.findall('(\w{4})(\d{3})(\w{1})\.(\d{2})([o])', filename)

        if sfile:
            return sfile[0]
        else:
            return []

    def scan_archive_struct(self,rootdir):

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
                else:
                    if file.endswith('DS_Store') or file[0:2] == '._':
                        # delete the stupid mac files
                        try:
                            os.remove(os.path.join(path, file))
                        except:
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
                        except:
                            sys.exc_clear()

        return stninfo,path2stninfo

    def build_rinex_path(self, NetworkCode, StationCode, ObservationYear, ObservationDOY, with_filename=True):

        # build the levels struct
        sql_list = []
        for level in self.levels:
            sql_list.append('"' + level.get('rinex_col_in') + '"')

        sql_list.append('"Filename"')

        sql_string = ", ".join(sql_list)

        rs = self.cnn.query('SELECT ' + sql_string + ' FROM rinex WHERE "NetworkCode" = \'' + NetworkCode + '\' AND "StationCode" = \'' + StationCode + '\' AND "ObservationYear" = ' + str(
            ObservationYear) + ' AND "ObservationDOY" = ' + str(ObservationDOY))

        if rs.ntuples() != 0:
            field = rs.dictresult()[0]
            keys = []
            for level in self.levels:
                keys.append(str(field.get(level.get('rinex_col_in'))).zfill(level.get('TotalChars')))

            if with_filename:
                # database stores rinex, we want crinex
                return "/".join(keys) + "/" + field['Filename'].replace(field['Filename'].split('.')[-1], field['Filename'].split('.')[-1].replace('o', 'd.Z'))
            else:
                return "/".join(keys)
        else:
            return None

    def parse_archive_keys(self, path, key_filter=()):

        try:
            pathparts = path.split('/')
            filename = path.split('/')[-1]
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

