"""Prove an option of a list row that draws a row of boxes of its own: the a1 II's Zebra Level > Custom 1 and Custom 2
(2026-11-18).

    .venv/bin/python -u kit/provers/optboxes_run.py --scan SCAN --row "Zebra Level" --option "Custom 1" --probe
    .venv/bin/python -u kit/provers/optboxes_run.py --scan SCAN --row "Zebra Level" --option "Custom 1" \\
        --context "Stills mode, Zebra Level Custom 1" [--only Standard]

The row opens a side list; with the option lit (the title line names it) the camera draws a row of boxes at the bottom.
Right enters them, the first box lit and its name written above the row ("Type"); Right again lights the next
("Standard", then "Range"), Left goes back; Up and Down step the lit box. Right on the last box leaves the boxes for
the list, whose cursor Up and Down then move to another option, and Left from the list lights the last box (kit2_pass2
241721-241726, 241750-241754). The first box (Type) redraws the row: on Std+Range it is Type, Standard and Range, on
Lower Limit Type and Lower Limit. A stepped value is applied live; MENU cancels the screen and takes it back, OK keeps
it. Boxes are named by the word the camera writes above the lit one, counted by their drawn outlines (drawn).

Check 1 (in_box) follows every press inside the boxes and comes before every reading there: the title line names the
option, exactly one box of the row is filled orange (by pixels) and it is the box meant, the word above the row is its
name; anything else stops the run at once, before another key goes. Moves between boxes are a known number of Rights or
Lefts (go), never a Right on the last box nor a Left on the first; the second reader is asked only on a frame check 1
has just passed (ask_box).
This prover sits beside boxes_run, not in it: boxes_run's screen is two fixed boxes reached by Right from the row, while
here an option of a list draws the boxes, their count and names change with the first box, and the list is stepped to
the option first; the exit statuses, the proof run and the shape of a proof line are boxes_run's.

--probe, read only: the option lit, the first box walked once round (its options), each of its options' row of boxes
counted from what is drawn and named (Right to each box the row draws, the word above it), each box under each option
walked (walk: Down until a further press changes nothing, an end, or a value seen before comes back, a list that comes
round, recorded with no ends; then Up to the top end; MAX_WALK presses at most each way: what is read is recorded, a box
of numbers read in its values' shape, OCR's glyph for the ± and the digits' look-alikes undone, and the second reader
asked about the lit box itself (proving.screens.box_answer, PROMPTS["box"]) where OCR's reading is empty or unclean, and
always about the value held, each end and a value come round; Standard and Range held to their constant step as well),
then MENU, which cancels it all, and the session's restore check. Nothing is chosen. One line goes to
kit2_pass2/option_boxes.jsonl (PROBES) once every box of every Type is read, none from a probe that stopped: the
option's rows of boxes ("types") and each box's values, the one it held, whether it comes round, and the first box's
option it is drawn under. The proof run refuses a probe line that lacks a box of a Type's row (probe_refused).

The proof run plans from the option's latest probe: a base first, the option chosen with its boxes as they stand (the
first box on the value it holds, OK), so the row's own record (Zebra Level moving to Custom N) moves there, and every
box proof is compared with that base, its changes the box's records alone. Each box then: both ends, the held value's
neighbours, one in the middle (for a list that comes round, the neighbours and the value opposite), and last the held
value, which must change nothing (values_for); a box drawn under
another of the first box's options (Lower Limit) from a base with the first box on that option. Each value is stepped
to and kept with OK, judged first on the screen's own shape (camkit.live.option_boxes_refused: the title names the
option, the word above the lit box is the box's, it is lit on the value, the footer draws the OK key, nothing asks);
the camera's own Enter guard judges it again (a dialog; read as no known kind, by the OptionBoxes consent). A download
and its diff make a proof line in boxes_run's shape (path row > option > box, kind "list", its index among the probe's
values, "sampled"), into kit2_pass2/proofs.jsonl with --context; a value whose records did not move is kept with no
changes and said "not proved", never credited. The screen after OK is read by proving.commit.after_ok: a value whose OK
the camera refuses is written "applied": false with its notice, and a base it refuses stops the run. The session puts
the start file back at the end.

HAZARD (the a1 II, 2026-11-18): the one screen "Standard lit at 30, Range ±5" stalls the camera's remote link while
the kit reads the screen through it (OSD eyes): no step goes onto it there (step_to refuses in plain words), the probe
walks Range before Standard (so Range has left ±5), the default values never hold Standard 30 while Range is ±5, and
on OSD eyes Standard is proved from a base with Range one step off ±5. A link that stalls all the same is waited for
by the run's cleanup (camkit.live.close), then MENU and the restore.

Exit status, as boxes_run's: 0 for a run that ends and a STOP; once the start file is back and checked, EXIT_REFUSED
for a refusal and EXIT_INCOMPLETE for anything else; EXIT_UNRESTORED when the restore does not check out (then
kit/tools/upload_check.py puts the run's start file back, as for every prover: these boxes are plain records of the
settings file, which its upload restores).
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, live, match, ocr, safety  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from boxes_run import EXIT_REFUSED, LOOKALIKE, PROOF_RUN, stop_status  # noqa: E402
from boxes_run import lines as boxes_lines  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, option_key, to_shooting  # noqa: E402
from proving.base import wait_lock  # noqa: E402
from proving.commit import after_ok  # noqa: E402
from proving.screens import box_answer, word_answer  # noqa: E402
from runner import (add_scan_argument, changes_of, close_screen, load_scan, menu_from_shooting, proofs_file,  # noqa: E402
                    prover_session, scan_position)

Refused = safety.Refused
# the row of boxes' places, measured on the a1 II's Zebra Level (kit2_look_zebra_a 00012-00015, kit2_zebra_split, the
# zebra crawl's 00024/00025): three on Std+Range, the first two on Lower Limit
PLACES = [(138, 349, 380, 404), (382, 349, 500, 404), (502, 349, 620, 404)]
PROBES = "option_boxes.jsonl"          # in PROOF_RUN: one line per probe
MAX_WALK = 130                         # presses at most to a box's end (Standard has 110 values)
RETRY_WAIT = 2.0                       # s before the second reader is asked again, where it did not answer (ask_box)
LIST_STEPS = 12                        # Down presses at most to light the option in its list
# the screen that stalls the remote link while OSD Image Mode is on (kit2_zebra_split, 2026-11-18): this box lit on this
# value while the other box reads that value
HAZARD = {"box": "Standard", "value": "30", "while": ("Range", "±5")}
# the a1 II's boxes that step by one constant step and stop at two ends (kit2_pass2: Standard 0 to 109, Range ±1 to ±10),
# that step held as a consistency test of their readings; any other box's values are recorded as read (Lower Limit's
# are not known yet: a list such as 70+ to 100+, perhaps one that comes round)
STEPPED = ("Standard", "Range")


def _read(cam, box, expect: str = "text") -> str:
    """The text at `box` of the frame on show, read as boxes_run reads its boxes (boxes_run.lines: OCR of the frame).
    The kit's readers move onto camkit.reading.read kind by kind (docs/decisions/0022); this one moves with boxes_run's."""
    return ocr.text_in(boxes_lines(cam), box)


def title(cam) -> str:
    """The list's lit option as its title line reads it ("Custom 1")."""
    return _read(cam, live.OPTION_TITLE, "label").strip()


