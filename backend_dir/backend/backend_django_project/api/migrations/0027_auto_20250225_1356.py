# Generated by Django 5.0.4 on 2025-02-25 13:56

from django.db import migrations


def add_status_color(apps, schema_editor):
    StationStatusColor = apps.get_model('api', 'StationStatusColor')
    colors = [
        "green-icon",
        "light-green-icon",
        "yellow-icon",
        "light-gray-icon",
        "gray-icon",
        "light-red-icon",
        "granate-icon",
        "blue-icon",
        "lilac-icon",
        "purple-icon",
        "light-blue-icon",
        "orange-icon"
    ]
    for color in colors:
        StationStatusColor.objects.create(color=color)


def add_station_status(apps, schema_editor):
    StationStatus = apps.get_model('api', 'StationStatus')
    StationStatusColor = apps.get_model('api', 'StationStatusColor')
    statuses = [
        "Active Online",
        "Active Offline",
        "Deactivated",
        "Destroyed",
        "Unknown"
    ]
    colors = ["green-icon", "light-green-icon",
              "light-red-icon", "light-gray-icon", "gray-icon"]
    for status, color in zip(statuses, colors):
        StationStatus.objects.create(
            name=status, color=StationStatusColor.objects.get(color=color))


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0026_stationstatuscolor_alter_stationstatus_color'),
    ]

    operations = [
        migrations.RunPython(add_status_color),
        migrations.RunPython(add_station_status)
    ]
