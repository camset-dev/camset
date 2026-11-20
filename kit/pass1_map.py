"""Merge pass 1's walks and label readings into one map: per row, its options in order, with labels.

    .venv/bin/python kit/pass1_map.py [CRAWL ...] [--dry-run] [--replace]   # runs in the camera's runs/<model>_fw<fw>/

Each crawl's map goes into <crawl>/map.json, and every crawl's rows together into kit2_pass1/map_all.json, the map
kit/prove_run.py, kit/axis_walk.py, kit/schema_update.py and the proof viewer read; each row there names its crawl
("run"), whose shots/ hold its frames. A map_all.json that differs from the one made now is replaced only with
--replace (the differences are listed); --dry-run writes nothing. Into a run folder a --network or --owner run marked,
it writes owner-only (camkit.runs.private_if_marked). A crawl run with --skip-settled (kit/crawl_run.py) left out the
rows the coverage ledger had settled, so its map has holes: it is refused for kit2_pass1's map, and --own says so. A row
a crawl only skipped as not seen opened on this body (camkit.first_open.SKIPPED) keeps the mapping made before of it.

Inputs: <run>/options.jsonl (kit/pass1_labels.py: OCR under the cursor + the second reader) and, if present,
<run>/tiebreak.jsonl (kit/tiebreak.py: the third role's readers where those two disagreed) and
<run>/checked_labels.json ({frame: label} read by eye, which wins). The sources and the review list name the second
reader "vllm" and the third "omlx", whatever readers play those roles (the servers that first did); a further third
reader's reading is under "voters". Rules, from the readings of 2026-10-28:
  - carousels (dialog): OCR of the orange line under the title wins; the vision readers tend to read the
    option's icon ("BRK WB") instead of its name ("White Balance Bracket: Lo"); likewise grids, whose
    subtitle names the selected cell ("Tracking: Spot M"; the vision reader said "M");
  - lists, checklists, side lists: the two readers when they agree, else the majority of the voices on the option's
    tiebreak line (majority: OCR, the second reader and each third reader, one vote per model family, as the line's
    "models" name them, none for a family that read two things); a reading neither OCR nor the second reader gave,
    which third readers alone carry, gets no label from the vote and goes on the review list with every voice's
    reading, its source "unresolved, third readers alone" (decision 22: 7 of the 10 such readings on the a1 II's own
    lines were wrong); a line kit/tiebreak.py wrote before it named its models keeps the winner it wrote, the majority
    of three, until kit/tiebreak.py --revote asks today's third readers about it;
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
from camkit import coverage, first_open, jsonl, paths  # noqa: E402
from camkit.reading import model_id, standing  # noqa: E402
from camkit.runs import private_if_marked  # noqa: E402
from page_model import same_option  # noqa: E402
from runner import read_json  # noqa: E402

BUTTONS = re.compile(r"^(ok|cancel|ok cancel)$", re.I)
MAP_ALL = "map_all.json"
COUNTED = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def voices(line: dict) -> list:
    """[(who, source, reading)] of a tiebreak.jsonl line (kit/tiebreak.py) in the order they count: OCR ("ocr", its
    source "ocr"), the second reader ("vllm"), the first third reader ("omlx"), then each further one ("voters", in the
    order asked: {"reader", "model", "selected"}). A reader's source is "reader:" and its model's family
    (camkit.reading.model_id) as the line's "models" ({"vllm": ..., "omlx": ...}) and each voter's "model" name it: two
    readers of one family are one source. Read only for a line that names its models (counted)."""
    models = line.get("models") or {}
    out = [("ocr", "ocr", str(line.get("ocr") or "")),
           ("vllm", f"reader:{model_id(models.get('vllm'))}", str(line.get("vllm") or "")),
           ("omlx", f"reader:{model_id(models.get('omlx'))}", str(line.get("omlx") or ""))]
    out += [(str(v.get("reader")), f"reader:{model_id(v.get('model'))}", str(v.get("selected") or ""))
            for v in line.get("voters") or [] if isinstance(v, dict)]
    return out


def majority(said: list) -> tuple:
    """(the reading that stands, the voices behind it) of voices() or (None, ()): camkit.reading.standing, the rule
    camkit.reading.tally counts by, with page_model.same_option as the comparison pass 1 has always made. A reading
    stands when voices of two sources or more name it (OCR is one source, each model family one) and no reading that
    names something else has as many; a source counts once however many of its readers name it, and not at all where
    its readers read two things; voices stand together only as a group whose every two readings are one option. The
    reading kept is the group's first in voices' order (OCR's, else the second reader's, else a third reader's). No
    majority is no reading: the option goes on the review list, never a guess."""
    group = standing([v for v in said if v[2].strip()], lambda a, b: same_option(a[2], b[2]), lambda v: v[1])
    return (group[0][2], tuple(w[0] for w in group)) if group else (None, ())


def third_only(text, line: dict) -> bool:
    """Whether the reading a majority names is one neither OCR nor the second reader gave on the line (its "ocr" and
    "vllm", page_model.same_option), so third readers alone carry it. It never stands on those later votes alone (as
    camkit.reading.tally refuses a group without the first two votes): the option goes on the review list, the line
    marked "third_only" (kit/tiebreak.py), for a look by eye. A reading the second reader gave whose family read two
    things (no vote) is not one: the second reader gave it."""
    return bool(text) and not any(same_option(text, line.get(k) or "") for k in ("ocr", "vllm"))


def settled(line: dict):
    """The reading a tiebreak line's voices settle (majority), or None: none stands, or third readers alone carry it
    (third_only)."""
    text, _ = majority(voices(line))
    return None if third_only(text, line) else text


def counted(line: dict) -> bool:
    """Whether a tiebreak line names the models that read it ("models", kit/tiebreak.py since 2026-11-19): its vote is
    then taken afresh by family (majority); an older line's is the "winner" it was written with."""
    return isinstance(line.get("models"), dict)


THIRD_ONLY = ", third readers alone"       # added to an unresolved option's source where third readers alone named it


def tie_label(line: dict) -> tuple:
    """(the label a tiebreak line settles, or None; the map's source for it): the majority of its voices by family
    ("majority of three", "majority of four"... by the voices on the line) where it names its models, else the winner
    it was written with ("majority of three"). Where third readers alone carry the majority (third_only): no label,
    and the source "unresolved" + THIRD_ONLY."""
    if not counted(line):
        return line.get("winner") or None, "majority of three"
    said = voices(line)
    text, _ = majority(said)
    if third_only(text, line):
        return None, "unresolved" + THIRD_ONLY
    return text, f"majority of {COUNTED.get(len(said), len(said))}"


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
        elif o["frame"] in ties:
            label, source = tie_label(ties[o["frame"]])
        if label is None:
            tie = ties.get(o["frame"], {})
            alone = source == "unresolved" + THIRD_ONLY
            review.append({"path": list(key), "frame": o["frame"], "ocr": ocr, "vllm": vsel, "omlx": tie.get("omlx", ""),
                           **({"voters": [{"reader": v.get("reader"), "selected": v.get("selected") or ""}
                                          for v in tie["voters"]]} if tie.get("voters") else {}),
                           **({"third_only": True} if alone else {})})
            label, source = vsel or ocr, "unresolved" + (THIRD_ONLY if alone else "")
        rows.setdefault(key, {"path": list(key), "kind": o["kind"], "options": []})["options"].append(
            {"index": o["index"], "label": label, "source": source, "frame": o["frame"]})
    # a label corrected by hand in the map made before (the playbook: the entry's "by" says how) is kept, and so is a
    # row the crawl's laps only skipped as not seen opened on this body (camkit.first_open.SKIPPED)
    fixed, unseen = {}, unseen_only(run)
    if (run / "map.json").exists():
        for r in read_json(run / "map.json").get("rows") or []:
            if tuple(r["path"]) not in rows and under(r["path"], unseen):
                rows[tuple(r["path"])] = r
            for op in r.get("options") or []:
                if op.get("by"):
                    fixed[(tuple(r["path"]), json.dumps(op.get("index")), op.get("frame"))] = op
    for r in rows.values():
        for op in r["options"]:
            hand = fixed.get((tuple(r["path"]), json.dumps(op["index"]), op["frame"]))
            if hand:
                op.update(label=hand["label"], source="by hand", by=hand["by"])
    return {"rows": list(rows.values()), "review": review}


def unseen_only(run: Path) -> set:
    """The row paths (labels from the top-level row) a crawl's rows.jsonl holds only as skipped by a first open's rule
    (camkit.first_open.SKIPPED), never walked in another lap."""
    skipped, other = set(), set()

    def walk(rows, parent):
        for r in rows:
            if not isinstance(r, dict):
                continue
            k = (*parent, r.get("label") or f"#{r.get('slot')}")
            (skipped if str(r.get("outcome") or "").startswith(first_open.SKIPPED) else other).add(k)
            walk(r.get("submenu") or [], k)
    walk(jsonl.read(run / "rows.jsonl", bad="skip") if (run / "rows.jsonl").exists() else [], ())
    return skipped - other


def under(path, rows: set) -> bool:
    """Whether the map row's path is one of `rows` or under one."""
    return any(tuple(path[:i]) in rows for i in range(1, len(path) + 1))


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
    # a crawl given --skip-settled did not open the rows the coverage ledger settled: its map has a hole at each
    for run in runs:
        holes = coverage.crawl_skipped(run)
        if holes and not a.own:
            sys.exit(f"{run.name} skipped {holes} rows the coverage ledger had settled (kit/crawl_run.py "
                     "--skip-settled): its map has holes there, so it is no part of pass 1's map; crawl again without "
                     "--skip-settled (or write its own map.json alone with --own)")
        if holes:
            print(f"{run.name}: {holes} rows skipped as settled (--skip-settled): its map.json has holes there")
        unseen = coverage.crawl_skipped(run, first_open.SKIPPED)
        if unseen:
            print(f"{run.name}: {unseen} rows skipped as not seen opened on this body (kit/crawl_run.py): the mapping "
                  "made before of each is kept")
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
            more = "".join(f" {v['reader']}={str(v['selected'])[:20]!r}" for v in r.get("voters") or [])
            print(f"  {r['frame']:16s} {' > '.join(r['path'][1:])[:30]:30s} OCR={r['ocr'][:20]!r} "
                  f"vLLM={r['vllm'][:20]!r} omlx={r['omlx'][:20]!r}{more}")
        alone = [(r["path"], op) for r in m["rows"] for op in r["options"] if str(op.get("source")).endswith(THIRD_ONLY)]
        if alone:
            print(f"  {len(alone)} options third readers alone named, a reading neither OCR nor the second reader gave: "
                  f"on the review list, no label from the vote (source \"unresolved{THIRD_ONLY}\"); look at each frame "
                  "by eye")
            for path, op in alone:
                print(f"    {op['frame']:16s} index {json.dumps(op['index'])} {' > '.join(path)[:60]}")
        old_ties = sum(1 for t in jsonl.read(run / "tiebreak.jsonl") if not counted(t))
        if old_ties:
            print(f"  {old_ties} tiebreak lines name no models: each keeps the winner it was written with (the "
                  f"majority of three); kit/tiebreak.py --revote --was MODEL {run.name} asks today's third readers "
                  "about them")
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
    unseen = set().union(*(unseen_only(run) for run in runs))
    have = {tuple(r["path"]) for r in everything["rows"]}
    everything["rows"] += [r for r in (old or {}).get("rows") or []
                           if tuple(r["path"]) not in have and under(r["path"], unseen)]
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


