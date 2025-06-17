#!/usr/bin/env python
"""
Project: Parallel.Archive
Date: 3/3/17 9:56 AM
Author: Demian D. Gomez

This class is based on the USGS Neicio: the USGS NEIC Python interface and its
purpose is to update the table "earthquakes" in the db with the latest
events (M >= 6)

"""
import re
import calendar
import xmltodict
import argparse
from datetime import datetime, timezone
from tqdm import tqdm

# deps
import libcomcat.search
import libcomcat.exceptions as libcome

# app
from pgamit import dbConnection
from pgamit.Utils import add_version_argument

TIMEFMT2 = '%Y-%m-%d %H:%M:%S.%f'

## Python3 Migration: This was not used and is not compatible with new libcomcat
## event format:
# def getNewEvent(event, maxmags):
#     ibigmag = -1
#     bigmag  = 0
#     for key in event.keys():
#         if re.search('mag[0-9]*-type', key):
#             ibigmag = event.keys().index(key)
#             bigmag  = int(re.findall('\d+', key)[0])
#     # we can only get away with this because this is an ordereddict
#     keys   = list(event.keys())
#     values = list(event.values())
#     idx = ibigmag + 1
#     for i in range(bigmag + 1, maxmags + 1):
#         keys.insert(idx,     'mag%i'        % i) # magkey
#         keys.insert(idx + 1, 'mag%i-source' % i) # srckey
#         keys.insert(idx + 2, 'mag%i-type'   % i) # typekey
#         values.insert(idx,     (float('nan'), '%.1f'))
#         values.insert(idx + 1, ('NA', '%s'))
#         values.insert(idx + 2, ('NA', '%s'))
#         idx += 3
# 
#     newevent = OrderedDict(zip(keys, values))
#     return newevent


WEEKSECS = 86400*14


def getTimeSegments2(starttime, endtime):
    #startsecs = int(starttime.strftime('%s'))
    startsecs = calendar.timegm(starttime.timetuple())
    #endsecs = int(endtime.strftime('%s'))
    endsecs = calendar.timegm(endtime.timetuple())
    starts = list(range(startsecs, endsecs, WEEKSECS))
    ends   = list(range(startsecs+WEEKSECS+1, endsecs+WEEKSECS, WEEKSECS))
    if ends[-1] > endsecs:
        ends[-1] = endsecs
    if len(starts) != len(ends):
        raise IndexError('Number of time segment starts/ends does not match for times: "%s" and "%s"' % 
                         (starttime, endtime))

    return [(datetime.utcfromtimestamp(start),
             datetime.utcfromtimestamp(end))
            for start, end in zip(starts, ends)]


class AddEarthquakes:

    def __init__(self, cnn, stime=None, etime=None):

        # check the last earthquake in the db

        if stime is None:
            quakes = cnn.query('SELECT max(date) as mdate FROM earthquakes')
            stime = quakes.dictresult()[0].get('mdate')

            if stime is None:
                # no events in the table, add all
                rinex = cnn.query('SELECT min("ObservationSTime") as mdate FROM rinex')
                stime = rinex.dictresult()[0].get('mdate')

        if etime is None:
            etime = datetime.now(timezone.utc)

        # we used to do a count of how many events would be returned,
        # but it turns out that doing the count takes almost as much time
        # as a query that actually returns the data.  So, here we're just
        # going to split the time segment up into one-week chunks and assume
        # that no individual segment will return more than the 20,000 event limit.
        segments  = getTimeSegments2(stime, etime)

        print('Breaking request into %i segments.' % len(segments))
        print('Requesting data by segment. This might take a few minutes...\n')

        for stime, etime in tqdm(segments, ncols=120):
            # sys.stderr.write('%s - Getting data for %s => %s\n' % (comcat.ShakeDateTime.now(),stime,etime))
            # https://github.com/usgs/libcomcat/blob/master/docs/api.md#Searching
            retry = 0
            eventlist = []
            while retry < 3:
                try:
                    eventlist = libcomcat.search.search(starttime=stime, endtime=etime, minmagnitude=6)
                    break
                except ConnectionError as e:
                    retry += 1
                    tqdm.write('There was a connection error while downloading segment %s %s, retrying %i, %s'
                               % (str(stime), str(etime), retry, str(e)))

            if not len(eventlist):
                tqdm.write('No events found')

            # eventlist is a list of SummaryEvent objects
            for event in eventlist:
                event_date = datetime.strptime(event.time.strftime(TIMEFMT2), TIMEFMT2)

                rs_event = cnn.query('SELECT * FROM earthquakes WHERE id = \'%s\'' % event.id)

                if not len(rs_event.dictresult()):
                    try:
                        # DDG: try to get the moment-tensor solution, if it exists
                        mt = libcomcat.search.get_product_bytes(event.id,
                                                                'moment-tensor',
                                                                'quakeml.xml').decode('utf-8')
                        # convert from XML to DICT
                        mtp = xmltodict.parse(mt)

                        nodal_planes = mtp['q:quakeml']['eventParameters']['event']['focalMechanism']['nodalPlanes']
                        strike1 = float(nodal_planes['nodalPlane1']['strike']['value'])
                        dip1 = float(nodal_planes['nodalPlane1']['dip']['value'])
                        rake1 = float(nodal_planes['nodalPlane1']['rake']['value'])
                        strike2 = float(nodal_planes['nodalPlane2']['strike']['value'])
                        dip2 = float(nodal_planes['nodalPlane2']['dip']['value'])
                        rake2 = float(nodal_planes['nodalPlane2']['rake']['value'])

                    except (libcome.ProductNotFoundError, KeyError, Exception) as e:
                        tqdm.write('Event id %s (%s mag=%.1f) has no moment-tensor solution: %s'
                                   % (event.id, event_date, event.magnitude, str(e)))
                        strike1 = 'NaN'
                        dip1 = 'NaN'
                        rake1 = 'NaN'
                        strike2 = 'NaN'
                        dip2 = 'NaN'
                        rake2 = 'NaN'

                    try:
                        # print('inserting', event)
                        cnn.insert('earthquakes',
                                   id       = event.id,
                                   date     = event_date,
                                   lat      = event.latitude,
                                   lon      = event.longitude,
                                   depth    = event.depth,
                                   mag      = event.magnitude,
                                   strike1  = strike1,
                                   dip1     = dip1,
                                   rake1    = rake1,
                                   strike2  = strike2,
                                   dip2     = dip2,
                                   rake2    = rake2,
                                   location = event.location)
                        tqdm.write('inserting event %s in the database' % event.id)
                    except Exception as e:
                        tqdm.write('Insert failed! %s' % str(e))
                        pass
                else:
                    tqdm.write('event %s %s already exists in the database' % (event.id, event.location))


def main():
    parser = argparse.ArgumentParser(description='Update earthquakes table')
    add_version_argument(parser)
    _ = parser.parse_args()

    cnn = dbConnection.Cnn('gnss_data.cfg')
    AddEarthquakes(cnn)


if __name__ == '__main__':
    main()
