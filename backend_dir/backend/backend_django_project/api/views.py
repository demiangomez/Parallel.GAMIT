from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from . import models
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from . import serializers
from . import filters
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiResponse
from rest_framework.response import Response
from . import exceptions
import platform
import inspect
import traceback
import re
import numpy
import datetime
from . import utils
import rest_framework.exceptions
from rest_framework.parsers import MultiPartParser
from django.http import Http404, HttpResponseServerError
from rest_framework.views import APIView
from django.conf import settings
import os.path
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
import base64
from django.forms.models import model_to_dict
from django.core.cache import cache
import time
from .tasks import update_gaps_status
from django.core.files.storage import default_storage
from pgamit import pyStationInfo, dbConnection, pyDate, pyETM
from pgamit import Utils as pyUtils
import dateutil.parser
from io import BytesIO


def response_is_paginated(response_data):
    return type(response_data) == dict


class AddCountMixin:

    def list(request, *args, **kwargs):
        """If the response status is 200, returns these additional fields:
        'count': the number of objects retrieved after pagination (if required) and after filtering,
        'total_count': the number of objects before pagination (if required) and after filtering
        """

        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:

            if response_is_paginated(response.data):

                response.data = {"count": len(response.data["data"]),
                                 "total_count": response.data["total_count"],
                                 "data": response.data["data"]}
            else:
                len_response_data = len(response.data)
                response.data = {"count": len_response_data,
                                 "total_count": len_response_data, "data": response.data}

        return response


@extend_schema(description="")
class CustomListAPIView(AddCountMixin, generics.ListAPIView):
    None


@extend_schema(description="")
class CustomListCreateAPIView(AddCountMixin, generics.ListCreateAPIView):
    None


class UserPhoto(APIView):
    serializer_class = serializers.DummySerializer

    def get_object(self, pk):
        try:
            user = models.User.objects.get(pk=pk)
        except models.User.DoesNotExist:
            raise Http404
        else:
            if not user.photo:
                raise Http404
            else:
                return user.photo.path

    @extend_schema(responses={200: OpenApiResponse(description="Image returned, content type is image/jpeg")})
    def get(self, request, pk, format=None):
        relative_photo_path = self.get_object(pk)

        absolute_photo_path = os.path.join(
            settings.MEDIA_ROOT, relative_photo_path)

        try:
            with open(absolute_photo_path, 'rb') as file:
                return Response({"photo": base64.b64encode(file.read()).decode('utf-8')})
        except IOError:
            raise exceptions.CustomServerErrorExceptionHandler(
                "Error reading the photo.")


