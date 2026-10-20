"""Shared BOM import logic used by the command-line importer and the Streamlit app."""
import csv, re, sys, os, psycopg2


EXCLUDE_REF = re.compile(r"^(FID|MH|H\d|TP|LOGO|G\d)", re.I)

def excluded(ref, value, fp):
    if EXCLUDE_REF.match(ref): return "mounting/fiducial/test point"
    if re.search(r"testpad|mounting_hole|fiducial", fp + value, re.I): return "mounting/fiducial/test point"
    if re.match(r"^(NS|NA)\(", value.upper()) or value.upper() in ("NA", "DNP", "NS"): return "not fitted (NS/NA/DNP)"
    return None

def category(ref, value, lib):
    pre = re.sub(r"\d.*$", "", ref).upper(); v = value.upper(); l = lib.upper()
    if "LED" in v or l.endswith(":LED") or l == "LED" or pre in ("ACT", "CHRG", "LNK") : return "LED"
    if pre in ("C",): return "Capacitor"
    if pre in ("R", "RM"): return "Resistor"
    if pre == "RV": return "Potentiometer"
    if pre in ("L", "FB"): return "Inductor / Ferrite"
    if pre in ("D", "TVS"): return "Diode"
    if pre in ("Q", "FET"): return "Transistor"
    if pre in ("X", "Y"): return "Crystal"
    if pre in ("U", "IC", "DCDC"): return "IC / Module"
    if pre in ("SW", "BUT", "RST", "S"): return "Switch"
    if pre in ("BT", "BAT") and "CON" not in l: return "Battery"
    if pre == "DS": return "Display"
    if pre in ("BZ", "LS"): return "Buzzer"
    if pre == "T": return "Transformer"
    if pre in ("J", "P", "CON", "EXT", "UEXT", "USB-UART", "LAN_CON", "MICRO_SD", "BAT", "PWR", "ANT"): return "Connector"
    return "Other"

def expand(refs):
    out = []
    for tok in refs.split(","):
        tok = tok.strip()
        m = re.fullmatch(r"([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)", tok)
        out += [m.group(1) + str(i) for i in range(int(m.group(2)), int(m.group(4)) + 1)] if m else [tok]
    return out

def rows_for(fmt, path):
    """Yield (ref, value, footprint, lib_id) from a KiCad grouped CSV or a flat extract."""
    if fmt == "kicad_grouped":       # KiCad grouped export: Refs,Value,Footprint,Qty
        for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
            refs = expand(r["Refs"])
            assert len(refs) == int(r["Qty"]), f"Qty mismatch on {r['Refs']}"
            for ref in refs: yield ref, r["Value"], r["Footprint"], ""
    else:                            # flat export from tools/extract_kicad.py: ref,value,footprint,lib_id
        for r in csv.DictReader(open(path, newline="", encoding="utf-8")): yield r["ref"], r["value"], r["footprint"], r["lib_id"]

LABEL_ONLY = re.compile(r"^(BTN\d+|RESET)$")   # uGameBox uses Value as a button label

def get_id(cur, sql_sel, sql_ins, args):
    cur.execute(sql_sel, args); row = cur.fetchone()
    if row: return row[0]
    cur.execute(sql_ins, args); return cur.fetchone()[0]


def connect():
    host = os.environ.get("PGHOST") or ("localhost" if os.name == "nt" else "/tmp")
    # sslmode/keepalives help on hosted databases (e.g. Neon) that drop idle sockets.
    return psycopg2.connect(host=host, dbname=os.environ.get("PGDATABASE", "bomtrack"),
                            user=os.environ.get("PGUSER", "postgres"), password=os.environ.get("PGPASSWORD"),
                            port=os.environ.get("PGPORT", "5432"),
                            sslmode=os.environ.get("PGSSLMODE", "prefer"),
                            connect_timeout=10, keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=3)

def import_board(conn, name, revision, source, rows):
    """rows: iterable of (ref, value, footprint, lib_id). Runs as ONE transaction; returns (board_id, placed, skipped)."""
    skipped = {}
    with conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO board(name, revision, source) VALUES (%s,%s,%s) RETURNING board_id", (name, revision, source))
            board_id = cur.fetchone()[0]; n = 0
            for ref, value, fp, lib in rows:
                why = excluded(ref, value, fp)
                if why: skipped[why] = skipped.get(why, 0) + 1; continue
                cat = category(ref, value, lib); label = None
                if cat == "Switch" and LABEL_ONLY.match(value): label, value = value, "Push button 6mm"
                value = value.strip() or "(no value)"
                cat_id = get_id(cur, "SELECT category_id FROM category WHERE name=%s",
                                "INSERT INTO category(name) VALUES (%s) RETURNING category_id", (cat,))
                part_id = get_id(cur, "SELECT part_id FROM part WHERE category_id=%s AND value_text=%s AND footprint=%s",
                                 "INSERT INTO part(category_id, value_text, footprint) VALUES (%s,%s,%s) RETURNING part_id",
                                 (cat_id, value, fp.strip()))
                cur.execute("INSERT INTO placement(board_id, part_id, ref_designator, label) VALUES (%s,%s,%s,%s)",
                            (board_id, part_id, ref, label))
                n += 1
    return board_id, n, skipped
