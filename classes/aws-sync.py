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
import pyETM
import pyRinex
import pyStationInfo
import os
import numpy
import pyJobServer
from tqdm import tqdm
import traceback
import platform
import Utils
from datetime import datetime
import shutil
import string
import random


class callback_class():
    def __init__(self, pbar):
        self.apr = None
        self.stninfo = None
        self.log = None
        self.pbar = pbar

    def process_callback(self, args):
        self.apr = args[0]
        self.stninfo = args[1]
        self.log = args[2]
        self.pbar.update(1)


def rinex_task(NetworkCode, StationCode, date, ObservationFYear):

    from pyRunWithRetry import RunCommandWithRetryExeception

    etm_err = ''

    # local directory as destiny for the CRINEZ files
    pwd_rinex = '/media/leleiona/aws-files/' + date.yyyy() + '/' + date.ddd()

    stop_no_aprs = False

    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn('gnss_data.cfg')

    # create Archive object
    Archive = pyArchiveStruct.RinexStruct(cnn)  # type: pyArchiveStruct.RinexStruct

    ArchiveFile = Archive.build_rinex_path(NetworkCode, StationCode, date.year, date.doy)
    ArchiveFile = os.path.join(Config.archive_path, ArchiveFile)

    # check for a station alias in the alias table
    alias = cnn.query('SELECT * FROM stationalias WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

    sa = alias.dictresult()

    if len(sa) > 0:
        StationAlias = sa[0]['StationAlias']
    else:
        StationAlias = StationCode

    # create the crinez filename
    filename = StationAlias + date.ddd() + '0.' + date.yyyy()[2:4] + 'd.Z'

    try:
        # create the ETM object
        etm = pyETM.PPPETM(cnn, NetworkCode, StationCode)

        # get APRs and sigmas (only in NEU)
        Apr, sigmas, Window, source = etm.get_xyz_s(date.year, date.doy)

        del etm

    except pyETM.pyETMException as e:
        # no PPP solutions available! MUST have aprs in the last run, try that
        stop_no_aprs = True
        Window = None
        source = ''
        etm_err = str(e)

    except Exception:

        return (None, None, traceback.format_exc() + ' processing ' + NetworkCode + '.' + StationCode + ' using node ' + platform.node() + '\n')

    # find this station-day in the lastest global run APRs
    apr_tbl = cnn.query('SELECT * FROM apr_coords WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                        'AND "Year" = %i AND "DOY" = %i' %
                        (NetworkCode, StationCode, date.year, date.doy))

    apr = apr_tbl.dictresult()

    if len(apr) > 0:
        # APRs exist for this station-day
        # replace PPP ETM with Mike's APRs
        Apr = numpy.array(([float(apr[0]['x'])], [float(apr[0]['y'])], [float(apr[0]['z'])]))
        sigmas = numpy.array(([float(apr[0]['sn'])], [float(apr[0]['se'])], [float(apr[0]['su'])]))
        source = apr[0]['ReferenceFrame'] + ' APRs'

    elif len(apr) == 0 and stop_no_aprs:

        return (None, None, '%s.%s has no PPP solutions and no APRs from last global run for %s! '
                            'Specific error from pyETM.PPPETM (if available) was: %s'
                % (NetworkCode, StationCode, date.yyyyddd(), etm_err))

    # convert sigmas to XYZ
    stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))
    stn = stn.dictresult()
    sigmas_xyz = sigmas_neu2xyz(stn[0]['lat'], stn[0]['lon'], sigmas)

    # write the station.info
    # if no station info comes back for this date, program will print a message and continue with next
    try:

        # Use the argument 'ObservationFYear' to get the exact RINEX session fyear without opening the file
        rnx_date = pyDate.Date(fyear=float(ObservationFYear))
        stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode, rnx_date)

    except pyStationInfo.pyStationInfoException:
        # if no metadata, warn user and continue
        return (None, None, '%s.%s has no metadata available for this date, but a RINEX exists!' % (NetworkCode, StationCode))

    # check if RINEX file needs to be synced or not.
    aws_sync = cnn.query('SELECT * FROM aws_sync WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' '
                        'AND "Year" = %i AND "DOY" = %i' %
                        (NetworkCode, StationCode, date.year, date.doy)).dictresult()

    cnn.close()

    if len(aws_sync) == 0:

        # only copy RINEX if not synced!
        # open the RINEX file in the Archive
        try:
            with pyRinex.ReadRinex(NetworkCode, StationCode, ArchiveFile, False) as Rinex:  # type: pyRinex.ReadRinex

                Rnx = None

                if Rinex.multiday:
                    # find the rinex that corresponds to the session being processed, if multiday
                    for rinex in Rinex.multiday_rnx_list:
                        if rinex.date == date:
                            Rnx = rinex
                            break

                    if Rnx is None:
                        return (None, None, '%s.%s was a multiday file and date %8.3f could not be found!' % (NetworkCode, StationCode, date.fyear))
                else:
                    # if Rinex is not multiday
                    Rnx = Rinex

                    Rnx.purge_comments()
                    Rnx.normalize_header(stninfo)
                    Rnx.rename(filename)

                    if Window is not None:
                        window_rinex(Rnx, Window)
                        source += ' windowed from/to ' + Window.datetime().strftime('%Y-%M-%d %H:%M:%S')
                    # before creating local copy, decimate file
                    Rnx.decimate(30)
                    Rnx.compress_local_copyto(pwd_rinex)

        except (pyRinex.pyRinexException, RunCommandWithRetryExeception):
            # new behavior: if error occurs while generating RINEX, then copy raw file from the archive
            try:
                shutil.copy(ArchiveFile, os.path.join(pwd_rinex, filename))

            except Exception:
                return (None, None,
                        traceback.format_exc() + ' processing ' + NetworkCode + '.' + StationCode + ' using node ' + platform.node() + '\n')

        except Exception:
            return (None, None, traceback.format_exc() + ' processing ' + NetworkCode + '.' + StationCode + ' using node ' + platform.node() + '\n')

    # everything ok, return information
    APR = '%s.%s %s %12.3f %12.3f %12.3f %5.3f %5.3f %5.3f %5.3f %5.3f %5.3f %s' % (NetworkCode, StationCode, StationAlias,
             Apr[0,0], Apr[1,0], Apr[2,0], sigmas_xyz[0,0], sigmas_xyz[1,0], sigmas_xyz[2,0],
             sigmas[1,0], sigmas[0,0], sigmas[2,0], source.replace(' ', '_'))

    return (APR, stninfo.return_stninfo().replace(StationCode.upper(), StationAlias.upper()), None)


