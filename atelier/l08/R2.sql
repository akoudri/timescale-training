-- R2 — fenêtre d'un jour, filtrée sur une série : sur cmp_serie le
-- prédicat series_id élimine des lots entiers sans décompression ;
-- sur cmp_aucun il n'élimine rien.
SELECT avg(valeur), count(*) FROM {{table}}
WHERE  series_id = 137
  AND  ts >= '2026-09-25T00:00:00Z' AND ts < '2026-09-26T00:00:00Z';
