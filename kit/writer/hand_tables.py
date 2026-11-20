"""A camera's hand tables: what its mapping found by hand about the camera and the rules the writer applies to its
definition (docs/decisions/0016, 0020), read from the camera's own public data file,

    data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json        schemas/hand-tables.schema.json says each table

each table under its name: records whose name or note the camera proved wrong (RECORD_FIXES), records the menus never
write, found by hand (NEW_RECORDS, FILTER_FLAGS, NEW_LIKE, FRAME_PROOFS), value names no proof can give (CAROUSEL,
VALUE_FIXES, KEEP_LABELS, ...), the pickers whose lists were walked whole (PICKER_LISTS), the values the menus never
offer (NOT_OFFERED), the copies the camera keeps (COPIES) and the switches that keep a family's copies apart
(KEEPS_APART), the limits it keeps in order (LIMIT_PAIRS), how far each focus frame travels (FRAME_TRAVEL), why a
record cannot be proved (UNPROVED), the rows the records name otherwise than the camera draws them (ROW_NAMES,
which camkit.row_names reads for every comparison of a row's name), the camera's menus by shooting mode (MENUS) and
the rows given by hand (HAND_PLACES: a record a row's own function writes, a row the walk can never read, seen on the
camera), which writer/fromdata.py reads, and the label fixes and proof-row rules the writer applies. The file holds what the camera is, the same for every owner of that model
and firmware, and is written and edited by hand. How, when and in which run each hand fact was proved is the mapping's
evidence, kept in the private overlay (private/evidence/<model>_fw<fw>.hand.json) and put back into the tables by
load() (writer/hand_evidence.py). A camera with no file has every table empty.

load() gives each table in the shape the writer reads: a set for a list of keys (KEEP_LABELS, NEW_WHOLE_LABELS,
EV_DOWN_FROM_20; COPY_MODES_UNKNOWN a frozenset), a dict by (key, value) for a table of [key, value, label] rows
(CAROUSEL, VALUE_FIXES, PP7_VALUES) and by (option, area) for FRAME_STEPS' [option, area, x, y], record ids for
LATE_COPY's "0x16bd", tuples where the writer unpacks (NEW_LIKE's (like, name), UNPROVED's (kind, day, why),
NOT_OFFERED's and PICKER_LISTS' table, COPY_MODES), a compiled pattern for ORIENTED, and every other table as the file
has it, in the file's order. A NEW_RECORDS entry {"$ref": "#/FILTER_FLAGS/<key>"} is FILTER_FLAGS' entry of the same
key, one object in both tables, so the evidence put on it lands once (hand_evidence._suffixed). The tables are made in
those shapes before the evidence is put back, as the Python module that held them before they were data made them.

The file is contributed data, so the reader takes nothing on trust that the writer would trip on later: each table's
JSON type, each entry's type and the fields the writer reads, the value lists' [code, name] pairs, every pattern the
writer runs, Python's regular expressions the maintainer reviews in a pull request as code (CONTEXT_WORDS' patterns,
each tried once with its words; NOT_OFFERED's walks; PICKER_LISTS' keys and walks; ORIENTED, with the group the writer
reads), and My Menu's empty line, whose one field is {code}. A file that is not JSON (NaN and Infinity included), nested
past what the parser follows, for another camera, with a table the kit does not know, a key or a row twice, a table or
an entry out of its shape, a pattern that does not compile, or a $ref anywhere but a NEW_RECORDS entry naming
FILTER_FLAGS' entry of the same key, is refused in plain words (Refused), naming the file and the table. What else an
entry may hold is the JSON Schema's, which the commit hooks and CI check. A file saved with a byte order mark (Windows
Notepad's) reads as one without.
"""
import json
import re
import types
from pathlib import Path

from camkit import datafiles, paths, row_names

from . import hand_evidence

