import xml.etree.ElementTree as ET
import sys

t = ET.parse(sys.argv[1] if len(sys.argv) > 1 else ".regression_batches/b02.xml")
root = t.getroot()
rows = []
for tc in root.iter("testcase"):
    status = "passed"
    for tag in ("error", "failure", "skipped"):
        if tc.find(tag) is not None:
            status = tag if tag != "failure" else "failed"
            break
    rows.append((tc.get("classname"), tc.get("name"), status))

first_bad = None
for i, (cn, name, st) in enumerate(rows):
    if st in ("error", "failed"):
        first_bad = i
        print("FIRST BAD:", cn, name, st)
        break

# files executed before first bad (unique, in order)
seen = []
for cn, name, st in rows[: first_bad or 0]:
    if cn not in seen:
        seen.append(cn)
print("classes before first bad:", seen[-6:])

# aggregate
from collections import Counter
c = Counter(st for _, _, st in rows)
print("status counts:", dict(c))
bad_classes = Counter(cn for cn, _, st in rows if st in ("error", "failed"))
print("bad classes:", dict(bad_classes))
