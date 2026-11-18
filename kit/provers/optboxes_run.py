"""Prove an option of a list row that draws a row of boxes of its own: the a1 II's Zebra Level > Custom 1 and Custom 2
(2026-11-18).

    .venv/bin/python -u kit/provers/optboxes_run.py --scan SCAN --row "Zebra Level" --option "Custom 1" --probe
    .venv/bin/python -u kit/provers/optboxes_run.py --scan SCAN --row "Zebra Level" --option "Custom 1" \\
        --context "Stills mode, Zebra Level Custom 1" [--only Standard]

The row opens a side list; with the option lit (the title line names it) the camera draws a row of boxes at the bottom.
Right enters them, the first box lit and its name written above the row ("Type"); Right again lights the next
("Standard", then "Range"), Left goes back; Up and Down step the lit box. The first box (Type) redraws the row: on
Std+Range it is Type, Standard and Range, on Lower Limit Type and Lower Limit. A stepped value is applied live; MENU
cancels the screen and takes it back, OK keeps it. Boxes are named by the word the camera writes above the lit one.
This prover sits beside boxes_run, not in it: boxes_run's screen is two fixed boxes reached by Right from the row, while
here an option of a list draws the boxes, their count and names change with the first box, and the list is stepped to
the option first; the exit statuses, the proof run and the shape of a proof line are boxes_run's.

--probe, read only: the option lit, the first box walked once round (its options), each of its options' row of boxes
read (Right through them, each name as written), each box under each option walked to both ends (Down until a further
press changes nothing or comes round, then Up the same way: the values in Up order; a box of numbers read in its
values' shape, OCR's glyph for the ± and the digits' look-alikes undone, and the second reader asked about the lit box
itself (proving.screens.box_answer, PROMPTS["box"]) where OCR's reading is empty, unclean or breaks the walk, which must
step as a stepped box does, and always about the value held and each end: value_read, walk), then MENU, which cancels it all,
and the session's restore check. Nothing is chosen. One line goes to kit2_pass2/option_boxes.jsonl (PROBES): the
option's rows of boxes ("types") and each box's values, the one it held and the first box's option it is drawn under.

The proof run plans from the option's latest probe: a base first, the option chosen with its boxes as they stand (the
first box on the value it holds, OK), so the row's own record (Zebra Level moving to Custom N) moves there, and every
box proof is compared with that base, its changes the box's records alone. Each box then: both ends, the held value's
neighbours, one in the middle, and last the held value, which must change nothing (values_for); a box drawn under
another of the first box's options (Lower Limit) from a base with the first box on that option. Each value is stepped
to and kept with OK, judged first on the screen's own shape (camkit.live.option_boxes_refused: the title names the
option, the word above the lit box is the box's, it is lit on the value, the footer draws the OK key, nothing asks);
the camera's own Enter guard judges it again (a dialog; read as no known kind, by the OptionBoxes consent). A download
and its diff make a proof line in boxes_run's shape (path row > option > box, kind "list", its index among the probe's
values, "sampled"), into kit2_pass2/proofs.jsonl with --context; a value whose records did not move is kept with no
changes and said "not proved", never credited. The session puts the start file back at the end.

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
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, live, ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from boxes_run import EXIT_REFUSED, LOOKALIKE, PROOF_RUN, stop_status  # noqa: E402
from boxes_run import lines as boxes_lines  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import LOCK_S, Failed, option_key, to_shooting  # noqa: E402
from proving.screens import box_answer  # noqa: E402
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


def _read(cam, box, expect: str = "text") -> str:
    """The text at `box` of the frame on show, read as boxes_run reads its boxes (boxes_run.lines: OCR of the frame).
    The kit's readers move onto camkit.reading.read kind by kind (docs/decisions/0022); this one moves with boxes_run's."""
    return ocr.text_in(boxes_lines(cam), box)


def title(cam) -> str:
    """The list's lit option as its title line reads it ("Custom 1")."""
    return _read(cam, live.OPTION_TITLE, "label").strip()


def word(cam) -> str:
    """The word the camera writes above the lit box ("Type", "Standard"), "" with none lit."""
    return _read(cam, live.BOX_WORD, "label").strip()


def read_at(cam, b: int) -> str:
    """Box b's value as OCR reads it: its look-alikes and the "‡" read for "±" undone, the spaces OCR puts beside a "+" or
    a "±" taken out and the rest one space ("Std +Range" is Std+Range, "‡ 5" ±5, "Lower Limit" stays two words)."""
    t = _read(cam, PLACES[b]).translate(LOOKALIKE).translate(live.VALUE_FOLD)
    return re.sub(r"\s*([+±])\s*", r"\1", " ".join(t.split()))


