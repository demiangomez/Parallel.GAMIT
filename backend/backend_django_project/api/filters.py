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
