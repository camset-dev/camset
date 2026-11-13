"""Pass 2's proofs into the camera's definition (editor/definitions/<model>_fw<fw>.json, docs/decisions/0019): the
camera's own labels, the values the definition lacked, and the evidence, as additive fields.

    .venv/bin/python kit/pass2_report.py && .venv/bin/python kit/schema_update.py [--write]
    .venv/bin/python kit/schema_update.py --from-data [--write]   # every definition's parts from data/ only, no runs
    .venv/bin/python kit/schema_update.py --option-trees [--write]  # only the option trees from the runs, with the audit
    .venv/bin/python kit/schema_update.py --drop-stale [--write]    # the evidence file's "stale" section listed (removed)
    .venv/bin/python kit/schema_update.py --finish-write            # a write cut short (its marker left), finished

Per record proved on the camera (kit2_pass2/report.json in the camera's runs/<model>_fw<fw>/, camkit.paths):
  values        a proved value whose schema label differs gets the label the camera's screen showed
                (cleaned of OCR slips; carousel options per CAROUSEL below); values the schema lacked
                are added. Unproved values keep their labels, except Focus Area's, which take the
                names the camera lists on Focus Area Limit (firmware 4.00 renamed Free Size to Custom).
  proved        {"run", "date", "values": [...], "menu": [row paths]}. Number records get
                "sampled": {"proofs", "linear"} and no values: each sample changes one digit of the
                camera's own setting, so the stored numbers would give that setting away. Of the proof the
                definition held before, only a value a counted proof line still wrote stays beside the report's,
                and is listed ("kept"); never an old menu row or count (kept_proof)
  written_with  not written (without_written_with): which records a proof wrote together stays in pass 2's report;
                beside it a definition would tell how the camera was set when the proofs were made (decision 16)
  menu_blocked  options the camera refused in the menu, with the reason it gave (not "refused":
                that field lists values the camera rejects in a loaded file)
  option_tree   a carousel's options as the camera lays them out, each main option with the choices on its own
                axis (Focus Area's Spot with its sizes), from the run's dialog and axis proofs (camkit.option_tree);
                a setting the proofs give none loses an old one. Untouched when the run has no proofs.
  proved.names  what backs each value's name (NAME_SOURCES: two readers, one reader, the vision model, the kept
                schema label, a hand table, a rule's copy, sampled), from the report's `names` (with_names); a
                value no option was seen to write is named by its readers like any other, and an old "inferred" or
                "held" is taken out (without_held, decision 16)
  shown_as      {"divide", "decimals"} for a number the camera shows scaled ("75%" stored 7500), from the side-list
                and field proofs (scaled_numbers), the unit from the camera's text
  observed      taken out of every setting (without_observed): the old lists of the values camera files held
                came from downloads, the owner's own settings among them (decision 16); an editor offers outside
                Expert mode what `proved` establishes (docs/DATA_CONTRACTS.md)
  disputed      true on a record pass2_report found not one to one: its proof is taken out (disputed_out)
  in_sets_proved  {"run", "date", "slot"} on a live setting whose memory copy a registration was seen to take
                (pass2_report.registration_mirrors: kit/provers/memreg_run.py's "registration mirror" lines), right
                after in_sets (with_in_sets_proved); a memory record no live record holds (a frame's place) takes the
                values its registrations wrote as proved (pass2_report.mirrored_values: framepos_run.py --zone-grid)
  video_system_values  {"NTSC": [...], "PAL": [...]}: the values a setting's menus offer under one video system only,
                from the rows walked under each, their downloads' headers saying which (writer/offered.py), or the hand
                table's VIDEO_SYSTEM_VALUES where no proof walked both
  copies, copy_of  a live setting's per-mode copies (the hand table's COPIES: the Picture Profile parameters and the
                profile in use, and the other settings Different Set for Still/Mv keeps per mode), written only while a
                sample of the camera's downloads bears out that its value equals one of its copies (writer/copies.py)
  note_evidence the owner's allowance a proof carries ("allowance": "the owner allowed <row> remotely, <date>", a
                never-open row proved with the owner's word) is added to the evidence of each setting it proved, once
                (with_allowances); a hand table's proof says it in its own "allowance"
Number records (with a range, proved through number fields or a side list of numbers) keep their
sample labels: their values are the numbers themselves.

--write refuses (exit 1, each listed) while the report holds a question the pass does not settle (questions): a
conflict whose label it keeps against the camera's reading, a new record it does not add, a record not one to one, a
name dispute or a carried-over value outside a hand rule, that the mapper's accepted file (private whole:
private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json, camkit.datafiles) does not accept (gate); --force writes
anyway, loudly. It also stops, before anything is written, when evidence went stale in this run's reading of the
definition (camkit.definitions.stale_refusal: a proof's, or more than five settings' or layouts', say after a key was
renamed by a merge); --accept-stale writes anyway, the evidence kept in the evidence file's "stale" section. A write
leaves a marker beside the evidence file while it writes (private/evidence/<model>_fw<fw>.json.writing, holding the
sha256 of the definition it is about to write) and removes it once the definition is in place; while one is left, the
last write was cut short, and every write stops and names --finish-write, which writes the definition that write was
writing (the evidence file's proofs' lean forms put into it, nothing else), only when its sha256 is the marker's, and
removes the marker (camkit.definitions.finish_write). After a write one line says when the "stale" section is there; --drop-stale lists
it, by setting key and field, and removes it only with --write. Every
refusal comes before anything is written (writer.fromdata.write_definition: the definition's, then the reset file's,
then the definition), and --write stops in plain words while the mapper's menu tree, accepted rulings or record shapes
are still at their old place in data/ (kit/tools/move_evidence.py moves them).
Rerunning gives the same file: a note line a pass adds is added once (add_line), a note a table writes whole is
compared with its evidence apart (note_is), and the proofs are kept as above. Prints every label it changes or adds;
never prints the camera's own settings (no start values). Without --write it only shows.

It writes the definition of the camera the kit works on (camkit.paths: --camera, CAMSET_CAMERA or
private/config.json), editor/definitions/<model>_fw<fw>.json, and refuses a run whose downloads are another camera
or firmware than that definition's (camkit.models): a body's proofs land in its own definition only. The ILCE-1M2
firmware 4.00's hand tables (CAROUSEL, the label tables and the rest: its data file,
data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json, which writer/hand_tables.py reads) and the fixes of its pass
below (the 0x04e2 range, the runs it reads) apply to that definition alone (TODO: each camera's pass reads its own
hand tables, docs/decisions/0020). Records pass2_report marks "not one to one" are left out and listed.

Any other camera's definition gets the plain pass (generic below), with none of those tables: each proved value the
label the camera showed, a record the definition lacks a setting named by its menu row, and the evidence. A camera
with no definition yet gets one started from its data/ folder and the run's newest download (seed below): its model
and layout signature, its tabs from the camera file's tab colours, and the settings the report proves. That is a
first definition, every name the camera's own; what the mapping finds by hand goes into its data/ files and, with
--write again, into it.

The parts of a definition the kit takes from data/ alone (from_data below) are written on every run: "$schema" and
"definition_format" first, the camera section copied from data/<model>_fw<fw>/camera_<model>_fw<fw>.json, the memory
copies named from it, the project's own help from data/<model>_fw<fw>/help_<model>_fw<fw>.json, each setting's
place on the camera's menus ("row", "row_at", "under_option", "row_tab", "row_group", "row_mode": the row its proof
went through in the camera's menu tree, private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json, by
camkit.placement, the proof viewer's placement; kept as they are where that tree or the evidence is not here), "expert": true on the settings shown in Expert mode only, and each note's evidence (the runs and the days that prove it) taken out
into "note_evidence", which the editor shows in Expert mode only (split_evidence). --from-data does only that, for
every definition, without runs: after a camera file or help file in data/ was edited (kit/tools/build_docs.py
--definitions runs it). On the committed data it gives the committed definitions byte for byte
(kit/tests/test_definitions.py).

The parts are in kit/writer/ (its __init__ lists them): the hand tables' reader, the names values get, the notes and
their evidence, the parts from data/, the gate and the plain pass. This file keeps the ILCE-1M2's pass (main) and the
readers of that camera's runs it needs, and gives every name of those parts under its old place (schema_update.clean).
"""
import argparse
import collections
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, datafiles, definitions, help_files, jsonl, models, option_tree, paths, placement  # noqa: E402,F401
from camkit.match import LOOKALIKES  # noqa: E402   (Cyrillic letters OCR reads for Latin; the proof viewer imports it)
from pass2_report import (close, latest_run, mirrored_values, num, registration_mirrors, report_proofs,  # noqa: E402,F401
                          row_name)
from runner import read_json  # noqa: E402
import writer.gate  # noqa: E402,F401   (the tests point its accepted file at their own)
from writer import proofs as writer_proofs  # noqa: E402   (menu_row reads the camera's reworded contexts from it)
from writer.labels import (LATIN, MODE_LETTERS, PICKER_FAMILY, TICKED, UNTICKED, axis_tail_out,  # noqa: E402,F401
                           check_labels, clean, ev_label, family_name, icon_word, one_name, option_prefix_out, picker_family,
                           same_option, snap, squashed, tick_values, value_order)
from writer.mirror import (mirror_key, mirror_names, mirror_of, mirror_place)  # noqa: E402,F401
from writer.notes import (ALLOWANCE, EVIDENCE, PAREN, TAIL, add_line, apply_fix, fix_differs, note_is,  # noqa: E402,F401
                          put_note, split_evidence, with_evidence_apart, with_tidy_note)
from writer.fromdata import (BUTTON_WORD, EXPERT_WORDS, MAPPING_WORDS, PLACE_KEYS, RECORD_REF,  # noqa: E402,F401
                             SETTING_GROUPS, expert, from_data, model_refused, mymenu_slots, own_help, places,
                             plain_reason, refresh_from_data, reset_names, say_stale, text, with_camera,
                             with_expert, with_menu, with_place, with_plain_words, write_definition)
from writer.proofs import (NAME_SOURCES, READER_RANK, SCALES, SHOWN_NUMBER, axis_value_rows,  # noqa: E402,F401
                           disputed_out, kept_proof, mixed, note_readers, one_slot_table, print_kept, reader_source,
                           sampled_scale, scaled_numbers, shown, menu_row, with_allowances, written_values,
                           with_in_sets_proved,
                           with_menu_rows, with_names, with_option_trees, with_scales, with_shown_as, without_held,
                           without_observed, without_written_with)
from writer.offered import check_video_systems, not_offered_marks, with_video_systems  # noqa: E402
from writer.copies import with_copies  # noqa: E402
from writer.gate import (QUESTION_KINDS, accepted_file, accepts, gate, questions, read_accepted)  # noqa: E402,F401
from writer.generic import (GENERIC_KEY, generic, generic_main, newest_download, seed)  # noqa: E402,F401
from writer import hand_evidence, hand_tables  # noqa: E402   (the hand tables, and where their evidence is kept)

# the ILCE-1M2's hand tables (data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json, writer/hand_tables.py), its hand
# evidence put back where the private overlay holds it (HAND_EVIDENCE: the file read, None on a clone without it, where
# --write refuses): its own pass (main) applies them, under these names, which the tests read and patch
HAND = hand_tables.load(paths.A1II)
CAROUSEL = HAND.CAROUSEL
CONTEXT_WORDS = HAND.CONTEXT_WORDS
COPIES = HAND.COPIES
COPY_MODES = HAND.COPY_MODES
COPY_MODES_UNKNOWN = HAND.COPY_MODES_UNKNOWN
EV_DOWN_FROM_20 = HAND.EV_DOWN_FROM_20
FRAME_PROOFS = HAND.FRAME_PROOFS
GROUP_NAMES = HAND.GROUP_NAMES
HAND_EVIDENCE = HAND.HAND_EVIDENCE
HOLD_BRACKET_COPIES = HAND.HOLD_BRACKET_COPIES
HOLD_TABLES = HAND.HOLD_TABLES
ISO_TABLE = HAND.ISO_TABLE
KEEP_LABELS = HAND.KEEP_LABELS
LABEL_FIXES = HAND.LABEL_FIXES
LATE_COPY = HAND.LATE_COPY
MY_MENU_EMPTY = HAND.MY_MENU_EMPTY
MY_MENU_ROW = HAND.MY_MENU_ROW
NEW_CHECK_NAMES = HAND.NEW_CHECK_NAMES
NEW_LIKE = HAND.NEW_LIKE
NEW_RECORDS = HAND.NEW_RECORDS
NEW_WHOLE_LABELS = HAND.NEW_WHOLE_LABELS
NOT_OFFERED = HAND.NOT_OFFERED
ORIENTED = HAND.ORIENTED
PP7_VALUES = HAND.PP7_VALUES
RECORD_FIXES = HAND.RECORD_FIXES
SHOOT_MODE_RECORDS = HAND.SHOOT_MODE_RECORDS
UNPROVED = HAND.UNPROVED
VALUE_FIXES = HAND.VALUE_FIXES
VIDEO_SYSTEM_VALUES = HAND.VIDEO_SYSTEM_VALUES

RUN_ROOT = paths.module_root()          # the camera's runs (models.refused checks they are the definition's)
RUN = RUN_ROOT / "kit2_pass2"
DATE = "2026-10-29"


def camset_read(path):
    from camkit import camset
    return camset.read(path)


def focus_area_names(schema_by_key) -> dict:
    """Schema label -> the camera's name, from Focus Area Limit (24 areas in the order of 0x0f46)."""
    m = read_json(RUN_ROOT / "kit2_pass1" / "map_all.json")
    row = next(r for r in m["rows"] if r["path"] == ["Focus Area Limit"])
    cam = [clean(o["label"]) for o in sorted(row["options"], key=lambda o: o["index"])]
    old = [lab for _, lab in schema_by_key["global:0x0f46"]["values"]]
    if len(cam) != len(old):
        sys.exit(f"Focus Area Limit lists {len(cam)} areas, the schema {len(old)}")
    names = dict(zip(old, cam, strict=True))
    names.update({"Flexible Spot": "Spot", "Free Size": "Custom"})        # the kind records
    names.update({f"Free Size {i}": f"Custom {i}" for i in (1, 2, 3)})    # once 0x0f46 is renamed
    return names


