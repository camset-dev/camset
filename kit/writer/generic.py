"""The plain pass, for any definition but the ILCE-1M2 firmware 4.00's: each proved value the label the camera showed,
a record the definition lacks a setting named by its menu row, and the evidence; a camera with no definition yet gets
one started from its data/ folder and the run's newest download (seed)."""
import collections
import re
import sys
from pathlib import Path

from camkit import definitions, option_tree, paths
from pass2_report import latest_run, num, registration_mirrors, report_proofs
from runner import read_json

from .fromdata import from_data, model_refused, say_stale, write_definition
from .gate import gate, questions
from .labels import clean
from .offered import check_video_systems, with_video_systems
from .proofs import (axis_value_rows, disputed_out, kept_proof, menu_row, mixed, note_readers, print_kept,
                     sampled_scale, with_allowances, with_in_sets_proved, with_menu_rows, with_names, written_values,
                     with_option_trees, with_scales, without_observed)


def newest_download(run: Path) -> Path:
    files = sorted((p for p in (run / "dat").glob("*.DAT") if not p.name.startswith("_camlink_upload")),
                   key=lambda p: (p.stat().st_mtime, p.name))    # never the copy an upload left (kit/link/camlink.cpp)
    if not files:
        sys.exit(f"schema_update: {run}/dat holds no settings file to read the layout from")
    return files[-1]


def seed(camera: str, run: Path) -> dict:
    """A definition to start from, for a camera with none yet: its model, firmware and layout signature from the run's
    newest download (read through the camera file's container block), its tabs from the camera file's tab colours,
    and no settings; generic() adds what the report proves, from_data() the camera section."""
    from camkit import camset
    cam = definitions.camera_file(camera)
    if not cam.exists():
        sys.exit(f"schema_update: no camera file for {camera} ({cam}): write data/{camera}/camera_{camera}.json first, "
                 "its container block and tab colours among it (docs/DATA_CONTRACTS.md; docs/REMAPPING_PLAYBOOK.md, "
                 "\"New model: first day\")")
    facts = read_json(cam)
    cs = camset.read(newest_download(run))
    model, firmware = paths.split(camera)
    return {"model": model, "tabs": list(facts.get("tab_colors") or {}),
            "layouts": [{"signature": cs.signature(), "model": model, "firmware": firmware,
                         "note": f"{model} firmware {firmware}",
                         "doc": f"docs/models/{camera}.md"}],
            "settings": [], "menu": [], "camera": {}}


GENERIC_KEY = re.compile(r"global:0x([0-9a-f]{4})(?:\[(\d+)\])?")


def grid_labels(s: dict, proved: dict, changed: list) -> None:
    """A White Balance grid record's names in the plain pass, which has no range and step to name every point from:
    the camera's readout ("B7", "0", "A7") of the points every grid walk visits whatever the grid held, both ends of
    the axis and 0, into the setting's values where they lack it. The grid stays sampled, its proofs not listed, and a
    point only the walk's put-back gave (kit/pass2_report.py's grid_values: the value the grid held when the walk
    began) is left out, for it is the camera's own setting (docs/decisions/0016)."""
    nums = [v for v in proved.values() if isinstance(v, (int, float))]
    if not nums:
        return
    keep = {min(nums), max(nums), 0}
    labels = dict((v, lab) for v, lab in s.get("values") or [])
    for lab, v in proved.items():
        if v in keep and labels.get(v) != clean(lab):
            changed.append((s["key"], s["name"], v, labels.get(v), clean(lab)))
            labels[v] = clean(lab)
    s["values"] = [[v, lab] for v, lab in sorted(labels.items())]


