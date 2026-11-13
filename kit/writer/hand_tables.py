"""A camera's hand tables: what its mapping found by hand about the camera and the rules the writer applies to its
definition (docs/decisions/0016, 0020), read from the camera's own public data file,

    data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json        schemas/hand-tables.schema.json says each table

each table under its name: records whose name or note the camera proved wrong (RECORD_FIXES), records the menus never
write, found by hand (NEW_RECORDS, FILTER_FLAGS, NEW_LIKE, FRAME_PROOFS), value names no proof can give (CAROUSEL,
VALUE_FIXES, KEEP_LABELS, ...), the values the menus never offer (NOT_OFFERED), the copies the camera keeps (COPIES),
why a record cannot be proved (UNPROVED), and the label fixes and proof-row rules the writer applies. The file holds
what the camera is, the same for every owner of that model and firmware, and is written and edited by hand. How, when
and in which run each hand fact was proved is the mapping's evidence, kept in the private overlay
(private/evidence/<model>_fw<fw>.hand.json) and put back into the tables by load() (writer/hand_evidence.py). A camera
with no file has every table empty.

load() gives each table in the shape the writer reads: a set for a list of keys (KEEP_LABELS, NEW_WHOLE_LABELS,
EV_DOWN_FROM_20; COPY_MODES_UNKNOWN a frozenset), a dict by (key, value) for a table of [key, value, label] rows
(CAROUSEL, VALUE_FIXES, PP7_VALUES) and by (option, area) for FRAME_STEPS' [option, area, x, y], record ids for
LATE_COPY's "0x16bd", tuples where the writer unpacks (NEW_LIKE's (like, name), UNPROVED's (kind, day, why),
NOT_OFFERED's table, COPY_MODES), a compiled pattern for ORIENTED, and every other table as the file has it, in the
file's order. A NEW_RECORDS entry {"$ref": "#/FILTER_FLAGS/<key>"} is FILTER_FLAGS' entry of the same key, one object
in both tables, so the evidence put on it lands once (hand_evidence._suffixed). The tables are made in those shapes
before the evidence is put back, as the Python module that held them before they were data made them.

The file is contributed data, so the reader takes nothing on trust that the writer would trip on later: each table's
JSON type, each entry's type and the fields the writer reads, the value lists' [code, name] pairs, every pattern the
writer runs (CONTEXT_WORDS' patterns, each tried once with its words; NOT_OFFERED's walks; ORIENTED, with the group
the writer reads), and My Menu's empty line, whose one field is {code}. A file that is not JSON (NaN and Infinity
included), nested past what the parser follows, for another camera, with a table the kit does not know, a key or a row
twice, a table or an entry out of its shape, a pattern that does not compile, or a $ref anywhere but a NEW_RECORDS entry
naming FILTER_FLAGS' entry of the same key, is refused in plain words (Refused), naming the file and the table. What
else an entry may hold is the JSON Schema's, which the commit hooks and CI check. A file saved with a byte order mark
(Windows Notepad's) reads as one without.
"""
import json
import re
import types
from pathlib import Path

from camkit import datafiles, paths

from . import hand_evidence

