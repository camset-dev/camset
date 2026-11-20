"""Build the page model from a page scan: structure from pixels, labels and values by vote.

    .venv/bin/python kit/page_model.py [--vlm] [kit2_page_scan]        # a run in the camera's runs/<model>_fw<fw>/
    .venv/bin/python kit/page_model.py --mode Stills kit2_page_scan    # only record the mode an older scan was made in

With --vlm, runs the VLM page-reading pass (asking the "second" reader, 8 at a time, or the reader --reader NAME
names when that one is away) before building the model; a scan folder a --network run marked (camkit.vlm.LOCAL_MARKER)
is read by a local reader only (camkit.vlm.local_only_runs), and the tool stops before asking anything otherwise.
For each scanned page it lines up the pixel reader's rows (how many, which are greyed: authoritative
for structure), OCR (and a second OCR engine as "ocr2" when one is installed), and each VLM's reading (only answers already in the VLM cache are
used: this never calls a server). Labels the user confirmed (<run>/user_labels.json, keyed by page
counter and row) count as a reading too, and so do labels read by eye off the frame where the readers
disagreed (<run>/checked_labels.json, same keys, each naming its frame). A label or value is "confirmed" when two of those sources agree
after icon noise is stripped; otherwise every source's reading is kept for review. Where the camera draws an icon before
a row's label, OCR reads the row again with the icon painted over and the label is voted on what lies right of it
(icon_vote); the row's "icon" says what was read, left out or kept.

Writes <run>/model.json and prints a summary with the disagreements. A runner takes a scan by default only while its
model.json is built from its lap (runner.scan_unready: the lap's scan id, recorded in <run>/scan_mode.json as
"model_of", for a scan made since 2026-11-11; else the model newer than the lap): after a lap is written again, run
this again.

--mode MODE records the shooting mode the scan was made in (<run>/scan_mode.json, that one field, runner.record_mode)
and does nothing else: for a scan made before kit/page_scan.py recorded it itself (2026-11-11), which no runner takes
by default until it does (runner.latest_scan). Say only a mode the scan's own run log or frames show; a scan that
records a mode keeps it.
"""
import argparse
import collections
import contextlib
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import config, match, ocr, paths, row_names, safety  # noqa: E402
from camkit.runs import private_if_marked  # noqa: E402
from camkit.screen import MENU_ROW_PITCH, MENU_ROW_TOP  # noqa: E402
from camkit.vlm import PROMPTS, NoReader, cache_key, cached, local_only_runs, make_reader, readers, role  # noqa: E402
from runner import (SCAN_MODES, OcrUnavailable, read_frames, read_json, record_mode, record_model,  # noqa: E402
                    scan_mode, scan_unready, write_json)


def alive(cfg) -> bool:
    body = {"model": cfg["model"], "max_tokens": 3, "messages": [{"role": "user", "content": "OK"}],
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(cfg["url"] + "/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=50).read()
        return True
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "not yet:", str(e)[:80], flush=True)
        return False


def vlm_read_pages(root: Path, reader_name: str | None = None):
    """Ask a reader for every page's first frame (answers go to the VLM cache): the "second" reader, or the
    configured reader --reader names when that one is away (a server on another machine switched off)."""
    listed = readers(stop=True)                 # none listed: its sentence, and nothing asked
    cfg = role("second") if not reader_name else next((r for r in listed if r["name"] == reader_name), None)
    if cfg is None:
        sys.exit(f"--reader {reader_name!r}: no reader of that name in private/config.json")
    # a run folder a --network run marked: local readers only, refused before even the first "alive" request
    local_only_runs(root)
    try:
        reader = make_reader(cfg)
    except NoReader as e:
        sys.exit(f"{e}: name a local reader with --reader; nothing asked")
    for _ in range(40):
        if cfg.get("kind") == "anthropic" or alive(cfg):     # Claude: the SDK retries for itself
            break
        time.sleep(60)
    else:
        sys.exit(f"gave up waiting for {cfg['name']}")
    firsts = collections.OrderedDict()
    for r in read_json(root / "scan_rekeyed.json"):
        if r["kind"] == "menu":
            firsts.setdefault(r["page"], r)

    def one(rec):
        try:
            reader.ask((root / "shots" / rec["frame"]).read_bytes(), PROMPTS["menu"])
            return "ok"
        except Exception as e:
            return f"error {e}"
    t = time.monotonic()
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, firsts.values()))
    print(f"read {sum(r == 'ok' for r in res)}/{len(res)} pages in {time.monotonic() - t:.0f} s", flush=True)


