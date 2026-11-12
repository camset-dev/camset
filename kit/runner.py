"""What the kit's runners share beyond camkit: the page scan loaded, a JSON file written whole, a proof's changes as the
proofs file holds them, and a session with the camera that always ends restoring its start file (docs/decisions/0015).

    add_scan_argument(ap)                         --scan as every runner takes it (LATEST_SCAN with mode=: the camera's
                                                  latest whole page scan made in that shooting mode, latest_scan)
    cycle, model = load_scan(a.scan)              the page scan's Down cycle, each position's screen read by today's
                                                  reader, and its page model, for camkit.crawl and crawl_run.go_to
    menu_from_shooting(cam); scan_position(...)   MENU (again if it went unanswered), and where the menu opened
    read_json(path); write_json(path, obj)        a JSON file read and closed; replaced whole (a crash leaves the old)
    lines, unread = read_frames(frames)           OCR of a batch that names each frame it could not read, never stops
    changes_of(camset.diff(a, b))                 [{"key", "before", "after"}] for a proof line
    end_session(link, eyes, start, why)           the shooting screen, then camkit.session.finish; when the shooting
                                                  screen does not come, the restore is still tried
    with prover_session(run, eyes) as s: ...      a prover's whole session: the start download, a LiveCamera (s.cam),
                                                  the body, and the end above, the restore checked (s.restored)
    sys.exit(EXIT_UNRESTORED)                     a runner's exit when the camera is not known to be as its start file
    with restoring(): ...                         a restore that raises is said and exits EXIT_UNRESTORED

Only camkit is imported at the top: crawl_run imports this, and prove_run's parts import crawl_run, so the prover's
own pieces (to_shooting) are imported where they are used.
"""
import contextlib
import json
import os
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from camkit import safety, screen, session
from camkit.frames import load
from camkit.link import Link, StopRequested
from camkit.live import LiveCamera, close, text_of
from camkit.screen import same_position
# A runner's exit status when the camera is not known to be as its start file at the end: the restore did not check
# out, the last download was refused so nothing was restored, or the restore itself failed (restoring). kit/tools/
# chain.py stops the chain after a step that exits with it, as after a failed upload; both take it from
# kit/exit_status.py, which imports nothing
from exit_status import EXIT_UNRESTORED          # the runners import it from here too

SETTLE_S = 5.0          # after the start download: MENU within ~4 s of a download leaves the menu locked


def _read_umask() -> int:
    """The process's umask, read once when this module is imported, before any runner starts a thread (the link's
    reader, a reader pool): the standard library reads it only by setting it, which for that instant would loosen the
    mode of a file another thread creates."""
    mask = os.umask(0o077)
    os.umask(mask)
    return mask


_UMASK = _read_umask()


LATEST_SCAN = "latest"          # --scan's default where a runner names no scan of its own: latest_scan()
# The menus differ per shooting mode (Movie and S&Q have menus of their own, and the pages differ), so a page scan
# records the mode it was made in, in SCAN_MODE_FILE beside its model.json: {"mode": one of SCAN_MODES}, written by
# kit/page_scan.py --mode, or for a scan made before 2026-11-11 by kit/page_model.py --mode (record_mode). A runner
# takes by default only the latest scan of the mode it works in (latest_scan), and a scan that records no mode never
# (no mode is guessed from a folder's name): driving a camera by another mode's menu map presses keys on rows that
# are not where the map says. SCAN_MODES are the Still/Movie/S&Q switch's positions, as the proofs' contexts and kit/
# tools/menu_tree.py --mode name them; Shoot Mode's families (kit/provers/shootmode_run.py's FAMILIES) S&Q Motion and
# Time-lapse are both the switch's S&Q, one menu (S&Q Shoot Mode chooses between them inside it)
SCAN_MODES = ("Stills", "Movie", "S&Q")
SCAN_MODE_FILE = "scan_mode.json"
SWITCH_KEPT = "mode_switch.json"   # in a run folder: kit/provers/mode_switch.py --keep's switch, waiting for --restore
# A scan is taken by default only once it is whole (scan_unready): kit/page_scan.py records its mode with "lap":
# LAP_SCANNING before its first press and LAP_WHOLE once it has written a full lap (mark_lap_whole), and its page model
# (model.json, kit/page_model.py) must be newer than that lap. A record without "lap" was written by kit/page_model.py
# --mode for a scan made before 2026-11-11, which it takes only for a folder holding a whole lap.
LAP_SCANNING, LAP_WHOLE = "scanning", "whole"
# Intelligent Auto's menu is not known to be P/A/S/M's: no scan of it has been made on any body yet, Flash Mode
# offers options there no other mode offers, and a page whose row count differs is a page no other scan knows (the
# page counter is part of every page's key). So a scan made while the kit's own record says the camera was left in
# Intelligent Auto (a kept kit/provers/mode_switch.py switch, copied into the scan's record as "switch") is that
# menu's scan: taken by default only while such a switch waits, and never for a camera in P, A, S or M (is_auto).
AUTO = "Intelligent Auto"


def scan_mode(word) -> str:
    """A shooting mode as SCAN_MODES spells it, from any case or Shoot Mode's own family name ("stills", "movie",
    "S&Q Motion", "Time-lapse": S&Q); ValueError for any other word (argparse says it for a type=)."""
    w = " ".join(str(word or "").split()).lower()
    w = {"still": "stills", "s&q motion": "s&q", "time-lapse": "s&q", "timelapse": "s&q"}.get(w, w)
    for m in SCAN_MODES:
        if m.lower() == w:
            return m
    raise ValueError(f"{word!r} is no shooting mode a page scan is made in: one of {', '.join(SCAN_MODES)}")


scan_mode.__name__ = "shooting mode"          # argparse's word for a refused value: "invalid shooting mode value"


def recorded_mode(scan) -> str | None:
    """The shooting mode a page scan was made in, as it recorded it (SCAN_MODE_FILE); None when it records none (every
    scan made before 2026-11-11) or its file names no mode of SCAN_MODES."""
    try:
        return scan_mode(read_json(Path(scan) / SCAN_MODE_FILE).get("mode"))
    except (OSError, ValueError, AttributeError):
        return None


