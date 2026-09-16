"""Référentiel MISTRAL : sites, actifs, signaux, affectation_capteur.

Répartition imposée par la fiche (§5.1), volontairement déséquilibrée :

| Site | Éoliennes | PV | PDL |
|------|-----------|----|-----|
| 1    | 15        | 0  | 0   |
| 2    | 18        | 0  | 0   |
| 3    | 9         | 1  | 0   |
| 4    | 0         | 2  | 1   |

490 séries : 42 éoliennes × 10 signaux + 3 centrales PV × 4 onduleurs
× 5 signaux + 1 point de livraison × 10 signaux.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .config import Config
from .rng import rng_pour

# (nom, region, latitude, longitude)
SITES = [
    (1, "Cap de la Serre", "Occitanie", 43.32, 2.48),
    (2, "Plateau des Brumes", "Hauts-de-France", 50.21, 2.79),
    (3, "Col du Levant", "Grand Est", 48.52, 5.47),
    (4, "Plaine de l'Adour", "Nouvelle-Aquitaine", 43.61, -0.27),
]

EOLIENNES_PAR_SITE = {1: 15, 2: 18, 3: 9, 4: 0}
PV_PAR_SITE = {1: 0, 2: 0, 3: 1, 4: 2}
PDL_PAR_SITE = {1: 0, 2: 0, 3: 0, 4: 1}

ONDULEURS_PAR_CENTRALE = 4
PV_PUISSANCE_ONDULEUR_KW = 300.0

# catalogue des types de signaux : (libelle, unite, famille)
SIGNAUX_EOLIENNE = [
    ("puissance_kw", "kW", "production"),
    ("energie_kwh", "kWh", "production"),
    ("vitesse_vent_ms", "m/s", "meteo"),
    ("direction_vent_deg", "°", "meteo"),
    ("temperature_nacelle_c", "°C", "mecanique"),
    ("temperature_multiplicateur_c", "°C", "mecanique"),
    ("vitesse_rotor_rpm", "tr/min", "mecanique"),
    ("angle_pale_deg", "°", "mecanique"),
    ("tension_reseau_v", "V", "electrique"),
    ("disponible", "", "production"),
]
SIGNAUX_PV = [
    ("puissance_dc_kw", "kW", "production"),
    ("puissance_ac_kw", "kW", "production"),
    ("tension_dc_v", "V", "electrique"),
    ("temperature_module_c", "°C", "mecanique"),
    ("irradiance_wm2", "W/m²", "meteo"),
]
SIGNAUX_PDL = [
    ("puissance_active_kw", "kW", "production"),
    ("puissance_reactive_kvar", "kvar", "electrique"),
    ("tension_l1_v", "V", "electrique"),
    ("tension_l2_v", "V", "electrique"),
    ("tension_l3_v", "V", "electrique"),
    ("courant_l1_a", "A", "electrique"),
    ("courant_l2_a", "A", "electrique"),
    ("courant_l3_a", "A", "electrique"),
    ("frequence_hz", "Hz", "electrique"),
]
# 10e signal PDL : la fréquence ne suffit qu'à 9, le comptage de la fiche
# (10 signaux) inclut l'énergie soutirée/injectée cumulée
SIGNAUX_PDL.append(("energie_injectee_kwh", "kWh", "production"))


@dataclass(frozen=True)
class Serie:
    series_id: int
    machine_id: int
    site_id: int
    type_machine: str        # eolienne | pv | pdl
    signal_id: int
    libelle: str
    unite: str
    famille: str
    onduleur: int | None     # 1..4 pour le PV, sinon None


@dataclass
class Referentiel:
    sites: list[tuple]                    # (site_id, nom, region, lat, lon)
    actifs: list[tuple]                   # (machine_id, site_id, type, modele, p_nom_kw, mise_en_service)
    signaux: list[tuple]                  # (signal_id, libelle, unite, famille)
    affectations: list[tuple]             # (series_id, machine_id, signal_id, debut_iso, fin)
    series: list[Serie]

    @property
    def series_par_machine(self) -> dict[int, list[Serie]]:
        d: dict[int, list[Serie]] = {}
        for s in self.series:
            d.setdefault(s.machine_id, []).append(s)
        return d

    def machines(self, type_machine: str) -> list[tuple]:
        return [a for a in self.actifs if a[2] == type_machine]


def construire_referentiel(cfg: Config, params: dict) -> Referentiel:
    rng = rng_pour(cfg.graine, "referentiel")
    ref_machine = params["referentiel"]

    sites = list(SITES)

    # --- signaux -------------------------------------------------------------
    signaux, signal_ids = [], {}
    sid = 0
    for lib, unite, famille in SIGNAUX_EOLIENNE + SIGNAUX_PV + SIGNAUX_PDL:
        sid += 1
        signaux.append((sid, lib, unite, famille))
        signal_ids[lib] = sid

    # --- actifs --------------------------------------------------------------
    actifs = []
    machine_id = 0

    def date_mes() -> str:
        # mise en service déterministe entre 2016 et 2023
        j = int(rng.integers(0, 8 * 365))
        return (date(2016, 3, 1) + timedelta(days=j)).isoformat()

    eoliennes, pvs, pdls = [], [], []
    for site_id, *_ in sites:
        for _ in range(EOLIENNES_PAR_SITE[site_id]):
            machine_id += 1
            actifs.append((machine_id, site_id, "eolienne", ref_machine["modele"],
                           ref_machine["puissance_nominale_kw"], date_mes()))
            eoliennes.append((machine_id, site_id))
    for site_id, *_ in sites:
        for _ in range(PV_PAR_SITE[site_id]):
            machine_id += 1
            p_nom = ONDULEURS_PAR_CENTRALE * PV_PUISSANCE_ONDULEUR_KW
            actifs.append((machine_id, site_id, "pv", "HelioWatt HW-300Q", p_nom, date_mes()))
            pvs.append((machine_id, site_id))
    for site_id, *_ in sites:
        for _ in range(PDL_PAR_SITE[site_id]):
            machine_id += 1
            actifs.append((machine_id, site_id, "pdl", "PDL HTB 90 MW", 90_000.0, date_mes()))
            pdls.append((machine_id, site_id))

    # --- affectations et séries ---------------------------------------------
    # l'affectation courante débute avant la fenêtre (fin = NULL)
    debut_aff = (cfg.fenetre.debut - timedelta(days=365)).isoformat()
    series: list[Serie] = []
    affectations = []
    series_id = 0

    for m_id, site_id in eoliennes:
        for lib, unite, famille in SIGNAUX_EOLIENNE:
            series_id += 1
            series.append(Serie(series_id, m_id, site_id, "eolienne",
                                signal_ids[lib], lib, unite, famille, None))
            affectations.append((series_id, m_id, signal_ids[lib], debut_aff, None))

    for m_id, site_id in pvs:
        for onduleur in range(1, ONDULEURS_PAR_CENTRALE + 1):
            for lib, unite, famille in SIGNAUX_PV:
                series_id += 1
                series.append(Serie(series_id, m_id, site_id, "pv",
                                    signal_ids[lib], lib, unite, famille, onduleur))
                affectations.append((series_id, m_id, signal_ids[lib], debut_aff, None))

    for m_id, site_id in pdls:
        for lib, unite, famille in SIGNAUX_PDL:
            series_id += 1
            series.append(Serie(series_id, m_id, site_id, "pdl",
                                signal_ids[lib], lib, unite, famille, None))
            affectations.append((series_id, m_id, signal_ids[lib], debut_aff, None))

    return Referentiel(sites, actifs, signaux, affectations, series)


DDL_REFERENTIEL = """\
CREATE TABLE sites (
    site_id  INTEGER PRIMARY KEY,
    nom      TEXT NOT NULL,
    region   TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL
);

