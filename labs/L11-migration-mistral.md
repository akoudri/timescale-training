# L11 — Migration MISTRAL

**Module** : M12 · Migration
**Durée** : 70 min — socle 65 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M11` côté cible, `mistral_legacy` côté source
**État de fil rouge en sortie** : `checklist-bascule.md` éprouvée

---

## Contexte

`mistral_legacy` tourne sur PostgreSQL 16, avec une table de mesures partitionnée à la main. La cible construite depuis M03 l'attend, complète : schéma, dimensionnement, index, agrégats, compression, rétention, automatisation.

**Le livrable de cet atelier n'est pas la migration. C'est la checklist.** L'exécution n'en est que la vérification, et l'étape 1 impose de l'écrire en entier — repli compris — avant de toucher à quoi que ce soit. Une migration improvisée réussit parfois ; elle ne se refait pas, et elle ne se transmet pas.

C'est aussi le seul livrable de toute la formation conçu pour sortir de MISTRAL et servir tel quel sur le contexte du participant.

---

## Prérequis

**État attendu**

- `mistral-M11` atteint côté cible
- L'instance source PostgreSQL 16 tourne, `mistral_legacy` chargée : environ 40 millions de lignes, 3 Go
- Les deux instances se voient sur le réseau du `docker compose`

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l11/checklist-modele.md` | Le squelette à compléter, avec ses rubriques |
| `l11/preparer-cible.sql` | Désactive les politiques et la compression sur la cible |
| `l11/controles.sql` | Les trois contrôles de cohérence, paramétrés |
| `l11/simuler-flux.sh` | Maintient un flux d'écriture sur la source pendant la migration |
| `l11/durcir-cible.sql` | Réactive compression et politiques après bascule |
| `l11/migrer.sh` | Copie initiale par plages d'identifiant, puis delta de rattrapage, production ouverte |

---

## SOCLE — pour tous

### Étape 1 — Écrire la checklist (15 min)

**Avant toute manipulation.** Compléter `l11/checklist-modele.md`, qui comporte trois rubriques.

**Avant la bascule**

- Les prérequis vérifiés côté cible : extensions présentes, schéma en place, espace disque suffisant
- La procédure de repli, complète, avec ses commandes
- Le délai maximal avant déclenchement du repli
- Qui prononce la bascule

**Pendant**

- Chaque étape, avec son critère de passage
- Les trois contrôles et leurs seuils d'acceptation
- L'emplacement où sera relevée l'interruption réelle

**Après**

- L'activation de la compression et des politiques
- Les vérifications post-bascule, séquences comprises
- La date à laquelle la source pourra être supprimée

**Le formateur relit une checklist par binôme avant d'autoriser l'étape 2.** Une checklist sans procédure de repli écrite ne passe pas.

### Étape 2 — Préparer la cible et copier (15 min)

Lancer d'abord le flux d'écriture sur la source : la migration doit se faire pendant que la production tourne.

```bash
./l11/simuler-flux.sh --debit 2000 &
```

Préparer la cible : une base **dédiée**, `mistral_prod`, qui porte le schéma de M03 et l'index de M06, sans compression ni politiques actives. La base du fil rouge ne convient pas : elle contient déjà un jeu de 45 jours qui n'est pas celui de la legacy (fenêtres partiellement recouvrantes, valeurs différentes) — y copier la source créerait des collisions sur `(series_id, ts)`.

```sql
\i l11/preparer-cible.sql
```

Le script crée la base, y rejoue le schéma et l'index, et vérifie que la compression n'est pas activée et qu'aucune politique ne tourne.

Copie initiale, par plages d'identifiant, production ouverte :

```bash
./l11/migrer.sh            # plages de 6 M d'identifiants, puis un premier delta
```

Le script s'appuie sur l'identifiant monotone de la source, alimenté par sa séquence : c'est l'équivalent, côté legacy, de l'horodatage d'ingestion ajouté en M05. Chaque plage est un `\copy` de la source vers la cible ; la borne haute relevée au départ délimite ce que le delta devra rattraper.

