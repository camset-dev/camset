"""Build a definition's sample file from a file the camera wrote right after Initialize, with the personal text removed.

    .venv/bin/python kit/tools/make_sample.py SRC.DAT [--out editor/definitions/<model>_fw<fw>.DAT] [--dry-run]
    .venv/bin/python kit/tools/make_sample.py SRC.DAT --take "Picture Profile PP" \\
        --from runs/<model>_fw<fw>/kit2_pp_reset_stills/pp_reset.json \\
        --from runs/<model>_fw<fw>/kit2_pp_reset_movie/pp_reset.json [--allow-unchanged] [--allow-no-notice] [--dry-run]

SRC is a file this body wrote right after Initialize, never the owner's own file: zeroing the text below does not
remove the settings an owner chose, and those never reach a public file (decision 16). Initialize does not put every
record back: on the ILCE-1M2 many records hold after it what they held before. Of those, only the Picture Profile
parameters are checked so far (the reset file lists what Initialize puts back for the settings tested): --take
"Picture Profile PP" --from RESULT takes their values after each offered profile's own Reset, in Stills and in Movie
(kit/provers/pp_reset_run.py), checking each result against its own downloads (below). Profiles the body keeps records
for but no menu offers (PP7-PP9 on the ILCE-1M2) cannot be reset by a menu and keep what the base held: a limit of the
sample. In the other records Initialize leaves, the sample holds what that body held then; it is a file the camera
wrote, not a list of factory values. The ILCE-1M2's sample is made from a download taken right after Initialize. The
sample goes beside the definition of the
file's model and firmware (editor/definitions/<model>_fw<fw>.DAT), which names it in its camera section ("sample",
from data/<model>_fw<fw>/camera_<model>_fw<fw>.json): the editor's Explore a sample opens it, the docs' memory map
reads it, and kit/tools/check_public.py lets that file alone be published.
Zeroed: every record whose value is printable text of 4+ characters (owner, copyright, network names, device names),
and the records the camera's own file lists in "personal_records" (data/<model>_fw<fw>/camera_<model>_fw<fw>.json,
schemas/camera.schema.json), every record that changes when the owner's own things change, text or not (the text
check misses a name packed against other bytes): "zeroed", records zeroed whole (the ILCE-1M2's registered lens list:
names, serials, per-lens data); "defaults", records set to the camera's own default (the ILCE-1M2's file-name prefix,
3 letters an owner chooses, often initials, set to DSC); "not_text", records of numbers never read for text between
NULs; "keep_text", the camera's own words kept. Records are named "0x167c", as the record keys and
kit/tools/upload_check.py --diff write them. Those are each body's own record ids, so before anything is written the
tool stops on a camera file without the key (saying what to add and how to find it: missing_words), on a key not
shaped as the schema says or naming a record twice (personal_rules), and on a record the file given does not hold or a
default of another length than its record (personal_problems); a list naming no record to zero or set back is said
(empty_note). kit/tools/check_public.py checks a published sample by the same key. A zeroed text is printed by its
length alone. The save time becomes 20260101_000000. Both checksums are recomputed at the file's container block's
sites (camkit.camset).

--take FAMILY --from RESULT (2026-11-11, made strict the same day): the records Initialize leaves, taken from files
the same camera wrote after the camera's own reset of them, so the sample holds the reset values, never the owner's.
It can publish nothing but reset values:
- FAMILY is one family of the definition (camera.families, by its prefix or title: "Picture Profile PP"), never a
  record id or a memory set's key. Its records hold one element per profile (a setting's group names the profile,
  "Picture Profile PP7", its index the element: on the ILCE-1M2, 25 parameters kept three times, in use, "(stills)"
  and "(movie)" by copy_for, each a record of 11 elements, PP1-PP11 at elements 0-10).
- RESULT is only kit/provers/pp_reset_run.py's pp_reset.json, checked by check_result. What is recomputed from the
  run's own downloads: every list of changed keys the result holds (each profile's "changed" and "family_changed",
  the control's "changed" and "reset_wrote" and their copies' counts, the verify pass's "family_changed" and
  "others_changed"), each compared with what the result says, the first difference named by key; the positive
  control, element by element by the family's layout (the change moved at least one of the family's records, only
  the control profile's element in each, among them a record in use and the copy of the run's mode, and the first
  profile's Reset wrote that element of every one of them back: the result's "ok" must agree); the verify pass moving
  none; the order of the downloads, by the camera's downloads manifest (camkit.provenance, downloads.jsonl): among its
  entries under the result's own folder, exactly the consecutive ones from the start file through verify (start,
  control-set, each profile's reset-<profile> in the result's order, verify; no _after, no second _before between;
  start the nearest _before before control-set), each a download of this camera's by its path and SHA-256; the last
  download of the base's model, firmware and records, saved in the mode the result says (camera.live_mode). What is
  taken as the run wrote it, checked only to be there and consistent: "finished", "verified", "peek", "asked" (null:
  a --profiles run never feeds the sample), "need_both_readers" (true), "family", "mode", the profiles reset (none
  twice, the first the control's) and "offered_profiles" (the reset ones; across a Stills and a Movie result the same
  set; and the recorded menu walk's list for that mode when the camera's menu tree is here); "complete", the camera's
  completion notice per profile (--allow-no-notice for a body that shows none); "readers", per profile, the title and
  the question before its Reset judged by both readers; "verify"."entered", each profile's panel confirmed as its
  own (its title read by both readers) in the verify pass; "last", "control"."reset_download" and the downloads'
  names, which must point at the files above inside the result's folder. downloads.jsonl itself is trusted as it is
  for uploads (Link.upload): it is the kit's own record of what the camera wrote. One Stills result and one Movie
  result: the in-use and stills records come from the Stills run, the movie records from the Movie run; one result
  alone only when it shows its resets write the other mode's copy too (writes_all).
- When no reset download holds any of the family's records unlike its run's start file, make_sample stops;
  --allow-unchanged takes the records then, the run's control being what shows a Reset writes them (one parameter of
  one profile). The control shows it for one parameter of one profile; for the rest the evidence is the camera's own
  completion notice.
- Each record is the base's with the element of every profile its run reset taken from that run's last reset
  download; a record both runs changed must hold the same bytes for the profiles both reset, else the tool stops.
  Profiles no run reset (profiles with elements on no menu) keep the base's bytes, and the tool says which. A record
  whose bytes no reset download holds unlike the run's start file is taken the same way (the case of a record already
  at its reset value, or one Reset does not write) and listed by id with the count (the whole family so: the bullet
  above). The composed records in use must equal the copy of the base's own mode, as the
  camera keeps them.
- The memory sets' copies of the taken records (in_sets) take the taken live bytes, but only when the base file holds
  each copy equal to its live record (the a1 II's file after Initialize does); otherwise the tool stops. The memory
  sets of a RESULT's download are never taken (they hold the owner's own registrations).
The tool prints, ids and profile names only, what came from which run and what was left. The file is written beside
its place and moved over it in one step; --dry-run prints everything and writes nothing.
"""
import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PureWindowsPath
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, match, paths, provenance, safety  # noqa: E402

