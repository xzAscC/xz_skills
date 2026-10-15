#!/usr/bin/env python3
"""给已有的 EPUB 换样式：嵌入子集字体，套基础样式、种类样式和书的主题，清理空段落，补章节标题。

    restyle.py in.epub -o out.epub [--category 31.19] [--theme themes/狼与香辛料]

样式按 基础（style.css）→ 种类（categories/31.NN.css）→ 主题（themes/…/theme.css）叠加。
种类默认从输入文件的路径里找 JD 编号（如「31.19 Fantasy」）。
原书的样式表保留，新样式表 restyle/restyle.css 链接在最后，同名规则覆盖原样式。
新加的文件都放在 OPF 旁的 restyle/ 目录里，重复运行会先删掉旧的。
"""
import argparse
import io
import pathlib
import posixpath
import re
import string
import sys
import zipfile

from fontTools import subset

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from build import epubcheck  # noqa: E402

HERE = pathlib.Path(__file__).parent
STYLE = HERE / "style.css"
CATEGORIES = HERE / "categories"
CACHE = pathlib.Path.home() / ".cache/epub-making/fonts"
HAN_SERIF = pathlib.Path("/usr/share/fonts/adobe-source-han-serif")
# CSS 里的字体名 → {字重: 字体文件}。都是 OFL 授权，允许嵌入。
FONTS = {
    "Book Serif": {400: HAN_SERIF / "SourceHanSerifCN-Regular.otf", 700: HAN_SERIF / "SourceHanSerifCN-Bold.otf"},
    "Book Kai": {400: CACHE / "LXGWWenKai-Regular.ttf", 700: CACHE / "LXGWWenKai-Medium.ttf"},
}
DIR = "restyle"
# 空段落；带 id 的不算，它们可能是目录链接的落点
EMPTY = r'<p(?![^>]*\sid=)[^>]*>(?:\s|　|&nbsp;|&#160;|\xa0)*</p>'
ASSET_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}


def clean(doc):
    # 夹在两个空段落之间的短段落是短篇集里的小标题（如「少年、少女与白花」）
    doc = re.sub(EMPTY + r'\s*<p>(?![\s　]*</p>)([^<。！？”]{1,20})</p>\s*' + EMPTY,
                 r'<h4 class="subtitle">\1</h4>', doc)
    # 其余空段落只是占位，删掉；连同它前面的空白，避免留下空行
    new = re.sub(r'\s*' + EMPTY, '', doc)
    # 整页只有空段落时（留白页）保持原样：XHTML 的 body 不能为空
    return doc if re.search(r'<body[^>]*>\s*</body>', new) else new


def chapter_titles(docs):
    """有的书把章节名只写在章首插图的 <hN title="…"><img/></hN> 里，正文页没有标题。
    把这个名字补成正文页开头的 <h3 class="chapter">。"""
    pending = None
    for name, doc in docs:
        body = doc.split("<body", 1)[-1]
        m = re.search(r'<h\d[^>]*title="([^"]+)"[^>]*>\s*<img', body)
        has_text = re.search(r'<p[^>]*>[^<\s]', body)
        if m and not has_text:
            pending = m.group(1)
        elif re.search(r'<h[1-3][^>]*>[^<\s]', body):  # h4 是短篇里的小标题，不算章节标题
            pending = None
        elif pending and has_text:
            yield name, re.sub(r'(<body[^>]*>)', rf'\1\n  <h3 class="chapter">{pending}</h3>', doc, count=1)
            pending = None


def category_of(path, given):
    if given:
        return given
    m = re.search(r'(?:^|/)(31\.\d\d) ', str(pathlib.Path(path).resolve()))
    return m and m.group(1)


def used_fonts(css):
    """--body-font、--heading-font 各取最后一次赋值（后面的层覆盖前面的），返回用到的字体名。"""
    names = set()
    for var in ("--body-font", "--heading-font"):
        values = re.findall(rf'{var}:\s*"([^"]+)"', css)
        if values:
            names.add(values[-1])
    return [n for n in FONTS if n in names]


