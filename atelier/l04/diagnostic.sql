-- Les trois diagnostics du point de rupture.
-- 1. Ce que la base attend :
SELECT wait_event_type, wait_event, count(*)
FROM   pg_stat_activity
WHERE  state = 'active' AND pid <> pg_backend_pid()
GROUP  BY 1, 2 ORDER BY 3 DESC;

-- 2. Ce que consomme le serveur / le client : docker stats --no-stream

-- 3. Ce que fait l'écriture différée :
SELECT * FROM pg_stat_bgwriter;