def lit_place(cam) -> int | None:
    """The place of the lit box (its orange), or None with no box lit."""
    o = screen._orange(cam.frame.image)
    lit = [float(o[y0:y1, x0:x1].mean()) for x0, y0, x1, y1 in PLACES]
    best = max(range(len(PLACES)), key=lambda i: lit[i])
    return best if lit[best] > 0.3 else None


def drawn(cam) -> int:
    """How many boxes the row draws: the places that read a value."""
    return sum(1 for b in range(len(PLACES)) if read_at(cam, b))


def _same(a, b) -> bool:
    return option_key(a) == option_key(b)


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


def enter_box(cam, index: int, name: str) -> None:
    """From the list with the option lit: Right into its boxes, to box `index`, which must be lit and named `name`."""
    for _ in range(index + 1):
        cam.press("right")
    if lit_place(cam) != index or not _same(word(cam), name):
        raise Failed(f"Right {index + 1} time(s) lit box {lit_place(cam)} named {word(cam)!r}, not {name!r} "
                     f"({getattr(cam.frame.path, 'name', '')})")


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


def ask_box(cam) -> tuple:
    """The second reader's (text, name, stands in) about the lit box (proving.screens.box_answer), asked once more after
    RETRY_WAIT where it does not answer: it runs on another machine, which can be busy. The text is None after both."""
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


def press_box(cam, b: int, key: str, names: list, vals: list | None = None) -> None:
    why = hazard_refused(cam, b, key, names, vals)
    if why:
        raise Refused(why)
    cam.press(key)


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


def walk(cam, b: int, names: list | None = None) -> tuple:
    """(the lit box b's values in Up order, the value it held): Down until a further press changes nothing (its low end)
    or it comes round to the value it held, then Up the same way. The box is left where the walk ended. A box of
    numbers is read in its values' shape, the second reader asked where OCR's reading breaks the walk (value_at), and
    must walk as a stepped box does: each press one constant step on, an end a value that stays; a reading that still
    does not stops the walk, naming its frame. A box of words (Type) is read as it is, and may come round."""
    names = names or []
    name = names[b] if b < len(names) else "?"
    held = read_at(cam, b)
    numbers = live.box_shape(held) is not None
    if numbers:
        held = value_at(cam, b, held, always=True, need=f"the value {name} held")
    step = None

    def read(prev, key):
        if not numbers:
            return read_at(cam, b)
        fits = _stepped(held, prev, key, step)
        end = live.box_value(read_at(cam, b), held) == prev       # stayed: an end, which the reader confirms
        return value_at(cam, b, held, fits, always=end,
                        need=f"after {key} from {prev!r}, {'an end of ' + name if end else name}")
    cur = held
    for _ in range(MAX_WALK):
        press_box(cam, b, "down", names)
        v = read(cur, "down")
        if v in (cur, held):
            break
        if numbers:
            step = step or abs(live.box_number(v, held) - live.box_number(cur, held))
        cur = v
    vals = [cur if numbers else read_at(cam, b)]
    for _ in range(MAX_WALK):
        press_box(cam, b, "up", names)
        v = read(vals[-1], "up")
        if v == vals[-1] or v == vals[0]:
            break
        if numbers:
            step = step or abs(live.box_number(v, held) - live.box_number(vals[-1], held))
        vals.append(v)
    if held not in vals or len(set(vals)) != len(vals) or not all(vals):
        raise Failed(f"box {b} ({name}): the walk read {vals} with {held!r} held")
    return vals, held


def step_to(cam, b: int, vals: list, target: str, names: list) -> None:
    """The lit box b stepped to `target` by its probe's values (Up order); Failed where it reads a value not among them
    or the target never comes up; the hazard refused on the way (press_box)."""
    for _ in range(len(vals) + 1):
        now = value_at(cam, b, target, lambda v: v in vals, need=f"stepping to {target!r}")
        if now == target:
            return
        if now not in vals:
            raise Failed(f"box {b}: read {now!r}, not one of its values ({getattr(cam.frame.path, 'name', '')})")
        press_box(cam, b, "up" if vals.index(target) > vals.index(now) else "down", names, vals)
    raise Failed(f"box {b}: {target!r} never came up")


def row_names(cam) -> list:
    """With the first box lit: the names of the row's boxes, Right through them, each as written; then Left back."""
    names = [word(cam)]
    for i in range(1, len(PLACES)):
        cam.press("right")
        if lit_place(cam) != i:
            break
        names.append(word(cam))
    for _ in range(len(names) - 1):
        cam.press("left")
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
    if lit_place(cam) != 0 or not word(cam):
        raise Failed(f"Right on {option!r} lit no named box ({getattr(cam.frame.path, 'name', '')})")
    first = word(cam)
    tvals, theld = walk(cam, 0, [first])
    boxes, types = {first: {"values": tvals, "held": theld}}, {}
    for t in [theld] + [v for v in tvals if v != theld]:
        step_to(cam, 0, tvals, t, [first])
        names = row_names(cam)
        types[t] = names
        for n in hazard_order(names):
            i = names.index(n)
            for _ in range(i):
                cam.press("right")
            vals, held = walk(cam, i, names)
            boxes[n] = {"values": vals, "held": held, "type": t}
            for _ in range(i):
                cam.press("left")
    close_screen(cam, link)            # MENU: the screen cancelled, every stepped value taken back
    return {"row": row, "option": option, "types": types, "boxes": boxes}


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


