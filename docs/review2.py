import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from logparse import *
B = os.path.dirname(os.path.abspath(__file__)) + "/.."
L = B + "/logs/"
d = new_doc("BOM-Track: Review II", "Database Implementation")
cover(d, "Review II: Database Implementation", "BOM-Track",
      "A Database for Hardware Bills of Materials, Part Stock and Board Builds",
      [("Implementation", "PostgreSQL 16 (SQL, PL/pgSQL), Python 3")])
header_footer(d, "BOM-Track | BCSE302L Course Project | Review II")

d.add_heading("Contents", 1)
for x in ["1. Implementation Overview", "2. Table Creation and Constraints (DDL)", "3. Data Population (DML)",
          "4. SQL Queries and Outputs", "5. Views", "6. Functions and Procedures", "7. Cursor", "8. Triggers", "9. Indexes"]:
    para(d, x, after=2)

d.add_heading("1. Implementation Overview", 1)
para(d, "BOM-Track is implemented on PostgreSQL 16. The procedural parts are written in PL/pgSQL, which is "
     "PostgreSQL's equivalent of Oracle PL/SQL (the same ideas: stored functions, procedures, explicit cursors, "
     "exception handling and row-level triggers). A Python front end (Streamlit with the psycopg2 driver) is used "
     "for Review III. Every output in this document was produced by running the scripts listed below; nothing was typed by hand.", align="j")
table(d, ["File", "Contents"], [
    ["sql/01_schema.sql", "CREATE TABLE statements with all keys and constraints"],
    ["sql/02_views.sql", "9 views that compute every derived value"],
    ["sql/03_plpgsql.sql, 03b_...", "2 functions, 3 procedures (one with a cursor), 3 triggers"],
    ["sql/04_queries.sql", "17 queries; output in logs/queries_output.log"],
    ["sql/06_indexes.sql", "Indexes on foreign-key columns"],
    ["tools/extract_kicad.py", "Reads KiCad schematics (.sch and .kicad_sch) into a flat BOM"],
    ["tools/import_boms.py, bomlib.py", "Loads BOM files into the database, one transaction per board"],
    ["tools/load_quotes.py", "Loads real supplier prices"],
    ["build_db.sh / build_db.bat", "Rebuilds the whole database from the raw files"],
], [2.3, 4.0], size=10, mono_cols=(0,))

d.add_heading("1.1 Data Sources", 2)
para(d, "All rows in the core tables come from real files. My own board is uGameBox (an AT89S52 handheld game). "
     "To get a realistic parts catalogue with parts shared between boards, I also loaded ten published open-hardware "
     "designs from GitHub. Their schematics were parsed directly, one row per reference designator.", align="j")
table(d, ["Board", "Source", "Placed", "Skipped"], [
    ["uGameBox rev 1", "My KiCad BOM export (28 grouped lines)", "49", "0"],
    ["Ubertooth One, Artichoke, Broccoli, Celery, Endive, Pogoprog, TC13 Badge", "github.com/greatscottgadgets/ubertooth (KiCad 4 schematics)", "431", "41"],
    ["OtterPill v1.3, v1.4", "github.com/Jana-Marie/OtterPill", "82", "4"],
    ["ESP32-PoE-ISO Rev N", "github.com/OLIMEX/ESP32-POE-ISO (KiCad 7 schematic)", "116", "22"],
], [2.4, 2.5, 0.7, 0.7], size=9.5)
para(d, "Skipped designators are mounting holes, fiducials, test pads and parts marked as not fitted (DNP, NS, NA). "
     "Nobody buys these, so they are not part of a bill of materials.", align="j")
para(d, "Checking the extraction: OLIMEX publishes its own BOM for Rev N. My extraction gives the same 138 designators, with "
     "none missing and none extra. For OtterPill v1.3, the published factory BOM lists 37 designators and mine has 43. The 6 extra "
     "are the pin headers J2 to J7, which the factory BOM leaves out because they are soldered by hand.", align="j")
para(d, "Prices come from two real sources. (a) 18 quotes from the Ubertooth Zero BOM, which lists Mouser part numbers and unit "
     "prices in USD; that file was committed on 4 November 2010, so the quotes carry that date. (b) 5 INR prices "
     "for uGameBox parts, read from the Probots and Zbotic websites on 14 October 2026 (prices include GST). A quote is linked to a "
     "part only when category, value and package all match; 10 of the 26 priced Mouser lines could not be matched and were left out rather than guessed.", align="j")

