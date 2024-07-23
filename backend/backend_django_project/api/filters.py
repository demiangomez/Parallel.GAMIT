from rest_framework import generics
from django_filters import rest_framework as filters
from . import models


class StationFilter(filters.FilterSet):
    network_code = filters.CharFilter(
        field_name='network_code__network_code', lookup_expr='exact')

    station_name = filters.CharFilter(
        field_name='station_name', lookup_expr='istartswith')

    station_code = filters.CharFilter(
        field_name='station_code', lookup_expr='istartswith')

    class Meta:
        model = models.Stations
        fields = ['network_code', 'station_name',
                  'station_code', 'country_code']


class StationinfoFilter(filters.FilterSet):

    class Meta:
        model = models.Stationinfo
        fields = ['network_code', 'station_code']


class GamitHtcFilter(filters.FilterSet):

    class Meta:
        model = models.GamitHtc
        fields = ['antenna_code']


class RinexFilter(filters.FilterSet):

    class Meta:
        model = models.Rinex
        fields = ['network_code', 'station_code']


class RolePersonStationFilter(filters.FilterSet):
    station_api_id = filters.CharFilter(
        field_name='station')

    class Meta:
        model = models.RolePersonStation
        fields = ['station_api_id']


class StationImagesFilter(filters.FilterSet):
    station_api_id = filters.CharFilter(
        field_name='station')

    class Meta:
        model = models.StationImages
        fields = ['station_api_id']


class StationAttachedFilesFilter(filters.FilterSet):
    station_api_id = filters.CharFilter(
        field_name='station')

    class Meta:
        model = models.StationAttachedFiles
        fields = ['station_api_id']


class VisitAttachedFilesFilter(filters.FilterSet):
    visit_api_id = filters.CharFilter(
        field_name='visit')

    class Meta:
        model = models.VisitAttachedFiles
        fields = ['visit_api_id']


class VisitImagesFilter(filters.FilterSet):
    visit_api_id = filters.CharFilter(
        field_name='visit')

    class Meta:
        model = models.VisitImages
        fields = ['visit_api_id']


class VisitGNSSDataFilesFilter(filters.FilterSet):
    visit_api_id = filters.CharFilter(
        field_name='visit')

    class Meta:
        model = models.VisitGNSSDataFiles
        fields = ['visit_api_id']
