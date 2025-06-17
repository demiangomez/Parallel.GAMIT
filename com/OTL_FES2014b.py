#!/usr/bin/env python

"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Ocean loading coefficients class. It runs and reads grdtab (from GAMIT).

Subject: Ocean Loading Tides
Header = ---- Ocean loading values follow next: ----
Model = FES2014b
LoadingType = displacement
GreensF = mc00egbc
CMC = 1
Plot = 0
OutputFormat = BLQ
Stations = %s
MyEmail = demiang@gmail.com
"""

# Import smtplib for the actual sending function
import smtplib
# Import the email modules we'll need
from email.mime.text import MIMEText
import argparse
import re

from pgamit import Utils
# app
from pgamit import dbConnection
from pgamit.Utils import file_write, file_readlines, process_stnlist, stationID, import_blq, add_version_argument


def main():
    parser = argparse.ArgumentParser(description='Ocean tide loading program')

    parser.add_argument('-import', '--import_otl', nargs=1,
                        help="File containing the BLQ parameters returned by the Chalmers website service.")

    parser.add_argument('-stn', '--station_list', type=str, nargs='+',
                        help="Limit the output to the provided station list.")

    add_version_argument(parser)

    args = parser.parse_args()

    if args.station_list:
        cnn = dbConnection.Cnn('gnss_data.cfg')
        stnlist = process_stnlist(cnn, args.station_list)
    else:
        stnlist = []

    if args.import_otl:
        process_blq(args.import_otl[0])
    else:
        create_files(stnlist)


def create_files(stnlist):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    if stnlist:
        sql_where = ','.join("'%s'" % stationID(stn) for stn in stnlist)

        rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND "Harpos_coeff_otl" LIKE '
                       '\'%%HARPOS%%\' AND "NetworkCode" || \'.\' || "StationCode" IN (%s) '
                       'ORDER BY "NetworkCode", "StationCode"' % sql_where)
    else:
        rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND "Harpos_coeff_otl" LIKE '
                       '\'%%HARPOS%%\' ORDER BY "NetworkCode", "StationCode"')
        # rs = cnn.query(

    #    'SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' ORDER BY "NetworkCode", "StationCode"')

    stations = rs.dictresult()
    print(' >> Cantidad de estaciones a procesar en Chalmers: %d' % len(stations))
    stnlist = []
    index   = 0
    for stn in stations:
        stnlist += ['%-24s %16.3f%16.3f%16.3f' % (stn['NetworkCode'] + '_' + stn['StationCode'],
                                                  float(stn['auto_x']),
                                                  float(stn['auto_y']),
                                                  float(stn['auto_z']))]

        if len(stnlist) == 99:

            body = '\n'.join(stnlist)

            file_write('otl_%i.list' % index,
                       body)

            index += 1
            # msg = MIMEText(body)
            # msg['Subject'] = 'Subject: Ocean Loading Tides'
            # msg['From'] = 'demiang@gmail.com'
            # msg['To'] = 'demiang@gmail.com'
            #
            # s = smtplib.SMTP_SSL('64.233.190.108', 465)
            # s.ehlo()
            # s.sendmail('demiang@gmail.com', 'demiang@gmail.com', msg.as_string())
            # s.close()

            stnlist = []

    if len(stnlist) > 0:
        body = '\n'.join(stnlist)

        file_write('otl_%i.list' % index, 
                   body)


def import_harpos(filename):
    # parse the file to see if it is HARPOS
    otl = file_readlines(filename)

    if otl[0][0:6] != 'HARPOS':
        print(' >> Input files does not appear to be in HARPOS format!')
        return

    # it's HARPOS alright
    # find the linenumber of the phase and frequency components
    header = []
    pattern = re.compile('H\s+Ssa\s+\d+.\d+[eEdD][-+]\d+\s+\d+.\d+[eEdD][-+]\d+\s+\d+.\d+[eEdD][-+]\d+')
    for line in otl:
        if pattern.match(line):
            header = otl[0:otl.index(line)+1]
            break

    if header:
        pattern = re.compile('S\s+\w+.\w+\s+[-]?\d+.\d+\s+[-]?\d+.\d+\s+[-]?\d+.\d+\s+[-]?\d+.\d+\s+[-]?\d+.\d+\s+[-]?\d+.\d+')

        for line in otl:
            if pattern.match(line):
                load_harpos(header, otl[otl.index(line) - 2:otl.index(line)+13])

    else:
        print(' >> Could not find a valid header')


def process_blq(filename):
    # open connection to database
    cnn = dbConnection.Cnn("gnss_data.cfg")

    # parse the file to see if it is BLQ
    otl = ''.join(file_readlines(filename))

    try:
        blq_otl = import_blq(otl)

        for stn in blq_otl:
            print(' >> Updating OTL for %s.%s' % (stn['NetworkCode'], stn['StationCode']))
            cnn.update('stations', {'Harpos_coeff_otl': stn['otl']},
                       NetworkCode=stn['NetworkCode'], StationCode=stn['StationCode'])

    except Utils.UtilsException as e:
        print(str(e))


def load_harpos(header, otl):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # begin removing the network code from the OTL
    NetStn = re.findall('S\s+(\w+.\w+)\s+', ''.join(otl))

    NetworkCode, StationCode = NetStn[0].split('.')

    OTL = (''.join(header) + ''.join(otl)).replace(NetStn[0], StationCode + '    ') + 'HARPOS Format version of 2002.12.12'

    print(' >> updating %s.%s' % (NetworkCode, StationCode))
    cnn.query('UPDATE stations SET "Harpos_coeff_otl" = \'%s\' WHERE "NetworkCode" = \'%s\' AND '
              '"StationCode" = \'%s\'' % (OTL, NetworkCode, StationCode))


if __name__ == '__main__':
    main()
