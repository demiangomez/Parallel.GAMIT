"""
Project: Parallel.GAMIT
Date: 11/20/2023
Author: Demian D. Gomez

This script assigns country codes to the stations table
"""
import dbConnection
import pyOptions
import country_converter as coco

from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="Parallel.GAMIT")

config = pyOptions.ReadOptions('gnss_data.cfg')
cnn = dbConnection.Cnn('gnss_data.cfg')

stations = cnn.query('SELECT * FROM stations WHERE country_code IS NULL AND '
                     'lat IS NOT NULL and lon IS NOT NULL').dictresult()

for stn in stations:
    print('Station %s.%s has no ISO3 lat: %12.8f lon: %13.8f'
          % (stn['NetworkCode'], stn['StationCode'], stn['lat'], stn['lon']))
    location = geolocator.reverse("%f, %f" % (stn['lat'], stn['lon']))
    if location and 'country_code' in location.raw['address'].keys():
        ISO3 = coco.convert(names=location.raw['address']['country_code'], to='ISO3')
        print(' -- Updating %s.%s with ISO3 %s' % (stn['NetworkCode'], stn['StationCode'], ISO3))
        cnn.update('stations', stn, country_code=ISO3)
    else:
        print(' -- Could not determine ISO3 for %s.%s' % (stn['NetworkCode'], stn['StationCode']))

