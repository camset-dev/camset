"""Checklists: a box's label (stars counted where it has no text), its tick and a radio sub-option's dot, the OK
button, and the prover that flips one box per visit and puts the last one back."""
import json
import re
import time
from pathlib import Path

import numpy as np

from camkit import camset, ocr, safety, screen
from camkit.frames import load
from page_model import same_text
from runner import changes_of

from . import nav
from .base import Failed, finish_attempt, frame_file
from .nav import after_download, to_row
from .putback import mirrored_boxes, put_back_leftovers, say_put_back
from .screens import option_key, place, same_place, vlm_option

CHECK_LATER = ("DISP",)          # DISP (Screen Disp) Set: radio sub-options inside, done last, by itself (--rows names it)
OK_RIGHT = ("DISP (Screen Disp) Set",)   # checklists whose OK/Cancel sit in a column right of the boxes (Down wraps)

DISP_MODES = {"global:0x04e5", "global:0x04e6"}   # the display mode in use, on the monitor and in the finder


def star_label(map_path, fr: str) -> str | None:
    """A star-only checklist box (Rating Set(Custom Key)) from pass 1's saved frame: "★" times the
    stars counted on the cursor row (OCR and the VLMs read "* ** *" and "1 star"). None when the frame
    is missing or the row shows any text."""
    f = frame_file(map_path, fr)
    if f is None:
        return None
    fr_ = load(f)
    s = screen.read(fr_)
    n = screen.box_stars(fr_.image, s)
    if not n or re.search(r"[A-Za-z0-9]", box_text(fr_, s)):
        return None
    return "★" * n


def box_text(f, s) -> str:
    """OCR on a checklist's cursor row, after its checkbox, inside its own column."""
    x0, x1 = s.boxes[0] if s.boxes else (10, 630)
    return ocr.text_in(ocr.read([f.path])[f.path], (max(60, x0 + 50), s.bar[0] - 2, min(620, x1), s.bar[1] + 2)).strip()


def check_box_label(cam) -> str:
    s, f = cam.read(), cam.frame
    if s.kind != "checklist" or not s.bar or s.focus != "rows":
        return ""
    return box_text(f, s)


def on_box(cam, labels: list, box: int) -> bool:
    """The checklist's cursor is on box `box`: star boxes by their star count, others by label."""
    if set(labels[box]) == {"★"}:
        return screen.box_stars(cam.frame.image, cam.read()) == len(labels[box])
    return is_box(check_box_label(cam), labels, box)


def is_box(read: str, labels: list, box: int) -> bool:
    """The row read is box `box`: the longest box label inside the reading is that box's. A row can
    show its value after its name and an icon before it ("4 Shutter Speed Range 1/60 - 1/200"), and
    one label can sit inside another ("Eye" in "Eye/Head")."""
    if same_text(read, labels[box]) or option_key(read) == option_key(labels[box]):
        return True
    inside = [i for i, l in enumerate(labels) if option_key(l) and option_key(l) in option_key(read)]
    return bool(inside) and max(inside, key=lambda i: len(option_key(labels[i]))) == box


def check_state(cam) -> bool | None:
    s = cam.read()
    if s.kind != "checklist" or s.focus != "rows" or s.row is None or s.row >= len(s.slots):
        return radio_state(cam)
    return s.slots[s.row] == "ticked"


def on_radio(cam) -> bool:
    """The cursor is on a radio sub-option: an indented bar the reader gives no slot (DISP Set's
    "Exposure: On" / "Exposure: TimeOut" under a box, 2026-10-30)."""
    s = cam.read()
    return s.kind == "checklist" and s.focus == "rows" and s.row is None and bool(s.bar) and \
        bool(s.boxes) and s.boxes[0][0] >= 20


def radio_state(cam) -> bool | None:
    """A radio sub-option's dot on the cursor row: red when chosen (~174,40,3, with or without the bar),
    grey when not (~186,186,186)."""
    if not on_radio(cam):
        return None
    y = (cam.read().bar[0] + cam.read().bar[1]) // 2
    r, g, b = cam.frame.image[y - 3:y + 3, 54:60].reshape(-1, 3).mean(0)
    if r > 140 and g < 90:
        return True
    if r > 140 and abs(r - g) < 25 and abs(g - b) < 25:
        return False
    return None


