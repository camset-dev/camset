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
    tables = hand_tables.load(paths.A1II, evidence=False)
    monkeypatch.setattr(F, "ZONE", tables.ZONE)
    monkeypatch.setattr(F, "FRAME_STEPS", tables.FRAME_STEPS)


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
        # the consent the press carried to the camera's own check (LiveCamera.answer_once), used up by it
        self.consents = [*getattr(self, "consents", []), getattr(self, "answer_once", None)]
        self.answer_once = None
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
    # the slot screen reads as no known kind: its Enter carries the run's --allow as consent to the camera's own check,
    # the row's opening and the Left none (review of C1, P2)
    assert cam.consents == [None, None, "--allow 'Camera Set. Memory'"]


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
    """A made-up definition: the current record, a level memory and its horizontal copy, and the grip down and grip up
    copies (names as the real one's)."""
    return {k: {"key": k, "name": n, "values": GRID} for k, n in [
        ("set:0x0b00", "Zone position (current; grid index)"), ("set:0x0b02", "Zone position memory (grid index)"),
        ("set:0x0b04", "Zone position memory (horizontal, grid index, copy 1)"),
        ("set:0x0b10", "Zone position memory (vertical, grip down, grid index, copy 1)"),
        ("set:0x0b12", "Zone position memory (vertical, grip up, grid index, copy 1)"),
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
               {"key": "set1:0x0b04", "before": 1, "after": 8},
               {"key": "set1:0x0b10", "before": 1, "after": 8}, {"key": "set1:0x0b12", "before": 1, "after": 8},
               {"key": "set1:0x0b20", "before": 1, "after": 4}, {"key": "set1:0x0c00", "before": 1, "after": 8},
               {"key": "set2:0x0b00", "before": 1, "after": 8}, {"key": "set1:0x0d00", "before": [1, 8], "after": [8, 8]}]
    line = F.sweep_line(2, (1, -1), 8, changes, "5_zone-upper-right.DAT", zone_index())
    assert (line["n"], line["place"], line["name"], line["expected"], line["confirmed"]) == \
        (3, 8, "Upper right", "Upper right", True)
    assert line["records"] == ["set1:0x0b00", "set1:0x0b02", "set1:0x0b04", "set1:0x0b10", "set1:0x0b12", "set1:0x0c00"]
    assert line["groups"] == {"horizontal": ["set1:0x0b00", "set1:0x0b02", "set1:0x0b04", "set1:0x0c00"],
                              "vertical, grip down": ["set1:0x0b10"], "vertical, grip up": ["set1:0x0b12"]}
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


# ---------------------------------------------------------------- held vertically (--grip)

GRIP_CONTEXT = "Switch V/H AF Area = AF Point + AF Area, camera grip down"
CAROUSEL = ["Wide", "Zone", "Center Fix", "Spot: M", "Expand Spot", "Custom 1", "Tracking: Spot M"]
CAROUSEL_AXES = {"Spot": {"values": ["Spot: XS", "Spot: S", "Spot: M", "Spot: L", "Spot: XL"]},
                 "Custom 1": {"values": ["Custom 1", "Custom 2", "Custom 3"]},
                 "Tracking": {"values": ["Tracking: Spot M", "Tracking: Custom 1"]}}
# slot 1's place records of a made-up definition, named as the real one names them: the Zone's level memory and its
# two vertical copies, Custom 1's box X and Y in two copies (keys made up)
PLACE_RECORDS = [("set:0x0b40", "Zone position memory (grid index)", GRID),
                 ("set:0x0b42", "Zone position memory (vertical, grip up, grid index, copy 1)", GRID),
                 ("set:0x0b44", "Zone position memory (vertical, grip down, grid index, copy 1)", GRID),
                 ("set:0x0c20", "Custom 1 box position: X (horizontal)", []),
                 ("set:0x0c22", "Custom 1 box position: X (vertical, grip down)", []),
                 ("set:0x0c24", "Custom 1 box position: Y (horizontal)", []),
                 ("set:0x0c26", "Custom 1 box position: Y (vertical, grip down)", [])]


def grip_index() -> dict:
    doc = made_up_doc()
    doc["settings"] += [{"key": k, "name": n, "values": v} for k, n, v in PLACE_RECORDS]
    return {s["key"]: s for s in doc["settings"]}


def test_list_with_grip_prints_the_plan_and_the_context_with_the_grip(capsys, monkeypatch):
    """--list --grip down prints the plan, the setup with Switch V/H AF Area = AF Point + AF Area and the context in
    afreg_run's words, touching no camera; the presses are the level ones, and no step a press takes is read from them
    (held vertically their directions are not taken to map onto X and Y). A run hands the grip to prove."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: made_up_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    assert F.main(["--list", "--areas", "Zone,Custom 1", "--grip", "down"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"2 areas ({GRIP_CONTEXT!r}; run kit2_framepos):")
    assert "set through the menu first: Switch V/H AF Area = AF Point + AF Area;" in out and "= Off" not in out
    assert "Custom 1 (code 109): no route in pass 1's map and the axis walk; moved Left 3, Up 2, put back Down 2, Right 3" in out
    F.main(["--list", "--areas", "Custom 1", "--grip", "up", "--frame-move-amt", "Large"])
    out = capsys.readouterr().out
    assert "'Switch V/H AF Area = AF Point + AF Area, camera grip up, AF Frame Move Amt Large'" in out
    assert "must hold Large's code 9" in out and "step per press" not in out
    assert not called
    assert F.main(["--areas", "Zone,Custom 1", "--grip", "down", "--allow", "Camera Set. Memory"]) == 0
    (args, kw), = called
    assert args[0].grip == "down" and args[5] == GRIP_CONTEXT


def test_a_grip_run_sets_switch_vh_af_area_to_af_point_and_af_area(monkeypatch, tmp_path):
    """With a grip the setup puts Switch V/H AF Area on AF Point + AF Area (afreg_run.VH), each row step found in
    setup_rows; level it stays Off. The context is afreg_run's for the grip, then AF Frame Move Amt, the moves and
    --context as level."""
    for grip in ("down", "up"):
        for focus in (False, True):
            for amt in (None, "Large"):
                rows = F.setup_rows(amt, grip)
                steps = F.setup_steps(focus, focus, amt, grip)
                assert ("row", "Switch V/H AF Area = AF Point + AF Area") in steps
                assert all(what in rows for kind, what in steps if kind == "row"), (grip, focus, amt)
    assert F.setup_steps(False, False, None, None) == [("row", "Switch V/H AF Area = Off")]
    assert F.setup_rows(None, "up")["Switch V/H AF Area = AF Point + AF Area"] == (["Switch V/H AF Area"], "AF Point + AF Area")
    assert F.context_of(None, None, None, "down") == GRIP_CONTEXT
    assert F.context_of("x", "Large", [["ms_right", 1]], "up") == (
        "Switch V/H AF Area = AF Point + AF Area, camera grip up, AF Frame Move Amt Large, moved Right 1, x")
    import afreg_run
    import mode_switch
    import prove_run
    import runner
    from camkit import camset
    calls = []
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: calls.append("menu"))
    monkeypatch.setattr(afreg_run, "set_setup_row", lambda cam, cycle, model, path, option: calls.append((path, option)))
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    monkeypatch.setattr(prove_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(camset, "read", lambda path: None)
    monkeypatch.setattr(camset, "diff", lambda a, b: [])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"00002_{tag}.DAT")
    steps = F.prepare(None, link, None, SimpleNamespace(dir=tmp_path), None, None, False, False,
                      tmp_path / "00001_start.DAT", None, index(), grip="down")
    assert steps == ["Switch V/H AF Area = AF Point + AF Area"]
    assert calls == ["menu", (["Switch V/H AF Area"], "AF Point + AF Area")]


def test_a_grip_registration_across_orientation_groups_is_reported_as_it_is():
    """Held vertically a registration's diff is reported whole, never filtered to the grip's own copies: every changed
    key is in the line and named in "grip down writes:", a record the definition does not name by its key. No delta is
    judged against the presses' directions (no "the way the presses went", no step a press, no "[the other way]");
    slot 1's records are said by their definition keys. The level summary of the same changes is as it was."""
    t = {"label": "Zone", "code": 101, "moves": [["ms_left", 1], ["ms_up", 1]]}
    ch = [{"key": "set1:0x0b40", "before": 0, "after": 6}, {"key": "set1:0x0b42", "before": 0, "after": 6},
          {"key": "set1:0x0b44", "before": 0, "after": 6}, {"key": "set1:0x0d10", "before": 4100, "after": 4102}]
    done = [["ms_left", 1], ["ms_up", 1]]
    line = F.area_line(t, ch, grip_index(), [], done, [["ms_down", 1], ["ms_right", 1]], {}, {}, back_changes=[],
                       grip="down")
    assert [c["key"] for c in line["changed"]] == ["set1:0x0b40", "set1:0x0b42", "set1:0x0b44", "set1:0x0d10"]
    assert line["grip"] == "down" and line["upright"] is True
    assert all(i["with_presses"] is None and "per_press" not in i for i in line["judged"])
    assert line["verdict"] == "4 records changed"
    text = "\n".join(F.summary_of(dict(line, context=GRIP_CONTEXT)))
    assert text.startswith(f"Zone (code 101; {GRIP_CONTEXT}), Left 1, Up 1 asked, Left 1, Up 1 taken: 4 records changed")
    assert "    set:0x0b44  Zone position memory (vertical, grip down, grid index, copy 1): grid -1 column(s), +1 row(s)" in text
    assert "    set1:0x0d10" not in text and "    set:0x0d10  (not in the definition): +2" in text
    assert ("    grip down writes: Zone position memory (grid index); Zone position memory (vertical, grip up, grid index, "
            "copy 1); Zone position memory (vertical, grip down, grid index, copy 1); set:0x0d10") in text
    assert "the way the presses went" not in text and "a press)" not in text and "[the other way]" not in text
    assert "put back: Down 1, Right 1; the registration after it matched the first" in text
    assert "4100" not in text and "4102" not in text, "a delta only, never a value a record held"
    level = F.area_line(t, ch, grip_index(), [], done, [], {}, {})
    assert "grip" not in level and "writes:" not in "\n".join(F.summary_of(level))
    assert "the way the presses went" in level["verdict"] and "4 the other way" in level["verdict"]
    nothing = F.area_line(t, [], grip_index(), [], done, [], {}, {}, grip="up")
    assert "    grip up writes: nothing" in F.summary_of(nothing)
    assert nothing["verdict"].startswith("nothing changed") and "edges" not in nothing["verdict"]


def test_zone_grid_with_grip_level_is_refused_and_held_vertically_is_planned(monkeypatch, capsys):
    """The level sweep is made with Switch V/H AF Area Off, so --zone-grid --grip level is refused before anything
    connects. Held vertically (--grip down or up) the sweep is planned: the grip's setup (AF Point + AF Area) with Circ.
    of Focus Point set so the zone stops at an edge, what each registration writes, and the run handed the grip. A plan
    that would open Drive Mode's chooser held vertically (a Tracking area) needs --drive-mode leave."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    with pytest.raises(SystemExit, match="the level sweep is made with Switch V/H AF Area Off, without --grip"):
        F.main(["--zone-grid", "--grip", "level", "--allow", "Camera Set. Memory"])
    assert F.main(["--list", "--zone-grid", "--grip", "down"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("0 areas and the zone grid sweep ('Switch V/H AF Area = AF Point + AF Area, camera grip down'")
    assert ("  held grip down, Switch V/H AF Area = AF Point + AF Area: each registration writes the records every "
            "orientation writes and grip down's copies") in out
    assert "Switch V/H AF Area = AF Point + AF Area; Circ. of Focus Point = Does Not Circulate;" in out
    assert "Drive Mode" not in out, "the Zone alone opens no Drive Mode chooser"
    with pytest.raises(SystemExit, match="give --drive-mode leave"):
        F.main(["--zone-grid", "--grip", "up", "--areas", "Tracking: Spot M", "--allow", "Camera Set. Memory"])
    assert not called
    assert F.main(["--zone-grid", "--grip", "up", "--allow", "Camera Set. Memory"]) == 0
    assert F.main(["--zone-grid", "--grip", "up", "--areas", "Tracking: Spot M", "--drive-mode", "leave", "--allow",
                   "Camera Set. Memory"]) == 0
    assert [args[0].grip for args, kw in called] == ["up", "up"] and called[0][0][0].zone_target["label"] == "Zone"


class Turned:
    """A made-up camera held vertically, grip down: its shooting screen turned (read as the shooting screen, its words
    only on the frame turned upright) and the Focus Area dialog turned (read as no known kind, its title and option only
    upright); the menu pages, the slot screen and its "Registered." level (kit2_vertical, held grip up). On the shooting
    screen the multi-selector moves the chosen area's frame in directions the run does not assume; registering slot 1
    copies the frame's place into the records this orientation keeps (the Zone's and Custom 1's grip down copies)."""
    MOVE = {"ms_left": (0, 1), "ms_up": (-1, 0), "ms_right": (0, -1), "ms_down": (1, 0)}
    LEVEL_MOVE = {"ms_left": (-1, 0), "ms_up": (0, -1), "ms_right": (1, 0), "ms_down": (0, 1)}
    CODES = {(0, 0): 0, (0, -1): 1, (1, 0): 2, (-1, 0): 3, (0, 1): 4, (1, 1): 5, (-1, 1): 6, (-1, -1): 7, (1, -1): 8}

    def __init__(self, run, upright_shooting="F5.0 ISO AUTO 1/250 RAW", level=False, extra=None, writes=None):
        """level: the camera stands level (with Switch V/H AF Area = AF Point + AF Area: --grip level), every screen
        level and a registration writing the level copies; extra: more records its downloads hold; writes: "vertical"
        for a registration writing the vertical copies whatever the screens (held vertically with Vertical Display
        Off)."""
        self.run, self.upright_shooting, self.level, self.writes = run, upright_shooting, level, writes
        self.n, self.pressed, self.named, self.chosen, self.logged = 0, [], [], [], []
        self.run.log = lambda kind, **f: self.logged.append((kind, f))
        self.opt, self.val, self.area, self.places = 0, 0, None, {}
        self.slot = {"set1:0x023c": 4, "set1:0x0b40": 0, "set1:0x0b42": 0, "set1:0x0b44": 0, "set1:0x0c20": 320,
                     "set1:0x0c22": 320, "set1:0x0c24": 240, "set1:0x0c26": 240, **(extra or {})}
        self.show("shooting")
        CAMS.append(self)

    def show(self, what):
        from camkit.ocr import Line
        if what == "shooting" and self.level:
            words = "F5.0 ISO AUTO 1/250 RAW"
            self.now = {"kind": "shooting", "text": words, "lines": [Line(words, 1.0, 10, 440, 300, 20)]}
        elif what == "shooting":
            ups = [Line(self.upright_shooting, 1.0, 10, 600, 300, 20)] if self.upright_shooting else []
            self.now = {"kind": "shooting", "text": "", "upright": ups}
        elif what == "menu":
            self.now = {"kind": "menu", "text": "Shooting Mode MR Camera Set. Memory", "lit": "MR Camera Set. Memory"}
        elif what == "dialog":
            lab = CAROUSEL[self.opt]
            o = next((o for o in CAROUSEL_AXES if lab == o or lab.startswith(f"{o}:")), None)
            shown = CAROUSEL_AXES[o]["values"][self.val] if o else lab
            if self.level or getattr(self, "dialog_level", False):
                self.now = {"kind": "dialog", "text": f"Focus Area {shown}", "shown": shown,
                            "lines": [Line("Focus Area", 1.0, 10, 10, 200, 30), Line(shown, 1.0, 120, 70, 200, 30)]}
                return
            self.now = {"kind": "unknown", "text": "", "shown": shown,
                        "upright": [Line("Focus Area", 1.0, 10, 10, 200, 30), Line(shown, 1.0, 5, 60, 200, 30)]}
        elif what == "slots":
            self.now = {"kind": "unknown", "text": SLOTS, "image": tab_image((224, 274))}
        else:
            self.now = {"kind": "notice", "text": "Registered.", "then": "menu"}

    @property
    def frame(self):
        return SimpleNamespace(image=self.now.get("image", np.zeros((480, 640, 3), np.uint8)),
                               path=Path(f"{self.n:05d}_frame.png"))

    def read(self):
        return SimpleNamespace(kind=self.now["kind"])

    def refresh(self, tag):
        self.n += 1
        if self.now.get("then"):
            self.show(self.now["then"])
        return self.read()

    def press(self, key, **kw):
        self.pressed.append(key)
        self.named.append((key, kw.get("on_shooting")))
        self.answer_once = None
        kind, self.n = self.now["kind"], self.n + 1
        if kind == "shooting":
            assert key in self.MOVE and kw.get("on_shooting") == key, (key, kw)
            x, y = self.places.get(self.area, (0, 0))
            dx, dy = (self.LEVEL_MOVE if self.level else self.MOVE)[key]
            self.places[self.area] = (x + dx, y + dy)
        elif kind == "menu" and key == "right":
            self.show("dialog")
        elif kind == "menu" and key == "enter":
            self.show("slots")
        elif "shown" in self.now and key in ("up", "right"):
            if key == "up":
                self.opt, self.val = (self.opt + 1) % len(CAROUSEL), 0
            else:
                self.val += 1
            self.show("dialog")
        elif "shown" in self.now and key == "enter":
            self.area = self.now["shown"]
            self.chosen.append(self.area)
            self.show("shooting")
        elif self.now.get("text") == SLOTS and key == "enter":
            x, y = self.places.get(self.area, (0, 0))
            zone, box = ("set1:0x0b40", ("set1:0x0c20", "set1:0x0c24")) if self.level and self.writes != "vertical" \
                else ("set1:0x0b44", ("set1:0x0c22", "set1:0x0c26"))
            if self.area == "Zone":
                self.slot[zone] = self.CODES[(x, y)]
            else:
                self.slot.update({box[0]: 320 + 13 * x, box[1]: 240 + 13 * y})
            self.show("registered")
        else:
            raise AssertionError(f"made-up camera: {key} on {self.now}")


@pytest.fixture
def turned(monkeypatch, quick, tmp_path):
    """A grip-down session of the made-up turned camera, every screen and download its own: the menu opened and its
    rows found at once, OCR reading only frames turned upright, a clock that moves a second each look, and downloads
    holding the slot records as they are."""
    import mode_switch
    import orient_run
    import prove_run
    import proving.screens
    import runner
    from camkit import camset, ocr
    clock = [1000.0]

    def tick():
        clock[0] += 1.0
        return clock[0]
    monkeypatch.setattr(F.time, "monotonic", tick)
    run = SimpleNamespace(dir=tmp_path)
    (tmp_path / "upright").mkdir()
    files = {}

    def opened(cam):
        cam.show("menu")
    monkeypatch.setattr(mode_switch, "open_menu", opened)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(orient_run, "menu_from_shooting", opened)
    monkeypatch.setattr(orient_run, "scan_position", lambda cam, cycle: 0)
    monkeypatch.setattr(orient_run, "go_to", lambda cam, cycle, model, j, row: 0)
    monkeypatch.setattr(orient_run, "enter_any", lambda cam, rows, i: None)
    monkeypatch.setattr(proving.screens, "vlm_option", lambda cam: "")
    monkeypatch.setattr(prove_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: cam.show("shooting"))
    run.upright_reads = []

    def read(paths):
        """A frame turned upright reads as the screen's upright lines (each such read kept), a frame as it is as its
        level lines."""
        run.upright_reads += [Path(p).name for p in paths if "_upright" in Path(p).name]
        return {p: CAMS[-1].now.get("upright" if "_upright" in Path(p).name else "lines", []) for p in paths}
    monkeypatch.setattr(ocr, "read", read)
    monkeypatch.setattr(camset, "read", lambda path: files[Path(path).name])
    monkeypatch.setattr(camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a.get(k), after=b.get(k))
                                                      for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)])
    monkeypatch.setattr(F, "slot_filled", lambda cs: True)
    monkeypatch.setattr(F, "prepare", lambda *a, **k: ["Switch V/H AF Area = AF Point + AF Area"])

    def session(cls=None, **kw):
        cam = (cls or Turned)(run, **kw)

        def download(tag):
            p = tmp_path / f"{cam.n:05d}_{tag}.DAT"
            files[p.name] = Download(cam.slot)
            return p
        files["00000_start.DAT"] = Download(cam.slot)
        return cam, SimpleNamespace(cam=cam, link=SimpleNamespace(download=download), start=tmp_path / "00000_start.DAT")
    return run, session


