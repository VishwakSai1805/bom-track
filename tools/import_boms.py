"""Load real KiCad BOMs into BOM-Track. One transaction per board: a bad file leaves no partial board behind.
Usage: python import_boms.py <data_dir>"""
import csv, sys
from bomlib import connect, import_board, rows_for

DATA = sys.argv[1]
conn = connect()
with conn:
    with conn.cursor() as cur:
        for s in csv.DictReader(open(f"{DATA}/suppliers.csv", encoding="utf-8")):
            cur.execute("INSERT INTO supplier(name, website) VALUES (%s,%s) ON CONFLICT (name) DO NOTHING", (s["name"], s["website"]))
for b in csv.DictReader(open(f"{DATA}/boards.csv", encoding="utf-8")):
    _, n, skipped = import_board(conn, b["name"], b["revision"], b["source"], rows_for(b["format"], f"{DATA}/raw/{b['file']}"))
    print(f"{b['name']:<20} {b['revision']:<12} placements={n:<4} skipped={skipped}")
