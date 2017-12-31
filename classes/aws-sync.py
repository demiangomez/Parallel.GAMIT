"""
Project: Parallel.Archive
Date: 12/21/17 12:53 PM
Author: Demian D. Gomez

Script to synchronize AWS with OSU's archive database
Run aws-sync -h for help
"""

import dbConnection
import pyDate
import argparse
import pyOptions
import pyArchiveStruct
import pyPPPETM
import pyRinex
import pyStationInfo
import os

def main():
    parser = argparse.ArgumentParser(description='Script to synchronize AWS with OSU\'s archive database')

    parser.add_argument('date', type=str, nargs=1, help="Check the sync state for this given date. Format can be fyear or yyyy,ddd.")
    parser.add_argument('-mark', '--mark_uploaded', type=str, help="Pass net.stnm to mark this files as transferred to the AWS")
    parser.add_argument('-pull', '--pull_rinex', action='store_true', help="Get all the unsynchronized RINEX files in the local dir")

    args = parser.parse_args()

    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn('gnss_data.cfg')

    dd = args.date[0]

    if ',' in dd:
        date = pyDate.Date(year=int(dd.split(',')[0]), doy=int(dd.split(',')[1]))
    else:
        date = pyDate.Date(fyear=float(dd))

    # get the list of rinex files not transferred to the AWS
    rs = cnn.query('SELECT rinex_proc.* FROM rinex_proc '
                   'LEFT JOIN aws_sync ON '
                   'rinex_proc."NetworkCode" = aws_sync."NetworkCode" AND '
                   'rinex_proc."StationCode" = aws_sync."StationCode" AND '
                   'rinex_proc."ObservationYear" = aws_sync."Year"    AND '
                   'rinex_proc."ObservationDOY" = aws_sync."DOY"          '
                   'WHERE "ObservationYear" = %i AND "ObservationDOY" = %i AND '
                   'aws_sync."NetworkCode" IS NULL' % (date.year, date.doy))

    rinex = rs.dictresult()

    for rnx in rinex:
        print '%s.%s' % (rnx['NetworkCode'], rnx['StationCode'])

        if args.pull_rinex:
            metafile = date.yyyyddd().replace(' ', '-')

            # write the station.info
            try:
                stninfo = pyStationInfo.StationInfo(cnn, rnx['NetworkCode'], rnx['StationCode'], date)

                with open('./' + metafile + '.info', mode='a') as fid:
                    fid.write(stninfo.return_stninfo(stninfo.currentrecord) + '\n')

            except pyStationInfo.pyStationInfoException:
                # if no metadata, warn user and continue
                print '  -> %s.%s has no metadata available for this date, but a RINEX exists!' % (rnx['NetworkCode'], rnx['StationCode'])
                continue

            Archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct
            ArchiveFile = Archive.build_rinex_path(rnx['NetworkCode'], rnx['StationCode'], date.year, date.doy)
            ArchiveFile = os.path.join(Config.archive_path, ArchiveFile)

            # check for a station alias in the alias table
            alias = cnn.query('SELECT * FROM stationalias WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (rnx['NetworkCode'], rnx['StationCode']))
            sa = alias.dictresult()
            if len(sa) > 0:
                StationAlias = sa[0]['StationAlias']
            else:
                StationAlias = rnx['StationCode']

            # create the crinez filename
            filename = StationAlias + date.ddd() + '0.' + date.yyyy()[2:4] + 'd.Z'

            # local directory as destiny for the files
            pwd_rinex = './'

            etm = pyPPPETM.ETM(cnn, rnx['NetworkCode'], rnx['StationCode'])

            Apr, sigmas, Window, source = etm.get_xyz_s(date.year, date.doy)

            with pyRinex.ReadRinex(rnx['NetworkCode'], rnx['StationCode'], ArchiveFile, False) as Rinex:  # type: pyRinex.ReadRinex

                if Rinex.multiday:
                    # find the rinex that corresponds to the session being processed
                    for Rnx in Rinex.multiday_rnx_list:
                        if Rnx.date == date:
                            Rnx.normalize_header(stninfo)
                            Rnx.rename(filename)

                            if Window is not None:
                                window_rinex(Rnx, Window)
                            # before creating local copy, decimate file
                            Rnx.decimate(30)
                            Rnx.compress_local_copyto(pwd_rinex)
                            break
                else:
                    Rinex.normalize_header(stninfo)
                    Rinex.rename(filename)

                    if Window is not None:
                        window_rinex(Rinex, Window)
                    # before creating local copy, decimate file
                    Rinex.decimate(30)
                    Rinex.compress_local_copyto(pwd_rinex)

            # write the APR and sigmas
            with open('./' + metafile + '.apr', mode='a') as fid:
                fid.write('%s.%s %s %12.3f %12.3f %12.3f %5.3f %5.3f %5.3f\n'
                          % (rnx['NetworkCode'], rnx['StationCode'], StationAlias,
                             Apr[0,0], Apr[1,0], Apr[2,0],
                             sigmas[0,0], sigmas[1,0], sigmas[2,0]))


def window_rinex(Rinex, window):

    # windows the data:
    # check which side of the earthquake yields more data: window before or after the earthquake
    if (window.datetime().hour + window.datetime().minute/60.0) < 12:
        Rinex.window_data(start=window.datetime())
    else:
        Rinex.window_data(end=window.datetime())

if __name__ == '__main__':
    main()