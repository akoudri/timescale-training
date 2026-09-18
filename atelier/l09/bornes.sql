-- L09 — bornes d'atelier de la chaîne (bascule 2 j, rétention 30 j), avec
-- le garde-fou des DEUX HORLOGES.
--
-- Le jeu est daté : la bascule et la rétention d'atelier se déclenchent à
-- borne EXPLICITE, calculée depuis max(ts). Mais les politiques de
-- rafraîchissement des agrégats (M08) sont relatives à now(), et rien ne
-- les en empêche. Si la date de la session tombe DANS la fenêtre du jeu et
-- que la purge emporte les chunks où se trouve now(), chaque passage de
-- ces politiques matérialise du vide sur la zone purgée et efface des
-- valeurs justes — le bloc 10.2, sans erreur ni avertissement.
-- La borne de rétention est donc plafonnée, quand now() est dans la
-- fenêtre, à now() − (plus grande portée de rafraîchissement) − 1 jour.
-- Si la session est POSTÉRIEURE à la fenêtre, aucune borne ne protège :
-- les politiques de bascule (7 j) et de rétention (30 j) agissent pour de
-- vrai — il faut régénérer le jeu avec une fenêtre future (fiche AMONT).
WITH portee AS (
  SELECT coalesce(max((config->>'start_offset')::interval), INTERVAL '3 days') AS maxi
  FROM   timescaledb_information.jobs
  WHERE  proc_name = 'policy_refresh_continuous_aggregate'
)
SELECT max(ts) - INTERVAL '2 days'                                  AS borne_bascule,
       CASE WHEN now() > min(ts)
            THEN least(max(ts) - INTERVAL '30 days',
                       now() - (SELECT maxi FROM portee) - INTERVAL '1 day')
            ELSE max(ts) - INTERVAL '30 days' END                     AS borne_retention,
       (now() BETWEEN min(ts) AND max(ts))                            AS session_dans_la_fenetre,
       (now() > max(ts))                                              AS session_apres_la_fenetre
FROM   mesures \gset

\echo bornes atelier : bascule < :borne_bascule · rétention < :borne_retention
\if :session_dans_la_fenetre
\echo ATTENTION : la session tombe dans la fenêtre du jeu — borne de rétention plafonnée pour ne pas croiser les fenêtres de rafraîchissement (voir les pièges, « les deux horloges »)
\endif
\if :session_apres_la_fenetre
\echo ATTENTION : la session est postérieure à la fenêtre du jeu — les politiques relatives à now() agiront réellement ; régénérer le jeu avec une fenêtre future (fiche AMONT, étape 4)
\endif