def blocked(run: Path) -> dict:
    """record-independent: row name -> [(label, reason)] of options the menu refused and that no
    later proof of the same option applied. A value the SDK's setter refused (kit/provers/sdk_run.py, "via" "SDK ...")
    is no menu's refusal: the menu may offer it all the same."""
    last = {}
    for r in jsonl.read(run / "proofs.jsonl"):
        if r["kind"] in ("list", "dialog", "sidelist"):
            last[(" > ".join(r["path"]), r["index"])] = r
    out = collections.defaultdict(list)
    for (row, _), r in last.items():
        if r.get("applied") is False and not str(r.get("via") or "").startswith("SDK "):
            why = re.sub(r"\s+", " ", (r.get("notice") or {}).get("text") or "").replace(" •OK", "").strip()
            why = plain_reason(why)
            out[row].append((clean(r["label"]), why))
    return out


def run_start() -> Path:
    """The run's newest start file, by the camera's downloads manifest (camkit.provenance.newest_start): a new record's
    size, count and memory-set presence are read from it, and like_setting's fill asks whether its value is among the
    proofs. Until 2026-11-11 the file names sorted as text chose it, an old download ("93438_before.DAT" after
    "239606_before.DAT")."""
    from camkit import provenance
    got = provenance.newest_start(RUN_ROOT, under=RUN)
    if got is None:
        sys.exit(f"no start file of {RUN.name} in the camera's downloads manifest "
                 f"({paths.shown(provenance.manifest_path(RUN_ROOT))}): a new record's layout is read from the run's "
                 "own start download; run a session of the run on the camera, or take its old downloads in with "
                 "kit/tools/upload_check.py --adopt")
    return got


def like_setting(key: str, by_key: dict, e: dict, r: dict) -> dict:
    """A proved record the schema lacked, laid out like its sibling: size, count and memory-set
    presence from the run's start file, labels from the proofs (axis value alone)."""
    from camkit import camset
    like, name = NEW_LIKE[key]
    rid = int(key.split("0x")[1], 16)
    cs = camset.read(run_start())
    rec = cs.get(0, rid)
    base = by_key[like]
    s = {f: base[f] for f in ("area", "source", "tab", "group", "order", "scalar", "modes") if f in base}
    vals = {} if "[field" in e["row"] else {v: clean(lab if key in NEW_WHOLE_LABELS else lab.split(":", 1)[-1].strip())
                                            for lab, v in r["proved"].items()}
    # the sibling's spelling of a label the proofs read the same ("ISO 160" for the box's "ISO160")
    sib = {v: lab for v, lab in base.get("values") or []}
    vals = {v: sib[v] if re.sub(r"\s+", "", str(sib.get(v, ""))).lower() == re.sub(r"\s+", "", lab).lower() else lab
            for v, lab in vals.items()}
    if vals and rec.value() not in vals:
        # the row's start value is not among the proofs: a gap there would tell the user's setting.
        # The sibling's labels fill it, as they agree with every proved one (S&Q's HD record, every
        # option proved, stores 25M as 29 where the movie one has 28, so no fill when not needed)
        for v, lab in base.get("values") or []:
            vals.setdefault(v, lab)
    # how it was found is evidence (camkit.definitions keeps note_evidence private): no note of its own
    s.update(key=key, id=rid, name=name, values=sorted([v, lab] for v, lab in vals.items()),
             note="", note_evidence=f"proved on the camera, laid out like {like} (runs/{RUN.name})",
             in_sets=cs.get(1, rid) is not None, size=rec.size, count=rec.count)
    return s


def my_menu_items(proofs: list, by_key: dict, records: list) -> list:
    """The items an Add Item proof wrote: [(slot key, code, name, source)], the name the proof's (the vision reader's
    words, as clean() mends them) and its source two readers when the lit row's OCR holds it too, else one reader;
    the slot's key from the page record (records: camera.my_menu.records) and the slot. A proof that did not apply,
    or a page or slot the definition lacks, gives none."""
    from pass2_report import alike, strip_icon
    out = []
    for r in proofs:
        mm = r.get("my_menu") or {}
        if r.get("applied") is False or not mm or not r.get("label") or mm.get("code") is None:
            continue
        page, slot = int(mm.get("page") or 0), mm.get("slot")
        if not 1 <= page <= len(records) or slot is None:
            continue
        key = f"global:0x{records[page - 1]:04x}[{slot}]"
        if key not in by_key:
            continue
        name = clean(r["label"])
        lit = strip_icon(str(r.get("shown") or ""))
        out.append((key, mm["code"], name, "two readers" if lit and alike(lit, name) else "one reader"))
    return out


def my_menu_empty(doc: dict, records: list, over: dict, changed: list) -> int:
    """My Menu's empty place in every slot (MY_MENU_EMPTY, a hand table): the code the camera file names for it
    (camera.my_menu.empty) labelled "(empty)", its name a hand table's, so an editor offers it outside Expert mode and
    a person can empty a place, and the camera's evidence added to each slot's note. Returns how many slots; none
    when the camera file names no empty code."""
    empty = ((doc.get("camera") or {}).get("my_menu") or {}).get("empty")
    if empty is None:
        return 0
    # {code} put in as text, never by str.format: the line is data, whose other braces must stay words
    line = MY_MENU_EMPTY["line"].replace("{code}", str(empty))
    slots = [x for x in doc["settings"] if x.get("area") == "global" and x.get("id") in records and x.get("index") is not None]
    for x in slots:
        labs = dict((v, lab) for v, lab in x.get("values") or [])
        if labs.get(empty) != MY_MENU_EMPTY["label"]:
            changed.append((x["key"], x["name"], empty, labs.get(empty), MY_MENU_EMPTY["label"]))
            labs[empty] = MY_MENU_EMPTY["label"]
            x["values"] = [[v, lab] for v, lab in sorted(labs.items(), key=lambda kv: value_order(kv[0]))]
        over[x["key"]][empty] = "hand table"
        if add_line(x, line):
            changed.append((x["key"], x["name"], "note", None, line[:60]))
    return len(slots)


def my_menu_tables(doc: dict, items: list, records: list, changed: list, readers: dict, derived: dict,
                   proved: dict) -> int:
    """Each Add Item proof's code named in every My Menu slot (one code table for the 42): the proved slot gets the
    proof's name with its source and the proof (proved.values and the row), the other slots the same name as derived,
    unproved. A name the table already holds and the proof's are two readings of one row when the report's rule finds
    them alike (judge: same text, or one held whole in the other): the fuller stays, for the screen shows an icon
    where the table's name has its word ("Shot Mark with Shutter Button" over the OCR's "with Shutter Button") and
    the table abbreviates where the screen has more ("Fn Menu Settings" over "Menu Settings", 2026-11-07), unless
    the table's is the proof's with an icon glyph glued in front (an old "SISO Range Limit": glued_icon); a name unlike the
    proof's gives way to it. Returns how many codes."""
    from pass2_report import alike, glued_icon, judge
    slots = [x for x in doc["settings"] if x.get("area") == "global" and x.get("id") in records and x.get("index") is not None]
    table = dict((v, lab) for v, lab in (slots[0].get("values") if slots else []) or [])
    names = {}
    for _key, code, name, _src in items:
        old = table.get(code)
        verdict, notes = judge({name: code}, {code: old} if old is not None else {})
        if old is not None and (verdict == "agrees" or alike(old, name)):
            names[code] = name if glued_icon(old, name) or len(name) > len(old) else old
        else:
            names[code] = name
    for x in slots:
        labs = dict((v, lab) for v, lab in x.get("values") or [])
        for code, name in names.items():
            if labs.get(code) != name:
                changed.append((x["key"], x["name"], code, labs.get(code), name))
                labs[code] = name
            derived[x["key"]][code] = "derived"
        x["values"] = [[v, lab] for v, lab in sorted(labs.items(), key=lambda kv: value_order(kv[0]))]
    by_key = {x["key"]: x for x in slots}
    for key, code, _name, src in items:
        x = by_key[key]
        readers[key][code] = src
        p = x.get("proved") or {"run": RUN.name, "date": DATE, "menu": [], "values": []}
        p["values"] = sorted(set(p.get("values") or []) | {code})
        p["menu"] = sorted(set(p.get("menu") or []) | {MY_MENU_ROW})
        x["proved"] = p
        proved.setdefault(key, set()).add(code)
    return len(names)


def spelled_names(by_key: dict, spelled: dict, over: dict, derived: dict) -> int:
    """What backs a name the old crawl misspelled and LABEL_FIXES mended (`spelled`: key -> values). The mended label
    is a hand table's where a proof chose the value (its proof is the evidence, the spelling the table's); a value a
    rule names otherwise keeps that rule's source; any other keeps the old schema's name, mended ("schema kept"),
    which no editor takes for the camera's word, for a spelling says nothing of the code (2026-11-08: Fn Menu codes no
    Fn picker lists, Custom Key codes, were offered outside Expert mode because "hand table" stood on their names).
    Returns how many values are left "schema kept"."""
    n = 0
    for k, vs in spelled.items():
        seen = set(((by_key.get(k) or {}).get("proved") or {}).get("values") or ())
        for v in vs:
            if v in seen:
                over[k].setdefault(v, "hand table")
            elif v not in over[k] and v not in derived[k]:
                over[k][v] = "schema kept"
                n += 1
    print(f"spelling fixes: {sum(map(len, spelled.values()))} mended names, {n} of them on values no proof or rule "
          "names (the old schema's, mended)")
    return n


def hold_agrees(hold: dict, codes, src: dict, src_codes) -> bool:
    """Whether a Recall Custom hold's proofs fit another hold's table (`src`, value -> label, proved at `src_codes`): no
    value proved on both is named apart, and no label is proved at two values. The labels are the camera's readings,
    as the pass set them from each hold's own proofs."""
    labs = dict((v, lab) for v, lab in hold.get("values") or [])
    code_of = {clean(str(src[v])).lower(): v for v in src_codes if v in src}
    for v in codes:
        if v not in labs:
            continue
        if v in src_codes and v in src and clean(str(labs[v])).lower() != clean(str(src[v])).lower():
            return False
        if code_of.get(clean(str(labs[v])).lower(), v) != v:
            return False
    return True


def reading(label) -> object:
    """A hold proof's label as a value to compare with the live setting's: a signed number for Exposure Comp. ("+4.7",
    "-0.3 EV", OCR's "‡0.0" or "I0.0" for ±0.0), else the words without case, spaces, "ISO" and a parenthesis ("ISO 50
    (multi-frame NR)" and "ISO 50" read alike, "ISO AUTO" and "AUTO")."""
    t = str(label).strip().replace("−", "-")
    m = re.fullmatch(r"\D{0,2}?([+-]?)\s*(\d+(?:\.\d+)?)\s*(?:EV)?", t)
    if m:
        return round(float(m[2]) * (-1 if m[1] == "-" else 1), 1)
    return re.sub(r"\([^)]*\)|\biso\b|\s+", "", t.lower())


def hold_tables(by_key: dict, proved: dict, report: list, over: dict, derived: dict, changed: list) -> None:
    """A Recall Custom hold's copy of a live setting (HOLD_TABLES): every proof of the hold, the label the camera showed
    against the code the hold stored, is checked against the live setting's table, the code itself or mirrored (the
    hold's code `mirror` minus the live one). When every proof fits, the evidence goes into the hold's note, and once
    the live table is proved in full the hold's values are named from it ("derived"; a mirrored copy takes the live
    labels in place of its hand table). A value whose name the hold keeps apart from the live table's (KEEP_LABELS: "ISO
    50 (multi-frame NR)" beside the live "ISO 50") stays the hand table's. A proof that does not fit stops the rule
    for that hold, printed."""
    for k, rule in HOLD_TABLES.items():
        s, live = by_key.get(k), by_key.get(rule["live"])
        if s is None or live is None:
            continue
        live_labs = dict((v, lab) for v, lab in live.get("values") or [])
        code_of = {reading(lab): v for v, lab in live_labs.items()}
        seen = [(lab, v) for e in report for kk, r in e["records"].items() if kk == k and not mixed(r)
                for lab, v in r["proved"].items()]
        mirror = rule["mirror"]
        bad = [(lab, v) for lab, v in seen if code_of.get(reading(lab)) is None
               or (code_of[reading(lab)] if mirror is None else mirror - code_of[reading(lab)]) != v]
        if not seen or bad:
            if bad:
                print(f"  hold      {k}: {len(bad)} of {len(seen)} proofs do not fit {rule['live']}'s table "
                      f"({bad[:3]}), the rule not applied")
            continue
        full = {v for v in live_labs if isinstance(v, int)} <= set(proved.get(rule["live"], ()))
        live_id = rule["live"].split(":")[1]
        how = f"the code of the live setting, {live_id}, as it is" if mirror is None else \
            f"{mirror} minus the code of the live setting, {live_id}"
        line = (f"A hold stores {how} (every proof of this hold fits that table, {len(seen)} proofs of this hold"
                f"{', the live table proved in full' if full else ', the live table not yet proved in full'}, "
                f"runs/{RUN.name}).")
        renew_line(s, line, re.compile(r"proofs of this hold"))
        if not full:
            continue
        labs = dict((v, lab) for v, lab in s.get("values") or [])
        for v in list(labs):
            src = v if mirror is None else mirror - v
            if src not in live_labs or v in proved.get(k, ()):
                continue
            if mirror is None and clean(str(labs[v])).lower() != clean(str(live_labs[src])).lower():
                over[k][v] = "hand table"       # the hold's fuller name, not the live table's
                continue
            derived[k][v] = "derived"
            if mirror is not None:
                over[k].pop(v, None)            # the live table's, no longer the hand table's
                if labs[v] != live_labs[src]:
                    changed.append((k, s["name"], v, labs[v], live_labs[src]))
                    labs[v] = live_labs[src]
        s["values"] = [[v, lab] for v, lab in sorted(labs.items(), key=lambda kv: value_order(kv[0]))]


