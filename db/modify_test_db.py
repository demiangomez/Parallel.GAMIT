import os
from datetime import timedelta
from dotenv import load_dotenv
import psycopg2
import sys
import json


def remove_tables(conn, cur):
    tables_to_remove = [
        "django_admin_log",
        "django_content_type",
        "django_migrations",
        "django_session",
        "auditlog_logentry",
        "api_clustertype",
        "api_endpointscluster",
        "api_endpointscluster_endpoints",
        "api_endpointscluster_endpoints",
        "api_page_endpoints_clusters",
        "api_role_endpoints_clusters",
        "api_role_pages",
        "api_pageendpoints",
        "api_endpoint",
        "api_monumenttype",
        "api_country",
        "api_resource",
        "api_page",
        "api_role",
        "api_roleendpoint",
        "api_rolepage",
        "api_roleuserstation",
        "api_stationmeta",
        "api_stationrole",
        "api_stationstatus",
        "api_user",
        "api_user_groups",
        "api_user_user_permissions",
        "auth_group",
        "auth_group_permissions",
        "auth_permission"
    ]

    for table in tables_to_remove:
        query = f"DROP TABLE IF EXISTS {table} CASCADE;"
        print("Executing: ", query)
        cur.execute(query)
    conn.commit()


if (__name__ == "__main__"):

    load_dotenv()

    # Connect to an existing database
    conn = psycopg2.connect(
        f'dbname={os.getenv("DB_NAME")} user={os.getenv("DB_USER")} password={os.getenv("DB_PASSWORD")} host={os.getenv("DB_HOST")} port={os.getenv("DB_PORT")}')

    cur = conn.cursor()

    remove_tables(conn, cur)

    # Close communication with the database
    cur.close()
    conn.close()
