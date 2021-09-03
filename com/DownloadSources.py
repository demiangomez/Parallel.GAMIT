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
from shutil import rmtree, copy
import glob
import urllib.request, urllib.parse, urllib.error
import subprocess

# deps
import numpy as np
from tqdm import tqdm

# app
import pyDate
import pyOptions
import dbConnection
import Utils
import pyArchiveStruct
import pysftp
import pyRinex
import pyStationInfo
from Utils import (required_length,
                   process_date,
                   print_columns,
                   indent)



TIMEOUT = 10


def replace_vars(filename, date, stationcode):

    return filename.replace('${year}',     str(date.year)) \
                   .replace('${doy}',      str(date.doy).zfill(3)) \
                   .replace('${day}',      str(date.day).zfill(2)) \
                   .replace('${month}',    str(date.month).zfill(2)) \
                   .replace('${gpsweek}',  str(date.gpsWeek).zfill(4)) \
                   .replace('${gpswkday}', str(date.gpsWeekDay)) \
                   .replace('${year2d}',   str(date.year)[2:]) \
                   .replace('${month2d}',  str(date.month).zfill(2)) \
                   .replace('${STATION}',  stationcode.upper()) \
                   .replace('${station}',  stationcode.lower()) \


def main():
    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to process given in [net].[stnm] format or just [stnm] "
                             "(separated by spaces; if [stnm] is not unique in the database, all stations with that "
                             "name will be processed). Use keyword 'all' to process all stations in the database. "
                             "If [net].all is given, all stations from network [net] will be processed. "
                             "Alternatevily, a file with the station list can be provided.")

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1, 2),
                        metavar='date_start|date_end',
                        help="Date range to check given as [date_start] or [date_start] "
                             "and [date_end]. Allowed formats are yyyy.doy or yyyy/mm/dd..")

    parser.add_argument('-win', '--window', nargs=1, metavar='days', type=int,
                        help="Download data from a given time window determined by today - {days}.")

    try:
        args = parser.parse_args()

        cnn    = dbConnection.Cnn('gnss_data.cfg')
        Config = pyOptions.ReadOptions('gnss_data.cfg')

        stnlist = Utils.process_stnlist(cnn, args.stnlist)

        print(' >> Selected station list:')
        print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in stnlist])

        dates = []
        now   = datetime.now()

        try:
            if args.window:
                # today - ndays
                d = pyDate.Date(year  = now.year,
                                month = now.month,
                                day   = now.day)
                dates = [d-int(args.window[0]), d]
            else:
                dates = process_date(args.date_range)

        except ValueError as e:
            parser.error(str(e))

        if dates[0] < pyDate.Date(gpsWeek=650, gpsWeekDay=0):
            dates = [pyDate.Date(gpsWeek=650, gpsWeekDay=0),
                     pyDate.Date(year  = now.year,
                                 month = now.month,
                                 day   = now.day)]

        # go through the dates
        drange = np.arange(dates[0].mjd,
                           dates[1].mjd + 1, 1)

        download_data(cnn, Config, stnlist, drange)

    except argparse.ArgumentTypeError as e:
        parser.error(str(e))


def download_data(cnn, Config, stnlist, drange):

    archive = pyArchiveStruct.RinexStruct(cnn)

    pbar = tqdm(desc='%-30s' % ' >> Downloading stations declared in data_source', total=len(drange)*len(stnlist), ncols=160)

    for mdj in drange:
        date = pyDate.Date(mjd=mdj)

        for stn in stnlist:

            StationCode = stn['StationCode']
            NetworkCode = stn['NetworkCode']

            station_id = '%s.%s' % (StationCode, NetworkCode)

            pbar.set_postfix(current='%s %s' % (station_id, date.yyyyddd()))
            pbar.update()

            try:
                _ = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode, date=date)
            except pyStationInfo.pyStationInfoHeightCodeNotFound:
                # if the error is that no height code is found, then there is a record
                pass
            except pyStationInfo.pyStationInfoException:
                # no possible data here, inform and skip
                tqdm.write(' >> %s skipped: no station information available -> assume station is inactive' % station_id)
                continue

            rinex = archive.get_rinex_record(NetworkCode     = NetworkCode,
                                             StationCode     = StationCode,
                                             ObservationYear = date.year,
                                             ObservationDOY  = date.doy)

            download = not rinex or rinex[0]['Completion'] < 0.5

            if download:
                rs = cnn.query('SELECT * FROM data_source WHERE "NetworkCode" = \'%s\' '
                               'AND "StationCode" = \'%s\' ORDER BY try_order' % (NetworkCode, StationCode))
                sources = rs.dictresult()

                for source in sources:

                    tqdm.write(' >> Need to download %s %s' % (station_id, date.yyyyddd()))

                    result = False

                    folder   = os.path .dirname(replace_vars(source['path'], date, StationCode))
                    filename = os.path.basename(replace_vars(source['path'], date, StationCode))
                    destiny  = os.path.join(Config.repository_data_in, source['fqdn'].replace(':', '_'))

                    protocol = source['protocol'].lower() 
                    if protocol == 'ftp':
                        result = download_ftp(source['fqdn'], source['username'], source['password'],
                                              folder, destiny, filename)

                    elif protocol == 'sftp':
                        result = download_sftp(source['fqdn'], source['username'], source['password'],
                                               folder, destiny, filename)

                    elif protocol == 'http':
                        result = download_http(source['fqdn'], folder, destiny, filename)

                    else:
                        tqdm.write('   -- Unknown protocol %s for %s' % (protocol, station_id))


                    if result:
                        tqdm.write('   -- Successful download of %s %s' % (station_id, date.yyyyddd()))

                        # success downloading file
                        if source['format']:
                            tqdm.write('   -- File requires postprocess using scheme %s' % (source['format']))
                            process_file(os.path.join(destiny, filename),
                                         filename, destiny, source['format'], StationCode, date)

                        break
                    else:
                        tqdm.write('   -- Could not download %s %s -> trying next source' % 
                                   (station_id, date.yyyyddd()))
            else:
                tqdm.write(' >> File for %s %s already in db' % (station_id, date.yyyyddd()))

    pbar.close()


