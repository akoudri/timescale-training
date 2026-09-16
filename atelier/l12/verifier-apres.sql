-- L12 — vérification post-restauration : les données NE SUFFISENT PAS.
-- 1. les données sont revenues
SELECT count(*) AS lignes, min(ts), max(ts) FROM mesures;

-- 2. les hypertables sont encore des hypertables
SELECT hypertable_name, num_dimensions
FROM   timescaledb_information.hypertables ORDER BY 1;

-- 3. les jobs sont replanifiés, avec une prochaine échéance
SELECT job_id, proc_name, scheduled, next_start
FROM   timescaledb_information.jobs ORDER BY job_id;

-- 4. les agrégats sont cohérents (contrôle de somme de L07)
\i l07/controle-somme.sql