DEFAULT_STAMP = "20260101_000000"
KEY = re.compile(r"(?:(global|set(\d+)):)?0x([0-9a-f]{1,4})", re.I)
MODES = ("Stills", "Movie")                      # the modes a reset run is made in (kit/provers/pp_reset_run.py)
# the camera file's key that names the body's records holding an owner's own data, text or not
# (schemas/camera.schema.json): each body's own record ids, never another body's
PERSONAL = "personal_records"
# a record id as a record key writes it and kit/tools/upload_check.py --diff prints it after "global:" or "setN:": the
# one form personal_records takes, and the form every message of make_sample and check_public names a record by
RECORD_ID = re.compile(r"0x[0-9a-f]{4}")          # whole (fullmatch): no newline after it
HEX_BYTES = re.compile(r"(?:[0-9a-f]{2})+")


def rid_text(rid: int) -> str:
    """A record id as personal_records and the record keys write it ("0x167c")."""
    return f"0x{rid:04x}"


class Personal(NamedTuple):
    """A camera's "personal_records", as the sample is scrubbed by them. Each record id holds in whichever section it is
    in."""
    zeroed: dict           # {record id: what it holds}: zeroed whole (the ILCE-1M2's registered lens list)
    defaults: dict         # {record id: (bytes, what it holds)}: set to the camera's own default (the ILCE-1M2's
                           # file-name prefix, DSC)
    not_text: frozenset    # record ids never read for pieces of text between NULs: numbers (memory exposure blocks)
    keep_text: frozenset   # text a record may hold and keep: the camera's own word, not an owner's (DSC)

    def protects(self) -> bool:
        """Whether the list names any record to zero or set back: an empty one leaves only the text check."""
        return bool(self.zeroed or self.defaults)


SHAPES = {"zeroed": ("records",), "defaults": ("record", "bytes"), "not_text": ("records",)}


def personal_rules(camera: dict) -> Personal | None:
    """The camera's facts' (its camera file's, or a definition's camera section) "personal_records", or None when they
    have none. ValueError, in words naming the entry or the record, for one not shaped as schemas/camera.schema.json
    says (as strict as the schema: no other key, no empty list of records), and for a record listed twice, in one
    group or two: each record has one place."""
    pr = (camera or {}).get(PERSONAL)
    if pr is None:
        return None
    if not isinstance(pr, dict) or set(pr) - {*SHAPES, "keep_text"}:
        raise ValueError(f"\"{PERSONAL}\" is an object of \"zeroed\", \"defaults\", \"not_text\" and \"keep_text\", "
                         "nothing else")
    seen = {}

    def rid(x, group: str) -> int:
        if not isinstance(x, str) or not RECORD_ID.fullmatch(x):
            raise ValueError(f"\"{PERSONAL}\".{group}: {json.dumps(x)} is not a record id as the record keys write it: "
                             "\"0x\" and four lower-case hex digits, as kit/tools/upload_check.py --diff prints it after "
                             "\"global:\" (\"0x167c\")")
        n = int(x, 16)
        if n in seen:
            twice = f"in {group} twice" if seen[n] == group else f"in {seen[n]} and in {group}"
            raise ValueError(f"\"{PERSONAL}\" lists {x} {twice}: each record goes in one place")
        seen[n] = group
        return n

    def entries(group: str) -> list:
        need = SHAPES[group]
        shape = ", ".join(f"\"{k}\"" for k in need)
        g = pr.get(group, [])
        if not isinstance(g, list):
            raise ValueError(f"\"{PERSONAL}\".{group} is a list of entries, each {{{shape} and maybe \"what\"}}")
        for i, e in enumerate(g):
            if not isinstance(e, dict) or set(need) - set(e) or set(e) - {*need, "what"} \
                    or not isinstance(e.get("what", ""), str):
                raise ValueError(f"\"{PERSONAL}\".{group}, entry {i + 1}: each holds {shape} and maybe \"what\" (a "
                                 "text), nothing else")
            if "records" in need and (not isinstance(e["records"], list) or not e["records"]):
                raise ValueError(f"\"{PERSONAL}\".{group}, entry {i + 1}: \"records\" is a list of one record id or "
                                 "more")
        return g
    zeroed = {rid(r, "zeroed"): e.get("what", "") for e in entries("zeroed") for r in e["records"]}
    defaults = {}
    for i, e in enumerate(entries("defaults")):
        b = e["bytes"]
        if not isinstance(b, str) or not HEX_BYTES.fullmatch(b):
            raise ValueError(f"\"{PERSONAL}\".defaults, entry {i + 1}: \"bytes\" is the default's whole bytes as "
                             "lower-case hex (\"44534300\")")
        defaults[rid(e["record"], "defaults")] = (bytes.fromhex(b), e.get("what", ""))
    not_text = frozenset(rid(r, "not_text") for e in entries("not_text") for r in e["records"])
    keep = pr.get("keep_text", [])
    if not isinstance(keep, list) or not all(isinstance(t, str) and t for t in keep):
        raise ValueError(f"\"{PERSONAL}\".keep_text is a list of texts, none empty")
    return Personal(zeroed, defaults, not_text, frozenset(keep))


def personal_problems(rules: Personal, cs, where: str) -> list:
    """What in a camera's personal records does not fit the file `cs` (`where` names it), each in words naming the
    record: a record no section of the file holds (a typo, or a decimal number written after "0x": it would protect
    nothing), and a default whose length is not the record's (it could never be set)."""
    held = set().union(*(set(sec) for sec in cs.sections))
    out = [f"{rid_text(r)} ({group}) is a record no section of {where} holds: a typo, or a decimal number written "
           "after \"0x\"? Take it from the keys kit/tools/upload_check.py --diff prints"
           for group, ids in (("zeroed", rules.zeroed), ("defaults", rules.defaults), ("not_text", rules.not_text))
           for r in sorted(ids) if r not in held]
    for r, (b, _what) in sorted(rules.defaults.items()):
        for si, sec in enumerate(cs.sections):
            got = sec.get(r)
            if got is not None and len(got.raw) != len(b):
                out.append(f"{rid_text(r)} (defaults): its default is {len(b)} bytes, and the record in section {si} of "
                           f"{where} holds {len(got.raw)}: give the record's whole bytes")
    return out


def empty_note(where: str) -> str:
    """What is said of a sample made or checked by a list that names no record to zero or set back."""
    return (f"{where}'s \"{PERSONAL}\" names no record to zero or set back, so only the records whose value reads as "
            "text are zeroed: right only for a body on which the owner's own things were tried (a lens registered, a "
            "file-name prefix set) and changed no other record (docs/DATA_CONTRACTS.md, \"Records that hold an "
            "owner's own data\")")


def missing_words(where: str, model: str) -> str:
    """Why a sample of this camera is not made (make_sample) or not shown clean (check_public): its camera file at
    `where` says nothing of its personal records; what to add, and how to find them on the body."""
    return (f"{where} has no \"{PERSONAL}\", so which of the {model}'s records hold an owner's own data is not known. "
            "The sample is published: the kit zeroes every record whose value reads as text, and the records that key "
            "lists, each body's own. Every record that changes when the owner's own things change goes in, text or "
            "not, as the text check misses a name packed against other bytes (on the ILCE-1M2: Preset Focus/Zoom's "
            "registered lens list, each lens's name, serial number and data, and the file-name prefix). Find this "
            "body's: download; ask the owner to change one such thing on the camera by their own hand (register a "
            "lens to a preset slot they do not use, set File Name's prefix); download again and compare "
            "(kit/tools/upload_check.py --diff REF TAG lists the records that differ by key; the bytes it prints are "
            "the owner's: copy them nowhere). List each record that changed, by its key's id (\"0x167c\"), as "
            f"\"{PERSONAL}\" (docs/DATA_CONTRACTS.md, \"Records that hold an owner's own data\"; the ILCE-1M2's camera "
            "file is the pattern); a record with a camera default goes under \"defaults\", its bytes read from the "
            "file the camera wrote right after Initialize (the one make_sample is given), never from the owner's "
            "working file, as they go into the sample. Then make the sample again with kit/tools/make_sample.py")