def cached_vlm(image: bytes, kind: str) -> dict:
    """{reader name: answer} for the answers already cached; no requests."""
    out = {}
    for r in config().get("readers") or []:
        answer = cached(cache_key(image, PROMPTS[kind], r["model"]))     # camkit.vlm's own cache, as a reader keeps it
        if answer is not None:
            out[r["name"]] = answer
    return out


# An icon OCR reads in front of a label, which key_text leaves out: the marks before its first letter, digit or bracket,
# but a sign right before a digit, which is the number's own ("+0.3 EV", "-1 EV", OCR's double dagger for the
# plus-minus); then a word of one letter, of two capitals or of two small letters, before a capital or a bracket ("S
# Focus Area", "MR Camera Set. Memory", "ni Shoe Audio Set."), or one small letter glued before a capital ("vDisplay").
# A word with a digit ("1 Sec", "10 Sec. 3 Img.") or of a capital and a small letter ("Tv", "Av", "Lo", "Hi") is the
# label's own. A letter outside A-Z in front is a mark, as before (OCR's Cyrillic С of "С.Temp./Filter"). These
# rules are this module's: until 2026-11-18 it borrowed the guards' safety.clean_label, which drops any sign and any word
# of one or two characters on purpose, and merged +0.3 EV with -0.3 EV, "1 Sec" with "2 Sec" and Av with Tv (review,
# finding 13). An icon read as a digit or as a capital and a small letter ("8 Exposure Comp.", "Px Proxy Settings")
# cannot be told from a word of the label's own: such a reading is a doubt, which each caller asks the reader about
_ICON_MARKS = re.compile(r"^(?:(?![+\-±‡]\d)[^A-Za-z0-9(])+")
_ICON_WORD = re.compile(r"^(?:[A-Za-z]|[A-Z]{2}|[a-z]{2})\s+(?=[A-Z(])|^[a-z](?=[A-Z])")
_DASHES = str.maketrans(dict.fromkeys("−–—‐‑﹣－", "-"))
# a sign before a lone zero is the plus-minus the camera draws there, however it is read ("+0.0", "-0", "+-0", OCR's
# double dagger)
_SIGN_ZERO = re.compile(r"^(?:\+-|-\+|[+\-±‡])\s*(?=0(?:\.0+)?(?![\d.]))")


def icon_cut(s) -> str:
    """A label or a reading without the icon OCR read in front of it (_ICON_MARKS, then _ICON_WORD), every dash a
    hyphen first. Case kept."""
    t = _ICON_MARKS.sub("", str(s or "").strip().translate(_DASHES))
    return _ICON_WORD.sub("", t).strip()


def _key(t: str) -> str:
    t = _SIGN_ZERO.sub("±", t.strip()).lower().replace("›", ">").replace("’", "'")
    t = re.sub(r"(?<=\d)\.(?=\d)", "p", t)                  # a decimal point between digits stays
    return re.sub(r"[\s.]+", "", t.translate(str.maketrans("l1|0", "iiio")))    # OCR look-alikes


def key_text(s) -> str:
    """Compare labels/values without icon noise (icon_cut), case, spacing, stops or OCR look-alikes, a number's sign
    and decimal point and every word but an icon kept: no two options of one setting of the a1 II's definition fold to
    one key (kit/tests/test_review_pipeline.py)."""
    return _key(icon_cut(s))