def hold_table_lines(by_key: dict, proved: dict, menus: dict, changed: list) -> None:
    """A Reg. Custom Shoot Set item proved in full on one hold (every value it lists: hold 3's Aperture, 49 of 49) names
    the other holds' values, as the lending above does: each other hold whose proofs agree with it (hold_agrees) says
    so in its note, with the evidence; a hold proved in full itself, or one that disagrees, says nothing."""
    for k in sorted(by_key):
        m = re.fullmatch(r"(global:0x[0-9a-f]+)\[([012])\]", k)
        s = by_key[k]
        codes = {v for v, _ in s.get("values") or [] if isinstance(v, int)}
        if not m or k in KEEP_LABELS or not codes or not codes <= set(proved.get(k, ())) \
                or not any(r.startswith("Reg. Custom Shoot Set") for r in menus.get(k, ())):
            continue
        src = dict((v, lab) for v, lab in s["values"])
        for i in range(3):
            o = f"{m.group(1)}[{i}]"
            if o == k or o not in by_key or by_key[o]["name"] != s["name"] \
                    or {v for v, _ in by_key[o].get("values") or []} <= set(proved.get(o, ())) \
                    or not hold_agrees(by_key[o], proved.get(o, ()), src, proved[k]):
                continue
            n = len(set(proved.get(o, ())))
            # how its names were found is evidence alone (the note says nothing of it): which hold a run proved in full
            line = (f"(Its values are named by hold {int(m[2]) + 1}'s table, which hold {int(m[2]) + 1} proved in full, "
                    f"the proofs of this hold agreeing with it: all {len(codes)} values proved on hold "
                    f"{int(m[2]) + 1}, {n} on this one, runs/{RUN.name}.)")
            if renew_line(by_key[o], line, re.compile(r"values proved on hold \d")):
                changed.append((o, by_key[o]["name"], "note", None, line[:60]))


def renew_line(s: dict, line: str, ev_like: re.Pattern) -> bool:
    """`line` after the setting's note, once, its evidence kept current: when the note says its words already and only
    the evidence moved on (a count after a new proof), the part of note_evidence `ev_like` finds is replaced; a rerun on
    the same evidence changes nothing. The note before the line ends its sentence ("Reg. Custom Shoot Set" is a
    heading). A line that is evidence alone (in parentheses with its run) goes into note_evidence only, the part
    `ev_like` finds replaced. Whether the note changed."""
    plain, evidence = split_evidence(line)
    was = (s.get("note"), s.get("note_evidence"))
    note, ev = s.get("note") or "", s.get("note_evidence") or ""
    if not plain:
        parts = [evidence if ev_like.search(p) else p for p in ev.split("; ") if p]
        s["note_evidence"] = "; ".join(dict.fromkeys(parts + [evidence]))
        return (s.get("note"), s.get("note_evidence")) != was
    at = note.find(plain)
    head = (note[:at] if at >= 0 else note).rstrip()
    if head and not re.search(r"[.!?]$", head):
        s["note"] = head + "." + (" " + note[at:] if at >= 0 else "")
    if at < 0:
        add_line(s, line)
    elif ev and evidence and evidence not in ev.split("; "):
        parts = [evidence if ev_like.search(p) else p for p in ev.split("; ")]
        s["note_evidence"] = "; ".join(dict.fromkeys(parts + [evidence]))
    return (s.get("note"), s.get("note_evidence")) != was


def by_lines_of(frame_proofs: dict) -> set:
    """The records a hand table lists values for but gives no proof (FRAME_PROOFS with "values" and without "proved" or
    "sampled": the Registered AF area records, whose holds are proof lines since 2026-11-09), proved by the report
    alone: what the table once listed is in the lines, and a value it listed that no line credits goes. An entry with a
    note only (AF Frame Move Amt's, 2026-11-09) is none of them: it sets the note, and the proof the definition holds
    is merged with the report's (kept_proof), as any setting's is."""
    return {k for k, fp in frame_proofs.items() if "values" in fp and not {"proved", "sampled"} & set(fp)}


def hold_chosen(proved_now, old_values, start_only) -> set:
    """The codes a hold's proofs chose, which EV_DOWN_FROM_20's hold names "hand table" (the rest "counted"): this run's
    proofs, and the definition's from before that a counted line still wrote (as kept_proof keeps them: the caller
    gives only those), but never a value only a start line accounted for
    (pass2_report.start_lines: the hold's own value, chosen last to put it back) that no proof here holds, for it would
    stand out among the counted ones (decision 16)."""
    now = set(proved_now)
    return now | (set(old_values) - (set(start_only) - now))


def picker_groups() -> dict:
    """Record of a slot proved in full -> the records of the slots sampled against it: the groups
    prove_run --picker-sample made (same functions in the same order), each slot's record read from
    the proofs: the record most of the slot's proofs changed first. A sampled slot shares the full slot's code table:
    its three proofs agreed with it. One proof's first change is no slot's record: the playback AEL key's Rating option
    writes Rating's copies (0x16bd...) first, and taking its proof alone tied the playback keys' group to Rating's copy,
    so the keys took no lending (2026-11-08)."""
    import prove_run as P
    firsts = collections.defaultdict(collections.Counter)
    for r in jsonl.read(RUN / "proofs.jsonl"):
        if r.get("kind") != "table" or r.get("opens") != "picker" or not r["changes"]:
            continue
        c = r["changes"][0]
        if isinstance(c["after"], list):                  # an array of slots (Fn Menu): the slot that moved
            slot = next((i for i, (a, b) in enumerate(zip(c["before"], c["after"], strict=True)) if a != b), None)
            key = f"{c['key']}[{slot}]"
        else:
            key = c["key"]
        firsts[P.job_key(r) if "option" in r else ""][key] += 1
    rec_of = {job: n.most_common(1)[0][0] for job, n in firsts.items()}
    jobs = [j for j in P.sample_pickers(P.table_jobs(None)) if j.get("opens") == "picker"]
    groups, firsts = collections.defaultdict(set), []
    for j in jobs:
        where = (" > ".join(j["path"]), j.get("screen"), j.get("nth", 0))
        full = next((f for w, f in firsts if w == where and P.same_functions(f["labels"], j["labels"])), None)
        if full is None:
            firsts.append((where, j))
        elif P.job_key(full) in rec_of and P.job_key(j) in rec_of:
            groups[rec_of[P.job_key(full)]].add(rec_of[P.job_key(j)])
    return groups


def new_setting(key: str, row: str, proved: dict) -> dict | None:
    """A schema entry for a record proved through a checklist that the schema lacked, with the size,
    slot count and memory-set presence read from the run's start file."""
    from camkit import camset
    m = re.fullmatch(r"global:0x([0-9a-f]+)(?:\[(\d+)\])?", key)
    if not m:
        return None
    rid, slot = int(m.group(1), 16), (int(m.group(2)) if m.group(2) else None)
    cs = camset.read(run_start())
    rec = cs.get(0, rid)
    if rec is None:
        return None
    on, off = tick_values(proved)
    box = next((lab.rsplit(": ", 1)[0] for lab in proved), "")
    if row.startswith("Reg. Custom Shoot Set"):
        # a hold's tick or value (2026-10-30): slots 0-2 are holds 1-3; slot 3 is the registration
        # working copy, which follows whichever hold was opened last, so it is no setting of its own
        if slot is None or slot > 2:
            return None
        if row.count(" > ") == 1:
            name = f"{box}: registered"
            values = sorted([[on, "Registered"], [off, "Not registered"]]) if on is not None and off is not None else []
        else:
            if len(set(proved.values())) < len(proved):
                return None             # the same value under different options: not the item's own
                                        # (registering a bracket drive mode writes 0x0e80 / 0x0e84)
            name, values = row.split(" > ")[-1], sorted([v, clean(lab)] for lab, v in proved.items())
        return {"key": key, "area": "global", "id": rid, "index": slot, "name": name, "source": "Menu",
                "tab": "Shooting", "group": f"Recall Custom hold {slot + 1}", "order": 1233, "values": values,
                "note": "Reg. Custom Shoot Set", "in_sets": cs.get(1, rid) is not None, "scalar": True,
                "size": rec.size, "count": rec.count, "modes": ""}
    tab = {"Recognition Target": "Focus", "Reg. Flash Shooting Set": "Exposure/Color",
           "Rating Set(Custom Key)": "Playback", "DISP (Screen Disp) Set": "Setup",
           "Focus Area Limit": "Focus"}.get(row.split(" > ")[0], "")
    radio = not any(lab.endswith((": ticked", ": unticked")) for lab in proved)
    if radio:                       # a radio sub-option pair (DISP Set's Exposure: On / TimeOut): its two labels
        values = sorted([v, clean(lab)] for lab, v in proved.items())
    else:
        words = ("Included in DISP cycle", "Not included") if row.startswith("DISP") else ("Ticked", "Not ticked")
        values = sorted([[on, words[0]], [off, words[1]]]) if on is not None and off is not None else []
    s = {"key": key, "area": "global", "id": rid, "name": NEW_CHECK_NAMES.get(key, f"{row}: {box}"), "source": "Menu",
         "tab": tab, "group": row.split(" > ")[0], "order": 9000, "values": values,
         "note": "One checkbox of this menu row." + LATE_COPY.get(rid, ""),
         "in_sets": cs.get(1, rid) is not None, "scalar": True, "size": rec.size, "count": rec.count, "modes": ""}
    if slot is not None:
        s["index"] = slot
    return s


HELP = RUN_ROOT / "kit2_help"


def menu_place(m: str) -> tuple:
    """A proof's menu row ("ISO > ISO AUTO Maximum [Movie mode]") as (mode, path keys)."""
    from page_model import key_text
    # S&Q's menu is Movie mode's, with its help (runs/kit2_page_scan_sq, 2026-10-30)
    ctx = "Movie mode" if re.search(r"\[(Movie mode|S&Q mode)", m) else "Stills mode"
    path = re.sub(r" \[[^\]]*\]", "", m).split(" / ")[0].split(" @")[0]
    return ctx, tuple(key_text(x).lower() for x in path.split(" > "))


def camera_group_names(doc) -> int:
    """Each setting's group under the camera's own name: a cut breadcrumb by the one camera group of its tab it
    can be, or, when several can, by the row its proof went through, in the Stills menu or in the Help Guide's
    list (every mode's rows: Movie mode's Auto Framing Settings). A submenu after the group is kept."""
    for m in doc.get("menu") or []:
        m["group"] = GROUP_NAMES.get(m["group"], m["group"])
    groups, rows = collections.defaultdict(list), collections.defaultdict(dict)
    for m in sorted(doc.get("menu") or [], key=lambda m: m["order"]):
        if m["group"] not in groups[m["tab"]]:
            groups[m["tab"]].append(m["group"])
        rows[m["tab"]].setdefault(m["label"].lower(), m["group"])
    guide = ROOT / "data" / f"{doc['model']}_fw{doc['layouts'][0]['firmware']}" / f"help_guide_menu_{doc['model']}_fw{doc['layouts'][0]['firmware']}.jsonl"
    for r in jsonl.read(guide):
        rows[r["tab"]].setdefault(r["item"].lower(), GROUP_NAMES.get(r["group"], r["group"]))
    n = 0
    for st in doc["settings"]:
        tab, g = st.get("tab"), st.get("group") or ""
        head, sep, rest = g.partition(" › ")
        head = GROUP_NAMES.get(head, head)
        if head not in groups[tab] and head.endswith("..."):
            hits = [x for x in groups[tab] if x.startswith(head[:-3])]
            menus = (st.get("proved") or {}).get("menu") or []
            for path in [menus] if isinstance(menus, str) else menus:
                seen = [rows[tab].get(x.strip().lower()) for x in re.sub(r"\s*\[[^\]]*\]", "", path).split(" > ")]
                hits = [x for x in hits if x in seen] or hits
            head = hits[0] if len(hits) == 1 else head
        full = head + sep + rest
        if full != g:
            st["group"] = full
            n += 1
    return n


DISABLED_RE = re.compile(r"\s*This function is currently disabled\.?\s*$", re.I)


def proved_rows(proofs) -> dict:
    """{record key: the rows (pass2_report.row_name) its proofs went through}, of the proofs given: the report's
    counted ones (attach_help, and kit/tools/proof_viewer.py by counted_proofs)."""
    went = collections.defaultdict(set)
    for r in proofs:
        for c in r.get("changes") or []:
            went[c["key"]].add(row_name(r))
    return went


def counted_proofs(run: Path) -> list:
    """The proofs the report counts (pass2_report.report_proofs over the camera's proof runs, the unfinished left
    out), as main() gives attach_help; [] for a run with no proofs or no report (kit/pass2_report.py writes
    report.json: before it there are no counted proofs, and schema_update does not run)."""
    if not ((Path(run) / "proofs.jsonl").exists() and (Path(run) / "report.json").exists()):
        return []
    proofs, cut_short = report_proofs(Path(run))[:2]
    return [r for i, r in enumerate(proofs) if i not in cut_short]


def help_rows(s: dict, went: dict) -> list:
    """The menu rows (menu_place: mode, path keys) a setting's help may be the guide of: its "proved" menu's rows, then
    the rows its counted proofs went through (proved_rows), which change less as proofs are made again. attach_help
    keeps a help that is still, word for word, one of these rows' guide; the proof viewer links the guides on them."""
    menus = [m for m in (s.get("proved") or {}).get("menu") or [] if isinstance(m, str)]
    return [menu_place(m) for m in [*menus, *sorted(went.get(s.get("key"), ()))]]


