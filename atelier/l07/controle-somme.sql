-- Contrôle de cohérence aux trois niveaux de la pyramide (et au brut), sur
-- une journée pleine : J-3 du jeu au sens du jour civil de Paris — celle
-- visée par l'injection tardive. Le niveau jour n'a de seau que pour des
-- jours de Paris ; les seaux heure (UTC) s'alignent sur ses frontières.
-- Les quatre COMPTES doivent être identiques (entiers) ; les sommes
-- flottantes ne coïncident qu'à ~1e-13 relatif près (ordre de sommation).
-- Un écart avant politiques signale une erreur d'agrégabilité, un écart
-- après signale un défaut de rafraîchissement.
SELECT (date_trunc('day', max(ts) AT TIME ZONE 'Europe/Paris') - interval '3 days')
       AT TIME ZONE 'Europe/Paris' AS j3
FROM   mesures \gset

SELECT 'brut'   AS niveau, sum(valeur)  AS somme, count(*)    AS points
FROM   mesures      WHERE ts   >= :'j3' AND ts   < :'j3'::timestamptz + interval '1 day'
UNION ALL
SELECT '1min', sum(somme), sum(points)
FROM   mistral_1min WHERE seau >= :'j3' AND seau < :'j3'::timestamptz + interval '1 day'
UNION ALL
SELECT '1h',   sum(somme), sum(points)
FROM   mistral_1h   WHERE seau >= :'j3' AND seau < :'j3'::timestamptz + interval '1 day'
UNION ALL
SELECT '1j',   sum(somme), sum(points)
FROM   mistral_1j   WHERE seau >= :'j3' AND seau < :'j3'::timestamptz + interval '1 day';
