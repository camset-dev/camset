"""A camera's hand tables as a data file (data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, read by
kit/writer/hand_tables.py): each table in the shape the writer reads, the hand evidence put back into them, a camera
with no file given empty tables (the plain pass, as before), and a file that does not fit refused in plain words. Made-up
cameras and files where a test needs them; the a1 II's file as shipped."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, datafiles, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_tables  # noqa: E402

A1 = paths.A1II
CAM = "ILCE-0X0_fw1.00"             # a made-up camera


def a_camera(monkeypatch, tmp_path, tables=None, camera=CAM) -> Path:
    """A data folder and an evidence folder of the test's own; the made-up camera's tables file when `tables` is given
    (its JSON text, or a dict written as JSON). Returns the file's path."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    (tmp_path / "evidence").mkdir()
    p = datafiles.hand_tables_file(camera)
    if tables is not None:
        p.parent.mkdir(parents=True)
        p.write_text(tables if isinstance(tables, str) else json.dumps({"camera": camera, **tables}), encoding="utf-8")
    return p


def test_a_camera_with_no_hand_tables_file_has_every_table_empty(monkeypatch, tmp_path):
    """Another mapper's camera, with no hand tables file: every table the writer reads is there and empty, in its
    shape, and no evidence is put back; kit/schema_update.py gives it the plain pass, as before the tables were data
    (test_definitions.py: test_the_a1_pass_runs_for_the_a1_definition_only)."""
    a_camera(monkeypatch, tmp_path)
    got = hand_tables.load(CAM)
    assert got.HAND_EVIDENCE is None
    assert {n: getattr(got, n) for n in hand_tables.TABLES} == hand_tables.empty()
    assert set(vars(got)) == set(hand_tables.TABLES) | {"HAND_EVIDENCE"}
    assert (type(got.KEEP_LABELS), type(got.COPY_MODES_UNKNOWN), type(got.NOT_OFFERED), got.ORIENTED, got.ISO_TABLE) == \
        (set, frozenset, list, None, None)


def test_a_made_up_camera_runs_the_plain_pass_with_its_tables_file_unread(monkeypatch, tmp_path):
    """Until each camera's pass reads its own hand tables (Stage 2 of the plan), a camera other than the a1 II takes
    the plain pass whether it has a hand tables file or not: schema_update dispatches to generic_main before any table
    is read."""
    import schema_update as S
    a_camera(monkeypatch, tmp_path, {"KEEP_LABELS": ["global:0x0001"]})
    called = []
    monkeypatch.setattr(S, "generic_main", lambda target, run, write, force=False, accept_stale=False:
                        called.append(target.stem))
    monkeypatch.setattr(S, "RUN_ROOT", Path("/nowhere") / CAM)
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    S.main()
    assert called == [CAM]


def test_the_a1_iis_tables_are_in_the_shapes_the_writer_reads():
    """The a1 II's file read without evidence: key lists are sets, rows tuple-keyed dicts in the file's order, a
    reason a (kind, day, why) tuple, a not-offered mark's table a tuple, the orientation pattern compiled, and each of
    FILTER_FLAGS' entries NEW_RECORDS' own object, first in NEW_RECORDS as the file lists them."""
    T = hand_tables.load(A1, evidence=False)
    assert T.HAND_EVIDENCE is None
    assert isinstance(T.KEEP_LABELS, set) and isinstance(T.COPY_MODES_UNKNOWN, frozenset)
    assert list(T.CAROUSEL)[:3] == [("global:0x0350", 2), ("global:0x0e06", 2), ("global:0x0e68", 3)]
    assert T.VALUE_FIXES[("global:0x118b", 1)] == "Time-lapse" and T.FRAME_STEPS[("Large", "Custom 1")] == (56, 38)
    assert all(isinstance(v, tuple) and len(v) == 3 and v[1] is None for v in T.UNPROVED.values())
    assert T.NEW_LIKE["global:0x0b63"] == ("global:0x0b65", "ISO Range Limit (upper)")
    assert T.LATE_COPY[0x16bd].startswith(" The second copy of this box") and isinstance(T.COPY_MODES, tuple)
    assert T.NOT_OFFERED[0]["table"] == ("Custom Key/Dial Set.", "Dial/Wheel")
    assert T.ORIENTED.search("Focus Area [Switch V/H AF Area = AF Point + AF Area, camera grip up]")[1] == "grip up"
    assert all(T.NEW_RECORDS[k] is e for k, e in T.FILTER_FLAGS.items())
    assert list(T.NEW_RECORDS)[:len(T.FILTER_FLAGS)] == list(T.FILTER_FLAGS)
    assert set(vars(T)) == set(hand_tables.TABLES) | {"HAND_EVIDENCE"}


