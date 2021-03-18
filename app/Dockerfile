FROM tiangolo/uwsgi-nginx:python3.8-alpine as base

# Based on: https://hub.docker.com/r/tiangolo/uwsgi-nginx-flask

RUN apk add --no-cache --virtual .build-deps gcc libc-dev python3-dev \
    && apk add --no-cache postgresql-dev \
    && pip install Flask==1.1.2 Flask-Mailman==0.1.7 psycopg2==2.8.6 \
    && apk del .build-deps

# URL under which static (not modified by Python) files will be requested
# They will be served by Nginx directly, without being handled by uWSGI
ENV STATIC_URL /static
# Absolute path in where the static files wil be
ENV STATIC_PATH /app/static

# If STATIC_INDEX is 1, serve / with /static/index.html directly (or the static URL configured)
# ENV STATIC_INDEX 1
ENV STATIC_INDEX 0

# Make /app/* available to be imported by Python globally to better support several use cases like Alembic migrations.
ENV PYTHONPATH=/app


# Development image
FROM base as dev

# For the dev image, we are just using Flask's built-in development server
CMD ["python", "main.py"]




# Production image
FROM base as prod

# Move the base entrypoint to reuse it
RUN mv /entrypoint.sh /uwsgi-nginx-entrypoint.sh
# Copy the entrypoint that will generate Nginx additional configs
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# Add demo app
COPY ./app /app
WORKDIR /app

# Run the start script provided by the parent image tiangolo/uwsgi-nginx.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Supervisor, which in turn will start Nginx and uWSGI
CMD ["/start.sh"]

