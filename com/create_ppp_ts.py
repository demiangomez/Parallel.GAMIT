#!/usr/bin/env python

# app
import dbConnection
import pyETM
from pyDate import Date

cnn = dbConnection.Cnn('gnss_data.cfg')

stns = cnn.query('SELECT * FROM stations WHERE "NetworkCode" NOT LIKE \'?%\'')

for stn in stns.dictresult():

    print(' >> working on %s.%s' % (stn['NetworkCode'], stn['StationCode']))
    etm = pyETM.PPPETM(cnn, stn['NetworkCode'], stn['StationCode'])

    dates = [Date(mjd=mjd)
             for mjd in etm.soln.mjd]

