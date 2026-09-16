"""Les dix signaux du point de livraison réseau.

La puissance active est cohérente avec la somme des productions du parc,
à des pertes près (fiche §5.2) — c'est vérifiable par agrégation.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .rng import rng_pour
from .vent import _ar1

TENSION_NOMINALE_V = 20_000.0     # HTA 20 kV
FREQUENCE_NOMINALE = 50.0


def synthese_pdl(
    cfg: Config,
    machine_id: int,
    somme_productions_kw: np.ndarray,
) -> dict[str, np.ndarray]:
    n = len(somme_productions_kw)
    rng = rng_pour(cfg.graine, "pdl", machine_id)

    pertes = cfg.pdl_pertes
    p_active = somme_productions_kw * (1.0 - pertes) \
        + 15.0 * _ar1(rng, n, 0.99)          # bruit de mesure de comptage
    p_active = np.clip(p_active, 0.0, None)

    # réactif : tangente phi pilotée autour de 0,1, un peu de dérive lente
    tan_phi = 0.10 + 0.03 * _ar1(rng, n, 0.9995)
    p_reactive = p_active * tan_phi

    tensions = {}
    for phase in ("l1", "l2", "l3"):
        tensions[phase] = TENSION_NOMINALE_V * (
            1.0 + 0.008 * _ar1(rng, n, 0.999) - 1.5e-7 * p_active
        )

    # I = S / (√3 · U), par phase (charge équilibrée au bruit près)
    s_apparente_kva = np.sqrt(p_active ** 2 + p_reactive ** 2)
    courants = {
        phase: s_apparente_kva * 1000.0 / (np.sqrt(3.0) * tensions[phase])
        * (1.0 + 0.004 * _ar1(rng, n, 0.99))
        for phase in ("l1", "l2", "l3")
    }

    frequence = FREQUENCE_NOMINALE + 0.02 * _ar1(rng, n, 0.998)

    energie = np.cumsum(p_active) * (cfg.pas_s / 3600.0) + float(rng.uniform(1e8, 3e8))

    return {
        "puissance_active_kw": p_active,
        "puissance_reactive_kvar": p_reactive,
        "tension_l1_v": tensions["l1"],
        "tension_l2_v": tensions["l2"],
        "tension_l3_v": tensions["l3"],
        "courant_l1_a": courants["l1"],
        "courant_l2_a": courants["l2"],
        "courant_l3_a": courants["l3"],
        "frequence_hz": frequence,
        "energie_injectee_kwh": energie,
    }
