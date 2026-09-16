"""§10 — Chargement.

- `mesures.bin` se charge par COPY ... FORMAT binary sans erreur sur
  PostgreSQL 17 (image TimescaleDB) ;
- le chargement dans une hypertable sans index secondaire prend moins de
  8 minutes sur une machine à 2 vCPU et 8 Go (cpuset + limite mémoire) ;
- la restauration de `mistral-referentiel.dump` prend moins de 2 minutes.

Marqué `chargement` : lancé explicitement (`pytest -m chargement`).
"""

import subprocess
import time

import pytest

from .outils import SORTIE

CONTENEUR = "mistral-test-pg17"
IMAGE = "timescale/timescaledb:latest-pg17"

DDL = """\
CREATE TABLE mesures (
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
) WITH (tsdb.hypertable, tsdb.partition_column = 'ts', tsdb.chunk_interval = '7 days');
"""

DDL_REPLI = """\
CREATE TABLE mesures (
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
);
SELECT create_hypertable('mesures', by_range('ts', INTERVAL '7 days'),
                         create_default_indexes => false);
"""


def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    assert r.returncode == 0, f"{' '.join(cmd[:8])} → {r.stdout[-800:]} {r.stderr[-800:]}"
    return r


def _psql(sql, base="postgres"):
    return _run(["docker", "exec", "-i", CONTENEUR, "psql", "-U", "postgres",
                 "-d", base, "-v", "ON_ERROR_STOP=1"], input=sql)


@pytest.fixture(scope="module")
def conteneur():
    # PGDATA sur /home : la partition du démon docker est trop petite pour
    # les ~12 Go de heap + WAL que produit le chargement
    pgdata = SORTIE / ".pgdata-test"
    subprocess.run(["docker", "rm", "-f", CONTENEUR], capture_output=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{pgdata.parent}:/p",
                    "busybox", "rm", "-rf", f"/p/{pgdata.name}"],
                   capture_output=True)
    pgdata.mkdir(parents=True, exist_ok=True)
    _run(["docker", "run", "-d", "--name", CONTENEUR,
          "--cpuset-cpus", "0,1", "--memory", "8g", "--memory-swap", "8g",
          "-e", "POSTGRES_PASSWORD=mistral",
          "-e", "PGDATA=/var/lib/postgresql/data/pgdata",
          "-v", f"{pgdata}:/var/lib/postgresql/data",
          "-v", f"{SORTIE}:/out:ro",
          "--shm-size", "1g", IMAGE])
    for _ in range(90):
        if subprocess.run(["docker", "exec", CONTENEUR, "pg_isready", "-U", "postgres"],
                          capture_output=True).returncode == 0:
            break
        time.sleep(1)
    else:
        pytest.fail("l'instance TimescaleDB pg17 ne démarre pas")
    time.sleep(3)
    yield CONTENEUR
    subprocess.run(["docker", "rm", "-f", CONTENEUR], capture_output=True)
    subprocess.run(["docker", "run", "--rm", "-v", f"{pgdata.parent}:/p",
                    "busybox", "rm", "-rf", f"/p/{pgdata.name}"],
                   capture_output=True)


@pytest.mark.chargement
def test_chargement_hypertable_sous_8_minutes(conteneur):
    _psql("DROP DATABASE IF EXISTS chargement; CREATE DATABASE chargement;")
    _psql("CREATE EXTENSION IF NOT EXISTS timescaledb;", base="chargement")
    version = _psql("SELECT current_setting('server_version_num');", base="chargement")
    assert int(version.stdout.splitlines()[2].strip()) >= 170000
    try:
        _psql(DDL, base="chargement")
    except AssertionError:
        _psql(DDL_REPLI, base="chargement")

    debut = time.monotonic()
    _psql("\\copy mesures FROM '/out/mesures.bin' WITH (FORMAT binary)\n",
          base="chargement")
    duree = time.monotonic() - debut

    n = _psql("SELECT count(*) FROM mesures;", base="chargement")
    assert int(n.stdout.splitlines()[2].strip()) == 189_958_049
    assert duree < 8 * 60, f"chargement en {duree:.0f}s (> 8 min)"


@pytest.mark.chargement
def test_restauration_referentiel_sous_2_minutes(conteneur):
    _psql("DROP DATABASE IF EXISTS ref_restauree; CREATE DATABASE ref_restauree;")
    debut = time.monotonic()
    _run(["docker", "exec", CONTENEUR, "pg_restore", "-U", "postgres",
          "--no-owner", "-d", "ref_restauree", "/out/mistral-referentiel.dump"])
    duree = time.monotonic() - debut
    comptes = _psql(
        "SELECT (SELECT count(*) FROM sites), (SELECT count(*) FROM actifs),"
        " (SELECT count(*) FROM signaux), (SELECT count(*) FROM affectation_capteur),"
        " (SELECT count(*) FROM evenements), (SELECT count(*) FROM meteo);",
        base="ref_restauree")
    ligne = comptes.stdout.splitlines()[2].split("|")
    assert [int(x) for x in ligne[:4]] == [4, 46, 25, 490]
    assert duree < 120, f"restauration en {duree:.0f}s (> 2 min)"


@pytest.mark.chargement
def test_chargement_hc_sans_erreur(conteneur):
    _psql("DROP DATABASE IF EXISTS hc; CREATE DATABASE hc;")
    _psql("CREATE EXTENSION IF NOT EXISTS timescaledb;", base="hc")
    try:
        _psql(DDL.replace("'7 days'", "'1 day'"), base="hc")
    except AssertionError:
        _psql(DDL_REPLI.replace("'7 days'", "'1 day'"), base="hc")
    _psql("\\copy mesures FROM '/out/mesures-hc.bin' WITH (FORMAT binary)\n", base="hc")
    n = _psql("SELECT count(*) FROM mesures;", base="hc")
    assert int(n.stdout.splitlines()[2].strip()) == 13_440_000