**Pourquoi pas la réplication logique.** Testée au pilote (TimescaleDB 2.29.2, PostgreSQL 17) : la synchronisation initiale d'une souscription vers une hypertable écrit dans la table racine, sans routage vers les chunks — trois gigaoctets copiés, zéro ligne visible, aucun message. S'y ajoute, côté source partitionnée en déclaratif, l'obligation de publier avec `publish_via_partition_root = true`, faute de quoi la souscription échoue sur les noms des partitions. La réplication logique reste un chemin de production légitime vers une table ordinaire ; vers une hypertable, elle est l'objet de l'extension E3, pas du socle.

### Étape 3 — Rattrapage (12 min)

Rejouer le delta tant que le flux tourne : chaque passage copie la plage `[borne précédente, max(id)]` et laisse derrière lui un retard égal à ce qui a été écrit pendant sa propre durée.

```bash
./l11/migrer.sh --delta      # rejouable autant de fois que necessaire
```

```bash
# ce que le prochain delta devra rattraper : max(id) source - derniere borne copiee
echo "derniere borne copiee : $(cat l11/.borne)"
docker compose exec -T legacy psql -U postgres -d mistral_legacy -Atc "SELECT max(id) FROM mesures;"
```

**Le critère d'entrée en bascule** : le retard est faible et **stable** — il ne décroît plus, il oscille autour de quelques secondes de flux. Un retard qui décroît encore signifie que la copie initiale n'est pas terminée.

### Étape 4 — Les trois contrôles (10 min)

Le même fichier s'exécute **des deux côtés**, et les deux sorties se comparent :

```bash
docker compose exec -T legacy      psql -U postgres -d mistral_legacy < l11/controles.sql > /tmp/ctl-source.txt
docker compose exec -T timescaledb psql -U postgres -d mistral_prod   < l11/controles.sql > /tmp/ctl-cible.txt
diff /tmp/ctl-source.txt /tmp/ctl-cible.txt
```

**Contrôle 1 — comptage global.** Rapide, détecte une copie tronquée. Tant que le flux tourne, il diverge de ce qui est en transit depuis le dernier delta : c'est attendu, et c'est le contrôle qui deviendra strict à la bascule.

**Contrôle 2 — somme par période.** Une agrégation par jour, des deux côtés, comparée.

```sql
SELECT date_trunc('day', ts) AS jour, count(*), sum(series_id)
FROM   mesures GROUP BY 1 ORDER BY 1;
```

Noter que la somme porte sur `series_id`, un entier — jamais sur la valeur, qui est un flottant. Voir les pièges.

**Contrôle 3 — échantillonnage.** Une centaine de lignes tirées au hasard, comparées champ par champ. « Au hasard » se vérifie : le script affiche la plage temporelle et le nombre de séries couvertes par l'échantillon. Un tirage par simple modulo sur un identifiant structuré tombe toujours sur les mêmes séries et les mêmes minutes — voir les pièges.

Les trois doivent passer **avant** toute décision de bascule. Consigner leurs résultats dans la checklist, à l'endroit prévu.

### Étape 5 — Basculer (8 min)

C'est la seule étape qui interrompt. Chronométrer du premier au dernier geste.

1. Arrêter le flux d'écriture sur la source — par son identifiant de processus (`kill $(cat l11/.flux.pid)`, le simulateur l'écrit au démarrage), jamais par un motif de ligne de commande : un `pkill -f` peut tuer le terminal qui l'exécute
2. **Vérifier** l'arrêt : le comptage source doit être stable à quelques secondes d'écart — un flux mal arrêté se découvre au contrôle 1, trop tard. Une recherche de processus par motif ne prouve rien : elle peut trouver son propre shell
3. Jouer le delta final
4. Vérifier une dernière fois le contrôle 1
5. **Remettre les séquences à niveau côté cible** — ni la réplication logique ni la copie par plages ne les positionnent
6. Basculer le flux d'écriture vers la cible

```sql
-- etape 5 : la seule qui ne va pas de soi
SELECT setval('mesures_id_seq',
              (SELECT max(id) FROM mesures));
```

Relever l'interruption réelle et la consigner.

### Étape 6 — Activer et durcir (10 min)

Après la bascule, jamais pendant.

```sql
\i l11/durcir-cible.sql
```

Le script active la compression et enregistre les deux politiques de la cible, compression et rétention, dont la première exécution est immédiate. Vérifier ensuite :

