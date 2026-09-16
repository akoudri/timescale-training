#!/bin/bash
# Maintient un flux d'écriture sur la source pendant la migration : la
# copie initiale et le rattrapage doivent se faire production ouverte.
# Horodatages : continuité après le max(ts) de la source (jeu daté).
set -euo pipefail
cd "$(dirname "$0")/.."
DEBIT=2000
while [ $# -gt 0 ]; do case "$1" in
  --debit) DEBIT="$2"; shift 2;;
  *) shift;;
esac; done
LOT=$((DEBIT / 4))

echo "flux d'écriture : ${DEBIT} lignes/s (lots de ${LOT}, 4/s) — Ctrl-C pour arrêter"
while true; do
  docker compose exec -T legacy psql -U postgres -d mistral_legacy -q -c "
    INSERT INTO mesures (ts, series_id, valeur, qualite)
    SELECT (SELECT max(ts) FROM mesures) + make_interval(secs => 0.001 * g),
           1 + (g % 400), random() * 1000, 0
    FROM generate_series(1, ${LOT}) g;" 2>/dev/null || true
  sleep 0.25
done
