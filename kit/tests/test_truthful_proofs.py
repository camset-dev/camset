"""Truthful proofs (docs/decisions/0025): a public proof lists the values a proof checked, and a setting some of whose
listed values were named from another setting's proof (a shared list) says so with one mark per setting, proved.shared,
never value by value (decision 16). The names are made afresh at every write, a name only a hand table gives is
counted in both passes, and the coverage ledger reads the writer's result: its private form says value by value which
were chosen and which inferred, its public form no more than the public definition. Made-up cameras and values."""
import inspect
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, definitions  # noqa: E402
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


def test_a_rerun_drops_a_name_no_rule_gives_any_more(tmp_path, monkeypatch, capsys):
    """The plain pass on a definition whose proof names a value "derived" with no rule naming it this run (a rule that
    no longer fires): the value stays in the list, named, but leaves the proof's values and the setting's mark."""
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
    c.write(capsys)
    pub, ev, _ = c.written()
    s = next(x for x in pub["settings"] if x["key"] == "global:0x01d8")
    assert [7, "Ghost"] in s["values"] and s["proved"] == {"values": [0, 1]}
    assert "7" not in ev["global:0x01d8"]["proved"]["names"]
