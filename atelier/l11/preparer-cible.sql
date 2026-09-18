-- L11 — prépare la base cible de migration : une base DÉDIÉE, mistral_prod,
-- portant le schéma cible de M03, SANS compression ni politiques actives
-- pendant la copie. La base du fil rouge ne convient pas : elle contient
-- déjà un jeu de 45 jours qui n'est pas celui de la legacy.
-- La colonne id est conservée : c'est l'identifiant monotone de la source
-- qui borne la copie par plages et le delta, et c'est elle qui porte la
-- leçon de la séquence (étape 5).
DROP DATABASE IF EXISTS mistral_prod;
CREATE DATABASE mistral_prod;
\c mistral_prod
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SEQUENCE mesures_id_seq;
CREATE TABLE mesures (
    id        BIGINT NOT NULL DEFAULT nextval('mesures_id_seq'),
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
);
-- create_hypertable() et non CREATE TABLE ... WITH (tsdb.hypertable) :
-- cette dernière forme active la compression ET pose une politique
-- columnstore par défaut (compress_after 7 jours, relative à now()), qui
-- basculerait des chunks PENDANT la copie — le piège n° 1 de la fiche.
SELECT create_hypertable('mesures', by_range('ts', INTERVAL '7 days'));
-- l'index de M06 : la cible reçoit le schéma complet
CREATE INDEX mesures_series_id_ts_idx ON mesures (series_id, ts DESC);

CREATE TABLE evenements (
    id         BIGSERIAL,
    ts         TIMESTAMPTZ NOT NULL,
    machine_id INTEGER NOT NULL,
    type       TEXT NOT NULL,
    code       INTEGER,
    message    TEXT
);
SELECT create_hypertable('evenements', by_range('ts', INTERVAL '7 days'),
                         migrate_data => true);

-- la compression n'est PAS activée : toujours après la bascule (étape 6).
-- Vérification : les deux requêtes doivent retourner « f » et « 0 ».
SELECT hypertable_name, compression_enabled
FROM   timescaledb_information.hypertables ORDER BY 1;
SELECT count(*) AS politiques_actives
FROM   timescaledb_information.jobs WHERE job_id >= 1000;