CREATE TABLE actifs (
    machine_id            INTEGER PRIMARY KEY,
    site_id               INTEGER NOT NULL REFERENCES sites,
    type                  TEXT NOT NULL CHECK (type IN ('eolienne','pv','pdl')),
    modele                TEXT NOT NULL,
    puissance_nominale_kw DOUBLE PRECISION NOT NULL,
    mise_en_service       DATE NOT NULL
);

CREATE TABLE signaux (
    signal_id INTEGER PRIMARY KEY,
    libelle   TEXT NOT NULL UNIQUE,
    unite     TEXT NOT NULL,
    famille   TEXT NOT NULL CHECK (famille IN ('production','meteo','mecanique','electrique'))
);

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE affectation_capteur (
    series_id  INTEGER NOT NULL,
    machine_id INTEGER NOT NULL REFERENCES actifs,
    signal_id  INTEGER NOT NULL REFERENCES signaux,
    debut      TIMESTAMPTZ NOT NULL,
    fin        TIMESTAMPTZ,
    EXCLUDE USING gist (series_id WITH =, tstzrange(debut, fin) WITH &&)
);
"""


def _q(texte: str) -> str:
    """Échappement d'un littéral SQL (apostrophes doublées)."""
    return texte.replace("'", "''")


def emettre_sql(ref: Referentiel) -> str:
    """SQL complet du référentiel (DDL + données)."""
    parties = [DDL_REFERENTIEL, "BEGIN;"]
    for site_id, nom, region, lat, lon in ref.sites:
        parties.append(
            f"INSERT INTO sites VALUES ({site_id}, '{_q(nom)}', '{_q(region)}', {lat}, {lon});")
    for m in ref.actifs:
        parties.append(
            f"INSERT INTO actifs VALUES ({m[0]}, {m[1]}, '{m[2]}', '{_q(m[3])}', {m[4]}, '{m[5]}');")
    for s in ref.signaux:
        parties.append(
            f"INSERT INTO signaux VALUES ({s[0]}, '{s[1]}', '{s[2]}', '{s[3]}');")
    for a in ref.affectations:
        fin = "NULL" if a[4] is None else f"'{a[4]}'"
        parties.append(
            f"INSERT INTO affectation_capteur VALUES ({a[0]}, {a[1]}, {a[2]}, '{a[3]}', {fin});")
    parties.append("COMMIT;")
    return "\n".join(parties) + "\n"
