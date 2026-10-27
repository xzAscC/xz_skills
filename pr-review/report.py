#!/usr/bin/env python3
"""Render a pr-review report.json into a standalone report.html next to it.

The page reads top-down by importance: the verdict and what needs the user, the summary,
a structure diagram with the stack, then a guide that explains the change section by
section next to its diffs (core first, as in Linear's guided reviews), evidence, and the
full review log.

report.json fields (all optional except title; paths relative to the JSON file):
  title, repo, branch, base, pr {number, url}, kind (research|development),
  tier (low|medium|high), tier_reason, summary (blank line = new paragraph),
  diff: unified diff file such as diff.patch,
  guide [{title, why, files [path]}]: core first; files no section names go to a last one,
  structure {columns [{title, nodes [{id, label, note, status (new|modified|unchanged|external)}]}],
             edges [{from, to, label}]},
  stack [{name, note}],
  findings [{label (Important|Nit|Pre-existing), source, where (path:line), text, resolution}],
  rejected [{source, where, text, reason}], reviewers [{name, status (done|...), note}],
  screens [{name, before, after}], numbers [{name, before, after}],
  tests [{command, status (pass|fail|not run), reason, output}], rounds, revert
A finding is unresolved while its resolution is empty or starts with "open".
Any other test status counts as a failure; any reviewer status but "done" as unfinished.
"""

import base64
import html
import json
import mimetypes
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

