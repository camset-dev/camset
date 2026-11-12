"""Prove a scale row: a number stepped with Left/Right between − and + boxes, applied with OK
(AF Transition Speed, AF Subj. Shift Sensitivity, Framing Tracking Speed: Movie mode, 2026-10-30).

    .venv/bin/python -u kit/provers/scale_run.py --scan kit2_page_scan_movie --context "Movie mode" \\
        --row "AF Transition Speed" --row "Auto Framing Settings > Framing Tracking Speed"
    .venv/bin/python -u kit/provers/scale_run.py --scan kit2_page_scan_1108 --context "stills" \\
        --set "Monitor Brightness > Brightness Setup=Manual" --panel-row "Monitor Brightness"
    .venv/bin/python -u kit/provers/scale_run.py --scan kit2_page_scan_osd3 --set "Select Finder/Monitor=VF(Manual)" \\
        --set "Viewfinder Bright. > Brightness Setup=Manual" --panel-row "Viewfinder Bright."

--panel-row: a slider inside a panel (Monitor Brightness, Viewfinder Bright.): the row opens on a setup row (the a1
II's Brightness Setup) whose option must read Manual, as the slider is there only then; Down goes to the slider, and
from there the row is proved as any scale. The run sets that setup row itself, through the menu, before the rows: a
--panel-row run must name its panel's setup row among the --set arguments, on Manual ("ROW > SETUP=Manual"), or it is
refused before anything connects, the refusal giving the --set to add, the setup row's label taken from the definition
(its setting one row inside the panel with Manual among its values: panel_set_refused). So every proof's context names
the setup row's option, and none tells that the camera already stood on Manual (decision 16). A plain scale opened as
a panel, or a panel opened as a plain scale (the pixel reader's "submenu" on opening), stops the row before any Left,
Right or OK. On a scale with negative numbers the labels are the camera's around zero: -2, -1, ±0, +1, +2, whoever read
them (labels_of). --set "ROW=OPTION"
(repeatable, in the order given; "A > B=OPTION" for a submenu's or a panel's row) puts ROW on OPTION through the menu
after the start download and before the first row, as kit/provers/afreg_run.py sets its setup rows (mode_switch's
set_row), then downloads the base the choices are compared with; the proofs' context names each ("Select
Finder/Monitor = VF(Manual)") before --context's words; a step that fails stops the run before any row, and the
session's end puts the start file back as ever. A --set row is judged as a --row (a never-open one needs its own
--allow), and never the camera's identity, a connection or its region, whatever is allowed (decision 8:
safety.identity_row). The option a --set row held is never printed: only the option asked for, and a count of records.

The pixel reader reads these screens as sliders since 2026-11-08 (their − and + drawn bare, without Aspect Marker
Level's boxes: camkit.screen's _bare_signs), but it gives no number for them, so this reads them by OCR: the title
must be the row's own label and the footer must offer OK before anything but an arrow is pressed (an OK OCR drops on
two frames may be the reader's: open_row); the value is the number in the middle. Where OCR reads no number on a frame
(nothing, or text that is no number: a letter for a digit), the vision reader is asked (proving.screens.option_answer:
its "selected", or its "value" where "selected" holds no digit), one question a frame, and its answer counts only when
it is a number (single digits on the volume scales: OCR read some and gave nothing for others, 2026-11-09); every
proof line says which of the two read the value chosen ("read_by": "ocr" or "reader"). A frame neither reads a number
on stops the row, naming the frame: two such frames in a row are never the number that stopped changing. Both readings
are cleaned alike (every dash a minus sign) and compared by key ("+2" and "2", "±0" and "0", "80%" and "80" one
number; pass2_report's scale_clean and scale_key), the labels kept as first read. A number only the reader read never
decides alone, for the reader can read the next number (kit/pass2_report.py, name_of), and no end of the scale stands
on two equal readings alone: every end, whoever read it, is confirmed by one more press (a press the camera drops
reads as an end, 2026-11-10), and the high end also by Left from it; a press that seems to leave the number as it was
is read again on a fresh frame (cam.refresh, no press). A number read twice in the look, whole numbers that do not
step evenly (every scale the kit has met counts in whole numbers, evenly; decimals are not judged), a look of one
value (a scale has two at least), or a held number the reader read away from where the Left presses counted it, stops
the row. A choice must open on the value chosen last (the value held, first), whoever reads it, and counts its presses
from there: a number OCR reads elsewhere, or one the reader alone read on the frame before OK, stops the row, the
screen closed with nothing chosen. A row's lines carry one attempt (as kit/prove_run.py's), recorded finished
(proving.base.finish_attempt) only once the value put back last leaves nothing changed, so kit/pass2_report.py counts
none of a row that stopped. A never-open row (a volume, the sound rows) is skipped unless the owner allowed it and the
run names it: --allow "Playback/Monitor. Vol." (repeatable, as drive.py's --allow: only the rows named open, never the
cards, Initialize, Reset Network Set. or credentials). The run prints the rows allowed, and every proof line carries
"allowance": "the owner allowed <row> remotely, <date>". First a look: Left until the number stops changing, then
Right until it stops (the scale's ends, in order), MENU. Then, as kit/prove_run.py does: each value against the start,
the one held last; every choice is the row, Right, Left/Right until the number is read, OK, a settings download.
Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl (kind "list", labelled with the numbers); the start file goes
back on at the end and is checked.
"""
import argparse
import itertools
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, match, ocr, safety  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.vlm import PROMPTS  # noqa: E402
from crawl_run import go_to  # noqa: E402
# a scale's number cleaned and keyed as the report counts a scale line's readers by them (pass2_report.name_of)
from pass2_report import scale_clean as clean, scale_key as key  # noqa: E402
from prove_run import LOCK_S, Failed, enter_any, held_value, option_key, to_shooting  # noqa: E402
from proving.base import finish_attempt  # noqa: E402
from proving.screens import ask_second, option_answer  # noqa: E402
from runner import (add_allow_argument, add_scan_argument, allowed_or_exit, changes_of, close_screen, load_scan, menu_from_shooting,  # noqa: E402
                    proofs_file, prover_session, read_json, scan_position)

