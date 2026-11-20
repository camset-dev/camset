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
is opened and cancelled (put_back): a file does not set the registration working copy (0x18cb's fourth slot,
WORKING_COPY), which follows the hold opened last (hold 3 in the owner's file); the session's restore check leaves that
record out (prover_session's expected) and the last download checks it.

A STOP means no press but cleanup MENU (camkit.link), here and in customshoot_values.py, which shares put_back and
run_end: after a STOP file made before the run or during it, a chain's limit or a first Ctrl-C, the put-back presses
nothing; the restore and the last download still happen. A STOP file there before the run: nothing pressed but MENU,
exit EXIT_UNRESTORED, the file named (a chain stops). A stop during the run: the start file back and checked, exit
EXIT_INCOMPLETE, and where the run had opened a hold's screen, that the working copy was not put back because the run
was told to stop, with the command that puts it back (customshoot_values.py --put-back). A failure or a refusal that
ends the run: the copy put back, exit EXIT_INCOMPLETE or EXIT_REFUSED. A restore that does not check out:
EXIT_UNRESTORED, as ever. A notice after Register counts only as the camera's "Registered." alone (registered_said).
"""
import argparse
import contextlib
import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, paths, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, enter_path, option_key, to_shooting, vlm_option  # noqa: E402
from proving.base import wait_lock  # noqa: E402
from proving.screens import later, settled  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_UNRESTORED, add_allow_argument, add_scan_argument,  # noqa: E402
                    allowed_or_exit, changes_of, close_for_restore, close_screen, load_scan, menu_from_shooting,
                    proofs_file, prover_session, restoring, scan_position)

ROW = "Reg. Custom Shoot Set"
ITEMS = ["Shoot Mode", "Aperture", "Shutter Speed", "Drive Mode", "Cnt Shoot Speed Boost", "Exposure Comp.", "ISO",
         "Metering Mode", "Focus Mode", "Focus Area", "AF Lvl for Crossing", "AF Trk for Spd Chng", "AF On"]
ROW_Y0, ROW_DY = 97, 50                  # the first visible item's centre, the item pitch
REGISTER_BOX = (425, 360, 610, 405)
IMPORT_BOX = (30, 360, 395, 405)
LAST_OPENED = 3                          # the hold whose screen the owner's file shows was opened last
# the record whose fourth slot, the registration working copy, follows the hold whose screen was opened last and no
# settings file sets back, by model: opening hold 2's screen moved it to hold 2's value (kit2_pass2 93341 -> 93435),
# the upload after that put every other hold record's fourth slot back but not this one (93435 -> 93436), and hold 3's
# screen opened and left put it back (93436 -> 93437, kit2_drive 00011 -> 00022). A run's restore check leaves it out
# (prover_session's expected) and its put-back's last download checks it. Its other three slots are the holds', a value
# each (2, 2 and 0 in the owner's file of 2026-10-31, 0 in all three after a reset) that no proof has named yet
WORKING_COPY = {"ILCE-1M2": "global:0x18cb"}
OPENED = {"hold": None}                  # the hold whose screen this run opened (open_hold), None until one is
REGISTERED = "registered"                # the camera's word on its notice after Register, and the whole of it
PROVER = "kit/provers/customshoot_values.py"     # its --put-back puts the working copy back as a run of its own


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
    OPENED["hold"] = h                   # the press went out: the working copy may follow this hold from here (run_end)
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
    chosen, seen_vlm = cam.frame.path.name, later(vlm_option, cam)
    cam.press("enter")
    said = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if cam.read().kind == "notice" and not registered_said(said):
        raise Failed(f"after Register: {said[:90]!r} ({cam.frame.path.name})")
    row_frame = cam.frame.path.name
    to_shooting(link, hdmi, "the download after Register")
    dat = link.download(f"hold{h}-ticks{'-'.join(map(str, sorted(cells)))}")     # camlink waits for the camera
    wait_lock(time.monotonic(), hdmi, clock=time)       # the menu's lock after it (camkit.session.wait_lock)
    return {"boxes": flipped, "refused": refused, "chosen_frame": chosen, "row_frame": row_frame, "vlm": seen_vlm,
            "dat": dat, "said": said.strip()}


def cancel_hold(cam, link, cycle, model, h: int):
    """Open hold h's screen and leave it with MENU: the working copy follows it."""
    open_hold(cam, cycle, model, h)
    close_screen(cam, link)


def registered_said(said: str) -> bool:
    """A notice after Register says the hold was written only when it is the camera's own word alone, "Registered."
    read by its letters (case, marks and spaces aside): "Not registered." or any other words are no registration. The
    frames on disk show none on this screen: every one read after Enter on Register (kit2_pass2) is the Reg. Custom
    Shoot Set list again; "Registered." is the camera's notice after Camera Set. Memory's registration."""
    return re.sub(r"[^a-z]+", " ", said.lower()).split() == [REGISTERED]


def working_copy_keys(run) -> frozenset:
    """The working copy's record (WORKING_COPY) of the camera whose runs `run` is in, as prover_session's expected;
    empty for a camera none is named for."""
    key = WORKING_COPY.get(Path(run.dir).parent.name.split("_fw")[0])
    return frozenset({key}) if key else frozenset()


@contextlib.contextmanager
def noted(stopped: list):
    """Inside a prover session: what ended its body (a stop, a refusal, a failure) kept in `stopped` for the run's end
    (run_end), then handed on to the session, which says it, closes and restores."""
    try:
        yield
    except Exception as e:
        stopped.append(e)
        raise


def told_to_stop(run, stopped: list) -> bool:
    """Whether the run was told to stop: a StopRequested ended its body, or its STOP is there now (a STOP file, made
    before the run or during it, a chain's limit, a first Ctrl-C)."""
    return any(isinstance(e, StopRequested) for e in stopped) or run.stop_requested()


def put_back_command(scan) -> str:
    """The command that puts the hold's working copy back as a run of its own (customshoot_values.py --put-back), with
    the eyes and the page scan this run used: the scan by its folder's name where it is in the camera's runs, as
    runner.load_scan names it, else by its path."""
    eyes = os.environ.get("CAMSET_EYES")
    scan, root = Path(scan), paths.run_root(required=False)
    named = scan.name if root is not None and scan.resolve().parent == root.resolve() else paths.shown(scan)
    return (f"{f'CAMSET_EYES={eyes} ' if eyes else ''}.venv/bin/python -u {PROVER} --allow {ROW!r} --put-back "
            f"--scan {named}")


def put_back(run, hdmi, cycle, model, allow, start: Path, ended: float, stopped: list) -> tuple:
    """The hold's working copy put back in a session of its own, after the run's session restored its start file: hold
    LAST_OPENED's screen opened and left with MENU (cancel_hold), then the last download compared with the start file,
    every record, the working copy's among them. Once the run was told to stop (told_to_stop) it presses nothing here:
    only the cleanup MENU that brings the shooting screen goes out, then the last download. A stop that comes while it
    presses (a press refused) is closed with cleanup MENU and kept in `stopped`. Returns (the records that differ from
    the start file at the end, whether the copy was put back). An error but a stop exits EXIT_UNRESTORED
    (runner.restoring)."""
    with restoring("putting the hold's working copy back"), Link(run) as link:
        hdmi.attach(link)
        to_shooting(link, hdmi, "before putting the working copy back")
        # the menu's lock after the session's last download, from when the session ended (camkit.session.wait_lock; the
        # link's open alone mostly outlasts it): it stood for 4 s before the link and 5 s after
        wait_lock(ended, hdmi, clock=time)
        done = False
        if told_to_stop(run, stopped):
            print("the run was told to stop: no press goes out to put the working copy back", flush=True)
        else:
            cam = LiveCamera(link, hdmi, run, may_open=set(allow))     # the owner's word for Reg. Custom Shoot Set
            try:
                cancel_hold(cam, link, cycle, model, LAST_OPENED)
                done = True
            except StopRequested as e:
                stopped.append(e)
                close_for_restore(cam, link, start)        # cleanup MENU out of whatever the put-back had opened
            except Exception:
                close_for_restore(cam, link, start)        # cleanup presses before the link closes over an open dialog
                raise
        to_shooting(link, hdmi, "the last download")      # camlink waits for the camera to allow the download
        last = camset.diff(camset.read(start), camset.read(link.download("end")))
        print(f"at the end: {len(last)} records differ from the start file {[c.key for c in last][:8]}", flush=True)
    return last, done


def run_end(run, restored: bool, last: list, stopped: list, opened, done: bool, keys: frozenset, scan) -> int:
    """The exit status of a Recall Custom run once its put-back is over, said in true words:
    - a STOP file there before the run started (Run._left): the run pressed nothing but MENU; EXIT_UNRESTORED, as it
      always exited, so a chain stops;
    - a restore that did not check out, or records other than the working copy's that differ at the end:
      EXIT_UNRESTORED, as ever;
    - a stop during the run (in its session or in the put-back): EXIT_INCOMPLETE, the start file back and checked;
      where this run opened a hold's screen (`opened`: OPENED as the session left it, or the hold --put-back opens)
      and the copy was not put back, that it was not, why, and the command that puts it back (put_back_command); where
      it opened none, that nothing else is owed. A refusal that ended the run EXIT_REFUSED, any other failure
      EXIT_INCOMPLETE, the copy put back;
    - else 0, or EXIT_UNRESTORED when the working copy's record differs after it was put back."""
    stop = next((e for e in stopped if isinstance(e, StopRequested)), None)
    left = getattr(run, "_left", None) or []
    if stop is not None and left:
        print(f"{left[0]} was there before this run started (an earlier stop): the run pressed nothing but MENU and "
              "registered nothing. Remove it to run.", flush=True)
        return EXIT_UNRESTORED
    others = [c.key for c in last if c.key not in keys]
    if not restored or others:
        return EXIT_UNRESTORED
    copy = [c.key for c in last if c.key in keys]
    if stopped:
        print("the start file is back and checked", flush=True)
        if not done and opened is not None:
            # (a stop alone leaves the copy where it is: put_back raises on any other error before this)
            print(f"the hold's working copy ({' '.join(sorted(keys)) or 'its record'}'s fourth slot, which no settings "
                  f"file sets back) was not put back, because the run was told to stop"
                  f"{'; it still differs from the start file' if copy else ''}. Put it back with:\n"
                  f"  {put_back_command(scan)}", flush=True)
        elif not done:
            print("no hold's screen was opened, so nothing else is owed", flush=True)
        if stop is None and isinstance(stopped[0], safety.Refused):
            return EXIT_REFUSED
        return EXIT_INCOMPLETE
    return EXIT_UNRESTORED if copy else 0


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
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    stopped = []                    # what ended the session's body, if anything (noted): run_end's words and exit
    keys = working_copy_keys(run)   # the working copy's record: the session's restore check leaves it out
    OPENED["hold"] = None
    try:
        with proofs_file(run, a.context, {"allowance": allowance}) as out, \
                prover_session(run, hdmi, may_open=set(a.allow), say_start=False,    # may_open: the owner's word
                               close_eyes=False, exit_unrestored=False,         # carried to the end (below)
                               end_why="the settings download after the hold", expected=keys,
                               note="the start file left records apart (see above)") as s, noted(stopped):
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
                       "chosen_frame": got["chosen_frame"], "vlm": settled(got["vlm"]), "row_frame": got["row_frame"],
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
        ended = time.monotonic()        # the session's last download (its end's, or its restore check's) came before
        opened = OPENED["hold"]         # whether this run opened a hold's screen: only then did the working copy move
        # the hold's working copy put back (put_back), which the start file does not cover; after a stop it presses
        # nothing, and run_end says what is owed
        last, done = put_back(run, hdmi, cycle, model, a.allow, start, ended, stopped)
    finally:
        hdmi.close()
    code = run_end(run, s.restored, last, stopped, opened, done, keys, a.scan)
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
