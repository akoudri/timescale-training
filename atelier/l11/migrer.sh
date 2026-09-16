#!/bin/bash
# L11 — copie par plages d'identifiant + delta de rattrapage, production
# ouverte, sans réplication logique (la synchronisation logique vers une
# hypertable écrit dans la table racine sans routage : données invisibles).
#
#   ./l11/migrer.sh            copie initiale par plages, puis un premier delta
#   ./l11/migrer.sh --delta    rejoue un delta depuis la dernière borne
#
# Le delta s'appuie sur l'id monotone de la source (alimenté par sa
# séquence) — l'équivalent legacy de l'horodatage d'ingestion de M05.
# La dernière borne copiée est mémorisée dans l11/.borne.
set -euo pipefail
cd "$(dirname "$0")/.."
MODE=initial; [ "${1:-}" = "--delta" ] && MODE=delta
BORNE_FICHIER=l11/.borne

SRC=(docker compose exec -T legacy psql -U postgres -d mistral_legacy -At -v ON_ERROR_STOP=1)

copie_plage() { # borne_min_id borne_max_id  (demi-ouvert)
  docker compose exec -T legacy psql -U postgres -d mistral_legacy -q -c \
    "\\copy (SELECT id, ts, series_id, valeur, qualite FROM mesures WHERE id >= $1 AND id < $2) TO STDOUT" \
  | docker compose exec -T -i timescaledb psql -U postgres -d mistral_prod -q -c \
    "\\copy mesures (id, ts, series_id, valeur, qualite) FROM STDIN"
}

delta() {
  local precedent nouveau
  precedent=$(cat "$BORNE_FICHIER")
  nouveau=$("${SRC[@]}" -c "SELECT max(id) FROM mesures;")
  echo "== delta : id [$((precedent + 1)), $((nouveau + 1))) — $((nouveau - precedent)) lignes =="
  copie_plage "$((precedent + 1))" "$((nouveau + 1))"
  echo "$nouveau" > "$BORNE_FICHIER"
  echo "delta ok — le retard restant est ce qui a été écrit pendant ce delta (borne : $nouveau)"
}

if [ "$MODE" = "delta" ]; then
  [ -f "$BORNE_FICHIER" ] || { echo "aucune borne : lancer d'abord la copie initiale" >&2; exit 2; }
  delta; exit 0
fi

echo "== copie initiale par plages (production ouverte) =="
borne=$("${SRC[@]}" -c "SELECT max(id) FROM mesures;")
echo "borne initiale : id <= $borne"
pas=6000000
debut=1
while [ "$debut" -le "$borne" ]; do
  fin=$((debut + pas)); [ $fin -gt $((borne + 1)) ] && fin=$((borne + 1))
  printf 'plage id [%d, %d) … ' "$debut" "$fin"
  copie_plage "$debut" "$fin"
  echo ok
  debut=$fin
done
echo "$borne" > "$BORNE_FICHIER"

echo "== événements =="
docker compose exec -T legacy psql -U postgres -d mistral_legacy -q -c \
  "\\copy (SELECT id, ts, machine_id, type, code, message FROM evenements) TO STDOUT" \
| docker compose exec -T -i timescaledb psql -U postgres -d mistral_prod -q -c \
  "\\copy evenements (id, ts, machine_id, type, code, message) FROM STDIN"

echo "== premier delta (rattrapage pendant que le flux tourne) =="
delta