def word(cam) -> str:
    """The word the camera writes above the lit box ("Type", "Standard") as OCR reads it, "" with none lit: never a
    box's name as it is (box_name)."""
    return _read(cam, live.BOX_WORD, "label").strip()


def clean_name(t) -> str:
    """`t` in plain Latin, OCR's look-alike letters folded (camkit.match.LOOKALIKES: OCR read "Tyрe", its р Cyrillic,
    above the a1 II's Type box), its spaces one: "" where it is empty or still holds a letter that is not ASCII."""
    t = " ".join(unicodedata.normalize("NFKC", str(t or "")).translate(match.LOOKALIKES).split())
    return t if t.isascii() and re.search(r"[A-Za-z]", t) else ""


def only_box(probed: dict, only: str | None) -> str | None:
    """The probe's name of the box --only names (compared as option names are: case, spaces and look-alikes aside),
    or None where it names none of them."""
    return next((n for n in (probed.get("boxes") or {}) if option_key(n) == option_key(only or "")), None)


def read_at(cam, b: int) -> str:
    """Box b's value as OCR reads it: its look-alikes and the "‡" read for "±" undone, the spaces OCR puts beside a "+" or
    a "±" taken out and the rest one space ("Std +Range" is Std+Range, "‡ 5" ±5, "Lower Limit" stays two words)."""
    t = _read(cam, PLACES[b]).translate(LOOKALIKE).translate(live.VALUE_FOLD)
    return re.sub(r"\s*([+±])\s*", r"\1", " ".join(t.split()))


def lit_place(cam) -> int | None:
    """The place of the one lit box (its orange, camkit.live.boxes_lit), or None with none lit or more than one."""
    lit = live.boxes_lit(cam.frame.image, PLACES)
    return lit[0] if len(lit) == 1 else None


def drawn(cam) -> int:
    """How many boxes the row draws, by their outlines (camkit.live.boxes_drawn): two under Lower Limit, three under
    Std+Range on the a1 II. The prover moves between them by this count, never by pressing past an end."""
    return live.boxes_drawn(cam.frame.image, PLACES)


def _same(a, b) -> bool:
    return option_key(a) == option_key(b)


def cursor_refused(cam, option: str, name: str | None, b: int) -> str:
    """Why the frame on show is not `option`'s box b (named `name`) with the cursor in it, or "" (live.in_box_refused)."""
    return live.in_box_refused(option, name, b, PLACES, boxes_lines(cam), cam.frame.image)


