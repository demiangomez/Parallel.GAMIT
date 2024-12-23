import datetime
from . import models
from . import exceptions
import numpy

from django.db import connection
import django.utils.timezone
import logging
from django.core.cache import cache
from django.conf import settings
from django.forms.models import model_to_dict
from rest_framework.response import Response
from rest_framework import status
import gzip
from django.core.files.base import ContentFile
from io import BytesIO
import re
import base64
from io import BytesIO
from PIL import Image, ImageOps
import grp
import os

logger = logging.getLogger('django')


def get_actual_image(obj, request):
    """Returns the actual image encoded in base64, optionally as a thumbnail"""
    thumbnail = request.query_params.get(
        'thumbnail', 'false').lower() == 'true' if request else False
    original_quality = request.query_params.get(
        'original_quality', 'false').lower() == 'true' if request else False

    if obj.image and obj.image.name:
        try:
            with open(obj.image.path, 'rb') as photo_file:
                image_data = photo_file.read()
                if thumbnail:
                    image = Image.open(BytesIO(image_data))
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((400, 400))
                    buffer = BytesIO()
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    image.save(buffer, format="JPEG")
                    image_data = buffer.getvalue()
                elif not original_quality:
                    image = Image.open(BytesIO(image_data))
                    image = ImageOps.exif_transpose(image)
                    image.thumbnail((1000, 1000))
                    buffer = BytesIO()
                    if image.mode in ("RGBA", "P"):
                        image = image.convert("RGB")
                    image.save(buffer, format="JPEG")
                    image_data = buffer.getvalue()
                return base64.b64encode(image_data).decode('utf-8')
        except FileNotFoundError:
            return None
    else:
        return None


