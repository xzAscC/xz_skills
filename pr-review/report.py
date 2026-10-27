#!/usr/bin/env python3
"""Render a pr-review report.json into a standalone report.html next to it.

report.json fields (all optional except title; paths relative to the JSON file):
  title, repo, branch, base, pr {number, url}, kind (research|development),
  tier (low|medium|high), tier_reason, summary (blank line = new paragraph),
  findings [{label (Important|Nit|Pre-existing), source, where, text, resolution}],
  rejected [{source, where, text, reason}], reviewers [{name, status, note}],
  screens [{name, before, after}], numbers [{name, before, after}],
  tests [{command, status (pass|fail|not run), reason, output}], rounds, revert
A finding is open when it is Important and its resolution is empty or starts with "open".
"""

import base64
import html
import json
import mimetypes
import sys
from pathlib import Path

LABELS = ("Important", "Nit", "Pre-existing")
TIERS = {"low": "低", "medium": "中", "high": "高"}
KINDS = {"research": "研究", "development": "开发"}
STATUS = {"pass": "通过", "fail": "失败", "not run": "未运行"}

CSS = """
:root { --bg:#fbfaf7; --fg:#1f2328; --muted:#636c76; --line:#d8dee4; --card:#fff;
  --bad:#c0362c; --warn:#9a6700; --good:#1a7f37; --tag:#eef1f4; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181b; --fg:#e6e8eb; --muted:#9aa4ae;
  --line:#30363d; --card:#1e2226; --bad:#ff7b72; --warn:#d29922; --good:#3fb950; --tag:#2a3036; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); line-height:1.55;
  font:15px/1.55 system-ui, "Noto Sans CJK SC", sans-serif; }
main { max-width:1200px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:1.5rem; margin:0 0 4px; } h2 { font-size:1.15rem; margin:32px 0 10px; }
.meta, .muted { color:var(--muted); } a { color:inherit; }
.summary { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:8px; margin:16px 0; }
.summary div { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; }
.summary b { display:block; font-size:1.1rem; }
.bad { color:var(--bad); } .warn { color:var(--warn); } .good { color:var(--good); }
table { width:100%; border-collapse:collapse; background:var(--card); }
th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
code, pre { font-family:ui-monospace, monospace; font-size:13px; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; background:var(--tag); padding:8px; border-radius:6px; }
.tag { background:var(--tag); border-radius:4px; padding:0 6px; white-space:nowrap; }
.pair { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:20px; }
.pair figure { margin:0; } .pair img { width:100%; border:1px solid var(--line); border-radius:6px; }
figcaption { font-size:13px; color:var(--muted); }
body.stacked .pair { grid-template-columns:1fr; } body.stacked .pair figure + figure { display:none; }
body.stacked .pair.swapped figure { display:none; } body.stacked .pair.swapped figure + figure { display:block; }
body.stacked .pair img { cursor:pointer; }
button { font:inherit; padding:2px 10px; }
@media (max-width:640px) { .pair { grid-template-columns:1fr; } }
"""

# Stacked mode shows one image per pair; clicking it swaps before/after in place,
# which makes small visual differences easier to spot than side by side.
JS = """
const mode = document.getElementById('mode');
if (mode) mode.onclick = () => document.body.classList.toggle('stacked');
document.querySelectorAll('.pair img').forEach(img => img.onclick = () => {
  if (document.body.classList.contains('stacked')) img.closest('.pair').classList.toggle('swapped');
});
"""


def esc(value):
    return html.escape("" if value is None else str(value))


def is_open(finding):
    resolution = (finding.get("resolution") or "").strip().lower()
    return finding.get("label") == "Important" and (not resolution or resolution.startswith("open"))


