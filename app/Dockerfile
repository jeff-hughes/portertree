FROM tiangolo/uwsgi-nginx:python3.8-alpine as base

# Based on: https://hub.docker.com/r/tiangolo/uwsgi-nginx-flask

RUN apk add --no-cache --virtual .build-deps gcc libc-dev python3-dev \
    && apk add --no-cache openssl postgresql-dev \
    && pip install Flask==1.1.2 Flask-Login==0.5.0 Flask-Mailman==0.1.7 psycopg2==2.8.6 \
    && apk del .build-deps


# Development image
FROM base as dev

# For the dev image, we are just using Flask's built-in development server
CMD ["python", "main.py"]



# Production image
FROM base as prod

COPY nginx.tmpl /nginx.tmpl

# Fix error with supervisord getting confused about nginx already
# running: see https://stackoverflow.com/questions/33650820/nginx-emerg-bind-to-0-0-0-080-failed-98-address-already-in-use-on-docke
RUN sed -i 's#command=/usr/sbin/nginx#command=/usr/sbin/nginx -g "daemon off;"#'  /etc/supervisor.d/supervisord.ini

# Copy the entrypoint that will generate Nginx additional configs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

COPY ./app /app
RUN chown -R uwsgi:uwsgi /app
WORKDIR /app

# Run the start script provided by the parent image tiangolo/uwsgi-nginx.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Supervisor, which in turn will start Nginx and uWSGI
CMD ["/start.sh"]

