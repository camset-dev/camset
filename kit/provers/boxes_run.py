"""Prove a two-box screen: two values side by side, Left/Right between the boxes, Up/Down through a
box's values, OK applies both (S&Q and Time-lapse Frame Rate Settings, Movie mode, 2026-10-30).

    .venv/bin/python -u kit/provers/boxes_run.py --scan kit2_page_scan_movie --context "Movie mode" \\
        --row "S&Q Settings > Frame Rate Settings" --boxes "Rec Frame Rate,Frame Rate"
    .venv/bin/python -u kit/provers/boxes_run.py --scan kit2_page_scan_movie --context "Movie mode" \\
        --row ISO --boxes "ISO AUTO Minimum,ISO AUTO Maximum" --layout iso --rights 2   # ISO AUTO in use

The pixel reader does not know these screens, so this reads them by OCR: the breadcrumb must end in
the row's label and the footer must offer OK before anything but an arrow is pressed. The box under
the cursor is the orange one; each box's value is the text inside it. The box names are given on the
command line, as read off the camera's frame (OCR reads their icons as letters: "sad Rec Frame Rate").
First a look per box: Up until the value stops changing or comes round, then Down the same way (its
values in Down order), MENU. Then, as kit/prove_run.py does, per box: each value against the start,
the one held last; every choice is the row, Right, Left/Right to the box, Up/Down until the value is
read, OK, a settings download. Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl (kind "list", the box name
last in the path); the start file goes back on at the end and is checked.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, match, ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import LOCK_S, Failed, enter_any, option_key, to_shooting, vlm_option  # noqa: E402
from runner import (add_scan_argument, changes_of, close_screen, load_scan, menu_from_shooting,  # noqa: E402
                    proofs_file, prover_session, scan_position)

# each screen's two boxes, measured off the frames: S&Q / Time-lapse Frame Rate Settings, and ISO AUTO's
# Minimum / Maximum (ISO > ISO AUTO > Right, Movie mode, 2026-11-01)
LAYOUTS = {"framerate": [(100, 178, 339, 233), (356, 178, 595, 233)],
           "iso": [(130, 350, 373, 405), (381, 350, 625, 405)]}
BOXES = LAYOUTS["framerate"]
RIGHTS = 1                       # Rights from the row to the boxes (ISO: one into the list, one into the boxes)
CRUMB = (0, 0, 640, 40)
FOOTER = (0, 425, 640, 480)
LOOKALIKE = str.maketrans("рРоОкКсС", "pPoOkKcC")          # OCR's Cyrillic: "30р", "ОК"


def lines(cam):
    f = cam.frame
    return ocr.read([f.path])[f.path]


def value(cam, b: int) -> str:
    return re.sub(r"\s+", "", ocr.text_in(lines(cam), BOXES[b]).translate(LOOKALIKE))


def focus(cam) -> int | None:
    o = screen._orange(cam.frame.image)
    lit = [float(o[y0:y1, x0:x1].mean()) for x0, y0, x1, y1 in BOXES]
    return max(range(2), key=lambda i: lit[i]) if max(lit) > 0.3 else None


def open_row(cam, cycle, model, path):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"could not reach {path[0]!r} by the scan")
    enter_any(cam, path, 0)
    for _ in range(RIGHTS):
        cam.press("right")
    crumb = ocr.text_in(lines(cam), CRUMB)
    foot = ocr.text_in(lines(cam), FOOTER).translate(LOOKALIKE)
    if option_key(path[-1]) not in option_key(crumb) or not match.offers_ok(foot) or focus(cam) is None:
        raise Failed(f"Right on {path[-1]!r} did not open its boxes (breadcrumb {crumb!r}, footer {foot!r})")


def to_box(cam, b: int):
    for _ in range(3):
        if focus(cam) == b:
            return
        cam.press("right" if focus(cam) < b else "left")
    raise Failed(f"box {b} never took the cursor")


def look(cam, link, cycle, model, path, b: int) -> tuple[list, str]:
    """(the box's values in Down order, the value held)."""
    open_row(cam, cycle, model, path)
    to_box(cam, b)
    held = value(cam, b)
    for _ in range(40):                       # Up to one end (or once round)
        before = value(cam, b)
        cam.press("up")
        if value(cam, b) in (before, held):
            break
    vals = [value(cam, b)]
    for _ in range(40):
        cam.press("down")
        v = value(cam, b)
        if v == vals[-1] or v == vals[0]:
            break
        vals.append(v)
    close_screen(cam, link)
    if held not in vals or len(set(vals)) != len(vals) or not all(vals):
        raise Failed(f"{path[-1]} box {b}: the look read {vals} with {held!r} held")
    return vals, held


def choose(cam, link, hdmi, cycle, model, path, b, vals, target) -> dict:
    open_row(cam, cycle, model, path)
    to_box(cam, b)
    for _ in range(len(vals) + 1):
        now = value(cam, b)
        if now == vals[target]:
            break
        if now not in vals:
            raise Failed(f"{path[-1]} box {b}: read {now!r}, not one of its values")
        cam.press("down" if vals.index(now) < target else "up")
    if value(cam, b) != vals[target] or focus(cam) != b:
        raise Failed(f"{path[-1]} box {b}: {vals[target]!r} never came up")
    full = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"{path[-1]}: the screen reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)     # a second reader, kept with the proof
    cam.press("enter")
    after_ok = cam.frame.path.name
    to_shooting(link, hdmi, "the download after OK")
    time.sleep(1)
    dat = link.download(f"{path[-1]}-{b}-{target}")
    time.sleep(LOCK_S)
    return {"chosen_frame": chosen, "row_frame": after_ok, "dat": dat, "vlm": seen_vlm}


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


def prove(cam, link, hdmi, cycle, model, path, names, only, first, start, out) -> Path:
    """Each box's values proved, as the module says; with first (box, value), that value chosen in that box before
    them. Each proof is compared with its base: the start file, or the download made after first's choice, so the
    held value (the last proof of each box) is a return to the base and must change nothing. Returns the base; the
    caller puts the start file back, whatever first chose."""
    base = start
    if first:
        fb = names.index(first[0])
        vals, held = look(cam, link, cycle, model, path, fb)
        want = [i for i, v in enumerate(vals) if option_key(v) == option_key(first[1])]
        if len(want) != 1:
            raise Failed(f"--first: {first[1]!r} is not one value of {names[fb]}: {vals}")
        base = choose(cam, link, hdmi, cycle, model, path, fb, vals, want[0])["dat"]
        print(f"first {names[fb]} = {vals[want[0]]} (it held {held!r}): proofs start from {base.name}", flush=True)
    for b in [b for b in range(2) if only in (None, names[b])]:
        vals, held = look(cam, link, cycle, model, path, b)
        print(f"{names[b]}: {vals}, held {held!r}", flush=True)
        h = vals.index(held)
        for i in [i for i in range(len(vals)) if i != h] + [h]:
            got = choose(cam, link, hdmi, cycle, model, path, b, vals, i)
            ch = camset.diff(camset.read(base), camset.read(got["dat"]))
            r = {"path": path + [names[b]], "kind": "list", "index": i, "label": vals[i],
                 "shown": vals[i], "vlm": got["vlm"], "chosen_frame": got["chosen_frame"],
                 "row_frame": got["row_frame"],
                 "dat": got["dat"].name, "base": base.name, "applied": True, "boxes": True,
                 "changes": changes_of(ch)}
            out.write(json.dumps(r) + "\n")
            out.flush()
            print(f"  {vals[i]}: {len(ch)} records {[(c.key, c.before, c.after) for c in ch][:4]}",
                  flush=True)
            if i == h and ch:
                raise Failed(f"{names[b]}: back on {held!r}, {len(ch)} records still differ")
    return base


def main(argv=None):
    a, path, names, first = arguments(argv)
    global BOXES, RIGHTS
    BOXES, RIGHTS = LAYOUTS[a.layout], a.rights
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    hdmi = eyes_from_config(run)
    # the session ends restoring the start file, not the base --first made
    with proofs_file(run, a.context) as out, prover_session(run, hdmi) as s:
        prove(s.cam, s.link, hdmi, cycle, model, path, names, a.only, first, s.start, out)


if __name__ == "__main__":
    main()
