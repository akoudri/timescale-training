# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "numpy>=1.26"]
# ///
"""Injecteur de charge MISTRAL (L04 / M05).

    uv run l04/injecteur.py --strategie unitaire --duree 60
    uv run l04/injecteur.py --strategie lots --taille-lot 1000 --duree 60
    uv run l04/injecteur.py --strategie copy --binaire --duree 60
    uv run l04/injecteur.py --strategie lots --debit-cible 50000 --duree 30
    uv run l04/injecteur.py --strategie lots --duree 60 --profil-retard mistral

Trois stratégies à durée fixe — on compare des lignes écrites, jamais des
durées totales. Le profil de retard « mistral » décale les horodatages
mesure (ts) par rapport à l'instant d'insertion (ingere_le) : sans lui, le
retard d'arrivée est mécaniquement nul et la valeur exportée vers M08 est
inutilisable.

Garde-fou : si le CPU du processus injecteur dépasse 80 %, l'injecteur le
signale — le point de rupture mesuré serait alors celui du client, pas de
la base.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import psycopg

DSN = os.environ.get(
    "MISTRAL_DSN", "host=127.0.0.1 port=6543 dbname=mistral user=postgres password=mistral")
SERIES = 490


def profil_mistral(rng: np.random.Generator, n: int) -> np.ndarray:
    """Retards d'arrivée (s) : majorité en quelques secondes, minorité de
    liaisons dégradées en minutes, et une reprise groupée après incident."""
    r = np.clip(rng.normal(2.0, 1.0, n), 0.2, None)
    degrades = rng.random(n) < 0.12
    r[degrades] = rng.lognormal(4.0, 0.8, degrades.sum())          # ~30-300 s
    reprise = rng.random(n) < 0.03
    r[reprise] = rng.uniform(600, 900, reprise.sum())              # incident collecteur
    return r


def generer_lot(rng, n, profil, t0):
    retards = profil_mistral(rng, n) if profil == "mistral" else np.zeros(n)
    ts = [t0 - timedelta(seconds=float(s)) for s in retards]
    series = rng.integers(1, SERIES + 1, n)
    valeurs = rng.normal(1000, 200, n)
    return list(zip(ts, series.tolist(), valeurs.tolist()))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategie", choices=["unitaire", "lots", "copy"], required=True)
    p.add_argument("--duree", type=float, default=60)
    p.add_argument("--taille-lot", type=int, default=1000)
    p.add_argument("--debit-cible", type=int, default=0, help="points/s, 0 = plein régime")
    p.add_argument("--profil-retard", choices=["aucun", "mistral"], default="aucun")
    p.add_argument("--graine", type=int, default=0)
    p.add_argument("--binaire", action="store_true", help="COPY au format binaire")
    p.add_argument("--on-conflict", choices=["erreur", "rien"], default="erreur")
    args = p.parse_args()

    rng = np.random.default_rng(args.graine or None)
    conflit = " ON CONFLICT (series_id, ts) DO NOTHING" if args.on_conflict == "rien" else ""

    lignes = 0
    latences: list[float] = []
    cpu0 = time.process_time()
    debut = time.monotonic()
    fin = debut + args.duree

    with psycopg.connect(DSN, autocommit=True) as conn:
        cur = conn.cursor()
        while time.monotonic() < fin:
            t0 = datetime.now(timezone.utc)
            if args.strategie == "unitaire":
                lot = generer_lot(rng, 1, args.profil_retard, t0)
                a = time.monotonic()
                cur.execute(
                    "INSERT INTO mesures_charge (ts, series_id, valeur) VALUES (%s,%s,%s)" + conflit,
                    lot[0])
                latences.append(time.monotonic() - a)
                lignes += 1
            elif args.strategie == "lots":
                lot = generer_lot(rng, args.taille_lot, args.profil_retard, t0)
                a = time.monotonic()
                cur.executemany(
                    "INSERT INTO mesures_charge (ts, series_id, valeur) VALUES (%s,%s,%s)" + conflit,
                    lot)
                latences.append(time.monotonic() - a)
                lignes += len(lot)
            else:  # copy
                lot = generer_lot(rng, max(args.taille_lot, 10_000), args.profil_retard, t0)
                a = time.monotonic()
                fmt = "(FORMAT BINARY)" if args.binaire else ""
                with cur.copy(f"COPY mesures_charge (ts, series_id, valeur) FROM STDIN {fmt}") as cp:
                    if args.binaire:
                        cp.set_types(["timestamptz", "int4", "float8"])
                    for ligne in lot:
                        cp.write_row(ligne)
                latences.append(time.monotonic() - a)
                lignes += len(lot)

            if args.debit_cible:
                attendu = lignes / args.debit_cible
                ecoule = time.monotonic() - debut
                if attendu > ecoule:
                    time.sleep(attendu - ecoule)

    duree = time.monotonic() - debut
    cpu_client = (time.process_time() - cpu0) / duree * 100
    resume = {
        "strategie": args.strategie + (" binaire" if args.binaire else ""),
        "duree_s": round(duree, 1),
        "lignes": lignes,
        "debit_points_s": round(lignes / duree),
        "latence_mediane_ms": round(statistics.median(latences) * 1000, 2),
        "cpu_client_pct": round(cpu_client, 1),
        "debit_cible": args.debit_cible or None,
        "profil_retard": args.profil_retard,
    }
    if cpu_client > 80:
        resume["avertissement"] = (
            "CPU client > 80 % : le point de rupture mesuré serait celui de "
            "l'injecteur, pas de la base — lancer deux injecteurs en parallèle")
    print(json.dumps(resume, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
