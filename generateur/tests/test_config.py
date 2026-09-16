import pytest
import yaml
from pathlib import Path

from mistral_gen.config import charger_config, ConfigError

BASE = Path(__file__).resolve().parents[1]


def _config_modifiee(tmp_path, **fenetre):
    d = yaml.safe_load((BASE / "config.yaml").read_text())
    d["fenetre"].update(fenetre)
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(d))
    return p


def test_config_reference_couvre_une_bascule():
    cfg = charger_config(BASE / "config.yaml")
    bascules = cfg.fenetre.jours_de_bascule()
    assert len(bascules) == 1
    # dernier dimanche d'octobre 2026
    assert bascules[0].date().isoformat() == "2026-10-25"
    assert cfg.points_par_jour == 8640
    assert cfg.pas_s == 10
    # la grille de mesures est absolue : exactement jours*86400 s,
    # le jour local de 25 h est absorbé par la fin de fenêtre locale
    assert cfg.fenetre.duree_s == 45 * 86400


def test_fenetre_sans_bascule_refusee(tmp_path):
    p = _config_modifiee(tmp_path, debut="2026-06-01T00:00:00+02:00")
    with pytest.raises(ConfigError, match="changement d'heure"):
        charger_config(p)


def test_fenetre_mars_acceptee(tmp_path):
    p = _config_modifiee(tmp_path, debut="2026-03-01T00:00:00+01:00")
    cfg = charger_config(p)
    assert cfg.fenetre.jours_de_bascule()[0].date().isoformat() == "2026-03-29"


def test_debut_sans_fuseau_refuse(tmp_path):
    p = _config_modifiee(tmp_path, debut="2026-09-15T00:00:00")
    with pytest.raises(ConfigError):
        charger_config(p)
