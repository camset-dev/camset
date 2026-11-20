"""Prove a carousel option's own fields, one value a download: the a1 II's Bracket Type (Shooting > Drive Mode > Bracket
Settings > Bracket Type, open only with the drive mode dial on BRK), whose Cont. Bracket and Single Bracket draw
Exposure Value and Number of Shots under the title, and Focus Bracket Step Width and Number of Shots in three digit
boxes (2026-11-19).

    CAMSET_EYES=osd .venv/bin/python -u kit/provers/carousel_fields_run.py --scan SCAN --map kit2_fin_crawl_brk/map.json \\
        --row "Bracket Settings > Bracket Type" --option "Cont. Bracket" --context "Drive Mode dial on BRK" --look
    (the same without --look; --box N proves the N-th box alone, counted from 0; --most N, the deadline; --grid every
    pair of two fields; --number N a named number in a digit field, repeated for more)

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
line, written once the next opening shows the camera kept the value. A value it did not keep is a finding, not a
failure (Focus Bracket's number of shots 000, kept as 2, its lowest, 2026-11-19): where the box opens on another value
and the download after that OK bears it out (a record holds the number the box's field now makes, or the same changes
as that value's own line), the line says "applied": false, "asked" and "kept" (as drawn), credits nothing, and the
walk steps the box back onto the place asked and goes on from there; otherwise the walk stops. The value held is proved
last, put back so, and its download must equal the base. Each box's walk is an attempt of its own, so a later box's
stop takes back no box that finished. The session's start file goes back on at the end, as every prover's.

--grid, for an option of two fields of one box each (Cont. and Single Bracket's Exposure Value and Number of Shots, one
record holding the pair): every pair the boxes offer, one a download, as one attempt. Box 1 is scanned where box 0
stands, nothing chosen (Down until it stands still, then Up until it stands still again, each new value read), then its
pairs are chosen from its top down to its low end, one visit each; box 0 moves only with box 1 on its low end, so a
step that refuses a count never stands still for it (which pairs exist is the camera's: the Drive Mode lists name 60
of the 72 crossings), Up from the value held one place at a time, then Down; the end it finds and the next place are
reached in one visit. An end of either box is taken only after presses the camera was seen to answer (at_end: one
step back and on again, each seen, then one more press that stands still), so two presses lost in a row never pass
for an end. Each opening checks the pair the last OK chose, box 1 too before MENU takes the visit back to the option
for box 0's move. The pair held is put back last; "whole" unless a deadline cut a list short or an end could not be
confirmed (a box of one value moves neither way). A pair the camera refuses stops the grid.

--number N (repeated), for an option with one field of digit boxes side by side (Focus Bracket's Number of Shots):
each box of the field stepped to N's digit in turn, Up where it is higher, else Down, no Enter on the way, then Enter
once on the field's last box, one download. A box that stands still or comes round short of its digit is said and
the number passed over, nothing chosen; so is one whose stepping moved another box (every other box's picture before
its first press and after its last, that box lit both times: the sides the pixel reader finds for a box move with the
lit box beside it), or a box outside the field not as the first visit saw it. Each next opening reads the boxes
before any key steps them: a number the camera kept otherwise is a finding, as in a walk ("applied": false, "asked",
"kept"). The number held is put back last, as one attempt with the numbers.

Readings, as kit/provers/optboxes_run.py reads its boxes: the lit box by OCR, the second reader asked about the lit box
itself on every doubt (camkit.reading.doubts) and always where the value decides a proof (the owner's rule: the reader is
asked before a row fails), OCR plain and the reader apart settled by the third role's readers where a reading stands by
the kit's one counting rule (box_vote), else stopping the row; the field's name by OCR, the reader where it
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
"both", "reader", "votes"), "shown" OCR's reading of it, "box_vlm" and "box_reader" the second reader's and its name,
"box_votes" where the third role's readers settled it (every vote: "eye", "reader", "model", "text"), "final" on
the put-back and with it "whole" (False where the deadline cut the walk short), "attempt", "changes". A grid's lines
say "walk": "grid", "index" ["grid", box 0's place, box 1's place from its low end], "field" and "value" box 1's; a
named number's "walk": "number", "index" ["number", N], "value" the number its boxes make.
kit/pass2_report.py credits a record moved by the lines of two fields or more, or by a grid's, with "label", a record
only one field's lines moved with that field's "value"; a put-back's value only where its walk was whole, as the value
held would stand out among a part walk's (docs/decisions/0016), and never a named number's. A record every pair of a
whole grid moved is no sample: every pair is listed, the one held among them.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, paths, reading, screen, vlm  # noqa: E402
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
from proving.screens import (box_answer, carousel_text, place, same_place, title_settled, vlm_option,  # noqa: E402
                             word_answer)
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
    asked), the reader that answered, which gave the value ("ocr", "both", "reader", "votes": the third role's readers
    settled it, box_vote), and then every vote cast (box_vote's)."""
    text: str
    ocr: str
    vlm: str | None = None
    reader: str | None = None
    by: str = "ocr"
    votes: tuple = ()


def votes_of(r: BoxRead) -> dict:
    """What a proof line keeps of a vote that settled the box (BoxRead.votes): {"box_votes": [...]}, else nothing."""
    return {"box_votes": list(r.votes)} if r.votes else {}


def title_reads(cam, labels: list) -> str | None:
    """The carousel option the title names, one of the map's `labels`: OCR's orange line (proving.screens.carousel_text)
    where it names one plainly (camkit.reading: no doubt, one option named), else the second reader's (vlm_option);
    None where neither names one. Read once the title has settled (proving.screens.title_settled): it redraws after the
    strip, and a frame just after a Down can show the strip on the next option under the old title."""
    title_settled(cam)
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


