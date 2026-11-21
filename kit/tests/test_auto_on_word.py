"""Intelligent Auto chosen on the owner's word (2026-11-21): its lit icon in Shoot Mode's family column is green, which
the red reading cannot judge, so the kit refused it (grey before Enter). The owner, shown the screen: "AUTO in a green
box is for auto mode when the camera selects the aperture , shutter, and iso automatically", then, asked whether the
kit may select it: "Yes you can use it and any other modes on that screen". So a run that names the entry
(--allow "Intelligent Auto") may choose it, and only where its lit icon is drawn in the look the camera's 550 frames
show (proving.greyed.auto_look: the lit row's band of the column, 373 to 745 green pixels at a 95th percentile of
green of 204 to 255; with any other mode lit, none); any other look, or the run without the word: refused as before.
It is an allowance, not a misjudgement: the grey memory still refuses where it marks the row. The camera's own frames
where the runs hold them; nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import load  # noqa: E402

pytestmark = pytest.mark.real_grey


def cam_of(rel: str):
    f = paths.a1ii_root() / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    frame = load(f)
    return SimpleNamespace(frame=frame, read=lambda: screen.read(frame))


IA_LIT = [("kit2_sq_1120c/shots/00048_reread.png", 237.0),        # the frame the owner was shown: S&Q, Intelligent Auto
          ("kit2_a1fin_look_sq/shots/00005_down.png", 204.0),       # the dimmest of the 550 (OSD eyes)
          ("kit2_crawl_sq_1120/shots/00107_left.png", 255.0)]       # the brightest
P_LIT = ["kit2_sq_1120c/shots/00050_reread.png", "kit2_crawl_sq_1120/shots/00056_left.png"]


@pytest.mark.parametrize("rel, p95", IA_LIT)
def test_the_lit_intelligent_auto_icon_measures_in_its_normal_look(rel, p95):
    from proving import greyed
    ok, level, n = greyed.auto_look(cam_of(rel))
    assert ok is True and level >= greyed.AUTO_GREEN and n >= greyed.AUTO_MIN, (rel, level, n)
    assert abs(level - p95) < 1.5 or rel.endswith("00048_reread.png")


@pytest.mark.parametrize("rel", P_LIT)
def test_another_mode_lit_shows_no_green_in_the_lit_row(rel):
    from proving import greyed
    ok, level, n = greyed.auto_look(cam_of(rel))
    assert ok is None and n == 0


def made_up(rgb, rows=(193, 217)):
    a = np.zeros((480, 640, 3), np.uint8)
    a[rows[0]:rows[1], 20:52] = rgb
    return SimpleNamespace(frame=SimpleNamespace(image=a, path=Path("00001_made-up.png")),
                           read=lambda: SimpleNamespace(kind="dialog", bar=None))


@pytest.mark.parametrize("rgb, rows, ok", [
    ((40, 240, 60), (193, 217), True),          # bright green, the size of the icons measured
    ((30, 150, 40), (193, 217), None),          # a dim green nobody has seen drawn: never taken as the normal look
    ((40, 240, 60), (205, 210), None),          # too few green pixels for the icon
    ((40, 240, 60), (130, 160), None),          # green on another family's row, nothing on the lit row
])
def test_a_look_outside_the_measured_one_is_never_the_normal_look(rgb, rows, ok):
    from proving import greyed
    assert greyed.auto_look(made_up(rgb, rows))[0] is ok


def test_the_word_lifts_cannot_be_told_for_intelligent_auto_alone(monkeypatch):
    from proving import greyed
    monkeypatch.setattr(greyed, "misjudged", lambda name, reading: None)
    cam = made_up((40, 240, 60))
    label = "S&Q Motion, Intelligent Auto"
    assert "cannot be told" in greyed.choice_refused(cam, "Shoot Mode", label)            # no word: as before
    assert greyed.choice_refused(cam, "Shoot Mode", label, auto_allowed=True) == ""
    dim = made_up((30, 150, 40))
    why = greyed.choice_refused(dim, "Shoot Mode", label, auto_allowed=True)
    assert "not the look the camera draws it in" in why and "nothing was pressed" in why
    # the word is the owner's for Shoot Mode's Intelligent Auto: no other row, no other entry
    assert "cannot be told" in greyed.choice_refused(cam, "Drive Mode", "Intelligent Auto", auto_allowed=True)
    assert "cannot be told" in greyed.choice_refused(cam, "Shoot Mode", "S&Q Motion, Program Auto", auto_allowed=True)


def test_the_grey_memory_still_refuses_where_it_marks_the_row(monkeypatch):
    from proving import greyed
    monkeypatch.setattr(greyed, "misjudged", lambda name, reading: {"run": "x", "frame": "00001.png"})
    why = greyed.choice_refused(made_up((40, 240, 60)), "Shoot Mode", "S&Q Motion, Intelligent Auto", auto_allowed=True)
    assert "marked misjudged" in why


def test_the_runs_flag_names_the_entry_and_nothing_else():
    import mode_switch
    import shootmode_run
    assert mode_switch.auto_allowed_or_exit(["Intelligent Auto"]) is True
    assert mode_switch.auto_allowed_or_exit([]) is False
    with pytest.raises(SystemExit, match="names only 'Intelligent Auto'"):
        mode_switch.auto_allowed_or_exit(["Program Auto"])
    assert shootmode_run.auto_allowed_or_exit is mode_switch.auto_allowed_or_exit


def test_the_choosers_pass_the_word_to_the_judgement():
    src = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in ("kit/provers/mode_switch.py",
                                                                     "kit/provers/shootmode_run.py")}
    assert 'auto_allowed=auto and got == AUTO_ENTRY' in src["kit/provers/mode_switch.py"]
    assert 'auto_allowed=auto and got == AUTO_ENTRY' in src["kit/provers/shootmode_run.py"]
    assert "choice_refused(cam, \"Shoot Mode\"" in src["kit/provers/shootmode_run.py"]
