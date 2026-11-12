"""The memory sets' twins: the set records that share an id with a live record, sorted from a camera's definition and
one of its settings files, and the plain list rows a registration spot check can change (2026-11-09).

    .venv/bin/python kit/tools/set_twins.py --evidenced RUN|'' [--file DAT] [--count 40] [--scan RUN]
    ... then kit/provers/memreg_run.py --list, which reads what this wrote

Each memory set (the file's sections 1-12 on the a1 II; section 1 is Memory 1, the dial's position 1) holds the same
record ids, 1,057 of them. A set record whose id is also a live record's (section 0) is that id's twin. The definition
flags a live setting "in_sets" when its id is in set 1 (kit/schema_update.py and kit/writer/generic.py: cs.get(1, rid)
is not None), and the editor's Memory views show those by the live name; a "set:" setting names a set record on its
own. The records fall into:
  flagged      twins whose live record a definition setting names (every such setting is flagged in_sets);
  unflagged    twins whose live record no setting names: the Memory views skip them, as the live views do;
  set_defined  the records of the set: settings, twins or not;
  set_only     set records with no live record and no set: setting.
For each twin: the live setting (its name, menu row, the row's kind and option count in the camera's menu tree,
the mapper's own in private/evidence/<camera>/: without it the survey stops in plain words), or,
for a record no setting names, its value shape (the mapper's record shapes, private whole in
private/evidence/<camera>/, camkit.datafiles) and the rows whose proof
lines moved the live record (every proofs.jsonl in the camera's runs/); and whether the set copy holds the live
record's bytes in the file (true or false, never a value).

The spot check (kit/provers/memreg_run.py) wants twins whose live setting a plain list row sets: --count of them are
picked, the unflagged first, spread over the tabs and their groups. A candidate is a list row of 2-8 options, at the
top level or one submenu down, the one setting to its row, whose values are the row's options one to one (so the
option chosen is known by its code) and written in plain letters (PLAIN: set_row finds an option by the list bar's
OCR), walked in the Stills menu tree, its top row in the page scan (--scan, which the prover navigates by) and not
greyed there, not never-open (camkit.safety.path_refused), not Movie-only; and none of
what EXCLUDE and EXCLUDE_GROUPS name (light and the flash, sound, motion, the shooting itself or its mode, the cards and
files, what the screen shows), nor a twin a registration already moved (--evidenced: the run whose drive.jsonl
registered the slot, its records evidenced already). Each pick's option is the first of its row's options, in the
menu's order, that the file's live record does not hold; the prover chooses again from its own start file. The console
and set_twins.json name the option each pick would choose, which on a row of few options can tell what its record
holds; both are local (runs/ is never versioned), and no other value a record holds is printed (docs/decisions/0016).

Written to runs/<camera>/kit2_memtwins/set_twins.json (runs/ is local, never versioned): the counts, the groups, every
candidate with the reason an excluded one was left out, and the picks.
"""
import argparse
import collections
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, datafiles, definitions, jsonl, match, paths, provenance, safety  # noqa: E402
from runner import LATEST_SCAN, read_json, scan_dir, scan_type, write_json  # noqa: E402

RUN = "kit2_memtwins"
OUT = "set_twins.json"
COUNT = 40
MEMORY_ROW = "Camera Set. Memory"
OPTIONS = (2, 8)                        # a plain list row's options, fewest and most
# an option label set_row can find by the list bar's OCR: letters, digits, spaces and plain punctuation ("Rating (★)",
# "Divider Frame (|→)" are not: the stars and the arrow come back as other marks, or none)
PLAIN = r"[A-Za-z0-9 .,:;+\-/()%'&]+"
# Never changed by the spot check, beyond the never-open list, each a regular expression searched in the row's path
# (its labels joined with " > "): light and the flash, sound, motion (decision 2); the shooting itself or its mode,
# which the registration records; the cards and files (decision 4); and what the screen shows, which the kit's eyes
# judge before every download (the shooting screen) and on the memory slot screen
EXCLUDE = (
    ("light or the flash", r"flash|\blight|illuminat|red\s*eye|\blamp\b|\bled\b"),
    ("sound", r"silent|sound|audio|beep|volume|speaker|\bmic\b"),
    ("motion: the lens or the shutter", r"zoom|drive|shutter\s*type|steady\s*shot|pre-?\s?af\b|eye-?\s?start"),
    ("the shooting itself or its mode", r"interval\s*shooting|nr\s*shooting|shoot\s*mode|mode\s*dial|still/mov|"
                                        r"focus\s*mode|exposure\s*ctrl"),
    ("the cards and files", r"media|card|file|folder|format|copyright|serial"),
    ("what the screen shows", r"grid|monitor|finder|hdmi|bright|live\s*view|display\s*quality|zebra"),
    ("a row the submenu lists only in some states (kit2_memtwins: not found in the run's frames)",
     r"(hi\+|lo|mid)\s*\(e-shutter\)|pre-captr\.\s*start\s*trigger"),
)
EXCLUDE_GROUPS = {"Flash": "light or the flash", "Zoom": "motion: the lens or the shutter",
                  "Media": "the cards and files", "Shooting Display": "what the screen shows"}