class EarthquakeUtils:
    @staticmethod
    def get_affected_stations(earthquake):
        # check if earthquake if of type models.Earthquake
        if not isinstance(earthquake, models.Earthquakes):
            raise exceptions.CustomServerErrorExceptionHandler(
                "earthquake must be an instance of models.Earthquake")

        # TODO: IMPLEMENT
        kml_base_64_encoded = b'PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPGttbCB4bWxucz0iaHR0cDovL3d3dy5vcGVuZ2lzLm5ldC9rbWwvMi4yIiB4bWxuczpneD0iaHR0cDovL3d3dy5nb29nbGUuY29tL2ttbC9leHQvMi4yIiB4bWxuczprbWw9Imh0dHA6Ly93d3cub3Blbmdpcy5uZXQva21sLzIuMiIgeG1sbnM6YXRvbT0iaHR0cDovL3d3dy53My5vcmcvMjAwNS9BdG9tIj4KPERvY3VtZW50PgoJPG5hbWU+VW50aXRsZWQgcHJvamVjdDwvbmFtZT4KCTxneDpDYXNjYWRpbmdTdHlsZSBrbWw6aWQ9Il9fbWFuYWdlZF9zdHlsZV8yRUIwQTBCMUU3MzUwRjkwNEMwMSI+CgkJPFN0eWxlPgoJCQk8SWNvblN0eWxlPgoJCQkJPHNjYWxlPjEuMjwvc2NhbGU+CgkJCQk8SWNvbj4KCQkJCQk8aHJlZj5odHRwczovL2VhcnRoLmdvb2dsZS5jb20vZWFydGgvZG9jdW1lbnQvaWNvbj9jb2xvcj0xOTc2ZDImYW1wO2lkPTIwMDAmYW1wO3NjYWxlPTQ8L2hyZWY+CgkJCQk8L0ljb24+CgkJCQk8aG90U3BvdCB4PSI2NCIgeT0iMTI4IiB4dW5pdHM9InBpeGVscyIgeXVuaXRzPSJpbnNldFBpeGVscyIvPgoJCQk8L0ljb25TdHlsZT4KCQkJPExhYmVsU3R5bGU+CgkJCTwvTGFiZWxTdHlsZT4KCQkJPExpbmVTdHlsZT4KCQkJCTxjb2xvcj5mZjJkYzBmYjwvY29sb3I+CgkJCQk8d2lkdGg+NTwvd2lkdGg+CgkJCTwvTGluZVN0eWxlPgoJCQk8UG9seVN0eWxlPgoJCQkJPGNvbG9yPjQwZmZmZmZmPC9jb2xvcj4KCQkJPC9Qb2x5U3R5bGU+CgkJCTxCYWxsb29uU3R5bGU+CgkJCQk8ZGlzcGxheU1vZGU+aGlkZTwvZGlzcGxheU1vZGU+CgkJCTwvQmFsbG9vblN0eWxlPgoJCTwvU3R5bGU+Cgk8L2d4OkNhc2NhZGluZ1N0eWxlPgoJPGd4OkNhc2NhZGluZ1N0eWxlIGttbDppZD0iX19tYW5hZ2VkX3N0eWxlXzFDMTFFQjUxNjkzNTBGOTA0QzAxIj4KCQk8U3R5bGU+CgkJCTxJY29uU3R5bGU+CgkJCQk8SWNvbj4KCQkJCQk8aHJlZj5odHRwczovL2VhcnRoLmdvb2dsZS5jb20vZWFydGgvZG9jdW1lbnQvaWNvbj9jb2xvcj0xOTc2ZDImYW1wO2lkPTIwMDAmYW1wO3NjYWxlPTQ8L2hyZWY+CgkJCQk8L0ljb24+CgkJCQk8aG90U3BvdCB4PSI2NCIgeT0iMTI4IiB4dW5pdHM9InBpeGVscyIgeXVuaXRzPSJpbnNldFBpeGVscyIvPgoJCQk8L0ljb25TdHlsZT4KCQkJPExhYmVsU3R5bGU+CgkJCTwvTGFiZWxTdHlsZT4KCQkJPExpbmVTdHlsZT4KCQkJCTxjb2xvcj5mZjJkYzBmYjwvY29sb3I+CgkJCQk8d2lkdGg+My4zMzMzMzwvd2lkdGg+CgkJCTwvTGluZVN0eWxlPgoJCQk8UG9seVN0eWxlPgoJCQkJPGNvbG9yPjQwZmZmZmZmPC9jb2xvcj4KCQkJPC9Qb2x5U3R5bGU+CgkJCTxCYWxsb29uU3R5bGU+CgkJCQk8ZGlzcGxheU1vZGU+aGlkZTwvZGlzcGxheU1vZGU+CgkJCTwvQmFsbG9vblN0eWxlPgoJCTwvU3R5bGU+Cgk8L2d4OkNhc2NhZGluZ1N0eWxlPgoJPFN0eWxlTWFwIGlkPSJfX21hbmFnZWRfc3R5bGVfMDQ0QUU1OUFEMzM1MEY5MDRDMDEiPgoJCTxQYWlyPgoJCQk8a2V5Pm5vcm1hbDwva2V5PgoJCQk8c3R5bGVVcmw+I19fbWFuYWdlZF9zdHlsZV8xQzExRUI1MTY5MzUwRjkwNEMwMTwvc3R5bGVVcmw+CgkJPC9QYWlyPgoJCTxQYWlyPgoJCQk8a2V5PmhpZ2hsaWdodDwva2V5PgoJCQk8c3R5bGVVcmw+I19fbWFuYWdlZF9zdHlsZV8yRUIwQTBCMUU3MzUwRjkwNEMwMTwvc3R5bGVVcmw+CgkJPC9QYWlyPgoJPC9TdHlsZU1hcD4KCTxQbGFjZW1hcmsgaWQ9IjA4RkZFN0M1RTczNTBGOTA0QzAxIj4KCQk8bmFtZT5VbnRpdGxlZCBwb2x5Z29uPC9uYW1lPgoJCTxMb29rQXQ+CgkJCTxsb25naXR1ZGU+LTkuODc1Nzc3MzA1NDMzODQzPC9sb25naXR1ZGU+CgkJCTxsYXRpdHVkZT4yNC4zNjQyODU0NjQwNzA3ODwvbGF0aXR1ZGU+CgkJCTxhbHRpdHVkZT4zMDMuMzEwMTg3MTkyMzA0NjwvYWx0aXR1ZGU+CgkJCTxoZWFkaW5nPjA8L2hlYWRpbmc+CgkJCTx0aWx0PjA8L3RpbHQ+CgkJCTxneDpmb3Z5PjM1PC9neDpmb3Z5PgoJCQk8cmFuZ2U+MjA2ODY1OC4wMDk3MDEwNzM8L3JhbmdlPgoJCQk8YWx0aXR1ZGVNb2RlPmFic29sdXRlPC9hbHRpdHVkZU1vZGU+CgkJPC9Mb29rQXQ+CgkJPHN0eWxlVXJsPiNfX21hbmFnZWRfc3R5bGVfMDQ0QUU1OUFEMzM1MEY5MDRDMDE8L3N0eWxlVXJsPgoJCTxQb2x5Z29uPgoJCQk8b3V0ZXJCb3VuZGFyeUlzPgoJCQkJPExpbmVhclJpbmc+CgkJCQkJPGNvb3JkaW5hdGVzPgoJCQkJCQktNy45MzEzMzMzODg3NDI1MjIsMjQuMzExNjE2NzI5ODM4MDgsMCAtOC43MjM0NTU2Mzk3NzEzMzQsMjEuNTI4NTM2MDg3NjUwMjUsMCAtMS42NjEzMDc5MjgzMTI5ODgsMTkuOTM5NDc2MzUzMzE4NTIsMCAxLjIyMjU0MzA3MDMwMTY2LDIzLjI2NjAwODc1NjIyODA0LDAgLTEuMDQxNDE0NTIyMTY0ODI5LDI0LjY2MTE0MzMzNjE5NDksMCAtMy44NjIwMTQxNDAyNTE1OTEsMjQuMjE5NTE3NTE2NjE3MjMsMCAtNy45MzEzMzMzODg3NDI1MjIsMjQuMzExNjE2NzI5ODM4MDgsMCAKCQkJCQk8L2Nvb3JkaW5hdGVzPgoJCQkJPC9MaW5lYXJSaW5nPgoJCQk8L291dGVyQm91bmRhcnlJcz4KCQk8L1BvbHlnb24+Cgk8L1BsYWNlbWFyaz4KCTxQbGFjZW1hcmsgaWQ9IjAxRDEyNUQwMDQzNTBGOTE1NzBGIj4KCQk8bmFtZT5VbnRpdGxlZCBwb2x5Z29uPC9uYW1lPgoJCTxMb29rQXQ+CgkJCTxsb25naXR1ZGU+LTguMzI4ODM0MjY5NDk3MDQ3PC9sb25naXR1ZGU+CgkJCTxsYXRpdHVkZT4xOC40Nzg0MjEzMDI0MTUyMTwvbGF0aXR1ZGU+CgkJCTxhbHRpdHVkZT41NDQuNzY3OTI5ODU1MTY5MzwvYWx0aXR1ZGU+CgkJCTxoZWFkaW5nPjA8L2hlYWRpbmc+CgkJCTx0aWx0PjA8L3RpbHQ+CgkJCTxneDpmb3Z5PjM1PC9neDpmb3Z5PgoJCQk8cmFuZ2U+Njk3NzI0NC45Nzk4OTE3Nzc8L3JhbmdlPgoJCQk8YWx0aXR1ZGVNb2RlPmFic29sdXRlPC9hbHRpdHVkZU1vZGU+CgkJPC9Mb29rQXQ+CgkJPHN0eWxlVXJsPiNfX21hbmFnZWRfc3R5bGVfMDQ0QUU1OUFEMzM1MEY5MDRDMDE8L3N0eWxlVXJsPgoJCTxQb2x5Z29uPgoJCQk8b3V0ZXJCb3VuZGFyeUlzPgoJCQkJPExpbmVhclJpbmc+CgkJCQkJPGNvb3JkaW5hdGVzPgoJCQkJCQktMjguOTgxNjQ5ODM5MTg4MjYsMTkuNzMxNzUyOTkxNjk4MiwwIC0xNy40NDI2NTA1NDI3NjgxMSwxMS45MzE1MjMzODc1MTkzLDAgLTMuMzAzNDk4MTk0NTY1NTk3LDkuMTIwMjg3NDM5ODc5Nzk2LDAgMTEuMjYwNDcwNTQ5NzE4NiwxMi4zMDU0OTMwNTAyMDYyMSwwIDE3LjMyMDUyMjMzNjMwNTYxLDE2LjI5MzI2NzIyMzg5NTc1LDAgNi4wMDM5MDM0NDM2MjY1MDgsMjguNjAxNDUxOTk1MDUyNTYsMCAtMS40MzcxNDkwMjEwNDQwNDYsMjkuMzQxODQ3NTg5MTk1MDUsMCAtMTIuOTk1MzA0OTUzNDk4OCwyOS4yNjI5NTg2ODk4Nzk4MSwwIC0xOC4wMTg5MzIxNDEyNzg3OCwyNi41MzkxMTY3MjAxNTIzNywwIC0yOC45ODE2NDk4MzkxODgyNiwxOS43MzE3NTI5OTE2OTgyLDAgCgkJCQkJPC9jb29yZGluYXRlcz4KCQkJCTwvTGluZWFyUmluZz4KCQkJPC9vdXRlckJvdW5kYXJ5SXM+CgkJPC9Qb2x5Z29uPgoJPC9QbGFjZW1hcms+CjwvRG9jdW1lbnQ+Cjwva21sPgo='

        return [{"network_code": "igs", "station_code": "drao"}, {"network_code": "chc", "station_code": "chen"}, {"network_code": "igs", "station_code": "shell"}], kml_base_64_encoded


