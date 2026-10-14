\pset footer on
\echo '=== Q1. All boards with their source and number of placed components (JOIN + GROUP BY)'
SELECT b.board_id, b.name, b.revision, COUNT(pl.placement_id) AS components
FROM board b LEFT JOIN placement pl ON pl.board_id = b.board_id
GROUP BY b.board_id ORDER BY b.board_id;

\echo '=== Q2. Full BOM of uGameBox, grouped like a KiCad export (view v_board_bom)'
SELECT refs, category, value_text, qty FROM v_board_bom
WHERE board = 'uGameBox' ORDER BY category, value_text;

\echo '=== Q3. Placements that carry a label different from the part value (uGameBox buttons)'
SELECT pl.ref_designator, pl.label, p.value_text
FROM placement pl JOIN part p ON p.part_id = pl.part_id
WHERE pl.label IS NOT NULL ORDER BY pl.ref_designator;

\echo '=== Q4. Number of distinct parts and placements per category (aggregation)'
SELECT c.name AS category, COUNT(DISTINCT p.part_id) AS distinct_parts, COUNT(pl.placement_id) AS placements
FROM category c JOIN part p ON p.category_id = c.category_id
LEFT JOIN placement pl ON pl.part_id = p.part_id
GROUP BY c.name ORDER BY placements DESC;

\echo '=== Q5. Most reused parts across all boards (v_shared_parts, top 10)'
SELECT category, value_text, footprint, boards, placements
FROM v_shared_parts ORDER BY boards DESC, placements DESC LIMIT 10;

\echo '=== Q6. Values on uGameBox that other boards also use, but in a different package (subquery with IN)'
SELECT c.name AS category, p.value_text AS value_on_ugamebox,
       (SELECT COUNT(DISTINCT pl2.board_id) FROM placement pl2 JOIN part p2 ON p2.part_id = pl2.part_id
        WHERE p2.category_id = p.category_id AND p2.value_text = p.value_text AND p2.part_id <> p.part_id) AS other_boards
FROM part p JOIN category c USING (category_id)
WHERE p.part_id IN (SELECT pl.part_id FROM placement pl JOIN board b USING (board_id) WHERE b.name = 'uGameBox')
  AND EXISTS (SELECT 1 FROM part p2 WHERE p2.category_id = p.category_id AND p2.value_text = p.value_text AND p2.part_id <> p.part_id)
ORDER BY other_boards DESC;

\echo '=== Q7. Parts that are on uGameBox and on no other board (NOT EXISTS)'
SELECT p.value_text, c.name AS category FROM part p JOIN category c USING (category_id)
WHERE EXISTS (SELECT 1 FROM placement pl JOIN board b USING (board_id) WHERE pl.part_id = p.part_id AND b.name = 'uGameBox')
  AND NOT EXISTS (SELECT 1 FROM placement pl JOIN board b USING (board_id) WHERE pl.part_id = p.part_id AND b.name <> 'uGameBox')
ORDER BY 2, 1;

\echo '=== Q8. Boards bigger than the average board (HAVING with a scalar subquery)'
SELECT b.name, b.revision, COUNT(*) AS components FROM board b JOIN placement pl USING (board_id)
GROUP BY b.board_id HAVING COUNT(*) > (SELECT AVG(n) FROM (SELECT COUNT(*) AS n FROM placement GROUP BY board_id) t)
ORDER BY components DESC;

\echo '=== Q9. Board cost from latest quotes, with price coverage (v_board_cost)'
SELECT board, revision, currency, priced_cost, priced_lines || ' of ' || total_lines AS lines_priced
FROM v_board_cost ORDER BY currency, priced_cost DESC;

\echo '=== Q10. Cost of uGameBox through function fn_board_cost'
SELECT fn_board_cost((SELECT board_id FROM board WHERE name = 'uGameBox'), 'INR') AS ugamebox_cost_inr;

\echo '=== Q11. Supplier comparison: number of quotes and average unit price (OUTER JOIN)'
SELECT s.name, COUNT(q.quote_id) AS quotes, ROUND(AVG(q.unit_price), 2) AS avg_price, MIN(q.currency) AS currency
FROM supplier s LEFT JOIN price_quote q ON q.supplier_id = s.supplier_id
GROUP BY s.name ORDER BY quotes DESC, s.name;

\echo '=== Q12. Supplier ranking per part: cheapest quote first (window function RANK)'
SELECT p.value_text, s.name AS supplier, q.unit_price, q.currency,
       RANK() OVER (PARTITION BY q.part_id, q.currency ORDER BY q.unit_price) AS price_rank
FROM price_quote q JOIN part p ON p.part_id = q.part_id JOIN supplier s ON s.supplier_id = q.supplier_id
WHERE q.currency = 'INR'
ORDER BY p.value_text, price_rank;

\echo '=== Q13. Unpriced lines of uGameBox (anti join)'
SELECT bb.refs, bb.category, bb.value_text FROM v_board_bom bb
LEFT JOIN v_latest_quote lq ON lq.part_id = bb.part_id
WHERE bb.board = 'uGameBox' AND lq.part_id IS NULL ORDER BY bb.category;

\echo '=== Q14. Capacitor values used on the Ubertooth family, by package (string functions + CASE)'
SELECT p.footprint AS package, COUNT(DISTINCT p.value_text) AS distinct_values,
       CASE WHEN COUNT(*) > 50 THEN 'heavy' WHEN COUNT(*) > 10 THEN 'medium' ELSE 'light' END AS usage
FROM placement pl JOIN part p USING (part_id) JOIN category c USING (category_id) JOIN board b USING (board_id)
WHERE c.name = 'Capacitor' AND b.source LIKE '%ubertooth%'
GROUP BY p.footprint ORDER BY COUNT(*) DESC;

\echo '=== Q15. Pairs of boards that share the most parts (self join)'
SELECT a.name || ' ' || a.revision AS board_a, b.name || ' ' || b.revision AS board_b, COUNT(*) AS common_parts
FROM (SELECT DISTINCT board_id, part_id FROM placement) x
JOIN (SELECT DISTINCT board_id, part_id FROM placement) y ON y.part_id = x.part_id AND x.board_id < y.board_id
JOIN board a ON a.board_id = x.board_id JOIN board b ON b.board_id = y.board_id
GROUP BY a.name, a.revision, b.name, b.revision ORDER BY common_parts DESC LIMIT 8;

\echo '=== Q16. Where-used: every board and designator that uses a 100nF 0402 capacitor (correlated lookup)'
SELECT b.name, b.revision, STRING_AGG(pl.ref_designator, ',' ORDER BY pl.ref_designator) AS refs
FROM placement pl JOIN board b USING (board_id) JOIN part p USING (part_id)
WHERE p.value_text IN ('100nF','100n','0.1uF','100n 50V') AND p.footprint ILIKE '%0402%'
GROUP BY b.name, b.revision ORDER BY b.name;

\echo '=== Q17. Number of placements per designator prefix (regular expressions)'
SELECT SUBSTRING(ref_designator FROM '^[A-Za-z_-]+') AS prefix, COUNT(*) AS n
FROM placement GROUP BY 1 HAVING COUNT(*) >= 5 ORDER BY n DESC;