# every table the kit reads, by how the file holds it (load() makes each the shape the writer reads); the file's own
# keys beside them
TABLES = {
    "RECORD_FIXES": "entries", "FILTER_FLAGS": "entries", "NEW_RECORDS": "new_records", "NEW_LIKE": "new_like",
    "NEW_WHOLE_LABELS": "set", "NEW_CHECK_NAMES": "words", "LATE_COPY": "record_ids", "ZONE": "values",
    "FRAME_STEPS": "steps", "FRAME_PROOFS": "entries", "CAROUSEL": "rows", "VALUE_FIXES": "rows", "PP7_VALUES": "rows",
    "KEEP_LABELS": "set", "EV_DOWN_FROM_20": "set", "HOLD_TABLES": "entries", "HOLD_BRACKET_COPIES": "words",
    "ISO_TABLE": "text", "LABEL_FIXES": "words", "GROUP_NAMES": "words", "MY_MENU_ROW": "text",
    "MY_MENU_EMPTY": "my_menu_empty", "SHOOT_MODE_RECORDS": "lists", "NOT_OFFERED": "not_offered",
    "VIDEO_SYSTEM_VALUES": "entries", "COPIES": "lists", "COPY_MODES": "tuple", "COPY_MODES_UNKNOWN": "frozenset",
    "UNPROVED": "unproved", "CONTEXT_WORDS": "context_words", "ORIENTED": "pattern",
}
OWN_KEYS = ("$schema", "_comment", "camera")
EMPTY = {"entries": dict, "new_records": dict, "new_like": dict, "words": dict, "lists": dict, "context_words": dict,
         "my_menu_empty": dict, "set": set, "frozenset": frozenset, "record_ids": dict, "values": list, "steps": dict,
         "rows": dict, "text": lambda: None, "not_offered": list, "tuple": tuple, "unproved": dict,
         "pattern": lambda: None}
REF = "#/FILTER_FLAGS/"         # the one $ref a file may hold: a NEW_RECORDS entry that is FILTER_FLAGS' own
# the fields of an entry the writer reads, by table, each with the JSON type it must have ("values": [code, name] pairs)
NEW_RECORD = {"like": str, "name": str, "values": "values", "note": str}
FIELDS = {"RECORD_FIXES": {"name": str}, "FILTER_FLAGS": NEW_RECORD, "NEW_RECORDS": NEW_RECORD,
          "FRAME_PROOFS": {"note": str}, "HOLD_TABLES": {"live": str, "mirror": (int, type(None))},
          "VIDEO_SYSTEM_VALUES": {"NTSC": list, "PAL": list}}
# fields read when an entry has them
MAYBE = {"FRAME_PROOFS": ("values",)}             # each a value list
JSON_TYPE = {dict: "an object", list: "an array", str: "a string", int: "a whole number", float: "a decimal number",
             type(None): "null"}


class Refused(SystemExit, ValueError):
    """A hand tables file the kit will not read as it stands, in plain words: what is wrong and what to do. A
    SystemExit, so a command stops with the words and no traceback; a ValueError too, for the callers that report a
    table they could not read and go on (kit/pass2_report.py's hand_rules)."""


class Tables(types.SimpleNamespace):
    """A camera's hand tables, each an attribute under its name (TABLES), and HAND_EVIDENCE: the hand evidence file
    put back into them, or None (none there, or load(evidence=False))."""


def empty() -> dict:
    """Every table, empty, in the shape the writer reads: a camera with no hand tables file."""
    return {name: EMPTY[kind]() for name, kind in TABLES.items()}


def load(camera: str, evidence: bool = True) -> Tables:
    """The camera's hand tables (`camera` its key, <model>_fw<fw>): its data file read (read), every table it does not
    hold empty, and, with `evidence`, the mapper's hand evidence put back where it is there (hand_evidence.put_back,
    which refuses evidence that does not fit). evidence=False: the public tables alone, as a clone without the private
    overlay reads them."""
    tables = empty()
    p = datafiles.hand_tables_file(camera)
    if p.exists():
        tables.update(read(p, camera))
    found = hand_evidence.put_back(tables, camera) if evidence else None
    return Tables(**tables, HAND_EVIDENCE=found)


