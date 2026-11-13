"""A camera's hand tables are public and hold what the camera is; their evidence is the mapper's (docs/decisions/0016):
the tables file, data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, keeps no day, no run and no hand proof (its JSON
Schema refuses an evidence field in an entry, and check_public's rule refuses a run or a day in it), and
kit/writer/hand_evidence.py puts the evidence back from the private overlay (private/evidence/<model>_fw<fw>.hand.json)
when it is there. Made-up tables where a test needs them; the real evidence only where the mapper's computer has it."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, datafiles, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_tables  # noqa: E402

TABLES = sorted((ROOT / "data").glob("*/hand_tables_*_fw*.json"))
# a day, a run's name, a run's folder (runs/, or runs\ as Windows writes it) or a download's or a frame's file name: the
# evidence's, never a public table's
DAY_OR_RUN = re.compile(r"\b20\d\d-\d\d-\d\d\b|kit2_|runs[/\\]|\.(?:DAT|png|jpg)\b")
# the fields a hand proof's evidence is made of (run, day, the values it chose, its sample, the owner's word...), which
# no public table writes
EVIDENCE_KEYS = {"run", "date", "proved", "sampled", "linear", "allowance", "evidence", "files"}
# what the hand evidence may hold, by table: evidence only, so no public fact hides in the private file either
# (a note's evidence is its suffix, "note+": hand_evidence never replaces a public note)
EVIDENCE_FIELDS = {"FRAME_PROOFS": {"note+", "proved", "sampled", "linear", "run", "date", "menu", "allowance"},
                   "NEW_RECORDS": {"note+"}, "FILTER_FLAGS": {"note+"}, "RECORD_FIXES": {"note+"},
                   "NOT_OFFERED": {"$key", "evidence", "files"}, "VIDEO_SYSTEM_VALUES": {"evidence"},
                   "UNPROVED": {"1"}, "MY_MENU_EMPTY": {"line+"}}
# the mapper's hand evidence for the a1 II, where this computer holds the private overlay
HAND_EVIDENCE = hand_evidence.path(paths.A1II)


def test_there_is_a_hand_table_to_check():
    assert datafiles.hand_tables_file(paths.A1II) in TABLES


def walk(o, where=""):
    """(place, key or None, value) of every object key and every value in a JSON document."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{where}/{k}", k, v
            yield from walk(v, f"{where}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield f"{where}/{i}", None, v
            yield from walk(v, f"{where}/{i}")


@pytest.mark.parametrize("path", TABLES, ids=lambda p: p.parent.name)
def test_a_hand_table_holds_no_day_no_run_and_no_hand_proof(path):
    """No string in the file (a key or a value) names a day, a kit2_ run or a run's folder, no key is one of a proof's
    or the evidence's, and check_public's rule for a camera's data folder (datafiles.evidence_in_public, the one that
    refuses a commit) finds nothing in it."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    said = [where for where, k, v in walk(doc) for s in (k, v) if isinstance(s, str) and DAY_OR_RUN.search(s)]
    keys = [where for where, k, _ in walk(doc) if k in EVIDENCE_KEYS]
    assert not said, "a day or a run in a public hand table (the hand evidence's, kit/writer/hand_evidence.py):\n" + \
        "\n".join(said)
    assert not keys, "a hand proof's or the evidence's key in a public hand table:\n" + "\n".join(keys)
    assert datafiles.evidence_in_public(path) == []


def test_the_schema_refuses_a_hand_proofs_evidence_in_an_entry():
    """schemas/hand-tables.schema.json, which the hooks and CI check every hand tables file against, takes the a1 II's
    file and refuses it with any of the evidence's fields put into an entry (a proof's run or day, its values, the
    owner's word, a not-offered mark's evidence, a reason's day), and a table it does not know."""
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "hand-tables.schema.json").read_text(encoding="utf-8"))
    check = jsonschema.Draft202012Validator(schema)
    doc = json.loads(datafiles.hand_tables_file(paths.A1II).read_text(encoding="utf-8"))
    check.validate(doc)
    for name, key, field, value in (("FRAME_PROOFS", "set:0x019a", "run", "x"), ("FRAME_PROOFS", "set:0x019a", "proved", [0]),
                                    ("FRAME_PROOFS", "global:0x0052", "allowance", "x"),
                                    ("FRAME_PROOFS", "global:0x0018", "linear", True),
                                    ("RECORD_FIXES", "global:0x0df2", "note+", "x"),
                                    ("NEW_RECORDS", "set:0x023c", "date", "x"), ("NOT_OFFERED", 0, "evidence", "x"),
                                    ("NOT_OFFERED", 0, "files", ["a.DAT"]), ("UNPROVED", "global:0x1672", 1, "x"),
                                    ("MY_MENU_EMPTY", None, "line+", "x"), ("VIDEO_SYSTEM_VALUES", "global:0x0202",
                                                                             "evidence", "x")):
        bad = json.loads(json.dumps(doc))
        (bad[name] if key is None else bad[name][key])[field] = value      # a field, or a reason's day (index 1)
        assert not check.is_valid(bad), (name, key, field)
    assert not check.is_valid({**doc, "NEW_TABLE": {}})


