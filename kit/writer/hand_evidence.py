"""A camera's hand tables, kept apart from their evidence (docs/decisions/0016). The tables file
(data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, which kit/writer/hand_tables.py reads) is public: it holds what
the camera is, the same for every owner of that model and firmware who maps it (record names, value tables, the copies
and families, the notes that say what a record holds, the rules the writer applies). How, when, in which run and from
which state each of its facts was proved (a hand proof's values, run, day and menu row, a sample's count, the owner's
allowance, a note's evidence, what shows a not-offered mark) is the mapping's evidence, and is kept in the private
overlay beside the definition's own evidence:

    private/evidence/<model>_fw<fw>.hand.json   by table name, the fields each entry's evidence adds or replaces

put_back() puts that evidence back into the tables when the file is there (writer/hand_tables.load calls it last, once
the tables are in the shapes the writer reads), so the writer reads them whole and writes the same definition and
evidence file as before the split. Without it (a fresh clone, CI) the tables stay the public ones: --from-data and the
checks need nothing more, and kit/schema_update.py --write, in either pass, refuses to write the definition of a camera
whose tables hold entries the evidence completes (COMPLETES: a hand proof, a reason's day, what shows a not-offered
mark), which would lose them (missing). Its shape is schemas/hand-evidence.schema.json's; a mapper who proved none of
those entries by hand keeps the file with no evidence in it ("tables": {}).

The file's "tables" map a table's name to a patch: for a dict, {key: value or patch}; for a list or a tuple, {index:
value or patch}, an entry of a list that has a "key" checked by "$key" (and by "$values", its "values", where the
part gives them). The evidence adds to entries, never makes one,
and never replaces a public value: a key or index the table lacks is refused; inside an entry a patch of a container
recurses into it, and any other value adds a field the entry lacks or fills one that is empty (None). Any other public
value it would replace (a string, a list, a number, a bool, ...) is refused unless the evidence holds the same value,
for the public tables' facts are the public file's alone (a contributor's fix to one must not be reverted by an older
copy kept here). A string takes evidence after its words instead: "<field>+" adds it, so a note's evidence is stored
as the suffix only, "note+": "(seen on the camera, <day>)", and the note the writer reads is the public note, a space,
and the suffix. Format 1 kept the whole note: put_back refuses it, and `--convert` turns it into format 2 once (keeping
the old file beside it). CAMSET_EVIDENCE_DIR points the folder elsewhere (camkit.definitions). That is how the ILCE-1M2's
own pass reads its tables (put_back, from writer/hand_tables.load).

The plain pass, every other camera's, never puts the evidence into the tables: it reads the file apart
(writer/hand_tables.load_plain) and writes each piece only where the definition keeps evidence (a hand proof's run,
day and rows in its proof, a note's evidence and the owner's word in note_evidence, a reason's day, a mark's evidence),
so none reaches a public field however it is worded; and it takes the file only as its JSON Schema allows (evidence
fields only, table by table), every part naming an entry the public tables hold, a NOT_OFFERED part with its "$key",
and with its "$values" too on a setting the table gives more than one mark (plain_problems). `--check` says, read only, which parts of a camera's file the plain pass would refuse, by table, key
and field, never a value: the way to bring the ILCE-1M2's file in line before the two passes become one.

    .venv/bin/python kit/writer/hand_evidence.py --convert [--camera <model>_fw<fw>]
    .venv/bin/python kit/writer/hand_evidence.py --check [--camera <model>_fw<fw>]
"""
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import definitions  # noqa: E402

FORMAT = 2         # 2: a note's evidence is its suffix ("note+"), never the whole note (1)


def path(camera: str) -> Path:
    """private/evidence/<model>_fw<fw>.hand.json of a camera's key (beside its definition's evidence)."""
    return definitions.EVIDENCE_DIR / f"{camera}.hand.json"


SCHEMA_REF = "../../schemas/hand-evidence.schema.json"      # the "$schema" the file names, from private/evidence/
# the tables whose entries the hand evidence completes in the definition: a FRAME_PROOFS entry's hand proof (its values
# or sample, run, day and menu rows), an UNPROVED reason's day, what shows a NOT_OFFERED mark. A definition written from
# tables that hold any of them, without the file, would lose those proofs.
COMPLETES = ("FRAME_PROOFS", "UNPROVED", "NOT_OFFERED")


