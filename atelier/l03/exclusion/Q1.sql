-- Q1 — bornes littérales
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT avg(valeur) FROM mesures_1j
WHERE  ts >= '2026-10-01T00:00:00+02' AND ts < '2026-10-04T00:00:00+02';