def scan_record(scan) -> dict:
    """A page scan's SCAN_MODE_FILE as it is ({} when it has none or it cannot be read)."""
    try:
        got = read_json(Path(scan) / SCAN_MODE_FILE)
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def record_mode(scan, mode, scanning: bool = False, switch: dict | None = None) -> str:
    """The shooting mode a page scan was made in written into its SCAN_MODE_FILE. scanning (kit/page_scan.py --mode,
    before its first press): {"mode", "lap": LAP_SCANNING, "started"} and the waiting switch the scan was made under
    ("switch", switch_for_scan), so the scan is no default until its lap is whole (mark_lap_whole, scan_unready); a
    scan again into the same folder starts the record afresh. Else (kit/page_model.py --mode, for a scan made before
    scans recorded it) {"mode"} alone, and a scan that records that mode already keeps its record as it is. A scan that
    records another mode keeps it: ValueError (a scan is made in one mode)."""
    mode, f = scan_mode(mode), Path(scan) / SCAN_MODE_FILE
    if f.exists() and recorded_mode(scan) != mode:
        from camkit import paths
        had = recorded_mode(scan)
        raise ValueError(f"the page scan {Path(scan).name} records {f'{had} mode' if had else 'a mode no kit reads'} "
                         f"already ({paths.shown(f)}), not {mode}: a scan is made in one mode. If that file is wrong, "
                         "delete it by hand and record the mode again.")
    if scanning:
        write_json(f, {"mode": mode, "lap": LAP_SCANNING, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                       SCAN_ID: new_scan_id(), **({"switch": switch} if switch else {})}, indent=1)
    elif not f.exists():
        write_json(f, {"mode": mode}, indent=1)
    return mode


# a scan's own id (kit/page_scan.py): written into its record (SCAN_MODE_FILE) before its first press and into each of
# its records in scan.jsonl, so a scan made again in the same folder writes its lap from its own records only
# (page_scan.write_cycle); the record keeps which scan the lap is ("lap_of", mark_lap_whole) and which lap the page
# model was built from ("model_of", kit/page_model.py: record_model), which scan_unready compares instead of file times
SCAN_ID = "scan_id"


def new_scan_id() -> str:
    """A new scan's id: its start time and a random part, unique for every scan of a folder."""
    import secrets
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def mark_lap_whole(scan, scan_id: str | None = None) -> None:
    """The scan's record marked LAP_WHOLE once kit/page_scan.py has written its full lap (scan_rekeyed.json), with the
    id of the scan the lap is ("lap_of"): from then on it is taken by default as soon as its page model is built from
    that lap (scan_unready)."""
    got = scan_record(scan)
    if got.get("lap") == LAP_SCANNING:
        write_json(Path(scan) / SCAN_MODE_FILE, {**got, "lap": LAP_WHOLE,
                                                 "lap_written": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                 **({"lap_of": scan_id} if scan_id else {})}, indent=1)


def record_model(scan, lap: list) -> None:
    """Which lap the page model kit/page_model.py just built is of ("model_of": the scan id its records carry), in the
    scan's record, when the scan has a record and the lap carries an id (a scan made since 2026-11-11); else nothing."""
    got = scan_record(scan)
    lap_id = next((r.get("scan") for r in lap if isinstance(r, dict) and r.get("scan")), None)
    if got and lap_id:
        write_json(Path(scan) / SCAN_MODE_FILE, {**got, "model_of": lap_id}, indent=1)


def is_auto(switch) -> bool:
    """A kept mode_switch record (or the copy a scan keeps of one) that left the camera in Intelligent Auto: --to Auto,
    a family with --mode Auto, or the title Shoot Mode named when the switch chose (a family's remembered mode)."""
    if not isinstance(switch, dict):
        return False
    return switch.get("to") == "Auto" or switch.get("mode") == "Auto" or \
        " ".join(str(switch.get("title") or "").split()).lower() == AUTO.lower()


def scan_auto(scan) -> bool:
    """The page scan was made while the kit's record said the camera was left in Intelligent Auto (AUTO)."""
    return is_auto(scan_record(scan).get("switch"))


def scan_unready(scan) -> str | None:
    """Why a page scan that records its mode is not taken by default, in words, or None when it is whole: a scan that
    began and has not written its full lap since (LAP_SCANNING: stopped early, or scanning now), or a page model not
    built from its lap (a lap written again, and kit/page_model.py not run since). A record that says which scan the lap
    is ("lap_of") is judged by which lap the model was built from ("model_of", record_model), whatever the file times
    (runs/ copied without them); an older record by the files' times, the model newer than the lap."""
    got = scan_record(scan)
    if got.get("lap") == LAP_SCANNING:
        return "its scan has not finished a lap"
    d = Path(scan)
    if got.get("lap_of"):
        if not ((d / "model.json").is_file() and (d / "scan_rekeyed.json").is_file()):
            return "it has no lap or no page model"
        if got.get("model_of") != got["lap_of"]:
            return "its page model is older than its lap"
        return None
    try:
        if (d / "model.json").stat().st_mtime < (d / "scan_rekeyed.json").stat().st_mtime:
            return "its page model is older than its lap"
    except OSError:
        return "it has no lap or no page model"
    return None


def lap_time(scan) -> float:
    """When a page scan's lap was written: its record's "lap_written" (mark_lap_whole, local time), which a copy or a
    restore of the folder keeps; else, for a scan that records none, its lap file's time (scan_rekeyed.json)."""
    written = scan_record(scan).get("lap_written")
    if isinstance(written, str):
        try:
            return time.mktime(time.strptime(written, "%Y-%m-%d %H:%M:%S"))
        except (ValueError, OverflowError):
            pass
    return (Path(scan) / "scan_rekeyed.json").stat().st_mtime


