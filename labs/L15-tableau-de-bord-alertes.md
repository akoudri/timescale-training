# L15 — Tableau de bord et alertes

**Module** : M15 · Diagnostic et supervision
**Durée** : 20 min — socle 18 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M15`
**État de fil rouge en sortie** : `mistral-M15`, augmenté des quatre alertes

---

## Contexte

Le tableau de bord est fourni **déjà construit et déjà branché** sur les huit métriques du bloc 15.3. Le construire de zéro coûterait quarante-cinq minutes et n'enseignerait rien sur TimescaleDB.

Ce que l'atelier demande tient en une phrase : **définir quatre alertes qui se déclenchent quand il faut, et qui se taisent le reste du temps.** Le second critère est de loin le plus difficile, et c'est celui qui sépare une supervision utile d'un bruit que l'équipe finit par filtrer.

Vingt minutes, quatre alertes. C'est court, et c'est délibéré : une liste courte défendable vaut mieux qu'une liste longue qu'on n'a pas le temps d'éprouver.

---

## Prérequis

**État attendu**

- `mistral-M15` atteint : incidents corrigés, requêtes de prévention écrites en L14
- Le tableau de bord Grafana est accessible et affiche les huit métriques
- Les deux requêtes de prévention de L14 sont disponibles

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l15/tableau-de-bord.json` | Le tableau de bord préconfiguré, à importer |
| `l15/metriques.sql` | Les huit requêtes qui alimentent les panneaux |
| `l15/provoquer.sh` | Provoque chacune des quatre situations d'alerte |
| `l15/alertes-modele.md` | La fiche par alerte, à compléter |

---

## SOCLE — pour tous

### Étape 0 — Démarrer Grafana et brancher la source (5 min)

```bash
docker compose --profile outils up -d grafana     # http://127.0.0.1:3000, admin / mistral
```

La source de données « PostgreSQL MISTRAL » est provisionnée sur le rôle `mistral_supervision`, **qui n'existe pas encore**. Le créer avec le strict nécessaire pour les huit requêtes de `l15/metriques.sql` — lecture des mesures et des agrégats, des vues d'information de l'extension, des statistiques de requêtes — et rien de plus : c'est la leçon de L13 appliquée à la supervision. Tant qu'il manque un droit, un panneau reste vide.

Importer ensuite `l15/tableau-de-bord.json` (menu Dashboards, Import, fichier monté sous `/l15` dans le conteneur ou copié depuis le dépôt), en choisissant cette source quand l'import la demande.

### Étape 1 — Définir les quatre alertes (8 min)

Compléter `l15/alertes-modele.md`. Chaque alerte comporte quatre rubriques, et **aucune ne peut rester vide**.

| Alerte | Ce qu'elle détecte | Contrainte sur le seuil |
|---|---|---|
| **A1 — Aucun worker actif** | Le système paraît sain et ne fait plus rien | Binaire : zéro processus TimescaleDB actif |
| **A2 — Job sans succès** | L'échec répété, et la suspension oubliée | **Relatif** : ancienneté du dernier succès supérieure à N fois la période du job |
| **A3 — Flux muet** | Un collecteur arrêté, avant que la courbe ne s'en aperçoive | **Relatif** à la fréquence attendue du flux, pas une durée fixe |
| **A4 — Espace disponible** | La seule qui doive réveiller quelqu'un la nuit | Seuil **et** tendance : le seuil seul se déclenche trop tard |

Les quatre rubriques par alerte :

1. **L'expression du seuil**, en SQL ou en langage du tableau de bord
2. **Ce que fait celui qui la reçoit** — une phrase, une action concrète
3. **Le propriétaire nommé**, qui peut décider de la retirer
4. **La raison de la retenir** dans une liste de quatre, plutôt qu'une autre

**A2 et A3 doivent être exprimées en relatif.** Un seuil absolu sur A2 devient faux dès qu'on change la période d'un job — ce qui arrivera, et personne ne pensera à ajuster l'alerte. **Et A2 se limite aux jobs déjà échus** : une politique jamais exécutée affiche `last_successful_finish = -infinity`, faux positif garanti si l'alerte compare cette valeur à la période.

### Étape 2 — Les déclencher (6 min)

```bash
./l15/provoquer.sh --alerte A1
./l15/provoquer.sh --alerte A2
./l15/provoquer.sh --alerte A3
./l15/provoquer.sh --alerte A4
```

Le script remet en état après chaque provocation. Vérifier pour chacune :

- l'alerte se déclenche
- **elle se déclenche pour la bonne raison** — lire la valeur qui a franchi le seuil, pas seulement le voyant
- elle retombe une fois la situation rétablie

