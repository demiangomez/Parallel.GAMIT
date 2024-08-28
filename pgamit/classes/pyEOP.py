"""
Project: Parallel.Archive
Date: 2/23/17 2:52 PM
Author: Demian D. Gomez

This class fetches earth orientation parameters files from the orbits folder (specified in the gnss_data.cfg file) passed as an argument (sp3archive)

"""
import pyDate
import pyProducts
import pyEvents


class pyEOPException(pyProducts.pyProductsException):
    def __init__(self, value):
        self.value = value
        self.event = pyEvents.Event(Description=value, EventType='error', module=type(self).__name__)

    def __str__(self):
        return str(self.value)


class GetEOP(pyProducts.OrbitalProduct):

    def __init__(self, sp3archive, date, sp3types, copyto):

        # try both compressed and non-compressed sp3 files
        # loop through the types of sp3 files to try
        self.eop_path = None

        # determine the date of the first day of the week
        week = pyDate.Date(gpsWeek=date.gpsWeek, gpsWeekDay=0)

        for sp3type in sp3types:
            if sp3type[0].isupper():
                # long name IGS format
                self.eop_filename = (sp3type.replace('{YYYYDDD}', week.yyyyddd(space=False)).
                                     replace('{INT}', '01D').
                                     replace('{PER}', '07D') + 'ERP.ERP')
            else:
                # short name IGS format
                self.eop_filename = sp3type.replace('{WWWWD}', week.wwww()) + '7.erp'

            try:
                pyProducts.OrbitalProduct.__init__(self, sp3archive, date, self.eop_filename, copyto)
                self.eop_path = self.file_path
                self.type     = sp3type
                break

            except pyProducts.pyProductsExceptionUnreasonableDate:
                raise

            # rapid EOP files do not work in NRCAN PPP
            # except pyProducts.pyProductsException:
            #    # rapid orbits do not have 7.erp, try wwwwd.erp

            #    self.eop_filename = sp3type + date.wwwwd() + '.erp'

            #    pyProducts.OrbitalProduct.__init__(self, sp3archive, date, self.eop_filename, copyto)
            #    self.eop_path = self.file_path

            except pyProducts.pyProductsException:
                # if the file was not found, go to next
                pass

        # if we get here and self.sp3_path is still none, then no type of sp3 file was found
        if self.eop_path is None:
            raise pyEOPException(
                'Could not find a valid earth orientation parameters file for gps week ' + date.wwww() +
                ' using any of the provided sp3 types')
