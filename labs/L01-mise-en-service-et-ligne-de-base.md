# L01 — Mise en service et ligne de base

**Module** : M02 · Déploiement, mise en service, méthode de mesure
**Durée** : 45 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : jeux restaurés (parcours amont)
**État de fil rouge en sortie** : `mistral-M02`

---

## Contexte

Le parcours amont a restauré trois jeux de données sur le poste. À ce stade, le poste possède des fichiers, pas un environnement de travail : rien ne garantit que l'extension est chargée, que les workers d'arrière-plan tournent, ni que les mesures produites seront comparables à celles du voisin.

Cet atelier transforme ces fichiers en environnement vérifié, puis établit la **ligne de base** : trois mesures de référence sur les données brutes, avant toute intervention. Tous les gains annoncés pendant les cinq jours se comparent à ces trois chiffres. Une ligne de base absente ou non défendable rend toutes les décisions ultérieures invérifiables.

C'est le seul atelier de la formation dont le livrable n'est pas une décision technique mais un point de départ mesuré.

---

## Prérequis

**Outils**

- Docker et Docker Compose fonctionnels, `verifier-poste.sh` retournant « poste conforme »
- `psql` en ligne de commande
- 60 Go d'espace disque libre

**Livrables des étapes précédentes**

- `mesures-avant.dump` restauré : la table `mesures` est une **table ordinaire
  de 5 jours** (21 168 000 lignes). C'est délibéré : la ligne de base se
  mesure sur table non partitionnée, et restaurer deux fois les 190 millions
  de lignes coûterait cher pour rien. Le jeu complet (`mesures.bin`,
  45 jours) sera chargé en M03, par `COPY ... FORMAT binary`, dans
  l'hypertable — c'est le mode de chargement que la formation enseigne.
