# L06 — Trois indicateurs MISTRAL

**Module** : M07 · Hyperfonctions et agrégabilité
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M06`
**État de fil rouge en sortie** : `mistral-M07`

---

## Contexte

Les cinq requêtes de M06 calculaient des sommes et des moyennes sur des grandeurs qui se comportent bien. Cet atelier prend trois indicateurs que le métier de MISTRAL demande réellement, et dont aucun ne se calcule comme une somme.

Il est court et volontairement resserré : trente minutes pour trois requêtes. Ce qui prend du temps n'est pas de les écrire, c'est de **savoir dire pourquoi la version évidente est fausse**. Le premier indicateur impose d'ailleurs d'écrire les deux versions et de chiffrer l'écart.

C'est le dernier atelier avant M08. La règle d'agrégabilité qui en sort commande toute l'architecture des agrégats continus.

---

## Prérequis

**État attendu**

- `mistral-M06` atteint, index `(series_id, ts DESC)` en place
- La table `evenements` est chargée avec les changements d'état des machines
- **Le Toolkit doit être installé** — à vérifier avant de commencer :

```sql
SELECT extname, extversion FROM pg_extension
WHERE  extname = 'timescaledb_toolkit';
```

Aucune ligne signifie que les trois fonctions de l'atelier n'existent pas. L'installer avant, ou basculer sur l'extension E4 qui traite le cas sans Toolkit.

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l06/machines-avec-arret.sql` | La liste des machines et des mois comportant un arrêt de maintenance |
| `l06/indicateurs/` | Répertoire vide, à remplir |
| `mesures.md` | Journal de bord |

Les bornes `:debut` et `:fin` se calculent comme en L05 : `\i l05/bornes.sql` en session psql.

---

## SOCLE — pour tous

### Indicateur 1 — Production mensuelle pondérée (15 min)

**Écrire les deux versions.** C'est l'objet principal de l'atelier.

Version naïve :

```sql
SELECT machine_id,
       time_bucket(INTERVAL '1 month', ts, 'Europe/Paris') AS mois,
       avg(puissance_kw) AS moyenne_naive
FROM   mesures_production
GROUP  BY 1, 2;
```

Version pondérée par le temps, à écrire avec les hyperfonctions du bloc 7.1 (`time_weight`, puis `average`) :

```sql
SELECT machine_id,
       time_bucket(INTERVAL '1 month', ts, 'Europe/Paris') AS mois,
       -- a completer : la moyenne ponderee par le temps de puissance_kw
       ...
FROM   mesures_production
GROUP  BY 1, 2;
```

Choisir ensuite **une machine et un mois comportant un arrêt de maintenance** — la liste est dans `l06/machines-avec-arret.sql` — et produire le tableau des deux valeurs côte à côte, avec l'écart en pourcentage.

Écrire enfin, en deux ou trois phrases, pourquoi la version naïve surestime. La formulation attendue mentionne le pas d'échantillonnage, pas la « qualité des données ».

**Le choix de la méthode** : LOCF ou linéaire ? La puissance instantanée d'une éolienne est-elle une valeur en escalier ou une grandeur continue ? Le tableau du bloc 6.2 s'applique ici aussi — justifier en commentaire.

### Indicateur 2 — Taux de disponibilité (10 min)

```sql
SELECT machine_id,
       duration_in(state_agg(ts, attributs->>'etat'), 'production')  AS temps_production,
       duration_in(state_agg(ts, attributs->>'etat'), 'arret')       AS temps_arret,
       duration_in(state_agg(ts, attributs->>'etat'), 'maintenance') AS temps_maintenance
FROM   evenements
WHERE  type = 'changement_etat'          -- les alarmes ne portent pas d'état
  AND  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1;
```

Puis en déduire le taux de disponibilité — et c'est là qu'est la difficulté.

**Le dénominateur n'est pas la durée de la fenêtre.** C'est la durée pour laquelle on dispose d'une information d'état. Une machine dont le collecteur d'événements a été coupé trois jours n'a pas été indisponible trois jours : on ignore ce qu'elle a fait.

Écrire la requête qui distingue les deux, et vérifier que le taux obtenu ne dépasse jamais cent pour cent. S'il les dépasse, le dénominateur est faux.

### Indicateur 3 — Percentile 95 de la vitesse du vent (5 min)

```sql
SELECT a.site_id,
       approx_percentile(0.95, percentile_agg(m.valeur)) AS p95_vent
FROM   mesures m
JOIN   affectation_capteur af
  ON   af.series_id = m.series_id
 AND   m.ts >= af.debut AND (af.fin IS NULL OR m.ts < af.fin)
JOIN   actifs a ON a.machine_id = af.machine_id
JOIN   signaux g ON g.signal_id = af.signal_id
WHERE  g.libelle = 'vitesse_vent_ms'
  AND  m.ts >= :'debut' AND m.ts < :'fin'
GROUP  BY 1;
```

Comparer au percentile exact calculé sur la même fenêtre, et **relever l'écart**. Il doit être faible et borné — c'est ce qui rend l'approximation défendable.

