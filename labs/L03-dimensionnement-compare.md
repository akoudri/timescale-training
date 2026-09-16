# L03 — Dimensionnement comparé

**Module** : M04 · Chunks, index, exclusion
**Durée** : 70 min — socle 60 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M03`
**État de fil rouge en sortie** : `mistral-M04`

---

## Contexte

Depuis M03, `mesures` est une hypertable — mais son intervalle de chunk vient du squelette, choisi sans aucune mesure. Cet atelier remplace cette valeur par défaut par une décision, et fournit la preuve qui la soutient.

Il produit aussi le **premier gain chiffré de la formation** : les trois requêtes de référence de M02 ont été mesurées sur une table ordinaire. Elles sont rejouées ici sur l'hypertable. L'écart est la première dette remboursée depuis l'amorce de M01.

**Une limite à énoncer d'emblée.** Comparer trois intervalles impose trois copies des données. À l'échelle complète, cela représente près de six cents millions de lignes et plus d'une heure de chargement. Les trois copies portent donc sur un **échantillon de cinquante séries** sur la fenêtre complète, soit environ 19 millions de lignes chacune. Cet échantillon isole correctement l'effet du **nombre de chunks** — planification, exclusion, granularité. Il ne permet pas d'observer l'effet du **volume du chunk actif** sur le débit d'insertion, qui suppose de saturer la mémoire : cette mesure-là est faite à l'échelle réelle en M05.

Le dire aux participants. Un atelier qui prétend démontrer plus qu'il ne démontre coûte plus cher qu'un atelier modeste.

---

## Prérequis

**État attendu**

- `mistral-M03` atteint : `schema.sql` exécuté, hypertables créées et chargées
- `mesures.md` contient la section `## M02 — ligne de base` avec les trois médianes
- L'instance est épinglée et vérifiée

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l03/creer-comparaison.sql` | Crée `mesures_1j`, `mesures_7j`, `mesures_30j` et charge l'échantillon |
| `l03/releves.sql` | Les trois relevés structurels, paramétrés par nom de table |
| `requetes/R1-dernier-point.sql` · `R2-fenetre-3j.sql` · `R3-agregation-fenetre.sql` | Les trois profils de requête, paramétrés par nom de table (`mesure.sh --table`) |
| `l03/exclusion/Q1.sql` … `Q5.sql` | Les cinq requêtes de l'étape 4 |
| `mesures.md` | Journal de bord, tableaux d'en-têtes déjà en place |

---

## SOCLE — pour tous

### Étape 1 — Rembourser la première dette (15 min)

Rejouer d'abord les trois requêtes de référence de M02 sur `mesures` devenue hypertable (45 jours) :

```bash
./mesure.sh requetes/R1-dernier-point.sql
./mesure.sh requetes/R2-fenetre-3j.sql
./mesure.sh requetes/R3-agregation-fenetre.sql
```

**Premier constat à faire, et à expliquer** : comparer ces trois médianes à la ligne de base de M02. Le rapport n'est pas celui qu'on attend d'un partitionnement, et R1 se distingue nettement. Avant de continuer, écrire en une phrase pourquoi — la réponse tient à ce que contenait la table de M02, et à ce que contient l'hypertable aujourd'hui. Savoir l'expliquer est le premier critère de l'atelier.

La dette se mesure ensuite contre la table ordinaire **à l'échelle réelle** : `l03/creer-comparaison.sql` a créé `mesures_ord`, copie ordinaire éphémère des 45 jours. Rejouer les trois requêtes dessus :

```bash
for r in R1-dernier-point R2-fenetre-3j R3-agregation-fenetre; do
  ./mesure.sh requetes/$r.sql --table mesures_ord
done
```

Reporter les six médianes dans `mesures.md`, sous `## M04 — après conversion en hypertable`, et **calculer le rapport hypertable / table ordinaire 45 j pour chacune**. Observer laquelle des trois profite le plus, et savoir dire pourquoi : les gains ne sont pas du même ordre, et la raison tient à l'exclusion de chunks. `mesures_ord` est supprimée en fin d'atelier.

