---
name: paper-figures
description: House style for research-paper figures drawn with matplotlib or TikZ/PGFPlots — fonts, print sizes, font sizes, semantic colors and markers, axes, legends, panel labels, uncertainty, export, and a verification checklist. Use before creating, restyling, or reviewing any figure meant for a paper (PDF in a LaTeX manuscript), so every figure in the paper reads as one system.
---

# Paper Figures

Every figure in a paper follows one style. Code that defines the style lives in one shared file; figures import it instead of copying settings.

## Where things go

- Plotting code: the project's `notebooks/` folder. Shared style: one `.py` file in `notebooks/` (e.g. `notebooks/figstyle.py`) holding the rcParams, size tiers, color tokens, and the project's method → color/marker table. Every notebook imports it.
- Output: PDF only, written to the project `figs/` and to the manuscript's `figs/` when it exists. Never save PNG or SVG files; preview inline in the notebook.
- Plot data is read from results/checkpoint files, never typed into the plotting code.
- TikZ/PGFPlots figures: a standalone `.tex` beside the manuscript, compiled to `figs/`, using the same fonts and color tokens as below.

## Fonts

- Figures: **Source Sans Pro**, math included. The paper body and abstract stay in the venue's serif (Times).
- matplotlib:

```python
from pathlib import Path
from matplotlib import font_manager
for f in Path("/usr/share/texmf-dist/fonts/opentype/adobe/sourcesanspro").glob("SourceSansPro-*.otf"):
    font_manager.fontManager.addfont(str(f))
RC = {
    "font.family": "Source Sans Pro", "mathtext.fontset": "custom",
    "mathtext.rm": "Source Sans Pro", "mathtext.it": "Source Sans Pro:italic",
    "mathtext.bf": "Source Sans Pro:bold", "mathtext.cal": "cmsy10",
    "mathtext.fallback": "stixsans", "pdf.fonttype": 42,
}
```

- TikZ preamble: `\usepackage[T1]{fontenc}`, `\usepackage{sourcesanspro}`, `\usepackage{amsmath}`, `\usepackage[scaled=.98]{newtxsf}`, `\let\mathrm\mathsf`, then `\sffamily` in the document.

## Size: draw at print size

- `figsize` width = the width the figure occupies on the page. In LaTeX use `width=\linewidth` of that slot with no extra scaling, so a font size in code is the printed size.
- Design for the narrowest target venue's `\textwidth` (5.5in for ICLR/NeurIPS-style templates). Tiers:
  - full width: 5.5in
  - half width (minipage or wrapfigure): 2.7in
- Check `\textwidth` in the template if the venue is different.

## Font sizes (printed pt)

| Role | Default | Allowed |
| --- | --- | --- |
| Panel title `(a) …` (bold) | 8 | 8–9 |
| Axis label | 8 | 7.5–9 |
| Tick label, legend, in-plot annotation | 7 | 6.5–8 |

Never below 6pt, never above the caption size (9pt). Crowded full-width multi-panel figures sit at the low end; sparse half-width figures may use the high end.

## Colors and markers

- Neutrals (only these three):
  - ink `#203342`: axis labels, titles, text
  - muted `#74818A`: tick labels, ticks, spines, secondary text
  - rule `#DCE3E6`: grid
- One meaning, one look: a method has the same color and marker in every figure. The project's style file holds the table. Default roles:

| Role | Color |
| --- | --- |
| Proposed method | teal `#007E80` |
| Main baseline | copper `#B77544` |
| Second baseline | violet `#8471AA` |
| Reference (e.g. no intervention) | gray `#505963` |
| Further methods | `#4C78A8`, `#8C6D31`, `#3C8966`, `#BD596B` |
| Models (when color encodes model) | `#3A6DB5`, `#D04A4A`, `#B88A12`, `#3E8E3E` |

- **Marker shape encodes the method; fill encodes a second factor** (e.g. operator: solid vs half-filled with `fillstyle="left"`, `markerfacecoloralt="white"`). Never reuse a shape for two methods, and never use fill to mean a method.
- Model colors and method colors do not share a figure.
- Series that are not methods (e.g. a random control) use muted gray.

## Axes

- Remove top and right spines; left and bottom spines muted, 0.5pt.
- Horizontal grid only, rule color, 0.4pt, below the data (`ax.set_axisbelow(True)`).
- Ticks outward, length 2.5pt, width 0.4pt, no minor ticks.
- Axis labels in Title Case with units in parentheses, e.g. `Behavioral Control (%)`. Use one name per quantity across the paper, matching the text.
- Report rates as percentages (0–100), not fractions.
- Log axes: tick labels as `10⁻³`, never `1e-3`.
- Broken or compressed axes: `//` break marks on the axis, and say so in the caption.

## Legends and labels

- Default: one legend above the plot area, single row, no frame (`frameon=False`). For multi-panel figures, one shared `fig.legend` above all panels.
- Direct labels (text next to the series, in its color) only when a legend does not fit or would cover data.

## Panel labels

- Multi-panel figures: `(a) Short title`, bold, left-aligned, above the axes (`ax.set_title(..., loc="left", fontweight="bold")`). The title names what the panel shows, not the finding.
- Single-panel figures: no label.

## Uncertainty

- Continuous x: line plus shaded band, `fill_between(..., alpha=0.12, linewidth=0)` in the series color.
- Discrete x: thin error bars (`elinewidth=0.6`, `capsize=1.5`).
- The caption states the band (std or s.e.) and the number of samples.

## Export

- `layout="constrained"`; do not use `bbox_inches="tight"` (it changes the PDF width away from `figsize`).
- `pdf.fonttype: 42` so fonts embed as TrueType.
- Save PDF only.

## Checklist (run for every figure)

1. `pdffonts fig.pdf`: only Source Sans (plus math fallbacks), all embedded.
2. `pdfinfo fig.pdf`: page width equals the tier width; the LaTeX include adds no scaling.
3. Compile the paper and view the page: all text 6–9pt and in proportion to the body text.
4. Colors and markers match the project table; series remain distinguishable in grayscale.
5. Data loads from results files; no hard-coded values.
6. Caption states uncertainty type, sample count, and any axis breaks.
