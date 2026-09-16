import json
from pathlib import Path

import pytest

from mistral_gen.config import charger_config
from mistral_gen.referentiel import construire_referentiel, emettre_sql

BASE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ref():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    return construire_referentiel(cfg, params)


def test_comptages(ref):
    assert len(ref.sites) == 4
    assert len(ref.actifs) == 46
    assert len(ref.signaux) == 25
    assert len(ref.affectations) == 490
    assert len(ref.series) == 490


def test_repartition_imposee(ref):
    par_site: dict[tuple, int] = {}
    for m in ref.actifs:
        par_site[(m[1], m[2])] = par_site.get((m[1], m[2]), 0) + 1
    assert par_site.get((1, "eolienne")) == 15
    assert par_site.get((2, "eolienne")) == 18
    assert par_site.get((3, "eolienne")) == 9
    assert (4, "eolienne") not in par_site
    assert par_site.get((3, "pv")) == 1
    assert par_site.get((4, "pv")) == 2
    assert par_site.get((4, "pdl")) == 1


def test_series_uniques_et_couverture(ref):
    ids = [s.series_id for s in ref.series]
    assert ids == list(range(1, 491))
    familles = {s.famille for s in ref.series}
    assert familles == {"production", "meteo", "mecanique", "electrique"}
    eol = [s for s in ref.series if s.type_machine == "eolienne"]
    pv = [s for s in ref.series if s.type_machine == "pv"]
    pdl = [s for s in ref.series if s.type_machine == "pdl"]
    assert len(eol) == 420 and len(pv) == 60 and len(pdl) == 10
    # 4 onduleurs × 5 signaux par centrale
    par_centrale: dict[int, set] = {}
    for s in pv:
        par_centrale.setdefault(s.machine_id, set()).add((s.onduleur, s.libelle))
    assert all(len(v) == 20 for v in par_centrale.values())


def test_affectations_courantes(ref):
    assert all(a[4] is None for a in ref.affectations)


def test_sql_contient_exclusion(ref):
    sql = emettre_sql(ref)
    assert "EXCLUDE USING gist (series_id WITH =, tstzrange(debut, fin) WITH &&)" in sql
    assert sql.count("INSERT INTO affectation_capteur") == 490


def test_determinisme(ref):
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    ref2 = construire_referentiel(cfg, params)
    assert ref2.actifs == ref.actifs
    assert ref2.affectations == ref.affectations
