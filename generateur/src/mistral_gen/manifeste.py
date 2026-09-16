"""MANIFESTE.json : empreintes, comptages, graine, version du générateur."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import __version__

ATTRIBUTION = (
    "Données de calibration issues des jeux SCADA Kelmarsh et Penmanshiel, "
    "publiés par Cubico Sustainable Investments Ltd sous licence CC-BY-4.0."
)


def sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def ecrire_manifeste(sortie: Path, graine: int, comptages: dict,
                     fichiers: list[str]) -> dict:
    manifeste = {
        "generateur": {"nom": "mistral-gen", "version": __version__},
        "graine": graine,
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attribution": ATTRIBUTION,
        "comptages": comptages,
        "empreintes_sha256": {
            nom: sha256_fichier(sortie / nom)
            for nom in fichiers if (sortie / nom).exists()
        },
    }
    (sortie / "MANIFESTE.json").write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n")
    return manifeste