def page_scans(root: Path | None = None) -> list[Path]:
    """The camera's page scans, the oldest lap first (lap_time: the record's "lap_written", else the lap file's time):
    of the folders in its runs (runs/<model>_fw<fw>/, or root), those that hold a whole lap (scan_rekeyed.json,
    kit/page_scan.py) and its page model (model.json, kit/page_model.py), which load_scan both reads. No folder name is
    assumed: each camera's scans are named as its mapper ran them."""
    from camkit import paths
    root = Path(root) if root is not None else paths.run_root(required=False)
    if root is None or not root.is_dir():
        return []
    got = [d for d in root.iterdir() if (d / "scan_rekeyed.json").is_file() and (d / "model.json").is_file()]
    return sorted(got, key=lambda d: (lap_time(d), d.name))


def latest_scan(mode, root: Path | None = None, auto: bool = False) -> Path | None:
    """The camera's latest page scan made in shooting mode `mode` (scan_mode): of its page scans that record that mode
    (recorded_mode) and are whole (scan_unready), the one whose lap was written last; None when there is none. A scan
    that records no mode, one whose scan did not finish its lap and one whose page model is older than its lap are
    never taken. auto: the scans made in Intelligent Auto (scan_auto) instead of the others (AUTO)."""
    mode = scan_mode(mode)
    return next((d for d in reversed(page_scans(root))
                 if recorded_mode(d) == mode and scan_auto(d) == auto and scan_unready(d) is None), None)


def _switches(root: Path | None = None) -> list:
    """[(the record's file, the record as read ({} unread), the shooting mode it left the camera in or None)] for each
    kept switch of the camera's runs (switch_waiting)."""
    from camkit import paths
    root = Path(root) if root is not None else paths.run_root(required=False)
    if root is None or not root.is_dir():
        return []
    out = []
    for f in sorted(root.glob(f"*/{SWITCH_KEPT}")):
        try:
            kept = read_json(f)
        except (OSError, ValueError):
            kept = {}
        kept = kept if isinstance(kept, dict) else {}
        out.append((f, kept, switch_left(kept)))
    return out


def switch_left(kept: dict) -> str | None:
    """The shooting mode a kept switch record left the camera in: its "scan_mode" (a record made since 2026-11-11),
    else its "to" (a family's name, or P/A/S/M/Auto: Stills); None for a record that names no mode."""
    to = kept.get("scan_mode") or kept.get("to") if isinstance(kept, dict) else None
    try:
        return scan_mode(to)
    except ValueError:
        return "Stills" if to else None


def switch_waiting(root: Path | None = None) -> list:
    """[(run folder, the shooting mode the camera was left in)] for each switch kit/provers/mode_switch.py --keep made
    and --restore has not undone (SWITCH_KEPT in a run folder of the camera's runs): the kit's own record of a camera
    left in another mode, read from the files, never from the camera. The record's "scan_mode" says it; an older
    record's "to" is a family (Movie, S&Q Motion, ...) or a stills exposure mode (P, A, S, M, Auto: Stills), as
    mode_switch takes --to."""
    return [(f.parent, left) for f, _, left in _switches(root)]


def waiting_auto(mode: str, root: Path | None = None) -> bool:
    """A kept switch left the camera in `mode` and in Intelligent Auto (is_auto), by the kit's own record."""
    return any(left == mode and is_auto(kept) for _, kept, left in _switches(root))


def switch_for_scan(mode: str, root: Path | None = None) -> dict | None:
    """What a page scan made now keeps of the switch the camera was left by in `mode` (its run, --to, --mode, the
    title chosen, its time), for scan_auto; None when no switch waits in that mode. The start file's path is not
    copied."""
    for f, kept, left in _switches(root):
        if left == mode:
            return {"run": f.parent.name, **{k: kept[k] for k in ("to", "mode", "title", "t") if kept.get(k)}}
    return None


# the stills exposure modes kit/provers/mode_switch.py --to (and a family's --mode) takes, as its MODES spells them;
# Intelligent Auto ("Auto") is the last of SHOWN_EXPOSURES
EXPOSURE_MODES = ("P", "A", "S", "M")
# what kit/provers/mode_switch.py --forget --shows takes: the shooting mode the camera's screen shows now, its family
# first (SHOWN_MODES: a Still/Movie/S&Q position, SCAN_MODES; Shoot Mode's family names, S&Q Motion and Time-lapse, are
# S&Q), then, as a second word when the screen shows one, the exposure mode (SHOWN_EXPOSURES: the screen's letter, or
# Intelligent Auto, which a switch can leave the camera in within Stills or Movie, is_auto): "Movie", "Stills M",
# "Movie Auto". A letter alone is refused: Movie's and S&Q's screens show an exposure letter too, so "M" or "S" does
# not say which family the camera is in
SHOWN_MODES = SCAN_MODES
SHOWN_EXPOSURES = (*EXPOSURE_MODES, "Auto")
EXPOSURE_NAMES = {"program auto": "P", "aperture priority": "A", "shutter priority": "S", "manual exposure": "M",
                  "auto": "Auto", "intelligent auto": "Auto"}


def exposure_mode(word) -> str | None:
    """An exposure mode as SHOWN_EXPOSURES spells it, from its letter or its name in any case; None for any other
    word."""
    w = " ".join(str(word or "").split()).lower()
    return next((m for m in EXPOSURE_MODES if w == m.lower()), None) or EXPOSURE_NAMES.get(w)


def shown_mode(word) -> str:
    """--shows: what the camera's screen shows, the family first (scan_mode's words) and the exposure mode as a second
    word when it is said ("Stills", "Stills M", "Movie Auto", "S&Q Motion S"), as "<family>" or "<family> <exposure>";
    ValueError in plain words for an exposure mode alone (its family first) or a word it does not know."""
    w = " ".join(str(word or "").split()).lower()
    alone = exposure_mode(w)
    if alone:
        raise ValueError(f"{word!r} is an exposure mode alone, and Movie's and S&Q's screens show an exposure letter "
                         f"too: say the family first, as the camera's screen shows it, then the exposure mode, as in "
                         f"\"Stills {alone}\" or \"Movie {alone}\" ({', '.join(SHOWN_MODES)}; then "
                         f"{', '.join(SHOWN_EXPOSURES)})")
    try:
        return scan_mode(w)
    except ValueError:
        pass
    for spelling in sorted([*(m.lower() for m in EXPOSURE_MODES), *EXPOSURE_NAMES], key=len, reverse=True):
        if w.endswith(" " + spelling):
            try:
                return f"{scan_mode(w[:-len(spelling) - 1])} {exposure_mode(spelling)}"
            except ValueError:
                continue
    raise ValueError(f"{word!r}: say what the camera's screen shows, the shooting mode ({', '.join(SHOWN_MODES)}) and, "
                     f"when the screen shows one, the exposure mode after it ({', '.join(SHOWN_EXPOSURES)}), as in "
                     "Movie, \"Stills M\" or \"Movie Auto\"")


