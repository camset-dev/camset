"""The plain pass (kit/writer/generic.py, every camera's but the ILCE-1M2 firmware 4.00's) with the camera's own hand
tables (data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json, kit/writer/hand_facts.py): each table it reads takes
effect, a table only the ILCE-1M2's pass reads is refused in plain words, the hand evidence of the camera's mapper
(private/evidence/<model>_fw<fw>.hand.json) goes into the private evidence file and never into the public definition
(docs/decisions/0016), --write stops without that file when the tables need it, and a camera with no file, or one of
empty tables, gets the plain pass as before. A made-up camera (the a1 II's sample with another model name, its
camera file with the a1 II's container block), made-up proofs and made-up tables; no camera."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, datafiles, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_facts, hand_tables  # noqa: E402
# imported before any test points the kit at a data folder of its own: it binds the a1 II's tables as it is imported
import schema_update  # noqa: E402,F401

A1 = paths.A1II
CAM = "ILCE-7M5_fw4.00"             # made up: the a1 II's sample under another model name
DOC = definitions.load(A1, evidence=False)
SAMPLE = definitions.sample(DOC)
EVIDENCE_WORDS = re.compile(r"kit2_|runs/|\b20\d\d-\d\d-\d\d\b")


class Cam:
    """A made-up camera's folders: its data folder (the camera file, and the hand tables when written), the evidence
    folder (the hand evidence and the accepted file), its definitions folder and its runs, kit2_pass2 holding three
    downloads (a start file, an NTSC and a PAL one) the downloads manifest lists."""

    def __init__(self, tmp_path: Path, monkeypatch):
        self.data, self.evidence = tmp_path / "data", tmp_path / "evidence"
        (self.data / CAM).mkdir(parents=True)
        self.evidence.mkdir()
        monkeypatch.setattr(definitions, "DATA", self.data)
        monkeypatch.setattr(definitions, "DIR", tmp_path / "definitions")
        monkeypatch.setattr(definitions, "EVIDENCE_DIR", self.evidence)
        (tmp_path / "definitions").mkdir()
        import schema_update as S
        monkeypatch.setattr(S.help_files, "OWN", self.data)
        facts = {"$schema": "../../schemas/camera.schema.json", **json.loads(json.dumps(DOC["camera"]))}
        facts.update(model="ILCE-7M5", volatile_records=[], link_records=[])
        for k in ("sample", "main_tiles", "my_menu", "mirrors", "families", "exposure", "memory_sets"):
            facts.pop(k)
        (self.data / CAM / f"camera_{CAM}.json").write_text(json.dumps(facts), encoding="utf-8")
        self.root = tmp_path / "runs" / CAM
        self.run = self.root / "kit2_pass2"
        (self.run / "dat").mkdir(parents=True)
        names = ("00001_before.DAT", "00002_ntsc.DAT", "00003_pal.DAT")
        for name, video in zip(names, (0, 0, 1), strict=True):
            self.body(self.run / "dat" / name, video)
        (self.root / "downloads.jsonl").write_text("".join(json.dumps({"path": f"kit2_pass2/dat/{n}"}) + "\n"
                                                           for n in names), encoding="utf-8")
        self.proofs([{"path": ["Shooting", "Drive Mode"], "kind": "list", "index": 0, "label": "Single Shooting",
                      "dat": "00002_ntsc.DAT", "base": "00001_before.DAT", "applied": True, "changes": []}])
        self.target = definitions.path(CAM)

    @staticmethod
    def body(path: Path, video: int):
        """The sample as the made-up camera's download (its video system byte `video`), the live Drive Mode and its two
        copies (0x01d8, 0x01da, 0x01dc) all 0, as a camera that keeps copies writes them."""
        b = camset.block_of(A1)
        d = bytearray(b.with_text(SAMPLE.read_bytes(), "model", b"ILCE-7M5"))
        d[b.video_system[0].n] = video
        path.write_bytes(b.sealed(bytes(d)))
        cs = camset.read(path)
        path.write_bytes(camset.with_values(cs, {(0, r): b"\x00" for r in (0x01d8, 0x01da, 0x01dc)}))

    def tables(self, **tables):
        p = datafiles.hand_tables_file(CAM)
        p.write_text(json.dumps({"$schema": "../../schemas/hand-tables.schema.json", "camera": CAM, **tables}),
                     encoding="utf-8")
        return p

    def hand_evidence(self, **tables):
        doc = {"$schema": hand_evidence.SCHEMA_REF, "hand_format": hand_evidence.FORMAT, "camera": CAM, "tables": tables}
        hand_evidence.path(CAM).write_text(json.dumps(doc), encoding="utf-8")
        return doc

    def report(self, rows: list):
        (self.run / "report.json").write_text(json.dumps(rows), encoding="utf-8")

    def proofs(self, lines: list):
        (self.run / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")

    def accept(self, *entries):
        datafiles.accepted_file(CAM).write_text(json.dumps({"model": "ILCE-7M5", "firmware": "4.00", "accepted": [
            {"why": "made up", "date": "2026-11-13", **e} for e in entries]}), encoding="utf-8")

    def write(self, capsys, write: bool = True):
        """The plain pass (schema_update's generic_main) on the run: (the definition it gave, what it printed)."""
        import schema_update as S
        doc = S.generic_main(self.target, self.run, write)
        return doc, capsys.readouterr().out

    def written(self):
        """(the public definition as written, its evidence file's settings, the public file's text)."""
        text = self.target.read_text(encoding="utf-8")
        ev = json.loads(definitions.evidence_path(self.target).read_text(encoding="utf-8"))
        return json.loads(text), ev["settings"], text


def rec(proved, verdict="new", notes=(), **more):
    return {"verdict": verdict, "proved": proved, "notes": list(notes), "linear": None, **more}


ROWS = [
    {"row": "Shooting > Drive Mode", "options": 2, "notices": [],
     "records": {"global:0x01d8": rec({"Single Shooting": 0, "Cont. Shooting": 1},
                                      names={"Single Shooting": "two readers", "Cont. Shooting": "two readers"})}},
    {"row": "Shooting > Speed [Movie mode, as set]", "options": 3, "notices": [],
     "records": {"global:0x04d2": rec({"Low": 0, "Mid": 2, "High": 4})}},
    {"row": "Shooting > Flag", "options": 2, "notices": [], "records": {"global:0x0050": rec({"A": 0, "B": 1})}},
    {"row": "Shooting > Fluor", "options": 2, "notices": [],
     "records": {"global:0x0053": rec({"Fluor.: Warm White": 2, "Fluor.: Cool White": 3})}},
]
# a made-up camera's tables, one entry or more of each table the plain pass reads
TABLES = {
    "RECORD_FIXES": {"global:0x04d2": {"name": "Speed of the thing", "note": "What the speed does."}},
    "NEW_RECORDS": {
        "global:0x0051": {"like": "global:0x01d8", "name": "A found flag", "values": [[0, "Off"], [1, "On"]], "note": ""},
        "global:0x0052": {"like": "global:0x01d8", "name": "A working value", "values": [],
                          "note": "A value the camera keeps while it works."},
        "global:0x01da": {"like": "global:0x01d8", "name": "Drive Mode (stills)",
                          "values": [[0, "Single Shooting"], [1, "Continuous"]], "note": "The stills copy."},
        "global:0x01dc": {"like": "global:0x01d8", "name": "Drive Mode (movie)",
                          "values": [[0, "Single Shooting"], [1, "Continuous"]], "note": "The movie copy."}},
    "NEW_LIKE": {"global:0x0053": {"like": "global:0x01d8", "name": "Drive Mode (third)"}},
    "FRAME_PROOFS": {"global:0x0051": {"note": "What the flag holds.", "values": [[0, "Off"], [1, "On"]]}},
    "CAROUSEL": [["global:0x04d2", 2, "Middle"]],
    "VALUE_FIXES": [["global:0x01d8", 1, "Continuous"]],
    "PP7_VALUES": [["global:0x04d2", 6, "Turbo"]],
    "NOT_OFFERED": [{"key": "global:0x04d2", "values": [6], "walk": "^Shooting > Speed\\b", "why": "Not on its list.",
                     "menu": "Shooting > Speed"}],
    "VIDEO_SYSTEM_VALUES": {"global:0x04d2": {"NTSC": [0], "PAL": [4]}},
    "COPIES": {"global:0x01d8": ["global:0x01da", "global:0x01dc"]},
    "COPY_MODES": [["Stills"], ["Movie", "S&Q", "Time-lapse"]],
    "UNPROVED": {"global:0x0052": ["state", None, "The camera keeps it while it works."]},
    "CONTEXT_WORDS": {", as set\\]": "]"},
}
# its mapper's hand evidence: a hand proof, a note's evidence, a reason's day, what shows a mark
EVIDENCE = {
    "FRAME_PROOFS": {"global:0x0051": {"proved": [0, 1], "run": "kit2_hand", "date": "2026-11-12",
                                       "menu": "Setup > Hand row", "note+": "(seen on the camera, 2026-11-12)"}},
    "RECORD_FIXES": {"global:0x04d2": {"note+": "(runs/kit2_hand)"}},
    "UNPROVED": {"global:0x0052": {"1": "2026-11-12"}},
    "NOT_OFFERED": {"0": {"$key": "global:0x04d2", "evidence": "the row walked whole in Movie mode, 2026-11-12"}}}


def test_every_table_the_kit_knows_is_read_by_the_plain_pass_or_refused_there():
    """Each table writer/hand_tables.py knows is one the plain pass reads, a prover's, or one it refuses (only the
    ILCE-1M2's pass reads it, or no pass does): none is left for a mapper to fill in and believe it took effect."""
    groups = [set(hand_facts.PLAIN), set(hand_facts.PROVERS), set(hand_facts.A1_PASS_ONLY), set(hand_facts.NO_READER)]
    assert sum(map(len, groups)) == len(set().union(*groups)) and set().union(*groups) == set(hand_tables.TABLES)


def test_each_table_the_plain_pass_reads_takes_effect_and_its_evidence_stays_private(tmp_path, monkeypatch, capsys):
    """A made-up camera with one entry or more of each table the plain pass reads, and its hand evidence: a record fix
    renames a setting and puts its note, the note's evidence going to the evidence file; records found by hand are
    added (laid out like their sibling, from the run's newest download) and a sibling's layout gives a record NEW_LIKE
    names its name and its values; a value fix and a carousel's option name a proved value against the reading, and a
    value the files hold outside the lists is added ("hand table" each); a hand proof proves its record, its run, day and
    menu row in the evidence only; a reason why a record cannot be proved is written, its day private; a not-offered
    mark holds while the walk never wrote the value, what shows it private; a video system's values where no row was
    walked under both; the copies written once the downloads bear them out, each copy with its modes; a context the
    runs reworded is the definition's in its new words. The public file names no run, day or hand proof, and check_public's
    rule finds nothing in it; the hand evidence file is in its JSON Schema's shape."""
    import jsonschema
    c = Cam(tmp_path, monkeypatch)
    c.tables(**TABLES)
    evidence = c.hand_evidence(**EVIDENCE)
    c.report(ROWS)
    doc, said = c.write(capsys)
    assert "wrote" in said and "not one to one" not in said
    pub, ev, text = c.written()
    by = {s["key"]: s for s in pub["settings"]}
    drive, speed = by["global:0x01d8"], by["global:0x04d2"]
    # VALUE_FIXES and CAROUSEL: the table's names, a hand table's source (in the evidence)
    assert drive["values"] == [[0, "Single Shooting"], [1, "Continuous"]]
    assert ev["global:0x01d8"]["proved"]["names"] == {"0": "two readers", "1": "hand table"}
    assert [2, "Middle"] in speed["values"] and ev["global:0x04d2"]["proved"]["names"]["2"] == "hand table"
    # RECORD_FIXES, its note's evidence apart; PP7_VALUES; NOT_OFFERED, its evidence apart; VIDEO_SYSTEM_VALUES
    assert speed["name"] == "Speed of the thing" and speed["note"] == "What the speed does."
    assert ev["global:0x04d2"]["note_evidence"] == "runs/kit2_hand"
    # PP7_VALUES: listed, but named, not proved (no proof covers it, no held mark): "counted", not offered outside
    # Expert mode (not among the public proof's values)
    assert [6, "Turbo"] in speed["values"] and ev["global:0x04d2"]["proved"]["names"]["6"] == "counted"
    assert 6 not in speed["proved"]["values"]
    assert speed["not_offered"] == [{"value": 6, "label": "Turbo", "why": "Not on its list.", "menu": "Shooting > Speed"}]
    assert ev["global:0x04d2"]["not_offered"] == [{"value": 6, "evidence": EVIDENCE["NOT_OFFERED"]["0"]["evidence"]}]
    assert speed["video_system_values"] == {"NTSC": [0], "PAL": [4]}
    # CONTEXT_WORDS: the proof's row in its new words (the row is evidence)
    assert ev["global:0x04d2"]["proved"]["menu"] == ["Shooting > Speed [Movie mode]"]
    # NEW_RECORDS and FRAME_PROOFS: the record found by hand, its hand proof's run, day and row in the evidence only
    flag = by["global:0x0051"]
    assert (flag["name"], flag["values"], flag["note"]) == ("A found flag", [[0, "Off"], [1, "On"]], "What the flag holds.")
    assert flag["proved"] == {"values": [0, 1]} and ev["global:0x0051"]["source"] == "Derived"
    assert {k: ev["global:0x0051"]["proved"][k] for k in ("run", "date", "menu", "values")} == \
        {"run": "kit2_hand", "date": "2026-11-12", "menu": ["Setup > Hand row"], "values": [0, 1]}
    assert ev["global:0x0051"]["proved"]["names"] == {"0": "hand table", "1": "hand table"}
    assert ev["global:0x0051"]["note_evidence"] == "seen on the camera, 2026-11-12"
    # UNPROVED: the kind and the why public, the day private
    work = by["global:0x0052"]
    assert work["unproved_reason"] == {"kind": "state", "why": "The camera keeps it while it works."}
    assert ev["global:0x0052"]["unproved_reason"] == {"date": "2026-11-12"} and "proved" not in work
    # NEW_LIKE: the sibling's layout and name, its values after the colon, the start value's gap filled from the sibling
    third = by["global:0x0053"]
    assert third["name"] == "Drive Mode (third)" and third["values"] == \
        [[0, "Single Shooting"], [1, "Continuous"], [2, "Warm White"], [3, "Cool White"]]
    assert third["note"] == "" and "laid out like global:0x01d8" in ev["global:0x0053"]["note_evidence"]
    assert ev["global:0x0053"]["proved"]["names"]["0"] == "derived"
    # COPIES and COPY_MODES
    assert drive["copies"] == ["global:0x01da", "global:0x01dc"]
    assert (by["global:0x01da"]["copy_of"], by["global:0x01da"]["copy_for"]) == ("global:0x01d8", ["Stills"])
    assert by["global:0x01dc"]["copy_for"] == ["Movie", "S&Q", "Time-lapse"]
    # decision 16: nothing of how anything was proved in the public file
    assert definitions.evidence_in_public(pub) == [] and not EVIDENCE_WORDS.search(text)
    assert not datafiles.evidence_in_public(datafiles.hand_tables_file(CAM))
    schema = json.loads((ROOT / "schemas" / "hand-evidence.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(evidence)
    tables = json.loads(datafiles.hand_tables_file(CAM).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "hand-tables.schema.json").read_text(
        encoding="utf-8"))).validate(tables)
    # a second run gives the same file, and says nothing changed
    _, said = c.write(capsys)
    assert c.target.read_text(encoding="utf-8") == text
    assert "settings proved; 0 labels changed or added" in said and not re.search(r"^  global:\S+ .*->", said, re.M)


def test_a_kept_label_keeps_the_definitions_names_and_its_conflict_goes_to_the_gate(tmp_path, monkeypatch, capsys):
    """KEEP_LABELS: a record proved by a row whose options do not name its values keeps the names the definition holds
    when a later report reads others, its proved values named "hand table", and the conflict the report notes is an
    open question for the gate (--write refuses until it is accepted), as in the ILCE-1M2's pass; pass2_report's hand
    rules name the record for that camera (a value carried over in it is left to the rule). A value fix names a value
    the definition lists that no row of the run names (here the kept record's), as it does one a row names."""
    import pass2_report as R
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS[2:3])
    c.write(capsys)
    c.tables(KEEP_LABELS=["global:0x0050"], VALUE_FIXES=[["global:0x0050", 0, "Ay"]])
    c.report([{**ROWS[2], "records": {"global:0x0050": rec({"A": 0, "Bee": 1}, "conflict", [
        {"value": 1, "camera": "Bee", "schema": "B", "kind": "conflict"}])}}])
    with pytest.raises(SystemExit, match="refused to write"):
        c.write(capsys)
    assert "1 conflict" in capsys.readouterr().out
    c.accept({"kind": "conflict", "key": "global:0x0050", "value": 1})
    doc, said = c.write(capsys)
    pub, ev, _ = c.written()
    flag = next(s for s in pub["settings"] if s["key"] == "global:0x0050")
    assert flag["values"] == [[0, "Ay"], [1, "B"]] and ev["global:0x0050"]["proved"]["names"] == {"0": "hand table",
                                                                                                     "1": "hand table"}
    assert R.hand_rules(("ILCE-7M5", "4.00")) == {"global:0x0050"} and R.hand_rules(None) == set()
    monkeypatch.setattr(definitions, "DATA", ROOT / "data")            # the a1 II's own tables, as shipped
    a1 = R.hand_rules(("ILCE-1M2", "4.00"))
    own = {k.split("[")[0] for k in set(R.WRITTEN_BY) | R.DISP_MODES}
    assert {k.split("[")[0] for k in hand_tables.load(A1, evidence=False).KEEP_LABELS} | own == a1
    assert R.hand_rules(("ILCE-1M2", "5.00")) == own, "another firmware's own tables (none), never the firmware 4.00's"


