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
from collections import OrderedDict
from datetime import datetime

# deps
import libcomcat.search


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


WEEKSECS = 86400*7
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
            for start,end in zip(starts,ends)]



class AddEarthquakes():

    def __init__(self, cnn):

        # check the last earthquake in the db
        quakes = cnn.query('SELECT max(date) as mdate FROM earthquakes')

        stime = quakes.dictresult()[0].get('mdate')

        if stime is None:
            # no events in the table, add all
            rinex = cnn.query('SELECT min("ObservationSTime") as mdate FROM rinex')
            stime = rinex.dictresult()[0].get('mdate')

        etime = datetime.utcnow()

        # we used to do a count of how many events would be returned,
        # but it turns out that doing the count takes almost as much time
        # as a query that actually returns the data.  So, here we're just
        # going to split the time segment up into one-week chunks and assume
        # that no individual segment will return more than the 20,000 event limit.
        segments  = getTimeSegments2(stime, etime)

        print('Breaking request into %i segments.\n' % len(segments))

        # @todo remove maxmags, was not used and getEventData always returns 0 on second retvalue
        #maxmags   = 0
        eventlist = []
        for stime, etime in segments:
            # sys.stderr.write('%s - Getting data for %s => %s\n' % (comcat.ShakeDateTime.now(),stime,etime))
            # https://github.com/usgs/libcomcat/blob/master/docs/api.md#Searching
            teventlist = libcomcat.search.search(starttime=stime, endtime=etime,
                                                 minmagnitude=6, maxmagnitude=10)
            eventlist += teventlist

        if not len(eventlist):
            print('No events found.  Exiting.\n')

        # eventlist is a list of SummaryEvent objects
        for event in eventlist:
            event_date = datetime.strptime(event.time.strftime(TIMEFMT2), TIMEFMT2)
            try:
                # print('inserting', event)
                cnn.insert('earthquakes',
                           date  = event_date,
                           lat   = event.latitude,
                           lon   = event.longitude,
                           depth = event.depth,
                           mag=event.magnitude)
                # print('inserted!')
            except:
                # print('failed!')
                pass


def main():
    import dbConnection
    cnn = dbConnection.Cnn('gnss_data.cfg')
    AddEarthquakes(cnn)


if __name__ == '__main__':
    main()
