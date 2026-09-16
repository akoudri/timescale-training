# Tarifs de valorisation de l'énergie — grille pour l'extension E1 de L05

**Ordres de grandeur relevés en septembre 2026, à actualiser avant chaque
session.** Ils servent à convertir une erreur technique (le bug de fuseau
de R2) en montant. Le chiffre doit être plausible et daté, pas exact : la
démonstration porte sur l'ordre de grandeur de l'écart, pas sur la facture.

## Tarif de référence à utiliser

| Grandeur | Valeur retenue | Source |
|---|---|---|
| **Tarif de rachat éolien terrestre** (complément de rémunération, appels d'offres PPE2 de la CRE) | **87 €/MWh**, soit **0,087 €/kWh** | Prix moyens pondérés des périodes récentes : 87,92 €/MWh (2024), 87,61 €/MWh (printemps 2025), 86,62 €/MWh (10ᵉ période) — CRE, rapport d'état des lieux des appels d'offres PPE2 |

C'est ce tarif que l'extension E1 applique à l'écart en kilowattheures :
`écart_kWh × 0,087 € = écart en euros`.

## Pour situer (ne pas utiliser dans le calcul)

| Grandeur | Ordre de grandeur | Remarque |
|---|---|---|
| Prix spot day-ahead France (EPEX), moyenne annuelle | 70 à 110 €/MWh selon l'année ; journées à 150 €/MWh et plus | Très volatil ; un producteur sous complément de rémunération n'y est exposé qu'à la marge |
| Prix de marché médian retenu par la CRE pour 2030 | ≈ 70 €/MWh (euros 2024) | Sert de référence de long terme aux appels d'offres |

## Rappels pour E1

- MISTRAL compte 42 éoliennes de 2 050 kW nominaux ; le jeu couvre 45 jours
  avec **un** changement d'heure (25 octobre 2026). Pour une année complète,
  l'extension extrapole aux **deux** week-ends de bascule.
- L'écart du bug de fuseau se lit jour par jour (fenêtre décalée de deux
  heures) et sur les journées de 23 h et 25 h ; le total annuel, lui, reste
  juste — c'est précisément ce que la note au service de facturation doit
  expliquer.
- Sources à citer dans la note : le rapport CRE sur les appels d'offres
  PPE2 (cre.fr) et le tableau de bord éCO2mix de RTE pour les prix spot.
