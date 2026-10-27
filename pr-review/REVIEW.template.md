# Review rules

<!-- Read by the pr-review skill. Keep it short; delete what you do not need. -->

Kind: research <!-- or: development -->

## Tests

Command: `python -m pytest -q`
Not runnable locally: tests marked `gpu` (A100; on OSC only when asked)

## Risk paths

High: `src/metrics/`, `src/data/`, `configs/train/`
Low: `docs/`

## Screenshots and numbers

Run a version: `python -m http.server 8000` in `site/`
Pages: `/`, `/blog/`
Numbers: `python scripts/eval.py --config tiny --seed 0`, compare `results/tiny.json`

## What counts as a failure here

- Reported numbers change without a stated reason

## Ignore

`third_party/`, generated files in `build/`

## Past misses

<!-- date, PR, what broke, which step should have caught it -->
