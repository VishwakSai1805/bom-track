\echo '=== 1. Size of the real tables'
SELECT relname AS table_name, n_live_tup AS rows, pg_size_pretty(pg_relation_size(relid)) AS heap_size,
       pg_relation_size(relid) / 8192 AS pages
FROM pg_stat_user_tables ORDER BY n_live_tup DESC;

DROP INDEX IF EXISTS idx_placement_part;
ANALYZE;
SELECT part_id AS p100n FROM part WHERE value_text = '100nF' AND footprint = '0603' \gset
\echo '=== 2. Where-used query for 100nF 0603 WITHOUT an index on placement(part_id)'
EXPLAIN (ANALYZE, BUFFERS, COSTS) SELECT board_id, ref_designator FROM placement WHERE part_id = :p100n;

\echo '=== 3. Same query WITH idx_placement_part'
CREATE INDEX idx_placement_part ON placement(part_id);
ANALYZE placement;
EXPLAIN (ANALYZE, BUFFERS, COSTS) SELECT board_id, ref_designator FROM placement WHERE part_id = :p100n;

\echo '=== 4. Forcing the index (enable_seqscan = off) to compare the planner cost estimates'
SET enable_seqscan = off;
EXPLAIN (ANALYZE, BUFFERS, COSTS) SELECT board_id, ref_designator FROM placement WHERE part_id = :p100n;
RESET enable_seqscan;

\echo '=== 5. Lookup by designator uses the index created by UNIQUE(board_id, ref_designator)'
EXPLAIN (ANALYZE, COSTS) SELECT part_id FROM placement WHERE board_id = 1 AND ref_designator = 'U1';

\echo '=== 6. Plan of the shortfall view for one build (join strategy)'
INSERT INTO build(board_id, units) SELECT board_id, 1 FROM board WHERE name = 'ESP32-PoE-ISO' RETURNING build_id \gset
EXPLAIN (ANALYZE, COSTS, SUMMARY) SELECT * FROM v_build_shortfall WHERE build_id = :build_id;
DELETE FROM build WHERE build_id = :build_id;
