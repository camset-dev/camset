"""How far each focus frame travels (the hand table FRAME_TRAVEL, kit/writer/frames.py): each record of a frame's place
gets its axis, its other record and the frame's limits by area, a box the bounds less half its size, only where the
hand evidence shows what measured the entry; an entry that cannot take effect is said and left out whole; and the
a1 II's definition carries exactly what its hand tables say. Made-up settings where a test needs them; the a1 II's
files as shipped."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, paths  # noqa: E402
from writer import frames, hand_tables  # noqa: E402

A1 = paths.A1II


def setting(key: str, **more) -> dict:
    return {"key": key, "name": key, "scalar": True, "values": [], **more}


def made_up() -> dict:
    """A definition with a spot's place (a ranged X and Y), a box's place, its size records, and a setting whose values
    name the areas."""
    return {"settings": [
        setting("set:0x0001", range=[0, 639]), setting("set:0x0002", range=[0, 479]),
        setting("set:0x0003"), setting("set:0x0004"), setting("set:0x0010"), setting("set:0x0011"),
        setting("global:0x0020", values=[[0, "Spot: M"], [1, "Spot: S"], [2, "Custom 1"]]),
        setting("global:0x0030", frame={"axis": "x", "with": "global:0x0031", "limits": [{"areas": ["Spot: M"], "range": [0, 1]}]}),
    ]}


SPOT = {"places": [["set:0x0001", "set:0x0002"]],
        "limits": [{"areas": ["Spot: M"], "x": [80, 560], "y": [72, 408]}, {"areas": ["Spot: S"], "x": [65, 575], "y": [61, 419]}]}
BOXES = {"inside": {"x": [46, 594], "y": [42, 438]}, "sizes_tried": {"x": [402, 168], "y": [182]},
         "boxes": [{"areas": ["Custom 1"], "size": ["set:0x0011", "set:0x0010"], "places": [["set:0x0003", "set:0x0004"]]}]}
SAID = {"Spot": {"evidence": "runs kit2_x, 2026-01-02"}, "Custom": {"evidence": "runs kit2_y, 2026-01-02"}}


def test_each_place_gets_its_axis_its_other_record_and_the_limits_by_area(capsys):
    """A measured frame: each record of its place, its axis, the place's other record and every limit on its own axis,
    by area; a box: the bounds on its axis, its size record for that axis and the sizes tried; an old frame on a
    setting no entry places taken off; the evidence (here given apart, as the plain pass reads it) reaches no field."""
    doc = made_up()
    assert frames.with_frames(doc, {"Spot": SPOT, "Custom": BOXES}, SAID) == 4
    by = {s["key"]: s for s in doc["settings"]}
    assert by["set:0x0001"]["frame"] == {"axis": "x", "with": "set:0x0002", "limits": [
        {"areas": ["Spot: M"], "range": [80, 560]}, {"areas": ["Spot: S"], "range": [65, 575]}]}
    assert by["set:0x0002"]["frame"] == {"axis": "y", "with": "set:0x0001", "limits": [
        {"areas": ["Spot: M"], "range": [72, 408]}, {"areas": ["Spot: S"], "range": [61, 419]}]}
    assert by["set:0x0003"]["frame"] == {"axis": "x", "with": "set:0x0004", "limits": [
        {"areas": ["Custom 1"], "inside": [46, 594], "size": "set:0x0011", "sizes_tried": [168, 402]}]}
    assert by["set:0x0004"]["frame"] == {"axis": "y", "with": "set:0x0003", "limits": [
        {"areas": ["Custom 1"], "inside": [42, 438], "size": "set:0x0010", "sizes_tried": [182]}]}
    assert [k for k, s in by.items() if "frame" in s] == ["set:0x0001", "set:0x0002", "set:0x0003", "set:0x0004"]
    assert "kit2_" not in json.dumps(doc)
    # the ILCE-1M2's pass: the evidence put back into the entries; a box entry without sizes_tried writes none
    doc = made_up()
    tried = {k: v for k, v in BOXES.items() if k != "sizes_tried"}
    assert frames.with_frames(doc, {"Custom": {**tried, "evidence": "runs kit2_y"}}) == 2
    assert next(s for s in doc["settings"] if s["key"] == "set:0x0003")["frame"]["limits"] == [
        {"areas": ["Custom 1"], "inside": [46, 594], "size": "set:0x0011"}]
    assert "kit2_" not in json.dumps(doc)


@pytest.mark.parametrize("table, words", [
    ({"Spot": SPOT}, "nothing in the hand evidence shows what measured it"),
    ({"Spot": {**SPOT, "places": [["set:0x0001", "set:0x0099"]]}}, "the definition lacks set:0x0099"),
    ({"Spot": {**SPOT, "places": [["set:0x0001", "global:0x0020"]]}}, "global:0x0020 names values, so it holds no position"),
    ({"Spot": {**SPOT, "limits": [{"areas": ["Spot: M"], "x": [80, 700], "y": [72, 408]}]}},
     "set:0x0001's limits [80, 700] are outside its range [0, 639]"),
    ({"Spot": {**SPOT, "limits": [{"areas": ["Spot: XXL"], "x": [80, 560], "y": [72, 408]}]}},
     "no setting of the definition names the area 'Spot: XXL' as a value"),
    ({"Custom": {**BOXES, "boxes": [{**BOXES["boxes"][0], "size": ["set:0x0099", "set:0x0010"]}]}},
     "the definition lacks set:0x0099, the box's size"),
    ({"Custom": {**BOXES, "boxes": [{**BOXES["boxes"][0], "places": [["set:0x0003", "set:0x0004"], ["set:0x0004", "set:0x0003"]]}]}},
     "set:0x0004 is placed twice, once as the y of set:0x0003"),
    ({"Spot": SPOT, "Again": {**SPOT, "limits": SPOT["limits"][:1]}}, "set:0x0001 is given limits twice for 'Spot: M'"),
], ids=lambda x: x if isinstance(x, str) else None)
def test_an_entry_that_cannot_take_effect_is_said_and_left_out_whole(capsys, table, words):
    """No evidence, a record the definition lacks or that names values, a limit outside a record's range, an area no
    setting names, a size record the definition lacks, a record placed on two axes, an area given limits twice: the
    entry is printed, "not applied", and none of its places gets a frame; an entry before it still applies."""
    doc = made_up()
    said = {} if "evidence" in words else {**SAID, "Again": SAID["Spot"]}
    n = frames.with_frames(doc, table, said)
    out = capsys.readouterr().out
    assert words in out and "not applied" in out, out
    assert n == (2 if "Again" in table else 0)
    assert all("frame" not in s for s in doc["settings"] if s["key"] in ("set:0x0003", "set:0x0004", "global:0x0030"))


def test_the_a1_iis_frames_are_its_hand_tables_and_nothing_else():
    """The a1 II's public definition: each record of each FRAME_TRAVEL place carries the frame the table gives it
    (writer/frames.placed), every other setting none, so the grip-up copies, whose way of holding the camera was not
    tried, carry none; each limit within its record's range where it has one; every Focus Area option the spot's and
    the boxes' limits name is a value of the definition's Focus Area records; and each Custom box's default size, as
    the sample (written after Initialize) holds it, is one the rule was tried at, and gives, by the rule, limits within
    the bounds."""
    pub = definitions.load_public(A1)
    by = {s["key"]: s for s in pub["settings"]}
    table = hand_tables.load(A1, evidence=False).FRAME_TRAVEL
    want = {}
    for e in table.values():
        for kx, ky, lims in frames.placed(e):
            want[kx] = {"axis": "x", "with": ky, "limits": lims["x"]}
            want[ky] = {"axis": "y", "with": kx, "limits": lims["y"]}
    assert {k: s["frame"] for k, s in by.items() if "frame" in s} == want
    assert len(want) == 6 + 2 * 3 * 3 + 2
    assert not {"set:0x01c2", "set:0x01c8", "set:0x1337", "set:0x133d", "set:0x1343", "set:0x1349", "set:0x134f",
                "set:0x1355"} & set(want)
    for k, f in want.items():
        lo, hi = by[k].get("range") or (None, None)
        for lim in f["limits"]:
            span = lim.get("range") or lim["inside"]
            assert lo is None or lo <= span[0] <= span[1] <= hi, (k, lim)
    names = {lab for k in ("global:0x0f46", "global:0x0f4c", "global:0x0f52") for _, lab in by[k]["values"]}
    assert {a for f in want.values() for lim in f["limits"] for a in lim["areas"]} <= names
    cs = camset.read(definitions.sample(pub))
    boxes = table["Custom"]
    for box in boxes["boxes"]:
        size = [int.from_bytes(cs.get(1, int(k.split(":")[1], 16)).raw[:4], "little") for k in box["size"]]
        for axis, n in zip(("x", "y"), size, strict=True):
            assert n in boxes["sizes_tried"][axis], (box["areas"], axis, n)
            lo, hi = boxes["inside"][axis]
            assert lo + n / 2 <= hi - n / 2, (box["areas"], axis, n)