def missing(camera: str, found, tables: dict) -> str | None:
    """Why kit/schema_update.py --write must not write the camera's definition, in plain words, or None: its hand tables
    (`tables`, {table name: table}) hold entries the hand evidence completes (COMPLETES) and the camera's hand evidence
    file was not found (`found` None, as writer/hand_tables.load's HAND_EVIDENCE says). Any camera, either pass. The
    words say where the file belongs, and how a mapper who proved none of those entries by hand says so: the file with
    no evidence in it."""
    held = [n for n in COMPLETES if tables.get(n)]
    if found is not None or not held:
        return None
    from camkit import datafiles, paths
    empty = json.dumps({"$schema": SCHEMA_REF, "hand_format": FORMAT, "camera": camera, "tables": {}})
    return (f"schema_update: nothing written. Part of the {camera} definition is proved by its hand tables "
            f"({paths.shown(datafiles.hand_tables_file(camera))}: {', '.join(held)}), and what those proofs were (a "
            "hand proof's values, run and day, a reason's day, what shows a not-offered mark) is kept in the mapper's "
            f"private file {paths.shown(path(camera))}, which is not on this computer. Writing without it would drop "
            "those proofs from the definition. Run --write where that file is (the private overlay, private/evidence/), "
            "or point CAMSET_EVIDENCE_DIR at its folder; --from-data needs no evidence. If you map this camera and "
            f"proved none of those entries by hand, say so with that file holding no evidence: {empty} "
            "(docs/DATA_CONTRACTS.md, \"The hand evidence file\").")


class Refused(SystemExit, ValueError):
    """A hand evidence file put_back will not read as it stands, in plain words: what is wrong and what to do. A
    SystemExit, so a command (or anything that reads the tables with their evidence: writer/hand_tables.load) stops
    with the words and no traceback; a ValueError too, for the callers that catch put_back's refusals as such."""


def read_doc(camera: str) -> tuple:
    """(the camera's hand evidence file as JSON, its path), or (None, None) when it is not there; Refused, in plain
    words, for a file that is not JSON, of format 1 (with the command that converts it), or for another camera or
    format."""
    p = path(camera)
    if not p.exists():
        return None, None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{p}: the hand evidence cannot be read as JSON ({e}). Mend it, or put back a good copy, then "
                      "run the command again.") from None
    doc = doc if isinstance(doc, dict) else {}
    if doc.get("hand_format") == 1 and doc.get("camera") == camera:
        raise Refused(f"{p}: hand evidence of format 1, which kept a note's evidence as the whole note; these tables "
                      f"read format {FORMAT}, the evidence after the public note. Nothing was done. Convert it once "
                      f"with\n  .venv/bin/python kit/writer/hand_evidence.py --convert --camera {camera}\n"
                      f"(on Windows: .venv\\Scripts\\python kit\\writer\\hand_evidence.py --convert --camera {camera}; "
                      "it keeps the old file beside it, as .format1.json), then run the command again.")
    if doc.get("hand_format") != FORMAT or doc.get("camera") != camera:
        raise Refused(f"{p}: hand evidence of format {doc.get('hand_format')!r} for {doc.get('camera')!r}; "
                      f"these tables read format {FORMAT} for {camera}. Nothing was done: put that camera's own "
                      "hand evidence there, or move this file away.")
    return doc, p


STALE = ("Nothing was done. The hand evidence no longer fits the tables (an entry taken out of the tables or renamed, "
         "or a value the public tables hold): take that part out of the hand evidence file, or put the entry back into "
         "the tables file, then run the command again ({check} lists every such part, by table and key)")


def put_back(tables: dict, camera: str) -> Path | None:
    """The camera's hand evidence put back into `tables` ({table name: table}, as writer/hand_tables.load makes them),
    in place; the file read, or None when it is not there. A file for another camera or format, or naming a table, key
    or index the tables do not have, or that would replace a public value, is refused (Refused, a ValueError too) in
    plain words naming the file, the table, the key and what to do: evidence that no longer fits its table must not
    land on another entry. The ILCE-1M2's pass reads its tables so; the plain pass reads the evidence apart
    (plain_problems, writer/hand_tables.load_plain)."""
    doc, p = read_doc(camera)
    if doc is None:
        return None
    try:
        for name, patch in (doc.get("tables") or {}).items():
            if name not in tables:
                raise ValueError(f"{p}: no table {name}")
            tables[name] = patched(tables[name], patch, f"{p.name}: {name}", table=True)
    except Refused:
        raise
    except ValueError as e:
        raise Refused(f"{e}. " + STALE.format(check=check_command(camera)) + ".") from None
    return p