def shown_parts(shows: str) -> tuple:
    """(family, exposure mode or None) of what --shows said (shown_mode)."""
    family, _, exposure = shown_mode(shows).partition(" ")
    return family, exposure or None


def switch_from(kept: dict) -> str:
    """The shooting mode a kept switch started from: its record's "from" (since 2026-11-11), else Stills, the mode an
    older switch navigated by default (mode_switch.py --in)."""
    try:
        return scan_mode(kept.get("from") or "Stills")
    except ValueError:
        return "Stills"


def switch_target(kept: dict) -> tuple:
    """(family, exposure mode) a kept switch went to, as shown_parts spells them, each None when its record does not
    say it or says it in words the kit does not know: its --to a family (with --mode its exposure mode) or a stills
    exposure mode (Stills), Intelligent Auto when the switch chose it (is_auto)."""
    to, mode = kept.get("to"), kept.get("mode")
    try:
        family = scan_mode(to) if to else None
    except ValueError:
        family = None
    exposure = exposure_mode(mode) if mode else None
    if family is None and exposure_mode(to):
        family, exposure = "Stills", exposure_mode(to)
    if exposure is None and is_auto(kept):
        exposure = "Auto"
    return family, exposure


def forget_refused(kept: dict, shows: str, left: str | None) -> str | None:
    """Why --forget --shows `shows` must not forget the kept switch `kept` (which left the camera in `left`), in words,
    or None. `shows` is the family the screen shows, maybe with its exposure mode (shown_mode; an exposure mode alone is
    refused there): a family is compared always, an exposure mode only when both the record and the claim name one.
    Refused: an empty or unreadable record (it says nothing to check the screen against); the screen shows only Stills
    for a switch to a stills exposure mode (the letter tells); the screen shows where the switch went, its family and
    (when both say one) its exposure mode, Intelligent Auto when the switch chose it (is_auto); the screen shows the
    family the switch went to, and that is not the family it started from, whatever its exposure mode; or, for a
    record that does not say where it started (no "from", older records), the screen shows the very family it went to
    and no other exposure mode than the record's. In each the switch may still be in effect, and --restore is what puts
    the camera back."""
    if not kept:
        return ("the record is empty or cannot be read, so nothing says which mode the switch left the camera in")
    start = switch_from(kept)
    family, exposure = shown_parts(shows)
    shows = shown_mode(shows)
    to_family, to_exposure = switch_target(kept)
    differs = exposure is not None and to_exposure is not None and exposure != to_exposure
    within = exposure_mode(kept.get("to"))
    if family == "Stills" and exposure is None and within and not kept.get("mode"):
        return (f"the screen shows Stills, and this switch went to {within} within Stills: say the exposure mode the "
                "screen shows too (\"Stills P\", \"Stills A\", \"Stills S\", \"Stills M\" or \"Stills Auto\")")
    if to_family is not None and family == to_family and not differs:
        return f"the screen shows {shows}, where this switch left the camera"
    if left and family == left and left != start:
        return f"the screen shows {shows}, the mode this switch went to from {start}"
    if left and family == left and not kept.get("from") and not differs:
        return (f"the screen shows {shows}, the mode this switch went to, and its record (made before records said "
                "where a switch started) does not say it started there")
    return None


def switch_advice(record: Path, kept: dict | None = None, left: str | None = None) -> str:
    """What to do about a kept switch the kit stops on, in this order: first look at the camera's screen (or ask its
    owner) which mode it shows; when the camera has been put back since by another way, the record is stale, and
    kit/provers/mode_switch.py --forget --shows <that mode> only renames it (refused while the screen shows the mode
    the switch went to, forget_refused); only when the camera is still where the switch left it, --restore, with what
    that uploads (the run's start file: every setting goes back to what it was before the switch, and whatever was
    changed on the camera since is undone)."""
    if kept is None:
        try:
            kept = read_json(record)
        except (OSError, ValueError):
            kept = {}
    kept = kept if isinstance(kept, dict) else {}
    run = record.parent.name
    when = kept.get("t") or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.stat().st_mtime))
    start = Path(str(kept.get("start") or "")).name or "its start file"
    where = f"{left} mode" if left else "the mode it names"
    return (f"The record was made {when}, by a switch to {kept.get('to') or 'a mode it does not name'}"
            f"{' (' + kept['title'] + ')' if kept.get('title') else ''} from {switch_from(kept)} mode.\n"
            "First look at the camera's screen (or ask its owner) which mode it shows now: "
            f"{', '.join(SHOWN_MODES[:-1])} or {SHOWN_MODES[-1]}, and the exposure mode when it shows one "
            f"({', '.join(SHOWN_EXPOSURES[:-1])} or {SHOWN_EXPOSURES[-1]}, Intelligent Auto).\n"
            "If the camera has been put back since (by hand, or by a later session's restore), this record is stale: "
            "remove it, saying what the screen shows, with\n"
            f"  .venv/bin/python kit/provers/mode_switch.py --forget --shows <the mode it shows> --run {run}\n"
            "the family first and the exposure mode after it when you say one (--shows Movie, --shows \"Stills M\"); "
            "it only renames the record and sends nothing to the camera (it refuses while the screen shows the "
            "mode the switch went to).\n"
            f"Only if the camera is still in {where}, put it back with\n"
            f"  .venv/bin/python kit/provers/mode_switch.py --restore --run {run}\n"
            f"Mind what that does: it uploads {start}, the settings file downloaded just before the switch, so every "
            "setting goes back to what it was then, and whatever was changed on the camera since is undone.")


