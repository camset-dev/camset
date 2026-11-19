"""Prove a carousel option's own fields, one value a download: the a1 II's Bracket Type (Shooting > Drive Mode > Bracket
Settings > Bracket Type, open only with the drive mode dial on BRK), whose Cont. Bracket and Single Bracket draw
Exposure Value and Number of Shots under the title, and Focus Bracket Step Width and Number of Shots in three digit
boxes (2026-11-19).

    CAMSET_EYES=osd .venv/bin/python -u kit/provers/carousel_fields_run.py --scan SCAN --map kit2_fin_crawl_brk/map.json \\
        --row "Bracket Settings > Bracket Type" --option "Cont. Bracket" --context "Drive Mode dial on BRK" --look
    (the same without --look; --box N proves the N-th box alone, counted from 0; --most N, the deadline)

The screen (camkit.screen's dialog with a lit field): Up and Down move between the carousel's options, Right on the lit
option goes into its boxes (the first lit, filled orange, its field's name written above the row, the option's icon in
the strip turned white), Right again to the next box, Up and Down step the lit box, MENU in the boxes goes back to the
lit option with the carousel still open, Enter in the boxes chooses the option with what its boxes hold. Right is never
pressed on the last box (what it does there was never seen), nor anything but MENU on a screen that stopped reading as
expected.

First a look, read only: the option lit (its title read against the map's options), Right into its boxes and through
every one, each box's value read while it is lit and its field's name above it, then MENU twice, nothing chosen. Boxes
side by side under one name are one field (Focus Bracket's three digits: the number they make). With --look the run
ends there. Then a base: the option chosen as its boxes stand (Enter on the option), a download every proof is compared
with, so the option's own record (Bracket Type's) moves there and never in a proof. Then each box in turn (--box: one):
from the value it holds, Up one value at a time until it comes round to that value or stops (a press that changes the
box's picture nothing, on a fresh frame too and one more press), then, where it stopped, Down from the value held the
same way; at most --most values each way (MOST, the deadline; the run says where it cut a walk short). Each value is
one visit: the row, the option, Right to the box, the box checked on the value the last OK chose, the keys to the next
value (each step through a value already seen checked against its picture), the value read, Enter, a download, a proof
line. The value held is proved last, put back so, and its download must equal the base. The session's start file goes
back on at the end, as every prover's.

Readings, as kit/provers/optboxes_run.py reads its boxes: the lit box by OCR, the second reader asked about the lit box
itself on every doubt (camkit.reading.doubts) and always where the value decides a proof (the owner's rule: the reader is
asked before a row fails), OCR plain and the reader apart stopping the row; the field's name by OCR, the reader where it
is not plain Latin; the title by OCR against the map's options, the reader on a doubt. Whether a press moved the box is
told by its picture (white on orange, over 150 grey), which no reading decides. A value read the same as the one before while
the picture changed (two values the readers cannot tell apart), a value seen before that is not the one held, a reader
that does not answer where it must, a title not the option's, a box not lit where it should be: each stops the row
before the next key, MENU out, the start file put back by the session.

Proof lines go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl with --context: path the row's and the option's, kind
"list", "via" VIA, "index" [box, place] (the place counted from the value held, Up positive), "field" the field's name
as drawn ("Exposure Value"), "value" that field's value after the change as drawn ("0.5EV"; a digit field's number),
"fields" every field as drawn after it ([{"label", "value"}]), "label" all of them together (two fields of a step and a
count in the words of the definition's Drive Mode bracket lists, "0.5 EV 3 Img.", as kit/provers/bracket_run.py forms
them; any other, the fields' values joined " | "), "box" and "read_by" the lit box's reading and who gave it ("ocr",
"both", "reader"), "shown" OCR's reading of it, "box_vlm" and "box_reader" the second reader's and its name, "final" on
the put-back and with it "whole" (False where the deadline cut the walk short), "attempt", "changes".
kit/pass2_report.py credits a record moved by the lines of two fields or more with "label", a record only one field's
lines moved with that field's "value"; a put-back's value only where its walk was whole, as the value held would stand
out among a part walk's (docs/decisions/0016).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, paths, reading, screen  # noqa: E402
import numpy as np  # noqa: E402  (after camkit, which says what to run where the kit's packages are missing)
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from boxes_run import EXIT_REFUSED, PROOF_RUN, lines, stop_status  # noqa: E402
from bracket_run import images_of, label as bracket_label, step_of  # noqa: E402
from crawl_run import go_to  # noqa: E402
from optboxes_run import RETRY_WAIT, clean_name  # noqa: E402
from prove_run import Failed, enter_any, main_name, option_key, to_shooting  # noqa: E402
from proving.base import finish_attempt, wait_lock  # noqa: E402
from proving.commit import after_ok  # noqa: E402
from proving.screens import box_answer, carousel_text, place, same_place, vlm_option, word_answer  # noqa: E402
from runner import (add_scan_argument, changes_of, close_screen, load_scan, menu_from_shooting, proofs_file,  # noqa: E402
                    prover_session, read_json, scan_position)

VIA = "a carousel option's own fields"      # kit/pass2_report.py reads these lines by it (OPTION_FIELDS)
MOST = 12                                   # values a walk proves each way at most (--most)
WORD = (100, 280, 640, 342)                 # where the camera writes the lit box's field name (camkit.live.BOX_WORD)
PIC_TOL = 20                                # pixels two pictures of one box value may differ by (OSD frames: none)


class Look(NamedTuple):
    """The option's boxes as the look read them: each box's field name, its value, and the fields they make."""
    labels: list
    values: list

    def fields(self, values=None) -> list:
        return fields_of(self.labels, self.values if values is None else values)


def fields_of(labels: list, values: list) -> list:
    """[{"label", "value"}]: the boxes side by side under one name are one field, its value the boxes' values together:
    digits alone make the number they write ("0", "0", "3" is "3"), anything else is joined by spaces."""
    out = []
    for lab, v in zip(labels, values, strict=True):
        if out and out[-1]["label"] == lab:
            out[-1]["boxes"].append(v)
        else:
            out.append({"label": lab, "boxes": [v]})
    for f in out:
        boxes = f.pop("boxes")
        digits = all(re.fullmatch(r"\d", str(b)) for b in boxes)
        f["value"] = str(int("".join(boxes))) if digits and len(boxes) > 1 else " ".join(map(str, boxes))
    return out


def together(fields: list) -> str:
    """The fields' values as one label: a step and a count (bracket_run.step_of, images_of) in the words of the
    definition's Drive Mode bracket lists ("0.5 EV 3 Img.", "0.3 EV 2 Img. +": bracket_run.label), else the values as
    drawn, joined " | " ("4(Standard) | 3"). Nothing the camera did not draw is added."""
    if len(fields) == 2:
        st, n = step_of(fields[0]["value"]), images_of(fields[1]["value"])
        if st is not None and n is not None:
            return bracket_label(st, n)
    return " | ".join(f["value"] for f in fields)


def key(text) -> str:
    """Two readings of one value compared: the digits, points and signs it holds, in order ("0.5EV" 0.5, "5 Images" 5,
    "2 Images +" 2+), its canonical form first (look-alike letters, every dash a hyphen); the whole reading, case and
    spacing aside, where it holds no digit. The words beside a number are its field's own (EV, Images, Standard), and
    OCR drops their letters ("5 mages" on kit2_fin_brtype_cont_img 00008_up.png), never a digit's place."""
    t = reading.canonical(text)
    nums = re.sub(r"[^0-9.+\-]", "", t)
    return nums if re.search(r"\d", nums) else re.sub(r"\s+", "", t).casefold()


