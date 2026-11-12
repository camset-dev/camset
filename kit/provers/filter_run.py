"""Prove Playback Filter Condition: a checklist whose boxes open a chooser each (2026-11-07).

    .venv/bin/python -u kit/provers/filter_run.py [--in Movie] [--scan RUN] [--run kit2_pass2] [--items Protect ...]

The row's screen lists the conditions a filtered playback can take (Date, Folder, Still Images/Movies, Rating,
Protect, Shot Mark, FTP Transfer Status, Smartphone Trans State, Voice Memo) with Cancel Filter and Execute Filter
under them. Enter on a box opens that condition's chooser instead of ticking it; choosing ticks the box and shows the
choice after its name, and the camera writes the condition to the settings file (Protect = No wrote three records).
The generic checklist prover expects Enter to tick, so it failed the row ("Enter did not flip 'Date'"); and the
camera answers "There are no target images." for every box while the playback target holds no image (the a1 II's
cards once, 2026-10-29).

Each item is proved as a list row of its own, path ["Playback Filter Condition", item]: its chooser's options in
turn, a download and a diff against the start file after each, the proofs tagged as one attempt. No option gives the
start state back (a box starts unticked, "-"), so the attempt is recorded finished with its records "not offered",
and the start file goes back on between items and at the end (every session starts from a known file and restores
it). A chooser that is no list (Date's calendar, Folder's list of the card's folders: data, not options) is noted and
left with MENU. Execute Filter, Cancel Filter and Fn (Reset Condition, a confirmation) are never pressed.

--run other than the main run (kit2_pass2) marks that run as one of the camera's proof runs (camkit.runs.PROOF_RUN), so
kit/pass2_report.py reads its proofs beside the main run's; a run made only to check the kit loses its mark by hand.

--untick (2026-11-09) also proves each box's value 0, "Not ticked": with the box ticked (by the item's own proof just
made, else by choosing its chooser's option in force again), the cursor goes to the box column, a download is made, Enter
unticks the box, the screen must show it unticked, and a second download is diffed against the first. The proof is
a list row's too (label "Not ticked", its own attempt), `applied` only when the box's own record went 1 -> 0.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from camkit import camset, definitions, ocr  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, LinkError  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.runs import MAIN_RUN, Run, mark_proof_run  # noqa: E402
from mode_switch import find, open_menu  # noqa: E402
from runner import (EXIT_UNRESTORED, LATEST_SCAN, add_in_argument, close_for_restore, end_session, in_mode,  # noqa: E402
                    load_scan, proofs_file, restore_checked, scan_arg)
from prove_run import (Failed, after_download, bar_text, check_box_label, check_state,  # noqa: E402
                       finish_attempt, focused_button, is_box, move_to, option_key, to_shooting, vlm_option)

ROW = "Playback Filter Condition"
ITEMS = ["Date", "Folder", "Still Images/Movies", "Rating", "Protect", "Shot Mark", "FTP Transfer Status",
         "Smartphone Trans State", "Voice Memo"]
DATA = {"Date", "Folder"}                     # choosers of data on the card, not of options


def download(link, name: str, say) -> Path:
    """A download the camera can refuse for a moment after the menu closes ("camera does not allow a settings
    download now"): asked again a few times."""
    for i in range(6):
        try:
            return link.download(name)
        except LinkError as e:
            if "does not allow" not in str(e) or i == 5:
                raise
            say(f"the camera is not ready for a download yet ({e}); waiting")
            time.sleep(4)


def text(cam) -> str:
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))


def box_key(definition: dict, item: str) -> str | None:
    """The record of an item's box in a definition ("Playback Filter Condition: <item> (box)"), None if it has none."""
    want = f"{ROW}: {item} (box)"
    return next((x.get("key") for x in definition.get("settings", []) if x.get("name") == want), None)


def untick_applied(changes: list, key: str | None) -> bool:
    """The untick took: the box's own record went 1 -> 0 (any record that did, when the definition names none)."""
    return any(c["key"] == key if key else True for c in changes if c["before"] == 1 and c["after"] == 0)


def box_column_state(kind: str, focus, row, boxes, slots) -> bool | None:
    """From a read screen: True/False when a checklist's cursor is the square on a box (box column: a row with no bar
    across it, so no `boxes`) and the box is ticked/unticked, else None (value column, a chooser, another screen)."""
    if kind != "checklist" or focus != "rows" or row is None or boxes or row >= len(slots):
        return None
    return slots[row] == "ticked"


