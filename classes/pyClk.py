"""
Project: Parallel.Archive
Date: 2/22/17 3:27 PM
Author: Demian D. Gomez

This class fetches statellite clock files from the orbits folder (specified in the gnss_data.cfg file) passed as an argument (clk_archive)
"""

import pyProducts
import os

class pyClkException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

class GetClkFile(pyProducts.OrbitalProduct):

    def __init__(self,clk_archive,date,sp3types,copyto,no_cleanup=False):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.clk_path = None
        self.no_cleanup = no_cleanup

        for sp3type in sp3types:
            self.clk_filename = sp3type + date.wwwwd() + '.clk'

            try:
                pyProducts.OrbitalProduct.__init__(self, clk_archive, date, self.clk_filename, copyto)
                self.clk_path = self.file_path
                break
            except pyProducts.pyProductsException:
                # if the file was not found, go to next
                pass
            except:
                # some other error, raise to parent
                raise

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.clk_path is None:
            raise pyClkException('Could not find a valid clocks file for ' + date.wwwwd() + ' using any of the provided sp3 types')

        return

    def cleanup(self):
        if self.clk_path and not self.no_cleanup:
            # delete files
            if os.path.isfile(self.clk_path):
                os.remove(self.clk_path)

    def __del__(self):
        self.cleanup()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __enter__(self):
        return self
