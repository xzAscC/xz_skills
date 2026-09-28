---
name: anki-vocab
description: Create or update English vocabulary Anki cards in a fixed concise format (word + source sentence / IPA, Chinese meanings, key phrase, translated example, synonyms), written to Anki through AnkiConnect. Use when the user asks what an English word means and wants an Anki card, asks to add/fill/rewrite Anki cards, or mentions the Write deck.
---

# Anki Vocab

Explain an English word the user met while reading, then write it to Anki as one Basic card.

## Card format

Lines are joined with `<br>`. No other HTML, links, or styling.

**Front**
```
infancy
This movement toward the data base is in its infancy.
```

**Back**
```
/ˈɪnfənsi/ n.
1. 婴儿期
2. （事物的）初期，萌芽阶段
be in its infancy = 处于起步阶段
例句：向数据库发展的这场变革还处于起步阶段。（Bachman, 1973）
近义：early stage, nascent, embryonic
```

Rules:
- Front line 1 is the word as a headword; line 2 is the sentence the user actually read, verbatim.
- Back line 1: IPA plus part of speech (`n.`, `v.`, `adj.`, `v. & n.`).
- Numbered meanings in Chinese, most basic first, and always include the meaning used in the sentence.
- One key collocation or phrase as `phrase = 中文`, preferably the one in the sentence.
- `例句：` gives the Chinese translation of the front sentence, with the source in `（）` when known.
- `近义：` gives 2–3 English synonyms.
- Keep it short. Do not add etymology or long explanations unless the user asks for them.
- If the user gave no source sentence, ask for one. If you have to write your own example, say so to the user.

## Writing to Anki

Anki desktop must be running with the AnkiConnect add-on (code `2055492159`,
listening on `127.0.0.1:8765`). Use the bundled script, which has no dependencies
beyond Python 3:

```bash
python3 <skill-dir>/anki.py list                      # words already in the deck
python3 <skill-dir>/anki.py add WORD "SENTENCE" "BACK LINE 1" "BACK LINE 2" ...
python3 <skill-dir>/anki.py update WORD "SENTENCE" "BACK LINE 1" ...   # rewrite an existing card
```

- The default deck is `Write`; pass `--deck NAME` before the subcommand to use another deck.
- `add` refuses a word that already exists in the deck; use `update` to rewrite that card.
- Text is HTML-escaped by the script, so pass plain text.

If AnkiConnect is unreachable (Anki is closed, or the AI has no shell access), do not keep
retrying. Give the user the card in the format above, plus one tab-separated import
line (`FRONT<TAB>BACK`, lines joined with `<br>`) for Anki's File → Import.
