#!/usr/bin/env python3
"""Check paper figure PDFs: embedded fonts, house text font, and print width.

Usage: python3 check_figs.py [--textwidth 5.5] FIG.pdf|DIR ...
Needs poppler's pdffonts and pdfinfo. Exits 1 when any figure fails.
"""
import argparse
import math
import os
import re
import subprocess
import sys
from pathlib import Path

TEXT_FONT = "SourceSansPro"
# Math fallbacks that may appear next to the text font (matplotlib mathtext, newtxsf).
MATH_FONTS = ("STIX", "Cmsy", "Cmmi", "Cmr", "Cmex", "DejaVuSans-Oblique", "zsfmi", "txsys", "newtx")


def poppler(command, pdf):
    try:
        result = subprocess.run([command, str(pdf.resolve())], capture_output=True,
                                text=True, timeout=30, env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as err:
        raise ValueError(f"{command}: {err}") from err
    if result.returncode:
        raise ValueError(f"{command}: {result.stderr.strip() or 'failed'}")
    return result.stdout


def fonts(pdf):
    rows = poppler("pdffonts", pdf).splitlines()[2:]
    out = []
    for row in rows:
        cols = row.split()
        if len(cols) < 6:
            raise ValueError(f"cannot parse pdffonts row: {row}")
        # Columns end with: emb sub uni object-id generation.
        out.append((cols[0].split("+")[-1], cols[-5] == "yes"))
    return out


def width_in(pdf):
    info = poppler("pdfinfo", pdf)
    pages = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not pages or int(pages.group(1)) != 1:
        raise ValueError("expected a single-page figure PDF")
    w = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info)
    if not w:
        raise ValueError("cannot read PDF page size")
    return float(w.group(1)) / 72, float(w.group(2)) / 72


def check(pdf, textwidth):
    problems = []
    w, h = width_in(pdf)
    if w > textwidth + 0.01:
        problems.append(f"width {w:.2f}in exceeds textwidth {textwidth}in")
    found = fonts(pdf)
    if not any(TEXT_FONT in name for name, _ in found):
        problems.append(f"no {TEXT_FONT} text font")
    for name, embedded in found:
        if not embedded:
            problems.append(f"font not embedded: {name}")
        if TEXT_FONT not in name and not name.startswith(MATH_FONTS):
            problems.append(f"unexpected font: {name}")
    return w, h, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--textwidth", type=float, default=5.5)
    args = parser.parse_args()
    if not math.isfinite(args.textwidth) or args.textwidth <= 0:
        parser.error("--textwidth must be a positive finite number")
    empty_dirs = [path for path in args.paths if path.is_dir() and not any(path.glob("*.pdf"))]
    for path in empty_dirs:
        print(f"FAIL  no PDF files in {path}")
    pdfs = [p for path in args.paths for p in (sorted(path.glob("*.pdf")) if path.is_dir() else [path])]
    failed = 0
    for pdf in pdfs:
        try:
            w, h, problems = check(pdf, args.textwidth)
        except ValueError as err:
            print(f"FAIL  {pdf.name}: {err}")
            failed += 1
            continue
        print(f"{'FAIL' if problems else 'ok  '}  {w:.2f} x {h:.2f}in  {pdf.name}")
        for p in problems:
            print(f"      - {p}")
        failed += bool(problems)
    print(f"{len(pdfs) - failed}/{len(pdfs)} figures pass. Widths must still match each figure's LaTeX slot.")
    sys.exit(1 if failed or empty_dirs else 0)


if __name__ == "__main__":
    main()
