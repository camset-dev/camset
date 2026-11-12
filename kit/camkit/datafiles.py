"""A camera's public data files and the ones kept private (docs/decisions/0016), as camkit.definitions keeps a
definition's evidence: two owners with different settings who map the same model and firmware completely get the same
public files, so nothing in data/<model>_fw<fw>/ says what the camera held, nor how, when or in which run it was read.

    data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json      public, lean: which settings each reset puts back
    private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json      private whole: the menus as the walk read them,
    private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json       the mapper's rulings on pass 2's report, and
    private/evidence/<model>_fw<fw>/record_shapes_<model>_fw<fw>.json  the downloads' value shapes

The private files sit in a folder named as the camera's data folder, beside the definition's evidence file
(private/evidence/<model>_fw<fw>.json). The menu tree has no public half: which rows the walk found greyed or could
not read, which option lists it read, and where each list began, are the state the camera stood in, so no projection
of it is the same for any owner; the definition's own menu list and each setting's place (row, row_at, row_tab,
row_group, row_mode, under_option) are the public menu structure.
The reset file is one file, public and lean (reset_not_lean, schemas/settings-reset.schema.json): the mapper writes it
by hand after the reset tests and edits it there; the kit reads only it and keeps no private half in step with it
(fromdata.reset_names refreshes its names and tabs from the definition, nothing else). A file in the older whole shape
(the tests' own words, dates, a reading no test could tell) is refused by every command that writes it and by
kit/tools/check_public.py, naming kit/tools/move_evidence.py, which keeps the whole once as an archive in
private/evidence/<model>_fw<fw>/ (never read again) and writes the lean projection (lean_reset) in its place.
menu_tree_file, accepted_file and record_shapes_file only name the three files that are private whole: no reading of a
path moves a file. One left at its old public place in data/ (a clone brought up to date in the middle of a mapping)
is moved by kit/tools/move_evidence.py alone (move_command); the commands that read or write these files
(kit/pass2_report.py, kit/schema_update.py --write, kit/tools/menu_tree.py, kit/tools/set_twins.py,
kit/provers/mymenu_run.py) stop in plain words naming it while one is there only (stop_if_left), and a reader that
only shows takes it as absent. load_menu_tree reads the first and stops in plain words without it (NoMenuTree); a
reader that goes on without it says so in one line (say_no_menu_tree).
"""
import json
import os
import re
import sys
from pathlib import Path

from . import ROOT, definitions

CLONE_DATA = ROOT / "data"          # the clone's own data/, whose private-whole files the evidence folder keeps
# words a public data file never holds: what the walk or a test found, which is the state the camera stood in or the
# run's own story (evidence_in_public)
STATE_WORDS = ("greyed", "blocked by", "unhandled", "not walked", "no response to Right", "no label read", "as found",
               "an information notice comes first", "looks like the default", "the camera gives no reason")
# the files of a camera's data folder that are private whole: their name's stem up to "_<model>_fw<fw>"
PRIVATE_WHOLE = ("menu_tree", "accepted", "record_shapes")
RESET_READINGS = ("resets", "keeps")
RESET_KEYS = ("$schema", "about", "records")                 # the lean reset file's own keys (reset_not_lean)
RESET_FIELDS = ("name", "tab", "result", "initialize")       # a record's (in this order)
RESET_KEY = re.compile(r"(global|set):0x[0-9a-f]{4}(\[\d+\]|@\d+)?")   # a setting's key, as a definition's
RESET_ABOUT = ("Which settings Camera Settings Reset (result) and Initialize (initialize) put back on this model and "
               "firmware: resets, the reset puts the setting back; keeps, it leaves it as it was. A setting no test "
               "could tell, or none tested, is not listed (docs/decisions/0016).")


def evidence_path(p) -> Path:
    """The private place of the data file at `p`: private/evidence/<model>_fw<fw>/<its name> for a file of the clone's
    data/<model>_fw<fw>/, else <name>.evidence.json beside it (a file a test writes in a folder of its own). Where the
    private-whole files are kept (private_place), and where kit/tools/move_evidence.py archives an older whole reset
    file, which nothing reads."""
    p = Path(p)
    if p.parent.parent.resolve() == CLONE_DATA.resolve():
        return definitions.EVIDENCE_DIR / p.parent.name / p.name
    return p.with_name(p.stem + ".evidence.json")


class NoMenuTree(FileNotFoundError):
    """The camera's menu tree is not on this computer: it is the mapper's own (private/evidence/), never in a clone."""


