"""The reviewer's three gaps in the 1fps refusal (2026-11-21): a run that reaches S&Q Frame Rate 1fps by its own choice
(prove_run on the frame rate, boxes_run, drive.py, a table walk: kit2_pass2 chose 1fps in S&Q, 277325) presses nothing
more but MENU on that link until its restore, as camkit.link judges every download; mode_switch --set compares the
option as the box choice reads it (option_key: "1 fps", "1FPS", "Ifps"); the owner's message says "nothing more was
pressed" and names no frame of this camera's runs. Nothing talks to a camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import link as camlink, safety, slow_states  # noqa: E402

DOC = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
LIVE, RATE = (0, 0x13bf), (0, 0x0248)


def reader(live, rate):
    return lambda section, rid: {LIVE: live, RATE: rate}.get((section, rid))


def a_link(monkeypatch, live, rate, tmp_path):
    """A Link whose downloads hold the given live mode and S&Q rate, and whose presses would go out (Sent)."""
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(live, rate))
    monkeypatch.setattr(camlink, "slow_doc", lambda: DOC)
    lk = camlink.Link.__new__(camlink.Link)
    lk.run = SimpleNamespace(dat_name=lambda tag: f"00001_{tag}", dat=tmp_path, root=tmp_path,
                             dir=SimpleNamespace(name="x"), log=lambda *a, **k: None)
    lk.model = "ILCE-1M2"
    lk.slow = ""
    monkeypatch.setattr(lk, "_must", lambda command, **kw: {"path": str(tmp_path / "00001_x.DAT")}, raising=False)
    monkeypatch.setattr(camlink.provenance, "record", lambda *a, **k: None)
    return lk


def test_a_download_in_the_state_leaves_menu_alone_until_one_without_it(monkeypatch, tmp_path):
    lk = a_link(monkeypatch, 2, 15, tmp_path)
    lk.download("after-choice")
    assert "S&Q Frame Rate at 1fps" in lk.slow
    for verb, args in (("press", ["down", "60"]), ("press", ["enter", "60"]), ("dial", ["rear", "1"])):
        with pytest.raises(safety.Refused, match="nothing more is pressed but MENU"):
            lk.slow_guard(verb, args)
    lk.slow_guard("press", ["menu", "60"])                     # MENU still goes: the way to the restore
    lk.slow_guard("upload", ["x.DAT"])                         # the restore itself presses nothing
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(2, 2))
    lk.download("restored")
    assert lk.slow == ""
    lk.slow_guard("press", ["down", "60"])


def test_a_download_out_of_the_state_changes_nothing(monkeypatch, tmp_path):
    lk = a_link(monkeypatch, 0, 15, tmp_path)                  # Stills, the S&Q rate 1fps: not the state
    lk.download("before")
    assert lk.slow == ""


def test_the_guard_sits_in_the_links_one_check():
    src = (ROOT / "kit" / "camkit" / "link.py").read_text(encoding="utf-8")
    assert "self.slow_guard(verb, args)" in src


@pytest.mark.parametrize("option", ["1fps", "1 fps", "1FPS", "Ifps", "1fps "])
def test_set_reads_the_option_as_the_box_choice_does(option):
    import mode_switch
    assert "the kit never sets it" in mode_switch.set_refused(DOC, [f"S&Q Settings > Frame Rate Settings > Frame Rate={option}"])
    assert "the kit never sets it" in mode_switch.set_refused(DOC, [f"S&Q settings > frame rate settings > frame rate={option}"])
    assert mode_switch.set_refused(DOC, ["S&Q Settings > Frame Rate Settings > Frame Rate=2fps"]) == ""


@pytest.mark.parametrize("path, lit, refused", [
    (["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "1fps", True),
    (["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "1 fps", True),
    (["S&Q Settings", "Frame Rate Settings"], "1fps", True),              # walked down from a row above it
    (["S&Q Settings"], "Ifps", True),
    (["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "2fps", False),
    (["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "Frame Rate", False),
    (["Exposure/Color", "Exposure"], "1fps", False),                     # another row's option of that label
    ([], "1fps", False),
])
def test_drive_never_chooses_the_state_on_its_rows_way(path, lit, refused):
    import drive
    for key in ("enter", " Enter", "ms_enter"):
        why = drive.slow_choice_refused(DOC, path, key, lit)
        assert bool(why) == refused and (not why or "the kit never sets it" in why)
    assert drive.slow_choice_refused(DOC, ["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "down", "1fps") == ""


def test_drive_judges_the_choice_where_it_judges_each_press():
    src = (ROOT / "kit" / "drive.py").read_text(encoding="utf-8")
    assert "slow_choice_refused(definition(), a.path, key, lit)" in src


def test_set_keeps_to_the_row_itself():
    assert slow_states.sets_state(DOC, ["S&Q Settings", "Frame Rate Settings"], "1fps") == ""
    assert slow_states.chosen(DOC, ["S&Q Settings", "Frame Rate Settings"], "1fps") is None
    assert slow_states.chosen(DOC, ["S&Q Settings", "Frame Rate Settings"], "1fps", within=True)["label"] == "1fps"


def test_the_owners_message_says_nothing_more_was_pressed_and_names_no_frame(monkeypatch):
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(2, 15))
    why = slow_states.refusal(DOC, "x.DAT", doing="prove_run.py")
    assert "Nothing more was pressed" in why and "Nothing was pressed" not in why
    assert "kit2_" not in why and "0449" not in why
