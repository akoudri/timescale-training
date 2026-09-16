"""§10 — Déterminisme strict : mêmes graine et config => fichiers identiques."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from mistral_gen.config import charger_config
from mistral_gen.manifeste import sha256_fichier

from .outils import BASE, SORTIE, manifeste

ARTEFACTS_DETERMINISTES = [
    "mesures.bin", "mesures-avant.bin", "mesures-hc.bin",
    "referentiel.sql", "evenements.csv", "meteo.csv", "machines-avec-arret.json",
]


def _generer_dans(tmp: Path, graine: int) -> Path:
    d = yaml.safe_load((BASE / "config.yaml").read_text())
    d["graine"] = graine
    sortie = tmp / f"sortie-{graine}"
    d["sortie"] = str(sortie)
    chemin = tmp / f"config-{graine}.yaml"
    chemin.write_text(yaml.dump(d))
    shutil.copy(BASE / "params.json", tmp / "params.json")

    from mistral_gen.cli import cmd_generer

    class Args:
        config = str(chemin)

    cmd_generer(Args())
    return sortie


@pytest.mark.lent
def test_meme_graine_memes_empreintes(tmp_path):
    sortie2 = _generer_dans(tmp_path, 20260315)
    empreintes_livrees = manifeste()["empreintes_sha256"]
    for nom in ARTEFACTS_DETERMINISTES:
        assert sha256_fichier(sortie2 / nom) == empreintes_livrees[nom], nom
    shutil.rmtree(sortie2)


@pytest.mark.lent
def test_graine_differente_artefacts_differents(tmp_path):
    sortie2 = _generer_dans(tmp_path, 19750523)
    empreintes_livrees = manifeste()["empreintes_sha256"]
    differents = [
        nom for nom in ("mesures.bin", "mesures-hc.bin", "evenements.csv")
        if sha256_fichier(sortie2 / nom) != empreintes_livrees[nom]
    ]
    assert differents == ["mesures.bin", "mesures-hc.bin", "evenements.csv"]
    shutil.rmtree(sortie2)


def test_manifeste_reproduit_les_empreintes_livrees():
    m = manifeste()
    for nom, empreinte in m["empreintes_sha256"].items():
        assert sha256_fichier(SORTIE / nom) == empreinte, nom