def check_command(camera: str) -> str:
    return f".venv/bin/python kit/writer/hand_evidence.py --check --camera {camera}"


def schema_problems(doc, schema: str) -> list:
    """Each place `doc` does not fit schemas/<schema>.schema.json, in words that name where (the table, the key, the
    field) and what the schema asks there, never a value the file holds (a key and a field name are where, not what)."""
    import re

    import jsonschema
    from camkit import ROOT
    s = json.loads((ROOT / "schemas" / f"{schema}.schema.json").read_text(encoding="utf-8"))
    out = []
    for e in sorted(jsonschema.Draft202012Validator(s).iter_errors(doc), key=lambda e: [str(x) for x in e.absolute_path]):
        where = " ".join(repr(x) if isinstance(x, str) else f"[{x}]" for x in e.absolute_path) or "the file"
        if e.validator == "additionalProperties":
            allowed, patterns = set(e.schema.get("properties") or {}), list(e.schema.get("patternProperties") or {})
            extra = sorted(k for k in e.instance if k not in allowed and not any(re.search(p, k) for p in patterns))
            out.append(f"{where} holds {', '.join(map(repr, extra))}, which it may not hold"
                       + (f" (it may hold {', '.join(map(repr, sorted(allowed)))})" if allowed else ""))
        elif e.validator == "required":
            out.append(f"{where} has no {', '.join(repr(r) for r in e.validator_value if r not in e.instance)}")
        elif e.validator == "propertyNames":
            out.append(f"{where} holds the key {e.instance!r}, which is not one it takes")
        elif e.validator == "type":
            kinds = e.validator_value if isinstance(e.validator_value, list) else [e.validator_value]
            out.append(f"{where} is not {' or '.join(kinds)}")
        elif e.validator in ("const", "enum"):
            out.append(f"{where} is not {e.validator_value!r}")
        else:
            out.append(f"{where} is not in the shape the schema gives ({e.validator})")
    return out


def plain_problems(doc: dict, camera: str, tables: dict) -> list:
    """Each part of the hand evidence file `doc` the plain pass (writer/generic.py, every camera's but the ILCE-1M2
    firmware 4.00's) refuses, one line each, in words naming the table, the key and the field, never a value: whatever
    its JSON Schema refuses (only the evidence fields of the tables that carry evidence, so nothing in it can set a
    public fact: schema_problems), an entry the public `tables` ({table name: table}, read without evidence) lack, a
    NOT_OFFERED part without "$key" or with another mark's, or, on a setting with more than one mark, without
    "$values" naming its mark's values or with another mark's (evidence kept by place would land on the wrong mark
    after a reorder or an insertion), and a "note+" for an entry with no public note. [] when the plain pass takes it.
    The words name where, never what: a "$values" that does not match is said so, not shown."""
    out = schema_problems(doc, "hand-evidence")
    for name, patch in ((doc.get("tables") or {}) if isinstance(doc.get("tables"), dict) else {}).items():
        table = tables.get(name)
        if table is None or not isinstance(patch, dict) or name == "MY_MENU_EMPTY":
            continue                                     # a table it does not know: the schema's line says so
        marks = {}                                       # setting key -> how many marks the table gives it
        for e in table if isinstance(table, (list, tuple)) else ():
            if isinstance(e, dict):
                marks[e.get("key")] = marks.get(e.get("key"), 0) + 1
        for key, fields in patch.items():
            fields = fields if isinstance(fields, dict) else {}
            if isinstance(table, (list, tuple)):
                entry = (table[int(key)] or {}) if key.isdigit() and int(key) < len(table) else None
                if entry is None:
                    out.append(f"{name} [{key}]: the tables have no entry there")
                elif "$key" not in fields:
                    out.append(f"{name} [{key}]: no \"$key\" naming the setting of its mark")
                elif fields["$key"] != entry.get("key"):
                    out.append(f"{name} [{key}]: its \"$key\" is not the setting of the mark at that place")
                elif "$values" in fields and not same_values(fields["$values"], entry.get("values")):
                    out.append(f"{name} [{key}]: its \"$values\" are not the values of the mark at that place")
                elif "$values" not in fields and marks.get(entry.get("key"), 0) > 1:
                    out.append(f"{name} [{key}]: no \"$values\" naming the values of its mark, which {entry.get('key')} "
                               "needs: the table gives it more than one mark")
            elif key not in table:
                out.append(f"{name} {key!r}: the tables have no such entry")
            elif "note+" in fields and not isinstance((table[key] or {}).get("note") if isinstance(table[key], dict)
                                                      else None, str):
                out.append(f"{name} {key!r}: \"note+\" for an entry with no note")
    return out


