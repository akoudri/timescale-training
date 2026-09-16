-- Q2 — prédicat EXTRACT, avec bornes littérales
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF)
SELECT avg(valeur) FROM mesures_1j
WHERE  EXTRACT(hour FROM ts) = 14
  AND  ts >= '2026-10-01T00:00:00+02' AND ts < '2026-10-04T00:00:00+02';
