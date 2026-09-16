"""§10 — Plausibilité physique, vérifiée sur les artefacts."""

import json

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.etats import generer_etats
from mistral_gen.pv import elevation_solaire
from mistral_gen.referentiel import construire_referentiel

from .outils import BASE, SORTIE, charger_mesures_bin, extraire_serie, ts_unix_s


@pytest.fixture(scope="module")
def cfg():
    return charger_config(BASE / "config.yaml")


@pytest.fixture(scope="module")
def params():
    return json.loads((BASE / "params.json").read_text())


@pytest.fixture(scope="module")
def mesures():
    return charger_mesures_bin(SORTIE / "mesures.bin")


def test_courbe_de_puissance_reproduite(mesures, params):
    ts_p, p = extraire_serie(mesures, 1)   # machine 1 : puissance
    ts_v, v = extraire_serie(mesures, 3)   # machine 1 : vent
    n = min(len(p), len(v))
    assert np.array_equal(ts_p[:n], ts_v[:n])
    p, v = p[:n], v[:n]
    prod = p > 0
    grille = np.array([pt["vitesse_ms"] for pt in params["courbe_puissance"]])
    med = np.array([max(pt["mediane_kw"], 0) for pt in params["courbe_puissance"]])
    attendu = np.interp(v[prod], grille, med)
    rmse = float(np.sqrt(np.mean((p[prod] - attendu) ** 2)))
    p_nom = params["referentiel"]["puissance_nominale_kw"]
    assert rmse < 0.10 * p_nom


def test_puissance_jamais_au_dela_de_110_pct(mesures, params):
    p_nom = params["referentiel"]["puissance_nominale_kw"]
    sid = np.asarray(mesures["sid"])
    puissance_eol = (sid <= 420) & (sid % 10 == 1)
    maxi = float(np.asarray(mesures["val"])[puissance_eol].max())
    assert maxi <= 1.10 * p_nom + 1e-6


def test_energie_monotone_entre_remises_a_zero(mesures):
    n_resets = 0
    for m_id in range(1, 43):
        sid = (m_id - 1) * 10 + 2
        _, e = extraire_serie(mesures, sid)
        d = np.diff(e)
        negatifs = np.flatnonzero(d < -1e-9)
        assert len(negatifs) <= 1, f"série {sid} : plusieurs décroissances"
        n_resets += len(negatifs)
        if len(negatifs):
            i = negatifs[0]
            assert np.all(np.diff(e[: i + 1]) >= -1e-9)
            assert np.all(np.diff(e[i + 1:]) >= -1e-9)
    assert n_resets == 2


def test_pv_nulles_la_nuit(mesures, cfg, params):
    ref = construire_referentiel(cfg, params)
    sites = {s[0]: s for s in ref.sites}
    pv_series = [s for s in ref.series if s.type_machine == "pv"
                 and s.libelle in ("puissance_dc_kw", "puissance_ac_kw",
                                   "irradiance_wm2", "tension_dc_v")]
    for serie in pv_series[::8] + pv_series[:1]:
        ts, val = extraire_serie(mesures, serie.series_id)
        site = sites[serie.site_id]
        elev = elevation_solaire(ts.astype(np.float64), site[3], site[4])
        nuit = elev <= 0
        assert np.all(val[nuit] == 0.0), serie.series_id


def test_autocorrelation_vent(mesures, params):
    _, v = extraire_serie(mesures, 3)
    v = v[: 5 * 8640]          # 5 jours pleins, sans trous
    x = v - v.mean()
    rho = float(np.dot(x[:-60], x[60:]) / np.dot(x, x))
    assert abs(rho - params["vent"]["autocorrelation_10min"]) < 0.1


def test_etats_couvrent_la_fenetre(cfg, params):
    ref = construire_referentiel(cfg, params)
    etats = generer_etats(cfg, params, ref)
    n = cfg.points_par_jour * cfg.fenetre.jours
    for m_id, seq in etats.segments.items():
        assert sum(i1 - i0 for _, i0, i1 in seq) == n
        assert seq[0][1] == 0 and seq[-1][2] == n
