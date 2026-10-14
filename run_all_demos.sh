#!/usr/bin/env bash
# Rebuild from real data, then run every demo and capture its output into logs/.
set -u
cd "$(dirname "$0")"
Q="psql -h ${PGHOST:-/tmp} -U postgres -d bomtrack -X"
./build_db.sh                                      > logs/build_db.log 2>&1
$Q -c "\dt+" -c "\dv" -c "\df+ fn_*|sp_*|trg_*"    > logs/catalog.log 2>&1
$Q -f sql/04_queries.sql                           > logs/queries_output.log 2>&1
$Q -e -f sql/05_transactions_demo.sql              > logs/transactions_demo.log 2>&1
tools/reset_demo_state.sh
demos/concurrency_demo.sh                          > logs/concurrency_demo.log 2>&1
demos/recovery_demo.sh                             > logs/recovery_demo.log 2>&1
$Q -f demos/indexing_demo.sql                      > logs/indexing_demo.log 2>&1
tools/reset_demo_state.sh
echo "done: $(date -u '+%Y-%m-%d %H:%M UTC')"
