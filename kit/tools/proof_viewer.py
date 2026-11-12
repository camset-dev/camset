"""A local page from a definition to the camera's own screens, laid out like the editor: the menu's tabs | the
tab's groups | every row of the group with its value | the chosen row, with the frames that proved each value
hidden until asked for.

    .venv/bin/python kit/tools/proof_viewer.py [--out PAGE.html] [--values FILE.DAT] [--definition KEY] [--open]
    .venv/bin/python kit/tools/proof_viewer.py --pack [--png] [--open]     # the page and its frames in its _viewer/

--open opens the page in the default browser; the last line printed is always the page's path.

The page is one definition's (editor/definitions/<model>_fw<fw>.json, docs/decisions/0019): --definition names it,
else it is the definition of the camera the kit works on (camkit.paths: --camera, CAMSET_CAMERA or
private/config.json), else, with no camera named or none of its own yet, the ILCE-1M2 firmware 4.00's (the
reference). It is built in that camera's folder, runs/<model>_fw<fw>/_viewer/index.html, and its title names the
camera. It reads only the runs of the camera the kit works on, and only when that camera is the definition's: another
camera's frames never hang on this definition's records.

No page without the camera's own runs (2026-11-06, the owner: "Proof view shouldn't be available if the kit has never
been run on a camera. The kit runs will be owned by the end users and they'll only submit the schema"): with no camera
named, another one, or no kit2_* run in the camera's folder, nothing is written and it says why and what would make
the page available, on stderr, with exit status 3 (NO_RUNS; kit/setup.py and build_docs.py report it as not built).
The page is for whoever ran the kit on their camera, never part of a submission. The kit's runs from before
per-camera folders (runs/kit2_*, runs/_viewer at the top of runs/) stop it with the command that moves them. The file layout view reads a download through the definition's container block
(its camera section's "file"; docs/decisions/0020), which the page carries.

Rows are the camera's own (the menu tree, the mapper's own in private/evidence/<model>_fw<firmware>/, kept private
whole, camkit.datafiles: every row pass 1 walked, greyed and action rows too, Playback's from the page scan; with no
tree the page has no rows of the camera's), each record hung on the row its proof went through (camkit.placement,
which kit/schema_update.py places a definition's settings with, so the editor's rows hang where the page's do). The
other shooting modes' menus (the tree's "modes": Movie, S&Q) are drawn as the editor draws a setting's row_mode: a
group's rows only that mode has after its Stills rows, under "In Movie mode", in the mode's order, with the records
placement hangs there and their walk's frames from that mode's crawls; a group only a mode has where its menu has it
(mode_rows). Values
are a camera download's (by default the newest session start file in the camera's runs), as the editor shows a
file's.

Evidence comes from three logs (2026-11-03, the owner: "visual verification from the schema to actual
pictures used"):
  <run>/proofs.jsonl   prove_run: the screen after OK, then the option lit before OK (the order a person reads
                       them: before OK the round dot still marks the value before); values from the
                       run's report.json (by row and label), else from the change itself
  <run>/drive.jsonl    drive.py: every screen on the way, for each record the drive changed
  <run>/hand.jsonl     hdmi_watch.py --each: the screens the owner went through by hand
(each <run> a kit2_* folder in runs/<model>_fw<fw>/). The page names frames by path relative to itself, so it stays
in the camera's folder beside them; nothing is copied, and a missing frame is left out; its _viewer/ is made as
needed.

Help text (2026-11-06, the owner: "when an item is selected or hovered, can we get the help text"): each setting's
and each option's, on hover and in the chosen row (an option's under it once chosen), and in the file layout's
inspector for the setting chosen or at the cursor. Text by text (a setting's help, each option's), it is the camera's
In-Camera Guide text where the private help file has it (private/help/), else the project's own words
(data/<model>_fw<fw>/help_*.json, merged into the definition), and its hover says whose. A row no setting belongs to
(an action, a submenu), or whose settings have none of the camera's help, shows its own guide, from the help runs'
logs, matched by its path and the mode as kit/schema_update.py's attach_help matches a setting's row. Where the
camera's runs are here, each text of the camera's links the guide frames it was read from (kit2_help/:
kit/help_run.py, prove_run --help-text, kit/tools/help_extras.py), the setting's own row's first, and a text whose two
readings differed (kit/help_reads.py) carries both and which was kept; the project's own words never get either. The
top bar says once where the help text comes from.

My Menu and Main, from the definition's camera section: the My Menu tab (camera.my_menu) shows the file's pages,
each item by the camera's name for its code and linked to the setting that carries the code (menu_code), and every
item name by code, with the frame of the camera's page that read it back where the slot settings' proof run holds
one (<run>/mymenu_readback.json), and how many names have one. A Main entry at the top of the tabs
(camera.main_tiles) shows each mode's tiles, the value each shows for the file as the editor works it out, the
records it reads (links to their rows), and a frame of the camera's own Main page from the page scans
(kit2_page_scan*/scan.jsonl, the mode by the run's name). A definition without either part shows no such entry.

--pack copies every frame the page links into its _viewer/frames/<run>/<its path in the run> and links the
copies instead: JPEG at quality 85, about a third of the PNG's size (--png copies the files as they are). The
folder then holds the page and all its pictures: zip it or copy it to another computer, where it opens in a
browser with no kit installed. A second pack redoes only the frames whose source is newer than the copy, and
removes the copies no page link names any more (under its _viewer/frames/ only). A build without --pack
(build_docs.py's too) links the frames in the runs again and leaves the copies be: pack again before copying the
folder. Packed or not, the folder shows the owner's own screens, so like the rest of runs/ it stays out of
every repository.
"""
import argparse
import base64
import collections
import datetime
import functools
import html
import json
import os
import re
import shutil
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, datafiles, definitions, help_files, jsonl, paths, placement  # noqa: E402
from camkit.placement import norm  # noqa: E402

RUN_ROOT = None          # the camera's runs the page reads (runs/<model>_fw<fw>/), or None: set by main(), place()
SCHEMA = None            # the definition the page is built from, when given (the tests); else pick_definition()
FRAMES = "frames"          # --pack: the frames' copies, in this folder beside the page
NO_RUNS = 3              # the exit status of a page refused for want of the camera's runs (kit/setup.py, build_docs.py)


class Keys:
    """Schema keys, to turn a change's key (and an array index or byte offset) into the schema's own."""

    def __init__(self, settings):
        self.all = {s["key"] for s in settings}
        self.at = collections.defaultdict(list)          # base key -> [(offset, size, key)] for "@" keys
        for s in settings:
            if "@" in s["key"]:
                base, off = s["key"].split("@")
                self.at[base].append((int(off), s.get("size") or 1, s["key"]))

    def of(self, key: str, before, after) -> list:
        """[(schema key, value)] a change touched: whole records, array elements ("[i]") or blobs' fields."""
        key = re.sub(r"^set\d+:", "set:", key)
        if not isinstance(after, list):
            return [(key, after)] if key in self.all else []
        before = before if isinstance(before, list) and len(before) == len(after) else [None] * len(after)
        out = []
        for i, (b, a) in enumerate(zip(before, after, strict=True)):          # before is after's length (above)
            if b == a:
                continue
            if f"{key}[{i}]" in self.all:
                out.append((f"{key}[{i}]", a))
            for off, size, k in self.at.get(key, ()):
                if off <= i < off + size and (k, None) not in out:
                    out.append((k, None))                 # a blob's field: its value is its bytes together
        if not out and key in self.all:
            out.append((key, None))
        return list(dict.fromkeys(out))


