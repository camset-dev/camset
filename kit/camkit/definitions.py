"""Camera definitions: editor/definitions/<model>_fw<firmware>.json, one per model and firmware (docs/decisions/0019).
The one place the kit knows where they are.

    editor/definitions/
      ILCE-1M2_fw4.00.json   the definition: what every record means, and its camera section
      ILCE-1M2_fw4.00.DAT    its sample (the camera section's "sample"): a file that body wrote, personal text removed

A definition is named as data/<model>_fw<fw>/ and docs/models/<model>_fw<fw>.md are, and as the camera's runs are
(runs/<model>_fw<fw>/, camkit.paths). kit/schema_update.py writes the definition of the camera the kit works on; the
editor reads every one it finds (the shipped set, and the user's own folder, where Add definition... copies one).

A definition is lean: it holds what the camera is, the same for every owner of that model and firmware who maps it
completely, and none of how, when, in which run or from which state each thing was proved
(docs/decisions/0016). That evidence is kept in the private overlay, one file per camera beside nothing public:

    private/evidence/<model>_fw<fw>.json   keyed by setting key: the proofs' runs, days, menu rows and name sources,
                                           the notes' evidence, the refusals met, the registrations seen
    private/evidence/<model>_fw<fw>/       the camera's data files that are private, by the data file's name
                                           (camkit.datafiles: the menu tree, the accepted rulings and the record
                                           shapes, private whole; an older whole reset file
                                           kept as an archive, never read)

write() splits a definition the kit holds whole into the two (split), load() puts them back together (merge), so the
kit's passes and tools read the whole as before and the public file never carries the evidence. load_public() reads
the public file alone (the docs, the checks). With no evidence file (a fresh clone, CI) load() gives the lean file.
merge() puts evidence back only onto the public field it is evidence of; what no longer fits (a public proof changed
since) is said, kept out of the whole and kept in the evidence file's "stale" section, never lost and never published;
a writer stops when this run's reading set a proof's evidence, or more than STALE_STOP_SETTINGS settings', aside
(stale_refusal; a newer piece set aside beside an older one is kept under "<field>#2", stale_entry), says when the
section is there (stale_summary) and drops it on request (drop_stale).
write() writes the evidence file first, then the public file, and refuses a definition read without its evidence,
whole or in part (check_write, lost_evidence). Before the evidence file it leaves a marker beside it
(writing_marker: <evidence>.writing, holding the sha256 of the public file it is about to write) and removes it once
the public file is in place: a write cut short is exactly one whose marker is still there. The next write stops on it,
naming kit/schema_update.py --finish-write (cut_short), which writes the public file the marker names, projected from
the evidence, only when its hash matches (finish_write).
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from . import ROOT, paths

DIR = ROOT / "editor" / "definitions"
SHIPPED = DIR                   # the clone's own folder, whose definitions' evidence is kept in EVIDENCE_DIR
DATA = ROOT / "data"            # each camera's data/<model>_fw<fw>/ folder, the camera file among them
# the layout of a definition file the kit writes; the editor refuses a newer one than it reads (DEFINITION_FORMAT in
# editor/src/schema.rs: a test ties the two). 2: the lean definition, its evidence in the private overlay
FORMAT = 2
# where each camera's evidence is kept: the private overlay (git-ignored, docs/decisions/0018); CAMSET_EVIDENCE_DIR
# points it elsewhere (the tests, a check run as a fresh clone would), a relative one from the repo root (ROOT / an
# absolute path is that path)
EVIDENCE_DIR = ROOT / Path(os.environ.get("CAMSET_EVIDENCE_DIR") or Path("private") / "evidence")
EVIDENCE_FORMAT = 1
# a setting's fields that are evidence whole: how its meaning was first found (source), what proves its note
# (note_evidence), the registration that showed a memory copying it (in_sets_proved), and the options its proof runs
# found refused under the state the camera stood in (menu_blocked)
EVIDENCE_FIELDS = ("source", "note_evidence", "in_sets_proved", "menu_blocked")
# the sources of a value's name (proved.names) that are the camera's own word, so the value counts as checked on the
# camera: the lean proof lists such a value among its values (the editor's CAMERA_SOURCES, which it no longer needs)
ESTABLISHING = ("two readers", "one reader", "vision model", "derived", "sampled", "hand table")
SCHEMA_REF = "../../schemas/definition.schema.json"         # the "$schema" a definition names, from its folder
# the definition docs/formats/sony_camset.ksy and the record names it imports describe: the body the kit was built on
REFERENCE = paths.A1II


def path(camera: str) -> Path:
    """editor/definitions/<model>_fw<fw>.json of a camera's key."""
    return DIR / f"{paths.checked(camera, 'a definition')}.json"


