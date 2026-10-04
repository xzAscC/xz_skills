#!/usr/bin/env python3
"""从书衣展开图（折口 | 封面 | 书脊 | 封底 | 折口）里裁出封面，并生成预览给人确认。

    cover.py SPREAD.jpg -o cover.jpg --preview preview.jpg [--ratio 0.68] [--side left] [--x0 N]

竖图（宽 < 高）本身就是封面，原样复制。
横图：折口、封面、书脊、封底之间通常有一条几乎全白的折缝。先按白缝切块，取指定一半里
宽高比最接近 ratio（同系列竖版封面的宽高比）的一块。没有白缝时退回滑动窗口：取封面宽的
窗口里非白像素最多的位置（折口、书脊多是白底，封面是满幅插画）。
（试过找竖直边缘：插画背景常是渐变，封面边缘很弱，反而对到封底色块上，所以不用。）
仍然裁偏时看预览，用 --x0 手动给封面左边界。
直排的中文书（台版、日版）从右往左翻，封面在书脊左边，所以 side 默认 left；横排书用 right。
"""
import argparse
import shutil

import numpy as np
from PIL import Image, ImageDraw


def column_ink(gray, white=235):
    """每一列非白像素的占比。折口、书脊多是白底加少量文字，封面是满幅插画。"""
    return (gray < white).mean(axis=0)


def panels(ink, gap=0.05, min_gap=8):
    """按白缝（连续 min_gap 列以上、墨量 < gap）把展开图切成若干块，返回 [(x0, x1), ...]。"""
    smooth = np.convolve(ink, np.ones(5) / 5, mode="same")
    white = smooth < gap
    out, start, x, w = [], 0, 0, len(ink)
    while x < w:
        if white[x]:
            run = x
            while run < w and white[run]:
                run += 1
            if run - x >= min_gap:
                if x > start:
                    out.append((start, x))
                start = run
            x = run
        else:
            x += 1
    if start < w:
        out.append((start, w))
    # 平滑会把块的边往白缝里扩几列，按原始墨量收回来
    tight = []
    for x0, x1 in out:
        while x0 < x1 and ink[x0] < gap:
            x0 += 1
        while x1 > x0 and ink[x1 - 1] < gap:
            x1 -= 1
        if x1 > x0:
            tight.append((x0, x1))
    return tight


def find_front(gray, ratio=0.68, side="left", tol=0.12):
    """返回封面在展开图中的 (x0, x1)。

    先按白缝切块，取指定一半里宽高比与 ratio 相差不超过 tol 的最接近的一块；
    没有合适的块（插画跨过折痕、没有白缝）时，退回滑动窗口：取墨量最大的封面宽窗口。
    """
    h, w = gray.shape
    cw = int(round(h * ratio))
    if cw >= w:
        return 0, w
    ink = column_ink(gray)
    half = (lambda c: c <= w / 2) if side == "left" else (lambda c: c >= w / 2)
    fits = [(abs((x1 - x0) / h - ratio), x0, x1) for x0, x1 in panels(ink)
            if half((x0 + x1) / 2) and abs((x1 - x0) / h - ratio) <= tol]
    if fits:
        _, x0, x1 = min(fits)
        return x0, x1
    csum = np.concatenate([[0.0], np.cumsum(ink)])
    best, best_x = -1.0, 0
    for x in range(0, w - cw + 1):
        if not half(x + cw / 2):
            continue
        score = csum[x + cw] - csum[x]
        if score > best:
            best, best_x = score, x
    return best_x, best_x + cw


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--preview")
    p.add_argument("--ratio", type=float, default=0.68)
    p.add_argument("--side", choices=["left", "right"], default="left")
    p.add_argument("--x0", type=int, help="手动指定封面左边界（自动裁偏时用）")
    a = p.parse_args(argv)

    img = Image.open(a.src).convert("RGB")
    w, h = img.size
    if w < h:
        shutil.copyfile(a.src, a.out)
        print(f"{a.src}: portrait {w}x{h}, used as is")
        return
    if a.x0 is not None:
        x0, x1 = a.x0, min(w, a.x0 + int(round(h * a.ratio)))
    else:
        x0, x1 = find_front(np.asarray(img.convert("L")), a.ratio, a.side)
    img.crop((x0, 0, x1, h)).save(a.out, quality=92)
    print(f"{a.src}: spread {w}x{h} -> front x={x0}..{x1}")
    if a.preview:
        # 左：展开图上画出裁剪框；右：裁出的封面
        scale = 400 / h
        left = img.resize((int(w * scale), 400))
        ImageDraw.Draw(left).rectangle((x0 * scale, 0, x1 * scale, 399), outline=(255, 0, 0), width=4)
        right = img.crop((x0, 0, x1, h)).resize((int((x1 - x0) * scale), 400))
        sheet = Image.new("RGB", (left.width + right.width + 10, 400), "white")
        sheet.paste(left, (0, 0))
        sheet.paste(right, (left.width + 10, 0))
        sheet.save(a.preview, quality=85)


if __name__ == "__main__":
    main()
