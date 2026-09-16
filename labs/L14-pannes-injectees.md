# L14 — Pannes injectées

**Module** : M15 · Diagnostic et supervision
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M14`, altéré à votre insu
**État de fil rouge en sortie** : `mistral-M15`

---

## Contexte

Deux incidents ont été introduits dans votre instance pendant la pause. Vous ne savez ni lesquels, ni combien de temps ils ont été actifs.

**Le critère de réussite n'est pas de les résoudre.** Un participant expérimenté finira par tomber dessus en tâtonnant. Ce qui est évalué, c'est de nommer, pour chaque incident, **la requête de diagnostic qui l'a révélé** — et d'être capable de refaire le chemin devant la salle.

C'est le dernier atelier de la formation, et il ne fait appel à aucune notion nouvelle. Tout ce qu'il faut a été écrit entre M02 et M11.

---

## Règles du jeu

- **En binômes.** Un participant manipule, l'autre tient le journal de diagnostic. On échange après le premier incident.
- **La méthode en cinq temps s'applique** : symptôme, hypothèses, requête de vérification, correction, prévention. Le journal suit ces cinq rubriques.
- **Interdiction de restaurer.** Revenir à `mistral-M14` résoudrait le problème sans rien apprendre. En production, l'option n'existe pas toujours.
- **Interdiction de deviner en modifiant.** Changer un réglage pour voir si ça va mieux n'est pas un diagnostic. Chaque hypothèse se vérifie par une requête avant d'être corrigée.
- **Le formateur ne confirme rien** avant la restitution.

---

## Prérequis

**État attendu**

- L'instance a été préparée par le formateur à partir de `mistral-M14`
- Le jeu de requêtes de diagnostic rassemblé au bloc 15.1 est à disposition
- `mesures.md` contient les mesures de référence des modules précédents

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l15/diagnostic/` | Le jeu de requêtes des quatre familles |
| `l14/journal-modele.md` | La fiche de diagnostic, une par incident |
| `l14/symptomes.md` | Les deux symptômes, tels qu'un utilisateur les rapporterait |

---

## SOCLE — pour tous

### Étape 1 — Lire les symptômes (3 min)

`l14/symptomes.md` contient deux tickets, rédigés comme le ferait un utilisateur. Ils ne contiennent aucune hypothèse technique, et c'est volontaire.

> **Ticket 1** — « Le tableau de bord du site 2 n'a pas bougé depuis ce matin. Les autres écrans ont l'air normaux. »
>
> **Ticket 2** — « L'écran "état du parc" met sept ou huit secondes à s'afficher. Avant-hier c'était instantané. Rien n'a été déployé. »

Reformuler chacun en **symptôme exploitable** : ce qui est observé, sur quel périmètre, depuis quand — sans encore supposer de cause.

### Étape 2 — Diagnostiquer l'incident 1 (12 min)

Remplir `l14/journal-modele.md`, rubrique par rubrique.

**Hypothèses.** En écrire deux ou trois, classées par probabilité et par coût de vérification. La moins chère à vérifier passe en premier, même si elle n'est pas la plus probable.

**Requête de vérification.** Une seule doit départager. Si deux hypothèses restent après l'avoir exécutée, elle n'était pas la bonne — en écrire une autre plutôt que d'en lancer six.

**Correction.** L'appliquer, puis **mesurer son effet** : le symptôme a-t-il disparu, et en combien de temps ?

**Prévention.** Écrire la requête qui aurait détecté l'incident trois jours plus tôt. Elle devient une alerte en L15.

### Étape 3 — Diagnostiquer l'incident 2 (12 min)

Même démarche, journal séparé. Échanger les rôles dans le binôme.

Un indice de méthode, et un seul : les deux incidents ne relèvent pas de la même famille de requêtes du bloc 15.1. Si les deux journaux citent la même famille, l'un des deux diagnostics est probablement superficiel.

### Étape 4 — Restituer (3 min par binôme)

Présenter la **démarche**, pas le résultat. Trois phrases suffisent :

