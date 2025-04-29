from rest_framework import serializers
from . import models
import django.contrib.auth.hashers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import datetime
from . import utils
import base64
from django.core.files.images import ImageFile
from django.conf import settings
import math
import decimal
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import country_converter as coco
from pgamit.Utils import ecef2lla, lla2ecef


def validate_file_size(value):
    if value is not None:
        if value.size > int(settings.MAX_SIZE_FILE_MB) * 1024 * 1024:
            raise serializers.ValidationError(
                f'File size must be less than {settings.MAX_SIZE_FILE_MB} MB')
        else:
            return value
    else:
        return value


def validate_image_size(value):
    if value is not None:
        if value.size > int(settings.MAX_SIZE_IMAGE_MB) * 1024 * 1024:
            raise serializers.ValidationError(
                f'Image size must be less than {settings.MAX_SIZE_IMAGE_MB} MB')
        else:
            return value
    else:
        return value


class DummySerializer(serializers.Serializer):
    """
        Used to bypass DRF Spectacular's error when a serializer is not defined for a model
    """
    pass


class MonumentTypeSerializer(serializers.ModelSerializer):
    photo_file = serializers.SerializerMethodField()

    class Meta:
        model = models.MonumentType
        fields = '__all__'
        extra_kwargs = {'photo_path': {'write_only': True}}

    def get_photo_file(self, obj):
        """Returns the actual image encoded in base64"""
        request = self.context.get('request', None)
        if obj.photo_path and obj.photo_path.name:
            return utils.get_actual_image(obj.photo_path, request)
        else:
            return None

    def validate_photo_path(self, value):
        return validate_image_size(value)


class MonumentTypeMetadataOnlySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MonumentType
        fields = ['id', 'name']


