---
name: epub-making
description: "Turn web-novel txt files (GBK or UTF-8) into valid per-volume EPUB 3 books with pandoc: polite downloading, chapter splitting, cleanup, series metadata, cover cropped from a jacket spread, illustrations, epubcheck, and a TOC check against the source site. Use when the user wants to 做 epub, 制作电子书, turn a txt novel or 轻小说 into EPUB, download volumes from a site like 轻小说文库/wenku8, add covers or 插图 to an epub, or run epubcheck."
---

# 制作 EPUB

把网上的小说 txt 做成合规的 EPUB 3：一卷一本、目录正确、带系列信息、封面和插图齐全、epubcheck 0 错误。脚本都在本目录：

| 脚本 | 用途 |
| --- | --- |
| `build.py` | txt → EPUB（切章节、清理、元数据、封面、插图），生成后自动跑 epubcheck |
| `fetch.py` | 礼貌下载（见下文规则） |
| `check_toc.py` | epub 目录和参考目录逐条对照 |
| `cover.py` | 从书衣展开图裁出封面，出预览图 |
| `restyle.py` | 给已有的 epub 换样式：嵌入子集字体、套默认样式和书的主题、清理空段落、补章节标题 |
| `sources/<站点>.md` / `.py` | 站点特例。已有：[wenku8](sources/wenku8.md) |

依赖：`pandoc`、`epubcheck`（Arch：`pacman -S epubcheck`）、Python 的 `numpy` 和 `Pillow`（只有 `cover.py` 用）。

## 礼貌下载（必须遵守）

- 单线程；同一站点两次请求至少隔 **2 秒**。`fetch.py` 不接受更短的间隔。
- 本地已有的文件不再请求；页面上解析出的 URL 列表也缓存（`urls.txt`）。
- 遇到 429/503 按 `Retry-After` 退避；连续 3 次失败就停下，报告给用户，不要换个方式硬冲。
- 批量下载前先告诉用户：要请求多少次、大约多久。长下载放后台。
- 不绕过登录、付费墙、验证码。用页面上公开的地址拼直链可以；连目录都要登录时，停下来问用户。
- 写临时脚本下载时同样遵守这些规则（直接 `import fetch` 用 `fetch.get`）。

## 流程

1. **拿到源文件和参考目录**。按站点看 `sources/`。没有站点目录时，让用户给一个（截图、网页都行）。
2. **查编码和切分规则**。`file` 看编码；GBK 一律按 GB18030 解（`build.py` 自动处理）。先跑
   `build.py X.txt --vol <卷名前缀> --list`，把识别出的章节和段落数给用户看。番外、短篇集的前缀常常不同（如 `第8.5卷`、`SSS短篇集`），逐卷确认。
3. **清理规则**。默认删掉含站点名的广告行和 `◆◇` 分隔线；正文里的 `***`、`———` 是场景分隔，要保留。没有正文的节会被删掉，`build.py` 会列出删了哪些——核对一下是不是只有「插图」这类空节。
4. **封面和插图**（可选，用户说以后再做就跳过，在日记里记 TODO）。
   - 插图目录里的图片按文件名排序、按内容去重，填进名为「插图」的空节，放回原目录位置。
   - 封面默认用插图的第一张。竖图直接用；横图是书衣展开图，用 `cover.py` 裁。**裁完把预览图拼成一张给用户看，确认后再写进 epub。**
5. **生成**。一卷一本，命令见下。系列名用官方译名；系列序号按站点目录顺序，番外用小数（7.5、8.5）。`build.py` 同时写 EPUB 3 的 `belongs-to-collection` 和 `calibre:series`，Calibre、KOReader 都能认出系列。
6. **校验**。每本 epubcheck 必须 0 错误（`build.py` 已自动跑）；再用 `check_toc.py` 和参考目录对照，不一致的逐条解释给用户。
7. **收尾**。不要覆盖用户可能改过的旧文件（大小、修改时间变了就先问）。按下文放进 JD，勾掉日记里的任务。

