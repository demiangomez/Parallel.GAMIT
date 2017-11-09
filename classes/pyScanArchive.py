"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Main routines to load the RINEX files to the database, load station information, run PPP on the archive files and obtain
the OTL coefficients

usage: pyScanArchive.py [-h] [-rinex] [-otl]
                        [-stninfo [argument [argument ...]]]
                        [-ppp [argument [argument ...]]]
                        [-rehash [argument [argument ...]]] [-np]
                        all|net.stnm [all|net.stnm ...]

Archive operations Main Program

positional arguments:
  all|net.stnm          List of networks/stations to process given in
                        [net].[stnm] format or just [stnm] (separated by
                        spaces; if [stnm] is not unique in the database, all
                        stations with that name will be processed). Use
                        keyword 'all' to process all stations in the database.
                        If [net].all is given, all stations from network [net]
                        will be processed. Alternatevily, a file with the
                        station list can be provided.

optional arguments:
  -h, --help            show this help message and exit
  -rinex, --rinex       Scan the current archive for RINEX files (d.Z).
  -otl, --ocean_loading
                        Calculate ocean loading coefficients.
  -stninfo [argument [argument ...]], --station_info [argument [argument ...]]
                        Insert station information to the database. If no
                        arguments are given, then scan the archive for station
                        info files and use their location (folder) to
                        determine the network to use during insertion. Only
                        stations in the station list will be processed. If a
                        filename is provided, then scan that file only, in
                        which case a second argument specifies the network to
                        use during insertion. Eg: -stninfo ~/station.info arg.
                        In cases where multiple networks are being processed,
                        the network argument will be used to desambiguate
                        station code conflicts. Eg: pyScanArchive all -stninfo
                        ~/station.info arg -> if a station named igm1 exists
                        in networks 'igs' and 'arg', only 'arg.igm1' will get
                        the station information insert. Use keyword 'stdin' to
                        read the station information data from the pipeline.
  -ppp [argument [argument ...]], --ppp [argument [argument ...]]
                        Run ppp on the rinex files in the database. Append
                        [date_start] and (optionally) [date_end] to limit the
                        range of the processing. Allowed formats are yyyy.doy
                        or yyyy/mm/dd. Append keyword 'hash' to the end to
                        check the PPP hash values against the station
                        information records. If hash doesn't match,
                        recalculate the PPP solutions.
  -rehash [argument [argument ...]], --rehash [argument [argument ...]]
                        Check PPP hash against station information hash.
                        Rehash PPP solutions to match the station information
                        hash without recalculating the PPP solution.
                        Optionally append [date_start] and (optionally)
                        [date_end] to limit the rehashing time window. Allowed
                        formats are yyyy.doy or yyyy/mm/dd.
  -np, --noparallel     Execute command without parallelization.
