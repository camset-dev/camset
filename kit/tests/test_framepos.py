"""The focus frame place prover (kit/provers/framepos_run.py) off the camera: its plan, the presses that move a frame and
put it back, how a diff of two registrations is judged and summed up (deltas only, never a value a record held), the
slot screen's lit tab measured, the slot registration's guards on a made-up camera, and the slot records the restore
check leaves out. Every definition, record and value here is made up; nothing talks to a camera."""
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
import framepos_run as F  # noqa: E402
from camkit import definitions, paths  # noqa: E402
from camkit.link import LinkError  # noqa: E402
from writer import hand_tables  # noqa: E402

LABELS = ["Wide", "Zone", "Center Fix", "Spot: XL", "Spot: L", "Spot: M", "Spot: S", "Spot: XS", "Expand Spot",
          "Custom 1", "Custom 2", "Custom 3", "Tracking: Wide", "Tracking: Zone", "Tracking: Center Fix",
          "Tracking: Spot XL", "Tracking: Spot L", "Tracking: Spot M", "Tracking: Spot S", "Tracking: Spot XS",
          "Tracking: Expand Spot", "Tracking: Custom 1", "Tracking: Custom 2", "Tracking: Custom 3"]
GRID = [[0, "Centre"], [1, "Up"], [2, "Right"], [3, "Left"], [4, "Down"], [5, "Lower right"], [6, "Lower left"],
        [7, "Upper left"], [8, "Upper right"]]
LEFT_UP = [["ms_left", 3], ["ms_up", 2]]
TAB = (158, 41, 3)                  # the lit slot tab's colour on the a1 II's slot screen


@pytest.fixture(autouse=True)
def a1_zone(monkeypatch):
    """The Zone grid's places these tests' sweeps are planned by: the a1 II's (its hand tables' ZONE, GRID above in
    another order). framepos_run reads the hand tables of the camera the kit works on, which no test names but where
    it says so."""
    monkeypatch.setattr(F, "ZONE", hand_tables.load(paths.A1II, evidence=False).ZONE)


def test_the_zone_table_is_the_active_cameras_and_without_one_the_sweep_stops(monkeypatch, tmp_path):
    """framepos_run's ZONE is the hand tables' of the camera the kit works on (writer/hand_tables.active), never the a1
    II's on another camera: a made-up camera with no hand tables file has none, and --zone-grid then stops before
    anything is read or connected; one whose file names a grid has its own."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-0X0_fw1.00")
    assert hand_tables.active().ZONE == []
    monkeypatch.setattr(F, "ZONE", hand_tables.active().ZONE)
    monkeypatch.setattr(F, "read_json", lambda path: pytest.fail("read the definition"))
    with pytest.raises(SystemExit, match="--zone-grid plans and checks its sweep by the Zone grid's places"):
        F.main(["--list", "--zone-grid"])
    p = tmp_path / "data" / "ILCE-0X0_fw1.00" / "hand_tables_ILCE-0X0_fw1.00.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"camera": "ILCE-0X0_fw1.00", "ZONE": [[0, "Centre"], [1, "Up"]]}', encoding="utf-8")
    assert hand_tables.active().ZONE == [[0, "Centre"], [1, "Up"]]


def made_up_doc() -> dict:
    """The REG table's horizontal area record (codes made up, unlike the camera's), two point records named with their
    axis, a zone grid record, one with no axis in its name, and AF Frame Move Amt's live record (codes made up)."""
    return {"settings": [
        {"key": "global:0x0a00", "name": "Registered AF area: area (horizontal)",
         "values": [[100 + i, lab] for i, lab in enumerate(LABELS)]},
        {"key": "set:0x0b10", "name": "Made-up point X (current)", "values": []},
        {"key": "set:0x0b12", "name": "Made-up point Y (current)", "values": []},
        {"key": "set:0x0b20", "name": "Made-up zone place (grid index)", "values": GRID},
        {"key": "set:0x0b30", "name": "Made-up box place", "values": []},
        {"key": "global:0x0c00", "name": "AF Frame Move Amt", "values": [[4, "Standard"], [9, "Large"]],
         "proved": {"menu": ["AF Frame Move Amt", "AF Frame Move Amt [Movie mode]"]}}]}


def index() -> dict:
    return {s["key"]: s for s in made_up_doc()["settings"]}


def tab_image(*spans) -> np.ndarray:
    img = np.zeros((480, 640, 3), np.uint8)
    for x0, x1 in spans:
        img[8:48, x0:x1] = TAB
    return img


# ---------------------------------------------------------------- the plan

def test_the_plan_takes_the_default_areas_in_order_and_never_a_frame_that_cannot_move():
    """The default is the fourteen movable areas, in their order; a zone (Zone, Tracking: Zone) moves once left and
    once up over its 3 x 3 grid, every other area three left and two up. "all" is every area but Wide and Center Fix
    and their Tracking forms; labels are matched without case, spaces or colons, in the order given; a fixed frame, or
    a label the definition does not offer, stops the plan."""
    doc = made_up_doc()
    got = F.plan(doc)
    assert [t["label"] for t in got] == list(F.DEFAULT_AREAS)
    by = {t["label"]: t for t in got}
    assert by["Spot: S"]["code"] == 106 and by["Tracking: Custom 1"]["code"] == 121
    assert by["Zone"]["moves"] == by["Tracking: Zone"]["moves"] == [["ms_left", 1], ["ms_up", 1]]
    assert by["Custom 2"]["moves"] == by["Tracking: Spot M"]["moves"] == LEFT_UP
    assert [t["label"] for t in got if t["tracking"]] == ["Tracking: Zone", "Tracking: Spot M", "Tracking: Expand Spot",
                                                          "Tracking: Custom 1"]
    every = [t["label"] for t in F.plan(doc, "all")]
    assert len(every) == 20 and not {"Wide", "Center Fix", "Tracking: Wide", "Tracking: Center Fix"} & set(every)
    assert [t["label"] for t in F.plan(doc, "tracking spot m, Zone, zone")] == ["Tracking: Spot M", "Zone"]
    for bad in ("Wide", "Tracking: Center Fix", "Spot: XXL", " , "):
        with pytest.raises(SystemExit):
            F.plan(doc, bad)
    assert F.setup_steps(True, True) == [
        ("dial", "Drive Mode Dial"), ("drive", "Drive Mode = Single Shooting"), ("dial", "Focus Mode Dial"),
        ("row", "Focus Mode = Continuous AF"), ("row", "Switch V/H AF Area = Off")]
    assert F.setup_steps(False, False) == [("row", "Switch V/H AF Area = Off")], "no AF Area Registration: no Fn hold"
    assert F.context_of(None) == "Switch V/H AF Area Off, camera level"


def test_frame_move_amt_is_set_last_in_the_setup_and_named_in_the_context():
    """--frame-move-amt Standard or Large adds AF Frame Move Amt after Switch V/H AF Area, and the context every line
    carries names it before any --context; without it the setup and the context are as they were."""
    assert F.setup_steps(False, False, "Large") == [("row", "Switch V/H AF Area = Off"), ("row", "AF Frame Move Amt = Large")]
    assert F.setup_steps(False, False) == F.setup_steps(False, False, None) == [("row", "Switch V/H AF Area = Off")]
    assert F.setup_steps(True, True, "Standard")[-2:] == [("row", "Switch V/H AF Area = Off"),
                                                          ("row", "AF Frame Move Amt = Standard")]
    assert F.context_of(None, "Standard") == "Switch V/H AF Area Off, camera level, AF Frame Move Amt Standard"
    assert F.context_of("x", "Large").endswith("AF Frame Move Amt Large, x")
    assert F.context_of("x") == "Switch V/H AF Area Off, camera level, x"