Une alerte qui se déclenche mais ne retombe pas est aussi inutilisable qu'une alerte qui ne se déclenche pas.

### Étape 3 — Vérifier le silence (4 min)

Laisser tourner le régime normal, sans rien provoquer, et vérifier qu'aucune des quatre ne s'active.

Quatre minutes ne prouvent rien statistiquement, et il faut le dire. **Le vrai test est de reprendre chaque expression de seuil et de répondre par écrit : quelle situation normale pourrait la franchir ?**

- Un pic de charge le lundi matin ?
- Une maintenance planifiée ?
- Un flux dont la fréquence varie légitimement selon la saison ?

Une alerte dont on ne sait pas répondre à cette question n'est pas prête.

### Critères de réussite

- [ ] Les quatre alertes sont définies, avec leurs quatre rubriques renseignées
- [ ] **A2 et A3 sont exprimées en relatif**, pas en valeur absolue
- [ ] A4 combine un seuil et une tendance
- [ ] Les quatre se déclenchent sur situation provoquée, **et retombent** après rétablissement
- [ ] Pour chacune, la valeur ayant franchi le seuil a été lue et vérifiée
- [ ] Pour chacune, une situation normale susceptible de la franchir a été envisagée par écrit

---

## EXTENSION — pour aller plus loin

Non évaluée.

### E1 — La régression de performance

Capturer un instantané des statistiques de requêtes, déployer une modification volontairement défavorable — un index supprimé, un paramètre mémoire réduit — puis rejouer et comparer.

Identifier la régression sur les trois grandeurs : temps total, nombre d'appels, blocs lus. Répondre : laquelle des trois l'a révélée le plus clairement ?

### E2 — Brancher les alertes de L14

Ajouter les deux requêtes de prévention écrites en L14 comme cinquième et sixième alertes, puis les soumettre aux mêmes tests que les quatre premières.

Puis se poser la question qui compte : maintenant qu'il y en a six, laquelle retirer pour revenir à quatre ?

### E3 — Défendre la liste courte

Rédiger une note d'une page qui justifie la liste des quatre alertes du premier jour de production — **et surtout ce qui en est exclu**.

Pourquoi pas d'alerte sur la durée des requêtes ? Pourquoi pas d'alerte sur le ratio de compression ? Pourquoi pas d'alerte sur le nombre de chunks ?

Ce sont les exclusions qui rendent la liste défendable, pas les inclusions.

---

## Pièges et indices

**L'alerte se déclenche en régime normal.**
Son seuil est absolu, ou trop serré. C'est le mode d'échec principal, et il ne se voit qu'au bout de quelques jours — d'où l'étape 3, qui remplace la durée par un raisonnement écrit.

**L'alerte se déclenche mais ne retombe pas.**
La condition de retour n'est pas l'inverse de la condition de déclenchement. Sur A2 notamment, l'ancienneté du dernier succès ne redescend qu'après une exécution réussie, pas après la correction.

**A3 se déclenche sur tous les flux à la fois.**
La fréquence attendue est exprimée globalement alors qu'elle diffère par flux : les mesures arrivent à 0,1 Hz, la météo au pas horaire. Le seuil doit être relatif à la fréquence du flux concerné.

**A4 se déclenche trop tard.**
Un seuil seul se franchit au moment où il est déjà trop tard pour agir. La tendance — combien de jours restent au rythme actuel — donne le délai d'action.

**L'instantané de statistiques est vide.**
Le module de suivi des requêtes doit être actif **avant** l'incident. C'est une ligne à ajouter à la checklist de mise en service de M02, et l'occasion de le faire.

**Le tableau de bord affiche des panneaux vides.**
Le rôle utilisé par Grafana n'a pas les droits sur les vues d'information ni sur les agrégats. C'est le prolongement direct de L13 — et l'illustration que le cloisonnement se conçoit avec la supervision, pas contre elle.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l15/alertes.md` | Les quatre alertes, quatre rubriques chacune |
| `l15/tableau-de-bord.json` | Exporté avec les alertes configurées |
| `l15/silence.md` | Pour chaque alerte, la situation normale envisagée et pourquoi elle ne la franchit pas |
| État de reprise | `mistral-M15` complet |

**Vers la clôture.** Le jeu de requêtes de diagnostic et les quatre alertes sont les deux livrables qui servent dès le premier jour de production. `mesures.md`, ouvert au deuxième module de la formation, devient le premier document d'exploitation.

La séquence de clôture reprend la carte des concepts, revient sur les six pathologies de M01 — et chacun écrit trois actions datées sur son propre contexte.
