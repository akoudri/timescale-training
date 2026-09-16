# L13 — Cloisonnement MISTRAL

**Module** : M14 · Sécurité et conformité
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M13`
**État de fil rouge en sortie** : `mistral-M14`

---

## Contexte

MISTRAL exploite quatre sites. Chaque exploitant local doit voir ses machines, et seulement les siennes. Le service central voit tout.

L'atelier met en place ce cloisonnement, puis **essaie de le contourner** — trois fois, avec trois mécanismes différents, tous légitimes du point de vue de PostgreSQL. Deux des trois fonctionnent sur une configuration naïve. C'est cette partie qui a de la valeur : un cloisonnement qu'on n'a pas essayé de contourner est une intention, pas une protection.

Le quatrième temps mesure ce que le cloisonnement coûte. Un surcoût non mesuré sera invoqué un jour pour désactiver la protection en urgence.

---

## Prérequis

**État attendu**

- `mistral-M13` atteint
- Les trois niveaux d'agrégats de M08 existent
- Des chunks en columnstore existent, pour la mesure de l'étape 4

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l13/roles.sql` | Le squelette des trois rôles, à compléter |
| `l13/contournements/T1.sql` · `T2.sql` · `T3.sql` | Les trois tentatives |
| `requetes/R1…R3` via `mesure.sh --table … --role …` | Les trois requêtes de référence, exécutables sous un rôle donné, sur la table ou sur la vue |

---

## SOCLE — pour tous

### Étape 1 — Les trois rôles (8 min)

```sql
\i l13/roles.sql
```

Le squelette crée trois rôles et laisse les attributions à compléter.

| Rôle | Doit pouvoir | Ne doit pas pouvoir |
|---|---|---|
| `mistral_ingestion` | Insérer dans `mesures` et `evenements` | Lire l'historique, supprimer, modifier le schéma |
| `mistral_lecture` | Lire les mesures et **les trois niveaux d'agrégats** | Écrire quoi que ce soit |
| `mistral_admin` | Tout, y compris politiques et jobs | — |

Vérifier chaque rôle en basculant dessus, plutôt qu'en relisant les instructions d'attribution :

```sql
SET ROLE mistral_ingestion;
SELECT count(*) FROM mesures;   -- doit echouer
RESET ROLE;
```

**Le rôle d'ingestion qui peut lire est l'erreur la plus fréquente de cette étape** : accorder `SELECT` en même temps que `INSERT` par réflexe annule tout l'intérêt de la séparation.

### Étape 2 — Cloisonner par site (10 min)

**La sécurité au niveau ligne n'est pas disponible ici.** Sur une hypertable au columnstore actif, `ENABLE ROW LEVEL SECURITY` est refusé (2.29 : « operation not supported on hypertables that have columnstore enabled »), et il l'est aussi sur les tables de matérialisation des agrégats continus. Le cloisonnement passe donc par une **vue sécurisée** : même prédicat, autre mécanisme — et retrait de l'accès direct à la table.

```sql
CREATE VIEW mesures_site WITH (security_barrier) AS
  SELECT m.*
  FROM   mesures m
  WHERE  m.series_id IN (
    SELECT af.series_id
    FROM   affectation_capteur af
    JOIN   actifs a ON a.machine_id = af.machine_id
    WHERE  a.site_id = current_setting('mistral.site')::int);

REVOKE SELECT ON mesures FROM mistral_lecture;
GRANT  SELECT ON mesures_site TO mistral_lecture;
```

`security_barrier` interdit au planificateur d'évaluer une fonction du lecteur avant le filtre de la vue ; sans lui, une fonction « indiscrète » peut voir passer les lignes filtrées.

Le site courant se positionne par session :

```sql
SET mistral.site = 2;
SET ROLE mistral_lecture;
SELECT count(DISTINCT series_id) FROM mesures_site;   -- les series du site 2 seulement
SELECT count(*) FROM mesures;                         -- permission denied
RESET ROLE;
```

**Ne pas s'arrêter là.** Faire de même pour les trois niveaux d'agrégats — `mistral_1min_site`, `mistral_1h_site`, `mistral_1j_site` — et retirer l'accès direct aux agrégats. C'est l'objet de la première tentative de contournement, et c'est l'oubli le plus coûteux du module.

