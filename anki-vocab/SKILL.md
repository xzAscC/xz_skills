---
name: anki-vocab
description: Create or update English vocabulary Anki cards in a fixed concise format (word + source sentence / IPA, Chinese meanings, key phrase, translated example, etymology with root breakdown, same-root words, synonyms), written to Anki through AnkiConnect. Use when the user asks what an English word means and wants an Anki card, asks to add/fill/rewrite Anki cards, or mentions the Write deck.
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
词源：in-（不）+ fa-（说，拉丁 fari）+ -ancy → 还不会说话的时期
同根：infant 婴儿, fable 寓言, fate 命运（神"说"定的）, preface 前言, ineffable 难以言表的
近义：early stage, nascent, embryonic
```

Rules:
- Front line 1 is the word as a headword; line 2 is the sentence the user actually read, verbatim.
- Back line 1: IPA plus part of speech (`n.`, `v.`, `adj.`, `v. & n.`).
- Numbered meanings in Chinese, most basic first, and always include the meaning used in the sentence.
- One key collocation or phrase as `phrase = 中文`, preferably the one in the sentence.
- `例句：` gives the Chinese translation of the front sentence, with the source in `（）` when known.
- `词源：` splits the word into prefix / root / suffix with each part's meaning in `（）`
  (name the Latin/Greek/Old English source of the root), then `→` a short Chinese gloss
  showing how the parts add up to the meaning. Prefer the real historical etymology over
  folk etymology; if the origin is uncertain or the word is not decomposable, give the
  source word briefly (e.g. `源自古法语 xxx`) instead of inventing a split.
- `同根：` gives 3–5 common words that share the root (or a key affix), each with a short
  Chinese gloss; add a few-word hint in `（）` when the link to the root is not obvious.
  Prefer words the user likely knows, so the new word hooks onto familiar ones.
- `近义：` gives 2–3 English synonyms.
- Keep it short: one line each for 词源 and 同根, no long explanations.
- If the user gave no source sentence, ask for one. If you have to write your own example, say so to the user.

## Writing to Anki

Anki desktop must be running with the AnkiConnect add-on (code `2055492159`,
listening on `127.0.0.1:8765`). Use the bundled script, which has no dependencies
beyond Python 3:

```bash
python3 <skill-dir>/anki.py list                      # words already in the deck
python3 <skill-dir>/anki.py add WORD "SENTENCE" "BACK LINE 1" "BACK LINE 2" ...
python3 <skill-dir>/anki.py update WORD "SENTENCE" "BACK LINE 1" ...   # rewrite an existing card
python3 <skill-dir>/anki.py delete WORD ...           # delete cards and their audio files
python3 <skill-dir>/anki.py audio [WORD ...]          # (re)attach audio to existing cards, text untouched
```

- The default deck is `Write`; pass `--deck NAME` before the subcommand to use another deck.
- `add` refuses a word that already exists in the deck; use `update` to rewrite that card.
- Text is HTML-escaped by the script, so pass plain text.

### Audio

`add` and `update` attach pronunciation audio to the front automatically (US accent by default):

- Word: Youdao dictionary pronunciation, falling back to TTS.
- Sentence: TTS via `edge-tts` (free Microsoft Edge neural voices, no API key; install with
  `uv tool install edge-tts`).
- Files are stored in Anki's media folder as `anki-vocab_<word>.mp3` and
  `anki-vocab_<word>_sentence.mp3`, and referenced with `[sound:...]` after the word and sentence.
- Global options go before the subcommand: `--accent uk` for British voices, `--no-audio` to skip.
- Audio failures only print a warning; the card is still written. If audio was skipped, tell the
  user and fix it later with `anki.py audio WORD`.

If AnkiConnect is unreachable (Anki is closed, or the AI has no shell access), do not keep
retrying. Give the user the card in the format above, plus one tab-separated import
line (`FRONT<TAB>BACK`, lines joined with `<br>`) for Anki's File → Import.
