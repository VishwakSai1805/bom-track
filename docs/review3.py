import sys, os
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from logparse import *
B = os.path.dirname(os.path.abspath(__file__)) + "/.."
L = B + "/logs/"; SS = B + "/docs/screenshots/"
d = new_doc("BOM-Track: Final Report", "Integrated System and Final Demonstration")
cover(d, "Review III: Integrated System and Final Demonstration", "BOM-Track",
      "A Database for Hardware Bills of Materials, Part Stock and Board Builds",
      [("Implementation", "PostgreSQL 16 (SQL, PL/pgSQL), Python 3, Streamlit")])
header_footer(d, "BOM-Track | BCSE302L Course Project | Final Report")
t = blocks(L + "transactions_demo.log", "##### T")

d.add_heading("Contents", 1)
for x in ["1. Project Title and Student Details", "2. Introduction and Problem Statement", "3. Functional Requirements",
          "4. ER Diagram", "5. Relational Schema", "6. Table Creation and Constraints", "7. SQL Queries and Outputs",
          "8. Procedures, Functions, Cursor and Triggers", "9. Real-World Transaction Demonstrations",
          "10. Conclusion", "Appendix A. How to Run"]:
    para(d, x, after=2)

d.add_heading("1. Project Title and Student Details", 1)
table(d, ["Item", "Detail"], [
    ["Title", "BOM-Track: A Database for Hardware Bills of Materials, Part Stock and Board Builds"],
    ["Student", "Vishwak (individual project)"], ["Register Number", "24BYB0053"],
    ["Course", "BCSE302L Database Systems"],
    ["Platform", "PostgreSQL 16 with PL/pgSQL; Python 3 with psycopg2 and Streamlit"],
], [1.6, 4.7])

d.add_heading("2. Introduction and Problem Statement", 1)
para(d, "When I design a PCB in KiCad, the bill of materials (BOM) comes out as a CSV file. For my 8051 board, uGameBox, "
     "it has 28 lines that group 49 components. The file is a parts list and nothing more: it cannot tell me what the board costs, "
     "what I still need to buy, or whether I have enough parts to build it. Those answers are usually worked out by hand and go stale "
     "as soon as a price changes or parts are used.", align="j")
para(d, "The file also mixes stored facts with numbers that can be calculated. Refs holds a list of designators in one cell, Qty is "
     "just a count of that list, and Value is sometimes a label (nine identical push buttons appear as nine lines named BTN0 to BTN7 "
     "and RESET).", align="j")
para(d, "BOM-Track stores only basic facts: which part is at which position on which board, which price a supplier quoted and when, "
     "how many parts came in, and when a build was started and finished. Everything else (quantities, cost, stock on hand, shortfall, "
     "readiness) is calculated by views and PL/pgSQL code each time it is needed. The database also enforces the rules of the domain with "
     "constraints and triggers, so the application cannot put it into an impossible state.", align="j")

d.add_heading("3. Functional Requirements", 1)
table(d, ["ID", "Requirement", "Implemented by"], [
    ["FR1", "Import a KiCad BOM, one placement per designator", "bomlib.import_board (one transaction); app page Import"],
    ["FR2", "Single parts catalogue with categories", "part, category; UNIQUE(category_id, value_text, footprint)"],
    ["FR3", "Boards and their placements", "board, placement; UNIQUE(board_id, ref_designator)"],
    ["FR4", "Suppliers and dated price quotes", "supplier, price_quote; v_latest_quote"],
    ["FR5", "Purchases and adjustments", "sp_record_purchase; stock_movement; trg_stock_guard"],
    ["FR6", "Plan and complete builds", "build; sp_complete_build; trg_build_complete"],
    ["FR7", "Cost, stock, shortfall, readiness, shared parts", "v_board_cost, v_stock_on_hand, v_build_shortfall, v_build_readiness, v_shared_parts, fn_board_cost"],
    ["FR8", "Reject invalid operations", "CHECK and FK constraints; 3 triggers"],
], [0.5, 2.7, 3.1], size=9.5)

d.add_heading("4. ER Diagram", 1)
d.add_picture(B + "/docs/er.png", width=Inches(6.3))
caption(d, "Figure 1. ER diagram (PK = primary key, FK = foreign key)")
para(d, "BOARD and PART are in an M:N relationship resolved by PLACEMENT, which also carries the designator and label. "
     "PART and SUPPLIER are M:N through PRICE_QUOTE. Every other relationship is 1:N. A stock movement has zero or one "
     "supplier: a purchase names one, an adjustment does not.", align="j")

