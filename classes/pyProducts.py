"""
Project:
Date: 2/23/17 10:12 AM
Author: Demian D. Gomez
"""
import os
from shutil import copyfile
import pyRunWithRetry
import pyEvents
import pyDate
from datetime import datetime


class pyProductsException(Exception):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)

    def __str__(self):
        return str(self.value)


class pyProductsExceptionUnreasonableDate(pyProductsException):
    pass


class OrbitalProduct(object):

    def __init__(self, archive, date, filename, copyto):

        if date.gpsWeek < 0 or date > pyDate.Date(datetime=datetime.now()):
            # do not allow negative weeks or future orbit downloads!
            raise pyProductsExceptionUnreasonableDate('Orbit requested for an unreasonable date: week '
                                                      + str(date.gpsWeek) + ' day ' + str(date.gpsWeekDay) +
                                                      ' (' + date.yyyyddd() + ')')

        archive = archive.replace('$year', str(date.year))
        archive = archive.replace('$doy', str(date.doy).zfill(3))
        archive = archive.replace('$gpsweek', str(date.gpsWeek).zfill(4))
        archive = archive.replace('$gpswkday', str(date.gpsWeekDay))

        self.archive = archive
        self.path = None
        self.filename = filename

        # try both zipped and unzipped n files
        archive_file_path = os.path.join(archive, self.filename)

        if os.path.isfile(archive_file_path):
            try:
                copyfile(archive_file_path, os.path.join(copyto, self.filename))
                self.file_path = os.path.join(copyto, self.filename)
            except Exception:
                raise
        else:
            ext = None
            if os.path.isfile(archive_file_path + '.Z'):
                ext = '.Z'
            elif os.path.isfile(archive_file_path + '.gz'):
                ext = '.gz'
            elif os.path.isfile(archive_file_path + '.zip'):
                ext = '.zip'

            if ext is not None:
                copyfile(archive_file_path + ext, os.path.join(copyto, self.filename + ext))
                self.file_path = os.path.join(copyto, self.filename)

                cmd = pyRunWithRetry.RunCommand('gunzip -f ' + self.file_path + ext, 15)
                try:
                    cmd.run_shell()
                except Exception:
                    raise
            else:
                raise pyProductsException('Could not find the archive file for ' + self.filename)
