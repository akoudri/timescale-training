-- L11 étape 6 — après la bascule, jamais pendant : activer la compression
-- et les politiques sur la cible.
ALTER TABLE mesures SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'series_id',
  timescaledb.compress_orderby   = 'ts DESC');
SELECT add_compression_policy('mesures', INTERVAL '7 days', if_not_exists => true);
SELECT add_retention_policy('mesures', INTERVAL '90 days', if_not_exists => true);

SELECT j.job_id, j.proc_name, j.scheduled, j.next_start, s.last_run_status
FROM   timescaledb_information.jobs j
LEFT   JOIN timescaledb_information.job_stats s USING (job_id)
ORDER  BY j.job_id;
