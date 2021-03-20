#! /usr/bin/env sh
set -e

sed "s/{{DOMAIN}}/$DOMAIN/g" /nginx.tmpl > /etc/nginx/conf.d/nginx.conf

# For Alpine:
# Explicitly add installed Python packages and uWSGI Python packages to PYTHONPATH
# Otherwise uWSGI can't import Flask
if [ -n "$ALPINEPYTHON" ] ; then
    export PYTHONPATH=$PYTHONPATH:/usr/local/lib/$ALPINEPYTHON/site-packages:/usr/lib/$ALPINEPYTHON/site-packages
fi

exec "$@"