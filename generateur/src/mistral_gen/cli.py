"""Point d'entrée du générateur MISTRAL.

    mistral-gen calibrer  [--config config.yaml]
    mistral-gen generer   [--config config.yaml]   # étage 2 : tous les artefacts fichiers
    mistral-gen dumps     [--config config.yaml]   # dumps PostgreSQL (docker requis)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .config import charger_config


def _base(chemin_config: str) -> Path:
    return Path(chemin_config).resolve().parent


def cmd_calibrer(args) -> int:
    from .calibration import calibrer
    base = _base(args.config)
    calibrer(base / "calibration-sources", base / "params.json")
    print("params.json écrit")
    return 0


def cmd_generer(args) -> int:
    from .etats import generer_etats, emettre_evenements_csv
    from .hc import generer_hc
    from .manifeste import ecrire_manifeste
    from .meteo import generer_meteo, emettre_meteo_csv
    from .mesures import construire_scenario, generer_mesures
    from .referentiel import construire_referentiel, emettre_sql
    from .vent import ChampsSite

    debut = time.monotonic()
    cfg = charger_config(args.config)
    params = json.loads((_base(args.config) / "params.json").read_text())
    sortie = cfg.sortie
    sortie.mkdir(parents=True, exist_ok=True)

    def top(msg):
        print(f"[{time.monotonic() - debut:6.1f}s] {msg}", flush=True)

    top("référentiel…")
    ref = construire_referentiel(cfg, params)
    (sortie / "referentiel.sql").write_text(emettre_sql(ref))

    top("états et événements…")
    etats = generer_etats(cfg, params, ref)
    n_ev = emettre_evenements_csv(etats, sortie / "evenements.csv")

    top("météo…")
    champs = ChampsSite(cfg, params)
    lignes_meteo = generer_meteo(cfg, params, ref, champs)
    n_meteo = emettre_meteo_csv(lignes_meteo, sortie / "meteo.csv")

    top("scénario des contraintes…")
    scenario = construire_scenario(cfg, params, ref, etats)

    top("mesures (190 M lignes)…")
    stats = generer_mesures(cfg, params, ref, etats, scenario, sortie)
    top(f"  mesures.bin : {stats.lignes:,} lignes "
        f"(arrêts -{stats.retirees_arrets:,}, trous -{stats.retirees_trous:,}) ; "
        f"mesures-avant.bin : {stats.lignes_avant:,}")

    top("haute cardinalité…")
    n_hc = generer_hc(cfg, sortie)
    top(f"  mesures-hc.bin : {n_hc:,} lignes")

    top("manifeste…")
    comptages = {
        "mesures": stats.lignes,
        "mesures_avant": stats.lignes_avant,
        "mesures_hc": n_hc,
        "evenements": n_ev,
        "meteo": n_meteo,
        "sites": len(ref.sites),
        "actifs": len(ref.actifs),
        "signaux": len(ref.signaux),
        "affectations": len(ref.affectations),
        "retirees_arrets_6_2": stats.retirees_arrets,
        "retirees_trous_6_4": stats.retirees_trous,
    }
    ecrire_manifeste(sortie, cfg.graine, comptages, [
        "mesures.bin", "mesures-avant.bin", "mesures-hc.bin",
        "referentiel.sql", "evenements.csv", "meteo.csv",
        "machines-avec-arret.json",
    ])
    top("terminé.")
    return 0


def cmd_dumps(args) -> int:
    from .dumps import construire_dumps
    cfg = charger_config(args.config)
    construire_dumps(cfg, _base(args.config))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mistral-gen")
    p.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "config.yaml"))
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("calibrer").set_defaults(fonc=cmd_calibrer)
    sous.add_parser("generer").set_defaults(fonc=cmd_generer)
    sous.add_parser("dumps").set_defaults(fonc=cmd_dumps)
    args = p.parse_args(argv)
    return args.fonc(args)


if __name__ == "__main__":
    sys.exit(main())
