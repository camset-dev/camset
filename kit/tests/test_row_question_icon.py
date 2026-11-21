"""The lit bar before Right on Exposure Std. Adjust, where the row draws an icon before its label (2026-11-21): in the
Movie and S&Q menus OCR reads the bar as "SExposure Std. Adjust" (kit2_crawl_expstd_mv 00013_down, kit2_crawl_expstd_sq
00011_down), the icon read as an S glued to the first word, so safety.bar_on_row refused it and the question was never
answered (expstd_movie_sq, 13:2x). proving.screens.bar_is_row takes the bar as the row only where bar_on_row takes the
lit text, OR an icon stands at the bar's start (camkit.screen.label_icons), the bar's label read with it painted over
(page_model.covered_readings, as camkit.crawl.icon_entry reads a row) passes bar_on_row, and the lit text is that
reading with at most ICON_LEAD letters in front: the bar must still BE the row. Every other caller of bar_on_row is
unchanged. The camera's own frames where the runs hold them; nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
from camkit import paths  # noqa: E402

ROW = "Exposure Std. Adjust"


def frame_of(rel):
    from camkit.frames import load
    f = paths.a1ii_root() / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    return load(f)


@pytest.mark.parametrize("rel, lit, ok", [
    ("kit2_crawl_expstd_mv/shots/00013_down.png", "SExposure Std. Adjust", True),        # Movie: the icon glued on
    ("kit2_crawl_expstd_sq/shots/00011_down.png", "SExposure Std. Adjust", True),        # S&Q: the same
    ("kit2_a1fin_look_stills/shots/00191_down.png", "R Exposure Std. Adjust", True),     # Stills: the icon set apart
    ("kit2_crawl_expstd_mv/shots/00012_down.png", "PExposure step 0.3EV", False),        # the row above lit
])
def test_the_lit_bar_is_the_row_by_its_label_right_of_the_icon(rel, lit, ok):
    from camkit import live
    from proving import screens
    frame = frame_of(rel)
    assert live.lit_text(frame.image, frame.path) == lit
    assert screens.lit_icon_label(frame).strip() in ("Exposure Std. Adjust", "Exposure step")
    assert screens.bar_is_row(lit, ROW, frame) is ok
    assert screens.bar_is_row(lit, ROW) is False            # with no frame: bar_on_row alone, as before


def test_the_question_frames_of_movie_and_s_and_q_read_as_the_question():
    from camkit import live, ocr, safety
    for rel in ("kit2_crawl_expstd_mv/shots/00014_right.png", "kit2_crawl_expstd_sq/shots/00012_right.png"):
        frame = frame_of(rel)
        text = ocr.text_in(ocr.read([frame.path])[frame.path], (0, 0, 640, 480))
        assert safety.row_question(text, ROW) == "", rel
        assert live.lit_text(frame.image, frame.path).strip() == "Cancel"


@pytest.mark.parametrize("lit, covered, ok", [
    ("SExposure Std. Adjust", "Exposure Std. Adjust", True),
    ("S&Q Exposure Std. Adjust", "Exposure Std. Adjust", True),         # three letters, set apart
    ("VWXYZExposure Std. Adjust", "Exposure Std. Adjust", False),       # five letters: more than an icon's
    ("A B Exposure Std. Adjust", "Exposure Std. Adjust", False),        # two tokens in front: no icon's reading
    ("SExposure Std. Adjust", "Exposure Comp.", False),                 # the covered reading is another row
    ("SExposure Std. Adjustment", "Exposure Std. Adjustment", False),   # a longer label
    ("SExposure Std. Adjust", "", False),                               # no icon found
])
def test_the_icon_way_holds_only_for_the_row_itself(monkeypatch, lit, covered, ok):
    from proving import screens
    monkeypatch.setattr(screens, "lit_icon_label", lambda frame: covered)
    assert screens.bar_is_row(lit, ROW, SimpleNamespace(image=None, path=Path("x.png"))) is ok


def test_the_pass_takes_the_frame_before_right(monkeypatch):
    """pass_row_question judges the bar with the frame before Right (crawl_run's info_ok and nav.enter_path give it)."""
    from proving import screens
    calls = []
    monkeypatch.setattr(screens, "ROW_QUESTION", {ROW})
    monkeypatch.setattr(screens, "bar_is_row", lambda lit, row, frame=None: calls.append((lit, row, frame)) or False)
    cam = SimpleNamespace(frame=SimpleNamespace(path=Path("00014_right.png")), read=lambda: SimpleNamespace(kind="notice"))
    before = SimpleNamespace(image=None, path=Path("00013_down.png"))
    got = screens.pass_row_question(cam, ROW, "SExposure Std. Adjust", before)
    assert "not the row named" in got["refused"] and calls == [("SExposure Std. Adjust", ROW, before)]


def test_the_callers_hand_the_frame_before_right():
    src = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in ("kit/crawl_run.py", "kit/proving/nav.py")}
    assert "screens.pass_row_question(cam, name, lit, before)" in src["kit/crawl_run.py"]
    assert "screens.pass_row_question(cam, \" > \".join(path[:k]), lit, before)" in src["kit/proving/nav.py"]
