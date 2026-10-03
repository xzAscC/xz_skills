---
name: en-controlled-writing
description: "Write, rewrite, or review English prose — docs, explanations, PR descriptions, error messages, agent output — in a controlled style based on ASD-STE100 (Simplified Technical English), with a strictness dial (strict / 80% / light). Use when asked to explain something in STE or ASD-STE100, to make English plainer or easier to read, to remove AI flavor from English text, or to review English docs for clarity."
---

# English Controlled Writing

Based on ASD-STE100 (Simplified Technical English, Issue 9). Full STE is written for aerospace maintenance manuals and is stricter than most readers need. The default level here is about 80% of STE: keep the rules that make text easier to read, and relax the ones that only serve non-native mechanics reading procedures.

## Scope

- Use for: explanations, docs, PR and change descriptions, error and warning text, agent output that people read.
- Do not use for: code, identifiers, commands, logs (keep them as they are); marketing copy; literary prose.
- For Chinese text, use zh-controlled-writing. Do not mix the two rule sets.

## Strictness levels

| Level | Trigger | What changes |
|---|---|---|
| strict | "in ASD-STE100", "strict STE" | All rules below, including the [strict] rules |
| 80% (default) | "controlled English", "plain English", "80% STE", no level given | All rules except the [strict] rules |
| light | "light touch", "just clean it up" | Only the AI-flavor checklist and rules 1, 3, 9, 10 |

## Modes

| Mode | Trigger | Behavior |
|---|---|---|
| write | "explain X", "write a version" | Write new text that follows the rules |
| rewrite | "make this plainer", "remove AI flavor" | Change each sentence that breaks a rule. Keep every fact, number, condition, and limit |
| review | "review this, don't change it" | Give a table: rule \| original \| rewrite. Then say what you kept unchanged |

## Vocabulary rules

1. Use one word for one meaning, and one meaning for one word. If you choose "check", do not also use "verify", "validate", and "confirm" for the same action.
2. Use short, common words: use (not utilize or leverage), start (not initiate), help (not facilitate), show (not demonstrate), about (not approximately), get (not obtain), but (not however, at the start of a sentence).
3. Use verbs, not nouns made from verbs. "Perform an installation of the package" → "Install the package". "Make a decision" → "Decide".
4. Do not use phrasal verbs when a single verb exists: "set up" → "configure" or "prepare"; "find out" → "learn"; "carry out" → "do". [strict] In strict mode, replace all phrasal verbs.
5. Keep technical names exactly as the source uses them. Define an abbreviation at its first use.
6. Remove vague praise and replace it with facts: "very fast" → "processes 100,000 rows per second". Same for: powerful, robust, seamless, comprehensive, cutting-edge, world-class, efficient.
7. Noun clusters: do not put more than three nouns in a row. "database connection pool timeout setting" → "the timeout setting for the database connection pool".

## Sentence rules

8. Use the active voice. "The file is read by the parser" → "The parser reads the file". Use the passive only when the actor is unknown or does not matter.
9. One idea per sentence. Split a sentence that does two things.
10. Sentence length: instructions 20 words maximum, descriptions 25 words maximum (do not count code or identifiers). Split longer sentences.
11. Write instructions as commands: "Restart the service." Not "You should restart the service" or "The service should be restarted".
12. Use simple tenses: simple present, simple past, simple future ("will"). [strict] In strict mode, use no other tenses and no "-ing" verb forms except in technical names.
13. Keep articles ("the", "a") and "that" in place. Do not drop them to make text shorter.
14. Make each pronoun clear. If "it" or "this" can refer to two things, repeat the noun.
15. Paragraphs: one topic each, 6 sentences maximum.
16. Lists: use a numbered list for steps that occur in sequence. Use a bulleted list for items that have no order. Do not hide a list of four or more items in a sentence.

## Warnings and errors

17. Start a warning or caution with a short command, then give the reason. "Do not delete the lock file. The next build will fail."
18. An error message says what happened and what to do next. It does not apologize or blame the user.

## AI-flavor checklist (scan in this order before you output text)

1. Filler openers and closers: "It's worth noting that", "Importantly,", "In summary,", "Ultimately,", "At the end of the day". Remove them.
2. Overused AI words: delve, leverage, robust, seamless, crucial, pivotal, landscape, realm, tapestry, navigate (when not about navigation), foster, underscore, showcase, streamline, holistic. Replace each with a plain word or a fact.
3. "Not just X, but Y" and "It's not X — it's Y" patterns. Write the claim directly.
4. Groups of three adjectives or three parallel phrases used for rhythm. Keep the one that carries information.
5. Em dashes used as general punctuation. Use a period or a comma. Keep at most one em dash in a paragraph.
6. Hedging stacks: "may potentially", "could possibly help to". Keep one hedge, or state the fact.
7. Rhetorical questions followed by their answer ("The result? ..."). Write the statement.
8. Self-reference and narration: "Let's dive in", "Here's the thing", "Great question". Remove them.
9. Sentences over the length limit. Split them.
10. The same concept with two words. Use one.

## Keep unchanged

19. Keep code, identifiers, error strings, units, commands, numbers, and quotations exactly as they are. Do not remove a fact to improve the style.

## Output discipline

- Output only what the user asked for: no preamble, no summary, no "Sure, here is".
- In rewrite mode, change only the text that breaks a rule. Do not rewrite for taste.
- If the input already follows the rules, return it unchanged and say so.

## Sources

ASD-STE100 Issue 9 (2025). The 80% default comes from Andrej Karpathy's note (2026-10-02) that asking an LLM for "80% of the way to ASD-STE100" gives readable output without the full stringency of the spec.