TITLE = (0, 0, 640, 52)
# the number between the ◂ ▸: measured on three scales, and down to 345 for Finder Color Temp.'s, drawn lower
# (kit2_hdmi_watch 02372_seen.png, centred near y 328; nothing else on a scale screen is inside it)
VALUE = (250, 265, 390, 345)
FOOTER = (0, 425, 640, 480)
NUMBER = re.compile(r"[+-]?\d{1,3}(?:\.\d+|%)?")    # a scale's number, cleaned: 3, +2, -1, 0.5, 80%
# A panel (--panel-row): a setup row first, its option at the right, the slider below it (Monitor Brightness and
# Viewfinder Bright.: Brightness Setup, then the slider, which is there only on Manual; kit2_small_1109 00346-00348 and
# kit2_hdmi_watch 02355-02367, over HDMI and over the camera's own display image alike)
PANEL_SETUP = (400, 70, 640, 130)     # the setup row's option, at its right
PANEL_NEEDS = "Manual"                # the option under which the panel shows its slider
PANEL_VALUE = (250, 140, 390, 200)    # the slider's number in a panel, centred near y 168

_said: dict = {}            # {frame path: the reader's whole answer}: one question a frame, however often it is read
_by_reader: set = set()     # the frames whose number the reader gave, OCR having read none
_number_box = VALUE         # where the row being proved draws its number: VALUE, or PANEL_VALUE (open_row sets it)


def text(cam, box) -> str:
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], box).strip()


def ocr_value(cam) -> str:
    """OCR's number: text centred near x 320 and digit-tall, so the ◂ beside it (read as "1", 19 px
    tall) and the tick marks ("3•") are left out (2026-10-30); cleaned (clean) and "" unless it is a number (NUMBER),
    as the reader's must be: a letter OCR reads for a digit ("O", "l") or a sign alone is no number, and the reader is
    asked. The scales' words ("Slow", "Fast" at the ends) stand beside the number, never in its place."""
    f = cam.frame
    lines = [ln for ln in ocr.read([f.path])[f.path] if ln.inside(_number_box) and ln.h >= 22
             and abs(ln.x + ln.w / 2 - 320) <= 45]
    v = clean(" ".join(ln.text for ln in lines))
    return v if NUMBER.fullmatch(v) else ""


def asked(cam):
    """The reader's whole answer about the option under the cursor on the frame on screen (proving.screens.
    option_answer: None when the reader fails), asked once a frame: a local reader takes seconds, and a frame is read
    before a press, after it and in loops. The same answer gives the second reading kept with a proof (choose)."""
    p = cam.frame.path
    if p not in _said:
        _said[p] = option_answer(cam)
    return _said[p]


def one_number(text) -> str:
    """The number `text` holds, cleaned as OCR's is (clean: "−1" is "-1", "±0" is "0", "+2" stays): "" when it holds
    none (a word, nothing) or more than one, or is no number once cleaned (NUMBER)."""
    v = clean(text)
    return v if len(re.findall(r"\d+(?:\.\d+)?", str(text or ""))) == 1 and NUMBER.fullmatch(v) else ""


