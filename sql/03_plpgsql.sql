-- Functions, procedures, cursor and triggers

-- F1: stock on hand for one part
CREATE OR REPLACE FUNCTION fn_stock_on_hand(p_part INT) RETURNS INT
LANGUAGE plpgsql STABLE AS $$
DECLARE v INT;
BEGIN
    SELECT on_hand INTO v FROM v_stock_on_hand WHERE part_id = p_part;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'part % does not exist', p_part;
    END IF;
    RETURN v;
END $$;

-- F2: cost of one board in a currency (only priced lines are counted)
CREATE OR REPLACE FUNCTION fn_board_cost(p_board INT, p_currency CHAR(3) DEFAULT 'INR') RETURNS NUMERIC
LANGUAGE plpgsql STABLE AS $$
DECLARE v NUMERIC;
BEGIN
    SELECT COALESCE(SUM(bb.qty * lq.unit_price), 0) INTO v
    FROM v_board_bom bb JOIN v_latest_quote lq ON lq.part_id = bb.part_id AND lq.currency = p_currency
    WHERE bb.board_id = p_board;
    RETURN ROUND(v, 2);
END $$;

-- P1: record a purchase. The price paid is also stored as a quote, so price lives in one table only.
CREATE OR REPLACE PROCEDURE sp_record_purchase(p_part INT, p_supplier INT, p_qty INT,
                                               p_unit_price NUMERIC DEFAULT NULL, p_currency CHAR(3) DEFAULT 'INR')
LANGUAGE plpgsql AS $$
BEGIN
    IF p_qty <= 0 THEN
        RAISE EXCEPTION 'purchase quantity must be positive, got %', p_qty;
    END IF;
    INSERT INTO stock_movement(part_id, supplier_id, qty_delta, movement_type)
    VALUES (p_part, p_supplier, p_qty, 'PURCHASE');
    IF p_unit_price IS NOT NULL THEN
        INSERT INTO price_quote(part_id, supplier_id, unit_price, currency)
        VALUES (p_part, p_supplier, p_unit_price, p_currency);
    END IF;
END $$;

-- P2: complete a build. The stock check itself is done by trigger trg_build_complete.
CREATE OR REPLACE PROCEDURE sp_complete_build(p_build INT)
LANGUAGE plpgsql AS $$
DECLARE v_done DATE;
BEGIN
    SELECT completed_on INTO v_done FROM build WHERE build_id = p_build;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'build % does not exist', p_build;
    ELSIF v_done IS NOT NULL THEN
        RAISE EXCEPTION 'build % was already completed on %', p_build, v_done;
    END IF;
    UPDATE build SET completed_on = CURRENT_DATE WHERE build_id = p_build;
END $$;

-- P3 (cursor): walk the shortfall of a build part by part, pick the cheapest latest quote,
-- print a shopping list and return its total.
CREATE OR REPLACE PROCEDURE sp_shopping_list(p_build INT, p_currency CHAR(3), INOUT p_total NUMERIC DEFAULT 0,
                                             INOUT p_unpriced INT DEFAULT 0)
LANGUAGE plpgsql AS $$
DECLARE
    cur_short CURSOR FOR
        SELECT sf.part_id, sf.category, sf.value_text, sf.shortfall
        FROM v_build_shortfall sf
        WHERE sf.build_id = p_build AND sf.shortfall > 0
        ORDER BY sf.category, sf.value_text;
    r         RECORD;
    v_price   NUMERIC;
    v_sup     TEXT;
BEGIN
    p_total := 0; p_unpriced := 0;
    OPEN cur_short;
    LOOP
        FETCH cur_short INTO r;
        EXIT WHEN NOT FOUND;
        SELECT lq.unit_price, lq.supplier INTO v_price, v_sup
        FROM v_latest_quote lq WHERE lq.part_id = r.part_id AND lq.currency = p_currency;
        IF FOUND THEN
            p_total := p_total + v_price * r.shortfall;
            RAISE NOTICE '% x % % from % @ % = %', r.shortfall, r.category, r.value_text, v_sup, v_price, v_price * r.shortfall;
        ELSE
            p_unpriced := p_unpriced + 1;
            RAISE NOTICE '% x % % : no % quote', r.shortfall, r.category, r.value_text, p_currency;
        END IF;
    END LOOP;
    CLOSE cur_short;
    p_total := ROUND(p_total, 2);
END $$;

-- T1: a negative adjustment may not take stock below zero
CREATE OR REPLACE FUNCTION trg_fn_stock_guard() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE v_on_hand INT;
BEGIN
    IF NEW.qty_delta < 0 THEN
        PERFORM 1 FROM part WHERE part_id = NEW.part_id FOR UPDATE;   -- serialize stock changes per part
        v_on_hand := fn_stock_on_hand(NEW.part_id);
        IF v_on_hand + NEW.qty_delta < 0 THEN
            RAISE EXCEPTION 'stock for part % would go negative (on hand %, change %)',
                            NEW.part_id, v_on_hand, NEW.qty_delta;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_stock_guard BEFORE INSERT ON stock_movement
FOR EACH ROW EXECUTE FUNCTION trg_fn_stock_guard();

-- T3: once a board has a completed build its placement list is frozen,
-- because past consumption is computed from it. Changes need a new revision.
CREATE OR REPLACE FUNCTION trg_fn_freeze_bom() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE v_board INT := COALESCE(NEW.board_id, OLD.board_id);
BEGIN
    IF EXISTS (SELECT 1 FROM build WHERE board_id = v_board AND completed_on IS NOT NULL) THEN
        RAISE EXCEPTION 'board % has completed builds; create a new revision instead of editing its BOM', v_board;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
CREATE TRIGGER trg_freeze_bom BEFORE INSERT OR UPDATE OR DELETE ON placement
FOR EACH ROW EXECUTE FUNCTION trg_fn_freeze_bom();
