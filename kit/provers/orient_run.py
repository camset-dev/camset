"""Prove a carousel row with the camera held vertically (by hand): Switch V/H AF Area keeps Focus
Area per orientation.

    .venv/bin/python -u kit/provers/orient_run.py --grip down [--row "Focus Area"]
    .venv/bin/python -u kit/provers/orient_run.py --grip down --af-point

Held vertically (Vertical Display On) the camera draws the shooting screen and the dialogs opened
from the menu in their portrait arrangement; the menu pages stay level (2026-10-30). HDMI shows a
portrait screen turned a quarter, the SDK's picture (the OSD eyes) unturned but squeezed into its
640 x 480 (2026-11-16). The prover's dialog reader can read neither, so this one reads the dialog
by OCR on the frame made upright, 480 x 640 (upright: HDMI's turned back, the SDK's resized): the
title, and the option under the cursor in orange under it.

As kit/prove_run.py does for a carousel row: each option against the row's base (the option the
row opened on last), then each option with a second axis (runs/<model>_fw<fw>/kit2_axes/axes.json), every axis
value against that option's own base (the value it held last). Every choice is the row, Right,
Up until the option is read, Right until the axis value is read, OK, then a settings download. The screen after OK is
read by proving.commit.after_ok (a notice's words both as the frame is and made upright): an option the camera refuses
is written "applied": false with its notice.
The keys are not assumed to move one way: grip down, Down steps back through the carousel.
Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl tagged with the context, each keeping the vision model's
reading of the chosen option ("vlm") beside OCR's ("shown"); the start file goes back on at the end and is checked.

--af-point: Spot chosen the same way, then the AF point moved with the multi-selector on the
shooting screen; what changed goes to runs/<model>_fw<fw>/kit2_pass2/afpoint.jsonl.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# camkit before any other package, as in every kit program: a Python without the kit's packages is told so (camkit/start.py)
from camkit import camset, live, ocr, safety  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from pass3_run import labels_of  # noqa: E402
from prove_run import (AXES, LOCK_S, Failed, enter_any, main_name, option_key, to_shooting,  # noqa: E402
                       vlm_option)
from proving.commit import REFUSED_WORDS, after_ok  # noqa: E402
from proving.screens import later, settled  # noqa: E402
from runner import (add_scan_argument, changes_of, close_screen, load_scan, menu_from_shooting,  # noqa: E402
                    proofs_file, prover_session, read_json, scan_position)

# np.rot90's k that turns HDMI's frame upright: grip down the picture is turned a quarter anticlockwise (the SDK's
# picture is never turned: upright resizes it)
GRIPS = {"down": -1, "up": 1}
# upright frame (480 x 640): the dialog's title, and the option under the cursor (lines starting at
# the left edge: Custom's area frame beside the name reads as a stray "7")
TITLE = (0, 0, 480, 52)
LABEL = (0, 52, 300, 105)
# the upright frame's footer band: below the line at y 586 the help glyph's "?" and the keys (MENU Cancel, OK), above it
# the title, the option, the second axis and the carousel strip (kit2_a1fin_framepos_edges_gripdown_vdon2's
# 00051_up_upright.png); camkit.live.FOOTER_TOP is the level frame's
FOOTER_TOP = 580


def squeezed(f) -> bool:
    """Whether the frame `f` is the SDK's picture of the camera's screen (the OSD eyes: camkit.frames' source "osd"),
    which shows a portrait screen (held vertically with Vertical Display On: Focus Area's carousel, the shooting screen)
    unturned but squeezed into its 640 x 480, where HDMI shows the same picture turned a quarter (2026-11-16:
    kit2_a1fin_framepos_edges_gripdown_vdon's 00048_right.png resized to 480 x 640 matches kit2_pass2's
    116917_right_upright.png element for element). A frame of no source is taken for HDMI's, as before."""
    return getattr(f, "source", "") == "osd"


def upright(cam, k: int, shots: Path) -> list:
    """OCR lines of the frame on screen made upright, the 480 x 640 portrait picture TITLE and LABEL are measured on
    (saved beside the evidence, not numbered): HDMI's turned back a quarter (np.rot90 by k, GRIPS), the SDK's picture
    resized, never turned (squeezed)."""
    f = cam.frame
    path = shots / f"{f.path.stem}_upright.png"
    if squeezed(f):
        Image.fromarray(f.image).resize((480, 640), Image.LANCZOS).save(path)
    else:
        Image.fromarray(np.ascontiguousarray(np.rot90(f.image, k))).save(path)
    return ocr.read([path])[path]


def reading(cam, k: int, shots: Path) -> tuple[str, str]:
    """(title, option) on the portrait dialog, made upright."""
    return dialog_reading(cam, k, shots)[:2]


def dialog_reading(cam, k: int, shots: Path) -> tuple[str, str, str, str]:
    """(title, option, whole text, text above the footer) on the portrait dialog, made upright: what the camera judges
    its Enter on (camkit.live.UprightDialog), as it judges a level dialog's on its frame (text_of, body_of, the lit
    option), the footer's help glyph and its "?" left out of the body as there."""
    lines = upright(cam, k, shots)
    title = ocr.text_in(lines, TITLE)
    opt = " ".join(ln.text for ln in lines if ln.inside(LABEL) and ln.x < 30)
    return (title, re.sub(r"[^A-Za-z0-9)]+$", "", opt.strip()), ocr.text_in(lines, (0, 0, 480, 640)),
            ocr.text_in(lines, (0, 0, 480, FOOTER_TOP)))


def axis_of(label: str, axes: dict):
    """The axis option ("Spot", "Custom 1", "Tracking") a carousel label belongs to, or None."""
    return next((o for o in axes if option_key(o) in (option_key(label), option_key(main_name(label, "dialog")))), None)


def which(text: str, labels: list, axes: dict):
    """(carousel index, axis value index or None) of a reading, or None when it is not one option."""
    t = option_key(text)
    hits = []
    for i, lab in enumerate(labels):
        o = axis_of(lab, axes)
        if o:
            hits += [(i, v) for v, val in enumerate(axes[o]["values"]) if option_key(val) == t]
        elif option_key(lab) == t:
            hits.append((i, None))
    return hits[0] if len(hits) == 1 else None


def open_row(cam, cycle, model, row: str, k: int, shots: Path):
    """From the shooting screen: MENU, the row, Right; the portrait dialog with the row's title, made upright."""
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, row) is None:
        raise Failed(f"could not reach {row!r} by the scan")
    enter_any(cam, [row], 0)
    cam.press("right")
    title, _ = reading(cam, k, shots)
    if option_key(row) not in option_key(title):
        raise Failed(f"Right on {row!r} did not open its dialog (title {title!r})")


def step_to(cam, k, shots, labels, axes, key: str, done, most: int, what: str):
    """Press `key` until done(reading) holds, reading after each press."""
    for _ in range(most + 1):
        _, opt = reading(cam, k, shots)
        if done(which(opt, labels, axes)):
            return opt
        cam.press(key)
    raise Failed(f"{what} never came under the cursor (last read {opt!r})")


def choose(cam, link, hdmi, run, cycle, model, row, k, labels, axes, i, v=None) -> dict:
    """Open the row, put carousel option i (and axis value v) under the cursor, OK, download."""
    shots = run.dir / "upright"
    open_row(cam, cycle, model, row, k, shots)
    opt = step_to(cam, k, shots, labels, axes, "up", lambda w: w is not None and w[0] == i, len(labels),
                  f"{row}: {labels[i]!r}")
    if v is not None:
        o = axis_of(labels[i], axes)
        opt = step_to(cam, k, shots, labels, axes, "right", lambda w: w == (i, v), len(axes[o]["values"]),
                      f"{row}: {axes[o]['values'][v]!r}")
    _, opt = reading(cam, k, shots)
    full = ocr.text_in(upright(cam, k, shots), (0, 0, 480, 640))
    if safety.confirmation(full):
        raise Failed(f"the dialog reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, seen_vlm = cam.frame.path.name, later(vlm_option, cam)     # a second reader, kept with the proof
    cam.press("enter")
    row_frame = cam.frame.path.name
    # what the camera did with it (proving.commit.after_ok): a refusal or a notice closed with MENU, never OK, its words
    # read level and upright (notice_text); the menu closed (Focus Area's OK closes it); a screen of no known kind is no
    # information screen taken here (a portrait screen reads so): it fails the row
    got = after_ok(cam, row, label=opt, info=False, read=lambda c: notice_text(c, k, shots))
    to_shooting(link, hdmi, "the download after OK")
    time.sleep(1)
    dat = link.download(f"{row}-{'axis-' if v is not None else ''}{v if v is not None else i}")
    time.sleep(LOCK_S)
    return {"shown": opt, "vlm": seen_vlm, "chosen_frame": chosen, "row_frame": row_frame, "dat": dat, "outcome": got}


def notice_text(cam, k: int, shots: Path) -> str:
    """A notice's whole text after OK, held vertically: read on the frame as it is (camkit.live.text_of) and made upright
    (upright), as nobody has seen which way the camera draws a notice there; the reading that holds a question or a
    refusal (safety.confirmation, proving.commit.REFUSED_WORDS), so either is never missed, else the longer."""
    level, turned = live.text_of(cam), ocr.text_in(upright(cam, k, shots), (0, 0, 480, 640))
    for t in (level, turned):
        if safety.confirmation(t) or REFUSED_WORDS.search(t):
            return t
    return max((level, turned), key=len)


def af_point(cam, link, hdmi, run, cycle, model, row, k, labels, axes, grip):
    """Spot under the cursor, then the multi-selector on the shooting screen (it moves the AF point
    in Spot; on the shooting screen the control wheel's keys do what they are assigned, so only the
    multi-selector is pressed), then a download diffed against the one after Spot was chosen."""
    spot = next(n for n, lab in enumerate(labels) if axis_of(lab, axes) == "Spot")
    got = choose(cam, link, hdmi, run, cycle, model, row, k, labels, axes, spot)
    if not got["outcome"].applied:
        raise Failed(f"{row}: the camera refused Spot (its notice closed with MENU): no AF point to move")
    base = got["dat"]
    cam.refresh("af-point-start")
    frames = [cam.frame.path.name]
    presses = ["ms_left"] * 4 + ["ms_up"] * 3
    for key in presses:
        cam.press(key, on_shooting=key)         # named: on the shooting screen this press moves the AF point
        frames.append(cam.frame.path.name)
        if cam.read().kind != "shooting":
            raise Failed(f"{key} left the shooting screen ({cam.read().kind})")
    time.sleep(1)
    moved = link.download("af-point-moved")
    time.sleep(LOCK_S)
    ch = camset.diff(camset.read(base), camset.read(moved))
    with open(run.dir / "afpoint.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"grip": grip, "focus_area": labels[spot], "presses": presses, "frames": frames,
                            "base": base.name, "dat": moved.name,
                            "changes": changes_of(ch)}) + "\n")
    print(f"AF point, grip {grip}: {len(ch)} records {[(c.key, c.before, c.after) for c in ch]}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grip", choices=sorted(GRIPS), required=True, help="which way the camera is held")
    ap.add_argument("--row", default="Focus Area")
    ap.add_argument("--context", default=None, help="default: Switch V/H AF Area = AF Point + AF Area, camera grip GRIP")
    add_scan_argument(ap)
    ap.add_argument("--only", action="append", default=None,
                    help="parts to prove: 'carousel', or an axis option (Spot, Custom 1, Tracking); default all")
    ap.add_argument("--af-point", action="store_true",
                    help="instead of the row's proofs: choose Spot, move the AF point with the multi-selector on "
                         "the shooting screen, list what changed (runs/<model>_fw<fw>/kit2_pass2/afpoint.jsonl)")
    a = ap.parse_args()
    k, row = GRIPS[a.grip], a.row
    context = a.context or f"Switch V/H AF Area = AF Point + AF Area, camera grip {a.grip}"
    labels, kind = labels_of([row])
    if kind != "dialog":
        sys.exit(f"{row!r} is a {kind}, not a carousel")
    axes = {o: info for o, info in read_json(AXES).get(row, {}).items() if len(info["values"]) > 1}
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    (run.dir / "upright").mkdir(exist_ok=True)
    hdmi = eyes_from_config(run)
    with proofs_file(run, context) as out, prover_session(run, hdmi) as s:
        cam, link, start = s.cam, s.link, s.start

        def record(i, got, base, extra):
            ch = camset.diff(camset.read(base), camset.read(got["dat"]))
            done = got["outcome"]
            r = {"path": [row], **extra, "shown": got["shown"], "vlm": settled(got["vlm"]), "chosen_frame": got["chosen_frame"],
                 "row_frame": got["row_frame"], "dat": got["dat"].name, "base": base.name,
                 "changes": changes_of(ch), **({"notice": done.notice} if done.notice else {}), "applied": done.applied,
                 "upright": True}
            out.write(json.dumps(r) + "\n")
            out.flush()
            print(f"  {extra.get('option', row)} [{extra['index']}] {extra['label']!r} (read {got['shown']!r}): "
                  f"{len(ch)} records {[(c.key, c.before, c.after) for c in ch][:4]}", flush=True)
            return ch

        if a.af_point:
            af_point(cam, link, hdmi, run, cycle, model, row, k, labels, axes, a.grip)
        else:
            # the carousel: every option against the start, the one held last
            todo = [o for o in axes if not a.only or o in a.only]
            open_row(cam, cycle, model, row, k, run.dir / "upright")
            held = which(reading(cam, k, run.dir / "upright")[1], labels, axes)
            close_screen(cam, link)
            if held is None:
                raise Failed(f"{row}: the option it opened on could not be read")
            print(f"{row} opened on {labels[held[0]]!r} (axis {held[1]})", flush=True)
            for i in ([i for i in range(len(labels)) if i != held[0]] + [held[0]]
                      if not a.only or "carousel" in a.only else []):
                got = choose(cam, link, hdmi, run, cycle, model, row, k, labels, axes, i)
                o = axis_of(labels[i], axes)
                w = which(got["shown"], labels, axes)
                lab = axes[o]["values"][w[1]] if o and w and w[1] is not None else labels[i]
                ch = record(i, got, start, {"kind": "dialog", "index": i, "label": lab})
                if i == held[0] and ch:
                    raise Failed(f"{row}: back on {lab!r}, {len(ch)} records still differ from the start")
            # each second axis: every value against the option's own base, the one held last
            for o in todo:
                info = axes[o]
                i = next(n for n, lab in enumerate(labels) if axis_of(lab, axes) == o)
                base = link.download(f"{row}-{o}-base")
                time.sleep(LOCK_S)
                open_row(cam, cycle, model, row, k, run.dir / "upright")
                step_to(cam, k, run.dir / "upright", labels, axes, "up", lambda w, i=i: w is not None and w[0] == i,
                        len(labels), f"{row}: {o!r}")
                v0 = which(reading(cam, k, run.dir / "upright")[1], labels, axes)[1]
                close_screen(cam, link)
                n = len(info["values"])
                for v in [(v0 + d) % n for d in range(1, n)] + [v0]:
                    got = choose(cam, link, hdmi, run, cycle, model, row, k, labels, axes, i, v)
                    record(i, got, base, {"kind": "axis", "option": o, "index": v,
                                          "label": info["values"][v], "final": False})


if __name__ == "__main__":
    main()