def reader_said(answer) -> tuple:
    """(what the reader said of the number, as it wrote it, which a proof line keeps as its "vlm"; the number, cleaned,
    or "" for none) from its answer to the option question: "selected" (the item under the cursor), or "value" (the
    value shown with it) where "selected" holds no digit at all, a word or nothing (the stand-in reader put a scale's
    number in "value" with "selected" empty, 2026-11-10). Two numbers that differ (by key) are no reading, both kept
    ("selected X; value Y"); "selected" holding digits that are not one number is none; an answer that is no object
    (a reader that failed) is ("", "")."""
    if not isinstance(answer, dict):
        return "", ""
    sel, val = (("" if x is None or x is False else str(x)) for x in (answer.get("selected"), answer.get("value")))     # a bare 0 is a number
    a, b = one_number(sel), one_number(val)
    if a and b and key(a) != key(b):
        return f"selected {sel}; value {val}", ""
    if a or re.search(r"\d", sel):
        return sel, a
    if b:
        return val, b
    return sel or val, ""


def reader_value(cam) -> str:
    """The reader's number on the frame on screen (reader_said, cleaned as OCR's is): "" when its answer holds none."""
    v = reader_said(asked(cam))[1]
    if v:
        _by_reader.add(cam.frame.path)
    return v


def value(cam) -> str:
    """The number on the frame on screen: OCR's, else the reader's (2026-11-09); "" when neither reads one."""
    return ocr_value(cam) or reader_value(cam)


def read_by(cam) -> str:
    """Which gave the number on the frame on screen: "reader", or "ocr"."""
    return "reader" if cam.frame.path in _by_reader else "ocr"


def number(cam, link, path) -> str:
    """value(cam), never "": a frame neither OCR nor the reader reads a number on stops the row, its screen closed
    first and the frame named (2026-11-09: two empty readings in a row, at two different numbers, ended a look as if
    the number had stopped changing)."""
    v = value(cam)
    if v:
        return v
    frame = cam.frame.path.name
    close_screen(cam, link)
    raise Failed(f"{path[-1]}: no number read on the scale on frame {frame}, by OCR or the reader")


class Reading(NamedTuple):
    """The number on a frame (number()), the frame's name, and whether the reader alone read it (OCR read none)."""
    text: str
    frame: str
    by_reader: bool


def reading(cam, link, path) -> Reading:
    v = number(cam, link, path)
    return Reading(v, cam.frame.path.name, cam.frame.path in _by_reader)


def numeric(k: str) -> float | None:
    try:
        return float(k)
    except ValueError:
        return None


def rises(before: str, after: str, way: str) -> bool:
    """Whether a press `way` moved the number the way a scale goes: Right raises it, Left lowers it (on screen: a volume
    stored the other way round still counts up). True when either reading is no plain number (nothing to say)."""
    a, b = numeric(key(before)), numeric(key(after))
    return a is None or b is None or (b > a if way == "right" else b < a)


def steps_even(keys: list) -> bool:
    """Whole numbers the same step apart throughout, as every scale the kit has met counts (a volume, a speed, a
    brightness around ±0); True when they are not all whole numbers: decimals are not judged (a scale in thirds shows
    0.3, 0.7, 1.0, steps that differ by rounding alone)."""
    if not all(re.fullmatch(r"-?\d+", k) for k in keys):
        return True
    n = [int(k) for k in keys]
    return len({b - a for a, b in itertools.pairwise(n)}) <= 1


def pressed(cam, way: str, before: Reading, read) -> Reading:
    """The reading after one press `way`. Where the number reads as on `before`, one fresh frame, grabbed without a
    press (cam.refresh), is read before that is believed: a press the camera answered late leaves its first frame
    showing the number before, and would pass for a press that went nowhere (an end, or a press dropped)."""
    cam.press(way)
    now = read()
    if key(now.text) == key(before.text):
        cam.refresh(f"{way}-again")
        now = read()
    return now


