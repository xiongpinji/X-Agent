# -*- coding: utf-8 -*-
"""P1-21 第二遍链接修复: 修复"源文件变深导致指向未移动目标的相对链接失效"。"""
import json, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_doc_move_map.json"), encoding="utf-8") as fh:
    FMAP = json.load(fh)
NEW2OLD = {v: k for k, v in FMAP.items()}
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

def norm(p):
    return os.path.normpath(p).replace("\\", "/")

fixed_total = 0
for new_rel, old_rel in sorted(NEW2OLD.items()):
    if not new_rel.endswith(".md"):
        continue
    path = os.path.join(ROOT, new_rel)
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    old_dir = os.path.dirname(old_rel).replace("\\", "/")
    new_dir = os.path.dirname(new_rel).replace("\\", "/")
    changed = False
    def repl(mobj):
        global fixed_total, changed
        label, target = mobj.group(1), mobj.group(2)
        t = target.strip()
        if not t or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", t) or t.startswith("#") or t.startswith("/") or t.startswith("<"):
            return mobj.group(0)
        anchor = ""
        core = t
        if "#" in core:
            core, anchor = core.split("#", 1)
            anchor = "#" + anchor
        core = core.split("?")[0]
        if not core:
            return mobj.group(0)
        # 新位置已可解析 -> 不动
        if os.path.exists(os.path.join(ROOT, norm(os.path.join(new_dir, core)))):
            return mobj.group(0)
        # 旧位置可解析(移动前有效) -> 按新位置重写
        old_resolved = norm(os.path.join(old_dir, core))
        # 旧目标自身若被移动, 用其新位置
        final_target = FMAP.get(old_resolved, old_resolved)
        if os.path.exists(os.path.join(ROOT, final_target)):
            rel = os.path.relpath(os.path.join(ROOT, final_target), os.path.join(ROOT, new_dir)).replace("\\", "/")
            if not rel.startswith("."):
                rel = "./" + rel
            fixed_total += 1
            changed = True
            return f"[{label}]({rel}{anchor})"
        return mobj.group(0)
    out = LINK_RE.sub(repl, text)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
print("第二遍修复:", fixed_total, "处")
