FROM postgres:13.2-alpine

COPY ./*.csv /data_imports/
COPY ./load_data.sql /docker-entrypoint-initdb.d/load_data.sql
    # files in the initdb directory are run on initialization, if
    # the data directory is empty (i.e., first time only)