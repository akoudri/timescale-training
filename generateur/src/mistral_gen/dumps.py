"""Construction des dumps PostgreSQL dans un conteneur postgres:16 éphémère.

Produit :
- `mistral-referentiel.dump`  — sites, actifs, signaux, affectation_capteur,
  meteo, evenements (pg_dump -Fc)
- `mesures-avant.dump`        — 5 jours en table ordinaire (~21,1 M lignes)
- `mistral-legacy.dump`       — la base source de migration complète (§7)

Le conteneur monte le répertoire de sortie en lecture pour les COPY, et
les dumps sont écrits directement dans ce répertoire.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .config import Config
from .legacy import APRES_CHARGEMENT, DDL_LEGACY, ecrire_legacy_bin, evenements_legacy_sql

CONTENEUR = "mistral-gen-pg16"
IMAGE = "postgres:16"

DDL_METEO_EVENEMENTS = """\
CREATE TABLE meteo (
    ts               TIMESTAMPTZ NOT NULL,
    site_id          INTEGER NOT NULL,
    temperature_c    DOUBLE PRECISION,
    vitesse_vent_ms  DOUBLE PRECISION,
    irradiance_wm2   DOUBLE PRECISION,
    type             TEXT NOT NULL CHECK (type IN ('releve','prevision'))
);