_PASSED = []                            # the frame check 1 last passed on: the only one the reader is asked about


def in_box(cam, option: str, name: str | None, b: int) -> None:
    """Check 1, after every press inside the boxes and before every reading there: the title line names `option`,
    exactly one box of the row is filled orange (pixels) and it is box b, and the word above the row is `name` (any
    word where None); else the run stops at once, before another key goes. A Right on the last box leaves the boxes
    for the list, whose cursor Up and Down then move (kit2_pass2 241721, 241724, 241752-241754): the walk took Custom
    2's row for Custom 1's Lower Limit there, and the reader read "70+" in no box at all. The frame it passes on is the
    only one the second reader may then be asked about (ask_box)."""
    _PASSED.clear()
    why = cursor_refused(cam, option, name, b)
    if why:
        raise Failed(f"the cursor is no longer in {option}'s {name or f'box {b + 1}'} "
                     f"({getattr(cam.frame.path, 'name', '')}): {why}")
    _PASSED.append(cam.frame)


def press_in(cam, key: str, option: str, names: list, b: int, vals: list | None = None) -> None:
    """`key` pressed with the cursor inside the boxes, then check 1 on box b: Up or Down step box b (the hazard refused
    first, hazard_refused); Left or Right move to box b, the box beside the one lit."""
    if key in ("up", "down"):
        why = hazard_refused(cam, b, key, names, vals)
        if why:
            raise Refused(why)
    # a step whose change the settle saw needs no look again (LiveCamera.look_late), a move between boxes keeps it
    cam.press(key, **({"seen_enough": True} if key in ("up", "down") else {}))
    in_box(cam, option, names[b] if b < len(names) else None, b)


def go(cam, option: str, names: list, src: int, dst: int) -> None:
    """From box `src` to box `dst` of the row `names`: that many Rights or Lefts, each followed by check 1. Never a
    Right on the last box nor a Left on the first: `dst` is a box the row draws (drawn)."""
    if not 0 <= dst < len(names):
        raise Failed(f"{option}: no box {dst + 1} in its row of {len(names)} ({', '.join(names)})")
    step = 1 if dst > src else -1
    for k in range(src + step, dst + step, step):
        press_in(cam, "right" if step > 0 else "left", option, names, k)


def open_option(cam, cycle, model, row: str, option: str) -> None:
    """From the shooting screen: MENU, the row by the scan, Right (its list), Down until its title line names `option`;
    Failed where the option never comes up."""
    menu_from_shooting(cam)
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, row) is None:
        raise Failed(f"could not reach {row!r} by the scan")
    cam.press("right")
    for _ in range(LIST_STEPS):
        if _same(title(cam), option):
            return
        cam.press("down")
    raise Failed(f"{row}: {option!r} never came up in its list (its title line read {title(cam)!r})")


def enter_box(cam, index: int, names: list, option: str) -> None:
    """From the list with the option lit: Right into its boxes (the first box lit), then to box `index` of the row
    `names` (go), every press followed by check 1."""
    cam.press("right")
    in_box(cam, option, names[0] if names else None, 0)
    go(cam, option, names, 0, index)


def _next(now: str, key: str, vals: list | None = None) -> str | None:
    """The value a press of `key` should bring: the next in `vals` (Up order), or for a number one more or less."""
    if vals and now in vals:
        i = vals.index(now) + (1 if key == "up" else -1)
        return vals[i] if 0 <= i < len(vals) else now
    m = re.fullmatch(r"(\D*)(\d+)(\D*)", now or "")
    return f"{m.group(1)}{int(m.group(2)) + (1 if key == 'up' else -1)}{m.group(3)}" if m else None


class BoxRead(NamedTuple):
    """One reading of a box: the value taken, OCR's reading as read (ocr), the second reader's in the box's shape
    (vlm, None: not asked), the reader that answered (reader) and whether it stands in for the second reader, and which
    gave the value (by: "ocr", "both", "vlm")."""
    value: str
    ocr: str
    vlm: str | None = None
    reader: str | None = None
    by: str = "ocr"
    stand_in: bool = False


