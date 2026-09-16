import json
from pathlib import Path

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.etats import generer_etats
from mistral_gen.mesures import JOURS_PROTEGES, Scenario, _masque_serie, construire_scenario
from mistral_gen.referentiel import construire_referentiel

BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def contexte():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    ref = construire_referentiel(cfg, params)
    etats = generer_etats(cfg, params, ref)
    sc = construire_scenario(cfg, params, ref, etats)
    return cfg, ref, etats, sc


def test_resets(contexte):
    cfg, ref, etats, sc = contexte
    assert len(sc.resets) == 2
    machines_arret = {a.machine_id for a in etats.arrets_imposes}
    types = {m[0]: m[2] for m in ref.actifs}
    for m_id, i in sc.resets.items():
        assert types[m_id] == "eolienne"
        assert m_id not in machines_arret
        assert i > JOURS_PROTEGES * cfg.points_par_jour


def test_trous_imposes(contexte):
    cfg, ref, etats, sc = contexte
    lib = {s.series_id: s.libelle for s in ref.series}
    seuil = int(30 * 60 / cfg.pas_s)
    longs = [(sid, i0, i1) for sid, ts in sc.trous.items()
             for i0, i1 in ts if i1 - i0 > seuil]
    assert len(longs) >= cfg.interruptions_min
    libs = {lib[sid] for sid, *_ in longs}
    assert "vitesse_vent_ms" in libs
    assert "energie_kwh" in libs
    assert len(libs) >= 5, "trous trop concentrés sur un seul type de signal"
    # aucun trou dans les jours protégés
    borne = JOURS_PROTEGES * cfg.points_par_jour
    assert all(i0 >= borne for ts in sc.trous.values() for i0, _ in ts)


def test_masque_serie_arret_horaire(contexte):
    cfg, *_ = contexte
    n = cfg.points_par_jour * cfg.fenetre.jours
    a = (10 * cfg.points_par_jour, 12 * cfg.points_par_jour)  # 48 h
    garde, ret_a, ret_t = _masque_serie(cfg, n, a, [])
    zone = garde[a[0]:a[1]]
    assert zone.sum() == 48  # un point par heure sur 48 h
    assert ret_a == 2 * cfg.points_par_jour - 48
    assert ret_t == 0
    assert garde[:a[0]].all() and garde[a[1]:].all()


def test_budget_de_retrait(contexte):
    cfg, ref, etats, sc = contexte
    total = 490 * cfg.points_par_jour * cfg.fenetre.jours
    ratio_arret = 3600 // cfg.pas_s
    ret_arrets = sum(
        (a.fin_i - a.debut_i) - ((a.fin_i - a.debut_i) + ratio_arret - 1) // ratio_arret
        for a in etats.arrets_imposes
    ) * 10  # 10 séries par éolienne
    ret_trous = sum(i1 - i0 for ts in sc.trous.values() for i0, i1 in ts)
    assert (ret_arrets + ret_trous) / total < 0.005, "plus de 0,5 % de lignes retirées"
