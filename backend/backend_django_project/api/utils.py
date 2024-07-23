import datetime
from . import models
from . import exceptions
import numpy

from django.db import connection
import django.utils.timezone

class StationMetaUtils:
    @staticmethod
    def update_has_gaps_status():
            
            records = models.StationMeta.objects.all()
            previous_time = datetime.datetime.now()
            records_updated_count = 0

            for record in records:
                
                if hasattr(record, 'station') and record.has_gaps_update_needed:
                    records_updated_count += 1
                    record.has_gaps = StationMetaUtils.station_has_gaps(record.station)
                    record.has_gaps_update_needed = False
                    record.has_gaps_last_update_datetime = django.utils.timezone.now()
                
                    record.save()
            
            if records_updated_count > 0:
                print(' \'has_gaps\' status updated. Total stations updated: ', records_updated_count, ' - Time taken: ', (datetime.datetime.now() - previous_time).total_seconds())

    @staticmethod
    def station_has_gaps(station_object):
        """
        This function checks any missing station info (gaps) or any data outside the first and last station info
        """

        def dictfetchall(cursor):
            "Return all rows from a cursor as a dict"
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
    ]

        def get_rinex_count(station_object, edate, sdate):
                                    
            with connection.cursor() as cursor:
                cursor.execute(
                            """SELECT count(*) as rcount FROM rinex_proc 
                            WHERE "NetworkCode" = %s AND "StationCode" = %s AND
                            "ObservationETime" > %s AND "ObservationSTime" < %s AND
                            "Completion" >= 0.5""", [station_object.network_code.network_code, station_object.station_code, edate, sdate])
                rows = dictfetchall(cursor)

                return rows[0]["rcount"]
            
        def get_first_and_last_rinex(station_object):

            with connection.cursor() as cursor:
                cursor.execute(
                            """SELECT min("ObservationSTime") as first_obs, max("ObservationSTime") as last_obs
                            FROM rinex_proc WHERE "NetworkCode" = %s AND "StationCode" = %s
                            AND "Completion" >= 0.5""", [station_object.network_code.network_code, station_object.station_code])
                rows = dictfetchall(cursor)

                return rows[0]

        def has_gaps_between_stationinfo_records(station_object, station_info_records):
            
            if station_info_records.count() > 1:
                # convert station_info_records to a list
                station_info_records = list(station_info_records)
                # get gaps between stninfo records
                for erecord, srecord in zip(station_info_records[0:-1], station_info_records[1:]):

                    sdate = srecord.date_start
                    edate = erecord.date_end

                    # if the delta between previous and current session exceeds one second, check if any rinex falls
                    # in that gap
                    if (sdate - edate).total_seconds() > 1:

                        if get_rinex_count(station_object, edate, sdate) != 0:
                            return True

            return False

        def has_gaps_outside_stationinfo_records(station_object, station_info_records):
            """
                There should not be RINEX data outside the station info window
            """
            rnxtbl = get_first_and_last_rinex(station_object)

            if rnxtbl["first_obs"] is not None and station_info_records.count() > 0:

                # to avoid empty stations (no rinex data)
                if station_info_records.first().date_start is not None and rnxtbl["first_obs"] < station_info_records.first().date_start:
                    return True
                
                if station_info_records.last().date_end is not None and rnxtbl["first_obs"] > station_info_records.last().date_end:
                    return True

            return False

        station_info_records = models.Stationinfo.objects.filter(
            network_code=station_object.network_code.network_code, station_code=station_object.station_code)

        # check if station_object has the required fields
        if not hasattr(station_object, 'network_code') or not hasattr(station_object, 'station_code'):
            return False

        return (has_gaps_between_stationinfo_records(station_object, station_info_records) or has_gaps_outside_stationinfo_records(station_object, station_info_records))


class PageUtils:
    def group_pages_by_url(pages):
        """
        Group pages by url
        """

        pages_by_url = {}

        for page in pages:
            url = page['url']
            if url not in pages_by_url:
                pages_by_url[url] = []
            pages_by_url[url].append(page)

        return pages_by_url


class EndpointsClusterUtils:
    def group_clusters_by_resource(clusters):
        """
        Group clusters by resource
        """

        clusters_by_resource = {}

        for cluster in clusters:
            resource = cluster['resource']['name']
            if resource not in clusters_by_resource:
                clusters_by_resource[resource] = []
            clusters_by_resource[resource].append(cluster)

        return clusters_by_resource


