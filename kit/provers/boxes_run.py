"""Prove a two-box screen: two values side by side, Left/Right between the boxes, Up/Down through a
box's values, OK leaves (S&Q and Time-lapse Frame Rate Settings, Movie mode, 2026-10-30).

    .venv/bin/python -u kit/provers/boxes_run.py --scan kit2_page_scan_movie --context "Movie mode" \\
        --row "S&Q Settings > Frame Rate Settings" --boxes "Rec Frame Rate,Frame Rate"
    .venv/bin/python -u kit/provers/boxes_run.py --scan kit2_page_scan_movie --context "Movie mode" \\
        --row ISO --boxes "ISO AUTO Minimum,ISO AUTO Maximum" --layout iso --rights 2   # ISO AUTO in use

The pixel reader does not know these screens, so this reads them by OCR: the breadcrumb must end in
the row's label, and the footer must draw its OK key (camkit.screen.footer_keys, by pixels: OCR drops it
as often as not) before anything but an arrow is pressed. The box under
the cursor is the orange one; each box's value is the text inside it (read_box: the arrows a lit box draws round its
value, which OCR reads glued to it over HDMI, go only where a value of the box is left, on a fresh frame, or in the
look where the second reader agrees). The box names are given on the command line, as read off the camera's frame (OCR
reads their icons as letters: "sad Rec Frame Rate").
First a look per box: Up until the value stops changing or comes round, then Down the same way (its
values in Down order), MENU. Then, as kit/prove_run.py does, per box: each value against the start,
the one held last; every choice is the row, Right, Left/Right to the box, Up/Down until the value is
read, OK, a settings download. Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl (kind "list", the box name
last in the path); the start file goes back on at the end and is checked. Each proof line keeps the vision model's
reading of the chosen value ("vlm") beside OCR's ("shown"), as the second reading: the lit box's value, asked as
optboxes_run asks it (box_reading). The value a box opened on is proved
only from another start: --first BOX=VALUE. A choice that also moved the other box (ISO AUTO keeps Minimum <= Maximum,
and a Maximum chosen rewrites a factory Minimum) says so on its line ("moved_other"), and the other box is put back
through the menu and checked before the next value; one that cannot be put back ends the box's proofs (prove).

On the Frame Rate Settings screens the value a box shows is already the setting: stepped to 24p and left with MENU,
no OK, the row read "Recording Frame Rate: 24p" (kit2_pass2 240079 -> 240080, XAVC HS 4K, 2026-11-17) and the download
after held it (240083). So each proof is what the record holds once the box was stepped to its value, and the OK only
leaves. The screen reads as no known kind, whose Enter the camera's shape check refuses (2026-11-14; the proofs before
it pressed it unguarded), so that OK goes by the screen's own consent (camkit.live.TwoBoxes: screen_consent), judged
on its shape; a screen it cannot judge so gets no OK and stops the run. The screen after OK is read by
proving.commit.after_ok: a value whose OK the camera refuses is written "applied": false with its notice.
A box that draws a dash (dashed: XAVC HS 8K's S&Q boxes, 240050, where Up raised "not available as follows: File
Format") is not offered in this state: the look presses nothing on it, and the run writes it to its failures.jsonl as
prove_run writes a row the camera would not open ("blocked": NOT_OFFERED, keyed like the box's proofs, tagged with
--context), and goes on.
Exit status: 0 for a run that ends, a STOP, and boxes not offered; once the start file is back and checked, a run a
refusal stopped exits EXIT_REFUSED and one anything else stopped EXIT_INCOMPLETE, as kit/crawl_run.py does
(kit/exit_status.py; kit/tools/chain.py stops there); a restore that does not check out, EXIT_UNRESTORED.
"""
import argparse
import functools
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, live, match, ocr, safety, screen, vlm  # noqa: E402
import numpy as np  # noqa: E402  (after camkit, which installs the plain words: test_start)
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from camkit.live import TwoBoxes  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, enter_any, option_key, to_shooting  # noqa: E402
from proving.base import wait_lock  # noqa: E402
from proving.commit import after_ok  # noqa: E402
from proving.screens import ask_second, later, settled  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_REFUSED, add_scan_argument, changes_of, close_screen, load_scan,  # noqa: E402
                    menu_from_shooting, proofs_file, prover_session, scan_position)