def load_plain(camera: str) -> tuple:
    """(the camera's hand tables, its hand evidence) as the plain pass reads them (writer/generic.py): the public tables
    alone (load(camera, evidence=False)), the tables file held to its JSON Schema (so no entry carries a field of a
    proof's evidence), and the hand evidence apart, never put into the tables: {table name: {key or place: fields}},
    held to its own schema and to the tables (hand_evidence.plain_problems: evidence fields only, every part on an
    entry the tables hold). Either file refused in plain words (Refused) naming the table, the key and the field.
    HAND_EVIDENCE is the evidence file read, None when there is none ({} then)."""
    tables = load(camera, evidence=False)
    p = datafiles.hand_tables_file(camera)
    if p.exists():
        why = hand_evidence.schema_problems(json.loads(p.read_text(encoding="utf-8-sig")), "hand-tables")
        if why:
            raise _refused(p, "it does not fit its JSON Schema: " + "; ".join(why))
    doc, found = hand_evidence.read_doc(camera)
    if doc is not None:
        why = hand_evidence.plain_problems(doc, camera, vars(tables))
        if why:
            raise hand_evidence.Refused(
                f"{paths.shown(found)}: the plain pass takes from the hand evidence only what its JSON Schema allows "
                "(schemas/hand-evidence.schema.json: evidence fields, table by table; anything that is a fact about the "
                "camera belongs in the public tables file), each part on an entry the tables hold:\n"
                + "".join(f"  {w}\n" for w in why) + "Nothing was done: mend the file by hand, then run the command "
                "again (" + hand_evidence.check_command(camera) + " lists the same, read only).")
    tables.HAND_EVIDENCE = found
    return tables, (doc or {}).get("tables") or {}


def active(evidence: bool = False) -> Tables:
    """The hand tables of the camera the kit works on (camkit.paths.camera: --camera, CAMSET_CAMERA or
    private/config.json), the public tables alone unless `evidence`; every table empty when nothing names the camera,
    as for a camera with no file. For a prover's table (framepos_run's ZONE): never another camera's."""
    try:
        got = paths.camera()
    except paths.NoCamera:
        got = None
    if got is None:
        return Tables(**empty(), HAND_EVIDENCE=None)
    return load(got[0], evidence=evidence)


def read(p: Path, camera: str) -> dict:
    """The tables the file at `p` holds, each in the shape the writer reads, for the camera `camera`; Refused, in plain
    words, for a file that is not JSON, another camera's file, a table the kit does not know, a key or a row twice, a
    table or an entry out of its shape, a pattern that does not compile, or a $ref it does not take."""
    p = Path(p)
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"), object_pairs_hook=_once, parse_constant=_no_constant)
    except _Twice as e:
        raise _refused(p, f"{e.args[0]!r} is there twice in one object (JSON keeps only the last)") from None
    except RecursionError:
        raise _refused(p, "it is nested deeper than the reader follows (no hand table nests so deep)") from None
    except (OSError, ValueError) as e:
        raise _refused(p, f"it cannot be read as JSON ({e})") from None
    if not isinstance(doc, dict):
        raise _refused(p, "it is not a JSON object")
    if doc.get("camera") != camera:
        raise _refused(p, f"its camera is {doc.get('camera')!r}, but the file is {camera}'s: a table keyed by another "
                          "body's records would land on the wrong ones")
    unknown = [k for k in doc if k not in TABLES and k not in OWN_KEYS]
    if unknown:
        raise _refused(p, f"the kit knows no table {', '.join(map(repr, unknown))} (kit/writer/hand_tables.py, TABLES)")
    out = {}
    for name, kind in TABLES.items():
        if name not in doc:
            continue
        try:
            out[name] = _shaped(name, kind, doc[name])
        except _Twice as e:
            raise _refused(p, f"{name} holds {e.args[0]!r} twice") from None
        except _Shape as e:
            raise _refused(p, f"{name} is not in its shape: {e}") from None
        except (TypeError, ValueError, KeyError, IndexError, AttributeError, re.error) as e:
            raise _refused(p, f"{name} is not in its shape ({type(e).__name__}: {e})") from None
    for k, e in (out.get("NEW_RECORDS") or {}).items():
        if "$ref" in e:
            if e != {"$ref": REF + k} or k not in (out.get("FILTER_FLAGS") or {}):
                raise _refused(p, f"NEW_RECORDS[{k!r}] is {e!r}: a $ref there is only ever FILTER_FLAGS' entry of the "
                                  f"same key, {{\"$ref\": \"{REF}{k}\"}}, and FILTER_FLAGS must hold it")
            out["NEW_RECORDS"][k] = out["FILTER_FLAGS"][k]     # one entry in both tables
    return out


class _Twice(ValueError):
    """A key or a row the file holds twice (its name the first argument)."""


