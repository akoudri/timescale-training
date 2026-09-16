-- L04 — table de charge dédiée. Jamais d'injection dans `mesures` :
-- l'état de reprise doit rester déterministe.
-- Même schéma que mesures + horodatage d'ingestion (fiche §13.3 : cette
-- colonne est introduite ICI, pédagogiquement, pas dans mesures).
DROP TABLE IF EXISTS mesures_charge;
CREATE TABLE mesures_charge (
    ts        TIMESTAMPTZ      NOT NULL,
    series_id INTEGER          NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT         NOT NULL DEFAULT 0,
    ingere_le TIMESTAMPTZ      NOT NULL DEFAULT now()
) WITH (
    tsdb.hypertable,
    tsdb.partition_column = 'ts',
    tsdb.chunk_interval   = '7 days'
);