def refuse_switched(mode: str, root: Path | None = None) -> None:
    """Stops, in plain words and before anything is sent, a run that works in `mode` while the kit's own record says
    the camera was left in another (switch_waiting), saying what to do (switch_advice). The camera's own
    Still/Movie/S&Q switch, turned by hand, is not seen here: the session reads no mode from the camera at its
    start."""
    from camkit import paths
    for f, kept, left in _switches(root):
        if left != mode:
            where = f"{left} mode" if left else "a mode its record does not name"
            sys.exit(f"A mode switch is waiting in {paths.shown(f)}: kit/provers/mode_switch.py left the camera in "
                     f"{where}, and this run works in {mode} mode. Nothing was sent to the camera.\n"
                     f"{switch_advice(f, kept, left)}\n"
                     f"Or run this in {left or 'that'} mode with that mode's page scan.")


class ScanArg(str):
    """--scan's value: a page scan's folder, or LATEST_SCAN, with the shooting mode the runner works in (mode; None
    for a runner that names none), which scan_dir takes the scan by and checks a named scan against."""
    mode = None


def scan_arg(given, mode=None) -> str:
    """--scan's type=: LATEST_SCAN stays as it is, for scan_dir to find when the scan is read (a runner's own refusals
    come first, and a run that reads no scan needs none); any other name is a run in the camera's runs, or a path
    (camkit.paths.run_arg). With `mode`, the shooting mode the runner works in goes with it (ScanArg)."""
    from camkit import paths
    return in_mode(given if given == LATEST_SCAN else paths.run_arg(given), mode)


def in_mode(scan, mode) -> ScanArg:
    """--scan's value with the shooting mode the runner works in (scan_mode; None: none), for a runner that knows its
    mode only once its arguments are read (kit/provers/mode_switch.py, --in)."""
    got = ScanArg(str(scan))
    got.mode = scan_mode(mode) if mode else None
    return got


def no_mode_latest() -> str:
    """What a runner that names no shooting mode says to --scan latest (LATEST_SCAN): no traceback."""
    return (f"--scan {LATEST_SCAN} takes the latest page scan of the shooting mode a command works in, and this one "
            "works in none of its own: name the page scan with --scan <run> (its folder in the camera's runs). Nothing "
            "was sent to the camera.")


def scan_type(mode):
    """--scan's type= for a runner that works in shooting mode `mode`: argparse turns the default through it too. For a
    runner that names no mode (prove_run, crawl_run, drive.py), LATEST_SCAN is refused there in plain words."""
    import argparse

    def scan(given):
        if given == LATEST_SCAN and not mode:
            raise argparse.ArgumentTypeError(no_mode_latest())
        return scan_arg(given, mode)
    return scan


def add_in_argument(ap, default: str | None = "Stills", said: str | None = None) -> None:
    """--in (a.in_mode), the shooting mode the camera is in for a runner that works in any (My Menu, the Playback
    filter): the page scan it takes by default is that mode's latest (latest_scan), and a named one must be of that
    mode (in_mode). said: the default in words, where it is not a mode."""
    ap.add_argument("--in", dest="in_mode", default=default, type=scan_mode, metavar="MODE",
                    help=f"the shooting mode the camera is in now ({', '.join(SCAN_MODES)}; default: "
                         f"{said or default}): --scan's default is that mode's latest page scan")


def scan_state(d: Path) -> str:
    """A page scan's state in a few words, for no_scan_message: the mode it records, made in Intelligent Auto, and
    why it is not whole (scan_unready)."""
    m = recorded_mode(d)
    if not m:
        return "mode not recorded"
    why = scan_unready(d)
    return f"{m} mode{f', {AUTO}' if scan_auto(d) else ''}{f': {why}' if why else ''}"


def no_scan_message(mode: str, root: Path | None = None, auto: bool = False) -> str:
    """What a runner says when the camera has no whole page scan that records shooting mode `mode` (auto: made in
    Intelligent Auto, while a kept switch left the camera there): its page scans, newest first, each with its lap's
    time and its state (scan_state), and the ways on."""
    from camkit import paths
    root = Path(root) if root is not None else paths.run_root(required=False)
    where = f"{paths.shown(root)}/" if root is not None else "the camera's runs"
    scans = list(reversed(page_scans(root)))
    what = f"the {mode} mode menu{f' in {AUTO}' if auto else ''}"
    head = (f"There is no whole page scan of {what} in {where} that records its mode, so no scan is taken by "
            "default: the menus differ per shooting mode, and a run driven by another mode's menu map would press keys "
            "on rows that are not where the map says. Nothing was sent to the camera.")
    if auto:
        head += (f" The kit's record says a switch left the camera in {AUTO} (kit/provers/mode_switch.py --keep), "
                 f"whose menu is not known to be P/A/S/M's: scan it while the switch waits (kit/page_scan.py --mode "
                 f"{mode} --run <a new run>, then kit/page_model.py --vlm <that run>).")
    if not scans:
        return (f"{head} The camera has no page scan yet (a run folder with scan_rekeyed.json and model.json): scan "
                f"{what} first (kit/page_scan.py --mode {mode}, then kit/page_model.py), or name the scan to use with "
                "--scan <run>.")
    width = max(len(d.name) for d in scans)
    lines = [f"  {d.name:<{width}}  lap written "
             f"{time.strftime('%Y-%m-%d %H:%M', time.localtime((d / 'scan_rekeyed.json').stat().st_mtime))}  "
             f"{scan_state(d)}" for d in scans]
    return "\n".join([head, "The camera's page scans, newest first:", *lines,
                      "Name the scan to use with --scan <run>; build a page model older than its lap again with "
                      "kit/page_model.py <run>; finish a scan that has not finished its lap with kit/page_scan.py; or "
                      "record the mode a scan was made in, once, with",
                      f"  .venv/bin/python kit/page_model.py --mode {mode} <run>",
                      f"only for a scan you know was made in {mode} mode (its own run log or frames say it)."])


