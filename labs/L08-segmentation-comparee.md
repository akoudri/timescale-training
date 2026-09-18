# L08 — Segmentation comparée

**Module** : M09 · Hypercore et columnstore
**Durée** : 60 min — socle 55 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M08`
**État de fil rouge en sortie** : `mistral-M09`

---

## Contexte

Le lab le plus décisif de la formation. Un `segmentby` mal choisi divise le ratio de compression par quatre **et** rend les requêtes filtrées plus lentes qu'avant la bascule. Aucune autre décision du programme n'a un tel écart entre le bon et le mauvais choix.

**Une limite de protocole, comme en L03.** On ne bascule pas 190 millions de lignes trois fois en une heure. Les trois configurations portent sur **deux jours de données**, chargées dans trois hypertables distinctes à chunks journaliers. Le ratio de compression se mesure chunk par chunk : la fenêtre réduite ne le fausse pas, à condition que les chunks soient pleins.

**Et surtout**, l'atelier introduit `mesures_hc` — 20 000 séries au lieu de 490. C'est le seul endroit de la formation où la cardinalité, nommée dès M01, devient un chiffre. Sans cette étape, elle reste une affirmation.

---

## Prérequis

**État attendu**

- `mistral-M08` atteint, pyramide d'agrégats en place
- `mesures.md` contient la section `## M05 — retard d'arrivée`
- `mesures_hc` est restauré (parcours amont) : 20 000 séries, pas de 15 minutes, 7 jours

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l08/creer-configurations.sql` | Crée `cmp_serie`, `cmp_machine`, `cmp_aucun` et charge deux jours |
| `l08/basculer.sql` | Bascule tous les chunks pleins d'une table donnée |
| `l08/ratios.sql` | Relève ratio et volumes, chunk par chunk |
| `l08/R1.sql` · `R2.sql` · `R3.sql` | Les trois profils, paramétrés par nom de table |
| `mesures.md` | Journal de bord, tableau d'en-têtes en place |

---

## SOCLE — pour tous

### Étape 1 — Préparer les trois configurations (15 min)

```sql
\i l08/creer-configurations.sql
```

Le script crée trois hypertables au schéma identique, à **chunks journaliers**, et y charge les deux mêmes jours de MISTRAL — 490 séries, environ 8,5 millions de lignes chacune. Elles ne diffèrent que par leur configuration de bascule :

```sql
-- cmp_serie
ALTER TABLE cmp_serie SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'series_id',
  timescaledb.compress_orderby   = 'ts DESC');

-- cmp_machine : segment sur une colonne de cardinalité bien plus faible
ALTER TABLE cmp_machine SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'machine_id',
  timescaledb.compress_orderby   = 'ts DESC');

-- cmp_aucun : aucun regroupement
ALTER TABLE cmp_aucun SET (
  timescaledb.compress,
  timescaledb.compress_orderby   = 'ts DESC');
```

Vérifier que les trois contiennent le même nombre de lignes et le même nombre de chunks **avant** de basculer. Un écart invalide toute la comparaison.

### Étape 2 — Basculer et relever les ratios (12 min)

```sql
\set table cmp_serie
\i l08/basculer.sql
\set table cmp_machine
\i l08/basculer.sql
\set table cmp_aucun
\i l08/basculer.sql
```

`\i` ne prend pas d'argument : le script lit le nom de la table dans la variable psql `table`, comme `l08/ratios.sql`.

Ne basculer que les **chunks pleins**. Un chunk partiel donne un ratio flatteur et non représentatif — le script filtre déjà sur ce critère, mais il faut savoir pourquoi.

```sql
SELECT pg_size_pretty(before_compression_total_bytes) AS avant,
       pg_size_pretty(after_compression_total_bytes)  AS apres,
       round(before_compression_total_bytes::numeric
             / after_compression_total_bytes, 1)      AS ratio
