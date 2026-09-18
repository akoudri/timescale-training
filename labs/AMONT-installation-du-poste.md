# AMONT — Installation du poste, du dépôt nu à l'environnement vérifié

**Quand** : avant le premier jour, ou en séance J1 avant L01 (compter 45 min
sur une machine vide, réseau compris).
**État de fil rouge en sortie** : « jeux restaurés » — le point d'entrée de L01.

---

## Contexte

Les quinze ateliers supposent un poste où deux instances PostgreSQL tournent
dans Docker et où la base `mistral` contient déjà le référentiel MISTRAL, cinq
jours de mesures et le jeu à forte cardinalité. Ce document décrit la
séquence qui amène un poste vide à cet état, **dans l'ordre**, avec ce que
chaque commande produit et le temps qu'elle prend.

Rien ici n'est un exercice. Le parcours amont se joue une fois, sans
réflexion à mener ; tout ce qui demande une décision commence en L01.

---

## Ce que fait le parcours amont, et ce qu'il laisse à L01

| Action | Parcours amont | L01 |
|---|---|---|
| Installer Docker, `uv`, cloner le dépôt | ✔ (étapes 1-3) | |
| Générer les jeux de données dans `generateur/output/` | ✔ (étape 4) | |
| Créer `pgdata/`, `pgdata-legacy/`, `archives/` à votre nom | ✔ (étape 5, par `restaurer.sh`) | |
| Démarrer les instances `timescaledb` et `legacy`, épinglées à 2 vCPU / 8 Go | ✔ (étape 5) | vérification seulement |
| Créer la base `mistral` avec l'extension `timescaledb` | ✔ (étape 5) | |
| Restaurer le référentiel, `mesures` (5 jours, table ordinaire), `mesures_hc` | ✔ (étape 5) | |
| Restaurer `mistral_legacy` sur l'instance PostgreSQL 16 | ✔ (étape 5) | |
| Préparer le point d'inclusion `conf.d/` dans `postgresql.conf` | ✔ (étape 5) | |
| Créer `timescaledb_toolkit` et `pg_stat_statements` dans `mistral` | | ✔ étape 2 |
| Copier la configuration d'atelier dans `conf.d/` et redémarrer | | ✔ étape 3 |
| Produire la ligne de base R1-R3 et le volume de départ | | ✔ étapes 4-5 |
| Charger le jeu complet de 45 jours dans l'hypertable | | L02 |

Tout ce qui est coché « parcours amont » est fait par un script et n'est **pas
à refaire** en L01.

---

## Prérequis matériels

- 2 vCPU et 8 Go réservables au conteneur `timescaledb` (donc un poste à
  4 cœurs / 16 Go est confortable, 2 cœurs / 8 Go est le strict minimum)
- **60 Go d'espace disque libre** sur la partition qui porte le dépôt :
  environ 12 Go de jeux générés, 4 Go d'images Docker, le reste pour les deux
  instances et les copies des ateliers
- Accès réseau pour tirer les images Docker et les paquets Python

## Prérequis calendaire : la session précède la fenêtre du jeu

Le jeu MISTRAL couvre 45 jours datés (dans la configuration livrée : du
15 septembre au 30 octobre 2026). Plusieurs politiques posées pendant la
formation sont relatives à l'horloge murale — bascule en columnstore
après 7 jours, rétention à 30 jours, rafraîchissement des agrégats — et
elles agissent pour de vrai dès que la date de la session dépasse le début
de la fenêtre : compression prématurée, purge du jeu, agrégats vidés. Les
fiches raisonnent donc avec **une session antérieure à la fenêtre**, et
`verifier-poste.sh` refuse un poste dont la date est dans ou après la
fenêtre. Si la formation a lieu plus tard, régénérer le jeu avec une
fenêtre future (étape 4, « choisir la fenêtre »).

---

## Étape 1 — Docker et Docker Compose, sans `sudo`

Sur Ubuntu, installer Docker Engine et le plugin Compose (paquets `docker.io`
et `docker-compose-v2`, ou Docker CE depuis le dépôt de Docker). Puis
**ajouter votre compte au groupe `docker`** :

```bash
sudo usermod -aG docker $USER
```

Fermer la session et la rouvrir : l'appartenance aux groupes est lue à
l'ouverture de session, un nouveau terminal ne suffit pas (`newgrp docker`
permet de tester sans se déconnecter). Vérifier :

```bash
docker info >/dev/null && docker compose version
```

Les deux commandes doivent répondre **sans `sudo`**. Toute la suite en
dépend : un `sudo docker compose up` crée les répertoires de données au nom
de root, et l'instance ne démarrera plus sous votre compte (voir les pièges).

