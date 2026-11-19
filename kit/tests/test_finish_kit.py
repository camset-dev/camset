"""Faults met on the a1 II while finishing its mapping (2026-11-19), each with the refusals around it that stay.

1. A notice on a dark scene taken for a black frame (camkit.live.black): a first open ended with RESTORE_BY_HAND.

Run: .venv/bin/python -m pytest kit/tests/test_finish_kit.py -q
The camera's frames live under runs/ (not versioned); the tests that read them skip when absent, the ones on drawn
pictures and made-up text run everywhere.
"""
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive  # noqa: E402
from camkit import live, paths, safety, screen, vlm  # noqa: E402
from camkit.frames import load  # noqa: E402

A1 = paths.a1ii_root()


def need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def frame_of(image, name="00001_x.png"):
    return SimpleNamespace(image=image, path=Path(name), t=0.0)


# ---------------------------------------------------------------- 1. a notice on a dark scene is not black

def blank(level=0) -> np.ndarray:
    return np.full((480, 640, 3), level, np.uint8)


def notice_picture() -> np.ndarray:
    """A notice drawn as the camera draws "Lens: Invalid with this lens. OK" over a capped lens: a frame line at grey 68,
    a title, a line of text and an OK, white strokes 3 px wide, on black; mean well under BLACK."""
    a = blank()
    a[14:16, 30:610] = a[408:410, 30:610] = 68
    a[14:410, 30:32] = a[14:410, 608:610] = 68
    for x0, x1, y0, y1 in ((250, 390, 60, 110), (205, 435, 258, 288), (565, 625, 440, 466)):
        for x in range(x0, x1, 9):                     # letters: upright strokes and a bar across each word
            a[y0:y1, x:x + 3] = 235
        a[y0:y0 + 3, x0:x1] = 235
    return a


def test_a_frame_with_text_drawn_is_not_black_whatever_its_mean():
    a = notice_picture()
    assert float(a.mean()) <= live.BLACK and live.dark(frame_of(a))
    assert not live.black(frame_of(a))
    shooting = blank()
    shooting[440:470, 40:600:12] = 220                 # the readouts along the bottom, a dark live view behind
    shooting[440:470, 41:600:12] = 220
    shooting[440:470, 42:600:12] = 220
    assert not live.black(frame_of(shooting))


@pytest.mark.parametrize("name", ["zeros", "low noise", "salt", "frame line only", "a few lit pixels"])
def test_a_blanked_frame_stays_black_with_its_noise(name):
    """HDMI blanked (Auto Framing in Movie mode): black, as are its noise, a notice's frame line with no text in it (a
    notice drawing or closing, kit2_a1fin_look_sq 00795) and stray lit pixels that make no stroke."""
    rng = np.random.default_rng(7)
    a = blank()
    if name == "low noise":
        a = rng.integers(0, 12, a.shape).astype(np.uint8)      # mean 5.5, under BLACK as a blanked frame's
    elif name == "salt":
        a[rng.random(a.shape[:2]) < 0.01] = 255
    elif name == "frame line only":
        a[14:16, 30:610] = a[408:410, 30:610] = a[14:410, 30:32] = a[14:410, 608:610] = 68
    elif name == "a few lit pixels":
        a[100:102, 100:110] = 255                      # 9 blocks of 2 x 2: under INK_MIN
    assert live.dark(frame_of(a)) and live.black(frame_of(a)), name


def test_a_frame_above_the_level_is_not_black_and_a_frame_without_a_picture_neither():
    assert not live.black(frame_of(blank(40)))
    assert not live.black(frame_of(None)) and not live.dark(frame_of(None))


def test_after_armed_reads_a_notice_on_a_dark_scene_and_still_refuses_a_blanked_frame(monkeypatch):
    """kit/drive.py's read after a first open: the notice is a screen it reads (so the run goes on to MENU and the remote
    restore); a blanked frame, a kind it does not read, or no text, still refuse as before."""
    monkeypatch.setattr(drive, "screen_text", lambda cam, grip: cam.text)

    def cam(image, kind, text="Lens Invalid with this lens. OK"):
        c = SimpleNamespace(frame=frame_of(image), text=text)
        c.refresh = lambda tag: SimpleNamespace(kind=kind)
        return c
    assert drive.after_armed(cam(notice_picture(), "notice"), None, safety.FIRST_OPEN_KINDS)[2] == ""
    assert drive.after_armed(cam(blank(), "notice"), None, safety.FIRST_OPEN_KINDS)[2] == "the frame after it is black"
    assert "no kind the kit reads" in drive.after_armed(cam(notice_picture(), "unknown"), None, safety.FIRST_OPEN_KINDS)[2]
    assert drive.after_armed(cam(notice_picture(), "notice", "  "), None, safety.FIRST_OPEN_KINDS)[2] == \
        "no text could be read on the screen after it"


def test_a_screen_of_no_known_kind_on_a_dark_frame_is_still_judged_on_the_cameras_own_picture():
    """LiveCamera.judged_screen keeps its trigger, the mean alone (dark): a screen read as no known kind on a dark frame
    is asked about even with something drawn on it, and the refusal where that picture cannot be read stays."""
    asked, logged = [], []
    cam = SimpleNamespace(screen=SimpleNamespace(kind="unknown"), frame=frame_of(notice_picture()),
                          run=SimpleNamespace(log=lambda *a, **k: logged.append(a)),
                          osd_seen=lambda: asked.append(1) or "")
    with pytest.raises(safety.Refused, match="could not be read"):
        live.LiveCamera.judged_screen(cam, "down")
    assert asked == [1]
    cam.frame = frame_of(blank(40))                     # a bright frame: the screen read is kept, nothing asked
    assert live.LiveCamera.judged_screen(cam, "down") is cam.screen and asked == [1]


def test_the_reader_is_asked_about_a_notice_on_a_dark_scene_and_never_about_a_blanked_frame():
    from PIL import Image

    def png(a) -> bytes:
        b = io.BytesIO()
        Image.fromarray(a).save(b, "PNG")
        return b.getvalue()
    assert not vlm.black_image(png(notice_picture()))
    assert vlm.black_image(png(blank()))


NOTICE_DARK = [A1 / "kit2_fin_look_zring1" / "shots" / "00028_after-armed.png",
               A1 / "kit2_fin_look_zring1" / "shots" / "00027_right.png",
               A1 / "kit2_pass2" / "shots" / "223037_after-the-add.png"]


@pytest.mark.parametrize("path", NOTICE_DARK, ids=["after-armed", "right", "added"])
def test_the_cameras_notices_on_a_dark_scene_are_not_black(path):
    """The capped lens's notice drive.py took for black (2026-11-19), the frame before it, and "Added.", the smallest
    notice the runs hold (mean 1.0): dark, read as notices, not black."""
    f = load(need(path))
    assert live.dark(f) and not live.black(f) and screen.read(f).kind == "notice"


def test_a_shooting_screen_in_the_dark_is_not_black():
    f = load(need(A1 / "kit2_fin_peek" / "shots" / "00002_peek.png"))
    assert not live.black(f) and screen.read(f).kind == "shooting"


@pytest.mark.parametrize("path", [A1 / "kit2_a1fin_look_stills" / "shots" / "00506_right.png",
                                  A1 / "kit2_a1fin_look_sq" / "shots" / "00795_closing.png"], ids=["zeros", "frame-line"])
def test_the_cameras_black_frames_stay_black(path):
    """A frame saved black (every pixel 0) and a notice's frame line with nothing in it yet: black."""
    assert live.black(load(need(path)))
