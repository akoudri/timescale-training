import json
from pathlib import Path

import pytest

from mistral_gen.config import charger_config
from mistral_gen.etats import generer_etats
from mistral_gen.referentiel import construire_referentiel

BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def contexte():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    ref = construire_referentiel(cfg, params)
    return cfg, params, ref, generer_etats(cfg, params, ref)


def test_sequences_couvrent_exactement_la_fenetre(contexte):
    cfg, _, ref, etats = contexte
    n = cfg.points_par_jour * cfg.fenetre.jours
    for m_id, seq in etats.segments.items():
        assert seq[0][1] == 0, m_id
        assert seq[-1][2] == n, m_id
        for (e1, a0, a1), (e2, b0, b1) in zip(seq, seq[1:]):
            assert a1 == b0, f"trou ou chevauchement machine {m_id}"
            assert e1 != e2, f"segments contigus de même état machine {m_id}"
        assert sum(i1 - i0 for _, i0, i1 in seq) == n


def test_arrets_imposes(contexte):
    cfg, _, ref, etats = contexte
    assert len(etats.arrets_imposes) == 3
    types = {m[0]: m[2] for m in ref.actifs}
    sites = {m[0]: m[1] for m in ref.actifs}
    assert {sites[a.machine_id] for a in etats.arrets_imposes} == {1, 2, 3}
    for a in etats.arrets_imposes:
        assert types[a.machine_id] == "eolienne"
        duree_h = (a.fin_i - a.debut_i) * cfg.pas_s / 3600
        assert 42 <= duree_h <= 48
        # l'arrêt figure bien comme maintenance dans la séquence
        seq = etats.segments[a.machine_id]
        couverts = [s for s in seq if s[0] == "maintenance"
                    and s[1] <= a.debut_i and s[2] >= a.fin_i]
        assert couverts, f"arrêt imposé absent de la séquence machine {a.machine_id}"
        # hors des 5 premiers jours (mesures-avant)
        assert a.debut_i > 5 * cfg.points_par_jour


def test_volume_evenements(contexte):
    *_, etats = contexte
    assert 650_000 <= len(etats.evenements) <= 750_000
    types = {e[2] for e in etats.evenements}
    assert types == {"alarme", "maintenance", "arret", "changement_etat"}
    # tris et JSON valides (échantillon)
    for e in etats.evenements[::50_000]:
        json.loads(e[4])


def test_machines_avec_arret_json(contexte):
    cfg, *_, etats = contexte
    doc = json.loads(etats.machines_avec_arret_json(cfg))
    assert len(doc) == 3
    assert all({"machine_id", "debut", "fin"} <= set(d) for d in doc)
