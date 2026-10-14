"""Extract a flat BOM (one row per reference designator) from a KiCad schematic.
Supports legacy EESchema .sch (KiCad 4/5) and S-expression .kicad_sch (KiCad 6+).
Output CSV columns: ref,value,footprint,lib_id
Power symbols (#PWR, #FLG) and symbols marked in_bom no are skipped."""
import re, sys, csv, os

def legacy(path):
    raw = open(path, "rb").read()
    try: txt = raw.decode("utf-8")
    except UnicodeDecodeError: txt = raw.decode("latin-1")
    cmp_fp = {}
    cmp = os.path.splitext(path)[0] + ".cmp"
    if os.path.exists(cmp):
        for blk in re.findall(r"BeginCmp(.*?)EndCmp", open(cmp, encoding="latin-1").read(), re.S):
            r = re.search(r"Reference\s*=\s*([^;]+);", blk); m = re.search(r"IdModule\s*=\s*([^;]+);", blk)
            if r and m: cmp_fp[r.group(1).strip()] = m.group(1).strip()
    out = {}
    for blk in re.findall(r"\$Comp\n(.*?)\$EndComp", txt, re.S):
        lib = re.search(r"^L (\S+) (\S+)", blk, re.M)
        f = {int(k): v for k, v in re.findall(r'^F (\d+) "([^"]*)"', blk, re.M)}
        ref = f.get(0, lib.group(2) if lib else "")
        if not ref or ref.startswith("#"): continue
        fp = f.get(2, "") or cmp_fp.get(ref, "")
        out.setdefault(ref, (ref, f.get(1, ""), fp, lib.group(1) if lib else ""))
    return list(out.values())

def sexpr(path):
    s = open(path, encoding="utf-8").read()
    # tokenize
    toks = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', s)
    pos = 0
    def parse():
        nonlocal pos
        lst = []
        while pos < len(toks):
            t = toks[pos]; pos += 1
            if t == "(": lst.append(parse())
            elif t == ")": return lst
            else: lst.append(t[1:-1] if t.startswith('"') else t)
        return lst
    tree = parse()[0]
    out = {}
    for node in tree:
        if isinstance(node, list) and node and node[0] == "symbol" and any(isinstance(x, list) and x[0] == "lib_id" for x in node):
            lib_id = next(x[1] for x in node if isinstance(x, list) and x[0] == "lib_id")
            in_bom = next((x[1] for x in node if isinstance(x, list) and x[0] == "in_bom"), "yes")
            props = {x[1]: x[2] for x in node if isinstance(x, list) and x[0] == "property" and len(x) > 2}
            ref = props.get("Reference", "")
            if in_bom == "no" or not ref or ref.startswith("#") or ref.endswith("?"): continue
            out.setdefault(ref, (ref, props.get("Value", ""), props.get("Footprint", ""), lib_id))
    return list(out.values())

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    rows = sexpr(src) if src.endswith(".kicad_sch") else legacy(src)
    rows.sort(key=lambda r: (re.sub(r"\d+", "", r[0]), int(re.sub(r"\D", "", r[0]) or 0)))
    with open(dst, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["ref", "value", "footprint", "lib_id"]); w.writerows(rows)
    print(f"{os.path.basename(dst)}: {len(rows)} designators")
