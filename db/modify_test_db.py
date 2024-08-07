import os
from datetime import timedelta
from dotenv import load_dotenv
import psycopg2
import sys
import json
def table_is_from_django_app(table_name):
    PREFIXES = ["api_", "auth_", "django_", "auditlog_"]
    
    for prefix in PREFIXES:
        if table_name.startswith(prefix):
            return True
    
    return False

def get_all_django_tables(conn, cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    
    tables = cur.fetchall()

    tables = [table[0] for table in tables if table_is_from_django_app(table[0])]

    return tables

def remove_tables(conn, cur):
    for table in get_all_django_tables(conn, cur):
        query = f"DROP TABLE IF EXISTS {table} CASCADE;"
        print("Executing: ", query)
        cur.execute(query)
    conn.commit()


def remove_functions(conn, cur):
    functions_to_remove = [
        "update_has_gaps_update_needed_field",
        "update_has_stationinfo_field",
        "delete_rows_referencing_stations",
    ]

    for function in functions_to_remove:
        query = f"DROP FUNCTION IF EXISTS {function} CASCADE;"
        print("Executing: ", query)
        cur.execute(query)
    conn.commit()

if (__name__ == "__main__"):

    load_dotenv()

    # Connect to an existing database
    conn = psycopg2.connect(
        f'dbname={os.getenv("DB_NAME")} user={os.getenv("DB_USER")} password={os.getenv("DB_PASSWORD")} host={os.getenv("DB_HOST")} port={os.getenv("DB_PORT")}')

    cur = conn.cursor()

    # remove some database objects
    remove_tables(conn, cur)
    remove_functions(conn, cur)

    # Close communication with the database
    cur.close()
    conn.close()
