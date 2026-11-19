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


# ---------------------------------------------------------------- 2. the --path's own row inside a submenu

BRACKET = ["Bracket Settings", "Bracket Type"]
BRACKET_OTHERS = ("Selftimer during Bracket", "Bracket order", "Focus Bracket Settings")
BRACKET_LIT = "Bracket Type Cont. Bracket"
VARSH = ["Anti-flicker Set.", "Var. Shutter Set."]
VARSH_OTHERS = ("Anti-flicker Shoot.", "Var. Shutter", "& Var. Shutter")
VARSH_LIT = "fVar. Shutter Set."


def bracket_bar(**kw):
    """Bracket Type's bar as drive.submenu_bar reads it (kit2_fin_look_brtype1 00018: the value at x 495-637), `kw`
    changing any part."""
    parts = dict(lit=BRACKET_LIT, label="Bracket Type", values=(("Cont. Bracket", 495, 637),), label_end=203,
                 bar_end=640, readings=("Bracket Type", "Bracket Type"), others=BRACKET_OTHERS)
    return drive.SubmenuBar(**{**parts, **kw})


def varsh_bar(**kw):
    """Var. Shutter Set.'s bar (kit2_fin_look_varsh 00020: its icon read "f", no value), `kw` changing any part."""
    parts = dict(lit=VARSH_LIT, label=VARSH_LIT, values=(), label_end=265, bar_end=640,
                 readings=("Var. Shutter Set.", VARSH_LIT, "Var. Shutter Set."), others=VARSH_OTHERS)
    return drive.SubmenuBar(**{**parts, **kw})


def judged(lit, path, b, depth=None, seen=None, known=()):
    """drive.lit_refused as kit/drive.py calls it on a submenu page: `known` beside the page's labels read live (every
    reading of every row, the lit row's among them) and the bar `b` read with them (None: no bar read)."""
    from camkit import first_open
    labels = set(known) | ({*b.readings, *b.others, b} if b is not None else set())
    return drive.lit_refused(lit, path[:-1] if depth is None else depth, path, seen or first_open.Seen(), labels,
                             None, {}, None)


def test_a_submenu_rows_bar_with_its_value_right_aligned_is_the_named_row():
    """Bracket Settings > Bracket Type (kit2_fin_look_brtype1): its value beside it, which no source knows yet."""
    assert judged(BRACKET_LIT, BRACKET, bracket_bar()) == ("", tuple(BRACKET))
    why, row = judged(BRACKET_LIT, BRACKET, None, known={"Bracket Type"})     # no reading of the bar: as before
    assert row is None and "runs on past the row 'bracket type' with words that are no value of it" in why


def test_a_submenu_rows_bar_with_its_icon_read_as_a_letter_is_the_named_row():
    """Anti-flicker Set. > Var. Shutter Set. (kit2_fin_look_varsh), seen opened: its icon read "f", glued on."""
    from camkit import first_open
    seen = first_open.Seen({("anti-flicker set.",), ("anti-flicker set.", "var. shutter set.")})
    assert judged(VARSH_LIT, VARSH, varsh_bar(), seen=seen) == ("", tuple(VARSH))
    why, row = judged(VARSH_LIT, VARSH, None, seen=seen, known={VARSH_LIT, "Var. Shutter Set."})
    assert row is None and "a row this camera has not been seen to open" in why


@pytest.mark.parametrize("case", [
    "label column longer", "value inside the label column", "value not at the bar's end", "another row starts so",
    "another row is the label", "the reader reads otherwise", "no reading of the lit row", "another frame's bar",
    "another page", "a page that cannot be placed", "the path names a shorter row", "a top-level row"])
def test_a_submenu_bar_that_could_be_another_row_stays_refused(case):
    """Every neighbour of Bracket Type's bar is refused, as before."""
    path, b, depth = BRACKET, bracket_bar(), None
    if case == "label column longer":
        b = bracket_bar(label="Bracket Type Cont.", values=(("Bracket", 520, 637),), label_end=330)
    elif case == "value inside the label column":
        b = bracket_bar(values=(("Cont. Bracket", 215, 360),))
    elif case == "value not at the bar's end":
        b = bracket_bar(values=(("Cont. Bracket", 480, 600),))
    elif case == "another row starts so":
        b = bracket_bar(others=(*BRACKET_OTHERS, "Bracket Type Set."))
    elif case == "another row is the label":
        b = bracket_bar(others=(*BRACKET_OTHERS, "Bracket Type"))
    elif case == "the reader reads otherwise":
        b = bracket_bar(readings=("Bracket Type", "Bracket Typo"))
    elif case == "no reading of the lit row":
        b = bracket_bar(readings=())
    elif case == "another frame's bar":
        b = bracket_bar(lit="Bracket Type Single Bracket")
    elif case == "another page":
        depth = ["Drive Mode"]
    elif case == "a page that cannot be placed":
        depth = None
        why, row = drive.lit_refused(BRACKET_LIT, None, path, __import__("camkit.first_open").first_open.Seen(),
                                     {b, *b.readings, *b.others}, None, {}, None)
        assert why and row is None, case
        return
    elif case == "the path names a shorter row":
        path = ["Bracket Settings", "Bracket"]
    elif case == "a top-level row":
        path, depth = ["Bracket Type"], []
    why, row = judged(BRACKET_LIT, path, b, depth=depth)
    assert why and row is None, case


