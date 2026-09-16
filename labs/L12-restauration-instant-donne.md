# L12 — Restauration à un instant donné

**Module** : M13 · Sauvegarde, restauration, montée de version
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M11`
**État de fil rouge en sortie** : `mistral-M13`

---

## Contexte

Un exploitant supprime par erreur trois semaines de mesures un mardi à 14 h 32. À 14 h 40, il faut revenir à 14 h 31.

Cet atelier exécute cette restauration de bout en bout. Il produit deux résultats, et le second compte davantage que le premier :

1. **Une durée mesurée.** Personne ne sait combien de temps prend une restauration tant qu'il ne l'a pas fait. Une estimation n'est pas une mesure, et c'est ce chiffre qu'on donne au métier quand il demande un engagement.
2. **Une checklist de vérification post-restauration.** Retrouver les données ne suffit pas : il faut que les hypertables soient encore des hypertables, que les six jobs soient replanifiés, et que les agrégats repartent. C'est l'étape que tout le monde saute.

---

## Prérequis

**État attendu**

- `mistral-M11` atteint : six jobs planifiés, pyramide et politiques en place
- L'instance dispose d'un répertoire d'archivage des journaux, monté et accessible en écriture
- Espace disque disponible pour une copie complète de l'instance

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l12/activer-archivage.sh` | Configure l'archivage et redémarre l'instance |
| `l12/sauvegarde-base.sh` | Prend la sauvegarde de base |
| `l12/incident.sql` | La suppression accidentelle, avec relevé de l'instant |
| `l12/restaurer.sh` | Restauration paramétrée par instant cible |
| `l12/verifier-apres.sql` | La checklist de vérification post-restauration |

---

## SOCLE — pour tous

### Étape 1 — Sauvegarde de base et archivage (10 min)

```bash
./l12/activer-archivage.sh
```

Vérifier que l'archivage fonctionne réellement — un archivage configuré mais en échec est le mode de défaillance le plus courant :

```sql
SELECT archived_count, last_archived_wal, last_archived_time,
       failed_count, last_failed_wal, last_failed_time
FROM   pg_stat_archiver;
```

`failed_count` doit être à zéro, et `last_archived_time` doit être récent. Forcer un changement de journal pour le confirmer :

```sql
SELECT pg_switch_wal();
```

Prendre ensuite la sauvegarde de base, et **chronométrer** :

```bash
time ./l12/sauvegarde-base.sh
```

Consigner la durée et le volume produit.

### Étape 2 — Provoquer l'incident (5 min)

```sql
\i l12/incident.sql
```

Le script relève l'instant précis **avant** de supprimer, et l'affiche :

```sql
SELECT now() AS instant_avant_incident \gset
\echo :instant_avant_incident

-- la fenêtre supprimée se calcule de max(ts), jamais de now() (jeu daté),
-- et porte sur les TROIS derniers jours — la zone rowstore : un DELETE
-- qui traverse les chunks basculés en columnstore échoue sur la limite
-- de décompression DML. La compression protège, de fait, l'historique
-- froid des suppressions accidentelles massives.
SELECT max(ts) - interval '3 days' AS coupure FROM mesures \gset
DELETE FROM mesures WHERE ts >= :'coupure';
```

**Noter cet horodatage.** Le récupérer après coup dans les journaux est possible, mais long — et en production il faut souvent le reconstituer à partir d'un ticket d'incident.

Constater les dégâts :

```sql
SELECT count(*), min(ts), max(ts) FROM mesures;
```

### Étape 3 — Restaurer (12 min)

```bash
time ./l12/restaurer.sh --instant "<horodatage relevé>"
```

Le script :

1. arrête l'instance
2. remplace le répertoire de données par la sauvegarde de base
3. positionne l'instant cible et le mode de rejeu
4. redémarre et laisse rejouer les journaux
5. attend la fin du rejeu avant d'ouvrir la base en écriture

**Chronométrer du premier au dernier geste**, et relever séparément la durée du rejeu des journaux — c'est elle qui croît avec la fenêtre à rattraper, indépendamment de la taille de la base.

### Étape 4 — Vérifier, et pas seulement les données (5 min)

```sql
\i l12/verifier-apres.sql
```

Le script contrôle quatre choses, dans cet ordre.

**Les données sont revenues.**

```sql
SELECT count(*), min(ts), max(ts) FROM mesures;
```

**Les hypertables sont encore des hypertables.**

```sql
SELECT hypertable_name, num_dimensions
FROM   timescaledb_information.hypertables ORDER BY 1;
```

**Les six jobs sont replanifiés, et ont une prochaine échéance.**

```sql
SELECT job_id, proc_name, scheduled, next_start
FROM   timescaledb_information.jobs ORDER BY job_id;
```

**Les agrégats sont cohérents.** Rejouer le contrôle de somme de L07 aux trois niveaux : l'écart doit être nul.

Un seul de ces quatre contrôles en échec invalide la restauration, même si les données sont là.

### Étape 5 — Chiffrer et consigner (3 min)

Reporter dans `mesures.md`, sous `## M13 — restauration` :

| Grandeur | Valeur |
|---|---|
| Durée de la sauvegarde de base | |
| Volume de la sauvegarde | |
| Fenêtre de journaux rejouée | |
| Durée du rejeu | |
| Durée totale, incident à service rétabli | |

**Écrire ensuite une phrase d'extrapolation** : « sur 45 jours et N Go, la restauration a pris T ; à l'échelle de production, la sauvegarde de base sera plus longue proportionnellement au volume, et le rejeu proportionnellement à la fenêtre. »