def test_without_its_evidence_a_table_says_what_the_camera_is_and_nothing_of_how(monkeypatch, tmp_path):
    """The tables as a clone without the overlay reads them: a hand table's entry is its note and its value names,
    a not-offered mark and a video system's values carry no evidence, a reason no day, My Menu's empty line no run;
    and no note names a day or a run. load(evidence=False) reads them so."""
    whole = hand_tables.load(paths.A1II)               # with the mapper's evidence where this computer holds it
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    T = hand_tables.load(paths.A1II)
    assert T.HAND_EVIDENCE is None and vars(hand_tables.load(paths.A1II, evidence=False)) == vars(T)
    assert {k: set(fp) - {"note", "values"} for k, fp in T.FRAME_PROOFS.items() if set(fp) - {"note", "values"}} == {}
    assert not [m["key"] for m in T.NOT_OFFERED if {"evidence", "files"} & set(m)]
    assert not [k for k, e in T.VIDEO_SYSTEM_VALUES.items() if set(e) - {"NTSC", "PAL"}]
    assert {date for _, date, _ in T.UNPROVED.values()} == {None}
    notes = [fp["note"] for fp in T.FRAME_PROOFS.values()] + [T.MY_MENU_EMPTY["line"]]
    notes += [e.get("note") or "" for table in (T.NEW_RECORDS, T.RECORD_FIXES) for e in table.values()]
    assert not [n for n in notes if DAY_OR_RUN.search(n)]
    # the same keys, in the same order, as with the evidence put back: the evidence adds to entries, never makes one
    for name in ("FRAME_PROOFS", "NEW_RECORDS", "RECORD_FIXES", "NOT_OFFERED", "VIDEO_SYSTEM_VALUES", "UNPROVED"):
        mine, theirs = getattr(T, name), getattr(whole, name)
        assert (list(mine) if isinstance(mine, dict) else len(mine)) == \
            (list(theirs) if isinstance(theirs, dict) else len(theirs)), name


def test_put_back_patches_the_tables_it_names_and_refuses_what_does_not_fit(monkeypatch, tmp_path):
    """put_back: a dict's entry gets its fields added in place (an entry two tables share stays shared, and the
    evidence after its note, "note+", is put there once though both tables carry it), an empty field filled, a tuple
    rebuilt, a list's entry checked by its key; a file for another camera, a table, key or index the tables lack, or a
    key that is not the entry's, is refused. No file: None, the tables as they were."""
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    shared = {"note": "A."}
    tables = {"FP": {"a": shared, "b": {"note": "B.", "values": [[0, "x"]]}}, "NR": {"a": shared},
              "UN": {"k": ("state", None, "Why.")}, "NO": [{"key": "k", "values": [1]}, {"key": "j", "values": [2]}]}
    cam = "ILCE-0X0_fw1.00"
    assert hand_evidence.put_back(tables, cam) is None and tables["UN"]["k"][1] is None
    p = hand_evidence.path(cam)
    assert p == tmp_path / "ILCE-0X0_fw1.00.hand.json"

    def file(tables_patch, camera=cam, fmt=hand_evidence.FORMAT):
        import json
        p.write_text(json.dumps({"hand_format": fmt, "camera": camera, "tables": tables_patch}), encoding="utf-8")

    file({"FP": {"a": {"note+": "(seen, 2026-01-02)", "proved": [1], "run": "kit2_x"}, "b": {"date": "2026-01-02"}},
          "NR": {"a": {"note+": "(seen, 2026-01-02)"}},
          "UN": {"k": {"1": "2026-01-02"}}, "NO": {"1": {"$key": "j", "evidence": "walked"}}})
    got = dict(tables)
    assert hand_evidence.put_back(got, cam) == p
    assert got["FP"]["a"] == {"note": "A. (seen, 2026-01-02)", "proved": [1], "run": "kit2_x"}
    assert got["NR"]["a"] is got["FP"]["a"], "a shared entry stays shared"
    assert list(got["FP"]["b"]) == ["note", "values", "date"]
    assert got["UN"]["k"] == ("state", "2026-01-02", "Why.") and isinstance(got["UN"]["k"], tuple)
    assert got["NO"][1] == {"key": "j", "values": [2], "evidence": "walked"} and got["NO"][0] == {"key": "k", "values": [1]}
    for bad, words in (({"XX": {}}, "no table"), ({"NO": {"5": {"evidence": "e"}}}, "no entry"),
                       ({"NO": {"0": {"$key": "j", "evidence": "e"}}}, "the evidence is of")):
        file(bad)
        with pytest.raises(ValueError, match=words):
            hand_evidence.put_back(dict(tables), cam)
    file({}, camera="ILCE-9X9_fw1.00")
    with pytest.raises(ValueError, match="these tables read"):
        hand_evidence.put_back(dict(tables), cam)