def test_every_row_step_of_the_setup_has_its_menu_path_and_option():
    """prepare looks each "row" step of setup_steps up in setup_rows: every one is there, whatever the plan and the
    option asked (a text drifting from its key would fail only on the camera, after the start download)."""
    for focus in (False, True):
        for drive in (False, True):
            for amt in (None, "Standard", "Large"):
                rows = F.setup_rows(amt)
                for kind, what in F.setup_steps(focus, drive, amt):
                    if kind == "row":
                        assert what in rows, (focus, drive, amt, what)
    assert F.setup_rows("Large")["AF Frame Move Amt = Large"] == (["AF Frame Move Amt"], "Large")
    assert F.setup_rows()["Switch V/H AF Area = Off"] == (["Switch V/H AF Area"], "Off")
    assert not any("AF Frame Move Amt" in k for k in F.setup_rows())


def test_the_option_asked_is_coded_as_the_definition_codes_it():
    """amt_code: AF Frame Move Amt's live record by its row's proof and the code its values give the option (made-up
    codes here, never hard-coded); none when the definition has no such record or names no such option."""
    assert F.amt_code(index(), "Large") == ("global:0x0c00", 9)
    assert F.amt_code(index(), "standard") == ("global:0x0c00", 4)
    assert F.amt_code(index(), "Huge") is None
    assert F.amt_code({k: v for k, v in index().items() if k != "global:0x0c00"}, "Large") is None


def table(key, values, menu, name="Made-up Row") -> dict:
    return {key: {"key": key, "name": name, "values": values, "proved": {"menu": menu}}}


@pytest.mark.parametrize("option, code", [("F11", 26), ("F1.1", 1), ('2.5"', 13), ('25"', 2), ("Option A", 5)])
def test_setting_code_names_an_option_exactly_never_its_folded_twin(option, code):
    """setting_code: the option is matched as the kit names an option from a reading (camkit.match.index_of): the
    label as written, a decimal point kept and digits compared exactly, so F1.1 is never F11 nor 2.5" 25", whichever
    comes first in the table."""
    values = [[1, "F1.1"], [26, "F11"], [2, '25"'], [13, '2.5"'], [5, "Option A"]]
    assert F.setting_code(table("global:0x0a10", values, ["Made-up Row"]), ["Made-up Row"], option) == ("global:0x0a10", code)


def test_setting_code_takes_an_exact_label_among_folded_twins_and_gives_none_for_two_exact_ones():
    """A label written exactly as the option is taken before any folding; two labels written alike name none."""
    folded = [[1, "Optlon l"], [2, "Option 1"], [3, "Option I"]]       # one under the kit's folding of 1, l and I
    assert F.setting_code(table("global:0x0a10", folded, ["Made-up Row"]), ["Made-up Row"], "Option 1") == ("global:0x0a10", 2)
    twins = [[1, "Option A"], [2, "Option A"]]
    assert F.setting_code(table("global:0x0a10", twins, ["Made-up Row"]), ["Made-up Row"], "Option A") is None


@pytest.mark.parametrize("menu, found", [
    (["Made-up Panel > Setup Row"], True), (["Made-up Panel > Setup Row [by hand]"], True),
    (["Made-up Panel > Setup Row", "Made-up Panel > Setup Row [Movie mode]"], True),
    (["Made-up Panel > Setup Row [Movie mode]"], False), (["Made-up Panel > Setup Row [by hand, no session]"], False),
    (["Made-up Panel > Setup Row [stills, as found]"], False), (["Another Panel > Setup Row"], False), ([], False)])
def test_setting_code_takes_only_a_proof_made_in_no_state_the_run_cannot_vouch_for(menu, found):
    """The record is the one whose proof names the row with no state, or "[by hand]" alone (how the proof was made, not
    a state); a proof under a mode or any other state, another row's, or a setting's name alone names none."""
    got = F.setting_code(table("global:0x0a10", [[0, "Option Z"], [1, "Manual"]], menu, name="Setup Row"),
                         ["Made-up Panel", "Setup Row"], "Manual")
    assert got == (("global:0x0a10", 1) if found else None)
    assert F.setting_code(table("global:0x0a10", [[1, "Manual"]], [], name="Setup Row"), ["Setup Row"], "Manual") is None


def test_setting_code_gives_none_when_two_records_have_the_rows_proof():
    two = {**table("global:0x0a10", [[1, "Manual"]], ["Made-up Row"]), **table("global:0x0a20", [[1, "Manual"]], ["Made-up Row"])}
    assert F.setting_code(two, ["Made-up Row"], "Manual") is None