def same_text(a, b) -> bool:
    """Two readings of one row label (or two labels): equal (key_text); or equal but for one or two letters in front of
    one of them, an icon OCR read as letters, that end where a word starts: a capital or a bracket glued after them
    ("vdFor viewfinder"; one digit glued before a capital too: "9Lo(E-Shutter)"), or a space after one letter, two
    capitals or two small letters ("S after still img crt"),
    never letters a small letter follows (Uncompressed is not Compressed), nor a digit or a sign ("15 images/s" is not
    "5 images/s"), what is left four characters or more; or equal but for a run of short words in front of one of them
    (_short_words: "9 Focus Area Limit", "Px Proxy Settings"). A number, a sign, a decimal point and every word of both
    are compared ("1 Sec" is not "2 Sec", +0.3 EV not -0.3 EV). Options of one list compare by same_option."""
    return _same(a, b, words=True)


def same_option(a, b) -> bool:
    """same_text for two options of one list, or two readings of one option: an icon read as a lone word of a capital
    and a small letter in front of one of them is never left out ("Tv Auto/Manual Switch" and "Av Auto/Manual Switch" are
    two options of one Fn Menu list, the second named "Auto/Manual Switch" until 2026-11-20), so no two options of one
    setting of the a1 II's definition are one
    (kit/tests/test_review_pipeline.py); a reading with such an icon ("Px Proxy Settings") is a doubt, which the caller
    asks the third reader or the reader about. Rows keep same_text, where that icon is common ("Sc Power Save by
    Monitor") and keeps_lead guards a row's own short word."""
    return _same(a, b, words=False)


def _same(a, b, words: bool) -> bool:
    ka, kb = key_text(a), key_text(b)
    if not ka or not kb:
        return False
    return ka == kb or _glued(a, kb) or _glued(b, ka) or _short_words(a, kb, words) or _short_words(b, ka, words)


def _short_words(text, other: str, words: bool = True) -> bool:
    """`text` is `other` (a key_text) but for an icon OCR read as a run of short words in front of it (camkit.match.ICON:
    "9 Focus Area Limit", "sa R0 Shoot Mode", "R (› Focal Length", "Px Proxy Settings"); with words False never a lone
    word of a capital and a small letter (Tv, Av: a word of a label's own as often as an icon); and a run holding a digit
    only once, before a label of two words or more that starts with a capital and holds no digit itself (a number before
    a unit is the label's own: "Sec" is not "2 Sec", nor "Images" "9 Images")."""
    t = _ICON_MARKS.sub("", str(text or "").strip().translate(_DASHES))
    m = match.ICON.match(t)
    if not m:
        return False
    run = m.group(0).split()
    for n in range(1, len(run) + 1):
        lead = run[:n]
        rest = re.sub(rf"^(?:\S{{1,2}}\s+){{{n}}}", "", t)
        if not rest or _key(rest) != other:
            continue
        if n == 1 and not words and re.fullmatch(r"[A-Z][a-z]", lead[0]):
            return False
        digits = [w for w in lead if re.search(r"\d", w)]
        # two numbers are a number of the label's own ("1 / 2 This Image")
        return not digits or (len(digits) == 1 and len(rest.split()) >= 2 and rest[:1].isupper()
                              and not re.search(r"\d", rest))
    return False


def _glued(text, other: str) -> bool:
    """`text` is `other` (a key_text) but for one or two letters in front of it at a word's start (same_text)."""
    t = icon_cut(text)
    if len(other) < 4:
        return False
    if t[:1].isdigit() and t[1:2].isupper() and _key(t[1:]) == other:
        return True                          # an icon read as one digit glued before a capital ("9Lo(E-Shutter)")
    letters = 0
    for i, c in enumerate(t):
        if c == " " and letters:
            continue
        if not c.isalpha() or letters == 2:
            return False
        letters += 1
        head, rest = t[:i + 1].replace(" ", ""), t[i + 1:]
        if not rest:
            return False
        if rest[0] == " ":
            if len(head) == 2 and not (head.isupper() or head.islower()):
                continue
        elif not (rest.lstrip(".")[:1].isupper() or rest[0] == "("):        # "C.Temp./Filter": a stop between
            continue
        if _key(rest) == other:
            return True
    return False