@pytest.mark.parametrize("case", ["the path names the shorter row", "two letters before the label",
                                  "the reader reads the icon too", "another row reads the label"])
def test_an_icon_bar_that_could_be_another_row_stays_refused(case):
    """Every neighbour of Var. Shutter Set.'s bar is refused, as before: Var. Shutter, a row of the same page whose label
    the lit one starts with, is never the bar "fVar. Shutter Set."."""
    from camkit import first_open
    seen = first_open.Seen({("anti-flicker set.",), ("anti-flicker set.", "var. shutter set."),
                            ("anti-flicker set.", "var. shutter")})
    path, lit, b = VARSH, VARSH_LIT, varsh_bar()
    if case == "the path names the shorter row":
        path, b = ["Anti-flicker Set.", "Var. Shutter"], varsh_bar(others=("Anti-flicker Shoot.", "Var. Shutter"))
    elif case == "two letters before the label":
        lit = "AF Var. Shutter Set."
        b = varsh_bar(lit=lit, label=lit, readings=("Var. Shutter Set.", lit))
    elif case == "the reader reads the icon too":
        b = varsh_bar(readings=(VARSH_LIT, VARSH_LIT))
    elif case == "another row reads the label":
        b = varsh_bar(others=(*VARSH_OTHERS, "Var. Shutter Set."))
    why, row = judged(lit, path, b, seen=seen)
    assert why and row is None, case


def test_the_bar_is_read_by_columns_from_ocrs_lines(monkeypatch):
    """drive.submenu_bar: the label column's text, the value column's lines with their x, the lit row's readings and the
    other rows', read on one frame, and shown_labels adds it to the page's labels; none off a submenu, or where the
    orange bar is not on the lit row."""
    from camkit.ocr import Line
    lines = [Line("Shooting > Drive Mode > Bracket Settings", 1, 0, 1, 454, 35), Line("Bracket Type", 1, 55, 57, 148, 37),
             Line("Cont. Bracket", 1, 495, 59, 142, 30), Line("Selftimer during Bracket", 1, 57, 109, 268, 35)]
    rows = [{"label": "Bracket Type", "readings": ["Bracket Type", "Bracket Type"]},
            {"label": "Selftimer during Bracket", "readings": ["Selftimer during Bracket"]}]
    shown = SimpleNamespace(kind="submenu", row=0, rows=[(45, 98), (98, 150)])
    cam = SimpleNamespace(frame=frame_of(blank()), read=lambda: shown)
    monkeypatch.setattr(drive, "lit_found", lambda image: ((56, 46, 640, 99), True))
    monkeypatch.setattr(drive.ocr, "read", lambda paths: {p: lines for p in paths})
    monkeypatch.setattr(drive, "highlighted", lambda image, p: BRACKET_LIT)
    monkeypatch.setattr(drive, "submenu_labels", lambda c: ("page", rows))
    b = drive.submenu_bar(cam, rows)
    assert b == drive.SubmenuBar(BRACKET_LIT, "Bracket Type", (("Cont. Bracket", 495, 637),), 203, 640,
                                 ("Bracket Type", "Bracket Type", "Bracket Type"), ("Selftimer during Bracket",) * 2)
    assert drive.shown_labels(cam, [], {})[-1] == b and drive.submenu_tied(BRACKET_LIT, "Bracket Type", b)
    shown.row = 1                                           # the orange bar is not on the lit row's place
    assert drive.submenu_bar(cam, rows) is None
    shown.kind, shown.row = "menu", 0
    assert drive.submenu_bar(cam, rows) is None


# the reader's labels of the two pages as it read them (its answers kept for other frames of those pages, 2026-11-19):
# the icon left out, as it is told to
READER = {"varsh": ["Anti-flicker Shoot.", "Var. Shutter", "Var. Shutter Set."],
          "brtype": ["Bracket Type", "Selftimer during Bracket", "Bracket order", "Focus Bracket Settings"]}
REFUSED_BARS = [("varsh", A1 / "kit2_fin_look_varsh" / "shots" / "00020_down.png", VARSH,
                 {("anti-flicker set.",), ("anti-flicker set.", "var. shutter set.")}),
                ("brtype", A1 / "kit2_fin_look_brtype1" / "shots" / "00018_right.png", BRACKET, set())]


@pytest.mark.parametrize("name, path, row, opened", REFUSED_BARS, ids=[r[0] for r in REFUSED_BARS])
def test_the_two_bars_refused_this_morning_are_their_rows(name, path, row, opened):
    """Opt-in (skipped without the runs or this computer's OCR): each frame drive.py refused its Right on, its page read
    as drive.py reads it (OCR's labels and the reader's), is the --path's own row; without the bar's reading the
    refusal of the morning stands."""
    from camkit import first_open, ocr
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = load(need(path))
    s = screen.read(f)
    texts = live.submenu_texts(ocr.read([f.path])[f.path], s)
    rows = [{"label": r, "readings": [t, r]} for t, r in zip(texts, READER[name], strict=True)]
    b = drive.submenu_bar(SimpleNamespace(frame=f, read=lambda: s), rows)
    lit = drive.highlighted(f.image, f.path)
    labels = {t for r in rows for t in (r["label"], *r["readings"])}
    seen = first_open.Seen(opened)
    assert b is not None and drive.lit_refused(lit, row[:-1], row, seen, labels | {b}, None, {}, None) == ("", tuple(row))
    assert drive.lit_refused(lit, row[:-1], row, seen, labels, None, {}, None)[1] is None
