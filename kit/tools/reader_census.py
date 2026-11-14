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

Decision 16 (docs/decisions/0016): the counts are for the owner's terminal. The tool prints no reading, no label and
no value, only counts, the kinds of sites and doubts and the Unicode names of letters; still, its output is made from
the owner's runs, so it stays out of commits, issues and the docs unless the owner chooses to send the counts.
"""
import argparse
import collections
import contextlib
import itertools
import json
import re
import sys
import tempfile
import threading
from pathlib import Path

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
VARIANTS = ("old", "new", "options", "decoy")
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
    """A reading with each rating star written as "*" (BLACK STAR): readers and OCR write the camera's stars either
    way, and a run's labels keep them as drawn."""
    return str(text or "").replace("\u2605", "*")


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
        return judge_boxes(item, value)
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


def questions_of(item: Item, frame_items: list, variants) -> list:
    """[(question id, the question's whole text, pick)] item is judged by: the old questions, the kind's new one
    (camkit.reading.QUESTIONS), and the new one with the options expected there handed to the reader ("options") or
    with every option but the one the file proved ("decoy": a reader that picks from the list rather than read the
    screen names another option there). A number-entry screen's options are said box by box (frame_items: the frame's
    items, a box each)."""
    out = []
    if "old" in variants:
        out += [(f"old: {key}", vlm.PROMPTS[key], pick) for key, pick in OLD[item.kind]]
    new = vlm.PROMPTS[reading.QUESTIONS[item.kind].prompt]
    pick = NEW_PICK.get(item.kind, _selected)
    if "new" in variants:
        out.append(("new", new, pick))
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
        out.append(("new + options", vlm.with_options(new, full), pick))
    if "decoy" in variants:
        out.append(("new + decoy", vlm.with_options(new, fewer), pick))
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
        if kind == "list" and STAR_LABEL.fullmatch(lab):
            counts = sorted({len(_bare(x["label"])) for x in row if STAR_LABEL.fullmatch(_bare(x["label"]))})
            out.append(Item("star rating", frame, len(lab), counts, [str(c) for c in counts], old=old))
        elif kind == "list" or kind in ("sidelist", "table", "dialog") or (kind == "axis" and not r.get("final")):
            site = {"list": "scale" if r.get("scale") else "list", "sidelist": "side list", "table": "table picker",
                    "dialog": "carousel", "axis": "axis"}[kind]
            if site == "list" and screen.read(load(frame)).kind == "shooting":
                continue                 # no menu up on the frame
            if expect_of(r) == "label" and drawn_alike(lab, labels):
                continue
            out.append(Item(site, frame, lab, labels, old=old, extra={"expect": expect_of(r)}))
            if kind == "dialog":
                out.append(Item("title", frame, str((r.get("path") or [""])[-1]), old=None))
            codes = [c for c in dict.fromkeys(cell_code(x) for x in labels) if c]
            if kind in ("dialog", "axis") and cell_code(lab) and len(codes) > 1 \
                    and axis_lit_x(load(frame).image) is not None:
                out.append(Item("axis cell", frame, cell_code(lab), codes, old=old))
        elif kind == "lookbase":
            out.append(Item("look base", frame, lab, labels, old=old))
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
                out.append(Item("checklist", frame, boxes, every, old=old, extra={"label": lab}))
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
                out.append(Item("number field", frame, number_of(p), values, box=k, old=old,
                                extra={"changed": changed}))
    return out


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