def test_the_setup_stops_the_run_when_frame_move_amt_did_not_take(monkeypatch, tmp_path):
    """prepare sets Switch V/H AF Area, then AF Frame Move Amt, each through the menu, and downloads: a download whose
    AF Frame Move Amt record holds the asked option's code goes on; one holding another code, or holding no such record,
    fails the run before any area, the value found never said; a definition that codes no such option fails it before
    the menu is opened."""
    import afreg_run
    import mode_switch
    import prove_run
    import runner
    from camkit import camset
    from prove_run import Failed
    held = {"code": 9}
    calls = []
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: calls.append("menu"))
    monkeypatch.setattr(afreg_run, "set_setup_row", lambda cam, cycle, model, path, option: calls.append((path, option)))
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    monkeypatch.setattr(prove_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(camset, "read", lambda path: SimpleNamespace(
        get=lambda section, rid: SimpleNamespace(value=lambda: held["code"]) if (section, rid) == (0, 0x0c00) else None))
    monkeypatch.setattr(camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0c00")])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"00002_{tag}.DAT")
    run = SimpleNamespace(dir=tmp_path)
    steps = F.prepare(None, link, None, run, None, None, False, False, tmp_path / "00001_start.DAT", "Large", index())
    assert steps == ["Switch V/H AF Area = Off", "AF Frame Move Amt = Large"]
    assert calls == ["menu", (["Switch V/H AF Area"], "Off"), "menu", (["AF Frame Move Amt"], "Large")]
    assert F.jsonl.read(tmp_path / "setup.jsonl")[-1]["frame_move_amt"] == {"asked": "Large", "took": True}
    held["code"] = 4
    with pytest.raises(Failed, match="AF Frame Move Amt did not take Large through the menu") as got:
        F.prepare(None, link, None, run, None, None, False, False, tmp_path / "00001_start.DAT", "Large", index())
    assert not set("0123456789") & set(str(got.value))
    held["code"] = 9                                  # the asked code, but the download has no such record
    monkeypatch.setattr(camset, "read", lambda path: SimpleNamespace(get=lambda section, rid: None))
    with pytest.raises(Failed, match="AF Frame Move Amt did not take Large through the menu") as got:
        F.prepare(None, link, None, run, None, None, False, False, tmp_path / "00001_start.DAT", "Large", index())
    assert not set("0123456789") & set(str(got.value))
    assert F.jsonl.read(tmp_path / "setup.jsonl")[-1]["frame_move_amt"] == {"asked": "Large", "took": False}
    calls.clear()
    with pytest.raises(Failed, match="gives no code"):
        F.prepare(None, link, None, run, None, None, False, False, tmp_path / "00001_start.DAT", "Huge", index())
    assert calls == []


def test_the_frame_goes_back_as_many_presses_as_it_moved():
    """The put-back reverses each move taken, last first, as many times as it was taken (a refused press is not
    undone); left_to_send is what a put-back cut short still owes."""
    assert F.back_of(LEFT_UP) == [["ms_down", 2], ["ms_right", 3]]
    assert F.back_of([["ms_left", 1], ["ms_up", 0]]) == [["ms_right", 1]]
    assert F.back_of([]) == []
    assert F.left_to_send([["ms_down", 2], ["ms_right", 3]], [["ms_down", 2], ["ms_right", 1]]) == [["ms_right", 2]]
    assert F.left_to_send([["ms_down", 2], ["ms_right", 3]], [["ms_down", 1]]) == [["ms_down", 1], ["ms_right", 3]]
    assert F.pull_of(LEFT_UP) == {"x": -3, "y": -2} and F.pull_of(F.back_of(LEFT_UP)) == {"x": 3, "y": 2}
    assert F.say_moves(LEFT_UP) == "Left 3, Up 2" and F.say_moves([]) == "none"


# ---------------------------------------------------------------- --moves

def test_moves_are_read_in_the_order_given_whatever_their_case():
    """--moves: a direction and its presses, comma-separated, kept in the order given; the words in any case, the
    spaces around them and an empty piece ignored."""
    assert F.parse_moves("Right 1") == [["ms_right", 1]]
    assert F.parse_moves("Left 1,Up 1") == [["ms_left", 1], ["ms_up", 1]]
    assert F.parse_moves(" up 2 , LEFT 9,") == [["ms_up", 2], ["ms_left", 9]]
    assert F.parse_moves("Down 7,rIGHT 4") == [["ms_down", 7], ["ms_right", 4]]
    assert F.say_moves(F.parse_moves("down 3, left 5")) == "Down 3, Left 5"


@pytest.mark.parametrize("text,words", [
    ("", "no move"), (" , ", "no move"),
    ("Left", "is not a direction and its presses"), ("Left 1 Up 1", "is not a direction and its presses"),
    ("Left -1", "is not a direction and its presses"), ("Left 1.5", "is not a direction and its presses"),
    ("Sideways 1", "'Sideways' is not a direction: Left, Right, Up or Down"),
    ("Left 0", "0 Left presses: a direction takes one to nine"), ("Up 11", "11 Up presses: a direction takes one to nine"),
    ("Left 1,left 2", "Left is given twice"),
    ("Left 1,Right 1", "Left with Right: the put-back is the moves reversed"),
    ("down 2, Up 1", "Down with Up"), ("Right 3,Up 1,Left 1", "Right with Left")])
def test_moves_that_say_nothing_or_would_only_cancel_are_refused(text, words):
    """One to nine presses a direction, each direction once, never with its opposite (the put-back reverses the moves,
    so the two would only cancel), at least one move: anything else ends the run, the value and what is wrong said."""
    with pytest.raises(SystemExit, match=re.escape(f"framepos_run: --moves {text!r}: ")) as got:
        F.parse_moves(text)
    assert words in str(got.value)


def test_moves_given_move_every_area_but_a_zone_and_the_context_names_them():
    """moves_of and plan give --moves to every point and box area, a copy each; a zone (Zone, Tracking: Zone) keeps its
    one step each way. The context names the moves after AF Frame Move Amt and before --context, so sessions under
    other moves keep their own summary lines; without them the context is as it was."""
    right = [["ms_right", 1]]
    assert F.moves_of("Custom 1", right) == right and F.moves_of("Custom 1") == LEFT_UP
    assert F.moves_of("Zone", right) == F.moves_of("Tracking: Zone", right) == [["ms_left", 1], ["ms_up", 1]]
    F.moves_of("Spot: S", right)[0][1] = 5
    assert right == [["ms_right", 1]]
    down_left = F.parse_moves("Down 2,Left 1")
    by = {t["label"]: t["moves"] for t in F.plan(made_up_doc(), "default", down_left)}
    assert by["Custom 3"] == by["Tracking: Expand Spot"] == by["Spot: XS"] == [["ms_down", 2], ["ms_left", 1]]
    assert by["Zone"] == by["Tracking: Zone"] == [["ms_left", 1], ["ms_up", 1]]
    assert F.plan(made_up_doc(), "Custom 1, Zone", None) == F.plan(made_up_doc(), "Custom 1, Zone")
    assert F.back_of(by["Custom 3"]) == [["ms_right", 1], ["ms_up", 2]]
    assert F.context_of(None, None, right) == "Switch V/H AF Area Off, camera level, moved Right 1"
    assert F.context_of("x", "Large", down_left) == ("Switch V/H AF Area Off, camera level, AF Frame Move Amt Large, "
                                                    "moved Down 2, Left 1, x")
    assert F.context_of("x", "Large", None) == F.context_of("x", "Large")
    large, moved = F.context_of(None, "Large"), F.context_of(None, "Large", right)
    failed = {"area": "Custom 1", "code": 109, "failed": "the carousel closed"}
    assert F.summary_lines([dict(failed, context=large), dict(failed, context=moved, failed="y")]) == [
        f"Custom 1 (code 109; {large}): failed: the carousel closed", f"Custom 1 (code 109; {moved}): failed: y"]


# ---------------------------------------------------------------- judging and summing up

def changes() -> list:
    return [{"key": "set1:0x0b10", "before": 317, "after": 272},          # X: three left
            {"key": "set1:0x0b12", "before": 251, "after": 237},          # Y: two up
            {"key": "set1:0x0b20", "before": 0, "after": 7},              # Centre -> Upper left
            {"key": "set1:0x0b30", "before": 5, "after": 9},              # no axis named, and it rose
            {"key": "global:0x0d00", "before": [1, 64, 1, 9], "after": [1, 227, 0, 9]}]


def test_a_diff_is_judged_by_axis_grid_and_the_way_the_presses_went():
    """Left lowers X and Up lowers Y on the 640 x 480 grid: a record named X or Y is judged on its own axis, with its
    step a press; a zone record by its labels' places (one column left, one row up; a zone at the left edge moves up
    alone, still the presses' way); a record no name gives an axis either way the presses went; a record of several
    values lists the values that changed and is not judged. An axis no press moved says nothing."""
    items = {i["key"]: i for i in F.judged(changes(), index(), LEFT_UP)}
    x, y, z, box, many = (items[k] for k in ("set1:0x0b10", "set1:0x0b12", "set1:0x0b20", "set1:0x0b30", "global:0x0d00"))
    assert (x["axis"], x["kind"], x["delta"], x["per_press"], x["with_presses"]) == ("X", "scalar", -45, -15, True)
    assert (y["axis"], y["delta"], y["per_press"], y["with_presses"]) == ("Y", -14, -7, True)
    assert (z["kind"], z["grid"], z["with_presses"]) == ("grid", [-1, -1], True)
    assert (box["axis"], box["delta"], box["with_presses"]) == (None, 4, False) and "per_press" not in box
    assert many["kind"] == "values" and many["values"] == [{"i": 1, "delta": 163}, {"i": 2, "delta": -1}]
    assert many["with_presses"] is None
    edge = F.judged([{"key": "set2:0x0b20", "before": 3, "after": 7}], index(), [["ms_left", 1], ["ms_up", 1]])[0]
    assert edge["grid"] == [0, -1] and edge["with_presses"] is True
    wrong = F.judged([{"key": "set1:0x0b20", "before": 0, "after": 2}], index(), [["ms_left", 1], ["ms_up", 1]])[0]
    assert wrong["with_presses"] is False
    no_x = F.judged(changes()[:1], index(), [["ms_left", 0], ["ms_up", 2]])[0]
    assert no_x["with_presses"] is None and "per_press" not in no_x
    said = F.verdict(list(items.values()), LEFT_UP)
    assert said.startswith("3 records moved the way the presses went") and "1 the other way (set1:0x0b30)" in said
    assert "1 record of several values changed" in said
    assert F.verdict([], LEFT_UP).startswith("nothing changed")
    assert F.verdict([], [["ms_left", 0], ["ms_up", 0]]).startswith("no press was taken")


def test_a_right_or_down_press_is_judged_and_said_the_way_it_went():
    """--moves may take Right or Down: Right raises X and Down raises Y, judged on each record's own axis with its step
    a press; the verdict says the rule for the directions taken, X first, and the edges a frame that did not move sat
    at. Left and Up alone keep the words they always had."""
    right = [["ms_right", 2]]
    x = F.judged([{"key": "set1:0x0b10", "before": 301, "after": 327}], index(), right)[0]
    assert (x["axis"], x["kind"], x["delta"], x["per_press"], x["with_presses"]) == ("X", "scalar", 26, 13, True)
    back = F.judged([{"key": "set1:0x0b10", "before": 327, "after": 301}], index(), right)[0]
    assert back["with_presses"] is False
    y = F.judged([{"key": "set1:0x0b12", "before": 211, "after": 222}], index(), right)[0]
    assert y["with_presses"] is None and "per_press" not in y, "no press moved Y"
    z = F.judged([{"key": "set1:0x0b20", "before": 0, "after": 2}], index(), right)[0]         # Centre -> Right
    assert z["grid"] == [1, 0] and z["with_presses"] is True
    assert F.verdict([x], right) == "1 record moved the way the presses went (Right raises X)"
    down_left = [["ms_down", 1], ["ms_left", 3]]
    both = F.judged([{"key": "set1:0x0b10", "before": 301, "after": 256},
                     {"key": "set1:0x0b12", "before": 211, "after": 218}], index(), down_left)
    assert [(i["delta"], i["per_press"], i["with_presses"]) for i in both] == [(-45, -15, True), (7, 7, True)]
    assert F.verdict(both, down_left).startswith("2 records moved the way the presses went (Left lowers X, Down raises Y)")
    assert F.verdict([], right).startswith("nothing changed: the frame did not move (it sat at the right edge already)")
    assert "(it sat at the left and bottom edges already)" in F.verdict([], down_left)
    assert "(Left lowers X, Up lowers Y)" in F.verdict([x], [["ms_left", 1], ["ms_up", 0]])
    assert "(it sat at the left and top edges already)" in F.verdict([], LEFT_UP)
    t = {"label": "Custom 1", "code": 109, "moves": right}
    line = F.area_line(t, [{"key": "set1:0x0b10", "before": 301, "after": 327}], index(), [], right, [["ms_left", 2]],
                       {}, {}, back_changes=[])
    text = "\n".join(F.summary_of(line))
    assert ("Custom 1 (code 109), Right 2 asked, Right 2 taken: 1 record moved the way the presses went "
            "(Right raises X)") in text
    assert "set1:0x0b10  Made-up point X (current): +26 (+13 a press)" in text and "put back: Left 2;" in text
    for held in ("301", "327"):
        assert held not in text, held


def test_a_verdict_names_only_the_axes_and_directions_a_press_went():
    """--moves on one axis, or with a press refused: the verdict's rule and the edges a frame that did not move sat at
    name exactly the directions taken, X first, never Left or Up for a press that was not taken; Left and Up asked
    together (the default, a zone, or --moves "Left 1,Up 1") keep today's words, whichever of them was taken."""
    up = [["ms_up", 1]]
    y = F.judged([{"key": "set1:0x0b12", "before": 211, "after": 205}], index(), up)
    assert F.verdict(y, up) == "1 record moved the way the presses went (Up lowers Y)"
    assert F.verdict([], up).startswith("nothing changed: the frame did not move (it sat at the top edge already)")
    left = [["ms_left", 1]]
    x = F.judged([{"key": "set1:0x0b10", "before": 301, "after": 297}], index(), left)
    assert F.verdict(x, left) == "1 record moved the way the presses went (Left lowers X)"
    assert "(it sat at the left edge already)" in F.verdict([], left)
    refused = [["ms_right", 0], ["ms_up", 1]]                 # --moves "Right 1,Up 1", the Right refused
    y = F.judged([{"key": "set1:0x0b12", "before": 211, "after": 205}], index(), refused)
    assert F.verdict(y, refused) == "1 record moved the way the presses went (Up lowers Y)"
    assert "(it sat at the top edge already)" in F.verdict([], refused)
    assert F.verdict([], [["ms_down", 0], ["ms_left", 2]]).startswith("nothing changed: the frame did not move (it sat "
                                                                     "at the left edge already)")
    both = [["ms_right", 1], ["ms_down", 2]]
    assert F.taken_ways(both) == ["ms_right", "ms_down"] and F.taken_ways(both[::-1]) == ["ms_right", "ms_down"]
    for done in ([["ms_left", 1], ["ms_up", 0]], [["ms_left", 0], ["ms_up", 1]], [["ms_up", 2], ["ms_left", 3]], LEFT_UP):
        assert F.taken_ways(done) == ["ms_left", "ms_up"]
        assert "(it sat at the left and top edges already)" in F.verdict([], done)
    assert "(Left lowers X, Up lowers Y)" in F.verdict(y, [["ms_left", 0], ["ms_up", 1]])


def test_the_line_keeps_the_evidence_and_the_summary_says_deltas_only():
    """The line in runs/ keeps each change as the diff gives it (the run's own evidence); the summary printed and
    written names each changed key with its delta, the presses refused or answered by a notice, and whether the frame
    is back, and never a value a record held (decision 16). The summary takes the last line of each area in each
    context, its head naming the context: a step run's Standard and Large sessions both stay."""
    t = {"label": "Spot: S", "code": 106, "moves": LEFT_UP}
    sent = [{"key": "ms_left", "frame": "1.png", "screen": "shooting"},
            {"key": "ms_left", "refused": "LinkError: button not accepted"},
            {"key": "ms_up", "frame": "3.png", "screen": "notice", "notice": "Invalid operation"},
            {"key": "ms_right", "frame": "4.png", "screen": "shooting", "put_back": True}]
    done = [["ms_left", 2], ["ms_up", 1]]
    line = F.area_line(t, changes(), index(), sent, done, [["ms_down", 1], ["ms_right", 2]], {"chosen": "0.png"},
                       {"base": "5_base.DAT", "moved": "6_moved.DAT"}, back_changes=[])
    assert line["changed"][0] == {"key": "set1:0x0b10", "before": 317, "after": 272}
    assert line["back"] == {"same": True, "off": []} and line["taken"] == done
    text = "\n".join(F.summary_of(line))
    assert "set1:0x0b10  Made-up point X (current): -45 (-22.5 a press)" in text
    assert "set1:0x0b20  Made-up zone place (grid index): grid -1 column(s), -1 row(s)" in text
    assert "set1:0x0b30  Made-up box place: +4  [the other way]" in text
    assert "global:0x0d00  (not in the definition): 2 of its values changed: [1] +163, [2] -1" in text
    assert "Left refused" in text and "Up answered by a notice (3.png)" in text
    assert "matched the first" in text
    for held in ("317", "272", "251", "237"):
        assert held not in text, held
    off = F.area_line(t, changes()[:1], index(), [], done, [], {}, {},
                      back_changes=[{"key": "set1:0x0b10", "before": 272, "after": 283}])
    assert "NOT where it was: set1:0x0b10 +11 off" in "\n".join(F.summary_of(off))
    assert "(not checked)" in "\n".join(F.summary_of(F.area_line(t, [], index(), [], done, [], {}, {})))
    failed = {"area": "Spot: S", "code": 106, "failed": "the carousel closed"}
    assert F.summary_lines([line, {"area": "Zone", "code": 101, "failed": "x"}, failed]) == [
        "Zone (code 101): failed: x", "Spot: S (code 106): failed: the carousel closed"]
    std, large = (F.context_of(None, amt) for amt in ("Standard", "Large"))
    two = F.summary_lines([dict(failed, context=std), dict(failed, context=large, failed="y"),
                           dict(failed, context=std, failed="again")])
    assert two == [f"Spot: S (code 106; {large}): failed: y", f"Spot: S (code 106; {std}): failed: again"]
    assert F.summary_of(dict(line, context=large))[0].startswith(f"Spot: S (code 106; {large}), Left 3, Up 2 asked")
    short = dict(line, put_back_short=[["ms_right", 1]])
    assert "PUT BACK SHORT: on the shooting screen with Focus Area = Spot: S, press Right 1 by hand" in \
        "\n".join(F.summary_of(short))


# ---------------------------------------------------------------- the slot screen

def test_the_lit_slot_tab_is_measured_on_the_frame():
    """Slot 1's lit tab spans x 224-273 on the a1 II's slot screen, the next ones 60 px on (kit2_frame_reg); nothing
    lit, a menu row's bar, two tabs or a tab between places measure as no slot."""
    assert F.lit_slot(tab_image((224, 274))) == "1"
    assert F.lit_slot(tab_image((284, 334))) == "2"
    assert F.lit_slot(tab_image((344, 394))) == "3"
    assert F.lit_slot(tab_image((584, 634))) == "M4"
    assert F.lit_slot(tab_image()) is None
    assert F.lit_slot(tab_image((20, 600))) is None, "a bar, not a tab"
    assert F.lit_slot(tab_image((224, 274), (284, 334))) is None
    assert F.lit_slot(tab_image((254, 304))) is None, "between slots 1 and 2"


class Cam:
    """A made-up camera: each press shows the next scripted screen ({"kind", "text", "image", "then"}: "then" is the
    kind a later look finds) or raises the scripted exception; frames are numbered."""
    def __init__(self, first: dict, script: list):
        self.now, self.script, self.pressed, self.n, self.logged = dict(first), list(script), [], 0, []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))
        CAMS.append(self)

    @property
    def frame(self):
        return SimpleNamespace(image=self.now.get("image", np.zeros((480, 640, 3), np.uint8)),
                               path=Path(f"{self.n:05d}_frame.png"))

    def read(self):
        return SimpleNamespace(kind=self.now["kind"])

    def press(self, key, **kw):
        self.pressed.append(key)
        nxt = self.script.pop(0) if self.script else self.now
        if isinstance(nxt, Exception):
            raise nxt
        self.n += 1
        self.now = dict(nxt)

    def refresh(self, tag):
        self.n += 1
        if self.now.get("then"):
            self.now = dict(self.now, kind=self.now.pop("then"))
        return self.read()


