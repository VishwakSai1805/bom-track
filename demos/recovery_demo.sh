#!/usr/bin/env bash
# Crash recovery: one transaction commits, a second is still open when the server is killed
# with an immediate shutdown (no checkpoint). After restart, WAL redo restores the committed
# change and the uncommitted one is gone.
cd "$(dirname "$0")/.."
PGDATA=${PGDATA:-/srv/pgdata}; BIN=/usr/lib/postgresql/16/bin
Q="psql -h ${PGHOST:-/tmp} -U postgres -d bomtrack -X"
$Q -q -c "TRUNCATE build, stock_movement RESTART IDENTITY"
echo "--- 1. Committed transaction: buy 5 x BC547"
$Q <<'SQL'
BEGIN;
DO $$ DECLARE v_part INT := (SELECT part_id FROM part WHERE value_text = 'BC547');
             v_sup  INT := (SELECT supplier_id FROM supplier WHERE name = 'Probots');
BEGIN CALL sp_record_purchase(v_part, v_sup, 5); END $$;
COMMIT;
SQL
echo "--- 2. Open transaction (never committed): buy 7 x L7805, then the server is killed"
( $Q <<'SQL'
BEGIN;
INSERT INTO stock_movement(part_id, supplier_id, qty_delta, movement_type)
SELECT part_id, (SELECT supplier_id FROM supplier WHERE name='Probots'), 7, 'PURCHASE' FROM part WHERE value_text = 'L7805';
SELECT 'inside open transaction' AS note, COUNT(*) AS rows_visible_here FROM stock_movement;
SELECT pg_sleep(10);
COMMIT;
SQL
) > /tmp/open_tx.out 2>&1 &
sleep 2
$Q -c "SELECT 'from another session' AS note, COUNT(*) AS rows_visible FROM stock_movement"
echo "--- 3. Kill the server: pg_ctl stop -m immediate (like a power cut, no checkpoint)"
su postgres -c "$BIN/pg_ctl -D $PGDATA stop -m immediate"
wait; echo "[open session output]"; cat /tmp/open_tx.out
echo "--- 4. Restart"
LOGPOS=$(wc -l < $PGDATA/server.log)
su postgres -c "$BIN/pg_ctl -D $PGDATA -l $PGDATA/server.log -o '-p 5432 -k /tmp' start" ; sleep 3
echo "[server log during startup]"; tail -n +$((LOGPOS+1)) $PGDATA/server.log | grep -E "interrupted|redo|ready to accept|not properly shut down|automatic recovery" | sed 's/^[0-9-]* [0-9:.]* UTC \[[0-9]*\] //'
echo "--- 5. What survived"
$Q -c "SELECT p.value_text, m.qty_delta, m.movement_type FROM stock_movement m JOIN part p USING (part_id) ORDER BY movement_id"
$Q -q -c "TRUNCATE build, stock_movement RESTART IDENTITY"
