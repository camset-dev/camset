"""Leftovers of the engineering review of 2026-11-18's fixes, each closed in a file its neighbour's fix did not own:
the hand evidence's part for the limit pairs (LIMIT_PAIRS). Made-up cameras, settings, keys and words; no camera, no
private file."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from writer import hand_evidence  # noqa: E402
# imported before any test points the kit at a data folder of its own: it binds the a1 II's tables as it is imported
import schema_update  # noqa: E402,F401
from test_plain_hand_tables import CAM, Cam, rec  # noqa: E402
from test_review_ordered import pairs_doc  # noqa: E402


# ---------------------------------------------------------------- 1. the limit pairs' hand evidence

PAIRS = {"global:0x0001": {"upper": "global:0x0002", "lower_moves_upper": True, "upper_moves_lower": True}}
SAID = "made-up words: what showed it"          # no run, no day: a test's evidence holds none of the owner's


def evidence_doc(tables: dict) -> dict:
    return {"$schema": hand_evidence.SCHEMA_REF, "hand_format": hand_evidence.FORMAT, "camera": CAM, "tables": tables}


def test_the_hand_evidence_takes_what_proved_each_direction_of_a_limit_pair():
    """schemas/hand-evidence.schema.json, which the plain pass holds the file to, has a LIMIT_PAIRS part: by the lower
    limit's key, its "evidence" by direction (the field the public table marks it with), words only; nothing else on a
    pair (no upper, no moves_it: the public table's alone), and a part for a pair the tables lack is refused."""
    tables = {"LIMIT_PAIRS": PAIRS}
    good = evidence_doc({"LIMIT_PAIRS": {"global:0x0001": {"evidence": {"lower_moves_upper": SAID,
                                                                         "upper_moves_lower": SAID}}}})
    assert hand_evidence.plain_problems(good, CAM, tables) == []
    for part in ({"upper": "global:0x0002"}, {"lower_moves_upper": True}, {"evidence": {"moves_it": SAID}},
                 {"evidence": {"lower_moves_upper": True}}, {"evidence": SAID}):
        bad = evidence_doc({"LIMIT_PAIRS": {"global:0x0001": part}})
        assert hand_evidence.plain_problems(bad, CAM, tables), part
    stale = evidence_doc({"LIMIT_PAIRS": {"global:0x0003": {"evidence": {"lower_moves_upper": SAID}}}})
    assert hand_evidence.plain_problems(stale, CAM, tables) == ["LIMIT_PAIRS 'global:0x0003': the tables have no such entry"]


def test_a_direction_marked_without_its_evidence_is_written_without_moves_it(capsys):
    """with_limit_pairs (kit/writer/limits.py): where the camera's hand evidence file is there (`evidence` a dict, the
    plain pass's LIMIT_PAIRS part read apart, or {} for the a1 II's pass, whose entries carry it put back), a direction
    the public table marks is written with moves_it only where the evidence shows it, said otherwise; without the file
    (None) moves_it is the table's, as before. The evidence never sets moves_it, and its words reach no field."""
    from writer.limits import with_limit_pairs

    def written(table, evidence):
        doc = pairs_doc()
        with_limit_pairs(doc, table, evidence=evidence)
        by = {s["key"]: s for s in doc["settings"]}
        return by["global:0x0001"]["at_most"], by["global:0x0002"]["at_least"], capsys.readouterr().out
    both = ({"setting": "global:0x0002", "moves_it": True}, {"setting": "global:0x0001", "moves_it": True})
    neither = ({"setting": "global:0x0002"}, {"setting": "global:0x0001"})
    assert written(PAIRS, None)[:2] == both                         # no evidence file: the table's
    lower, upper, said = written(PAIRS, {})                         # a file with nothing for the pair
    assert (lower, upper) == neither
    for flag in ("lower_moves_upper", "upper_moves_lower"):
        assert (f"limit pair global:0x0001 <= global:0x0002: nothing in the hand evidence shows {flag} (its "
                f"\"evidence\" in LIMIT_PAIRS); written without moves_it") in said, said
    # the plain pass: the part read apart, one direction shown
    part = {"global:0x0001": {"evidence": {"upper_moves_lower": SAID}}}
    assert written(PAIRS, part)[:2] == (neither[0], both[1])
    # the a1 II's pass: the evidence put back into the entry
    put_back = {"global:0x0001": {**PAIRS["global:0x0001"], "evidence": {"lower_moves_upper": SAID}}}
    lower, upper, said = written(put_back, {})
    assert (lower, upper) == (both[0], neither[1]) and SAID not in json.dumps([lower, upper])
    # evidence for a direction the table does not mark never sets moves_it
    unmarked = {"global:0x0001": {"upper": "global:0x0002"}}
    assert written(unmarked, {"global:0x0001": {"evidence": {"lower_moves_upper": SAID}}})[:2] == neither


@pytest.mark.parametrize("evidence, want", [
    (None, {"setting": "global:0x0b65", "moves_it": True}),                    # no file: the table's
    ({}, {"setting": "global:0x0b65"}),                                         # a file with nothing for it
    ({"LIMIT_PAIRS": {"global:0x0b65": {"evidence": {"upper_moves_lower": SAID}}}},
     {"setting": "global:0x0b65", "moves_it": True}),
], ids=["no file", "nothing for it", "shown"])
def test_the_plain_pass_holds_a_marked_direction_to_its_evidence(tmp_path, monkeypatch, capsys, evidence, want):
    """The plain pass (every camera's but the a1 II's) reads the LIMIT_PAIRS part of the hand evidence apart and gives
    it to the writer: a made-up camera whose table marks one direction, with no evidence file, with one holding nothing
    for the pair, and with one showing it. The evidence's words reach neither the public definition nor its evidence."""
    c = Cam(tmp_path, monkeypatch)
    steps = {"Step 1": 4, "Step 2": 6, "Step 3": 8}
    c.report([{"row": "Shooting > Low End", "options": 3, "notices": [], "records": {"global:0x0b65": rec(dict(steps))}},
              {"row": "Shooting > High End", "options": 3, "notices": [], "records": {"global:0x0b63": rec(dict(steps))}}])
    c.tables(LIMIT_PAIRS={"global:0x0b65": {"upper": "global:0x0b63", "upper_moves_lower": True}})
    if evidence is not None:
        c.hand_evidence(**evidence)
    _, said = c.write(capsys)
    public, private, text = c.written()
    by = {s["key"]: s for s in public["settings"]}
    assert by["global:0x0b63"]["at_least"] == want, said
    assert by["global:0x0b65"]["at_most"] == {"setting": "global:0x0b63"}
    assert ("written without moves_it" in said) is (evidence == {})
    assert SAID not in text and SAID not in json.dumps(private)
