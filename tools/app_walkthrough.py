"""Drive the Streamlit app in a real browser: one full build cycle on uGameBox, with screenshots.
Purchases here are DEMONSTRATION transactions."""
import sys, time, subprocess
from playwright.sync_api import sync_playwright
OUT, CSV = sys.argv[1], sys.argv[2]; URL = "http://localhost:8501"
def wait(page, t=2.0):
    time.sleep(t)
    try: page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=15000)
    except Exception: pass
    time.sleep(0.8)
def nav(page, name): page.get_by_text(name, exact=True).click(); wait(page)
def shot(page, name, h=None):
    if h: page.set_viewport_size({"width": 1400, "height": h}); time.sleep(0.6)
    page.evaluate("""() => { for (const el of document.querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"], section.main, .main')) el.scrollTo(0, 0); window.scrollTo(0, 0); }""")
    time.sleep(0.5)
    page.screenshot(path=f"{OUT}/{name}.png"); print("shot", name)
    page.set_viewport_size({"width": 1400, "height": 900})
def alerts(page): return sorted({a.inner_text() for a in page.locator('[data-testid="stAlert"]').all()})
def psql(sql): return subprocess.run(["psql", "-h", "/tmp", "-U", "postgres", "-d", "bomtrack", "-tAc", sql], capture_output=True, text=True).stdout.strip()
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={"width": 1400, "height": 900})
    page.goto(URL); wait(page, 4); shot(page, "01_overview", 1000)
    nav(page, "Boards and BOM"); shot(page, "02_board_bom_ugamebox", 1500)
    # T: plan build
    nav(page, "Builds"); page.get_by_role("button", name="Plan build").click(); wait(page)
    print("plan ->", alerts(page))
    # T: complete with no stock -> rejected
    page.get_by_role("button", name="Complete build").click(); wait(page)
    print("complete (no stock) ->", alerts(page)); shot(page, "03_complete_rejected", 1250)
    # T: shopping list via cursor
    page.get_by_role("button", name="Shopping list (cursor)").click(); wait(page)
    shot(page, "04_shopping_list_cursor", 1900)
    # T: purchase through the form (AT89S52 from Zbotic at the listed price)
    at = psql("SELECT part_id FROM part WHERE value_text='AT89S52'")
    nav(page, "Purchases and quotes")
    page.get_by_label("part_id").fill(at)
    page.get_by_label("Quantity").fill("1")
    page.get_by_label("Unit price INR (0 = not known)").fill("103.84")
    page.locator('[data-testid="stSelectbox"]').first.click(); page.get_by_role("option", name="Zbotic").click(); wait(page, 1)
    page.get_by_role("button", name="Record purchase").click(); wait(page)
    print("purchase ->", alerts(page)); shot(page, "05_purchase_form", 1100)
    # remaining shortfall bought in one SQL transaction (same procedure, called in a loop)
    psql("""DO $$ DECLARE r RECORD; s INT := (SELECT supplier_id FROM supplier WHERE name='Probots');
            BEGIN FOR r IN SELECT part_id, shortfall FROM v_build_shortfall WHERE build_id=1 AND shortfall>0 LOOP
            CALL sp_record_purchase(r.part_id, s, r.shortfall); END LOOP; END $$""")
    # T: complete build -> succeeds
    nav(page, "Builds"); page.get_by_role("button", name="Complete build").click(); wait(page)
    print("complete (stock ok) ->", alerts(page)); shot(page, "06_build_completed", 1000)
    # T: adjustment that would go negative -> trigger rejects
    led = psql("SELECT part_id FROM part WHERE value_text='LED' AND footprint LIKE 'LED_THT%'")
    nav(page, "Parts and stock"); page.get_by_label("Search value or footprint").fill("LED_THT"); page.keyboard.press("Enter"); wait(page)
    page.get_by_label("part_id").fill(led); page.get_by_label("Change (+/-)").fill("-1")
    page.get_by_role("button", name="Record adjustment").click(); wait(page)
    print("adjust ->", alerts(page)); shot(page, "07_adjustment_rejected", 900)
    # T: import a KiCad BOM file through the UI (one transaction)
    nav(page, "Import KiCad BOM")
    page.locator('input[type="file"]').set_input_files(CSV); wait(page, 1)
    page.get_by_label("Board name").fill("uGameBox"); page.get_by_label("Revision").fill("rev 2 (draft)"); page.keyboard.press("Enter"); wait(page, 1)
    page.get_by_role("button", name="Import").click(); wait(page)
    print("import ->", alerts(page)); shot(page, "08_import_bom", 900)
    nav(page, "Overview"); shot(page, "09_overview_after", 1000)
    b.close()
