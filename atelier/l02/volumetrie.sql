-- Aide au calcul de volume à 3 ans — ÉCHELLE DE PRODUCTION (4 000 signaux
-- à 0,1 Hz), pas l'échelle d'atelier. Chaque hypothèse est explicite.
SELECT pg_column_size(row(now(), 1::integer, 1.0::float8, 0::smallint))
       AS octets_utiles;

WITH hypotheses AS (
    SELECT 4000::numeric               AS signaux,          -- H1
           0.1::numeric                AS hz,               -- H1
           1095::numeric               AS jours,            -- H2 (3 ans)
           27 + 24                     AS octets_ligne,     -- H3 (utile + en-tête)
           30::numeric                 AS octets_index      -- H5 (par entrée (series_id, ts))
)
SELECT round(signaux * hz * 86400)                          AS points_par_jour,
       round(signaux * hz * 86400 * jours / 1e9, 1)        AS points_3ans_milliards,
       pg_size_pretty((signaux * hz * 86400 * jours * octets_ligne)::bigint)
                                                            AS volume_heap,
       pg_size_pretty((signaux * hz * 86400 * jours * octets_index)::bigint)
                                                            AS volume_index
FROM hypotheses;
