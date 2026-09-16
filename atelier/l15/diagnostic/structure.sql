-- Famille STRUCTURE : ce que la base est censée être.
SELECT hypertable_name, num_dimensions FROM timescaledb_information.hypertables ORDER BY 1;
SELECT hypertable_name, count(*) AS chunks,
       count(*) FILTER (WHERE is_compressed) AS columnstore
FROM   timescaledb_information.chunks GROUP BY 1 ORDER BY 1;
-- inventaire des index de l'hypertable principale, à comparer à schema.sql
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'mesures' ORDER BY 1;
