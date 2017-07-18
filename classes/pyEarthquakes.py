"""
Project: Parallel.Archive
Date: 3/3/17 9:56 AM
Author: Demian D. Gomez

This class is based on the USGS Neicio: the USGS NEIC Python interface and its purpose is to update the table "earthquakes" in the db with the latest events (M >= 6)

"""
from libcomcat import comcat
from datetime import datetime,timedelta
from collections import OrderedDict
import re

TIMEFMT2 = '%Y-%m-%d %H:%M:%S.%f'

def getNewEvent(event, maxmags):
    ibigmag = -1
    bigmag = 0
    for key in event.keys():
        if re.search('mag[0-9]*-type', key):
            ibigmag = event.keys().index(key)
            bigmag = int(re.findall('\d+', key)[0])
    # we can only get away with this because this is an ordereddict
    keys = event.keys()
    values = event.values()
    idx = ibigmag + 1
    for i in range(bigmag + 1, maxmags + 1):
        magkey = 'mag%i' % i
        srckey = 'mag%i-source' % i
        typekey = 'mag%i-type' % i
        keys.insert(idx, magkey)
        keys.insert(idx + 1, srckey)
        keys.insert(idx + 2, typekey)
        values.insert(idx, (float('nan'), '%.1f'))
        values.insert(idx + 1, ('NA', '%s'))
        values.insert(idx + 2, ('NA', '%s'))
        idx += 3

    newevent = OrderedDict(zip(keys, values))
    return newevent

class AddEarthquakes():

    def __init__(self, cnn):

        # check the last earthquake in the db
        quakes = cnn.query('SELECT max(date) as mdate FROM earthquakes')

        stime = quakes.dictresult()[0].get('mdate')

        if stime is None:
            # no events in the table, add all
            rinex = cnn.query('SELECT min("ObservationSTime") as mdate FROM rinex')

            stime = rinex.dictresult()[0].get('mdate')

        etime = comcat.ShakeDateTime.utcnow()

        # we used to do a count of how many events would be returned,
        # but it turns out that doing the count takes almost as much time
        # as a query that actually returns the data.  So, here we're just
        # going to split the time segment up into one-week chunks and assume
        # that no individual segment will return more than the 20,000 event limit.
        segments = comcat.getTimeSegments2(stime, etime)
        eventlist = []
        maxmags = 0

        print('Breaking request into %i segments.\n' % len(segments))

        for stime, etime in segments:
            # sys.stderr.write('%s - Getting data for %s => %s\n' % (comcat.ShakeDateTime.now(),stime,etime))
            teventlist, tmaxmags = comcat.getEventData(starttime=stime, endtime=etime, magrange=(6,10))
            eventlist += teventlist
            if tmaxmags > maxmags:
                maxmags = tmaxmags

        if not len(eventlist):
            print('No events found.  Exiting.\n')

        # eventlist is a list of ordereddict objects
        for event in eventlist:
            event_date = datetime.strptime(event.get('time')[0].strftime(TIMEFMT2),TIMEFMT2)
            try:
                cnn.insert('earthquakes', date=event_date, lat=event.get('lat')[0],
                       lon=event.get('lon')[0], depth=event.get('depth')[0],
                       mag=event.get('mag')[0])
            except Exception as e:
                continue
