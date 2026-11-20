"""Why a menu row is drawn grey, asked of the camera: Help first, then one Right for its notice (proving.greyrow; the
owner, 2026-11-20).

    .venv/bin/python -u kit/provers/greyrow_run.py --in Movie --row "Framing Stabilizer"
    .venv/bin/python -u kit/provers/greyrow_run.py --in Stills --context "Stills mode, M" \\
        --row "ISO AUTO Min. SS" --row "Aspect Marker Level"
    .venv/bin/python -u kit/provers/greyrow_run.py --in Movie --look --context "Touch Operation On" \\
        --row "Framing Stabilizer"

--look only looks: each row is reached as below and read, on a frame grabbed afresh, as drawn grey, white or unsure
(proving.greyrow.look), nothing pressed on it, no Help, no Right, its line of the kind "look" spending none. A chain sets
a blocker's value with kit/provers/mode_switch.py --set and looks, value by value: the runs a hand table's
inactive_when takes its values from.

Each --row (its path, ' > ' between submenus, as the other provers take it) is gone to through the page scan as the
other runners go (MENU, the scan's Down cycle to its top-level row, each submenu's row by its label) and asked why it
is grey (proving.greyrow.ask_why): drawn grey now, on a frame grabbed afresh; the camera's Help where the footer offers
it (guarded, decision 7); one Right only where the guide gives no reason and the kit may open the row as it would if it
were white, never twice on a row in the run; after it, a notice left with MENU (its OK only where the camera refuses
MENU and OK is plainly its only button), a question or any other screen MENU alone, no other Enter. A row the kit may not
open or reach (never-open, a row whose opening acts, a format, delete or reset, a row above it this body has not been
seen to open) is passed over before anything is pressed; a row not seen opened itself gets its Help alone (its first
open is the crawl's procedure, camkit.first_open). Then MENU back to the shooting screen, and the next row.

One session (runner.prover_session, decision 15): the start file downloaded first; a STOP file (<run>/STOP) or one
Ctrl-C stops the run at its next press, the camera closed with MENU; at the end the start file goes back and is
checked (the run chooses nothing, so nothing should differ). Lines: <run>/greyrows.jsonl in the camera's
runs/<model>_fw<fw>/ (the run kit2_greyrow unless --run names another), one a row: the mode and --context, the start
file, the outcome, whether the row's one Right is spent ("spent") and went out ("right"), the guide's and the notice's
words and frames (Sony's text and the camera's state: they stay in runs/, decision 13), and the blocker the notice names
(camkit.coverage.blocker_of: the row label, never its value). That blocker is a lead, the setting to try, never the
values that grey the row: the value the start file holds is the owner's (decision 16), so a hand table's inactive_when
takes its values and the value that un-greys the row only from runs where the kit set each value of that setting
itself from a known start file and saw the row grey or white, every value classified before the entry is written
(docs/REMAPPING_PLAYBOOK.md, Phase 3). A row is the row the kit
finds (row_keys: its labels folded as camkit.first_open folds them, and the row the page scan leads to), so a row named
twice, spelled or read otherwise, is asked once; a row whose Right is spent in this run folder, mode and context (each
compared folded) gets none again: another --context (another state) or --run asks again.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import first_open, jsonl, safety  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to, target_of  # noqa: E402
from proving import greyrow  # noqa: E402
from proving.base import Failed  # noqa: E402
from proving.nav import enter_any  # noqa: E402
from runner import (LATEST_SCAN, add_in_argument, blocker_labels, close_screen, in_mode, load_scan,  # noqa: E402
                    menu_from_shooting, prover_session, scan_arg, scan_position)

LINES = "greyrows.jsonl"
NOT_REACHED, STOPPED = "not reached", "stopped"


def _say(message: str) -> None:
    print(message, flush=True)


def row_paths(rows) -> list:
    """Each --row as its path, the labels ' > ' parts it into, spacing round each left out; a row naming nothing is
    left out."""
    out = []
    for r in rows:
        path = [x.strip() for x in str(r).split(" > ") if x.strip()]
        if path:
            out.append(path)
    return out


def row_keys(cycle, model, path) -> tuple:
    """The keys a row's one Right is spent under, as the kit finds the row: its labels folded as camkit.first_open.Seen
    folds them (proving.greyrow.label_key), and, where the page scan leads to it, the row crawl_run.target_of goes to
    (its page's key and its slot) with the submenu labels folded, so two spellings or two readings of one row are one
    row."""
    keys = [greyrow.label_key(path)]
    j = target_of(cycle, model, path[0])[0] if cycle else None
    if j is not None:
        keys.append(("row", cycle[j]["page"], cycle[j]["row"], *first_open.key(path)[1:]))     # renamed whole
    return tuple(keys)


def same_words(a, b) -> bool:
    """Two modes or two contexts compared folded (safety.plain): "Touch Off" is "touch  off"."""
    return safety.plain(str(a or "")) == safety.plain(str(b or ""))


def spent_rows(path: Path, mode: str, context: str) -> set:
    """The keys of the rows whose one Right is spent in the run's lines file for this mode and context, each compared
    folded (same_words): each line's "keys" as written, and its path's label_key computed now, under the camera's
    ROW_NAMES as it stands (first_open.key renames it), so a table added since an earlier run leaves no row a second
    Right under its camera's name."""
    out = set()
    for x in jsonl.read(path, bad="skip"):
        if x.get("spent") and x.get("kind") != greyrow.LOOK and same_words(x.get("mode"), mode) \
                and same_words(x.get("context"), context):
            out |= {tuple(k) for k in x.get("keys") or () if isinstance(k, list | tuple)}
            if isinstance(x.get("path"), list) and x["path"]:
                out.add(greyrow.label_key(x["path"]))
    return out


def distinct_rows(cycle, model, rows, say=_say) -> list:
    """[(path, its row_keys)] for each row named, in the order given, a row whose keys meet an earlier row's (the same
    row spelled or read otherwise) left out and said."""
    out, had = [], set()
    for path in rows:
        keys = row_keys(cycle, model, path)
        if any(k in had for k in keys):
            say(f"{' > '.join(path)}: the same row as one named before it, asked once")
            continue
        had.update(keys)
        out.append((path, keys))
    return out


def stored_reason(cycle, model, path) -> str | None:
    """The page model's stored never-open reason of the row's top-level row (the one go_to steps to), or None."""
    j = target_of(cycle, model, path[0])[0]
    if j is None:
        return None
    rows = model[cycle[j]["page"]]["rows"]
    return rows[cycle[j]["row"]].get("never_open") if cycle[j]["row"] < len(rows) else None


def this_body_first(camera: str):
    """The session's way to the shooting screen for its start download (runner.prover_session's reach), once the camera
    connected is known to be the one whose records say which rows are seen opened (camkit.first_open.other_body, as
    kit/crawl_run.py and kit/drive.py ask it): another body, or one that cannot say, stops the run with nothing sent."""
    def reach(link, eyes, why: str) -> None:
        other = first_open.other_body(link, camera)
        if other:
            raise SystemExit(f"{other}: nothing was sent to the camera")
        from proving.nav import to_shooting
        to_shooting(link, eyes, why)
    return reach


def reach(cam, cycle, model, path) -> None:
    """From the shooting screen to the row: MENU, the scan's cycle to its top-level row (crawl_run.go_to, every screen
    checked against the scan), then Right into each submenu and Down to the next label (proving.nav.enter_any), each
    Right judged by the camera's never-open check as every opening press is. Failed where the scan does not lead there."""
    menu_from_shooting(cam)
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"{' > '.join(path)}: the page scan does not lead to {path[0]!r} from here ({cam.frame.path.name})")
    enter_any(cam, path, 0)


