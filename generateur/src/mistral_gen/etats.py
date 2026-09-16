"""États opérationnels des machines et table `evenements`.

Chaque machine porte une séquence d'états continue (production | arret |
maintenance) couvrant exactement la fenêtre : à tout instant l'état est
déterminé, la somme des durées d'état vaut la durée de la fenêtre
(vérifié par un atelier de la formation avec `state_agg`).

Trois éoliennes (contrainte 6.2) subissent un arrêt de maintenance long
(42-48 h) pendant lequel l'échantillonnage des mesures passera au pas
horaire ; la liste est exportée dans `machines-avec-arret.json`.

La table `evenements` (~700 000 lignes) mélange les transitions d'état,
les bulletins de maintenance et un fond d'alarmes concentré autour des
transitions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .config import Config
from .referentiel import Referentiel
from .rng import rng_pour

ETATS = ("production", "arret", "maintenance")

# petit catalogue d'alarmes plausible (code, libellé, familles concernées)
ALARMES = [
    (1005, "Vent inferieur au seuil de demarrage", "eolienne"),
    (1012, "Rafale detectee, repli aerodynamique", "eolienne"),
    (2103, "Temperature multiplicateur elevee", "eolienne"),
    (2118, "Vibration nacelle hors gabarit", "eolienne"),
    (3021, "Ecart de tension reseau", "eolienne"),
    (3044, "Convertisseur : limitation thermique", "eolienne"),
    (4201, "Onduleur : derating temperature", "pv"),
    (4215, "Isolement DC degrade", "pv"),
    (4302, "Chaine PV deconnectee", "pv"),
    (5101, "Depassement seuil reactif", "pdl"),
    (5110, "Creux de tension detecte", "pdl"),
]


@dataclass(frozen=True)
class ArretImpose:
    machine_id: int
    debut_i: int    # indice de point (pas de 10 s)
    fin_i: int


@dataclass
class Etats:
    # par machine : liste de (etat, i0, i1) en indices de points, i1 exclu,
    # couvrant [0, n_points) sans trou ni chevauchement
    segments: dict[int, list[tuple[str, int, int]]]
    arrets_imposes: list[ArretImpose]
    evenements: list[tuple[int, int, str, int, str]]  # (ts_unix_s, machine_id, type, code, attributs_json)

    def machines_avec_arret_json(self, cfg: Config) -> str:
        t0 = int(cfg.fenetre.debut.timestamp())
        pas = cfg.pas_s
        donnees = [
            {
                "machine_id": a.machine_id,
                "debut": _iso(t0 + a.debut_i * pas),
                "fin": _iso(t0 + a.fin_i * pas),
                "pas_pendant_arret_s": 3600,
            }
            for a in self.arrets_imposes
        ]
        return json.dumps(donnees, indent=2) + "\n"


def _iso(ts_unix: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts_unix, tz=timezone.utc).isoformat()


def _sequence_machine(
    rng: np.random.Generator,
    n_points: int,
    pas_s: int,
    params: dict,
) -> list[tuple[str, int, int]]:
    """Processus de renouvellement : production entrecoupée d'arrêts calibrés."""
    d = params["disponibilite"]
    arrets_par_s = d["arrets_par_jour_machine"] / 86400.0
    mu, sigma = d["duree_arret_lognorm_mu"], d["duree_arret_lognorm_sigma"]

    segments: list[tuple[str, int, int]] = []
    i = 0
    # la machine peut commencer à l'arrêt (rare)
    if rng.random() < 0.02:
        duree_i = max(1, int(rng.lognormal(mu, sigma) / pas_s))
        fin = min(n_points, duree_i)
        segments.append(("arret", 0, fin))
        i = fin
    while i < n_points:
        duree_prod_s = rng.exponential(1.0 / arrets_par_s)
        fin_prod = min(n_points, i + max(1, int(duree_prod_s / pas_s)))
        segments.append(("production", i, fin_prod))
        i = fin_prod
        if i >= n_points:
            break
        etat = "maintenance" if rng.random() < 0.12 else "arret"
        duree_arret_s = float(np.clip(rng.lognormal(mu, sigma), 60, 3 * 86400))
        fin_arret = min(n_points, i + max(1, int(duree_arret_s / pas_s)))
        segments.append((etat, i, fin_arret))
        i = fin_arret
    return segments


def _imposer_maintenance(
    segments: list[tuple[str, int, int]], debut_i: int, fin_i: int
) -> list[tuple[str, int, int]]:
    """Insère un segment maintenance [debut_i, fin_i) en découpant l'existant."""
    resultat = []
    for etat, i0, i1 in segments:
        if i1 <= debut_i or i0 >= fin_i:
            resultat.append((etat, i0, i1))
            continue
        if i0 < debut_i:
            resultat.append((etat, i0, debut_i))
        if i1 > fin_i:
            resultat.append((etat, fin_i, i1))
    resultat.append(("maintenance", debut_i, fin_i))
    resultat.sort(key=lambda s: s[1])
    # fusionner les segments contigus de même état
    fusionne: list[tuple[str, int, int]] = []
    for seg in resultat:
        if fusionne and fusionne[-1][0] == seg[0] and fusionne[-1][2] == seg[1]:
            fusionne[-1] = (seg[0], fusionne[-1][1], seg[2])
        else:
            fusionne.append(seg)
    return [tuple(s) for s in fusionne]