# ------------------------------------------------------------------------------------------------ the screen

class BoxRead(NamedTuple):
    """One reading of the lit box (lit_read): the value taken, OCR's reading as read, the second reader's (None: not
    asked), the reader that answered, and which gave the value ("ocr", "both", "reader")."""
    text: str
    ocr: str
    vlm: str | None = None
    reader: str | None = None
    by: str = "ocr"


def title_reads(cam, labels: list) -> str | None:
    """The carousel option the title names, one of the map's `labels`: OCR's orange line (proving.screens.carousel_text)
    where it names one plainly (camkit.reading: no doubt, one option named), else the second reader's (vlm_option);
    None where neither names one."""
    t = carousel_text(cam)
    i = reading.choice_of(t, "label", labels)
    if i is None or reading.doubts(t, "label", choices=labels):
        v = vlm_option(cam)
        i = reading.choice_of(v, "label", labels) if v else None
    return labels[i] if i is not None else None


def is_option(name: str | None, option: str) -> bool:
    return name is not None and option_key(main_name(name, "dialog")) == option_key(main_name(option, "dialog"))


def option_refused(cam, option: str, labels: list) -> str:
    """Why the frame on show is not the carousel with `option` itself lit, or "": the pixel reader's dialog with no
    field lit, its title naming the option."""
    s = cam.read()
    if s.kind != "dialog":
        return f"the screen reads as {s.kind}, not the carousel"
    if getattr(s, "field", None) is not None:
        return f"box {s.field} is lit, not the option"
    named = title_reads(cam, labels)
    return "" if is_option(named, option) else f"its title names {named!r}, not {option!r}"


