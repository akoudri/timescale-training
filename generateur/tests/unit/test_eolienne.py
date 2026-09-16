import json
from pathlib import Path

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.eolienne import synthese_eolienne
from mistral_gen.etats import generer_etats
from mistral_gen.referentiel import construire_referentiel
from mistral_gen.vent import ChampsSite

BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def contexte():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    ref = construire_referentiel(cfg, params)
    etats = generer_etats(cfg, params, ref)
    champs = ChampsSite(cfg, params)
    signaux = synthese_eolienne(cfg, params, champs, 1, 1, etats.segments[1])
    return cfg, params, etats, signaux


def _autocorr(x, lag):
    x = x - x.mean()
    return float(np.dot(x[:-lag], x[lag:]) / np.dot(x, x))


def test_autocorrelation_vent_calibree(contexte):
    cfg, params, _, s = contexte
    rho_cible = params["vent"]["autocorrelation_10min"]
    rho = _autocorr(s["vitesse_vent_ms"], 60)  # 60 pas de 10 s = 10 min
    assert abs(rho - rho_cible) < 0.1


def test_courbe_de_puissance_reproduite(contexte):
    cfg, params, etats, s = contexte
    p_nom = params["referentiel"]["puissance_nominale_kw"]
    from mistral_gen.eolienne import masque_production
    n = len(s["puissance_kw"])
    prod = masque_production(etats.segments[1], n)
    v, p = s["vitesse_vent_ms"][prod], s["puissance_kw"][prod]
    v_grille = np.array([pt["vitesse_ms"] for pt in params["courbe_puissance"]])
    p_med = np.array([max(pt["mediane_kw"], 0) for pt in params["courbe_puissance"]])
    attendu = np.interp(v, v_grille, p_med)
    rmse = float(np.sqrt(np.mean((p - attendu) ** 2)))
    assert rmse < 0.10 * p_nom, f"RMSE {rmse:.0f} kW"


def test_bornes_physiques(contexte):
    cfg, params, _, s = contexte
    p_nom = params["referentiel"]["puissance_nominale_kw"]
    assert s["puissance_kw"].max() <= 1.10 * p_nom + 1e-9
    assert s["puissance_kw"].min() >= 0
    assert np.all(np.diff(s["energie_kwh"]) >= -1e-9), "compteur non monotone"
    assert 0 <= s["direction_vent_deg"].min() and s["direction_vent_deg"].max() < 360
    assert set(np.unique(s["disponible"])) <= {0.0, 1.0}


def test_angle_pale_en_escalier(contexte):
    _, _, _, s = contexte
    pale = s["angle_pale_deg"]
    changements = np.count_nonzero(np.diff(pale))
    # une consigne toutes les 10 min au plus : << nombre de points
    assert changements < len(pale) / 30


def test_signaux_lents_et_volatils_se_distinguent(contexte):
    _, _, _, s = contexte
    var_vent = np.var(np.diff(s["vitesse_vent_ms"]))
    var_temp = np.var(np.diff(s["temperature_multiplicateur_c"]))
    assert var_temp < var_vent / 10
