import subprocess, os, json, re

out = subprocess.run(
    ["./venv/Scripts/python.exe", "-m", "pytest", "tests/", "--collect-only", "-q", "--no-cov"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
)

counts = {}
level_name = {}   # indent level -> name
cur_module = None
for line in out.stdout.splitlines():
    stripped = line.strip()
    indent = (len(line) - len(line.lstrip())) // 2
    m = re.match(r"<(Dir|Package|Module|Class|Function|Coroutine)\s+([^>]+)>", stripped)
    if not m:
        continue
    kind, name = m.group(1), m.group(2)
    if kind in ("Dir", "Package"):
        level_name[indent] = name
        # clear deeper levels
        for k in list(level_name):
            if k > indent:
                del level_name[k]
        cur_module = None
    elif kind == "Module":
        level_name[indent] = name
        for k in list(level_name):
            if k > indent:
                del level_name[k]
        parts = [level_name[k] for k in sorted(level_name)]
        # parts[0] is repo root dir name; drop it
        path = "/".join(parts[1:])
        cur_module = path
        counts.setdefault(path, 0)
    elif kind in ("Function", "Coroutine"):
        if cur_module:
            counts[cur_module] += 1

files = sorted((f, n) for f, n in counts.items() if n > 0)
total = sum(n for _, n in files)
print("files:", len(files), "tests:", total)

bins, cur, cur_n = [], [], 0
for f, n in files:
    if cur_n + n > 380 and cur:
        bins.append(cur)
        cur, cur_n = [], 0
    cur.append(f)
    cur_n += n
if cur:
    bins.append(cur)

os.makedirs(".regression_batches", exist_ok=True)
meta = []
for i, b in enumerate(bins):
    p = ".regression_batches/batch_%02d.txt" % i
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(b))
    meta.append({"batch": i, "files": len(b), "tests": sum(counts[f] for f in b)})
print(json.dumps(meta))