def one_row(cam, cycle, model, path, seen, tried: set, keys, labels, say=_say, look=False) -> dict:
    """The row's line: passed over before anything is pressed where the kit may not open or reach it (proving.greyrow.
    closed), else reached and asked (proving.greyrow.ask_why); a row that fails, or is not reached, says why. A row that
    leaves the camera on its playback view ends the run (greyrow.StopsRun, raised on with its line)."""
    name = " > ".join(path)
    stored = stored_reason(cycle, model, path)
    why = greyrow.closed(path, seen, stored)
    if why:
        say(f"{name}: passed over, nothing pressed: {why}")
        return {**({"kind": greyrow.LOOK} if look else {"right": False}), "path": path, "outcome": greyrow.PASSED,
                "why": why}
    try:
        reach(cam, cycle, model, path)
    except Failed as e:
        say(f"{name}: not reached: {e}")
        return {**({"kind": greyrow.LOOK} if look else {"right": False}), "path": path, "outcome": NOT_REACHED,
                "why": str(e)}
    try:
        if look:
            return greyrow.look(cam, path, seen=seen, stored=stored, say=say)
        return greyrow.ask_why(cam, path, seen=seen, tried=tried, keys=keys, stored=stored, labels=labels, say=say)
    except greyrow.StopsRun:
        raise                                   # the playback view: main writes its line, the session closes
    except greyrow.RowFailed as e:
        say(f"{name}: failed: {e}")
        return e.line


