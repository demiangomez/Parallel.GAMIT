"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez
"""

from shutil import copyfile
import os
import pyProducts

class pyBrdcException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class GetBrdcOrbits(pyProducts.OrbitalProduct):

    def __init__(self,brdc_archive, date, copyto, no_cleanup=False):

        self.brdc_archive = brdc_archive
        self.brdc_path = None
        self.no_cleanup = no_cleanup

        # try both zipped and unzipped n files
        self.brdc_filename = 'brdc' + str(date.doy).zfill(3) + '0.' + str(date.year)[2:4] + 'n'

        try:
            pyProducts.OrbitalProduct.__init__(self, self.brdc_archive, date, self.brdc_filename, copyto)
            self.brdc_path = self.file_path

        except pyProducts.pyProductsException:
            raise pyBrdcException(
                'Could not find the broadcast ephemeris file for ' + str(date.year) + ' ' + str(date.doy))
        except:
            raise


        return

    def cleanup(self):
        if self.brdc_path and not self.no_cleanup:
            # delete files
            if os.path.isfile(self.brdc_path):
                os.remove(self.brdc_path)

        return

    def __del__(self):
        self.cleanup()
        return

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self