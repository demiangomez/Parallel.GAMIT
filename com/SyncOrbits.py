#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 11/8/17 9:24 AM
Author: Demian D. Gomez

Script to synchronize sp3 and brdc orbits using the CDDIS FTP server.
"""

import os
import argparse
from datetime import datetime
import ftplib
import zlib

# deps
import numpy as np
from tqdm import tqdm

# app
import pyDate
import pyOptions
from Utils import required_length, process_date
import pyRunWithRetry

# Old FTP server:
#FTP_HOST = '198.118.242.40'

# New FTP-SSL server:
FTP_HOST = 'gdc.cddis.eosdis.nasa.gov'
FTP_USER = 'Anonymous'
FTP_PASS = 'gomez.124@osu.edu'

# @todo
# METHOD = 'HTTP'   # 'FTP' | 'HTTP'
# Taken from https://wiki.earthdata.nasa.gov/display/EL/How+To+Access+Data+With+Python
# http://sgf.rgo.ac.uk/forumNESC/index.php?topic=58.0
# *?list


def main():
    parser = argparse.ArgumentParser( description = 'Archive operations Main Program')

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1, 2), metavar='date_start|date_end',
                        help="Date range to check given as [date_start] or [date_start] and [date_end]. "
                             "Allowed formats are yyyy.doy or yyyy/mm/dd..")

    parser.add_argument('-win', '--window', nargs=1, metavar='days', type=int,
                        help="Download data from a given time window determined by today - {days}.")

    try:
        args   = parser.parse_args()
        Config = pyOptions.ReadOptions('gnss_data.cfg')

        dates = ()
        now   = datetime.now()
        try:
            if args.window:
                # today - ndays
                d = pyDate.Date( year = now.year,
                                month = now.month,
                                 day  = now.day)
                dates = (d - int(args.window[0]),
                         d)
            else:
                dates = process_date(args.date_range)
        except ValueError as e:
            parser.error(str(e))

        if dates[0] < pyDate.Date(gpsWeek=650, gpsWeekDay=0):
            dates = (pyDate.Date(gpsWeek=650, gpsWeekDay=0),
                     pyDate.Date(year  = now.year,
                                 month = now.month,
                                 day  =  now.day))

        # go through the dates
        drange = np.arange(dates[0].mjd,
                           dates[1].mjd, 1)

        pbar = tqdm(desc='%-30s' % ' >> Synchronizing orbit files', total=len(drange), ncols=160)

        # connect to ftp
        ftp = ftplib.FTP_TLS(FTP_HOST, FTP_USER, FTP_PASS)
 
        ftp.set_pasv(True)
        ftp.prot_p()

        def downloadIfMissing(ftp_list, ftp_filename, local_filename, local_dir, desc):
            mark_path = os.path.join(local_dir, local_filename)
            if not os.path.isfile(mark_path) and ftp_filename in ftp_list:
                tqdm.write('%-31s: %s' % (' -- trying to download ' + desc, filename))
                down_path = os.path.join(local_dir, ftp_filename)
                with open(down_path, 'wb') as f:
                    ftp.retrbinary("RETR " + ftp_filename, f.write)
                return True

        def get_archive_path(archive, date):
            return archive.replace('$year',     str(date.year)) \
                          .replace('$doy',      str(date.doy).zfill(3)) \
                          .replace('$gpsweek',  str(date.gpsWeek).zfill(4)) \
                          .replace('$gpswkday', str(date.gpsWeekDay))

        for date in (pyDate.Date(mjd=mdj) for mdj in drange):

            sp3_archive = get_archive_path(Config.sp3_path, date)

            if not os.path.exists(sp3_archive):
                os.makedirs(sp3_archive)

            for repro in ('', '/repro2', '/repro3'):
                # try both in the repro and / folders
                folder = "/pub/gps/products/" + date.wwww() + repro
                try:
                    tqdm.write(' -- Changing folder to ' + folder)
                    ftp.cwd(folder)
                    ftp_list = set(ftp.nlst())
                except Exception:
                    # folder not present, skip
                    continue

                for orbit in Config.sp3types + Config.sp3altrn:
                    for ext in ('.sp3', '.clk', '.erp', '7.erp'):
                        try:
                            if ext == '7.erp':
                                filename = orbit + date.wwww() + ext + '.Z'
                            else:
                                filename = orbit + date.wwwwd() + ext + '.Z'
                            downloadIfMissing(ftp_list,
                                              filename,
                                              filename,
                                              sp3_archive,
                                              'EOP' if ext == '7.erp' else ext.upper())
                        except:
                            pass

            ###### now the brdc files #########

            try:
                folder = "/pub/gps/data/daily/%s/%s/%sn" % (date.yyyy(), date.ddd(), date.yyyy()[2:])
                tqdm.write(' -- Changing folder to ' + folder)
                ftp.cwd(folder)
                ftp_list = set(ftp.nlst())
            except:
                continue

            brdc_archive = get_archive_path(Config.brdc_path, date)

            if not os.path.exists(brdc_archive):
                os.makedirs(brdc_archive)

            try:
                filename     = 'brdc%s0.%sn' % (str(date.doy).zfill(3),
                                                str(date.year)[2:4])
                ftp_filename = filename + '.gz'
                if downloadIfMissing(ftp_list,
                                     ftp_filename,
                                     filename,
                                     brdc_archive,
                                     'BRDC'):
                    # decompress file
                    tqdm.write('  -> Download succeeded %s' %  os.path.join(brdc_archive, ftp_filename))
                    pyRunWithRetry.RunCommand('gunzip -f ' + os.path.join(brdc_archive, ftp_filename),
                                              15).run_shell()
            except Exception as e:
                tqdm.write(' -- BRDC ERROR: %s' % str(e))

            pbar.set_postfix(gpsWeek='%i %i' % (date.gpsWeek, date.gpsWeekDay))
            pbar.update()

        pbar.close()
        ftp.quit()

    except argparse.ArgumentTypeError as e:
        parser.error(str(e))


if __name__ == '__main__':
    main()
