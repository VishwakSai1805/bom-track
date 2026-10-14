-- Derived facts. Nothing below is stored; every value is computed on read.

-- Quantity of each part on each board (replaces the Qty column of a KiCad BOM)
CREATE VIEW v_board_bom AS
SELECT b.board_id, b.name AS board, b.revision, p.part_id, c.name AS category,
       p.value_text, p.footprint, COUNT(*) AS qty,
       STRING_AGG(pl.ref_designator, ',' ORDER BY pl.ref_designator) AS refs
FROM placement pl
JOIN board b    ON b.board_id = pl.board_id
JOIN part p     ON p.part_id = pl.part_id
JOIN category c ON c.category_id = p.category_id
GROUP BY b.board_id, b.name, b.revision, p.part_id, c.name, p.value_text, p.footprint;

-- Parts consumed by completed builds: units x placements of that board
CREATE VIEW v_part_consumed AS
SELECT pl.part_id, SUM(bu.units)::INT AS consumed
FROM build bu
JOIN placement pl ON pl.board_id = bu.board_id
WHERE bu.completed_on IS NOT NULL
GROUP BY pl.part_id;

-- Stock on hand = movements in/out minus consumption by completed builds
CREATE VIEW v_stock_on_hand AS
SELECT p.part_id, c.name AS category, p.value_text, p.footprint,
       COALESCE(m.moved, 0) AS moved_in,
       COALESCE(u.consumed, 0) AS consumed,
       COALESCE(m.moved, 0) - COALESCE(u.consumed, 0) AS on_hand
FROM part p
JOIN category c ON c.category_id = p.category_id
LEFT JOIN (SELECT part_id, SUM(qty_delta)::INT AS moved FROM stock_movement GROUP BY part_id) m ON m.part_id = p.part_id
LEFT JOIN v_part_consumed u ON u.part_id = p.part_id;

-- Latest quote per part and currency
CREATE VIEW v_latest_quote AS
SELECT DISTINCT ON (q.part_id, q.currency)
       q.part_id, q.currency, q.unit_price, q.captured_at, s.name AS supplier
FROM price_quote q JOIN supplier s ON s.supplier_id = q.supplier_id
ORDER BY q.part_id, q.currency, q.captured_at DESC, q.unit_price;

-- Board cost per currency, with how much of the BOM is actually priced
CREATE VIEW v_board_cost AS
SELECT bb.board_id, bb.board, bb.revision, lq.currency,
       SUM(bb.qty * lq.unit_price)::NUMERIC(12,2) AS priced_cost,
       COUNT(*) AS priced_lines,
       (SELECT COUNT(*) FROM v_board_bom x WHERE x.board_id = bb.board_id) AS total_lines
FROM v_board_bom bb
JOIN v_latest_quote lq ON lq.part_id = bb.part_id
GROUP BY bb.board_id, bb.board, bb.revision, lq.currency;

-- Build status comes only from the dates
CREATE VIEW v_build_status AS
SELECT bu.build_id, b.name AS board, b.revision, bu.units, bu.started_on, bu.completed_on,
       CASE WHEN bu.completed_on IS NULL THEN 'IN PROGRESS' ELSE 'COMPLETED' END AS status
FROM build bu JOIN board b ON b.board_id = bu.board_id;

-- Shortfall of every open build (each build checked against current stock on its own)
CREATE VIEW v_build_shortfall AS
SELECT bu.build_id, bb.part_id, bb.category, bb.value_text, bb.footprint,
       (bb.qty * bu.units)::INT AS needed, s.on_hand,
       GREATEST(bb.qty * bu.units - s.on_hand, 0)::INT AS shortfall
FROM build bu
JOIN v_board_bom bb    ON bb.board_id = bu.board_id
JOIN v_stock_on_hand s ON s.part_id = bb.part_id
WHERE bu.completed_on IS NULL;

-- Ready to build = no part short
CREATE VIEW v_build_readiness AS
SELECT bs.build_id, bs.board, bs.revision, bs.units,
       COUNT(sf.part_id) FILTER (WHERE sf.shortfall > 0) AS parts_short,
       COALESCE(SUM(sf.shortfall), 0)::INT AS units_short,
       (COUNT(sf.part_id) FILTER (WHERE sf.shortfall > 0) = 0) AS ready
FROM v_build_status bs
LEFT JOIN v_build_shortfall sf ON sf.build_id = bs.build_id
WHERE bs.status = 'IN PROGRESS'
GROUP BY bs.build_id, bs.board, bs.revision, bs.units;

-- Parts used on more than one board
CREATE VIEW v_shared_parts AS
SELECT p.part_id, c.name AS category, p.value_text, p.footprint,
       COUNT(DISTINCT pl.board_id) AS boards, COUNT(*) AS placements
FROM placement pl JOIN part p ON p.part_id = pl.part_id JOIN category c ON c.category_id = p.category_id
GROUP BY p.part_id, c.name, p.value_text, p.footprint
HAVING COUNT(DISTINCT pl.board_id) > 1;
