"""Jeu de contraste à haute cardinalité (contrainte 6.5).

20 000 séries, pas de 15 minutes, 7 jours : 13 440 000 lignes exactement.
Le contenu importe peu — marches aléatoires quelconques — seul compte
l'identifiant de série à forte cardinalité : sur un découpage journalier,
96 lignes par série et par jour, très en dessous de la taille d'un lot
de compression.

Les 7 jours sont alignés sur la fin de la fenêtre MISTRAL.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import numpy as np

from .config import Config
from .copybin import CopyBinaryWriter
from .rng import rng_pour


def generer_hc(cfg: Config, sortie: Path) -> int:
    pas_s = cfg.hc_pas_minutes * 60
    points_par_jour = 86400 // pas_s
    n_points = points_par_jour * cfg.hc_jours
    debut = cfg.fenetre.fin - timedelta(days=cfg.hc_jours)
    t0_us = int(debut.timestamp()) * 1_000_000
    pas_us = pas_s * 1_000_000

    ts_serie = t0_us + np.arange(n_points, dtype=np.int64) * pas_us
    qualite_zero = np.zeros(n_points, dtype=np.int16)

    lot = 500  # séries par bloc d'écriture
    with CopyBinaryWriter(sortie / "mesures-hc.bin") as w:
        for premier in range(1, cfg.hc_series + 1, lot):
            series = np.arange(premier, min(premier + lot, cfg.hc_series + 1))
            rng = rng_pour(cfg.graine, "hc", premier)
            pas_marche = rng.normal(0, 1.0, size=(len(series), n_points))
            valeurs = 100.0 + np.cumsum(pas_marche, axis=1)
            ts_bloc = np.broadcast_to(ts_serie, (len(series), n_points)).reshape(-1)
            sid_bloc = np.repeat(series.astype(np.int32), n_points)
            q_bloc = np.broadcast_to(qualite_zero, (len(series), n_points)).reshape(-1)
            w.ecrire_bloc(ts_bloc, sid_bloc, valeurs.reshape(-1), q_bloc)
    return w.lignes
