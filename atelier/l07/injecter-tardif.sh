#!/bin/bash
# Injecte un lot daté de J-3 (relatif au jeu, jamais à l'horloge murale —
# le comportement doit être identique quel que soit le jour de l'atelier).
set -euo pipefail
cd "$(dirname "$0")/.."
POINTS=100000
while [ $# -gt 0 ]; do case "$1" in
  --points) POINTS="$2"; shift 2;;
  --jour)   shift 2;;   # J-3 par construction
  *) shift;;
esac; done

docker compose exec -T timescaledb psql -U postgres -d mistral -v ON_ERROR_STOP=1 <<SQL
SELECT setseed(0.42);          -- rejouable : même lot à chaque exécution
WITH j3 AS (
  SELECT date_trunc('day', max(ts)) - interval '3 days' AS debut FROM mesures
)
INSERT INTO mesures (ts, series_id, valeur, qualite)
SELECT (SELECT debut FROM j3)
         -- demi-seconde d'offset : jamais en collision avec la grille 10 s
         + make_interval(secs => trunc(random() * 86390)::int + 0.5),
       1 + trunc(random() * 490)::int,
       random() * 100,
       2                       -- substituée : donnée de rattrapage
FROM   generate_series(1, ${POINTS});
SELECT '${POINTS} points injectés sur J-3';
SQL