def test_write_stops_without_the_hand_evidence_the_tables_need(tmp_path, monkeypatch, capsys):
    """Any camera, as the ILCE-1M2: tables holding a hand proof's entry, a reason or a not-offered mark, and no hand
    evidence file here: --write stops before the definition is read, in plain words naming the file and how to say no
    entry was proved by hand; a look (no --write) goes on. Tables needing no evidence (a record fix) write without the
    file, and the file holding no evidence lets the write go on."""
    import schema_update as S
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS[:1])
    for table, entry in (("FRAME_PROOFS", {"global:0x01d8": {"note": "What it holds."}}),
                         ("UNPROVED", {"global:0x01d8": ["state", None, "Why."]}),
                         ("NOT_OFFERED", [{"key": "global:0x01d8", "values": [5], "walk": "^Shooting", "why": "W.",
                                           "menu": "Drive Mode"}])):
        c.tables(**{table: entry})
        with monkeypatch.context() as m:
            m.setattr(S.definitions, "load", lambda *a, **k: pytest.fail("read the definition"))
            m.setattr(S, "seed", lambda *a, **k: pytest.fail("started a definition"))
            with pytest.raises(SystemExit) as got:
                c.write(capsys)
        words = str(got.value.code)
        assert "nothing written" in words and f"{CAM}.hand.json" in words and table in words, words
        assert "would drop those proofs" in words and '"tables": {}' in words
        assert not c.target.exists()
        c.write(capsys, write=False)                       # a look needs no evidence
    c.tables(RECORD_FIXES={"global:0x01d8": {"name": "Drive"}})
    c.write(capsys)
    assert json.loads(c.target.read_text(encoding="utf-8"))["settings"][0]["name"] == "Drive"
    c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "What it holds."}})
    c.hand_evidence()
    c.write(capsys)
    assert next(s for s in json.loads(c.target.read_text(encoding="utf-8"))["settings"]
                if s["key"] == "global:0x01d8")["note"] == "What it holds."


