"""Vision-language readers: OpenAI-compatible servers (the local omlx, vLLM on the LAN, or a hosted
service with "api_key_env") and Claude (camkit.claude_reader), in parallel.

Each reader answers the same question about the same frame; the callers decide what the readers agree on (a label two
sources read alike: page_model.py's vote, pass1_map.py, tiebreak.py) and flag the rest for review.
Answers are cached under the camera's runs (runs/<model>_fw<fw>/_cache/vlm) by image + prompt + model, so re-reads
are free (cache_key, cached, keep: every reader keeps its answers the same way).
Readers and endpoints come from private/config.json ("readers"). A camera run that asks a reader checks, before it
opens the link (check_readers), that its OCR engines are ones the kit knows and that a reader it can use answers a
real question: each is asked to read CHECK_TEXT off a small picture drawn here (check_picture), through the same
request a run's question makes, and with none answering the run stops there. kit/tools/reader_check.py asks the same
with no camera. Inside a run a missing reader is an ordinary exception (NoReader).

Every question a run asks about a frame goes through ask_role, which takes up a stand-in when the reader playing the
role will not connect, and says once per reader, on standard error and in the run's events.jsonl, when one first fails
during the run. The batch tools that read a whole run's frames afterwards build their readers themselves
(make_reader) and get no stand-in: kit/tiebreak.py, kit/pass1_labels.py, kit/page_model.py and kit/help_reads.py;
kit/tools/reader_census.py --questions, which measures the questions themselves on recorded frames, asks a reader it
names through ask_named_reader. A --network run (docs/decisions/0008) asks local readers only (LOCAL_ONLY) and marks
its run folder so (LOCAL_MARKER); every tool that reads a run folder's frames afterwards looks for that mark
(local_only_runs) before it builds a reader, and make_reader builds no reader that is not local while LOCAL_ONLY is
set. PROMPTS holds the questions the kit asks today and, beside them, one question per kind of
screen (the ".v2" keys, camkit.reading.QUESTIONS), which no run asks yet.
"""
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import ConfigMissing, config, paths

CACHE = None          # the answers' folder when set (the tests); else the camera's, cache_dir()


def cache_dir() -> Path:
    """runs/<model>_fw<fw>/_cache/vlm: the readers' answers, beside the camera's runs (camkit.paths)."""
    return Path(CACHE) if CACHE is not None else paths.run_root() / "_cache" / "vlm"


def cache_key(image: bytes, prompt: str, model: str) -> str:
    """The name an answer is kept under: the frame's bytes, the question and the model."""
    return hashlib.sha1(image + prompt.encode() + model.encode()).hexdigest()


def usable(answer) -> bool:
    """An answer that can be read: a JSON object, neither garbled ({"_unparsed": ...}, not JSON) nor a refusal
    ({"_error": ...}, camkit.claude_reader). Neither is ever kept (keep, ClaudeReader.ask), so a kept answer that is
    not usable is a file an older kit, a crash or another tool left: asked again."""
    return isinstance(answer, dict) and "_unparsed" not in answer and "_error" not in answer