def rid_of(key: str) -> int:
    """The record id of a definition key ("global:0x0290", "set:0x0180@288", "global:0x0bf1[0]")."""
    return int(re.match(r"[a-z]+\d*:0x([0-9a-f]+)", key).group(1), 16)


def hexid(rid: int) -> str:
    return f"0x{rid:04x}"


# ---------------------------------------------------------------- the groups

def groups(doc: dict, cs) -> dict:
    """{"flagged", "unflagged", "set_defined", "set_only", "twins"}: sorted record ids of set 1 (section 1), as the
    module's docstring sorts them, from the definition's settings and the file's sections. Also "flag_missing": live
    settings flagged in_sets whose id set 1 of this file does not hold (none on a file of the definition's layout)."""
    live, sets = set(cs.sections[0]), set(cs.sections[1])
    settings = doc.get("settings") or []
    named = {s["id"] for s in settings if s.get("area") == "global"}
    flag = {s["id"] for s in settings if s.get("area") == "global" and s.get("in_sets")}
    own = {s["id"] for s in settings if s.get("area") == "set"}
    twins = live & sets
    return {"twins": sorted(twins), "flagged": sorted(twins & named), "unflagged": sorted(twins - named - own),
            "set_defined": sorted(own & sets), "set_only": sorted(sets - live - own),
            "flag_missing": sorted(flag - sets)}


def stills_rows(tree: dict) -> dict:
    """{path tuple: [(tab, group, row)]} of the Stills menu (the menu tree's "tabs"), submenu rows by their path."""
    out = collections.defaultdict(list)

    def walk(rows, prefix, tab, group):
        for r in rows:
            path = prefix + (r["label"],)
            out[path].append((tab, group, r))
            if r.get("children"):
                walk(r["children"], path, tab, group)
    for t in tree.get("tabs") or []:
        for page in t.get("pages") or []:
            walk(page.get("rows") or [], (), t["tab"], page.get("group") or "")
    return dict(out)


def scan_rows(model: list) -> dict:
    """{label key: greyed} of the page scan's rows (its model.json): only whether a row was greyed, never its value."""
    out = {}
    for page in model:
        for r in page.get("rows") or []:
            k = match.key(r.get("label") or "")
            if k:
                out[k] = out.get(k, False) or bool(r.get("greyed"))
    return out


def moved_by(root: Path, keys: set) -> dict:
    """{key: [[row, count], ...]} for the live keys ("global:0x0e18") that proof lines in the camera's runs moved: the
    rows whose lines named them among their changes or side effects, the most first."""
    seen = collections.defaultdict(collections.Counter)
    for f in sorted(Path(root).glob("*/proofs.jsonl")):
        for r in jsonl.read(f):
            hit = {c.get("key") for c in r.get("changes") or [] if isinstance(c, dict)}
            hit |= {k for k in r.get("side_effects") or [] if isinstance(k, str)}
            row = " > ".join(str(x) for x in r.get("path") or [])
            for k in hit & keys:
                seen[k][row] += 1
    return {k: [[row, n] for row, n in c.most_common(3)] for k, c in seen.items()}