def vote(readings: dict) -> tuple:
    """(value, agreed_by): the cleanest reading another source matches (VLM before OCR, shorter
    before longer, then the shorter raw text: one OCR engine keeps an icon read as "•" that the
    other drops, 2026-10-30), else (None, [])."""
    names = sorted(readings, key=lambda n: (n in ("ocr", "ocr2"), len(key_text(readings[n])),
                                            len(str(readings[n] or ""))))
    for a in names:
        same = [b for b in names if b != a and same_text(readings[a], readings[b])]
        if same:
            return readings[a], sorted([a] + same)
    return None, []


# An icon the camera draws before a row's label (camkit.screen.label_icons): OCR reads the row again with every icon of
# the frame painted over (covered_readings), and that reading, which starts where the label's text starts, says what any
# other reading read in front of the label: the icon, left out (icon_lead). A page's label is then voted on as before
# (icon_vote, page_labels), a crawl's submenu label cut so (icon_label); both keep the label as read wherever they cannot
# tell, and say in the row's "icon" what they read, left out or kept, and why. The readings the row keeps are the raw
# ones (2026-11-19: the reader read the S&Q box as "S&Q" on one crawl of S&Q Settings and not on another, and the row's
# proof was refused under the name the map gave it).
OCR_SOURCES = ("ocr", "ocr2")
ICON_LEAD = row_names.ICON_LEAD          # characters (spaces aside) one icon is read as at most: "S&Q", "LAN", "MR"
MENU_LABEL, SUBMENU_LABEL = (140, 470), (55, 470)       # the label's column on a menu page and on a submenu (x0, x1)
# how far OCR's first line may start before the last icon's end (Apple Vision's box of a word starts up to 12 px before
# a painted icon's end; RapidOCR's within 1) and after the text's start (a line starting later lost the first word)
LEAD_SLACK, TEXT_SLACK = 14, 4


def page_icons(path: Path, n: int) -> tuple:
    """(picture, {row: (band, boxes, text_x)}): the menu page frame at `path` and the icons drawn before its first `n`
    rows' labels (camkit.screen.label_icons), each row where page_model reads its label (MENU_ROW_TOP, MENU_ROW_PITCH);
    (None, {}) for a frame that cannot be loaded (its OCR readings say why)."""
    from camkit import frames, screen
    try:
        image = frames.load(path).image
    except Exception:
        return None, {}
    rows = {}
    for i in range(n):
        band = (MENU_ROW_TOP + MENU_ROW_PITCH * i, MENU_ROW_TOP + MENU_ROW_PITCH * i + 52)
        boxes, text_x = screen.label_icons(image, band, MENU_LABEL[0])
        if boxes:
            rows[i] = (band, boxes, text_x)
    return image, rows