def key(doc: dict) -> str:
    """The camera a definition is: <model>_fw<fw> of its one layout."""
    lay = (doc.get("layouts") or [{}])[0]
    return paths.key(lay.get("model") or doc.get("model", ""), lay.get("firmware", ""))


def _where(where) -> Path:
    return Path(where) if str(where).endswith(".json") else path(where)


def evidence_path(p) -> Path:
    """The private evidence file of the definition at `p`: private/evidence/<model>_fw<fw>.json for one in the
    clone's editor/definitions/ (SHIPPED), else <name>.evidence.json beside it (a definition a test writes elsewhere,
    DIR pointed at a folder of its own included)."""
    p = Path(p)
    if p.parent.resolve() == SHIPPED.resolve():
        return EVIDENCE_DIR / p.name
    return p.with_name(p.stem + ".evidence.json")


def load(where, evidence: bool = True) -> dict:
    """A definition by its camera's key or its path, whole: the public file with its private evidence put back
    (merge), when the evidence file is there. evidence=False: the public file alone (load_public)."""
    p = _where(where)
    doc = json.loads(p.read_text(encoding="utf-8"))
    ev = evidence_path(p)
    if evidence and ev.exists():
        doc = merge(doc, json.loads(ev.read_text(encoding="utf-8")), ev)
    return doc


def with_evidence(doc: dict, where) -> dict:
    """A definition already read from `where` (its public file), whole: its private evidence put back when the
    evidence file is there, else as it is."""
    ev = evidence_path(_where(where))
    return merge(doc, json.loads(ev.read_text(encoding="utf-8")), ev) if ev.exists() else doc


def load_public(where) -> dict:
    """The public definition file alone, as the editor and the docs read it."""
    return load(where, evidence=False)


def every(evidence: bool = True) -> list:
    """[(path, definition)] of every definition in editor/definitions/, by file name, each whole (load) or, with
    evidence=False, the public file alone."""
    return [(p, load(p, evidence)) for p in sorted(DIR.glob("*.json"))]


def lean_proof(proved: dict) -> dict:
    """A proof as a definition publishes it: the values a proof on the camera checked ("values": those a proof chose,
    and those whose name has a source on the camera, ESTABLISHING), and for a scale proved by samples whether they lie
    on one line ("sampled": {"linear"}; a scale on its line checks every value, so it lists none). Never the run, the
    day, the menu rows, the name sources, how many samples, nor whether a sample began at the option the camera held:
    two owners mapping the same camera completely get the same lean proof. A lean proof gives itself back."""
    names = proved.get("names") or {}
    checked = set(proved.get("values") or ()) | {int(v) for v, src in names.items() if src in ESTABLISHING}
    sampled = proved.get("sampled")
    out = {}
    if sampled is None or (sampled.get("linear") is not True and checked):
        out["values"] = sorted(checked)
    if sampled is not None:
        out["sampled"] = {"linear": sampled.get("linear")}
    return out


def split(doc: dict) -> tuple:
    """(the public definition, its evidence) of a definition the kit holds whole. The public one keeps every field in
    its place but EVIDENCE_FIELDS, a lean proof (lean_proof), and no date in unproved_reason and unproved_sets nor
    evidence in not_offered; a layout keeps no note_evidence. The evidence holds what went, by setting key (and by
    layout signature), so merge() gives the whole back; a setting with nothing removed has no entry."""
    settings, layouts, pub = {}, {}, {}
    for k, v in doc.items():
        if k == STALE:
            continue
        if k == "layouts":
            lays = []
            for lay in v:
                if lay.get("note_evidence"):
                    layouts[lay.get("signature", "")] = {"note_evidence": lay["note_evidence"]}
                lays.append({kk: vv for kk, vv in lay.items() if kk != "note_evidence"})
            pub[k] = lays
        elif k == "settings":
            pub[k] = []
            for s in v:
                out, ev = {}, {}
                for f, x in s.items():
                    if f in EVIDENCE_FIELDS:
                        ev[f] = x
                    elif f == "proved" and isinstance(x, dict):
                        out[f] = lean_proof(x)
                        if out[f] != x:
                            ev[f] = x
                    elif f in ("unproved_reason", "unproved_sets") and isinstance(x, dict) and "date" in x:
                        out[f] = {kk: vv for kk, vv in x.items() if kk != "date"}
                        ev[f] = {"date": x["date"]}
                    elif f == "not_offered" and isinstance(x, list):
                        out[f] = [{kk: vv for kk, vv in m.items() if kk != "evidence"} for m in x]
                        said = [{"value": m.get("value"), "evidence": m["evidence"]} for m in x if m.get("evidence")]
                        if said:
                            ev[f] = said
                    else:
                        out[f] = x
                pub[k].append(out)
                if ev:
                    order = ("source", "proved", "note_evidence", "in_sets_proved", "menu_blocked", "unproved_reason",
                             "unproved_sets", "not_offered")
                    settings[s["key"]] = {f: ev[f] for f in order if f in ev}
        else:
            pub[k] = v
    lay = (doc.get("layouts") or [{}])[0]
    evidence = {"$comment": "Private: how, when and from which state each thing in the definition of the same name was "
                            "proved (docs/decisions/0016). Written by kit/schema_update.py --write; never published.",
                "evidence_format": EVIDENCE_FORMAT, "model": lay.get("model") or doc.get("model", ""),
                "firmware": lay.get("firmware", ""), "layouts": layouts, "settings": settings}
    if doc.get(STALE):
        evidence["stale"] = doc[STALE]          # what merge() found no longer fits (kept, never published)
    return pub, evidence


