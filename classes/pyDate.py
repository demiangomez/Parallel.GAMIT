"""
Project: Parallel.Archive
Date: 2/23/17 9:28 AM
Author: Abel Brown
Modified by: Demian D. Gomez

Class that handles all the date conversions betweem different systems and formats

"""

import math
from datetime import datetime
import sys

class pyDateException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return str(self.value)

def yeardoy2fyear(year,doy,hour=12):

    # parse to integers (defensive)
    year = int(year)
    doy  = int(doy)
    hour = int(hour)

    # default number of days in a year
    diy=365

    # check for leap years
    if year % 4 ==0:
        diy += 1.

    # make sure day of year is valid
    if doy < 1 or doy > diy:
        raise pyDateException('invalid day of year')

    # compute the fractional year
    fractionalYear = year + ((doy-1)+hour/24.)/diy

    # that's all ...
    return fractionalYear

def fyear2yeardoy(fyear):

    year = math.floor(fyear)
    fractionOfyear = fyear - year

    if year % 4 == 0:
        doy = math.floor(366*fractionOfyear)+1
    else:
        doy = math.floor(365*fractionOfyear)+1

    return int(year),int(doy)

def date2doy(year,month,day,hour=12):

    # parse to integers (defensive)
    year  = int(year)
    month = int(month)
    day   = int(day)
    hour  = int(hour)

    # localized days of year
    if year % 4 == 0:
        lday = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]
    else:
        lday =  [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

    # compute the day of year
    doy=lday[month - 1]+day

    # finally, compute fractional year
    fyear = yeardoy2fyear(year,doy,hour)

    # that's a [w]rap
    return doy,fyear

def doy2date(year,doy):

    # parsem up to integers
    year = int(year)
    doy  = int(doy)

    # make note of leap year or not
    isLeapYear=False
    if year % 4 == 0:
        isLeapYear=True

    # make note of valid doy for year
    mxd = 365
    if isLeapYear:
        mxd +=1

    # check doy based on year
    if doy < 1 or doy > mxd:
        raise pyDateException('day of year input is invalid')

    # localized days
    if not isLeapYear:
        fday = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
        lday = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]

    if isLeapYear:
        fday = [1, 32, 61, 92, 122, 153, 183, 214, 245, 275, 306, 336]
        lday = [31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335, 366]

    # compute the month
    for i in range(0,12):
        if doy <= lday[i]:
            #remember: zero based indexing!
            month=i+1
            break

    # compute the day (dont forget zero based indexing)
    day = doy - fday[month-1] +1

    return month,day

def date2gpsDate(year,month,day):

    year  = int(year)
    month = int(month)
    day   = int(day)

    if month <= 2:
        month += 12
        year  -=  1

    ut  = (day % 1) *24.
    day = math.floor(day)

    julianDay =   math.floor( 365.25 * year )              \
                + math.floor( 30.6001 * ( month + 1. ) )   \
                + day                                      \
                + ut/24.                                   \
                + 1720981.5

    gpsWeek    = math.floor((julianDay - 2444244.5)/7.)
    gpsWeekDay = (julianDay - 2444244.5) % 7

    # that's a [w]rap
    return int(gpsWeek), int(gpsWeekDay)

def gpsDate2mjd(gpsWeek,gpsWeekDay):

    # parse to integers
    gpsWeek    = int(gpsWeek)
    gpsWeekDay = int(gpsWeekDay)

    mjd = (gpsWeek * 7.) + 44244. + gpsWeekDay

    return int(mjd)

def mjd2date(mjd):

    mjd = float(mjd)

    jd = mjd + 2400000.5

    ijd = math.floor(jd + 0.5)

    a = ijd + 32044.
    b = math.floor((4. * a + 3.) / 146097.)
    c = a - math.floor((b * 146097.) / 4.)

    d = math.floor((4. * c + 3.) / 1461.)
    e = c - math.floor((1461. * d) / 4.)
    m = math.floor((5. * e + 2.) / 153.)

    day   = e - math.floor((153. * m + 2.) / 5.) + 1.
    month = m + 3. - 12. * math.floor(m / 10.)
    year  = b * 100. + d - 4800. + math.floor(m / 10.)

    return int(year),int(month),int(day)