# every table the kit reads, by how the file holds it (load() makes each the shape the writer reads); the file's own
# keys beside them
TABLES = {
    "RECORD_FIXES": "entries", "FILTER_FLAGS": "entries", "NEW_RECORDS": "new_records", "NEW_LIKE": "new_like",
    "NEW_WHOLE_LABELS": "set", "NEW_CHECK_NAMES": "words", "LATE_COPY": "record_ids", "ZONE": "values",
    "FRAME_STEPS": "steps", "FRAME_TRAVEL": "frame_travel", "FRAME_PROOFS": "entries", "CAROUSEL": "rows",
    "VALUE_FIXES": "rows", "PP7_VALUES": "rows",
    "KEEP_LABELS": "set", "EV_DOWN_FROM_20": "set", "HOLD_TABLES": "entries", "HOLD_BRACKET_COPIES": "words",
    "ISO_TABLE": "text", "LABEL_FIXES": "words", "GROUP_NAMES": "words", "MY_MENU_ROW": "text",
    "MY_MENU_EMPTY": "my_menu_empty", "SHOOT_MODE_RECORDS": "lists", "PICKER_LISTS": "picker_lists",
    "NOT_OFFERED": "not_offered", "VIDEO_SYSTEM_VALUES": "entries", "COPIES": "lists", "COPY_MODES": "tuple", "COPY_MODES_UNKNOWN": "frozenset",
    "KEEPS_APART": "keeps_apart", "LIMIT_PAIRS": "limit_pairs",
    "UNPROVED": "unproved", "CONTEXT_WORDS": "context_words", "ORIENTED": "pattern", "ROW_NAMES": "row_names",
    "MENUS": "menus", "HAND_PLACES": "hand_places",
}
OWN_KEYS = ("$schema", "_comment", "camera")
EMPTY = {"entries": dict, "new_records": dict, "new_like": dict, "words": dict, "lists": dict, "context_words": dict,
         "my_menu_empty": dict, "set": set, "frozenset": frozenset, "record_ids": dict, "values": list, "steps": dict,
         "rows": dict, "text": lambda: None, "not_offered": list, "tuple": tuple, "unproved": dict,
         "pattern": lambda: None, "picker_lists": dict, "keeps_apart": dict, "limit_pairs": dict,
         "frame_travel": dict, "row_names": dict, "menus": list, "hand_places": dict}
REF = "#/FILTER_FLAGS/"         # the one $ref a file may hold: a NEW_RECORDS entry that is FILTER_FLAGS' own
PLACED_KEY = re.compile(r"(global|set):0x[0-9a-f]{4}(\[\d+\]|@\d+)?")          # a setting's key (HAND_PLACES)
# the fields of an entry the writer reads, by table, each with the JSON type it must have ("values": [code, name] pairs)
NEW_RECORD = {"like": str, "name": str, "values": "values", "note": str}
FIELDS = {"RECORD_FIXES": {"name": str}, "FILTER_FLAGS": NEW_RECORD, "NEW_RECORDS": NEW_RECORD,
          "FRAME_PROOFS": {"note": str}, "HOLD_TABLES": {"live": str, "mirror": (int, type(None))},
          "VIDEO_SYSTEM_VALUES": {"NTSC": list, "PAL": list}}
# fields read when an entry has them
MAYBE = {"FRAME_PROOFS": ("values",)}             # each a value list
JSON_TYPE = {dict: "an object", list: "an array", str: "a string", int: "a whole number", float: "a decimal number",
             type(None): "null", bool: "true or false"}


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


def _in_modes(x, has_by: bool, where: str) -> list:
    """A frame's in_modes: entries each naming some shooting modes, no mode twice, and taking the limits by "by" (no
    "as") or as for one value of it ("as", where there is a "by"), "inferred" only ever true and only beside an "as"."""
    for i, m in enumerate(_listed(x, where)):
        _fields(m, ("modes",), f"{where}[{i}]")
        _areas(m["modes"], f"{where}[{i}]'s modes")
        if "as" in m:
            if not has_by:
                raise _Shape(f"{where}[{i}] has an 'as', and its entry has no 'by'")
            _need(m["as"], int, f"{where}[{i}]'s as")
        if "inferred" in m and (_need(m["inferred"], bool, f"{where}[{i}]'s inferred") is not True or "as" not in m):
            raise _Shape(f"{where}[{i}]'s inferred is only ever true, beside an 'as'")
    _unique(mode for m in x for mode in m["modes"])
    return x


def _listed(x, where: str) -> list:
    """A list with something in it, as it is."""
    if not _need(x, list, where):
        raise _Shape(f"{where} lists nothing")
    return x