def box_vote(cam, raw: str, said: str, who) -> tuple:
    """Where OCR's plain reading of the lit box and the second reader's are two numbers (lit_read): the third role's
    readers (camkit.vlm.voters, in the order private/config.json gives them) asked in turn the second reader's own
    question about the same frame (PROMPTS["box"], through camkit.reading.ask under each one's role key), each only while
    no reading stands and none where a reader of its model's family has read the box already (camkit.reading.family_voted:
    it could make nothing stand). The votes are counted by the kit's one rule, camkit.reading.tally, a number's way: one
    vote per OCR engine and per model family, a family that read two things casts none, and a reading neither OCR nor the
    second reader gave never stands on later votes alone; here it stands only with a third reader's vote among those
    behind it, OCR and the second reader having been read apart. A third reader that does not answer casts no vote.
    Returns (the reading that stands, canonical, or None; every vote cast, {"eye", "reader", "model", "text"} and "why"
    where one gave no answer, as the proof line keeps them). No fresh frame first: this prover reads the box on the frame
    its picture was judged on, a doubtful reading included, and the proof line names that frame."""
    frame = cam.frame.path.name
    second = vlm.answered_by() or reading._reader_model("second")    # the model that answered the second's question
    votes = [reading.Vote("ocr", f"ocr:{reading.engine_of(ocr.engine())}", raw, frame),
             reading.Vote("reader", f"reader:{reading.model_id(second or who)}", said, frame)]
    kept = [{"eye": "ocr", "reader": ocr.engine(), "model": None, "text": raw},
            {"eye": "reader", "reader": who, "model": second, "text": said}]

    def stands():
        win, eyes = reading.tally(votes, "number")
        return win if win is not None and any(vlm.voter_index(e) is not None for e in eyes) else None
    for k in range(reading.MAX_THIRD):
        if stands() is not None:
            break
        role = vlm.voter_key(k)
        model = reading._reader_model(role)
        if model is None:
            break
        if reading.family_voted(votes, model):
            continue
        got = reading.ask(cam.frame, "box", 25.0, role=role)
        value = got.answer.get("value") if isinstance(got.answer, dict) else None
        value = " ".join(value.split()) if isinstance(value, str) and value.strip() else None
        votes.append(reading.Vote(role, f"reader:{reading.model_id(got.model or model)}", value, frame))
        kept.append({"eye": role, "reader": got.name, "model": got.model or model, "text": value,
                     **({"why": got.why} if got.why else {})})
    win = stands()
    return (None if win is None else reading.canonical(win.text)), tuple(kept)


def voters_said(votes: tuple) -> str:
    """The third readers' votes in words, for a refusal: each reader's reading, or that none was asked."""
    third = [v for v in votes if vlm.voter_index(v["eye"]) is not None]
    if not third:
        return " (no third reader of another model family to ask)"
    return " (the third readers: " + ", ".join(f"{v['reader'] or v['eye']} {v['text']!r}" for v in third) + \
        ": no reading stands by the kit's rule)"


# Characters OCR reads into a lit box that the camera never draws in one: the bullet it read for the minus sign of
# "2 Images (-)" (16 of the 327 HDMI frames of that value, none of the 554 of "(+)", none over OSD). Measured 2026-11-20 on
# the 11,612 dialog frames recorded with a box lit (Apple Vision; 483 readings): the bullet in those 16 alone, and no
# other dot-like character (a middle dot, a dot operator) in any. A reading holding one is doubted (box_doubts), so the
# second reader reads the box on a read with OCR alone too, where the bullet would make another value
BOX_MISREADS = "\u2022"


def box_doubts(raw: str) -> list:
    """Why OCR's reading of a lit box is not plain: camkit.reading.doubts as a number, and each character OCR reads there
    that the camera never draws (BOX_MISREADS)."""
    odd = [f"U+{ord(c):04X}, which the camera never draws in a lit box" for c in dict.fromkeys(raw) if c in BOX_MISREADS]
    return reading.doubts(raw, "number", lit=True) + odd


def lit_read(cam, always: bool) -> BoxRead:
    """The lit box's value, as optboxes_run reads its boxes: OCR's reading (boxes_run.lines) stands alone where it is
    plain (box_doubts: camkit.reading.doubts, a number: four characters or more, no look-alike; and no character the
    camera never draws there, BOX_MISREADS) and `always` is False. Otherwise,
    and always where `always` (a new value, the value held, a value Enter goes on: each decides a proof), the second
    reader is asked about the lit box itself (ask_box): where OCR was unsure, its reading is taken (the owner's rule,
    2026-11-06: the reader is right where OCR drops or mangles short digits, and it is asked before a row fails); where
    OCR was plain, both must hold the same number (key), and the reader's words are kept, OCR dropping letters of them.
    Where they hold two numbers, the third role's readers vote (box_vote: OCR read a bullet for the minus sign of the
    second reader's "2 Images (-)", kit2_pass2 266268, 2026-11-20), and the reading that stands is taken, said so
    ("votes"). A reader
    that does not answer where it must, or two numbers apart that no vote settles, stop the row: the kit does not
    guess."""
    frame = cam.frame.path.name
    raw = ocr.text_in(lines(cam), lit_box(cam)).strip()
    doubted = box_doubts(raw)
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
        voted, votes = box_vote(cam, raw, said, who)
        if voted is None:
            raise Failed(f"the lit box on {frame}: OCR read {raw!r} and the second reader {said!r}: the kit does not "
                         f"guess which{voters_said(votes)}")
        return BoxRead(voted, raw, said, who, "votes", votes)
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


def stood_still(cam, option: str, b: int, count: int, way: str, name: str) -> bool:
    """One Up or Down on box b (step), judged by its picture: False where the box moved; True where it stood still, on a
    fresh frame too and on one more press (an end). A box that stood still and then moved on that press stops the row:
    a press went unanswered."""
    before = box_pic(cam, b)
    step(cam, option, b, count, way)
    if not same_pic(box_pic(cam, b), before):
        return False
    cam.refresh("field-again")                          # nothing moved: a late frame, or an end
    if not same_pic(box_pic(cam, b), before):
        return False
    step(cam, option, b, count, way)                    # one more press: at an end it changes nothing either
    if not same_pic(box_pic(cam, b), before):
        raise Failed(f"{name}: box {b} stood still on one {way.title()} and moved on the next "
                     f"({cam.frame.path.name}): a press went unanswered; nothing chosen")
    return True


