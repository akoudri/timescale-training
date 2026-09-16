-- L03 — tables de comparaison.
--
-- 1. `mesures_ord` : copie ORDINAIRE éphémère des 45 jours complets.
--    La ligne de base de M02 (5 jours) ne peut pas montrer le gain du
--    partitionnement : une table qui ne contient que la fenêtre interrogée
--    n'a rien à exclure. La dette de M01 se mesure contre la table
--    ordinaire à l'échelle réelle — créée ici, supprimée en fin d'atelier.
-- 2. `mesures_1j`, `mesures_7j`, `mesures_30j` : le même échantillon de
--    cinquante séries sur la fenêtre complète, à trois intervalles de
--    chunk. Chargées sans index secondaire, l'index ensuite.
\timing on

CREATE TABLE mesures_ord (LIKE mesures);
INSERT INTO mesures_ord SELECT * FROM mesures;

CREATE TABLE mesures_1j  (LIKE mesures);
CREATE TABLE mesures_7j  (LIKE mesures);
CREATE TABLE mesures_30j (LIKE mesures);
SELECT create_hypertable('mesures_1j',  by_range('ts', INTERVAL '1 day'),
                         create_default_indexes => false);
SELECT create_hypertable('mesures_7j',  by_range('ts', INTERVAL '7 days'),
                         create_default_indexes => false);
SELECT create_hypertable('mesures_30j', by_range('ts', INTERVAL '30 days'),
                         create_default_indexes => false);

INSERT INTO mesures_1j  SELECT * FROM mesures WHERE series_id <= 50;
INSERT INTO mesures_7j  SELECT * FROM mesures WHERE series_id <= 50;
INSERT INTO mesures_30j SELECT * FROM mesures WHERE series_id <= 50;

CREATE INDEX ON mesures_1j  (ts DESC);
CREATE INDEX ON mesures_7j  (ts DESC);
CREATE INDEX ON mesures_30j (ts DESC);

SELECT 'mesures_ord' AS t, count(*) FROM mesures_ord
UNION ALL SELECT 'mesures_1j',  count(*) FROM mesures_1j
UNION ALL SELECT 'mesures_7j',  count(*) FROM mesures_7j
UNION ALL SELECT 'mesures_30j', count(*) FROM mesures_30j;