def scan_dir(scan, mode: str | None = None) -> Path:
    """The page scan's folder: --scan's as given, or for LATEST_SCAN the camera's latest whole page scan of the
    runner's shooting mode (latest_scan; Intelligent Auto's while a kept switch left the camera there, waiting_auto),
    stopping in plain words when it has none (no_scan_message). mode: the runner's, else the one --scan carries
    (ScanArg). With a mode, a named scan that records another stops, and so does any scan while the kit's record says
    the camera was left in another mode (refuse_switched). LATEST_SCAN with no mode stops in plain words."""
    from camkit import paths
    mode = scan_mode(mode) if mode else getattr(scan, "mode", None)
    if mode:
        refuse_switched(mode)
    if scan != LATEST_SCAN:
        got = Path(scan)
        had = recorded_mode(got) if mode else None
        if had and had != mode:
            sys.exit(f"The page scan {paths.shown(got)} was made in {had} mode, and this run works in {mode} mode: its "
                     f"menu pages are not this mode's. Nothing was sent to the camera. Name a {mode} mode page scan "
                     "with --scan <run>.")
        return got
    if mode is None:
        sys.exit(no_mode_latest())
    auto = waiting_auto(mode)
    got = latest_scan(mode, auto=auto)
    if got is None:
        sys.exit(no_scan_message(mode, auto=auto))
    return got


def add_scan_argument(ap, default: str = "kit2_page_scan", mode: str | None = None) -> None:
    """--scan, the page scan a runner navigates by, as every runner takes it; default LATEST_SCAN takes the camera's
    latest page scan made in shooting mode `mode`, the mode the runner works in, which a runner with that default
    names (scan_type)."""
    if default == LATEST_SCAN and not mode:
        raise ValueError("--scan's default LATEST_SCAN needs the shooting mode the runner works in")
    said = f"the camera's latest page scan made in {mode} mode" if default == LATEST_SCAN else default
    ap.add_argument("--scan", default=default, type=scan_type(mode),
                    help=f"the page scan (a run in the camera's runs/<model>_fw<fw>/, or a path; default: {said})")


def load_scan(scan, mode: str | None = None) -> tuple[list, dict]:
    """The page scan's Down cycle (scan_rekeyed.json without its last record, which is the start again) with each
    position's screen read by the current reader rather than the one at scan time, and the page model by key. scan:
    a folder, or LATEST_SCAN (scan_dir: the latest of the runner's mode, `mode` or the one --scan carries), which is
    said."""
    latest, scan = scan == LATEST_SCAN, scan_dir(scan, mode)
    if latest:
        print(f"page scan: {scan.name} (the camera's latest {recorded_mode(scan)} mode scan"
              f"{f' made in {AUTO}' if scan_auto(scan) else ''}; --scan names another)", flush=True)
    with open(scan / "scan_rekeyed.json", encoding="utf-8") as f:
        cycle = json.load(f)[:-1]
    with open(scan / "model.json", encoding="utf-8") as f:
        model = {p["key"]: p for p in json.load(f)}
    for pos in cycle:
        sc = screen.read(load(scan / "shots" / pos["frame"]))
        pos.update(signature=sc.signature, kind=sc.kind, row=sc.row, screen=sc)
    return cycle, model


def scan_position(cam, cycle) -> int | None:
    """The position of the page scan's cycle the screen shows now (camkit.screen.same_position), or None."""
    return next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)


def menu_from_shooting(cam) -> None:
    """MENU from the shooting screen. MENU can go unanswered just after a download (two in a row, 2026-10-30): look
    again at a fresh frame and only then press it once more, as prove_run's to_row does; a second MENU on a menu that
    is only slow closes it again."""
    cam.press("menu")
    for _ in range(3):
        if cam.read().kind != "shooting":
            break
        time.sleep(1.5)
        if cam.refresh("menu-check").kind != "shooting":
            break
        cam.press("menu")