def box_refused(cam, option: str, labels: list, b: int, count: int | None) -> str:
    """Why the frame on show is not `option`'s box b lit (of `count` boxes, where known), or "": the pixel reader's
    dialog with box b the lit one, as many boxes as before; the title read only where asked (`labels`)."""
    s = cam.read()
    if s.kind != "dialog":
        return f"the screen reads as {s.kind}, not the carousel"
    if getattr(s, "field", None) != b:
        return f"box {getattr(s, 'field', None)} is lit, not box {b}"
    if count is not None and len(s.boxes) != count:
        return f"{len(s.boxes)} boxes are drawn, not {count}"
    if labels and not is_option(title_reads(cam, labels), option):
        return f"its title no longer names {option!r}"
    return ""


def lit_box(cam) -> tuple:
    """(x0, y0, x1, y1) of the lit box's inside, as the pixel reader found it."""
    s = cam.read()
    x0, x1 = s.boxes[s.field]
    return x0 + 3, s.bar[0] + 3, x1 - 3, s.bar[1] - 3


def ask_box(cam) -> tuple:
    """The second reader's (value, name) about the lit box (proving.screens.box_answer, PROMPTS["box"]), asked once more
    after RETRY_WAIT where it does not answer; the value None after both."""
    said, who, _ = box_answer(cam)
    if said is None:
        time.sleep(RETRY_WAIT)
        said, who, _ = box_answer(cam)
    return said, who


def lit_read(cam, always: bool) -> BoxRead:
    """The lit box's value, as optboxes_run reads its boxes: OCR's reading (boxes_run.lines) stands alone where it is
    plain (camkit.reading.doubts, a number: four characters or more, no look-alike) and `always` is False. Otherwise,
    and always where `always` (a new value, the value held, a value Enter goes on: each decides a proof), the second
    reader is asked about the lit box itself (ask_box): where OCR was unsure, its reading is taken (the owner's rule,
    2026-11-06: the reader is right where OCR drops or mangles short digits, and it is asked before a row fails); where
    OCR was plain, both must hold the same number (key), and the reader's words are kept, OCR dropping letters of them.
    A reader that does not answer where it must, or two numbers apart, stop the row: the kit does not guess."""
    frame = cam.frame.path.name
    raw = ocr.text_in(lines(cam), lit_box(cam)).strip()
    doubted = reading.doubts(raw, "number", lit=True)
    if not doubted and not always:
        return BoxRead(reading.canonical(raw), raw)
    said, who = ask_box(cam)
    if said is None:
        raise Failed(f"the lit box on {frame}: OCR read {raw!r}{' (unsure)' if doubted else ''}, and the second reader "
                     f"did not answer (asked twice, {RETRY_WAIT:g} s apart): the kit does not guess a value; check the "
                     "reader (kit/tools/reader_check.py)")
    said = " ".join(str(said).split())
    if doubted:
        return BoxRead(reading.canonical(said), raw, said, who, "reader")
    if key(raw) != key(said):
        raise Failed(f"the lit box on {frame}: OCR read {raw!r} and the second reader {said!r}: the kit does not guess "
                     "which")
    return BoxRead(reading.canonical(said), raw, said, who, "both")


