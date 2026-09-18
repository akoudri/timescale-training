-- Le contrôle qui empêche l'agrégat vide du bloc 10.2 :
-- rétention STRICTEMENT au-delà de la portée du rafraîchissement.
-- Si la rétention coupe à 30 j et qu'un rafraîchissement remonte à 35 j,
-- chaque passage matérialise du vide et écrase des valeurs justes.
WITH fenetres AS (
    SELECT 'rafraîchissement ' || ca.view_name AS quoi,
           (j.config->>'start_offset')::interval AS portee
    FROM   timescaledb_information.jobs j
    JOIN   timescaledb_information.continuous_aggregates ca
      ON   ca.materialization_hypertable_name =
           '_materialized_hypertable_' || (j.config->>'mat_hypertable_id')
    WHERE  j.proc_name = 'policy_refresh_continuous_aggregate'
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

-- Les DEUX HORLOGES : la zone purgée (bornée sur le jeu) ne doit pas être
-- recouverte par les fenêtres de rafraîchissement (relatives à now()).
-- Sinon chaque passage matérialise du vide sur [min(seau), min(ts)[ — la
-- zone où l'agrégat a encore des valeurs mais le brut n'en a plus.
WITH p AS (
  SELECT max((config->>'start_offset')::interval) AS portee,
         min((config->>'end_offset')::interval)   AS marge
  FROM   timescaledb_information.jobs
  WHERE  proc_name = 'policy_refresh_continuous_aggregate'
), z AS (
  SELECT (SELECT min(seau) FROM mistral_1h) AS debut_agregat,
         (SELECT min(ts)   FROM mesures)    AS debut_brut
)
SELECT CASE
  WHEN debut_agregat IS NULL OR debut_agregat >= debut_brut
    THEN 'DEUX HORLOGES : sans objet, aucune zone purgée sous les agrégats'
  WHEN now() - marge <= debut_agregat OR now() - portee >= debut_brut
    THEN 'COHÉRENT (deux horloges) : la fenêtre de rafraîchissement [' ||
         (now() - portee)::timestamp(0) || ', ' || (now() - marge)::timestamp(0) ||
         '] ne recouvre pas la zone purgée [' || debut_agregat::date || ', ' || debut_brut::date || '['
  ELSE 'INCOHÉRENT (deux horloges) : la fenêtre de rafraîchissement [' ||
       (now() - portee)::timestamp(0) || ', ' || (now() - marge)::timestamp(0) ||
       '] recouvre la zone purgée [' || debut_agregat::date || ', ' || debut_brut::date ||
       '[ — les politiques y matérialisent du vide à chaque passage'
END AS verdict_deux_horloges
FROM p, z;
