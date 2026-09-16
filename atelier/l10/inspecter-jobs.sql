-- L10 — les deux requêtes de supervision du bloc 11.1.
-- La discrimination se fait sur scheduled / next_start / last_successful_finish,
-- pas sur last_run_status : un job suspendu n'échoue pas, il disparaît.

-- 1. l'historique d'exécution, échecs en tête
SELECT j.job_id, j.proc_name, j.scheduled, j.next_start,
       s.last_run_started_at, s.last_successful_finish,
       s.last_run_status, s.total_runs, s.total_failures
FROM   timescaledb_information.jobs j
LEFT   JOIN timescaledb_information.job_stats s USING (job_id)
ORDER  BY s.total_failures DESC NULLS LAST, j.job_id;

-- 2. le détail des erreurs, quand il y en a
--    (seules les exécutions lancées par l'ORDONNANCEUR y sont écrites :
--     un CALL run_job() en session renvoie l'erreur au client, rien ici)
SELECT job_id, start_time, finish_time, left(err_message, 120) AS erreur
FROM   timescaledb_information.job_errors
ORDER  BY start_time DESC LIMIT 20;
