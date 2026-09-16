"""Lecture des artefacts COPY binaire pour les tests d'acceptation.

Les fichiers mesures ont des lignes de taille fixe (40 octets pour le
schéma à 4 colonnes) : ils se relisent par vue numpy structurée, sans
passer par PostgreSQL.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mistral_gen.copybin import EPOQUE_PG_US, _DTYPE_MESURE

BASE = Path(__file__).resolve().parents[2]
SORTIE = BASE / "output"

TAILLE_ENTETE = 19
TAILLE_FIN = 2


def charger_mesures_bin(chemin: Path) -> np.ndarray:
    """memmap structuré sur un fichier COPY binaire au schéma mesures."""
    taille = chemin.stat().st_size
    n = (taille - TAILLE_ENTETE - TAILLE_FIN) // _DTYPE_MESURE.itemsize
    assert (taille - TAILLE_ENTETE - TAILLE_FIN) % _DTYPE_MESURE.itemsize == 0, \
        "taille de fichier incompatible avec des lignes de taille fixe"
    return np.memmap(chemin, dtype=_DTYPE_MESURE, mode="r",
                     offset=TAILLE_ENTETE, shape=(n,))


def ts_unix_s(bloc: np.ndarray) -> np.ndarray:
    return (bloc["ts"].astype(np.int64) + EPOQUE_PG_US) // 1_000_000


def extraire_serie(mm: np.ndarray, series_id: int) -> tuple[np.ndarray, np.ndarray]:
    """(ts_unix_s, valeurs) d'une série, dans l'ordre du fichier."""
    masque = mm["sid"] == series_id
    sous = mm[masque]
    return ts_unix_s(sous), np.asarray(sous["val"], dtype=np.float64)


def manifeste() -> dict:
    return json.loads((SORTIE / "MANIFESTE.json").read_text())


def machines_avec_arret() -> list[dict]:
    return json.loads((SORTIE / "machines-avec-arret.json").read_text())
