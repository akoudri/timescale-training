"""La base source à migrer : `mistral_legacy` (fiche §7).

Base PostgreSQL 16 **délibérément mal conçue** :
- table de mesures partitionnée par plage **en déclaratif**, partitions
  mensuelles créées par un script versionné dans la base — c'est cette
  contrainte qui interdit la conversion en hypertable et impose la
  migration par recréation (point pédagogique de M12) ;
- vues matérialisées classiques, rafraîchies sans suivi d'invalidation ;
- fonction de purge qui supprime ligne à ligne ;
- séquence sur `id` laissée dans un état non trivial (en avance sur
  max(id) après des purges) — l'atelier découvre qu'elle n'est pas
  répliquée ;
- fenêtre 20 juillet → 30 septembre 2026 : recouvre partiellement celle
  de `mesures` (15 septembre → 30 octobre) sans lui être identique, et
  contient les dates de juillet 2026 citées par le support.

400 séries au pas de 60 s sur 72 jours = 41 472 000 lignes (38-42 M ✓).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from .config import Config
from .copybin import ENTETE, FIN, EPOQUE_PG_US
from .rng import rng_pour

_DTYPE_LEGACY = np.dtype([
    ("n", ">i2"),
    ("lid", ">i4"), ("id", ">i8"),
    ("lts", ">i4"), ("ts", ">i8"),
    ("lsid", ">i4"), ("sid", ">i4"),
    ("lval", ">i4"), ("val", ">f8"),
    ("lq", ">i4"), ("q", ">i2"),
])

DDL_LEGACY = """\
-- mistral_legacy : le système historique, tel qu'il tourne aujourd'hui.
-- Partitionnement déclaratif par plage : les partitions mensuelles sont
-- créées à la main par creer_partition_mois(), appelée par un cron.

CREATE SEQUENCE mesures_id_seq;

CREATE TABLE mesures (
    id        BIGINT NOT NULL DEFAULT nextval('mesures_id_seq'),
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
) PARTITION BY RANGE (ts);

CREATE OR REPLACE FUNCTION creer_partition_mois(mois date)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    nom text := format('mesures_y%sm%s', to_char(mois, 'YYYY'), to_char(mois, 'MM'));
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF mesures FOR VALUES FROM (%L) TO (%L)',
        nom, date_trunc('month', mois), date_trunc('month', mois) + interval '1 month');
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (ts)', nom || '_ts_idx', nom);
    RETURN nom;
END $$;

SELECT creer_partition_mois(m::date)
FROM generate_series('2026-07-01'::date, '2026-10-01'::date, interval '1 month') m;

CREATE TABLE evenements (
    id         BIGSERIAL,
    ts         TIMESTAMPTZ NOT NULL,
    machine_id INTEGER NOT NULL,
    type       TEXT NOT NULL,
    code       INTEGER,
    message    TEXT
);

-- Purge « historique » : suppression ligne à ligne, par paquets, dans une
-- boucle. C'est elle qui bloque la production une nuit par mois.
CREATE OR REPLACE FUNCTION purge_anciennes_mesures(limite timestamptz)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    supprimees bigint := 0;
    lot bigint;
BEGIN
    LOOP
        DELETE FROM mesures WHERE id IN (
            SELECT id FROM mesures WHERE ts < limite LIMIT 1000);
        GET DIAGNOSTICS lot = ROW_COUNT;
        supprimees := supprimees + lot;
        EXIT WHEN lot = 0;
    END LOOP;
    RETURN supprimees;
END $$;
"""

APRES_CHARGEMENT = """\
-- Vues matérialisées classiques : recalcul complet à chaque REFRESH,
-- aucun suivi d'invalidation (pathologie n°3 de M01).
CREATE MATERIALIZED VIEW mv_energie_jour AS
SELECT date_trunc('day', ts) AS jour, series_id,
       count(*) AS points, sum(valeur) AS somme
