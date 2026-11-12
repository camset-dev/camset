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
"""
import argparse
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


def ident(name: str, used: set, rid: int) -> str:
    """A Kaitai identifier (lower case, digits, underscores, a letter first), unique in the enum."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "record"
    if not s[0].isalpha():
        s = "r_" + s
    s = s[:60].rstrip("_")
    if s in used:
        s = f"{s}_{rid:04x}"
    used.add(s)
    return s


def record_names(doc) -> dict:
    """{record id: (identifier, doc line)} from the schema, live keys before memory-set ones."""
    first = {}
    for s in doc["settings"]:
        m = re.match(r"(global|set):0x([0-9a-f]+)(\[\d+\]|@\d+)?$", s["key"])
        if not m:
            continue
        rid = int(m.group(2), 16)
        if rid in first and (first[rid][0] == "global" or m.group(1) == "set"):
            first[rid][2].append(s)
            continue
        first[rid] = (m.group(1), s, [s])
    out, used = {}, set()
    for rid in sorted(first):
        area, s, all_ = first[rid]
        proved = sum(1 for x in all_ if x.get("proved"))
        name = re.sub(r"\s*\(.*?\)\s*$", "", s.get("name") or "") or f"record {rid:04x}"
        if s["key"].endswith("]") or "@" in s["key"]:
            name = f"{name} (array)" if s["key"].endswith("]") else f"{name} (block)"
        vals = s.get("values") or []
        line = f"{s.get('name')}" + (f" [{s.get('tab')} > {s.get('group')}]" if s.get("tab") else "")
        if 0 < len(vals) <= 8 and not s["key"].endswith("]"):
            line += ": " + ", ".join(f"{v} {lab}" for v, lab in vals)
        line += f". {'memory sets' if area == 'set' else 'live settings'}; {proved} of {len(all_)} settings on it proved on the camera."
        out[rid] = (ident(name, used, rid), line)
    return out


def ksy(doc) -> dict:
    lay = (doc.get("layouts") or [{}])[0]
    names = record_names(doc)
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


def render(doc) -> str:
    """The .ksy file's text (kit/tools/build_docs.py writes it, and its test compares it with the committed file)."""
    text = yaml.safe_dump(ksy(doc), sort_keys=False, allow_unicode=True, width=110)
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
