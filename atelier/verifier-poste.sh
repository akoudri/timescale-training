#!/bin/bash
# Vérification du poste avant L01 (fiche AMONT, étape 6).
# Affiche « poste conforme » si tout va bien.
# Les lignes « à faire en L01 » sont des avertissements, pas des échecs.
set -uo pipefail
cd "$(dirname "$0")"
ko=0
dire() { printf '%-58s %s\n' "$1" "$2"; }

# 1. Docker accessible sans sudo (groupe docker, ou Docker Desktop)
if [ "$(id -u)" -eq 0 ]; then
  dire "exécution" "EN ROOT — relancer sans sudo (fiche AMONT, étape 1)"; ko=1
fi
if docker info >/dev/null 2>&1; then
  dire "docker sans sudo" "ok"
else
  dire "docker sans sudo" "REFUSÉ — groupe docker manquant ou session non rouverte (fiche AMONT, étape 1)"
  echo "poste NON conforme"; exit 1
fi

# 2. Répertoires de données à l'uid courant
for d in pgdata pgdata-legacy archives; do
  if [ ! -d "$d" ]; then
    dire "répertoire $d" "ABSENT — lancer ./amont/restaurer.sh"; ko=1
  elif [ "$(stat -c %u "$d")" != "$(id -u)" ]; then
    dire "répertoire $d" "PROPRIÉTÉ DE L'UID $(stat -c %u "$d") — voir les pièges de la fiche AMONT"; ko=1
  else
    dire "répertoire $d" "ok"
  fi
done

# 3. Outil du générateur
if command -v uv >/dev/null 2>&1; then
  dire "uv ($(uv --version 2>/dev/null | awk '{print $2}'))" "ok"
else
  dire "uv" "absent — nécessaire seulement pour (re)générer les jeux (fiche AMONT, étape 2)"
fi

# 4. Instances
docker compose ps --format '{{.Name}} {{.State}}' | grep -q "timescaledb running" \
  && dire "instance timescaledb" "ok" || { dire "instance timescaledb" "ABSENTE"; ko=1; }
docker compose ps --format '{{.Name}} {{.State}}' | grep -q "legacy running" \
  && dire "instance legacy (PG16)" "ok" || { dire "instance legacy" "ABSENTE"; ko=1; }

# 5. Épinglage mémoire
lim=$(docker inspect timescaledb --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}' 2>/dev/null || echo "0 0")
[ "$(echo "$lim" | awk '{print $1}')" = "8589934592" ] && [ "$(echo "$lim" | awk '{print $1}')" = "$(echo "$lim" | awk '{print $2}')" ] \
  && dire "épinglage 8 Go, swap désactivé" "ok" || { dire "épinglage mémoire" "NON CONFORME ($lim)"; ko=1; }

# 6. Tables restaurées
for t in mesures mesures_hc sites actifs signaux affectation_capteur evenements meteo; do
  n=$(docker compose exec -T timescaledb psql -U postgres -d mistral -At \
      -c "SELECT count(*) FROM $t" 2>/dev/null || echo "-")
  [ "$n" != "-" ] && dire "table $t" "$n lignes" || { dire "table $t" "ABSENTE"; ko=1; }
done
n=$(docker compose exec -T legacy psql -U postgres -d mistral_legacy -At \
    -c "SELECT count(*) FROM mesures" 2>/dev/null || echo "-")
[ "$n" != "-" ] && dire "legacy.mesures" "$n lignes" || { dire "legacy.mesures" "ABSENTE"; ko=1; }

# 7. Extensions dans mistral : timescaledb par l'amont, les deux autres par L01 étape 2
ext=$(docker compose exec -T timescaledb psql -U postgres -d mistral -At \
      -c "SELECT string_agg(extname, ',') FROM pg_extension" 2>/dev/null || echo "")
for e in timescaledb timescaledb_toolkit pg_stat_statements; do
  if echo ",$ext," | grep -q ",$e,"; then
    dire "extension $e" "ok"
  elif [ "$e" = "timescaledb" ]; then
    dire "extension $e" "ABSENTE — lancer ./amont/restaurer.sh"; ko=1
  else
    dire "extension $e" "à faire en L01 (étape 2)"
  fi
done

# 8. Espace disque
libre=$(df --output=avail -BG "$(pwd)" | tail -1 | tr -dc 0-9)
[ "$libre" -ge 60 ] && dire "espace disque libre (${libre} Go)" "ok" \
  || { dire "espace disque libre (${libre} Go < 60)" "INSUFFISANT"; ko=1; }

[ $ko -eq 0 ] && echo "poste conforme" || { echo "poste NON conforme"; exit 1; }
