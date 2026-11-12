"""The camera's options, nested (kit/camkit/option_tree.py): a carousel's main options with the choices on their own
axis, from pass 2's dialog and axis proofs, written into a definition as "option_tree" by kit/schema_update.py.

Run: .venv/bin/python -m pytest kit/tests/test_option_tree.py -q
Made-up proofs and settings, then the a1 II's committed definition; nothing talks to a camera.
"""
import json
import os
import shutil
import subprocess
import sys

from camkit import ROOT, definitions, option_tree as O, paths

A1 = paths.A1II


def dialog(path, index, label, context=None):
    return {"path": [path], "kind": "dialog", "index": index, "label": label, "context": context}


def axis(path, option, index, label, context=None):
    return {"path": [path], "kind": "axis", "option": option, "index": index, "label": label, "context": context}


# a made-up carousel: Area's Dot opens its sizes (the axis held on M, stepping right M, S, XL, L), Slot its three
# slots (held on Slot 1), Follow the areas again; proved a second time in a mode whose menu lacks Follow
AREA = ([dialog("Area", i, lab) for i, lab in enumerate(["Wide", "Dot: M", "Slot 1", "Follow: Wide"])]
        + [axis("Area", "Dot", i, lab) for i, lab in enumerate(["Dot: M", "Dot: S", "Dot: XL", "Dot: L"])]
        + [axis("Area", "Slot 1", i, f"Slot {i + 1}") for i in range(3)]
        + [axis("Area", "Follow", i, lab) for i, lab in enumerate(["Follow: Wide", "Follow: DotS", "Follow: Dot XL"])]
        + [dialog("Area", i, lab, "Movie mode") for i, lab in enumerate(["Wide", "Dot: M", "Slot 1"])]
        # a list the camera shows flat: each "Tube:" option is an option of its own
        + [dialog("Light", i, lab) for i, lab in enumerate(["Auto", "Tube: Warm", "Tube: Cool", "Temp."])]
        + [axis("Light", "Temp.", i, f"Temp.: {k} K") for i, k in enumerate([5000, 9000])])
VALUES = [[0, "Wide"], [1, "Dot: XL"], [2, "Dot: L"], [3, "Dot: M"], [4, "Dot: S"], [5, "Slot 1"], [6, "Slot 2"],
          [7, "Slot 3"], [8, "Follow: Wide"], [9, "Follow: Dot XL"], [10, "Follow: Dot S"]]


def setting(key, values, row=("Area",), **more):
    s = {"key": key, "name": key, "order": 1, "row": list(row), "row_at": [0] * len(row), "values": values}
    s.update(more)
    return s


def test_the_rows_main_options_and_their_axes_come_from_the_proofs():
    rows = O.rows(AREA)
    assert [m.name for m in rows[("Area",)]] == ["Wide", "Dot", "Slot", "Follow"], "the context with the most options"
    dot = rows[("Area",)][1]
    assert dot.held == ("Dot: M",) and dot.subs == ("Dot: M", "Dot: S", "Dot: XL", "Dot: L"), "in the axis's order"
    assert rows[("Area",)][2].name == "Slot", "an option named by its held choice is named by what its choices share"
    assert [m.subs for m in rows[("Light",)]][:3] == [(), (), ()]
    assert O.rows([dialog("Plain", 0, "On"), dialog("Plain", 1, "Off")]) == {}, "a row with no axis is not one"


def test_a_setting_holding_the_whole_choice_gets_its_tree_in_the_cameras_order():
    got, why = O.tree(VALUES, O.rows(AREA)[("Area",)])
    assert why is None
    assert got == [
        {"label": "Wide", "value": 0},
        # the axis's order (M, S, XL, L, wrapping), from the value the setting lists first (XL)
        {"label": "Dot", "options": [[1, "XL"], [2, "L"], [3, "M"], [4, "S"]]},
        {"label": "Slot", "options": [[5, "Slot 1"], [6, "Slot 2"], [7, "Slot 3"]]},      # not a bare "1"
        {"label": "Follow", "options": [[8, "Wide"], [10, "Dot S"], [9, "Dot XL"]]},       # "DotS": a reader's slip
    ]
    assert O.shown(got) == "Wide, Dot [XL, L, M, S], Slot [Slot 1, Slot 2, Slot 3], Follow [Wide, Dot S, Dot XL]"
    # a left-over value takes the one option its label starts
    rows = O.rows([dialog("Drive", 0, "Single"), dialog("Drive", 1, "Timer(One): 5 sec"), dialog("Drive", 2, "Burst: Hi")]
                  + [axis("Drive", "Timer(One)", i, f"Timer(One): {k} sec") for i, k in enumerate([2, 5])]
                  + [axis("Drive", "Burst", i, f"Burst: {k}") for i, k in enumerate(["Lo", "Hi"])])
    got, _ = O.tree([[0, "Single"], [1, "Timer"], [2, "Burst Hi"], [3, "Burst Lo"]], rows[("Drive",)])
    assert got == [{"label": "Single", "value": 0}, {"label": "Timer", "value": 1},
                   {"label": "Burst", "options": [[2, "Hi"], [3, "Lo"]]}]


