"""
Project: Parallel.Archive
Date: 2/22/17 3:27 PM
Author: Demian D. Gomez

This class fetches statellite clock files from the orbits folder (specified in 
the gnss_data.cfg file) passed as an argument (clk_archive)
"""

import os

# app
import pyProducts
from Utils import file_try_remove


class pyClkException(pyProducts.pyProductsException):
    pass


class GetClkFile(pyProducts.OrbitalProduct):

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
                pyProducts.OrbitalProduct.__init__(self, clk_archive, date, self.clk_filename, copyto)
                self.clk_path = self.file_path
                break
            except pyProducts.pyProductsExceptionUnreasonableDate:
                raise
            except pyProducts.pyProductsException:
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