def at_end(cam, option: str, b: int, count: int, way: str, name: str) -> bool | None:
    """Whether box b stands at its end `way` (the grid's), taken only after presses the camera was seen to answer: where
    it stood still (stood_still: two presses, a fresh frame between), one step back must move it, one step on must
    bring it back to that picture, and one more press must leave it standing still, on a fresh frame too. True: an end;
    False: that last press moved it, so the stand-still before was presses lost (two in a row, the review of
    2026-11-19), and the box stands on the next value; None: it moves neither way, an end no answered press confirms
    (a box of one value, or a link that stopped answering), which the grid then calls not whole. Three presses an end."""
    if not stood_still(cam, option, b, count, way, name):
        return False
    end = box_pic(cam, b)
    step(cam, option, b, count, "down" if way == "up" else "up")
    if same_pic(box_pic(cam, b), end):
        cam.refresh("field-again")
        if same_pic(box_pic(cam, b), end):
            return None
    step(cam, option, b, count, way)                    # back onto the end
    if not same_pic(box_pic(cam, b), end):
        cam.refresh("field-again")
        if not same_pic(box_pic(cam, b), end):
            raise Failed(f"{name}: box {b} did not come back onto its end on {way.title()} ({cam.frame.path.name}): a "
                         "press went unanswered; nothing chosen")
    step(cam, option, b, count, way)                    # beyond it once more
    if not same_pic(box_pic(cam, b), end):
        return False
    cam.refresh("field-again")
    return same_pic(box_pic(cam, b), end)


def step_known(cam, option: str, b: int, count: int, way: str, want: tuple, name: str) -> None:
    """One Up or Down on box b onto a value seen there before (`want`, its reading and picture): the box must move, and
    show that picture, else read as that value (a value seen before, on the way, as visit checks one)."""
    before = box_pic(cam, b)
    step(cam, option, b, count, way)
    now = box_pic(cam, b)
    if same_pic(now, before):
        cam.refresh("field-again")
        now = box_pic(cam, b)
    if same_pic(now, want[1]):
        return
    if same_pic(now, before):
        raise Failed(f"{name}: box {b} stood still on {way.title()} where it moved on to {want[0]!r} before "
                     f"({cam.frame.path.name}); nothing chosen")
    got = lit_read(cam, False).text
    if key(got) != key(want[0]):
        raise Failed(f"{name}: box {b} reads {got!r} where it read {want[0]!r} before ({cam.frame.path.name}); nothing "
                     "chosen")


def enter(cam, option: str, labels: list, b: int | None, count: int | None, want: str | None, pic=None) -> str:
    """Enter on this row's option itself (b None) or on its box b holding `want` (its picture `pic`, as the walk saw
    that value): judged first (option_refused; on a box, a fresh frame grabbed, box_refused with the title read, the
    box's picture and its reading by both readers on it, lit_read's vote where they differ: Enter goes only where the
    reading that stands is `want`), then by the camera's own Enter guard (LiveCamera). The fresh frame is the box
    prover's own: LiveCamera's look before Enter compares screens by their signature, and a dialog's cannot see what its
    lit box holds (0.3EV lit and 0.5EV lit are one signature on the camera's frames). OCR alone refused an Enter on a
    frame it misread (a bullet for the minus sign of "2 Images (-)", about one HDMI frame of that value in twenty).
    Returns the frame Enter went on."""
    if b is not None:
        cam.refresh("enter-check")
    why = option_refused(cam, option, labels) if b is None else box_refused(cam, option, labels, b, count)
    if not why and b is not None and (not same_pic(box_pic(cam, b), pic) or key(lit_read(cam, True).text) != key(want)):
        why = f"box {b} no longer reads {want!r}"
    if why:
        raise Failed(f"{option}: no Enter: {why} ({cam.frame.path.name})")
    chosen = cam.frame.path.name
    cam.press("enter")
    return chosen


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
        self.changes = {0: []}          # place -> the records its line changed (bears_out)
        self.pending = None             # the last value's line, written once the next opening shows what was kept
        self.off = None                 # (picture, reading) of a value the camera kept in place of the one asked

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
    on_opening(cam, look_, b, w, out, name)
    if w.off is not None:
        find_asked(cam, option, b, count, w, name)      # from the value the camera kept, back onto the one asked
    way = "up" if target > w.pos else "down"
    at = w.pos
    while at != target:
        nxt = at + (1 if way == "up" else -1)
        if stood_still(cam, option, b, count, way, name):
            if nxt in w.values:
                raise Failed(f"{name}: box {b} stopped at {w.values[at]!r}, where it had moved on before "
                             f"({cam.frame.path.name})")
            print(f"   box {b}: {w.values[at]!r} is its {'top' if way == 'up' else 'low'} end (one more "
                  f"{way.title()} changed nothing)", flush=True)
            close_screen(cam, link)
            return "end"
        now = box_pic(cam, b)
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


SEARCH = 2 * MOST               # presses at most each way stepping back onto a value the camera did not keep (find_asked)


def on_opening(cam, look_: Look, b: int, w: Walk, out, name: str) -> None:
    """The box on opening, checked against what the last OK left, and the last value's line written then (w.pending).
    On the value chosen (its picture, else its reading): the line as it stands. Where the camera kept another value
    (w.off since an earlier opening): that value again. On another value than the last OK chose: where the download
    after that OK bears the box out (bears_out: the camera's own correction, Focus Bracket's 000 kept as 2), the line
    says what was asked and what the camera kept ("applied": false, "asked", "kept", as drawn), credits nothing, and
    the walk goes on from the place asked (find_asked); otherwise the walk stops, as it did before 2026-11-19."""
    pic = box_pic(cam, b)
    if w.off is not None:
        if not same_pic(pic, w.off[0]) and key(lit_read(cam, False).text) != key(w.off[1]):
            raise Failed(f"{name}: box {b} opened on {lit_read(cam, False).text!r}, not {w.off[1]!r}, which the camera "
                         f"kept ({cam.frame.path.name})")
        return
    if same_pic(pic, w.pics[w.pos]) or key(lit_read(cam, False).text) == key(w.values[w.pos]):
        flush(w, out)
        return
    shown = lit_read(cam, True).text
    if w.pending is None or not bears_out(w, look_, b, shown, pic):
        raise Failed(f"{name}: box {b} opened on {shown!r}, not {w.values[w.pos]!r}, which the last OK chose "
                     f"({cam.frame.path.name})")
    print(f"   box {b}: the camera kept {shown!r}, not {w.pending['box']!r}, the value asked (its download bears the "
          "box out): nothing credited to it", flush=True)
    flush(w, out, applied=False, asked=w.pending["box"], kept=shown)
    p = w.known(shown, pic)
    if p is not None and same_pic(pic, w.pics.get(p)):
        w.pos = p                                       # a value seen before: the walk stands on its place
    else:
        w.off = (pic, shown)