def main():
    ap = argparse.ArgumentParser(description="Why a menu row is drawn grey: the camera's Help, then one Right for its "
                                             "notice where Help gives no reason (see this file's docstring).")
    ap.add_argument("--row", dest="rows", action="append", default=[], metavar="ROW",
                    help="a row's path, ' > ' between submenus (repeatable, in the order given)")
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (a run in the camera's runs, or a path; "
                         "default: the camera's latest page scan made in the mode --in names)")
    add_in_argument(ap)
    ap.add_argument("--context", default="",
                    help="the state the camera is in, in words (on every line; a row's one Right is spent per run "
                         "folder, mode and context)")
    ap.add_argument("--run", default="kit2_greyrow", help="the run folder in the camera's runs (default kit2_greyrow)")
    ap.add_argument("--look", action="store_true",
                    help="only look: reach each row and read whether it is drawn grey, white or unsure, pressing "
                         "nothing on it (no Help, no Right) and spending no Right; for a chain that sets a blocker's "
                         "value (mode_switch.py --set) and looks, value by value")
    a = ap.parse_args()
    rows = row_paths(a.rows)
    if not rows:
        ap.error("--row: at least one row")
    cycle, model = load_scan(in_mode(a.scan, a.in_mode))
    rows = distinct_rows(cycle, model, rows)
    run = Run(a.run)
    out_path = run.dir / LINES
    tried = set() if a.look else spent_rows(out_path, a.in_mode, a.context)       # a look spends none
    seen = first_open.seen_record(run.root.name)
    labels = blocker_labels(model)
    hdmi = eyes_from_config(run)
    with open(out_path, "a", encoding="utf-8", newline="\n") as out, \
            prover_session(run, hdmi, reach=this_body_first(run.root.name)) as s:
        def write(line: dict, keys) -> None:
            spent = {} if a.look else {"spent": any(k in tried for k in keys)}       # a look's line spends no Right
            out.write(json.dumps({"t": round(time.time(), 3), "mode": a.in_mode, "context": a.context,
                                  "start": s.start.name, **line, "keys": [list(k) for k in keys], **spent}) + "\n")
            out.flush()
        for path, keys in rows:
            try:
                line = one_row(s.cam, cycle, model, path, seen, tried, keys, labels, look=a.look)
            except Exception as e:      # a STOP, a refused press, a lost link, the playback view: the line, then the
                # session's close (a row's own line where it ends the run: greyrow.StopsRun)
                write(getattr(e, "line", None) or {**({"kind": greyrow.LOOK} if a.look else {"right": None}),
                                                   "path": path, "outcome": STOPPED,
                                                   "why": f"{type(e).__name__}: {e}"}, keys)
                raise
            write(line, keys)
            close_screen(s.cam, s.link)         # MENU back to the shooting screen, for the next row's MENU


if __name__ == "__main__":
    main()