def test_the_shipped_file_holds_no_key_and_no_row_twice():
    """JSON keeps the last of two equal keys without a word, so a table entry given twice would vanish: the shipped
    file holds every object's keys once, and every tuple-keyed table's rows once (the reader refuses either)."""
    for p in sorted((ROOT / "data").glob("*/hand_tables_*_fw*.json")):
        twice = []

        def once(pairs, p=p, twice=twice):
            keys = [k for k, _ in pairs]
            twice.extend(k for k in set(keys) if keys.count(k) > 1)
            return dict(pairs)
        doc = json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=once)
        assert twice == [], (p.name, twice)
        for name in ("CAROUSEL", "VALUE_FIXES", "PP7_VALUES", "FRAME_STEPS"):
            rows = [tuple(r[:2]) for r in doc.get(name) or []]
            assert len(rows) == len(set(rows)), (p.name, name)
        hand_tables.read(p, p.parent.name)              # and the reader takes it


def j(**tables) -> str:
    """A made-up camera's tables file holding `tables`, as JSON text."""
    return json.dumps({"camera": CAM, **tables})


ENTRY = {"like": "global:0x0003", "name": "A", "values": [], "note": ""}
NOT_OFFERED = {"key": "global:0x0001", "values": [1], "why": "Not on its list.", "menu": "Row"}
DEEP = 100000                      # deeper than Python's parser follows


