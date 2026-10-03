#!/usr/bin/env python3
"""Add or update Basic vocab cards through AnkiConnect (127.0.0.1:8765), with audio."""

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:8765"
# Youdao word pronunciation: type=2 is US, type=1 is UK
YOUDAO = "https://dict.youdao.com/dictvoice?audio={word}&type={type}"
VOICES = {"us": "en-US-AriaNeural", "uk": "en-GB-SoniaNeural"}
SOUND = re.compile(r"\s*\[sound:[^\]]*\]")


def call(action, **params):
    req = json.dumps({"action": action, "version": 6, "params": params}).encode()
    try:
        with urllib.request.urlopen(URL, req, timeout=10) as resp:
            reply = json.load(resp)
    except (urllib.error.URLError, OSError) as err:
        sys.exit(f"Cannot reach AnkiConnect at {URL} ({err}). Is Anki running with AnkiConnect?")
    if reply["error"]:
        sys.exit(f"AnkiConnect {action} failed: {reply['error']}")
    return reply["result"]


def headword(front):
    # Front is "word<br>sentence"; compare on the first line with tags/entities stripped
    first = re.split(r"<br\s*/?>|<div>|\n", front, maxsplit=1)[0]
    return html.unescape(re.sub(r"<[^>]+>", "", SOUND.sub("", first))).strip().lower()


def front_sentence(front):
    parts = re.split(r"<br\s*/?>", front, maxsplit=1)
    return html.unescape(re.sub(r"<[^>]+>", "", SOUND.sub("", parts[1]))).strip() if len(parts) > 1 else ""


def tts(text, accent):
    """Synthesize text with edge-tts (free Microsoft Edge neural voices); returns mp3 bytes or None."""
    cmd = shutil.which("edge-tts") and ["edge-tts"] or shutil.which("uvx") and ["uvx", "edge-tts"]
    if not cmd:
        print("warning: edge-tts not installed (uv tool install edge-tts); skipping TTS", file=sys.stderr)
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "a.mp3"
        try:
            run = subprocess.run(cmd + ["--voice", VOICES[accent], "--text", text, "--write-media", str(out)],
                                 capture_output=True, text=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError) as err:
            print(f"warning: edge-tts failed: {err}; skipping TTS", file=sys.stderr)
            return None
        if run.returncode or not out.exists() or not out.stat().st_size:
            print(f"warning: edge-tts failed: {run.stderr.strip()[-200:]}", file=sys.stderr)
            return None
        return out.read_bytes()


def word_audio(word, accent):
    """Dictionary pronunciation from Youdao, falling back to edge-tts."""
    url = YOUDAO.format(word=urllib.parse.quote(word), type=2 if accent == "us" else 1)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = resp.read()
            if resp.headers.get_content_type().startswith("audio") and len(data) > 1000:
                return data
    except (urllib.error.URLError, OSError):
        pass
    return tts(word, accent)


def store(name, data):
    filename = call("storeMediaFile", filename=name, data=base64.b64encode(data).decode())
    return f" [sound:{filename}]"


def notes_by_word(deck):
    escaped_deck = deck.replace("\\", "\\\\").replace('"', '\\"')
    ids = call("findNotes", query=f'deck:"{escaped_deck}"')
    notes = {}
    for note in call("notesInfo", notes=ids):
        if not {"Front", "Back"} <= note["fields"].keys():
            continue
        word = headword(note["fields"]["Front"]["value"])
        if word in notes:
            sys.exit(f"Multiple notes for '{word}' in deck {deck}; resolve duplicates in Anki first.")
        notes[word] = note
    return notes


def slug(word):
    return re.sub(r"[^a-z0-9]+", "-", word.lower()).strip("-")


def audio_tags(word, sentence, accent):
    w_snd = s_snd = ""
    if accent:
        if data := word_audio(word, accent):
            w_snd = store(f"anki-vocab_{slug(word)}_{hashlib.sha256(data).hexdigest()}.mp3", data)
        if sentence and (data := tts(sentence, accent)):
            s_snd = store(f"anki-vocab_{slug(word)}_sentence_{hashlib.sha256(data).hexdigest()}.mp3", data)
    return w_snd, s_snd


