"""BOM-Track front end (Streamlit + psycopg2).
Every action shows the SQL / PL/pgSQL it runs, so each step of
User operation -> SQL -> database -> result can be explained."""
import io, csv, sys, os
import pandas as pd
import psycopg2
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
from bomlib import connect, import_board, rows_for  # noqa: E402

st.set_page_config(page_title="BOM-Track", layout="wide")

@st.cache_resource
def get_conn():
    return connect()

def conn():
    c = get_conn()
    if c.closed:
        st.cache_resource.clear(); c = get_conn()
    return c

def q(sql, params=None):
    c = conn()
    with c.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    c.rollback()  # read-only, end the implicit transaction
    return pd.DataFrame(rows, columns=cols)

def run(sql, params=None, label="SQL executed"):
    """Run one write in its own transaction. Shows the SQL, commits on success, rolls back on error."""
    c = conn(); c.notices.clear()
    try:
        with c:
            with c.cursor() as cur:
                cur.execute(sql, params)
                out = cur.fetchall() if cur.description else None
        return True, out, [n.strip() for n in c.notices]
    except psycopg2.Error as e:
        msg = (e.diag.message_primary or str(e)).strip()
        return False, msg, []

def done(ok, good, out, sql, params=None):
    """Store the result, then rerun so every table on the page is redrawn from the database."""
    st.session_state["flash"] = (ok, good if ok else f"Rejected by the database: {out}", sql.strip(), params)
    st.rerun()

def show_flash():
    if "flash" in st.session_state:
        ok, msg, sql, params = st.session_state.pop("flash")
        if ok: st.success(msg)
        else: st.error(msg)
        with st.expander("SQL executed", expanded=True):
            st.code(sql, language="sql")
            if params: st.caption(f"parameters: {params}")

def opts(sql):
    df = q(sql); return dict(zip(df.iloc[:, 1], df.iloc[:, 0]))

st.sidebar.title("BOM-Track")
st.sidebar.caption("Hardware BOM, stock and build tracker")
page = st.sidebar.radio("Go to", ["Overview", "Boards and BOM", "Import KiCad BOM", "Parts and stock",
                                  "Purchases and quotes", "Builds"])
show_flash()

if page == "Overview":
    st.header("Overview")
    counts = q("""SELECT (SELECT COUNT(*) FROM board) boards, (SELECT COUNT(*) FROM part) parts,
                  (SELECT COUNT(*) FROM placement) placements, (SELECT COUNT(*) FROM price_quote) quotes,
                  (SELECT COUNT(*) FROM build) builds""").iloc[0]
    cols = st.columns(5)
    for c, k in zip(cols, counts.index): c.metric(k.capitalize(), int(counts[k]))
    st.subheader("Board cost from latest quotes (view v_board_cost)")
    st.dataframe(q("SELECT board, revision, currency, priced_cost, priced_lines, total_lines FROM v_board_cost ORDER BY currency, priced_cost DESC"),
                 hide_index=True, use_container_width=True)
    st.subheader("Open builds (view v_build_readiness)")
    st.dataframe(q("SELECT build_id, board, revision, units, parts_short, units_short, ready FROM v_build_readiness ORDER BY build_id"),
                 hide_index=True, use_container_width=True)

elif page == "Boards and BOM":
    st.header("Boards and BOM")
    boards = opts("SELECT board_id, name || ' ' || revision FROM board ORDER BY board_id")
    b = st.selectbox("Board", list(boards.keys()))
    bid = boards[b]
    st.caption(q("SELECT source FROM board WHERE board_id = %s", (bid,)).iloc[0, 0])
    bom = q("SELECT refs, category, value_text, footprint, qty FROM v_board_bom WHERE board_id = %s ORDER BY category, value_text", (bid,))
    st.write(f"{len(bom)} lines, {int(bom.qty.sum()) if len(bom) else 0} components")
    st.dataframe(bom, hide_index=True, use_container_width=True)
    cost = q("SELECT currency, fn_board_cost(%s, currency) AS cost FROM (SELECT DISTINCT currency FROM price_quote) c", (bid,))
    st.write("Cost by currency (function fn_board_cost):")
    st.dataframe(cost, hide_index=True)

elif page == "Import KiCad BOM":
    st.header("Import a KiCad BOM")
    st.write("Upload a KiCad grouped BOM CSV (columns Refs, Value, Footprint, Qty). The whole board is inserted in one transaction.")
    up = st.file_uploader("BOM CSV", type="csv")
    name = st.text_input("Board name"); rev = st.text_input("Revision", "rev 1")
    if st.button("Import", disabled=not (up and name)):
        tmp = os.path.join("/tmp", "upload_bom.csv"); open(tmp, "wb").write(up.getvalue())
        st.code("BEGIN;\nINSERT INTO board(name, revision, source) ...;\n-- for each designator:\n"
                "INSERT INTO category ... (if new); INSERT INTO part ... (if new);\nINSERT INTO placement(board_id, part_id, ref_designator, label) ...;\nCOMMIT;", language="sql")
        try:
            board_id, n, skipped = import_board(conn(), name, rev, f"Uploaded file {up.name}", rows_for("kicad_grouped", tmp))
            st.success(f"Board {board_id} created with {n} placements. Skipped: {skipped or 'none'}")
        except (psycopg2.Error, AssertionError, KeyError) as e:
            conn().rollback(); st.error(f"Import rolled back: {e}")

