# L05 — Réécriture de cinq requêtes

**Module** : M06 · Interrogation temporelle
**Durée** : 70 min — socle 60 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M05`
**État de fil rouge en sortie** : `mistral-M06`

---

## Contexte

Cinq requêtes extraites de `mistral_legacy`, telles qu'elles tournent aujourd'hui en production. Ce sont elles qui alimentent les tableaux de bord de l'amorce de M01, et elles qui mettent quarante secondes à s'ouvrir.

Quatre sont lentes. **Une est fausse** — et c'est la plus difficile des cinq. Elle retourne un chiffre plausible, ses totaux annuels sont exacts, et aucun contrôle de cohérence ne la signale.

L'atelier ne consiste pas à appliquer des recettes. Pour chaque requête, il faut produire le plan avant, produire le plan après, et **désigner le nœud responsable du gain**. Une réécriture qui va plus vite sans qu'on sache pourquoi n'est pas une réécriture, c'est un coup de chance.

---

## Prérequis

**État attendu**

- `mistral-M05` atteint
- `mesures` est une hypertable chargée, avec le référentiel daté de M03
- L'index de M04 est en place ; l'index `(series_id, ts DESC)` **ne l'est pas encore** — c'est un objet de l'étape 5

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l05/avant/R1.sql` … `R5.sql` | Les cinq requêtes dans leur écriture d'origine |
| `l05/apres/` | Répertoire vide, à remplir |
| `l05/bornes.sql` | Calcule `:debut` et `:fin` à partir du jeu |
| `mesures.md` | Journal de bord |

---

## SOCLE — pour tous

Protocole identique pour les cinq : mesurer avant, produire le plan avant, réécrire, mesurer après, produire le plan après, désigner le nœud responsable, consigner le rapport.

```bash
./mesure.sh l05/avant/R1.sql
./mesure.sh l05/apres/R1.sql
```

### R1 — Production horaire par site, sur trente jours (10 min)

**Avant**

```sql
SELECT a.site_id,
       date_trunc('hour', m.ts) AS heure,
       sum(m.valeur)            AS production
FROM   mesures m, affectation_capteur af, actifs a
WHERE  af.series_id = m.series_id
  AND  a.machine_id = af.machine_id
  AND  m.ts > (SELECT max(ts) FROM mesures) - INTERVAL '30 days'  -- borne calculee du jeu
GROUP  BY 1, 2;
```

Trois défauts à identifier avant de réécrire. Le premier concerne le seau, le deuxième la jointure au référentiel, le troisième porte sur ce qui manque dans les résultats et que M03 avait pourtant traité.

**Attendu** : `time_bucket`, bornes explicites, jointure datée sur `debut` et `fin`.

**Le gain sera modeste.** La requête portait déjà un prédicat temporel, donc l'exclusion de chunks jouait déjà. C'est un résultat correct, pas un échec — le consigner tel quel.

### R2 — Énergie journalière facturable (15 min)

**Avant**

```sql
SELECT time_bucket(INTERVAL '1 day', ts) AS jour,
       sum(energie_kwh)                  AS energie
FROM   mesures_production
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
```

Cette requête est rapide. Elle est fausse.

**Démarche imposée** : ne pas corriger avant d'avoir **démontré** l'erreur. Choisir la semaine du changement d'heure de MISTRAL, exécuter la requête d'origine, exécuter la variante corrigée, et produire le tableau des écarts jour par jour.

```sql
-- comparer les deux decoupages sur la semaine de bascule
SELECT j_utc.jour, j_utc.energie AS sans_fuseau,
       j_loc.energie AS avec_fuseau,
       j_loc.energie - j_utc.energie AS ecart
FROM   ( ... time_bucket(INTERVAL '1 day', ts) ... )                  j_utc
FULL   JOIN ( ... time_bucket(INTERVAL '1 day', ts, 'Europe/Paris') ... ) j_loc
  ON   j_utc.jour = j_loc.jour;
```

**Réussi si** l'écart est chiffré en kilowattheures sur la journée concernée, et si le participant sait dire pourquoi la somme sur l'année reste identique.

### R3 — Courbe de vent à pas régulier (12 min)

**Avant**

```sql
SELECT date_trunc('hour', ts) AS heure, avg(valeur) AS vitesse
FROM   mesures
WHERE  series_id = 137
  AND  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
```

La courbe présente des trous : les heures sans mesure n'apparaissent pas, et l'axe des temps se contracte à l'affichage.

