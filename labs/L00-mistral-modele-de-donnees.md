# L00 — MISTRAL : le métier et le modèle de données

**À lire après le parcours amont, avant L02.** Ce document décrit ce que les
quinze ateliers manipulent : l'exploitant fictif MISTRAL, son parc, ses
capteurs, et les tables que le parcours amont a restaurées dans la base
`mistral`. Il ne prend aucune des décisions de modélisation de L02 : il
décrit l'existant, le référentiel tel qu'il est livré, et le jeu de mesures
tel qu'il arrive.

---

## 1. Le métier

MISTRAL exploite un parc de production d'électricité renouvelable réparti
sur quatre sites en France :

| Site | Nom | Région | Ce qu'il porte |
|---|---|---|---|
| 1 | Cap de la Serre | Occitanie | 15 éoliennes |
| 2 | Plateau des Brumes | Hauts-de-France | 18 éoliennes |
| 3 | Col du Levant | Grand Est | 9 éoliennes et 1 centrale photovoltaïque |
| 4 | Plaine de l'Adour | Nouvelle-Aquitaine | 2 centrales photovoltaïques et le point de livraison réseau |

Soit **46 actifs** : 42 éoliennes Senvion MM92 de 2 050 kW, 3 centrales
photovoltaïques et 1 point de livraison (le comptage à l'interface avec le
réseau). Chaque actif remonte des mesures via le système de supervision
(SCADA) toutes les **dix secondes**.

Les questions que le métier pose à ces données, et que les ateliers
traduisent en requêtes : quelle est la production horaire d'un site, quelle
énergie a été produite chaque jour (elle se facture à la journée, en heure
locale), quelle est la dernière valeur connue de chaque capteur (le tableau
de bord), quelle machine est disponible, quand un capteur s'est tu.

## 2. Ce que le parcours amont a restauré

Huit tables dans la base `mistral`, toutes dans le schéma `public` :

| Table | Lignes | Rôle |
|---|---|---|
| `sites` | 4 | Les sites, avec région et coordonnées |
| `actifs` | 46 | Les machines : type, modèle, puissance nominale, date de mise en service |
| `signaux` | 25 | Le **catalogue** des types de signaux : libellé, unité, famille |
| `affectation_capteur` | 490 | Quel signal, sur quelle machine, alimente quelle **série** — et depuis quand |
| `meteo` | 38 916 | Relevés et prévisions météo horaires par site |
| `evenements` | 699 981 | Alarmes, arrêts, maintenances, changements d'état des machines |
| `mesures` | 21 168 000 | Les mesures brutes : **5 jours**, table ordinaire (voir §5) |
| `mesures_hc` | 13 440 000 | Un second jeu, à forte cardinalité, réservé à M09 |

Les cinq premières forment le **référentiel** : petit, stable, décrit le
parc. Les trois dernières sont les **séries temporelles** : volumineuses,
en append, décrivent ce qui se passe. Toute la formation tourne autour de la
jointure entre les deux.

## 3. Le référentiel

### `sites` et `actifs`

```
sites(site_id PK, nom, region, latitude, longitude)
actifs(machine_id PK, site_id → sites, type, modele, puissance_nominale_kw, mise_en_service)
```

`type` vaut `eolienne`, `pv` ou `pdl`. Les identifiants de machines sont
numérotés par site : 1 à 15 sur le site 1, 16 à 33 sur le 2, 34 à 43 sur le
3, 44 à 46 sur le 4.

### `signaux` : un catalogue de 25 types

Un signal est un **type de grandeur mesurée**, pas un capteur physique. Il
porte une unité et une **famille**, qui sert plus tard à regrouper, à
choisir la fréquence attendue d'un flux et à cloisonner.

| Famille | Signaux |
|---|---|
| `production` | `puissance_kw`, `energie_kwh`, `disponible`, `puissance_dc_kw`, `puissance_ac_kw`, `puissance_active_kw`, `energie_injectee_kwh` |
| `meteo` | `vitesse_vent_ms`, `direction_vent_deg`, `irradiance_wm2` |
| `mecanique` | `temperature_nacelle_c`, `temperature_multiplicateur_c`, `vitesse_rotor_rpm`, `angle_pale_deg`, `temperature_module_c` |
| `electrique` | `tension_reseau_v`, `tension_dc_v`, `puissance_reactive_kvar`, `tension_l1/l2/l3_v`, `courant_l1/l2/l3_a`, `frequence_hz` |