### Étape 3 — Les trois tentatives (9 min)

Exécuter chacune, constater si elle réussit, et corriger.

**T1 — passer par l'agrégat**

```sql
\i l13/contournements/T1.sql
```

Sous `mistral_lecture` avec `mistral.site = 2`, interroger `mistral_1h` plutôt que `mesures`. Si les données des quatre sites remontent, l'agrégat est un canal de fuite complet — et il est plus rapide que la table qu'il contourne.

*À corriger* : se demander ce que l'étape 2 a cloisonné, et ce qu'elle n'a pas touché — et par quel chemin ce rôle lit encore la pyramide.

**T2 — utiliser le propriétaire**

```sql
\i l13/contournements/T2.sql
```

Se connecter sous le rôle propriétaire de la table et rejouer la requête sur `mesures` : les quatre sites remontent.

*À corriger* : se demander d'abord si cette tentative est corrigeable techniquement, ou si elle appelle une règle d'organisation à écrire. Puis vérifier par requête sur `information_schema.role_table_grants`, pas de mémoire, quels rôles conservent un accès direct à `mesures` et aux tables de matérialisation.

**T3 — passer par un job**

```sql
\i l13/contournements/T3.sql
```

Appeler l'action de contrôle qualité de M11, créée sous un compte d'administration. Elle lit toutes les séries, tous sites confondus, et consigne le résultat dans une table lisible par `mistral_lecture`.

*À corriger* : deux surfaces à examiner — sous quel rôle l'action s'exécute, et qui peut lire la table qu'elle remplit. C'est le sujet du slide 14.1 sur les jobs, et le fil laissé ouvert par M11.

Consigner pour chacune : réussie ou non avant correction, et la correction appliquée.

### Étape 4 — Mesurer le surcoût (8 min)

Protocole de M02, appliqué à quatre configurations.

```bash
for r in R1-dernier-point R2-fenetre-3j R3-agregation-fenetre; do
  ./mesure.sh requetes/$r.sql --table mesures      --role mistral_admin     # acces direct a la table
  ./mesure.sh requetes/$r.sql --table mesures_site --role mistral_lecture   # a travers la vue
done
```

Relever, pour les trois requêtes de référence :

| Grandeur | Accès direct | Via la vue | Rapport |
|---|---|---|---|
| R1 · point le plus récent | | | |
| R2 · fenêtre de 3 jours | | | |
| R3 · agrégation complète | | | |

Puis produire les plans des deux versions de R2, et répondre :

- le prédicat de cloisonnement apparaît-il comme un filtre appliqué tardivement, ou est-il poussé au plus près de la lecture ?
- sur les chunks en columnstore, le nombre de lots traités change-t-il ?

**Ce qu'il faut observer** : les trois rapports ne vont pas forcément dans le même sens. Pour chacun, comparer les deux plans et dire ce que la vue a changé — puis en tirer une règle d'exploitation, en une phrase, pour un tableau de bord cloisonné.

Consigner dans `mesures.md`, sous `## M14 — coût du cloisonnement`.

### Critères de réussite