def attach_help(doc, report, proofs=()) -> tuple:
    """The camera's own help (In-Camera Guide, 2026-11-01) for a setting's menu row (kit/help_run.py:
    every page's rows; prove_run --help-text: list and dialog rows in submenus too) and for each option
    it proved, by stored value. Read in the mode the setting was proved in when the walk has it there;
    the words a second reader confirmed (kit/help_reads.py).
    Sony's wording, the owner's choice: main() moves it into the private help file (kit/camkit/help_files.py),
    never into the published schema. Settings with nothing read keep what they had, and so does a setting whose help
    is still, word for word, the guide of a row one of its counted proofs went through (proofs: the report's, the
    unfinished left out; pass2_report.row_name). Its "proved" menu lists only the rows of each option's latest proof,
    and those change as proofs are made again: S&Q Shoot Mode's proofs of 2026-10-29 wrote global:0x13e2, its later
    ones (in Time-lapse) global:0x13e3, so on 2026-11-11 its S&Q help gave way to the next row's, Shoot Mode's
    general guide, in the private help file."""
    from page_model import key_text
    rows, opts = {}, {}
    # the text two readers settled on (kit/help_reads.py), by the guide's first frame; else the OCR
    reads = {}
    for x in jsonl.read(HELP / "help_reads.jsonl"):
        reads[x["frame"]] = x["text"]
    for name in ("help.jsonl", "option_help.jsonl", "drive_help.jsonl"):
        for r in jsonl.read(HELP / name):
            if not r.get("text"):
                continue
            r["text"] = reads.get((r.get("frames") or [None])[0], r["text"])
            # a greyed row's guide ends with the camera's state, not the setting's help (2026-11-01)
            r["text"] = DISABLED_RE.sub("", r["text"])
            ctx = r.get("context") or "Stills mode"
            path = tuple(key_text(x).lower() for x in (r.get("path") or [r["label"]]))
            if r.get("index", -1) >= 0:
                opts[(ctx, path, key_text(r["label"].translate(LOOKALIKES)).lower())] = r["text"]
            else:
                rows[(ctx, path)] = r["text"]

    def find(table, ctx, *key):
        return table.get((ctx, *key)) or next((t for k, t in table.items() if k[1:] == key), None)

    by_key = {s["key"]: s for s in doc["settings"]}
    went = proved_rows(proofs)
    for s in doc["settings"]:
        menus = (s.get("proved") or {}).get("menu") or []
        had = s.get("help")
        if had and any(find(rows, *place) == had for place in help_rows(s, went)):
            continue                                 # still the guide of a row it was proved through: kept
        for m in menus:
            text = find(rows, *menu_place(m))      # noqa: F811   (attach_help's own: the guide's text, not fromdata.text)
            if text:
                s["help"] = text
                break
    # a number field's own guide, after the row's (ISO Range Limit's Minimum and Maximum, 2026-11-02;
    # runs/kit2_help/field_help.jsonl, kit/tools/help_extras.py --fields)
    fields = {}
    if (HELP / "field_help.jsonl").exists():
        for r in jsonl.read(HELP / "field_help.jsonl"):
            text = reads.get(r["frames"][0], r["text"])
            fields[(r["context"], tuple(key_text(x).lower() for x in r["path"]), r["field"])] = f"{r['label']}: {text}"
    for e in report:
        m = re.search(r" \[field (\d+)\]", e["row"])
        text = m and find(fields, *menu_place(e["row"]), int(m.group(1)))
        for k, r in e["records"].items() if text else ():
            s = by_key.get(k)
            if s and s.get("help") and r["verdict"] not in ("new", "readout") and text not in s["help"]:
                s["help"] += " " + text
    # built afresh from the readings each time: a reading corrected later (a second reader, a reread)
    # replaces the text the schema had (2026-11-01: kept texts hid the corrections)
    fresh = collections.defaultdict(dict)

    def option_text(ctx, path, lab):
        """An option's guide by its label as the proof read it. Cyrillic look-alikes the OCR put in read
        as Latin ("120р", 2026-11-02). A label read with its icon's text ("XAVCS XAVC S HD HD") takes the
        option label inside it when the rest only repeats that label's letters, as the icon does: "Tracking:
        Wide" is not Wide, nor "C.Temp./Filter: 6000 K" the C.Temp./Filter option."""
        key = key_text(lab.translate(LOOKALIKES)).lower()
        text = find(opts, ctx, path, key)
        if text:
            return text
        alnum = lambda t: re.sub(r"[^a-z0-9]", "", t)                        # noqa: E731
        inside = {k[2] for k in opts if k[1] == path and len(alnum(k[2])) >= 4 and alnum(k[2]) in alnum(key)
                  and set(alnum(key).replace(alnum(k[2]), "", 1)) <= set(alnum(k[2]))}
        best = [k for k in inside if len(k) == max(map(len, inside))] if inside else []
        return find(opts, ctx, path, best[0]) if len(best) == 1 else None

    texts = collections.defaultdict(set)
    for e in report:
        ctx, path = menu_place(e["row"])
        for k, r in e["records"].items():
            if k not in by_key or r["verdict"] in ("new", "readout"):
                continue
            for lab, v in r["proved"].items():
                text = option_text(ctx, path, lab)
                if text and isinstance(v, int):
                    texts[(k, v)].add(text)
    # settings proved outside the report (FRAME_PROOFS: the Screen Reader's, 2026-11-02), by their menu row and
    # their own value labels
    for k, fp in FRAME_PROOFS.items():
        if k not in by_key or not fp.get("menu") or not fp.get("values"):
            continue
        for menu in fp["menu"] if isinstance(fp["menu"], list) else [fp["menu"]]:     # one row or several
            ctx, path = menu_place(menu)
            for v, lab in fp["values"]:
                text = v in fp.get("proved", []) and option_text(ctx, path, lab)
                if text:
                    texts[(k, v)].add(text)
    # options with different help that store the same value (HEIF 4:2:0 and 4:2:2 in a JPEG/HEIF flag): the
    # value is neither, so it gets no text
    for (k, v), have in texts.items():
        if len(have) == 1:
            fresh[k][v] = next(iter(have))
    # the Shoot Mode carousel shows each mode's description on its own screen, no guide (carousel_help.jsonl,
    # kit/tools/help_extras.py --carousel, 2026-11-02): a family's own mode record, matched by the record's value labels
    if (HELP / "carousel_help.jsonl").exists():
        for r in jsonl.read(HELP / "carousel_help.jsonl"):
            text = reads.get(r["frames"][0], r["text"])
            for k in SHOOT_MODE_RECORDS.get(r["family"], ()):
                for v, lab in (by_key.get(k) or {}).get("values") or []:
                    if lab in (r["label"], MODE_LETTERS.get(r["label"])):
                        fresh[k].setdefault(v, text)
    for k, have in fresh.items():
        by_key[k]["option_help"] = sorted([v, t] for v, t in have.items())
    return sum(1 for s in doc["settings"] if s.get("help")), sum(1 for s in doc["settings"] if s.get("option_help"))


