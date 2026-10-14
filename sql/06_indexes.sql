-- Foreign keys are not indexed automatically in PostgreSQL. These support the joins used by the views.
CREATE INDEX IF NOT EXISTS idx_placement_part   ON placement(part_id);
CREATE INDEX IF NOT EXISTS idx_quote_part       ON price_quote(part_id, currency, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_movement_part    ON stock_movement(part_id);
CREATE INDEX IF NOT EXISTS idx_build_board      ON build(board_id);