# a run's folder (written / or, on Windows, \), a kit2_ run name or an ISO date: none is anywhere in a public definition
# (evidence_in_public)
RUN_OR_DAY = re.compile(r"runs[/\\]|kit2_|\b20\d\d-\d\d-\d\d\b")
# a download's or a frame's file name ("00420_after.DAT", "00145_enter.png"): a proof's, never a public file's; but the
# camera's own file names, its sample and the suffix of the files it saves, which a camera file and a definition's
# camera section give (OWN_FILE_NAMES), are what the camera is (file_names)
FILE_NAME = re.compile(r"[\w.-]*\.(?:DAT|png|jpg)\b")
OWN_FILE_NAMES = ("sample", "save_name")


def file_names(doc, camera: str | None = "camera") -> list:
    """Every download's or frame's file name (FILE_NAME) in the JSON document `doc`, in order, but the camera's own
    file names (OWN_FILE_NAMES) in its camera section: `camera` names that section's key in `doc` (a definition's
    "camera"), or None for a camera file, whose own top level it is."""
    if isinstance(doc, dict):
        if camera is None:
            doc = {k: v for k, v in doc.items() if k not in OWN_FILE_NAMES}
        elif isinstance(doc.get(camera), dict):
            doc = {**doc, camera: {k: v for k, v in doc[camera].items() if k not in OWN_FILE_NAMES}}
    return FILE_NAME.findall(json.dumps(doc, ensure_ascii=False))


def evidence_in_public(doc: dict, text: str = None) -> list:
    """Every place a public definition carries evidence, in words: a field of EVIDENCE_FIELDS (or the old observed,
    written_with) on a setting, a proof key but values and sampled, a sample's key but linear, a date in
    unproved_reason or unproved_sets, not_offered's evidence, a layout's note_evidence, in the file's text (`text`,
    else the definition as JSON) a run's folder, a kit2_ run name or an ISO date, and anywhere but the camera's own
    file names a download's or a frame's file name (file_names). Empty for a lean one."""
    text = json.dumps(doc) if text is None else text
    found = [f"names {m!r}" for m in RUN_OR_DAY.findall(text)]
    found += [f"names the file {m!r}" for m in file_names(doc)]
    found += ["a layout's note_evidence" for lay in doc.get("layouts") or [] if "note_evidence" in lay]
    if STALE in doc:
        found.append(f"the evidence kept aside ({STALE})")
    for s in doc.get("settings") or []:
        k = s.get("key")
        found += [f"{k}: {f}" for f in (*EVIDENCE_FIELDS, "observed", "written_with") if f in s]
        p = s.get("proved")
        if isinstance(p, dict):
            found += [f"{k}: proved.{f}" for f in p if f not in ("values", "sampled")]
            found += [f"{k}: proved.sampled.{f}" for f in (p.get("sampled") or {}) if f != "linear"]
        found += [f"{k}: {f}.date" for f in ("unproved_reason", "unproved_sets") if "date" in (s.get(f) or {})]
        found += [f"{k}: not_offered's evidence" for m in s.get("not_offered") or [] if "evidence" in m]
    return found


def has_evidence(evidence: dict) -> bool:
    return bool(evidence.get("settings") or evidence.get("layouts") or evidence.get("stale"))


# the key a definition merge() gives carries the evidence that no longer fits the public file under (STALE), so the
# next write() keeps it in the evidence file's "stale" section; split() takes it out, so no public file carries it
STALE = "$stale_evidence"
_SAID_STALE = set()             # (evidence file, setting key or layout, field) said once a process (merge)