class _Shape(ValueError):
    """A table or an entry not in its shape: where, and what was expected, in words."""


class _NotJson(ValueError):
    """A constant JSON does not have (NaN, Infinity), which Python's reader would take."""


def _once(pairs: list) -> dict:
    """An object's pairs as a dict, refusing a key given twice (json would keep the last silently)."""
    out = {}
    for k, v in pairs:
        if k in out:
            raise _Twice(k)
        out[k] = v
    return out


def _no_constant(name: str):
    raise _NotJson(f"{name} is no number JSON has")


def _unique(items, what=lambda x: x) -> None:
    seen = set()
    for x in items:
        k = what(x)
        if k in seen:
            raise _Twice(k)
        seen.add(k)


def _is(x, kind) -> bool:
    """Whether `x` has the JSON type `kind` (a Python type or a tuple of them; a number never a bool)."""
    kinds = kind if isinstance(kind, tuple) else (kind,)
    return isinstance(x, kinds) and not (isinstance(x, bool) and int in kinds)


def _need(x, kind, where: str):
    """`x`, if it has the JSON type `kind`; else _Shape, saying where and what was expected."""
    if not _is(x, kind):
        kinds = kind if isinstance(kind, tuple) else (kind,)
        raise _Shape(f"{where} is {_json_type(x)}, not {' or '.join(JSON_TYPE[k] for k in kinds)}")
    return x


def _json_type(x) -> str:
    return "true or false" if isinstance(x, bool) else next((w for t, w in JSON_TYPE.items() if isinstance(x, t)),
                                                             type(x).__name__)


def _values(x, where: str) -> list:
    """A value list, [[code, name], ...] (the code a number, the name a string), as it is."""
    for i, pair in enumerate(_need(x, list, where)):
        if not (_is(pair, list) and len(pair) == 2 and _is(pair[0], int) and _is(pair[1], str)):
            raise _Shape(f"{where}[{i}] is {pair!r}, not a [code, name] pair (a number and a string)")
    return x


def _row(r, types_: tuple, where: str, words: str) -> list:
    """A row of a table of rows: an array of len(types_) items of those JSON types, as it is."""
    if not (_is(r, list) and len(r) == len(types_) and all(_is(v, t) for v, t in zip(r, types_, strict=True))):
        raise _Shape(f"{where} is {r!r}, not {words}")
    return r


def _pattern(text, where: str) -> re.Pattern:
    """`text` compiled as the writer runs it (Python's re); _Shape, saying where, when it does not compile."""
    try:
        return re.compile(_need(text, str, where))
    except re.error as e:
        raise _Shape(f"{where}, {text!r}, is no pattern Python reads ({e})") from None