def covered_readings(frames: dict, column, engines: dict) -> dict:
    """{frame: {row: {source: text}}}: OCR's reading of each row's label with every icon of its frame painted over
    (camkit.screen.cover_icons). frames: {frame: (image, {row: (band, boxes, text_x)})}, the icons camkit.screen.
    label_icons found; column: the label's (x0, x1), MENU_LABEL or SUBMENU_LABEL; engines: {source: OCR engine} ("ocr":
    None for the configured one, "ocr2": the second). A reading is kept only where OCR's first line in the row starts
    where the label's text starts (from LEAD_SLACK px before the last icon's end, which OCR's box of a word takes in, to
    TEXT_SLACK px after text_x): never one that kept a piece of an icon, nor one that left the label's first word out. The
    pictures are written to a folder of their own, gone after, and read in one batch per engine (a frame the batch
    cannot read, again alone); a frame or an engine that fails gives no reading (the label stays as read)."""
    import tempfile

    from camkit import screen
    from PIL import Image
    out = {f: {} for f in frames}
    with tempfile.TemporaryDirectory(prefix="camset-icons-") as tmp:
        files = {}
        for n, (f, (image, rows)) in enumerate(frames.items()):
            if not rows:
                continue
            covered = image
            for band, boxes, _ in rows.values():
                covered = screen.cover_icons(covered, band, boxes)
            files[f] = Path(tmp) / f"{n:05d}.png"
            Image.fromarray(covered).save(files[f])
        for source, eng in engines.items():
            try:
                read = ocr.read(list(files.values()), eng) if files else {}
            except Exception:               # one frame the helper cannot read: each frame alone, from the cache
                read = {}
                for p in files.values():
                    with contextlib.suppress(Exception):        # an engine that will not run: no reading
                        read.update(ocr.read([p], eng))
            for f, p in files.items():
                lines = read.get(p)
                if lines is None:
                    continue
                for row, (band, boxes, text_x) in frames[f][1].items():
                    got = [ln for ln in lines if ln.inside((column[0], band[0], column[1], band[1]))]
                    if got and boxes[-1][1] - LEAD_SLACK <= min(ln.x for ln in got) <= text_x + TEXT_SLACK:
                        out[f].setdefault(row, {})[source] = " ".join(ln.text for ln in got).strip()
    return out


def icon_lead(reading, covered) -> tuple | None:
    """(rest, lead, glued): the reading `reading` as far as OCR's reading right of the icon (`covered`) has it, compared
    as key_text compares (case, spacing, stops, OCR's look-alikes), what it read in front of that (the icon), and whether
    that is glued to the label's first letter ("RISO") rather than a word of its own ("Saa Record Setting"). None where
    the reading does not end so or reads nothing in front."""
    t, want = str(reading or "").strip(), _key(str(covered or ""))
    if not want:
        return None
    for i in range(1, len(t)):
        if _key(t[i:]) == want:
            lead, rest = t[:i], t[i:]
            if not lead.strip():
                return None
            return rest.strip(), lead.strip(), not (lead[-1].isspace() or rest[:1].isspace())
    return None


def _lead_ok(lead: str, icons: int) -> bool:
    """Whether what a reading read in front of a label can be the reading of `icons` icons (ICON_LEAD characters each)."""
    return 0 < len(re.sub(r"\s", "", lead)) <= ICON_LEAD * max(1, icons)


def icon_vote(labels: dict, covered: dict, label, by: list, icons) -> tuple:
    """(label, agreed_by, record) of a page row whose label starts after icons (`icons`, camkit.screen.label_icons'
    boxes), from its readings (`labels`: {source: text}), OCR's readings right of the icons (`covered`: {source: text},
    covered_readings) and the label voted before (`label`, `by`: vote's). Each OCR engine's reading is its reading right
    of the icons; any other reader's, where it is that with a word of its own in front (icon_lead, ICON_LEAD characters
    an icon), is the rest; then vote. The new label is taken only where a reader other than OCR agrees on it, and it is
    the label voted before, or that with something in front left out, or there was none; else the label stays as voted
    before. record: what OCR read right of the icons, what each reading had in front, left out, and "kept" with why
    where the label stays (page_labels keeps it too where another row of the page has the new label)."""
    cut, left_out = {}, {}
    for name, text in labels.items():
        if name in covered:
            cut[name] = covered[name]
            got = icon_lead(text, covered[name])
            if got:
                left_out[name] = got[1]
            continue
        got = next((g for g in (icon_lead(text, c) for c in covered.values()) if g), None)
        if got and not got[2] and _lead_ok(got[1], len(icons)):
            cut[name], left_out[name] = got[0], got[1]
        else:
            cut[name] = text
    new, nby = vote(cut)
    record = {"icons": [list(b) for b in icons], "covered": dict(covered), "left_out": left_out}
    before = icon_lead(label, new) if label and new else None
    if not new:
        why = "no two readings agree on the label right of the icon"
    elif all(n in OCR_SOURCES for n in nby):
        why = f"only OCR reads {new!r} there"
    elif label and _key(label) != _key(new) and not (before and _lead_ok(before[1], len(icons))):
        why = f"{new!r} is not the label voted before ({label!r}) with something in front left out"
    else:
        return new, nby, record
    return label, by, {**record, "kept": why}