def _say_stale(where, what: str, field: str, why: str) -> None:
    sig = (str(where), what, field)
    if sig not in _SAID_STALE:
        _SAID_STALE.add(sig)
        print(f"evidence: {what}: its {field} in {where or 'the evidence'} no longer fits the public definition ({why}); "
              "left out of the definition the kit reads and kept aside in the evidence file's \"stale\" section",
              file=sys.stderr)


def merge(doc: dict, evidence: dict, where=None) -> dict:
    """The whole definition from the public one and its evidence (split's other half): each field back in the place the
    kit writes it (source after name, note_evidence after note, in_sets_proved after in_sets, menu_blocked last), the
    whole proof for the lean one, the dates and not_offered's evidence back in their entries.

    Evidence is put back only onto what it is evidence of: a whole proof only where its lean form (lean_proof) is the
    public "proved", a date only where the public unproved_reason or unproved_sets is there, a not-offered mark's
    evidence only on the public mark of its value, a layout's note_evidence only on the layout of its signature. What
    no longer fits (a contributor changed or took out the public field since, or the setting is gone) is said once a
    process (setting key and field, `where` the evidence file) and left out, so it never reaches the public file again
    on the next write; it is kept, with the evidence file's own "stale" section, under the merged definition's STALE
    key, which split() writes back into that section: nothing of the mapper's evidence is lost."""
    doc = json.loads(json.dumps(doc))
    old = evidence.get("stale") or {}
    stale = {"settings": json.loads(json.dumps(old.get("settings") or {})),
             "layouts": json.loads(json.dumps(old.get("layouts") or {}))}

    def aside(part: str, what: str, field: str, value, why: str):
        _say_stale(where, what, field, why)
        got = stale[part].setdefault(what, {})
        if field == "not_offered":                 # marks one by one, or a gone setting's whole list
            marks = got.setdefault(field, [])
            marks.extend(m for m in (value if isinstance(value, list) else [value]) if m not in marks)
        else:
            got.update(stale_entry(got, field, value))
    by_sig = evidence.get("layouts") or {}
    sigs = {lay.get("signature", "") for lay in doc.get("layouts") or []}
    for sig, ev in by_sig.items():
        if sig not in sigs:
            for f, v in ev.items():
                aside("layouts", sig, f, v, "the definition has no layout of that signature")
    doc["layouts"] = [_with_after(lay, "note", {"note_evidence": by_sig[lay.get("signature", "")]["note_evidence"]})
                      if "note_evidence" in by_sig.get(lay.get("signature", ""), {}) else lay
                      for lay in doc.get("layouts") or []]
    by_key = evidence.get("settings") or {}
    keys = {s.get("key") for s in doc.get("settings") or []}
    for k, ev in by_key.items():
        if k not in keys:
            for f, v in ev.items():
                aside("settings", k, f, v, "the definition has no setting of that key")
    out = []
    for s in doc.get("settings") or []:
        k = s.get("key")
        ev = by_key.get(k)
        if not ev:
            out.append(s)
            continue
        s = dict(s)
        if "proved" in ev:
            # the lean forms compared on both sides, so a later change to what lean_proof keeps (a field added or taken
            # out) leaves every proof that still fits in place, instead of setting each one aside as stale
            if isinstance(ev["proved"], dict) and isinstance(s.get("proved"), dict) \
                    and lean_proof(ev["proved"]) == lean_proof(s["proved"]):
                s["proved"] = ev["proved"]
            else:
                aside("settings", k, "proved", ev["proved"], "the public proof is not this proof's lean form"
                      if "proved" in s else "the public setting has no proof")
        for f in ("unproved_reason", "unproved_sets"):
            if f in ev:
                if isinstance(s.get(f), dict):
                    s[f] = {**s[f], **ev[f]}
                else:
                    aside("settings", k, f, ev[f], f"the public setting has no {f}")
        if "not_offered" in ev:
            have = {json.dumps(m.get("value")) for m in s.get("not_offered") or [] if isinstance(m, dict)}
            said = {}
            for m in ev["not_offered"]:
                if json.dumps(m.get("value")) in have:
                    said[json.dumps(m.get("value"))] = m["evidence"]
                else:
                    aside("settings", k, "not_offered", m, "the public setting has no not-offered mark of that value")
            if said:
                s["not_offered"] = [_with_after(m, "menu" if "menu" in m else "why",
                                                {"evidence": said[json.dumps(m.get("value"))]})
                                    if json.dumps(m.get("value")) in said else m for m in s["not_offered"]]
        for f, after in (("source", "name"), ("note_evidence", "note"), ("in_sets_proved", "in_sets")):
            if f in ev:
                s = _with_after(s, after, {f: ev[f]})
        if "menu_blocked" in ev:
            s["menu_blocked"] = ev["menu_blocked"]
        out.append(s)
    doc["settings"] = out
    if old.get("settings") or old.get("layouts"):
        n = len(old.get("settings") or {}) + len(old.get("layouts") or {})
        sig = (str(where), "*", "*")
        if sig not in _SAID_STALE:
            _SAID_STALE.add(sig)
            print(f"evidence: {n} settings or layouts have evidence kept aside in the \"stale\" section of "
                  f"{where or 'the evidence'}, which no longer fit the public definition; look at each and take it "
                  "out of that section when it is of no more use", file=sys.stderr)
    stale = {part: v for part, v in stale.items() if v}
    if stale:
        doc[STALE] = stale
    return doc


