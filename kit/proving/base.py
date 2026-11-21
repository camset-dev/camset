"""The prover's places and basics: where the camera's runs are (pass 1's map, the table walk's and the axis walk's
results), the exceptions a row ends with, the proofs file every prover appends to, the attempts file, and pass 1's
saved frames.

MAP, TABLES and AXES are read as base.NAME at call time: main() points MAP at a pass-3 run's own map (prove_run --map),
and the tests point TABLES, FRAME_DIRS and RUN_ROOT at their own files and the ILCE-1M2's runs. Only MAP is rebound by
a run; a copy of the others by name (prove_run's PASS1 and AXES, proving.tables' RUN_ROOT) stays right."""
import json
import re
import time
from pathlib import Path

from camkit import paths
from camkit.session import (LOCK_S, LockSeen, lock_log, lock_measured, lock_over,  # noqa: F401 (the lock after a
                            wait_lock)                                            # download, for the provers)
from runner import read_json

RUN_ROOT = paths.module_root()          # the camera's runs, runs/<model>_fw<fw>/ (camkit.paths)
PASS1 = RUN_ROOT / "kit2_pass1"



class Failed(Exception):
    pass


class Blocked(Failed):
    """The camera would not open the row: "not available as follows <setting> <value>". A skip, not
    a failure: nothing changed, the run goes on to the next row."""
    def __init__(self, msg: str, reason: str):
        super().__init__(msg)
        self.reason = reason


MAP = PASS1 / "map_all.json"


def number(v: str):
    d = re.sub(r"[^\d.]", "", v or "").strip(".")
    try:
        return float(d) if d else None
    except ValueError:
        return None


def finish_attempt(run, attempt: str, name: str, put_back: dict | None = None):
    """The attempt ended as it began: kit/pass2_report.py counts only the proofs of attempts recorded here. `put_back`
    notes the records the put-back left differing and why that is no failure (put_back_leftovers)."""
    with open(run.dir / "attempts.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "attempt": attempt, "row": name, "complete": True,
                            **({"put_back": put_back} if put_back else {})}) + "\n")


FRAME_DIRS = (PASS1 / "shots", RUN_ROOT / "kit2_panels" / "shots")
_FRAME_RUN: dict = {}


def frame_file(map_path, fr: str):
    """Pass 1's saved frame for a map row: frame numbers repeat across runs (pass 1 and the panels
    run both have 00263_right.png), so the run whose map recorded this row with this frame decides;
    the first folder holding the name is only the fallback."""
    if not _FRAME_RUN:
        # a merged map (kit/pass1_map.py) names each row's crawl ("run"), whose shots/ hold its frames
        for mp in dict.fromkeys((PASS1 / "map_all.json", MAP)):
            try:
                rows = read_json(mp)["rows"]
            except (OSError, ValueError, KeyError, TypeError):
                continue
            for r in rows:
                if r.get("run"):
                    for o in r.get("options") or []:
                        _FRAME_RUN.setdefault((tuple(r["path"]), o["frame"]), RUN_ROOT / r["run"] / "shots")
        for run in ("kit2_pass1", "kit2_panels", "kit2_pass3", "kit2_play", "kit2_play2"):
            mp = RUN_ROOT / run / "map.json"
            if mp.exists():
                for r in read_json(mp)["rows"]:
                    for o in r["options"]:
                        _FRAME_RUN.setdefault((tuple(r["path"]), o["frame"]), RUN_ROOT / run / "shots")
    d = _FRAME_RUN.get((tuple(map_path or ()), fr))
    if d is not None and (d / fr).exists():
        return d / fr
    return next((dd / fr for dd in FRAME_DIRS if (dd / fr).exists()), None)


AXES = RUN_ROOT / "kit2_axes" / "axes.json"


def map_key(map_path, root) -> str:
    """How an axis walk's entry names the run's own map it walked (kit/axis_walk.py --map, its "map"), and how
    jobs.axis_jobs finds the entries of the map a run proves with: the map's path under the camera's runs (`root`),
    with forward slashes ("kit2_fin_crawl_brk/map.json"), else its whole path."""
    p = Path(map_path).resolve()
    try:
        return p.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()

TABLES = RUN_ROOT / "kit2_tables" / "tables.json"


class RestoreAfter(Exception):
    """A row whose proofs are all made but whose saved option is left for the session's upload to
    put back: the session ends there (not a failure)."""


# How find_row found the row it is on, where not by OCR's reading of its bar: {row label: "lit letter"} for a lit
# one-letter row OCR dropped and proving.screens.lit_letter labelled from two agreeing signs (2026-11-21); at_label keeps
# it, and Tagged writes it into the row's proof lines ("row_by"), so kit/pass2_report.py never takes such a line's move
# of a record another row's proofs own as the row's setting. Private-run detail: proofs.jsonl alone (decision 16)
ROW_BY: dict = {}


class Tagged:
    """The proofs file, every line tagged with the state it was proved in ("Switch V/H AF Area = AF
    Point + AF Area"): the same row proved under another setting is another row in the report. A line whose path goes
    through a row found by its lit letter alone (ROW_BY; a bracketed tail aside) carries "row_by"; every other line is
    written as it comes."""
    def __init__(self, f, context: str | None, extra: dict | None = None):
        self.f, self.context, self.extra = f, context, extra or {}

    def write(self, line: str):
        if (self.context or self.extra or ROW_BY) and line.strip():
            r = json.loads(line)
            path = r.get("path") if isinstance(r.get("path"), list) else []
            by = next((ROW_BY[k] for k in (re.split(r" \[", str(e))[0] for e in path) if k in ROW_BY), None)
            if self.context or self.extra or by:
                r = {**r, **self.extra}
                if by:
                    r["row_by"] = by
                if self.context:
                    r["context"] = self.context
                line = json.dumps(r) + "\n"
        self.f.write(line)

    def flush(self):
        self.f.flush()

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
