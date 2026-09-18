-- R2 après. Nœud responsable : aucun — la requête n'était pas lente,
-- elle était FAUSSE. time_bucket sans fuseau découpe des jours UTC :
-- les 25 et 26 octobre (jour de 25 h), l'énergie est imputée au mauvais
-- jour. Le total annuel reste juste, ce qui rend l'erreur indétectable
-- par les contrôles de somme.
SELECT time_bucket(INTERVAL '1 day', ts, 'Europe/Paris') AS jour,
       sum(energie_kwh)                                  AS energie
FROM   mesures_production
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