def same_values(said, values) -> bool:
    """Whether a part's "$values" are a mark's values, order aside."""
    try:
        return isinstance(said, list) and sorted(said) == sorted(values or [])
    except TypeError:
        return False


SUFFIX = "+"            # "<field>+": evidence added after the public string field's own words


def patched(target, patch: dict, where: str, table: bool = False):
    """`target` with `patch` put in (see the module's words): a dict in place, a list in place, a tuple rebuilt. At a
    table's own level (`table`) a key the table lacks is refused: the evidence adds to entries, never makes one."""
    if isinstance(target, dict):
        for k, v in patch.items():
            if k.endswith(SUFFIX) and k[:-1] in target:
                target[k[:-1]] = _suffixed(target[k[:-1]], v, f"{where}[{k!r}]")
            elif k in target:
                target[k] = _one(target[k], v, f"{where}[{k!r}]")
            elif table:
                raise ValueError(f"{where}: no entry {k!r} (the evidence adds to a table's entries, never makes one)")
            elif k.endswith(SUFFIX):
                raise ValueError(f"{where}: no field {k[:-1]!r} for {k!r} to add to")
            else:
                target[k] = v
        return target
    if isinstance(target, (list, tuple)):
        out = list(target)
        for i, v in patch.items():
            if not i.isdigit() or int(i) >= len(out):
                raise ValueError(f"{where}: no entry {i}")
            if isinstance(v, dict) and "$key" in v:
                if not isinstance(out[int(i)], dict) or out[int(i)].get("key") != v["$key"]:
                    raise ValueError(f"{where}[{i}]: the evidence is of {v['$key']!r}, the entry of "
                                     f"{(out[int(i)] or {}).get('key')!r}")
                v = {f: x for f, x in v.items() if f != "$key"}
            if isinstance(v, dict) and "$values" in v:      # checked as "$key" is, where the file gives it
                if not isinstance(out[int(i)], dict) or not same_values(v["$values"], out[int(i)].get("values")):
                    raise ValueError(f"{where}[{i}]: the evidence's \"$values\" are not the entry's values")
                v = {f: x for f, x in v.items() if f != "$values"}
            out[int(i)] = _one(out[int(i)], v, f"{where}[{i}]")
        if isinstance(target, list):
            target[:] = out
            return target
        return tuple(out)
    raise ValueError(f"{where}: not a table ({type(target).__name__})")


def _one(old, new, where: str):
    """The value an entry's field takes from the evidence `new`: a patch of a container recursed into, an empty (None)
    field filled, the same value kept; any other public value is never replaced (ValueError, naming the table, key and
    field: a string takes its evidence in "<field>+" instead)."""
    if isinstance(new, dict) and isinstance(old, (dict, list, tuple)):
        return patched(old, new, where)
    if old is None:
        return new
    if _same(old, new):
        return old                  # the same value: the public one kept as it is (a tuple stays a tuple)
    if isinstance(old, str):
        raise ValueError(f"{where}: the evidence would replace the public words {old[:40]!r}...; evidence goes after "
                         f"them, in \"<field>{SUFFIX}\"")
    raise ValueError(f"{where}: the evidence would replace the public {type(old).__name__} there with another value; "
                     "hand evidence only adds a field an entry lacks or fills an empty one (None). If the public table "
                     "is wrong, correct it there; if the evidence is out of date, take that field out of the hand file")


def _same(old, new) -> bool:
    """The public value `old` and the evidence `new` (read from JSON, where a tuple is a list) are the same value."""
    if old == new:
        return True
    try:
        return json.loads(json.dumps(old)) == new
    except (TypeError, ValueError):
        return False


def _suffixed(old, add, where: str) -> str:
    """The public string `old` and the evidence `add` after it, one space between (`add` alone after an empty one);
    once: an entry two tables share (FILTER_FLAGS' and NEW_RECORDS') gets it from both, and keeps one copy."""
    if not isinstance(old, str) or not isinstance(add, str):
        raise ValueError(f"{where}: adds to a string only")
    if old == add or old.endswith(f" {add}"):
        return old
    return f"{old} {add}" if old else add


