#!/bin/bash
# L12 — active l'archivage des journaux vers /archives/wal et redémarre.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p archives/wal
docker compose exec -T timescaledb psql -U postgres -v ON_ERROR_STOP=1 <<'SQL'
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'test ! -f /archives/wal/%f && cp %p /archives/wal/%f';
SQL
docker compose restart timescaledb
for i in $(seq 1 60); do
  docker compose exec -T timescaledb pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker compose exec -T timescaledb psql -U postgres -c "SHOW archive_mode;" \
  -c "SELECT pg_switch_wal();" >/dev/null
sleep 2
docker compose exec -T timescaledb psql -U postgres -c "
SELECT archived_count, last_archived_wal, failed_count
FROM   pg_stat_archiver;"