def make_subset(src, text):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]  # 保留竖排、标点挤压等 OpenType 特性
    font = subset.load_font(str(src), opts)
    s = subset.Subsetter(opts)
    s.populate(text=text)
    s.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def original_styling(files):
    """原书自己的排版：样式表、规则数、嵌入字体。规则多或嵌了字体，说明排过版，改之前要先和用户讨论。"""
    css = [n for n in files if n.endswith(".css")]
    rules = sum(files[n].decode("utf-8", "replace").count("{") for n in css)
    fonts = [posixpath.basename(n) for n in files if n.lower().endswith((".ttf", ".otf", ".woff", ".woff2"))]
    return f"{len(css)} stylesheets, {rules} rules, embedded fonts: {', '.join(fonts) or 'none'}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("-o", "--out")
    p.add_argument("--report", action="store_true", help="只报告原书已有的排版，不生成文件")
    p.add_argument("--category", help="JD 种类编号，如 31.19；默认从输入路径里找")
    p.add_argument("--theme", help="书的主题目录：theme.css 和它用到的 SVG/PNG")
    a = p.parse_args(argv)
    if a.report:
        z = zipfile.ZipFile(a.src)
        files = {n: z.read(n) for n in z.namelist() if f"/{DIR}/" not in n}
        print(f"{pathlib.Path(a.src).name}: {original_styling(files)}")
        return
    if not a.out:
        sys.exit("-o is required unless --report")
    out = pathlib.Path(a.out).resolve()
    if out == pathlib.Path(a.src).resolve():
        sys.exit("refusing to overwrite the source; write to a copy")

    # 样式叠加：基础 → 种类 → 主题；装饰图片按同样的顺序找，后面的层优先
    layers = [STYLE]
    category = category_of(a.src, a.category)
    if category:
        layers.append(CATEGORIES / f"{category}.css")
    if a.theme:
        layers.append(pathlib.Path(a.theme) / "theme.css")
    for f in layers:
        if not f.exists():
            sys.exit(f"missing style: {f}")
    css = "\n".join(f.read_text(encoding="utf-8") for f in layers)

    zin = zipfile.ZipFile(a.src)
    files = {i.filename: zin.read(i) for i in zin.infolist()}
    opf_name = re.search(rb'full-path="([^"]+)"', files["META-INF/container.xml"]).group(1).decode()
    root = posixpath.dirname(opf_name)
    opf = files[opf_name].decode()

    # 删掉上次运行留下的 restyle/ 文件和清单项
    files = {n: d for n, d in files.items() if not n.startswith(posixpath.join(root, DIR) + "/")}
    opf = re.sub(rf'\s*<item [^>]*href="{DIR}/[^"]*"[^>]*/>', "", opf)

    # 按书脊顺序处理正文
    items = dict(re.findall(r'<item [^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf))
    items.update({i: h for h, i in re.findall(r'<item [^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf)})
    spine = [posixpath.join(root, items[i]) for i in re.findall(r'<itemref [^>]*idref="([^"]+)"', opf)]
    docs = {n: clean(files[n].decode()) for n in spine}
    titled = dict(chapter_titles((n, docs[n]) for n in spine))
    docs.update(titled)
    for n, doc in docs.items():
        href = posixpath.relpath(posixpath.join(root, DIR, "restyle.css"), posixpath.dirname(n))
        doc = re.sub(r'\s*<link [^>]*restyle\.css[^>]*/>', "", doc)
        doc = doc.replace("</head>", f'  <link href="{href}" rel="stylesheet" type="text/css" />\n</head>', 1)
        files[n] = doc.encode()

    # 字体子集：全书正文、目录用到的字，加上 ASCII 和常用标点
    text = "".join(re.sub(r"<[^>]+>", "", d.decode()) for n, d in files.items()
                   if n.endswith((".html", ".xhtml", ".ncx")))
    text += string.printable + "，。、；：？！“”‘’（）《》〈〉【】「」『』…—·　◆◇■❀"
    new, faces = {}, []
    for family in used_fonts(css):
        for weight, src in FONTS[family].items():
            name = f"{family.split()[-1].lower()}-{weight}.woff2"
            new[name] = make_subset(src, text)
            faces.append(f'@font-face {{ font-family: "{family}"; font-weight: {weight}; '
                         f'src: url({name}) format("woff2"); }}')
    # 装饰图片：只复制 CSS 里引用到的
    for ref in sorted(set(re.findall(r'url\(([^)"\']+\.(?:svg|png|jpg))\)', css))):
        found = [d / ref for d in (f.parent for f in reversed(layers)) if (d / ref).exists()]
        if not found:
            sys.exit(f"missing asset: {ref}")
        new[ref] = found[0].read_bytes()
    new["restyle.css"] = ("\n".join(faces) + "\n" + css).encode()

    manifest = []
    for i, (name, data) in enumerate(new.items()):
        files[posixpath.join(root, DIR, name)] = data
        ext = pathlib.Path(name).suffix
        mt = {".css": "text/css", ".woff2": "font/woff2"}.get(ext) or ASSET_TYPES[ext]
        manifest.append(f'    <item id="restyle-{i}" href="{DIR}/{name}" media-type="{mt}"/>')
    opf = opf.replace("</manifest>", "\n".join(manifest) + "\n  </manifest>", 1)
    files[opf_name] = opf.encode()

    # mimetype 必须第一个且不压缩
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), files.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        for n, d in files.items():
            z.writestr(n, d)
    size = sum(len(v) for k, v in new.items() if k.endswith(".woff2"))
    print(f"{out.name}: category {category or '-'}, fonts {used_fonts(css)} {size / 1e6:.1f} MB, "
          f"chapter titles added: {len(titled)}")
    if not epubcheck(out):
        sys.exit(1)


if __name__ == "__main__":
    main()
