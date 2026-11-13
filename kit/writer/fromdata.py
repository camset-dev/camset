"""The parts of a definition the kit takes from data/ alone, whatever the runs hold (kit/schema_update.py --from-data):
the format and the camera section, the memory copies named from it, the project's own help, each setting's place on the
camera's menus and its menu list, the Expert marks, the photographer's words, and each note tidy with its evidence apart. On the
committed data it gives the committed definitions byte for byte (kit/tests/test_definitions.py)."""
import json
import re
from pathlib import Path

from camkit import ROOT, datafiles, definitions, help_files, models, paths, placement
from runner import read_json

from .mirror import mirror_names, mirror_of, mirror_place
from .notes import with_evidence_apart, with_tidy_note
from .proofs import without_held, without_observed, without_written_with


def model_refused(run: Path, doc: dict) -> str:
    """Why the run's proofs may not go into this definition, or "": its downloads must be the definition's model
    and firmware (camkit.models)."""
    return models.refused(run, doc["model"], doc["layouts"][0]["firmware"],
                          f"editor/definitions/{definitions.key(doc)}.json")


EXPERT_WORDS = ("copy", "flag", "alt numbering", "working", "in use", "toggle", "alternate")
# the words of a record's mapping that a setting off every camera row may still carry in its name ("Drive Mode (third
# record)", "Memory 1: Shutter speed: numerator", the SDK's "Unknown (...)"): such a setting is the kit's, not the
# photographer's, so Expert mode only, whatever its source (2026-11-07). A setting on a camera row keeps its place in
# the lists; its name is the kit's to make plain (RECORD_FIXES), and test_definitions' "mapping words" test holds it.
MAPPING_WORDS = re.compile(r"\brecord\b|slot memory|numerator|denominator|mirror|kind memory|copy\)|\(inferred|"
                           r"\bthird\b|second record|\bsdk\b", re.I)


def expert(s: dict, slots: frozenset = frozenset(), mirror: dict = None) -> bool:
    """Shown in Expert mode only: a derived working copy, a flag or an alternate numbering, by its name (the rule the
    editor held until 2026-11-05, decision 20, now the kit's); one of My Menu's places, a live setting of a record
    the camera's My Menu names (`slots`, mymenu_slots), which the editor's My Menu page edits place by place, so the
    raw places are a duplicate there; a field of the memories' live copy (`mirror`, mirror_of: each memory set holds
    its own, which the editor shows); a setting on no camera row whose name holds a mapping word (MAPPING_WORDS); or a
    copy named so ("JPEG/HEIF Quality (Slot 1, copy)", which the camera writes with Slot 1's on every choice): the main
    one is the photographer's, the copy a duplicate."""
    if s.get("area") == "global" and s.get("id") in slots:
        return True
    if re.search(r"\bcopy\)$", s["name"]):
        return True
    if mirror_place(s["key"], mirror or {})[0] is not None:
        return True
    if "row" not in s and MAPPING_WORDS.search(s["name"]):
        return True
    # how the record's meaning was found ("source") is evidence (camkit.definitions): a definition read without its
    # evidence keeps the mark it has for this last rule
    derived = s["source"] == "Derived" if "source" in s else bool(s.get("expert"))
    return derived and any(w in s["name"].lower() for w in EXPERT_WORDS)


def mymenu_slots(doc: dict) -> frozenset:
    """The records of My Menu's pages, from the camera section (camera.my_menu.records); none without My Menu."""
    return frozenset(((doc.get("camera") or {}).get("my_menu") or {}).get("records") or ())


def with_expert(s: dict, slots: frozenset = frozenset(), mirror: dict = None) -> dict:
    """The setting with "expert": true after "in_sets" when expert() says so, and without the key otherwise."""
    flag = expert(s, slots, mirror)
    out = {}
    for k, v in s.items():
        if k == "expert":
            continue
        out[k] = v
        if k == "in_sets" and flag:
            out["expert"] = True
    if flag and "expert" not in out:
        out["expert"] = True
    return out


def with_camera(doc: dict) -> dict:
    """"$schema" and "definition_format" first, and the camera section copied from the camera file in data/ (when
    there is one): the camera's own facts are edited there only."""
    cam = definitions.camera_file(definitions.key(doc))
    if cam.exists():
        camera = read_json(cam)
        camera.pop("_comment", None)
        camera.pop("$schema", None)
        doc = dict(doc, camera=camera)
    # the file names its JSON Schema (schemas/), so editors and check-jsonschema validate it
    return {"$schema": definitions.SCHEMA_REF, "definition_format": definitions.FORMAT,
            **{k: v for k, v in doc.items() if k not in ("$schema", "definition_format")}}


