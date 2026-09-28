# xz_skills

Personal agent skills (the `SKILL.md` format used by Claude Code, opencode, and others).

| Skill | What it does |
| --- | --- |
| [anki-vocab](anki-vocab/SKILL.md) | Turns an English word plus the sentence it came from into a concise Anki card, written through AnkiConnect |

## Install

Clone the repo, then link each skill into the directories your agents read:

```bash
git clone https://github.com/xzAscC/xz_skills.git ~/xz_skills
ln -s ~/xz_skills/anki-vocab ~/.agents/skills/anki-vocab
ln -s ../../.agents/skills/anki-vocab ~/.claude/skills/anki-vocab
```

`anki-vocab` needs Anki desktop running with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.
