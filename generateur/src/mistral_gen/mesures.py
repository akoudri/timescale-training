"""Assemblage de la table `mesures` : 490 séries × 45 jours à 0,1 Hz.

Applique les trois contraintes de génération :
- 6.2 — pendant les trois arrêts de maintenance imposés, toutes les séries
  de la machine passent du pas 10 s au pas horaire ;
- 6.3 — deux compteurs `energie_kwh` repartent de zéro en cours de fenêtre ;
- 6.4 — interruptions de collecte : 24 trous imposés de plus de 30 min
  (dont un sur une vitesse de vent et un sur un compteur), plus des trous
  « naturels » à la fréquence calibrée.

Les cinq premiers jours restent intacts (aucun trou, aucun arrêt imposé) :
ils forment `mesures-avant`, dont le comptage doit être exact.

Écrit `mesures.bin` (COPY binaire) en flux, machine par machine, sans
jamais matérialiser les 190 M lignes en mémoire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .config import Config
from .copybin import CopyBinaryWriter
from .eolienne import synthese_eolienne
from .etats import Etats
from .pdl import synthese_pdl
from .pv import synthese_pv
from .referentiel import Referentiel, Serie
from .rng import rng_pour

JOURS_PROTEGES = 5          # mesures-avant : aucun retrait sur ces jours
PAS_ARRET_S = 3600          # pas d'échantillonnage pendant un arrêt imposé
QUALITE_FENETRE_PTS = 60    # ±10 min autour d'une transition d'état


@dataclass
class Scenario:
    """Décisions déterministes des contraintes 6.3 et 6.4."""
    resets: dict[int, int]                       # machine_id -> indice de remise à zéro
    trous: dict[int, list[tuple[int, int]]]      # series_id -> [(i0, i1)]


@dataclass
class StatsMesures:
    lignes: int = 0
    retirees_arrets: int = 0
    retirees_trous: int = 0
    lignes_avant: int = 0
    par_famille: dict = field(default_factory=dict)


def construire_scenario(cfg: Config, params: dict, ref: Referentiel,
                        etats: Etats) -> Scenario:
    n = cfg.points_par_jour * cfg.fenetre.jours
    ppj = cfg.points_par_jour
    rng = rng_pour(cfg.graine, "scenario")

    machines_arret = {a.machine_id for a in etats.arrets_imposes}

    # --- 6.3 : deux remises à zéro de compteur -------------------------------
    candidates = [m[0] for m in ref.machines("eolienne") if m[0] not in machines_arret]
    choix = rng.choice(len(candidates), size=cfg.remises_a_zero_compteur, replace=False)
    resets = {}
    jours_reset = (25, 33)
    for rang, c in enumerate(sorted(choix.tolist())):
        m_id = candidates[c]
        i = jours_reset[rang % len(jours_reset)] * ppj + int(rng.integers(0, ppj))
        resets[m_id] = i

    # --- 6.4 : trous imposés -------------------------------------------------
    series_vent = [s for s in ref.series if s.libelle == "vitesse_vent_ms"]
    series_compteur = [s for s in ref.series if s.libelle == "energie_kwh"]
    autres = [s for s in ref.series
              if s.libelle not in ("vitesse_vent_ms", "energie_kwh")]

    imposes: list[Serie] = [
        series_vent[int(rng.integers(0, len(series_vent)))],
        series_compteur[int(rng.integers(0, len(series_compteur)))],
    ]
    idx_autres = rng.choice(len(autres), size=cfg.interruptions_total - 2, replace=False)
    imposes.extend(autres[i] for i in idx_autres.tolist())

    trous: dict[int, list[tuple[int, int]]] = {}
    for s in imposes:
        duree_s = float(rng.uniform(35 * 60, 8 * 3600))
        debut_i = int(rng.integers(JOURS_PROTEGES * ppj, n - int(duree_s / cfg.pas_s) - 1))
        fin_i = debut_i + max(1, int(duree_s / cfg.pas_s))
        trous.setdefault(s.series_id, []).append((debut_i, fin_i))

    # --- trous naturels, à la fréquence calibrée (rabotée par série) ---------
    ic = params["interruptions_collecte"]
    taux_serie_jour = ic["par_jour_machine"] / 20.0
    esperance = taux_serie_jour * (cfg.fenetre.jours - JOURS_PROTEGES)
    mu, sigma = ic["duree_lognorm_mu"], ic["duree_lognorm_sigma"]
    for s in ref.series:
        rng_s = rng_pour(cfg.graine, "trous-naturels", s.series_id)
        n_trous = int(rng_s.poisson(esperance))
        for _ in range(n_trous):
            duree_s = float(np.clip(rng_s.lognormal(mu, sigma), 120, 6 * 3600))
            debut_i = int(rng_s.integers(JOURS_PROTEGES * ppj, n - 2))
            fin_i = min(n, debut_i + max(1, int(duree_s / cfg.pas_s)))
            trous.setdefault(s.series_id, []).append((debut_i, fin_i))

    return Scenario(resets=resets, trous=trous)


def _masque_serie(
    cfg: Config,
    n: int,
    machine_arret: tuple[int, int] | None,
    trous_serie: list[tuple[int, int]],
) -> tuple[np.ndarray, int, int]:
    """Masque des points conservés + comptages retirés (arrêt, trous)."""
    garde = np.ones(n, dtype=bool)
    ret_arret = 0
    if machine_arret is not None:
        i0, i1 = machine_arret
        ratio = PAS_ARRET_S // cfg.pas_s
        zone = np.arange(i0, i1)
        garde[zone] = (zone - i0) % ratio == 0
        ret_arret = int((~garde[i0:i1]).sum())
    avant = int(garde.sum())
    for i0, i1 in trous_serie:
        garde[i0:i1] = False
    ret_trous = avant - int(garde.sum())
    return garde, ret_arret, ret_trous


def _qualite_serie(
    rng: np.random.Generator,
    n: int,
    transitions: np.ndarray,
) -> np.ndarray:
    """~2 % de lignes non nominales, concentrées autour des transitions."""
    q = np.zeros(n, dtype=np.int16)
    if len(transitions):
        for t in transitions:
            i0 = max(0, t - QUALITE_FENETRE_PTS)
            i1 = min(n, t + QUALITE_FENETRE_PTS)
            q[i0:i1] = 1
        substituees = transitions[rng.random(len(transitions)) < 0.3]
        for t in substituees:
            q[max(0, t - 6):min(n, t + 6)] = 2
    # épisodes dégradés diffus (~1 %)
    n_episodes = max(1, int(n / 86_400))         # ~4-5 épisodes de 10 min / 45 j
    for _ in range(n_episodes * 9):
        i0 = int(rng.integers(0, n - 60))
        q[i0:i0 + 60] = np.maximum(q[i0:i0 + 60], 1)
    return q


def generer_mesures(
    cfg: Config,
    params: dict,
    ref: Referentiel,
    etats: Etats,
    scenario: Scenario,
    sortie: Path,
) -> StatsMesures:
    from .vent import ChampsSite

    n = cfg.points_par_jour * cfg.fenetre.jours
    ppj = cfg.points_par_jour
    t0_us = int(cfg.fenetre.debut.timestamp()) * 1_000_000
    pas_us = cfg.pas_s * 1_000_000

    champs = ChampsSite(cfg, params)
    stats = StatsMesures()
    arrets_par_machine = {a.machine_id: (a.debut_i, a.fin_i)
                          for a in etats.arrets_imposes}
    sites = {s[0]: s for s in ref.sites}
    series_par_machine = ref.series_par_machine

    somme_productions = np.zeros(n, dtype=np.float64)

    sortie.mkdir(parents=True, exist_ok=True)
    w = CopyBinaryWriter(sortie / "mesures.bin")
    w_avant = CopyBinaryWriter(sortie / "mesures-avant.bin")
    n_avant = JOURS_PROTEGES * ppj

    indices_tout = np.arange(n, dtype=np.int64)

    def ecrire_serie(serie: Serie, valeurs: np.ndarray,
                     transitions: np.ndarray) -> None:
        machine_arret = arrets_par_machine.get(serie.machine_id)
        trous_serie = scenario.trous.get(serie.series_id, [])
        garde, ret_a, ret_t = _masque_serie(cfg, n, machine_arret, trous_serie)
        rng_q = rng_pour(cfg.graine, "qualite", serie.series_id)
        qualite = _qualite_serie(rng_q, n, transitions)

        idx = indices_tout[garde]
        ts_us = t0_us + idx * pas_us
        sid = np.full(len(idx), serie.series_id, dtype=np.int32)
        val = valeurs[garde]
        q = qualite[garde]
        w.ecrire_bloc(ts_us, sid, val, q)

        m_avant = idx < n_avant
        w_avant.ecrire_bloc(ts_us[m_avant], sid[m_avant], val[m_avant], q[m_avant])

        stats.lignes += len(idx)
        stats.lignes_avant += int(m_avant.sum())
        stats.retirees_arrets += ret_a
        stats.retirees_trous += ret_t
        stats.par_famille[serie.famille] = stats.par_famille.get(serie.famille, 0) + len(idx)

    machines_pdl = []
    for m in ref.actifs:
        m_id, site_id, type_m = m[0], m[1], m[2]
        segments = etats.segments[m_id]
        transitions = np.array([i0 for _, i0, _ in segments if i0 > 0], dtype=np.int64)

        if type_m == "eolienne":
            signaux = synthese_eolienne(cfg, params, champs, m_id, site_id, segments)
            if m_id in scenario.resets:
                i_reset = scenario.resets[m_id]
                e = signaux["energie_kwh"]
                e[i_reset:] = e[i_reset:] - e[i_reset]
            somme_productions += signaux["puissance_kw"]
            for serie in series_par_machine[m_id]:
                ecrire_serie(serie, signaux[serie.libelle], transitions)

        elif type_m == "pv":
            site = sites[site_id]
            signaux_pv = synthese_pv(cfg, params, champs, m_id, site_id,
                                     site[3], site[4], segments)
            for onduleur in range(1, 5):
                somme_productions += signaux_pv[(onduleur, "puissance_ac_kw")]
            for serie in series_par_machine[m_id]:
                ecrire_serie(serie, signaux_pv[(serie.onduleur, serie.libelle)],
                             transitions)

        elif type_m == "pdl":
            machines_pdl.append((m, segments, transitions))

    for m, segments, transitions in machines_pdl:
        m_id = m[0]
        signaux = synthese_pdl(cfg, m_id, somme_productions)
        for serie in series_par_machine[m_id]:
            ecrire_serie(serie, signaux[serie.libelle], transitions)

    w.fermer()
    w_avant.fermer()

    (sortie / "machines-avec-arret.json").write_text(
        etats.machines_avec_arret_json(cfg))
    return stats
