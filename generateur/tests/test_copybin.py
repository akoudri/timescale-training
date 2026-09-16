import io
import struct
import time

import numpy as np

from mistral_gen.copybin import CopyBinaryWriter, EPOQUE_PG_US


def test_format_octet_par_octet():
    buf = io.BytesIO()
    w = CopyBinaryWriter(buf)
    # 2000-01-01T00:00:00Z (0 µs PG) et une seconde plus tard
    ts = np.array([EPOQUE_PG_US, EPOQUE_PG_US + 1_000_000], dtype=np.int64)
    w.ecrire_bloc(ts, np.array([7, 8]), np.array([1.5, -2.0]), np.array([0, 2]))
    w.fermer()
    donnees = buf.getvalue()

    entete = b"PGCOPY\n\xff\r\n\x00" + struct.pack(">ii", 0, 0)
    assert donnees.startswith(entete)
    corps = donnees[len(entete):-2]
    assert donnees[-2:] == b"\xff\xff"  # int16 -1

    ligne1 = (struct.pack(">h", 4)
              + struct.pack(">iq", 8, 0)
              + struct.pack(">ii", 4, 7)
              + struct.pack(">id", 8, 1.5)
              + struct.pack(">ih", 2, 0))
    ligne2 = (struct.pack(">h", 4)
              + struct.pack(">iq", 8, 1_000_000)
              + struct.pack(">ii", 4, 8)
              + struct.pack(">id", 8, -2.0)
              + struct.pack(">ih", 2, 2))
    assert corps == ligne1 + ligne2


def test_debit_10M_lignes(tmp_path):
    n = 10_000_000
    ts = np.arange(n, dtype=np.int64) * 10_000_000 + EPOQUE_PG_US
    sid = np.full(n, 42, dtype=np.int32)
    val = np.random.default_rng(0).normal(size=n)
    q = np.zeros(n, dtype=np.int16)
    debut = time.monotonic()
    with CopyBinaryWriter(tmp_path / "essai.bin") as w:
        for i in range(0, n, 1_000_000):
            s = slice(i, i + 1_000_000)
            w.ecrire_bloc(ts[s], sid[s], val[s], q[s])
    duree = time.monotonic() - debut
    assert w.lignes == n
    assert duree < 20, f"écriture trop lente : {duree:.1f}s pour 10M lignes"
