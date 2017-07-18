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

class RinexStruct():

    def __init__(self, cnn):

        self.cnn = cnn

        # read the structure definition table
        levels = cnn.query('SELECT rinex_tank_struct.*, keys.* FROM rinex_tank_struct LEFT JOIN keys ON keys."KeyCode" = rinex_tank_struct."KeyCode" ORDER BY "Level"')
        self.levels = levels.dictresult()

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

    def scan_archive_struct(self,rootdir):

        self.archiveroot = rootdir

        rnx = []
        path2rnx = []
        for path, dirs, files in os.walk(rootdir):
            for file in files:
                if file.endswith("d.Z"):
                    # only add valid rinex compressed files
                    rnx.append(os.path.join(path,file).rsplit(rootdir+'/')[1])
                    path2rnx.append(os.path.join(path,file))

                if file.endswith('DS_Store') or file[0:2] == '._':
                    # delete the stupid mac files
                    try:
                        os.remove(os.path.join(path, file))
                    except:
                        sys.exc_clear()

        return rnx,path2rnx

    def scan_archive_struct_stninfo(self,rootdir):

        # same as scan archive struct but looks for station info files
        self.archiveroot = rootdir

        stninfo = []
        path2stninfo = []
        for path, dirs, files in os.walk(rootdir):
            for file in files:
                if file.endswith(".info"):
                    # only add valid rinex compressed files
                    stninfo.append(os.path.join(path,file).rsplit(rootdir+'/')[1])
                    path2stninfo.append(os.path.join(path,file))

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

        day = None
        month = None
        year = None
        network = None
        station = None
        doy = None

        # split the fields and verify if everything is OK
        try:
            valid = True
            keys = []
            for level in self.levels:
                if not level.get('KeyCode') in key_filter and len(key_filter) > 0:
                    # skip this key if not requested in key_filter
                    continue
                keys.append(path.split('/')[level.get('Level')-1])

                if len(keys[-1]) != level.get('TotalChars'):
                    # invalid key in this level
                    valid = False

            if valid:
                for level in self.levels:
                    if not level.get('KeyCode') in key_filter and len(key_filter) > 0:
                        # skip this key if not requested in key_filter
                        continue
                    if level.get('isnumeric') == 1:
                        exec("%s = %d" % (level.get('KeyCode'), int(path.split('/')[level.get('Level') - 1])))
                    else:
                        exec("%s = '%s'.lower()" % (level.get('KeyCode'), path.split('/')[level.get('Level') - 1]))

            if not station and 'station' in key_filter:
                # station code not defined (and it was requested), parse it from the file
                station = path.split('/')[-1][0:4].lower()

            if not network and 'network' in key_filter:
                # network code not defined, assign default (if requested)
                network = 'rnx'

            if not doy and 'doy' in key_filter:
                # doy not defined (and it was requested), try to parse it from the file
                try:
                    doy = int(path.split('/')[-1][4:3])
                except:
                    valid = False
        except IndexError:
            return False, network, station, year, doy, month, day

        return valid,network,station,year,doy,month,day

    def get_archive_filelist(self,archive,network,station):

        varnames = []
        for level in self.levels:
            if level.get('KeyCode') == 'network' or level.get('KeyCode') == 'station':
                varnames.append(level.get('KeyCode'))

        exec('filter = %s' % (' + "/" + '.join(varnames)))

        filter_archive = []
        for rinex in archive:
            if filter in rinex:
                filter_archive.append(rinex)

        return filter_archive