class Download(dict):
    """A made-up download: its records by key, and each record as camset's get(section, id) gives it, so
    prove_run.held_value reads it as it reads a settings file."""
    def get(self, *args):
        if len(args) == 2 and isinstance(args[0], int):
            section, rid = args
            key = f"global:0x{rid:04x}" if section == 0 else f"set{section}:0x{rid:04x}"
            return SimpleNamespace(value=lambda: self[key]) if key in self else None
        return super().get(*args)


def grip_areas(run, s, labels: str, grip: str = "down", index: dict | None = None):
    """F.areas over the plan's `labels`, held as `grip` says (grip down unless told), routed by CAROUSEL; (framepos.jsonl,
    the lines)."""
    import afreg_run
    todo = F.plan(made_up_doc(), labels)
    a = SimpleNamespace(zone_grid=False, context=None, allow=["Camera Set. Memory"], check_back=True, grip=grip)
    tag = {"context": F.context_of(None, None, None, grip), "allowance": "a", "grip": grip,
           **({"upright": True} if grip != "level" else {})}
    routes = {t["label"]: afreg_run.route(t["label"], CAROUSEL, CAROUSEL_AXES) for t in todo}
    out, lines = run.dir / "framepos.jsonl", []
    F.areas(s, a, run, None, None, None, CAROUSEL, CAROUSEL_AXES, todo, routes, index or grip_index(), False, False,
            out, tag, lines, None, tag)
    return out, lines


def test_a_grip_down_run_reads_the_turned_screens_and_says_what_the_orientation_writes(turned, capsys):
    """Held grip down, a run of Zone and Custom 1 on a camera whose shooting screen and Focus Area dialog turn: each
    area chosen on the dialog read upright (afreg_run.choose_area), slot 1 registered on the level slot screen, the
    download's message waited out on the shooting screen read upright, the level presses sent (each named for the
    shooting screen), registered again, put back and checked; each line holds the records that changed, carries the
    grip, and its summary names them with the definition's names in "grip down writes:"."""
    run, session = turned
    cam, s = session()
    out, lines = grip_areas(run, s, "Zone, Custom 1")
    assert cam.chosen == ["Zone", "Custom 1"]
    moves = [k for k in cam.pressed if k.startswith("ms_")]
    assert moves == (["ms_left", "ms_up", "ms_down", "ms_right"] + ["ms_left"] * 3 + ["ms_up"] * 2 + ["ms_down"] * 2
                     + ["ms_right"] * 3)
    assert all(named == key for key, named in cam.named if key.startswith("ms_"))
    assert cam.pressed.count("enter") == 2 * (1 + 3 * 2), "per area: OK on the dialog, and three registrations"
    got = {ln["area"]: ln for ln in F.jsonl.read(out)}
    assert [c["key"] for c in got["Zone"]["changed"]] == ["set1:0x0b44"]
    assert [c["key"] for c in got["Custom 1"]["changed"]] == ["set1:0x0c22", "set1:0x0c26"]
    assert all(ln["grip"] == "down" and ln["upright"] is True and ln["context"] == GRIP_CONTEXT
               and ln["back"]["same"] for ln in got.values())
    assert any(p.name.endswith("_upright.png") for p in (run.dir / "upright").iterdir())
    said = capsys.readouterr().out
    for text in (said, "\n".join(F.summary_lines(F.jsonl.read(out)))):
        assert "    grip down writes: Zone position memory (vertical, grip down, grid index, copy 1)" in text
        assert "    grip down writes: Custom 1 box position: X (vertical, grip down); Custom 1 box position: Y (vertical, grip down)" in text
        assert "    set:0x0c22  Custom 1 box position: X (vertical, grip down): -26" in text
        assert "    set:0x0c26  Custom 1 box position: Y (vertical, grip down): +39" in text
        assert "the way the presses went" not in text and "320" not in text and "240" not in text


def test_a_turned_screen_the_upright_reader_cannot_read_stops_the_run(turned, capsys):
    """A turned shooting screen whose frame turned upright reads no text (the camera held otherwise than the grip
    says, say) cannot show the download's message gone: before any press the run waits it out, then stops with a
    message saying which check and why; no press went out, and the next area is never chosen."""
    run, session = turned
    cam, s = session(upright_shooting="")
    out, lines = grip_areas(run, s, "Zone, Custom 1")
    assert cam.chosen == ["Zone"] and not [k for k in cam.pressed if k.startswith("ms_")]
    (line,) = F.jsonl.read(out)
    assert line["area"] == "Zone" and line["grip"] == "down"
    assert "held vertically (grip down)" in line["failed"] and "reads no text" in line["failed"]
    assert "cannot be judged" in line["failed"]
    said = capsys.readouterr().out
    assert "stopping" in said and "Custom 1" not in said


def test_held_vertically_a_screen_not_read_as_the_shooting_screen_gets_no_press(quick):
    """Before each press the screen must read as the shooting screen, held vertically as level (the turned shooting
    screen reads as one: kit/tests/test_core.py's turned screens); one that does not gets no press, and with a grip the
    message says the check cannot be made on the turned screen."""
    from prove_run import Failed
    turned = Cam({"kind": "unknown"}, [])
    with pytest.raises(Failed, match=r"not on the shooting screen before Left \(unknown") as got:
        F.press_moves(turned, LEFT_UP, [], [], "down", None)
    assert "held vertically (grip down)" in str(got.value) and turned.pressed == []
    with pytest.raises(Failed) as level:
        F.press_moves(Cam({"kind": "unknown"}, []), LEFT_UP, [], [])
    assert "held vertically" not in str(level.value)


# ---------------------------------------------------------------- standing level, each orientation its own (--grip level)

LEVEL_CONTEXT = "Switch V/H AF Area = AF Point + AF Area, camera level"


