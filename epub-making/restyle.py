#!/usr/bin/env python3
"""给已有的 EPUB 换样式：嵌入子集字体，套基础样式、种类样式和书的主题，清理空段落，补章节标题。

    restyle.py in.epub -o out.epub [--category 31.19] [--theme themes/狼与香辛料] [--strip-inline]

样式按 基础（style.css）→ 种类（categories/31.NN.css）→ 主题（themes/…/theme.css）叠加。
种类默认从输入文件的路径里找 JD 编号（如「31.19 Fantasy」）。
原书的样式表保留，新样式表 restyle/restyle.css 链接在最后，同名规则覆盖原样式。
新加的文件都放在 OPF 旁的 restyle/ 目录里，重复运行会先删掉旧的。
--strip-inline 用于把排版写在内联 style 里的书（如得到 APP 转制的），见 strip_inline()。
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
from lxml import etree

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
    # 朱雀仿宋 v0.212（https://github.com/TrionesType/zhuque ，预览版，只有常规体）
    "Book Fangsong": {400: CACHE / "ZhuqueFangsong-Regular.ttf"},
}
DIR = "restyle"
# 空段落；带 id 的不算，它们可能是目录链接的落点
EMPTY = r'<p(?![^>]*\sid=)[^>]*>(?:\s|　|&nbsp;|&#160;|\xa0)*</p>'
ASSET_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg"}
H = "{http://www.w3.org/1999/xhtml}"
EPUB_TYPE = "{http://www.idpf.org/2007/ops}type"
HEADINGS = {H + f"h{i}" for i in range(1, 7)}
BLOCKS = HEADINGS | {H + t for t in ("p", "div", "li", "blockquote")}
VOID = {H + t for t in ("img", "br", "hr", "meta", "link", "col", "wbr", "source")}
BODY_PX = 16  # 得到的正文字号；比它小的算小字


def inline_style(el):
    """style 属性拆成 {属性: 值}，值去掉引号。"""
    pairs = (d.split(":", 1) for d in el.get("style", "").split(";") if ":" in d)
    return {k.strip().lower(): v.strip().strip("'\"") for k, v in pairs}


def append_text(el, text):
    """把文字接在 el 的内容末尾。"""
    if not text:
        return
    if len(el):
        el[-1].tail = (el[-1].tail or "") + text
    else:
        el.text = (el.text or "") + text


def only_children(el, tag):
    """el 的内容是否全包在 tag 元素里（如逐字的 <b>作</b><b>者</b>）。"""
    return (len(el) and not (el.text or "").strip()
            and all(c.tag == tag and not (c.tail or "").strip() for c in el))


def strip_inline(doc):
    """得到 APP 转制的书把排版全写在 span 的 style 里：写死的 px 字号让阅读器调不动字号，
    苹方、方正仿宋、方正楷体又多半没装。这里换成 restyle.css 的 class（rs- 开头，免得和原书的撞名）：
    仿宋 → rs-quote（引文），楷体靠右 → rs-sign（落款），居中 → rs-center，比正文小 → rs-small；
    粗体、斜体用 b、i，逐字包的 <b>作</b><b>者</b> 合成一个。class 能放到段落上就放到段落上。
    脚注（aside）挪到引用它的段落后面。认不出的样式原样留下，并打印出来。"""
    root = etree.fromstring(doc.encode())
    for el in reversed(list(root.iter(H + "span", H + "div"))):  # 先里后外
        if "style" not in el.attrib:
            continue
        s = inline_style(el)
        del el.attrib["style"]
        family, align = s.pop("font-family", ""), s.pop("text-align", "")
        size = re.fullmatch(r"([\d.]+)px", s.pop("font-size", ""))
        small = size and float(size[1]) < BODY_PX
        s.pop("display", None)
        if s.get("color", "").replace(" ", "") in ("rgb(0,0,0)", "#000", "#000000") or small:
            s.pop("color", None)  # 黑字跟阅读器配色；小字用强调色
        cls = []
        if "FangSong" in family:
            cls.append("rs-quote")
        if "Kai" in family and align == "right":
            cls.append("rs-sign")
        elif align == "center":
            cls.append("rs-center")
        elif align:
            s["text-align"] = align
        if small:
            cls.append("rs-small")
        for prop, tag, values in (("font-weight", "b", ("bold", "700")), ("font-style", "i", ("italic", "oblique"))):
            if s.get(prop) in values:
                del s[prop]
                if not only_children(el, H + tag):
                    b = etree.Element(H + tag)
                    b.text, el.text = el.text, None
                    b.extend(list(el))
                    el.append(b)
        if s:
            el.set("style", ";".join(f"{k}:{v}" for k, v in s.items()))
            print(f"strip-inline: kept {el.get('style')}", file=sys.stderr)
        parent = el.getparent()
        if parent.tag in HEADINGS and "rs-center" in cls:
            cls.remove("rs-center")  # 标题本来就居中
        if (cls and el.tag == H + "span" and parent.tag in BLOCKS and len(parent) == 1
                and not (parent.text or "").strip() and not (el.tail or "").strip()):
            parent.set("class", " ".join(filter(None, [parent.get("class"), *cls])))
            cls = []
        if cls:
            el.set("class", " ".join(filter(None, [el.get("class"), *cls])))
        if el.tag == H + "span" and not (set(el.attrib) - {"id"}):  # 只剩 id（或什么都没有）的 span 拆掉
            if "id" in el.attrib and "id" not in parent.attrib:
                parent.set("id", el.attrib.pop("id"))
            if "id" not in el.attrib:
                el.tag = "rs-unwrap"
    etree.strip_tags(root, "rs-unwrap")
    for h in root.iter(*HEADINGS):
        etree.strip_tags(h, H + "b")  # 标题本来就是粗体
    for el in list(root.iter(H + "b", H + "i")):
        if el.getparent() is None:  # 已经合进前一个
            continue
        while (nxt := el.getnext()) is not None and nxt.tag == el.tag and not el.tail and not el.attrib and not nxt.attrib:
            append_text(el, nxt.text)
            el.extend(list(nxt))
            el.tail = nxt.tail
            el.getparent().remove(nxt)
    for note in [a for a in root.iter(H + "aside") if a.get(EPUB_TYPE) == "footnote" and a.get("id")]:
        ref = next((a for a in root.iter(H + "a") if a.get("href") == "#" + note.get("id")), None)
        block = ref is not None and next((b for b in ref.iterancestors() if b.tag in BLOCKS), None)
        if block is None or block is False:
            continue
        prev = note.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + (note.tail or "")
        else:
            note.getparent().text = (note.getparent().text or "") + (note.tail or "")
        note.tail = None
        block.addnext(note)
        note.tail = "\n"
        note.set("class", " ".join(filter(None, [note.get("class"), "rs-note"])))
        ref.set("class", " ".join(filter(None, [ref.get("class"), "rs-noteref"])))
        for img in ref.iter(H + "img"):
            img.attrib.pop("width", None)  # 图标跟着字号缩放
    for el in root.iter():
        if el.tag not in VOID and el.text is None and not len(el):
            el.text = ""  # 写成 <div></div>，不写 <div/>：HTML 解析器会把 <div/> 当成开始标签
    return doc[:doc.index("<html")] + etree.tostring(root, encoding="unicode")


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


def class_text(doc, cls):
    """doc 里带 class cls 的元素的字。"""
    root = etree.fromstring(doc.encode())
    return "".join(t for el in root.iter(tag=etree.Element) if cls in (el.get("class") or "").split()
                   for t in el.itertext())


def used_fonts(css, docs=()):
    """用到的字体 → 要覆盖的字（None 是全书）。变量各取最后一次赋值（后面的层覆盖前面的）。
    --body-font、--heading-font 用在全书；--quote-font、--sign-font 只用在 rs-quote、rs-sign
    （--strip-inline 生成）的元素上，书里没有这些元素就不嵌入。"""
    used = {}
    for var, cls in (("--body-font", ""), ("--heading-font", ""), ("--quote-font", "rs-quote"), ("--sign-font", "rs-sign")):
        values = re.findall(rf'{var}:\s*"([^"]+)"', css)
        if not values:
            continue
        if not cls:
            used[values[-1]] = None
        elif used.get(values[-1], "") is not None and (chars := "".join(class_text(d, cls) for d in docs)):
            used[values[-1]] = used.get(values[-1], "") + chars
    return {n: used[n] for n in FONTS if n in used}
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
    """原书自己的排版：样式表、规则数、嵌入字体。规则多或嵌了字体，说明排过版，改之前要先和用户讨论。
    样式表几乎是空的、内联 style 却很多的（得到 APP 转制的书），用 --strip-inline。"""
    css = [n for n in files if n.endswith(".css")]
    rules = sum(files[n].decode("utf-8", "replace").count("{") for n in css)
    fonts = [posixpath.basename(n) for n in files if n.lower().endswith((".ttf", ".otf", ".woff", ".woff2"))]
    inline = sum(files[n].count(b' style="') for n in files if n.endswith((".html", ".xhtml")))
    return (f"{len(css)} stylesheets, {rules} rules, embedded fonts: {', '.join(fonts) or 'none'}, "
            f"inline styles: {inline}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("-o", "--out")
    p.add_argument("--report", action="store_true", help="只报告原书已有的排版，不生成文件")
    p.add_argument("--category", help="JD 种类编号，如 31.19；默认从输入路径里找")
    p.add_argument("--theme", help="书的主题目录：theme.css 和它用到的 SVG/PNG")
    p.add_argument("--strip-inline", action="store_true", help="把内联 style 换成 class（得到 APP 转制的书）")
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
    docs = {n: files[n].decode() for n in spine}
    docs = {n: clean(strip_inline(d) if a.strip_inline else d) for n, d in docs.items()}
    titled = dict(chapter_titles((n, docs[n]) for n in spine))
    docs.update(titled)
    for n, doc in docs.items():
        href = posixpath.relpath(posixpath.join(root, DIR, "restyle.css"), posixpath.dirname(n))
        doc = re.sub(r'\s*<link [^>]*restyle\.css[^>]*/>', "", doc)
        doc = doc.replace("</head>", f'  <link href="{href}" rel="stylesheet" type="text/css" />\n</head>', 1)
        files[n] = doc.encode()

    # 字体子集：全书正文、目录用到的字，加上 ASCII 和常用标点；只用在引文、落款上的字体只取那些字，只嵌常规体
    punct = string.printable + "，。、；：？！“”‘’（）《》〈〉【】「」『』…—·　◆◇■❀"
    text = "".join(re.sub(r"<[^>]+>", "", d.decode()) for n, d in files.items()
                   if n.endswith((".html", ".xhtml", ".ncx"))) + punct
    fonts = used_fonts(css, docs.values())
    new, faces = {}, []
    for family, only in fonts.items():
        for weight, src in FONTS[family].items():
            if only is not None and weight != 400:
                continue
            name = f"{family.split()[-1].lower()}-{weight}.woff2"
            new[name] = make_subset(src, text if only is None else only + punct)
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
    print(f"{out.name}: category {category or '-'}, fonts {list(fonts)} {size / 1e6:.1f} MB, "
          f"chapter titles added: {len(titled)}")
    if not epubcheck(out):
        sys.exit(1)


if __name__ == "__main__":
    main()