def stale_entry(got: dict, field: str, value) -> dict:
    """{name: value} to add to a setting's (or layout's) entry `got` of the "stale" section for the evidence `value` of
    `field` set aside now: under the field's own name when the entry has none; never over an older piece kept there,
    which stays as it was: the newer one takes the next free name "<field>#2", "#3", ...; nothing when the entry holds
    that very value already (under the field's name or one of its numbered ones). A numbered name is a stale item of
    its own (stale_items), so a proof set aside again after an older one counts for the stop (stale_refusal)."""
    same = [k for k in got if k == field or k.startswith(field + "#")]
    if any(got[k] == value for k in same):
        return {}
    if field not in got:
        return {field: value}
    n = 2
    while f"{field}#{n}" in got:
        n += 1
    return {f"{field}#{n}": value}


def stale_field(f: str) -> str:
    """The field a stale item's name stands for: "proved#2" (a newer piece kept beside an older one) is "proved"."""
    return f.split("#", 1)[0]


def _with_after(item: dict, after: str, fields: dict) -> dict:
    """`item` with `fields` right after its key `after` (at the end when it has none), any old copy of them gone."""
    out, placed = {}, False
    for k, v in item.items():
        if k in fields:
            continue
        out[k] = v
        if k == after:
            out.update(fields)
            placed = True
    if not placed:
        out.update(fields)
    return out


def active(required: bool = True) -> Path | None:
    """The definition of the camera the kit works on (camkit.paths), there or not; None with no camera named and
    required=False."""
    got = paths.camera()
    if got is None:
        if required:
            raise paths.NoCamera(paths.no_camera_message())
        return None
    return path(got[0])


def sample(doc: dict, where: Path = None) -> Path | None:
    """A definition's sample file (its camera section's "sample", beside it), or None when it names none."""
    name = (doc.get("camera") or {}).get("sample")
    return (Path(where).parent if where else DIR) / name if name else None


def data_dir(camera: str) -> Path:
    return DATA / camera


def camera_file(camera: str) -> Path:
    """data/<model>_fw<fw>/camera_<model>_fw<fw>.json: the camera section's one source."""
    return data_dir(camera) / f"camera_{camera}.json"


def menu_tree_file(camera: str) -> Path:
    """private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json: the camera's menus, row by row, as the kit walked
    them, private whole (camkit.datafiles): what the walk found greyed, unread or listed from the held option is the
    state the camera stood in. The definition's own menu list and each setting's place are the public menu structure.
    Only a path: nothing is read or moved (one left at its old public place, data/<model>_fw<fw>/, is moved by
    kit/tools/move_evidence.py alone: camkit.datafiles.stop_if_left)."""
    return EVIDENCE_DIR / camera / f"menu_tree_{camera}.json"


def _dump(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".part")              # never a half-written contract
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
    tmp.replace(p)


class WouldLoseEvidence(SystemExit):
    """write() refused, in plain words: the definition was read without its evidence (load_public), whole or in part,
    and writing it would empty the evidence file that is there or drop part of it (lost_evidence)."""