def word_read(cam) -> str:
    """The field name written above the lit box: OCR's (boxes_run.lines) where it is plain Latin words (optboxes_run's
    clean_name), else the second reader's (proving.screens.word_answer, PROMPTS["box_word"]); Failed where neither is."""
    raw = ocr.text_in(lines(cam), WORD).strip()
    got = clean_name(raw)
    if got and not reading.doubts(raw, "label"):
        return got
    said, _, _ = word_answer(cam)
    got = clean_name(said)
    if not got:
        raise Failed(f"the name above the lit box on {cam.frame.path.name} reads {raw!r} to OCR and {said!r} to the "
                     "second reader: not a name in plain Latin letters")
    return got


def box_pic(cam, b: int):
    """Box b's picture (its inside, light over 150 grey: white digits on orange, or on black unlit), which tells whether
    a press moved it with no reading; None where box b is not drawn."""
    s = cam.read()
    if s.bar is None or b >= len(s.boxes):
        return None
    x0, x1 = s.boxes[b]
    return screen._grey(cam.frame.image)[s.bar[0] + 6:s.bar[1] - 5, x0 + 4:x1 - 3] > 150


def same_pic(a, b) -> bool:
    return a is not None and b is not None and a.shape == b.shape and int(np.count_nonzero(a != b)) <= PIC_TOL


# ------------------------------------------------------------------------------------------------ the way there

def open_row(cam, cycle, model, path: list) -> tuple:
    """From the shooting screen: MENU, the row by the scan (its submenus by path), its place noted, Right; the
    carousel expected. Returns the row's place (proving.screens.place), what after_ok's back() is judged by."""
    menu_from_shooting(cam)
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"could not reach {path[0]!r} by the scan")
    if len(path) > 1:
        enter_any(cam, path, 0)
    row = place(cam)
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"Right on {path[-1]!r} opened {cam.read().kind}, not its carousel")
    return row


def to_option(cam, option: str, labels: list) -> None:
    """Down the carousel's options until `option` itself is lit (option_refused), at most once round."""
    for _ in range(len(labels) + 1):
        if not option_refused(cam, option, labels):
            return
        if cam.read().kind != "dialog" or getattr(cam.read(), "field", None) is not None:
            raise Failed(f"{option}: {option_refused(cam, option, labels)} ({cam.frame.path.name})")
        cam.press("down")
    raise Failed(f"{option} never came up in the carousel ({option_refused(cam, option, labels)})")


def into_box(cam, option: str, labels: list, b: int, count: int | None) -> None:
    """From the option lit: Right into its boxes, then Right to box b. The frame before the first Right must be the
    option itself lit (option_refused), the frame before each further Right box b - 1 lit with a box after it: never a
    Right on the last box. Each frame after a Right must read as the box meant (box_refused)."""
    why = option_refused(cam, option, labels)
    if why:
        raise Failed(f"{option}: no Right into its boxes: {why} ({cam.frame.path.name})")
    cam.press("right")
    why = box_refused(cam, option, labels, 0, count)
    if why:
        raise Failed(f"{option}: Right on the option did not light its first box: {why} ({cam.frame.path.name})")
    for k in range(1, b + 1):
        s = cam.read()
        if getattr(s, "field", None) != k - 1 or k >= len(s.boxes):
            raise Failed(f"{option}: no Right to box {k}: box {getattr(s, 'field', None)} of {len(s.boxes)} is lit "
                         f"({cam.frame.path.name})")
        cam.press("right")
        why = box_refused(cam, option, [], k, count)
        if why:
            raise Failed(f"{option}: Right did not light box {k}: {why} ({cam.frame.path.name})")


