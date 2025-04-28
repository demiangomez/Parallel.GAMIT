# Installation

### Prerequirements

1. Docker installed

### DB Setup

Skip this part if you are using an existing db

1. bash command as postgres user: createuser gnss_data_osu;
2. bash command as postgres user: createdb gnss;
3. psql command as postgres user at postgres db: alter user gnss_data_osu with password 'password';
4. bash command as postgres user: psql -d gnss -f DUMP_FILE_PATH > LOG_FILE_PATH 2>&1 &
5. psql command as postgres user at postgres db: alter database gnss owner to gnss_data_osu;
6. psql command as postgres user at postgres db: GRANT ALL PRIVILEGES ON DATABASE gnss TO gnss_data_osu;
7. set postgresql.conf file properly
8. set pg_hba.conf file properly

### Procedure
1. Define a conf file named ".env" inside the root folder following '.env.sample'
2. Define a conf file named "gnss_data.cfg" following the example under 'backend/' following 'backend/conf_example.txt'
3. From the root directory:

```
   docker compose up --build -d
```

# Tests

There are some test created. Before running them, you need to manually create an empty database with the same schema as the one used in production.

This database should be named 'test\_{PRODUCTION_DB_NAME}' and should be accessible by the user specified in the config file.

You should use the script 'db/modify_test_db.py' to remove some tables that may generate conflict. DONT forget to
set .env under 'db' folder file with test db credentials.

To run the tests, under root directory

```
    cd backend/backend_django_project/
    python manage.py test --keepdb
```

# Docs

There's a file called 'schema.yml' under 'backend/docs/' with the API documentation. It follows the OpenApi specification. In order to generate the client, run the following command under 'backend/docs/':

```
    sudo docker run -p 8080:8080 -e SWAGGER_JSON=/schema.yml -v ${PWD}/schema.yml:/schema.yml swaggerapi/swagger-ui
```

Now open any web browser and type 'localhost:8080' to use the API client.