def box_name(cam, option: str, b: int) -> str:
    """The name of box b, lit, as the camera writes it above the row, in plain Latin (clean_name): what the probe line,
    the proof line's path, --only and every message carry. Where OCR's word is empty or not plain Latin once its
    look-alikes are folded, the second reader is asked for it (proving.screens.word_answer, PROMPTS["box_word"]), only
    on a frame check 1 has just passed (in_box), once more after RETRY_WAIT where it does not answer, and both readings
    logged ("box_name"); a name still not plain Latin stops the run, nothing written."""
    raw = word(cam)
    got = clean_name(raw)
    if got:
        return got
    frame = getattr(cam.frame.path, "name", "")
    if not _PASSED or _PASSED[0] is not cam.frame:
        raise Failed(f"the second reader was about to be asked the name of {option}'s box {b + 1} on {frame}, a frame "
                     "check 1 has not passed: not asked")
    said, who, standing = word_answer(cam)
    if said is None:
        time.sleep(RETRY_WAIT)
        said, who, standing = word_answer(cam)
    got = clean_name(said)
    log = getattr(getattr(cam, "run", None), "log", None)
    if log:
        log("box_name", box=b, frame=frame, ocr=raw, vlm=said, taken=got or None, reader=who)
    if not got:
        raise Failed(f"{option}'s box {b + 1} on {frame}: the word above the row reads {raw!r} to OCR and "
                     f"{said!r} to the second reader: not a name in plain Latin letters, so it is not written down")
    return got


def ask_box(cam) -> tuple:
    """The second reader's (text, name, stands in) about the lit box (proving.screens.box_answer), asked once more after
    RETRY_WAIT where it does not answer: it runs on another machine, which can be busy. The text is None after both."""
    if not _PASSED or _PASSED[0] is not cam.frame:
        raise Failed(f"the second reader was about to be asked about a box on {getattr(cam.frame.path, 'name', '')}, a "
                     "frame check 1 has not passed (the cursor's place in the boxes unchecked): not asked")
    said, who, standing = box_answer(cam)
    if said is None:
        time.sleep(RETRY_WAIT)
        said, who, standing = box_answer(cam)
    return said, who, standing


def value_read(cam, b: int, like: str, fits=None, always: bool = False, need: str = "") -> BoxRead:
    """Box b's value, read in the shape of its values (`like`, one of them: camkit.live.box_value, OCR's glyph for the
    sign and the digits' look-alikes undone; a box of words as read). OCR's reading stands alone where it is a clean
    value that `fits` (what a press may have brought) takes and `always` is False. Otherwise, and always where `always`
    (an end of a walk, the value held, a value to be kept with OK: each decides what is written down), the second
    reader is asked about the lit box itself (ask_box, one retry), and both readings are logged with the one taken
    ("box_reading": frame, box, ocr, vlm, taken, reader). Its value, in the box's shape, is taken where it is clean and
    fits; where it does not answer, or its value does not fit, the walk stops in plain words naming the frame, never a
    guess (`need` says what the reading was for). The owner's rule (2026-11-06): the reader is right where OCR drops or
    mangles short text, and it is asked before a row fails; about 1 s a call, it is used where it makes sense."""
    raw = read_at(cam, b)
    words = live.box_shape(like) is None
    ocr_v = raw if words else live.box_value(raw, like)

    def clean(v):
        return bool(v) and (words or live.box_number(v, like) is not None) and (fits is None or fits(v))
    if clean(ocr_v) and not always:
        return BoxRead(ocr_v, raw)
    said, who, standing = ask_box(cam)
    vlm_v = None if said is None else (" ".join(said.split()) if words else live.box_value(said, like))
    if words and vlm_v is not None and option_key(vlm_v) == option_key(ocr_v):
        vlm_v = ocr_v                   # the same words, spaced as OCR read them (the label a proof line keeps)
    taken = vlm_v if vlm_v is not None and clean(vlm_v) else None
    frame = getattr(cam.frame.path, "name", "")
    log = getattr(getattr(cam, "run", None), "log", None)
    if log:
        log("box_reading", box=b, frame=frame, ocr=raw, vlm=vlm_v, taken=taken, reader=who)
    why = need or f"OCR read {raw!r}"
    if said is None:
        raise Failed(f"box {b} on {frame}: {why}, and the second reader did not answer (asked twice, {RETRY_WAIT:g} s "
                     "apart): the kit does not guess a value. Check the reader (kit/tools/reader_check.py) and run the "
                     "probe again")
    if taken is None:
        raise Failed(f"box {b} on {frame}: {why}, the second reader read {said!r}, and neither is a value a stepped box "
                     "gives here: the kit does not guess which")
    return BoxRead(taken, raw, vlm_v, who, "both" if taken == ocr_v else "vlm", standing)


def value_at(cam, b: int, like: str, fits=None, always: bool = False, need: str = "") -> str:
    """value_read's value alone."""
    return value_read(cam, b, like, fits, always, need).value


def hazard_refused(cam, b: int, key: str, names: list, vals: list | None = None) -> str:
    """Why `key` on box b may not go (HAZARD), or "": on OSD eyes, never onto the hazard box's value while the other box
    reads its value."""
    if getattr(getattr(cam, "hdmi", None), "name", "") != "osd" or b >= len(names) or names[b] != HAZARD["box"]:
        return ""
    other, its = HAZARD["while"]
    now = live.box_value(read_at(cam, b), HAZARD["value"])
    if other not in names or _next(now, key, vals) != HAZARD["value"] or \
            live.box_value(read_at(cam, names.index(other)), its) != its:
        return ""
    return (f"{HAZARD['box']} {HAZARD['value']} with {other} at {its} is a screen whose picture stalls the camera's remote "
            "link while the kit reads its screen through it (OSD eyes): step it with HDMI eyes, or move "
            f"{other} off {its} first")


