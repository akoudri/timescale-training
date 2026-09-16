-- Q4 — borne issue d'une sous-requête
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT avg(valeur) FROM mesures_1j
WHERE  ts >= (SELECT max(ts) - interval '3 days' FROM mesures_1j);
