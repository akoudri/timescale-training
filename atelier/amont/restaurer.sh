#!/bin/bash
# Parcours amont : démarre les deux instances et restaure les trois jeux.
# À exécuter une fois avant L01. Idempotent (détruit et refait les bases).
set -euo pipefail
cd "$(dirname "$0")/.."

JEUX=../generateur/output
for f in mesures-avant.dump mistral-referentiel.dump mistral-legacy.dump \
         mesures.bin mesures-hc.bin machines-avec-arret.json; do
  [ -f "$JEUX/$f" ] || { echo "jeu manquant : $JEUX/$f (lancer le générateur)"; exit 1; }
done

mkdir -p pgdata pgdata-legacy archives
docker compose up -d

echo "attente des instances…"
for c in timescaledb legacy; do
  for i in $(seq 1 90); do
    docker compose exec -T "$c" pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 1
  done
done
sleep 2

PSQL_T=(docker compose exec -T timescaledb psql -U postgres -v ON_ERROR_STOP=1)
PSQL_L=(docker compose exec -T legacy psql -U postgres -v ON_ERROR_STOP=1)

# postgresql.conf : point d'inclusion pour la configuration de l'atelier
# (L01 étape 3 copie conf/timescaledb-mistral.conf dans conf.d/)
docker compose exec -T timescaledb bash -c '
  PGDATA=/home/postgres/pgdata/data
  mkdir -p $PGDATA/conf.d
  grep -q "include_dir = .conf.d." $PGDATA/postgresql.conf ||
    echo "include_dir = '\''conf.d'\''" >> $PGDATA/postgresql.conf'

echo "== base mistral : table de référence (5 jours), référentiel, haute cardinalité =="
"${PSQL_T[@]}" -c "DROP DATABASE IF EXISTS mistral;" -c "CREATE DATABASE mistral;"
"${PSQL_T[@]}" -d mistral -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

docker compose exec -T timescaledb pg_restore -U postgres --no-owner \
  -d mistral /jeux/mesures-avant.dump
docker compose exec -T timescaledb pg_restore -U postgres --no-owner \
  -d mistral /jeux/mistral-referentiel.dump

"${PSQL_T[@]}" -d mistral <<'SQL'
CREATE TABLE mesures_hc (
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
);
SELECT create_hypertable('mesures_hc', by_range('ts', INTERVAL '1 day'),
                         create_default_indexes => false);
SQL
docker compose exec -T timescaledb psql -U postgres -d mistral -q \
  -c "\\copy mesures_hc FROM '/jeux/mesures-hc.bin' WITH (FORMAT binary)"

echo "== instance source : mistral_legacy (PostgreSQL 16) =="
"${PSQL_L[@]}" -c "DROP DATABASE IF EXISTS mistral_legacy;" -c "CREATE DATABASE mistral_legacy;"
docker compose exec -T legacy pg_restore -U postgres --no-owner -j 4 \
  -d mistral_legacy /jeux/mistral-legacy.dump

echo "== contrôles =="
"${PSQL_T[@]}" -d mistral -At -c "
  SELECT 'mesures (table ordinaire, 5 j) : ' || count(*) FROM mesures;" \
  -c "SELECT 'mesures_hc : ' || count(*) FROM mesures_hc;" \
  -c "SELECT 'referentiel : ' || (SELECT count(*) FROM sites) || '/' ||
      (SELECT count(*) FROM actifs) || '/' || (SELECT count(*) FROM signaux) || '/' ||
      (SELECT count(*) FROM affectation_capteur);"
"${PSQL_L[@]}" -d mistral_legacy -At -c "SELECT 'legacy : ' || count(*) FROM mesures;"
echo "parcours amont terminé."
