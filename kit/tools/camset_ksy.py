"""Write the record names the CAMSET format's Kaitai description imports: a definition's record ids as an enum.

    .venv/bin/python kit/tools/camset_ksy.py        # every definition's (kit/tools/build_docs.py writes them too)

docs/formats/sony_camset.ksy describes the container block the ILCE-1M2 writes, written by hand, for people and for
the tools that read files with it (Kaitai Struct's Web IDE and compiler, ImHex); the contract the kit and the editor
read is the camera's container block, the "file" of its camera section (docs/decisions/0020), and a test ties the two
(kit/tests/test_definitions.py). This writes the record names, one file per definition in editor/definitions/:
docs/formats/sony_camset_ids_<model>_fw<fw>.ksy, Kaitai id sony_camset_ids_<model>_fw<fw> in lower case with "_" for
anything else (sony_camset_ids_ilce_1m2_fw4_00), an enum naming each record id the definition knows (the first
setting on it, its tab and group, its values when they are few, and whether it is proved). sony_camset.ksy imports
the reference definition's (camkit.definitions.REFERENCE); a second camera's is written all the same, for a container
spec of its own. Sony's help text stays out: the files are meant to be published.

A record's identifier is its first setting's name in Kaitai's spelling (base), with its record id added where another
record holds that one. A name someone's parser uses must never come to mean another record: no identifier the file
ever gave one record is given to another. So the file is its own memory (published, record_names): its enum, and under
the top-level key "-retired-ids" (RETIRED) every identifier a record bore before it was renamed, or before it left the
definition, with that record's id. Kaitai's compiler ignores a key that begins with "-" (its reader comes out the
same, and kit/tools/build_docs.py leaves such keys out of what the reader is compiled from), and the key sits in the
file itself so the memory travels with what is published and merged, and no other file can fall out of step with it.
A record keeps the identifier the file gives it while the name of one of its settings still gives it (base, or base
with its id: a live setting found on a memory set's record leaves the set's name with it), takes back one it bore
before when its name gives that again, and otherwise takes its name's, with its id added where the file gave that one
to another record, current or retired. Renames stay allowed: the old identifier is retired, never reused. A file that
cannot be read (git's conflict markers left in it) stops the write in plain words, never a traceback: the memory is
never written over unread.

Until 2026-11-19 the names were dealt out afresh in record order at every write, so a new record with a lower id took a
name another record had borne (b3afe42: 0x01de took jpeg_heif_quality from 0x01ea), and then for a while a renamed
record's old identifier left the file and could be taken again. The a1 II's retired identifiers were seeded from the
published files (github/main, gitea/main, v0.2.0, v0.2.1): the ten its records bore there before they were renamed.
"""
import argparse
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# camkit before any other package, as in every kit program: a Python without the kit's packages is told so (camkit/start.py)
from camkit import ROOT, definitions  # noqa: E402
import yaml  # noqa: E402

SCHEMA = definitions.path(definitions.REFERENCE)          # the definition whose record names the .ksy imports
FORMATS = ROOT / "docs" / "formats"
FORMAT = FORMATS / "sony_camset.ksy"
IDS_PREFIX = "sony_camset_ids_"
RETIRED = "-retired-ids"            # {identifier: record id} no longer borne, never given to another record
IDENT = re.compile(r"[a-z][a-z0-9_]*")


def ids_name(camera: str) -> str:
    """The record names' file name, without .ksy, of a camera's key: sony_camset_ids_ILCE-1M2_fw4.00 (what an
    import names: Kaitai reads <name>.ksy beside the spec that imports it)."""
    return IDS_PREFIX + camera


def ids_path(camera: str) -> Path:
    """docs/formats/sony_camset_ids_<model>_fw<fw>.ksy of a camera's key."""
    return FORMATS / f"{ids_name(camera)}.ksy"


def ids_id(camera: str) -> str:
    """The record names' Kaitai id (meta.id) of a camera's key, a valid identifier: lower case, "_" for anything
    else (sony_camset_ids_ilce_1m2_fw4_00). kaitai-struct-compiler names the Python module after it."""
    return IDS_PREFIX + re.sub(r"[^a-z0-9]+", "_", camera.lower()).strip("_")


def imported() -> list:
    """The record names' files (names without .ksy) the hand-written container imports."""
    return list((format_spec().get("meta") or {}).get("imports") or [])


def base(name: str) -> str:
    """The Kaitai identifier a name gives (lower case, digits, underscores, a letter first), before any record id is
    added to tell it apart."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "record"
    if not s[0].isalpha():
        s = "r_" + s
    return s[:60].rstrip("_")


def ident(name: str, used: set, rid: int) -> str:
    """A Kaitai identifier for record `rid` named `name`, unique among `used` (which it joins): the name's (base),
    else with the record's id added."""
    s = base(name)
    if s in used:
        s = f"{s}_{rid:04x}"
    n = 2
    while s in used:                    # a name that is another's with an id already ("x 01de" beside "x")
        s, n = f"{base(name)}_{rid:04x}_{n}", n + 1
    used.add(s)
    return s


