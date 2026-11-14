"""Owner decisions (decisions 4, 5, 8 and 9 as they stand since 2026-11-13): a dated decision in the camera's reviewed
scope that says "lifts": "owner" names rows of the never-open list a kit/drive.py run given --owner may open, the last
label of its --path, one per run: to look, to choose the options it names, and, in a run given --confirm, to confirm an
action as the run's last press. Inside an action any Enter may be the final one: a step goes before the last press only
where the decision marks it seen safe. Every layer is tested on its own: the decision's reading (camkit.safety), the
camera's own check (camkit.live.LiveCamera, its link a fake that checks nothing), drive.py's (its camera a fake that
checks nothing), the eyes (camkit.frames), the restore by hand (camkit.runs, camkit.link, kit/tools/upload_check.py,
kit/tools/chain.py) and the batch tools. Nothing here talks to a camera, a reader or a network; every value is a
placeholder.
"""
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, crawl, live, safety, vlm  # noqa: E402
from camkit.runs import RESTORE_BY_HAND, Run, mark_restore_by_hand, restore_pending  # noqa: E402

from conftest import TEST_CAMERA  # noqa: E402

DAY = "2026-11-13"
OWNER = {"date": DAY, "lifts": "owner", "why": "the owner: read everything, the cards are generic"}
# the menu places the kit knows (runner.known_places), as the definition writes them: (tab, group, row)
PLACES = [("Shooting", "Media", "Format"), ("Playback", "Delete", "Delete"), ("Shooting", "File", "Create New Folder"),
          ("Shooting", "File", "Select REC Folder"), ("Setup", "Reset/Save Settings", "Setting Reset"),
          ("Setup", "Reset/Save Settings", "Save/Load Settings"),
          ("Network", "Network Option", "Access Authen. Info"), ("Network", "Network Option", "Access Authen. Settings"),
          ("Network", "Network Option", "Reset Network Set."), ("Network", "Wi-Fi", "SSID/PW Reset"),
          ("Network", "Wi-Fi", "WPS Push"), ("Network", "Bluetooth", "Pairing"),
          ("Setup", "Setup Option", "Display Serial Number"), ("Network", "Wired LAN", "Wired LAN Connect"),
          ("Network", "Bluetooth", "Bluetooth Function"), ("Playback", "Editing", "Protect"),
          ("Network", "Wi-Fi", "Wi-Fi Direct Info."), ("Shooting", "Shooting Mode", "Camera Set. Memory"),
          ("Shooting", "Shooting Mode", "Reg. Custom Shoot Set"), ("Network", "Network Option", "Password Setting"),
          ("Shooting", "File", "File/Folder Settings"), ("Setup", "Setup Option", "Copyright Info"),
          ("Playback", "Playback Target", "Playback Filter Condition")]
FORMAT = "Shooting > Media > Format"
DELETE = "Playback > Delete > Delete"
SETTING_RESET = "Setup > Reset/Save Settings > Setting Reset"
RESET_NET = "Network > Network Option > Reset Network Set."
SSID_RESET = "Network > Wi-Fi > SSID/PW Reset"
SAVE_LOAD = "Setup > Reset/Save Settings > Save/Load Settings"
PROTECT = "Playback > Editing > Protect"
CREATE = "Shooting > File > Create New Folder"
FOLDER = "Shooting > File > Select REC Folder"
MEMORY = "Shooting > Shooting Mode > Camera Set. Memory"
SURE = "Format the memory card in Slot 1? All data will be deleted. Enter Cancel"
SECRET, USER, SERIAL = "made-up-secret", "camera-user", "1234567"       # placeholders, never a camera's own


def owner(*decisions, places=PLACES) -> dict:
    return safety.owner_decided({"decisions": [{**OWNER, **d} for d in decisions]}, places)


def info_of(entry, *decisions) -> dict:
    got = owner(*decisions)
    assert got["refusals"] == [], got["refusals"]
    return got["rows"][entry]


FORMAT_DECISION = {"rows": [FORMAT], "options": {FORMAT: ["Slot 1"]}, "confirm": [FORMAT]}
FORMAT_SEEN = {**FORMAT_DECISION, "steps_seen": {FORMAT: ["Slot 1"]}}
FORMAT_PLACE = ("shooting", "media", "format")


@pytest.fixture
def shipped():
    """The places that open to look as the kit ships them (safety.OPENS_TO_LOOK), not the tests' Format below."""


@pytest.fixture(autouse=True)
def format_seen(monkeypatch, request):
    """The steps, final presses and confirmations below are walked through Format, the action they were written for,
    as if a run's frame had shown that Right on "Shooting > Media > Format" opens its slots: the kit ships no such
    frame, so Format acts on opening (test_format_and_delete_act_on_opening_as_shipped). A test that asks for
    `shipped` sees the list as shipped."""
    if "shipped" not in request.fixturenames:
        monkeypatch.setattr(safety, "OPENS_TO_LOOK", safety.OPENS_TO_LOOK | {FORMAT_PLACE})


# ---------------------------------------------------------------- what a decision may name (findings 7, 11; D)

@pytest.mark.parametrize("entry,cls", [
    (FORMAT, safety.LIFT_CARDS), (DELETE, safety.LIFT_CARDS), (SETTING_RESET, safety.LIFT_ACTION),
    (RESET_NET, safety.LIFT_ACTION), (SSID_RESET, safety.LIFT_ACTION), ("Access Authen. Info", safety.LIFT_CREDENTIALS),
    ("Display Serial Number", safety.LIFT_SERIAL), ("Pairing", safety.LIFT_FIXED), ("WPS Push", safety.LIFT_FIXED),
    ("Wired LAN Connect", safety.LIFT_IDENTITY), ("Bluetooth Function", safety.LIFT_NETWORK)])
def test_an_owner_decision_names_rows_of_every_class_it_lifts(entry, cls):
    got = owner({"rows": [entry]})
    assert got["refusals"] == [] and got["rows"][entry]["class"] == cls
    assert len(got["rows"][entry]["path"]) >= 3                  # its place, from the path or the one place it is in
    # a network decision naming the same row: only its own three classes
    _, refusals = safety.network_decided({"decisions": [{**OWNER, "lifts": "network", "rows": [entry]}]})
    assert (refusals == []) is (cls in safety.NARROW), refusals


@pytest.mark.parametrize("label", ["Version", "Firmware Update", "Lens Firmware Update", "Recall Camera Setting",
                                   "Import Root Certificate", "Cleaning Mode", "Pixel Mapping", "Auto Pixel Mapping",
                                   "Anti-dust Function", "Preset Focus/Zoom", "Volume Settings", "Screen Reader",
                                   "Audio Signals", "Pre-AF", "Shutter When Pwr OFF", "SteadyShot",
                                   "Auto Power OFF Temp.", "AF Illuminator", "Video Light Setting", "Initialize"])
def test_no_decision_names_a_firmware_update_a_load_initialize_nor_sound_light_motion_or_the_screen_reader(label):
    """Finding 7 and the hard limits: these keep their own routes (a run's --allow, a dated approval, decision 3);
    Initialize is an item of Setting Reset's dialog whose Enter nobody has seen."""
    got = owner({"rows": [label]}, places=PLACES + [("Setup", "Option", label)])
    assert got["rows"] == {} and got["refusals"], got
    assert safety.owner_class(label) is None and safety.owner_never(label)
    assert owner({"rows": [f"{SETTING_RESET} > {label}"]})["rows"] == {}


def test_look_alike_spellings_name_nothing_no_decision_names():
    """The reviewer's probe: Cyrillic letters and OCR's slips are folded before the hard limits are judged."""
    places = [("Setup", "Setup Option", "Version"), ("Setup", "Accessibility", "Screen Reader"),
              ("Shooting", "Shooting Mode", "Recall Camera Setting")]
    for row in ["Vеrsion", "Setup > Setup Option > Versi0n", "Scrееn Reader",
                "Shooting > Shooting Mode > Recаll Camera Setting", "Firmwаre Update"]:
        got = owner({"rows": [row]}, places=places)
        assert got["rows"] == {} and got["refusals"], (row, got)
    for step in ["Lоad", "L0ad", "Import", "Recall"]:
        assert safety.owner_option_refused(step, "Save/Load Settings", safety.LIFT_ACTION), step


def test_a_card_or_action_row_is_named_by_its_path_and_a_label_known_twice_too():
    """Finding 11: "Delete" and "Format" recur inside rows the kit never opens; a label the kit knows in two places
    (or none) says no place; a path names a top-level place the kit knows."""
    for bare in ("Format", "Delete", "Setting Reset", "Reset Network Set."):
        got = owner({"rows": [bare]})
        assert got["rows"] == {} and "by its path" in got["refusals"][0], got
    assert owner({"rows": [FORMAT, DELETE]})["refusals"] == []
    got = owner({"rows": ["Wired LAN Connect"]}, places=PLACES + [("Network", "Other", "Wired LAN Connect")])
    assert "in 2 menu places" in got["refusals"][0]
    assert "in 0 menu places" in owner({"rows": ["Pairing"]}, places=[])["refusals"][0]
    assert "no top-level place" in owner({"rows": ["Setup > Media > Format"]})["refusals"][0]
    assert "Tab > Group > Row" in owner({"rows": ["Media > Format"]})["refusals"][0]
    assert info_of("Pairing", {"rows": ["Pairing"]})["path"] == ["Network", "Bluetooth", "Pairing"]


def test_a_scope_with_a_key_written_twice_or_tracked_by_git_is_refused(tmp_path):
    import runner
    f = tmp_path / "pass2_scope_draft.json"
    f.write_text('{"decisions": [{"date": "2026-11-13", "lifts": "owner", "rows": ["Pairing"], "link_loss": false, '
                 '"link_loss": true, "why": "w"}]}', encoding="utf-8")
    with pytest.raises(SystemExit, match="written twice"):
        runner.decisions_scope_or_exit(f, "--owner")
    f.write_text(json.dumps({"decisions": []}), encoding="utf-8")
    assert runner.decisions_scope_or_exit(f, "--owner") == {"decisions": []}         # outside a repository
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert runner.decisions_scope_or_exit(f, "--owner") == {"decisions": []}         # in one, not tracked
    subprocess.run(["git", "-C", str(tmp_path), "add", f.name], check=True)
    with pytest.raises(SystemExit, match="git tracks it"):
        runner.decisions_scope_or_exit(f, "--owner")


def test_a_network_decision_never_says_what_only_an_owner_decision_says():
    """Finding 6: link_loss, values, confirm and steps_seen belong to an owner decision alone."""
    for more in ({"link_loss": True}, {"values": "logged"}, {"confirm": ["Bluetooth Function"]},
                 {"steps_seen": {"Bluetooth Function": ["On"]}}):
        d = {**OWNER, "lifts": "network", "rows": ["Bluetooth Function"], **more}
        rows, refusals = safety.network_decided({"decisions": [d]})
        assert rows == {} and "only an owner decision" in refusals[0], refusals


def test_an_owner_decision_is_invisible_to_the_network_reading_and_the_motion_approvals():
    scope = {"decisions": [{**OWNER, "rows": [FORMAT, "Pairing"], "confirm": [FORMAT]}]}
    assert safety.network_decided(scope) == ({}, []) and safety.network_options(scope) == {}
    assert safety.approved_rows(scope) == set()
    rows = {**OWNER, "lifts": "network", "rows": ["Bluetooth Function"]}
    assert "network decision names it too" in owner(rows, {"rows": ["Bluetooth Function"]})["refusals"][0]


@pytest.mark.parametrize("bad", [{"link_loss": "yes"}, {"values": "all"}, {"confirm": FORMAT}, {"options": [FORMAT]},
                                 {"steps_seen": ["Slot 1"]}, {"what": 1}, {"date": "2099-01-01"}, {"why": " "},
                                 {"rows": []}])
def test_a_decision_of_the_wrong_shape_lifts_nothing(bad):
    got = owner({"rows": [FORMAT], **bad})
    assert got["rows"] == {} and got["refusals"], got


# ---------------------------------------------------------------- opening: what opens to look (D)

@pytest.mark.parametrize("place", ["Setup > Reset/Save Settings > Setting Reset",
                                   "Shooting > Shooting Mode > Camera Set. Memory",
                                   "Shooting > Shooting Mode > Reg. Custom Shoot Set", "My Menu > My Menu Setting > Add Item",
                                   "Shooting > File > Select REC Folder", " setup >  reset/save settings > SETTING RESET "])
def test_the_actions_seen_to_open_a_list_or_a_question_open_to_look_at_their_own_place(place, shipped):
    """Finding 2: by the whole place, as the a1 II's definition and Help Guide give it (a list of parts too)."""
    row = place.split(">")[-1].strip()
    assert safety.opens_to_look(place) and safety.opens_to_look([x.strip() for x in place.split(">")])
    assert not safety.opens_acting(row, safety.owner_class(row), place.split(">"))
    assert safety.opens_acting(row, safety.owner_class(row))                 # no place: it acts on opening
    assert not safety.opens_to_look(row)                                     # a label alone is no place


@pytest.mark.parametrize("place", [FORMAT, DELETE, "Focus > Subject Recognition > Face Memory > Delete",
                                   "Setup > Reset/Save Settings > Save/Load Settings > Delete",
                                   "Shooting > File > File/Folder Settings > Format", "Playback > Delete > Format",
                                   "Setup > Reset/Save Settings > Setting Reset > Format",
                                   "Setup > Setting Reset > Camera Set. Memory", "Format", "Delete", "Setting Reset"])
def test_a_place_nobody_has_seen_open_acts_on_opening(place, shipped):
    """Finding 2: Format and Delete have no frame of their opening; the names recur at places nobody opened."""
    row = place.split(">")[-1].strip()
    assert not safety.opens_to_look(place)
    assert safety.opens_acting(row, safety.owner_class(row), place.split(">")), place


def test_format_and_delete_act_on_opening_as_shipped(shipped):
    """Finding 2: as shipped, Format's and Delete's opening is the armed last press, and nothing is chosen in them."""
    for entry in (FORMAT, DELETE):
        got = info_of(entry, {"rows": [entry], "confirm": [entry]})
        assert got["acts_on_open"] and got["confirm"], entry
    said = owner(FORMAT_DECISION)["refusals"]
    assert said and "its opening acts" in said[0], said
    arm, C = safety.arm_refused, safety.LIFT_CARDS
    place = ["Shooting", "Media", "Format"]
    assert arm("Format", C, "open", "submenu", "Format", "", confirm=True, place=place) == ""
    assert "does not name it under" in arm("Format", C, "open", "submenu", "Format", "", place=place)


@pytest.mark.parametrize("row", ["Focus Magnifier", "Slide Show", "Enlarge Screen", "Copy", "Recover Image DB",
                                 "Reset Transfer Status", "Del. Regist. AF Area", "Lock Operation Parts", "Protect",
                                 "Reset Network Set.", "SSID/PW Reset", "Save/Load Settings", "Image Index",
                                 "Disp Specified Time Img.", "Create New Folder", "WPS Push", "Pairing", "Format",
                                 "Delete", "Setting Reset"])
def test_every_other_action_acts_on_opening(row):
    """D: the kit cannot know for an unseen row whether Right acts at once: its opening is its armed last press."""
    cls = safety.owner_class(row)
    assert cls is not None and safety.opens_acting(row, cls), row


def test_a_row_whose_opening_acts_takes_no_option_and_needs_link_loss_where_the_network_may_change():
    for row in ("WPS Push", "Pairing"):
        assert "may change the network" in owner({"rows": [row], "confirm": [row]})["refusals"][0]
        # finding 4 of the fourth review: its screens blanked, the screen after its opening could never be judged
        said = owner({"rows": [row], "confirm": [row], "link_loss": True})["refusals"]
        assert said and "\"values\": \"logged\"" in said[0], said
        assert info_of(row, {"rows": [row], "confirm": [row], "link_loss": True, "values": "logged"})["acts_on_open"]
        assert info_of(row, {"rows": [row], "link_loss": True})["confirm"] is False          # to name it, no confirm
    got = info_of(CREATE, {"rows": [CREATE], "confirm": [CREATE]})
    assert got["acts_on_open"] and got["confirm"] and not got["link_loss"]
    assert "its opening acts" in owner({"rows": [PROTECT], "options": {PROTECT: ["Multiple Img."]},
                                        "confirm": [PROTECT]})["refusals"][0]
    assert not info_of(FORMAT, FORMAT_DECISION)["acts_on_open"]


# ---------------------------------------------------------------- options, steps and confirmations (A)

@pytest.mark.parametrize("step", ["OK", "Enter", "Execute", "Yes", "No", "Done", "Cancel", "Set", "Format",
                                  "Full Format", "Delete", "Load", "Recall", "A", "?", "Space", "Del", "abc",
                                  "Continue", "Start", "Apply", "Proceed", "Accept", "Confirm", "Register", "Agree",
                                  "Begin", "Run", "Okay", "All in this Folder", "C0ntinue", "Cоntinue"])
def test_an_actions_steps_are_never_a_button_a_go_ahead_the_action_itself_a_confirmation_a_load_or_a_key(step):
    """A(2) and finding 1(c): a step never reads as the answer to the action's question."""
    got = owner({"rows": [FORMAT], "options": {FORMAT: ["Slot 1", step]}, "confirm": [FORMAT]})
    assert got["rows"][FORMAT]["options"] == [] and got["refusals"], (step, got)


def test_an_actions_steps_need_the_action_under_confirm_and_a_link_wiping_reset_none_at_all():
    assert "under \"confirm\" too" in owner({"rows": [FORMAT], "options": {FORMAT: ["Slot 1"]}})["refusals"][0]
    assert info_of(FORMAT, FORMAT_DECISION)["options"] == ["Slot 1"]
    for row in (RESET_NET, SSID_RESET):
        assert "wipes the network setup" in owner({"rows": [row], "confirm": [row]})["refusals"][0], row
        got = info_of(row, {"rows": [row], "confirm": [row], "link_loss": True})
        assert got["confirm"] and got["link_loss"] and got["acts_on_open"]
        # A(3): no step in a reset that wipes the link (the reviewer's "Continue" answered SSID/PW Reset as a step)
        said = owner({"rows": [row], "options": {row: ["Slot 1"]}, "confirm": [row], "link_loss": True})["refusals"]
        assert said and "takes no step" in said[0], said
    assert "is no action" in owner({"rows": ["Wired LAN Connect"], "confirm": ["Wired LAN Connect"]})["refusals"][0]


