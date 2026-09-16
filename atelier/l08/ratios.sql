-- L08 — ratio et volumes, chunk par chunk, pour la table :table
--   psql -v table=cmp_serie -f l08/ratios.sql   (ou \set table cmp_serie puis \i)
-- Ne comparer que des chunks PLEINS : un chunk partiel donne un ratio flatteur.
SELECT chunk_name,
       pg_size_pretty(before_compression_total_bytes) AS avant,
       pg_size_pretty(after_compression_total_bytes)  AS apres,
       round(before_compression_total_bytes::numeric
             / nullif(after_compression_total_bytes, 0), 1) AS ratio
FROM   chunk_compression_stats(:'table')
ORDER  BY chunk_name;

SELECT :'table' AS table_,
       pg_size_pretty(sum(before_compression_total_bytes)) AS avant,
       pg_size_pretty(sum(after_compression_total_bytes))  AS apres,
       round(sum(before_compression_total_bytes)::numeric
             / nullif(sum(after_compression_total_bytes), 0), 1) AS ratio
FROM   chunk_compression_stats(:'table');
