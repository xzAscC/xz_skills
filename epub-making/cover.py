#!/usr/bin/env python3
"""从书衣展开图（折口 | 封面 | 书脊 | 封底 | 折口）里裁出封面，并生成预览给人确认。

    cover.py SPREAD.jpg -o cover.jpg --preview preview.jpg [--ratio 0.68] [--side left]

竖图（宽 < 高）本身就是封面，原样复制。
横图：封面宽 ≈ 高 × ratio（同系列竖版封面的宽高比）。在指定的一半里滑动这个宽度的窗口，
取非白像素最多的位置：折口和书脊多是白底，封面是满幅插画。
（试过找竖直边缘：插画背景常是渐变，封面边缘很弱，反而会对到封底色块上，所以不用。）
直排的中文书（台版、日版）从右往左翻，封面在书脊左边，所以 side 默认 left；横排书用 right。
"""
import argparse
import shutil

import numpy as np
from PIL import Image, ImageDraw


def column_ink(gray, white=235):
    """每一列非白像素的占比。折口、书脊多是白底加少量文字，封面是满幅插画。"""
    return (gray < white).mean(axis=0)


def find_front(gray, ratio=0.68, side="left"):
    """返回封面在展开图中的 (x0, x1)：在指定的一半里，取「墨量」最大的封面宽窗口。"""
    h, w = gray.shape
    cw = int(round(h * ratio))
    if cw >= w:
        return 0, w
    csum = np.concatenate([[0.0], np.cumsum(column_ink(gray))])
    best, best_x = -1.0, 0
    for x in range(0, w - cw + 1):
        centre = x + cw / 2
        if (side == "left" and centre > w / 2) or (side == "right" and centre < w / 2):
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
    a = p.parse_args(argv)

    img = Image.open(a.src).convert("RGB")
    w, h = img.size
    if w < h:
        shutil.copyfile(a.src, a.out)
        print(f"{a.src}: portrait {w}x{h}, used as is")
        return
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
