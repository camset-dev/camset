"""Prove Reg. Custom Shoot Set: a Recall Custom hold's ticks (2026-10-30).

    .venv/bin/python -u kit/provers/customshoot_run.py --allow "Reg. Custom Shoot Set" --hold 1 [--first 0] [--count 13]

Reg. Custom Shoot Set is a never-open action row (camkit.safety): a run opens it only when given --allow "Reg. Custom
Shoot Set", the owner's word, refuses to start without it or with any other --allow (allowed), and every proof line
carries it ("allowance", runner.allowed_or_exit).

A hold's screen lists 13 items, each a tick (recalled with the hold or not) and a value, over two
buttons, Import Current Setting and Register. The cursor bar sits on the labels; Left moves it to
the tick column, where Enter flips the tick and Up/Down move as on the labels. Enter on a label
opens the item's value list instead. Down from the last item lands on Register, which writes the
hold ("Registered."); MENU cancels without writing.

Like kit/provers/grid_run.py: one visit per item puts the previous item's tick back and flips the next,
Register, a settings download, a diff with the start; a last visit puts the last tick back. An item
greyed by the hold's own values (Shutter Speed when its Shoot Mode is A) does not flip and is
recorded as refused. Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl as kind "checklist", path
["Reg. Custom Shoot Set", "Recall Custom hold N"]. At the end the start file goes back on, and hold 3
is opened and cancelled: a file does not set the registration working copy (0x18cb's fourth slot),
which follows the hold opened last (hold 3 in the owner's file).
"""
import argparse
import difflib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import LOCK_S, Failed, enter_path, option_key, to_shooting, vlm_option  # noqa: E402
from runner import (EXIT_UNRESTORED, add_allow_argument, add_scan_argument, allowed_or_exit, changes_of,  # noqa: E402
                    close_for_restore, close_screen, load_scan, menu_from_shooting, proofs_file, prover_session,
                    restoring, scan_position)

ROW = "Reg. Custom Shoot Set"
ITEMS = ["Shoot Mode", "Aperture", "Shutter Speed", "Drive Mode", "Cnt Shoot Speed Boost", "Exposure Comp.", "ISO",
         "Metering Mode", "Focus Mode", "Focus Area", "AF Lvl for Crossing", "AF Trk for Spd Chng", "AF On"]
ROW_Y0, ROW_DY = 97, 50                  # the first visible item's centre, the item pitch
REGISTER_BOX = (425, 360, 610, 405)
IMPORT_BOX = (30, 360, 395, 405)
LAST_OPENED = 3                          # the hold whose screen the owner's file shows was opened last


def allowed(allow, prover: str) -> str:
    """The proof lines' allowance for a run that opens Reg. Custom Shoot Set (this prover and customshoot_values.py):
    exits before anything connects unless --allow names the row, the owner's word, and nothing else
    (runner.allowed_or_exit then says it and gives its words)."""
    if not safety.named(ROW, allow):
        sys.exit(f"{prover}: {ROW} is never-open (an action); a run opens it only with the owner's word, --allow {ROW!r}")
    others = [x for x in allow if not safety.named(ROW, [x])]
    if others:
        sys.exit(f"{prover}: --allow names {others}: this run opens no never-open row but {ROW}")
    return allowed_or_exit(allow)


def lines(cam):
    return ocr.read([cam.frame.path])[cam.frame.path]


def orange(cam, box) -> float:
    x0, y0, x1, y1 = box
    return float(screen._orange(cam.frame.image)[y0:y1, x0:x1].mean())


def row_box(row: int, x0: int, x1: int) -> tuple:
    y = ROW_Y0 + ROW_DY * row
    return (x0, y - 22, x1, y + 22)


def on_ticks(cam) -> bool:
    """The cursor is in the tick column: a box around the tick, no bar over the label (0.03 against 0.83)."""
    s = cam.read()
    return s.kind == "checklist" and s.row is not None and orange(cam, row_box(s.row, 75, 600)) < 0.3 \
        and orange(cam, row_box(s.row, 18, 70)) > 0.3