@pytest.mark.parametrize("text, words", [
    # a key or a row twice, another camera, an unknown table, not JSON
    ('{"camera": "ILCE-0X0_fw1.00", "RECORD_FIXES": {"global:0x0001": {"name": "A"}, "global:0x0001": {"name": "B"}}}',
     "'global:0x0001' is there twice"),
    (j(CAROUSEL=[["global:0x0001", 1, "A"], ["global:0x0001", 1, "B"]]), "CAROUSEL holds ('global:0x0001', 1) twice"),
    (j(KEEP_LABELS=["global:0x0001", "global:0x0001"]), "KEEP_LABELS holds 'global:0x0001' twice"),
    ('{"camera": "ILCE-9X9_fw1.00"}', "its camera is 'ILCE-9X9_fw1.00'"),
    (j(NEW_TABLE={}), "the kit knows no table 'NEW_TABLE'"),
    ('{"camera": "ILCE-0X0_fw1.00", ', "cannot be read as JSON"),
    ('{"camera": "ILCE-0X0_fw1.00", "ZONE": [[NaN, "A"]]}', "cannot be read as JSON (NaN is no number JSON has)"),
    ('{"camera": "ILCE-0X0_fw1.00", "ZONE": [[-Infinity, "A"]]}', "-Infinity is no number JSON has"),
    ('{"camera": "ILCE-0X0_fw1.00", "ZONE": ' + "[" * DEEP + "]" * DEEP + "}", "nested deeper than the reader follows"),
    # a table of the wrong JSON type: refused, never iterated as another (a string as a list of its letters)
    (j(NEW_LIKE=[]), "NEW_LIKE is not in its shape: the table is an array, not an object"),
    (j(LATE_COPY=["x"]), "LATE_COPY is not in its shape: the table is an array, not an object"),
    (j(UNPROVED=[]), "UNPROVED is not in its shape: the table is an array, not an object"),
    (j(NOT_OFFERED={"global:0x0001": NOT_OFFERED}), "NOT_OFFERED is not in its shape: the table is an object, not an array"),
    (j(KEEP_LABELS="abc"), "KEEP_LABELS is not in its shape: the table is a string, not an array"),
    (j(COPY_MODES_UNKNOWN="abc"), "COPY_MODES_UNKNOWN is not in its shape: the table is a string, not an array"),
    (j(COPY_MODES="Stills"), "COPY_MODES is not in its shape: the table is a string, not an array"),
    (j(CAROUSEL={"global:0x0001": {"1": "A"}}), "CAROUSEL is not in its shape: the table is an object, not an array"),
    (j(FRAME_STEPS={"Standard": {}}), "FRAME_STEPS is not in its shape: the table is an object, not an array"),
    (j(ZONE={"0": "Centre"}), "ZONE is not in its shape: the table is an object, not an array"),
    (j(RECORD_FIXES=[]), "RECORD_FIXES is not in its shape: the table is an array, not an object"),
    (j(ISO_TABLE=["global:0x0334"]), "ISO_TABLE is not in its shape: the table is an array, not a string"),
    (j(MY_MENU_EMPTY="(empty)"), "MY_MENU_EMPTY is not in its shape: the table is a string, not an object"),
    # an entry or an item of the wrong type, or without a field the writer reads
    (j(NOT_OFFERED=["x"]), "NOT_OFFERED is not in its shape: mark 0 is a string, not an object"),
    (j(NOT_OFFERED=[{**NOT_OFFERED, "values": 1}]), "mark 0's 'values' is a whole number, not an array"),
    (j(NOT_OFFERED=[{k: v for k, v in NOT_OFFERED.items() if k != "why"}]), "mark 0 has no 'why'"),
    (j(NOT_OFFERED=[{**NOT_OFFERED, "table": "Dial/Wheel"}]), "mark 0's table is 'Dial/Wheel', not [table, page or null]"),
    (j(UNPROVED={"global:0x0001": "abc"}), "UNPROVED is not in its shape: 'global:0x0001' is 'abc', not [kind, null, why]"),
    (j(UNPROVED={"global:0x0001": ["state", None]}), "'global:0x0001' is ['state', None], not [kind, null, why]"),
    (j(UNPROVED={"global:0x0001": ["state", "2026-01-02", "Why."]}), "(the day is the hand evidence's)"),
    (j(KEEP_LABELS=[1]), "KEEP_LABELS is not in its shape: item 0 is a whole number, not a string"),
    (j(COPY_MODES=["Stills"]), "COPY_MODES is not in its shape: item 0 is a string, not an array"),
    (j(NEW_LIKE={"global:0x0001": ["global:0x0002", "A"]}), "'global:0x0001' is an array, not an object"),
    (j(NEW_LIKE={"global:0x0001": {"name": "A"}}), "NEW_LIKE is not in its shape: 'global:0x0001' has no 'like'"),
    (j(LATE_COPY={"5821": "x"}), "LATE_COPY is not in its shape: '5821' is not a record id"),
    (j(LATE_COPY={"0x16bd": 1}), "LATE_COPY is not in its shape: '0x16bd' is a whole number, not a string"),
    (j(CAROUSEL=[["global:0x0001", "1", "A"]]), "row 0 is ['global:0x0001', '1', 'A'], not [key, value, label]"),
    (j(CAROUSEL=["global:0x0001"]), "row 0 is 'global:0x0001', not [key, value, label]"),
    (j(VALUE_FIXES=[["global:0x0001", True, "A"]]), "VALUE_FIXES is not in its shape: row 0 is"),
    (j(FRAME_STEPS=[["Standard", "Spot M", 30]]), "FRAME_STEPS is not in its shape: row 0 is"),
    (j(FRAME_PROOFS={"global:0x0001": "A note."}), "FRAME_PROOFS is not in its shape: 'global:0x0001' is a string"),
    (j(FRAME_PROOFS={"global:0x0001": {"values": []}}), "FRAME_PROOFS is not in its shape: 'global:0x0001' has no 'note'"),
    (j(FRAME_PROOFS={"global:0x0001": {"note": "N.", "values": [[0, "A", 1]]}}),
     "'global:0x0001''s 'values'[0] is [0, 'A', 1], not a [code, name] pair"),
    (j(NEW_RECORDS={"global:0x0001": {k: v for k, v in ENTRY.items() if k != "values"}}), "'global:0x0001' has no 'values'"),
    (j(FILTER_FLAGS={"global:0x0001": {**ENTRY, "like": 3}}), "'global:0x0001''s 'like' is a whole number, not a string"),
    (j(HOLD_TABLES={"global:0x0001": {"live": "global:0x0002", "mirror": "40"}}), "'mirror' is a string, not a whole number or null"),
    (j(VIDEO_SYSTEM_VALUES={"global:0x0001": {"NTSC": []}}), "'global:0x0001' has no 'PAL'"),
    (j(ZONE=[[0, "Centre"], ["1", "Up"]]), "ZONE is not in its shape: the table[1] is ['1', 'Up'], not a [code, name] pair"),
    (j(COPIES={"global:0x0001": "global:0x0002"}), "COPIES is not in its shape: 'global:0x0001' is a string, not an array"),
    (j(LABEL_FIXES={"Slip": 1}), "LABEL_FIXES is not in its shape: 'Slip' is a whole number, not a string"),
    (j(MY_MENU_EMPTY={"label": "(empty)"}), "MY_MENU_EMPTY is not in its shape: it has no 'line'"),
    # the patterns the writer runs, each compiled (and each replacement tried) as the file is read
    (j(CONTEXT_WORDS={"Slot (": "x"}), "CONTEXT_WORDS is not in its shape: a pattern, 'Slot (', is no pattern Python reads"),
    (j(CONTEXT_WORDS={"Slot": "\\9"}), "the words for 'Slot', '\\\\9', are no replacement Python reads"),
    (j(CONTEXT_WORDS={"Slot": "\\g<x>"}), "the words for 'Slot', '\\\\g<x>', are no replacement Python reads"),
    (j(CONTEXT_WORDS={"Slot": 1}), "the words for 'Slot' is a whole number, not a string"),
    (j(NOT_OFFERED=[{**NOT_OFFERED, "walk": "^Row ["}]), "mark 0's walk, '^Row [', is no pattern Python reads"),
    (j(ORIENTED="camera (level"), "ORIENTED is not in its shape: the table, 'camera (level', is no pattern Python reads"),
    (j(ORIENTED="camera level"), "ORIENTED is not in its shape: 'camera level' has no group, and the writer reads its first"),
    # My Menu's empty line: {code} is the one field, put in as text
    (j(MY_MENU_EMPTY={"label": "(empty)", "line": "An empty place stores {x}."}), "holds a brace that is not {code}"),
    (j(MY_MENU_EMPTY={"label": "(empty)", "line": "Stores {code.__class__}."}), "holds a brace that is not {code}"),
    (j(MY_MENU_EMPTY={"label": "(empty)", "line": "Stores {code}}."}), "holds a brace that is not {code}"),
    # a $ref only ever a NEW_RECORDS entry naming FILTER_FLAGS' entry of the same key
    (j(NEW_RECORDS={"global:0x0002": {"$ref": "#/FILTER_FLAGS/global:0x0001"}}, FILTER_FLAGS={"global:0x0001": ENTRY}),
     "a $ref there is only ever FILTER_FLAGS' entry of the same key"),
    (j(NEW_RECORDS={"global:0x0001": {"$ref": "#/FILTER_FLAGS/global:0x0001"}}), "FILTER_FLAGS must hold it"),
    (j(FILTER_FLAGS={"global:0x0001": {"$ref": "#/NEW_RECORDS/global:0x0001"}}),
     "FILTER_FLAGS is not in its shape: 'global:0x0001' is a $ref, which only a NEW_RECORDS entry may be"),
    (j(RECORD_FIXES={"global:0x0001": {"$ref": "#/FILTER_FLAGS/global:0x0001"}}), "is a $ref, which only a NEW_RECORDS"),
])
def test_a_tables_file_that_does_not_fit_is_refused_in_plain_words(monkeypatch, tmp_path, text, words):
    """A key or a row twice, another camera's file, a table the kit does not know, a file that is not JSON (NaN and
    Infinity too) or nests past what the parser follows, a table or an entry of the wrong JSON type (never a string
    iterated as a list of its letters) or without a field the writer reads, a pattern or a replacement that does not
    compile, My Menu's empty line with a field other than {code}, a $ref anywhere but a NEW_RECORDS entry naming
    FILTER_FLAGS' entry of the same key: refused as the file is read, before the writer trips on it, nothing read, the
    file and the table named and what was expected said; a SystemExit with no traceback, and a ValueError for a caller
    that reports and goes on."""
    p = a_camera(monkeypatch, tmp_path, text)
    with pytest.raises(hand_tables.Refused) as got:
        hand_tables.load(CAM)
    said = str(got.value)
    assert words in said and p.name in said and "mend the file by hand" in said, said
    assert issubclass(hand_tables.Refused, SystemExit) and issubclass(hand_tables.Refused, ValueError)


