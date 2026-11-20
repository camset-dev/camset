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
record holds that one. A name someone's parser uses must never come to mean another record, so the file is its own
memory (record_names, published): a record keeps the identifier the file gives it while the name of one of its
settings still gives that identifier (base, or base with its id: a live setting found on a memory set's record leaves
the set's name with it), and no record takes an identifier the file gives another. A new record whose
name another record already bears takes its id ("jpeg_heif_quality_01de" beside the Slot 1 record's
"jpeg_heif_quality"); a record renamed takes its new name's identifier, the old one gone with the name it said. Until
2026-11-19 the names were dealt out afresh in record order at every write, so a new record with a lower id took a name
another record had borne (b3afe42: 0x01de took jpeg_heif_quality from 0x01ea).
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


def published(camera: str) -> dict:
    """{record id: identifier} the camera's committed record names file gives (ids_path), {} with none: the memory
    record_names keeps each identifier with its record by."""
    p = ids_path(camera)
    if not p.exists():
        return {}
    spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    values = ((spec.get("enums") or {}).get("setting") or {}) if isinstance(spec, dict) else {}
    return {rid: e["id"] for rid, e in values.items()
            if isinstance(rid, int) and isinstance(e, dict) and isinstance(e.get("id"), str)}


def record_names(doc, kept: dict | None = None) -> dict:
    """{record id: (identifier, doc line)} from the schema, live keys before memory-set ones. `kept`, the identifiers
    the committed file gives (published): a record keeps its own while the name of one of its settings still gives it
    (base, or base with its id: a live setting found on a memory set's record leaves the set's name with it), and none
    takes one the file gives another record; every other record, in record order, takes its first setting's name's
    (ident)."""
    kept = kept or {}
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
    # what the file gives a record stays its own while one of its settings' names gives it; every identifier the file
    # holds is taken
    stays = {}
    for rid in sorted(first):
        mine = kept.get(rid)
        given = {x for s in every[rid] for b in [base(name_of(rid, s))] for x in (b, f"{b}_{rid:04x}")}
        if mine in given and mine not in stays.values():
            stays[rid] = mine
    out, used = {}, set(kept.values())
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


def ksy(doc, kept: dict | None = None) -> dict:
    """The record names file of a definition as data; `kept` the identifiers to keep with their records (record_names),
    by default the ones the camera's committed file gives (published)."""
    lay = (doc.get("layouts") or [{}])[0]
    names = record_names(doc, published(definitions.key(doc)) if kept is None else kept)
    cam, model, fw = definitions.key(doc), lay.get("model", doc.get("model")), lay.get("firmware", "?")
    used = ("imported by sony_camset.ksy" if ids_name(cam) in imported() else
            "no container spec imports it yet (docs/formats/index.md)")
    return {
        "meta": {"id": ids_id(cam), "title": f"Record ids of a Sony camera settings file, by name: {model} firmware {fw}"},
        "doc": (f"The record ids {model} firmware {fw} (layout "
                f"{lay.get('signature', '?')}) uses, named from editor/definitions/{cam}.json; {used}. "
                "Generated by kit/tools/build_docs.py (kit/tools/camset_ksy.py); edit those, not this file."),
        "enums": {"setting": {rid: {"id": i, "doc": d} for rid, (i, d) in names.items()}},
    }


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


def render(doc, kept: dict | None = None) -> str:
    """The .ksy file's text (kit/tools/build_docs.py writes it, and its test compares it with the committed file);
    `kept` as ksy's."""
    text = yaml.safe_dump(ksy(doc, kept), sort_keys=False, allow_unicode=True, width=110)
    # hex record ids read better than YAML's decimal keys
    text = re.sub(r"^(    )(\d+):$", lambda m: f"{m.group(1)}0x{int(m.group(2)):04x}:", text, flags=re.M)
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