def to_box(cam, i: int):
    """The checklist's cursor on item i: to the top first (the screen reopens on the box used last), then Down."""
    for _ in range(len(ITEMS) + 2):
        if is_box(box_label(cam), ITEMS, 0):
            break
        cam.press("up")
        if cam.read().kind != "checklist":
            raise Failed(f"Up left the checklist ({cam.read().kind}, {cam.frame.path.name})")
    else:
        raise Failed(f"the top box {ITEMS[0]!r} was not reached ({box_label(cam)!r})")
    for _ in range(i):
        cam.press("down")
    if cam.read().kind != "checklist" or not is_box(box_label(cam), ITEMS, i):
        raise Failed(f"the cursor is not on {ITEMS[i]!r} ({box_label(cam)!r}, {cam.frame.path.name})")


def open_row(cam, cycle, model):
    find(cam, cycle, model, ROW)
    cam.press("right")
    if cam.read().kind != "checklist":
        raise Failed(f"Right on {ROW!r} opened {cam.read().kind} ({cam.frame.path.name}): {text(cam)[:80]!r}")


def box_label(cam) -> str:
    """The item under the cursor, in the box column (the cursor a square on the box) or the value column (a bar
    across the row, where Right and a choice leave it)."""
    s, f = cam.read(), cam.frame
    if s.kind != "checklist" or not s.bar:
        return ""
    reads = [check_box_label(cam)] if s.focus == "rows" else []
    reads.append(ocr.text_in(ocr.read([f.path])[f.path], (60, s.bar[0] - 2, 500, s.bar[1] + 2)).strip())
    # on the orange bar OCR can drop the name and keep the value ("Yes" for "Protect  Yes"): the read that names
    # an item wins
    return next((r for r in reads if any(is_box(r, ITEMS, i) for i in range(len(ITEMS)))), reads[-1])


def on_filter_list(cam) -> bool:
    """The filter's own checklist is on screen (a row names one of its items), not a chooser (Rating's grid is a
    checklist too, of star boxes)."""
    return cam.read().kind == "checklist" and any(is_box(box_label(cam), ITEMS, i) for i in range(len(ITEMS)))


def open_chooser(cam):
    """The chooser of the box under the cursor: Right opens it from the value column, or moves the cursor there from
    the box column, where Enter then opens it (Enter in the box column ticks or unticks a box that holds a value)."""
    cam.press("right")
    if on_filter_list(cam):
        cam.press("enter")


def list_labels(cam) -> list:
    """The chooser's options, read from its top down (it opens on the option in force)."""
    for _ in range(12):
        if cam.read().at_start:
            break
        cam.press("up")
    labels = []
    for _ in range(16):
        labels.append(bar_text(cam))
        if cam.read().at_end:
            break
        cam.press("down")
    return labels


