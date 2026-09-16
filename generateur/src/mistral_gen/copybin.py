"""Écrivain du format PostgreSQL COPY ... WITH (FORMAT binary), en flux.

Schéma cible (fiche §5.3) :
    ts         TIMESTAMPTZ      NOT NULL   -- int64, µs depuis 2000-01-01 UTC
    series_id  INTEGER          NOT NULL
    valeur     DOUBLE PRECISION NOT NULL
    qualite    SMALLINT         NOT NULL

L'écriture est vectorisée : chaque bloc de N lignes est encodé d'un coup
dans un tableau numpy structuré grand-boutiste, sans boucle Python.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import BinaryIO

import numpy as np

ENTETE = b"PGCOPY\n\xff\r\n\x00" + struct.pack(">ii", 0, 0)
FIN = struct.pack(">h", -1)

# époque PostgreSQL (2000-01-01T00:00:00Z) en µs depuis l'époque Unix
EPOQUE_PG_US = 946_684_800_000_000

_DTYPE_MESURE = np.dtype([
    ("n", ">i2"),
    ("lts", ">i4"), ("ts", ">i8"),
    ("lsid", ">i4"), ("sid", ">i4"),
    ("lval", ">i4"), ("val", ">f8"),
    ("lq", ">i4"), ("q", ">i2"),
])


def unix_us_vers_pg(ts_unix_us: np.ndarray) -> np.ndarray:
    """µs Unix -> µs PostgreSQL (int64)."""
    return ts_unix_us.astype(np.int64) - EPOQUE_PG_US


class CopyBinaryWriter:
    """Écrit des lignes (ts, series_id, valeur, qualite) au format COPY binaire."""

    def __init__(self, destination: str | Path | BinaryIO):
        if hasattr(destination, "write"):
            self._f: BinaryIO = destination  # type: ignore[assignment]
            self._proprietaire = False
        else:
            self._f = open(destination, "wb", buffering=1024 * 1024)
            self._proprietaire = True
        self._f.write(ENTETE)
        self.lignes = 0

    def ecrire_bloc(
        self,
        ts_unix_us: np.ndarray,
        series_id: np.ndarray,
        valeur: np.ndarray,
        qualite: np.ndarray,
    ) -> None:
        n = len(ts_unix_us)
        if not (len(series_id) == len(valeur) == len(qualite) == n):
            raise ValueError("longueurs de colonnes incohérentes")
        bloc = np.empty(n, dtype=_DTYPE_MESURE)
        bloc["n"] = 4
        bloc["lts"] = 8
        bloc["ts"] = unix_us_vers_pg(np.asarray(ts_unix_us))
        bloc["lsid"] = 4
        bloc["sid"] = np.asarray(series_id, dtype=np.int32)
        bloc["lval"] = 8
        bloc["val"] = np.asarray(valeur, dtype=np.float64)
        bloc["lq"] = 2
        bloc["q"] = np.asarray(qualite, dtype=np.int16)
        self._f.write(bloc.tobytes())
        self.lignes += n

    def fermer(self) -> int:
        self._f.write(FIN)
        self._f.flush()
        if self._proprietaire:
            self._f.close()
        return self.lignes

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fermer()
        return False