def registered_ids(root: Path, run: str) -> set:
    """The set record ids a registration of `run` moved (its drive.jsonl lines on the Camera Set. Memory row that
    completed): the twins whose copy is evidenced already."""
    f = Path(root) / run / "drive.jsonl"
    out = set()
    if not f.exists():
        return out
    for r in jsonl.read(f):
        if r.get("path") == [MEMORY_ROW] and r.get("completed"):
            out |= {rid_of(c["key"]) for c in r.get("changes") or [] if re.match(r"set\d+:", c.get("key", ""))}
    return out


# ---------------------------------------------------------------- the candidates and the picks

def excluded_by(path: list, group: str) -> str | None:
    """Why the spot check never changes this row (EXCLUDE, EXCLUDE_GROUPS, the never-open list), or None."""
    why = safety.path_refused(list(path))
    if why:
        return f"never-open: {why}"
    if group in EXCLUDE_GROUPS:
        return f"{EXCLUDE_GROUPS[group]} (the {group} group)"
    text = " > ".join(path).lower()
    for why, rx in EXCLUDE:
        if re.search(rx, text):
            return why
    return None


def candidates(doc: dict, cs, rows: dict, scanned: dict, twin_of: dict, evidenced: set = frozenset()) -> list:
    """Every twin's live setting with a menu row, as a candidate: {"record", "key", "setting", "path", "tab", "group",
    "kind", "options", "codes", "twin", "excluded"} ("excluded": why it is left out, or None). twin_of: {record id:
    "flagged" | "unflagged"}."""
    settings = [s for s in doc.get("settings") or [] if s.get("area") == "global" and s.get("row")]
    per_row = collections.Counter(tuple(s["row"]) for s in settings)
    out = []
    for s in settings:
        twin = twin_of.get(s["id"])
        if twin is None:
            continue
        path = tuple(s["row"])
        hits = rows.get(path) or []
        tab, group, row = hits[0] if len(hits) == 1 else ("", "", {})
        opts = list(row.get("options") or [])
        by_label = {match.key(lab): v for v, lab in s.get("values") or []}
        c = {"record": hexid(s["id"]), "key": s["key"], "setting": s["name"], "path": list(path), "tab": tab,
             "group": group, "kind": row.get("kind"), "options": opts,
             "codes": [by_label.get(match.key(o)) for o in opts], "twin": twin, "excluded": None}
        rec = cs.get(0, s["id"])
        why = None
        if len(path) > 2:
            why = "deeper than one submenu"
        elif per_row[path] != 1:
            why = "the row writes more than one setting"
        elif not re.fullmatch(r"global:0x[0-9a-f]+", s["key"]) or rec is None or rec.count != 1:
            why = "a slot or part of a record, not a whole one"
        elif not hits:
            why = "not in the Stills menu tree"
        elif len(hits) > 1:
            why = "in the Stills menu tree twice"
        elif row.get("kind") != "list" or row.get("state") != "walked":
            why = f"not a walked list ({row.get('kind')}, {row.get('state')})"
        elif not OPTIONS[0] <= len(opts) <= OPTIONS[1]:
            why = f"{len(opts)} options"
        elif len(by_label) != len(s.get("values") or []) or len(opts) != len(by_label) or None in c["codes"]:
            why = "its values are not the row's options one to one"
        elif not all(re.fullmatch(PLAIN, o) for o in opts):
            why = "an option drawn with symbols the list's OCR may not read (set_row finds the option by its text)"
        elif s.get("modes") and "still" not in s["modes"]:
            why = f"not offered in Stills ({s['modes']})"
        elif match.key(path[0]) not in scanned:
            why = "its top row is not in the page scan"
        elif scanned[match.key(path[0])]:
            why = "greyed in the page scan"
        elif s["id"] in evidenced:
            why = "a registration moved its copy already"
        else:
            why = excluded_by(path, group)
        c["excluded"] = why
        out.append(c)
    return out


def option_for(c: dict, cs) -> tuple:
    """(label, code) of the first option of the row, in the menu's order, the file's live record does not hold."""
    rec = cs.get(0, int(c["record"], 16))
    held = rec.value() if rec is not None else None
    for lab, code in zip(c["options"], c["codes"], strict=True):
        if code != held:
            return lab, code
    return None, None


