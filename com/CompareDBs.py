
import dbConnection
import pyPPP
from Utils import stationID
from ScanArchive import export_station
import os
import pyArchiveStruct
import pyOptions
import shutil


def main():

    cnn1 = dbConnection.Cnn('gnss_data_ign.cfg')
    cnn2 = dbConnection.Cnn('gnss_data_osu.cfg')

    pyArchive = pyArchiveStruct.RinexStruct(cnn1)
    Config = pyOptions.ReadOptions("gnss_data_ign.cfg")  # type: pyOptions.ReadOptions

    # get all the stations from the database (IGN)
    stns = cnn1.query('SELECT * FROM stations').dictresult()

    for stn in stns:
        sp = pyPPP.PPPSpatialCheck([float(stn['lat'])], [float(stn['lon'])], [float(stn['height'])])

        found, match, stn_list = sp.verify_spatial_coherence(cnn2, stn['StationCode'])

        if found:
            # print(' -- %s was found as %s' % (stationID(stn), stationID(match[0])))
            # if it was found don't do anything
            pass
        else:
            if len(match) > 0:
                print(' -- %s was NOT found: maybe it is %s (distance: %8.3f m)'
                      % (stationID(stn), stationID(match[0]), match[0]['distance']))

                if not os.path.exists('export/maybe'):
                    os.makedirs('export/maybe')

                export_station(cnn1, [stn], pyArchive, Config.archive_path, False)

                # move the file into the folder
                shutil.move('%s.zip' % stationID(stn), 'export/maybe/%s.zip' % stationID(stn))
            else:
                print(' -- %s was NOT found' % stationID(stn))

                if not os.path.exists('export/sure'):
                    os.makedirs('export/sure')

                export_station(cnn1, [stn], pyArchive, Config.archive_path, False)

                # move the file into the folder
                shutil.move('%s.zip' % stationID(stn), 'export/sure/%s.zip' % stationID(stn))


if __name__ == '__main__':
    main()
