"""An entry a prover is about to choose by a caller's word is judged first (proving.greyed.choice_drawing,
choice_refused, 2026-11-20): drawn grey is never entered, and a drawing no pixel reading can tell is not entered on a
guess. Per screen kind: a list's and a side list's lit band and a carousel's lit icon (proving.screens.drawn_grey), a
checklist item's label on its row's band (CHECK_X); a grid of boxes or a table has no reading. The camera's own frames
where the runs hold them, a made-up icon where they hold no greyed carousel entry; then each prover wired to it stops
before its Enter. Nothing talks to a camera."""
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

A1 = paths.a1ii_root()


def cam_of(rel: str):
    f = A1 / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    frame = load(f)
    return SimpleNamespace(frame=frame, read=lambda: screen.read(frame))


@pytest.mark.parametrize("rel, kind, grey", [
    ("kit2_pass2/shots/14373_down.png", "list", True),          # Flash Sync Spd. Prty.'s On, greyed with E-Shutter
    ("kit2_pass2/shots/14389_up.png", "list", False),           # its Off, taken
    ("kit2_pass2/shots/270326_fresh.png", "dialog", False),     # movie Self-timer's On, its red icon bright
    ("kit2_sq_1120/shots/00051_right.png", "dialog", False),    # Shoot Mode, S&Q Motion's Program Auto
    ("kit2_crawl_sq_1120/shots/00056_left.png", "dialog", False),     # Shoot Mode, Time-lapse's Program Auto
    ("kit2_sq_1120/shots/00049_down.png", "dialog", None),      # Shoot Mode, Intelligent Auto: a green icon
    ("kit2_crawl_movie_playback/shots/00094_right.png", "checklist", False),   # Playback Filter Condition's Date
])
def test_the_cameras_entries_are_told_grey_white_or_not_at_all(rel, kind, grey):
    from proving import greyed
    cam = cam_of(rel)
    assert cam.read().kind == kind
    got, level, how = greyed.choice_drawing(cam)
    assert got is grey, (rel, level, how)
    if grey is None:
        assert "not the red one" in how


def icon_cam(rgb):
    """A carousel frame whose lit icon in the left column is drawn in `rgb` (test_finish_kit's made-up icon)."""
    a = np.zeros((480, 640, 3), np.uint8)
    a[150:250, 20:90] = rgb
    return SimpleNamespace(frame=SimpleNamespace(image=a, path=Path("00001_made-up.png")),
                           read=lambda: SimpleNamespace(kind="dialog", bar=None))


def test_a_carousel_entry_with_a_dim_red_icon_is_refused_and_a_bright_one_chosen():
    """The runs hold no greyed carousel entry's frame now: the icon's red as proving.screens measured it on the camera
    (102-124 refused, 209-255 taken), made up."""
    from proving import greyed
    assert greyed.choice_refused(icon_cam((230, 60, 40)), "Drive Mode", "Cont. Bracket") == ""
    why = greyed.choice_refused(icon_cam((115, 30, 30)), "Drive Mode", "Cont. Bracket")
    assert "'Cont. Bracket' is drawn grey" in why and "never entered" in why and "nothing was pressed on it" in why
    why = greyed.choice_refused(icon_cam((165, 50, 40)), "Drive Mode", "Cont. Bracket")
    assert "cannot be told" in why and "not entered on a guess" in why


def test_a_screen_no_reading_measures_is_refused_saying_so():
    from proving import greyed
    cam = SimpleNamespace(frame=SimpleNamespace(image=np.zeros((480, 640, 3), np.uint8), path=Path("00002_grid.png")),
                          read=lambda: SimpleNamespace(kind="checkgrid", bar=None))
    why = greyed.choice_refused(cam, "Different Set for Still/Mv", "ISO")
    assert "no pixel reading for an entry of a 'checkgrid' screen" in why and "cannot be told" in why