class Refused(SystemExit):
    """A data file the kit will not read or write as it stands, in plain words: what is wrong, naming the files, and
    what to do (a SystemExit, so a command stops with the words and no traceback)."""


def _shown(p: Path) -> str:
    p = Path(p)
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


# the command that moves a mapper's private-whole files left at their old public place, data/<model>_fw<fw>/, into
# private/evidence/<model>_fw<fw>/ (kit/tools/move_evidence.py); nothing else ever moves them: a path is only a path
MOVE_COMMAND = ".venv/bin/python kit/tools/move_evidence.py"


def move_command(camera: str) -> str:
    """The exact command that moves `camera`'s private-whole files out of data/ (MOVE_COMMAND)."""
    return f"{MOVE_COMMAND} --camera {camera}"


def old_place(camera: str, kind: str) -> Path:
    """data/<model>_fw<fw>/<kind>_<model>_fw<fw>.json: where a file that is private whole (PRIVATE_WHOLE) was kept
    before 2026-11-11; a clone brought up to date in the middle of a mapping can still have it there."""
    return definitions.data_dir(camera) / f"{kind}_{camera}.json"


def private_place(camera: str, kind: str) -> Path:
    """private/evidence/<model>_fw<fw>/<kind>_<model>_fw<fw>.json: where the kit keeps a file that is private whole
    (evidence_path of its old place: beside it, for a data folder a test made of its own)."""
    return evidence_path(old_place(camera, kind))


def left_in_data(camera: str) -> list:
    """[(old place, private place)] of each file that is private whole and is still at its old public place only (not
    yet moved: move_command). Reads nothing but whether the files are there."""
    return [(old_place(camera, k), private_place(camera, k)) for k in PRIVATE_WHOLE
            if old_place(camera, k).exists() and not private_place(camera, k).exists()]


def stop_if_left(camera: str, doing: str) -> None:
    """Stops in plain words (Refused) a command that reads or writes the camera's private-whole files (`doing`, in
    words: the report, the writers, the menu tree, set_twins, mymenu_run) while one of them is at its old public place
    only: it would go on without the mapper's own file. Naming the command that moves them (move_command); a reader
    that only shows takes the file as absent instead."""
    left = left_in_data(camera)
    if not left:
        return
    names = ", ".join(_shown(o) for o, _ in left)
    env = (" CAMSET_EVIDENCE_DIR is set, so the kit looks for them there; the move goes into this clone's own "
           "private/evidence/, so afterwards point CAMSET_EVIDENCE_DIR at that folder or copy the moved files to yours."
           ) if os.environ.get("CAMSET_EVIDENCE_DIR") else ""
    raise Refused(f"nothing done: {doing} needs your own mapping's files, and {names} "
                  f"{'is' if len(left) == 1 else 'are'} still in data/, where the kit no longer reads them (they are "
                  f"private now, kept in private/evidence/{camera}/).{env} Move them there once with\n"
                  f"  {move_command(camera)}\n"
                  "(on Windows: .venv\\Scripts\\python kit\\tools\\move_evidence.py --camera "
                  f"{camera}), then run the command again.")


def menu_tree_file(camera: str) -> Path:
    """The camera's menus, row by row, as the kit walked them (kit/tools/menu_tree.py), private whole (private_place);
    only a path: nothing is read or moved (one left at its old public place: move_command)."""
    return definitions.menu_tree_file(camera)


def accepted_file(camera: str) -> Path:
    """The mapper's rulings on what pass 2's report leaves open (kit/writer/gate.py), private whole: every entry is a
    ruling on one mapping's report, which another owner's mapping need not raise. Only a path (private_place)."""
    return private_place(camera, "accepted")


def record_shapes_file(camera: str) -> Path:
    """The value shapes of the records no setting covers, read off one body's downloads, private whole: a shape
    ("constant", "boolean", ...) is what the owner's files held; the record's size and count the sample shows. Only a
    path (private_place)."""
    return private_place(camera, "record_shapes")


_SAID_NO_TREE = set()


def say_no_menu_tree(p, meaning: str) -> None:
    """One line, once a process for each file and meaning, that the camera's menu tree is not at `p` and what that
    means for what the command gives (`meaning`): a reader that goes on without it says so."""
    if (str(p), meaning) not in _SAID_NO_TREE:
        _SAID_NO_TREE.add((str(p), meaning))
        print(f"no menu tree at {_shown(p)} (the mapper's own, private): {meaning}{_old_copy_said(p)}", file=sys.stderr)


