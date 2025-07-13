"""
Project:
Date: 2/23/17 10:12 AM
Author: Demian D. Gomez
"""
import os
import glob
import re
from shutil import copyfile
from datetime import datetime

# app
from pgamit import pyRunWithRetry
from pgamit import pyEvents
from pgamit import pyDate
from pgamit.Utils import file_open, file_try_remove, crc32


class pyProductsException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description = value,
                                    EventType   = 'error',
                                    module      = type(self).__name__)

    def __str__(self):
        return str(self.value)


class pyProductsExceptionUnreasonableDate(pyProductsException):
    pass


class pySp3Exception(pyProductsException):
    pass


class pyClkException(pyProductsException):
    pass


class pyEOPException(pyProductsException):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)

    def __str__(self):
        return str(self.value)


class pyBrdcException(pyProductsException):
    pass


class OrbitalProduct:
    def __init__(self, archive, date, filename, copyto, short_name=True):
        """
        Module to obtain IGS products.
        archive   : location of the local archive where files live
        date      : date of the orbit file being retrieved
        filename  : orbital product file name (now with REGEX for version)
        short_name: if True, then copy the product to destination using shortname format (default is True)
        """
        if date.gpsWeek < 0 or date > pyDate.Date(datetime=datetime.now()):
            # do not allow negative weeks or future orbit downloads!
            raise pyProductsExceptionUnreasonableDate('Orbit requested for an unreasonable date: '
                                                      'week ' + str(date.gpsWeek) +
                                                      ' day ' + str(date.gpsWeekDay) +
                                                      ' (' + date.yyyyddd() + ')')

        archive = archive.replace('$year',     str(date.year)) \
                         .replace('$doy',      str(date.doy).zfill(3)) \
                         .replace('$gpsweek',  str(date.gpsWeek).zfill(4)) \
                         .replace('$gpswkday', str(date.gpsWeekDay))

        self.archive  = archive
        self.path     = None
        self.filename = ''
        self.archive_filename = ''
        self.version  = 0
        self.interval = 0
        self.hash     = 0

        # DDG: new behavior -> search for all available versions of a file and use largest one
        # first, check if letter is upper case, which means we are getting a long filename
        if filename[0].isupper():
            r = re.compile('(' + filename + ')')
            match = list(filter(r.match, os.listdir(archive)))
            for prod in match:
                if int(prod[3]) >= self.version:
                    # save the version
                    self.version = int(prod[3])
                    # save the interval
                    self.interval = int(prod[27:27 + 2])
                    # assign archive_filename with current product candidate
                    # archive_filename should be the basename without the compression extension
                    self.archive_filename = os.path.splitext(os.path.basename(prod))[0]

            # redo this loop to determine if there is a file with the selected version that has a > interval
            for prod in match:
                if int(prod[27:27+2]) > self.interval and int(prod[3]) >= self.version:
                    # if interval is greater and version is the same, keep the file with larger interval
                    # this is to speed up the processing
                    self.interval = int(prod[27:27+2])
                    self.archive_filename = os.path.splitext(os.path.basename(prod))[0]

            # DDG: new behavior -> if short_name then use short name destination file
            if short_name:
                # get file extension
                cnt = os.path.splitext(os.path.basename(self.archive_filename))[1].lower()
                snm = self.archive_filename[0:3].lower() + date.wwwwd() + cnt
                # replace the filename with the short name version
                self.filename = snm
        else:
            # short name version, do nothing
            self.filename = filename
            self.archive_filename = filename

        copy_path = os.path.join(copyto, self.filename)
        archive_file_path = os.path.join(archive, self.archive_filename)
        self.file_path = copy_path

        # try both zipped and unzipped n files
        if os.path.isfile(archive_file_path):
            # if enters here, then uncompressed file exists in the orbits archive
            copyfile(archive_file_path, copy_path)
        else:
            for ext in ('.Z', '.gz', '.zip'):
                if os.path.isfile(archive_file_path + ext):
                    copyfile(archive_file_path + ext, copy_path + ext)

                    pyRunWithRetry.RunCommand('gunzip -f ' + copy_path + ext, 15).run_shell()
                    break
            else:
                raise pyProductsException('Could not find the archive file for ' + self.filename)


class GetSp3Orbits(OrbitalProduct):

    def __init__(self, sp3archive, date, sp3types, copyto, no_cleanup=False):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.sp3_path   = None
        self.RF         = None
        self.no_cleanup = no_cleanup

        for sp3type in sp3types:
            # DDG: now the filename is built as a REGEX string and the latest version of the file is obtained
            # detect the type of sp3 file we are using (long name: upper case; short name: lowercase)
            if sp3type[0].isupper():
                # long name IGS format
                self.sp3_filename = (sp3type.replace('{YYYYDDD}', date.yyyyddd(space=False)).
                                     replace('{INT}', '[0-1]5M').
                                     replace('{PER}', '01D') + 'ORB.SP3')
            else:
                # short name IGS format
                self.sp3_filename = sp3type.replace('{WWWWD}', date.wwwwd()) + '.sp3'

            try:
                OrbitalProduct.__init__(self, sp3archive, date, self.sp3_filename, copyto)
                self.sp3_path = self.file_path
                self.type     = sp3type
                break
            except pyProductsExceptionUnreasonableDate:
                raise
            except pyProductsException:
                # if the file was not found, go to next
                continue

        # create a hash value with the name of the orbit file
        self.hash = crc32(self.archive_filename)

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.sp3_path is None:
            raise pySp3Exception('Could not find a valid orbit file (types: ' +
                                 ', '.join(sp3types) + ') for '
                                 'week ' + str(date.gpsWeek) +
                                 ' day ' + str(date.gpsWeekDay) + ' (' + date.yyyymmdd() + ')'
                                 ' using any of the provided sp3 types')

        # parse the RF of the orbit file
        with file_open(self.sp3_path) as fileio:
            line = fileio.readline()

            self.RF = line[46:51].strip()

    def cleanup(self):
        if self.sp3_path and not self.no_cleanup:
            # delete files
            file_try_remove(self.sp3_path)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self


