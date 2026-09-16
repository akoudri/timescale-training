"""Champ de vent et d'ambiance par site.

Le vent est un processus AR(1) gaussien au pas de 10 s dont le coefficient
est dérivé de l'autocorrélation à 10 min calibrée (φ₁₀ₛ = ρ₆₀₀^(1/60)),
transformé vers la loi de Weibull calibrée par correspondance de quantiles.
Chaque turbine voit un mélange composante de site / composante propre
(corrélation spatiale ≈ 0,85), ce qui préserve la marginale et
l'autocorrélation tout en différenciant les machines.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from scipy.signal import lfilter
from scipy.special import ndtr

from .config import Config
from .rng import rng_pour

CORRELATION_SITE = 0.85
_WARMUP = 20_000


def _ar1(rng: np.random.Generator, n: int, phi: float) -> np.ndarray:
    """AR(1) gaussien stationnaire N(0,1), transitoire écarté."""
    eps = rng.standard_normal(n + _WARMUP)
    x = lfilter([np.sqrt(1.0 - phi * phi)], [1.0, -phi], eps)
    return x[_WARMUP:]


def _filtre_expo(x: np.ndarray, tau_s: float, pas_s: float) -> np.ndarray:
    """Filtre passe-bas exponentiel du premier ordre (constante de temps τ)."""
    alpha = 1.0 - np.exp(-pas_s / tau_s)
    return lfilter([alpha], [1.0, -(1.0 - alpha)], x, zi=[x[0] * (1.0 - alpha)])[0]


def phi_pas(params: dict, pas_s: int) -> float:
    rho_600 = params["vent"]["autocorrelation_10min"]
    return float(rho_600 ** (pas_s / 600.0))


def gauss_vers_weibull(g: np.ndarray, k: float, lam: float) -> np.ndarray:
    u = np.clip(ndtr(g), 1e-9, 1 - 1e-9)
    return lam * np.power(-np.log1p(-u), 1.0 / k)


class ChampsSite:
    """Composantes partagées par les machines d'un même site (mémoïsées)."""

    def __init__(self, cfg: Config, params: dict):
        self.cfg = cfg
        self.params = params
        self.n = cfg.points_par_jour * cfg.fenetre.jours
        self.phi = phi_pas(params, cfg.pas_s)

    @lru_cache(maxsize=8)
    def gauss_vent(self, site_id: int) -> np.ndarray:
        rng = rng_pour(self.cfg.graine, "vent-site", site_id)
        return _ar1(rng, self.n, self.phi)

    @lru_cache(maxsize=8)
    def direction(self, site_id: int) -> np.ndarray:
        """Direction du vent 0-360°, lente, partagée par site."""
        rng = rng_pour(self.cfg.graine, "direction-site", site_id)
        phi_lent = 0.99995   # τ ≈ 55 h : régimes de vent synoptiques
        g = _ar1(rng, self.n, phi_lent)
        base = float(rng.uniform(0, 360))
        return np.mod(base + 80.0 * g, 360.0)

    @lru_cache(maxsize=8)
    def temperature_ambiante(self, site_id: int) -> np.ndarray:
        """Température ambiante : cycle diurne + dérive synoptique + bruit."""
        p = self.params["temperatures"]
        rng = rng_pour(self.cfg.graine, "temp-site", site_id)
        t0 = self.cfg.fenetre.debut.timestamp()
        t = t0 + np.arange(self.n, dtype=np.float64) * self.cfg.pas_s
        # cycle diurne : minimum vers 05 h, maximum vers 15 h locale (approx UTC+1.5)
        heure = (t / 3600.0 + 1.5) % 24.0
        diurne = 4.0 * np.sin((heure - 9.0) / 24.0 * 2 * np.pi)
        # dérive saisonnière légère sur la fenêtre (sept -> oct : -4 °C)
        saison = -4.0 * np.arange(self.n) / self.n
        synoptique = 3.0 * _ar1(rng, self.n, 0.99998)
        bruit = 0.3 * _ar1(rng, self.n, 0.995)
        return p["nacelle_moyenne_c"] + diurne + saison + synoptique + bruit

    def vent_turbine(self, site_id: int, machine_id: int) -> np.ndarray:
        """Vitesse de vent (m/s) vue par une turbine du site."""
        rng = rng_pour(self.cfg.graine, "vent-turbine", machine_id)
        propre = _ar1(rng, self.n, self.phi)
        a = CORRELATION_SITE
        g = a * self.gauss_vent(site_id) + np.sqrt(1 - a * a) * propre
        v = self.params["vent"]
        return gauss_vers_weibull(g, v["weibull_k"], v["weibull_lambda_ms"])
