"""Repack tests into N balanced batches."""
import re
import sys
from pathlib import Path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
root = Path(__file__).parent
counts = {}
for line in (root / "collect_out.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    m = re.match(r"^(tests/[^:]+): (\d+)$", line.strip())
    if m:
        counts[m.group(1)] = int(m.group(2))

bins = [[] for _ in range(N)]
sizes = [0] * N
for f, c in sorted(counts.items(), key=lambda kv: -kv[1]):
    i = sizes.index(min(sizes))
    bins[i].append(f)
    sizes[i] += c

outdir = root / ".regression_batches"
for i, b in enumerate(bins):
    (outdir / f"s_{i:02d}.txt").write_text(
        "\n".join(sorted(b)) + "\n", encoding="utf-8", newline="\n"
    )
print(f"{N} batches, sizes {min(sizes)}-{max(sizes)}")