def own_help(doc: dict) -> int:
    """The project's own help (data/<model>_fw<fw>/help_<model>_fw<fw>.json) in place of whatever help the settings
    held; how many got some. A file there that says it is for another camera (another model, or another firmware of
    this one) or names none is refused (help_files.read says why), and the definition gets no help: it only ever
    carries its own camera's."""
    help_files.taken(doc)
    return help_files.put(doc, help_files.read(help_files.own_path(doc), doc))


# the groups the first kit named by where it found them, under plain names (2026-11-07): "Other settings", not the
# editor's own "Other" (the Menu's entry for tabs no list names); the memories' live copy, all Expert mode only (expert),
# beside the exposure each memory set stores, "Memory exposure (stored per memory)"
SETTING_GROUPS = {"Other (from SDK)": "Other settings",
                  "Memory exposure (mirror of all 12 memories)": "Memory exposure (live copy)"}
BUTTON_WORD = re.compile(r"\s*•\s*(OK|Cancel)\s*$")        # a dialog's button, read with its notice
RECORD_REF = re.compile(r"\s*\((?:global:|set:)?0x[0-9a-f]{4}\)", re.I)  # "the manual level (0x0052)"


def plain_reason(why: str) -> str:
    """A refused option's reason without the dialog's button word read after it ("... Gamma HLG2 • OK")."""
    return BUTTON_WORD.sub("", why)


# the camera's refusal names what blocks the option: "... not available as follows <setting> <value>", a setting and
# the value it stood on when the row was walked
AS_FOLLOWS = re.compile(r"\s+as follows:?\s+(\S.*)$", re.I | re.S)


def blocked_reason(why: str, row: str, names: list) -> str:
    """A refused option's reason as a definition publishes it (plain_reason): up to the blocking setting's name, without
    the value that setting stood on ("... not available as follows <setting>"), for unless a run set that state itself
    it was the camera's own, a contributor's setting (docs/decisions/0016). The value stays where the row's proof
    context names the blocking setting (the run set it). The setting
    is the longest of the definition's setting names (`names`, longest first) the words after "as follows" start with,
    a word ending there; where none fits, everything from "as follows" goes."""
    why = plain_reason(why)
    m = AS_FOLLOWS.search(why)
    if not m:
        return why
    rest = m[1]
    name = next((n for n in names if rest.lower().startswith(n.lower()) and rest[len(n):len(n) + 1] in ("", " ")), None)
    ctx = re.search(r"\[([^\]]*)\]\s*$", row or "")
    if name and ctx and name.lower() in ctx[1].lower():
        return why
    return why[:m.start(1)] + rest[:len(name)] if name else why[:m.start()]


def with_plain_words(s: dict, names: list = ()) -> dict:
    """What a photographer reads of a setting, in their words: its group by SETTING_GROUPS, each refused option's
    reason without the button word nor the value the blocking setting stood on (blocked_reason, `names` the definition's
    setting names, longest first), and its display rule without record numbers (those stay in the note, which the
    editor shows in Expert mode)."""
    s = dict(s)
    head, sep, rest = (s.get("group") or "").partition(" › ")
    if head in SETTING_GROUPS:
        s["group"] = SETTING_GROUPS[head] + sep + rest
    if s.get("menu_blocked"):
        s["menu_blocked"] = [dict(b, reason=blocked_reason(b["reason"], b.get("menu"), names)) if b.get("reason")
                             else b for b in s["menu_blocked"]]
    if s.get("display_rule"):
        s["display_rule"] = RECORD_REF.sub("", s["display_rule"])
    return s


PLACE_KEYS = ("row", "row_at", "under_option", "row_tab", "row_group", "row_mode")
# what a definition written without the camera's menu tree keeps (places, menu_list), said once (a fresh clone, CI)
NO_TREE = "the definition's menu list and each setting's place on the camera stay as the definition has them"


def places(doc: dict) -> dict | None:
    """Each setting's place on the camera, from the camera's menu tree (the Stills menu, and the other shooting modes'
    menus it holds: the mapper's own, private whole, camkit.datafiles) and the setting's own proof paths
    (camkit.placement, the proof viewer's placement): {key: {"row", "row_at"[, "under_option"][, "row_tab"][,
    "row_group"][, "row_mode"]}}. None, so the places stay as they are, for a definition read without its evidence (no
    setting holds its proof paths, proved.menu, which are evidence: camkit.definitions) or with no menu tree on this
    computer (a fresh clone, CI: the places are what is public of the menus)."""
    if not any("menu" in (s.get("proved") or {}) for s in doc["settings"]):
        return None
    tree = definitions.menu_tree_file(definitions.key(doc))
    if not tree.exists():
        datafiles.say_no_menu_tree(tree, NO_TREE)
        return None
    return placement.settings(doc, datafiles.load_menu_tree(tree))


