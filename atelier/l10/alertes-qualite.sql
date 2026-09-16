-- L10 — table de consignation du contrôle qualité.
CREATE TABLE IF NOT EXISTS alertes_qualite (
    detecte_le    TIMESTAMPTZ NOT NULL,
    series_id     INTEGER NOT NULL,
    dernier_point TIMESTAMPTZ,
    anciennete    INTERVAL
);
