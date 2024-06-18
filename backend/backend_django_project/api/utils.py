import datetime
from . import models
from . import exceptions
import numpy

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

