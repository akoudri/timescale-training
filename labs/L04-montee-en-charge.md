# L04 — Montée en charge

**Module** : M05 · Ingestion à haut débit
**Durée** : 70 min — socle 60 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M04`
**État de fil rouge en sortie** : `mistral-M05`

---

## Contexte

Tout ce qui a été mesuré jusqu'ici portait sur des lectures. Cet atelier mesure des écritures, et produit trois résultats de nature différente :

1. **Un rapport** entre la stratégie naïve et la meilleure — l'ordre de grandeur annoncé au slide 5.1 est vérifié, pas récité.
2. **Une ressource limitante nommée**, appuyée sur une mesure et non sur une intuition. « C'est lent » n'est pas un diagnostic.
3. **Le retard d'arrivée**, en p50, p99 et pire cas. C'est la seule valeur de tout le module dont un autre module dépend structurellement : M08 s'en sert pour dimensionner ses fenêtres de rafraîchissement.

**Deux règles de protocole, à poser avant de commencer.**

Les trois stratégies tournent à **durée fixe** — soixante secondes chacune — et l'on compare le **nombre de lignes écrites**. Comparer des durées totales sur des volumes différents ne veut rien dire, et injecter cinq millions de points en `INSERT` unitaire prendrait une demi-heure.

L'injection se fait dans une hypertable dédiée, `mesures_charge`, jamais dans `mesures`. Injecter dans le fil rouge rendrait l'état de reprise non déterministe et fausserait tous les comptages des modules suivants.

---

## Prérequis

**État attendu**

- `mistral-M04` atteint : intervalle de chunk tranché et inscrit, `mesures.md` renseigné
- L'instance est épinglée à 2 vCPU et 8 Go, swap désactivé

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l04/creer-charge.sql` | Crée `mesures_charge`, même schéma que `mesures`, avec la colonne `ingere_le` |
| `l04/injecteur.py` | Injecteur paramétrable : stratégie, durée, taille de lot, débit cible, décalage d'horodatage |
| `l04/diagnostic.sql` | Les trois requêtes de diagnostic de l'étape 4 |
| `l04/retard.sql` | Le calcul du retard d'arrivée |
| `mesures.md` | Journal de bord, tableau d'en-têtes déjà en place |

---

## SOCLE — pour tous

### Étape 1 — Préparer la table de charge (8 min)

```sql
\i l04/creer-charge.sql

SELECT hypertable_name, num_dimensions
FROM   timescaledb_information.hypertables
WHERE  hypertable_name = 'mesures_charge';
```

`mesures_charge` reprend le schéma retenu en M03 et l'intervalle tranché en M04, avec une colonne supplémentaire :

```sql
ingere_le TIMESTAMPTZ NOT NULL DEFAULT now()
```

C'est elle qui rendra le retard d'arrivée mesurable à l'étape 5.

Vérifier que la table est vide avant chaque série de mesures :

```sql
TRUNCATE mesures_charge;
```

### Étape 2 — Les trois injections (25 min)

Chaque stratégie tourne soixante secondes. Entre deux stratégies, vider la table et laisser l'activité retomber — un autovacuum en cours fausse la mesure suivante.

```bash
uv run l04/injecteur.py --strategie unitaire --duree 60
uv run l04/injecteur.py --strategie lots --taille-lot 1000 --duree 60
uv run l04/injecteur.py --strategie copy --binaire --duree 60
```

Pour chacune, relever **cinq grandeurs**.

Lignes écrites et débit — reportés par l'injecteur, à recouper côté base :

```sql
SELECT count(*) FROM mesures_charge;
```

Latence médiane par opération — reportée par l'injecteur.

CPU pendant l'injection, côté serveur **et** côté client :

```bash
docker stats --no-stream timescaledb
```

Volume de journal produit, par différence de position :

```sql
SELECT pg_current_wal_lsn() AS avant \gset
-- ... lancer l'injection, attendre la fin ...
SELECT pg_size_pretty(
         pg_wal_lsn_diff(pg_current_wal_lsn(), :'avant')) AS wal_produit;
```

Remplir le tableau de `mesures.md` :

| Grandeur relevée | Unitaire | Lots 1 000 | COPY binaire |
|---|---|---|---|
| Lignes écrites en 60 s | | | |
| Débit · points par seconde | | | |
| Latence médiane par opération | | | |
| CPU serveur / CPU client | | | |
| Journal produit | | | |

### Étape 3 — Le rapport, et ce qu'il veut dire (7 min)

Calculer le rapport entre la stratégie unitaire et la meilleure des trois, et le consigner **avec son contexte** :