@pytest.fixture
def quick(monkeypatch):
    """No waiting, and the screen's text and its lit text are the made-up camera's own."""
    import camkit.live
    import drive
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(camkit.live, "text_of", lambda cam: cam.now.get("text", ""))
    monkeypatch.setattr(drive, "highlighted", lambda image, path: CAMS[-1].now.get("lit", ""))


CAMS = []                           # the made-up camera a test made last, whose lit text drive.highlighted reads


def test_moves_count_only_the_presses_the_camera_took(quick):
    """A press the link refuses, or one a notice answers (waited out), is recorded and not counted; a failure part way
    leaves `done` saying what was taken, so the put-back owes exactly that."""
    from prove_run import Failed
    shooting = {"kind": "shooting"}
    cam = Cam(shooting, [shooting, LinkError("press ms_left 60: button not accepted"),
                         {"kind": "notice", "text": "Invalid operation", "then": "shooting"}, shooting, shooting])
    sent, done = [], []
    F.press_moves(cam, LEFT_UP, sent, done)
    assert done == [["ms_left", 1], ["ms_up", 2]] and cam.pressed == ["ms_left"] * 3 + ["ms_up"] * 2
    assert "refused" in sent[1] and sent[2]["notice"] == "Invalid operation" and len(sent) == 5
    stuck = Cam(shooting, [shooting, {"kind": "menu", "text": "MENU Made-up Words"}])
    sent, done = [], []
    with pytest.raises(Failed, match="left the shooting screen") as got:
        F.press_moves(stuck, [["ms_left", 3]], sent, done)
    assert "Made-up" not in str(got.value) and stuck.logged[-1][1]["notice"] == "MENU Made-up Words"
    assert done == [["ms_left", 1]] and F.back_of(done) == [["ms_right", 1]]
    with pytest.raises(Failed, match="not on the shooting screen"):
        F.press_moves(Cam({"kind": "menu"}, []), LEFT_UP, [], done := [])
    assert done == [["ms_left", 0]]