FROM   hypertable_compression_stats('cmp_serie');
```

Le ratio chunk par chunk, qui seul permet de vérifier que les chunks comparés sont pleins, est dans `l08/ratios.sql` (même convention `\set table`).

Reporter les trois ratios dans `mesures.md`.

### Étape 3 — Les trois profils de requête (13 min)

```bash
for t in cmp_serie cmp_machine cmp_aucun; do
  for r in R1 R2 R3; do ./mesure.sh l08/$r.sql --table $t; done
done
```

R1 est le point le plus récent d'une série, R2 une fenêtre de trois jours filtrée sur une série, R3 une agrégation sur toute la fenêtre sans filtre de série.

**Ce qu'il faut observer** : laquelle des trois requêtes creuse l'écart entre les configurations, et sur laquelle des trois tables. L'expliquer par le mécanisme du slide 14 — ce que le prédicat de la requête a le droit d'éliminer avant toute décompression.

### Étape 4 — Le coût d'une correction (5 min)

```sql
\timing on
UPDATE cmp_serie SET valeur = valeur * 1.01
WHERE  series_id = 137 AND ts >= '<jour 1>' AND ts < '<jour 1>'::date + 1;
```

Rejouer le même `UPDATE` sur une période **non basculée**, et comparer. Consigner le rapport.

C'est ce chiffre, et non une intuition, qui doit décider du délai de bascule à l'étape 6.

### Étape 5 — La cardinalité, en chiffres (10 min)

Basculer `mesures_hc` avec la configuration `segmentby = 'series_id'` — la même que `cmp_serie` — et relever son ratio.

Comparer au ratio de `cmp_serie`, obtenu avec la même configuration. **L'écart doit être expliqué et chiffré**, pas constaté.

```sql
-- nombre de lignes par segment et par chunk
SELECT 'cmp_serie'   AS table_, count(*) / count(DISTINCT series_id) AS lignes_par_segment
FROM   cmp_serie WHERE ts >= '<jour 1>' AND ts < '<jour 1>'::date + 1
UNION ALL
SELECT 'mesures_hc', count(*) / count(DISTINCT series_id)
FROM   mesures_hc WHERE ts >= '<jour 1>' AND ts < '<jour 1>'::date + 1;
```

**L'explication à écrire** rapproche ces deux nombres de la taille maximale d'un lot de compression, vue au bloc 9.2. Elle tient en trois phrases : ce qu'est un lot, ce qui se passe quand un segment en remplit plusieurs, et ce qui se passe quand il n'en remplit pas un.

### Étape 6 — Trancher (5 min)

Écrire dans `politiques.sql` la configuration retenue pour MISTRAL, avec :

- le ratio mesuré qui la justifie
- le délai de bascule retenu
- **la vérification explicite que ce délai dépasse le retard d'arrivée mesuré en M05**

```sql
ALTER TABLE mesures SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = '<retenu>',
  timescaledb.compress_orderby   = '<retenu>');

SELECT add_compression_policy('mesures', INTERVAL '<retenu>');
-- justification : ratio mesuré N, retard d'arrivée p99 = X, marge = Y
```

### Critères de réussite

- [ ] Les trois tables contiennent le même nombre de lignes et de chunks avant bascule
- [ ] Les trois ratios sont relevés sur des chunks pleins uniquement
- [ ] Les neuf mesures de requête sont consignées
- [ ] **L'écart de ratio entre la meilleure et la pire configuration est chiffré**
- [ ] Le ratio de `mesures_hc` est relevé, et **expliqué par le nombre de lignes par segment et par chunk**, calculé
- [ ] Le coût d'un `UPDATE` avant et après bascule est chiffré
- [ ] Le délai de bascule retenu est justifié, et sa marge sur le retard d'arrivée de M05 est explicite
- [ ] Les trois tables `cmp_*` sont supprimées

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M09`.

### E1 — Voir l'élimination de lots

Sur `cmp_serie`, produire le plan de R2 avec et sans le prédicat sur `series_id`. Relever, dans la sortie, le nombre de lots traités dans les deux cas.

C'est la mesure directe du mécanisme du slide 14. Refaire l'exercice sur `cmp_aucun` et constater que le nombre ne change pas.

