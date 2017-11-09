"""
Project: Parallel.GAMIT
Date: 3/31/17 3:39 PM
Author: Demian D. Gomez

Class that holds the station metadata needed to process in GAMIT
"""
import pyStationInfo
import pyPPPETM
import pyRinex
import pyArchiveStruct
import pyDate
import random
import string
import os

class Station():

    def __init__(self, cnn, NetworkCode, StationCode):

        self.NetworkCode  = NetworkCode
        self.StationCode  = StationCode
        self.StationAlias = StationCode  # upon creation, Alias = StationCode
        self.record       = None
        self.etm          = None
        self.StationInfo  = None
        self.lat          = None
        self.lon          = None
        self.height       = None
        self.X            = None
        self.Y            = None
        self.Z            = None

        try:
            rs = cnn.query('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                           % (NetworkCode, StationCode))

            if rs.ntuples() != 0:
                self.record = rs.dictresult() # type: dict

                self.lat = float(self.record[0]['lat'])
                self.lon = float(self.record[0]['lon'])
                self.height = float(self.record[0]['height'])
                self.X      = float(self.record[0]['auto_x'])
                self.Y      = float(self.record[0]['auto_y'])
                self.Z      = float(self.record[0]['auto_z'])

                self.etm = pyPPPETM.ETM(cnn,NetworkCode,StationCode)  # type: pyPPPETM.ETM
                self.StationInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)  # type: pyStationInfo.StationInfo

        except:
            raise

        return

    def GenerateStationAlias(self):
        self.StationAlias = self.id_generator()

    def id_generator(self, size=4, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

class StationInstance():

    def __init__(self, cnn, Station, date, Archive_path):

        self.cnn          = cnn
        self.Rinex        = None
        self.Station      = Station # type: Station
        self.StationInfo  = pyStationInfo.StationInfo(self.cnn, self.Station.NetworkCode, self.Station.StationCode, date) # type: pyStationInfo.StationInfo
        self.date         = date # type: pyDate.Date
        self.Archive_path = Archive_path

        # get the APR and sigmas for this date (let get_xyz_s determine which side of the jump returns, if any)
        self.Apr, self.Sigmas, self.Window = self.Station.etm.get_xyz_s(self.date.year, self.date.doy)

        return

    def GetRinexFilename(self):

        self.Archive = pyArchiveStruct.RinexStruct(self.cnn) # type: pyArchiveStruct.RinexStruct
        ArchiveFile = self.Archive.build_rinex_path(self.Station.NetworkCode, self.Station.StationCode, self.date.year, self.date.doy)

        filename = self.Station.StationAlias + self.date.ddd() + '0.' + self.date.yyyy()[2:4] + 'd.Z'

        return {'NetworkCode' : self.Station.NetworkCode,
                'StationCode' : self.Station.StationCode,
                'StationAlias': self.Station.StationAlias,
                'source'      : os.path.join(self.Archive_path, ArchiveFile),
                'destiny'     : filename,
                'lat'         : self.Station.lat,
                'lon'         : self.Station.lon,
                'height'      : self.Station.height,
                'jump'        : self.Window}


    def GetApr(self):
        x = self.Apr

        return ' ' + self.Station.StationAlias.upper() + '_GPS ' + '{:12.3f}'.format(x[0, 0]) + ' ' + '{:12.3f}'.format(
            x[1, 0]) + ' ' + '{:12.3f}'.format(x[2, 0]) + ' 0.000 0.000 0.000 ' + '{:8.3f}'.format(
            self.date.fyear)

    def GetSittbl(self):
        s = self.Sigmas*2.5

        return self.Station.StationAlias.upper() + ' ' + self.Station.StationAlias.upper() + '_GPS' + 'NNN'.rjust(8) + '    {:.5}'.format(
            '%5.3f' % (s[0, 0])) + ' ' + '{:.5}'.format('%5.3f' % (s[1, 0])) + ' ' + '{:.5}'.format(
            '%5.3f' % (s[2, 0]))

    def DebugCoord(self):
        x = self.Apr

        rs = self.cnn.query('SELECT * FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND "Year" = %s AND "DOY" = %s' % (self.Station.NetworkCode,self.Station.StationCode, self.date.yyyy(), self.date.ddd()))

        if rs.ntuples() > 0:
            ppp = rs.dictresult()
            return self.Station.StationAlias.upper() + ' ' + self.Station.StationAlias.upper() + '_GPS' + 'NNN'.rjust(8) \
               + '    {:.8}'.format('%8.3f' % (float(ppp[0]['X']) - self.Station.X)) \
               + ' ' + '{:.8}'.format('%8.3f' % (float(ppp[0]['Y']) - self.Station.Y)) \
               + ' ' + '{:.8}'.format('%8.3f' % (float(ppp[0]['Z']) - self.Station.Z)) \
               + '{:12.3f}'.format(x[0, 0]) + ' ' + '{:12.3f}'.format(x[1, 0]) + ' ' + '{:12.3f}'.format(x[2, 0]) + ' 0.000 0.000 0.000 ' + '{:8.3f}'.format(self.date.fyear)
        else:
            return self.Station.StationAlias.upper() + ' ' + self.Station.StationAlias.upper() + '_GPS' + 'NNN'.rjust(8) + ' NO PPP COORDINATE! ' + '{:12.3f}'.format(x[0, 0]) + ' ' + '{:12.3f}'.format(x[1, 0]) + ' ' + '{:12.3f}'.format(x[2, 0]) + ' 0.000 0.000 0.000 ' + '{:8.3f}'.format(self.date.fyear)

    def GetStationInformation(self):

        self.StationInfo.return_stninfo().replace(self.Station.StationCode.upper(), self.Station.StationAlias.upper())

