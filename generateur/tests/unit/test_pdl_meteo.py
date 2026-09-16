import json
from pathlib import Path

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.meteo import generer_meteo
from mistral_gen.pdl import synthese_pdl
from mistral_gen.referentiel import construire_referentiel
from mistral_gen.rng import rng_pour
from mistral_gen.vent import ChampsSite

BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def contexte():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    ref = construire_referentiel(cfg, params)
    champs = ChampsSite(cfg, params)
    return cfg, params, ref, champs


def test_pdl_coherent_avec_la_somme(contexte):
    cfg, *_ = contexte
    n = 50_000
    rng = rng_pour(1, "test-somme")
    somme = np.clip(80_000 + 20_000 * rng.standard_normal(n), 0, None)
    s = synthese_pdl(cfg, 46, somme)
    r = np.corrcoef(s["puissance_active_kw"], somme)[0, 1]
    assert r > 0.99
    # à des pertes près : rapport moyen ≈ 1 - pertes
    rapport = s["puissance_active_kw"].sum() / somme.sum()
    assert abs(rapport - (1 - cfg.pdl_pertes)) < 0.01
    assert len(s) == 10
    assert np.all(np.diff(s["energie_injectee_kwh"]) >= -1e-9)


def test_meteo_volume_et_correlation(contexte):
    cfg, params, ref, champs = contexte
    lignes = generer_meteo(cfg, params, ref, champs)
    assert 35_000 <= len(lignes) <= 45_000
    types = {l[5] for l in lignes}
    assert types == {"releve", "prevision"}

    # corrélation relevés site 1 <-> vent des capteurs, sans identité
    rel1 = [(l[0], l[3]) for l in lignes if l[1] == 1 and l[5] == "releve"]
    rel1.sort()
    vent_meteo = np.array([v for _, v in rel1])
    vent_cap = champs.vent_turbine(1, 1)
    pas_h = 3600 // cfg.pas_s
    idx = np.minimum(np.arange(len(rel1)) * pas_h, len(vent_cap) - 1)
    vent_ref = vent_cap[idx]
    r = np.corrcoef(vent_meteo, vent_ref)[0, 1]
    assert r > 0.6, f"météo décorrélée des capteurs : r={r:.2f}"
    assert not np.allclose(vent_meteo, vent_ref), "météo identique aux capteurs"
