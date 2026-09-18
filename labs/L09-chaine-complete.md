# L09 — La chaîne complète

**Module** : M10 · Cycle de vie de la donnée
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M09`
**État de fil rouge en sortie** : `mistral-M10`

---

## Contexte

Trois politiques vont désormais coexister sur la même hypertable : rafraîchissement des agrégats (M08), bascule en columnstore (M09), et rétention (ce module). Elles ne sont pas indépendantes, et l'ordre dans lequel leurs **fenêtres** se recouvrent décide si la chaîne est cohérente ou si elle produit silencieusement du vide.

**Une difficulté d'échelle, à énoncer avant de commencer.** La cible de production est « 7 jours en rowstore, 90 jours en columnstore, agrégats horaires conservés 10 ans ». Le jeu d'atelier ne couvre que 45 jours : avec ces valeurs, la rétention ne supprimerait jamais rien et l'atelier ne montrerait rien.

L'atelier applique donc des **valeurs réduites** — 2 jours, 30 jours — pour rendre l'effet observable, et écrit **séparément** la cible de production dans `politiques.sql`. Les deux jeux de valeurs cohabitent dans le fichier, chacun clairement étiqueté. C'est la même discipline des deux échelles qu'en L02 et L08.

---

## Prérequis

**État attendu**

- `mistral-M09` atteint : compression configurée et chunks basculés
- La pyramide de M08 tourne, avec ses trois politiques de rafraîchissement
- Les workers d'arrière-plan sont actifs

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l09/etat-chunks.sql` | Nombre et état des chunks, par hypertable |
| `l09/bornes.sql` | Les bornes d'atelier de la bascule et de la rétention, calculées depuis le jeu, avec le garde-fou des deux horloges |
| `l09/coherence-fenetres.sql` | Le contrôle de l'étape 3 |
| `l09/economie.sql` | Volumes avant et après, et extrapolation |
| `politiques.sql` | Produit en M09, à compléter ici |

---

## SOCLE — pour tous

### Étape 1 — Appliquer la chaîne (12 min)

Relever d'abord l'état de départ, il servira de référence à l'étape 4 :

```sql
\i l09/etat-chunks.sql
```

Puis compléter la chaîne. Le rafraîchissement est en place depuis M08, la bascule depuis M09 ; il manque la rétention.

```sql
-- ATELIER : valeurs reduites, pour que l'effet soit observable sur 45 jours
SELECT add_retention_policy('mesures', INTERVAL '30 days');
```

Relever les deux politiques côte à côte, et noter que la bascule tranchée en M09 (7 jours) reste enregistrée telle quelle : c'est une valeur de production, elle ne bouge pas. La valeur d'atelier de la bascule — 2 jours — n'est pas un réglage de la politique mais la **borne explicite** appliquée ci-dessous ; les deux valeurs seront étiquetées dans `politiques.sql`.

```sql
SELECT job_id, proc_name, config
FROM   timescaledb_information.jobs
WHERE  proc_name LIKE '%compression%' OR proc_name LIKE '%retention%';
```

