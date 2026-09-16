# L07 — Pyramide d'agrégats MISTRAL

**Module** : M08 · Agrégats continus
**Durée** : 60 min — socle 50 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M07`
**État de fil rouge en sortie** : `mistral-M08`

---

## Contexte

Trois niveaux — une minute, une heure, un jour — chacun défini au-dessus du précédent. Puis une donnée tardive injectée sur J-3, qui doit remonter jusqu'en haut.

Deux difficultés, et elles ne sont pas là où on les attend.

La première est de **choisir ce que le niveau bas stocke**. Écrire `avg(valeur)` au niveau minute condamne toute la pyramide : le niveau horaire ne pourra plus qu'en faire une moyenne de moyennes, c'est-à-dire un chiffre faux. Le tableau du bloc 7.2 se transforme ici en décision d'architecture.

La seconde est de **prouver que la donnée tardive est reprise**. Une pyramide qui affiche des valeurs plausibles n'est pas une pyramide vérifiée. Le seul contrôle valable est un contrôle de somme aux trois niveaux, réalisé avant et après.

---

## Prérequis

**État attendu**

- `mistral-M07` atteint
- `mesures.md` contient la section `## M05 — retard d'arrivée` avec p50, p95, p99 et pire cas
- Les workers d'arrière-plan sont actifs — à revérifier, les politiques en dépendent :

```sql
SELECT application_name FROM pg_stat_activity
WHERE  application_name LIKE 'TimescaleDB%';
```

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l07/tableau-de-bord.sql` | Les quatre requêtes du tableau de bord MISTRAL |
| `l07/controle-somme.sql` | Le contrôle de cohérence aux trois niveaux |
| `l07/injecter-tardif.sh` | Injecte un lot daté de J-3 |
| `mesures.md` | Journal de bord |

---

## SOCLE — pour tous

### Étape 1 — Le niveau minute, et la décision qui engage la suite (15 min)

Avant d'écrire quoi que ce soit, répondre à la question du bloc 8.3 : **que doit stocker le niveau bas ?**

Les quatre indicateurs à porter dans la pyramide sont l'énergie produite, la puissance moyenne, la puissance maximale et le nombre de points. Pour chacun, décider ce qui est stocké au niveau minute — et se reporter au tableau du bloc 7.2 en cas d'hésitation.

```sql
CREATE MATERIALIZED VIEW mistral_1min
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 minute', ts) AS seau,
       series_id,
       -- a completer : quatre expressions, dont aucune n'est une moyenne
       ...
FROM   mesures
GROUP  BY 1, 2
WITH NO DATA;
```

Puis matérialiser l'historique — cette opération prend plusieurs minutes, la lancer avant de passer à la lecture de l'étape 2 :

```sql
CALL refresh_continuous_aggregate('mistral_1min', NULL, NULL);
```

### Étape 2 — Les niveaux heure et jour (15 min)

Chacun se définit **au-dessus du précédent**, jamais sur les mesures brutes.

```sql
CREATE MATERIALIZED VIEW mistral_1h
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 hour', seau) AS seau,
       series_id,
       sum(somme)               AS somme,
       sum(points)              AS points,
       max(maximum)             AS maximum
FROM   mistral_1min
GROUP  BY 1, 2
WITH NO DATA;
```

Le niveau bas ne stocke que somme, compte et maximum — l'énergie d'une
série de puissance se **dérive** de la somme (kW × 10 s / 3600) à la
lecture : une colonne `energie` au niveau minute serait redondante avec
`somme` et se réagrégerait pareil.

```sql
```

Le niveau jour se construit sur `mistral_1h`, avec le fuseau `Europe/Paris` — la leçon de R2 en M06 s'applique ici aussi.

Vérifier la cohérence immédiatement, sans attendre :

```sql
-- la somme doit etre identique aux trois niveaux, sur une journee complete
\i l07/controle-somme.sql
```

Un écart à ce stade signale une erreur d'agrégabilité, pas un problème de rafraîchissement.

### Étape 3 — Les politiques, avec un décalage justifié (10 min)

```sql
SELECT add_continuous_aggregate_policy('mistral_1min',
  start_offset      => INTERVAL '<votre valeur>',
  end_offset        => INTERVAL '<votre valeur>',
  schedule_interval => INTERVAL '<votre valeur>');