def item_now(cam) -> int | None:
    """The item under the cursor, from its label (OCR: "AF Lvlfor Crossing" still matches)."""
    s = cam.read()
    if s.kind != "checklist" or s.row is None:
        return None
    k = option_key(ocr.text_in(lines(cam), row_box(s.row, 70, 420)))
    best, at = 0.0, None
    for i, item in enumerate(ITEMS):
        want = option_key(item)
        r = 1.0 if k.startswith(want) else difflib.SequenceMatcher(None, k[:len(want)], want).ratio()
        if r > best:
            best, at = r, i
    return at if best >= 0.8 else None


TRACK = {"at": None}                     # the item the presses since the last sure reading lead to


def tick(cam) -> bool | None:
    s = cam.read()
    if s.kind != "checklist" or s.row is None or s.row >= len(s.slots):
        return None
    return {"ticked": True, "empty": False}.get(s.slots[s.row])


def to_item(cam, k: int):
    """To item k. OCR names the item; where it cannot (2026-10-30: "ISO" read as "SO" beside the
    orange tick box), the count of presses since the last sure reading does."""
    for _ in range(4):
        at = item_now(cam)
        if at is None:
            at = TRACK["at"]
            if at is None:
                raise Failed(f"cannot tell which item the cursor is on ({cam.frame.path.name})")
            print(f"   (item read by counting: {ITEMS[at]!r}, {cam.frame.path.name})", flush=True)
        if at == k:
            TRACK["at"] = k
            return
        for _ in range(abs(k - at)):
            cam.press("down" if k > at else "up")
        TRACK["at"] = k
    raise Failed(f"item {ITEMS[k]!r} never took the cursor ({cam.frame.path.name})")


def open_hold(cam, cycle, model, h: int):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, ROW) is None:
        raise Failed(f"could not reach {ROW!r} by the scan")
    enter_path(cam, [ROW, f"Recall Custom hold {h}"], 0)
    cam.press("right")
    title = ocr.text_in(lines(cam), (0, 0, 640, 52))
    if cam.read().kind != "checklist" or option_key(f"Recall Custom hold {h}") not in option_key(title):
        raise Failed(f"Right on hold {h} opened {cam.read().kind} ({title!r}), not its items")
    TRACK["at"] = item_now(cam)          # the screen opens on Shoot Mode


def to_register(cam):
    to_item(cam, len(ITEMS) - 1)
    cam.press("down")
    if orange(cam, IMPORT_BOX) > 0.5:
        cam.press("right")
    word = ocr.text_in(lines(cam), REGISTER_BOX)
    if orange(cam, REGISTER_BOX) < 0.5 or option_key(word) != option_key("Register"):
        raise Failed(f"the cursor is not on Register ({word!r}, {cam.frame.path.name})")


def visit(cam, link, hdmi, cycle, model, h: int, cells: list) -> dict:
    """Flip `cells` in order, Register, download. Returns what the proof record needs."""
    open_hold(cam, cycle, model, h)
    cam.press("left")
    if not on_ticks(cam):
        raise Failed(f"Left did not move the cursor to the ticks ({cam.frame.path.name})")
    flipped, refused = [], []
    for k in sorted(cells):
        to_item(cam, k)
        before = tick(cam)
        cam.press("enter")
        after = tick(cam)
        if before is None or after is None:
            raise Failed(f"cannot read {ITEMS[k]!r}'s tick ({before} -> {after}, {cam.frame.path.name})")
        if after == before:
            refused.append({"box": k, "label": ITEMS[k], "frame": cam.frame.path.name})
            continue
        flipped.append({"box": k, "label": ITEMS[k], "ticked": after})
    to_register(cam)
    full = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"the screen reads like a confirmation ({safety.confirmation(full)}): no Register")
    chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
    cam.press("enter")
    said = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if cam.read().kind == "notice" and "registered" not in said.lower():
        raise Failed(f"after Register: {said[:90]!r} ({cam.frame.path.name})")
    row_frame = cam.frame.path.name
    to_shooting(link, hdmi, "the download after Register")
    time.sleep(1)
    dat = link.download(f"hold{h}-ticks{'-'.join(map(str, sorted(cells)))}")
    time.sleep(LOCK_S)
    return {"boxes": flipped, "refused": refused, "chosen_frame": chosen, "row_frame": row_frame, "vlm": seen_vlm,
            "dat": dat, "said": said.strip()}


