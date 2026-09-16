-- Famille VOLUME : ce que la base pèse et compresse.
SELECT pg_size_pretty(hypertable_size('mesures')) AS mesures;
SELECT round(before_compression_total_bytes::numeric
             / nullif(after_compression_total_bytes, 0), 1) AS ratio
FROM   hypertable_compression_stats('mesures');
SELECT pg_size_pretty(pg_database_size(current_database())) AS base;
