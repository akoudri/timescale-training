#!/bin/bash
# Vérification du poste avant L01. Affiche « poste conforme » si tout va bien.
set -euo pipefail
cd "$(dirname "$0")"
ko=0
dire() { printf '%-58s %s\n' "$1" "$2"; }

docker compose ps --format '{{.Name}} {{.State}}' | grep -q "timescaledb running" \
  && dire "instance timescaledb" "ok" || { dire "instance timescaledb" "ABSENTE"; ko=1; }
docker compose ps --format '{{.Name}} {{.State}}' | grep -q "legacy running" \
  && dire "instance legacy (PG16)" "ok" || { dire "instance legacy" "ABSENTE"; ko=1; }

lim=$(docker inspect timescaledb --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}' 2>/dev/null || echo "0 0")
[ "$(echo "$lim" | awk '{print $1}')" = "8589934592" ] && [ "$(echo "$lim" | awk '{print $1}')" = "$(echo "$lim" | awk '{print $2}')" ] \
  && dire "épinglage 8 Go, swap désactivé" "ok" || { dire "épinglage mémoire" "NON CONFORME ($lim)"; ko=1; }

for t in mesures mesures_hc sites actifs signaux affectation_capteur evenements meteo; do
  n=$(docker compose exec -T timescaledb psql -U postgres -d mistral -At \
      -c "SELECT count(*) FROM $t" 2>/dev/null || echo "-")
  [ "$n" != "-" ] && dire "table $t" "$n lignes" || { dire "table $t" "ABSENTE"; ko=1; }
done
n=$(docker compose exec -T legacy psql -U postgres -d mistral_legacy -At \
    -c "SELECT count(*) FROM mesures" 2>/dev/null || echo "-")
[ "$n" != "-" ] && dire "legacy.mesures" "$n lignes" || { dire "legacy.mesures" "ABSENTE"; ko=1; }

libre=$(df --output=avail -BG "$(pwd)" | tail -1 | tr -dc 0-9)
[ "$libre" -ge 60 ] && dire "espace disque libre (${libre} Go)" "ok" \
  || { dire "espace disque libre (${libre} Go < 60)" "INSUFFISANT"; ko=1; }

[ $ko -eq 0 ] && echo "poste conforme" || { echo "poste NON conforme"; exit 1; }