def test_steps_seen_name_an_actions_own_steps_and_never_a_row_whose_first_enter_registers():
    """A(4): Camera Set. Memory's "M1", Reg. Custom Shoot Set's "C1" register at once: never a seen step."""
    assert info_of(FORMAT, FORMAT_SEEN)["steps_seen"] == ["Slot 1"]
    assert "do not name" in owner({**FORMAT_DECISION, "steps_seen": {FORMAT: ["Slot 2"]}})["refusals"][0]
    assert "only an action" in owner({"rows": ["Bluetooth Function"], "options": {"Bluetooth Function": ["On"]},
                                      "steps_seen": {"Bluetooth Function": ["On"]}})["refusals"][0]
    got = owner({"rows": [MEMORY], "options": {MEMORY: ["M1"]}, "confirm": [MEMORY], "steps_seen": {MEMORY: ["M1"]}})
    assert "registers or acts" in got["refusals"][0]
    # its step may still be named, as the run's armed last press (final), never before it
    assert info_of(MEMORY, {"rows": [MEMORY], "options": {MEMORY: ["M1"]}, "confirm": [MEMORY]})["options"] == ["M1"]
    assert safety.owner_enter("Camera Set. Memory", safety.LIFT_ACTION, "dialog", "M1", "Register? M1", ["M1"],
                              ["M1"]) == ("", "final")
    # owner_enter's own word on it: even marked seen on a plain list, a registering row's step is final
    assert safety.owner_enter("Camera Set. Memory", safety.LIFT_ACTION, "list", "M1", "Camera Set. Memory M1 M2",
                              ["M1"], ["M1"]) == ("", "final")
    assert safety.arm_refused("Camera Set. Memory", safety.LIFT_ACTION, "step", "list", "M1", "", True)


def test_a_never_choose_option_needs_link_loss_and_language_none_ever():
    """Finding 8 too: Access Authen. and Wi-Fi Direct are never-choose rows."""
    assert safety.never_choose("Access Authen.") and safety.never_choose("Wi-Fi Direct Settings")
    for row, opt in (("Wired LAN Connect", "Off"), ("Access Authen. Settings", "Off")):
        assert "link_loss" in owner({"rows": [row], "options": {row: [opt]}})["refusals"][0]
        assert info_of(row, {"rows": [row], "options": {row: [opt]}, "link_loss": True})["options"] == [opt]
    lang = owner({"rows": ["Language"], "options": {"Language": ["English"]}, "link_loss": True},
                 places=PLACES + [("Setup", "Area", "Language")])
    assert "whatever a decision says" in lang["refusals"][0]
    assert "no option to choose" in owner({"rows": ["Display Serial Number"],
                                           "options": {"Display Serial Number": ["On"]}})["refusals"][0]


def test_a_credentials_rows_options_are_its_own_listed_values_on_its_own_list_alone():
    """Finding 8; N49: a credentials row that is no never-choose row takes no option at all."""
    info = {"class": safety.LIFT_CREDENTIALS, "label": "Access Authen.", "options": ["Off"]}
    assert safety.owner_values_refused(info, ["On", "Off"]) == ""
    assert safety.owner_values_refused(info, [])
    assert owner({"rows": ["Access Authen. Settings"], "options": {"Access Authen. Settings": ["Shift"]},
                  "link_loss": True})["refusals"]                                           # a key's word
    said = owner({"rows": ["Password Setting"], "options": {"Password Setting": ["On"]}, "link_loss": True})["refusals"]
    assert said and "credentials row" in said[0], said


# ---------------------------------------------------------------- the Enter inside a row (A, findings 1, 5, 8)

def test_inside_an_action_any_enter_may_be_the_final_one():
    """A(1) and A(4): a named step is a step only where the decision marks it seen, on a screen that is no dialog or
    notice and reads as no question once its own title is off; otherwise "final", the armed last press."""
    enter = safety.owner_enter
    assert enter("Format", safety.LIFT_CARDS, "list", "Slot 1", "Format Slot 1 Slot 2", ["Slot 1"], ["Slot 1"]) == \
        ("", "step")
    assert enter("Format", safety.LIFT_CARDS, "list", "Slot 1", "Format Slot 1 Slot 2", ["Slot 1"]) == ("", "final")
    for kind, text in (("dialog", "Format Slot 1 Slot 2"), ("notice", "Format Slot 1 Slot 2"),
                       ("list", "Format Slot 1? Slot 2"), ("list", "Slot 1 Slot 2 All data will be deleted"),
                       ("list", "Slot 1 Format Slot 2 Format")):
        assert enter("Format", safety.LIFT_CARDS, kind, "Slot 1", text, ["Slot 1"], ["Slot 1"]) == ("", "final"), \
            (kind, text)
    for kind, lit, text in (("list", "Slot 2", "Format Slot 1 Slot 2"), ("dialog", "Enter", SURE),
                            ("dialog", "Cancel", SURE), ("dialog", "Delete", "Delete? Delete Cancel")):
        assert enter("Format", safety.LIFT_CARDS, kind, lit, text, ["Slot 1"], ["Slot 1"]) == ("", "confirm")
    assert enter("Save/Load Settings", safety.LIFT_ACTION, "submenu", "Load", "Save Load", ["Save"], ["Save"])[0]


def test_the_title_comes_off_once_and_only_where_it_leads():
    assert safety._title_off("Format Slot 1 Slot 2", "Format").strip() == "Slot 1 Slot 2"
    assert safety._title_off("Formatting Slot 1", "Format").startswith("Formatting")
    assert safety._title_off("Slot 1 Format", "Format") == "Slot 1 Format"
    assert safety.confirmation(safety._title_off(SURE, "Format"))           # the question stays a question
    # R19: the row's name comes off once, as the leading title alone; the second "Format" stays, so a seen step on
    # such a screen is no step but the armed last press
    assert safety._title_off("Format Slot 1 Slot 2 Format", "Format").strip() == "Slot 1 Slot 2 Format"
    for text in ("Format Slot 1 Format Enter Cancel", "Format Slot 1 Slot 2 Format", "Format Slot 1 Format"):
        assert safety.owner_enter("Format", safety.LIFT_CARDS, "list", "Slot 1", text, ["Slot 1"], ["Slot 1"]) == \
            ("", "final"), text


@pytest.mark.parametrize("text,pair", [
    ("Select REC Folder 100MSDCF Enter Cancel", True), ("100MSDCF 101MSDCF OK Cancel", True),
    ("100MSDCF Execute  Cancel", True), ("100MSDCF Yes Cancel", True), ("100MSDCF ОК Cаncel", True),
    ("Select REC Folder 100MSDCF 101MSDCF", False), ("Select REC Folder 100MSDCF Cancel", False),
    ("100MSDCF Enter", False), ("100MSDCF Entertain Cancellation", False)])
def test_a_seen_steps_screen_with_a_dialogs_two_buttons_is_no_step(text, pair):
    """Residue A3: a question whose "?" OCR dropped, read as a list, still shows its two buttons: the seen step is no
    step there, only the run's armed last press."""
    row = "Select REC Folder"
    assert bool(safety.confirm_pair(text, row)) is pair, text
    got = safety.owner_enter(row, safety.LIFT_ACTION, "list", "100MSDCF", text, ["100MSDCF"], ["100MSDCF"])
    assert got == ("", "final" if pair else "step"), (text, got)
    # the row's own action word with Cancel: Delete's two buttons, its title off first
    assert safety.confirm_pair("Delete Slot 1 Delete Cancel", "Delete")
    assert not safety.confirm_pair("Delete Slot 1 Slot 2 Cancel", "Delete")


@pytest.mark.parametrize("row,cls,text,lit", [
    ("Format", safety.LIFT_CARDS, SURE, "Enter"), ("Delete", safety.LIFT_CARDS, "Delete? Delete Cancel", "Delete"),
    ("Setting Reset", safety.LIFT_ACTION, "Reset camera settings? Enter Cancel", "Enter"),
    ("Reset Network Set.", safety.LIFT_ACTION, "Reset network settings? Enter Cancel", "OK"),
    ("SSID/PW Reset", safety.LIFT_ACTION, "SSID/PW Reset Reset? OK Cancel", "OK")])
def test_a_confirmation_is_armed_on_its_own_unstripped_text_with_a_confirm_button_lit(row, cls, text, lit):
    """Finding 1(d) and finding 5: only on a dialog or a notice, a confirm button lit, the text that action's own."""
    assert safety.arm_refused(row, cls, "confirm", "dialog", lit, text, confirm=True, link_loss=True) == ""
    assert safety.arm_refused(row, cls, "confirm", "submenu", lit, text, confirm=True, link_loss=True)
    assert safety.arm_refused(row, cls, "confirm", "dialog", "Slot 1", text, confirm=True, link_loss=True)
    assert safety.arm_refused(row, cls, "confirm", "dialog", lit, "Drive Mode Single Shooting", confirm=True,
                              link_loss=True)
    assert safety.arm_refused(row, cls, "confirm", "dialog", lit, text, confirm=False, link_loss=True)


def test_each_armed_press_is_armed_only_as_its_own_rules_say():
    """N01-N12 in the layer they live in: arm_refused's every branch, each check on its own."""
    arm, C, A, F = safety.arm_refused, safety.LIFT_CARDS, safety.LIFT_ACTION, safety.LIFT_FIXED
    assert "under \"confirm\"" in arm("Format", C, "confirm", "dialog", "Enter", SURE)
    assert "link_loss" in arm("Reset Network Set.", A, "confirm", "dialog", "Enter", "Reset network settings? Enter",
                              confirm=True)
    assert arm("Save/Load Settings", A, "confirm", "dialog", "Enter", "Load the settings? Enter Cancel", confirm=True)
    # final: a named step that may act at once
    assert arm("Format", C, "final", "list", "Slot 1", "Format Slot 1 Slot 2", confirm=True) == ""
    assert arm("Format", C, "final", "list", "Slot 1", "Format Slot 1 Slot 2", confirm=False)
    assert arm("Format", C, "final", "unknown", "Slot 1", "", confirm=True)
    assert arm("Format", C, "final", "shooting", "Slot 1", "", confirm=True)
    assert arm("Format", C, "final", "list", "Save", "Load the file", confirm=True)
    assert arm("Pairing", F, "final", "list", "On", "On Off", confirm=True)
    assert "wipe the link" in arm("SSID/PW Reset", A, "final", "list", "x1", "", confirm=True)    # no link_loss
    assert safety.loses_link("SSID/PW Reset", "final") and not safety.loses_link("Format", "final")
    # open: a row whose opening acts (N06-N09)
    assert arm("Create New Folder", A, "open", "submenu", "Create New Folder", "", confirm=True) == ""
    assert "does not name it under" in arm("Create New Folder", A, "open", "submenu", "Create New Folder", "")
    assert "not a menu page" in arm("Create New Folder", A, "open", "list", "Create New Folder", "", confirm=True)
    assert "is not" in arm("Create New Folder", A, "open", "submenu", "Format", "", confirm=True)
    assert "may change the network" in arm("WPS Push", F, "open", "submenu", "WPS Push", "", confirm=True)
    assert arm("WPS Push", F, "open", "submenu", "WPS Push", "", confirm=True, link_loss=True) == ""
    assert "may change the network" in arm("Reset Network Set.", A, "open", "submenu", "Reset Network Set.", "",
                                           confirm=True)
    assert "opens to look" in arm("Format", C, "open", "submenu", "Format", "", confirm=True,
                                  place=["Shooting", "Media", "Format"])
    assert arm("Format", C, "open", "submenu", "Format", "", confirm=True) == ""        # no place: it acts on opening
    # choose (N10, N11)
    assert "link_loss" in arm("Wired LAN Connect", safety.LIFT_IDENTITY, "choose", "list", "Off", "On Off")
    assert "not an option list" in arm("Wired LAN Connect", safety.LIFT_IDENTITY, "choose", "submenu", "Off", "",
                                       link_loss=True)
    assert arm("Wired LAN Connect", safety.LIFT_IDENTITY, "choose", "list", "Off", "On Off", link_loss=True) == ""
    assert arm("Language", safety.LIFT_IDENTITY, "choose", "list", "English", "", link_loss=True)
    # step (N12): only an action's, under confirm, never a registering row's
    assert "under \"confirm\" too" in arm("Format", C, "step", "list", "Slot 1", "Format Slot 1 Slot 2")
    assert arm("Format", C, "step", "list", "Slot 1", "Format Slot 1 Slot 2", confirm=True) == ""
    assert arm("Pairing", F, "step", "list", "On", "On Off", confirm=True)
    assert arm("Format", C, "nonsense", "dialog", "Enter", SURE, True, True)


def test_owner_enter_refuses_a_firmware_screen_language_and_an_unread_or_loading_lit_text():
    """N15, N16, N17."""
    enter = safety.owner_enter
    assert "firmware" in enter("Format", safety.LIFT_CARDS, "list", "Slot 1", "Firmware Update Slot 1", ["Slot 1"])[0]
    assert "whatever a decision says" in enter("Language", safety.LIFT_IDENTITY, "list", "English", "English",
                                               ["English"])[0]
    assert enter("Format", safety.LIFT_CARDS, "list", "", "Format", ["Slot 1"])[0]
    assert enter("Save/Load Settings", safety.LIFT_ACTION, "list", "Load", "Load", ["Load"])[0]


def test_inside_a_credentials_row_enter_goes_only_on_a_named_option_of_a_list():
    row, cls = "Access Authen.", safety.LIFT_CREDENTIALS
    assert safety.owner_enter(row, cls, "list", "Off", "Access Authen. On Off", ["Off"]) == ("", "choose")
    for kind in ("unknown", "notice", "fields", "submenu", "menu"):
        assert safety.owner_enter(row, cls, kind, "Off", "Off", ["Off"])[0], kind
    assert safety.owner_enter(row, cls, "list", "On", "On Off", ["Off"])[0]


def test_the_screens_that_take_menu_alone_whatever_the_decision_says_of_values():
    """Finding 6; N50-N53: each check on its own."""
    only = safety.owner_menu_only
    assert only(safety.LIFT_FIXED, "list", "On Off", "Copyright Info", blank=True)                       # N50
    assert only(safety.LIFT_ACTION, "unknown", "A B C Done", "Format")                                   # N51
    assert only(safety.LIFT_SERIAL, "notice", "Done", "Display Serial Number")                           # N52
    assert only(safety.LIFT_CREDENTIALS, "submenu", "Access Authen. On Off", "Access Authen.")           # N53
    assert only(safety.LIFT_CREDENTIALS, "list", "Access Authen. On Off", "Access Authen.") is None
    assert only(safety.LIFT_FIXED, "submenu", f"Password {SECRET}", "Server Setting")
    assert only(safety.LIFT_ADDRESS, "notice", "MAC Address", "Display Wi-Fi Info.")
    assert only(safety.LIFT_ACTION, "notice", "Connecting to the server", "Reset Transfer Status")
    assert only(safety.LIFT_ACTION, "dialog", "SSID/PW Reset Reset? OK Cancel", "SSID/PW Reset") is None


def test_the_lifted_row_is_of_the_class_it_was_lifted_from():
    """N63: a value that reads as another class (a pairing after a connection row's name) opens nothing."""
    owner_rows = {"Wired LAN Connect": {"class": safety.LIFT_IDENTITY}}
    assert safety.owner_lifted_row("Wired LAN Connect On", owner_rows, {"Wired LAN Connect": ["On"]}) == \
        "Wired LAN Connect"
    assert safety.owner_lifted_row("Wired LAN Connect Pairing", owner_rows,
                                   {"Wired LAN Connect": ["Pairing"]}) is None
    assert safety.owner_lifted_row("Wired LAN Connect Settings", owner_rows) is None
    assert safety.owner_lifted_row("Format", {"Format": {"class": safety.LIFT_ACTION}}) is None    # it is a card's


def test_initialize_reset_network_and_ssid_pw_reset_go_only_as_that_very_armed_action():
    """A(5): SSID/PW Reset joins NEVER_ENTER and armed_wiping."""
    import drive
    for word in ("Initialize", "Reset Network Set.", "SSID/PW Reset", "SSID / PW Reset"):
        assert drive.NEVER_ENTER.search(word), word
    assert safety.armed_wiping("SSID/PW Reset", "ssid/pw reset")
    assert not safety.armed_wiping("Reset Network Set.", "ssid/pw reset")
    assert not safety.armed_wiping("Format", "initialize") and not safety.armed_wiping("", "reset network")
    text = "SSID/PW Reset Reset? OK Cancel"
    assert drive.press_refused("enter", "OK", text, "dialog", confirm=True)
    assert drive.press_refused("enter", "OK", text, "dialog", confirm=True, armed_row="Reset Network Set.")
    assert drive.press_refused("enter", "OK", text, "dialog", confirm=True, armed_row="SSID/PW Reset") == ""


# ---------------------------------------------------------------- default deny (the shipped labels)

def shipped_labels() -> list:
    import re
    out = set()
    for f in sorted((ROOT / "data" / "ILCE-1M2_fw4.00").glob("*.json*")):
        out |= set(re.findall(r'"([^"\\]{2,60})"', f.read_text(encoding="utf-8")))
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    out |= {m.get("label") for m in doc.get("menu") or []}
    out |= {x for s in doc.get("settings") or [] for x in s.get("row") or []}
    return sorted(x for x in out if isinstance(x, str) and x.strip())


def test_without_owner_the_shipped_labels_open_as_before():
    """Default deny: with no owner row given, press_refused and open_refused answer as without the new arguments."""
    import drive
    labels = [x for x in shipped_labels() if safety.never_open(x)]
    assert len(labels) > 100
    for x in labels:
        assert drive.press_refused("right", x, "", "submenu") == drive.press_refused("right", x, "", "submenu",
                                                                                    owner=None, armed_row="")
        assert drive.press_refused("right", x, "", "submenu"), x
        assert live.open_refused(x), x
        assert safety.owner_lifted_row(x, {}) is None


# ---------------------------------------------------------------- the eyes: a withheld row's frames never reach the disk (F)

class OsdLink:
    """The OSD eyes' link: osd(path) writes a picture with white text-like pixels, as camlink writes the camera's."""
    def __init__(self):
        self.written = []

    def osd(self, path):
        from PIL import Image
        image = np.zeros((480, 640, 3), np.uint8)
        image[100:140, 100:500] = 255
        Image.fromarray(image).save(path)
        self.written.append(Path(path))
        return path


def test_the_eyes_save_a_withheld_frame_black_and_poll_outside_the_run(tmp_path, monkeypatch):
    from PIL import Image
    from camkit import frames
    run = Run("eyes", root=tmp_path)
    link = OsdLink()
    eyes = frames.OsdSource(link, run)
    f = eyes.grab("plain")
    assert np.asarray(Image.open(f.path)).max() == 255 and link.written[-1] == run.dir / "_live.png"
    (run.dir / "_live.png").unlink()
    eyes.withheld = True
    f = eyes.grab("withheld")
    assert np.asarray(Image.open(f.path)).max() == 0 and f.image.max() == 255     # the picture kept in memory alone
    assert not (run.dir / "_live.png").exists() and not link.written[-1].exists()
    assert link.written[-1].parent != run.dir
    ticks = iter(range(0, 10 ** 6, 10))
    monkeypatch.setattr(frames.time, "sleep", lambda s: None)
    monkeypatch.setattr(frames.time, "monotonic", lambda: next(ticks))
    f, _ = eyes.settle(None, "settled", timeout=0.01, quiet=0.0)
    assert np.asarray(Image.open(f.path)).max() == 0
    frame = frames.Frame(image=np.full((4, 4, 3), 200, np.uint8), t=0.0)
    frame.save(tmp_path / "x.png", withheld=True)
    assert np.asarray(Image.open(tmp_path / "x.png")).max() == 0
    hdmi = frames.HdmiSource.__new__(frames.HdmiSource)
    hdmi.run, hdmi.withheld = run, True
    monkeypatch.setattr(hdmi, "latest", lambda: SimpleNamespace(image=np.full((4, 4, 3), 200, np.uint8), t=0.0,
                                                                small=None), raising=False)
    got = frames.HdmiSource.grab(hdmi, "hdmi")
    assert np.asarray(Image.open(got.path)).max() == 0