# each screen's two boxes, measured off the frames: S&Q / Time-lapse Frame Rate Settings, and ISO AUTO's
# Minimum / Maximum (ISO > ISO AUTO > Right, Movie mode, 2026-11-01)
LAYOUTS = {"framerate": [(100, 178, 339, 233), (356, 178, 595, 233)],
           "iso": [(130, 350, 373, 405), (381, 350, 625, 405)]}
BOXES = LAYOUTS["framerate"]
RIGHTS = 1                       # Rights from the row to the boxes (ISO: one into the list, one into the boxes)
CRUMB = (0, 0, 640, 40)
FOOTER = (0, 425, 640, 480)
LOOKALIKE = str.maketrans("рРоОкКсС", "pPoOkKcC")          # OCR's Cyrillic: "30р", "ОК"
# a dash's ink in a box, at most (px, tall and wide): kit2_pass2 240050's is 3 x 7 in either box, a value's glyphs 34 tall
DASH = (8, 30)
NOT_OFFERED = "not offered in this state: its box draws a dash"
PROOF_RUN = "kit2_pass2"         # the run its proofs go to (kit/provers/mode_switch.py's box_proofs reads them there)


class NotOffered(Exception):
    """A box that draws a dash (dashed), seen on `frame`: not offered in this state."""
    def __init__(self, frame: str):
        super().__init__(f"the box draws a dash ({frame})")
        self.frame = frame


def lines(cam):
    f = cam.frame
    return ocr.read([f.path])[f.path]


def value(cam, b: int) -> str:
    return re.sub(r"\s+", "", ocr.text_in(lines(cam), BOXES[b]).translate(LOOKALIKE))


# the arrows a lit box draws above and below its value (its Up and Down), as OCR reads them glued to the value at an end
# over HDMI: "^ISO500", "^ISO200" (kit2_pass2 248934, 248975, 248980: Movie, ISO AUTO Minimum, 2026-11-18, on some frames
# only, never on the dark box); the signs they read as, and the letters they look like
ARROW_SIGNS = "^˄˅∧∨⌃⌄↑↓▲▼△▽"   # ^ ˄ ˅ ∧ ∨ ⌃ ⌄ ↑ ↓ ▲ ▼ △ ▽
ARROW_LETTERS = "vVAΛ"                                                              # and a Greek capital lambda
FRESH = 3              # fresh frames a box is read again on while its reading keeps an arrow's sign at an end


def box_value(raw: str, vals) -> str:
    """A box's reading as one of its values `vals`: as read where it is one; else with an arrow read glued at its start,
    its end or both (ARROW_SIGNS, ARROW_LETTERS) left off, where that leaves exactly one of them; else as read. Never a
    guess: what is left must be a value the box's own look read."""
    if raw in vals:
        return raw
    marks = ARROW_SIGNS + ARROW_LETTERS
    cuts = [raw[a:len(raw) - z] for a in (0, 1) for z in (0, 1) if (a or z)
            and (not a or raw[:1] in marks) and (not z or raw[-1:] in marks) and len(raw) > a + z]
    hits = list(dict.fromkeys(t for t in cuts if t in vals))
    return hits[0] if len(hits) == 1 else raw


def arrow_signed(t: str) -> bool:
    """Whether a reading keeps an arrow's sign at an end: no value of a box starts or ends so."""
    return bool(t) and (t[0] in ARROW_SIGNS or t[-1] in ARROW_SIGNS)


def read_box(cam, b: int, vals=None, row: str = "") -> str:
    """Box b's value: OCR's reading (value), as one of the box's values `vals` where they are known (box_value: the
    proving pass), and while it keeps an arrow's sign at an end, read again on up to FRESH fresh frames, no press: the
    first reading without one. Still signed after them: in the look, where the values are not known yet, the signs left
    off (never a letter) and taken only where the second reader agrees (by_both); in the proving pass, Failed, naming
    the reading. No value is guessed."""
    for k in range(FRESH + 1):
        raw = value(cam, b)
        got = box_value(raw, vals) if vals else raw
        if not arrow_signed(got):
            return got
        if k < FRESH and hasattr(cam, "refresh"):
            cam.refresh("reread")
        else:
            break
    if vals:
        raise Failed(f"{row} box {b}: read {raw!r} on {k + 1} frames, an arrow's sign at its end: not one value")
    return by_both(cam, b, raw, row, k + 1)


