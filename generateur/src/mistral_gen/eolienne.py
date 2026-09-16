"""Les dix signaux d'une éolienne (fiche §5.2).

Chaque nature de signal est réellement différente — la formation enseigne
que le traitement des trous en dépend :
- `puissance_kw`        continue, dérivée de la courbe de puissance calibrée
- `energie_kwh`         compteur cumulatif monotone
- `vitesse_vent_ms`     continue, volatile, autocorrélée
- `direction_vent_deg`  circulaire 0-360
- `temperature_*`       continues, lentes (filtre passe-bas calibré)
- `vitesse_rotor_rpm`   continue, corrélée au vent, nulle à l'arrêt
- `angle_pale_deg`      en escalier : consigne tenue jusqu'au changement
- `tension_reseau_v`    continue, faible variance
- `disponible`          discrète 0/1
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .rng import rng_pour
from .vent import ChampsSite, _ar1, _filtre_expo

PLAFOND_RELATIF = 1.10  # jamais plus de 110 % de la puissance nominale


def _interp_courbe(courbe: list[dict], cle: str) -> tuple[np.ndarray, np.ndarray]:
    v = np.array([p["vitesse_ms"] for p in courbe])
    y = np.array([max(p[cle], 0.0) for p in courbe])
    return v, y


def masque_production(segments: list[tuple[str, int, int]], n: int) -> np.ndarray:
    m = np.zeros(n, dtype=bool)
    for etat, i0, i1 in segments:
        if etat == "production":
            m[i0:i1] = True
    return m


def synthese_eolienne(
    cfg: Config,
    params: dict,
    champs: ChampsSite,
    machine_id: int,
    site_id: int,
    segments: list[tuple[str, int, int]],
) -> dict[str, np.ndarray]:
    n = champs.n
    pas = cfg.pas_s
    rng = rng_pour(cfg.graine, "eolienne", machine_id)
    p_nom = params["referentiel"]["puissance_nominale_kw"]

    en_prod = masque_production(segments, n)

    # --- vent et direction ---------------------------------------------------
    vent = champs.vent_turbine(site_id, machine_id)
    direction = np.mod(
        champs.direction(site_id) + rng.normal(0, 4.0) + 2.0 * _ar1(rng, n, 0.999),
        360.0,
    )

    # --- puissance : courbe calibrée + dispersion, nulle hors production -----
    v_grille, p_med = _interp_courbe(params["courbe_puissance"], "mediane_kw")
    _, p_sig = _interp_courbe(params["courbe_puissance"], "sigma_kw")
    puissance = np.interp(vent, v_grille, p_med)
    sigma = np.interp(vent, v_grille, p_sig)
    bruit = _ar1(rng, n, 0.98)          # dispersion corrélée dans le temps
    puissance = puissance + 0.6 * sigma * bruit
    puissance = np.clip(puissance, 0.0, PLAFOND_RELATIF * p_nom)
    puissance[~en_prod] = 0.0

    # --- compteur d'énergie (kWh), monotone ----------------------------------
    energie = np.cumsum(puissance) * (pas / 3600.0)
    energie += float(rng.uniform(5e6, 4e7))   # index de compteur déjà ancien

    # --- températures --------------------------------------------------------
    t = params["temperatures"]
    ambiante = champs.temperature_ambiante(site_id)
    nacelle = ambiante + 4.0 + 0.4 * _ar1(rng, n, 0.999)
    multiplicateur = _filtre_expo(
        t["multiplicateur_base_c"]
        + t["multiplicateur_pente_c_par_kw"] * puissance
        + 0.3 * (ambiante - np.mean(ambiante)),
        t["constante_temps_s"], pas,
    ) + 0.2 * _ar1(rng, n, 0.995)

    # --- rotor ---------------------------------------------------------------
    r_grille = np.array([p["vitesse_ms"] for p in params["rotor"]])
    r_rpm = np.array([p["rpm"] for p in params["rotor"]])
    rotor = np.interp(vent, r_grille, r_rpm) + 0.05 * _ar1(rng, n, 0.99)
    rotor = np.clip(rotor, 0.0, None)
    rotor[~en_prod] = 0.0

    # --- angle de pale : consigne en escalier, tenue 10 min ------------------
    v_rated = 11.5
    bloc = 60  # consigne recalculée toutes les 10 min
    n_blocs = n // bloc
    v_bloc = vent[: n_blocs * bloc].reshape(n_blocs, bloc).mean(axis=1)
    consigne = np.where(v_bloc <= v_rated, 0.0,
                        np.minimum(25.0, (v_bloc - v_rated) * 2.2))
    consigne = np.round(consigne * 2.0) / 2.0     # pas de consigne : 0,5°
    pale = np.repeat(consigne, bloc)
    if len(pale) < n:
        pale = np.concatenate([pale, np.full(n - len(pale), pale[-1])])
    pale = pale.copy()
    pale[~en_prod] = 90.0                          # pales en drapeau à l'arrêt

    # --- tension réseau ------------------------------------------------------
    te = params["tension"]
    tension = te["moyenne_v"] + 0.15 * te["sigma_v"] * _ar1(rng, n, 0.99)

    disponible = en_prod.astype(np.float64)

    return {
        "puissance_kw": puissance,
        "energie_kwh": energie,
        "vitesse_vent_ms": vent,
        "direction_vent_deg": direction,
        "temperature_nacelle_c": nacelle,
        "temperature_multiplicateur_c": multiplicateur,
        "vitesse_rotor_rpm": rotor,
        "angle_pale_deg": pale,
        "tension_reseau_v": tension,
        "disponible": disponible,
    }