def at_end(cam, link, path, way: str, before: Reading, now: Reading, read) -> Reading:
    """The reading on screen once the end is confirmed: `before` and `now`, one press `way` apart, read the same number
    (by key), so the scale seems at its end. One more press `way` (at an end a press does nothing) must read the same
    number again, whoever read them (2026-11-10: a press the camera dropped once read as an end, by OCR too, and a row
    finished on a short scale); another number stops the row, its screen closed, the three frames named. `read`: the
    look's reader."""
    again = pressed(cam, way, now, read)
    if key(again.text) == key(now.text):
        return again
    close_screen(cam, link)
    raise Failed(f"{path[-1]}: {before.text!r} ({before.frame}) and {now.text!r} ({now.frame}) read as the "
                 f"{'low' if way == 'left' else 'high'} end, but one more {way.title()} read {again.text!r} "
                 f"({again.frame}): a press went unanswered, or the readings disagree")


def reader_footer(cam):
    """The reader's answer about the frame on screen to the dialog question (camkit.vlm.PROMPTS["dialog"]: the title,
    the selected line, other values and "footer", the bottom bar's button labels); None when the reader fails."""
    try:
        return ask_second(cam.frame.path.read_bytes(), PROMPTS["dialog"], timeout=25)
    except Exception:
        return None


def reader_sees_ok(cam) -> bool | None:
    """Whether the reader reads an OK among the footer's button labels on the frame on screen (match.offers_ok on each):
    True; False for an answer whose footer holds none; None for a reader that failed or answered anything else."""
    said = reader_footer(cam)
    foot = said.get("footer") if isinstance(said, dict) else None
    foot = [foot] if isinstance(foot, str) else foot
    if not isinstance(foot, list):
        return None
    return any(match.offers_ok(x) for x in foot if isinstance(x, str))


def open_row(cam, cycle, model, path, panel=False):
    """From the shooting screen: MENU, the row, Right; the scale with the row's title, by OCR. A plain scale must not
    open as a panel or a submenu (the pixel reader's "submenu", a row lit): that stops the row. A panel (panel True,
    --panel-row) must show its setup row's option as PANEL_NEEDS, Manual (the slider is there only then; the --set the
    run must be given put it there before the rows, panel_set_refused), and Down goes from the setup row, lit on
    opening, to the slider.
    Then an OK in its footer: OCR's (match.offers_ok), on the frame or, where it reads none, on one fresh frame
    (cam.refresh, no press); where it reads none on either, the reader's, asked once about the fresh frame
    (reader_sees_ok). OCR dropped the OK of "MENU Cancel ●OK" on every frame of one number, 2026-11-10, and a row
    stopped on an open scale. A title not the row's, or a footer neither reads an OK in, stops the row, the message
    saying who was asked; then the number, read where the screen draws it (_number_box), as before. Nothing but Right
    and a panel's Down is pressed before all this holds."""
    global _number_box
    _number_box = PANEL_VALUE if panel else VALUE
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"could not reach {path[0]!r} by the scan")
    enter_any(cam, path, 0)
    cam.press("right")
    title, foot = text(cam, TITLE), text(cam, FOOTER)
    if option_key(path[-1]) in option_key(title):
        if not panel and cam.read().kind == "submenu":
            raise Failed(f"Right on {path[-1]!r} opened a panel or a submenu, not a scale ({cam.frame.path.name}): a "
                         "panel's slider is proved with --panel-row")
        if panel:
            # the option is the owner's: the message says only whether it reads PANEL_NEEDS
            if match.key(text(cam, PANEL_SETUP)) != match.key(PANEL_NEEDS):
                raise Failed(f"{path[-1]}: its panel's setup row does not read {PANEL_NEEDS} ({cam.frame.path.name}), or "
                             f"this is no panel: the slider is there only on {PANEL_NEEDS}, where the --set before the "
                             "rows should have left it")
            if cam.read().kind == "submenu":
                cam.press("down")                # from the setup row to the slider
            title, foot = text(cam, TITLE), text(cam, FOOTER)
    ok = match.offers_ok(foot)
    if option_key(path[-1]) in option_key(title) and not ok:
        first = cam.frame.path.name
        cam.refresh("scale-footer")
        title, foot = text(cam, TITLE), text(cam, FOOTER)
        ok = match.offers_ok(foot)
        if option_key(path[-1]) in option_key(title) and not ok:
            said, frame = reader_sees_ok(cam), cam.frame.path.name
            if not said:
                raise Failed(f"Right on {path[-1]!r} did not open its scale (title {title!r}, footer {foot!r}): OCR read "
                             f"no OK on {first} or {frame}, and the reader, asked about {frame}, "
                             + ("read none" if said is False else "gave no answer it could use"))
            ok = True
    if option_key(path[-1]) not in option_key(title) or not ok:
        raise Failed(f"Right on {path[-1]!r} did not open its scale (title {title!r}, footer {foot!r})")
    if not value(cam):
        raise Failed(f"{path[-1]}: no number read on the scale on frame {cam.frame.path.name}, by OCR or the reader")