- `mistral-legacy.dump` restauré sur l'instance PostgreSQL 16
- `mesures-hc.bin` chargé (il ne servira qu'en M09, mais son chargement se vérifie ici)

**Lecture recommandée** : `L00-mistral-modele-de-donnees.md` décrit le parc MISTRAL, le référentiel et les tables restaurées. Il est indispensable avant L02, utile dès maintenant pour savoir ce que mesurent R1, R2 et R3.

**Fichiers fournis dans le dépôt**

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Instance épinglée à 2 vCPU et 8 Go |
| `conf/timescaledb-mistral.conf` | Configuration recommandée pour l'atelier |
| `mesure.sh` | Harnais de mesure : cinq exécutions, médiane, écart-type |
| `requetes/R1-dernier-point.sql` · `R2-fenetre-3j.sql` · `R3-agregation-fenetre.sql` | Les trois requêtes de référence |
| `mesures.md` | Journal de bord, à compléter |

---

## SOCLE — pour tous

**Avant l'étape 1 : le parcours amont doit avoir été joué.** Il crée les répertoires de données, démarre les deux instances, crée la base `mistral` et y restaure les trois jeux. Toutes les étapes ci-dessous se font **dans la base `mistral`**. Si `verifier-poste.sh` ne répond pas « poste conforme », le jouer maintenant, depuis `atelier/` :

```bash
./amont/restaurer.sh && ./verifier-poste.sh
```

### Étape 1 — Démarrer l'instance épinglée

L'épinglage n'est pas un détail de confort : sans lui, les mesures d'un participant ne sont pas comparables à celles d'un autre, et la règle du rapport plutôt que de la durée absolue perd son sens.

```bash
docker compose up -d timescaledb      # sans effet si le parcours amont l'a déjà démarrée
docker stats --no-stream timescaledb
```

Les répertoires de données (`pgdata/`, `pgdata-legacy/`, `archives/`) sont montés depuis le disque hôte. Le parcours amont les a créés à votre nom ; s'ils n'existent pas au premier `up`, Docker les crée lui-même, propriété de root, et l'instance ne démarre pas (voir les pièges).

Vérifier que la sortie de `docker stats` affiche bien une limite mémoire de 8 Go et non la mémoire totale du poste.

Vérifier également que le swap est désactivé côté conteneur :

```bash
docker inspect timescaledb --format '{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}'
```

Les deux valeurs doivent être identiques : mémoire et mémoire+swap au même plafond signifie qu'aucun swap n'est disponible.

### Étape 2 — Activer les trois extensions et contrôler les versions

Trois extensions, pas une. La première porte le produit ; les deux autres sont exigées par des modules ultérieurs, et ce sont celles qu'on oublie.

Se connecter à la base `mistral` — **une extension se crée par base** : le parcours amont n'y a créé que `timescaledb`, les deux autres sont à votre charge, et une extension créée dans la base `postgres` ne sert à rien ici.

```bash
docker compose exec -w /atelier timescaledb psql -U postgres -d mistral
```

C'est **la** commande de connexion pour toute la formation : `psql` s'exécute dans le conteneur, où le dossier `atelier/` est monté sous `/atelier`. L'option `-w /atelier` en fait le répertoire courant, ce qui rend valables les `\i l02/...` des fiches et les chemins `/jeux/...` des scripts de chargement. Un `psql` installé sur le poste verrait les fichiers du dépôt mais pas les jeux.

La première bibliothèque et la troisième doivent être **préchargées au démarrage** : c'est le paramètre `shared_preload_libraries`, qui ne se modifie qu'avec un redémarrage. Dans le kit, il n'est pas à écrire dans `postgresql.conf` (le fichier de configuration du serveur, dans le conteneur) : le `docker-compose.yml` le passe sur la ligne de commande du serveur (`command: postgres -c shared_preload_libraries=…`). Le vérifier avant de créer les extensions :

```sql
SHOW shared_preload_libraries;   -- attendu : timescaledb,pg_stat_statements

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

SELECT extname, extversion FROM pg_extension ORDER BY extname;
SELECT version();
```

`timescaledb` doit retourner `2.29.x`. La version PostgreSQL doit être 17 ou 18.

| Extension | Requise par | Ce qui se passe si elle manque |
|---|---|---|
| `timescaledb` | tout | Rien ne fonctionne, et cela se voit immédiatement |
| `timescaledb_toolkit` | M07, M08 | L06 s'arrête au premier indicateur, deux jours plus tard |
| `pg_stat_statements` | M13, M15 | La non-régression de performance est impossible — et l'absence ne se découvre qu'au moment où l'on en a besoin |

**Les deux dernières s'installent séparément et ont leur propre cycle de version.** Une montée de version de `timescaledb` n'emporte pas le Toolkit.

### Étape 3 — Appliquer la configuration et vérifier les workers

Deux fichiers sont en jeu, à ne pas confondre :

- `conf/timescaledb-mistral.conf`, dans le dépôt, monté dans le conteneur sous `/conf` : la configuration d'atelier (mémoire, workers, suivi des requêtes) ;
- `postgresql.conf`, dans le conteneur, créé par l'image au premier démarrage : la configuration du serveur. Il ne lit la première que si on la lui fait **inclure**.

Le parcours amont a préparé le point d'inclusion (un répertoire `conf.d/` et la ligne `include_dir` dans `postgresql.conf`). Il reste à y copier la configuration d'atelier et à redémarrer, depuis `atelier/` :

```bash
D=/home/postgres/pgdata/data
docker compose exec timescaledb mkdir -p $D/conf.d
docker compose exec timescaledb sh -c "grep -q '^include_dir' $D/postgresql.conf \
  || echo \"include_dir = 'conf.d'\" >> $D/postgresql.conf"
docker compose exec timescaledb cp /conf/timescaledb-mistral.conf $D/conf.d/
docker compose restart timescaledb
```

Les deux premières commandes ne font rien si le parcours amont est passé ; elles rendent l'étape rejouable sur une instance démarrée sans lui. Un redémarrage complet est obligatoire : ces paramètres ne se rechargent pas à chaud.

Puis, une fois l'instance revenue :

```sql
SHOW shared_buffers;
SHOW work_mem;
SHOW maintenance_work_mem;
SHOW max_worker_processes;
SHOW timescaledb.max_background_workers;

SELECT application_name, backend_type, state
FROM   pg_stat_activity
WHERE  application_name LIKE 'TimescaleDB%';
```

La dernière requête doit retourner au moins une ligne. Aucune ligne signifie que l'ordonnanceur n'a pas démarré — voir les pièges.

### Étape 4 — Produire la ligne de base

Les trois requêtes de référence portent sur `mesures` encore en table ordinaire. Elles fixent l'état « avant » de toute la formation.

Les bornes temporelles sont calculées à partir du jeu, jamais écrites en
dur — `mesure.sh` les calcule et les passe en variables psql. Elles visent
les jours 1 à 5 de la fenêtre : ces jours existent à l'identique dans la
table de référence et dans l'hypertable de M03, ce qui rendra les rapports
avant/après comparables à données égales.

Exécuter les trois mesures :

```bash
./mesure.sh requetes/R1-dernier-point.sql
./mesure.sh requetes/R2-fenetre-3j.sql
./mesure.sh requetes/R3-agregation-fenetre.sql
```

Contenu des trois requêtes, pour information :

```sql
-- R1 : dernière valeur de chaque série (motif le plus fréquent en production)
SELECT DISTINCT ON (series_id) series_id, ts, valeur
FROM   mesures
ORDER  BY series_id, ts DESC;

-- R2 : agrégation horaire sur une fenêtre de trois jours (jours 3-5)
SELECT date_trunc('hour', ts) AS heure, avg(valeur)
FROM   mesures
WHERE  ts >= :'fen3' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;

-- R3 : agrégation par série sur la fenêtre de référence (jours 1-5)
SELECT series_id, avg(valeur), count(*)
FROM   mesures
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY series_id;
```

Reporter les trois médianes et les trois écarts-types dans `mesures.md`. Un écart-type supérieur à 20 % de la médiane invalide la mesure : attendre et relancer.

### Étape 5 — Relever le volume de départ

```sql
SELECT pg_size_pretty(pg_relation_size('mesures'))        AS heap,
       pg_size_pretty(pg_indexes_size('mesures'))         AS index,
       pg_size_pretty(pg_total_relation_size('mesures'))  AS total;
```

Consigner les trois valeurs dans `mesures.md`. Elles serviront de dénominateur au ratio de compression mesuré en M09.

### Critères de réussite

- [ ] `docker stats` affiche une limite de 8 Go, et mémoire et mémoire+swap sont au même plafond
- [ ] **Les trois extensions sont chargées**, et leurs versions relevées
- [ ] `timescaledb` retourne `2.29.x` et `version()` retourne PostgreSQL 17 ou 18
- [ ] `pg_stat_statements` figure dans `shared_preload_libraries`, pas seulement dans `pg_extension`
- [ ] Les cinq paramètres de l'étape 3 retournent les valeurs de `timescaledb-mistral.conf`
- [ ] La requête sur `pg_stat_activity` retourne au moins un processus TimescaleDB
- [ ] Les trois médianes sont consignées dans `mesures.md`, chacune avec un écart-type **inférieur à 20 %**
- [ ] Les trois valeurs de volume sont consignées

---

## EXTENSION — pour aller plus loin

Ces travaux ne sont ni évalués ni attendus. Ils n'entrent pas dans l'état de reprise `mistral-M02` : le module suivant part du socle, et de lui seul.

### E1 — Auditer `timescaledb-tune`

```bash
docker compose exec timescaledb timescaledb-tune --dry-run --quiet
```

Comparer la sortie proposée à `conf/timescaledb-mistral.conf`, ligne par ligne. Pour chaque écart, écrire une phrase expliquant lequel des deux réglages est le bon **dans le contexte de l'atelier** — 2 vCPU, 8 Go, un seul utilisateur — et pourquoi la réponse serait différente en production.

L'objectif n'est pas de trouver la bonne configuration mais de constater que l'outil raisonne sur les ressources détectées, pas sur la charge attendue.

### E2 — Comparer avec un service managé

Provisionner un service Tiger Cloud de dimensionnement équivalent, y restaurer `actifs` et `meteo` (les deux petits flux suffisent). Relever les mêmes cinq paramètres qu'à l'étape 3.

Deux questions à documenter : lesquels de ces paramètres sont modifiables sur le service managé, et lesquels ne le sont pas ? Le résultat prépare directement le module M13.

### E3 — Mesurer l'effet de `shared_buffers`

Rejouer R2 avec trois valeurs de `shared_buffers` — par exemple 512 Mo, 2 Go, 4 Go — en redémarrant entre chaque, et en relançant `mesure.sh` à froid.

Tracer le rapport entre la meilleure et la pire valeur, puis répondre par écrit : à partir de quelle valeur le gain cesse-t-il, et quelle grandeur physique explique le plateau ?

### E4 — Instrumenter le harnais

Modifier `mesure.sh` pour qu'il consigne également, à chaque exécution, le nombre de blocs lus depuis le cache et depuis le disque, extrait de `EXPLAIN (ANALYZE, BUFFERS)`. C'est cette instrumentation qui rendra les mesures de M04 et M09 interprétables plutôt que seulement comparables.

---

## Pièges et indices

**Le conteneur s'arrête aussitôt : « mkdir: cannot create directory '/home/postgres/pgdata/data': Permission denied ».**
Le répertoire `pgdata/` a été créé par Docker (donc par root) parce qu'il n'existait pas au premier `up`. L'image tourne sous l'uid 1000 et ne peut pas y écrire. Supprimer le répertoire vide (`rmdir pgdata`), le recréer à votre nom (`mkdir pgdata`), relancer. `./amont/restaurer.sh` fait cette création correctement ; c'est une raison de plus de ne pas sauter le parcours amont.

**`ERROR: relation "mesures" does not exist`, alors que le parcours amont est passé.**
La session `psql` n'est pas connectée à la bonne base. Sans option `-d`, `psql` ouvre la base `postgres`, qui est vide ; tout le travail des quinze labs se fait dans `mistral`. Le prompt le dit : il doit afficher `mistral=#`, pas `postgres=#`. Corriger avec `\c mistral`, ou se connecter par `docker compose exec timescaledb psql -U postgres -d mistral`. `mesure.sh` n'a pas ce problème, il nomme la base lui-même — c'est pour cela que l'étape 4 passe et que l'étape 5, tapée à la main, échoue.

**La limite du conteneur semble ignorée.**
Sur macOS et Windows, `--memory` ne fait effet que si la machine virtuelle de Docker Desktop est plus grande que la limite demandée. Vérifier d'abord le dimensionnement de la VM dans les préférences, ensuite seulement celui du conteneur. Un conteneur à 8 Go dans une VM à 4 Go se comporte comme un conteneur à 4 Go, sans le signaler.

**Le Toolkit ou le suivi des requêtes manquent, et rien ne le signale.**
Leur absence n'a aucune conséquence visible aujourd'hui. Elle se découvre en L06, deux jours plus tard, sur un message d'erreur qui ne suggère pas d'installer une extension — et en L15, au moment précis où l'on cherche à comparer un instantané qui n'existe pas. C'est pour cela que leur vérification appartient à la mise en service, et non au module qui les utilise.

**`pg_stat_statements` est créé mais ne collecte rien.**
La création de l'extension ne suffit pas : la bibliothèque doit être chargée au démarrage. Vérifier les deux, `shared_preload_libraries` **et** `pg_extension`.

**`\dx` affiche une version, `extversion` en affiche une autre.**
`\dx` liste ce qui est disponible sur le disque. Seule la colonne `extversion` de `pg_extension` dit ce qui est réellement chargé dans la base courante. Après une montée de version de paquet sans `ALTER EXTENSION UPDATE`, les deux divergent — c'est exactement la situation traitée en M13.

**`CREATE EXTENSION` échoue avec un message sur la bibliothèque partagée.**
`shared_preload_libraries` n'est pas positionné, ou l'instance n'a pas été redémarrée après l'avoir positionné. Ce paramètre ne se recharge pas : il exige un redémarrage complet, pas un `pg_reload_conf()`.

**Aucun processus TimescaleDB dans `pg_stat_activity`.**
Vérifier `max_worker_processes` **avant** `timescaledb.max_background_workers`. Le plafond global l'emporte : si la somme des workers TimescaleDB et du parallélisme PostgreSQL le dépasse, les workers ne démarrent pas et rien ne le signale dans les journaux applicatifs. Cette panne ouvre le catalogue de M15.

**L'écart-type dépasse durablement 20 %.**
Une indexation, un autovacuum ou la fin de la restauration tourne encore. Vérifier avec :

```sql
SELECT pid, query_start, state, left(query, 60) AS requete
FROM   pg_stat_activity
WHERE  state <> 'idle' AND pid <> pg_backend_pid();
```

Attendre que l'activité retombe. Ne pas moyenner du bruit : une mesure instable n'est pas une mesure approximative, c'est une absence de mesure.

**R3 et R2 donnent des durées du même ordre.**
C'est attendu, et c'est le point : sans partitionnement ni index utile,
les deux balayent toute la table quelle que soit la fenêtre demandée —
le prédicat temporel ne réduit pas les lectures. R1 paie en plus son tri
par série. Ces chiffres sont ceux auxquels M04, M08 et M09 se compareront.

**Le voisin obtient des durées très différentes.**
C'est attendu, et documenté : les entrées-sorties diffèrent d'un poste à l'autre, parfois d'un facteur cinq. Ce sont les **rapports** entre configurations qui sont comparables, jamais les durées absolues. Ne pas chercher à faire converger les chiffres entre participants.

---

## Livrable

| Élément | Contenu |
|---|---|
| Instance conforme | Trois extensions chargées, configuration appliquée, workers actifs, épinglage vérifié |
| `mesures.md` | Trois médianes avec écarts-types, trois valeurs de volume, en-tête précisant l'environnement |
| État de reprise | `mistral-M02` |

En-tête attendu de `mesures.md` :

```markdown
## M02 — ligne de base
Environnement : Docker 2 vCPU / 8 Go · TimescaleDB 2.29.x · PostgreSQL 17.x · <OS du poste>

| requête                       | médiane | écart-type | note        |
|-------------------------------|---------|------------|-------------|
| R1 dernier point              |         |            | table brute |
| R2 fenêtre 3 jours            |         |            | table brute |
| R3 agrégation fenêtre (j1-j5) |         |            | table brute |

Volume : heap … · index … · total …
```

**Vers la suite.** M03 ouvre sur une question à laquelle cet atelier ne répond pas : ces trois requêtes portent sur un schéma qui n'a jamais été discuté. Le module suivant le reprend depuis le début, et le schéma qui en sortira est celui que tous les ateliers utiliseront jusqu'à la migration de M12.

---

## Note de production

Conformément à l'annexe B du plan, le corrigé de ce socle **est** le script `reprise/M02.sql` accompagné de `reprise/M02.sh` pour la partie conteneur. Ces fichiers ne sont pas une transcription du lab : ce sont les mêmes fichiers, commentés, qui construisent l'état `mistral-M02` de la chaîne d'instantanés.

Le test d'état associé, `tests/M02.sql`, vérifie les six critères de réussite du socle. Les fourchettes de durée y sont exprimées en tolérance relative et non en valeurs absolues, faute de quoi tout changement d'environnement de référence les invalide.