class UserList(CustomListCreateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = serializers.UserSerializer
    parser_classes = [MultiPartParser]


class UserDetail(generics.RetrieveUpdateAPIView):
    queryset = get_user_model().objects.all()
    serializer_class = serializers.UserSerializer
    parser_classes = [MultiPartParser]


class RoleList(CustomListCreateAPIView):
    queryset = models.Role.objects.all()
    serializer_class = serializers.RoleSerializer


class RoleDetail(generics.RetrieveUpdateAPIView):
    queryset = models.Role.objects.all()
    serializer_class = serializers.RoleSerializer

    def update(self, request, *args, **kwargs):
        """
            Deactivate role's users if the role is deactivated.
        """
        is_active_before_update = self.get_object().is_active

        response = super().update(request, *args, **kwargs)

        is_active_after_update = self.get_object().is_active

        if (is_active_before_update == True and is_active_after_update == False):
            models.User.objects.filter(
                role=self.get_object().id).update(is_active=False)

        return response


class EndpointList(CustomListCreateAPIView):
    queryset = models.Endpoint.objects.all()
    serializer_class = serializers.EndpointSerializer


class EndpointDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Endpoint.objects.all()
    serializer_class = serializers.EndpointSerializer


class EndpointsClusterList(CustomListCreateAPIView):
    queryset = models.EndPointsCluster.objects.all()
    serializer_class = serializers.EndpointsClusterSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.EndpointsClusterFilter

    def list(request, *args, **kwargs):
        """ If response status is 200, group clusters by resource"""

        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:

            response.data['data'] = utils.EndpointsClusterUtils.group_clusters_by_resource(
                response.data['data'])

        return response


class EndpointsClusterDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.EndPointsCluster.objects.all()
    serializer_class = serializers.EndpointsClusterSerializer


class NetworkList(CustomListCreateAPIView):
    queryset = models.Networks.objects.all()
    serializer_class = serializers.NetworkSerializer


class NetworkDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Networks.objects.all()
    serializer_class = serializers.NetworkSerializer


class MonumentTypeList(CustomListCreateAPIView):
    queryset = models.MonumentType.objects.all()
    serializer_class = serializers.MonumentTypeSerializer


class MonumentTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.MonumentType.objects.all()
    serializer_class = serializers.MonumentTypeSerializer


class ReceiverList(CustomListCreateAPIView):
    queryset = models.Receivers.objects.all()
    serializer_class = serializers.ReceiverSerializer


class ReceiverDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Receivers.objects.all()
    serializer_class = serializers.ReceiverSerializer


class AntennaList(CustomListCreateAPIView):
    queryset = models.Antennas.objects.all()
    serializer_class = serializers.AntennaSerializer


class AntennaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Antennas.objects.all()
    serializer_class = serializers.AntennaSerializer


class StationList(CustomListCreateAPIView):
    queryset = models.Stations.objects.select_related('network_code').all()
    serializer_class = serializers.StationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StationFilter

    def list(request, *args, **kwargs):
        """If the response status is 200, add some fields of the related stationmeta object"""

        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:

            station_meta_query = models.StationMeta.objects.values_list(
                'station', 'has_gaps', 'has_stationinfo', 'id', 'status__name', 'station_type__name')

            station_meta_gaps = models.StationMetaGaps.objects.select_related(
                'station_meta').all()

            station_meta_gaps_dict = {station_meta_object[3]: [
            ] for station_meta_object in station_meta_query}

            for gap in station_meta_gaps:
                station_meta_gaps_dict[gap.station_meta.id].append(
                    model_to_dict(gap))

            station_meta_dict = {
                station_meta_object[0]: (
                    station_meta_object[1],
                    station_meta_object[2],
                    station_meta_object[3],
                    station_meta_object[4],
                    station_meta_object[5]
                )
                for station_meta_object in station_meta_query
            }

            # Update the response data with the information from station_meta_dict
            for station in response.data["data"]:
                if 'api_id' in station:

                    if station['api_id'] in station_meta_dict:
                        has_gaps, has_stationinfo, station_meta_id, station_status_name, station_type_name = station_meta_dict[
                            station['api_id']]
                        station["has_gaps"] = has_gaps
                        station["has_stationinfo"] = has_stationinfo
                        station["gaps"] = station_meta_gaps_dict[station_meta_id]
                        station["status"] = station_status_name
                        station["type"] = station_type_name

        return response


class StationDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Stations.objects.all()
    serializer_class = serializers.StationSerializer

    def retrieve(self, request, *args, **kwargs):
        """If response is 200, add some related station meta fields"""

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:

            if 'api_id' in response.data:

                stationmeta = models.StationMeta.objects.get(
                    station=response.data['api_id'])
                response.data["has_gaps"] = stationmeta.has_gaps
                response.data["has_stationinfo"] = stationmeta.has_stationinfo
                response.data["gaps"] = [model_to_dict(
                    gap) for gap in stationmeta.stationmetagaps_set.all()]
                response.data["status"] = stationmeta.status.name
                response.data["type"] = stationmeta.station_type.name

        return response


class StationCodesList(CustomListAPIView):
    queryset = models.Stations.objects.none()
    serializer_class = serializers.StationCodeSerializer

    def get_queryset(self):
        return models.Stations.objects.all().filter(network_code__api_id=self.kwargs["network_api_id"]).values("station_code")

    def list(request, *args, **kwargs):
        """If the response status is 200, returns a list of station codes instead of an list of objects"""

        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:

            response.data["data"] = [station["station_code"]
                                     for station in response.data["data"]]

        return response


class TimeSeries(CustomListAPIView):
    serializer_class = serializers.RinexSerializer

    def get_queryset(self, pk):
        return None

    def _get_required_param(self, request, params, param_name):
        param_value = request.query_params.get(param_name)

        # param_value can't be None or an empty string
        if param_value is not None and (isinstance(param_value, str) and param_value != ""):
            params[param_name] = param_value
        else:
            raise exceptions.CustomValidationErrorExceptionHandler(
                "'" + param_name + "'" + " parameter is required.")

    def _convert_to_bool(self, params, param_name):
        param_value = params[param_name].strip().lower()

        if param_value in ("true", "false"):
            params[param_name] = param_value == "true"
        else:
            raise exceptions.CustomValidationErrorExceptionHandler(
                "'" + param_name + "'" + " parameter is not a valid boolean.")

    def _check_params(self, request):
        params = {}

        for param_name in ("solution", "residuals", "missing_data", "plot_outliers", "plot_auto_jumps",
                           "no_model", "remove_jumps", "remove_polynomial"):
            self._get_required_param(request, params, param_name)

        self._get_dates_param(request, params)

        for param_name in ("residuals", "missing_data", "plot_outliers", "plot_auto_jumps", "no_model", "remove_jumps", "remove_polynomial"):
            self._convert_to_bool(params, param_name)

        params["solution"] = params["solution"].strip().upper()

        if params["solution"] not in ("PPP", "GAMIT"):
            raise exceptions.CustomValidationErrorExceptionHandler(
                "'solution' parameter must be either 'PPP' or 'GAMIT'")

        if params["solution"] == "GAMIT":
            self._get_required_param(request, params, "stack")

        return params

    def _deprecated_check_params(self, request, params):

        date_start = request.query_params.get("date_start")
        date_end = request.query_params.get("date_end")

        for param_name, param_value in (("date_start", date_start), ("date_end", date_end)):

            if param_value is not None:
                try:
                    date = dateutil.parser.parse(param_value)
                except (dateutil.parser.ParserError, ValueError):
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        "'" + param_name + "'" + " parameter has a wrong format.")
                else:
                    params[param_name] = date
                    print(f"{type(date)=}")

        if isinstance(params["date_start"], datetime.datetime) and isinstance(params["date_end"], datetime.datetime):
            if params["date_start"] > params["date_end"]:
                raise exceptions.CustomValidationErrorExceptionHandler(
                    "'date_start' parameter can't be greater than 'date_end' parameter.")

    def _get_dates_param(self, request, params):
        date_start = request.query_params.get("date_start")
        date_end = request.query_params.get("date_end")

        time_window = []

        if date_start is not None:
            time_window.append(date_start)
        if date_end is not None:
            time_window.append(date_end)

        dates = None
        try:
            if len(time_window) > 0:
                if len(time_window) == 1:
                    try:
                        dates = pyUtils.process_date(
                            time_window, missing_input=None, allow_days=False)
                        dates = (dates[0].fyear, )
                    except ValueError:
                        # an integer value
                        dates = float(time_window[0])
                else:
                    dates = pyUtils.process_date(time_window)
                    dates = (dates[0].fyear, dates[1].fyear)
        except Exception as e:
            raise exceptions.CustomValidationErrorExceptionHandler(
                e.detail if hasattr(e, 'detail') else str(e))

        params["dates"] = dates

    def _get_station(self, station_api_id):
        try:
            station = models.Stations.objects.get(api_id=station_api_id)
        except models.Stations.DoesNotExist:
            raise Http404
        else:
            return station.network_code.network_code, station.station_code

    def list(self, request, *args, **kwargs):
        network_code, station_code = self._get_station(
            kwargs.get("station_api_id"))

        params = self._check_params(request)

        cnn = dbConnection.Cnn(settings.CONFIG_FILE_ABSOLUTE_PATH)
        try:
            if params["solution"] == "GAMIT":
                polyhedrons = cnn.query_float('SELECT "X", "Y", "Z", "Year", "DOY" FROM stacks '
                                              'WHERE "name" = \'%s\' AND "NetworkCode" = \'%s\' AND '
                                              '"StationCode" = \'%s\' '
                                              'ORDER BY "Year", "DOY", "NetworkCode", "StationCode"'
                                              % (params["stack"], network_code, station_code))

                soln = pyETM.GamitSoln(
                    cnn, polyhedrons, network_code, station_code, params["stack"])

                etm = pyETM.GamitETM(cnn, network_code, station_code, False,
                                     params["no_model"], gamit_soln=soln, plot_remove_jumps=params["remove_jumps"],
                                     plot_polynomial_removed=params["remove_polynomial"])
            else:
                etm = pyETM.PPPETM(cnn, network_code, station_code, False, params["no_model"],
                                   plot_remove_jumps=params["remove_jumps"],
                                   plot_polynomial_removed=params["remove_polynomial"])
            fileio = BytesIO()
            image = etm.plot(pngfile=None, t_win=params["dates"], residuals=params["residuals"],
                             plot_missing=params["missing_data"], plot_outliers=params["plot_outliers"], fileio=fileio)
        except Exception as e:
            raise exceptions.CustomValidationErrorExceptionHandler(
                e.detail if hasattr(e, 'detail') else str(e))

        return Response(data={"time_series": image}, status=status.HTTP_200_OK)