```bash
S=~/xz_skills/epub-making
python3 $S/build.py 1.txt --vol 第一卷 -o "书名1 (作者).epub" --title 书名1 \
    --author 作者 --illustrator 画师 --series 书名 --pos 1 \
    --cover cover1.jpg --illus img/1 --subject 轻小说 --description "来源与译本说明"
python3 $S/check_toc.py "书名1 (作者).epub" work/toc/第一卷.txt
python3 $S/cover.py img/2/001.jpg -o cover2.jpg --preview cover2-preview.jpg
```

中间文件（txt、图片、预览）放 scratchpad，不放进 JD。

## 样式

目标阅读器是 Arch 上的 calibre ebook-viewer（Chromium 内核，CSS 支持完整），不为 Kindle 妥协。

**依据**：按书的 `dc:language` 选规则。中文书（简体、繁体）按 W3C《中文排版需求》（clreq，https://www.w3.org/TR/clreq/）。英文书按 Standard Ebooks 的 Manual of Style（https://standardebooks.org/manual），它的结构写法两种语言都参考。CSS 文件头注明采用了哪些条目。

**分两层**：
- 默认样式：轻松的轻小说风格，所有书都用。管正文排版：字体、行距、缩进、标题、插图。
- 书的主题（可选）：每个系列可以单独建一个，放在 `themes/<系列名>/`。只覆盖字体、配色和装饰（书边、章首、场景分隔的纹样），装饰贴合这本书的题材。

**排版规则（两种语言通用）**：
- 段间不留空，靠首行缩进分段。
- 留白用 CSS margin，不用空段落（`<p>　</p>`、`<p>&nbsp;</p>`）占位。
- 每章开头要有页面上看得见的标题元素，不能只写在 `<title>` 里。
- 场景分隔用 `<hr/>` 加样式，不用 `***` 之类的文字。
- 正文字体嵌进 epub，只用 OFL 等允许嵌入的开源字体，按全书用到的字做子集；不依赖系统装了什么字体。
- 装饰用 SVG（矢量，体积小，深浅色都清楚），不能挡住正文，也不能挤占行宽。

**中文**：首行缩进 2em，每一段都缩进；两端对齐；不断词。繁体书的标点位置按 clreq 里繁体的规定。

**英文**：首行缩进 1em；标题和场景分隔后的第一段不缩进（Standard Ebooks 的做法）；两端对齐，同时开连字符断词（`hyphens: auto`，要求 `xml:lang="en"` 写对）。出版社排好版的书（如 31.08 里的学术书），先问用户要不要动。

**calibre ebook-viewer 的限制**（读 `/usr/share/calibre/viewer.js` 得知，主题要绕开）：
- `html`、`body` 的背景色被设成透明，文字颜色被设成阅读器配色。所以底色用 `background-image` 铺一层，文字颜色加 `!important`。
- 翻页模式下 `body` 的 margin、padding 被锁成 0。要给正文留边，就加在 `body > *` 上，再配 `box-decoration-break: clone`。
- 阅读器会按配色设置 `color-scheme`，所以用 `prefers-color-scheme` 区分浅色和深色；两种都要截图检查。
- `background-attachment: fixed` 的背景每一页都会画，书边装饰就靠它。

字体缓存在 `~/.cache/epub-making/fonts/`（霞鹜文楷 Regular/Medium，https://github.com/lxgw/LxgwWenKai/releases ）。