class PersonSerializer(serializers.ModelSerializer):
    photo_actual_file = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = models.Person
        fields = '__all__'
        extra_kwargs = {'photo': {'write_only': True},
                        'user_name': {'read_only': True}}

    def get_photo_actual_file(self, obj):
        """Returns the actual image encoded in base64"""
        request = self.context.get('request')
        if request and request.query_params.get('without_photo') == 'true':
            return None

        if obj.photo and obj.photo.name:
            try:
                with open(obj.photo.path, 'rb') as photo_file:
                    return base64.b64encode(photo_file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def validate_first_name(self, value):
        if isinstance(value, str) and "/" in value:
            raise serializers.ValidationError(
                "First name must not contain '/' character.")
        else:
            return value

    def validate_last_name(self, value):
        if isinstance(value, str) and "/" in value:
            raise serializers.ValidationError(
                "Last name must not contain '/' character.")
        else:
            return value

    def validate_photo(self, value):
        return validate_image_size(value)

    def get_user_name(self, obj):
        """Retrieve the username from the related User model"""
        return obj.user.username if obj.user else None


class StationStatusColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StationStatusColor
        fields = '__all__'


class StationStatusSerializer(serializers.ModelSerializer):
    color_name = serializers.SerializerMethodField()

    class Meta:
        model = models.StationStatus
        fields = '__all__'
        extra_kwargs = {'color_name': {'read_only': True}}

    def get_color_name(self, obj):
        if obj.color:
            return obj.color.color
        return None


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

    def validate_photo(self, value):
        return validate_image_size(value)


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
            representation["cluster_type"] = ClusterTypeSerializer(
                models.ClusterType.objects.get(id=representation["cluster_type"])).data

        if 'resource' in representation:
            representation["resource"] = ResourceSerializer(
                models.Resource.objects.get(id=representation["resource"])).data

        return representation


class StationinfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stationinfo
        fields = '__all__'

    def validate(self, data):
        """
            Check that antenna_code and height_code exist in 'gamit_htc' table,
            since Django doesn't support composite foreign keys.
            Also check date_end is greater than date_start
        """
        try:
            models.GamitHtc.objects.get(
                antenna_code=data['antenna_code'], height_code=data['height_code'])
        except models.GamitHtc.DoesNotExist:
            raise serializers.ValidationError(
                'The combination of antenna_code and height_code does not exist in the gamit_htc table')

        if 'date_start' in data and 'date_end' in data and isinstance(data['date_start'], datetime.datetime) and isinstance(data['date_end'], datetime.datetime):
            if data['date_start'] > data['date_end']:
                raise serializers.ValidationError(
                    'date_end must be greater or equal than date_start')

        if 'date_start' in data and isinstance(data['date_start'], datetime.datetime):
            if data['date_start'] >= datetime.datetime(9999, 12, 31):
                raise serializers.ValidationError(
                    'date_start must be less than 9999-12-31')

        if 'date_end' in data and isinstance(data['date_end'], datetime.datetime):
            if data['date_end'] >= datetime.datetime(9999, 12, 31):
                raise serializers.ValidationError(
                    'date_end must be less than 9999-12-31')

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

    harpos_coeff_otl_by_file = serializers.FileField(
        write_only=True, required=False)

    class Meta:
        model = models.Stations
        fields = '__all__'
        kwargs = {'country_code': {'read_only': True}}

    def validate(self, data):
        """
            Check that lat, lon and height are provided
            or auto_x, auto_y and auto_z are provided
        """
        if 'lat' not in data or 'lon' not in data or 'height' not in data:
            if 'auto_x' not in data or 'auto_y' not in data or 'auto_z' not in data:
                raise serializers.ValidationError(
                    "fields 'lat', 'lon' and 'height' or ECEF coordinates (fields 'auto_x', 'auto_y', 'auto_z') must be provided")

        return data

    def create(self, validated_data):
        validated_data.pop('harpos_coeff_otl_by_file', None)

        return super().create(validated_data)

    def update(self, instance, validated_data):

        # set harpos_coeff_otl by file
        if 'harpos_coeff_otl_by_file' in validated_data:
            validated_data['harpos_coeff_otl'] = utils.StationUtils.parse_harpos_coeff_otl_file(
                validated_data['harpos_coeff_otl_by_file'], instance.network_code.network_code, instance.station_code)

            # Remove this field as it's not actually stored in the model
            validated_data.pop('harpos_coeff_otl_by_file')

        # Remove network_code and station_code from validated_data to prevent updates
        validated_data.pop('network_code', None)
        validated_data.pop('station_code', None)

        return super().update(instance, validated_data)

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        # set country code
        if 'lat' in internal_value and 'lon' in internal_value and internal_value['lat'] is not None and internal_value['lon'] is not None:
            geolocator = Nominatim(user_agent="Parallel.GAMIT")

            reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

            location = reverse("%f, %f" %
                               (internal_value['lat'], internal_value['lon']))

            if location and 'country_code' in location.raw['address'].keys():
                internal_value["country_code"] = coco.convert(names=location.raw['address']['country_code'],
                                                              to='ISO3')

        # set lat and lon from auto_x, auto_y, auto_z (or viceversa)

        if 'auto_x' in internal_value and 'auto_y' in internal_value and 'auto_z' in internal_value and internal_value['auto_x'] is not None and internal_value['auto_y'] is not None and internal_value['auto_z'] is not None:
            lat, lon, height = ecef2lla([float(internal_value['auto_x']),
                                         float(internal_value['auto_y']), float(internal_value['auto_z'])])
            internal_value['lat'] = lat[0]
            internal_value['lon'] = lon[0]
            internal_value['height'] = height[0]
        else:
            auto_x, auto_y, auto_z = lla2ecef([float(internal_value['lat']), float(internal_value['lon']),
                                               float(internal_value['height'])])

            internal_value['auto_x'] = auto_x[0]
            internal_value['auto_y'] = auto_y[0]
            internal_value['auto_z'] = auto_z[0]

        return internal_value


class StationMetaGapsSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StationMetaGaps
        fields = '__all__'


class StationMetaSerializer(serializers.ModelSerializer):
    navigation_actual_file = serializers.SerializerMethodField()
    station_type_name = serializers.SerializerMethodField()
    navigation_file_delete = serializers.BooleanField(write_only=True)
    station_status_name = serializers.SerializerMethodField()
    station_gaps = serializers.SerializerMethodField()
    rinex_count = serializers.SerializerMethodField()
    distinct_visit_years = serializers.SerializerMethodField()
    station_name = serializers.SerializerMethodField()

    class Meta:
        model = models.StationMeta
        fields = '__all__'
        lookup_field = "station__api_id"
        extra_kwargs = {
            'navigation_file': {'write_only': True},
            'has_gaps_last_update_datetime': {'read_only': True},
            'station_type_name': {'read_only': True},
            'station_status_name': {'read_only': True},
            'has_gaps_update_needed': {'read_only': True},
            'has_gaps': {'read_only': True},
            'has_stationinfo': {'read_only': True},
            'rinex_count': {'read_only': True},
            'distinct_visit_years': {'read_only': True},
            'station_name': {'read_only': True}
        }

    def get_station_gaps(self, obj):
        gaps = models.StationMetaGaps.objects.filter(station_meta=obj)
        return StationMetaGapsSerializer(gaps, many=True).data

    def get_navigation_actual_file(self, obj):
        """Returns the actual file encoded in base64"""

        if obj.navigation_file and obj.navigation_file.name:
            try:
                with open(obj.navigation_file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def get_station_type_name(self, obj):
        if hasattr(obj, "station_type") and obj.station_type is not None:
            return obj.station_type.name
        else:
            return None

    def get_station_status_name(self, obj):

        if hasattr(obj, "status") and obj.status is not None:
            return obj.status.name
        else:
            return None

    def to_internal_value(self, data):
        """Set filename fields"""
        internal_value = super().to_internal_value(data)

        if 'navigation_file' in data and not isinstance(data['navigation_file'], str):
            internal_value['navigation_filename'] = data['navigation_file'].name

        return internal_value

    def get_rinex_count(self, obj):
        return models.Rinex.objects.filter(network_code=obj.station.network_code.network_code, station_code=obj.station.station_code).count()

    def get_distinct_visit_years(self, obj):
        list_of_distinct_dates = models.Visits.objects.filter(
            station=obj.station).values_list('date', flat=True).distinct()

        list_of_distinct_years = list(
            set([date.year for date in list_of_distinct_dates]))

        return list_of_distinct_years

    def get_station_name(self, obj):
        return obj.station.station_name

    def validate_navigation_file(self, value):
        return validate_file_size(value)

    def update(self, instance, validated_data):

        if 'navigation_file_delete' in validated_data and instance.navigation_file and validated_data['navigation_file_delete']:
            instance.navigation_file.delete(save=False)
            instance.navigation_filename = ''

        return super().update(instance, validated_data)

    def create(self, validated_data):
        """Create a visit instance"""

        # these fields are only needed when updating
        del validated_data['navigation_file_delete']

        return super().create(validated_data)


class RolePersonStationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RolePersonStation
        fields = '__all__'


class StationTypeSerializer(serializers.ModelSerializer):
    actual_image = serializers.SerializerMethodField()

    class Meta:
        model = models.StationType
        fields = '__all__'
        extra_kwargs = {'icon': {'write_only': True}}

    def validate_icon(self, value):
        return validate_image_size(value)

    def to_internal_value(self, data):
        # Always set search_icon_on_assets_folder to False because it its true only on default station types (created at start up)
        internal_value = super().to_internal_value(data)
        internal_value['search_icon_on_assets_folder'] = False
        return internal_value

    def get_actual_image(self, obj):
        # return the image encoded in base 64
        if obj.icon and obj.icon.name:
            try:
                with open(obj.get_icon_url(), 'rb') as icon_file:
                    return base64.b64encode(icon_file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None


class StationAttachedFilesSerializer(serializers.ModelSerializer):
    actual_file = serializers.SerializerMethodField()

    class Meta:
        model = models.StationAttachedFiles
        fields = '__all__'
        extra_kwargs = {'file': {'write_only': True}}

    def to_internal_value(self, data):
        """Set filename field"""
        internal_value = super().to_internal_value(data)

        if 'file' in data:
            internal_value['filename'] = data['file'].name

        return internal_value

    def get_actual_file(self, obj):
        """Returns the actual file"""

        if obj.file and obj.file.name:
            try:
                with open(obj.file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def validate_file(self, value):
        return validate_file_size(value)


class StationAttachedFilesOnlyMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StationAttachedFiles
        fields = ['id', 'station', 'filename', 'description']


class StationImagesSerializer(serializers.ModelSerializer):
    actual_image = serializers.SerializerMethodField()

    class Meta:
        model = models.StationImages
        fields = '__all__'
        extra_kwargs = {'image': {'write_only': True}}

    def to_internal_value(self, data):
        """Set image name as name when no name is provided"""
        internal_value = super().to_internal_value(data)

        if ('name' not in data or data['name'] == '') and 'image' in data:
            internal_value['name'] = data['image'].name

        return internal_value

    def get_actual_image(self, obj):
        request = self.context.get('request', None)
        return utils.get_actual_image(obj.image, request)

    def validate_image(self, value):
        return validate_image_size(value)


class StationImagesOnlyMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StationImages
        fields = ['id', 'station', 'name', 'description']


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Campaigns
        fields = '__all__'

    def validate(self, data):

        # Check that date start is before date end.
        start_date = data['start_date'] if 'start_date' in data else (
            self.instance.start_date if self.instance is not None and hasattr(self.instance, 'start_date') else None)
        end_date = data['end_date'] if 'end_date' in data else (
            self.instance.end_date if self.instance is not None and hasattr(self.instance, 'end_date') else None)

        if start_date is not None and end_date is not None and start_date > end_date:
            raise serializers.ValidationError(
                "End Date must occur after Start Date")

        # check if all related visits date fall between campaign date range
        if self.instance is not None:
            visit_dates = models.Visits.objects.filter(
                campaign=self.instance).values_list('date', flat=True)

            for visit_date in visit_dates:
                if visit_date < start_date or visit_date > end_date:
                    raise serializers.ValidationError(
                        "All visits related to this campaign must have their date within the campaign date range")

        return data


class VisitSerializer(serializers.ModelSerializer):
    log_sheet_actual_file = serializers.SerializerMethodField()
    navigation_actual_file = serializers.SerializerMethodField()
    campaign_name = serializers.SerializerMethodField()
    log_sheet_file_delete = serializers.BooleanField(write_only=True)
    navigation_file_delete = serializers.BooleanField(write_only=True)
    observation_file_count = serializers.SerializerMethodField()
    visit_image_count = serializers.SerializerMethodField()
    other_file_count = serializers.SerializerMethodField()
    station_network_code = serializers.SerializerMethodField()
    station_station_code = serializers.SerializerMethodField()

    class Meta:
        model = models.Visits
        fields = '__all__'
        extra_kwargs = {
            'log_sheet_file': {'write_only': True},
            'navigation_file': {'write_only': True},
            'campaign_name': {'read_only': True},
            'observation_file_count': {'read_only': True},
            'visit_image_count': {'read_only': True},
            'other_file_count': {'read_only': True}
        }

    def validate(self, data):
        # Check that visit date in between campaing date range
        campaign = data['campaign'] if 'campaign' in data else (
            self.instance.campaign if self.instance is not None and hasattr(self.instance, 'campaign') else None)
        date = data['date'] if 'date' in data else (
            self.instance.date if self.instance is not None and hasattr(self.instance, 'date') else None)

        if campaign is not None and date is not None:
            if date < campaign.start_date or date > campaign.end_date:
                raise serializers.ValidationError(
                    "The visit date is NOT within the campaign date range")
        return data

    def get_campaign_name(self, obj):
        if hasattr(obj, "campaign") and obj.campaign is not None:
            return obj.campaign.name
        else:
            return None

    def get_log_sheet_actual_file(self, obj):
        """Returns the actual file encoded in base64"""

        if obj.log_sheet_file and obj.log_sheet_file.name:
            try:
                with open(obj.log_sheet_file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def get_navigation_actual_file(self, obj):
        """Returns the actual file encoded in base64"""

        if obj.navigation_file and obj.navigation_file.name:
            try:
                with open(obj.navigation_file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def update(self, instance, validated_data):

        if 'log_sheet_file_delete' in validated_data and instance.log_sheet_file and validated_data['log_sheet_file_delete']:
            instance.log_sheet_file.delete(save=False)
            instance.log_sheet_filename = ''

        if 'navigation_file_delete' in validated_data and instance.navigation_file and validated_data['navigation_file_delete']:
            instance.navigation_file.delete(save=False)
            instance.navigation_filename = ''

        return super().update(instance, validated_data)

    def create(self, validated_data):
        """Create a visit instance"""

        # these fields are only needed when updating
        del validated_data['log_sheet_file_delete']
        del validated_data['navigation_file_delete']

        return super().create(validated_data)

    def to_internal_value(self, data):
        """Set filename fields"""
        internal_value = super().to_internal_value(data)

        if 'log_sheet_file' in data and not isinstance(data['log_sheet_file'], str):
            internal_value['log_sheet_filename'] = data['log_sheet_file'].name

        if 'navigation_file' in data and not isinstance(data['navigation_file'], str):
            internal_value['navigation_filename'] = data['navigation_file'].name

        return internal_value

    def validate_log_sheet_file(self, value):
        return validate_file_size(value)

    def validate_navigation_file(self, value):
        return validate_file_size(value)

    def get_observation_file_count(self, obj):
        return models.VisitGNSSDataFiles.objects.filter(visit=obj).count()

    def get_visit_image_count(self, obj):
        return models.VisitImages.objects.filter(visit=obj).count()

    def get_other_file_count(self, obj):
        return models.VisitAttachedFiles.objects.filter(visit=obj).count()

    def get_station_network_code(self, obj):
        if hasattr(obj, "station") and obj.station is not None:
            return obj.station.network_code.network_code
        else:
            return None

    def get_station_station_code(self, obj):
        if hasattr(obj, "station") and obj.station is not None:
            return obj.station.station_code
        else:
            return None


class VisitAttachedFilesSerializer(serializers.ModelSerializer):
    actual_file = serializers.SerializerMethodField()

    class Meta:
        model = models.VisitAttachedFiles
        fields = '__all__'
        extra_kwargs = {'file': {'write_only': True}}

    def to_internal_value(self, data):
        """Set filename field"""
        internal_value = super().to_internal_value(data)

        if 'file' in data:
            internal_value['filename'] = data['file'].name

        return internal_value

    def get_actual_file(self, obj):
        """Returns the actual file"""

        if obj.file and obj.file.name:
            try:
                with open(obj.file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def validate_file(self, value):
        return validate_file_size(value)


class VisitAttachedFilesOnlyMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VisitAttachedFiles
        fields = ['id', 'visit', 'filename', 'description']


class VisitImagesSerializer(serializers.ModelSerializer):
    actual_image = serializers.SerializerMethodField()

    class Meta:
        model = models.VisitImages
        fields = '__all__'
        extra_kwargs = {'image': {'write_only': True}}

    def to_internal_value(self, data):
        """Set image name as name when no name is provided"""
        internal_value = super().to_internal_value(data)

        if ('name' not in data or data['name'] == '') and 'image' in data:
            internal_value['name'] = data['image'].name

        return internal_value

    def get_actual_image(self, obj):
        request = self.context.get('request', None)
        return utils.get_actual_image(obj.image, request)

    def validate_image(self, value):
        return validate_image_size(value)


class VisitImagesOnlyMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VisitImages
        fields = ['id', 'visit', 'name', 'description']


class VisitGNSSDataFilesSerializer(serializers.ModelSerializer):
    actual_file = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = models.VisitGNSSDataFiles
        fields = '__all__'
        extra_kwargs = {'file': {'write_only': True}}

    def to_internal_value(self, data):
        """Set filename field"""
        internal_value = super().to_internal_value(data)

        if 'file' in data:
            internal_value['filename'] = data['file'].name

        return internal_value

    def get_actual_file(self, obj):
        """Returns the actual file"""

        if obj.file and obj.file.name:
            try:
                with open(obj.file.path, 'rb') as file:
                    return base64.b64encode(file.read()).decode('utf-8')
            except FileNotFoundError:
                return None
        else:
            return None

    def get_file_count(self, obj):
        return models.VisitGNSSDataFiles.objects.filter(visit=obj.visit).count()

    def validate_file(self, value):
        return validate_file_size(value)


class VisitGNSSDataFilesOnlyMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VisitGNSSDataFiles
        fields = ['id', 'visit', 'filename', 'description']


class StationCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stations
        fields = ['station_code']


class StationRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.StationRole
        fields = '__all__'


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

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        for key, value in representation.items():
            if isinstance(value, decimal.Decimal) and math.isnan(value):
                representation[key] = None
        return representation


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
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        userModel = get_user_model().objects.get(username=user.username)

        token['username'] = userModel.username
        token['role_id'] = userModel.role.id
        token['role_name'] = userModel.role.name

        return token