def prove_item(cam, link, run, cycle, model, i: int, start: Path, out, say) -> int:
    """Item i's chooser, every option; the number of proofs written."""
    name = f"{ROW} > {ITEMS[i]}"
    base = camset.read(start)
    open_row(cam, cycle, model)
    to_box(cam, i)
    open_chooser(cam)
    s = cam.read()
    if s.kind == "checklist" and ITEMS[i] == "Rating":
        return prove_grid(cam, link, run, cycle, model, i, start, out, say)
    if s.kind != "list":
        t = text(cam)
        say(f"{name}: Enter opened {s.kind} ({cam.frame.path.name}), not a list: {t[:90]!r}; left with MENU")
        run.log("filter_item", item=ITEMS[i], opened=s.kind, frame=cam.frame.path.name, text=t[:200])
        cam.press("menu")
        return 0
    labels = list_labels(cam)
    say(f"{name}: {len(labels)} options {labels}")
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    cur, n, written = len(labels) - 1, len(labels), set()
    for j in range(n):
        if j:
            open_row(cam, cycle, model)
            to_box(cam, i)
            open_chooser(cam)
            if cam.read().kind != "list":
                raise Failed(f"{name}: {cam.read().kind} ({cam.frame.path.name}), not the chooser, for option {j}")
            cur = j - 1                           # the chooser opens on the option chosen last
        move_to(cam, cur, j, n)
        shown, chosen, seen = bar_text(cam), cam.frame.path.name, vlm_option(cam)
        cam.press("enter")
        if cam.read().kind != "checklist" or not is_box(box_label(cam), ITEMS, i):
            raise Failed(f"{name}: after choosing {labels[j]!r} the screen is {cam.read().kind} "
                         f"({cam.frame.path.name}), not the checklist on the box")
        back = cam.frame.path.name
        cam.press("menu")                         # back to the row, where the download is made
        if cam.read().kind != "menu":
            raise Failed(f"{name}: MENU off the checklist left {cam.read().kind} ({cam.frame.path.name})")
        dat = link.download(f"{ITEMS[i]}-{j}".replace("/", "-"))
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        written |= {c.key for c in changes}
        out.write(json.dumps({"path": [ROW, ITEMS[i]], "kind": "list", "index": j, "label": labels[j], "shown": shown,
                              "chosen_frame": chosen, "vlm": seen, "row_frame": back, "dat": dat.name,
                              "base": start.name, "applied": True, "attempt": attempt, "part_of": ROW,
                              "changes": [{"key": c.key, "before": c.before, "after": c.after} for c in changes]})
                  + "\n")
        out.flush()
        brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in changes[:6]) or "no change"
        say(f"   {labels[j]!r:24s} {brief}")
        after_download(cam, done)                 # the saving banner clears; the menu back if it closed
    # a box starts unticked ("-"), which no option of its chooser gives back: the start file puts it back
    finish_attempt(run, attempt, name, {"kept": [], "not_offered": sorted(written)})
    return n


# Rating's chooser: a grid of star boxes, two columns, Down walking the left column then the right (the a1 II,
# 2026-11-07: ★, ★★, ★★★ on the left, ★★★★, ★★★★★ and ★OFF on the right, as the records 0x1282-0x1287 and the
# copies 0x16bd-0x16c2 Rating Set(Custom Key) mirrors confirm), then its Enter and Cancel buttons
STARS = ["★", "★★", "★★★", "★★★★", "★★★★★", "★OFF"]


def grid_top(cam):
    for _ in range(8):
        s = cam.read()
        if s.kind == "checklist" and s.focus == "rows" and s.row == 0:
            return
        cam.press("up")
    raise Failed(f"the grid's first box was not reached ({cam.read().kind}, {cam.frame.path.name})")


def grid_tick(cam, name: str, b: int):
    """Enter on box b of the grid, from its top; the box must flip."""
    grid_top(cam)
    for _ in range(b):
        cam.press("down")
    s = cam.read()
    if s.kind != "checklist" or s.focus != "rows" or s.row != b:
        raise Failed(f"{name}: the cursor is not on box {b} ({s.kind}, row {s.row}, {cam.frame.path.name})")
    before = check_state(cam)
    cam.press("enter")
    after = check_state(cam)
    if before is None or after is None or after == before:
        raise Failed(f"{name}: Enter did not flip box {b} ({before} -> {after}, {cam.frame.path.name})")
    return after


def grid_enter(cam, name: str):
    """Down to the grid's Enter button and press it: back on the filter's checklist."""
    for _ in range(len(STARS) + 2):
        if cam.read().focus == "button":
            break
        cam.press("down")
    if cam.read().focus != "button" or option_key(focused_button(cam)) != option_key("Enter"):
        raise Failed(f"{name}: the cursor is not on the grid's Enter ({focused_button(cam)!r}, {cam.frame.path.name})")
    cam.press("enter")