**改已有的 epub**：
0. 尊重原书已有的排版。先跑 `restyle.py X.epub --report`，再在 ebook-viewer 里截一张原书的图。只要原书排过版（样式表规则多、嵌了字体、标题有颜色或图片、段落有自己的间距，如多看格式的网文），就先把原书截图给用户看，讨论保留哪些、改哪些，用户同意后再改；必要时给这本书单独建主题，在主题里保留原来的做法。只有没怎么排版的书才直接套种类样式。
1. 先把原书复制到 scratchpad，只改副本；原文件在用户确认之前不动。
2. 选一章做 2–3 个版本，用 ebook-viewer 截图，拼在一起给用户选。窗口不要开在用户的主屏（3440 宽屏）上：Hyprland 下先用 `hyprctl eval` 加一条临时 window rule，把 `calibre-ebook-viewer` 放到左屏的 11 号工作区；用 `--open-at 'search:正文片段'` 跳到要看的页，`grim -g` 截窗口，截完关掉窗口、停用这条 rule。
3. 定稿后再批量改，每本都跑 epubcheck，抽查截图。
4. 用户确认后，才替换 JD 里的原文件。默认样式定稿后要写回 `style.css`，书的主题写进 `themes/`。

## 放进 JD

- 位置：`~/JD/31 Books/31.01 TODO/31.01.NN <系列名>/`。**一个系列一个目录**，各卷 epub 都放在里面，不要每卷再建子目录。
- 文件名：`<书名> (<作者>).epub`，如 `败犬女主太多了！1 (雨森焚火).epub`。
- 目录里写一个 `README.md`：书名、作者、译本、来源链接、卷数、封面插图状态。在 `31.01 TODO/README.md` 加一行索引。
- `*.epub` 走 Git LFS（JD 的 `.gitattributes` 已配置）。按 JD 的 `Agents.md` 提交。

## 放进 Kindle（USB）

Kindle 不读 USB 拷进去的 EPUB（只有 Send to Kindle 会在云端转换），USB 要先转 AZW3。

1. 先列出设备上已有的书给用户看（`documents/`，购买的书在 `documents/Downloads/`），删什么由用户定。购买的书删掉的只是下载副本，可从云端重下。
2. 转 AZW3，并把 ASIN 固定成 epub 的 UUID（重拷新版时阅读进度不丢）。calibre 会先塞一个随机 uuid，`ebook-meta --identifier` 改不动 AZW3 的 ASIN，要在转换时用 `--read-metadata-from-opf` 指定：
   ```bash
   # m.opf 里只放 <dc:identifier opf:scheme="uuid" id="uuid_id">UUID</dc:identifier>（再加 subject/description，否则会丢）
   ebook-convert book.epub book.azw3 --read-metadata-from-opf m.opf
   ebook-meta book.azw3 | grep Identifiers   # 应为 mobi-asin:UUID
   ```
3. 一个系列一个文件夹：`documents/<系列名>/`。
4. 封面缩略图：联网后 Kindle 会去亚马逊找侧载书的封面，找不到就变空白。预先放 `system/thumbnails/thumbnail_<ASIN>_EBOK_portrait.jpg`（`ebook-meta --get-cover` 取出，缩到高 330）。
5. 只删用户数据和别的系统留下的垃圾（`.Spotlight-V100`、`.fseventsd`、`System Volume Information`、`._*`、`*.calibre`、`amazon-cover-bug`）；`system/`、`audible/`、`voice/`、`fonts/` 等固件目录不动。
6. `udisksctl unmount -b /dev/sdX && udisksctl power-off -b /dev/sdX` 安全弹出，Kindle 才会开始索引。
7. 设备显示 0 字节时，是 Kindle 没进 USB 驱动器模式：唤醒或重插。

## 常见坑

- 用 HTML 作为 pandoc 的输入，不要用 Markdown：正文里的 `*`、`>`、`1.` 会被当成格式。
- pandoc 报 `Could not load translations for zh-CN` 是无害警告，`build.py` 已过滤。
- 图片站点常把同一张图列两次；只按文件名去重不够，要按内容。去重只删完全相同的文件；同一张图有彩色和黑白两个版本时，删黑白的、留彩色的。正文的黑白插画不是副本，不要删。
- 合并成一本还是一卷一本：默认一卷一本（阅读器按卷记进度、书架按系列排序），用户要合订本时再合。