def test_hand_evidence_adds_to_entries_and_never_rewrites_public_words(monkeypatch, tmp_path):
    """The reviewer's two holes (2026-11-11): a key a table lacks at the table's own level is refused (the evidence
    adds fields inside an existing entry, never an entry: one would reach the definition from the private file alone);
    and a note's evidence is its suffix only, so a contributor's fix to a public note stays: the note the writer reads
    is the corrected public note and the evidence after it, never an older copy of the note kept privately. A whole
    note in the evidence that would replace the public words is refused, saying to use the suffix."""
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    cam = "ILCE-0X0_fw1.00"

    def put(tables, patch):
        import json
        hand_evidence.path(cam).write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": cam,
                                                       "tables": patch}), encoding="utf-8")
        return hand_evidence.put_back(tables, cam)
    with pytest.raises(ValueError, match="no entry 'new'"):
        put({"FP": {"a": {"note": "A."}}}, {"FP": {"new": {"note+": "(seen, 2026-01-02)"}}})
    with pytest.raises(ValueError, match="no entry 'line2"):
        put({"EMPTY": {"line": "Empty."}}, {"EMPTY": {"line2+": "(runs/kit2_x)"}})
    fixed = {"FP": {"a": {"note": "A, corrected by a contributor."}}, "EMPTY": {"line": "Empty."}}
    put(fixed, {"FP": {"a": {"note+": "(seen, 2026-01-02)", "run": "kit2_x"}}, "EMPTY": {"line+": "(runs/kit2_x)"}})
    assert fixed == {"FP": {"a": {"note": "A, corrected by a contributor. (seen, 2026-01-02)", "run": "kit2_x"}},
                     "EMPTY": {"line": "Empty. (runs/kit2_x)"}}
    with pytest.raises(ValueError, match="would replace the public words"):
        put({"FP": {"a": {"note": "A, corrected."}}}, {"FP": {"a": {"note": "A (seen, 2026-01-02)."}}})


