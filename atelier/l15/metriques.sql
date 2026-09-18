-- L15 — les huit métriques du tableau de bord (bloc 15.3).
-- Chacune est une requête autonome, exécutable sous le rôle de
-- supervision (GRANT SELECT sur les vues d'information + référentiel).

-- M1 · débit d'ingestion (points/min sur les 15 dernières minutes du flux)
SELECT count(*) / 15.0 AS points_par_minute
FROM   mesures WHERE ts >= (SELECT max(ts) - interval '15 minutes' FROM mesures);

-- M2 · ancienneté du dernier point, par flux (le pas attendu est celui du
--      catalogue : mesures 10 s, météo 1 h — le seuil de A3 est RELATIF)
SELECT g.famille, max(m.ts) AS dernier_point,
       (SELECT max(ts) FROM mesures) - max(m.ts) AS anciennete
FROM   mesures m
JOIN   affectation_capteur af ON af.series_id = m.series_id
JOIN   signaux g ON g.signal_id = af.signal_id
WHERE  m.ts >= (SELECT max(ts) - interval '1 hour' FROM mesures)
GROUP  BY 1;

-- M3 · retard de rafraîchissement par agrégat (dernier seau vs brut)
SELECT 'mistral_1min' AS agregat,
       (SELECT max(ts) FROM mesures) - max(seau) AS retard FROM mistral_1min
UNION ALL SELECT 'mistral_1h', (SELECT max(ts) FROM mesures) - max(seau) FROM mistral_1h
UNION ALL SELECT 'mistral_1j', (SELECT max(ts) FROM mesures) - max(seau) FROM mistral_1j;

-- M4 · nombre de chunks par hypertable
SELECT hypertable_name, count(*) AS chunks
FROM   timescaledb_information.chunks GROUP BY 1 ORDER BY 2 DESC;

-- M5 · ratio de compression et part de chunks non basculés
SELECT round(before_compression_total_bytes::numeric
             / nullif(after_compression_total_bytes, 0), 1) AS ratio,
       (SELECT count(*) FILTER (WHERE NOT is_compressed)::float / count(*)
        FROM timescaledb_information.chunks
        WHERE hypertable_name = 'mesures') AS part_rowstore
FROM   hypertable_compression_stats('mesures');

-- M6 · état des jobs : échecs, ancienneté du dernier succès
SELECT j.job_id, j.proc_name, j.scheduled, s.total_failures,
       now() - s.last_successful_finish AS depuis_dernier_succes
FROM   timescaledb_information.jobs j
LEFT   JOIN timescaledb_information.job_stats s USING (job_id);

-- M7 · espace disque : taille de la base (valeur instantanée, celle du
--      panneau) et sa tendance, calculée sur l'historique que le job de
--      relevé tient en base (l15/supervision-taille.sql) — une source SQL
--      n'a pas de mémoire, Grafana n'archive rien
SELECT pg_database_size(current_database()) AS octets_base;

SELECT o.octets                                                  AS dernier_releve,
       round(t.pente_par_jour / 1024^2)                          AS mo_par_jour,
       round(((200.0 * 1024^3) - o.octets) / nullif(t.pente_par_jour, 0)) AS jours_restants
FROM  (SELECT octets FROM supervision_taille ORDER BY ts DESC LIMIT 1) o,
      (SELECT regr_slope(octets, extract(epoch FROM ts)) * 86400 AS pente_par_jour
       FROM   supervision_taille WHERE ts >= now() - interval '24 hours') t;

-- M8 · taux de succès du cache
SELECT round(100.0 * blks_hit / nullif(blks_hit + blks_read, 0), 2)
       AS cache_hit_pct
FROM   pg_stat_database WHERE datname = current_database();