def test_a_hand_proof_without_its_run_day_or_row_is_refused(tmp_path, monkeypatch, capsys):
    """A hand proof the evidence gives (its values) names its run, day and menu row there: one without them stops the
    plain pass before anything is read, naming the record and what it lacks (the ILCE-1M2's pass has defaults of its
    own, which no other camera's runs share)."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS[:1])
    c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "What it holds."}})
    c.hand_evidence(FRAME_PROOFS={"global:0x01d8": {"proved": [0], "date": "2026-11-12"}})
    with pytest.raises(SystemExit) as got:
        c.write(capsys, write=False)
    assert "global:0x01d8 (no run, menu)" in str(got.value.code) and "nothing done" in str(got.value.code)


SHAPED = {"NEW_CHECK_NAMES": {"global:0x0001": "A"}, "LATE_COPY": {"0x0001": " A."},
          "EV_DOWN_FROM_20": ["global:0x0001"], "HOLD_TABLES": {"global:0x0001": {"live": "global:0x0002", "mirror": None}},
          "HOLD_BRACKET_COPIES": {"global:0x0001": "global:0x0002"}, "ISO_TABLE": "global:0x0001",
          "LABEL_FIXES": {"Slip": "Mend"}, "GROUP_NAMES": {"Cut...": "Full"}, "MY_MENU_ROW": "My Menu > Add Item",
          "MY_MENU_EMPTY": {"label": "(empty)", "line": "Empty {code}."}, "SHOOT_MODE_RECORDS": {"Stills": ["global:0x0001"]},
          "ORIENTED": "camera (level)", "FRAME_STEPS": [["Standard", "Spot M", 30, 20]]}


@pytest.mark.parametrize("tables, words", [
    *[({name: value}, name) for name, value in SHAPED.items()],
    ({"FILTER_FLAGS": {"global:0x0001": {"like": "global:0x0002", "name": "A", "values": [], "note": ""}}},
     "FILTER_FLAGS' entry 'global:0x0001': written only through NEW_RECORDS'"),
    ({"NEW_WHOLE_LABELS": ["global:0x0001"]}, "read only for a NEW_LIKE record"),
    ({"COPY_MODES": [["Stills"], ["Movie"]]}, "COPY_MODES: read only with COPIES' families"),
    ({"COPIES": {"global:0x0001": ["global:0x0002", "global:0x0003"]}, "COPY_MODES_UNKNOWN": ["global:0x0009"]},
     "COPY_MODES_UNKNOWN's 'global:0x0009'"),
    ({"NEW_RECORDS": {"global:0x0001[2]": {"like": "global:0x0002", "name": "A", "values": [], "note": ""}}},
     "NEW_RECORDS' 'global:0x0001[2]': a record found by hand is a whole record"),
    ({"NEW_LIKE": {"set:0x0001": {"like": "set:0x0002", "name": "A"}}}, "NEW_LIKE's 'set:0x0001'"),
], ids=lambda x: x if isinstance(x, str) else None)
def test_a_table_the_plain_pass_does_not_read_is_refused_in_plain_words(tmp_path, monkeypatch, capsys, tables, words):
    """A table only the ILCE-1M2's pass reads (or no pass), or an entry no table the plain pass reads would use, stops
    it before anything is read or written, in plain words naming the file, the table, that it would change nothing,
    and the tables the plain pass reads: a mapper who fills one in must not believe it took effect."""
    import schema_update as S
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS[:1])
    p = c.tables(**tables)
    monkeypatch.setattr(S, "seed", lambda *a, **k: pytest.fail("started a definition"))
    with pytest.raises(SystemExit) as got:
        c.write(capsys)
    said = str(got.value.code)
    assert words in said and p.name in said and "nothing done" in said and "would change nothing" in said, said
    assert "the plain pass reads RECORD_FIXES" in said and not c.target.exists()
    if next(iter(tables)) in hand_facts.A1_PASS_ONLY:
        assert "read only by the ILCE-1M2's own pass so far" in said


def test_no_hand_tables_and_empty_tables_give_the_plain_pass_as_before(tmp_path, monkeypatch, capsys):
    """A camera with no hand tables file and the same camera with a file of every table, each empty: the same
    definition, evidence and printed words, byte for byte (the plain pass before it read any tables; the comparison
    with that kit itself was made once by hand, its scenario in the round's notes)."""
    out = []
    for name, tables in (("none", None), ("empty", {n: [] if k in ("set", "frozenset", "values", "not_offered", "tuple",
                                                                    "rows", "steps") else {} for n, k in
                                                    hand_tables.TABLES.items() if k not in ("text", "pattern",
                                                                                            "my_menu_empty")})):
        c = Cam(tmp_path / name, monkeypatch)
        if tables is not None:
            c.tables(**tables)
            assert vars(hand_tables.load(CAM)) == {**hand_tables.empty(), "HAND_EVIDENCE": None}
        c.report(ROWS)
        c.write(capsys)
        said = c.write(capsys)[1]
        pub, ev, text = c.written()
        out.append((text, json.dumps(ev), said.replace(str(tmp_path / name), "<tmp>")
                    .replace((tmp_path / name).as_posix(), "<tmp>")))      # Windows prints some paths with "/"
    assert out[0] == out[1]


# ---------------------------------------------------------------- the review of the plain pass (2026-11-13)

# canaries: a kit2_ run, a run of another name, an ISO day, a day in words, a download's and a frame's names, a person,
# and words of each evidence field; none may reach a public file, however the evidence words them
CANARIES = ("kit2_cnryrun", "zebrarun", "2026-01-02", "Jan 2nd", "00777_cnry.DAT", "00778_cnry.png", "CNRYPERSON",
            "CNRYMENU", "CNRYALLOW", "CNRYNOTE", "CNRYVSV", "CNRYNOFF")


def canary_tables() -> dict:
    """TABLES and an entry of each other table a piece of evidence lands on (a FILTER_FLAGS entry NEW_RECORDS takes in,
    a FRAME_PROOFS note on the working value), with KEEP_LABELS and NEW_WHOLE_LABELS, so every table the plain pass
    reads is there."""
    t = json.loads(json.dumps(TABLES))
    t["KEEP_LABELS"], t["NEW_WHOLE_LABELS"] = ["global:0x0050"], ["global:0x0053"]
    t["FILTER_FLAGS"] = {"global:0x0068": {"like": "global:0x01d8", "name": "A filter flag",
                                           "values": [[0, "Off"], [1, "On"]], "note": "A flag."}}
    t["NEW_RECORDS"]["global:0x0068"] = {"$ref": "#/FILTER_FLAGS/global:0x0068"}
    t["FRAME_PROOFS"]["global:0x0052"] = {"note": "Working value note."}
    return t


WELL_FORMED = {     # every evidence field, each with canaries beside a run or a day, as the docs show evidence
    "FRAME_PROOFS": {
        "global:0x0051": {"proved": [0, 1], "run": "kit2_cnryrun zebrarun", "date": "2026-01-02 Jan 2nd",
                          "menu": ["CNRYMENU > Hand row 00778_cnry.png"],
                          "note+": "(CNRYNOTE seen by CNRYPERSON in zebrarun, 00777_cnry.DAT, 2026-01-02)",
                          "allowance": "the owner allowed CNRYALLOW remotely, 2026-01-02"},
        "global:0x0052": {"note+": "(runs/kit2_cnryrun CNRYPERSON)"}},
    "RECORD_FIXES": {"global:0x04d2": {"note+": "(runs/kit2_cnryrun, CNRYNOTE, 00777_cnry.DAT)"}},
    "NEW_RECORDS": {"global:0x0051": {"note+": "(CNRYNOTE by CNRYPERSON 2026-01-02)"}},
    "FILTER_FLAGS": {"global:0x0068": {"note+": "(CNRYNOTE zebrarun 2026-01-02)"}},
    "UNPROVED": {"global:0x0052": {"1": "2026-01-02 CNRYPERSON Jan 2nd"}},
    "NOT_OFFERED": {"0": {"$key": "global:0x04d2", "evidence": "CNRYNOFF CNRYPERSON walked in zebrarun, 2026-01-02",
                          "files": ["00777_cnry.DAT"]}},
    "VIDEO_SYSTEM_VALUES": {"global:0x04d2": {"evidence": "CNRYVSV CNRYPERSON saw it, 2026-01-02, 00778_cnry.png"}}}
BARE = {            # the same fields worded with no run folder and no ISO day, as a mapper might write them
    "FRAME_PROOFS": {"global:0x0051": {"proved": [0, 1], "run": "zebrarun", "date": "Jan 2nd", "menu": "CNRYMENU > Row",
                                       "note+": "(CNRYNOTE seen by CNRYPERSON in zebrarun)",
                                       "allowance": "CNRYPERSON allowed CNRYALLOW remotely"}},
    "RECORD_FIXES": {"global:0x04d2": {"note+": "(CNRYPERSON; 2026-01-02)"}},
    "NEW_RECORDS": {"global:0x0051": {"note+": "seen by CNRYPERSON"}},
    "UNPROVED": {"global:0x0052": {"1": "Jan 2nd"}},
    "NOT_OFFERED": {"0": {"$key": "global:0x04d2", "evidence": "CNRYNOFF CNRYPERSON"}}}


def public_texts(c) -> dict:
    """{name: text} of every public file the plain pass wrote: the definition and the camera's data folder (the test
    folder's private places beside it left out)."""
    out = {"definition": c.target.read_text(encoding="utf-8")}
    out.update({p.name: p.read_text(encoding="utf-8") for p in sorted((c.data / CAM).glob("*.json"))
                if not p.name.endswith(".evidence.json")})
    return out


@pytest.mark.parametrize("evidence", [WELL_FORMED, BARE], ids=["worded as the docs show", "bare"])
def test_no_piece_of_hand_evidence_reaches_a_public_file(tmp_path, monkeypatch, capsys, evidence):
    """Decision 16, structurally, for every evidence field (the review's canaries, 2026-11-13): the plain pass writes a
    note's evidence ("note+") and the owner's word ("allowance") into note_evidence, a hand proof's run, day and rows
    into its proof, a reason's day and a mark's evidence where the definition keeps them private, never into a public
    field, whatever the words (with a run folder or an ISO day, or with neither, which a rule recognising evidence
    would miss): no canary in the public definition or the data folder, each public note the table's word for word,
    and a second run gives the same files."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(**canary_tables())
    c.hand_evidence(**evidence)
    c.report(ROWS)
    c.write(capsys)
    texts = public_texts(c)
    assert not [(name, w) for name, text in texts.items() for w in CANARIES if w in text]
    ev_text = definitions.evidence_path(c.target).read_text(encoding="utf-8")
    assert "CNRYPERSON" in ev_text and "CNRYNOTE" in ev_text            # kept, in the private evidence file
    by = {s["key"]: s for s in json.loads(texts["definition"])["settings"]}
    assert (by["global:0x0051"]["note"], by["global:0x04d2"]["note"]) == ("What the flag holds.", "What the speed does.")
    assert by["global:0x0068"]["note"] == "A flag." and by["global:0x0052"]["note"] == "Working value note."
    assert definitions.evidence_in_public(json.loads(texts["definition"]), texts["definition"]) == []
    # a mark's downloads ("files") serve the check of a held value only: no mark carries them, public or private
    marks = [m for s in json.loads(texts["definition"])["settings"] for m in s.get("not_offered") or []]
    marks += [m for s in json.loads(ev_text)["settings"].values() for m in s.get("not_offered") or []]
    assert marks and not [m for m in marks if "files" in m]
    _, said = c.write(capsys)
    assert public_texts(c) == texts and definitions.evidence_path(c.target).read_text(encoding="utf-8") == ev_text
    assert "0 labels changed or added" in said and not re.search(r"^  global:\S+ .*->", said, re.M)
    # the parts from data/ alone, as --from-data --write writes them (refresh_from_data, for this one definition: the
    # test keeps its evidence beside it, where --from-data would take it for a definition): nothing private comes back
    from writer.fromdata import from_data
    definitions.write(c.target, from_data(definitions.load(c.target)))
    assert not [(name, w) for name, text in public_texts(c).items() for w in CANARIES if w in text]
    assert public_texts(c) == texts


@pytest.mark.parametrize("evidence, words", [
    ({"RECORD_FIXES": {"global:0x04d2": {"group": "CNRYGROUP"}}}, "'RECORD_FIXES' 'global:0x04d2' holds 'group'"),
    ({"FRAME_PROOFS": {"global:0x0052": {"values": [[0, "CNRYLABEL"]]}}}, "'FRAME_PROOFS' 'global:0x0052' holds 'values'"),
    ({"NOT_OFFERED": {"0": {"$key": "global:0x04d2", "held": True}}}, "'NOT_OFFERED' '0' holds 'held'"),
    ({"NEW_RECORDS": {"global:0x0052": {"tab": "CNRYTAB"}}}, "'NEW_RECORDS' 'global:0x0052' holds 'tab'"),
    ({"KEEP_LABELS": {"global:0x0050": {}}}, "'tables' holds 'KEEP_LABELS'"),
    ({"NOT_OFFERED": {"0": {"evidence": "CNRYNOFF"}}}, "NOT_OFFERED [0]: no \"$key\""),
    ({"NOT_OFFERED": {"0": {"$key": "global:0x01d8", "evidence": "CNRYNOFF"}}}, "NOT_OFFERED [0]: its \"$key\" is not"),
    ({"FRAME_PROOFS": {"global:0x0099": {"note+": "(CNRYNOTE)"}}}, "FRAME_PROOFS 'global:0x0099': the tables have no"),
    ({"RECORD_FIXES": {"global:0x0050": {"note+": "(CNRYNOTE)"}}}, "RECORD_FIXES 'global:0x0050': \"note+\" for an entry"),
])
def test_hand_evidence_that_is_not_evidence_is_refused(tmp_path, monkeypatch, capsys, evidence, words):
    """The plain pass takes from the hand evidence only what its JSON Schema allows, evidence fields table by table, so
    nothing in the private file sets a public fact (a group, a tab, value names, a held mark) that a reviewer could not
    rebuild from data/; and every part names an entry the public tables hold (a part for an entry taken out, or a
    NOT_OFFERED part without its "$key" or with another mark's, would land on the wrong entry). Refused before anything
    is read or written, naming the file, the table, the key and the field, never a value it holds."""
    c = Cam(tmp_path, monkeypatch)
    t = canary_tables()
    t["RECORD_FIXES"]["global:0x0050"] = {"name": "A flag, renamed"}
    c.tables(**t)
    c.hand_evidence(**evidence)
    c.report(ROWS)
    with pytest.raises(hand_evidence.Refused) as got:
        c.write(capsys, write=False)
    said = str(got.value)
    assert words in said and f"{CAM}.hand.json" in said and "Nothing was done" in said, said
    assert not [w for w in ("CNRYGROUP", "CNRYLABEL", "CNRYTAB", "CNRYNOFF", "CNRYNOTE") if w in said]
    assert not c.target.exists()


def test_a_value_a_hand_table_names_is_named_not_proved(tmp_path, monkeypatch, capsys):
    """A value a hand table names is named, not proved: without a proof (the report's, or a hand proof with its
    evidence) or a NOT_OFFERED mark that the camera holds it, its name's source is "counted", so the editor offers it
    in Expert mode only (it is not among the public proof's values): a FRAME_PROOFS entry's values the report does not
    prove, NEW_RECORDS' values beyond the hand proof's, a PP7_VALUES value; a held mark makes one offered ("hand table").
    A value fix for a value no setting lists is said, not applied."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "Drive.", "values": [[0, "Single"], [1, "Cont"], [2, "Self"],
                                                                          [3, "Bracket"]]},
                           "global:0x0051": {"note": "Flag."}},
             PP7_VALUES=[["global:0x04d2", 9, "Ghost"], ["global:0x04d2", 8, "Held one"]],
             NOT_OFFERED=[{"key": "global:0x04d2", "values": [8], "walk": "^Shooting > Speed\\b", "why": "W.",
                           "menu": "Speed", "held": True}],
             NEW_RECORDS={"global:0x0051": {"like": "global:0x01d8", "name": "Flag",
                                            "values": [[0, "Off"], [1, "On"], [2, "Turbo"]], "note": ""}},
             VALUE_FIXES=[["global:0x0050", 7, "Seven"]])
    c.hand_evidence(FRAME_PROOFS={"global:0x0051": {"proved": [0], "run": "kit2_x", "date": "2026-11-12", "menu": "M"}},
                    NOT_OFFERED={"0": {"$key": "global:0x04d2", "evidence": "walked whole, 2026-11-12"}})
    c.report(ROWS)
    _, said = c.write(capsys)
    pub, ev, _ = c.written()
    by = {s["key"]: s for s in pub["settings"]}

    def names(k):
        return ev[k]["proved"]["names"]
    assert by["global:0x01d8"]["proved"]["values"] == [0, 1]
    assert (names("global:0x01d8")["2"], names("global:0x01d8")["3"]) == ("counted", "counted")
    assert by["global:0x0051"]["proved"]["values"] == [0]
    assert names("global:0x0051") == {"0": "hand table", "1": "counted", "2": "counted"}
    assert 9 not in by["global:0x04d2"]["proved"]["values"] and names("global:0x04d2")["9"] == "counted"
    assert 8 in by["global:0x04d2"]["proved"]["values"] and names("global:0x04d2")["8"] == "hand table"
    assert "value fix  global:0x0050 7: not applied, the setting lists no such value" in said


