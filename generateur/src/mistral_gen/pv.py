"""Les signaux photovoltaïques : 5 signaux × 4 onduleurs par centrale.

Profil diurne calculé par la position solaire (algorithme NOAA simplifié)
aux coordonnées du site : les séries de production (puissances, irradiance,
tension DC) sont **strictement nulles** entre le coucher et le lever.
La température de module suit l'ambiante la nuit — une température nulle
ne serait pas une donnée, ce point est assumé et documenté.

La couverture nuageuse est un AR(1) lent partagé par la centrale : les
onduleurs d'une même centrale sont fortement corrélés entre eux.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .referentiel import ONDULEURS_PAR_CENTRALE, PV_PUISSANCE_ONDULEUR_KW
from .rng import rng_pour
from .vent import ChampsSite, _ar1, _filtre_expo

RENDEMENT_ONDULEUR = 0.965
COEF_TEMPERATURE = 0.004      # perte relative par °C au-dessus de 25 °C


def elevation_solaire(ts_unix: np.ndarray, lat_deg: float, lon_deg: float) -> np.ndarray:
    """Élévation du soleil (radians), algorithme NOAA simplifié, vectorisé."""
    jours = ts_unix / 86400.0
    # jour julien depuis l'époque Unix ; 2440587.5 = JD du 1970-01-01T00:00Z
    jd = jours + 2440587.5
    n = jd - 2451545.0                      # jours depuis J2000
    L = np.radians((280.460 + 0.9856474 * n) % 360.0)   # longitude moyenne
    g = np.radians((357.528 + 0.9856003 * n) % 360.0)   # anomalie moyenne
    lam = L + np.radians(1.915) * np.sin(g) + np.radians(0.020) * np.sin(2 * g)
    eps = np.radians(23.439 - 0.0000004 * n)
    decl = np.arcsin(np.sin(eps) * np.sin(lam))
    # équation du temps (minutes), approximation classique
    alpha = np.arctan2(np.cos(eps) * np.sin(lam), np.cos(lam))
    eqtime = 4.0 * np.degrees(np.mod(L - alpha + np.pi, 2 * np.pi) - np.pi)
    # temps solaire vrai (minutes depuis minuit UTC) + correction longitude
    minutes = np.mod(ts_unix / 60.0, 1440.0)
    tst = np.mod(minutes + eqtime + 4.0 * lon_deg, 1440.0)
    ha = np.radians(tst / 4.0 - 180.0)
    lat = np.radians(lat_deg)
    sin_elev = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(ha)
    return np.arcsin(np.clip(sin_elev, -1.0, 1.0))


def synthese_pv(
    cfg: Config,
    params: dict,
    champs: ChampsSite,
    machine_id: int,
    site_id: int,
    lat: float,
    lon: float,
    segments: list[tuple[str, int, int]],
) -> dict[tuple[int, str], np.ndarray]:
    """Retourne {(onduleur, libelle): série} pour les 20 séries de la centrale."""
    n = champs.n
    pas = cfg.pas_s
    t0 = cfg.fenetre.debut.timestamp()
    ts = t0 + np.arange(n, dtype=np.float64) * pas

    elev = elevation_solaire(ts, lat, lon)
    jour_masque = elev > 0.0
    ciel_clair = 1050.0 * np.power(np.clip(np.sin(elev), 0.0, 1.0), 1.15)

    # couverture nuageuse partagée par la centrale (AR lent -> [0.12, 1])
    rng_c = rng_pour(cfg.graine, "nuages", machine_id)
    g_nuages = _ar1(rng_c, n, 0.9998)
    attenuation = 0.12 + 0.88 / (1.0 + np.exp(-1.3 * (g_nuages + 0.6)))

    en_marche = np.ones(n, dtype=bool)
    for etat, i0, i1 in segments:
        if etat != "production":
            en_marche[i0:i1] = False

    ambiante = champs.temperature_ambiante(site_id)

    resultat: dict[tuple[int, str], np.ndarray] = {}
    for onduleur in range(1, ONDULEURS_PAR_CENTRALE + 1):
        rng_o = rng_pour(cfg.graine, "onduleur", machine_id * 10 + onduleur)
        # petite variation propre (salissure, désalignement, mismatch)
        facteur = float(rng_o.uniform(0.96, 1.0))
        bruit_o = 1.0 + 0.02 * _ar1(rng_o, n, 0.995)

        irradiance = ciel_clair * attenuation * bruit_o
        irradiance[~jour_masque] = 0.0

        t_module = ambiante + 0.028 * _filtre_expo(irradiance, 1200.0, pas)

        p_dc = (PV_PUISSANCE_ONDULEUR_KW / 1000.0) * irradiance * facteur \
            * (1.0 - COEF_TEMPERATURE * np.clip(t_module - 25.0, 0.0, None))
        p_dc = np.clip(p_dc, 0.0, 1.08 * PV_PUISSANCE_ONDULEUR_KW)
        p_dc[~en_marche] = 0.0
        p_dc[~jour_masque] = 0.0

        p_ac = np.minimum(p_dc * RENDEMENT_ONDULEUR, PV_PUISSANCE_ONDULEUR_KW)

        tension_dc = np.where(
            jour_masque & en_marche,
            655.0 - 0.9 * np.clip(t_module - 25.0, -20.0, None) + 4.0 * _ar1(rng_o, n, 0.99),
            0.0,
        )

        resultat[(onduleur, "puissance_dc_kw")] = p_dc
        resultat[(onduleur, "puissance_ac_kw")] = p_ac
        resultat[(onduleur, "tension_dc_v")] = tension_dc
        resultat[(onduleur, "temperature_module_c")] = t_module
        resultat[(onduleur, "irradiance_wm2")] = irradiance
    return resultat