def test_what_the_camera_does_not_nest_gets_no_tree():
    rows = O.rows(AREA)
    flat = [[0, "Auto"], [1, "Tube: Warm"], [2, "Tube: Cool"], [3, "Temp."]]
    assert O.tree(flat, rows[("Light",)]) == (None, "each of its values is an option of its own on the row: the camera shows them flat")
    _, why = O.tree(VALUES[:8], rows[("Area",)])
    assert why.startswith("the row's option(s) Follow hold none of its values")
    _, why = O.tree(VALUES + [[11, "Elsewhere"]], rows[("Area",)])
    assert why == "Elsewhere match no option of the row"
    doc = {"settings": [
        setting("whole", VALUES),
        setting("light", flat, row=("Light",)),
        setting("size", [[0, "XL"], [1, "L"]], under_option="Dot"),
        setting("flat", [[0, "On: Type1"], [1, "On: Type2"], [2, "Off"]], row=("Timing",)),
        setting("nowhere", [[0, "On: Type1"], [1, "On: Type2"]], row=()),
        setting("plain", [[0, "On"], [1, "Off"]], row=("Timing",)),
    ]}
    found, why_not = O.trees(doc, AREA)
    assert list(found) == ["whole"]
    assert why_not == {
        "light": "each of its values is an option of its own on the row: the camera shows them flat",
        "size": "the choice for the option Dot (shown under it already)",
        "flat": "its row has no carousel axis in the proofs: the camera lists these options flat",
        "nowhere": "not placed on a menu row",
    }, "and nothing about a plain list with no nested look"


def test_a_value_the_option_holds_off_its_axis_gets_no_tree():
    """A value matched to an option by the option's own name ("Dot"), when the option's axis has no such choice, has
    no place in the camera's order: the setting gets no tree, and why, where tree() used to raise ValueError (and
    kit/schema_update.py with it)."""
    values = [[0, "Wide"], [1, "Dot"], [2, "Dot: XL"], [3, "Dot: L"], [4, "Dot: M"], [5, "Dot: S"], [6, "Slot 1"],
              [7, "Slot 2"], [8, "Slot 3"], [9, "Follow: Wide"], [10, "Follow: Dot XL"], [11, "Follow: Dot S"]]
    got, why = O.tree(values, O.rows(AREA)[("Area",)])
    assert got is None and why == "Dot is not on Dot's axis"


def test_a_last_proof_line_cut_short_is_left_out(tmp_path):
    """A crash while proofs.jsonl is written leaves its last line cut short: the proofs before it still read."""
    lines = [json.dumps(p) for p in AREA[:3]] + ['{"path": ["Area"], "kind": "dia']
    (tmp_path / "proofs.jsonl").write_text("\n".join(lines), encoding="utf-8")
    assert O.read_proofs(tmp_path) == AREA[:3]
    assert O.read_proofs(tmp_path / "none") == []


def test_a_setting_of_the_same_values_shares_the_tree():
    """A setting no row's proofs speak for shares the tree of one whose values are identical, in the same tab and
    group family; values only alike, another family, a row the proofs give a verdict for, or two different trees for
    the same values, share nothing."""
    tabbed = lambda key, values, row=("Area",), group="Area": setting(key, values, row, tab="Focus", group=group)          # noqa: E731
    fewer = VALUES[:8]
    doc = {"settings": [tabbed("whole", VALUES), tabbed("again", VALUES, row=()), tabbed("sub", VALUES, row=(), group="Area › Registered"),
                        tabbed("other", VALUES, row=(), group="Elsewhere"), tabbed("fewer", fewer, row=()),
                        {**tabbed("away", VALUES, row=()), "tab": "Setup"}, tabbed("light", VALUES, row=("Light",))]}
    shared_from = {}
    found, why_not = O.trees(doc, AREA, shared_from)
    assert shared_from == {"again": "whole", "sub": "whole"}
    assert found["again"] == found["whole"] == found["sub"]
    assert not {"other", "fewer", "away", "light"} & set(found), "another family or tab, fewer values, a row's own verdict"
    assert "light" in why_not
    assert O.family({"tab": "Focus", "group": "Area › Registered"}) == ("Focus", "Area")
    # two settings of those values with different trees: none to share
    doc["settings"].append(tabbed("whole2", VALUES, row=("Area2",)))
    proofs = AREA + [dialog("Area2", i, lab) for i, lab in enumerate(["Slot 1", "Wide", "Dot: M", "Follow: Wide"])] \
        + [{**p, "path": ["Area2"]} for p in AREA if p["path"] == ["Area"] and p["kind"] == "axis"]          # its options in another order
    found, _ = O.trees(doc, proofs)
    assert found["whole2"] != found["whole"] and "again" not in found