def process_file(filepath, filename, destiny, source, StationCode, date):
    # post-process of data

    temp_dir = os.path.join(destiny, 'temp')

    try:

        if os.path.isfile(filepath):
            if not os.path.isdir(temp_dir):
                os.makedirs(temp_dir)

        src = source.lower()

        if src in ('ibge', 'uruguay'):
            os.system('unzip -o "%s" -d "%s" > /dev/null' % (filepath, temp_dir))

        elif src == 'chile':
            os.system('gzip -f -d -c "%s" > %s' % (filepath, os.path.join(temp_dir, filename.replace('.gz', ''))))

        elif src == 'igac':
            os.system('gzip -f -d -c "%s" > %s' % (filepath,
                                                   os.path.join(temp_dir,
                                                                filename.replace('o.Z', 'o').replace('O.Z', 'o'))))
            os.system("cd " + temp_dir + "; for f in *; do mv $f `echo $f | tr '[:upper:]' '[:lower:]'`; done")
        elif src == 'rnx2crz':
            # scheme rnx2crz does not require any pre-process, just copy the file
            copy(filepath, temp_dir)
        else:
            tqdm.write('   -- Unknown process scheme: %s' % src)

        # open rinex file
        ofile = glob.glob(temp_dir + '/*.??[oOdD]')

        if ofile:
            rinex = pyRinex.ReadRinex('???', StationCode, ofile[0])
            # compress rinex to data_in
            rinex.compress_local_copyto(destiny)
            # remove downloaded zip
            os.remove(filepath)

        # remove temp folder
        rmtree(temp_dir)

    except Exception as e:
        tqdm.write('   -- ERROR in process_file: %s' % str(e))

        try:
            if os.path.isdir(temp_dir):
                rmtree(temp_dir)

            if os.path.isfile(filepath):
                os.remove(filepath)

        except Exception as e:
            tqdm.write('   -- ERROR in ERROR_HANDLER: %s' % str(e))




def download_ftp(fqdn, username, password, folder, destiny, filename):

    try:
        tqdm.write('   -- Connecting to ' + fqdn)

        # connect to ftp
        # ftp = ftplib.FTP(fqdn, username, password)

        if not os.path.exists(destiny):
            os.makedirs(destiny)
            tqdm.write('   -- Creating dir ' + destiny)

        # tqdm.write('   -- Changing folder to ' + folder)

        # ftp.cwd(folder)
        # ftp_list = ftp.nlst()
        # if filename in ftp_list:
        #     ftp.retrbinary("RETR " + filename, open(os.path.join(destiny, filename), 'wb').write)
        # else:
        #    ftp.quit()
        #    return False
        # ftp.quit()

        destiny_path = os.path.join(destiny, filename)
        p = subprocess.Popen('wget --user=%s --password=%s -O %s ftp://%s%s || rm -f %s'
                             % (username, password, destiny_path, fqdn,
                                os.path.join(folder, filename),
                                destiny_path),
                             shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE)

        stdout, stderr = p.communicate()

        if stdout:
            tqdm.write(indent(stdout, 6))

        if stderr:
            tqdm.write(indent(stderr, 6))

        return os.path.isfile(destiny_path)

    except Exception as e:
        # folder not present, skip
        tqdm.write('   -- ftp error: ' + str(e))
        return False


def download_sftp(fqdn, username, password, folder, destiny, filename):
    try:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        # connect to ftp
        if ':' in fqdn:
            port = fqdn.split(':')
            fqdn = port[0]
            port = int(port[1])
        else:
            port = 22

        # sftp = pysftp.Connection(fqdn, port=port, username=username, password=password, cnopts=cnopts)

        # tqdm.write('   -- Connecting to ' + fqdn)

        if not os.path.exists(destiny):
            os.makedirs(destiny)
            tqdm.write('   -- Creating dir ' + destiny)

        # tqdm.write('   -- Changing folder to ' + folder)

        # sftp.chdir(folder)

        # ftp_list = sftp.listdir()

        # if filename in ftp_list:
        #     sftp.get(filename, os.path.join(destiny, filename))
        # else:
        #    sftp.close()
        #    return False

        #sftp.close()

        return False

    except Exception as e:
        # folder not present, skip
        tqdm.write('   -- ftp error: ' + str(e))
        return False


def download_http(fqdn, folder, destiny, filename):

    try:

        if not os.path.exists(destiny):
            os.makedirs(destiny)
            tqdm.write('   -- Creating dir ' + destiny)

        # rinex = urllib.URLopener()
        url_path = os.path.join(folder, filename)
        tqdm.write('   -- %s%s ' % (fqdn, url_path))
        # rinex.retrieve("http://%s%s" % (fqdn, os.path.join(folder, filename)), os.path.join(destiny, filename))
        destiny_path = os.path.join(destiny, filename)
        p = subprocess.Popen('wget -O %s http://%s%s || rm -f %s'
                             % (destiny_path, fqdn, url_path, destiny_path),
                             shell  = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.PIPE)

        stdout, stderr = p.communicate()
        if stdout:
            tqdm.write(indent(stdout, 6))
        if stderr:
            tqdm.write(indent(stderr, 6))

    except Exception as e:
        # folder not present, skip
        tqdm.write('   -- http error: ' + str(e))
        return False

    return os.path.isfile(os.path.join(destiny, filename))


if __name__ == '__main__':
    main()
