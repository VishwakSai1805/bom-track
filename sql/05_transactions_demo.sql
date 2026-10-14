-- Review III transaction demo. These are DEMONSTRATION operations run against the real data set:
-- the purchases below were NOT real purchases. Reset with sql/99_reset_demo.sql.
\set VERBOSITY terse
SELECT supplier_id AS probots FROM supplier WHERE name = 'Probots' \gset
SELECT supplier_id AS robu FROM supplier WHERE name = 'Robu.in' \gset
SELECT pl.part_id AS led, (SELECT part_id FROM placement WHERE board_id = 1 AND ref_designator = 'R1') AS res1k
FROM placement pl WHERE pl.board_id = 1 AND pl.ref_designator = 'D1' \gset
\echo '##### T1. Plan a build of 1 uGameBox (INSERT into build)'
INSERT INTO build(board_id, units) SELECT board_id, 1 FROM board WHERE name = 'uGameBox' RETURNING build_id, units, started_on;
SELECT * FROM v_build_readiness;

\echo '##### T2. Try to complete it with no stock (procedure sp_complete_build -> trigger trg_build_complete)'
CALL sp_complete_build(1);
SELECT * FROM v_build_status;

\echo '##### T3. Shopping list for the build (procedure sp_shopping_list with an explicit CURSOR)'
CALL sp_shopping_list(1, 'INR', NULL, NULL);

\echo '##### T4. Buy exactly the shortfall in one transaction (DEMO purchases via sp_record_purchase)'
BEGIN;
DO $$
DECLARE r RECORD; v_sup INT := (SELECT supplier_id FROM supplier WHERE name = 'Probots');
BEGIN
    FOR r IN SELECT part_id, shortfall FROM v_build_shortfall WHERE build_id = 1 AND shortfall > 0 LOOP
        CALL sp_record_purchase(r.part_id, v_sup, r.shortfall);
    END LOOP;
END $$;
COMMIT;
SELECT movement_type, COUNT(*) AS movements, SUM(qty_delta) AS parts_in FROM stock_movement GROUP BY movement_type;
SELECT * FROM v_build_readiness;

\echo '##### T5. Complete the build now (trigger passes; stock is consumed through v_part_consumed)'
CALL sp_complete_build(1);
SELECT * FROM v_build_status;
SELECT category, value_text, moved_in, consumed, on_hand FROM v_stock_on_hand
WHERE part_id IN (SELECT part_id FROM placement WHERE board_id = 1) ORDER BY category LIMIT 6;

\echo '##### T6. Record 1 damaged LED as a negative adjustment (trigger trg_stock_guard rejects: on hand is 0)'
INSERT INTO stock_movement(part_id, qty_delta, movement_type)
SELECT part_id, -1, 'ADJUSTMENT' FROM placement WHERE board_id = 1 AND ref_designator = 'D1';

\echo '##### T7. Buy 10 spare LEDs, then the same adjustment succeeds (function fn_stock_on_hand)'
CALL sp_record_purchase(:led, :robu, 10);
INSERT INTO stock_movement(part_id, qty_delta, movement_type)
SELECT part_id, -1, 'ADJUSTMENT' FROM placement WHERE board_id = 1 AND ref_designator = 'D1';
SELECT fn_stock_on_hand(:led) AS led_on_hand;

\echo '##### T8. Try to change the BOM of a board that has been built (trigger trg_freeze_bom rejects)'
DELETE FROM placement WHERE board_id = 1 AND ref_designator = 'R11';
UPDATE placement SET label = 'FIRE' WHERE board_id = 1 AND ref_designator = 'SW1';

\echo '##### T9. UPDATE that is allowed: add a description to a part'
UPDATE part SET description = '8051 MCU, 8 KB flash, DIP-40' WHERE value_text = 'AT89S52' RETURNING part_id, value_text, description;

\echo '##### T10. DELETE: a planned build can be removed; a supplier with history cannot (FK)'
INSERT INTO build(board_id, units) SELECT board_id, 2 FROM board WHERE name = 'OtterPill' AND revision = 'v1.4' RETURNING build_id;
DELETE FROM build WHERE completed_on IS NULL AND board_id = (SELECT board_id FROM board WHERE name = 'OtterPill' AND revision = 'v1.4') RETURNING build_id;
DELETE FROM supplier WHERE name = 'Probots';

\echo '##### T11. Atomicity with SAVEPOINT: a bad step is undone, the good step is kept'
BEGIN;
CALL sp_record_purchase(:res1k, :robu, 20);
SAVEPOINT before_bad;
INSERT INTO price_quote(part_id, supplier_id, unit_price) SELECT part_id, 1, -5 FROM placement WHERE board_id = 1 AND ref_designator = 'R1';
ROLLBACK TO SAVEPOINT before_bad;
COMMIT;
SELECT value_text, moved_in, consumed, on_hand FROM v_stock_on_hand
WHERE part_id = (SELECT part_id FROM placement WHERE board_id = 1 AND ref_designator = 'R1');

\echo '##### T12. Plan one build of every other board in a single INSERT ... SELECT, then check readiness for all'
INSERT INTO build(board_id, units, started_on)
SELECT board_id, 1, CURRENT_DATE FROM board WHERE name <> 'uGameBox';
SELECT build_id, board, revision, units, parts_short, units_short, ready FROM v_build_readiness ORDER BY build_id;

\echo '##### Final row counts'
SELECT 'build' t, COUNT(*) FROM build UNION ALL SELECT 'stock_movement', COUNT(*) FROM stock_movement;
