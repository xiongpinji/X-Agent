"""Regenerate regression batches by bin-packing per-file test counts."""
import re
from pathlib import Path

root = Path(__file__).parent
counts = {}
for line in (root / "collect_out.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    m = re.match(r"^(tests/[^:]+): (\d+)$", line.strip())
    if m:
        counts[m.group(1)] = int(m.group(2))

batched = set()
tmp = root / ".regression_batches" / "_batchfiles.tmp"
if tmp.exists():
    for l in tmp.read_text(encoding="utf-8").splitlines():
        l = l.strip().replace("\\", "/")
        if l:
            batched.add(l)

collected = set(counts)
missing = sorted(collected - batched)
stale = sorted(batched - collected)
print("collected files:", len(collected), "total tests:", sum(counts.values()))
print("batched files:", len(batched))
print("missing:", len(missing))
for f in missing:
    print("  M", f, counts[f])
print("stale:", len(stale))
for f in stale[:15]:
    print("  S", f)

# Bin-pack all collected files into N batches by count (LPT)
N = 12
bins = [[] for _ in range(N)]
sizes = [0] * N
for f, c in sorted(counts.items(), key=lambda kv: -kv[1]):
    i = sizes.index(min(sizes))
    bins[i].append(f)
    sizes[i] += c

outdir = root / ".regression_batches"
for i, b in enumerate(bins):
    p = outdir / f"reg_{i:02d}.txt"
    p.write_text("\n".join(sorted(b)) + "\n", encoding="utf-8", newline="\n")
    print(f"reg_{i:02d}.txt: {len(b)} files, {sizes[i]} tests")
