# xz_skills

Personal agent skills (the `SKILL.md` format used by Claude Code, opencode, and others).

| Skill | What it does |
| --- | --- |
| [anki-vocab](anki-vocab/SKILL.md) | Turns an English word plus the sentence it came from into a concise Anki card, written through AnkiConnect |
| [paper-figures](paper-figures/SKILL.md) | House style for paper figures (matplotlib and TikZ): fonts, print sizes, colors, axes, export, checklist |
| [zhihu-answer-writing](zhihu-answer-writing/SKILL.md) | Drafts or revises Zhihu answers in the user's own analytical first-person voice: verified data, no AI flavor |
| [zh-controlled-writing](zh-controlled-writing/SKILL.md) | Rewrites or reviews Chinese technical prose with concise rules and personal style preferences |
| [en-controlled-writing](en-controlled-writing/SKILL.md) | Writes, rewrites or reviews plain English with strict, default and light editing levels |
| [x-post-writing](x-post-writing/SKILL.md) | Drafts English X posts and threads in the user's voice, checks weighted length, and archives what was posted |

## Install

Clone the repo, then link each skill into the directories your agents read:

```bash
git clone https://github.com/xzAscC/xz_skills.git ~/xz_skills
mkdir -p ~/.agents/skills ~/.claude/skills
for skill in anki-vocab paper-figures zhihu-answer-writing zh-controlled-writing en-controlled-writing x-post-writing; do
    ln -sT ~/xz_skills/"$skill" ~/.agents/skills/"$skill"
    ln -sT ../../.agents/skills/"$skill" ~/.claude/skills/"$skill"
done
```

These commands use GNU `ln` (Linux). Existing destinations are left intact and
reported as errors; inspect them before replacing a skill installation.

`anki-vocab` needs Anki desktop running with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.
Its optional sentence audio uses `edge-tts` or `uvx` and network access.
`paper-figures/check_figs.py` needs Poppler's `pdffonts` and `pdfinfo`.

Run the offline regression checks with `python3 -m unittest discover -s tests -v`.
