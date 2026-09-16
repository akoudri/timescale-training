# Générateur des jeux de données MISTRAL

Générateur des jeux de données du fil rouge **MISTRAL** (exploitant fictif
de parc éolien et photovoltaïque) pour la formation TimescaleDB de cinq
jours. Il implémente la fiche de spécification du générateur (document de
conception, non distribué avec le dépôt) ; les renvois « fiche §n » ci-dessous
s'y rapportent.

## Architecture en deux étages

**Étage 1 — calibration** (exécuté une fois, résultat versionné) : lit les
CSV SCADA réels de Kelmarsh (Zenodo, CC-BY-4.0) et écrit `params.json`.
Voir `CALIBRATION.md`. Les CSV sources ne sont pas versionnés.

**Étage 2 — synthèse** (rejoué à chaque reconstruction) : lit `params.json`
et `config.yaml`, produit tous les artefacts dans `output/`. Déterministe :
deux exécutions à graine égale produisent des fichiers binairement
identiques (vérifié par empreinte).

## Utilisation

```bash
uv sync

# étage 1 (optionnel : params.json est déjà versionné)
#   nécessite calibration-sources/, voir CALIBRATION.md
uv run mistral-gen calibrer

# étage 2 : tous les artefacts fichiers (~20 s, ~9 Go)
uv run mistral-gen generer

# dumps PostgreSQL (nécessite docker, image postgres:16 ; ~2 min 30)
uv run mistral-gen dumps

# tests d'acceptation
uv run pytest -m "not lent and not chargement"   # ~35 s
uv run pytest -m lent                            # déterminisme, ~1 min
uv run pytest -m chargement                      # docker pg17, ~10 min
```

## Artefacts produits (`output/`)

| Artefact | Contenu | Taille |
|---|---|---|
| `mesures.bin` | COPY binaire, 189 958 049 lignes (490 séries × 45 j à 0,1 Hz, moins les retraits 6.2/6.4 = 0,29 %) | 7,6 Go |
| `mesures-avant.bin` / `.dump` | Jours 1-5 en table ordinaire, 21 168 000 lignes exactes | 0,8 Go / 0,2 Go |
| `mesures-hc.bin` | 20 000 séries × 96 × 7 = 13 440 000 lignes (contrainte 6.5) | 0,5 Go |
| `mistral-referentiel.dump` | sites, actifs, signaux, affectation_capteur, meteo, evenements | 4 Mo |
| `mistral-legacy.dump` | Base source de migration : PG 16, partitions déclaratives mensuelles, vues matérialisées, purge ligne à ligne, séquence non triviale — 41 471 963 lignes, ≈ 3 Go restaurés | 0,6 Go |
| `machines-avec-arret.json` | Les trois arrêts de maintenance de la contrainte 6.2 | — |
| `referentiel.sql`, `evenements.csv`, `meteo.csv` | Sources des dumps, rechargeables directement | 77 Mo |
| `MANIFESTE.json` | Empreintes SHA-256, comptages, graine, attribution | — |

Chargement des `.bin` :

```sql
\copy mesures FROM 'mesures.bin' WITH (FORMAT binary)
```

## Les cinq contraintes (fiche §6)

| Contrainte | Réalisation |
|---|---|
| 6.1 changement d'heure | Fenêtre 15 sept → 30 oct 2026 (bascule le 25 oct, vérifiée au chargement de la config — génération refusée sinon) |
| 6.2 pas irrégulier | 3 éoliennes (une par site éolien) en arrêt maintenance 42-48 h début octobre, échantillonnage horaire pendant l'arrêt, listées dans `machines-avec-arret.json` |
| 6.3 remises à zéro | 2 compteurs `energie_kwh` repartent de 0 (jours 25 et 33) |
| 6.4 interruptions | 24 trous imposés de 35 min à 8 h (dont vent + compteur) + trous naturels à la fréquence calibrée ; aucun sur les jours 1-5 |
| 6.5 cardinalité | `mesures_hc` : 96 lignes/série/jour contre 8 640 pour `mesures` |

## Choix d'implémentation

- Python 3.12 + numpy vectorisé, écriture COPY binaire en flux par blocs
  structurés : les 190 M lignes sont produites en ~20 s, sans jamais tenir
  le jeu en mémoire.
- Générateurs Philox à clé dérivée SHA-256 de (graine, volet, clé) : le
  déterminisme ne dépend pas de l'ordre d'exécution.
- Vent : AR(1) gaussien au pas 10 s (φ = ρ₆₀₀^(1/60), ρ₆₀₀ calibré),
  transformé en Weibull calibrée par correspondance de quantiles ;
  corrélation spatiale intra-site 0,85.
- Les dumps PostgreSQL sont dérivés dans un conteneur postgres:16
  éphémère ; leur *contenu* est déterministe mais pg_dump n'est pas
  reproductible bit à bit (voir `note_derives` du manifeste).

## Fenêtres temporelles

- `mesures` : 2026-09-15 00:00 +02 → 2026-10-30 (45 jours, 25 oct = 25 h)
- `mistral_legacy` : 2026-07-20 → 2026-09-30 (72 j, pas 60 s, 400 séries) —
  recouvre partiellement `mesures` (15-30 sept) sans lui être identique,
  et contient les dates de juillet 2026 citées par le support.
