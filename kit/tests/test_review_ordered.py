"""The engineering review of 2026-11-18, finding 6 (track 4's finding 2): two limits the camera keeps in order, ISO
Range Limit's two ends and ISO AUTO's Minimum and Maximum, which the definition could not say, so an editor let a
lower limit be set above its upper one. The hand table's LIMIT_PAIRS names each pair and the directions in which a
proof showed the camera move the other limit; both writer passes put it on the two settings as at_most and at_least,
where the two list the same values and are kept in the same sets, checked against the camera's downloads. The lower
ISO Range Limit is named by its end, as the upper is. Made-up settings, keys and values, the a1 II's committed public
files where a test reads the shipped ones, and files made from its sample with made-up values."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import datafiles, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_tables  # noqa: E402
# imported before any test points the kit at a data folder of its own: it binds the a1 II's tables as it is imported
import schema_update  # noqa: E402,F401

A1 = paths.A1II
PUB = definitions.load_public(A1)
PUB_BY = {s["key"]: s for s in PUB["settings"]}
CAM = "ILCE-0X0_fw1.00"             # a made-up camera
LOWERS = ("global:0x0b65", "global:0x0b69", "global:0x0b6d")
UPPERS = ("global:0x0b63", "global:0x0b67", "global:0x0b6b")
# the a1 II's pairs as its hand table names them: ISO Range Limit, both directions proved; ISO AUTO's Minimum and
# Maximum, and each mode's copies of the two, a Minimum chosen above the Maximum proved to raise it, the other way not
# tried
A1_PAIRS = {
    "global:0x0b65": {"upper": "global:0x0b63", "lower_moves_upper": True, "upper_moves_lower": True},
    "global:0x0dfa": {"upper": "global:0x0e00", "lower_moves_upper": True},
    "global:0x0dfc": {"upper": "global:0x0e02", "lower_moves_upper": True},
    "global:0x0dfe": {"upper": "global:0x0e04", "lower_moves_upper": True},
}


# ---------------------------------------------------------------- the hand table

def test_the_a1_hand_tables_name_both_pairs_and_the_lower_end_by_its_name():
    """The a1 II's LIMIT_PAIRS: ISO Range Limit (both directions proved, 2026-11-18), ISO AUTO's Minimum and Maximum
    and each mode's copies of the two (a Minimum chosen above the Maximum raised it, in Movie mode the movie copies
    and in Stills mode the stills copies; a Maximum chosen below the Minimum was never tried, so no upper_moves_lower).
    The lower ISO Range Limit's three records are named "ISO Range Limit (lower)", together, so they stay one row
    beside "ISO Range Limit (upper)". Each pair lists the same values in the committed definition and is kept in the
    same sets; the file fits its JSON Schema."""
    T = hand_tables.load(A1, evidence=False)
    assert T.LIMIT_PAIRS == A1_PAIRS
    assert [T.RECORD_FIXES[k]["name"] for k in LOWERS] == ["ISO Range Limit (lower)"] * 3
    assert [T.RECORD_FIXES[k]["name"] for k in UPPERS] == ["ISO Range Limit (upper)"] * 3
    for lower, e in A1_PAIRS.items():
        lo, up = PUB_BY[lower], PUB_BY[e["upper"]]
        assert lo["values"] == up["values"] and len(lo["values"]) > 2, lower
        assert (lo["area"], lo.get("in_sets")) == (up["area"], up.get("in_sets")), lower
    doc = json.loads(datafiles.hand_tables_file(A1).read_text(encoding="utf-8"))
    assert hand_evidence.schema_problems(doc, "hand-tables") == []


def a_camera(monkeypatch, tmp_path, tables) -> Path:
    """A made-up camera's tables file holding `tables`, in a data folder of the test's own."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    (tmp_path / "evidence").mkdir()
    p = datafiles.hand_tables_file(CAM)
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"camera": CAM, "LIMIT_PAIRS": tables}), encoding="utf-8")
    return p


PAIR = {"upper": "global:0x0002", "lower_moves_upper": True}


def test_a_limit_pairs_table_reads_as_the_file_has_it(monkeypatch, tmp_path):
    """LIMIT_PAIRS read as the file has it, by the lower limit's key; a camera without the table has it empty."""
    a_camera(monkeypatch, tmp_path, {"global:0x0001": PAIR, "global:0x0003": {"upper": "global:0x0004"}})
    assert hand_tables.load(CAM).LIMIT_PAIRS == {"global:0x0001": PAIR, "global:0x0003": {"upper": "global:0x0004"}}
    assert hand_tables.empty()["LIMIT_PAIRS"] == {}


@pytest.mark.parametrize("table, words", [
    ([PAIR], "LIMIT_PAIRS is not in its shape: the table is an array, not an object"),
    ({"global:0x0001": "global:0x0002"}, "'global:0x0001' is a string, not an object"),
    ({"global:0x0001": {"lower_moves_upper": True}}, "'global:0x0001' has no 'upper'"),
    ({"global:0x0001": {"upper": 2}}, "'global:0x0001''s 'upper' is a whole number, not a string"),
    ({"global:0x0001": {"upper": "global:0x0001"}}, "'global:0x0001' names itself as its upper limit"),
    ({"global:0x0001": {**PAIR, "lower_moves_upper": False}}, "'lower_moves_upper' is only ever true"),
    ({"global:0x0001": {**PAIR, "upper_moves_lower": "yes"}}, "'upper_moves_lower' is a string, not true or false"),
    ({"global:0x0001": PAIR, "global:0x0003": PAIR}, "LIMIT_PAIRS holds 'global:0x0002' twice"),
])
def test_a_limit_pairs_table_out_of_its_shape_is_refused(monkeypatch, tmp_path, table, words):
    """A LIMIT_PAIRS table or entry out of its shape: refused as the file is read, in plain words, the file and the
    table named and what was expected said, before the writer trips on it."""
    p = a_camera(monkeypatch, tmp_path, table)
    with pytest.raises(hand_tables.Refused) as got:
        hand_tables.load(CAM)
    said = str(got.value)
    assert words in said and p.name in said and "mend the file by hand" in said, said