def step(cam, option: str, b: int, count: int, way: str) -> None:
    """Up or Down on box b, which must be lit before (box_refused) and after."""
    why = box_refused(cam, option, [], b, count)
    if why:
        raise Failed(f"{option}: no {way.title()}: {why} ({cam.frame.path.name})")
    cam.press(way)
    why = box_refused(cam, option, [], b, count)
    if why:
        raise Failed(f"{option}: after {way.title()} on box {b}: {why} ({cam.frame.path.name})")


def enter(cam, option: str, labels: list, b: int | None, count: int | None, want: str | None) -> None:
    """Enter on this row's option itself (b None) or on its box b reading `want`: judged first (option_refused,
    box_refused with the title read), then by the camera's own Enter guard (LiveCamera)."""
    why = option_refused(cam, option, labels) if b is None else box_refused(cam, option, labels, b, count)
    if not why and b is not None and key(lit_read(cam, False).text) != key(want):
        why = f"box {b} no longer reads {want!r}"
    if why:
        raise Failed(f"{option}: no Enter: {why} ({cam.frame.path.name})")
    cam.press("enter")


# ------------------------------------------------------------------------------------------------ the look and the walk

def look(cam, link, cycle, model, path, option, labels) -> Look:
    """The read-only look (the module's): every box's field name and value, read while it is lit; MENU twice."""
    open_row(cam, cycle, model, path)
    to_option(cam, option, labels)
    into_box(cam, option, labels, 0, None)
    count = len(cam.read().boxes)
    names, values = [], []
    for k in range(count):
        if k:
            into_next(cam, option, k, count)
        names.append(word_read(cam))
        values.append(lit_read(cam, True).text)
    close_screen(cam, link)                 # MENU: back to the option, MENU again: the carousel cancelled
    return Look(names, values)


def into_next(cam, option: str, k: int, count: int) -> None:
    """Right from box k - 1 to box k (never from the last box)."""
    s = cam.read()
    if getattr(s, "field", None) != k - 1 or k >= count:
        raise Failed(f"{option}: no Right to box {k} ({cam.frame.path.name})")
    cam.press("right")
    why = box_refused(cam, option, [], k, count)
    if why:
        raise Failed(f"{option}: Right did not light box {k}: {why} ({cam.frame.path.name})")


class Walk:
    """One box's walk: the values seen at each place (counted from the value held, Up positive), their pictures, where
    the box stands (the value the last OK left), and the ends found."""

    def __init__(self, held: str, pic):
        self.values, self.pics, self.pos = {0: held}, {0: pic}, 0
        self.cut = False                # the deadline cut a way short: the walk is not the field's whole list

    def known(self, text, pic) -> int | None:
        """The place of a value seen before, by its picture, else by its reading."""
        by_pic = [p for p, x in self.pics.items() if same_pic(x, pic)]
        if by_pic:
            return by_pic[0]
        return next((p for p, v in self.values.items() if text is not None and key(v) == key(text)), None)