def test_a_tables_file_saved_with_a_byte_order_mark_reads(monkeypatch, tmp_path):
    """A file a Windows editor saved with a byte order mark (Notepad's UTF-8) reads as one without."""
    a_camera(monkeypatch, tmp_path, "\ufeff" + j(KEEP_LABELS=["global:0x0001"], CONTEXT_WORDS={r"Slot (\d+)": r"slot \1"}))
    got = hand_tables.load(CAM)
    kept, words = got.KEEP_LABELS, got.CONTEXT_WORDS
    assert kept == {"global:0x0001"} and words == {r"Slot (\d+)": r"slot \1"}


def test_my_menus_empty_line_takes_the_code_as_text(monkeypatch):
    """schema_update puts the camera file's empty code into My Menu's empty line in place of {code}, as text: the
    line is data, so it is never formatted (a field there would run on the code), and the reader refuses any other
    brace in it."""
    import collections
    import schema_update as S
    monkeypatch.setattr(S, "MY_MENU_EMPTY", {"label": "(empty)", "line": "An empty place stores {code}."})
    slot = {"key": "global:0x0c8a[0]", "area": "global", "id": 3210, "index": 0, "name": "My Menu 1: 1",
            "values": [[2, "x"]], "note": ""}
    over, changed = collections.defaultdict(dict), []
    assert S.my_menu_empty({"camera": {"my_menu": {"empty": 2}}, "settings": [slot]}, [3210], over, changed) == 1
    assert slot["note"] == "An empty place stores 2." and slot["values"] == [[2, "(empty)"]]


