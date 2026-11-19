"""Truthful proofs (docs/decisions/0025): a public proof lists the values a proof checked, and a setting some of whose
listed values were named from another setting's proof (a shared list) says so with one mark per setting, proved.shared,
never value by value (decision 16). The names are made afresh at every write, a name only a hand table gives is
counted in both passes, and the coverage ledger reads the writer's result: its private form says value by value which
were chosen and which inferred, its public form no more than the public definition. Made-up cameras and values."""
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import ROOT, coverage, definitions  # noqa: E402
from test_coverage import CAM, SETTINGS, extra_settings, ledger, write_proofs  # noqa: E402
from test_coverage import camera  # noqa: E402, F401  (the made-up camera's fixture)
from test_plain_hand_tables import ROWS, Cam  # noqa: E402

SCHEMA = json.loads((ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- the mark: one per setting, never per value

def test_a_proof_whose_list_holds_a_value_named_from_another_setting_is_marked():
    """lean_proof: a value named from another setting's proof ("derived") that no proof chose on this setting is listed
    and marks the setting (shared); a value chosen here is no inference whatever names it; a sampled scale's values
    between its points, a held value a hand table names, a name kept from an old schema or counted out mark nothing; a
    scale sampled on its line lists no value, so nothing to mark. A lean proof gives itself back, its mark with it."""
    lean = definitions.lean_proof
    whole = {"run": "r", "date": "d", "values": [0, 1],
             "names": {"0": "two readers", "1": "derived", "2": "derived", "3": "schema kept", "4": "counted"}}
    assert lean(whole) == {"values": [0, 1, 2], "shared": True}
    assert definitions.inferred(whole) == {2}, "1 was chosen here, whatever named it"
    assert lean({**whole, "names": {"0": "two readers", "1": "derived"}}) == {"values": [0, 1]}
    assert lean({"values": [0], "names": {"0": "one reader", "5": "hand table"}}) == {"values": [0, 5]}
    sample = {"sampled": {"proofs": 3, "linear": None}, "names": {"0": "sampled", "10": "sampled"}}
    assert lean(sample) == {"values": [0, 10], "sampled": {"linear": None}} and definitions.inferred(sample) == set()
    picker = {"sampled": {"proofs": 3, "linear": None, "from_start": True}, "names": {"7": "derived", "8": "derived"}}
    assert lean(picker) == {"values": [7, 8], "shared": True, "sampled": {"linear": None}}
    assert lean({"sampled": {"proofs": 2, "linear": True}, "names": {"7": "derived"}}) == {"sampled": {"linear": True}}
    for p in ({"values": [0, 1, 2], "shared": True}, {"values": [7, 8], "shared": True, "sampled": {"linear": None}},
              {"values": [0]}):
        assert lean(p) == p and definitions.inferred(p) == set(), "a lean proof says nothing value by value"


def test_the_mark_is_public_and_merge_puts_the_evidence_back_beside_an_older_file_without_it(tmp_path, capsys):
    """The public file carries the mark and nothing it was made from (the names stay in the evidence file); the schema
    takes it as a boolean. A public file written before the mark existed, read with evidence whose names give one,
    takes its whole proofs back with nothing set aside: the mark is made from the names, never evidence of its own."""
    import jsonschema
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    doc = {"$schema": definitions.SCHEMA_REF, "definition_format": definitions.FORMAT, "model": "ILCE-0X0",
           "tabs": ["Shooting"], "layouts": [{"signature": "0" * 16, "model": "ILCE-0X0", "firmware": "1.00"}],
           "settings": [{"key": "global:0x0001", "area": "global", "id": 1, "name": "Key", "tab": "Shooting",
                         "group": "G", "values": [[0, "A"], [1, "B"], [2, "C"]],
                         "proved": {"run": "kit2_x", "date": "2026-01-02", "menu": ["Key"], "values": [0],
                                    "names": {"0": "two readers", "1": "derived", "2": "derived"}}}],
           "menu": [], "camera": {}}
    definitions.write(p, doc)
    text = p.read_text(encoding="utf-8")
    pub = json.loads(text)
    assert pub["settings"][0]["proved"] == {"values": [0, 1, 2], "shared": True}
    assert definitions.evidence_in_public(pub, text) == [] and "derived" not in text
    check = jsonschema.Draft202012Validator(SCHEMA["$defs"]["setting"])
    assert check.is_valid(pub["settings"][0])
    assert not check.is_valid({**pub["settings"][0], "proved": {"values": [0], "shared": "yes"}})
    # the file as an older write left it, the mark not there yet
    pub["settings"][0]["proved"] = {"values": [0, 1, 2]}
    p.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    whole = definitions.load(p)
    assert definitions.STALE not in whole and definitions.newly_stale(whole, p) == []
    assert whole["settings"][0]["proved"]["names"]["1"] == "derived", "the whole proof put back"
    assert "no longer fits" not in capsys.readouterr().err
    assert definitions.lost_evidence(whole, json.loads(definitions.evidence_path(p).read_text(encoding="utf-8"))) == []


# ---------------------------------------------------------------- the writer: names made afresh, hand names counted

def test_a_rule_or_a_tables_name_is_never_taken_from_the_old_proof():
    """with_names: "derived", "hand table" and "counted" are a rule's or a table's word, made afresh at every write, so
    one the old proof held stands only where this run's rule or table says it again: a value no rule names now keeps
    no source and leaves the listed values; a chosen value takes its readers' source, never an old rule's. A reading
    kept from the old proof stays."""
    from writer.proofs import with_names
    s = {"key": "k", "values": [[0, "A"], [1, "B"], [2, "C"], [3, "D"], [4, "E"]],
         "proved": {"run": "r", "date": "d", "values": [0, 1],
                    "names": {"0": "two readers", "1": "derived", "2": "derived", "3": "hand table", "4": "counted"}}}
    with_names(s, {}, {}, {})
    assert s["proved"]["names"] == {"0": "two readers", "1": "one reader"}
    assert definitions.lean_proof(s["proved"]) == {"values": [0, 1]}
    with_names(s, {}, {3: "hand table"}, {2: "derived"})
    assert s["proved"]["names"] == {"0": "two readers", "1": "one reader", "2": "derived", "3": "hand table"}


def test_a_name_only_a_hand_table_gives_is_counted_unless_a_shared_list_or_a_held_mark_backs_it():
    """named_not_proved, in both passes: a value a hand table names that no proof chose is counted (named, not proved),
    unless a rule this run named it from another setting's proof, which makes it inferred ("derived"), or a held
    not-offered mark says the camera writes it itself; a chosen value keeps the table's name, and so does any value of
    a scale proved by samples (its samples name the values between), but not of a picker's sample from the option the
    camera held, which names nothing."""
    from writer import hand_facts
    doc = {"settings": [{"key": "a", "values": [[0, "A"], [1, "B"], [2, "C"], [3, "D"]], "proved": {"values": [0]},
                         "not_offered": [{"value": 3, "label": "D", "held": True}]},
                        {"key": "line", "values": [[0, "-1"], [1, "0"], [2, "+1"]],
                         "proved": {"sampled": {"proofs": 2, "linear": True}}},
                        {"key": "pick", "values": [[0, "A"], [1, "B"]],
                         "proved": {"sampled": {"proofs": 3, "linear": None, "from_start": True}}}]}
    over = {"a": {0: "hand table", 1: "hand table", 2: "hand table", 3: "hand table"}, "line": {1: "hand table"},
            "pick": {1: "hand table"}}
    assert hand_facts.named_not_proved(doc, over, {"a": {2: "derived"}}) == 2
    assert over["a"] == {0: "hand table", 1: "counted", 2: "derived", 3: "hand table"}
    assert over["line"] == {1: "hand table"} and over["pick"] == {1: "counted"}


def test_both_passes_set_the_names_one_way():
    """The a1 II's own pass and the plain pass name values through one step (hand_facts.name_sources: a hand table's
    name no proof and no shared list backs counted, then with_names), so neither lists a hand-table-only name as
    proved (review 2026-11-18, finding 19)."""
    import schema_update as S
    from writer import generic
    for f in (S.main, generic.generic):
        src = inspect.getsource(f)
        assert "hand_facts.name_sources(" in src and "with_names(" not in src, f.__name__


def dial(option: str, y: int, x: int = 448, path=("My Dial Settings",)) -> dict:
    """A picker proof line of a table cell, its row read as it was then ("mFront dial / *i")."""
    return {"path": list(path), "kind": "table", "opens": "picker", "screen": "table", "option": option, "cell": [x, y],
            "changes": [{"key": "global:0x045f", "before": [0, 0, 0], "after": [1, 0, 0]}]}


def test_a_table_cell_proved_under_an_older_reading_of_its_row_is_the_plans_cell():
    """picker_groups finds a slot's group through prove_run's plan, which names a table's cells as the kit names a
    table's row (match.table_row_label over every reading of the row: an icon read as a letter or a mark in front, the
    values of the cells before it glued on, left out). A proof line made while the row read otherwise ("mFront dial / *i",
    "Tir Rear Dial R", "T Rear Dial R -- / *2") is the plan's cell when its row, named by that same rule from the
    readings its lines give at that height, is a row the plan holds (plan_keys); a key the plan holds as it is stays.
    A row that really is another ("Rear Dial L" against the plan's "Rear Dial R", "Tv Auto/Manual Switch" against "Av
    Auto/Manual Switch") is no plan cell, so a rule that no longer fires is never revived by a likeness."""
    import schema_update as S
    plan = {"My Dial Settings / Front dial / *i", "My Dial Settings / Front dial / 2", "My Dial Settings / Front dial",
            "My Dial Settings / Rear Dial R", "My Dial Settings / Rear Dial R / *2", "My Dial Settings / Rear Dial R / *3",
            "My Dial Settings / 17 Rear Dial L / *2", "Shutter / Av Auto/Manual Switch / x"}
    lines = [dial("mFront dial / *i", 148), dial("wFront dial -- / 2", 148, 516), dial("•Front dial --", 148, 380),
             dial("Tir Rear Dial R", 200, 380), dial("T Rear Dial R -- / *2", 200), dial("T Rear Dial R -- -- / *3", 200, 516),
             dial("17 Rear Dial L -- / *2", 252), dial("Rear Dial L / *3", 304),
             dial("Tv Auto/Manual Switch / x", 148, path=("Shutter",))]
    assert S.plan_keys(lines, plan) == [
        "My Dial Settings / Front dial / *i", "My Dial Settings / Front dial / 2", "My Dial Settings / Front dial",
        "My Dial Settings / Rear Dial R", "My Dial Settings / Rear Dial R / *2", "My Dial Settings / Rear Dial R / *3",
        "My Dial Settings / 17 Rear Dial L / *2", None, None]
    # a key the plan holds as it is stays, whatever the row's other readings say
    assert S.plan_keys([dial("17 Rear Dial L / *2", 252), dial("x 17 Rear Dial L -- / *3", 252)], plan)[0] == \
        "My Dial Settings / 17 Rear Dial L / *2"


def test_a_copy_takes_its_settings_established_values_named_from_its_proof():
    """copy_names: a copy (copy_of) lists, named from its setting's proof ("derived", so its setting is marked), each
    value its setting established (chosen there, or itself named from another setting) under the same label, where
    its own proofs name the value no other way: a value a proof wrote to the copy under another name is not lent, a
    value chosen on the copy keeps its readers' name, one its setting did not establish stays as it was (a hand
    table's, counted). A copy with no proof, a copy proved on a line and a copy of a setting with no proof take
    nothing: no proof is made up."""
    from writer.copies import copy_names
    vals = [[0, "A"], [1, "B"], [2, "C"], [3, "D"]]
    main = {"key": "m", "values": vals, "proved": {"values": [0, 1], "names": {"0": "two readers", "1": "two readers",
                                                                                "2": "derived"}}}
    copy = {"key": "c", "copy_of": "m", "values": [[0, "A"], [1, "B"], [2, "X"], [3, "D"]],
            "proved": {"values": [0], "names": {"0": "one reader", "3": "counted"}}}
    bare = {"key": "b", "copy_of": "m", "values": vals}
    line = {"key": "l", "copy_of": "m", "values": vals, "proved": {"sampled": {"proofs": 3, "linear": True}}}
    orphan = {"key": "o", "copy_of": "n", "values": vals, "proved": {"values": [0], "names": {"0": "one reader"}}}
    unproved_main = {"key": "n", "values": vals}
    doc = {"settings": [main, copy, bare, line, orphan, unproved_main]}
    assert copy_names(doc) == 1
    assert copy["proved"]["names"] == {"0": "one reader", "1": "derived", "3": "counted"}
    assert definitions.lean_proof(copy["proved"]) == {"values": [0, 1], "shared": True}
    assert definitions.inferred(copy["proved"]) == {1}, "the ledger's one rule: inferred, privately"
    assert "proved" not in bare and line["proved"] == {"sampled": {"proofs": 3, "linear": True}}
    assert orphan["proved"]["names"] == {"0": "one reader"}
    assert copy_names(doc) == 0, "a rerun names nothing afresh"


def test_both_passes_name_a_copys_values_from_its_setting():
    """The a1 II's own pass and the plain pass both run copy_names once the copies are written (with_copies) and the
    names set, so a copy proved on every value but the one it held at its start never shows that value as the one gap
    in its list (decision 16)."""
    import schema_update as S
    from writer import generic
    for f in (S.main, generic.plain):
        src = inspect.getsource(f)
        assert "copy_names(" in src and src.index("with_copies(") < src.index("copy_names("), f.__name__
    assert inspect.getsource(S.main).index("hand_facts.name_sources(") < inspect.getsource(S.main).index("copy_names(")


def gap_doc() -> dict:
    """Made-up settings on the made-up camera's records (Cam's start file holds 0 in 0x01d8, 0x01da and 0x01dc)."""
    vals = [[0, "A"], [1, "B"], [2, "C"]]

    def s(key, proved=None, **more):
        rid = int(key.split("0x")[1][:4], 16)
        return {"key": key, "area": "global", "id": rid, "name": f"Thing {key[-4:]}", "values": vals,
                **({"proved": proved} if proved else {}), **more}
    return {"settings": [
        s("global:0x01d8", {"values": [1, 2]}),                               # short of 0, the start's: kind (a)
        s("global:0x01da", {"values": [0, 1]}),                               # short of 2, no start's: kind (b)
        s("global:0x01dc", {"values": [1, 2]}, not_offered=[{"value": 0, "label": "A", "held": True}]),  # a mark
        s("global:0x0050", None, unproved_reason={"kind": "state", "why": "Kept by the camera."}),     # a reason
        s("global:0x0051", {"values": [0]}),                                  # two short: no gap of one
        s("global:0x0053", {"sampled": {"proofs": 3, "linear": True}})]}      # a line: every value


def test_a_public_list_one_value_short_is_found_and_told_by_the_start_files(tmp_path, monkeypatch):
    """writer/listgaps.py: a setting whose public proof lists every value of its list but one is a gap, of kind (a) where a
    start file of this camera holds the missing value (how many files, never which value), (b) where none does, (c)
    where no start file is here to tell; a value a not_offered mark names (held or not), a setting a reason covers, a
    list two short and a scale on a line are no gap."""
    from writer import listgaps as gaps
    c = Cam(tmp_path, monkeypatch)
    got = {q["key"]: q for q in gaps.questions(gap_doc(), c.root)}
    assert set(got) == {"global:0x01d8", "global:0x01da"}
    assert (got["global:0x01d8"]["start"], got["global:0x01d8"]["files"]) == ("a", 1)
    assert got["global:0x01da"]["start"] == "b" and got["global:0x01da"]["kind"] == gaps.KIND
    assert all("value" not in q for q in got.values()), "a gap names its setting, never the value"
    none = tmp_path / "no_runs"
    none.mkdir()
    assert {q["start"] for q in gaps.questions(gap_doc(), none)} == {"c"}


def test_the_gate_counts_a_gap_and_refuses_one_of_a_start_value(tmp_path, monkeypatch, capsys):
    """The gate counts each gap as an open question: a ruling in the accepted file accepts one of kind (b) by its key,
    never one of kind (a); a look prints them; --write refuses while one of kind (a) stands, --force or not, naming the
    three ways out, with exit status 1 (a SystemExit with words)."""
    from writer import listgaps as gaps
    from writer.gate import gate
    c = Cam(tmp_path, monkeypatch)
    qs = gaps.questions(gap_doc(), c.root)
    b = [q for q in qs if q["start"] == "b"]
    c.accept({"kind": gaps.KIND, "key": "global:0x01da"}, {"kind": gaps.KIND, "key": "global:0x01d8"})
    assert gate(b, "ILCE-7M5_fw4.00", force=False, write=True) is True
    assert "1 lists one value short" in capsys.readouterr().out
    assert gate(qs, "ILCE-7M5_fw4.00", force=False, write=False) is False
    out = capsys.readouterr().out
    assert "global:0x01d8" in out and "a start file of this camera holds the value it lacks (1 start file)" in out
    assert "never accepted" in out
    for force in (False, True):
        with pytest.raises(gaps.OneShort) as e:
            gate(qs, "ILCE-7M5_fw4.00", force=force, write=True)
        said = str(e.value.code)
        assert isinstance(e.value.code, str) and "global:0x01d8" in said
        assert all(w in said for w in ("another start", "held not-offered mark", "reason")), said


def test_both_passes_check_their_lists_one_value_short(tmp_path, monkeypatch, capsys):
    """The plain pass, a look and a write: a list its proofs now leave one value short, the value the camera's start
    file holds, is printed with the gate line and counted in it, and --write refuses it; the a1 II's own pass runs the
    same check before its gate."""
    import schema_update as S
    from writer import listgaps as gaps
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.write(capsys)
    c.report([{**ROWS[0], "records": {"global:0x01d8": {**ROWS[0]["records"]["global:0x01d8"],
                                                        "proved": {"Cont. Shooting": 1}}}}] + ROWS[1:])
    _, said = c.write(capsys, write=False)
    assert "global:0x01d8" in said and "1 lists one value short" in said, said
    with pytest.raises(gaps.OneShort):
        c.write(capsys)
    src = inspect.getsource(S.main)
    assert "listgaps.questions(" in src and src.index("listgaps.questions(") < src.index("gate(open_ones")


def test_a_rerun_drops_a_name_no_rule_gives_any_more(tmp_path, monkeypatch, capsys):
    """The plain pass on a definition whose proof names a value "derived" with no rule naming it this run (a rule that
    no longer fires): the value stays in the list, named, but leaves the proof's values and the setting's mark. Its
    list is then one value short of a value no start file holds, which the gate counts and a ruling accepts."""
    c = Cam(tmp_path, monkeypatch)
    c.report(ROWS)
    c.write(capsys)
    pub, ev, _ = c.written()
    s = next(x for x in pub["settings"] if x["key"] == "global:0x01d8")
    s["values"].append([7, "Ghost"])
    s["proved"] = {"values": [0, 1, 7], "shared": True}
    ev["global:0x01d8"]["proved"]["names"]["7"] = "derived"
    c.target.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    evfile = definitions.evidence_path(c.target)
    whole_ev = json.loads(evfile.read_text(encoding="utf-8"))
    whole_ev["settings"] = ev
    evfile.write_text(json.dumps(whole_ev, indent=1), encoding="utf-8")
    assert definitions.load(c.target)["settings"]           # it reads back whole
    with pytest.raises(SystemExit, match="open questions above"):
        c.write(capsys)
    c.accept({"kind": "one value short", "key": "global:0x01d8"})
    _, said = c.write(capsys)
    assert "1 lists one value short, every one accepted" in said, said
    pub, ev, _ = c.written()
    s = next(x for x in pub["settings"] if x["key"] == "global:0x01d8")
    assert [7, "Ghost"] in s["values"] and s["proved"] == {"values": [0, 1]}
    assert "7" not in ev["global:0x01d8"]["proved"]["names"]


# ---------------------------------------------------------------- the ledger reads the writer's result

def test_the_private_form_says_value_by_value_and_the_public_no_more_than_the_mark(camera):  # noqa: F811 (the fixture)
    """November slot 2 as the test camera holds it (test_coverage's fixture, the writer's result: 10 and 11 chosen on
    it, 12 to 14 named from slot 1's proof). Privately the values the writer named from a shared list are inferred, the
    chosen ones proved; publicly, where the definition says only that some of the listed values were named so, every
    listed value of the marked setting is "proved or named from a shared list", and an unmarked setting's are proved,
    as privately. Inferred never reaches the public form; the public form passes its checks and its schema."""
    import jsonschema
    priv = {o["key"]: o["values"] for o in ledger().options}
    inf = coverage.INFERRED
    assert priv["global:0x0121"] == {10: "proved", 11: "proved", 12: inf, 13: inf, 14: inf}
    assert priv["global:0x0120"] == {v: "proved" for v in (10, 11, 12, 13, 14)}
    pub = coverage.public_doc(ledger(public=True))
    by = {o["key"]: o["statuses"] for o in pub["options"]}
    assert by["global:0x0121"] == {coverage.PROVED_OR_SHARED: [10, 11, 12, 13, 14]}
    assert by["global:0x0120"] == {"proved": [10, 11, 12, 13, 14]}
    assert not [o for o in pub["options"] if inf in o["statuses"]] and f'"{inf}"' not in coverage.text(pub)
    assert not coverage.public_problems(pub, camera=CAM)
    schema = json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(pub)
    assert coverage.public_doc(ledger())["options"] == pub["options"], "the private build's public form is the same"


def test_the_writers_inference_stands_where_the_lists_own_lines_do_not_bear_it_out(camera, monkeypatch, capsys):  # noqa: F811 (the fixture)
    """The ledger's shared-list check (a setting's own proof lines showing two values as the list names them, no line
    reading a value as another) decides nothing any more: a value the writer named from the list is inferred though a
    line of the setting's own contradicts the list, and kit/tools/coverage.py --shared says where the check does not
    bear the writer out."""
    import coverage as tool
    contra = {"path": ["November"], "kind": "table", "opens": "picker", "label": "Ant", "shown": "Dog", "vlm": "Dog",
              "changes": [{"key": "global:0x0121", "before": 10, "after": 11}]}
    write_proofs(camera, "kit2_pass2", [contra])
    led = ledger()
    assert {o["key"]: o for o in led.options}["global:0x0121"]["values"][12] == coverage.INFERRED
    lines = coverage.shared_view(led)
    assert any("global:0x0121" in x and "not borne out" in x for x in lines), lines
    coverage.forget()
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--shared"])
    tool.main()
    assert "not borne out" in capsys.readouterr().out


def test_a_sample_is_sampled_in_both_forms(camera):  # noqa: F811 (the fixture)
    """A scale proved by samples off its line: its values between are "sampled" in the private form, read from the
    whole proof's names, as in the public one, read from its lean values (review 2026-11-18, B4: the whole proof of a
    sample lists no values, so the private form gave none of its values "sampled")."""
    k = "global:0x0102"
    i = next(n for n, x in enumerate(SETTINGS) if x["key"] == k)
    whole = {"run": "kit2_pass2", "sampled": {"proofs": 3, "linear": None}, "names": {"0": "sampled", "10": "sampled"}}
    with extra_settings(camera, evidence={k: {"proved": whole}}):
        assert SETTINGS[i]["proved"] == definitions.lean_proof(whole)
        priv = {o["key"]: o["values"] for o in ledger().options}[k]
        pub = {o["key"]: o["values"] for o in ledger(public=True).options}[k]
        assert priv == pub == {0: "sampled", 10: "sampled", 20: "not yet tried"}


def test_a_status_list_names_the_new_public_status_once():
    """The public status of a marked setting's listed values is one of the ledger's statuses, a value's (the coverage
    schema's option vocabulary), settled as proved and inferred are; inferred stays private."""
    assert coverage.PROVED_OR_SHARED in coverage.STATUS_NAMES
    schema = json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8"))
    assert coverage.PROVED_OR_SHARED in schema["$defs"]["option_status"]["enum"]
    assert coverage.INFERRED in coverage.NEVER_PUBLIC and coverage.PROVED_OR_SHARED not in coverage.NEVER_PUBLIC
    assert {coverage.PROVED_OR_SHARED, coverage.INFERRED, "proved"} <= coverage.SETTLED
