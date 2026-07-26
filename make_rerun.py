"""Map failing dotted test names to file paths, emit two group files."""
from pathlib import Path

root = Path(__file__).parent
collected = set()
for line in (root / "collect_out.txt").read_text(encoding="utf-8", errors="replace").splitlines():
    if ":" in line and line.startswith("tests/"):
        collected.add(line.split(":")[0].strip())

skip = {"tests/test_agent_extended.py", "tests/test_coverage_branch_coverage.py"}
files = set()
for line in (root / ".regression_batches" / "fail_by_file.txt").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or "FAILED:" not in line:
        continue
    dotted = line.split("FAILED:")[1].strip()
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        cand = "/".join(parts[:i]) + ".py"
        if cand in collected:
            if cand not in skip:
                files.add(cand)
            break

files = sorted(files)
half = (len(files) + 1) // 2
for idx, group in enumerate([files[:half], files[half:]]):
    (root / ".regression_batches" / f"rerun_{idx}.txt").write_text(
        "\n".join(group) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"rerun_{idx}.txt: {len(group)} files")
print("total files:", len(files))