FROM   mesures GROUP BY 1, 2;
CREATE INDEX ON mv_energie_jour (jour, series_id);

CREATE MATERIALIZED VIEW mv_moyennes_heure AS
SELECT date_trunc('hour', ts) AS heure, series_id, avg(valeur) AS moyenne
FROM   mesures GROUP BY 1, 2;
CREATE INDEX ON mv_moyennes_heure (heure, series_id);

-- Un passé de purges a laissé la séquence en avance sur max(id) :
-- état non trivial, découvert en atelier (elle n'est pas répliquée).
DELETE FROM mesures WHERE id IN (SELECT id FROM mesures ORDER BY id LIMIT 37);
SELECT setval('mesures_id_seq',
              (SELECT max(id) FROM mesures) + 52341);

ANALYZE mesures;
"""


def ecrire_legacy_bin(cfg: Config, chemin: Path) -> int:
    """COPY binaire (id, ts, series_id, valeur, qualite) pour mistral_legacy."""
    pas_s = cfg.legacy_pas_secondes
    n_points = cfg.legacy_jours * 86400 // pas_s
    t0_us = int(cfg.legacy_debut.timestamp()) * 1_000_000
    pas_us = pas_s * 1_000_000

    ts_us_pg = (t0_us + np.arange(n_points, dtype=np.int64) * pas_us) - EPOQUE_PG_US
    t_jour = (np.arange(n_points, dtype=np.float64) * pas_s / 86400.0) % 1.0

    lignes = 0
    prochain_id = 1
    with open(chemin, "wb", buffering=1024 * 1024) as f:
        f.write(ENTETE)
        for serie in range(1, cfg.legacy_series + 1):
            rng = rng_pour(cfg.graine, "legacy", serie)
            base = float(rng.uniform(50, 1500))
            ampl = float(rng.uniform(5, 200))
            phase = float(rng.uniform(0, 2 * np.pi))
            lent = np.interp(
                np.arange(n_points),
                np.linspace(0, n_points, 200),
                rng.normal(0, ampl / 2, 200),
            )
            valeurs = base + ampl * np.sin(2 * np.pi * t_jour + phase) + lent \
                + rng.normal(0, ampl / 10, n_points)
            qualite = (rng.random(n_points) < 0.01).astype(np.int16)

            bloc = np.empty(n_points, dtype=_DTYPE_LEGACY)
            bloc["n"] = 5
            bloc["lid"] = 8
            bloc["id"] = np.arange(prochain_id, prochain_id + n_points, dtype=np.int64)
            bloc["lts"] = 8
            bloc["ts"] = ts_us_pg
            bloc["lsid"] = 4
            bloc["sid"] = serie
            bloc["lval"] = 8
            bloc["val"] = valeurs
            bloc["lq"] = 2
            bloc["q"] = qualite
            f.write(bloc.tobytes())
            prochain_id += n_points
            lignes += n_points
        f.write(FIN)
    return lignes


def evenements_legacy_sql(cfg: Config) -> str:
    """Quelques dizaines de milliers d'événements legacy (INSERT groupés)."""
    rng = rng_pour(cfg.graine, "legacy-evenements")
    n = 60_000
    t0 = int(cfg.legacy_debut.timestamp())
    duree = cfg.legacy_jours * 86400
    ts = np.sort(rng.integers(0, duree, n)) + t0
    machines = rng.integers(1, 47, n)
    codes = rng.integers(100, 900, n)
    types = np.array(["alarme", "arret", "maintenance"])[rng.integers(0, 3, n)]
    lignes = ["INSERT INTO evenements (ts, machine_id, type, code, message) VALUES"]
    valeurs = []
    from datetime import datetime, timezone
    for i in range(n):
        iso = datetime.fromtimestamp(int(ts[i]), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")
        valeurs.append(f"('{iso}',{machines[i]},'{types[i]}',{codes[i]},'code {codes[i]}')")
    corps = ",\n".join(valeurs)
    return lignes[0] + "\n" + corps + ";\n"
