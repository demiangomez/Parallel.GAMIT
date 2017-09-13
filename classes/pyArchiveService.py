"""
Project: Parallel.Archive
Date: 3/19/17 11:41 AM
Author: Demian D. Gomez

Main script that scans the repository for new rinex files.
It PPPs the rinex files and searches the database for stations (within 100 m) with the same station 4 letter code.
If the station exists in the db, it moves the file to the archive and adds the new file to the "rinex" table.
if the station doesn't exist, then it incorporates the station with a special NetworkCode (???) and leaves the file in the repo until you assign the correct NetworkCode and add the station information.

It is invoked jusy by calling python pyArchiveService.py
Requires the config file gnss_data.cfg (in the running folder)

"""

import pyRinex
import dbConnection
import pyStationInfo
import pyArchiveStruct
import pyPPP
import pyBrdc
import sys
import os
import pp
import pyOptions
import Utils
import pyOTL
import shutil
import datetime
import time
import uuid
import pySp3
from tqdm import tqdm
import traceback
import platform

# class to handle the output of the parallel processing
class callback_class():
    def __init__(self, pbar):
        self.errors = None
        self.stns = None
        self.pbar = pbar

    def callbackfunc(self, args):
        msg = args[0]
        new_stn = args[1]
        self.errors = msg
        self.stns = new_stn
        self.pbar.update(1)


def check_rinex_timespan_int(rinex, stn):

    # how many seconds difference between the rinex file and the record in the db
    stime_diff = abs((stn['ObservationSTime'] - rinex.datetime_firstObs).total_seconds())
    etime_diff = abs((stn['ObservationETime'] - rinex.datetime_lastObs).total_seconds())

    # at least four minutes different on each side
    if stime_diff <= 240 and etime_diff <= 240 and stn['Interval'] == rinex.interval:
        return False
    else:
        return True

def write_error(folder, filename, msg):

    # do append just in case...
    count = 0
    while True:
        try:
            file = open(os.path.join(folder,filename),'a')
            file.write(msg)
            file.close()
            break
        except IOError as e:
            if count < 3:
                count += 1
            else:
                raise IOError(str(e) + ' after 3 retries')
            continue
        except:
            raise

    return


def error_handle(cnn, message, crinex, folder, filename, no_db_log=False):

    # rollback any active transactions
    if cnn.active_transaction:
        cnn.rollback_transac()

    # move to the folder indicated
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    except OSError:
        # racing condition of two processes trying to create the same folder
        pass
    except:
        raise

    try:
        index = 1
        # if the parent process could not read the name of the station, year and doy, then it created a uuid folder
        # in that case, it will not try to parse the filename since it will be the only file in the folder
        while os.path.isfile(os.path.join(folder, filename)):
            filename_parts = filename.split('.')
            filename = filename_parts[0][0:-1] + str(index) + '.' + filename_parts[1] + '.' + filename_parts[2]
            index += 1

        shutil.move(crinex, os.path.join(folder, filename))
    except Exception as e:
        message = 'could not move file into this folder!' + str(e) + '\n' + message

    error_file = filename.replace('d.Z','.log')
    write_error(folder, error_file, message)

    if not no_db_log:
        cnn.insert_warning(message)

    return