def page_labels(readings: list, icons: dict, covered: dict) -> list:
    """[(label, agreed_by, icon)] of a page's rows, from each row's readings ({source: text}, in row order): vote's,
    and on a row whose label starts after icons (`icons`: {row: (band, boxes, text_x)}, page_icons) icon_vote's, with
    OCR's readings right of them (`covered`: {row: {source: text}}, covered_readings); icon is that row's record, else
    None. A label icon_vote changed to one another row of the page has too goes back to the label voted before: there
    the icon is what tells the two apart (the a1 II's Shoot Mode, and the Shoot Mode an S&Q box and a dial are drawn
    before)."""
    out, before = [], {}
    for i, labels in enumerate(readings):
        label, by = vote(labels)
        icon = None
        if i in icons:
            before[i] = (label, by)
            label, by, icon = icon_vote(labels, covered.get(i, {}), label, by, icons[i][1])
        out.append((label, by, icon))
    for i, (label, _, icon) in enumerate(out):
        old = before.get(i)
        if old is None or not label or _key(old[0] or "") == _key(label):
            continue
        twin = next((j for j, o in enumerate(out) if j != i and o[0] and _key(o[0]) == _key(label)), None)
        if twin is not None:
            out[i] = (*old, {**icon, "kept": f"{label!r} is also the label of row {twin}: the icon tells them apart"})
    return out


def icon_label(label, covered, icons, others=()) -> tuple:
    """(label, record) of a crawl's submenu row whose label starts after icons (`icons`, camkit.screen.label_icons'
    boxes): the label as read (`label`: the reader's, else OCR's) with what it read in front of OCR's reading right of
    the icons (`covered`, covered_readings) left out, where that is a word of its own (icon_lead) of ICON_LEAD
    characters an icon at most, and what is left is no other row's label of the page (`others`); else the label as
    read. record: the label as read, OCR's reading right of the icons, what was left out, or "kept" with why."""
    label = str(label or "")
    record = {"icons": [list(b) for b in icons], "read": label, "covered": covered or ""}
    if not covered:
        return label, {**record, "kept": "OCR reads nothing right of the icon where the label starts"}
    if _key(label) == _key(covered):
        return label, record
    got = icon_lead(label, covered)
    if not got:
        why = "the label does not end with OCR's reading right of the icon"
    elif got[2]:
        why = f"{got[1]!r} is glued to the label's first letter"
    elif not _lead_ok(got[1], len(icons)):
        why = f"{got[1]!r} is longer than the icon is read as"
    elif any(_key(str(o or "")) == _key(got[0]) for o in others):
        why = f"{got[0]!r} is also the label of another row of the page: the icon tells them apart"
    else:
        return got[0], {**record, "left_out": got[1]}
    return label, {**record, "kept": why}


