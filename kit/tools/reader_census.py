"""How often the one reading rule (camkit.reading, docs/decisions/0022) would doubt OCR and ask the reader: counted over
runs already made, before the rule decides anything on the camera.

    .venv/bin/python kit/tools/reader_census.py [WHERE ...] [--model NAME ...] [--json] [--ask [--limit N] [--cache DIR]]
    .venv/bin/python kit/tools/reader_census.py [WHERE ...] --questions [--reader NAME ...] [--per-kind N]
        [--kinds K,...] [--variants old,new,options,decoy] [--minutes M] [--cache DIR] [--json]

WHERE is a camera's run root (runs/<model>_fw<fw>/; by default the camera the kit works on), a run in it, or a path to
either. The tool replays camkit.reading's doubts() and agree() over:
  proofs   each run's proofs.jsonl: the bar's OCR at OK time ("shown") of the option each proof chose ("label"), with
           the labels the run proved on the same row standing for the options expected there, and the vision model's
           reading of that frame: the line's own ("vlm"), else kit/tools/reread_proofs.py's (readings.jsonl), else an
           answer already in the readers' cache (<run root>/_cache/vlm) to the option question about the line's chosen
           frame, by a model private/config.json lists or --model names
  menus    each page model (model.json, kit/page_model.py): each menu row's OCR reading against the row labels of its
           page, beside each vision reader's reading of it: how often finding a row (navigation) would doubt OCR, an
           icon OCR read in front of a row's label left out first where what is left names one row exactly (the
           stakes "find": camkit.reading.icon_left_out), counted as "icon left out"
A proof's label is taken as the option on the screen (the proof chose it there), and the labels proved on its row as
the options expected there: both stand in for what the rule will be given, so the counts are estimates. A number-entry
proof keeps its boxes as one reading, joined by " | " (kit/proving/fields.py writes it so): the tool judges each box
apart, against that box's values on the row, as camkit.reading.read reads one box at a time (FIELD).

It prints counts: readings plain and doubtful per site (a proof's kind, a menu row); each doubt's kind; the letters
outside ASCII by their Unicode names; how OCR, the reader and the proof's option agree, plain and doubtful readings
apart; what the first two votes make of each reading (camkit.reading.outcome); the reader calls the rule would add (a
doubtful reading with no reader reading today); and, for readings OCR and the reader leave apart, what a third vote by
the second OCR engine would settle (camkit.reading.tally) where the run kept that engine's reading: the page models
keep one per row, the proof lines none (the tool says so).
--json prints the same counts as one JSON object, and nothing else on standard output, to send to the maintainer when
asked (the playbook's checks after the change).

The runs are only read: nothing under runs/ is written, and a --cache inside them (the runs folder, or a camera's run
root read) is refused. No reader is asked unless --ask or --questions. With --ask the "second" reader
(camkit.reading.ask: a stand-in when it will not connect, never about a black frame) reads each doubtful proof frame
that has no reading yet, --limit N of them at most, and its answers are kept in --cache (by default a folder in the
system's temporary folder), never in the camera's runs.

--questions measures the reader's questions themselves, before any caller asks a new one: for a sample of each kind
of screen's proof frames (camkit.reading.QUESTIONS: a list, a side list, a table's picker, a scale, a star rating, a
checklist, a number-entry screen's box the proof changed, a carousel, its second axis and that axis's lit cell, a
Creative Look parameter, its scale's ends and its look, the white balance grid, a notice, a title; left out: an
option the screen draws with the same text as another of its row, a checklist longer than a screenful, a frame with
no menu up), --per-kind frames chosen the same way every time (half where the proof's own second reading named
something else than the option proved, half where it named it; a smaller sample is the start of a larger), each
reader named (--reader; by default the second and third readers, a paid one only when named) is asked the questions
the kit asks there today ("old: option", "old: fields", "old: notice"), the kind's new question ("new"), and the new
one with the options expected there handed over ("new + options") or with every option but the one the file proved
("new + decoy": a reader that picks from the list rather than read the screen names another option there, the wrong
pick handing it options can cause), through camkit.vlm.ask_named_reader. Each answer is judged against the option the
proof's file proved: right, another option, no option, or no answer (it holds no reading there), which make the right
rate; "reader failed" (an HTTP error, a timeout, a refusal, an answer that is no JSON object) and "not asked" (the
reader's --minutes passed, or it failed FAIL_RUN times in a row and was asked nothing more) are counted apart. The
answers are kept in --cache (by default a folder in the system's temporary folder); the camera's own answers' cache is
looked in and never written; an answer already kept and usable is taken whatever the time (--minutes 0: those alone).
A notice's and a title's truth is the text the run recorded, not a proof. --per-kind, --variants, --minutes and
--timeout go with --questions alone (said when given without it).
"v3" asks the candidates for a third question (HYPOTHESES: a change to a kind's second aimed at one class of misses,
a crop of the lit item enlarged, a list proof on a carousel asked the carousel's question); --held-out takes a second
sample of the same size from the frames the first does not take, to check a change made on the first, never to tune
on; --truth judges every answer also against a truth checked by eye, a file of {kind: {label as recorded: label as
drawn}} kept outside the repository and the runs (refused inside them, private/ apart), for labels a run recorded as
OCR read an icon or a garbled letter; a fix that would make two of a reading's options one is not made there, and
counted.
Where a proof kept OCR's reading ("shown"), each answer is also counted against it (BOTH): a reader's wrong answer OCR
reads alike is the dangerous case, which OCR-main and reader-backup (decision 22) would not catch. A self-check ("unsure")
in an answer is counted against whether the answer was right; the seconds each question took are said.
--claude-cli MODEL asks a Claude model through the Claude Code command line in print mode, on the person's own
signed-in plan (CliReader: census-only, never a reader a camera run could pick up): one question per call, one call at
a time, the frame alone in a new, empty working folder, the Read tool alone, no settings, memory, MCP servers or
session kept, a minimal system prompt, and of the environment only what it needs to run and find the sign-in
(cli_env: never an API key, a base URL or a Claude Code session's variables, so the plan answers, not a key); its
answers are kept by model, its calls' seconds and tokens are said, and a usage or rate limit stops it at once. A
hosted reader (that, a paid one, or one at an address off the person's own machine and network: is_hosted) is never
sent a frame hosted_refused refuses for any reading it holds (a network run, a menu path or screen text naming the
camera's identity, a connection or a credential, an address on screen, no text read, no menu or option screen), and
every reader of the run is judged on what is left, how many left out said; where two or more readers are asked, where
they part is counted (pairs). --dry-run asks nothing and says what a run would ask each reader; --max-questions caps
it; --parallel asks a local server several questions at once (at most its config's "parallel" and 8); --fail-run sets
the failures in a row after which a reader is asked nothing more.

Decision 16 (docs/decisions/0016): the counts are for the owner's terminal. The tool prints no reading, no label and
no value, only counts, the kinds of sites and doubts and the Unicode names of letters; still, its output is made from
the owner's runs, so it stays out of commits, issues and the docs unless the owner chooses to send the counts.
"""
import argparse
import collections
import contextlib
import io
import ipaddress
import itertools
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import config, jsonl, match, paths, reading, vlm  # noqa: E402

NUMBER_KINDS = {"look", "wbgrid", "fields"}          # proofs whose label is a number set
NOT_READERS = {"ocr", "ocr2", "user", "checked"}     # a page model's sources that are not vision readers
# a label that is a short code: "PP3", "C1", "User2"; never an F-number ("F11" is an aperture, a label that names
# itself among "F1.1" and "F14"), and a shutter time is a number (NUMBERISH)
CODE = re.compile(r"(?!F\d)[A-Za-z]{1,4} ?\d{1,2}")
NUMBERISH = re.compile(r"[\d\s.,/:+\-\"'\u00B1\u2212]+")   # digits and a number's signs (PLUS-MINUS, MINUS SIGN)
SECOND_ENGINE_KEYS = ("shown2", "ocr2")              # where a proof line would keep a second OCR engine's reading


def runs_in(where: Path) -> tuple:
    """(the run root, [the runs]) WHERE names: a run (a folder with proofs.jsonl or model.json) or a run root."""
    if (where / "proofs.jsonl").exists() or (where / "model.json").exists():
        return where.parent, [where]
    found = {p.parent for name in ("proofs.jsonl", "model.json") for p in where.glob(f"*/{name}")}
    return where, sorted(found)


def expect_of(r: dict) -> str:
    """What a proof's option is, as camkit.reading compares it: a number, a short code, or a label."""
    label = str(r.get("label") or "").strip()
    if r.get("kind") in NUMBER_KINDS or r.get("scale") or (re.fullmatch(NUMBERISH, label) and re.search(r"\d", label)):
        return "number"
    return "code" if CODE.fullmatch(label) else "label"


def row_of(run: Path, r: dict) -> tuple:
    """The row a proof is of: its labels there stand for the options expected (one axis, cell or parameter apart)."""
    cell = tuple(r["cell"]) if isinstance(r.get("cell"), list) else None
    return (run.name, tuple(r.get("path") or ()), r.get("kind"), r.get("option"), cell, r.get("param"), r.get("axis"))


