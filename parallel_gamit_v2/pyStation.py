"""
Project: Parallel.GAMIT
Date: 3/31/17 3:39 PM
Author: Demian D. Gomez

Class that holds the station metadata needed to process in GAMIT
"""
import pyStationInfo
import pyETM
import pyBunch
import pyDate
import random
import string
import os

COMPLETION = 0.5
INTERVAL = 120


class pyStationException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Station(object):

    def __init__(self, cnn, NetworkCode, StationCode, dates):

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
        self.otl_H        = None

        rs = cnn.query_float('SELECT * FROM stations WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\''
                             % (NetworkCode, StationCode), as_dict=True)

        if len(rs) != 0:
            self.record = pyBunch.Bunch().fromDict(rs[0])

            self.otl_H = self.record.Harpos_coeff_otl
            self.lat = self.record.lat
            self.lon = self.record.lon
            self.height = self.record.height
            self.X = self.record.auto_x
            self.Y = self.record.auto_y
            self.Z = self.record.auto_z

            # get the available dates for the station (RINEX files with conditions to be processed)
            rs = cnn.query(
                'SELECT "ObservationYear" as y, "ObservationDOY" as d FROM rinex_proc '
                'WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                '"ObservationSTime" >= \'%s\' AND "ObservationETime" <= \'%s\' AND '
                '"Completion" >= %.3f AND "Interval" <= %i'
                % (NetworkCode, StationCode, dates[0].first_epoch(), dates[1].last_epoch(), COMPLETION, INTERVAL))

            self.good_rinex = [pyDate.Date(year=r['y'], doy=r['d']) for r in rs.dictresult()]

            # create a list of the missing days
            good_rinex = [d.mjd for d in self.good_rinex]

            self.missing_rinex = [pyDate.Date(mjd=d)
                                  for d in range(dates[0].mjd, dates[1].mjd+1) if d not in good_rinex]

            self.etm = pyETM.PPPETM(cnn, NetworkCode, StationCode)  # type: pyETM.PPPETM
            self.StationInfo = pyStationInfo.StationInfo(cnn, NetworkCode, StationCode)
        else:
            raise ValueError('Specified station %s.%s could not be found' % (NetworkCode, StationCode))

    def generate_alias(self):
        self.StationAlias = self.id_generator()

    @staticmethod
    def id_generator(size=4, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def __eq__(self, station):

        if not isinstance(station, Station):
            raise pyStationException('type: '+str(type(station))+' invalid.  Can only compare pyStation.Station')

        return self.NetworkCode == station.NetworkCode and self.StationCode == station.StationCode


class StationInstance(object):

    def __init__(self, cnn, archive, station, date, archive_path):

        self.NetworkCode = station.NetworkCode
        self.StationCode = station.StationCode
        self.StationAlias = station.StationAlias
        self.lat = station.record.lat
        self.lon = station.record.lon
        self.height = station.record.height
        self.X = station.record.auto_x
        self.Y = station.record.auto_y
        self.Z = station.record.auto_z
        self.otl_H = station.otl_H
        self.Rinex = None

        # save the station information as text
        self.StationInfo = pyStationInfo.StationInfo(cnn,
                                                     station.NetworkCode, station.StationCode, date).return_stninfo()

        self.date = date  # type: pyDate.Date
        self.Archive_path = archive_path

        # get the APR and sigmas for this date (let get_xyz_s determine which side of the jump returns, if any)
        self.Apr, self.Sigmas, self.Window, self.source = station.etm.get_xyz_s(self.date.year, self.date.doy)

        # rinex file
        self.ArchiveFile = archive.build_rinex_path(self.NetworkCode, self.StationCode,
                                                    self.date.year, self.date.doy)

        self.filename = self.StationAlias + self.date.ddd() + '0.' + self.date.yyyy()[2:4] + 'd.Z'

        # save some information for debugging purposes
        rs = cnn.query_float('SELECT * FROM ppp_soln WHERE "NetworkCode" = \'%s\' AND "StationCode" = \'%s\' AND '
                             '"Year" = %s AND "DOY" = %s'
                             % (self.NetworkCode, self.StationCode, self.date.yyyy(), self.date.ddd()), as_dict=True)

        if len(rs) > 0:
            self.ppp = rs[0]
        else:
            self.ppp = None

    def GetRinexFilename(self):

        return {'NetworkCode' : self.NetworkCode,
                'StationCode' : self.StationCode,
                'StationAlias': self.StationAlias,
                'source'      : os.path.join(self.Archive_path, self.ArchiveFile),
                'destiny'     : self.filename,
                'lat'         : self.lat,
                'lon'         : self.lon,
                'height'      : self.height,
                'jump'        : self.Window}

    def GetApr(self):
        x = self.Apr

        return ' ' + self.StationAlias.upper() + '_GPS ' + '{:12.3f}'.format(x[0, 0]) + ' ' + '{:12.3f}'.format(
            x[1, 0]) + ' ' + '{:12.3f}'.format(x[2, 0]) + ' 0.000 0.000 0.000 ' + '{:8.4f}'.format(
            self.date.fyear)

    def GetSittbl(self):
        s = self.Sigmas

        return self.StationAlias.upper() + ' ' + self.StationAlias.upper() + '_GPS' + 'NNN'.rjust(8) + '    {:.5}'.format(
            '%5.3f' % (s[0, 0])) + ' ' + '{:.5}'.format('%5.3f' % (s[1, 0])) + ' ' + '{:.5}'.format(
            '%5.3f' % (s[2, 0]))

    def DebugCoord(self):
        x = self.Apr
        s = self.Sigmas

        if self.ppp is not None:
            return '%s %s_GPS %8.3f %8.3f %8.3f %14.3f %14.3f %14.3f %8.3f %8.3f %8.3f %8.4f %s' % \
                   (self.StationAlias.upper(), self.StationAlias.upper(),
                    self.ppp['X'] - self.X,
                    self.ppp['Y'] - self.Y,
                    self.ppp['Z'] - self.Z,
                    x[0, 0], x[1, 0], x[2, 0],
                    s[0, 0], s[1, 0], s[2, 0],
                    self.date.fyear, self.source)
        else:
            return '%s %s_GPS %-26s %14.3f %14.3f %14.3f %8.3f %8.3f %8.3f %8.4f %s' % \
                   (self.StationAlias.upper(), self.StationAlias.upper(), 'NO PPP COORDINATE',
                    x[0, 0], x[1, 0], x[2, 0],
                    s[0, 0], s[1, 0], s[2, 0],
                    self.date.fyear, self.source)

    def GetStationInformation(self):

        return self.StationInfo.replace(self.StationCode.upper(), self.StationAlias.upper())