def test_list_with_grip_level_prints_the_context_and_the_plan(capsys, monkeypatch):
    """--list --grip level: the context "Switch V/H AF Area = AF Point + AF Area, camera level", the setup putting the
    row on AF Point + AF Area and the level plan; no camera. No record is checked for how the camera is held, with any
    grip: the a1 II has none (0x04e2, once taken for one, held the same however the camera was held)."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    doc = {"settings": list(grip_index().values())}
    monkeypatch.setattr(F, "read_json", lambda path: doc)
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("no camera in a test"))
    assert F.main(["--list", "--areas", "Zone,Custom 1", "--grip", "level"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"2 areas ({LEVEL_CONTEXT!r}; run kit2_framepos):")
    assert "set through the menu first: Switch V/H AF Area = AF Point + AF Area;" in out
    assert "Custom 1 (code 109): no route in pass 1's map and the axis walk; moved Left 3, Up 2, put back Down 2, Right 3" in out
    assert "how it is held" not in out
    for grip in ("down", "up"):
        F.main(["--list", "--areas", "Zone", "--grip", grip])
        assert "how it is held" not in capsys.readouterr().out


def test_a_level_grip_sets_the_row_like_a_vertical_one_and_says_level(monkeypatch, tmp_path):
    """--grip level puts Switch V/H AF Area on AF Point + AF Area as down and up do; its context says the camera is
    level, in the words the hand tables' ORIENTED pattern reads; down's and up's stay afreg_run's."""
    import afreg_run
    assert ("row", "Switch V/H AF Area = AF Point + AF Area") in F.setup_steps(True, True, "Large", "level")
    assert F.setup_rows(None, "level")["Switch V/H AF Area = AF Point + AF Area"] == (["Switch V/H AF Area"],
                                                                                     "AF Point + AF Area")
    assert F.context_of(None, None, None, "level") == LEVEL_CONTEXT
    assert F.context_of("x", None, None, "level") == f"{LEVEL_CONTEXT}, x"
    assert [F.context_of(None, None, None, g) for g in ("down", "up")] == [afreg_run.context_of(g, None) for g in
                                                                           ("down", "up")]
    oriented = hand_tables.load(paths.A1II, evidence=False).ORIENTED
    assert oriented.search(f"Focus Area [{LEVEL_CONTEXT}]")[1] == "level"
    import mode_switch
    import prove_run
    import runner
    from camkit import camset
    calls = []
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(afreg_run, "set_setup_row", lambda cam, cycle, model, path, option: calls.append((path, option)))
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    monkeypatch.setattr(prove_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(camset, "read", lambda path: None)
    monkeypatch.setattr(camset, "diff", lambda a, b: [])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"00002_{tag}.DAT")
    F.prepare(None, link, None, SimpleNamespace(dir=tmp_path), None, None, False, False, tmp_path / "00001_start.DAT",
              None, index(), grip="level")
    assert calls == [(["Switch V/H AF Area"], "AF Point + AF Area")]


def test_a_level_grip_run_reads_every_screen_level_and_says_what_level_writes(turned, monkeypatch, capsys):
    """--grip level on a camera standing level: each area chosen on the level dialog (afreg_run's level path), the
    shooting screen read as it is, no frame turned upright; the lines carry "grip": "level" and no "upright", and each
    area's summary ends "level writes:" with the definition's names of the level copies."""
    import afreg_run

    def choose_level(cam, cycle, model, labels, axes, i, o, v):
        cam.show("menu")
        cam.press("right")                          # Focus Area, Right: its carousel, level
        cam.opt, cam.val = i, v or 0
        cam.show("dialog")
        return {}
    monkeypatch.setattr(afreg_run, "choose_level", choose_level)
    run, session = turned
    cam, s = session(level=True)
    out, lines = grip_areas(run, s, "Zone, Custom 1", "level")
    assert cam.chosen == ["Zone", "Custom 1"]
    assert run.upright_reads == [] and not list((run.dir / "upright").iterdir())
    got = {ln["area"]: ln for ln in F.jsonl.read(out)}
    assert [c["key"] for c in got["Zone"]["changed"]] == ["set1:0x0b40"]
    assert [c["key"] for c in got["Custom 1"]["changed"]] == ["set1:0x0c20", "set1:0x0c24"]
    assert all(ln["grip"] == "level" and "upright" not in ln and ln["context"] == LEVEL_CONTEXT and ln["back"]["same"]
               for ln in got.values())
    said = capsys.readouterr().out
    for text in (said, "\n".join(F.summary_lines(F.jsonl.read(out)))):
        assert "    level writes: Zone position memory (grid index)" in text
        assert "    level writes: Custom 1 box position: X (horizontal); Custom 1 box position: Y (horizontal)" in text
        assert "    set:0x0c20  Custom 1 box position: X (horizontal): -39" in text
        assert "camera grip level" not in text and "grip level writes" not in text
        assert "the way the presses went" not in text


# ---------------------------------------------------------------- held vertically, Vertical Display Off or On

VD_KEY = "global:0x0e30"
VD_OFF_CONTEXT = f"{GRIP_CONTEXT}, Vertical Display Off"
VD_ON_CONTEXT = f"{GRIP_CONTEXT}, Vertical Display On"


def vd_index(values=([0, "On"], [1, "Off"])) -> dict:
    """grip_index with a made-up Vertical Display record, proved by the menu row as the a1 II's is (codes made up)."""
    return grip_index() | {VD_KEY: {"key": VD_KEY, "name": "Made-up display turning", "values": [list(v) for v in values],
                                    "proved": {"menu": ["Vertical Display", "Vertical Display [Movie mode]"]}}}


def choose_level(cam, cycle, model, labels, axes, i, o, v):
    """afreg_run.choose_level on the made-up camera: Focus Area, Right, its level carousel on the option."""
    cam.show("menu")
    cam.press("right")
    cam.opt, cam.val = i, v or 0
    cam.show("dialog")
    return {}


def test_vertical_display_is_read_by_its_rows_record_and_codes_never_guessed():
    """afreg_run.vertical_display: On or Off as the start download holds the record the definition proves the Vertical
    Display row writes, by the codes its values give On and Off (framepos_run.setting_code's rule); a definition
    without the record, a download without it, or a code its values name neither reads as not read, which keeps the
    portrait reading a grip run had before (the camera's own default is On), and says why; no code is said. On, and not
    read, say how a portrait screen is made upright with either eyes: turned a quarter over HDMI, resized through the
    SDK's picture, which squeezes it unturned into 640 x 480; neither says what the SDK's picture draws is unknown."""
    import afreg_run
    assert afreg_run.vertical_display(vd_index(), Download({VD_KEY: 1}))[0] == "Off"
    assert afreg_run.vertical_display(vd_index(), Download({VD_KEY: 0}))[0] == "On"
    for index, held, why in ((grip_index(), {VD_KEY: 1}, "the definition names no record"),
                             (vd_index(), {}, "the start download holds no"),
                             (vd_index(), {VD_KEY: 5}, "a code its values name neither On nor Off")):
        state, said = afreg_run.vertical_display(index, Download(held))
        assert state is None and why in said and "own default" in said and "5" not in said, said
        assert "turned a quarter over HDMI" in said and "resized through the SDK's picture" in said, said
    said = afreg_run.vertical_display(vd_index(), Download({VD_KEY: 0}))[1]
    assert said.startswith(f"Vertical Display On in the start download ({VD_KEY}): Focus Area's dialog and the shooting "
                           "screen are read in their portrait arrangement, made upright as 480 x 640")
    assert "turned a quarter over HDMI" in said and "resized through the SDK's picture" in said
    assert "squeezes it unturned into 640 x 480" in said and "not known" not in said and "as it is drawn" not in said
    assert afreg_run.vertical_display(vd_index(), Download({VD_KEY: 1}))[1] == (
        f"Vertical Display Off in the start download ({VD_KEY}): every screen stays level, read as it is")


def test_the_list_says_how_each_eyes_reads_held_vertically_and_what_the_context_adds():
    """afreg_run.vertical_plan, the line --list prints held vertically (afreg_run.py's and framepos_run.py's): the record
    Vertical Display is read from and what the context adds, On or Off; Off every screen level, On or not read the
    portrait screens made upright, turned a quarter over HDMI, resized through the SDK's picture. Nothing said standing
    level or with no grip."""
    import afreg_run
    plan = afreg_run.vertical_plan("down", vd_index())
    assert plan.startswith(f"held vertically: Vertical Display read from the start download ({VD_KEY}), the context "
                           "adding 'Vertical Display On' or 'Vertical Display Off': Off keeps every screen level, read "
                           "as it is; On, or not read, reads Focus Area's dialog and the shooting screen in their "
                           "portrait arrangement, made upright as 480 x 640")
    assert "turned a quarter over HDMI" in plan and "resized through the SDK's picture" in plan
    assert "not known" not in plan and "as it is drawn" not in plan
    bare_plan = afreg_run.vertical_plan("up", grip_index())
    assert bare_plan.startswith("held vertically: the definition names no Vertical Display record, so the context adds "
                                "nothing; ")
    assert "own default" in bare_plan and "resized through the SDK's picture" in bare_plan
    assert afreg_run.vertical_plan("level", vd_index()) == afreg_run.vertical_plan(None, vd_index()) == ""


def test_held_vertically_the_display_decides_how_screens_are_read_and_the_context_says_it():
    """Held vertically (down, up) with Vertical Display Off every screen stays level (turned None); On, or not read, the
    screens turn as before; standing level, or with no grip, Vertical Display is not read and changes nothing. The
    context ends "Vertical Display Off" or "Vertical Display On" before --context, as the start download holds it, and
    adds nothing where it was not read."""
    import afreg_run
    off, on = Download({VD_KEY: 1}), Download({VD_KEY: 0})
    assert afreg_run.screens_held("down", vd_index(), off)[:2] == (None, "Off")
    assert afreg_run.screens_held("up", vd_index(), on)[:2] == ("up", "On")
    assert afreg_run.screens_held("down", grip_index(), off)[:2] == ("down", None)
    assert afreg_run.screens_held("level", vd_index(), off) == (None, None, "")
    assert afreg_run.screens_held(None, vd_index(), off) == (None, None, "")
    assert afreg_run.context_of("down", None, "Off") == VD_OFF_CONTEXT
    assert afreg_run.context_of("up", "x", "Off") == ("Switch V/H AF Area = AF Point + AF Area, camera grip up, Vertical "
                                                      "Display Off, x")
    assert afreg_run.context_of("down", None, "On") == VD_ON_CONTEXT
    assert afreg_run.context_of("up", "x", "On") == ("Switch V/H AF Area = AF Point + AF Area, camera grip up, Vertical "
                                                     "Display On, x")
    assert afreg_run.context_of("down", None) == afreg_run.context_of("down", None, None) == GRIP_CONTEXT
    assert afreg_run.context_of("level", None, "Off") == afreg_run.context_of("level", None, "On") == LEVEL_CONTEXT
    assert F.context_of("x", "Standard", None, "down", "Off") == f"{VD_OFF_CONTEXT}, AF Frame Move Amt Standard, x"
    assert F.context_of(None, None, None, "down", "On") == VD_ON_CONTEXT
    assert F.context_of(None, None, None, "down") == GRIP_CONTEXT
    assert afreg_run.turned_of("down", "Off") is None and afreg_run.turned_of("down", "On") == "down"
    assert F.turned_of("up", "Off") is None and F.turned_of("up") == "up" and F.turned_of("level", "On") is None


def test_a_grip_proof_counts_for_the_orientation_it_names_whatever_vertical_display_was():
    """The report's row for a grip run's proof (pass2_report.row_name: the path, then the context in brackets) is read
    by the hand tables' ORIENTED pattern (kit/schema_update.py's notes on which orientation writes a record) as the
    grip it names, with Vertical Display On or Off in the context as without it; a run with no grip names none."""
    import afreg_run
    from pass2_report import row_name
    oriented = hand_tables.load(paths.A1II, evidence=False).ORIENTED
    for grip, words in (("level", "level"), ("down", "grip down"), ("up", "grip up")):
        for vertical in (None, "On", "Off"):
            for context in (afreg_run.context_of(grip, None, vertical), F.context_of(None, None, None, grip, vertical)):
                row = row_name({"path": [afreg_run.MENU], "kind": "list", "context": context})
                assert oriented.search(row)[1] == words, (grip, vertical, row)
    assert "Vertical Display Off" in afreg_run.context_of("down", None, "Off")
    assert "Vertical Display On" in afreg_run.context_of("up", None, "On") and "Vertical Display On" in F.context_of(
        None, None, None, "down", "On")
    assert oriented.search(row_name({"path": [afreg_run.MENU], "kind": "list",
                                     "context": afreg_run.context_of(None, None)})) is None


def test_held_grip_down_with_vertical_display_off_reads_every_screen_level_and_says_so(turned, monkeypatch, capsys):
    """Held grip down with Vertical Display Off in the start download: each area chosen on the level dialog
    (afreg_run's level path), the shooting screen read as it is, no frame turned upright; the registrations write grip
    down's own copies; the lines carry "grip": "down", no "upright" and the context "..., camera grip down, Vertical
    Display Off", and each area's summary ends "grip down writes:" (the workaround run of 2026-11-16 said "level")."""
    import afreg_run
    monkeypatch.setattr(afreg_run, "choose_level", choose_level)
    run, session = turned
    cam, s = session(level=True, writes="vertical", extra={VD_KEY: 1})
    out, lines = grip_areas(run, s, "Zone, Custom 1", "down", vd_index())
    assert cam.chosen == ["Zone", "Custom 1"]
    assert run.upright_reads == [] and not list((run.dir / "upright").iterdir())
    got = {ln["area"]: ln for ln in F.jsonl.read(out)}
    assert [c["key"] for c in got["Zone"]["changed"]] == ["set1:0x0b44"]
    assert [c["key"] for c in got["Custom 1"]["changed"]] == ["set1:0x0c22", "set1:0x0c26"]
    assert all(ln["grip"] == "down" and "upright" not in ln and ln["context"] == VD_OFF_CONTEXT and ln["back"]["same"]
               for ln in got.values())
    said = capsys.readouterr().out
    assert f"Vertical Display Off in the start download ({VD_KEY})" in said
    for text in (said, "\n".join(F.summary_lines(F.jsonl.read(out)))):
        assert f"Custom 1 (code 109; {VD_OFF_CONTEXT})" in text
        assert "    grip down writes: Zone position memory (vertical, grip down, grid index, copy 1)" in text
        assert "    grip down writes: Custom 1 box position: X (vertical, grip down); Custom 1 box position: Y (vertical, grip down)" in text
        assert "    set:0x0c22  Custom 1 box position: X (vertical, grip down): -39" in text
        assert "level writes" not in text and "the way the presses went" not in text


def test_held_grip_down_with_vertical_display_on_reads_the_turned_screens_as_before(turned, capsys):
    """Vertical Display On in the start download: the portrait screens read upright as a grip run read them before, the
    lines marked "upright", the context ending "Vertical Display On", and the run says it read Vertical Display On."""
    run, session = turned
    cam, s = session(extra={VD_KEY: 0})
    out, lines = grip_areas(run, s, "Zone, Custom 1", "down", vd_index())
    assert cam.chosen == ["Zone", "Custom 1"] and run.upright_reads
    assert all(ln["upright"] is True and ln["context"] == VD_ON_CONTEXT and ln["back"]["same"]
               for ln in F.jsonl.read(out))
    assert f"Vertical Display On in the start download ({VD_KEY})" in capsys.readouterr().out


def test_held_vertically_with_the_display_on_a_dialog_drawn_level_stops_the_run_saying_what_it_saw(turned, capsys):
    """Vertical Display On, where Focus Area's dialog is drawn in its portrait arrangement: a dialog drawn level is not
    guessed at. The area fails before any press, saying the upright reading found no title, what the frame read as it
    is shows (Focus Area's title, read level), which eyes the frame came from and how it was made upright (HDMI's, a
    frame of no source: turned a quarter), and that the camera's own screen must be looked at; held vertically, the run
    stops there."""
    run, session = turned
    cam, s = session(extra={VD_KEY: 0})
    cam.dialog_level = True
    out, lines = grip_areas(run, s, "Zone, Custom 1", "down", vd_index())
    assert cam.chosen == [] and not [k for k in cam.pressed if k.startswith("ms_")]
    (line,) = F.jsonl.read(out)
    assert "did not open its dialog" in line["failed"]
    assert "read as it is, the frame shows Focus Area's title" in line["failed"]
    assert "HDMI's picture, turned a quarter back upright" in line["failed"] and "not known" not in line["failed"]
    assert "look at the camera's own screen" in line["failed"]
    assert "a failed area ends the run: stopping" in capsys.readouterr().out


def portrait_dialog() -> np.ndarray:
    """A made-up portrait dialog, 480 x 640, as the camera draws Focus Area's carousel held vertically with Vertical
    Display On (kit2_pass2's 116917_right_upright.png and kit2_a1fin_framepos_edges_gripdown_vdon's 00048_right.png
    resized, side by side, 2026-11-16): its title top left (red here), the option under the cursor beneath it (green),
    the carousel strip along the bottom (blue); each colour stands for the words a reader finds there."""
    img = np.zeros((640, 480, 3), np.uint8)
    img[10:42, 10:200] = (255, 0, 0)            # the title, in orient_run.TITLE
    img[62:92, 8:80] = (0, 255, 0)              # the option, in orient_run.LABEL, at the left edge
    img[505:555, 200:420] = (0, 0, 255)         # the carousel strip
    img[600:630, 140:470] = (255, 255, 0)       # the footer: the help glyph's "?" and the keys, below the line at 586
    return img


# portrait_dialog's colours and the words a reader finds where each lies
COLOUR_WORDS = (((255, 0, 0), "Focus Area"), ((0, 255, 0), "Wide"), ((0, 0, 255), "carousel"),
                ((255, 255, 0), "? MENU Cancel OK"))


def colour_reader(paths) -> dict:
    """A made-up OCR: on a 480 x 640 frame each of portrait_dialog's colours, where it lies, as its words; any other
    frame reads nothing."""
    from PIL import Image
    from camkit.ocr import Line
    out = {}
    for p in paths:
        img = np.asarray(Image.open(p).convert("RGB")).astype(int)
        out[p] = []
        if img.shape[:2] != (640, 480):
            continue
        for colour, words in COLOUR_WORDS:
            ys, xs = np.nonzero((np.abs(img - colour) < 70).all(axis=2))
            if len(xs):
                out[p].append(Line(words, 1.0, int(xs.min()), int(ys.min()), int(np.ptp(xs)), int(np.ptp(ys))))
    return out


def test_a_portrait_dialog_reads_the_same_turned_over_hdmi_or_squeezed_by_the_sdks_picture(monkeypatch, tmp_path):
    """Held vertically with Vertical Display On the camera draws Focus Area's dialog in its portrait arrangement: HDMI
    shows it turned a quarter (anticlockwise, grip down), the SDK's picture (the OSD eyes: a frame of source "osd")
    unturned but squeezed into its 640 x 480 (2026-11-16). orient_run.upright makes either the same 480 x 640 upright
    picture, HDMI's turned back and the SDK's resized, never turned, so the title and the option read alike and
    open_row finds the dialog; turned, the squeezed frame read no title (the run of 2026-11-16 stopped so)."""
    import orient_run
    from PIL import Image
    from camkit import ocr
    from camkit.frames import Frame
    monkeypatch.setattr(ocr, "read", colour_reader)
    for name in ("menu_from_shooting", "enter_any"):
        monkeypatch.setattr(orient_run, name, lambda *a: None)
    monkeypatch.setattr(orient_run, "scan_position", lambda cam, cycle: 0)
    monkeypatch.setattr(orient_run, "go_to", lambda cam, cycle, model, j, row: 0)
    portrait, k = portrait_dialog(), orient_run.GRIPS["down"]
    squeezed = np.asarray(Image.fromarray(portrait).resize((640, 480), Image.LANCZOS))
    frames = {"hdmi": Frame(np.ascontiguousarray(np.rot90(portrait, 1)), 0.0, tmp_path / "00001_right.png", "hdmi"),
              "osd": Frame(squeezed, 0.0, tmp_path / "00048_right.png", "osd")}
    assert orient_run.squeezed(frames["osd"]) and not orient_run.squeezed(frames["hdmi"])
    assert not orient_run.squeezed(SimpleNamespace(image=squeezed, path=tmp_path / "x.png"))
    for source, f in frames.items():
        cam = SimpleNamespace(frame=None)
        cam.press = lambda key, cam=cam, f=f: setattr(cam, "frame", f)        # Right on the row: its dialog
        orient_run.open_row(cam, None, None, "Focus Area", k, tmp_path)
        assert orient_run.reading(cam, k, tmp_path) == ("Focus Area", "Wide"), source
        # what the camera's Enter guard judges it on (camkit.live.UprightDialog): the footer's "?" below the body
        assert orient_run.dialog_reading(cam, k, tmp_path) == (
            "Focus Area", "Wide", "Focus Area Wide carousel ? MENU Cancel OK", "Focus Area Wide carousel"), source
        up = np.asarray(Image.open(tmp_path / f"{f.path.stem}_upright.png").convert("RGB")).astype(int)
        assert up.shape == (640, 480, 3) and np.abs(up - portrait).mean() < 3, source
    turned = SimpleNamespace(frame=SimpleNamespace(image=squeezed, path=tmp_path / "00049_right.png"))
    assert orient_run.reading(turned, k, tmp_path) == ("", ""), "the squeezed frame turned reads no title"


def watched_enter(cam) -> list:
    """The consent each Enter on Focus Area's dialog carried, as (its type, its words, its row, what it reads on the
    camera's frame then), or None where it carried none; recorded as the camera would judge it, then pressed as ever."""
    got, real = [], cam.press

    def press(key, **kw):
        if key == "enter" and "shown" in cam.now:
            c = getattr(cam, "answer_once", None)
            got.append(None if c is None else (type(c).__name__, c.name, c.row, c.read(cam)))
        return real(key, **kw)
    cam.press = press
    return got


def test_held_vertically_choosing_the_area_hands_the_camera_a_consent_for_its_own_dialogs_enter(turned):
    """Held grip down with Vertical Display On, afreg_run.choose_area gives the Enter on Focus Area's portrait dialog the
    camera's consent for that one press (camkit.live.UprightDialog), named for the row's own dialog read upright, once
    its own upright checks passed; what it reads is the dialog made upright (orient_run.dialog_reading). The slot
    screen's Enter keeps register_slot's own consent, and a level dialog's Enter carries none."""
    run, session = turned
    cam, s = session(extra={VD_KEY: 0})
    got = watched_enter(cam)
    out, lines = grip_areas(run, s, "Custom 1", "down", vd_index())
    assert cam.chosen == ["Custom 1"] and F.jsonl.read(out)[0]["back"]["same"]
    assert got == [("UprightDialog", "Focus Area's own dialog, read upright, held vertically (grip down)", "Focus Area",
                    ("Focus Area", "Custom 1", "Focus Area Custom 1", "Focus Area Custom 1"))]


def test_a_level_dialogs_enter_carries_no_upright_consent(turned, monkeypatch):
    """Held grip down with Vertical Display Off (every screen level), the dialog's Enter carries no consent: a level
    dialog is judged as ever."""
    import afreg_run
    monkeypatch.setattr(afreg_run, "choose_level", choose_level)
    run, session = turned
    cam, s = session(level=True, writes="vertical", extra={VD_KEY: 1})
    got = watched_enter(cam)
    grip_areas(run, s, "Custom 1", "down", vd_index())
    assert cam.chosen == ["Custom 1"] and got == [None]


class NoticeAfterOk(Turned):
    """The turned camera on which OK on Focus Area's dialog brings a screen read as no known kind (a notice drawn in
    the portrait arrangement, say), its words only on the frame made upright; MENU leaves it for the shooting screen."""
    def press(self, key, **kw):
        from camkit.ocr import Line
        if key == "enter" and "shown" in self.now:
            self.pressed.append(key)
            self.now = {"kind": "unknown", "text": "", "upright": [Line("Made-up Row: Made-up Value", 1.0, 10, 200, 300, 30)]}
            return
        if key == "menu" and self.now["kind"] == "unknown":
            self.pressed.append(key)
            self.show("shooting")
            return
        return super().press(key, **kw)


def test_held_vertically_a_screen_after_ok_that_is_not_the_shooting_screen_fails_the_area(turned, capsys):
    """Held vertically, a notice may be drawn in its portrait arrangement and read as no known kind, which the notice
    check alone would let by, and the area would then be measured as another: a screen after OK that reads neither as
    the shooting screen nor as a notice, looked at again, fails the area as a notice does, its words read upright and
    kept in the run's events alone, MENU leaving it; held vertically the run stops there."""
    run, session = turned
    cam, s = session(cls=NoticeAfterOk, extra={VD_KEY: 0})
    out, lines = grip_areas(run, s, "Zone, Custom 1", "down", vd_index())
    (line,) = F.jsonl.read(out)
    assert "is not the shooting screen" in line["failed"] and "Made-up" not in line["failed"]
    assert cam.pressed.count("menu") >= 1 and not [k for k in cam.pressed if k.startswith("ms_")]
    assert [f["notice"] for k, f in cam.logged if k == "area_notice"] == ["Made-up Row: Made-up Value"]
    said = capsys.readouterr().out
    assert "stopping" in said and "Made-up" not in said


def test_a_failed_upright_reading_says_which_eyes_and_how_the_frame_was_made_upright(monkeypatch, tmp_path):
    """afreg_run.as_it_is, what a failed upright reading of Focus Area's dialog adds: what the frame read as it is shows,
    and the frame's eyes with the way it was made upright (the SDK's picture resized to 480 x 640, HDMI's turned a
    quarter); never that what the SDK's picture draws is unknown."""
    import afreg_run
    from camkit import ocr
    from camkit.frames import Frame
    from camkit.ocr import Line
    monkeypatch.setattr(ocr, "read", lambda paths: {p: [Line("Focus Area", 1.0, 10, 10, 200, 30)] for p in paths})
    for source, way in (("osd", "the SDK's picture, resized to 480 x 640"), ("hdmi", "HDMI's picture, turned a quarter")):
        f = Frame(np.zeros((480, 640, 3), np.uint8), 0.0, tmp_path / "00048_right.png", source)
        cam = SimpleNamespace(frame=f, read=lambda: SimpleNamespace(kind="unknown"))
        said = afreg_run.as_it_is(cam)
        assert said.startswith("; read as it is, the frame shows Focus Area's title (unknown, 00048_right.png)"), said
        assert way in said and "look at the camera's own screen" in said and "not known" not in said, said


def test_held_vertically_the_portrait_shooting_screen_is_read_as_it_is(quick, tmp_path, monkeypatch):
    """afreg_run.shooting_words held vertically: the portrait shooting screen (screen.portrait_battery: Vertical
    Display On through the SDK's picture) is drawn upright, so its words are read as they are; any other frame is
    turned upright as before (HDMI turns it)."""
    import afreg_run
    from PIL import Image
    from camkit import ocr, screen
    icon = np.asarray(Image.open(Path(screen.__file__).parent / "glyphs" / "battery_portrait.png").convert("L"))
    portrait = np.zeros((480, 640, 3), np.uint8)
    portrait[3:3 + icon.shape[0], 551:551 + icon.shape[1]] = icon[..., None]
    turned_reads = []
    monkeypatch.setattr(ocr, "read", lambda paths: turned_reads.extend(paths) or {p: [] for p in paths})
    (tmp_path / "upright").mkdir()
    run = SimpleNamespace(dir=tmp_path)
    cam = Cam({"kind": "shooting", "text": "6991 J-FINE 50M", "image": portrait}, [])
    assert afreg_run.shooting_words(cam, run, "down") == "6991 J-FINE 50M" and turned_reads == []
    assert afreg_run.shooting_words(Cam({"kind": "shooting", "text": "level words"}, []), run, "down") == ""
    assert [Path(p).name for p in turned_reads] == ["00000_frame_upright.png"]


def test_an_afreg_proof_line_is_marked_upright_only_where_its_screens_were_read_turned():
    """afreg_run.proof_line: "upright" where the screens were read turned (a grip down or up, Vertical Display On or
    not read), none where they stayed level (Vertical Display Off); "grip" either way."""
    import afreg_run
    t = {"label": "Spot: S", "code": 6, "expected": {}, "own_key": "global:0x0a00", "copied": [], "other_area_keys": []}
    got = {"shown": "Spot: S", "vlm": "", "chosen_frame": "00001_a.png", "row_frame": "00002_b.png"}
    hold = {"frames": [], "said": ""}
    args = (t, got, hold, Path("00003_before.DAT"), Path("00004_after.DAT"), [], {})
    assert afreg_run.proof_line(*args, "down", [])["upright"] is True
    level = afreg_run.proof_line(*args, "down", [], upright=False)
    assert level["grip"] == "down" and "upright" not in level


# ---------------------------------------------------------------- --edges: how far each frame can travel

X, Y = "set1:0x0c20", "set1:0x0c24"                 # Custom 1's box X and Y (horizontal) in the made-up definition
CIRC_KEY = "global:0x0c10"
AMT_LIVE, AMT_COPY = "global:0x0c00", "set1:0x0c00"  # made_up_doc's AF Frame Move Amt record and a slot's copy of it
AMT_CODES = {"Standard": 4, "Large": 9}


def stepped(v: int, d: int, low: int, high: int, s: int, centre: int | None) -> int:
    """One press of the camera's frame along a record, as the registrations of 2026-11-16 show it: a whole step `s` the
    way `d` goes, stopped at an edge, and under Standard (`centre` given) stopped at the centre where it would cross it;
    under Large (no `centre`) never."""
    w = min(max(v + d * s, low), high)
    if centre is not None and min(v, w) < centre < max(v, w):
        return centre
    return w


def pressed(place: tuple, presses: list, low: tuple, high: tuple, step: tuple, centre: tuple | None) -> tuple:
    """A frame's (X, Y) after `presses` ([[key, n]]: Left and Right move X, Up and Down Y), each one `stepped`."""
    x, y = place
    for key, n in presses:
        axis, d = {"ms_right": (0, 1), "ms_left": (0, -1), "ms_down": (1, 1), "ms_up": (1, -1)}[key]
        for _ in range(n):
            if axis == 0:
                x = stepped(x, d, low[0], high[0], step[0], centre and centre[0])
            else:
                y = stepped(y, d, low[1], high[1], step[1], centre and centre[1])
    return x, y


def test_the_camera_models_reproduce_the_runs_of_2026_11_16():
    """The two models the fakes below step by, against the a1 II's own numbers for Spot: XL held grip up
    (kit2_a1fin_framepos_edges_gripup_vdon_plain under Standard, _gripup_large_plain under Large): Standard's way back
    from the far corner, Left 7 and Up 7, lands on the start at the centre; Large's first presses off the low edge are
    whole steps across the centre line, and its way back of Left 3 and Up 2, counted as if it stopped there, leaves the
    frame at (245, 226), where kit2_a1fin_framepos_where_xl found it."""
    low, high, centre = (125, 106), (515, 374), (320, 240)
    assert pressed(high, [["ms_left", 7], ["ms_up", 7]], low, high, (30, 20), centre) == (320, 240)
    assert pressed(low, [["ms_right", 1]], low, high, (30, 20), centre) == (155, 106)
    assert pressed(low, [["ms_right", 2], ["ms_down", 2]], low, high, (90, 74), None) == (305, 254)
    assert pressed(high, [["ms_left", 3], ["ms_up", 2]], low, high, (90, 74), None) == (245, 226)


def regs_of(*places, keys=(X, Y)) -> dict:
    """The six registrations of an edge measure (EDGE_TAGS: base, low, snap-h, step-h, step-v, high), each a place."""
    return {tag: dict(zip(keys, p, strict=True)) for tag, p in zip(F.EDGE_TAGS, places, strict=True)}


# a frame whose edges are 26 and 614, 33 and 447 (the centre 320, 240), 28 a press in X and 19 in Y under Standard, 56
# and 38 under Large, started at (376, 183), two steps right and three up of the centre, each registration as `pressed`
# makes it: base, the low corner (Left 40, Up 40), Right 1, Right 1 and Down 1, Down 1 and Right 40, Down 40
EDGE_GRID = {"low": (26, 33), "high": (614, 447), "centre": (320, 240), "Standard": (28, 19), "Large": (56, 38)}
GRID_REGS = regs_of((376, 183), (26, 33), (54, 33), (82, 52), (614, 71), (614, 447))
LARGE_REGS = regs_of((376, 183), (26, 33), (82, 33), (138, 71), (614, 109), (614, 447))


def test_an_edge_measure_tells_each_keys_records_their_edges_and_step_from_the_registrations():
    """Which records the horizontal keys move is what changed when Right alone was pressed off the low corner, and the
    vertical keys' what changed when Down joined it, less those: measured, never taken from a record's name or from how
    the view turns. Each record's step is the second press off the low edge, its first a whole step too, its edges the
    two corners, its centre their middle, and a push of n presses that moved n presses' worth may have stopped short of
    the edge."""
    assert F.edge_groups(GRID_REGS) == {"h": [X], "v": [Y]}
    m = F.edge_measure(GRID_REGS, 40)
    assert (m["h"]["step"][X], m["h"]["first"][X], m["h"]["low"][X], m["h"]["high"][X], m["h"]["centre"][X]) == \
        (28, 28, 26, 614, 320)
    assert (m["v"]["step"][Y], m["v"]["first"][Y], m["v"]["low"][Y], m["v"]["high"][Y], m["v"]["centre"][Y]) == \
        (19, 19, 33, 447, 240)
    assert m["h"]["short"] == [] and m["v"]["short"] == [] and m["odd"] == []
    # a view whose keys turn: Right moves Y, Down moves X; the groups and steps follow what moved
    turned = regs_of((376, 183), (26, 33), (26, 52), (54, 71), (82, 447), (614, 447))
    assert F.edge_groups(turned) == {"h": [Y], "v": [X]}
    m2 = F.edge_measure(turned, 40)
    assert m2["h"]["step"][Y] == 19 and m2["v"]["step"][X] == 28
    assert F.edge_way_back(turned["high"], turned["base"], m2) == \
        ([["ms_left", 14], ["ms_up", 11], ["ms_down", 2]], {})
    # eight presses a push: none reached the left edge, nor the far ones
    short = regs_of((376, 183), (152, 33), (180, 33), (208, 52), (432, 71), (432, 223))
    m3 = F.edge_measure(short, 8)
    assert len(m3["h"]["short"]) == 2 and len(m3["v"]["short"]) == 1 and "--edge-presses" in m3["h"]["short"][0]
    assert F.centre_of(26, 614) == 320 and F.centre_of(26, 615) is None


def test_the_way_back_under_standard_counts_on_the_centre_stop_and_says_where_no_press_reaches():
    """axis_way, the way back under Standard: whole steps where it does not cross the centre, as many presses as reach
    the centre or an edge (the press that would pass the centre stops on it), across the centre to it and on in whole
    steps, by the centre and back to a start off this record's grid but on the centre's; None where no press reaches the
    start. edge_way_back turns it into keys, and gives no press at all where one record cannot be reached."""
    assert F.axis_way(515, 320, 30, 320, 125, 515) == [[-1, 7]]          # Spot: XL's way back, as proved
    assert F.axis_way(408, 240, 20, 240, 72, 408) == [[-1, 9]]           # Spot: M's Y: 248, then the centre
    assert F.axis_way(560, 380, 30, 320, 80, 560) == [[-1, 6]]           # whole steps, the centre not crossed
    assert F.axis_way(447, 183, 19, 240, 33, 447) == [[-1, 14]]          # to the centre and three on
    assert F.axis_way(614, 376, 28, 320, 26, 614) == [[-1, 11], [1, 2]]  # by the centre and back
    assert F.axis_way(320, 376, 28, 320, 26, 614) == [[1, 2]]
    assert F.axis_way(320, 26, 28, 320, 26, 614) == [[-1, 11]]           # to an edge: the last press stops there
    assert F.axis_way(376, 376, 28, 320, 26, 614) == []
    assert F.axis_way(614, 377, 28, 320, 26, 614) is None
    m = F.edge_measure(GRID_REGS, 40)
    back, off = F.edge_way_back(GRID_REGS["high"], GRID_REGS["base"], m)
    assert (back, off) == ([["ms_left", 11], ["ms_right", 2], ["ms_up", 14]], {})
    assert pressed(EDGE_GRID["high"], back, EDGE_GRID["low"], EDGE_GRID["high"], EDGE_GRID["Standard"], EDGE_GRID["centre"]) == (376, 183)
    assert F.edge_way_back(GRID_REGS["high"], {X: 377, Y: 183}, m) == ([], {X: 237})


def test_under_large_the_way_back_is_counted_in_standards_step_and_lands_only_under_standard():
    """A Large measure's way back counted in Large's step goes wrong on the camera (Large crosses the centre without
    stopping); standard_m puts Standard's step (the hand tables' FRAME_STEPS, by the record's X or Y) on the Large
    measure's groups and edges, which gives Standard's own way back, and that lands under Standard."""
    m = F.edge_measure(LARGE_REGS, 40)
    assert (m["h"]["step"][X], m["v"]["step"][Y]) == (56, 38)
    as_large, _ = F.edge_way_back(LARGE_REGS["high"], LARGE_REGS["base"], m)
    assert pressed(EDGE_GRID["high"], as_large, EDGE_GRID["low"], EDGE_GRID["high"], EDGE_GRID["Large"], None) != (376, 183)
    std = F.standard_m(F.edge_records(m, grip_index()), EDGE_GRID["Standard"])
    assert (std["h"]["step"][X], std["v"]["step"][Y], std["h"]["centre"][X]) == (28, 19, 320)
    back, off = F.edge_way_back(LARGE_REGS["high"], LARGE_REGS["base"], std)
    assert back == [["ms_left", 11], ["ms_right", 2], ["ms_up", 14]] and off == {}
    assert pressed(EDGE_GRID["high"], back, EDGE_GRID["low"], EDGE_GRID["high"], EDGE_GRID["Standard"], EDGE_GRID["centre"]) == (376, 183)
    assert F.standard_step("Spot: XL") == (30, 20) and F.standard_step("Tracking: Custom 3") == (28, 19)
    assert F.standard_step("Made-up area") is None
    unnamed = [dict(r, name="Made-up record") for r in F.edge_records(m, grip_index())]
    assert F.standard_m(unnamed, EDGE_GRID["Standard"]) is None


def spot_xl_line(base=(320, 240), keys=("set1:0x019c", "set1:0x019e"), names=("AF point position X (current)",
                                                                                "AF point position Y (current)")) -> dict:
    """An edges line as kit2_a1fin_framepos_edges_gripup_large_plain wrote it for Spot: XL (the current records only):
    measured under Large, its frame left at (245, 226)."""
    x, y = keys
    rec = [{"key": x, "name": names[0], "keys": "Left/Right", "low": 125, "high": 515, "corner": 125, "step": 90,
            "raises": "Right", "first": 90, "short": []},
           {"key": y, "name": names[1], "keys": "Up/Down", "low": 106, "high": 374, "corner": 106, "step": 74,
            "raises": "Down", "first": 74, "short": []}]
    return {"area": "Spot: XL", "code": 103, "grip": "up", "moved": True,
            "context": "Switch V/H AF Area = AF Point + AF Area, camera grip up, Vertical Display On, AF Frame Move Amt "
                       "Large",
            "values": {"base": {x: base[0], y: base[1]}, "high": {x: 515, y: 374}},
            "files": {"base": "00073_edge-base-spot-xl.DAT"}, "edges": rec,
            "back": {"same": False, "off": [{"key": x, "delta": -75}, {"key": y, "delta": -14}], "tries": 1}}


def test_the_put_back_plan_for_the_frame_the_large_run_left_and_its_refusals():
    """--put-back's plan for the line kit2_a1fin_framepos_edges_gripup_large_plain left (Spot: XL, start (320, 240),
    measured under Large): Standard's step from the hand tables, the way back from the far corner Left 7 and Up 7, as
    the Standard runs went. A line whose frame came back is not planned; one without measured edges, one whose area has
    no Standard step, and one whose start no press reaches from the far corner are refused, nothing pressed."""
    line = spot_xl_line()
    assert F.left_behind([dict(line, back={"same": True}), line]) == [line]
    assert F.left_behind([line, dict(line, back={"same": True})]) == []
    m, why = F.put_back_plan(line)
    assert why == "" and F.edge_way_back(line["values"]["high"], line["values"]["base"], m) == \
        ([["ms_left", 7], ["ms_up", 7]], {})
    assert "no edges" in F.put_back_plan(dict(line, edges=None))[1]
    assert "FRAME_STEPS give no Standard step" in F.put_back_plan(line, table={})[1]
    m, why = F.put_back_plan(spot_xl_line(base=(321, 240)))
    assert m is None and "no press reaches its start from the far corner" in why and "+194" in why


class EdgeCam(Turned):
    """A made-up camera whose focus frames step as the a1 II's do (`stepped`): whole steps, stopped at an edge, and under
    AF Frame Move Amt Standard stopped at the centre where a press would cross it, under Large not. AF Frame Move Amt is
    `amt` and follows its menu row (set_amt), its code in the live record and each registration's copy. The
    multi-selector's presses come through the link (a push) or through the camera (a single press) alike; `drop` lists
    the link presses that are lost, by number; `turn` swaps the keys' axes; `flip` turns their sense (Right lowers where
    it raised); `fail_regs` the slot registrations, by number, that bring no "Registered."; a registration writes Custom
    boxes into X and Y, any other area into the made-up point records."""
    GEOMETRY = {"Custom 1": ((26, 33), (614, 447), {"Standard": (28, 19), "Large": (56, 38)}),
                "Expand Spot": ((65, 61), (575, 419), {"Standard": (30, 20), "Large": (60, 38)}),
                "Spot: XL": ((125, 106), (515, 374), {"Standard": (30, 20), "Large": (90, 74)})}
    POINT = ("set1:0x0b10", "set1:0x0b12")

    def __init__(self, run, start=None, drop=(), turn=False, fail_regs=(), flip=False, amt="Standard", **kw):
        super().__init__(run, level=True, **kw)
        self.slot.update({self.POINT[0]: 300, self.POINT[1]: 200, AMT_LIVE: AMT_CODES[amt], AMT_COPY: AMT_CODES[amt]})
        self.pos = dict(start or {"Custom 1": (376, 183), "Expand Spot": (320, 240)})
        self.drop, self.turn, self.fail_regs, self.flip, self.amt = set(drop), turn, set(fail_regs), flip, amt
        self.link_presses, self.regs, self.pushed, self.amt_rows = 0, 0, [], []
        self.hdmi = SimpleNamespace(grab=lambda save=True: self.frame)
        self.link = SimpleNamespace(press=self.link_press)

    def set_amt(self, option):
        self.amt_rows.append(option)
        self.amt = option
        self.slot[AMT_LIVE] = AMT_CODES[option]

    def reading(self, f):
        return SimpleNamespace(kind=self.now["kind"])

    def move(self, key):
        axis, d = {"ms_right": (0, 1), "ms_left": (0, -1), "ms_down": (1, 1), "ms_up": (1, -1)}[key]
        if self.turn:
            axis = 1 - axis
        if self.flip:
            d = -d
        low, high, steps = self.GEOMETRY[self.area]
        place = list(self.pos[self.area])
        centre = F.centre_of(low[axis], high[axis]) if self.amt == "Standard" else None
        place[axis] = stepped(place[axis], d, low[axis], high[axis], steps[self.amt][axis], centre)
        self.pos[self.area] = tuple(place)

    def link_press(self, key, *args, on_shooting=frozenset(), screen=None, **kw):
        assert getattr(screen, "kind", screen) == "shooting" and key in on_shooting, (key, on_shooting, screen)
        self.link_presses += 1
        self.pushed.append(key)
        if self.link_presses not in self.drop:
            self.move(key)

    def press(self, key, **kw):
        if self.now.get("text") == SLOTS and key == "enter":
            self.pressed.append(key)
            self.answer_once, self.n, self.regs = None, self.n + 1, self.regs + 1
            if self.regs in self.fail_regs:
                self.now = {"kind": "menu", "text": "Shooting Mode MR Camera Set. Memory"}
                return
            x, y = self.pos[self.area]
            keys = (X, Y) if self.area.startswith("Custom") else self.POINT
            self.slot.update({keys[0]: x, keys[1]: y, AMT_COPY: AMT_CODES[self.amt]})
            self.show("registered")
            return
        if self.now["kind"] == "shooting":
            assert key in self.MOVE and kw.get("on_shooting") == key, (key, kw)
            self.pressed.append(key)
            self.named.append((key, kw.get("on_shooting")))
            self.n += 1
            self.move(key)
            return
        super().press(key, **kw)


def edge_index() -> dict:
    """vd_index with Circ. of Focus Point's record, proved by its menu row (codes made up)."""
    return vd_index() | {CIRC_KEY: {"key": CIRC_KEY, "name": "Circ. of Focus Point",
                                      "values": [[0, "Does Not Circulate"], [1, "Circulate"]],
                                      "proved": {"menu": ["Circ. of Focus Point"]}}}


@pytest.fixture
def edges(turned, monkeypatch):
    """The turned fixture's session on EdgeCam, every area chosen on the level dialog and AF Frame Move Amt's row set on
    the camera; go(s, labels) runs F.areas with --edges over them (go(s, labels, put_back=line) --put-back of that
    edges line instead) and returns the lines written."""
    import afreg_run
    monkeypatch.setattr(afreg_run, "choose_level", choose_level)

    def row_set(cam, cycle, model, path, option):
        assert path == [F.AMT_ROW], path
        cam.set_amt(option)
    monkeypatch.setattr(afreg_run, "set_setup_row", row_set)
    run, session = turned

    def go(s, labels: str, grip=None, n=40, amt="Standard", put_back=None, index=None):
        todo = F.edge_plan(made_up_doc(), labels)
        idx = index or edge_index()
        a = SimpleNamespace(zone_grid=False, context=None, allow=["Camera Set. Memory"], check_back=True, grip=grip,
                            edges=not put_back, edge_presses=n, put_back="kit2_made_up" if put_back else None)
        if put_back:
            a.put_back_lines = {put_back["area"]: (put_back, F.put_back_plan(put_back, index=idx)[0])}
        tag = {"context": F.context_of(None, amt, None, grip), "allowance": "a", **({"grip": grip} if grip else {})}
        routes = {t["label"]: afreg_run.route(t["label"], CAROUSEL, CAROUSEL_AXES) for t in todo}
        lines = []
        F.areas(s, a, run, None, None, None, CAROUSEL, CAROUSEL_AXES, todo, routes, idx, False, False,
                run.dir / "framepos.jsonl", tag, lines, amt, tag)
        out = run.dir / ("put_back.jsonl" if put_back else "edges.jsonl")
        return F.jsonl.read(out) if out.exists() else []
    return run, (lambda cls=EdgeCam, **kw: session(cls=cls, **kw)), go


def test_edges_measure_each_area_in_seven_registrations_and_put_its_frame_back_exactly(edges, capsys):
    """--edges on two areas: each chosen, its start registered, pushed to the low corner, one press off it on each axis,
    pushed to the far corner, brought back by computed presses and registered once more, which matches the first: seven
    registrations an area. The pushes go through the link, each named for the shooting screen; the summary gives each
    record's edges, step and first press off the low edge, and never the start nor the presses that told it."""
    run, session, go = edges
    cam, s = session()
    lines = go(s, "Custom 1, Expand Spot")
    assert cam.chosen == ["Custom 1", "Expand Spot"] and cam.regs == 14 and cam.amt_rows == []
    assert cam.pos == {"Custom 1": (376, 183), "Expand Spot": (320, 240)}
    got = {ln["area"]: ln for ln in lines}
    assert all(ln["back"]["same"] and not ln.get("failed") for ln in got.values())
    rec = {r["key"]: r for r in got["Custom 1"]["edges"]}
    assert (rec[X]["low"], rec[X]["high"], rec[X]["step"], rec[X]["first"], rec[X]["keys"]) == (26, 614, 28, 28, "Left/Right")
    assert (rec[Y]["low"], rec[Y]["high"], rec[Y]["step"], rec[Y]["first"], rec[Y]["keys"]) == (33, 447, 19, 19, "Up/Down")
    assert got["Custom 1"]["values"]["base"] == {X: 376, Y: 183}, "the start kept in the run's own file"
    said = capsys.readouterr().out
    summary = (run.dir / "edges_summary.txt").read_text(encoding="utf-8")
    for text in (said, summary):
        assert ("    Left/Right  set:0x0c20  Custom 1 box position: X (horizontal): 26 to 614, a press 28 (Right raises it), "
                "the first press off 26 moves 28") in text
        assert "    Up/Down  set:0x0c24  Custom 1 box position: Y (horizontal): 33 to 447, a press 19 (Down raises it)" in text
        assert "    put back: the registration after it matched the first" in text
    assert "376" not in summary and "183" not in summary and "Left 11" not in said


def test_edges_under_large_measure_large_and_come_back_under_standard(edges, capsys):
    """--edges --frame-move-amt Large: each area measured under Large (its steps Large's in the line), AF Frame Move Amt
    = Standard through its row once the far corner is registered, the way back counted in Standard's step and pressed
    under Standard, which lands; Large again before the next area, whose start reads Large; the check leaves AF Frame
    Move Amt's own records out. The summary says the way back was made under Standard."""
    run, session, go = edges
    cam, s = session(amt="Large")
    lines = go(s, "Custom 1, Expand Spot", amt="Large")
    assert cam.pos == {"Custom 1": (376, 183), "Expand Spot": (320, 240)} and cam.regs == 14
    assert cam.amt_rows == ["Standard", "Large", "Standard"]
    got = {ln["area"]: ln for ln in lines}
    assert all(ln["back"]["same"] and ln["back"]["under"] == "Standard" and not ln.get("failed") for ln in got.values())
    rec = {r["key"]: r for r in got["Custom 1"]["edges"]}
    assert (rec[X]["step"], rec[Y]["step"]) == (56, 38) and "AF Frame Move Amt Large" in got["Custom 1"]["context"]
    assert got["Custom 1"]["values"]["low"] == {X: 26, Y: 33} and got["Custom 1"]["values"]["snap-h"] == {X: 82, Y: 33}
    assert "    put back under Standard: the registration after it matched the first" in capsys.readouterr().out


def test_an_area_whose_start_does_not_read_large_is_not_measured(edges, capsys):
    """Under Large an area's start must read AF Frame Move Amt Large (its code in the start's registration), or nothing
    is measured: the frame is not moved."""
    run, session, go = edges
    cam, s = session(amt="Standard")                                    # the setup's Large did not take, say
    (line,) = go(s, "Custom 1", amt="Large")
    assert "does not hold AF Frame Move Amt Large's code" in line["failed"]
    assert not line["moved"] and "back" not in line and cam.pushed == [] and cam.regs == 1
    assert "its frame was not moved" in capsys.readouterr().out


def test_a_press_lost_on_the_way_back_is_found_by_the_check_and_made_good(edges):
    """A push's press the camera lost on the way back leaves the frame a step off: the check registration shows it, the
    run plans the way again from where it landed and checks again, which matches."""
    run, session, go = edges
    cam, s = session(drop={165})                    # a Left of Custom 1's way back (80 + 40 + 40 presses before it)
    (line,) = go(s, "Custom 1")
    assert cam.regs == 8 and line["back"]["same"] and line["back"]["tries"] == 2 and cam.pos["Custom 1"] == (376, 183)


def test_a_start_no_press_can_reach_stops_the_run_saying_the_difference(edges, capsys):
    """A start no press reaches from the far corner (set by touch, say: off every grid a press steps on): nothing is
    pressed after the far corner; the area fails saying each measured record's difference, and the run stops there."""
    run, session, go = edges
    cam, s = session(start={"Custom 1": (377, 183), "Expand Spot": (320, 240)})
    lines = go(s, "Custom 1, Expand Spot")
    assert cam.chosen == ["Custom 1"] and len(lines) == 1 and cam.pos["Custom 1"] == (614, 447)
    assert lines[0]["back"]["same"] is False and lines[0]["back"]["off"] == [{"key": X, "delta": 237},
                                                                              {"key": Y, "delta": 264}]
    said = capsys.readouterr().out
    assert "NOT PUT BACK: set:0x0c20 +237; set:0x0c24 +264" in said and "move it back by hand" in said
    assert "stopping" in said and "no press reaches its start" in lines[0]["failed"]


@pytest.mark.parametrize("fail,regs,tags,amt", [
    (5, 11, ["again-low", "again-snap-h", "again-step-h", "again-step-v", "again-high", "back1"], "Standard"),
    (6, 8, ["again-high", "back1"], "Standard"),                        # every step known: the far corner, then back
    (7, 9, ["again-high", "back1"], "Standard"),                        # the way back's check
    (6, 8, ["again-high", "back1"], "Large")])                          # under Large: Standard first
def test_a_registration_that_fails_mid_area_brings_the_frame_back_from_the_far_corner(edges, capsys, fail, regs, tags,
                                                                                      amt):
    """A registration failing once the frame has moved: the screen closed, the low side measured again where its steps
    are not all known, the frame pushed to the far corner and brought back from there under Standard (a Large run sets
    it first), checked. The area is failed (its edges not measured), its frame back where it began, and the run goes on
    to the next area."""
    run, session, go = edges
    cam, s = session(fail_regs={fail}, amt=amt)
    lines = go(s, "Custom 1, Expand Spot", amt=amt)
    assert cam.chosen == ["Custom 1", "Expand Spot"] and cam.pos["Custom 1"] == (376, 183)
    first = lines[0]
    assert first["failed"] and first["back"]["same"] and list(first["files"])[-len(tags):] == tags
    assert cam.regs - 7 == regs, "Expand Spot's seven after Custom 1's own"
    assert lines[1]["back"]["same"] and not lines[1].get("failed")
    assert cam.amt_rows == ([] if amt == "Standard" else ["Standard", "Large", "Standard"])


def test_edges_held_vertically_with_turned_keys_measure_what_each_key_moves(edges):
    """Held grip down (Vertical Display Off, the screens level), a view whose keys turn (Right moves Y): the groups
    follow what moved, the way back presses the keys that move each record, and the frame ends where it began."""
    run, session, go = edges
    cam, s = session(turn=True, extra={VD_KEY: 1})
    (line,) = go(s, "Custom 1", grip="down")
    assert line["back"]["same"] and cam.pos["Custom 1"] == (376, 183)
    rec = {r["key"]: r for r in line["edges"]}
    assert rec[Y]["keys"] == "Left/Right" and rec[X]["keys"] == "Up/Down" and rec[X]["step"] == 28


def test_edges_held_vertically_with_keys_turned_and_mirrored_take_what_the_registrations_show(edges):
    """Held vertically the keys may move the other axis and the other way (Right lowers Y, Down lowers X): nothing
    assumes Right raises X or Down raises Y. Which key moves which record, its step's sign, the edges by value and the
    way back all come from the registrations: Left and Up reach the high values, the steps read negative ("Left raises
    it", "Up raises it"), the edges are the same 26 to 614 and 33 to 447, and the frame ends where it began."""
    run, session, go = edges
    cam, s = session(turn=True, flip=True, extra={VD_KEY: 1})
    (line,) = go(s, "Custom 1", grip="down")
    assert line["back"]["same"] and cam.pos["Custom 1"] == (376, 183) and not line.get("odd")
    rec = {r["key"]: r for r in line["edges"]}
    assert (rec[Y]["keys"], rec[Y]["low"], rec[Y]["high"], rec[Y]["step"], rec[Y]["raises"], rec[Y]["corner"]) == \
        ("Left/Right", 33, 447, 19, "Left", 447)
    assert (rec[X]["keys"], rec[X]["low"], rec[X]["high"], rec[X]["step"], rec[X]["raises"], rec[X]["corner"]) == \
        ("Up/Down", 26, 614, 28, "Up", 614)
    assert (rec[Y]["first"], rec[X]["first"]) == (19, 28)


def point_line(**kw) -> dict:
    """spot_xl_line on the made-up definition's point records, which EdgeCam writes for a Spot."""
    return spot_xl_line(keys=EdgeCam.POINT, names=("Made-up point X (current)", "Made-up point Y (current)"), **kw)


def test_put_back_brings_the_large_runs_frame_back_through_the_far_corner_under_standard(edges, capsys):
    """--put-back of the line the Large run left: Spot: XL found at (245, 226), held grip up; registered there, pushed
    Right and Down to the far corner (which reads as the run's), registered, brought back Left 7 and Up 7 under
    Standard and registered, which matches the start on the measured records (the start's registration held Large's
    code, this one Standard's: not judged). Three registrations; the summary says it is put back."""
    run, session, go = edges
    cam, s = session(start={"Spot: XL": (245, 226)}, extra={VD_KEY: 1})
    (line,) = go(s, "Spot: XL", grip="up", put_back=point_line())
    assert cam.pos["Spot: XL"] == (320, 240) and cam.regs == 3 and cam.amt_rows == []
    assert line["back"]["same"] and line["values"]["now"] == {EdgeCam.POINT[0]: 245, EdgeCam.POINT[1]: 226}
    assert line["back"]["presses"] == [[["ms_left", 7], ["ms_up", 7]]] and "far_off" not in line
    assert line["source"] == {"run": "kit2_made_up", "start": "00073_edge-base-spot-xl.DAT",
                              "context": point_line()["context"]}
    said = capsys.readouterr().out
    assert "    put back under Standard: the registration after it matched the start's on the measured records" in said


def test_put_back_of_a_frame_already_at_its_start_presses_nothing(edges, capsys):
    run, session, go = edges
    cam, s = session(start={"Spot: XL": (320, 240)}, extra={VD_KEY: 1})
    (line,) = go(s, "Spot: XL", grip="up", put_back=point_line())
    assert cam.regs == 1 and cam.pushed == [] and line["back"]["already"]
    assert "already where it began: nothing pressed" in capsys.readouterr().out


def test_a_push_names_each_press_for_the_shooting_screen_and_stops_where_the_screen_is_not_it(quick, tmp_path):
    """F.push: each press named for the shooting screen and judged at the link on a fresh frame read as the shooting
    screen (decision 21), none waited on to settle; a screen not read as it before a press stops the push, nothing
    pressed there."""
    from prove_run import Failed
    cam = EdgeCam(SimpleNamespace(dir=tmp_path))
    cam.area = "Custom 1"
    assert F.push(cam, [["ms_left", 40], ["ms_up", 2]]) == [["ms_left", 40], ["ms_up", 2]]
    assert cam.pos["Custom 1"] == (26, 145) and cam.pushed == ["ms_left"] * 40 + ["ms_up"] * 2
    cam.now = {"kind": "notice", "text": "Made-up notice"}
    with pytest.raises(Failed, match="not on the shooting screen before Right"):
        F.push(cam, [["ms_right", 3]])
    assert len(cam.pushed) == 42


def edges_doc(circ=True) -> dict:
    doc = made_up_doc()
    doc["settings"] += [v for k, v in edge_index().items() if k not in index() and (circ or k != CIRC_KEY)]
    return doc


def test_list_with_edges_plans_every_movable_area_but_the_zones_and_sets_the_frame_to_stop_at_its_edges(
        capsys, monkeypatch):
    """--list --edges: every movable area but Zone and Tracking: Zone (their places are the nine --zone-grid proved),
    Circ. of Focus Point set to Does Not Circulate and AF Frame Move Amt to Standard through the menu first, both
    checked in the download after the setup, the registrations an area and how long the sweep should take; its own run
    folder. No camera."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    assert F.main(["--list", "--edges"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("18 areas' edges ('Switch V/H AF Area Off, camera level, AF Frame Move Amt Standard'; run "
                          "kit2_framepos_edges):")
    assert "  Zone " not in out and "Tracking: Zone" not in out and "  Custom 1 (code 109)" in out
    assert ("; Switch V/H AF Area = Off; Circ. of Focus Point = Does Not Circulate; AF Frame Move Amt = Standard; the "
            "start file") in out
    assert f"must hold Does Not Circulate's code 0 in {CIRC_KEY}" in out
    assert "7 registrations an area" in out and "minutes" in out
    F.main(["--list", "--edges", "--frame-move-amt", "Large", "--edge-presses", "30"])
    out = capsys.readouterr().out
    assert "AF Frame Move Amt Large" in out and "30 presses a push" in out
    assert "under Large each way back is made under Standard" in out
    assert not called
    assert F.main(["--edges", "--areas", "Custom 1", "--allow", "Camera Set. Memory"]) == 0
    (args, kw), = called
    assert args[0].edges and args[0].run == "kit2_framepos_edges" and kw["amt"] == "Standard"


@pytest.mark.parametrize("argv,words", [
    (["--edges", "--zone-grid"], "--edges with --zone-grid"),
    (["--edges", "--moves", "Right 1"], "--edges with --moves"),
    (["--edges", "--no-check-back"], "--edges with --no-check-back"),
    (["--edges", "--areas", "Zone,Custom 1"], "the nine named places"),
    (["--edges", "--edge-presses", "3"], "--edge-presses 3"),
    (["--edges", "--frame-move-amt", "leave"], "--frame-move-amt leave")])
def test_edges_refuse_what_they_cannot_measure_before_anything_connects(monkeypatch, argv, words):
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("connected"))
    with pytest.raises(SystemExit, match=re.escape(words)):
        F.main(argv + ["--allow", "Camera Set. Memory"])


def test_edges_under_large_need_standards_step_for_every_area(monkeypatch):
    """Under Large the way back is counted in Standard's step: an area the hand tables' FRAME_STEPS give none for stops
    the run before anything connects, naming it."""
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("connected"))
    monkeypatch.setattr(F, "FRAME_STEPS", {k: v for k, v in F.FRAME_STEPS.items() if k[1] != "Custom 2"})
    with pytest.raises(SystemExit, match=r"FRAME_STEPS give none for \['Custom 2'\]"):
        F.main(["--edges", "--frame-move-amt", "Large", "--areas", "Custom 1,Custom 2", "--allow", "Camera Set. Memory"])


def put_back_run(tmp_path, monkeypatch, *lines) -> str:
    """A made-up edges run's edges.jsonl holding `lines`, where paths.run_root finds it; its name."""
    monkeypatch.setattr(F.paths, "run_root", lambda *a, **k: tmp_path)
    (tmp_path / "kit2_made_up").mkdir()
    for ln in lines:
        F.jsonl.append(tmp_path / "kit2_made_up" / "edges.jsonl", ln)
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc())
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    return "kit2_made_up"


