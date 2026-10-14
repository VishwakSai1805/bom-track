"""Load real supplier prices into price_quote.
Source: Ubertooth Zero BOM (Mouser part numbers and unit prices, committed 2010-11-04, USD).
A quote is attached to a PART when the category, the numeric value and the package all match.
Lines that cannot be matched to a part already in the database are reported, not guessed."""
import csv, re, sys
from bomlib import connect
DATA = sys.argv[1]
conn = connect()
MULT = {"P": 1e-12, "N": 1e-9, "U": 1e-6, "µ": 1e-6, "Μ": 1e-6, "M": 1e-3, "K": 1e3, "R": 1, "": 1, "MEG": 1e6}

def num(text, unit_letter):
    """'2p2'->2.2e-12, '100nF'->1e-7, '.5PF'->5e-13, '10K'->1e4, '5n6'->5.6e-9, '4.7k'->4700"""
    t = text.upper().replace("µ", "U").replace("Μ", "U").replace(" ", "")
    t = re.sub(unit_letter + r"$", "", t)          # drop trailing F / H / OHM
    m = re.fullmatch(r"(\d*)\.?(\d*)?(MEG|[PNUMKR]?)(\d*)", t)
    if not m: return None
    a, b, mult, c = m.groups()
    if c and not b:                                # 2P2 / 5N6 / 4K7 style
        val = float(f"{a or 0}.{c}")
    else:
        try: val = float(f"{a or 0}.{b or 0}")
        except ValueError: return None
    return round(val * MULT.get(mult, 1), 18)

def describe(desc):
    d = desc.upper()
    pkg = re.search(r"\b(0201|0402|0603|0805|1206)\b", d)
    if d.startswith("CAP"):
        v = re.search(r"([\d.]+)\s*(PF|NF|UF)", d); return "Capacitor", num(v.group(1) + v.group(2)[0], "") if v else None, pkg and pkg.group(1)
    if d.startswith("RES") or "RESISTOR" in d:
        v = re.search(r"\s([\d.]+)\s*(K|M)?\s*(OHMS?)?\s+\d+%", d) or re.search(r"\s([\d.]+)\s*(K|M)?\s*OHMS?\b", d)
        return "Resistor", num(v.group(1) + (v.group(2) or ""), "") if v else None, pkg and pkg.group(1)
    if d.startswith("INDUCTOR"):
        v = re.search(r"([\d.]+)\s*(NH|UH)", d); return "Inductor / Ferrite", num(v.group(1) + v.group(2)[0], "") if v else None, pkg and pkg.group(1)
    return None, None, None

cur = conn.cursor()
cur.execute("SELECT supplier_id FROM supplier WHERE name='Mouser Electronics'"); mouser = cur.fetchone()[0]
cur.execute("SELECT p.part_id, c.name, p.value_text, p.footprint FROM part p JOIN category c USING(category_id)")
parts = cur.fetchall()
loaded, unmatched = 0, []
with conn:
    for r in csv.DictReader(open(f"{DATA}/raw/mouser-quotes-ubertooth-zero-2010.csv", encoding="latin-1")):
        r = {k.replace("\n", " "): v for k, v in r.items()}
        if not r.get("Price Each"): continue
        price = float(r["Price Each"]); mpn = r["Manufacturer Part Number"].upper(); desc = r["Description"]
        cat, val, pkg = describe(desc)
        hits = []
        for pid, pcat, pval, pfp in parts:
            if cat and pcat == cat and pfp == pkg:
                unit = {"Capacitor": "F", "Inductor / Ferrite": "H", "Resistor": "OHM"}[cat]
                if val is not None and num(pval, unit) == val: hits.append(pid)
            elif not cat and len(pval) >= 4 and (pval.upper() in mpn or mpn.startswith(pval.upper())):
                hits.append(pid)
        for pid in hits:
            cur.execute("INSERT INTO price_quote(part_id, supplier_id, unit_price, currency, captured_at) VALUES (%s,%s,%s,'USD','2010-11-04')",
                        (pid, mouser, price)); loaded += 1
        if not hits: unmatched.append(f"{r['Reference Designator']}: {desc} ({mpn})")
print("quotes loaded:", loaded); print("unmatched lines:", len(unmatched)); [print("  ", u) for u in unmatched]

# Second source: INR prices checked on supplier websites on 2026-10-14 for uGameBox parts.
with conn:
    n = 0
    for r in csv.DictReader(open(f"{DATA}/quotes_inr_2026-10-14.csv", encoding="utf-8")):
        cur.execute("""INSERT INTO price_quote(part_id, supplier_id, unit_price, currency, captured_at)
                       SELECT pl.part_id, s.supplier_id, %s, 'INR', %s
                       FROM placement pl JOIN board b ON b.board_id = pl.board_id, supplier s
                       WHERE b.name = 'uGameBox' AND pl.ref_designator = %s AND s.name = %s""",
                    (r["unit_price_inr"], r["captured_on"], r["ugamebox_ref"], r["supplier"]))
        n += cur.rowcount
    print("INR quotes loaded:", n)
