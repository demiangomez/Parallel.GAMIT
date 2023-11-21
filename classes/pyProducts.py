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
import pyRunWithRetry
import pyEvents
import pyDate


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

        # DDG: new behavior -> search for all available versions of a file and use largest one
        # first, check if letter is upper case, which means we are getting a long filename
        if filename[0].isupper():
            r = re.compile('(' + filename + ')')
            match = list(filter(r.match, os.listdir(archive)))
            for prod in match:
                if int(prod[3]) >= self.version:
                    # save the version
                    self.version = int(prod[3])
                    # assign archive_filename with current product candidate
                    # archive_filename should be the basename without the compression extension
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