Docker Desktop pour Linux, macOS ou Windows n'a pas besoin du groupe. Sur
macOS et Windows, dimensionner la machine virtuelle de Docker Desktop à
**plus de 8 Go** avant de continuer, sinon la limite du conteneur est
silencieusement ignorée.

## Étape 2 — `uv`, le gestionnaire Python du générateur

Le générateur de jeux de données est un projet Python géré par `uv`. Une seule
commande l'installe, sans `sudo`, dans `~/.local/bin` :

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ouvrir un nouveau terminal (ou `source ~/.bashrc`) et vérifier avec
`uv --version`. Sur une Ubuntu minimale, installer `curl` d'abord
(`sudo apt install curl`). Alternatives : `sudo snap install astral-uv --classic`
ou `pipx install uv`.

**Python 3.12 n'est pas à installer.** Le générateur l'exige, mais `uv`
télécharge lui-même un interpréteur compatible s'il n'en trouve pas sur le
poste. Aucun PPA, aucun `apt install python3.12`.

## Étape 3 — Cloner le dépôt

```bash
git clone <URL du dépôt> timescale-training
cd timescale-training
```

Le dépôt contient trois répertoires : `labs/` (les fiches), `atelier/`
(compose, scripts, fichiers fournis — c'est le répertoire de travail de toute
la formation) et `generateur/` (le générateur des jeux). Les jeux eux-mêmes
ne sont pas versionnés : c'est l'objet de l'étape suivante.

## Étape 4 — Générer les jeux de données

Depuis `generateur/` :

```bash
cd generateur
uv sync                        # environnement Python, ~1 min la première fois
uv run mistral-gen generer     # fichiers COPY binaires et CSV, ~20 s, ~9 Go
uv run mistral-gen dumps       # dumps PostgreSQL, conteneur postgres:16 éphémère, ~2 min 30
cd ..
```

La génération est déterministe : la graine `20260315` de `config.yaml`
produit les mêmes fichiers sur tous les postes, ce qui rend les résultats
comparables entre participants. `output/MANIFESTE.json` en donne les
empreintes et les comptages.

À la fin, `generateur/output/` doit contenir au moins :

| Fichier | Rôle | Taille |
|---|---|---|
| `mesures-avant.dump` | `mesures` en table ordinaire, jours 1-5 (restauré maintenant) | 0,2 Go |
| `mistral-referentiel.dump` | sites, actifs, signaux, affectations, météo, événements | 4 Mo |
| `mesures-hc.bin` | jeu à forte cardinalité, 13,4 M lignes (chargé maintenant) | 0,5 Go |
| `mistral-legacy.dump` | la production actuelle de MISTRAL, PostgreSQL 16 (restauré maintenant) | 0,6 Go |
| `mesures.bin` | le jeu complet, 45 jours, 190 M lignes (**chargé en L02**, pas maintenant) | 7,2 Go |
| `machines-avec-arret.json` | les trois arrêts de maintenance, utilisé en L10 | — |

**Choisir la fenêtre.** Si la session est postérieure au 15 septembre 2026,
modifier `fenetre.debut` dans `generateur/config.yaml` avant de générer :
la fenêtre doit commencer **après le dernier jour de la session** et
contenir un changement d'heure Europe/Paris, faute de quoi le générateur
refuse (contrainte 6.1). Par exemple `"2027-10-01T00:00:00+02:00"` couvre
le 31 octobre 2027 (jour de 25 heures, comme dans les fiches) ;
`"2027-03-01T00:00:00+01:00"` couvre le 28 mars 2027 (jour de 23 heures :
le piège du fuseau de L05 change de sens). Les dates absolues citées dans
les fiches et les corrigés (25 et 26 octobre, jour de 25 h) se lisent alors
en relatif au jeu. La copie `mistral_legacy` suit la même règle
(`legacy.debut`).

Si le dépôt a été livré avec des fichiers `.zst` déjà générés (transfert par
clé USB, par exemple), les décompresser en place avec `zstd -d` remplace
l'étape 4. Vérifier alors que les six fichiers ci-dessus sont présents.

## Étape 5 — Restaurer

Depuis `atelier/` :

```bash
cd atelier
./amont/restaurer.sh
```

