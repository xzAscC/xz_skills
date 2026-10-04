#!/usr/bin/env python3
"""txt 小说 → EPUB 3（经 pandoc），生成后自动跑 epubcheck。

先看章节切分是否正确：
    build.py 1.txt --vol 第一卷 --list
再生成：
    build.py 1.txt --vol 第一卷 -o "书名1 (作者).epub" --title 书名1 --author 作者 \
        [--illustrator 画师] [--series 书名 --pos 1] [--cover cover.jpg] [--illus img/1]

章节标题行的格式是「行首最多 3 个空白 + 卷名前缀 + 空白 + 章节名」，正文缩进更深。
没有正文的节会被删掉并报告；但给了 --illus 时，名为 --illus-title 的节换成该目录里的图片。
"""
import argparse
import hashlib
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

STYLE = pathlib.Path(__file__).with_name("style.css")
JUNK = r"wenku8|轻小说文库"
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def decode(raw):
    # GBK 一律按 GB18030 解：它是 GBK 的超集，生僻字也不会坏
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("gb18030")


def split(text, vol, junk=JUNK):
    """返回 [(章节名, [段落...]), ...]；章节标题之前的内容丢弃。"""
    head = re.compile(r"^\s{0,3}" + re.escape(vol) + r"\s+(.+?)\s*$")
    junk_re = re.compile(junk, re.I)
    chapters = []
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        # 只删网站分隔线 ◆◇；正文里的 *** / ——— 是场景分隔，要保留
        if not s or junk_re.search(s) or set(s) <= set("◆◇"):
            continue
        m = head.match(line)
        if m:
            chapters.append((m.group(1).strip(), []))
        elif chapters:
            chapters[-1][1].append(s)
    return chapters


def images(folder):
    """目录中的图片按文件名排序，按内容去重（有的站点同一张图列两次）。"""
    seen, out = set(), []
    for f in sorted(pathlib.Path(folder).iterdir()):
        if f.suffix.lower() not in IMG_EXT:
            continue
        h = hashlib.md5(f.read_bytes()).hexdigest()
        if h not in seen:
            seen.add(h)
            out.append(f.resolve())
    return out


def render(chapters, illus=None, illus_title="插图"):
    """生成 HTML；返回 (html, 保留的章节名, 删掉的空节名)。"""
    body, kept, dropped = [], [], []
    for title, paras in chapters:
        if not paras and illus is not None and title == illus_title:
            imgs = images(illus)
            if imgs:
                body.append(f"<h1>{html.escape(title)}</h1>")
                body += [f'<div class="illus"><img src="{p}" alt="" /></div>' for p in imgs]
                kept.append(title)
                continue
        if not paras:
            dropped.append(title)
            continue
        body.append(f"<h1>{html.escape(title)}</h1>")
        body += [f"<p>{html.escape(p)}</p>" for p in paras]
        kept.append(title)
    return "<html><body>\n" + "\n".join(body) + "\n</body></html>\n", kept, dropped


def metadata(a):
    # YAML 兼容 JSON 字符串，用 json.dumps 省去转义问题
    q = json.dumps
    lines = [f"title: {q(a.title)}", f"lang: {q(a.lang)}", "creator:"]
    lines.append(f"  - role: author\n    text: {q(a.author)}")
    if a.illustrator:
        lines.append(f"  - role: illustrator\n    text: {q(a.illustrator)}")
    if a.series:
        lines += [f"belongs-to-collection: {q(a.series)}", f"group-position: {q(a.pos)}"]
    if a.description:
        lines.append(f"description: {q(a.description)}")
    if a.subject:
        lines.append(f"subject: {q(a.subject)}")
    return "\n".join(lines) + "\n"


def add_calibre_series(epub, series, pos):
    """pandoc 只写 EPUB 3 的 belongs-to-collection；补上 calibre:series 供旧阅读器识别。"""
    tmp = epub.with_suffix(".tmp")
    with zipfile.ZipFile(epub) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith(".opf"):
                extra = (f'<meta name="calibre:series" content="{html.escape(series)}" />\n'
                         f'    <meta name="calibre:series_index" content="{html.escape(pos)}" />\n  </metadata>')
                data = data.decode().replace("</metadata>", extra, 1).encode()
            # mimetype 必须第一个且不压缩，其余照原样的压缩方式写回
            zout.writestr(item, data, compress_type=item.compress_type)
    tmp.replace(epub)


def epubcheck(epub):
    if not shutil.which("epubcheck"):
        print("warning: epubcheck not installed; skipped", file=sys.stderr)
        return True
    r = subprocess.run(["epubcheck", str(epub)], capture_output=True, text=True)
    summary = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("Messages:", "ERROR", "FATAL", "WARNING"))]
    print("epubcheck:", "\n  ".join(summary) or "(no summary)")
    return r.returncode == 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("--vol", required=True, help="章节标题行的前缀，如 第一卷 / SSS短篇集")
    p.add_argument("--list", action="store_true", help="只列出识别到的章节")
    p.add_argument("-o", "--out")
    p.add_argument("--title")
    p.add_argument("--author", default="佚名")
    p.add_argument("--illustrator")
    p.add_argument("--series")
    p.add_argument("--pos", default="1", help="系列序号，番外可用小数，如 7.5")
    p.add_argument("--lang", default="zh-CN")
    p.add_argument("--subject")
    p.add_argument("--description")
    p.add_argument("--cover")
    p.add_argument("--illus", help="插图目录，填进名为 --illus-title 的空节")
    p.add_argument("--illus-title", default="插图")
    p.add_argument("--junk", default=JUNK, help="要删除的广告行（正则）")
    a = p.parse_args(argv)

    chapters = split(decode(pathlib.Path(a.src).read_bytes()), a.vol, a.junk)
    if not chapters:
        sys.exit(f"no heading starts with {a.vol!r}; check --vol")
    if a.list:
        for t, ps in chapters:
            print(f"{len(ps):6d}  {t}")
        return
    if not (a.out and a.title):
        sys.exit("-o and --title are required unless --list")

    doc, kept, dropped = render(chapters, a.illus, a.illus_title)
    out = pathlib.Path(a.out).resolve()
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "book.html").write_text(doc, encoding="utf-8")
        (d / "meta.yaml").write_text(metadata(a), encoding="utf-8")
        cmd = ["pandoc", str(d / "book.html"), "-f", "html", "-o", str(out),
               "--metadata-file", str(d / "meta.yaml"), "--css", str(STYLE),
               "--toc", "--toc-depth=1", "--split-level=1"]
        if a.cover:
            cmd += ["--epub-cover-image", str(pathlib.Path(a.cover).resolve())]
        r = subprocess.run(cmd, capture_output=True, text=True)
        # pandoc 缺中文界面翻译时的警告无害，过滤掉
        noise = ("translations", "zh.yaml", "Abstract")
        for l in r.stderr.splitlines():
            if not any(n in l for n in noise):
                print(l, file=sys.stderr)
        if r.returncode:
            sys.exit(r.returncode)
    if a.series:
        add_calibre_series(out, a.series, a.pos)
    print(f"{out.name}: {len(kept)} chapters; dropped empty: {dropped}")
    if not epubcheck(out):
        sys.exit(1)


if __name__ == "__main__":
    main()