def insert_data(Config, cnn, StationCode, rs_stn, rinexinfo, year, doy, retry_folder):

    # does the name of the file agree with the StationCode found in the database?
    # also, check the doy and year
    filename = rinexinfo.crinex
    if StationCode != rs_stn['StationCode'] or int(rinexinfo.date.year) != int(year) or int(rinexinfo.date.doy) != int(doy):
        # this if still remains here but we do not allow this condition any more to happen. See process_crinex_file -> if Result...
        # NO! rename the file before moving to the archive
        filename = rs_stn['StationCode'] + rinexinfo.date.ddd() + '0.' + rinexinfo.date.yyyy()[2:4] + 'd.Z'

    #try:
    # must rename filename to assign the correct network to the rinex record
    rinexinfo.rename_crinex_rinex(filename, rs_stn['NetworkCode'], rs_stn['StationCode'])

    # get the path to access the archive
    Archive = pyArchiveStruct.RinexStruct(cnn)

    # is this day already in the database?
    rsdoy = cnn.query('SELECT * FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i' % (rs_stn['NetworkCode'], rs_stn['StationCode'], int(rinexinfo.date.year), int(rinexinfo.date.doy)))

    rnx = rsdoy.dictresult()

    if rsdoy.ntuples() == 0:
        # this is a new day that wasn't previously in the db
        # not need to check date of multiday: done in parent function

        # possible racing condition: if the same file is in two different folders, there might be a racing condition of two processes
        # trying to make the same insert at the same time.
        # this error is handled by the parent function.

        cnn.begin_transac()
        cnn.insert('rinex', rinexinfo.record)

        # move the crinex to the archive
        # first check that all the structure exists. This might be the first file of a new station
        path2archive = os.path.join(Config.options['path'], Archive.build_rinex_path(rs_stn['NetworkCode'], rs_stn['StationCode'], rinexinfo.date.year, rinexinfo.date.doy, False))

        # again, the "archive" for this rinexinfo object is the repository
        rinexinfo.move_origin_file(path2archive)

        cnn.insert_info('New data was found and added to the archive: %s.%s for %s' % (rs_stn['NetworkCode'], rs_stn['StationCode'], rinexinfo.date.yyyyddd()))

        cnn.commit_transac()

        # this file is ready to be processed by pyScanArchive -ppp
    else:

        # before inserting a rinex_extra, verify the time span
        if not check_rinex_timespan_int(rinexinfo, rnx[0]):
            # this is the same file in the db (maybe with different sampling interval)
            # or has less observations than the present file
            # delete it from data_in and don't insert it in the database
            os.remove(rinexinfo.origin_file)
            return

        # there is a file in the db already. Add it to the rinex_extra table for later time span check (first check passed: new > current)
        # the time span check cannot be done here because we could be checking in parallel and there isn't a unique answer when more than 2 files
        cnn.begin_transac()

        path2archive = os.path.join(Config.options['path'],
                                    Archive.build_rinex_path(rs_stn['NetworkCode'], rs_stn['StationCode'],
                                                             rinexinfo.date.year, rinexinfo.date.doy, False))

        Archive.check_directory_struct(Config.options['path'], rs_stn['NetworkCode'], rs_stn['StationCode'], rinexinfo.date)

        # renaming of the file is taken care by move_origin_file
        rinexinfo.move_origin_file(path2archive)

        cnn.insert('rinex_extra', rinexinfo.record)

        cnn.insert_info(
            'More data for %s was found and added to rinex_extra for %s.%s' % (rinexinfo.date.yyyyddd(), rs_stn['NetworkCode'], rs_stn['StationCode']))

        cnn.commit_transac()
        # these cases can be solved by running pyScanArhive -rinex (resolve conflicts)
    #except:
    #    error_handle(cnn, 'An unexpected error ocurred while inserting a record for ' + rinexinfo.crinex_path + ' : (file moved to retry folder)\n' + traceback.format_exc(), rinexinfo.crinex_path, retry_folder, filename)


def verify_rinex_multiday(cnn, rinexinfo, Config):
    # function to verify if rinex is multiday
    # returns true if parent process can continue with insert
    # returns false if file had to be moved to the retry

    # check if rinex is a multiday file (rinex with more than one day of observations)
    if rinexinfo.multiday:

        # move all the files to the repository, delete the crinex from the archive, log the event
        rnxlist = []
        for rnx in rinexinfo.multiday_rnx_list:
            rnxlist.append(rnx.rinex)
            # some other file, move it to the repository
            retry_folder = os.path.join(Config.repository_data_in_retry, rnx.date.yyyy() + '/' + rnx.date.ddd())
            rnx.compress_local_copyto(retry_folder)

        # if the file corresponding to this session is found, assign its object to rinexinfo
        cnn.insert_info('%s was a multi-day rinex file. The following rinex files where generated and moved to the repository/data_in_retry: %s. The file %s  did not enter the database at this time.' % (
            rinexinfo.origin_file, ','.join(rnxlist), rinexinfo.crinex))
        # remove crinex from the repository (origin_file points to the repository, not to the archive in this case)
        os.remove(rinexinfo.origin_file)

        return False

    return True