CREATE TABLE evenements (
    ts         TIMESTAMPTZ NOT NULL,
    machine_id INTEGER NOT NULL,
    type       TEXT NOT NULL CHECK (type IN ('alarme','maintenance','arret','changement_etat')),
    code       INTEGER NOT NULL,
    attributs  JSONB
);
"""

DDL_MESURES = """\
CREATE TABLE mesures (
    ts        TIMESTAMPTZ NOT NULL,
    series_id INTEGER NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT NOT NULL DEFAULT 0
);
"""


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"échec: {' '.join(cmd[:6])}…\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def _psql(base: str, sql: str) -> str:
    r = _run(["docker", "exec", "-i", CONTENEUR,
              "psql", "-U", "postgres", "-d", base, "-v", "ON_ERROR_STOP=1"],
             input=sql)
    return r.stdout


def _psql_fichier(base: str, chemin_conteneur: str) -> str:
    return _psql(base, f"\\i {chemin_conteneur}\n")


def _dump(base: str, nom_fichier: str, sortie: Path) -> None:
    """pg_dump -Fc vers /tmp du conteneur puis rapatriement (droits)."""
    _run(["docker", "exec", CONTENEUR, "pg_dump", "-U", "postgres", "-Fc",
          "-f", f"/tmp/{nom_fichier}", base])
    _run(["docker", "cp", f"{CONTENEUR}:/tmp/{nom_fichier}", str(sortie / nom_fichier)])
    _run(["docker", "exec", CONTENEUR, "rm", f"/tmp/{nom_fichier}"])


def construire_dumps(cfg: Config, base_dir: Path) -> None:
    sortie = cfg.sortie
    t_debut = time.monotonic()

    def top(msg):
        print(f"[{time.monotonic() - t_debut:6.1f}s] {msg}", flush=True)

    top("mistral-legacy.bin (41,5 M lignes)…")
    n_legacy = ecrire_legacy_bin(cfg, sortie / "mistral-legacy.bin")
    (sortie / "legacy-evenements.sql").write_text(evenements_legacy_sql(cfg))
    top(f"  {n_legacy:,} lignes")

    top("démarrage du conteneur postgres:16…")
    subprocess.run(["docker", "rm", "-f", CONTENEUR], capture_output=True)
    _run(["docker", "run", "-d", "--name", CONTENEUR,
          "-e", "POSTGRES_PASSWORD=mistral",
          "-e", "POSTGRES_INITDB_ARGS=--locale=C.UTF-8",
          "-v", f"{sortie}:/out",
          "--shm-size", "1g",
          IMAGE, "-c", "fsync=off", "-c", "full_page_writes=off",
          "-c", "max_wal_size=4GB", "-c", "shared_buffers=1GB"])
    for _ in range(60):
        r = subprocess.run(["docker", "exec", CONTENEUR, "pg_isready", "-U", "postgres"],
                           capture_output=True)
        if r.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("postgres:16 ne démarre pas")
    time.sleep(2)

    # --- 1. référentiel + météo + événements --------------------------------
    top("base referentiel…")
    _psql("postgres", "DROP DATABASE IF EXISTS mistral_ref; CREATE DATABASE mistral_ref;")
    _psql_fichier("mistral_ref", "/out/referentiel.sql")
    _psql("mistral_ref", DDL_METEO_EVENEMENTS)
    _psql("mistral_ref",
          "\\copy meteo FROM '/out/meteo.csv' WITH (FORMAT csv)\n"
          "\\copy evenements FROM '/out/evenements.csv' WITH (FORMAT csv)\n")
    controle = _psql("mistral_ref",
                     "SELECT (SELECT count(*) FROM sites), (SELECT count(*) FROM actifs),"
                     " (SELECT count(*) FROM signaux), (SELECT count(*) FROM affectation_capteur),"
                     " (SELECT count(*) FROM meteo), (SELECT count(*) FROM evenements);")
    top(f"  comptages: {controle.splitlines()[2].strip()}")
    _dump("mistral_ref", "mistral-referentiel.dump", sortie)

    # --- 2. mesures-avant (table ordinaire, 5 jours) ------------------------
    top("base mesures-avant (21,1 M lignes)…")
    _psql("postgres", "DROP DATABASE IF EXISTS mistral_avant; CREATE DATABASE mistral_avant;")
    _psql("mistral_avant", DDL_MESURES)
    _psql("mistral_avant",
          "\\copy mesures FROM '/out/mesures-avant.bin' WITH (FORMAT binary)\n")
    controle = _psql("mistral_avant", "SELECT count(*) FROM mesures;")
    top(f"  lignes: {controle.splitlines()[2].strip()}")
    _dump("mistral_avant", "mesures-avant.dump", sortie)

    # --- 3. mistral_legacy ---------------------------------------------------
    top("base mistral_legacy…")
    _psql("postgres", "DROP DATABASE IF EXISTS mistral_legacy; CREATE DATABASE mistral_legacy;")
    _psql("mistral_legacy", DDL_LEGACY)
    _psql("mistral_legacy",
          "\\copy mesures (id, ts, series_id, valeur, qualite) FROM '/out/mistral-legacy.bin' WITH (FORMAT binary)\n")
    _psql_fichier("mistral_legacy", "/out/legacy-evenements.sql")
    top("  vues matérialisées et séquence…")
    _psql("mistral_legacy", APRES_CHARGEMENT)
    controle = _psql("mistral_legacy",
                     "SELECT (SELECT count(*) FROM mesures),"
                     " (SELECT last_value FROM mesures_id_seq),"
                     " (SELECT max(id) FROM mesures),"
                     " pg_size_pretty(pg_database_size('mistral_legacy'));")
    top(f"  contrôle: {controle.splitlines()[2].strip()}")
    _dump("mistral_legacy", "mistral-legacy.dump", sortie)

    top("arrêt du conteneur…")
    subprocess.run(["docker", "rm", "-f", CONTENEUR], capture_output=True)

    # les .bin intermédiaires de legacy ne sont pas des artefacts livrés
    (sortie / "mistral-legacy.bin").unlink(missing_ok=True)
    (sortie / "legacy-evenements.sql").unlink(missing_ok=True)

    # compléter le manifeste : les dumps sont des artefacts dérivés —
    # leur contenu est déterministe (il vient des fichiers ci-dessus),
    # mais pg_dump n'est pas reproductible bit à bit (horodatages internes)
    import json as _json
    from .manifeste import sha256_fichier
    chemin_manifeste = sortie / "MANIFESTE.json"
    if chemin_manifeste.exists():
        m = _json.loads(chemin_manifeste.read_text())
        m["comptages"]["mistral_legacy"] = n_legacy - 37  # purge simulée
        m["empreintes_sha256_derives"] = {
            nom: sha256_fichier(sortie / nom)
            for nom in ("mistral-referentiel.dump", "mesures-avant.dump",
                        "mistral-legacy.dump")
            if (sortie / nom).exists()
        }
        m["note_derives"] = (
            "Les dumps PostgreSQL sont dérivés des artefacts déterministes "
            "ci-dessus ; pg_dump n'étant pas reproductible bit à bit, leurs "
            "empreintes valent pour cette livraison, pas entre exécutions."
        )
        chemin_manifeste.write_text(_json.dumps(m, ensure_ascii=False, indent=2) + "\n")
    top("dumps terminés.")
