#! /bin/bash

D=/home/postgres/pgdata/data
docker compose exec timescaledb mkdir -p $D/conf.d
docker compose exec timescaledb sh -c "grep -q '^include_dir' $D/postgresql.conf \
  || echo \"include_dir = 'conf.d'\" >> $D/postgresql.conf"
docker compose exec timescaledb cp /conf/timescaledb-mistral.conf $D/conf.d/
docker compose restart timescaledb