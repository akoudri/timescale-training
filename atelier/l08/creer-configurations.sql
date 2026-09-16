-- L08 — trois hypertables identiques à chunks journaliers, deux jours
-- pleins de MISTRAL (490 séries, ≈ 8,5 M lignes chacune), alignées sur
-- des chunks UTC entiers : le ratio se mesure sur des chunks PLEINS.
-- machine_id est matérialisé par la jointure datée : c'est le candidat
-- segmentby « de cardinalité bien plus faible » (46 contre 490).
\timing on
DROP TABLE IF EXISTS cmp_serie; DROP TABLE IF EXISTS cmp_machine; DROP TABLE IF EXISTS cmp_aucun;

CREATE TABLE cmp_serie (
    ts         TIMESTAMPTZ NOT NULL,
    series_id  INTEGER NOT NULL,
    machine_id INTEGER NOT NULL,
    valeur     DOUBLE PRECISION NOT NULL,
    qualite    SMALLINT NOT NULL
);
CREATE TABLE cmp_machine (LIKE cmp_serie);
CREATE TABLE cmp_aucun   (LIKE cmp_serie);
SELECT create_hypertable('cmp_serie',   by_range('ts', INTERVAL '1 day'), create_default_indexes => false);
SELECT create_hypertable('cmp_machine', by_range('ts', INTERVAL '1 day'), create_default_indexes => false);
SELECT create_hypertable('cmp_aucun',   by_range('ts', INTERVAL '1 day'), create_default_indexes => false);

-- deux jours UTC pleins, nominaux (avant les arrêts imposés d'octobre)
CREATE TEMP TABLE deux_jours AS
SELECT m.ts, m.series_id, af.machine_id, m.valeur, m.qualite
FROM   mesures m
JOIN   affectation_capteur af
  ON   af.series_id = m.series_id
 AND   m.ts >= af.debut AND (af.fin IS NULL OR m.ts < af.fin)
WHERE  m.ts >= '2026-09-25T00:00:00Z' AND m.ts < '2026-09-27T00:00:00Z';

INSERT INTO cmp_serie   SELECT * FROM deux_jours;
INSERT INTO cmp_machine SELECT * FROM deux_jours;
INSERT INTO cmp_aucun   SELECT * FROM deux_jours;
DROP TABLE deux_jours;

ALTER TABLE cmp_serie SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'series_id',
  timescaledb.compress_orderby   = 'ts DESC');

ALTER TABLE cmp_machine SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'machine_id',
  timescaledb.compress_orderby   = 'ts DESC');

ALTER TABLE cmp_aucun SET (
  timescaledb.compress,
  timescaledb.compress_orderby   = 'ts DESC');

SELECT 'cmp_serie' AS t, count(*), (SELECT count(*) FROM timescaledb_information.chunks WHERE hypertable_name='cmp_serie') AS chunks FROM cmp_serie
UNION ALL SELECT 'cmp_machine', count(*), (SELECT count(*) FROM timescaledb_information.chunks WHERE hypertable_name='cmp_machine') FROM cmp_machine
UNION ALL SELECT 'cmp_aucun', count(*), (SELECT count(*) FROM timescaledb_information.chunks WHERE hypertable_name='cmp_aucun') FROM cmp_aucun;
