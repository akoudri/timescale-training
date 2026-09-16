# Checklist de bascule — migration `mistral_legacy` → `mistral_prod`

À écrire **avant toute manipulation** (L11, étape 1). L'exécution n'est que
la vérification de cette liste. Aucune rubrique ne reste vide ; le
formateur relit la checklist avant d'autoriser l'étape 2.

## Avant la bascule

- [ ] Cible : extension présente (version : ……), schéma en place
      (objets : ……), espace disque ≥ …… (vérifié : ……)
- [ ] Cible : compression NON activée, aucune politique active
- [ ] Source : identifiant monotone disponible pour borner les plages et
      le delta (colonne : ……)
- [ ] Flux d'écriture actif sur la source pendant toute la migration
      (commande : ……)
- [ ] **Procédure de repli, complète, avec ses commandes** :
  1. ……
  2. ……
  3. ……
- [ ] Délai maximal avant déclenchement du repli : …… (décidé à froid)
- [ ] Qui prononce la bascule : ……

## Pendant

| Étape | Critère de passage |
|---|---|
| Copie initiale par plages | …… |
| Delta de rattrapage | …… (faible et **stable** : il oscille, il ne décroît plus) |
| Contrôle 1 — comptage global | seuil : …… |
| Contrôle 2 — somme par jour, sur entiers | seuil : …… |
| Contrôle 3 — échantillon de lignes, champ par champ | seuil : …… |
| Interruption réelle relevée ici → | du premier au dernier geste : …… |

## Bascule (seule étape qui interrompt — chronométrer)

1. Arrêter le flux d'écriture sur la source — commande : ……
2. **Vérifier** l'arrêt (comptage source stable) — requête : ……
3. Delta final — commande : ……
4. Contrôle 1, égalité stricte
5. Séquences remises à niveau côté cible — commande : ……
6. Basculer le flux vers la cible — commande : ……

## Après

- [ ] Compression et politiques réactivées (script : ……), première
      exécution déclenchée
- [ ] Tous les jobs planifiés, avec une prochaine échéance
- [ ] Séquence au-delà du maximum observé — vérifiée par une insertion réelle
- [ ] La source reste intacte jusqu'au : …… ; suppression planifiée le : ……

## Résultats

(consignés à l'exécution : contrôles, interruption mesurée, écarts entre
la procédure écrite et la procédure exécutée)