def box_reading(cam, b: int) -> str:
    """The second reader's reading of the value in lit box b on the frame on show: the question kit/provers/
    optboxes_run.py asks of the same widget (PROMPTS["box"]), with the box's place handed over (camkit.vlm.box_at: the
    left or the right of the two), never the "option" question, which named the dialog's option ("ISO AUTO") for ISO
    AUTO Minimum's "ISO500" (2026-11-19, on the camera). "" where the reader fails, says no box is orange, or answers
    anything but one non-empty "value"."""
    try:
        v = ask_second(cam.frame.path.read_bytes(), vlm.box_at("left" if b == 0 else "right"), timeout=25)
    except Exception:
        return ""
    value = v.get("value") if isinstance(v, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else ""


def by_both(cam, b: int, raw: str, row: str, frames: int) -> str:
    """A look's reading that keeps an arrow's sign at an end on every fresh frame (kit2_pass2 249674-249677: "^ISO500"
    each time, 2026-11-18): the signs left off (ARROW_SIGNS alone, never a letter), and the second reader asked in line
    what the lit box shows on that frame (box_reading, as each proof's second reading is); the cleaned value taken only
    where the two agree as a proof's two readings are judged (camkit.match.same), both readings logged in the run's
    events ("box_read_by_both"). Two that disagree, or no answer: Failed, naming both, as before."""
    cleaned = raw.strip(ARROW_SIGNS)
    second = box_reading(cam, b) or ""
    agree = bool(cleaned and second and match.same(cleaned, second))
    log = getattr(getattr(cam, "run", None), "log", None)
    if log:
        log("box_read_by_both", row=row, box=b, frame=getattr(cam.frame.path, "name", ""), ocr=raw, cleaned=cleaned,
            second=second, agree=agree)
    if agree:
        return cleaned
    said = repr(second) if second else "no answer"
    raise Failed(f"{row} box {b}: read {raw!r} on {frames} frames, an arrow's sign at its end, and the second reader "
                 f"{said} for {cleaned!r}: not one value")


def dashed(cam, b: int) -> bool:
    """Whether box b draws a dash: OCR reads no letter or digit in it (the dash read as nothing, or as "-"), and its ink,
    the pixels off the box's own colour (orange when lit, dark when not; its border left out), is there and no more than
    a short flat stroke (DASH). A box drawn empty (a frame caught mid-draw) is none, nor one whose glyphs OCR missed."""
    if re.search(r"[^\W_]", value(cam, b)):
        return False
    x0, y0, x1, y1 = BOXES[b]
    box = np.asarray(cam.frame.image)[y0 + 5:y1 - 5, x0 + 5:x1 - 5].astype(int)
    if box.size == 0:
        return False
    ink = np.abs(box - np.median(box.reshape(-1, box.shape[-1]), axis=0)).sum(axis=2) > 120
    ys, xs = np.nonzero(ink)
    return bool(len(ys) and ys.max() - ys.min() < DASH[0] and xs.max() - xs.min() < DASH[1])


def focus(cam) -> int | None:
    o = screen._orange(cam.frame.image)
    lit = [float(o[y0:y1, x0:x1].mean()) for x0, y0, x1, y1 in BOXES]
    return max(range(2), key=lambda i: lit[i]) if max(lit) > 0.3 else None


def row_refused(cam, path: list) -> None:
    """Failed where the lit row (the last of `path`) is drawn grey (proving.greyrow.row_grey, as mode_switch's set_row
    judges a list row): no Right on it, nothing pressed. Where its drawing cannot be told the row opens as before."""
    from proving.greyrow import row_grey
    if not callable(getattr(cam, "read", None)):
        return                  # a camera that reads no screen tells no drawing: the row opens as before
    grey, measure = row_grey(cam)
    if grey:
        raise Failed(f"{' > '.join(path)}: the row is drawn grey (its label reads {measure:.0f}, "
                     f"{getattr(cam.frame.path, 'name', '')}), so it was not opened: kit/provers/greyrow_run.py asks the "
                     "camera why; nothing was pressed on it")


def open_row(cam, cycle, model, path):
    """From the shooting screen: MENU, the row by the scan, Right (RIGHTS times); the boxes opened where the breadcrumb
    holds the row's label, a box is lit and the footer draws its OK key (camkit.screen.footer_keys, by pixels, as the
    screen's consent judges it: OCR read "● OK" on one frame and missed it on the next, kit2_pass2 240268 and 240575,
    2026-11-18, the footer the same pixel for pixel); else Failed, nothing but Right pressed. Each row on the way is
    judged grey before the Right that would open it (row_refused: the top row before the walk into it, the two-box row
    before its own), as set_row judges a list row: mode_switch --set takes this path on the S&Q menu too, whose rows
    in Time-lapse no look has drawn yet."""
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"could not reach {path[0]!r} by the scan")
    row_refused(cam, path[:1])
    enter_any(cam, path, 0)
    if len(path) > 1:
        row_refused(cam, path)
    for _ in range(RIGHTS):
        cam.press("right")
    crumb = ocr.text_in(lines(cam), CRUMB)
    foot = ocr.text_in(lines(cam), FOOTER).translate(LOOKALIKE)
    if option_key(path[-1]) not in option_key(crumb) or focus(cam) is None:
        raise Failed(f"Right on {path[-1]!r} did not open its boxes (breadcrumb {crumb!r}, footer {foot!r})")
    if "ok_key" not in screen.footer_keys(cam.frame.image):
        raise Failed(f"Right on {path[-1]!r} did not open its boxes: no OK key drawn in the footer ({cam.frame.path.name}; "
                     f"OCR read the footer {foot!r})")