def test_list_with_put_back_plans_the_frames_the_run_left_held_as_it_held_them(capsys, monkeypatch, tmp_path):
    """--list --put-back RUN: each area RUN's edges.jsonl leaves out of place (a line that came back is not), held as
    RUN held the camera (its lines' grip), under Standard with Circ. of Focus Point set, to its start registration in
    RUN by name; its own run folder. A line whose start no press reaches is said and left out. A run hands the session
    the grip, Standard and the plans; nothing to put back says so."""
    import pass3_run

    def no_map(path):
        raise SystemExit("no pass 1 map")
    monkeypatch.setattr(pass3_run, "labels_of", no_map)
    called = []
    monkeypatch.setattr(F, "prove", lambda *a, **k: called.append((a, k)) or 0)
    back = dict(spot_xl_line(), area="Custom 1", code=109, back={"same": True})
    run = put_back_run(tmp_path, monkeypatch, spot_xl_line(), back, dict(spot_xl_line(base=(321, 240)), area="Spot: L"))
    assert F.main(["--list", "--put-back", run]) == 0
    out = capsys.readouterr().out
    assert out.startswith("  Spot: L: not put back: no press reaches its start from the far corner")
    assert ("1 frames kit2_made_up left out of place, to be put back ('Switch V/H AF Area = AF Point + AF Area, camera "
            "grip up, AF Frame Move Amt Standard'; run kit2_framepos_put_back):") in out
    assert "  Spot: XL (code 103): to its start registration in kit2_made_up (00073_edge-base-spot-xl.DAT)" in out
    assert "Circ. of Focus Point = Does Not Circulate; AF Frame Move Amt = Standard" in out and "Custom 1" not in out
    assert not called
    assert F.main(["--put-back", run, "--allow", "Camera Set. Memory"]) == 0
    (args, kw), = called
    assert args[0].grip == "up" and kw["amt"] == "Standard" and list(args[0].put_back_lines) == ["Spot: XL"]
    assert [t["label"] for t in args[2]] == ["Spot: XL"]
    run2 = "kit2_made_up"
    F.jsonl.append(tmp_path / run2 / "edges.jsonl", dict(spot_xl_line(), back={"same": True}))
    F.jsonl.append(tmp_path / run2 / "edges.jsonl", dict(spot_xl_line(base=(321, 240)), area="Spot: L",
                                                         back={"same": True}))
    assert F.main(["--list", "--put-back", run2]) == 0
    assert "no frame of kit2_made_up is left out of place" in capsys.readouterr().out


