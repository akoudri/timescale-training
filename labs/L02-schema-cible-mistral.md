# L02 — Schéma cible MISTRAL

**Module** : M03 · Modélisation des données temporelles
**Durée** : 50 min — socle 40 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M02`
**État de fil rouge en sortie** : `mistral-M03`

---

## Contexte

Le métier, le référentiel et les tables restaurées sont décrits dans `L00-mistral-modele-de-donnees.md` : le lire avant de trancher quoi que ce soit. Les six décisions ci-dessous portent sur ce qu'il laisse volontairement ouvert.

C'est le seul atelier de la formation dont le livrable est une **décision** et non une mesure. Le schéma produit ici n'est pas un exercice : il est utilisé par les douze modules suivants, et c'est lui qui est migré en M12.

Deux conséquences pratiques. D'abord, il ne s'agit pas de partir d'une page blanche : le dépôt fournit un squelette avec **six points de décision** explicitement marqués, et le travail consiste à les trancher et à écrire pourquoi. Ensuite, la chaîne d'instantanés impose une **variante de référence** : c'est celle que `reprise/M03.sql` implémente, et c'est sur elle que les modules suivants s'appuient. Un sous-groupe qui retient un autre modèle a le droit d'avoir raison — il consigne son choix dans son plan d'application et poursuit sur la référence.

Ce qui est réellement évalué n'est pas le schéma retenu, mais la qualité des six justifications.

---

## Prérequis

**Lecture préalable obligatoire**

- `L00-mistral-modele-de-donnees.md` : le métier MISTRAL, le catalogue des 25 signaux, l'affectation datée, la fenêtre du jeu et ses irrégularités. Les six décisions ne se tranchent pas sans savoir ce que l'on modélise ; compter dix minutes de lecture, avant la séance.

**État attendu**

- `mistral-M02` atteint : instance conforme, extension 2.29 chargée, `mesures.md` renseigné avec trois médianes
- Le jeu MISTRAL est restauré, `mesures` est encore une **table ordinaire**

**Tables de référentiel déjà présentes** (détaillées dans L00)

| Table | Colonnes utiles |
|---|---|
| `sites` | `site_id`, `nom`, `region` |
| `actifs` | `machine_id`, `site_id`, `type` (`eolienne`, `pv`, `pdl`), `mise_en_service` |
| `signaux` | `signal_id`, `libelle`, `unite`, `famille` |
| `affectation_capteur` | `series_id`, `machine_id`, `signal_id`, `debut`, `fin` |

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l02/schema-squelette.sql` | Le squelette à compléter, six décisions marquées |
| `l02/charger-referentiel.sql` | Vérification du référentiel restauré (`sites`, `actifs`, `signaux`, `affectation_capteur`) |
| `l02/charger-mesures.sql` | Chargement du jeu complet (45 j) par `COPY ... FORMAT binary` |
| `l02/volumetrie.sql` | Aide au calcul de volume, voir étape 5 |

---

## SOCLE — pour tous

### Étape 1 — Trancher les six points de décision (15 min)

Travail en sous-groupes de deux ou trois. Ouvrir `l02/schema-squelette.sql` : chaque décision est marquée par un bloc de la forme suivante.

```sql
-- ┌── DÉCISION 1 ─────────────────────────────────────────────────┐
-- │ Forme du modèle pour `mesures`                                │
-- │   a) étroit        : ts, series_id, valeur                    │
-- │   b) large         : ts, machine_id, une colonne par signal   │
-- │   c) intermédiaire : une hypertable par famille de signaux    │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
```

**La valeur par défaut n'est pas la bonne réponse : c'est la plus courante.** Chaque décision attend une phrase de justification, pas une validation.

Les six décisions :