START_AGAIN = ("Its identifiers are the memory that keeps each record's Kaitai name with its record, so it is never "
               "written over unread. Take the file whole as the branch you publish from has it (git checkout main -- {f}; "
               "with conflict markers, that is resolving the conflict to that side), then run "
               ".venv/bin/python kit/tools/build_docs.py --no-viewer: the records only the other side named take their "
               "names again, and none takes one the file gave another record. Nothing was written.")


def unreadable(p: Path, why: str) -> SystemExit:
    """The stop for a record names file the memory cannot be read from, in plain words: why, and how to start again."""
    from camkit import paths
    f = paths.shown(p) if Path(p).resolve().is_relative_to(ROOT) else str(p)
    return SystemExit(f"{f}: {why}. " + START_AGAIN.format(f=f))


def published(camera: str) -> tuple:
    """(kept, retired): the identifiers the camera's committed record names file gives (ids_path), {record id:
    identifier} from its enum, and {identifier: record id} from its RETIRED key; ({}, {}) with no file. The memory
    record_names keeps each identifier with its one record by. A file that is not YAML (git's conflict markers left
    in it), or that gives one identifier to two records, stops in plain words (unreadable), never a traceback."""
    p = ids_path(camera)
    if not p.exists():
        return {}, {}
    text = p.read_text(encoding="utf-8")
    try:
        spec = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        marks = any(line.startswith(("<<<<<<<", ">>>>>>>")) for line in text.splitlines())
        raise unreadable(p, ("it holds git's conflict markers, so it does not read as YAML" if marks else
                             f"it does not read as YAML ({str(e).splitlines()[0]})")) from None
    if not isinstance(spec, dict):
        raise unreadable(p, "it is not a Kaitai spec (no mapping at its top)")
    values = ((spec.get("enums") or {}).get("setting") or {})
    kept = {rid: e["id"] for rid, e in values.items()
            if isinstance(rid, int) and isinstance(e, dict) and isinstance(e.get("id"), str)}
    retired = spec.get(RETIRED) or {}
    if not isinstance(retired, dict) or not all(isinstance(i, str) and IDENT.fullmatch(i) and isinstance(r, int)
                                                and not isinstance(r, bool) for i, r in retired.items()):
        raise unreadable(p, f"its {RETIRED} is not identifiers each with a record id")
    owner = dict(retired)
    for rid, i in sorted(kept.items()):
        if owner.setdefault(i, rid) != rid:
            a, b = sorted((owner[i], rid))
            raise unreadable(p, f"it gives {i} to two records, 0x{a:04x} and 0x{b:04x}")
    return kept, dict(retired)


def retired_after(names: dict, kept: dict, retired: dict) -> dict:
    """{identifier: record id} retired once `names` (record_names') are written: every identifier the file gave a
    record (`kept`, `retired`) that its record does not bear now, renamed or gone from the definition."""
    owner = {**retired, **{i: rid for rid, i in kept.items()}}
    return {i: rid for i, rid in owner.items() if (names.get(rid) or (None,))[0] != i}


def record_names(doc, kept: dict | None = None, retired: dict | None = None) -> dict:
    """{record id: (identifier, doc line)} from the schema, live keys before memory-set ones. `kept` and `retired`, the
    identifiers the committed file gives (published): a record keeps its own while the name of one of its settings
    still gives it (base, or base with its id: a live setting found on a memory set's record leaves the set's name with
    it), else takes back one it bore before (retired) that a name of its gives again; none ever takes one the file gave
    another record, current or retired; every other record, in record order, takes its first setting's name's
    (ident)."""
    kept, retired = kept or {}, retired or {}
    first, every = {}, collections.defaultdict(list)
    for s in doc["settings"]:
        m = re.match(r"(global|set):0x([0-9a-f]+)(\[\d+\]|@\d+)?$", s["key"])
        if not m:
            continue
        rid = int(m.group(2), 16)
        every[rid].append(s)
        if rid in first and (first[rid][0] == "global" or m.group(1) == "set"):
            first[rid][2].append(s)
            continue
        first[rid] = (m.group(1), s, [s])

    def name_of(rid, s):
        name = re.sub(r"\s*\(.*?\)\s*$", "", s.get("name") or "") or f"record {rid:04x}"
        if s["key"].endswith("]") or "@" in s["key"]:
            name = f"{name} (array)" if s["key"].endswith("]") else f"{name} (block)"
        return name
    names = {rid: name_of(rid, s) for rid, (_, s, _) in first.items()}
    # what the file gives a record stays its own while one of its settings' names gives it, else one it bore before
    # that a name of its gives again; every identifier the file ever gave a record is taken
    stays = {}
    for rid in sorted(first):
        mine = kept.get(rid)
        given = [x for s in every[rid] for b in [base(name_of(rid, s))] for x in (b, f"{b}_{rid:04x}")]
        back = [x for x in given if retired.get(x) == rid and x not in stays.values()]
        if mine in given and mine not in stays.values():
            stays[rid] = mine
        elif back:
            stays[rid] = back[0]
    out, used = {}, set(kept.values()) | set(retired)
    for rid in sorted(first):
        area, s, all_ = first[rid]
        proved = sum(1 for x in all_ if x.get("proved"))
        vals = s.get("values") or []
        line = f"{s.get('name')}" + (f" [{s.get('tab')} > {s.get('group')}]" if s.get("tab") else "")
        if 0 < len(vals) <= 8 and not s["key"].endswith("]"):
            line += ": " + ", ".join(f"{v} {lab}" for v, lab in vals)
        line += f". {'memory sets' if area == 'set' else 'live settings'}; {proved} of {len(all_)} settings on it proved on the camera."
        out[rid] = (stays.get(rid) or ident(names[rid], used, rid), line)
    return out