@pytest.mark.parametrize("argv,words", [
    (["--edges"], "--put-back with --edges"),
    (["--areas", "Spot: XL"], "--put-back with --areas"),
    (["--grip", "down"], "not --grip down"),
    (["--frame-move-amt", "Large"], "made under AF Frame Move Amt Standard")])
def test_put_back_refuses_what_it_cannot_do_as_the_run_did_before_anything_connects(monkeypatch, tmp_path, argv,
                                                                                    words):
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("connected"))
    run = put_back_run(tmp_path, monkeypatch, spot_xl_line())
    with pytest.raises(SystemExit, match=re.escape(words)):
        F.main(["--put-back", run, "--allow", "Camera Set. Memory", *argv])


def test_edges_need_circ_of_focus_point_in_the_definition_to_check_the_frame_stops(monkeypatch):
    """Without Circ. of Focus Point's record (proved by its row, its values naming Does Not Circulate) nothing could
    check that a frame stops at its edge rather than wrapping round: refused before anything connects."""
    monkeypatch.setattr(F, "read_json", lambda path: edges_doc(circ=False))
    monkeypatch.setattr(F.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(F, "prove", lambda *a, **k: pytest.fail("connected"))
    with pytest.raises(SystemExit, match="Circ. of Focus Point"):
        F.main(["--edges", "--allow", "Camera Set. Memory"])


def test_the_setup_sets_circ_of_focus_point_and_stops_when_it_did_not_take(monkeypatch, tmp_path):
    """With --edges the setup puts Circ. of Focus Point on Does Not Circulate before AF Frame Move Amt, and the download
    after it must hold that code, or the run stops before any area (the restore puts it back)."""
    import mode_switch
    import prove_run
    import runner
    from camkit import camset
    assert F.setup_steps(False, False, "Standard", None, circ=True)[-2:] == [
        ("row", "Circ. of Focus Point = Does Not Circulate"), ("row", "AF Frame Move Amt = Standard")]
    assert F.setup_rows("Standard", None, circ=True)["Circ. of Focus Point = Does Not Circulate"] == (
        ["Circ. of Focus Point"], "Does Not Circulate")
    held = {"global:0x0c00": 4, CIRC_KEY: 1}
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(F.afreg_run, "set_setup_row", lambda cam, cycle, model, path, option: None)
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    monkeypatch.setattr(prove_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(camset, "read", lambda path: Download(held))
    monkeypatch.setattr(camset, "diff", lambda a, b: [])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"00002_{tag}.DAT")
    args = (None, link, None, SimpleNamespace(dir=tmp_path), None, None, False, False, tmp_path / "00001_start.DAT",
            "Standard", edge_index())
    with pytest.raises(prove_run.Failed, match="Circ. of Focus Point did not take Does Not Circulate"):
        F.prepare(*args, circ=True)
    held[CIRC_KEY] = 0
    assert F.prepare(*args, circ=True)[-2:] == ["Circ. of Focus Point = Does Not Circulate", "AF Frame Move Amt = Standard"]


# ---------------------------------------------------------------- --zone-grid held vertically

# the a1 II's twelve zone records' names (keys as the camera's, a level copy and one or two of each grip's)
ZONE_NAMES = {"set:0x019a": "Zone position (current; grid index)", "set:0x0f0b": "Zone position memory (grid index)",
              "set:0x0f0d": "Zone position memory (grid index, copy)",
              "set:0x0f2c": "Zone position memory (horizontal, grid index, copy 1)",
              "set:0x0f32": "Zone position memory (vertical, grip down, grid index, copy 1)",
              "set:0x0f34": "Zone position memory (vertical, grip down, grid index, copy 2)",
              "set:0x0f38": "Zone position memory (vertical, grip up, grid index, copy 1)"}
EVERY = ["set1:0x019a", "set1:0x0f0b", "set1:0x0f0d"]          # what every orientation's registration writes
OWN = {"down": ["set1:0x0f32", "set1:0x0f34"], "up": ["set1:0x0f38"], "level": ["set1:0x0f2c"]}


def zone_vertical_index() -> dict:
    """The made-up definition with Vertical Display, Circ. of Focus Point and the zone records of ZONE_NAMES alone."""
    extra = edge_index()
    return index() | {k: extra[k] for k in (VD_KEY, CIRC_KEY)} | {k: {"key": k, "name": n, "values": GRID}
                                                                  for k, n in ZONE_NAMES.items()}


def test_a_vertical_sweeps_proof_lines_cover_every_orientations_records_and_that_grips_copies():
    """Held vertically, with Switch V/H AF Area = AF Point + AF Area, a registration writes the records every
    orientation writes and that grip's copies alone: the proof lines cover those (sweep_records), never the other grip's
    nor the horizontal copies; level (Switch V/H AF Area Off) they are zone_records' as before. Each line says how the
    camera was held; a copy that did not take the place's code is credited nothing."""
    idx = zone_vertical_index()
    assert F.sweep_records(idx, "down") == ["set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f32", "set:0x0f34"]
    assert F.sweep_records(idx, "up") == ["set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f38"]
    assert F.sweep_records(idx) == F.zone_records(idx) == ["set:0x019a", "set:0x0f32", "set:0x0f34", "set:0x0f38"]
    changes = [{"key": k, "before": 0, "after": 7} for k in EVERY + ["set1:0x0f32"]] + \
        [{"key": "set1:0x0f34", "before": 0, "after": 6}]
    line = F.sweep_line(0, (-1, -1), 7, changes, "4_zone-upper-left.DAT", idx)
    assert line["groups"] == {"horizontal": EVERY, "vertical, grip down": ["set1:0x0f32"], "vertical, grip up": []}
    assert line["other"] == {"set1:0x0f34": 6}
    held = {k.replace("set1:", "set:"): 7 for k in EVERY + ["set1:0x0f32"]} | {"set:0x0f34": 6}
    got = F.sweep_proofs(line, held, "3_zone-start.DAT", changes, idx, {"context": "c"}, "down")
    assert [(x["record"], x["applied"]) for x in got] == [("set:0x019a", True), ("set:0x0f0b", True),
                                                          ("set:0x0f0d", True), ("set:0x0f32", True),
                                                          ("set:0x0f34", False)]
    assert all("Switch V/H AF Area = AF Point + AF Area, the camera held grip down" in x["via"] for x in got)
    assert "Switch V/H AF Area = Off" in F.sweep_proofs(line, held, "b", changes, idx, {})[0]["via"]


def test_the_key_mappings_that_explain_a_move_and_the_way_back_under_one():
    """zone_fits: the turns and mirrors of the level keys under which presses lead from one place to another (the grid's
    edges stopping the zone); one Right that moved the zone down leaves two (Down's way not seen); the way back under a
    mapping (zone_back_presses) undoes it."""
    level, down_right = F.KEY_MAPS[0], ((0, 1), (1, 0))             # Right moves it down, Down moves it right
    assert F.zone_fits((-1, -1), [["ms_right", 1]], (0, -1)) == [level, ((1, 0), (0, -1))]
    two = F.zone_fits((-1, -1), [["ms_right", 1]], (-1, 0))
    assert len(two) == 2 and down_right in two and all(m[0] == (0, 1) for m in two)
    assert F.mapping_words(down_right) == "Right moved it down, Down right"
    assert F.mapping_words(level).startswith("as level")
    assert F.zone_moved((1, -1), [["ms_left", 2]], level) == (-1, -1)
    assert F.zone_moved((1, -1), [["ms_left", 2]], down_right) == (1, -1), "Left moves it up, stopped at the edge"
    assert F.zone_back_presses((1, 1), (-1, -1), level) == [["ms_left", 2], ["ms_up", 2]]
    turned = ((0, 1), (-1, 0))                                      # Right moves it down, Down left
    back = F.zone_back_presses((1, 1), (-1, -1), turned)
    assert back == [["ms_left", 2], ["ms_down", 2]] and F.zone_moved((1, 1), back, turned) == (-1, -1)


def test_a_grip_sweeps_context_is_read_by_the_oriented_pattern_as_its_grip():
    """The sweep's lines carry the grip context ("..., camera grip down, Vertical Display On"), which the hand tables'
    ORIENTED pattern reads as that grip, Vertical Display On or Off."""
    oriented = hand_tables.load(paths.A1II, evidence=False).ORIENTED
    for grip, words in (("down", "grip down"), ("up", "grip up")):
        for vertical in ("On", "Off"):
            context = F.context_of(None, None, None, grip, vertical)
            assert context.startswith(f"Switch V/H AF Area = AF Point + AF Area, camera {words}, Vertical Display ")
            assert oriented.search(f"Camera Set. Memory / Zone place [{context}]")[1] == words


class ZoneCam(Turned):
    """A made-up camera whose Zone steps over its 3 x 3 grid as `mapping` (KEY_MAPS) moves it, stopped at an edge; held
    `held` (down, up, level with Switch V/H AF Area = AF Point + AF Area, or None for it Off): a registration writes the
    zone's code into the records every orientation writes and that grip's copies (EVERY, OWN), or with it Off into
    every one. `drop`: the multi-selector presses lost, by number. Every screen level (Vertical Display Off)."""

    def __init__(self, run, start=(0, 0), held="down", mapping=None, drop=(), **kw):
        super().__init__(run, level=True, **kw)
        self.zone, self.held, self.mapping = tuple(start), held, mapping or F.KEY_MAPS[0]
        self.drop, self.presses = set(drop), 0
        self.slot.update({k: self.CODES[self.zone] for k in EVERY + sum(OWN.values(), [])})

    def press(self, key, **kw):
        if self.now.get("text") == SLOTS and key == "enter":
            self.pressed.append(key)
            self.answer_once, self.n = None, self.n + 1
            written = EVERY + sum(OWN.values(), []) if self.held is None else EVERY + OWN[self.held]
            self.slot.update({k: self.CODES[self.zone] for k in written})
            self.show("registered")
            return
        if self.now["kind"] == "shooting":
            assert key in self.MOVE and kw.get("on_shooting") == key, (key, kw)
            self.pressed.append(key)
            self.n, self.presses = self.n + 1, self.presses + 1
            if self.presses not in self.drop:
                self.zone = F.zone_moved(self.zone, [[key, 1]], self.mapping)
            return
        super().press(key, **kw)


@pytest.fixture
def zones(turned, monkeypatch):
    """The turned fixture's session on ZoneCam (its "extra" holding Vertical Display Off), Zone chosen on the level
    dialog; go(s, grip) runs F.areas with --zone-grid alone and returns (the sweep's line, zone_grid.jsonl's lines,
    proofs.jsonl's lines)."""
    import afreg_run
    monkeypatch.setattr(afreg_run, "choose_level", choose_level)
    run, session = turned

    def go(s, grip):
        a = SimpleNamespace(zone_grid=True, zone_target=F.plan(made_up_doc(), "Zone")[0], context=None, moves=None,
                            allow=["Camera Set. Memory"], check_back=True, grip=grip, edges=False, put_back=None)
        tag = {"context": F.context_of(None, None, None, grip), "allowance": "a", **({"grip": grip} if grip else {}),
               **({"upright": True} if grip in F.TURNED else {})}
        lines = []
        F.areas(s, a, run, None, None, None, CAROUSEL, CAROUSEL_AXES, [],
                {"Zone": afreg_run.route("Zone", CAROUSEL, CAROUSEL_AXES)}, zone_vertical_index(), False, False,
                run.dir / "framepos.jsonl", tag, lines, None, tag)
        return lines[-1], F.jsonl.read(run.dir / "zone_grid.jsonl"), F.jsonl.read(run.dir / "proofs.jsonl")
    return run, (lambda **kw: session(cls=ZoneCam, extra={VD_KEY: 1}, **kw)), go


@pytest.mark.parametrize("grip", ["down", "up"])
def test_a_sweep_held_vertically_walks_the_nine_places_and_says_what_each_wrote_by_orientation(zones, capsys, grip):
    """--zone-grid held grip down (or up): the nine places walked as the level sweep walks them, each registration's
    records by orientation (every orientation's records and that grip's copies, none of the other grip's), one console
    line a place with codes, names and keys only; proof lines for those records with the grip context the ORIENTED
    pattern reads; the zone put back and checked."""
    run, session, go = zones
    cam, s = session(held=grip, start=(1, 0))
    sweep, grid, proofs = go(s, grip)
    assert sweep["confirmed"] == 9 and sweep["back_same"] and "failed" not in sweep and cam.zone == (1, 0)
    other = "vertical, grip up" if grip == "down" else "vertical, grip down"
    own = "vertical, grip down" if grip == "down" else "vertical, grip up"
    assert [x["name"] for x in grid] == ["Upper left", "Up", "Upper right", "Right", "Centre", "Left", "Lower left",
                                         "Down", "Lower right"]
    assert all(x["groups"]["horizontal"] == EVERY and x["groups"][own] == OWN[grip] and x["groups"][other] == []
               and x["other"] == {} for x in grid)
    context = f"Switch V/H AF Area = AF Point + AF Area, camera grip {grip}, Vertical Display Off"
    assert all(x["context"] == context and x["grip"] == grip and "upright" not in x for x in grid + proofs)
    applied = [p for p in proofs if p["applied"]]
    assert {p["key"] for p in applied} == set(EVERY + OWN[grip]) and len(applied) == 9 * len(EVERY + OWN[grip])
    assert all(p["kind"] == "registration mirror" and f"camera held grip {grip}" in p["via"] for p in proofs)
    said = capsys.readouterr().out
    assert (f"  zone sweep 1/9: Upper left -> code 7 (Upper left), confirmed; records: horizontal {', '.join(EVERY)}; "
            f"{own} {', '.join(OWN[grip])}") in said
    assert "the registration after the put-back matched the start's" in said and "Right (" not in said.split("1/9")[0]


def test_a_level_sweep_is_as_it_was(zones):
    """No grip: Switch V/H AF Area Off, every copy written at once, the proof lines zone_records' (the current record
    and the vertical copies), the context the level one."""
    run, session, go = zones
    cam, s = session(held=None, start=(0, 0))
    sweep, grid, proofs = go(s, None)
    assert sweep["confirmed"] == 9 and sweep["back_same"] and cam.zone == (0, 0)
    assert {p["key"] for p in proofs if p["applied"]} == {"set1:0x019a", "set1:0x0f32", "set1:0x0f34", "set1:0x0f38"}
    assert all(x["context"] == "Switch V/H AF Area Off, camera level" for x in grid)


def test_keys_that_move_the_zone_turned_are_said_as_a_finding_and_the_zone_still_comes_back(zones, capsys):
    """Held grip up on a camera whose keys move the zone turned (Right moves it down, Down right): the corner reads as
    routed (Left and Up still lead there), the next place does not; the walk ends saying what Right did and the one
    turn of the keys that explains every move seen, writes no proof line for that place, and still puts the zone back
    and checks it. The sweep fails with the finding."""
    run, session, go = zones
    cam, s = session(held="up", start=(0, 0), mapping=((0, 1), (1, 0)))
    sweep, grid, proofs = go(s, "up")
    assert cam.zone == (0, 0) and sweep["back_same"] and sweep["confirmed"] == 1 and len(grid) == 2
    assert grid[1]["confirmed"] is False and grid[1]["fits"] == ["Right moved it down, Down right"]
    assert "Right moved the zone +0 column(s), +1 row(s), where level it moves +1 column(s), +0 row(s)" in sweep["failed"]
    assert {p["dat"] for p in proofs if p["applied"]} == {grid[0]["download"]}
    said = capsys.readouterr().out
    assert ("  zone sweep 2/9: Up NOT as routed: Right moved the zone +0 column(s), +1 row(s), where level it moves +1 "
            "column(s), +0 row(s); the keys act turned: Right moved it down, Down right") in said


def test_a_turn_the_moves_do_not_tell_apart_is_said_and_a_zone_off_its_start_is_said_not_guessed(zones, capsys):
    """Keys turned half round from a start at an edge: the presses toward the upper left read elsewhere, which two
    turns or mirrors explain; the counted presses back do not bring it to its start (a press met the edge), and with no
    one mapping known nothing more is pressed: the zone-back differs and the sweep says so."""
    run, session, go = zones
    cam, s = session(held="down", start=(1, 1), mapping=((-1, 0), (0, -1)))
    sweep, grid, proofs = go(s, "down")
    assert len(grid) == 1 and grid[0]["confirmed"] is False and len(grid[0]["fits"]) == 2 and proofs == []
    assert not sweep["back_same"] and cam.zone != (1, 1)
    said = capsys.readouterr().out
    assert "1/9: Upper left NOT as routed: the presses toward the upper left led elsewhere; 2 turns or mirrors" in said
    assert "differs from the start's" in said and "move it back by hand" in said


def test_a_press_lost_on_the_way_back_is_made_good_under_the_level_keys(zones, capsys):
    """Every place read as routed, so the keys act as level: a press lost on the way back leaves the zone off its start,
    which zone-back shows; it is brought there straight and checked again (zone-back2)."""
    run, session, go = zones
    cam, s = session(held="down", start=(0, 0), drop={11})          # the corner's 2 and the route's 8 before it
    sweep, grid, proofs = go(s, "down")
    assert sweep["confirmed"] == 9 and sweep["back_same"] and cam.zone == (0, 0)
    assert sweep["files"]["back"].endswith("zone-back2.DAT")
    assert "the registration after the put-back matched the start's" in capsys.readouterr().out


# ---------------------------------------------------------------- a STOP mid-area, and the Aspect Ratio (2026-11-17)

RATIO_KEY = "global:0x0c30"
RATIO_CODES = {"3:2": 0, "4:3": 1, "16:9": 2, "1:1": 3}
EDGES_CONTEXT = "Switch V/H AF Area Off, camera level, AF Frame Move Amt Standard"


def ratio_index() -> dict:
    """edge_index with a made-up Aspect Ratio record, proved by its row as the a1 II's global:0x01fe is."""
    return edge_index() | {RATIO_KEY: {"key": RATIO_KEY, "name": "Aspect Ratio",
                                       "values": [[v, k] for k, v in RATIO_CODES.items()],
                                       "proved": {"menu": ["Aspect Ratio"]}}}


class StopCam(EdgeCam):
    """EdgeCam whose STOP file is put down once its second registration (the low corner) is made and one more Right has
    gone out, as kit2_a1fin_framepos_edges_ar169_all stopped in Custom 1: the next press the run sends raises
    StopRequested, as the link does for every press after a STOP."""
    def press(self, key, **kw):
        from camkit.link import StopRequested
        if self.regs >= 2 and getattr(self, "went", False):
            raise StopRequested("STOP file in the run's folder")
        if self.regs >= 2 and key == "ms_right":
            self.went = True
        super().press(key, **kw)


def files_line(base=(320, 240), **kw) -> dict:
    """Custom 1's line as files_lines makes it from a stopped run's downloads: its start and its low corner."""
    return {"area": "Custom 1", "code": 109, "moved": True, "from_files": True, "context": EDGES_CONTEXT,
            "files": {"base": "01063_edge-base-custom-1.DAT", "low": "01081_edge-low-custom-1.DAT"},
            "values": {"base": {X: base[0], Y: base[1]}, "low": {X: 26, Y: 33}}, **kw}


def test_an_area_a_stop_ends_writes_its_line_and_put_back_brings_its_frame_back(edges, capsys):
    """A STOP once Custom 1's frame has moved (its start and low corner registered, one more Right gone out): nothing
    more is pressed, and the area's line is written all the same, moved, no "back", its registrations so far (files and
    values) and what stopped it, so left_behind finds it and --put-back plans it from them: the records that changed,
    each one's axis by its name, Standard's step, the grid's centre. Brought back from where it was left, it lands on its
    start."""
    from camkit.link import StopRequested
    run, session, go = edges
    cam, s = session(cls=StopCam, start={"Custom 1": (320, 240), "Expand Spot": (320, 240)})
    with pytest.raises(StopRequested):
        go(s, "Custom 1, Expand Spot")
    (line,) = F.jsonl.read(run.dir / "edges.jsonl")
    assert line["area"] == "Custom 1" and line["moved"] and "back" not in line and "edges" not in line
    assert line["stopped"].startswith("StopRequested") and list(line["files"]) == ["base", "low"]
    assert line["values"] == {"base": {X: 320, Y: 240}, "low": {X: 26, Y: 33}} and line["context"] == EDGES_CONTEXT
    assert cam.chosen == ["Custom 1"] and cam.pos["Custom 1"] == (54, 33), "the Right that went out, nothing after"
    said = capsys.readouterr().out
    assert "    stopped: StopRequested" in said and "bring it back with --put-back" in said
    assert F.left_behind([line]) == [line]
    m, why = F.put_back_plan(line, index=edge_index())
    assert why == "" and (m["h"]["keys"], m["v"]["keys"]) == ([X], [Y])
    assert (m["h"]["centre"][X], m["v"]["centre"][Y], m["h"]["step"][X], m["v"]["step"][Y]) == (320, 240, 28, 19)
    back, s2 = session(start={"Custom 1": (54, 33)})
    (put,) = go(s2, "Custom 1", put_back=line)
    assert put["back"]["same"] and back.pos["Custom 1"] == (320, 240)
    assert put["source"] == {"run": "kit2_made_up", "start": line["files"]["base"], "context": EDGES_CONTEXT}


def test_a_stopped_line_with_no_registration_after_its_start_is_not_planned():
    """A line stopped after its start alone (or held vertically, the keys perhaps turned) gives no plan: said why."""
    one = files_line()
    one["values"] = {"base": one["values"]["base"]}
    assert "no registration was made after its start" in F.put_back_plan(one, index=edge_index())[1]
    assert "otherwise than level" in F.put_back_plan(files_line(grip="down"), index=edge_index())[1]
    assert "gives no X or Y" in F.put_back_plan(files_line(), index={})[1]


def stopped_run(tmp_path, monkeypatch, held: dict, lines=(), setup=None) -> Path:
    """A made-up edges run where paths.run_root finds it (put_back_run): its edges.jsonl holding `lines`, its dat/ the
    downloads `held` names ({file: records}, read back by camset.read), its setup.jsonl `setup` ([steps, after])."""
    from camkit import camset
    run = tmp_path / put_back_run(tmp_path, monkeypatch, *lines)
    (run / "dat").mkdir()
    for name in held:
        (run / "dat" / name).write_bytes(b"")
    if setup:
        F.jsonl.append(run / "setup.jsonl", {"steps": setup[0], "start": "00001_before.DAT", "after": setup[1]})
    monkeypatch.setattr(camset, "read", lambda p: Download(held[Path(p).name]))
    monkeypatch.setattr(camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a.get(k), after=b.get(k))
                                                      for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)])
    return run


