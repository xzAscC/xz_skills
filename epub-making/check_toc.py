#!/usr/bin/env python3
"""对照 epub 目录与参考目录（每行一个章节名）：报告缺漏、多余和顺序。

    check_toc.py BOOK.epub REF.txt [--allow-missing 插图]

全部一致时退出码 0；否则 1。空白差异不算不一致。
"""
import argparse
import html
import re
import sys
import zipfile


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def epub_toc(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith("nav.xhtml"))
        nav = z.read(name).decode()
    toc = nav.split('epub:type="toc"', 1)[1].split("</nav>", 1)[0]
    return [norm(html.unescape(re.sub(r"<[^>]+>", "", t))) for t in re.findall(r"<a [^>]*>(.*?)</a>", toc, re.S)]


def compare(ref, got, allow_missing=()):
    ref, got = [norm(x) for x in ref], [norm(x) for x in got]
    missing = [x for x in ref if x not in got and x not in allow_missing]
    extra = [x for x in got if x not in ref]
    in_order = [x for x in ref if x in got] == [x for x in got if x in ref]
    return missing, extra, in_order


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("epub")
    p.add_argument("ref")
    p.add_argument("--allow-missing", nargs="*", default=[])
    a = p.parse_args(argv)
    ref = [l for l in open(a.ref, encoding="utf-8").read().splitlines() if l.strip()]
    got = epub_toc(a.epub)
    missing, extra, in_order = compare(ref, got, a.allow_missing)
    print(f"{a.epub}: ref {len(ref)} / epub {len(got)} / in order: {in_order}")
    if missing:
        print("  missing:", missing)
    if extra:
        print("  extra:", extra)
    sys.exit(0 if in_order and not missing and not extra else 1)


if __name__ == "__main__":
    main()