def cached(key: str, folder=None) -> dict | None:
    """The answer kept under key (in folder, default cache_dir()), or None: none kept, or one that is not usable (a
    file a crash or another thread left unreadable, a garbled answer an older kit kept): asked again."""
    try:
        answer = json.loads((Path(folder or cache_dir()) / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return answer if usable(answer) else None


def keep(key: str, answer: dict, folder=None) -> dict:
    """The answer, kept under key (in folder, default cache_dir()) unless it is not usable (a garbled answer is asked
    again next time). Written whole or not at all: readers ask in parallel, and two threads can keep the same frame's
    answer at once. The cache is best effort: a write that fails (a full disk; on Windows, replacing a file another
    thread is reading) keeps nothing and leaves no part file, and the answer, paid for with a hosted reader, still goes
    back to the caller."""
    if not usable(answer):
        return answer
    f = Path(folder or cache_dir()) / f"{key}.json"
    part = f.with_name(f"{f.name}.{os.getpid()}.{threading.get_ident()}.part")
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        part.write_text(json.dumps(answer), encoding="utf-8")
        part.replace(f)
    except OSError:
        with contextlib.suppress(OSError):
            part.unlink()
    return answer


PROMPTS = {
    "dialog": (
        "This is a Sony camera menu screen showing one setting's options. Reply with JSON only:\n"
        '{"title": the white title at the top, "selected": the full orange text line under the title '
        '(the selected option\'s name), "values": any other value text visible (list), '
        '"footer": the button labels in the bottom bar (list)}'),
    "menu": (
        "This is a Sony camera menu page. Reply with JSON only:\n"
        '{"breadcrumb": the text at the top left, "page": the n/N page counter at the top right, '
        '"rows": [{"label": row label, "value": value shown at the right or "", '
        '"greyed": true if the row text is grey, "highlighted": true for the row with the orange bar}]}'),
    "notice": (
        "This is a message on a Sony camera screen. Reply with JSON only:\n"
        '{"text": the full message text, "buttons": button labels (list)}'),
    "option": (
        "This is a Sony camera settings screen. Reply with JSON only:\n"
        '{"title": the title of the screen, "selected": the exact text of the item under the CURSOR: '
        'the item on the orange bar, or in the orange box, or the orange line under the title. A radio '
        'button with an orange dot marks the SAVED value, which can be a different item: do not use it. '
        '"value": the value shown with the cursor item, or ""}'),
    "fields": (
        "This is a Sony camera number-entry screen. Reply with JSON only:\n"
        '{"title": the title, "fields": [the value in each box, left to right, with its unit], '
        '"active": index of the orange box}'),
    "any": (
        "Describe this Sony camera screen. Reply with JSON only:\n"
        '{"kind": one of menu_page | dialog | checkbox_list | number_fields | grid | tiles | notice | '
        'shooting | playback | keyboard | other, "title": main title text, "selected": highlighted item text, '
        '"text": all other visible text (list)}'),
}

# The questions asked one kind of screen at a time (2026-11-13: the owner's "keep OCR as main and VLM as back up,
# maybe we can feed a better prompt to the VLM"; camkit.reading.QUESTIONS says which kind asks which). Each asks for
# exactly the thing the kit reads there, in a pinned form; the three that read a lit item that may be missing (lit.v2,
# cell.v2, stars.v2) say to answer "none" then. The keys above
# keep their text: the answers already cached are keyed by it, and every caller asks them. Nothing asks these during a
# run yet: kit/tools/reader_census.py --questions measures them against the old ones on frames already recorded
# (docs/REMAPPING_PLAYBOOK.md, section 5), and a caller moves onto one only once that has been measured.
_JSON = "Reply with JSON only, on one line: "
PROMPTS.update({
    # the item on the orange bar or in the orange box: a list, a side list, a table's function picker
    "lit.v2": (
        "This is a Sony camera menu screen. One item is highlighted: it sits on an orange bar or inside an orange "
        "box. Copy that item's own text exactly as drawn, every letter, digit, sign and space, in its case. Leave out "
        "any icon, radio button or check box before it and any value written to its right. If no item is "
        "highlighted, write none. " + _JSON + '{"selected": "<the text>"}'),
    # the orange line under a carousel's title: the option, and its second axis's value after a colon
    "carousel.v2": (
        "This is a Sony camera setting screen. At the top is a white title, and right under it one line of orange "
        "text names the option chosen now. Copy that orange line exactly as drawn, all of it, including any part "
        "after a colon. Do not read the icons in the column at the left or the small cells near the bottom. "
        + _JSON + '{"selected": "<the orange line>"}'),
    # the lit cell of a carousel option's second axis, drawn as a strip of cells
    "cell.v2": (
        "This is a Sony camera setting screen. Near the bottom, between a left and a right arrow, is a row of small "
        "cells, and one of them is orange. Copy the text inside the orange cell exactly as drawn: it is short, one to "
        "three letters or digits. If no cell is orange, or the orange cell holds only an icon, write none. "
        + _JSON + '{"selected": "<the text>"}'),
    # every box of a number-entry screen
    "fields.v2": (
        "This is a Sony camera number-entry screen: one or more boxes side by side, each holding a value, and one of "
        "them orange. Read every box from left to right and copy its value exactly as drawn, with its sign or decimal "
        "point, without the unit and without the words above or beside the boxes. "
        + _JSON + '{"fields": ["<first box>", "<second box>"], "active": <the orange box, counted from 0>}'),
    # a Creative Look panel's lit parameter
    "look.v2": (
        "This is a Sony camera Creative Look screen. Along the bottom is a row of boxes, each a small icon and a "
        "value, and one box is orange. Copy the value in the orange box exactly as drawn, with its sign (a plus, a "
        "minus or a plus-minus sign), and the orange word just above the row, which names that value. "
        + _JSON + '{"name": "<the orange word>", "selected": "<the value>"}'),
    # a Creative Look panel's vertical scale: its two ends
    "lookscale.v2": (
        "This is a Sony camera screen with a vertical scale at the right: a column of ticks with a number at its top "
        "end and a number at its bottom end. Copy those two numbers exactly as drawn, with their signs. "
        + _JSON + '{"top": "<the number at the top>", "bottom": "<the number at the bottom>"}'),
    # the value a horizontal scale stands at, written over it
    "scale.v2": (
        "This is a Sony camera setting screen with a horizontal scale: a bar, a row of marks or a line of ticks "
        "between a minus and a plus or between two words. Just above the scale, the value chosen now is written in "
        "orange, with small arrows beside it. Copy that value exactly as drawn, with its sign. "
        + _JSON + '{"selected": "<the value>"}'),
    # a grid of rating stars: the lit box's count
    "stars.v2": (
        "This is a Sony camera screen with boxes of rating stars, and one box is highlighted in orange. Count the "
        "stars drawn in the orange box, every star in every row (they may stand in two or three rows), and write the "
        "count as a digit; if that box shows OFF, write off; if no box is orange, write none. Also say whether its "
        "check box is ticked. "
        + _JSON + '{"selected": "<the count>", "ticked": true or false}'),
    # a list of check boxes: each box's label and whether it is ticked
    "checklist.v2": (
        "This is a Sony camera screen with a list of check boxes. For every check box, copy its label exactly as "
        "drawn and say whether the box is ticked. For a label made only of stars, count every star in every row "
        "(they may stand in two or three rows) and write the count as a digit. Leave out the buttons, such as OK, "
        "Enter or Cancel. "
        + _JSON + '{"boxes": [{"label": "<the label>", "ticked": true or false}]}'),
    # the white balance fine-tune grid's two readouts
    "wbgrid.v2": (
        'This is a Sony camera white balance fine-tune screen: a small colour grid, and two readouts, one starting '
        '"A-B:" and one starting "G-M:". Copy the value after each colon exactly as drawn: a letter and a number, '
        'or 0. ' + _JSON + '{"A-B": "<the value>", "G-M": "<the value>"}'),
    # a message: its text, without its buttons
    "notice.v2": (
        "This is a message on a Sony camera screen. Copy the message exactly as drawn, its lines joined with single "
        "spaces, without the buttons and without any check box under it. Then list the buttons. "
        + _JSON + '{"text": "<the message>", "buttons": ["<a button>"]}'),
    # a screen's title
    "title.v2": (
        "This is a Sony camera screen. Copy the title at the top left exactly as drawn, without any icon before it "
        "and without the page counter at the top right. " + _JSON + '{"title": "<the title>"}'),
})

# A third question, kept where it measured better than the kind's second on the census's sample and not worse on a
# second, held-out one (kit/tools/reader_census.py --questions, its "v3" questions; the candidates not kept stay with
# the census, its CANDIDATES). The second questions keep their text beside it.
PROMPTS.update({
    # title.v2, never the orange line under it, and a turned screen read turned
    "title.v3": (
        "This is a Sony camera screen. Copy its title exactly as drawn: the white text at the top, never the orange "
        "line under it. If the screen is drawn turned, read it turned. Leave out any icon before the title and the "
        "page counter at the top right. " + _JSON + '{"title": "<the title>"}'),
})


def with_options(prompt: str, options) -> str:
    """A question's text (a PROMPTS value) with the options expected there handed to the reader, said just before its
    "Reply with JSON" line: options a list of texts, or {part: [texts]} for a screen read in parts (a number-entry
    screen's boxes, the white balance grid's two readouts), each part said in turn. It tells the reader to copy what
    the screen shows where that is none of them. Whether handing them over helps or makes the reader pick one of them
    against the screen is what kit/tools/reader_census.py --questions measures (its "options" and "decoy" questions);
    nothing asks it during a run."""
    def said(texts) -> str:
        return ", ".join(json.dumps(str(t), ensure_ascii=False) for t in texts)
    if isinstance(options, dict):
        parts = [f"The {part} should be one of these: {said(texts)}." for part, texts in options.items() if texts]
        tail = "If what is drawn is none of them, copy what is drawn instead."
    else:
        parts = [f"It should be one of these: {said(options)}."]
        tail = "If the screen shows something else, copy what it shows instead."
    hint = " ".join(parts + [tail]) + " "
    at = prompt.rfind(_JSON)
    return prompt[:at] + hint + prompt[at:] if at >= 0 else prompt + " " + hint.strip()


def make_reader(cfg: dict, **override):
    """The reader a private/config.json "readers" entry describes: "kind": "anthropic" is Claude
    (camkit.claude_reader), anything else an OpenAI-compatible /v1 server (Reader). While LOCAL_ONLY is set (a --network
    run, or a tool reading a run folder such a run marked: local_only_runs), a reader that is not local
    (local_reader) is never built, and while HELD none is: NoReader, nothing sent (local_only). Every reader the kit
    asks is built here, the batch tools' too."""
    cfg = {**cfg, **override}
    local_only(cfg)
    if cfg.get("kind") == "anthropic":
        from .claude_reader import ClaudeReader
        return ClaudeReader(**cfg)
    return Reader(**cfg)


NO_READER = ("private/config.json lists no reader: copy the ones you choose from \"readers_examples\" into \"readers\" "
             "(docs/QUICKSTART.md, \"Choosing a reader\")")


class NoReader(LookupError):
    """No reader to ask: private/config.json lists none (kit/config.example.json lists none, so a copy of it asks no
    server anything until its owner has chosen one, 2026-11-13), or none for a role. An ordinary exception, never a
    SystemExit: inside a camera run every caller of a reader takes it as a reader that could not answer, as it took the
    IndexError and KeyError this was before, so the run's own cleanup and restore go on as ever. A camera run that
    asks a reader finds a missing list before it opens the link (check_readers), and the batch tools with no camera
    stop on it with its message (readers(stop=True))."""


def _settings() -> dict:
    """private/config.json, or {} when there is none: a missing file is a missing reader list here (NoReader), never a
    ConfigMissing (a SystemExit) in the middle of a run."""
    try:
        return config()
    except ConfigMissing:
        return {}


def readers(stop: bool = False, settings: dict | None = None) -> list:
    """The readers private/config.json lists ("readers"), or `settings` (the config a caller has read already). None
    listed raises NoReader, saying what to do; stop: raises ConfigMissing instead, which ends the program with that
    sentence (the batch tools with no camera, and check_readers), and no private/config.json at all ends it with
    config()'s own."""
    if settings is None:
        settings = config() if stop else _settings()
    listed = settings.get("readers") or []
    if not listed:
        raise (ConfigMissing if stop else NoReader)(NO_READER)
    why = malformed(listed, settings.get("roles") or {})    # "roles": null is as none given
    if why:
        raise (ConfigMissing if stop else NoReader)(
            f"private/config.json: {why}: each reader is an object with a \"name\" of its own, as in \"readers_examples\", "
            f"and \"roles\" an object giving a role a reader's name, {{\"second\": \"omlx\"}} (docs/QUICKSTART.md, "
            f"\"Choosing a reader\")")
    return listed


def malformed(listed, roles=None) -> str:
    """Why private/config.json's "readers" (and "roles") cannot be read as readers ("" when it can): not a list, an
    entry that is no object, one with no "name", two with the same one, or "roles" that is no object of names. Said by
    its place in the list, never by what it holds."""
    if roles is not None and (not isinstance(roles, dict) or not all(isinstance(v, str) for v in roles.values())):
        return "\"roles\" is not an object giving each role a reader's name"
    if not isinstance(listed, list):
        return "\"readers\" is not a list"
    names = set()
    for i, r in enumerate(listed, 1):
        if not isinstance(r, dict):
            return f"entry {i} of \"readers\" is not an object"
        name = r.get("name")
        if not isinstance(name, str) or not name.strip():
            return f"entry {i} of \"readers\" has no \"name\""
        if name in names:
            return f"two entries of \"readers\" have the name {name!r}"
        names.add(name)
    return ""


def check_readers() -> list:
    """The start check of a camera run, called by every run that asks a reader (each one that builds a LiveCamera, and
    runner.prover_session for the provers) before it opens the link; the Checks (start_check). In order: the readers
    listed (a config that lists none, no config at all, or one that cannot be read, said in a sentence with no path in
    it, unreadable, stops it), the OCR engines (camkit.reading.check_engines: a name the kit does not know stops the
    run), and each reader the run can use asked a real question (start_check:
    none answering, or the second reader not answering with no local reader to stand in, stops it, naming each reader
    and what it said or which error, and what to do). All three stop with ConfigMissing, before anything is pressed or
    downloaded. A reader that does not answer is skipped for the run: a local one that answered stands in for it in
    its role as a stand-in would (stand_in; never a paid one), and a role left with none goes unanswered for the run,
    each of its questions taken as no answer at once (ask_role). A healthy config's readers play their roles as ever.
    Asked once per process: a run that calls it again (a prover with a second session) is not asked again. A run
    that asks no reader (page_scan, selftest, identify) and a restore (mode_switch --restore, pass 3's, prove_run's
    start file put back with nothing to prove) never check. Until 2026-11-13 a run went on with OCR alone when no
    reader was listed, and until the start check asked a question, when the readers listed did not answer."""
    from . import reading
    try:
        readers(stop=True)          # the config read first: check_engines takes any ValueError for an unknown engine
    except CONFIG_FAULTS as e:      # not JSON, not a file that opens, not the shape the kit reads: one plain sentence
        raise ConfigMissing(unreadable(e)) from None
    role_players()                  # any other fault is the kit's, raised as itself, still before the link
    reading.check_engines()
    if _CHECKED is None:
        _passed(start_check())
    return list(_CHECKED)


# What reading private/config.json raises when the file is not JSON (ValueError), does not open (OSError) or is not
# the shape the kit reads (TypeError, AttributeError: a list where an object goes); unreadable says it in words
CONFIG_FAULTS = (ValueError, TypeError, AttributeError, OSError)


def unreadable(e: BaseException) -> str:
    """What is wrong with a private/config.json the kit cannot read (CONFIG_FAULTS), in one plain sentence naming
    neither a path nor what the file holds: not JSON (the line and column to fix), not a file that opens, or not the
    shape the kit reads. It never says to copy the example over it: the file holds the person's own settings."""
    shape = "kit/config.example.json shows the shape the kit reads (docs/QUICKSTART.md, step 3)"
    if isinstance(e, json.JSONDecodeError):
        return (f"private/config.json is not valid JSON at line {e.lineno}, column {e.colno} ({e.msg}): fix that line; "
                f"{shape}")
    if isinstance(e, OSError):
        return f"private/config.json cannot be opened ({type(e).__name__}): check that it is a file you can read"
    return (f"private/config.json is not in the shape the kit reads ({type(e).__name__}): it must be one JSON object, "
            f"with \"readers\" a list of objects and \"roles\" an object of names; {shape}")


# ------------------------------------------------------------------------------------------------ the start check

CHECK_TEXT = "MENU 42"       # what the check's picture says, and what a reader must read off it
CHECK_PROMPT = "notice"      # the question asked about it, one of a run's own (PROMPTS)
CHECK_TIMEOUT = 25.0         # s a reader gets to answer it: what a proof's question gets (camkit.reading.TIMEOUTS)
CHECK_WAITS = (2, None)      # a busy gateway (502/503/504) is asked once more after 2 s, where a run's question waits more
NO_ANSWER = "no answer"      # a Check's error when the reader was still busy at the deadline
CHECK_SLACK = 5.0            # s past a reader's tries and pauses before the check stops waiting for it (ask_checks)


def paid(cfg: dict) -> bool:
    """A reader that costs money per question: Claude ("kind": "anthropic") or a hosted service, which names the
    environment variable holding its key ("api_key_env": OpenAI, Gemini). It plays only the roles private/config.json
    gives it ("roles", or its place in "readers") and never stands in for another (may_stand_in); the start check
    asks it when it is the second reader, as every proof does, and as the third only when no local reader answered."""
    return cfg.get("kind") == "anthropic" or bool(cfg.get("api_key_env"))


def may_stand_in(cfg: dict) -> bool:
    """A reader the kit may bring in by itself for one that does not answer (stand_in, start_check): a local one, never
    a paid one (paid), which would make every question of the run cost money though the config never gave it the
    role (the owner's decision, 2026-11-13)."""
    return not paid(cfg)


def kind_of(cfg: dict) -> str:
    """A reader's kind in words: "anthropic", or "openai-compatible" for a server or service (Reader)."""
    return "anthropic" if cfg.get("kind") == "anthropic" else "openai-compatible"


def _last_part(model) -> str:
    """A model id's last part when it holds a path separator, else the id."""
    text = str(model or "")
    return re.split(r"[/\\]+", text.rstrip("/\\"))[-1] if ("/" in text or "\\" in text) else text


def shown_model(model) -> str:
    """A model id as the kit prints it: its last part when it holds a path separator (a local path names a folder of
    the person's own; a repository id's owner goes too), scrubbed, never taken for a key (scrub's keep)."""
    text = _last_part(model)
    return scrub(text, keep=(text,))


# What scrub replaces in a text the kit prints or logs about a reader: a server's own message can echo an address, a
# key or a folder. The patterns are a small cousin of kit/tools/check_public.py's (not importable from camkit).
_SCRUBS = [
    (re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"<>)\]]+"), "<address>"),                      # any URL
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"), "<e-mail>"),
    (re.compile(r"(?:\b[A-Za-z]:)?[/\\]{1,2}(?:home|Users|users|mnt/[a-z]/users)[/\\]{1,2}[^/\\\s'\"]+"), "<home>"),
    (re.compile(r"\b(?:Bearer|Basic)\s+\S+|\b(?:sk|pk|rk)-[A-Za-z0-9_-]{6,}|\bAIza[0-9A-Za-z_-]{20,}"), "<key>"),
    (re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"), "<address>"),
    (re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?![\d.])"), "<address>"),
    (re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:local|lan|home|internal|localdomain|intranet)\b", re.I), "<address>"),
]
_IP6 = re.compile(r"(?<![\w.:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?:%[\w.-]+)?(?![\w:])")
# a key with no prefix: an unbroken run of 32 letters and digits or more, as keys are; a long model id is words joined
# by hyphens or underscores ("Qwen3-VL-30B-A3B-Instruct-AWQ-4bit") and is never one. The model ids private/config.json
# names, and the one a server says answered, are kept from this rule (scrub's keep)
_OPAQUE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{32,}(?![A-Za-z0-9])")
_TOKEN = r"(?<![\w.-]){}(?![\w.-])"            # a configured text, matched only as a whole token


def _ip6(m) -> str:
    import ipaddress
    try:
        ipaddress.ip_address(m.group(0).split("%")[0])
    except ValueError:
        return m.group(0)
    return "<address>"


def _configured(listed) -> tuple:
    """({the pattern of a configured address or key: (the length of its text, what it is replaced by)}, the configured
    model ids' last parts) for the readers listed. A host name with no dot ("gpu") is matched only where it is written
    as an address: after "//" or "@", or before a port; never as a word of a sentence ("the gpu is busy")."""
    known, models = {}, set()
    for r in listed if isinstance(listed, list) else []:
        if not isinstance(r, dict):
            continue
        if isinstance(r.get("model"), str) and _last_part(r["model"]).strip():
            models.add(_last_part(r["model"]).strip())
        url = r.get("url")
        if isinstance(url, str) and url.strip():
            host = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", url.strip()).split("/")[0]
            bare = host.rsplit("@", 1)[-1]
            name = bare.split(":")[0]
            for h in (url.strip().rstrip("/"), host, bare):
                if len(h) > 2 and ("." in h or ":" in h or "/" in h):
                    known[re.escape(h)] = (len(h), "<address>")
            if len(name) > 2:
                n = re.escape(name)
                known[n if "." in name else rf"(?:(?<=//)|(?<=@)){n}|{n}(?=:\d)"] = (len(name), "<address>")
        key = os.environ.get(r["api_key_env"]) if isinstance(r.get("api_key_env"), str) else None
        if key and len(key) > 3:
            known[re.escape(key)] = (len(key), "<key>")
    return known, models


def scrub(text, listed: list | None = None, keep=()) -> str:
    """text with what could name the person's network or keys taken out, for the terminal and a run's events.jsonl:
    every address and host a reader of private/config.json (or of listed) names, each as a whole token, every key a
    reader's "api_key_env" holds, and anything that looks like an address (a URL, an IPv4 or IPv6 address, a MAC
    address, a .local host), a key (a bearer token, sk-..., an unbroken run of 32 letters and digits or more), an e-mail
    address or a home folder. The configured model ids' last parts and keep (the model a server says answered) are
    never taken for a key. Never raises: a config that cannot be read scrubs by the patterns alone."""
    text = str(text)
    if listed is None:
        try:
            listed = _settings().get("readers") or []
        except Exception:        # noqa: BLE001 - an unreadable config: the patterns alone
            listed = []
    known, models = _configured(listed)
    for pattern, word in _SCRUBS:   # a URL whole first, a configured host inside it with it
        text = pattern.sub(word, text)
    text = _IP6.sub(_ip6, text)
    for pattern in sorted(known, key=lambda p: known[p][0], reverse=True):      # the longest text first
        text = re.sub(_TOKEN.format(f"(?:{pattern})"), known[pattern][1], text)
    held = []

    def hold(m):                    # a kept id out of the way of the rule, put back after it
        held.append(m.group(0))
        return f"\x00{len(held) - 1}\x00"
    for k in sorted({k for k in (*models, *(_last_part(x).strip() for x in keep)) if k}, key=len, reverse=True):
        text = re.sub(_TOKEN.format(re.escape(k)), hold, text)
    text = _OPAQUE.sub("<key>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], text)


def check_picture() -> bytes:
    """The start check's picture, as a PNG: CHECK_TEXT in white on black, at the size of the kit's frames (640 x 480,
    camkit.frames)."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = 640, 480
    try:
        font = ImageFont.load_default(size=88)
        image = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(image)
        x0, y0, x1, y1 = draw.textbbox((0, 0), CHECK_TEXT, font=font)
        draw.text(((w - (x1 - x0)) // 2 - x0, (h - (y1 - y0)) // 2 - y0), CHECK_TEXT, font=font, fill="white")
    except (ImportError, OSError, TypeError):        # a Pillow without FreeType: its bitmap font, drawn small and enlarged
        small = Image.new("RGB", (w // 8, h // 8))
        ImageDraw.Draw(small).text((14, 25), CHECK_TEXT, fill="white")
        image = small.resize((w, h), Image.NEAREST)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class Check:
    """One reader at the start check: its configured name, kind and model (as shown_model prints it), whether it costs
    money (paid), the roles it plays ("second", "third"), whether it was asked and, if not, why; whether its answer read
    CHECK_TEXT (ok), how long it took (seconds), what it read (said), when it did not answer right, why (error), and
    the model the server says answered where that is another id than the configured one (served). Every text in it is
    scrubbed (scrub)."""
    name: str
    kind: str
    model: str
    paid: bool
    roles: tuple = ()
    asked: bool = False
    not_asked: str = ""
    ok: bool = False
    seconds: float | None = None
    said: str = ""
    error: str = ""
    served: str = ""

    def who(self) -> str:
        """The reader as the messages name it: 'name', with its roles and whether it costs money."""
        notes = [f"{r} reader" for r in self.roles] + (["paid"] if self.paid else [])
        return repr(self.name) + (f" ({', '.join(notes)})" if notes else "")

    def outcome(self) -> str:
        """What came of it, in words."""
        if not self.asked:
            return f"not asked: {self.not_asked}"
        if self.ok:
            return f"answered in {self.seconds:.1f} s"
        return f"did not answer right: {self.error}"


def server_says(e: urllib.error.HTTPError) -> str:
    """The short message an HTTP error's body gives (an OpenAI-style {"error": {"message": ...}}, a {"detail": ...}, or
    its first words), or ""."""
    try:
        text = (e.read(4096) or b"").decode("utf-8", "replace").strip()
    except Exception:            # noqa: BLE001 - the body is only words for the message
        return ""
    try:
        body = json.loads(text)
    except ValueError:
        body = None
    if isinstance(body, dict):
        said = next((body[k] for k in ("error", "detail", "message") if body.get(k)), "")
        if isinstance(said, dict):
            said = said.get("message") or said.get("type") or ""
        text = said if isinstance(said, str) else json.dumps(said)
    text = " ".join(text.split())
    return text if len(text) <= 160 else text[:157] + "..."


def failure(e: BaseException, timeout: float | None = None) -> str:
    """Why a reader gave no answer, in words: the HTTP status, its reason and the server's own short message ("HTTP 507
    Insufficient Storage: ..."), a timeout, a refused connection, or the exception; scrubbed (scrub)."""
    if isinstance(e, urllib.error.HTTPError):
        said = server_says(e)
        return scrub(f"HTTP {e.code} {e.reason}".rstrip() + (f": {said}" if said else ""))
    reason = e.reason if isinstance(e, urllib.error.URLError) else e
    if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower() or "timeout" in type(e).__name__.lower():
        return f"no answer within {timeout:g} s (timed out)" if timeout else "timed out"
    if isinstance(e, urllib.error.URLError):
        return scrub(f"could not connect ({getattr(reason, 'strerror', None) or reason})")
    status = getattr(e, "status_code", None)               # the Anthropic SDK's errors
    if status:
        return scrub(f"HTTP {status}: {getattr(e, 'message', None) or e}"[:300])
    return scrub(f"{type(e).__name__}: {e}"[:300])


def url_refused(cfg: dict) -> str:
    """Why an OpenAI-compatible reader's "url" cannot be asked, naming only the reader's entry, never the text in it
    (it is an address): none, or one with no http:// or https:// in front. "" when it can, and for Claude, which has
    no url."""
    if cfg.get("kind") == "anthropic":
        return ""
    url = cfg.get("url")
    if not isinstance(url, str) or not url.strip():
        return "its entry in private/config.json has no \"url\""
    if not re.match(r"(?i)https?://\S", url.strip()):
        return "its \"url\" in private/config.json does not start with http:// or https://"
    return ""


def _texts(answer) -> list:
    """Every text in an answer, nested lists and objects included."""
    if isinstance(answer, dict):
        return [t for v in answer.values() for t in _texts(v)]
    if isinstance(answer, list):
        return [t for v in answer for t in _texts(v)]
    return [str(answer)] if isinstance(answer, (str, int, float)) and not isinstance(answer, bool) else []


def _folded(text: str) -> str:
    return re.sub(r"[\W_]", "", text).casefold()


def reads_check_text(answer) -> bool:
    """The answer reads CHECK_TEXT and nothing else, case, spacing and signs aside ("MENU 42", "Menu42"; never "MENU
    420" or "SUBMENU 42"): its "text", or, when it has no "text", all its texts joined."""
    text = answer.get("text") if isinstance(answer, dict) else None
    if not isinstance(text, str):
        text = " ".join(_texts(answer))
    return _folded(text) == _folded(CHECK_TEXT)


def ask_check(cfg: dict, image: bytes, timeout: float = CHECK_TIMEOUT, roles: tuple = ()) -> Check:
    """One reader asked the start check's question about image (check_picture) through the request a run's question
    makes (make_reader, the reader's answer), with nothing looked up in or kept to the answers' cache; one whose url
    cannot be asked is not sent anything (url_refused). Never raises."""
    c = Check(str(cfg.get("name")), kind_of(cfg), shown_model(cfg.get("model")), paid(cfg), tuple(roles), asked=True)
    t = time.monotonic()
    refused = url_refused(cfg)
    if refused:
        c.error, c.seconds = refused, 0.0
        return c
    reader = None
    try:
        reader = make_reader(cfg, timeout=timeout)
        answer = reader.answer(image, PROMPTS[CHECK_PROMPT], waits=CHECK_WAITS)
    except Exception as e:       # noqa: BLE001 - every failure is the reader's error, said
        c.error = failure(e, timeout)
    else:
        if not isinstance(answer, dict) or "_unparsed" in answer:
            raw = " ".join(str(answer.get("_unparsed", answer) if isinstance(answer, dict) else answer).split())
            c.error = scrub(f"its answer was no JSON object: {raw[:80]!r}" if raw else "its answer was empty")
        elif "_error" in answer:
            c.error = scrub(str(answer["_error"])[:300])
        else:
            said = answer.get("text") if isinstance(answer.get("text"), str) else " ".join(_texts(answer))
            c.said = scrub(" ".join(said.split())[:80])
            c.ok = reads_check_text(answer)
            if not c.ok:
                c.error = f"it read {c.said!r} where the picture says {CHECK_TEXT!r}"
    served = str(getattr(reader, "served", None) or "").strip()
    configured = str(cfg.get("model") or "").strip()
    # the raw ids compared first, then what is printed: a path before the same name is no other model
    if served and served.casefold() != configured.casefold() and shown_model(served).casefold() != c.model.casefold():
        c.served = shown_model(served)
    c.seconds = time.monotonic() - t
    return c


def ask_checks(cfgs: list, image: bytes, timeout: float = CHECK_TIMEOUT, roles: dict | None = None) -> list:
    """ask_check for each reader at once, in threads of their own, so that the check takes as long as the slowest
    reader, not their sum: Checks in the order given. A reader still busy past the deadline (its tries and its pause
    on a busy gateway) is no answer."""
    roles = roles or {}
    out = [None] * len(cfgs)
    lock, closed = threading.Lock(), []

    def one(i, cfg):
        c = ask_check(cfg, image, timeout, roles.get(cfg.get("name"), ()))
        with lock:
            if not closed:              # a reader that answers after the deadline changes nothing
                out[i] = c
    threads = [threading.Thread(target=one, args=(i, cfg), daemon=True) for i, cfg in enumerate(cfgs)]
    deadline = time.monotonic() + timeout * len(CHECK_WAITS) + sum(w or 0 for w in CHECK_WAITS) + CHECK_SLACK
    for th in threads:
        th.start()
    for th in threads:
        th.join(max(0.0, deadline - time.monotonic()))
    with lock:
        closed.append(True)
        got = list(out)
    for i, cfg in enumerate(cfgs):
        if got[i] is None:
            got[i] = Check(str(cfg.get("name")), kind_of(cfg), shown_model(cfg.get("model")), paid(cfg),
                           tuple(roles.get(cfg.get("name"), ())), asked=True,
                           error=f"{NO_ANSWER} within {timeout:g} s (timed out)")
    return got


def role_players() -> dict:
    """{reader name: (the roles it plays)} for the readers private/config.json lists ("second", "third": role); a
    "roles" entry naming no reader listed is refused there (ConfigMissing), where during a run it would fail every
    question."""
    players: dict = {}
    for name in ("second", "third"):
        try:
            cfg = role(name)
        except NoReader:
            continue
        except ValueError as e:
            raise ConfigMissing(str(e)) from None
        players.setdefault(cfg["name"], ())
        players[cfg["name"]] += (name,)
    return players


def _unasked(r: dict, roles: tuple, why: str) -> Check:
    return Check(str(r["name"]), kind_of(r), shown_model(r.get("model")), paid(r), tuple(roles), not_asked=why)


# why a reader is not asked during a --network run (LOCAL_ONLY): verdict takes a local stand-in for its role
NOT_LOCAL = "not a local reader, and a --network run asks only local readers (docs/decisions/0008)"


def plan(listed: list, players: dict, ask_paid: str = "needed") -> tuple:
    """(the readers asked first, the paid ones asked only when no local reader of the first answered, the Checks of
    those never asked), in the order listed. The readers a run can use: each local one (it plays a role or may stand
    in, may_stand_in) and each paid one that plays a role (it never stands in). A paid second reader is asked with the
    local ones: a run asks it on every proof, so one question more costs nothing by comparison, and a second reader
    that does not answer (a key not set) must be found before the link. ask_paid: "needed" (the run's rule: a paid
    third reader only when no local one answered), "all" (kit/tools/reader_check.py --all: every reader listed, paid
    or not, used by a run or not) or "never" (reader_check.py --local, which kit/setup.py runs: never a paid one)."""
    first, later, skipped = [], [], []
    for r in listed:
        roles = players.get(r["name"], ())
        if LOCAL_ONLY and not local_reader(r):
            skipped.append(_unasked(r, roles, NOT_LOCAL))
        elif ask_paid == "all" or not paid(r):
            first.append(r)
        elif not roles:
            skipped.append(_unasked(r, roles, "a run never asks it: a paid reader plays only the roles private/"
                                              "config.json gives it, and stands in for none (--all asks it)"))
        elif ask_paid == "never":
            skipped.append(_unasked(r, roles, "paid: not asked with --local (a run asks it as the second reader, as "
                                              "the third when no local reader answers; --all asks it)"))
        elif "second" in roles:
            first.append(r)
        else:
            later.append(r)
    return first, later, skipped


def start_check(ask_paid: str = "needed", timeout: float = CHECK_TIMEOUT, say=print) -> list:
    """Each reader a run can use asked the start check's question (plan, ask_checks): the local ones and a paid second
    reader first and at once, a paid third reader only when no local one answered (each question to it costs money:
    say says so first); the Checks of all the readers listed, in their order. No reader listed, or an entry that is no
    reader, raises ConfigMissing (readers). Asks; decides nothing: verdict says what a run makes of the Checks."""
    listed = readers(stop=True)
    players = role_players()
    first, later, skipped = plan(listed, players, ask_paid)
    image = check_picture()
    checks = ask_checks(first, image, timeout, players)
    left = list(later)
    if later and not any(c.ok and not c.paid for c in checks):
        say(f"no local reader answered: asking the paid third reader {', '.join(repr(r['name']) for r in later)} "
            f"(each question costs money)")
        checks += ask_checks(later, image, timeout, players)
        left = []
    for r in left:
        skipped.append(_unasked(r, players.get(r["name"], ()),
                                "paid, and a local reader answered (kit/tools/reader_check.py --all asks it)"))
    by_name = {c.name: c for c in checks + skipped}
    return [by_name[str(r["name"])] for r in listed if str(r["name"]) in by_name]


def verdict(checks: list) -> tuple:
    """What a run makes of the start check's Checks: (the stand-ins to take up, {role: the config of the reader that
    stands in for the one that did not answer}, and the reason the run cannot start, or "" when it can). The run needs
    a reader for the "second" role, the one asked about the screen: its own, unless it did not answer, then the first
    local reader listed that answered (may_stand_in, as stand_in takes one during a run; never a paid one); the
    "third" role gets a stand-in the same way where one answered, and otherwise goes unanswered for the run (ask_role:
    a run asks it only to break a tie). A paid third reader not asked because a local one answered keeps its role,
    unchecked."""
    listed = readers(stop=True)
    good = [r for r in listed if any(c.name == str(r["name"]) and c.ok for c in checks)]
    stand_ins, why = {}, ""
    for name in ("second", "third"):
        own = next((c for c in checks if name in c.roles), None)
        not_local = own is not None and not own.asked and own.not_asked == NOT_LOCAL      # a --network run's
        if own is None or own.ok or (not own.asked and not not_local):
            continue
        sub = next((r for r in good if str(r["name"]) != own.name and may_stand_in(r)
                    and (local_reader(r) or not LOCAL_ONLY)), None)
        if sub is not None:
            stand_ins[name] = sub
        elif name == "second" and not_local:
            why = (f"the second reader, {own.name!r}, is not a local reader, which a --network run asks only, and no "
                   "local reader answered to stand in for it")
        elif name == "second":
            why = _second_missing(own, checks, listed)
    if not why and not good:
        why = "no reader answered"
    return stand_ins, why


def _second_missing(own: Check, checks: list, listed: list) -> str:
    """Why a run cannot start when its second reader did not answer and no local reader may stand in: which answered,
    and, where a paid reader is listed for another role or none, that it stands in for no other, and how to give it
    the role for one who would pay for it."""
    answered = [c.name for c in checks if c.ok]
    why = ("no reader answered" if not answered else
           f"the second reader, {own.name!r}, did not answer, and no local reader answered to stand in for it "
           f"({', '.join(repr(n) for n in answered)} answered)")
    others = [str(r["name"]) for r in listed if paid(r) and str(r["name"]) != own.name]
    if others:
        one = len(others) == 1
        why += (f"; {', '.join(repr(n) for n in others)} {'is a paid reader' if one else 'are paid readers'} listed but "
                f"not given the second role, and a paid reader never stands in for another: to pay for "
                f"{'it' if one else 'one'} as the second reader, give it the role in private/config.json, "
                f"\"roles\": {{\"second\": {json.dumps(others[0])}}}")
    return why


_CHECKED: list | None = None   # the Checks of the start check that let this process's run start, or None (not checked)
_SKIPPED: set = set()          # the readers that did not answer it: none stands in, none is asked in the role it kept


def _passed(checks: list) -> None:
    """The start check's Checks taken by the run: stops it (ConfigMissing) when it cannot start, naming each reader and
    what came of it, with what to do; else says in a line what came of each, takes up the stand-ins (assign_role) and
    skips for the run the readers that did not answer (_SKIPPED: never brought in as a stand-in, and a role left to
    one goes unanswered, ask_role)."""
    global _CHECKED
    stand_ins, why = verdict(checks)
    if why:
        lines = [f"  {c.who()}: {c.outcome()}" for c in checks]
        raise ConfigMissing(
            f"The start check: {why}, so this run stops before it opens the camera link, and nothing is pressed (a "
            f"reader is required: docs/decisions/0022). Each reader was asked to read {CHECK_TEXT!r} off a small "
            f"picture, as a run asks about the camera's screen:\n" + "\n".join(lines) + "\n"
            "What to do: start each reader's server, or give it what it says it lacks (an HTTP 507 is the server short "
            "of memory or disk, a 503 one still loading its model; a paid reader, its key in the environment variable "
            "its entry names), and check its \"url\" and \"model\" in private/config.json; then "
            ".venv/bin/python kit/tools/reader_check.py asks the same question with no camera (docs/QUICKSTART.md, "
            "\"Choosing a reader\").")
    print("readers: " + "; ".join(f"{c.who()} {c.outcome()}" for c in checks), flush=True)
    for c in checks:
        if c.asked and not c.ok:
            _SKIPPED.add(c.name)
    for name, sub in stand_ins.items():
        own = next(c for c in checks if name in c.roles)
        assign_role(name, sub)
        print(f"reader {own.name!r} {'is not local' if own.not_asked == NOT_LOCAL else 'does not answer'}: "
              f"{sub['name']!r} stands in as the {name} reader for this run", flush=True)
    for name in ("second", "third"):
        own = next((c for c in checks if name in c.roles), None)
        if own is not None and own.name in _SKIPPED and name not in stand_ins:
            print(f"reader {own.name!r} does not answer and no local reader may stand in: the {name} reader's "
                  f"questions go unanswered for this run", flush=True)
    _CHECKED = list(checks)


# ------------------------------------------------------------------------------------------------ during a run

_FAILING: set = set()          # the readers whose failure during this run has been said (failing)
_RUN = None                    # the run whose events.jsonl that is logged in (log_to), or None
# Set by every --network run (runner.network_decided_or_exit: kit/drive.py, kit/crawl_run.py, kit/prove_run.py, which
# may open a Wi-Fi or Bluetooth row a dated owner decision names, docs/decisions/0008): only a local reader (local_reader:
# not paid, and its "url" a loopback, private or link-local address written as such, or localhost) is asked anything.
# The start check asks no other, and takes a local one that answered as the stand-in for a role whose reader is not
# local (plan, verdict); stand_in brings in no other; ask_role raises NoReader for any other before a request is sent,
# cache or not, and the caller takes it as no answer
LOCAL_ONLY = False
# Set while a screen that names the camera's identity, a connection or credentials, or its addresses, is open inside a
# network row (camkit.live.LiveCamera; safety.identity_screen): the reason, or None. ask_role asks no reader at all
# meanwhile, local or not
HELD = None


def log_to(run) -> None:
    """The run whose events.jsonl a reader's failure is logged in (camkit.live.LiveCamera gives it its own run)."""
    global _RUN
    _RUN = run


def failing(cfg: dict, e: BaseException, timeout: float | None = None) -> None:
    """A reader that failed a run's question, said once per reader in the run, on standard error and in the run's
    events.jsonl ("reader_failing"), not once per question: the question itself is still taken as no answer by its
    caller, as ever."""
    name = str(cfg.get("name"))
    if name in _FAILING:
        return
    _FAILING.add(name)
    why = failure(e, timeout)
    print(f"reader {name!r} failed during the run ({why}): each question to it is taken as no answer, the readings go "
          f"on with OCR alone or a local stand-in, and this is said once", file=sys.stderr, flush=True)
    with contextlib.suppress(Exception):
        if _RUN is not None and hasattr(_RUN, "log"):
            _RUN.log("reader_failing", reader=name, why=why)


def forget() -> None:
    """A run's readers' state cleared: the start check's verdict, the readers it skipped, the stand-ins, the failures
    said and the run they are logged in (a new run in the same process; the tests)."""
    global _CHECKED, _RUN, LOCAL_ONLY, HELD
    _CHECKED, _RUN, LOCAL_ONLY, HELD = None, None, False, None
    _SKIPPED.clear()
    _FAILING.clear()
    _STANDING_IN.clear()


def role(name: str) -> dict:
    """The config entry that plays a role: "second" (the second reading beside OCR, asked on every
    proof) or "third" (the tie-breaker where OCR and the second disagree). private/config.json "roles"
    names a reader for each ({"second": "claude"}); without it, the first and second readers listed. No reader for
    the role raises NoReader, an ordinary exception (see there)."""
    c = _settings()
    listed = readers(settings=c)
    named = (c.get("roles") or {}).get(name)
    if named:
        found = next((r for r in listed if r["name"] == named), None)
        if found is None:
            raise ValueError(f"private/config.json: \"roles\" gives the {name} role to {named!r}, which no entry of "
                             f"\"readers\" names ({', '.join(repr(r['name']) for r in listed)})")
        return found
    at = {"second": 0, "third": 1}[name]
    if at >= len(listed):
        raise NoReader(f"private/config.json lists one reader, and the {name} role needs another: add one to "
                       f"\"readers\", or name the reader for it in \"roles\" (docs/QUICKSTART.md, step 3)")
    return listed[at]


_STANDING_IN: dict = {}        # role -> the reader config standing in for one that would not connect, or given it


def assign_role(name: str, cfg: dict) -> None:
    """Give a role ("second", "third") to a configured reader for the rest of the process, as a stand-in is given one
    (kit/tools/reread_proofs.py --reader NAME)."""
    _STANDING_IN[name] = cfg


def standing_in(name: str) -> dict | None:
    """The config entry given a role for the process (assign_role) or standing in for it (stand_in), or None."""
    return _STANDING_IN.get(name)


def playing(name: str) -> dict:
    """The config entry playing a role now: the one given it or standing in (standing_in), else role()."""
    return standing_in(name) or role(name)


def reader_for(name: str, **override):
    """The reader playing a role (`role`), or, once that one has failed to connect, the next configured reader that
    answers, remembered for the process: a server on another machine switched off must not cost every proof its
    reading (2026-11-06). A paid reader (paid) is never chosen as a stand-in: it costs money, so it plays only the
    roles the config gives it."""
    return make_reader(playing(name), **override)


def stand_in(name: str, failed: dict) -> dict | None:
    """After `failed` would not connect: the next local reader that answers a tiny request, kept for the role; never a
    paid one (may_stand_in), nor one that did not answer the run's start check (check_readers)."""
    for r in readers():
        if r["name"] == failed.get("name") or not may_stand_in(r) or r["name"] in _SKIPPED:
            continue
        if LOCAL_ONLY and not local_reader(r):          # not even the tiny request goes to it
            continue
        try:
            make_reader(r, timeout=20).ping()
        except Exception:
            continue
        _STANDING_IN[name] = r
        print(f"reader {failed.get('name')!r} does not answer: {r['name']!r} stands in", flush=True)
        return r
    return None


# the networks a reader's address must be in to count as local: loopback, and the private and link-local ranges (RFC
# 1918, RFC 3927, RFC 4193, RFC 4291), each as (its first address as a number, its prefix length), which
# kit/tools/check_public.py reads as no address of anyone's
_LOCAL_NETS = ((127 << 24, 8), (10 << 24, 8), ((172 << 24) | (16 << 16), 12), ((192 << 24) | (168 << 16), 16),
               ((169 << 24) | (254 << 16), 16), (1, 128, 6), (0xFC << 120, 7, 6), (0xFE80 << 112, 10, 6))


def _local_networks() -> list:
    """_LOCAL_NETS as ipaddress networks (a third number 6: an IPv6 one)."""
    import ipaddress
    out = []
    for net in _LOCAL_NETS:
        address = ipaddress.IPv6Address(net[0]) if len(net) > 2 else ipaddress.IPv4Address(net[0])
        out.append(ipaddress.ip_network((address, net[1])))
    return out


def local_reader(cfg: dict) -> bool:
    """A reader on this computer or on the owner's own network: not paid (paid: no Claude, no "api_key_env"), and its
    "url" an http:// or https:// address whose host is written as a loopback, private or link-local address
    (_LOCAL_NETS), or is localhost. private/config.json marks no reader local or hosted, so a host written as a name
    the kit cannot place (a server's name, which could resolve anywhere) counts as not local."""
    import ipaddress
    import urllib.parse
    if paid(cfg) or cfg.get("kind") == "anthropic" or url_refused(cfg):
        return False
    try:
        host = urllib.parse.urlsplit(str(cfg.get("url")).strip()).hostname or ""
        ip = None if host.lower() == "localhost" else ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    return ip is None or any(ip in net for net in _local_networks() if net.version == ip.version)


def local_only(cfg: dict, name: str | None = None) -> None:
    """NoReader, before anything is sent: while HELD (an identity screen open), for every reader; while LOCAL_ONLY (a
    --network run, or a tool reading a run folder one marked: local_only_runs), for a reader that is not local
    (local_reader). name: the role asked, for the words."""
    what = f"the {name} reader's question goes unanswered" if name else "it is not asked"
    if HELD:
        raise NoReader(f"no reader is asked while {HELD} (docs/decisions/0008), so {what}")
    if LOCAL_ONLY and not local_reader(cfg):
        raise NoReader(f"reader {cfg.get('name')!r} is not a local reader (a paid service, or an address that is not "
                       f"this computer's or a private network's), and frames of a --network run go only to local "
                       f"readers (docs/decisions/0008), so {what}")


# The file a --network run writes in its run folder (runner.log_network_decided): its frames may show what a network or
# identity row holds, so every tool that reads that folder's frames later asks local readers only (local_only_runs)
LOCAL_MARKER = "LOCAL_ONLY"


def mark_local_only(folder) -> Path:
    """LOCAL_MARKER written in a run's folder: a --network run's, whose frames go to local readers only, now and
    whenever a tool reads them (local_only_runs). Returns its path."""
    f = Path(folder) / LOCAL_MARKER
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("frames of a --network run: local readers only (docs/decisions/0008)\n", encoding="utf-8")
    return f


def local_only_runs(*places) -> list:
    """The run folders among `places` (each a run folder, or a file or folder inside one) that hold LOCAL_MARKER, looked
    for in each place and the folders above it up to the runs folder (camkit.paths.runs_top); when any does, LOCAL_ONLY
    is set for the rest of the process, and said once: every reader the tool then builds is a local one (make_reader).
    Where a batch tool resolves the run folders it reads, it calls this before it builds a reader."""
    global LOCAL_ONLY
    try:
        top = paths.runs_top().resolve()
    except Exception:                       # no runs folder known: each place and its parents are looked in
        top = None
    found = []
    for p in places:
        if p is None:
            continue
        here = Path(p).resolve()
        for folder in (here, *here.parents):
            if top is not None and folder == top:
                break
            if (folder / LOCAL_MARKER).is_file():
                found.append(folder)
                break
    found = list(dict.fromkeys(found))
    if found and not LOCAL_ONLY:
        LOCAL_ONLY = True
        print(f"{', '.join(paths.shown(f) for f in found)}: frames of a --network run, so only local readers are asked "
              "(docs/decisions/0008)", file=sys.stderr, flush=True)
    return found


def ask_role(name: str, image: bytes, prompt: str, timeout: float) -> dict:
    """The answer of the reader playing a role ("second", "third"); when it will not connect, the next configured
    reader that answers takes the role for the rest of the run (stand_in): the remote server was off, 2026-11-06.
    Every question a run asks about a frame comes here (proving.screens.ask_second, camkit.live's reader_label and
    submenu_labels, camkit.reading.ask); the batch tools the module docstring names are the exception. A reader that
    fails is said once in the run (failing); the failure goes on to the caller as before. A role whose reader did not
    answer the run's start check, with no reader standing in, raises NoReader at once, asking nothing: every caller
    takes it as no answer, as from a reader that failed, without the timeout each question would cost. While LOCAL_ONLY
    is set, a reader that is not local (local_reader) is never asked, and while HELD none is: NoReader at once, nothing
    sent (local_only)."""
    cfg = playing(name)
    local_only(cfg, name)
    if str(cfg.get("name")) in _SKIPPED:
        raise NoReader(f"reader {cfg.get('name')!r} did not answer the run's start check, and no reader stands in for "
                       f"it: the {name} reader's questions go unanswered for this run")
    try:
        return make_reader(cfg, timeout=timeout).ask(image, prompt)
    except Exception as e:
        failing(cfg, e, timeout)
        if not isinstance(e, urllib.error.URLError) or standing_in(name) is not None or stand_in(name, role(name)) is None:
            raise
    cfg = playing(name)
    local_only(cfg, name)
    try:
        return make_reader(cfg, timeout=max(timeout, 60)).ask(image, prompt)
    except Exception as e:
        failing(cfg, e, max(timeout, 60))
        raise


def ask_named_reader(cfg: dict, image: bytes, prompt: str, cache, timeout: float = 60.0, read_only=(),
                     ask: bool = True) -> dict | None:
    """One question to the reader a private/config.json "readers" entry describes, for a tool that measures the
    questions themselves on frames already recorded (kit/tools/reader_census.py --questions), outside any run: no role,
    no stand-in, no start check. prompt is the question's whole text (a PROMPTS value, or one with_options made); cache
    the folder its answers are kept in, given outright (never cache_dir(), the camera's runs). The answer is keyed as
    the reader keys it (its model, a default one included: make_reader) and comes from cache, else from a folder of
    read_only (another cache, such as a camera's own runs/<model>_fw<fw>/_cache/vlm: looked in, never written), each
    only when usable; else, with ask, it is asked and kept in cache (keep: an answer that is not usable is not kept),
    and without ask (the tool's time is up) None. A failure raises, as the reader raised it."""
    reader = make_reader(cfg, timeout=timeout)
    key = cache_key(image, prompt, str(getattr(reader, "model", None) or cfg.get("model")))
    for folder in (cache, *read_only):
        answer = cached(key, folder)
        if answer is not None:
            return answer
    if not ask:
        return None
    return keep(key, reader.answer(image, prompt), cache)


BUSY_WAITS = (2, 5, 15, None)    # s between a run's tries at a busy gateway (502/503/504), then it gives up


class Reader:
    def __init__(self, name, url, model, parallel=1, timeout=120, kind=None, api_key_env=None, **_):
        self.name, self.url, self.model, self.timeout = name, url.rstrip("/"), model, timeout
        self.api_key_env = api_key_env
        self.slots = threading.Semaphore(parallel)

    def headers(self) -> dict:
        """A hosted service's entry names, in "api_key_env", the environment variable holding its key. The
        key is read from it here, when a request is sent, and goes only into that request's Authorization
        header: never into the config, the cache or a run (2026-11-04). A local server needs no key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key:
                raise RuntimeError(f"reader {self.name}: the environment variable {self.api_key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def ping(self):
        """A tiny request, to tell a server that answers from one that is off."""
        body = {"model": self.model, "max_tokens": 3, "messages": [{"role": "user", "content": "OK"}],
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(self.url + "/chat/completions", json.dumps(body).encode(), self.headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as reply:
            reply.read()

    def ask(self, image: bytes, prompt: str) -> dict:
        """The answer, from the cache when this model has answered this question about this picture, else asked
        (answer) and kept (keep)."""
        key = cache_key(image, prompt, self.model)
        answer = cached(key)
        if answer is not None:
            return answer
        return keep(key, self.answer(image, prompt))

    def answer(self, image: bytes, prompt: str, waits: tuple = BUSY_WAITS) -> dict:
        """The answer asked now, nothing looked up or kept (ask keeps it; the start check asks this way). waits: the
        seconds between tries when the gateway is busy (502/503/504), None ending them."""
        body = {
            "model": self.model, "temperature": 0, "max_tokens": 800,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}},
                {"type": "text", "text": prompt}]}],
        }
        req = urllib.request.Request(self.url + "/chat/completions", json.dumps(body).encode(), self.headers())
        with self.slots:
            for wait in waits:
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as r:
                        reply = json.load(r)
                    break
                except urllib.error.HTTPError as e:
                    # 502/503/504: the gateway is busy or swapping models (2026-10-28); retry, then give up
                    if e.code not in (502, 503, 504) or wait is None:
                        raise
                    time.sleep(wait)
        self.served = reply.get("model") if isinstance(reply, dict) else None     # the model the server says answered
        # a reasoning server can answer with no content at all ("content": null): that is no JSON, asked again
        return parse_json(reply["choices"][0]["message"].get("content") or "")


def parse_json(text: str) -> dict:
    """The JSON object in a model's answer (tolerates ``` fences and surrounding prose)."""
    text = text or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"_unparsed": text}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {"_unparsed": text}
