"""
Project:
Date: 2/23/17 10:12 AM
Author: Demian D. Gomez
"""
import os
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
    def __init__(self, archive, date, filename, copyto):

        if date.gpsWeek < 0 or date > pyDate.Date(datetime=datetime.now()):
            # do not allow negative weeks or future orbit downloads!
            raise pyProductsExceptionUnreasonableDate('Orbit requested for an unreasonable date: '
                                                      'week ' + str(date.gpsWeek) + \
                                                      ' day ' + str(date.gpsWeekDay) + \
                                                      ' (' + date.yyyyddd() + ')')

        archive = archive.replace('$year',     str(date.year)) \
                         .replace('$doy',      str(date.doy).zfill(3)) \
                         .replace('$gpsweek',  str(date.gpsWeek).zfill(4)) \
                         .replace('$gpswkday', str(date.gpsWeekDay))

        self.archive  = archive
        self.path     = None
        self.filename = filename

        archive_file_path = os.path.join(archive, self.filename)
        copy_path         = os.path.join(copyto,  self.filename)

        self.file_path = copy_path

        # try both zipped and unzipped n files
        if os.path.isfile(archive_file_path):
            copyfile(archive_file_path,
                     copy_path)
        else:
            for ext in ('.Z', '.gz', '.zip'):
                if os.path.isfile(archive_file_path + ext):
                    copyfile(archive_file_path + ext,
                             copy_path + ext)

                    pyRunWithRetry.RunCommand('gunzip -f ' + copy_path + ext, 15).run_shell()
                    break
            else:
                raise pyProductsException('Could not find the archive file for ' + self.filename)

