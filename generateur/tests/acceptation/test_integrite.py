"""§10 — Intégrité relationnelle, sur les artefacts fichiers."""

import csv
import json
from datetime import datetime

import numpy as np
import pytest

from mistral_gen.config import charger_config
from mistral_gen.referentiel import construire_referentiel

from .outils import BASE, SORTIE, charger_mesures_bin, ts_unix_s


@pytest.fixture(scope="module")
def contexte():
    cfg = charger_config(BASE / "config.yaml")
    params = json.loads((BASE / "params.json").read_text())
    return cfg, construire_referentiel(cfg, params)


def test_toute_serie_de_mesures_a_une_affectation(contexte):
    cfg, ref = contexte
    mm = charger_mesures_bin(SORTIE / "mesures.bin")
    sid = np.unique(np.asarray(mm[::1009]["sid"]))
    couverts = {a[0] for a in ref.affectations}
    assert set(sid.tolist()) <= couverts
    # l'affectation couvre l'horodatage : debut < min(ts), fin = NULL
    t_min = int(ts_unix_s(mm[:1]).min())
    for a in ref.affectations:
        debut = datetime.fromisoformat(a[3]).timestamp()
        assert debut <= t_min
        assert a[4] is None


def test_aucun_chevauchement_affectation(contexte):
    _, ref = contexte
    par_serie: dict[int, int] = {}
    for a in ref.affectations:
        par_serie[a[0]] = par_serie.get(a[0], 0) + 1
    # une seule affectation courante par série : aucun chevauchement possible
    assert all(n == 1 for n in par_serie.values())


def test_machine_id_evenements_existent(contexte):
    _, ref = contexte
    machines = {m[0] for m in ref.actifs}
    vus = set()
    with open(SORTIE / "evenements.csv") as f:
        for ligne in csv.reader(f):
            vus.add(int(ligne[1]))
    assert vus <= machines
    assert len(vus) == 46, "des machines sans aucun événement"


def test_meteo_reference_les_sites(contexte):
    _, ref = contexte
    sites = {s[0] for s in ref.sites}
    vus = set()
    with open(SORTIE / "meteo.csv") as f:
        for ligne in csv.reader(f):
            vus.add(int(ligne[1]))
    assert vus == sites