def test_the_hand_evidence_is_put_back_into_the_tables_read_from_the_file(monkeypatch, tmp_path):
    """load() puts the camera's hand evidence back once the tables are in their shapes: a note's evidence after the
    note, once on an entry FILTER_FLAGS and NEW_RECORDS share though both tables carry it, a reason's day into its
    tuple, a not-offered mark's evidence by its key, a proof's fields into a FRAME_PROOFS entry; load(evidence=False)
    leaves them out, and evidence for an entry the file lacks is refused."""
    entry = {"like": "global:0x0003", "name": "A box", "values": [[0, "Not ticked"], [1, "Ticked"]], "note": "A box."}
    a_camera(monkeypatch, tmp_path, {
        "FILTER_FLAGS": {"global:0x0001": entry},
        "NEW_RECORDS": {"global:0x0001": {"$ref": "#/FILTER_FLAGS/global:0x0001"},
                        "global:0x0002": {"like": "global:0x0003", "name": "B", "values": [], "note": ""}},
        "FRAME_PROOFS": {"global:0x0002": {"note": "What B holds."}},
        "UNPROVED": {"global:0x0004": ["state", None, "A working value."]},
        "NOT_OFFERED": [{"key": "global:0x0005", "values": [3], "walk": "^Row$", "why": "Not on the list.", "menu": "Row"}]})
    evidence = hand_evidence.path(CAM)
    evidence.write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": CAM, "tables": {
        "FILTER_FLAGS": {"global:0x0001": {"note+": "(seen, 2026-01-02)"}},
        "NEW_RECORDS": {"global:0x0001": {"note+": "(seen, 2026-01-02)"}},
        "FRAME_PROOFS": {"global:0x0002": {"proved": [0], "run": "kit2_x", "date": "2026-01-02", "menu": "Row"}},
        "UNPROVED": {"global:0x0004": {"1": "2026-01-02"}},
        "NOT_OFFERED": {"0": {"$key": "global:0x0005", "evidence": "walked whole"}}}}), encoding="utf-8")
    got = hand_tables.load(CAM)
    assert evidence == got.HAND_EVIDENCE
    assert got.NEW_RECORDS["global:0x0001"] is got.FILTER_FLAGS["global:0x0001"]
    assert got.FILTER_FLAGS["global:0x0001"]["note"] == "A box. (seen, 2026-01-02)"
    assert got.FRAME_PROOFS["global:0x0002"] == {"note": "What B holds.", "proved": [0], "run": "kit2_x",
                                                 "date": "2026-01-02", "menu": "Row"}
    assert got.UNPROVED["global:0x0004"] == ("state", "2026-01-02", "A working value.")
    assert got.NOT_OFFERED[0]["evidence"] == "walked whole"
    public = hand_tables.load(CAM, evidence=False)
    assert public.HAND_EVIDENCE is None and public.FILTER_FLAGS["global:0x0001"]["note"] == "A box."
    assert hand_evidence.public_tables(CAM)["UNPROVED"] == {"global:0x0004": ("state", None, "A working value.")}
    hand_evidence.path(CAM).write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": CAM, "tables": {
        "FRAME_PROOFS": {"global:0x0099": {"run": "kit2_x"}}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="no entry 'global:0x0099'"):
        hand_tables.load(CAM)


