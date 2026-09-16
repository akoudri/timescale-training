# Tarifs de stockage — grille pour l'extension E3 de L09

Grille identique à `l08/tarifs-stockage.md`, rappelée ici pour l'extension E3
(étagement avec et sans, calcul de l'étape 4 repris à l'échelle de production).

**Tarifs publics relevés en septembre 2026, hors taxes, à actualiser avant
chaque session.** Les prix sont en dollars par gigaoctet et par mois ;
l'hypothèse de conversion est **1 $ ≈ 0,90 €** (à ajuster au cours du
jour). Ils servent à chiffrer une économie annuelle à l'échelle de
production (estimation à 3 ans de L02) — l'ordre de grandeur compte, pas
le centime.

## Grille

| Stockage | Prix | Source | Ce qu'il représente pour MISTRAL |
|---|---|---|---|
| **Tiger Cloud — stockage haute performance** | **0,177 $/Go-mois** | tigerdata.com/pricing | La base managée : rowstore et columnstore, données interrogeables à pleine vitesse |
| **Tiger Cloud — stockage étagé** (objet, plat, toutes régions) | **0,021 $/Go-mois** | tigerdata.com/pricing ; billet « Introducing tiered storage » | Les chunks anciens déplacés vers le stockage objet, toujours interrogeables, plus lentement. **N'existe qu'en service managé** (M10). Facturé sur le volume **avant** compression |
| AWS EBS gp3 (bloc SSD) | 0,08 $/Go-mois | aws.amazon.com/ebs/pricing | Le disque d'une instance auto-hébergée, hors instance et hors IOPS/débit provisionnés |
| AWS S3 Standard (objet) | 0,023 $/Go-mois (0,0265 en Europe pour les 50 premiers To) | aws.amazon.com/s3/pricing | L'équivalent « à construire soi-même » du stockage étagé : export, suppression, chemin de relecture — un projet, pas un réglage |

## Méthode de calcul (E3 de L09)

1. Partir du volume heap + index à 3 ans estimé en L02 (`l02/volumetrie.sql`),
   échelle de production : 4 000 signaux à 0,1 Hz.
2. Appliquer le **ratio de compression mesuré en L08** sur la part du
   volume qui vit en columnstore (tout sauf la fenêtre rowstore retenue).
3. Multiplier le volume résultant par le tarif haute performance, ×12 pour
   l'année ; comparer au volume non compressé au même tarif : c'est
   l'économie annuelle de la compression.
4. Refaire le calcul en déplaçant les chunks au-delà de la rétention chaude
   vers le stockage étagé à 0,021 $/Go-mois — attention, facturé sur le
   volume **avant** compression : l'écart avec le point 3 est l'argument
   financier de M10.

## Ce que la grille ne couvre pas

- Le coût de l'instance (vCPU, mémoire), des IOPS et du débit provisionnés,
  des sauvegardes et du transfert réseau.
- La différence de latence entre les tiers : un chunk étagé se lit, mais
  plus lentement — le chiffre en euros ne dit rien du temps de réponse.