class Date():

    def __init__(self,**kwargs):

        # init
        self.mjd        = None
        self.fyear      = None
        self.year       = None
        self.doy        = None
        self.day        = None
        self.month      = None
        self.gpsWeek    = None
        self.gpsWeekDay = None
        self.hour       = 12 # DDG 03-28-2017: include hour and minute to work with station info object
        self.minute     = 0
        self.second     = 0

        # parse args
        for key in kwargs:

            arg = kwargs[key]
            key = key.lower()

            if key == 'year':
                if int(arg) < 1900:
                    # the date is in 2 digit format
                    if int(arg) > 80:
                        self.year = int(arg)+ 1900
                    else:
                        self.year = int(arg)+ 2000
                else:
                    self.year = arg
            elif key == 'doy':
                self.doy = arg
            elif key == 'day':
                self.day = arg
            elif key == 'month':
                self.month = arg
            elif key == 'gpsweek':
                self.gpsWeek = arg
            elif key == 'gpsweekday':
                self.gpsWeekDay = arg
            elif key in ('fyear','fractionalyear','fracyear'):
                self.fyear = arg
            elif key == 'mjd':
                self.mjd = arg
            elif key == 'hour': #DDG 03-28-2017: include hour to work with station info object
                self.hour = arg
            elif key == 'minute': #DDG 03-28-2017: include minute to work with station info object
                self.minute = arg
            elif key == 'datetime': #DDG 03-28-2017: handle conversion from datetime to pyDate
                if isinstance(arg, datetime):
                    self.day = arg.day
                    self.month = arg.month
                    self.year = arg.year
                    self.hour = arg.hour
                    self.minute = arg.minute
                    self.second = arg.second
                else:
                    raise pyDateException('invalid type for ' + key + '\n')
            else:
                raise pyDateException('unrecognized input arg: '+key+'\n')

        # make due with what we gots
        if self.year != None and self.doy != None:

            # compute the month and day of month
            self.month,self.day = doy2date(self.year, self.doy)

            # compute the fractional year
            self.fyear = yeardoy2fyear(self.year,self.doy,self.hour)

            # compute the gps date
            self.gpsWeek,self.gpsWeekDay = date2gpsDate(self.year,self.month,self.day)

            self.mjd = gpsDate2mjd(self.gpsWeek,self.gpsWeekDay)

        elif self.gpsWeek != None and self.gpsWeekDay != None:

            # initialize modified julian day from gps date
            self.mjd = gpsDate2mjd(self.gpsWeek,self.gpsWeekDay)

            # compute year, month, and day of month from modified julian day
            self.year,self.month,self.day = mjd2date(self.mjd)

            # compute day of year from month and day of month
            self.doy,self.fyear = date2doy(self.year,self.month,self.day,self.hour)

        elif self.year != None and self.month != None and self.day:

            # initialize day of year and fractional year from date
            self.doy,self.fyear = date2doy(self.year,self.month,self.day,self.hour)

            # compute the gps date
            self.gpsWeek,self.gpsWeekDay = date2gpsDate(self.year,self.month,self.day)

            # init the modified julian date
            self.mjd = gpsDate2mjd(self.gpsWeek,self.gpsWeekDay)

        elif self.fyear != None:

            # initialize year and day of year
            self.year,self.doy = fyear2yeardoy(self.fyear)

            # set the month and day of month
            # compute the month and day of month
            self.month,self.day = doy2date(self.year, self.doy)

            # compute the gps date
            self.gpsWeek,self.gpsWeekDay = date2gpsDate(self.year,self.month,self.day)

            # finally, compute modified jumlian day
            self.mjd = gpsDate2mjd(self.gpsWeek,self.gpsWeekDay)

        elif self.mjd != None:

            # compute year, month, and day of month from modified julian day
            self.year,self.month,self.day = mjd2date(self.mjd)

            # compute day of year from month and day of month
            self.doy,self.fyear = date2doy(self.year,self.month,self.day,self.hour)

            # compute the gps date
            self.gpsWeek,self.gpsWeekDay = date2gpsDate(self.year,self.month,self.day)

        else:
            raise pyDateException('not enough independent input args to compute full date ')

    def __repr__(self):
        return 'pyDate.Date('+str(self.year)+', '+str(self.doy)+')'

    def __str__(self):
        return str(self.year)+', '+str(self.doy)

    def __lt__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+type(date)+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd < date.mjd

    def __le__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+type(date)+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd <= date.mjd

    def __gt__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+type(date)+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd > date.mjd

    def __ge__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+type(date)+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd >= date.mjd

    def __eq__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+str(type(date))+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd == date.mjd

    def __ne__(self,date):

        if not isinstance(date,Date):
            raise pyDateException('type: '+type(date)+' invalid.  Can only compare pyDate.Date objects')

        return self.mjd != date.mjd

    def __add__(self,ndays):

        if not isinstance(ndays,int):
            raise pyDateException('type: '+type(ndays)+' invalid.  Can only add integer number of days')

        return Date(mjd=self.mjd+ndays)

    def __sub__(self,ndays):

        if not isinstance(ndays,int):
            raise pyDateException('type: '+type(ndays)+' invalid.  Can only subtract integer number of days')

        return Date(mjd=self.mjd-ndays)

    def ddd(self):
        doystr = str(self.doy)
        return "0"*(3-len(doystr))+doystr

    def yyyy(self):
        return str(self.year)

    def wwww(self):
        weekstr = str(self.gpsWeek)
        return '0'*(4-len(weekstr))+weekstr

    def wwwwd(self):
        return self.wwww()+str(self.gpsWeekDay)

    def yyyymmdd(self):
        return str(self.year)+'/'+str(self.month)+'/'+str(self.day)

    def yyyyddd(self):
        doystr = str(self.doy)
        return str(self.year) + ' ' + doystr.rjust(3, '0')

    def datetime(self):
        return datetime(year=self.year, month=self.month, day=self.day, hour=self.hour, minute=self.minute)


def main(argv):

    date = Date(year=argv[0],doy=argv[1])

if __name__ == '__main__':
    main()