class GetClkFile(OrbitalProduct):

    def __init__(self, clk_archive, date, sp3types, copyto, no_cleanup=False):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.clk_path   = None
        self.no_cleanup = no_cleanup

        for sp3type in sp3types:
            # DDG: now the filename is built as a REGEX string and the latest version of the file is obtained
            # detect the type of sp3 file we are using (long name: upper case; short name: lowercase)
            if sp3type[0].isupper():
                # long name IGS format
                self.clk_filename = (sp3type.replace('{YYYYDDD}', date.yyyyddd(space=False)).
                                     replace('{INT}', '[0-3][0-5][SM]').
                                     replace('{PER}', '01D') + 'CLK.CLK')
            else:
                # short name IGS format
                self.clk_filename = sp3type.replace('{WWWWD}', date.wwwwd()) + '.clk'

            try:
                OrbitalProduct.__init__(self, clk_archive, date, self.clk_filename, copyto)
                self.clk_path = self.file_path
                break
            except pyProductsExceptionUnreasonableDate:
                raise
            except pyProductsException:
                # if the file was not found, go to next
                continue

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.clk_path is None:
            raise pyClkException('Could not find a valid clocks file for ' + date.wwwwd() + ' (' + date.yyyymmdd() + ')'
                                 ' using any of the provided sp3 types')

    def cleanup(self):
        if self.clk_path and not self.no_cleanup:
            # delete files
            file_try_remove(self.clk_path)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self


class GetEOP(OrbitalProduct):

    def __init__(self, sp3archive, date, sp3types, copyto):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.eop_path = None

        for sp3type in sp3types:
            # determine the date of the first day of the week
            # DDG: COD products give the ERP at the end of the week, IGS at the beginning
            if sp3type[0:3] == 'COD':
                week = pyDate.Date(gpsWeek=date.gpsWeek, gpsWeekDay=6)
            else:
                week = pyDate.Date(gpsWeek=date.gpsWeek, gpsWeekDay=0)

            if sp3type[0].isupper():
                # long name IGS format
                self.eop_filename = (sp3type.replace('{YYYYDDD}', week.yyyyddd(space=False)).
                                     replace('{INT}', '01D').
                                     replace('{PER}', '07D') + '(?:ERP|ORB).ERP')
            else:
                # short name IGS format
                self.eop_filename = sp3type.replace('{WWWWD}', week.wwww()) + '7.erp'

            try:
                OrbitalProduct.__init__(self, sp3archive, date, self.eop_filename, copyto)
                self.eop_path = self.file_path
                self.type     = sp3type
                break

            except pyProductsExceptionUnreasonableDate:
                raise

            # rapid EOP files do not work in NRCAN PPP
            # except pyProducts.pyProductsException:
            #    # rapid orbits do not have 7.erp, try wwwwd.erp

            #    self.eop_filename = sp3type + date.wwwwd() + '.erp'

            #    pyProducts.OrbitalProduct.__init__(self, sp3archive, date, self.eop_filename, copyto)
            #    self.eop_path = self.file_path

            except pyProductsException:
                # if the file was not found, go to next
                pass

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.eop_path is None:
            raise pyEOPException(
                'Could not find a valid earth orientation parameters file for gps week ' + date.wwww() +
                ' using any of the provided sp3 types')


class GetBrdcOrbits(OrbitalProduct):

    def __init__(self, brdc_archive, date, copyto, no_cleanup=False):

        self.brdc_archive = brdc_archive
        self.brdc_path    = None
        self.no_cleanup   = no_cleanup
        # DDG: for compatibility with sp3 object
        self.type         = 'brdc'

        # try both zipped and unzipped n files
        self.brdc_filename = 'brdc' + str(date.doy).zfill(3) + '0.' + str(date.year)[2:4] + 'n'

        try:
            OrbitalProduct.__init__(self, self.brdc_archive, date, self.brdc_filename, copyto)
            self.brdc_path = self.file_path

        except pyProductsExceptionUnreasonableDate:
            raise
        except pyProductsException:
            raise pyBrdcException(
                'Could not find the broadcast ephemeris file for ' + str(date.year) + ' ' + str(date.doy))

    def cleanup(self):
        if self.brdc_path and not self.no_cleanup:
            # delete files
            if os.path.isfile(self.brdc_path):
                os.remove(self.brdc_path)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
