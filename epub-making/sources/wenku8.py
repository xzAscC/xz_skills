#!/usr/bin/env python3
"""解析轻小说文库的目录页（novel/<x>/<aid>/index.htm，可以是浏览器另存的 html），输出：

    OUT/volumes.tsv   卷名 \t vid \t txt 下载地址 \t 插图页地址（没有就空）
    OUT/toc/<卷名>.txt 该卷的参考目录，每行一个章节名（给 check_toc.py 用）

    wenku8.py index.html OUT [--aid 3057]
"""
import argparse
import pathlib
import re
from html.parser import HTMLParser

TXT_URL = "https://dl.wenku8.com/packtxt.php?aid={aid}&vid={vid}&charset=gbk"


class _Toc(HTMLParser):
    # 目录表：td.vcss 是卷名（带 vid 属性），td.ccss 里的 <a> 是章节
    def __init__(self):
        super().__init__()
        self.vols, self.cls, self.href, self.buf = [], None, None, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td":
            self.cls, self.buf, self.href = a.get("class"), "", None
            if self.cls == "vcss":
                self.vols.append({"name": "", "vid": a.get("vid", ""), "chapters": [], "illus": ""})
        elif tag == "a" and self.cls == "ccss":
            self.href = a.get("href")

    def handle_data(self, data):
        if self.cls:
            self.buf += data

    def handle_endtag(self, tag):
        if tag != "td" or not self.cls:
            return
        text = self.buf.strip()
        if self.cls == "vcss":
            self.vols[-1]["name"] = text
        elif self.cls == "ccss" and text and self.vols:
            self.vols[-1]["chapters"].append(text)
            if text == "插图":
                self.vols[-1]["illus"] = self.href or ""
        self.cls = None


def parse(text):
    p = _Toc()
    p.feed(text)
    return p.vols


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("index")
    p.add_argument("out")
    p.add_argument("--aid", help="默认从页面里的 /novel/<x>/<aid>/ 链接推断")
    a = p.parse_args(argv)
    raw = pathlib.Path(a.index).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    aid = a.aid or re.search(r"/novel/\d+/(\d+)/", text).group(1)
    out = pathlib.Path(a.out)
    (out / "toc").mkdir(parents=True, exist_ok=True)
    rows = []
    for v in parse(text):
        (out / "toc" / f"{v['name']}.txt").write_text("\n".join(v["chapters"]) + "\n", encoding="utf-8")
        rows.append("\t".join([v["name"], v["vid"], TXT_URL.format(aid=aid, vid=v["vid"]), v["illus"]]))
        print(f"{v['name']}\tvid={v['vid']}\t{len(v['chapters'])} chapters\tillus={'yes' if v['illus'] else 'no'}")
    (out / "volumes.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