def process_crinex_file(crinex, filename, data_rejected, data_retry, Config):

    # create a uuid temporary folder in case we cannot read the year and doy from the file (and gets rejected)
    reject_folder = os.path.join(data_rejected, str(uuid.uuid4()))

    try:
        cnn = dbConnection.Cnn("gnss_data.cfg")
    except:
        return (traceback.format_exc() + ' open de database when processing file ' + crinex, None)

    # assume a default networkcode
    NetworkCode = 'rnx'
    # get the station code year and doy from the filename
    try:
        StationCode = crinex.split('/')[-1][0:4].lower()
        year = int(Utils.get_norm_year_str(int(crinex.split('/')[-1][9:11])))
        doy = int(crinex.split('/')[-1][4:7])
    except:
        error = traceback.format_exc() + ' could not read the station code, year or doy for file ' + crinex
        error_handle(cnn, error,crinex,reject_folder,filename,True)
        return (error, None)

    # we can now make better reject and retry folders
    reject_folder = os.path.join(data_rejected, Utils.get_norm_year_str(year) + '/' + Utils.get_norm_doy_str(doy))
    retry_folder = os.path.join(data_retry, Utils.get_norm_year_str(year) + '/' + Utils.get_norm_doy_str(doy))

    try:
        # main try except block
        rinexinfo = pyRinex.ReadRinex(NetworkCode, StationCode, crinex) # type: pyRinex.ReadRinex

        # STOP! see if rinexinfo is a multiday rinex file
        if not verify_rinex_multiday(cnn, rinexinfo, Config):
            # was a multiday rinex. verify_rinex_date_multiday took care of it
            return (None, None)

        # DDG: we don't use otl coefficients because we need an approximated coordinate
        # we therefore just calculate the first coordinate without otl
        # NOTICE that we have to trust the information coming in the RINEX header (receiver type, antenna type, etc)
        # we don't have station info data! Still, good enough
        # the final PPP coordinate will be calculated by pyScanArchive on a different process

        ppp = pyPPP.RunPPP(rinexinfo, '', Config.options, Config.sp3types, Config.sp3altrn, rinexinfo.antOffset, False, False) # type: pyPPP.RunPPP

        try:
            ppp.exec_ppp()

        except pyPPP.pyRunPPPException as e:
            # ppp didn't work, try using sh_rx2apr
            brdc = pyBrdc.GetBrdcOrbits(Config.brdc_path, rinexinfo.date, rinexinfo.rootdir)

            _, auto_coords = rinexinfo.auto_coord(brdc)

            if auto_coords:
                ppp.lat = auto_coords[0]
                ppp.lon = auto_coords[1]
                ppp.h   = auto_coords[2]
            else:
                raise pyPPP.pyRunPPPException('Both PPP and sh_rx2apr failed to obtain a coordinate for ' + crinex +
                                              '.\nThe file has been moved into the rejection folder. '
                                              'Summary PPP file (if exists) follows:\n' + ppp.summary)

        # check for unreasonable heights
        if ppp.h[0] > 9000 or ppp.h[0] < -400:
            # elevation cannot be higher or lower than the tallest and lowest point on the Earth
            error_handle(cnn, crinex + ' : unreasonable geodetic height (%.3f). RINEX file will not enter the archive.' % (ppp.h[0]), crinex, reject_folder, filename)
            return (None, None)

        Result, match, closest_stn = ppp.verify_spatial_coherence(cnn, StationCode)

        if Result:
            if match['StationCode'] == StationCode:
                # no further verification need because we don't know anything about the network code
                # even if the station code is wrong, if result is True we insert (there is only 1 match)
                insert_data(Config, cnn, StationCode, match, rinexinfo, year, doy, retry_folder)
            else:
                error = \
                """
                %s was found to match %s.%s but the name of the file indicates it is actually from station %s.
                Please verify that %s belongs to %s.%s, rename it and try again. The file was moved to the retry folder.
                """ % (crinex, match['NetworkCode'], match['StationCode'],StationCode, crinex, match['NetworkCode'], match['StationCode'])

                error_handle(cnn, error, crinex, retry_folder, filename)

        else:
            # a number of things could have happened:
            # 1) wrong station code and more than one solution (that do not match the station code, of course)
            #    see rms.lhcl 2007 113 -> matches rms.igm0: 34.293 m, rms.igm1: 40.604 m, rms.byns: 4.819 m
            # 2) no entry in the database for this solution -> add a lock and populate the exit args

            if len(match) > 0:
                # no match, but we have some candidates
                matches = ', '.join(['%s.%s: %.3f m' % (m['NetworkCode'], m['StationCode'], m['distance']) for m in match])

                error = 'Solution for rinex in repository (%s %s) did not match a station code or a unique station location within 5 km. Possible cantidate(s): %s. This file has been moved to data_in_rejected' % (crinex, rinexinfo.date.yyyyddd(), matches)

                error_handle(cnn, error, crinex, reject_folder, filename)

                return (None, None)

            else:
                # only found a station removing the distance limit (could be thousands of km away!)

                # The user will have to add the metadata to the database before the file can be added, but in principle
                # no problem was detected by the process. This file will stay in this folder so that it gets analyzed again
                # but a "lock" will be added to the file that will have to be removed before the service analyzes again.
                # if the user inserted the station by then, it will get moved to the appropriate place.
                # we return all the relevant metadata to ease the insert of the station in the database

                otl = pyOTL.OceanLoading(StationCode, Config.options['grdtab'], Config.options['otlgrid'])
                # use the ppp coordinates to calculate the otl
                coeff = otl.calculate_otl_coeff(x=ppp.x, y=ppp.y, z=ppp.z)

                # add the file to the locks table so that it doesn't get processed over and over
                # this will be removed by user so that the file gets reprocessed once all the metadata is ready
                cnn.insert('locks',filename=crinex)

                # return a string with the relevant information to insert into the database (NetworkCode = default (rnx))
                return (None, [StationCode, (ppp.x, ppp.y, ppp.z), coeff, (ppp.lat[0], ppp.lon[0], ppp.h[0]), crinex])


    except pyRinex.pyRinexException as e:
        # error, move the file to rejected folder
        error_handle(cnn, crinex + ' : (file moved to rejected folder)\n' + str(e), crinex, reject_folder, filename)

        return (None, None)

    except pyPPP.pyRunPPPException as e:

        #msg = 'Error in PPP while processing: ' + crinex + ' : \n' + str(e) + '\nThe file has been moved into the rejection folder. Summary PPP file (if exists) follows:\n' + ppp.summary
        error_handle(cnn, str(e), crinex, reject_folder, filename)

        return (None, None)

    except pyStationInfo.pyStationInfoException as e:

        msg = 'pyStationInfoException: ' + str(e) + '. The file will stay in the repository and processed during the next cycle, but further information will be logged.'
        error_handle(cnn, msg, crinex, retry_folder, filename)

        return (None, None)

    except pyOTL.pyOTLException as e:

        msg = "Error while calculating OTL for " + crinex + ": " + str(e) + '. The file has been moved into the retry folder.'
        error_handle(cnn, msg, crinex, retry_folder, filename)

        return (None, None)

    except pySp3.pySp3Exception as e:
        # DDG: changed from rejected to retry because the logic was rejecting files when no orbit file was found
        # it should move the files to the retry folder, not to the rejected
        # another case is when the date is crewed up and there are negative or non-reasonable values for gps week
        # should split the pySp3Exception into "file not found" and "unreasonable gps week
        msg = "Error while obtaining orbit for " + crinex + ": " + str(e) + '\nThe file has been moved into the retry folder. Most likely bad rinex header/data. Rinex header follows:\n%s' % (''.join(rinexinfo.get_header()))
        error_handle(cnn, msg, crinex, retry_folder, filename)

        return (None, None)

    except dbConnection.dbErrInsert as e:
        # insert duplicate values: two parallel processes tried to insert different filenames (or the same) of the same station
        # to the db: move it to the rejected folder. The user might want to retry later. Log it in events
        # this case should be very rare

        error_handle(cnn, crinex + ' : (file moved to rejected folder)' + str(e), crinex, reject_folder, filename)

        return (None, None)

    except:

        error = traceback.format_exc() + ' processing: ' + crinex + ' in node ' + platform.node() + ' (file moved to retry folder)'
        error_handle(cnn, error, crinex, retry_folder, filename, no_db_log=True)

        return (error, None)

    return (None, None)

