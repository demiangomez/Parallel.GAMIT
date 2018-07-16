"""
Project: Parallel.Archive
Date: 02/16/2017
Author: Demian D. Gomez

Ocean loading coefficients class. It runs and reads grdtab (from GAMIT).
"""

import dbConnection
# Import smtplib for the actual sending function
import smtplib
import argparse
import re

# Import the email modules we'll need
from email.mime.text import MIMEText

def main():
    parser = argparse.ArgumentParser(description='Ocean tide loading program')

    parser.add_argument('-import', '--import_otl', nargs=1,
                        help="File containing the BLQ parameters returned by the Chalmers website service.")

    args = parser.parse_args()

    if args.import_otl:
        import_blq(args.import_otl[0])
    else:
        create_files()


def create_files():

    cnn = dbConnection.Cnn("gnss_data.cfg")

    rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%%\' AND "Harpos_coeff_otl" LIKE \'%%HARPOS%%\' ORDER BY "NetworkCode", "StationCode"')

    stations = rs.dictresult()
    print ' >> Cantidad de estaciones a procesar en Chalmers: ' + str(len(stations))
    stnlist = []
    index = 0
    for stn in stations:
        stnlist += ['%-24s %16.3f%16.3f%16.3f' % (stn['NetworkCode'] + '.' + stn['StationCode'], float(stn['auto_x']), float(stn['auto_y']), float(stn['auto_z']))]

        if len(stnlist) == 99:

            body = """Subject: Ocean Loading Tides
Header = ---- Ocean loading values follow next: ----
Model = FES2014b
LoadingType = displacement
GreensF = mc00egbc
CMC = 1
Plot = 0
OutputFormat = BLQ
Stations = %s
MyEmail = demiang@gmail.com\n
""" % ('\n'.join(stnlist))

            with open('otl_%i.list' % index, 'w') as otl_list:
                otl_list.write(body)

            index += 1
            # msg = MIMEText(body)
            # msg['Subject'] = 'Subject: Ocean Loading Tides'
            # msg['From'] = 'demiang@gmail.com'
            # msg['To'] = 'demiang@gmail.com'
            #
            # s = smtplib.SMTP_SSL('64.233.190.108', 465)
            # s.ehlo()
            # s.login('demiang@gmail.com', 'demostenes0624')
            # s.sendmail('demiang@gmail.com', 'demiang@gmail.com', msg.as_string())
            # s.close()

            stnlist = []

    if len(stnlist) > 0:
        body = """Subject: Ocean Loading Tides
Header = ---- Ocean loading values follow next: ----
Model = FES2014b
LoadingType = displacement
GreensF = mc00egbc
CMC = 1
Plot = 0
OutputFormat = BLQ
Stations = %s
MyEmail = demiang@gmail.com\n
""" % ('\n'.join(stnlist))

        with open('otl_%i.list' % index, 'w') as otl_list:
            otl_list.write(body)

def import_harpos(filename):

    # parse the file to see if it is HARPOS
    with open(filename, 'r') as fileio:
        otl = fileio.readlines()

        if otl[0][0:6] != 'HARPOS':
            print ' >> Input files does not appear to be in HARPOS format!'
            return
        else:
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
                print ' >> Could not find a valid header'

def import_blq(filename):

    # parse the file to see if it is HARPOS
    with open(filename, 'r') as fileio:
        otl = fileio.readlines()

        if otl[0][0:2] != '$$':
            print ' >> Input files does not appear to be in BLQ format!'
            return
        else:
            # it's BLQ alright
            # find the linenumber of the phase and frequency components
            header = otl[0:29]
            pattern = re.compile('\s{2}\w{3}\.\w{4}')

            for line in otl[29:]:
                if pattern.match(line):
                    load_blq(header, otl[otl.index(line):otl.index(line) + 11])


def load_blq(header, otl):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # begin removing the network code from the OTL
    NetStn = re.findall('\s{2}(\w{3}\.\w{4})', ''.join(otl))

    NetworkCode, StationCode = NetStn[0].split('.')

    OTL = (''.join(header) + ''.join(otl)).replace('  ' + NetStn[0], '  ' + StationCode)
    OTL = OTL.replace('$$ ' + NetStn[0], '$$ %-8s' % StationCode)
    OTL = OTL.replace('$$ END TABLE', '$$')
    OTL = OTL.replace("'", "")

    print ' >> updating %s.%s' % (NetworkCode, StationCode)

    cnn.query('UPDATE stations SET "Harpos_coeff_otl" = \'%s\' WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (OTL, NetworkCode, StationCode))


def load_harpos(header, otl):

    cnn = dbConnection.Cnn("gnss_data.cfg")

    # begin removing the network code from the OTL
    NetStn = re.findall('S\s+(\w+.\w+)\s+', ''.join(otl))

    NetworkCode, StationCode = NetStn[0].split('.')

    OTL = (''.join(header) + ''.join(otl)).replace(NetStn[0], StationCode + '    ') + 'HARPOS Format version of 2002.12.12'

    print ' >> updating %s.%s' % (NetworkCode, StationCode)
    cnn.query('UPDATE stations SET "Harpos_coeff_otl" = \'%s\' WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (OTL, NetworkCode, StationCode))


if __name__ == '__main__':

    main()