def bears_out(w: Walk, look_: Look, b: int, shown: str, pic) -> bool:
    """Whether the download after the last OK shows the record on the value box b now shows (`shown`, its picture
    `pic`): a record it changed now holds the number box b's field now makes (Focus Bracket's 000 kept as 2: 0x10aa 2),
    or the box shows a value seen before whose own line changed the same records to the same values."""
    changes = w.pending["changes"]
    values = list(look_.values)
    values[b] = shown
    field = next(f for f in look_.fields(values) if f["label"] == look_.labels[b])
    try:
        number = float(key(field["value"]))
    except ValueError:
        number = None
    if number is not None and any(isinstance(c.get("after"), (int, float)) and not isinstance(c.get("after"), bool)
                                  and c["after"] == number for c in changes):
        return True
    p = w.known(shown, pic)
    return p is not None and p != w.pos and w.changes.get(p) == changes


def flush(w: Walk, out, **said) -> None:
    """The last value's line written (w.pending), with what the opening after it found (`said`), and forgotten."""
    if w.pending is None:
        return
    out.write(json.dumps({**w.pending, **said}, ensure_ascii=False) + "\n")
    out.flush()
    w.pending = None


def find_asked(cam, option: str, b: int, count: int, w: Walk, name: str) -> None:
    """From the value the camera kept (w.off), box b stepped back onto the place asked (its picture, w.pics[w.pos]):
    Down first, then Up, SEARCH presses at most each way, a way given up where a press moves nothing (an end, on a fresh
    look too); every press checked as any step in the box. Failed where the place asked never shows again."""
    want = w.pics[w.pos]
    for way in ("down", "up"):
        for _ in range(SEARCH):
            before = box_pic(cam, b)
            step(cam, option, b, count, way)
            now = box_pic(cam, b)
            if same_pic(now, before):
                cam.refresh("field-again")
                now = box_pic(cam, b)
            if same_pic(now, want):
                w.off = None
                return
            if same_pic(now, before):
                break
    raise Failed(f"{name}: box {b} never showed {w.values[w.pos]!r} again from {w.off[1]!r}, which the camera kept "
                 f"({cam.frame.path.name})")


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
    the box stays where it stood; the put-back ("round", "back") must change nothing, its line written at once. Any
    other line waits for the next opening (w.pending, on_opening), which shows whether the camera kept the value."""
    name = f"{' > '.join(path)} > {option}"
    values = other_values(cam, look_, b, KEEP_OPENED.get(b, {}))
    values[b] = r.text
    fields = look_.fields(values)
    field = next(f for f in fields if f["label"] == look_.labels[b])
    lab = together(fields)
    chosen = enter(cam, option, labels, b, len(look_.labels), r.text, w.pics[place_])
    got = after_ok(cam, name, label=lab, back=lambda: same_place(place(cam), row), info=False)
    row_frame = cam.frame.path.name
    to_shooting(link, eyes, "the download after OK")
    dat = link.download(f"{path[-1]}-{b}-{place_}".replace(" ", "-"))
    wait_lock(time.monotonic(), eyes, clock=time)
    ch = camset.diff(camset.read(base), camset.read(dat))
    final = what in ("round", "back")
    rec = {"path": [*path, option], "kind": "list", "via": VIA, "index": [b, place_], "field": look_.labels[b],
           "value": field["value"], "label": lab, "fields": fields, "box": r.text, "read_by": r.by, "shown": r.ocr,
           "box_vlm": r.vlm, "box_reader": r.reader, **votes_of(r), "chosen_frame": chosen, "row_frame": row_frame,
           "dat": dat.name, "base": base.name, **({"notice": got.notice} if got.notice else {}), "applied": got.applied,
           "final": final, **({"whole": not w.cut} if final else {}), "attempt": attempt, "changes": changes_of(ch)}
    if final or not got.applied:
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
    else:
        w.pending = rec
    print(f"   {look_.labels[b]} = {r.text!r} ({lab}): " + ("refused by the camera" if not got.applied else
          ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:4]) or "no change"), flush=True)
    if got.applied:
        w.pos, w.changes[place_] = place_, rec["changes"]
    if final and ch:
        raise Failed(f"{name}: box {b} back on {r.text!r}, {len(ch)} records still differ from the base")
    return what


KEEP_OPENED: dict = {}          # box -> the pictures of every box as its walk first opened it (other_values)


def walk_box(cam, link, eyes, cycle, model, path, option, labels, look_: Look, b, base, out, run, most: int) -> None:
    """Box b walked (the module's): Up until it comes round or stops, then Down from the value held where it stopped,
    `most` values each way at most, the value held put back last; one attempt of its own, finished once that put-back
    changed nothing, so a later box's stop never takes back a box that finished. A line still waiting for the next
    opening when the walk stops is written saying what applied is not known ("applied": null)."""
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
    try:
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
    finally:
        flush(w, out, applied=None)          # never seen again: what applied is not known
    finish_attempt(run, attempt, name)
    ups = [w.values[p] for p in sorted(w.values) if p > 0]
    downs = [w.values[p] for p in sorted(w.values, reverse=True) if p < 0]
    print(f"{name}: box {b} walked: held {w.values[0]!r}; Up {ups}; Down {downs}", flush=True)


# ------------------------------------------------------------------------------------------------ every pair (--grid)

class Grid:
    """A two-field option's pairs (--grid): box 0's values by place (counted from the value held, Up positive), box 1's
    values at each place of box 0, low end first, as a scan found them; the pairs chosen, where the last OK left the
    boxes, and whether a deadline cut a list short."""

    def __init__(self):
        self.outer = {}         # box 0's place -> (reading, picture)
        self.inner = {}         # box 0's place -> [(reading, picture)] of box 1 there, its low end first
        self.held = None        # box 1's place in inner[0] that the base holds
        self.done = set()       # (place, box 1's place) chosen, a download each
        self.pos = None         # (place, box 1's place) the last OK left
        self.phase = "up"       # box 0 Up from the value held, then Down from it, then "done"
        self.cut = False        # a deadline cut a list short: the pairs proved are not every pair
        self.pending = None     # the last pair's line, written once the next opening shows the camera kept it
        self.left = None        # box 0's picture once Right left it (choose_pair: it never moves with box 1)

    def next_at(self, p) -> int | None:
        """The pair to choose next at box 0's place p: the highest place of box 1 there not chosen yet, the pair held
        left to the put-back, but at box 1's low end, where every move of box 0 starts from (grid_walk)."""
        todo = [i for i in range(len(self.inner[p])) if (p, i) not in self.done
                and not (p == 0 and i == self.held and i != 0)]
        return max(todo) if todo else None


def held_box(cam, b: int, look_: Look, name: str) -> tuple:
    """(reading, picture) of the lit box b, which must hold what the look read there."""
    r = lit_read(cam, True)
    if key(r.text) != key(look_.values[b]):
        raise Failed(f"{name}: box {b} holds {r.text!r}, the look read {look_.values[b]!r}")
    return r.text, box_pic(cam, b)


def expect(cam, b: int, want: tuple, name: str) -> None:
    """The lit box b on opening shows the value the last OK chose (`want`, its reading and picture): its picture, else
    its reading; the grid stops on any other (no correction of the camera's is looked for here)."""
    if same_pic(box_pic(cam, b), want[1]):
        return
    got = lit_read(cam, False).text
    if key(got) != key(want[0]):
        raise Failed(f"{name}: box {b} opened on {got!r}, not {want[0]!r}, which the last OK chose "
                     f"({cam.frame.path.name})")


def scan(cam, option: str, b: int, count: int, start: tuple, most: int, name: str) -> tuple:
    """Box b's values from `start` (the reading and picture of the value it shows) to both its ends, nothing chosen: Down
    until it stands at its end (at_end), then Up through those and on to its other end, each new value read by both
    readers (lit_read: each decides a proof), `most` new values each way at most. Returns ([(reading, picture)], its low
    end first, and whether the list may be short: the deadline cut it, or an end no answered press confirmed); the box
    stands on the last of them. A value seen before on the way (a box that comes round, or two values the readers
    cannot tell apart) stops the row."""
    vals, cut = [start], False
    for way in ("down", "up"):
        if way == "up":
            for k in range(1, len(vals)):                   # back up through the values the Down found
                step_known(cam, option, b, count, "up", vals[k], name)
        for n in range(most + 1):
            if n == most:
                cut = True
                print(f"   box {b}: {most} values {way} from {start[0]!r}, the deadline (--most): its "
                      f"{'top' if way == 'up' else 'low'} end not reached", flush=True)
                break
            end = at_end(cam, option, b, count, way, name)
            if end is None:
                cut = True
                print(f"   box {b}: {vals[0 if way == 'down' else -1][0]!r} moves neither way: an end no answered press "
                      "confirms, so the grid is not called whole", flush=True)
            if end is not False:
                break
            now = box_pic(cam, b)
            r = lit_read(cam, True)
            if any(same_pic(now, p) or key(r.text) == key(t) for t, p in vals):
                raise Failed(f"{name}: box {b} reads {r.text!r} ({cam.frame.path.name}), a value seen before on its "
                             "way: it comes round, or the readers cannot tell its values apart; nothing chosen")
            if way == "down":
                vals.insert(0, (r.text, now))
            else:
                vals.append((r.text, now))
    return vals, cut


def move_to(cam, option: str, b: int, count: int, vals: list, at: int, to: int, name: str) -> None:
    """Box b from its place `at` to `to` among `vals` (a scan's), each press onto a value seen there before."""
    way, d = ("up", 1) if to > at else ("down", -1)
    while at != to:
        at += d
        step_known(cam, option, b, count, way, vals[at], name)


def next_outer(cam, option: str, count: int, g: Grid, p: int, most: int, name: str) -> int | None:
    """Box 0, lit on its place p, stepped to its next new place: Up beyond the highest seen, then Down beyond the
    lowest, each press onto a place seen before checked on the way. Where the box stands at its end (at_end; one no
    answered press confirms makes the grid not whole) or the deadline (`most` places each way, likewise) is reached,
    that way is done and the other goes on in the same visit. Returns the
    new place, its value read by both readers; None once both ways are done, box 0 then stepped back to place 0."""
    at = p
    while g.phase != "done":
        way, d = (g.phase, 1) if g.phase == "up" else (g.phase, -1)
        edge = max(g.outer) if d > 0 else min(g.outer)
        while at != edge:
            at += d
            step_known(cam, option, 0, count, way, g.outer[at], name)
        nxt = at + d
        end = None if abs(nxt) > most else at_end(cam, option, 0, count, way, name)
        if abs(nxt) > most:
            g.cut = True
            print(f"   box 0: {most} values {way} from the one held, the deadline (--most): its "
                  f"{'top' if d > 0 else 'low'} end not reached", flush=True)
        elif end is None:
            g.cut = True
            print(f"   box 0: {g.outer[at][0]!r} moves neither way: an end no answered press confirms, so the grid is "
                  "not called whole", flush=True)
        elif end:
            print(f"   box 0: {g.outer[at][0]!r} is its {'top' if d > 0 else 'low'} end (one more {way.title()} "
                  "changed nothing)", flush=True)
        else:
            now, r = box_pic(cam, 0), lit_read(cam, True)
            if any(same_pic(now, pic) or key(r.text) == key(t) for t, pic in g.outer.values()):
                raise Failed(f"{name}: box 0 reads {r.text!r} ({cam.frame.path.name}), a value seen before: it comes "
                             "round, or the readers cannot tell its values apart; nothing chosen")
            g.outer[nxt] = (r.text, now)
            return nxt
        g.phase = "down" if d > 0 else "done"
    move_to(cam, option, 0, count, [g.outer[k] for k in sorted(g.outer)], sorted(g.outer).index(at),
            sorted(g.outer).index(0), name)
    return None


def choose_pair(cam, link, eyes, path, option, labels, look_: Look, g: Grid, p: int, i: int, row, base, out, attempt,
                final: bool = False) -> None:
    """The pair (box 0's place p, box 1's place i there), box 1 lit on it: read by both readers against the scan's
    reading, box 0 checked as Right left it, Enter (enter), the screen after it read (after_ok), a download, its diff
    against the base and the proof line, which waits for the next opening (g.pending) but where the camera refused it
    or it is the put-back (`final`, the pair held: it must change nothing)."""
    name = f"{' > '.join(path)} > {option}"
    count = len(look_.labels)
    want_text, want_pic = g.inner[p][i]
    r = lit_read(cam, True)
    if key(r.text) != key(want_text):
        raise Failed(f"{name}: box 1 reads {r.text!r}, where the scan read {want_text!r} ({cam.frame.path.name}); "
                     "nothing chosen")
    if not same_pic(box_pic(cam, 0), g.left):
        raise Failed(f"{name}: box 0 changed while box 1 moved ({cam.frame.path.name}); nothing chosen")
    fields = look_.fields([g.outer[p][0], r.text])
    lab = together(fields)
    chosen = enter(cam, option, labels, 1, count, r.text, want_pic)
    got = after_ok(cam, name, label=lab, back=lambda: same_place(place(cam), row), info=False)
    row_frame = cam.frame.path.name
    to_shooting(link, eyes, "the download after OK")
    dat = link.download(f"{path[-1]}-grid-{p}-{i}".replace(" ", "-"))
    wait_lock(time.monotonic(), eyes, clock=time)
    ch = camset.diff(camset.read(base), camset.read(dat))
    rec = {"path": [*path, option], "kind": "list", "via": VIA, "walk": "grid", "index": ["grid", p, i],
           "field": look_.labels[1], "value": r.text, "label": lab, "fields": fields, "box": r.text, "read_by": r.by,
           "shown": r.ocr, "box_vlm": r.vlm, "box_reader": r.reader, **votes_of(r), "chosen_frame": chosen,
           "row_frame": row_frame, "dat": dat.name, "base": base.name, **({"notice": got.notice} if got.notice else {}),
           "applied": got.applied, "final": final, **({"whole": not g.cut} if final else {}), "attempt": attempt,
           "changes": changes_of(ch)}
    if final or not got.applied:
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
    else:
        g.pending = rec
    print(f"   {lab}: " + ("refused by the camera" if not got.applied else
                           ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:4]) or "no change"), flush=True)
    if not got.applied:
        # a pair its boxes offered: box 1 would stand off its low end for box 0's next move, so the grid stops here
        raise Failed(f"{name}: the camera refused {lab!r}, a pair its boxes offered (its notice closed with MENU)")
    g.pos = (p, i)
    g.done.add((p, i))
    if final and ch:
        raise Failed(f"{name}: the pair held put back, {len(ch)} records still differ from the base")