def test_converting_hand_evidence_needs_the_cameras_tables_file(monkeypatch, tmp_path):
    """kit/writer/hand_evidence.py --convert reads the public tables from the camera's tables file; a camera without
    one has no hand evidence to convert, and says so."""
    a_camera(monkeypatch, tmp_path)
    with pytest.raises(SystemExit, match="has no hand tables"):
        hand_evidence.public_tables(CAM)


# the sentences the hand tables repeat in several notes, each group's notes saying them alike from the marker on
# (None: the whole note): one fact, so a change to one copy and not the others fails here
REPEATED = {
    "the level Zone places": (("set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f2c", "set:0x0f2e", "set:0x0f30"), None),
    "the vertical Zone places": (("set:0x0f32", "set:0x0f34", "set:0x0f36", "set:0x0f38", "set:0x0f3a", "set:0x0f3c"), None),
    "the spot's point": (("set:0x019c", "set:0x01be", "set:0x019e", "set:0x01c4"), None),
    "the vertical points": (("set:0x01c0", "set:0x01c6", "set:0x01c2", "set:0x01c8"),
                            " Written when a memory slot is registered: with the camera held that way"),
    "a point's frame positions": (("set:0x019c", "set:0x01c0", "set:0x01c6", "set:0x01c2", "set:0x01c8"),
                                  " With Switch V/H AF Area Off, Left and Up presses under Spot S"),
    "a Custom box's place": (tuple(f"set:0x{r:04x}" for r in [0x1327, 0x1329, *range(0x1333, 0x1356, 2),
                                                               *range(0x139f, 0x13aa, 2)]),
                             " Written when a memory slot is registered: moving the box"),
    "a Custom box's size": (tuple(f"set:0x{r:04x}" for r in [*range(0x14b4, 0x14bf, 2), *range(0x1488, 0x148f, 2), 0x14b0,
                                                              0x14b2, *range(0x14c0, 0x14cb, 2)]),
                            " Kept only in the memory sets"),
    "Preset Focus/Zoom": (("global:0x167c", "global:0x16a1", "global:0x1694", "global:0x1682", "global:0x1688",
                           "global:0x1732", "global:0x1437", "global:0x16f3", "global:0x168e", "global:0x172c",
                           "global:0x0b75"), "Preset Focus/Zoom's six slots"),
    "AF Area Registration": (tuple(f"global:{r}" for r in ("0x0e7a", "0x0e7c", "0x0e7e", "0x0f80", "0x0f82", "0x0f84",
                                                           "0x0e74", "0x0e76", "0x0e78", "0x0f8c", "0x0f8e", "0x0f90")),
                             None),
}


@pytest.mark.parametrize("group", REPEATED)
def test_a_sentence_the_tables_repeat_is_said_alike_in_every_note(group):
    """JSON has no fragments to share (the Python tables built these notes from one sentence each), so the file says
    each repeated sentence again in every note of its group: they stay word for word alike, the Zone places' values are
    ZONE, and each group's count is the camera's."""
    keys, marker = REPEATED[group]
    fp = hand_tables.load(A1, evidence=False).FRAME_PROOFS
    tails = {fp[k]["note"][fp[k]["note"].index(marker):] if marker else fp[k]["note"] for k in keys}
    assert len(tails) == 1, (group, tails)
    if "Zone" in group:
        assert all(fp[k]["values"] == hand_tables.load(A1, evidence=False).ZONE for k in keys)
    assert len(keys) == {"a Custom box's place": 26, "a Custom box's size": 18, "Preset Focus/Zoom": 11,
                         "AF Area Registration": 12}.get(group, len(keys))


def test_no_tracked_file_names_the_tables_module_that_is_gone():
    """The ILCE-1M2's hand tables were a Python module in the kit until they became its data file: no tracked file
    names that module any more (this test builds the name)."""
    gone = "a1_" + "tables"
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout
    here = Path(__file__).resolve().relative_to(ROOT.resolve()).as_posix()
    found = []
    for f in files.decode("utf-8").split("\0"):
        p = ROOT / f
        if not f or f == here or not p.is_file():
            continue
        try:
            if re.search(gone, p.read_text(encoding="utf-8")):
                found.append(f)
        except (UnicodeDecodeError, OSError):
            continue
    assert found == []