def prove_grid(cam, link, run, cycle, model, i: int, start: Path, out, say) -> int:
    """Rating's grid, open: each star box ticked alone (the one before unticked on the same visit), Enter, a download
    and a diff against the start file; proofs as a list row's, one per box."""
    name = f"{ROW} > {ITEMS[i]}"
    base = camset.read(start)
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    written = set()
    say(f"{name}: a grid of {len(STARS)} boxes {STARS}")
    for b in range(len(STARS)):
        if b:
            open_row(cam, cycle, model)
            to_box(cam, i)
            open_chooser(cam)
            if cam.read().kind != "checklist" or cam.read().focus != "rows":
                raise Failed(f"{name}: {cam.read().kind} ({cam.frame.path.name}), not the grid, for box {b}")
            if grid_tick(cam, name, b - 1):
                raise Failed(f"{name}: box {b - 1} ticked again instead of unticked")
        if not grid_tick(cam, name, b):
            raise Failed(f"{name}: box {b} unticked instead of ticked")
        shown, chosen, seen = STARS[b], cam.frame.path.name, vlm_option(cam)
        grid_enter(cam, name)
        if cam.read().kind != "checklist" or not is_box(box_label(cam), ITEMS, i):
            raise Failed(f"{name}: after the grid's Enter the screen is {cam.read().kind} ({cam.frame.path.name}), "
                         f"not the checklist on the box")
        back = cam.frame.path.name
        cam.press("menu")
        if cam.read().kind != "menu":
            raise Failed(f"{name}: MENU off the checklist left {cam.read().kind} ({cam.frame.path.name})")
        dat = link.download(f"Rating-{b}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        written |= {c.key for c in changes}
        out.write(json.dumps({"path": [ROW, ITEMS[i]], "kind": "list", "index": b, "label": STARS[b], "shown": shown,
                              "chosen_frame": chosen, "vlm": seen, "row_frame": back, "dat": dat.name,
                              "base": start.name, "applied": True, "attempt": attempt, "part_of": ROW, "grid_box": b,
                              "changes": [{"key": c.key, "before": c.before, "after": c.after} for c in changes]})
                  + "\n")
        out.flush()
        brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in changes[:6]) or "no change"
        say(f"   {STARS[b]!r:24s} {brief}")
        after_download(cam, done)
    finish_attempt(run, attempt, name, {"kept": [], "not_offered": sorted(written)})
    return len(STARS)


def box_state(cam) -> bool | None:
    s = cam.read()
    return box_column_state(s.kind, s.focus, s.row, s.boxes, s.slots)


def in_box_column(cam) -> bool | None:
    """The cursor moved to the box column (Left from the value column, where Right and a choice leave it), and the
    box's state there: True ticked, False unticked, None when the cursor is on no box in the box column."""
    if box_state(cam) is None:
        cam.press("left")
    return box_state(cam)