def test_a_kept_label_names_a_value_the_definition_does_not_name_yet(tmp_path, monkeypatch, capsys):
    """KEEP_LABELS on a camera's first write (the definition names none of the record's values yet): each proved value
    takes the camera's label, its readers' source, so no proved value is left without a name; the names it then holds
    stay on a later write that reads others."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(KEEP_LABELS=["global:0x0050"])
    c.report(ROWS)
    c.write(capsys)
    pub, ev, _ = c.written()
    flag = next(s for s in pub["settings"] if s["key"] == "global:0x0050")
    assert flag["values"] == [[0, "A"], [1, "B"]]
    assert ev["global:0x0050"]["proved"]["names"] == {"0": "one reader", "1": "one reader"}
    c.report([ROWS[0], {**ROWS[2], "records": {"global:0x0050": rec({"A": 0, "Bee": 1})}}, ROWS[1], ROWS[3]])
    c.write(capsys)
    flag = next(s for s in c.written()[0]["settings"] if s["key"] == "global:0x0050")
    assert flag["values"] == [[0, "A"], [1, "B"]]


def test_a_new_like_record_is_the_same_whatever_the_reports_order_and_a_later_run_lays_it_out(tmp_path, monkeypatch,
                                                                                               capsys):
    """NEW_LIKE is laid out once every row is read: the report with the record's row before its sibling's or after it
    gives the same definition; a run whose report lacks the sibling names the record by its menu row (said), and a
    later run that has it lays the record out like its sibling."""
    like = {"NEW_LIKE": {"global:0x0053": {"like": "global:0x01d8", "name": "Drive Mode (third)"}}}
    texts = []
    for name, rows in (("after", [ROWS[0], ROWS[3]]), ("before", [ROWS[3], ROWS[0]])):
        c = Cam(tmp_path / name, monkeypatch)
        c.tables(**like)
        c.report(rows)
        c.write(capsys)
        texts.append(c.target.read_text(encoding="utf-8"))
    assert texts[0] == texts[1]
    c = Cam(tmp_path / "later", monkeypatch)
    c.tables(**like)
    c.report([ROWS[3]])
    _, said = c.write(capsys)
    assert "new like  global:0x0053: the definition has no global:0x01d8 to lay it out like yet; named by its menu row" \
        in said
    third = next(s for s in c.written()[0]["settings"] if s["key"] == "global:0x0053")
    assert third["name"] == "Fluor" and third["values"] == [[2, "Warm White"], [3, "Cool White"]]
    c.report([ROWS[3], ROWS[0]])
    _, said = c.write(capsys)
    assert "new like  global:0x0053: laid out like global:0x01d8 now" in said
    settings = {s["key"]: s for s in c.written()[0]["settings"]}
    third, drive = settings["global:0x0053"], settings["global:0x01d8"]
    assert third["name"] == "Drive Mode (third)"
    assert (third["tab"], third["group"], third["order"]) == (drive["tab"], drive["group"], drive["order"])
    assert third["values"] == [[0, "Single Shooting"], [1, "Cont. Shooting"], [2, "Warm White"], [3, "Cool White"]]
    c.write(capsys)
    assert next(s for s in c.written()[0]["settings"] if s["key"] == "global:0x0053") == third


def test_stale_hand_evidence_is_refused_in_plain_words_in_either_pass(tmp_path, monkeypatch, capsys):
    """Evidence for an entry the tables no longer hold: the plain pass, through schema_update.main, stops with the file,
    the table, the key and what to do, no traceback; the ILCE-1M2's way of reading (put_back) stops so too (Refused, a
    ValueError still for the callers that catch one), naming the read-only check that lists every such part."""
    import schema_update as S
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.tables(RECORD_FIXES={"global:0x04d2": {"name": "Speed"}})
    c.hand_evidence(FRAME_PROOFS={"global:0x0051": {"note+": "(seen, 2026-11-12)"}})
    monkeypatch.setattr(S, "RUN_ROOT", c.root)
    monkeypatch.setattr(S, "RUN", c.run)
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    with pytest.raises(hand_evidence.Refused) as got:
        S.main()
    assert "FRAME_PROOFS 'global:0x0051': the tables have no such entry" in str(got.value)
    with pytest.raises(hand_evidence.Refused) as got:
        hand_tables.load(CAM)
    words = str(got.value)
    assert "no entry 'global:0x0051'" in words and f"kit/writer/hand_evidence.py --check --camera {CAM}" in words
    assert isinstance(got.value, ValueError) and "Nothing was done" in words


def test_entries_that_cannot_take_effect_are_said(tmp_path, monkeypatch, capsys):
    """Each entry for a setting the definition lacks (VALUE_FIXES, PP7_VALUES, KEEP_LABELS, UNPROVED,
    VIDEO_SYSTEM_VALUES, RECORD_FIXES) and a CONTEXT_WORDS pattern that matches no row is said, "not applied", as the
    pass goes; the definition is written all the same."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(VALUE_FIXES=[["global:0x0999", 1, "X"]], PP7_VALUES=[["global:0x0999", 2, "Y"]],
             KEEP_LABELS=["global:0x0999"], UNPROVED={"global:0x0999": ["state", None, "W."]},
             VIDEO_SYSTEM_VALUES={"global:0x0999": {"NTSC": [1], "PAL": []}}, RECORD_FIXES={"global:0x0999": {"name": "Z"}},
             CONTEXT_WORDS={"never matches": "x"})
    c.hand_evidence()
    c.report(ROWS)
    _, said = c.write(capsys)
    for line in ("value fix  global:0x0999 1: not applied, the definition has no such setting yet",
                 "extra value  global:0x0999 2: the definition has no such setting yet, not applied",
                 "kept label  global:0x0999: the definition has no such setting yet, not applied",
                 "unproved  global:0x0999: the definition has no such setting yet, not applied",
                 "video system  global:0x0999: the definition has no such setting yet, not applied",
                 "record fix  global:0x0999 'Z': the definition has no such setting yet, not applied",
                 "context words  'never matches': matches no row of the report or the definition, not applied"):
        assert line in said, line
    assert "wrote" in said