def menu_list(doc: dict) -> list | None:
    """The definition's "menu" (tab, group, label, order): the camera's top rows tab by tab, in its menu's order, from
    the camera's menu tree's Stills tabs (the mapper's own, private whole, camkit.datafiles), the tabs the definition
    has only (no My Menu); its labels as the tree holds them, the ones each setting's "row" begins with, and each
    group under the definition's name for it where the tree reads its icon as a letter. Nothing of the state the walk
    found the camera in: no row state, option or other mode's row; so two owners of the model get the same list. The
    numbering starts where the list's did (else at 1). None, so the list stays as written, with no menu tree on this
    computer (a fresh clone, CI), as the places do."""
    p = definitions.menu_tree_file(definitions.key(doc))
    if not p.exists():
        datafiles.say_no_menu_tree(p, NO_TREE)
        return None
    tree = datafiles.load_menu_tree(p)
    old = doc.get("menu") or []
    start = min((m["order"] for m in old), default=1)
    groups = {}
    for m in old:
        groups.setdefault(m["tab"], []).append(m["group"])
    out = []
    for tb in tree.get("tabs") or []:
        if tb["tab"] not in (doc.get("tabs") or []):
            continue
        for pg in tb.get("pages") or []:
            g = pg["group"]
            icon = [x for x in groups.get(tb["tab"], ()) if x != g and placement.norm(g)[1:] == placement.norm(x)]
            g = icon[0] if len(set(icon)) == 1 and g not in groups.get(tb["tab"], ()) else g
            for r in pg.get("rows") or []:
                label = " ".join((r.get("label") or "").split())
                if label:
                    out.append({"tab": tb["tab"], "group": g, "label": label, "order": start + len(out)})
    return out or None


def with_menu(doc: dict) -> dict:
    """The definition with its "menu" rebuilt from the camera's menu tree (menu_list), in place; as it was without one."""
    got = menu_list(doc)
    if got is not None:
        doc["menu"] = got
    return doc


def with_place(s: dict, place: dict) -> dict:
    """The setting with its place on the camera right after "order", and without one when it has none."""
    out = {}
    for k, v in s.items():
        if k in PLACE_KEYS:
            continue
        out[k] = v
        if k == "order":
            out.update(place)
    return out if "order" in s else {**out, **place}


def from_data(doc: dict) -> dict:
    """The parts of a definition the kit takes from data/ alone, whatever the runs hold: the format and the camera
    section, the memory copies named from it, the project's own help, the menu list (with_menu) and each setting's
    place on the camera's menus; and the kit's own rules over it, the Expert marks, the photographer's words (with_plain_words), each note tidy (with_tidy_note) and its evidence apart (shown in
    Expert mode only), no setting's old `observed` (without_observed: it held the owner's own settings), and no mark on
    the values no option was seen to write (without_held), and no list of the records a proof wrote together
    (without_written_with: it told how the camera was set).
    main() ends the same way, so on the committed data this gives the committed definition."""
    doc = with_menu(with_camera(doc))
    without_observed(doc, say=False)
    without_held(doc)
    without_written_with(doc)
    mirror_names(doc)
    own_help(doc)
    doc["layouts"] = [with_evidence_apart(with_tidy_note(lay)) for lay in doc["layouts"]]
    found, slots, mirror = places(doc), mymenu_slots(doc), mirror_of(doc)
    names = sorted({s["name"] for s in doc["settings"]}, key=len, reverse=True)

    def placed(s):
        return s if found is None else with_place(s, found.get(s["key"], {}))
    doc["settings"] = [with_expert(placed(with_plain_words(with_evidence_apart(with_tidy_note(s)), names)), slots, mirror)
                       for s in doc["settings"]]
    return doc


def text(doc: dict) -> str:
    """A definition's public file as definitions.write writes it (lean: its evidence apart, camkit.definitions)."""
    return definitions.text(doc)


def reset_refusal(doc: dict) -> str | None:
    """Why the camera's public reset file (data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json) must not be
    rewritten, in plain words naming the command that makes it lean (camkit.datafiles.not_lean_words), or None: it is
    lean, or there is none."""
    p = datafiles.reset_file(definitions.key(doc))
    if not p.exists():
        return None
    why = datafiles.reset_not_lean(datafiles.read_reset(p))
    return datafiles.not_lean_words(p, why) if why else None