```
Rapport unitaire → COPY binaire : × NN
Contexte : conteneur local, latence réseau négligeable, 2 vCPU, disque <type>
```

Répondre ensuite par écrit à deux questions :

- Le journal produit est-il proportionnel au nombre de lignes, ou dépend-il aussi de la stratégie ?
- La latence médiane des lots est-elle mille fois celle des insertions unitaires ? Sinon, qu'est-ce que cela dit du coût par instruction ?

### Étape 4 — Le point de rupture (15 min)

Relancer l'injection par lots avec un débit cible croissant, jusqu'à ce que le débit réel cesse de suivre le débit demandé.

```bash
for d in 20000 50000 100000 200000; do
  uv run l04/injecteur.py --strategie lots --taille-lot 1000 \
                           --debit-cible $d --duree 30
done
```

Le point de rupture est le premier palier où le débit obtenu décroche du débit demandé. Le relever, puis **nommer la ressource saturée** à l'aide des trois diagnostics.

Ce que la base attend :

```sql
SELECT wait_event_type, wait_event, count(*)
FROM   pg_stat_activity
WHERE  state = 'active' AND pid <> pg_backend_pid()
GROUP  BY 1, 2 ORDER BY 3 DESC
\watch 0.5
```

Ce que consomme le serveur, et ce que consomme le client :

```bash
docker stats --no-stream
```

Ce que fait l'écriture différée :

```sql
SELECT * FROM pg_stat_bgwriter;
```

Écrire la conclusion en une phrase, de la forme : « au-delà de N points par seconde, la ressource X sature, ce qui se lit sur Y ».

### Étape 5 — Le retard d'arrivée (12 min)

L'injecteur produit par défaut des horodatages à l'instant de l'insertion, ce qui donne un retard nul et une valeur inutilisable. Utiliser le profil de décalage réaliste :

```bash
uv run l04/injecteur.py --strategie lots --taille-lot 1000 --duree 60 \
                         --profil-retard mistral
```

Ce profil reproduit le comportement du parc : la majorité des points arrivent en quelques secondes, une minorité de capteurs à liaison dégradée remonte avec plusieurs minutes de retard, et un incident de collecte simulé produit une reprise groupée.

```sql
SELECT percentile_disc(0.50) WITHIN GROUP (ORDER BY ingere_le - ts) AS p50,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY ingere_le - ts) AS p95,
       percentile_disc(0.99) WITHIN GROUP (ORDER BY ingere_le - ts) AS p99,
       max(ingere_le - ts)                                          AS pire
FROM   mesures_charge;
```

Consigner les quatre valeurs dans `mesures.md`, sous un titre `## M05 — retard d'arrivée`, **et marquer explicitement cette section comme reprise en M08**.

Répondre enfin à la question qui sera posée en M08 : entre le p95, le p99 et le pire cas, laquelle de ces valeurs faut-il retenir pour dimensionner une fenêtre de rafraîchissement, et qu'est-ce qu'on accepte de perdre en choisissant chacune ?

### Critères de réussite

- [ ] Les trois injections ont tourné soixante secondes chacune, sur une table vidée entre chaque
- [ ] Les cinq grandeurs sont renseignées pour les trois stratégies
- [ ] Le rapport unitaire vers meilleure **dépasse un ordre de grandeur**, et son contexte est consigné
- [ ] Le point de rupture est relevé, et la ressource saturée est nommée **avec le diagnostic qui l'a révélée**
- [ ] Le retard d'arrivée est mesuré en p50, p95, p99 et pire cas, avec le profil de décalage
- [ ] La section `## M05 — retard d'arrivée` est marquée comme reprise en M08
- [ ] `mesures_charge` est vidée en fin d'atelier

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M05`.

### E1 — Rendre l'ingestion idempotente

Ajouter la contrainte d'unicité, réinjecter, puis **rejouer volontairement le même lot** :

```sql
ALTER TABLE mesures_charge
  ADD CONSTRAINT charge_uk UNIQUE (series_id, ts);
