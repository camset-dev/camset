"""How often the one reading rule (camkit.reading, docs/decisions/0022) would doubt OCR and ask the reader: counted over
runs already made, before the rule decides anything on the camera.

    .venv/bin/python kit/tools/reader_census.py [WHERE ...] [--model NAME ...] [--json] [--ask [--limit N] [--cache DIR]]

WHERE is a camera's run root (runs/<model>_fw<fw>/; by default the camera the kit works on), a run in it, or a path to
either. The tool replays camkit.reading's doubts() and agree() over:
  proofs   each run's proofs.jsonl: the bar's OCR at OK time ("shown") of the option each proof chose ("label"), with
           the labels the run proved on the same row standing for the options expected there, and the vision model's
           reading of that frame: the line's own ("vlm"), else kit/tools/reread_proofs.py's (readings.jsonl), else an
           answer already in the readers' cache (<run root>/_cache/vlm) to the option question about the line's chosen
           frame, by a model private/config.json lists or --model names
  menus    each page model (model.json, kit/page_model.py): each menu row's OCR reading against the row labels of its
           page, beside each vision reader's reading of it: how often finding a row (navigation) would doubt OCR
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

The runs are only read: nothing under runs/ is written. No reader is asked unless --ask: then the "second" reader
(camkit.reading.ask: a stand-in when it will not connect, never about a black frame) reads each doubtful proof frame
that has no reading yet, --limit N of them at most, and its answers are kept in --cache (by default a folder in the
system's temporary folder), never in the camera's runs.

Decision 16 (docs/decisions/0016): the counts are for the owner's terminal. The tool prints no reading, no label and
no value, only counts, the kinds of sites and doubts and the Unicode names of letters; still, its output is made from
the owner's runs, so it stays out of commits, issues and the docs unless the owner chooses to send the counts.
"""
import argparse
import collections
import contextlib
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import config, jsonl, paths, reading, vlm  # noqa: E402

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
            calls: bool = True):
        """One reading counted; returns what the rule makes of it (camkit.reading.outcome). calls False: its reader
        call, if the rule would add one, is counted by the caller (one question reads a number-entry screen's boxes)."""
        ds = reading.doubts(shown, expect, choices=choices, lit=True)
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
            how = tally.add("menu row", shown, label, said, "label", labels)
            if how in reading.APART:
                third_vote(tally, shown, who, said, said_by.get("ocr2"), label, "label", labels)


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
    ap.add_argument("--cache", default=None, help="with --ask: the folder its answers are kept in")
    args = ap.parse_args(argv)
    if (args.limit is not None or args.cache) and not args.ask:
        ap.error("--limit and --cache go with --ask")
    places = [paths.run_path(w) for w in args.where] or [paths.run_root()]
    # with --json, standard output carries the JSON alone: what the kit says on the way (a reader standing in for
    # another, camkit.vlm.stand_in) goes to standard error
    with contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext():
        out = census(places, args)
    if args.json:
        print(json.dumps(out, indent=1))
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
        vlm.check_readers()                  # none listed: its sentence, and nothing asked
        models.append(vlm.role("second").get("model"))
    proofs, menus, runs = Tally(), Tally(), 0
    for place in places:
        if not place.is_dir():
            sys.exit(f"{place} is not a folder")
        root, found = runs_in(place)
        if args.ask:
            vlm.CACHE = Path(args.cache) if args.cache else Path(tempfile.gettempdir()) / "camset_reader_census" / root.name
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
