-- BOM-Track: tables and constraints (PostgreSQL 16)



CREATE TABLE category (
    category_id  SERIAL       PRIMARY KEY,
    name         VARCHAR(40)  NOT NULL UNIQUE
);

CREATE TABLE part (
    part_id      SERIAL        PRIMARY KEY,
    category_id  INT           NOT NULL REFERENCES category(category_id),
    value_text   VARCHAR(160)  NOT NULL,
    footprint    VARCHAR(160)  NOT NULL DEFAULT '',
    description  VARCHAR(200),
    CONSTRAINT uq_part UNIQUE (category_id, value_text, footprint)
);

CREATE TABLE board (
    board_id     SERIAL        PRIMARY KEY,
    name         VARCHAR(60)   NOT NULL,
    revision     VARCHAR(30)   NOT NULL,
    source       VARCHAR(200),
    created_on   DATE          NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT uq_board UNIQUE (name, revision)
);

CREATE TABLE placement (
    placement_id   SERIAL       PRIMARY KEY,
    board_id       INT          NOT NULL REFERENCES board(board_id) ON DELETE CASCADE,
    part_id        INT          NOT NULL REFERENCES part(part_id),
    ref_designator VARCHAR(20)  NOT NULL,
    label          VARCHAR(40),
    CONSTRAINT uq_placement UNIQUE (board_id, ref_designator)
);

CREATE TABLE supplier (
    supplier_id  SERIAL        PRIMARY KEY,
    name         VARCHAR(60)   NOT NULL UNIQUE,
    website      VARCHAR(120)
);

CREATE TABLE price_quote (
    quote_id     SERIAL         PRIMARY KEY,
    part_id      INT            NOT NULL REFERENCES part(part_id),
    supplier_id  INT            NOT NULL REFERENCES supplier(supplier_id),
    unit_price   NUMERIC(10,4)  NOT NULL CHECK (unit_price > 0),
    currency     CHAR(3)        NOT NULL DEFAULT 'INR',
    captured_at  TIMESTAMP      NOT NULL DEFAULT now()
);

CREATE TABLE build (
    build_id     SERIAL  PRIMARY KEY,
    board_id     INT     NOT NULL REFERENCES board(board_id),
    units        INT     NOT NULL DEFAULT 1 CHECK (units > 0),
    started_on   DATE    NOT NULL DEFAULT CURRENT_DATE,
    completed_on DATE,
    CONSTRAINT ck_build_dates CHECK (completed_on IS NULL OR completed_on >= started_on)
);

CREATE TABLE stock_movement (
    movement_id   SERIAL       PRIMARY KEY,
    part_id       INT          NOT NULL REFERENCES part(part_id),
    supplier_id   INT          REFERENCES supplier(supplier_id),
    qty_delta     INT          NOT NULL CHECK (qty_delta <> 0),
    movement_type VARCHAR(10)  NOT NULL CHECK (movement_type IN ('PURCHASE','ADJUSTMENT')),
    moved_at      TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT ck_purchase CHECK (movement_type <> 'PURCHASE' OR (qty_delta > 0 AND supplier_id IS NOT NULL))
);
