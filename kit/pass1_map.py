"""Merge pass 1's walks and label readings into one map: per row, its options in order, with labels.

    .venv/bin/python kit/pass1_map.py [CRAWL ...] [--dry-run] [--replace]   # runs in the camera's runs/<model>_fw<fw>/

Each crawl's map goes into <crawl>/map.json, and every crawl's rows together into kit2_pass1/map_all.json, the map
kit/prove_run.py, kit/axis_walk.py, kit/schema_update.py and the proof viewer read; each row there names its crawl
("run"), whose shots/ hold its frames. A map_all.json that differs from the one made now is replaced only with
--replace (the differences are listed); --dry-run writes nothing. Into a run folder a --network or --owner run marked,
it writes owner-only (camkit.runs.private_if_marked).

Inputs: <run>/options.jsonl (kit/pass1_labels.py: OCR under the cursor + vLLM) and, if present,
<run>/tiebreak.jsonl (omlx as a third reader where those two disagreed) and <run>/checked_labels.json
({frame: label} read by eye, which wins). Rules, from the readings of
2026-10-28:
  - carousels (dialog): OCR of the orange line under the title wins; the VLMs tend to read the
    option's icon ("BRK WB") instead of its name ("White Balance Bracket: Lo"); likewise grids, whose
    subtitle names the selected cell ("Tracking: Spot M"; the VLM said "M");
  - lists, checklists, side lists: the two readers when they agree, else the majority of three;
  - the cursor on OK/Cancel is a button, not an option;
  - star ratings, and anything without a majority, go on the review list.
It prints a summary with the review list.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths  # noqa: E402
from camkit.runs import private_if_marked  # noqa: E402
from runner import read_json  # noqa: E402

BUTTONS = re.compile(r"^(ok|cancel|ok cancel)$", re.I)
MAP_ALL = "map_all.json"


def build(run: Path) -> dict:
    """The crawl's map, {"rows": [{"path", "kind", "options": [{"index", "label", "source", "frame"}]}], "review"}."""
    if not (run / "options.jsonl").exists():       # never an empty map over the crawl's own (it may hold corrections)
        sys.exit(f"{run}: no options.jsonl (kit/pass1_labels.py writes it); no map made")
    opts = jsonl.read(run / "options.jsonl")
    ties = {t["frame"]: t for t in jsonl.read(run / "tiebreak.jsonl")}
    # labels read by eye off the frame, keyed by frame: they win over every reader (star ratings, which
    # OCR and the VLM agreed on wrongly: "Rating Only" read as "Rating (★★★★)", 2026-10-30)
    checked = read_json(run / "checked_labels.json") if (run / "checked_labels.json").exists() else {}
    rows = collections.OrderedDict()
    review = []
    for o in opts:
        key = tuple(o["path"])
        vsel = str((o.get("vlm") or {}).get("selected") or "")
        ocr = o.get("ocr") or ""
        label, source = None, None
        if o["frame"] in checked:
            label, source = checked[o["frame"]], "checked by eye"
        elif BUTTONS.match(ocr.strip()):
            label, source = ocr.strip(), "button"
        elif o["kind"] == "dialog" and ocr:
            label, source = ocr, "ocr (carousel line)"
        elif o["kind"] == "checkgrid" and ocr:
            label, source = ocr, "ocr (grid subtitle)"       # the VLM reads the cell's icon ("C1" for "Custom 1")
        elif o["kind"] == "fields" and ocr:
            label, source = ocr, "ocr (each field)" if o.get("agreed") else "ocr (each field; vLLM differs)"
        elif o.get("agreed"):
            label, source = ocr or vsel, "ocr + vllm"
        elif o["frame"] in ties and ties[o["frame"]].get("winner"):
            t = ties[o["frame"]]
            label, source = t["winner"], "majority of three"
        if label is None:
            review.append({"path": list(key), "frame": o["frame"], "ocr": ocr, "vllm": vsel,
                           "omlx": ties.get(o["frame"], {}).get("omlx", "")})
            label, source = vsel or ocr, "unresolved"
        rows.setdefault(key, {"path": list(key), "kind": o["kind"], "options": []})["options"].append(
            {"index": o["index"], "label": label, "source": source, "frame": o["frame"]})
    # a label corrected by hand in the map made before (the playbook: the entry's "by" says how) is kept
    fixed = {}
    if (run / "map.json").exists():
        for r in read_json(run / "map.json").get("rows") or []:
            for op in r.get("options") or []:
                if op.get("by"):
                    fixed[(tuple(r["path"]), json.dumps(op.get("index")), op.get("frame"))] = op
    for r in rows.values():
        for op in r["options"]:
            hand = fixed.get((tuple(r["path"]), json.dumps(op["index"]), op["frame"]))
            if hand:
                op.update(label=hand["label"], source="by hand", by=hand["by"])
    return {"rows": list(rows.values()), "review": review}