def test_hand_evidence_never_replaces_any_public_value(monkeypatch, tmp_path):
    """2026-11-11 review: any public value that is not a string (a list, a number, a bool) was silently replaced by the
    evidence. Now evidence may add a field an entry lacks, fill one that is None, keep one it holds the same, and add
    after a string ("<field>+"); replacing any other value is refused in plain words naming the table, key and field,
    and the tables are left for the caller to drop (put_back raises before the writer reads them)."""
    import json
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    cam = "ILCE-0X0_fw1.00"

    def put(tables, patch):
        hand_evidence.path(cam).write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": cam,
                                                       "tables": patch}), encoding="utf-8")
        return hand_evidence.put_back(tables, cam)
    for public, evidence in (([0, 1], [0, 1, 2]), (3, 4), (True, False), (0, None), ((1, 2), [1, 2, 3])):
        with pytest.raises(ValueError) as e:
            put({"FP": {"a": {"values": public}}}, {"FP": {"a": {"values": evidence}}})
        words = str(e.value)
        assert "FP" in words and "'a'" in words and "'values'" in words and "would replace the public" in words
    ok = {"FP": {"a": {"values": [0, 1], "sampled": None, "linear": True}}, "UN": {"k": ("state", None, "Why.")}}
    put(ok, {"FP": {"a": {"values": [0, 1], "sampled": 3, "linear": True, "run": "kit2_x"}}, "UN": {"k": {"1": "d"}}})
    assert ok == {"FP": {"a": {"values": [0, 1], "sampled": 3, "linear": True, "run": "kit2_x"}},
                  "UN": {"k": ("state", "d", "Why.")}}
    with pytest.raises(ValueError, match=r"UN: k\]\[0\]|UN\['k'\]\[0\]"):
        put({"UN": {"k": ("state", None, "Why.")}}, {"UN": {"k": {"0": "other"}}})


def test_format_one_hand_evidence_is_refused_with_how_to_convert_it(monkeypatch, tmp_path):
    """Format 1 kept a note's evidence as the whole note: put_back refuses it, naming the command that converts it, and
    hand_evidence.convert gives format 2 (the whole note's suffix after the public words as "note+"; a note that does
    not begin with the public words is listed and left for put_back to refuse by name)."""
    import json
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    cam = "ILCE-0X0_fw1.00"
    one = {"hand_format": 1, "camera": cam, "tables": {
        "FP": {"a": {"note": "A. (seen, 2026-01-02)", "run": "kit2_x"}, "b": {"note": "Changed since. (seen)"}},
        "LIST": {"0": {"$key": "k", "evidence": "walked"}}}}
    hand_evidence.path(cam).write_text(json.dumps(one), encoding="utf-8")
    tables = {"FP": {"a": {"note": "A."}, "b": {"note": "B."}}, "LIST": [{"key": "k", "values": [1]}]}
    with pytest.raises(ValueError) as e:
        hand_evidence.put_back(tables, cam)
    assert f"kit/writer/hand_evidence.py --convert --camera {cam}" in str(e.value) and "format 1" in str(e.value)
    two, left = hand_evidence.convert(one, tables)
    assert two["hand_format"] == hand_evidence.FORMAT
    assert two["tables"]["FP"]["a"] == {"note+": "(seen, 2026-01-02)", "run": "kit2_x"}
    assert two["tables"]["LIST"] == one["tables"]["LIST"] and left == ["FP['b']['note']"]
    two["tables"]["FP"].pop("b")
    hand_evidence.path(cam).write_text(json.dumps(two), encoding="utf-8")
    got = json.loads(json.dumps(tables))
    hand_evidence.put_back(got, cam)
    assert got["FP"]["a"] == {"note": "A. (seen, 2026-01-02)", "run": "kit2_x"}


def test_write_refuses_without_the_hand_evidence(monkeypatch):
    """kit/schema_update.py --write for the ILCE-1M2 refuses, in plain words and before it reads anything, when the
    hand tables' evidence is not here: a definition written so would lose every hand proof."""
    import schema_update as S
    monkeypatch.setattr(S, "HAND_EVIDENCE", None)
    monkeypatch.setattr(S, "RUN_ROOT", Path("/nowhere") / paths.A1II)
    monkeypatch.setattr(S.definitions, "load", lambda *a, **k: pytest.fail("read the definition"))
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--write"])
    with pytest.raises(SystemExit) as got:
        S.main()
    words = str(got.value.code)
    assert "nothing written" in words and "hand tables" in words and "would drop those proofs" in words
    assert f"{paths.A1II}.hand.json" in words


@pytest.mark.skipif(not HAND_EVIDENCE.exists(), reason="the hand tables' evidence is the mapper's (private/evidence/)")
def test_the_hand_evidence_holds_evidence_only():
    """The mapper's hand evidence names only evidence fields, table by table (EVIDENCE_FIELDS): a value name, a record
    name or a structure in it would be a public fact kept out of the public file. Every table it names is one the
    tables file holds (writer/hand_tables.TABLES)."""
    doc = json.loads(HAND_EVIDENCE.read_text(encoding="utf-8"))
    assert set(doc["tables"]) <= set(hand_tables.TABLES)
    assert doc["camera"] == paths.A1II and set(doc["tables"]) <= set(EVIDENCE_FIELDS)
    wrong = {}
    for name, patch in doc["tables"].items():
        for key, fields in patch.items():
            extra = set(fields) - EVIDENCE_FIELDS[name] if isinstance(fields, dict) else {"(whole)"}
            if name == "MY_MENU_EMPTY":
                extra = {key} - EVIDENCE_FIELDS[name]
            if extra:
                wrong[f"{name}[{key}]"] = sorted(extra)
    assert wrong == {}


