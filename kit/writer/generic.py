"""The plain pass, for any definition but the ILCE-1M2 firmware 4.00's: each proved value the label the camera showed,
a record the definition lacks a setting named by its menu row, and the evidence; a camera with no definition yet gets
one started from its data/ folder and the run's newest download (seed). The camera's own hand tables
(data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, writer/hand_tables.py, its hand evidence put back) are applied
where it has them (writer/hand_facts.py says which tables, and refuses the ones only the ILCE-1M2's pass reads); a
camera with none, or with every table empty, gets the plain pass as it was before it read any."""
import collections
import re
import sys
from pathlib import Path

from camkit import definitions, option_tree, paths
from pass2_report import latest_run, mirrored_values, num, registration_mirrors, report_proofs
from runner import read_json

from . import hand_evidence, hand_facts, hand_tables
from .copies import with_copies
from .fromdata import from_data, model_refused, say_stale, write_definition
from .gate import gate, questions
from .labels import clean
from .offered import check_video_systems, with_video_systems
from .proofs import (axis_value_rows, disputed_out, kept_proof, menu_row, mixed, note_readers, print_kept, reworded,
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


def no_tables() -> hand_tables.Tables:
    """A camera's hand tables when it has none: every table empty, no evidence."""
    return hand_tables.Tables(**hand_tables.empty(), HAND_EVIDENCE=None)


def generic(doc: dict, report: list, run: Path, date: str, tables=None, unresolved: list = None,
            allowed: dict = None, evidence: dict = None, taken_out: set = None) -> list:
    """Pass 2's report into a definition: each proved value the label the camera showed (a number field keeps its
    numbers), a live record the definition lacks a setting named by its menu row, and each proved setting its evidence
    ("proved": the run, the date, the rows, the values; of what it held before only a value a counted line still wrote,
    kept_proof; a record another proof run proved names that run and the day of its latest proof, latest_run), with
    what backs each value's name (proved.names). Memory-set records are left out; a record the report
    marks not one to one loses its proof and is marked disputed (disputed_out). Returns the changes, as main() prints
    them.

    `tables`: the camera's public hand tables and `evidence` its hand evidence apart (writer/hand_tables.load_plain;
    None: every table empty, no evidence): a proved value VALUE_FIXES or CAROUSEL names takes the table's name ("hand
    table") whatever the proof read; a KEEP_LABELS record's values keep the definition's names (a value it does not
    name yet takes the camera's label), its conflicts added to `unresolved` for the gate; a record NEW_LIKE names is
    laid out like its sibling once every row is read (lay_like: the report's order changes nothing, and a later run
    lays out one an earlier run could not); a FRAME_PROOFS entry listing values with no hand proof is proved by the
    report's lines alone (hand_facts.by_lines); then the hand facts (writer/hand_facts.py: NEW_RECORDS, VALUE_FIXES,
    RECORD_FIXES, UNPROVED, PP7_VALUES, FRAME_PROOFS, a registration's allowance into `allowed`, what the tables no
    longer name taken out, the entries that cannot take effect said) before a disputed record loses its proof, and the
    not-offered marks (NOT_OFFERED) before the names' sources are set, a value a hand table names that no proof covers
    named "counted" (hand_facts.named_not_proved), and a NEW_LIKE record's filled values named as its sibling's stand
    (hand_facts.like_fill_names). The evidence reaches only the fields the definition keeps private; a reason's day or
    a mark's evidence the hand evidence no longer gives is taken out on purpose, said and added to `taken_out` for the
    write. Every step is a no-op on empty tables. CONTEXT_WORDS is generic_main's (proofs.reworded)."""
    from camkit import camset
    T = tables if tables is not None else no_tables()
    E = evidence or {}
    taken_out = set() if taken_out is None else taken_out
    unresolved = [] if unresolved is None else unresolved
    allowed = collections.defaultdict(set) if allowed is None else allowed
    cs = camset.read(newest_download(run))
    by_key = {s["key"]: s for s in doc["settings"]}
    changed, menus, proved, sampled = [], collections.defaultdict(set), collections.defaultdict(set), {}
    from_start = collections.Counter()
    start_only = collections.defaultdict(set)      # values only a start line credited (pass2_report.start_lines)
    came = collections.defaultdict(dict)       # the runs whose proofs proved each record, each its latest day
    readers, disputed = collections.defaultdict(dict), set()
    # what backs a value's name against the reading (a hand table's), and a rule's copy (a sibling's fill): with_names
    over, derived = collections.defaultdict(dict), collections.defaultdict(dict)
    like_rows = {}                             # a NEW_LIKE record's rows, laid out after the loop (lay_like)
    named = set()                              # every record key a report row names
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
            named.add(k)                       # every key a row names, proved or not (hand_facts.new_records)
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
            if k in T.NEW_LIKE:
                # laid out like its sibling once every row is read (lay_like), whatever the report's order
                like_rows.setdefault(k, []).append((e, r, row))
            elif s is None:
                s = menu_setting(k, m, row, cs, order + 1, run)
                if s is None:
                    continue
                order += 1
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
                if grid and s is not None:
                    grid_labels(s, r["proved"], changed)
                continue
            if k in T.KEEP_LABELS or k in T.NEW_LIKE:
                # proved, but not named by the options (KEEP_LABELS: a flag several options share), its conflicts left
                # to the gate; or a record laid out like its sibling (NEW_LIKE), named once every row is read (lay_like)
                proved[k] |= set(r["proved"].values())
                note_readers(readers, k, r)
                if k in T.NEW_LIKE:
                    continue
                # the names the definition holds stay, a hand table's where the camera read otherwise; a value it does
                # not name yet takes the camera's label, its readers' source, so no proved value is left without a name
                labels = dict((v, lab) for v, lab in s.get("values") or [])
                for lab, v in r["proved"].items():
                    if isinstance(v, (list, dict)):
                        continue
                    if v not in labels:
                        labels[v] = clean(lab)
                        changed.append((k, s["name"], v, None, clean(lab)))
                    elif labels[v] != clean(lab):
                        over[k][v] = "hand table"
                s["values"] = [[v, lab] for v, lab in sorted(labels.items())]
                unresolved += [{"key": k, "row": re.sub(r" \[field \d+\]$", "", e["row"]), "value": n["value"],
                                "label": n.get("schema"), "camera": n.get("camera")}
                               for n in r.get("notes") or [] if n.get("kind") == "conflict"]
                continue
            labels = dict((v, lab) for v, lab in s.get("values") or [])
            for lab, v in r["proved"].items():
                # a label checked by hand stands (VALUE_FIXES), and a carousel's option takes its own name (CAROUSEL)
                new = T.VALUE_FIXES.get((k, v)) or T.CAROUSEL.get((k, v)) or clean(lab)
                if (k, v) in T.VALUE_FIXES or (k, v) in T.CAROUSEL:
                    over[k][v] = "hand table"
                if labels.get(v) != new:
                    changed.append((k, s["name"], v, labels.get(v), new))
                    labels[v] = new
            s["values"] = [[v, lab] for v, lab in sorted(labels.items())]
            proved[k] |= set(r["proved"].values())
            note_readers(readers, k, r)
    # a chain's sibling first, else in key order: the same definition whatever the report's or the file's order
    for k in [x for x in hand_facts.like_order(T) if x in like_rows]:
        order = lay_like(doc, by_key, k, like_rows[k], T, run, cs, order, derived, changed)
        if k not in by_key:                    # not added (lay_like said why): nothing of its proofs is written
            for d in (proved, sampled, from_start, menus, came, start_only):
                d.pop(k, None)
    kept_old = {}
    by_lines = hand_facts.by_lines(T, E)       # what a hand table listed, proved by the lines alone
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
        s["proved"], kept_old[k] = kept_proof(None if k in by_lines else s.get("proved"), new,
                                              frozenset(start_only[k] - proved[k]), frozenset(written.get(k, ())))
    print_kept(kept_old, by_key)
    # the hand facts, in the ILCE-1M2's pass's order (writer/hand_facts.py); each a no-op on empty tables
    reported = named | set(proved) | set(sampled) | set(from_start)     # what a row names stays though no table does
    hand_facts.new_records(doc, by_key, T, E, cs, over, changed, reported)
    hand_facts.value_fixes(by_key, T, over, changed)
    hand_facts.record_fixes(by_key, T, E, changed)
    hand_facts.unproved(doc, by_key, T, E, changed, taken_out)
    hand_facts.extra_values(by_key, T, over, changed)
    hand_facts.frame_proofs(by_key, T, E, over, changed, mirrored_values(run) if T.FRAME_PROOFS else {}, allowed)
    hand_facts.not_found(by_key, T)
    disputed_out(doc, disputed & set(by_key))
    hand_facts.not_offered(doc, T, E, report, run.parent, derived, taken_out)
    hand_facts.named_not_proved(doc, over)     # a value a hand table names that no proof covers: named, not proved
    for s in doc["settings"]:
        with_names(s, readers[s["key"]], over[s["key"]], derived[s["key"]])
    hand_facts.like_fill_names(doc, T)         # a NEW_LIKE record's fill: established only where the sibling's is
    return changed


def menu_setting(k: str, m, row: str, cs, order: int, run: Path) -> dict | None:
    """A live record the definition lacks, a setting named by its menu row (`row`, the proof's, `m` its key's match),
    laid out from the run's newest download (`cs`), numbered `order`; None when the download holds no such record."""
    rid, index = int(m[1], 16), (int(m[2]) if m[2] else None)
    rec = cs.get(0, rid)
    if rec is None:
        return None
    path = row.split(" [")[0].split(" > ")
    return {"key": k, "area": "global", "id": rid, **({"index": index} if index is not None else {}),
            "name": path[-1], "source": "Menu", "tab": path[0] if len(path) > 1 else "",
            "group": " > ".join(path[:-1]) if len(path) > 1 else path[0], "order": order, "values": [],
            # how it was found is evidence (camkit.definitions keeps note_evidence private)
            "note": "", "note_evidence": f"proved on the camera through {row} (runs/{run.name})",
            "in_sets": cs.get(1, rid) is not None,
            "scalar": index is not None or rec.count == 1, "size": rec.size, "count": rec.count, "modes": ""}


# the fields a record NEW_LIKE lays out takes from its sibling and the start file (hand_facts.like_setting), which a
# later run puts right when the record was laid out otherwise (its sibling missing then, or the entry changed)
LIKE_FIELDS = ("area", "source", "tab", "group", "order", "scalar", "modes", "id", "name", "note", "note_evidence",
               "in_sets", "size", "count")


def lay_like(doc: dict, by_key: dict, k: str, rows: list, tables, run: Path, cs, order: int, derived: dict,
             changed: list) -> int:
    """A record NEW_LIKE names, laid out like its sibling once the report is read (hand_facts.like_setting, from the
    run's start file and the first of its rows; its later rows' values named by the same rule, like_more), so the
    report's order changes nothing. The definition lacks it: added. It holds it laid out otherwise (named by its menu
    row on a run that lacked the sibling, or before the entry changed): laid out again, its values the rule's and any
    other it held kept. It holds it so laid out: its names stay, a value it does not name yet named by the rule. The
    definition lacks the sibling, or the start file the record: said, and a record it lacks is named by its menu row
    (a later run lays it out). Returns the order number taken so far."""
    from camkit import camset
    like, name = tables.NEW_LIKE[k]
    whole = k in tables.NEW_WHOLE_LABELS
    s = by_key.get(k)
    start = hand_facts.run_start(run.parent, run)
    if like not in by_key or camset.read(start).get(0, int(k.split("0x")[1], 16)) is None:
        print(f"  new like  {k}: " + (f"the definition has no {like} to lay it out like yet" if like not in by_key
                                      else f"the run's start file ({start.name}) holds no such record")
              + ("; named by its menu row" if s is None else "; left as it is"))
        if s is None:
            s = menu_setting(k, GENERIC_KEY.fullmatch(k), rows[0][2], cs, order + 1, run)
            if s is None:
                print(f"  new like  {k}: not added, the run's newest download holds no such record either")
                return order
            order += 1
            doc["settings"].append(s)
            by_key[k] = s
            changed.append((k, s["name"], "new", None, rows[0][2]))
        for _e, r, _row in rows:
            like_more(s, r, whole)
        return order
    e0, r0, _ = rows[0]
    fresh = hand_facts.like_setting(k, by_key, e0, r0, tables.NEW_LIKE, tables.NEW_WHOLE_LABELS, start, run.name)
    for _e, r, _row in rows[1:]:
        like_more(fresh, r, whole)
    proved = {v for _e, r, _row in rows for v in r["proved"].values() if not isinstance(v, (list, dict))}
    fill = {v for v, _ in fresh["values"] if v not in proved}
    fix = tables.RECORD_FIXES.get(k) or {}
    names = {name, fix.get("name")}
    # laid out otherwise: a name, tab, group or order unlike the layout's, its own RECORD_FIXES' fields counted as the
    # layout's (they are put on it after, hand_facts.record_fixes)
    differs = s is not None and (s.get("name") not in names
                                 or any(s.get(f) != fix.get(f, fresh.get(f)) for f in ("tab", "group", "order")))
    if s is None:
        doc["settings"].append(fresh)
        by_key[k] = fresh
        derived[k].update({v: "derived" for v in fill})
        changed.append((k, fresh["name"], "new", None, fresh["values"]))
    elif differs:
        kept = {v: lab for v, lab in s.get("values") or [] if v not in {x for x, _ in fresh["values"]}}
        print(f"  new like  {k}: laid out like {like} now (it was laid out otherwise)")
        for f in LIKE_FIELDS:
            if f in fresh:
                s[f] = fresh[f]
        s["values"] = sorted([[v, lab] for v, lab in fresh["values"]] + [[v, lab] for v, lab in kept.items()])
        derived[k].update({v: "derived" for v in fill})
        changed.append((k, s["name"], "laid out", None, like))
    else:
        for _e, r, _row in rows:
            like_more(s, r, whole)
    return order


def like_more(s: dict, r: dict, whole: bool) -> None:
    """A value a later row proves of a record laid out like its sibling, named by its rule (the part of the label after
    its colon unless `whole`), where the record does not name it yet."""
    labels = dict((v, lab) for v, lab in s.get("values") or [])
    for lab, v in r["proved"].items():
        labels.setdefault(v, clean(lab if whole else lab.split(":", 1)[-1].strip()))
    s["values"] = sorted([v, lab] for v, lab in labels.items())


def generic_main(target: Path, run: Path, write: bool, force: bool = False, accept_stale: bool = False) -> dict:
    """schema_update for any definition but the ILCE-1M2 firmware 4.00's: the plain pass, from a seed when the camera
    has no definition yet, with the camera's own hand tables and their evidence apart (writer/hand_tables.load_plain
    of target's camera: either file refused in plain words where it does not fit its JSON Schema, the evidence holding
    evidence fields only, every part on an entry the tables hold). Before anything else is read it stops, in plain
    words: on a table only the ILCE-1M2's pass reads, or an entry no table it reads would use (hand_facts.refusals);
    with write, when the tables hold entries the hand evidence completes and that file is not here
    (hand_evidence.missing: a look says the same as a note, and goes on); and on a hand proof the evidence gives
    without its run, day or menu rows (hand_facts.hand_proof_gaps). The camera's proof contexts are put in other words
    (CONTEXT_WORDS) while it runs; a pattern that matches no row is said. Returns the definition, written with
    write."""
    camera = target.stem
    T, E = hand_tables.load_plain(camera)
    why = hand_facts.refusals(T)
    if why:
        sys.exit(hand_facts.refusal_words(camera, why))
    missing = hand_evidence.missing(camera, T.HAND_EVIDENCE, vars(T))
    if write and missing:
        sys.exit(missing)
    gaps = hand_facts.hand_proof_gaps(E)
    if gaps:
        sys.exit(f"schema_update: nothing done. The hand evidence, {paths.shown(hand_evidence.path(camera))}, gives "
                 f"hand proofs of FRAME_PROOFS without what the definition's evidence keeps of each: {'; '.join(gaps)}. "
                 "A hand proof names the run it was made in, its day and its menu row (\"run\", \"date\" and \"menu\" "
                 "beside its \"proved\" or \"sampled\"; docs/DATA_CONTRACTS.md, \"The hand evidence file\"): add them "
                 "there, then run the command again.")
    if missing:                                 # a look goes on, and says what --write would stop on
        print(f"note, before --write: {missing}")
    if E.get("MY_MENU_EMPTY"):                  # evidence for a table only the ILCE-1M2's pass reads
        print("  hand evidence  MY_MENU_EMPTY: read only by the ILCE-1M2's own pass so far, not applied")
    with reworded(T.CONTEXT_WORDS):             # the camera's proof contexts the runs reworded (menu_row)
        return plain(target, run, write, force, accept_stale, T, E)


def plain(target: Path, run: Path, write: bool, force: bool, accept_stale: bool, tables, evidence: dict = None) -> dict:
    """generic_main's pass, once the camera's hand tables (`tables`) and hand evidence (`evidence`) are read and
    checked."""
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
    # a reworded context that matches no row the report or the definition holds rewords nothing: said
    rows = [e["row"] for e in report] + [m for s in doc["settings"] for m in (s.get("proved") or {}).get("menu") or []
                                         if isinstance(m, str)]
    unmatched = [p for p in tables.CONTEXT_WORDS if not any(re.search(p, x) for x in rows)]
    for pattern in unmatched:
        print(f"  context words  {pattern!r}: matches no row of the report or the definition, not applied")
    # a live setting's memory copy seen taken by a registration, and the owner's word for a never-open row in the
    # evidence of what it proved (a hand proof's registration among them), as the ILCE-1M2's pass has them
    mirrors = registration_mirrors(run)
    allowed = collections.defaultdict(set)
    for e in report:
        for k, r in e["records"].items():
            allowed[k] |= set(r.get("allowances") or ())
    for k, m in mirrors.items():
        if m.get("allowance"):
            allowed[k].add(m["allowance"])
    unresolved = []                 # the conflicts a hand table keeps against the camera's reading (KEEP_LABELS)
    taken_out = set()               # evidence the pass took out on purpose, said (a reason's day, a mark's evidence)
    changed = generic(doc, report, run, date, tables, unresolved, allowed, evidence, taken_out)
    print(f"in sets: {with_in_sets_proved(doc, mirrors)} settings whose memory copy a registration took; allowances: "
          f"{with_allowances(doc, allowed)} settings took the owner's word into their evidence")
    # the rows a definition kept, named so too; the patterns said applied are those that match a row
    with_menu_rows(doc, axis_value_rows(option_tree.read_proofs(run)), len(tables.CONTEXT_WORDS) - len(unmatched))
    with_option_trees(doc, run)
    with_scales(doc, run)
    # the values offered under one video system only, where rows were walked under each, else the hand table's
    if with_video_systems(doc, report, report_proofs(run)[0] if (run / "proofs.jsonl").exists() else [],
                          tables.VIDEO_SYSTEM_VALUES, run.parent, run) is None and tables.VIDEO_SYSTEM_VALUES:
        print("  video system  VIDEO_SYSTEM_VALUES: the run has no proofs to set it beside, not applied")
    check_video_systems(doc, run.parent)
    # the copies the camera keeps of a live value (COPIES), where its downloads bear the rule out; a definition whose
    # table is emptied loses them
    if tables.COPIES or any({"copies", "copy_of", "copy_for"} & set(s) for s in doc["settings"]):
        with_copies(doc, tables.COPIES, run.parent, modes=tables.COPY_MODES, unknown=tables.COPY_MODES_UNKNOWN)
    without_observed(doc)
    doc = from_data(doc)
    print(f"{sum(1 for s in doc['settings'] if s.get('proved'))} of {len(doc['settings'])} settings proved; "
          f"{len(changed)} labels changed or added")
    for k, name, v, old, new in changed:
        print(f"  {k} {name[:44]:44s} {v!s:>4}: {old!r} -> {new!r}")
    # the plain pass gives every proved value the camera's label, so no conflict stands but one a hand table keeps; the
    # rest is the gate's
    gate(questions(report, unresolved, frozenset(s["key"] for s in doc["settings"])), camera, force, write)
    if write:
        write_definition(target, doc, accept_stale, taken_out=taken_out)   # every refusal first, the reset file, this
        print(f"wrote {target}")
        say_stale(target)
    return doc