def values_for(name: str, vals: list, held: str, range_held: str | None = None) -> list:
    """The values a box is proved on: both ends, the held value's neighbours, one in the middle, then the held value
    (which must change nothing); for a box of two or three options, each other one, then the held. The hazard's value
    is left out while its other box holds its value (HAZARD)."""
    i = vals.index(held)
    picks = [vals[0], vals[-1], vals[i - 1] if i else None, vals[i + 1] if i + 1 < len(vals) else None,
             vals[len(vals) // 2]] if len(vals) > 3 else list(vals)
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
    the value kept decides the proof), then a settings download; {"chosen_frame", "row_frame", "shown", "vlm",
    "vlm_reader", "read_by", "stand_in", "dat"}."""
    open_option(cam, cycle, model, row, option)
    enter_box(cam, idx, names[idx])
    step_to(cam, idx, vals, target, names)
    consent = live.OptionBoxes(f"{option}'s {names[idx]} box on {target}: OK keeps it (optboxes_run)", option, names[idx],
                               target, PLACES[idx])
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
    to_shooting(link, hdmi, "the download after OK")
    time.sleep(1)
    dat = link.download(f"{names[idx]}-{vals.index(target)}".replace(" ", "-"))
    time.sleep(LOCK_S)
    return {"chosen_frame": chosen, "row_frame": row_frame, "shown": read.ocr, "vlm": read.vlm, "vlm_reader": read.reader,
            "read_by": read.by, "stand_in": read.stand_in, "dat": dat}


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
    base = keep(cam, link, hdmi, cycle, model, row, option, names_held, 0, tvals, theld)["dat"]
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
            b_base = keep(cam, link, hdmi, cycle, model, row, option, names_held, 0, tvals, t)["dat"]
            print(f"{name}: from a base with {first} on {t}", flush=True)
        range_held = boxes.get(other, {}).get("held")
        if osd and name == HAZARD["box"] and other in names and range_held == its:
            ovals = boxes[other]["values"]
            off = ovals[ovals.index(its) + 1] if ovals.index(its) + 1 < len(ovals) else ovals[ovals.index(its) - 1]
            b_base = keep(cam, link, hdmi, cycle, model, row, option, names, names.index(other), ovals, off)["dat"]
            range_held = off
            print(f"{name}: from a base with {other} on {off} (OSD eyes: {name} {HAZARD['value']} with {other} at {its} "
                  "stalls the camera's remote link)", flush=True)
        vals = info["values"]
        for target in values_for(name, vals, info["held"], range_held):
            got = keep(cam, link, hdmi, cycle, model, row, option, names, idx, vals, target)
            ch = _diff(b_base, got["dat"])
            out.write(json.dumps({"path": [row, option, name], "kind": "list", "index": vals.index(target),
                                  "label": target, "shown": got["shown"], "vlm": got["vlm"],
                                  "vlm_reader": got["vlm_reader"], "read_by": got["read_by"],
                                  **({"vlm_stand_in": True} if got["stand_in"] else {}),
                                  "chosen_frame": got["chosen_frame"],
                                  "row_frame": got["row_frame"], "dat": got["dat"].name, "base": b_base.name,
                                  "applied": True, "boxes": True, "sampled": True, "changes": changes_of(ch)}) + "\n")
            out.flush()
            if got["stand_in"]:
                print(f"  {name} = {target}: read by {got['vlm_reader']!r}, standing in for the second reader", flush=True)
            if ch:
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
        if a.only and a.only not in probed.get("boxes", {}):
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
                        print(f"{n}: {len(b['values'])} values, {b['values'][0]} to {b['values'][-1]}, held "
                              f"{b['held']!r}", flush=True)
            else:
                prove(s.cam, s.link, hdmi, cycle, model, a.row, a.option, probed, a.only, s.start, out)
        except Exception as e:
            stopped.append(e)
            raise
    code = stop_status(stopped[0] if stopped else None)
    if code:
        print(f"the run was stopped by {'a refusal' if code == EXIT_REFUSED else 'a failure'}: its start file is back and "
              f"checked, but what came after it was not done (exit status {code})", flush=True)
        sys.exit(code)


if __name__ == "__main__":
    main()
