"""
Project: Parallel.GAMIT
Date: 11/8/17 9:24 AM
Author: Demian D. Gomez

Script to synchronize sp3 and brdc orbits using the CDDIS FTP server.
"""

import os
import pyDate
import argparse
import pyOptions
from Utils import required_length
from Utils import process_date
from datetime import datetime
import numpy as np
from tqdm import tqdm
import ftplib
import zlib

def get_archive_path(archive, date):

    archive = archive.replace('$year', str(date.year))
    archive = archive.replace('$doy', str(date.doy).zfill(3))
    archive = archive.replace('$gpsweek', str(date.gpsWeek).zfill(4))
    archive = archive.replace('$gpswkday', str(date.gpsWeekDay))

    return archive

def main():
    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1,2), metavar='date_start|date_end', help="Date range to check given as [date_start] or [date_start] and [date_end]. Allowed formats are yyyy.doy or yyyy/mm/dd..")

    try:
        args = parser.parse_args()

        Config = pyOptions.ReadOptions('gnss_data.cfg')

        dates = []

        try:
            dates = process_date(args.date_range)
        except ValueError as e:
            parser.error(str(e))

        if dates[0] < pyDate.Date(gpsWeek=650, gpsWeekDay=0):
            dates = [pyDate.Date(gpsWeek=650, gpsWeekDay=0),
                     pyDate.Date(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)]

        # go through the dates
        drange = np.arange(dates[0].mjd, dates[1].mjd, 1)

        pbar = tqdm(desc='%-30s' % ' >> Synchronizing orbit files', total=len(drange), ncols=160)

        # connect to ftp
        ftp = ftplib.FTP('198.118.242.40', 'Anonymous', 'gomez.124@osu.edu')

        for date in [pyDate.Date(mjd=mdj) for mdj in drange]:

            sp3_archive = get_archive_path(Config.sp3_path, date)

            for repro in ['', '/repro2']:
                # try both in the repro and / folders
                folder = "/pub/gps/products/" + date.wwww() + repro
                try:
                    ftp.cwd(folder)
                except ftplib.error_perm:
                    # folder not present, skip
                    continue

                tqdm.write(' -- Changing folder to ' + folder)
                ftp_list = ftp.nlst()

                for orbit in Config.sp3types + Config.sp3altrn:

                    for ext in ['.sp3.Z', '.clk.Z', '.erp.Z']:
                        filename = orbit + date.wwwwd() + ext

                        if not os.path.isfile(os.path.join(sp3_archive, filename)) and filename in ftp_list:
                            tqdm.write('%-31s: %s' % (' -- trying to download ' + ext.replace('.Z', '').upper(), filename))
                            ftp.retrbinary("RETR " + filename, open(os.path.join(sp3_archive, filename), 'wb').write)

                    # now the eop file
                    filename = orbit + date.wwww() + '7.erp.Z'
                    if not os.path.isfile(os.path.join(sp3_archive, filename)) and filename in ftp_list:
                        tqdm.write('%-31s: %s' % (' -- trying to download EOP', filename))
                        ftp.retrbinary("RETR " + filename, open(os.path.join(sp3_archive, filename), 'wb').write)

            ###### now the brdc files #########

            folder = "/pub/gps/data/daily/%s/%s/%sn" % (date.yyyy(), date.ddd(), date.yyyy()[2:])
            tqdm.write(' -- Changing folder to ' + folder)
            ftp.cwd(folder)
            ftp_list = ftp.nlst()

            brdc_archive = get_archive_path(Config.brdc_path, date)
            filename = 'brdc' + str(date.doy).zfill(3) + '0.' + str(date.year)[2:4] + 'n'

            if not os.path.isfile(os.path.join(brdc_archive, filename)) and filename + '.Z' in ftp_list:
                tqdm.write('%-31s: %s' % (' -- trying to download BRDC', filename))
                #ftp.retrbinary("RETR " + filename + '.Z', open(os.path.join(sp3_archive, filename), 'wb').write)
                # decompress file

            pbar.set_postfix(gpsWeek='%i %i' % (date.gpsWeek, date.gpsWeekDay))
            pbar.update()

        pbar.close()
        ftp.quit()

    except argparse.ArgumentTypeError as e:
        parser.error(str(e))


if __name__ == '__main__':
    main()