def sigmas_neu2xyz(lat, lon, sigmas):
    # function to convert a given sigma from NEU to XYZ
    # convert sigmas to XYZ
    R = Utils.rotlg2ct(float(lat), float(lon))
    sd = numpy.diagflat(sigmas)
    sxyz = numpy.dot(numpy.dot(R[:, :, 0], sd), R[:, :, 0].transpose())
    oxyz = numpy.diag(sxyz)

    return numpy.row_stack((oxyz[0], oxyz[1], oxyz[2]))


def main():
    parser = argparse.ArgumentParser(description='Script to synchronize AWS with OSU\'s archive database')

    parser.add_argument('date', type=str, nargs=1, help="Check the sync state for this given date. Format can be fyear or yyyy_ddd.")
    parser.add_argument('-mark', '--mark_uploaded', nargs='+', type=str, help="Pass net.stnm to mark these files as transferred to the AWS", metavar='{net.stnm}')
    parser.add_argument('-pull', '--pull_rinex', action='store_true', help="Get all the unsynchronized RINEX files in the local dir")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    Config = pyOptions.ReadOptions("gnss_data.cfg")  # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn('gnss_data.cfg')

    # before attempting anything, check aliases!!
    print ' >> Checking GAMIT aliases'
    check_aliases(cnn)

    # initialize the PP job server
    if not args.noparallel:
        JobServer = pyJobServer.JobServer(Config, 1500)  # type: pyJobServer.JobServer
    else:
        JobServer = None
        Config.run_parallel = False

    dd = args.date[0]

    if '_' in dd:
        date = pyDate.Date(year=int(dd.split('_')[0]), doy=int(dd.split('_')[1]))
    elif dd == 'all':
        # run all dates (1994 to 2018)
        ts = range(pyDate.Date(year=1994, doy=1).mjd, pyDate.Date(year=2018, doy=87).mjd, 1)
        ts = [pyDate.Date(mjd=tts) for tts in ts]
        for date in ts:
            print ' >> Processing ' + str(date)
            pull_rinex(cnn, date, Config, JobServer)

        return
    else:
        date = pyDate.Date(fyear=float(dd))

    if args.pull_rinex:
        pull_rinex(cnn, date, Config, JobServer)

    if args.mark_uploaded is not None:
        print 'Processing %i for day %s' % (len(args.mark_uploaded), date.yyyyddd())
        # mark the list of stations as transferred to the AWS
        mark_uploaded(cnn, date, args.mark_uploaded)