def ends(cam, link, cycle, model, path, panel=False) -> tuple[list, str]:
    """(every value in Right order, as first read; the value held, as that list names it): Left to the low end, Right
    to the high end, MENU. Readings are compared by key, and a press that seems to leave the number as it was is read
    again on a fresh frame (pressed). Every end is confirmed by one more press (at_end), and the high end also by Left
    from it, which must read the number before it; after the low end each Right press that changed the number is one
    place further, so a number read a second time is a look gone wrong; whole numbers must step evenly (steps_even); a
    scale has two values at least; and a held number the reader alone read must stand as many places above the low end
    as Left presses changed the number. Each stops the row, its screen closed, the frames named where one is to
    blame."""
    def read() -> Reading:
        return reading(cam, link, path)
    open_row(cam, cycle, model, path, panel)
    held = prev = now = read()
    lefts = 0                                   # Left presses that changed the number: the held number's place
    for _ in range(30):
        now = pressed(cam, "left", prev, read)
        if key(now.text) == key(prev.text):
            now = at_end(cam, link, path, "left", prev, now, read)
            break
        lefts += 1
        prev = now
    vals = [prev.text]
    for _ in range(60):
        nxt = pressed(cam, "right", now, read)
        if key(nxt.text) == key(now.text):
            end = at_end(cam, link, path, "right", now, nxt, read)
            want = vals[-2] if len(vals) > 1 else vals[-1]      # the number before it, else a misread passed for the end
            back = pressed(cam, "left", end, read)
            if key(back.text) != key(want):
                close_screen(cam, link)
                raise Failed(f"{path[-1]}: {end.text!r} ({end.frame}) read as the high end, but Left from it read "
                             f"{back.text!r} ({back.frame}), not {want!r}: a press went unanswered, or the readings "
                             "disagree")
            break
        if key(nxt.text) in [key(v) for v in vals]:
            close_screen(cam, link)
            raise Failed(f"{path[-1]}: the look read {nxt.text!r} ({nxt.frame}) {len(vals)} places above the low end, "
                         f"where it had read it {[key(v) for v in vals].index(key(nxt.text))} places above: the "
                         "readings disagree")
        vals.append(nxt.text)
        now = nxt
    close_screen(cam, link)
    keys = [key(v) for v in vals]
    if len(vals) < 2:
        raise Failed(f"{path[-1]}: the look read one value only, {vals[0]!r} (frame {now.frame}), and a scale has two "
                     "at least: a press went unanswered, or the readings disagree")
    if key(held.text) not in keys or len(set(keys)) != len(keys):
        raise Failed(f"{path[-1]}: the look read {vals} with {held.text!r} held")
    if not steps_even(keys):
        raise Failed(f"{path[-1]}: the look read {vals}, whole numbers stepping unevenly: a number misread")
    if not all(rises(a, b, "right") for a, b in itertools.pairwise(vals)):
        raise Failed(f"{path[-1]}: the look read {vals}, the number falling on Right: a scale counts up to the right, "
                     "so a number or its sign was misread")
    h = keys.index(key(held.text))
    if held.by_reader and h != lefts:
        raise Failed(f"{path[-1]}: the reader read {held.text!r} held ({held.frame}), {h} places above the low end, but "
                     f"{lefts} Left presses changed the number on the way there: the readings disagree")
    return vals, vals[h]