### E2 — Le retour en rowstore

Chronométrer la décompression d'un chunk complet, puis sa recompression. Comparer à la durée de la bascule initiale.

Répondre : dans quels cas de production cette opération est-elle nécessaire, et quelle fenêtre de maintenance faut-il prévoir pour un chunk de trente jours à l'échelle de production ?

### E3 — Le ratio, colonne par colonne

Comparer les volumes compressés de chaque colonne prise séparément : horodatage, identifiant de série, valeur, drapeau de qualité.

L'horodatage compresse le mieux — expliquer pourquoi en une phrase, puis en déduire ce que cela implique pour le choix de `orderby`.

### E4 — L'économie à l'échelle de production

Reprendre l'estimation de volume à 3 ans de L02, appliquer le ratio mesuré, et chiffrer l'économie annuelle en euros à partir des tarifs de `l08/tarifs-stockage.md`.

Produire ensuite le même calcul avec le stockage étagé, dont M10 traite la disponibilité. L'écart entre les deux chiffres est l'argument financier du module suivant.

---

## Pièges et indices

**La bascule échoue ou traîne beaucoup sur les chunks récents.**
Un chunk encore alimenté coûte cher à basculer. Ne compresser que des chunks situés au-delà de la fenêtre de données tardives mesurée en M05 — c'est exactement la raison d'être du délai de bascule.

**Le ratio mesuré est bien meilleur qu'attendu.**
Vérifier que le chunk mesuré est plein. Un chunk partiel — le premier ou le dernier de la fenêtre — donne un ratio flatteur qui ne se reproduira pas en production.

**Les trois configurations ne portent pas sur les mêmes chunks.**
Le ratio varie d'un chunk à l'autre selon la densité des données. Comparer chunk par chunk, ou sur exactement la même plage temporelle.

**`mesures_hc` donne un mauvais ratio.**
C'est le résultat attendu, et c'est toute la leçon de l'étape 5. Ne pas chercher d'erreur de configuration : calculer le nombre de lignes par segment et par chunk, et l'explication apparaît d'elle-même.

**R2 n'est pas plus rapide sur `cmp_serie`.**
Vérifier que la requête filtre bien sur la colonne de segment, et pas sur une colonne dérivée ou jointe. Le mécanisme d'élimination de lots n'opère que sur les colonnes de segment et de tri.

**L'`UPDATE` de l'étape 4 ne se termine pas.**
La plage visée couvre plusieurs chunks basculés. Restreindre à un seul chunk : l'objet de la mesure est le rapport, pas le volume traité.

**Le délai de bascule retenu est plus court que le retard d'arrivée.**
C'est une faute de conception, pas un réglage agressif. Elle se paiera à chaque correction tardive, et le coût mesuré à l'étape 4 en donne l'ordre de grandeur.

---

## Livrable

| Élément | Contenu |
|---|---|
| `politiques.sql` | Configuration de compression tranchée, délai de bascule justifié |
| `mesures.md` §`M09` | Trois ratios, neuf mesures, ratio `mesures_hc`, lignes par segment, coût de l'`UPDATE` |
| `l08/cardinalite.md` | L'explication écrite de l'écart de ratio, chiffres à l'appui |
| État de reprise | `mistral-M09` |

## Nettoyage

À faire en fin d'atelier, extensions comprises : ce qui n'appartient pas à l'état de reprise part.

Les trois tables de comparaison ne font pas partie de l'état de reprise `mistral-M09` ; `mesures_hc`, elle, reste — c'est elle qui porte la démonstration de cardinalité, et M15 la retrouvera.

```sql
DROP TABLE cmp_serie, cmp_machine, cmp_aucun;
```

---

**Vers la suite.** Le volume est divisé. Il reste à décider ce qu'on garde, combien de temps, et sous quelle forme — et à articuler la compression avec la rétention et le rafraîchissement des agrégats, dans un ordre qui n'est pas indifférent. C'est M10.