```sql
SELECT job_id, proc_name, scheduled, next_start, last_run_status
FROM   timescaledb_information.job_stats
JOIN   timescaledb_information.jobs USING (job_id);
```

Les deux politiques doivent être planifiées et avoir une prochaine échéance (les jobs 1 et 3 de la liste sont ceux du système, pas les vôtres). Contrairement au fil rouge, les données de la legacy sont réellement dans le passé de `now()` : la politique de compression agit dès sa première exécution, et le volume de la cible baisse aussitôt. Un job resté suspendu est le mode de défaillance de M11, transposé à la migration.

### Critères de réussite

- [ ] La checklist était **complète avant l'étape 2**, procédure de repli incluse, et a été relue par le formateur
- [ ] La copie initiale s'est faite pendant que le flux d'écriture tournait
- [ ] Le delta a été rejoué jusqu'à stabilisation, et l'arrêt du flux a été **vérifié** par comptage avant le delta final
- [ ] Les trois contrôles passent, et leurs résultats sont consignés dans la checklist
- [ ] Les séquences ont été remises à niveau **avant** de basculer le flux
- [ ] L'interruption réelle est mesurée et consignée
- [ ] Les deux politiques de la cible sont planifiées et ont une prochaine échéance

---

## EXTENSION — pour aller plus loin

Non évaluée.

### E1 — Exécuter le repli

Recommencer la migration, et interrompre volontairement le rattrapage à mi-parcours — arrêt du script de copie, ou coupure réseau entre les deux conteneurs.

Exécuter alors la procédure de repli **telle qu'elle est écrite dans la checklist**, sans l'improviser. Chronométrer, puis noter les écarts entre ce qui était écrit et ce qu'il a fallu faire. Ces écarts sont la vraie valeur de l'exercice.

### E2 — L'extension manquante

Supprimer une extension utilisée par le schéma source côté cible, puis relancer la migration. Diagnostiquer le message obtenu, et déterminer à quelle étape de la checklist ce contrôle aurait dû figurer.

### E3 — La réplication logique, pour constater

Tenter la voie écartée du socle : créer la publication côté source **avec** `publish_via_partition_root = true` (la source est partitionnée en déclaratif), la souscription côté cible avec `copy_data = true`, puis compter les lignes visibles dans l'hypertable cible (`count(*)`), et comparer avec ce que la table racine a réellement reçu : `n_tup_ins` et `n_live_tup` dans `pg_stat_user_tables`, et `pg_relation_size('mesures')`. Un `SELECT count(*) FROM ONLY mesures` ne les montre pas non plus : le planificateur de l'extension considère la racine comme vide par construction. Comparer avec la copie par plages sur trois grandeurs : durée totale, interruption réelle, complexité de la procédure — et écrire en une phrase pourquoi la réplication logique reste un bon choix vers une table ordinaire, et pas vers une hypertable en 2.29. Ne pas oublier `DROP SUBSCRIPTION` en fin d'essai, et vérifier côté source que le slot de réplication a disparu : un slot orphelin retient le journal de la source indéfiniment.

### E4 — Transposer à l'échelle de production

Reprendre la checklist et la confronter à 200 Go et 19 milliards de points.

Quels contrôles ne passent plus à l'échelle — et par quoi les remplacer ? Le contrôle 3 par échantillonnage tient-il encore ? Le contrôle 2 par jour devient-il trop long ? Écrire la version production de la checklist.

---

## Pièges et indices

**La compression a été activée avant la copie.**
La durée est multipliée. Le script de préparation vérifie ce point, mais un participant qui l'a contourné le paiera à l'étape 2. Toujours après la bascule, à l'étape 6.

**Les séquences sont restées à zéro côté cible.**
Ni la réplication logique ni la copie par plages ne les positionnent. La première insertion post-bascule entre en conflit de clé, et l'incident est immédiat et visible. C'est l'étape 5.5, et c'est la ligne qu'on oublie.

**La somme de contrôle diverge sans raison apparente.**
Elle porte sur des flottants, et l'ordre d'agrégation diffère entre les deux instances. Utiliser des comptages et des sommes sur entiers — c'est pourquoi le contrôle 2 somme `series_id` et non `valeur`.