def focused_button(cam) -> str:
    """OCR of the orange button the cursor is on (OK or Cancel)."""
    s, f = cam.read(), cam.frame
    if s.kind != "checklist" or s.focus != "button" or not s.bar:
        return ""
    o = screen._orange(f.image)[s.bar[0]:s.bar[1] + 1]
    xs = np.nonzero(o.sum(axis=0) > 3)[0]
    if not len(xs):
        return ""
    # the widest unbroken orange span: a red tick in a box row beside the button (DISP Set's OK sits
    # level with "For viewfinder") must not widen the box
    runs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
    xs = max(runs, key=len)
    return ocr.text_in(ocr.read([f.path])[f.path], (int(xs.min()), s.bar[0], int(xs.max()) + 1, s.bar[1] + 1)).strip()


def read_boxes(cam, name: str, labels: list) -> tuple[set, set]:
    """Before the first visit: Right into the checklist, Down through every box reading its state, then
    MENU (Cancel) back to the row. Returns (the radio sub-options, the boxes ticked or chosen). Only
    lists with radio sub-options need it; others return at once with nothing read."""
    if not name.startswith(CHECK_LATER):
        return set(), set()
    cam.press("right")
    radio, held = set(), set()
    for i in range(len(labels)):
        if i:
            cam.press("down")
        if not on_box(cam, labels, i):
            raise Failed(f"{name}: reading the boxes, the cursor is on {check_box_label(cam)!r}, not {labels[i]!r}")
        state = check_state(cam)
        if state is None:
            raise Failed(f"{name}: cannot read {labels[i]!r} ({cam.frame.path.name})")
        if on_radio(cam):
            radio.add(i)
        if state:
            held.add(i)
    print(f"   boxes ticked or chosen: {[labels[i] for i in sorted(held)]}; radio sub-options: "
          f"{[labels[i] for i in sorted(radio)]}", flush=True)
    cam.press("menu")
    return radio, held


def prove_check_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    try:
        return _prove_check_row(cam, link, run, job, base_path, out, top)
    finally:
        nav.QUIET_SHOOTING = False