def image(path):
    if not path.is_file():
        raise SystemExit(f"report.py: screenshot not found: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def table(head, rows):
    cells = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{cells}</tr>{body}</table>"


def render(data, root):
    findings = sorted(data.get("findings", []),
                      key=lambda f: LABELS.index(f["label"]) if f.get("label") in LABELS else len(LABELS))
    tests = data.get("tests", [])
    opened = sum(map(is_open, findings))
    counts = " / ".join(f"{label} {sum(f.get('label') == label for f in findings)}" for label in LABELS)
    test_counts = {s: sum(t.get("status") == s for t in tests) for s in STATUS}
    test_text = "，".join(f"{STATUS[s]} {n}" for s, n in test_counts.items() if n) or "没有记录"
    test_class = "bad" if test_counts["fail"] else "warn" if test_counts["not run"] or not tests else "good"
    open_text = f'<b class="bad">未解决 Important：{opened}</b>' if opened else '<b class="good">无未解决问题</b>'

    pr = data.get("pr") or {}
    pr_link = f' · <a href="{esc(pr.get("url"))}">PR #{esc(pr.get("number"))}</a>' if pr.get("url") else ""
    out = [f"<h1>{esc(data['title'])}</h1>",
           f'<div class="meta">{esc(data.get("repo"))} · <code>{esc(data.get("branch"))}</code> → '
           f'<code>{esc(data.get("base"))}</code>{pr_link}</div>',
           '<div class="summary">',
           f'<div>类型<b>{esc(KINDS.get(data.get("kind"), data.get("kind") or "—"))}</b></div>',
           f'<div>风险档<b>{esc(TIERS.get(data.get("tier"), data.get("tier") or "—"))}</b></div>',
           f'<div>测试<b class="{test_class}">{esc(test_text)}</b></div>',
           f"<div>审查意见<b>{esc(counts)}</b></div>",
           f"<div>结论{open_text}</div>",
           f'<div>修复轮数<b>{esc(data.get("rounds", 0))} / 3</b></div>',
           "</div>"]
    out += [f"<p>{esc(p)}</p>" for p in (data.get("summary") or "").split("\n\n") if p.strip()]
    if data.get("tier_reason"):
        out.append(f'<p class="muted">风险档理由：{esc(data["tier_reason"])}</p>')

    out.append("<h2>审查意见</h2>")
    if findings:
        out.append(table(["标签", "来源", "位置", "问题", "处理"], [
            [f'<span class="tag">{esc(f.get("label"))}</span>', esc(f.get("source")),
             f'<code>{esc(f.get("where"))}</code>', esc(f.get("text")),
             '<span class="bad">未解决</span>' if is_open(f) else esc(f.get("resolution"))]
            for f in findings]))
    else:
        out.append("<p>没有审查意见。</p>")
    if data.get("reviewers"):
        out.append('<p class="muted">审查者：' + "；".join(
            f'{esc(r.get("name"))}（{esc(r.get("status"))}{"，" + esc(r["note"]) if r.get("note") else ""}）'
            for r in data["reviewers"]) + "</p>")

    if data.get("screens"):
        out.append('<h2>截图对比 <button id="mode">并排 / 叠放</button></h2>'
                   '<p class="muted">叠放模式下点击图片在改动前后之间切换。</p>')
        for s in data["screens"]:
            out.append(f'<h3>{esc(s.get("name"))}</h3><div class="pair">'
                       f'<figure><img src="{image(root / s["before"])}" alt="改动前"><figcaption>改动前（base）</figcaption></figure>'
                       f'<figure><img src="{image(root / s["after"])}" alt="改动后"><figcaption>改动后（branch）</figcaption></figure>'
                       "</div>")

    if data.get("numbers"):
        out.append("<h2>数值对比</h2>")
        out.append(table(["指标", "改动前", "改动后"], [
            [esc(n.get("name")), esc(n.get("before")),
             f'<span class="{"good" if str(n.get("before")) == str(n.get("after")) else "warn"}">{esc(n.get("after"))}</span>']
            for n in data["numbers"]]))

    out.append("<h2>测试</h2>")
    if tests:
        out.append(table(["命令", "结果", "说明"], [
            [f'<code>{esc(t.get("command"))}</code>',
             f'<span class="{ {"pass": "good", "fail": "bad"}.get(t.get("status"), "warn") }">'
             f'{esc(STATUS.get(t.get("status"), t.get("status")))}</span>',
             esc(t.get("reason")) + (f'<details><summary>输出</summary><pre>{esc(t["output"])}</pre></details>'
                                     if t.get("output") else "")]
            for t in tests]))
    else:
        out.append('<p class="warn">没有运行测试。</p>')

    if data.get("rejected"):
        out.append(f'<h2>未采纳的意见（{len(data["rejected"])}）</h2>')
        out.append(table(["来源", "位置", "意见", "未采纳理由"], [
            [esc(r.get("source")), f'<code>{esc(r.get("where"))}</code>', esc(r.get("text")), esc(r.get("reason"))]
            for r in data["rejected"]]))

    if data.get("revert"):
        out.append(f'<h2>如何回滚</h2><pre>{esc(data["revert"])}</pre>')

    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{esc(data['title'])}</title><style>{CSS}</style></head>"
            f"<body><main>{''.join(out)}</main><script>{JS}</script></body></html>")


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: report.py report.json")
    source = Path(argv[1])
    target = source.with_name("report.html")
    target.write_text(render(json.loads(source.read_text()), source.parent), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main(sys.argv)