LABELS = ("Important", "Nit", "Pre-existing")
TIERS = {"low": "低", "medium": "中", "high": "高"}
KINDS = {"research": "研究", "development": "开发"}
STATUS = {"pass": "通过", "fail": "失败", "not run": "未运行"}
NODES = {"new": "新增", "modified": "修改", "unchanged": "未改", "external": "外部"}
HUNK = re.compile(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

CSS = """
:root { color-scheme:light; --bg:#f7f7f8; --panel:#fff; --sunken:#f1f1f3; --line:#e4e4e8;
  --fg:#1b1c1f; --muted:#5f636b; --faint:#999da5; --accent:#5e6ad2; --good:#2b8a52; --bad:#cf3f35;
  --warn:#a86b00; --good-bg:#e8f5ee; --bad-bg:#fcebea; --warn-bg:#fbf1dc; --accent-bg:#eceefb; }
@media (prefers-color-scheme: dark) { :root { color-scheme:dark; --bg:#0e0f11; --panel:#16171a;
  --sunken:#1d1e22; --line:#27292e; --fg:#e7e8eb; --muted:#a3a7ae; --faint:#6c717a; --accent:#8d95f2;
  --good:#4cb782; --bad:#f06a6a; --warn:#f2c94c; --good-bg:rgba(76,183,130,.13);
  --bad-bg:rgba(240,106,106,.13); --warn-bg:rgba(242,201,76,.12); --accent-bg:rgba(141,149,242,.14); } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); -webkit-font-smoothing:antialiased;
  font:14px/1.6 Inter, system-ui, "Noto Sans CJK SC", sans-serif; }
main { max-width:1240px; margin:0 auto; padding:40px 24px 96px; }
a { color:inherit; text-decoration:none; } a:hover { text-decoration:underline; }
code, pre, .mono { font-family:"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px; }
.crumb { color:var(--muted); font-size:13px; }
h1 { font-size:24px; font-weight:600; letter-spacing:-.01em; margin:4px 0 14px; }
h2 { font-size:12px; font-weight:600; letter-spacing:.08em; color:var(--faint); margin:52px 0 14px; }
h3 { font-size:15px; font-weight:600; margin:0 0 6px; }
.chips { display:flex; flex-wrap:wrap; gap:6px; }
.chip { display:inline-flex; align-items:center; gap:6px; border:1px solid var(--line); background:var(--panel);
  border-radius:999px; padding:2px 10px; font-size:12.5px; color:var(--muted); white-space:nowrap; }
.chip b { color:var(--fg); font-weight:600; }
.add { color:var(--good); } .del { color:var(--bad); }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
.verdict { margin-top:24px; padding:18px 22px; border-left:4px solid var(--good); }
.verdict.bad { border-left-color:var(--bad); } .verdict.warn { border-left-color:var(--warn); }
.verdict-title { font-size:18px; font-weight:600; }
.verdict.good .verdict-title { color:var(--good); } .verdict.bad .verdict-title { color:var(--bad); }
.verdict.warn .verdict-title { color:var(--warn); }
.verdict-sub { color:var(--muted); }
.items { list-style:none; margin:14px 0 0; padding:0; display:grid; gap:8px; }
.items li { display:grid; grid-template-columns:110px 1fr; gap:12px; align-items:baseline; }
.sev { justify-self:start; font-size:11.5px; font-weight:600; border-radius:4px; padding:1px 7px; white-space:nowrap; }
.sev.bad { background:var(--bad-bg); color:var(--bad); } .sev.warn { background:var(--warn-bg); color:var(--warn); }
.sev.info { background:var(--sunken); color:var(--muted); } .sev.good { background:var(--good-bg); color:var(--good); }
.where { color:var(--faint); font-size:12px; margin-left:6px; }
.summary p { max-width:82ch; margin:18px 0 0; }
.muted { color:var(--muted); }
.diagram { padding:20px 20px 12px; overflow-x:auto; }
.diagram svg { display:block; max-width:100%; height:auto; }
.n rect { fill:var(--panel); stroke:var(--line); stroke-width:1.2; }
.n.new rect { stroke:var(--accent); fill:var(--accent-bg); } .n.modified rect { stroke:var(--warn); fill:var(--warn-bg); }
.n.external rect { stroke-dasharray:4 3; fill:var(--sunken); }
.n .l { fill:var(--fg); font-size:12.5px; font-weight:600; } .n .s { fill:var(--muted); font-size:11px; }
.n .t { font-size:10px; font-weight:600; } .n.new .t { fill:var(--accent); } .n.modified .t { fill:var(--warn); }
.ct { fill:var(--faint); font-size:11.5px; font-weight:600; letter-spacing:.06em; }
.e { fill:none; stroke:var(--faint); stroke-width:1.2; } .ah { fill:var(--faint); }
.el { fill:var(--muted); font-size:10.5px; paint-order:stroke; stroke:var(--panel); stroke-width:4px; }
.legend { display:flex; flex-wrap:wrap; gap:14px; padding:10px 20px 16px; font-size:12px; color:var(--muted); }
.legend i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; vertical-align:-1px;
  border:1.2px solid var(--line); background:var(--panel); }
.legend .new { border-color:var(--accent); background:var(--accent-bg); }
.legend .modified { border-color:var(--warn); background:var(--warn-bg); }
.legend .external { border-style:dashed; background:var(--sunken); }
.stack { margin-top:12px; }
.section { display:grid; grid-template-columns:minmax(260px, 340px) minmax(0, 1fr); gap:28px; padding:26px 0;
  border-top:1px solid var(--line); }
.guide > .section:first-child { border-top:0; padding-top:4px; }
.side { position:sticky; top:16px; align-self:start; }
.step { color:var(--faint); font-size:12px; font-variant-numeric:tabular-nums; }
.side p { color:var(--muted); margin:0 0 14px; }
.files { list-style:none; padding:0; margin:0; border:1px solid var(--line); border-radius:8px; background:var(--panel); }
.files li { display:flex; justify-content:space-between; gap:10px; padding:6px 10px; border-top:1px solid var(--line); font-size:12.5px; }
.files li:first-child { border-top:0; }
.fname { font-family:"JetBrains Mono", ui-monospace, monospace; } .fdir { color:var(--faint); margin-left:6px; }
.count { white-space:nowrap; font-family:ui-monospace, monospace; font-size:12px; }
.diffs { display:grid; gap:10px; min-width:0; align-content:start; }
details.file { border:1px solid var(--line); border-radius:8px; background:var(--panel); overflow:hidden; }
details.file > summary { display:flex; justify-content:space-between; gap:12px; padding:8px 12px; cursor:pointer;
  list-style:none; font-size:12.5px; }
details.file > summary::-webkit-details-marker { display:none; }
details.file > summary::before { content:"▸"; color:var(--faint); margin-right:8px; }
details.file[open] > summary::before { content:"▾"; }
details.file > summary .path { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
details.file[open] > summary { border-bottom:1px solid var(--line); }
.diff { overflow-x:auto; font:12px/1.55 "JetBrains Mono", ui-monospace, monospace; }
.diff table { border-collapse:collapse; width:100%; }
.diff td { padding:0 10px; white-space:pre; vertical-align:top; }
.diff td.ln { color:var(--faint); text-align:right; user-select:none; width:1%; padding:0 6px; }
.diff tr.a { background:var(--good-bg); } .diff tr.d { background:var(--bad-bg); }
.diff tr.h td { color:var(--faint); background:var(--sunken); padding:3px 10px; }
.toolbar { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:12px; }
.seg { display:inline-flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; background:var(--panel); }
.seg button { font:inherit; font-size:12.5px; border:0; background:none; color:var(--muted); padding:4px 12px; cursor:pointer; }
.seg button.on { background:var(--sunken); color:var(--fg); }
.shot { margin-bottom:22px; } .shot h3 { font-size:13px; color:var(--muted); font-weight:500; }
.pair { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.pair figure { margin:0; } .pair img { width:100%; display:block; border:1px solid var(--line); border-radius:8px; }
figcaption { font-size:12px; color:var(--faint); margin-top:6px; }
body.stacked .pair { grid-template-columns:1fr; } body.stacked .pair figure + figure { display:none; }
body.stacked .pair.swapped figure { display:none; } body.stacked .pair.swapped figure + figure { display:block; }
body.stacked .pair img { cursor:pointer; }
.tbl { width:100%; border-collapse:collapse; font-size:13px; }
.tbl th { text-align:left; color:var(--faint); font-weight:500; font-size:12px; padding:9px 14px; }
.tbl td { padding:9px 14px; border-top:1px solid var(--line); vertical-align:top; }
.tbl td:first-child { white-space:nowrap; }
.log > details { margin-top:10px; }
.log summary { cursor:pointer; color:var(--muted); font-size:13px; padding:4px 0; }
.log .panel { margin-top:8px; overflow-x:auto; }
pre.out { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--sunken); padding:10px; border-radius:6px; margin:8px 0 0; }
@media (max-width:860px) { .section { grid-template-columns:1fr; } .side { position:static; } }
@media (max-width:640px) { main { padding:24px 16px 64px; } .pair { grid-template-columns:1fr; }
  .items li { grid-template-columns:1fr; gap:2px; } }
"""

# Stacked mode shows one screenshot per pair; clicking it swaps before/after in place,
# which shows small differences better than side by side. A file link opens its diff.
JS = """
document.querySelectorAll('[data-mode]').forEach(b => b.onclick = () => {
  document.body.classList.toggle('stacked', b.dataset.mode === 'stacked');
  document.querySelectorAll('[data-mode]').forEach(x => x.classList.toggle('on', x === b));
});
document.querySelectorAll('.pair img').forEach(img => img.onclick = () => {
  if (document.body.classList.contains('stacked')) img.closest('.pair').classList.toggle('swapped');
});
document.querySelectorAll('a[href^="#f"]').forEach(a => a.addEventListener('click', () => {
  const d = document.querySelector(a.getAttribute('href'));
  if (d) d.open = true;
}));
"""


def esc(value):
    return html.escape("" if value is None else str(value))


def label(finding):
    # Case-insensitive; a missing or unknown label counts as Important so it cannot hide a bug.
    return {name.lower(): name for name in LABELS}.get(str(finding.get("label") or "").strip().lower(), "Important")


def status(item):
    return str(item.get("status") or "").strip().lower()


def unresolved(finding):
    resolution = str(finding.get("resolution") or "").strip().lower()
    return not resolution or resolution.startswith("open")


def same(before, after):
    # Decimal compares exactly (no float rounding of large integers) and treats 1 and 1.0 as equal.
    if before is None or after is None:
        return False
    a, b = str(before).strip(), str(after).strip()
    try:
        x, y = Decimal(a), Decimal(b)
        if x.is_nan() or y.is_nan():  # checked first: comparing a signaling NaN raises
            return x.is_nan() and y.is_nan()
        return x == y
    except InvalidOperation:
        return a == b


def clip(text, units):
    # Fit a label into a diagram box: CJK characters are about twice as wide as Latin ones.
    text, out, used = str(text or ""), "", 0
    for ch in text:
        used += 2 if ord(ch) > 0x2E80 else 1
        if used > units:
            return out + "…"
        out += ch
    return out


def image(root, name):
    path = root / str(name or "")
    if not name or not path.is_file():
        raise SystemExit(f"report.py: screenshot not found: {path if name else '(no path given)'}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def parse_diff(text):
    """Split a unified diff into files with +/- counts and rows (kind, old line, new line, text)."""
    files = []
    for line in text.splitlines():
        if line.startswith("diff --git "):
            files.append({"path": line.split(" b/", 1)[-1], "add": 0, "del": 0, "rows": [], "hunk": False})
            continue
        if not files:
            continue
        f = files[-1]
        m = HUNK.match(line)
        if m:
            f.update(hunk=True, old=int(m[1]), new=int(m[2]))
            f["rows"].append(("h", "", "", line))
        elif not f["hunk"]:
            continue  # file header: index, ---/+++, mode and rename lines
        elif line.startswith("+"):
            f["add"] += 1
            f["rows"].append(("a", "", f["new"], line[1:]))
            f["new"] += 1
        elif line.startswith("-"):
            f["del"] += 1
            f["rows"].append(("d", f["old"], "", line[1:]))
            f["old"] += 1
        elif line.startswith("\\"):
            f["rows"].append(("h", "", "", line))
        else:
            f["rows"].append(("c", f["old"], f["new"], line[1:]))
            f["old"] += 1
            f["new"] += 1
    return files


def counts(add, dele):
    return f'<span class="count"><span class="add">+{add}</span> <span class="del">−{dele}</span></span>'


def file_name(path):
    folder, _, name = str(path).rpartition("/")
    return f'<span class="fname">{esc(name)}</span>' + (f'<span class="fdir">{esc(folder)}/</span>' if folder else "")


def where_link(where, anchors):
    path = str(where or "").split(":", 1)[0]
    text = f'<code>{esc(where)}</code>'
    return f'<a href="#{anchors[path]}">{text}</a>' if path in anchors else text


def diagram(structure):
    columns = structure.get("columns") or []
    if not columns:
        return ""
    w, h, gap, vgap, top = 214, 54, 96, 14, 34
    pos, nodes, edges, bottom = {}, [], [], top
    for i, column in enumerate(columns):
        x = i * (w + gap)
        nodes.append(f'<text class="ct" x="{x}" y="14">{esc(column.get("title"))}</text>')
        for j, node in enumerate(column.get("nodes") or []):
            y = top + j * (h + vgap)
            kind = node.get("status") if node.get("status") in NODES else "unchanged"
            pos[node.get("id")] = (i, x, y)
            tag = f'<text class="t" x="{x + w - 10}" y="{y + 17}" text-anchor="end">{NODES[kind]}</text>' \
                if kind in ("new", "modified") else ""
            nodes.append(f'<g class="n {kind}"><title>{esc(node.get("label"))}：{esc(node.get("note"))}</title>'
                         f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>'
                         f'<text class="l" x="{x + 12}" y="{y + 22}">{esc(clip(node.get("label"), 24 if tag else 30))}</text>'
                         f'<text class="s" x="{x + 12}" y="{y + 41}">{esc(clip(node.get("note"), 32))}</text>{tag}</g>')
            bottom = max(bottom, y + h)
    for e in structure.get("edges") or []:
        a, b = pos.get(e.get("from")), pos.get(e.get("to"))
        if not a or not b:
            continue
        (ca, xa, ya), (cb, xb, yb) = a, b
        y1, y2 = ya + h / 2, yb + h / 2
        if ca == cb:  # same column: loop out on the right side
            x1 = x2 = xa + w
            d, lx = f"M{x1},{y1} C{x1 + 44},{y1} {x2 + 44},{y2} {x2 + 4},{y2}", x1 + 36
        else:
            x1, x2 = (xa + w, xb - 4) if ca < cb else (xa, xb + w + 4)
            mid = (x1 + x2) / 2
            d, lx = f"M{x1},{y1} C{mid},{y1} {mid},{y2} {x2},{y2}", mid
        edges.append(f'<path class="e" d="{d}" marker-end="url(#arrow)"/>')
        if e.get("label"):
            edges.append(f'<text class="el" x="{lx}" y="{(y1 + y2) / 2 - 5}" text-anchor="middle">{esc(e["label"])}</text>')
    width = len(columns) * (w + gap) - gap + 52  # room for same-column loops on the right
    marker = ('<defs><marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" '
              'orient="auto"><path class="ah" d="M0,0 L8,4 L0,8 z"/></marker></defs>')
    return (f'<svg viewBox="-2 0 {width} {bottom + 4}" width="{width}" role="img" aria-label="代码结构图">'
            f'{marker}{"".join(edges)}{"".join(nodes)}</svg>')


def attention(findings, tests, reviewers):
    """Items that need the user, most severe first: (severity, tag, html)."""
    items = []
    for f in findings:
        if unresolved(f):
            sev = "bad" if label(f) == "Important" else "info"
            items.append((sev, label(f), esc(f.get("text")) + f'<span class="where">{esc(f.get("where"))}</span>'))
    for t in tests:
        if status(t) not in ("pass", "not run"):
            items.append(("bad", "测试失败", f'<code>{esc(t.get("command"))}</code>'))
        elif status(t) == "not run":
            items.append(("warn", "未运行", f'<code>{esc(t.get("command"))}</code> {esc(t.get("reason"))}'))
    if not tests:
        items.append(("warn", "没有测试", "没有测试记录"))
    for r in reviewers:
        if status(r) != "done":
            items.append(("warn", "审查未完成", f'{esc(r.get("name") or "未命名审查者")} {esc(r.get("status"))}'))
    order = {"bad": 0, "warn": 1, "info": 2}
    return sorted(items, key=lambda item: order[item[0]])


def render(data, root):
    findings = sorted(data.get("findings") or [], key=lambda f: (not unresolved(f), LABELS.index(label(f))))
    tests = data.get("tests") or []
    reviewers = data.get("reviewers") or []
    diff = parse_diff((root / data["diff"]).read_text(encoding="utf-8")) if data.get("diff") else []
    anchors = {f["path"]: f"f{i}" for i, f in enumerate(diff)}
    statuses = [status(t) for t in tests]

    pr = data.get("pr") or {}
    url = str(pr.get("url") or "")
    crumb = [esc(data.get("repo"))] if data.get("repo") else []
    if url.startswith(("https://", "http://")):
        crumb.append(f'<a href="{esc(url)}">PR #{esc(pr.get("number"))}</a>')
    if data.get("branch"):
        crumb.append(f'<code>{esc(data.get("branch"))}</code> → <code>{esc(data.get("base"))}</code>')
    test_text = "，".join(f"{STATUS.get(s, s or '无状态')} {statuses.count(s)}" for s in dict.fromkeys(statuses))
    chips = [f'<span class="chip">类型 <b>{esc(KINDS.get(data.get("kind"), data.get("kind") or "—"))}</b></span>',
             f'<span class="chip">风险 <b>{esc(TIERS.get(data.get("tier"), data.get("tier") or "—"))}</b></span>']
    if diff:
        chips.append(f'<span class="chip">{len(diff)} 个文件 {counts(sum(f["add"] for f in diff), sum(f["del"] for f in diff))}</span>')
    chips.append(f'<span class="chip">测试 <b>{esc(test_text or "没有记录")}</b></span>')
    chips.append(f'<span class="chip">修复轮数 <b>{esc(data.get("rounds", 0))} / 3</b></span>')
    out = [f'<div class="crumb">{" · ".join(crumb)}</div>', f"<h1>{esc(data['title'])}</h1>",
           f'<div class="chips">{"".join(chips)}</div>']

    # Verdict first: what blocks the merge, then what needs a look, then optional items.
    items = attention(findings, tests, reviewers)
    blocking = [i for i in items if i[0] != "info"]
    worst = items[0][0] if items else "good"
    if worst == "bad":
        title, sub, cls = f"需要处理 {len(blocking)} 项", "先处理下面红色的项目再合并。", "bad"
    elif worst == "warn":
        title, sub, cls = f"合并前请确认 {len(blocking)} 项", "没有已知的 bug，但还有项目没验证完。", "warn"
    else:
        optional = len(items)
        title, cls = "可以合并", "good"
        sub = f"无未解决问题；另有 {optional} 条可选意见，不阻塞合并。" if optional else "无未解决问题。"
    out.append(f'<section class="panel verdict {cls}"><div class="verdict-title">{title}</div>'
               f'<div class="verdict-sub">{sub}</div>')
    if items:
        out.append('<ul class="items">' + "".join(
            f'<li><span class="sev {sev}">{esc(tag)}</span><span>{text}</span></li>' for sev, tag, text in items) + "</ul>")
    out.append("</section>")

    out.append('<div class="summary">' + "".join(
        f"<p>{esc(p)}</p>" for p in (data.get("summary") or "").split("\n\n") if p.strip()))
    if data.get("tier_reason"):
        out.append(f'<p class="muted">风险档理由：{esc(data["tier_reason"])}</p>')
    out.append("</div>")

    structure = data.get("structure") or {}
    if structure.get("columns") or data.get("stack"):
        out.append("<h2>结构与技术栈</h2>")
        if structure.get("columns"):
            out.append(f'<div class="panel"><div class="diagram">{diagram(structure)}</div><div class="legend">'
                       + "".join(f'<span><i class="{k}"></i>{v}</span>' for k, v in NODES.items()) + "</div></div>")
        if data.get("stack"):
            out.append('<div class="chips stack">' + "".join(
                f'<span class="chip"><b>{esc(s.get("name"))}</b>{esc(s.get("note"))}</span>' for s in data["stack"]) + "</div>")

    sections = [dict(s) for s in data.get("guide") or []]
    named = {p for s in sections for p in s.get("files") or []}
    rest = [f["path"] for f in diff if f["path"] not in named]
    if rest:
        sections.append({"title": "其他改动" if sections else "全部改动",
                         "why": "导读没有单独解释的文件。" if sections else "", "files": rest})
    if sections:
        out.append('<h2>改动导读</h2><div class="guide">')
        by_path = {f["path"]: f for f in diff}
        for n, s in enumerate(sections, 1):
            paths = s.get("files") or []
            listed = "".join(
                f'<li><a href="#{anchors[p]}">{file_name(p)}</a>{counts(by_path[p]["add"], by_path[p]["del"])}</li>'
                if p in by_path else f"<li>{file_name(p)}</li>" for p in paths)
            diffs = "".join(
                f'<details class="file" id="{anchors[p]}"><summary><span class="path">{file_name(p)}</span>'
                f'{counts(by_path[p]["add"], by_path[p]["del"])}</summary><div class="diff"><table>'
                + "".join(f'<tr class="{k}"><td class="ln">{o}</td><td class="ln">{w}</td><td>{esc(t)}</td></tr>'
                          if k != "h" else f'<tr class="h"><td colspan="3">{esc(t)}</td></tr>'
                          for k, o, w, t in by_path[p]["rows"])
                + "</table></div></details>" for p in paths if p in by_path)
            out.append(f'<section class="section"><div class="side"><div class="step">{n:02d} / {len(sections):02d}</div>'
                       f'<h3>{esc(s.get("title"))}</h3><p>{esc(s.get("why"))}</p><ul class="files">{listed}</ul></div>'
                       f'<div class="diffs">{diffs}</div></section>')
        out.append("</div>")

    if data.get("screens") or data.get("numbers") or tests:
        out.append("<h2>证据</h2>")
    if data.get("screens"):
        out.append('<div class="toolbar"><span class="muted">截图对比 · 叠放时点击图片切换改动前后</span>'
                   '<span class="seg"><button data-mode="side" class="on">并排</button>'
                   '<button data-mode="stacked">叠放</button></span></div>')
        for s in data["screens"]:
            out.append(f'<div class="shot"><h3>{esc(s.get("name"))}</h3><div class="pair">'
                       f'<figure><img src="{image(root, s.get("before"))}" alt="改动前"><figcaption>改动前 · {esc(data.get("base") or "base")}</figcaption></figure>'
                       f'<figure><img src="{image(root, s.get("after"))}" alt="改动后"><figcaption>改动后 · {esc(data.get("branch") or "branch")}</figcaption></figure>'
                       "</div></div>")
    if data.get("numbers"):
        out.append('<div class="panel"><table class="tbl"><tr><th>指标</th><th>改动前</th><th>改动后</th></tr>' + "".join(
            f'<tr><td>{esc(n.get("name"))}</td><td>{esc(n.get("before"))}</td><td><span class="sev '
            f'{"good" if same(n.get("before"), n.get("after")) else "warn"}">{esc(n.get("after"))}</span></td></tr>'
            for n in data["numbers"]) + "</table></div>")
    if tests:
        out.append('<div class="panel" style="margin-top:14px"><table class="tbl"><tr><th>结果</th><th>命令</th><th>说明</th></tr>' + "".join(
            f'<tr><td><span class="sev {({"pass": "good", "not run": "warn"}).get(status(t), "bad")}">'
            f'{esc(STATUS.get(status(t), status(t) or "无状态"))}</span></td><td><code>{esc(t.get("command"))}</code></td>'
            f'<td>{esc(t.get("reason"))}'
            + (f'<details><summary class="muted">输出</summary><pre class="out">{esc(t["output"])}</pre></details>'
               if t.get("output") else "") + "</td></tr>" for t in tests) + "</table></div>")

    out.append('<h2>审查记录</h2><div class="log">')
    tally = " · ".join(f"{name} {sum(label(f) == name for f in findings)}" for name in LABELS)
    fixed = sum(not unresolved(f) for f in findings)
    out.append(f'<div class="chips"><span class="chip">意见 <b>{tally}</b></span>'
               f'<span class="chip">已处理 <b>{fixed} / {len(findings)}</b></span>'
               + (f'<span class="chip">未采纳 <b>{len(data["rejected"])}</b></span>' if data.get("rejected") else "")
               + "</div>")
    if reviewers:
        out.append('<p class="muted">审查者：' + "；".join(
            f'{esc(r.get("name") or "未命名审查者")}（{esc(r.get("status"))}{"，" + esc(r["note"]) if r.get("note") else ""}）'
            for r in reviewers) + "</p>")
    if findings:
        out.append(f'<details><summary>全部 {len(findings)} 条意见</summary><div class="panel"><table class="tbl">'
                   "<tr><th>标签</th><th>位置</th><th>问题</th><th>处理</th><th>来源</th></tr>" + "".join(
                       f'<tr><td><span class="sev {"bad" if label(f) == "Important" else "info"}">{esc(label(f))}</span></td>'
                       f'<td>{where_link(f.get("where"), anchors)}</td><td>{esc(f.get("text"))}</td>'
                       f'<td>{"<b>未解决</b> " if unresolved(f) else ""}{esc(f.get("resolution"))}</td>'
                       f'<td class="muted">{esc(f.get("source"))}</td></tr>' for f in findings) + "</table></div></details>")
    else:
        out.append('<p class="muted">没有审查意见。</p>')
    if data.get("rejected"):
        out.append(f'<details><summary>未采纳的 {len(data["rejected"])} 条意见</summary><div class="panel"><table class="tbl">'
                   "<tr><th>来源</th><th>位置</th><th>意见</th><th>未采纳理由</th></tr>" + "".join(
                       f'<tr><td class="muted">{esc(r.get("source"))}</td><td>{where_link(r.get("where"), anchors)}</td>'
                       f'<td>{esc(r.get("text"))}</td><td>{esc(r.get("reason"))}</td></tr>' for r in data["rejected"])
                   + "</table></div></details>")
    out.append("</div>")

    if data.get("revert"):
        out.append(f'<h2>如何回滚</h2><pre class="out">{esc(data["revert"])}</pre>')

    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{esc(data['title'])}</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(out)}</main><script>{JS}</script></body></html>")


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: report.py report.json")
    source = Path(argv[1])
    target = source.with_name("report.html")
    target.write_text(render(json.loads(source.read_text(encoding="utf-8")), source.parent), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main(sys.argv)