class StationMetaList(CustomListCreateAPIView):
    queryset = models.StationMeta.objects.all()
    serializer_class = serializers.StationMetaSerializer


class StationMetaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.StationMeta.objects.all()
    serializer_class = serializers.StationMetaSerializer
    lookup_field = 'station_id'

    @extend_schema(description="In order to delete navigation_file, send 'navigation_file_delete' as true.")
    def put(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(description="In order to delete navigation_file, send 'navigation_file_delete' as true.")
    def patch(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)


class StationStatusList(CustomListCreateAPIView):
    queryset = models.StationStatus.objects.all()
    serializer_class = serializers.StationStatusSerializer


class StationStatusDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.StationStatus.objects.all()
    serializer_class = serializers.StationStatusSerializer


class StationTypeList(CustomListCreateAPIView):
    queryset = models.StationType.objects.all()
    serializer_class = serializers.StationTypeSerializer


class StationTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.StationType.objects.all()
    serializer_class = serializers.StationTypeSerializer


class StationAttachedFilesList(CustomListCreateAPIView):
    queryset = models.StationAttachedFiles.objects.all()
    serializer_class = serializers.StationAttachedFilesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StationAttachedFilesFilter
    parser_classes = [MultiPartParser]

    @extend_schema(description="""The endpoint expects each one of the following parameters per file: 'station' for station api_id, 'file', 'description'.""")
    def post(self, request, *args, **kwargs):
        return utils.UploadMultipleFilesUtils.upload_multiple_files(self, request, 'station')

    def list(self, request, *args, **kwargs):
        only_metadata = request.query_params.get(
            'only_metadata', 'false').lower() == 'true'
        if only_metadata:
            self.serializer_class = serializers.StationAttachedFilesOnlyMetadataSerializer
        return super().list(request, *args, **kwargs)


class StationAttachedFilesDetail(generics.RetrieveDestroyAPIView):
    queryset = models.StationAttachedFiles.objects.all()
    serializer_class = serializers.StationAttachedFilesSerializer


class StationImagesList(CustomListCreateAPIView):
    queryset = models.StationImages.objects.all()
    serializer_class = serializers.StationImagesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StationImagesFilter
    parser_classes = [MultiPartParser]

    @extend_schema(description="""In the filesystem, image name will be the same as uploaded image unless 'name' parameter is specified (also specify image extension in 'name'). If 'name' is an empty string, it will be treated as no name either.
                   \nThe endpoint expects each one of the following parameters per image: 'station' for station api_id, 'image', 'name', 'description'.""")
    def post(self, request, *args, **kwargs):
        return utils.UploadMultipleFilesUtils.upload_multiple_images(self, request, 'station')

    def list(self, request, *args, **kwargs):
        only_metadata = request.query_params.get(
            'only_metadata', 'false').lower() == 'true'
        if only_metadata:
            self.serializer_class = serializers.StationImagesOnlyMetadataSerializer
        return super().list(request, *args, **kwargs)


class StationImagesDetail(generics.RetrieveDestroyAPIView):
    queryset = models.StationImages.objects.all()
    serializer_class = serializers.StationImagesSerializer


class CampaignList(CustomListCreateAPIView):
    queryset = models.Campaigns.objects.all()
    serializer_class = serializers.CampaignSerializer


class CampaignDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Campaigns.objects.all()
    serializer_class = serializers.CampaignSerializer


class VisitList(CustomListCreateAPIView):
    queryset = models.Visits.objects.all()
    serializer_class = serializers.VisitSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VisitFilter

    def list(request, *args, **kwargs):
        """If the response status is 200, add some fields of the related station object"""

        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # Add people name to people array

            people_list = models.Person.objects.values_list(
                'id', 'first_name', 'last_name')

            people_dict = {
                person[0]: person[1] + ' ' + person[2]
                for person in people_list
            }

            for visit in response.data["data"]:

                if 'people' in visit:
                    people_ids = visit["people"].copy()

                    visit["people"].clear()

                    for people_id in people_ids:
                        if people_id in people_dict:
                            visit["people"].append(
                                {'id': people_id, 'name': people_dict[people_id]})

        return response


class VisitDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Visits.objects.all()
    serializer_class = serializers.VisitSerializer

    def retrieve(self, request, *args, **kwargs):
        """If response is 200, add some related station fields"""

        response = super().retrieve(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # Add people name to people array

            people_list = models.Person.objects.values_list(
                'id', 'first_name', 'last_name')

            people_dict = {
                person[0]: person[1] + ' ' + person[2]
                for person in people_list
            }

            if 'people' in response.data:
                people_ids = response.data["people"].copy()

                response.data["people"].clear()

                for people_id in people_ids:
                    if people_id in people_dict:
                        response.data["people"].append(
                            {'id': people_id, 'name': people_dict[people_id]})

        return response

    @extend_schema(description="In order to delete log_sheet_file, send 'log_sheet_file_delete' as true. The same applies with 'navigation_file_delete' for the navigation_file.")
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @extend_schema(description="In order to delete log_sheet_file, send 'log_sheet_file_delete' as true. The same applies with 'navigation_file_delete' for the navigation_file.")
    def patch(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class VisitAttachedFilesList(CustomListCreateAPIView):
    queryset = models.VisitAttachedFiles.objects.all()
    serializer_class = serializers.VisitAttachedFilesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VisitAttachedFilesFilter
    parser_classes = [MultiPartParser]

    @extend_schema(description="""The endpoint expects each one of the following parameters per file: 'visit' for visit api_id, 'file', 'description'.""")
    def post(self, request, *args, **kwargs):
        return utils.UploadMultipleFilesUtils.upload_multiple_files(self, request, 'visit')

    def list(self, request, *args, **kwargs):
        only_metadata = request.query_params.get(
            'only_metadata', 'false').lower() == 'true'
        if only_metadata:
            self.serializer_class = serializers.VisitAttachedFilesOnlyMetadataSerializer
        return super().list(request, *args, **kwargs)


class VisitAttachedFilesDetail(generics.RetrieveDestroyAPIView):
    queryset = models.VisitAttachedFiles.objects.all()
    serializer_class = serializers.VisitAttachedFilesSerializer


class VisitImagesList(CustomListCreateAPIView):
    queryset = models.VisitImages.objects.all()
    serializer_class = serializers.VisitImagesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VisitImagesFilter
    parser_classes = [MultiPartParser]

    @extend_schema(description="""In the filesystem, image name will be the same as uploaded image unless 'name' parameter is specified (also specify image extension in 'name'). If 'name' is an empty string, it will be treated as no name either.
                   \nThe endpoint expects each one of the following parameters per image: 'visit' for station api_id, 'image', 'name', 'description'.""")
    def post(self, request, *args, **kwargs):

        return utils.UploadMultipleFilesUtils.upload_multiple_images(self, request, 'visit')

    def list(self, request, *args, **kwargs):
        only_metadata = request.query_params.get(
            'only_metadata', 'false').lower() == 'true'
        if only_metadata:
            self.serializer_class = serializers.VisitImagesOnlyMetadataSerializer
        return super().list(request, *args, **kwargs)


class VisitImagesDetail(generics.RetrieveDestroyAPIView):
    queryset = models.VisitImages.objects.all()
    serializer_class = serializers.VisitImagesSerializer


class VisitGNSSDataFilesList(CustomListCreateAPIView):
    queryset = models.VisitGNSSDataFiles.objects.all()
    serializer_class = serializers.VisitGNSSDataFilesSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.VisitGNSSDataFilesFilter
    parser_classes = [MultiPartParser]

    @extend_schema(description="""The endpoint expects each one of the following parameters per file: 'visit' for visit id, 'file', 'description'.""")
    def post(self, request, *args, **kwargs):
        return utils.UploadMultipleFilesUtils.upload_multiple_files(self, request, 'visit')

    def list(self, request, *args, **kwargs):
        only_metadata = request.query_params.get(
            'only_metadata', 'false').lower() == 'true'
        if only_metadata:
            self.serializer_class = serializers.VisitGNSSDataFilesOnlyMetadataSerializer
        return super().list(request, *args, **kwargs)


class VisitGNSSDataFilesDetail(generics.RetrieveDestroyAPIView):
    queryset = models.VisitGNSSDataFiles.objects.all()
    serializer_class = serializers.VisitGNSSDataFilesSerializer


class RolePersonStationList(CustomListCreateAPIView):
    queryset = models.RolePersonStation.objects.all()
    serializer_class = serializers.RolePersonStationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.RolePersonStationFilter


class RolePersonStationDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.RolePersonStation.objects.all()
    serializer_class = serializers.RolePersonStationSerializer


class StationRolesList(CustomListCreateAPIView):
    queryset = models.StationRole.objects.all()
    serializer_class = serializers.StationRoleSerializer


class StationRolesDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.StationRole.objects.all()
    serializer_class = serializers.StationRoleSerializer


class RolePersonStationDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.RolePersonStation.objects.all()
    serializer_class = serializers.RolePersonStationSerializer


class AprCoordsList(CustomListCreateAPIView):
    queryset = models.AprCoords.objects.all()
    serializer_class = serializers.AprCoordsSerializer


class AprCoordsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.AprCoords.objects.all()
    serializer_class = serializers.AprCoordsSerializer


class AwsSyncList(CustomListCreateAPIView):
    queryset = models.AwsSync.objects.all()
    serializer_class = serializers.AprCoordsSerializer


class AwsSyncDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.AwsSync.objects.all()
    serializer_class = serializers.AprCoordsSerializer


class CountryList(AddCountMixin, generics.ListCreateAPIView):
    queryset = models.Country.objects.all()
    serializer_class = serializers.CountrySerializer


class CountryDetail(generics.RetrieveAPIView):
    queryset = models.Country.objects.all()
    serializer_class = serializers.CountrySerializer


class DataSourceList(CustomListCreateAPIView):
    queryset = models.DataSource.objects.all()
    serializer_class = serializers.DataSourceSerializer


class DataSourceDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.DataSource.objects.all()
    serializer_class = serializers.DataSourceSerializer


class EarthquakesList(CustomListCreateAPIView):
    queryset = models.Earthquakes.objects.all()
    serializer_class = serializers.EarthquakesSerializer


class EarthquakesDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Earthquakes.objects.all()
    serializer_class = serializers.EarthquakesSerializer


class EtmParamsList(CustomListCreateAPIView):
    queryset = models.EtmParams.objects.all()
    serializer_class = serializers.EtmParamsSerializer


class EtmParamsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.EtmParams.objects.all()
    serializer_class = serializers.EtmParamsSerializer


class EtmsList(CustomListCreateAPIView):
    queryset = models.Etms.objects.all()
    serializer_class = serializers.EtmsSerializer


class EtmsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Etms.objects.all()
    serializer_class = serializers.EtmsSerializer


class EventsList(CustomListCreateAPIView):
    queryset = models.Events.objects.all()
    serializer_class = serializers.EventsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.EventsFilter


class EventsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Events.objects.all()
    serializer_class = serializers.EventsSerializer


class ExecutionsList(CustomListCreateAPIView):
    queryset = models.Executions.objects.all()
    serializer_class = serializers.ExecutionsSerializer


class ExecutionsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Executions.objects.all()
    serializer_class = serializers.ExecutionsSerializer


class HealthCheck(APIView):
    @extend_schema(
        description="Returns a success message if the API is up and connected to the database.",
        responses={
            200: OpenApiResponse(
                description="API is up and connected to the database",
                examples={
                    "application/json": {
                        "result": "API is up and connected to database"
                    }
                }
            ),
        },
        tags=["health-check"]
    )
    def get(self, request, format=None):
        return Response({'result': "API is up and connected to database"}, status=200)


class GamitHtcList(CustomListCreateAPIView):
    queryset = models.GamitHtc.objects.all()
    serializer_class = serializers.GamitHtcSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.GamitHtcFilter


class GamitHtcDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitHtc.objects.all()
    serializer_class = serializers.GamitHtcSerializer


class GamitSolnList(CustomListCreateAPIView):
    queryset = models.GamitSoln.objects.all()
    serializer_class = serializers.GamitSolnSerializer


class GamitSolnDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitSoln.objects.all()
    serializer_class = serializers.GamitSolnSerializer


class GamitSolnExcl(generics.ListCreateAPIView):
    queryset = models.GamitSolnExcl.objects.all()
    serializer_class = serializers.GamitSolnExclSerializer


class GamitSolnExclList(CustomListCreateAPIView):
    queryset = models.GamitSolnExcl.objects.all()
    serializer_class = serializers.GamitSolnExclSerializer


class GamitSolnExclDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitSolnExcl.objects.all()
    serializer_class = serializers.GamitSolnExclSerializer


class GamitStatsList(CustomListCreateAPIView):
    queryset = models.GamitStats.objects.all()
    serializer_class = serializers.GamitStatsSerializer


class GamitStatsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitStats.objects.all()
    serializer_class = serializers.GamitStatsSerializer


class GamitSubnetsList(CustomListCreateAPIView):
    queryset = models.GamitSubnets.objects.all()
    serializer_class = serializers.GamitSubnetsSerializer


class GamitSubnetsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitSubnets.objects.all()
    serializer_class = serializers.GamitSubnetsSerializer


class GamitZtdList(CustomListCreateAPIView):
    queryset = models.GamitZtd.objects.all()
    serializer_class = serializers.GamitZtdSerializer


class GamitZtdDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.GamitZtd.objects.all()
    serializer_class = serializers.GamitZtdSerializer


class KeysList(CustomListCreateAPIView):
    queryset = models.Keys.objects.all()
    serializer_class = serializers.KeysSerializer


class KeysDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Keys.objects.all()
    serializer_class = serializers.KeysSerializer


class LocksList(CustomListCreateAPIView):
    queryset = models.Locks.objects.all()
    serializer_class = serializers.LocksSerializer


class LocksDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Locks.objects.all()
    serializer_class = serializers.LocksSerializer


class PersonList(CustomListCreateAPIView):
    queryset = models.Person.objects.all()
    serializer_class = serializers.PersonSerializer


class PersonDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Person.objects.all()
    serializer_class = serializers.PersonSerializer


class PppSolnList(CustomListCreateAPIView):
    queryset = models.PppSoln.objects.all()
    serializer_class = serializers.PppSolnSerializer


class PppSolnDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.PppSoln.objects.all()
    serializer_class = serializers.PppSolnSerializer


class PppSolnExclList(CustomListCreateAPIView):
    queryset = models.PppSolnExcl.objects.all()
    serializer_class = serializers.PppSolnExclSerializer


class PppSolnExclDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.PppSolnExcl.objects.all()
    serializer_class = serializers.PppSolnExclSerializer


class ReceiversList(CustomListCreateAPIView):
    queryset = models.Receivers.objects.all()
    serializer_class = serializers.ReceiversSerializer


class ReceiversDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Receivers.objects.all()
    serializer_class = serializers.ReceiversSerializer


class RinexList(CustomListCreateAPIView):
    queryset = models.Rinex.objects.all()
    serializer_class = serializers.RinexSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.RinexFilter


class GetRinexWithStatus(CustomListCreateAPIView):
    serializer_class = serializers.RinexSerializer

    def get_queryset(self):
        # get all rinex from given station

        station_api_id = self.kwargs.get('station_api_id')
        try:
            station = models.Stations.objects.get(api_id=station_api_id)
        except models.Stations.DoesNotExist:
            raise Http404
        else:
            return models.Rinex.objects.filter(
                network_code=station.network_code_id,
                station_code=station.station_code
            ).exclude(observation_s_time__isnull=True).exclude(observation_e_time__isnull=True)

    def _get_filters_from_request(self, request):
        filters = {}

        filters["observation_doy"] = request.query_params.get(
            "observation_doy", None)
        filters["observation_s_time_since"] = request.query_params.get(
            "observation_s_time_since", None)
        filters["observation_s_time_until"] = request.query_params.get(
            "observation_s_time_until", None)
        filters["observation_e_time_since"] = request.query_params.get(
            "observation_e_time_since", None)
        filters["observation_e_time_until"] = request.query_params.get(
            "observation_e_time_until", None)
        filters["observation_f_year"] = request.query_params.get(
            "observation_f_year", None)
        filters["observation_year"] = request.query_params.get(
            "observation_year", None)
        filters["antenna_dome"] = request.query_params.get(
            "antenna_dome", None)
        filters["antenna_offset"] = request.query_params.get(
            "antenna_offset", None)
        filters["antenna_serial"] = request.query_params.get(
            "antenna_serial", None)
        filters["antenna_type"] = request.query_params.get(
            "antenna_type", None)
        filters["receiver_fw"] = request.query_params.get("receiver_fw", None)
        filters["receiver_serial"] = request.query_params.get(
            "receiver_serial", None)
        filters["receiver_type"] = request.query_params.get(
            "receiver_type", None)
        filters["completion_operator"] = request.query_params.get(
            "completion_operator", None)
        filters["completion"] = request.query_params.get("completion", None)
        filters["interval"] = request.query_params.get("interval", None)

        return filters

    def list(self, request, *args, **kwargs):

        rinex_list = self.get_queryset()

        filters = self._get_filters_from_request(request)

        rinex_with_status = utils.RinexUtils.get_rinex_with_status(
            rinex_list, filters)

        return Response(rinex_with_status)


class RinexDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Rinex.objects.all()
    serializer_class = serializers.RinexSerializer


class GetNextStationInfoFromRinex(APIView):
    serializer_class = serializers.RinexSerializer

    def get_queryset(self, pk):
        try:
            return models.Rinex.objects.get(api_id=pk)
        except models.Rinex.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        rinex = self.get_queryset(pk)
        try:
            next_station_info = utils.RinexUtils.get_next_station_info(rinex)

            if next_station_info == None:
                raise exceptions.CustomValidationErrorExceptionHandler(
                    'No station info to extend for %s.%s' % (rinex.network_code.network_code, rinex.station_code))

        except Exception as e:
            raise exceptions.CustomValidationErrorExceptionHandler(e)

        return Response(data={"next_station_info_api_id": next_station_info.api_id}, status=status.HTTP_200_OK)


class GetPreviousStationInfoFromRinex(APIView):
    serializer_class = serializers.RinexSerializer

    def get_queryset(self, pk):
        try:
            return models.Rinex.objects.get(api_id=pk)
        except models.Rinex.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):

        rinex = self.get_queryset(pk)
        try:
            previous_station_info = utils.RinexUtils.get_previous_station_info(
                rinex)

            if previous_station_info == None:
                raise exceptions.CustomValidationErrorExceptionHandler(
                    'No station info to extend for %s.%s' % (rinex.network_code.network_code, rinex.station_code))

        except Exception as e:
            raise exceptions.CustomValidationErrorExceptionHandler(e)

        return Response(data={"previous_station_info_api_id": previous_station_info.api_id}, status=status.HTTP_200_OK)


class RinexSourcesInfoList(CustomListCreateAPIView):
    queryset = models.RinexSourcesInfo.objects.all()
    serializer_class = serializers.RinexSourcesInfoSerializer


class RinexSourcesInfoDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.RinexSourcesInfo.objects.all()
    serializer_class = serializers.RinexSourcesInfoSerializer


class RinexTankStructList(CustomListCreateAPIView):
    queryset = models.RinexTankStruct.objects.all()
    serializer_class = serializers.RinexTankStructSerializer


class RinexTankStructDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.RinexTankStruct.objects.all()
    serializer_class = serializers.RinexTankStructSerializer


class SourcesFormatsList(CustomListCreateAPIView):
    queryset = models.SourcesFormats.objects.all()
    serializer_class = serializers.SourcesFormatsSerializer


class SourcesFormatsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.SourcesFormats.objects.all()
    serializer_class = serializers.SourcesFormatsSerializer


class SourcesServersList(CustomListCreateAPIView):
    queryset = models.SourcesServers.objects.all()
    serializer_class = serializers.SourcesServersSerializer


class SourcesServersDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.SourcesServers.objects.all()
    serializer_class = serializers.SourcesServersSerializer


class SourcesStationsList(CustomListCreateAPIView):
    queryset = models.SourcesStations.objects.all()
    serializer_class = serializers.SourcesStationsSerializer


class SourcesStationsDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.SourcesStations.objects.all()
    serializer_class = serializers.SourcesStationsSerializer


class StacksList(CustomListCreateAPIView):
    queryset = models.Stacks.objects.all()
    serializer_class = serializers.StacksSerializer


class StacksDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Stacks.objects.all()
    serializer_class = serializers.StacksSerializer


class StationaliasList(CustomListCreateAPIView):
    queryset = models.Stationalias.objects.all()
    serializer_class = serializers.StationaliasSerializer


class StationaliasDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Stationalias.objects.all()
    serializer_class = serializers.StationaliasSerializer


class EventManager():

    @staticmethod
    def create_event(**kwargs):
        values = dict()

        values['event_type'] = 'info'
        values['network_code'] = None
        values['station_code'] = None
        values['year'] = None
        values['doy'] = None
        values['description'] = ''
        values['node'] = platform.node()
        values['stack'] = None

        module = inspect.getmodule(inspect.stack()[1][0])
        stack = traceback.extract_stack()[0:-2]

        if module is None:
            # just get the calling module
            values['module'] = inspect.stack()[1][3]
        else:
            # values['module'] = module.__name__ + '.' + inspect.stack()[1][3]  # just get the calling module
            values['module'] = module.__name__ + '.' + \
                stack[-1][2]  # just get the calling module

        # initialize the dictionary based on the input
        for key in kwargs:
            if key not in values.keys():
                raise exceptions.CustomValidationErrorExceptionHandler(
                    'Provided key not in list of valid fields.')

            arg = kwargs[key]
            values[key] = arg

        if values['event_type'] == 'error':
            # print the traceback until just before this call
            values['stack'] = ''.join(traceback.format_stack()[0:-2])
        else:
            values['stack'] = None

        EventManager.clean_str(values)

        models.Events.objects.create(**values)

    def clean_str(values):
        # remove any invalid chars that can cause problems in the database

        for key in values:
            s = values[key]
            if type(s) is str:
                s = re.sub(r'[^\x00-\x7f]+', '', s)
                s = s.replace('\'', '"')
                s = re.sub(r'BASH.*', '', s)
                s = re.sub(r'PSQL.*', '', s)
                values[key] = s

        return values


class StationinfoList(CustomListCreateAPIView):
    queryset = models.Stationinfo.objects.all()
    serializer_class = serializers.StationinfoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.StationinfoFilter

    def post(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = self._custom_post(serializer)

        if result == None:

            headers = self.get_success_headers(serializer.data)

            created_record_serializer = serializers.StationinfoSerializer(self.get_queryset().get(
                network_code=serializer.validated_data['network_code'], station_code=serializer.validated_data['station_code'], date_start=serializer.validated_data['date_start']))

            return Response(created_record_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            # no new record was created, only the start date of the first record was modified
            previous_date = result

            headers = self.get_success_headers(serializer.data)

            return Response('The start date of the station information record ' +
                            previous_date.strftime("%Y-%m-%d %H:%M:%S") +
                            ' has been been modified to ' +
                            serializer.validated_data['date_start'].strftime("%Y-%m-%d %H:%M:%S"), status=status.HTTP_201_CREATED, headers=headers)

    def _custom_post(self, serializer):
        def pk_already_exists(serializer):
            return self.queryset.filter(network_code=serializer.validated_data['network_code'], station_code=serializer.validated_data['station_code'], date_start=serializer.validated_data['date_start']).exists()

        def records_are_equal(serializer, record):

            return (serializer.validated_data.get('receiver_code') == record.receiver_code and
                    serializer.validated_data.get('receiver_serial') == record.receiver_serial and
                    serializer.validated_data.get('antenna_code') == record.antenna_code and
                    serializer.validated_data.get('antenna_serial') == record.antenna_serial and
                    serializer.validated_data.get('antenna_height') == record.antenna_height and
                    serializer.validated_data.get('antenna_north') == record.antenna_north and
                    serializer.validated_data.get('antenna_east') == record.antenna_east and
                    serializer.validated_data.get('height_code') == record.height_code and
                    serializer.validated_data.get('radome_code') == record.radome_code)

        def modify_record_start_date(serializer, record):
            record.date_start = serializer.validated_data['date_start']
            record.save()

        def insert_update_event(serializer, previous_date):
            EventManager.create_event(description='The start date of the station information record ' +
                                      previous_date.strftime("%Y-%m-%d %H:%M:%S") +
                                      ' has been been modified to ' +
                                      serializer.validated_data['date_start'].strftime(
                                          "%Y-%m-%d %H:%M:%S"),
                                      station_code=serializer.validated_data['station_code'],
                                      network_code=serializer.validated_data['network_code'])

        def insert_create_event(serializer, created_object):
            EventManager.create_event(description='A new station information record was added:\n'
                                      + utils.StationInfoUtils.record_to_str(created_object),
                                      station_code=serializer.validated_data['station_code'],
                                      network_code=serializer.validated_data['network_code'])

        def insert_create_event_with_extra_description(serializer, record):
            EventManager.create_event(description='A new station information record was added:\n' +
                                      utils.StationInfoUtils.return_stninfo(serializer=serializer) +
                                      '\nThe previous DateEnd value was updated to ' +
                                      record.date_end.strftime(
                                          "%Y-%m-%d %H:%M:%S"),
                                      station_code=serializer.validated_data['station_code'],
                                      network_code=serializer.validated_data['network_code'])

        def modify_date_end(serializer, first_record):

            serializer.validated_data['date_end'] = first_record.date_start - \
                datetime.timedelta(seconds=1)

        def modify_last_record_end_date(serializer, last_record):
            last_record.date_end = serializer.validated_data['date_start'] - datetime.timedelta(
                seconds=1)
            last_record.save()

        def get_overlap_exception_detail(records_that_overlap):

            stroverlap = []

            for overlap_record in records_that_overlap:
                stroverlap.append(
                    ' -> '.join([str(overlap_record.date_start), str(overlap_record.date_end)]))

            return ' '.join(stroverlap)

        if not pk_already_exists(serializer):
            # can insert because it's not the same record
            # 1) verify the record is not between any two existing records
            records_that_overlap = utils.StationInfoUtils.get_records_that_overlap(
                serializer, self.get_queryset)

            if len(records_that_overlap) > 0:
                # if it overlaps all records and the date_start < first_record.date_start
                # see if we have to extend the initial date

                if len(records_that_overlap) == utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).count() and \
                        serializer.validated_data['date_start'] < utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).first().date_start:
                    if records_are_equal(serializer, utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).first()):

                        previous_date = utils.StationInfoUtils.get_same_station_records(
                            serializer, self.get_queryset).first().date_start

                        modify_record_start_date(
                            serializer, utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).first())

                        insert_update_event(serializer, previous_date)

                        return previous_date  # in order to change the response message
                    else:

                        modify_date_end(
                            serializer, utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).first())

                        created_object = serializer.save()

                        insert_create_event(serializer,
                                            created_object)

                elif len(records_that_overlap) == 1 and records_that_overlap[0] == utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).last() and \
                        utils.StationInfoUtils.get_same_station_records(serializer, self.get_queryset).last().date_end == None:
                    # overlap with the last session
                    # stop the current valid session
                    last_record = utils.StationInfoUtils.get_same_station_records(
                        serializer, self.get_queryset).last()

                    modify_last_record_end_date(serializer, last_record)

                    # create the incoming session
                    serializer.save()

                    insert_create_event_with_extra_description(
                        serializer, last_record)

                else:
                    raise exceptions.CustomValidationErrorExceptionHandler(
                        f"Record ${serializer.validated_data['date_start']} -> ${serializer.validated_data['date_end'] if 'date_end' in serializer.validated_data else None} overlaps with existing station.info records: ${get_overlap_exception_detail(records_that_overlap)}")
            else:
                # no overlaps, insert the record
                created_object = serializer.save()

                insert_create_event(serializer, created_object)
        else:
            raise exceptions.CustomValidationErrorExceptionHandler(
                'The record already exists in the database.')