d.add_heading("5. Relational Schema", 1)
para(d, "Primary keys are underlined, foreign keys are marked with *.", italic=True)
schema = [("CATEGORY", ["category_id"], [], ["name"]),
 ("PART", ["part_id"], ["category_id"], ["value_text", "footprint", "description"]),
 ("BOARD", ["board_id"], [], ["name", "revision", "source", "created_on"]),
 ("PLACEMENT", ["placement_id"], ["board_id", "part_id"], ["ref_designator", "label"]),
 ("SUPPLIER", ["supplier_id"], [], ["name", "website"]),
 ("PRICE_QUOTE", ["quote_id"], ["part_id", "supplier_id"], ["unit_price", "currency", "captured_at"]),
 ("BUILD", ["build_id"], ["board_id"], ["units", "started_on", "completed_on"]),
 ("STOCK_MOVEMENT", ["movement_id"], ["part_id", "supplier_id"], ["qty_delta", "movement_type", "moved_at"])]
for name, pk, fk, rest in schema:
    p = d.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    r = p.add_run(name + " ( "); r.bold = True
    items = [(a, "pk") for a in pk] + [(a, "fk") for a in fk] + [(a, "") for a in rest]
    for i, (a, k) in enumerate(items):
        r = p.add_run(a + ("*" if k == "fk" else ""))
        if k == "pk": r.underline = True
        if i < len(items) - 1: p.add_run(", ")
    p.add_run(" )").bold = True
para(d, "All eight tables are in BCNF: in each table every determinant is a candidate key (the surrogate key, plus the declared "
     "natural keys such as (board_id, ref_designator) and (category_id, value_text, footprint)). The functional dependencies are listed in the Review I document.", align="j")

d.add_heading("6. Table Creation and Constraints", 1)
para(d, "The full DDL is in sql/01_schema.sql and is listed in the Review II document. Summary of the constraints:", align="j")
table(d, ["Type", "Count", "Purpose"], [
    ["PRIMARY KEY", "8", "Surrogate key in every table"],
    ["FOREIGN KEY", "8", "Every reference between tables; placement -> board cascades on delete"],
    ["UNIQUE", "5", "Natural keys: part identity, designator per board, board name + revision, category and supplier names"],
    ["CHECK", "6", "Positive prices and units, valid dates, non-zero movements, movement type, purchase rule"],
    ["NOT NULL", "31 columns", "Keys, names, values and dates"],
    ["DEFAULT", "7 columns", "INR currency, current date/time, 1 unit"],
], [1.4, 1.0, 3.9], size=10)
para(d, "Data loaded from real sources: 11 boards (my uGameBox and 10 published open-hardware designs), 242 parts, 678 placements, "
     "15 categories, 11 suppliers and 23 dated price quotes (18 Mouser prices from 2010 in USD, 5 Probots/Zbotic prices from 14 October 2026 in INR).", align="j")

d.add_heading("7. SQL Queries and Outputs", 1)
para(d, "Seventeen queries were run (full SQL and output in Review II and logs/queries_output.log):", align="j")
qs = sql_blocks(B + "/sql/04_queries.sql"); out = blocks(L + "queries_output.log", "=== Q")
table(d, ["#", "Question answered", "Rows"], [[f"Q{n}", qs[n][0], (re.findall(r"\((\d+) rows?\)", out[n]) or ["-"])[-1]] for n in sorted(qs, key=int)],
      [0.45, 5.15, 0.7], size=9)
d.add_heading("Sample outputs", 2)
for n in ("2", "9", "15"):
    para(d, f"Q{n}. {qs[n][0]}", bold=True)
    code(d, trim(strip_title(out[n]), 14), size=8)

