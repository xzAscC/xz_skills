---
name: bib-lookup
description: Get correct BibTeX for papers with the `aibib` CLI (AI Bib Helper) — DBLP search, then the publisher's official export, the DOI agency's, or DBLP metadata. Use when the user asks to 找 bib, 加引用, get/fix a BibTeX entry, fill a .bib file, or cite a paper by title, DOI or URL. Never write BibTeX from memory.
---

# Bib Lookup

BibTeX written from memory has wrong venues, years and author lists. Every
entry must come from `aibib` (https://github.com/xzAscC/AI-Bib-Helper). If the
command is not installed, ask before you install it with
`uv tool install git+https://github.com/xzAscC/AI-Bib-Helper`.

## Steps

1. Get the exact title from the paper or from the user. Do not guess a title
   from a topic. If you only have keywords, run `aibib search "<keywords>" -n 5`
   and let the user pick.
2. Run `aibib get "<exact title>"` (several titles in one call are fine; the
   tool spaces the requests). A DOI or paper URL also works.
3. Read the `%` line on stderr for each entry. Check the title, the year and the
   first author against what the user meant. Also check the version:
   - `[published]` is preferred.
   - If the line says `[preprint]` but the paper was published, run
     `aibib search` and take the published version with `--pick N`.
4. Report the source to the user:
   - `NeurIPS`, `PMLR`, `ACL`, `CVF`, `AAAI`, `IJCAI`, `Springer`: the
     publisher's official export.
   - `DOI`: the Crossref or DataCite record.
   - `DBLP-metadata`: built from DBLP's record. Mention this.
5. Add the entry to the `.bib` file only when the user asks. Keep the official
   key unless the user wants their own key; then use `--key`. Before you
   append, check the file for a duplicate key or title.

## Limits

- Exit code 2 means the run was rate-limited. Stop, tell the user, and do not
  retry in a loop.
- Do not use Google Scholar, OpenReview or dblp.org pages directly; they block
  scripts. The user's browser userscript Overleaf-Bib-Helper (Chrome Profile 4,
  `Alt+Shift+B` in an Overleaf project) covers those cases by hand.
- `aibib --refresh` refetches. Use it only if the cached entry is wrong.