@functools.cache
def in_viewer(here: Path, root: Path) -> bool:
    """Whether the page goes in the camera's own _viewer/, compared as the folders are on disk (runs/ may be a link to
    another disk, and the page's folder is resolved)."""
    return Path(here).resolve() == (root / "_viewer").resolve()


def frame(run: Path, name, here: Path):
    """A frame's link: relative to the page in the camera's _viewer/, else its absolute path; with forward slashes on
    every OS, as a page's links are. None when the file is not there."""
    if not name:
        return None
    for sub in ("shots", "upright", "."):
        p = run / sub / name
        if p.exists():
            return (Path("..") / p.relative_to(RUN_ROOT)).as_posix() if in_viewer(here, RUN_ROOT) else p.as_posix()
    return None


def row_name(r) -> str:
    name = " > ".join(r["path"])
    if r.get("kind") == "fields" and isinstance(r.get("index"), list):
        name += f" [field {r['index'][0]}]"
    if r.get("context"):
        name += f" [{r['context']}]"
    return name


DAMAGED = {}          # a run log read with damaged lines left out -> how many (read_log; main() reports them)


def read_log(path: Path) -> list:
    """A run's log (camkit.jsonl). A line cut short at its end, a run stopped mid-write, is left out as camkit.jsonl
    leaves it. A damaged line elsewhere (a run resumed after a stop appends past a torn line; disk damage) is left out
    too, so one such line is one proof's frames missing rather than the whole page refused; but it is counted and said
    on stderr, with the first one's line, and the page's top bar says how many, so a damaged log is noticed."""
    try:
        return jsonl.read(path)
    except ValueError as e:
        whole = jsonl.read(path, bad="skip")
        with open(path, encoding="utf-8", errors="replace") as f:          # lines as camkit.jsonl splits them
            lines = [line for line in f if line.strip()]
        torn = not _parses(lines[-1])          # the stop the log ends with, left out in any case
        DAMAGED[paths.shown(path)] = len(lines) - len(whole) - torn
        print(f"{e}: {len(lines) - len(whole) - torn} damaged line(s) of it left out of the page"
              + (", and its torn last line" if torn else ""), file=sys.stderr)
        return whole


def _parses(line: str) -> bool:
    try:
        return isinstance(json.loads(line), dict)
    except ValueError:
        return False


def from_proofs(run: Path, keys: Keys, here: Path, ev):
    report = {}
    if (run / "report.json").exists():
        report = {r["row"]: r["records"] for r in json.loads((run / "report.json").read_text(encoding="utf-8"))}
    for r in read_log(run / "proofs.jsonl"):
        if not r.get("path"):
            continue
        row = row_name(r)
        # in the order a person reads them (2026-11-06, the owner: a picture "with JPEG selected"): after OK first,
        # the value set, then the option lit before OK, where the round dot still marks the value before
        shots = [[p, cap] for p, cap in ((frame(run, r.get("row_frame"), here), "after OK"),
                                         (frame(run, r.get("chosen_frame"), here), "option lit")) if p]
        # a table cell's list as it showed (options_seen, 2026-11-08: it can hold options the walk never saw), which
        # the page writes under the proof's pictures ("seen"); the captions stay the two steps' own words
        seen = [str(o) for o in r.get("options_seen") or []] if isinstance(r.get("options_seen"), list) else []
        hits = {}
        for k, rec in (report.get(row) or {}).items():
            v = (rec.get("proved") or {}).get(r.get("label"))
            if isinstance(v, int):
                for sk, _ in keys.of(k, None, v):
                    hits[sk] = v
        for c in r.get("changes") or []:
            for sk, v in keys.of(c["key"], c.get("before"), c.get("after")):
                hits.setdefault(sk, v)
        for sk, v in hits.items():
            ev[sk].append({"v": v, "how": "proof", "run": run.name, "row": row, "label": r.get("label"),
                           "frames": shots, **({"seen": seen} if seen else {})})


def from_steps(run: Path, log: str, keys: Keys, here: Path, ev):
    for r in read_log(run / log):
        if not r.get("changes"):
            continue
        steps = r.get("screens") if log == "drive.jsonl" else r.get("frames")
        if not isinstance(steps, list):
            continue
        shots = [[p, s.get("after") or s.get("kind") or ""] for s in steps
                 for p in [frame(run, s.get("frame"), here)] if p]
        row = " > ".join(r.get("path") or []) if log == "drive.jsonl" else "by hand"
        for c in r["changes"]:
            for sk, v in keys.of(c["key"], c.get("before"), c.get("after")):
                ev[sk].append({"v": v, "how": "drive" if log == "drive.jsonl" else "hand", "run": run.name,
                               "row": row, "label": r.get("note") or "", "frames": shots,
                               "before": c.get("before") if not isinstance(c.get("before"), list) else None})


def the_runs() -> list:
    """The kit's runs of the camera the page reads (runs/<model>_fw<fw>/kit2_*): none in a clone that has not mapped
    it, or when the page reads no camera's runs."""
    if RUN_ROOT is None or not RUN_ROOT.is_dir():
        return []
    return sorted(p for p in RUN_ROOT.iterdir() if p.is_dir() and p.name.startswith("kit2_"))


def definition_key(doc) -> str:
    """The camera the definition is (its first layout's model and firmware): <model>_fw<fw>, which also names its
    data/ folder."""
    return definitions.key(doc)


def pick_definition(given: str = None) -> Path:
    """The definition the page is built from: the one named, else the active camera's when it has one, else the
    reference (the ILCE-1M2 firmware 4.00's)."""
    if given:
        p = definitions.path(given)
        if not p.exists():
            raise SystemExit(f"no definition of {given} ({p.relative_to(ROOT).as_posix()})")
        return p
    got = paths.camera()
    if got and definitions.path(got[0]).exists():
        return definitions.path(got[0])
    return definitions.path(definitions.REFERENCE)


def place(doc) -> tuple:
    """(the folder the page goes in, the camera's runs it reads or None, why there is no page when it reads none):
    the definition's camera folder, runs/<model>_fw<fw>/; its runs only when the kit works on that camera
    (camkit.paths) and has run on it here (the_runs()), else the page is refused (main())."""
    paths.check_leftovers()
    mine = definition_key(doc)
    folder = paths.runs_top() / mine
    got = paths.camera()
    how = ("The page shows the camera's own screens from the kit's runs, so it is only for whoever ran the kit on "
           "their camera; a submission carries the camera's definition, never its runs.")
    if got is None:
        return folder, None, (f"No proof viewer for {mine}: no camera's runs are on this computer (no camera is "
                              f"named). {how} To have it, map your camera with the kit (docs/QUICKSTART.md), then "
                              "run this again. A camera file's settings open in the editor without it.")
    if got[0] != mine:
        nxt = (f"For {got[0]}'s own page: kit/tools/proof_viewer.py --definition {got[0]}."
               if definitions.path(got[0]).exists() else
               f"{got[0]} has no definition yet: kit/schema_update.py --write writes it from its runs, and its own "
               "page can then be built.")
        return folder, None, (f"No proof viewer for {mine}: the kit works on {got[0]} ({got[1]}), and another "
                              f"camera's runs are never shown on this definition (docs/decisions/0019). {nxt}")
    return folder, folder, (f"No proof viewer for {mine}: {paths.shown(folder)}/ holds no runs of the kit yet. {how} "
                            "Run the kit on the camera (docs/QUICKSTART.md), then run this again.")