def test_each_move_is_named_for_the_shooting_screen(quick):
    """The link sends no key but MENU on the shooting screen unless the caller names it for the press (decision 21):
    every multi-selector move names its own key, and no other."""
    shooting = {"kind": "shooting"}
    named = []

    class Naming(Cam):
        def press(self, key, **kw):
            named.append((key, kw.get("on_shooting")))
            super().press(key, **kw)
    F.press_moves(Naming(shooting, [shooting] * 5), LEFT_UP, [], [])
    assert named == [("ms_left", "ms_left")] * 3 + [("ms_up", "ms_up")] * 2


SLOTS = "MR Memory 1 2 3 M1 M2 M3 M4 M 1/250 F5.6 ISO AUTO AWB MENU OK"


@pytest.fixture
def menu(monkeypatch, quick):
    """The menu open on Camera Set. Memory, whatever the scan says."""
    import mode_switch
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    return {"kind": "menu", "text": "Shooting > Shooting Mode MR Camera Set. Memory", "lit": "MR Camera Set. Memory"}


def test_slot_one_is_registered_only_when_its_tab_is_measured_lit(menu):
    """Enter on the row opens the slot screen; a lit tab elsewhere is stepped to slot 1 with Left; Enter then, and
    "Registered." must follow."""
    cam = Cam(menu, [{"kind": "unknown", "text": SLOTS, "image": tab_image((284, 334))},
                     {"kind": "unknown", "text": SLOTS, "image": tab_image((224, 274))},
                     {"kind": "notice", "text": "Registered.", "then": "menu"}])
    got = F.register_slot(cam, None, None, ["Camera Set. Memory"])
    assert cam.pressed == ["enter", "left", "enter"] and got["said"] == "Registered." and len(got["frames"]) == 4


@pytest.mark.parametrize("screen,words", [
    ({"kind": "unknown", "text": SLOTS, "image": tab_image()}, "not slot 1"),
    ({"kind": "unknown", "text": SLOTS + " Format", "image": tab_image((224, 274))}, "Enter refused"),
    ({"kind": "unknown", "text": "Setting Reset Camera Settings Reset Initialize", "image": tab_image((224, 274))},
     "not the slot screen"),
    ({"kind": "menu", "text": SLOTS, "image": tab_image((224, 274))}, "Enter refused")])