def to_box(cam, b: int):
    for _ in range(3):
        if focus(cam) == b:
            return
        cam.press("right" if focus(cam) < b else "left")
    raise Failed(f"box {b} never took the cursor")


def look(cam, link, cycle, model, path, b: int, seen: dict | None = None) -> tuple[list, str]:
    """(the box's values in Down order, the value held). A box that draws a dash once the screen is open (dashed) is
    left with MENU, nothing pressed on it, and raises NotOffered. On a screen whose box is its setting (the module's
    words), the look leaves the box where its walk ended: the held value on a box that comes round, as the Frame Rate
    boxes do; each proof is compared with its base all the same. seen: each box's value as the screen opened, filled
    where not there yet (prove: what a box that moved with the other is put back on)."""
    open_row(cam, cycle, model, path)
    return look_open(cam, link, path, b, seen)


def look_open(cam, link, path, b: int, seen: dict | None = None) -> tuple[list, str]:
    """look's walk on the row's screen already open (open_row): the dash check, the walk, MENU."""
    if dashed(cam, b):
        frame = cam.frame.path.name
        close_screen(cam, link)
        raise NotOffered(frame)
    to_box(cam, b)
    row = path[-1]
    held = read_box(cam, b, row=row)
    if seen is not None:
        seen.setdefault(b, held)
        if 1 - b not in seen:
            seen[1 - b] = read_box(cam, 1 - b, row=row)      # the other box, as the screen opened
    for _ in range(40):                       # Up to one end (or once round)
        before = read_box(cam, b, row=row)
        cam.press("up", seen_enough=True)     # a step whose change was seen needs no look again (LiveCamera.look_late)
        if read_box(cam, b, row=row) in (before, held):
            break
    vals = [read_box(cam, b, row=row)]
    for _ in range(40):
        cam.press("down", seen_enough=True)
        v = read_box(cam, b, row=row)
        if v == vals[-1] or v == vals[0]:
            break
        vals.append(v)
    close_screen(cam, link)
    if held not in vals or len(set(vals)) != len(vals) or not all(vals):
        raise Failed(f"{path[-1]} box {b}: the look read {vals} with {held!r} held")
    return vals, held


