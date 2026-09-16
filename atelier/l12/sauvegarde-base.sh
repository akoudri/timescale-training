#!/bin/bash
# L12 — sauvegarde de base (physique, format plain, WAL inclus en flux).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf archives/base
docker compose exec -T timescaledb pg_basebackup -U postgres \
  -D /archives/base -Fp -Xs -c fast --no-password
echo "sauvegarde de base : $(du -sh archives/base | cut -f1)"