def visit(cam, link, eyes, cycle, model, path, option, labels, look_: Look, b, w: Walk, target, base, out,
          attempt) -> str:
    """One visit of box b towards place `target` (a new one beside the places seen, or 0, the value held); returns
    "proved" (a new value chosen and downloaded), "end" (the box stopped: nothing chosen, closed with MENU), "round"
    (the box came round to the value held, which was then chosen: the put-back) or "back" (the put-back)."""
    name = f"{' > '.join(path)} > {option}"
    count = len(look_.labels)
    row = open_row(cam, cycle, model, path)
    to_option(cam, option, labels)
    into_box(cam, option, labels, b, count)
    pic = box_pic(cam, b)
    if not same_pic(pic, w.pics[w.pos]) and key(lit_read(cam, False).text) != key(w.values[w.pos]):
        raise Failed(f"{name}: box {b} opened on {lit_read(cam, False).text!r}, not {w.values[w.pos]!r}, which the "
                     f"last OK chose ({cam.frame.path.name})")
    way = "up" if target > w.pos else "down"
    at = w.pos
    while at != target:
        before = box_pic(cam, b)
        step(cam, option, b, count, way)
        nxt = at + (1 if way == "up" else -1)
        now = box_pic(cam, b)
        if same_pic(now, before):                       # nothing moved: a late frame, or an end
            cam.refresh("field-again")
            now = box_pic(cam, b)
        if same_pic(now, before):
            step(cam, option, b, count, way)            # one more press: at an end it changes nothing either
            if not same_pic(box_pic(cam, b), before):
                raise Failed(f"{name}: box {b} stood still on one {way.title()} and moved on the next "
                             f"({cam.frame.path.name}): a press went unanswered; nothing chosen")
            if nxt in w.values:
                raise Failed(f"{name}: box {b} stopped at {w.values[at]!r}, where it had moved on before "
                             f"({cam.frame.path.name})")
            print(f"   box {b}: {w.values[at]!r} is its {'top' if way == 'up' else 'low'} end (one more "
                  f"{way.title()} changed nothing)", flush=True)
            close_screen(cam, link)
            return "end"
        if nxt in w.values:                             # a place seen before, on the way: its picture again
            if not same_pic(now, w.pics[nxt]) and key(lit_read(cam, False).text) != key(w.values[nxt]):
                raise Failed(f"{name}: box {b} reads {lit_read(cam, False).text!r} where it read "
                             f"{w.values[nxt]!r} before ({cam.frame.path.name})")
            at = nxt
            continue
        r = lit_read(cam, True)                      # a new place: what it holds decides the proof
        seen = w.known(r.text, now)
        if seen == 0 and same_pic(now, w.pics[0]):
            print(f"   box {b}: came round to {w.values[0]!r}, the value it held", flush=True)
            return keep(cam, link, eyes, path, option, labels, look_, b, w, 0, r, row, base, out, attempt, "round")
        if seen is not None:
            raise Failed(f"{name}: box {b} reads {r.text!r} ({cam.frame.path.name}), "
                         + ("as its picture before" if same_pic(now, w.pics.get(seen)) else "as read before")
                         + " at another place than the one it held: the readers cannot tell its values apart, or it "
                         "does not come round to the value held; nothing chosen")
        w.values[nxt], w.pics[nxt] = r.text, now
        return keep(cam, link, eyes, path, option, labels, look_, b, w, nxt, r, row, base, out, attempt, "proved")
    r = lit_read(cam, True)                          # back on the value held: the put-back
    if not same_pic(box_pic(cam, b), w.pics[0]) or key(r.text) != key(w.values[0]):
        raise Failed(f"{name}: box {b} reads {r.text!r}, not {w.values[0]!r}, the value it held "
                     f"({cam.frame.path.name}); nothing chosen")
    return keep(cam, link, eyes, path, option, labels, look_, b, w, 0, r, row, base, out, attempt, "back")


def other_values(cam, look_: Look, b: int, opened: dict) -> list:
    """Every box's value on the frame on show: box b's from its reading, the others as the look read them while their
    pictures stay as they were when its walk first opened it (`opened`: box -> picture); one that changed (a value the
    camera moved with box b) is read again by OCR where it reads it plainly (camkit.reading.doubts), or the row stops
    before Enter: no reader is asked about a box that is not lit."""
    s = cam.read()
    out = list(look_.values)
    for k in range(len(out)):
        if k == b or same_pic(box_pic(cam, k), opened.get(k)):
            continue
        x0, x1 = s.boxes[k]
        raw = ocr.text_in(lines(cam), (x0 + 3, s.bar[0] + 3, x1 - 3, s.bar[1] - 3)).strip()
        if not raw or reading.doubts(raw, "number", lit=True):
            raise Failed(f"box {k} changed with box {b}, and OCR reads it {raw!r}, not plainly ({cam.frame.path.name}); "
                         "nothing chosen")
        out[k] = reading.canonical(raw)
    return out