def test_the_withheld_polls_go_to_a_folder_of_the_eyes_own_removed_at_the_end(tmp_path):
    """Finding 5: no file of a predictable name in the shared temporary folder: one folder per eyes (mode 0700, made by
    tempfile.mkdtemp), the picture and camlink's .part removed after each poll, failed or not, and the folder at
    close()."""
    import os
    import tempfile
    from camkit import frames
    run = Run("eyes", root=tmp_path)
    link = OsdLink()
    eyes, other = frames.OsdFeed(run), frames.OsdFeed(run)
    eyes.attach(link)
    other.attach(link)
    eyes.withheld = other.withheld = True
    eyes.peek()
    folder = link.written[-1].parent
    assert folder != Path(tempfile.gettempdir()) and folder.is_dir() and folder != run.dir
    assert str(os.getpid()) not in folder.name and list(folder.iterdir()) == []
    if os.name != "nt":
        assert folder.stat().st_mode & 0o777 == 0o700
    other.peek()
    assert link.written[-1].parent != folder                              # each eyes its own

    def broken(path):
        Path(str(path) + ".part").write_bytes(b"half a picture")
        Path(path).write_bytes(b"not a picture")
        raise RuntimeError("camlink died mid-write")
    link.osd = broken
    with pytest.raises(RuntimeError):
        eyes.peek()
    assert list(folder.iterdir()) == []                                    # removed although the poll failed
    eyes.close()
    other.close()
    assert not folder.exists() and eyes._private is None
    live_cam = SimpleNamespace(hdmi=frames.OsdFeed(run), blank=True)
    live_cam.hdmi.attach(OsdLink())
    live_cam.hdmi.withheld = True
    live_cam.hdmi.peek()
    made = live_cam.hdmi._private
    live.LiveCamera.withhold(live_cam, False)                              # the row left: the folder goes with it
    assert not made.exists() and live_cam.hdmi.withheld is False


def test_the_cameras_own_picture_of_a_withheld_row_is_fetched_into_a_folder_of_the_runs_own(tmp_path):
    """Finding 5, and main's suspect-shooting rule: the picture osd_kind fetches while a withheld row is open goes to the
    eyes' own folder, or with eyes that have none (HDMI) to one of the camera's own, removed when the row is left;
    otherwise to the shared temporary folder as before."""
    import tempfile
    from camkit import frames
    run = Run("eyes", root=tmp_path)
    class PartLink(OsdLink):                    # camlink's .part beside the picture, as a write cut short leaves it
        def osd(self, path):
            Path(str(path) + ".part").write_bytes(b"half")
            return super().osd(path)
    for eyes in (SimpleNamespace(withheld=False), frames.OsdFeed(run)):
        link = PartLink()
        cam = live.LiveCamera.__new__(live.LiveCamera)
        cam.link, cam.hdmi, cam.blank = link, eyes, False
        assert cam.osd_seen() and link.written[-1].parent == Path(tempfile.gettempdir())
        cam.withhold(True)
        cam.osd_seen()
        folder = link.written[-1].parent
        assert folder != Path(tempfile.gettempdir()) and folder.is_dir() and list(folder.iterdir()) == []
        assert folder.stat().st_mode & 0o777 == 0o700 or __import__("os").name == "nt"
        cam.withhold(False)
        assert not folder.exists()


# ---------------------------------------------------------------- the camera's own check (LiveCamera)

class Presses:
    """A link that checks nothing: it records the keys and moves the made-up camera."""
    def __init__(self, go):
        self.sent, self.go, self.menus, self.cleanups = [], go, 0, []

    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset()):
        self.sent.append(key)
        self.cleanups.append(cleanup)
        self.menus += key == "menu"
        self.go(key)


class Screens:
    """Settles onto the screens a press leads to: states {name: (kind, text, lit)}, moves {(state, key): state}; each
    frame saved as a real PNG with white text-like pixels, black where the camera set withheld (as camkit.frames' eyes
    do), and whether it was set at each settle recorded (settled)."""
    def __init__(self, tmp_path, monkeypatch, states, moves, start):
        self.states, self.moves, self.at, self.n, self.tmp = states, moves, start, 1, tmp_path
        self.withheld, self.settled = False, []
        (tmp_path / "shots").mkdir(exist_ok=True)
        monkeypatch.setattr(live.screen, "read", lambda f: SimpleNamespace(kind=self.states[self.at][0], focus="rows",
                                                                          where=self.at))
        monkeypatch.setattr(live.screen, "same_position", lambda a, b: getattr(a, "where", None) == getattr(b, "where",
                                                                                                         None))
        monkeypatch.setattr(live.screen, "same_state", lambda a, b: False)
        monkeypatch.setattr(live, "text_of", lambda cam: self.states[self.at][1])
        monkeypatch.setattr(live, "lit_text", lambda image, path: self.states[self.at][2])
        monkeypatch.setattr(live.time, "sleep", lambda s: None)

    def go(self, key):
        self.at = self.moves.get((self.at, key), self.at)

    def frame(self, tag):
        from PIL import Image
        self.n += 1
        path = self.tmp / "shots" / f"{self.n:05d}_{tag}.png"
        image = np.zeros((48, 64, 3), np.uint8)
        image[10:20, 10:50] = 255
        Image.fromarray(np.zeros_like(image) if self.withheld else image).save(path)
        return SimpleNamespace(image=image, path=path)

    def settle(self, before, tag, **kw):
        self.settled.append(self.withheld)
        return self.frame(tag), True

    def grab(self, tag, save=True):
        return self.frame(tag)

    timing = {}


FORMAT_STATES = {"page": ("submenu", "Shooting > Media Format", "Format"),
                 "slots": ("list", "Format Slot 1 Slot 2", "Slot 1"),
                 "sure": ("dialog", SURE, "Enter"), "busy": ("notice", "Formatting...", "")}
FORMAT_MOVES = {("page", "right"): "slots", ("slots", "enter"): "sure", ("sure", "enter"): "busy",
                ("sure", "menu"): "page", ("slots", "menu"): "page", ("busy", "menu"): "page"}


def camera(tmp_path, monkeypatch, info, states=FORMAT_STATES, moves=FORMAT_MOVES, start="page", label="Format"):
    """A LiveCamera given one owner row (`info`, owner_decided's), on a made-up camera and a link that checks nothing."""
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.hdmi = Screens(tmp_path, monkeypatch, states, moves, start)
    cam.link = Presses(cam.hdmi.go)
    cam.run = Run("own", root=tmp_path)
    cam.may_open, cam.network, cam.screens, cam.options, cam.values = frozenset(), frozenset(), False, {}, {}
    cam.owner, cam.permit = {label: info}, None
    cam.owner_opened = cam.owner_done = cam.blank = False
    cam.network_open = cam.address_open = cam.identity_open = cam.may_open_exact = None
    cam.presses = cam.handed = cam._seen = 0
    cam.frame = cam.hdmi.frame("start")
    cam.screen = live.screen.read(cam.frame)
    return cam


def format_info(**more) -> dict:
    return {**info_of(FORMAT, FORMAT_DECISION), **more}


def seen_info(**more) -> dict:
    return {**info_of(FORMAT, FORMAT_SEEN), **more}


def test_the_camera_opens_its_owner_row_with_right_alone_once(tmp_path, monkeypatch):
    """N26, N27 on the camera's side."""
    cam = camera(tmp_path, monkeypatch, format_info())
    for key in ("enter", "ms_right", "ms_enter"):
        with pytest.raises(safety.Refused, match="Right alone"):
            cam.press(key)
    cam.press("right")
    assert cam.network_open["owner"] and cam.network_open["class"] == safety.LIFT_CARDS
    cam.press("menu")
    assert cam.network_open is None and cam.link.sent == ["right", "menu"]
    with pytest.raises(safety.Refused, match="one owner row per run"):
        cam.press("right")


def test_the_camera_opens_no_owner_row_from_a_screen_that_is_no_menu_page(tmp_path, monkeypatch):
    """The two layers: a Right on the owner row lit on a page read as anything but a menu page, judged by the camera
    too, whatever kind it reads as."""
    for kind in ("list", "dialog", "unknown", "tiles"):
        states = {**FORMAT_STATES, "page": (kind, "Shooting > Media Format", "Format")}
        cam = camera(tmp_path, monkeypatch, format_info(), states)
        with pytest.raises(safety.Refused, match="menu page"):
            cam.press("right")
        assert cam.link.sent == [] and cam.network_open is None, kind


def test_the_camera_takes_a_seen_step_and_a_confirmation_only_with_drives_word_for_that_row_and_press(tmp_path,
                                                                                                    monkeypatch):
    """Mutation 2 (and N28): the permit names this row and this press."""
    cam = camera(tmp_path, monkeypatch, seen_info())
    cam.press("right")
    with pytest.raises(safety.Refused, match="did not allow"):
        cam.press("enter")                                          # a seen step, no permit
    for permit in ({"row": "Other", "what": "step"}, {"row": "Format", "what": "confirm"}):
        cam.permit = permit
        with pytest.raises(safety.Refused, match="did not allow"):
            cam.press("enter")
        assert cam.permit is None                                   # used up, whatever it was
    cam.permit = {"row": "Format", "what": "step"}
    cam.press("enter")                                              # Slot 1, seen: a step
    assert not cam.owner_done
    for permit in (None, {"row": "Other", "what": "confirm"}, {"row": "Format", "what": "step"}):
        cam.permit = permit
        with pytest.raises(safety.Refused):
            cam.press("enter")                                      # the confirmation
    cam.permit = {"row": "Format", "what": "confirm"}
    cam.press("enter")
    assert cam.link.sent == ["right", "enter", "enter"] and cam.owner_done
    for key in ("enter", "down", "up"):
        with pytest.raises(safety.Refused, match="armed press of the run has gone"):
            cam.press(key)
    cam.press("menu")
    assert cam.link.sent[-1] == "menu"


def test_the_camera_takes_a_step_never_seen_only_as_the_armed_final_press(tmp_path, monkeypatch):
    """A(4) on the camera's side: with no "steps_seen", Enter on the slot is the run's armed last press."""
    cam = camera(tmp_path, monkeypatch, format_info())
    cam.press("right")
    cam.permit = {"row": "Format", "what": "step"}
    with pytest.raises(safety.Refused, match="did not allow"):
        cam.press("enter")
    cam.permit = {"row": "Format", "what": "final"}
    cam.press("enter")
    assert cam.link.sent == ["right", "enter"] and cam.owner_done
    cam = camera(tmp_path, monkeypatch, seen_info())
    cam.press("right")
    cam.permit = {"row": "Format", "what": "final"}                 # a seen step drive.py arms as the last Enter
    cam.press("enter")
    assert cam.owner_done


def test_the_camera_never_takes_a_final_permit_for_a_confirmation(tmp_path, monkeypatch):
    """A permit "final" stands for a named step alone: on the action's question with Cancel lit, the camera refuses."""
    states = {**FORMAT_STATES, "sure": ("dialog", SURE, "Cancel")}
    cam = camera(tmp_path, monkeypatch, format_info(), states, start="sure")
    cam.owner_opened = True
    cam.network_open = {"row": "Format", "class": safety.LIFT_CARDS, "address": False, "owner": True, "from": None,
                        "closing": False, "menus": 0}
    cam.permit = {"row": "Format", "what": "final"}
    with pytest.raises(safety.Refused, match="did not allow"):
        cam.press("enter")
    assert cam.link.sent == []


def test_the_camera_confirms_nothing_the_decision_does_not_name_under_confirm(tmp_path, monkeypatch):
    """Mutation 1 on the camera's side: its own arm_refused, with drive's permit given."""
    cam = camera(tmp_path, monkeypatch, {**format_info(), "confirm": False}, start="sure")
    cam.owner_opened = True
    cam.network_open = {"row": "Format", "class": safety.LIFT_CARDS, "address": False, "owner": True, "from": None,
                        "closing": False, "menus": 0}
    cam.permit = {"row": "Format", "what": "confirm"}
    with pytest.raises(safety.Refused, match="the owner decision does not name"):
        cam.press("enter")
    assert cam.link.sent == []


def test_the_camera_takes_no_step_of_an_action_not_under_confirm(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, {**seen_info(), "confirm": False})
    cam.press("right")
    cam.permit = {"row": "Format", "what": "step"}
    with pytest.raises(safety.Refused, match="too"):
        cam.press("enter")
    assert cam.link.sent == ["right"]


def test_the_camera_ends_a_never_choose_choice_with_menu_alone(tmp_path, monkeypatch):
    """N70 on the camera's side: a choice that may drop the link is armed, once."""
    info = info_of("Wired LAN Connect", {"rows": ["Wired LAN Connect"], "options": {"Wired LAN Connect": ["Off"]},
                                         "link_loss": True})
    states = {"page": ("submenu", "Network > Wired LAN Wired LAN Connect", "Wired LAN Connect"),
              "list": ("list", "Wired LAN Connect On Off", "Off")}
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "list"}, label="Wired LAN Connect")
    cam.press("right")
    with pytest.raises(safety.Refused, match="did not allow"):
        cam.press("enter")
    cam.permit = {"row": "Wired LAN Connect", "what": "choose"}
    cam.press("enter")
    assert cam.owner_done
    with pytest.raises(safety.Refused, match="armed press of the run has gone"):
        cam.press("down")


@pytest.mark.parametrize("key", ["right", "left", "ms_enter", "ms_up", "c4", "Enter", " down"])
def test_inside_an_owner_row_only_up_down_menu_and_enter_go_out(tmp_path, monkeypatch, key):
    cam = camera(tmp_path, monkeypatch, format_info())
    cam.press("right")
    with pytest.raises(safety.Refused):
        cam.press(key)
    with pytest.raises(safety.Refused):
        cam.dial("front", 1)
    assert cam.link.sent == ["right"]


def test_the_camera_refuses_enter_on_initialize_and_its_kin_by_itself(tmp_path, monkeypatch):
    """A(6): LiveCamera's own NEVER_ENTER, beside drive.py's."""
    states = {"page": ("submenu", "Setup > Reset/Save Settings Setting Reset", "Setting Reset"),
              "items": ("dialog", "Setting Reset Camera Settings Reset Initialize", "Initialize")}
    info = info_of(SETTING_RESET, {"rows": [SETTING_RESET], "confirm": [SETTING_RESET]})
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "items"}, label="Setting Reset")
    cam.press("right")
    cam.permit = {"row": "Setting Reset", "what": "confirm"}
    with pytest.raises(safety.Refused, match="cursor is on|confirm button"):
        cam.press("enter")
    assert cam.link.sent == ["right"]
    # a screen reading Reset Network Set. takes no Enter unless that very action is armed
    states = {"page": ("submenu", "Shooting > Media Format", "Format"),
              "sure": ("dialog", "Reset network settings? Format Enter Cancel", "Enter")}
    cam = camera(tmp_path, monkeypatch, format_info(), states, {("page", "right"): "sure"})
    cam.press("right")
    cam.permit = {"row": "Format", "what": "confirm"}
    with pytest.raises(safety.Refused, match="no armed confirmation of that very action"):
        cam.press("enter")
    assert cam.link.sent == ["right"]


CREDS_STATES = {"page": ("submenu", "Network > Network Option Access Authen. Info", "Access Authen. Info"),
                "info": ("notice", f"User Name {USER} Password {SECRET} OK", "OK"), "shot": ("shooting", "", "")}
CREDS_MOVES = {("page", "right"): "info", ("info", "menu"): "page", ("page", "menu"): "shot"}
DRIVE_CREDS = {("page", "right"): "info", ("info", "menu"): "page"}       # drive.py's own first MENU opens the menu


def test_a_withheld_row_has_the_eyes_save_black_from_its_opening_no_reader_and_menu_alone(tmp_path, monkeypatch):
    """Finding 2 and F: the eyes are told before the opened screen is settled and saved."""
    from PIL import Image
    info = info_of("Access Authen. Info", {"rows": ["Access Authen. Info"]})
    cam = camera(tmp_path, monkeypatch, info, CREDS_STATES, CREDS_MOVES, label="Access Authen. Info")
    page = cam.frame.path
    cam.press("right")
    assert cam.hdmi.settled == [True] and cam.blank and cam.hdmi.withheld and vlm.HELD and cam.identity_open
    assert np.asarray(Image.open(cam.frame.path)).max() == 0                 # the opened screen: black
    assert np.asarray(Image.open(page)).max() == 255                         # the page before it: as it was
    with pytest.raises(safety.Refused, match="MENU"):
        cam.press("down")
    cam.press("menu")                   # back on the page: its frames are not read, so only the shooting screen frees it
    assert cam.blank and cam.network_open and np.asarray(Image.open(cam.frame.path)).max() == 0
    cam.press("menu")
    assert not cam.blank and not cam.hdmi.withheld and cam.network_open is None and vlm.HELD is None
    assert cam.link.sent == ["right", "menu", "menu"]
    logged = info_of("Access Authen. Info", {"rows": ["Access Authen. Info"], "values": "logged"})
    cam = camera(tmp_path, monkeypatch, logged, CREDS_STATES, CREDS_MOVES, label="Access Authen. Info")
    cam.press("right")
    assert not cam.blank and np.asarray(Image.open(cam.frame.path)).max() == 255
    with pytest.raises(safety.Refused, match="MENU"):                       # logged: the text kept, never more keys
        cam.press("down")


def test_a_row_that_acts_on_opening_opens_only_with_drives_word_on_the_camera(tmp_path, monkeypatch):
    info = info_of(CREATE, {"rows": [CREATE], "confirm": [CREATE]})
    states = {"page": ("submenu", "Shooting > File Create New Folder", "Create New Folder"),
              "made": ("notice", "Done", "OK")}
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "made"}, label="Create New Folder")
    with pytest.raises(safety.Refused, match="acts as soon as it opens"):
        cam.press("right")
    cam.permit = {"row": "Create New Folder", "what": "open"}
    cam.press("right")
    assert cam.link.sent == ["right"] and cam.owner_done
    with pytest.raises(safety.Refused, match="armed press of the run has gone"):
        cam.press("enter")


def test_the_camera_counts_a_press_handed_only_once_its_own_checks_let_it_go(tmp_path, monkeypatch):
    """Finding 4 and N34 on the camera's side: drive.py tells a press that went from one refused before it by handed."""
    cam = camera(tmp_path, monkeypatch, format_info())
    cam.press("right")
    assert cam.handed == 1
    with pytest.raises(safety.Refused):
        cam.press("enter")                                          # no permit: refused before the link
    assert cam.handed == 1 and cam.link.sent == ["right"]


