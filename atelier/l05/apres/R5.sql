-- R5 après. Nœud responsable du gain : PAS la syntaxe — l'index
-- (series_id, ts DESC). DISTINCT ON sans lui balaye et trie toute la
-- table (mesuré : gain quasi nul à l'étape 1) ; avec lui, le plan devient
-- un parcours d'index par saut de série : quelques centaines de lectures.
SELECT DISTINCT ON (series_id) series_id, ts, valeur
FROM   mesures
ORDER  BY series_id, ts DESC;