def pick(pool: list, count: int) -> list:
    """`count` candidates, the unflagged twins first, then spread: round robin over the tabs (in the menu's order),
    within a tab over its groups, within a group in the menu's order."""
    out = []
    for twin in ("unflagged", "flagged"):
        tabs = collections.OrderedDict()
        for c in pool:
            if c["twin"] == twin:
                tabs.setdefault(c["tab"], collections.OrderedDict()).setdefault(c["group"], []).append(c)
        queues = {t: collections.deque(collections.deque(g) for g in gs.values()) for t, gs in tabs.items()}
        while len(out) < count and any(queues.values()):
            for t in list(queues):
                q = queues[t]
                if not q or len(out) >= count:
                    continue
                g = q.popleft()
                out.append(g.popleft())
                if g:
                    q.append(g)
    return out


# ---------------------------------------------------------------- the file the prover reads

def survey(doc: dict, cs, tree: dict, model: list, root: Path, count: int = COUNT, evidenced_run: str = "",
           shapes: dict = None) -> dict:
    """The whole survey, as set_twins.json holds it."""
    g = groups(doc, cs)
    shapes = shapes or {}
    by_id = collections.defaultdict(list)
    for s in doc.get("settings") or []:
        by_id[(s.get("area"), s["id"])].append(s)
    rows = stills_rows(tree)
    same = {rid: cs.sections[1][rid].raw == cs.sections[0][rid].raw for rid in g["twins"]}
    moved = moved_by(root, {f"global:{hexid(r)}" for r in g["unflagged"]})

    def live_setting(s):
        hits = rows.get(tuple(s.get("row") or ())) or []
        row = hits[0][2] if len(hits) == 1 else {}
        return {"key": s["key"], "name": s["name"], "row": s.get("row"), "kind": row.get("kind"),
                "options": len(row.get("options") or []) or None}
    twin_of = {**{r: "flagged" for r in g["flagged"]}, **{r: "unflagged" for r in g["unflagged"]}}
    evidenced = registered_ids(root, evidenced_run) if evidenced_run else set()
    pool = candidates(doc, cs, rows, scan_rows(model), twin_of, evidenced)
    eligible = [c for c in pool if c["excluded"] is None]
    picks = pick(eligible, count)
    chosen = {id(c) for c in picks}
    for c in eligible:
        c["option"], c["option_code"] = option_for(c, cs)
        c["picked"] = id(c) in chosen
    return {
        "made": time.strftime("%Y-%m-%d %H:%M"), "camera": definitions.key(doc), "file": None,
        "records": {"live": len(cs.sections[0]), "per_set": len(cs.sections[1]), "sets": len(cs.sections) - 1},
        "counts": {"twins": len(g["twins"]), "flagged": len(g["flagged"]), "unflagged": len(g["unflagged"]),
                   "set_defined": len(g["set_defined"]),
                   "set_defined_twins": len(set(g["set_defined"]) & set(g["twins"])),
                   "set_only": len(g["set_only"]), "flag_missing": len(g["flag_missing"]),
                   "unflagged_moved_in_proofs": len(moved), "candidates": len(eligible),
                   "candidates_unflagged": sum(c["twin"] == "unflagged" for c in eligible), "picked": len(picks)},
        "flagged": [{"record": hexid(r), "settings": [live_setting(s) for s in by_id[("global", r)]],
                     "set_equals_live": same[r]} for r in g["flagged"]],
        "unflagged": [{"record": hexid(r), "live_setting": None, "shape": shapes.get(f"global:{hexid(r)}"),
                       "moved_by": moved.get(f"global:{hexid(r)}", []), "set_equals_live": same[r]}
                      for r in g["unflagged"]],
        "set_defined": [{"record": hexid(r), "settings": [s["key"] for s in by_id[("set", r)]],
                         "twin": r in same} for r in g["set_defined"]],
        "set_only": [{"record": hexid(r), "shape": shapes.get(f"set:{hexid(r)}")} for r in g["set_only"]],
        "flag_missing": [hexid(r) for r in g["flag_missing"]],
        "evidenced_by": evidenced_run if evidenced else None,
        "candidates": pool,
        "picked": [c["path"] for c in picks],
    }