def mark_uploaded(cnn, date, stns):

    for stn in stns:
        NetworkCode = stn.split('.')[0]
        StationCode = stn.split('.')[1].split(':')[0]
        StationAlias = stn.split('.')[1].split(':')[1]

        # check if valid station
        rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))
        if rs.ntuples() == 0:
            print ' %s.%s is not an existing station' % (NetworkCode, StationCode)
            continue

        # check if station already marked
        rs = cnn.query('SELECT * FROM aws_sync WHERE "NetworkCode" = \'%s\' AND '
                       '"StationCode" =  \'%s\' AND '
                       '"Year" = %i AND "DOY" = %i ' % (NetworkCode, StationCode, date.year, date.doy))

        if rs.ntuples() == 0:
            # print ' Marking %s.%s as uploaded' % (NetworkCode, StationCode)

            cnn.query('INSERT INTO aws_sync ("NetworkCode", "StationCode", "StationAlias", "Year", "DOY", sync_date) '
                      'VALUES (\'%s\', \'%s\', \'%s\', %i, %i, \'%s\')'
                      % (NetworkCode, StationCode, StationAlias, date.year, date.doy,
                         datetime.now().strftime('%Y-%m-%d %H:%m:%S')))
        else:
            print ' %s.%s was already marked' % (NetworkCode, StationCode)