def _stepped(like: str, prev: str, key: str, step: int | None):
    """What a press of `key` from `prev` may bring in a box of numbers shaped as `like`: `prev` again (an end stays on
    a further press), or a value one constant step on, in the press's direction (`step` once the walk has seen one)."""
    def fits(v):
        n, p = live.box_number(v, like), live.box_number(prev, like)
        if n is None or p is None:
            return False
        if n == p:
            return True
        return (n > p) == (key == "up") and (step is None or abs(n - p) == step)
    return fits


class Walk(NamedTuple):
    """A box walked: its values in Up order (for a list that comes round, in the order Up shows them from the value
    held), the value it held, and whether it comes round (a list with no ends) rather than stopping at two ends."""
    values: list
    held: str
    wraps: bool = False


def walk(cam, b: int, names: list, option: str) -> Walk:
    """Box b of the row `names` (its cursor in it: check 1 first and after every press, press_in) walked to its ends:
    Down until a further press changes nothing (its low end) or a value seen before comes back (a list that comes round:
    recorded so, with no ends), then Up from the low end to the top end the same way. What is read is recorded, nothing
    assumed of it: a value of numbers is read in its values' shape, the second reader asked about the lit box where OCR's
    reading is empty or unclean, and always about the value held and each end (value_read). A box that steps by one
    constant step (STEPPED) is held to that too where its readings are numbers, a consistency test sent to the reader
    when broken. No end and no coming round within MAX_WALK presses stops the walk in plain words. The box is left where
    the walk ended."""
    name = names[b] if b < len(names) else "?"
    in_box(cam, option, name, b)
    held = read_at(cam, b)
    numbers = live.box_shape(held) is not None
    if numbers:
        held = value_at(cam, b, held, always=True, need=f"the value {name} held")
    stepped, step = numbers and name in STEPPED, None

    def read(prev, key, seen):
        if not numbers:
            return read_at(cam, b)
        steps = _stepped(held, prev, key, step) if stepped else None
        fits = None if steps is None else (lambda v: steps(v) or v in seen)
        ocr_v = live.box_value(read_at(cam, b), held)
        end, back = ocr_v == prev, ocr_v != prev and ocr_v in seen   # each decides what is written: the reader confirms
        return value_at(cam, b, held, fits, always=end or back,
                        need=f"after {key} from {prev!r}, " + ("an end of " if end else "a value seen before in " if back
                                                                else "") + name)

    def stop(why):
        return Failed(f"{option}'s {name} ({getattr(cam.frame.path, 'name', '')}): {why}: the walk stops")
    seen = [held]                       # in Down order
    for _ in range(MAX_WALK):
        press_in(cam, "down", option, names, b)
        v = read(seen[-1], "down", seen)
        if v == seen[-1]:
            break                       # the low end: it stayed on a further press
        if v in seen:                   # came round: a list with no ends, in the order Up shows it from the value held
            if v != held:
                raise stop(f"Down brought {v!r} back after {seen}, not the value held: the readings disagree")
            return Walk([held] + seen[:0:-1], held, True)
        if stepped:
            step = step or abs(live.box_number(v, held) - live.box_number(seen[-1], held))
        seen.append(v)
    else:
        raise stop(f"neither an end (a value that stays on a further press) nor its values coming round within "
                   f"{MAX_WALK} Down presses")
    vals = [seen[-1]]
    for _ in range(MAX_WALK):
        press_in(cam, "up", option, names, b)
        v = read(vals[-1], "up", vals)
        if v == vals[-1]:
            break                       # the top end
        if v in vals:
            raise stop(f"Up brought {v!r} back after {vals}, though Down stopped at an end: the readings disagree")
        if stepped:
            step = step or abs(live.box_number(v, held) - live.box_number(vals[-1], held))
        vals.append(v)
    else:
        raise stop(f"no top end within {MAX_WALK} Up presses")
    if held not in vals or not all(vals):
        raise stop(f"the walk read {vals} with {held!r} held")
    return Walk(vals, held, False)


def step_to(cam, b: int, vals: list, target: str, names: list, option: str) -> None:
    """Box b (its cursor in it) stepped to `target` by its probe's values (Up order), every press followed by check 1
    (press_in, the hazard refused on the way); Failed where it reads a value not among them or the target never comes
    up."""
    in_box(cam, option, names[b] if b < len(names) else None, b)
    for _ in range(len(vals) + 1):
        now = value_at(cam, b, target, lambda v: v in vals, need=f"stepping to {target!r}")
        if now == target:
            return
        if now not in vals:
            raise Failed(f"box {b}: read {now!r}, not one of its values ({getattr(cam.frame.path, 'name', '')})")
        press_in(cam, "up" if vals.index(target) > vals.index(now) else "down", option, names, b, vals)
    raise Failed(f"box {b}: {target!r} never came up")


