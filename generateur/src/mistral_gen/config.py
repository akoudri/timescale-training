"""Chargement et validation de la configuration.

La fenêtre de 45 jours doit couvrir un week-end de bascule heure d'été /
heure d'hiver en Europe/Paris (contrainte 6.1). Cette vérification est
faite ici, au chargement : une fenêtre non conforme lève ConfigError et
le générateur refuse de produire un jeu inutilisable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Fenetre:
    debut: datetime          # aware, dans le fuseau métier
    jours: int
    fuseau: str

    @property
    def fin(self) -> datetime:
        # borne exclusive : debut + jours en temps civil UTC (la durée réelle
        # est exactement jours*86400 s : la grille de mesures est en UTC)
        return self.debut + timedelta(days=self.jours)

    @property
    def duree_s(self) -> int:
        return int((self.fin - self.debut).total_seconds())

    def jours_de_bascule(self) -> list[datetime]:
        """Jours civils (locaux) dont la durée n'est pas 24 h."""
        tz = ZoneInfo(self.fuseau)
        local_debut = self.debut.astimezone(tz)
        jour = local_debut.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = self.fin.astimezone(tz)
        bascules = []
        while jour < fin:
            lendemain_naif = (jour.replace(tzinfo=None) + timedelta(days=1))
            lendemain = lendemain_naif.replace(tzinfo=tz)
            # soustraction intra-fuseau = temps mural : passer par les
            # timestamps absolus pour voir les jours de 23 h et 25 h
            duree = lendemain.timestamp() - jour.timestamp()
            if duree != 86400 and lendemain <= fin:
                bascules.append(jour)
            jour = lendemain
        return bascules


@dataclass(frozen=True)
class Config:
    graine: int
    fenetre: Fenetre
    eoliennes: int
    centrales_pv: int
    points_livraison: int
    frequence_hz: float
    hc_series: int
    hc_pas_minutes: int
    hc_jours: int
    machines_avec_arret: int
    arret_duree_heures: tuple[float, float]
    remises_a_zero_compteur: int
    interruptions_min: int
    interruptions_total: int
    legacy_debut: datetime
    legacy_jours: int
    legacy_series: int
    legacy_pas_secondes: int
    mesures_avant_jours: int
    pdl_pertes: float
    sortie: Path
    brut: dict = field(repr=False, default_factory=dict)

    @property
    def pas_s(self) -> int:
        return round(1.0 / self.frequence_hz)

    @property
    def points_par_jour(self) -> int:
        return round(86400 * self.frequence_hz)


def charger_config(chemin: str | Path) -> Config:
    chemin = Path(chemin)
    d = yaml.safe_load(chemin.read_text())

    f = d["fenetre"]
    debut = datetime.fromisoformat(f["debut"])
    if debut.tzinfo is None:
        raise ConfigError("fenetre.debut doit porter un décalage horaire explicite")
    fen = Fenetre(debut=debut, jours=int(f["jours"]), fuseau=f.get("fuseau", "Europe/Paris"))

    bascules = fen.jours_de_bascule()
    if not bascules:
        raise ConfigError(
            f"La fenêtre {fen.debut.isoformat()} + {fen.jours} jours ne couvre aucun "
            f"changement d'heure {fen.fuseau} (contrainte 6.1). "
            "Choisir un début tel que la fenêtre inclue le dernier dimanche de mars "
            "ou le dernier dimanche d'octobre. Génération refusée."
        )

    c = d["contraintes"]
    leg = d["legacy"]
    legacy_debut = datetime.fromisoformat(leg["debut"])

    cfg = Config(
        graine=int(d["graine"]),
        fenetre=fen,
        eoliennes=int(d["series"]["eoliennes"]),
        centrales_pv=int(d["series"]["centrales_pv"]),
        points_livraison=int(d["series"]["points_livraison"]),
        frequence_hz=float(d["frequence_hz"]),
        hc_series=int(d["haute_cardinalite"]["series"]),
        hc_pas_minutes=int(d["haute_cardinalite"]["pas_minutes"]),
        hc_jours=int(d["haute_cardinalite"]["jours"]),
        machines_avec_arret=int(c["machines_avec_arret"]),
        arret_duree_heures=tuple(c.get("arret_duree_heures", [42, 48])),
        remises_a_zero_compteur=int(c["remises_a_zero_compteur"]),
        interruptions_min=int(c["interruptions_min"]),
        interruptions_total=int(c.get("interruptions_total", 24)),
        legacy_debut=legacy_debut,
        legacy_jours=int(leg["jours"]),
        legacy_series=int(leg["series"]),
        legacy_pas_secondes=int(leg["pas_secondes"]),
        mesures_avant_jours=int(d["mesures_avant"]["jours"]),
        pdl_pertes=float(d["pdl"]["pertes"]),
        sortie=(chemin.parent / d.get("sortie", "output")).resolve(),
        brut=d,
    )

    if abs(1.0 / cfg.frequence_hz - cfg.pas_s) > 1e-9:
        raise ConfigError("frequence_hz doit correspondre à un pas entier en secondes")
    return cfg