| N° | Objet | Options | Ce qui doit être invoqué |
|---|---|---|---|
| 1 | Forme du modèle pour `mesures` | étroit · large · intermédiaire | Le profil de requêtes attendu et la volatilité du parc de signaux |
| 2 | Clé d'identification de série | `series_id` entier · clé composite `(site, machine, signal)` · `tag` textuel | Le volume par ligne **et** la cardinalité future du `segmentby` de M09 |
| 3 | Type de la valeur mesurée | `double precision` · `real` · `numeric` | La précision réellement utile du capteur, pas la précision maximale disponible |
| 4 | Emplacement du drapeau de qualité | colonne `qualite` · encodé dans la valeur · table séparée | Le coût par ligne et la fréquence des requêtes qui filtrent dessus |
| 5 | Charge utile des événements | `JSONB` · colonnes typées · les deux | Le rapport entre variabilité de la charge utile et volume de la table |
| 6 | Lien entre une mesure et sa machine | `machine_id` dénormalisé dans `mesures` · jointure sur `affectation_capteur` | La possibilité de corriger une affectation erronée après coup |

### Étape 2 — Créer les hypertables (10 min)

Compléter le squelette, puis l'exécuter. Ne **pas** choisir d'intervalle de chunk : conserver la valeur par défaut du squelette, M04 y reviendra avec une mesure à l'appui.

```sql
\i l02/schema-squelette.sql

-- vérification
SELECT hypertable_name, num_dimensions
FROM   timescaledb_information.hypertables
ORDER  BY hypertable_name;
```

Deux hypertables sont attendues au minimum : les mesures (une ou plusieurs selon la décision 1), et les événements. La variante de référence en crée exactement deux — `mesures_production` y est une **vue**, pas une hypertable.

Charger ensuite le jeu complet dans l'hypertable — c'est le chargement par `COPY` binaire que M05 mesurera, appliqué ici une bonne fois :

```sql
\i l02/charger-mesures.sql   -- ~190 M lignes, quelques minutes sur 2 vCPU
```

La table de la ligne de base de M02 reste consultable sous le nom `mesures_avant` : le squelette l'a renommée avant de créer l'hypertable.

### Étape 3 — Charger le référentiel (5 min)

```sql
\i l02/charger-referentiel.sql

SELECT (SELECT count(*) FROM sites)                AS sites,
       (SELECT count(*) FROM actifs)               AS actifs,
       (SELECT count(*) FROM signaux)              AS signaux,
       (SELECT count(*) FROM affectation_capteur)  AS affectations;
```

Valeurs attendues : 4 sites, 46 actifs, **25 signaux, 490 affectations** — `signaux` est un catalogue de *types* de signaux ; ce sont les affectations qui matérialisent les 490 séries, une seule affectation courante par série à ce stade.

### Étape 4 — Écrire la jointure au référentiel (10 min)

Produire une requête qui retourne, pour un intervalle de temps donné, chaque mesure enrichie du **site**, de la **machine** et du **libellé du signal** avec son unité.

La jointure doit tenir compte de la période de validité de l'affectation, faute de quoi un capteur remplacé fausse silencieusement l'historique.

```sql
SELECT max(ts) AS fin, max(ts) - interval '1 hour' AS debut
FROM   mesures \gset

SELECT m.ts,
       s.nom       AS site,
       a.machine_id,
       g.libelle,
       g.unite,
       m.valeur
FROM   mesures m
JOIN   affectation_capteur af
  ON   af.series_id = m.series_id
 AND   m.ts >= af.debut
 AND   (af.fin IS NULL OR m.ts < af.fin)
JOIN   actifs  a ON a.machine_id = af.machine_id
JOIN   sites   s ON s.site_id    = a.site_id
JOIN   signaux g ON g.signal_id  = af.signal_id
WHERE  m.ts >= :'debut' AND m.ts < :'fin'
LIMIT  20;
```

Consigner la requête dans `requetes/jointure-referentiel.sql`.

### Étape 5 — Estimer le volume à 3 ans (8 min)

L'estimation porte sur l'**échelle de production**, pas sur l'échelle d'atelier. Le rappel des deux échelles est au slide 3.1 du support ; en cas de doute, poser la question avant de calculer.

Mesurer d'abord le coût réel d'une ligne du schéma retenu :

