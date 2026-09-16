-- Q5 — fonction appliquée à la colonne de temps
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT avg(valeur) FROM mesures_1j
WHERE  date_trunc('day', ts) = '2026-10-01T00:00:00+02';
