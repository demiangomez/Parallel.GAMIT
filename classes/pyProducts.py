"""
Project:
Date: 2/23/17 10:12 AM
Author: Demian D. Gomez
"""
import os
from shutil import copyfile
import pyRunWithRetry

class pyProductsException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class OrbitalProduct():

    def __init__(self,archive, date, filename, copyto):

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
            except:
                raise
        else:
            ext = None
            if os.path.isfile(archive_file_path + '.Z'):
                ext = '.Z'
            elif os.path.isfile(archive_file_path + '.gz'):
                ext = '.gz'
            elif os.path.isfile(archive_file_path + '.zip'):
                ext = '.zip'

            if not ext is None:
                copyfile(archive_file_path + ext, os.path.join(copyto, self.filename + ext))
                self.file_path = os.path.join(copyto, self.filename)

                cmd = pyRunWithRetry.RunCommand('gunzip -f ' + self.file_path + ext, 15)
                try:
                    cmd.run_shell()
                except:
                    raise
            else:
                raise pyProductsException('Could not find the archive file for ' + self.filename)

        return