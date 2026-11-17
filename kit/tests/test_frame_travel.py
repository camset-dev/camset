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
    (writer/frames.placed), every other setting none: the spot's four places (current, level, grip down, grip up),
    each Custom box's four and the box in use, each frame's limits picked by Aspect Ratio (global:0x01fe, kept in the
    memory sets as in the live settings); each limit within its record's range where it has one; every Focus Area
    option the spot's and the boxes' limits name is a value of the definition's Focus Area records; at each ratio one
    limit for each area; and each Custom box's default size, as the sample (written after Initialize) holds it, is one
    the rule was tried at for every ratio."""
    pub = definitions.load_public(A1)
    by = {s["key"]: s for s in pub["settings"]}
    table = hand_tables.load(A1, evidence=False).FRAME_TRAVEL
    want = {}
    for e in table.values():
        for kx, ky, lims in frames.placed(e):
            want[kx] = {"axis": "x", "with": ky, "by": e["by"], "limits": lims["x"]}
            want[ky] = {"axis": "y", "with": kx, "by": e["by"], "limits": lims["y"]}
    assert {k: s["frame"] for k, s in by.items() if "frame" in s} == want
    assert len(want) == 2 * 4 + 2 * 4 * 3 + 2
    ratio = by["global:0x01fe"]
    assert ratio["name"] == "Aspect Ratio" and ratio["in_sets"]
    assert ratio["values"] == [[0, "3:2"], [1, "4:3"], [2, "16:9"], [3, "1:1"]]
    for k, f in want.items():
        lo, hi = by[k].get("range") or (None, None)
        for lim in f["limits"]:
            span = lim.get("range") or lim["inside"]
            assert lo is None or lo <= span[0] <= span[1] <= hi, (k, lim)
        every = {a for lim in f["limits"] for a in lim["areas"]}
        for code in range(4):                      # one limit for each area at each ratio
            got = [a for lim in f["limits"] for a in lim["areas"]
                   if code in lim.get("when", []) or any(code in p["when"] for p in lim.get("pictures", []))]
            assert len(got) == len(set(got)) and set(got) == every, (k, code)
    names = {lab for k in ("global:0x0f46", "global:0x0f4c", "global:0x0f52") for _, lab in by[k]["values"]}
    assert {a for f in want.values() for lim in f["limits"] for a in lim["areas"]} <= names
    cs = camset.read(definitions.sample(pub))
    for box in table["Custom"]["boxes"]:
        size = [int.from_bytes(cs.get(1, int(k.split(":")[1], 16)).raw[:4], "little") for k in box["size"]]
        for axis, n in zip(("x", "y"), size, strict=True):
            assert all(n in pic["sizes_tried"][axis] for pic in table["Custom"]["pictures"]), (box["areas"], axis, n)


# every Custom box limit measured at the three default sizes (Custom 1 402 x 182, Custom 2 402 x 132, Custom 3 168 x
# 318), by Aspect Ratio's code: (X lowest, X highest, Y lowest, Y highest)
MEASURED = {
    0: {"Custom 1": (247, 393, 133, 347), "Custom 2": (247, 393, 108, 372), "Custom 3": (130, 510, 201, 279)},
    1: {"Custom 1": (238, 402, 133, 347), "Custom 2": (238, 402, 108, 372), "Custom 3": (107, 533, 201, 279)},
    2: {"Custom 1": (247, 393, 113, 367), "Custom 2": (247, 393, 83, 397), "Custom 3": (130, 510, 194, 286)},
    3: {"Custom 1": (302, 338, 133, 347), "Custom 2": (302, 338, 108, 372), "Custom 3": (126, 514, 201, 279)},
}


def test_the_custom_box_rule_gives_every_measured_limit_at_every_aspect_ratio():
    """The a1 II's Custom box rule, as its definition writes it (the bounds on the grid's whole span, each ratio's
    picture, a half rounded toward the centre: writer/frames.box_limits), gives exactly every limit the boxes were
    measured at, at their default sizes, at all four aspect ratios, for each box's records and the box in use's; the
    bounds alone (no pictures) give 3:2's only."""
    by = {s["key"]: s for s in definitions.load_public(A1)["settings"]}
    sizes = {"Custom 1": (402, 182), "Custom 2": (402, 132), "Custom 3": (168, 318)}
    first = {"Custom 1": ("set:0x1333", "set:0x1339"), "Custom 2": ("set:0x133f", "set:0x1345"),
             "Custom 3": ("set:0x134b", "set:0x1351")}
    limit = lambda k: by[k]["frame"]["limits"][0]
    for code, boxes in MEASURED.items():
        for area, want in boxes.items():
            (kx, ky), (w, h) = first[area], sizes[area]
            assert frames.box_limits(limit(kx), w, code) + frames.box_limits(limit(ky), h, code) == want, (code, area)
            assert frames.box_limits(limit("set:0x1327"), w, code) + frames.box_limits(limit("set:0x1329"), h, code) == want
    plain = {k: v for k, v in limit("set:0x1333").items() if k not in ("pictures", "grid")}
    assert frames.box_limits(plain, 402) == MEASURED[0]["Custom 1"][:2] != MEASURED[3]["Custom 1"][:2]


