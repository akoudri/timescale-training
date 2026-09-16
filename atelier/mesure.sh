#!/bin/bash
# Harnais de mesure MISTRAL : cinq exécutions, médiane, écart-type.
#
#   ./mesure.sh requetes/R2-fenetre-3j.sql [--table mesures_7j] [--role r]
#
# Règles (bloc 2.2) : médiane sur 5 exécutions ; une mesure dont
# l'écart-type dépasse 20 % de la médiane est à relancer, pas à reporter.
# Les bornes :debut / :fin sont calculées à partir du jeu, jamais en dur :
# ici, l'intersection commune aux deux états du fil rouge — les jours 1 à 5
# de la fenêtre — pour que les rapports avant/après restent comparables.
set -euo pipefail

FICHIER="$1"; shift || true
TABLE="mesures"; ROLE=""; DB="mistral"; BORNES="reference"
while [ $# -gt 0 ]; do
  case "$1" in
    --table)  TABLE="$2"; shift 2;;
    --role)   ROLE="$2"; shift 2;;
    --db)     DB="$2"; shift 2;;
    --bornes) BORNES="$2"; shift 2;;   # reference (j1-j5) | complet (fenêtre entière)
    *) echo "option inconnue: $1" >&2; exit 2;;
  esac
done

PSQL=(docker compose exec -T timescaledb psql -U postgres -d "$DB" -q -v ON_ERROR_STOP=1)

# bornes stables : jours 1-5 de la fenêtre (données identiques avant/après)

# le site est positionné aussi pour le calcul des bornes : les vues
# cloisonnées de M14 en dépendent (sans effet sur les tables ordinaires)
if [ "$BORNES" = "complet" ]; then
  IFS='|' read -r DEBUT FIN FEN3 <<<"$("${PSQL[@]}" -At -c \
    "SET mistral.site = 2; SELECT min(ts), max(ts) + interval '10 seconds', max(ts) - interval '3 days' FROM ${TABLE};" | tail -1)"
else
  IFS='|' read -r DEBUT FIN FEN3 <<<"$("${PSQL[@]}" -At -c \
    "SET mistral.site = 2; SELECT min(ts), min(ts) + interval '5 days', min(ts) + interval '2 days' FROM ${TABLE};" | tail -1)"
fi
SERIE_VENT=$("${PSQL[@]}" -At -c "
  SELECT coalesce(min(af.series_id), 3) FROM affectation_capteur af
  JOIN signaux g ON g.signal_id = af.signal_id
  WHERE g.libelle = 'vitesse_vent_ms';" 2>/dev/null || echo 3)

SQL=$(sed "s/{{table}}/${TABLE}/g" "$FICHIER")
PRELUDE=""
[ -n "$ROLE" ] && PRELUDE="SET ROLE ${ROLE}; SET mistral.site = 2;"

durees=()
for i in 1 2 3 4 5; do
  t0=$(date +%s%N)
  printf '%s' "$PRELUDE $SQL" | "${PSQL[@]}" \
      -v debut="$DEBUT" -v fin="$FIN" -v fen3="$FEN3" -v serie_vent="$SERIE_VENT" > /dev/null
  t1=$(date +%s%N)
  durees+=($(( (t1 - t0) / 1000000 )))
done

IFS=$'\n' tri=($(sort -n <<<"${durees[*]// /$'\n'}")); unset IFS
mediane=${tri[2]}
somme=0; for d in "${durees[@]}"; do somme=$((somme + d)); done
moy=$((somme / 5))
var=0; for d in "${durees[@]}"; do var=$(( var + (d - moy) * (d - moy) )); done
ecart=$(awk "BEGIN{printf \"%.0f\", sqrt($var/5)}")
pct=$(awk "BEGIN{printf \"%.1f\", ($mediane>0)? 100*$ecart/$mediane : 0}")

echo "fichier=${FICHIER} table=${TABLE} runs=${durees[*]} ms | mediane=${mediane} ms ecart-type=${ecart} ms (${pct}%)"
