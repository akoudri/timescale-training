# Quiz de positionnement

**Parcours amont · à soumettre au plus tard à J-5**
**15 questions · trois paliers · durée indicative 20 min**

---

## Note au participant

Ce questionnaire n'est pas un examen et son résultat n'est communiqué à personne d'autre que vous et le formateur. Il sert à deux choses : vérifier que le plancher de prérequis est atteint, et orienter chacun vers les modules de pré-travail dont il a réellement besoin.

**Il ne porte pas sur TimescaleDB.** Aucune connaissance préalable de l'extension n'est attendue. Il porte sur PostgreSQL, parce que c'est là-dessus que la formation s'appuie sans le réexpliquer.

Répondez sans documentation. Une réponse fausse renvoie vers un module de pré-travail de trente à soixante minutes — c'est le résultat utile.

---

## Palier 1 — Plancher

Ces six questions sont **filtrantes**. La formation les suppose acquises et ne les traite nulle part.

### Q1 — Lire un plan d'exécution

Dans la sortie de `EXPLAIN (ANALYZE, BUFFERS)`, quelle information indique le nombre de blocs qu'il a fallu aller chercher **sur le disque** ?

- **a)** `shared hit`
- **b)** `shared read`
- **c)** `actual rows`
- **d)** `actual time`

### Q2 — Choix du planificateur

Sur une table de 200 lignes, un index existe sur la colonne filtrée. Le planificateur choisit malgré tout un parcours séquentiel. Pourquoi ?

- **a)** Les statistiques de la table sont périmées
- **b)** Un index n'est jamais utilisé sur une colonne de type texte
- **c)** Lire l'index puis les lignes coûte plus cher que lire les 200 lignes directement
- **d)** L'index n'a pas été analysé depuis sa création

### Q3 — Agrégation et fenêtrage

Quelle différence entre `sum(x) OVER (PARTITION BY m)` et `sum(x) ... GROUP BY m` ?

- **a)** Aucune, ce sont deux écritures du même calcul
- **b)** La première conserve une ligne par ligne d'entrée, la seconde en retourne une par valeur de `m`
- **c)** La première est toujours plus rapide
- **d)** La seconde ne fonctionne pas si `x` contient des valeurs nulles

### Q4 — Journal des transactions

À quoi sert principalement le journal des transactions ?

- **a)** Accélérer les lectures en conservant les résultats récents
- **b)** Conserver un historique des modifications à des fins d'audit
- **c)** Garantir la durabilité et permettre la reprise après un arrêt brutal
- **d)** Stocker les requêtes lentes pour analyse ultérieure

### Q5 — Espace disque après suppression

Un million de lignes viennent d'être supprimées. La taille de la table sur disque n'a pas diminué. Pourquoi ?

- **a)** La suppression n'a pas été validée
- **b)** L'espace est marqué réutilisable mais n'est pas rendu au système de fichiers
- **c)** Les index conservent les lignes supprimées indéfiniment
- **d)** Il faut attendre le prochain redémarrage de l'instance

### Q6 — Chargement en masse

Pour charger dix millions de lignes depuis un fichier, quelle méthode est la plus rapide ?

- **a)** `INSERT` ligne à ligne, dans une seule transaction
- **b)** `INSERT` multi-valeurs par lots de 100
- **c)** `COPY`
- **d)** `INSERT ... SELECT` depuis une table temporaire

---

## Palier 2 — Niveau attendu

Ces six questions ne sont pas filtrantes. Un échec oriente vers un module de pré-travail précis.

### Q7 — Partitionnement déclaratif

Une table est partitionnée par plage sur la colonne `ts`. Quelle condition permet au planificateur d'éliminer des partitions ?

- **a)** `WHERE date_trunc('day', ts) = '2026-07-01'`
- **b)** `WHERE ts::date = '2026-07-01'`
- **c)** `WHERE ts >= '2026-07-01' AND ts < '2026-07-02'`
- **d)** `WHERE extract(day FROM ts) = 1`

### Q8 — DISTINCT ON

Que retourne `SELECT DISTINCT ON (a) a, b FROM t ORDER BY a, b DESC` ?

- **a)** Toutes les lignes, triées par `a` puis `b` décroissant
- **b)** Une ligne par valeur distincte de `a`, celle dont `b` est la plus grande
- **c)** Une ligne par couple distinct `(a, b)`
- **d)** Une erreur : `DISTINCT ON` exige un `GROUP BY`

### Q9 — Taille de transaction

Insérer un million de lignes en une seule transaction plutôt qu'en un million de transactions :

- **a)** Réduit le coût de validation et le volume de journal produit
- **b)** N'a aucun effet sur les performances
- **c)** Augmente le volume de journal, car la transaction est plus longue
- **d)** Est impossible au-delà de dix mille lignes

### Q10 — Privilèges

Après `GRANT SELECT ON ma_table TO r;`, le rôle `r` peut-il lire la table ?

- **a)** Oui, systématiquement
- **b)** Seulement s'il dispose aussi du privilège `USAGE` sur le schéma
- **c)** Seulement s'il est propriétaire de la table
- **d)** Non, il faut également `GRANT CONNECT`

### Q11 — Utilisation d'un index

Un index B-tree existe sur `ts`. Laquelle de ces conditions peut l'utiliser ?

- **a)** `WHERE date_trunc('hour', ts) = '2026-07-01 08:00'`
- **b)** `WHERE ts::text LIKE '2026-07%'`
- **c)** `WHERE ts >= '2026-07-01' AND ts < '2026-07-02'`
- **d)** `WHERE extract(hour FROM ts) = 8`

### Q12 — Vue matérialisée

Une vue matérialisée PostgreSQL se met-elle à jour automatiquement quand les données sources changent ?

- **a)** Oui, à chaque modification de la table source
- **b)** Oui, mais avec un délai configurable
- **c)** Non, un rafraîchissement explicite recalcule la totalité de la vue
- **d)** Non, mais elle recalcule automatiquement les seules lignes modifiées

---

## Palier 3 — Détection de profils avancés

Ces trois questions ne sont pas attendues. Elles servent à repérer les participants qui devront être occupés par les extensions.

### Q13 — Réplication logique

Qu'est-ce que la réplication logique **ne réplique pas** ?

- **a)** Les mises à jour de lignes
- **b)** Les suppressions
- **c)** Les séquences et les changements de schéma
- **d)** Les insertions dans les tables partitionnées

### Q14 — Statistiques de requêtes

À quoi sert `pg_stat_statements` ?

- **a)** À conserver le texte intégral de chaque requête exécutée
- **b)** À agréger les statistiques d'exécution par requête normalisée
- **c)** À enregistrer les plans d'exécution de toutes les requêtes
- **d)** À suivre l'activité des connexions en temps réel

### Q15 — Choix d'index

Une colonne booléenne vaut `true` sur 2 % des lignes d'une table de 200 millions de lignes, et n'est jamais filtrée que sur `true`. Quel index est le plus pertinent ?

- **a)** Un index B-tree sur la colonne
- **b)** Un index partiel restreint aux lignes à `true`
- **c)** Un index de hachage
- **d)** Aucun index : une colonne booléenne n'est jamais sélective
