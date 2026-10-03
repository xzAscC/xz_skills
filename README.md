# xz_skills

Personal agent skills (the `SKILL.md` format used by Claude Code, opencode, and others).

| Skill | What it does |
| --- | --- |
| [anki-vocab](anki-vocab/SKILL.md) | Turns an English word plus the sentence it came from into a concise Anki card, written through AnkiConnect |
| [paper-figures](paper-figures/SKILL.md) | House style for paper figures (matplotlib and TikZ): fonts, print sizes, colors, axes, export, checklist |

## Install

Clone the repo, then link each skill into the directories your agents read:

```bash
git clone https://github.com/xzAscC/xz_skills.git ~/xz_skills
ln -s ~/xz_skills/anki-vocab ~/.agents/skills/anki-vocab
ln -s ../../.agents/skills/anki-vocab ~/.claude/skills/anki-vocab
ln -s ~/xz_skills/paper-figures ~/.agents/skills/paper-figures
ln -s ../../.agents/skills/paper-figures ~/.claude/skills/paper-figures
```

`anki-vocab` needs Anki desktop running with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.