def merged(maps: list) -> tuple:
    """(map_all, duplicates): every crawl's rows in the order given, each row naming its crawl ("run": its frames are
    in that run's shots/, which the proof viewer and the provers look in); a row path two crawls hold keeps the
    first's, and the later ones are listed."""
    rows, seen, dupes = [], {}, []
    for name, m in maps:
        for r in m["rows"]:
            key = tuple(r["path"])
            if key in seen:
                dupes.append((" > ".join(r["path"]), seen[key], name))
                continue
            seen[key] = name
            rows.append({**r, "run": name})
    return {"rows": rows}, dupes


def differences(old: dict, new: dict) -> list:
    """What a new map_all changes in the old one, by row: added, gone, changed."""
    a = {tuple(r["path"]): r for r in old.get("rows") or []}
    b = {tuple(r["path"]): r for r in new.get("rows") or []}
    out = [f"added {' > '.join(k)}" for k in b if k not in a]
    out += [f"gone {' > '.join(k)}" for k in a if k not in b]
    out += [f"changed {' > '.join(k)}" for k in b if k in a and a[k] != b[k]]
    return out


def summary(m: dict) -> str:
    n = sum(len(r["options"]) for r in m["rows"])
    src = collections.Counter(op["source"] for r in m["rows"] for op in r["options"])
    return f"{len(m['rows'])} rows, {n} options; label sources: {dict(src)}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pass 1's maps: each crawl's map.json, and every crawl's rows in "
                                             f"kit2_pass1/{MAP_ALL}, which kit/prove_run.py and the proof viewer read")
    ap.add_argument("crawls", nargs="*", default=["kit2_pass1"],
                    help="crawl runs (in the camera's runs/<model>_fw<fw>/, or paths), each with its options.jsonl; "
                         "a row two of them hold keeps the first's (default: kit2_pass1)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be written; write nothing")
    ap.add_argument("--replace", action="store_true", help=f"replace a {MAP_ALL} that differs from the one made now")
    ap.add_argument("--own", action="store_true",
                    help=f"write each crawl's own map.json and leave {MAP_ALL} alone: a walk of one row in one state "
                         "(kit/pass3_run.py) is no part of pass 1's map")
    a = ap.parse_args(argv)
    runs = [paths.run_path(c) for c in a.crawls]
    if not a.dry_run:
        # a --network or --owner run's folder: map.json, and the map of them all where it is one, 0600 in it too
        root = paths.run_root(required=False)
        private_if_marked(*runs, *([root / "kit2_pass1"] if root is not None else []))
    maps = []
    for run in runs:
        m = build(run)
        maps.append((run.name, m))
        print(f"{run.name}: {summary(m)}; for review: {len(m['review'])}")
        for r in m["review"]:
            print(f"  {r['frame']:16s} {' > '.join(r['path'][1:])[:30]:30s} OCR={r['ocr'][:20]!r} "
                  f"vLLM={r['vllm'][:20]!r} omlx={r['omlx'][:20]!r}")
        if not a.dry_run:
            with open(run / "map.json", "w", encoding="utf-8", newline="\n") as f:
                json.dump(m, f, indent=1, ensure_ascii=False)
    if a.own:
        return maps[-1][1] if maps else None
    everything, dupes = merged(maps)
    for path, first, later in dupes:
        print(f"  {path}: in {first} and {later}; {first}'s kept")
    target = paths.run_root() / "kit2_pass1" / MAP_ALL
    old = read_json(target) if target.exists() else None
    changed = differences(old, everything) if old is not None else None
    print(f"{MAP_ALL}: {summary(everything)}, from {', '.join(n for n, _ in maps)}")
    if old is not None and not changed:
        print(f"{paths.shown(target)} is current")
        return everything
    if changed:
        print(f"it differs from {paths.shown(target)} in {len(changed)} rows:\n  " + "\n  ".join(changed[:30]))
    if a.dry_run:
        print("--dry-run: nothing written")
        return everything
    if changed and not a.replace:
        sys.exit(f"{paths.shown(target)} is left as it is: --replace writes the map made now over it (a map corrected "
                 f"by hand keeps its corrections only in the crawls' own map.json)")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        json.dump(everything, f, indent=1, ensure_ascii=False)
    print(f"wrote {paths.shown(target)}")
    return everything


if __name__ == "__main__":
    main()


