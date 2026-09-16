# Journal de bord MISTRAL

Tenu conformément au bloc 2.2 : médiane sur cinq exécutions, écart-type,
mesure relancée (jamais reportée) au-delà de 20 % de la médiane. Les durées
absolues ne sont pas transposables ; seuls les **rapports** le sont.

Les sections ci-dessous sont des en-têtes à compléter au fil des ateliers
(L01, L03, L04, L08). Les autres modules ajoutent leur section librement.

## M02 — ligne de base
Environnement : Docker 2 vCPU / 8 Go · TimescaleDB 2.29.x · PostgreSQL 17.x · <OS du poste>

| requête                       | médiane | écart-type | note        |
|-------------------------------|---------|------------|-------------|
| R1 dernier point              |         |            | table brute |
| R2 fenêtre 3 jours            |         |            | table brute |
| R3 agrégation fenêtre (j1-j5) |         |            | table brute |

Volume : heap … · index … · total …

## M04 — après conversion en hypertable

| requête                       | ligne de base M02 | hypertable | rapport |
|-------------------------------|-------------------|------------|---------|
| R1 dernier point              |                   |            |         |
| R2 fenêtre 3 jours            |                   |            |         |
| R3 agrégation fenêtre (j1-j5) |                   |            |         |

| Grandeur relevée              | 1 jour | 7 jours | 30 jours |
|-------------------------------|--------|---------|----------|
| Nombre de chunks              |        |         |          |
| Volume total                  |        |         |          |
| Temps de planification        |        |         |          |
| R1 · point le plus récent     |        |         |          |
| R2 · fenêtre de 3 jours       |        |         |          |
| R3 · agrégation complète      |        |         |          |

Requête corrigée (étape 4) : avant … · après … · rapport …

## M05 — montée en charge

| Grandeur relevée              | Unitaire | Lots 1 000 | COPY binaire |
|-------------------------------|----------|------------|--------------|
| Lignes écrites en 60 s        |          |            |              |
| Débit · points par seconde    |          |            |              |
| Latence médiane par opération |          |            |              |
| CPU serveur / CPU client      |          |            |              |
| Journal produit               |          |            |              |

Rapport unitaire → meilleure stratégie : … (contexte : …)
Point de rupture : … points/s · ressource saturée : … · diagnostic : …

## M05 — retard d'arrivée

| p50 | p95 | p99 | pire cas |
|-----|-----|-----|----------|
|     |     |     |          |

Profil de décalage : … — **section reprise en M08**.

## M09 — segmentation comparée

| Grandeur                      | segmentby series_id | segmentby machine_id | aucun |
|-------------------------------|---------------------|----------------------|-------|
| Ratio de compression          |                     |                      |       |
| R1 · point le plus récent     |                     |                      |       |
| R2 · fenêtre filtrée sur série|                     |                      |       |
| R3 · agrégation complète      |                     |                      |       |

Ratio `mesures_hc` : … · lignes par segment : … · coût de l'`UPDATE` : …
