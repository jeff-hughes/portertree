FROM tiangolo/meinheld-gunicorn:python3.8-alpine3.11 as base

# Based on: https://hub.docker.com/r/tiangolo/meinheld-gunicorn-flask/

RUN apk add --no-cache --virtual .build-deps gcc libc-dev python3-dev \
    && apk add --no-cache postgresql-dev \
    && pip install Flask==1.1.2 Flask-Mailman==0.1.7 psycopg2==2.8.6 \
    && apk del .build-deps


# Development image
FROM base as dev

WORKDIR /app

# For the dev image, we are just using Flask's built-in development server
CMD ["python", "main.py"]



# Production image
FROM base as prod

COPY ./app /app
WORKDIR /app

# Run the start script provided by the parent image
# tiangolo/meinheld-gunicorn-docker.
# It will check for an /app/prestart.sh script (e.g. for migrations)
# And then will start Gunicorn with Meinheld
CMD ["/start.sh"]
