"""Values the camera's menus never offer (not_offered): each mark a table names, written only when the evidence it
cites holds, so a rerun after a new walk drops a mark the camera contradicts. And the values they offer under one video
system only (video_system_values), from the rows walked under each system, the downloads' headers saying which, checked
against the camera's own downloads at every write."""
import json
import re
import sys
from pathlib import Path

from pass2_report import alike, strip_icon


def table_cells(tables: dict, name: str, page: str | None) -> list:
    """The picker cells of one screen of the table walk (runs/<camera>/kit2_tables/tables.json): a keyset's page by
    its title ("Dial/Wheel"), or a table's own cells (My Dial Settings). None found: []."""
    t = tables.get(name) or {}
    if page is None:
        return [c for c in t.get("cells") or [] if c.get("opens") == "picker"]
    return [c for p in t.get("pages") or [] if p.get("title") == page for c in p.get("items") or []
            if c.get("opens") == "picker"]


def walked_rows(report: list, key: str, pattern: str) -> list:
    """The report's rows whose name matches `pattern` and that prove `key`: the walks of its list in each state."""
    return [e for e in report if re.search(pattern, e["row"]) and key in e["records"]]


def held_in(run_root: Path, files: list, key: str, value: int) -> bool:
    """Whether each download (a path in the camera's runs) holds `value` in the record `key` ("global:0x0dfa")."""
    from camkit import camset
    m = re.fullmatch(r"global:0x([0-9a-f]{4})", key)
    if not m or not files:
        return False
    for f in files:
        path = run_root / f
        rec = camset.read(path).get(0, int(m[1], 16)) if path.exists() else None
        if rec is None or rec.value() != value:
            return False
    return True


def why_not(entry: dict, s: dict, value: int, report: list, tables: dict, run_root: Path) -> str | None:
    """Why a mark does not stand (None when its evidence holds): the setting lacks the value; a walk wrote it, or no
    walk proves the record; a picker list was not walked round, or lists the function; a held value's downloads do
    not hold it."""
    labels = dict((v, lab) for v, lab in s.get("values") or [])
    if value not in labels:
        return "the setting has no such value"
    if "walk" in entry:
        rows = walked_rows(report, s["key"], entry["walk"])
        if not rows:
            return f"no row the report proves matches {entry['walk']!r}"
        wrote = [e["row"] for e in rows if value in e["records"][s["key"]]["proved"].values()]
        if wrote:
            return f"{wrote[0]} wrote it"
    if "table" in entry:
        cells = table_cells(tables, *entry["table"])
        if not cells:
            return f"the table walk has no picker list on {entry['table']}"
        if not all(c.get("wrapped") for c in cells):
            return f"a list on {entry['table']} was not walked round to its start"
        listed = [o["label"] for c in cells for o in c.get("options") or [] if alike(strip_icon(o["label"]), labels[value])]
        if listed:
            return f"{entry['table']} lists {listed[0]!r}"
    if entry.get("held") and entry.get("files") and not held_in(run_root, entry["files"], s["key"], value):
        return "a download it cites does not hold it"
    return None


def not_offered_marks(doc: dict, entries: list, report: list, tables: dict, run_root: Path) -> tuple:
    """Each setting's `not_offered`, [{value, label, why, menu, evidence, held?}] in value order, from the marks
    `entries` names (the hand tables' NOT_OFFERED: a key, its values, the why in plain words, the menu, the
    evidence, and
    "walk" (a pattern for the report's rows that walked the list, whole as the entry's evidence says: the writer checks
    that each proves the record and none wrote the value), "table" (a picker screen of the table walk) or both), each
    written only when its evidence holds (why_not); a mark it refuses is printed. A value the camera holds but its list
    cannot choose back is "held" (ISO AUTO Minimum's factory ISO 64), and an editor keeps offering it. A setting no
    mark names loses an old field. Returns (values marked, marks refused)."""
    by_key = {s["key"]: s for s in doc["settings"]}
    marks, refused = {}, []
    for entry in entries:
        s = by_key.get(entry["key"])
        for v in entry["values"]:
            why = "no such setting" if s is None else why_not(entry, s, v, report, tables, run_root)
            if why:
                refused.append((entry["key"], v, why))
                continue
            mark = {"value": v, "label": dict((x, lab) for x, lab in s["values"])[v], "why": entry["why"],
                    "menu": entry["menu"]}
            if entry.get("evidence"):               # the hand evidence's (writer/hand_evidence.py), when it is here
                mark["evidence"] = entry["evidence"]
            if entry.get("held"):
                mark["held"] = True
            marks.setdefault(s["key"], {})[v] = mark
    for s in doc["settings"]:
        got = [m for _, m in sorted((marks.get(s["key"]) or {}).items())]
        if got:
            s["not_offered"] = got
        else:
            s.pop("not_offered", None)
    n = sum(len(m) for m in marks.values())
    print(f"not offered: {n} values the camera's menus never offer, on {len(marks)} settings "
          f"({sum(1 for m in marks.values() for x in m.values() if x.get('held'))} of them held, still offered); "
          f"{len(refused)} marks refused")
    for k, v, why in refused:
        print(f"  not marked  {k} {v}: {why}")
    return n, len(refused)


