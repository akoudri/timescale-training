"""Étage 1 — calibration sur les jeux SCADA réels (Kelmarsh, Zenodo).

Lit les CSV 10 minutes des 6 éoliennes Senvion MM92 (année 2020) et le
fichier d'événements (Status), en extrait les paramètres statistiques de
la fiche §4, et écrit `params.json`.

Exécuté une seule fois ; le résultat est versionné. Les CSV sources ne
le sont pas.

Attribution : données SCADA Kelmarsh publiées par Cubico Sustainable
Investments Ltd sous licence CC-BY-4.0 (DOI 10.5281/zenodo.8252025).
"""

from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

COLONNES = {
    "ts": "Date and time",
    "vent": "Wind speed (m/s)",
    "direction": "Wind direction (°)",
    "puissance": "Power (kW)",
    "compteur": "Energy Export counter (kWh)",
    "rotor": "Rotor speed (RPM)",
    "pale": "Blade angle (pitch position) A (°)",
    "t_nacelle": "Nacelle ambient temperature (°C)",
    "t_multiplicateur": "Gear oil temperature (°C)",
    "tension": "Grid voltage (V)",
}

PAS_SOURCE_S = 600  # SCADA 10 minutes


def _lire_turbine(flux: io.TextIOWrapper) -> dict[str, np.ndarray]:
    lecteur = csv.reader(flux)
    entete = None
    for ligne in lecteur:
        if ligne and ligne[0].startswith("# Date and time"):
            ligne[0] = ligne[0].lstrip("# ")
            entete = ligne
            break
    if entete is None:
        raise ValueError("en-tête introuvable dans le CSV turbine")
    idx = {cle: entete.index(nom) for cle, nom in COLONNES.items()}

    brut: dict[str, list] = {cle: [] for cle in COLONNES}
    for ligne in lecteur:
        if not ligne or ligne[0].startswith("#"):
            continue
        for cle, i in idx.items():
            brut[cle].append(ligne[i])

    ts = np.array(
        [datetime.strptime(v, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
         for v in brut["ts"]],
        dtype=np.float64,
    )
    resultat = {"ts": ts}
    for cle in COLONNES:
        if cle == "ts":
            continue
        col = np.array([float(v) if v not in ("", "-") else np.nan for v in brut[cle]])
        resultat[cle] = col
    return resultat


def _intervalles_arret(flux: io.TextIOWrapper) -> list[tuple[float, float]]:
    """Périodes non nominales depuis le fichier Status (catégorie IEC)."""
    lecteur = csv.reader(flux)
    entete = None
    for ligne in lecteur:
        if ligne and ligne[0].lstrip("# ").startswith("Timestamp start"):
            ligne[0] = ligne[0].lstrip("# ")
            entete = ligne
            break
    if entete is None:
        raise ValueError("en-tête introuvable dans le CSV status")
    i_debut = entete.index("Timestamp start")
    i_fin = entete.index("Timestamp end")
    i_cat = entete.index("IEC category")

    intervalles = []
    for ligne in lecteur:
        if not ligne or ligne[0].startswith("#") or len(ligne) <= i_cat:
            continue
        cat = ligne[i_cat].strip()
        fin = ligne[i_fin].strip()
        if cat in ("Full Performance", "") or fin in ("", "-"):
            continue
        try:
            t0 = datetime.strptime(ligne[i_debut], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            t1 = datetime.strptime(fin, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
        if t1 > t0:
            intervalles.append((t0, t1))
    return intervalles


def _masque_arret(ts: np.ndarray, intervalles: list[tuple[float, float]]) -> np.ndarray:
    masque = np.zeros(len(ts), dtype=bool)
    if not intervalles:
        return masque
    debuts = np.array([i[0] for i in intervalles])
    fins = np.array([i[1] for i in intervalles])
    ordre = np.argsort(debuts)
    debuts, fins = debuts[ordre], fins[ordre]
    # un pas de 10 min est « à l'arrêt » si son intervalle recouvre un arrêt
    for d, f in zip(debuts, fins):
        masque |= (ts < f) & (ts + PAS_SOURCE_S > d)
    return masque


def _ajuster_weibull(v: np.ndarray) -> tuple[float, float]:
    """Méthode des moments : k depuis le coefficient de variation, puis λ."""
    v = v[np.isfinite(v) & (v >= 0)]
    m, s = float(np.mean(v)), float(np.std(v))
    cv = s / m
    # résolution de cv(k) par dichotomie sur k ∈ [0.5, 10]
    def cv_theorique(k):
        g1 = math.gamma(1 + 1 / k)
        g2 = math.gamma(1 + 2 / k)
        return math.sqrt(max(g2 - g1 * g1, 1e-12)) / g1
    lo, hi = 0.5, 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if cv_theorique(mid) > cv:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    lam = m / math.gamma(1 + 1 / k)
    return k, lam


def _autocorrelation(x: np.ndarray, decalage: int = 1) -> float:
    x = x[np.isfinite(x)]
    x = x - x.mean()
    num = float(np.dot(x[:-decalage], x[decalage:]))
    den = float(np.dot(x, x))
    return num / den


def _constante_temps(temp: np.ndarray) -> float:
    """Constante de temps (s) estimée par décroissance de l'autocorrélation
    à 1 h de décalage (le pas 10 min est trop court, ρ1 y est ≈ 1) :
    τ = -3600 / ln(ρ6)."""
    rho = _autocorrelation(temp[np.isfinite(temp)], decalage=6)
    rho = min(max(rho, 1e-6), 0.999999)
    return -3600.0 / math.log(rho)


def calibrer(dossier_sources: Path, sortie: Path) -> dict:
    zip_scada = dossier_sources / "Kelmarsh_SCADA_2020.zip"
    statique = dossier_sources / "Kelmarsh_WT_static.csv"

    # --- référentiel machine -------------------------------------------------
    ref = {}
    with open(statique, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f))
    l0 = lignes[0]
    ref = {
        "modele": f"{l0['Manufacturer']} {l0['Model']}",
        "puissance_nominale_kw": float(l0["Rated power (kW)"]),
        "diametre_rotor_m": float(l0["Rotor Diameter (m)"]),
        "hauteur_moyeu_m": float(l0["Hub Height (m)"]),
    }

    # --- agrégats sur les 6 turbines ----------------------------------------
    vents, puissances, arrets_masques = [], [], []
    durees_arret, trous_durees = [], []
    autocorrs, rotor_vent = [], []
    t_nacelle_tout, t_mult_tout, p_tout = [], [], []
    tensions, disponibilites = [], []
    heures_totales = 0.0

    with zipfile.ZipFile(zip_scada) as z:
        noms = sorted(z.namelist())
        turbines = [n for n in noms if n.startswith("Turbine_Data")]
        statuts = {n.split("Kelmarsh_")[1].split("_")[0]: n
                   for n in noms if n.startswith("Status")}
        for nom in turbines:
            numero = nom.split("Kelmarsh_")[1].split("_")[0]
            with z.open(nom) as f:
                d = _lire_turbine(io.TextIOWrapper(f, encoding="utf-8-sig"))
            with z.open(statuts[numero]) as f:
                inter = _intervalles_arret(io.TextIOWrapper(f, encoding="utf-8-sig"))

            arret = _masque_arret(d["ts"], inter)
            fini = np.isfinite(d["vent"]) & np.isfinite(d["puissance"])

            vents.append(d["vent"][fini])
            puissances.append(d["puissance"][fini])
            arrets_masques.append(arret[fini])

            durees_arret.extend([f - dbt for dbt, f in inter])
            heures_totales += (d["ts"][-1] - d["ts"][0]) / 3600
            disponibilites.append(1.0 - arret.mean())

            # trous de collecte : l'export Greenbyte matérialise la grille
            # complète, un trou est une suite de lignes entièrement NaN
            absent = ~np.isfinite(d["vent"]) & ~np.isfinite(d["puissance"])
            if absent.any():
                bords_runs = np.diff(absent.astype(np.int8))
                debuts_r = np.flatnonzero(bords_runs == 1) + 1
                fins_r = np.flatnonzero(bords_runs == -1) + 1
                if absent[0]:
                    debuts_r = np.r_[0, debuts_r]
                if absent[-1]:
                    fins_r = np.r_[fins_r, len(absent)]
                for dr, fr in zip(debuts_r, fins_r):
                    duree = (fr - dr) * PAS_SOURCE_S
                    if duree >= PAS_SOURCE_S * 2:
                        trous_durees.append(duree)

            v_ok = d["vent"][np.isfinite(d["vent"])]
            autocorrs.append(_autocorrelation(d["vent"][np.isfinite(d["vent"])]))

            ok = fini & ~arret
            rotor_ok = np.isfinite(d["rotor"]) & ok
            rotor_vent.append((d["vent"][rotor_ok], d["rotor"][rotor_ok]))

            tn = np.isfinite(d["t_nacelle"])
            tm = np.isfinite(d["t_multiplicateur"]) & np.isfinite(d["puissance"])
            t_nacelle_tout.append(d["t_nacelle"][tn])
            t_mult_tout.append(d["t_multiplicateur"][tm])
            p_tout.append(d["puissance"][tm])
            tensions.append(d["tension"][np.isfinite(d["tension"])])

    vent = np.concatenate(vents)
    puissance = np.concatenate(puissances)
    arret = np.concatenate(arrets_masques)

    # --- courbe de puissance (hors arrêts, hors puissances négatives) --------
    exploitable = ~arret & (puissance > -50)
    v_e, p_e = vent[exploitable], puissance[exploitable]
    # retirer aussi les bridages manifestes : P quasi nulle par vent > 5 m/s
    bride = (p_e < 10) & (v_e > 5)
    v_e, p_e = v_e[~bride], p_e[~bride]

    pas = 0.5
    bords = np.arange(0, 30 + pas, pas)
    centres = (bords[:-1] + bords[1:]) / 2
    courbe = []
    for i in range(len(centres)):
        m = (v_e >= bords[i]) & (v_e < bords[i + 1])
        if m.sum() < 20:
            continue
        p_bin = p_e[m]
        courbe.append({
            "vitesse_ms": round(float(centres[i]), 2),
            "mediane_kw": round(float(np.median(p_bin)), 1),
            "sigma_kw": round(float(np.std(p_bin)), 1),
            "q10_kw": round(float(np.quantile(p_bin, 0.10)), 1),
            "q90_kw": round(float(np.quantile(p_bin, 0.90)), 1),
            "n": int(m.sum()),
        })

    k, lam = _ajuster_weibull(vent[~arret])

    # --- relation rotor / vent (moyenne par bin, pour vitesse_rotor_rpm) -----
    rv = np.concatenate([r[0] for r in rotor_vent])
    rr = np.concatenate([r[1] for r in rotor_vent])
    rotor_courbe = []
    for i in range(len(centres)):
        m = (rv >= bords[i]) & (rv < bords[i + 1])
        if m.sum() < 20:
            continue
        rotor_courbe.append({
            "vitesse_ms": round(float(centres[i]), 2),
            "rpm": round(float(np.median(rr[m])), 2),
        })

    # --- températures --------------------------------------------------------
    t_mult = np.concatenate(t_mult_tout)
    p_temp = np.concatenate(p_tout)
    a, b = np.polyfit(p_temp, t_mult, 1)
    t_nac = np.concatenate(t_nacelle_tout)
    tau_mult = _constante_temps(t_mult)

    # --- arrêts : ajustement log-normal des durées ---------------------------
    da = np.array([x for x in durees_arret if 60 <= x <= 30 * 86400])
    log_da = np.log(da)

    # --- trous de collecte ---------------------------------------------------
    trous = np.array(trous_durees)
    freq_trous_par_jour = len(trous) / (heures_totales / 24)
    log_trous = np.log(trous) if len(trous) else np.array([math.log(3600)])

    tension = np.concatenate(tensions)
    tension = tension[(tension > 100)]  # écarte les zéros d'arrêt

    params = {
        "_attribution": (
            "Données de calibration issues du jeu SCADA Kelmarsh, publié par "
            "Cubico Sustainable Investments Ltd sous licence CC-BY-4.0 "
            "(DOI 10.5281/zenodo.8252025), année 2020, 6 éoliennes Senvion MM92."
        ),
        "_extraction": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "referentiel": ref,
        "courbe_puissance": courbe,
        "vent": {
            "weibull_k": round(k, 4),
            "weibull_lambda_ms": round(lam, 4),
            "autocorrelation_10min": round(float(np.mean(autocorrs)), 4),
            "moyenne_ms": round(float(np.mean(vent[~arret])), 3),
        },
        "rotor": rotor_courbe,
        "disponibilite": {
            "taux_moyen": round(float(np.mean(disponibilites)), 4),
            "arrets_par_jour_machine": round(len(da) / (heures_totales / 24), 3),
            "duree_arret_lognorm_mu": round(float(np.mean(log_da)), 4),
            "duree_arret_lognorm_sigma": round(float(np.std(log_da)), 4),
        },
        "interruptions_collecte": {
            "par_jour_machine": round(float(freq_trous_par_jour), 4),
            "duree_lognorm_mu": round(float(np.mean(log_trous)), 4),
            "duree_lognorm_sigma": round(float(np.std(log_trous)) or 0.5, 4),
        },
        "temperatures": {
            "nacelle_moyenne_c": round(float(np.mean(t_nac)), 2),
            "nacelle_sigma_c": round(float(np.std(t_nac)), 2),
            "multiplicateur_base_c": round(float(a * 0 + b), 2),
            "multiplicateur_pente_c_par_kw": round(float(a), 6),
            "constante_temps_s": round(float(min(max(tau_mult, 600), 4 * 3600)), 1),
        },
        "tension": {
            "moyenne_v": round(float(np.mean(tension)), 1),
            "sigma_v": round(float(np.std(tension)), 2),
        },
    }

    sortie.write_text(json.dumps(params, ensure_ascii=False, indent=2) + "\n")
    return params


def main():
    base = Path(__file__).resolve().parents[2]
    params = calibrer(base / "calibration-sources", base / "params.json")
    print(f"params.json écrit : {len(params['courbe_puissance'])} points de courbe, "
          f"Weibull k={params['vent']['weibull_k']} λ={params['vent']['weibull_lambda_ms']}, "
          f"autocorr 10 min = {params['vent']['autocorrelation_10min']}")


if __name__ == "__main__":
    main()