def lost_evidence(doc: dict, have: dict) -> list:
    """["<setting key>: <field>"] of the evidence the evidence file `have` holds for a setting that `doc` (a whole
    definition about to be written) still has the public part of, but not the evidence: a whole proof whose lean form
    is the public "proved" `doc` holds lean, a date of an unproved_reason or unproved_sets `doc` holds without one, a
    not-offered mark's evidence where `doc` has the mark without it. Exact: a run that proves again writes a whole proof,
    and one that changes a public field changes what the evidence is checked against. A proof read lean still counts
    as lean when a pass has since put the sources of its names on it (proved.names, which writer/proofs.with_names adds
    to every proof): it holds none of the run, day and rows the evidence file keeps (until 2026-11-13 the names hid it,
    and such a write dropped them). The fields that are evidence
    whole (EVIDENCE_FIELDS: source, note_evidence, in_sets_proved, menu_blocked) and a layout's note_evidence have no
    public part to tell a dropped one from one a run took out, so they are not checked here (only a definition with no
    evidence at all is refused for them, write)."""
    out = []
    by_key = {s.get("key"): s for s in doc.get("settings") or []}
    for k, ev in (have.get("settings") or {}).items():
        s = by_key.get(k)
        if s is None:
            continue
        p = s.get("proved")
        if isinstance(ev.get("proved"), dict) and isinstance(p, dict) and set(p) - {"names"} <= {"values", "sampled"} \
                and lean_proof(ev["proved"]) == lean_proof(p) \
                and {f: x for f, x in p.items() if f != "names"} != {f: x for f, x in ev["proved"].items() if f != "names"}:
            out.append(f"{k}: proved")
        for f in ("unproved_reason", "unproved_sets"):
            if "date" in (ev.get(f) or {}) and isinstance(s.get(f), dict) and "date" not in s[f]:
                out.append(f"{k}: {f}.date")
        said = {json.dumps(m.get("value")) for m in ev.get("not_offered") or [] if isinstance(m, dict)}
        if any(isinstance(m, dict) and json.dumps(m.get("value")) in said and not m.get("evidence")
               for m in s.get("not_offered") or []):
            out.append(f"{k}: not_offered's evidence")
    return out


class CutShort(SystemExit):
    """A write refused, in plain words: the last write of the definition was cut short (its marker is still there,
    writing_marker), and kit/schema_update.py --finish-write finishes it."""


def writing_marker(where) -> Path:
    """The marker a write leaves beside the evidence file while it writes (<evidence>.writing): it holds the sha256 of
    the public file the write is about to write; there after the write only when the write was cut short."""
    ev = evidence_path(_where(where))
    return ev.with_name(ev.name + ".writing")


def cut_short(where) -> str | None:
    """Why no write of the definition at `where` may start, in words, when its last write was cut short (its marker is
    still there, writing_marker), naming --finish-write; None otherwise."""
    marker = writing_marker(where)
    if not marker.exists():
        return None
    return (f"nothing written: the last write of {_where(where).name} was cut short: its marker "
            f"{paths.shown(marker)} is still there (a write leaves it while it writes the evidence file and then the "
            "definition, and removes it once both are in place). Finish that write first with\n"
            "  .venv/bin/python kit/schema_update.py --finish-write\n"
            "(on Windows: .venv\\Scripts\\python kit\\schema_update.py --finish-write), which writes the definition "
            "that write was writing, checked against the marker, and nothing else, then run this command again.")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_write(p: Path, doc: dict, taken_out=()) -> None:
    """What write() refuses, before anything is written: a write cut short still unfinished (CutShort: its marker
    there, cut_short); a definition with no evidence at all where the evidence file holds some, or one that lacks part
    of the evidence that file holds for its settings (lost_evidence): it was read without it (load_public), whole or in
    part (WouldLoseEvidence). `taken_out`: lost_evidence's words ("<key>: <field>") for evidence the writer took out on
    purpose, which it said (the plain pass, when the hand evidence no longer gives a reason's day or a mark's
    evidence): not refused."""
    why = cut_short(p)
    if why:
        raise CutShort(why)
    ev = evidence_path(p)
    if not ev.exists():
        return
    have = json.loads(ev.read_text(encoding="utf-8"))
    evidence = split(doc)[1]
    if not has_evidence(evidence) and has_evidence(have):
        raise WouldLoseEvidence(f"nothing written: {p} holds none of the evidence that {ev} keeps for it, so it was "
                                "read without it (definitions.load_public), and writing it would empty that file. "
                                "Read it with definitions.load(), which puts the evidence back, and write that.")
    lost = [x for x in lost_evidence(doc, have) if x not in set(taken_out)]
    if lost:
        raise WouldLoseEvidence(f"nothing written: {p} lacks part of the evidence that {ev} keeps for its settings "
                                f"({len(lost)}: {', '.join(lost[:5])}{', ...' if len(lost) > 5 else ''}), so it was "
                                "read without it, or that part was taken out; writing it would drop that evidence. "
                                "Read it with definitions.load(), which puts the evidence back, and write that.")