def grid_walk(cam, link, eyes, cycle, model, path, option, labels, look_: Look, base, out, run, most: int) -> None:
    """Every pair of a two-field option (--grid, the module's), one pair a download, as one attempt: box 1 scanned at
    each place of box 0 and its pairs chosen from its top down to its low end, box 0 moved only with box 1 on its low
    end, Up from the value held and then Down; the pair held put back last, "whole" where no deadline cut a list short.
    A line still waiting for the next opening when the walk stops is written saying what applied is not known."""
    name = f"{' > '.join(path)} > {option}"
    count = len(look_.labels)
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    g = Grid()
    print(f"{name}: every pair of {look_.labels[0]} and {look_.labels[1]}, one a download", flush=True)
    try:
        while True:
            row = open_row(cam, cycle, model, path)
            to_option(cam, option, labels)
            into_box(cam, option, labels, 0, count)
            if g.pos is None:                       # the first visit: the boxes as the base holds them
                g.outer[0] = held_box(cam, 0, look_, name)
                into_next(cam, option, 1, count)
                g.left = box_pic(cam, 0)            # before the scan: box 0 must stand so until Enter (choose_pair)
                start = held_box(cam, 1, look_, name)
                g.inner[0], cut = scan(cam, option, 1, count, start, most, name)
                g.cut |= cut
                g.held = next(k for k, (_, pic) in enumerate(g.inner[0]) if same_pic(pic, start[1]))
                p, at = 0, len(g.inner[0]) - 1
            else:                                   # the last OK's pair, as the camera shows it, then its line
                p, at = g.pos
                expect(cam, 0, g.outer[p], name)
                into_next(cam, option, 1, count)
                g.left = box_pic(cam, 0)
                expect(cam, 1, g.inner[p][at], name)
                flush(g, out)
            i = g.next_at(p)
            if i is None:                           # every pair at this place chosen, box 1 on its low end
                cam.press("menu")                   # back to the option lit, nothing changed; box 0 again
                into_box(cam, option, labels, 0, count)
                expect(cam, 0, g.outer[p], name)
                nxt = next_outer(cam, option, count, g, p, most, name)
                into_next(cam, option, 1, count)
                g.left = box_pic(cam, 0)
                arrived = (lit_read(cam, True).text, box_pic(cam, 1))
                if nxt is None:                     # every place walked: the pair held put back
                    at = next((k for k, v in enumerate(g.inner[0]) if same_pic(v[1], arrived[1])
                               or key(v[0]) == key(arrived[0])), None)
                    if at is None:
                        raise Failed(f"{name}: box 1 shows {arrived[0]!r} back on {g.outer[0][0]!r}, none of the "
                                     "values the scan found there; nothing chosen")
                    move_to(cam, option, 1, count, g.inner[0], at, g.held, name)
                    choose_pair(cam, link, eyes, path, option, labels, look_, g, 0, g.held, row, base, out, attempt,
                                final=True)
                    break
                p = nxt
                g.inner[p], cut = scan(cam, option, 1, count, arrived, most, name)
                g.cut |= cut
                at, i = len(g.inner[p]) - 1, g.next_at(p)
            move_to(cam, option, 1, count, g.inner[p], at, i, name)
            choose_pair(cam, link, eyes, path, option, labels, look_, g, p, i, row, base, out, attempt)
    finally:
        flush(g, out, applied=None)          # never seen again: what applied is not known
    finish_attempt(run, attempt, name)
    print(f"{name}: {len(g.done)} pairs over {len(g.outer)} values of {look_.labels[0]}"
          + ("" if not g.cut else ", a deadline cutting a list short: not every pair"), flush=True)