def ask_all(cfg: dict, asks: list, minutes: float, cache: Path, read_only: tuple, timeout: float,
            say=print) -> tuple:
    """({(frame, question): the answer, FAILED or NOT_ASKED}, {"asked", "from a cache", "failed", "not asked",
    "stopped after failures", "seconds"}): each question to the reader cfg describes, about each frame, once
    (camkit.vlm.ask_named_reader, its answers kept in cache), as many at once as its "parallel" allows. An answer
    already kept (in cache or read_only, and usable) is always taken; once `minutes` have passed (0: at once), or once
    the reader has failed FAIL_RUN times in a row (its server down, or short of memory: the run says so once), nothing
    more is asked."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    t0 = time.monotonic()
    deadline = t0 + minutes * 60
    tally = collections.Counter()
    lock = threading.Lock()
    state = {"in a row": 0, "down": False}

    def kept(image, prompt):
        try:
            return vlm.ask_named_reader(cfg, image, prompt, cache, timeout, read_only, ask=False)
        except Exception:        # noqa: BLE001 - no reader to key the answer by: none kept
            return None

    def one(a):
        frame, prompt = a
        image = frame.read_bytes()
        got = kept(image, prompt)
        with lock:
            stop = state["down"] or minutes <= 0 or time.monotonic() > deadline
            if got is not None or stop:
                tally["from a cache" if got is not None else "not asked"] += 1
                return a, got if got is not None else NOT_ASKED
        try:
            got = vlm.ask_named_reader(cfg, image, prompt, cache, timeout, read_only)
        except Exception:        # noqa: BLE001 - a failure is the reader's, counted apart from the question's
            got = FAILED
        if got is not FAILED and not vlm.usable(got):
            got = FAILED
        with lock:
            state["in a row"] = state["in a row"] + 1 if got is FAILED else 0
            if state["in a row"] >= FAIL_RUN and not state["down"]:
                state["down"] = True
                say(f"  {cfg.get('name')}: failed {FAIL_RUN} questions in a row: asked nothing more")
            tally["failed" if got is FAILED else "asked"] += 1
            done = sum(tally.values())
        if done % 200 == 0:
            say(f"  {cfg.get('name')}: {done} of {len(asks)} questions, {time.monotonic() - t0:.0f} s")
        return a, got
    with ThreadPoolExecutor(max(1, int(cfg.get("parallel") or 1))) as ex:
        answers = dict(ex.map(one, asks))
    if state["down"]:
        tally["stopped after failures"] = 1
    return answers, {**tally, "seconds": round(time.monotonic() - t0)}


def answers_folder(given, places: list) -> Path:
    """The folder the readers' answers go to: given (--cache), else one in the system's temporary folder. Refused (a
    SystemExit) when it lies inside the runs folder (camkit.paths.runs_top, the clone's runs/) or inside a camera's run
    root the tool reads: the runs are evidence, only read (docs/decisions/0015)."""
    from camkit import RUNS
    folder = Path(given).expanduser() if given else Path(tempfile.gettempdir()) / "camset_reader_census" / "answers"
    target = folder.resolve()
    guarded = [paths.runs_top(), RUNS, *places, *(runs_in(p)[0] for p in places if p.is_dir())]
    for g in guarded:
        g = Path(g).resolve()
        if target == g or target.is_relative_to(g):
            sys.exit("--cache: the folder given is inside the runs, which this tool only reads (docs/decisions/0015); "
                     "give a folder outside them")
    return folder


def measure(places: list, args) -> dict:
    """--questions: the old questions and the new ones (camkit.reading.QUESTIONS) asked about a sample of each kind's
    proof frames by each reader named, and judged against the option each proof's file proved (judge): counts only."""
    from camkit.frames import load
    from camkit.live import black
    listed = vlm.readers(stop=True)
    if args.reader:
        cfgs = []
        for name in args.reader:
            cfg = next((r for r in listed if r.get("name") == name), None)
            if cfg is None:
                sys.exit(f"--reader {name!r}: private/config.json lists no reader of that name")
            cfgs.append(cfg)
    else:
        names_ = []
        for role in ("second", "third"):
            with contextlib.suppress(vlm.NoReader):
                names_.append(vlm.role(role)["name"])
        cfgs = [r for r in listed if r["name"] in dict.fromkeys(names_) and not vlm.paid(r)]
    if not cfgs:
        sys.exit("--questions: no reader to ask (name one with --reader; a paid one is asked only when named)")
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
    split = {k: dict(collections.Counter(old_split(u) for u in chosen.get(k, []))) for k in kinds}
    plans = {}                           # kind -> [(item, [(question id, text, pick)])]
    for kind in kinds:
        plans[kind] = [(it, questions_of(it, u, variants)) for u in chosen.get(kind, []) for it in u]
    asks = []
    for row in itertools.zip_longest(*[plans[k] for k in kinds]):
        for entry in row:
            if entry is not None:
                it, qs = entry
                asks += [(it.frame, text) for _, text, _ in qs]
    asks = list(dict.fromkeys(asks))
    scores = {k: collections.defaultdict(lambda: collections.defaultdict(collections.Counter)) for k in kinds}
    asked = {}
    for cfg in cfgs:
        name = str(cfg["name"])
        if vlm.paid(cfg):
            print(f"{name!r} is a paid reader: each question to it costs money", file=sys.stderr, flush=True)
        answers, asked[name] = ask_all(cfg, asks, args.minutes, cache, tuple(read_only), args.timeout,
                                       say=lambda s: print(s, file=sys.stderr, flush=True))
        for kind in kinds:
            for it, qs in plans[kind]:
                for qid, text, pick in qs:
                    got = answers.get((it.frame, text), NOT_ASKED)
                    if got is NOT_ASKED:
                        verdict = "not asked"
                    elif got is FAILED:
                        verdict = "reader failed"
                    else:
                        value = pick(got, it)
                        if value is SKIP:
                            continue
                        empty = value is None or (isinstance(value, str) and not value.strip()) or \
                            (isinstance(value, tuple) and not any(str(v or "").strip() for v in value))
                        verdict = "no answer" if empty else judge(it, value)
                    scores[kind][qid][name][verdict] += 1
    return {"runs": runs, "readers": [str(c["name"]) for c in cfgs], "variants": variants,
            "black frames left out": sum(not v for v in lit.values()),
            "sampled": {k: {"frames": len(chosen.get(k, [])), "items": len(plans[k]), **split[k]} for k in kinds},
            "scores": {k: {q: {r: dict(c) for r, c in v.items()} for q, v in scores[k].items()} for k in kinds},
            "asked": asked}


def show_questions(out: dict) -> None:
    """--questions' counts, as text: per kind, the frames sampled, then per question and reader each verdict."""
    print(f"reader questions: {out['runs']} runs read; readers {', '.join(repr(r) for r in out['readers'])} (counts only: "
          "no reading, label, value or file name is printed; docs/decisions/0016)")
    print("  right: names the option the camera's file proved; another option: names another of the row's (with the "
          "decoy question, the list's pick against the screen); no option: names none; no answer: the answer holds "
          "no reading there; reader failed and not asked: the reader's or the tool's, left out of the right rate")
    for kind, s in out["sampled"].items():
        print(f"\n== {kind}: {s['frames']} frames, {s['items']} readings (the proof's own reading: "
              + ", ".join(f"{k} {s.get(k, 0)}" for k in ("apart", "agreed", "none") if s.get(k))
              + ")")
        print(f"  {'question':16s} {'reader':10s} " + " ".join(f"{v:>14s}" for v in VERDICTS) + f" {'right %':>8s}")
        for q, by_reader in out["scores"][kind].items():
            for r, c in by_reader.items():
                judged = sum(c.get(v, 0) for v in JUDGED)
                print(f"  {q:16s} {r:10s} " + " ".join(f"{c.get(v, 0):14d}" for v in VERDICTS)
                      + f" {percent(c.get('right', 0), judged):>8s}")
    print(f"\nblack frames left out of the sample: {out['black frames left out']}")
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
    args = ap.parse_args(argv)
    if args.limit is not None and not args.ask:
        ap.error("--limit goes with --ask")
    if args.cache and not (args.ask or args.questions):
        ap.error("--cache goes with --ask or --questions")
    if args.ask and args.questions:
        ap.error("--ask and --questions are two modes: give one")
    if not args.questions and (args.reader or args.kinds):
        ap.error("--reader and --kinds go with --questions")
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