d.add_heading("2. Table Creation and Constraints (DDL)", 1)
code(d, open(B + "/sql/01_schema.sql").read().strip(), size=8.5)
para(d, "Constraints in the final schema (read from information_schema after the build):", align="j")
table(d, ["Constraint type", "Count", "Examples"], [
    ["PRIMARY KEY", "8", "one surrogate key per table (SERIAL)"],
    ["FOREIGN KEY", "8", "placement.board_id -> board (ON DELETE CASCADE), price_quote.supplier_id -> supplier"],
    ["UNIQUE", "5", "part(category_id, value_text, footprint); placement(board_id, ref_designator); board(name, revision)"],
    ["CHECK", "6", "unit_price > 0; units > 0; completed_on >= started_on; qty_delta <> 0; movement_type list; purchase rule"],
    ["NOT NULL", "31 columns", "every key, name, value and date that the system depends on"],
    ["DEFAULT", "7 columns", "currency 'INR'; captured_at now(); units 1; created_on and started_on CURRENT_DATE"],
], [1.4, 0.9, 4.0], size=10)

d.add_heading("3. Data Population (DML)", 1)
para(d, "Rows per table after running build_db.sh (before any demonstration transactions):", align="j")
table(d, ["Table", "Rows", "Where the rows come from"], [
    ["category", "15", "Assigned by the importer from the designator prefix and symbol name"],
    ["part", "242", "Distinct (category, value, footprint) combinations across all 11 boards"],
    ["board", "11", "uGameBox plus 10 open-hardware boards"],
    ["placement", "678", "One row per reference designator"],
    ["supplier", "11", "Real component distributors (Mouser, DigiKey, LCSC, Probots, Zbotic, ...)"],
    ["price_quote", "23", "18 Mouser (USD, 2010) + 5 Probots/Zbotic (INR, 2026)"],
    ["build", "0", "Filled by using the system (Review III)"],
    ["stock_movement", "0", "Filled by using the system (Review III)"],
], [1.4, 0.7, 4.2], size=10)
para(d, "The build and stock_movement tables start empty on purpose. I have not bought any parts or built any boards "
     "since starting this project, so any rows here would be made up. They are filled by the demonstration transactions in "
     "Review III (11 builds and 23 stock movements after the demo script runs), and those rows are clearly labelled as demonstration data.", align="j")
d.add_heading("3.1 INSERT, UPDATE and DELETE", 2)
t = blocks(L + "transactions_demo.log", "##### T")
para(d, "INSERT: the importer inserts board, part and placement rows inside one transaction per board. Planning a build is a plain INSERT:", align="j")
code(d, trim(strip_title(t["1"]), 9))
para(d, "UPDATE: correcting a part's description.", align="j")
code(d, strip_title(t["9"]))
para(d, "DELETE: a planned build can be deleted; a supplier that already has quotes cannot, because of the foreign key.", align="j")
code(d, strip_title(t["10"]))

d.add_heading("4. SQL Queries and Outputs", 1)
para(d, "Seventeen queries were run on the real data. Each one answers a question that comes up when working with BOMs. "
     "Long outputs are shortened; the full output is in logs/queries_output.log.", align="j")
qs = sql_blocks(B + "/sql/04_queries.sql"); out = blocks(L + "queries_output.log", "=== Q")
notes = {
 "6": "uGameBox is all through-hole, while the other boards are surface-mount. So no exact part is shared, but the same values (100nF, 10k) appear in other packages. This is why a part is defined by value and footprint together.",
 "9": "Only priced lines are added up, so the coverage column is shown next to the cost. A board cost with 4 of 20 lines priced is not the full cost, and the query makes that visible.",
 "13": "This list is what still needs a price before the full uGameBox cost can be known.",
 "15": "The Ubertooth family boards share many parts, which is the situation where a shared parts catalogue saves work. OtterPill v1.3 and v1.4 share all 24 parts; the two revisions differ only in PCB layout.",
}
for n in sorted(qs, key=int):
    title, sql = qs[n]
    d.add_heading(f"Q{n}. {title}", 3)
    code(d, sql, size=8.5)
    code(d, trim(strip_title(out[n]), 13), size=8)
    if n in notes: para(d, notes[n], italic=True, align="j")

