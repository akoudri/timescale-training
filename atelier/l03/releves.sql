-- Relevés structurels par table de comparaison : nombre de chunks, volume,
-- temps de planification (ligne « Planning Time » de l'EXPLAIN).
SELECT :'table' AS table_,
       (SELECT count(*) FROM timescaledb_information.chunks
        WHERE hypertable_name = :'table')          AS chunks,
       pg_size_pretty(hypertable_size(:'table'))    AS volume;
EXPLAIN (SUMMARY)
SELECT avg(valeur) FROM :"table"
WHERE  ts >= :'fen3' AND ts < :'fin';
