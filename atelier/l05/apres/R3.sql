-- R3 après. Nœud responsable : time_bucket_gapfill génère les seaux
-- manquants — l'axe des temps redevient régulier.
--
-- JUSTIFICATION (exigée par le critère) : les valeurs restent à NULL.
-- Pour une vitesse de vent — grandeur volatile, décorrélée en quelques
-- minutes — LOCF et interpolation FABRIQUENT une donnée fausse : un trou
-- de 2 h comblé par la dernière valeur affiche un vent constant qui n'a
-- jamais existé. Le tableau du bloc 6.2 classe la vitesse de vent
-- « ne pas combler » : le trou est l'information, le tableau de bord doit
-- afficher une interruption, pas une droite fictive.
SELECT time_bucket_gapfill(INTERVAL '1 hour', ts,
                           :'debut'::timestamptz, :'fin'::timestamptz) AS heure,
       avg(valeur) AS vitesse
FROM   mesures
WHERE  series_id = :serie_vent
  AND  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
