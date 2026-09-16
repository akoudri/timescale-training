-- R2 : agrégation horaire sur une fenêtre de trois jours
-- (bornes calculées du jeu par mesure.sh : jours 3 à 5 de la fenêtre,
--  présents à l'identique dans la table de référence et l'hypertable)
SELECT date_trunc('hour', ts) AS heure, avg(valeur)
FROM   {{table}}
WHERE  ts >= :'fen3' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
