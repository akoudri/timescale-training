#!/bin/bash
# L03 étape 3 — les neuf mesures : trois profils sur trois intervalles de chunk.
set -euo pipefail
cd "$(dirname "$0")"
for t in 1j 7j 30j; do
  for r in R1-dernier-point R2-fenetre-3j R3-agregation-fenetre; do
    ./mesure.sh requetes/$r.sql --table mesures_$t
  done
done
