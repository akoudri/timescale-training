-- T3 — passer par un job : l'action de contrôle qualité de M11 s'exécute
-- sous le rôle qui l'a créée, et consigne ce qu'elle voit.
SELECT job_id FROM timescaledb_information.jobs
WHERE  proc_name = 'controle_qualite' \gset
CALL run_job(:job_id);

SET mistral.site = 2;
SET ROLE mistral_lecture;
SELECT count(DISTINCT series_id) AS series_consignees,
       count(*)                  AS lignes
FROM   alertes_qualite;
RESET ROLE;
-- Réussie si le lecteur du site 2 lit, via la table d'alertes, des séries
-- d'autres sites — ou si le simple accès à la table lui est ouvert.
