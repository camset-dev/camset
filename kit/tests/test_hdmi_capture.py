"""HDMI eyes on a dongle that delivers another size than the one the crop was calibrated on (2026-11-18: after a
camera reset HDMI Resolution went back to Auto and the Cam Link 4K offered only 3840x2160 at 29.97 fps). "hdmi" keeps
size, fps and crop as the calibration's; an optional "capture" names the mode asked of the dongle, and the crop is
scaled onto it before the one crop-and-scale to 640x480. No dongle, no ffmpeg run: commands, settings and pictures
made here.
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import frames, paths, screen  # noqa: E402
from camkit.frames import canonical, changed_fraction, feed_error, hdmi_command, hdmi_settings, scaled_crop  # noqa: E402
from camkit.runs import Run  # noqa: E402

CAL = {"device": "Cam Link 4K", "size": [1920, 1080], "fps": 59.94, "crop": [150, 0, 1620, 1080]}
CAPTURE_4K = {"size": [3840, 2160], "fps": 29.97}
# what ffmpeg's avfoundation input said when asked for 1080p at 59.94 by a dongle offering 2160p alone (2026-11-18)
REFUSED = ["[avfoundation @ 0x7f8] Selected video size (1920x1080) is not supported by the device.",
           "[avfoundation @ 0x7f8] Supported modes:",
           "[avfoundation @ 0x7f8]   3840x2160@[29.970000 29.970000]fps",
           "Error opening input file Cam Link 4K:none."]


def test_the_crop_is_scaled_from_the_calibrations_size_to_the_capture():
    """The calibration's crop (x, y, width, height on its frames) scaled by capture/size: 1080p to 2160p doubles it;
    the same size leaves it; a capture of another shape (4:3 against 16:9) is refused in plain words."""
    assert scaled_crop((150, 0, 1620, 1080), (1920, 1080), (3840, 2160)) == (300, 0, 3240, 2160)
    assert scaled_crop((150, 0, 1620, 1080), (1920, 1080), (1920, 1080)) == (150, 0, 1620, 1080)
    assert scaled_crop((150, 0, 1620, 1080), (1920, 1080), (1280, 720)) == (100, 0, 1080, 720)
    with pytest.raises(ValueError, match="not the shape of"):
        scaled_crop((150, 0, 1620, 1080), (1920, 1080), (1440, 1080))


def test_the_settings_take_capture_when_given_and_the_calibration_otherwise():
    """hdmi_settings: without "capture" the dongle is asked for the calibration's size and fps (as before); with it,
    for its size and fps (fps defaulting to the calibration's), the crop staying the calibration's; a "capture" with
    no proper size is refused in plain words."""
    plain = hdmi_settings(CAL)
    assert plain == {"device": "Cam Link 4K", "size": (1920, 1080), "fps": 59.94, "crop": (150, 0, 1620, 1080),
                     "capture": None}
    got = hdmi_settings({**CAL, "capture": CAPTURE_4K})
    assert got["capture"] == ((3840, 2160), 29.97) and got["crop"] == (150, 0, 1620, 1080) and got["size"] == (1920, 1080)
    assert hdmi_settings({**CAL, "capture": {"size": [3840, 2160]}})["capture"] == ((3840, 2160), 59.94)
    for bad in ({"fps": 29.97}, {"size": [3840]}, {"size": ["3840", 2160]}, {"size": [3840, 2160], "fps": 0}):
        with pytest.raises(ValueError, match="capture"):
            hdmi_settings({**CAL, "capture": bad})


def test_the_ffmpeg_command_asks_the_capture_mode_and_crops_by_the_scaled_crop(monkeypatch):
    """hdmi_command: the dongle asked for the capture's size and fps (-video_size, -framerate), the crop filter at the
    crop scaled onto it, one scale to 640x480; without capture, as before (the calibration's size, fps and crop)."""
    monkeypatch.setattr(frames.sys, "platform", "darwin")
    cmd, out = hdmi_command("Cam Link 4K", (1920, 1080), 59.94, (150, 0, 1620, 1080))
    assert out == (640, 480)
    assert cmd[cmd.index("-video_size") + 1] == "1920x1080" and cmd[cmd.index("-framerate") + 1] == "59.94"
    assert cmd[cmd.index("-vf") + 1] == "crop=1620:1080:150:0,scale=640:480:flags=lanczos"
    cmd, out = hdmi_command("Cam Link 4K", (1920, 1080), 59.94, (150, 0, 1620, 1080), capture=((3840, 2160), 29.97))
    assert out == (640, 480)
    assert cmd[cmd.index("-video_size") + 1] == "3840x2160" and cmd[cmd.index("-framerate") + 1] == "29.97"
    assert cmd[cmd.index("-vf") + 1] == "crop=3240:2160:300:0,scale=640:480:flags=lanczos"
    assert cmd.count("-vf") == 1, "one crop-and-scale, no 1080p frame in between"
    cmd, out = hdmi_command("Cam Link 4K", (1920, 1080), 59.94, None, capture=((3840, 2160), 29.97))
    assert out == (3840, 2160) and "-vf" not in cmd


def test_a_refused_mode_is_said_in_plain_words_with_the_modes_offered():
    """feed_error on ffmpeg's own lines for a refused mode: what was asked, the modes the dongle offers as ffmpeg
    listed them, and what to do ("capture" in private/config.json, or HDMI Resolution set back); no ffmpeg line in it.
    Other lines give a plain sentence that points to the run's log."""
    said = feed_error(REFUSED, (1920, 1080), 59.94)
    assert "does not offer 1920x1080 at 59.94 fps" in said and "3840x2160 at 29.97 fps" in said
    assert '"capture"' in said and "private/config.json" in said and "HDMI Resolution" in said
    assert "avfoundation" not in said and "Supported modes" not in said
    other = feed_error(["Input/output error"], (1920, 1080), 59.94)
    assert "sent no frames" in other and "log" in other and "Input/output" not in other


def test_a_dongle_that_sends_nothing_raises_the_plain_words_and_logs_ffmpegs_own(tmp_path, monkeypatch):
    """HdmiSource.grab on a feed that never started (ffmpeg refused the mode): the error is feed_error's, and ffmpeg's
    lines go to the run's log alone."""
    import json
    src = frames.HdmiSource.__new__(frames.HdmiSource)
    src.run, src.capture_size, src.fps = Run("hdmi", root=tmp_path), (1920, 1080), 59.94
    src.errors = list(REFUSED)
    src.latest = lambda: None
    clock = iter(range(0, 100))
    monkeypatch.setattr(frames.time, "monotonic", lambda: float(next(clock)))
    monkeypatch.setattr(frames.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError) as got:
        src.grab()
    assert "does not offer 1920x1080 at 59.94 fps" in str(got.value) and "avfoundation" not in str(got.value)
    logged = [json.loads(x) for x in (src.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["ffmpeg"] for e in logged if e["kind"] == "hdmi_feed_error"] == [REFUSED]


def menu_picture() -> np.ndarray:
    """A 1080p picture shaped like a menu page inside the calibrated 3:2 area: rows of light text-like strokes, one
    row lit orange, a tab column, the black margins outside the crop."""
    a = np.zeros((1080, 1920, 3), np.uint8)
    x0, w = 150, 1620
    a[:, x0:x0 + w] = 12
    for i in range(7):
        y = 160 + i * 120
        if i == 2:
            a[y - 10:y + 90, x0 + 190:x0 + w - 40] = (200, 70, 10)
        for k in range(10):
            a[y + 20:y + 70, x0 + 240 + k * 110:x0 + 300 + k * 110] = 230
    a[100:1000, x0 + 30:x0 + 150] = 60
    return a


def both(img1080) -> tuple:
    """(the 640x480 screen of a 1080p picture through the calibration's crop, the same picture upscaled to 2160p
    through the crop scaled onto it: the capture path's one crop-and-scale)."""
    img2160 = np.asarray(Image.fromarray(img1080).resize((3840, 2160), Image.LANCZOS))
    a = canonical(img1080, (150, 0, 1620, 1080))
    b = canonical(img2160, scaled_crop((150, 0, 1620, 1080), (1920, 1080), (3840, 2160)))
    return a, b


def test_a_2160p_picture_reads_as_the_same_screen_as_its_1080p_one():
    """The same picture at 1080p and at 2160p (both) gives the same 640x480 screen within the readers' tolerance."""
    a, b = both(menu_picture())
    assert a.shape == b.shape == (480, 640, 3) and changed_fraction(a, b) <= 0.01


def test_the_stored_calibration_frame_upscaled_reads_as_the_same_menu():
    """The stored 1080p calibration frame (kit2_hdmi, test_hdmi_calibration's) and the same picture upscaled to 2160p
    read through the two paths as the same screen kind, cursor and row (Setup > External Output, row 2 lit)."""
    stored = paths.a1ii_root() / "kit2_hdmi" / "calibration_1080p.png"
    if not stored.exists():
        pytest.skip(f"{stored} not present")
    a, b = both(np.asarray(Image.open(stored).convert("RGB")))
    sa, sb = (screen.read(frames.Frame(x, 0)) for x in (a, b))
    assert (sa.kind, sa.focus, sa.row) == (sb.kind, sb.focus, sb.row) == ("menu", "rows", 2)
    assert changed_fraction(a, b) <= 0.01