def generic(doc: dict, report: list, run: Path, date: str) -> list:
    """Pass 2's report into a definition, with none of the ILCE-1M2's tables: each proved value the label the camera
    showed (a number field keeps its numbers), a live record the definition lacks a setting named by its menu row,
    and each proved setting its evidence ("proved": the run, the date, the rows, the values; of what it held before only
    a value a counted line still wrote, kept_proof; a record another proof run proved names that run and the day of
    its latest proof, latest_run), with
    what backs each value's name (proved.names). Memory-set records are left out; a record the report
    marks not one to one loses its proof and is marked disputed (disputed_out). Returns the changes, as main() prints
    them."""
    from camkit import camset
    cs = camset.read(newest_download(run))
    by_key = {s["key"]: s for s in doc["settings"]}
    changed, menus, proved, sampled = [], collections.defaultdict(set), collections.defaultdict(set), {}
    from_start = collections.Counter()
    start_only = collections.defaultdict(set)      # values only a start line credited (pass2_report.start_lines)
    came = collections.defaultdict(dict)       # the runs whose proofs proved each record, each its latest day
    readers, disputed = collections.defaultdict(dict), set()
    order = max([s.get("order", 0) for s in doc["settings"]] + [0])
    # an axis row named after the value its axis stood on is named by its item alone (menu_row), in a new setting's
    # name and note as in its proof's rows: that value was the camera's own setting when the row began
    axis_rows = axis_value_rows(option_tree.read_proofs(run))
    # the values the lines the report counts wrote: of the proof the definition held before, only such a value is kept
    # beside the report's (kept_proof); an old menu row never is
    written = written_values(*report_proofs(run)[:2], {e["row"] for e in report}) \
        if (run / "proofs.jsonl").exists() else {}
    for e in report:
        row = menu_row(re.sub(r" \[field \d+\]$", "", e["row"]), axis_rows)
        for k, r in e["records"].items():
            m = GENERIC_KEY.fullmatch(k)
            if mixed(r) or r["verdict"] == "readout" or not m:
                if mixed(r):
                    print(f"  left out, not one to one: {k} {row[:60]} (prove it again)")
                    disputed.add(k)
                continue
            s = by_key.get(k)
            grid = "wbgrid" in e.get("kinds", ())
            # a number field, a list of numbers, a White Balance grid (its ends and 0 named, grid_labels), or a listed
            # scale whose samples lie on a line (sampled_scale): sampled, its proofs not listed, for one is the
            # camera's own setting (docs/decisions/0016)
            numbers = "[field" in e["row"] or (bool(r["proved"]) and all(num(lab) is not None for lab in r["proved"])) \
                or grid or (s is not None and r.get("linear") is True and sampled_scale(s, set(r["proved"].values())))
            if s is None and k.split("[")[0] in by_key:
                continue                               # a slot of a record the definition holds whole
            if s is None:
                rid, index = int(m[1], 16), (int(m[2]) if m[2] else None)
                rec = cs.get(0, rid)
                if rec is None:
                    continue
                order += 1
                path = row.split(" [")[0].split(" > ")
                s = {"key": k, "area": "global", "id": rid, **({"index": index} if index is not None else {}),
                     "name": path[-1], "source": "Menu", "tab": path[0] if len(path) > 1 else "",
                     "group": " > ".join(path[:-1]) if len(path) > 1 else path[0], "order": order, "values": [],
                     # how it was found is evidence (camkit.definitions keeps note_evidence private)
                     "note": "", "note_evidence": f"proved on the camera through {row} (runs/{run.name})",
                     "in_sets": cs.get(1, rid) is not None,
                     "scalar": index is not None or rec.count == 1, "size": rec.size, "count": rec.count, "modes": ""}
                doc["settings"].append(s)
                by_key[k] = s
                changed.append((k, s["name"], "new", None, row))
            menus[k].add(row)
            for by, day in (r.get("runs") or {run.name: None}).items():
                came[k][by] = max(filter(None, (came[k].get(by), day)), default=None)
            start_only[k] |= {v for v in (r.get("start_only") or {}).values() if not isinstance(v, (list, dict))}
            if r.get("sampled_from_start"):
                # a sample stepped from the option the camera held (pass2_report.sampled_from_start): a count, its values
                # and their readings nowhere (docs/decisions/0016), unless another row walks the record whole
                from_start[k] += r.get("sample_proofs", e["options"])
                continue
            if numbers:
                sampled.setdefault(k, {"proofs": 0, "linear": None})
                sampled[k]["proofs"] += e["options"]
                if r.get("linear") is not None:
                    was = sampled[k]["linear"]
                    sampled[k]["linear"] = bool(r["linear"]) if was is None else was and bool(r["linear"])
                if grid:
                    grid_labels(s, r["proved"], changed)
                continue
            labels = dict((v, lab) for v, lab in s.get("values") or [])
            for lab, v in r["proved"].items():
                if labels.get(v) != clean(lab):
                    changed.append((k, s["name"], v, labels.get(v), clean(lab)))
                    labels[v] = clean(lab)
            s["values"] = [[v, lab] for v, lab in sorted(labels.items())]
            proved[k] |= set(r["proved"].values())
            note_readers(readers, k, r)
    kept_old = {}
    for k in set(proved) | set(sampled) | set(from_start):
        s = by_key[k]
        by, day = latest_run(came.get(k), run.name, date)          # another proof run's, dated by its download
        new = {"run": by, "date": day, "menu": sorted(menus[k])}
        if k in sampled:
            new["sampled"] = sampled[k]
        elif from_start[k] and not proved[k]:
            new["sampled"] = {"proofs": from_start[k], "linear": None, "from_start": True}
        else:
            new["values"] = sorted(proved[k])
        # what the definition held stays, but a value only a start line accounted for
        s["proved"], kept_old[k] = kept_proof(s.get("proved"), new, frozenset(start_only[k] - proved[k]),
                                              frozenset(written.get(k, ())))
    print_kept(kept_old, by_key)
    disputed_out(doc, disputed & set(by_key))
    for s in doc["settings"]:
        with_names(s, readers[s["key"]], {}, {})
    return changed