**Le jeu est daté.** Une politique relative à `now()` — c'est le cas de la bascule et de la rétention — ne trouve aucun chunk à traiter tant que la session précède la fenêtre du jeu : elle s'exécute, réussit, et ne fait rien. Les politiques restent enregistrées (c'est leur structure et leur supervision que M11 étudie) ; l'effet, lui, se déclenche à borne explicite, calculée depuis le dernier point du jeu :

```sql
\i l09/bornes.sql        -- borne_bascule = max(ts) − 2 j, borne_retention = max(ts) − 30 j

SELECT compress_chunk(c)
FROM   show_chunks('mesures', older_than => :'borne_bascule'::timestamptz) c;
SELECT drop_chunks('mesures', older_than => :'borne_retention'::timestamptz);
```

Règle générale, valable pour tout l'atelier : tout énoncé qui dépend de l'horloge murale se raisonne en temps relatif au jeu (`max(ts)`), jamais en `now()`. Le script de bornes applique une exception, et l'affiche quand elle joue : si la date de la session tombe dans la fenêtre du jeu, la rétention d'atelier ne doit pas emporter les chunks où se trouve `now()`, parce que les politiques de rafraîchissement de M08, elles, y regardent — voir le piège « les deux horloges ».

### Étape 2 — Vérifier l'état des chunks (8 min)

```sql
\i l09/etat-chunks.sql
```

L'état attendu sur `mesures`, après exécution :

| Zone | État attendu |
|---|---|
| Moins de 2 jours | chunks en rowstore |
| De 2 à 30 jours | chunks en columnstore |
| Au-delà de 30 jours | chunks supprimés |

**Le résultat ne sera pas exactement celui-là, et c'est normal.** Consigner le nombre de chunks dans chaque zone, comparer aux bornes annoncées, et **écrire d'une phrase pourquoi la frontière n'est pas nette**. La réponse tient à la granularité de ce que la rétention supprime, et donc à une décision prise en M04.

Vérifier ensuite que les agrégats, eux, n'ont rien perdu :

```sql
SELECT min(seau), max(seau), count(*) FROM mistral_1h;
```

Les agrégats couvrent toujours les 45 jours, alors que les mesures brutes ne couvrent plus que 30. C'est exactement l'effet recherché par le downsampling.

### Étape 3 — Vérifier la cohérence des fenêtres (7 min)

Le contrôle qui empêche l'erreur du bloc 10.2.

```sql
\i l09/coherence-fenetres.sql
```

Le script rapproche, pour chaque hypertable, trois grandeurs :

- la portée du rafraîchissement de l'agrégat qui la consomme (`start_offset`)
- le délai de bascule en columnstore
- le seuil de rétention

**La règle à vérifier** : le seuil de rétention doit être strictement supérieur à la portée du rafraîchissement. Si la rétention coupe à 30 jours et que le rafraîchissement remonte à 35, chaque passage matérialise du vide sur les cinq jours manquants — et écrase des valeurs auparavant correctes.

Écrire la vérification en une ligne dans `politiques.sql`, en commentaire, avec les trois valeurs.

### Étape 4 — Chiffrer l'économie (8 min)

```sql
\i l09/economie.sql
```

Produire deux chiffres, et les distinguer clairement :

**Sur l'échelle d'atelier** — volume occupé par `mesures` avant et après application de la chaîne, agrégats compris. Attention : la pyramide de M08 ajoute du volume. L'économie nette est ce qui reste après l'avoir déduite.

**Sur l'échelle de production** — reprendre l'estimation à 3 ans de L02, appliquer le ratio de compression mesuré en L08 et la rétention retenue, et chiffrer le volume final.

Écrire enfin dans `politiques.sql` la **cible de production**, distincte des valeurs d'atelier :

```sql
-- PRODUCTION : cible retenue, non applicable au jeu d'atelier
--   rowstore     : 7 jours
--   columnstore  : 90 jours
--   retention brut : 90 jours
--   agregat 1 min  : 1 an
--   agregat 1 h    : 10 ans
--   agregat 1 jour : sans limite
-- Volume estime a 3 ans : ...
```

### Critères de réussite

- [ ] Les trois politiques sont enregistrées et se sont exécutées au moins une fois
- [ ] L'état des chunks est conforme aux trois zones, aux effets de bord de granularité près
- [ ] **La raison pour laquelle la frontière n'est pas nette est écrite**, et rattachée à l'intervalle de chunk
- [ ] Les agrégats couvrent toujours 45 jours alors que le brut n'en couvre plus que 30
- [ ] Le contrôle de cohérence des fenêtres passe, et les trois valeurs sont consignées
- [ ] L'économie est chiffrée **sur les deux échelles**, la pyramide déduite de l'échelle d'atelier
- [ ] `politiques.sql` contient les valeurs d'atelier **et** la cible de production, étiquetées

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M10`.

### E1 — Provoquer l'agrégat vide

Sur une copie de travail, régler délibérément la rétention à 20 jours alors que le rafraîchissement remonte à 25. Déclencher les deux travaux dans le mauvais ordre, puis interroger l'agrégat sur la zone de recouvrement.

Constater que les valeurs auparavant correctes ont été remplacées par du vide, **sans erreur ni avertissement**. Écrire ensuite la requête de détection qui aurait signalé l'anomalie — elle deviendra une des alertes de M15.

### E2 — Les politiques de l'agrégat lui-même

Appliquer compression et rétention au niveau minute de la pyramide, et mesurer le gain en volume.

Répondre ensuite : le niveau minute représente quelle part du volume total après application de la chaîne ? Le résultat surprend généralement.

### E3 — Le stockage étagé, chiffré

Sur l'instance managée, appliquer un étagement sur les chunks les plus anciens et relever le volume déplacé.

Reprendre le calcul de production de l'étape 4 avec et sans étagement, à partir des tarifs de `l09/tarifs-stockage.md`. L'écart entre les deux chiffres est l'argument financier de l'arbitrage — et il ne vaut qu'en service managé.

### E4 — Suppression de chunk contre DELETE

Chronométrer `drop_chunks` sur un chunk, puis un `DELETE` couvrant exactement la même plage sur un chunk équivalent.

Relever trois grandeurs pour chacun : la durée, le volume de journal produit, et l'espace disque rendu immédiatement. Le troisième chiffre est le plus parlant.

---

## Pièges et indices

**Les deux horloges : la session tombe dans la fenêtre du jeu.**
Le jeu se lit à l'horloge de `max(ts)`, les politiques de rafraîchissement des agrégats à l'horloge murale. Tant que la session précède la fenêtre, les deux ne se rencontrent pas. Si elle tombe dedans, une purge bornée sur le jeu qui emporte les chunks où se trouve `now()` déclenche exactement l'erreur du bloc 10.2 : à chaque passage, la politique matérialise du vide sur sa fenêtre et efface, sans erreur, des valeurs qui étaient justes — d'abord au niveau minute, puis à l'heure et au jour, de proche en proche. `l09/bornes.sql` plafonne la borne de rétention pour l'éviter et le signale ; la purge observée à l'étape 2 est alors plus courte que les trente jours annoncés, et il faut le dire plutôt que forcer la borne. Si la session est postérieure à la fenêtre, aucune borne ne protège : bascule et rétention relatives à `now()` agissent pour de vrai, et le jeu doit être régénéré avec une fenêtre future (fiche AMONT, étape 4). Le contrôle de l'étape 3 vérifie ce point en plus de la règle rétention > portée.

**La rétention ne supprime rien.**
Deux causes possibles. Soit le seuil est plus large que la fenêtre du jeu — vérifier qu'on utilise bien les valeurs d'atelier et non celles de production. Soit aucun chunk n'est **entièrement** antérieur à la limite : c'est l'effet de granularité, et il faut le comprendre plutôt que d'élargir le seuil au hasard.

**L'agrégat devient vide sur une plage.**
La rétention coupe sous la portée du rafraîchissement. C'est l'erreur du bloc 10.2, elle ne produit aucun message, et l'étape 3 existe précisément pour l'éviter.

**Le stockage étagé n'est pas disponible.**
Il n'existe qu'en service managé. La démonstration se fait sur l'instance managée du binôme, jamais sur le conteneur local — la fonction n'y est pas.

**L'économie chiffrée paraît trop belle.**
Deux vérifications. La pyramide de M08 a-t-elle été déduite du volume final ? Et l'extrapolation à trois ans part-elle bien de l'échelle de production, ou multiplie-t-elle par erreur les chiffres d'atelier par cinq cents ?

**Les deux jeux de valeurs se mélangent.**
Étiqueter `ATELIER` et `PRODUCTION` dans `politiques.sql` dès l'écriture, pas après. C'est le fichier que le participant emportera, et une valeur d'atelier appliquée en production détruirait des données.

**`run_job` échoue avec une erreur de transaction.**
Comme `refresh_continuous_aggregate`, il ne peut pas s'exécuter dans une transaction explicite.

---

## Livrable

| Élément | Contenu |
|---|---|
| `politiques.sql` | La chaîne complète, valeurs d'atelier et cible de production étiquetées, contrôle de cohérence en commentaire |
| `mesures.md` §`M10` | État des chunks par zone, économie sur les deux échelles |
| `l09/granularite.md` | La phrase expliquant pourquoi la frontière de rétention n'est pas nette |
| État de reprise | `mistral-M10` |

**Vers la suite.** Cinq travaux automatiques tournent désormais sur MISTRAL, et personne ne les a jamais regardés. M11 les met sous surveillance, et ajoute le premier travail qui ne soit pas une politique du produit mais une tâche métier.