def row_names(cam, option: str, first: str) -> list:
    """With the first box lit (named `first`): the row's boxes counted from what is drawn (drawn: their outlines), each
    named by the word the camera writes above it as Right lights it in turn, then Left back to the first; every press
    followed by check 1, never a Right on the last box (it leaves the boxes for the list) nor a Left on the first."""
    in_box(cam, option, first, 0)
    count = drawn(cam)
    names = [first]
    for i in range(1, count):
        press_in(cam, "right", option, names, i)
        names.append(box_name(cam, option, i))
    for i in range(count - 2, -1, -1):
        press_in(cam, "left", option, names, i)
    return names


def hazard_order(names: list) -> list:
    """The value boxes of a row in the order the probe walks them: the hazard's other box before the hazard's box."""
    rest = list(names[1:])
    other = HAZARD["while"][0]
    if other in rest and HAZARD["box"] in rest:
        rest.remove(other)
        rest.insert(rest.index(HAZARD["box"]), other)
    return rest


def probe(cam, link, cycle, model, row: str, option: str) -> dict:
    """The read-only look (the module's --probe); its record (written by main)."""
    open_option(cam, cycle, model, row, option)
    cam.press("right")
    in_box(cam, option, None, 0)        # the first box lit, its name written above the row
    first = box_name(cam, option, 0)
    tw = walk(cam, 0, [first], option)
    boxes, types = {first: {"values": tw.values, "held": tw.held, "wraps": tw.wraps}}, {}
    for t in [tw.held] + [v for v in tw.values if v != tw.held]:
        step_to(cam, 0, tw.values, t, [first], option)
        names = row_names(cam, option, first)
        types[t] = names
        for n in hazard_order(names):
            i = names.index(n)
            go(cam, option, names, 0, i)
            w = walk(cam, i, names, option)
            boxes[n] = {"values": w.values, "held": w.held, "type": t, "wraps": w.wraps}
            go(cam, option, names, i, 0)
    close_screen(cam, link)            # MENU: the screen cancelled, every stepped value taken back
    return {"row": row, "option": option, "types": types, "boxes": boxes}


def probe_refused(probed: dict) -> str:
    """Why a probe line cannot plan a proof run, or "": every box of every Type's row must have its walk in it."""
    boxes = probed.get("boxes") or {}
    names = {n for row in (probed.get("types") or {}).values() for n in row} | set(boxes)
    missing = sorted({n for row in (probed.get("types") or {}).values() for n in row if n not in boxes})
    unclean = sorted(n for n in names if clean_name(n) != n)
    if not probed.get("types"):
        return "it records no row of boxes"
    if unclean:
        return (f"it names {', '.join(map(repr, unclean))}, not in plain Latin letters (OCR's look-alikes, which a "
                "proof line would carry into the report and the definition): probe again")
    return f"it lacks the walk of {', '.join(missing)}" if missing else ""


def latest_probe(run, row: str, option: str) -> dict | None:
    """The option's latest probe in the run (PROBES), or None."""
    f = Path(run.dir) / PROBES
    if not f.exists():
        return None
    got = None
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("row") == row and r.get("option") == option:
            got = r
    return got