elif page == "Parts and stock":
    st.header("Parts and stock (view v_stock_on_hand)")
    term = st.text_input("Search value or footprint")
    df = q("""SELECT part_id, category, value_text, footprint, moved_in, consumed, on_hand FROM v_stock_on_hand
              WHERE value_text ILIKE %s OR footprint ILIKE %s ORDER BY category, value_text""", (f"%{term}%", f"%{term}%"))
    only = st.checkbox("Only parts with stock movements")
    if only: df = df[(df.moved_in != 0) | (df.consumed != 0)]
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.subheader("Stock adjustment")
    st.caption("Negative adjustments go through trigger trg_stock_guard, which rejects them if stock would go below zero.")
    c1, c2 = st.columns(2)
    pid = c1.number_input("part_id", min_value=1, step=1); delta = c2.number_input("Change (+/-)", value=-1, step=1)
    if st.button("Record adjustment"):
        sql = "INSERT INTO stock_movement(part_id, qty_delta, movement_type) VALUES (%s, %s, 'ADJUSTMENT') RETURNING movement_id"
        ok, out, _ = run(sql, (int(pid), int(delta)))
        done(ok, f"Movement {out[0][0]} recorded" if ok else "", out, sql, (int(pid), int(delta)))

elif page == "Purchases and quotes":
    st.header("Purchases and quotes")
    sups = opts("SELECT supplier_id, name FROM supplier ORDER BY name")
    st.subheader("Record a purchase (procedure sp_record_purchase)")
    c1, c2, c3, c4 = st.columns(4)
    pid = c1.number_input("part_id", min_value=1, step=1, key="pp")
    sup = c2.selectbox("Supplier", list(sups.keys()))
    qty = c3.number_input("Quantity", min_value=1, value=10, step=1)
    price = c4.number_input("Unit price INR (0 = not known)", min_value=0.0, value=0.0, step=0.5)
    if st.button("Record purchase"):
        sql = "CALL sp_record_purchase(%s, %s, %s, %s, 'INR')"
        prm = (int(pid), sups[sup], int(qty), price if price > 0 else None)
        ok, out, _ = run(sql, prm)
        done(ok, "Purchase recorded", out, sql, prm)
    st.subheader("Latest quote per part (view v_latest_quote)")
    st.dataframe(q("""SELECT lq.part_id, p.value_text, lq.supplier, lq.unit_price, lq.currency, lq.captured_at
                      FROM v_latest_quote lq JOIN part p USING (part_id) ORDER BY lq.currency, p.value_text"""),
                 hide_index=True, use_container_width=True)
    st.subheader("Suppliers")
    st.dataframe(q("""SELECT s.name, s.website, COUNT(q.quote_id) AS quotes FROM supplier s
                      LEFT JOIN price_quote q USING (supplier_id) GROUP BY s.supplier_id ORDER BY quotes DESC, s.name"""),
                 hide_index=True, use_container_width=True)

elif page == "Builds":
    st.header("Builds")
    boards = opts("SELECT board_id, name || ' ' || revision FROM board ORDER BY board_id")
    st.subheader("Plan a build")
    c1, c2 = st.columns([3, 1])
    b = c1.selectbox("Board", list(boards.keys())); units = c2.number_input("Units", min_value=1, value=1)
    if st.button("Plan build"):
        sql = "INSERT INTO build(board_id, units) VALUES (%s, %s) RETURNING build_id"
        ok, out, _ = run(sql, (boards[b], int(units)))
        done(ok, f"Build {out[0][0]} planned" if ok else "", out, sql, (boards[b], int(units)))
    st.subheader("All builds (view v_build_status)")
    st.dataframe(q("SELECT * FROM v_build_status ORDER BY build_id"), hide_index=True, use_container_width=True)
    open_b = q("SELECT build_id, board || ' ' || revision || ' x' || units AS label FROM v_build_readiness ORDER BY build_id")
    if len(open_b):
        sel = st.selectbox("Open build", open_b.label.tolist())
        bid = int(open_b[open_b.label == sel].build_id.iloc[0])
        r = q("SELECT parts_short, units_short, ready FROM v_build_readiness WHERE build_id = %s", (bid,)).iloc[0]
        st.write(f"Parts short: **{r.parts_short}**, units short: **{r.units_short}**, ready: **{r.ready}**")
        short = q("SELECT category, value_text, needed, on_hand, shortfall FROM v_build_shortfall WHERE build_id = %s AND shortfall > 0 ORDER BY category", (bid,))
        st.dataframe(short, hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2)
        if c1.button("Shopping list (cursor)"):
            ok, out, notices = run("CALL sp_shopping_list(%s, 'INR', NULL, NULL)", (bid,))
            with st.expander("SQL executed", expanded=True):
                st.code("CALL sp_shopping_list(%s, 'INR', NULL, NULL)  -- explicit cursor over v_build_shortfall", language="sql")
            if ok:
                st.text("\n".join(n.replace("NOTICE:  ", "") for n in notices))
                st.write(f"Total for priced lines: INR {out[0][0]}; lines with no INR quote: {out[0][1]}")
            else:
                st.error(out)
        if c2.button("Complete build"):
            ok, out, _ = run("CALL sp_complete_build(%s)", (bid,))
            done(ok, f"Build {bid} completed; its parts are now consumed from stock", out, "CALL sp_complete_build(%s)", (bid,))
