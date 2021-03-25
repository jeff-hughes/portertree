#! /usr/bin/env sh
set -e

sed "s/{{DOMAIN}}/$DOMAIN/g" /nginx.tmpl > /etc/nginx/conf.d/nginx.conf

# create Diffie-Hellman parameters for SSL if they don't yet exist
DHPARAM="/etc/ssl/certs/dhparam-2048.pem"
if [ ! -f $DHPARAM ]; then
    openssl dhparam -out $DHPARAM 2048
fi

# For Alpine:
# Explicitly add installed Python packages and uWSGI Python packages to PYTHONPATH
# Otherwise uWSGI can't import Flask
if [ -n "$ALPINEPYTHON" ] ; then
    export PYTHONPATH=$PYTHONPATH:/usr/local/lib/$ALPINEPYTHON/site-packages:/usr/lib/$ALPINEPYTHON/site-packages
fi

exec "$@"