def test_the_grey_list_entry_on_the_camera_is_refused_in_plain_words():
    from proving import greyed
    why = greyed.choice_refused(cam_of("kit2_pass2/shots/14373_down.png"), "Flash Sync Spd. Prty.", "On")
    assert why.startswith("Flash Sync Spd. Prty.: 'On' is drawn grey (its lit band's text, it reads 118")
    assert why.endswith("nothing was pressed on it")


# ------------------------------------------------------------------ each prover stops before its Enter

class Pressed(SimpleNamespace):
    def press(self, key, **kw):
        self.keys.append(key)


def refusing(monkeypatch):
    from proving import greyed
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (True, 118.0, "its lit band's text"))


def test_mode_switch_never_oks_a_greyed_shoot_mode_entry(monkeypatch):
    import mode_switch as M
    refusing(monkeypatch)
    cam = Pressed(keys=[], frame=SimpleNamespace(path=Path("00010_down.png"), image=None),
                  read=lambda: SimpleNamespace(kind="dialog"))
    monkeypatch.setattr(M, "find", lambda *a: None)
    monkeypatch.setattr(M, "mode_name", lambda c: "Program Auto")
    monkeypatch.setattr(M.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
    monkeypatch.setattr(M.ocr, "text_in", lambda lines, box: "Shoot Mode")
    with pytest.raises(M.Failed, match="'Time-lapse, Program Auto' is drawn grey"):
        M.shoot_mode(cam, None, None, 3, "Program Auto", lambda m: None)
    assert "enter" not in cam.keys


def test_carousel_fields_run_never_enters_a_greyed_option(monkeypatch):
    import carousel_fields_run as F
    refusing(monkeypatch)
    cam = Pressed(keys=[], frame=SimpleNamespace(path=Path("00011_x.png"), image=None))
    monkeypatch.setattr(F, "option_refused", lambda cam, option, labels: "")
    with pytest.raises(F.Failed, match="'On' is drawn grey"):
        F.enter(cam, "On", ["On", "Off"], None, None, None)
    assert cam.keys == []


def test_optboxes_run_never_enters_the_boxes_of_a_greyed_option(monkeypatch):
    import optboxes_run as O
    refusing(monkeypatch)
    cam = Pressed(keys=[], frame=SimpleNamespace(path=Path("00012_x.png"), image=None))
    with pytest.raises(O.Failed, match="'Custom 1' is drawn grey"):
        O.enter_box(cam, 0, ["Type"], "Custom 1")
    assert cam.keys == []


def test_bracket_run_never_oks_a_greyed_option(monkeypatch):
    import bracket_run as B
    refusing(monkeypatch)
    cam = Pressed(keys=[], frame=SimpleNamespace(path=Path("00013_x.png"), image=None),
                  read=lambda: SimpleNamespace(kind="dialog", field=None))
    monkeypatch.setattr(B.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
    monkeypatch.setattr(B.ocr, "text_in", lambda lines, box: "Drive Mode")
    with pytest.raises(B.Failed, match="'Cont. Bracket' is drawn grey"):
        B.commit(cam, "Cont. Bracket")
    assert cam.keys == []


def test_prove_run_judges_a_first_value_and_never_enter_grey_checklist_boxes():
    """Where the judgement sits in prove_run's axis rows (--first, or every value under --never-enter-grey, the
    put-back aside) and in its checklist rows (--never-enter-grey): before each Enter, read from the source."""
    src = (ROOT / "kit" / "prove_run.py").read_text(encoding="utf-8")
    at = src.index("why = greyed.choice_refused(cam, name, axis_title(cam))")
    assert at < src.index("chosen, shown, seen_vlm = enter_chosen(cam, (cam.frame.path.name, axis_title(cam)", at)
    chk = (ROOT / "kit" / "proving" / "checklists.py").read_text(encoding="utf-8")
    at = chk.index("why = greyed.choice_refused(cam, name, labels[box])")
    assert at < chk.index('cam.press("enter")', at)