def collect(settings, here: Path) -> dict:
    keys, ev = Keys(settings), collections.defaultdict(list)
    for run in the_runs():
        if (run / "proofs.jsonl").exists():
            from_proofs(run, keys, here, ev)
        for log in ("drive.jsonl", "hand.jsonl"):
            if (run / log).exists():
                from_steps(run, log, keys, here, ev)
    return ev


class Place(placement.Place):
    """Where a record sits in the camera's own menu (camkit.placement, which kit/schema_update.py places each
    setting of a definition with), and the families' place, which only the page draws."""

    def families(self, out: list, families: list):
        """Picture Profiles and Creative Looks sit in the camera group most of their records' proofs went through
        (Color/Tone), each profile or look a subsection of the family there."""
        last = None
        for f in families:
            mine = [r for r in out if r["g"].startswith(f["prefix"])]
            placed = collections.Counter((r["t"], r["cg"], r["cgi"]) for r in mine if r["cgi"] is not None)
            if placed:
                last = placed.most_common(1)[0][0]
            if not mine or not last:          # the factory defaults have no proofs: beside the family before them
                continue
            tab, cg, cgi = last
            rank = carousel_order(f["prefix"])
            for r in mine:
                sub = r["g"][f["prefix"].rfind(" ") + 1:] or r["g"]
                r.update({"t": tab, "cg": cg, "cgi": cgi, "fam": f["title"], "sub": sub, "so": rank.get(sub, 999)})