**Attendu** : `time_bucket_gapfill` avec ses bornes, pour que chaque heure de la fenêtre produise une ligne.

**Puis la question qui compte** : faut-il remplir ces lignes ? Consulter le tableau du bloc 6.2. Pour une vitesse de vent, LOCF et interpolation sont **toutes deux des fautes** : la grandeur est trop volatile pour qu'une valeur inventée ait un sens.

La réécriture correcte génère donc les seaux et **laisse les valeurs à NULL**. L'axe devient régulier, le trou reste visible, et le tableau de bord affiche une interruption plutôt qu'une droite fictive.

Écrire la justification dans `l05/apres/R3.sql`, en commentaire. Une réécriture qui remplit sans justifier ne passe pas le critère.

### R4 — Comparaison d'un mois avec le mois précédent (10 min)

**Avant**

```sql
SELECT m1.mois, m1.energie, m2.energie AS mois_precedent
FROM   ( SELECT date_trunc('month', ts) AS mois, sum(energie_kwh) AS energie
         FROM mesures_production GROUP BY 1 ) m1
LEFT   JOIN ( SELECT date_trunc('month', ts) AS mois, sum(energie_kwh) AS energie
              FROM mesures_production GROUP BY 1 ) m2
  ON   m2.mois = m1.mois - INTERVAL '1 month';
```

Deux défauts : l'agrégation est calculée deux fois, et le découpage mensuel souffre du même problème de fuseau que R2.

**Attendu** : une seule agrégation, un seau de largeur variable avec fuseau, et `lag()` pour le décalage.

### R5 — Dernière valeur de chaque capteur (13 min)

**Avant**

```sql
SELECT m.series_id, m.ts, m.valeur
FROM   mesures m
JOIN  ( SELECT series_id, max(ts) AS ts
        FROM   mesures GROUP BY series_id ) d
  ON   d.series_id = m.series_id AND d.ts = m.ts;
```

Huit secondes. C'est le motif du bloc 6.3.

**Démarche imposée**, dans cet ordre :

1. Réécrire en `DISTINCT ON` **sans** créer d'index. Mesurer. Constater que le gain est faible.
2. Créer l'index `(series_id, ts DESC)`. Mesurer à nouveau, sans changer la requête.
3. Produire les deux plans et expliquer ce qui a changé.

C'est l'index qui fait le travail, pas la syntaxe. L'ordre des étapes existe pour rendre ce point impossible à manquer.

**Réussi si** la requête passe sous la seconde et si le participant explique le plan à un voisin sans lire ses notes.

### Critères de réussite