def insert_station_w_lock(cnn, StationCode, filename, lat, lon, h, x, y, z, otl):

    rs = cnn.query("""
                    SELECT * FROM
                        (SELECT *, 2*asin(sqrt(sin((radians(%.8f)-radians(lat))/2)^2 + cos(radians(lat)) * cos(radians(%.8f)) * sin((radians(%.8f)-radians(lon))/2)^2))*6371000 AS distance
                            FROM stations WHERE "NetworkCode" like \'?%%\' AND "StationCode" = \'%s\') as DD
                        WHERE distance <= 100
                    """ % (lat, lat, lon, StationCode))

    if not rs.ntuples() == 0:
        NetworkCode = rs.dictresult()[0]['NetworkCode']
        # if it's a record that was found, update the locks with the station code
        cnn.update('locks', {'filename': filename}, NetworkCode=NetworkCode, StationCode=StationCode)
    else:
        # insert this new record in the stations table using a default network name (???)
        # this network name is a flag that tells the ArchiveService that no data should be added to this station
        # until a proper networkname is assigned.

        # check if network code exists
        NetworkCode = '???'
        index = 0
        while cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode)).ntuples() != 0:
            NetworkCode = hex(index).replace('0x','').rjust(3, '?')
            index += 1
            if index > 255:
                # FATAL ERROR! the networkCode exceed 99
                raise Exception(
                    'While looking for a temporary network code, ?ff was reached! Cannot continue executing pyArchiveService. Please free some temporary network codes.')

        rs = cnn.query('SELECT * FROM networks WHERE "NetworkCode" = \'%s\'' % (NetworkCode))

        cnn.begin_transac()
        if rs.ntuples() == 0:
            # create network code
            cnn.insert('networks', NetworkCode=NetworkCode, NetworkName='Temporary network for new stations')

        # insert record in stations with temporary NetworkCode
        try:
            cnn.insert('stations', NetworkCode=NetworkCode,
                       StationCode=StationCode,
                       auto_x=x,
                       auto_y=y,
                       auto_z=z,
                       Harpos_coeff_otl=otl,
                       lat=round(lat, 8),
                       lon=round(lon, 8),
                       height=round(h, 3))
        except dbConnection.dbErrInsert:
            # another process did the insert before, ignore the error
            pass
        except:
            raise

        # update the lock information for this station
        cnn.update('locks', {'filename': filename}, NetworkCode=NetworkCode, StationCode=StationCode)
        cnn.commit_transac()

