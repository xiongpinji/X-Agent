"""Count pass/fail/skip from a log's progress characters."""
import re
import sys

p, f, s, e, x = 0, 0, 0, 0, 0
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    if re.match(r"^[.sFxXeE ]+\[\s*\d+%\]$", line.strip()) or re.match(
        r"^[.sFxXeE ]+$", line.strip()
    ):
        for ch in line:
            if ch == ".":
                p += 1
            elif ch == "F":
                f += 1
            elif ch == "s":
                s += 1
            elif ch in "eE":
                e += 1
            elif ch in "xX":
                x += 1
print(f"passed={p} failed={f} skipped={s} error={e} xfail={x} total={p+f+s+e+x}")
