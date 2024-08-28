#!/usr/bin/env python

"""
Project: Mike's APRs into db
Date: 1/19/18 8:37 PM
Author: Demian D. Gomez
"""

# deps
import pg
import hdf5storage
import numpy as np

# app
import dbConnection
import pyDate

def main():

    print(' >> Loading g08d APRs...')
    mat = hdf5storage.loadmat('PRIORS_from_g08d.mat')

    # stn_index = np.where(mat['pv_stnm'] == rnx['NetworkCode'].uppper() + '_' + rnx['StationCode'].upper())[0][0]
    # ydm_index = np.where((mat['pv_Epoch']['iyear'] == date.year) & (mat['pv_Epoch']['doy'] == date.doy))

    cnn = dbConnection.Cnn('gnss_data.cfg')

    for stnm in mat['pv_stnm'].tolist():
        NetworkCode = stnm[0].split('_')[0].lower()
        StationCode = stnm[0].split('_')[1].lower()

        station_id = NetworkCode + '.' + StationCode

        print(' -- inserting ' + station_id)

        if cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\'' % (NetworkCode, StationCode)).ntuples() != 0:
            # get the rows for this station
            stn_index = np.where(mat['pv_stnm'] == stnm[0])[0][0]
            xyz = mat['pv_xyz'][stn_index*3:stn_index*3+3]
            enu = mat['pv_sig_enu'][stn_index*3:stn_index*3+3]

            # loop through the epochs
            for i, fyear in enumerate(mat['pv_Epoch']['fyear'][0][0]):
                date = pyDate.Date(fyear=fyear)

                if enu[0][i] < 10:
                    # print ' -- ' + station_id  + ' ' + date.yyyyddd()
                    # actual sigma value, otherwise it's a super unconstrained (should not be inserted)
                    try:
                        cnn.query('INSERT INTO apr_coords '
                                  '("NetworkCode", "StationCode", "Year", "DOY", "FYear", "x", "y", "z", "sn", "se", "su", "ReferenceFrame") VALUES '
                                  '(\'%s\', \'%s\', %i, %i, %f, %f, %f, %f, %f, %f, %f, \'g08d\')' %
                                  (NetworkCode, StationCode, date.year, date.doy, date.fyear,
                                   xyz[0][i], xyz[1][i], xyz[2][i],
                                   enu[0][i], enu[1][i], enu[2][i]))
                    except pg.IntegrityError:
                        print(' -- ' + station_id + ' ' + date.yyyyddd() + ' already exists!')

        else:
            print(' -- COULD NOT FIND STATION ' + station_id)

if __name__ == '__main__':
    main()
