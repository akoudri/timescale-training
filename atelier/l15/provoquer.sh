#!/bin/bash
# L15 — provoque chaque situation d'alerte, VÉRIFIE l'expression du seuil,
# puis remet en état et vérifie la remise en état (une provocation laissée
# active fausse l'étape 3 « silence »).
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL=(docker compose exec -T timescaledb psql -U postgres -d mistral -At -v ON_ERROR_STOP=1)
ALERTE="${1#--alerte=}"; [ "$#" -ge 2 ] && ALERTE="$2"

etat_a2() { "${PSQL[@]}" -c "
  SELECT count(*) FROM timescaledb_information.jobs j
  LEFT JOIN timescaledb_information.job_stats s USING (job_id)
  WHERE NOT j.scheduled
     OR (s.last_run_started_at IS NOT NULL
         AND s.last_successful_finish > '-infinity'
         AND s.last_successful_finish < now() - 3 * j.schedule_interval);"; }
etat_a3() { "${PSQL[@]}" -c "
  SELECT count(*) FROM (
    SELECT series_id, max(ts) AS dernier FROM mesures
    WHERE ts >= (SELECT max(ts) - interval '1 day' FROM mesures)
    GROUP BY 1) s
  WHERE s.dernier < (SELECT max(ts) FROM mesures) - interval '10 minutes';"; }

case "$ALERTE" in
  A1)
    echo "A1 · expression : zéro processus TimescaleDB actif"
    "${PSQL[@]}" -c "SELECT count(*) || ' workers actifs (declenche si 0)'
                     FROM pg_stat_activity WHERE application_name LIKE 'TimescaleDB%';"
    echo "provocation réelle = max_background_workers=0 + redémarrage (2 restarts) ;"
    echo "faite en salle sur l'instance du binôme, pas automatisée ici."
    ;;
  A2)
    # le job suspendu est celui du rafraîchissement de mistral_1min : son
    # identifiant dépend du poste (ordre de création des politiques) — il
    # se résout par requête, jamais codé en dur
    job=$("${PSQL[@]}" -c "SELECT job_id FROM timescaledb_information.jobs
                           WHERE proc_name = 'policy_refresh_continuous_aggregate'
                             AND hypertable_name = 'mistral_1min';")
    [ -n "$job" ] || { echo "A2 : aucune politique de rafraîchissement sur mistral_1min" >&2; exit 1; }
    avant=$(etat_a2)
    "${PSQL[@]}" -c "SELECT alter_job($job, scheduled => false);" > /dev/null
    pendant=$(etat_a2)
    "${PSQL[@]}" -c "SELECT alter_job($job, scheduled => true);" > /dev/null
    apres=$(etat_a2)
    echo "A2 · job suspendu puis réactivé : $job"
    echo "A2 · anomalies : avant=$avant pendant=$pendant apres=$apres (attendu 0/≥1/0)"
    ;;
  A3)
    avant=$(etat_a3)
    ./l10/couper-capteurs.sh --series 490 --depuis "30 minutes" > /dev/null
    pendant=$(etat_a3)
    # remise en état : réinjection des points supprimés depuis l'agrégat
    # n'est pas possible — on constate, et on documente que la série 490
    # restera « muette » : la remise en état réelle passe par le retour
    # du flux (ici : fin du jeu). Choisir une série déjà coupée en L10
    # aurait masqué le déclenchement.
    echo "A3 · flux muets : avant=$avant pendant=$pendant (attendu : pendant > avant)"
    ;;
  A4)
    "${PSQL[@]}" -c "
      SELECT round(100.0 * pg_database_size(current_database())
                   / (1024.0*1024*1024*200), 1)
             || ' % d''un volume de 200 Go (déclenche si > 85 %)';"
    # la tendance se lit dans l'historique tenu en base par le job de
    # relevé (l15/supervision-taille.sql) : Grafana n'archive rien
    "${PSQL[@]}" -c "
      SELECT 'A4 · ' || count(*) || ' relevé(s) sur 24 h, dernier : '
             || pg_size_pretty(max(octets)) || ', pente : '
             || coalesce(round(regr_slope(octets, extract(epoch FROM ts)) * 86400 / 1024^2)::text
                         || ' Mo/jour', 'NULL (moins de 2 relevés)')
      FROM   supervision_taille WHERE ts >= now() - interval '24 hours';"
    "${PSQL[@]}" -c "
      SELECT 'A4 · jours restants au rythme des 24 h : '
             || coalesce(round(((200.0*1024^3) - o.octets) / nullif(t.pente, 0))::text,
                         'indéterminé (pente nulle ou NULL)')
             || ' (déclenche si entre 0 et 7)'
      FROM (SELECT octets FROM supervision_taille ORDER BY ts DESC LIMIT 1) o,
           (SELECT regr_slope(octets, extract(epoch FROM ts)) * 86400 AS pente
            FROM supervision_taille WHERE ts >= now() - interval '24 hours') t;"
    echo "A4 · provocation réelle = remplissage disque, PROSCRITE sur un poste"
    echo "partagé — vérification par l'expression (seuil ET tendance), documentée."
    ;;
  *) echo "usage: $0 --alerte A1|A2|A3|A4" >&2; exit 2;;
esac
