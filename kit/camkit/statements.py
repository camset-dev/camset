"""The camera owner's dated statements, kept in the camera's reviewed scope beside the owner decisions (its "decisions"
list, runs/<model>_fw<fw>/kit2_pass1/pass2_scope_draft.json, never committed: docs/decisions/0018):

    {"date": "YYYY-MM-DD", "cards": "blank", "why": "..."}      every card in the camera holds nothing the owner wants
                                                                 kept, and the cards stay in for the whole mapping
    {"date": "YYYY-MM-DD", "cards": "withdrawn", "why": "..."}  no longer so (a card the owner keeps went back in)
    {"date": "YYYY-MM-DD", "picture": "once", "why": "..."}     the owner let kit/tools/take_picture.py release the
                                                                 shutter once, told what it would sound and light

A statement lifts no guard: Format and Delete stay refused exactly as before. It records what the owner was asked, and
the runs that need it read it: a row's first open on the body (camkit.first_open: kit/drive.py, kit/crawl_run.py) needs
the latest cards statement to say "blank", and take_picture.py needs both. It carries no "lifts" and no "rows", so no
decision reader takes it for a decision (safety.owner_decided, network_decided, approved_rows).

Only the answer a person types at a real terminal writes one (ask: kit/tools/owner_statement.py, take_picture.py): no
flag answers it, nor a pipe (standard input no TTY), nor a shell that says in its environment an agent started it
(AGENT_MARKERS). It stops a careless agent, not a determined one (a pseudo-terminal started with a clean environment can
answer it, and the file can be written by hand), so the question says that only the camera's owner answers it, as
kit/drive.py's typed_word says of the owner route's.
"""
import datetime
import json
import os
import sys
from pathlib import Path

from . import safety

KINDS = {"cards": ("blank", "withdrawn"), "picture": ("once",)}
# what a shell an agent started says in its environment (Claude Code's, and the shared AI_AGENT convention): a question
# asked there is never answered, a pseudo-terminal or not
AGENT_MARKERS = ("AI_AGENT", "CLAUDECODE")
CARDS_HOW = ("ask the owner to put in cards that hold nothing they want kept, to leave them in for the whole mapping, "
             "and to run, in their own terminal, .venv/bin/python kit/tools/owner_statement.py cards (only the owner "
             "answers its question)")


def problem(d) -> str:
    """Why the decision entry `d`, which carries a statement's key, is no statement (its keys exactly date, the kind and
    why; a day written YYYY-MM-DD, today or before; a why; the kind's own value), or ""."""
    kind = next((k for k in KINDS if k in d), None)
    if kind is None:
        return "it names no statement"
    if set(d) != {"date", kind, "why"}:
        return f"a statement holds date, {kind} and why alone, not {', '.join(sorted(set(d) - {'date', kind, 'why'}))}"
    if not safety._valid_day(d.get("date")):
        return f"its date {d.get('date')!r} is not a day written YYYY-MM-DD, today or before"
    if not isinstance(d.get("why"), str) or not d["why"].strip():
        return "it says no why"
    if d[kind] not in KINDS[kind]:
        return f"its {kind!r} is {d[kind]!r}, not {' or '.join(map(repr, KINDS[kind]))}"
    return ""


def latest(scope, kind: str) -> tuple:
    """(the last statement of `kind` in the scope's decisions, why one of that kind is refused or ""): a malformed one
    refuses all of its kind, since what it meant cannot be told."""
    found = None
    decisions = scope.get("decisions") if isinstance(scope, dict) else None
    for i, d in enumerate(decisions if isinstance(decisions, list) else []):
        if not isinstance(d, dict) or kind not in d:
            continue
        why = problem(d)
        if why:
            return None, f"decision {i + 1} of the reviewed scope is no statement the kit reads ({why})"
        found = d
    return found, ""


def cards_refused(scope) -> str:
    """Why the scope holds no current blank-cards statement (in plain words, with what to do), or "" when its latest
    cards statement says "blank"."""
    got, why = latest(scope, "cards")
    if why:
        return f"{why}: {CARDS_HOW}"
    if got is None:
        return f"the camera's reviewed scope holds no blank-cards statement: {CARDS_HOW}"
    if got["cards"] != "blank":
        return f"the owner withdrew the blank-cards statement on {got['date']}: {CARDS_HOW}"
    return ""


def agent_shell(env=None) -> str:
    """The marker of an agent's shell in the environment (AGENT_MARKERS), or ""."""
    env = os.environ if env is None else env
    return next((k for k in AGENT_MARKERS if str(env.get(k) or "").strip()), "")


def typed(prompt: str, read=None, tty=None) -> str | None:
    """What the person at a real terminal typed after `prompt` (printed first), "" when the input ended or was
    interrupted, None when standard input is no terminal (a pipe, a file, an agent's shell). `read`: input, unless
    given; `tty`: sys.stdin.isatty(), unless given. kit/drive.py's typed_word asks the owner route's question so."""
    tty = sys.stdin.isatty() if tty is None else tty
    if not tty:
        return None
    print(prompt, flush=True)
    try:
        return (read or input)("> ")
    except (EOFError, KeyboardInterrupt):
        return ""


def ask(question: str, word: str, read=None, tty=None, env=None) -> str:
    """Why the person did not answer `question` with `word`, or "" when they typed it (compared as safety.plain
    compares names): refused before anything is printed in a shell an agent started (agent_shell) and where standard
    input is no terminal (typed). The question is printed with the word to type and the words that only the camera's
    owner answers it."""
    marker = agent_shell(env)
    if marker:
        return (f"this shell says an agent started it ({marker} is set): only the camera's owner answers this question, "
                "in a terminal of their own")
    got = typed(f"{question}\nOnly the camera's owner answers this. Type {word} to say so; anything else stops.", read,
                tty)
    if got is None:
        return ("this question needs the camera's owner at a terminal, and standard input is no terminal: run it in "
                "your own terminal")
    if safety.plain(got) != safety.plain(word):
        return f"the answer was not {word!r}: nothing was written"
    return ""


def today() -> str:
    return datetime.date.today().isoformat()


def add(scope_file: Path, scope: dict, entry: dict) -> Path:
    """`entry` (a statement: problem() refuses anything else) appended to the scope's decisions and the scope written to
    `scope_file` whole, through a file beside it renamed over it."""
    why = problem(entry)
    if why:
        raise ValueError(f"not a statement: {why}")
    scope = dict(scope)
    scope["decisions"] = [*(scope.get("decisions") or []), entry]
    scope_file = Path(scope_file)
    scope_file.parent.mkdir(parents=True, exist_ok=True)
    part = scope_file.with_name(scope_file.name + ".part")
    part.write_text(json.dumps(scope, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(part, scope_file)
    return scope_file