# ------------------------------------------------------------------------------------------------ a named number (--number)

class Named:
    """A digit field's named numbers (--number): the last number's line waiting for the next opening, and each box's
    digits by picture, read once."""

    def __init__(self):
        self.pending = None
        self.cache = {}         # box -> [(picture, digit)]


def digit_field(look_: Look) -> tuple | None:
    """(first box, last box) of the option's one field of digit boxes side by side under one name (Focus Bracket's
    Number of Shots); None where it draws none, or more than one."""
    runs = []
    for k, lab in enumerate(look_.labels):
        if runs and look_.labels[runs[-1][0]] == lab:
            runs[-1][1] = k
        else:
            runs.append([k, k])
    found = [(a, b) for a, b in runs if b > a and all(re.fullmatch(r"\d", key(look_.values[k])) for k in range(a, b + 1))]
    return found[0] if len(found) == 1 else None


def digit_at(cam, b: int, n: Named, name: str) -> str:
    """The digit the lit box b shows: by its picture where seen before, else read by both readers (lit_read)."""
    pic = box_pic(cam, b)
    seen = n.cache.setdefault(b, [])
    hit = next((d for p, d in seen if same_pic(p, pic)), None)
    if hit is not None:
        return hit
    r = lit_read(cam, True)
    d = key(r.text)
    if not re.fullmatch(r"\d", d):
        raise Failed(f"{name}: box {b} reads {r.text!r}, not one digit ({cam.frame.path.name})")
    seen.append((pic, d))
    return d