def values_for(name: str, vals: list, held: str, range_held: str | None = None, wraps: bool = False) -> list:
    """The values a box is proved on: both ends, the held value's neighbours, one in the middle, then the held value
    (which must change nothing); for a list that comes round (no ends), the held value's neighbours either side and
    the one opposite it; for a box of two or three options, each other one, then the held. The hazard's value is left
    out while its other box holds its value (HAZARD)."""
    i, n = vals.index(held), len(vals)
    if n <= 3:
        picks = list(vals)
    elif wraps:
        picks = [vals[(i - 1) % n], vals[(i + 1) % n], vals[(i + n // 2) % n]]
    else:
        picks = [vals[0], vals[-1], vals[i - 1] if i else None, vals[i + 1] if i + 1 < n else None, vals[n // 2]]
    out = []
    for v in picks:
        if v is None or v == held or v in out:
            continue
        if name == HAZARD["box"] and v == HAZARD["value"] and range_held == HAZARD["while"][1]:
            continue
        out.append(v)
    return out + [held]


def keep(cam, link, hdmi, cycle, model, row: str, option: str, names: list, idx: int, vals: list, target: str) -> dict:
    """Box `idx` (of the row `names`) stepped to `target` and kept with OK, judged first on the screen's own shape
    (ok_refused) and on the box's value as OCR and the second reader read it (value_read, the reader always asked:
    the value kept decides the proof), then what the camera did with the OK (proving.commit.after_ok: a refusal or a
    notice closed with MENU, never OK; no information screen taken, the boxes reading as no known kind), then a
    settings download; {"chosen_frame", "row_frame", "shown", "vlm", "vlm_reader", "read_by", "stand_in", "dat",
    "outcome"}."""
    open_option(cam, cycle, model, row, option)
    enter_box(cam, idx, names, option)
    step_to(cam, idx, vals, target, names, option)
    in_box(cam, option, names[idx], idx)
    consent = live.OptionBoxes(f"{option}'s {names[idx]} box on {target}: OK keeps it (optboxes_run)", option, names[idx],
                               target, PLACES[idx], tuple(PLACES))
    read = value_read(cam, idx, target, lambda v: v in vals, always=True, need=f"the value {target!r} to keep with OK")
    if read.value != target:
        raise Failed(f"{row} > {option} > {names[idx]}: it reads {read.value!r} on {getattr(cam.frame.path, 'name', '')}, "
                     f"not {target!r}: no OK")
    why = ok_refused(cam, consent, read.value)
    if why:
        raise Failed(f"{row} > {option} > {names[idx]} = {target}: no OK: {why}")
    chosen = getattr(cam.frame.path, "name", "")
    cam.answer_once = consent           # read as a dialog the camera's own guard judges it; as no known kind, this does
    cam.press("enter")
    row_frame = getattr(cam.frame.path, "name", "")
    got = after_ok(cam, f"{row} > {option} > {names[idx]}", label=target, info=False)
    to_shooting(link, hdmi, "the download after OK")
    # no wait first: camlink waits up to 5 s for the camera to allow a settings download
    dat = link.download(f"{names[idx]}-{vals.index(target)}".replace(" ", "-"))
    wait_lock(time.monotonic(), hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
    return {"chosen_frame": chosen, "row_frame": row_frame, "shown": read.ocr, "vlm": read.vlm, "vlm_reader": read.reader,
            "read_by": read.by, "stand_in": read.stand_in, "dat": dat, "outcome": got}


def kept_base(got: dict, what: str, chose: str) -> Path:
    """The download a base was made of (keep's), or Failed where the camera refused its OK: no base, nothing proved
    from it (`what` names the base, `chose` the choice its OK went on)."""
    if not got["outcome"].applied:
        raise Failed(f"{what}: the camera refused {chose} after OK (its notice on {got['outcome'].notice['frame']}): no "
                     "base, nothing proved from it")
    return got["dat"]


def ok_refused(cam, consent, read: str | None = None) -> str:
    """Why the OK may not go on the screen on show (camkit.live.option_boxes_refused), or "": the box's value judged on
    `read`, the prover's own reading of it (value_at: OCR's, or the second reader's), where given."""
    return live.option_boxes_refused(consent, boxes_lines(cam), cam.frame.image, read)


def _diff(a, b) -> list:
    return camset.diff(camset.read(a), camset.read(b))


def prove(cam, link, hdmi, cycle, model, row: str, option: str, probed: dict, only, start, out) -> None:
    """The proof run (the module's), from the option's probe `probed`; proof lines into `out`."""
    types, boxes = probed["types"], probed["boxes"]
    first = next(iter(types.values()))[0]
    theld, tvals = boxes[first]["held"], boxes[first]["values"]
    names_held = types[theld]
    base = kept_base(keep(cam, link, hdmi, cycle, model, row, option, names_held, 0, tvals, theld), "the base",
                     f"{row} > {option} > {first} = {theld}")
    moved = _diff(start, base)
    print(f"base: {row} on {option}, its boxes as they stand ({len(moved)} records moved from the start file: "
          f"{', '.join(c.key for c in moved) or 'none'}); every proof below is compared with it", flush=True)
    order = [first] + hazard_order(names_held) + [n for t, ns in types.items() if t != theld for n in ns[1:]]
    osd = getattr(getattr(cam, "hdmi", None), "name", "") == "osd"
    other, its = HAZARD["while"]
    for name in dict.fromkeys(order):
        if only not in (None, name) or name not in boxes:
            continue
        info = boxes[name]
        t = info.get("type", theld)
        names = types[t]
        idx, b_base = names.index(name), base
        if t != theld:
            b_base = kept_base(keep(cam, link, hdmi, cycle, model, row, option, names_held, 0, tvals, t),
                               f"{name}'s base", f"{row} > {option} > {first} = {t}")
            print(f"{name}: from a base with {first} on {t}", flush=True)
        range_held = boxes.get(other, {}).get("held")
        if osd and name == HAZARD["box"] and other in names and range_held == its:
            ovals = boxes[other]["values"]
            off = ovals[ovals.index(its) + 1] if ovals.index(its) + 1 < len(ovals) else ovals[ovals.index(its) - 1]
            b_base = kept_base(keep(cam, link, hdmi, cycle, model, row, option, names, names.index(other), ovals, off),
                               f"{name}'s base", f"{row} > {option} > {other} = {off}")
            range_held = off
            print(f"{name}: from a base with {other} on {off} (OSD eyes: {name} {HAZARD['value']} with {other} at {its} "
                  "stalls the camera's remote link)", flush=True)
        vals = info["values"]
        for target in values_for(name, vals, info["held"], range_held, info.get("wraps", False)):
            got = keep(cam, link, hdmi, cycle, model, row, option, names, idx, vals, target)
            ch, done = _diff(b_base, got["dat"]), got["outcome"]
            out.write(json.dumps({"path": [row, option, name], "kind": "list", "index": vals.index(target),
                                  "label": target, "shown": got["shown"], "vlm": got["vlm"],
                                  "vlm_reader": got["vlm_reader"], "read_by": got["read_by"],
                                  **({"vlm_stand_in": True} if got["stand_in"] else {}),
                                  "chosen_frame": got["chosen_frame"],
                                  "row_frame": got["row_frame"], "dat": got["dat"].name, "base": b_base.name,
                                  **({"notice": done.notice} if done.notice else {}), "applied": done.applied,
                                  "boxes": True, "sampled": True, "changes": changes_of(ch)}) + "\n")
            out.flush()
            if got["stand_in"]:
                print(f"  {name} = {target}: read by {got['vlm_reader']!r}, standing in for the second reader", flush=True)
            if not done.applied:
                print(f"  {name} = {target}: refused by the camera, not proved", flush=True)
            elif ch:
                print(f"  {name} = {target}: {len(ch)} records {[(c.key, c.before, c.after) for c in ch][:4]}", flush=True)
            elif target != info["held"]:
                print(f"  {name} = {target}: not proved: no record moved from its base", flush=True)
            if target == info["held"] and ch:
                raise Failed(f"{name}: back on {target!r}, {len(ch)} records still differ from its base")


def arguments(argv=None):
    ap = argparse.ArgumentParser(description="An option of a list row that draws a row of boxes (Zebra Level > Custom N)")
    ap.add_argument("--row", required=True, help="the list row (\"Zebra Level\")")
    ap.add_argument("--option", required=True, help="its option that draws the boxes (\"Custom 1\")")
    ap.add_argument("--probe", action="store_true", help="read only: walk every box to its ends, choose nothing")
    ap.add_argument("--only", default=None, help="prove this box alone (its name as the camera writes it)")
    ap.add_argument("--context", default=None, help="the state the proofs are made in (e.g. Stills mode, Zebra Level "
                                                    "Custom 1)")
    add_scan_argument(ap)
    return ap.parse_args(argv)


def main(argv=None):
    a = arguments(argv)
    cycle, model = load_scan(a.scan)
    run = Run(PROOF_RUN)
    probed = None
    if not a.probe:
        probed = latest_probe(run, a.row, a.option)
        if probed is None:
            sys.exit(f"no probe of {a.row} > {a.option} in {PROOF_RUN}: run this command with --probe first (read only), "
                     "which walks each box to its ends; nothing was sent to the camera")
        why = probe_refused(probed)
        if why:
            sys.exit(f"the latest probe of {a.row} > {a.option} in {PROOF_RUN} cannot plan a proof run: {why}. Run the "
                     "probe again; nothing was sent to the camera")
        if a.only and only_box(probed, a.only) is None:
            sys.exit(f"--only {a.only!r}: not a box the probe saw ({', '.join(probed.get('boxes', {}))})")
    hdmi = eyes_from_config(run)
    stopped = []
    with proofs_file(run, a.context) as out, prover_session(run, hdmi) as s:
        try:
            if a.probe:
                got = probe(s.cam, s.link, cycle, model, a.row, a.option)
                if got:
                    got.update(eyes=getattr(hdmi, "name", None), context=a.context, t=round(time.time(), 3))
                    with open(Path(run.dir) / PROBES, "a", encoding="utf-8", newline="\n") as f:
                        f.write(json.dumps(got) + "\n")
                    for n, b in got["boxes"].items():
                        span = "a list that comes round" if b.get("wraps") else f"{b['values'][0]} to {b['values'][-1]}"
                        print(f"{n}: {len(b['values'])} values, {span}, held {b['held']!r}", flush=True)
            else:
                prove(s.cam, s.link, hdmi, cycle, model, a.row, a.option, probed,
                      only_box(probed, a.only) if a.only else None, s.start, out)
        except Exception as e:
            stopped.append(e)
            if a.probe:
                print(f"the probe stopped before every box of every Type was read: nothing was written to {PROBES}",
                      flush=True)
            raise
    code = stop_status(stopped[0] if stopped else None)
    if code:
        print(f"the run was stopped by {'a refusal' if code == EXIT_REFUSED else 'a failure'}: its start file is back and "
              f"checked, but what came after it was not done (exit status {code})", flush=True)
        sys.exit(code)


if __name__ == "__main__":
    main()