def generer_etats(cfg: Config, params: dict, ref: Referentiel) -> Etats:
    n_points = cfg.points_par_jour * cfg.fenetre.jours
    pas = cfg.pas_s
    t0 = int(cfg.fenetre.debut.timestamp())

    # --- choix des 3 machines à arrêt imposé (une par site éolien) ----------
    rng_choix = rng_pour(cfg.graine, "arrets-imposes")
    arrets_imposes: list[ArretImpose] = []
    lo_h, hi_h = cfg.arret_duree_heures
    eoliennes_par_site: dict[int, list[int]] = {}
    for m_id, site_id, type_m, *_ in ref.actifs:
        if type_m == "eolienne":
            eoliennes_par_site.setdefault(site_id, []).append(m_id)
    # arrêts placés en octobre (mois de la démonstration L06), espacés,
    # loin des jours 1-5 (mesures-avant) et du changement d'heure
    jours_debut = [18, 22, 26]  # jours de fenêtre = 3, 7 et 11 octobre
    for rang, site_id in enumerate(sorted(eoliennes_par_site)[: cfg.machines_avec_arret]):
        machines = eoliennes_par_site[site_id]
        m_id = machines[int(rng_choix.integers(0, len(machines)))]
        duree_h = float(rng_choix.uniform(lo_h, hi_h))
        debut_i = jours_debut[rang % len(jours_debut)] * cfg.points_par_jour \
            + int(rng_choix.integers(0, cfg.points_par_jour // 4))
        fin_i = min(n_points, debut_i + int(duree_h * 3600 / pas))
        arrets_imposes.append(ArretImpose(m_id, debut_i, fin_i))

    # --- séquences d'états ---------------------------------------------------
    segments: dict[int, list[tuple[str, int, int]]] = {}
    for m_id, site_id, type_m, *_ in ref.actifs:
        rng_m = rng_pour(cfg.graine, "etats", m_id)
        if type_m == "eolienne":
            seq = _sequence_machine(rng_m, n_points, pas, params)
        else:
            # PV et PDL : très disponibles, quelques arrêts brefs
            quasi_params = {
                "disponibilite": {
                    "arrets_par_jour_machine": 0.05,
                    "duree_arret_lognorm_mu": 7.0,
                    "duree_arret_lognorm_sigma": 0.8,
                }
            }
            seq = _sequence_machine(rng_m, n_points, pas, quasi_params)
        segments[m_id] = seq

    for a in arrets_imposes:
        segments[a.machine_id] = _imposer_maintenance(
            segments[a.machine_id], a.debut_i, a.fin_i)

    # --- événements ----------------------------------------------------------
    evenements: list[tuple[int, int, str, int, str]] = []
    for m_id, seq in segments.items():
        precedent = None
        for etat, i0, i1 in seq:
            ts = t0 + i0 * pas
            attrs = {"etat": etat}
            if precedent:
                attrs["precedent"] = precedent
            evenements.append((ts, m_id, "changement_etat",
                               100 + ETATS.index(etat), json.dumps(attrs)))
            if etat == "maintenance":
                evenements.append((ts, m_id, "maintenance", 900,
                                   json.dumps({"duree_prevue_h": round((i1 - i0) * pas / 3600, 1)})))
            elif etat == "arret":
                evenements.append((ts, m_id, "arret", 800,
                                   json.dumps({"duree_s": (i1 - i0) * pas})))
            precedent = etat

    # fond d'alarmes : volume cible ~700 000 lignes au total, tiré par
    # machine, aux deux tiers concentré autour des transitions d'état
    cible_alarmes = 700_000 - len(evenements)
    types_machine = {m[0]: m[2] for m in ref.actifs}
    poids = {m_id: (10.0 if types_machine[m_id] == "eolienne" else 2.0)
             for m_id in segments}
    total_poids = sum(poids.values())
    for m_id, seq in segments.items():
        rng_a = rng_pour(cfg.graine, "alarmes", m_id)
        n_alarmes = int(cible_alarmes * poids[m_id] / total_poids)
        catalogue = [a for a in ALARMES if a[2] == types_machine[m_id]]
        transitions = np.array([i0 for _, i0, _ in seq if i0 > 0], dtype=np.int64)

        n_pres = int(n_alarmes * 2 / 3) if len(transitions) else 0
        if n_pres:
            base = transitions[rng_a.integers(0, len(transitions), n_pres)]
            decal = rng_a.normal(0, 90, n_pres).astype(np.int64)  # ±15 min en points
            idx_pres = np.clip(base + decal, 0, n_points - 1)
        else:
            idx_pres = np.array([], dtype=np.int64)
        idx_fond = rng_a.integers(0, n_points, n_alarmes - n_pres)
        indices = np.concatenate([idx_pres, idx_fond])
        codes = rng_a.integers(0, len(catalogue), len(indices))
        gravites = rng_a.integers(1, 4, len(indices))
        for i, c, g in zip(indices.tolist(), codes.tolist(), gravites.tolist()):
            code, libelle, _ = catalogue[c]
            evenements.append((
                t0 + i * pas, m_id, "alarme", code,
                json.dumps({"libelle": libelle, "gravite": int(g)}),
            ))

    evenements.sort(key=lambda e: (e[0], e[1], e[3]))
    return Etats(segments, arrets_imposes, evenements)


def emettre_evenements_csv(etats: Etats, chemin) -> int:
    """CSV pour COPY : ts, machine_id, type, code, attributs (JSON)."""
    from datetime import datetime, timezone
    with open(chemin, "w", encoding="utf-8", newline="\n") as f:
        for ts, m_id, type_e, code, attrs in etats.evenements:
            iso = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00")
            attrs_csv = attrs.replace('"', '""')
            f.write(f'{iso},{m_id},{type_e},{code},"{attrs_csv}"\n')
    return len(etats.evenements)