### Étape 2 — Créer les trois hypertables de comparaison (15 min)

```sql
\i l03/creer-comparaison.sql
```

Le script crée trois hypertables au schéma identique, d'intervalles 1 jour, 7 jours et 30 jours, et y charge le même échantillon de cinquante séries sur la fenêtre complète. Le chargement se fait par `COPY`, sans index secondaire, l'index étant créé après.

Vérifier que les trois contiennent le même nombre de lignes :

```sql
SELECT 'mesures_1j'  AS t, count(*) FROM mesures_1j
UNION ALL SELECT 'mesures_7j',  count(*) FROM mesures_7j
UNION ALL SELECT 'mesures_30j', count(*) FROM mesures_30j;
```

Un écart entre les trois invalide toute la comparaison qui suit. Vérifier avant de mesurer, pas après.

### Étape 3 — Les relevés et les neuf mesures (20 min)

**Relevés structurels**, pour chacune des trois tables. Les bornes se calculent d'abord depuis la table (mêmes jours que le harnais : 3 à 5 de la fenêtre), puis servent à l'`EXPLAIN` :

```sql
-- bornes, calculees du jeu (a refaire pour chaque table)
SELECT min(ts) + interval '2 days' AS fen3,
       min(ts) + interval '5 days' AS fin
FROM   mesures_7j \gset

-- nombre de chunks
SELECT count(*) FROM timescaledb_information.chunks
WHERE  hypertable_name = 'mesures_7j';

-- volume total
SELECT pg_size_pretty(hypertable_size('mesures_7j'));

-- temps de planification : lire la ligne Planning Time
EXPLAIN SELECT avg(valeur) FROM mesures_7j
WHERE  ts >= :'fen3' AND ts < :'fin';
```

Le script `l03/releves.sql` regroupe les trois relevés pour une table passée en variable : `\set table mesures_7j` puis `\i l03/releves.sql`, après le `\gset` ci-dessus.

**Neuf mesures** : les trois profils R1, R2, R3 sur chacune des trois tables.

```bash
for t in 1j 7j 30j; do
  for r in R1-dernier-point R2-fenetre-3j R3-agregation-fenetre; do
    ./mesure.sh requetes/$r.sql --table mesures_$t
  done
done
```

Remplir le tableau de `mesures.md` :

| Grandeur relevée | 1 jour | 7 jours | 30 jours |
|---|---|---|---|
| Nombre de chunks | | | |
| Volume total | | | |
| Temps de planification | | | |
| R1 · point le plus récent | | | |
| R2 · fenêtre de 3 jours | | | |
| R3 · agrégation complète | | | |

Toute mesure dont l'écart-type dépasse 20 % est relancée, pas reportée.

### Étape 4 — Trouver la requête qui n'exclut rien (15 min)

Cinq requêtes retournant toutes un résultat correct sur `mesures_1j`. Elles ne se comportent pas de la même façon devant le planificateur.

Pour chacune, produire le plan et classer le comportement :

```sql
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF) ...
```

| | Écriture | Comportement à identifier |
|---|---|---|
| Q1 | `WHERE ts >= '…' AND ts < '…'` | Référence |
| Q2 | `WHERE EXTRACT(hour FROM ts) = 14 AND ts >= '…' AND ts < '…'` | ? |
| Q3 | `PREPARE p(timestamptz, timestamptz) AS … ; EXECUTE p('…','…')` | ? |
| Q4 | `WHERE ts >= (SELECT max(ts) - interval '3 days' FROM mesures_1j)` | ? |
| Q5 | `WHERE date_trunc('day', ts) = '2026-10-01'` | ? |

Trois catégories, et une seule des cinq relève de la troisième :

