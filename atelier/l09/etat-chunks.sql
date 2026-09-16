-- État des chunks par hypertable : bornes, bascule columnstore.
SELECT hypertable_name,
       chunk_name,
       range_start::date AS debut,
       range_end::date   AS fin,
       is_compressed     AS columnstore
FROM   timescaledb_information.chunks
WHERE  hypertable_name IN ('mesures', 'evenements', 'mesures_hc')
ORDER  BY hypertable_name, range_start;

SELECT hypertable_name, count(*) AS chunks,
       count(*) FILTER (WHERE is_compressed)     AS en_columnstore,
       count(*) FILTER (WHERE NOT is_compressed) AS en_rowstore
FROM   timescaledb_information.chunks
WHERE  hypertable_name IN ('mesures', 'evenements', 'mesures_hc')
GROUP  BY 1 ORDER BY 1;
