from rest_framework import serializers
from . import models
import django.contrib.auth.hashers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import datetime
from . import utils


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Role
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'password', 'role', 'is_active',
                  'first_name', 'last_name', 'email', 'phone', 'address', 'photo']
        extra_kwargs = {'password': {'write_only': True}}

    def save(self):
        # hash password (it didn't work with to_internal_value(self, data))
        if 'password' in self.validated_data:
            self.validated_data["password"] = django.contrib.auth.hashers.make_password(
                self.validated_data["password"])
        super().save()

    def to_representation(self, instance):
        """
           Show role details in user representation
        """
        representation = super().to_representation(instance)

        representation["role"] = RoleSerializer(instance.role).data

        return representation
    
    def validate(self, data):
        """
           Check if role is active when attempting to activate a user
        """
        if "is_active" in data:
            if "role" in data:
                    if data["is_active"] == True and models.Role.objects.filter(id=data["role"].id).exists() and not models.Role.objects.get(id=data["role"].id).is_active:
                        raise serializers.ValidationError(
                            'Cannot activate a user with an inactive role')
            else:
                params_user_id = self.context["request"].parser_context["kwargs"]["pk"]
        
                if get_user_model().objects.filter(id=params_user_id).exists():
                    if data["is_active"] == True and not get_user_model().objects.get(id=params_user_id).role.is_active:
                        raise serializers.ValidationError(
                            'Cannot activate a user with an inactive role')

        return data

        


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Page
        fields = '__all__'

class ClusterTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ClusterType
        fields = '__all__'

class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Resource
        fields = '__all__'


class EndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Endpoint
        fields = '__all__'

class EndpointsClusterSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EndPointsCluster
        fields = '__all__'

    
    def to_representation(self, instance):
        """
           Show object fields instead of just ids in some fields
        """
        representation = super().to_representation(instance)

        if 'cluster_type' in representation:
            representation["cluster_type"] = ClusterTypeSerializer(models.ClusterType.objects.get(id=representation["cluster_type"])).data
        
        if 'resource' in representation:
            representation["resource"] = ResourceSerializer(models.Resource.objects.get(id=representation["resource"])).data
        
        return representation


class StationinfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stationinfo
        fields = '__all__'

    def validate(self, data):
        """
            Check that antenna_code and height_code exist in 'gamit_htc' table,
            since Django doesn't support composite foreign keys.
        """
        try:
            models.GamitHtc.objects.get(
                antenna_code=data['antenna_code'], height_code=data['height_code'])
        except models.GamitHtc.DoesNotExist:
            raise serializers.ValidationError(
                'The combination of antenna_code and height_code does not exist in the gamit_htc table')
        else:
            return data

    def to_internal_value(self, data):
        """
        Unset timezone for dates
        """

        internal_value = super().to_internal_value(data)

        if 'date_start' in internal_value and internal_value['date_start'] is not None:
            internal_value['date_start'] = internal_value['date_start'].replace(
                tzinfo=None)

        if 'date_end' in internal_value and internal_value['date_end'] is not None:
            internal_value['date_end'] = internal_value['date_end'].replace(
                tzinfo=None)

        return internal_value


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stations
        fields = '__all__'


class StationCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stations
        fields = ['station_code']


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Networks
        fields = '__all__'


class ReceiverSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Receivers
        fields = '__all__'


class AntennaSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Antennas
        fields = '__all__'


class AprCoordsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AprCoords
        fields = '__all__'


class AwsSyncSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AwsSync
        fields = '__all__'


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Country
        fields = '__all__'


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.DataSource
        fields = '__all__'


class EarthquakesSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Earthquakes
        fields = '__all__'


class EtmParamsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.EtmParams
        fields = '__all__'


class EtmsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Etms
        fields = '__all__'


class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Events
        fields = '__all__'


class ExecutionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Executions
        fields = '__all__'


class GamitHtcSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitHtc
        fields = '__all__'


class GamitSolnSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitSoln
        fields = '__all__'


class GamitSolnExclSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitSolnExcl
        fields = '__all__'


class GamitStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitStats
        fields = '__all__'


class GamitSubnetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitSubnets
        fields = '__all__'


class GamitZtdSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.GamitZtd
        fields = '__all__'


class KeysSerializer(serializers.ModelSerializer):
    isnumeric = serializers.BooleanField(required=False)

    class Meta:
        model = models.Keys
        fields = '__all__'


class LocksSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Locks
        fields = '__all__'


class PppSolnSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PppSoln
        fields = '__all__'


class PppSolnExclSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PppSolnExcl
        fields = '__all__'


class ReceiversSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Receivers
        fields = '__all__'


class RinexSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Rinex
        fields = '__all__'


class RinexSourcesInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RinexSourcesInfo
        fields = '__all__'


class RinexTankStructSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RinexTankStruct
        fields = '__all__'


class SourcesFormatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SourcesFormats
        fields = '__all__'


class SourcesServersSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SourcesServers
        fields = '__all__'


class SourcesStationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SourcesStations
        fields = '__all__'


class StacksSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stacks
        fields = '__all__'


class StationaliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stationalias
        fields = '__all__'


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @ classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        userModel = get_user_model().objects.get(username=user.username)

        token['username'] = userModel.username
        token['role_id'] = userModel.role.id
        token['role_name'] = userModel.role.name

        return token