d.add_heading("5. Views", 1)
para(d, "Every derived value is a view. No total, count or status is stored in a table.", align="j")
table(d, ["View", "What it computes"], [
    ["v_board_bom", "Quantity of each part on each board (COUNT of placements), with the designator list"],
    ["v_part_consumed", "Parts used by completed builds: units x placements"],
    ["v_stock_on_hand", "SUM(qty_delta) of movements minus consumption"],
    ["v_latest_quote", "Most recent quote per part and currency (DISTINCT ON)"],
    ["v_board_cost", "BOM quantity x latest price, with how many lines are priced"],
    ["v_build_status", "IN PROGRESS / COMPLETED from the build dates"],
    ["v_build_shortfall", "Needed vs on hand for every part of every open build"],
    ["v_build_readiness", "Parts short per open build; ready when none are short"],
    ["v_shared_parts", "Parts placed on more than one board"],
], [1.8, 4.5], size=10, mono_cols=(0,))

plsql = open(B + "/sql/03_plpgsql.sql").read()
def cut(src, start, end):
    i = src.index(start); j = src.index(end, i) if end else len(src); return src[i:j].strip()
d.add_heading("6. Functions and Procedures", 1)
d.add_heading("6.1 Function fn_stock_on_hand", 2)
para(d, "Returns the stock on hand of one part; raises an error for a part that does not exist. Used by the stock trigger and the app.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE FUNCTION fn_stock_on_hand", "-- F2"), size=8.5)
d.add_heading("6.2 Function fn_board_cost", 2)
para(d, "Returns the cost of one board in a given currency from the latest quotes. Example (Q10): fn_board_cost(1, 'INR') = 315.84 for uGameBox, which is 103.84 + 159 + 15 + 38 for the four priced lines.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE FUNCTION fn_board_cost", "-- P1"), size=8.5)
d.add_heading("6.3 Procedure sp_record_purchase", 2)
para(d, "Records parts coming in. If a price is given it is stored as a quote too, so prices live only in price_quote.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE PROCEDURE sp_record_purchase", "-- P2"), size=8.5)
d.add_heading("6.4 Procedure sp_complete_build", 2)
para(d, "Marks a build as completed. It checks that the build exists and is still open; the stock check is done by the trigger trg_build_complete so that it also applies to any direct UPDATE.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE PROCEDURE sp_complete_build", "-- P3"), size=8.5)

d.add_heading("7. Cursor", 1)
para(d, "sp_shopping_list opens an explicit cursor over the shortfall of one build, fetches the rows one at a time, "
     "looks up the cheapest latest quote for each part, prints one line per part and returns the total cost and the number of unpriced parts "
     "through INOUT parameters.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE PROCEDURE sp_shopping_list", "-- T1"), size=8.5)
para(d, "Output for the uGameBox build (from logs/transactions_demo.log):", align="j")
code(d, trim(strip_title(t["3"]), 30), size=8)

d.add_heading("8. Triggers", 1)
d.add_heading("8.1 trg_stock_guard (BEFORE INSERT on stock_movement)", 2)
para(d, "Rejects a negative adjustment that would take stock below zero. It locks the part row first so two adjustments of the same part are checked one after the other.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE FUNCTION trg_fn_stock_guard", "-- T3"), size=8.5)
code(d, trim(strip_title(t["6"]), 8), size=8)
d.add_heading("8.2 trg_build_complete (BEFORE UPDATE OF completed_on on build)", 2)
para(d, "A build can only be completed when no part is short. The parts of the board are locked with SELECT ... FOR UPDATE, "
     "which matters when two builds are completed at the same time (see Review III, concurrency).", align="j")
code(d, open(B + "/sql/03b_trg_build_complete.sql").read().strip(), size=8.5)
code(d, trim(strip_title(t["2"]), 10), size=8)
d.add_heading("8.3 trg_freeze_bom (BEFORE INSERT/UPDATE/DELETE on placement)", 2)
para(d, "Past consumption is computed from a board's placements, so editing the BOM of a board that has been built would silently change history. "
     "The trigger blocks this; a design change must be stored as a new revision.", align="j")
code(d, cut(plsql, "CREATE OR REPLACE FUNCTION trg_fn_freeze_bom", None), size=8.5)
code(d, strip_title(t["8"]), size=8)

d.add_heading("9. Indexes", 1)
para(d, "PostgreSQL creates indexes for primary keys and UNIQUE constraints automatically, but not for foreign keys. "
     "I added indexes on the foreign-key columns used in the views' joins:", align="j")
code(d, open(B + "/sql/06_indexes.sql").read().strip(), size=8.5)
para(d, "Their effect on the real data (678 placements in 4 pages) is measured and discussed honestly in Review III.", align="j")
d.save(B + "/docs/BOM-Track_Review2.docx"); print("saved")
