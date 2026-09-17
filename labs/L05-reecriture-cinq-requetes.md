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
./mesure.sh l05/avant/R1.sql --bornes complet
./mesure.sh l05/apres/R1.sql --bornes complet
```

`--bornes complet` reproduit `l05/bornes.sql` (fenêtre entière du jeu). Les bornes par défaut du harnais (jours 1 à 5) ne couvrent ni la semaine de bascule de R2, ni deux mois pour R4.

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

Trois défauts à identifier avant de réécrire. Le premier concerne le seau, le deuxième la jointure au référentiel, le troisième porte sur ce qui manque dans les résultats et que M03 avait pourtant traité. Les nommer par écrit avant de toucher au SQL.

**Le gain sera modeste.** La requête portait déjà un prédicat temporel, donc l'exclusion de chunks jouait déjà. C'est un résultat correct, pas un échec — le consigner tel quel.

### R2 — Énergie journalière facturable (15 min)

**Avant**

```sql
SELECT time_bucket(INTERVAL '1 day', ts) AS jour,
       sum(puissance_kw) / 360.0         AS energie_kwh  -- énergie dérivée de la puissance (pas 10 s)
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
FROM   ( ... la requete d'origine ... )   j_utc
FULL   JOIN ( ... votre variante corrigee ... ) j_loc
  ON   j_utc.jour = j_loc.jour;
```

**Réussi si** l'écart est chiffré en kilowattheures sur la journée concernée, et si le participant sait dire pourquoi la somme sur l'année reste identique.

### R3 — Courbe de vent à pas régulier (12 min)

**Avant**

```sql
SELECT date_trunc('hour', ts) AS heure, avg(valeur) AS vitesse
FROM   mesures
WHERE  series_id = :serie_vent   -- première série vitesse_vent_ms, calculée par l05/bornes.sql
  AND  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
```

La courbe présente des trous : les heures sans mesure n'apparaissent pas, et l'axe des temps se contracte à l'affichage.

**Attendu** : `time_bucket_gapfill` avec ses bornes, pour que chaque heure de la fenêtre produise une ligne.

**Puis la question qui compte** : faut-il remplir ces lignes, et avec quoi ? Consulter le tableau du bloc 6.2 et trancher d'après la nature du signal, pas d'après le confort d'affichage : LOCF, interpolation, ou rien.

Écrire la justification dans `l05/apres/R3.sql`, en commentaire. Une réécriture qui remplit sans justifier ne passe pas le critère — et une réécriture qui ne remplit pas doit le justifier tout autant.

### R4 — Comparaison d'un mois avec le mois précédent (10 min)

**Avant**

```sql
SELECT m1.mois, m1.energie, m2.energie AS mois_precedent
FROM   ( SELECT date_trunc('month', ts) AS mois, sum(puissance_kw) / 360.0 AS energie
         FROM mesures_production GROUP BY 1 ) m1
LEFT   JOIN ( SELECT date_trunc('month', ts) AS mois, sum(puissance_kw) / 360.0 AS energie
              FROM mesures_production GROUP BY 1 ) m2
  ON   m2.mois = m1.mois - INTERVAL '1 month';
```

Deux défauts à trouver : l'un touche au coût, l'autre à la justesse — et R2 vient d'en montrer un des deux. Les fonctions de fenêtrage du bloc 6.3 sont le bon outil pour le premier.

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
- [ ] R3 : les seaux sont générés, et le traitement des trous est justifié en commentaire par la nature du signal
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
Elle l'est sur les totaux annuels. Le découpage en UTC décale la fenêtre de chaque jour de deux heures : l'écart existe tous les jours, mais c'est sur la semaine du changement d'heure qu'il devient indiscutable, avec une journée de 25 heures découpée en 24. Aller directement sur cette semaine, et comparer jour par jour.

**La réécriture de R5 n'apporte presque rien.**
C'est attendu à l'étape 1, et c'est le but. Sans l'index `(series_id, ts DESC)`, aucune des trois réécritures ne peut gagner. Ne pas créer l'index avant d'avoir mesuré sans lui.

**Le gain de R1 est décevant.**
Elle portait déjà un prédicat temporel : l'exclusion jouait déjà. Son gain viendra des agrégats continus de M08, pas de la réécriture. Consigner le rapport tel quel plutôt que de chercher une optimisation qui n'existe pas.

**R3 est réécrite avec `locf()` par réflexe.**
C'est la faute que l'atelier cherche à provoquer. Relire le tableau du bloc 6.2 : la nature du signal décide de ce qu'on a le droit d'inventer, et une vitesse de vent n'est pas une consigne d'angle de pale.

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
