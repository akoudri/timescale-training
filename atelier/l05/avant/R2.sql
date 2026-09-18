-- R2 avant — énergie journalière facturable. Rapide. Fausse.
-- (le découpage journalier est fait en UTC : les jours de 23 h et 25 h
--  du changement d'heure sont mal découpés, et rien ne le signale)
SELECT time_bucket(INTERVAL '1 day', ts) AS jour,
       sum(puissance_kw) / 360.0         AS energie_kwh  -- énergie dérivée de la puissance (pas 10 s) ; le compteur cumulatif se traite en M07 (counter_agg)
FROM   mesures_production
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