- **exclusion à la planification** — les chunks écartés n'apparaissent pas dans le plan
- **exclusion à l'exécution** — tous les chunks figurent dans le plan, l'élimination se lit sur une ligne dédiée au démarrage
- **aucune exclusion** — tous les chunks sont lus

Corriger la requête de la troisième catégorie, mesurer le gain, et le consigner.

**Q2 mérite une attention particulière** : elle contient une fonction appliquée à la colonne de temps. Classer d'abord d'après le plan, expliquer ensuite — c'est la différence entre appliquer une recette et comprendre le mécanisme.

### Étape 5 — Trancher et inscrire (8 min)

Écrire dans `schema.sql` — le squelette complété en L02, copié à la racine d'`atelier/` ; s'il manque, `cp l02/schema-squelette.sql schema.sql` — en commentaire au-dessus de la définition de `mesures`, l'intervalle retenu et **la mesure qui le justifie** — une phrase, un chiffre.

Si la mesure conduit à un intervalle différent de celui du squelette, l'appliquer :

```sql
SELECT set_chunk_time_interval('mesures', INTERVAL '<retenu>');
```

Rappel : cet appel ne concerne que les chunks à venir. Les chunks existants gardent leur intervalle, ce qui est licite et parfaitement visible dans le catalogue.

### Critères de réussite

- [ ] Les trois rapports avec la ligne de base de M02 sont calculés et consignés
- [ ] Les trois tables de comparaison contiennent le même nombre de lignes
- [ ] Les six lignes du tableau sont renseignées pour les trois intervalles, écarts-types sous 20 %
- [ ] Les cinq requêtes sont classées dans les trois catégories, et le classement est exact
- [ ] La requête sans exclusion est corrigée et son gain est mesuré
- [ ] L'intervalle retenu figure dans `schema.sql` **avec le chiffre qui le justifie**
- [ ] Le participant sait montrer l'exclusion de chunks dans un plan à un voisin
- [ ] `mesures_ord` et les tables de comparaison sont supprimées

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M04`.

### E1 — L'intervalle absurde

Créer `mesures_1h` sur le même échantillon, en chunks d'une heure. La fenêtre complète produit environ 1 080 chunks.

Mesurer le temps de planification de R2, et le rapporter au nombre de chunks. Comparer à la même grandeur sur les trois autres tables. La question à laquelle répondre : le coût de planification croît-il linéairement avec le nombre de chunks, ou plus vite ?

Relever également la taille du catalogue :

```sql
SELECT pg_size_pretty(pg_total_relation_size('_timescaledb_catalog.chunk'))
       AS catalogue_chunks;
