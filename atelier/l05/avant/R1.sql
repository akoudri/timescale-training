-- R1 avant — production horaire par site, sur trente jours (telle qu'elle tourne en production).
SELECT a.site_id,
       date_trunc('hour', m.ts) AS heure,
       sum(m.valeur)            AS production
FROM   mesures m, affectation_capteur af, actifs a
WHERE  af.series_id = m.series_id
  AND  a.machine_id = af.machine_id
  AND  m.ts > (SELECT max(ts) FROM mesures) - interval '30 days'
GROUP  BY 1, 2;