DISK = {"00001_before.DAT": {RATIO_KEY: 2}, "00909_edge-base-expand-spot.DAT": {RATIO_KEY: 2},
        "01063_edge-base-custom-1.DAT": {X: 320, Y: 240, RATIO_KEY: 2},
        "01081_edge-low-custom-1.DAT": {X: 26, Y: 33, RATIO_KEY: 2}, "01095_restored.DAT": {RATIO_KEY: 2}}


def test_put_back_finds_an_area_a_run_stopped_in_from_its_files_alone(capsys, monkeypatch, tmp_path):
    """kit2_a1fin_framepos_edges_ar169_all's case: stopped in Custom 1 before its line was written (by a kit older than
    the stopped line), edges.jsonl holding the finished areas alone. The edge-base download no line names is Custom 1's
    start, its registrations its downloads up to the run's end, its place records those that changed between them, its
    state the run's line before it (context, Aspect Ratio 16:9 said there); --put-back plans it from them and says so,
    and that its start is the centre, put back at any ratio."""
    before = dict(point_line(), area="Expand Spot", code=108, grip=None, context=f"{EDGES_CONTEXT}, Aspect Ratio 16:9",
                  back={"same": True}, files={"base": "00909_edge-base-expand-spot.DAT"})
    run = stopped_run(tmp_path, monkeypatch, DISK, [before])
    monkeypatch.setattr(F, "read_json", lambda path: {**edges_doc(), "settings": list(ratio_index().values())})
    (line,), said = F.files_lines(run, [before], {"settings": list(ratio_index().values())})
    assert said == [] and line["from_files"] and line["area"] == "Custom 1" and line["code"] == 109
    assert line["files"] == {"base": "01063_edge-base-custom-1.DAT", "low": "01081_edge-low-custom-1.DAT"}
    assert line["values"] == {"base": {X: 320, Y: 240}, "low": {X: 26, Y: 33}}
    assert (line["context"], line["state_from"]) == (before["context"], "the run's line before it (Expand Spot)")
    assert F.main(["--list", "--put-back", run.name]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"1 frames {run.name} left out of place, to be put back")
    assert "  Custom 1 (code 109): to its start registration in kit2_made_up (01063_edge-base-custom-1.DAT)" in out
    assert "taken from the run's files" in out and "its state the run's line before it (Expand Spot)" in out
    assert "measured under Aspect Ratio 16:9 (its start download): its start is the centre, the centre at any ratio" in out