def _shaped(name: str, kind: str, raw):
    """A table as the file holds it (`raw`), made the shape the writer reads (`kind`, TABLES); _Shape, saying where
    and what was expected, for one out of its shape."""
    if kind in ("entries", "new_records"):
        for k, e in _need(raw, dict, "the table").items():
            _need(e, dict, repr(k))
            if "$ref" in e:
                if kind != "new_records":
                    raise _Shape(f"{k!r} is a $ref, which only a NEW_RECORDS entry may be")
                continue
            for f, t in FIELDS[name].items():
                if f not in e:
                    raise _Shape(f"{k!r} has no {f!r}")
                if t == "values":
                    _values(e[f], f"{k!r}'s {f!r}")
                else:
                    _need(e[f], t, f"{k!r}'s {f!r}")
            for f in MAYBE.get(name) or ():
                if f in e:
                    _values(e[f], f"{k!r}'s {f!r}")
        return raw
    if kind == "words":
        for k, v in _need(raw, dict, "the table").items():
            _need(v, str, repr(k))
        return raw
    if kind == "lists":
        for k, v in _need(raw, dict, "the table").items():
            for i, x in enumerate(_need(v, list, repr(k))):
                _need(x, str, f"{k!r}[{i}]")
        return raw
    if kind == "context_words":
        for k, v in _need(raw, dict, "the table").items():
            _need(v, str, f"the words for {k!r}")
            try:
                _pattern(k, "a pattern").sub(v, "")             # the words tried once as the replacement
            except (re.error, IndexError) as e:
                raise _Shape(f"the words for {k!r}, {v!r}, are no replacement Python reads ({e})") from None
        return raw
    if kind == "my_menu_empty":
        _need(raw, dict, "the table")
        for f in ("label", "line"):
            if f not in raw:
                raise _Shape(f"it has no {f!r}")
            _need(raw[f], str, repr(f))
        if "{" in raw["line"].replace("{code}", "") or "}" in raw["line"].replace("{code}", ""):
            raise _Shape(f"its line, {raw['line']!r}, holds a brace that is not {{code}} (the camera file's empty code, "
                         "the one field the writer puts in)")
        return raw
    if kind == "values":
        return _values(raw, "the table")
    if kind == "text":
        return _need(raw, str, "the table")
    if kind in ("set", "frozenset"):
        for i, x in enumerate(_need(raw, list, "the table")):
            _need(x, str, f"item {i}")
        _unique(raw)
        return set(raw) if kind == "set" else frozenset(raw)
    if kind == "tuple":
        for i, x in enumerate(_need(raw, list, "the table")):
            for j, m in enumerate(_need(x, list, f"item {i}")):
                _need(m, str, f"item {i}[{j}]")
        return tuple(raw)
    if kind == "new_like":
        for k, e in _need(raw, dict, "the table").items():
            for f in ("like", "name"):
                if f not in _need(e, dict, repr(k)):
                    raise _Shape(f"{k!r} has no {f!r}")
                _need(e[f], str, f"{k!r}'s {f!r}")
        return {k: (e["like"], e["name"]) for k, e in raw.items()}
    if kind == "record_ids":
        for k, v in _need(raw, dict, "the table").items():
            if not re.fullmatch(r"0x[0-9a-f]{4}", k):
                raise _Shape(f"{k!r} is not a record id (\"0x16bd\")")
            _need(v, str, repr(k))
        return {int(k, 16): v for k, v in raw.items()}
    if kind == "rows":
        for i, r in enumerate(_need(raw, list, "the table")):
            _row(r, (str, int, str), f"row {i}", "[key, value, label] (a string, a number, a string)")
        _unique(raw, lambda r: (r[0], r[1]))
        return {(k, v): lab for k, v, lab in raw}
    if kind == "steps":
        for i, r in enumerate(_need(raw, list, "the table")):
            _row(r, (str, str, int, int), f"row {i}", "[option, area, x, y] (two strings and two numbers)")
        _unique(raw, lambda r: (r[0], r[1]))
        return {(option, area): (x, y) for option, area, x, y in raw}
    if kind == "not_offered":
        for i, e in enumerate(_need(raw, list, "the table")):
            _need(e, dict, f"mark {i}")
            for f, t in (("key", str), ("values", list), ("why", str), ("menu", str)):
                if f not in e:
                    raise _Shape(f"mark {i} has no {f!r}")
                _need(e[f], t, f"mark {i}'s {f!r}")
            if "walk" in e:
                _pattern(e["walk"], f"mark {i}'s walk")
            if "table" in e:
                _row(e["table"], (str, (str, type(None))), f"mark {i}'s table", "[table, page or null]")
        return [{f: tuple(v) if f == "table" else v for f, v in e.items()} for e in raw]
    if kind == "unproved":
        out = {}
        for k, e in _need(raw, dict, "the table").items():
            _row(e, (str, type(None), str), repr(k), "[kind, null, why] (the day is the hand evidence's)")
            out[k] = tuple(e)
        return out
    if kind == "pattern":
        got = _pattern(raw, "the table")
        if got.groups < 1:
            raise _Shape(f"{raw!r} has no group, and the writer reads its first")
        return got
    raise _Shape(f"no such kind of table: {kind}")


def _refused(p: Path, why: str) -> Refused:
    return Refused(f"{paths.shown(p)}: {why}. Nothing was done: mend the file by hand "
                   "(schemas/hand-tables.schema.json says each table's shape), then run the command again.")
