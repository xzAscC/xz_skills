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

## 放进 JD

- 位置：`~/JD/31 Books/31.01 TODO/31.01.NN <系列名>/`。**一个系列一个目录**，各卷 epub 都放在里面，不要每卷再建子目录。
- 文件名：`<书名> (<作者>).epub`，如 `败犬女主太多了！1 (雨森焚火).epub`。
- 目录里写一个 `README.md`：书名、作者、译本、来源链接、卷数、封面插图状态。在 `31.01 TODO/README.md` 加一行索引。
- `*.epub` 走 Git LFS（JD 的 `.gitattributes` 已配置）。按 JD 的 `Agents.md` 提交。

## 常见坑

- 用 HTML 作为 pandoc 的输入，不要用 Markdown：正文里的 `*`、`>`、`1.` 会被当成格式。
- pandoc 报 `Could not load translations for zh-CN` 是无害警告，`build.py` 已过滤。
- 图片站点常把同一张图列两次；只按文件名去重不够，要按内容。
- 合并成一本还是一卷一本：默认一卷一本（阅读器按卷记进度、书架按系列排序），用户要合订本时再合。