def choose(cam, link, hdmi, cycle, model, path, vals, target, start=None, panel=False) -> dict:
    """The scale's value vals[target] chosen and downloaded: the row, Left/Right until the number reads it (by key), OK,
    the download after it. With a `start` (the index the scale should open on: the value held, then each value chosen
    before, main), the number on the frame the scale opens on must be that one, whoever read it, or the row stops (the
    screen closed, nothing chosen): a fresh look at what the last OK left. Every press is counted from there, a press
    at an end going nowhere, and so is one OCR saw leave the number as it was even on a fresh frame (pressed: a press
    the camera dropped, and the walk presses again); with a place so known, a number OCR reads elsewhere stops the row.
    With no `start`, the first number read sets the place, and OCR's, once read, makes it known. When the number on
    the frame before OK is one the reader alone read, the count must put the scale on `target` too, or the screen is
    closed, nothing chosen, and the row stops."""
    open_row(cam, cycle, model, path, panel)
    keys = [key(v) for v in vals]
    place, known = start, start is not None     # where the presses put the scale; known: counted from a known place
    now, was, way, presses = reading(cam, link, path), None, None, 0    # was, way: the reading before the last press
    while True:
        k = key(now.text)
        if k not in keys:
            if presses > len(vals):
                break
            raise Failed(f"{path[-1]}: read {now.text!r}, not one of the scale's values")
        if was is not None and k != key(was.text) and not rises(was.text, now.text, way):
            close_screen(cam, link)
            raise Failed(f"{path[-1]}: {way.title()} moved the number the wrong way ({was.frame} to {now.frame}): a "
                         "scale counts up to the right, so a number or its sign was misread; no OK")
        if was is not None and (was.by_reader or now.by_reader or k != key(was.text)):
            place = min(place + 1, len(vals) - 1) if way == "right" else max(place - 1, 0)
        if presses == 0 and known and keys.index(k) != place:
            close_screen(cam, link)
            raise Failed(f"{path[-1]}: the scale opened on {now.text!r} (frame {now.frame}, read by "
                         f"{'the reader' if now.by_reader else 'OCR'}), not on {vals[place]!r}, the value last chosen: "
                         "the last OK did not take, or the readings disagree; no OK")
        if not now.by_reader:
            if known and keys.index(k) != place:
                close_screen(cam, link)
                raise Failed(f"{path[-1]}: OCR read {now.text!r} on frame {now.frame}, but the presses counted put the "
                             f"scale on {vals[place]!r}: the readings disagree, no OK")
            place, known = keys.index(k), True
        elif place is None:
            place = keys.index(k)               # the first number read, the reader's: a place, not a known one
        if k == keys[target] or presses > len(vals):
            break
        way, was = ("right" if keys.index(k) < target else "left"), now
        now = pressed(cam, way, was, lambda: reading(cam, link, path))
        presses += 1
    if k != keys[target]:
        raise Failed(f"{path[-1]}: {vals[target]!r} never came up")
    if now.by_reader and place != target:
        close_screen(cam, link)
        raise Failed(f"{path[-1]}: the reader read {now.text!r} on frame {now.frame}, but the presses counted put the "
                     f"scale on {vals[place]!r}: the readings disagree, no OK")
    full = text(cam, (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"{path[-1]}: the screen reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, by, seen_vlm = cam.frame.path.name, read_by(cam), reader_said(asked(cam))[0]   # the reader's, kept
    cam.press("enter")
    after_ok = cam.frame.path.name
    to_shooting(link, hdmi, "the download after OK")
    time.sleep(1)
    dat = link.download(f"{path[-1]}-{target}")
    time.sleep(LOCK_S)
    return {"chosen_frame": chosen, "row_frame": after_ok, "dat": dat, "vlm": seen_vlm, "read_by": by}


def labels_of(vals: list) -> list:
    """The labels a scale's proof lines carry, one for each value of the look (vals, as first read): as read, except on
    a scale with negative numbers, which the camera writes around zero with a sign on every number and ±0 for zero
    (the definition's own: -2, -1, ±0, +1, +2), however OCR spelled it ("‡0", "+0", "+-0", "0") and whoever read it. A
    sign is never guessed: the walk compares by key, where "1" is "+1", and a "1" read for -1 meets +1 in the look (a
    number read twice) or the count of presses in a choice, and stops the row."""
    keys = [key(v) for v in vals]
    if not any(k.startswith("-") for k in keys):
        return list(vals)
    return ["±0" if k == "0" else k if k.startswith("-") else f"+{k}" for k in keys]


def parse_set(item: str, allowed) -> tuple:
    """(path, option) of a --set "ROW=OPTION" ("Viewfinder Bright. > Brightness Setup=Manual"); the run ends before
    anything connects when it is not of that form, when the row is never-open and not allowed (as a --row, its own
    --allow word), or when it is the camera's identity, a connection or its region (decision 8: safety.identity_row),
    which no --allow lets a run set."""
    row, eq, option = item.partition("=")
    path, option = [x.strip() for x in row.split(" > ")], option.strip()
    if not eq or not option or not all(path):
        sys.exit(f"--set {item!r}: ROW=OPTION, ' > ' between submenus (\"Viewfinder Bright. > Brightness Setup=Manual\")")
    for label in path:
        if safety.identity_row(label):
            sys.exit(f"--set {item!r}: {safety.identity_row(label)}")
    why = safety.path_refused(path, allowed=allowed)
    if why:
        sys.exit(f"--set {item!r}: never-open ({why}); --allow with its label is the owner's word for it")
    return path, option


def setup_rows_named(panel: list, index: dict) -> list:
    """The labels the definition gives the setup row of the panel whose menu path is `panel` (index: its settings by
    key): its settings whose menu row is that path and one label more, with PANEL_NEEDS among their values (the a1 II's
    Monitor Brightness > Brightness Setup); sorted, each once. The definition's own words: no body's label is written
    here."""
    want = [match.key(x) for x in panel]
    out = set()
    for s in index.values():
        row = s.get("row") or []
        if len(row) == len(panel) + 1 and [match.key(x) for x in row[:-1]] == want and \
                any(match.key(lab) == match.key(PANEL_NEEDS) for _, lab in s.get("values") or []):
            out.add(str(row[-1]))
    return sorted(out)


def panel_set_refused(rows: list, sets: list, index: dict | None = None) -> str:
    """Why the run may not start, or "": every --panel-row's panel must have its setup row among the --set rows (a row
    one level inside the panel, "ROW > SETUP") on PANEL_NEEDS, so the run puts it there through the menu and every
    proof's context names it; a proof made on the option the camera stood on would tell it (decision 16). The refusal
    gives the exact --set to add, the setup row's label from the definition (setup_rows_named; index: its settings by
    key, read when needed and not given), or the --set's form where the definition names no one label."""
    for row, panel in rows:
        if not panel:
            continue
        inside = [option for path, option in sets if len(path) > 1 and " > ".join(path[:-1]) == row]
        if any(match.key(option) == match.key(PANEL_NEEDS) for option in inside):
            continue
        if inside:
            return (f"--panel-row {row!r}: its panel's setup row is set to {inside[-1]!r}, not {PANEL_NEEDS}: the slider "
                    f"is there only on {PANEL_NEEDS}")
        if index is None:
            try:
                index = definition_index()
            except Exception:                   # no definition named: the --set's form, without the label
                index = {}
        labels = setup_rows_named(row.split(" > "), index)
        add = f'--set "{row} > {labels[0] if len(labels) == 1 else "<its setup row>"}={PANEL_NEEDS}"'
        known = "" if len(labels) == 1 else (
            f" (the definition names {'no' if not labels else 'more than one'} setup row with {PANEL_NEEDS} among its "
            f"values inside {row!r}{': ' + ', '.join(labels) if labels else ''})")
        return (f"--panel-row {row!r}: its panel's setup row must be set to {PANEL_NEEDS} through the menu before the "
                f"rows, so every proof's context names it (docs/decisions/0016): add {add}{known}")
    return ""


def state_of(sets: list) -> str:
    """The --set rows as a proof's context names them, in the order given ("Select Finder/Monitor = VF(Manual)")."""
    return ", ".join(f"{' > '.join(path)} = {option}" for path, option in sets)


def definition_index() -> dict:
    """The active definition's settings by key, for setting_code."""
    p = definitions.active()
    return {s["key"]: s for s in definitions.with_evidence(read_json(p), p).get("settings") or []}


def setup(cam, link, hdmi, cycle, model, start, sets, panels=frozenset()) -> Path:
    """Each --set row put on its option through the menu, in the order given, by kit/provers/afreg_run.py's
    set_setup_row (mode_switch.set_row: the row by the scan, each submenu or panel of "A > B" opened with Right and its
    row found, Right on the row, a list expected, the option found by the list bar's text, OK; a notice after OK kept
    in the run's events and never said; a failure said without the option the list was on, which can be the owner's).
    A row inside one of this run's panels (`panels`: the --panel-row rows) must then read the option asked for on the
    panel OK brought back; a submenu's row is not judged so (its page shows its first row's value where a panel shows
    its setup option, kit2_pass2 145809_menu.png). Then a download: the base every choice is compared with, so a set
    row's records are no scale value's; in it each set row's record must hold the option's code, where the definition
    names both (framepos_run.setting_code), else the run stops; where it names neither, the run says the set is not
    verified in the file and goes on. Only the count of records that differ from the start file is printed, never what
    a screen or a record held; a step that fails stops the run before any row."""
    from afreg_run import set_setup_row
    from framepos_run import setting_code
    from mode_switch import open_menu
    for path, option in sets:
        open_menu(cam)
        set_setup_row(cam, cycle, model, path, option)
        if " > ".join(path[:-1]) in panels and option_key(path[0]) in option_key(text(cam, TITLE)) and \
                match.key(text(cam, PANEL_SETUP)) != match.key(option):
            # back in the panel: its setup row must read the option asked for (open_row's check); what it reads
            # instead is the owner's, never said
            frame = cam.frame.path.name
            close_screen(cam, link)
            raise Failed(f"{' > '.join(path)}: after OK the panel's setup row does not read {option} ({frame})")
        close_screen(cam, link)
        time.sleep(1.0)
    to_shooting(link, hdmi, "the download after the settings")
    time.sleep(1)
    base = link.download("after-set")
    after, index = camset.read(base), definition_index()
    for path, option in sets:
        got = setting_code(index, path, option)
        if got is None:
            print(f"{' > '.join(path)} = {option}: not verified in the file (the definition names no record and code "
                  "for it)", flush=True)
        elif held_value(after, got[0]) != got[1]:
            raise Failed(f"{' > '.join(path)}: the file after the setting does not hold {option} ({got[0]})")
    n = len(camset.diff(camset.read(start), after))
    print(f"set through the menu: {state_of(sets)}; {n} records now differ from the start file (the restore puts them "
          "back)", flush=True)
    time.sleep(LOCK_S)
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", dest="rows", action="append", type=lambda r: (r, False), default=[],
                    help="a plain scale row's path, ' > ' between submenus (repeatable, in the order given)")
    ap.add_argument("--panel-row", dest="rows", action="append", type=lambda r: (r, True),
                    help="a panel's row (its setup row first, which must read Manual, then the slider: Monitor "
                         "Brightness, Viewfinder Bright.), proved as a scale, in the order given among the --row; its "
                         "setup row must be among the --set rows, on Manual ('ROW > SETUP=Manual')")
    ap.add_argument("--set", action="append", default=[], metavar="ROW=OPTION",
                    help="before the first row, put ROW on OPTION through the menu (repeatable, in the order given; "
                         "'A > B=OPTION' for a submenu's or a panel's row); the proofs' context names it")
    ap.add_argument("--context", default=None, help="the state these proofs are made in (e.g. Movie mode)")
    add_scan_argument(ap)
    add_allow_argument(ap)
    a = ap.parse_args()
    if not a.rows:
        ap.error("--row or --panel-row: at least one")
    sets = [parse_set(item, a.allow) for item in a.set]
    why = panel_set_refused(a.rows, sets)
    if why:
        sys.exit(why)
    allowance = allowed_or_exit(a.allow)
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    hdmi = eyes_from_config(run)
    extra = {"allowance": allowance} if allowance else None
    context = ", ".join(x for x in (state_of(sets), a.context) if x) or None
    with proofs_file(run, context, extra) as out, prover_session(run, hdmi, may_open=a.allow) as s:
        cam, link, start = s.cam, s.link, s.start
        panels = {row for row, panel in a.rows if panel}
        base = setup(cam, link, hdmi, cycle, model, start, sets, panels) if sets else start
        for row, panel in a.rows:
            path = row.split(" > ")
            if safety.path_refused(path, allowed=a.allow):
                print(f"{row}: never-open, skipped", flush=True)
                continue
            attempt = f"{run.dir.name}-{time.time_ns():x}"     # the row's lines, counted once it finishes
            try:
                vals, held = ends(cam, link, cycle, model, path, panel)
                print(f"{row}: {vals}, held {held!r}", flush=True)
                h, labels = vals.index(held), labels_of(vals)
                at = h                      # where the scale stands when opened: the value held, then each chosen
                for i in [i for i in range(len(vals)) if i != h] + [h]:
                    got = choose(cam, link, hdmi, cycle, model, path, vals, i, at, panel)
                    at = i
                    ch = camset.diff(camset.read(base), camset.read(got["dat"]))
                    r = {"path": path, "kind": "list", "index": i, "label": labels[i], "shown": labels[i],
                         "chosen_frame": got["chosen_frame"], "row_frame": got["row_frame"],
                         "vlm": got["vlm"], "read_by": got["read_by"], "dat": got["dat"].name, "base": base.name,
                         "applied": True, "scale": True, "changes": changes_of(ch), "attempt": attempt}
                    out.write(json.dumps(r) + "\n")
                    out.flush()
                    print(f"  {labels[i]}: {len(ch)} records {[(c.key, c.before, c.after) for c in ch][:4]}", flush=True)
                    if i == h and ch:
                        raise Failed(f"{row}: back on {held!r}, {len(ch)} records still differ from the file the row "
                                     "started from")
                finish_attempt(run, attempt, row)    # the put-back's download is the start again: the lines count
            except Exception as e:
                print(f"{row} stopped: {type(e).__name__}: {e}", flush=True)
                close_screen(cam, link)
                break


if __name__ == "__main__":
    main()
