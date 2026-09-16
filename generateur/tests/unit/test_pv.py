import json
from pathlib import Path

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.etats import generer_etats
from mistral_gen.pv import elevation_solaire, synthese_pv
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
    centrale = ref.machines("pv")[0]
    m_id, site_id = centrale[0], centrale[1]
    site = next(s for s in ref.sites if s[0] == site_id)
    signaux = synthese_pv(cfg, params, champs, m_id, site_id, site[3], site[4],
                          etats.segments[m_id])
    cfg2 = (cfg, params, signaux, site)
    return cfg2


def test_elevation_solaire_plausible():
    # midi solaire à Greenwich à l'équinoxe : élévation ≈ 90 - |lat|
    import datetime as dt
    ts = np.array([dt.datetime(2026, 9, 23, 12, 0,
                               tzinfo=dt.timezone.utc).timestamp()])
    elev = np.degrees(elevation_solaire(ts, 48.0, 0.0))[0]
    assert abs(elev - 42.0) < 2.0


def test_production_nulle_la_nuit(contexte):
    cfg, params, signaux, site = contexte
    t0 = cfg.fenetre.debut.timestamp()
    n = len(next(iter(signaux.values())))
    ts = t0 + np.arange(n) * cfg.pas_s
    elev = elevation_solaire(ts, site[3], site[4])
    nuit = elev <= 0
    for (ond, lib), serie in signaux.items():
        if lib in ("puissance_dc_kw", "puissance_ac_kw", "irradiance_wm2", "tension_dc_v"):
            assert np.all(serie[nuit] == 0.0), (ond, lib)


def test_correlation_entre_onduleurs(contexte):
    _, _, signaux, _ = contexte
    p1 = signaux[(1, "puissance_ac_kw")]
    p2 = signaux[(2, "puissance_ac_kw")]
    jour = (p1 > 0) & (p2 > 0)
    r = np.corrcoef(p1[jour], p2[jour])[0, 1]
    assert r > 0.8


def test_dc_superieur_ou_egal_ac(contexte):
    _, _, signaux, _ = contexte
    for ond in (1, 2, 3, 4):
        dc = signaux[(ond, "puissance_dc_kw")]
        ac = signaux[(ond, "puissance_ac_kw")]
        assert np.all(dc + 1e-9 >= ac)