```sql
-- taille utile d'une ligne, hors en-tête de tuple
SELECT pg_column_size(row(now(), 1::integer, 1.0::float8, 0::smallint))
       AS octets_utiles;
```

Puis appliquer la méthode, en écrivant chaque hypothèse :

1. Points par jour : `4 000 signaux × 0,1 Hz × 86 400 s`
2. Points sur 3 ans : `points/jour × 1 095`
3. Octets par ligne : `octets_utiles + 24` (en-tête de tuple et pointeur de ligne)
4. Volume heap : `points × octets/ligne`
5. Volume d'index : compter environ 30 octets par entrée pour un index sur `(series_id, ts)`

Reporter le résultat et les cinq hypothèses dans `mesures.md`, sous un titre `## M03 — volumétrie à 3 ans`.

### Critères de réussite

- [ ] Les six décisions sont tranchées et **chacune porte une justification écrite d'au moins une phrase**
- [ ] Le squelette complété s'exécute sans erreur et `timescaledb_information.hypertables` retourne les hypertables attendues
- [ ] Le schéma absorbe l'ajout d'un nouveau type de capteur **sans `ALTER TABLE`** — à démontrer en insérant une série d'un type absent du référentiel initial
- [ ] La jointure de l'étape 4 retourne 20 lignes avec site, machine, libellé et unité renseignés
- [ ] Le référentiel affiche 4 / 46 / 25 / 490
- [ ] L'estimation à 3 ans est consignée avec ses cinq hypothèses explicites

---

## EXTENSION — pour aller plus loin

Non évaluée, non attendue. Ces travaux n'entrent pas dans l'état de reprise `mistral-M03` : le module suivant part du socle et de lui seul.

### E1 — Confronter deux propositions

Deux sous-groupes présentent leur schéma au tableau, décision par décision. Arbitrer collectivement, en identifiant les décisions où les deux groupes divergent et pourquoi.

L'objectif n'est pas de désigner un gagnant mais de faire apparaître quelles décisions sont réellement dépendantes du contexte et lesquelles ont une réponse à peu près universelle. Il y en a généralement une de chaque catégorie.

### E2 — Le capteur remplacé

Simuler le remplacement d'un capteur en cours de période :

```sql
-- clore l'affectation courante d'une serie, en ouvrir une nouvelle
UPDATE affectation_capteur
SET    fin = '2026-10-12 00:00:00+02'
WHERE  series_id = 137 AND fin IS NULL;

INSERT INTO affectation_capteur (series_id, machine_id, signal_id, debut, fin)
VALUES (137, 42, 7, '2026-10-12 00:00:00+02', NULL);
```

Rejouer la requête de l'étape 4 sur une fenêtre couvrant le 12 octobre, et vérifier que chaque point est rattaché à la bonne machine de part et d'autre de la bascule.

Écrire ensuite la requête qui **détecte** les séries dont l'affectation présente un trou ou un chevauchement. Sur un référentiel protégé par une contrainte d'exclusion, elle doit retourner zéro ligne — c'est ce qui rend la contrainte défendable.

### E3 — JSONB contre colonnes typées

Créer deux variantes de la table d'événements, l'une avec `attributs JSONB`, l'autre avec trois colonnes typées, et y charger le même jeu de 10 millions de lignes.

Comparer, avant et après passage au columnstore :

```sql
SELECT pg_size_pretty(hypertable_size('evenements_jsonb'))  AS jsonb,
       pg_size_pretty(hypertable_size('evenements_typee'))  AS typee;
```

Documenter le rapport obtenu. La question à laquelle répondre : à partir de quelle proportion de lignes portant réellement des attributs variables JSONB devient-il le bon choix ?

### E4 — La variante en modèle large

Écrire le schéma en modèle large — une colonne par signal, sur une machine — et y charger les mesures d'une seule éolienne sur la fenêtre complète.

Comparer le volume au modèle retenu, ramené au même nombre de points. Puis répondre par écrit : quelle proportion de colonnes creuses annulerait le gain observé ?

---

## Pièges et indices

