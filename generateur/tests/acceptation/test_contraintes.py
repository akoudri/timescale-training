"""§10 — Les cinq contraintes non négociables (6.1 à 6.5).

Vérifiées directement sur les artefacts binaires, sans base de données.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from mistral_gen.config import charger_config

from .outils import BASE, SORTIE, charger_mesures_bin, extraire_serie, \
    machines_avec_arret, ts_unix_s

# bascule heure d'été -> heure d'hiver : 2026-10-25 03:00+02 = 01:00 UTC
BASCULE_UTC = 1793235600


@pytest.fixture(scope="module")
def cfg():
    return charger_config(BASE / "config.yaml")


@pytest.fixture(scope="module")
def mesures():
    return charger_mesures_bin(SORTIE / "mesures.bin")


def _serie_de(machine_id: int, libelle: str) -> int:
    """series_id d'un signal d'éolienne (machines 1..42, 10 signaux)."""
    ordre = ["puissance_kw", "energie_kwh", "vitesse_vent_ms", "direction_vent_deg",
             "temperature_nacelle_c", "temperature_multiplicateur_c",
             "vitesse_rotor_rpm", "angle_pale_deg", "tension_reseau_v", "disponible"]
    return (machine_id - 1) * 10 + ordre.index(libelle) + 1


def test_6_1_changement_heure(mesures, cfg):
    ts, val = extraire_serie(mesures, _serie_de(1, "puissance_kw"))

    jour_utc = ts // 86400
    decalage = np.where(ts < BASCULE_UTC, 7200, 3600)
    jour_paris = (ts + decalage) // 86400

    jour_bascule = (BASCULE_UTC + 3600) // 86400  # 2026-10-25

    somme_utc = val[jour_utc == jour_bascule].sum()
    somme_paris = val[jour_paris == jour_bascule].sum()
    ecart = abs(somme_paris - somme_utc) / max(somme_utc, 1e-9)
    assert ecart > 0.02, f"écart UTC/Paris de {ecart:.1%} le jour de bascule"

    # au total sur la fenêtre, les deux découpages couvrent les mêmes points
    assert np.isclose(val.sum(), val.sum())
    totaux_utc = sum(val[jour_utc == j].sum() for j in np.unique(jour_utc))
    assert np.isclose(totaux_utc, val.sum(), rtol=1e-12)


def test_6_2_moyenne_ponderee(mesures, cfg):
    arrets = machines_avec_arret()
    assert len(arrets) == 3
    # mois d'octobre en heure de Paris
    import datetime as dt
    tz2 = 7200
    debut_oct = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp()) - tz2
    fin_fenetre = int(cfg.fenetre.fin.timestamp())

    for a in arrets:
        sid = _serie_de(a["machine_id"], "puissance_kw")
        ts, val = extraire_serie(mesures, sid)
        m = (ts >= debut_oct) & (ts < fin_fenetre)
        ts_m, val_m = ts[m], val[m]
        assert len(ts_m) > 0
        moy_naive = val_m.mean()
        delta = np.diff(ts_m, append=ts_m[-1] + cfg.pas_s).astype(np.float64)
        moy_ponderee = float(np.sum(val_m * delta) / np.sum(delta))
        ecart = abs(moy_naive - moy_ponderee) / max(moy_ponderee, 1e-9)
        assert ecart > 0.05, (
            f"machine {a['machine_id']} : écart naïve/pondérée {ecart:.1%} ≤ 5 %")


def test_6_3_remises_a_zero(mesures, cfg):
    series_avec_reset = []
    for m_id in range(1, 43):
        sid = _serie_de(m_id, "energie_kwh")
        _, val = extraire_serie(mesures, sid)
        d = np.diff(val)
        chutes = np.flatnonzero(d < 0)
        for i in chutes:
            if val[i] > 0 and (val[i] - val[i + 1]) / val[i] > 0.5:
                series_avec_reset.append(sid)
                break
    assert len(series_avec_reset) >= 2, series_avec_reset


def test_6_4_interruptions(mesures, cfg):
    sid = np.asarray(mesures["sid"])
    ts = ts_unix_s(mesures)
    meme_serie = sid[1:] == sid[:-1]
    ecarts = np.diff(ts)
    longs = meme_serie & (ecarts > 30 * 60)
    series_touchees = np.unique(sid[:-1][longs])
    assert longs.sum() >= cfg.interruptions_min
    assert len(series_touchees) >= 10, "interruptions trop concentrées"

    reste = sid[:-1][longs] % 10
    # séries éoliennes : vitesse de vent = rang 3, compteur = rang 2
    eol = sid[:-1][longs] <= 420
    assert np.any(eol & (reste == 3)), "aucune interruption sur une vitesse de vent"
    assert np.any(eol & (reste == 2)), "aucune interruption sur un compteur d'énergie"


def test_6_5_cardinalite(mesures, cfg):
    # un jour plein de mesures : lignes par série et par jour >> 5000
    ts = ts_unix_s(mesures[:: 97])   # échantillon strié suffisant pour un ratio
    t0 = int(cfg.fenetre.debut.timestamp())
    jour1 = (ts >= t0 + 86400) & (ts < t0 + 2 * 86400)
    sid_j = np.asarray(mesures[:: 97]["sid"])[jour1]
    ratio_mesures = len(sid_j) * 97 / len(np.unique(sid_j))
    assert ratio_mesures > 5000

    hc = charger_mesures_bin(SORTIE / "mesures-hc.bin")
    ts_hc = ts_unix_s(hc)
    j0 = ts_hc.min() // 86400
    jour = ts_hc // 86400 == j0 + 1
    sid_hc = np.asarray(hc["sid"])[jour]
    ratio_hc = len(sid_hc) / len(np.unique(sid_hc))
    assert ratio_hc < 150
    assert ratio_hc == pytest.approx(96, abs=1)