Chaque type d'actif porte ses propres signaux : **10 par éolienne**
(puissance, énergie, disponibilité, vent, direction, températures, rotor,
angle de pale, tension), **5 types par centrale photovoltaïque**
(puissances DC et AC, tension DC, température de module, irradiance),
chacun mesuré sur **quatre onduleurs**, soit 20 séries par centrale, et
**10 pour le point de livraison** (puissance active et réactive, tensions
et courants par phase, fréquence, énergie injectée).

Deux signaux méritent une attention particulière : `energie_kwh` et
`energie_injectee_kwh` sont des **compteurs cumulatifs**. Ils croissent,
peuvent être remis à zéro, et ne se somment pas comme une puissance. Une
puissance en kW se convertit en énergie ; un compteur se lit par différence.

### `affectation_capteur` : la clé de tout

```
affectation_capteur(series_id, machine_id → actifs, signal_id → signaux, debut, fin)
```

C'est la table pivot. Une **série** (`series_id`) est un flux de mesures ;
l'affectation dit quelle machine et quel signal elle représente, **et sur
quelle période** (`debut`, `fin` ; `fin` vaut NULL pour l'affectation
courante). Une contrainte d'exclusion garantit qu'une série n'a jamais deux
affectations qui se chevauchent.

Pourquoi dater l'affectation ? Parce qu'un capteur se remplace, se
recalibre, se déplace. Sans date, la question « à quelle machine
appartiennent les points d'avant le remplacement ? » n'a pas de réponse.