def test_the_tree_sits_after_the_values_and_goes_when_the_proofs_give_none(tmp_path):
    import schema_update as S
    s = setting("whole", VALUES, note="n")
    placed = O.with_tree(s, [{"label": "Wide", "value": 0}])
    assert list(placed) == ["key", "name", "order", "row", "row_at", "values", "option_tree", "note"]
    assert "option_tree" not in O.with_tree(placed, None)
    run = tmp_path / "kit2_pass2"
    run.mkdir()
    doc = {"settings": [setting("whole", VALUES), {**setting("gone", [[0, "a"], [1, "b"]]), "option_tree": [{"label": "a", "value": 0}]}]}
    assert S.with_option_trees(doc, run) is None, "no proofs: nothing is written, nothing taken away"
    assert "option_tree" in doc["settings"][1]
    (run / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in AREA), encoding="utf-8")
    assert S.with_option_trees(doc, run) == 1
    assert doc["settings"][0]["option_tree"][1]["label"] == "Dot" and "option_tree" not in doc["settings"][1]


def test_option_trees_command_prints_the_audit_and_writes_only_with_write(tmp_path):
    """--option-trees reads the run of the camera the kit works on (here a made-up runs folder holding the sample as
    its download, so the proofs are the definition's camera's) and prints every tree and every setting without one;
    without --write the definition is left alone."""
    run = tmp_path / A1 / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    shutil.copy(definitions.sample(definitions.load(A1)), run / "dat" / "00001_x.DAT")
    proofs = ([dialog("Focus Area", i, lab) for i, lab in enumerate(["Wide", "Zone", "Center Fix", "Spot: M", "Expand Spot", "Custom 1", "Tracking: Wide"])]
              + [axis("Focus Area", "Spot", i, f"Spot: {k}") for i, k in enumerate(["M", "S", "XS", "XL", "L"])]
              + [axis("Focus Area", "Custom 1", i, f"Custom {i + 1}") for i in range(3)]
              + [axis("Focus Area", "Tracking", i, f"Tracking: {k}") for i, k in enumerate(
                  ["Wide", "Zone", "Center Fix", "Spot XL", "Spot L", "Spot M", "Spot S", "Spot XS", "Expand Spot", "Custom 1", "Custom 2", "Custom 3"])])
    (run / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in proofs), encoding="utf-8")
    target = definitions.path(A1)
    before = target.read_bytes()
    env = {**os.environ, "CAMSET_RUNS": str(tmp_path), "CAMSET_CAMERA": A1}
    out = subprocess.run([sys.executable, str(ROOT / "kit" / "schema_update.py"), "--option-trees"], env=env,
                         capture_output=True, text=True, check=True).stdout
    assert "tree  global:0x0f46 Focus Area memory (horizontal)" in out
    assert "Spot [XL, L, M, S, XS]" in out and "Custom [Custom 1, Custom 2, Custom 3]" in out
    assert "none  global:0x0e62 Tracking start area memory (horizontal)" in out
    assert "none  global:0x0367 White Balance" in out and "not placed on a menu row" in out
    assert target.read_bytes() == before, "shown, not written"


def test_the_shipped_definition_nests_focus_area_as_the_camera_does():
    doc = definitions.load(A1)
    by_key = {s["key"]: s for s in doc["settings"]}
    fa = by_key["global:0x0f46"]
    assert O.shown(fa["option_tree"]).startswith("Wide, Zone, Center Fix, Spot [XL, L, M, S, XS], Expand Spot, Custom [")
    for s in doc["settings"]:
        if "option_tree" in s:          # every value once, one option with choices at least: the contract
            got = [n["value"] for n in s["option_tree"] if "value" in n] + [v for n in s["option_tree"] for v, _ in n.get("options", [])]
            assert sorted(got) == sorted(v for v, _ in s["values"]), s["key"]
            assert any("options" in n for n in s["option_tree"]), s["key"]
    # the camera lists these flat, whatever their labels look like
    for k in ("global:0x0367", "global:0x0485", "global:0x0e62"):
        assert "option_tree" not in by_key[k], k
    # Registered AF area's areas hold Focus Area memory's values and share its tree; its Tracking start areas hold
    # fewer, or number the Spot sizes otherwise, and share none
    for k in ("global:0x0f80", "global:0x0f82", "global:0x0f84"):
        assert by_key[k]["option_tree"] == fa["option_tree"], k
    for k in ("global:0x0e74", "global:0x0e76", "global:0x0e78", "global:0x0f8c", "global:0x0f8e", "global:0x0f90"):
        assert "option_tree" not in by_key[k], k
