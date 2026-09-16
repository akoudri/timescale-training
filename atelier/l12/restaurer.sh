#!/bin/bash
# L12 — restauration à un instant donné :
#   ./l12/restaurer.sh --instant "2026-08-31 18:55:00+00"
# 1. arrête l'instance   2. remplace PGDATA par la sauvegarde de base
# 3. positionne cible et rejeu   4. redémarre et laisse rejouer
# 5. attend la fin du rejeu avant d'ouvrir en écriture
set -euo pipefail
cd "$(dirname "$0")/.."
INSTANT=""
while [ $# -gt 0 ]; do case "$1" in
  --instant) INSTANT="$2"; shift 2;;
  *) shift;;
esac; done
[ -n "$INSTANT" ] || { echo "--instant requis"; exit 2; }

echo "== 1. arrêt de l'instance =="
docker compose stop timescaledb

echo "== 2. remplacement du répertoire de données =="
rm -rf pgdata/data.incident
mv pgdata/data pgdata/data.incident
cp -a archives/base pgdata/data
chmod 700 pgdata/data

echo "== 3. cible de rejeu : ${INSTANT} =="
rm -f pgdata/data/standby.signal
touch pgdata/data/recovery.signal
cat >> pgdata/data/postgresql.auto.conf <<CONF
restore_command = 'cp /archives/wal/%f %p'
recovery_target_time = '${INSTANT}'
recovery_target_action = 'promote'
CONF

echo "== 4. redémarrage et rejeu =="
docker compose start timescaledb
for i in $(seq 1 180); do
  docker compose exec -T timescaledb pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 2
done

echo "== 5. attendre la fin du rejeu (sortie de recovery) =="
for i in $(seq 1 180); do
  encore=$(docker compose exec -T timescaledb psql -U postgres -At \
           -c "SELECT pg_is_in_recovery();" 2>/dev/null || echo t)
  [ "$encore" = "f" ] && { echo "instance promue, ouverte en écriture"; exit 0; }
  sleep 2
done
echo "le rejeu ne se termine pas — vérifier les journaux" >&2
exit 1