def test_a_stopped_areas_state_comes_from_the_setup_where_no_line_came_before(monkeypatch, tmp_path):
    """Stopped in the run's first area: its state is the setup's (Switch V/H AF Area = Off: the camera level, its AF
    Frame Move Amt); a setup that does not say the camera level, or an area with two starts no line names, is said and
    left out."""
    disk = {k: v for k, v in DISK.items() if "expand" not in k}
    steps = ["Switch V/H AF Area = Off", "Circ. of Focus Point = Does Not Circulate", "AF Frame Move Amt = Standard"]
    run = stopped_run(tmp_path, monkeypatch, disk, setup=(steps, "00109_after-setup.DAT"))
    (line,), said = F.files_lines(run, [], {"settings": list(ratio_index().values())})
    assert line["context"] == EDGES_CONTEXT and "setup.jsonl" in line["state_from"] and "grip" not in line
    (run / "setup.jsonl").unlink()
    F.jsonl.append(run / "setup.jsonl", {"steps": ["Switch V/H AF Area = AF Point + AF Area"], "after": "00109_x.DAT"})
    lines, said = F.files_lines(run, [], {"settings": list(ratio_index().values())})
    assert lines == [] and "do not say how the camera was set" in said[0]
    (run / "dat" / "01200_edge-base-custom-1.DAT").write_bytes(b"")
    lines, said = F.files_lines(run, [], {"settings": list(ratio_index().values())})
    assert lines == [] and "2 starts no line names" in said[0]


