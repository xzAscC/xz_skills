# 轻小说文库（wenku8）

## 拿目录

让用户在浏览器里打开 `https://www.wenku8.net/novel/<x>/<aid>/index.htm` 并另存为 html（或直接给 URL，用 `fetch.py --one` 下载）。然后：

```bash
python3 ~/xz_skills/epub-making/sources/wenku8.py index.html work/
```

得到 `work/volumes.tsv`（卷名、vid、txt 地址、插图页地址）和 `work/toc/<卷名>.txt`（参考目录）。

## 下载 txt

`packshow.php` 下载页要登录，不用它。txt 的直链只需要目录页里公开的 `aid` 和 `vid`：

```
https://dl.wenku8.com/packtxt.php?aid=<aid>&vid=<vid>&charset=gbk
```

第一次用时，先下一卷，和用户手里已有的同一卷 `cmp` 一下，一致再批量下载。每卷用 `fetch.py --one URL -o <卷>.txt`，它自带 2 秒间隔。

## txt 格式

- GBK 编码，CRLF。
- 第 1 行和最后两行是网站广告（含 `wenku8`、`轻小说文库`）和 `◆◇` 分隔线。
- 章节标题行：两个空格 + 卷名 + 空格 + 章节名，如 `  第一卷 序`。正文缩进四个空格。
- 卷名前缀不一定是「第X卷」：番外是 `第8.5卷`，短篇集是 `SSS短篇集`。`--vol` 用 `volumes.tsv` 里的卷名。
- 「插图」节在 txt 里是空的，图片只在网页上。位置不固定：有的在卷末，有的在特典之前。

## 插图与封面

- 插图页就是目录里名为「插图」的章节页面。图片地址形如 `https://pic.<域名>/3/<aid>/<章节id>/<图片id>.jpg`：
  ```bash
  python3 fetch.py --page <插图页> --match 'https://pic[^"]+\.(?:jpg|jpeg|png|webp)' \
      --encoding gb18030 --referer https://www.wenku8.net/ -d img/<卷>
  ```
- **每张图列了两次**（md5 相同）；`build.py --illus` 会按内容去重。黑白图是正文插画，和彩页是不同的图，不是副本，要保留。
- 第一张是封面相关的图：有的卷是竖版封面，直接用；有的卷是**书衣展开图**（折口 | 封面 | 书脊 | 封底 | 折口），用 `cover.py` 裁出封面（台版直排，封面在书脊左边，`--side left`）。
- 去掉书腰的变体封面（同一张插画，书名在底部）不是正式封面，不要拿来当封面。
- 一个插图页约 40 张、两次请求间隔 2 秒，下载一卷要 1–2 分钟；整套书先报总数和耗时。
- 请求偶尔会返回空页面（被限流），`fetch.py` 会重试；不要缩短间隔。
