# Calibration du générateur MISTRAL (étage 1)

## Sources

| Jeu | Contenu utilisé | Accès |
|---|---|---|
| **Kelmarsh** | 6 éoliennes Senvion MM92, SCADA 10 min, année **2020** (`Kelmarsh_SCADA_2020_3086.zip`), fichiers `Turbine_Data_*` et `Status_*`, plus `Kelmarsh_WT_static.csv` | Zenodo, DOI [`10.5281/zenodo.8252025`](https://doi.org/10.5281/zenodo.8252025) |

Données publiées par **Cubico Sustainable Investments Ltd** sous licence
**CC-BY-4.0**. Les CSV sources ne sont pas versionnés (`calibration-sources/`,
ignoré) ; seul `params.json` l'est.

Extraction réalisée le **2026-08-31** par `src/mistral_gen/calibration.py`
(`uv run python -m mistral_gen.calibration`, ~13 s).

## Méthode

- **Courbe de puissance** — puissance active en fonction de la vitesse de vent,
  par pas de 0,5 m/s : médiane, écart-type, quantiles 10/90 par classe.
  Les périodes d'arrêt sont filtrées au préalable à l'aide du fichier
  d'événements (`Status_*`) : tout intervalle daté dont la catégorie IEC
  n'est pas `Full Performance` est exclu, ainsi que les bridages manifestes
  (P < 10 kW par vent > 5 m/s). Sans ce filtre la courbe est écrasée vers
  le bas.
- **Distribution du vent** — loi de Weibull ajustée par la méthode des
  moments sur la vitesse hors arrêts ; **autocorrélation au décalage
  10 min** calculée sur la série brute (elle pilote le processus AR(1) de
  l'étage 2 — sans elle, le vent synthétique saute d'une valeur à l'autre
  et toute interpolation devient absurde).
- **Disponibilité** — part du temps hors intervalles d'arrêt ; fréquence
  d'arrêts par machine-jour ; durées d'arrêt ajustées par une loi
  log-normale (µ, σ sur le logarithme des durées en secondes).
- **Interruptions de collecte** — l'export Greenbyte matérialise la grille
  10 min complète : un trou de collecte y apparaît comme une suite de
  lignes entièrement NaN (vent et puissance). Fréquence par machine-jour
  et durées ajustées en log-normale.
- **Températures** — relation linéaire entre température d'huile de
  multiplicateur et puissance active (pente °C/kW, ordonnée à l'origine) ;
  constante de temps estimée par décroissance de l'autocorrélation à 1 h
  (τ = −3600 / ln ρ₆), bornée à [10 min, 4 h] ; moyenne et écart-type de
  la température nacelle.
- **Rotor** — médiane de la vitesse rotor par classe de vent de 0,5 m/s
  (hors arrêts).
- **Tension réseau** — moyenne et écart-type de `Grid voltage (V)` hors
  valeurs nulles d'arrêt.
- **Référentiel** — puissance nominale (2 050 kW), diamètre rotor (92 m),
  hauteur de moyeu (78,5 m) depuis `Kelmarsh_WT_static.csv`.

## Valeurs clés extraites

| Paramètre | Valeur |
|---|---|
| Weibull k / λ | 2,379 / 7,399 m/s |
| Autocorrélation vent à 10 min | 0,970 |
| Taux de disponibilité | 95,4 % |
| Arrêts par machine-jour | 0,58 (durées log-normales µ=5,90 σ=1,56) |
| Interruptions de collecte par machine-jour | 0,052 (µ=9,01 σ=1,11) |
| Saturation courbe de puissance | ≈ 2 045 kW (nominal 2 050 kW) |

## Reproduire

```bash
cd generateur
mkdir -p calibration-sources && cd calibration-sources
curl -LO "https://zenodo.org/api/records/8252025/files/Kelmarsh_WT_static.csv/content" -o Kelmarsh_WT_static.csv
curl -L  "https://zenodo.org/api/records/8252025/files/Kelmarsh_SCADA_2020_3086.zip/content" -o Kelmarsh_SCADA_2020.zip
cd .. && uv run python -m mistral_gen.calibration
```
