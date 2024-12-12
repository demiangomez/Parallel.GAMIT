# Generated by Django 4.2.16 on 2024-10-18 15:49

from django.db import migrations
from django.conf import settings
import psycopg2

def connect_to_db():
    conn = psycopg2.connect(
        f'dbname={settings.DATABASES["default"]["NAME"]} user={settings.DATABASES["default"]["USER"]} password={settings.DATABASES["default"]["PASSWORD"]} host={settings.DATABASES["default"]["HOST"]} port={settings.DATABASES["default"]["PORT"]}')

    cur = conn.cursor()

    return conn, cur

def create_endpoint(apps, schema_editor):
    Endpoint = apps.get_model("api", "Endpoint")

    Endpoint.objects.get_or_create(path="/api/delete-update-gaps-status-block", method="POST")

    Resource = apps.get_model("api", "Resource")
    
    Resource.objects.get_or_create(name="delete-update-gaps-status-block")

    endpoints_cluster = apps.get_model("api", "EndPointsCluster")
    endpoint = apps.get_model("api", "Endpoint")
    cluster_type = apps.get_model("api", "ClusterType")
    role = apps.get_model("api", "Role")
    resource = apps.get_model("api", "Resource")

    front_read_stations = endpoints_cluster(resource=resource.objects.get(name='delete-update-gaps-status-block'),
                                            cluster_type=cluster_type.objects.get(name="read-write"), role_type='API')
    
    front_read_stations.save()
    
    front_read_stations.endpoints.add(
        endpoint.objects.get(path="/api/delete-update-gaps-status-block", method="POST"))
    
def allow_update_gaps_user_to_delete_block(apps, schema_editor):
    
    Role = apps.get_model("api", "Role")
    User = apps.get_model("api", "User")
    EndPointsCluster = apps.get_model("api", "EndPointsCluster")
    cluster_type = apps.get_model("api", "ClusterType")
    resource = apps.get_model("api", "Resource")

    update_gaps_status_role = Role.objects.get(
        name="update-gaps-status")

    update_gaps_status_role.endpoints_clusters.add(EndPointsCluster.objects.get(resource=resource.objects.get(name='delete-update-gaps-status-block'),
                                                                             cluster_type=cluster_type.objects.get(name="read-write"), role_type='API'))


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_auto_20240920_1711'),
    ]

    operations = [
        migrations.RunPython(
            create_endpoint
        ),
        migrations.RunPython(
            allow_update_gaps_user_to_delete_block
        ),
    ]