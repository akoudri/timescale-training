"""Générateurs pseudo-aléatoires déterministes, indépendants de l'ordre d'appel.

Chaque volet de génération (vent d'un site, signaux d'une machine, trous,
haute cardinalité...) reçoit son propre générateur Philox dont la clé est
dérivée de (graine, volet, clé numérique) par SHA-256. Deux exécutions avec
la même graine produisent donc exactement les mêmes tirages, quel que soit
l'ordre dans lequel les volets sont générés.
"""

from __future__ import annotations

import hashlib

import numpy as np


def rng_pour(graine: int, volet: str, cle: int = 0) -> np.random.Generator:
    h = hashlib.sha256(f"{graine}|{volet}|{cle}".encode()).digest()
    key = int.from_bytes(h[:16], "big")
    return np.random.Generator(np.random.Philox(key=key))