def test_the_camera_after_an_armed_reset_reads_and_cancels_its_question_with_menu_alone(tmp_path, monkeypatch):
    """The third review's rule on the camera's side: after the armed opening of Reset Network Set. its question takes
    no key but MENU; drive.py's read after it (refresh) presses nothing, and its cancel (cancel_to_menu) is one cleanup
    MENU each, which a STOP never holds."""
    info = info_of(RESET_NET, {"rows": [RESET_NET], "confirm": [RESET_NET], "link_loss": True})
    states = {"page": ("submenu", "Network > Network Option Reset Network Set.", "Reset Network Set."),
              "question": ("dialog", "Reset network settings? Enter Cancel", "Enter")}
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "question", ("question", "menu"): "page"},
                 label="Reset Network Set.")
    with pytest.raises(safety.Refused, match="acts as soon as it opens"):
        cam.press("right")
    cam.permit = {"row": "Reset Network Set.", "what": "open"}
    cam.press("right")
    assert cam.owner_done and cam.link.sent == ["right"]
    assert cam.refresh("after-armed").kind == "dialog" and cam.link.sent == ["right"]
    assert safety.own_question("dialog", states["question"][1], "Reset Network Set.")
    for key in ("enter", "down", "up"):
        cam.permit = {"row": "Reset Network Set.", "what": "confirm"}
        with pytest.raises(safety.Refused, match="armed press of the run has gone"):
            cam.press(key)
    assert cam.link.sent == ["right"]
    cam.run.request_stop("a STOP while the question is open")
    cam.cancel_to_menu(1)
    assert cam.link.sent == ["right", "menu"] and cam.link.cleanups[-1] is True and cam.read().kind == "submenu"


def test_own_question_reads_a_dialog_or_notice_that_asks():
    """(e)'s test of the screen, in its layer."""
    q = safety.own_question
    assert q("dialog", "Reset network settings? Enter Cancel", "Reset Network Set.")
    assert q("notice", "SSID/PW Reset Reset? OK Cancel", "SSID/PW Reset")
    assert q("dialog", "Format the memory card? Enter Cancel", "Reset Network Set.")      # asks, and confirms: yes
    for kind, text in (("list", "Reset network settings? Enter Cancel"), ("submenu", "Reset Network Set."),
                       ("dialog", "Format the memory card. Enter Cancel"),                  # no "?", not its own
                       ("notice", "Resetting the network settings"), ("dialog", "Wi-Fi Frequency Band 2.4GHz 5GHz"),
                       ("dialog", "Turn on? OK Cancel"), ("dialog", "")):
        assert not q(kind, text, "Reset Network Set."), (kind, text)


def test_without_an_owner_row_the_camera_opens_none(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, format_info())
    cam.owner = {}
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press("right")
    assert cam.link.sent == []


# ---------------------------------------------------------------- drive.py (its camera a fake that checks nothing)

@pytest.fixture
def scope_file(own_runs, monkeypatch):
    from proving import base
    import runner
    pass1 = own_runs / TEST_CAMERA / "kit2_pass1"
    monkeypatch.setattr(base, "PASS1", pass1)
    monkeypatch.setattr(runner, "known_places", lambda model=None: PLACES)

    def write(*decisions):
        pass1.mkdir(parents=True, exist_ok=True)
        f = pass1 / "pass2_scope_draft.json"
        f.write_text(json.dumps({"prove": [], "exclude": {}, "decisions": [{**OWNER, **d} for d in decisions]}),
                     encoding="utf-8")
        return f
    return write


def drive_run(tmp_path, monkeypatch, scope_file, presses, path, decision, states, moves, start="page", more=(),
              fails=None, values=None, places=None, extra=None, blacks=(), refresh_fails=False, restored=True,
              close_exits=False, typed="auto", walk=False, put_back_fails=False):
    """drive.py's main() with --owner on a made-up camera moving through `states` ({name: (kind, text, lit)}) by
    `moves`; the camera checks nothing (fails(state, key, cam) may raise in its press, after it was handed or before).
    Returns (the keys the camera was asked to press, drive.jsonl's last line, the run's events, the exit status, the
    restore's steps, the console, the permits given). places collects the places go_to was asked for; extra (a dict)
    gets what the restore's check was given ("restore_kw") and, at each press, whether RESTORE_BY_HAND was there
    ("marked"). blacks: the states whose frame is black; refresh_fails: the read after a press raises; restored: the
    restore's check's verdict; close_exits: the close before the restore gives up (its SystemExit). typed: what the
    person types at the terminal ("auto": the owner row's name; None: no terminal at all); walk: the real walk to a
    deep owner row (drive.owner_walk) instead of none; put_back_fails: the restore's upload raises after the download."""
    import drive as D
    from runner import EXIT_UNRESTORED
    scope_file(decision)
    run = Run("kit2_drive", root=tmp_path)
    sent, at, restore, permits = [], {"s": start}, [], []
    extra = {} if extra is None else extra

    class Link:
        def __init__(self, r):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def press(self, key, **kw):
            sent.append(("link", key))

        def download(self, tag):
            return tmp_path / f"{tag}.DAT"

    class Cam:
        handed, permit, blank = 0, None, False

        @property
        def frame(self):
            return SimpleNamespace(path=tmp_path / f"0000{len(sent)}_{at['s']}.png", image=None)

        def read(self):
            return SimpleNamespace(kind=states[at["s"]][0], where=at["s"])

        def press(self, key, **kw):
            permits.append(self.permit)
            extra.setdefault("marked", []).append(restore_pending(tmp_path) is not None)
            self.permit = None
            if fails:
                fails(at["s"], key, self)
            self.handed += 1
            sent.append(("cam", key))
            at["s"] = moves.get((at["s"], key), at["s"])

        def refresh(self, tag):
            extra.setdefault("refreshes", []).append(tag)
            if refresh_fails:
                raise RuntimeError("the eyes' feed is gone")
            return self.read()

        def cancel_to_menu(self, tries=3):
            for _ in range(tries):
                if states[at["s"]][0] in ("menu", "tiles", "shooting"):
                    return True
                sent.append(("cam", "menu"))            # a cleanup MENU, as LiveCamera's own
                at["s"] = moves.get((at["s"], "menu"), at["s"])
            return states[at["s"]][0] in ("menu", "tiles", "shooting")

    def go_to(*a, **k):
        if places is not None:
            places.append(k.get("place"))
        return True

    def close_for_restore(cam, link):
        restore.append("closed")
        if close_exits:
            raise SystemExit(EXIT_UNRESTORED)

    def restore_checked(r, e, before, **kw):
        extra["restore_kw"] = kw
        return restored

    def put_back(link, e, before):
        if put_back_fails:
            raise RuntimeError("the upload was not answered")
        return e

    class Terminal:
        def isatty(self):
            return typed is not None

    def answer(prompt=""):
        extra.setdefault("asked", []).append(prompt)
        return path[-1] if typed == "auto" else typed
    ending = SimpleNamespace(after=tmp_path / "after.DAT", changes=[], uploaded=False)
    for name, value in (("check_readers", lambda: None), ("load_scan", lambda scan: ([], {})), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None,
                                                                       grab=lambda save=False: None, close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("Link", Link), ("LiveCamera", lambda *a, **k: extra.setdefault("cam", Cam())),
                        ("find_position", lambda cam, cycle, model: 0), ("go_to", go_to),
                        ("enter_any", lambda cam, path, i: extra.setdefault("flag_at_walk", getattr(cam, "owner_only",
                                                                                                      False))),
                        ("bar_at", lambda cam, y: False),
                        ("screen_text", lambda cam, grip: states[at["s"]][1]),
                        ("screen_lines", lambda cam, grip: states[at["s"]][1].split("  ")),
                        ("highlighted", lambda image, path: states[at["s"]][2]),
                        ("same_position", lambda a, b: getattr(a, "where", 1) == getattr(b, "where", 2)),
                        ("network_values", lambda rows, model: {r: (values or {}).get(r, []) for r in rows}),
                        ("known_labels", lambda model: set()),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("black", lambda f: at["s"] in blacks),
                        ("close_for_restore", close_for_restore),
                        ("session", SimpleNamespace(ended=lambda link, before, show=30, **kw: restore.append("ended") or extra.update(ended_kw={"show": show, **kw})
                                                    or ending,
                                                    put_back=put_back)),
                        ("restore_checked", restore_checked)):
        monkeypatch.setattr(D, name, value)
    if not walk:
        monkeypatch.setattr(D, "owner_walk", lambda cam, path, grip, place=(): extra.setdefault(
            "flag_at_walk", getattr(cam, "owner_only", False)) and "")
    monkeypatch.setattr(D.sys, "stdin", Terminal())
    monkeypatch.setattr(D, "input", answer, raising=False)
    argv = ["drive.py", "--owner", *[x for p in path for x in ("--path", p)], *[x for p in presses for x in ("--press", p)]]
    monkeypatch.setattr(sys, "argv", argv + list(more))
    out = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out):
        try:
            D.main()
        except SystemExit as e:
            code = e.code
    lines = (run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines() if (run.dir / "drive.jsonl").exists() \
        else []
    logged = (run.dir / "events.jsonl").read_text(encoding="utf-8") if (run.dir / "events.jsonl").exists() else ""
    return ([s[1] for s in sent if s[0] == "cam"], json.loads(lines[-1]) if lines else {}, logged, code, restore,
            out.getvalue(), permits)


def test_drive_confirms_format_after_a_seen_step(tmp_path, monkeypatch, scope_file):
    """A(4), the steps_seen way: the slot's Enter goes as a step, the question's Enter as the armed last press."""
    places = []
    pressed, line, logged, code, restore, out, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Slot", "enter:memory card"], ["Format"], FORMAT_SEEN,
        FORMAT_STATES, FORMAT_MOVES, more=["--confirm"], places=places)
    assert pressed == ["menu", "right", "enter", "enter"] and code == 0 and restore == ["closed", "ended"]
    assert permits[2:] == [{"row": "Format", "what": "step"}, {"row": "Format", "what": "confirm"}]
    assert [list(x) for x in places] == [["Shooting", "Media"]]                         # E: its tab and group
    assert [s["armed"] for s in line["screens"] if "armed" in s] == ["confirm"]      # N65: the armed press went
    assert '"owner_decided"' in logged and line["owner"][FORMAT]["class"] == safety.LIFT_CARDS


def test_drive_confirms_format_with_the_slots_enter_as_the_armed_last_press(tmp_path, monkeypatch, scope_file):
    """A(4), the default way: no steps_seen, the slot's Enter is the run's armed last press ("final")."""
    pressed, line, _, code, restore, _, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Slot"], ["Format"], FORMAT_DECISION, FORMAT_STATES,
        FORMAT_MOVES, more=["--confirm"])
    assert pressed == ["menu", "right", "enter"] and code == 0 and restore == ["closed", "ended"]
    assert permits[-1] == {"row": "Format", "what": "final"}
    assert [s["armed"] for s in line["screens"] if "armed" in s] == ["final"]


@pytest.mark.parametrize("decision,presses", [
    (FORMAT_DECISION, ["right", "enter:Slot", "enter:memory card"]),        # a step never seen, then more
    (FORMAT_DECISION, ["right", "enter:Slot", "menu", "menu"]),             # the reviewer's: it formats at once
    (FORMAT_SEEN, ["right", "enter:Slot", "menu"]),                          # seen, but no Enter after it: final
])
def test_drive_sends_no_step_that_may_act_before_the_last_press(tmp_path, monkeypatch, scope_file, decision, presses):
    """A(1) and A(4) on drive's side: the reviewer's Format that formats on the slot's Enter goes nowhere mid-run."""
    pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, presses, ["Format"],
                                                        decision, FORMAT_STATES, FORMAT_MOVES, more=["--confirm"])
    assert pressed == ["menu", "right"] and line["completed"] is False and restore == ["closed", "ended"], pressed
    assert "last press" in out


def test_the_reviewed_finding_no_confirmation_goes_without_confirm_or_as_no_last_press(tmp_path, monkeypatch,
                                                                                     scope_file):
    """Finding 1 and A(2): the reviewers' decisions (Format bare, Enter or Continue among its options) are refused
    before anything connects; the sound one sends nothing without --confirm, nor a confirmation as no last press."""
    import drive as D
    for options in (["Slot 1", "Enter"], ["Slot 1", "Continue"]):
        scope_file({"rows": [FORMAT], "options": {FORMAT: options}, "confirm": [FORMAT]})
        monkeypatch.setattr(D, "load_scan", lambda scan: ([], {}))
        monkeypatch.setattr(sys, "argv", ["drive.py", "--owner", "--path", "Format", "--press", "right"])
        with pytest.raises(SystemExit, match="go-ahead|button"):
            D.main()
    presses = ["right", "enter:Slot", "enter:memory card", "menu"]
    for decision in (FORMAT_DECISION, FORMAT_SEEN):
        for more in ([], ["--confirm"]):
            pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, presses, ["Format"],
                                                                decision, FORMAT_STATES, FORMAT_MOVES, more=more)
            want = ["menu", "right", "enter"] if more and decision is FORMAT_SEEN else ["menu", "right"]
            assert pressed == want, (decision, more, pressed)
            assert line["completed"] is False and restore == ["closed", "ended"] and code == 0


def test_drive_refuses_the_confirmation_of_a_row_not_under_confirm(tmp_path, monkeypatch, scope_file):
    """Mutations 1 and 3 on drive's side: --confirm, the last press, a confirmation screen: still refused."""
    pressed, line, _, _, _, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:memory card"],
                                               ["Format"], {"rows": [FORMAT]}, FORMAT_STATES,
                                               {("page", "right"): "sure"}, more=["--confirm"])
    assert pressed == ["menu", "right"] and line["completed"] is False and "the owner decision does not name" in out


FOLDER_STATES = {"page": ("submenu", "Shooting > File Select REC Folder", "Select REC Folder"),
                 "list": ("list", "Select REC Folder 100MSDCF 101MSDCF", "100MSDCF"), "done": ("submenu", "x", "OK")}
FOLDER_DECISION = {"rows": [FOLDER], "options": {FOLDER: ["100MSDCF"]}, "steps_seen": {FOLDER: ["100MSDCF"]},
                   "confirm": [FOLDER]}


def test_drive_refuses_a_step_and_a_choice_without_confirm_where_press_refused_would_not(tmp_path, monkeypatch,
                                                                                       scope_file):
    """Mutation 5 and N18: --confirm checked inside the row by drive itself, on screens that read as no confirmation."""
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:100", "enter:OK"],
                                  ["Select REC Folder"], FOLDER_DECISION, FOLDER_STATES,
                                  {("page", "right"): "list", ("list", "enter"): "done"})
    assert pressed == ["menu", "right"] and line["completed"] is False
    wired = {"page": ("submenu", "Network > Wired LAN Wired LAN Connect", "Wired LAN Connect"),
             "list": ("list", "Wired LAN Connect On Off", "Off")}
    decision = {"rows": ["Wired LAN Connect"], "options": {"Wired LAN Connect": ["Off"]}, "link_loss": True}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Off"], ["Wired LAN Connect"],
                                  decision, wired, {("page", "right"): "list"})
    assert pressed == ["menu", "right"] and line["completed"] is False
    # N70: with --confirm, a never-choose choice still goes only as the last press
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Off", "menu"],
                                  ["Wired LAN Connect"], decision, wired, {("page", "right"): "list"},
                                  more=["--confirm"])
    assert pressed == ["menu", "right"] and line["completed"] is False


def test_drive_keeps_the_initialize_check_unless_the_armed_row_is_that_very_action():
    """Mutation 4: armed for Format, a screen reading Initialize is refused; armed for Initialize, Reset Network Set.'s
    question is refused."""
    import drive
    text = "Initialize? All settings will be reset. Enter Cancel"
    assert drive.press_refused("enter", "Enter", text, "dialog", confirm=True)
    assert drive.press_refused("enter", "Enter", text, "dialog", confirm=True, armed_row="Format")
    assert drive.press_refused("enter", "Enter", text, "dialog", confirm=True, armed_row="Reset Network Set.")
    assert drive.press_refused("enter", "Enter", text, "dialog", confirm=True, armed_row="Initialize") == ""
    net = "Reset network settings? Enter Cancel"
    assert drive.press_refused("enter", "Enter", net, "dialog", confirm=True, armed_row="Initialize")
    assert drive.press_refused("enter", "Enter", net, "dialog", confirm=True, armed_row="Reset Network Set.") == ""
    assert drive.press_refused("enter", "Initialize", text, "dialog", confirm=True, armed_row="Initialize")
    # the confirmation check stays main's, on the whole text as read (finding 1a)
    assert "confirmation" in drive.press_refused("enter", "Enter", SURE, "dialog", armed_row="Format",
                                                 owner={"Format": format_info()})


def test_drive_keeps_the_never_open_check_on_the_armed_press(tmp_path, monkeypatch, scope_file):
    """Mutation 7: "Reset" reads as a confirm button of Setting Reset, and is never-open: refused."""
    import drive
    info = info_of(SETTING_RESET, {"rows": [SETTING_RESET], "confirm": [SETTING_RESET]})
    text = "Reset camera settings? Reset Cancel"
    assert safety.arm_refused("Setting Reset", info["class"], "confirm", "dialog", "Reset", text, True, True) == ""
    assert drive.press_refused("enter", "Reset", text, "dialog", confirm=True, armed_row="Setting Reset",
                               owner={"Setting Reset": info})
    states = {"page": ("submenu", "Setup > Reset/Save Settings Setting Reset", "Setting Reset"),
              "sure": ("dialog", text, "Reset")}
    pressed, *_, code, restore, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Reset"],
                                                 ["Setting Reset"], {"rows": [SETTING_RESET], "confirm": [SETTING_RESET]},
                                                 states, {("page", "right"): "sure"}, more=["--confirm"])
    assert pressed == ["menu", "right"] and code == 0 and restore == ["closed", "ended"]


def test_drive_opens_the_owner_row_with_right_alone_once_from_a_menu_page(tmp_path, monkeypatch, scope_file):
    """N22, N23, N24 on drive's side, its camera checking nothing."""
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["enter:Format"], ["Format"], FORMAT_DECISION,
                                  FORMAT_STATES, FORMAT_MOVES, more=["--confirm"])
    assert pressed == ["menu"] and line["completed"] is False                          # N22
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "menu", "right"], ["Format"],
                                  FORMAT_DECISION, FORMAT_STATES, FORMAT_MOVES)
    assert pressed == ["menu", "right", "menu"] and line["completed"] is False          # N23
    states = {**FORMAT_STATES, "page": ("list", "Shooting > Media Format", "Format")}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Format"], FORMAT_DECISION, states,
                                  FORMAT_MOVES)
    assert pressed == ["menu"] and line["completed"] is False                          # N24


def test_drive_opens_the_owner_row_only_in_its_own_tab_and_group(tmp_path, monkeypatch, scope_file):
    """E: the page shown must read the decision's tab and group, before the walk to the row and before its opening."""
    for text in ("Playback > Media Format", "Shooting > File Format", "", "Format"):
        states = {**FORMAT_STATES, "page": ("submenu", text, "Format")}
        pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Format"],
                                                            FORMAT_DECISION, states, FORMAT_MOVES)
        assert pressed == ["menu"] and line["completed"] is False and restore == ["closed", "ended"], text
    # a row under a submenu: its tab and group are read on the top-level page, before the walk to it
    deep = "Shooting > File > File/Folder Settings > Format"
    for text, want in (("Playback > Delete File/Folder Settings", ["menu"]),
                       ("Shooting > File File/Folder Settings", ["menu", "right"])):
        states = {"page": ("submenu", text, "Format"), "slots": ("list", "Format Slot 1 Slot 2", "Slot 1")}
        # a Format at a place nobody has seen open acts on opening: its Right is the run's armed last press
        pressed, line, *_, permits = drive_run(tmp_path, monkeypatch, scope_file, ["right"],
                                               ["File/Folder Settings", "Format"], {"rows": [deep], "confirm": [deep]},
                                               states, {("page", "right"): "slots"}, more=["--confirm"])
        assert pressed == want, (text, pressed)
        assert permits[-1] == ({"row": "Format", "what": "open"} if len(want) == 2 else None)
    # a top-level row: read again at its opening, after presses that may have moved the page
    states = {**FORMAT_STATES, "other": ("submenu", "Playback > Delete Format", "Format")}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["down", "right"], ["Format"], FORMAT_DECISION,
                                  states, {**FORMAT_MOVES, ("page", "down"): "other"})
    assert pressed == ["menu", "down"] and line["completed"] is False