class InsertStationInfoByFile(APIView):
    parser_classes = [MultiPartParser]

    def _station_info_pgamit_to_serializer(self, station_info_record_from_pgamit):
        station_info_instance = {
            "network_code": station_info_record_from_pgamit.NetworkCode,
            "station_code": station_info_record_from_pgamit.StationCode,
            "receiver_code": station_info_record_from_pgamit.ReceiverCode,
            "receiver_serial": station_info_record_from_pgamit.ReceiverSerial,
            "receiver_firmware": station_info_record_from_pgamit.ReceiverFirmware,
            "antenna_code": station_info_record_from_pgamit.AntennaCode,
            "antenna_serial": station_info_record_from_pgamit.AntennaSerial,
            "antenna_height": station_info_record_from_pgamit.AntennaHeight,
            "antenna_north": station_info_record_from_pgamit.AntennaNorth,
            "antenna_east": station_info_record_from_pgamit.AntennaEast,
            "height_code": station_info_record_from_pgamit.HeightCode,
            "radome_code": station_info_record_from_pgamit.RadomeCode,
            "date_start": pyDate.Date(stninfo=station_info_record_from_pgamit.DateStart).datetime(),
            "date_end": pyDate.Date(stninfo=station_info_record_from_pgamit.DateEnd).datetime(),
            "receiver_vers": station_info_record_from_pgamit.ReceiverVers,
            "comments": station_info_record_from_pgamit.Comments
        }
        station_info_serializer = serializers.StationinfoSerializer(
            data=station_info_instance)

        station_info_serializer.is_valid(raise_exception=True)

        return station_info_serializer

    @extend_schema(
        request=OpenApiTypes.OBJECT,
        parameters=[
            OpenApiParameter(name='file', type=OpenApiTypes.BINARY,
                             required=True, description='The file to upload.')
        ],
        description="This endpoint uses PGAMIT module to parse the file. \nIt returns a value with key 'inserted_station_info' containing a list of station info successfully inserted. \nIf at least one station info insert failed, another value with key 'error_message' detailing the error is returned."
    )
    def post(self, request, *args, **kwargs):
        if 'file' not in request.FILES:
            raise exceptions.CustomValidationErrorExceptionHandler(
                "No file was uploaded.")

        uploaded_file = request.FILES['file']

        # Save the file temporarily to pass file path to parser
        file_path = default_storage.save(uploaded_file.name, uploaded_file)
        full_file_path = os.path.join(default_storage.location, file_path)

        try:
            station = models.Stations.objects.get(
                api_id=kwargs['station_api_id'])
        except models.Stations.DoesNotExist:
            if os.path.exists(full_file_path):
                os.remove(full_file_path)
            raise exceptions.CustomValidationErrorExceptionHandler(
                "Station does not exist.")
        except models.Stations.MultipleObjectsReturned:
            if os.path.exists(full_file_path):
                os.remove(full_file_path)
            raise exceptions.CustomServerErrorExceptionHandler(
                "Multiple stations with the same API ID exist.")

        succesfully_inserted = []

        try:
            cnn = dbConnection.Cnn(settings.CONFIG_FILE_ABSOLUTE_PATH)

            pgamit_stationinfo = pyStationInfo.StationInfo(
                cnn=cnn, NetworkCode=station.network_code.network_code, StationCode=station.station_code, allow_empty=True)
            station_info_records = pgamit_stationinfo.parse_station_info(
                full_file_path)

            for station_info_record in station_info_records:
                station_info_serializer = self._station_info_pgamit_to_serializer(
                    station_info_record)

                if station_info_serializer.validated_data['station_code'] == station.station_code and station_info_serializer.validated_data['network_code'] == station.network_code.network_code:
                    station_info_list = StationinfoList()
                    station_info_list._custom_post(station_info_serializer)

                    succesfully_inserted.append({"station_code": station_info_serializer.validated_data['station_code'], "network_code": station_info_serializer.validated_data[
                                                'network_code'], "date_start": station_info_serializer.validated_data['date_start']})

            if os.path.exists(full_file_path):
                os.remove(full_file_path)

            return Response({"inserted_station_info": succesfully_inserted}, status=status.HTTP_201_CREATED)
        except Exception as e:

            if os.path.exists(full_file_path):
                os.remove(full_file_path)

            if len(succesfully_inserted) == 0:
                return Response({"inserted_station_info": [], "error_message": e.detail if hasattr(e, 'detail') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"inserted_station_info": succesfully_inserted, "error_message": e.detail if hasattr(e, 'detail') else str(e)}, status=status.HTTP_201_CREATED)


class StationinfoDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = models.Stationinfo.objects.all()
    serializer_class = serializers.StationinfoSerializer
    http_method_names = ["get", "put", "delete"]

    def put(self, request, *args, **kwargs):

        def overlaps_at_least_one_record(serializer):

            records_that_overlap = utils.StationInfoUtils.get_records_that_overlap(
                serializer, self.get_queryset, self.get_object)

            # it can overlap itself, so we need to check if it overlaps at least one other record
            for record in records_that_overlap:
                if record.api_id != self.get_object().api_id:
                    return True

            return False

        def insert_event(serializer, record_before_update: dict):

            EventManager.create_event(description=serializer.validated_data["date_start"].strftime("%Y-%m-%d %H:%M:%S") +
                                      ' has been updated:\n' + utils.StationInfoUtils.record_to_str(self.get_object()) +
                                      '\n+++++++++++++++++++++++++++++++++++++\n' +
                                      'Previous record:\n' +
                                      str(record_before_update) + '\n',
                                      station_code=record_before_update["station_code"],
                                      network_code=record_before_update["network_code"])

        def custom_update(serializer):
            if overlaps_at_least_one_record(serializer):
                raise exceptions.CustomValidationErrorExceptionHandler(
                    'The record overlaps with at least one existing record.')
            else:
                record_before_update = utils.StationInfoUtils.get_record_values(
                    self.get_object)

                self.perform_update(serializer)

                insert_event(serializer, record_before_update)

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # they should not be updated
        del serializer.validated_data['network_code']
        del serializer.validated_data['station_code']

        custom_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
            Adds an event when the object is succesfully deleted
        """
        record_before_delete = utils.StationInfoUtils.get_record_values(
            self.get_object)

        self.perform_destroy(self.get_object())

        EventManager.create_event(description='The station information record ' +
                                  record_before_delete["date_start"].strftime("%Y-%m-%d %H:%M:%S") +
                                  ' has been deleted.',
                                  station_code=record_before_delete["station_code"],
                                  network_code=record_before_delete["network_code"])

        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateGapsStatus(APIView):
    serializer_class = serializers.DummySerializer

    @extend_schema(description="Computes gaps status for all station_meta objects with 'has_gaps_update_needed' = true")
    def post(self, request, format=None):

        if cache.add('update_gaps_status_lock', 'locked', timeout=60*60):
            update_gaps_status.delay()
            return Response(status=status.HTTP_201_CREATED)
        else:
            return Response(status=status.HTTP_429_TOO_MANY_REQUESTS)


class DeleteUpdateGapsStatusBlock(APIView):
    serializer_class = serializers.DummySerializer

    def post(self, request, format=None):
        cache.delete('update_gaps_status_lock')
        return Response(status=status.HTTP_201_CREATED)


class DistinctStackNames(APIView):
    serializer_class = serializers.DummySerializer

    def get(self, *args, **kwargs):
        station_api_id = kwargs.get('station_api_id')
        try:
            station = models.Stations.objects.get(api_id=station_api_id)
        except models.Stations.DoesNotExist:
            raise Http404
        else:
            stack_names = models.Stacks.objects.filter(
                station_code=station.station_code, network_code=station.network_code.network_code).values_list('name', flat=True).distinct()
            return Response({"stack_names": stack_names})