def test_a_start_off_the_centre_is_put_back_only_under_the_ratio_it_was_measured_in():
    """The place grid is stretched over the recorded picture: a start at the centre is put back at any Aspect Ratio; one
    off it only where the ratio it was measured under (its start download's) is the camera's now, both read by the
    definition's labels."""
    idx = ratio_index()
    assert F.ratio_of(idx, Download({RATIO_KEY: 2})) == "16:9" and F.ratio_of(idx, Download({})) is None
    assert F.ratio_of(edge_index(), Download({RATIO_KEY: 2})) is None
    centre, off = {X: 320, Y: 240}, {X: 376, Y: 183}
    assert F.at_centre(centre, idx) and not F.at_centre(off, idx) and not F.at_centre({"set1:0x0b30": 320}, idx)
    assert F.ratio_refusal("16:9", "3:2", centre, idx) is None and F.ratio_refusal(None, None, centre, idx) is None
    assert F.ratio_refusal("16:9", "16:9", off, idx) is None
    assert "measured under Aspect Ratio 16:9, the camera is on 3:2" in F.ratio_refusal("16:9", "3:2", off, idx)
    assert "could not be read" in F.ratio_refusal(None, "3:2", off, idx)


@pytest.mark.parametrize("now,goes", [("3:2", False), ("16:9", True)])
def test_put_back_of_a_start_off_the_centre_needs_the_ratio_it_was_measured_in(edges, capsys, now, goes):
    """Custom 1 stopped at a start off the centre measured under 16:9: on a camera at 3:2 it is refused before it is
    chosen, nothing pressed, its line saying why; at 16:9 it is put back and lands on its start."""
    run, session, go = edges
    cam, s = session(start={"Custom 1": (54, 33)}, extra={RATIO_KEY: RATIO_CODES[now]})
    (put,) = go(s, "Custom 1", put_back=files_line(base=(376, 183), start_ratio="16:9"), index=ratio_index())
    if goes:
        assert put["back"]["same"] and cam.pos["Custom 1"] == (376, 183)
    else:
        assert "measured under Aspect Ratio 16:9, the camera is on 3:2" in put["refused"]
        assert cam.chosen == [] and cam.pushed == [] and cam.regs == 0 and cam.pos["Custom 1"] == (54, 33)
        assert "NOT PUT BACK, nothing pressed" in capsys.readouterr().out
