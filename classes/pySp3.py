"""
Project: Parallel.Archive
Date: 2/22/17 3:27 PM
Author: Demian D. Gomez

AUG 2 2023: changed the default behavior (due to new naming convention from IGS)
the sp3_ keywords in gnss_data.cfg incorporate
sp3_ac: an ordered list of the precedence of Analysis Centers to get orbits from (IGS, JPL, COD, etc)
sp3_cs: an ordered list of campaign/project specifications that determines which product to download. In general the
        first one is R03,R02,etc and then OPS
sp3_st: an ordered list of solution types. In general the first one is FIN and then RAP

if the new orbit name scheme results in no match, then by default we fall back to the old naming convention using the
ACs specified in sp3_ac using the following download tries (where xx or xxx is the lowercase AC code) xx2, xxx, xxr
The sp3_type_x and sp3_altr_x are now deprecated.
"""

import os

# app
import pyProducts
from Utils import file_open, file_try_remove


class pySp3Exception(pyProducts.pyProductsException):
    pass


class GetSp3Orbits(pyProducts.OrbitalProduct):

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
                pyProducts.OrbitalProduct.__init__(self, sp3archive, date, self.sp3_filename, copyto)
                self.sp3_path = self.file_path
                self.type     = sp3type
                break
            except pyProducts.pyProductsExceptionUnreasonableDate:
                raise
            except pyProducts.pyProductsException:
                # if the file was not found, go to next
                continue

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
