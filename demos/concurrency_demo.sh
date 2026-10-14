#!/usr/bin/env bash
# Two sessions complete two uGameBox builds at the same time, with stock for only ONE board.
# Run 1: build trigger WITHOUT row locks  -> both succeed, stock goes negative (lost update / write skew).
# Run 2: the real trigger (SELECT ... FOR UPDATE on the parts) -> second session waits, then is rejected.
cd "$(dirname "$0")/.."
Q="psql -h ${PGHOST:-/tmp} -U postgres -d bomtrack -X -q -v ON_ERROR_STOP=0"
setup() {
$Q <<'SQL'
TRUNCATE build, stock_movement RESTART IDENTITY;
INSERT INTO build(board_id, units) SELECT board_id, 1 FROM board WHERE name = 'uGameBox';   -- build 1
INSERT INTO build(board_id, units) SELECT board_id, 1 FROM board WHERE name = 'uGameBox';   -- build 2
DO $$ DECLARE r RECORD; s INT := (SELECT supplier_id FROM supplier WHERE name = 'Probots');
BEGIN FOR r IN SELECT part_id, needed FROM v_build_shortfall WHERE build_id = 1 LOOP
        CALL sp_record_purchase(r.part_id, s, r.needed); END LOOP; END $$;   -- stock for exactly ONE board
SQL
}
session() {   # $1 = build id, $2 = name
$Q <<SQL 2>&1 | sed "s/^/[$2] /"
SET bomtrack.demo_delay = '3';
SELECT to_char(clock_timestamp(),'HH24:MI:SS.MS') AS t, 'start: complete build $1' AS event;
CALL sp_complete_build($1);
SELECT to_char(clock_timestamp(),'HH24:MI:SS.MS') AS t, 'end' AS event;
SQL
}
report() {
$Q -c "SELECT build_id, status FROM v_build_status ORDER BY build_id" \
   -c "SELECT value_text, moved_in, consumed, on_hand FROM v_stock_on_hand WHERE on_hand < 0 OR value_text IN ('AT89S52','1k') ORDER BY on_hand LIMIT 5"
}
echo "================ RUN 1: trigger without locking (broken version) ================"
$Q <<'SQL'
CREATE OR REPLACE FUNCTION trg_fn_build_complete() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE r RECORD; v_short BOOLEAN;
BEGIN
    IF OLD.completed_on IS NULL AND NEW.completed_on IS NOT NULL THEN
        SELECT * INTO r FROM v_build_shortfall WHERE build_id = NEW.build_id AND shortfall > 0 LIMIT 1;
        v_short := FOUND;
        PERFORM pg_sleep(current_setting('bomtrack.demo_delay', true)::NUMERIC);
        IF v_short THEN RAISE EXCEPTION 'build % cannot be completed: short of % x %', NEW.build_id, r.shortfall, r.value_text; END IF;
    END IF;
    RETURN NEW;
END $$;
SQL
setup
session 1 A & sleep 1; session 2 B & wait
report
echo; echo "================ RUN 2: real trigger with SELECT ... FOR UPDATE ================"
$Q -f sql/03b_trg_build_complete.sql
setup
session 1 A & sleep 1; session 2 B & wait
report
$Q -c "TRUNCATE build, stock_movement RESTART IDENTITY"