def camera_rules(cs) -> Personal:
    """The personal records of the camera that wrote `cs`, from its own camera file (data/<model>_fw<fw>/
    camera_<model>_fw<fw>.json), checked against `cs` (personal_problems); exits, saying what to add or correct and how,
    when that file or its key is not there, or the key is not shaped right or does not fit the file. Says so when the
    list names no record to zero or set back (empty_note)."""
    key = paths.key(cs.model, cs.firmware)
    f = definitions.camera_file(key)
    if not f.exists():
        sys.exit(f"make_sample: nothing written: the {cs.model} firmware {cs.firmware} has no camera file "
                 f"({paths.shown(f)}), so which of its records hold an owner's own data is not known. Start its data/ "
                 f"folder first (docs/REMAPPING_PLAYBOOK.md, section 16), with \"{PERSONAL}\" in it")
    try:
        rules = personal_rules(json.loads(f.read_text(encoding="utf-8")))
    except ValueError as e:
        sys.exit(f"make_sample: nothing written: {paths.shown(f)}: {e}")
    if rules is None:
        sys.exit("make_sample: nothing written: " + missing_words(paths.shown(f), cs.model))
    bad = personal_problems(rules, cs, "the file given")
    if bad:
        sys.exit(f"make_sample: nothing written: {paths.shown(f)}'s \"{PERSONAL}\": " + "; ".join(bad))
    if not rules.protects():
        print("note: " + empty_note(paths.shown(f)))
    return rules


def personal(rid: int, raw: bytes, rules: Personal) -> str:
    """Why a record is zeroed: what its personal records say it holds (a record they list), or the text it holds (to
    be counted, never shown); "" when it is kept."""
    text = raw.rstrip(b"\0")
    if rid in rules.zeroed:
        return rules.zeroed[rid] or "personal record"
    if len(text) >= 4 and len(raw) > 4 and all(32 <= b < 127 for b in text) and text.decode("ascii").strip() not in rules.keep_text:
        return text.decode("ascii")
    if b"\0" in raw and rid not in rules.not_text:
        for chunk in raw.split(b"\0"):
            if len(chunk) >= 4 and all(32 <= b < 127 for b in chunk) and chunk.decode("ascii").strip() not in rules.keep_text:
                return chunk.decode("ascii")
    return ""


def shown_why(rid: int, why: str, rules: Personal) -> str:
    """A zeroed record's reason as make_sample and check_public print it: a listed record by what it holds, a text by
    its length alone (a pull request's check log is public)."""
    return why if rid in rules.zeroed else f"text, {len(why)} characters"


def default_due(rid: int, raw: bytes, rules: Personal) -> bytes | None:
    """The camera's default a record is set to (its personal records' "defaults"), when it holds another value
    (personal_problems has refused a default of another length); None otherwise."""
    d = rules.defaults.get(rid)
    return d[0] if d is not None and raw != d[0] and len(raw) == len(d[0]) else None


# ---------------------------------------------------------------- --take: which records (the definition)

def _said(x) -> str:
    return " ".join(safety.fold(x or "").casefold().split())


def family_of(doc: dict, name: str) -> dict | None:
    """The definition's family (camera.families) named `name` by its prefix or its title, or None."""
    fams = [f for f in ((doc or {}).get("camera") or {}).get("families") or [] if isinstance(f, dict)]
    fam = next((f for f in fams if _said(name) in {_said(f.get("prefix")), _said(f.get("title"))}), None)
    return fam if fam is not None and fam.get("prefix") else None


def family_ids(doc: dict, name: str) -> list | None:
    """The record ids (the file's first section, "global") of the definition's family named `name` by its prefix or its
    title (camera.families): every setting whose group starts with the family's prefix. None when no family is so
    named."""
    fam = family_of(doc, name)
    if fam is None:
        return None
    return sorted({s["id"] for s in doc.get("settings") or []
                   if s.get("area") == "global" and str(s.get("group") or "").startswith(fam["prefix"])})


def family_names(doc: dict) -> list:
    return [f.get("prefix") for f in ((doc or {}).get("camera") or {}).get("families") or [] if isinstance(f, dict)]


def set_sections(doc: dict, n_sections: int) -> list:
    """The memory sets' sections the definition names (camera.memory_sets), within the file's."""
    names = (((doc or {}).get("camera") or {}).get("memory_sets") or {}).get("names") or {}
    return sorted(int(k) for k in names if str(k).isdigit() and 0 < int(k) < n_sections)


def in_sets_ids(doc: dict) -> set:
    """The ids of the live settings the definition says are copied into each memory set (in_sets)."""
    return {s["id"] for s in (doc or {}).get("settings") or [] if s.get("area") == "global" and s.get("in_sets")}


def file_mode(doc: dict | None, cs) -> str | None:
    """The shooting mode a file was saved in, as the definition's camera.live_mode reads it (its record's first
    element, a mode's number), or None when the definition names no such record or the file holds no such value."""
    lm = ((doc or {}).get("camera") or {}).get("live_mode") or {}
    if not lm.get("key"):
        return None
    try:
        sec, rid = parse_key(str(lm["key"]).split("[")[0])
    except ValueError:
        return None
    r = cs.get(sec, rid) if sec < len(cs.sections) else None
    if r is None or not r.raw:
        return None
    return (lm.get("modes") or {}).get(str(int.from_bytes(r.raw[:r.size], "little")))


COPIES = ("live", "stills", "movie")
COPY_SAID = {"live": "in-use", "stills": "stills", "movie": "movie"}


def copy_class(s: dict) -> str:
    """Which of a parameter's three records a setting is: "live" (the one in use: no copy_for, no copy_of), "stills"
    (copy_for names Stills, its name ends "(stills)") or "movie" (copy_for names Movie, its name ends "(movie)"); exits
    on a setting whose copy_for and name say different things, or neither."""
    cf, name = s.get("copy_for"), str(s.get("name") or "").strip().lower()
    if not cf and not s.get("copy_of"):
        got = "live"
    elif cf and "Stills" in cf and "Movie" not in cf:
        got = "stills"
    elif cf and "Movie" in cf and "Stills" not in cf:
        got = "movie"
    else:
        sys.exit(f"make_sample: {s.get('key')}: its copy_for ({cf}) names no one mode's copy: which reset gives it is "
                 "not known")
    tail = "stills" if name.endswith("(stills)") else "movie" if name.endswith("(movie)") else "live"
    if tail != got:
        sys.exit(f"make_sample: {s.get('key')}: its name says the {tail} record, its copy_for the {got} one: the "
                 "definition does not tell its copies apart; nothing written")
    return got


