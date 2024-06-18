from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from auditlog.registry import auditlog
from . import custom_fields
import sys
import inspect

# ------------------------------MODELS BASED ON EXISTING DB-----------------------------


class Antennas(models.Model):
    # Field name made lowercase.
    antenna_code = models.CharField(
        db_column='AntennaCode', max_length=22)
    # Field name made lowercase.
    antenna_description = models.CharField(
        db_column='AntennaDescription', blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'antennas'


class AprCoords(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode')
    # Field name made lowercase.
    f_year = models.DecimalField(
        db_column='FYear', max_digits=120, decimal_places=50, blank=True, null=True)
    x = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    y = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    z = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    sn = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    se = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    su = models.DecimalField(
        max_digits=120, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    reference_frame = models.CharField(
        db_column='ReferenceFrame', max_length=20, blank=True, null=True)
    year = models.IntegerField(db_column='Year')  # Field name made lowercase.
    doy = models.IntegerField(db_column='DOY')  # Field name made lowercase.
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'apr_coords'
        unique_together = (('network_code', 'station_code', 'year', 'doy'),)


class AwsSync(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode')
    # Field name made lowercase.
    station_alias = models.CharField(db_column='StationAlias', max_length=4)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    sync_date = models.DateTimeField(blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'aws_sync'
        unique_together = (('network_code', 'station_code', 'year', 'doy'),)

class DataSource(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    try_order = models.DecimalField(max_digits=65535, decimal_places=65535)
    protocol = models.CharField()
    fqdn = models.CharField()
    username = models.CharField(blank=True, null=True)
    password = models.CharField(blank=True, null=True)
    path = models.CharField(blank=True, null=True)
    format = models.CharField(blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'data_source'
        unique_together = (('network_code', 'station_code', 'try_order'),)


class Earthquakes(models.Model):
    # The composite primary key (date, lat, lon) found, that is not supported. The first column is selected.
    date = models.DateTimeField()
    lat = models.DecimalField(max_digits=65535, decimal_places=65535)
    lon = models.DecimalField(max_digits=65535, decimal_places=65535)
    depth = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    mag = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    strike1 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    dip1 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    rake1 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    strike2 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    dip2 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    rake2 = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    id = models.CharField(max_length=40, blank=True, null=True)
    location = models.CharField(max_length=120, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'earthquakes'
        unique_together = (('date', 'lat', 'lon'),)


class EtmParams(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    soln = models.CharField(max_length=10)
    object = models.CharField(max_length=10)
    terms = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    frequencies = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    jump_type = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    relaxation = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=150, decimal_places=50, blank=True, null=True)
    action = models.CharField(max_length=1, blank=True, null=True)
    uid = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'etm_params'


class Etms(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    soln = models.CharField(max_length=10)
    object = models.CharField(max_length=10)
    t_ref = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    jump_type = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    relaxation = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    frequencies = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    params = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    sigmas = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    metadata = models.TextField(blank=True, null=True)
    hash = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    jump_date = models.DateTimeField(blank=True, null=True)
    uid = models.AutoField(primary_key=True)
    stack = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'etms'


class Events(models.Model):
    # The composite primary key (event_id, EventDate) found, that is not supported. The first column is selected.
    event_id = models.BigAutoField(primary_key=True)
    # Field name made lowercase.
    event_date = models.DateTimeField(auto_now_add=True, db_column='EventDate')
    # Field name made lowercase.
    event_type = models.CharField(
        db_column='EventType', max_length=6, blank=True, null=True)
    # Field name made lowercase.
    network_code = models.CharField(
        db_column='NetworkCode', max_length=3, blank=True, null=True)
    # Field name made lowercase.
    station_code = models.CharField(
        db_column='StationCode', max_length=4, blank=True, null=True)
    # Field name made lowercase.
    year = models.IntegerField(db_column='Year', blank=True, null=True)
    # Field name made lowercase.
    doy = models.IntegerField(db_column='DOY', blank=True, null=True)
    # Field name made lowercase.
    description = models.TextField(
        db_column='Description', blank=True, null=True)
    stack = models.TextField(blank=True, null=True)
    module = models.TextField(blank=True, null=True)
    node = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'events'
        unique_together = (('event_id', 'event_date'),)


class Executions(models.Model):
    script = models.CharField(max_length=40, blank=True, null=True)
    exec_date = models.DateTimeField(blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'executions'


class GamitHtc(models.Model):
    # Field name made lowercase. The composite primary key (AntennaCode, HeightCode) found, that is not supported. The first column is selected.
    antenna_code = models.CharField(db_column='AntennaCode', max_length=22)
    # Field name made lowercase.
    height_code = models.CharField(db_column='HeightCode', max_length=5)
    v_offset = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    h_offset = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)

    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_htc'
        unique_together = (('antenna_code', 'height_code'),)


class GamitSoln(models.Model):
    # Field name made lowercase.
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    project = models.CharField(db_column='Project', max_length=20)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    fyear = models.DecimalField(
        db_column='FYear', max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    x = models.DecimalField(db_column='X', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    y = models.DecimalField(db_column='Y', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    z = models.DecimalField(db_column='Z', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    sigmax = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmay = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    variance_factor = models.DecimalField(
        db_column='VarianceFactor', max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxy = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmayz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_soln'
        unique_together = (
            ('network_code', 'station_code', 'project', 'year', 'doy'),)


class GamitSolnExcl(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    project = models.CharField(db_column='Project', max_length=20)
    # Field name made lowercase.
    year = models.BigIntegerField(db_column='Year')
    doy = models.BigIntegerField(db_column='DOY')  # Field name made lowercase.
    residual = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_soln_excl'
        unique_together = (
            ('network_code', 'station_code', 'project', 'year', 'doy'),)


class GamitStats(models.Model):
    # Field name made lowercase. The composite primary key (Project, subnet, Year, DOY, system) found, that is not supported. The first column is selected.
    project = models.CharField(
        db_column='Project', max_length=20)
    subnet = models.DecimalField(max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    f_year = models.DecimalField(
        db_column='FYear', max_digits=150, decimal_places=50, blank=True, null=True)
    wl = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    nl = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    nrms = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    relaxed_constrains = models.TextField(blank=True, null=True)
    max_overconstrained = models.CharField(max_length=8, blank=True, null=True)
    updated_apr = models.TextField(blank=True, null=True)
    iterations = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    node = models.CharField(max_length=50, blank=True, null=True)
    execution_time = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    execution_date = models.DateTimeField(blank=True, null=True)
    system = models.CharField(max_length=1)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_stats'
        unique_together = (('project', 'subnet', 'year', 'doy', 'system'),)


class GamitSubnets(models.Model):
    # Field name made lowercase. The composite primary key (Project, subnet, Year, DOY) found, that is not supported. The first column is selected.
    project = models.CharField(
        db_column='Project', max_length=20)
    subnet = models.DecimalField(max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    centroid = ArrayField(models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True))
    stations = ArrayField(models.CharField())
    alias = ArrayField(models.CharField())
    ties = ArrayField(models.CharField())
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_subnets'
        unique_together = (('project', 'subnet', 'year', 'doy'),)


class GamitZtd(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    date = models.DateTimeField(db_column='Date')  # Field name made lowercase.
    # Field name made lowercase.
    project = models.CharField(db_column='Project', max_length=20)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    ztd = models.DecimalField(
        db_column='ZTD', max_digits=65535, decimal_places=65535)
    model = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigma = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'gamit_ztd'
        unique_together = (('network_code', 'station_code',
                           'date', 'project', 'year', 'doy'),)


class Keys(models.Model):
    # Field name made lowercase.
    key_code = models.CharField(
        db_column='KeyCode', max_length=7)
    # Field name made lowercase.
    total_chars = models.IntegerField(
        db_column='TotalChars', blank=True, null=True)
    rinex_col_out = models.CharField(blank=True, null=True)
    rinex_col_in = models.CharField(max_length=60, blank=True, null=True)
    isnumeric = custom_fields.BitField(null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'keys'


class Locks(models.Model):
    filename = models.TextField()
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(
        db_column='StationCode', max_length=4, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'locks'


class Networks(models.Model):
    # Field name made lowercase.
    network_code = models.CharField(db_column='NetworkCode', unique=True)
    # Field name made lowercase.
    network_name = models.CharField(
        db_column='NetworkName', blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'networks'


class PppSoln(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode')
    # Field name made lowercase.
    x = models.DecimalField(db_column='X', max_digits=12,
                            decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    y = models.DecimalField(db_column='Y', max_digits=12,
                            decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    z = models.DecimalField(db_column='Z', max_digits=12,
                            decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    reference_frame = models.CharField(
        db_column='ReferenceFrame', max_length=20)
    sigmax = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmay = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxy = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmayz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    hash = models.IntegerField(blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'ppp_soln'
        unique_together = (('network_code', 'station_code',
                           'year', 'doy', 'reference_frame'),)


class PppSolnExcl(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'ppp_soln_excl'
        unique_together = (('network_code', 'station_code', 'year', 'doy'),)


class Receivers(models.Model):
    # Field name made lowercase.
    receiver_code = models.CharField(
        db_column='ReceiverCode', max_length=22)
    # Field name made lowercase.
    receiver_description = models.CharField(
        db_column='ReceiverDescription', max_length=22, blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'receivers'


class Rinex(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode')
    # Field name made lowercase.
    observation_year = models.DecimalField(
        db_column='ObservationYear', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    observation_month = models.DecimalField(
        db_column='ObservationMonth', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    observation_day = models.DecimalField(
        db_column='ObservationDay', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    observation_doy = models.DecimalField(
        db_column='ObservationDOY', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    observation_f_year = models.DecimalField(
        db_column='ObservationFYear', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    observation_s_time = models.DateTimeField(
        db_column='ObservationSTime', blank=True, null=True)
    # Field name made lowercase.
    observation_e_time = models.DateTimeField(
        db_column='ObservationETime', blank=True, null=True)
    # Field name made lowercase.
    receiver_type = models.CharField(
        db_column='ReceiverType', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    receiver_serial = models.CharField(
        db_column='ReceiverSerial', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    receiver_fw = models.CharField(
        db_column='ReceiverFw', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    antenna_type = models.CharField(
        db_column='AntennaType', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    antenna_serial = models.CharField(
        db_column='AntennaSerial', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    antenna_dome = models.CharField(
        db_column='AntennaDome', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    filename = models.CharField(
        db_column='Filename', max_length=50, blank=True, null=True)
    # Field name made lowercase.
    interval = models.DecimalField(
        db_column='Interval', max_digits=150, decimal_places=50)
    # Field name made lowercase.
    antenna_offset = models.DecimalField(
        db_column='AntennaOffset', max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    completion = models.DecimalField(
        db_column='Completion', max_digits=7, decimal_places=3)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'rinex'
        unique_together = (('network_code', 'station_code', 'observation_year',
                           'observation_doy', 'interval', 'completion'),)


class RinexSourcesInfo(models.Model):
    name = models.CharField(max_length=20)
    fqdn = models.CharField()
    protocol = models.CharField()
    username = models.CharField(blank=True, null=True)
    password = models.CharField(blank=True, null=True)
    path = models.CharField(blank=True, null=True)
    format = models.CharField(blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'rinex_sources_info'


class RinexTankStruct(models.Model):
    # Field name made lowercase.
    level = models.IntegerField(db_column='Level')
    # Field name made lowercase.
    key_code = models.ForeignKey(
        Keys, models.DO_NOTHING, db_column='KeyCode', blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'rinex_tank_struct'


class SourcesFormats(models.Model):
    format = models.CharField()
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'sources_formats'


class SourcesServers(models.Model):
    server_id = models.AutoField(primary_key=True)
    protocol = models.CharField()
    fqdn = models.CharField()
    username = models.CharField(blank=True, null=True)
    password = models.CharField(blank=True, null=True)
    path = models.CharField(blank=True, null=True)
    format = models.ForeignKey(
        SourcesFormats, models.DO_NOTHING, db_column='format')

    class Meta:
        managed = False
        db_table = 'sources_servers'


class SourcesStations(models.Model):
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    station_code = models.CharField(db_column='StationCode', max_length=4)
    try_order = models.SmallIntegerField()
    server_id = models.ForeignKey(SourcesServers, models.DO_NOTHING)
    path = models.CharField(blank=True, null=True)
    format = models.ForeignKey(
        SourcesFormats, models.DO_NOTHING, db_column='format', blank=True, null=True)

    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'sources_stations'
        unique_together = (('network_code', 'station_code', 'try_order'),)


class Stacks(models.Model):
    # Field name made lowercase. The composite primary key (NetworkCode, StationCode, Year, DOY, name) found, that is not supported. The first column is selected.
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    project = models.CharField(db_column='Project', max_length=20)
    # Field name made lowercase.
    year = models.DecimalField(
        db_column='Year', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    doy = models.DecimalField(
        db_column='DOY', max_digits=65535, decimal_places=65535)
    # Field name made lowercase.
    f_year = models.DecimalField(
        db_column='FYear', max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    x = models.DecimalField(db_column='X', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    y = models.DecimalField(db_column='Y', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    z = models.DecimalField(db_column='Z', max_digits=150,
                            decimal_places=50, blank=True, null=True)
    sigmax = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmay = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    variance_factor = models.DecimalField(
        db_column='VarianceFactor', max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxy = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmayz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    sigmaxz = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    name = models.CharField(max_length=20)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'stacks'
        unique_together = (
            ('network_code', 'station_code', 'year', 'doy', 'name'),)


class Stationalias(models.Model):
    # Field name made lowercase.
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    station_alias = models.CharField(
        db_column='StationAlias', unique=True, max_length=4)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'stationalias'
        unique_together = (('network_code', 'station_code'),)


class Stationinfo(models.Model):
    # Field name made lowercase.
    network_code = models.CharField(db_column='NetworkCode', max_length=3)
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    receiver_code = models.CharField(
        db_column='ReceiverCode', max_length=22)
    # Field name made lowercase.
    receiver_serial = models.CharField(
        db_column='ReceiverSerial', max_length=22, blank=True, null=True)
    # Field name made lowercase.
    receiver_firmware = models.CharField(
        db_column='ReceiverFirmware', max_length=10, blank=True, null=True)
    # Field name made lowercase.
    antenna_code = models.CharField(
        db_column='AntennaCode', max_length=22)
    # Field name made lowercase.
    antenna_serial = models.CharField(
        db_column='AntennaSerial', max_length=20, blank=True, null=True)
    # Field name made lowercase.
    antenna_height = models.DecimalField(
        db_column='AntennaHeight', max_digits=6, decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    antenna_north = models.DecimalField(
        db_column='AntennaNorth', max_digits=12, decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    antenna_east = models.DecimalField(
        db_column='AntennaEast', max_digits=12, decimal_places=4, blank=True, null=True)
    # Field name made lowercase.
    height_code = models.CharField(
        db_column='HeightCode')
    # Field name made lowercase.
    radome_code = models.CharField(db_column='RadomeCode', max_length=7)
    # Field name made lowercase.
    date_start = models.DateTimeField(db_column='DateStart')
    # Field name made lowercase.
    date_end = models.DateTimeField(db_column='DateEnd', blank=True, null=True)
    # Field name made lowercase.
    receiver_vers = models.CharField(
        db_column='ReceiverVers', max_length=22, blank=True, null=True)
    # Field name made lowercase.
    comments = models.TextField(db_column='Comments', blank=True, null=True)
    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'stationinfo'
        ordering = ["date_start"]
        constraints = [
            models.UniqueConstraint(
                fields=['network_code', 'station_code', 'date_start'], name='network_code_station_code_date_start_unique')
        ]


class Stations(models.Model):
    # Field name made lowercase.
    network_code = models.ForeignKey(
        Networks, models.DO_NOTHING, db_column='NetworkCode', to_field="network_code")
    # Field name made lowercase.
    station_code = models.CharField(db_column='StationCode', max_length=4)
    # Field name made lowercase.
    station_name = models.CharField(
        db_column='StationName', max_length=40, blank=True, null=True)
    # Field name made lowercase.
    date_start = models.DecimalField(
        db_column='DateStart', max_digits=7, decimal_places=3, blank=True, null=True)
    # Field name made lowercase.
    date_end = models.DecimalField(
        db_column='DateEnd', max_digits=7, decimal_places=3, blank=True, null=True)
    auto_x = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    auto_y = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    auto_z = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    # Field name made lowercase.
    harpos_coeff_otl = models.TextField(
        db_column='Harpos_coeff_otl', blank=True, null=True)
    lat = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    lon = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    height = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    max_dist = models.DecimalField(
        max_digits=150, decimal_places=50, blank=True, null=True)
    dome = models.CharField(max_length=9, blank=True, null=True)
    country_code = models.CharField(max_length=3, blank=True, null=True)
    marker = models.IntegerField(blank=True, null=True)

    api_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'stations'
        ordering = ["api_id"]
        unique_together = (('network_code', 'station_code'),
                           ('network_code', 'station_code'),)


# ----------------------------------API-SPECIFIC MODELS-------------------------------------

class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    two_digits_code = models.CharField(max_length=2, unique=True)
    three_digits_code = models.CharField(max_length=3, unique=True)
    

    def __str__(self):
        return self.name

class Endpoint(models.Model):
    path = models.CharField(max_length=100)
    description = models.CharField(max_length=100, blank=True)

    METHOD_CHOICES = {
        "GET": "GET",
        "POST": "POST",
        "PUT": "PUT",
        "DELETE": "DELETE",
        "PATCH": "PATCH",
        "ALL": "ALL"
    }

    method = models.CharField(max_length=6, choices=METHOD_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['path', 'method'], name='path_method_unique')
        ]

    def __str__(self):
        return self.path


class ClusterType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class Resource(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
class EndPointsCluster(models.Model):
    resource = models.ForeignKey(Resource, models.CASCADE)
    description = models.CharField(max_length=100, blank=True)
    endpoints = models.ManyToManyField(Endpoint)
    cluster_type = models.ForeignKey(ClusterType, models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['resource', 'cluster_type', 'description'], name='resource_cluster_type_description_unique')
        ]
    
class Page(models.Model):
    url = models.CharField(max_length=100)
    description = models.CharField(max_length=100, blank=True)
    endpoints_clusters = models.ManyToManyField(EndPointsCluster)

    def __str__(self):
        return self.url

    
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    role_api = models.BooleanField()
    allow_all = models.BooleanField()
    endpoints_clusters = models.ManyToManyField(EndPointsCluster, blank=True)
    pages = models.ManyToManyField(Page, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    role = models.ForeignKey(
        Role, models.CASCADE)
    phone = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='user_photos/', blank=True)

    REQUIRED_FIELDS = ["role"]

    def __str__(self):
        return self.username


class StationRole(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class RoleUserStation(models.Model):
    role = models.ForeignKey(StationRole, models.CASCADE)
    user = models.ForeignKey(User, models.CASCADE)
    station = models.ForeignKey(Stations, models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'user', 'station'], name='role_user_station_unique')
        ]


class StationStatus(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class MonumentType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class StationMeta(models.Model):
    station = models.ForeignKey(Stations, models.CASCADE)
    status = models.ForeignKey(StationStatus, models.CASCADE)
    monument_type = models.ForeignKey(MonumentType, models.CASCADE)
    remote_access_link = models.CharField(max_length=100, blank=True)
    has_battery = models.BooleanField()
    battery_description = models.CharField(max_length=100, blank=True)
    has_communications = models.BooleanField()
    communications_description = models.CharField(max_length=100, blank=True)
    comments = models.CharField(max_length=100, blank=True)


def enable_automatic_auditlog():
    auditlog.register(Networks)
    auditlog.register(Antennas)
    auditlog.register(AprCoords)
    auditlog.register(AwsSync)
    auditlog.register(Country)
    auditlog.register(DataSource)
    auditlog.register(Earthquakes)
    auditlog.register(EtmParams)
    auditlog.register(Etms)
    auditlog.register(Events)
    auditlog.register(Executions)
    auditlog.register(GamitHtc)
    auditlog.register(GamitSoln)
    auditlog.register(GamitSolnExcl)
    auditlog.register(GamitStats)
    auditlog.register(GamitSubnets)
    auditlog.register(GamitZtd)
    auditlog.register(Keys)
    auditlog.register(Locks)
    auditlog.register(Networks)
    auditlog.register(PppSoln)
    auditlog.register(PppSolnExcl)
    auditlog.register(Receivers)
    auditlog.register(Rinex)
    auditlog.register(RinexSourcesInfo)
    auditlog.register(RinexTankStruct)
    auditlog.register(SourcesFormats)
    auditlog.register(SourcesServers)
    auditlog.register(SourcesStations)
    auditlog.register(Stacks)
    auditlog.register(Stationalias)
    auditlog.register(Stationinfo)
    auditlog.register(Stations)
    auditlog.register(Role)
    auditlog.register(User)
    auditlog.register(Page)
    auditlog.register(Endpoint)
    auditlog.register(StationRole)
    auditlog.register(RoleUserStation)
    auditlog.register(StationStatus)
    auditlog.register(MonumentType)
    auditlog.register(StationMeta)
    auditlog.register(EndPointsCluster)


enable_automatic_auditlog()