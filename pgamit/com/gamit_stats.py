#!/usr/bin/env python

"""
Project:
Date: 10/27/17 12:40 PM
Author: Demian D. Gomez
"""

import os
import glob
import re
from datetime import datetime

# deps
import numpy as np

# app
from pyDate import Date
import dbConnection
import pyOptions
from Utils import file_readlines

def parse_monitor(cnn, monitor):
    lines  = file_readlines(monitor)
    output = ''.join(lines)

    try:
        project, subnet, year, doy = re.findall('GamitTask initialized for (\w+.*?).(\w+\d+): (\d+) (\d+)', output, re.MULTILINE)[0]
        subnet = int(subnet[3:])
        year   = int(year)
        doy    = int(doy)
    except:
        # maybe it is a project with no subnets
        try:
            project, year, doy = re.findall('GamitTask initialized for (\w+.*?): (\d+) (\d+)', output, re.MULTILINE)[0]
            subnet = 0
            year   = int(year)
            doy    = int(doy)
        except:
            print(' -- could not determine project! ' + monitor)
            return

    try:
        node = re.findall('executing on (\w+)', output, re.MULTILINE)[0]
    except:
        node = 'PUGAMIT100'

    try:
        start_time = datetime.strptime(re.findall('run.sh \((\d+-\d+-\d+ \d+:\d+:\d+)\): Iteration depth: 1', output, re.MULTILINE)[0], '%Y-%m-%d %H:%M:%S')
    except:
        print(' -- could not determine start_time! ' + monitor)
        return

    try:
        end_time = datetime.strptime(re.findall('finish.sh \((\d+-\d+-\d+ \d+:\d+:\d+)\): Done processing h-files and generating SINEX.', output, re.MULTILINE)[0], '%Y-%m-%d %H:%M:%S')
    except:
        print(' -- could not determine end_time! ' + monitor)
        return

    try:
        iterations = int(re.findall('run.sh \(\d+-\d+-\d+ \d+:\d+:\d+\): Iteration depth: (\d+)', output, re.MULTILINE)[-1])
    except:
        print(' -- could not determine iterations!')
        return

    try:
        nrms = float(re.findall('Prefit nrms:\s+\d+.\d+[eEdD]\+\d+\s+Postfit nrms:\s+(\d+.\d+[eEdD][+-]\d+)', output, re.MULTILINE)[-1])
    except:
        # maybe GAMIT didn't finish
        nrms = 1

    try:
        updated_apr = re.findall(' (\w+).*?Updated from', output, re.MULTILINE)[0]
        updated_apr = [upd.replace('_GPS', '').lower() for upd in updated_apr]
        upd_stn = []
        for stn in updated_apr:
            upd_stn += re.findall('fetching rinex for (\w+.\w+) %s' % stn.lower(), output, re.MULTILINE)

        upd_stn = ','.join(upd_stn)
    except:
        # maybe GAMIT didn't finish
        upd_stn = None

    try:
        wl = float(re.findall('WL fixed\s+(\d+.\d+)', output, re.MULTILINE)[0])
    except:
        # maybe GAMIT didn't finish
        wl = 0

    try:
        nl = float(re.findall('NL fixed\s+(\d+.\d+)', output, re.MULTILINE)[0])
    except:
        # maybe GAMIT didn't finish
        nl = 0

    try:
        oc = re.findall('relaxing over constrained stations (\w+.*)', output, re.MULTILINE)[0]
        oc = oc.replace('|', ',').replace('_GPS','').lower()

        oc_stn = []
        for stn in oc.split(','):
            oc_stn += re.findall('fetching rinex for (\w+.\w+) %s' % stn.lower(), output, re.MULTILINE)

        oc_stn = ','.join(oc_stn)

    except:
        # maybe GAMIT didn't finish
        oc_stn = None

    try:
        overcons = re.findall('GCR APTOL (\w+).{10}\s+([-]?\d+.\d+)', output, re.MULTILINE)

        if len(overcons) > 0:
            i   = np.argmax(np.abs([float(o[1]) for o in overcons]))
            stn = overcons[int(i)][0]

            # get the real station code
            max_overconstrained = re.findall('fetching rinex for (\w+.\w+) %s' % stn.lower(), output, re.MULTILINE)[0]
        else:
            max_overconstrained = None
    except:
        # maybe GAMIT didn't finish
        max_overconstrained = None

    try:
        cnn.insert('gamit_stats', {'Project'             : project,
                                   'subnet'              :  subnet,
                                   'Year'                : year,
                                   'DOY'                 : doy,
                                   'FYear'               : Date(year=year, doy=doy).fyear,
                                   'wl'                  : wl,
                                   'nl'                  : nl,
                                   'nrms'                : nrms,
                                   'relaxed_constrains'  : oc_stn,
                                   'max_overconstrained' : max_overconstrained,
                                   'updated_apr'         : upd_stn,
                                   'iterations'          : iterations,
                                   'node'                : node,
                                   'execution_time'      : int((end_time - start_time).total_seconds()/60.0),
                                   'execution_date'      : start_time})
    except dbConnection.dbErrInsert:
        print(' -- record already exists ' + monitor)


def main():

    cnn = dbConnection.Cnn('gnss_data.cfg')

    yrs = glob.glob('/data/[1-2]*')

    for dir in yrs:
        days = glob.glob(dir + '/*')

        for day in days:
            sessions = glob.glob(day + '/*')

            for sess in sessions:
                parts = os.path.split(sess)

                path = sess + '/monitor.log'
                if '.' in parts[1]:
                    # gamit session, parse monitor insert data
                    parse_monitor(cnn, path)

                elif os.path.isfile(path):
                    parse_monitor(cnn, path)


if __name__ == '__main__':
    main()
