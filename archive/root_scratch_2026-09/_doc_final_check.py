# -*- coding: utf-8 -*-
"""P1-21 最终校验: 按新位置解析全部对内链接; 扫描范围外对旧路径的引用。"""
import json, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_doc_move_map.json"), encoding="utf-8") as fh:
    FMAP = json.load(fh)
OLD_PATHS = set(FMAP)
DIR_MAP_OLD = ["docs/01-项目规划", "docs/02-技术设计", "docs/best-practices", "docs/case-studies",
               "docs/diagrams", "docs/enterprise", "docs/faq", "docs/specs", "docs/superpowers",
               "docs/training-materials", "docs/troubleshooting", "docs/tutorials", "docs/user-guide",
               "docs/video-scripts", "docs/video-tutorials", "backend/docs"]

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

def check_file(rel):
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return []
    broken = []
    d = os.path.dirname(rel).replace("\\", "/")
    for mobj in LINK_RE.finditer(text):
        t = mobj.group(2).strip()
        if not t or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", t) or t.startswith("#") or t.startswith("/") or t.startswith("<"):
            continue
        t2 = t.split("#")[0].split("?")[0]
        if not t2:
            continue
        cand = os.path.normpath(os.path.join(d, t2)).replace("\\", "/")
        cand_root = os.path.normpath(t2).replace("\\", "/")
        if os.path.exists(os.path.join(ROOT, cand)) or os.path.exists(os.path.join(ROOT, cand_root)):
            continue
        broken.append(t)
    return broken

def collect(scope_dirs, scope_root_md=False):
    files = []
    for sd in scope_dirs:
        for dp, _, fns in os.walk(os.path.join(ROOT, sd)):
            for fn in fns:
                if fn.endswith(".md"):
                    files.append(os.path.relpath(os.path.join(dp, fn), ROOT).replace("\\", "/"))
    if scope_root_md:
        for fn in os.listdir(ROOT):
            if fn.endswith(".md"):
                files.append(fn)
    return sorted(files)

print("== 范围内最终失效链接 ==")
in_scope = collect(["docs", "examples"], scope_root_md=True)
total_broken = 0
for rel in in_scope:
    bl = check_file(rel)
    if bl:
        total_broken += len(bl)
        print(f"  {rel}: {bl}")
print(f"范围内文件 {len(in_scope)} 个, 失效链接 {total_broken} 处")

print("\n== 范围外对旧路径的引用(仅报告, 不修改) ==")
out_scope_dirs = ["backend", "commercial_audit", "monitoring", "deployment", "disaster-recovery",
                  "benchmarks", "archive", "tests", "scripts", "cli", "frontend", "desktop",
                  "extension", "k8s", "mobile", "cloud", "packaging", "sdks", "skills"]
hits = {}
for sd in out_scope_dirs:
    base = os.path.join(ROOT, sd)
    if not os.path.isdir(base):
        continue
    for dp, dns, fns in os.walk(base):
        dns[:] = [x for x in dns if x not in ("node_modules", "__pycache__", ".git")]
        for fn in fns:
            if not fn.endswith((".md", ".py", ".txt", ".rst")):
                continue
            p = os.path.join(dp, fn)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except Exception:
                continue
            found = set()
            for old in OLD_PATHS:
                if old in text:
                    found.add(old)
            for od in DIR_MAP_OLD:
                if od + "/" in text:
                    found.add(od + "/")
            if found:
                rel = os.path.relpath(p, ROOT).replace("\\", "/")
                hits[rel] = sorted(found)
print(f"范围外引用旧路径的文件数: {len(hits)}")
for rel, found in sorted(hits.items())[:30]:
    print(f"  {rel}: {found[:3]}{'...' if len(found) > 3 else ''}")
with open(os.path.join(ROOT, "_out_scope_refs.json"), "w", encoding="utf-8") as fh:
    json.dump(hits, fh, ensure_ascii=False, indent=1)
