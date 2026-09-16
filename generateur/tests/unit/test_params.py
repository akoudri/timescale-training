import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]


def test_params_json_plausible():
    p = json.loads((BASE / "params.json").read_text())

    ref = p["referentiel"]
    assert 1000 <= ref["puissance_nominale_kw"] <= 5000
    assert 60 <= ref["diametre_rotor_m"] <= 150

    courbe = p["courbe_puissance"]
    assert len(courbe) >= 30
    plafond = max(pt["mediane_kw"] for pt in courbe)
    assert 0.9 * ref["puissance_nominale_kw"] <= plafond <= 1.05 * ref["puissance_nominale_kw"]
    # croissante puis saturée : la médiane à 12 m/s dépasse celle à 6 m/s
    par_v = {pt["vitesse_ms"]: pt["mediane_kw"] for pt in courbe}
    assert par_v[12.25] > par_v[6.25] > par_v[3.25]

    v = p["vent"]
    assert 1.5 <= v["weibull_k"] <= 3.5
    assert 5.0 <= v["weibull_lambda_ms"] <= 12.0
    assert 0.85 <= v["autocorrelation_10min"] <= 0.999

    d = p["disponibilite"]
    assert 0.85 <= d["taux_moyen"] <= 0.995
    assert d["arrets_par_jour_machine"] > 0

    i = p["interruptions_collecte"]
    assert i["par_jour_machine"] > 0

    assert "CC-BY-4.0" in p["_attribution"]
