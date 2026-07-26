"""Aggregate pass/fail/skip counts from junit XML files."""
import sys
import xml.etree.ElementTree as ET

tp = tf = ts = te = 0
failures = []
for path in sys.argv[1:]:
    try:
        tree = ET.parse(path)
    except Exception as ex:
        print(f"{path}: PARSE_ERROR {ex}")
        continue
    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    for s in suites:
        tp += int(s.get("tests", 0)) - int(s.get("failures", 0)) - int(s.get("errors", 0)) - int(s.get("skipped", 0))
        tf += int(s.get("failures", 0))
        te += int(s.get("errors", 0))
        ts += int(s.get("skipped", 0))
        for tc in s.iter("testcase"):
            for bad in list(tc.findall("failure")) + list(tc.findall("error")):
                name = f"{tc.get('classname')}::{tc.get('name')}"
                msg = (bad.get("message") or "")[:150]
                failures.append(f"{name} | {msg}")
print(f"passed={tp} failed={tf} skipped={ts} error={te} total={tp+tf+ts+te}")
for f_ in failures:
    print("FAILED:", f_)