RESET_STATES = {"page": ("submenu", "Network > Network Option Reset Network Set.", "Reset Network Set."),
                "gone": ("unknown", "", "")}
RESET_MOVES = {("page", "right"): "gone"}
RESET_DECISION = {"rows": [RESET_NET], "confirm": [RESET_NET], "link_loss": True}


def test_drive_opens_reset_network_set_as_its_armed_last_press_and_leaves_the_restore_by_hand(tmp_path, monkeypatch,
                                                                                            scope_file):
    """D: no frame records what Right on it shows, so its opening is the armed press; then RESTORE_BY_HAND."""
    from exit_status import EXIT_RESTORE_BY_HAND
    for presses, more in ((["right"], []), (["right", "menu"], ["--confirm"])):
        pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, presses, ["Reset Network Set."],
                                      RESET_DECISION, RESET_STATES, RESET_MOVES, more=more)
        assert pressed == ["menu"] and line["completed"] is False, (presses, more)
    pressed, line, logged, code, restore, out, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
        RESET_MOVES, more=["--confirm"])
    assert pressed == ["menu", "right"] and code == EXIT_RESTORE_BY_HAND and restore == []
    assert permits[-1] == {"row": "Reset Network Set.", "what": "open"}
    assert line["restore"] == "by hand" and '"restore_by_hand"' in logged and "upload_check.py" in out
    pending = restore_pending(tmp_path)
    assert pending["run"] == "kit2_drive" and pending["start"] == "before.DAT"      # the fake link's download


def test_drive_opens_ssid_pw_reset_as_its_armed_last_press_and_leaves_the_restore_by_hand(tmp_path, monkeypatch,
                                                                                        scope_file):
    from exit_status import EXIT_RESTORE_BY_HAND
    states = {"page": ("submenu", "Network > Wi-Fi SSID/PW Reset", "SSID/PW Reset"), "gone": ("unknown", "", "")}
    pressed, line, _, code, restore, _, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["SSID/PW Reset"],
        {"rows": [SSID_RESET], "confirm": [SSID_RESET], "link_loss": True}, states, {("page", "right"): "gone"},
        more=["--confirm"])
    assert pressed == ["menu", "right"] and code == EXIT_RESTORE_BY_HAND and restore == []


def test_a_refused_armed_press_closes_and_restores_and_any_other_failure_does_not(tmp_path, monkeypatch, scope_file):
    """Finding 4, B and the third review's rule (a, b, c): RESTORE_BY_HAND is there when the press is handed over; a
    press refused before it went (Refused, StopRequested, CameraRefused) takes it away and closes and restores; any
    other failure keeps it, exits 5 and presses nothing more, whether or not the press had reached the link."""
    from camkit.link import CameraRefused, LinkError, StopRequested
    from exit_status import EXIT_RESTORE_BY_HAND

    def refused(state, key, cam):
        if state == "page" and key == "right":
            raise safety.Refused("right: the camera's own check refused it")

    def stopped(state, key, cam):
        if state == "page" and key == "right":
            raise StopRequested("STOP file")

    def not_accepted(state, key, cam):
        if state == "page" and key == "right":
            cam.handed += 1
            raise CameraRefused("press right 60: button not accepted")
    for fails in (refused, stopped, not_accepted):
        extra = {}
        pressed, line, _, code, restore, _, _ = drive_run(
            tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
            RESET_MOVES, more=["--confirm"], fails=fails, extra=extra)
        assert extra["marked"] == [False, True], fails.__name__                    # (a) there as the press went
        assert code == 0 and restore == ["closed", "ended"] and restore_pending(tmp_path) is None, fails.__name__
        # (b), and the records that differ said by key alone, never a value (an owner run: runner.values_withheld)
        assert line["completed"] is False and extra.get("restore_kw") == {"show": 0, "keys": True}

    def not_handed(state, key, cam):
        if state == "page" and key == "right":
            raise RuntimeError("the frame could not be read")      # before the press reached the link: all the same

    def dropped(state, key, cam):
        if state == "page" and key == "right":
            cam.handed += 1                     # handed to the link, then no answer
            raise LinkError("press right 60: no reply within 30 s")
    for fails, said in ((not_handed, "given to the camera"), (dropped, "handed to the link")):
        pressed, line, _, code, restore, out, _ = drive_run(
            tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
            RESET_MOVES, more=["--confirm"], fails=fails)
        assert code == EXIT_RESTORE_BY_HAND and restore == [] and restore_pending(tmp_path), fails.__name__   # (c)
        assert pressed == ["menu"] and line["restore"] == "by hand" and said in line["outcome"], (pressed, line)
        assert "upload_check.py" in out
        (tmp_path / RESTORE_BY_HAND).unlink()


def test_drive_presses_nothing_when_the_restore_by_hand_cannot_be_written(tmp_path, monkeypatch, scope_file):
    """(a): the intent is written before the press, or the press never goes."""
    import drive as D

    def cannot(*a, **k):
        (tmp_path / RESTORE_BY_HAND).write_text("{}", encoding="utf-8")         # one place written, the next not
        raise OSError("read-only folder")
    monkeypatch.setattr(D, "mark_restore_by_hand", cannot)
    pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"],
                                                        ["Reset Network Set."], RESET_DECISION, RESET_STATES,
                                                        RESET_MOVES, more=["--confirm"])
    assert pressed == ["menu"] and code == 0 and restore == ["closed", "ended"] and restore_pending(tmp_path) is None
    assert "nothing was pressed" in out


RESET_ASKS = {"page": ("submenu", "Network > Network Option Reset Network Set.", "Reset Network Set."),
              "question": ("dialog", "Reset Network Set. Reset network settings? Enter Cancel", "Cancel"),
              "busy": ("notice", "Resetting the network settings", ""),
              "dark": ("dialog", "", ""), "odd": ("keyboard", "A B C", "A")}
ASKS_AND_CANCELS = {("page", "right"): "question", ("question", "menu"): "page"}


def test_drive_cancels_a_resets_own_question_with_menu_and_says_nothing_was_confirmed(tmp_path, monkeypatch,
                                                                                      scope_file):
    """(e): Right on Reset Network Set. brought up its question: MENU alone (never Enter), the restore as ever, its
    check opening as upload_check's does, then the marker taken away, the outcome and the question's frame kept, exit
    6. Its SSID/PW Reset kin the same."""
    from exit_status import EXIT_NOT_CONFIRMED
    extra = {}
    pressed, line, logged, code, restore, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_ASKS,
        ASKS_AND_CANCELS, more=["--confirm"], extra=extra)
    assert pressed == ["menu", "right", "menu"] and code == EXIT_NOT_CONFIRMED and restore == ["closed", "ended"]
    assert line["outcome"] == "question shown, cancelled" and line["question_frame"].endswith("_question.png")
    assert extra["refreshes"] == ["after-armed"]
    assert [s["after"] for s in line["screens"]] == ["right"]             # the armed press ends the presses (M75)
    assert restore_pending(tmp_path) is None and "nothing was confirmed" in out
    assert extra["restore_kw"]["link_class"].keywords == {"pending_restore": True}
    assert '"armed_question"' in logged and '"restore_by_hand_cleared"' in logged
    states = {"page": ("submenu", "Network > Wi-Fi SSID/PW Reset", "SSID/PW Reset"),
              "question": ("dialog", "SSID/PW Reset Reset? OK Cancel", "OK")}
    pressed, line, _, code, *_ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["SSID/PW Reset"],
        {"rows": [SSID_RESET], "confirm": [SSID_RESET], "link_loss": True}, states, ASKS_AND_CANCELS,
        more=["--confirm"])
    assert pressed == ["menu", "right", "menu"] and code == EXIT_NOT_CONFIRMED and restore_pending(tmp_path) is None


def test_drive_leaves_a_question_menu_cannot_clear_to_a_person(tmp_path, monkeypatch, scope_file):
    """(e): three MENUs at most, never Enter; the question still there: the marker stays, exit 5, no restore."""
    from exit_status import EXIT_RESTORE_BY_HAND
    pressed, line, _, code, restore, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_ASKS,
        {("page", "right"): "question"}, more=["--confirm"])
    assert pressed == ["menu", "right", "menu", "menu", "menu"] and code == EXIT_RESTORE_BY_HAND and restore == []
    assert restore_pending(tmp_path) and "a person must cancel it on the camera" in out
    assert line["outcome"] == "question left open" and line["question_frame"].endswith("_question.png")
    # a MENU that lands on a screen the kit cannot read (black, of no kind it reads, no text) does not count as the
    # question gone: MENU again, three at most, then the same
    for unread, kw in ((("unknown", "", ""), {}), (("notice", "", ""), {}), (("submenu", "x", "x"), {"blacks": ("dim",)})):
        pressed, line, _, code, restore, out, _ = drive_run(
            tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION,
            {**RESET_ASKS, "dim": unread}, {("page", "right"): "question", ("question", "menu"): "dim"},
            more=["--confirm"], **kw)
        assert pressed == ["menu", "right", "menu", "menu", "menu"] and code == EXIT_RESTORE_BY_HAND, (unread, pressed)
        assert restore == [] and restore_pending(tmp_path) and line["outcome"] == "question left open"
        (tmp_path / RESTORE_BY_HAND).unlink()


def test_drive_keeps_the_marker_when_the_restore_after_a_cancelled_question_does_not_check_out(tmp_path, monkeypatch,
                                                                                               scope_file):
    from exit_status import EXIT_RESTORE_BY_HAND
    for kw in ({"restored": False}, {"close_exits": True}):
        *_, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."],
                                              RESET_DECISION, RESET_ASKS, ASKS_AND_CANCELS, more=["--confirm"], **kw)
        assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path), kw
        assert "the restore after it did not check out" in out
        (tmp_path / RESTORE_BY_HAND).unlink()


@pytest.mark.parametrize("states,kw,said", [
    (RESET_ASKS, {"refresh_fails": True}, "could not be read"),
    (RESET_ASKS, {"blacks": ("question",)}, "is black"),
    (RESET_STATES, {}, "reads as 'unknown'"),
    ({**RESET_ASKS, "question": RESET_ASKS["odd"]}, {}, "reads as 'keyboard'"),
    ({**RESET_ASKS, "question": RESET_ASKS["dark"]}, {}, "no text could be read")])
def test_drive_presses_nothing_after_an_armed_press_whose_screen_cannot_be_judged(tmp_path, monkeypatch, scope_file,
                                                                                  states, kw, said):
    """(d): the read after it fails, the frame is black or of no kind the kit reads, or no text: exit 5."""
    from exit_status import EXIT_RESTORE_BY_HAND
    moves = RESET_MOVES if states is RESET_STATES else ASKS_AND_CANCELS
    extra = {}
    pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"],
                                                        ["Reset Network Set."], RESET_DECISION, states, moves,
                                                        more=["--confirm"], extra=extra, **kw)
    assert pressed == ["menu", "right"] and code == EXIT_RESTORE_BY_HAND and restore == [], pressed
    assert restore_pending(tmp_path) and said in line["outcome"] and said in out
    assert extra["refreshes"] == ["after-armed"]                      # read once, and nothing after it


def test_drive_restores_over_a_link_that_answered_and_takes_the_marker_away_only_once_it_checks(tmp_path, monkeypatch,
                                                                                               scope_file):
    """(f): another screen than the question: the MENU-only close and the remote restore; the marker taken away only
    on a restore that checks out, else exit 5."""
    from exit_status import EXIT_RESTORE_BY_HAND
    moves = {("page", "right"): "busy", ("busy", "menu"): "page"}
    extra = {}
    pressed, line, _, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"],
                                                        ["Reset Network Set."], RESET_DECISION, RESET_ASKS, moves,
                                                        more=["--confirm"], extra=extra)
    assert pressed == ["menu", "right"] and code == 0 and restore == ["closed", "ended"]
    assert restore_pending(tmp_path) is None and line["outcome"] == "pressed; the link answered"
    assert extra["restore_kw"]["link_class"].keywords == {"pending_restore": True}
    for kw in ({"restored": False}, {"close_exits": True}):
        *_, code, restore, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."],
                                              RESET_DECISION, RESET_ASKS, moves, more=["--confirm"], **kw)
        assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and restore[0] == "closed", kw
        (tmp_path / RESTORE_BY_HAND).unlink()


def test_the_same_rule_holds_for_a_choice_and_a_final_press_that_may_drop_the_link(tmp_path, monkeypatch, scope_file):
    """The rule's tail is one for every armed press that may drop the link: a never-choose option ("link_loss"), and a
    final step or a confirmation where loses_link says so."""
    from exit_status import EXIT_RESTORE_BY_HAND
    wired = {"page": ("submenu", "Network > Wired LAN Wired LAN Connect", "Wired LAN Connect"),
             "list": ("list", "Wired LAN Connect On Off", "Off"), "gone": ("unknown", "", "")}
    decision = {"rows": ["Wired LAN Connect"], "options": {"Wired LAN Connect": ["Off"]}, "link_loss": True}
    extra = {}
    pressed, _, _, code, restore, _, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Off"], ["Wired LAN Connect"], decision, wired,
        {("page", "right"): "list", ("list", "enter"): "page"}, more=["--confirm"], extra=extra)
    assert permits[-1] == {"row": "Wired LAN Connect", "what": "choose"} and extra["marked"][-1] is True
    assert code == 0 and restore == ["closed", "ended"] and restore_pending(tmp_path) is None
    *_, code, restore, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Off"],
                                        ["Wired LAN Connect"], decision, wired,
                                        {("page", "right"): "list", ("list", "enter"): "gone"}, more=["--confirm"])
    assert code == EXIT_RESTORE_BY_HAND and restore == [] and restore_pending(tmp_path)
    (tmp_path / RESTORE_BY_HAND).unlink()
    monkeypatch.setattr(safety, "loses_link", lambda row, what: what == "final")
    states = {**FORMAT_STATES, "slots": ("list", "Format Slot 1 Slot 2", "Slot 1"),
              "sure": ("dialog", "Format Slot 1 Format the memory card in Slot 1? Enter Cancel", "Cancel")}
    pressed, line, _, code, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Slot"], ["Format"],
                                           FORMAT_DECISION, states, FORMAT_MOVES, more=["--confirm"])
    from exit_status import EXIT_NOT_CONFIRMED
    assert pressed == ["menu", "right", "enter", "menu"] and code == EXIT_NOT_CONFIRMED, (pressed, code)
    assert line["outcome"] == "question shown, cancelled" and restore_pending(tmp_path) is None


def test_a_not_accepted_reply_is_camera_refused_and_a_held_button_or_a_signal_is_not():
    """B: Link._must tells a reply that said "not taken" from one after which the press may have acted."""
    from camkit import link as L
    lk = L.Link.__new__(L.Link)
    for reply, kind in (({"ok": False, "error": "button not accepted"}, L.CameraRefused),
                        ({"ok": False, "error": "refused", "cause": "refused"}, L.CameraRefused),
                        ({"ok": False, "error": "held", "cause": "button_held"}, L.LinkError),
                        ({"ok": False, "cause": "signal"}, L.LinkError)):
        lk.call = lambda command, timeout=30.0, r=reply, **g: r
        with pytest.raises(L.LinkError) as e:
            lk._must("press enter 60")
        assert type(e.value) is kind, reply


def test_drive_opens_a_row_that_acts_on_opening_only_as_its_armed_last_press(tmp_path, monkeypatch, scope_file):
    states = {"page": ("submenu", "Shooting > File Create New Folder", "Create New Folder"),
              "made": ("notice", "Done", "OK")}
    decision = {"rows": [CREATE], "confirm": [CREATE]}
    for presses, more in ((["right"], []), (["right", "menu"], ["--confirm"])):
        pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, presses, ["Create New Folder"], decision,
                                      states, {("page", "right"): "made"}, more=more)
        assert pressed == ["menu"] and line["completed"] is False, (presses, more)
    pressed, *_, code, restore, _, permits = drive_run(tmp_path, monkeypatch, scope_file, ["right"],
                                                       ["Create New Folder"], decision, states,
                                                       {("page", "right"): "made"}, more=["--confirm"])
    assert pressed == ["menu", "right"] and permits[-1] == {"row": "Create New Folder", "what": "open"} and code == 0


def test_save_load_settings_never_loads_whatever_is_decided(tmp_path, monkeypatch, scope_file):
    """Finding 5: its opening acts (it is no row seen to open to look), so it is the armed last press or nothing; its
    Load is never named."""
    states = {"page": ("submenu", "Setup > Reset/Save Settings Save/Load Settings", "Save/Load Settings"),
              "list": ("submenu", "Save/Load Settings Save Load", "Load")}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Load"], ["Save/Load Settings"],
                                  {"rows": [SAVE_LOAD], "confirm": [SAVE_LOAD]}, states, {("page", "right"): "list"},
                                  more=["--confirm"])
    assert pressed == ["menu"] and line["completed"] is False
    assert owner({"rows": [SAVE_LOAD], "options": {SAVE_LOAD: ["Load"]}, "confirm": [SAVE_LOAD]})["refusals"]


def test_drive_logs_values_in_its_files_and_never_in_its_console(tmp_path, monkeypatch, scope_file):
    """Finding 2: Access Authen. Info with values logged."""
    pressed, line, logged, code, _, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "menu"], ["Access Authen. Info"],
        {"rows": ["Access Authen. Info"], "values": "logged"}, CREDS_STATES, DRIVE_CREDS)
    assert pressed == ["menu", "right", "menu"] and code == 0
    assert SECRET in json.dumps(line["screens"]) and "(values in drive.jsonl)" in out
    assert SECRET not in out and USER not in out and SECRET not in logged
    assert vlm.LOCAL_ONLY is True
    run_dir = tmp_path / "kit2_drive"
    assert (run_dir / vlm.LOCAL_MARKER).is_file() and (run_dir / vlm.NO_READER_MARKER).is_file()   # finding 10


# Access Authen. Info as OCR reads it in lines (drive_run's screen_lines splits on two spaces): a name and its value on
# one line, a name alone, a value alone; the values are placeholders
CREDS_LINES = {**CREDS_STATES, "info": ("notice", f"Access Authen. Info  User Name: {USER}  Password: {SECRET}  "
                                                  "Fingerprint  SHA256:made-up-print  OK", "OK")}


