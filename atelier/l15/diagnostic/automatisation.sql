-- Famille AUTOMATISATION : ce que les jobs font — ou ne font plus.
-- La discrimination se fait sur scheduled et next_start, PAS sur
-- last_run_status : un job suspendu n'échoue pas, il disparaît.
SELECT j.job_id, j.proc_name, j.scheduled, j.next_start,
       s.last_run_status, s.last_successful_finish, s.total_failures
FROM   timescaledb_information.jobs j
LEFT   JOIN timescaledb_information.job_stats s USING (job_id)
ORDER  BY j.job_id;

SELECT job_id, start_time, left(err_message, 60) AS erreur
FROM   timescaledb_information.job_errors
ORDER  BY start_time DESC LIMIT 5;

-- fraîcheur des agrégats : dernier seau matérialisé vs dernier point brut
SELECT 'mistral_1min' AS agregat, max(seau) AS dernier_seau FROM mistral_1min
UNION ALL SELECT 'mistral_1h', max(seau) FROM mistral_1h
UNION ALL SELECT 'brut (réf.)', max(ts) FROM mesures;