def test_no_enter_on_a_slot_screen_the_guards_do_not_pass(menu, screen, words):
    """No second Enter when the lit tab measures as no slot, the screen names something never-open, the screen is not
    the slot screen, or it reads as a menu page (Enter there opens a row nobody read: drive.VOUCH_REFUSED)."""
    from prove_run import Failed
    cam = Cam(menu, [screen])
    with pytest.raises(Failed, match=words):
        F.register_slot(cam, None, None, ["Camera Set. Memory"])
    assert cam.pressed == ["enter"]


def test_no_registered_notice_fails_the_area_and_no_other_row_is_opened(menu):
    """No "Registered." after the Enter fails the area; a lit row that is not Camera Set. Memory (the scan landed
    elsewhere) is never opened."""
    from prove_run import Failed
    cam = Cam(menu, [{"kind": "unknown", "text": SLOTS, "image": tab_image((224, 274))},
                     {"kind": "menu", "text": "Made-up Setting Made-up Value"}])
    with pytest.raises(Failed, match="no \"Registered.\"") as got:
        F.register_slot(cam, None, None, ["Camera Set. Memory"])
    assert "Made-up" not in str(got.value) and cam.logged[-1][1]["notice"] == "Made-up Setting Made-up Value"
    noticed = Cam(menu, [{"kind": "notice", "text": "Made-up notice: Made-up Value"}])
    with pytest.raises(Failed, match="a notice instead of the slots") as got:
        F.register_slot(noticed, None, None, ["Camera Set. Memory"])
    assert "Made-up" not in str(got.value) and noticed.logged[-1][0] == "memory_notice"
    elsewhere = Cam(dict(menu, lit="MR Recall Camera Setting"), [])
    with pytest.raises(Failed, match="not Camera Set. Memory"):
        F.register_slot(elsewhere, None, None, ["Camera Set. Memory"])
    assert elsewhere.pressed == []


# ---------------------------------------------------------------- the restore, and the command line

def test_slot_one_must_be_filled_already_and_its_marks_are_left_out_of_the_restore_check():
    """Registering writes set1:0x023c (the filled mark), 0x11ab and 0x11ad, which no settings file sets back: the
    restore check names them and leaves them out (runner.prover_session's expected). A slot 1 the start file has
    empty is never registered: its filled mark would stay for good."""
    assert F.EXPECTED_LEFT == ("set1:0x023c", "set1:0x11ab", "set1:0x11ad") and F.FILLED[0] in F.EXPECTED_LEFT

    def file_with(mark):
        return SimpleNamespace(get=lambda section, rid: SimpleNamespace(value=lambda: mark)
                               if (section, rid) == (1, 0x023c) else None)
    assert F.slot_filled(file_with(4)) is True
    assert F.slot_filled(file_with(2)) is False
    assert F.slot_filled(SimpleNamespace(get=lambda section, rid: None)) is False


def test_list_prints_the_plan_and_a_run_needs_the_owners_word_for_camera_set_memory(capsys, monkeypatch):
    """--list prints the plan, the setup and the registration's leftovers note, touching no camera. Camera Set. Memory
    is a never-open action row: a run without --allow naming it stops before anything connects, and --allow never
    names Initialize."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)          # whichever map another test left pointed at
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("no camera in a test"))
    assert F.main(["--list", "--areas", "Zone,Tracking: Spot M"]) == 0
    out = capsys.readouterr().out
    assert "Zone (code 101): no route in pass 1's map and the axis walk; moved Left 1, Up 1, put back Down 1, Right 1" in out
    assert "Focus Mode = Continuous AF; Switch V/H AF Area = Off" in out and "AF Area Registration" not in out
    assert "set1:0x023c, set1:0x11ab, set1:0x11ad" in out and "after the put-back" in out
    assert "slot 1 must be filled in the start file already" in out
    F.main(["--list", "--areas", "Zone", "--no-check-back"])
    assert "after the put-back" not in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--allow 'Camera Set. Memory'"):
        F.main(["--areas", "Zone"])
    with pytest.raises(SystemExit, match="Initialize"):
        F.main(["--areas", "Zone", "--allow", "Camera Set. Memory", "--allow", "Initialize"])


def test_list_names_frame_move_amt_in_the_setup_and_the_run_carries_it(capsys, monkeypatch):
    """--frame-move-amt Large is set through the menu with the other setup rows, named in the context, and says how the
    step a press takes is read; a run hands it to prove; leave (the default) sets nothing."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    assert F.main(["--list", "--areas", "Spot: M", "--frame-move-amt", "Large"]) == 0
    out = capsys.readouterr().out
    assert "set through the menu first: Switch V/H AF Area = Off; AF Frame Move Amt = Large;" in out
    assert "'Switch V/H AF Area Off, camera level, AF Frame Move Amt Large'" in out
    assert "X over 3 Left presses, Y over 2 Up presses" in out and "of the point and box areas" in out
    assert "must hold Large's code 9 in global:0x0c00 (AF Frame Move Amt, as the definition codes it)" in out
    F.main(["--list", "--areas", "Spot: M"])
    out = capsys.readouterr().out
    assert "AF Frame Move Amt" not in out and "step per press" not in out
    assert not called
    assert F.main(["--areas", "Spot: M", "--frame-move-amt", "Standard", "--allow", "Camera Set. Memory"]) == 0
    (args, kw), = called
    assert kw == {"amt": "Standard"} and args[5].endswith("AF Frame Move Amt Standard")
    monkeypatch.setattr(F, "read_json", lambda path: {"settings": made_up_doc()["settings"][:-1]})
    with pytest.raises(SystemExit, match="no AF Frame Move Amt record"):
        F.main(["--list", "--areas", "Spot: M", "--frame-move-amt", "Large"])


def test_list_with_moves_names_them_and_reads_the_step_on_their_axes_only(capsys, monkeypatch):
    """--moves "Right 1" with --frame-move-amt Large: the context names both, each point or box area moves Right 1 and
    goes back Left 1, a zone keeps its own, and the step line names the axes the moves are on (X over 1 Right press,
    no Y); a run hands the moves to prove in the plan; a bad value, or a plan of zones alone, stops before anything
    connects."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    assert F.main(["--list", "--areas", "Custom 1", "--frame-move-amt", "Large", "--moves", "Right 1"]) == 0
    out = capsys.readouterr().out
    assert "'Switch V/H AF Area Off, camera level, AF Frame Move Amt Large, moved Right 1'" in out
    assert "Custom 1 (code 109): no route in pass 1's map and the axis walk; moved Right 1, put back Left 1" in out
    assert "of the point and box areas (Spot, Expand Spot, Custom): X over 1 Right press (a Zone moves" in out
    assert "Y over" not in out and "Left press" not in out
    F.main(["--list", "--areas", "Zone,Spot: S", "--frame-move-amt", "Standard", "--moves", "up 2"])
    out = capsys.readouterr().out
    assert "Zone (code 101): no route in pass 1's map and the axis walk; moved Left 1, Up 1, put back Down 1, Right 1" in out
    assert "Spot: S (code 106): no route in pass 1's map and the axis walk; moved Up 2, put back Down 2" in out
    assert "(Spot, Expand Spot, Custom): Y over 2 Up presses (a Zone" in out and "X over" not in out
    F.main(["--list", "--areas", "Custom 1", "--moves", "Right 1"])
    out = capsys.readouterr().out
    assert "moved Right 1'" in out and "step per press" not in out
    assert not called
    assert F.main(["--areas", "Custom 1", "--moves", "Right 1", "--allow", "Camera Set. Memory"]) == 0
    (args, kw), = called
    assert args[2][0]["moves"] == [["ms_right", 1]] and args[5].endswith(", moved Right 1") and kw == {"amt": None}
    with pytest.raises(SystemExit, match="--moves 'Left 1,Right 1': Left with Right"):
        F.main(["--list", "--areas", "Custom 1", "--moves", "Left 1,Right 1"])
    with pytest.raises(SystemExit, match="no area of the plan takes them"):
        F.main(["--list", "--areas", "Zone,Tracking: Zone", "--moves", "Right 1"])
    with pytest.raises(SystemExit, match="no area of the plan takes them"):
        F.main(["--list", "--zone-grid", "--moves", "Right 1"])


def test_moves_without_the_check_back_say_nothing_tells_whether_the_frame_stayed_clear(capsys, monkeypatch):
    """--moves with --no-check-back is taken, with one plain line: without the check-back nothing tells whether the
    moves kept the frame clear of the limit of its travel. Without --moves, or with the check-back, no such line."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    said = ("--moves with --no-check-back: without the check-back nothing tells whether the moves kept the frame clear "
            "of the limit of its travel")
    assert F.main(["--list", "--areas", "Custom 1", "--moves", "Right 1", "--no-check-back"]) == 0
    out = capsys.readouterr().out
    assert out.count(said) == 1 and "and after the put-back, to check it" not in out
    for argv in (["--list", "--areas", "Custom 1", "--moves", "Right 1"], ["--list", "--areas", "Custom 1",
                                                                          "--no-check-back"]):
        F.main(argv)
        assert "nothing tells whether" not in capsys.readouterr().out, argv