```

### E2 — Voir l'exclusion à l'exécution

Reprendre Q3 et lire attentivement le plan complet. Tous les chunks y figurent ; l'élimination apparaît sur une ligne distincte, produite au démarrage de l'exécution.

Mesurer ensuite le temps de planification de Q1 et de Q3 sur `mesures_1h`. C'est là que la différence devient spectaculaire, et c'est exactement ce qui arrive à une application qui utilise des requêtes préparées sur une hypertable à mille chunks.

### E3 — Le coût d'un index inutile

Sur `mesures_7j`, mesurer le débit d'insertion de 2 millions de lignes en trois configurations :

1. index par défaut seul
2. index par défaut + `(series_id, ts DESC)`
3. les deux précédents + un index sur `series_id` seul, qui est redondant

Chiffrer le coût du troisième index en débit d'insertion et en volume sur disque. C'est la mesure que M05 reprend à l'échelle, sur trois stratégies d'écriture.

### E4 — L'intervalle à l'échelle de production

Recalculer l'intervalle théorique pour 4 000 signaux à 0,1 Hz sur un serveur de 64 Go, en reprenant la méthode du slide 4.1.

Puis répondre par écrit : pour quel dimensionnement de serveur l'intervalle théorique passerait-il sous la journée, et cette configuration a-t-elle un sens ?

---

## Pièges et indices

**Le temps de planification n'apparaît pas dans la sortie.**
Il se lit sur la ligne `Planning Time`, produite par `EXPLAIN` avec ou sans `ANALYZE`. C'est cette grandeur qui trahit la prolifération de chunks, pas le temps d'exécution — et c'est celle que l'on oublie systématiquement de relever.

**Les trois tables n'ont pas le même nombre de lignes.**
Le chargement d'une des trois a été interrompu, ou la fenêtre de l'échantillon a été modifiée entre deux exécutions. Toute la comparaison est invalidée. Recharger, ne pas corriger le tableau à la main.

**Changer l'intervalle sur une table existante ne change rien aux mesures.**
`set_chunk_time_interval` ne touche pas les chunks déjà créés. Comparer trois intervalles exige trois hypertables distinctes, pas trois réglages successifs sur la même. C'est l'erreur la plus fréquente de cet atelier.

**R1 est identique sur les trois tables.**
C'est attendu. « Le point le plus récent » ne lit qu'un seul chunk quel que soit l'intervalle. Le profil est dans le jeu précisément pour montrer que tous les profils ne sont pas sensibles au dimensionnement — un point que la comparaison à deux profils seulement aurait masqué.

**La requête fautive semble rapide.**
Sur sept chunks, tout lire n'est pas dramatique : le chronomètre ne trahit rien. C'est le **plan** qu'il faut regarder, puis extrapoler à mille chunks. L'extension E2 rend cette extrapolation concrète.

**Q2 exclut alors qu'elle contient une fonction sur la colonne de temps.**
Les bornes littérales sont présentes en plus du prédicat `EXTRACT`. Le planificateur exclut sur les bornes, puis filtre le reste. Un prédicat non sargable n'est fatal que lorsqu'il est **le seul** prédicat temporel.

**Face à la ligne de base de M02, l'hypertable perd — et c'est normal.**
La ligne de base portait sur 5 jours ; l'hypertable en porte 45. Le rapport qui compte est celui contre `mesures_ord` (45 j en table ordinaire). Et sur cette comparaison-là, le gain de R3 reste modeste : une agrégation bornée sur les jours 1-5 n'exclut que ce qui est hors fenêtre — le gain massif viendra du columnstore en M09 et des agrégats continus en M08, pas du partitionnement seul.

---

## Livrable

| Élément | Contenu |
|---|---|
| `mesures.md` | Section `## M04` : trois rapports avec la ligne de base, tableau de neuf mesures et trois relevés, gain de la requête corrigée |
| `schema.sql` | Intervalle retenu en commentaire, avec le chiffre qui le justifie |
| `l03/exclusion/classement.md` | Les cinq requêtes classées dans les trois catégories |
| État de reprise | `mistral-M04` |

## Nettoyage

À faire en fin d'atelier, extensions comprises : ce qui n'appartient pas à l'état de reprise part.

L'atelier a créé une copie ordinaire de 45 jours et trois hypertables de comparaison : plus de quinze gigaoctets qui n'entrent pas dans l'état de reprise `mistral-M04`.

```sql
DROP TABLE mesures_ord;                              -- 11 Go, plus aucun usage
DROP TABLE mesures_1j, mesures_7j, mesures_30j;      -- à garder seulement pour l'extension E1
```

L'espace est rendu au système de fichiers immédiatement — c'est l'un des arguments de M10, constaté ici en passant. Vérifier avec `\dt+` ou `df -h` que le volume est bien redescendu.

---

**Vers la suite.** Cet atelier a mesuré des lectures. Il a délibérément laissé de côté l'effet du dimensionnement sur les **écritures**, qui suppose de saturer la mémoire à l'échelle réelle. C'est le premier objet de M05, avec une question à laquelle la ligne de base ne répond pas encore : combien de points par seconde cette instance accepte-t-elle réellement, et qu'est-ce qui l'en empêche ?
