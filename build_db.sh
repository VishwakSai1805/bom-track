#!/usr/bin/env bash
# Rebuild BOM-Track from scratch: schema, views, PL/pgSQL, real BOM import, real price quotes.
set -euo pipefail
cd "$(dirname "$0")"
PSQL="psql -h ${PGHOST:-/tmp} -U ${PGUSER:-postgres} -v ON_ERROR_STOP=1 -q"
$PSQL -d postgres -c "DROP DATABASE IF EXISTS bomtrack WITH (FORCE)" -c "CREATE DATABASE bomtrack"
for f in sql/01_schema.sql sql/02_views.sql sql/03_plpgsql.sql sql/03b_trg_build_complete.sql sql/06_indexes.sql; do $PSQL -d bomtrack -f "$f"; done
python3 tools/import_boms.py data
python3 tools/load_quotes.py data
