"""§10 — Volumétrie."""

from mistral_gen.config import charger_config

from .outils import BASE, SORTIE, charger_mesures_bin, manifeste


def test_mesures_volume_nominal_moins_les_retraits():
    m = manifeste()["comptages"]
    nominal = 490 * 8640 * 45
    assert nominal == 190_512_000
    retirees = m["retirees_arrets_6_2"] + m["retirees_trous_6_4"]
    assert m["mesures"] == nominal - retirees
    assert retirees / nominal < 0.005, "plus de 0,5 % de lignes retirées"
    # le fichier lui-même est cohérent avec le manifeste
    mm = charger_mesures_bin(SORTIE / "mesures.bin")
    assert len(mm) == m["mesures"]


def test_mesures_hc_exact():
    m = manifeste()["comptages"]
    assert m["mesures_hc"] == 20_000 * 96 * 7 == 13_440_000
    mm = charger_mesures_bin(SORTIE / "mesures-hc.bin")
    assert len(mm) == 13_440_000


def test_mesures_avant_exactement_5_jours():
    cfg = charger_config(BASE / "config.yaml")
    m = manifeste()["comptages"]
    assert m["mesures_avant"] == 490 * 8640 * 5 == 21_168_000
    mm = charger_mesures_bin(SORTIE / "mesures-avant.bin")
    assert len(mm) == 21_168_000
    from .outils import ts_unix_s
    t0 = int(cfg.fenetre.debut.timestamp())
    ts = ts_unix_s(mm[:: len(mm) // 1000])
    assert ts.min() >= t0
    assert ts.max() < t0 + 5 * 86400


def test_referentiel():
    m = manifeste()["comptages"]
    assert m["sites"] == 4
    assert m["actifs"] == 46
    assert 20 <= m["signaux"] <= 30
    assert m["affectations"] == 490


def test_evenements_et_meteo():
    m = manifeste()["comptages"]
    assert 650_000 <= m["evenements"] <= 750_000
    assert 35_000 <= m["meteo"] <= 45_000


def test_legacy_dans_la_fourchette():
    cfg = charger_config(BASE / "config.yaml")
    n = cfg.legacy_series * (86400 // cfg.legacy_pas_secondes) * cfg.legacy_jours
    assert 38_000_000 <= n <= 42_000_000