def family_layout(doc: dict, name: str) -> dict:
    """How the family's records hold the profiles: {"prefix", "records": {id: {"copy": live|stills|movie,
    "copy_for": [...], "live": the live record's id (a copy's), "profiles": {"PP1": element index, ...}}}}. Each
    setting of the family is one profile's element of one record: its group's last word is the profile ("Picture
    Profile PP7": PP7), its index the element. Exits when the family is not there, a group names no profile, or the
    definition says two things of one record or element."""
    fam = family_of(doc, name)
    if fam is None:
        sys.exit(f"make_sample: --take {name!r} is not a family of the definition (its families: "
                 f"{', '.join(repr(x) for x in family_names(doc)) or 'none'}); --take names a family, never record ids")
    recs = {}
    for s in doc.get("settings") or []:
        if s.get("area") != "global" or not str(s.get("group") or "").startswith(fam["prefix"]):
            continue
        prof = str(s["group"]).split()[-1]
        if not safety.PROFILE_NAME.fullmatch(prof) or not isinstance(s.get("index"), int):
            sys.exit(f"make_sample: {s.get('key')}: its group {s['group']!r} names no profile (PP and a number) and "
                     "element: --take takes a family whose records hold one element per profile")
        copy = copy_class(s)
        live = None
        if copy != "live":
            m = KEY.search(str(s.get("copy_of") or ""))
            live = int(m.group(3), 16) if m else None
            if live is None:
                sys.exit(f"make_sample: {s.get('key')}: a copy that names no live record (copy_of)")
        r = recs.setdefault(s["id"], {"copy": copy, "copy_for": s.get("copy_for") or [], "live": live, "profiles": {}})
        if (r["copy"], r["live"]) != (copy, live) or r["profiles"].get(prof, s["index"]) != s["index"] \
                or (prof not in r["profiles"] and s["index"] in r["profiles"].values()):
            sys.exit(f"make_sample: the definition says two things of {hexid(s['id'])} ({s.get('key')}): nothing "
                     "written")
        r["profiles"][prof] = s["index"]
    if not recs:
        sys.exit(f"make_sample: --take {name!r}: the definition's family holds no record")
    return {"prefix": fam["prefix"], "records": recs}


def hexid(rid: int) -> str:
    return f"0x{rid:04x}"


def keyname(key: tuple) -> str:
    return camset.Change(key[0], key[1], None, None).key


def parse_key(k: str) -> tuple:
    m = KEY.fullmatch(str(k))
    if not m:
        raise ValueError(f"not a record key: {k!r}")
    return (int(m.group(2)) if m.group(2) else 0, int(m.group(3), 16))


# ---------------------------------------------------------------- --from: the reset runs' results

class Source:
    def __init__(self, given: Path, dat: Path, cs, changed: set, mode: str, reset: list, offered: list):
        self.given, self.dat, self.cs, self.changed = given, dat, cs, changed
        self.mode, self.reset, self.offered = mode, reset, offered


def same_layout(base, cs, name: str) -> str:
    """Why `cs` is not a file of the base's camera with the base's records, or "": model, firmware, the sections, and
    each record's id, element size and count."""
    if (cs.model, cs.firmware) != (base.model, base.firmware):
        return f"{name} is a {cs.model} firmware {cs.firmware} file, the base a {base.model} firmware {base.firmware} one"
    if len(cs.sections) != len(base.sections):
        return f"{name} has {len(cs.sections)} sections, the base {len(base.sections)}"
    for s, (a, b) in enumerate(zip(base.sections, cs.sections, strict=True)):
        if a.keys() != b.keys():
            return f"{name}: section {s} holds other records than the base's ({len(b)} against {len(a)})"
        for rid, r in a.items():
            if (b[rid].size, b[rid].count) != (r.size, r.count):
                return (f"{name}: {keyname((s, rid))} is {b[rid].count} x {b[rid].size} bytes, the base's "
                        f"{r.count} x {r.size}")
    return ""


COPY_COUNT = {"live": "in_use", "stills": "stills", "movie": "movie"}


def copies_of(keys, copy_by_id: dict | None) -> dict | None:
    """How many of `keys` (record keys, "global:0x04e9") are a parameter's in-use record, its "(stills)" copy and its
    "(movie)" copy, by the definition (copy_by_id: {id: live|stills|movie}, family_layout's "copy"); a key no record
    of the family names is left out. None when the definition's family is not known."""
    if copy_by_id is None:
        return None
    out = dict.fromkeys(COPY_COUNT.values(), 0)
    for k in keys:
        try:
            sec, rid = parse_key(k)
        except ValueError:
            continue
        if sec == 0 and rid in copy_by_id:
            out[COPY_COUNT[copy_by_id[rid]]] += 1
    return out


def changed_of(a, b) -> list:
    """The record keys whose bytes differ between two files (camset.diff, the volatile records left out): as
    kit/provers/pp_reset_run.py's changed_keys computes them."""
    return [c.key for c in camset.diff(a, b)]


def family_keys(keys, ids: set) -> list:
    """The keys of the family's records (the file's first section) among `keys`, as pp_reset_run.split takes them."""
    return [k for k in keys if k.startswith("global:") and int(k.split(":0x")[1], 16) in ids]


def only_element(a: bytes, b: bytes, i: int, size: int) -> bool:
    """Whether two versions of a record differ in element `i` (of `size` bytes) and nowhere else."""
    lo, hi = i * size, (i + 1) * size
    return len(a) == len(b) and a[lo:hi] != b[lo:hi] and a[:lo] == b[:lo] and a[hi:] == b[hi:]


def control_change_of(start, control, layout: dict, profile: str, mode: str) -> dict:
    """What the control's change did, element by element (the family's layout: each record one element per profile):
    "changed", the family's records that differ between the start file and control-set; "others", those of them in
    which anything but `profile`'s element moved (another profile's element, or a record that holds none for it): a
    control moves one parameter of one profile; "missing", the copies the change must reach and did not: the record in
    use and the copy of the run's `mode` ("in-use", "stills" or "movie")."""
    recs = layout["records"]
    changed = family_keys(changed_of(start, control), set(recs))
    others = []
    for k in changed:
        rid = parse_key(k)[1]
        i, a, b = recs[rid]["profiles"].get(profile), start.get(0, rid), control.get(0, rid)
        if i is None or not only_element(a.raw, b.raw, i, a.size):
            others.append(k)
    got = {recs[parse_key(k)[1]]["copy"] for k in changed}
    mine = "stills" if mode == "Stills" else "movie"
    missing = [COPY_SAID[c] for c in ("live", mine) if c not in got]
    return {"changed": changed, "others": others, "missing": missing}


def control_wrote(control, first_reset, layout: dict, profile: str, changed) -> list:
    """Those of the control's changed records (keys) whose `profile` element differs between control-set and the
    first reset's download: the records that profile's Reset wrote back, element by element (another profile's
    element moving is not that profile's Reset writing)."""
    recs, out = layout["records"], []
    for k in changed:
        rid = parse_key(k)[1]
        i, b, c = recs.get(rid, {}).get("profiles", {}).get(profile), control.get(0, rid), first_reset.get(0, rid)
        if i is not None and element(b.raw, i, b.size) != element(c.raw, i, c.size):
            out.append(k)
    return out


def control_of(start, control, first_reset, layout: dict, profile: str, mode: str) -> dict:
    """The positive control computed from its downloads, element by element: "changed", the family's records the
    control's change moved (start to control-set); "others" and "missing" (control_change_of); "reset_wrote", those of
    them whose `profile` element the first profile's Reset wrote (control_wrote); their copies' counts; "ok" when the
    change moved at least one record, only `profile`'s element in each, an in-use record and the mode's copy among
    them, and the Reset wrote every one."""
    got = control_change_of(start, control, layout, profile, mode)
    copy_by_id = {rid: r["copy"] for rid, r in layout["records"].items()}
    wrote = control_wrote(control, first_reset, layout, profile, got["changed"])
    return {**got, "copies_changed": copies_of(got["changed"], copy_by_id), "reset_wrote": wrote,
            "copies_reset_wrote": copies_of(wrote, copy_by_id),
            "ok": bool(got["changed"]) and not got["others"] and not got["missing"] and wrote == got["changed"]}


