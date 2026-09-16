-- R5 avant — dernière valeur de chaque capteur (motif du bloc 6.3)
SELECT m.series_id, m.ts, m.valeur
FROM   mesures m
JOIN  ( SELECT series_id, max(ts) AS ts
        FROM   mesures GROUP BY series_id ) d
  ON   d.series_id = m.series_id AND d.ts = m.ts;