Comptage de contrôle, à retenir : **4 sites, 46 actifs, 25 signaux,
490 affectations**, une seule affectation courante par série au moment de
la restauration (elles commencent toutes à l'ouverture de la fenêtre).
Les 490 séries se répartissent en 420 pour les éoliennes (42 × 10), 60 pour
le photovoltaïque (3 centrales × 4 onduleurs × 5 signaux) et 10 pour le
point de livraison. Une même machine peut donc porter plusieurs séries du
même signal : c'est `series_id`, pas le couple (machine, signal), qui
identifie un flux.

## 4. Les séries temporelles

### `mesures` : le flux principal

```
mesures(ts TIMESTAMPTZ, series_id INTEGER, valeur DOUBLE PRECISION, qualite SMALLINT)
```

Une ligne par point : quand, quelle série, quelle valeur, quelle qualité.
Pour savoir de quelle machine et de quel signal il s'agit, on joint
`affectation_capteur` sur `series_id` **et sur la date** (`ts` entre
`debut` et `fin`). Le sens de `valeur` dépend du signal : des kW, des m/s,
des °C ou un 0/1 pour `disponible`.

Le drapeau `qualite` :

| Code | Sens | Part |
|---|---|---|
| 0 | nominale | ≈ 98 % |
| 1 | douteuse : autour d'un changement d'état de la machine, ou épisode dégradé du capteur | ≈ 1,5 % |
| 2 | substituée : valeur reconstituée, pas mesurée | < 0,1 % |

Pas d'échantillonnage : **10 secondes**, soit 8 640 points par série et par
jour. Sur 490 séries, cela fait 4,2 millions de points par jour.

### `evenements`

```
evenements(ts, machine_id → actifs, type, code, attributs JSONB)
```

Quatre types : `alarme` (l'immense majorité), `changement_etat` (production,
arrêt, maintenance...), `arret`, `maintenance`. Le champ `attributs` porte
une charge utile qui varie selon le type : gravité et libellé d'une alarme,
durée d'un arrêt, état atteint. Les événements couvrent les 45 jours de la
fenêtre, contrairement à `mesures` (voir §5).

### `meteo`

```
meteo(ts, site_id, temperature_c, vitesse_vent_ms, irradiance_wm2, type)
```

Un relevé par heure et par site (`type = 'releve'`), plus des prévisions
(`type = 'prevision'`, huit fois plus nombreuses). La météo est **par site**,
les mesures sont **par série** : le lien passe par `actifs`.

### `mesures_hc`

Même structure que `mesures`, mais **20 000 séries** à un pas de **15
minutes** sur les 7 derniers jours de la fenêtre. Ce jeu ne représente
aucune réalité métier : il sert uniquement, en M09, à démontrer l'effet de
la cardinalité sur la compression. Il est déjà une hypertable.

## 5. La fenêtre temporelle, et ce qu'elle impose

Le jeu complet couvre **45 jours, du 15 septembre au 30 octobre 2026**
(heure de Paris), soit environ 190 millions de mesures. Cette fenêtre a été
choisie pour contenir le **changement d'heure du 25 octobre** : une journée
de 25 heures, qui piège toute agrégation journalière faite en UTC.

Le parcours amont n'a restauré dans `mesures` que les **cinq premiers
jours** (15 au 19 septembre, 21 168 000 lignes), en **table ordinaire**,
sans index. C'est délibéré : la ligne de base de L01 se mesure sur une
table brute. Le jeu complet (`mesures.bin`, 45 jours) sera chargé en L02,
par COPY binaire, dans la table que vous aurez conçue.

Trois conséquences pratiques pour toutes les fiches :

- **Le jeu est daté.** Il ne bouge pas avec le calendrier. Tout ce qui
  raisonne « depuis maintenant » (`now()`) ne trouve rien : on raisonne
  depuis le dernier point du jeu, `max(ts)`. Les scripts du kit le font.
- **Les horodatages sont en `TIMESTAMPTZ`**, stockés en UTC. Le jeu
  commence le 15 septembre à minuit heure de Paris, soit le 14 septembre
  22:00 UTC : c'est ce que `min(ts)` affiche selon le fuseau de la session.
- **Le jeu contient des irrégularités voulues**, calibrées sur des données
  SCADA réelles de parcs éoliens (voir `ATTRIBUTION.md`) : trois éoliennes
  en arrêt de maintenance prolongé en octobre, dont l'échantillonnage passe
  à l'heure pendant l'arrêt ; deux remises à zéro de compteur d'énergie ;
  une vingtaine d'interruptions de collecte de 35 minutes à 8 heures ;
  environ 2 % de points de qualité non nominale. Aucune de ces
  irrégularités ne touche les cinq premiers jours. Chacune est le sujet
  d'un atelier.

## 6. La source à migrer : `mistral_legacy`

Sur la seconde instance (PostgreSQL 16, conteneur `legacy`), la base
`mistral_legacy` représente **la production actuelle de MISTRAL**, celle
que M12 migrera. Elle contient une table `mesures` partitionnée à la main
par mois (partitionnement déclaratif, partitions créées par un cron), avec
un identifiant `id` alimenté par une séquence, environ 41 millions de
lignes sur 400 séries au pas d'une minute, du 20 juillet au 30 septembre
2026, une table `evenements`, des vues matérialisées recalculées de zéro et
une purge ligne à ligne. Ses données **ne sont pas** celles de `mistral` :
les fenêtres se recouvrent partiellement, les valeurs diffèrent. C'est la
base des cinq requêtes « telles qu'elles tournent aujourd'hui » de L05, et
la source de la migration de L11.

## 7. Outils optionnels : Grafana et pgAdmin

Le compose porte un profil `outils`, jamais démarré par défaut :

```bash
docker compose --profile outils up -d      # depuis atelier/
```

- **Grafana**, sur `http://127.0.0.1:3000` (admin / mistral). Il ne sert
  qu'en L15, où le tableau de bord fourni s'importe et où les quatre
  alertes se définissent. Sa source de données est déjà déclarée ; le rôle
  qu'elle utilise, lui, est à créer en L15.
- **pgAdmin**, sur `http://127.0.0.1:5050`, sans écran de connexion, avec
  les deux serveurs préenregistrés (mot de passe : mistral). Utile pour
  parcourir le référentiel décrit ici et pour lire un plan d'exécution
  graphiquement.

**Aucun des deux ne sert à mesurer.** Toutes les mesures de la formation
passent par `psql` et `mesure.sh` : une durée lue dans une interface
graphique inclut le rendu, et sort du protocole du bloc 2.2.

## 8. Espace disque et nettoyage

Le poste doit disposer de 60 Go libres, et ce budget suppose que chaque atelier range derrière lui. Ceux qui créent des objets volumineux portent une section **Nettoyage** en toute fin de fiche, après les extensions : L03 (copie ordinaire et tables de comparaison, 15 Go), L04 (table de charge à vider), L08 (tables de comparaison), L11 (base cible de migration), L12 (ancien répertoire de données, sauvegarde de base, journaux archivés — le plus lourd, et le seul qui grossit tout seul si on l'oublie). Ce qui appartient à l'état de reprise reste ; le reste part. `df -h` avant et après est un réflexe à prendre.

## 9. Ce que ce document ne dit pas

Comment `mesures` doit être modélisée pour tenir trois ans à l'échelle de
production, quelle clé identifie une série, où mettre le drapeau de
qualité, comment stocker la charge utile des événements : ce sont les six
décisions de L02, et elles vous appartiennent.