- [ ] Les cinq requêtes sont réécrites dans `l05/apres/`
- [ ] Pour chacune : mesure avant, mesure après, rapport consigné dans `mesures.md`
- [ ] Pour chacune : le nœud responsable du gain est **désigné par écrit**
- [ ] R2 : l'écart est chiffré en kWh sur la journée de bascule, et l'invariance du total annuel est expliquée
- [ ] R3 : les seaux sont générés, les valeurs restent à NULL, et la justification est en commentaire
- [ ] R5 : passe sous la seconde, et l'écart entre l'étape 1 et l'étape 2 est mesuré séparément
- [ ] Le gain modeste de R1 est consigné comme un résultat, pas comme un échec

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M06`.

### E1 — Chiffrer le bug de fuseau sur une année

Étendre la démonstration de R2 aux deux week-ends de bascule d'une année complète. Produire l'écart total en kilowattheures, puis le convertir en euros au tarif de rachat fourni dans `l05/tarifs.md`.

Écrire ensuite la note d'une page qui expliquerait cet écart à un service de facturation : ce qui a été facturé, ce qui aurait dû l'être, et pourquoi le contrôle annuel ne l'a pas détecté.

### E2 — Trois variantes, classées par mesure

Écrire les trois réécritures de « dernière valeur par série » vues au bloc 6.3 — `DISTINCT ON`, jointure latérale sur le référentiel, et la variante s'appuyant sur l'index — puis les classer par mesure.

Refaire le classement en restreignant à 20 séries, puis en l'étendant aux 490. Le classement change-t-il ? Où se situe le seuil ?

### E3 — Quand l'absence doit rester visible

Reprendre R3 et écrire la requête qui **détecte et qualifie** les interruptions plutôt que de les masquer : pour chaque série, la liste des périodes sans mesure de plus de trente minutes, avec leur durée.

C'est cette requête, et non la courbe comblée, qui a une valeur d'exploitation. Elle préfigure le contrôle qualité automatisé de M11.

### E4 — Largeur fixe contre largeur variable

Comparer, sur les seaux mensuels de R4, le résultat obtenu avec une largeur variable et celui obtenu avec une largeur fixe de trente jours.

Chiffrer l'écart sur douze mois et répondre : dans quel cas la largeur fixe est-elle malgré tout préférable ?

---

## Pièges et indices

**`gapfill` retourne une erreur déroutante.**
Les bornes temporelles doivent figurer explicitement dans le `WHERE`, ou être passées en arguments `start` et `finish`. Sans elles, la fonction ne sait pas quels seaux engendrer, et le message ne le dit pas clairement.

**R2 semble correcte.**
Elle l'est sur les totaux annuels, et sur toutes les journées sauf deux. Ne pas chercher l'erreur sur une fenêtre quelconque : aller directement sur la semaine de changement d'heure. C'est là, et seulement là, que l'écart apparaît.

**La réécriture de R5 n'apporte presque rien.**
C'est attendu à l'étape 1, et c'est le but. Sans l'index `(series_id, ts DESC)`, aucune des trois réécritures ne peut gagner. Ne pas créer l'index avant d'avoir mesuré sans lui.

**Le gain de R1 est décevant.**
Elle portait déjà un prédicat temporel : l'exclusion jouait déjà. Son gain viendra des agrégats continus de M08, pas de la réécriture. Consigner le rapport tel quel plutôt que de chercher une optimisation qui n'existe pas.

**R3 est réécrite avec `locf()` par réflexe.**
C'est la faute que l'atelier cherche à provoquer. Relire le tableau du bloc 6.2 : pour une vitesse de vent, LOCF fabrique une donnée fausse. La bonne réponse laisse les valeurs à NULL.

**Les plans avant et après ne sont pas comparables.**
Le cache est chaud après la première exécution. Utiliser `mesure.sh`, qui applique le même protocole aux deux, plutôt que de chronométrer à la main.

**La jointure datée de R1 fait exploser le nombre de lignes.**
Les bornes `debut` et `fin` de l'affectation ont été omises. Une série ayant eu deux affectations produit alors deux lignes par point — même mode de défaillance qu'en L02.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l05/apres/R1.sql` … `R5.sql` | Les cinq réécritures, chacune commentée du nœud responsable du gain |
| `mesures.md` §`M06` | Cinq rapports avant/après, écart R5 avant et après index, écart R2 en kWh |
| `l05/R2-demonstration.md` | Le tableau des écarts jour par jour sur la semaine de bascule |
| État de reprise | `mistral-M06` |

**Vers la suite.** Les cinq requêtes sont rapides et justes. Mais R1 calcule une somme, et R4 aussi — deux grandeurs qui se comportent bien. M07 pose la question suivante : que se passe-t-il quand l'indicateur demandé est une moyenne sur un pas irrégulier, un taux de disponibilité, ou un percentile ? Aucun des trois ne se calcule comme une somme, et aucun des trois ne remonte une hiérarchie de la même façon.

---

## Note de production

`reprise/M06.sql` contient les cinq réécritures de référence **et l'index `(series_id, ts DESC)`**. Cet index fait partie de l'état `mistral-M06` : les modules suivants s'appuient sur lui, notamment M09 où l'ordre de ses colonnes éclaire le choix de `orderby`.

R2 impose une contrainte sur le générateur : la fenêtre de 45 jours du jeu d'atelier **doit couvrir un week-end de changement d'heure**, sans quoi la requête fausse ne peut pas être démontrée. C'est la seule contrainte de calendrier de toute la formation, et elle doit être fixée avant la génération du jeu — soit fin mars, soit fin octobre.

`tests/M06.sql` vérifie la présence de l'index et l'existence des cinq fichiers `apres/`. Il ne vérifie pas les durées : les cinq rapports varient trop d'un environnement à l'autre. Le seul seuil testé est celui de R5, exprimé en rapport minimal avant et après création de l'index.

**Point ouvert** : le tarif de rachat de `l05/tarifs.md`, utilisé par l'extension E1, doit être un ordre de grandeur plausible et daté, pas un chiffre inventé. Il sert à convertir une erreur technique en montant — c'est ce qui rend la démonstration mémorable, et c'est aussi ce qui la rend contestable si le chiffre est fantaisiste.