def set_digit(cam, option: str, b: int, count: int, have: str, want: str, n: Named, name: str) -> str:
    """Box b stepped from digit `have` to `want`, nothing chosen: Up where `want` is higher, else Down, each press judged
    by the box's picture (stood_still) and its digit read (digit_at). Returns "" once the box shows `want`; else why not
    (it stood still at an end, or came round, short of it): the camera does not offer the number so."""
    way = "up" if int(want) > int(have) else "down"
    seen = [have]
    for _ in range(10):
        if stood_still(cam, option, b, count, way, name):
            return f"box {b} stands still on {seen[-1]}, its {'top' if way == 'up' else 'low'} end, short of {want}"
        d = digit_at(cam, b, n, name)
        if d == want:
            return ""
        if d in seen:
            return f"box {b} came round to {d} without showing {want}"
        seen.append(d)
    return f"box {b} never showed {want} in ten presses"


def others_pics(cam, b: int, count: int) -> dict:
    """Every box's picture but box b's on the frame on show, box b lit: what box b's stepping is judged by (moved_box).
    A picture is cut by the sides the pixel reader finds, and those of a box beside the lit one move with it (Focus
    Bracket's box 1 is x 393-446 beside box 2 lit and 393-450 with box 3 lit: two shapes of one digit, kit2_pass2
    269127/269128), so pictures are compared only with one box lit."""
    return {k: box_pic(cam, k) for k in range(count) if k != b}


def moved_box(cam, pics: dict) -> int | None:
    """The first box whose picture on the frame on show is not its picture in `pics`, taken with the same box lit."""
    return next((k for k, p in pics.items() if not same_pic(box_pic(cam, k), p)), None)


def put_number(cam, option, labels, look_: Look, span: tuple, digits: str, n: Named, opened: dict, name: str,
               first: str | None = None) -> tuple:
    """From the option lit: Right into the digit field (span: its first and last box), each box stepped to its digit of
    `digits` in turn (set_digit), never Enter on the way. `first`: the digits the boxes must open on (the first visit's,
    the look's). Returns (why the number cannot be put in, None), nothing chosen, or ("", the last box's reading) once
    every box shows its digit and no box moved but the one stepped: each box's stepping judged by every other box's
    picture before its first press and after its last (others_pics), the boxes outside the field by theirs as the first
    visit saw them (`opened`, filled then), the field's first box lit each time."""
    b0, b1 = span
    count = len(look_.labels)
    into_box(cam, option, labels, b0, count)
    if not opened:
        opened.update({k: box_pic(cam, k) for k in range(count) if not b0 <= k <= b1})
    k = moved_box(cam, opened)
    if k is not None:
        return f"box {k} is not as the first visit saw it", None
    for j, b in enumerate(range(b0, b1 + 1)):
        if j:
            into_next(cam, option, b, count)
        have = digit_at(cam, b, n, name)
        if first is not None and have != first[j]:
            raise Failed(f"{name}: box {b} holds {have!r}, the look read {first[j]!r}")
        if have != digits[j]:
            before = others_pics(cam, b, count)
            why = set_digit(cam, option, b, count, have, digits[j], n, name)
            if why:
                return why, None
            k = moved_box(cam, before)
            if k is not None:
                return f"box {k} changed while box {b} was stepped", None
    r = lit_read(cam, True)
    if key(r.text) != digits[-1]:
        raise Failed(f"{name}: box {b1} reads {r.text!r}, not {digits[-1]!r} ({cam.frame.path.name}); nothing chosen")
    return "", r


def read_number(cam, option, labels, look_: Look, span: tuple, n: Named, name: str) -> int:
    """From the option lit: Right through the digit field, each box's digit read as it is lit (digit_at), nothing
    stepped; the number they show."""
    b0, b1 = span
    count = len(look_.labels)
    into_box(cam, option, labels, b0, count)
    shown = []
    for b in range(b0, b1 + 1):
        if b > b0:
            into_next(cam, option, b, count)
        shown.append(digit_at(cam, b, n, name))
    return int("".join(shown))