def _fields(x, names: tuple, where: str) -> dict:
    """An object holding each of `names`, as it is."""
    for f in names:
        if f not in _need(x, dict, where):
            raise _Shape(f"{where} has no {f!r}")
    return x


def _areas(x, where: str) -> list:
    """Areas: some names, none empty, none twice."""
    for i, a in enumerate(_listed(x, where)):
        if not _need(a, str, f"{where}[{i}]").strip():
            raise _Shape(f"{where}[{i}] is empty")
    _unique(x)
    return x


def _span(x, where: str, kind=int) -> list:
    """[lowest, highest], two whole numbers (or numbers of `kind`), the second not below the first."""
    _row(x, (kind, kind), where, "[lowest, highest] (two whole numbers)" if kind is int else "[lowest, highest] (two numbers)")
    if x[1] < x[0]:
        raise _Shape(f"{where} is {x!r}: its highest is below its lowest")
    return x


def _when(x: dict, needed: bool, where: str) -> None:
    """A limit's or a picture's "when": the values of its entry's "by" it is for, some whole numbers, each once; there
    exactly when the entry has a "by" (`needed`)."""
    if ("when" in x) != needed:
        raise _Shape(f"{where} {'has no' if needed else 'has a'} 'when', and its entry {'has a' if needed else 'has no'} 'by'")
    if needed:
        for j, v in enumerate(_listed(x["when"], f"{where}'s when")):
            _need(v, int, f"{where}'s when[{j}]")
        _unique(x["when"])


def _sizes(x, where: str) -> None:
    """Sizes tried, {"x": [...], "y": [...]}, whole numbers."""
    _fields(x, ("x", "y"), where)
    for f in ("x", "y"):
        for j, v in enumerate(_listed(x[f], f"{where}'s {f}")):
            _need(v, int, f"{where}'s {f}[{j}]")


def _pair(p, where: str, words: str = "[X record, Y record] (two keys)") -> list:
    """A pair of two different record keys, as it is."""
    _row(p, (str, str), where, words)
    if p[0] == p[1]:
        raise _Shape(f"{where} names {p[0]!r} twice")
    return p


