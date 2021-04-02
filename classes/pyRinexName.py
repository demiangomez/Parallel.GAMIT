"""
Project: Parallel.GAMIT
Date: 7/15/20 5:25 PM
Author: Demian D. Gomez

"""

import os
import re
from pyDate import Date
from pyEvents import Event

TYPE_CRINEZ = 0
TYPE_RINEX = 1
TYPE_RINEZ = 2
TYPE_CRINEX = 3

version_2_ext = {TYPE_CRINEZ: 'd.Z',
                 TYPE_RINEX: 'o',
                 TYPE_RINEZ: 'o.Z',
                 TYPE_CRINEX: 'd'}

version_3_ext = {TYPE_CRINEZ: 'crx.gz',
                 TYPE_RINEX: 'rnx',
                 TYPE_RINEZ: 'rnx.gz',
                 TYPE_CRINEX: 'crx'}


def check_year(year):
    # to check for wrong dates in RinSum

    if int(year) - 1900 < 80 and int(year) >= 1900:
        year = int(year) - 1900 + 2000

    elif int(year) < 1900 and int(year) >= 80:
        year = int(year) + 1900

    elif int(year) < 1900 and int(year) < 80:
        year = int(year) + 2000

    return year


class RinexNameException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = Event(Description=value, EventType='error')

    def __str__(self):
        return str(self.value)


class RinexNameFormat(object):
    def __init__(self, filename):
        self.path = os.path.dirname(filename)
        self.filename = os.path.basename(filename)
        self.version = 0

        self.type = self.identify_rinex_type(filename)

        parts = self.split_filename(filename)
        try:
            if self.version < 3:
                self.StationCode = parts[0]
                self.monument = None
                self.receiver = None
                self.country = None
                self.doy = parts[1]
                self.session = parts[2]
                self.year = parts[3]
                self.format_compression = parts[4]
                self.start_time = None
                self.data_source = None
                self.file_period = None
                self.data_frequency = None
                self.data_type = None
                self.date = Date(year=check_year(self.year), doy=int(self.doy))
                self.month = self.date.month
                self.day = self.date.day
            else:
                self.StationCode = parts[0][0:4]
                self.monument = parts[0][4:5]
                self.receiver = parts[0][5:6]
                self.country = parts[0][6:]
                self.session = None
                self.year = parts[2][0:4]
                self.doy = parts[2][4:7]
                self.date = Date(year=int(self.year), doy=int(self.doy))
                self.month = self.date.month
                self.day = self.date.day
                self.format_compression = parts[6]
                self.start_time = parts[2]
                self.data_source = parts[1]
                self.file_period = parts[3]
                self.data_frequency = parts[4]
                self.data_type = parts[5]
        except Exception as e:
            raise RinexNameException(e)

    def identify_rinex_type(self, filename):

        # get the type of file passed
        filename = os.path.basename(filename)

        if (filename.endswith('d.Z') or filename.endswith('o') or
                filename.endswith('o.Z') or filename.endswith('d')):
            self.version = 2
        else:
            self.version = 3

        if self.version < 3:
            if filename.endswith('d.Z'):
                return TYPE_CRINEZ
            elif filename.endswith('o'):
                return TYPE_RINEX
            elif filename.endswith('o.Z'):
                return TYPE_RINEZ
            elif filename.endswith('d'):
                return TYPE_CRINEX
            else:
                raise RinexNameException('Invalid filename format: ' + filename)
        else:
            # DDG: itentify file type from filename
            sfile = re.findall(r'[A-Z0-9]{9}_[RSU]_[0-9]{11}_[0-9]{2}[MHDYU]_[0-9]{2}[CZSMHDU]_'
                               r'[GREJCISM][OMN]\.(crx|rnx)(.gz|.zip|.bzip2|.bz2)?$', filename)
            if sfile:
                if sfile[0][0] == 'rnx' and sfile[0][1] is not '':
                    return TYPE_RINEZ
                elif sfile[0][0] == 'rnx' and sfile[0][1] is '':
                    return TYPE_RINEX
                elif sfile[0][0] == 'crx' and sfile[0][1] is not '':
                    return TYPE_CRINEZ
                elif sfile[0][0] == 'crx' and sfile[0][1] is '':
                    return TYPE_CRINEX
            else:
                raise RinexNameException('Could not determine the rinex type (malformed filename): ' + filename)

    def to_rinex_format(self, to_type, no_path=False):

        if no_path:
            path = ''
        else:
            path = self.path

        if self.version < 3:
            # join the path to the file again
            return os.path.join(path, self.StationCode + self.doy + self.session + '.' + self.year +
                                version_2_ext[to_type])
        else:
            # join the path to the file again
            return os.path.join(path, self.StationCode + self.monument + self.receiver + self.country + '_' +
                                self.data_source + '_' + self.start_time + '_' + self.file_period + '_' +
                                self.data_frequency + '_' + self.data_type + '.' + version_3_ext[to_type])

    def filename_no_ext(self, no_path=False):

        if no_path:
            path = ''
        else:
            path = self.path

        if self.version < 3:
            # join the path to the file again
            return os.path.join(self.path, self.StationCode + self.doy + self.session + '.' + self.year)
        else:
            return os.path.join(self.path, self.StationCode + self.monument + self.receiver + self.country + '_' +
                                self.data_source + '_' + self.start_time + '_' + self.file_period + '_' +
                                self.data_frequency + '_' + self.data_type)

    def split_filename(self, filename):

        if self.version < 3:
            sfile = re.findall(r'(\w{4})(\d{3})(\w)\.(\d{2})([doOD]\.?[Z]?)$', filename)

            if sfile:
                return sfile[0]
            else:
                raise RinexNameException(
                    'Invalid filename format: ' + filename + ' for rinex version ' + str(self.version))
        else:
            sfile = re.findall(r'([A-Z0-9]{9})_([RSU])_([0-9]{11})_([0-9]{2}[MHDYU])_([0-9]{2}[CZSMHDU])_'
                               r'([GREJCISM][OMN])\.((?:crx|rnx)(?:.gz|.zip|.bzip2|.bz2)?)$', filename)
            if sfile:
                return sfile[0]
            else:
                raise RinexNameException(
                    'Invalid filename format: ' + filename + ' for rinex version ' + str(self.version))