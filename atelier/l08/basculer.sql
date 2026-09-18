-- Bascule en columnstore de tous les chunks de la table :table.
-- (ici tous les chunks sont pleins par construction — deux jours UTC
--  entiers sur des chunks journaliers)
SELECT compress_chunk(c) FROM show_chunks(:'table') AS c;
-- hypertable_compression_stats() ne retourne pas le nom de la table :
-- on le rappelle depuis la variable psql.
SELECT :'table' AS table_,
       pg_size_pretty(before_compression_total_bytes) AS avant,
       pg_size_pretty(after_compression_total_bytes)  AS apres,
       round(before_compression_total_bytes::numeric
             / after_compression_total_bytes, 1)      AS ratio
FROM   hypertable_compression_stats(:'table');
