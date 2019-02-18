"""
Project: Parallel.Archive
Date: 2/22/17 3:27 PM
Author: Demian D. Gomez
"""

import pyProducts
import os


class pySp3Exception(pyProducts.pyProductsException):
    pass


class GetSp3Orbits(pyProducts.OrbitalProduct):

    def __init__(self, sp3archive, date, sp3types, copyto, no_cleanup=False):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.sp3_path = None
        self.RF = None
        self.no_cleanup = no_cleanup

        for sp3type in sp3types:
            self.sp3_filename = sp3type + date.wwwwd() + '.sp3'

            try:
                pyProducts.OrbitalProduct.__init__(self, sp3archive, date, self.sp3_filename, copyto)
                self.sp3_path = self.file_path
                self.type = sp3type
                break
            except pyProducts.pyProductsExceptionUnreasonableDate:
                raise
            except pyProducts.pyProductsException:
                # if the file was not found, go to next
                pass

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.sp3_path is None:
            raise pySp3Exception('Could not find a valid orbit file (types: ' + ', '.join(sp3types) + ') for week ' + str(date.gpsWeek) + ' day ' + str(date.gpsWeekDay) + ' using any of the provided sp3 types')
        else:
            # parse the RF of the orbit file
            try:
                with open(self.sp3_path, 'r') as fileio:
                    line = fileio.readline()

                    self.RF = line[46:51].strip()
            except Exception:
                raise

        return

    def cleanup(self):
        if self.sp3_path and not self.no_cleanup:
            # delete files
            if os.path.isfile(self.sp3_path):
                os.remove(self.sp3_path)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
