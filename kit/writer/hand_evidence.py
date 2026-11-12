"""A camera's hand tables, kept apart from their evidence (docs/decisions/0016). A tables file (kit/writer/a1_tables.py
for the ILCE-1M2 firmware 4.00) is public: it holds what the camera is, the same for every owner of that model and
firmware who maps it (record names, value tables, the copies and families, the notes that say what a record holds, the
rules the writer applies). How, when, in which run and from which state each of its facts was proved (a hand proof's
values, run, day and menu row, a sample's count, the owner's allowance, a note's evidence, what shows a not-offered
mark) is the mapping's evidence, and is kept in the private overlay beside the definition's own evidence:

    private/evidence/<model>_fw<fw>.hand.json   by table name, the fields each entry's evidence adds or replaces

put_back() puts that evidence back into the tables when the file is there (the tables file calls it last), so the
writer reads them whole and writes the same definition and evidence file as before the split. Without it (a fresh
clone, CI) the tables stay the public ones: --from-data and the checks need nothing more, and kit/schema_update.py
--write refuses to write that camera's definition, which would lose the hand proofs.

The file's "tables" map a table's name to a patch: for a dict, {key: value or patch}; for a list or a tuple, {index:
value or patch}, an entry of a list that has a "key" checked by "$key". The evidence adds to entries, never makes one,
and never replaces a public value: a key or index the table lacks is refused; inside an entry a patch of a container
recurses into it, and any other value adds a field the entry lacks or fills one that is empty (None). Any other public
value it would replace (a string, a list, a number, a bool, ...) is refused unless the evidence holds the same value,
for the public tables' facts are the public file's alone (a contributor's fix to one must not be reverted by an older
copy kept here). A string takes evidence after its words instead: "<field>+" adds it, so a note's evidence is stored
as the suffix only, "note+": "(seen on the camera, <day>)", and the note the writer reads is the public note, a space,
and the suffix. Format 1 kept the whole note: put_back refuses it, and `--convert` turns it into format 2 once (keeping
the old file beside it). CAMSET_EVIDENCE_DIR points the folder elsewhere (camkit.definitions).

    .venv/bin/python kit/writer/hand_evidence.py --convert [--camera <model>_fw<fw>]
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


class Refused(SystemExit, ValueError):
    """A hand evidence file put_back will not read as it stands, in plain words: what is wrong and what to do. A
    SystemExit, so a command (or the tables module's import, which calls put_back) stops with the words and no
    traceback; a ValueError too, for the callers that catch put_back's refusals as such."""


def put_back(tables: dict, camera: str) -> Path | None:
    """The camera's hand evidence put back into `tables` (a tables module's globals()), in place; the file read, or
    None when it is not there. A file for another camera or format, or naming a table, key or index the tables do not
    have, is refused (ValueError): evidence that no longer fits its table must not land on another entry."""
    p = path(camera)
    if not p.exists():
        return None
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
    for name, patch in (doc.get("tables") or {}).items():
        if name not in tables:
            raise ValueError(f"{p}: no table {name}")
        tables[name] = patched(tables[name], patch, f"{p.name}: {name}", table=True)
    return p


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
    """(format 2 of the format-1 hand evidence `doc`, [what could not be converted]) against the public `tables` (a
    tables module's globals() read without evidence): each string the evidence held whole where the public entry has
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


# the hand tables module of each camera that has one (kit/writer/<name>.py), by the camera's key
TABLES_MODULES = {"ILCE-1M2_fw4.00": "a1_tables"}


def public_tables(camera: str) -> dict:
    """The camera's hand tables as a clone without the overlay reads them (no evidence put back): its tables module
    read afresh with the evidence folder pointed at an empty one."""
    import importlib.util
    import tempfile
    name = TABLES_MODULES.get(camera)
    if name is None:
        raise SystemExit(f"{camera} has no hand tables (kit/writer/*_tables.py), so it has no hand evidence to convert")
    keep = definitions.EVIDENCE_DIR
    with tempfile.TemporaryDirectory() as empty:
        definitions.EVIDENCE_DIR = Path(empty)
        try:
            spec = importlib.util.spec_from_file_location(f"writer._{name}_public",
                                                          Path(__file__).resolve().parent / f"{name}.py")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
        finally:
            definitions.EVIDENCE_DIR = keep
    return vars(mod)


def main(argv=None) -> None:
    import argparse
    import shutil
    from camkit import paths
    ap = argparse.ArgumentParser(description="Convert a camera's hand evidence of format 1 into format 2, once.")
    ap.add_argument("--convert", action="store_true", required=True, help="convert the file (it is all this does)")
    ap.parse_args(argv)         # --camera <model>_fw<fw> is taken by camkit (camkit.paths.take_command_line)
    got = paths.camera()
    if got is None:
        raise paths.NoCamera(paths.no_camera_message())
    camera = got[0]
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


if __name__ == "__main__":
    main()
