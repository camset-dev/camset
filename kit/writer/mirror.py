"""The memories' live copy (camera.mirrors[0] in the camera file): one block per memory set in a live record, each
set's own copy of it. A field of the live copy is global:0x<live_record>@<offset>; these turn it into (memory set,
offset) and back, and name the fields after the memories."""
import re


def mirror_of(doc) -> dict:
    """The definition's first mirror (camera.mirrors[0], from the camera file): the live record holding one block per
    memory set, and each set's own copy of it; {} without one, or without its element_bytes, which the kit needs."""
    m = ((doc.get("camera") or {}).get("mirrors") or [{}])[0]
    return m if m.get("element_bytes") else {}


def mirror_place(key: str, mirror: dict) -> tuple:
    """(memory set, offset in its block) of a field of the live copy, global:0x<live_record>@n; (None, None)
    otherwise."""
    m = re.fullmatch(rf"global:0x{mirror['live_record']:04x}@(\d+)", key) if mirror else None
    n = mirror.get("element_bytes") if mirror else None
    return (int(m[1]) // n + mirror["first_section"], int(m[1]) % n) if m else (None, None)


def mirror_key(mirror: dict, section: int, off: int) -> str:
    """The live copy's key of a memory set's field: the inverse of mirror_place."""
    return f"global:0x{mirror['live_record']:04x}@{mirror['element_bytes'] * (section - mirror['first_section']) + off}"


def mirror_names(doc) -> int:
    """The live copy's fields under the memories' own names ("Movie Memory 1: Aperture (F-number)"); the first
    kit called sets 4-12 "Set 4" ... "Set 12" (2026-11-03)."""
    names, n = (doc["camera"].get("memory_sets") or {}).get("names") or {}, 0
    mirror = mirror_of(doc)
    for st in doc["settings"]:
        mset, _ = mirror_place(st["key"], mirror)
        if mset and str(mset) in names and ": " in st["name"]:
            name = f"{names[str(mset)]}: {st['name'].split(': ', 1)[1]}"
            n += name != st["name"]
            st["name"] = name
    return n