def untick_item(cam, link, run, cycle, model, i: int, key: str | None, out, say) -> bool:
    """Item i's box, ticked, unticked by Enter in the box column and proved by a download before and after. The menu
    is open on the row (prove_item left it so). True when the proof was written applied."""
    name = f"{ROW} > {ITEMS[i]}"
    dat0 = download(link, f"{ITEMS[i]}-untick-before".replace("/", "-"), say)
    done = time.monotonic()
    after_download(cam, done)
    open_row(cam, cycle, model)
    to_box(cam, i)
    state = in_box_column(cam)
    if state is None or not is_box(box_label(cam), ITEMS, i):
        raise Failed(f"{name}: the cursor is not on the box in the box column ({cam.read().kind}, {cam.frame.path.name})")
    if not state:                                 # unticked: its chooser's option in force ticks it again
        if ITEMS[i] == "Rating":
            raise Failed(f"{name}: the box is not ticked and Rating's grid is not chosen again here")
        open_chooser(cam)
        if cam.read().kind != "list":
            raise Failed(f"{name}: {cam.read().kind} ({cam.frame.path.name}), not the chooser, to tick the box again")
        cam.press("enter")                        # back on the checklist, the cursor in the value column
        if cam.read().kind != "checklist" or in_box_column(cam) is not True:
            raise Failed(f"{name}: the box did not tick ({cam.frame.path.name})")
        cam.press("menu")
        if cam.read().kind != "menu":
            raise Failed(f"{name}: MENU off the checklist left {cam.read().kind} ({cam.frame.path.name})")
        dat0 = download(link, f"{ITEMS[i]}-untick-before2".replace("/", "-"), say)
        after_download(cam, time.monotonic())
        open_row(cam, cycle, model)
        to_box(cam, i)
        if in_box_column(cam) is not True:
            raise Failed(f"{name}: the box is not ticked on the box column ({cam.frame.path.name})")
    ticked = cam.frame.path.name
    cam.press("enter")
    if cam.read().kind != "checklist" or box_state(cam) is not False:
        raise Failed(f"{name}: Enter in the box column did not untick the box ({cam.read().kind}, "
                     f"{box_state(cam)}, {cam.frame.path.name})")
    chosen, seen = cam.frame.path.name, vlm_option(cam)
    cam.press("menu")
    if cam.read().kind != "menu":
        raise Failed(f"{name}: MENU off the checklist left {cam.read().kind} ({cam.frame.path.name})")
    back = cam.frame.path.name
    dat = download(link, f"{ITEMS[i]}-unticked".replace("/", "-"), say)
    done = time.monotonic()
    changes = [{"key": c.key, "before": c.before, "after": c.after} for c in camset.diff(camset.read(dat0), camset.read(dat))]
    applied = untick_applied(changes, key)
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    out.write(json.dumps({"path": [ROW, ITEMS[i]], "kind": "list", "index": 0, "label": "Not ticked",
                          "shown": "Not ticked", "chosen_frame": chosen, "vlm": seen, "row_frame": back,
                          "dat": dat.name, "base": dat0.name, "applied": applied, "attempt": attempt,
                          "part_of": ROW, "untick": True, "ticked_frame": ticked, "changes": changes}) + "\n")
    out.flush()
    brief = ", ".join(f"{c['key']} {c['before']!r}->{c['after']!r}" for c in changes[:6]) or "no change"
    say(f"   {'Not ticked'!r:24s} {brief}" + ("" if applied else "   (box record did not go 1 -> 0)"))
    finish_attempt(run, attempt, name, {"kept": [], "not_offered": sorted(c["key"] for c in changes)})
    after_download(cam, done)
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (default: the camera's latest page scan "
                         "made in the mode --in names, runner.latest_scan)")
    add_in_argument(ap)
    ap.add_argument("--run", default="kit2_pass2")
    ap.add_argument("--untick", action="store_true",
                    help="after each item's proof, untick its box (Enter in the box column) and prove value 0")
    ap.add_argument("--items", nargs="*", default=None, help="the items to prove (default: all but the data choosers)")
    a = ap.parse_args()
    run = Run(a.run)
    if mark_proof_run(run.dir, f"kit/provers/filter_run.py --run {run.dir.name}"):
        print(f"{run.dir.name} is marked as one of the camera's proof runs: kit/pass2_report.py reads its proofs beside "
              f"{MAIN_RUN}'s", flush=True)
    say = lambda m: print(m, flush=True)
    cycle, model = load_scan(in_mode(a.scan, a.in_mode))
    items = a.items if a.items is not None else [x for x in ITEMS if x not in DATA]
    bad = [x for x in items if x not in ITEMS]
    if bad:
        sys.exit(f"unknown items {bad}: one of {ITEMS}")
    defn = {}
    if a.untick:
        df = definitions.path(run.dir.parent.name)          # its box names are public (definitions.load_public)
        defn = definitions.load_public(df) if df.exists() else {}
    hdmi = eyes_from_config(run)
    proofs, unrestored = 0, False
    try:
        with proofs_file(run, None) as out:
            for item in items:
                i, stop = ITEMS.index(item), False
                with Link(run) as link:
                    hdmi.attach(link)
                    to_shooting(link, hdmi, "the start download")
                    start = download(link, "before", say)
                    time.sleep(5)
                    cam = LiveCamera(link, hdmi, run)
                    try:
                        open_menu(cam)
                        n = prove_item(cam, link, run, cycle, model, i, start, out, say)
                        proofs += n
                        if a.untick and n:
                            proofs += untick_item(cam, link, run, cycle, model, i, box_key(defn, item), out, say)
                    except (Failed, LinkError) as e:      # LinkError: a press the camera did not take ("button not
                        say(f"{item}: failed: {e}")        # accepted" while it drew Folder's list, 2026-11-07)
                        with open(run.dir / "failures.jsonl", "a", encoding="utf-8", newline="\n") as f:
                            f.write(json.dumps({"path": [ROW, item], "why": str(e), "frame": cam.frame.path.name}) + "\n")
                    except Exception as e:                # a STOP, the eyes' feed gone: the item's start goes back, then stop
                        say(f"{item}: stopped: {type(e).__name__}: {e}")
                        stop = True
                    finally:
                        close_for_restore(cam, link)
                    # each item ends restoring its start file, whatever ended it (decision 15)
                    ending = end_session(link, hdmi, start, "the check after the item", tag="check")
                unrestored = not restore_checked(run, ending, start,
                                                 f"the start file did not take after {item}: stopping")
                if unrestored or stop:
                    break
    finally:
        hdmi.close()
    say(f"finished: {proofs} proofs of {len(items)} items")
    if unrestored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