def test_a_hand_proof_in_the_wrong_file_or_without_its_run_names_the_file(tmp_path, monkeypatch, capsys):
    """A hand proof's evidence written into the public tables file is refused there, naming that file and the field
    (its JSON Schema keeps evidence out of it); one in the hand evidence without its run, day or menu row is refused
    naming the hand evidence file."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    p = c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "N.", "proved": [0]}})
    with pytest.raises(hand_tables.Refused) as got:
        c.write(capsys, write=False)
    assert p.name in str(got.value) and "'FRAME_PROOFS' 'global:0x01d8' holds 'proved'" in str(got.value)
    c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "N."}})
    c.hand_evidence(FRAME_PROOFS={"global:0x01d8": {"proved": [0], "date": "2026-11-12"}})
    with pytest.raises(SystemExit) as got:
        c.write(capsys, write=False)
    assert f"The hand evidence, {paths.shown(hand_evidence.path(CAM))}" in str(got.value.code)
    assert "global:0x01d8 (no run, menu)" in str(got.value.code)


def test_a_look_without_the_hand_evidence_says_what_write_would_stop_on(tmp_path, monkeypatch, capsys):
    """A dry run whose tables need the hand evidence, without that file, goes on and says, before anything else, what
    --write would stop on."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(FRAME_PROOFS={"global:0x01d8": {"note": "N."}})
    c.report(ROWS)
    _, said = c.write(capsys, write=False)
    assert said.startswith("note, before --write: schema_update: nothing written.") and f"{CAM}.hand.json" in said