def output_handle(cnn, callback):

    out_messages = [outmsg.errors for outmsg in callback]
    new_stations = [outmsg.stns for outmsg in callback]

    if len([out_msg for out_msg in out_messages if out_msg]) > 0:
        tqdm.write(
            ' >> There were unhandled errors during this batch. Please check errors_pyArchiveService.log for details')
    if len([out_msg for out_msg in new_stations if out_msg]) > 0:
        tqdm.write(
            ' >> New stations were found in the repository. Please assign a network to them, remove the locks from the files and run again pyArchiveService')

    # function to print any error that are encountered during parallel execution
    for msg in out_messages:
        if msg:
            f = open('errors_pyArchiveService.log','a')
            f.write('ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n')
            f.write(msg + '\n')
            f.write('END OF ERROR =================== \n\n')
            f.close()

    for nstn in new_stations:
        if nstn:
            # check the distance w.r.t the current new stations

            StationCode = nstn[0]
            x   = nstn[1][0]
            y   = nstn[1][1]
            z   = nstn[1][2]
            otl = nstn[2]
            lat = nstn[3][0]
            lon = nstn[3][1]
            h   = nstn[3][2]

            filename = nstn[4]


            # logic behind this sql sentence:
            # we are searching for a station within 100 meters that has been recently added, so NetworkCode = ???
            # we also force the StationName to be equal to that of the incoming RINEX to avoid having problems with
            # stations that are within 100 m (misidentifying IGM1 for IGM0, for example).
            # This logic assumes that stations within 100 m do not have the same name!
            insert_station_w_lock(cnn,StationCode,filename,lat,lon,h,x,y,z,otl)

    return []

def print_help():
    print "  usage: "
    print "  pyArchiveService : scan for rinex file in [repo directory]/data_in"
    print "    The repository should have the following folders (created if they don't exist):"
    print "    - data_in      : a folder to put incoming data (in any structure)."
    print "    - data_in_retry: that has some failure and that was moved out of the directory to allow the used to identify problems"
    print "                     will be moved back into data_in when the program is restarted."
    print "    - data_reject  : rejected data due to not having been able to run ppp on it."

def remove_empty_folders(folder):

    for dirpath, _, files in os.walk(folder, topdown=False):  # Listing the files
        for file in files:
            if file.endswith('DS_Store'):
                # delete the stupid mac files
                try:
                    os.remove(os.path.join(dirpath, file))
                except:
                    sys.exc_clear()
        if dirpath == folder:
            break
        try:
            os.rmdir(dirpath)
        except OSError:
            sys.exc_clear()

    return