@pytest.mark.parametrize("logged", [True, False])
def test_an_owner_rows_screen_names_its_fields_and_counts_the_rest_never_a_value(tmp_path, monkeypatch, scope_file,
                                                                                 logged):
    """The first --owner look on the camera (Access Authen. Info, values logged) showed "fields []" and no count: the
    console names the fields the kit can name without a value (whole row labels; the name before a value where it is a
    field name camkit.safety.ADDRESS_FIELDS lists: Password, Fingerprint, User Name...) and always counts the lines not
    shown; never a value, logged or not."""
    decision = {"rows": ["Access Authen. Info"], **({"values": "logged"} if logged else {})}
    pressed, line, logged_events, code, _, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "menu"],
                                                              ["Access Authen. Info"], decision, CREDS_LINES, DRIVE_CREDS)
    assert code == 0
    said = "fields ['Access Authen. Info', 'User Name', 'Password', 'Fingerprint'], 4 lines withheld"
    assert said in out and ("(values in drive.jsonl)" in out) is logged, out
    for where in (out, logged_events):
        assert SECRET not in where and USER not in where and "made-up-print" not in where
    info = next(s for s in line["screens"] if s.get("fields"))
    assert info["fields"] == ["Access Authen. Info", "User Name", "Password", "Fingerprint"] and info["withheld"] == 4
    assert (SECRET in json.dumps(line["screens"])) is logged                      # drive.jsonl holds them only if logged


def test_a_blanked_owner_screen_is_said_as_withheld_with_its_kind(tmp_path):
    import drive
    cam = SimpleNamespace(blank=True, frame=SimpleNamespace(path=tmp_path / "00001_x.png", image=None))
    console, kept = drive.shown_screen(cam, None, "anything", True, kind="notice")
    assert kept == {"blanked": True} and "screen withheld" in console and "anything" not in console


def test_drive_sends_menu_alone_in_a_logged_credentials_screen(tmp_path, monkeypatch, scope_file):
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "down", "menu"], ["Access Authen. Info"],
                                  {"rows": ["Access Authen. Info"], "values": "logged"}, CREDS_STATES, DRIVE_CREDS)
    assert pressed == ["menu", "right"] and line["completed"] is False


def test_drive_reads_no_text_of_a_blanked_rows_screen(monkeypatch, tmp_path):
    """N56: screen_text and screen_lines read nothing of a blanked frame, nor turn and save it upright."""
    import drive
    monkeypatch.setattr(drive, "text_of", lambda cam: pytest.fail("a blanked frame was read"))
    monkeypatch.setattr(drive.ocr, "read", lambda paths, eng=None: pytest.fail("a blanked frame was read"))
    cam = SimpleNamespace(blank=True, frame=SimpleNamespace(path=tmp_path / "00001_x.png", image=None))
    assert drive.screen_text(cam, "up") == "" and drive.screen_lines(cam, "up") == []
    assert drive.shown_screen(cam, None, "x", True)[1] == {"blanked": True}


def test_drive_refuses_credentials_options_not_among_the_rows_own_values(tmp_path, monkeypatch, scope_file):
    decision = {"rows": ["Access Authen. Settings"], "options": {"Access Authen. Settings": ["Off"]}, "link_loss": True}
    *_, code, _, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Access Authen. Settings"], decision,
                                  CREDS_STATES, DRIVE_CREDS)
    assert code and "is not one of the values the page scan and the definition list" in str(code)


def test_drive_opens_an_owner_row_only_as_the_last_label_of_its_path(scope_file, monkeypatch):
    """N67: another owner row earlier in --path is refused as such."""
    import drive as D
    deep = "Network > Bluetooth > Pairing > Access Authen. Info"
    rows = owner({"rows": ["Pairing", deep]})["rows"]
    assert "only as the last label" in D.owner_path(["Pairing", "Access Authen. Info"], rows)[2]
    assert D.owner_path(["Pairing"], rows)[0] == "Pairing"
    assert "no row" in D.owner_path(["Drive Mode"], rows)[2]
    scope_file({"rows": ["Pairing", deep]})
    monkeypatch.setattr(D, "load_scan", lambda scan: ([], {}))
    for path, said in ((["Pairing", "Access Authen. Info"], "only as the last label"), (["Drive Mode"], "no row")):
        monkeypatch.setattr(sys, "argv", ["drive.py", "--owner", *[x for p in path for x in ("--path", p)]])
        with pytest.raises(SystemExit, match=said):
            D.main()


def test_the_walk_goes_to_a_row_in_the_tab_and_group_it_is_asked_for():
    """E: go_to, given a place, takes only a row whose page's breadcrumb reads that tab and group."""
    import crawl_run
    model = {"a": {"breadcrumb": "Network > Wi-Fi", "rows": [{"label": "Delete"}]},
             "b": {"breadcrumb": "Playback > Delete", "rows": [{"label": "Delete"}]}}
    cycle = [{"kind": "menu", "page": "a", "row": 0, "screen": "sa"}, {"kind": "menu", "page": "b", "row": 0,
                                                                         "screen": "sb"}]
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu"))
    assert crawl_run.go_to(cam, cycle, model, 1, "Delete", place=("Setup", "Media")) is None


def test_without_owner_drive_refuses_the_row_as_before(scope_file):
    scope_file({"rows": [FORMAT], "options": {FORMAT: ["Slot 1"]}, "confirm": [FORMAT]})
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), "--path", "Format", "--press", "right"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "0004" in r.stderr


# ---------------------------------------------------------------- the crawl and the proofs take no owner row (finding 3)

class RowCamera:
    """The crawl's camera: a row page, Right opens a list; it records every key (it checks nothing)."""
    def __init__(self):
        self.keys, self.presses, self.kind = [], 0, "submenu"

    def press(self, key, **kw):
        self.keys.append(key)
        self.presses += 1
        self.kind = "list" if key == "right" else "submenu"

    def read(self):
        return SimpleNamespace(kind=self.kind, focus="rows", count=2, rows=[], bar=None)


@pytest.mark.parametrize("label", ["Format", "Initialize", "Create New Folder", "WPS Push", "Pairing",
                                   "Access Authen. Info", "Display Serial Number", "Reset Network Set."])
def test_the_crawl_never_presses_right_on_an_owner_row(label):
    cam = RowCamera()
    r = crawl.visit_row(cam, cam.read(), {"page": "x"}, 0, {"label": label}, network={label: DAY})
    assert cam.keys == [] and r.outcome.startswith("skipped"), (label, r.outcome)


def test_the_crawl_and_prove_run_read_no_owner_decision(scope_file, tmp_path):
    import crawl_run
    import prove_run
    scope_file({"rows": [FORMAT, "Pairing", CREATE], "confirm": [FORMAT]})
    with pytest.raises(SystemExit, match="no dated owner decision"):
        crawl_run.network_settings_or_exit(Run("net", root=tmp_path))
    with pytest.raises(SystemExit, match="no dated owner decision"):
        prove_run.network_rows_or_exit(["Format"])


# ---------------------------------------------------------------- the restore by hand (finding 9; C; H)

def test_no_link_opens_while_a_restore_by_hand_is_pending(tmp_path, monkeypatch):
    from camkit import link as L
    run = Run("next", root=tmp_path)
    start = tmp_path / "kit2_drive" / "dat" / "00001_before.DAT"
    mark_restore_by_hand(tmp_path, "kit2_drive", start, "a made-up lost link")
    started = []

    def popen(*a, **k):
        started.append(a)
        raise RuntimeError("camlink would start here")
    monkeypatch.setattr(L.subprocess, "Popen", popen)
    with pytest.raises(L.LinkError, match="upload_check.py kit2_drive/dat/00001_before.DAT"):
        L.Link(run, ip="192.0.2.10", catch_signals=False).open()
    assert started == []
    with pytest.raises(RuntimeError, match="camlink would start"):
        L.Link(run, ip="192.0.2.10", catch_signals=False, pending_restore=True).open()
    (tmp_path / RESTORE_BY_HAND).unlink()
    with pytest.raises(RuntimeError, match="camlink would start"):
        L.Link(run, ip="192.0.2.10", catch_signals=False).open()


def test_a_restore_by_hand_in_the_cameras_usual_folder_holds_when_camset_runs_points_elsewhere(tmp_path, monkeypatch):
    """H: the marker is looked for in the clone's runs/ for the same camera key too."""
    import camkit
    from camkit import link as L
    usual, elsewhere = tmp_path / "usual", tmp_path / "elsewhere"
    monkeypatch.setattr(camkit, "RUNS", usual)
    (usual / TEST_CAMERA).mkdir(parents=True)
    mark_restore_by_hand((usual / TEST_CAMERA).resolve(), "kit2_drive",
                         usual / TEST_CAMERA / "kit2_drive" / "dat" / "x.DAT", "lost")
    run = Run("next", root=elsewhere / TEST_CAMERA)
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: pytest.fail("camlink started"))
    with pytest.raises(L.LinkError, match="may have dropped the link"):
        L.Link(run, ip="192.0.2.10", catch_signals=False).open()
    other = Run("next", root=elsewhere / "OTHER-CAM_fw1.00")      # another camera key: another camera's marker

    def popen(*a, **k):
        raise RuntimeError("camlink would start here")
    monkeypatch.setattr(L.subprocess, "Popen", popen)
    with pytest.raises(RuntimeError, match="camlink would start"):
        L.Link(other, ip="192.0.2.10", catch_signals=False).open()


def test_the_restore_by_hand_is_written_and_cleared_in_both_runs_folders(tmp_path, monkeypatch):
    """Finding 4: under CAMSET_RUNS=/x the marker goes to /x/<key> and to the clone's runs/<key>, so a later run with
    either folder sees it; clearing takes both away. A folder that is no camera's key gets it alone."""
    import camkit
    from camkit import link as L
    from camkit.runs import clear_restore_by_hand, restore_pending_any
    usual, elsewhere = tmp_path / "usual", tmp_path / "elsewhere"
    monkeypatch.setattr(camkit, "RUNS", usual)
    root = elsewhere / TEST_CAMERA
    start = root / "kit2_drive" / "dat" / "00001_before.DAT"
    assert mark_restore_by_hand(root, "kit2_drive", start, "lost") == root / RESTORE_BY_HAND
    assert restore_pending(root)["start"] == "kit2_drive/dat/00001_before.DAT"
    assert restore_pending(usual / TEST_CAMERA)["start"] == str(start)            # whole: it is not under that folder
    later = Run("next", root=usual / TEST_CAMERA)                                  # the default runs/ afterwards
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: pytest.fail("camlink started"))
    with pytest.raises(L.LinkError, match="may have dropped the link"):
        L.Link(later, ip="192.0.2.10", catch_signals=False).open()
    assert restore_pending_any(usual / TEST_CAMERA)[0] == usual / TEST_CAMERA
    assert clear_restore_by_hand(root)
    assert restore_pending(root) is None and restore_pending(usual / TEST_CAMERA) is None
    mark_restore_by_hand(usual / TEST_CAMERA, "kit2_drive", usual / TEST_CAMERA / "x.DAT", "lost")
    assert clear_restore_by_hand(elsewhere / TEST_CAMERA) and restore_pending(usual / TEST_CAMERA) is None
    other = tmp_path / "scratch"
    mark_restore_by_hand(other, "r", other / "x.DAT", "lost")
    assert restore_pending(other) and not (usual / "scratch").exists()


def upload_harness(tmp_path, monkeypatch, verdict, root=None, differ=("global:0x0123",)):
    """kit/tools/upload_check.py with a fake link, its verify_restore answering verdict["n"] and recording what it was
    given, the restored file differing from the start file in `differ`. Returns (the module, the start file, another
    download, the record). root: the camera's run root (tmp_path by default)."""
    from tools import upload_check as U
    root = tmp_path if root is None else root
    run_dir = root / "kit2_drive" / "dat"
    run_dir.mkdir(parents=True)
    start, other = run_dir / "00001_before.DAT", run_dir / "00009_other.DAT"
    start.write_bytes(b"start bytes")
    other.write_bytes(b"other bytes")
    mark_restore_by_hand(root, "kit2_drive", start, "a made-up lost link")
    links = []

    class Link:
        def __init__(self, run, pending_restore=False):
            links.append(pending_restore)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def upload(self, f):
            return {"ok": True}

    def verify(run, f, link_class=None, expected=frozenset()):
        links.append(("verify", link_class, expected))
        return verdict["n"]
    monkeypatch.setattr(U, "Link", Link)
    monkeypatch.setattr(U, "Run", lambda name: Run(name, root=root))
    monkeypatch.setattr(U.provenance, "check", lambda f, root: {"sha256": "x"})
    monkeypatch.setattr(U, "verify_restore", verify)
    monkeypatch.setattr(U.paths, "run_arg", lambda x: x)
    monkeypatch.setattr(U, "setting_names", lambda: {})
    monkeypatch.setattr(U.camset, "diff", lambda *a: [SimpleNamespace(key=k) for k in differ])
    monkeypatch.setattr(U, "read_noted", lambda *f: [None, None])
    monkeypatch.setattr(U, "known_left", lambda f: frozenset({"global:0x1126", "set1:0x023c"}))
    monkeypatch.setattr(U.glob, "glob", lambda pattern: [str(start)])
    return U, start, other, links


def test_upload_check_puts_back_that_file_alone_and_clears_the_mark_once_it_checks(tmp_path, monkeypatch, capsys):
    verdict = {"n": 3}
    U, start, other, links = upload_harness(tmp_path, monkeypatch, verdict)
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(other)])
    with pytest.raises(SystemExit, match="put its start file back first"):
        U.main()
    assert links == []
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start)])
    U.main()
    assert links[0] is True and restore_pending(tmp_path)                    # 3 records differ: the mark stays
    assert links[1][1].keywords == {"pending_restore": True}                 # the reconnection may open too
    assert links[1][2] == {"global:0x1126", "set1:0x023c"}                   # C: what no file sets back, left out
    assert "global:0x1126" in capsys.readouterr().out
    verdict["n"] = 0
    U.main()
    assert restore_pending(tmp_path) is None


def test_upload_check_clears_the_mark_only_when_accept_names_exactly_what_still_differs(tmp_path, monkeypatch, capsys):
    """C and finding 6: without --accept the mark stays and the records that differ are printed, with the line the
    owner names them back with; --accept takes ids, and clears the mark only when they are exactly those records."""
    verdict = {"n": 3}
    U, start, _, _ = upload_harness(tmp_path, monkeypatch, verdict,
                                    differ=("global:0x0123", "set1:0x0456", "set2:0x0456", "global:0x1126"))
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start)])
    U.main()
    out = capsys.readouterr().out
    assert restore_pending(tmp_path) and "--accept 0x0123,0x0456" in out and "never an agent's" in out
    assert "global:0x1126" not in out.split("records that still differ:")[1].split(".")[0]      # left out: known
    for given in ("0x0123", "0x0123,0x0456,0x0789", "0x0123,set1:0x0456", "nonsense", "", "0x0456"):
        monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start), "--accept", given])
        U.main()
        assert restore_pending(tmp_path), given
        assert "did not check out" in capsys.readouterr().out
    with pytest.raises(SystemExit):                                       # a flag alone is no longer taken
        monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start), "--accept"])
        U.main()
    for given in ("0x0123,set1:0x0456,set2:0x0456", " 0x123 , 0x0456 "):
        mark_restore_by_hand(tmp_path, "kit2_drive", start, "again")
        monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start), "--accept", given])
        U.main()
        out = capsys.readouterr().out
        assert restore_pending(tmp_path) is None and "and accepts them" in out, given
    verdict["n"] = None                                                   # no reconnection: never accepted
    mark_restore_by_hand(tmp_path, "kit2_drive", start, "again")
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start), "--accept", "0x0123,0x0456"])
    U.main()
    assert restore_pending(tmp_path)


def test_upload_check_clears_the_mark_in_both_runs_folders(tmp_path, monkeypatch):
    """Finding 4: written, looked for and removed in the run's root and the clone's runs/<key>."""
    import camkit
    usual, elsewhere = tmp_path / "usual", tmp_path / "elsewhere"
    monkeypatch.setattr(camkit, "RUNS", usual)
    U, start, _, _ = upload_harness(tmp_path, monkeypatch, {"n": 0}, root=elsewhere / TEST_CAMERA)
    assert restore_pending(elsewhere / TEST_CAMERA) and restore_pending(usual / TEST_CAMERA)
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start)])
    U.main()
    assert restore_pending(elsewhere / TEST_CAMERA) is None and restore_pending(usual / TEST_CAMERA) is None


def test_the_records_no_file_sets_back_are_known_by_model(tmp_path, monkeypatch):
    from tools import upload_check as U
    monkeypatch.setattr(U.camset, "read", lambda f: SimpleNamespace(model="ILCE-1M2"))
    got = U.known_left(tmp_path / "x.DAT")
    assert {"global:0x18cb", "global:0x1126", "set1:0x023c", "set3:0x11ad"} <= got
    monkeypatch.setattr(U.camset, "read", lambda f: SimpleNamespace(model="OTHER-1"))
    assert U.known_left(tmp_path / "x.DAT") == frozenset()


def test_a_chain_uploads_no_end_file_after_a_step_that_restores_by_hand(tmp_path, monkeypatch):
    from tools import chain
    from exit_status import EXIT_RESTORE_BY_HAND
    end = tmp_path / "owner.DAT"
    end.write_bytes(b"x")
    f = tmp_path / "c.toml"
    f.write_text('name = "c"\n[[step]]\ntitle = "reset"\nrun = ["kit/drive.py"]\n[[step]]\ntitle = "next"\n'
                 'run = ["kit/drive.py"]\n', encoding="utf-8")
    ran = []

    def step(s, env, out):
        ran.append(s.get("title") or ("upload", s.get("upload")))
        return EXIT_RESTORE_BY_HAND if s.get("title") == "reset" else 0
    monkeypatch.setattr(chain, "run_step", step)
    monkeypatch.setattr(chain.paths, "run_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["chain.py", str(f), "--end", str(end), "--stop", str(tmp_path / "STOP_CHAIN")])
    chain.main()
    assert ran == ["reset"]


def test_a_chain_stops_after_a_step_that_confirmed_nothing_and_uploads_its_end_file(tmp_path, monkeypatch):
    """(e): status 6, the row's question cancelled and the start file back: the chain stops, the end file goes up."""
    from tools import chain
    from exit_status import EXIT_NOT_CONFIRMED
    end = tmp_path / "owner.DAT"
    end.write_bytes(b"x")
    f = tmp_path / "c.toml"
    f.write_text('name = "c"\n[[step]]\ntitle = "reset"\nrun = ["kit/drive.py"]\n[[step]]\ntitle = "next"\n'
                 'run = ["kit/drive.py"]\n', encoding="utf-8")
    ran = []

    def step(s, env, out):
        ran.append(s.get("title") or ("upload", Path(s.get("upload")).name))
        return EXIT_NOT_CONFIRMED if s.get("title") == "reset" else 0
    monkeypatch.setattr(chain, "run_step", step)
    monkeypatch.setattr(chain.paths, "run_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["chain.py", str(f), "--end", str(end), "--stop", str(tmp_path / "STOP_CHAIN")])
    chain.main()
    assert ran == ["reset", ("upload", "owner.DAT")]


# ---------------------------------------------------------------- the batch tools read no owner run (finding 10)

def test_no_batch_tool_asks_a_reader_about_an_owner_runs_frames(tmp_path, monkeypatch):
    import camkit
    import help_reads
    import pass1_labels
    import tiebreak
    import page_model
    from camkit import claude_reader
    from tools import reader_census, reread_proofs
    folder = tmp_path / TEST_CAMERA / "kit2_drive"
    (folder / "shots").mkdir(parents=True)
    vlm.mark_local_only(folder)
    vlm.mark_no_reader(folder)
    for name in ("rows.jsonl", "options.jsonl", "proofs.jsonl"):
        (folder / name).write_text("", encoding="utf-8")
    built = []

    class Fake:                         # a reader built is a reader that could be asked: none may be
        def __init__(self, name=None, **kw):
            built.append(name)
    monkeypatch.setattr(vlm, "Reader", Fake)
    monkeypatch.setattr(claude_reader, "ClaudeReader", Fake)
    cfg = tmp_path / "config.json"
    local = {"name": "local", "url": "http://127.0.0.1:8000/v1", "model": "m"}
    cfg.write_text(json.dumps({"readers": [local, {**local, "name": "lan", "url": "http://192.168.1.50/v1"}],
                               "roles": {"second": "local", "third": "lan"}}), encoding="utf-8")
    monkeypatch.setattr(camkit, "CONFIG", cfg)
    calls = [lambda: (monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(folder)]), pass1_labels.main()),
             lambda: (monkeypatch.setattr(sys, "argv", ["tiebreak.py", str(folder)]), tiebreak.main()),
             lambda: page_model.vlm_read_pages(folder),
             lambda: (monkeypatch.setattr(help_reads, "RUN", folder), help_reads.main()),
             lambda: reread_proofs.main([str(folder)]),
             lambda: vlm.local_only_runs(folder / "shots" / "00001_down.png")]
    for call in calls:
        with pytest.raises(SystemExit, match="no reader reads them"):
            call()
    assert built == []
    root, found = reader_census.runs_in(tmp_path / TEST_CAMERA)
    assert found == []                                                        # under a run root: left out
    assert vlm.held_runs(folder) == [folder.resolve()]