def write(p: Path, doc: dict, taken_out=()) -> Path | None:
    """The definition's own format (one-space indent, ASCII), written whole or not at all: its evidence into the
    private evidence file (evidence_path; private/ made as needed) when there is any or the file is there already,
    first, then the public file lean (split), each through a temporary file, so a write that fails half way never
    loses this write's evidence. Before the evidence file, the marker (writing_marker) holding the sha256 of the public
    file about to be written; removed once the public file is in place, so a marker left says the write was cut short
    (finish_write). Returns the evidence file written, or None. Refused (check_write): a write cut short still
    unfinished (CutShort), a definition with no evidence at all where the evidence file holds some, or one lacking part
    of it (WouldLoseEvidence) but what the writer took out on purpose (`taken_out`, check_write)."""
    check_write(p, doc, taken_out)
    pub, evidence = split(doc)
    ev = evidence_path(p)
    if not (has_evidence(evidence) or ev.exists()):
        _dump(Path(p), pub)                          # one file: nothing to cut short between two
        return None
    marker = writing_marker(p)
    marker.parent.mkdir(parents=True, exist_ok=True)
    tmp = marker.with_name(marker.name + ".part")
    tmp.write_text(json.dumps({"public": Path(p).name, "sha256": _sha256(json.dumps(pub, indent=1))}, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    tmp.replace(marker)
    _dump(ev, evidence)
    _dump(Path(p), pub)
    marker.unlink()
    return ev


# ---------------------------------------------------------------- the evidence that no longer fits ("stale")

# a write stops (StaleStop) when this run's reading of the definition set aside a proof's evidence, or the evidence of
# more settings or layouts than this, that the evidence file did not hold aside before: a key renamed or a public
# proof changed since (a merge, a contributor's edit) would otherwise orphan the mapping's evidence unnoticed
STALE_STOP_SETTINGS = 5


class StaleStop(SystemExit):
    """A write stopped before anything was written, in plain words: evidence went stale in this run (stale_refusal)."""


def stale_items(stale: dict) -> list:
    """[(part, setting key or layout signature, field)] of a "stale" section (or a merged definition's STALE)."""
    return sorted((part, what, f) for part in ("settings", "layouts")
                  for what, fields in ((stale or {}).get(part) or {}).items() for f in fields)


def _stale_in_file(where) -> dict:
    ev = evidence_path(_where(where))
    return (json.loads(ev.read_text(encoding="utf-8")).get("stale") or {}) if ev.exists() else {}


def newly_stale(doc: dict, where) -> list:
    """The stale items (stale_items) a whole definition read in this run holds aside that the evidence file of the
    definition at `where` did not hold aside before: evidence that went stale in this run's reading (merge)."""
    had = set(stale_items(_stale_in_file(where)))
    return [x for x in stale_items(doc.get(STALE) or {}) if x not in had]


def stale_refusal(new: list, where) -> str | None:
    """Why a write stops, in words, or None: the last write cut short (cut_short: its marker still there), whatever
    went stale; else on the evidence that went stale in this run (`new`, newly_stale): a proof's evidence among it, or
    more than STALE_STOP_SETTINGS settings and layouts."""
    cut = cut_short(where)
    if cut:                                          # a write cut short: finished first, whatever went stale
        return cut + " Do not write with --accept-stale here: it would set that write's proofs aside."
    owners = {(part, what) for part, what, _ in new}
    proofs = any(stale_field(f) == "proved" for _, _, f in new)
    if not proofs and len(owners) <= STALE_STOP_SETTINGS:
        return None
    lines = [f"  {what}: {f}" for _, what, f in new[:40]] + ([f"  ... and {len(new) - 40} more"] if len(new) > 40 else [])
    return (f"nothing written: reading {_where(where).name} with its evidence set aside the evidence of "
            f"{len(owners)} settings or layouts that no longer fit the public definition "
            f"({'a proof among them' if proofs else 'more than a handful'}). A setting's "
            "key renamed or a public proof changed since (a merge, a branch switch, an edit) does that, and writing "
            "now would leave that evidence aside for good. These (key and field):\n" + "\n".join(lines) +
            "\nIf the public definition is not as it should be, put it back (git restore, or the merge undone) and run "
            "again. If it is right, write with --accept-stale: the evidence is kept in the evidence file's \"stale\" "
            "section, never published, and kit/schema_update.py --drop-stale --write removes it later.")


class Unfinished(SystemExit):
    """finish_write refused, in plain words: no write was cut short, or the one that was cannot be finished here."""


def finish_write(where) -> tuple:
    """kit/schema_update.py --finish-write: the write cut short (its marker there, writing_marker) finished: the public
    file it was writing, projected from the evidence file as it stands (each setting's public proof the lean form of
    the whole proof the evidence holds for it, nothing else of the public file changed, the evidence file not
    touched), written only when its sha256 is the marker's, then the marker removed. Returns (the keys whose proofs it
    wrote, what it did in words). With the public file already the marker's (cut short after it), not there at all
    (cut short in its first write), or the two files agreeing still (cut short before the evidence file changed what
    the definition shows), only the marker is removed. Refused (Unfinished), nothing written: no marker (no write was cut short), a marker that cannot be read,
    or a projection that is not the marker's file (the write changed more than proofs): it says how to go on."""
    import contextlib
    import io
    p = _where(where)
    ev = evidence_path(p)
    marker = writing_marker(p)
    by_hand = (f"Only if you are sure, remove the marker by hand:\n  rm '{marker}'\n(Windows: del \"{marker}\") and run "
               "your --write again: it reads the evidence file as it stands, and stops on what no longer fits.")
    if not marker.exists():
        raise Unfinished(f"nothing to finish: no write of {paths.shown(p)} was cut short (a write leaves "
                         f"{paths.shown(marker)} only while it writes). Nothing was written.")
    try:
        want = json.loads(marker.read_text(encoding="utf-8"))["sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        raise Unfinished(f"nothing written: the marker {paths.shown(marker)} cannot be read, so nothing says which "
                         f"definition the write cut short was writing. {by_hand}") from None
    if not p.exists():                              # the first write of it: nothing public to be out of step with
        marker.unlink()
        return [], (f"{paths.shown(p)} was never written: the write cut short was its first, so there is nothing to "
                    "finish. Its marker removed, nothing else changed. Run your command again: it writes the whole "
                    "definition.")
    current = p.read_text(encoding="utf-8")
    if _sha256(current) == want:
        marker.unlink()
        return [], (f"{paths.shown(p)} is already the definition the write cut short was writing (it stopped after "
                    "writing it): its marker removed, nothing else changed. Run your command again.")
    pub = json.loads(current)
    have = json.loads(ev.read_text(encoding="utf-8")) if ev.exists() else {}
    proofs = have.get("settings") or {}
    keys = []
    for s in pub.get("settings") or []:
        whole = (proofs.get(s.get("key")) or {}).get("proved")
        if isinstance(whole, dict) and s.get("proved") != lean_proof(whole):
            s["proved"] = lean_proof(whole)
            keys.append(s["key"])
    if _sha256(json.dumps(pub, indent=1)) == want:
        _dump(p, pub)
        marker.unlink()
        return keys, (f"wrote {paths.shown(p)}: the proofs of {len(keys)} settings as its evidence file gives them, "
                      "which the write cut short had not written (checked against its marker); nothing else changed. "
                      "Run your command again.")
    if not keys:
        with contextlib.redirect_stderr(io.StringIO()):
            agree = not newly_stale(merge(json.loads(current), have, ev), p)
        if agree:
            marker.unlink()
            return [], (f"{paths.shown(p)} and its evidence file agree: the write was cut short before it changed "
                        "what the definition shows, so there is nothing to finish. Its marker removed, nothing else "
                        "changed. Run your command again: it writes the whole definition.")
    raise Unfinished(f"nothing written: the definition the write cut short was writing is not {paths.shown(p)} with "
                     "its evidence file's proofs put in (the marker's sha256 is another), so that write changed more "
                     f"than proofs and cannot be finished from the evidence. {by_hand}")


def stale_summary(where) -> str | None:
    """One line when the evidence file of the definition at `where` holds a "stale" section: how many settings and
    layouts, where, and how to look at it and drop it; None without one."""
    stale = _stale_in_file(where)
    owners = {(part, what) for part, what, _ in stale_items(stale)}
    if not owners:
        return None
    ev = evidence_path(_where(where))
    return (f"evidence: {len(owners)} settings or layouts have evidence kept aside in the \"stale\" section of "
            f"{paths.shown(ev)} (it no longer fits the definition); look at it there (kit/schema_update.py "
            "--drop-stale lists it), and kit/schema_update.py --drop-stale --write removes it once it is of no more use")


def drop_stale(where, write: bool = True) -> list:
    """The "stale" section taken out of the evidence file of the definition at `where` (with write; else only shown):
    the items it held (stale_items), the rest of the file as it was."""
    ev = evidence_path(_where(where))
    if not ev.exists():
        return []
    have = json.loads(ev.read_text(encoding="utf-8"))
    got = stale_items(have.get("stale") or {})
    if got and write:
        have.pop("stale")
        _dump(ev, have)
    return got


def text(doc: dict) -> str:
    """A definition's public file as write() writes it."""
    return json.dumps(split(doc)[0], indent=1)