def write_text(path, text: str) -> None:
    """The file replaced whole, by a temporary file beside it renamed over it: a run stopped mid-write (a crash, a
    killed process, a power cut: the data reaches the disk before the rename) leaves the file as it was, never cut
    short (a walk's tables.json holds hours of walking). The file keeps its permissions, and a new one gets what
    open() would give it (the umask's), not mkstemp's owner-only 0600. A symbolic link is written through, to the file
    it names, as open(path, "w") wrote through it."""
    path = Path(path)
    if path.is_symlink():
        path = path.resolve()
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode) if path.exists() else 0o666 & ~_UMASK)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def read_json(path):
    """A JSON file's contents, the file closed at once (json.load(open(...)) left it to the collector)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj, **dump) -> None:
    """obj as JSON (json.dumps' keywords: indent, ensure_ascii), the file replaced whole (write_text)."""
    write_text(path, json.dumps(obj, **dump))


class OcrUnavailable(RuntimeError):
    """The OCR engine could not run at all (its helper missing, its library not installed, not one frame read): no
    frame is unread for a reason of its own, so a caller stops before writing anything rather than record every frame
    as unread over the readings it had."""


def read_frames(paths, eng: str | None = None) -> tuple[dict, dict]:
    """OCR of many frames that does not stop at one it cannot read: ({frame: its lines}, {frame: why it was not
    read}). camkit.ocr.read raises when the helper cannot read a frame (a torn PNG; it once came back as a frame
    without text), which would end an overnight batch of thousands at the first; here the batch is read whole when it
    can be, else frame by frame (the frames already read come from camkit.ocr's cache), and each frame that fails is
    named with the helper's reason. A caller records such a frame as unread, never as a frame without text. An engine
    that cannot run (an ImportError, the helper itself missing, or not one frame of the batch read) is no torn frame:
    OcrUnavailable, and the caller stops."""
    from camkit import ocr
    paths = [Path(p) for p in paths]
    try:
        return ocr.read(paths, eng), {}
    except ImportError as e:
        raise OcrUnavailable(f"the OCR engine {eng or ocr.engine()!r} will not load: {e}") from e
    except Exception:           # the helper's RuntimeError, its exit status, RapidOCR's LoadImageError, a file gone
        pass
    got, unread = {}, {}
    for p in paths:
        try:
            got.update(ocr.read([p], eng))
        except ImportError as e:
            raise OcrUnavailable(f"the OCR engine {eng or ocr.engine()!r} will not load: {e}") from e
        except FileNotFoundError as e:
            if e.filename and Path(e.filename) != p:        # the helper itself, not the frame
                raise OcrUnavailable(f"the OCR helper is not there ({e.filename}): build it with kit/setup.py") from e
            unread[p] = f"{type(e).__name__}: {e}"
        except Exception as e:
            unread[p] = f"{type(e).__name__}: {e}"
    if paths and not got:
        first = next(iter(unread.values()), "")
        raise OcrUnavailable(f"not one of {len(paths)} frames was read by OCR (the first: {first})")
    return got, unread


def changes_of(changes) -> list:
    """A diff's changes (camkit.camset.diff) as a proof line holds them."""
    return [{"key": c.key, "before": c.before, "after": c.after} for c in changes]


@contextlib.contextmanager
def restoring(what: str = "the restore"):
    """Around a restore: any exception it raises (an upload the camera refused or did not answer, a STOP while waiting
    for the shooting screen, camkit.live.close giving up with its SystemExit) is said and turned into exit
    EXIT_UNRESTORED, so a chain stops there instead of starting its next step from a camera that may not be on its
    start file. A traceback's exit status 1 once let it go on. A second Ctrl-C (KeyboardInterrupt) is left as it is."""
    try:
        yield
    except SystemExit as e:
        if e.code in (None, 0, EXIT_UNRESTORED):
            raise
        print(f"{what} did not finish ({e}): the camera may not be on its start file", flush=True)
        raise SystemExit(EXIT_UNRESTORED) from e
    except Exception as e:
        print(f"{what} did not finish ({type(e).__name__}: {e}): the camera may not be on its start file", flush=True)
        raise SystemExit(EXIT_UNRESTORED) from e


def end_session(link, eyes, start: Path, why: str = "the settings download after the rows", tag: str = "after",
                reach=None, show: int | None = None, expected=frozenset()):
    """The session's end (decision 15): back to the shooting screen, then camkit.session.finish (download, compare with
    `start`, upload it when anything differs). `reach(link, eyes, why)` gets there: prove_run's to_shooting by default
    (MENU until the shooting screen), wait_shooting for a walker that has closed the menu itself. When the shooting
    screen does not come (to_shooting gives up after 5 minutes, wait_for after 15, the eyes' feed is gone), the restore
    is still tried, never skipped: the download closes a menu itself, and finish says so when the camera refuses it.
    A STOP asked for while that wait goes on (camkit.session.wait_for's StopRequested) ends the wait as the other
    failures do, and the restore goes on all the same (2026-11-08: it used to leave the camera unrestored and exit
    EXIT_UNRESTORED): the STOP still refuses every further press (camkit.link: no press, dial or set after a STOP but
    a cleanup press), never the download and the upload a restore is made of. A restore that raises (the upload
    refused or unanswered) exits EXIT_UNRESTORED (restoring). show=0 counts the records that differ from the start file
    and lists none (camkit.session.ended), for a prover that never prints a value the start file holds (afreg_run).
    expected: records no settings file sets which the run is known to write (camkit.session.ended), said by key and
    left out (memreg_run: a memory slot's registration marks)."""
    if reach is None:
        from proving.nav import to_shooting as reach
    with restoring(f"the session's end ({why})"):
        try:
            reach(link, eyes, why)
        except StopRequested:                   # the STOP holds for every press; only the restore goes on
            print("STOP file: the wait for the shooting screen ends here; restoring all the same", flush=True)
        except Exception as e:                  # Failed (no shooting screen), RuntimeError (the feed), LinkError
            print(f"   {why}: {type(e).__name__}: {e}; restoring all the same", flush=True)
        time.sleep(1)
        return session.finish(link, start, tag=tag, **({} if show is None else {"show": show}),
                              **({"expected": frozenset(expected)} if expected else {}))


def wait_shooting(link, eyes, why: str):
    """end_session's reach for a walker that closed the menu itself: wait for the shooting screen (camkit.session's
    wait_for, a black HDMI frame read on the SDK's OSD)."""
    session.wait_for(eyes, ("shooting",), why, link=link)


def restore_checked(run, ending, start: Path, note: str = "THE START FILE DID NOT TAKE: check the camera",
                    **kw) -> bool:
    """After end_session: when the start file was uploaded, reconnect and check it took (camkit.session.check_restore,
    which takes `kw`: show=0 says the count only); `note` is printed when it did not. True when the camera is as the
    start file has it, or nothing was uploaded."""
    if ending is None or not ending.uploaded:
        return ending is not None and ending.after is not None
    if session.check_restore(run, ending, start, **kw) != 0:
        print(note, flush=True)
        return False
    return True


class CloseGaveUp(RuntimeError):
    """camkit.live.close gave up getting back to the shooting screen (8 tries, "please close it on the camera by
    hand"), as an exception a session's own error path takes: the camera closed again and the start file restored,
    else exit EXIT_UNRESTORED. Its SystemExit once ended the process with exit 1 and no restore."""


def close_screen(cam, link) -> None:
    """camkit.live.close for a session's body (back to the shooting screen with cleanup presses): as it is, but its
    SystemExit is CloseGaveUp, so the session's error path (prover_session, a prover's own except) tries the restore."""
    try:
        close(cam, link)
    except SystemExit as e:
        if e.code in (None, 0):
            raise
        raise CloseGaveUp(str(e.code)) from e


# The screens camkit.live.close may give up on with the restore still tried over them (2026-11-08, the owner): kinds
# the reader knows, none of which executes anything on OK. A restore over an open option list was proved on the camera
# (runs/ILCE-1M2_fw4.00/kit2_dialog_restore, frame 00034_left-open.png: Grid Line Display one option along, its list
# left open; the download closed the list, the start file went up, 0 records differed after)
RESTORABLE_KINDS = frozenset({"menu", "submenu", "tiles", "list", "fields", "sidelist", "table", "checklist", "look",
                              "wbgrid", "notice"})


def restorable_after_close(cam) -> tuple:
    """(the last screen's kind, "") when the restore may be tried over it after camkit.live.close gave up: a kind
    RESTORABLE_KINDS names whose text safety.confirmation does not take for a confirmation. (None, why not) when the
    kind is another (unknown, a dialog, a picker), the text asks to execute something, or the frame or its text cannot
    be read: then no restore is tried, and a person looks."""
    try:
        kind = cam.read().kind
    except Exception as e:
        return None, f"its last screen cannot be read ({type(e).__name__}: {e})"
    if kind not in RESTORABLE_KINDS:
        return None, f"its last screen reads as {kind!r}, not a menu, list, panel or notice"
    try:
        text = text_of(cam)
    except Exception as e:
        return None, f"the text of its last screen ({kind}) cannot be read ({type(e).__name__}: {e})"
    if not text.strip():
        return None, f"no text could be read on its last screen ({kind}), so no confirmation check can judge it"
    why = safety.confirmation(text)
    if why:
        return None, f"its last screen ({kind}) reads as a confirmation ({why})"
    return kind, ""


def close_for_restore(cam, link) -> None:
    """After a body failed: back to the shooting screen with cleanup presses (camkit.live.close), which go out after a
    STOP too. When that fails as well (the eyes' feed gone: a RuntimeError), it is said and the session goes on to
    end_session, whose reach closes what is still open and whose restore is tried all the same: an unguarded close
    once skipped the restore. When camkit.live.close gives up (its SystemExit after 8 tries, or CloseGaveUp), the last
    screen decides (restorable_after_close, 2026-11-08): on a menu, submenu, the Main tiles, a list, number fields, a
    side list, a table, a checklist, a look panel, the white balance grid or a notice, none of them reading as a
    confirmation, it is said ("closing gave up on a <kind> screen; restoring all the same") and the session goes on to
    end_session as after the other failures, the download closing what is open. On any other screen (unknown, a
    dialog), one that reads as a confirmation, or none that can be read, the run ends as it says, with exit
    EXIT_UNRESTORED (restoring): no restore is tried over it, and a person looks."""
    with restoring("closing the camera before its restore"):
        try:
            close(cam, link)
        except (SystemExit, CloseGaveUp) as e:
            if isinstance(e, SystemExit) and e.code in (None, 0):
                raise
            kind, why_not = restorable_after_close(cam)
            if kind is None:
                print(f"closing gave up and {why_not}: no restore is tried over it", flush=True)
                raise                           # restoring: said, exit EXIT_UNRESTORED
            print(f"closing gave up on a {kind} screen; restoring all the same", flush=True)
        except Exception as e:
            print(f"closing: {type(e).__name__}: {e}; restoring all the same", flush=True)


@dataclass
class ProverSession:
    link: object
    cam: object
    start: Path
    restored: bool = False          # set when the session has ended: the start file is back on, checked


@contextlib.contextmanager
def prover_session(run, eyes, start_tag: str = "before", may_open=(), settle: float = SETTLE_S, say_start: bool = True,
                   end_why: str = "the settings download after the rows", end_tag: str = "after",
                   note: str = "THE START FILE DID NOT TAKE: check the camera", close_eyes: bool = True,
                   exit_unrestored: bool = True, show: int | None = None, expected=frozenset()):
    """A prover's session, as every prover in kit/provers/ ran it: the shooting screen, the start download, a pause
    for the menu lock, a LiveCamera (may_open: the never-open rows the owner allowed this prover), then the body. An
    exception in the body (a Failed row, a STOP, a dropped press) is printed and the camera closed back to the shooting
    screen (close_for_restore); either way the session ends restoring the start file (end_session) and the restore is
    checked. The eyes are closed at the end, unless close_eyes is False (a prover with a second session after this
    one). A start file that did not take (or a last download refused) ends the run, unless exit_unrestored is False,
    with status EXIT_UNRESTORED, after which kit/tools/chain.py stops the chain.
    Either way the verdict is left on the session (s.restored), for a prover with a second session to carry it to its
    own exit. show=0: the end and the restore's check count the records that differ from the start file without listing
    them (end_session), so no value the start file holds is printed. expected: the keys of records no settings file
    sets which the body is known to write (a memory slot's registration marks: memreg_run): the end and the check say
    them by key and leave them out of the count (camkit.session.ended), so they never fail the restore."""
    from proving.nav import to_shooting
    ending = start = None
    restored = False
    try:
        with Link(run) as link:
            eyes.attach(link)
            to_shooting(link, eyes, "the start download")
            start = link.download(start_tag)
            if say_start:
                print(f"start file: {start.name}", flush=True)
            time.sleep(settle)
            cam = LiveCamera(link, eyes, run, may_open=may_open)
            ps = ProverSession(link, cam, start)
            try:
                yield ps
            except Exception as e:
                print(f"stopped: {type(e).__name__}: {e}", flush=True)
                close_for_restore(cam, link)
            ending = end_session(link, eyes, start, end_why, tag=end_tag, show=show, expected=expected)
        restored = ps.restored = restore_checked(run, ending, start, note, **({} if show is None else {"show": show}),
                                                 **({"expected": frozenset(expected)} if expected else {}))
    finally:
        if close_eyes:
            eyes.close()
    if not restored and exit_unrestored:
        raise SystemExit(EXIT_UNRESTORED)


def proofs_file(run, context: str | None = None, extra: dict | None = None):
    """The run's proofs.jsonl opened for appending, each line tagged with `context` and the fields of `extra`
    (proving.base.Tagged; "allowance" for the never-open rows the owner allowed the run)."""
    from proving.base import Tagged
    return Tagged(open(run.dir / "proofs.jsonl", "a", encoding="utf-8", newline="\n"), context, extra)


def add_allow_argument(ap):
    """--allow LABEL, repeatable, as drive.py has it: a never-open row this run may enter (the owner's word, per row)."""
    ap.add_argument("--allow", action="append", default=[], help="a never-open label this run may enter")


def allowed_or_exit(labels) -> str:
    """Exit on a label no allowance opens (the cards, Initialize, Reset Network Set., credentials); print and return
    the allowance's words for the proof lines ("" with none)."""
    for label in labels:
        why = safety.allow_refused(label)
        if why:
            sys.exit(f"{label!r}: {why}")
    if labels:
        print(f"operator allowed these never-open rows: {', '.join(repr(x) for x in labels)}", flush=True)
    return safety.allowance(labels)