# ---------------------------------------------------------------- the fourth review (2026-11-14)

MISREAD_STATES = {"shoot": ("shooting", "", ""), "slots": ("list", "Format Slot 1 Slot 2", "Slot 1"),
                  "sure": ("dialog", SURE, "Enter"), "busy": ("notice", "Formatting...", "")}
MISREAD_MOVES = {("shoot", "menu"): "page", ("page", "right"): "slots", ("slots", "enter"): "sure",
                 ("sure", "enter"): "busy", ("busy", "menu"): "page", ("slots", "menu"): "page", ("sure", "menu"): "page"}


@pytest.mark.parametrize("misread", ["Formal", "Fomat", "Forma t"])
def test_drive_takes_no_right_or_enter_that_is_not_the_owner_rows_opening_or_inside_it(tmp_path, monkeypatch,
                                                                                       scope_file, shipped, misread):
    """Finding 1: the lit Format row misread is no ordinary row to open; --confirm covers no unjudged press. Its
    refusal's quoted texts are withheld (M73)."""
    states = {**MISREAD_STATES, "page": ("submenu", "Shooting > Media Format", misread)}
    pressed, line, _, code, restore, out, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Slot", "enter:memory card"], ["Format"],
        {"rows": [FORMAT], "confirm": [FORMAT]}, states, MISREAD_MOVES, start="shoot", more=["--confirm"])
    assert pressed == ["menu"] and code == 0 and restore == ["closed", "ended"] and line["completed"] is False
    said = next(x for x in out.splitlines() if x.startswith("right refused:"))
    assert "'(withheld)'" in said and "Format" not in said and "Formal" not in said, said


def test_drives_confirm_covers_only_a_press_the_owner_gates_judged(tmp_path, monkeypatch, scope_file):
    """Finding 1: a named option of a row that is no action, on a screen that reads as a confirmation: the run's
    --confirm, given for an armed press, never lets it through."""
    states = {"page": ("submenu", "Network > Bluetooth Bluetooth Function", "Bluetooth Function"),
              "list": ("list", "Bluetooth Function On Off Execute", "On")}
    decision = {"rows": ["Bluetooth Function"], "options": {"Bluetooth Function": ["On"]}}
    pressed, line, _, code, restore, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:On"], ["Bluetooth Function"], decision, states,
        {("page", "right"): "list"}, more=["--confirm"])
    assert pressed == ["menu", "right"] and line["completed"] is False and "confirmation" in out


def test_drive_sends_nothing_but_up_and_down_between_the_walk_and_the_opening(tmp_path, monkeypatch, scope_file):
    """Finding 3: MENU, Left or a dial before the opening could move the page off the place that was read."""
    for presses in (["menu", "right"], ["left", "right"], ["dial.front.1:Format", "right"], ["help", "right"]):
        pressed, line, _, code, *_ = drive_run(tmp_path, monkeypatch, scope_file, presses, ["Format"], FORMAT_DECISION,
                                               FORMAT_STATES, FORMAT_MOVES, more=["--confirm"])
        assert pressed == ["menu"] and line["completed"] is False, (presses, pressed)
    pressed, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["down", "up", "right"], ["Format"], FORMAT_DECISION,
                            FORMAT_STATES, {**FORMAT_MOVES, ("page", "down"): "page"}, more=["--confirm"])
    assert pressed == ["menu", "down", "up", "right"]


@pytest.mark.parametrize("misread", ["Formal", "Fomat", "Forma t"])
def test_the_camera_opens_no_row_but_the_owner_row_once_drive_has_walked_to_it(tmp_path, monkeypatch, shipped, misread):
    """Finding 1 on the camera's side: owner_only, set by drive.py after its walk, refuses any opening press whose lit
    row is not the owner row, and any Enter outside it, on any screen."""
    states = {**FORMAT_STATES, "page": ("submenu", "Shooting > Media Format", misread)}
    cam = camera(tmp_path, monkeypatch, info_of(FORMAT, {"rows": [FORMAT], "confirm": [FORMAT]}), states)
    cam.press("right")                                  # before the flag, as before: a row of no list opens
    assert cam.link.sent == ["right"]
    cam = camera(tmp_path, monkeypatch, info_of(FORMAT, {"rows": [FORMAT], "confirm": [FORMAT]}), states)
    cam.owner_only = True
    for key in ("right", "enter", "ms_right", "ms_enter"):
        with pytest.raises(safety.Refused, match="no row but the owner row opens"):
            cam.press(key)
    states = {**FORMAT_STATES, "page": ("dialog", SURE, "Enter")}
    cam = camera(tmp_path, monkeypatch, info_of(FORMAT, {"rows": [FORMAT], "confirm": [FORMAT]}), states)
    cam.owner_only = True
    with pytest.raises(safety.Refused, match="no row but the owner row opens"):
        cam.press("enter")
    cam.press("down")
    cam.press("menu")
    assert cam.link.sent == ["down", "menu"]


def test_the_cameras_refusals_withhold_their_quoted_texts_on_an_owner_run(tmp_path, monkeypatch):
    """M72: a row's bar can carry a value: on an owner run the refusal says no quoted text."""
    cam = camera(tmp_path, monkeypatch, format_info())
    with pytest.raises(safety.Refused) as e:
        cam.press("enter")
    assert "'(withheld)'" in str(e.value) and "Format" not in str(e.value)


@pytest.mark.parametrize("text,asks", [
    ("The SSID and password have been reset. OK", False), ("Network settings have been reset. OK", False),
    ("Reset network settings? Enter Cancel", True), ("SSID/PW Reset Reset? OK Cancel", True),
    ("Reset network settings Enter Cancel", True), ("Reset Network Set. Reset Done OK", False),
    ("Reset network settings in progress. Cancel", False), ("SSID/PW Reset in progress. Cancel", False),
    ("Reset network settings. OK Cancel", True)])
def test_a_question_asks_and_a_notice_that_says_it_was_done_is_none(text, asks):
    """Finding 2: own_question needs a "?" or a dialog's two buttons; a fifth review: the row's own action word
    ("Reset") with Cancel is no dialog's two buttons, so a progress notice asks nothing."""
    row = "SSID/PW Reset" if "SSID" in text else "Reset Network Set."
    assert bool(safety.own_question("notice", text, row)) is asks, text


def test_drive_takes_a_resets_done_notice_for_an_answer_and_claims_nothing(tmp_path, monkeypatch, scope_file):
    """Finding 2 (the reviewer's probe a): the reset acted and the camera, still answering, says so: path (f), never
    "nothing was confirmed", the marker taken away only because the restore checked out."""
    states = {"shoot": ("shooting", "", ""),
              "page": ("submenu", "Network > Network Option Reset Network Set.", "Reset Network Set."),
              "done": ("notice", "Network settings have been reset. OK", "OK")}
    moves = {("shoot", "menu"): "page", ("page", "right"): "done", ("done", "menu"): "page"}
    pressed, line, _, code, restore, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, states, moves,
        start="shoot", more=["--confirm"])
    assert pressed == ["menu", "right"] and code == 0 and restore == ["closed", "ended"]
    assert line["outcome"] == "pressed; the link answered" and "question_frame" not in line
    assert "nothing was confirmed" not in out and "evidence" not in out and restore_pending(tmp_path) is None
    # what drive.jsonl keeps of that screen: its field names, never its text (the decision logs no values)
    assert "text" not in line["screens"][-1] and "fields" in line["screens"][-1]


def test_drive_checks_the_whole_place_of_a_row_deeper_than_its_top_level_row(tmp_path, monkeypatch, scope_file):
    """Finding 3 (the reviewer's probe b): a sub-row's opening is made only on its parent's own page, whose title was
    read; the walk reads each parent before its Right."""
    sub = "Playback > Playback Target > Playback Filter Condition > Protect"
    decision = {"rows": [sub], "confirm": [sub]}
    states = {"shoot": ("shooting", "", ""),
              "page": ("submenu", "Playback > Playback Target Playback Filter Condition Rating",
                       "Playback Filter Condition"),
              "filter": ("submenu", "Playback Filter Condition Protect Rating", "Protect"),
              "other": ("submenu", "Playback > Editing Protect Rotate", "Protect"),
              "opened": ("list", "Protect Multiple Img. Cancel All", "Multiple Img.")}
    moves = {("shoot", "menu"): "page", ("page", "right"): "filter", ("filter", "menu"): "other",
             ("other", "right"): "opened", ("filter", "right"): "opened", ("opened", "menu"): "filter"}
    path = ["Playback Filter Condition", "Protect"]
    # the probe: MENU before the opening is refused, so its Right never lands on Playback > Editing > Protect
    pressed, line, _, code, _, _, permits = drive_run(tmp_path, monkeypatch, scope_file, ["menu", "right"], path,
                                                      decision, states, moves, start="shoot", more=["--confirm"],
                                                      walk=True)
    assert pressed == ["menu", "right"] and {"row": "Protect", "what": "open"} not in permits
    # the walk read its parent and the title of the page it opened: the opening goes there
    pressed, line, _, code, _, _, permits = drive_run(tmp_path, monkeypatch, scope_file, ["right"], path, decision,
                                                      states, moves, start="shoot", more=["--confirm"], walk=True)
    assert pressed == ["menu", "right", "right"] and permits[-1] == {"row": "Protect", "what": "open"}
    # the page shown at the opening is another than the parent's: refused
    states_off = {**states, "filter": ("submenu", "Playback > Editing Protect Rotate", "Protect")}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], path, decision, states_off, moves,
                                  start="shoot", more=["--confirm"], walk=True)
    assert pressed == ["menu", "right"], pressed                           # the walk's Right; the opening refused
    # the parent lit is another row: the walk refuses before its Right
    states_lit = {**states, "page": ("submenu", "Playback > Playback Target Rating", "Rating")}
    pressed, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], path, decision, states_lit, moves,
                            start="shoot", more=["--confirm"], walk=True)
    assert pressed == ["menu"]


PB = ["Playback", "Playback Target"]


def test_the_title_of_a_parents_page_is_read_at_its_head():
    import drive as D
    for text in ("Playback Filter Condition Protect Rating", "Playback > Playback Target Playback Filter Condition",
                 "Playback > Playback Target > Playback Filter Condition Protect", "Playback Playback Filter Condition"):
        assert D.title_refused("submenu", text, "Playback Filter Condition", PB) == "", text
    assert D.title_refused("submenu", "Shooting > File File/Folder Settings", "File/Folder Settings",
                           ["Shooting", "File"]) == ""
    assert D.title_refused("submenu", "File/Folder Settings Format", "File/Folder Settings", ["Shooting", "File"]) == ""
    for kind, text in (("menu", "Playback Filter Condition Protect"), ("submenu", ""),
                       ("submenu", "Playback > Editing Protect Rotate"),
                       ("submenu", "Playback > Editing Protect Rotate Rating Delete Slideshow Playback Filter Condition"),
                       ("submenu", "Playback > Editing Playback Filter Condition"),
                       ("submenu", "XPlayback Filter Condition"), ("submenu", "Playback Filter Conditions Protect")):
        assert D.title_refused(kind, text, "Playback Filter Condition", PB), (kind, text)
    assert D.reads_row("Protect", "Protect") and D.reads_row("Protect On", "Protect")
    assert not D.reads_row("Protection", "Protect") and not D.reads_row("", "Protect")


def test_the_walk_refuses_whatever_it_cannot_read(monkeypatch):
    """Finding 3: owner_walk's checks, each on its own."""
    import drive as D
    at = {"s": "top"}
    screens = {"top": ("submenu", "Playback > Playback Target Playback Filter Condition", "Playback Filter Condition"),
               "sub": ("submenu", "Playback Filter Condition Rating Protect", "Rating"),
               "sub2": ("submenu", "Playback Filter Condition Rating Protect", "Protect")}
    moves = {("top", "right"): "sub", ("sub", "down"): "sub2", ("sub2", "down"): "sub"}
    downs = []
    cam = SimpleNamespace(frame=SimpleNamespace(image=None, path=None),
                          read=lambda: SimpleNamespace(kind=screens[at["s"]][0], where=at["s"]))

    def pressed(key, **kw):
        downs.append(key == "down")
        at["s"] = moves.get((at["s"], key), at["s"])
    cam.press = pressed
    monkeypatch.setattr(D, "highlighted", lambda image, path: screens[at["s"]][2])
    monkeypatch.setattr(D, "screen_text", lambda c, grip: screens[at["s"]][1])
    monkeypatch.setattr(D, "same_position", lambda a, b: a.where == b.where)
    assert D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB) == "" and at["s"] == "sub2"
    at["s"] = "top"
    downs.clear()
    assert "no row 'Lock'" in D.owner_walk(cam, ["Playback Filter Condition", "Lock"], None, PB)
    # N30: the walk stops once the first lit row comes round again, not after its 40 Downs (two rows: two Downs)
    assert sum(downs) == 2, sum(downs)
    at["s"] = "top"
    screens["sub"] = ("list", "Playback Filter Condition Rating Protect", "Rating")
    assert "not the submenu" in D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB)
    at["s"] = "top"
    screens["sub"] = ("submenu", "", "Rating")
    assert "cannot be read" in D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB)
    at["s"] = "top"
    screens["top"] = ("submenu", "Playback > Playback Target Rating", "")
    assert "not 'Playback Filter Condition'" in D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB)


def test_a_blanked_row_whose_opening_may_change_the_network_is_confirmed_only_with_values_logged():
    """Finding 4: without "values": "logged" the screen after its opening could never be judged."""
    for row in ("WPS Push", "Pairing"):
        said = owner({"rows": [row], "confirm": [row], "link_loss": True})["refusals"]
        assert said and "blanked" in said[0], said
        assert info_of(row, {"rows": [row], "confirm": [row], "link_loss": True, "values": "logged"})["confirm"]
    # a row whose opening keeps the link takes it as before
    assert info_of(CREATE, {"rows": [CREATE], "confirm": [CREATE]})["confirm"]


def test_every_restore_by_hand_tells_the_owner_to_cancel_what_the_camera_still_shows(tmp_path, monkeypatch,
                                                                                    scope_file):
    """Finding 4: the exit-5 message."""
    *_, code, _, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."],
                                    RESET_DECISION, RESET_STATES, RESET_MOVES, more=["--confirm"])
    assert code == 5 and "cancelled there by hand, with MENU or Cancel, never Enter or OK" in out


def test_the_proof_viewer_never_shows_an_owner_runs_frames_nor_packs_a_local_runs(tmp_path, monkeypatch):
    """Finding 5: proof_viewer's frame() and collect() leave a NO_READER run out; --pack copies no frame of a run
    marked LOCAL_ONLY or NO_READER."""
    from tools import proof_viewer as P
    root = tmp_path / TEST_CAMERA
    for name in ("kit2_owner", "kit2_net", "kit2_plain"):
        (root / name / "shots").mkdir(parents=True)
        (root / name / "shots" / "00001_x.png").write_bytes(b"png")
    vlm.mark_no_reader(root / "kit2_owner")
    vlm.mark_local_only(root / "kit2_owner")
    vlm.mark_local_only(root / "kit2_net")
    monkeypatch.setattr(P, "RUN_ROOT", root)
    page = root / "_viewer"
    page.mkdir()
    assert P.frame(root / "kit2_owner", "00001_x.png", page) is None
    links = {P.frame(root / n, "00001_x.png", page) for n in ("kit2_net", "kit2_plain")}
    assert None not in links
    plan = P.pack_plan(links, page, root)
    assert [Path(v[0]).parent.parent.name for v in plan.values()] == ["kit2_plain"]
    line = json.dumps({"path": ["Format"], "presses": [], "changes": [{"key": "global:0x0001", "before": 0, "after": 1}],
                       "screens": [{"after": "right", "frame": "00001_x.png"}]})
    for name in ("kit2_owner", "kit2_plain"):
        (root / name / "drive.jsonl").write_text(line + "\n", encoding="utf-8")
    monkeypatch.setattr(P, "from_steps", lambda run, log, keys, here, ev: ev["seen"].append(run.name))
    monkeypatch.setattr(P, "Keys", lambda settings: None)
    assert P.collect([], page)["seen"] == ["kit2_plain"]


def test_owner_said_warns_that_a_registering_rows_first_enter_registers_and_nothing_restores_it():
    """Finding 6."""
    said = safety.owner_said(info_of(MEMORY, {"rows": [MEMORY], "options": {MEMORY: ["M1"]}, "confirm": [MEMORY]}))
    assert "registers at once" in said and "no settings file puts that registration back" in said
    assert "registers" not in safety.owner_said(format_info())


