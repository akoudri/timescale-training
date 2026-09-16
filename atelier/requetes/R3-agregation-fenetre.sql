-- R3 : agrégation par série sur la fenêtre de référence (jours 1 à 5).
-- La ligne de base se mesure sur `mesures-avant` (5 jours, table ordinaire) ;
-- borner l'hypertable aux mêmes jours garde le rapport avant/après honnête.
SELECT series_id, avg(valeur), count(*)
FROM   {{table}}
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY series_id;
