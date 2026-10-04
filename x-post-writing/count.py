#!/usr/bin/env python3
"""Weighted X (Twitter) length for each post, following twitter-text v3.

Usage: count.py [FILE] [--limit N]   (reads stdin without FILE)

Posts are split on lines like "1/", "2/". Without such lines the whole
text is one post. Rules: CJK and most non-Latin chars count 2, an emoji
sequence counts 2, any URL counts 23, everything else counts 1.
"""

import argparse
import re
import sys

URL_WEIGHT = 23
# Bare domains only for common TLDs, so "Node.js" is not taken as a URL.
URL_RE = re.compile(
    r"(?:https?://\S+|www\.\S+"
    r"|\b(?:[\w-]+\.)+(?:com|org|net|io|dev|ai|me|co|cn|app|xyz|edu|gov)(?:/\S*)?)",
    re.IGNORECASE)
# twitter-text "light" ranges that weigh 1; all other code points weigh 2.
LIGHT = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]
SPLIT_RE = re.compile(r"^\s*\d+/\s*$", re.MULTILINE)


def is_emoji(cp):
    return cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF


def char_weight(cp):
    return 1 if any(lo <= cp <= hi for lo, hi in LIGHT) else 2


def text_weight(text):
    total, i = 0, 0
    while i < len(text):
        cp = ord(text[i])
        i += 1
        if not is_emoji(cp):
            total += char_weight(cp)
            continue
        # One emoji sequence: modifiers, VS16, and ZWJ-joined parts count once.
        while i < len(text):
            nxt = ord(text[i])
            if nxt == 0xFE0F or 0x1F3FB <= nxt <= 0x1F3FF:
                i += 1
            elif nxt == 0x200D and i + 1 < len(text):
                i += 2
            else:
                break
        total += 2
    return total


def weight(post):
    post = post.strip()
    total, last = 0, 0
    for m in URL_RE.finditer(post):
        url = m.group().rstrip(".,!?;:)\"'")
        total += text_weight(post[last:m.start()]) + URL_WEIGHT
        last = m.start() + len(url)
    return total + text_weight(post[last:])


def split_posts(text):
    parts = [p for p in SPLIT_RE.split(text) if p.strip()]
    return parts if SPLIT_RE.search(text) else [text]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--limit", type=int, default=280)
    args = ap.parse_args(argv)
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    over = 0
    for n, post in enumerate(split_posts(text), 1):
        w = weight(post)
        flag = "OVER" if w > args.limit else "ok"
        over += w > args.limit
        print(f"{n}/ {w:>4} / {args.limit}  {flag}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
