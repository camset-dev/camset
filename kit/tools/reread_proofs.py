"""The vision model's reading of the option each proof chose, for the proofs that have none: the third source of a name.

    .venv/bin/python kit/tools/reread_proofs.py [RUN] [--reader NAME] [--limit N] [--all]

A list, dialog, side list, axis or table proof in RUN's proofs.jsonl (a run in the camera's runs/<model>_fw<fw>/, or a
path; kit2_pass2 by default) keeps the frame it chose its option on ("chosen_frame"). Proofs written while the vision
reader was off carry no "vlm" reading; this asks the reader what the option under the cursor says on that frame
(prove_run's question, camkit.vlm's PROMPTS["option"]) and appends one line per frame to RUN/readings.jsonl:
{frame, kind, row, keys, label, reading, reader, date}. kit/pass2_report.py takes it as the "vlm" of a proof that has
none, and its name rule weighs it with the map's label and the bar's OCR (the vision model breaks ties; a reading far
from both is listed as a name dispute, never taken alone).

The camera is not touched: only frames already saved are read. Restartable: frames already in readings.jsonl are
skipped (--all asks again, also for proofs with a reading of their own). The reader is the "second" one (the next that
answers stands in when it is off, camkit.vlm.stand_in), or the configured reader --reader names (omlx, the local
one). Answers are cached (camkit.vlm), so asking again costs nothing. --limit N reads N frames, for a trial.
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import config, jsonl, paths, vlm  # noqa: E402

KINDS = ("list", "dialog", "sidelist", "axis", "table")


def todo(run: Path, redo: bool) -> list:
    """The proofs to read, one per chosen frame, in the order they were written: no reading yet (any with redo), the
    frame on disk, and not already in readings.jsonl unless redo."""
    done = set() if redo else {r.get("frame") for r in jsonl.read(run / "readings.jsonl")}
    out, seen = [], set()
    for r in jsonl.read(run / "proofs.jsonl"):
        f = r.get("chosen_frame")
        if r.get("kind") not in KINDS or not f or f in seen or f in done or (r.get("vlm") and not redo):
            continue
        if not (run / "shots" / f).exists():
            continue
        seen.add(f)
        out.append(r)
    return out


def use_reader(name: str | None) -> str:
    """The reader that answers: --reader's configured one by name (it plays the "second" role for this process, as
    prove_run's ask_second then asks it), else the "second" one. Returns its name."""
    if not name:
        return vlm.role("second")["name"]
    cfg = next((r for r in config()["readers"] if r["name"] == name), None)
    if cfg is None:
        sys.exit(f"--reader {name!r}: no reader of that name in private/config.json")
    vlm.assign_role("second", cfg)
    return name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", nargs="?", default="kit2_pass2", type=paths.run_arg,
                    help="the proofs' run (a run in the camera's runs/<model>_fw<fw>/, or a path)")
    ap.add_argument("--reader", default=None, metavar="NAME",
                    help="the configured reader to ask, by its name (omlx: the local one), instead of the \"second\"")
    ap.add_argument("--limit", type=int, default=None, metavar="N", help="read N frames only (a trial)")
    ap.add_argument("--all", action="store_true", help="ask again for every frame, also proofs with a reading")
    a = ap.parse_args(argv)
    run = Path(a.run)
    from pass2_report import row_name
    from prove_run import PROMPTS, ask_second
    reader = use_reader(a.reader)
    jobs = todo(run, a.all)[:a.limit] if a.limit else todo(run, a.all)
    print(f"{len(jobs)} frames to read with {reader!r} -> {paths.shown(run / 'readings.jsonl')}", flush=True)
    t0, n = time.monotonic(), 0
    with open(run / "readings.jsonl", "a", encoding="utf-8", newline="\n") as out:
        for r in jobs:
            try:
                v = ask_second((run / "shots" / r["chosen_frame"]).read_bytes(), PROMPTS["option"], timeout=120)
            except Exception as e:              # noqa: BLE001 - the reader is away: stop, the next run resumes here
                sys.exit(f"the reader did not answer on {r['chosen_frame']} ({e}); {n} frames read, run again to go on")
            reading = str(v.get("selected") or "") if isinstance(v, dict) else ""
            who = vlm.playing("second")["name"]
            out.write(json.dumps({"frame": r["chosen_frame"], "kind": r["kind"], "row": row_name(r),
                                  "keys": sorted({c["key"] for c in r.get("changes") or []}), "label": r.get("label"),
                                  "reading": reading, "reader": who, "date": datetime.date.today().isoformat()},
                                 ensure_ascii=False) + "\n")
            out.flush()
            n += 1
            if n % 20 == 0 or n == len(jobs):
                spent = time.monotonic() - t0
                print(f"  {n}/{len(jobs)} frames, {spent:.0f} s, about {spent / n * (len(jobs) - n):.0f} s left",
                      flush=True)
    print(f"read {n} frames; kit/pass2_report.py takes them as the vision reading of the proofs without one", flush=True)


if __name__ == "__main__":
    main()
