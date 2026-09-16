-- Famille ACTIVITÉ : ce que l'instance fait à l'instant t.
SELECT count(*) AS workers_timescaledb
FROM   pg_stat_activity WHERE application_name LIKE 'TimescaleDB%';

SELECT wait_event_type, wait_event, count(*)
FROM   pg_stat_activity
WHERE  state = 'active' AND pid <> pg_backend_pid()
GROUP  BY 1, 2 ORDER BY 3 DESC;

SELECT calls, round(total_exec_time::numeric, 0) AS ms_total,
       round(mean_exec_time::numeric, 1) AS ms_moyen, left(query, 70) AS requete
FROM   pg_stat_statements ORDER BY total_exec_time DESC LIMIT 8;
