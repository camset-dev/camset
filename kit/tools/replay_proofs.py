"""Diff every proof's settings files again with today's parser and compare with the changes the proof stored.

    .venv/bin/python kit/tools/replay_proofs.py [RUN] [--limit N] [--quiet]

Each proof in RUN's proofs.jsonl (a run in the camera's runs/<model>_fw<fw>/, or a path; kit2_pass2 by default) names
the camera's download it was diffed from ("base") and the one after its choice ("dat"), both in RUN/dat/ (or at the
run's top; a proof made in a run of its own, by hand or through the SDK, names that run, "run", and its files are in
that run's dat/), and keeps
the records that differed ("changes"; diffed against "diffed_with" instead of the base when the proof names one), as
kit/prove_run.py wrote them with camkit.camset's read and diff then. This reads both files again with today's
camkit.camset (its container block, record layout and volatile list) and diffs them the way prove_run does
(camset.diff, volatile records left out), then compares record by record: a record only one side has, or one whose
before or after value differs, is printed with the proof's row, label and files. A proof that stored only its own
records of a download other proofs share (the by-hand Time Code Preset proofs: one download per value set, each
field's proof storing that field's record) is counted apart as sharing it, when today's diff holds beside its own
exactly what those other proofs stored. The records a proof names as side effects ("side_effects": by key, as
kit/provers/afreg_run.py keeps its copies of the camera's own Tracking start area, or with the values a by-hand proof
saw, as the records an information screen's OK also rewrote) are left out of today's diff too, as they were kept out
of its changes. A registration mirror line ("kind": "registration mirror": a memory slot registered to see its copy
take a live setting, kit/provers/memreg_run.py, or a frame's place, framepos_run.py --zone-grid) claims one record, its
"key": what that record holds in the download after the registration must be its stored after, or the code the line
names when it stored no change (its before is the
download before that registration, which the prover may not have named as the base: framepos_run.py's zone sweep
diffed each place against the place before and, until 2026-11-09, named the sweep's first download as every place's
base). A proof whose files are gone is listed as missing; a proof that names no files (a held value, a
display proof) is counted apart. The main run (kit2_pass2) is replayed with the camera's other proof runs, the ones its
report reads (pass2_report.proof_runs), each run's summary on its own line; --alone replays the one run. Exit status 1
when any proof differs or a file is missing, else 0.

The camera is not touched and nothing is written. Use it after a change to the parser, the camera's container block
or the volatile list: a proof diffed again must say what it said when it was made.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, jsonl, paths  # noqa: E402
from pass2_report import proof_runs  # noqa: E402


def norm(v):
    """A value as proofs.jsonl stores it (JSON: tuples become lists)."""
    return json.loads(json.dumps(v))


def as_map(changes) -> dict:
    return {c["key"]: (norm(c["before"]), norm(c["after"])) for c in changes}


def where(run: Path, name: str, own: str | None = None) -> Path:
    """A proof's file: in the proof's own run (`own`, its "run": kit/drive.py's kit2_drive, the SDK's kit2_sdk_ev,
    beside RUN in the camera's runs) when it names one, else in RUN; in that run's dat/, else at its top (start files
    saved by hand, 2026-10-30). The 89 proofs recorded into kit2_pass2 by hand and through the SDK were counted missing
    until 2026-11-08, their files being in their own runs. Where the file is in none, the first place looked."""
    runs = ([run.parent / own] if own and own != run.name else []) + [run]
    places = [p for r in runs for p in (r / "dat" / name, r / name)]
    return next((p for p in places if p.exists()), places[0])


def replay(run: Path, limit: int = None):
    """(differing, shared, missing, unfiled, checked): differing as (proof, only_stored, only_now, values_differ) per
    proof; shared as (proof, the records today's diff adds), for a proof whose download other proofs share and whose
    extra records they stored, each as today's diff has it."""
    bases: collections.OrderedDict = collections.OrderedDict()      # proofs of one row share a base: a few kept

    def read_base(path):
        if path not in bases:
            bases[path] = camset.read(path)
            if len(bases) > 8:
                bases.popitem(last=False)
        bases.move_to_end(path)
        return bases[path]

    differing, shared, missing, unfiled, checked = [], [], [], 0, 0
    lines = jsonl.read(run / "proofs.jsonl")
    lines = lines[:limit] if limit else lines
    # what the proofs of one download stored between them (its run, its base, its file): the records a proof of one
    # field left to the proofs of the others
    together = collections.defaultdict(dict)
    for p in lines:
        if p.get("base") and p.get("dat"):
            together[(p.get("run"), p.get("diffed_with") or p["base"], p["dat"])].update(as_map(p.get("changes") or []))
    for p in lines:
        if not p.get("base") or not p.get("dat"):
            unfiled += 1
            continue
        base = p.get("diffed_with") or p["base"]       # a proof diffed against another download says which
        gone = [n for n in (base, p["dat"]) if not where(run, n, p.get("run")).exists()]
        if gone:
            missing.append((p, gone))
            continue
        # by path: two runs number their downloads alike (kit2_sdk_ev's 00002 is not kit2_pass2's)
        # named by key only (a prover's), or with the values a by-hand proof saw: no value of the proof's either way
        side = {x["key"] if isinstance(x, dict) else x for x in p.get("side_effects") or ()}
        now = as_map({"key": c.key, "before": c.before, "after": c.after}
                     for c in camset.diff(read_base(where(run, base, p.get("run"))),
                                          camset.read(where(run, p["dat"], p.get("run")))) if c.key not in side)
        stored = as_map(p.get("changes") or [])
        checked += 1
        if p.get("kind") == "registration mirror":
            # the one record the line claims, by what it holds after the registration (mirror_held): its stored after,
            # or, a line that stored no change, the code it says the record holds
            key = p.get("key")
            want = stored[key][1] if key in stored else p.get("index") if p.get("applied") else None
            if want is not None and mirror_held(read_base(where(run, p["dat"], p.get("run"))), p) != norm(want):
                differing.append((p, [], [], [key]))
            continue
        if now != stored:
            only_stored, only_now = sorted(stored.keys() - now.keys()), sorted(now.keys() - stored.keys())
            moved = sorted(k for k in stored.keys() & now.keys() if stored[k] != now[k])
            others = together[(p.get("run"), base, p["dat"])]
            if not only_stored and not moved and all(others.get(k) == now[k] for k in only_now):
                shared.append((p, only_now))
            else:
                differing.append((p, only_stored, only_now, moved))
    return differing, shared, missing, unfiled, checked


KEY = re.compile(r"(global|set(\d+)):0x([0-9a-f]+)")


def mirror_held(cs, p: dict):
    """What the record a registration mirror line claims ("key": "set1:0x0f32") holds in a settings file, as
    proofs.jsonl stores a value; None when the file has no such record."""
    m = KEY.fullmatch(p.get("key") or "")
    rec = cs.get(int(m[2]) if m and m[2] else 0, int(m[3], 16)) if m else None
    return None if rec is None else norm(rec.value())


def name(p) -> str:
    return f"{' > '.join(p.get('path') or [])} / {p.get('option', '') + ': ' if p.get('option') else ''}{p.get('label')}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run", nargs="?", default="kit2_pass2", type=paths.run_arg,
                    help="the proofs' run (a run in the camera's runs/<model>_fw<fw>/, or a path)")
    ap.add_argument("--limit", type=int, default=None, metavar="N", help="the first N proofs only (a trial)")
    ap.add_argument("--quiet", action="store_true", help="the summary only")
    ap.add_argument("--alone", action="store_true", help="the run only, without the camera's other proof runs")
    a = ap.parse_args(argv)
    run = Path(a.run)
    if not (run / "proofs.jsonl").exists():
        sys.exit(f"replay_proofs: {paths.shown(run)} holds no proofs.jsonl")
    rc = 0
    for part in proof_runs(run, a.alone):
        rc |= replay_one(part, a)
    return rc


def replay_one(run: Path, a) -> int:
    """One run's proofs diffed again, what differs printed (unless --quiet) and its summary line; 1 when any differs
    or a file is missing."""
    differing, shared, missing, unfiled, checked = replay(run, a.limit)
    if not a.quiet:
        for p, extra in shared:
            print(f"SHARED  {name(p)} ({p['base']} -> {p['dat']}): today's diff also holds {', '.join(extra)}, "
                  "as the other proofs of that download stored them")
        for p, only_stored, only_now, moved in differing:
            print(f"DIFFERS {name(p)} ({p['base']} -> {p['dat']})")
            for what, keys in (("stored only", only_stored), ("today only", only_now), ("values differ", moved)):
                if keys:
                    print(f"    {what}: {', '.join(keys)}")
        for p, gone in missing:
            print(f"MISSING {name(p)}: {', '.join(gone)}")
    by_key = collections.Counter(k for _, s, n, m in differing for k in s + n + m)
    if by_key and not a.quiet:
        print("records most often involved: " + ", ".join(f"{k} ({n})" for k, n in by_key.most_common(10)))
    print(f"{paths.shown(run)}: {checked} proofs diffed again, {checked - len(differing) - len(shared)} the same, "
          f"{len(shared)} sharing a download with other proofs, {len(differing)} differ, {len(missing)} with a file "
          f"missing, {unfiled} name no files")
    return 1 if differing or missing else 0


if __name__ == "__main__":
    sys.exit(main())