### Critères de réussite

- [ ] L'archivage est vérifié comme fonctionnel, pas seulement configuré
- [ ] L'instant précédant l'incident a été relevé **avant** la suppression
- [ ] Les données sont retrouvées, aux bornes attendues
- [ ] **Les quatre contrôles de l'étape 4 passent**, jobs et agrégats compris
- [ ] Les cinq durées sont consignées, dont le rejeu séparément
- [ ] La phrase d'extrapolation est écrite

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M13`.

### E1 — Le dump logique face aux chunks compressés

Prendre un dump logique de la base **sans** encadrer la restauration par les deux appels dédiés de l'extension, puis restaurer sur une instance vierge.

Constater précisément ce qui est perdu : les hypertables sont-elles des hypertables ? Les chunks compressés sont-ils lisibles ? Les politiques existent-elles ?

Recommencer avec les deux appels, et comparer. C'est la démonstration du slide 13.1, faite plutôt que racontée.

### E2 — Monter l'extension sur une instance de test

Sur un conteneur jetable, installer une version mineure antérieure, y restaurer un jeu réduit, puis exécuter la mise à jour de l'extension.

Vérifier ensuite le catalogue : version chargée, hypertables intactes, politiques présentes. Et surtout : refaire la vérification **après reconnexion**, pour observer la différence avec une session ouverte avant la mise à jour.

### E3 — Le chemin de montée d'une instance ancienne

Une instance fictive tourne en TimescaleDB 2.21 sur PostgreSQL 15. Établir le chemin complet vers 2.29 sur PostgreSQL 17, étape par étape, en indiquant pour chacune :

- ce qui est monté
- pourquoi cette étape ne peut pas être sautée
- ce qui doit être sauvegardé avant

Le résultat est une procédure d'une page, directement transposable.

### E4 — Les plans avant et après

Capturer un instantané des statistiques de requêtes avant la montée de version de E2, le rejouer après, et comparer les plans des requêtes critiques de M06.

Un plan qui change après une montée de version est un incident silencieux. C'est le sujet de la non-régression de performance de M15.

---

## Pièges et indices

**L'archivage est configuré mais échoue.**
`failed_count` non nul dans les statistiques d'archivage. Cause la plus fréquente : le répertoire cible n'est pas accessible en écriture par l'utilisateur du serveur. Un archivage en échec rend la restauration à un instant donné impossible, et **rien ne le signale** tant qu'on n'en a pas besoin.

**Les hypertables sont devenues des tables ordinaires.**
Ce piège ne concerne que la restauration d'un dump logique, pas la restauration physique de cet atelier. Si le symptôme apparaît malgré tout, c'est que la mauvaise procédure a été suivie — recommencer, il n'y a pas de rattrapage après coup.

**Les données sont là, mais les jobs ne repartent pas.**
Vérifier `scheduled` et `next_start` pour les six. C'est l'étape 4, et c'est celle qu'on saute parce que le comptage des lignes est rassurant.

**L'instant cible tombe après l'incident.**
La restauration s'arrête juste avant l'instant demandé. Si l'horodatage relevé est celui du `DELETE` lui-même plutôt que celui qui le précède, la suppression est rejouée. Reprendre avec une seconde d'avance.

**Le rejeu semble ne jamais finir.**
Vérifier que tous les journaux nécessaires sont présents dans le répertoire d'archivage. Un journal manquant bloque le rejeu à l'endroit exact où il manque, et le message est peu explicite.

**La durée mesurée n'a rien à voir avec la production.**
C'est attendu et il faut le dire. La sauvegarde de base croît avec le volume, le rejeu croît avec la fenêtre de journaux. Consigner la mesure **avec son contexte**, et écrire l'extrapolation plutôt que de laisser transposer le chiffre brut.

---

## Livrable

| Élément | Contenu |
|---|---|
| `mesures.md` §`M13` | Les cinq durées, et la phrase d'extrapolation |
| `l12/verification-post-restauration.md` | La checklist des quatre contrôles, réutilisable |
| État de reprise | `mistral-M13` |

**Vers la suite.** L'instance est sauvegardée et restaurable. Reste à décider qui peut voir quoi — et à répondre à une demande d'effacement portant sur des données compressées, agrégées, et présentes dans les sauvegardes qu'on vient de produire. C'est M14, et les trois obstacles s'y additionnent.

---

## Note de production

`reprise/M13.sql` ne restaure rien : l'état `mistral-M13` est identique à `mistral-M11` du point de vue du schéma et des données. Le module produit des fichiers et une mesure, pas un état.

Le script `l12/incident.sql` **doit être rejouable et déterministe** : la fenêtre supprimée est calculée à partir de `max(ts)` du jeu, jamais à partir de `now()`, faute de quoi le comportement dépend de la date d'exécution de l'atelier.

`tests/M13.sql` vérifie l'existence de la section de mesures et la présence des quatre contrôles dans le fichier de vérification. Il ne vérifie aucune durée.

**Point ouvert** : l'atelier utilise une restauration physique avec rejeu de journaux, montée sur les outils de base de PostgreSQL. C'est le choix le plus neutre en versions et le plus pédagogique. Si l'environnement de référence retenu s'appuie sur un outil de sauvegarde dédié, l'étape 3 doit être réécrite avec cet outil — et l'étape 1 aussi, car la vérification de l'archivage n'y prend pas la même forme. Le reste de l'atelier, y compris les quatre contrôles de l'étape 4, reste inchangé.