Le script refuse de partir s'il manque un fichier dans `generateur/output/`
(message « jeu manquant : … (lancer le générateur) » : retourner à l'étape 4).
Sinon, dans l'ordre, il :

1. crée `pgdata/`, `pgdata-legacy/` et `archives/` **à votre nom** ;
2. tire les images et démarre les deux instances (`docker compose up -d`) ;
3. prépare le point d'inclusion `conf.d/` dans `postgresql.conf` ;
4. crée la base `mistral` avec l'extension `timescaledb`, y restaure la
   table `mesures` de 5 jours et le référentiel, crée l'hypertable
   `mesures_hc` et y charge le jeu à forte cardinalité ;
5. crée `mistral_legacy` sur l'instance PostgreSQL 16 et y restaure la
   production actuelle ;
6. affiche les comptages de contrôle et « parcours amont terminé ».

Compter de quelques minutes à un quart d'heure selon le disque ; la
restauration de la base legacy (3 Go) est la partie la plus longue. Le script
est **idempotent au sens destructif** : le rejouer détruit et recrée les deux
bases. Ne pas le relancer une fois L01 commencé.

## Étape 6 — Vérifier

```bash
./verifier-poste.sh
```

Le script contrôle l'accès à Docker sans `sudo`, le propriétaire des
répertoires de données, les deux instances, l'épinglage mémoire, les huit
tables de `mistral`, la base legacy, l'espace disque, et signale les
extensions que L01 devra créer. Il doit terminer par **« poste conforme »**.
Toute ligne marquée `ABSENTE`, `NON CONFORME` ou `INSUFFISANT` est à
corriger avant L01 ; les lignes `à faire en L01` sont normales à ce stade.

## Étape 7 — Lire L00

`L00-mistral-modele-de-donnees.md` décrit le parc MISTRAL, le référentiel et
les tables que le script vient de restaurer. Sa lecture n'est pas
indispensable pour L01, elle l'est pour L02.

---

## Critères de réussite

- [ ] `docker info` et `uv --version` répondent sans `sudo`
- [ ] `generateur/output/` contient les six fichiers du tableau de l'étape 4
- [ ] `restaurer.sh` s'est terminé sur « parcours amont terminé »
- [ ] `verifier-poste.sh` répond « poste conforme »

---

## Pièges et indices

**Chaque commande `docker` réclame `sudo`, ou répond « permission denied while
trying to connect to the Docker daemon socket ».**
Votre compte n'est pas dans le groupe `docker`, ou la session n'a pas été
rouverte depuis l'ajout. Étape 1. Ne pas contourner par `sudo` : voir le piège
suivant.

**Le conteneur s'arrête aussitôt : « mkdir: cannot create directory
'/home/postgres/pgdata/data': Permission denied ».**
`pgdata/` appartient à root, soit parce que Docker l'a créé lui-même (premier
`up` lancé à la main, sans `restaurer.sh`), soit parce que le script a été
lancé avec `sudo`. L'image tourne sous l'uid 1000 et ne peut pas y écrire.
Arrêter (`docker compose down`), reprendre la propriété du dépôt
(`sudo chown -R $USER:$USER .` depuis la racine du dépôt), relancer
`./amont/restaurer.sh` sans `sudo`.

**« jeu manquant : ../generateur/output/… (lancer le générateur) ».**
L'étape 4 n'a pas été jouée, ou l'a été depuis un autre répertoire. Le
générateur écrit dans `generateur/output/`, que le compose monte dans les
conteneurs sous `/jeux`.

**`uv: command not found` juste après l'installation.**
Le terminal courant ne connaît pas encore `~/.local/bin`. Ouvrir un nouveau
terminal. Si `uv` a été installé avec `sudo`, il est dans `/root/.local/bin`
et invisible pour votre compte : le réinstaller sans `sudo`.

**`uv sync` échoue sur la version de Python.**
Le poste est hors ligne et `uv` ne peut pas télécharger l'interpréteur 3.12.
Revenir en ligne le temps d'un `uv python install 3.12`.

**`restaurer.sh` s'arrête sur « attente des instances… » puis échoue.**
Une instance n'a pas démarré. `docker compose logs timescaledb` (ou `legacy`)
donne la cause ; la plus fréquente est le piège des permissions ci-dessus, la
seconde un port 6543 ou 6544 déjà occupé sur le poste (ports hôte des deux
instances, sur 127.0.0.1 uniquement).

**La limite mémoire affichée par `docker stats` est celle du poste, pas 8 Go.**
Sur macOS et Windows, la machine virtuelle de Docker Desktop est plus petite
que la limite demandée. Étape 1, dernier paragraphe.

---

## Livrable

| Élément | Contenu |
|---|---|
| Poste conforme | `verifier-poste.sh` : « poste conforme » |
| État de reprise | « jeux restaurés » — entrée de L01 |
