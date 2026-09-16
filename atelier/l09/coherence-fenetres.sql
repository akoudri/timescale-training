-- Le contrôle qui empêche l'agrégat vide du bloc 10.2 :
-- rétention STRICTEMENT au-delà de la portée du rafraîchissement.
-- Si la rétention coupe à 30 j et qu'un rafraîchissement remonte à 35 j,
-- chaque passage matérialise du vide et écrase des valeurs justes.
WITH fenetres AS (
    SELECT 'rafraîchissement 1min' AS quoi,
           (config->>'start_offset')::interval AS portee
    FROM   timescaledb_information.jobs
    WHERE  proc_name = 'policy_refresh_continuous_aggregate'
    UNION ALL
    SELECT 'bascule columnstore (atelier)', interval '2 days'
    UNION ALL
    SELECT 'rétention (atelier)', interval '30 days'
)
SELECT quoi, portee FROM fenetres ORDER BY portee;

SELECT CASE
  WHEN interval '30 days' > (
       SELECT max((config->>'start_offset')::interval)
       FROM timescaledb_information.jobs
       WHERE proc_name = 'policy_refresh_continuous_aggregate')
  THEN 'COHÉRENT : la rétention (30 j) dépasse la plus grande portée de rafraîchissement'
  ELSE 'INCOHÉRENT : un rafraîchissement remonte au-delà de la rétention'
END AS verdict;