def test_what_the_tables_no_longer_name_leaves_the_definition(tmp_path, monkeypatch, capsys):
    """Retraction: a hand proof whose evidence is gone is taken out of the definition, and a record NEW_RECORDS added
    that the table no longer holds and no row proves is taken out, each said; a mapper never edits the definition by
    hand to take a wrong hand fact back."""
    c = Cam(tmp_path, monkeypatch)
    found = {"global:0x0051": {"like": "global:0x01d8", "name": "Flag", "values": [[0, "Off"], [1, "On"]], "note": ""}}
    c.tables(NEW_RECORDS=found, FRAME_PROOFS={"global:0x0051": {"note": "Flag."}})
    c.hand_evidence(FRAME_PROOFS={"global:0x0051": {"proved": [0, 1], "run": "kit2_x", "date": "2026-11-12", "menu": "M"}})
    c.report(ROWS)
    c.write(capsys)
    assert next(s for s in c.written()[0]["settings"] if s["key"] == "global:0x0051")["proved"] == {"values": [0, 1]}
    c.hand_evidence()
    _, said = c.write(capsys)
    flag = next(s for s in c.written()[0]["settings"] if s["key"] == "global:0x0051")
    assert "proved" not in flag and "frame proof  global:0x0051: its hand proof taken out" in said
    assert "proved" not in c.written()[1].get("global:0x0051", {})
    c.tables()
    _, said = c.write(capsys)
    assert "global:0x0051" not in {s["key"] for s in c.written()[0]["settings"]}
    assert "new record  global:0x0051 'Flag': taken out, NEW_RECORDS no longer holds it" in said


def test_the_hand_evidence_check_says_what_the_plain_pass_would_refuse_and_nothing_it_holds(tmp_path, monkeypatch,
                                                                                            capsys):
    """kit/writer/hand_evidence.py --check, read only: each part of the camera's hand evidence the plain pass would
    refuse, by table, key and field, never a value it holds (exit 1); a file it takes as it stands, exit 0. The way to
    bring the ILCE-1M2's file in line, whose pass reads it as before."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(**canary_tables())
    monkeypatch.setenv("CAMSET_CAMERA", CAM)
    c.hand_evidence(**WELL_FORMED)
    assert hand_evidence.main(["--check"]) == 0
    assert "the plain pass takes it as it stands" in capsys.readouterr().out
    c.hand_evidence(RECORD_FIXES={"global:0x04d2": {"group": "CNRYGROUP"}},
                    NOT_OFFERED={"0": {"evidence": "CNRYNOFF"}}, FRAME_PROOFS={"global:0x0099": {"run": "zebrarun"}})
    before = hand_evidence.path(CAM).read_bytes()
    assert hand_evidence.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "'RECORD_FIXES' 'global:0x04d2' holds 'group'" in out and "NOT_OFFERED [0]: no \"$key\"" in out
    assert "FRAME_PROOFS 'global:0x0099': the tables have no such entry" in out and "3 parts" in out
    assert not [w for w in ("CNRYGROUP", "CNRYNOFF", "zebrarun") if w in out]
    assert hand_evidence.path(CAM).read_bytes() == before


# ---------------------------------------------------------------- the second review (2026-11-13)

def published(c) -> tuple:
    """({key: setting} of the public definition as written, {key: evidence} of its evidence file)."""
    pub, ev, _ = c.written()
    return {s["key"]: s for s in pub["settings"]}, ev


def test_a_new_like_records_fill_never_makes_a_counted_value_checked(tmp_path, monkeypatch, capsys):
    """NEW_LIKE fills a gap at the start value with its sibling's labels: a value the sibling only names by a hand table
    (PP7_VALUES, FRAME_PROOFS' values, renamed by VALUE_FIXES: counted there) stays counted on the record, and only the
    sibling's established values (its public proof's) are "derived"; a sibling found by hand (NEW_RECORDS, no proof)
    lends none checked. The record's public proof lists only those, on the run that lays it out and every later one."""
    c = Cam(tmp_path / "a", monkeypatch)
    sibling = dict(FRAME_PROOFS={"global:0x01d8": {"note": "Drive.", "values": [[0, "Single Shooting"],
                                                                                [1, "Cont. Shooting"], [2, "Self"],
                                                                                [3, "Bracket"]]}},
                   PP7_VALUES=[["global:0x01d8", 9, "Ghost"]], VALUE_FIXES=[["global:0x01d8", 3, "Bracket set"]])
    c.tables(**sibling)                # the sibling first, its counted values written, then the record laid out like it
    fluor = {**ROWS[3], "records": {"global:0x0053": rec({"Fluor.: Warm White": 2})}}
    c.hand_evidence()
    c.report([ROWS[0]])
    c.write(capsys)
    c.tables(**sibling, NEW_LIKE={"global:0x0053": {"like": "global:0x01d8", "name": "Drive Mode (third)"}})
    c.report([ROWS[0], fluor])
    c.write(capsys)
    for _ in range(2):
        by, ev = published(c)
        assert by["global:0x01d8"]["proved"]["values"] == [0, 1]
        names = ev["global:0x0053"]["proved"]["names"]
        assert by["global:0x0053"]["proved"]["values"] == [0, 1, 2], names
        assert (names["0"], names["1"], names["3"], names["9"]) == ("derived", "derived", "counted", "counted")
        _, said = c.write(capsys)
        assert "0 labels changed or added" in said
    c = Cam(tmp_path / "b", monkeypatch)
    c.tables(NEW_RECORDS={"global:0x0051": {"like": "global:0x01d8", "name": "Flag",
                                            "values": [[0, "Off"], [1, "On"], [3, "Turbo"]], "note": ""}},
             NEW_LIKE={"global:0x0053": {"like": "global:0x0051", "name": "Flag (third)"}})
    c.report([ROWS[0], fluor])
    c.write(capsys)                    # the sibling is added after this run's records: the record waits, said
    _, said = c.write(capsys)
    assert "new like  global:0x0053: laid out like global:0x0051 now" in said
    by, ev = published(c)
    assert by["global:0x0053"]["proved"]["values"] == [2]
    assert {ev["global:0x0053"]["proved"]["names"][x] for x in ("0", "1", "3")} == {"counted"}


