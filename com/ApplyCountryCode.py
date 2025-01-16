#!/usr/bin/env python
"""
Project: Parallel.GAMIT
Date: 11/20/2023
Author: Demian D. Gomez

This script assigns country codes to the stations table
"""
from pgamit import dbConnection
import country_converter as coco

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


def main():
    geolocator = Nominatim(user_agent="Parallel.GAMIT")

    cnn = dbConnection.Cnn('gnss_data.cfg')

    stations = cnn.query('''SELECT * FROM stations
                         WHERE country_code IS NULL AND
                         lat IS NOT NULL and lon IS NOT NULL''').dictresult()

    ''' add minimum delay of 1s to comply with nominatim usage policy &
avoid timeout error
    https://operations.osmfoundation.org/policies/nominatim/
    https://gis.stackexchange.com/questions/331144
/bulk-reverse-geocoding-with-geopy-using-built-in-rate-limiter
    '''

    reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

    for stn in stations:
        print('Station %s.%s has no ISO3 lat: %12.8f lon: %13.8f'
              % (stn['NetworkCode'], stn['StationCode'],
                 stn['lat'], stn['lon']))
        location = reverse("%f, %f" % (stn['lat'], stn['lon']))
        if location and 'country_code' in location.raw['address'].keys():
            ISO3 = coco.convert(names=location.raw['address']['country_code'],
                                to='ISO3')
            print(' -- Updating %s.%s with ISO3 %s'
                  % (stn['NetworkCode'], stn['StationCode'], ISO3))
            cnn.update('stations', {'country_code': ISO3}, **stn)
        else:
            print(' -- Could not determine ISO3 for %s.%s'
                  % (stn['NetworkCode'], stn['StationCode']))


if __name__ == '__main__':
    main()