**La clé primaire est refusée.**
Toute contrainte d'unicité sur une hypertable doit contenir la colonne de partitionnement. Un `PRIMARY KEY (series_id, ts)` fonctionne, un `PRIMARY KEY (series_id)` seul échoue. Ce n'est pas arbitraire : l'unicité globale ne peut pas être garantie sans lire tous les chunks.

**La colonne de temps doit être `NOT NULL`.**
Une ligne sans date n'a pas de chunk d'accueil. L'oubli produit une erreur à la création, pas à l'insertion.

**Les clés étrangères : une seule combinaison est interdite.**
Une clé étrangère entre **deux hypertables** n'est pas autorisée. Toutes les autres combinaisons le sont, y compris une hypertable qui référence une table de référentiel ordinaire, et l'inverse. Poser la contrainte de `mesures` vers `actifs` est donc légitime — reste à décider si c'est souhaitable, ce qui est l'objet de la décision 6.

**Le squelette s'exécute mais aucune hypertable n'apparaît.**
Les options `WITH` ont été écrites sur une table déjà créée, ou mal orthographiées. `WITH (timescaledb.hypertable)` ne produit pas d'erreur si l'option est ignorée sur certaines versions : vérifier systématiquement par `timescaledb_information.hypertables`, jamais par l'absence de message d'erreur.

**L'estimation à 3 ans donne un résultat improbable.**
Vérifier l'échelle utilisée. 190 millions de points sur 45 jours est l'échelle d'atelier ; l'estimation porte sur 4 000 signaux à 0,1 Hz, soit environ 34,5 millions de points **par jour**. Un écart d'un facteur 20 entre deux sous-groupes vient presque toujours de là.

**La jointure au référentiel retourne trop de lignes.**
Les bornes `debut` et `fin` de l'affectation ont été omises. Sans elles, une série ayant eu deux affectations produit deux lignes par point. C'est le mode de défaillance qui rend l'historique faux sans rien signaler.

**Un sous-groupe veut dénormaliser `machine_id` dans `mesures`.**
C'est un choix défendable et fréquent en production, à condition d'en énoncer le prix : corriger une affectation erronée impose alors de réécrire des millions de lignes. La décision 6 attend cette phrase, pas un refus de principe.

---

## Livrable

| Élément | Contenu |
|---|---|
| `schema.sql` | Le squelette complété, avec les six justifications en commentaires |
| `requetes/jointure-referentiel.sql` | La requête de l'étape 4 |
| `mesures.md` | Section `## M03 — volumétrie à 3 ans`, résultat et cinq hypothèses |
| État de reprise | `mistral-M03` |

**Vers la suite.** Les hypertables tournent sur l'intervalle de chunk par défaut du squelette, choisi sans aucune mesure. M04 pose la question que cet atelier a délibérément mise de côté : cet intervalle est-il le bon, et comment le prouver ? Les trois médianes de la ligne de base de M02 servent enfin de point de comparaison.

---

## Note de production

Le corrigé de ce socle **est** `reprise/M03.sql`, qui implémente la variante de référence — modèle intermédiaire par famille, `series_id` entier, `double precision`, colonne `qualite`, événements en JSONB, affectation datée. Ces six choix ne sont pas les seuls défendables ; ils sont ceux que la chaîne d'instantanés matérialise, et l'énoncé le dit aux participants.

`tests/M03.sql` vérifie les six critères de réussite du socle. Le troisième — absorber un nouveau type de capteur sans `ALTER TABLE` — s'y traduit par l'insertion d'une série de `signal_id` inconnu suivie d'une lecture réussie : c'est un test fonctionnel, pas une inspection de schéma, ce qui laisse passer plusieurs modèles corrects.

**Point ouvert** : la syntaxe `WITH (timescaledb.hypertable, timescaledb.partition_column, timescaledb.chunk_interval)` est récente et son vocabulaire a évolué entre versions mineures. Le squelette doit être exécuté sur l'instance 2.29 de référence avant diffusion, et une variante `create_hypertable()` conservée en commentaire pour les environnements plus anciens.