def test_a_zone_in_a_session_under_moves_carries_the_context_of_a_run_without_them(tmp_path, monkeypatch, capsys):
    """A zone moves by its own one-step moves, never by --moves: in a session under --moves its line carries the
    context a default run gives (zone_tag), so it sums up with a default run's Zone, while a box area's line names the
    moves; a failed zone's line too."""
    import runner
    from camkit import camset
    from prove_run import Failed
    moved, plain = F.context_of(None, "Large", [["ms_right", 1]]), F.context_of(None, "Large")
    tag, zone_tag = {"context": moved, "allowance": "a"}, {"context": plain, "allowance": "a"}
    todo = F.plan(made_up_doc(), "Zone, Custom 1, Tracking: Zone", [["ms_right", 1]])
    monkeypatch.setattr(camset, "read", lambda path: None)
    monkeypatch.setattr(F, "slot_filled", lambda cs: True)
    monkeypatch.setattr(F, "prepare", lambda *a, **k: ["setup"])

    def one_area(cam, link, hdmi, run, cycle, model, labels, axes, t, r, a, index, owed):
        if t["label"] == "Tracking: Zone":
            raise Failed("made up")
        return {"t": 1.0, "area": t["label"], "code": t["code"], "moves": t["moves"], "taken": t["moves"], "sent": [],
                "put_back": F.back_of(t["moves"]), "changed": [], "judged": [], "verdict": "v", "frames": {}, "files": {}}
    monkeypatch.setattr(F, "one_area", one_area)
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    s = SimpleNamespace(cam=None, link=None, start=tmp_path / "start.DAT")
    a = SimpleNamespace(zone_grid=False, context=None)
    out, lines = tmp_path / "framepos.jsonl", []
    F.areas(s, a, None, None, None, None, None, None, todo, {t["label"]: None for t in todo}, index(), False, False,
            out, tag, lines, "Large", zone_tag)
    got = {ln["area"]: ln["context"] for ln in F.jsonl.read(out)}
    assert got == {"Zone": plain, "Custom 1": moved, "Tracking: Zone": plain}
    assert all(ln["allowance"] == "a" for ln in lines)
    heads = F.summary_lines(F.jsonl.read(out))
    assert heads[0].startswith(f"Zone (code 101; {plain}), Left 1, Up 1 asked")
    assert any(h.startswith(f"Custom 1 (code 109; {moved}), Right 1 asked") for h in heads)
    default_zone = {"t": 0.5, "area": "Zone", "code": 101, "moves": [["ms_left", 1], ["ms_up", 1]], "taken": [],
                    "sent": [], "put_back": [], "changed": [], "judged": [], "verdict": "w", "context": plain}
    merged = F.summary_lines([default_zone] + F.jsonl.read(out))
    assert sum(h.startswith("Zone (code 101;") for h in merged) == 1, "a default run's Zone and this one sum up as one"
    lines.clear()
    out.unlink()
    F.areas(s, a, None, None, None, None, None, None, todo[:2], {t["label"]: None for t in todo}, index(), False, False,
            out, tag, lines, "Large")
    assert [ln["context"] for ln in F.jsonl.read(out)] == [moved, moved], "no zone_tag: the session's tag, as before"


# ---------------------------------------------------------------- the zone grid sweep

def zone_index() -> dict:
    """A made-up definition: the current record, a level memory, and vertical copies A and B (names as the real one's)."""
    return {k: {"key": k, "name": n, "values": GRID} for k, n in [
        ("set:0x0b00", "Zone position (current; grid index)"), ("set:0x0b02", "Zone position memory (grid index)"),
        ("set:0x0b10", "Zone position memory (vertical A, grid index, copy 1)"),
        ("set:0x0b12", "Zone position memory (vertical B, grid index, copy 1)"),
        ("set:0x0b20", "Point X (current)")]}


def test_the_sweep_visits_the_nine_places_row_by_row_with_exact_presses():
    """The route: the corner by exact presses from any place (none past an edge, so right whether the zone stops or
    wraps), then Right, Right, Down, Left, Left, Down, Right, Right over the nine places once each; the put-back is the
    net of everything pressed."""
    route = F.sweep_route()
    assert [k for k, _ in route] == [None, "ms_right", "ms_right", "ms_down", "ms_left", "ms_left", "ms_down",
                                     "ms_right", "ms_right"]
    assert [F.place_name(p) for _, p in route] == ["Upper left", "Up", "Upper right", "Right", "Centre", "Left",
                                                   "Lower left", "Down", "Lower right"]
    assert len({p for _, p in route}) == 9
    assert F.corner_moves((0, 0)) == [["ms_left", 1], ["ms_up", 1]]
    assert F.corner_moves((1, 1)) == [["ms_left", 2], ["ms_up", 2]]
    assert F.corner_moves((-1, -1)) == [] and F.corner_moves((-1, 1)) == [["ms_up", 2]]
    assert F.corner_moves(F.code_place(5)) == [["ms_left", 2], ["ms_up", 2]]       # Lower right
    done = F.corner_moves((0, 0)) + [[k, 1] for k, _ in route if k]
    assert F.net_back(done) == [["ms_left", 1], ["ms_up", 1]]
    assert F.pull_of(F.net_back(done)) == {"x": -F.pull_of(done)["x"], "y": -F.pull_of(done)["y"]}
    assert F.net_back([["ms_left", 1], ["ms_right", 1]]) == []


def test_places_are_read_from_the_codes_and_labelled_with_the_zone_names():
    assert F.zone_names()[8] == "Upper right" and F.code_place(8) == (1, -1) and F.code_place(0) == (0, 0)
    assert F.code_place(99) is None and F.place_name((9, 9)) is None
    assert [F.code_place(c) for c in (7, 1, 8, 2, 0, 3, 6, 4, 5)] == [p for _, p in F.sweep_route()]


