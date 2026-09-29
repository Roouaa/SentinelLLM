# Log

Two lines per session: what I did, what fought back. Oldest first.

## 2026-09-19
Did: set up the repo, venv, folder structure, .gitignore. First two commits.
Fought back: where ARCHITECTURE.md belongs, git author identity, naming eval/ vs evals/.

## 2026-09-21
Did: wrote attacks.yaml with three cases (direct, extraction, indirect). Runner loads the
file and fails cleanly when it is missing or invalid, with an exit code instead of a traceback.
Fought back: YAML punctuation — a colon or a dash needs a space after it or the line is not
what it looks like. Also picked bad canaries at first: "You are" and "system prompt" both
appear in an ordinary refusal, so a perfect defence would have scored as a failure. And
extract-001 meant nothing until there was an actual secret in a system prompt to steal.

## 2026-09-24
Did: wrote the stub model, the canary judge, and build_prompt (joins the question and the
untrusted document, wraps the document in markers). Added the loop over cases.
Fought back: print vs return — kept showing values on screen instead of handing them back,
three times. Related: calling a function and letting the result fall on the floor. Also lost
time to editor tabs that were not saved, and to the file path meaning something different
depending on which folder I ran the command from.

## 2026-09-27
Did: finished M0. Score line, main() with the __name__ guard, benign-001 case, and a path
built from __file__ so it works from any folder. Wrote the known-limitations section in the
README.
Fought back: the canary list parsed as a *string* instead of a list, because the dashes had
no space after them. The judge then looped over it character by character, matched a space,
and reported a passing case as a failure — valid YAML, no error, wrong answer. Caught by the
benign case on its first run. Also thought __file__ and .parent were placeholders to fill in
with the real names; they are literal words Python fills in itself.
