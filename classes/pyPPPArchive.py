"""
Project: Parallel.Archive
Date: 2/24/17 9:56 AM
Author: Demian D. Gomez
"""

import dbConnection
import ConfigParser
import pyRinex
import pyArchiveStruct
import pp
import sys
import pyPPP
import pyStationInfo
import pyDate
import pySp3
import os
from tqdm import tqdm
import datetime

def load_config(configfile):
    options = {'path'       : None,
               'parallel'   : False,
               'brdc'       : None,
               'sp3_type_1' : None,
               'sp3_type_2' : None,
               'sp3_type_3' : None,
               'grdtab'     : None,
               'otlgrid'    : None,
               'ppp_path'   : None,
               'institution': None,
               'info'       : None,
               'sp3'        : None,
               'atx'        : None,
               'ppp_exe'    : None}

    config = ConfigParser.ConfigParser()
    config.readfp(open(configfile))

    # get the archive config
    for iconfig, val in dict(config.items('archive')).iteritems():
        options[iconfig] = val

    # get the otl config
    for iconfig, val in dict(config.items('otl')).iteritems():
        options[iconfig] = val

    # get the ppp config
    for iconfig, val in dict(config.items('ppp')).iteritems():
        options[iconfig] = val

    sp3types = [options['sp3_type_1'], options['sp3_type_2'], options['sp3_type_3']]

    sp3types = [sp3type for sp3type in sp3types if sp3type is not None]

    return options, sp3types

def output_handle(messages):
    # function to print any error that are encountered during parallel execution
    for msg in messages:
        if msg:
            f = open('errors_pyPPPArchive.log','a')
            f.write('ON ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' an unhandled error occurred:\n')
            f.write(msg + '\n')
            f.write('END OF ERROR =================== \n\n')
            f.close()

def main():

    out_messages = []

    def callbackfunc(msg):
        out_messages.append(msg)

    options, sp3types = load_config("gnss_data.cfg")

    archive_path = options['path']

    if options['parallel'] == 'True':
        run_parallel = True
    else:
        run_parallel = False

    cnn = dbConnection.Cnn('gnss_data.cfg')

    pyArchive = pyArchiveStruct.RinexStruct(cnn)

    #################################

    if run_parallel:
        ppservers = ('*',)
        job_server = pp.Server(ppservers=ppservers)

        print "Starting pp with", job_server.get_active_nodes(), "workers"

    #########################################
    #########################################

    # for each rinex in the db, run PPP and get a coordinate
    rs_rnx = cnn.query('SELECT * FROM rinex ORDER BY "ObservationSTime"')
    tblrinex = rs_rnx.dictresult()

    submit = 0
    for record in tqdm(tblrinex):

        rinex_path = pyArchive.build_rinex_path(record.get('NetworkCode'),      record.get('StationCode'),
                                                record.get('ObservationYear'),  record.get('ObservationDOY'))

        # add the base dir
        rinex_path = os.path.join(archive_path, rinex_path)

        if run_parallel:
            submit += 1

            job_server.submit(execute_ppp, args=(record.get('NetworkCode'),     record.get('StationCode'),
                                                 record.get('ObservationYear'), record.get('ObservationDOY'),
                                                 rinex_path, options, sp3types),
                                            modules=('dbConnection', 'pyRinex', 'pyPPP', 'pyStationInfo', 'pyDate', 'pySp3', 'os'),
                                            callback=callbackfunc)

            if submit > 300:
                # when we submit more than 300 jobs, wait until this batch is complete
                job_server.wait()
                # handle any output messages during this batch
                output_handle(out_messages)
                out_messages = []
                submit = 0

        else:
            output_handle(execute_ppp(record.get('NetworkCode'),     record.get('StationCode'),
                                      record.get('ObservationYear'), record.get('ObservationDOY'),
                                      rinex_path, options, sp3types))

    if run_parallel:
        job_server.wait()
        job_server.print_stats()

    # handle any output messages during this batch
    output_handle(out_messages)

def execute_ppp(NetworkCode, StationCode, year, doy, rinex_path, options, sp3types):

    import traceback

    def insert_warning(desc):
        # do not insert if record exists
        desc = desc.replace('\'', '')
        warn = cnn.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        if warn.ntuples() == 0:
            cnn.insert('events',EventType='warn',EventDescription=desc)

    def insert_error(desc):
        # do not insert if record exists
        desc = desc.replace('\'', '')
        err = cnn.query('SELECT * FROM events WHERE "EventDescription" = \'%s\'' % (desc))

        if err.ntuples() == 0:
            cnn.insert('events',EventType='error',EventDescription=desc)

    # create a temp folder in production to put the orbit in
    # we need to check the RF of the orbit to see if we have this solution in the DB
    try:
        cnn = dbConnection.Cnn('gnss_data.cfg')

        rootdir = 'production/' + NetworkCode + '/' + StationCode

        try:
            if not os.path.exists(rootdir):
                os.makedirs(rootdir)
        except OSError as e:
            # folder exists from a concurring instance, ignore the error
            sys.exc_clear()
        except:
            raise

        date = pyDate.Date(year=year,doy=doy)
        orbit = pySp3.GetSp3Orbits(options['sp3'], date, sp3types, rootdir)

        # check to see if record exists for this file in ppp_soln
        ppp_soln = cnn.query('SELECT * FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                             '"Year" = %s AND "DOY" = %s AND "ReferenceFrame" = \'%s\''
                             % (NetworkCode, StationCode, year, doy, orbit.RF))

        if ppp_soln.ntuples() == 0:

            # load the stations record to get the OTL params
            rs_stn = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (
                                NetworkCode, StationCode))
            stn = rs_stn.dictresult()

            # RINEX FILE TO BE PROCESSED
            Rinex = pyRinex.ReadRinex(NetworkCode, StationCode, rinex_path)

            stninfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode, Rinex.date)

            Rinex.normalize_header(StationInfo=stninfo, x=stn[0].get('auto_x'), y=stn[0].get('auto_y'), z=stn[0].get('auto_z'))

            ppp = pyPPP.RunPPP(Rinex,stn[0].get('Harpos_coeff_otl'), options, sp3types, stninfo.AntennaHeight)

            # insert record in DB
            cnn.insert('ppp_soln',
                       NetworkCode    = NetworkCode,
                       StationCode    = StationCode,
                       X              = ppp.x,
                       Y              = ppp.y,
                       Z              = ppp.z,
                       Year           = year,
                       DOY            = doy,
                       ReferenceFrame = ppp.frame,
                       sigmax         = ppp.sigmax,
                       sigmay         = ppp.sigmay,
                       sigmaz         = ppp.sigmaz,
                       sigmaxy        = ppp.sigmaxy,
                       sigmaxz        = ppp.sigmaxz,
                       sigmayz        = ppp.sigmayz)

    except pyPPP.pyRunPPPException as e:
        insert_warning('Error in PPP while processing: ' + NetworkCode + ' ' + StationCode + ' ' + str(year) + ' ' + str(doy) + ': \n' + str(e))
    except pyStationInfo.pyStationInfoException as e:
        insert_warning('pyStationInfoException while running pyPPPArchive: ' + str(e))
    except:
        return traceback.format_exc() + ' processing: ' + NetworkCode + ' ' + StationCode + ' ' + str(year) + ' ' + str(doy)


if __name__ == '__main__':

    main()