def front_field(word, sentence, accent):
    """Front with word + sentence audio; accent None means no audio."""
    w_snd, s_snd = audio_tags(word, sentence, accent)
    return f"{html.escape(word, quote=False)}{w_snd}<br>{html.escape(sentence, quote=False)}{s_snd}"


def refresh_audio(front, accent):
    """Replace sound tags without rewriting the card's text or HTML."""
    parts = re.split(r"(<br\s*/?>)", front, maxsplit=1)
    if len(parts) != 3:
        raise ValueError("Front must contain a word and sentence separated by <br>")
    w_snd, s_snd = audio_tags(headword(front), front_sentence(front), accent)
    word_part = SOUND.sub("", parts[0]) + w_snd if w_snd else parts[0]
    sentence_part = SOUND.sub("", parts[2]) + s_snd if s_snd else parts[2]
    return word_part + parts[1] + sentence_part


def fields(word, sentence, back_lines, accent):
    esc = [html.escape(s, quote=False) for s in back_lines]
    return {"Front": front_field(word, sentence, accent), "Back": "<br>".join(esc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", default="Write")
    parser.add_argument("--accent", choices=VOICES, default="us")
    parser.add_argument("--no-audio", action="store_true", help="do not attach pronunciation audio")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list words in the deck")
    p = sub.add_parser("delete", help="delete notes; retain media that other cards may share")
    p.add_argument("words", nargs="+")
    p = sub.add_parser("audio", help="(re)attach audio to existing cards, keeping their text")
    p.add_argument("words", nargs="*", help="words to process (default: every card in the deck)")
    for name in ("add", "update"):
        p = sub.add_parser(name, help=f"{name} a card")
        p.add_argument("word")
        p.add_argument("sentence")
        p.add_argument("back", nargs="+", help="back lines, in order")
    args = parser.parse_args()
    if args.cmd == "audio" and args.no_audio:
        parser.error("--no-audio cannot be used with audio")
    if args.cmd in ("add", "update") and not args.word.strip():
        parser.error("word must not be empty")

    existing = notes_by_word(args.deck)
    if args.cmd == "list":
        print("\n".join(sorted(existing)) or f"(deck {args.deck} is empty)")
        return

    if args.cmd == "delete":
        for word in args.words:
            note = existing.get(word.strip().lower())
            if not note:
                print(f"'{word}' not found in deck {args.deck}; skipped", file=sys.stderr)
                continue
            call("deleteNotes", notes=[note["noteId"]])
            print(f"deleted {word} from {args.deck} (note {note['noteId']})")
        return

    accent = None if args.no_audio else args.accent
    if args.cmd == "audio":
        for word in args.words or sorted(existing):
            note = existing.get(word.strip().lower())
            if not note:
                print(f"'{word}' not found in deck {args.deck}; skipped", file=sys.stderr)
                continue
            try:
                front = refresh_audio(note["fields"]["Front"]["value"], accent)
            except ValueError as err:
                print(f"'{word}': {err}; skipped", file=sys.stderr)
                continue
            call("updateNoteFields", note={"id": note["noteId"], "fields": {"Front": front}})
            print(f"audio {word}: {front.count('[sound:')} file(s)")
        return

    key = args.word.strip().lower()
    if args.cmd == "add" and key in existing:
        sys.exit(f"'{args.word}' already in deck {args.deck}; use update to rewrite it.")
    if args.cmd == "update" and key not in existing:
        sys.exit(f"'{args.word}' not found in deck {args.deck}; use add instead.")
    new_fields = fields(args.word.strip(), args.sentence.strip(), args.back, accent)
    if args.cmd == "add":
        nid = call("addNote", note={"deckName": args.deck, "modelName": "Basic", "fields": new_fields})
        print(f"added {args.word} to {args.deck} (note {nid})")
    else:
        nid = existing[key]["noteId"]
        call("updateNoteFields", note={"id": nid, "fields": new_fields})
        print(f"updated {args.word} in {args.deck} (note {nid})")


if __name__ == "__main__":
    main()