class Cache:
    """The readers' answers already cached (<run root>/_cache/vlm), read only: the option question's "selected" about a
    frame, by any of the models."""

    def __init__(self, root: Path, models: list):
        self.dir, self.models = root / "_cache" / "vlm", [m for m in dict.fromkeys(models) if m]

    def option(self, frame: Path) -> str | None:
        if not self.models or not frame.is_file():
            return None
        image = frame.read_bytes()
        for m in self.models:
            try:
                got = json.loads((self.dir / f"{vlm.cache_key(image, vlm.PROMPTS['option'], m)}.json").read_text(
                    encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(got, dict) and str(got.get("selected") or "").strip():
                return str(got["selected"])
        return None


def stood(shown: str, said: str | None, how: str) -> str | None:
    """The reading the rule keeps: OCR's when plain or both agree, the reader's when it stands alone, else None."""
    return shown if how in ("plain", "stands on both") else said if how == "stands on one reader" else None


class Tally:
    """Counts for one source (proofs or menus): plain and doubtful readings per site, doubt kinds, letters, agreement,
    the rule's outcomes, and the reader calls the rule would add."""

    def __init__(self):
        self.c = collections.Counter()
        self.sites = collections.defaultdict(collections.Counter)
        self.kinds = collections.Counter()
        self.kinds_by_site = collections.defaultdict(collections.Counter)
        self.letters = collections.Counter()
        self.agreement = collections.Counter()
        self.outcomes = collections.Counter()
        self.outcomes_by_site = collections.defaultdict(collections.Counter)
        self.readers = collections.Counter()
        self.third = collections.Counter()

    def add(self, site: str, shown: str, label: str | None, said: str | None, expect: str, choices: list,
            calls: bool = True, find: bool = False):
        """One reading counted; returns what the rule makes of it (camkit.reading.outcome). calls False: its reader
        call, if the rule would add one, is counted by the caller (one question reads a number-entry screen's boxes).
        find: the reading finds a row (camkit.reading.doubts' find): an icon OCR read in front of the label is left out
        first where what is left names one row exactly (icon_left_out), counted as "icon left out", and what is left is
        judged and compared."""
        if find:
            left = reading.icon_left_out(shown, choices) if expect == "label" else None
            if left is not None:
                self.c["icon left out"] += 1
                self.sites[site]["icon left out"] += 1
                shown = left
        ds = reading.doubts(shown, expect, choices=choices, lit=True, find=find)
        plain = "plain" if not ds else "doubtful"
        self.c["read"] += 1
        self.sites[site]["read"] += 1
        self.sites[site][plain] += 1
        for d in ds:
            k = reading.kind_of(d)
            self.kinds[k] += 1
            self.kinds_by_site[site][k] += 1
            if k in ("lookalike", "foreign", "cleaned"):
                self.letters[d] += 1
        how = reading.outcome(shown, said, expect, choices, ds)
        self.outcomes[how] += 1
        self.outcomes_by_site[site][how] += 1
        if ds and said is None and calls:
            self.c["extra reader calls"] += 1
        if label is not None:
            self.agreement[f"{plain}: OCR names the option" if reading.agree(shown, label, expect, choices)
                           else f"{plain}: OCR does not name it"] += 1
            if said is not None:
                self.agreement[f"{plain}: the reader names the option" if reading.agree(said, label, expect, choices)
                               else f"{plain}: the reader does not name it"] += 1
            kept = stood(shown, said, how)
            if kept is not None:
                self.agreement[f"kept by the rule ({how}): names the option" if reading.agree(kept, label, expect, choices)
                               else f"kept by the rule ({how}): does not name it"] += 1
        if said is not None and reading.canonical(shown):
            self.agreement[f"{plain}: OCR and the reader agree" if reading.agree(shown, said, expect, choices)
                           else f"{plain}: OCR and the reader apart"] += 1
        return how

    def as_dict(self) -> dict:
        return {"counts": dict(self.c), "readers": dict(self.readers), "third vote": dict(sorted(self.third.items())),
                "sites": {s: dict(v) for s, v in sorted(self.sites.items())},
                "doubts": dict(self.kinds.most_common()),
                "doubts by site": {s: dict(v.most_common()) for s, v in sorted(self.kinds_by_site.items())},
                "letters": dict(self.letters.most_common()), "agreement": dict(sorted(self.agreement.items())),
                "outcomes": dict(self.outcomes.most_common()),
                "outcomes by site": {s: dict(v.most_common()) for s, v in sorted(self.outcomes_by_site.items())}}


class Asker:
    """--ask: the second reader asked about a doubtful proof frame with no reading yet, at most `limit` frames."""

    def __init__(self, limit: int | None):
        self.limit, self.asked, self.answered = limit, 0, 0

    def __call__(self, frame: Path) -> str | None:
        if self.limit is not None and self.asked >= self.limit or not frame.is_file():
            return None
        from camkit.frames import load
        self.asked += 1
        answer = reading.ask(load(frame), "option", reading.TIMEOUTS["proof"]).answer
        said = str((answer or {}).get("selected") or "").strip() or None
        self.answered += said is not None
        return said


def census_proofs(run: Path, cache: Cache, tally: Tally, asker: Asker | None) -> None:
    lines = jsonl.read(run / "proofs.jsonl", bad="skip")
    if not lines:
        return
    reread = {r["frame"]: str(r["reading"]) for r in jsonl.read(run / "readings.jsonl", bad="skip")
              if r.get("frame") and r.get("reading")}
    rows = collections.defaultdict(list)
    for r in lines:
        if r.get("label") is not None:
            rows[row_of(run, r)].append(str(r["label"]))
    for r in lines:
        tally.c["proof lines"] += 1
        if "shown" not in r or r.get("label") is None:
            tally.c["no OCR reading kept"] += 1
            continue
        if any(str(r.get(k) or "").strip() for k in SECOND_ENGINE_KEYS):
            tally.c["with a second OCR engine's reading"] += 1
        site = f"{r.get('kind')}{' (scale)' if r.get('scale') else ''}"
        frame = run / "shots" / str(r.get("chosen_frame") or "")
        said, source = (str(r["vlm"]), "own") if r.get("vlm") else (None, "none")
        if said is None and r.get("chosen_frame") in reread:
            said, source = reread[r["chosen_frame"]], "readings.jsonl"
        if said is None and r.get("chosen_frame"):
            said = cache.option(frame)
            source = "cache" if said else "none"
        expect, choices = expect_of(r), list(dict.fromkeys(rows[row_of(run, r)]))
        shown = str(r.get("shown") or "")
        if said is None and asker is not None and r.get("chosen_frame") \
                and reading.doubts(shown, expect, choices=choices, lit=True):
            said = asker(frame)
            source = "asked" if said else "none"
        tally.readers[source] += 1
        ocr2 = next((r[k] for k in SECOND_ENGINE_KEYS if str(r.get(k) or "").strip()), None)
        boxes, needed = boxes_of(r, shown, said, ocr2, choices), False
        for shown_k, label_k, said_k, ocr2_k, choices_k in boxes:
            how = tally.add(site, shown_k, label_k, said_k, expect, choices_k, calls=len(boxes) == 1)
            needed |= how == "reader needed"
            if how in reading.APART:
                third_vote(tally, shown_k, "second", said_k, ocr2_k, label_k, expect, choices_k)
        if len(boxes) > 1 and needed:
            tally.c["extra reader calls"] += 1          # one question to the reader reads every box of the screen


FIELD_JOIN = " | "         # how kit/proving/fields.py keeps a number-entry screen's boxes in one reading


def boxes_of(r: dict, shown: str, said, ocr2, choices: list) -> list:
    """The readings to judge for one proof line: [(OCR's, the label, the reader's, the second engine's, the options)].
    A number-entry proof (kind "fields") keeps its boxes as one reading joined by FIELD_JOIN (kit/proving/fields.py),
    as its label is: each box is judged apart, against that box's values on the row, and a reader's or second engine's
    reading counts for a box only where it splits into as many boxes (or the screen has one). Any other line is one
    reading."""
    label = str(r["label"])
    if r.get("kind") != "fields" or FIELD_JOIN not in label + shown:
        return [(shown, label, said, ocr2, choices)]
    labels = label.split(FIELD_JOIN)
    n = len(labels)
    boxes = shown.split(FIELD_JOIN) if shown else [""] * n
    if len(boxes) != n:
        return [(shown, label, said, ocr2, choices)]

    def split(reading):
        parts = str(reading).split(FIELD_JOIN) if reading else []
        return parts if len(parts) == n else [None] * n

    said_k, ocr2_k = split(said), split(ocr2)
    options = [list(dict.fromkeys(c.split(FIELD_JOIN)[k] for c in choices if len(c.split(FIELD_JOIN)) == n))
               for k in range(n)]
    return [(boxes[k], labels[k], said_k[k], ocr2_k[k], options[k]) for k in range(n)]


def census_menus(run: Path, tally: Tally) -> None:
    try:
        pages = json.loads((run / "model.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for page in pages if isinstance(pages, list) else []:
        rows = [r for r in page.get("rows") or [] if isinstance(r, dict)]
        labels = list(dict.fromkeys(str(r["label"]) for r in rows if r.get("label")))
        for r in rows:
            said_by = (r.get("readings") or {}).get("label") or {}
            if "ocr" not in said_by:
                tally.c["rows with no OCR reading"] += 1
                continue
            readers = [(k, str(v)) for k, v in said_by.items() if k not in NOT_READERS and str(v or "").strip()]
            who, said = readers[0] if readers else (None, None)
            shown, label = str(said_by.get("ocr") or ""), (str(r["label"]) if r.get("label") else None)
            tally.readers["a vision reader" if said else "none"] += 1
            how = tally.add("menu row", shown, label, said, "label", labels, find=True)
            if how in reading.APART:
                left = reading.icon_left_out(shown, labels) or shown
                ocr2 = said_by.get("ocr2")       # the second engine's reading loses its icon too, as read() casts it
                third_vote(tally, left, who, said, reading.icon_left_out(ocr2, labels) or ocr2 if ocr2 else ocr2,
                           label, "label", labels)


def third_vote(tally: "Tally", shown: str, who: str, said: str, ocr2, label: str | None, expect: str,
               choices: list) -> None:
    """A reading the first two votes leave apart, voted on a third time by the second OCR engine's reading where the
    run kept one (camkit.reading.tally: what two independent votes name stands): settled or not, and whether what
    stands names the option or row label recorded."""
    if not str(ocr2 or "").strip():
        tally.third["apart, no second OCR engine's reading kept"] += 1
        return
    votes = [reading.Vote("ocr", "ocr:first", shown), reading.Vote("reader", f"reader:{who}", said),
             reading.Vote("ocr2", "ocr:second", str(ocr2))]
    win, _ = reading.tally(votes, expect, choices)
    if win is None:
        tally.third["apart, still apart after the second OCR engine"] += 1
    elif label is None:
        tally.third["apart, settled by the second OCR engine (no label to check it by)"] += 1
    else:
        names = reading.agree(win.text, label, expect, choices)
        tally.third[f"apart, settled by the second OCR engine: {'names' if names else 'does not name'} the label"] += 1


# ------------------------------------------------------------------------------------------------ --questions

# what an answer says of the option proved: the first four are judged (and make the right rate), the last two are the
# reader's or the tool's, never the question's: "reader failed" (an HTTP error, a timeout, a refusal, an answer that is
# no JSON object), "not asked" (past the reader's --minutes, or after it failed FAIL_RUN times in a row)
VERDICTS = ("right", "another option", "no option", "no answer", "reader failed", "not asked")
JUDGED = VERDICTS[:4]
VARIANTS = ("old", "new", "options", "decoy", "v3", "best")
# a Claude model asked through the Claude Code command line (--claude-cli MODEL), on the person's own signed-in plan:
# census-only (CliReader), never a reader a camera run could pick up; one call at a time
CLI = "claude"                       # the command, found on PATH (CAMSET_CLAUDE_CLI names another)
CLI_PROMPT = ("You read pictures of a camera's screen. The picture is the file frame.png in the working directory: read "
              "it once with the Read tool, then answer the question with the JSON it asks for and nothing else.")
# the leanest call that still reads the picture: the Read tool alone, confined to an empty working folder holding
# the one frame (--restricted), no settings, memory, skills, hooks or MCP servers, no session kept, nothing that
# would ask for permission, and a minimal system prompt in place of Claude Code's
CLI_FLAGS = ("--output-format", "json", "--restricted", "--safe-mode", "--tools", "Read", "--allowedTools", "Read",
             "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
             "--permission-prompts", "none", "--system-prompt", CLI_PROMPT)
# the environment a call of the command line gets (cli_env): what it needs to run and find the person's own sign-in,
# and LC_*; never an API key or a base URL (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL: with one
# passed on, the command line would ask through that key or server, not the plan) nor the session variables of a
# Claude Code the census may itself run under (CLAUDECODE, the other CLAUDE_CODE_*). On Windows, what a program there
# needs to start and find its folders, none of it a key
CLI_ENV = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "TMPDIR", "SHELL", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN")
CLI_ENV_WINDOWS = ("SYSTEMROOT", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "PATHEXT", "COMSPEC")
CLI_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\[\]-]*")   # --claude-cli's MODEL: a name or an id, never an option
# where a reader is on the person's own machine or network (local_url): loopback and link-local by ipaddress's rule,
# private as RFC 1918 (10/8, 172.16/12, 192.168/16) and IPv6's unique local addresses (fc00::/7) say; ipaddress's
# is_private also takes the documentation ranges, 203.0.113.0/24 among them, which are no one's own network. The IPv4
# networks are built from their numbers: kit/tools/check_public.py refuses a private address written out
PRIVATE_NETS = tuple(ipaddress.ip_network(n) for n in ((10 << 24, 8), (172 << 24 | 16 << 16, 12),
                                                       (192 << 24 | 168 << 16, 16), "fc00::/7"))
# what a plan's usage or rate limit says, in the answer or on standard error: the run stops, never asks again
CLI_LIMIT = re.compile(r"(?i)usage limit|rate.?limit|limit reached|reached your|too many requests|\b429\b|overloaded|"
                       r"credit balance")
# the frames a hosted reader is never sent (hosted_refused): a run named for a network or address look, and screens no
# menu or option screen is (a shooting or playback screen, a help pop-up, one the screen reader cannot tell)
NETWORK_RUN = re.compile(r"(?i)wi-?fi|wlan|(?:^|[_-])lan(?:[_-]|$)|network|(?:^|[_-])net(?:[_-]|$)|addr|ssid|"
                         r"bluetooth|(?:^|[_-])bt(?:[_-]|$)|ftp|(?:^|[_-])mac(?:[_-]|$)|(?:^|[_-])ip(?:[_-]|$)|serial|"
                         r"tether|ident")
MENU_SCREENS = frozenset({"menu", "submenu", "list", "sidelist", "dialog", "picker", "table", "fnmenu", "keyset",
                          "checklist", "checkgrid", "fields", "look", "wbgrid", "slider", "notice", "tiles"})
# how OCR's reading at the proof (the line's "shown") and the reader's answer stand together, against the option
# proved: "both wrong, alike" is the dangerous one, where decision 22's OCR-main and reader-backup would not catch it
BOTH = ("both right", "reader wrong, OCR right", "OCR wrong, reader right", "both wrong, apart", "both wrong, alike")
DEFAULTS = {"variants": ",".join(VARIANTS), "per_kind": 60, "minutes": 40.0, "timeout": 60.0}   # --questions'
FAIL_RUN = 8                         # failures in a row after which a reader is asked nothing more (its server is down)
SKIP = object()                      # a question that judges nothing for this item (the old question, a box it skips)
FAILED = object()                    # the reader failed, or answered nothing usable (camkit.vlm.usable)
NOT_ASKED = object()                 # past the reader's time or after FAIL_RUN failures in a row, and in no cache
WB_SIDES = {"A-B": ("A", "B"), "G-M": ("G", "M")}    # each readout's letters: the first negative (proving.wbgrid)
STAR_LABEL = re.compile(r"\u2605+")                  # a label of rating stars alone (BLACK STAR)
BULLET = re.compile(r"^[\u2022\u00B7]\s*")           # the radio dot a picker's label is recorded with (BULLET, MIDDLE DOT)
# the buttons a notice ends with, which its recorded text keeps (BLACK CIRCLE, BULLET: OCR's reading of OK's dot)
NOTICE_BUTTONS = re.compile(r"(?:\s*(?:\bOK\b|\bCancel\b|\bEnter\b|\bYes\b|\bNo\b|[\u25CF\u2022]))+\s*$", re.I)


class Item:
    """One thing a sampled proof frame shows, to be read: kind, a camkit.reading.QUESTIONS key; frame, the file;
    truth, what the camera's file proved there, in the kind's own form (a label, a number, a star count, the white
    balance value in thousandths, a Creative Look scale's ends, a checklist's [(box label, ticked)], a notice's or
    title's recorded text); options, the options expected there in the same form (the row's, as the run proved them);
    shown, how each option is said to the reader with the options question; box, a number-entry screen's box; old, the
    proof line's own second reading (the option question's, asked at the time), for the sample's split; extra, what
    one kind needs more (a checklist's own label, a number-entry screen's changed box, a white balance axis)."""

    def __init__(self, kind, frame, truth, options=(), shown=None, box=None, old=None, extra=None):
        self.kind, self.frame, self.truth, self.options = kind, frame, truth, list(options)
        self.shown = list(shown) if shown is not None else [str(o) for o in self.options]
        self.box, self.old, self.extra = box, old, dict(extra or {})


def _bare(label) -> str:
    return BULLET.sub("", str(label or "")).strip()


def number_of(text) -> str | None:
    """The first number in a reading, as the kit takes a box's (proving.fields.fields_by_reader): sign, digits and
    decimal point, a comma for the point, leading zeros and a plus left out, a plus-minus or signed zero "0"; None
    without a digit."""
    from decimal import Decimal
    m = re.search(r"([+\-\u00B1]?)\s*(\d+(?:[.,]\d+)?)", reading.canonical(text))
    if not m:
        return None
    v = Decimal(m.group(2).replace(",", "."))
    if v == 0:
        return "0"
    return ("-" if m.group(1) == "-" else "") + format(v.normalize(), "f")


def star_count(text) -> int | None:
    """The stars a reading counts: a digit (with "star" or "stars" after it), or the stars themselves as BLACK STAR or
    "*"; 0 for "off"; None otherwise."""
    t = reading.canonical(text).strip().lower()
    if t in ("off", "0"):
        return 0
    m = re.fullmatch(r"(\d)\s*(?:stars?)?", t)
    if m:
        return int(m.group(1))
    if t and set(t) <= set("\u2605*\u2606 "):        # BLACK STAR, WHITE STAR
        return sum(c in "\u2605*" for c in t) or None
    return None


def wb_value(axis: str, text) -> int | None:
    """A white balance readout ("A7", "M1.25", "0", "A-B: A7") in thousandths, its first letter negative
    (proving.wbgrid.wb_reading's convention); None when it is not one of the axis's."""
    t = re.sub(r"\s", "", reading.canonical(text)).upper()
    t = re.sub(r"^(?:A-B|G-M):?", "", t)
    m = re.fullmatch(r"([A-Z]?)(\d+(?:[.,]\d+)?)", t)
    if not m:
        return None
    v = round(float(m.group(2).replace(",", ".")) * 1000)
    neg, pos = WB_SIDES[axis]
    return 0 if v == 0 else -v if m.group(1) == neg else v if m.group(1) == pos else None


def wb_readout(axis: str, value: int) -> str:
    neg, pos = WB_SIDES[axis]
    return "0" if not value else f"{neg if value < 0 else pos}{abs(value) / 1000:g}"


def _keeps_lead(text, label) -> bool:
    """proving.screens.keeps_lead: a label's short first word ("Tv", "Av") is in the reading too, so no rule here
    takes a reading of one such row for the other."""
    from proving.screens import keeps_lead
    return keeps_lead(str(text or ""), str(label or ""))


def _alike_but_icon(text: str, label: str) -> bool:
    """A reading alike a label once an icon OCR read in front of the reading is left out (camkit.reading.without_icon),
    or but for one or two characters in front of the reading (page_model.same_text's prefix): only the reading loses
    its front, as camkit.reading.icon_left_out cuts it, never the label, and the label's short first word must be in
    the reading (_keeps_lead): "AF On" is never alike "MF On", nor a reading "Tv ..." alike "Av ..."."""
    kl, kt = match.norm(label), match.norm(text)
    if not kl or not kt or not _keeps_lead(text, label):
        return False
    if not re.search(r"[A-Za-z0-9]", str(label)):
        return kl == kt                  # a label of signs alone (rating stars): each sign counts, none is an icon
    return kl in (kt, match.norm(reading.without_icon(text))) or (
        len(kl) >= 4 and 0 < len(kt) - len(kl) <= 2 and kt.endswith(kl))


def _starless(text) -> str:
    """A reading with each rating star written as "*" (BLACK STAR), and a count of them ("5 stars", which a question
    may ask for) written as that many: readers and OCR write the camera's stars either way, and a run's labels keep
    them as drawn."""
    t = str(text or "").replace("\u2605", "*")
    return re.sub(r"\b([1-9])\s*stars?\b", lambda m: "*" * int(m.group(1)), t, flags=re.I)


def _closest(text, options: list) -> int | None:
    """The option a label reading is clearly closest to, as proving.screens.closest_row takes a row (a ratio of 0.8 or
    more, 0.1 over the next), its digits the same: a run's label recorded as OCR read it ("Fixed Speed SBY") against
    a reader's reading of what is drawn."""
    import difflib
    keys = [k for k in dict.fromkeys((match.norm(text), match.norm(reading.without_icon(text)))) if k]
    if not keys:
        return None
    # the reading with and without an icon in front, each against the label as recorded (never cut)
    score = sorted(((max(difflib.SequenceMatcher(None, k, match.norm(o)).ratio() for k in keys), j)
                    for j, o in enumerate(options)), reverse=True)
    if not score or score[0][0] < 0.8 or (len(score) > 1 and score[0][0] - score[1][0] < 0.1):
        return None
    j = score[0][1]
    same_digits = re.findall(r"\d+", reading.without_icon(options[j])) == re.findall(r"\d+", reading.without_icon(text))
    return j if same_digits and _keeps_lead(text, options[j]) else None


def names(text, options: list, expect: str) -> int | None:
    """The one option a reading names (camkit.reading.choice_of, stars written as "*" on both sides), else, for a
    label, the one it is alike once an icon read in front of the reading is left out (_alike_but_icon), else the one
    it is clearly closest to (_closest); None for an empty reading, "none" and anything else. A label's short first
    word must be in the reading whatever named it (_keeps_lead: choice_of's loose likeness takes "Tv ..." for "Av
    ..." where only one of them is an option)."""
    if not str(text or "").strip():
        return None
    text, options = _starless(text), [_starless(o) for o in options]
    i = reading.choice_of(text, expect, options)
    if i is not None and expect == "label" and not _keeps_lead(text, options[i]):
        return None
    if i is not None or expect != "label":
        return i
    hits = [j for j, o in enumerate(options) if _alike_but_icon(text, o)]
    return hits[0] if len(hits) == 1 else _closest(text, options) if not hits else None


def drawn_alike(label: str, options: list) -> bool:
    """Another option of the row is drawn with the same text, but for an icon OCR read in front of one of the two
    (_alike_but_icon, each taken in turn as the reading): no reading of the text can tell them apart, only their place,
    so such a proof is left out of the sample."""
    return any(o != label and (_alike_but_icon(o, label) or _alike_but_icon(label, o)) for o in options)


def _verdict(i, item: Item) -> str:
    if i is None:
        return "no option"
    return "right" if item.options[i] == item.truth else "another option"


def _index(value, options: list) -> int | None:
    return options.index(value) if value is not None and value in options else None


def judge(item: Item, value) -> str:
    """What a reading of item says, by its kind: "right" (the option the file proved), "another option" (another of
    the row's), "no option" (none of them, "none" among them); for a notice and a title, which have no options,
    "another option" is a text read otherwise than recorded."""
    k = item.kind
    if k == "checklist" and isinstance(value, list):
        radios = any(isinstance(b, dict) and isinstance(b.get("radios"), list) for b in value)
        return judge_radio(item, value) if item.extra.get("radio_of") and radios else judge_boxes(item, value)
    text = value if isinstance(value, str) else (str(value) if isinstance(value, (int, float)) and not isinstance(
        value, bool) else "")
    if k == "checklist":
        return _verdict(names(text, item.options, "label"), Item(k, item.frame, item.extra["label"], item.options))
    if k in ("number field", "look"):
        return _verdict(_index(number_of(text), item.options), item)
    if k == "star rating":
        return _verdict(_index(star_count(text), item.options), item)
    if k == "wb grid":
        return _verdict(_index(wb_value(item.extra["axis"], text), item.options), item)
    if k == "look base":
        code = re.split(r"[\s(]", reading.canonical(text).strip(), maxsplit=1)[0] if text.strip() else ""
        return _verdict(names(code, item.options, "code"), item)
    if k == "axis cell":
        return _verdict(names(text, item.options, "code"), item)
    if k == "look scale":
        top, bottom = value if isinstance(value, tuple) else (None, None)
        got = (number_of(bottom), number_of(top))
        if None in got:
            return "no option"
        return "right" if got == item.truth else "another option"
    if k == "notice":
        import difflib
        a = reading.said_key(NOTICE_BUTTONS.sub("", reading.canonical(text)))
        b = reading.said_key(NOTICE_BUTTONS.sub("", reading.canonical(item.truth)))
        if not a or a == "none":
            return "no option"
        return "right" if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 else "another option"
    if k == "title":
        if not text.strip() or text.strip().lower() == "none":
            return "no option"
        same = (reading.agree(text, item.truth, "label") and _keeps_lead(text, item.truth)) or \
            _alike_but_icon(text, item.truth)
        return "right" if same else "another option"
    expect = item.extra.get("expect", "label")
    return _verdict(names(text, item.options, expect), item)


def box_of(label, labels: list) -> int | None:
    """The box of a checklist a reader's label names: by its star count where the boxes are rating stars, else by
    names(), else by the short text its cell shows ("XL" for Tracking: Spot XL, proving.screens.cell_code)."""
    if any(STAR_LABEL.fullmatch(str(o)) for o in labels):
        n = star_count(label)
        hits = [j for j, o in enumerate(labels) if STAR_LABEL.fullmatch(str(o)) and len(str(o)) == n]
        return hits[0] if len(hits) == 1 else None
    i = names(label, labels, "label")
    if i is not None:
        return i
    from proving.screens import cell_code
    code = re.sub(r"[\s.]", "", reading.canonical(label)).upper()
    hits = [j for j, o in enumerate(labels) if code and cell_code(o) == code]
    return hits[0] if len(hits) == 1 else None


def judge_boxes(item: Item, boxes: list) -> str:
    """A checklist answer ([{"label", "ticked"}]) against the boxes the proof changed (item.truth): "right" when each
    of them is named once with the state the proof left it in, "another option" when one is named with the other
    state, "no option" when one is not named once with a true or false."""
    seen = collections.defaultdict(list)
    for b in boxes:
        if isinstance(b, dict):
            j = box_of(b.get("label"), item.options)
            if j is not None:
                seen[j].append(b.get("ticked"))
    verdict = "right"
    for label, ticked in item.truth:
        got = seen.get(item.options.index(label)) or []
        if len(got) != 1 or not isinstance(got[0], bool):
            return "no option"
        if got[0] != ticked:
            verdict = "another option"
    return verdict


def _selected(answer: dict, item: Item):
    return answer.get("selected")


def _selected_or_value(answer: dict, item: Item):
    v = answer.get("selected")
    return v if str(v or "").strip() else answer.get("value")


def _field(name: str):
    def pick(answer: dict, item: Item):
        return answer.get(name)
    return pick


def _as_kit_reads(v):
    """A box's answer as proving.fields and proving.looks take it: its text, whatever the reader put there (an object
    such as {"value": "15", "unit": "sec"} is read as its text, its first number the box's)."""
    return None if v is None else v if isinstance(v, str) else str(v)


def _box(answer: dict, item: Item):
    v = answer.get("fields")
    ok = isinstance(v, list) and item.box is not None and 0 <= item.box < len(v)
    return _as_kit_reads(v[item.box]) if ok else None


def _active(answer: dict, item: Item):
    v, k = answer.get("fields"), answer.get("active")
    ok = isinstance(v, list) and isinstance(k, int) and not isinstance(k, bool) and 0 <= k < len(v)
    return _as_kit_reads(v[k]) if ok else None


def _changed_box(answer: dict, item: Item):
    """The option question's one reading of a number-entry screen judges only the box the proof changed."""
    return answer.get("selected") if item.box == item.extra.get("changed") else SKIP


def _wb(answer: dict, item: Item):
    return answer.get(item.extra["axis"])


def _ends(answer: dict, item: Item):
    return (answer.get("top"), answer.get("bottom"))


# the questions the kit asks today at each kind's proof site: the option question every proof keeps a second reading
# by (proving.screens.vlm_option), the number-box question proving.fields and proving.looks ask, the notice's
OLD = {
    "list": [("option", _selected)], "side list": [("option", _selected)], "table picker": [("option", _selected)],
    "scale": [("option", _selected_or_value)], "star rating": [("option", _selected)],
    "checklist": [("option", _selected)], "number field": [("option", _changed_box), ("fields", _box)],
    "carousel": [("option", _selected)], "axis": [("option", _selected)], "axis cell": [("option", _selected)],
    "look": [("option", _selected), ("fields", _active)], "look scale": [], "look base": [("option", _selected)],
    "wb grid": [("option", _selected)], "notice": [("notice", _field("text"))], "title": [("option", _field("title"))],
}
NEW_PICK = {"number field": _box, "wb grid": _wb, "look scale": _ends, "checklist": _field("boxes"),
            "notice": _field("text"), "title": _field("title")}
NO_OPTIONS = {"checklist", "look scale", "notice", "title"}     # kinds asked no options question


def _rows(answer: dict, item: Item):
    """The stars question's count, from its rows (stars.rows.v3), or its "off"."""
    rows = answer.get("rows")
    if str(answer.get("selected") or "").strip().lower() == "off":
        return "off"
    if isinstance(rows, list) and rows and all(isinstance(n, int) and not isinstance(n, bool) for n in rows):
        return str(sum(rows))
    return None


def _routed(item: Item) -> str:
    """The question a list proof is read by where the screen tells it (a pixel rule a caller can use too): a carousel's
    orange line where the screen is a carousel whose second axis lights a strip cell (proving.screens.axis_lit_x), its
    lit item elsewhere."""
    return "carousel.v2" if item.extra.get("strip") else "lit.v2"


# Candidates for a third question, each one change to a kind's second aimed at a class of misses the census found on the
# first camera's frames (2026-11-13): measured on the census's sample and on a second, held-out one (--held-out), and
# none kept, because none measured better on the one and not worse on the other with no more wrong options (the kept
# one, title.v3, is camkit.vlm's). They stay here so the measurement can be made again on another camera's runs.
_LIT = vlm.PROMPTS["lit.v2"].split(" If no item is highlighted")[0]      # lit.v2 up to its "none" sentence
_JSON = "Reply with JSON only, on one line: "
CANDIDATES = {
    # lit.v2, and a short code or icon text before the item's name left out (it left out a real part of a label too)
    "lit.codes.v3": (
        _LIT + " Where a short code or a small icon text stands on the bar before the item's own name (a size, a "
        "quality mark), leave it out too and copy the name. If no item is highlighted, write none. "
        + _JSON + '{"selected": "<the text>"}'),
    # lit.v2, and rating stars given as their count (more stars counted wrong as another option)
    "lit.stars.v3": (
        _LIT + " Where the item holds rating stars, count every star (they may stand in two or three rows) and write "
        "the count and the word stars in their place, such as (3 stars). If no item is highlighted, write none. "
        + _JSON + '{"selected": "<the text>"}'),
    # lit.v2, asked about the lit item cut out of the frame and enlarged (it lost small marks, more wrong options)
    "litcrop.v3": (
        "This is one highlighted item cut out of a Sony camera menu screen and enlarged. Copy the item's own text "
        "exactly as drawn, every letter, digit, sign and space, in its case. Leave out any icon, radio button or check "
        "box before it and any value written to its right. If no text is drawn, write none. "
        + _JSON + '{"selected": "<the text>"}'),
    # lit.v2, with the reader saying whether it was unsure of a character (it was never unsure of a wrong answer)
    "lit.check.v3": (
        _LIT + " If no item is highlighted, write none. "
        + _JSON + '{"selected": "<the text>", "unsure": true if any character was hard to read, else false}'),
    # a grid of rating stars: the lit box's stars row by row (no more right; a wrong count became no option)
    "stars.rows.v3": (
        "This is a Sony camera screen with boxes of rating stars, and one box is highlighted in orange. The stars in "
        "a box may stand in two or three rows. For the orange box, give how many stars stand in each of its rows, from "
        "the top row down; if that box shows OFF, give no rows and write off. Also say whether its check box is "
        "ticked. " + _JSON + '{"rows": [<stars in the top row>, <in the next row>], "selected": "off" or "", '
        '"ticked": true or false}'),
    # a list of check boxes, with the radio buttons drawn under a check box (worse, and three times slower)
    "checklist.radio.v3": (
        "This is a Sony camera screen with a list of check boxes, and some check boxes have radio buttons under them. "
        "For every check box, copy its label exactly as drawn, say whether it is ticked, and list the radio buttons "
        "drawn under it before the next check box, each with its label and whether it is the selected one (its dot "
        "filled). For a label made only of stars, count every star in every row and write the count as a digit. Leave "
        "out the buttons, such as OK, Enter or Cancel. " + _JSON + '{"boxes": [{"label": "<the label>", "ticked": '
        'true or false, "radios": [{"label": "<the label>", "selected": true or false}]}]}'),
}
QUESTION_TEXTS = {**vlm.PROMPTS, **CANDIDATES}


def _question(key) -> str:
    return QUESTION_TEXTS[key]


# the candidates for a third question ("v3"), per kind: (question id, a key of QUESTION_TEXTS or a function of the
# item giving one, pick, what the reader is shown: None for the frame, "lit crop" for the lit item cut out and enlarged
# twice, "scale crop" for a Creative Look scale's column cut out and enlarged twice). "v3: route" asks a list proof on
# a carousel the carousel's question (_routed): measured better on both samples, it is the list caller's to make when
# it moves onto its question; "v3: v2" asks the second question beside a kept third (title.v3)
LIT_V3 = [("v3: codes", "lit.codes.v3", _selected, None), ("v3: stars", "lit.stars.v3", _selected, None),
          ("v3: crop", "litcrop.v3", _selected, "lit crop"), ("v3: check", "lit.check.v3", _selected, None)]
HYPOTHESES = {
    "list": [("v3: route", _routed, _selected, None), *LIT_V3], "side list": LIT_V3, "table picker": LIT_V3,
    "star rating": [("v3: rows", "stars.rows.v3", _rows, None)],
    "checklist": [("v3: radio", "checklist.radio.v3", _field("boxes"), None)],
    "look scale": [("v3: crop", "lookscale.v2", _ends, "scale crop")],
    "title": [("v3: v2", "title.v2", _field("title"), None)],
}
CROPS = {"lit crop": None, "scale crop": (540, 70, 640, 272)}   # the scale's ends: proving.looks.look_cell's boxes
# "best": each kind's best measured question, one per reading: the new one (QUESTIONS), but where a v3 that is no
# question of QUESTIONS measured better on both samples (the list's routing), that one in its place
BEST = {"list": ("v3: route",)}


def image_of(frame: Path, transform=None) -> bytes:
    """The picture the reader is sent: the frame's file, or a part of it enlarged twice (CROPS: the lit item's box,
    camkit.live.lit_found, with a margin; a fixed region), as a PNG. A frame with nothing lit is sent whole."""
    data = frame.read_bytes()
    if transform is None:
        return data
    from PIL import Image

    from camkit import live
    from camkit.frames import load
    box = CROPS[transform]
    if box is None:
        lit = live.lit_found(load(frame).image)[0]
        if lit is None:
            return data
        x0, y0, x1, y1 = lit
        box = (max(0, x0 - 8), max(0, y0 - 8), min(640, x1 + 8), min(480, y1 + 8))
    with Image.open(frame) as im:
        part = im.convert("RGB").crop(box)
    buf = io.BytesIO()
    part.resize((part.width * 2, part.height * 2), Image.LANCZOS).save(buf, format="PNG")
    return buf.getvalue()


def questions_of(item: Item, frame_items: list, variants) -> list:
    """[(question id, the question's whole text, pick, what the reader is shown: image_of's transform)] item is judged
    by: the old questions, the kind's new one (camkit.reading.QUESTIONS), the new one with the options expected there
    handed to the reader ("options") or with every option but the one the file proved ("decoy": a reader that picks
    from the list rather than read the screen names another option there), and the candidates for a third ("v3",
    HYPOTHESES). A number-entry screen's options are said box by box (frame_items: the frame's items, a box each)."""
    out = []
    if "old" in variants:
        out += [(f"old: {key}", vlm.PROMPTS[key], pick, None) for key, pick in OLD[item.kind]]
    new = vlm.PROMPTS[reading.QUESTIONS[item.kind].prompt]
    pick = NEW_PICK.get(item.kind, _selected)
    if "new" in variants or ("best" in variants and item.kind not in BEST):
        out.append(("new", new, pick, None))
    if "v3" in variants or "best" in variants:
        for qid, key, v3_pick, transform in HYPOTHESES.get(item.kind, ()):
            if "v3" in variants or qid in BEST.get(item.kind, ()):
                out.append((qid, _question(key(item) if callable(key) else key), v3_pick, transform))
    if item.kind in NO_OPTIONS or not {"options", "decoy"} & set(variants):
        return out
    if item.kind == "number field":
        full = {f"box {it.box + 1}": it.shown for it in frame_items}
        fewer = {f"box {it.box + 1}": [s for s, o in zip(it.shown, it.options, strict=True) if o != it.truth]
                 for it in frame_items}
    elif item.kind == "wb grid":
        full = {f"{item.extra['axis']} value": item.shown}
        fewer = {f"{item.extra['axis']} value": [s for s, o in zip(item.shown, item.options, strict=True)
                                                 if o != item.truth]}
    else:
        full = item.shown
        fewer = [s for s, o in zip(item.shown, item.options, strict=True) if o != item.truth]
    if not any(fewer.values() if isinstance(fewer, dict) else fewer):
        return out                       # one option only: nothing to hand over
    if "options" in variants:
        out.append(("new + options", vlm.with_options(new, full), pick, None))
    if "decoy" in variants:
        out.append(("new + decoy", vlm.with_options(new, fewer), pick, None))
    return out


def question_items(run: Path, lines: list, reread: dict) -> list:
    """The Items of one run's proof lines, by kind (camkit.reading.QUESTIONS), each with the row's options: a proof
    line whose option is not on its own frame (an axis's last visit, which puts the carousel back on the option it
    opened on; a list proof that kept no OCR of its bar, a prover's that read the screen elsewhere) or whose frame is
    missing gives none."""
    from proving.screens import axis_lit_x, cell_code

    from camkit import screen
    from camkit.frames import load
    rows = collections.defaultdict(list)
    for r in lines:
        if r.get("label") is not None:
            rows[row_of(run, r)].append(r)
    shots = run / "shots"
    out = []
    for r in lines:
        made = len(out)
        try:
            frame = shots / str(r.get("chosen_frame") or "")
            kind, label = r.get("kind"), r.get("label")
            own = r.get("vlm")               # "": asked at the time, and nothing read; None: not asked
            old = own if str(own or "").strip() else reread.get(r.get("chosen_frame")) or ("" if own is not None else None)
            notice = r.get("notice") if isinstance(r.get("notice"), dict) else None
            # a notice the camera drew, as the run recorded its text (the kit's own notes start in lower case: "the menu
            # closed after OK"), on a frame the screen reader takes for a notice
            said = str((notice or {}).get("text") or "").strip()
            if said and not said[0].islower() and notice.get("frame") and (shots / str(notice["frame"])).is_file() \
                    and screen.read(load(shots / str(notice["frame"]))).kind == "notice":
                out.append(Item("notice", shots / str(notice["frame"]), said))
            if label is None or not r.get("chosen_frame") or not frame.is_file():
                continue
            row = rows[row_of(run, r)]
            labels = list(dict.fromkeys(_bare(x["label"]) for x in row))
            lab = _bare(label)
            if kind in ("list", "sidelist", "table", "dialog", "axis") and "shown" not in r:
                continue                     # a prover's line that read no option off its frame (a hold's, read on Register)
            ocr_said = {"ocr": str(r["shown"])} if isinstance(r.get("shown"), str) else {}   # OCR's reading at the proof
            if kind == "list" and STAR_LABEL.fullmatch(lab):
                counts = sorted({len(_bare(x["label"])) for x in row if STAR_LABEL.fullmatch(_bare(x["label"]))})
                out.append(Item("star rating", frame, len(lab), counts, [str(c) for c in counts], old=old, extra=ocr_said))
            elif kind == "list" or kind in ("sidelist", "table", "dialog") or (kind == "axis" and not r.get("final")):
                site = {"list": "scale" if r.get("scale") else "list", "sidelist": "side list", "table": "table picker",
                        "dialog": "carousel", "axis": "axis"}[kind]
                seen = screen.read(load(frame)).kind if site == "list" else None
                if seen == "shooting":
                    continue                 # no menu up on the frame
                if expect_of(r) == "label" and drawn_alike(lab, labels):
                    continue
                # a list proof on a carousel whose second axis lights a strip cell (HYPOTHESES' route)
                strip = seen == "dialog" and axis_lit_x(load(frame).image) is not None
                out.append(Item(site, frame, lab, labels, old=old,
                                extra={"expect": expect_of(r), **ocr_said, **({"strip": True} if strip else {})}))
                if kind == "dialog":
                    out.append(Item("title", frame, str((r.get("path") or [""])[-1]), old=None))
                codes = [c for c in dict.fromkeys(cell_code(x) for x in labels) if c]
                if kind in ("dialog", "axis") and cell_code(lab) and len(codes) > 1 \
                        and axis_lit_x(load(frame).image) is not None:
                    out.append(Item("axis cell", frame, cell_code(lab), codes, old=old))
            elif kind == "lookbase":
                out.append(Item("look base", frame, lab, labels, old=old, extra=ocr_said))
            elif kind == "look" and isinstance(r.get("value"), int):
                values = list(dict.fromkeys(x["value"] for x in row if isinstance(x.get("value"), int)))
                shown = [f"{v:+d}" if v else "\u00B10" for v in values]          # PLUS-MINUS SIGN before a zero
                out.append(Item("look", frame, str(r["value"]), [str(v) for v in values], shown, old=old))
                rng = r.get("range")
                if isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng):
                    out.append(Item("look scale", frame, (str(rng[0]), str(rng[1]))))
            elif kind == "wbgrid" and r.get("axis") in WB_SIDES and isinstance(r.get("value"), int):
                axis = r["axis"]
                values = list(dict.fromkeys(x["value"] for x in row if isinstance(x.get("value"), int)))
                out.append(Item("wb grid", frame, r["value"], values, [wb_readout(axis, v) for v in values], old=old,
                                extra={"axis": axis}))
            elif kind == "checklist" and isinstance(r.get("boxes"), list) and r["boxes"]:
                # the box this proof changed, which the frame shows (another box it put back can be scrolled away)
                boxes = [(str(b.get("label")), b.get("ticked")) for b in r["boxes"]
                         if isinstance(b, dict) and str(b.get("label")) == lab]
                every = list(dict.fromkeys(str(b.get("label")) for x in row for b in x.get("boxes") or []
                                           if isinstance(b, dict)))
                # a screenful of boxes, each told apart by its text (a longer list scrolls its boxes away; a grid of
                # icons draws two boxes alike)
                codes = [cell_code(x) for x in every if cell_code(x)]
                apart = len(every) <= 6 and not any(drawn_alike(x, every) for x in every) and len(codes) == len(set(codes))
                if apart and len(boxes) == 1 and isinstance(boxes[0][1], bool):
                    out.append(Item("checklist", frame, boxes, every, old=old, extra={"label": lab, **radio_of(row, r, lab)}))
            elif kind == "fields":
                parts = str(label).split(FIELD_JOIN)
                shown = str(r.get("shown") or "")
                if shown and len(shown.split(FIELD_JOIN)) != len(parts):
                    continue                 # a label of one box where the screen has more: no box to judge it by
                per = [list(dict.fromkeys(x["label"].split(FIELD_JOIN)[k] for x in row
                                          if len(str(x["label"]).split(FIELD_JOIN)) == len(parts)))
                       for k in range(len(parts))]
                changed = next((k for k, p in enumerate(parts) if p.strip() == str(r.get("value") or "").strip()), None)
                for k, p in enumerate(parts):
                    if number_of(p) is None or k != changed:
                        continue             # the box the proof changed, which its file proved; the others are as planned
                    values = list(dict.fromkeys(n for n in (number_of(v) for v in per[k]) if n is not None))
                    ocr_box = {"ocr": shown.split(FIELD_JOIN)[k]} if shown else {}
                    out.append(Item("number field", frame, number_of(p), values, box=k, old=old,
                                    extra={"changed": changed, **ocr_box}))
        finally:
            for it in out[made:]:          # the menu path each item came from: what a hosted reader's guard judges
                it.extra.setdefault("path", [str(x) for x in r.get("path") or ()])
    return out


def radio_of(row: list, r: dict, label: str) -> dict:
    """Where a checklist proof's box is a radio button under a check box (the run kept it with "radio", the other
    button of its pair, on this line or another of the row): {"radio_of": the check box above it, "radios": the radio
    labels of the row, "boxes_only": the check boxes' labels, "other": the other button}; {} for a check box. The check
    box above is the nearest one before it in the row's order of boxes ("box", counted over every row of the list)."""
    entries = [b for x in row for b in x.get("boxes") or [] if isinstance(b, dict) and isinstance(b.get("box"), int)]
    radios = {str(b["label"]) for b in entries if b.get("radio")} | {str(b["radio"]) for b in entries if b.get("radio")}
    mine = next((b for b in r.get("boxes") or [] if isinstance(b, dict) and str(b.get("label")) == label), None)
    if label not in radios or mine is None or not isinstance(mine.get("box"), int):
        return {}
    at = {b["box"]: str(b["label"]) for b in entries}
    above = [at[i] for i in sorted(at) if i < mine["box"] and at[i] not in radios]
    other = str(mine.get("radio") or next((b["radio"] for b in entries if str(b["label"]) == label and b.get("radio")),
                                          ""))
    if not above:
        return {}
    return {"radio_of": above[-1], "radios": sorted(radios), "other": other,
            "boxes_only": list(dict.fromkeys(str(b["label"]) for b in entries if str(b["label"]) not in radios))}


def judge_radio(item: Item, boxes: list) -> str:
    """A checklist answer with radio buttons under its check boxes (checklist.radio.v3) against a proof that set a
    radio button: "right" when the check box above it is named once and its selected button is the one the proof left
    selected (the label where ticked, else the other of the pair), "another option" when the other is selected there,
    "no option" when the check box, or one selected button under it, is not found."""
    parent, (label, ticked) = item.extra["radio_of"], item.truth[0]
    tops = item.extra["boxes_only"]
    under = [b for b in boxes if isinstance(b, dict) and box_of(b.get("label"), tops) == tops.index(parent)]
    if len(under) != 1:
        return "no option"
    chosen = [x for x in under[0].get("radios") or [] if isinstance(x, dict) and x.get("selected") is True]
    if len(chosen) != 1:
        return "no option"
    pair = [label, item.extra.get("other") or ""]
    i = names(chosen[0].get("label"), [p for p in pair if p], "label")
    if i is None:
        return "no option"
    return "right" if (i == 0) == bool(ticked) else "another option"


def old_split(units: list) -> str:
    """How the proof's own second reading (the option question's, asked at the time) read a frame's items: "agreed"
    (it names the option the file proved), "apart" (it read something else, or nothing) or "none" (no reading kept)."""
    first = units[0]
    if first.kind == "number field":
        first = next((u for u in units if u.box == u.extra.get("changed")), first)
    if first.old is None or first.kind in ("look scale", "notice", "title"):
        return "none"
    return "agreed" if judge(first, str(first.old)) == "right" else "apart"


def sample(items: list, per_kind: int, usable=None) -> dict:
    """{kind: [the frames' Item lists]}: up to per_kind frames of each kind, chosen the same way every time (by a hash
    of the frame's run and name), half where the proof's own second reading named something else than the option
    proved and half where it named it, then frames with no such reading; a smaller sample is the start of a larger
    one, and within a kind the two halves alternate, so that a reader's time running out cuts both alike. usable: a
    test a frame must pass (not black), made only on the frames taken in turn."""
    import hashlib
    by_kind = collections.defaultdict(lambda: collections.defaultdict(list))
    for it in items:
        by_kind[it.kind][it.frame].append(it)
    out = {}
    for kind, frames in by_kind.items():
        def h(f, kind=kind):
            return hashlib.sha1(f"{f.parent.parent.name}/{f.name}/{kind}".encode()).hexdigest()
        buckets = {"apart": [], "agreed": [], "none": []}
        for f in sorted(frames, key=h):
            buckets[old_split(frames[f])].append(frames[f])

        def take(units, n):
            return list(itertools.islice((u for u in units if usable is None or usable(u[0].frame)), max(0, n)))
        apart = take(buckets["apart"], per_kind // 2)
        agreed = take(buckets["agreed"], per_kind - len(apart))
        chosen = [u for pair in itertools.zip_longest(apart, agreed) for u in pair if u is not None]
        rest = [u for u in buckets["none"] + buckets["apart"] + buckets["agreed"] if u not in chosen]
        out[kind] = chosen + take(rest, per_kind - len(chosen))
    return out


def local_url(url) -> bool:
    """A reader's address on the person's own machine or network: its host localhost, a .local name, or an address
    that is loopback, link-local or private (PRIVATE_NETS). Any other name, a bare one ("gpu") among them, and an
    address that cannot be read are not."""
    try:
        host = (urlsplit(str(url or "").strip()).hostname or "").rstrip(".")
    except ValueError:
        return False
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_loopback or ip.is_link_local or any(ip in n for n in PRIVATE_NETS)


def is_hosted(cfg: dict) -> bool:
    """A reader whose questions may leave the person's machine and network: a paid one (camkit.vlm.paid), the Claude
    Code command line (CliReader), or one at an address local_url does not take for local (an unpaid OpenAI-compatible
    service at a public address is sent the frames as a paid one is)."""
    return vlm.paid(cfg) or cfg.get("kind") == "claude-cli" or not local_url(cfg.get("url"))


def cli_env(environ=None) -> dict:
    """The environment a call of the command line gets: CLI_ENV's variables that are set, and LC_*, from environ
    (os.environ)."""
    environ = os.environ if environ is None else environ
    keep = CLI_ENV + (CLI_ENV_WINDOWS if os.name == "nt" else ())
    return {k: v for k, v in environ.items() if k in keep or k.startswith("LC_")}


class CliLimit(RuntimeError):
    """The plan's usage or rate limit, as the Claude Code command line says it: the run asks that reader nothing
    more."""


class CliReader:
    """One question about one picture per call of the Claude Code command line in print mode (CLI_FLAGS), on the
    person's own signed-in plan: the picture written alone into a new, empty working folder under base, read there
    with the Read tool and nothing else, and the folder removed after the call, its environment cli_env's alone (no API
    key: the plan answers). Census-only: no camera run knows it. calls: what each call's JSON says of it (seconds, the
    API's seconds, input and output tokens, turns)."""

    def __init__(self, cfg: dict, base: Path, timeout: float):
        self.name, self.model, self.base, self.timeout = str(cfg["name"]), str(cfg["model"]), Path(base), timeout
        if not CLI_MODEL.fullmatch(self.model):
            raise ValueError("a Claude model's name or id is letters, digits and ._:[]- only, a letter or digit first")
        self.key_model = f"claude-cli:{self.model}"      # its answers keyed apart from any API reader's
        self.calls, self.lock = [], threading.Lock()

    def answer(self, image: bytes, prompt: str) -> dict:
        import shutil
        import subprocess
        import time
        self.base.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="q-", dir=self.base))
        try:
            (work / "frame.png").write_bytes(image)
            cmd = [os.environ.get("CAMSET_CLAUDE_CLI") or CLI, "-p", "--model", self.model, *CLI_FLAGS, prompt]
            t = time.monotonic()
            p = subprocess.run(cmd, cwd=work, env=cli_env(), capture_output=True, text=True, timeout=self.timeout)
            took = time.monotonic() - t
        finally:
            shutil.rmtree(work, ignore_errors=True)
        try:
            d = json.loads(p.stdout or "")
        except ValueError:
            d = {}
        said = str(d.get("result") or "") if isinstance(d, dict) else ""
        failed = p.returncode != 0 or not isinstance(d, dict) or d.get("is_error") or d.get("subtype") != "success"
        if CLI_LIMIT.search(p.stderr or "") or (failed and CLI_LIMIT.search(said or p.stdout or "")):
            raise CliLimit("the command line says a usage or rate limit was reached")
        if failed:
            raise RuntimeError(f"the command line gave no answer (exit {p.returncode})")
        usage = d.get("usage") or {}
        with self.lock:
            self.calls.append({"seconds": took, "api seconds": (d.get("duration_api_ms") or 0) / 1000,
                               "input tokens": sum(usage.get(k) or 0 for k in
                                                   ("input_tokens", "cache_read_input_tokens",
                                                    "cache_creation_input_tokens")),
                               "output tokens": usage.get("output_tokens") or 0, "turns": d.get("num_turns") or 0})
        return vlm.parse_json(said)

    def summary(self) -> dict:
        """The calls' numbers: how many, and the mean of each."""
        n = len(self.calls)
        if not n:
            return {"calls": 0}
        return {"calls": n, **{f"mean {k}": round(sum(c[k] for c in self.calls) / n, 2)
                               for k in ("seconds", "api seconds", "input tokens", "output tokens", "turns")}}


def ask_cli(reader: CliReader, image: bytes, prompt: str, cache, read_only=(), ask: bool = True) -> dict | None:
    """ask_named_reader's contract for the Claude Code command line: kept answers first (usable only), else asked
    and kept in cache; without ask, None."""
    key = vlm.cache_key(image, prompt, reader.key_model)
    for folder in (cache, *read_only):
        got = vlm.cached(key, folder)
        if got is not None:
            return got
    if not ask:
        return None
    return vlm.keep(key, reader.answer(image, prompt), cache)


def ask_all(cfg: dict, asks: list, minutes: float, cache: Path, read_only: tuple, timeout: float,
            say=print, max_questions: int | None = None, dry: bool = False, workers: int | None = None,
            fail_run: int = FAIL_RUN, cli: CliReader | None = None) -> tuple:
    """({(frame, question, transform): the answer, FAILED or NOT_ASKED}, {"asked", "from a cache", "failed", "not
    asked", "stopped after failures", "seconds"}, {ask: the seconds the reader took to answer it, for each one asked
    now}): each question to the reader cfg describes, about each frame (or the part image_of cuts out), once
    (camkit.vlm.ask_named_reader, its answers kept in cache), as many at once as its "parallel" allows. An answer
    already kept (in cache or read_only, and usable) is always taken; once `minutes` have passed (0: at once), once
    max_questions have been asked, or once the reader has failed FAIL_RUN times in a row (its server down, or short of
    memory: the run says so once), nothing more is asked. dry: nothing is asked at all, and each question not kept is
    counted "would ask" (the cost of a run, before it)."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.monotonic()
    deadline = t0 + minutes * 60
    tally = collections.Counter()
    lock = threading.Lock()
    state = {"in a row": 0, "down": False, "asking": 0}
    took = {}

    def asked_of(image, prompt, ask):
        if cli is not None:
            return ask_cli(cli, image, prompt, cache, read_only, ask)
        return vlm.ask_named_reader(cfg, image, prompt, cache, timeout, read_only, ask=ask)

    def kept(image, prompt):
        try:
            return asked_of(image, prompt, False)
        except Exception:        # noqa: BLE001 - no reader to key the answer by: none kept
            return None

    def one(a):
        frame, prompt, transform = a
        image = image_of(frame, transform)
        got = kept(image, prompt)
        with lock:
            capped = max_questions is not None and state["asking"] >= max_questions
            stop = dry or state["down"] or capped or minutes <= 0 or time.monotonic() > deadline
            if got is not None or stop:
                tally["from a cache" if got is not None else "would ask" if dry else "not asked"] += 1
                return a, got if got is not None else NOT_ASKED
            state["asking"] += 1
        t = time.monotonic()
        limited = False
        try:
            got = asked_of(image, prompt, True)
        except CliLimit:
            got, limited = FAILED, True
        except Exception:        # noqa: BLE001 - a failure is the reader's, counted apart from the question's
            got = FAILED
        if got is not FAILED and not vlm.usable(got):
            got = FAILED
        with lock:
            took[a] = time.monotonic() - t
            state["in a row"] = state["in a row"] + 1 if got is FAILED else 0
            if limited and not state["down"]:
                state["down"] = True
                tally["stopped at a usage or rate limit"] = 1
                say(f"  {cfg.get('name')}: a usage or rate limit was reached: asked nothing more")
            if state["in a row"] >= fail_run and not state["down"]:
                state["down"] = True
                say(f"  {cfg.get('name')}: failed {fail_run} questions in a row: asked nothing more")
            tally["failed" if got is FAILED else "asked"] += 1
            done = sum(tally.values())
        if done % 200 == 0:
            say(f"  {cfg.get('name')}: {done} of {len(asks)} questions, {time.monotonic() - t0:.0f} s")
        return a, got
    n = 1 if cli is not None else max(1, min(int(cfg.get("parallel") or 1), workers or int(cfg.get("parallel") or 1)))
    with ThreadPoolExecutor(n) as ex:
        answers = dict(ex.map(one, asks))
    if state["down"] and "stopped at a usage or rate limit" not in tally:
        tally["stopped after failures"] = 1
    return answers, {**tally, "seconds": round(time.monotonic() - t0)}, took


def answers_folder(given, places: list) -> Path:
    """The folder the readers' answers go to: given (--cache), else one in the system's temporary folder. Refused (a
    SystemExit) when it lies inside the runs folder (camkit.paths.runs_top, the clone's runs/) or inside a camera's run
    root the tool reads: the runs are evidence, only read (docs/decisions/0015)."""
    folder = Path(given).expanduser() if given else Path(tempfile.gettempdir()) / "camset_reader_census" / "answers"
    if in_runs(folder, places):
        sys.exit("--cache: the folder given is inside the runs, which this tool only reads (docs/decisions/0015); "
                 "give a folder outside them")
    return folder


def in_runs(path: Path, places: list) -> bool:
    """path lies inside the runs folder (camkit.paths.runs_top, the clone's runs/), a place read or a camera's run root
    the tool reads, or is one of them."""
    from camkit import RUNS
    target = Path(path).expanduser().resolve()
    guarded = [paths.runs_top(), RUNS, *places, *(runs_in(p)[0] for p in places if p.is_dir())]
    return any(target.is_relative_to(Path(g).resolve()) for g in guarded)


def measure(places: list, args) -> dict:
    """--questions: the old questions and the new ones (camkit.reading.QUESTIONS) asked about a sample of each kind's
    proof frames by each reader named, and judged against the option each proof's file proved (judge): counts only."""
    from camkit.frames import load
    from camkit.live import black
    claude = [{"name": f"cli:{m}", "kind": "claude-cli", "model": m, "parallel": 1}
              for m in dict.fromkeys(getattr(args, "claude_cli", None) or [])]
    listed = (vlm.readers() if _has_readers() else []) if claude else vlm.readers(stop=True)
    if args.reader:
        cfgs = []
        for name in args.reader:
            cfg = next((r for r in listed if r.get("name") == name), None)
            if cfg is None:
                sys.exit(f"--reader {name!r}: private/config.json lists no reader of that name")
            cfgs.append(cfg)
    elif claude:
        cfgs = []                        # the Claude readers alone, unless --reader names others beside them
    else:
        names_ = []
        for role in ("second", "third"):
            with contextlib.suppress(vlm.NoReader):
                names_.append(vlm.role(role)["name"])
        cfgs = [r for r in listed if r["name"] in dict.fromkeys(names_) and not vlm.paid(r)]
    cfgs += [c for c in claude if c["name"] not in {str(r["name"]) for r in cfgs}]
    if not cfgs:
        sys.exit("--questions: no reader to ask (name one with --reader or --claude-cli; a paid one is asked only "
                 "when named)")
    hosted = [str(c["name"]) for c in cfgs if is_hosted(c)]
    for k, v in DEFAULTS.items():
        if getattr(args, k, None) is None:
            setattr(args, k, v)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    if not variants or set(variants) - set(VARIANTS):
        sys.exit(f"--variants: some of {', '.join(VARIANTS)}")
    kinds = [k.strip() for k in args.kinds.split(",")] if args.kinds else list(reading.QUESTIONS)
    if set(kinds) - set(reading.QUESTIONS):
        sys.exit(f"--kinds: some of {', '.join(reading.QUESTIONS)}")
    cache = answers_folder(args.cache, places)
    items, read_only, runs = [], [], 0
    for place in places:
        if not place.is_dir():
            sys.exit(f"{place} is not a folder")
        root, found = runs_in(place)
        read_only.append(root / "_cache" / "vlm")
        for run in found:
            runs += 1
            lines = jsonl.read(run / "proofs.jsonl", bad="skip")
            reread = {r["frame"]: str(r["reading"]) for r in jsonl.read(run / "readings.jsonl", bad="skip")
                      if r.get("frame") and r.get("reading")}
            items += [it for it in question_items(run, lines, reread) if it.kind in kinds]
    lit = {}

    def usable(frame) -> bool:           # never asked about a black frame (camkit.reading.ask's rule)
        if frame not in lit:
            lit[frame] = not black(load(frame))
        return lit[frame]
    chosen = sample(items, args.per_kind, usable)
    if args.held_out:
        # a second sample of the same size, the same way, from the frames the first did not take (never tuned on)
        taken = {(k, u[0].frame) for k, units in chosen.items() for u in units}
        chosen = sample([it for it in items if (it.kind, it.frame) not in taken], args.per_kind, usable)
    left_out = collections.Counter()
    if hosted:
        # a hosted reader is sent no frame that may name the network, an address or a credential: every reader of the
        # run is judged on what is left, so the readers' figures stand side by side
        chosen, left_out = hosted_sample(chosen)
        print(f"hosted reader(s) {', '.join(repr(n) for n in hosted)}: {sum(left_out.values())} sampled frames left "
              f"out, never sent (" + (", ".join(f"{k} {v}" for k, v in left_out.most_common()) or "none") + ")",
              file=sys.stderr, flush=True)
    fixes = read_truth(args.truth, places) if args.truth else {}
    split = {k: dict(collections.Counter(old_split(u) for u in chosen.get(k, []))) for k in kinds}
    plans = {}                           # kind -> [(item, the item against the corrected truth, [questions_of])]
    fixes_left_out = collections.Counter()
    for kind in kinds:
        plans[kind] = [(it, corrected(it, fixes.get(kind) or {}, fixes_left_out), questions_of(it, u, variants))
                       for u in chosen.get(kind, []) for it in u]
    asks = []
    for row in itertools.zip_longest(*[plans[k] for k in kinds]):
        for entry in row:
            if entry is not None:
                it, _, qs = entry
                asks += [(it.frame, text, transform) for _, text, _, transform in qs]
    asks = list(dict.fromkeys(asks))

    def table():
        return {k: collections.defaultdict(lambda: collections.defaultdict(collections.Counter)) for k in kinds}
    scores, fixed, both, flags = table(), table(), table(), table()
    asked, timing, verdicts, cli_calls = {}, {k: collections.defaultdict(dict) for k in kinds}, {}, {}
    for cfg in cfgs:
        name = str(cfg["name"])
        if vlm.paid(cfg) and not args.dry_run:
            print(f"{name!r} is a paid reader: each question to it costs money", file=sys.stderr, flush=True)
        cli = CliReader(cfg, cache / "_cli_work", max(args.timeout, 120)) if cfg.get("kind") == "claude-cli" else None
        answers, asked[name], took = ask_all(cfg, asks, args.minutes, cache, tuple(read_only), args.timeout,
                                             say=lambda s: print(s, file=sys.stderr, flush=True),
                                             max_questions=args.max_questions, dry=args.dry_run,
                                             workers=getattr(args, "parallel", None),
                                             fail_run=getattr(args, "fail_run", FAIL_RUN), cli=cli)
        if cli is not None:
            cli_calls[name] = cli.summary()
        verdicts[name] = {}
        for kind in kinds:
            spent = collections.defaultdict(list)
            for it, it_fixed, qs in plans[kind]:
                for qid, text, pick, transform in qs:
                    got = answers.get((it.frame, text, transform), NOT_ASKED)
                    if (it.frame, text, transform) in took:
                        spent[qid].append(took[(it.frame, text, transform)])
                    if got is NOT_ASKED or got is FAILED:
                        verdict = fixed_verdict = "not asked" if got is NOT_ASKED else "reader failed"
                    else:
                        value = pick(got, it)
                        if value is SKIP:
                            continue
                        empty = value is None or (isinstance(value, str) and not value.strip()) or \
                            (isinstance(value, tuple) and not any(str(v or "").strip() for v in value))
                        verdict = "no answer" if empty else judge(it, value)
                        fixed_verdict = "no answer" if empty else judge(it_fixed, value)
                        how = None if empty else together(it_fixed, value)
                        if how:
                            both[kind][qid][name][how] += 1
                        if isinstance(got.get("unsure"), bool) and fixed_verdict in JUDGED:
                            flags[kind][qid][name][f"{'right' if fixed_verdict == 'right' else 'wrong'}, "
                                                   f"{'unsure' if got['unsure'] else 'sure'}"] += 1
                    scores[kind][qid][name][verdict] += 1
                    fixed[kind][qid][name][fixed_verdict] += 1
                    verdicts[name][(kind, qid, it.frame, it.box)] = fixed_verdict
            for qid, secs in spent.items():
                timing[kind][qid][name] = {"asked now": len(secs), "mean s": round(sum(secs) / len(secs), 2),
                                           "max s": round(max(secs), 2)}

    def plain(t):
        return {k: {q: {r: dict(c) for r, c in v.items()} for q, v in t[k].items()} for k in kinds}
    out = {"runs": runs, "readers": [str(c["name"]) for c in cfgs], "variants": variants,
           "sample": "held out" if args.held_out else "tune", "black frames left out": sum(not v for v in lit.values()),
           "sampled": {k: {"frames": len(chosen.get(k, [])), "items": len(plans[k]), **split[k]} for k in kinds},
           "scores": plain(scores), "asked": asked, "both": plain(both), "flags": plain(flags),
           "timing": {k: dict(v) for k, v in timing.items()}, "pairs": pairs(verdicts)}
    if hosted:
        out["left out for hosted readers"] = dict(left_out)
    if cli_calls:
        out["cli calls"] = cli_calls
    if args.dry_run:
        out["dry run"] = True
    if fixes:
        out["scores corrected"] = plain(fixed)
        out["truth fixes left out"] = dict(fixes_left_out)
    return out


def _has_readers() -> bool:
    """private/config.json lists a reader (a Claude reader named on the command line needs none listed there)."""
    try:
        vlm.readers()
    except (vlm.NoReader, SystemExit):
        return False
    return True


def pairs(verdicts: dict) -> dict:
    """{kind: {question: {"A vs B": {"both right", "A right only", "B right only", "both wrong"}}}} for each two
    readers, over the readings both judged (against the corrected truth where one is given; "reader failed" and "not
    asked" left out): where two readers' answers part."""
    out = {}
    names = list(verdicts)
    for a, b in itertools.combinations(names, 2):
        for key, va in verdicts[a].items():
            vb = verdicts[b].get(key)
            if va not in JUDGED or vb not in JUDGED:
                continue
            kind, qid = key[0], key[1]
            how = ("both right" if va == vb == "right" else f"{a} right only" if va == "right"
                   else f"{b} right only" if vb == "right" else "both wrong")
            c = out.setdefault(kind, {}).setdefault(qid, {}).setdefault(f"{a} vs {b}", {})
            c[how] = c.get(how, 0) + 1
    return out


def hosted_refused(item: Item, text: str, kind: str | None) -> str | None:
    """Why a frame may not go to a hosted reader (is_hosted), or None: its run is named for a network or address look
    (NETWORK_RUN), its menu path or label names the camera's identity, a connection or a credential
    (camkit.safety.never_lifted, as the guards judge a row: Display Wi-Fi Info., Display Wired LAN Info., an address or
    a serial number's screen), the screen reader takes it for no menu or option screen (MENU_SCREENS), or the text OCR
    reads on the whole frame names any of those or holds what camkit.vlm.scrub takes out (an address, a key, an e-mail
    address, a home folder). Fails closed: a frame whose text cannot be read, or on which OCR read nothing, is refused
    too."""
    from camkit import safety
    run = item.frame.parent.parent.name
    if NETWORK_RUN.search(run):
        return "a network run"
    for part in [*item.extra.get("path", ()), item.truth if isinstance(item.truth, str) else ""]:
        if part and safety.never_lifted(str(part)):
            return "its menu path"
    if kind not in MENU_SCREENS:
        return "no menu screen"
    if not (text or "").strip():
        return "no text read"
    if safety.never_lifted(text) or safety.identity_row(text):
        return "its screen's words"
    if vlm.scrub(text) != text:
        return "an address on screen"
    return None


def screen_kind(frame: Path) -> str:
    """The kind of screen camkit.screen takes the frame file for."""
    from camkit import screen
    from camkit.frames import load
    return screen.read(load(frame)).kind


def hosted_sample(chosen: dict) -> tuple:
    """(the sample without every frame hosted_refused refuses for any reading it holds, in any kind, {why: frames left
    out}), each frame counted once."""
    items_of = collections.defaultdict(list)
    for units in chosen.values():
        for u in units:
            for it in u:
                items_of[it.frame].append(it)
    try:
        texts = reading.screen_texts(list(items_of))
    except Exception:        # noqa: BLE001 - no OCR to judge with: every frame is refused (fails closed)
        texts = {}
    why_of, left = {}, collections.Counter()
    for f, items in items_of.items():
        kind = screen_kind(f)
        why_of[f] = next((w for w in (hosted_refused(it, texts.get(f), kind) for it in items) if w), None)
        if why_of[f]:
            left[why_of[f]] += 1
    out = {kind: [u for u in units if not any(why_of[it.frame] for it in u)] for kind, units in chosen.items()}
    return out, left


def read_truth(path, places: list = ()) -> dict:
    """--truth: {kind: {a label as the run recorded it: the label as the screen draws it}}, a file kept outside the
    repository and the runs (the owner's labels: docs/decisions/0016), for judging against a truth checked by eye where
    the run recorded OCR's reading of an icon or a garbled letter. Refused (a SystemExit), before it is read, inside
    the runs (in_runs, places the ones read) and inside the clone other than under private/, whose files are never
    committed (docs/decisions/0018)."""
    from camkit import ROOT
    target = Path(path).expanduser().resolve()
    if in_runs(target, list(places)):
        sys.exit("--truth: the file given is inside the runs, which this tool only reads (docs/decisions/0015); keep "
                 "it outside the repository or in private/")
    root = Path(ROOT).resolve()
    if target.is_relative_to(root) and not target.is_relative_to((root / "private").resolve()):
        sys.exit("--truth: the file given is inside the repository, where it could be committed (the owner's labels: "
                 "docs/decisions/0016); keep it outside the repository or in private/")
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"--truth: cannot be read ({type(e).__name__})")
    if not isinstance(got, dict) or not all(isinstance(v, dict) for v in got.values()):
        sys.exit("--truth: it must be {kind: {recorded label: label as drawn}}")
    return got


def corrected(item: Item, fixes: dict, left_out: collections.Counter | None = None) -> Item:
    """item against the corrected truth: each recorded label fixes names (truth, options, a checklist's boxes) put as
    the screen draws it; item itself when fixes change nothing. A fix that would put an option as another option of
    the item is drawn (two options made one, and a reader's answer naming the other one judged right) is not made
    there, and counted in left_out, by kind (its options: the row's, and a checklist's radios and plain boxes)."""
    if not fixes:
        return item
    opts = list(dict.fromkeys(o for o in [*item.options, *item.extra.get("radios", ()), *item.extra.get("boxes_only", ())]
                              if isinstance(o, str)))
    after = {o: fixes[o] if isinstance(fixes.get(o), str) else o for o in opts}
    onto = collections.Counter(after.values())
    merging = {o for o in opts if after[o] != o and onto[after[o]] > 1}
    if merging and left_out is not None:
        left_out[item.kind] += len(merging)
    use = {k: v for k, v in fixes.items() if isinstance(v, str) and k not in merging}

    def fix(x):
        return use.get(x, x) if isinstance(x, str) else x
    truth = [(fix(lab), t) for lab, t in item.truth] if item.kind == "checklist" else fix(item.truth)
    extra = dict(item.extra)
    for k in ("label", "radio_of", "other"):
        if k in extra:
            extra[k] = fix(extra[k])
    for k in ("boxes_only", "radios"):
        if k in extra:
            extra[k] = [fix(x) for x in extra[k]]
    options = list(dict.fromkeys(fix(o) for o in item.options))
    return Item(item.kind, item.frame, truth, options, [str(o) for o in options], item.box, item.old, extra)


def _named(item: Item, text) -> int | None:
    """The option a reading names, by its kind's rule (judge's): an index into item.options, or None."""
    k, t = item.kind, str(text or "")
    if k in ("number field", "look"):
        return _index(number_of(t), item.options)
    if k == "star rating":
        return _index(star_count(t), item.options)
    if k == "look base":
        return names(re.split(r"[\s(]", reading.canonical(t).strip(), maxsplit=1)[0] if t.strip() else "",
                     item.options, "code")
    if k == "axis cell":
        return names(t, item.options, "code")
    return names(t, item.options, item.extra.get("expect", "label"))


def together(item: Item, said) -> str | None:
    """How OCR's reading at the proof (item.extra["ocr"]) and the reader's stand together against the option proved
    (BOTH), or None where the run kept no OCR reading or the reader's is no text. Both wrong are "alike" when they name
    the same other option, or name none and read alike (camkit.reading.said_key): OCR-main and reader-backup would let
    such a reading through."""
    ocr = item.extra.get("ocr")
    if ocr is None or not isinstance(said, (str, int)) or isinstance(said, bool):
        return None
    o, s = judge(item, ocr), judge(item, str(said))
    if o == "right" and s == "right":
        return "both right"
    if s == "right":
        return "OCR wrong, reader right"
    if o == "right":
        return "reader wrong, OCR right"
    i, j = _named(item, ocr), _named(item, str(said))
    if i is not None or j is not None:
        return "both wrong, alike" if i == j else "both wrong, apart"
    a, b = reading.said_key(ocr), reading.said_key(str(said))
    return "both wrong, alike" if a and a == b else "both wrong, apart"


def show_questions(out: dict) -> None:
    """--questions' counts, as text: per kind, the frames sampled, then per question and reader each verdict."""
    print(f"reader questions: {out['runs']} runs read; readers {', '.join(repr(r) for r in out['readers'])} (counts only: "
          "no reading, label, value or file name is printed; docs/decisions/0016)")
    print("  right: names the option the camera's file proved; another option: names another of the row's (with the "
          "decoy question, the list's pick against the screen); no option: names none; no answer: the answer holds "
          "no reading there; reader failed and not asked: the reader's or the tool's, left out of the right rate")
    fixed = out.get("scores corrected")
    print(f"  the {out.get('sample', 'tune')} sample" + ("; corr. %: the right rate against the corrected truth "
                                                          "(--truth)" if fixed else ""))
    for kind, s in out["sampled"].items():
        print(f"\n== {kind}: {s['frames']} frames, {s['items']} readings (the proof's own reading: "
              + ", ".join(f"{k} {s.get(k, 0)}" for k in ("apart", "agreed", "none") if s.get(k))
              + ")")
        print(f"  {'question':16s} {'reader':10s} " + " ".join(f"{v:>14s}" for v in VERDICTS) + f" {'right %':>8s}"
              + (f" {'corr. %':>8s}" if fixed else ""))
        for q, by_reader in out["scores"][kind].items():
            for r, c in by_reader.items():
                f = (fixed or {}).get(kind, {}).get(q, {}).get(r, {})
                print(f"  {q:16s} {r:10s} " + " ".join(f"{c.get(v, 0):14d}" for v in VERDICTS)
                      + f" {percent(c.get('right', 0), sum(c.get(v, 0) for v in JUDGED)):>8s}"
                      + (f" {percent(f.get('right', 0), sum(f.get(v, 0) for v in JUDGED)):>8s}" if fixed else ""))
        for q, by_reader in out["both"][kind].items():
            for r, c in by_reader.items():
                print(f"  OCR and {q} ({r}): " + ", ".join(f"{k} {c.get(k, 0)}" for k in BOTH if c.get(k)))
        for q, by_reader in out["flags"][kind].items():
            for r, c in by_reader.items():
                print(f"  self-check {q} ({r}): " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
        for q, by_reader in out["timing"][kind].items():
            for r, t in by_reader.items():
                print(f"  seconds {q} ({r}): {t['asked now']} asked now, mean {t['mean s']}, max {t['max s']}")
        for q, by_pair in out.get("pairs", {}).get(kind, {}).items():
            for p, c in by_pair.items():
                print(f"  {q}, {p}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    print(f"\nblack frames left out of the sample: {out['black frames left out']}")
    if out.get("truth fixes left out"):
        print("truth fixes not made, as they would make two options one (--truth): " + ", ".join(
            f"{k} {v}" for k, v in out["truth fixes left out"].items()))
    if "left out for hosted readers" in out:
        print("left out, never sent to a hosted reader: " + (", ".join(
            f"{k} {v}" for k, v in out["left out for hosted readers"].items()) or "none"))
    for r, c in out.get("cli calls", {}).items():
        print(f"{r}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    if out.get("dry run"):
        print("dry run: nothing was asked ('would ask' is what a run would ask each reader; 'from a cache' is free)")
    print("asked: " + "; ".join(f"{r}: " + ", ".join(f"{k} {v}" for k, v in a.items()) for r, a in out["asked"].items()))


def percent(n: int, of: int) -> str:
    return f"{100 * n / of:5.1f}%" if of else "   - "


def show(title: str, d: dict) -> None:
    """One source's counts (Tally.as_dict), as text."""
    print(f"\n== {title} ==")
    for k, v in d["counts"].items():
        print(f"  {k:34s} {v:7d}")
    if d["readers"]:
        print("  the reader's reading came from: " + ", ".join(f"{k} {v}" for k, v in d["readers"].items()))
    if not d["sites"]:
        return
    print(f"\n  {'site':22s} {'read':>7s} {'plain':>7s} {'doubtful':>9s} {'doubtful %':>11s}")
    for s, v in d["sites"].items():
        print(f"  {s:22s} {v.get('read', 0):7d} {v.get('plain', 0):7d} {v.get('doubtful', 0):9d} "
              f"{percent(v.get('doubtful', 0), v.get('read', 0)):>11s}")
    print("\n  doubts by kind (a reading can have several):")
    for k, v in d["doubts"].items():
        print(f"    {k:28s} {v:7d}")
    print("\n  doubts by site:")
    for s, v in d["doubts by site"].items():
        print(f"    {s:22s} " + ", ".join(f"{k} {n}" for k, n in v.items()))
    if d["letters"]:
        print("\n  characters outside ASCII (readings holding each):")
        for k, v in d["letters"].items():
            print(f"    {k:56s} {v:7d}")
    print("\n  what the rule makes of each reading:")
    for k, v in d["outcomes"].items():
        print(f"    {k:28s} {v:7d} {percent(v, d['counts'].get('read', 0))}")
    print("\n  outcomes by site:")
    for s, v in d["outcomes by site"].items():
        print(f"    {s:22s} " + ", ".join(f"{k} {n}" for k, n in v.items()))
    print("\n  agreement:")
    for k, v in d["agreement"].items():
        print(f"    {k:58s} {v:7d}")
    if d["third vote"]:
        print("\n  the third vote (the second OCR engine's reading, where the run kept one), on readings left apart:")
        for k, v in d["third vote"].items():
            print(f"    {k:72s} {v:7d}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("where", nargs="*", help="a camera's run root, a run in it, or a path to either (default: the "
                                             "camera the kit works on)")
    ap.add_argument("--model", action="append", default=[], help="a model whose cached answers count too (repeatable; "
                                                                  "the models private/config.json lists always do)")
    ap.add_argument("--json", action="store_true", help="the counts as one JSON object")
    ap.add_argument("--ask", action="store_true", help="ask the second reader about doubtful proof frames with no "
                                                       "reading (answers kept in --cache, never in runs/)")
    ap.add_argument("--limit", type=int, default=None, help="with --ask: ask about this many frames at most")
    ap.add_argument("--cache", default=None, help="with --ask or --questions: the folder the answers are kept in")
    q = ap.add_argument_group("--questions: the reader's questions measured on recorded frames")
    q.add_argument("--questions", action="store_true", help="ask the old questions and each kind's new one about a "
                                                            "sample of proof frames, and judge each answer against "
                                                            "the option the proof's file proved")
    q.add_argument("--reader", action="append", default=[], help="a reader to ask, by its name in private/config.json "
                                                                 "(repeatable; default: the second and third readers, "
                                                                 "a paid one only when named)")
    q.add_argument("--per-kind", type=int, default=None,
                   help=f"frames sampled per kind of screen (default {DEFAULTS['per_kind']})")
    q.add_argument("--kinds", default=None, help="the kinds of screen, comma-separated (default: every kind of "
                                                 "camkit.reading.QUESTIONS)")
    q.add_argument("--variants", default=None, help="the questions asked, comma-separated, some of "
                                                    f"{', '.join(VARIANTS)} (default: all)")
    q.add_argument("--minutes", type=float, default=None,
                   help=f"each reader's time; then only answers already kept are taken (default {DEFAULTS['minutes']:g}; "
                        "0: those alone, nothing asked)")
    q.add_argument("--timeout", type=float, default=None,
                   help=f"seconds a reader gets per question (default {DEFAULTS['timeout']:g})")
    q.add_argument("--held-out", action="store_true", help="a second sample of the same size, the frames the first "
                                                           "does not take: to check a change made on the first")
    q.add_argument("--truth", default=None, help="a file of {kind: {label as recorded: label as drawn}} kept outside "
                                                 "the repository (or in private/) and the runs: each answer judged "
                                                 "against it too")
    q.add_argument("--claude-cli", action="append", default=[], metavar="MODEL",
                   help="a Claude model asked through the Claude Code command line on the person's signed-in plan, "
                        "no API key from the environment passed on (sonnet, haiku, opus or a full id; repeatable; one "
                        "call at a time; hosted: frames that may name the network are left out)")
    q.add_argument("--parallel", type=int, default=4, help="questions asked at once of a reader whose config allows "
                                                           "it (default 4, at most 8; a Claude CLI reader: 1)")
    q.add_argument("--fail-run", type=int, default=FAIL_RUN, help=f"failures in a row after which a reader is asked "
                                                                  f"nothing more (default {FAIL_RUN})")
    q.add_argument("--dry-run", action="store_true", help="ask nothing: count, per reader, the questions it would be "
                                                          "asked and those already kept")
    q.add_argument("--max-questions", type=int, default=None, help="ask each reader this many questions at most")
    args = ap.parse_args(argv)
    if args.limit is not None and not args.ask:
        ap.error("--limit goes with --ask")
    if args.cache and not (args.ask or args.questions):
        ap.error("--cache goes with --ask or --questions")
    if args.ask and args.questions:
        ap.error("--ask and --questions are two modes: give one")
    if not args.questions and (args.reader or args.kinds or args.held_out or args.truth or args.claude_cli
                               or args.dry_run or args.max_questions is not None):
        ap.error("--reader, --kinds, --held-out, --truth, --claude-cli, --dry-run and --max-questions go with "
                 "--questions")
    if not 1 <= args.parallel <= 8:
        ap.error("--parallel: from 1 to 8")
    for m in args.claude_cli:
        if not CLI_MODEL.fullmatch(m):
            ap.error(f"--claude-cli {m!r}: a model's name or id (sonnet, haiku, opus or a full id), letters, digits "
                     "and ._:[]- only, a letter or digit first")
    given = [f"--{k.replace('_', '-')}" for k in DEFAULTS if getattr(args, k) is not None]
    if given and not args.questions:
        print(f"reader census: {', '.join(given)} go with --questions, and are left unused here", file=sys.stderr)
    places = [paths.run_path(w) for w in args.where] or [paths.run_root()]
    # with --json, standard output carries the JSON alone: what the kit says on the way (a reader standing in for
    # another, camkit.vlm.stand_in) goes to standard error
    with contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext():
        out = measure(places, args) if args.questions else census(places, args)
    if args.json:
        print(json.dumps(out, indent=1))
        return 0
    if args.questions:
        show_questions(out)
        return 0
    print(f"reader census: {out['runs']} runs read (counts only: no reading, label or value is printed; "
          "docs/decisions/0016)")
    show("proofs: the bar's OCR at OK time", out["proofs"])
    if not out["proofs"]["counts"].get("with a second OCR engine's reading"):
        print("\n  no proof line keeps a second OCR engine's reading of its option, so what a third vote by it would "
              "settle on these proofs cannot be counted")
    show("menus: each row's OCR on the page scan (navigation)", out["menus"])
    if "asked" in out:
        print(f"\nasked the reader about {out['asked']['frames']} frames, {out['asked']['answered']} answered")
    return 0


def census(places: list, args) -> dict:
    """The counts over the runs in places (Tally.as_dict each, for proofs and menus)."""
    models = [r.get("model") for r in config(required=False).get("readers") or []] + args.model
    asker = None
    if args.ask:
        vlm.readers(stop=True)               # none listed: its sentence, and nothing asked
        models.append(vlm.role("second").get("model"))
    proofs, menus, runs = Tally(), Tally(), 0
    for place in places:
        if not place.is_dir():
            sys.exit(f"{place} is not a folder")
        root, found = runs_in(place)
        if args.ask:
            vlm.CACHE = answers_folder(args.cache or Path(tempfile.gettempdir()) / "camset_reader_census" / root.name,
                                       places)
            asker = asker or Asker(args.limit)
        cache = Cache(root, models)
        for run in found:
            runs += 1
            census_proofs(run, cache, proofs, asker)
            census_menus(run, menus)
    out = {"runs": runs, "proofs": proofs.as_dict(), "menus": menus.as_dict()}
    if asker is not None:
        out["asked"] = {"frames": asker.asked, "answered": asker.answered}
    return out


if __name__ == "__main__":
    sys.exit(main())