def _pairs(x, where: str) -> list:
    """Some [X record, Y record] pairs (_pair)."""
    for i, p in enumerate(_listed(x, where)):
        _pair(p, f"{where}[{i}]")
    return x


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
            if "live_only" in e and name in ("NEW_RECORDS", "FILTER_FLAGS") and \
                    (e["live_only"] is not True or not str(k).startswith("global:")):
                raise _Shape(f"{k!r}'s 'live_only' is only ever true, on a live record (\"global:0x....\"): it keeps "
                             "the record out of the memory sets")
        return raw
    if kind == "words":
        for k, v in _need(raw, dict, "the table").items():
            _need(v, str, repr(k))
        return raw
    if kind == "row_names":             # an older row path and the camera's (camkit.row_names, which reads it)
        for k, v in _need(raw, dict, "the table").items():
            _need(v, str, repr(k))
        try:
            row_names.read(raw)
        except ValueError as e:
            raise _Shape(str(e).split(": ", 1)[1]) from None
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
    if kind == "picker_lists":
        for k, e in _need(raw, dict, "the table").items():
            if not k.strip():
                raise _Shape("an entry has no name")
            _need(e, dict, repr(k))
            for f, t in (("keys", str), ("walk", str), ("table", list), ("why", str)):
                if f not in e:
                    raise _Shape(f"{k!r} has no {f!r}")
                _need(e[f], t, f"{k!r}'s {f!r}")
            _pattern(e["keys"], f"{k!r}'s keys")
            _pattern(e["walk"], f"{k!r}'s walk")
            _row(e["table"], (str, (str, type(None))), f"{k!r}'s table", "[screen, page or section or null]")
        return {k: {f: tuple(v) if f == "table" else v for f, v in e.items()} for k, e in raw.items()}
    if kind == "keeps_apart":
        # a switch's key, then what it keeps apart: [{setting, apart, untick_sets?}], the fields the writer reads
        for k, entries in _need(raw, dict, "the table").items():
            if not _need(entries, list, repr(k)):
                raise _Shape(f"{k!r} lists nothing it keeps apart")
            for i, e in enumerate(entries):
                where = f"{k!r}[{i}]"
                _need(e, dict, where)
                for f, t in (("setting", str), ("apart", list)):
                    if f not in e:
                        raise _Shape(f"{where} has no {f!r}")
                    _need(e[f], t, f"{where}'s {f!r}")
                if not e["apart"]:
                    raise _Shape(f"{where}'s 'apart' names no value")
                for j, v in enumerate(e["apart"]):
                    _need(v, int, f"{where}'s 'apart'[{j}]")
                if "untick_sets" in e:
                    _need(e["untick_sets"], int, f"{where}'s 'untick_sets'")
            _unique(entries, lambda e: e["setting"])
        return raw
    if kind == "limit_pairs":
        # the lower limit's key, then {upper, lower_moves_upper?, upper_moves_lower?}, the fields the writer reads; a
        # direction the camera was not seen to move the other in is left out, never false; each upper of one pair
        for k, e in _need(raw, dict, "the table").items():
            _fields(e, ("upper",), repr(k))
            if _need(e["upper"], str, f"{k!r}'s 'upper'") == k:
                raise _Shape(f"{k!r} names itself as its upper limit")
            for f in ("lower_moves_upper", "upper_moves_lower"):
                if f in e and _need(e[f], bool, f"{k!r}'s {f!r}") is not True:
                    raise _Shape(f"{k!r}'s {f!r} is only ever true (left out where the camera was not seen to do it)")
        _unique(e["upper"] for e in raw.values())
        return raw
    if kind == "frame_travel":
        # a kind of focus frame, by a name: measured area by area ({places, limits}) or boxes one rule bounds ({inside,
        # boxes[, sizes_tried]}), the fields writer/frames.py reads; with "by" (the setting whose value picks the limits)
        # every limit names the values it is for ("when"), and boxes give each value's picture ("pictures", with the
        # grid); each area, and each area at each value, in one limit of its entry at most; "in_modes", how some shooting
        # modes' sections pick the limits, on the entry or (for its places alone) on a box
        for name, e in _need(raw, dict, "the table").items():
            if not name.strip():
                raise _Shape("an entry has no name")
            where = repr(name)
            has = set(_need(e, dict, where))
            if "by" in has:
                _need(e["by"], str, f"{where}'s by")
            if "in_modes" in has:
                _in_modes(e["in_modes"], "by" in has, f"{where}'s in_modes")
            if {"places", "limits"} <= has and not {"inside", "boxes", "sizes_tried", "pictures", "grid"} & has:
                _pairs(e["places"], f"{where}'s places")
                for i, lim in enumerate(_listed(e["limits"], f"{where}'s limits")):
                    _fields(lim, ("areas", "x", "y"), f"{where}'s limits[{i}]")
                    _areas(lim["areas"], f"{where}'s limits[{i}]'s areas")
                    for f in ("x", "y"):
                        _span(lim[f], f"{where}'s limits[{i}]'s {f}")
                    _when(lim, "by" in has, f"{where}'s limits[{i}]")
                _unique(a if v is None else (a, v) for lim in e["limits"] for a in lim["areas"] for v in lim.get("when") or [None])
            elif {"inside", "boxes"} <= has and not {"places", "limits"} & has:
                _fields(e["inside"], ("x", "y"), f"{where}'s inside")
                for f in ("x", "y"):
                    _span(e["inside"][f], f"{where}'s inside's {f}", (int, float))
                if "sizes_tried" in e:
                    if "pictures" in e:
                        raise _Shape(f"{where} has sizes_tried beside pictures, which hold each picture's own")
                    _sizes(e["sizes_tried"], f"{where}'s sizes_tried")
                if ("pictures" in e) != ("by" in e) or ("pictures" in e) != ("grid" in e):
                    raise _Shape(f"{where} has {'pictures' if 'pictures' in e else 'by or grid'} without "
                                 f"{'by and grid' if 'pictures' in e else 'pictures'}: the three go together")
                if "pictures" in e:
                    _fields(e["grid"], ("x", "y"), f"{where}'s grid")
                    for f in ("x", "y"):
                        if not _need(e["grid"][f], int, f"{where}'s grid's {f}") > 0 or not \
                                0 <= e["inside"][f][0] <= e["inside"][f][1] <= e["grid"][f]:
                            raise _Shape(f"{where}'s inside's {f} is not within its grid, 0 to {e['grid'][f]}")
                    for i, pic in enumerate(_listed(e["pictures"], f"{where}'s pictures")):
                        _fields(pic, ("when", "x", "y"), f"{where}'s pictures[{i}]")
                        _when(pic, True, f"{where}'s pictures[{i}]")
                        for f in ("x", "y"):
                            frac = _row(pic[f], (int, int), f"{where}'s pictures[{i}]'s {f}", "[numerator, denominator]")
                            if not 0 < frac[0] <= frac[1]:
                                raise _Shape(f"{where}'s pictures[{i}]'s {f} is {frac!r}: no part of the grid's span")
                        if "sizes_tried" in pic:
                            _sizes(pic["sizes_tried"], f"{where}'s pictures[{i}]'s sizes_tried")
                        if "sizes_range" in pic:
                            if "sizes_tried" in pic:
                                raise _Shape(f"{where}'s pictures[{i}] has sizes_tried beside sizes_range: one or the other")
                            _fields(pic["sizes_range"], ("x", "y"), f"{where}'s pictures[{i}]'s sizes_range")
                            for f in ("x", "y"):
                                _span(pic["sizes_range"][f], f"{where}'s pictures[{i}]'s sizes_range's {f}")
                    _unique(v for pic in e["pictures"] for v in pic["when"])
                for i, box in enumerate(_listed(e["boxes"], f"{where}'s boxes")):
                    _fields(box, ("areas", "size", "places"), f"{where}'s boxes[{i}]")
                    _areas(box["areas"], f"{where}'s boxes[{i}]'s areas")
                    _pair(box["size"], f"{where}'s boxes[{i}]'s size", "[width record, height record] (two keys)")
                    _pairs(box["places"], f"{where}'s boxes[{i}]'s places")
                    if "in_modes" in box:
                        _in_modes(box["in_modes"], "by" in has, f"{where}'s boxes[{i}]'s in_modes")
            else:
                raise _Shape(f"{where} is neither a frame measured area by area (places and limits) nor boxes one rule "
                             "bounds (inside and boxes, and sizes_tried where known)")
        return raw
    if kind == "menus":
        # the camera's menus, one per position of its shooting-mode switch, in order: {name, modes[, main_tiles][, hover]}
        # (writer/fromdata.py camera_menus holds each mode and tile set to the camera file)
        for i, e in enumerate(_need(raw, list, "the table")):
            where = f"menu {i}"
            _fields(e, ("name", "modes"), where)
            if not _need(e["name"], str, f"{where}'s name").strip():
                raise _Shape(f"{where} has no name")
            if not _need(e["modes"], list, f"{where}'s modes"):
                raise _Shape(f"{where} ({e['name']!r}) names no mode")
            for j, m in enumerate(e["modes"]):
                _need(m, str, f"{where}'s modes[{j}]")
            for f in ("main_tiles", "hover"):
                if f in e:
                    _need(e[f], str, f"{where}'s {f}")
            extra = sorted(set(e) - {"name", "modes", "main_tiles", "hover"})
            if extra:
                raise _Shape(f"{where} holds {', '.join(map(repr, extra))}, which a menu does not have")
        _unique(raw, lambda e: e["name"])
        return raw
    if kind == "hand_places":
        # a record's row given by hand, by key: {row: its tab, then the labels from the top row down, " > " between;
        # why: what kind of fact it is, in a few words}
        for k, e in _need(raw, dict, "the table").items():
            if not PLACED_KEY.fullmatch(k):
                raise _Shape(f"{k!r} is not a setting's key (\"global:0x....\", \"set:0x....\", with [n] or @n)")
            _fields(e, ("row", "why"), repr(k))
            labels = [x.strip() for x in _need(e["row"], str, f"{k!r}'s row").split(" > ")]
            if len(labels) < 2 or not all(labels):
                raise _Shape(f"{k!r}'s row, {e['row']!r}, is not its tab then its row's labels, \" > \" between")
            if not _need(e["why"], str, f"{k!r}'s why").strip():
                raise _Shape(f"{k!r} says no why")
            extra = sorted(set(e) - {"row", "why"})
            if extra:
                raise _Shape(f"{k!r} holds {', '.join(map(repr, extra))}, which a hand place does not have")
        return raw
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