- [ ] Les trois rôles existent et sont **vérifiés par bascule**, pas par relecture des attributions
- [ ] `mistral_ingestion` ne peut pas lire
- [ ] Le cloisonnement s'applique aux mesures **et aux trois niveaux d'agrégats**
- [ ] Les trois tentatives de contournement échouent après correction
- [ ] Pour chacune : le résultat avant correction est consigné
- [ ] Le surcoût est chiffré sur les trois requêtes, avec les rapports
- [ ] L'effet sur l'élimination de lots en columnstore est constaté

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M14`.

### E1 — Cloisonnement et columnstore

Mesurer précisément l'interaction : ratio de compression inchangé, mais nombre de lots traités par R2 avant et après activation de la politique.

Répondre : le prédicat de cloisonnement porte-t-il sur une colonne de segment ? Si non, peut-on le réécrire pour qu'il le fasse — et à quel prix sur la lisibilité de la politique ?

### E2 — Effacer un actif, partout

Un client exige l'effacement de toutes les données d'une machine. Exécuter l'opération complète :

1. dans les mesures brutes, y compris les chunks en columnstore
2. dans les trois niveaux d'agrégats
3. dans la table d'alertes de M11

Chronométrer chaque étape et chiffrer le total. Puis écrire ce qui reste : les sauvegardes, et le délai au terme duquel elles auront expiré.

### E3 — Recréer l'action sous un rôle dédié

Reprendre l'action de M11 et la recréer sous `mistral_qualite`, un rôle disposant du strict nécessaire.

Vérifier ensuite qu'elle ne voit plus que son périmètre — et constater ce qu'elle ne peut plus faire. Le compromis est réel : une action cloisonnée détecte moins de choses.

### E4 — La note au délégué à la protection des données

Rédiger la note d'une page qui répond à une demande d'effacement : ce qui est effacé immédiatement, ce qui l'est sous N jours, ce qui subsiste dans les sauvegardes jusqu'à M jours, et pourquoi.

C'est un exercice de rédaction, pas de SQL. Il est plus difficile qu'il n'y paraît, et c'est celui que le participant réutilisera.

---

## Pièges et indices

**Le cloisonnement fonctionne sur les mesures, pas sur les agrégats.**
C'est T1, et c'est le piège central de l'atelier. Les agrégats continus sont des objets distincts, et leurs tables de matérialisation refusent la RLS : ce qui a été fait pour `mesures` à l'étape 2 reste à faire pour chaque niveau, faute de quoi la pyramide est un canal de fuite complet — et plus rapide que la table qu'elle contourne.

**Le propriétaire de la table passe à côté de la vue.**
C'est T2, et c'est structurel : il lit la table, pas la vue. Tester systématiquement avec un rôle dédié, jamais avec le compte qui a créé les tables — et vérifier qu'aucun rôle de lecture ne conserve de `GRANT` direct.

**`ENABLE ROW LEVEL SECURITY` est refusé.**
Attendu en 2.29 sur une hypertable compressée et sur les tables de matérialisation. Ce n'est pas un problème de droits : c'est la raison d'être de la vue barrière.

**Le job de M11 voit toujours tout.**
C'est T3, et c'est attendu : il s'exécute sous le rôle qui l'a créé. Ce n'est pas un défaut du produit, c'est un angle mort de la conception — traité en E3.

**Le rôle d'ingestion peut lire l'historique.**
`GRANT INSERT` a été accompagné d'un `GRANT SELECT` par réflexe. Sur une hypertable, `INSERT` seul suffit — vérifier par bascule de rôle.

**Le surcoût mesuré est nul, ou négatif.**
Trois causes. Le rôle utilisé lit encore la table directement. Ou la requête porte sur une table non protégée. Ou le prédicat est si sélectif qu'il réduit le volume lu au point de compenser son propre coût — ce dernier cas est réel sur les fenêtres, et c'est le motif dernière-valeur qu'il faut alors mesurer.

**`current_setting` retourne une erreur sur une session neuve.**
Le paramètre de site n'est pas positionné. En production, il l'est par l'application à l'ouverture de connexion — prévoir une valeur par défaut, ou une politique qui ne retourne rien plutôt que d'échouer.

**Les tableaux de bord tombent après l'étape 2.**
Le rôle de lecture n'a pas reçu les droits sur les agrégats continus. C'est l'inverse de T1, et les deux se produisent dans la même séance.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l13/roles.sql` | Les trois rôles complétés, politiques comprises |
| `l13/contournements/resultats.md` | Pour chaque tentative : résultat avant correction, correction appliquée |
| `mesures.md` §`M14` | Le surcoût sur les trois requêtes, et l'effet sur l'élimination de lots |
| État de reprise | `mistral-M14` |

**Vers la suite.** L'instance est cloisonnée, sauvegardée, automatisée. Un agrégat continu ne se rafraîchit plus depuis onze jours, et personne ne l'a vu. M15 rassemble le jeu de requêtes de diagnostic construit depuis M02, et met la salle face à deux pannes injectées à son insu.
