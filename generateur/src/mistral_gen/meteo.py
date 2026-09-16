"""Table `meteo` : source externe au pas horaire (fiche §5.5).

Corrélée aux mesures capteurs **sans leur être identique** : biais propre,
bruit d'observation, et prévisions dont l'erreur croît avec l'horizon.
Par site et par heure : 1 relevé + 8 prévisions (horizons 1 à 8 h),
soit ≈ 39 000 lignes (« environ 40 000 »).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .config import Config
from .pv import elevation_solaire
from .referentiel import Referentiel
from .rng import rng_pour
from .vent import ChampsSite

HORIZONS_PREVISION = 8


def generer_meteo(cfg: Config, params: dict, ref: Referentiel,
                  champs: ChampsSite) -> list[tuple]:
    """Lignes (ts_unix, site_id, temperature_c, vitesse_vent_ms,
    irradiance_wm2, type)."""
    pas_h = 3600 // cfg.pas_s
    n_heures = cfg.fenetre.jours * 24 + 1
    t0 = int(cfg.fenetre.debut.timestamp())
    lignes: list[tuple] = []

    for site_id, nom, region, lat, lon in ref.sites:
        rng = rng_pour(cfg.graine, "meteo", site_id)

        # vérité terrain : moyennes horaires des champs de site
        vent_site = champs.vent_turbine(site_id, machine_id=1000 + site_id)
        temp_site = champs.temperature_ambiante(site_id)
        n = len(vent_site)
        idx = np.minimum(np.arange(n_heures) * pas_h, n - 1)

        ts_h = t0 + np.arange(n_heures, dtype=np.int64) * 3600
        elev = elevation_solaire(ts_h.astype(np.float64), lat, lon)
        irr_h = 1050.0 * np.power(np.clip(np.sin(elev), 0.0, 1.0), 1.15) \
            * (0.45 + 0.4 * rng.random(n_heures))

        # station externe : biais fixe + bruit d'observation
        biais_v = float(rng.normal(0, 0.6))
        biais_t = float(rng.normal(0, 1.0))
        vent_rel = np.clip(vent_site[idx] + biais_v + rng.normal(0, 0.5, n_heures), 0, None)
        temp_rel = temp_site[idx] + biais_t + rng.normal(0, 0.4, n_heures)

        for i in range(n_heures):
            lignes.append((int(ts_h[i]), site_id, round(float(temp_rel[i]), 2),
                           round(float(vent_rel[i]), 2), round(float(irr_h[i]), 1),
                           "releve"))

        # prévisions : émises pour l'heure H, erreur croissante avec l'horizon
        for h in range(1, HORIZONS_PREVISION + 1):
            err_v = rng.normal(0, 0.35 * np.sqrt(h), n_heures)
            err_t = rng.normal(0, 0.3 * np.sqrt(h), n_heures)
            cible = np.minimum(np.arange(n_heures) + h, n_heures - 1)
            for i in range(n_heures):
                j = int(cible[i])
                lignes.append((
                    int(ts_h[j]), site_id,
                    round(float(temp_rel[j] + err_t[i]), 2),
                    round(float(max(vent_rel[j] + err_v[i], 0.0)), 2),
                    round(float(irr_h[j] * (1 + 0.1 * np.sqrt(h) * float(rng.normal())) if irr_h[j] > 0 else 0.0), 1),
                    "prevision",
                ))

    lignes.sort(key=lambda l: (l[0], l[1], l[5]))
    return lignes


def emettre_meteo_csv(lignes: list[tuple], chemin) -> int:
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        for ts, site_id, temp, vent, irr, type_ in lignes:
            iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")
            f.write(f"{iso},{site_id},{temp},{vent},{irr},{type_}\n")
    return len(lignes)