def screen_consent(path, names) -> TwoBoxes:
    """The consent for the one OK that leaves the row's own two-box screen (camkit.live.TwoBoxes), named for the row,
    its two boxes and where they stand (BOXES)."""
    return TwoBoxes(f"{path[-1]}'s own two-box screen: OK leaves it on the values its boxes show (boxes_run)", path[-1],
                    tuple(names), tuple(tuple(b) for b in BOXES))


def choose(cam, link, hdmi, cycle, model, path, b, vals, target, names) -> dict:
    """The box stepped to vals[target] (the setting from then on), its OK under the screen's consent (step_ok), a
    settings download."""
    got = step_ok(cam, cycle, model, path, b, vals, target, names)
    to_shooting(link, hdmi, "the download after OK")
    dat = link.download(f"{path[-1]}-{b}-{target}")     # camlink waits up to 5 s for the camera to allow it
    wait_lock(time.monotonic(), hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
    return {**got, "dat": dat}


def step_ok(cam, cycle, model, path, b, vals, target, names, quiet: bool = False) -> dict:
    """The row opened, box b stepped to vals[target] (the setting from then on) and left with OK under the screen's
    consent (screen_consent); {"chosen_frame", "row_frame", "vlm", "outcome"}: the frame it was chosen on, the frame after
    OK, the second reader's reading of it, and what the camera did with the OK (proving.commit.after_ok: a refusal or a
    notice closed with MENU, never OK; no information screen taken, the two-box screen reading as no known kind). quiet:
    a notice's words not said (mode_switch's setting, set_value)."""
    open_row(cam, cycle, model, path)
    to_box(cam, b)
    for _ in range(len(vals) + 1):
        now = read_box(cam, b, vals, path[-1])
        if now == vals[target]:
            break
        if now not in vals:
            raise Failed(f"{path[-1]} box {b}: read {now!r}, not one of its values")
        cam.press("down" if vals.index(now) < target else "up", seen_enough=True)
    if read_box(cam, b, vals, path[-1]) != vals[target] or focus(cam) != b:
        raise Failed(f"{path[-1]} box {b}: {vals[target]!r} never came up")
    full = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"{path[-1]}: the screen reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, seen_vlm = cam.frame.path.name, later(functools.partial(box_reading, b=b), cam)     # kept with the proof
    cam.answer_once = screen_consent(path, names)        # the OK that leaves, judged on the screen's shape (TwoBoxes)
    cam.press("enter")
    row_frame = cam.frame.path.name
    got = after_ok(cam, path[-1], label=vals[target], info=False, **({"say": None} if quiet else {}))
    return {"chosen_frame": chosen, "row_frame": row_frame, "vlm": seen_vlm, "outcome": got}


def drawn_names(cam, names) -> list:
    """The row's two box names `names` (any order) in the order its open screen draws them, left first
    (camkit.live.names_drawn: each box's name read where the screen's consent reads it); Failed where they are not
    those two, before anything but Right was pressed."""
    got = live.names_drawn(lines(cam), BOXES, list(names))
    if got is None:
        raise Failed(f"the names drawn above its boxes are not {' and '.join(names)} ({cam.frame.path.name}): not that "
                     "row's two-box screen")
    return got


def set_value(cam, link, cycle, model, path, names, box: str, value: str) -> dict:
    """One box of the row's two-box screen put on `value` and left there (kit/provers/mode_switch.py --set "ROW > BOX=
    VALUE"): the row opened (open_row: its breadcrumb, a lit box, the OK key drawn), its boxes' names read where they
    are drawn (drawn_names, `names` in any order), the box looked at as a proof's look is (look_open: NotOffered where
    it draws a dash), then opened again, stepped to the value and left with OK under the screen's consent (step_ok).
    Failed where the value is not one of the box's values as the camera walks them, or the box holds it already
    (nothing to set, no OK). Returns {"values": the box's values in Down order, "held": the one it held, "box": its
    index, "names": the names left first, "chosen_frame", ...}."""
    open_row(cam, cycle, model, path)
    names = drawn_names(cam, names)
    b = names.index(box)
    vals, held = look_open(cam, link, path, b)
    want = [i for i, v in enumerate(vals) if option_key(v) == option_key(value)]
    if len(want) != 1:
        raise Failed(f"{path[-1]} > {box}: {value!r} is not one of its values ({', '.join(vals)}): nothing chosen")
    if vals[want[0]] == held:
        raise Failed(f"{path[-1]} > {box} already holds {held!r}: nothing to set, no OK")
    got = step_ok(cam, cycle, model, path, b, vals, want[0], names, quiet=True)
    if not got["outcome"].applied:          # the notice's words can name another setting's value: its frame alone
        raise Failed(f"{path[-1]} > {box} = {value}: the camera refused it after OK (its notice on "
                     f"{got['outcome'].notice['frame']})")
    return {**got, "values": vals, "held": held, "box": b, "names": names}


def arguments(argv=None):
    """The command line: (its arguments, the row's path, the two box names, --first as (box, value) or None). Stops
    with what is wrong: not two boxes, a never-open row, --only or --first naming no box, --first not BOX=VALUE."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", required=True, help="the row's path, ' > ' between submenus")
    ap.add_argument("--boxes", required=True, help="the two boxes' names, left first, comma-separated")
    ap.add_argument("--context", default=None, help="the state these proofs are made in (e.g. Movie mode)")
    add_scan_argument(ap)
    ap.add_argument("--layout", choices=sorted(LAYOUTS), default="framerate", help="where the two boxes are")
    ap.add_argument("--rights", type=int, default=1, help="Rights from the row to the boxes (ISO AUTO: 2)")
    ap.add_argument("--only", default=None, help="prove this one box (its name from --boxes)")
    ap.add_argument("--first", default=None, metavar="BOX=VALUE",
                    help="choose this value in that box first and prove from there: a box's last proof is the value "
                         "it held, which changes nothing, so the held value is proved only from another start. The "
                         "start file still goes back on at the end")
    a = ap.parse_args(argv)
    path, names = a.row.split(" > "), [x.strip() for x in a.boxes.split(",")]
    if len(names) != 2 or any(safety.never_open(p) for p in path):
        sys.exit("two box names, and a row that is not never-open")
    if a.only and a.only not in names:
        sys.exit(f"--only {a.only!r}: not one of {names}")
    first = tuple(x.strip() for x in a.first.split("=", 1)) if a.first else None
    if first and (len(first) != 2 or first[0] not in names or not first[1]):
        sys.exit(f"--first {a.first!r}: BOX=VALUE, the box one of {names}")
    return a, path, names, first


def not_offered(fails, path, name: str, frame: str) -> None:
    """A box not offered in this state, said and written to the run's failures (`fails`) as prove_run writes a row the
    camera would not open: "blocked" (camkit.coverage: greyed in state; pass2_report: a row the camera would not open,
    until a later proof of it), its path the box's proofs' (the row's, then the box's name)."""
    where = " > ".join([*path, name])
    print(f"{where}: {NOT_OFFERED} ({frame})", flush=True)
    if fails is not None:
        fails.write(json.dumps({"path": [*path, name], "why": f"{where}: {NOT_OFFERED}", "blocked": NOT_OFFERED,
                                "frame": frame, "boxes": True}) + "\n")
        fails.flush()


def box_history(out, path, names) -> list:
    """(box, changes) of each applied line of the row's two boxes already in the proofs file `out` writes to (a
    proofs_file: its file's name), made in the same state (its context), without the changes it names as the other
    box's (moved_other): what proving.fields.Limits learns from first."""
    try:
        from camkit import jsonl
        lines = jsonl.read(Path(out.f.name))
    except Exception:            # noqa: BLE001 - no file to read: nothing learned before
        return []
    got = []
    for r in lines:
        p = r.get("path") or []
        if p[:-1] == list(path) and p[-1:] and p[-1] in names and r.get("boxes") is True and r.get("applied") is True \
                and r.get("context") == getattr(out, "context", None) and r.get("changes"):
            other = {c["key"] for c in (r.get("moved_other") or {}).get("changes") or []}
            got.append((names.index(p[-1]), [c for c in r["changes"] if c["key"] not in other]))
    return got


def put_back(cam, link, hdmi, cycle, model, path, names, b, value, j, theirs, base, limits, start) -> Path:
    """Box j, which the choice of `value` in box b moved, back on the value it showed as the row opened (start), chosen
    through the menu as a proof chooses (look, choose); Failed in plain words where its list does not offer that value,
    or where a record of it (`theirs`, with its own as limits knows them) still differs from the base after it. Returns
    the download after it."""
    moved = f"choosing {value!r} in {names[b]} also moved {names[j]}"
    vals, _ = look(cam, link, cycle, model, path, j)
    want = [i for i, v in enumerate(vals) if start.get(j) and option_key(v) == option_key(start[j])]
    if len(want) != 1:
        raise Failed(f"{path[-1]}: {moved}, and the value {names[j]} showed as the row opened ({start.get(j)!r}) is not "
                     f"one of its list's ({', '.join(vals)}), so it cannot be put back by a menu choice (a factory value "
                     "the menu cannot choose again?): this box's proofs end here rather than carry that leftover, and "
                     f"the start file goes back on; prove {names[b]} from a start where {names[j]} holds a value its "
                     "list offers")
    dat = choose(cam, link, hdmi, cycle, model, path, j, vals, want[0], names)["dat"]
    left = sorted({c.key for c in camset.diff(camset.read(base), camset.read(dat))} & (set(theirs) | limits.own(j)))
    if left:
        raise Failed(f"{path[-1]}: {moved}, and choosing {vals[want[0]]!r} in {names[j]} again through the menu does not "
                     f"bring back what the start held in {', '.join(left)} ({dat.name}): a value the menu cannot choose "
                     "again (a factory value?). This box's proofs end here rather than carry that leftover, and the "
                     f"start file goes back on; prove {names[b]} from a start where {names[j]} holds a value its list "
                     "offers")
    print(f"  {names[j]} put back on {vals[want[0]]!r} through the menu ({dat.name})", flush=True)
    return dat


def prove(cam, link, hdmi, cycle, model, path, names, only, first, start, out, fails=None) -> Path:
    """Each box's values proved, as the module says; with first (box, value), that value chosen in that box before
    them. Each proof is compared with its base: the start file, or the download made after first's choice, so the
    held value (the last proof of each box) is a return to the base and must change nothing: a last proof that changed
    something is not written, and the run stops. A box not offered in this state (NotOffered) is written to `fails`
    (not_offered) and the next box tried; first's box not offered, nothing else is. Returns the base; the caller puts
    the start file back, whatever first chose.
    A choice in one box that changed a record of the other (ISO AUTO: a Maximum chosen rewrites a factory Minimum, and a
    limit chosen past the other moves it; proving.fields.Limits tells the boxes' records apart, from the proofs file's
    earlier lines and this run's) says so on its line, "moved_other": {"box": the other box's name, "changes": its
    records' changes}, which the report leaves out of the choice's own records; the other box is then put back on the
    value it showed as the row opened, through the menu, and checked (put_back), before the next value is proved. A
    value the menu cannot bring back ends this box's proofs there, said in plain words, before another line is written."""
    from proving.fields import Limits, copies, readouts
    base = start
    if first:
        fb = names.index(first[0])
        try:
            vals, held = look(cam, link, cycle, model, path, fb)
        except NotOffered as e:
            not_offered(fails, path, names[fb], e.frame)
            return base
        want = [i for i, v in enumerate(vals) if option_key(v) == option_key(first[1])]
        if len(want) != 1:
            raise Failed(f"--first: {first[1]!r} is not one value of {names[fb]}: {vals}")
        base = choose(cam, link, hdmi, cycle, model, path, fb, vals, want[0], names)["dat"]
        print(f"first {names[fb]} = {vals[want[0]]} (it held {held!r}): proofs start from {base.name}", flush=True)
    limits, opened = Limits(2, box_history(out, path, names), readouts(), copies()), {}
    for b in [b for b in range(2) if only in (None, names[b])]:
        try:
            vals, held = look(cam, link, cycle, model, path, b, opened)
        except NotOffered as e:
            not_offered(fails, path, names[b], e.frame)
            continue
        print(f"{names[b]}: {vals}, held {held!r}", flush=True)
        h = vals.index(held)
        for i in [i for i in range(len(vals)) if i != h] + [h]:
            got = choose(cam, link, hdmi, cycle, model, path, b, vals, i, names)
            ch = camset.diff(camset.read(base), camset.read(got["dat"]))
            print(f"  {vals[i]}: {len(ch)} records {[(c.key, c.before, c.after) for c in ch][:4]}",
                  flush=True)
            if i == h and ch:
                raise Failed(f"{names[b]}: back on {held!r}, {len(ch)} records still differ from the start "
                             f"({', '.join(c.key for c in ch[:6])}): that last proof is not written, and the start file "
                             "goes back on")
            keys = {c.key for c in ch}
            other = limits.other(b, keys)
            done = got["outcome"]
            r = {"path": path + [names[b]], "kind": "list", "index": i, "label": vals[i],
                 "shown": vals[i], "vlm": settled(got["vlm"]), "chosen_frame": got["chosen_frame"],
                 "row_frame": got["row_frame"],
                 "dat": got["dat"].name, "base": base.name, **({"notice": done.notice} if done.notice else {}),
                 "applied": done.applied, "boxes": True, "changes": changes_of(ch)}
            if other:
                (j, theirs), = other.items()
                r["moved_other"] = {"box": names[j], "changes": [c for c in r["changes"] if c["key"] in theirs]}
                print(f"  {names[j]} moved with it: {', '.join(sorted(theirs))}", flush=True)
            out.write(json.dumps(r) + "\n")
            out.flush()
            theirs_all = set().union(*other.values())
            if done.applied:                    # what a box writes is learnt from applied lines alone (box_history)
                limits.learn(b, [c for c in r["changes"] if c["key"] not in theirs_all])
            if other:
                put_back(cam, link, hdmi, cycle, model, path, names, b, vals[i], j, theirs, base, limits, opened)
    return base


def failures_file(run, context: str | None):
    """The run's failures.jsonl opened for appending, each line tagged with `context` as its proofs are."""
    from proving.base import Tagged
    return Tagged(open(run.dir / "failures.jsonl", "a", encoding="utf-8", newline="\n"), context)


def stop_status(e) -> int:
    """The exit status of a run whose body ended on `e` (None: it ended), its start file back and checked: 0 for none and
    for a STOP; EXIT_REFUSED for a refusal (camkit.safety.Refused: a press the guards would not send), EXIT_INCOMPLETE
    for anything else (a Failed step, a lost feed), as kit/crawl_run.py exits."""
    if e is None or isinstance(e, StopRequested):
        return 0
    return EXIT_REFUSED if isinstance(e, safety.Refused) else EXIT_INCOMPLETE


def main(argv=None):
    a, path, names, first = arguments(argv)
    global BOXES, RIGHTS
    BOXES, RIGHTS = LAYOUTS[a.layout], a.rights
    cycle, model = load_scan(a.scan)
    run = Run(PROOF_RUN)
    hdmi = eyes_from_config(run)
    stopped = []
    # the session ends restoring the start file, not the base --first made; it says a body's exception and raises it no
    # further (runner.prover_session), so the exception is kept here and the exit status told from it once the restore
    # has checked out (a restore that does not exits EXIT_UNRESTORED from the session itself)
    with proofs_file(run, a.context) as out, failures_file(run, a.context) as fails, prover_session(run, hdmi) as s:
        try:
            prove(s.cam, s.link, hdmi, cycle, model, path, names, a.only, first, s.start, out, fails)
        except Exception as e:
            stopped.append(e)
            raise
    code = stop_status(stopped[0] if stopped else None)
    if code:
        print(f"the run was stopped by {'a refusal' if code == EXIT_REFUSED else 'a failure'}: its start file is back and "
              f"checked, but the proofs after it were not made (exit status {code})", flush=True)
        sys.exit(code)


if __name__ == "__main__":
    main()
