FROM tiangolo/uwsgi-nginx:python3.12 as base

# Based on: https://hub.docker.com/r/tiangolo/uwsgi-nginx-flask

RUN apt-get update && apt-get install -y openssl \
    && pip install Flask==3.1.0 Flask-Login==0.6.3 psycopg2-binary==2.9.10 \
    && rm -rf /var/lib/apt/lists/*
# Flask-Mailman==0.3.0  # no longer used


# Development image
FROM base AS dev

# For the dev image, we are just using Flask's built-in development server
CMD ["python", "main.py"]



# Production image
FROM base AS prod

COPY nginx.tmpl /nginx.tmpl

# Fix error with supervisord getting confused about nginx already
# running: see https://stackoverflow.com/questions/33650820/nginx-emerg-bind-to-0-0-0-080-failed-98-address-already-in-use-on-docke
#RUN sed -i 's#command=/usr/sbin/nginx#command=/usr/sbin/nginx -g "daemon off;"#'  /etc/supervisor.d/supervisord.ini

# Copy the entrypoint that will generate Nginx additional configs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

COPY ./app /app
# RUN chown -R uwsgi:uwsgi /app
WORKDIR /app

# Run the start script provided by the parent image tiangolo/uwsgi-nginx.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Supervisor, which in turn will start Nginx and uWSGI
CMD ["/start.sh"]