def test_a_reasons_day_or_a_marks_evidence_the_hand_evidence_no_longer_gives_is_taken_out(tmp_path, monkeypatch,
                                                                                          capsys):
    """Taking a reason's day, or a not-offered mark's evidence, out of the hand evidence takes it out of the definition's
    evidence on the next write, said, as a hand proof taken out is; so does a hand evidence file that holds none
    ("tables": {}) after a write that had them. The write is not refused as one that read the evidence away."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.tables(UNPROVED={"global:0x01dc": ["state", None, "W."]},
             NEW_RECORDS={"global:0x01dc": {"like": "global:0x01d8", "name": "Copy", "values": [], "note": ""}},
             PP7_VALUES=[["global:0x04d2", 6, "Turbo"]],
             NOT_OFFERED=[{"key": "global:0x04d2", "values": [6], "walk": "^Shooting > Speed\\b", "why": "W.",
                           "menu": "Speed"}])
    day = {"UNPROVED": {"global:0x01dc": {"1": "2026-11-12"}}}
    mark = {"NOT_OFFERED": {"0": {"$key": "global:0x04d2", "evidence": "walked whole, 2026-11-12"}}}
    c.hand_evidence(**day, **mark)
    c.write(capsys)
    _, ev = published(c)
    assert ev["global:0x01dc"]["unproved_reason"] == {"date": "2026-11-12"} and ev["global:0x04d2"]["not_offered"]
    c.hand_evidence(**mark)
    _, said = c.write(capsys)
    assert "unproved  global:0x01dc: its day taken out, the hand evidence no longer gives one" in said
    by, ev = published(c)
    assert "unproved_reason" not in ev.get("global:0x01dc", {}) and by["global:0x01dc"]["unproved_reason"]["kind"] == "state"
    c.hand_evidence(**day)
    _, said = c.write(capsys)
    assert "not offered  global:0x04d2 6: the mark's evidence taken out, the hand evidence no longer gives it" in said
    by, ev = published(c)
    assert "not_offered" not in ev.get("global:0x04d2", {}) and by["global:0x04d2"]["not_offered"][0]["value"] == 6
    c.hand_evidence(**day, **mark)
    c.write(capsys)
    c.hand_evidence()
    _, said = c.write(capsys)
    assert "its day taken out" in said and "6: the mark's evidence taken out" in said
    _, ev = published(c)
    assert "unproved_reason" not in ev.get("global:0x01dc", {}) and "not_offered" not in ev.get("global:0x04d2", {})
    _, said = c.write(capsys)
    assert "its day taken out" not in said and "evidence taken out" not in said and "0 labels changed or added" in said


def test_a_record_found_by_hand_stays_while_a_report_row_names_it(tmp_path, monkeypatch, capsys):
    """A record NEW_RECORDS added stays when its entry is taken out while a report row names it, proved or not: a row
    that finds it not one to one (accepted: it is marked disputed) or a readout row; one no row names goes."""
    for verdict in ("not one to one", "readout"):
        c = Cam(tmp_path / verdict.replace(" ", "_"), monkeypatch)
        c.report(ROWS)
        c.tables(NEW_RECORDS={"global:0x0051": {"like": "global:0x01d8", "name": "Flag", "values": [[0, "Off"]],
                                                "note": ""}})
        c.write(capsys)
        found = rec({"Off": 1, "On": 1}, "conflict", [{"value": 1, "camera": "Off, On", "schema": None,
                                                       "kind": "not one to one"}]) if verdict != "readout" else \
            rec({"Off": 0}, "readout")
        c.report(ROWS + [{"row": "Shooting > Found", "options": 2, "notices": [], "records": {"global:0x0051": found}}])
        c.tables()
        c.accept({"kind": "not one to one", "key": "global:0x0051"}) if verdict != "readout" else None
        _, said = c.write(capsys)
        flag = published(c)[0].get("global:0x0051")
        assert flag is not None and "new record  global:0x0051" not in said, verdict
        assert flag.get("disputed") is (True if verdict != "readout" else None), verdict


def test_a_note_suffix_with_parts_settles_and_a_new_like_records_own_fixes_do_not_lay_it_out_again(tmp_path,
                                                                                                    monkeypatch, capsys):
    """A "note+" holding parts ("seen; <day>") and a NEW_LIKE record with its own RECORD_FIXES tab and group: the second
    run, a look included, changes nothing and says so."""
    c = Cam(tmp_path, monkeypatch)
    c.report([ROWS[0], ROWS[1], ROWS[3]])
    c.tables(RECORD_FIXES={"global:0x04d2": {"name": "Speed", "note": "Speed note."},
                           "global:0x0053": {"name": "Third", "tab": "Other tab", "group": "Other group"}},
             NEW_LIKE={"global:0x0053": {"like": "global:0x01d8", "name": "Drive Mode (third)"}})
    c.hand_evidence(RECORD_FIXES={"global:0x04d2": {"note+": "(seen; 2026-11-12)"}})
    c.write(capsys)
    first = c.target.read_text(encoding="utf-8")
    for write in (True, False):
        _, said = c.write(capsys, write=write)
        assert c.target.read_text(encoding="utf-8") == first
        assert "0 labels changed or added" in said and "new like" not in said, said
    by, ev = published(c)
    assert ev["global:0x04d2"]["note_evidence"] == "seen; 2026-11-12" and by["global:0x04d2"]["note"] == "Speed note."
    assert (by["global:0x0053"]["tab"], by["global:0x0053"]["group"]) == ("Other tab", "Other group")


def test_a_copy_loses_a_hand_proof_its_live_setting_no_longer_has(tmp_path, monkeypatch, capsys):
    """A family whose copies' modes are not known yet: each copy takes its live setting's proof (writer/copies.py),
    a hand proof among them; once the hand evidence no longer gives the live setting's, the copies lose it too (they
    kept it before, 2026-11-13's review)."""
    c = Cam(tmp_path, monkeypatch)
    found = {"like": "global:0x04d2", "values": [[0, "A"], [1, "B"]], "note": ""}
    c.tables(NEW_RECORDS={"global:0x01d8": {**found, "name": "Live"}, "global:0x01da": {**found, "name": "Live (copy 1)"},
                          "global:0x01dc": {**found, "name": "Live (copy 2)"}},
             FRAME_PROOFS={"global:0x01d8": {"note": "Live."}},
             COPIES={"global:0x01d8": ["global:0x01da", "global:0x01dc"]}, COPY_MODES_UNKNOWN=["global:0x01d8"])
    c.hand_evidence(FRAME_PROOFS={"global:0x01d8": {"proved": [0], "run": "kit2_x", "date": "2026-11-12", "menu": "M"}})
    c.report(ROWS[1:])
    c.write(capsys)
    by, ev = published(c)
    assert by["global:0x01da"]["proved"] == {"values": [0]} and ev["global:0x01da"]["proved"]["by_hand"] is True
    c.hand_evidence()
    _, said = c.write(capsys)
    by, ev = published(c)
    assert not [k for k in ("global:0x01d8", "global:0x01da", "global:0x01dc") if "proved" in by[k]]
    assert "frame proof  global:0x01da: its hand proof taken out" in said


def test_a_hand_proofs_mark_is_evidence_and_a_public_one_is_flagged():
    """The mark a hand proof carries (by_hand) is evidence: split() keeps it in the evidence file only, and
    check_public's rule (evidence_in_public) flags a public proof that carries it."""
    doc = {"model": "X", "layouts": [{"signature": "s", "firmware": "1.00"}],
           "settings": [{"key": "global:0x0001", "name": "A", "values": [[0, "a"]],
                         "proved": {"run": "kit2_x", "date": "2026-11-12", "menu": ["M"], "values": [0],
                                    "by_hand": True}}]}
    pub, ev = definitions.split(doc)
    assert pub["settings"][0]["proved"] == {"values": [0]} and ev["settings"]["global:0x0001"]["proved"]["by_hand"]
    flagged = definitions.evidence_in_public({**pub, "settings": [{**pub["settings"][0],
                                                                   "proved": {"values": [0], "by_hand": True}}]})
    assert flagged == ["global:0x0001: proved.by_hand"]