d.add_heading("8. Procedures, Functions, Cursor and Triggers", 1)
table(d, ["Component", "Type", "Used in", "What it does"], [
    ["fn_stock_on_hand", "Function", "Stock trigger, app", "Stock on hand of one part, from movements minus consumption"],
    ["fn_board_cost", "Function", "Board page, Q10", "Cost of a board in a currency from latest quotes"],
    ["sp_record_purchase", "Procedure", "Purchase page", "Inserts a PURCHASE movement; stores the paid price as a quote"],
    ["sp_complete_build", "Procedure", "Builds page", "Validates and completes a build"],
    ["sp_shopping_list", "Procedure with cursor", "Builds page", "Cursor over the shortfall: one line per part, total cost, unpriced count"],
    ["trg_stock_guard", "Trigger (BEFORE INSERT)", "Every stock movement", "Stops stock going below zero; locks the part row"],
    ["trg_build_complete", "Trigger (BEFORE UPDATE)", "Completing a build", "Rejects completion if any part is short; locks the board's parts"],
    ["trg_freeze_bom", "Trigger (BEFORE I/U/D)", "Editing placements", "Blocks BOM edits on boards that have been built"],
], [1.5, 1.25, 1.3, 2.25], size=9, mono_cols=(0,))

d.add_heading("9. Real-World Transaction Demonstrations", 1)
para(d, "The flow is the same for every transaction: the user acts in the Streamlit app, the app runs SQL or calls a PL/pgSQL "
     "procedure through psycopg2, PostgreSQL applies constraints and triggers, commits or rolls back, and the page is redrawn from the views. "
     "Each screen shows the SQL that was executed. The screenshots were taken from the running app in a browser.", align="j")
para(d, "Important: these transactions are demonstrations. The purchases recorded here did not really happen; they exist only to exercise "
     "the system. The script sql/99_reset_demo.sql removes them and returns the database to the real data.", bold=True, align="j")
code(d, '''# app.py: every write runs in its own transaction
def run(sql, params=None):
    c = conn(); c.notices.clear()
    try:
        with c:                      # psycopg2: COMMIT on success, ROLLBACK on exception
            with c.cursor() as cur:
                cur.execute(sql, params)
                out = cur.fetchall() if cur.description else None
        return True, out, [n.strip() for n in c.notices]
    except psycopg2.Error as e:
        return False, e.diag.message_primary, []''', size=8.5)

TX = [
 ("Import a KiCad BOM file", "08_import_bom", 900,
  "The user uploads a KiCad BOM CSV and gives a board name and revision.",
  "board, category, part, placement",
  "Python importer (bomlib.import_board) running INSERTs in one transaction; UNIQUE constraints decide whether a part already exists.",
  "One board row and 49 placement rows are added. Parts that already exist are reused, so no part is duplicated. If any line fails, the whole board is rolled back.",
  "\"Board created with 49 placements. Skipped: none\"."),
 ("Complete a build with no parts in stock", "03_complete_rejected", 1100,
  "A build of 1 uGameBox is planned (INSERT into build), then the user clicks Complete build.",
  "build (update attempted); read: placement, stock_movement via v_build_shortfall",
  "CALL sp_complete_build(1) -> UPDATE build -> trigger trg_build_complete.",
  "Nothing changes. The trigger finds parts short and raises an exception; the transaction is rolled back.",
  "\"Rejected by the database: build 1 cannot be completed: short of 9 x Resistor 1k\"."),
 ("Shopping list for the build (cursor)", "04_shopping_list_cursor", 1900,
  "The user asks for a shopping list for the open build.",
  "Read only: v_build_shortfall, v_latest_quote, supplier",
  "CALL sp_shopping_list(1, 'INR', NULL, NULL): explicit cursor, FETCH loop, RAISE NOTICE per part, INOUT totals.",
  "No change.",
  "20 lines, one per short part. INR 315.84 for the 4 priced lines; 16 lines have no INR quote yet."),
 ("Record a purchase", "05_purchase_form", 1000,
  "The user records buying 1 AT89S52 from Zbotic at INR 103.84.",
  "stock_movement, price_quote",
  "CALL sp_record_purchase(18, 11, 1, 103.84, 'INR'); trigger trg_stock_guard runs on the insert.",
  "One PURCHASE row in stock_movement (+1) and one row in price_quote. Stock on hand rises through v_stock_on_hand.",
  "\"Purchase recorded\"."),
 ("Complete the build once stock is available", "06_build_completed", 1000,
  "After the remaining shortfall is bought (same procedure, called in a loop), the user clicks Complete build again.",
  "build; read: placement, stock_movement",
  "CALL sp_complete_build(1); trigger trg_build_complete locks the parts and finds no shortfall.",
  "completed_on is set. The status in v_build_status changes to COMPLETED and the 49 components are subtracted in v_stock_on_hand through v_part_consumed. No stock column is updated, because none exists.",
  "\"Build 1 completed; its parts are now consumed from stock\"."),
 ("Write off a damaged LED when none is left", "07_adjustment_rejected", 900,
  "The user records -1 LED as an adjustment. All 8 LEDs were used by the build.",
  "stock_movement (insert attempted)",
  "INSERT into stock_movement -> trigger trg_stock_guard -> function fn_stock_on_hand.",
  "Nothing changes; the insert is rejected.",
  "\"stock for part 5 would go negative (on hand 0, change -1)\"."),
]
for i, (title, img, h, op, tables, comp, effect, result) in enumerate(TX, 1):
    d.add_heading(f"9.{i} Transaction {i}: {title}", 2)
    table(d, ["Question", "Answer"], [["Operation", op], ["Tables involved", tables], ["SQL / PL/pgSQL executed", comp],
                                       ["Effect on the database", effect], ["Result shown", result]], [1.7, 4.6], size=9.5)
    d.add_picture(SS + img + ".png", width=Inches(6.2))
    caption(d, f"Figure {i + 1}. {title}")

