-- T2: a build can only be completed if every part is in stock
CREATE OR REPLACE FUNCTION trg_fn_build_complete() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE r RECORD; v_short BOOLEAN;
BEGIN
    IF OLD.completed_on IS NULL AND NEW.completed_on IS NOT NULL THEN
        -- lock the parts of this board so two builds cannot use the same stock at once
        PERFORM 1 FROM part WHERE part_id IN (SELECT part_id FROM placement WHERE board_id = NEW.board_id)
        ORDER BY part_id FOR UPDATE;
        SELECT * INTO r FROM v_build_shortfall WHERE build_id = NEW.build_id AND shortfall > 0
        ORDER BY shortfall DESC LIMIT 1;
        v_short := FOUND;
        -- optional delay, only set by the concurrency demo, to widen the timing window
        IF current_setting('bomtrack.demo_delay', true) IS NOT NULL AND current_setting('bomtrack.demo_delay', true) <> '' THEN
            PERFORM pg_sleep(current_setting('bomtrack.demo_delay', true)::NUMERIC);
        END IF;
        IF v_short THEN
            RAISE EXCEPTION 'build % cannot be completed: short of % x % % (and possibly more)',
                            NEW.build_id, r.shortfall, r.category, r.value_text;
        END IF;
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_build_complete ON build;
CREATE TRIGGER trg_build_complete BEFORE UPDATE OF completed_on ON build
FOR EACH ROW EXECUTE FUNCTION trg_fn_build_complete();