def reset_names(doc: dict, write: bool) -> int:
    """data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json's setting names and tabs refreshed from the definition by
    key, nothing else in it touched (a setting renamed in RECORD_FIXES reads the same there): the definition is where a
    name or tab is corrected. The public file is the reset file's one source, written and edited by the mapper by hand
    (camkit.datafiles); the kit keeps no private half of it. Written with write, and only when a name or tab differs;
    a file that is not lean is never rewritten: with write that stops (datafiles.Refused, before anything is written:
    reset_refusal), without it is said, each naming kit/tools/move_evidence.py. Returns how many names and tabs
    differ."""
    p = datafiles.reset_file(definitions.key(doc))
    if not p.exists():
        return 0
    why = reset_refusal(doc)
    if why:
        if write:
            raise datafiles.Refused("nothing written: " + why)
        print(f"note: {why}")
        return 0
    reset = datafiles.read_reset(p)
    names = {s["key"]: s for s in doc["settings"]}
    n = 0
    for k, r in (reset.get("records") or {}).items():
        for f in ("name", "tab"):
            if k in names and f in names[k] and r.get(f) != names[k][f]:
                r[f], n = names[k][f], n + 1
    if n and write:
        datafiles.write_reset(p, reset)
        print(f"wrote {paths.shown(p)}: {n} setting names and tabs from the definition")
    elif n:
        print(f"{paths.shown(p)}: {n} setting names and tabs differ from the definition (--write writes them)")
    return n


def refuse_before_writing(target, doc: dict, accept_stale: bool = False, taken_out=()) -> None:
    """Every refusal of a definition's write, before anything is written: evidence that went stale in this run's
    reading (definitions.stale_refusal; accept_stale writes all the same, the evidence kept aside), and a definition
    that lacks the evidence its evidence file holds (definitions.check_write), but what the writer took out on purpose
    and said (`taken_out`)."""
    why = None if accept_stale else definitions.stale_refusal(definitions.newly_stale(doc, target), target)
    if why:
        raise definitions.StaleStop(why)
    definitions.check_write(target, doc, taken_out)


def write_definition(target, doc: dict, accept_stale: bool = False, reset: bool = True, taken_out=()) -> None:
    """The definition `doc` written to `target`, its refusals first (refuse_before_writing, and with reset the reset
    file's: reset_refusal), then (reset) the reset file's names and tabs from it, then the definition itself: no
    refusal arrives after a file was written. `taken_out`: evidence the writer took out on purpose (check_write)."""
    refuse_before_writing(target, doc, accept_stale, taken_out)
    if reset:
        why = reset_refusal(doc)
        if why:
            raise datafiles.Refused("nothing written: " + why)
        reset_names(doc, True)
    definitions.write(target, doc, taken_out)


def say_stale(target) -> None:
    """The one line about the evidence file's "stale" section after a write, when it has one (stale_summary)."""
    line = definitions.stale_summary(target)
    if line:
        print(line)


def refresh_from_data(write: bool, accept_stale: bool = False) -> None:
    """--from-data: every definition's parts from data/, shown, and written with --write: each definition read whole
    (its private evidence put back, where this computer has it), its public file and its evidence written apart. Every
    definition is checked before any is written (its camera's private files still in data/, its stale evidence, its
    evidence guard and its reset file: refuse_before_writing, reset_refusal), so a refusal for one never leaves another
    written."""
    planned = []
    for p, doc in definitions.every():
        if write:                                    # before from_data, which would read past a tree left in data/
            datafiles.stop_if_left(definitions.key(doc), "kit/schema_update.py --from-data --write")
        new = from_data(json.loads(json.dumps(doc)))
        ev = definitions.evidence_path(p)
        pub, evidence = definitions.split(new)
        same_ev = not definitions.has_evidence(evidence) and not ev.exists() or \
            ev.exists() and json.dumps(evidence, indent=1) == ev.read_text(encoding="utf-8")
        same = text(new) == p.read_text(encoding="utf-8") and same_ev
        planned.append((p, new, ev, same))
    if write:
        for p, new, _ev, same in planned:            # every refusal, for every definition, before anything is written
            if not same:
                refuse_before_writing(p, new, accept_stale)
            why = reset_refusal(new)
            if why:
                raise datafiles.Refused("nothing written: " + why)
    for p, new, ev, same in planned:
        reset_names(new, write)
        if same:
            print(f"{p.relative_to(ROOT).as_posix()}: current")
        elif write:
            definitions.write(p, new)
            print(f"wrote {p.relative_to(ROOT).as_posix()} (its evidence in {paths.shown(ev)})")
        else:
            print(f"{p.relative_to(ROOT).as_posix()}: its parts from data/ differ (--write writes them)")
        if write:
            say_stale(p)
