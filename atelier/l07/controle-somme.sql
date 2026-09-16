-- Contrôle de cohérence aux trois niveaux, sur une journée pleine (J-3 du
-- jeu — celle visée par l'injection tardive). Les trois sommes et les
-- trois comptes doivent être identiques : un écart avant politiques
-- signale une erreur d'agrégabilité, un écart après signale un défaut de
-- rafraîchissement.
SELECT date_trunc('day', max(ts)) - interval '3 days' AS j3
FROM   mesures \gset

SELECT 'brut'   AS niveau, sum(valeur)  AS somme, count(*)    AS points
FROM   mesures     WHERE ts   >= :'j3' AND ts   < :'j3'::timestamptz + interval '1 day'
UNION ALL
SELECT '1min', sum(somme), sum(points)
FROM   mistral_1min WHERE seau >= :'j3' AND seau < :'j3'::timestamptz + interval '1 day'
UNION ALL
SELECT '1h',   sum(somme), sum(points)
FROM   mistral_1h   WHERE seau >= :'j3' AND seau < :'j3'::timestamptz + interval '1 day';