def test_hand_evidence_for_a_table_the_plain_pass_does_not_read_is_said(tmp_path, monkeypatch, capsys):
    """My Menu's empty line's evidence (MY_MENU_EMPTY, a table only the ILCE-1M2's pass reads) is said, not applied."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.hand_evidence(MY_MENU_EMPTY={"line+": "(runs/kit2_x)"})
    _, said = c.write(capsys, write=False)
    assert "hand evidence  MY_MENU_EMPTY: read only by the ILCE-1M2's own pass so far, not applied" in said


# ---------------------------------------------------------------- the third review (2026-11-13)

MARKS = [{"key": "global:0x04d2", "values": [6], "walk": "^Shooting > Speed\\b", "why": "Six.", "menu": "Speed"},
         {"key": "global:0x04d2", "values": [8], "walk": "^Shooting > Speed\\b", "why": "Eight.", "menu": "Speed"}]
FOUR = {"key": "global:0x04d2", "values": [4], "walk": "^Shooting > Speed\\b", "why": "Four.", "menu": "Speed"}


def speed(marks: list) -> dict:
    return {"PP7_VALUES": [["global:0x04d2", 6, "Turbo"], ["global:0x04d2", 8, "Warp"]], "NOT_OFFERED": marks}


def marks_evidence(c) -> dict:
    return {m["value"]: m.get("evidence") for m in published(c)[1]["global:0x04d2"].get("not_offered") or []}


def test_two_marks_on_one_setting_keep_their_own_evidence(tmp_path, monkeypatch, capsys):
    """A setting with two NOT_OFFERED marks: each evidence part names its mark's values ("$values") as well as its
    setting, required where the table gives a setting more than one mark. Swapping the two entries in the table, or
    inserting a third before them, with the evidence file as it was, is refused (no evidence lands on another mark,
    none is taken out unasked), naming the place and the field, never a value; a part without "$values" there is
    refused too, and --check lists it. Taking one mark's evidence out takes out that mark's alone, said with its
    value."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.tables(**speed(MARKS))
    parts = {"0": {"$key": "global:0x04d2", "$values": [6], "evidence": "six walked whole, 2026-11-12"},
             "1": {"$key": "global:0x04d2", "$values": [8], "evidence": "eight walked whole, 2026-11-12"}}
    c.hand_evidence(NOT_OFFERED=parts)
    c.write(capsys)
    assert marks_evidence(c) == {6: "six walked whole, 2026-11-12", 8: "eight walked whole, 2026-11-12"}
    written = c.target.read_text(encoding="utf-8"), definitions.evidence_path(c.target).read_text(encoding="utf-8")
    for marks in ([MARKS[1], MARKS[0]], [FOUR, *MARKS]):
        c.tables(**speed(marks))
        with pytest.raises(hand_evidence.Refused) as got:
            c.write(capsys)
        assert "NOT_OFFERED [0]: its \"$values\" are not the values of the mark at that place" in str(got.value)
        assert "walked whole" not in str(got.value)
        assert (c.target.read_text(encoding="utf-8"),
                definitions.evidence_path(c.target).read_text(encoding="utf-8")) == written
    c.tables(**speed(MARKS))
    c.hand_evidence(NOT_OFFERED={"0": {"$key": "global:0x04d2", "evidence": "six walked whole, 2026-11-12"},
                                 "1": parts["1"]})
    with pytest.raises(hand_evidence.Refused) as got:
        c.write(capsys)
    assert "NOT_OFFERED [0]: no \"$values\" naming the values of its mark, which global:0x04d2 needs" in str(got.value)
    monkeypatch.setenv("CAMSET_CAMERA", CAM)
    assert hand_evidence.main(["--check"]) == 1 and "NOT_OFFERED [0]: no \"$values\"" in capsys.readouterr().out
    c.hand_evidence(NOT_OFFERED={"1": parts["1"]})            # mark 6's evidence taken out, on purpose
    _, said = c.write(capsys)
    assert "not offered  global:0x04d2 6: the mark's evidence taken out" in said
    assert "global:0x04d2 8: the mark's evidence taken out" not in said
    assert marks_evidence(c) == {8: "eight walked whole, 2026-11-12"}
    one = {"0": {"$key": "global:0x04d2", "evidence": "six walked whole, 2026-11-12"}}
    c.tables(**speed(MARKS[:1]))                              # one mark on the setting: "$values" may stay out
    c.hand_evidence(NOT_OFFERED=one)
    c.write(capsys)
    assert marks_evidence(c) == {6: "six walked whole, 2026-11-12"}


def test_the_ilce_1m2s_way_of_reading_checks_values_where_a_part_gives_them():
    """The ILCE-1M2's pass (put_back) reads a part without "$values" as before; one that gives them is held to its
    entry's values, as "$key" is, and puts no "$values" into the entry."""
    tables = {"NOT_OFFERED": [{"key": "k", "values": [6]}, {"key": "k", "values": [8]}]}
    got = hand_evidence.patched(json.loads(json.dumps(tables["NOT_OFFERED"])),
                                {"0": {"$key": "k", "evidence": "a"}, "1": {"$key": "k", "$values": [8], "evidence": "b"}},
                                "NO", table=True)
    assert got == [{"key": "k", "values": [6], "evidence": "a"}, {"key": "k", "values": [8], "evidence": "b"}]
    with pytest.raises(ValueError, match="\"\\$values\" are not the entry's values"):
        hand_evidence.patched(json.loads(json.dumps(tables["NOT_OFFERED"])),
                              {"0": {"$key": "k", "$values": [8], "evidence": "b"}}, "NO", table=True)


@pytest.mark.parametrize("like", [
    {"global:0x0068": {"like": "global:0x0053", "name": "Fourth"}, "global:0x0053": {"like": "global:0x01d8", "name": "Third"}},
    {"global:0x0053": {"like": "global:0x01d8", "name": "Third"}, "global:0x0068": {"like": "global:0x0053", "name": "Fourth"}},
], ids=["dependent first", "sibling first"])
def test_a_chain_of_new_like_records_is_laid_out_and_judged_sibling_first(tmp_path, monkeypatch, capsys, like):
    """A NEW_LIKE record laid out like another one (A like B, B like C): B is laid out and judged before A, whatever the
    file's order, so a value C names by a hand table only stays counted all down the chain (never in A's public proof)
    and the first write is the second."""
    c = Cam(tmp_path, monkeypatch)
    rows = [ROWS[0], ROWS[3], {"row": "Shooting > Fluor2", "options": 2, "notices": [],
                               "records": {"global:0x0068": rec({"Fluor.: Warm White": 2, "Fluor.: Day": 5})}}]
    c.tables(PP7_VALUES=[["global:0x01d8", 9, "Ghost"]])
    c.report(rows[:1])
    c.write(capsys)
    c.tables(PP7_VALUES=[["global:0x01d8", 9, "Ghost"]], NEW_LIKE=like)
    c.report(rows)
    texts = []
    for _ in range(2):
        c.write(capsys)
        texts.append((c.target.read_text(encoding="utf-8"), definitions.evidence_path(c.target).read_text(encoding="utf-8")))
    assert texts[0] == texts[1]
    by, ev = published(c)
    for k in ("global:0x0053", "global:0x0068"):
        assert 9 not in by[k]["proved"]["values"] and ev[k]["proved"]["names"]["9"] == "counted", k


def test_a_cycle_of_new_like_records_is_refused(tmp_path, monkeypatch, capsys):
    """NEW_LIKE records laid out like each other in a cycle: refused before anything is read, naming the cycle."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.tables(NEW_LIKE={"global:0x0053": {"like": "global:0x0068", "name": "A"},
                       "global:0x0068": {"like": "global:0x0053", "name": "B"}})
    with pytest.raises(SystemExit) as got:
        c.write(capsys, write=False)
    assert "NEW_LIKE's global:0x0053 -> global:0x0068 -> global:0x0053: a cycle" in str(got.value.code)


def test_a_new_like_record_neither_download_holds_is_said_and_left_out(tmp_path, monkeypatch, capsys):
    """A record NEW_LIKE names that the report proves but neither the run's start file nor its newest download holds:
    said, left out with its proofs (no traceback); the gate then holds it as a new record the definition lacks."""
    c = Cam(tmp_path, monkeypatch)
    c.tables(NEW_LIKE={"global:0x0054": {"like": "global:0x01d8", "name": "Missing"}})
    c.report([ROWS[0], {"row": "Shooting > Gone", "options": 1, "notices": [],
                        "records": {"global:0x0054": rec({"Only: One": 1})}}])
    doc, said = c.write(capsys, write=False)
    assert "new like  global:0x0054: not added, the run's newest download holds no such record either" in said
    assert "global:0x0054" not in {s["key"] for s in doc["settings"]} and "global:0x0054" in said.split("gate:")[1]


@pytest.mark.parametrize("hand", [False, True], ids=["no hand tables", "a reason's day taken out too"])
def test_a_write_never_drops_a_report_proofs_evidence_it_read_away(tmp_path, monkeypatch, capsys, hand):
    """A definition read with a report proof lean (its run, day and rows not put back) and a run that leaves that proof
    as it was read: the pass puts its names' sources on it (with_names), and the write is still refused, nothing
    written, for it would drop the evidence file's run, day and rows; a reason's day taken out on purpose in the same
    run covers nothing else (the review of 2026-11-13: until then the names hid the lean proof from the guard,
    definitions.lost_evidence, and such a write dropped them, with or without hand tables)."""
    from writer import generic
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    if hand:
        c.tables(UNPROVED={"global:0x01dc": ["state", None, "W."]},
                 NEW_RECORDS={"global:0x01dc": {"like": "global:0x01d8", "name": "Copy", "values": [], "note": ""}})
        c.hand_evidence(UNPROVED={"global:0x01dc": {"1": "2026-11-12"}})
    c.write(capsys)
    written = c.target.read_text(encoding="utf-8"), definitions.evidence_path(c.target).read_text(encoding="utf-8")
    assert {"run", "date", "menu"} <= set(published(c)[1]["global:0x0050"]["proved"])
    real_load = definitions.load

    def lean_flag(where, evidence=True):
        doc = real_load(where, evidence)
        for s in doc["settings"]:
            if s["key"] == "global:0x0050":
                s["proved"] = definitions.lean_proof(s["proved"])
        return doc
    monkeypatch.setattr(generic.definitions, "load", lean_flag)
    c.report([r for r in ROWS if "Flag" not in r["row"]])     # the proof is left as it was read
    if hand:
        c.hand_evidence()
    with pytest.raises(definitions.WouldLoseEvidence, match="global:0x0050: proved"):
        c.write(capsys)
    assert (c.target.read_text(encoding="utf-8"),
            definitions.evidence_path(c.target).read_text(encoding="utf-8")) == written
