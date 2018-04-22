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
import pyRunWithRetry
import dbConnection
import Utils
from Utils import print_columns
import pyArchiveStruct
import pysftp

def replace_vars(filename, date):

    filename = filename.replace('${year}', str(date.year))
    filename = filename.replace('${doy}', str(date.doy).zfill(3))
    filename = filename.replace('${day}', str(date.day).zfill(2))
    filename = filename.replace('${month}', str(date.month).zfill(2))
    filename = filename.replace('${gpsweek}', str(date.gpsWeek).zfill(4))
    filename = filename.replace('${gpswkday}', str(date.gpsWeekDay))
    filename = filename.replace('${year2d}', str(date.year)[2:])

    return filename


def main():
    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm',
                        help="List of networks/stations to process given in [net].[stnm] format or just [stnm] (separated by spaces; if [stnm] is not unique in the database, all stations with that name will be processed). Use keyword 'all' to process all stations in the database. If [net].all is given, all stations from network [net] will be processed. Alternatevily, a file with the station list can be provided.")

    parser.add_argument('-date', '--date_range', nargs='+', action=required_length(1,2), metavar='date_start|date_end', help="Date range to check given as [date_start] or [date_start] and [date_end]. Allowed formats are yyyy.doy or yyyy/mm/dd..")

    try:
        args = parser.parse_args()

        cnn = dbConnection.Cnn('gnss_data.cfg')
        Config = pyOptions.ReadOptions('gnss_data.cfg')

        if len(args.stnlist) == 1 and os.path.isfile(args.stnlist[0]):
            print ' >> Station list read from ' + args.stnlist[0]
            stnlist = [line.strip() for line in open(args.stnlist[0], 'r')]
            stnlist = [{'NetworkCode': item.split('.')[0], 'StationCode': item.split('.')[1]} for item in stnlist]
        else:
            stnlist = Utils.process_stnlist(cnn, args.stnlist)

        print ' >> Selected station list:'
        print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in stnlist])

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

        download_data(cnn, Config, stnlist, drange)

    except argparse.ArgumentTypeError as e:
        parser.error(str(e))


def download_data(cnn, Config, stnlist, drange):

    archive = pyArchiveStruct.RinexStruct(cnn)

    pbar = tqdm(desc='%-30s' % ' >> Downloading stations declared in data_source', total=len(drange)*len(stnlist), ncols=160)

    for date in [pyDate.Date(mjd=mdj) for mdj in drange]:

        for stn in stnlist:

            StationCode = stn['StationCode']
            NetworkCode = stn['NetworkCode']

            pbar.set_postfix(current='%s.%s %s' % (NetworkCode, StationCode, date.yyyyddd()))
            pbar.update()

            rinex = archive.get_rinex_record(NetworkCode=NetworkCode, StationCode=StationCode, ObservationYear=date.year,
                                             ObservationDOY=date.doy)

            if not rinex:
                download = True
            elif rinex and rinex[0]['Completion'] < 0.5:
                download = True
            else:
                download = False

            if download:
                rs = cnn.query('SELECT * FROM data_source WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' ORDER BY try_order' % (NetworkCode, StationCode))
                sources = rs.dictresult()

                for source in sources:

                    result = False

                    if source['protocol'].lower() == 'ftp':
                        result = download_ftp(source['fqdn'], source['username'], source['password'], source['path'], Config.repository_data_in, date)

                    elif source['protocol'].lower() == 'sftp':
                        result = download_sftp(source['fqdn'], source['username'], source['password'], source['path'], Config.repository_data_in, date)

                    elif source['protocol'].lower() == 'http':
                        result = download_http(source['fqdn'], source['username'], source['password'], source['path'], Config.repository_data_in, date)

                    else:
                        tqdm.write(' -- Unknown protocol %s for %s.%s' % (source['protocol'].lower(), NetworkCode, StationCode))

                    if result:
                        tqdm.write(' -- Successful download of %s.%s %s' % (NetworkCode, StationCode, date.yyyyddd()))
                        break
                    else:
                        tqdm.write(' -- Could not download %s.%s %s -> trying next source' % (NetworkCode, StationCode, date.yyyyddd()))
            else:
                tqdm.write(' -- File for %s.%s %s already in db' % (NetworkCode, StationCode, date.yyyyddd()))

    pbar.close()


def download_ftp(fqdn, username, password, path, destiny, date):

    try:
        # connect to ftp
        ftp = ftplib.FTP(fqdn, username, password)

        tqdm.write('   -- Connecting to ' + fqdn)

        destiny = os.path.join(destiny, fqdn)

        if not os.path.exists(destiny):
            os.makedirs(destiny)
            tqdm.write('   -- Creating dir ' + destiny)

        folder = os.path.dirname(replace_vars(path, date))
        filename = os.path.basename(replace_vars(path, date))

        tqdm.write('   -- Changing folder to ' + folder)

        ftp.cwd(folder)

        ftp_list = ftp.nlst()

        if filename in ftp_list:
            ftp.retrbinary("RETR " + filename, open(os.path.join(destiny, filename), 'wb').write)
        else:
            ftp.quit()
            return False

        ftp.quit()

        return True

    except Exception as e:
        # folder not present, skip
        tqdm.write('   -- ftp error: ' + str(e))
        return False


def download_sftp(fqdn, username, password, path, destiny, date):
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

        sftp = pysftp.Connection(fqdn, port=port, username=username, password=password, cnopts=cnopts)

        tqdm.write('   -- Connecting to ' + fqdn)

        destiny = os.path.join(destiny, fqdn)

        if not os.path.exists(destiny):
            os.makedirs(destiny)
            tqdm.write('   -- Creating dir ' + destiny)

        folder = os.path.dirname(replace_vars(path, date))
        filename = os.path.basename(replace_vars(path, date))

        tqdm.write('   -- Changing folder to ' + folder)

        sftp.cd(folder)

        ftp_list = sftp.listdir()

        if filename in ftp_list:
            sftp.get(filename,os.path.join(destiny, filename))
        else:
            sftp.close()
            return False

        sftp.close()

        return True

    except Exception as e:
        # folder not present, skip
        tqdm.write('   -- ftp error: ' + str(e))
        return False


def download_http(fqdn, username, password, folder, destiny, date):
    pass


if __name__ == '__main__':
    main()