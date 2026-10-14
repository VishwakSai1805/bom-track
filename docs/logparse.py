import re
def blocks(path, marker):
    """Split a log into {key: text} by lines starting with marker, e.g. '=== Q' or '##### T'."""
    out, key, buf = {}, None, []
    for line in open(path, encoding="utf-8", errors="replace").read().split("\n"):
        if line.startswith(marker):
            if key: out[key] = "\n".join(buf).strip("\n")
            key = line[len(marker):].split(".")[0].strip(); buf = [line]
        elif key: buf.append(line)
    if key: out[key] = "\n".join(buf).strip("\n")
    return out
def sql_blocks(path):
    """Split sql/04_queries.sql into {n: sql} using the \\echo markers."""
    out, key, buf = {}, None, []
    for line in open(path).read().split("\n"):
        m = re.match(r"\\echo '=== Q(\d+)\. (.*)'", line)
        if m:
            if key: out[key] = (title, "\n".join(buf).strip())
            key, title, buf = m.group(1), m.group(2), []
        elif key and not line.startswith("\\"): buf.append(line)
    if key: out[key] = (title, "\n".join(buf).strip())
    return out
def trim(text, n=14):
    lines = [l for l in text.split("\n")]
    if len(lines) <= n: return text
    tail = [l for l in lines if re.match(r"^\(\d+ rows?\)$", l.strip())]
    return "\n".join(lines[:n] + ["...", tail[-1] if tail else ""])
def strip_title(text):
    body = "\n".join(text.split("\n")[1:]).strip("\n")
    return re.sub(r"psql:[^:]+:\d+: ", "", body)
def section(path, start, end=None):
    s = open(path, encoding="utf-8", errors="replace").read()
    i = s.index(start); j = s.index(end, i + len(start)) if end else len(s)
    return s[i:j].rstrip()