# a proof's context that names the video system its row was walked under ("Movie mode, PAL, File Format XAVC S 4K")
SYSTEM_WORD = re.compile(r"\[[^\]]*\b(NTSC|PAL)\b[^\]]*\]")


def proof_file(run_root: Path, run: Path, dat: str) -> Path | None:
    """A proof's download: one named with its run in front (pass2_report.qualified) in that run's dat/ or at its top,
    else in the main run's dat/."""
    from pass2_report import QUALIFIED
    m = QUALIFIED.fullmatch(dat or "")
    places = [run_root / m[1] / "dat" / m[2], run_root / m[1] / m[2]] if m else [run / "dat" / (dat or "")]
    return next((p for p in places if dat and p.exists()), None)


def row_systems(report: list, proofs: list, run_root: Path, run: Path) -> dict:
    """{report row: its video system} for each row of a record some row's context walked under a named video system
    (SYSTEM_WORD): the system every download of the row's proofs says in its header (camkit.camset's video_system),
    and the context's word, where it names one, agreeing. A row whose downloads say two systems, none, or another than
    its context is printed and left out."""
    from camkit import camset
    from pass2_report import row_name
    named = {k for e in report if SYSTEM_WORD.search(e["row"]) for k in e["records"]}
    rows = {e["row"] for e in report if set(e["records"]) & named}
    files = {}
    for r in proofs:
        if row_name(r) in rows:
            files.setdefault(row_name(r), []).append(proof_file(run_root, run, r.get("dat")))
    out, seen = {}, {}
    for row in sorted(rows):
        said = set()
        for f in files.get(row) or [None]:
            if f is not None and f not in seen:
                seen[f] = camset.read(f).video_system
            said.add(seen.get(f) if f is not None else None)
        word = SYSTEM_WORD.search(row)
        if len(said) == 1 and None not in said and (not word or word[1] in said):
            out[row] = said.pop()
        else:
            print(f"  video system  {row[:70]}: its downloads say {sorted(map(str, said))}"
                  + (f", its context {word[1]}" if word else "") + "; left out")
    return out


def system_values(doc: dict, report: list, systems: dict, table: dict) -> dict:
    """{key: {"NTSC": [...], "PAL": [...]}}: for each setting rows walked under each video system (row_systems), the
    listed values proved under one system only, in value order; a value proved under both is under neither, and so is
    one no proof walked. A setting gets one when some listed value is one system's: a list whose listed values are all
    one system's has the other's empty (the other system's rates, proved, not among its values). The camera's hand
    table (`table`, the hand tables' VIDEO_SYSTEM_VALUES: a key, its values by system, both keys, and the evidence)
    gives a
    setting no proof walked under both systems; where the proofs speak, they stand and the table's entry is printed."""
    by_key = {s["key"]: s for s in doc["settings"]}
    seen = {}
    for e in report:
        system = systems.get(e["row"])
        for k, r in e["records"].items() if system else ():
            seen.setdefault(k, {}).setdefault(system, set()).update(
                v for v in r["proved"].values() if not isinstance(v, (list, dict)))
    out = {}
    for k, by in seen.items():
        listed = [v for v, _ in (by_key.get(k) or {}).get("values") or []]
        ntsc, pal = by.get("NTSC", set()), by.get("PAL", set())
        got = {"NTSC": sorted(v for v in listed if v in ntsc - pal), "PAL": sorted(v for v in listed if v in pal - ntsc)}
        if "NTSC" in by and "PAL" in by and (got["NTSC"] or got["PAL"]):
            out[k] = got
    for k, entry in table.items():
        if k in out:
            print(f"  video system  {k}: the proofs give its values; the hand table's entry is not used")
        elif k in by_key:
            listed = {v for v, _ in by_key[k].get("values") or []}
            out[k] = {"NTSC": sorted(v for v in entry["NTSC"] if v in listed),
                      "PAL": sorted(v for v in entry["PAL"] if v in listed)}
    return out


