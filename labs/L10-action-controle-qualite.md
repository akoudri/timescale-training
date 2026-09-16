# L10 — Action de contrôle qualité

**Module** : M11 · Automatisation par les jobs
**Durée** : 35 min — socle 30 min, extension en auto-rythme
**État de fil rouge en entrée** : `mistral-M10`
**État de fil rouge en sortie** : `mistral-M11`

---

## Contexte

MISTRAL compte 490 capteurs. Certains cessent de remonter sans que rien ne le signale : liaison coupée, carte défaillante, collecteur arrêté. Aujourd'hui, on s'en aperçoit quand quelqu'un regarde une courbe.

Cet atelier écrit la première tâche métier automatisée de la formation, et elle sert de prétexte à trois choses qui comptent davantage que la tâche elle-même : le **contrat de signature** d'une action, la **configuration qui vit dans la base**, et surtout le fait qu'un job qui échoue **ne dit rien**.

C'est pour cette dernière raison que l'étape 4 impose de provoquer une erreur volontaire. Un participant qui n'a jamais vu où atterrit l'erreur d'un job ne saura pas la chercher le jour où elle se produira.

---

## Prérequis

**État attendu**

- `mistral-M10` atteint : cinq politiques enregistrées et exécutées
- Les workers d'arrière-plan sont actifs — à revérifier, c'est la première cause d'échec de cet atelier

```sql
SHOW timescaledb.max_background_workers;
SHOW max_worker_processes;
```

**Fichiers fournis**

| Fichier | Rôle |
|---|---|
| `l10/alertes-qualite.sql` | Crée la table de consignation |
| `l10/inspecter-jobs.sql` | Les deux requêtes de supervision du bloc 11.1 |
| `l10/couper-capteurs.sh` | Simule l'arrêt de trois capteurs |

---

## SOCLE — pour tous

### Étape 1 — Préparer la table de consignation (5 min)

```sql
\i l10/alertes-qualite.sql
```

Elle contient au minimum : l'instant de détection, la série concernée, l'horodatage de son dernier point, et l'ancienneté constatée.

Simuler ensuite l'arrêt de trois capteurs, pour avoir quelque chose à détecter :

```bash
./l10/couper-capteurs.sh --series 137,208,451 --depuis "3 hours"
```

### Étape 2 — Écrire l'action (10 min)

La signature est imposée : un identifiant de job, une configuration en JSON.

```sql
CREATE PROCEDURE controle_qualite(job_id int, config jsonb)
LANGUAGE plpgsql AS $$
DECLARE
  seuil interval := (config->>'seuil')::interval;
  n     integer;
BEGIN
  -- journaliser le parametre recu : voir les pieges
  RAISE NOTICE 'controle_qualite job=% seuil=%', job_id, seuil;

  -- a completer : consigner dans alertes_qualite chaque serie dont le
  -- dernier point est plus ancien que le seuil (detecte_le, series_id,
  -- dernier_point, anciennete)
  ...

  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'controle_qualite : % capteurs muets', n;
END $$;
```

**Une question à trancher avant d'écrire la requête** : « plus ancien que le seuil » par rapport à quoi ? L'horloge murale, ou le dernier point reçu par le parc ? Le jeu MISTRAL est daté, ce qui règle la question pour l'atelier — mais en production aussi, un incident de collecte global ne doit pas déclarer 490 capteurs muets d'un coup. Écrire le choix en commentaire.

**Ne pas tester en appelant la procédure directement.** Le contexte d'exécution d'un job diffère de celui d'une session interactive — rôle, `search_path`, privilèges. Un test qui passe à la main ne prouve rien.

### Étape 3 — Enregistrer, planifier, vérifier (8 min)

```sql
SELECT add_job('controle_qualite', INTERVAL '1 hour',
               config => '{"seuil": "1 hour"}'::jsonb);
```

Forcer une première exécution, hors transaction :

```sql
CALL run_job(<job_id>);
```

Puis vérifier les trois choses qui comptent :

```sql
-- l'enregistrement et la prochaine echeance
SELECT job_id, proc_name, config, scheduled, next_start
FROM   timescaledb_information.jobs WHERE proc_name = 'controle_qualite';

-- l'historique d'execution
SELECT job_id, last_run_started_at, last_successful_finish,
       last_run_status, total_runs, total_failures
FROM   timescaledb_information.job_stats WHERE job_id = <job_id>;

-- le resultat metier
SELECT * FROM alertes_qualite ORDER BY detecte_le DESC;
```

Les trois capteurs coupés à l'étape 1 doivent apparaître. Si la table est vide alors que le job s'est exécuté avec succès, passer directement au dernier piège.

### Étape 4 — Provoquer une erreur, et la retrouver (7 min)

C'est l'étape qui justifie l'atelier.

Introduire une faute volontaire — par exemple une configuration dont le seuil n'est pas un intervalle valide :

```sql
SELECT alter_job(<job_id>, config     => '{"seuil": "une heure"}'::jsonb,
                           next_start => now() + INTERVAL '10 seconds');
```

Puis **attendre l'échéance** : c'est l'ordonnanceur qui doit exécuter le job. Un `CALL run_job()` en session renverrait l'erreur au client et n'écrirait **rien** dans le journal des erreurs — seules les exécutions lancées par l'ordonnanceur y sont journalisées. Retrouver ensuite la trace de l'échec :

