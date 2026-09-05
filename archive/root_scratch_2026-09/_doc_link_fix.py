# -*- coding: utf-8 -*-
"""P1-21 链接修复: 依据 _doc_move_map.json 重写受影响的对内 markdown 链接。"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, "_doc_move_map.json"), encoding="utf-8") as fh:
    FMAP = json.load(fh)  # old repo-rel -> new repo-rel

NEW2OLD = {v: k for k, v in FMAP.items()}

DIR_MAP = {
    "docs/01-项目规划": "docs/concepts/planning/01-项目规划",
    "docs/02-技术设计": "docs/concepts/design/02-技术设计",
    "docs/best-practices": "docs/developer/best-practices/best-practices",
    "docs/case-studies": "docs/concepts/case-studies",
    "docs/diagrams": "docs/concepts/diagrams",
    "docs/enterprise": "docs/admin/enterprise/enterprise",
    "docs/faq": "docs/operations/support/faq",
    "docs/specs": "docs/developer/specs",
    "docs/superpowers": "docs/concepts/planning/superpowers",
    "docs/training-materials": "docs/developer/tutorials/training-materials",
    "docs/troubleshooting": "docs/operations/support/troubleshooting",
    "docs/tutorials": "docs/developer/tutorials/tutorials",
    "docs/user-guide": "docs/developer/tutorials/user-guide",
    "docs/video-scripts": "docs/developer/tutorials/video-scripts",
    "docs/video-tutorials": "docs/developer/tutorials/video-tutorials",
    "backend/docs": None,  # 整目录解散, 文件级走 FMAP
}

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

def norm(p):
    return os.path.normpath(p).replace("\\", "/")

def map_target(repo_rel):
    """repo-rel 旧路径 -> 新路径(若被移动)"""
    if repo_rel in FMAP:
        return FMAP[repo_rel]
    for sd, dd in DIR_MAP.items():
        if dd and (repo_rel == sd or repo_rel.startswith(sd + "/")):
            return dd + repo_rel[len(sd):]
    return None

def relink(target, old_file_rel, new_file_rel):
    """返回 (新链接文本 or None, 状态)"""
    t = target.strip()
    if not t or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", t) or t.startswith("#") or t.startswith("<"):
        return None, "skip"
    anchor = ""
    if "#" in t:
        t, anchor = t.split("#", 1)
        anchor = "#" + anchor
    if not t:  # 纯锚点
        return None, "skip"
    t = t.split("?")[0]
    if t.startswith("/"):  # 站点绝对路径不处理
        return None, "skip"
    # 候选1: 相对文件旧位置解析
    old_dir = os.path.dirname(old_file_rel).replace("\\", "/")
    cand1 = norm(os.path.join(old_dir, t)) if old_dir else norm(t)
    # 候选2: 仓库根相对
    cand2 = norm(t)
    new_repo = map_target(cand1) or map_target(cand2)
    if not new_repo:
        # 未移动: 检查旧解析目标是否仍存在(原样保留)
        if os.path.exists(os.path.join(ROOT, cand1)):
            return None, "ok"
        if os.path.exists(os.path.join(ROOT, cand2)):
            return None, "ok"
        return None, "broken"
    new_dir = os.path.dirname(new_file_rel).replace("\\", "/")
    rel = os.path.relpath(os.path.join(ROOT, new_repo), os.path.join(ROOT, new_dir)).replace("\\", "/")
    if not rel.startswith("."):
        rel = "./" + rel
    return rel + anchor, "fixed"

def process(path_rel):
    path = os.path.join(ROOT, path_rel)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    old_rel = NEW2OLD.get(path_rel, path_rel)  # 被移动文件按其旧位置解析旧链接
    stats = {"fixed": 0, "broken": 0, "ok": 0, "skip": 0}
    broken_list = []
    def repl(mobj):
        label, target = mobj.group(1), mobj.group(2)
        new_t, st = relink(target, old_rel, path_rel)
        stats[st] += 1
        if st == "broken":
            broken_list.append(target)
        if new_t:
            return f"[{label}]({new_t})"
        return mobj.group(0)
    out = LINK_RE.sub(repl, text)
    if out != text:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out)
    return stats, broken_list

def main():
    targets = []
    # docs/ 全部 .md
    for dp, _, fns in os.walk(os.path.join(ROOT, "docs")):
        for fn in fns:
            if fn.endswith(".md"):
                targets.append(os.path.relpath(os.path.join(dp, fn), ROOT).replace("\\", "/"))
    # 根目录保留 .md
    for fn in os.listdir(ROOT):
        if fn.endswith(".md"):
            targets.append(fn)
    # examples/*.md
    for fn in os.listdir(os.path.join(ROOT, "examples")):
        if fn.endswith(".md"):
            targets.append(f"examples/{fn}")
    total = {"fixed": 0, "broken": 0, "ok": 0, "skip": 0}
    broken_report = {}
    for t in sorted(set(targets)):
        st, bl = process(t)
        for k in total:
            total[k] += st[k]
        if bl:
            broken_report[t] = bl
    print("总计:", total)
    print("含失效链接的文件数:", len(broken_report))
    with open(os.path.join(ROOT, "_broken_links.json"), "w", encoding="utf-8") as fh:
        json.dump(broken_report, fh, ensure_ascii=False, indent=1)
    for f, bl in list(broken_report.items())[:15]:
        print(" ", f, "->", bl[:4])

if __name__ == "__main__":
    main()
