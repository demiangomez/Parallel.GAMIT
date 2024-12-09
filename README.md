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

1. Define a conf file named "gnss_data.cfg" under 'backend_dir/backend/' following 'backend_dir/backend/conf_example.txt'
2. Define a conf file named ".env" under 'front_dir/' following 'front_dir/.env.sample'
3. From the root directory:

```
   MEDIA_FOLDER_HOST_PATH=/path/to/media-folder docker compose up --build -d
```

### Usage

Don't change password of 'update-gaps-status' user. Otherwise, gaps status won't be updated.