def main(argv):

    # bind to the repository directory

    Config = pyOptions.ReadOptions('gnss_data.cfg')
    cnn = dbConnection.Cnn('gnss_data.cfg')

    if not os.path.isdir(Config.repository):
        print "the provided argument is not a folder"
        print_help()
        exit()

    if Config.run_parallel:
        ppservers = ('*',)
        job_server = pp.Server(ncpus=Utils.get_processor_count(), ppservers=ppservers)
        time.sleep(3)
        print "Starting pp with", job_server.get_active_nodes(), "workers"
    else:
        job_server = None

    # set the data_xx directories
    data_in = os.path.join(Config.repository,'data_in')
    data_in_retry = os.path.join(Config.repository, 'data_in_retry')
    data_reject = os.path.join(Config.repository, 'data_rejected')

    # if if the subdirs exist
    if not os.path.isdir(data_in):
        os.makedirs(data_in)

    if not os.path.isdir(data_in_retry):
        os.makedirs(data_in_retry)

    if not os.path.isdir(data_reject):
        os.makedirs(data_reject)

    # look for data in the data_in_retry and move it to data_in
    for path, dirs, files in os.walk(data_in_retry):
        for file in files:
            if file.endswith("d.Z") and file[0:2] != '._':
                file_to_process = os.path.join(path, file)
                # create a folder in data_in
                uid_folder = os.path.join(data_in, path.replace(data_in_retry + '/','').replace('/' + file,''))
                if not os.path.isdir(uid_folder):
                    os.makedirs(uid_folder)
                # move the file into the folder
                shutil.move(file_to_process,os.path.join(uid_folder, file))
                # remove folder from data_in_retry (also removes the log file)
                try:
                    # remove the log file that accompanies this Z file
                    os.remove(file_to_process.replace('d.Z','.log'))
                except:
                    sys.exc_clear()

            if file.endswith('DS_Store') or file[0:2] == '._':
                # delete the stupid mac files
                try:
                    os.remove(os.path.join(path, file))
                except:
                    sys.exc_clear()

    remove_empty_folders(data_in_retry)

    time.sleep(5)

    # delete any locks with a NetworkCode != '?%'
    cnn.query('delete from locks where "NetworkCode" not like \'?%\'')
    # get the locks to avoid reprocessing files that had no metadata in the database
    locks = cnn.query('SELECT * FROM locks')
    locks = locks.dictresult()

    submit = 0
    files_path = []
    files_list = []
    tqdm.write("\n >> " +  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ": Starting repository recursion walk...")

    for path, dirs, files in os.walk(data_in):
        for file in files:
            if file.endswith("d.Z"):
                # send this file to process
                file_to_process = os.path.join(path, file)

                if file_to_process not in [lock['filename'] for lock in locks]:
                    files_path.append(file_to_process)
                    files_list.append(file)

    tqdm.write("Found %i files in the lock list..." % (len(locks)))
    tqdm.write("Found %i files to process..." % (len(files_list)))

    pbar = tqdm(total=len(files_path),ncols=80)
    callback = []
    for file_to_process, file in zip(files_path,files_list):

        if Config.run_parallel:
            callback.append(callback_class(pbar))
            job_server.submit(process_crinex_file,(file_to_process, file, data_reject, data_in_retry, Config),
                              depfuncs=(check_rinex_timespan_int,write_error,error_handle,insert_data,verify_rinex_multiday),
                              modules=('pyRinex','pyArchiveStruct','pyOTL','pyPPP','pyStationInfo','dbConnection','Utils','shutil','os','uuid','datetime','pyDate','numpy','pySp3','traceback','platform','pyBrdc'),
                              callback=callback[submit].callbackfunc)

            submit += 1

            if submit >= 300:
                # when we submit more than 300 jobs, wait until this batch is complete
                # print " >> Batch of 300 jobs sent to the queue. Waiting until complete..."
                tqdm.write(' >> waiting for jobs to finish...')
                job_server.wait()
                tqdm.write(' >> Done.')
                # handle any output messages during this batch
                callback = output_handle(cnn, callback)
                submit = 0
        else:
            callback.append(callback_class(pbar))
            callback[0].callbackfunc(process_crinex_file(file_to_process, file, data_reject, data_in_retry, Config))
            callback = output_handle(cnn, callback)

    # once we finnish walking the dir, wait and, handle the output messages
    if Config.run_parallel:
        tqdm.write(' >> waiting for jobs to finish...')
        job_server.wait()
        tqdm.write(' >> Done.')

    # process the errors and the new stations
    output_handle(cnn, callback)

    pbar.close()

    # iterate to delete empty folders
    remove_empty_folders(data_in)

if __name__ == '__main__':

    main(sys.argv[1:])