def ksy(doc, kept: dict | None = None, retired: dict | None = None) -> dict:
    """The record names file of a definition as data; `kept` and `retired` the identifiers to keep with their records
    (record_names), by default the ones the camera's committed file gives (published). The identifiers no record bears
    now go under RETIRED, by record id, last."""
    lay = (doc.get("layouts") or [{}])[0]
    if kept is None:
        kept, retired = published(definitions.key(doc))
    retired = retired or {}
    names = record_names(doc, kept, retired)
    cam, model, fw = definitions.key(doc), lay.get("model", doc.get("model")), lay.get("firmware", "?")
    used = ("imported by sony_camset.ksy" if ids_name(cam) in imported() else
            "no container spec imports it yet (docs/formats/index.md)")
    out = {
        "meta": {"id": ids_id(cam), "title": f"Record ids of a Sony camera settings file, by name: {model} firmware {fw}"},
        "doc": (f"The record ids {model} firmware {fw} (layout "
                f"{lay.get('signature', '?')}) uses, named from editor/definitions/{cam}.json; {used}. "
                "Generated by kit/tools/build_docs.py (kit/tools/camset_ksy.py); edit those, not this file."),
        "enums": {"setting": {rid: {"id": i, "doc": d} for rid, (i, d) in names.items()}},
    }
    gone = retired_after(names, kept, retired)
    if gone:
        out[RETIRED] = dict(sorted(gone.items(), key=lambda x: (x[1], x[0])))
    return out


def format_spec() -> dict:
    """The hand-written format (docs/formats/sony_camset.ksy) as data."""
    return yaml.safe_load(FORMAT.read_text(encoding="utf-8"))


def width(spec: dict, f: dict) -> int:
    """How many bytes a fixed-size field of the format takes: its contents, its size, an integer, or a type of
    the format's own (the header's firmware version)."""
    if "contents" in f:
        return len(f["contents"])
    if "size" in f:
        return f["size"]
    ints = {"u1": 1, "s1": 1, "u2": 2, "s2": 2, "u2be": 2, "u4": 4, "s4": 4, "u8": 8, "s8": 8}
    return ints.get(f["type"]) or sum(width(spec, x) for x in spec["types"][f["type"]]["seq"])


def render(doc, kept: dict | None = None, retired: dict | None = None) -> str:
    """The .ksy file's text (kit/tools/build_docs.py writes it, and its test compares it with the committed file);
    `kept` and `retired` as ksy's."""
    spec = ksy(doc, kept, retired)
    gone = spec.pop(RETIRED, None)
    text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=110)
    # hex record ids read better than YAML's decimal keys and values
    text = re.sub(r"^(    )(\d+):$", lambda m: f"{m.group(1)}0x{int(m.group(2)):04x}:", text, flags=re.M)
    if gone:
        text += f"{RETIRED}:\n" + "".join(f"  {i}: 0x{rid:04x}\n" for i, rid in gone.items())
    return (f"# Generated by kit/tools/build_docs.py (kit/tools/camset_ksy.py) from editor/definitions/"
            f"{definitions.key(doc)}.json; edit those, not this file.\n" + text)


def main():
    argparse.ArgumentParser(description="Write docs/formats/sony_camset_ids_<model>_fw<fw>.ksy of every definition.").parse_args()
    for _, doc in definitions.every(evidence=False):
        out = ids_path(definitions.key(doc))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(doc), encoding="utf-8", newline="\n")
        print(f"wrote {out.relative_to(ROOT).as_posix()}: {len(ksy(doc)['enums']['setting'])} record ids named")


if __name__ == "__main__":
    main()