n = len(TX) + 1
d.add_heading(f"9.{n} Transaction {n}: Editing the BOM of a board that has been built", 2)
table(d, ["Question", "Answer"], [
    ["Operation", "Delete R11 from uGameBox, and relabel SW1, after build 1 was completed."],
    ["Tables involved", "placement (delete and update attempted); read: build"],
    ["SQL / PL/pgSQL executed", "DELETE / UPDATE on placement -> trigger trg_freeze_bom"],
    ["Effect on the database", "Nothing changes. Past consumption is computed from the placements, so changing them would rewrite history."],
    ["Result shown", "\"board 1 has completed builds; create a new revision instead of editing its BOM\""]], [1.7, 4.6], size=9.5)
code(d, strip_title(t["8"]), size=8)
n += 1
d.add_heading(f"9.{n} Transaction {n}: Savepoint inside one transaction", 2)
para(d, "A purchase is recorded, then a quote with a negative price is attempted inside the same transaction. "
     "ROLLBACK TO SAVEPOINT undoes only the bad step; the purchase is kept when the transaction commits.", align="j")
code(d, trim(strip_title(t["11"]), 26), size=8)

d.add_heading("9.10 Concurrency control", 2)
para(d, "Two sessions try to complete two different uGameBox builds at the same moment, with stock for only one board. "
     "Each check reads stock that the other session has not committed yet. To make the timing repeatable, a delay can be "
     "set for the demo session (setting bomtrack.demo_delay = 3 seconds); it is not used in normal operation.", align="j")
para(d, "Run 1 uses a version of the trigger without row locks. Both sessions pass the check and both builds complete:", align="j")
c = open(L + "concurrency_demo.log").read()
r1 = c[c.index(" build_id"):c.index("================ RUN 2")].strip()
code(d, r1, size=8)
para(d, "Stock went negative (-9 push buttons, -9 resistors, -8 LEDs). This is a write-skew anomaly: each transaction was "
     "correct on its own, but together they used the same parts twice.", align="j")
para(d, "Run 2 uses the real trigger, which takes row locks on the board's parts with SELECT ... FOR UPDATE before checking:", align="j")
r2 = c[c.index("================ RUN 2"):].strip()
lines = [l for l in r2.split("\n") if l.strip() and not l.startswith("[A] (") and not l.startswith("[B] (") and "CONTEXT" not in l and "PL/pgSQL function sp_" not in l and "SQL statement" not in l]
code(d, "\n".join(lines[1:]), size=8)
para(d, "Session B started at 11:25:27.2 but was blocked on the row lock until A committed at 11:25:29.2. It then ran its own check, saw that "
     "A had used the parts, and was rejected (it ends at 32.2 because of the 3-second demo delay). Stock ends at exactly 0. Under READ COMMITTED, each statement in the PL/pgSQL trigger takes a "
     "fresh snapshot, so the check after the lock sees A's committed change.", align="j")

d.add_heading("9.11 Crash recovery", 2)
para(d, "One transaction commits a purchase of 5 BC547. A second transaction inserts a purchase of 7 L7805 and is still open when "
     "the server is stopped with pg_ctl stop -m immediate, which kills it without a checkpoint, like a power cut.", align="j")