class StationMetaUtils:
    @staticmethod
    def update_gaps_status_for_all_station_meta_needed():

        records = models.StationMeta.objects.filter(
            has_gaps_update_needed=True).exclude(station__isnull=True)
        previous_time = datetime.datetime.now()

        for record in records:
            StationMetaUtils.update_gaps_status(record)

        logger.info(
            f' \'has_gaps\' status updated. Total stations updated: {records.count()} - Time taken: {(datetime.datetime.now() - previous_time).total_seconds()}')

        cache.delete('update_gaps_status_lock')

    @staticmethod
    def update_gaps_status(station_meta_record):

        models.StationMetaGaps.objects.filter(
            station_meta=station_meta_record).delete()

        station_gaps = StationMetaUtils.get_station_gaps(station_meta_record)

        for gap in station_gaps:
            gap.save()

        if len(station_gaps) > 0:
            station_meta_record.has_gaps = True
        else:
            station_meta_record.has_gaps = False

        station_meta_record.has_gaps_update_needed = False
        station_meta_record.has_gaps_last_update_datetime = django.utils.timezone.now()

        station_meta_record.save()

    @staticmethod
    def get_station_gaps(station_meta):
        """
        This function checks if there rinex data that falls outside the station info window and returns info about the gaps
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

        def get_rinex_count_before_date(station_object, date):

            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT count(*) as rcount FROM rinex_proc 
                            WHERE "NetworkCode" = %s AND "StationCode" = %s AND
                            "ObservationSTime" < %s AND
                            "Completion" >= 0.5""", [station_object.network_code.network_code, station_object.station_code, date])
                rows = dictfetchall(cursor)

                return rows[0]["rcount"]

        def get_rinex_count_after_date(station_object, date):

            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT count(*) as rcount FROM rinex_proc 
                            WHERE "NetworkCode" = %s AND "StationCode" = %s AND
                            "ObservationSTime" > %s AND
                            "Completion" >= 0.5""", [station_object.network_code.network_code, station_object.station_code, date])
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

        def has_gaps_between_stationinfo_records(station_object, station_info_records, station_meta):

            gaps_found = []

            if station_info_records.count() > 1:
                # convert station_info_records to a list
                station_info_records = list(station_info_records)

                # get gaps between stninfo records
                for erecord, srecord in zip(station_info_records[0:-1], station_info_records[1:]):

                    sdate = srecord.date_start
                    edate = erecord.date_end

                    if sdate is None or edate is None:
                        logger.error(
                            f"Station info record has None value for date_start or date_end. Station: {station_object.network_code.network_code}.{station_object.station_code}")
                        continue

                    # if the delta between previous and current session exceeds one second, check if any rinex falls
                    # in that gap
                    if (sdate - edate).total_seconds() > 1:

                        rinex_count = get_rinex_count(
                            station_object, edate, sdate)

                        if rinex_count != 0:
                            gaps_found.append(models.StationMetaGaps.objects.create(station_meta=station_meta, rinex_count=rinex_count, record_start_date_start=srecord.date_start,
                                              record_start_date_end=srecord.date_end, record_end_date_start=erecord.date_start, record_end_date_end=erecord.date_end))

            return gaps_found

        def has_gaps_outside_stationinfo_records(station_object, station_info_records, station_meta):
            """
                There should not be RINEX data outside the station info window
            """
            rnxtbl = get_first_and_last_rinex(station_object)

            gaps_found = []

            if rnxtbl["first_obs"] is not None and station_info_records.count() > 0:

                # to avoid empty stations (no rinex data)
                if station_info_records.first().date_start is not None and rnxtbl["first_obs"] < station_info_records.first().date_start:
                    rinex_count = get_rinex_count_before_date(
                        station_object, station_info_records.first().date_start)
                    gaps_found.append(models.StationMetaGaps.objects.create(station_meta=station_meta, rinex_count=rinex_count,
                                      record_start_date_start=station_info_records.first().date_start, record_start_date_end=station_info_records.first().date_end))

                if station_info_records.last().date_end is not None and rnxtbl["last_obs"] > station_info_records.last().date_end:
                    rinex_count = get_rinex_count_after_date(
                        station_object, station_info_records.last().date_end)
                    gaps_found.append(models.StationMetaGaps.objects.create(station_meta=station_meta, rinex_count=rinex_count,
                                      record_end_date_start=station_info_records.last().date_start, record_end_date_end=station_info_records.last().date_end))

            return gaps_found

        station_object = station_meta.station

        station_info_records = models.Stationinfo.objects.filter(
            network_code=station_object.network_code.network_code, station_code=station_object.station_code)

        # check if station_object has the required fields
        if not hasattr(station_object, 'network_code') or not hasattr(station_object, 'station_code'):
            return []

        gaps_found = []

        gaps_found.extend(has_gaps_between_stationinfo_records(
            station_object, station_info_records, station_meta))
        gaps_found.extend(has_gaps_outside_stationinfo_records(
            station_object, station_info_records, station_meta))

        return gaps_found


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


class UploadMultipleFilesUtils:

    @staticmethod
    def change_file_user_group(file_object, user_group):
        # Get the path of the uploaded file
        file_path = file_object.path

        # Specify the target group name (e.g., 'developers')
        target_group_name = user_group

        # Get the group ID using the group name
        try:
            target_group = grp.getgrnam(target_group_name)
            group_id = target_group.gr_gid

            # Change the group of the file
            # -1 means do not change the user owner
            os.chown(file_path, -1, group_id)
        except KeyError:
            # If running in docker container, it throws an error but in host machine the user group is changed
            pass
        finally:
            # Change the file permissions to give all permissions to the group
            os.chmod(file_path, 0o770)

    @staticmethod
    def upload_multiple_files(view, request, main_object_type):
        if not isinstance(main_object_type, str) or main_object_type not in ('visit', 'station'):
            raise exceptions.CustomServerErrorExceptionHandler(
                "main_object_type must be 'visit' or 'station'")

        files = request.FILES.getlist('file')
        main_objects = request.POST.getlist(main_object_type)
        description = request.POST.getlist('description')

        if len(files) != len(main_objects) or len(files) != len(description):
            raise exceptions.CustomValidationErrorExceptionHandler(
                f"No description or {main_object_type} or filename provided for at least one file")

        try:
            created_files = []
            created_file_instances = set()
            created_file_index = 0
            file_parts_dict = {}

            for file, main_object, description in zip(files, main_objects, description):
                # check if file ends with regex .part followed by a number
                if not bool(re.search(r'part\d+$', file.name)):
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"File {file.name} does not end with 'part' and a number")

                # check that file name has just one .part string on it
                if len(file.name.split('.part')) > 2:
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"File {file.name} has more than one '.part' string on it")

                file_name = file.name.rsplit('.part', 1)[0]
                if file_name not in file_parts_dict:
                    file_parts_dict[file_name] = []
                file_parts_dict[file_name].append(
                    (file, main_object, description))

            for file_name, parts in file_parts_dict.items():
                parts.sort(key=lambda x: int(
                    x[0].name.rsplit('.part', 1)[1]))
                joined_file_content = b''.join(
                    [part[0].read() for part in parts])

                # Decompress the file using gzip
                try:
                    with gzip.GzipFile(fileobj=BytesIO(joined_file_content), mode='rb') as f:
                        decompressed_data = f.read()
                except Exception as e:
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"Failed to decompress file: {str(e)}")

                main_object = parts[0][1]
                description = parts[0][2]
                data = {'file': ContentFile(decompressed_data, name=file_name), main_object_type: main_object,
                        'description': description, 'filename': file_name}

                serializer = view.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                created_file_instance = serializer.save()
                created_file_instances.add(created_file_instance)

                created_files.append({created_file_index: serializer.data})
                created_file_index += 1

        except Exception as e:
            for created_file_instance in created_file_instances:
                created_file_instance.delete()

            return Response({"error_message": {file_name: e.detail if hasattr(e, 'detail') else str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"created_files": [created_file.filename for created_file in created_file_instances]}, status=status.HTTP_201_CREATED)

    def upload_multiple_images(view, request, main_object_type):

        if not isinstance(main_object_type, str) or main_object_type not in ('visit', 'station'):
            raise exceptions.CustomServerErrorExceptionHandler(
                "main_object_type must be 'visit' or 'station'")

        images = request.FILES.getlist('image')
        main_objects = request.POST.getlist(main_object_type)
        description = request.POST.getlist('description')
        names = request.POST.getlist('name')

        if len(images) != len(main_objects) or len(images) != len(description) or len(names) != len(images):
            raise exceptions.CustomValidationErrorExceptionHandler(
                f"No description or {main_object_type} or name provided for at least one image")

        try:
            created_images = []
            created_image_instances = set()
            current_image_index = 0
            image_parts_dict = {}

            for image, main_object, description, name in zip(images, main_objects, description, names):
                # check if image ends with regex .part followed by a number
                if not bool(re.search(r'part\d+$', image.name)):
                    image_name = image.name
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"Image {image.name} does not end with 'part' and a number")

                # check that image name has just one .part string on it
                if len(image.name.split('.part')) > 2:
                    image_name = image.name
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"Image {image.name} has more than one '.part' string on it")

                image_name = image.name.rsplit('.part', 1)[0]
                if image_name not in image_parts_dict:
                    image_parts_dict[image_name] = []
                image_parts_dict[image_name].append(
                    (image, main_object, description, name))

            for image_name, parts in image_parts_dict.items():
                parts.sort(key=lambda x: int(
                    x[0].name.rsplit('.part', 1)[1]))
                joined_image_content = b''.join(
                    [part[0].read() for part in parts])

                # Decompress the image using gzip
                try:
                    with gzip.GzipFile(fileobj=BytesIO(joined_image_content), mode='rb') as f:
                        decompressed_data = f.read()
                except Exception as e:
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"Failed to decompress image: {str(e)}")

                main_object = parts[0][1]
                description = parts[0][2]
                name = parts[0][3]
                data = {'image': ContentFile(decompressed_data, name=image_name), main_object_type: main_object,
                        'description': description, 'name': name}

                serializer = view.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                created_image_instance = serializer.save()
                created_image_instances.add(created_image_instance)

                created_images.append({current_image_index: serializer.data})
                current_image_index += 1

        except Exception as e:
            for created_image_instance in created_image_instances:
                created_image_instance.delete()

            return Response({"error_message": {image_name: e.detail if hasattr(e, 'detail') else str(e)}}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"created_images": [created_image.name for created_image in created_image_instances]}, status=status.HTTP_201_CREATED)


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

                if 'antenna_height' in serializer.validated_data and serializer.validated_data['antenna_height'] is not None:
                    serializer.validated_data['antenna_height'] = numpy.sqrt(numpy.square(float(serializer.validated_data['antenna_height'])) -
                                                                             numpy.square(float(htc.h_offset))) - float(htc.v_offset)
                if 'comments' in serializer.validated_data and isinstance(serializer.validated_data['comments'], str):
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
                                                      numpy.square(float(htc.h_offset))) - float(htc.v_offset)
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


class RinexUtils:
    @staticmethod
    def get_next_station_info(rinex):

        related_station_info = models.Stationinfo.objects.filter(
            network_code=rinex.network_code,
            station_code=rinex.station_code
        ).order_by('date_start')

        if related_station_info.count() == 0:
            raise exceptions.CustomValidationErrorExceptionHandler(
                'No station info found for %s.%s' % (rinex.network_code, rinex.station_code))

        station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex = RinexUtils._clasify_station_info_from_rinex(
            rinex, related_station_info)

        if len(station_info_after_rinex) > 0:
            return station_info_after_rinex[0]
        else:
            return None

    @staticmethod
    def get_previous_station_info(rinex):

        related_station_info = models.Stationinfo.objects.filter(
            network_code=rinex.network_code,
            station_code=rinex.station_code
        ).order_by('date_start')

        if related_station_info.count() == 0:
            raise exceptions.CustomValidationErrorExceptionHandler(
                'No station info found for %s.%s' % (rinex.network_code, rinex.station_code))

        station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex = RinexUtils._clasify_station_info_from_rinex(
            rinex, related_station_info)

        if len(station_info_before_rinex) > 0:
            return station_info_before_rinex[-1]
        else:
            return None

    @staticmethod
    def get_rinex_with_status(rinex_list, filters):
        if len(rinex_list) > 0:
            station_info_from_station = list(RinexUtils._get_station_info_from_station(
                rinex_list[0].network_code, rinex_list[0].station_code))

            rinex_with_related_station_info = []

            for rinex in rinex_list:
                station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex = RinexUtils._clasify_station_info_from_rinex(
                    rinex, station_info_from_station)

                rinex.has_station_info = len(station_info_containing_rinex) > 0

                rinex.has_multiple_station_info_gap = RinexUtils._get_has_multiple_station_info_gap(
                    rinex, station_info_from_station)

                rinex.metadata_mismatch = RinexUtils._check_metadata_mismatch(
                    rinex, station_info_containing_rinex)

                rinex.gap_type = RinexUtils._get_gap_type(
                    rinex, station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex)

                rinex_with_related_station_info.append(
                    (rinex, station_info_containing_rinex))

            rinex_list = RinexUtils._group_by_same_date_range(
                rinex_with_related_station_info)

            rinex_list = RinexUtils._group_by_date_range_distance(rinex_list)

            rinex_list = RinexUtils._convert_to_correct_format(rinex_list)

            rinex_list = RinexUtils._filter_rinex(rinex_list, filters)

            return rinex_list
        else:
            return []

    @staticmethod
    def _is_filtered(rinex, filters):
        datetime_string_format = "%Y-%m-%d %H:%M"

        if filters["observation_doy"] != None and str(filters["observation_doy"]) not in str(rinex["observation_doy"]):
            return True
        elif filters["observation_f_year"] != None and str(filters["observation_f_year"]) not in str(round(float(rinex["observation_f_year"]), 3)):
            return True
        elif filters["observation_s_time_since"] != None and datetime.datetime.strptime(filters["observation_s_time_since"], datetime_string_format).replace(second=0) > rinex["observation_s_time"].replace(second=0):
            return True
        elif filters["observation_s_time_until"] != None and datetime.datetime.strptime(filters["observation_s_time_until"], datetime_string_format).replace(second=0) < rinex["observation_s_time"].replace(second=0):
            return True
        elif filters["observation_e_time_since"] != None and datetime.datetime.strptime(filters["observation_e_time_since"], datetime_string_format).replace(second=0) > rinex["observation_e_time"].replace(second=0):
            return True
        elif filters["observation_e_time_until"] != None and datetime.datetime.strptime(filters["observation_e_time_until"], datetime_string_format).replace(second=0) < rinex["observation_e_time"].replace(second=0):
            return True
        elif filters["observation_year"] != None and str(filters["observation_year"]) not in str(rinex["observation_year"]):
            return True
        elif filters["antenna_dome"] != None and str(filters["antenna_dome"]) not in str(rinex["antenna_dome"]):
            return True
        elif filters["antenna_offset"] != None and str(filters["antenna_offset"]) not in str(rinex["antenna_offset"]):
            return True
        elif filters["antenna_serial"] != None and str(filters["antenna_serial"]) not in str(rinex["antenna_serial"]):
            return True
        elif filters["antenna_type"] != None and str(filters["antenna_type"]) not in str(rinex["antenna_type"]):
            return True
        elif filters["receiver_fw"] != None and str(filters["receiver_fw"]) not in str(rinex["receiver_fw"]):
            return True
        elif filters["receiver_serial"] != None and str(filters["receiver_serial"]) not in str(rinex["receiver_serial"]):
            return True
        elif filters["receiver_type"] != None and str(filters["receiver_type"]) not in str(rinex["receiver_type"]):
            return True
        elif filters["completion_operator"] != None and filters["completion"] != None and RinexUtils._filter_rinex_by_completion(rinex, filters["completion_operator"], filters["completion"]):
            return True
        elif filters["interval"] != None and str(filters["interval"]) not in str(rinex["interval"]):
            return True
        else:
            return False

    @staticmethod
    def _filter_rinex_by_completion(rinex, completion_operator, completion):
        if completion_operator.upper().strip() == "GREATER_THAN":
            return float(rinex["completion"]) <= float(completion)
        elif completion_operator.upper().strip() == "LESS_THAN":
            return float(rinex["completion"]) >= float(completion)
        elif completion_operator.upper().strip() == "EQUAL":
            return float(rinex["completion"]) != float(completion)
        else:
            return False

    @staticmethod
    def _filter_rinex(rinex_list, filters):
        for first_groups in rinex_list:
            for second_groups in first_groups["rinex"]:
                for rinex in second_groups["rinex"]:
                    rinex["filtered"] = RinexUtils._is_filtered(rinex, filters)

        return rinex_list

    @staticmethod
    def _get_station_info_from_station(network_code, station_code):
        return models.Stationinfo.objects.filter(network_code=network_code, station_code=station_code).order_by('date_start')

    @staticmethod
    def _get_has_multiple_station_info_gap(rinex, station_info_list):
        station_info_containing_start_date = None
        station_info_containing_end_date = None

        for station_info in station_info_list:
            station_info_date_end = station_info.date_end if station_info.date_end is not None else datetime.datetime(
                9999, 12, 31)

            if station_info.date_start <= rinex.observation_s_time and station_info_date_end >= rinex.observation_s_time:
                station_info_containing_start_date = station_info
            if station_info.date_start <= rinex.observation_e_time and station_info_date_end >= rinex.observation_e_time:
                station_info_containing_end_date = station_info

        return station_info_containing_start_date is not None and station_info_containing_end_date is not None and station_info_containing_start_date != station_info_containing_end_date

    @staticmethod
    def _convert_rinex_to_dict(rinex):
        has_station_info = rinex.has_station_info
        has_multiple_station_info_gap = rinex.has_multiple_station_info_gap
        metadata_mismatch = rinex.metadata_mismatch
        gap_type = rinex.gap_type

        rinex = model_to_dict(rinex)

        rinex['has_station_info'] = has_station_info
        rinex['has_multiple_station_info_gap'] = has_multiple_station_info_gap
        rinex['metadata_mismatch'] = metadata_mismatch
        rinex['gap_type'] = gap_type

        return rinex

    @staticmethod
    def _convert_stationinfo_to_dict(stationinfo):

        stationinfo = {"api_id": stationinfo.api_id,
                       "date_start": stationinfo.date_start, "date_end": stationinfo.date_end}

        return stationinfo

    @staticmethod
    def _convert_to_correct_format(rinex_list):
        # Converts to a list of dict and sort all the stationinfo lists

        list_dict = []

        for stationinfo_super_set, rinex_with_related_stationinfo_list in rinex_list:

            stationinfo_super_set_list = list(stationinfo_super_set)
            stationinfo_super_set_list.sort(key=lambda x: x.date_start)

            correct_format_super_group = {
                'related_station_info': [RinexUtils._convert_stationinfo_to_dict(stationinfo_super_set_list_element) for stationinfo_super_set_list_element in stationinfo_super_set_list],
                'rinex': [
                    {
                        'rinex': [RinexUtils._convert_rinex_to_dict(rinex_element) for rinex_element in rinex],
                        'related_station_info': [RinexUtils._convert_stationinfo_to_dict(related_station_info_element) for related_station_info_element in sorted(list(stationinfo_from_rinex), key=lambda x: x.date_start)]
                    }
                    for rinex, stationinfo_from_rinex in rinex_with_related_stationinfo_list
                ]
            }
            list_dict.append(correct_format_super_group)

        return list_dict

    @staticmethod
    def _group_by_same_date_range(rinex_list):

        rinex_list.sort(key=lambda x: x[0].observation_s_time)

        rinex_groups = []

        for rinex, station_info in rinex_list:
            if len(rinex_groups) == 0:
                rinex_groups.append([(rinex, station_info)])
            else:
                if rinex_groups[-1][0][0].observation_s_time == rinex.observation_s_time and rinex_groups[-1][0][0].observation_e_time == rinex.observation_e_time:
                    rinex_groups[-1].append((rinex, station_info))
                else:
                    rinex_groups.append([(rinex, station_info)])

        # group station info from same rinex group and remove duplicates

        rinex_groups_with_station_info = []

        for rinex_group in rinex_groups:
            station_info_set = set()
            rinexs = []

            for rinex, station_info in rinex_group:
                rinexs.append(rinex)
                station_info_set.update(station_info)

            rinex_groups_with_station_info.append((rinexs, station_info_set))

        return rinex_groups_with_station_info

    @staticmethod
    def _group_by_date_range_distance(rinex_list):
        # iterate over rinex_list with format [([rinex1_1, rinex1_2], set(stationinfo1, stationinfo2)), ([rinex2_1, rinex2_2], set(stationinfo1, stationinfo2))]
        # take the first rinex of each group compare them like if rinex2_1.observation_s_time - rinex1_1.observation_e_time) < settings.RINEX_STATUS_DATE_SPAN_SECONDS
        # if the condition is met, add all rinex and stationinfo from both groups into a new group.
        # continue until a rinex doesn't fulfill the condition. Then, that rinex will be the first one of the next group.

        rinex_list = list(rinex_list)

        rinex_groups = []

        for rinex_group, station_info_set in rinex_list:
            if len(rinex_groups) == 0:
                rinex_groups.append(
                    (station_info_set.copy(), [(rinex_group, station_info_set.copy())]))
            else:
                if (rinex_group[0].observation_s_time - rinex_groups[-1][1][-1][0][0].observation_e_time).total_seconds() < float(settings.RINEX_STATUS_DATE_SPAN_SECONDS):

                    rinex_groups[-1][1].append((rinex_group,
                                               station_info_set.copy()))
                    rinex_groups[-1][0].update(station_info_set)

                else:
                    rinex_groups.append(
                        (station_info_set.copy(), [(rinex_group, station_info_set)]))

        return rinex_groups

    @staticmethod
    def _get_gap_type(rinex, station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex):
        if not hasattr(rinex, 'has_multiple_station_info_gap'):
            raise exceptions.CustomServerErrorExceptionHandler(
                'Rinex object must have the attribute has_multiple_station_info_gap')

        if rinex.has_multiple_station_info_gap:
            return None
        elif len(station_info_before_rinex) == 0 and len(station_info_containing_rinex) == 0 and len(station_info_after_rinex) == 0:
            return "NO STATION INFO"
        elif len(station_info_containing_rinex) > 0:
            return None
        else:
            if len(station_info_before_rinex) == 0:
                return "BEFORE FIRST STATIONINFO"
            elif len(station_info_after_rinex) == 0:
                return "AFTER LAST STATIONINFO"
            else:
                return "BETWEEN TWO STATIONINFO"

    @staticmethod
    def _check_metadata_mismatch(rinex, station_info_containing_rinex):
        if len(station_info_containing_rinex) > 0:
            mismatches = []

            if rinex.receiver_type != station_info_containing_rinex[0].receiver_code:
                mismatches.append('receiver_type')

            if rinex.receiver_serial != station_info_containing_rinex[0].receiver_serial:
                mismatches.append('receiver_serial')

            if rinex.receiver_fw != station_info_containing_rinex[0].receiver_firmware:
                mismatches.append('receiver_fw')

            if rinex.antenna_type != station_info_containing_rinex[0].antenna_code:
                mismatches.append('antenna_type')

            if rinex.antenna_serial != station_info_containing_rinex[0].antenna_serial:
                mismatches.append('antenna_serial')

            if rinex.antenna_dome != station_info_containing_rinex[0].radome_code:
                mismatches.append('antenna_dome')

            if rinex.antenna_offset != station_info_containing_rinex[0].antenna_height:
                mismatches.append('antenna_offset')

            return mismatches
        else:
            return []

    @staticmethod
    def _clasify_station_info_from_rinex(rinex, station_info_from_station):
        station_info_before_rinex = []
        station_info_containing_rinex = []
        station_info_after_rinex = []

        for station_info in station_info_from_station:

            station_info_date_end = station_info.date_end if station_info.date_end is not None else datetime.datetime(
                9999, 12, 31)

            if station_info.date_start < rinex.observation_s_time and station_info_date_end < rinex.observation_s_time:
                station_info_before_rinex.append(station_info)
            elif rinex.observation_s_time >= station_info.date_start and rinex.observation_s_time <= station_info_date_end and rinex.observation_e_time > station_info_date_end:
                station_info_before_rinex.append(station_info)
            elif rinex.observation_s_time < station_info.date_start and rinex.observation_e_time >= station_info.date_start and rinex.observation_e_time <= station_info_date_end:
                station_info_after_rinex.append(station_info)
            elif station_info.date_start <= rinex.observation_s_time and station_info_date_end >= rinex.observation_e_time:
                station_info_containing_rinex.append(station_info)
            elif station_info.date_start > rinex.observation_e_time:
                station_info_after_rinex.append(station_info)

        return station_info_before_rinex, station_info_containing_rinex, station_info_after_rinex