def test_a_place_line_names_the_records_that_changed_to_its_code_in_three_groups():
    changes = [{"key": "set1:0x0b00", "before": 1, "after": 8}, {"key": "set1:0x0b02", "before": 1, "after": 8},
               {"key": "set1:0x0b10", "before": 1, "after": 8}, {"key": "set1:0x0b12", "before": 1, "after": 8},
               {"key": "set1:0x0b20", "before": 1, "after": 4}, {"key": "set1:0x0c00", "before": 1, "after": 8},
               {"key": "set2:0x0b00", "before": 1, "after": 8}, {"key": "set1:0x0d00", "before": [1, 8], "after": [8, 8]}]
    line = F.sweep_line(2, (1, -1), 8, changes, "5_zone-upper-right.DAT", zone_index())
    assert (line["n"], line["place"], line["name"], line["expected"], line["confirmed"]) == \
        (3, 8, "Upper right", "Upper right", True)
    assert line["records"] == ["set1:0x0b00", "set1:0x0b02", "set1:0x0b10", "set1:0x0b12", "set1:0x0c00"]
    assert line["groups"] == {"horizontal": ["set1:0x0b00", "set1:0x0b02", "set1:0x0c00"],
                              "vertical A": ["set1:0x0b10"], "vertical B": ["set1:0x0b12"]}
    off = F.sweep_line(2, (1, -1), 7, changes, "x.DAT", zone_index())
    assert off["confirmed"] is False and off["name"] == "Upper left" and off["expected"] == "Upper right"
    assert F.sweep_line(0, (-1, -1), None, [], "x.DAT", zone_index())["confirmed"] is False
    assert F.sweep_line(0, (-1, -1), 99, [], "x.DAT", zone_index())["name"] is None


def test_proof_lines_cover_the_current_record_and_the_vertical_copies_and_say_whether_each_holds_the_code():
    idx = zone_index()
    assert F.zone_records(idx) == ["set:0x0b00", "set:0x0b10", "set:0x0b12"]       # not the level memory, not a point
    changes = [{"key": "set1:0x0b00", "before": 7, "after": 1}, {"key": "set1:0x0b10", "before": 7, "after": 1}]
    line = F.sweep_line(1, (0, -1), 1, changes, "4_zone-up.DAT", idx)
    got = F.sweep_proofs(line, {"set:0x0b00": 1, "set:0x0b10": 1, "set:0x0b12": 4}, "3_zone-start.DAT", changes, idx,
                         {"context": "c"})
    assert [(x["record"], x["key"], x["index"], x["label"], x["applied"]) for x in got] == [
        ("set:0x0b00", "set1:0x0b00", 1, "Up", True), ("set:0x0b10", "set1:0x0b10", 1, "Up", True),
        ("set:0x0b12", "set1:0x0b12", 1, "Up", False)]
    assert got[1]["changes"] == [changes[1]] and got[0]["changes"] == [changes[0]] and "not_applied" in got[2]
    assert all(x["kind"] == "registration mirror" and x["dat"] == "4_zone-up.DAT" and x["base"] == "3_zone-start.DAT"
               and x["path"] == ["Camera Set. Memory", "Zone place"] and x["context"] == "c" for x in got)
    assert "not_applied" not in got[0]


def test_a_record_that_holds_the_code_without_changing_is_no_proof():
    """A confirmed place credits a record only when it changed to the place's code from the download before: one that
    holds the code unchanged (a copy the registration did not write, keeping what the camera had, or the first place
    when the zone began there) is not applied, a put-back by another name (docs/decisions/0016)."""
    idx = zone_index()
    changes = [{"key": "set1:0x0b00", "before": 7, "after": 1}]
    line = F.sweep_line(1, (0, -1), 1, changes, "4_zone-up.DAT", idx)
    assert line["confirmed"] and line["records"] == ["set1:0x0b00"]
    got = F.sweep_proofs(line, {"set:0x0b00": 1, "set:0x0b10": 1, "set:0x0b12": 1}, "3_zone-start.DAT", changes, idx, {})
    assert [x["applied"] for x in got] == [True, False, False]
    assert all(x["not_applied"].startswith("the record did not change to the place's code") for x in got[1:])
    first = F.sweep_line(0, (-1, -1), 7, [], "4_zone-upper-left.DAT", idx)          # began there: nothing changed
    assert first["confirmed"] and not any(x["applied"] for x in F.sweep_proofs(
        first, {"set:0x0b00": 7, "set:0x0b10": 7, "set:0x0b12": 7}, "3_zone-start.DAT", [], idx, {}))


def test_an_unconfirmed_place_writes_no_proof_line_and_applies_nothing(tmp_path):
    """A place that does not read as the route led (a press refused or answered by a notice on the way, so the
    download may still hold the start place, the camera's own: docs/decisions/0016) keeps its zone_grid.jsonl line, but
    writes no proof line and does not mark the run a proof run; sweep_proofs applies nothing for it even where a record
    holds the code it read. A confirmed place writes its proof lines and marks the run."""
    import json
    idx = zone_index()
    off = F.sweep_line(1, (0, -1), 7, [], "4_zone-up.DAT", idx)          # led to Up, reads Upper left
    assert off["confirmed"] is False
    held = {"set:0x0b00": 7, "set:0x0b10": 7, "set:0x0b12": 7}
    got = F.sweep_proofs(off, held, "3_zone-start.DAT", [], idx, {"context": "c"})
    assert got and not any(x["applied"] for x in got)
    assert all(x["not_applied"] == "the place does not read as the route led there" for x in got)
    assert F.place_written(tmp_path, off, held, "3_zone-start.DAT", [], idx, {"context": "c"}) == []
    assert not (tmp_path / "proofs.jsonl").exists() and not (tmp_path / "proof_run.json").exists()
    grid = [json.loads(x) for x in (tmp_path / "zone_grid.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(grid) == 1 and grid[0]["confirmed"] is False and grid[0]["context"] == "c"
    moved = [{"key": k, "before": 7, "after": 1} for k in ("set1:0x0b00", "set1:0x0b10", "set1:0x0b12")]
    ok = F.sweep_line(1, (0, -1), 1, moved, "4_zone-up.DAT", idx)
    wrote = F.place_written(tmp_path, ok, {"set:0x0b00": 1, "set:0x0b10": 1, "set:0x0b12": 1}, "3_zone-start.DAT",
                            moved, idx, {"context": "c"})
    assert [x["applied"] for x in wrote] == [True, True, True]
    assert len((tmp_path / "proofs.jsonl").read_text(encoding="utf-8").splitlines()) == 3
    assert (tmp_path / "proof_run.json").exists()


def test_a_run_opens_no_never_open_row_but_camera_set_memory(monkeypatch):
    """--allow naming any other row stops the run before anything connects, as memreg_run's does."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append(a[-1]) or 0)
    with pytest.raises(SystemExit, match="opens no never-open row but Camera Set. Memory"):
        F.main(["--zone-grid", "--allow", "Camera Set. Memory", "--allow", "Audio Signals"])
    assert not called
    assert F.main(["--zone-grid", "--allow", "Camera Set. Memory"]) == 0
    assert called and "the owner allowed Camera Set. Memory remotely" in called[0]


def test_list_shows_the_sweep_and_zone_grid_alone_plans_no_other_area(capsys, monkeypatch):
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("no camera in a test"))
    assert F.main(["--list", "--zone-grid"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("0 areas and the zone grid sweep") and "Spot" not in out
    assert "Upper left, Up, Upper right, Right, Centre, Left, Lower left, Down, Lower right" in out
    assert "Right, Right, Down, Left, Left, Down, Right, Right" in out and "zone-back" in out
    F.main(["--list", "--zone-grid", "--areas", "Spot: S"])
    assert capsys.readouterr().out.startswith("1 areas and the zone grid sweep")
    with pytest.raises(SystemExit, match="--allow 'Camera Set. Memory'"):
        F.main(["--zone-grid"])