def id_generator(size=4, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def pull_rinex(cnn, date, Config, JobServer):


    # before starting the sync, determine if there were any station code changes that will require file deletions in AWS
    # Join aws_sync with stations. If an entry in aws_sync has has no record in stations, station was renamed and needs
    # to be deleted. It will be resent in this run.
    rs = cnn.query('SELECT a."NetworkCode", a."StationCode", a."StationAlias" FROM aws_sync as a '
                   'LEFT JOIN stations as s on '
                   'a."NetworkCode" = s."NetworkCode" and '
                   'a."StationCode" = s."StationCode" '
                   'WHERE "Year" = %i AND "DOY" = %i AND s."StationCode" IS NULL' % (date.year, date.doy))

    deletes = rs.dictresult()

    for stn in deletes:
        # produce a single file with the deletions that need to occur in the AWS
        with open('file_ops.log', mode='a') as fid:
            fid.write('rm %s/%s* # %s.%s not found in stations table with net.stn code declared in aws_sync\n'
                      % (date.yyyyddd().replace(' ', '/'), stn['StationAlias'], stn['NetworkCode'], stn['StationCode']))

    # delete the records from aws_sync

    # Join aws_sync with stationalias (stationalias is FK-ed to stations).
    # If an entry in aws_sync that has StationCode <> StationAlias has no record in stationalias OR
    # the stationalias declared is different than the station alias in the aws_sync, delete from AWS.
    # will be resent in this batch
    rs = cnn.query('SELECT a."NetworkCode", a."StationCode", a."StationAlias" FROM aws_sync as a '
                   'LEFT JOIN stationalias as sa on '
                   'a."NetworkCode" = sa."NetworkCode" and '
                   'a."StationCode" = sa."StationCode" '
                   'WHERE "Year" = %i AND "DOY" = %i AND '
                   'a."StationAlias" <> sa."StationAlias" OR '
                   '(sa."StationAlias" IS NULL AND a."StationCode" <> a."StationAlias")' % (date.year, date.doy))

    deletes = rs.dictresult()

    for stn in deletes:
        # produce a single file with the deletions that need to occur in the AWS
        with open('file_ops.log', mode='a') as fid:
            fid.write('rm %s/%s* # alias declared in aws_sync for %s.%s does not match alias in stationalias table\n'
                      % (date.yyyyddd().replace(' ', '/'), stn['StationAlias'], stn['NetworkCode'], stn['StationCode']))

    # delete the records from aws_sync

    # check the individual files for this day. All files reported as uploaded should have a match in the rinex_proc
    # table, otherwise this could be a station split or deletion. If that's the case, order their deletion from the AWS
    rs = cnn.query('SELECT a."NetworkCode", a."StationCode", a."StationAlias" FROM aws_sync as a '
                   'LEFT JOIN rinex_proc as rx on '
                   'a."NetworkCode" = rx."NetworkCode" and '
                   'a."StationCode" = rx."StationCode" and '
                   'a."Year"        = rx."ObservationYear" and '
                   'a."DOY"         = rx."ObservationDOY" '
                   'WHERE "Year" = %i AND "DOY" = %i AND '
                   'rx."StationCode" IS NULL ' % (date.year, date.doy))

    deletes = rs.dictresult()

    for stn in deletes:
        # produce a single file with the deletions that need to occur in the AWS
        with open('file_ops.log', mode='a') as fid:
            fid.write('rm %s/%s* # rinex file for %s.%s could not be found in the rinex_proc table\n'
                      % (date.yyyyddd().replace(' ', '/'), stn['StationAlias'], stn['NetworkCode'], stn['StationCode']))

    # delete the records from aws_sync

    ####################################################################################################################
    # continue with sync of files
    ####################################################################################################################

    # behavior requested by Abel: ALWAYS output the metadata but don't output a RINEX if already synced.
    rs = cnn.query('SELECT rinex_proc.* FROM rinex_proc '
                   'WHERE "ObservationYear" = %i AND "ObservationDOY" = %i AND "Completion" >= 0.3'
                   % (date.year, date.doy))

    rinex = rs.dictresult()

    callback = []
    pbar = tqdm(total=len(rinex), ncols=80)

    metafile = date.yyyy() + '/' + date.ddd() + '/' + date.yyyyddd().replace(' ', '-')

    if not os.path.isdir('./' + date.yyyy() + '/' + date.ddd()):
        os.makedirs('./' + date.yyyy() + '/' + date.ddd())

    # following Abel's request, make a subdir for the files
    if not os.path.isdir('/media/leleiona/aws-files/' + date.yyyy() + '/' + date.ddd()):
        os.makedirs('/media/leleiona/aws-files/' + date.yyyy() + '/' + date.ddd())

    # write the header to the .info file
    with open('./' + metafile + '.info', mode='w') as fid:
        fid.write('*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  Ant N    Ant E    '
                  'Receiver Type         Vers                  SwVer  Receiver SN           Antenna Type     Dome   '
                  'Antenna SN          \n')

    for rnx in rinex:
        if Config.run_parallel:
            JobServer.SubmitJob(rinex_task, (rnx['NetworkCode'], rnx['StationCode'], date, rnx['ObservationFYear']),
                                (window_rinex, sigmas_neu2xyz),
                                ('dbConnection', 'pyETM', 'pyDate', 'pyRinex', 'pyStationInfo',
                                                  'pyOptions', 'pyArchiveStruct', 'os', 'numpy',
                                                  'traceback', 'platform', 'Utils', 'shutil'), callback,
                                callback_class(pbar), 'process_callback')

            if JobServer.process_callback:
                # handle any output messages during this batch
                callback = output_handle(callback, metafile)
                JobServer.process_callback = False
        else:
            callback.append(callback_class(pbar))
            callback[0].process_callback(rinex_task(rnx['NetworkCode'], rnx['StationCode'], date, rnx['ObservationFYear']))
            callback = output_handle(callback, metafile)

    if Config.run_parallel:
        tqdm.write(' >> waiting for jobs to finish...')
        JobServer.job_server.wait()

    # handle any output messages during this batch
    output_handle(callback, metafile)
    pbar.close()
    print 'Done, chau!'


def check_aliases(cnn):
    # check that all stations have an alias and that there is no collision between station codes and aliases
    rs = cnn.query('SELECT s."StationCode", count(s."StationCode") AS stnc FROM stations AS s '
                   'LEFT JOIN stationalias AS sa ON '
                   's."NetworkCode" = sa."NetworkCode" AND '
                   's."StationCode" = sa."StationCode" '
                   'WHERE sa."StationAlias" IS NULL and s."NetworkCode" not like \'?%\' '
                   'GROUP BY s."StationCode" '
                   'ORDER BY stnc DESC')

    aliases = rs.dictresult()

    for alias in aliases:

        if alias['stnc'] > 1:
            # one or more stations need an alias!
            stna = cnn.query('SELECT s."NetworkCode", s."StationCode" FROM stations as s '
                             'LEFT JOIN stationalias AS sa ON '
                             's."NetworkCode" = sa."NetworkCode" AND '
                             's."StationCode" = sa."StationCode" '
                             'WHERE sa."StationAlias" IS NULL '
                             'AND s."StationCode" = \'%s\' and s."NetworkCode" not like \'?%%\''
                             % alias['StationCode']).dictresult()

            for stn in stna[0:-1]:
                # get a random alias for this station
                while True:
                    new_alias = id_generator()
                    # check it does not collide with any other stationalias or code
                    chk = cnn.query('SELECT "StationCode" FROM stations WHERE "StationCode" = \'%s\' UNION '
                                    'SELECT "StationAlias" as "StationCode" FROM stationalias '
                                    'WHERE "StationAlias" = \'%s\'' % (new_alias, new_alias))

                    if len(chk.getresult()) == 0:
                        # no collision, insert
                        try:
                            cnn.insert('stationalias', NetworkCode=stn['NetworkCode'], StationCode=stn['StationCode'],
                                       StationAlias=new_alias)

                            print ' -- alias created for %s.%s -> %s' \
                                  % (stn['NetworkCode'], stn['StationCode'], new_alias)

                        except dbConnection.dbErrInsert:
                            print ' -- station %s.%s already has an alias' % (stn['NetworkCode'], stn['StationCode'])

                        break


def output_handle(callback, metafile):

    for obj in callback:
        # write the APR and sigmas
        # writen in ENU not NEU, as specified by Abel
        if obj.apr is not None:
            with open('./' + metafile + '.apr', mode='a') as fid:
                fid.write(obj.apr + '\n')

        if obj.stninfo is not None:
            with open('./' + metafile + '.info', mode='a') as fid:
                fid.write(obj.stninfo + '\n')

        # write a log line for debugging
        if obj.log is not None:
            with open('./' + metafile + '.log', mode='a') as fid:
                fid.write(obj.log + '\n')

    return []


def window_rinex(Rinex, window):

    # windows the data:
    # check which side of the earthquake yields more data: window before or after the earthquake
    if (window.datetime().hour + window.datetime().minute/60.0) < 12:
        Rinex.window_data(start=window.datetime())
    else:
        Rinex.window_data(end=window.datetime())


if __name__ == '__main__':
    main()