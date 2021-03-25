#!/bin/bash

COMPOSE="/usr/local/bin/docker-compose -f compose.common.yml -f compose.prod.yml"

cd /home/jeff/portertree/
$COMPOSE run certbot renew && $COMPOSE exec -d -T app nginx -s reload
