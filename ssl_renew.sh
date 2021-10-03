#!/bin/bash

COMPOSE="/usr/local/bin/docker-compose -f compose.common.yml -f compose.prod.yml"
DOCKER="/usr/bin/docker"

cd /home/jeff/portertree/
echo $(date)
$COMPOSE run certbot renew && $COMPOSE exec -d -T app nginx -s reload
$DOCKER system prune -f