def generic_main(target: Path, run: Path, write: bool, force: bool = False, accept_stale: bool = False) -> dict:
    """schema_update for any definition but the ILCE-1M2 firmware 4.00's: the plain pass, from a seed when the camera
    has no definition yet. Returns the definition, written with write."""
    import datetime
    camera = target.stem
    report_file = run / "report.json"
    if not report_file.exists():
        sys.exit(f"schema_update: no pass-2 report in {run} (kit/pass2_report.py writes it)")
    doc = definitions.load(target) if target.exists() else seed(camera, run)
    why = model_refused(run, doc)
    if why:
        sys.exit(f"schema_update: {why}")
    if not target.exists():
        print(f"{camera} has no definition yet: starting {paths.shown(target)} from data/{camera}/ "
              f"and {run.name}'s downloads")
    date = datetime.date.fromtimestamp(report_file.stat().st_mtime).isoformat()
    report = read_json(report_file)
    changed = generic(doc, report, run, date)
    # a live setting's memory copy seen taken by a registration, and the owner's word for a never-open row in the
    # evidence of what it proved, as the ILCE-1M2's pass has them
    mirrors = registration_mirrors(run)
    allowed = collections.defaultdict(set)
    for e in report:
        for k, r in e["records"].items():
            allowed[k] |= set(r.get("allowances") or ())
    for k, m in mirrors.items():
        if m.get("allowance"):
            allowed[k].add(m["allowance"])
    print(f"in sets: {with_in_sets_proved(doc, mirrors)} settings whose memory copy a registration took; allowances: "
          f"{with_allowances(doc, allowed)} settings took the owner's word into their evidence")
    with_menu_rows(doc, axis_value_rows(option_tree.read_proofs(run)))     # the rows a definition kept, named so too
    with_option_trees(doc, run)
    with_scales(doc, run)
    # the values offered under one video system only, where rows were walked under each (no hand table here)
    with_video_systems(doc, report, report_proofs(run)[0] if (run / "proofs.jsonl").exists() else [], {}, run.parent, run)
    check_video_systems(doc, run.parent)
    without_observed(doc)
    doc = from_data(doc)
    print(f"{sum(1 for s in doc['settings'] if s.get('proved'))} of {len(doc['settings'])} settings proved; "
          f"{len(changed)} labels changed or added")
    for k, name, v, old, new in changed:
        print(f"  {k} {name[:44]:44s} {v!s:>4}: {old!r} -> {new!r}")
    # the plain pass gives every proved value the camera's label, so no conflict stands; the rest is the gate's
    gate(questions(report, (), frozenset(s["key"] for s in doc["settings"])), camera, force, write)
    if write:
        write_definition(target, doc, accept_stale)       # every refusal first, then the reset file, then this
        print(f"wrote {target}")
        say_stale(target)
    return doc