def main():
    ap = argparse.ArgumentParser(description="Build the page model from a page scan")
    ap.add_argument("run", nargs="?", default=None, type=paths.run_arg,
                    help="run folder (a run in the camera's runs/<model>_fw<fw>/, or a path; default: kit2_page_scan, "
                         "but --mode takes only a scan named)")
    ap.add_argument("--vlm", action="store_true", help="run VLM page-reading pass before building model")
    ap.add_argument("--reader", default=None, metavar="NAME",
                    help="with --vlm: the configured reader to ask, by its name, instead of the \"second\" one")
    ap.add_argument("--mode", default=None, type=scan_mode,
                    help=f"only record the shooting mode the scan was made in ({', '.join(SCAN_MODES)}) and stop")
    a = ap.parse_args()
    if a.mode and a.run is None:
        sys.exit("page_model: --mode records the mode of the scan named: page_model.py --mode MODE <run>")
    run = Path(a.run or paths.run_arg("kit2_page_scan"))
    private_if_marked(run)              # a --network or --owner run's folder: model.json 0600 in it too
    if a.mode:
        if a.vlm or a.reader:
            sys.exit("page_model: --mode only records the scan's mode; run --vlm on its own")
        if not (run / "scan_rekeyed.json").is_file():
            sys.exit(f"page_model: {run} holds no whole lap (scan_rekeyed.json): no page scan to record a mode for")
        try:
            record_mode(run, a.mode)
        except ValueError as e:
            sys.exit(f"page_model: {e}")
        why = scan_unready(run)
        print(f"{run.name}: recorded as a {a.mode} mode page scan ({run / 'scan_mode.json'})"
              + (f"; no runner takes it by default yet: {why}" if why else ""))
        return
    if a.vlm:
        vlm_read_pages(run, a.reader)
    shots = run / "shots"
    recs = read_json(run / "scan_rekeyed.json")
    pages = collections.OrderedDict()
    for r in recs:
        if r["kind"] == "menu":
            pages.setdefault(r["page"], []).append(r)
    firsts = [rs[0] for rs in pages.values()]
    # a frame the OCR helper cannot read (a torn PNG) is named and left unread, never taken for a page without text:
    # its OCR readings stay out of the vote, which the other readers decide (runner.read_frames)
    try:
        ocr_lines, unread = read_frames([shots / r["frame"] for r in firsts])
    except OcrUnavailable as e:                     # the engine, not a frame: model.json left as it is
        sys.exit(f"{e}; no page model made, {run / 'model.json'} left as it is")
    # a second, independent OCR engine when one is installed (Apple Vision and RapidOCR miss different
    # rows: kit/tools/ocr_compare.py); its readings vote as "ocr2". One that cannot run gives no vote
    eng2, ocr2_lines, unread2 = ocr.second(), {}, {}
    if eng2:
        try:
            ocr2_lines, unread2 = read_frames([shots / r["frame"] for r in firsts], eng2)
        except OcrUnavailable as e:
            print(f"the second OCR engine gives no vote: {e}", flush=True)
            eng2 = None
    for p, why in {**unread, **unread2}.items():
        print(f"not read by OCR, left out of the vote: {p.name}: {why}", flush=True)
    user = read_json(run / "user_labels.json") if (run / "user_labels.json").exists() else {}
    # labels read by eye off the scan's own frame where the readers disagreed (not the user's word;
    # each entry names its frame): a reading like any other
    eye = read_json(run / "checked_labels.json") if (run / "checked_labels.json").exists() else {}
    # the icons drawn before rows' labels, and OCR's readings with them painted over (icon_vote)
    icons = {shots / rs[0]["frame"]: page_icons(shots / rs[0]["frame"], max(r["rows"] or 0 for r in rs))
             for rs in pages.values()}
    covered = covered_readings(icons, MENU_LABEL, {"ocr": None, **({"ocr2": eng2} if eng2 else {})})
    model, confirmed, total, disagreements = [], 0, 0, []
    for key, rs in pages.items():
        first = rs[0]
        path = shots / first["frame"]
        lines = ocr_lines.get(path)               # None: the frame was not read (unread), not a page without text
        lines2 = ocr2_lines.get(path) if eng2 else None
        vlm = cached_vlm(path.read_bytes(), "menu")
        n = max(r["rows"] or 0 for r in rs)
        states = {}
        for r in rs:
            for i, st in enumerate(r["slots"] or []):
                if st != "cursor":
                    states.setdefault(i, st)
        crumb = {"ocr": ocr.text_in(lines, (0, 0, 520, 40))} if lines is not None else {}
        counter = {"ocr": ocr.text_in(lines, (520, 0, 640, 40))} if lines is not None else {}
        for name, a in vlm.items():
            crumb[name], counter[name] = a.get("breadcrumb"), a.get("page")
        # the page's n/N, by OCR; on a page OCR did not read, the vision readers' (agreed, else the first given), so
        # the owner's labels for it (user_labels.json, checked_labels.json) still reach the vote
        page_no = (counter["ocr"] if "ocr" in counter else vote(counter)[0]
                   or next((str(v) for v in counter.values() if v), "") or "").replace(" ", "")
        rows = []
        for i in range(n):
            y0 = MENU_ROW_TOP + MENU_ROW_PITCH * i
            labels, values = {}, {}
            if lines is not None:
                labels["ocr"] = ocr.text_in(lines, (140, y0, 470, y0 + 52)).strip()
                values["ocr"] = ocr.text_in(lines, (470, y0, 640, y0 + 52)).strip()
            if lines2 is not None:
                labels["ocr2"] = ocr.text_in(lines2, (140, y0, 470, y0 + 52)).strip()
                values["ocr2"] = ocr.text_in(lines2, (470, y0, 640, y0 + 52)).strip()
            vgrey = {}
            for name, a in vlm.items():
                vr = (a.get("rows") or [])
                if i < len(vr) and isinstance(vr[i], dict):
                    labels[name], values[name] = vr[i].get("label"), vr[i].get("value")
                    vgrey[name] = vr[i].get("greyed")
            if str(i) in user.get(page_no, {}):
                labels["user"] = user[page_no][str(i)]["label"]
            if str(i) in eye.get(page_no, {}):
                labels["eye"] = eye[page_no][str(i)]["label"]
            value, vby = vote(values)
            rows.append({"slot": i, "value": value, "value_by": vby,
                         "greyed": states.get(i) == "greyed" if i in states else None,
                         "vlm_greyed": vgrey, "readings": {"label": labels, "value": values}})
        voted = page_labels([r["readings"]["label"] for r in rows], icons[path][1], covered[path])
        for row, (label, by, icon) in zip(rows, voted, strict=True):
            labels = row["readings"]["label"]
            row.update({"label": label, "label_by": by, **({"icon": icon} if icon else {}),
                        # never-open by the label, else by any reading (an unread OCR leaves the others to say it)
                        "never_open": safety.never_open(label or "") or next(
                            (w for w in (safety.never_open(x) for x in labels.values() if x) if w), None)})
            total += 1
            confirmed += bool(by)
            if not by:
                disagreements.append((first["frame"], row["slot"], labels))
        vlm_rows = {name: len(a.get("rows") or []) for name, a in vlm.items()}
        model.append({"page": vote(counter)[0] or counter.get("ocr"), "breadcrumb": vote(crumb)[0] or crumb.get("ocr"),
                      "key": key, "frame": first["frame"], "down_from_start": first["n"], "rows": rows,
                      "vlm_row_counts": vlm_rows, "readers": sorted(vlm),
                      **({"ocr_unread": unread[path]} if path in unread else {}),
                      **({"ocr2_unread": unread2[path]} if path in unread2 else {})})
    write_json(run / "model.json", model, indent=1)
    record_model(run, recs)                 # which lap the model is of (runner.scan_unready), where the scan says it
    readers = collections.Counter(n for p in model for n in p["readers"])
    mismatched = [(p["page"], len(p["rows"]), p["vlm_row_counts"]) for p in model
                  if any(c != len(p["rows"]) for c in p["vlm_row_counts"].values())]
    print(f"{len(model)} pages, {total} rows; labels confirmed by two sources: {confirmed}/{total}")
    print(f"VLM readings available: {dict(readers)}")
    print(f"pages where a VLM counts a different number of rows: {len(mismatched)} {mismatched[:6]}")
    for frame, i, labels in disagreements[:25]:
        print(f"  ? {frame} row {i}: " + " | ".join(f"{k}={str(v)[:28]!r}" for k, v in labels.items()))


if __name__ == "__main__":
    main()