def kept_number(n: Named, shown: int, held: int, out, name: str) -> None:
    """The last number's line written once the boxes show what the camera kept (read_number): as it stands where they
    show the number asked; where they show another and the download after that OK bears it out (a record moved to that
    number, or none moved and they show the number held), "applied": false with "asked" and "kept", nothing credited
    (Focus Bracket's 000 kept as 2); otherwise the walk stops."""
    asked = int(n.pending["value"])
    if shown == asked:
        flush(n, out)
        return
    ch = n.pending["changes"]
    if not any(c.get("after") == shown and isinstance(c.get("after"), int) and not isinstance(c.get("after"), bool)
               for c in ch) and (ch or shown != held):
        raise Failed(f"{name}: the boxes opened on {shown}, not {asked}, which the last OK chose, and its download does "
                     "not bear them out")
    print(f"   the camera kept {shown}, not {asked}, the number asked (its download bears the boxes out): nothing "
          "credited to it", flush=True)
    flush(n, out, applied=False, asked=str(asked), kept=str(shown))


def named_walk(cam, link, eyes, cycle, model, path, option, labels, look_: Look, base, out, run,
               numbers: list) -> None:
    """Each named number put into the option's digit field and chosen once (--number, the module's), one download each,
    as one attempt; the number held put back last. A number the boxes will not hold is said and passed over, nothing
    chosen. Each line waits for the next opening (read_number, kept_number); one still waiting when the walk stops is
    written saying what applied is not known."""
    name = f"{' > '.join(path)} > {option}"
    span = digit_field(look_)
    b0, b1 = span
    count = len(look_.labels)
    width = b1 - b0 + 1
    first = "".join(key(v) for v in look_.values[b0:b1 + 1])
    held = int(first)
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    n, opened = Named(), {}
    print(f"{name}: {look_.labels[b0]} holds {held}; the numbers {', '.join(map(str, numbers))} put in, one a download",
          flush=True)
    try:
        for k, number in enumerate([*numbers, held]):
            final = k == len(numbers)
            digits = str(number).zfill(width)
            row = open_row(cam, cycle, model, path)
            to_option(cam, option, labels)
            if n.pending is not None:
                kept_number(n, read_number(cam, option, labels, look_, (b0, b1), n, name), held, out, name)
                cam.press("menu")                   # back to the option lit, nothing changed
            why, r = put_number(cam, option, labels, look_, (b0, b1), digits, n, opened, name,
                                first if not opened else None)
            if why:
                if final:
                    raise Failed(f"{name}: the number held, {held}, cannot be put back: {why}")
                print(f"   {number}: not put in: {why}; nothing chosen", flush=True)
                close_screen(cam, link)
                continue
            values = list(look_.values)
            values[b0:b1 + 1] = list(digits)
            fields = look_.fields(values)
            field = next(f for f in fields if f["label"] == look_.labels[b0])
            lab = together(fields)
            chosen = enter(cam, option, labels, b1, count, r.text, box_pic(cam, b1))
            got = after_ok(cam, name, label=lab, back=lambda at=row: same_place(place(cam), at), info=False)
            row_frame = cam.frame.path.name
            to_shooting(link, eyes, "the download after OK")
            dat = link.download(f"{path[-1]}-number-{number}".replace(" ", "-"))
            wait_lock(time.monotonic(), eyes, clock=time)
            ch = camset.diff(camset.read(base), camset.read(dat))
            rec = {"path": [*path, option], "kind": "list", "via": VIA, "walk": "number", "index": ["number", number],
                   "field": look_.labels[b0], "value": field["value"], "label": lab, "fields": fields, "box": r.text,
                   "read_by": r.by, "shown": r.ocr, "box_vlm": r.vlm, "box_reader": r.reader, **votes_of(r),
                   "chosen_frame": chosen, "row_frame": row_frame, "dat": dat.name, "base": base.name,
                   **({"notice": got.notice} if got.notice else {}), "applied": got.applied, "final": final,
                   "attempt": attempt, "changes": changes_of(ch)}
            if final or not got.applied:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
            else:
                n.pending = rec
            print(f"   {look_.labels[b0]} = {number} ({lab}): " + ("refused by the camera" if not got.applied else
                  ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:4]) or "no change"), flush=True)
            if final and ch:
                raise Failed(f"{name}: {held} put back, {len(ch)} records still differ from the base")
    finally:
        flush(n, out, applied=None)          # never seen again: what applied is not known
    finish_attempt(run, attempt, name)


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
    ap.add_argument("--grid", action="store_true",
                    help="every pair of the option's two fields, one pair a download (Cont. Bracket's Exposure Value "
                         "and Number of Shots)")
    ap.add_argument("--number", type=int, action="append", default=None,
                    help="put this number into the option's digit field and choose it once (repeat it for more), the "
                         "number held put back last")
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
    ways = [w for w, on in (("--look", a.look), ("--box", a.box is not None), ("--grid", a.grid),
                            ("--number", a.number is not None)) if on]
    if len(ways) > 1:
        sys.exit(f"{' and '.join(ways)}: one way of proving a run, nothing was sent to the camera")
    if a.number is not None and min(a.number) < 0:
        sys.exit("--number: a number of zero or more, nothing was sent to the camera")
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
    if a.grid and (len(seen.labels) != 2 or len(seen.fields()) != 2):
        raise Failed(f"--grid: {a.option} draws {len(seen.labels)} boxes in {len(seen.fields())} fields, not two fields "
                     "of one box each; nothing chosen")
    if a.number is not None:
        span = digit_field(seen)
        if span is None:
            raise Failed(f"--number: {a.option} draws no one field of digit boxes side by side; nothing chosen")
        width = span[1] - span[0] + 1
        big = [n for n in a.number if len(str(n)) > width]
        if big:
            raise Failed(f"--number {big}: {seen.labels[span[0]]} has {width} digit boxes; nothing chosen")
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
    if a.grid:
        grid_walk(cam, link, eyes, cycle, model, path, a.option, labels, seen, base, out, run, a.most)
    elif a.number is not None:
        named_walk(cam, link, eyes, cycle, model, path, a.option, labels, seen, base, out, run, a.number)
    else:
        for b in boxes:
            walk_box(cam, link, eyes, cycle, model, path, a.option, labels, seen, b, base, out, run, a.most)


if __name__ == "__main__":
    main()
