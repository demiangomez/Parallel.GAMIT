# Installation

This document explains how to deploy the app using Docker Compose. We will use it to build and start two containers with a single command: one for the back end and one for the front end.

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

### Params Explanation

.env file on root folder
1. MEDIA_FOLDER_HOST_PATH: path to where media (documents, images, etc.) uploaded by the user will be placed.
2. APP_PORT: port where the app will be served.
3. USER_ID_TO_SAVE_FILES: all the media saved by the app will be owned by this user.    
4. GROUP_ID_TO_SAVE_FILES: all the media saved by the app will be owned by this group. 

.env file on front_dir folder
1. VITE_API_URL: The API URL is the same as the app URL (as the front end and the back end are running on the same machine). For example, if users access the app at https://192.168.18.10:2375/, then that will also be the value for this parameter.

### Procedure

1. Define a conf file named ".env" inside the root folder following '.env.sample' (detail on this below)
2. Define a conf file named "gnss_data.cfg" under 'backend_dir/backend/' following 'backend_dir/backend/conf_example.txt'
3. Define a conf file named ".env" under 'front_dir/' following 'front_dir/.env.sample'
4. From the root directory:

```
   docker compose up --build -d
```