> « Le symptôme était X. Nous avons envisagé A, B et C. La requête Y a montré que c'était B, parce que Z. »

La salle réagit, et le formateur confirme ou infirme à ce moment-là seulement.

### Critères de réussite

- [ ] Les deux symptômes sont reformulés sans hypothèse implicite
- [ ] Chaque journal comporte au moins deux hypothèses, avec leur ordre de vérification justifié
- [ ] **Pour chaque incident, la requête de diagnostic qui l'a révélé est citée explicitement**
- [ ] Les deux corrections sont appliquées, et leur effet mesuré
- [ ] Deux requêtes de prévention sont écrites, une par incident
- [ ] La restitution décrit la démarche, pas seulement la cause

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M15`.

### E1 — Le troisième incident

Un troisième incident est présent, **non documenté dans le catalogue des sept pannes** du bloc 15.2. Il ne produit aucun symptôme visible à l'écran : tout fonctionne, simplement un peu plus tard que prévu.

Le trouver suppose de comparer l'état actuel à une référence — et cette référence est dans `mesures.md`. C'est l'exercice qui montre le mieux pourquoi ce fichier a été tenu pendant cinq jours.

### E2 — Les requêtes de prévention, en série

Pour les trois incidents, écrire la requête qui les aurait détectés trois jours plus tôt, et vérifier qu'elle les détecte effectivement en réintroduisant chaque incident un par un.

Une requête de prévention qui ne se déclenche pas sur l'incident qu'elle est censée prévenir est fréquente, et c'est ce test qui le révèle.

### E3 — En faire des alertes

Transformer les trois requêtes de prévention en alertes dans le tableau de bord, et les soumettre aux quatre critères du bloc 15.3 : déclenchement provoqué, silence en régime normal, action écrite, propriétaire nommé.

C'est le prolongement direct de L15, et la meilleure façon de l'aborder si le temps le permet.

---

## Pièges et indices

**La panne est trouvée, mais par tâtonnement.**
C'est le mode d'échec principal de cet atelier, et il est difficile à admettre parce que le problème est résolu. Reprendre la méthode en cinq temps et refaire le chemin **après** avoir trouvé : quelle requête aurait suffi ?

**Le symptôme reformulé contient déjà la cause.**
« Le job de rafraîchissement ne tourne plus » n'est pas un symptôme, c'est une hypothèse. Le symptôme est « les valeurs affichées n'évoluent plus depuis N heures sur le périmètre P ».

**Six requêtes sont lancées d'affilée.**
Chacune vérifie une hypothèse ; six requêtes signifient qu'aucune n'était discriminante. Écrire l'hypothèse avant la requête, et non l'inverse.

**Les événements d'attente ne montrent rien.**
Une prise unique attrape mal un phénomène intermittent. Boucler la requête toutes les deux secondes pendant une minute et agréger.

**L'incident 2 est diagnostiqué comme « c'est la compression ».**
C'est l'hypothèse réflexe dès qu'une lecture ralentit. Elle est vérifiable en une requête — la vérifier, l'écarter, et passer à la suivante plutôt que de s'y installer.

**Le binôme ne tient pas de journal.**
Sans journal, la restitution devient un récit reconstitué, et la requête décisive est oubliée. Le journal est le livrable, pas la correction.

**La correction est appliquée avant la vérification.**
« On a remis le job en marche et ça va mieux » ne dit pas pourquoi il était arrêté, ni si quelque chose d'autre l'a arrêté. La cause racine peut être ailleurs.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l14/journal-incident-1.md` | Les cinq rubriques renseignées |
| `l14/journal-incident-2.md` | Idem |
| `l15/diagnostic/prevention.sql` | Les deux requêtes de prévention, commentées |
| État de reprise | `mistral-M15` |

**Vers la suite.** Les deux incidents sont corrigés, et deux requêtes de prévention existent. Il reste à les brancher : L15 construit les quatre alertes du premier jour de production, et vérifie qu'elles se taisent en régime normal.
