-- Q3 — requête préparée : plan générique, l'élimination se joue à l'exécution
PREPARE p(timestamptz, timestamptz) AS
SELECT avg(valeur) FROM mesures_1j WHERE ts >= $1 AND ts < $2;
-- forcer le plan générique (comportement d'un pool applicatif)
SET plan_cache_mode = force_generic_plan;
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
EXECUTE p('2026-10-01T00:00:00+02', '2026-10-04T00:00:00+02');
DEALLOCATE p;
RESET plan_cache_mode;
