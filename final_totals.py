"""Final totals: original batch XMLs with rerun-file results replaced."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).parent / ".regression_batches"


collected = set()
for line in Path("collect_out.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    if ":" in line and line.startswith("tests/"):
        collected.add(line.split(":")[0].strip())


def classname_to_file(cn):
    parts = cn.split(".")
    for i in range(len(parts), 0, -1):
        cand = "/".join(parts[:i]) + ".py"
        if cand in collected:
            return cand
    return cn.replace(".", "/") + ".py"


def per_file(xml_path):
    """Return {file_path: [passed, failed, skipped, error]}."""
    out = {}
    tree = ET.parse(xml_path)
    r = tree.getroot()
    suites = [r] if r.tag == "testsuite" else r.findall("testsuite")
    for s in suites:
        for tc in s.iter("testcase"):
            f = classname_to_file(tc.get("classname") or "")
            rec = out.setdefault(f, [0, 0, 0, 0])
            if tc.find("failure") is not None:
                rec[1] += 1
            elif tc.find("error") is not None:
                rec[3] += 1
            elif tc.find("skipped") is not None:
                rec[2] += 1
            else:
                rec[0] += 1
    return out


orig = {}
for x in sorted(root.glob("s_*.xml")) + [root / "diag_agentext.xml", root / "diag_covbranch.xml"]:
    for f, rec in per_file(x).items():
        orig[f] = rec

rerun_files = set()
for name in ("rerun_0.txt", "rerun_1.txt"):
    rerun_files.update(
        l.strip() for l in (root / name).read_text().splitlines() if l.strip()
    )

rerun = {}
for x in ("rr0_p0.xml", "rr0_p1.xml", "rerun_1.xml"):
    for f, rec in per_file(root / x).items():
        rerun[f] = rec

# sanity: rerun coverage of the 65 files
missing = rerun_files - set(rerun)
print("rerun files:", len(rerun_files), "covered:", len(set(rerun) & rerun_files), "missing:", sorted(missing))

tp = tf = ts = te = 0
for f, rec in orig.items():
    use = rerun.get(f, rec) if f in rerun_files else rec
    tp, tf, ts, te = tp + use[0], tf + use[1], ts + use[2], te + use[3]
print(f"FINAL passed={tp} failed={tf} skipped={ts} error={te} total={tp+tf+ts+te}")
print(f"pass_rate_all={tp/(tp+tf+ts+te)*100:.2f}%")
print(f"pass_rate_excl_skip={tp/(tp+tf+te)*100:.2f}%")

# per-file final failures for classification
print("\n--- files with remaining failures/errors ---")
for f in sorted(orig):
    use = rerun.get(f, orig[f]) if f in rerun_files else orig[f]
    if use[1] or use[3]:
        print(f"{f}: failed={use[1]} error={use[3]}")

# detailed remaining failure list
print("\n--- remaining failure details ---")
for x in ("rr0_p0.xml", "rr0_p1.xml", "rerun_1.xml"):
    tree = ET.parse(root / x)
    r = tree.getroot()
    suites = [r] if r.tag == "testsuite" else r.findall("testsuite")
    for s in suites:
        for tc in s.iter("testcase"):
            for bad in list(tc.findall("failure")) + list(tc.findall("error")):
                msg = (bad.get("message") or "")[:120].replace("\n", " ")
                print(f"{tc.get('classname')}::{tc.get('name')} | {msg}")