**Le delta ne rétrécit jamais.**
Soit la copie initiale n'est pas terminée — c'est normal, attendre. Soit le flux d'écriture est plus rapide que la copie : réduire le débit du simulateur, la salle n'a pas la bande passante de la production.

**Le contrôle 1 diverge de quelques centaines de lignes après le delta final.**
Le flux n'était pas arrêté : le processus tué n'était pas le bon, ou un lot était encore en vol. L'arrêt du flux se **vérifie** par un comptage source stable, il ne se suppose pas. En production : arrêt de service et connexions en lecture seule, pas un kill de processus.

**La réplication logique « fonctionne » mais la cible reste vide.**
C'est le comportement constaté au pilote vers une hypertable : les lignes sont dans le tas de la table racine, pas dans les chunks, et aucune requête ne les voit — pas même `SELECT count(*) FROM ONLY mesures`, que le planificateur de l'extension réduit à un filtre constant faux. Seules les statistiques (`pg_stat_user_tables.n_live_tup`) et la taille physique (`pg_relation_size`) trahissent leur présence. Le worker de réplication écrit avec `session_replication_role = replica`, ce qui désactive le déclencheur qui bloque d'ordinaire les insertions directes dans la racine. Le flux continu après la synchronisation initiale atterrit au même endroit. Ce n'est pas une erreur de manipulation, c'est la raison pour laquelle le socle copie par plages.

**Un job est resté suspendu après l'étape 6.**
Le script les réactive, mais un `alter_job` manuel passé en cours d'atelier peut en avoir laissé un de côté. Vérifier `scheduled` et `next_start` pour les six, pas seulement l'absence d'erreur.

**L'échantillon du contrôle 3 ne couvre qu'un seul jour.**
L'identifiant de la legacy est structuré : un bloc de 103 680 minutes par série. Un tirage par `id % N = 1` avec N voisin d'un multiple de ce bloc retombe sur les mêmes séries et les mêmes minutes — cent lignes des deux dernières heures de la fenêtre, rien de juillet. Le script tire par hachage de l'identifiant, ce qui est déterministe des deux côtés et réparti ; et il affiche la couverture de l'échantillon, à lire avant de comparer.

**La cible est « migrée » mais ce n'est pas une hypertable.**
Sans l'extension, le script de préparation crée quand même les tables — ordinaires — et échoue seulement sur `create_hypertable`. Un participant qui ne lit pas l'erreur copie ensuite quarante millions de lignes dans une table ordinaire, sans un message. Le contrôle « extension présente et hypertables créées » appartient à la rubrique « Avant la bascule », et il se vérifie sur `timescaledb_information.hypertables`, pas sur l'absence d'erreur.

**Le chronomètre de l'étape 5 donne quelques secondes.**
C'est attendu sur ce volume et dans ce réseau. La valeur n'est pas transposable — la **procédure**, elle, l'est. Le consigner avec son contexte.

---

## Livrable

| Élément | Contenu |
|---|---|
| `checklist-bascule.md` | Complète, éprouvée, avec les résultats des contrôles et l'interruption mesurée |
| `mesures.md` §`M12` | Interruption réelle, durée de la copie initiale, retard du dernier delta à la bascule |
| `l11/ecarts.md` | Pour ceux qui ont fait E1 : les écarts entre le repli écrit et le repli exécuté |

## Nettoyage

À faire en fin d'atelier, extensions comprises : ce qui n'appartient pas à l'état de reprise part.

Arrêter le simulateur de flux s'il tourne encore (`Ctrl-C` dans son terminal, ou `kill $(cat l11/.flux.pid)`), et vérifier qu'il est bien arrêté par un comptage stable côté source — la leçon de l'étape 5 vaut aussi ici.

La base cible `mistral_prod` (environ 3 Go) n'est pas utilisée par les modules suivants : la conserver le temps de la relecture de la checklist, puis la supprimer. Le fichier de borne `l11/.borne` peut partir avec elle.

```sql
DROP DATABASE mistral_prod;    -- depuis une session sur une autre base
```

---

**Vers la suite.** La production tourne sur la cible. La question suivante est celle qu'on ne se pose jamais assez tôt : que se passe-t-il si cette instance disparaît ? M13 traite la sauvegarde, la restauration — et la montée de version, qui n'a pas de retour arrière.