def _prove_check_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """A checklist, one box per visit: each visit puts the previous box back and flips the next, then
    OK on the OK button, download, diff with the row's base (so only the flipped box's records show);
    a last visit puts the last box back and must leave nothing changed. Each box is found by counting
    Downs from the top row and checked by its label; its tick is read before and after Enter.
    A box the camera will not untick on its own (the only one ticked: Rating Set's "Item not
    selected.", 2026-10-29) is proved afterwards together with the box below it, then both put back.
    Records written on every OK whatever the boxes (Rating Set's second copy of the 1-star box stays
    0 until the screen is first saved) do not fail the last visit; they are kept as "written_on_ok"."""
    path, name, labels = job["path"], " > ".join(job["path"]), job["labels"]
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    n = len(labels)
    partner: dict = {}                          # radio sub-option -> the one it is put back with
    nav.QUIET_SHOOTING = name.startswith(OK_RIGHT)
    row_place = place(cam)
    base = camset.read(base_path)
    last, flipped = base_path, []               # flipped: the boxes the last visit left changed
    every, applied = None, 0                    # record keys every applied box visit changed, and how many
    history, flips = [], []                     # each download's records differing from the start, and its flipped boxes
    put_back = None                             # why the last visit left records differing (all_back)

    def visit(boxes: list, index, label: str, first: bool, extra: dict) -> tuple:
        nonlocal last, every, applied
        if not first:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
        cam.press("right")
        if cam.read().kind != "checklist" or cam.read().focus != "rows":
            raise Failed(f"{name}: Right opened {cam.read().kind}, not the checklist's rows")
        at, changed_boxes = 0, []
        for box in sorted(boxes):                # Down only: the boxes in screen order
            for _ in range(box - at):
                cam.press("down")
            at = box
            if not on_box(cam, labels, box):
                seen = screen.box_stars(cam.frame.image, cam.read())
                raise Failed(f"{name}: the cursor is on {('★' * seen) if seen else check_box_label(cam)!r}, "
                             f"not {labels[box]!r}")
            before = check_state(cam)
            cam.press("enter")
            after = check_state(cam)
            if before is None or after is None or after == before:
                raise Failed(f"{name}: Enter did not flip {labels[box]!r} ({before} -> {after})")
            changed_boxes.append({"box": box, "label": labels[box], "ticked": after,
                                  **({"radio": labels[partner[box]]} if box in partner else {})})
        if name.startswith(OK_RIGHT):         # the buttons sit right of the boxes; Down only wraps round
            cam.press("right")
        for _ in range(n + 3):                  # down to the buttons; the first is OK (Enter on Rating Set)
            if cam.read().focus == "button":
                break
            cam.press("down")
        if cam.read().focus != "button" or option_key(focused_button(cam)) not in (option_key("OK"), option_key("Enter")):
            raise Failed(f"{name}: the cursor is not on OK ({focused_button(cam)!r})")
        chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
        cam.press("enter")
        s = cam.read()
        notice, refused = None, False
        if s.kind == "notice":
            text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
            if safety.confirmation(text_n):
                raise Failed(f"{name}: after OK a confirmation came up ({cam.frame.path.name})")
            refused = True
            notice = {"text": text_n, "frame": cam.frame.path.name}
            print(f"   refused: {text_n[:90]!r}", flush=True)
            cam.cancel_to_menu()
        elif s.kind != "shooting" and not same_place(place(cam), row_place):
            raise Failed(f"{name}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
        dat = link.download(f"{path[-1]}-box{index}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        history.append({ch.key: ch.after for ch in changes})
        flips.append({} if refused else {b["box"]: b["ticked"] for b in changed_boxes})
        rec = {"path": path, "kind": "checklist", "index": index, "label": label, "attempt": attempt,
               "boxes": changed_boxes, "chosen_frame": chosen, "vlm": seen_vlm, "row_frame": cam.frame.path.name, "dat": dat.name,
               "base": base_path.name, "notice": notice, "applied": not refused, **extra,
               "changes": changes_of(changes)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
        what = ", ".join(f"{b['label']!r} {'ticked' if b['ticked'] else 'unticked'}" for b in changed_boxes)
        print(f"   {what:48s} {brief}", flush=True)
        last = dat
        after_download(cam, done)
        if not refused and label != "(all back)" and not extra:      # one-box visits only
            applied += 1
            every = {ch.key for ch in changes} if every is None else every & {ch.key for ch in changes}
        return refused, changes

    def all_back(changes):
        nonlocal put_back
        # DISP Set: unticking the display mode in use moves the current mode (0x04e5 monitor, 0x04e6
        # finder) and ticking it again does not move it back (2026-10-30); the start file does
        rest = [ch for ch in changes if (applied < 2 or ch.key not in (every or set())) and
                not (name.startswith(OK_RIGHT) and ch.key in DISP_MODES)]
        if rest:
            # a record the camera keeps once touched (Rating Set(Custom Key)'s second copies, 0 until a box is
            # ticked and 1 from then on, 2026-11-07): no failure, the session's upload puts it back
            why = put_back_leftovers(rest, history) or mirrored_boxes(rest, history, flips, labels)
            if why is None:
                raise Failed(f"{name}: every box back, {len(rest)} records still differ")
            say_put_back(name, why)
            put_back = why
        if changes:
            print(f"   written on every OK: {[ch.key for ch in changes]}", flush=True)

    radio, held = read_boxes(cam, name, labels)
    if radio:
        to_row(cam, path, top, row_place)
    groups, g = [], []                          # runs of radio sub-options under one box
    for i in range(n):
        if i in radio:
            g.append(i)
        elif g:
            groups.append(g)
            g = []
    if g:
        groups.append(g)
    chosen = {i: next((j for j in grp if j in held), None) for grp in groups for i in grp}
    # a radio sub-option's partner: the one chosen before (for the one chosen, the first other)
    partner = {i: (chosen[i] if chosen[i] != i else next(j for grp in groups if i in grp for j in grp if j != i))
               for i in radio if chosen.get(i) is not None}
    alone = []                                  # boxes refused on their own
    for i in range(n + 1):
        if i < n and i in radio and i in held:  # the chosen sub-option: its partners' visits prove it
            print(f"   {labels[i]!r} is the chosen sub-option; its partners prove it", flush=True)
            continue
        boxes = flipped + ([i] if i < n else [])
        refused, changes = visit(boxes, i, labels[i] if i < n else "(all back)", bool(radio) is False and i == 0, {})
        if refused and i < n:
            alone.append(i)
        back = chosen.get(i) if i in radio else i       # a radio is put back by choosing the one chosen before
        flipped = [] if refused or i >= n or back is None else [back]
        if i == n:
            all_back(changes)
    for i in alone:                             # with the box below it changed too (proved on its own)
        j = (i + 1) % n
        refused, _ = visit([i, j], i, labels[i], False, {"together_with": labels[j]})
        if refused:
            print(f"   {labels[i]!r} refused together with {labels[j]!r} too", flush=True)
            continue
        _, changes = visit([i, j], n, "(all back)", False, {})
        all_back(changes)
    finish_attempt(run, attempt, name, put_back)
    to_row(cam, path, top, row_place)
    return last
