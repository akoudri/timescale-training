#!/bin/bash
# Simule l'arrêt de capteurs : supprime leurs derniers points.
# Rejouable et déterministe : « depuis » se mesure au dernier point du
# parc (max(ts)), jamais à l'horloge murale.
set -euo pipefail
cd "$(dirname "$0")/.."
SERIES="137,208,451"; DEPUIS="3 hours"
while [ $# -gt 0 ]; do case "$1" in
  --series) SERIES="$2"; shift 2;;
  --depuis) DEPUIS="$2"; shift 2;;
  *) shift;;
esac; done

docker compose exec -T timescaledb psql -U postgres -d mistral -v ON_ERROR_STOP=1 <<SQL
-- borne en LITTÉRAL (via \gset) : une borne en sous-requête n'est connue
-- qu'à l'exécution, et le DELETE marquerait alors comme candidats à la
-- décompression tous les lots des séries visées dans les chunks basculés
-- (leçon de L03/Q4, version DML — vérifié : limite DML dépassée)
SELECT max(ts) - interval '${DEPUIS}' AS coupure FROM mesures \gset
DELETE FROM mesures
WHERE  series_id IN (${SERIES})
  AND  ts > :'coupure';
SELECT 'capteurs coupés : ${SERIES} (depuis ${DEPUIS} avant la fin du jeu)';
SQL