```

**Le `start_offset` du niveau minute doit être justifié par le retard d'arrivée mesuré en M05.** Reprendre le tableau du slide 8.2 : p50, p95, p99 ou pire cas — et écrire en commentaire la valeur retenue **et ce qu'on accepte de perdre en la retenant**.

Pour les niveaux supérieurs, le raisonnement change : leur source n'est plus le flux d'ingestion mais l'agrégat du dessous. Leur `start_offset` doit couvrir le retard de rafraîchissement du niveau inférieur, pas le retard d'arrivée des mesures.

Vérifier que les trois travaux sont enregistrés :

```sql
SELECT job_id, application_name, schedule_interval, next_start
FROM   timescaledb_information.jobs
WHERE  application_name LIKE '%Continuous Aggregate%';
```

### Étape 4 — Mesurer le gain (8 min)

```bash
./mesure.sh l07/tableau-de-bord.sql --source brut
./mesure.sh l07/tableau-de-bord.sql --source pyramide
```

Consigner les quatre gains dans `mesures.md`, sous `## M08 — pyramide d'agrégats`.

**Réussi si** le tableau de bord passe sous la seconde. Si ce n'est pas le cas, vérifier d'abord si les quatre requêtes lisent réellement le bon niveau : lire le niveau minute pour afficher un graphe mensuel annule tout le bénéfice.

### Étape 5 — Le protocole de la donnée tardive (12 min)

Suivre exactement les cinq étapes du slide 21, dans l'ordre.

```sql
-- 1. relever la reference, avant toute injection
\i l07/controle-somme.sql   -- noter les trois sommes sur J-3
```

```bash
# 2. injecter cent mille points dates de J-3
./l07/injecter-tardif.sh --jour J-3 --points 100000
```

```sql
-- 3. recontroler : les trois niveaux n'ont pas bouge. C'est normal.
\i l07/controle-somme.sql

-- 4. declencher le rattrapage du niveau le plus bas
--    (bornes calculees du jeu, jamais de now() : le jeu est date)
SELECT max(ts) - INTERVAL '4 days' AS debut,
       max(ts) - INTERVAL '2 days' AS fin FROM mesures \gset
CALL refresh_continuous_aggregate('mistral_1min', :'debut', :'fin');

-- 5. recontroler : les niveaux superieurs n'ont PAS suivi. Les rattraper
--    a la main, bornes identiques, du bas vers le haut
\i l07/controle-somme.sql
CALL refresh_continuous_aggregate('mistral_1h', :'debut', :'fin');
CALL refresh_continuous_aggregate('mistral_1j', :'debut', :'fin');
\i l07/controle-somme.sql
```

**Ce qu'il faut constater, et documenter** : après le rattrapage du niveau minute, les niveaux heure et jour ne bougent pas. Leur politique ne regarde que sa propre fenêtre (`start_offset` → `end_offset`) : une donnée tardive plus ancienne que le `start_offset` du niveau supérieur ne sera jamais rattrapée automatiquement, et un `run_job` forcé sur ce niveau n'y change rien. La propagation se fait à la main, bornée, niveau par niveau — et c'est cette procédure, pas la pyramide, qu'il faut consigner.

### Critères de réussite

