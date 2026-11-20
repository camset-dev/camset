"""Why a menu row is drawn grey, asked of the camera: Help first, then one Right for its notice (proving.greyrow; the
owner, 2026-11-20).

    .venv/bin/python -u kit/provers/greyrow_run.py --in Movie --row "Framing Stabilizer"
    .venv/bin/python -u kit/provers/greyrow_run.py --in Stills --context "Stills mode, M" \\
        --row "ISO AUTO Min. SS" --row "Aspect Marker Level"

Each --row (its path, ' > ' between submenus, as the other provers take it) is gone to through the page scan as the
other runners go (MENU, the scan's Down cycle to its top-level row, each submenu's row by its label) and asked why it
is grey (proving.greyrow.ask_why): drawn grey now, on a frame grabbed afresh; the camera's Help where the footer offers
it (guarded, decision 7); one Right only where the guide gives no reason and the kit may open the row as it would if it
were white, never twice on a row in the run; after it, a notice left with MENU (its OK only where the camera refuses
MENU and OK is plainly its only button), a question or any other screen MENU alone, never Enter. A row the kit may not
open or reach (never-open, a row whose opening acts, a format, delete or reset, a row above it this body has not been
seen to open) is passed over before anything is pressed; a row not seen opened itself gets its Help alone (its first
open is the crawl's procedure, camkit.first_open). Then MENU back to the shooting screen, and the next row.

One session (runner.prover_session, decision 15): the start file downloaded first; a STOP file (<run>/STOP) or one
Ctrl-C stops the run at its next press, the camera closed with MENU; at the end the start file goes back and is
checked (the run chooses nothing, so nothing should differ). Lines: <run>/greyrows.jsonl in the camera's
runs/<model>_fw<fw>/ (the run kit2_greyrow unless --run names another), one a row: the mode and --context, the start
file, the outcome, whether the row's one Right is spent ("spent") and went out ("right"), the guide's and the notice's
words and frames (Sony's text and the camera's state: they stay in runs/, decision 13), and the blocker the notice names
(camkit.coverage.blocker_of: the row label, never its value), which a data pass takes to the hand tables'
inactive_when with the start file's record of that row (docs/REMAPPING_PLAYBOOK.md, Phase 3). A row whose Right is
spent in this run folder, mode and context gets none again: a new --context (another state) or --run asks again.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import first_open, jsonl  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to, target_of  # noqa: E402
from proving import greyrow  # noqa: E402
from proving.base import Failed  # noqa: E402
from proving.nav import enter_any  # noqa: E402
from runner import (LATEST_SCAN, add_in_argument, close_screen, in_mode, known_labels, load_scan,  # noqa: E402
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


def row_key(mode: str, context: str, path) -> tuple:
    return (str(mode or ""), str(context or ""), tuple(str(x) for x in path))


def spent_rows(path: Path, mode: str, context: str) -> set:
    """The rows whose one Right is spent in the run's lines file for this mode and context (their row_key)."""
    return {row_key(x.get("mode"), x.get("context"), x.get("path") or ()) for x in jsonl.read(path, bad="skip")
            if x.get("spent") and x.get("mode") == mode and (x.get("context") or "") == (context or "")}


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


def one_row(cam, cycle, model, path, seen, tried: set, key, labels, say=_say) -> dict:
    """The row's line: passed over before anything is pressed where the kit may not open or reach it (proving.greyrow.
    closed), else reached and asked (proving.greyrow.ask_why); a row that fails, or is not reached, says why."""
    name = " > ".join(path)
    stored = stored_reason(cycle, model, path)
    why = greyrow.closed(path, seen, stored)
    if why:
        say(f"{name}: passed over, nothing pressed: {why}")
        return {"path": path, "right": False, "outcome": greyrow.PASSED, "why": why}
    try:
        reach(cam, cycle, model, path)
    except Failed as e:
        say(f"{name}: not reached: {e}")
        return {"path": path, "right": False, "outcome": NOT_REACHED, "why": str(e)}
    try:
        return greyrow.ask_why(cam, path, seen=seen, tried=tried, key=key, stored=stored, labels=labels, say=say)
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
    a = ap.parse_args()
    rows = row_paths(a.rows)
    if not rows:
        ap.error("--row: at least one row")
    cycle, model = load_scan(in_mode(a.scan, a.in_mode))
    run = Run(a.run)
    out_path = run.dir / LINES
    tried = spent_rows(out_path, a.in_mode, a.context)
    seen = first_open.seen_record(run.root.name)
    labels = known_labels(model)
    hdmi = eyes_from_config(run)
    with open(out_path, "a", encoding="utf-8", newline="\n") as out, \
            prover_session(run, hdmi, reach=this_body_first(run.root.name)) as s:
        def write(line: dict, key) -> None:
            out.write(json.dumps({"t": round(time.time(), 3), "mode": a.in_mode, "context": a.context,
                                  "start": s.start.name, **line, "spent": key in tried}) + "\n")
            out.flush()
        for path in rows:
            key = row_key(a.in_mode, a.context, path)
            try:
                line = one_row(s.cam, cycle, model, path, seen, tried, key, labels)
            except Exception as e:      # a STOP, a refused press, a lost link: the line, then the session's close
                write({"path": path, "right": None, "outcome": STOPPED, "why": f"{type(e).__name__}: {e}"}, key)
                raise
            write(line, key)
            close_screen(s.cam, s.link)         # MENU back to the shooting screen, for the next row's MENU


if __name__ == "__main__":
    main()
