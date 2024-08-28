"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez


This class fetches broadcast orbits from the brdc folder (specified in the 
gnss_data.cfg file) passed as an argument (brdc_archive)
"""

import os

# app
import pyProducts


class pyBrdcException(pyProducts.pyProductsException):
    pass


class GetBrdcOrbits(pyProducts.OrbitalProduct):

    def __init__(self, brdc_archive, date, copyto, no_cleanup=False):

        self.brdc_archive = brdc_archive
        self.brdc_path    = None
        self.no_cleanup   = no_cleanup
        # DDG: for compatibility with sp3 object
        self.type         = 'brdc'

        # try both zipped and unzipped n files
        self.brdc_filename = 'brdc' + str(date.doy).zfill(3) + '0.' + str(date.year)[2:4] + 'n'

        try:
            pyProducts.OrbitalProduct.__init__(self, self.brdc_archive, date, self.brdc_filename, copyto)
            self.brdc_path = self.file_path

        except pyProducts.pyProductsExceptionUnreasonableDate:
            raise
        except pyProducts.pyProductsException:
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
