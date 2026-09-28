#!/usr/bin/env python3
"""Add or update Basic vocab cards through AnkiConnect (127.0.0.1:8765)."""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8765"


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
    return html.unescape(re.sub(r"<[^>]+>", "", first)).strip().lower()


def notes_by_word(deck):
    ids = call("findNotes", query=f'deck:"{deck}"')
    return {headword(n["fields"]["Front"]["value"]): n for n in call("notesInfo", notes=ids)}


def fields(word, sentence, back_lines):
    esc = [html.escape(s, quote=False) for s in back_lines]
    return {
        "Front": f"{html.escape(word, quote=False)}<br>{html.escape(sentence, quote=False)}",
        "Back": "<br>".join(esc),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", default="Write")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list words in the deck")
    for name in ("add", "update"):
        p = sub.add_parser(name, help=f"{name} a card")
        p.add_argument("word")
        p.add_argument("sentence")
        p.add_argument("back", nargs="+", help="back lines, in order")
    args = parser.parse_args()

    existing = notes_by_word(args.deck)
    if args.cmd == "list":
        print("\n".join(sorted(existing)) or f"(deck {args.deck} is empty)")
        return

    key = args.word.strip().lower()
    new_fields = fields(args.word.strip(), args.sentence.strip(), args.back)
    if args.cmd == "add":
        if key in existing:
            sys.exit(f"'{args.word}' already in deck {args.deck}; use update to rewrite it.")
        nid = call("addNote", note={"deckName": args.deck, "modelName": "Basic", "fields": new_fields})
        print(f"added {args.word} to {args.deck} (note {nid})")
    else:
        if key not in existing:
            sys.exit(f"'{args.word}' not found in deck {args.deck}; use add instead.")
        nid = existing[key]["noteId"]
        call("updateNoteFields", note={"id": nid, "fields": new_fields})
        print(f"updated {args.word} in {args.deck} (note {nid})")


if __name__ == "__main__":
    main()