Consigner les trois indicateurs et l'écart de l'indicateur 1 dans `mesures.md`, sous `## M07 — indicateurs métier`.

### Critères de réussite

- [ ] Les trois indicateurs retournent un résultat cohérent sur l'ensemble du parc
- [ ] L'écart entre version naïve et version pondérée est **chiffré en pourcentage** sur une machine ayant subi un arrêt
- [ ] L'explication de cet écart mentionne le pas d'échantillonnage, et non la qualité des données
- [ ] Le choix LOCF ou linéaire est justifié en commentaire
- [ ] Le taux de disponibilité ne dépasse jamais cent pour cent, et son dénominateur est explicité
- [ ] L'écart entre percentile approché et percentile exact est relevé

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M07`.

### E1 — La moyenne de moyennes

Calculer la moyenne journalière de deux façons : directement sur les mesures, puis comme moyenne des vingt-quatre moyennes horaires.

Chiffrer l'écart sur une journée comportant un arrêt, puis sur une journée nominale. Répondre : sous quelle condition exacte les deux coïncident-elles, et cette condition est-elle jamais vraie sur MISTRAL ?

C'est la démonstration qui rend le tableau du bloc 7.2 opérationnel plutôt que théorique.

### E2 — Réagréger un état de percentile

Construire une table intermédiaire au niveau horaire qui stocke `percentile_agg(valeur)` plutôt que le percentile lui-même. Puis en déduire le p95 journalier par réagrégation :

```sql
SELECT jour, approx_percentile(0.95, rollup(etat)) FROM ... GROUP BY jour;
```

Comparer au p95 journalier calculé directement sur les mesures brutes, et relever l'écart. C'est exactement le mécanisme que M08 industrialise.

### E3 — Réduire une série pour l'affichage

Une courbe de 8 640 points affichée sur 800 pixels ne peut pas montrer 8 640 points. Réduire la série à 500 points **en conservant la forme de la courbe** — pics et creux compris — plutôt qu'en échantillonnant une valeur sur dix-sept.

Comparer visuellement les deux réductions dans Grafana. La différence est spectaculaire sur les rafales de vent.

### E4 — Sans Toolkit

Réécrire l'indicateur 1 en SQL pur, avec des fonctions de fenêtrage : calculer la durée couverte par chaque point via `lead(ts) OVER (...)`, pondérer, sommer, diviser.

Mesurer l'écart de durée avec la version Toolkit, puis énumérer les cas limites qu'il a fallu traiter à la main — premier point de la fenêtre, dernier point, trous, valeurs NULL.

C'est le chemin obligé sur une plateforme managée dépourvue de Toolkit, et il faut savoir ce qu'il coûte.

---

## Pièges et indices

**Le Toolkit n'est pas installé.**
À vérifier avant de commencer, pas au milieu du premier indicateur. Le message d'erreur retourné pour une fonction inexistante ne suggère pas l'installation d'une extension, et fait perdre plusieurs minutes.

**La version naïve donne presque le même résultat.**
La machine ou le mois choisis ne comportent pas d'arrêt : le pas est régulier, donc les deux moyennes coïncident. Utiliser la liste fournie, elle existe pour ça.

**Le taux de disponibilité dépasse cent pour cent.**
Le dénominateur retenu est la durée de la fenêtre alors que les états n'en couvrent qu'une partie. C'est le même piège qu'au bloc 6.2, transposé sur un autre indicateur : une absence d'information n'est pas un état.

**`state_agg` ignore les valeurs NULL en silence.**
Un état non renseigné n'est pas un état, et la fonction ne le signale pas : la ligne est sautée et l'état précédent court jusqu'au changement suivant. Filtrer en amont, ou décider explicitement de le traiter comme un état nommé — mais le décider, pas le subir.

**Le percentile approché et le percentile exact diffèrent.**
C'est attendu. Ce qui compte n'est pas qu'ils soient égaux, mais que l'écart soit borné et mesuré. Le relever plutôt que de le constater : c'est cette mesure qui rend l'approximation défendable devant un métier.

**`time_weight` réclame un ordre.**
La fonction suppose que les points lui parviennent triés par temps au sein de chaque groupe. Sur une hypertable c'est généralement le cas, mais ce n'est pas garanti par le SQL : en cas de résultat aberrant, vérifier ce point avant de mettre en cause la fonction.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l06/indicateurs/production-ponderee.sql` | Les deux versions, écart chiffré et explication en commentaire |
| `l06/indicateurs/disponibilite.sql` | Le taux, avec son dénominateur explicité |
| `l06/indicateurs/p95-vent.sql` | Le percentile approché, et l'écart avec l'exact |
| `mesures.md` §`M07` | Les trois indicateurs, l'écart naïve/pondérée en pourcentage |
| État de reprise | `mistral-M07` |

**Vers la suite.** Ces trois indicateurs sont justes, et recalculés à chaque exécution. M08 les matérialise — mais seulement ceux qui ont le droit de monter dans une hiérarchie. Le tableau du bloc 7.2 devient alors une décision d'architecture : le niveau horaire de la pyramide stockera-t-il des moyennes, ou des états intermédiaires ?