- [ ] Les trois niveaux existent, chacun défini au-dessus du précédent
- [ ] **Aucune moyenne n'est stockée** au niveau minute : les quatre expressions sont réagrégeables
- [ ] Le contrôle de somme sur une journée nominale retourne un écart nul aux trois niveaux
- [ ] Les trois politiques sont enregistrées et leur prochain déclenchement est visible
- [ ] Le `start_offset` du niveau minute est justifié par écrit, avec ce qu'il accepte de perdre
- [ ] Le tableau de bord passe sous la seconde, les quatre gains sont consignés
- [ ] Après le protocole de l'étape 5, le contrôle de somme retourne à nouveau un écart nul

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M08`.

### E1 — La pyramide en vaut-elle le coût ?

Créer un agrégat journalier calculé **directement sur les mesures brutes**, en parallèle de la pyramide.

Comparer trois grandeurs : la durée d'un rafraîchissement complet, la durée d'un rafraîchissement incrémental après injection d'une heure de données, et le volume total occupé par les trois niveaux face à celui du niveau unique.

Répondre : à partir de combien de niveaux la pyramide cesse-t-elle d'être rentable, et quel est le critère qui décide ?

### E2 — Le coût du temps réel

Désactiver l'agrégation en temps réel sur le niveau jour, puis mesurer les quatre requêtes du tableau de bord dans les deux configurations.

Mesurer ensuite en situation de charge : lancer l'injecteur de M05 en arrière-plan et refaire les deux mesures. L'écart se creuse-t-il ? Pourquoi ?

### E3 — Modifier un agrégat en production

Ajouter la puissance minimale au niveau minute. La définition ne se modifie pas : il faut créer le nouvel agrégat à côté, le matérialiser sur l'historique, basculer les lecteurs, supprimer l'ancien.

Chronométrer l'opération complète, et écrire la procédure de bascule sous la forme d'une checklist réutilisable. Elle ressemblera beaucoup à celle de M12 — c'est le même problème à plus petite échelle.

### E4 — Un état de percentile dans la pyramide

Stocker `percentile_agg(valeur)` au niveau horaire, puis calculer le p95 journalier par `rollup`. Comparer au p95 journalier calculé directement sur les mesures brutes, et relever l'écart.

C'est l'industrialisation de l'extension E2 de L06.

---

## Pièges et indices

**Le décalage est trop court.**
Des seaux incomplets sont matérialisés, puis figés. Rien ne le signale : les valeurs sont plausibles, simplement trop basses. Le seul moyen de le détecter est de comparer un seau matérialisé au calcul direct sur le brut, sur une période où des données tardives sont arrivées.

**Le niveau supérieur refuse d'être créé.**
Les largeurs de seau doivent s'aligner : le seau du niveau haut doit être un multiple exact de celui du niveau bas. Une heure sur une minute passe ; une heure sur quarante-cinq secondes ne passe pas.

**`avg(moyenne)` au lieu de `sum(somme) / sum(points)`.**
La faute la plus fréquente de l'atelier, et la plus difficile à voir : le résultat est plausible. Le contrôle de somme de l'étape 2 la révèle immédiatement — c'est pour cela qu'il est placé avant les politiques et non après.

**Le temps réel fausse la comparaison.**
Un niveau en agrégation temps réel et un autre non ne se comparent pas : le premier inclut des données que le second ignore. Fixer le même réglage sur les trois avant tout contrôle de somme.

**La matérialisation initiale semble bloquée.**
`refresh_continuous_aggregate` sur l'historique complet du niveau minute traite 190 millions de lignes. Compter plusieurs minutes, et ne pas l'interrompre. Lancer l'étape 2 en lecture pendant ce temps.

**L'appel de rattrapage échoue avec une erreur de transaction.**
`CALL refresh_continuous_aggregate` ne peut pas s'exécuter dans une transaction explicite. Ne pas l'encadrer d'un `BEGIN`, et ne pas l'inclure dans un script qui en ouvre une.

**Le tableau de bord ne passe pas sous la seconde.**
Vérifier quel niveau chaque requête interroge. Un graphe mensuel lu sur le niveau minute annule tout le bénéfice de la pyramide — c'est une erreur de branchement, pas de conception.

---

## Livrable

| Élément | Contenu |
|---|---|
| `agregats.sql` | Les trois niveaux et leurs politiques, décalages justifiés en commentaires |
| `mesures.md` §`M08` | Quatre gains du tableau de bord, résultats du protocole de donnée tardive |
| `l07/tardif-observations.md` | Réponses aux deux questions de l'étape 5 |
| État de reprise | `mistral-M08` |

**Vers la suite.** Les requêtes sont rapides, justes et matérialisées. Mais les mesures brutes occupent toujours quinze gigaoctets pour quarante-cinq jours, et la pyramide en a ajouté. M09 s'attaque au stockage — et le délai de bascule vers le columnstore devra, une fois de plus, dépasser la fenêtre de données tardives mesurée en M05.

---

## Note de production

`reprise/M08.sql` définit les trois niveaux avec un `start_offset` de référence calé sur le **p99** du profil de retard `mistral`. Ce choix est celui de la chaîne, pas la bonne réponse : l'énoncé demande au participant de trancher lui-même et d'écrire ce qu'il accepte de perdre.

La matérialisation initiale du niveau minute est l'opération la plus longue de toute la chaîne d'instantanés — compter quinze à trente minutes selon l'environnement. C'est elle qui domine le budget de reconstruction annoncé à l'annexe B.

`tests/M08.sql` vérifie l'existence des trois niveaux, l'absence de moyenne stockée au niveau bas — par inspection de la définition — et l'écart nul du contrôle de somme. Il ne vérifie pas les valeurs de décalage, qui sont une décision légitime du participant.

**Point tranché sur l'instance de référence (2.29.2)** : la propagation d'un rattrapage vers les niveaux supérieurs n'est pas automatique dès que la donnée tardive est plus ancienne que leur `start_offset`, et un `run_job` forcé ne suffit pas. Le corrigé enseigne la propagation manuelle bornée, niveau par niveau ; l'étape 5 fait constater le comportement avant de le corriger.