def _old_copy_said(p) -> str:
    """"; an old copy is in data/ ... (the command that moves it)" when the private file at `p` is missing and the
    file is still at its old public place, else ""."""
    p = Path(p)
    camera = p.parent.name
    kind = kind_of(Path(camera) / p.name)
    if kind not in PRIVATE_WHOLE or not old_place(camera, kind).exists():
        return ""
    return (f"; an old copy is still at {_shown(old_place(camera, kind))}, where the kit no longer reads it: move it "
            f"with {move_command(camera)}")


def read_json(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _dump(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".part")              # never a half-written file
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    tmp.replace(p)


# ---------------------------------------------------------------- the menu tree

def load_menu_tree(where) -> dict:
    """A camera's menu tree, whole, by its camera key (private/evidence/<model>_fw<fw>/, menu_tree_file) or its path;
    NoMenuTree, in plain words, when it is not there (a clone holds none: the definition's menu list and each setting's
    place are what is public of the menus)."""
    p = Path(where) if str(where).endswith(".json") else menu_tree_file(where)
    if not p.exists():
        raise NoMenuTree(f"no menu tree at {p}: it is the mapper's own, kept private whole (docs/decisions/0016). "
                         "kit/tools/menu_tree.py writes it from pass 1's page scan and crawls on the computer that holds "
                         "the camera's runs; CAMSET_EVIDENCE_DIR points the kit at another private/evidence/ folder"
                         f"{_old_copy_said(p)}.")
    return read_json(p)


def write_menu_tree(where, doc: dict) -> Path:
    """The menu tree `doc` whole into the file at `where` (menu_tree_file of the camera, or a path); returns it."""
    p = Path(where)
    _dump(p, doc)
    return p


# ---------------------------------------------------------------- the settings reset file

def reset_not_lean(doc) -> list:
    """Why a reset file is not in its lean shape, in words; empty for a lean one. Lean: an object of "about" (words, the
    kit's RESET_ABOUT or the mapper's own), "records" and at most a "$schema"; each record keyed as a definition's
    setting is ("global:0x0123", "set:0x0123", with "[i]" or "@n" after it) holds only "name" and "tab" (words) and
    "result" (Camera Settings Reset) and "initialize" (Initialize), at least one of the two, each "resets" or "keeps".
    No date, count or note about the tests, and no setting whose reading a test could not tell (it is simply not
    listed): those go in the mapper's own private notes (schemas/settings-reset.schema.json says the same)."""
    if not isinstance(doc, dict):
        return ["it is not a JSON object"]
    out = [f"the key {k!r} (a lean file holds only about and records)" for k in doc if k not in RESET_KEYS]
    if not isinstance(doc.get("about"), str):
        out.append("no \"about\" words")
    recs = doc.get("records")
    if not isinstance(recs, dict):
        return out + ["no \"records\" object"]
    for k, r in recs.items():
        if not RESET_KEY.fullmatch(str(k)):
            out.append(f"{k}: not a setting's key")
        if not isinstance(r, dict):
            out.append(f"{k}: not an object")
            continue
        out += [f"{k}: the field {f!r}" for f in r if f not in RESET_FIELDS]
        out += [f"{k}: {f} is not words" for f in ("name", "tab") if f in r and not isinstance(r[f], str)]
        said = [f for f in ("result", "initialize") if f in r]
        if not said:
            out.append(f"{k}: neither result nor initialize")
        out += [f"{k}: {f} {r[f]!r} (only resets or keeps)" for f in said if r[f] not in RESET_READINGS]
    return out


def lean_reset(doc: dict) -> dict:
    """The lean projection of a reset file in the older whole shape (kit/tools/move_evidence.py writes it once in the
    whole file's place): what each reset does to each setting a test could tell ("resets" or "keeps" for the one
    reading or both), its name and tab; never the tests' own words (their days and counts), and no setting a reading of
    which no test could tell (a test value that was the value the reset gives: such a reading would say the camera
    held another value before the test). Such a setting reads as one not tested. Its "about" is the kit's
    (RESET_ABOUT); a "$schema" the file names is kept."""
    out = {**({"$schema": doc["$schema"]} if isinstance(doc.get("$schema"), str) else {}),
           "about": RESET_ABOUT, "records": {}}
    for k, r in (doc.get("records") or {}).items():
        if not isinstance(r, dict) or not RESET_KEY.fullmatch(str(k)):
            continue
        said = [r[f] for f in ("result", "initialize") if f in r]
        if not said or any(x not in RESET_READINGS for x in said):
            continue
        out["records"][k] = {f: r[f] for f in RESET_FIELDS if f in r and (f in ("result", "initialize")
                                                                          or isinstance(r[f], str))}
    return out


def reset_file(camera: str) -> Path:
    return definitions.data_dir(camera) / f"settings_reset_{camera}.json"


def not_lean_words(p, why: list) -> str:
    """The plain words a command stops with on a reset file that is not lean (reset_not_lean's `why`), naming the
    command that keeps the whole file privately and writes the lean one (kit/tools/move_evidence.py)."""
    p = Path(p)
    camera = p.parent.name
    return (f"{_shown(p)} is not in the lean shape a public reset file has ({'; '.join(why[:3])}"
            f"{'; ...' if len(why) > 3 else ''}). It was written by an older kit, or by hand with notes about the "
            f"tests. Run once\n  {move_command(camera)}\n(on Windows: .venv\\Scripts\\python "
            f"kit\\tools\\move_evidence.py --camera {camera}): it keeps the whole file in private/evidence/{camera}/ "
            "and writes the lean one in its place. Keep notes about the tests (dates, counts, what was tried) in your "
            "own private/ notes, never in the public file.")


def read_reset(p) -> dict:
    """The public reset file at `p`, as it is; Refused, in plain words, when it is not readable JSON."""
    try:
        return read_json(p)
    except (OSError, ValueError) as e:
        raise Refused(f"{_shown(Path(p))} cannot be read as JSON ({e}): mend it by hand (it is written by hand, "
                      "docs/REMAPPING_PLAYBOOK.md, Phase 5), then run the command again.") from None


def write_reset(p, doc: dict) -> Path:
    """The lean reset file `doc` written to `p` (through a temporary file); Refused, nothing written, for one that is
    not lean (reset_not_lean)."""
    why = reset_not_lean(doc)
    if why:
        raise Refused("nothing written: " + not_lean_words(p, why))
    _dump(Path(p), doc)
    return Path(p)


# ---------------------------------------------------------------- what a public data file must not hold

# a run's folder, a kit2_ run name or an ISO date (camkit.definitions.RUN_OR_DAY)
RUN_OR_DAY = definitions.RUN_OR_DAY


def kind_of(p) -> str | None:
    """The kind of a camera data folder's file by its name: settings_reset, camera, help, help_guide_menu, and the
    private ones (PRIVATE_WHOLE: menu_tree, accepted, record_shapes); None for another name."""
    p = Path(p)
    m = re.fullmatch(r"(.+?)_" + re.escape(p.parent.name) + r"\.jsonl?", p.name)
    return m.group(1) if m else None


def camera_folders(data: Path = None) -> list:
    """Each camera's folder in `data` (default: the clone's data/), named <model>_fw<fw>."""
    from . import paths
    data = Path(data) if data is not None else CLONE_DATA
    return sorted(d for d in data.iterdir() if d.is_dir() and paths.KEY.match(d.name)) if data.exists() else []


def evidence_in_public(p, text: str = None) -> list:
    """Every place a public file of a camera's data folder carries what decision 16 keeps private, in words: a file
    that is private whole (PRIVATE_WHOLE: a menu tree, the accepted rulings, the record shapes); a run's folder, a
    kit2_ run name or an ISO date anywhere; in the reset file the walk's state words (STATE_WORDS) and any part of the
    older whole shape (reset_not_lean: the tests' own words, a reading no test could tell), naming the command that
    makes it lean. Empty for a lean file. `text` is the file's contents (a commit's blob, check_public --commits),
    else the file is read."""
    p = Path(p)
    kind = kind_of(p)
    if kind in PRIVATE_WHOLE:
        return [f"{p.name} is private whole, kept in private/evidence/{p.parent.name}/: move it there with "
                f"{move_command(p.parent.name)}"]
    text = p.read_text(encoding="utf-8") if text is None else text
    found = [f"names {m!r}" for m in sorted(set(RUN_OR_DAY.findall(text)))]
    if kind == "settings_reset":
        found += [f"the words {w!r}" for w in STATE_WORDS if w.lower() in text.lower()]
        try:
            why = reset_not_lean(json.loads(text))
        except ValueError:
            why = ["it is not valid JSON"]
        if why:
            found.append(f"not lean ({'; '.join(why[:3])}{'; ...' if len(why) > 3 else ''}): "
                         f"{move_command(p.parent.name)} keeps the whole file in private/evidence/{p.parent.name}/ and "
                         "writes the lean one")
    return found