```sql
SELECT job_id, start_time, err_message
FROM   timescaledb_information.job_errors
ORDER  BY start_time DESC LIMIT 5;

SELECT job_id, last_run_status, total_failures, last_successful_finish
FROM   timescaledb_information.job_stats WHERE job_id = <job_id>;
```

**Deux observations à consigner** : rien n'a été journalisé côté applicatif, et `last_successful_finish` ne bouge plus alors que `last_run_started_at` continue d'avancer. C'est exactement le motif que la supervision de M15 devra détecter.

Restaurer ensuite une configuration valide et vérifier que le job repart.

### Critères de réussite

- [ ] L'action est enregistrée, planifiée, et sa prochaine échéance est visible
- [ ] Une exécution forcée détecte les trois capteurs coupés et les consigne
- [ ] L'erreur volontaire apparaît dans le journal des erreurs de l'extension
- [ ] Le participant sait dire **où** chercher l'erreur d'un job, sans hésiter
- [ ] L'écart entre `last_run_started_at` et `last_successful_finish` est constaté et compris
- [ ] Le job repart après restauration d'une configuration valide

---

## EXTENSION — pour aller plus loin

Non évaluée. N'entre pas dans l'état de reprise `mistral-M11`.

### E1 — Purge sélective paramétrée

Écrire une action qui supprime les mesures d'un site déclassé, en dehors du cadre de la politique globale de rétention.

Le site visé et la profondeur doivent venir de la configuration, pas du code. Vérifier ensuite qu'un `alter_job` suffit à changer de site sans redéployer quoi que ce soit.

### E2 — L'effet d'un job long

Lancer une matérialisation complète d'un agrégat en arrière-plan, puis observer l'exécution des politiques concurrentes pendant ce temps.

Relever le décalage entre `next_start` prévu et `last_run_started_at` réel sur les autres travaux. Faire varier le nombre de workers et refaire la mesure : à partir de combien de workers le décalage disparaît-il ?

### E3 — Instrumenter l'action

Modifier `controle_qualite` pour qu'elle consigne sa propre durée d'exécution et le nombre de lignes produites dans une table dédiée.

C'est ce que fait toute action de production sérieuse, et c'est la source de la métrique de fraîcheur du tableau de bord de M15.

### E4 — Le contrôle de cohérence

Écrire l'action qui aurait détecté l'agrégat vide du bloc 10.2 : comparer périodiquement, sur un échantillon de périodes tirées au hasard, la valeur matérialisée dans l'agrégat horaire et le calcul direct sur les mesures brutes.

Consigner tout écart supérieur à une tolérance donnée. C'est la plus utile des quatre extensions, et celle qui demande le plus de réflexion sur le choix de l'échantillon.

---

## Pièges et indices

**Le job ne se déclenche jamais.**
Vérifier le nombre de workers avant tout le reste. Si `max_worker_processes` ne couvre pas la somme des workers de l'extension et du parallélisme, aucun travail ne démarre — et rien ne le signale. C'est la première cause d'échec de cet atelier, et la première panne du catalogue de M15.

**L'action fonctionne à la main mais pas en job.**
Le contexte diffère : rôle propriétaire, `search_path`, privilèges. Toujours tester par `run_job`, jamais par un `CALL` direct de la procédure.

**L'erreur volontaire n'apparaît nulle part.**
Deux causes. Soit on la cherche dans le journal applicatif de PostgreSQL alors qu'elle est dans le journal des erreurs de l'extension : deux endroits distincts. Soit le job a été exécuté par `CALL run_job()` en session : l'erreur est remontée au client et rien n'a été journalisé — seul l'ordonnanceur écrit dans `job_errors`. Rapprocher l'échéance et laisser le job échouer en arrière-plan.

**Le job s'exécute avec succès mais la table reste vide.**
Une configuration mal formée est souvent lue sans erreur et donne une valeur nulle : une soustraction avec `NULL` ne compare rien, et la clause `HAVING` ne retient personne. C'est pour cela que l'action journalise le paramètre reçu dès sa première ligne.

**`run_job` échoue avec une erreur de transaction.**
Comme `refresh_continuous_aggregate`, il ne peut pas s'exécuter dans une transaction explicite. Ne pas l'encadrer d'un `BEGIN`.

**Les trois capteurs coupés n'apparaissent pas.**
Vérifier que le script de coupure a bien agi sur `mesures` et non sur une table de travail, et que le seuil de la configuration est inférieur à l'ancienneté simulée.

**Le job est resté suspendu après un test.**
Un `alter_job(..., scheduled => false)` oublié ne produit aucune erreur : le travail cesse simplement d'exister pour l'ordonnanceur. Vérifier `scheduled` et `next_start`, pas seulement `last_run_status`.

---

## Livrable

| Élément | Contenu |
|---|---|
| `l10/controle-qualite.sql` | La procédure et son enregistrement |
| `l10/observations.md` | Les deux observations de l'étape 4, écrites |
| `mesures.md` §`M11` | Les six jobs recensés, avec leur état |
| État de reprise | `mistral-M11` |

**Vers la suite.** La cible est complète : schéma, dimensionnement, agrégats, compression, rétention, automatisation. Il reste à y amener la production — deux cents gigaoctets qui tournent encore sur `mistral_legacy`, avec un budget d'interruption à négocier. C'est M12.