def control_refusal(got: dict, profile: str, mode: str) -> str:
    """Why the control computed from the downloads (control_of) does not hold, in plain words, or ""."""
    if not got["changed"]:
        return "the control's change moved none of the family's records"
    if got["others"]:
        return (f"the control's change moved more than {profile}'s element of {got['others'][0]} (another profile's "
                f"element, or a record that holds none for {profile}; {len(got['others'])} records so): a control "
                "moves one parameter of one profile")
    if got["missing"]:
        return (f"the control's change moved no {' and no '.join(got['missing'])} record (a {mode} run's control "
                f"moves the record in use and the {mode.lower()} copy)")
    if got["reset_wrote"] != got["changed"]:
        return (f"{profile}'s Reset left {len(got['changed']) - len(got['reset_wrote'])} of the "
                f"{len(got['changed'])} records the control changed as the control set them ({profile}'s element)")
    return ""


PP_ROW = "Picture Profile"                       # the menu row whose carousel offers the profiles (pp_reset_run)


def menu_tree_options(tree: dict, mode: str, row: str = PP_ROW) -> list | None:
    """The options the camera's menu tree (kit/tools/menu_tree.py) records for `row` in `mode`'s menu (Stills: the
    tree's own tabs; another mode: its entry in "modes"), or None when it records none."""
    if not isinstance(tree, dict):
        return None
    tabs = tree.get("tabs") if mode == "Stills" else next(
        (m.get("tabs") for m in tree.get("modes") or [] if isinstance(m, dict) and m.get("mode") == mode), None)
    found = []

    def walk(x):
        if isinstance(x, dict):
            if match.key(str(x.get("label") or "")) == match.key(row) and x.get("options"):
                found.append(x["options"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(tabs)
    return found[0] if found else None


def profiles_in(labels) -> list:
    """The profiles (PP and a number) a list of option labels names, each once, in their number's order."""
    got = {n for k, n in (safety.profile_label_kind(x) for x in labels or []) if k == "profile"}
    return sorted(got, key=lambda p: int(p[2:]))


def recorded_profiles(camera: str, mode: str) -> list | None:
    """The profiles the camera's recorded menu walk (its menu tree, private evidence) lists on the Picture Profile row
    in `mode`'s menu, or None when no tree is here or it records none."""
    try:
        f = Path(definitions.menu_tree_file(camera))
        tree = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except (OSError, ValueError):
        return None
    opts = menu_tree_options(tree, mode)
    return None if opts is None else profiles_in(opts)


def _manifest_place(path: Path, root: Path) -> str:
    """A file as the downloads manifest keeps it (camkit.provenance): relative to the camera's run root when inside
    it, else absolute."""
    p = Path(path).resolve()
    try:
        return p.relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def first_difference(what: str, said, computed) -> str:
    """"" when the result's list says what its downloads do, else the first key that differs, named (no value)."""
    if said is None or not isinstance(said, (list, dict)):
        return f"{what}: the result holds no such list"
    if isinstance(computed, dict) or isinstance(said, dict):
        if said != computed:
            k = next((k for k in sorted(set(said) | set(computed or {})) if said.get(k) != (computed or {}).get(k)),
                     None)
            return f"{what}: the result's count {k!r} is not the one its downloads give"
        return ""
    a, b = {str(x) for x in said}, set(computed)
    if a == b and len(said) == len(computed):
        return ""
    extra, missing = sorted(a - b), sorted(b - a)
    if extra:
        return f"{what}: the result names {extra[0]}, which its downloads do not show changing"
    if missing:
        return f"{what}: its downloads show {missing[0]} changing, which the result does not name"
    return f"{what}: the result names a key twice"


def one_session(files: list, folder: Path, root: Path) -> str:
    """Why the result's downloads (start, control-set, the resets, verify) are not one session's, or "": in the
    camera's downloads manifest, among the entries under the result's own folder, they must be exactly the consecutive
    entries from start through verify, each by its path and SHA-256 (nothing between them: no _after, no second
    _before), start being the nearest _before entry before control-set. Two sessions' downloads in one folder are
    never spliced into one result."""
    folder = Path(folder).resolve()
    places = [_manifest_place(f, root) for f in files]
    digests = [provenance.sha256(f) for f in files]
    mine = [e for e in provenance.entries(root)
            if isinstance(e.get("path"), str) and folder in (Path(root) / e["path"]).resolve().parents]
    for f, place, digest in zip(files, places, digests, strict=True):
        if not any(e.get("path") == place and e.get("sha256") == digest for e in mine):
            return (f"{f.name} is not listed in the camera's downloads manifest under its own path: the order of the "
                    "run's downloads is not known")
    why = "its control-set download is not in the manifest"
    for at in [i for i, e in enumerate(mine) if e.get("path") == places[1] and e.get("sha256") == digests[1]]:
        before = next((i for i in range(at - 1, -1, -1) if str(mine[i]["path"]).endswith("_before.DAT")), None)
        if before is None or (mine[before].get("path"), mine[before].get("sha256")) != (places[0], digests[0]):
            why = (f"its start file ({files[0].name}) is not the session start nearest before its control-set "
                   f"download ({mine[before]['path'] if before is not None else 'none'} is): the downloads are not "
                   "one session's")
            continue
        got = mine[before:before + len(files)]
        bad = next((k for k in range(len(files)) if k >= len(got)
                    or (got[k].get("path"), got[k].get("sha256")) != (places[k], digests[k])), None)
        if bad is None:
            return ""
        why = (f"its downloads were not made in the order start, control-set, the resets, verify, one after another "
               f"in its own folder: where {files[bad].name} belongs the manifest holds "
               f"{got[bad]['path'] if bad < len(got) else 'nothing'} (another session's download, an _after, or a "
               "download made out of order): the downloads are not one session's")
    return why


def anchored(rel: str) -> bool:
    """True for a path that is absolute on any OS, whichever OS reads it (a result may be written on one and read on
    another): a POSIX one (/tmp/x), a drive (C:\\x, C:/x, and C:x, which is on that drive's current folder), a
    network share (\\\\server\\share), a leading slash or backslash. Windows' reading of a path finds them all, a
    POSIX path's leading slash included, and pathlib on POSIX takes none but the leading slash for absolute."""
    return bool(PureWindowsPath(rel).anchor)


def check_result(p: Path, result: dict, doc: dict, prefix: str, root: Path, allow_no_notice: bool = False,
                 base=None) -> dict:
    """A reset run's result checked (the module's words: which claims are recomputed from the run's own downloads,
    which are taken as the run wrote them); exits naming the first that fails. Returns {"start", "last" (paths),
    "start_cs", "last_cs", "changed" (the keys any reset download holds unlike the start file), "reset", "offered"}."""
    def no(why):
        sys.exit(f"make_sample: --from {p}: {why}")
    if result.get("peek") or not result.get("finished") or not result.get("last"):
        no("its run did not finish its resets (a stopped run or a peek): its last download is not every profile "
           "reset. Run it again to the end.")
    if result.get("verified") is not True:
        v = (result.get("verify") or {}).get("family_changed")
        no(f"its run is not verified (entering the panels again changed "
           f"{', '.join(v) if v else 'records, or no verify pass was made'}): what changed is not known to be the "
           "resets' own")
    if _said(result.get("family")) != _said(prefix):
        no(f"its run reset the family {result.get('family')!r}, not {prefix!r}")
    if result.get("mode") not in MODES:
        no(f"its run's mode {result.get('mode')!r} is neither {' nor '.join(MODES)}")
    if result.get("asked") is not None:
        no(f"its run was limited to {result.get('asked')!r} (--profiles): a --profiles run never feeds the sample")
    entries = result.get("profiles")
    if not isinstance(entries, list) or not entries or not all(isinstance(e, dict) for e in entries):
        no("its result lists no profile reset")
    reset = [str(e.get("profile")) for e in entries]
    if len(set(reset)) != len(reset):
        no("a profile is reset twice in its result")
    offered = result.get("offered_profiles")
    if not isinstance(offered, list) or not offered:
        no("its result does not say which profiles the camera offered")
    missing = [x for x in offered if x not in reset]
    if missing:
        no(f"the camera offered {', '.join(map(str, missing))}, which its run did not reset (a --profiles run, or one "
           "cut short): the sample takes only a run that reset every offered profile")
    if set(map(str, offered)) != set(reset):
        no(f"its run reset {', '.join(x for x in reset if x not in offered)}, which the camera's list it read did not "
           "offer")
    if base is not None:
        walked = recorded_profiles(paths.key(base.model, base.firmware), result.get("mode"))
        if walked is not None and set(walked) != set(map(str, offered)):
            gone = [x for x in walked if x not in offered]
            new = [x for x in offered if x not in walked]
            no(f"the profiles it says the camera offered are not the recorded menu walk's ({', '.join(walked)}): "
               + "; ".join(x for x in (f"it leaves out {', '.join(gone)}" if gone else "",
                                       f"it names {', '.join(map(str, new))}, which the walk does not" if new else "")
                           if x)
               + " (pp_reset_run stops on such a list unless --profiles names the profiles, and a --profiles run "
                 "never feeds the sample)")
    if result.get("need_both_readers") is not True:
        no("its run did not need both readers (--ocr-alone-ok, or a run before that check): a run meant for the "
           "sample judges every guarded name, and the panels it enters again, by OCR and the vision model both")
    control = result.get("control")
    if not isinstance(control, dict):
        no("its run made no positive control (--no-control, or a run before the control existed): without one, no "
           "record changing shows nothing about what a Reset writes")
    if control.get("profile") != reset[0]:
        no(f"its control was made on {control.get('profile')!r}, not on the first profile reset ({reset[0]})")
    if not allow_no_notice:
        quiet = [e["profile"] for e in entries if e.get("complete") is not True]
        if quiet:
            no(f"{', '.join(quiet)} showed no completion notice (the settings straight back after OK): give "
               "--allow-no-notice only for a body that shows none")
    for e in entries:
        r = e.get("readers") if isinstance(e.get("readers"), dict) else {}
        alone = [k for k in ("title", "question") if r.get(k) != "both"]
        if alone:
            no(f"{e['profile']}: the {' and the '.join(alone)} before its Reset {'was' if len(alone) == 1 else 'were'} "
               "not judged by both readers (the vision model unreachable or unreadable then): run again with both "
               "readers working")
    folder = p.parent.resolve()

    def inside(rel, what) -> Path:
        if not isinstance(rel, str) or not rel.strip():
            no(f"{what}: the result names no download")
        if anchored(rel):
            # "C:x" is a plain name to macOS and Linux, but Windows reads it as a drive: refused all the same
            drive = os.name != "nt" and re.match(r"^[A-Za-z]:", rel)
            no(f"{what} is an absolute path{', or a name Windows reads as a drive' if drive else ''} ({rel}): a result "
               "names its downloads inside its own folder")
        q = Path(rel)
        full = (folder / q).resolve()
        if folder not in full.parents or ".." in PureWindowsPath(rel).parts:
            no(f"{what} ({rel}) is outside the result's own folder")
        if not full.is_file():
            no(f"{what}: no such file {full}")
        try:
            provenance.check(full, root)
        except provenance.NotADownload as e:
            no(f"{what}: {e}")
        return full
    if result["last"] != entries[-1].get("download"):
        no(f"its last download ({result['last']}) is not its last profile's ({entries[-1].get('download')})")
    verify = result.get("verify") if isinstance(result.get("verify"), dict) else {}
    entered = verify.get("entered")
    if not isinstance(entered, dict):
        no("its verify pass does not say that each panel it entered was confirmed as the profile's own (its title "
           "read by both readers): a run made before that check. Run it again on the camera "
           "(kit/provers/pp_reset_run.py)")
    unsure = [x for x in reset if entered.get(x) != "confirmed"]
    if unsure:
        no(f"its verify pass entered {', '.join(unsure)} without confirming the panel as the profile's own (its title "
           "read by both readers): what that pass shows is not known to be those profiles'. Run it again")
    named = [("start", result.get("start"), "_before.DAT"), ("control", control.get("download"), "_control-set.DAT")]
    named += [(f"{e['profile']}'s reset", e.get("download"), f"_reset-{e['profile']}.DAT") for e in entries]
    named += [("verify", verify.get("download"), "_verify.DAT")]
    files = []
    for what, rel, tag in named:
        f = inside(rel, what)
        if not f.name.endswith(tag):
            no(f"{what}: {f.name} is not a {tag[1:-4]} download (its name ends {tag})")
        files.append(f)
    inside(result["last"], "last")
    if control.get("reset_download") != entries[0].get("download"):
        no(f"its control's reset_download ({control.get('reset_download')}) is not its first profile's download "
           f"({entries[0].get('download')}): the control's Reset is the first reset")
    try:
        cs = [camset.read(f) for f in files]
    except ValueError as e:
        no(f"a download is not a settings file the kit reads ({e})")
    if base is not None:
        for f, c in zip(files, cs, strict=True):
            why = same_layout(base, c, str(f))
            if why:
                sys.exit(f"make_sample: {why}: records are taken only from a file of the base's own camera and layout")
    saved = file_mode(doc, cs[-2])
    if saved is None:
        no("the definition names no live_mode record a file's mode is read from, so whether its run was made in "
           f"{result['mode']} mode cannot be checked")
    if saved != result["mode"]:
        no(f"its run says {result['mode']} mode, but its last download was saved in {saved} mode")
    why = one_session(files, folder, root)
    if why:
        no(why)
    ids = set(family_ids(doc, prefix) or ())
    layout = family_layout(doc, prefix)
    start_cs, control_cs, resets, verify_cs = cs[0], cs[1], cs[2:-1], cs[-1]
    got = control_of(start_cs, control_cs, resets[0], layout, reset[0], result["mode"])
    why = control_refusal(got, reset[0], result["mode"])
    if why or control.get("ok") is not True:
        no("its positive control does not hold: " + (why or "the result says so") + ": the resets are not shown to "
           "write the records")
    for k in ("changed", "reset_wrote", "copies_changed", "copies_reset_wrote"):
        why = first_difference(f"the control's {k}", control.get(k), got[k])
        if why:
            no(why)
    prev = control_cs
    for e, now in zip(entries, resets, strict=True):
        keys = changed_of(prev, now)
        for k, computed in (("changed", keys), ("family_changed", family_keys(keys, ids))):
            why = first_difference(f"{e['profile']}'s {k}", e.get(k), computed)
            if why:
                no(why)
        prev = now
    after = changed_of(resets[-1], verify_cs)
    why = first_difference("the verify pass's family_changed", verify.get("family_changed"), family_keys(after, ids))
    if why:
        no(why)
    if verify.get("family_changed"):
        no("its verify pass moved the family's records")
    if type(verify.get("others_changed")) is not int or \
            verify["others_changed"] != len(after) - len(family_keys(after, ids)):
        no("the verify pass's others_changed is not the count of other records its downloads show changing")
    changed = {parse_key(k) for now in resets for k in changed_of(start_cs, now)}
    return {"start": files[0], "last": files[-2], "start_cs": start_cs, "last_cs": resets[-1], "changed": changed,
            "reset": reset, "offered": [str(x) for x in offered]}


def source(given: str, base, doc: dict, prefix: str, root: Path | None = None,
           allow_no_notice: bool = False) -> Source:
    """A --from file: only a kit/provers/pp_reset_run.py result (pp_reset.json) of the family --take names whose every
    claim its own downloads bear out (check_result), its last reset download of the base's layout and saved in the
    mode the result says. Exits on anything else."""
    p = Path(given)
    if p.suffix.lower() != ".json":
        sys.exit(f"make_sample: --from {p}: --from takes only a reset run's result (kit/provers/pp_reset_run.py's "
                 "pp_reset.json), never a download: a download says nothing of which records a reset wrote")
    try:
        result = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        sys.exit(f"make_sample: --from {p}: not a readable result file ({e})")
    if not isinstance(result, dict):
        sys.exit(f"make_sample: --from {p}: not a reset run's result")
    mode = result.get("mode")
    got = check_result(p, result, doc, prefix, root if root is not None else paths.run_root(
        paths.key(base.model, base.firmware)), allow_no_notice, base)
    dat, cs = got["last"], got["last_cs"]
    changed, reset, offered = got["changed"], got["reset"], got["offered"]
    return Source(p, dat, cs, changed, mode, reset, offered)


def element(raw: bytes, i: int, size: int) -> bytes:
    return raw[i * size:(i + 1) * size]


def roles(sources: list, layout: dict) -> dict:
    """{copy: the Source it is taken from}: the in-use and stills records from the Stills result, the movie records
    from the Movie result. One result alone gives all three only when it shows its resets write the other mode's copy
    (writes_all). Exits on two results of one mode, more than two, or a mode missing."""
    by = {}
    for s in sources:
        if s.mode in by:
            sys.exit(f"make_sample: --from {by[s.mode].given} and {s.given} are both {s.mode} runs: give one Stills "
                     "and one Movie result")
        by[s.mode] = s
    if "Stills" in by and "Movie" in by:
        return {"live": by["Stills"], "stills": by["Stills"], "movie": by["Movie"]}
    only = sources[0]
    why = writes_all(only, layout)
    if why:
        need = "Movie" if only.mode == "Stills" else "Stills"
        sys.exit(f"make_sample: a {need} run's result is needed too ({why}): the {need.lower()} copies of the "
                 "profiles' parameters are written by a reset in that mode, as far as anything shows")
    return dict.fromkeys(COPIES, only)


def writes_all(src: Source, layout: dict) -> str:
    """Why one run's result does not show that its resets write every copy, or "": the other mode's copy of every live
    record its resets changed changed too (and at least one did), and its last download holds the other mode's copy
    equal to the live record for every profile reset."""
    other = "movie" if src.mode == "Stills" else "stills"
    recs = layout["records"]
    copy_of = {r["live"]: rid for rid, r in recs.items() if r["copy"] == other}
    pairs = [(lid, copy_of.get(lid)) for lid, r in recs.items() if r["copy"] == "live" and (0, lid) in src.changed]
    if not pairs:
        return "its resets changed no record in use"
    lost = [hexid(lid) for lid, cid in pairs if cid is None or (0, cid) not in src.changed]
    if lost:
        return f"its resets changed {len(lost)} records in use whose {other} copy they did not change"
    for lid, r in recs.items():
        cid = copy_of.get(lid)
        if r["copy"] != "live" or cid is None:
            continue
        size = src.cs.get(0, lid).size
        for p in src.reset:
            i = r["profiles"].get(p)
            if i is not None and element(src.cs.get(0, lid).raw, i, size) != element(src.cs.get(0, cid).raw, i, size):
                return f"its last download holds {hexid(cid)} unlike {hexid(lid)} for {p}"
    return ""


def compose(base, layout: dict, sources: list, doc: dict | None = None) -> tuple:
    """({(0, id): the record's bytes}, the report) by the rule in the module's words: each record of the family is the
    base's, with the element of every profile reset in the record's run (roles) taken from that run's last reset
    download; a record two runs both changed must hold the same bytes for the profiles both reset; the profiles no run
    reset keep the base's bytes. Exits on a disagreement, a record whose bytes are not its elements, or a composed file
    whose records in use differ from the copy of the base's own mode."""
    who = roles(sources, layout)
    recs, out = layout["records"], {}
    report = {"left": {c: set() for c in COPIES}, "from": {c: who[c] for c in COPIES}, "unchanged": []}
    for rid, r in sorted(recs.items()):
        b = base.get(0, rid)
        if b is None or len(b.raw) != b.size * b.count or any(i >= b.count for i in r["profiles"].values()):
            sys.exit(f"make_sample: {hexid(rid)} is not one element per profile in the base file")
        src = who[r["copy"]]
        unknown = [p for p in src.reset if p not in r["profiles"]]
        if unknown:
            sys.exit(f"make_sample: {src.given} resets {', '.join(unknown)}, which {hexid(rid)} holds no element for")
        raw, got = bytearray(b.raw), src.cs.get(0, rid).raw
        for p in src.reset:
            i = r["profiles"][p]
            raw[i * b.size:(i + 1) * b.size] = element(got, i, b.size)
        for other in sources:
            if other is src or (0, rid) not in other.changed:
                continue
            for p in (x for x in src.reset if x in other.reset):
                i = r["profiles"][p]
                if element(other.cs.get(0, rid).raw, i, b.size) != element(got, i, b.size):
                    sys.exit(f"make_sample: {hexid(rid)} ({p}) was changed by the resets of {src.given} and of "
                             f"{other.given}, to different bytes: the two runs disagree on its reset value; nothing "
                             "written")
        report["left"][r["copy"]] |= {p for p in r["profiles"] if p not in src.reset}
        if not any((0, rid) in s.changed for s in sources):
            report["unchanged"].append(rid)
        out[(0, rid)] = bytes(raw)
    mode = file_mode(doc, base) if doc else None
    if mode:
        for rid, r in recs.items():
            if r["copy"] == "live" or mode not in r["copy_for"]:
                continue
            lid, size = r["live"], base.get(0, rid).size
            for p, i in r["profiles"].items():
                if element(out[(0, lid)], i, size) != element(out[(0, rid)], i, size):
                    sys.exit(f"make_sample: the base was saved in {mode} mode, but the taken {hexid(lid)} (in use) and "
                             f"{hexid(rid)} ({mode}'s copy) differ for {p}: the file would break the copies rule; "
                             "nothing written")
    report["mode"] = mode
    return out, report


def mirrors(doc: dict | None, base, keys: list) -> dict:
    """{(set section, id): (0, id)}: the memory-set copies of the taken live settings the definition copies into the
    sets (in_sets), each to take the live record's taken bytes. Exits when the base holds a copy unlike its live
    record (what a reset leaves in a memory set is not known then)."""
    if not doc:
        return {}
    copied, sets, out = in_sets_ids(doc), set_sections(doc, len(base.sections)), {}
    for s, rid in keys:
        if s != 0 or rid not in copied:
            continue
        for sec in sets:
            copy = base.get(sec, rid)
            if copy is None or (sec, rid) in keys:
                continue
            if copy.raw != base.get(0, rid).raw:
                sys.exit(f"make_sample: the base file's {keyname((sec, rid))} differs from its live record "
                         f"{keyname((0, rid))}: what a reset leaves in a memory set is not known, so its copy cannot "
                         "follow the taken record; nothing written")
            out[(sec, rid)] = (0, rid)
    return out


def ids_text(keys) -> str:
    return ", ".join(hexid(rid) if s == 0 else keyname((s, rid)) for s, rid in keys) or "none"


def say_taken(layout, sources, report, mirrored, say=print):
    """Which records came from which run's last reset download and for which profiles (ids and names only), the
    profiles whose bytes were left as the base has them, the records no reset changed, the memory-set copies, and the
    keys the runs' resets changed outside the family."""
    recs = layout["records"]
    say(f"took the {len(recs)} records of the family {layout['prefix']!r}, element by element (ids only):")
    for c in COPIES:
        src, mine = report["from"][c], sorted(rid for rid, r in recs.items() if r["copy"] == c)
        if not mine:
            continue
        say(f"  {COPY_SAID[c]} records ({len(mine)}): the elements of {', '.join(src.reset)} from {src.mode} run "
            f"{paths.shown(src.dat)}")
    left = sorted(set().union(*report["left"].values()), key=lambda p: int(p[2:]))
    if left:
        where = "; ".join(f"{COPY_SAID[c]} records: {', '.join(sorted(v, key=lambda p: int(p[2:])))}"
                          for c, v in report["left"].items() if v)
        say(f"  left as the base sample has them, no run having reset them (no menu of the runs offered them): the "
            f"bytes of {', '.join(left)} ({where})")
    un = report["unchanged"]
    say(f"  held by every reset download as in its run's start file (the start file already at the reset value, or a "
        f"record Reset does not write): {len(un)} of {len(recs)}"
        + (f": {', '.join(map(hexid, un))} (taken from the last reset download as the camera held them after every "
           "profile's Reset)" if un else ""))
    if mirrored:
        secs = sorted({s for s, _ in mirrored})
        say(f"  their copies in the memory sets ({', '.join(map(str, secs))}): {len(mirrored)}, each the live record's "
            "taken bytes (the base holds each copy equal to its live record)")
    outside = sorted(set().union(*(s.changed for s in sources)) - {(0, rid) for rid in recs} - set(mirrored))
    if outside:
        say(f"  held by the runs' reset downloads unlike their start files and not taken: {len(outside)}: {', '.join(keyname(k) for k in outside)}")


def definition_of(cs, given: str | None):
    p = Path(given) if given else definitions.DIR / f"{paths.key(cs.model, cs.firmware)}.json"
    if not p.exists():
        if given:
            sys.exit(f"make_sample: --definition {p}: no such file")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_replacing(path: Path, data: bytes):
    """The file written beside its place first, then moved over it in one step: never half a sample."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="a file this body wrote right after Initialize, never the owner's own file")
    ap.add_argument("--out", default=None, help="default: editor/definitions/<model>_fw<fw>.DAT of the file's own model "
                                                "and firmware, beside its definition")
    ap.add_argument("--take", action="append", default=[], metavar="FAMILY",
                    help="the family of the definition whose records the reset runs give (its prefix or title, e.g. "
                         "'Picture Profile PP'); never record ids")
    ap.add_argument("--from", dest="sources", action="append", default=[], metavar="RESULT",
                    help="a kit/provers/pp_reset_run.py result (pp_reset.json), checked against its own downloads: "
                         "one Stills run's and one Movie run's")
    ap.add_argument("--allow-unchanged", action="store_true",
                    help="take the family even when no reset download holds any of its records unlike its run's "
                         "start file (look at the runs first)")
    ap.add_argument("--allow-no-notice", action="store_true",
                    help="take a result whose profiles came straight back to their settings after OK with no "
                         "completion notice (complete: false): only for a body that shows none")
    ap.add_argument("--definition", default=None, help="the definition naming the families (default: the file's own, "
                                                       "editor/definitions/<model>_fw<fw>.json)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be taken and zeroed; write nothing")
    a = ap.parse_args(argv)
    if bool(a.take) != bool(a.sources):
        sys.exit("make_sample: --take and --from go together: the family, and the reset runs it comes from")
    cs = camset.read(a.src)
    rules = camera_rules(cs)                       # before anything else: no sample without them
    out_path = Path(a.out) if a.out else definitions.DIR / f"{paths.key(cs.model, cs.firmware)}.DAT"
    changes, zeroed, taken_keys = {}, [], set()
    if a.take:
        if len(a.take) != 1 or "," in a.take[0]:
            sys.exit("make_sample: --take names one family (the one the reset runs reset)")
        doc = definition_of(cs, a.definition)
        if doc is None:
            sys.exit("make_sample: --take needs the camera's definition (its families); none found")
        layout = family_layout(doc, a.take[0])
        if len(a.sources) > 2:
            sys.exit("make_sample: --from takes at most two results, one Stills run's and one Movie run's")
        sources = [source(f, cs, doc, layout["prefix"], allow_no_notice=a.allow_no_notice) for f in a.sources]
        if len(sources) == 2 and set(sources[0].offered) != set(sources[1].offered):
            sys.exit(f"make_sample: --from {sources[0].given} and {sources[1].given}: the camera offered "
                     f"{', '.join(sources[0].offered)} in one run and {', '.join(sources[1].offered)} in the other: "
                     "the two runs must reset the same profiles")
        taken, report = compose(cs, layout, sources, doc)
        if len(report["unchanged"]) == len(layout["records"]) and not a.allow_unchanged:
            sys.exit(f"make_sample: no reset download holds any of the family's {len(layout['records'])} records unlike "
                     "its run's start file. Look at the runs; --allow-unchanged takes them anyway. Nothing written")
        mirrored = mirrors(doc, cs, list(taken))
        changes.update(taken)
        for k, live in mirrored.items():
            changes[k] = taken[live]
        taken_keys = set(changes)
        say_taken(layout, sources, report, mirrored)
    for si, sec in enumerate(cs.sections):
        for rid, r in sec.items():
            raw = changes.get((si, rid), r.raw)
            why = personal(rid, raw, rules)
            if (si, rid) in taken_keys and (why or rid in rules.defaults):
                sys.exit(f"make_sample: {keyname((si, rid))} is taken and also zeroed as personal: take another record")
            default = default_due(rid, r.raw, rules)
            if default is not None:
                changes[(si, rid)] = default
                zeroed.append((si, rid, len(r.raw), f"{rules.defaults[rid][1] or 'personal record'}: set to the "
                                                    "camera's default", True))
            elif why:
                changes[(si, rid)] = bytes(len(r.raw))
                zeroed.append((si, rid, len(r.raw), why, rid in rules.zeroed))
    b = cs.block
    out = b.sealed(b.with_text(camset.with_values(cs, changes), "saved", DEFAULT_STAMP))
    if a.dry_run:
        print(f"dry run: {out_path} not written; {len(zeroed)} records would be zeroed or reset")
    else:
        write_replacing(out_path, out)
        print(f"{out_path}: {len(zeroed)} records zeroed or reset" + (f", {len(taken_keys)} taken" if taken_keys else ""))
    for si, rid, n, why, listed in zeroed[:40]:      # a listed record by what it holds; a text by its length alone
        print(f"  section {si} {rid_text(rid)} ({n} B): {why if listed else '(' + shown_why(rid, why, rules) + ')'}")


if __name__ == "__main__":
    main()
