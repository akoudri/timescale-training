-- R3 avant — courbe de vent à pas régulier : les heures sans mesure
-- n'apparaissent pas, l'axe des temps se contracte à l'affichage.
SELECT date_trunc('hour', ts) AS heure, avg(valeur) AS vitesse
FROM   mesures
WHERE  series_id = :serie_vent
  AND  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