def test_box_limits_round_a_half_toward_the_centre_and_need_a_picture_for_the_value():
    """box_limits: the bounds on the whole span and the box's size, the picture for the value (none: None), the grid
    stretched over it and the box kept inside the picture too, each end to the nearest whole number, a half toward the
    centre."""
    lim = {"inside": [46.25, 593.75], "grid": 640, "pictures": [{"when": [0], "fraction": [1, 1]}, {"when": [3], "fraction": [2, 3]}]}
    assert frames.box_limits(lim, 402, 3) == (302, 338)             # 301.5 and 338.5, a half toward 320 each
    assert frames.box_limits(lim, 168, 3) == (126, 514)             # the picture, not the bounds, keeps it
    assert frames.box_limits(lim, 402, 0) == (247, 393)             # 247.25 and 392.75
    assert frames.box_limits(lim, 402, 1) is None


def test_limits_by_a_setting_merge_their_values_and_are_checked_against_it(capsys):
    """An entry whose limits depend on a setting ("by"): each limit for some of its values ("when"), those alike on an
    axis merged into one, "by" on the frame; a box's pictures likewise; refused, said and left out: a setting the
    definition lacks, a value it does not list, a record two entries place with limits by different settings."""
    doc = made_up()
    doc["settings"].append(setting("global:0x0040", values=[[0, "3:2"], [1, "16:9"]]))
    spot = {"places": SPOT["places"], "by": "global:0x0040", "limits": [
        {"areas": ["Spot: M"], "when": [0], "x": [80, 560], "y": [72, 408]},
        {"areas": ["Spot: M"], "when": [1], "x": [80, 560], "y": [41, 439]}]}
    boxes = {**{k: v for k, v in BOXES.items() if k != "sizes_tried"}, "by": "global:0x0040", "grid": {"x": 640, "y": 480},
             "pictures": [{"when": [0], "x": [1, 1], "y": [1, 1], "sizes_tried": {"x": [402], "y": [182]}},
                          {"when": [1], "x": [1, 1], "y": [27, 32], "sizes_tried": {"x": [402], "y": [182]}}]}
    assert frames.with_frames(doc, {"Spot": spot, "Custom": boxes}, SAID) == 4
    by = {s["key"]: s for s in doc["settings"]}
    assert by["set:0x0001"]["frame"] == {"axis": "x", "with": "set:0x0002", "by": "global:0x0040",
                                         "limits": [{"areas": ["Spot: M"], "when": [0, 1], "range": [80, 560]}]}
    assert by["set:0x0002"]["frame"]["limits"] == [{"areas": ["Spot: M"], "when": [0], "range": [72, 408]},
                                                   {"areas": ["Spot: M"], "when": [1], "range": [41, 439]}]
    assert by["set:0x0004"]["frame"]["limits"] == [{"areas": ["Custom 1"], "inside": [42, 438], "size": "set:0x0010", "grid": 480,
                                                    "pictures": [{"when": [0], "fraction": [1, 1], "sizes_tried": [182]},
                                                                 {"when": [1], "fraction": [27, 32], "sizes_tried": [182]}]}]
    assert by["set:0x0003"]["frame"]["limits"][0]["pictures"] == [{"when": [0, 1], "fraction": [1, 1], "sizes_tried": [402]}]
    for table, words in (({"Spot": {**spot, "by": "global:0x0099"}}, "the definition lacks global:0x0099"),
                         ({"Spot": {**spot, "limits": [{**spot["limits"][0], "when": [7]}]}}, "global:0x0040 has no value 7"),
                         ({"Spot": spot, "Again": {**SPOT, "limits": [{**SPOT["limits"][1]}]}}, "its limits depending once on")):
        doc = made_up()
        doc["settings"].append(setting("global:0x0040", values=[[0, "3:2"], [1, "16:9"]]))
        frames.with_frames(doc, table, {**SAID, "Again": SAID["Spot"]})
        out = capsys.readouterr().out
        assert words in out and "not applied" in out, out