def keep(cam, link, eyes, path, option, labels, look_: Look, b, w: Walk, place_, r, row, base, out, attempt,
         what: str) -> str:
    """Box b's value at `place_` (read as `r`) chosen with Enter, the screen after it read (proving.commit.after_ok), a
    download, its diff against the base and the proof line. A value the camera refuses is written "applied": false and
    the box stays where it stood; the put-back ("round", "back") must change nothing."""
    name = f"{' > '.join(path)} > {option}"
    opened = KEEP_OPENED.get(b, {})
    values = other_values(cam, look_, b, opened)
    values[b] = r.text
    fields = look_.fields(values)
    field = next(f for f in fields if f["label"] == look_.labels[b])
    lab = together(fields)
    chosen = cam.frame.path.name
    enter(cam, option, labels, b, len(look_.labels), r.text)
    got = after_ok(cam, name, label=lab, back=lambda: same_place(place(cam), row), info=False)
    row_frame = cam.frame.path.name
    to_shooting(link, eyes, "the download after OK")
    dat = link.download(f"{path[-1]}-{b}-{place_}".replace(" ", "-"))
    wait_lock(time.monotonic(), eyes, clock=time)
    ch = camset.diff(camset.read(base), camset.read(dat))
    final = what in ("round", "back")
    rec = {"path": [*path, option], "kind": "list", "via": VIA, "index": [b, place_], "field": look_.labels[b],
           "value": field["value"], "label": lab, "fields": fields, "box": r.text, "read_by": r.by, "shown": r.ocr,
           "box_vlm": r.vlm, "box_reader": r.reader, "chosen_frame": chosen, "row_frame": row_frame,
           "dat": dat.name, "base": base.name, **({"notice": got.notice} if got.notice else {}), "applied": got.applied,
           "final": final, **({"whole": not w.cut} if final else {}), "attempt": attempt, "changes": changes_of(ch)}
    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.flush()
    print(f"   {look_.labels[b]} = {r.text!r} ({lab}): " + ("refused by the camera" if not got.applied else
          ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:4]) or "no change"), flush=True)
    if got.applied:
        w.pos = place_
    if final and ch:
        raise Failed(f"{name}: box {b} back on {r.text!r}, {len(ch)} records still differ from the base")
    return what


KEEP_OPENED: dict = {}          # box -> the pictures of every box as its walk first opened it (other_values)


def walk_box(cam, link, eyes, cycle, model, path, option, labels, look_: Look, b, base, out, run, most: int) -> None:
    """Box b walked (the module's): Up until it comes round or stops, then Down from the value held where it stopped,
    `most` values each way at most, the value held put back last; one attempt, finished once that put-back changed
    nothing."""
    name = f"{' > '.join(path)} > {option}"
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    open_row(cam, cycle, model, path)
    to_option(cam, option, labels)
    into_box(cam, option, labels, b, len(look_.labels))
    held = lit_read(cam, True).text
    if key(held) != key(look_.values[b]):
        raise Failed(f"{name}: box {b} holds {held!r}, the look read {look_.values[b]!r}")
    KEEP_OPENED[b] = {k: box_pic(cam, k) for k in range(len(look_.labels))}
    w = Walk(held, box_pic(cam, b))
    close_screen(cam, link)
    print(f"{name}: box {b} ({look_.labels[b]}) holds {held!r}; Up from it, then Down where it stops, {most} values "
          "each way at most", flush=True)
    phase, counts = "up", {"up": 0, "down": 0}
    while True:
        target = max(w.values) + 1 if phase == "up" else min(w.values) - 1 if phase == "down" else 0
        got = visit(cam, link, eyes, cycle, model, path, option, labels, look_, b, w, target, base, out, attempt)
        if got in ("round", "back"):
            break
        if got == "end":
            phase = "down" if phase == "up" else "back"
            continue
        counts[phase] += 1
        if counts[phase] >= most:
            print(f"   box {b}: {most} values {phase} from the one held, the deadline (--most): its "
                  f"{'top' if phase == 'up' else 'low'} end not reached", flush=True)
            phase, w.cut = ("down" if phase == "up" else "back"), True
    finish_attempt(run, attempt, name)
    ups = [w.values[p] for p in sorted(w.values) if p > 0]
    downs = [w.values[p] for p in sorted(w.values, reverse=True) if p < 0]
    print(f"{name}: box {b} walked: held {w.values[0]!r}; Up {ups}; Down {downs}", flush=True)