code(d, open(L + "recovery_demo.log").read().replace("waiting for server to shut down.... done\n", "").strip(), size=7.5)
para(d, "On restart PostgreSQL detects the unclean shutdown and replays the write-ahead log (redo). The committed purchase is "
     "present (durability) and the uncommitted one is gone (atomicity). While the second transaction was open, another session saw "
     "only 1 row and the open session saw 2 (isolation).", align="j")

d.add_heading("9.12 Indexing", 2)
ix = open(L + "indexing_demo.log").read()
code(d, ix[ix.index("=== 1."):ix.index("DROP INDEX")].strip(), size=8)
para(d, "The where-used query (all placements of one part) without an index on placement(part_id), and then with it:", align="j")
def plan(sec_start, sec_end):
    s = ix[ix.index(sec_start):ix.index(sec_end)]
    return "\n".join(l for l in s.split("\n")[1:] if l.strip() and not l.startswith(("CREATE INDEX", "ANALYZE", "SET")))
code(d, plan("=== 2.", "=== 3."), size=8)
code(d, plan("=== 3.", "=== 4."), size=8)
para(d, "With the index the planner switches from a sequential scan to a bitmap index scan, and its cost estimate drops from 12.47 to 9.02. "
     "But the measured times do not show a gain: 0.065 ms without the index, 0.079 ms with it on its first run (the index pages had to be "
     "read from disk, shown as \"read=2\" in the buffers line) and 0.028 ms when repeated. These differences are noise. The whole placement table is "
     "678 rows in 4 pages of 8 KB, so reading all of it is already instant. I did not create a large artificial table to show a bigger "
     "speed-up, because the real data does not need one. The index is kept because it is the correct design for the join and will matter "
     "as more boards are imported. Lookups by designator already use the index created for UNIQUE(board_id, ref_designator):", align="j")
code(d, plan("=== 5.", "=== 6."), size=8)

d.add_heading("9.13 Reports produced by the system", 2)
para(d, "The overview page reads the cost and readiness views directly:", align="j")
d.add_picture(SS + "09_overview_after.png", width=Inches(6.2))
caption(d, f"Figure {len(TX) + 2}. Overview after the demonstration")

d.add_heading("10. Conclusion", 1)
para(d, "BOM-Track turns flat KiCad BOM exports into a normalized PostgreSQL database in which the database does the work: "
     "quantities, costs, stock, shortfall and build status are all computed by views, functions and procedures, and the rules of the "
     "domain are enforced by constraints and triggers. Every component listed in the guidelines is used inside a real operation of the "
     "application, and every output in this report was produced by running the code.", align="j")
d.add_heading("10.1 Limitations", 2)
for x in [
    "Purchases, builds and stock movements in the demonstrations are not real; I have not bought parts for this project yet.",
    "Price coverage is partial: 4 of 20 uGameBox lines have an INR price, and the USD prices for the Ubertooth boards are from 2010.",
    "A part is identified by its exact value and footprint text, so \"100nF\" and \"100n\" are stored as different parts. Normalizing values is future work.",
    "Categories are assigned by rules on the designator prefix and symbol name; unusual designators could be misclassified.",
    "The shortfall of each open build is checked against current stock on its own, so two open builds may both look ready while competing for the same parts. The trigger still prevents both from being completed.",
    "The data set is small (678 placements), so indexing changes the query plan but not the measured time.",
]: bullet(d, x)
d.add_heading("10.2 Future work", 2)
for x in ["Normalize component values (100n = 100nF = 0.1uF) before matching parts.",
          "Import LCSC part numbers where the BOM has them and fetch prices automatically.",
          "Reserve stock for planned builds so that open builds do not compete silently."]: bullet(d, x)

d.add_heading("Appendix A. How to Run", 1)
code(d, '''# Windows (PostgreSQL 18 installed at the default path)
pip install -r requirements.txt
set PGPASSWORD=<your postgres password>
build_db.bat
python -m streamlit run app.py          # opens http://localhost:8501

# Linux / macOS
./build_db.sh
./run_all_demos.sh                      # regenerates every file in logs/
python3 -m streamlit run app.py''', size=9)
d.save(B + "/docs/BOM-Track_Review3_Final_Report.docx"); print("saved")