"""

import pyArchiveStruct
import dbConnection
import pyDate
import pyRinex
import traceback
import datetime
import os
import pyOTL
import pyStationInfo
import sys
import pySp3
import pyPPP
from tqdm import tqdm
import argparse
import numpy
import pyOptions
import Utils
import platform
import pyJobServer
from Utils import print_columns
from Utils import process_date
from Utils import ecef2lla
import pyEvents
import scandir

class callback_scan_class():
    def __init__(self, pbar):
        self.errors = None
        self.pbar = pbar

    def callbackfunc(self, args):
        msg = args
        self.errors = msg

class callback_class():
    def __init__(self, pbar):
        self.errors = None
        self.pbar = pbar

    def callbackfunc(self, args):
        msg = args
        self.errors = msg
        self.pbar.update(1)


def verify_rinex_date_multiday(cnn, date, rinexinfo, Config):
    # function to verify if rinex is multiday or if the file is from the date it was stored in the archive
    # returns true if parent process can continue with insert
    # returns false if file had to be moved from the archive (date != rinex.date or multiday file)

    # check if rinex is a multiday file (rinex with more than one day of observations)
    if rinexinfo.multiday:

        # move all the files to the repository, delete the crinex from the archive, log the event
        rnxlist = []
        for rnx in rinexinfo.multiday_rnx_list:
            rnxlist.append(rnx.rinex)
            # some other file, move it to the repository
            retry_folder = os.path.join(Config.repository_data_in_retry, 'multidays_found/' + rnx.date.yyyy() + '/' + rnx.date.ddd())
            rnx.compress_local_copyto(retry_folder)

        # if the file corresponding to this session is found, assign its object to rinexinfo
        event = pyEvents.Event(
            Description='%s was a multi-day rinex file. The following rinex files where generated and moved to the repository/data_in_retry: %s.' % (
                rinexinfo.origin_file, ','.join(rnxlist)),
            NetworkCode=rinexinfo.NetworkCode,
            EventType='warn',
            StationCode=rinexinfo.StationCode,
            Year=int(rinexinfo.date.year),
            DOY=int(rinexinfo.date.doy))

        cnn.insert_event(event)

        # remove crinex from archive
        os.remove(rinexinfo.origin_file)

        return False

    # compare the date of the rinex with the date in the archive
    if not date == rinexinfo.date:
        # move the file out of the archive because it's in the wrong spot (wrong folder, wrong name, etc)
        # let pyArchiveService fix the issue
        retry_folder = os.path.join(Config.repository_data_in_retry, 'wrong_date_found/' +  date.yyyy() + '/' + date.ddd())
        # move the crinex out of the archive
        rinexinfo.move_origin_file(retry_folder)

        event = pyEvents.Event(
            Description='The date in the archive for ' + rinexinfo.rinex + ' (' + date.yyyyddd() + ') does not agree with the mean session date (' +
                rinexinfo.date.yyyyddd() + '). The file was moved to the repository/data_in_retry.',
            NetworkCode=rinexinfo.NetworkCode,
            EventType='warn',
            StationCode=rinexinfo.StationCode,
            Year=int(rinexinfo.date.year),
            DOY=int(rinexinfo.date.doy))

        cnn.insert_event(event)

        return False

    return True


def try_insert(NetworkCode, StationCode, year, doy, rinex):

    try:
        # try to open a connection to the database
        cnn = dbConnection.Cnn("gnss_data.cfg")
        Config = pyOptions.ReadOptions("gnss_data.cfg")

        # get the rejection directory ready
        data_reject = os.path.join(Config.repository_data_reject, 'bad_rinex/%i/%03i' % (year, doy))

    except Exception:
        return traceback.format_exc() + ' processing rinex: ' + rinex + ' (' + NetworkCode + '.' + StationCode + ' ' + str(year) + ' ' + str(doy) + ') using node ' + platform.node()

    try:
        # get the rinex file name
        filename = os.path.basename(rinex).replace('d.Z', 'o')

        # build the archive level sql string
        # the file has not to exist in the RINEX table (check done using filename)
        rs = cnn.query(
            'SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Filename" = \'%s\''
            % (NetworkCode, StationCode, filename))

        if rs.ntuples() == 0:
            # no record found, possible new rinex file for this day
            rinexinfo = pyRinex.ReadRinex(NetworkCode, StationCode, rinex)

            date = pyDate.Date(year=year, doy=doy)

            # verify that the rinex is from this date and that is not a multiday file
            if verify_rinex_date_multiday(cnn, date, rinexinfo, Config):
                try:
                    # create the insert statement
                    cnn.insert('rinex', rinexinfo.record)

                    event = pyEvents.Event(
                        Description='Archived crinex file %s added to the database.' % (rinex),
                        EventType='info',
                        StationCode=StationCode,
                        NetworkCode=NetworkCode,
                        Year=date.year,
                        DOY=date.doy)
                    cnn.insert_event(event)

                except dbConnection.dbErrInsert:
                    # insert duplicate values: a rinex file with different name but same interval and completion %
                    # discard file
                    cnn.begin_transac()

                    event = pyEvents.Event(
                        Description='Crinex file %s was removed from the archive (and not added to db) because '
                                    'it matched the interval and completion of an already existing file.' % (rinex),
                        EventType='info',
                        StationCode=StationCode,
                        NetworkCode=NetworkCode,
                        Year=date.year,
                        DOY=date.doy)

                    cnn.insert_event(event)

                    rinexinfo.move_origin_file(os.path.join(Config.repository_data_reject, 'duplicate_insert/%i/%03i' % (year, doy)))

                    cnn.commit_transac()

    except (pyRinex.pyRinexExceptionBadFile, pyRinex.pyRinexExceptionSingleEpoch) as e:

        try:
            filename = Utils.move(rinex, os.path.join(data_reject, os.path.basename(rinex)))
        except OSError:
            # permission denied: could not move file out of the archive->return error in an orderly fashion
            return traceback.format_exc() + ' processing rinex: ' + rinex + ' (' + NetworkCode + '.' + StationCode + ' ' + str(year) + ' ' + str(doy) + ') using node ' + platform.node()

        e.event['Description'] = 'During ' + os.path.basename(rinex) + ', file moved to %s' % (filename) + ': ' + e.event['Description']
        e.event['StationCode'] = StationCode
        e.event['NetworkCode'] = NetworkCode
        e.event['Year'] = year
        e.event['DOY'] = doy

        cnn.insert_event(e.event)
        return

    except pyRinex.pyRinexException as e:

        if cnn.active_transaction:
            cnn.rollback_transac()

        e.event['Description'] = e.event['Description'] + ' during ' + rinex
        e.event['StationCode'] = StationCode
        e.event['NetworkCode'] = NetworkCode
        e.event['Year'] = year
        e.event['DOY'] = doy

        cnn.insert_event(e.event)
        return

    except Exception:

        if cnn.active_transaction:
            cnn.rollback_transac()

        return traceback.format_exc() + ' processing rinex: ' + rinex + ' (' + NetworkCode + '.' + StationCode + ' ' + str(year) + ' ' + str(doy) + ') using node ' + platform.node()


def obtain_otl(NetworkCode, StationCode):

    errors = ''
    outmsg = []
    x = []
    y = []
    z = []

    try:
        cnn = dbConnection.Cnn("gnss_data.cfg")
        Config = pyOptions.ReadOptions("gnss_data.cfg")

        pyArchive = pyArchiveStruct.RinexStruct(cnn)

        # assumes that the files in the db are correct. We take 10 records from the time span (evenly spaced)
        count = cnn.query('SELECT count(*) as cc FROM rinex_proc as r WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

        count = count.dictresult()

        #print '\nsuma total: ' + str(count[0]['cc'])

        if count[0]['cc'] >= 10:
            #stn = cnn.query('SELECT * FROM (SELECT row_number() OVER() as rnum, r.* FROM rinex_proc as r WHERE "NetworkCode" = \'%s\' '
            #                'AND "StationCode" = \'%s\' ORDER BY "ObservationSTime") AS rr '
            #                'WHERE (rnum %% ((SELECT count(*) FROM rinex_proc as r WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\')/10)) = 0' % (
            #    NetworkCode, StationCode, NetworkCode, StationCode))

            stn = cnn.query('SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY "NetworkCode", "StationCode") as rnum, '
                            'count(*) OVER (PARTITION BY "NetworkCode", "StationCode") as cc FROM rinex_proc) as rinex '
                            'WHERE rinex."NetworkCode" = \'%s\' AND rinex."StationCode" = \'%s\' '
                            'AND rinex.rnum %% (rinex.cc/10) = 0 ORDER BY rinex."ObservationSTime"' % (NetworkCode, StationCode))

            #print 'select 10>'
        elif count[0]['cc'] < 10:
            stn = cnn.query(
                'SELECT * FROM (SELECT row_number() OVER() as rnum, r.* FROM rinex_proc as r WHERE "NetworkCode" = \'%s\' '
                'AND "StationCode" = \'%s\' ORDER BY "ObservationSTime") AS rr ' % (NetworkCode, StationCode))
            #print 'select all'
        else:
            return 'Station ' + NetworkCode + '.' + StationCode + ' had no rinex files in the archive. Please check the database for problems.'

        tblrinex = stn.dictresult()

        for dbRinex in tblrinex:
            # obtain the path to the crinex
            file = pyArchive.build_rinex_path(NetworkCode, StationCode, dbRinex['ObservationYear'],
                                              dbRinex['ObservationDOY'])
            # read the crinex
            try:
                Rinex = pyRinex.ReadRinex(dbRinex['NetworkCode'], dbRinex['StationCode'],
                                          os.path.join(Config.archive_path, file))

                # run ppp without otl and met and in non-strict mode
                ppp = pyPPP.RunPPP(Rinex, '', Config.options, Config.sp3types, Config.sp3altrn, Rinex.antOffset, strict=False, apply_met=False, clock_interpolation=True)

                ppp.exec_ppp()

                x.append(ppp.x)
                y.append(ppp.y)
                z.append(ppp.z)
                errors = errors + 'PPP -> ' + NetworkCode + '.' + StationCode + ': ' + str(ppp.x) + ' ' + str(ppp.y) + ' ' + str(ppp.z) + '\n'

            except (IOError, pyRinex.pyRinexException, pyRinex.pyRinexExceptionBadFile, pySp3.pySp3Exception, pyPPP.pyRunPPPException) as e:
                # problem loading this file, try another one
                errors = errors + str(e) + '\n'
                continue
            except Exception:
                return traceback.format_exc() + ' processing: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node()

        # average the x y z values
        if len(x) > 0:
            #print 'about to average'
            if len(x) > 1:
                x = numpy.array(x)
                y = numpy.array(y)
                z = numpy.array(z)

                x = numpy.mean(x[abs(x - numpy.mean(x)) < 2 * numpy.std(x)])
                y = numpy.mean(y[abs(y - numpy.mean(y)) < 2 * numpy.std(y)])
                z = numpy.mean(z[abs(z - numpy.mean(z)) < 2 * numpy.std(z)])
            else:
                x = x[0]
                y = y[0]
                z = z[0]

            lat,lon,h = ecef2lla([x,y,z])

            # calculate the otl parameters if the auto_coord returned a valid position
            errors = errors + 'Mean -> ' + NetworkCode + '.' + StationCode + ': ' + str(x) + ' ' + str(y) + ' ' + str(z) + '\n'

            otl = pyOTL.OceanLoading(StationCode, Config.options['grdtab'], Config.options['otlgrid'])
            coeff = otl.calculate_otl_coeff(x=x, y=y, z=z)

            # update record in the database
            cnn.query('UPDATE stations SET "auto_x" = %.3f, "auto_y" = %.3f, "auto_z" = %.3f, "lat" = %.8f, "lon" = %.8f, "height" = %.3f, "Harpos_coeff_otl" = \'%s\' WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (x, y, z, lat[0], lon[0], h[0], coeff, NetworkCode, StationCode))

        else:
            outmsg = 'Could not obtain a coordinate/otl coefficients for ' + NetworkCode + ' ' + StationCode + ' after 20 tries. Maybe there where few valid RINEX files or could not find an ephemeris file. Debug info and errors follow:\n' + errors

    except pyOTL.pyOTLException as e:

        return "Error while calculating OTL for " + NetworkCode + " " + StationCode + ": " + str(e) + '\n Debug info and errors follow: \n' + errors

    except Exception:
        # print 'problem!' + traceback.format_exc()
        outmsg = traceback.format_exc() + ' processing otl: ' + NetworkCode + '.' + StationCode + ' using node ' + platform.node() + '\n Debug info and errors follow: \n' + errors

    return outmsg


def insert_stninfo(NetworkCode, StationCode, stninfofile):

    errors = []

    try:
        cnn = dbConnection.Cnn("gnss_data.cfg")
    except Exception:
        return traceback.format_exc() + ' insert_stninfo: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node()

    try:
        stnInfo = pyStationInfo.StationInfo(cnn,NetworkCode,StationCode, allow_empty=True)
        stninfo = stnInfo.parse_station_info(stninfofile)

    except pyStationInfo.pyStationInfoException as e:
        return traceback.format_exc() + ' insert_stninfo: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node()

    # insert all the receivers and antennas in the db
    for stn in stninfo:
        # there is a racing condition in this part due to many instances trying to insert the same receivers at the same time
        try:
            rec = cnn.query('SELECT * FROM receivers WHERE "ReceiverCode" = \'%s\'' % (stn['ReceiverCode']))
            if rec.ntuples() == 0:
                cnn.insert('receivers', ReceiverCode=stn['ReceiverCode'])
        except dbConnection.dbErrInsert:
            sys.exc_clear()

        try:
            rec = cnn.query('SELECT * FROM antennas WHERE "AntennaCode" = \'%s\'' % (stn['AntennaCode']))
            if rec.ntuples() == 0:
                cnn.insert('antennas', AntennaCode=stn['AntennaCode'])
        except dbConnection.dbErrInsert:
            sys.exc_clear()

    # ready to insert stuff to station info table
    for stn in stninfo:
        if stn.get('StationCode').lower() == StationCode:
            try:
                stnInfo.InsertStationInfo(stn)
            except pyStationInfo.pyStationInfoException as e:
                errors.append(str(e))
            except Exception:
                errors.append(traceback.format_exc() + ' insert_stninfo: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node())
                continue

    if not errors:
        return
    else:
        return '\n\n'.join(errors)


def remove_from_archive(cnn, record, Rinex, Config):

    # do not make very complex things here, just move it out from the archive
    retry_folder = os.path.join(Config.repository_data_in_retry, 'inconsistent_ppp_solution/' + Rinex.date.yyyy() + '/' + Rinex.date.ddd())

    pyArchive = pyArchiveStruct.RinexStruct(cnn)
    pyArchive.remove_rinex(record, retry_folder)

    event = pyEvents.Event(
        Description='After running PPP it was found that the rinex file %s does not belong to this station. '
                    'This file was removed from the rinex table and moved to the repository/data_in_retry to add it '
                    'to the corresponding station.' % (Rinex.origin_file),
        NetworkCode=record['NetworkCode'],
        StationCode=record['StationCode'],
        EventType='warn',
        Year=int(Rinex.date.year),
        DOY=int(Rinex.date.doy))

    cnn.insert_event(event)

    return


def execute_ppp(record, rinex_path):

    NetworkCode = record['NetworkCode']
    StationCode = record['StationCode']
    year = record['ObservationYear']
    doy = record['ObservationDOY']

    try:
        # try to open a connection to the database
        cnn = dbConnection.Cnn("gnss_data.cfg")

        Config = pyOptions.ReadOptions("gnss_data.cfg")
    except Exception:
        return traceback.format_exc() + ' processing rinex: ' + NetworkCode + '.' + StationCode + ' using node ' + platform.node()

    # create a temp folder in production to put the orbit in
    # we need to check the RF of the orbit to see if we have this solution in the DB
    try:

        # check to see if record exists for this file in ppp_soln
        # DDG: fixed frame to avoid problems with bad frame in the IGS sp3 files. Need to find a good way to determine
        # the frame of the orbits (probably in the config file)
        ppp_soln = cnn.query('SELECT * FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                             '"Year" = %s AND "DOY" = %s AND "ReferenceFrame" = \'%s\''
                             % (NetworkCode, StationCode, year, doy, 'IGb08'))

        if ppp_soln.ntuples() == 0:

            # load the stations record to get the OTL params
            rs_stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (
                                NetworkCode, StationCode))
            stn = rs_stn.dictresult()

            # RINEX FILE TO BE PROCESSED
            Rinex = pyRinex.ReadRinex(NetworkCode, StationCode, rinex_path)

            if not verify_rinex_date_multiday(cnn, Rinex.date, Rinex, Config):
                # the file is a multiday file. These files are not supposed to be in the archive, but, due to a bug in
                # ScanArchive (now fixed - 2017-10-26) some multiday files are still in the rinex table
                # the file is moved out of the archive (into the retry folder and the rinex record is deleted
                event = pyEvents.Event(EventType='warn',
                                       Description='RINEX record in database belonged to a multiday file. '
                                                   'The record has been removed from the database. '
                                                   'See previous associated event.',
                                       StationCode=StationCode,
                                       NetworkCode=NetworkCode,
                                       Year=int(Rinex.date.year),
                                       DOY=int(Rinex.date.doy))
                cnn.insert_event(event)

                cnn.begin_transac()
                cnn.query(
                    'DELETE FROM gamit_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))
                cnn.query(
                    'DELETE FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))
                cnn.query(
                    'DELETE FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i AND "Filename" = \'%s\''
                    % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY'], record['Filename']))
                cnn.commit_transac()

                return

            stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode, Rinex.date)

            Rinex.normalize_header(StationInfo=stninfo, x=stn[0]['auto_x'], y=stn[0]['auto_y'], z=stn[0]['auto_z'])

            ppp = pyPPP.RunPPP(Rinex, stn[0]['Harpos_coeff_otl'], Config.options, Config.sp3types, Config.sp3altrn, stninfo.AntennaHeight, hash=stninfo.hash)
            ppp.exec_ppp()

            # verify that the solution is from the station it claims to be
            Result, match, closest_stn = ppp.verify_spatial_coherence(cnn, StationCode)

            if Result:
                if match['NetworkCode'] == NetworkCode and match['StationCode'] == StationCode:
                    # the match agrees with the station-day that we THINK we are processing
                    # this check should not be necessary if the rinex went through Archive Service, since we
                    # already match rinex vs station
                    # but it's still here to prevent that a rinex imported by pyScanArchive (which assumes the rinex
                    # files belong to the network/station of the folder) doesn't get into the PPP table if it's not
                    # of the station it claims to be.

                    # insert record in DB
                    cnn.insert('ppp_soln', ppp.record)
                    # DDG: Eric's request to generate a date of PPP solution
                    event = pyEvents.Event(Description='A new PPP solution was created for frame IGb08',
                                           NetworkCode=NetworkCode,
                                           StationCode=StationCode,
                                           Year=int(year),
                                           DOY=int(doy))
                    cnn.insert_event(event)
                else:
                    remove_from_archive(cnn, record, Rinex, Config)
            else:
                remove_from_archive(cnn, record, Rinex, Config)

    except (pyRinex.pyRinexException, pyRinex.pyRinexExceptionBadFile, pyRinex.pyRinexExceptionSingleEpoch) as e:

        e.event['StationCode'] = StationCode
        e.event['NetworkCode'] = NetworkCode
        e.event['Year'] = int(year)
        e.event['DOY'] = int(doy)

        cnn.insert_event(e.event)

    except pyPPP.pyRunPPPException as e:

        e.event['StationCode'] = StationCode
        e.event['NetworkCode'] = NetworkCode
        e.event['Year'] = int(year)
        e.event['DOY'] = int(doy)

        cnn.insert_event(e.event)

    except pyStationInfo.pyStationInfoException as e:
        e.event['StationCode'] = StationCode
        e.event['NetworkCode'] = NetworkCode
        e.event['Year'] = int(year)
        e.event['DOY'] = int(doy)

        cnn.insert_event(e.event)

    except Exception:
        return traceback.format_exc() + ' processing: ' + NetworkCode + '.' + StationCode + ' ' + str(year) + ' ' + str(doy) + ' using node ' + platform.node()


def output_handle(callback):

    messages = [outmsg.errors for outmsg in callback]

    if len([out_msg for out_msg in messages if out_msg]) > 0:
        tqdm.write(
            ' -- There were unhandled errors during this batch. Please check errors_pyScanArchive.log for details')

    # function to print any error that are encountered during parallel execution
    for msg in messages:
        if msg:
            f = open('errors_pyScanArchive.log','a')
            f.write('ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n')
            f.write(msg + '\n')
            f.write('END OF ERROR =================== \n\n')
            f.close()

    return []


def post_scan_rinex_job(cnn, Config, Archive, rinex_file, rinexpath, master_list, JobServer, callback, pbar):

    valid, result = Archive.parse_archive_keys(rinex_file, key_filter=('network', 'station', 'year', 'doy'))

    depfuncs = (verify_rinex_date_multiday,)
    modules = ('dbConnection', 'pyDate', 'pyRinex', 'shutil', 'platform', 'datetime',
               'traceback', 'pyOptions', 'pyEvents', 'Utils', 'os')

    if valid:

        NetworkCode = result['network']
        StationCode = result['station']
        year = result['year']
        doy = result['doy']

        # check the master_list
        if NetworkCode + '.' + StationCode in master_list:
            # check existence of network in the db
            rs = cnn.query('SELECT * FROM networks WHERE "NetworkCode" = \'%s\'' % (NetworkCode))
            if rs.ntuples() == 0:
                cnn.insert('networks', NetworkCode=NetworkCode, NetworkName='UNK')

            # check existence of station in the db
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (
            NetworkCode, StationCode))
            if rs.ntuples() == 0:
                # run grdtab to get the OTL parameters in HARPOS format and insert then in the db
                # use the current rinex to get an approximate coordinate
                cnn.insert('stations', NetworkCode=NetworkCode, StationCode=StationCode)

            if Config.run_parallel:
                arguments = (NetworkCode, StationCode, year, doy, rinexpath)

                JobServer.SubmitJob(try_insert, arguments, depfuncs, modules, callback, callback_scan_class(pbar), 'callbackfunc')

                if JobServer.process_callback:
                    # handle any output messages during this batch
                    callback = output_handle(callback)
                    JobServer.process_callback = False
            else:
                callback.append(callback_class(pbar))
                callback[0].callbackfunc(try_insert(NetworkCode, StationCode, year, doy, rinexpath))
                callback = output_handle(callback)

    return callback

def scan_rinex(cnn, JobServer, pyArchive, archive_path, Config, master_list):

    callback = []
    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    print " >> Analyzing the archive's structure..."
    pbar = tqdm(ncols=80, unit='crz')

    #archivefiles, path2rinex, _ = pyArchive.scan_archive_struct(archive_path, execute_function=post_scan_rinex_job, arguments=(master_list, JobServer, callback, pbar))
    for path, _, files in scandir.walk(archive_path):
        for file in files:
            # DDG issue #15: match the name of the file to a valid rinex filename
            if pyArchive.parse_crinex_filename(file):
                # only examine valid rinex compressed files
                rnx = os.path.join(path, file).rsplit(archive_path + '/')[1]
                path2rnx = os.path.join(path, file)

                pbar.set_postfix(crinex=rnx)
                pbar.update()

                callback = post_scan_rinex_job(cnn, Config, pyArchive, rnx, path2rnx, master_list, JobServer, callback, pbar)


    if Config.run_parallel:
        tqdm.write(' -- waiting for jobs to finish...')
        JobServer.job_server.wait()
        tqdm.write(' -- Done.')

    # handle any output messages during this batch
    output_handle(callback)
    pbar.close()

    if Config.run_parallel:
         print "\n"
         JobServer.job_server.print_stats()

    return


def process_otl(cnn, JobServer, run_parallel, archive_path, brdc_path, sp3types, sp3altrn, master_list):

    print ""
    print " >> Calculating coordinates and OTL for new stations..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    rs = cnn.query('SELECT "NetworkCode", "StationCode" FROM stations '
                   'WHERE auto_x is null OR auto_y is null OR auto_z is null OR "Harpos_coeff_otl" is null '
                   'AND "NetworkCode" not like \'?%\' '
                   'AND "NetworkCode" || \'.\' || "StationCode" IN (\'' + '\',\''.join(master_list) + '\')')

    records = rs.dictresult()

    pbar = tqdm(total=len(records), ncols=80)
    callback = []

    depfuncs = (ecef2lla,)
    modules = ('dbConnection', 'pyRinex', 'pyArchiveStruct', 'pyOTL', 'pyPPP', 'numpy', 'platform', 'pySp3', 'traceback', 'pyOptions')

    for record in records:
        NetworkCode = record['NetworkCode']
        StationCode = record['StationCode']

        if run_parallel:

            arguments = (NetworkCode, StationCode)

            JobServer.SubmitJob(obtain_otl, arguments, depfuncs, modules, callback, callback_class(pbar), 'callbackfunc')

            if JobServer.process_callback:
                # handle any output messages during this batch
                callback = output_handle(callback)
                JobServer.process_callback = False

        else:
            callback.append(callback_class(pbar))
            callback[0].callbackfunc(obtain_otl(NetworkCode, StationCode))
            callback = output_handle(callback)

    if run_parallel:
        tqdm.write(' >> waiting for jobs to finish...')
        JobServer.job_server.wait()
        tqdm.write(' >> Done.')

    # handle any output messages during this batch
    output_handle(callback)
    pbar.close()

    if run_parallel:
        print '\n'
        JobServer.job_server.print_stats()

    return


def scan_station_info(JobServer, run_parallel, pyArchive, archive_path, master_list):

    print " >> Searching for station info files in the archive..."

    stninfo, path2stninfo = pyArchive.scan_archive_struct_stninfo(archive_path)

    print "   >> Processing Station Info files..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    pbar = tqdm(total=len(stninfo), ncols=80)
    callback = []

    modules = ('dbConnection', 'pyStationInfo', 'sys', 'datetime', 'pyDate', 'platform', 'traceback')

    for stninfofile, stninfopath in zip(stninfo,path2stninfo):

        valid, result = pyArchive.parse_archive_keys(stninfofile, key_filter=('network','station'))

        if valid:

            NetworkCode = result['network']
            StationCode = result['station']

            if NetworkCode + '.' + StationCode in master_list:
                # we were able to get the network and station code, add it to the database
                if run_parallel:
                    arguments = (NetworkCode, StationCode, stninfopath)

                    JobServer.SubmitJob(insert_stninfo, arguments, tuple(), modules, callback, callback_class(pbar), 'callbackfunc')

                else:
                    callback.append(callback_class(pbar))
                    callback[0].callbackfunc(insert_stninfo(NetworkCode,StationCode,stninfopath))
                    callback = output_handle(callback)

    if run_parallel:
        tqdm.write(' >> waiting for jobs to finish...')
        JobServer.job_server.wait()
        tqdm.write(' >> Done.')

    # handle any output messages during this batch
    output_handle(callback)
    pbar.close()

    if run_parallel:
        print '\n'
        JobServer.job_server.print_stats()

    return

def scan_station_info_manual(cnn, pyArchive, stn_info_path, stations, stn_info_net, stdin=None):
    # input "stations" has a list in net.stnm format

    print " >> Manual scan of station info files in " + stn_info_path

    NetworkCode = stn_info_net

    if stdin:
        stn_info_obj = pyStationInfo.StationInfo(cnn)
        stn_list = stn_info_obj.parse_station_info(stdin)

        for Station in tqdm(stations, total=len(stations)):
            # input "stations" has a list in net.stnm format
            if Station['StationCode'] in [stn['StationCode'].lower() for stn in stn_list]:
                tqdm.write("   >> Processing %s using network code %s" % (Station['StationCode'], NetworkCode))
                out = insert_stninfo(NetworkCode, Station['StationCode'], stdin)

                if out:
                    tqdm.write(out)
            else:
                tqdm.write('   >> Station %s.%s was not found in the station info file %s' % (Station['NetworkCode'], Station['StationCode'], 'standard input'))

    else:
        if os.path.isfile(stn_info_path):
            path2stninfo = [stn_info_path]
        else:
            _, path2stninfo = pyArchive.scan_archive_struct_stninfo(stn_info_path)

        print "   >> Found %i station information files." % (len(path2stninfo))

        for stninfopath in path2stninfo:

            stn_info_obj = pyStationInfo.StationInfo(cnn)
            stn_list = stn_info_obj.parse_station_info(stninfopath)

            for Station in tqdm(stations, total=len(stations)):
                # input "stations" has a list in net.stnm format
                if Station['StationCode'] in [stn['StationCode'].lower() for stn in stn_list]:
                    tqdm.write("   >> Processing %s using network code %s" % (Station['StationCode'], NetworkCode))
                    out = insert_stninfo(NetworkCode,Station['StationCode'],stninfopath)

                    if out:
                        tqdm.write(out)
                else:
                    tqdm.write('   >> Station %s.%s was not found in the station info file %s' % (Station['NetworkCode'], Station['StationCode'], stninfopath))

    return

def hash_check(cnn, master_list, sdate, edate, rehash=False):

    print " >> Running hash check to the PPP solutions..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    ppp_soln = cnn.query('SELECT ppp_soln.* FROM ppp_soln '
                         'LEFT JOIN rinex_proc as rinex ON '
                         'ppp_soln."NetworkCode" = rinex."NetworkCode" AND '
                         'ppp_soln."StationCode" = rinex."StationCode" AND '
                         'ppp_soln."Year" = rinex."ObservationYear" AND '
                         'ppp_soln."DOY" = rinex."ObservationDOY" '
                         'WHERE ppp_soln."NetworkCode" || \'.\' || ppp_soln."StationCode" IN (\'' + '\',\''.join(master_list) + '\') '
                         'AND rinex."ObservationSTime" BETWEEN \'' + sdate.yyyymmdd() + '\' AND \'' + (edate+1).yyyymmdd() + '\' '
                         'ORDER BY "ObservationSTime", ppp_soln."NetworkCode", ppp_soln."StationCode"')

    tbl = ppp_soln.dictresult()

    # check the hash values if specified
    if not rehash:
        print ' -- Checking hash values.'
    else:
        print ' -- Rehashing all records. This may take a while...'

    for soln in tqdm(tbl,ncols=80):
        # load station info object
        try:
            stninfo = pyStationInfo.StationInfo(cnn, soln['NetworkCode'], soln['StationCode'], pyDate.Date(year=soln['Year'],doy=soln['DOY']))

            if stninfo.hash != soln['hash']:
                if not rehash:
                    tqdm.write(" -- Hash value for %s.%s %i %03i does not match with Station Information hash. PPP coordinate will be recalculated." % (soln['NetworkCode'], soln['StationCode'], soln['Year'], soln['DOY']))
                    cnn.delete('ppp_soln', soln)
                else:
                    tqdm.write(" -- %s.%s %i %03i has been rehashed." % (soln['NetworkCode'], soln['StationCode'], soln['Year'], soln['DOY']))
                    cnn.update('ppp_soln', soln, hash=stninfo.hash)
        except pyStationInfo.pyStationInfoException as e:
            tqdm.write(str(e))
        except Exception:
            raise

    if not rehash:
        print ' -- Done checking hash values.'
    else:
        print ' -- Done rehashing PPP records.'


def process_ppp(cnn, pyArchive, archive_path, JobServer, run_parallel, master_list, sdate, edate):

    print " >> Running PPP on the RINEX files in the archive..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    # for each rinex in the db, run PPP and get a coordinate
    rs_rnx = cnn.query('SELECT rinex.* FROM rinex_proc as rinex '
                       'LEFT JOIN ppp_soln ON '
                       'rinex."NetworkCode" = ppp_soln."NetworkCode" AND '
                       'rinex."StationCode" = ppp_soln."StationCode" AND '
                       'rinex."ObservationYear" = ppp_soln."Year" AND '
                       'rinex."ObservationDOY" = ppp_soln."DOY" '
                       'WHERE ppp_soln."NetworkCode" is null '
                       'AND rinex."NetworkCode" || \'.\' || rinex."StationCode" IN (\'' + '\',\''.join(master_list) + '\') '
                       'AND rinex."ObservationSTime" BETWEEN \'' + sdate.yyyymmdd() + '\' AND \'' + (edate+1).yyyymmdd() + '\' '
                       'ORDER BY "ObservationSTime"')

    tblrinex = rs_rnx.dictresult()

    pbar = tqdm(total=len(tblrinex), ncols=80)

    modules = ('dbConnection', 'pyRinex', 'pyPPP', 'pyStationInfo', 'pyDate', 'pySp3', 'os', 'platform', 'pyArchiveStruct', 'traceback', 'pyOptions', 'pyEvents')
    depfuncs = (remove_from_archive, verify_rinex_date_multiday)

    callback = []

    for record in tblrinex:

        rinex_path = pyArchive.build_rinex_path(record['NetworkCode'], record['StationCode'],
                                                record['ObservationYear'], record['ObservationDOY'])

        # add the base dir
        rinex_path = os.path.join(archive_path, rinex_path)

        if run_parallel:

            callback.append(callback_class(pbar))

            arguments = (record, rinex_path)

            JobServer.SubmitJob(execute_ppp, arguments, depfuncs, modules, callback, callback_class(pbar), 'callbackfunc')

            if JobServer.process_callback:
                # handle any output messages during this batch
                callback = output_handle(callback)
                JobServer.process_callback = False

        else:
            callback.append(callback_class(pbar))
            callback[0].callbackfunc(execute_ppp(record, rinex_path))
            callback = output_handle(callback)

    if run_parallel:
        tqdm.write(' >> waiting for jobs to finish...')
        JobServer.job_server.wait()
        tqdm.write(' >> Done.')

    # handle any output messages during this batch
    output_handle(callback)
    pbar.close()

    if run_parallel:
        print '\n'
        JobServer.job_server.print_stats()


def main():

    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm', help="List of networks/stations to process given in [net].[stnm] format or just [stnm] (separated by spaces; if [stnm] is not unique in the database, all stations with that name will be processed). Use keyword 'all' to process all stations in the database. If [net].all is given, all stations from network [net] will be processed. Alternatevily, a file with the station list can be provided.")
    parser.add_argument('-rinex', '--rinex', action='store_true', help="Scan the current archive for RINEX files (d.Z).")
    parser.add_argument('-otl', '--ocean_loading', action='store_true', help="Calculate ocean loading coefficients.")
    parser.add_argument('-stninfo', '--station_info', nargs='*', metavar='argument', help="Insert station information to the database. "
        "If no arguments are given, then scan the archive for station info files and use their location (folder) to determine the network to use during insertion. "
        "Only stations in the station list will be processed. "
        "If a filename is provided, then scan that file only, in which case a second argument specifies the network to use during insertion. Eg: -stninfo ~/station.info arg. "
        "In cases where multiple networks are being processed, the network argument will be used to desambiguate station code conflicts. "
        "Eg: pyScanArchive all -stninfo ~/station.info arg -> if a station named igm1 exists in networks 'igs' and 'arg', only 'arg.igm1' will get the station information insert. "
        "Use keyword 'stdin' to read the station information data from the pipeline.")
    parser.add_argument('-ppp', '--ppp', nargs='*', metavar='argument', help="Run ppp on the rinex files in the database. Append [date_start] and (optionally) [date_end] to limit the range of the processing. Allowed formats are yyyy.doy or yyyy/mm/dd. Append keyword 'hash' to the end to check the PPP hash values against the station information records. If hash doesn't match, recalculate the PPP solutions.")
    parser.add_argument('-rehash', '--rehash', nargs='*', metavar='argument', help="Check PPP hash against station information hash. Rehash PPP solutions to match the station information hash without recalculating the PPP solution. Optionally append [date_start] and (optionally) [date_end] to limit the rehashing time window. Allowed formats are yyyy.doy or yyyy/mm/dd.")
    parser.add_argument('-np', '--noparallel', action='store_true', help="Execute command without parallelization.")

    args = parser.parse_args()

    if not args.station_info is None and (not len(args.station_info) in (0,2)):
        parser.error('-stninfo requires 0 or 2 arguments. {} given.'.format(len(args.station_info)))


    Config = pyOptions.ReadOptions("gnss_data.cfg") # type: pyOptions.ReadOptions

    cnn = dbConnection.Cnn("gnss_data.cfg")
    # create the execution log
    cnn.insert('executions', script='pyScanArchive.py')

    # get the station list
    if len(args.stnlist) == 1 and os.path.isfile(args.stnlist[0]):
        print ' >> Station list read from ' + args.stnlist[0]
        stnlist = [line.strip() for line in open(args.stnlist[0], 'r')]
        stnlist = [{'NetworkCode': item.split('.')[0], 'StationCode': item.split('.')[1]} for item in stnlist]
    else:
        stnlist = Utils.process_stnlist(cnn, args.stnlist)

    print ' >> Selected station list:'
    print_columns([item['NetworkCode'] + '.' + item['StationCode'] for item in stnlist])

    pyArchive = pyArchiveStruct.RinexStruct(cnn)

    # initialize the PP job server
    if not args.noparallel:
        JobServer = pyJobServer.JobServer(Config) # type: pyJobServer.JobServer
    else:
        JobServer = None
        Config.run_parallel = False
    #########################################

    if args.rinex:
        scan_rinex(cnn, JobServer, pyArchive, Config.archive_path, Config, stnlist)

    #########################################

    if args.ocean_loading:
        process_otl(cnn, JobServer, Config.run_parallel, Config.archive_path, Config.brdc_path, Config.sp3types, Config.sp3altrn, stnlist)

    #########################################

    if not args.station_info is None:
        if len(args.station_info) == 0:
            scan_station_info(JobServer, Config.run_parallel, pyArchive, Config.archive_path, stnlist)
        else:
            stn_info_stdin = []
            if args.station_info[0] == 'stdin':
                for line in sys.stdin:
                    stn_info_stdin.append(line)

            scan_station_info_manual(cnn, pyArchive, args.station_info[0], stnlist, args.station_info[1], stn_info_stdin)

    #########################################

    if args.rehash is not None:
        dates = []
        try:
            dates = process_date(args.rehash)
        except ValueError as e:
            parser.error(str(e))

        hash_check(cnn, stnlist, dates[0], dates[1], rehash=True)

    #########################################

    if not args.ppp is None:
        # check other possible arguments
        dates = []
        do_hash = True if 'hash' in args.ppp else False
        date_args = [date for date in args.ppp if date != 'hash']

        try:
            dates = process_date(date_args)
        except ValueError as e:
            parser.error(str(e))

        if do_hash:
            hash_check(cnn, stnlist, dates[0], dates[1], rehash=False)

        process_ppp(cnn, pyArchive, Config.archive_path, JobServer, Config.run_parallel, stnlist, dates[0], dates[1])

    #########################################

    # remove the production dir
    #if os.path.isdir('production'):
    #    rmtree('production')

if __name__ == '__main__':

    main()