def map_labels(map_path, path: list) -> list:
    """The carousel's options as the row's own map names them ([] where the map has no such carousel)."""
    rows = read_json(Path(map_path)).get("rows") or []
    return [o["label"] for r in rows if r.get("path") == list(path) and r.get("kind") == "dialog"
            for o in sorted(r.get("options") or [], key=lambda o: o["index"])]


def main(argv=None):
    ap = argparse.ArgumentParser(description="A carousel option's own fields, one value a download")
    ap.add_argument("--row", required=True, help="the carousel's row, ' > ' between submenus")
    ap.add_argument("--option", required=True, help="its option that draws the fields (\"Cont. Bracket\")")
    ap.add_argument("--map", required=True, type=paths.run_arg, help="the row's own map.json (the crawl's)")
    ap.add_argument("--look", action="store_true", help="read only: the boxes' names and values, nothing chosen")
    ap.add_argument("--box", type=int, action="append", default=None, help="prove this box alone (from 0)")
    ap.add_argument("--most", type=int, default=MOST, help=f"values a walk proves each way at most ({MOST})")
    ap.add_argument("--context", default=None, help="the state the proofs are made in (\"Drive Mode dial on BRK\")")
    add_scan_argument(ap)
    a = ap.parse_args(argv)
    path = [x.strip() for x in a.row.split(" > ")]
    labels = map_labels(a.map, path)
    if not any(is_option(lab, a.option) for lab in labels):
        sys.exit(f"{a.option!r} is not one of the options {a.map} gives {a.row!r} ({', '.join(labels) or 'none'}): "
                 "nothing was sent to the camera")
    if a.most < 1:
        sys.exit("--most: one value at least")
    cycle, model = load_scan(a.scan)
    run = Run(PROOF_RUN)
    eyes = eyes_from_config(run)
    KEEP_OPENED.clear()
    stopped = []
    with proofs_file(run, a.context) as out, prover_session(run, eyes) as s:
        try:
            body(s, eyes, cycle, model, path, a, labels, out, run)
        except Exception as e:
            stopped.append(e)
            raise
    code = stop_status(stopped[0] if stopped else None)
    if code:
        print(f"the run was stopped by {'a refusal' if code == EXIT_REFUSED else 'a failure'}: its start file is back and "
              f"checked, but what came after it was not done (exit status {code})", flush=True)
        sys.exit(code)


def body(s, eyes, cycle, model, path, a, labels, out, run) -> None:
    """The run inside its session (main): the look, then (without --look) the base and each box's walk."""
    cam, link = s.cam, s.link
    seen = look(cam, link, cycle, model, path, a.option, labels)
    for k, (lab, v) in enumerate(zip(seen.labels, seen.values, strict=True)):
        print(f"box {k}: {lab} = {v!r}", flush=True)
    print(f"fields: {seen.fields()}; together {together(seen.fields())!r}", flush=True)
    if a.look:
        return
    boxes = a.box if a.box is not None else list(range(len(seen.labels)))
    bad = [b for b in boxes if not 0 <= b < len(seen.labels)]
    if bad:
        raise Failed(f"--box {bad}: the option draws {len(seen.labels)} boxes (counted from 0)")
    # the base: the option chosen as its boxes stand, so its own record never moves in a proof
    row = open_row(cam, cycle, model, path)
    to_option(cam, a.option, labels)
    enter(cam, a.option, labels, None, None, None)
    got = after_ok(cam, f"{a.row} > {a.option}", label=a.option, back=lambda: same_place(place(cam), row), info=False)
    if not got.applied:
        raise Failed(f"{a.option}: the camera refused it as its boxes stood (its notice closed with MENU): no base, "
                     "nothing proved")
    to_shooting(link, eyes, "the base download")
    base = link.download(f"{path[-1]}-{a.option}-base".replace(" ", "-"))
    wait_lock(time.monotonic(), eyes, clock=time)
    moved = camset.diff(camset.read(s.start), camset.read(base))
    print(f"base: {a.option} chosen as its boxes stand ({len(moved)} records moved from the start file); every proof "
          "is compared with it", flush=True)
    for b in boxes:
        walk_box(cam, link, eyes, cycle, model, path, a.option, labels, seen, b, base, out, run, a.most)


if __name__ == "__main__":
    main()