def cancel_hold(cam, link, cycle, model, h: int):
    """Open hold h's screen and leave it with MENU: the working copy follows it."""
    open_hold(cam, cycle, model, h)
    close_screen(cam, link)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, required=True, choices=(1, 2, 3))
    add_scan_argument(ap)
    ap.add_argument("--context", default=None, help="the state these proofs are made in")
    ap.add_argument("--first", type=int, default=0, help="start at this item (the items before it proved already)")
    ap.add_argument("--count", type=int, default=99, help="prove this many items, then put the last back")
    add_allow_argument(ap)
    a = ap.parse_args()
    allowance = allowed(a.allow, "customshoot_run")
    h, n = a.hold, len(ITEMS)
    path = [ROW, f"Recall Custom hold {h}"]
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    hdmi = eyes_from_config(run)
    try:
        with proofs_file(run, a.context, {"allowance": allowance}) as out, \
                prover_session(run, hdmi, may_open=set(a.allow), say_start=False,    # may_open: the owner's word
                               close_eyes=False, exit_unrestored=False,         # carried to the end (below)
                               end_why="the settings download after the hold",
                               note="the start file left records apart (see above)") as s:
            cam, link, start = s.cam, s.link, s.start
            base = camset.read(start)
            print(f"start file: {start.name}; hold {h}, {n} items", flush=True)
            flipped = []
            upto = min(n, a.first + a.count)
            for i in list(range(a.first, upto)) + [n]:
                got = visit(cam, link, hdmi, cycle, model, h, flipped + ([i] if i < n else []))
                ch = camset.diff(base, camset.read(got["dat"]))
                greyed = any(r["box"] == i for r in got["refused"])
                label = ITEMS[i] if i < n else "(all back)"
                rec = {"path": path, "kind": "checklist", "index": i, "label": label, "boxes": got["boxes"],
                       "chosen_frame": got["chosen_frame"], "vlm": got["vlm"], "row_frame": got["row_frame"],
                       "dat": got["dat"].name, "base": start.name, "said": got["said"],
                       "notice": {"text": "greyed: the tick did not flip", "frame": got["refused"][0]["frame"]}
                       if greyed else None,
                       "applied": not greyed,
                       "changes": changes_of(ch)}
                out.write(json.dumps(rec) + "\n")
                out.flush()
                what = ", ".join(f"{b['label']!r} {'ticked' if b['ticked'] else 'unticked'}" for b in got["boxes"])
                brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:6]) or "no change"
                print(f"   {what or ('(greyed) ' + label):52s} {brief}", flush=True)
                flipped = [] if greyed or i >= n else [i]
                if i == n and ch:
                    print(f"   every tick back; {len(ch)} records still differ: {[c.key for c in ch][:8]}", flush=True)
        time.sleep(4)
        # the hold's working copy put back, which the start file does not cover: a STOP at cancel_hold's first press
        # (not a cleanup press) or an error leaves it where it is, which exits EXIT_UNRESTORED (runner.restoring)
        with restoring("putting the hold's working copy back"), Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "before putting the working copy back")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run, may_open=set(a.allow))     # the owner's word, as above
            try:
                cancel_hold(cam, link, cycle, model, LAST_OPENED)
            except Exception:
                close_for_restore(cam, link)        # cleanup presses before the link closes over an open dialog
                raise
            to_shooting(link, hdmi, "the last download")
            time.sleep(1)
            last = camset.diff(camset.read(start), camset.read(link.download("end")))
            print(f"at the end: {len(last)} records differ from the start file "
                  f"{[c.key for c in last][:8]}", flush=True)
    finally:
        hdmi.close()
    if not s.restored or last:
        # the first session's start file did not take, or the camera still differs after the working copy went
        # back: not as its start file, which the exit status says (runner.EXIT_UNRESTORED)
        sys.exit(EXIT_UNRESTORED)


if __name__ == "__main__":
    main()
