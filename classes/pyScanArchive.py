"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Main routines to load the RINEX files to the database, load station information, run PPP on the archive files and obtain
the OTL coefficients
usage:
         --rinex  : scan for rinex"
         --rnxcft : resolve rinex conflicts (multiple files per day)"
         --otl    : calculate OTL parameters for stations in the database"
         --stninfo: scan for station info files in the archive"
                    if no arguments, searches the archive for station info files and uses their location to determine network"
                    else, use: --stninfo_path --stn --network, where"
                    --stninfo_path: path to a dir with station info files, or single station info file. Type 'stdin' to use standard input"
                    --stn         : station to search for in the station info, of list of stations separated by comma, no spaces between ('all' will try to add all of them)"
                    --net         : network name that has to be used to add the station information"
         --ppp    : run ppp to the rinex files in the archive"
         --all    : do all of the above"
"""

import pyArchiveStruct
import dbConnection
import pyDate
import pyRinex
import traceback
import datetime
import copy
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
import scandir

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
        cnn.insert_warning(
            '%s was a multi-day rinex file. The following rinex files where generated and moved to the repository/data_in_retry: %s. The file %s (which did not enter the database) was deleted from the archive.' % (
            rinexinfo.origin_file, ','.join(rnxlist), rinexinfo.crinex))
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

        cnn.insert_warning(
            'The date in the archive for ' + rinexinfo.NetworkCode + '.' + rinexinfo.StationCode + '::' +
            rinexinfo.rinex + ' (' + date.yyyyddd() + ') does not agree with the mean session date (' +
            rinexinfo.date.yyyyddd() + '). The file was moved to the repository/data_in_retry and should be analyzed later by pyArchiveService.')

        return False

    return True


def check_rinex_timespan_int(rinex, stn):

    # DDG: in some unknown cases, stn['ObservationSTime'] and stn['ObservationETime'] comes back as a string.

    if type(stn['ObservationSTime']) is str:
        ObservationSTime = datetime.datetime.strptime(stn['ObservationSTime'], '%Y-%m-%d %H:%M:%S')
    else:
        ObservationSTime = stn['ObservationSTime']

    if type(stn['ObservationETime']) is str:
        ObservationETime = datetime.datetime.strptime(stn['ObservationETime'], '%Y-%m-%d %H:%M:%S')
    else:
        ObservationETime = stn['ObservationETime']

    # how many seconds difference between the rinex file and the record in the db
    stime_diff = abs((ObservationSTime - rinex.datetime_firstObs).total_seconds())
    etime_diff = abs((ObservationETime - rinex.datetime_lastObs).total_seconds())

    # at least four minutes different on each side
    if stime_diff <= 240 and etime_diff <= 240 and stn['Interval'] == rinex.interval:
        return False
    else:
        return True


def try_insert(NetworkCode, StationCode, year, doy, rinex):

    try:
        # try to open a connection to the database
        cnn = dbConnection.Cnn("gnss_data.cfg")
        Config = pyOptions.ReadOptions("gnss_data.cfg")
    except Exception:
        return traceback.format_exc() + ' processing rinex: ' + rinex + ' (' + NetworkCode + ' ' + StationCode + ' ' + year + ' ' + doy + ') using node ' + platform.node()

    try:
        # get the rinex file name
        filename = rinex.split('/')[-1].replace('d.Z', 'o')

        # build the archive level sql string
        # the file has not to exist in the RINEX table
        # or in the RINEX extra table with the same name
        rs = cnn.query(
            'SELECT * FROM rinex       WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %s UNION '
            'SELECT * FROM rinex_extra WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %s AND "Filename" = \'%s\''
            % (NetworkCode, StationCode, year, doy, NetworkCode, StationCode, year, doy, filename))

        if rs.ntuples() == 0:
            # no record found, new rinex file for this day
            # examine the rinex. This is NOT a RINEX that exists in rinex_extra
            rinexinfo = pyRinex.ReadRinex(NetworkCode, StationCode, rinex)

            date = pyDate.Date(year=year, doy=doy)

            # verify that the rinex is from this date and that is not a multiday file
            if verify_rinex_date_multiday(cnn, date, rinexinfo, Config):
                try:
                    # create the insert statement
                    cnn.insert('rinex', rinexinfo.record)
                except dbConnection.dbErrInsert:
                    # insert duplicate values: two parallel processes tried to insert different filenames of the same station
                    # to the db: insert to the rinex_extra and let the parent process decide (in serial mode)
                    # DDG: this insert can also fail. Example:
                    # two files from the same day: riog2040.04d -> rinex and riog2041.04d -> rinex_extra
                    # delete riog2040.04d from rinex because, say, bad interval (due to bug)
                    # then scan_archive tries to insert record riog2040.04d and riog2041.04d at the same time
                    # only riog2040.04d make it in
                    # then we try to insert riog2041.04d in rinex_extra
                    # but it already exists, so it fails insertion too.
                    # DDG: now, we check to see if the file exists either in rinex or rinex_extra.
                    # If in rinex_extra, ignore too
                    cnn.insert('rinex_extra', rinexinfo.record)
        else:
            # one or more records found, see if it's in rinex or rinex_extra
            rnx = rs.dictresult()[0]

            # Check if the filename is the same
            rs = cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %s AND "Filename" = \'%s\''
                % (NetworkCode, StationCode, year, doy, filename))

            # if there is a record, it's the same file being reprocessed. Just ignore it
            if rs.ntuples() == 0:
                # if no records came back, there might be a duplicate rinex with a different filename
                # or this could be another session of the same day

                # first, verify that this file isn't in the rinex_extra table
                # if it's in the table, do nothing
                rs = cnn.query('SELECT * FROM rinex_extra WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %s AND "Filename" = \'%s\''
                    % (NetworkCode, StationCode, year, doy, filename))

                if rs.ntuples() == 0:
                    # the file was not found the rinex_extra

                    rinexinfo = pyRinex.ReadRinex(NetworkCode, StationCode, rinex)

                    date = pyDate.Date(year=year, doy=doy)

                    if verify_rinex_date_multiday(cnn, date, rinexinfo, Config):

                        # we need to check if both files are the same or not
                        # if the file has the same time span as the primary rinex in the db and the same interval,
                        # do not add it to the database
                        if check_rinex_timespan_int(rinexinfo, rnx):
                            # insert to rinex_extra. Will be processed later (not in parallel) to decide which file
                            # should go into rinex and which one should stay in rinex_extra
                            cnn.insert('rinex_extra', rinexinfo.record)
                        else:
                            # do not remove for the moment
                            # log the event
                            #os.remove()
                            cnn.insert_info('The archive crinex file %s had the same timespan and sampling interval than %s.%s %s. The file was not added to rinex_extra but it was not removed from the archive. In a future release, these files will be deleted.' % (rinex,NetworkCode,StationCode,date.yyyyddd()))


    except pyRinex.pyRinexException as e:

        cnn.insert_warning('During ' + rinex + ' :' + str(e))
        return

    except Exception:

        return traceback.format_exc() + ' processing rinex: ' + rinex + ' (' + NetworkCode + ' ' + StationCode + ' ' + year + ' ' + doy + ') using node ' + platform.node()


def process_extra_rinex(NetworkCode, StationCode, year, doy, rinex):

    try:
        # try to open a connection to the database
        cnn = dbConnection.Cnn("gnss_data.cfg")
    except Exception:
        return traceback.format_exc() + ' processing rinex_extra: ' + rinex + ' (' + NetworkCode + ' ' + StationCode + ' ' + year + ' ' + doy + ') using node ' + platform.node()

    try:
        # load the current_rinex
        rs = cnn.query(
            'SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %s AND "ObservationDOY" = %s'
            % (NetworkCode, StationCode, year, doy))

        # save the information of the current rinex in the db
        current_rinex = rs.dictresult()[0]

        rinexinfo = pyRinex.ReadRinex(NetworkCode, StationCode, rinex)

        if (current_rinex['ObservationETime'] - current_rinex['ObservationSTime']).total_seconds() < \
                (rinexinfo.datetime_firstObs - rinexinfo.datetime_firstObs).total_seconds():
            # new file larger than previous, update rinex table
            cnn.begin_transac()

            # this dictionary will be updated
            update_dict = copy.deepcopy(current_rinex)

            cnn.update('rinex', update_dict, rinexinfo.record)

            # update the record in rinex_extra (put in the rinex file we had in rinex)
            cnn.insert('rinex_extra', current_rinex)
            # delete the other one
            # cnn.delete('rinex_extra', update_dict)
            cnn.query('DELETE FROM rinex_extra WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i AND "Filename" = \'%s\''
            % (update_dict['NetworkCode'], update_dict['StationCode'], update_dict['ObservationYear'], update_dict['ObservationDOY'], update_dict['Filename']))

            # generate an info event saying what we did
            cnn.insert_info(
                'A longer rinex file (' + rinexinfo.rinex + ') was found for ' + NetworkCode + ' ' + StationCode + ' '
                + rinexinfo.date.yyyyddd() + ' and replaced file ' + current_rinex['Filename'])

            cnn.commit_transac()

    except pyRinex.pyRinexException as e:

        cnn.insert_warning('Processing EXTRA RINEX during ' + rinex + ' :' + str(e))
        return

    except Exception:

        return traceback.format_exc() + ' processing rinex_extra: ' + rinex + ' (' + NetworkCode + ' ' + StationCode + ' ' + year + ' ' + doy + ') using node ' + platform.node()


def ecef2lla(ecefArr):
    # convert ECEF coordinates to LLA
    # test data : test_coord = [2297292.91, 1016894.94, -5843939.62]
    # expected result : -66.8765400174 23.876539914 999.998386689

    x = float(ecefArr[0])
    y = float(ecefArr[1])
    z = float(ecefArr[2])

    a = 6378137
    e = 8.1819190842622e-2

    asq = numpy.power(a, 2)
    esq = numpy.power(e, 2)

    b = numpy.sqrt(asq * (1 - esq))
    bsq = numpy.power(b, 2)

    ep = numpy.sqrt((asq - bsq) / bsq)
    p = numpy.sqrt(numpy.power(x, 2) + numpy.power(y, 2))
    th = numpy.arctan2(a * z, b * p)

    lon = numpy.arctan2(y, x)
    lat = numpy.arctan2((z + numpy.power(ep, 2) * b * numpy.power(numpy.sin(th), 3)),
                     (p - esq * a * numpy.power(numpy.cos(th), 3)))
    N = a / (numpy.sqrt(1 - esq * numpy.power(numpy.sin(lat), 2)))
    alt = p / numpy.cos(lat) - N

    lon = lon * 180 / numpy.pi
    lat = lat * 180 / numpy.pi

    return numpy.array([lat]), numpy.array([lon]), numpy.array([alt])


def obtain_otl(NetworkCode, StationCode, archive_path, brdc_path, sp3types, sp3altrn):

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
        count = cnn.query('SELECT count(*) as cc FROM rinex as r WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode))

        count = count.dictresult()

        #print '\nsuma total: ' + str(count[0]['cc'])

        if count[0]['cc'] >= 10:
            stn = cnn.query('SELECT * FROM (SELECT row_number() OVER() as rnum, r.* FROM rinex as r WHERE "NetworkCode" = \'%s\' '
                            'AND "StationCode" = \'%s\' ORDER BY "ObservationSTime") AS rr '
                            'WHERE (rnum %% ((SELECT count(*) FROM rinex as r WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\')/10)) = 0' % (
                NetworkCode, StationCode, NetworkCode, StationCode))

            #print 'select 10>'
        elif count[0]['cc'] < 10:
            stn = cnn.query(
                'SELECT * FROM (SELECT row_number() OVER() as rnum, r.* FROM rinex as r WHERE "NetworkCode" = \'%s\' '
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
                                          os.path.join(archive_path, file))

                # run ppp without otl and met and in non-strict mode
                ppp = pyPPP.RunPPP(Rinex, '', Config.options, sp3types, sp3altrn, Rinex.antOffset, False, False)

                ppp.exec_ppp()

                x.append(ppp.x)
                y.append(ppp.y)
                z.append(ppp.z)
                errors = errors + 'PPP -> ' + NetworkCode + '.' + StationCode + ': ' + str(ppp.x) + ' ' + str(ppp.y) + ' ' + str(ppp.z) + '\n'

            except (IOError, pyRinex.pyRinexException, pySp3.pySp3Exception, pyPPP.pyRunPPPException) as e:
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
        outmsg = traceback.format_exc() + ' processing otl: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node() + '\n Debug info and errors follow: \n' + errors

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
    Rinex.move_origin_file(retry_folder)

    cnn.begin_transac()
    # delete this rinex entry from the database
    # cnn.delete('rinex', record)
    cnn.query(
        'DELETE FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i'
        % (record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))

    # are there any rinex extra? Maybe they are correct.
    rs = cnn.query(
        'SELECT * FROM rinex_extra WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i' % (
        record['NetworkCode'], record['StationCode'], record['ObservationYear'], record['ObservationDOY']))

    if rs.ntuples() > 0:
        rnx = rs.dictresult()

        cnn.insert_warning(
            'After running PPP it was found that the rinex file %s does not belong to %s.%s. This file will be removed from the rinex table (and a rinex_extra %s was promoted to rinex) and moved to the repository/data_in_retry to try to add it to the corresponding station.' % (
                Rinex.origin_file, record['NetworkCode'], record['StationCode'], rnx[0]['Filename']))

        cnn.insert('rinex', rnx[0])
        #cnn.delete('rinex_extra', rnx[0])
        cnn.query(
            'DELETE FROM rinex_extra WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i AND "Filename" = \'%s\''
            % (rnx[0]['NetworkCode'], rnx[0]['StationCode'], rnx[0]['ObservationYear'],
               rnx[0]['ObservationDOY'], rnx[0]['Filename']))

        cnn.commit_transac()

        # compile information to run ppp on the "new" rinex file
        pyArchive = pyArchiveStruct.RinexStruct(cnn)

        rinex_path = pyArchive.build_rinex_path(rnx[0]['NetworkCode'], rnx[0]['StationCode'],
                                                rnx[0]['ObservationYear'], rnx[0]['ObservationDOY'])
        # add the base dir
        rinex_path = os.path.join(Config.archive_path, rinex_path)

        # ppp this rinex newly added rinex file (from the rinex_extra table)
        execute_ppp(rnx[0], rinex_path)
    else:
        cnn.insert_warning(
            'After running PPP it was found that the rinex file %s does not belong to %s.%s. This file will be removed from the rinex table (no rinex_extra found to be promoted to rinex) and moved to the repository/data_in_retry to add it to the corresponding station.' % (
                Rinex.origin_file, record['NetworkCode'], record['StationCode']))

        cnn.commit_transac()

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
        return traceback.format_exc() + ' processing rinex: ' + NetworkCode + ' ' + StationCode + ' using node ' + platform.node()

    # create a temp folder in production to put the orbit in
    # we need to check the RF of the orbit to see if we have this solution in the DB
    try:

        #rootdir = 'production/' + NetworkCode + '/' + StationCode

        #try:
        #    if not os.path.exists(rootdir):
        #        os.makedirs(rootdir)
        #except OSError:
        #    # folder exists from a concurring instance, ignore the error
        #    sys.exc_clear()
        #except:
        #    raise

        #date = pyDate.Date(year=year,doy=doy)
        #orbit = pySp3.GetSp3Orbits(Config.options['sp3'], date, Config.sp3types, rootdir)

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

            stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode, Rinex.date)

            Rinex.normalize_header(StationInfo=stninfo, x=stn[0]['auto_x'], y=stn[0]['auto_y'], z=stn[0]['auto_z'])

            ppp = pyPPP.RunPPP(Rinex, stn[0]['Harpos_coeff_otl'], Config.options, Config.sp3types, Config.sp3altrn, stninfo.AntennaHeight,hash=stninfo.hash)
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
                    cnn.insert_info('A new PPP solution was created for %s.%s %i %i (frame %s)' % (NetworkCode, StationCode, int(year), int(doy), 'IGb08'))
                else:
                    remove_from_archive(cnn, record, Rinex, Config)
            else:
                remove_from_archive(cnn, record, Rinex, Config)

    except pyRinex.pyRinexException as e:
        cnn.insert_warning('Error in ReadRinex: ' + NetworkCode + ' ' + StationCode + ' ' + str(year) + ' ' + str(doy) + ': \n' + str(e))

    except pyPPP.pyRunPPPException as e:
        cnn.insert_warning('Error in PPP while processing: ' + NetworkCode + ' ' + StationCode + ' ' + str(year) + ' ' + str(doy) + ': \n' + str(e))

    except pyStationInfo.pyStationInfoException as e:
        cnn.insert_warning('pyStationInfoException while running pyPPPArchive: ' + str(e))

    except Exception:
        return traceback.format_exc() + ' processing: ' + NetworkCode + ' ' + StationCode + ' ' + str(year) + ' ' + str(doy) + ' using node ' + platform.node()


def output_handle(callback):

    messages = [outmsg.errors for outmsg in callback]

    if len([out_msg for out_msg in messages if out_msg]) > 0:
        tqdm.write(
            ' >> There were unhandled errors during this batch. Please check errors_pyScanArchive.log for details')

    # function to print any error that are encountered during parallel execution
    for msg in messages:
        if msg:
            f = open('errors_pyScanArchive.log','a')
            f.write('ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n')
            f.write(msg + '\n')
            f.write('END OF ERROR =================== \n\n')
            f.close()

    return []

def scan_rinex(cnn, JobServer, pyArchive, archive_path, Config, master_list):

    print " >> Analyzing the archive's structure..."
    archivefiles, path2rinex = pyArchive.scan_archive_struct(archive_path)

    print "   >> Beginning with the recursive search for CRINEX files..."
    if master_list:
        master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]
        print "   -- NOTE: the number of files reported in the progress bar might be larger than the processed list."

    pbar = tqdm(total=len(archivefiles), ncols=80)

    depfuncs = (verify_rinex_date_multiday, check_rinex_timespan_int)
    modules = ('dbConnection', 'pyDate', 'pyRinex', 'shutil', 'platform', 'datetime', 'traceback', 'pyOptions')

    callback = []
    for rinex, rinexpath in zip(archivefiles, path2rinex):

        valid, NetworkCode, StationCode, year, doy, _, _ = pyArchive.parse_archive_keys(rinex, key_filter=('network','station','year','doy'))

        if valid:

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

            # it was a valid archive entry, insert in database
            # print "About to execute "+rinexpath
            if not master_list or NetworkCode + '.' + StationCode in master_list:
                if Config.run_parallel:
                    arguments = (NetworkCode, StationCode, year, doy, rinexpath)

                    JobServer.SubmitJob(try_insert, arguments, depfuncs, modules, callback, callback_class(pbar), 'callbackfunc')

                    if JobServer.process_callback:
                        tqdm.write(' -- Done processing 300 jobs.')
                        # handle any output messages during this batch
                        callback = output_handle(callback)
                        JobServer.process_callback = False

                else:
                    callback.append(callback_class(pbar))
                    callback[0].callbackfunc(try_insert(NetworkCode, StationCode, year, doy, rinexpath))
                    callback = output_handle(callback)
            else:
                pbar.update(1)

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


def process_conflicts(cnn, pyArchive, archive_path, master_list):

    print " >> About to process RINEX conflicts..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    rs = cnn.query('SELECT * FROM rinex_extra WHERE "NetworkCode" || \'.\' || "StationCode" IN (\'' + '\',\''.join(master_list) + '\') ')
    records = rs.dictresult()

    for record in tqdm(records):
        crinexpath = pyArchive.build_rinex_path(record['NetworkCode'], record['StationCode'],
                                              record['ObservationYear'], record['ObservationDOY'])

        if crinexpath:
            # replace the rinex filename with the rinex_extra filename
            crinexpath = crinexpath.split('/')[:-1]
            crinexpath = os.path.join(os.path.join(archive_path, '/'.join(crinexpath)), record['Filename'][:-1] + 'd.Z')

            process_extra_rinex(record['NetworkCode'], record['StationCode'], record['ObservationYear'],
                                record['ObservationDOY'], crinexpath)

    return


def process_otl(cnn, JobServer, run_parallel, archive_path, brdc_path, sp3types, sp3altrn, master_list):

    print ""
    print " >> Calculating coordinates and OTL for new stations..."

    master_list = [item['NetworkCode'] + '.' + item['StationCode'] for item in master_list]

    rs = cnn.query('SELECT stations."NetworkCode", stations."StationCode", count(rinex."ObservationMonth") FROM stations '
                    'RIGHT JOIN rinex ON rinex."NetworkCode" = stations."NetworkCode" AND rinex."StationCode" = stations."StationCode" '
                    'WHERE auto_x is null OR auto_y is null OR auto_z is null OR "Harpos_coeff_otl" is null '
                    'AND stations."NetworkCode" || \'.\' || stations."StationCode" IN (\'' + '\',\''.join(master_list) + '\') '
                    'GROUP BY stations."NetworkCode", stations."StationCode"')

    records = rs.dictresult()

    pbar = tqdm(total=len(records), ncols=80)
    callback = []

    depfuncs = (ecef2lla,)
    modules = ('dbConnection', 'pyRinex', 'pyArchiveStruct', 'pyOTL', 'pyPPP', 'numpy', 'platform', 'pySp3', 'traceback', 'pyOptions')

    for record in records:
        NetworkCode = record['NetworkCode']
        StationCode = record['StationCode']

        if run_parallel:

            arguments = (NetworkCode, StationCode, archive_path, brdc_path, sp3types, sp3altrn)

            JobServer.SubmitJob(obtain_otl, arguments, depfuncs, modules, callback, callback_class(pbar), 'callbackfunc')

            if JobServer.process_callback:
                tqdm.write(' >> Done processing 300 jobs.')
                # handle any output messages during this batch
                callback = output_handle(callback)
                JobServer.process_callback = False

        else:
            callback.append(callback_class(pbar))
            callback[0].callbackfunc(obtain_otl(NetworkCode, StationCode, archive_path, brdc_path, sp3types, sp3altrn))
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

        valid, NetworkCode, StationCode, _, _, _, _ = pyArchive.parse_archive_keys(stninfofile, key_filter=('network','station'))

        if valid and NetworkCode + '.' + StationCode in master_list:
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
                         'LEFT JOIN rinex ON '
                         'ppp_soln."NetworkCode" = rinex."NetworkCode" AND '
                         'ppp_soln."StationCode" = rinex."StationCode" AND '
                         'ppp_soln."Year" = rinex."ObservationYear" AND '
                         'ppp_soln."DOY" = rinex."ObservationDOY" '
                         'WHERE ppp_soln."NetworkCode" || \'.\' || ppp_soln."StationCode" IN (\'' + '\',\''.join(master_list) + '\') '
                         'AND rinex."ObservationSTime" >= \'' + sdate.yyyymmdd() + '\' '
                         'AND rinex."ObservationETime" <= \'' + edate.yyyymmdd() + '\' '
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
    rs_rnx = cnn.query('SELECT rinex.* FROM rinex '
                       'LEFT JOIN ppp_soln ON '
                       'rinex."NetworkCode" = ppp_soln."NetworkCode" AND '
                       'rinex."StationCode" = ppp_soln."StationCode" AND '
                       'rinex."ObservationYear" = ppp_soln."Year" AND '
                       'rinex."ObservationDOY" = ppp_soln."DOY" '
                       'WHERE ppp_soln."NetworkCode" is null '
                       'AND rinex."NetworkCode" || \'.\' || rinex."StationCode" IN (\'' + '\',\''.join(master_list) + '\') '
                       'AND rinex."ObservationSTime" >= \'' + sdate.yyyymmdd() + '\' '
                       'AND rinex."ObservationETime" <= \'' + edate.yyyymmdd() + '\' '
                       'ORDER BY "ObservationSTime"')

    tblrinex = rs_rnx.dictresult()

    pbar = tqdm(total=len(tblrinex), ncols=80)

    modules = ('dbConnection', 'pyRinex', 'pyPPP', 'pyStationInfo', 'pyDate', 'pySp3', 'os', 'platform', 'pyArchiveStruct', 'traceback', 'pyOptions')
    depfuncs = (remove_from_archive,)

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

def print_columns(l):

    for a, b, c, d, e, f, g, h in zip(l[::8], l[1::8], l[2::8], l[3::8], l[4::8], l[5::8], l[6::8], l[7::8]):
        print('    {:<10}{:<10}{:<10}{:<10}{:<10}{:<10}{:<10}{:<}'.format(a, b, c, d, e, f, g, h))

    if len(l) % 8 != 0:
        sys.stdout.write('    ')
        for i in range(len(l) - len(l) % 8, len(l)):
            sys.stdout.write('{:<10}'.format(l[i]))
        sys.stdout.write('\n')


def process_date(arg):

    if '.' in arg:
        date = pyDate.Date(year=arg.split('.')[0], doy=arg.split('.')[1])
    else:
        date = pyDate.Date(year=arg.split('/')[0], month=arg.split('/')[1], day=arg.split('/')[2])

    return date


def main():

    parser = argparse.ArgumentParser(description='Archive operations Main Program')

    parser.add_argument('stnlist', type=str, nargs='+', metavar='all|net.stnm', help="List of networks/stations to process given in [net].[stnm] format or just [stnm] (separated by spaces; if [stnm] is not unique in the database, all stations with that name will be processed). Use keyword 'all' to process all stations in the database. If [net].all is given, all stations from network [net] will be processed. Alternatevily, a file with the station list can be provided.")
    parser.add_argument('-rinex', '--rinex', action='store_true', help="Scan the current archive for RINEX files (d.Z).")
    parser.add_argument('-rnxcft', '--rinex_conflicts', action='store_true', help="Resolve rinex conflicts (multiple files per day).")
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

    if args.rinex_conflicts:
        process_conflicts(cnn, pyArchive, Config.archive_path, stnlist)

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
        dates = [pyDate.Date(year=1980, doy=1), pyDate.Date(year=2100, doy=1)]

        if len(args.rehash) > 0:

            for i, arg in enumerate(args.ppp):
                try:
                    dates[i] = process_date(arg)
                except Exception as e:
                    parser.error('Error while reading the date start/end hash parameters: ' + str(e) + '\n' +  traceback.format_exc())

        hash_check(cnn, stnlist, dates[0], dates[1], rehash=True)

    #########################################

    if not args.ppp is None:
        # check other possible arguments
        dates = [pyDate.Date(year=1980, doy=1), pyDate.Date(year=2100, doy=1)]
        do_hash = False

        if len(args.ppp) > 0:

            for i, arg in enumerate(args.ppp):

                if not arg == 'hash':
                    try:
                        dates[i] = process_date(arg)
                    except Exception as e:
                        parser.error('Error while reading the date start/end hash parameters: ' + str(e) + '\n' +  traceback.format_exc())
                else:
                    do_hash = True
                    break

        if do_hash:
            hash_check(cnn, stnlist, dates[0], dates[1], rehash=False)

        process_ppp(cnn, pyArchive, Config.archive_path, JobServer, Config.run_parallel, stnlist, dates[0], dates[1])

    #########################################

    # remove the production dir
    #if os.path.isdir('production'):
    #    rmtree('production')

if __name__ == '__main__':

    main()