def convert(doc: dict, tables: dict) -> tuple:
    """(format 2 of the format-1 hand evidence `doc`, [what could not be converted]) against the public `tables`
    ({table name: table}, read without evidence: writer/hand_tables.load(camera, evidence=False)): each string the evidence held whole where the public entry has
    a string becomes its suffix, "<field>+" (dropped when it is the public string itself); a string that does not begin
    with the public words is listed (table, key, field), left as it is, and put_back then refuses it by name."""
    left = []

    def entry(target, k):
        if isinstance(target, dict):
            return target.get(k)
        return target[int(k)] if k.isdigit() and int(k) < len(target) else None

    def walk(target, patch, where):
        out = {}
        for k, v in patch.items():
            old = entry(target, k)
            if isinstance(v, dict) and isinstance(old, (dict, list, tuple)):
                out[k] = walk(old, v, f"{where}[{k!r}]")
            elif isinstance(v, str) and isinstance(old, str) and old and v != old:
                if v.startswith(old + " "):
                    out[f"{k}{SUFFIX}"] = v[len(old) + 1:]
                else:
                    left.append(f"{where}[{k!r}]")
                    out[k] = v
            elif not (isinstance(v, str) and v == old):
                out[k] = v
        return out
    tabs = {name: walk(tables[name], patch, name) if name in tables else patch
            for name, patch in (doc.get("tables") or {}).items()}
    return {**doc, "hand_format": FORMAT, "tables": tabs}, left


def public_tables(camera: str) -> dict:
    """The camera's hand tables as a clone without the overlay reads them (no evidence put back), {table name: table},
    from its tables file (writer/hand_tables.py); a camera without one has no hand evidence to convert."""
    from camkit import datafiles
    from writer import hand_tables
    if not datafiles.hand_tables_file(camera).exists():
        raise SystemExit(f"{camera} has no hand tables ({datafiles.hand_tables_file(camera).name} in its data folder), "
                         "so it has no hand evidence to convert")
    return vars(hand_tables.load(camera, evidence=False))


def check(camera: str) -> int:
    """--check: the camera's hand evidence held to what the plain pass takes (plain_problems), read only: each part it
    would refuse, by table, key and field, never a value; 0 when it takes it as it stands, 1 otherwise. The ILCE-1M2's
    own pass reads its evidence as before (put_back); this says what to change so the file fits both."""
    from camkit import paths
    p = path(camera)
    if not p.exists():
        print(f"no hand evidence at {paths.shown(p)}: nothing to check")
        return 0
    doc, _ = read_doc(camera)
    found = plain_problems(doc, camera, public_tables(camera))
    for w in found:
        print(f"  {w}")
    print(f"{paths.shown(p)}: " + (f"{len(found)} parts the plain pass would refuse (nothing was changed)" if found else
                                   "the plain pass takes it as it stands"))
    return 1 if found else 0


def main(argv=None) -> int:
    import argparse
    import shutil
    from camkit import paths
    ap = argparse.ArgumentParser(description="A camera's hand evidence: convert format 1 into format 2 once (--convert), "
                                             "or say, read only, which parts the plain pass would refuse (--check).")
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--convert", action="store_true", help="convert the file from format 1, once")
    what.add_argument("--check", action="store_true",
                      help="read only: list each part of the file the plain pass would refuse, by table, key and field, "
                           "never a value (exit 1 when there is any)")
    a = ap.parse_args(argv)     # --camera <model>_fw<fw> is taken by camkit (camkit.paths.take_command_line)
    got = paths.camera()
    if got is None:
        raise paths.NoCamera(paths.no_camera_message())
    camera = got[0]
    if a.check:
        return check(camera)
    p = path(camera)
    if not p.exists():
        raise SystemExit(f"no hand evidence at {paths.shown(p)}: nothing to convert")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("hand_format") == FORMAT:
        print(f"{paths.shown(p)} is format {FORMAT} already: nothing to convert")
        return
    if doc.get("hand_format") != 1 or doc.get("camera") != camera:
        raise SystemExit(f"{paths.shown(p)}: format {doc.get('hand_format')!r} for {doc.get('camera')!r}, not format 1 "
                         f"for {camera}: not converted")
    new, left = convert(doc, public_tables(camera))
    keep = p.with_name(p.name.replace(".hand.json", ".hand.format1.json"))
    shutil.copyfile(p, keep)
    tmp = p.with_name(p.name + ".part")
    tmp.write_text(json.dumps(new, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)
    print(f"converted {paths.shown(p)} to format {FORMAT} (the old file kept as {paths.shown(keep)})")
    for w in left:
        print(f"  not converted, the public words differ from the start of the evidence's: {w} (put_back refuses it "
              "until the field is mended by hand: the public words, then the evidence in \"<field>+\")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