def out_path(root: Path) -> Path:
    return Path(root) / RUN / OUT


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--file", default=None, help="a settings file the camera wrote (default: the newest start file "
                                                 "in the camera's downloads manifest)")
    ap.add_argument("--definition", default=None, help="the definition (default: the camera's)")
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_type("Stills"),
                    help="the Stills page scan the prover navigates by (default: the camera's latest page scan made "
                         "in Stills mode, runner.latest_scan)")
    ap.add_argument("--evidenced", required=True, metavar="RUN",
                    help="the run whose drive.jsonl registered the slot already (its twins are left out), a run in "
                         "the camera's runs; --evidenced '' for none")
    ap.add_argument("--count", type=int, default=COUNT, help="how many rows to pick for the spot check")
    ap.add_argument("--out", default=None, help=f"where to write (default: runs/<camera>/{RUN}/{OUT})")
    a = ap.parse_args(argv)
    root = paths.run_root()
    if a.evidenced and not (root / a.evidenced / "drive.jsonl").is_file():
        sys.exit(f"set_twins: --evidenced {a.evidenced!r}: no drive.jsonl in {paths.shown(root / a.evidenced)} (the run "
                 "whose kit/drive.py registrations of the slot it names); --evidenced '' for none")
    defn = Path(a.definition) if a.definition else definitions.active()
    doc = definitions.with_evidence(read_json(defn), defn)
    camera = definitions.key(doc)
    datafiles.stop_if_left(camera, "set_twins.py")          # its menu tree and record shapes, if still in data/
    f = Path(a.file) if a.file else provenance.newest_start(root)
    if f is None or not f.exists():
        sys.exit("set_twins: no settings file: name one with --file")
    cs = camset.read(f)
    try:
        tree = datafiles.load_menu_tree(camera)          # the mapper's own, private whole
    except datafiles.NoMenuTree as e:
        sys.exit(f"set_twins: {e}")
    scan = scan_dir(a.scan)
    model = read_json(scan / "model.json")
    shapes_file = datafiles.record_shapes_file(camera)          # private whole, beside the definition's evidence
    shapes = read_json(shapes_file).get("types", {}) if shapes_file.exists() else {}
    got = survey(doc, cs, tree, model, root, a.count, a.evidenced, shapes)
    got["file"] = paths.shown(f)
    got["scan"] = scan.name
    n = got["counts"]
    print(f"{camera}, file {f.name}: {n['twins']} of the {got['records']['per_set']} records of each memory set share "
          f"an id with a live record ({got['records']['live']} live records)")
    print(f"  flagged in_sets (a live setting names the record): {n['flagged']}")
    shape_counts = collections.Counter(u["shape"] or "no shape on file" for u in got["unflagged"])
    print(f"  unflagged: {n['unflagged']}; a live setting names none of them, so there is no live name for the Memory "
          f"views to show ({', '.join(f'{k} {v}' for k, v in shape_counts.most_common())})")
    if n["unflagged_moved_in_proofs"]:
        rows = collections.Counter(m[0][0] for u in got["unflagged"] if (m := u["moved_by"]))
        print(f"    {n['unflagged_moved_in_proofs']} of them moved in proof lines, by: "
              + "; ".join(f"{r} ({k})" for r, k in rows.most_common()))
    print(f"  set: settings: {n['set_defined']} records ({n['set_defined_twins']} of them twins)")
    print(f"  set records with no live record and no set: setting: {n['set_only']}")
    if n["flag_missing"]:
        print(f"  warning: {n['flag_missing']} settings flagged in_sets have no record in this file's set 1")
    print(f"spot check: {n['candidates']} plain list rows qualify ({n['candidates_unflagged']} of them unflagged "
          f"twins); {n['picked']} picked:")
    by_path = {tuple(c["path"]): c for c in got["candidates"]}
    for p in got["picked"]:
        c = by_path[tuple(p)]
        print(f"  {' > '.join(p)} [{c['tab']} / {c['group']}, {c['twin']}]: set {c['option']!r}")
    out = Path(a.out) if a.out else out_path(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, got, indent=1)
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
