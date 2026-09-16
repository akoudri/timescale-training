-- R1 : dernière valeur de chaque série (motif le plus fréquent en production)
SELECT DISTINCT ON (series_id) series_id, ts, valeur
FROM   {{table}}
ORDER  BY series_id, ts DESC;
