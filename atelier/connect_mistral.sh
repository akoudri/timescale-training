#!/bin/bash
# Ouvre psql sur la base mistral, dans le conteneur, avec /atelier comme
# répertoire courant : les \i l02/... des fiches et les chemins /jeux/...
# des scripts de chargement y sont valables.
set -euo pipefail
cd "$(dirname "$0")"                       # le compose est ici, d'où qu'on appelle
exec docker compose exec -w /atelier timescaledb psql -U postgres -d mistral "$@"
