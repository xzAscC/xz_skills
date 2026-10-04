#!/usr/bin/env python3
"""礼貌下载：单线程、同站请求间隔 ≥2s、本地已有就跳过、失败退避重试、连续失败就停。

下载 URL 列表（每行一个）到目录，文件按 001.jpg、002.jpg… 编号：
    fetch.py --urls urls.txt -d img/1
先抓一个页面、用正则提取 URL，再下载（页面会存成 DIR/urls.txt，重跑不再请求页面）：
    fetch.py --page URL --match 'https://pic[^"]+\\.jpg' -d img/1 [--encoding gb18030]
下载单个文件到指定路径：
    fetch.py --one URL -o 1.txt
"""
import argparse
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0"
_last = [0.0]


def get(url, delay=2.0, referer=None, retries=2, backoff=10.0):
    """请求一个 URL；两次请求之间至少隔 delay 秒；429/503 按 Retry-After 退避。"""
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    for attempt in range(retries + 1):
        wait = _last[0] + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                pause = float(e.headers.get("Retry-After") or backoff * (attempt + 1))
            elif e.code in (401, 403, 404):
                raise  # 要登录或不存在：重试没用，交给人处理
            else:
                pause = backoff * (attempt + 1)
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            pause, err = backoff * (attempt + 1), e
        if attempt < retries:
            print(f"  retry in {pause:.0f}s: {url} ({err})", file=sys.stderr, flush=True)
            time.sleep(pause)
    raise err


def download_all(urls, folder, delay=2.0, referer=None, max_fail=3):
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    todo = []
    for i, u in enumerate(urls, 1):
        f = folder / f"{i:03d}{pathlib.Path(u.split('?')[0]).suffix or '.bin'}"
        if not (f.exists() and f.stat().st_size):
            todo.append((u, f))
    print(f"{folder}: {len(urls)} urls, {len(todo)} to fetch, ~{len(todo) * delay / 60:.1f} min", flush=True)
    fails = 0
    for u, f in todo:
        try:
            f.write_bytes(get(u, delay, referer))
            fails = 0
        except Exception as e:
            fails += 1
            print(f"  failed: {u} ({e})", file=sys.stderr, flush=True)
            if fails >= max_fail:
                sys.exit(f"{max_fail} failures in a row; stopping. Check the site before retrying.")
    return len(todo)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--urls")
    g.add_argument("--page")
    g.add_argument("--one")
    p.add_argument("--match", help="与 --page 一起用：提取 URL 的正则")
    p.add_argument("-d", "--dir")
    p.add_argument("-o", "--out")
    p.add_argument("--encoding", default="utf-8")
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--referer")
    a = p.parse_args(argv)
    if a.delay < 2:
        sys.exit("--delay must be at least 2 seconds")

    if a.one:
        out = pathlib.Path(a.out or pathlib.Path(a.one.split("?")[0]).name)
        if out.exists() and out.stat().st_size:
            print(f"{out}: exists, skipped")
        else:
            out.write_bytes(get(a.one, a.delay, a.referer))
            print(f"{out}: {out.stat().st_size} bytes")
        return
    if not a.dir:
        sys.exit("-d is required")
    if a.urls:
        urls = pathlib.Path(a.urls).read_text().split()
    else:
        if not a.match:
            sys.exit("--page needs --match")
        cache = pathlib.Path(a.dir) / "urls.txt"
        if cache.exists() and cache.read_text().strip():
            urls = cache.read_text().split()
        else:
            # 被限流时站点常返回 200 的空页面：没匹配到就退避后再试，最多 3 次
            for attempt in range(3):
                text = get(a.page, a.delay, a.referer).decode(a.encoding, "replace")
                urls = list(dict.fromkeys(re.findall(a.match, text)))
                if urls:
                    break
                time.sleep(10 * (attempt + 1))
            else:
                sys.exit(f"no url matched {a.match!r} on {a.page}")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("\n".join(urls) + "\n")
    download_all(urls, a.dir, a.delay, a.referer)


if __name__ == "__main__":
    main()