def with_video_systems(doc: dict, report: list, proofs: list, table: dict, run_root: Path, run: Path) -> int | None:
    """Each setting's `video_system_values` ({"NTSC": [...], "PAL": [...]}: a value listed under one system is
    offered only when the file's header says that system; one under neither under both) from system_values, right
    after its `not_offered` or its values; a setting none is found for loses an old one. With no proofs (a plain run
    with no report) the definition is left as it is. Returns how many settings carry one."""
    if not proofs:
        return None
    found = system_values(doc, report, row_systems(report, proofs, run_root, run), table)
    for s in doc["settings"]:
        want = found.get(s["key"])
        fields = [(k, v) for k, v in s.items() if k != "video_system_values"]
        after = "not_offered" if "not_offered" in s else "values"
        s.clear()                                   # in place: the callers' by-key maps hold these very settings
        for k, v in fields:
            s[k] = v
            if k == after and want:
                s["video_system_values"] = want
        if want and "video_system_values" not in s:
            s["video_system_values"] = want
    print(f"video systems: {len(found)} settings whose menus offer some values under one video system only "
          f"({', '.join(sorted(found))})")
    return len(found)


# how many downloads of each video system the check reads, spread over the camera's download log
SYSTEM_SAMPLE = 200


def downloads_by_system(run_root: Path, most: int = SYSTEM_SAMPLE) -> tuple:
    """({video system: [downloads]}, how many could not be read): up to `most` of the camera's downloads of each video
    system its header says (the download log, runs/<model>_fw<fw>/downloads.jsonl), spread evenly over each system's
    downloads, so the system with few downloads is read as widely as the other."""
    from camkit import camset
    log = run_root / "downloads.jsonl"
    names = [json.loads(x)["path"] for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if log.exists() else []
    by, unread = {}, 0
    for n in names:
        path = run_root / n
        try:
            by.setdefault(camset.peek_video_system(path.read_bytes()), []).append(path)
        except (ValueError, OSError):
            unread += 1
    # a file whose block does not say its system ("") says nothing of either list
    return {vs: files[::max(1, len(files) // most)][:most] for vs, files in by.items() if vs}, unread


def check_video_systems(doc: dict, run_root: Path, most: int = SYSTEM_SAMPLE) -> tuple | None:
    """Every setting's video_system_values against the camera's own downloads (downloads_by_system): a value listed as
    one system's only must not be held in the live settings of a download whose header says the other system, for the
    camera wrote that file and an editor would flag it. A contradiction stops the write (exit 1, the setting and the
    file named, never a value); a download that cannot be read is skipped and counted. Returns (downloads read, could
    not be read), None with no downloads."""
    from camkit import camset
    marked = [s for s in doc["settings"] if s.get("video_system_values")]
    by, unread = downloads_by_system(run_root, most)
    if not by:
        return None
    read = 0
    for system, files in sorted(by.items()):
        for f in files:
            try:
                cs = camset.read(f)
            except (ValueError, OSError):
                unread += 1
                continue
            read += 1
            for s in marked:
                other = [v for vs, vals in s["video_system_values"].items() if vs != system for v in vals]
                m = re.fullmatch(r"global:0x([0-9a-f]{4})", s["key"])
                rec = cs.get(0, int(m[1], 16)) if m else None
                if rec is not None and rec.value() in other:
                    sys.exit(f"video systems: {s['key']} ({s['name']}) lists a value as another system's only, but "
                             f"{f.relative_to(run_root)}, a {system} download, holds it: the proofs or the hand table "
                             "(VIDEO_SYSTEM_VALUES) are wrong for this camera; nothing written")
    print(f"video systems: {len(marked)} settings' values checked against {read} of the camera's downloads "
          f"({', '.join(f'{len(fs)} {vs}' for vs, fs in sorted(by.items()))})"
          + (f", {unread} that could not be read skipped" if unread else ""))
    return read, unread