```

```bash
uv run l04/injecteur.py --strategie lots --duree 30 --graine 42
uv run l04/injecteur.py --strategie lots --duree 30 --graine 42 --on-conflict rien
```

Vérifier qu'aucun doublon n'apparaît, puis mesurer le surcoût de la contrainte sur le débit, en comparant à la mesure de l'étape 2. Comparer enfin `DO NOTHING` et `DO UPDATE` : le second corrige la valeur, et son coût n'est pas le même.

### E2 — Backfill concurrent

Lancer l'injection courante en arrière-plan, puis charger trente jours d'historique pendant qu'elle tourne :

```bash
uv run l04/injecteur.py --strategie lots --debit-cible 20000 --duree 180 &
uv run l04/injecteur.py --strategie copy --backfill 30j
```

Mesurer la dégradation du flux courant : débit et latence, avant et pendant le backfill. Recommencer en découpant le backfill par chunk avec une pause entre chaque, et comparer.

### E3 — Journalisée contre non journalisée

Comparer le débit d'un `COPY` sur `mesures_charge` puis sur une variante non journalisée. Chiffrer le gain et le volume de journal économisé.

Puis énoncer par écrit la règle d'emploi : dans quel cas précis ce compromis est acceptable, et qu'est-ce qui doit être vrai du producteur pour qu'il le soit.

### E4 — La courbe du plateau

Faire varier la taille de lot sur six valeurs — 100, 500, 1 000, 5 000, 20 000, 50 000 — à durée fixe.

Tracer le débit en fonction de la taille de lot et situer le plateau. Répondre ensuite : au-delà du plateau, qu'est-ce qui empêche le débit de continuer à croître, et cela se lit-il dans les événements d'attente de l'étape 4 ?

---

## Pièges et indices

**Le rapport mesuré ne sera pas transposable en production.**
Il dépend massivement de la latence réseau. En conteneur local, l'aller-retour est négligeable et le rapport sera nettement plus faible qu'à travers un réseau d'entreprise. Consigner le contexte à côté du chiffre, sinon quelqu'un le citera hors contexte six mois plus tard.

**Le volume de journal semble nul.**
Il se relève par différence de position via `pg_wal_lsn_diff`, jamais par la taille du répertoire `pg_wal`, qui est recyclé en continu et dont la taille est à peu près constante.

**Le point de rupture n'arrive jamais.**
L'injecteur sature avant la base. Vérifier le CPU **du client** avant de conclure quoi que ce soit sur le serveur — c'est le mode de défaillance le plus fréquent de cet atelier, et il conduit à des conclusions inversées. Si le client sature, lancer deux injecteurs en parallèle.

**Le retard d'arrivée mesuré est nul.**
Le profil de décalage n'a pas été activé. Sans `--profil-retard mistral`, l'injecteur horodate à l'instant de l'insertion et le retard est mécaniquement nul. La valeur exportée vers M08 est alors inutilisable, et le problème ne se découvrira qu'un jour et demi plus tard.

**Le débit de la stratégie unitaire varie beaucoup entre participants.**
C'est attendu : elle mesure surtout la latence de la boucle client-serveur, qui dépend de l'environnement. C'est aussi pourquoi le critère porte sur le rapport et non sur une valeur absolue.

**La table n'a pas été vidée entre deux stratégies.**
Le second `count(*)` inclut alors les lignes de la première. Le débit calculé est faux, et l'erreur est invisible si l'on ne recoupe pas avec le compteur de l'injecteur. `TRUNCATE` entre chaque, systématiquement.

**Les événements d'attente ne montrent rien de net.**
Une seule prise de mesure attrape mal un phénomène intermittent. Boucler la requête toutes les deux secondes pendant l'injection et agréger, plutôt que de la lancer une fois.

---

## Livrable

| Élément | Contenu |
|---|---|
| `mesures.md` | Tableau des cinq grandeurs sur trois stratégies, rapport avec son contexte, point de rupture et ressource nommée |
| `mesures.md` §`M05 — retard d'arrivée` | p50, p95, p99, pire cas — **marqué comme repris en M08** |
| `l04/conclusion.md` | La phrase de diagnostic : « au-delà de N points/s, X sature, ce qui se lit sur Y » |
| État de reprise | `mistral-M05` |

## Nettoyage

À faire en fin d'atelier, extensions comprises : ce qui n'appartient pas à l'état de reprise part.

`mesures_charge` fait partie de l'état de reprise `mistral-M05`, mais **vide** : le volume écrit en salle dépend du poste et ne doit pas se propager aux modules suivants. Vider la table, sans la supprimer :

```sql
TRUNCATE mesures_charge;
```

Le journal produit pendant l'atelier (plusieurs gigaoctets de WAL) est recyclé par PostgreSQL de lui-même ; rien à faire de ce côté.

---

**Vers la suite.** L'écriture est réglée. Les tableaux de bord de MISTRAL mettent toujours quarante secondes à s'ouvrir, et cette fois le partitionnement n'y changera rien : le problème est dans la façon dont les requêtes sont écrites. M06 reprend cinq requêtes de `mistral_legacy` — la base de l'amorce de M01 — et les réécrit.