class StationInfoUtils:
    @staticmethod
    def get_same_station_records(serializer, get_queryset, get_object=None):

        if get_object != None:
            network_code = get_object().network_code
            station_code = get_object().station_code
        else:
            network_code = serializer.validated_data['network_code']
            station_code = serializer.validated_data['station_code']

        return get_queryset().filter(network_code=network_code, station_code=station_code)

    @staticmethod
    def get_records_that_overlap(serializer, get_queryset, get_object=None):
        # check if the incoming record is between any existing record
        records_that_overlap = []

        q_end = None

        q_start = serializer.validated_data['date_start']

        if 'date_end' in serializer.validated_data:
            q_end = serializer.validated_data['date_end']

        for record in StationInfoUtils.get_same_station_records(serializer, get_queryset, get_object):
            r_start = record.date_start

            r_end = record.date_end

            earliest_end = min(datetime.datetime(9999, 12, 31) if q_end == None else q_end, datetime.datetime(
                9999, 12, 31) if r_end == None else r_end)
            latest_start = max(q_start, r_start)

            if (earliest_end - latest_start).total_seconds() > 0:
                records_that_overlap.append(record)

        return records_that_overlap

    @staticmethod
    def return_stninfo(serializer=None, record=None):
        """
        return a station information string to write to a file (without header
        :return: a string in station information format
        """
        if serializer != None:
            StationInfoUtils.to_dharp(serializer=serializer)
            values = serializer.validated_data.values()
        elif record != None:
            StationInfoUtils.to_dharp(record=record)
            values = record.values()

        return '\n'.join([str(value) for value in values])

    @staticmethod
    def to_dharp(serializer=None, record=None):
        """
        function to convert the current height code to DHARP
        :return: DHARP height
        """
        if serializer != None:
            StationInfoUtils.to_dharp_from_serializer(serializer)
        elif record != None:
            StationInfoUtils.to_dharp_from_record(record)
        else:
            raise exceptions.CustomValidationErrorExceptionHandler(
                'Serializer or record must be provided to convert height code to DHARP.')

    @staticmethod
    def to_dharp_from_serializer(serializer):

        if serializer.validated_data['height_code'] != 'DHARP':
            try:
                htc = models.GamitHtc.objects.get(
                    antenna_code=serializer.validated_data['antenna_code'], height_code=serializer.validated_data['height_code'])

            except models.GamitHtc.DoesNotExist:

                raise exceptions.CustomValidationErrorExceptionHandler('%s.%s: %s -> Could not translate height code %s to DHARP. '
                                                                       'Check the height codes table.'
                                                                       % (serializer.validated_data['network_code'],
                                                                          serializer.validated_data['station_code'],
                                                                          serializer.validated_data['antenna_code'],
                                                                          serializer.validated_data['height_code']))
            else:

                if 'antenna_height' in serializer.validated_data:
                    serializer.validated_data['antenna_height'] = numpy.sqrt(numpy.square(float(serializer.validated_data['antenna_height'])) -
                                                                             numpy.square(float(htc[0]['h_offset']))) - float(htc[0]['v_offset'])
                if 'comments' in serializer.validated_data:
                    serializer.validated_data['comments'] = serializer.validated_data['comments'] + '\nChanged from %s to DHARP by Django API.\n' \
                        % serializer.validated_data['height_code']
                else:
                    serializer.validated_data['comments'] = 'Changed from %s to DHARP by Django API.\n' % serializer.validated_data['height_code']

                serializer.validated_data['height_code'] = 'DHARP'

    @staticmethod
    def to_dharp_from_record(record):

        if record['height_code'] != 'DHARP':
            try:
                htc = models.GamitHtc.objects.get(
                    antenna_code=record['antenna_code'], height_code=record['height_code'])

            except models.GamitHtc.DoesNotExist:

                raise exceptions.CustomValidationErrorExceptionHandler('%s.%s: %s -> Could not translate height code %s to DHARP. '
                                                                       'Check the height codes table.'
                                                                       % (record['network_code'],
                                                                          record['station_code'],
                                                                          record['antenna_code'],
                                                                          record['height_code']))
            else:

                record['antenna_height'] = numpy.sqrt(numpy.square(float(record['antenna_height'])) -
                                                      numpy.square(float(htc[0]['h_offset']))) - float(htc[0]['v_offset'])
                if record['comments'] is not None:
                    record['comments'] = record['comments'] + '\nChanged from %s to DHARP by Django API.\n' \
                        % record['height_code']
                else:
                    record['comments'] = 'Changed from %s to DHARP by Django API.\n' % record['height_code']

                record['height_code'] = 'DHARP'

    def record_to_str(record):
        return str(StationInfoUtils.get_record_values(record=record))

    def get_record_values(get_object=None, record=None):
        if record != None:
            values = {field.name: getattr(record, field.name)
                      for field in models.Stationinfo._meta.get_fields()}

        elif get_object != None:
            values = {field.name: getattr(get_object(
            ), field.name) for field in models.Stationinfo._meta.get_fields()}

        return values
