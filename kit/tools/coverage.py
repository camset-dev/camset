"""The coverage ledger: what is settled about a camera's menus and its file, and what is left (docs/decisions/0023).

    .venv/bin/python kit/tools/coverage.py                     # counts per tab and status, options, records and bytes
    .venv/bin/python kit/tools/coverage.py --public-only       # the same from the public sources alone (a fresh clone)
    .venv/bin/python kit/tools/coverage.py --print             # the public form, as JSON: what any clone prints
    .venv/bin/python kit/tools/coverage.py --write             # the seen file into data/, the private form beside
                                                               # the looks file (private/evidence/<model>_fw<fw>/)
    .venv/bin/python kit/tools/coverage.py --check             # is the seen file current, the public form lean?
    .venv/bin/python kit/tools/coverage.py --todo [--tab T] [--mode Movie] [--needs remote-look|remote-proof|hand|
                                                    equipment|decision|kit] [--limit N]
    .venv/bin/python kit/tools/coverage.py --row "Wi-Fi Connect" [--public]
    .venv/bin/python kit/tools/coverage.py --record --path "Network > Wi-Fi > Wi-Fi Frequency Band" --did choose \\
        --option "5GHz" --start kit2_hand/dat/00001_before.DAT --end kit2_hand/dat/00002_after.DAT
    .venv/bin/python kit/tools/coverage.py --record --path "Setup > Setup Option > Version" --did open --result retract
    .venv/bin/python kit/tools/coverage.py --bundles           # per run folder: frames and downloads backing a valid
                                                               # proof, and those that back none (nothing deleted)
    .venv/bin/python kit/tools/coverage.py --proofs            # the proofs' validity: valid, inferred, unchecked
    .venv/bin/python kit/tools/coverage.py --shared            # the shared lists (a picker's slots): what each slot
                                                               # shows of its own, the values no slot is proved on

The camera is the one the kit works on (--camera, CAMSET_CAMERA or private/config.json: camkit.paths). The ledger is
generated each time from the definition, the hand tables, the camera file, the Help Guide's list, camkit.safety and,
on the computer that holds them, the camera's looks file, runs and leads (camkit.coverage says which and how), so it
cannot drift from them. The counts and --todo, --row, --bundles and --proofs read that full build; --public-only reads
the public sources alone. The public form (schemas/coverage.schema.json) is always the PUBLIC build's: the public
sources and the few facts a look establishes that hold for every camera of the model (camkit.coverage.ALLOWED: an
information screen and its address field names, a row that acts when opened, a hand check that changed a record, a row
of the maker's Save/Load list confirmed), which live in a small file of their own, the seen file
(data/<model>_fw<fw>/seen_<model>_fw<fw>.json, schemas/coverage-seen.schema.json): --write writes it where the looks
file is on this computer (the committed facts with the looks' own, a retraction of the looks taking a committed one
out), or where there is none yet. The public form holds never a state seen, a run, a date, a hash, a frame, a current
option or a value, and is never kept in a file (docs/decisions/0023): --print prints it, the same bytes in any clone,
which has no runs/ and no private/, and kit/tools/check_public.py refuses a copy in data/. --check says whether the
public form the public sources and the seen file give is lean (its schema, its closed vocabulary, no evidence), the
seen file too, and, where this computer holds the looks file, whether the seen file is what --write writes from them;
it exits 1 when any is not.

--record writes one look for an owner's hand check into the looks file (by "hand"), which it leaves owner-only: the
row (its tab and group first when the path starts with a tab's name), what was done (--did), the option, and the
records that differ between the two files, both of which must be camera downloads (camkit.provenance: their bytes in
the downloads manifest), by key alone, never a value. --result retract takes neither file and must name --did: it
says the look before it of that row, that did and that --option holds no more (the latest look of each wins), and
--write then takes the seen file's facts that look gave out of it. --leads names the mining's leads file when it is
not at private/evidence/<model>_fw<fw>/leads_<model>_fw<fw>.json.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import coverage as ledger, definitions, paths  # noqa: E402


def camera_or_exit() -> str:
    got = paths.camera()
    if not got:
        sys.exit(paths.no_camera_message())
    return got[0]


def show_counts(led, public: bool) -> None:
    c = ledger.counts(led, public)
    tabs = list(c["rows"])
    print(f"{led.camera}: {sum(len(e['path']) == 1 for e in led.rows)} top rows, "
          f"{sum(c['deeper'].values())} deeper rows, {sum(c['options'].values())} values of {len(led.options)} "
          f"settings, {len(led.records)} records ({led.src.records_from or 'no file'}); "
          f"{'public sources only' if not led.src.private else f'{len(led.src.looks)} looks'}")
    names = [s for s in ledger.STATUS_NAMES if any(s in c["rows"][t] for t in tabs)]
    width = max(len(t) for t in tabs) if tabs else 4
    print(f"\n{'top rows':{width}s}  " + "  ".join(f"{s}" for s in names))
    for t in tabs:
        print(f"{t:{width}s}  " + "  ".join(f"{c['rows'][t].get(s, 0):>{len(s)}d}" for s in names))
    print("\ndeeper rows: " + ", ".join(f"{s} {c['deeper'][s]}" for s in ledger.STATUS_NAMES if s in c["deeper"]))
    print("values:      " + ", ".join(f"{s} {c['options'][s]}" for s in ledger.STATUS_NAMES if s in c["options"]))
    order = ledger.PUBLIC_RECORD_NAMES if public else ledger.RECORD_NAMES
    for area, said in (("global", "live records"), ("set", "each memory set's records")):
        got = c["records"].get(area) or {}
        total = sum(n[1] for n in got.values()) or 1
        print(f"{said}: " + ", ".join(f"{s} {got[s][0]} ({got[s][1]} value bytes, {100 * got[s][1] / total:.1f}%)"
                                      for s in order if s in got))
    if led.unresolved:
        print(f"\n{len(led.unresolved)} looks name no row of the ledger (the private form lists them)")


def show_todo(led, a) -> None:
    items = ledger.todo(led, a.tab, a.mode, a.needs)
    print(f"{len(items)} entries left" + (f" (tab {a.tab})" if a.tab else "") + (f" (mode {a.mode})" if a.mode else "")
          + (f" (needs {a.needs})" if a.needs else "") + ", by expected yield:")
    for x in items[:a.limit]:
        e = x["entry"]
        near = f"; {len(x['near'])} unmapped records beside it" if x["near"] else ""
        seen = f"; a look saw {len(e['changed_in_looks'])} records change" if e.get("changed_in_looks") else ""
        left = f"; {x['left']} values still to try" if x["left"] else ""
        inferred = f"; {x['inferred']} values inferred from a shared list" if x["inferred"] else ""
        print(f"{x['yield']:4d}  {e['mode']} > {e['tab']} > {e['group']} > {' > '.join(e['path'])}: {e['status']}"
              f"{inferred}{left}{near}{seen}\n      needs {x['needs']}: {x['next']}")


def record(a, camera: str) -> None:
    from camkit import camset, provenance
    retract = a.result == "retract"
    if not a.path or not retract and (not a.start or not a.end):
        sys.exit("--record needs --path, --start and --end (two camera downloads, before and after the hand check); "
                 "--result retract needs --path and --did alone")
    if retract and not a.did:
        sys.exit("--result retract needs --did (open, choose or act): it withdraws the latest look of that row, that did "
                 "and that --option only")
    a.did = a.did or "choose"
    root = paths.runs_top() / camera
    files, keys = [], []
    for f in () if retract else (a.start, a.end):
        p = paths.run_path(f)
        try:
            provenance.check(p, root)
        except provenance.NotADownload as e:
            sys.exit(f"nothing recorded: {e}")
        files.append(p)
    if files:
        keys = [c.key for c in camset.diff(camset.read(files[0]), camset.read(files[1]))]
    labels = [x.strip() for x in a.path.split(" > ") if x.strip()]
    led = ledger.build(camera, public=True)
    tabs = set(led.src.definition.get("tabs") or []) | {"My Menu"}
    tab = group = None
    if labels and labels[0] in tabs and len(labels) >= 3:
        tab, group, labels = labels[0], labels[1], labels[2:]
    if not led.find(labels, None, tab, group):
        print(f"note: no ledger entry is {a.path!r} yet; the look is recorded all the same", flush=True)
    result = a.result or ("changed" if keys else "no_change")
    look = {"t": ledger.now(), "run": files[0].parent.parent.name if files and files[0].parent.name == "dat" else None,
            "kit": ledger.kit_commit(), "by": "hand", "mode": a.mode, "tab": tab, "group": group, "path": labels,
            "option": a.option, "did": a.did, "screen": None, "result": result,
            "blocker": {"row": a.blocker} if a.blocker and not retract else None, "fields": [], "kit_message": None,
            "start_sha256": provenance.sha256(files[0]) if files else None,
            "end_sha256": provenance.sha256(files[1]) if files else None,
            "records_changed": keys, "note": a.note or None}
    # owner-only, as every private run leaves it: the looks file names runs, days and the downloads' hashes
    if not ledger.append_look(camera, look, private=True, say=print):
        sys.exit(1)
    print(f"recorded: {' > '.join(labels)}{f' = {a.option!r}' if a.option else ''}, {a.did}, {result}; records that "
          f"differ: {', '.join(keys) or 'none'} (into {paths.shown(ledger.looks_file(camera))})")


def print_public(camera: str) -> None:
    """The public form on standard output: the public build of the public sources and the seen file as they stand
    (never this computer's looks or runs), so any clone prints the same bytes; nothing written. The bytes go under the
    text layer, which on Windows would write each newline as CR LF."""
    if not definitions.path(camera).exists():
        sys.exit(f"no definition for {camera}: kit/schema_update.py --write makes one")
    t = ledger.public_build_text(camera)
    why = ledger.public_problems(json.loads(t), t, camera=camera)
    if why:
        sys.exit(f"the public form would hold what decision 16 keeps private, so it is not printed: {'; '.join(why[:3])}")
    out = getattr(sys.stdout, "buffer", None)
    if out is None:                         # a stream with no bytes under it: its text is all there is
        sys.stdout.write(t)
        return
    sys.stdout.flush()
    out.write(t.encode("utf-8"))
    out.flush()


def check(camera: str, led) -> None:
    """--check: the public form the public sources and the seen file give, and the seen file, lean
    (camkit.coverage.public_build_problems); where the looks file is on this computer, the seen file what --write
    writes from it. Exit status 1, with what to do, when any is not so."""
    seen = ledger.seen_file(camera)
    found = ledger.public_build_problems(camera)
    for x in found:
        print(f"  {x}")
    stale = False
    if led.src.private and led.src.looks_present:
        local = ledger.text(ledger.seen_doc(camera, ledger.public_seen(led)))
        stale = not seen.exists() or seen.read_text(encoding="utf-8") != local
    if found:
        sys.exit(f"the public form of {camera} or {paths.shown(seen)} holds what it may not ({len(found)} places, above)"
                 + ("; this computer's looks would also change the seen file" if stale else ""))
    if stale:
        sys.exit(f"this computer's looks would change {paths.shown(seen)}: kit/tools/coverage.py --write writes it")
    print(f"the public form of {camera}, built from the public sources and "
          f"{paths.shown(seen) if seen.exists() else 'no seen file'}, is lean"
          + (", and the seen file is what this computer's looks give" if led.src.private and led.src.looks_present
             else " (no looks file read, so the seen file is judged as it stands)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="write the seen file (and the private form)")
    ap.add_argument("--public-only", action="store_true", help="from the public sources alone, as a fresh clone")
    ap.add_argument("--print", action="store_true",
                    help="print the public form, as JSON: the public sources and the seen file's build, as any clone "
                         "prints it (it is never kept in a file)")
    ap.add_argument("--check", action="store_true",
                    help="say whether the public form is lean, the seen file too, and whether this computer's looks "
                         "would change the seen file (exit status 1 when any is so)")
    ap.add_argument("--todo", action="store_true", help="what is left, by expected yield")
    ap.add_argument("--tab")
    ap.add_argument("--mode")
    ap.add_argument("--needs", choices=ledger.NEEDS)
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--row", help="one row (its last label), with its citations")
    ap.add_argument("--public", action="store_true", help="with --row: what the public form says (the public build), "
                                                          "no citations")
    ap.add_argument("--record", action="store_true", help="record an owner's hand check (by \"hand\")")
    ap.add_argument("--path", help="with --record: the row, \"Tab > Group > Row [> Row]\" or its labels from the top row")
    ap.add_argument("--did", choices=ledger.LOOK_DID[:3],
                    help="with --record: what the hand check did (default choose); with --result retract, what the look "
                         "withdrawn did, which it must name")
    ap.add_argument("--option", help="with --record: the option chosen, as the camera writes it")
    ap.add_argument("--start", help="with --record: the camera download before the check")
    ap.add_argument("--end", help="with --record: the camera download after it")
    ap.add_argument("--result", choices=ledger.LOOK_RESULTS, help="with --record: when the files do not say it "
                                                                 "(refused, greyed, acted), or retract: the look "
                                                                 "before of that row, did and option holds no more")
    ap.add_argument("--blocker", help="with --record --result greyed: the row the camera named")
    ap.add_argument("--note", help="with --record: words of your own (no value)")
    ap.add_argument("--bundles", action="store_true", help="per run folder: what backs a valid proof (nothing deleted)")
    ap.add_argument("--proofs", action="store_true", help="the proofs' validity, repeats and evidence bundles")
    ap.add_argument("--shared", action="store_true",
                    help="the shared lists (one row's settings listing the same values): their proofs, the values no "
                         "setting of a list is proved on, the settings whose own record shows no value")
    ap.add_argument("--leads", type=Path, help="the mining's leads file (leads.json's shape)")
    a = ap.parse_args()
    camera = camera_or_exit()
    if a.record:
        record(a, camera)
        return
    if a.print:
        print_public(camera)
        return
    src = ledger.load_sources(camera, public=a.public_only, leads=a.leads)
    if not src.definition:
        sys.exit(f"no definition for {camera}: kit/schema_update.py --write makes one")
    led = ledger.build(camera, src=src, validity=bool(a.write or a.bundles or a.proofs or a.row))
    if a.row:
        # --public: the public build's word (the public sources and the allow-list), never the full build's
        lines = ledger.row_view(ledger.public_ledger(led) if a.public else led, a.row, public=a.public or a.public_only)
        print("\n".join(lines) if lines else f"no row of the ledger is labelled {a.row!r}")
        return
    if a.todo:
        show_todo(led, a)
        return
    if a.shared:
        print("\n".join(ledger.shared_view(led)))
        return
    if a.bundles:
        rows = ledger.bundles_report(led)
        if not rows:
            print("no run folders on this computer")
        tot = [0] * 8
        for r in rows:
            f, d = r["frames"], r["downloads"]
            tot = [x + y for x, y in zip(tot, f + d, strict=True)]
            print(f"{r['run']:32s} frames: {f[0]} back a valid proof ({f[2]} bytes), {f[1]} do not ({f[3]} bytes); "
                  f"downloads: {d[0]} ({d[2]} bytes), {d[1]} ({d[3]} bytes)")
        if rows:
            print(f"{'all':32s} frames: {tot[0]} ({tot[2]} bytes) / {tot[1]} ({tot[3]} bytes); downloads: {tot[4]} "
                  f"({tot[6]} bytes) / {tot[5]} ({tot[7]} bytes). Nothing was deleted.")
        return
    if a.proofs:
        print(json.dumps(led.proof_summary, indent=1))
        return
    if a.check:
        check(camera, led)
        return
    show_counts(led, public=a.public_only)
    if a.write:
        written = ledger.write(led, private_path=False if a.public_only else None)
        for p in written:
            print(f"written: {paths.shown(p)}")


if __name__ == "__main__":
    main()
