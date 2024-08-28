#!/usr/bin/env python

"""
Project:
Date: 10/27/17 12:40 PM
Author: Demian D. Gomez
"""

import os
import traceback
import platform
import datetime

# deps
from tqdm import tqdm

# app
import dbConnection
import pyOptions
import pyArchiveStruct
import pyRinex
import pyDate
import pyJobServer
from Utils import file_append

class callback_class():
    def __init__(self, pbar):
        self.errors = None
        self.pbar   = pbar

    def callbackfunc(self, args):
        msg = args
        self.errors = msg
        self.pbar.update(1)


def verify_rinex_date_multiday(date, rinexinfo, Config):
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
            retry_folder = os.path.join(Config.repository_data_in_retry, 'multidays_found/%s/%s' % (rnx.date.yyyy(), rnx.date.ddd()))
            rnx.compress_local_copyto(retry_folder)

        # remove crinex from archive
        os.remove(rinexinfo.origin_file)

        return False

    # compare the date of the rinex with the date in the archive
    elif not date == rinexinfo.date:
        # move the file out of the archive because it's in the wrong spot (wrong folder, wrong name, etc)
        # let pyArchiveService fix the issue
        retry_folder = os.path.join(Config.repository_data_in_retry, 'wrong_date_found/%s/%s' % (date.yyyy(), date.ddd()))
        # move the crinex out of the archive
        rinexinfo.move_origin_file(retry_folder)

        return False

    else:
        return True


def UpdateRecord(rinex, path):

    cnn = dbConnection.Cnn('gnss_data.cfg')
    Config = pyOptions.ReadOptions('gnss_data.cfg')

    try:
        rnxobj = pyRinex.ReadRinex(rinex['NetworkCode'],
                                   rinex['StationCode'],
                                   path)

        date = pyDate.Date(year = rinex['ObservationYear'],
                           doy  = rinex['ObservationDOY'])

        if not verify_rinex_date_multiday(date, rnxobj, Config):
            cnn.begin_transac()
            # propagate the deletes
            cnn.query(
                'DELETE FROM gamit_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                % (rinex['NetworkCode'], rinex['StationCode'], rinex['ObservationYear'], rinex['ObservationDOY']))
            cnn.query(
                'DELETE FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %i AND "DOY" = %i'
                % (rinex['NetworkCode'], rinex['StationCode'], rinex['ObservationYear'], rinex['ObservationDOY']))
            cnn.query(
                'DELETE FROM rinex WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "ObservationYear" = %i AND "ObservationDOY" = %i'
                % (rinex['NetworkCode'], rinex['StationCode'], rinex['ObservationYear'], rinex['ObservationDOY']))
            cnn.commit_transac()

            return 'Multiday rinex file moved out of the archive: ' + rinex['NetworkCode'] + '.' + rinex['StationCode'] + ' ' + str(rinex['ObservationYear']) + ' ' + str(rinex['ObservationDOY']) + ' using node ' + platform.node()
        else:
            cnn.update('rinex', rinex, Completion=rnxobj.completion)

    except pyRinex.pyRinexExceptionBadFile:
        # empty file or problem with crinex format, move out
        archive = pyArchiveStruct.RinexStruct(cnn)
        archive.remove_rinex(rinex, os.path.join(Config.repository_data_reject, 'bad_rinex/%i/%03i' % (rinex['ObservationYear'], rinex['ObservationDOY'])))

    except Exception:
        return traceback.format_exc() + ' processing rinex: ' + rinex['NetworkCode'] + '.' + rinex['StationCode'] + ' ' + str(rinex['ObservationYear']) + ' ' + str(rinex['ObservationDOY']) + ' using node ' + platform.node()


def output_handle(callback):

    messages = [outmsg.errors for outmsg in callback]

    if len([out_msg for out_msg in messages if out_msg]) > 0:
        tqdm.write(
            ' >> There were unhandled errors during this batch. Please check errors_pyScanArchive.log for details')

    # function to print any error that are encountered during parallel execution
    for msg in messages:
        if msg:
            file_append('errors_amend.log',
                        'ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n' +
                        msg + '\n' +
                        'END OF ERROR =================== \n\n')
    return []

cnn     = dbConnection.Cnn('gnss_data.cfg')
options = pyOptions.ReadOptions('gnss_data.cfg')

JobServer = pyJobServer.JobServer(options)
archive   = pyArchiveStruct.RinexStruct(cnn)

for table in ['rinex']:

    print(" >> Processing " + table)

    tbl = cnn.query('SELECT * FROM ' + table + ' WHERE "Completion" is null')

    rnx = tbl.dictresult()

    callback = []
    pbar     = tqdm(total=len(rnx), ncols=80)

    depfuncs = (verify_rinex_date_multiday,)
    modules  = ('pyRinex', 'dbConnection', 'traceback', 'platform', 'pyDate', 'pyOptions', 'pyArchiveStruct')

    for rinex in rnx:
        path = archive.build_rinex_path(rinex['NetworkCode'],
                                        rinex['StationCode'],
                                        rinex['ObservationYear'],
                                        rinex['ObservationDOY'])

        rfile = os.path.join(options.archive_path, path)

        callback.append(callback_class(pbar))

        arguments = (rinex, rfile)

        JobServer.SubmitJob(UpdateRecord, arguments, depfuncs, modules, callback, callback_class(pbar), 'callbackfunc')

        if JobServer.process_callback:
            # handle any output messages during this batch
            callback = output_handle(callback)
            JobServer.process_callback = False


    tqdm.write(' >> waiting for jobs to finish...')
    JobServer.job_server.wait()
    tqdm.write(' >> Done.')
    pbar.close()
    output_handle(callback)


print('\n')
JobServer.job_server.print_stats()