@pytest.mark.skipif(not HAND_EVIDENCE.exists(), reason="the hand tables' evidence is the mapper's (private/evidence/)")
def test_a_note_in_the_hand_evidence_is_the_public_note_with_its_evidence():
    """A note's evidence in the hand evidence (its suffix, "note+", or My Menu's "line+") is evidence only: put after
    the public table's note, the note says, once its evidence is set apart (writer.notes.split_evidence), what the
    public note says. The written definition's note is the public one for every owner, and the private file only adds
    how and when it was found."""
    from writer.notes import split_evidence
    T = hand_tables.load(paths.A1II, evidence=False)          # the public tables, no evidence put back
    doc = json.loads(HAND_EVIDENCE.read_text(encoding="utf-8"))
    pairs = [(f"{name}[{key}]", getattr(T, name)[key].get("note") or "", fields["note+"])
             for name, patch in doc["tables"].items() for key, fields in patch.items()
             if isinstance(fields, dict) and "note+" in fields]
    pairs += [(f"MY_MENU_EMPTY[{k}]", T.MY_MENU_EMPTY[k[:-1]], v)
              for k, v in (doc["tables"].get("MY_MENU_EMPTY") or {}).items() if k.endswith("+")]
    assert pairs
    differ = [where for where, public, suffix in pairs
              if split_evidence(f"{public} {suffix}") != (public, split_evidence(f"{public} {suffix}")[1])
              or not split_evidence(f"{public} {suffix}")[1]]
    assert differ == []
    assert not [f"{name}[{key}]" for name, patch in doc["tables"].items() for key, fields in patch.items()
                if isinstance(fields, dict) and "note" in fields], "a whole note: the public words twice"


def test_format_one_hand_evidence_stops_the_tables_reading_in_plain_words(tmp_path):
    """Review 4 (2026-11-11): reading the tables puts the hand evidence back (writer/hand_tables.load, as
    kit/schema_update.py does when it is imported), so a format-1 file stopped every command with a traceback. Now it
    stops in plain words naming the command that converts it (and put_back's refusals are still ValueErrors for the
    callers that catch them)."""
    import os
    import subprocess
    (tmp_path / f"{paths.A1II}.hand.json").write_text(json.dumps({"hand_format": 1, "camera": paths.A1II,
                                                                  "tables": {}}), encoding="utf-8")
    got = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                          "from writer import hand_tables; hand_tables.load(sys.argv[2])", str(ROOT / "kit"),
                          paths.A1II], env={**os.environ, "CAMSET_EVIDENCE_DIR": str(tmp_path)},
                         capture_output=True, text=True)
    assert got.returncode == 1 and "Traceback" not in got.stderr
    assert "format 1" in got.stderr and f"kit/writer/hand_evidence.py --convert --camera {paths.A1II}" in got.stderr
    assert issubclass(hand_evidence.Refused, ValueError) and issubclass(hand_evidence.Refused, SystemExit)


def test_hand_evidence_holding_a_public_tuple_as_a_list_is_the_same_value(monkeypatch, tmp_path):
    """Review 4 (2026-11-11): JSON has no tuple, so evidence that holds a public tuple's very value reads as a list;
    _one takes the two as the same value (kept, the public tuple as it is) instead of refusing it as a replacement."""
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    cam = "ILCE-0X0_fw1.00"
    hand_evidence.path(cam).write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": cam, "tables": {
        "FP": {"a": {"values": [1, 2], "run": "kit2_x"}}}}), encoding="utf-8")
    tables = {"FP": {"a": {"values": (1, 2)}}}
    hand_evidence.put_back(tables, cam)
    assert tables["FP"]["a"] == {"values": (1, 2), "run": "kit2_x"} and isinstance(tables["FP"]["a"]["values"], tuple)