def test_a_scope_git_could_not_judge_is_refused(tmp_path, monkeypatch):
    """Finding 7: only git's exit 1 says a file is untracked."""
    import runner
    f = tmp_path / "pass2_scope_draft.json"
    f.write_text("{}", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    for code, refused in ((0, True), (1, False), (128, True), (2, True)):
        monkeypatch.setattr(subprocess, "run", lambda *a, c=code, **k: SimpleNamespace(returncode=c))
        assert bool(runner.scope_tracked(f)) is refused, code


def test_register_iptc_info_reads_the_card_and_is_never_named_nor_pressed():
    """Finding 8."""
    for spelling in ("Register IPTC Info", "Register IPTC Info.", "RegisterIPTC Info"):
        assert safety.owner_never(spelling), spelling
        assert safety.owner_option_refused(spelling, "IPTC Information", safety.LIFT_FIXED)
        assert safety.owner_enter("IPTC Information", safety.LIFT_FIXED, "list", spelling, "IPTC Information",
                                  [spelling])[0]
    assert not safety.owner_never("Write IPTC Info") and not safety.owner_never("IPTC Information")


def test_typed_word_needs_a_terminal_and_the_rows_own_name(capsys):
    """Finding 9 in its layer: no terminal, no go; a wrong word, no go; the row's name, go."""
    import drive as D
    place = ["Shooting", "Media", "Format"]
    assert "no terminal" in D.typed_word("Format", place, "format", "TEST-CAM_fw9.99", read=lambda p: "Format",
                                         tty=False)
    assert "typed 'yes'" in D.typed_word("Format", place, "format", "TEST-CAM_fw9.99", read=lambda p: "yes", tty=True)
    assert D.typed_word("Format", place, "format", "TEST-CAM_fw9.99", read=lambda p: " format ", tty=True) == ""
    out = capsys.readouterr().out
    assert "'Shooting > Media > Format'" in out and "TEST-CAM_fw9.99" in out

    def interrupted(p):
        raise EOFError
    assert D.typed_word("Format", place, "format", "c", read=interrupted, tty=True)


def test_drive_asks_the_person_before_an_armed_press_and_nothing_answers_for_them(tmp_path, monkeypatch, scope_file):
    """Finding 9 on drive's side: no terminal refuses before anything connects; a wrong word refuses; "unattended"
    waives the question and says so; a run with no --confirm asks nothing; a fifth review: a confirming run in a row of
    no action that does not act on opening is asked too."""
    for typed, said in ((None, "no terminal"), ("Formal", "typed 'Formal'")):
        pressed, line, _, code, restore, _, _ = drive_run(
            tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
            RESET_MOVES, more=["--confirm"], typed=typed)
        assert pressed == [] and restore == [] and said in str(code), (typed, code)
        assert restore_pending(tmp_path) is None
    extra = {}
    *_, code, _, out, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."],
                                    {**RESET_DECISION, "unattended": True}, RESET_STATES, RESET_MOVES,
                                    more=["--confirm"], typed=None, extra=extra)
    assert code == 5 and "waived the terminal question" in out and "asked" not in extra
    extra = {}
    drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
              RESET_MOVES, typed=None, extra=extra)
    assert "asked" not in extra                                            # no --confirm: no armed press, no question
    extra = {}
    pressed, _, _, code, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "menu"], ["Access Authen. Info"],
                                        {"rows": ["Access Authen. Info"], "values": "logged"}, CREDS_STATES,
                                        DRIVE_CREDS, more=["--confirm"], typed=None, extra=extra)
    assert pressed == [] and "no terminal" in str(code)        # a fifth review: every confirming owner run asks
    extra = {}
    pressed, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "enter:Slot"], ["Format"], FORMAT_DECISION,
                            FORMAT_STATES, FORMAT_MOVES, more=["--confirm"], extra=extra)
    assert pressed == ["menu", "right", "enter"] and extra["asked"]


def test_unattended_is_an_owner_decisions_alone_and_only_beside_an_armed_press():
    """Finding 9: the parser; a fifth review: "unattended" stands beside "confirm" or a never-choose row's "options"
    with "link_loss", and nowhere else; every other confirming run asks, a look-only row's too."""
    assert info_of(RESET_NET, {**RESET_DECISION, "unattended": True})["unattended"] is True
    assert not safety.asks_person(info_of(RESET_NET, {**RESET_DECISION, "unattended": True}))
    assert safety.asks_person(info_of(RESET_NET, RESET_DECISION)) and safety.asks_person(format_info())
    assert safety.asks_person(info_of("Access Authen. Info", {"rows": ["Access Authen. Info"]}))
    wired = {"rows": ["Wired LAN Connect"], "options": {"Wired LAN Connect": ["Off"]}, "link_loss": True}
    assert info_of("Wired LAN Connect", {**wired, "unattended": True})["unattended"] is True
    assert not safety.asks_person(info_of("Wired LAN Connect", {**wired, "unattended": True}))
    for bad in ({"rows": [FORMAT], "unattended": True}, {**FORMAT_DECISION, "unattended": "yes"},
                {**wired, "link_loss": False, "unattended": True},          # a never-choose option without link_loss
                {"rows": ["Bluetooth Function"], "options": {"Bluetooth Function": ["Off"]}, "link_loss": True,
                 "unattended": True},                                       # an option that is no armed press
                {"rows": ["Access Authen. Info"], "values": "logged", "unattended": True}):
        got = owner(bad)
        assert got["rows"] == {} and "unattended" in got["refusals"][0], (bad, got)
    rows, refusals = safety.network_decided({"decisions": [{**OWNER, "lifts": "network", "rows": ["Bluetooth Function"],
                                                            "unattended": True}]})
    assert rows == {} and "only an owner decision" in refusals[0]


def test_drive_keeps_a_blanked_rows_screens_menu_alone_by_its_own_flag(tmp_path, monkeypatch, scope_file):
    """M17: a closed identity row's values withheld: drive's own lock, beside the camera's (which here checks nothing)."""
    states = {"page": ("submenu", "Setup > Setup Option Copyright Info", "Copyright Info"),
              "list": ("list", "Copyright Info Write On Off", "On")}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right", "down"], ["Copyright Info"],
                                  {"rows": ["Copyright Info"]}, states, {("page", "right"): "list"})
    assert pressed == ["menu", "right"] and line["completed"] is False


def test_drive_judges_every_label_of_an_owner_runs_path_but_its_last(tmp_path, monkeypatch, scope_file):
    """M56: a never-open label above the owner row is refused as in any run."""
    deep = "Network > Wi-Fi > WPS Push > Access Authen. Info"
    *_, code, _, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["WPS Push", "Access Authen. Info"],
                                  {"rows": [deep]}, CREDS_STATES, DRIVE_CREDS)
    assert "'WPS Push'" in str(code)


def test_a_row_named_twice_and_a_path_by_its_last_label_are_refused():
    """M92, M96."""
    for rows in ([FORMAT, FORMAT], [FORMAT, FORMAT + " "]):
        got = owner({"rows": rows, "confirm": [FORMAT]})
        assert any("named twice" in r for r in got["refusals"]), got
    import drive as D
    deep = "Shooting > File > File/Folder Settings > Format"
    rows = owner({"rows": [deep]})["rows"]
    assert "no row" in D.owner_path(["Format"], rows)[2]
    assert D.owner_path(["File/Folder Settings", "Format"], rows)[0] == deep


def test_the_serial_number_screen_is_blanked_from_its_opening(tmp_path, monkeypatch):
    """M99."""
    from PIL import Image
    info = info_of("Display Serial Number", {"rows": ["Display Serial Number"]})
    states = {"page": ("submenu", "Setup > Setup Option Display Serial Number", "Display Serial Number"),
              "serial": ("notice", f"Serial Number {SERIAL}", "")}
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "serial"}, label="Display Serial Number")
    cam.press("right")
    assert cam.blank and cam.hdmi.withheld and np.asarray(Image.open(cam.frame.path)).max() == 0


def test_drive_keeps_the_marker_when_the_restores_upload_fails_after_its_download(tmp_path, monkeypatch, scope_file):
    """M50: a restore that did not finish is never checked as if it had."""
    *_, code, restore, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."],
                                        RESET_DECISION, RESET_ASKS, ASKS_AND_CANCELS, more=["--confirm"],
                                        put_back_fails=True)
    assert code == 5 and restore == ["closed", "ended"] and restore_pending(tmp_path)


def test_drive_tells_the_camera_after_its_walk_that_only_the_owner_row_opens(tmp_path, monkeypatch, scope_file):
    """f1: drive.py sets LiveCamera.owner_only once its walk is done, never before it."""
    deep = {**FORMAT_STATES, "page": ("submenu", "Shooting > File File/Folder Settings Format", "Format")}
    for path, decision, states in ((["Format"], FORMAT_DECISION, FORMAT_STATES),
                                   (["File/Folder Settings", "Format"],
                                    {"rows": ["Shooting > File > File/Folder Settings > Format"]}, deep)):
        extra = {}
        drive_run(tmp_path, monkeypatch, scope_file, ["down"], path, decision, states, FORMAT_MOVES, extra=extra)
        assert extra["flag_at_walk"] is False and extra["cam"].owner_only is True, path


def test_drive_opens_a_row_only_with_right_and_reads_the_top_level_page_before_the_walk(tmp_path, monkeypatch,
                                                                                       scope_file):
    """N22: owner_open_decision takes Right alone; R15b/R28/M26: the top-level page's tab and group are read before
    the walk, which the title of a parent's page alone could not tell (a bare title reads the same in any group)."""
    import drive as D
    info = format_info()
    for key in ("enter", "ms_right", "ms_enter", " right"):
        assert "Right alone" in D.owner_open_decision(key, "Format", "submenu", "Format", info, True, True, False)[0]
    assert D.owner_open_decision("right", "Format", "submenu", "Format", info, True, True, False) == ("", "look")
    sub = "Playback > Playback Target > Playback Filter Condition > Protect"
    states = {"shoot": ("shooting", "", ""),
              "page": ("submenu", "Playback > Editing Playback Filter Condition Rating", "Playback Filter Condition"),
              "filter": ("submenu", "Playback Filter Condition Protect Rating", "Protect"),
              "opened": ("list", "Protect Multiple Img. Cancel All", "Multiple Img.")}
    moves = {("shoot", "menu"): "page", ("page", "right"): "filter", ("filter", "right"): "opened"}
    pressed, line, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["Playback Filter Condition", "Protect"],
                                  {"rows": [sub], "confirm": [sub]}, states, moves, start="shoot", more=["--confirm"],
                                  walk=True)
    assert pressed == ["menu"] and line["completed"] is False


def test_drive_reads_the_parents_page_again_at_a_deep_rows_opening(tmp_path, monkeypatch, scope_file):
    """f3: the page shown at the opening of a deeper row is its parent's own, its title read again there."""
    deep = "Shooting > File > File/Folder Settings > Format"
    for text, want in (("Shooting > File Select REC Folder Format", ["menu"]),
                       ("Shooting > File File/Folder Settings Format", ["menu", "right"])):
        states = {"page": ("submenu", text, "Format"), "slots": ("list", "Format Slot 1 Slot 2", "Slot 1")}
        pressed, *_ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], ["File/Folder Settings", "Format"],
                                {"rows": [deep], "confirm": [deep]}, states, {("page", "right"): "slots"},
                                more=["--confirm"])
        assert pressed == want, (text, pressed)


def test_a_row_whose_opening_may_change_the_network_needs_link_loss_whatever_it_logs():
    """N47/M07: "values": "logged" lets its screens be judged; it never stands in for "link_loss"."""
    for row in ("WPS Push", "Pairing"):
        said = owner({"rows": [row], "confirm": [row], "values": "logged"})["refusals"]
        assert said and "only with \"link_loss\": true" in said[0] and "blanked" not in said[0], said


# ---------------------------------------------------------------- a fifth review (2026-11-14)

WIRED_STATES = {"page": ("submenu", "Network > Wired LAN Wired LAN Connect", "Wired LAN Connect"),
                "list": ("list", "Wired LAN Connect On Off", "Off")}
WIRED_DECISION = {"rows": ["Wired LAN Connect"], "options": {"Wired LAN Connect": ["Off"]}, "link_loss": True}
NET_PLACES = PLACES + [("Network", "Bluetooth", "Bluetooth Rmt Ctrl"), ("Network", "Network Option", "Airplane Mode"),
                       ("Network", "Wi-Fi", "Wi-Fi Connect")]


def test_every_confirming_owner_run_asks_the_person_a_choice_that_may_drop_the_link_too(tmp_path, monkeypatch,
                                                                                         scope_file):
    """1: a never-choose option is an armed press that may drop the link and writes RESTORE_BY_HAND: the terminal
    question is asked before it as before any other confirming run; with no terminal nothing is pressed at all."""
    import drive as D
    pressed, _, _, code, restore, _, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Off"], ["Wired LAN Connect"], WIRED_DECISION, WIRED_STATES,
        {("page", "right"): "list", ("list", "enter"): "page"}, more=["--confirm"], typed=None)
    assert pressed == [] and restore == [] and "no terminal" in str(code) and restore_pending(tmp_path) is None
    extra = {}
    pressed, _, _, code, _, out, permits = drive_run(
        tmp_path, monkeypatch, scope_file, ["right", "enter:Off"], ["Wired LAN Connect"], WIRED_DECISION, WIRED_STATES,
        {("page", "right"): "list", ("list", "enter"): "page"}, more=["--confirm"], extra=extra)
    assert extra["asked"] and pressed == ["menu", "right", "enter"] and code == 0
    assert permits[-1] == {"row": "Wired LAN Connect", "what": "choose"}
    assert "choose Off, which may drop the link to the camera" in out
    # the other never-choose rows of the a1 II whose options a decision may name with "link_loss": each asked
    for row, opt in (("Access Authen. Settings", "Off"), ("Bluetooth Rmt Ctrl", "On"), ("Airplane Mode", "On"),
                     ("Wi-Fi Connect", "On")):
        got = owner({"rows": [row], "options": {row: [opt]}, "link_loss": True, "values": "logged"}, places=NET_PLACES)
        assert got["refusals"] == [], (row, got)
        info = got["rows"][row]
        assert safety.asks_person(info) and "which may drop the link" in D.armed_words(info), row


def test_a_run_that_logs_values_in_an_action_or_a_row_whose_opening_acts_is_still_asked(tmp_path, monkeypatch,
                                                                                        scope_file):
    """N33: "values": "logged" says what the run keeps, never who answers for the person."""
    logged = {"rows": ["WPS Push"], "confirm": ["WPS Push"], "link_loss": True, "values": "logged"}
    assert safety.asks_person(info_of("WPS Push", logged)) and info_of("WPS Push", logged)["acts_on_open"]
    assert safety.asks_person(format_info(values="logged"))
    for decision, path, states, moves in (({**RESET_DECISION, "values": "logged"}, ["Reset Network Set."],
                                           RESET_STATES, RESET_MOVES),
                                          ({**FORMAT_DECISION, "values": "logged"}, ["Format"], FORMAT_STATES,
                                           FORMAT_MOVES)):
        pressed, _, _, code, restore, _, _ = drive_run(tmp_path, monkeypatch, scope_file, ["right"], path, decision,
                                                       states, moves, more=["--confirm"], typed=None)
        assert pressed == [] and restore == [] and "no terminal" in str(code), (path, code)


def test_the_terminal_question_shows_the_place_and_never_prints_the_answer(capsys):
    """4: the prompt shows the row's whole place and asks for its name; it never writes the name out as the word to
    type (the place holds it, as the last label)."""
    import drive as D
    assert D.typed_word("Format", ["Shooting", "Media", "Format"], "format", "TEST-CAM_fw9.99",
                        read=lambda p: "Format", tty=True) == ""
    out = capsys.readouterr().out
    assert "'Shooting > Media > Format'" in out and "row's name" in out
    assert "'Format'" not in out and "type: format" not in out.lower() and "name, Format" not in out


def test_the_terminal_question_names_what_a_card_writing_or_registering_row_leaves(shipped):
    """5: a row that writes to a card, and one whose first Enter registers, are named for what nothing puts back."""
    import drive as D
    for entry in (CREATE, PROTECT):
        info = info_of(entry, {"rows": [entry], "confirm": [entry]})
        assert D.armed_words(info) == "write to a card, which nothing puts back", entry
    memory = info_of(MEMORY, {"rows": [MEMORY], "options": {MEMORY: ["M1"]}, "confirm": [MEMORY]})
    assert D.armed_words(memory) == "register at once; no settings file puts it back"
    for label in ("Create New Folder", "Protect", "Rotate", "Copy", "Crop", "Recover Image DB"):
        assert safety.writes_card(label) and not safety.registers(label), label
    for label in ("Copyright Info", "Camera Set. Memory", "Format", "Protection"):
        assert not safety.writes_card(label), label
    assert D.armed_words(info_of(RESET_NET, RESET_DECISION)).startswith("reset the camera's network setup")
    assert D.armed_words(info_of(FORMAT, {"rows": [FORMAT], "confirm": [FORMAT]})).startswith("format or delete")
    assert "drop the link" in D.armed_words(info_of("WPS Push", {"rows": ["WPS Push"], "confirm": ["WPS Push"],
                                                                 "link_loss": True, "values": "logged"}))
    assert D.armed_words(info_of(SETTING_RESET, {"rows": [SETTING_RESET], "confirm": [SETTING_RESET]})) == \
        "confirm the row's action"
    assert D.armed_words(info_of("Bluetooth Function", {"rows": ["Bluetooth Function"],
                                                        "options": {"Bluetooth Function": ["Off"]}})) == "choose Off"
    assert "only open the row, to look" in D.armed_words(info_of("Access Authen. Info", {"rows": ["Access Authen. Info"]}))


def test_a_parents_page_never_passes_for_its_childs_on_a_deep_path():
    """2: after a parent in the breadcrumb only " > " joins the title; a space joins it right after the tab or the
    group alone."""
    import drive as D
    lead = ["Shooting", "File", "File/Folder Settings"]
    assert D.title_refused("submenu", "Shooting > File > File/Folder Settings File Number Folder Name", "File Number",
                           lead)
    assert D.title_refused("submenu", "Shooting > File > File/Folder Settings > File Number Reset Series",
                           "File Number", lead) == ""
    assert D.title_refused("submenu", "Shooting > File File/Folder Settings File Number", "File/Folder Settings",
                           ["Shooting", "File"]) == ""
    assert D.title_refused("submenu", "Shooting File/Folder Settings File Number", "File/Folder Settings",
                           ["Shooting", "File"]) == ""


def test_the_walk_refuses_a_right_that_left_the_page_where_it_was(monkeypatch):
    """2: a Right the camera ignored, or drew late, leaves the parent's own page, whose breadcrumb and lit row read as
    the parent's title: the walk refuses on the position alone, and on two screens it cannot compare."""
    import drive as D
    at = {"s": "top"}
    screens = {"top": ("submenu", "Playback > Playback Target Playback Filter Condition Protect",
                       "Playback Filter Condition"),
               "top2": ("submenu", "Playback > Playback Target Playback Filter Condition Protect", "Protect")}
    moves = {("top", "down"): "top2", ("top2", "down"): "top"}             # Right ignored
    cam = SimpleNamespace(frame=SimpleNamespace(image=None, path=None),
                          read=lambda: SimpleNamespace(kind=screens[at["s"]][0], where=at["s"]))
    cam.press = lambda key, **kw: at.__setitem__("s", moves.get((at["s"], key), at["s"]))
    monkeypatch.setattr(D, "highlighted", lambda image, path: screens[at["s"]][2])
    monkeypatch.setattr(D, "screen_text", lambda c, grip: screens[at["s"]][1])
    monkeypatch.setattr(D, "same_position", lambda a, b: a.where == b.where)
    assert "same position" in D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB)
    assert at["s"] == "top"                                                 # nothing pressed after it

    def cannot(a, b):
        raise ValueError("no picture")
    moves[("top", "right")] = "top2"
    monkeypatch.setattr(D, "same_position", cannot)
    assert "same position" in D.owner_walk(cam, ["Playback Filter Condition", "Protect"], None, PB)