def main():
    ap = argparse.ArgumentParser()
    # writing is asked for, never the default: a run meant as a look wrote the schema (2026-10-29)
    ap.add_argument("--write", action="store_true",
                    help="write editor/definitions/<model>_fw<fw>.json, the definition of the camera the kit works on "
                         "(otherwise only show)")
    ap.add_argument("--dry-run", action="store_true", help="the default; kept for old command lines")
    ap.add_argument("--force", action="store_true",
                    help="write although the report holds open questions the accepted file does not accept (gate), "
                         "with a loud warning; never for a submission")
    ap.add_argument("--from-data", action="store_true",
                    help="only every definition's parts from data/ (the camera section, the own help, the format, the "
                         "Expert marks, the notes' evidence apart), without runs")
    ap.add_argument("--option-trees", action="store_true",
                    help="only each setting's option tree from the run's proofs (the camera's nested options), with the "
                         "audit: every setting that gets one, and every nested-looking one that does not, with why")
    ap.add_argument("--accept-stale", action="store_true",
                    help="write although this run's reading set evidence aside that no longer fits the public "
                         "definition (a proof's, or more than a handful of settings'); it is kept in the evidence "
                         "file's \"stale\" section, never published")
    ap.add_argument("--drop-stale", action="store_true",
                    help="only list the evidence file's \"stale\" section (setting keys and fields); with --write, "
                         "remove it")
    ap.add_argument("--finish-write", action="store_true",
                    help="only finish a write cut short (its marker left beside the evidence file): the definition it "
                         "was writing, the evidence file's proofs' lean forms put in, written only when it is the one "
                         "the marker names (the stop that finds the marker names this)")
    a = ap.parse_args()
    if a.from_data:
        refresh_from_data(a.write and not a.dry_run, a.accept_stale)
        return
    target = definitions.path(RUN_ROOT.name) if paths.KEY.match(RUN_ROOT.name) else definitions.active()
    if a.drop_stale:
        drop_stale(target, a.write and not a.dry_run)
        return
    if a.finish_write:
        _keys, said = definitions.finish_write(target)
        print(said)
        return
    if a.write and not a.dry_run:
        # the mapper's menu tree, accepted rulings and record shapes, if still at their old place in data/
        datafiles.stop_if_left(target.stem, "kit/schema_update.py --write")
    if a.option_trees:
        doc = definitions.load(target)
        why = model_refused(RUN, doc)
        if why:
            sys.exit(f"schema_update: {why}")
        if with_option_trees(doc, RUN, audit=True) is not None and a.write and not a.dry_run:
            without_observed(doc)           # an old list of what the owner's files held is not written back
            without_held(doc)               # nor an old mark on the values no option was seen to write
            write_definition(target, doc, a.accept_stale, reset=False)
            print(f"wrote {target}")
            say_stale(target)
        return
    if target.stem != paths.A1II:
        generic_main(target, RUN, a.write and not a.dry_run, a.force, a.accept_stale)   # any other camera: the plain pass
        return
    if a.write and not a.dry_run and HAND_EVIDENCE is None:
        # the hand tables' evidence (writer/hand_evidence.py) is the mapper's, in the private overlay: without it the
        # tables give no hand proofs, and a definition written so would lose every one of them
        sys.exit(f"schema_update: nothing written. Part of the {paths.A1II} definition is proved by its hand tables "
                 f"({paths.shown(datafiles.hand_tables_file(paths.A1II))}), and what those proofs were is kept in the "
                 "mapper's private file "
                 f"{paths.shown(hand_evidence.path(paths.A1II))}, which is not on this computer. Writing without it "
                 "would drop those proofs from the definition. Run --write where that file is (the private overlay, "
                 "private/evidence/), or point CAMSET_EVIDENCE_DIR at its folder; --from-data needs no evidence.")
    doc = definitions.load(target)
    writer_proofs.CONTEXT_WORDS.update(CONTEXT_WORDS)      # this body's contexts the runs reworded (menu_row)
    why = model_refused(RUN, doc)
    if why:
        sys.exit(f"schema_update: {why}")
    # the camera's own facts (tab colours, memory names, families, the container...) are edited in
    # data/<model>_fw<fw>/camera_<model>_fw<fw>.json only, the file of the definition's model and firmware
    doc = with_camera(doc)
    mirror = mirror_of(doc)
    by_key = {s["key"]: s for s in doc["settings"]}
    report = read_json(RUN / "report.json")
    fa_names = focus_area_names(by_key)
    kinds, pickers, axes = {}, set(), set()
    subs = [x for x in doc["settings"] if x.get("under_option") and x.get("row")]     # sub-choices (axis_tail_out)
    all_proofs, cut_short = [], set()
    # every proof the report read (pass2_report.report_proofs: this run's and every other proof run's of the camera)
    if (RUN / "proofs.jsonl").exists():
        all_proofs, cut_short = report_proofs(RUN)[:2]
    for r in all_proofs:
        kinds[" > ".join(r["path"])] = r["kind"]
        if r["kind"] == "axis" and r.get("option"):
            axes.add((" > ".join(r["path"]), r["option"]))
        if r.get("opens") == "picker":
            pickers.add(" > ".join(r["path"]) + f" / {r['option']}")      # the report's row name
    menus = collections.defaultdict(set)
    proved = collections.defaultdict(set)
    came = collections.defaultdict(dict)    # the runs whose proofs proved each record, each its latest day ("runs")
    sampled = {}
    # records a table row proved only by a sample stepped from the option the camera held (pass2_report's
    # "sampled_from_start"): how many proofs, written as a count unless another row walked the record whole
    from_start = collections.Counter()
    # values only a start line credited (pass2_report's "start_only": a part walk's start or put-back): no proof, so
    # never kept from an older definition nor named by the hold tables as chosen, unless a line proves them
    start_only = collections.defaultdict(set)
    with_ = collections.defaultdict(set)
    changed, review, shared, corrected = [], [], {}, {}
    # what backs each value's name (proved.names, with_names): the readers', a name set against the reading, a copy
    readers, over, derived = (collections.defaultdict(dict) for _ in range(3))
    unresolved, disputed = [], set()        # conflicts the pass leaves standing, records not one to one (gate)
    allowed = collections.defaultdict(set)     # key -> the owner's allowances its proofs carry (with_allowances)
    # the registrations seen copying a live setting into a memory set, and the values registered into a memory record
    # no live record holds (a frame's place): "registration mirror" lines, which no report row holds
    mirrors, registered = registration_mirrors(RUN), mirrored_values(RUN)
    for k, m in mirrors.items():
        if m.get("allowance"):
            allowed[k].add(m["allowance"])
    assigned = collections.defaultdict(set)    # (key, value) -> the names this run's rows gave it (one_name)
    prefixes = collections.defaultdict(set)    # key -> the option name every proved label of a row starts with
    # the old crawl's OCR slips mended (LABEL_FIXES): a spelling, no evidence of the code, so its source is settled
    # once the proofs are in (spelled_names)
    spelled = collections.defaultdict(set)
    for x in doc["settings"]:
        for pair in x.get("values") or []:
            if pair[1] in LABEL_FIXES.values():
                spelled[x["key"]].add(pair[0])
            if pair[1] in LABEL_FIXES:
                changed.append((x["key"], x["name"], pair[0], pair[1], LABEL_FIXES[pair[1]]))
                pair[1] = LABEL_FIXES[pair[1]]
                spelled[x["key"]].add(pair[0])
    vocabulary = sorted({str(lab) for x in doc["settings"] for _, lab in x.get("values") or [] if isinstance(lab, str)}
                        | {x["name"] for x in doc["settings"]})
    family = {}
    for x in doc["settings"]:
        if ":" in x["name"]:
            for v, lab in x.get("values") or []:
                family.setdefault((x["name"].split(":")[0], v), lab)
    # an axis row named after the value its axis stood on is named by its item alone wherever the definition says it
    # (menu_row): in each proof's rows from here on, so a rerun's rows meet the definition's as written
    axis_rows = axis_value_rows(all_proofs)
    # the values the lines the report counts wrote: of the proof the definition held before, only such a value is kept
    # beside the report's (kept_proof); an old menu row never is
    written = written_values(all_proofs, cut_short, {e["row"] for e in report})
    for e in report:
        row = re.sub(r" \[field \d+\]$", "", e["row"])
        if row.startswith(MY_MENU_ROW):
            continue                                   # read from its proofs (my_menu_items)
        # a record the definition lacks is new, whatever the report said against the definition it read
        keys = [k for k, r in e["records"].items() if r["verdict"] != "new" and not mixed(r) and k in by_key]
        for k, r in e["records"].items():
            if mixed(r):
                print(f"  left out, not one to one: {k} {row[:60]} (prove it again)")
                disputed.add(k)
        for k in e["records"]:
            # a checklist's boxes are separate choices: its records are not written together (the count printed below;
            # which records, the report's, never the definition's: without_written_with)
            if len(e["records"]) > 1 and kinds.get(row) != "checklist":
                with_[k] |= set(e["records"]) - {k}
        for k in keys:
            s, r = by_key[k], e["records"][k]
            if "view only" in (s.get("note") or "").lower():
                continue                                   # a live readout (ISO in use), not a setting
            menus[k].add(menu_row(row, axis_rows))
            allowed[k] |= set(r.get("allowances") or ())          # the owner's word for a never-open row (the evidence)
            for by, day in (r.get("runs") or {RUN.name: None}).items():
                came[k][by] = max(filter(None, (came[k].get(by), day)), default=None)
            start_only[k] |= {v for v in (r.get("start_only") or {}).values() if not isinstance(v, (list, dict))}
            if r.get("sampled_from_start"):
                # the held option and the ones a fixed number of presses on: its values would tell the camera's own
                # option (decision 16), so neither they nor their readings name anything; the slot's names come from
                # the slot its picker group proved in full (picker_groups, "derived")
                proved.setdefault(k, set())
                from_start[k] += r.get("sample_proofs", e["options"])
                continue
            if kinds.get(row) == "checklist" and any(lab.endswith((": ticked", ": unticked")) for lab in r["proved"]):
                if check_labels(s, r["proved"], changed) == "kept":
                    over[k].update({v: "schema kept" for v in r["proved"].values()})
                note_readers(readers, k, r)
                proved[k] |= set(r["proved"].values())
                continue
            grid = "wbgrid" in e.get("kinds", ())
            if "[field" in e["row"] or (s.get("range") and (grid or all(num(lab) is not None for lab in r["proved"]))) \
                    or (r.get("linear") is True and sampled_scale(s, set(r["proved"].values()))):
                # a number field is proved by samples, one of them the row's own start: only how many
                # and whether they lie on a line are kept (the values would carry the user's setting). So is a White
                # Balance grid (its ends, 0, the corners and an inside point) and a listed scale of numbers whose
                # samples lie on a line (sampled_scale: the colour temperature, Exposure Std. Adjust's sixths)
                proved.setdefault(k, set())
                sampled.setdefault(k, {"proofs": 0, "linear": None})
                sampled[k]["proofs"] += e["options"]
                if r["linear"] is not None:
                    was = sampled[k]["linear"]
                    sampled[k]["linear"] = bool(r["linear"]) if was is None else was and bool(r["linear"])
                if not s.get("range"):
                    continue                                   # an index field (ISO Range Limit): ISO_TABLE
                lo, hi = s["range"]
                seen = [v for v in r["proved"].values() if isinstance(v, (int, float))]
                if seen and (min(seen) < lo or max(seen) > hi):
                    # the camera offered and stored it (Saturation +32 against a schema range to +31)
                    new_range = [min(lo, min(seen)), max(hi, max(seen))]
                    changed.append((k, s["name"], "range", s["range"], new_range))
                    s["range"] = new_range
                continue                                   # numbers: the value is the number
            proved[k] |= set(r["proved"].values())
            note_readers(readers, k, r)
            heads = {lab.split(": ", 1)[0].strip() if ": " in lab else None for lab in r["proved"]}
            if len(r["proved"]) > 1 and len(heads) == 1 and None not in heads:
                prefixes[k] |= heads
            if k in KEEP_LABELS:
                over[k].update({v: "hand table" for v in r["proved"].values()})
                unresolved += [{"key": k, "row": row, "value": n["value"], "label": n.get("schema"),
                                "camera": n.get("camera")} for n in r["notes"] if n.get("kind") == "conflict"]
                continue                                   # proved, but not named by the options
            labels = dict((v, lab) for v, lab in s.get("values") or [])
            for n in r["notes"]:
                v = n["value"]
                if (k, v) in VALUE_FIXES:
                    over[k][v] = "hand table"
                    continue                               # a label checked by hand stands
                if e["row"] in pickers and labels.get(v) and not n.get("sure"):
                    # a function's name read off a picker is OCR of icons and arrows: the schema's
                    # label stands; a reading nothing like it is listed for a person to look at.
                    # When OCR and the vision model both read the same name, the camera wins (871 is
                    # "Finder/Monitor Sel." on every key; the playback keys' schema said "Touch
                    # Operation Select", which is 870)
                    review.append((k, v, labels[v], n["camera"]))
                    over[k][v] = "schema kept"
                    if n.get("kind") == "conflict":
                        unresolved.append({"key": k, "row": row, "value": v, "label": labels[v], "camera": n["camera"]})
                    continue
                new = CAROUSEL.get((k, v)) or clean(n["camera"])
                if (k, v) in CAROUSEL:
                    over[k][v] = "hand table"
                if e["row"] in pickers:
                    # one code table per family ("Custom Key (Still)": every key): a name the family
                    # already gives this code wins over the reading; else the reading, snapped
                    fam = s["name"].split(":")[0]
                    read = new
                    new = snap(new, vocabulary) if n.get("sure") else family.get((fam, v)) or snap(new, vocabulary)
                    if new != read:
                        over[k][v] = "derived" if not n.get("sure") and family.get((fam, v)) == new else "schema kept"
                    shared[(k.split("[")[0], v)] = new
                if kinds.get(row) == "dialog" and (k, v) not in CAROUSEL and labels.get(v) and ":" not in labels[v] \
                        and ":" in new:
                    new = new.split(":", 1)[0].strip()      # an option-only record: drop the axis value
                if e["row"] not in pickers and (k, v) not in CAROUSEL:
                    new = axis_tail_out(new, v, s, subs, axes, row, labels)
                if " / " in e["row"] and ":" in new:
                    main = new.split(":", 1)[0].strip() + ":"
                    if not any(str(x).startswith(main) for x in labels.values() if x):
                        # an axis-only record (DRO level, tracking start area): the axis value alone
                        new = new.split(":", 1)[1].strip()
                if e["row"] not in pickers:
                    assigned[(k, v)].add(new)
                if labels.get(v) != new:
                    changed.append((k, s["name"], v, labels.get(v), new))
                    if e["row"] in pickers and n.get("sure") and labels.get(v):
                        corrected[(s["name"].split(":")[0], v, labels[v])] = new
                    labels[v] = new
            if e["row"] not in pickers:          # a value this row agreed on: its name, beside another row's (one_name)
                noted = {n["value"] for n in r["notes"]}
                for lab, v in r["proved"].items():
                    agreed = (r.get("schema") or {}).get(str(v)) or labels.get(v)    # the label the report agreed with
                    if v not in noted and agreed and not isinstance(v, (list, dict)):
                        assigned[(k, v)].add(agreed)
                    if not isinstance(v, (list, dict)) and list(r["proved"].values()).count(v) > 1:
                        assigned[(k, v)].add(clean(lab))         # two options of this row write it alike
            # one form for the record's values: a value still named by its icon ("X.FINE") takes the words the
            # camera shows beside it ("Extra fine"), as its siblings did ("FINE Fine" -> "Fine")
            if e["row"] not in pickers and k not in KEEP_LABELS:
                for lab, v in r["proved"].items():
                    icon = icon_word(unicodedata.normalize("NFKC", str(lab)).strip())
                    if icon and (k, v) not in VALUE_FIXES and str(labels.get(v, "")).upper() == icon[0].upper():
                        changed.append((k, s["name"], v, labels[v], icon[1]))
                        labels[v] = icon[1]
                    # a bare number the camera shows with its unit ("120" read "120fps"), as its siblings are named
                    read = clean(lab)
                    if (k, v) not in VALUE_FIXES and re.fullmatch(r"\d+(?:\.\d+)?", str(labels.get(v, ""))) \
                            and re.fullmatch(re.escape(str(labels[v])) + r"[A-Za-z]+", read):
                        changed.append((k, s["name"], v, labels[v], read))
                        labels[v] = read
            s["values"] = [[v, lab] for v, lab in sorted(labels.items())]
    # Reg. Custom Shoot Set: the three holds are one record's slots with one encoding, so a value a
    # hold's list proved names the same value in the other holds (2026-10-30), unless the proofs of the two holds
    # disagree (hold_agrees); a hold proved in full lends its whole table, with the evidence (hold_table_lines)
    for k in sorted(by_key):
        m = re.fullmatch(r"(global:0x[0-9a-f]+)\[([012])\]", k)
        if not m or k in KEEP_LABELS or not any(r.startswith("Reg. Custom Shoot Set") and r.count(" > ") == 2
                                                for r in menus.get(k, ())):
            continue
        src = dict((v, lab) for v, lab in by_key[k].get("values") or [])
        for i in range(3):
            o = f"{m.group(1)}[{i}]"
            if o == k or o not in by_key or by_key[o]["name"] != by_key[k]["name"]:
                continue
            if not hold_agrees(by_key[o], proved.get(o, ()), src, proved[k]):
                print(f"  hold      {o} {by_key[o]['name']!r}: its proofs disagree with {k}'s, nothing lent")
                continue
            labs = dict((v, lab) for v, lab in by_key[o].get("values") or [])
            for v in proved[k]:
                if v in src:
                    derived[o][v] = "derived"
                if v in src and labs.get(v) != src[v]:
                    changed.append((o, by_key[o]["name"], v, labs.get(v), src[v]))
                    labs[v] = src[v]
            by_key[o]["values"] = [[v, lab] for v, lab in sorted(labs.items())]
    # a value a later option left as it was (carried over) is that option's too: one name for both (one_name), unless
    # the option's label names another value of the record (ISO AUTO Maximum keeping its value under Minimum's options)
    for e in report:
        for c in e.get("carried_over") or []:
            k, v, r = c["key"], c.get("value"), e["records"].get(c["key"])
            if c.get("hand_rule") or r is None or k not in by_key or e["row"] in pickers or isinstance(v, (list, dict)):
                continue
            writers = {clean(lab) for lab, w in r["proved"].items() if w == v}
            other = {lab for w, lab in by_key[k].get("values") or [] if w != v}
            if writers and clean(c["label"]) not in other:
                assigned[(k, v)] |= writers | {clean(c["label"])}
    # a value two rows named apart gets one name, not the last row's (one_name)
    for (k, v), names in sorted(assigned.items(), key=lambda kv: (kv[0][0], value_order(kv[0][1]))):
        if len(names) > 1 and k in by_key:
            one = one_name(names)
            print(f"  one name  {k} {v!s:>4}: {sorted(names)} -> {one!r}")
            for pair in by_key[k].get("values") or []:
                if pair[0] == v and pair[1] != one:
                    changed.append((k, by_key[k]["name"], v, pair[1], one))
                    pair[1] = one
    # a sub-choice's labels without its option's name before them (option_prefix_out): the option it sits under, or
    # the one every proved label of a row started with, for a setting that is not its row's own
    for x in doc["settings"]:
        opts = {x["under_option"]} if x.get("under_option") else set()
        if x.get("row") and placement.norm(x["name"]) != placement.norm(x["row"][-1]):
            opts |= prefixes.get(x["key"], set())
        vals = x.get("values") or []
        heads = {str(lab).split(": ", 1)[0].strip() for _, lab in vals if ": " in str(lab)}
        if not opts or len(heads) != 1:
            continue                       # options told apart by their heads ("Spot: XL", "Tracking: Wide"): kept
        outs = [option_prefix_out(lab, opts) for _, lab in vals]
        if len(set(outs)) < len(outs):
            continue                       # stripped, two values would read alike
        for pair, out in zip(vals, outs, strict=True):
            if out != pair[1]:
                changed.append((x["key"], x["name"], pair[0], pair[1], out))
                pair[1] = out
    # an unproved value left in the old form beside proved ones in the new: the mode letter beside the mode names
    # (MODE_LETTERS), a bare number beside numbers that all carry one unit ("120" beside "60fps"); source "derived"
    letters = {b: a for a, b in MODE_LETTERS.items()}
    for x in doc["settings"]:
        vals, seen = x.get("values") or [], set((x.get("proved") or {}).get("values") or ())
        labs = [str(lab) for _, lab in vals]
        units = {m[2] for lab in labs if (m := re.fullmatch(r"(\d+(?:\.\d+)?)([A-Za-z]+)", lab))}
        with_unit = sum(bool(re.fullmatch(r"\d+(?:\.\d+)?[A-Za-z]+", lab)) for lab in labs)
        for pair in vals:
            if pair[0] in seen or not isinstance(pair[1], str):
                continue
            new = None
            if pair[1] in letters and any(lab in MODE_LETTERS for lab in labs):
                new = letters[pair[1]]
            elif re.fullmatch(r"\d+(?:\.\d+)?", pair[1]) and len(units) == 1 and with_unit >= 3 \
                    and with_unit == len(labs) - sum(bool(re.fullmatch(r"\d+(?:\.\d+)?", lab)) for lab in labs):
                new = pair[1] + next(iter(units))
            if new and new != pair[1]:
                changed.append((x["key"], x["name"], pair[0], pair[1], new))
                pair[1] = new
                derived[x["key"]][pair[0]] = "derived"
    # an option still named with its sub-choice's value from an earlier pass loses it too (axis_tail_out)
    for x in doc["settings"]:
        if not x.get("row") or x.get("expert"):
            continue
        labs = dict((v, lab) for v, lab in x.get("values") or [])
        for pair in x.get("values") or []:
            if isinstance(pair[1], str) and ":" in pair[1] and (x["key"], pair[0]) not in CAROUSEL:
                out = axis_tail_out(pair[1], pair[0], x, subs, axes, " > ".join(x["row"]), labs)
                if out != pair[1]:
                    changed.append((x["key"], x["name"], pair[0], pair[1], out))
                    labs[pair[0]] = pair[1] = out
    for k in EV_DOWN_FROM_20 & set(by_key):
        chose = hold_chosen(proved.get(k, ()), set((by_key[k].get("proved") or {}).get("values") or ()) & written.get(k, set()),
                            start_only[k])
        for pair in by_key[k].get("values") or []:
            # a code the hold's proofs chose is the hand table's; any other the rule counts out in quarter stops, as
            # the live list's thirds and halves are, which no line rule may infer (every value must be seen):
            # "counted", no camera's word, until the live table is proved in full and names it (hold_tables)
            over[k][pair[0]] = "hand table" if pair[0] in chose else "counted"
            if pair[1] != ev_label(pair[0]):
                changed.append((k, by_key[k]["name"], pair[0], pair[1], ev_label(pair[0])))
                pair[1] = ev_label(pair[0])
    # a hold's copy of a live setting named by the live table once that is proved in full (HOLD_TABLES), and a hold
    # proved in full lending its table to the other holds, each with what proves it in the note's evidence
    hold_tables(by_key, proved, report, over, derived, changed)
    hold_table_lines(by_key, proved, menus, changed)
    # records the schema did not have, proved through checklists: added with the file's own layout;
    # others like a sibling record (NEW_LIKE)
    for e in report:
        row = re.sub(r" \[field \d+\]$", "", e["row"])
        for k, r in e["records"].items():
            if r["verdict"] != "new" or k in by_key or k.split("[")[0] in by_key:
                continue                           # a slot of a record held whole (0x0e84) is no setting of its own
            if k in NEW_LIKE:
                s = like_setting(k, by_key, e, r)
                doc["settings"].append(s)
                by_key[k] = s
                menus[k].add(menu_row(row, axis_rows))
                note_readers(readers, k, r)
                derived[k].update({v: "derived" for v, _ in s["values"] if v not in r["proved"].values()})
                if "[field" in e["row"]:
                    proved.setdefault(k, set())
                    sampled.setdefault(k, {"proofs": 0, "linear": None})["proofs"] += e["options"]
                else:
                    proved[k] |= set(r["proved"].values())
                changed.append((k, s["name"], "new", None, s["values"]))
                continue
            if kinds.get(row) != "checklist" and not row.startswith("Reg. Custom Shoot Set"):
                continue
            s = new_setting(k, row, r["proved"])
            if s is None:
                continue
            doc["settings"].append(s)
            by_key[k] = s
            menus[k].add(menu_row(row, axis_rows))
            note_readers(readers, k, r)
            proved[k] |= set(r["proved"].values())
            changed.append((k, s["name"], "new", None, s["values"]))
    # White Balance fine-tune: the grid's readout at both ends decides which side is negative; when
    # the camera stores A7 (or G7) as +7000 the schema's whole scale is the wrong way round
    # (2026-10-29: "A-B: A7" on screen stored +7000). Each proved record is relabelled from end to end.
    for e in report:
        for k, r in e["records"].items():
            s = by_key.get(k)
            if s is None or not s["name"].startswith("WB fine-tune") or r["verdict"] == "new":
                continue
            neg_side = next((lab[0] for lab, v in r["proved"].items() if v == -7000 and lab[:1] in "ABGM"), None)
            if neg_side is None:
                continue
            pos_side = {"A": "B", "B": "A", "G": "M", "M": "G"}[neg_side]
            vals = []
            for v, lab in s.get("values") or []:
                new = "0" if v == 0 else f"{neg_side if v < 0 else pos_side}{abs(v) / 1000:g}"
                if new != lab:
                    changed.append((k, s["name"], v, lab, new))
                vals.append([v, new])
                if k not in sampled:
                    derived[k][v] = "derived"          # the whole scale named from its two proved ends
            s["values"] = vals
            menus[k].add(e["row"].split(" / ")[0])
            if k not in sampled:                       # a grid sampled on its line names every step "sampled"
                note_readers(readers, k, r)
                proved[k] |= set(r["proved"].values())
    # Focus Area records: the camera's names for every area, proved or not
    for s in doc["settings"]:
        if s["name"].startswith(("Focus Area memory", "Focus Area kind memory", "Focus Area remembered",
                                 "Tracking start area memory")):
            vals = []
            for v, lab in s.get("values") or []:
                new = fa_names.get(lab, lab)
                if new != lab:
                    changed.append((s["key"], s["name"], v, lab, new))
                if lab in fa_names:
                    derived[s["key"]][v] = "derived"   # the names Focus Area Limit lists
                vals.append([v, new])
            s["values"] = vals
    # ISO Range Limit: an index into the ISO table (ISO 50 = 2 ... ISO 102400 = 35, as ISO's own
    # record); every entry gets the whole table, not just the samples
    iso = {v: lab for v, lab in by_key[ISO_TABLE]["values"] if v >= 2}
    for s in doc["settings"]:
        if s["name"].startswith("ISO Range Limit"):
            derived[s["key"]].update({v: "derived" for v in iso})      # ISO's own table
        if s["name"].startswith("ISO Range Limit") and s.get("values") != sorted([v, lab] for v, lab in iso.items()):
            changed.append((s["key"], s["name"], "table", len(s.get("values") or []), len(iso)))
            s["values"] = sorted([v, lab] for v, lab in iso.items())
    # an array's slots of one name share one code table when the camera shows them one list and no proofs of theirs
    # disagree (Picture Profile's Color Mode): linked by a value proved alike, or by a label one slot's row refused
    # (in any state: the row without its context) that another proved
    blocks = blocked(RUN)
    refused = {k: {lab for row in menus[k] for lab, _ in blocks.get(re.sub(r" \[[^\]]*\]$", "", row), ())}
               | {b["label"] for b in by_key[k].get("menu_blocked") or []} for k in proved}
    print(f"one table: {one_slot_table(doc, proved, derived, changed, refused)} values named afresh from another slot "
          "of their array")
    kept_old = {}                      # the old values each proof keeps that this report did not credit (kept_proof)
    by_lines = by_lines_of(FRAME_PROOFS)
    for k in proved:
        s = by_key[k]
        # the run of its latest proof: the main run's, dated DATE as ever, or another run's (AF Area Registration's, the
        # filter boxes', a proof recorded with its run), dated by that proof's download (pass2_report.latest_run)
        by_run, on = latest_run(came.get(k), RUN.name, DATE)
        new = {"run": by_run, "date": on, "menu": sorted(menus[k])}
        if k in sampled:
            new["sampled"] = sampled[k]
        elif from_start[k] and not proved[k]:
            new["sampled"] = {"proofs": from_start[k], "linear": None, "from_start": True}
        else:
            new["values"] = sorted(proved[k])           # never which of them no option wrote (decision 16)
        s["proved"], kept_old[k] = kept_proof(None if k in by_lines else s.get("proved"), new,
                                              frozenset(start_only[k] - proved[k]), frozenset(written.get(k, ())))
        mb = []
        for row in s["proved"]["menu"]:
            for lab, why in blocks.get(row, []):
                # the refusal's label as the camera showed it, the list's as a reader read it: spaces aside ("Black &
                # White" refused, "Black&White" listed on PP10's Color Mode)
                v = next((v for v, l2 in s.get("values") or [] if squashed(l2) == squashed(lab)), None)
                mb.append({"value": v, "label": lab, "reason": why, "menu": row})
        if mb:
            s["menu_blocked"] = mb
        elif "menu_blocked" in s:
            del s["menu_blocked"]
    # a name the camera corrected on one key is corrected on every key of its family
    for x in doc["settings"]:
        fam = x["name"].split(":")[0]
        for pair in x.get("values") or []:
            fix = corrected.get((fam, pair[0], pair[1]))
            if fix:
                changed.append((x["key"], x["name"], pair[0], pair[1], fix))
                pair[1] = fix
                derived[x["key"]][pair[0]] = "derived"
    # a key or tile proved in full lends the codes it proved to the slots sampled against it
    proved_codes = collections.defaultdict(set)
    for e in report:
        if e["row"] in pickers:
            for k, r in e["records"].items():
                proved_codes[k] |= set(r["proved"].values())
    for full, against in picker_groups().items():      # the slots sampled against the one proved in full
        if full not in by_key:
            continue
        # the group shares the full slot's code table (each sampled slot's proofs agreed with it): the codes the full
        # slot proved, and a code another slot of the group proved that the full slot's list names alike. The playback
        # Fn picker lists 33 functions on every slot, and its full slot's walk proved 32 (never its first, Send, 1204),
        # which Upper 4's walk proved. A record the proofs tie to a group by its first change that holds no such list
        # (Rating's copy, 0x16bd, on the playback Custom Key picker) lends and takes nothing beyond it
        group = [full] + sorted(k for k in against if k != full)
        labels_full = dict((v, lab) for v, lab in by_key[full].get("values") or [])
        table = {v: labels_full[v] for v in sorted(proved_codes[full]) if v in labels_full}
        for k in group[1:]:
            labs = dict((v, lab) for v, lab in (by_key.get(k) or {}).get("values") or [])
            for v in sorted(proved_codes[k]):
                if v in labels_full and labs.get(v) == labels_full[v]:
                    table.setdefault(v, labels_full[v])
        for k in group:
            s = by_key.get(k)
            if s is None or not s.get("values"):
                continue
            have = {v for v, _ in s["values"]}
            derived[k].update({v: "derived" for v in table})
            add = [[v, lab] for v, lab in sorted(table.items()) if v not in have]
            for v, lab in add:
                changed.append((k, s["name"], v, None, lab))
            s["values"] = sorted(s["values"] + add)
    for (rec, v), lab in shared.items():           # the other slots of a picker record: same codes
        for s in doc["settings"]:
            if s["key"].split("[")[0] == rec and s.get("values"):
                derived[s["key"]][v] = "derived"
            if s["key"].split("[")[0] == rec and s.get("values") and v not in {x for x, _ in s["values"]}:
                changed.append((s["key"], s["name"], v, None, lab))
                s["values"] = sorted(s["values"] + [[v, lab]])
    latest = camset_read(sorted(p for p in (RUN_ROOT / "kit2_dial" / "dat").glob("*.DAT") if not p.name.startswith("_camlink_upload"))[-1])
    # a guessed record this body's file does not hold (2026-10-30: "WB fine-tune A-B (Custom 1-3)",
    # 0x0c65 / 0x0c67 / 0x0c69; the Custom grids write G-M only) is dropped: nothing could set it
    for s in list(doc["settings"]):
        m = re.fullmatch(r"(global|set):0x([0-9a-f]+)(?:[\[@].*)?", s["key"])
        if m and s.get("source") == "Derived" and latest.get(0 if m.group(1) == "global" else 1,
                                                             int(m.group(2), 16)) is None:
            changed.append((s["key"], s["name"], "dropped", s["name"], "(not in this body's file)"))
            doc["settings"].remove(s)
            by_key.pop(s["key"], None)
    for k, live in HOLD_BRACKET_COPIES.items():
        if live in by_key:                           # the live list's labels, by place from 0
            NEW_RECORDS[k]["values"] = [[i, lab] for i, (_, lab) in enumerate(sorted(by_key[live]["values"]))]
    for k, info in NEW_RECORDS.items():
        (derived if k in HOLD_BRACKET_COPIES else over)[k].update(
            {v: "derived" if k in HOLD_BRACKET_COPIES else "hand table" for v, _ in info["values"]})
        if k in by_key:                              # added before: keep its words current
            # a record FRAME_PROOFS fills keeps its values and note from there
            fix = {f: info[f] for f in ("name", "values", "note") if fix_differs(by_key[k], {f: info[f]})
                   and not (k in FRAME_PROOFS and f in ("values", "note"))}
            if fix:
                changed.append((k, by_key[k]["name"], ",".join(fix), None, info["name"]))
                apply_fix(by_key[k], fix)
            continue
        if info["like"] not in by_key:
            continue
        base, rid = by_key[info["like"]], int(k.split("0x")[1], 16)
        sec = 1 if k.startswith("set:") else 0
        rec = latest.get(sec, rid)
        s = {f: base[f] for f in ("area", "tab", "group", "order", "scalar", "modes") if f in base}
        s.update(key=k, id=rid, name=info["name"], source="Derived", values=info["values"], note=info["note"],
                 in_sets=latest.get(1, rid) is not None, size=rec.size, count=rec.count, scalar=rec.count == 1)
        doc["settings"].append(s)
        by_key[k] = s
        changed.append((k, s["name"], "new", None, info["values"]))
    for lay in doc.get("layouts") or []:          # the layout's model page, docs/models/<key>.md (as seed names it)
        if lay.get("doc") != f"docs/models/{target.stem}.md":
            lay["doc"] = f"docs/models/{target.stem}.md"
            changed.append(("layout " + lay["signature"], lay.get("model", ""), "doc", None, lay["doc"]))
    for (k, v), lab in VALUE_FIXES.items():
        over[k][v] = "hand table"
        for pair in (by_key[k].get("values") or []) if k in by_key else []:
            if pair[0] == v and pair[1] != lab:
                changed.append((k, by_key[k]["name"], v, pair[1], lab))
                pair[1] = lab
    for k, fix in RECORD_FIXES.items():
        if k in by_key and fix_differs(by_key[k], fix):
            changed.append((k, by_key[k]["name"], "name", by_key[k]["name"], fix["name"]))
            apply_fix(by_key[k], fix)
    # PP7-PP9 (elements 6-8 of each profile array) are not on this body's menu (2026-10-30): the list
    # offers PP1-PP6, PP10, PP11 in Stills and Movie mode alike, and Log Shooting on greys it out.
    # Why (2026-10-31): they are the first a1's log presets, kept in the file but dropped from this
    # body, whose log shooting has its own menu; PP7's gamma and colour mode are values it refuses
    off_menu = ("PP%d is not on the ILCE-1M2's menu (fw 4.00): the Picture Profile list offers PP1-PP6, PP10 "
                "and PP11 in Stills and Movie mode, and greys out with Log Shooting on (2026-10-30). The "
                "file still holds it, filled even after Initialize with the first a1's log presets: PP7 "
                "S-Log2 / S-Gamut, PP8 S-Log3 / S-Gamut3.Cine, PP9 S-Log3 / S-Gamut3 (Sony's ILCE-1 Help "
                "Guide lists PP1-PP11; the ILCE-1M2's lists PP1-PP6, PP10, PP11 and PPLUT1-4, and sets log "
                "shooting in Log Shooting Setting). PP7's Gamma 15 and Color Mode 11 are not in this body's "
                "lists, and a file that puts them in PP1 is refused (2026-10-31).")
    for k, r in by_key.items():
        if (r.get("note") or "").startswith("Picture Profile parameter") and r.get("index") in (6, 7, 8):
            line = off_menu % (r["index"] + 1)
            if line not in r["note"] and split_evidence(line)[0] not in r["note"]:
                changed.append((k, r["name"], "note", None, line[:60]))
                kept = re.sub(r"\s*PP\d is not on the ILCE-1M2's menu.*$", "", r["note"], flags=re.S)
                put_note(r, (kept + " " + line).strip())
    # Each Picture Profile parameter is kept three times: the one in use, the stills copy and the movie
    # copy, as Different Set for Still/Mv keeps ISO and White Balance. Stills edits write the first two;
    # in Movie mode (the switch, 2026-11-01) PP1's Black Level wrote the first and third (runs/kit2_pass2,
    # context "Movie mode"). The third was once taken for the factory default a profile's Reset uses:
    # Reset gives Sony's values whatever it holds (runs/kit2_ppreset)
    # whether an edit in one mode writes the other mode's copy too is Different Set for Still/Mv's Picture Profile box,
    # the camera's own setting and not proved yet: the notes say what each mode's edit was seen to write, never that
    # the other copy stays (nor how the box stood, decision 16)
    movie_note = ("Movie mode's copy of this Picture Profile parameter: editing the profile in Movie mode writes it "
                  "and the one in use; whether a Stills edit writes it too is Different Set for Still/Mv's Picture "
                  "Profile box, not proved yet. Not the factory default: a profile's Reset gives Sony's values "
                  "whatever this holds (2026-11-01).")
    stills_note = ("The stills copy of this Picture Profile parameter: editing the profile in Stills mode writes it "
                   "and the one in use; whether a Movie edit writes it too is Different Set for Still/Mv's Picture "
                   "Profile box, not proved yet (2026-11-01).")
    old_stills_note = ("The stills copy of this Picture Profile parameter: editing the profile in Stills mode writes it "
                       "and the one in use; Movie mode writes the movie copy instead.")
    # PP7-PP9 are on no menu (elements 6-8): nothing was proved of what writes their copies, which are laid out alike
    stills_note_off = ("The stills copy of this Picture Profile parameter, laid out as PP1-PP6, PP10 and PP11's are, where "
                       "editing the profile in Stills mode writes it and the one in use; no menu reaches PP7-PP9 "
                       "(2026-11-01).")
    movie_note_off = ("Movie mode's copy of this Picture Profile parameter, laid out as PP1-PP6, PP10 and PP11's are, "
                      "where editing the profile in Movie mode writes it and the one in use; no menu reaches PP7-PP9. "
                      "Not the factory default: a profile's Reset gives Sony's values whatever this holds (2026-11-01).")
    pp_live = {}
    for k, r in by_key.items():
        g = r.get("group") or ""
        m = re.fullmatch(r"Picture Profile (PP\d+)", g)
        if m and r.get("index") is not None and k.startswith("global:0x"):
            pp_live.setdefault((m.group(1), re.sub(r" \((stills|in use)\)$", "", r["name"])), []).append(k)
    for (_pp, name), keys in pp_live.items():
        if len(keys) != 2:
            continue
        stills = max(keys, key=lambda k: int(k.split("0x")[1][:4], 16))      # the higher record is the stills copy
        r = by_key[stills]
        if r["name"] != f"{name} (stills)":
            changed.append((stills, r["name"], "name", r["name"], f"{name} (stills)"))
            r["name"] = f"{name} (stills)"
        line = stills_note_off if r.get("index") in (6, 7, 8) else stills_note
        for old in (old_stills_note, split_evidence(stills_note)[0]):     # earlier words, the evidence kept
            if old != split_evidence(line)[0] and old in (r.get("note") or ""):
                r["note"] = r["note"].replace(old, split_evidence(line)[0])
        add_line(r, line)
    old_movie_note = ("Movie mode's copy of this Picture Profile parameter: editing the profile in Movie mode writes it "
                      "and the one in use, and Stills edits never touch it. Not the factory default: a profile's Reset "
                      "gives Sony's values whatever this holds.")
    for r in by_key.values():
        line = movie_note_off if r.get("index") in (6, 7, 8) else movie_note
        if r.get("note") in (old_movie_note, split_evidence(movie_note)[0]):     # earlier words, the evidence kept
            r["note"] = split_evidence(line)[0]
    for k, r in by_key.items():
        g = r.get("group") or ""
        if g.startswith(("Picture Profile default ", "Picture Profile third copy ")):
            base = re.sub(r" \((factory default|third copy)\)$", "", r["name"])
            fix = {"group": "Picture Profile " + g.split()[-1], "name": f"{base} (movie)", "note": movie_note}
            if fix_differs(r, fix):
                changed.append((k, r["name"], "name", r["name"], fix["name"]))
                apply_fix(r, fix)
    # the two copies of each Creative Look's base look (2026-11-01, runs/kit2_csr): a file set C1-C6 apart
    # in all three arrays, then Camera Settings Reset put all three back to Sony's base looks
    look_copy = ("One of two copies of each look's base look beside the one in use (0x0cbe). Changing a custom "
                 "look's base look writes only 0x0cbe, in the Stills menu and in Movie mode's alike (C1 through "
                 "eight looks, Picture Profile Off, 2026-11-02), so neither copy is Movie's. Camera Settings "
                 "Reset puts all three back to Sony's base looks (C1-C6: ST, FL, IN, SH, VV2, BW) whatever a file "
                 "had put in each, so neither copy is what the reset reads (2026-11-01). A base-look change in "
                 "S&Q (Program Auto) and in Time-lapse writes only 0x0cbe too, and so does the look panel's own "
                 "Reset (C4), which puts the parameters back and keeps the base (runs/kit2_lookreset, 2026-11-03): "
                 "no menu action writes either copy. Not a per-mode Creative Look: Different Set for Still/Mv "
                 "lists no Creative Look on this body (Aperture, Shutter Speed, ISO, Exposure Comp., Metering "
                 "Mode, White Balance, Picture Profile; runs/kit2_diffset), and only the base look is kept three "
                 "times, the eight parameters once each (the owner checked by hand that the looks are the same in "
                 "Stills, Movie and S&Q, 2026-11-03). Recorded by the values the camera writes into it (the "
                 "owner's call, 2026-11-03): the reset's Sony base look, and each built-in look's own number, in "
                 "0x0cbe's numbering. What the camera uses it for is unknown.")
    for k, r in by_key.items():
        if k.startswith(("global:0x0f9b[", "global:0x0fbb[")) and not note_is(r, look_copy):
            changed.append((k, r["name"], "note", None, look_copy[:60]))
            put_note(r, look_copy)
    # the copies proved by what the camera itself writes there (runs/kit2_csr: Camera Settings Reset put Sony's
    # base looks into all three lists), labelled with 0x0cbe's proved list; the built-in looks hold their own
    # number in every file, as 0x0cbe's do
    base_labels = (by_key.get("global:0x0cbe[10]") or {}).get("values") or []
    for arr in ("0x0f9b", "0x0fbb"):
        for i in range(18):
            v = i if i < 10 else ([0, 5, 6, 7, 4, 8][i - 10] if i < 16 else i - 6)
            FRAME_PROOFS[f"global:{arr}[{i}]"] = {
                "note": look_copy, "values": base_labels, "proved": [v], "run": "kit2_csr", "date": "2026-11-01",
                "menu": "Setup > Reset/Save Settings > Setting Reset > Camera Settings Reset (all three lists to Sony's base looks)"}
    # why a record stays unproved, when no proof can be made (2026-11-03, the owner: "the picture profiles are
    # proven that they are not on this camera ... can we also mark them"): a third state beside proved and not
    # proved, as test tools keep "not applicable" and "skipped" apart from a failure; the records the hand table names
    # (UNPROVED: a working value of the camera's, a value only its own saves write, equipment, a network block, or every
    # candidate row tried), each until a proof reaches it (2026-11-09)
    for k, r in by_key.items():
        why = None
        if not r.get("proved") and k in UNPROVED and not {"proved", "sampled"} & set(FRAME_PROOFS.get(k) or ()):
            kind, date, text = UNPROVED[k]
            why = {"kind": kind, "date": date, "why": text}
        elif not r.get("proved") and (r.get("group") or "") in ("Picture Profile PP7", "Picture Profile PP8", "Picture Profile PP9"):
            why = {"kind": "not_on_camera", "date": "2026-10-30",
                   "why": f"{r['group'][len('Picture Profile '):]} is not on the ILCE-1M2's menu (firmware 4.00): the "
                          "Picture Profile list offers Off, PP1-PP6, PP10 and PP11, so no menu writes it."}
        elif not r.get("proved") and mirror_place(k, mirror)[0] and 4 <= mirror_place(k, mirror)[0] <= 12 \
                and mirror_place(k, mirror)[1] in (260, 262):
            why = {"kind": "not_on_camera", "date": "2026-11-02",
                   "why": "Never written on this camera: sets 4-12 are the Movie, S&Q and Time-lapse memories (1-3 "
                          "each), and registering them leaves the raw stop values as they were; only Stills memories "
                          "write them. Their F-number and shutter are proved."}
        if why and r.get("unproved_reason") != why:
            changed.append((k, r["name"], "unproved_reason", None, why["kind"]))
            r["unproved_reason"] = why
        elif not why and "unproved_reason" in r:
            del r["unproved_reason"]
    # the same fact on a memory set's own block (0x0180), for the sets where the live copy of that set's block
    # says no proof can reach the field: one schema key covers all twelve sets, so it says which (2026-11-03)
    for k, r in by_key.items():
        m = re.fullmatch(rf"set:0x{mirror['set_record']:04x}@(\d+)", k) if mirror else None
        if not m:
            continue
        reasons = {n: (by_key.get(mirror_key(mirror, n, int(m[1]))) or {}).get("unproved_reason")
                   for n in mirror["sections"]}
        sets = [n for n, w in reasons.items() if w]
        if sets:
            w = reasons[sets[0]]
            r["unproved_sets"] = {"sets": sets, "kind": w["kind"], "why": w["why"], "date": w.get("date", "")}
        else:
            r.pop("unproved_sets", None)
    for (k, v), lab in PP7_VALUES.items():
        over[k][v] = "hand table"
        if k in by_key and v not in {x for x, _ in by_key[k].get("values") or []}:
            changed.append((k, by_key[k]["name"], v, None, lab))
            by_key[k]["values"] = sorted((by_key[k].get("values") or []) + [[v, lab]])
    for k, fp in FRAME_PROOFS.items():
        s = by_key.get(k)
        if s is None:
            continue
        # the owner's word for a never-open row, when the hand table's proof was made with it, in the note's evidence
        want = {"note": fp["note"] + (f" ({fp['allowance']})" if fp.get("allowance") else "")}
        if "values" in fp:
            want["values"] = fp["values"]
            over[k].update({v: "hand table" for v, _ in fp["values"]})
        for f, v in want.items():
            if fix_differs(s, {f: v}):
                changed.append((k, s["name"], f, None, str(v)[:40]))
                apply_fix(s, {f: v})
        if "values" in fp and "range" in s:
            del s["range"]                         # a place on a grid, not a number
        if "proved" not in fp and "sampled" not in fp:
            continue                               # names and note only: the report's proof stands (by_lines_of)
        menu = fp.get("menu", "Camera Set. Memory (registered after moving the focus frame)")
        proof = {"run": fp.get("run", "kit2_frame_reg"), "date": fp.get("date", "2026-10-31"),
                 "menu": sorted(menu) if isinstance(menu, list) else [menu]}
        if "proved" in fp and fp.get("linear"):
            # a scale whose proofs lie on a line, both ends among them (sampled_scale: Audio Rec Level), is sampled: its
            # values between are inferred, and the proofs are not listed (the level put back is the camera's own)
            if sampled_scale(s, fp["proved"]):
                proof["sampled"] = {"proofs": len(fp["proved"]), "linear": True}
            else:
                print(f"  frame proofs  {k}: said to lie on a line, but its proofs do not (both ends, every proof on the "
                      "line); kept as proved values")
                proof["values"] = fp["proved"]
        else:
            proof.update({"values": fp["proved"]} if "proved" in fp else {"sampled": {"proofs": fp["sampled"], "linear": None}})
        got = registered.pop(k, None)
        if got and "values" in proof:
            # the values a registration wrote here (a zone place, framepos_run.py --zone-grid), each under the table's
            # own label; the latest run and day
            labels = dict((v, lab) for v, lab in fp.get("values") or s.get("values") or [])
            fits = {v for v, lab in got["values"].items() if labels.get(v) == lab}
            for v in sorted(set(got["values"]) - fits):
                print(f"  registered {k} {v}: the line calls it {got['values'][v]!r}, the table {labels.get(v)!r}; "
                      "not credited")
            proof["values"] = sorted(set(proof["values"]) | fits)
            if fits and (got["date"] or "", got["run"]) > (proof["date"], proof["run"]):
                proof.update(run=got["run"], date=got["date"])
            if got.get("allowance"):
                allowed[k].add(got["allowance"])
        if s.get("proved") != proof:
            s["proved"] = proof
        proved.setdefault(k, set(fp.get("proved", [])) | set((s.get("proved") or {}).get("values") or ()))
    # My Menu's six pages (2026-10-31): 42 known codes loaded by a file, one per slot, and read back on
    # the pages by a page scan (runs/kit2_mymenu_scan/mymenu_readback.json, every page in order): the
    # slot records are proved in place, each with the code it showed
    readback = RUN_ROOT / "kit2_mymenu_scan" / "mymenu_readback.json"
    if readback.exists():
        pages = read_json(readback)
        for pg, info in pages.items():
            if not info.get("in_order"):
                continue
            rec = doc["camera"]["my_menu"]["records"][int(pg) - 1]      # the camera file's page records
            for i, (code, name) in enumerate(info["slots"]):
                k = f"global:0x{rec:04x}[{i}]"
                if k not in by_key:
                    continue
                labels = dict((v, lab) for v, lab in by_key[k].get("values") or [])
                if labels.get(code) != name:
                    changed.append((k, by_key[k]["name"], code, labels.get(code), name))
                    labels[code] = name
                    by_key[k]["values"] = [[v, lab] for v, lab in sorted(labels.items())]
                proof = {"run": "kit2_mymenu_scan", "date": "2026-10-31", "values": [code],
                         "menu": ["My Menu (a code loaded by a file, read back on its page)"]}
                readers[k][code] = "one reader"            # its name read back on the page
                if (by_key[k].get("proved") or {}).get("names"):
                    proof["names"] = by_key[k]["proved"]["names"]
                if by_key[k].get("proved") != proof:
                    by_key[k]["proved"] = proof
                proved.setdefault(k, {code})
    # My Menu Setting > Add Item: each item's code named in all 42 slots, after the read-back so it is not overwritten
    mm_records = mymenu_slots(doc)
    n_items = my_menu_tables(doc, my_menu_items(all_proofs, by_key, sorted(mm_records)), sorted(mm_records), changed,
                             readers, derived, proved) if mm_records else 0
    print(f"my menu: {n_items} codes from Add Item proofs, named in every slot; the empty place named in "
          f"{my_menu_empty(doc, sorted(mm_records), over, changed) if mm_records else 0} slots (a hand table)")
    held = collections.defaultdict(set)
    for e in report:
        m = ORIENTED.search(e["row"])
        if m:
            for k in e["records"]:
                held[k].add(m.group(1))
    for k, ways in held.items():
        line = (f"With Switch V/H AF Area on, Focus Area writes it only with the camera {' or '.join(sorted(ways))} "
                f"(proved holding the camera each way, 2026-10-30).")
        if k in by_key and add_line(by_key[k], line):
            changed.append((k, by_key[k]["name"], "note", None, line[:60]))
    for s in doc["settings"]:
        if s["key"] == "global:0x04e2" and s.get("range") == [0, 255]:
            s["range"] = [0, 127]
    # a Picture Profile parameter's movie copy and its stills copy (or the unnamed one) offer the same values: a value
    # one copy proved and the other lacks or names otherwise unproved is copied over, either way (source "derived")
    pp = {(x["name"], x.get("group"), x.get("index")): x for x in doc["settings"]
          if re.search(r"\bPP\d+$", x.get("group") or "")}
    for (name, group, index), mv in pp.items():
        if not name.endswith(" (movie)"):
            continue
        base = name[: -len(" (movie)")]
        st = pp.get((base + " (stills)", group, index)) or pp.get((base, group, index))
        if st is None or not mv.get("values") and not st.get("values"):
            continue
        for cp, src in ((mv, st), (st, mv)):
            seen = set((cp.get("proved") or {}).get("values") or ())
            labs, moved = dict((v, lab) for v, lab in cp.get("values") or []), False
            for v in (src.get("proved") or {}).get("values") or []:
                lab = dict(src.get("values") or []).get(v)
                if lab is not None and v not in seen:
                    derived[cp["key"]][v] = "derived"
                if lab is not None and v not in seen and labs.get(v) != lab:
                    changed.append((cp["key"], cp["name"], v, labs.get(v), lab))
                    labs[v], moved = lab, True
            if moved:
                cp["values"] = [[v, lab] for v, lab in sorted(labs.items(), key=lambda kv: value_order(kv[0]))]
    # one name per code in each picker family (family_name)
    reads = collections.defaultdict(dict)
    for e in report:
        if e["row"] not in pickers:
            continue
        for k, r in e["records"].items():
            fam = picker_family((by_key.get(k) or {}).get("name"))
            for lab, v in (r.get("proved") or {}).items() if fam else []:
                src = reader_source((r.get("names") or {}).get(lab))
                was = reads[(fam, v)].get(clean(lab))
                if was is None or READER_RANK.index(src) < READER_RANK.index(was):
                    reads[(fam, v)][clean(lab)] = src
    slots = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for x in doc["settings"]:
        fam = picker_family(x["name"])
        for v, lab in x.get("values") or [] if fam else []:
            slots[(fam, v)][lab][0] += 1
            slots[(fam, v)][lab][1] += len(proved.get(x["key"]) or ()) >= 10
    chosen = {}
    for (fam, v), names in sorted(slots.items(), key=lambda kv: (kv[0][0], value_order(kv[0][1]))):
        if len(names) > 1:
            chosen[(fam, v)] = family_name(names, reads.get((fam, v), {}))
            print(f"  family    {fam} {v!s:>5}: {dict(sorted((k, tuple(c)) for k, c in names.items()))} -> "
                  f"{chosen[(fam, v)]!r}")
    for x in doc["settings"]:
        fam = picker_family(x["name"])
        for pair in x.get("values") or [] if fam else []:
            one = chosen.get((fam, pair[0]))
            if one and pair[1] != one:
                changed.append((x["key"], x["name"], pair[0], pair[1], one))
                pair[1] = one
                derived[x["key"]][pair[0]] = "derived"
                if over[x["key"]].get(pair[0]) == "schema kept":
                    over[x["key"]][pair[0]] = "derived"
    disputed_out(doc, disputed & set(by_key))
    for k in disputed:
        proved.pop(k, None)
    with_scales(doc, RUN)
    by_key = {s["key"]: s for s in doc["settings"]}
    # values the menus never offer, each where its evidence holds (writer/offered.py); a held one the ISO table names
    tables_file = RUN_ROOT / "kit2_tables" / "tables.json"
    not_offered_marks(doc, NOT_OFFERED, report, read_json(tables_file) if tables_file.exists() else {}, RUN_ROOT)
    for entry in NOT_OFFERED:
        src, k = by_key.get(entry.get("named_by", "")), entry["key"]
        for m in (by_key.get(k) or {}).get("not_offered") or [] if src else []:
            if m["value"] in entry["values"] and m["value"] in ((src.get("proved") or {}).get("values") or ()) \
                    and dict((v, lab) for v, lab in src["values"]).get(m["value"]) == m["label"]:
                derived[k][m["value"]] = "derived"
    # the values offered under one video system only, from the rows walked under each (their downloads' headers), and
    # the copies the camera keeps of a live value, where its downloads bear the rule out (writer/offered.py, copies.py)
    with_video_systems(doc, report, all_proofs, VIDEO_SYSTEM_VALUES, RUN_ROOT, RUN)
    check_video_systems(doc, RUN_ROOT)          # no download of one system holds a value listed as the other's
    with_copies(doc, COPIES, RUN_ROOT, modes=COPY_MODES, unknown=COPY_MODES_UNKNOWN)
    spelled_names(by_key, spelled, over, derived)
    with_menu_rows(doc, axis_rows)      # the rows the definition kept from an older run, named so too
    for s in doc["settings"]:
        with_names(s, readers[s["key"]], over[s["key"]], derived[s["key"]])
    without_observed(doc)           # the old lists of what the owner's files held: an editor reads the proofs
    for k in sorted(registered):        # registered values no hand table's proof took in: printed, not credited
        print(f"  registered {k}: {len(registered[k]['values'])} values registered ({registered[k]['run']}), but no "
              "hand table's proof of it takes them in; not credited")
    in_sets, took = with_in_sets_proved(doc, mirrors), with_allowances(doc, allowed)
    # every setting whose note says the owner's word, from the proof lines (with_allowances) or a hand table's own
    # "allowance" (FRAME_PROOFS), its evidence split from the note or not yet
    carry = sum(1 for s in doc["settings"] if ALLOWANCE.search(f"{s.get('note_evidence') or ''} {s.get('note') or ''}"))
    print(f"in sets: {in_sets} live settings whose memory copy a registration was seen to take "
          f"({', '.join(sorted({m['run'] for m in mirrors.values()})) or 'none'}); allowances: {took} settings took the "
          f"owner's word for a never-open row from proof lines into their evidence; {carry} carry one (proof lines and "
          "hand tables)")
    open_ones = questions(report, unresolved, frozenset(by_key))
    print(f"{len(proved)} records marked proved; {len(changed)} labels changed or added; "
          f"{sum(1 for k in proved if with_.get(k))} written with other records (the report's); "
          f"{sum(1 for k in proved if by_key[k].get('menu_blocked'))} with menu-blocked options")
    print_kept(kept_old, by_key)
    for k, name, v, old, new in changed:
        print(f"  {k} {name[:44]:44s} {v!s:>4}: {old!r} -> {new!r}")
    seen_review = set()
    for k, v, had, read in review:                  # one line per code, not per slot
        if (v, had) not in seen_review:
            seen_review.add((v, had))
            print(f"  review {k} {v!s:>5}: schema {had!r}, camera read {read!r}")
    for k in proved:
        for b in by_key[k].get("menu_blocked", []):
            print(f"  blocked {k} {b['label']!r} (value {b['value']}): {b['reason'][:90]!r}")
    # the camera's help text is Sony's: it is read into the private help file, and the published schema carries
    # the project's own words (docs/decisions/0018). The schema held Sony's until 2026-11-03, so a first run
    # without the private file starts from what the schema has.
    private = help_files.PRIVATE / help_files.name(doc)
    had = help_files.taken(doc)
    help_files.put(doc, help_files.read(private, doc) or had)
    n_help, n_opt = attach_help(doc, report, [r for i, r in enumerate(all_proofs) if i not in cut_short])
    with_menu(doc)                       # the menu list from the camera's menu tree, before the groups are named by it
    print(f"groups: {camera_group_names(doc)} settings put under the camera's own group name; "
          f"{mirror_names(doc)} of the memories' live copy renamed")
    sony = help_files.taken(doc)
    n_own = own_help(doc)
    print(f"help: {n_help} settings with the camera's In-Camera Guide text ({n_opt} with help for their options), "
          f"kept in {paths.shown(private)}; {n_own} with the project's own in the definition")
    with_option_trees(doc, RUN)
    doc = from_data(doc)                 # the parts from data/, as --from-data gives them, last
    print(f"expert: {sum(1 for s in doc['settings'] if s.get('expert'))} settings shown in Expert mode only")
    names = collections.Counter(src for s in doc["settings"] for src in ((s.get("proved") or {}).get("names") or {}).values())
    print(f"names: {dict(names.most_common())}")
    gate(open_ones, target.stem, a.force, a.write and not a.dry_run)
    if a.write and not a.dry_run:
        write_definition(target, doc, a.accept_stale)      # every refusal first, then the reset file, then this
        print(f"wrote {target}")
        help_files.write(private, doc, sony, help_files.SONY_SOURCE)
        print(f"wrote {private}")
        say_stale(target)


def drop_stale(target: Path, write: bool) -> None:
    """--drop-stale: the evidence file's "stale" section listed, by setting key (or layout signature) and field only,
    never a value, and taken out only with write (--drop-stale --write); the rest of the evidence file stays as it
    was."""
    ev = definitions.evidence_path(target)
    got = definitions.drop_stale(target, write)
    if not got:
        print(f"{paths.shown(ev)}: no \"stale\" section, nothing to drop")
        return
    print(f"{paths.shown(ev)}: the \"stale\" section holds {len(got)} pieces of evidence that no longer fit the "
          "definition:")
    for part, what, f in got:
        print(f"  {'layout ' if part == 'layouts' else ''}{what}: {f}")
    print("removed from the evidence file" if write else
          "nothing removed: kit/schema_update.py --drop-stale --write removes it")


if __name__ == "__main__":
    main()