def map_rows(f: Path) -> list | None:
    """The rows of a pass 1 map (kit2_pass1/map_all.json, a crawl's map.json); None when it is not there or not one."""
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))["rows"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def carousel_order(prefix: str) -> dict:
    """A family's subsections in the order the camera's carousel shows them, read in pass 1: Creative Look's
    (FL2 and FL3 follow FL there, not BW as in the file). Picture Profile's carousel was read out of order
    (PP5 last), so profiles keep their numbers' order."""
    if not prefix.startswith("Creative Look") or RUN_ROOT is None:
        return {}
    rows = map_rows(RUN_ROOT / "kit2_pass1" / "map_all.json") or []
    rank = {}
    for row in rows:
        if row.get("path") == ["Creative Look"]:
            for o in row.get("options") or []:
                rank.setdefault(o["label"].split("(")[0].strip(), len(rank))
    return rank


def records(doc, ev) -> list:
    out, place = [], Place(doc)
    for s in doc["settings"]:
        p = s.get("proved") or {}
        out.append({"k": s["key"], "n": s.get("name") or "", "t": s.get("tab") or "Other", "g": s.get("group") or "",
                    "o": s.get("order") if isinstance(s.get("order"), (int, float)) else 9999,
                    "vals": s.get("values") or [], "pv": p.get("values"), "menu": p.get("menu") or [],
                    "run": p.get("run"), "date": p.get("date"), "sampled": bool(p.get("sampled")),
                    "proved": bool(p), "why": s.get("unproved_reason"), "us": s.get("unproved_sets"), "is": bool(s.get("in_sets")),
                    "note": s.get("note") or "",
                    "ev": ev.get(s["key"], []), **place.of(s)})
    place.families(out, [f for f in (doc.get("camera") or {}).get("families", []) if f.get("prefix")])
    for r in out:
        r["cgn"] = place.display.get(r["cg"], r["cg"])
    return out


def mode_word(mode) -> str:
    """A mode's name as the kit's run names carry it ("S&Q" in kit2_page_scan_sq, "Movie" in kit2_crawl_movie)."""
    return re.sub(r"[^a-z0-9]+", "", (mode or "").lower())


def walk_frames(here: Path, mode: str = None) -> dict:
    """Pass 1's frame of each option with the cursor on it, by row path: [[frame, label]] in the list's order. The
    Stills menu's from kit2_pass1/map_all.json; another shooting mode's (`mode`) from the maps of that mode's crawls
    (kit/pass1_map.py's <crawl>/map.json in the kit2_crawl* runs whose name names the mode, as kit/tools/menu_tree.py
    --mode reads them: kit2_crawl_movie), the plainest name first."""
    if RUN_ROOT is None:
        return {}
    rows = []
    if mode is None:
        rows = map_rows(RUN_ROOT / "kit2_pass1" / "map_all.json")
        if rows is None:
            return {}
    else:
        crawls = [p.parent for p in RUN_ROOT.glob("kit2_crawl*/map.json")
                  if mode_word(mode) in [w for w in p.parent.name[len("kit2_crawl"):].split("_") if w]]
        for crawl in sorted(crawls, key=lambda c: (len(c.name), c.name)):
            rows += [dict(r, run=r.get("run") or crawl.name) for r in map_rows(crawl / "map.json") or []]
    out = {}
    for row in rows:
        if mode is not None and tuple(norm(x) for x in row.get("path") or []) in out:          # a later crawl's row: the first's
            continue
        seen, shots = set(), []
        for o in row.get("options") or []:
            at = json.dumps(o.get("index"))          # a list's index, or [field, value] for number fields
            if at in seen:
                continue
            seen.add(at)
            f = frame(RUN_ROOT / (row.get("run") or "kit2_pass1"), o.get("frame"), here)   # the row's crawl (pass1_map)
            if f:
                shots.append([f, o.get("label") or ""])
        out[tuple(norm(x) for x in row["path"])] = shots
    return out


def current_values(path) -> dict:
    """Each global record's value in a camera download: {key: int} (array elements by "[i]")."""
    cs = camset.read(path)
    out = {}
    for rid, rec in cs.sections[0].items():
        v = rec.value()
        if isinstance(v, int):
            out[f"global:0x{rid:04x}"] = v
        elif isinstance(v, list) and rec.size in (1, 2, 4, 8):
            for i, x in enumerate(v):
                out[f"global:0x{rid:04x}[{i}]"] = x
    return out


def newest_start() -> Path | None:
    """The newest session start file in the camera's runs the page reads; None without them."""
    if RUN_ROOT is None or not RUN_ROOT.is_dir():
        return None
    files = sorted(RUN_ROOT.glob("kit2_*/dat/reference_session_start.DAT"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def mode_rows(stills, modes, tabs: list) -> None:
    """Each other shooting mode's rows (`modes`: [(name, placement.Tree)], the menu tree's "modes"), in place, as the
    editor lays out a setting's row_mode: a group's rows only that mode's menu has after the group's Stills rows, in
    the mode's own order, each top row marked with its mode ("mode", the page's "In Movie mode" heading over them), and
    a group only a mode has where that mode's menu has it, its rows marked the same (the group too). A row both menus
    have is the Stills one, and a row S&Q shares with Movie is Movie's, unless records hang on it (placement.reach
    found it only there): placement.merge_tops numbers every top row of a tab, the rows the menus share alike, so a
    tab's groups are ordered by their first row's number. A tab the Stills menu does not have (Movie's My Menu, which
    the page draws from the definition) is left out."""
    number = placement.merge_tops(stills, modes)

    def held(x) -> bool:
        return bool(x["recs"] or x["subs"]) or any(held(k) for k in x["kids"])

    def mark(x, mode):
        x["mode"] = mode
        for k in x["kids"]:
            mark(k, mode)
    for t in tabs:
        tab = t["tab"]
        shown = {number.get((None, tab, i)) for i in range(len(stills.tops.get(tab, [])))}
        first = {}          # id(group) -> the number of its first row
        for g in t["groups"]:
            first[id(g)] = min((number.get((None, tab, stills.where[x["id"]][2][0]), 0) for x in g["rows"]), default=None)
        for mode, m in modes:
            for mg in (m.by_tab.get(tab) or {}).get("groups") or []:
                keep = []
                for x in mg["rows"]:
                    n = number.get((mode, tab, m.where[x["id"]][2][0]))
                    if n not in shown or held(x):
                        keep.append((n, x))
                        shown.add(n)
                if not keep:
                    continue
                g = next((g for g in t["groups"] if g["name"] == mg["name"]), None) or \
                    next((g for g in t["groups"] if norm(g["name"]) == norm(mg["name"])), None)
                if g is None:          # a group only a mode's menu has
                    g = {"name": mg["name"], "num": "", "rows": [], "extra": [], "mode": mode}
                    t["groups"].append(g)
                    first[id(g)] = min(n for n, _ in keep)
                for _, x in keep:
                    mark(x, mode)
                    g["rows"].append(x)
        at = 0
        for g in t["groups"]:          # a group with no row keeps its place after the one before it
            at = first[id(g)] if first[id(g)] is not None else at
            first[id(g)] = at
        t["groups"].sort(key=lambda g: first[id(g)])


def menu(doc, recs, here: Path) -> list:
    """The camera's tabs, groups and rows (the menu tree), every record hung on the row its proof went through
    (placement.grown, as the definition places it: a row in another tab where its own tab has none, the sub-rows its
    paths name under a row the tree knows none under; else by its name, else at the end of its group), Picture
    Profiles and Creative Looks as subsections of their rows; the other shooting modes' rows after a group's Stills
    rows (mode_rows), and the records placement hangs there with them; records no menu lists in groups of their own
    after the camera's."""
    cam = definition_key(doc)
    try:
        tree = datafiles.load_menu_tree(cam)          # the mapper's own, private whole (private/evidence/)
    except datafiles.NoMenuTree:
        datafiles.say_no_menu_tree(datafiles.menu_tree_file(cam), "the viewer lists every record under its tab and "
                                   "group, not on the camera's own menu rows")
        tree = {"tabs": []}
    cam_tree = placement.Tree(doc, tree, walk_frames(here))          # the rows, and where a record hangs on them
    modes = placement.mode_trees(doc, tree, {m.get("mode"): walk_frames(here, m["mode"]) for m in tree.get("modes") or [] if m.get("mode")})
    tabs, by_tab, nodes, find = cam_tree.tabs, cam_tree.by_tab, cam_tree.nodes, cam_tree.find
    leaves = placement.leaf_rows([cam_tree] + [m for _, m in modes])          # before any row is grown from the paths

    other = collections.defaultdict(list)          # tab -> {group name: [keys]} the menu does not list
    fams = collections.defaultdict(dict)           # family row id -> {sub: [keys]}
    for r in recs:
        t = by_tab.get(r["t"])
        if r.get("fam"):
            row = find(r["t"], [norm(" ".join(r["g"].split()[:2]))], r["cg"]) if t else None
            if row:
                fams[row["id"]].setdefault(r["sub"], (r.get("so", 999), []))[1].append(r["k"])
                row["fam"] = r["fam"]
                continue
        menus = [r["menu"]] if isinstance(r["menu"], str) else r["menu"]
        # as the definition places it: in another tab where its own has no row, on the sub-rows its paths name where
        # the tree knows none (headings with no walk frames of their own)
        _, hit = placement.grown(cam_tree, modes, leaves, menus, r["t"], r["cg"], r["n"])
        g = None if hit else cam_tree.hang(r["t"], menus, r["cg"], r["n"])[1]
        if hit:
            hit["recs"].append(r["k"])
        elif g:
            g["extra"].append(r["k"])
        else:
            other[r["t"]].append(r)
    mode_rows(cam_tree, modes, tabs)
    for t in tabs:
        for g in t["groups"]:
            for x, _ in nodes(g["rows"]):
                if x["id"] in fams:
                    x["kids"] = []          # the profiles and looks come from their records
                    x["subs"] = [{"name": s, "keys": keys} for s, (_, keys) in
                                 sorted(fams[x["id"]].items(), key=lambda kv: (kv[1][0], [int(c) if c.isdigit() else c for c in re.split(r"(\d+)", kv[0])]))]
        groups = collections.OrderedDict()
        for r in sorted(other.pop(t["tab"], []), key=lambda r: (r["g"], r["o"])):
            groups.setdefault(r["g"] or "(no group)", []).append(r["k"])
        t["others"] = [{"name": k, "keys": v} for k, v in groups.items()]
    for tab, rs in other.items():          # tabs the camera's tree does not have (My Menu)
        groups = collections.OrderedDict()
        for r in rs:
            groups.setdefault(r["g"] or "(no group)", []).append(r["k"])
        tabs.append({"tab": tab, "groups": [], "others": [{"name": k, "keys": v} for k, v in groups.items()]})
    return tabs


def unmapped(doc, path) -> list:
    """The download's records no schema setting covers, as the editor's Unmapped view lists them: live ones and
    the memory sets' (set 1's values; every set holds the same records), in 256-id blocks, each with its
    shape, its value and what the mapper's record shapes found (constant, boolean, ...: read off the body's downloads,
    kept private whole beside the definition's evidence, camkit.datafiles.record_shapes_file)."""
    if not path:
        return []
    cs = camset.read(path)
    have = {"global": set(), "set": set()}
    for s in doc["settings"]:
        m = re.match(r"(global|set\d*):0x([0-9a-f]+)", s["key"])
        if m:
            have["global" if m.group(1) == "global" else "set"].add(int(m.group(2), 16))
    cam = definition_key(doc)          # found by the layout's model and firmware, as the menu tree is
    try:
        types = json.loads(datafiles.record_shapes_file(cam).read_text(encoding="utf-8")).get("types") or {}
    except (OSError, ValueError, AttributeError):
        types = {}
    out = []
    for sec, area, label in ((0, "global", "Live"), (1, "set", "Memory sets")):
        if sec >= len(cs.sections):
            continue
        for rid, rec in sorted(cs.sections[sec].items()):
            if rid in have[area] or (area == "set" and rid in have["global"]):
                continue
            v = rec.value()
            raw = str(v) if not isinstance(v, list) else " ".join(str(x) for x in v[:16]) + (" …" if len(v) > 16 else "")
            key = f"{area}:0x{rid:04x}"
            kind = types.get(key) or types.get(f"global:0x{rid:04x}") or ""
            block = rid & ~0xFF
            out.append({"key": key, "name": f"0x{rid:04x}", "tab": "Unmapped records", "order": rid,
                        "group": f"{label} 0x{block:04x}–0x{block + 0xFF:04x}", "values": [],
                        "note": f"Not in the schema. Shape {rec.size}×{rec.count}" + (f"; across the downloads: {kind}" if kind else "")
                                + (" (set 1's value; every memory set holds this record)" if area == "set" else "") + ".",
                        "raw": raw})
    return out


# ---------------------------------------------------------------- help text, and the camera's guides it was read from

HELP_RUN = "kit2_help"          # the help runs' logs and the guide frames they kept (kit/help_run.py, kit/help_reads.py)
HELP_LOGS = ("help.jsonl", "option_help.jsonl", "drive_help.jsonl", "field_help.jsonl", "carousel_help.jsonl")
ROW_LOGS = ("help.jsonl", "option_help.jsonl", "drive_help.jsonl")          # the ones that hold rows' own guides
FIRST_CONTEXT = "Stills mode"          # the menu tree's mode (pass 1's Stills Menu Map), looked in first


def guide_reads(here: Path) -> list:
    """Every In-Camera Guide the camera's help runs read (runs/<model>_fw<fw>/kit2_help/*.jsonl), with its text as
    kit/schema_update.py's attach_help takes it into the help file: the words kit/help_reads.py's readers settled on
    (by the guide's first frame), else the OCR's, a greyed row's closing line cut off. Each: {"log", "ctx", "path",
    "index", "label", "text", "how" (help_reads' verdict, "" when no second reader saw it), "ocr" and "vlm" (both
    readings, only where their words differ), "where", "frames": [[link, caption]]}. None without the camera's runs."""
    help_dir = RUN_ROOT / HELP_RUN if RUN_ROOT is not None else None
    if help_dir is None or not help_dir.is_dir():
        return []
    from schema_update import DISABLED_RE          # the help file's own cut (kit/schema_update.py)
    words = lambda t: re.sub(r"[^a-z0-9]", "", (t or "").lower())          # noqa: E731  as help_reads compares them
    reads = {x["frame"]: x for x in read_log(help_dir / "help_reads.jsonl")}
    out = []
    for log in HELP_LOGS:
        for r in read_log(help_dir / log):
            if not r.get("text") or not r.get("frames"):
                continue
            rd = reads.get(r["frames"][0]) or {}
            index = r["index"] if isinstance(r.get("index"), int) else -1
            ctx = r.get("context") or (f"{r['family']} mode" if r.get("family") else FIRST_CONTEXT)
            path = r.get("path") or (["Shoot Mode"] if r.get("family") else [r["label"]])
            tail = [r["label"]] if r.get("label") and (index >= 0 or log in ("field_help.jsonl", "carousel_help.jsonl")) else []
            where = " > ".join(([r["breadcrumb"]] if r.get("breadcrumb") else []) + list(path) + tail)
            g = {"log": log, "ctx": ctx, "path": path, "index": index, "label": r.get("label"),
                 "text": DISABLED_RE.sub("", rd.get("text") or r["text"]), "how": rd.get("how") or "", "where": where,
                 "frames": [[p, f"the camera's guide · {ctx} · {where}"] for p in
                            (frame(help_dir, name, here) for name in r["frames"]) if p]}
            if rd and words(rd.get("ocr")) != words(rd.get("vlm")):
                g.update(ocr=rd.get("ocr") or "", vlm=rd.get("vlm") or "")
            out.append(g)
    return out


def text_guides(text: str, guides: list, by_text: dict = None) -> list:
    """The guides a help text was read from, by index: those whose words are the text; else, for a row's guide with
    its number fields' own after it ("Minimum: …", as attach_help joins them), the row's and each field's. by_text:
    {text: [index]}, made here when not given."""
    if by_text is None:
        by_text = collections.defaultdict(list)
        for i, g in enumerate(guides):
            by_text[g["text"]].append(i)
    if not text:
        return []
    if text in by_text:
        return list(by_text[text])
    fields = [(j, f"{g['label']}: {g['text']}") for j, g in enumerate(guides) if g["log"] == "field_help.jsonl"]
    for row in sorted({g["text"] for g in guides if g["log"] != "field_help.jsonl" and text.startswith(g["text"] + " ")},
                      key=len, reverse=True):
        rest, got = text[len(row):].strip(), []
        while rest:
            hit = next((t for _, t in fields if rest.startswith(t)), None)
            if not hit:
                break
            got += [j for j, t in fields if t == hit]
            rest = rest[len(hit):].strip()
        if not rest:
            return list(by_text[row]) + got
    return []


def on_row(ids: list, s: dict, guides: list, label: str = None, went: dict = None) -> list:
    """Of the guides a setting's text was read from, those on the setting's own menu rows (kit/schema_update.py's
    help_rows, by which attach_help found or kept the text: the rows of its "proved" menu, then those its counted
    proofs went through, went: schema_update.proved_rows), in their mode first, else in another, else all of them (the
    same words on other rows' guides, which their captions name); of those, the row's own guide for the setting's help,
    the option's (label: the value's name) for an option's help, when there is one (a row whose every option shows
    the row's guide has many)."""
    from page_model import key_text
    from schema_update import LOOKALIKES, help_rows
    places = help_rows(s, went or {})
    key = lambda i: tuple(key_text(x).lower() for x in guides[i]["path"])          # noqa: E731
    name = lambda t: key_text((t or "").translate(LOOKALIKES)).lower()          # noqa: E731
    pick = ([i for i in ids if (guides[i]["ctx"], key(i)) in places]
            or [i for i in ids if key(i) in {p[1] for p in places}] or ids)
    own = ([i for i in pick if guides[i]["index"] < 0] if label is None
           else [i for i in pick if guides[i]["label"] and name(guides[i]["label"]) == name(label)])
    return own or pick


def used_guides(data, guides: list) -> list:
    """The guides the page links (a setting's, an option's or a row's help), renumbered in place, each with only what
    the page shows of it: its frames, where and in which mode, and both readings where they differed."""
    lists = ([r["hg"] for r in data["records"].values() if r.get("hg")]
             + [o[2] for r in data["records"].values() for o in r.get("oh") or []]
             + [x["hg"] for x, _ in menu_nodes(data["menu"]) if x.get("hg")])
    lists = list({id(ids): ids for ids in lists}.values())          # a list two texts share is renumbered once
    used = sorted({i for ids in lists for i in ids})
    new = {old: n for n, old in enumerate(used)}
    for ids in lists:
        ids[:] = [new[i] for i in ids]
    return [{k: guides[i][k] for k in ("frames", "where", "ctx", "how", "ocr", "vlm") if k in guides[i]} for i in used]


def row_guides(guides: list) -> dict:
    """(context, the row's path as attach_help keys it) -> [guide index] for each row's own guide (not an option's,
    a field's or a mode's): the keys kit/schema_update.py's attach_help matches a setting's menu row by."""
    from page_model import key_text
    out = collections.defaultdict(list)
    for i, g in enumerate(guides):
        if g["log"] in ROW_LOGS and (g["index"] if isinstance(g["index"], int) else -1) < 0:
            out[(g["ctx"], tuple(key_text(x).lower() for x in g["path"]))].append(i)
    return out


def row_help(path: list, rows: dict, mode: str = None) -> list:
    """A menu row's own guides: in its menu's mode first (the Stills menu's, else `mode`'s for another mode's row:
    "Movie mode"), else in any mode the help runs read it in (as attach_help's find takes a row read in another
    mode)."""
    from page_model import key_text
    key = tuple(key_text(x).lower() for x in path)
    return rows.get((f"{mode} mode" if mode else FIRST_CONTEXT, key)) or next((v for k, v in rows.items() if k[1] == key), [])


def attach_help(recs: list, doc: dict, guides: list) -> collections.Counter:
    """Each record's help text and each option's, in place: "help" and "hs" (whose words: "camera" or "own"), "hg" (the
    guides the camera's words were read from), "oh" ([value, text, its guides, whose] per option). Text by text, the
    camera's own where the private help file has it (private/help/: the page stays local), else the project's own
    (data/<model>_fw<firmware>/help_*.json, else the definition's, merged in by schema_update, the same words); only
    the camera's words were read off a guide, so only they get its frames (2026-11-06, the owner: "when an item is
    selected or hovered, can we get the help text"). How many texts are whose."""
    from schema_update import counted_proofs, proved_rows
    sony = help_files.read(help_files.PRIVATE / help_files.name(doc), doc)          # each only if it is this camera's
    own = help_files.read(help_files.own_path(doc), doc)
    # the rows each record's counted proofs went through, as schema_update's attach_help keeps a help by them
    went = proved_rows(counted_proofs(RUN_ROOT / "kit2_pass2")) if RUN_ROOT is not None and sony else {}
    by_text = collections.defaultdict(list)
    for i, g in enumerate(guides):
        by_text[g["text"]].append(i)

    def help_of(s):
        for src, who in ((sony, "camera"), (own, "own"), ({s["key"]: s}, "own")):
            if (src.get(s["key"]) or {}).get("help"):
                return src[s["key"]]["help"], who
        return None, None

    def options_of(s):
        """[(value, text, whose)] in the values' order: the camera's text for a value where the private file has one,
        else the project's own."""
        got = {}
        for src, who in (({s["key"]: s}, "own"), (own, "own"), (sony, "camera")):          # the last one found wins
            for v, t in (src.get(s["key"]) or {}).get("option_help") or []:
                if t:
                    got[v] = (t, who)
        return [(v, *got[v]) for v in sorted(got)]
    by_key = {s["key"]: s for s in doc["settings"]}
    told = collections.Counter()
    for r in recs:
        s = by_key.get(r["k"]) or {}
        text, who = help_of(s) if s else (None, None)
        r["help"] = text or ""
        if text:
            r["hs"], told[who] = who, told[who] + 1
            r["hg"] = on_row(text_guides(text, guides, by_text), s, guides, went=went) if who == "camera" else []
        opts = options_of(s) if s else []
        if opts:
            names = dict((v, lab) for v, lab in s.get("values") or [])
            r["oh"] = [[v, t, on_row(text_guides(t, guides, by_text), s, guides, names.get(v, str(v)), went)
                        if who == "camera" else [], who]
                       for v, t, who in opts]
    return told


def attach_row_help(data, guides: list, told: collections.Counter) -> None:
    """A row no setting of the file belongs to (an action, a submenu), or whose settings have none of the camera's
    help, gets its own guide, in place, matched by its path in the menu and the mode as kit/schema_update.py's
    attach_help matches a setting's row: the last reading, as attach_help keeps it; counted in told as the camera's."""
    rows, by_rec = row_guides(guides), data["records"]
    for node, path in menu_nodes(data["menu"]):
        if any(by_rec.get(k, {}).get("hs") == "camera" for k in node["recs"]):
            continue
        hit = row_help(path, rows, node.get("mode"))
        if hit:
            last = guides[hit[-1]]["text"]
            node.update(help=last, hg=[i for i in hit if guides[i]["text"] == last], hs="camera")
            told["camera"] += 1


def menu_nodes(tabs: list):
    """Every row of the menu view, with its path from the top row (the tab and group left out, as the help runs key
    rows)."""
    def walk(rows, path):
        for x in rows:
            yield x, path + [x["l"]]
            yield from walk(x.get("kids") or [], path + [x["l"]])
    for t in tabs:
        for g in t.get("groups") or []:
            yield from walk(g.get("rows") or [], [])


# ---------------------------------------------------------------- My Menu and the Main page

def my_menu(doc, here: Path):
    """The definition's My Menu (camera.my_menu: one array record per page, each element a menu-item code) as the page
    shows it: every item's name by code (the slot settings' values), the settings each code opens (their menu_code),
    and the pages the slot settings' proof read back on the camera (<run>/mymenu_readback.json in the run their proof
    names: a file with known codes loaded, each page then read on the camera's screen), each with its frame. None when
    the definition has no My Menu."""
    cam = doc.get("camera") or {}
    mm = cam.get("my_menu") or {}
    if not mm.get("records"):
        return None
    ids = {f"global:0x{r:04x}" for r in mm["records"]}
    slots = [s for s in doc["settings"] if s["key"].split("[")[0] in ids]
    names = {}
    for s in slots:
        for v, lab in s.get("values") or []:
            names.setdefault(v, lab)
    opens = collections.defaultdict(list)
    for s in sorted(doc["settings"], key=lambda s: (s.get("area") != "global", s.get("order") if isinstance(s.get("order"), (int, float)) else 9999)):
        if isinstance(s.get("menu_code"), int) and s["key"].split("[")[0] not in ids:
            opens[str(s["menu_code"])].append(s["key"])
    read = []
    for run in sorted({(s.get("proved") or {}).get("run") for s in slots} - {None}) if RUN_ROOT is not None else ():
        src = RUN_ROOT / run / "mymenu_readback.json"
        if not src.exists():
            continue
        for page, info in sorted(json.loads(src.read_text(encoding="utf-8")).items(), key=lambda kv: int(kv[0])):
            link = frame(RUN_ROOT / run, info.get("frame"), here)
            read.append({"run": run, "page": int(page), "in_order": bool(info.get("in_order")),
                         "slots": info.get("slots") or [],
                         "frames": [[link, f"{run} · page {page} read back on the camera"]] if link else []})
    return {"title": (cam.get("text") or {}).get("my_menu_name") or "My Menu", "records": mm["records"],
            "empty": mm.get("empty"), "max_items": mm.get("max_items") or 0, "packed": mm.get("packed", True),
            "names": sorted([v, lab] for v, lab in names.items()), "opens": dict(opens), "read": read}


def main_pages(here: Path, modes: list, title: str = "Main") -> dict:
    """{mode: {"run", "frames"}}: a frame of the camera's own Main page in each mode, from the page scans of the camera's
    runs (kit/page_scan.py: every menu page with Down, the Main tile grid too; <run>/scan.jsonl): the Main page that
    follows the menu page before it in the lap (page 1; a second Main page follows the first), one frame per row of
    tiles, the first row lit first. A scan runs in one mode and its log does not say which: its run's name does, as
    the kit names them (kit2_page_scan_movie, kit2_page_scan_sq: a word of the name that is a mode's name), and a page
    scan whose name names none is the first mode's (kit2_page_scan, the Stills menu's). The plainest name first."""
    if RUN_ROOT is None or not RUN_ROOT.is_dir():
        return {}
    runs = []
    for run in RUN_ROOT.glob("kit2_page_scan*/scan.jsonl"):
        extra = [w for w in run.parent.name[len("kit2_page_scan"):].split("_") if w]
        named = [m for m in modes if mode_word(m) in extra]
        if len(named) <= 1 and modes:
            runs.append((len(extra), run.parent.name, named[0] if named else modes[0], run))
    out = {}
    for _, name, mode, scan in sorted(runs):
        if mode in out:
            continue
        recs = read_log(scan)
        lap = len(recs) > 2 and (recs[-1].get("page"), recs[-1].get("signature")) == (recs[0].get("page"), recs[0].get("signature"))
        recs = recs[:-1] if lap else recs
        for i, r in enumerate(recs):
            before = recs[i - 1] if i or lap else None
            if r.get("kind") != "tiles" or before is None or before.get("kind") == "tiles":
                continue
            page, row = [], -1
            for x in recs[i:] + (recs[:i] if lap else []):
                if x.get("kind") != "tiles" or (x.get("row") or 0) <= row:
                    break
                row = x.get("row") or 0
                link = frame(scan.parent, x.get("frame"), here)
                if link:
                    page.append([link, f"{mode}: the camera's {title} page ({name}), row {row + 1} of tiles lit"])
            if page:
                out[mode] = {"run": name, "frames": page}
                break
    return out


def main_page(doc, here: Path):
    """The camera's Main page per mode (camera.main_tiles: each tile's caption and the records it reads) with a frame
    of each mode's Main page where the runs hold one (main_pages); None when the definition has none."""
    cam = doc.get("camera") or {}
    sets = [s for s in cam.get("main_tiles") or [] if s.get("tiles")]
    if not sets:
        return None
    title = (cam.get("text") or {}).get("main_title") or "Main"
    shots = main_pages(here, [s.get("name") or "" for s in sets], title)
    return {"title": title,
            "modes": [{"name": s.get("name") or "", "tiles": s["tiles"], **shots.get(s.get("name") or "", {"run": None, "frames": []})}
                      for s in sets]}


def extras_line(data) -> str:
    """One line on the help text, My Menu and the Main page: how much of each the runs tie to a frame."""
    gs, recs = data.get("guides") or [], (data.get("records") or {}).values()
    shown = lambda ids: any(gs[i]["frames"] for i in ids or [])          # noqa: E731
    helps = [r for r in recs if r.get("help")]
    opts = [o for r in recs for o in r.get("oh") or []]
    # only the camera's words can be tied to a guide frame: the project's own are counted apart, never as unlinked
    texts = [r.get("hg") for r in helps if r.get("hs") == "camera"] + [o[2] for o in opts if o[3] == "camera"]
    nodes = [x for x, _ in menu_nodes(data.get("menu") or [])]
    bare = [x for x in nodes if not x["recs"] and not x["subs"]]          # no setting of the file belongs to the row
    leaves = [x for x in bare if not x["kids"]]
    src, osrc = collections.Counter(r.get("hs") for r in helps), collections.Counter(o[3] for o in opts)
    line = (f"help: {len(helps)} settings ({src.get('camera', 0)} the camera's guide, {src.get('own', 0)} the project's own words), "
            f"{len(opts)} option texts ({osrc.get('camera', 0)} the camera's guide, {osrc.get('own', 0)} the project's own words); "
            f"{sum(1 for g in texts if shown(g))} of {len(texts)} texts from the camera's guide linked to a guide frame, "
            f"{sum(1 for g in texts if any('ocr' in gs[i] for i in g or []))} whose two readings differed; "
            f"{sum(1 for x in bare if x.get('help'))} of {len(bare)} rows with no setting of "
            f"their own given their guide ({sum(1 for x in leaves if x.get('help'))} of {len(leaves)} with no rows under "
            f"them), {sum(1 for x in nodes if x.get('help') and x['recs'])} rows whose settings have none of the camera's "
            f"help given theirs")
    mm = data.get("my_menu")
    if mm:
        seen = {c for p in mm["read"] if p["in_order"] and p["frames"] for c, _ in p["slots"]}
        names = [c for c, _ in mm["names"] if c != mm["empty"]]
        line += f"; My Menu: {sum(c in seen for c in names)} of {len(names)} item names with a picture"
    main = data.get("main")
    if main:
        line += f"; Main: {sum(1 for m in main['modes'] if m['frames'])} of {len(main['modes'])} modes with a frame"
    return line


# ---------------------------------------------------------------- --pack: the page and its frames in one folder

def frame_lists(data):
    """Every [[frame, caption]] list the page shows: each record's evidence, each menu row's pass 1 walk, each guide
    a help text was read from, My Menu's pages read back and each mode's Main page."""
    for r in (data.get("records") or {}).values():
        for e in r.get("ev") or []:
            yield e["frames"]
    for g in data.get("guides") or []:
        yield g["frames"]
    for p in (data.get("my_menu") or {}).get("read") or []:
        yield p["frames"]
    for m in (data.get("main") or {}).get("modes") or []:
        yield m["frames"]
    for x, _ in menu_nodes(data.get("menu") or []):
        yield x.get("walk") or []


def linked_frames(data) -> set:
    """The frame paths the page links, as frame() wrote them."""
    return {shot[0] for shots in frame_lists(data) for shot in shots}


def relink(data, new: dict) -> int:
    """Point every frame link that new names at new[link], in place (a list several records share is mended
    once); the number of links changed."""
    n = 0
    for shots in frame_lists(data):
        for shot in shots:
            if shot[0] in new:
                shot[0], n = new[shot[0]], n + 1
    return n


def pack_plan(links, page_dir: Path, runs: Path = None, png: bool = False) -> dict:
    """{link: (the frame's file, its copy's link)}: the copy under frames/<run>/<its path in the run>, relative to
    the page, with a .jpg name unless png (a frame already in JPEG keeps its name)."""
    plan, runs = {}, runs or RUN_ROOT
    for link in links:
        src = Path(link) if Path(link).is_absolute() else Path(os.path.normpath(page_dir / link))
        rel = src.relative_to(runs)
        if not png and src.suffix.lower() not in (".jpg", ".jpeg"):
            rel = rel.with_suffix(".jpg")
        plan[link] = (src, (Path(FRAMES) / rel).as_posix())
    return plan


def pack_one(src: Path, dst: Path) -> str:
    """Copy one frame, converted to JPEG when dst is a .jpg and src is not; "skipped" when dst is there and as new
    as src, else "converted" or "copied". Written beside dst and then renamed, so a stopped pack leaves no half
    file that a later one would take for done."""
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return "skipped"
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    if dst.suffix.lower() == ".jpg" and src.suffix.lower() not in (".jpg", ".jpeg"):
        from PIL import Image
        with Image.open(src) as im:
            im.convert("RGB").save(part, "JPEG", quality=85, optimize=True)
        part.replace(dst)
        return "converted"
    shutil.copy2(src, part)          # keeps the source's time, so the next pack skips it
    part.replace(dst)
    return "copied"


def pack_frames(jobs: dict, workers: int | None = None, say=print):
    """Copy or convert every frame (jobs: {source: copy}) on threads, Pillow letting go of the GIL while it
    decodes and encodes; (a Counter of "converted", "copied" and "skipped", {source: error} for those that failed).
    Says how far it is every 1000 frames."""
    done, failed = collections.Counter(), {}
    pool = ThreadPoolExecutor(max_workers=workers or os.cpu_count() or 4)
    try:
        futures = {pool.submit(pack_one, src, dst): src for src, dst in jobs.items()}
        for i, f in enumerate(as_completed(futures), 1):
            try:
                done[f.result()] += 1
            except Exception as e:          # one unreadable frame does not stop the other 16,000
                failed[futures[f]] = e
            if i % 1000 == 0:
                say(f"  {i} / {len(jobs)} frames")
    finally:
        pool.shutdown(cancel_futures=True)          # Ctrl-C stops at once, not after the queue
    return done, failed


def prune(frames_dir: Path, keep) -> int:
    """Remove the files under frames_dir that keep does not name, then the folders that leaves empty; the number
    of files removed. Only a folder named frames/, and nothing outside it."""
    if frames_dir.name != FRAMES:
        raise ValueError(f"{frames_dir} is not a {FRAMES}/ folder")
    if not frames_dir.is_dir():
        return 0
    keep = {Path(os.path.normpath(p)) for p in keep}
    n = 0
    for d, _, files in os.walk(frames_dir, topdown=False):
        for f in files:
            if Path(os.path.normpath(Path(d) / f)) not in keep:
                (Path(d) / f).unlink()
                n += 1
        if Path(d) != frames_dir and not os.listdir(d):
            os.rmdir(d)
    return n


def size_text(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.1f} MB"


def pack(data, page_dir: Path, runs: Path = None, png: bool = False, workers: int | None = None, say=print) -> str:
    """Copy every frame data links into page_dir/frames/, point the links at the copies (in place) and remove the
    copies no longer linked; the summary line. A frame that could not be copied keeps its link into the runs
    (runs: the camera's run root the links point into, by default the one the page reads)."""
    plan = pack_plan(linked_frames(data), page_dir, runs, png)
    jobs = {src: page_dir / new for src, new in plan.values()}
    done, failed = pack_frames(jobs, workers, say)
    for src, e in list(failed.items())[:5]:
        say(f"  could not pack {src}: {e}")
    removed = prune(page_dir / FRAMES, jobs.values())
    relink(data, {link: new for link, (src, new) in plan.items() if src not in failed})
    size = sum(p.stat().st_size for p in (page_dir / FRAMES).rglob("*") if p.is_file())
    try:
        where = page_dir.relative_to(ROOT).as_posix()
    except ValueError:
        where = str(page_dir)
    line = (f"packed {len(jobs) - len(failed)} frames: {done['converted']} converted to JPEG, {done['copied']} copied, "
            f"{done['skipped']} skipped (already there), {removed} removed (no longer linked); "
            f"{FRAMES}/ holds {size_text(size)}")
    if failed:
        return line + f"; {len(failed)} could not be packed and still link into runs/, so {where}/ is not self-contained"
    return line + f". {where}/ is now self-contained: copy or zip the folder"


def page_json(data) -> str:
    """The page's DATA as its script holds it: JSON with every <, > and & written as \\u003c, \\u003e, \\u0026 (the
    same strings to the script), so no text in it, a guide read off the screen or a note, can end the script or, with
    "<!--" and "<script", keep the page's own </script> from ending it."""
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def main():
    global RUN_ROOT
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=None, help="the page (default: runs/<model>_fw<fw>/_viewer/index.html, the "
                                                "definition's camera's folder)")
    ap.add_argument("--values", default=None, help="a camera download whose values the rows show (default: the "
                                                   "newest kit2_*/dat/reference_session_start.DAT in the camera's runs)")
    ap.add_argument("--pack", action="store_true", help="also copy every frame the page links into its "
                    "_viewer/frames/ (JPEG, quality 85) and link the copies: the folder then opens on any computer")
    ap.add_argument("--png", action="store_true", help="with --pack: copy the frames as they are, not as JPEG")
    ap.add_argument("--open", action="store_true", help="open the page in the default browser once it is built")
    ap.add_argument("--definition", default=None, help="the definition's camera, <model>_fw<fw> (default: the camera "
                                                        "the kit works on, else ILCE-1M2_fw4.00)")
    a = ap.parse_args()
    if a.png and not a.pack:
        ap.error("--png goes with --pack")
    if a.pack and a.out:
        ap.error("--pack packs the page's own _viewer/ only (it removes old copies under its frames/): leave --out "
                 "at its default")
    doc = definitions.load(Path(SCHEMA or pick_definition(a.definition)))      # whole: the evidence put back
    DAMAGED.clear()
    folder, RUN_ROOT, why = place(doc)
    if not the_runs():          # no page without the camera's own runs (2026-11-06, the owner): nothing is written
        print(why, file=sys.stderr)
        sys.exit(NO_RUNS)
    out = Path(a.out).resolve() if a.out else (folder / "_viewer" / "index.html").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    values = Path(a.values) if a.values else newest_start()
    raw = unmapped(doc, values)
    full = dict(doc, settings=doc["settings"] + raw)       # the unmapped records get their frames too
    ev = collect(full["settings"], out.parent)
    recs = records(full, ev)
    cur = current_values(values) if values else {}
    guides = guide_reads(out.parent)
    told = attach_help(recs, doc, guides)
    raw_of, by_key = {s["key"]: s["raw"] for s in raw}, {s["key"]: s for s in doc["settings"]}
    for r in recs:
        r["cur"] = cur.get(r["k"])
        if r["k"] in raw_of:
            r["raw"] = raw_of[r["k"]]
        if (by_key.get(r["k"]) or {}).get("range"):
            r["rg"], r["u"] = True, by_key[r["k"]].get("unit") or ""          # a number's unit, as the editor writes one (the Main tiles)
    links = sum(len(e["frames"]) for r in recs for e in r["ev"])
    data = {"model": doc.get("model"), "camera": definition_key(doc), "made": datetime.date.today().isoformat(),
            "pictures": links,              # 0: the title line says there are none on this computer
            # the download itself, for the file layout view (the page reads it through the block, as camkit/camset.py does)
            "file": {"name": values.name, "b64": base64.b64encode(values.read_bytes()).decode()} if values else None,
            "values": f"{values.parent.parent.name}/{values.name}" if values else "",
            "colors": (doc.get("camera") or {}).get("tab_colors") or {},
            # the container block the layout view reads the file through and names its parts by (decision 20)
            "format": (doc.get("camera") or {}).get("file"),
            "memory_names": ((doc.get("camera") or {}).get("memory_sets") or {}).get("names") or {},
            "memory_modes": ((doc.get("camera") or {}).get("memory_sets") or {}).get("modes") or {},
            "menu": menu(full, recs, out.parent), "records": {r["k"]: r for r in recs}}
    # My Menu and the Main page from the definition's camera section, with the frames of the camera's own screens
    data.update(my_menu=my_menu(doc, out.parent), main=main_page(doc, out.parent))
    attach_row_help(data, guides, told)
    data["guides"], data["help_source"] = used_guides(data, guides), dict(told)          # the top bar says where help comes from
    data["damaged"] = sum(DAMAGED.values())          # the top bar says how many damaged log lines were left out
    packed = pack(data, out.parent, RUN_ROOT, a.png) if a.pack else None
    page = (Path(__file__).with_name("proof_viewer.html").read_text(encoding="utf-8")
            .replace("<title>Proof Viewer</title>", f"<title>Proof Viewer: {html.escape(data['camera'])}</title>", 1)
            .replace("/*DATA*/null", page_json(data), 1))
    out.write_text(page, encoding="utf-8", newline="\n")
    shown = sum(1 for r in recs if any(e["frames"] for e in r["ev"]))
    print(extras_line(data))
    print(f"wrote the proof viewer: {len(recs)} records, {sum(r['proved'] for r in recs)} proved, {shown} with "
          f"pictures, {links} frame links, from {paths.shown(RUN_ROOT)}/"
          + (f"; values from {paths.shown(values)}" if values else "; no camera download (--values FILE.DAT shows a file's values)"))
    if DAMAGED:
        print(f"left out {sum(DAMAGED.values())} damaged log line(s): "
              + ", ".join(f"{n} in {f}" for f, n in sorted(DAMAGED.items())))
    if packed:
        print(packed)
    if a.open and not webbrowser.open(out.as_uri()):
        print("no browser could be opened: open the page below by hand")
    print(out)          # always the last line: kit/setup.py reports it


if __name__ == "__main__":
    main()
