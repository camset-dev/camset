"""A lit one-letter row OCR does not read (2026-11-21): on Picture Profile's Color Depth panel Apple Vision drops a lone
white letter on the orange bar (kit2_pass2 304086: the M lit, OCR reads R G B C Y; 304087: the Y lit, OCR reads R G B C
M), so find_row found "no row 'M'" and the S&Q proofs failed. proving.screens.lit_letter gives the lit bar a label only
from TWO signs that agree: the label OCR read at the bar's place on the frame before (the cursor moved one row; every
row both frames read outside the two bars reads alike) AND the second reader's label for the lit bar
(camkit.live.reader_label; the third readers do not count). Where they differ, or either is missing, there is no label,
as before. The camera's own frames where the runs hold them; the reader made up; nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
from camkit import paths, screen  # noqa: E402

pytestmark = pytest.mark.real_grey


def cam_of(rel):
    from camkit.frames import load
    f = paths.a1ii_root() / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    frame = load(f)
    return SimpleNamespace(frame=frame, read=lambda: screen.read(frame))


SHOTS = "kit2_pass2/shots/"


@pytest.mark.parametrize("before, now, letter", [
    ("304085_down.png", "304086_down.png", "M"),       # C lit, then M lit: OCR reads no M on 304086
    ("304086_down.png", "304087_down.png", "Y"),       # M lit, then Y lit: OCR reads no Y on 304087
])
def test_the_lit_letter_rests_on_the_frame_before_and_the_second_reader(monkeypatch, before, now, letter):
    from camkit import live
    from proving import screens
    cam, prev = cam_of(SHOTS + now), cam_of(SHOTS + before)
    assert screens.bar_text(cam) == ""                            # what OCR reads on the lit bar: nothing
    monkeypatch.setattr(live, "reader_label", lambda path, timeout=None: (letter, ""))
    assert screens.lit_letter(cam, prev.frame) == letter
    monkeypatch.setattr(live, "reader_label", lambda path, timeout=None: ("G", ""))          # the reader disagrees
    assert screens.lit_letter(cam, prev.frame) == ""
    monkeypatch.setattr(live, "reader_label", lambda path, timeout=None: ("", "the reader failed"))
    assert screens.lit_letter(cam, prev.frame) == ""                                          # one sign alone
    assert screens.lit_letter(cam, None) == ""                                                # no frame before


def test_a_page_that_changed_between_the_frames_gives_no_label(monkeypatch):
    """The frame before must be the same page: a row both frames read outside the two bars, read otherwise, is a
    changed page (304080: the panel's own rows, Color Depth lit, before the Color Depth list opened)."""
    from camkit import live
    from proving import screens
    cam, prev = cam_of(SHOTS + "304086_down.png"), cam_of(SHOTS + "304080_down.png")
    monkeypatch.setattr(live, "reader_label", lambda path, timeout=None: ("M", ""))
    assert screens.lit_letter(cam, prev.frame) == ""


def test_a_bar_ocr_reads_is_never_relabelled(monkeypatch):
    from camkit import live
    from proving import screens
    cam, prev = cam_of(SHOTS + "304085_down.png"), cam_of(SHOTS + "304084_down.png")
    assert screens.bar_text(cam) == "C"
    monkeypatch.setattr(live, "reader_label", lambda path, timeout=None: ("M", ""))
    assert screens.lit_letter(cam, prev.frame) == ""                  # OCR read the bar: no second way


def test_find_row_hands_the_frame_before_to_the_label(monkeypatch):
    """find_row asks at_label with the frame before each Down, so a lit letter OCR drops can be found (lit_letter)."""
    from proving import nav
    seen = []

    class Cam:
        def __init__(self):
            self.n, self.frame = 0, SimpleNamespace(path=Path("00000.png"))

        def read(self):
            return SimpleNamespace(kind="submenu", n=self.n)

        def press(self, key, **kw):
            self.n += 1
            self.frame = SimpleNamespace(path=Path(f"{self.n:05d}.png"))

    def at_label(cam, kind, label, prev=None):
        seen.append((cam.n, prev.path.name if prev is not None else None))
        return cam.n == 2
    monkeypatch.setattr(nav, "at_label", at_label)
    monkeypatch.setattr(nav, "bar_text", lambda cam: "")
    monkeypatch.setattr(nav, "same_state", lambda a, b: False)
    assert nav.find_row(Cam(), "M") is True
    assert seen == [(0, None), (1, "00000.png"), (2, "00001.png")]
