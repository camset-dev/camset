"""Faults met on the a1 II while finishing its mapping (2026-11-19), each with the refusals around it that stay.

1. A notice on a dark scene taken for a black frame (camkit.live.black): a first open ended with RESTORE_BY_HAND.

Run: .venv/bin/python -m pytest kit/tests/test_finish_kit.py -q
The camera's frames live under runs/ (not versioned); the tests that read them skip when absent, the ones on drawn
pictures and made-up text run everywhere.
"""
import io
import re
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


# ---------------------------------------------------------------- 3. two boxed options beside a drawing

WHITE, FILL, BORDER, GREY_EDGE = 221, (170, 51, 0), (221, 85, 0), 85


def glyph(name: str) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(Path(screen.__file__).parent / "glyphs" / f"{name}.png").convert("L"))


def strokes(a, y0, y1, x0, x1):
    """Letter-like white strokes (4 px wide, 6 px apart) across x0..x1."""
    for x in range(x0, x1, 10):
        a[y0:y1, x:x + 4] = WHITE


def media_card(lit=0, x0=376, x1=615, top=215, n=2, footer="menu_back", prose_low=False, extra=False,
               drawing=True) -> np.ndarray:
    """"Select media card." as the a1 II draws it (kit2_fin_look_media 00016): a title at the top left over its rule, a
    line of words over the boxes, the camera drawn at the left (its lines and a small orange slot mark), `n` boxes x
    x0..x1, 55 px tall, 70 px pitch from y `top`, the `lit` one filled orange, the others outlined, text in each; the
    footer's rule and its `footer` key (glyphs/<footer>.png; None, none). prose_low: the words reach down beside the
    first box; extra: a mark at the right below the boxes."""
    a = np.zeros((480, 640, 3), np.uint8)
    strokes(a, 14, 40, 21, 330)
    a[53, 5:635] = 102
    a[426, 5:635] = 119
    strokes(a, 90, 120, 200, 440)                                 # "Select media card."
    if prose_low:
        strokes(a, top + 4, top + 30, 80, 560)
    if drawing:
        a[190:340, 230:232] = a[190:340, 328:330] = a[190:192, 230:330] = a[338:340, 230:330] = WHITE
        a[240:280, 254:257] = BORDER                              # the lit slot's mark
        strokes(a, 210, 240, 50, 170)                             # the cards' logos
    for i in range(n):
        t = top + 70 * i
        b = t + 54
        if i == lit:
            a[t:b + 1, x0:x1 + 1] = BORDER
            a[t + 2:b - 1, x0 + 2:x1 - 1] = FILL
        else:
            a[t:t + 2, x0:x1 + 1] = a[b - 1:b + 1, x0:x1 + 1] = GREY_EDGE
            a[t:b + 1, x0:x0 + 2] = a[t:b + 1, x1 - 1:x1 + 1] = GREY_EDGE
        strokes(a, t + 14, t + 40, x0 + 80, x0 + 160)
    if extra:
        a[380:400, 500:540] = WHITE
    if footer:
        g = glyph(footer)
        x = 558 if footer == "menu_back" else 470
        a[437:437 + g.shape[0], x:x + g.shape[1]] = g[..., None]
    return a


def kind_of(a) -> screen.Screen:
    from camkit.frames import Frame
    return screen.read(Frame(image=a, t=0.0))


@pytest.mark.parametrize("lit", [0, 1])
def test_two_boxes_beside_a_drawing_read_as_buttons_with_the_lit_one(lit):
    s = kind_of(media_card(lit))
    assert s.kind == "buttons" and (s.count, s.row) == (2, lit)
    assert s.rows == [(215, 269), (285, 339)] and s.bar == s.rows[lit] and s.boxes == [(376, 615)] * 2


@pytest.mark.parametrize("case, a", [
    ("the help button in the footer", lambda: media_card(footer="help_only")),
    ("the help button beside the MENU key", lambda: media_card(footer="menu_back") | media_card(footer="help_only")),
    ("no footer key", lambda: media_card(footer=None)),
    ("words beside the first box", lambda: media_card(prose_low=True)),
    ("a mark at the right below the boxes", lambda: media_card(extra=True)),
    ("boxes elsewhere", lambda: media_card(x0=330, x1=569)),
    ("one box", lambda: media_card(n=1)),
    ("none lit", lambda: media_card(lit=-1)),
], ids=lambda v: v if isinstance(v, str) else "")
def test_what_is_not_two_boxes_beside_a_drawing_stays_unknown(case, a):
    """The side layout's neighbours read as they did before it: unknown."""
    f = screen.features(a())
    assert f["option_boxes"] is None and screen.classify(f) == "unknown", case


def test_centred_boxes_still_need_a_screen_black_but_for_them():
    """The centred layout (Image Index) keeps its rule: a drawing beside centred boxes is no "buttons" screen."""
    f = screen.features(media_card(x0=96, x1=543))
    assert f["option_boxes"] is None and screen.classify(f) == "unknown"


def test_enter_stays_refused_on_two_boxes_beside_a_drawing():
    """A "buttons" screen takes no Enter by its kind, whatever its words (the playbook's rule 8)."""
    assert "buttons" not in safety.ENTER_KINDS and "buttons" not in safety.SHOWN_KINDS
    why = safety.enter_refused("buttons", "Display Media Info. Select media card. Slot 1 Slot 2", "Slot 1")
    assert "not one whose Enter chooses or opens" in why, why


MEDIA_CARD = [A1 / "kit2_fin_look_media" / "shots" / "00016_right.png",
              A1 / "kit2_fin_look_multi" / "shots" / "00014_right.png",
              A1 / "kit2_a1fin_look_playback4" / "shots" / "00205_right.png"]


@pytest.mark.parametrize("path", MEDIA_CARD, ids=["display-media-info", "multi-media", "multi-media-2"])
def test_the_cameras_select_media_card_screens_read_as_buttons(path):
    """Display Media Info. and Play Set of Multi. Media: two boxes x 376-615, Slot 1 lit."""
    s = screen.read(load(need(path)))
    assert s.kind == "buttons" and (s.count, s.row) == (2, 0) and s.boxes == [(376, 615)] * 2
    assert s.rows[1][0] - s.rows[0][0] == 70


# ---------------------------------------------------------------- 3b. a slider drawn over a picture

CY, PITCH, FIRST = 347, 22, 155          # the scale's line, its pitch, the place of its low end (Aspect Marker Level's)
FRAME = (108, 532)                       # the aspect marker's frame: the bands outside it are what the level dims
BANDS = [1.0, 0.75, 0.5, 0.25, 0.0]      # the bands' share of the picture's brightness: untouched (level 0) to black


def outlined(a, mask, ink):
    """`mask` drawn in `ink` (a grey, or a grey picture of the frame's size) inside a 1-px black outline, as the camera
    draws its − and +, its numbers and its footer keys over a picture (kit2_pass2 261812): their light pixels are the
    same over any picture."""
    import cv2
    ring = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~mask
    a[ring] = 0
    a[mask] = ink if np.isscalar(ink) else ink[mask][:, None]


def picture_slider(at=12, ticks=True, uneven=False, marks=1, mark_off=0, value_x=320, ok=True, blob=False,
                   footer_rule=False, seed=3, band=0.15, hidden=(), trees=True) -> np.ndarray:
    """Aspect Marker Level over a picture as the a1 II draws it with HDMI Info. Display Off (kit2_fin_crawl_amdisp_off
    00028, kit2_pass2 261797-261812): a bright, textured "sky" over a darker "field"; at each side dark "trees" with a
    few lighter leaves round the − and + (trees=False: none), and a grey "path" low down (the photograph's right band
    holds one, which lifts the footer's measured rule there); outside the aspect marker's frame (FRAME, its 2-px lines
    drawn) the bands at `band` of the picture's brightness, the level's doing (1: untouched, 0: black); the title; the
    value in orange between white ◂ ▸ (each outlined in black, as the camera draws them over a picture); the scale on
    the line of the bare − and + (0 to 15, ticks 2 x 12 at a 22 px pitch, the end numbers and every fifth drawn as
    digits, the places in `hidden` drawn as nothing); an orange 13 x 13 marker over the value `at`; the footer's Help
    button and OK key. The −, the +, the numbers and the footer keys are outlined in black, as the camera draws them.
    The other arguments make its neighbours."""
    rng = np.random.default_rng(seed)
    a = np.zeros((480, 640, 3), np.uint8)
    light = rng.integers(0, 60, (300, 640, 1))
    a[:300] = np.concatenate([120 + light, 160 + light // 2, 195 + light], axis=2).astype(np.uint8)          # sky
    dark = rng.integers(0, 50, (180, 640, 1))
    a[300:] = np.concatenate([30 + dark, 80 + dark, 20 + dark // 2], axis=2).astype(np.uint8)                # field
    if trees:
        leaf = rng.integers(0, 15, (112, 640, 1))
        wood = np.concatenate([10 + leaf, 25 + leaf, 10 + leaf // 2], axis=2).astype(np.uint8)
        wood[rng.random((112, 640)) < 0.02] = (60, 85, 50)                                  # a lighter leaf
        a[250:362, :200], a[250:362, 440:] = wood[:, :200], wood[:, 440:]
    grey = rng.integers(95, 140, (21, 640, 1)).astype(np.uint8)
    a[415:436, :200], a[415:436, 440:] = grey[:, :200], grey[:, 440:]                                         # path
    for x0, x1 in ((0, FRAME[0]), (FRAME[1], 640)):
        a[:, x0:x1] = (a[:, x0:x1] * band).astype(np.uint8)                                 # the level's bands
    for x in FRAME:
        a[:, x - 1:x + 1] = a[:, x - 1:x + 1] // 2 + 60                                     # the frame's lines
    for x in range(20, 300, 12):                                                            # the title
        a[12:40, x:x + 4] = 221
    digits = 2 if at >= 10 else 1
    for i in range(digits):                                                                 # the value, orange
        x = value_x - 10 * digits + 20 * i
        a[236:266, x:x + 12] = (230, 100, 0)
    for x0, step in ((258, 1), (382, -1)):                                                  # ◂ ▸, outlined
        for j in range(10):
            ys = slice(252 - j // 2 - 2, 252 + j // 2 + 3)
            a[ys, x0 + step * j - 1:x0 + step * j + 2] = 0
        for j in range(10):
            a[252 - j // 2:252 + j // 2 + 1, x0 + step * j] = 221
    signs = np.zeros((480, 640), bool)
    signs[CY - 2:CY + 2, 50:77] = True                                                      # − alone
    signs[CY - 2:CY + 2, 563:590] = True                                                    # + alone, mirrored
    signs[CY - 13:CY + 14, 575:579] = True
    outlined(a, signs, 221)
    digits = np.zeros((480, 640), bool)
    for v in range(16):
        x = FIRST + PITCH * v + (5 if uneven and v == 7 else 0)
        if v in hidden:
            continue
        if v % 5 == 0:                                                                      # a number: a digit's block
            digits[CY - 13:CY + 13, x - 6:x - 3] = digits[CY - 13:CY + 13, x + 3:x + 6] = True
        elif ticks:
            a[CY - 7:CY + 7, x - 2:x + 2] = 0
            a[CY - 6:CY + 6, x - 1:x + 1] = 221
    outlined(a, digits, 221)
    for k in range(marks):                                                                  # the marker
        x = FIRST + PITCH * (at + 2 * k) + mark_off
        a[CY - 37:CY - 24, x - 6:x + 7] = (230, 100, 0)
    if blob:
        a[CY - 70:CY - 55, 150:175] = (230, 100, 0)                                         # the picture's orange
    if footer_rule:
        a[426, 5:635] = 119
    for name, x in (("help_only", 281), *((("ok_key", 561),) if ok else ())):
        g = glyph(name)
        ink = np.zeros((480, 640), np.uint8)
        ink[437:437 + g.shape[0], x:x + g.shape[1]] = g
        outlined(a, ink > 60, ink)
    return a


@pytest.mark.parametrize("band", BANDS)
@pytest.mark.parametrize("at", [0, 1, 7, 12, 15])
def test_a_slider_over_a_picture_reads_as_a_slider_with_its_marker_at_every_level(at, band):
    """The bands outside the aspect marker from untouched (the lowest levels) to black (the highest), the marker at
    either end too: a slider over a picture, its marker where it stands on the scale."""
    s = kind_of(picture_slider(at, band=band))
    assert s.kind == "slider" and s.features["picture_slider"] and s.marker == FIRST + PITCH * at
    assert s.glyphs == {}, "the ◂ ▸ are not read over a picture: no end said where one may only be hidden"


@pytest.mark.parametrize("band, trees, rules", [
    (1.0, True, "unknown"), (0.5, True, "slider"), (1.0, False, "notice")], ids=["untouched", "half", "evenly-lit"])
def test_what_the_level_changes_decides_nothing(band, trees, rules):
    """What the bands' level moves, and what the rules alone would read the screen as: untouched (kit2_pass2 261808 to
    261812, 3 down to 1), the − and + no longer stand alone, leaves lit round them (_bare_signs' "alone", which the
    reading once rested on), so no slider rule reads it: unknown; half as light, they stand alone but the footer's rule
    measured across the whole width reads over half a line (the bands' grey path), so the slider rule reads it, its
    number in OCR's box; a band lit evenly draws a notice's frame lines (x 30 and 609). Each time the screen reads as
    the slider over a picture, its marker where it stands."""
    a = picture_slider(3, band=band, trees=trees)
    f = screen.features(a)
    assert screen.classify({**f, "picture_slider": None}) == rules
    assert (screen._bare_signs(screen._grey(a)) is None) == (band == 1.0) and f["footer_line"] > 0.45
    s = kind_of(a)
    assert s.kind == "slider" and s.features["picture_slider"]["marker"] == s.marker == FIRST + PITCH * 3


def test_two_places_of_the_marker_are_two_states():
    a, b = kind_of(picture_slider(11)), kind_of(picture_slider(12))
    assert a.kind == b.kind == "slider" and not screen.same_state(a, b)


@pytest.mark.parametrize("band", [1.0, 0.15, 0.0])
@pytest.mark.parametrize("case, kw", [
    ("no ticks", dict(ticks=False)), ("ticks unevenly apart", dict(uneven=True)), ("two markers", dict(marks=2)),
    ("the marker off the ticks' grid", dict(mark_off=9)), ("the value off centre", dict(value_x=420)),
    ("no OK key", dict(ok=False)), ("the picture's orange beside the scale", dict(blob=True)),
    ("no number on the scale", dict(hidden=(0, 5, 10, 15))), ("one number on the scale", dict(hidden=(0, 5, 10))),
], ids=lambda v: v if isinstance(v, str) else "")
def test_what_a_picture_could_fake_leaves_it_unknown(case, kw, band):
    """Each part a photograph could fake or hide is required, whatever the bands' level: without it the screen reads as
    before, unknown."""
    f = screen.features(picture_slider(**kw, band=band))
    assert f["picture_slider"] is None and screen.classify(f) == "unknown", case


def test_a_slider_with_its_footer_rule_is_read_as_before():
    """Where the footer's rule shows, the rules read it as they always have; the picture's reading is not looked for."""
    f = screen.features(picture_slider(footer_rule=True))
    assert f["picture_slider"] is None and screen.classify(f) == screen.classify({**f, "picture_slider": None})


def test_a_footer_rule_drawn_across_the_scale_is_no_picture_slider_with_the_bands_untouched():
    """The footer's rule drawn across the scale, the − and + not alone (the bands untouched), so no slider rule reads
    it: not read as a slider over a picture either, whose footer draws no rule."""
    f = screen.features(picture_slider(footer_rule=True, band=1.0))
    assert f["picture_slider"] is None and screen.classify(f) == "unknown"


def test_the_aspect_marker_level_over_the_sample_photograph_is_a_slider():
    """The frame the crawl called an unknown screen (kit2_fin_crawl_amdisp_off 00028): a slider, its marker over 12 (the
    scale's low end at x 155, 22 px a step), its ◂ ▸ not read."""
    s = screen.read(load(need(A1 / "kit2_fin_crawl_amdisp_off" / "shots" / "00028_right.png")))
    assert s.kind == "slider" and s.marker == 418 and s.glyphs == {}
    assert round((s.marker - 155) / 22) == 12


# ---------------------------------------------------------------- 4. two rows whose opening acts

ACTING = ["Cont. Play for Interval", "Zoom"]
ZOOM_ROWS = ["Zoom Range", "Zoom Ring Rotate", "Custom Key Z. Speed", "Remote Zoom Speed"]


@pytest.mark.parametrize("label", [*ACTING, "Cont. Play for Interval.", "zoom", "S Zoom", "• Zoom", "Cont.Play for Interval"])
def test_the_two_rows_act_as_they_open_and_a_look_lap_leaves_them_to_the_owner(label):
    """The camera's own spelling, read with a stop after it, an icon before it or its words run together."""
    assert safety.acts_on_open(label), label
    assert safety.look_lap_refused(label, False).startswith("a row whose opening acts"), label
    assert safety.look_lap_refused(label, True).startswith("a row whose opening acts"), "seen or not"


@pytest.mark.parametrize("label", [*ZOOM_ROWS, "Clear Image Zoom", "ZoomRange", "Cont. Play for Interval Set",
                                   "Interval Shoot Func."])
def test_the_list_compares_whole_labels(label):
    """"Zoom" is a short word: the rows that hold it, run together or not, are untouched, as they were."""
    assert not safety.acts_on_open(label) and not safety.look_lap_refused(label, False), label
    assert safety.never_open(label) is None, label


def test_the_ledger_classes_them_as_the_lists_other_rows_and_the_zoom_group_stays_open():
    """Cont. Play for Interval is an action of the never-open list, as Create New Folder, Send and FTP Transfer are
    (their openings act too); Zoom is not on it (its name would close the group Shooting > Zoom to the group column,
    and the four rows of that group with it): an ordinary row for the ledger, which a look lap leaves to the owner."""
    from camkit import coverage
    assert coverage.rule_class("Cont. Play for Interval") == coverage.rule_class("Create New Folder") == "action"
    assert coverage.rule_class("Zoom") is None and all(coverage.rule_class(r) is None for r in ZOOM_ROWS)
    assert safety.group_refused("Zoom") is None and safety.group_refused("Viewing") is None


def test_what_each_run_does_at_the_two_rows():
    """A crawl: Cont. Play for Interval never-open (skipped, as every action), and on a look lap left to the owner's own
    run; Zoom opened by a plain crawl as before, left by a look lap. drive.py --network: refused before connecting."""
    from camkit import crawl
    page = {"breadcrumb": "Playback > Viewing"}
    assert crawl.closed_row(page, {"label": "Cont. Play for Interval"})[0].startswith("action:")
    assert crawl.closed_row(page, {"label": "Cont. Play for Interval"}, look=True)[0].startswith("a row whose opening")
    zoom = {"breadcrumb": "Shooting > Zoom"}
    assert not crawl.closed_row(zoom, {"label": "Zoom"})[0]
    assert crawl.closed_row(zoom, {"label": "Zoom"}, look=True)[0].startswith("a row whose opening acts")
    for label in ACTING:
        with pytest.raises(SystemExit, match="a row whose opening acts"):
            drive.look_path_or_exit([label], None)


# ---------------------------------------------------------------- 5. the serial number screen always black

@pytest.mark.parametrize("cls, logged, blank", [
    (safety.LIFT_SERIAL, True, True), (safety.LIFT_SERIAL, False, True),
    (safety.LIFT_CREDENTIALS, True, False), (safety.LIFT_CREDENTIALS, False, True),
    (safety.LIFT_FIXED, True, False), (safety.LIFT_FIXED, False, True),
    (safety.LIFT_ACTION, True, False), (safety.LIFT_CARDS, False, False), (None, True, False)])
def test_values_logged_unblank_a_credentials_screen_never_the_serial_number(cls, logged, blank):
    assert safety.blanked(cls, logged) is blank


def test_the_owner_route_saves_the_serial_number_screen_black_whatever_its_decision_says(tmp_path, monkeypatch):
    """A decision naming Display Serial Number with "values": "logged": its frames saved black from its opening all the
    same, and the run's words about the row say its values are withheld."""
    from PIL import Image
    from test_owner_decisions import SERIAL, camera, info_of
    info = info_of("Display Serial Number", {"rows": ["Display Serial Number"], "values": "logged"})
    assert info["class"] == safety.LIFT_SERIAL and info["logged"]
    assert "values withheld" in safety.owner_said(info) and "values logged" not in safety.owner_said(info)
    states = {"page": ("submenu", "Setup > Setup Option Display Serial Number", "Display Serial Number"),
              "serial": ("notice", f"Serial Number {SERIAL}", "")}
    cam = camera(tmp_path, monkeypatch, info, states, {("page", "right"): "serial"}, label="Display Serial Number")
    cam.press("right")
    assert cam.blank and cam.hdmi.withheld and np.asarray(Image.open(cam.frame.path)).max() == 0
    assert cam.network_open["blank"] is True


# ---------------------------------------------------------------- 6. what a plain crawl keeps of a notice

LABELS = {"HDMI Info. Display", "Zoom Ring Rotate", "Function Ring(Lens)", "Shoe Audio Set.", "Aspect Marker Level"}
# the four notices of 2026-11-19 as the crawls logged them (notice_not_passed), and the blocker each names
NOTICES = [("• Lens Invalid with this lens.", {"equipment": "a power-zoom lens"}),
           ("• Lens Please attach a supported lens since the current lens is not supported.",
            {"equipment": "a lens with a function ring"}),
           ("Invalid since no audio device is attached to the multi interface shoe. Correctly attach the audio device.",
            {"equipment": "a shoe audio accessory"}),
           ("This operation or setting not available as follows HDMI Info. Display On", {"row": "HDMI Info. Display"})]


@pytest.mark.parametrize("text, blocker", NOTICES, ids=["zoom-ring", "function-ring", "shoe", "hdmi-info"])
def test_a_plain_crawl_keeps_what_the_notice_names_and_nothing_more(text, blocker):
    """The kept text gives the ledger the blocker drive.py's look gives the whole text, and holds nothing else: never
    the blocking row's value ("On"), never the notice's other words."""
    from camkit import coverage, crawl
    kept = crawl.notice_named(text, LABELS, {})
    assert coverage.blocker_of(kept, LABELS) == coverage.blocker_of(text, LABELS) == blocker, kept
    assert len(kept) < len(text) and not kept.endswith(" On"), kept


@pytest.mark.parametrize("text", ["Shooting is in progress. Please wait.",
                                  "This operation or setting not available as follows Some Row Nobody Knows On",
                                  "Format the memory card? OK Cancel",
                                  "Connected to Remote Shooting. Cannot be executed.", ""])
def test_a_notice_that_names_nothing_the_kit_knows_keeps_nothing_named(text):
    """Nothing the kit knows, a row it does not know (the fixed sentence alone, as a look lap keeps it), a question, a
    connection's words (identity: as notice_kept), no text: no blocker kept."""
    from camkit import coverage, crawl
    kept = crawl.notice_named(text, LABELS, {})
    assert not coverage.blocker_of(kept, LABELS) and "Nobody" not in kept and "Shooting" not in kept, kept


def test_a_known_shape_is_kept_as_the_look_lap_keeps_it():
    from camkit import crawl
    assert crawl.notice_named("This function is currently disabled. OK", LABELS, {}) == safety.notice_kept(
        "This function is currently disabled. OK", LABELS, {}) == "This function is currently disabled."


def test_a_plain_crawls_row_and_look_carry_the_blocker_and_a_look_laps_rows_as_before(tmp_path, monkeypatch):
    """camkit.crawl.visit_row on a row whose Right opens the capped lens's notice: a plain crawl's row keeps what it
    names, its summary (kit/crawl_run.py) writes it and the look made of it (camkit.coverage.crawl_looks) carries the
    blocker; a look lap keeps nothing more of an ordinary row's notice than before."""
    import crawl_run
    from camkit import coverage, crawl
    from test_info_notice import NoticeCamera
    notices = ((lambda cam: NOTICES[0][0]), LABELS, {})

    def visit(**kw):
        cam = NoticeCamera(tmp_path)
        return crawl.visit_row(cam, cam.read(), {"page": "Shooting > Zoom"}, 0, {"label": "Zoom Ring Rotate"}, **kw)
    r = visit(notices=notices)
    assert r.outcome == "notice" and r.notice == "Invalid with this lens"
    row = crawl_run.summary(r)
    assert row["notice"] == r.notice
    look = coverage.crawl_looks(row, ["Shooting", "Zoom"], "Stills", "kit2_x", "TEST-CAM_fw9.99")[0]
    assert look["result"] == "greyed" and look["blocker"] == {"equipment": "a power-zoom lens"}
    lap = visit(notices=notices, look=True)
    assert lap.kind == "notice" and lap.notice == ""          # its notice met (the lap's way back aside), nothing kept
    assert visit().notice == "", "no reader of the screen given: nothing kept, as before"


# ================================================================ the second round of 2026-11-19
# ---------------------------------------------------------------- 7. the scale prover reads a slider over a picture

def scale_run_module():
    sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "provers"))
    import scale_run
    return scale_run


def scale_ocr(numbers=(5, 10, 15), drawn=None, value_lines=None):
    """masked_lines as OCR reads a slider over a picture once the picture is left out: on the scale's line, each of
    `numbers` alone on its place (Apple's OCR drops the lone 0 at the low end, 2026-11-19), or `drawn` (a list of (text,
    x0, x1) lines); at the number drawn in orange, `value_lines(box)` (none: nothing read)."""
    from camkit.ocr import Line

    def lines(mask, box):
        if box[1] <= CY <= box[3]:
            got = drawn if drawn is not None else [(str(n), FIRST + PITCH * n - 8, FIRST + PITCH * n + 8) for n in numbers]
            return [Line(t, 1.0, x0, CY - 13, x1 - x0, 27) for t, x0, x1 in got]
        return [Line(t, 1.0, box[0], box[1], box[2] - box[0], box[3] - box[1]) for t in (value_lines or (lambda b: []))(box)]
    return lines


def picture_cam(a, name="00001_slider.png"):
    f = frame_of(a, name)
    s = kind_of(a)
    return SimpleNamespace(frame=f, read=lambda: s)


def reader_says(monkeypatch, S, said) -> list:
    """The vision reader stubbed for every frame: `said` its "selected" (a text), or its whole answer (a dict), or None
    (a reader that fails); its one-question-a-frame cache emptied. Returns the frames it was asked about."""
    asked = []
    monkeypatch.setattr(S, "_said", {})
    monkeypatch.setattr(S, "_by_reader", set())

    def option_answer(cam):
        asked.append(cam.frame.path)
        return {"title": "Aspect Marker Level", "selected": said, "value": ""} if isinstance(said, str) else said
    monkeypatch.setattr(S, "option_answer", option_answer)
    return asked


@pytest.mark.parametrize("at", [0, 7, 15])
@pytest.mark.parametrize("ocr_reads_it", [False, True])
def test_a_slider_over_a_picture_reads_its_number_from_the_marker(monkeypatch, at, ocr_reads_it):
    """The marker's place on the scale's own ticks, the scale's numbers read on their places (5, 10 and 15: the 0 at the
    low end dropped, as Apple's OCR drops it), and the number drawn in orange, where OCR reads it, the same. OCR
    reading the marker's number, or none, asks the reader nothing."""
    S = scale_run_module()
    asked = reader_says(monkeypatch, S, str(at))
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=(lambda b: [str(at)]) if ocr_reads_it else None))
    cam = picture_cam(picture_slider(at))
    assert S.value(cam) == str(at) and S.read_by(cam) == "marker"
    assert S.reading(cam, None, ["Aspect Marker Level"]) == S.Reading(str(at), cam.frame.path.name, False)
    assert asked == [] and cam.frame.path not in S._outvoted


@pytest.mark.parametrize("said", ["8", "+8", {"title": "Aspect Marker Level", "selected": "", "value": "8"}],
                         ids=["selected", "signed", "in-value"])
def test_where_ocr_reads_the_drawn_number_otherwise_the_reader_reading_the_markers_number_lets_it_stand(monkeypatch, said):
    """The marker on 8 and OCR reading the orange 8 as "00" (kit2_pass2 261759, 2026-11-19): the reader, asked once about
    that frame, reads 8 (by key), and the marker's number stands, read by the marker, not the reader (the reader never
    decides alone: a Reading the reader alone read would be by_reader); OCR's reading is kept as outvoted."""
    S = scale_run_module()
    asked = reader_says(monkeypatch, S, said)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: ["00"]))
    cam = picture_cam(picture_slider(8), "00009_left.png")
    assert S.value(cam) == "8" and S.read_by(cam) == "marker" and S._outvoted[cam.frame.path] == "00"
    assert S.reading(cam, None, ["Aspect Marker Level"]) == S.Reading("8", "00009_left.png", False)
    assert asked == [cam.frame.path], "one question a frame, however often it is read"


@pytest.mark.parametrize("said, reader", [
    ("9", "'9' by the reader"), ("00", "'00' by the reader"), ("Cancel", "the reader read 'Cancel', no number"),
    ("", "the reader read no number"), (None, "the reader gave no answer")],
    ids=["another-number", "ocrs-number", "a-word", "nothing", "failed"])
def test_where_the_reader_does_not_read_the_markers_number_the_row_stops_saying_what_each_read(monkeypatch, said, reader):
    """The marker on 8, OCR "00", the reader anything but 8 (OCR's own misreading too): no number, and number() stops the
    row, its screen closed, the message naming the frame and what the marker, OCR and the reader each read."""
    S = scale_run_module()
    asked = reader_says(monkeypatch, S, said)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: ["00"]))
    closed = []
    monkeypatch.setattr(S, "close_screen", lambda cam, link: closed.append(1))
    cam = picture_cam(picture_slider(8), "00009_left.png")
    msg = (r"no number read on the scale on frame 00009_left\.png, by its marker: the marker stands on '8' on the "
           r"scale, but the number drawn reads '00' by OCR" + (" and " if reader.startswith("'") else ", and ")
           + re.escape(reader) + "$")
    with pytest.raises(S.Failed, match=msg):
        S.number(cam, None, ["Aspect Marker Level"])
    assert closed == [1] and asked == [cam.frame.path] and cam.frame.path not in S._outvoted


@pytest.mark.parametrize("case, kw, why", [
    ("the number drawn read otherwise", dict(value_lines=lambda b: ["92"]), "the number drawn reads '92' by OCR"),
    ("one number read", dict(numbers=(15,)), "OCR read 1 of the scale's numbers"),
    ("none read", dict(numbers=()), "OCR read 0 of the scale's numbers"),
    ("numbers stepping unevenly", dict(drawn=[("5", 257, 273), ("10", 367, 383), ("16", 477, 493)]), "stepping evenly"),
    ("numbers falling", dict(drawn=[("15", 257, 273), ("10", 367, 383)]), "stepping evenly"),
    ("a number read two ways", dict(drawn=[("5", 257, 273), ("6", 259, 271), ("15", 477, 493)]), "two ways"),
    ("a number that is no whole number", dict(drawn=[("5", 257, 273), ("10.5", 367, 383)]), "no whole number"),
], ids=lambda v: v if isinstance(v, str) and len(v) < 40 else "")
def test_a_slider_over_a_picture_gives_no_number_where_its_readings_do_not_hold(monkeypatch, case, kw, why):
    S = scale_run_module()
    reader_says(monkeypatch, S, None)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(**kw))
    cam = picture_cam(picture_slider(12))
    assert S.value(cam) == "" and why in S._why[cam.frame.path], (case, S._why.get(cam.frame.path))


def test_a_line_across_two_numbers_is_no_reading_of_either(monkeypatch):
    """OCR reading "05" across the 0 and the 5 gives neither; 10 and 15 still give the scale."""
    S = scale_run_module()
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=[("05", 147, 273), ("10", 367, 383), ("15", 477, 493)]))
    assert S.value(picture_cam(picture_slider(3))) == "3"
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=[("05", 147, 273), ("15", 477, 493)]))
    assert S.value(picture_cam(picture_slider(3))) == ""


def hide(a, xs):
    """The ticks at `xs` painted over with the field's colour, as a picture as light as they are would hide them."""
    for x in xs:
        a[CY - 7:CY + 7, x - 2:x + 2] = (40, 90, 25)
    return a


def _tick_at(v):
    a = np.zeros((480, 640, 3), np.uint8)
    x = FIRST + PITCH * v
    a[CY - 6:CY + 6, x - 1:x + 1] = 221
    return a


def _blob_on_line():
    a = np.zeros((480, 640, 3), np.uint8)
    a[CY - 4:CY + 4, FIRST + PITCH * 6 + 7:FIRST + PITCH * 6 + 15] = 230
    return a


@pytest.mark.parametrize("band", [1.0, 0.15, 0.0])
@pytest.mark.parametrize("case, a, why", [
    ("a tick hidden", lambda b: hide(picture_slider(12, band=b), [FIRST + PITCH * 8]), "one on each place"),
    ("a tick beyond the high end's number", lambda b: picture_slider(12, band=b) | _tick_at(16),
     "no number drawn at each end"),
    ("a mark on the line that is neither", lambda b: picture_slider(12, band=b) | _blob_on_line(),
     "other than ticks and numbers"),
    ("no number at the high end", lambda b: picture_slider(12, band=b, hidden=(15,)), "no number drawn at each end"),
    ("no number at the low end", lambda b: picture_slider(12, band=b, hidden=(0,)), "no number drawn at each end"),
], ids=lambda v: v if isinstance(v, str) else "")
def test_a_scale_that_could_be_misplaced_gives_no_number(monkeypatch, case, a, why, band):
    """Whatever the bands' level, a scale missing a tick or an end's number, or with a mark on its line that is neither,
    is read as the slider but gives no number: never a guess at the marker's place."""
    S = scale_run_module()
    monkeypatch.setattr(S, "masked_lines", scale_ocr())
    cam = picture_cam(a(band))
    assert cam.read().kind == "slider", case
    assert S.value(cam) == "" and why in S._why[cam.frame.path], (case, S._why.get(cam.frame.path))


@pytest.mark.parametrize("band", BANDS)
@pytest.mark.parametrize("at", [0, 1, 7, 15])
def test_the_number_is_the_markers_at_every_level(monkeypatch, at, band):
    """The bands from untouched to black, the marker at either end too: the number is the one the marker stands on, read
    by the marker, the reader not asked (OCR reading nothing on the orange digits)."""
    S = scale_run_module()
    asked = reader_says(monkeypatch, S, None)
    monkeypatch.setattr(S, "masked_lines", scale_ocr())
    cam = picture_cam(picture_slider(at, band=band))
    assert S.value(cam) == str(at) and S.read_by(cam) == "marker" and asked == []


def test_number_stops_the_row_saying_why_the_marker_gave_none(monkeypatch):
    S = scale_run_module()
    reader_says(monkeypatch, S, "92")
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: ["92"]))
    closed = []
    monkeypatch.setattr(S, "close_screen", lambda cam, link: closed.append(1))
    cam = picture_cam(picture_slider(12), "00007_right.png")
    with pytest.raises(S.Failed, match=r"no number read on the scale on frame 00007_right\.png, by its marker: the "
                                       r"marker stands on '12' on the scale, but the number drawn reads '92' by OCR "
                                       r"and '92' by the reader"):
        S.number(cam, None, ["Aspect Marker Level"])
    assert closed == [1]


def test_a_slider_with_its_footer_rule_is_still_read_by_ocr_in_its_box(monkeypatch):
    """The marker is read only on a slider over a picture: elsewhere OCR's number in the value box, as before."""
    from camkit.ocr import Line
    S = scale_run_module()
    monkeypatch.setattr(S, "masked_lines", lambda mask, box: pytest.fail("no masked reading off a picture slider"))
    monkeypatch.setattr(S.ocr, "read", lambda paths: {p: [Line("3", 1.0, 311, 287, 18, 29)] for p in paths})
    monkeypatch.setattr(S, "_number_box", S.VALUE)
    cam = SimpleNamespace(frame=frame_of(picture_slider(footer_rule=True)),
                          read=lambda: kind_of(picture_slider(footer_rule=True)))
    assert S.picture_of(cam) is None and S.value(cam) == "3" and S.read_by(cam) == "ocr"


@pytest.fixture
def scale_main(monkeypatch, tmp_path):
    """test_scale_run's drive: scale_run.main() on a made-up slider, its proofs in a run folder of its own."""
    import test_scale_run
    return test_scale_run.drive.__wrapped__(monkeypatch, tmp_path)


def picture_slider_cam(held, top=15, unknown=()):
    """test_scale_run's Slider, each scale frame Aspect Marker Level over a picture at the place it shows; at the places
    in `unknown` the pixel reader reads it as no known kind (as kit2_pass2 261808 to 261812 once read)."""
    import test_scale_run
    from camkit.frames import Frame
    cache: dict = {}

    class PictureSlider(test_scale_run.Slider):
        def shoot(self):
            super().shoot()
            at = self.truth[self.frame.path]
            self.frame = frame_of(picture_slider(at) if at is not None else blank(), self.frame.path.name)

        def read(self):
            at = self.truth.get(self.frame.path)
            if self.screen != "scale" or at is None or self.lit == "setup" or at in unknown:
                return super().read()
            if at not in cache:
                cache[at] = screen.read(Frame(image=picture_slider(at), t=0.0))
            return cache[at]
    return PictureSlider(held, top)


@pytest.mark.parametrize("held", [0, 7, 12, 15])
def test_main_proves_a_slider_over_a_picture_by_its_marker_with_its_checks(monkeypatch, scale_main, held):
    """scale_run.main() on Aspect Marker Level over a picture: the look reads 0 to 15, every OK lands on the value its
    line names, each line read by the marker, the put-back back on the held value with nothing changed, the row's
    attempt finished. OCR reads no number in the old box, as on the camera."""
    S = scale_run_module()
    cam = picture_slider_cam(held)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: [str(cam.truth[cam.frame.path])]
                                                     if cam.truth[cam.frame.path] >= 10 else []))
    got = scale_main(held, set(), lambda place, i: str(place), cam=cam)
    assert "stopped" not in got.out, got.out
    assert f"Made-up Scale: {[str(v) for v in range(16)]}, held '{held}'" in got.out
    want = [i for i in range(16) if i != held] + [held]
    assert got.cam.oks == want and [ln["label"] for ln in got.lines] == [str(i) for i in want]
    assert got.shown == want and {ln["read_by"] for ln in got.lines} == {"marker"}
    assert got.lines[-1]["changes"] == [] and len(got.attempts) == 1 and got.counted == got.lines
    assert {p.name for p in got.asked} <= {ln["chosen_frame"] for ln in got.lines}, \
        "OCR reading the marker's number or none: the reader asked only for the line's second reading, at OK"
    assert not any("ocr_outvoted" in ln for ln in got.lines)


def test_main_proves_a_slider_over_a_picture_where_the_reader_outvotes_ocr_and_says_so(monkeypatch, scale_main):
    """OCR reading the number drawn as "92" on every frame of 9, the reader reading 9 there: the row is proved whole, the
    reader asked about those frames only (and at each OK, for the line's second reading); 9's line is read by the marker
    and keeps OCR's reading as "ocr_outvoted", the others carry none. The report credits 9 to two readers, the marker and
    the vision model, which is what read it on that frame."""
    import pass2_report as R
    S = scale_run_module()
    cam = picture_slider_cam(12)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: ["92"] if cam.truth[cam.frame.path] == 9
                                                     else []))
    got = scale_main(12, set(), lambda place, i: str(place), cam=cam)
    assert "stopped" not in got.out, got.out
    want = [i for i in range(16) if i != 12] + [12]
    assert got.cam.oks == want and got.shown == want and len(got.attempts) == 1 and got.counted == got.lines
    assert {ln["read_by"] for ln in got.lines} == {"marker"}
    assert [(ln["label"], ln["ocr_outvoted"]) for ln in got.lines if "ocr_outvoted" in ln] == [("9", "92")]
    nine = next(ln for ln in got.lines if ln["label"] == "9")
    assert nine["vlm"] == "9" and R.name_of(nine) == ("9", "two readers", None)
    chosen = {ln["chosen_frame"] for ln in got.lines}
    assert all(cam.truth[p] == 9 or p.name in chosen for p in got.asked)
    assert any(cam.truth[p] == 9 and p.name not in chosen for p in got.asked), "asked in the look too"


@pytest.mark.parametrize("said", ["10", "92", ""], ids=["another-number", "ocrs-number", "nothing"])
def test_main_stops_a_slider_over_a_picture_whose_number_reads_otherwise(monkeypatch, scale_main, said):
    """The number drawn read otherwise than the marker's on one frame of the look, and the reader not reading the
    marker's number there either: the row stops, no OK, no line, the message saying what each of the three read."""
    S = scale_run_module()
    cam = picture_slider_cam(12)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(value_lines=lambda b: ["92"] if cam.truth[cam.frame.path] == 9
                                                     else []))
    got = scale_main(12, set(), lambda place, i: said if place == 9 else str(place), cam=cam)
    assert "the marker stands on '9' on the scale, but the number drawn reads '92' by OCR" + (
        f" and {said!r} by the reader" if said else ", and the reader read no number") in got.out
    assert got.cam.oks == [] and got.lines == [] and got.attempts == []


@pytest.mark.parametrize("held", [6, 12])
def test_main_stops_a_slider_over_a_picture_where_it_turns_unknown_before_the_next_left(monkeypatch, scale_main, held):
    """The slider over a picture opened on `held`, its frames from 3 down reading as no known kind (as kit2_pass2 261808
    to 261812 did, 2026-11-19), OCR reading the number on every frame: the look stops on the first such frame, before
    another Left, its screen closed with MENU (the slider's place not applied), no OK and no line, and the session's
    restore puts the start back. A scale's walk goes on only while its screen reads as the one its row opened."""
    S = scale_run_module()
    cam = picture_slider_cam(held, unknown={0, 1, 2, 3})
    monkeypatch.setattr(S, "masked_lines", scale_ocr())
    got = scale_main(held, set(range(16)), lambda place, i: str(place), cam=cam)
    (frame,) = [p.name for p, at in got.cam.truth.items() if at == 3]
    assert (f"Made-up Scale stopped: Failed: Made-up Scale: the scale opened as a slider drawn over a picture, but frame "
            f"{frame} reads as a screen of no known kind") in got.out
    assert got.cam.presses == ["left"] * (held - 3), "no key after the frame that read otherwise"
    assert got.cam.oks == [] and got.lines == [] and got.attempts == []
    assert got.cam.screen == "shooting" and got.cam.pos == held, "closed with MENU, nothing applied"
    assert got.cam.restored_from == Path("start.DAT") and got.cam.setting == held


def test_a_choice_stops_where_its_slider_turns_unknown_before_any_ok(monkeypatch):
    """A choice from 6 down to 0 on the slider over a picture, the frame of 3 reading as no known kind: the row stops
    there, before another Left and before any OK, its screen closed, the frame named."""
    from camkit.ocr import Line
    S = scale_run_module()
    cam = picture_slider_cam(6, unknown={3})
    closed = []

    def open_row(c, cycle, model, path, panel=False):
        cam.screen, cam.pos = "scale", cam.setting
        cam.shoot()
    monkeypatch.setattr(S, "open_row", open_row)
    monkeypatch.setattr(S, "close_screen", lambda c, link: closed.append(c.frame.path.name))
    monkeypatch.setattr(S, "masked_lines", scale_ocr())
    monkeypatch.setattr(S.ocr, "read", lambda paths, eng=None: {p: [Line(str(cam.truth[p]), 1.0, 311, 287, 18, 29)]
                                                                for p in paths})
    reader_says(monkeypatch, S, None)
    with pytest.raises(S.Failed, match=r"the scale opened as a slider drawn over a picture, but frame \d+_slider\.png "
                                       r"reads as a screen of no known kind"):
        S.choose(cam, None, None, None, None, ["Made-up Scale"], [str(v) for v in range(16)], 0, 6)
    (three,) = [p.name for p, at in cam.truth.items() if at == 3]
    assert cam.presses == ["left"] * 3 and cam.oks == [] and closed == [three]


AM_LEVEL = [A1 / "kit2_pass2" / "shots" / "259951_right.png",
            A1 / "kit2_fin_crawl_amdisp_off" / "shots" / "00028_right.png"]
AM_LEVEL_8 = A1 / "kit2_pass2" / "shots" / "261759_left.png"     # the marker on 8, OCR's "00" (2026-11-19)
AM_DRAWN = [("5", 254, 271), ("10", 356, 393), ("15", 466, 501)]   # what Apple's OCR read alone on their scale's line


def real_picture_cam(path):
    f = load(need(path))
    s = screen.read(f)
    return SimpleNamespace(frame=f, read=lambda: s)


@pytest.mark.parametrize("path", AM_LEVEL, ids=["pass2", "crawl"])
def test_the_aspect_marker_level_frames_read_12_by_their_marker(monkeypatch, path):
    """The frames the prover stopped on (2026-11-19): the scale's numbers on places 0, 5, 10 and 15 of a grid from x 155,
    22 px a step, the marker on place 12; with what Apple's OCR read alone on the line (5, 10, 15) and on the orange
    digits (12), the number is 12; with the number read "92" (OCR's reading of it over the photograph), none."""
    S = scale_run_module()
    cam = real_picture_cam(path)
    pic = S.picture_of(cam)
    assert pic and pic["strays"] == 0 and len(pic["numbers"]) == 4 and pic["grid"] == (177.0, 22.0)
    asked = reader_says(monkeypatch, S, None)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=AM_DRAWN, value_lines=lambda b: ["12"]))
    assert S.value(cam) == "12" and S.read_by(cam) == "marker" and asked == []
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=AM_DRAWN, value_lines=lambda b: ["92"]))
    assert S.value(cam) == "" and "reads '92' by OCR, and the reader gave no answer" in S._why[cam.frame.path]
    assert asked == [cam.frame.path]


@pytest.mark.parametrize("said, got", [("8", "8"), ("9", ""), ("", ""), (None, "")],
                         ids=["reader-8", "reader-9", "reader-nothing", "reader-failed"])
def test_the_frame_whose_8_ocr_read_00_reads_8_where_the_reader_reads_8(monkeypatch, said, got):
    """The frame the prover stopped on (kit2_pass2 261759, 2026-11-19): the marker on place 8 of the same grid; with what
    Apple's OCR read alone on the line (5, 10, 15) and on the orange digit ("00"), the reader is asked once about that
    frame: reading 8, the number is 8, read by the marker, OCR's "00" kept as outvoted; reading anything else, none."""
    S = scale_run_module()
    cam = real_picture_cam(AM_LEVEL_8)
    pic = S.picture_of(cam)
    assert pic and pic["strays"] == 0 and pic["grid"] == (177.0, 22.0) and pic["marker"] == 330
    asked = reader_says(monkeypatch, S, said)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=AM_DRAWN, value_lines=lambda b: ["00"]))
    assert S.value(cam) == got and asked == [cam.frame.path]
    if got:
        assert S.read_by(cam) == "marker" and S._outvoted[cam.frame.path] == "00"
    else:
        assert "the marker stands on '8' on the scale, but the number drawn reads '00' by OCR" in S._why[cam.frame.path]


# the walk the prover stopped on (kit2_pass2, 2026-11-19, OSD eyes: opened on 12, Left down to 1; "fresh" a frame
# grabbed again without a press) and the frame of 8 a run before it: each frame's value, the place its marker stands on
AM_WALK = {"261759_left.png": 8, "261797_right.png": 12, "261798_fresh.png": 12, "261799_left.png": 11,
           "261800_left.png": 10, "261801_left.png": 9, "261802_left.png": 8, "261803_fresh.png": 8,
           "261804_left.png": 7, "261805_left.png": 6, "261806_left.png": 5, "261807_left.png": 4,
           "261808_left.png": 3, "261809_fresh.png": 3, "261810_left.png": 2, "261811_fresh.png": 2,
           "261812_left.png": 1}


@pytest.mark.parametrize("name", sorted(AM_WALK))
def test_the_aspect_marker_level_walk_reads_every_frame_by_its_marker(monkeypatch, name):
    """Every frame of that walk, 3 down to 1 among them (read unknown then: the bands outside the aspect marker grown
    as light as the picture), is a slider over a picture, the scale on the grid from x 155 at 22 px a step; its number
    the one its marker stands on, with what Apple's OCR read alone on the scale's line (5, 10, 15) and nothing read on
    the orange digits, the reader not asked."""
    S = scale_run_module()
    cam = real_picture_cam(A1 / "kit2_pass2" / "shots" / name)
    s, want = cam.read(), AM_WALK[name]
    pic = s.features.get("picture_slider")
    assert s.kind == "slider" and pic and pic["grid"] == (177.0, 22.0) and round((s.marker - FIRST) / PITCH) == want
    asked = reader_says(monkeypatch, S, None)
    monkeypatch.setattr(S, "masked_lines", scale_ocr(drawn=AM_DRAWN))
    assert S.value(cam) == str(want) and S.read_by(cam) == "marker" and asked == [], S._why.get(cam.frame.path)


@pytest.mark.parametrize("path", AM_LEVEL, ids=["pass2", "crawl"])
def test_the_aspect_marker_level_frames_read_12_with_this_computers_ocr(monkeypatch, path):
    """Opt-in (skipped without the runs or this computer's OCR): the real OCR on the masked line and digits, the reader
    never asked (a reader that fails: OCR alone reads the 12)."""
    from camkit import ocr
    S = scale_run_module()
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    asked = reader_says(monkeypatch, S, None)
    cam = real_picture_cam(path)
    assert S.value(cam) == "12" and S.read_by(cam) == "marker", S._why.get(cam.frame.path)
    assert asked == []


def test_the_frame_whose_8_ocr_read_00_reads_8_with_this_computers_ocr_and_the_reader_reading_8(monkeypatch):
    """Opt-in (skipped without the runs or this computer's OCR): the real OCR on kit2_pass2 261759, the reader stubbed to
    read 8: the number is 8, by the marker, the reader asked at most once (only where OCR reads the 8 otherwise)."""
    from camkit import ocr
    S = scale_run_module()
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    asked = reader_says(monkeypatch, S, "8")
    cam = real_picture_cam(AM_LEVEL_8)
    assert S.value(cam) == "8" and S.read_by(cam) == "marker", S._why.get(cam.frame.path)
    assert asked == ([cam.frame.path] if cam.frame.path in S._outvoted else [])


# ---------------------------------------------------------------- 8. --stepped: a look that stepped a value

LIVE = "Tv STEP Tv Anti-flicker Tv Scan MENU Exit 256.0 F5.6 ±0.0 ISO"


@pytest.mark.parametrize("case, args, stepped", [
    ("Up on a live adjust screen", ("up", None, "unknown", "unknown", LIVE, LIVE.replace("256.0", "257.4")), True),
    ("a dial on a slider", ("dial.front.1", None, "slider", "slider", "Level 3", "Level 4"), True),
    ("Left on number fields", ("left", None, "fields", "fields", "10 : 30", "10 : 29"), True),
    ("the text read alike", ("up", None, "unknown", "unknown", LIVE, LIVE), False),
    ("spacing alone", ("up", None, "unknown", "unknown", LIVE, LIVE.replace(" ", "  ")), False),
    ("nothing read after it", ("up", None, "unknown", "unknown", LIVE, " "), False),
    ("MENU", ("menu", None, "unknown", "unknown", LIVE, "other"), False),
    ("an opener", ("right", None, "unknown", "unknown", LIVE, "other"), False),
    ("Enter", ("enter", None, "unknown", "unknown", LIVE, "other"), False),
    ("a cursor's key@y", ("down", "367", "unknown", "unknown", LIVE, "other"), False),
    ("a menu page", ("down", None, "menu", "menu", "Shooting > A B", "Shooting > A C"), False),
    ("a submenu page", ("down", None, "submenu", "submenu", "A > B", "A > C"), False),
    ("a list whose cursor moved", ("down", None, "list", "list", "Off On", "Off On"), False),
    ("a list that scrolled", ("down", None, "list", "list", "1 2 3 4", "2 3 4 5"), False),
    ("a side list", ("down", None, "sidelist", "sidelist", "A B", "B C"), False),
    ("the screen left for another kind", ("up", None, "unknown", "notice", LIVE, "Not available"), False),
], ids=lambda v: v if isinstance(v, str) else "")
def test_a_press_steps_a_value_only_off_cursor_screens_with_the_text_changed(case, args, stepped):
    assert drive.stepped_press(*args) is stepped, case


def test_the_up_that_stepped_var_shutter_set_this_morning_is_a_stepped_press():
    """kit2_fin_vs_up1 (2026-11-19): Right opened the live screen, Up stepped 256.0 to 257.4, MENU left it."""
    import json
    line = json.loads(need(A1 / "kit2_fin_vs_up1" / "drive.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    opened, up, menu = line["screens"][:3]
    assert drive.stepped_press("up", None, opened["kind"], up["kind"], opened["text"], up["text"])
    assert not drive.stepped_press("menu", None, up["kind"], menu["kind"], up["text"], menu["text"])


def vs_line(**kw):
    """A drive.jsonl result line as kit2_fin_vs_up1's: Right opened the row's live screen, Up, MENU."""
    return {"path": ["Kilo"], "presses": ["right", "up:Tv Scan", "menu"], "completed": True,
            "screens": [{"after": "right", "kind": "unknown"}, {"after": "up:Tv Scan", "kind": "unknown"},
                        {"after": "menu", "kind": "menu"}],
            "before": "a.DAT", "after": "b.DAT", "changes": [], **kw}


@pytest.fixture
def ledger_camera(tmp_path, monkeypatch):
    """test_coverage's made-up camera (its definition, looks and runs in the test's own folders)."""
    import test_coverage
    return test_coverage.camera.__wrapped__(tmp_path, monkeypatch)


def test_a_stepped_line_is_a_choice_tested_with_no_record_changes_and_a_plain_one_stays_an_open(ledger_camera):
    """drive_look: "stepped": true makes the run a choice (the ledger's "tested, no record changes" where no record
    differed); the same presses without it an open, which leaves the row "not yet tried" as before. The look keeps no
    option and no value either way."""
    import test_coverage as T
    from camkit import coverage
    lk = coverage.drive_look(vs_line(), T.CAM, "Stills", "kit2_x")
    assert lk["did"] == "open" and lk["result"] == "no_change" and lk["option"] is None
    T.add_looks(ledger_camera, {k: v for k, v in lk.items() if v is not None})
    assert T.row(T.ledger(), "Kilo")["status"] == "not yet tried"
    lk = coverage.drive_look(vs_line(stepped=True), T.CAM, "Stills", "kit2_y")
    assert lk["did"] == "choose" and lk["result"] == "no_change" and lk["option"] is None
    assert "256.0" not in json_text(lk) and "257.4" not in json_text(lk)
    T.add_looks(ledger_camera, {k: v for k, v in lk.items() if v is not None})
    assert T.row(T.ledger(), "Kilo")["status"] == "tested, no record changes"


def json_text(x) -> str:
    import json
    return json.dumps(x)


def test_a_stepped_line_without_an_opening_press_stays_an_open():
    from camkit import coverage
    from conftest import TEST_CAMERA
    for presses in ([], ["up", "menu"], ["down@3"]):
        assert coverage.drive_look(vs_line(presses=presses, stepped=True), TEST_CAMERA, None, "r")["did"] == "open"
    assert coverage.drive_look(vs_line(stepped="yes"), TEST_CAMERA, None, "r")["did"] == "open", "true alone"


def stepped_run(tmp_path, monkeypatch, presses, states, stepped=True, path=("Kilo",)):
    """drive.py's main() as test_first_open's drive_run fakes it, the row `path` seen opened, each state (kind, lit,
    text) the screen after the opening MENU and after each press. Returns (the presses sent, the drive.jsonl line, what
    was printed)."""
    import contextlib
    import io
    import json

    import runner
    from camkit import coverage
    from camkit.runs import Run
    from conftest import TEST_CAMERA
    from test_first_open import says
    assert coverage.append_look(TEST_CAMERA, {"t": "2026-11-19T10:00:00", "by": "crawl", "path": list(path),
                                              "did": "open", "result": "looked"})
    run = Run("kit2_drive", root=tmp_path)
    pressed = []

    def now():
        return states[min(max(len(pressed) - 1, 0), len(states) - 1)]

    class Cam:
        frame = SimpleNamespace(path=tmp_path / "00001_menu.png", image=None)

        def read(self):
            return SimpleNamespace(kind=now()[0])

        def press(self, key, **kw):
            pressed.append(key)

        def refresh(self, tag):
            return self.read()

    ending = SimpleNamespace(after=tmp_path / "after.DAT", uploaded=False, changes=[])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT", press=lambda *a, **k: None, call=says().call)
    for name, value in (("check_readers", lambda: None), ("load_scan", lambda _: ([], {})), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None,
                                                                       grab=lambda save=False: None, close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("LiveCamera", lambda *a, **k: Cam()),
                        ("find_position", lambda cam, cycle, model: 0), ("go_to", lambda *a, **k: True),
                        ("enter_any", lambda cam, path, i: None), ("screen_text", lambda cam, grip: now()[2]),
                        ("highlighted", lambda image, p: now()[1]),
                        ("time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0)),
                        ("close_for_restore", lambda cam, link, start: None),
                        ("restore_checked", lambda r, e, before, **k: True), ("row_values", lambda model: {}),
                        ("submenu_labels", lambda cam: ("page", [{"label": x, "readings": [x]} for x in path])),
                        ("page_labels", lambda now, cycle, model: list(path)),
                        ("Link", lambda r, **k: contextlib.nullcontext(link))):
        monkeypatch.setattr(drive, name, value)
    monkeypatch.setattr(runner.session, "finish", lambda link, before, **k: ending)
    monkeypatch.setattr(sys, "argv", ["drive.py", *[x for p in path for x in ("--path", p)],
                                      *[x for p in presses for x in ("--press", p)], *(["--stepped"] if stepped else [])])
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        drive.main()
    lines = (run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines()
    return pressed, json.loads(lines[-1]), out.getvalue()


MENU_PAGE = ("menu", "Kilo", "Shooting > G1 Kilo Alpha")


def test_drive_stepped_says_a_choice_where_a_press_inside_the_open_row_stepped_it(tmp_path, monkeypatch):
    states = [MENU_PAGE, ("unknown", "", LIVE), ("unknown", "", LIVE.replace("256.0", "257.4")), MENU_PAGE]
    pressed, line, said = stepped_run(tmp_path, monkeypatch, ["right", "up:Tv Scan", "menu"], states)
    assert pressed == ["menu", "right", "up", "menu"]
    assert line["stepped"] is True and [s.get("stepped") for s in line["screens"][:3]] == [None, True, None]
    assert "up stepped the row's value" in said and "257.4" not in json_text(line.get("stepped"))
    from camkit import coverage
    from conftest import TEST_CAMERA
    assert coverage.drive_look(line, TEST_CAMERA, None, "r")["did"] == "choose"


@pytest.mark.parametrize("case, presses, states", [
    ("a list whose cursor only moved", ["right", "down", "menu"],
     [MENU_PAGE, ("list", "Off", "Kilo Off On"), ("list", "On", "Kilo Off On"), MENU_PAGE]),
    ("a list that scrolled", ["right", "down", "menu"],
     [MENU_PAGE, ("list", "1", "Kilo 1 2 3"), ("list", "4", "Kilo 2 3 4"), MENU_PAGE]),
    ("Up on the menu page before the row opened", ["up", "right", "menu"],
     [MENU_PAGE, ("menu", "Kilo", "Shooting > G1 Juliet Kilo"), ("unknown", "", LIVE), MENU_PAGE]),
    ("Up after the row's screen was left", ["right", "menu", "up"],
     [MENU_PAGE, ("unknown", "", LIVE), MENU_PAGE, ("menu", "Juliet", "Shooting > G1 Juliet Kilo")]),
    ("nothing pressed inside", ["right", "menu"], [MENU_PAGE, ("unknown", "", LIVE), MENU_PAGE]),
], ids=lambda v: v if isinstance(v, str) else "")
def test_drive_stepped_leaves_an_open_where_no_press_stepped_the_row(tmp_path, monkeypatch, case, presses, states):
    pressed, line, said = stepped_run(tmp_path, monkeypatch, presses, states)
    assert "stepped" not in line and not any(s.get("stepped") for s in line["screens"]), case
    assert "--stepped: no press stepped the --path's row" in said, case
    from camkit import coverage
    from conftest import TEST_CAMERA
    assert coverage.drive_look(line, TEST_CAMERA, None, "r")["did"] == "open", case


def test_drive_stepped_lets_no_press_through_that_was_refused_without_it(tmp_path, monkeypatch):
    """Enter with no regex is refused before anything connects, and Right on an unread lit row on the page, with
    --stepped as without it; a run without --stepped that steps writes no "stepped"."""
    for flag in (False, True):
        monkeypatch.setattr(sys, "argv", ["drive.py", "--path", "Kilo", "--press", "enter",
                                          *(["--stepped"] if flag else [])])
        with pytest.raises(SystemExit, match="regex"):
            drive.main()
    states = [("menu", "", "Shooting > G1"), ("unknown", "", LIVE)]
    for flag in (False, True):
        pressed, line, said = stepped_run(tmp_path / str(flag), monkeypatch, ["right"], states, stepped=flag)
        assert pressed == ["menu"] and "right refused" in said and "stepped" not in line
    states = [MENU_PAGE, ("unknown", "", LIVE), ("unknown", "", LIVE.replace("256.0", "257.4")), MENU_PAGE]
    pressed, line, said = stepped_run(tmp_path / "plain", monkeypatch, ["right", "up", "menu"], states, stepped=False)
    assert pressed == ["menu", "right", "up", "menu"] and "stepped" not in line and "stepped" not in said


# ---------------------------------------------------------------- 9. a label read with a space before its bracket

FRING = "Function Ring(Lens)"


def fring_judged(lit, path=(FRING,), depth=None, known=(), values=None, seen=None):
    from camkit import first_open
    return drive.lit_refused(lit, list(path[:-1]) if depth is None else depth, list(path), seen or first_open.Seen(),
                             set(known), None, values or {}, None)


@pytest.mark.parametrize("lit", ["Function Ring (Lens)", "Function  Ring (Lens)", "Function Ring ( Lens )",
                                 "Function Ring(Lens)", "function ring (lens)"])
def test_the_paths_own_row_read_with_a_space_before_its_bracket_is_that_row(lit):
    assert fring_judged(lit) == ("", (FRING,)), lit
    assert drive.reads_row_spaced(lit, FRING), lit


def test_a_value_after_the_spaced_label_is_judged_as_before():
    values = {"function ring(lens)": ["Off", "On"]}
    assert fring_judged("Function Ring (Lens) On", values=values) == ("", (FRING,))
    why, row = fring_judged("Function Ring (Lens) Zoom", values=values)
    assert row is None and "runs on past the row" in why


@pytest.mark.parametrize("case, lit, path, depth, known", [
    ("the path names Function Ring alone", "Function Ring (Lens)", ("Function Ring",), None, ()),
    ("a longer row read", "Function Ring (Lens) Set.", (FRING,), None, ()),
    ("a digit glued after it", "Function Ring (Lens)2", (FRING,), None, ()),
    ("another letter", "Function Rings (Lens)", (FRING,), None, ()),
    ("another sign", "Function Ring (Lens.)", (FRING,), None, ()),
    ("a stop before the bracket", "Function Ring. (Lens)", (FRING,), None, ()),
    ("another page", "Function Ring (Lens)", ("Dial Customize", FRING), ["Other"], ()),
    ("another row of the page, not the path's", "Function Ring (Lens)", ("Zoom",), None, (FRING,)),
], ids=lambda v: v if isinstance(v, str) else "")
def test_what_merely_starts_alike_stays_refused(case, lit, path, depth, known):
    why, row = fring_judged(lit, path, depth, known)
    assert why and row is None, (case, why)
    if case not in ("the path names Function Ring alone", "a longer row read", "another page",
                    "another row of the page, not the path's"):
        assert not drive.reads_row_spaced(lit, path[-1]), case


def test_a_longer_row_the_bar_reads_plainly_stays_that_row():
    """The longest-label rule first: a known row the bar reads exactly and longer than the --path's label keeps it."""
    from camkit import first_open
    seen = first_open.Seen({("function ring (lens) x",)})
    why, row = fring_judged("Function Ring (Lens) X", known={"Function Ring (Lens) X"}, seen=seen)
    assert (why, row) == ("", ("function ring (lens) x",))


@pytest.fixture
def statement_scope(own_runs, monkeypatch):
    import test_first_open
    return test_first_open.scope.__wrapped__(own_runs, monkeypatch)


def test_drive_makes_the_first_open_of_a_row_read_with_a_space_before_its_bracket(tmp_path, monkeypatch,
                                                                                 statement_scope):
    """kit2_fin_look_fring2 (2026-11-19): `--path "Function Ring(Lens)" --press right`, the bar read "Function Ring
    (Lens)", now opens as that row's first open (RESTORE_BY_HAND written before its Right); a bar reading Function Ring
    alone, or another row, is still refused."""
    from test_first_open import BLANK, drive_run
    statement_scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path / "a", monkeypatch, path=(FRING,), lit="Function Ring (Lens)",
                                          shown=(FRING,))
    assert pressed == [("menu", False), ("right", True)] and line["first_open"] is True, said
    for lit in ("Function Ring", "Function Ring (Lens) Set.", "Zoom Ring Rotate"):
        code, pressed, line, said = drive_run(tmp_path / lit.replace(" ", "_"), monkeypatch, path=(FRING,), lit=lit,
                                              shown=(FRING,))
        assert pressed == [("menu", False)] and "right refused" in said, (lit, said)


def test_the_refusal_of_this_morning_is_lifted():
    """The lit text the run refused (its events.jsonl, kit2_fin_look_fring2): the --path's row now."""
    import json
    events = need(A1 / "kit2_fin_look_fring2" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    why = next(json.loads(x)["why"] for x in events if '"press_refused"' in x)
    lit = why.split("'")[1]
    assert lit == "Function Ring (Lens)" and fring_judged(lit) == ("", (FRING,)) and drive.reads_row_spaced(lit, FRING)


def test_the_bar_of_this_morning_read_by_this_computers_ocr_is_the_row():
    """Opt-in (skipped without the runs or this computer's OCR): the frame the Right was refused on."""
    from camkit import ocr
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = load(need(A1 / "kit2_fin_look_fring2" / "shots" / "00008_down.png"))
    lit = drive.highlighted(f.image, f.path)
    assert drive.lit_refused(lit, [], [FRING], __import__("camkit.first_open").first_open.Seen(), set(), None,
                             {"function ring(lens)": ["-"]}, None) == ("", (FRING,)), lit


# ---------------------------------------------------------------- 10. the first open of an icon row in a submenu

def test_the_first_opens_check_takes_a_submenu_bar_lit_refused_tied_to_the_row():
    assert drive.first_open_tied(VARSH_LIT, VARSH[:-1], VARSH, ["Var. Shutter", varsh_bar()], tuple(VARSH))
    assert not drive.reads_row_spaced(VARSH_LIT, VARSH[-1]), "the label check alone refuses it, as before"


@pytest.mark.parametrize("case", ["no bar read", "another frame's bar", "the reader reads otherwise",
                                  "another row reads the label", "lit_refused named no row", "lit_refused named another",
                                  "another page", "a page not placed", "a one-label path"])
def test_the_first_opens_check_takes_no_wider_than_lit_refuseds_submenu_rule(case):
    lit, depth, path, labels, row = VARSH_LIT, VARSH[:-1], VARSH, [varsh_bar()], tuple(VARSH)
    if case == "no bar read":
        labels = ["Var. Shutter Set.", VARSH_LIT]
    elif case == "another frame's bar":
        labels = [varsh_bar(lit="fVar. Shutter")]
    elif case == "the reader reads otherwise":
        labels = [varsh_bar(readings=(VARSH_LIT, VARSH_LIT))]
    elif case == "another row reads the label":
        labels = [varsh_bar(others=(*VARSH_OTHERS, "Var. Shutter Set."))]
    elif case == "lit_refused named no row":
        row = None
    elif case == "lit_refused named another":
        row = ("Anti-flicker Set.", "Var. Shutter")
    elif case == "another page":
        depth = ["Drive Mode"]
    elif case == "a page not placed":
        depth = None
    elif case == "a one-label path":
        path, depth, row = ["Var. Shutter Set."], [], ("Var. Shutter Set.",)
    assert not drive.first_open_tied(lit, depth, path, labels, row), case


def test_drive_makes_the_first_open_of_an_icon_row_in_a_submenu_under_the_link_loss_procedure(tmp_path, monkeypatch,
                                                                                              statement_scope):
    """`--path "Anti-flicker Set." --path "Var. Shutter Set." --press right` on a body that has opened Anti-flicker Set.
    but not the row: the bar "fVar. Shutter Set.", tied by the submenu page read live, opens as the row's first open,
    RESTORE_BY_HAND written before its Right, the start file checked after; without the bar read, refused as before."""
    from conftest import TEST_CAMERA
    from test_first_open import BLANK, drive_run, look, looks_of
    from camkit.runs import restore_pending
    statement_scope(BLANK)
    looks_of(TEST_CAMERA, look(["Anti-flicker Set."]))
    monkeypatch.setattr(drive, "submenu_bar", lambda cam, rows: varsh_bar())
    code, pressed, line, said = drive_run(tmp_path / "a", monkeypatch, path=tuple(VARSH), lit=VARSH_LIT,
                                          states=[("submenu", VARSH_LIT)], live=READER["varsh"])
    assert pressed == [("menu", False), ("right", True)] and line["first_open"] is True, said
    assert "opens as any row from now on" in said and not restore_pending(tmp_path / "a")
    monkeypatch.setattr(drive, "submenu_bar", lambda cam, rows: None)
    code, pressed, line, said = drive_run(tmp_path / "b", monkeypatch, path=tuple(VARSH), lit=VARSH_LIT,
                                          states=[("submenu", VARSH_LIT)], live=READER["varsh"])
    assert pressed == [("menu", False)] and "right refused" in said, said
    monkeypatch.setattr(drive, "submenu_bar", lambda cam, rows: varsh_bar(readings=(VARSH_LIT, VARSH_LIT)))
    code, pressed, line, said = drive_run(tmp_path / "c", monkeypatch, path=tuple(VARSH), lit=VARSH_LIT,
                                          states=[("submenu", VARSH_LIT)], live=READER["varsh"])
    assert pressed == [("menu", False)] and "right refused" in said, said


# ---------------------------------------------------------------- 12. the rules' defaults are the decisions' Rule lines

def test_no_comment_says_the_playbooks_rules_hold_a_default():
    """Since 3613360 the by-hand default is decision 8's Rule line (AGENTS.md's list), the serial number screen's
    decision 24's; the playbook's section 1, rules 1-4, holds how an owner allows more."""
    import re
    kit = Path(__file__).resolve().parents[1]
    for f in (kit / "camkit" / "safety.py", kit / "tests" / "test_guards.py"):
        text = " ".join(f.read_text(encoding="utf-8").replace("#", " ").split())
        assert not re.search(r"playbook's rules? (?:3|1-4)\b(?! how)", text), f.name


# ---------------------------------------------------------------- 13. an option drawn grey is never chosen

def option_line(text_grey, kind="sidelist", ink=True, lit=True):
    """A list's or side list's option line as the a1 II draws it: on its orange bar where lit (else on black), its text
    letter strokes at `text_grey` (~120 greyed, ~225 white), a dark outline round them."""
    a = np.zeros((480, 640, 3), np.uint8)
    t, b = 236, 282
    x0 = 305 if kind == "sidelist" else 110
    if lit:
        a[t:b, x0 - 2:595] = (170, 51, 0)
    if ink:
        for x in range(x0 + 10, x0 + 160, 9):
            a[t + 12:b - 12, x - 1:x + 4] = 10                     # the outline
            a[t + 12:b - 12, x:x + 3] = text_grey
    return a, (t, b)


def grey_cam(a, bar, kind="sidelist"):
    return SimpleNamespace(frame=frame_of(a), read=lambda: SimpleNamespace(kind=kind, bar=bar))


@pytest.mark.parametrize("kind", ["sidelist", "list"])
@pytest.mark.parametrize("level, lit, want", [(120, True, True), (134, True, True), (225, True, False),
                                              (245, True, False), (120, False, True), (225, False, False),
                                              (170, True, None), (160, True, None), (185, True, None)])
def test_an_option_is_told_grey_or_white_by_the_greyed_rows_measure(kind, level, lit, want):
    from proving import screens as PS
    a, bar = option_line(level, kind, lit=lit)
    grey, p = PS.drawn_grey(grey_cam(a, bar, kind))
    assert grey is want and p is not None, (level, p)


def test_where_the_measure_cannot_read_an_option_it_says_nothing():
    from proving import screens as PS
    a, bar = option_line(225, ink=False)
    assert PS.drawn_grey(grey_cam(a, bar)) == (None, None), "no text on the line"
    assert PS.drawn_grey(grey_cam(a, None)) == (None, None), "no bar"
    assert PS.drawn_grey(grey_cam(a, bar, "dialog")) == (None, None), "a carousel with no red icon: not judged"
    assert PS.drawn_grey(SimpleNamespace(frame=frame_of(None), read=lambda: SimpleNamespace(kind="list", bar=bar))) \
        == (None, None)


PP4_HLG = {"260193_down.png": True, "260212_down.png": True, "260232_down.png": True, "260253_down.png": True,
           "260272_up.png": True, "260291_up.png": True, "260308_up.png": True, "260324_up.png": True,
           "260339_up.png": True, "260354_down.png": False, "260368_up.png": False}
# PP10's Color Mode in Movie mode with Gamma Movie: BT.2020 and 709 grey, the others white; Flash Sync Spd. Prty.'s On
# grey with Electronic Shutter, its Off white; Shading Comp.'s list, none grey
OTHERS = {"257814_down.png": True, "257831_down.png": True, "257693_down.png": False, "257848_down.png": False,
          "14373_down.png": True, "14389_up.png": False, "00011_down.png": False}


@pytest.mark.parametrize("name, grey", [*PP4_HLG.items(), *OTHERS.items()])
def test_the_cameras_options_are_told_grey_or_white(name, grey):
    """The frames the PP4 Color Mode run of 2026-11-19 chose each option on (nine drawn grey, two white), and the other
    lists of the runs (a side list with two grey, a list with one, a list with none)."""
    from proving import screens as PS
    f = load(need(A1 / "kit2_pass2" / "shots" / name))
    s = screen.read(f)
    assert PS.drawn_grey(SimpleNamespace(frame=f, read=lambda: s))[0] is grey, name


REFUSAL = "This operation or setting not available as follows Gamma HLG • OK"
COLOR = ["Movie", "Still", "S-Cinetone", "709", "BT.2020"]


class SideCam:
    """A Picture Profile side list (COLOR, saved on BT.2020) as prove_side_row meets it: Right opens it on the saved
    value, Down and Up move the cursor, Enter on an option in `refuse` brings the camera's refusal (MENU closes it, the
    value kept), any other Enter saves it and goes back to the row, MENU on the list goes back to the row; the options in
    `grey` are drawn grey (drawn_grey's answer, `unsure` none). C4 is the guide's (help_run.guide, faked)."""

    def __init__(self, grey=(0, 1, 2), refuse=(0, 1, 2), saved=4, unsure=()):
        self.grey, self.refuse, self.unsure = set(grey), set(refuse), set(unsure)
        self.where, self.option, self.saved, self.keys, self.n = "row", saved, saved, [], 1
        self.frame = SimpleNamespace(path=Path("00001_row.png"), image=None)

    def shoot(self, tag):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{tag}.png"), image=None)

    def press(self, key, **kw):
        self.keys.append(key)
        if key == "right":
            self.where, self.option = "list", self.saved
        elif key in ("down", "up") and self.where == "list":
            self.option = (self.option + (1 if key == "down" else -1)) % len(COLOR)
        elif key == "enter":
            if self.option in self.refuse:
                self.where = "notice"
            else:
                self.where, self.saved = "row", self.option
        elif key == "menu":
            self.where = "row"
        self.shoot(key)

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "sidelist", "notice": "notice"}[self.where], bar=(236, 282))


def side_world(monkeypatch, cam, help_text="Sets the color mode. This function is currently disabled.", help_ok=True):
    """prove_side_row's seams faked round `cam`; returns (run, its proof lines, what it printed, the guides asked for)."""
    import contextlib
    import io
    import json

    import drive as D
    import help_run
    from camkit.ocr import Line
    from proving import greyed, sidelists as SL
    guides = []

    def guide(c, label):
        guides.append((label, c.option))
        c.keys.append("c4")
        c.shoot("guide")
        return {"title": label, "text": help_text, "frames": [c.frame.path.name], "popup": False}
    monkeypatch.setattr(help_run, "guide", guide)
    monkeypatch.setattr(D, "help_refused", lambda kind, image: "" if help_ok else "the footer shows no help button")
    monkeypatch.setattr(greyed, "drawn_grey", lambda c: ((None, 170.0) if c.option in cam.unsure else
                                                         (c.option in cam.grey, 120.0 if c.option in cam.grey else 225.0))
                        if c.read().kind == "sidelist" else (None, None))
    monkeypatch.setattr(greyed, "REASONS", {})
    monkeypatch.setattr(greyed, "LABELS", {"Gamma", "Color Mode", "Black Level"})
    for name, value in (("place", lambda c: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("after_download", lambda c, done: None), ("side_index", lambda c, job: c.option),
                        ("side_text", lambda c: COLOR[c.option]), ("later", lambda read, c: COLOR[c.option]),
                        ("settled", lambda v: v)):
        monkeypatch.setattr(SL, name, value)
    monkeypatch.setattr(SL.ocr, "read", lambda paths: {p: [Line(REFUSAL, 1.0, 0, 200, 600, 40)] if cam.where == "notice"
                                                       else [] for p in paths})
    state = {"saved": cam.saved}
    monkeypatch.setattr(SL.camset, "read", lambda p: {"global:0x073b": state["saved"]} if p else {})
    monkeypatch.setattr(SL.camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a[k], after=b[k])
                                                         for k in a if a[k] != b[k]])

    def download(tag):
        state["saved"] = cam.saved
        return Path(f"{tag}.DAT")
    out, said = io.StringIO(), io.StringIO()
    job = {"path": ["Picture Profile", "PP4", "Color Mode"], "values": COLOR, "plan": list(range(len(COLOR)))}
    with contextlib.redirect_stdout(said):
        SL.prove_side_row(cam, SimpleNamespace(download=download), None, job, Path("start.DAT"), out)
    return [json.loads(x) for x in out.getvalue().splitlines()], said.getvalue(), guides


def by_label(lines):
    return {x["label"]: x for x in lines}


def test_a_side_lists_grey_options_get_help_once_one_enter_for_the_reason_and_no_key_after(monkeypatch):
    """PP4's Color Mode with Gamma on HLG, as this morning: the first grey option (Movie) gets the camera's Help, which
    says only that it is disabled, then the row's one Enter, to read the notice (Gamma); Still and S-Cinetone get no key
    at all, written greyed as drawn with that reason, no download, no diff; 709 and BT.2020 are proved as before."""
    cam = SideCam()
    lines, said, guides = side_world(monkeypatch, cam)
    assert guides == [("Picture Profile > PP4 > Color Mode: Movie", 0)]
    assert cam.keys.count("enter") == 3 and cam.keys.count("c4") == 1
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert entered == ["Movie", "709", "BT.2020"], cam.keys
    got = by_label(lines)
    movie = got["Movie"]
    assert (movie["applied"], movie["changes"], movie["greyed"], movie["entered"]) == (False, [], "drawn", "for its reason")
    assert movie["blocker"] == {"row": "Gamma"} and movie["reason"]["from"] == "notice" and movie["notice"]["text"]
    for label in ("Still", "S-Cinetone"):
        x = got[label]
        assert (x["applied"], x["changes"], x["dat"], x["notice"], x["greyed"]) == (False, [], None, None, "drawn")
        assert x["blocker"] == {"row": "Gamma"} and x["reason"] == {"from": "notice", "frame": movie["reason"]["frame"],
                                                                     "entry": "Movie"}
        assert "entered" not in x
    assert got["709"]["applied"] and got["709"]["changes"] and "greyed" not in got["709"]
    assert got["BT.2020"]["applied"] and got["BT.2020"]["changes"] == []
    assert "the one Enter of this row on an option drawn grey, to read why it is greyed, not to choose" in said
    assert "'Still'                  greyed as drawn, never entered: blocked by Gamma (the camera's notice on 'Movie'" in said
    assert "applied ['709', 'BT.2020']; greyed as drawn, never entered ['Still', 'S-Cinetone']; entered once to read why: ['Movie']" in said


def enter_options(cam):
    """The option the cursor was on at each key the camera got, replayed from its keys (SideCam's own moves)."""
    out, where, option, saved = [], "row", 4, 4
    for k in cam.keys:
        out.append(option)
        if k == "right":
            where, option = "list", saved
        elif k in ("down", "up") and where == "list":
            option = (option + (1 if k == "down" else -1)) % len(COLOR)
        elif k == "enter":
            if option in cam.refuse:
                where = "notice"
            else:
                where, saved = "row", option
        elif k == "menu":
            where = "row"
    return out


def test_never_enter_grey_presses_no_enter_on_any_grey_option(monkeypatch):
    from proving import greyed
    monkeypatch.setattr(greyed, "NEVER_ENTER", True)
    cam = SideCam()
    lines, said, guides = side_world(monkeypatch, cam)
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert entered == ["709", "BT.2020"] and len(guides) == 1
    got = by_label(lines)
    for label in ("Movie", "Still", "S-Cinetone"):
        assert (got[label]["greyed"], got[label]["applied"], got[label]["dat"]) == ("drawn", False, None), label
        assert "blocker" not in got[label] and got[label]["reason"]["from"] == "help", label
    assert "--never-enter-grey: no Enter on it" in said


def test_help_that_names_the_blocker_spares_every_enter(monkeypatch):
    cam = SideCam()
    lines, said, guides = side_world(monkeypatch, cam, help_text=REFUSAL)
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert entered == ["709", "BT.2020"]
    assert all(by_label(lines)[x]["blocker"] == {"row": "Gamma"} and by_label(lines)[x]["reason"]["from"] == "help"
               for x in ("Movie", "Still", "S-Cinetone"))
    assert "why greyed: blocked by Gamma (the camera's Help on 'Movie'" in said


def test_a_help_description_naming_equipment_or_rows_is_no_blocker():
    from proving import greyed
    for text in ("Assigns functions to the function ring of the lens. This function is currently disabled.",
                 "Sets the Gamma and the Black Level of the flash. This function is currently disabled.", ""):
        assert greyed.help_blocker(text) is None, text


def test_where_help_is_not_allowed_the_one_enter_reads_the_reason(monkeypatch):
    cam = SideCam()
    lines, said, guides = side_world(monkeypatch, cam, help_ok=False)
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert guides == [] and "c4" not in cam.keys and entered == ["Movie", "709", "BT.2020"]
    assert "no Help on it (the footer shows no help button)" in said


def test_a_grey_option_the_camera_applies_was_misjudged_and_the_rows_others_are_entered(monkeypatch):
    cam = SideCam(refuse=())
    lines, said, guides = side_world(monkeypatch, cam)
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert entered == COLOR, "every option entered: the drawing was misjudged"
    assert all(x["applied"] and "greyed" not in x for x in lines)
    assert "was drawn grey, yet the camera applied it" in said


def test_a_second_visit_to_the_row_in_the_run_tries_nothing_again(monkeypatch):
    from proving import greyed
    cam = SideCam()
    side_world(monkeypatch, cam)
    kept = dict(greyed.REASONS)
    cam2 = SideCam()
    monkeypatch.setattr(greyed, "REASONS", kept)
    import proving.sidelists as SL
    import contextlib
    import io
    job = {"path": ["Picture Profile", "PP4", "Color Mode"], "values": COLOR, "plan": list(range(len(COLOR)))}
    monkeypatch.setattr(SL.ocr, "read", lambda paths: {p: [] for p in paths})
    with contextlib.redirect_stdout(io.StringIO()):
        SL.prove_side_row(cam2, SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")), None, job, Path("s.DAT"),
                          io.StringIO())
    entered = [COLOR[o] for o, k in zip(enter_options(cam2), cam2.keys, strict=False) if k == "enter"]
    assert entered == ["709", "BT.2020"] and "c4" not in cam2.keys


def test_the_rows_one_enter_is_spent_even_where_what_follows_it_fails(monkeypatch):
    """The row's one Enter is counted as it is decided: should the row fail after it (a question, a lost row), a later
    visit to the row in the run tries no second Enter and no second Help."""
    from proving import greyed
    monkeypatch.setattr(greyed, "REASONS", {})
    monkeypatch.setattr(greyed, "drawn_grey", lambda c: (True, 120.0))
    helps = []
    monkeypatch.setattr(greyed, "by_help", lambda cam, name, label, back: helps.append(label) or
                        greyed.Reason(None, "help", "00002_guide.png", label))
    cam = SimpleNamespace()
    said = []
    assert greyed.judge(cam, "Row", "A", 0, 3, None, say=said.append) == greyed.TRY
    assert greyed.judge(cam, "Row", "B", 1, 3, None, say=said.append) == greyed.SKIP and helps == ["A"]


def test_the_saved_value_drawn_grey_is_still_its_put_back_and_an_unsure_drawing_is_entered(monkeypatch):
    cam = SideCam(grey=(0, 4), refuse=(0,), unsure=(1,))
    lines, said, guides = side_world(monkeypatch, cam)
    entered = [COLOR[o] for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter"]
    assert entered == ["Movie", "Still", "S-Cinetone", "709", "BT.2020"]
    assert "'BT.2020': drawn grey, but it is the value the row was saved on: entered as its put-back" in said
    assert "'Still': whether it is drawn grey cannot be told (its text reads 170): entered as before" in said


SHUTTER = ["Auto", "On", "Off"]
SYNC_REFUSAL = "This operation or setting not available as follows Shutter Type Electronic Shutter • OK"


class ListCam(SideCam):
    """A list (SHUTTER, saved on Auto) as prove_row meets it: Flash Sync Spd. Prty. with the electronic shutter, On drawn
    grey and refused."""

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "list", "notice": "notice"}[self.where], bar=(145, 191))

    def press(self, key, **kw):
        self.keys.append(key)
        if key == "right":
            self.where, self.option = "list", self.saved
        elif key in ("down", "up") and self.where == "list":
            self.option = (self.option + (1 if key == "down" else -1)) % len(SHUTTER)
        elif key == "enter":
            if self.option in self.refuse:
                self.where = "notice"
            else:
                self.where, self.saved = "row", self.option
        elif key == "menu":
            self.where = "row"
        self.shoot(key)


def list_world(monkeypatch, cam, help_text="Gives priority to the flash sync speed. This function is currently disabled.",
               kind="list"):
    import contextlib
    import io
    import json

    import drive as D
    import help_run
    import prove_run as P
    from camkit import ocr as O
    from camkit.ocr import Line
    from camkit.runs import Run
    from proving import greyed
    guides = []

    def guide(c, label):
        guides.append(label)
        c.keys.append("c4")
        c.shoot("guide")
        return {"text": help_text, "frames": [c.frame.path.name]}
    monkeypatch.setattr(help_run, "guide", guide)
    monkeypatch.setattr(D, "help_refused", lambda kind, image: "")
    monkeypatch.setattr(greyed, "drawn_grey", lambda c: (c.option in cam.grey, 120.0) if c.read().kind == "list"
                        else getattr(cam, "icon", {}).get(c.option, (None, None)))    # a carousel's lit icon
    monkeypatch.setattr(greyed, "REASONS", {})
    monkeypatch.setattr(greyed, "LABELS", {"Shutter Type", "Flash Mode"})
    for name, value in (("place", lambda c: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("which_option", lambda c, job: c.option), ("vlm_option", lambda c: SHUTTER[c.option]),
                        ("bar_text", lambda c: SHUTTER[c.option]), ("after_download", lambda c, done: None),
                        ("finish_attempt", lambda *a, **k: None)):
        monkeypatch.setattr(P, name, value)
    monkeypatch.setattr(O, "read", lambda frames, eng=None: {f: [Line(SYNC_REFUSAL, 0.9, 0, 0, 10, 10)]
                                                            if cam.where == "notice" else [] for f in frames})
    monkeypatch.setattr(P.camset, "read", lambda p: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [])
    out, said = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(said):
        P.prove_row(cam, SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")), Run("pass2", root=Path(".")),
                    {"path": ["Flash Sync Spd. Prty."], "kind": kind, "labels": SHUTTER}, Path("base.DAT"), out)
    return [json.loads(x) for x in out.getvalue().splitlines()], said.getvalue(), guides


def test_the_list_prover_reads_the_reason_of_its_rows_first_grey_option_once(monkeypatch, tmp_path):
    """prove_row: On drawn grey, Help names no reason, the row's one Enter reads Shutter Type from the notice; the line
    says not applied, greyed as drawn, entered for its reason, no diff; Off and the put-back Auto proved as before."""
    monkeypatch.chdir(tmp_path)
    cam = ListCam(grey=(1,), refuse=(1,), saved=0)
    lines, said, guides = list_world(monkeypatch, cam)
    on = by_label(lines)["On"]
    assert (on["applied"], on["changes"], on["greyed"], on["entered"], on["blocker"]) == (
        False, [], "drawn", "for its reason", {"row": "Shutter Type"})
    assert guides == ["Flash Sync Spd. Prty.: On"] and cam.keys.count("enter") == 3
    assert "entered once to read why: ['On']; blocked by Shutter Type (the camera's notice on 'On'" in said


def test_the_list_prover_presses_nothing_on_a_grey_option_once_its_rows_reason_is_known(monkeypatch, tmp_path):
    from proving import greyed
    monkeypatch.chdir(tmp_path)
    cam = ListCam(grey=(1,), refuse=(1,), saved=0)
    lines, said, guides = list_world(monkeypatch, cam)
    kept = dict(greyed.REASONS)
    cam2 = ListCam(grey=(1,), refuse=(1,), saved=0)
    import contextlib
    import io
    import json

    import prove_run as P
    from camkit.runs import Run
    monkeypatch.setattr(greyed, "REASONS", kept)
    out = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()):
        P.prove_row(cam2, SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")), Run("pass2", root=Path(".")),
                    {"path": ["Flash Sync Spd. Prty."], "kind": "list", "labels": SHUTTER}, Path("base.DAT"), out)
    on = by_label([json.loads(x) for x in out.getvalue().splitlines()])["On"]
    assert on["greyed"] == "drawn" and on["dat"] is None and "entered" not in on and on["blocker"] == {"row": "Shutter Type"}
    assert cam2.keys.count("enter") == 2 and "c4" not in cam2.keys


def test_a_refused_line_carries_no_diff_that_is_another_options(monkeypatch):
    """Movie mode, PP10, Gamma Movie (kit2_pass2 9010-9011, 8459-8460): BT.2020 and 709 refused after S-Gamut3 applied;
    their lines say not applied and carry no diff, though the record still differs from the row's base."""
    cam = SideCam(grey=(), refuse=(3,), saved=0)
    lines, said, guides = side_world(monkeypatch, cam)
    got = by_label(lines)
    assert got["Still"]["changes"] and got["709"]["applied"] is False and got["709"]["changes"] == []
    assert "'709'                    not applied" in said


# ------------------------------------------- 13b. the reader says which option is grey too, and only adds care (2026-11-19)

# The reader's flag given outright on a side list (proving.greyed.reader_grey faked), to hold judge's rule for two
# eyes; the whole-list answers that give it in a run (proving.greyed.Flags) have tests of their own below
OUTRIGHT = ("sidelist",)


def said_by_reader(monkeypatch, cam, said, kinds=("dialog",)):
    """The second reader's "greyed" faked round cam (proving.greyed.reader_grey): said, {option: True, False or None};
    an option it does not name gets no answer; on a kind of screen not in kinds (a carousel's alone, as in a run;
    OUTRIGHT for judge's two-eye rule), no question."""
    from proving import greyed
    asked = []

    def reader_grey(c, **kw):
        if c.read().kind not in kinds:
            return None, {}
        asked.append(c.option)
        got = said.get(c.option)
        return got, {"question": "lit.v2.grey", "reader_name": "fake", **({"why": "no answer"} if got is None else {})}
    monkeypatch.setattr(greyed, "reader_grey", reader_grey)
    return asked


def enters_on(cam, options):
    """How many Enters the camera got on each option of `options` (SideCam's keys replayed)."""
    return sum(1 for o, k in zip(enter_options(cam), cam.keys, strict=False) if k == "enter" and o in options)


@pytest.mark.parametrize("pixels, level, reader, grey, told", [
    (True, 120.0, True, True, "both"), (True, 120.0, False, True, "pixels"), (True, 120.0, None, True, "pixels"),
    (False, 225.0, True, True, "reader"), (False, 225.0, False, False, None), (False, 225.0, None, False, None),
    (None, 170.0, True, True, "reader"), (None, 170.0, False, False, None), (None, 170.0, None, False, None),
    (None, None, True, True, "reader"), (None, None, False, False, None), (None, None, None, False, None)])
def test_either_eye_saying_grey_makes_an_option_grey_and_the_reader_decides_where_the_pixels_cannot_tell(
        monkeypatch, pixels, level, reader, grey, told):
    """judge on one option of a row with nothing read yet: grey (never entered to choose it: Help first) where either
    eye says grey, told by those that did; where the pixels cannot tell (a measure in between, or a carousel's, not
    judged), the reader's answer decides; no answer from the reader leaves the pixels' rule as it was."""
    from proving import greyed
    monkeypatch.setattr(greyed, "REASONS", {})
    helps = []
    monkeypatch.setattr(greyed, "by_help", lambda cam, name, label, back: helps.append(label) or
                        greyed.Reason({"row": "Gamma"}, "help", "00002_guide.png", label))
    d = greyed.Drawing(pixels, level, reader, {"question": "lit.v2.grey"})
    said = []
    what = greyed.judge(SimpleNamespace(), "Row", "A", 0, 3, None, say=said.append, drawn=d)
    assert (what == greyed.SKIP, what.told, bool(helps)) == (grey, told, grey), (what, said)
    assert what == (greyed.SKIP if grey else greyed.ENTER) and what.drawing is d
    if grey:
        assert greyed.line({"label": "A", "chosen_frame": "00001_x.png"}, greyed.REASONS["Row"], what)["greyed_by"] == told
    assert greyed.readings(what) == {"grey_readings": {"pixels": pixels, **({"level": level} if level else {}),
                                                       "reader": reader, "question": "lit.v2.grey"}}


@pytest.mark.parametrize("pixels, k, known, asked", [
    (False, 0, None, True), (None, 0, None, True),                   # white or untold: the reader's grey decides
    (True, 0, None, False),                                          # the pixels' grey stands whatever is said
    (False, 3, None, False), (True, 3, None, False),                 # the saved value: its put-back whatever is said
    (False, 0, "reader", False), (True, 0, "reader", False),         # the reader misjudged this row: not heard
    (True, 0, "pixels", True), (False, 0, "pixels", True),           # the pixels misjudged it: the reader decides
    (False, 0, "reason", True)])                                     # a reason read: grey is no key, white an Enter
def test_the_reader_is_asked_only_where_its_answer_can_change_what_is_pressed(monkeypatch, pixels, k, known, asked):
    """proving.greyed.judge asks the second reader, in line, only where its answer can change what the option gets; where
    it does not, the line says why ("not_asked") and that the pixels alone told it."""
    from proving import greyed
    reasons = {None: {}, "reader": {"Row": greyed.Misjudged(frozenset({"reader"}))},
               "pixels": {"Row": greyed.Misjudged(frozenset({"pixels"}))},
               "reason": {"Row": greyed.Reason({"row": "Gamma"}, "help", "00002_guide.png", "B")}}[known]
    monkeypatch.setattr(greyed, "REASONS", dict(reasons))
    monkeypatch.setattr(greyed, "drawn_grey", lambda cam: (pixels, 120.0 if pixels else 225.0 if pixels is False
                                                           else 170.0))
    calls = []
    monkeypatch.setattr(greyed, "reader_grey", lambda cam, **kw: calls.append(1) or (True, {"question": "lit.v2.grey"}))
    monkeypatch.setattr(greyed, "by_help", lambda cam, name, label, back: greyed.Reason({"row": "Gamma"}, "help",
                                                                                        "00003_guide.png", label))
    what = greyed.judge(SimpleNamespace(), "Row", "A", k, 3, None, say=lambda m: None)
    assert bool(calls) is asked
    kept = greyed.readings(what)["grey_readings"]
    assert ("not_asked" in kept) is (not asked) and (kept["reader"] is None) is (not asked)
    if not asked and what.told:
        assert what.told == "pixels"
    assert greyed.unasked(k, 3, greyed._deaf(reasons.get("Row")), pixels) == kept.get("not_asked", "")


class GreyPool:
    """proving.greyed's grey worker faked: each whole-list question answered at once, or never (late: the answer still
    out when every option is judged); the frames asked about recorded."""

    def __init__(self, late=False):
        self.late, self.asked, self.looked = late, [], []      # looked: the option the cursor was on, a question each

    def submit(self, fn, *a):
        from concurrent.futures import Future
        f = Future()
        self.asked.append(a[0].path.name)
        if not self.late:
            f.set_result(fn(*a))
        return f


def listen_world(monkeypatch, answer, window=None, late=False):
    """proving.greyed's whole-list seams faked round a list: band_options gives window(cam) (the options OCR names on
    the bands on show; default every option of COLOR), ask_entries the second reader's answer, answer(the window asked
    about) (a dict, or None for no answer). Returns the worker (its frames asked about)."""
    from camkit import reading
    from proving import greyed
    shown = {}

    def bands(cam, labels):
        w = list(window(cam)) if window else list(range(len(labels)))
        shown[cam.frame.path.name] = w
        pool.looked.append(getattr(cam, "option", None))
        return w

    def ask(frame):
        got = answer(shown[frame.path.name])
        return reading.Asked(got, "fake second", "fake-model", "" if got is not None else "no answer")
    pool = GreyPool(late)
    monkeypatch.setattr(greyed, "band_options", bands)
    monkeypatch.setattr(greyed, "ask_entries", ask)
    monkeypatch.setattr(greyed, "_pool", lambda: pool)
    return pool


def entries_of(labels, grey=(), skip=(), twice=()):
    """A whole-list answer listing labels[j] for each j of a window: "greyed" true for those in grey; skip left out,
    twice listed twice."""
    def answer(window):
        out = []
        for j in window:
            if j in skip:
                continue
            out += [{"label": labels[j], "greyed": j in grey, "highlighted": False}] * (2 if j in twice else 1)
        return {"entries": out}
    return answer


def test_a_side_list_asks_its_whole_list_once_and_a_grey_flag_beside_white_pixels_keeps_it_unchosen(monkeypatch):
    """PP4's Color Mode, Still and S-Cinetone grey by their pixels and Movie by the second reader's whole-list flag
    alone: one question for the row's visit (its five options on one screenful), Movie gets the camera's Help and the
    row's one Enter for the reason, never one to choose it, and Still and S-Cinetone then no key; each line keeps the
    reader's flag, the question and the frame it was asked on."""
    alone = SideCam(grey=(1, 2), refuse=(0, 1, 2))
    listen_world(monkeypatch, lambda w: None)
    side_world(monkeypatch, alone)
    cam = SideCam(grey=(1, 2), refuse=(0, 1, 2))
    pool = listen_world(monkeypatch, entries_of(COLOR, grey={0, 1, 2}))
    lines, said, guides = side_world(monkeypatch, cam)
    got = by_label(lines)
    assert len(pool.asked) == 1 and guides == [("Picture Profile > PP4 > Color Mode: Movie", 0)]
    assert enters_on(cam, {1, 2}) == 0 < enters_on(alone, {1, 2}) and enters_on(cam, {0}) == 1
    assert (got["Movie"]["greyed_by"], got["Movie"]["entered"], got["Movie"]["applied"]) == ("reader", "for its reason",
                                                                                           False)
    assert got["Movie"]["grey_readings"] == {"pixels": False, "level": 225.0, "reader": True, "question": "entries.v2",
                                             "asked_on": pool.asked[0], "read": "Movie", "reader_name": "fake second"}
    assert got["709"]["grey_readings"]["reader"] is False and got["709"]["applied"]
    assert got["Still"]["grey_readings"]["not_asked"] == "the pixels tell it grey, which no answer changes"


@pytest.mark.parametrize("variant", ["late", "none", "empty", "garbled", "short", "long", "unknown labels",
                                     "twice", "not listed", "flags not true or false"])
def test_a_late_empty_garbled_or_wrong_length_answer_changes_nothing(monkeypatch, variant):
    """The whole-list answer that cannot be trusted for an option gives it no flag: the camera gets exactly the keys of
    the pixels alone (no answer at all), whatever the answer would have said."""
    alone = SideCam(grey=(1,), refuse=(0, 1, 3))
    listen_world(monkeypatch, lambda w: None)
    side_world(monkeypatch, alone)
    all_grey = set(range(len(COLOR)))
    answer = {"late": entries_of(COLOR, grey=all_grey), "none": lambda w: None, "empty": lambda w: {"entries": []},
              "garbled": lambda w: {"selected": "Movie", "greyed": True},
              "short": entries_of(COLOR, grey=all_grey, skip={4}),
              "long": lambda w: {"entries": entries_of(COLOR, grey=all_grey)(w)["entries"] + [{"label": "Movie",
                                                                                             "greyed": True}]},
              "unknown labels": lambda w: {"entries": [{"label": f"Zqx {j}", "greyed": True} for j in w]},
              "twice": lambda w: {"entries": [{"label": "Movie", "greyed": True}] * len(w)},
              "not listed": lambda w: {"entries": [{"label": "BT.2020", "greyed": True}] + [
                  {"label": f"Zqx {j}", "greyed": True} for j in w[1:]]},
              "flags not true or false": lambda w: {"entries": [{"label": COLOR[j], "greyed": "maybe"} for j in w]}}
    cam = SideCam(grey=(1,), refuse=(0, 1, 3))
    listen_world(monkeypatch, answer[variant], late=variant == "late")
    lines, said, guides = side_world(monkeypatch, cam)
    assert cam.keys == alone.keys, variant
    for x in lines:
        if x["label"] not in ("Still", "BT.2020"):      # Still: the pixels' grey; BT.2020: the put-back
            assert x["grey_readings"]["reader"] is None and x["grey_readings"]["why"], (variant, x)
        assert x.get("greyed_by") in (None, "pixels"), (variant, x)


@pytest.mark.parametrize("pixels", [(), (0,), (1, 2), (0, 2, 3)])
@pytest.mark.parametrize("reader", [(), (0,), (3,), (0, 1, 2, 3), (2, 3)])
@pytest.mark.parametrize("refuse", ["pixels", "both", "none"])
def test_the_whole_list_answer_never_causes_an_enter_or_a_right_the_pixels_alone_would_not(monkeypatch, pixels, reader,
                                                                                         refuse):
    """Whatever the whole-list flags say and whatever the camera refuses, no option gets more Enters than with the
    pixels alone, the row no more Rights, and an option only the reader calls grey at most the row's one Enter for its
    reason, but where the reader misjudged the row."""
    pixel_grey, reader_grey = set(pixels), set(reader)
    refused = {"pixels": pixel_grey, "both": pixel_grey | reader_grey, "none": set()}[refuse]
    alone = SideCam(grey=pixel_grey, refuse=refused)
    listen_world(monkeypatch, lambda w: None)
    side_world(monkeypatch, alone)
    cam = SideCam(grey=pixel_grey, refuse=refused)
    listen_world(monkeypatch, entries_of(COLOR, grey=reader_grey))
    lines, said, guides = side_world(monkeypatch, cam)
    for o in range(len(COLOR)):
        assert enters_on(cam, {o}) <= enters_on(alone, {o}), (o, cam.keys, alone.keys)
    assert cam.keys.count("right") <= alone.keys.count("right") and cam.keys.count("enter") <= alone.keys.count("enter")


@pytest.mark.parametrize("answer, grey", [(entries_of(COLOR, grey={1}), True), (entries_of(COLOR), False),
                                          (lambda w: None, False), (entries_of(COLOR, grey={1}, skip={1}), False)])
def test_where_the_pixels_cannot_tell_the_whole_list_flag_is_waited_for_and_taken(monkeypatch, answer, grey):
    """Still's text measures 170: the row's whole-list answer is waited for and its flag taken; no answer, or Still not
    listed, enters it as before."""
    cam = SideCam(grey=(), refuse=(1,), unsure=(1,))
    listen_world(monkeypatch, answer)
    lines, said, guides = side_world(monkeypatch, cam)
    still = by_label(lines)["Still"]
    assert (still.get("greyed_by") == "reader") is grey and (still["grey_readings"]["reader"] is True) is grey


def test_an_answer_still_out_where_the_pixels_cannot_tell_is_waited_for_a_presss_time_then_entered(monkeypatch):
    from camkit import reading
    monkeypatch.setitem(reading.TIMEOUTS, "press", 0.05)
    cam = SideCam(grey=(), refuse=(), unsure=(1,))
    listen_world(monkeypatch, entries_of(COLOR, grey={1}), late=True)
    lines, said, guides = side_world(monkeypatch, cam)
    still = by_label(lines)["Still"]
    assert still["applied"] and still["grey_readings"]["why"] == "the answer was not in yet"


class Visit(SimpleNamespace):
    """A cursor resting on option k of a long side list, its frame a name of its own."""


@pytest.mark.parametrize("window, asks", [
    (lambda k: range(k // 6 * 6, k // 6 * 6 + 6), 3),             # a list that pages: once a screenful
    (lambda k: range(max(0, min(k - 3, 12)), max(0, min(k - 3, 12)) + 6), 5),  # cursor kept on band 3: once in 3
    (lambda k: range(max(0, k - 5), max(0, k - 5) + 6), 13)])     # cursor on the bottom band: once an option past it
def test_a_list_that_scrolls_asks_once_where_the_cursor_reaches_an_option_no_screenful_asked_showed(monkeypatch, window,
                                                                                                  asks):
    """proving.greyed.Flags on an 18-option list visited option by option: a question about the screenful on show only
    where the cursor's option is on no screenful asked yet, never twice about one frame."""
    from camkit import reading
    from proving import greyed
    labels = [f"Zqx {j}" for j in range(18)]
    pool = GreyPool()
    monkeypatch.setattr(greyed, "_pool", lambda: pool)
    shown = {}
    monkeypatch.setattr(greyed, "band_options", lambda cam, labs: shown.setdefault(cam.frame.path.name,
                                                                                    list(window(cam.k))))
    monkeypatch.setattr(greyed, "ask_entries", lambda frame: reading.Asked(
        entries_of(labels)(shown[frame.path.name]), "fake second", "m", ""))
    flags = greyed.Flags(labels)
    for k in range(18):
        cam = Visit(k=k, frame=SimpleNamespace(path=Path(f"{k:05d}_down.png"), image=None))
        flags.look(cam, k)
        flags.look(cam, k)                                       # the same frame: never asked twice
    assert len(pool.asked) == asks
    assert all(flags.flag(k)[0] is False for k in range(18))     # every option flagged white, by its label


def test_no_whole_list_question_goes_out_where_its_answer_could_not_be_taken(monkeypatch):
    """PP4's Color Mode with Movie, Still and S-Cinetone grey by their pixels and BT.2020 the saved value: the one
    question of the row is asked on 709's frame, the first option whose flag could change what it gets; none on the
    open list (the saved value), the pixel-grey options or the put-back."""
    cam = SideCam(grey=(0, 1, 2), refuse=(0, 1, 2))
    pool = listen_world(monkeypatch, entries_of(COLOR))
    side_world(monkeypatch, cam)
    assert pool.looked == [3] and len(pool.asked) == 1


def test_a_rows_questions_not_started_are_dropped_when_it_ends_however_it_ends(monkeypatch, tmp_path):
    """proving.greyed.Flags.close, from a finally in prove_row and prove_side_row: a question still queued is
    cancelled when the row ends, and when it fails."""
    import prove_run as P
    from proving import greyed, sidelists as SL
    closed = []
    real_close = greyed.Flags.close
    monkeypatch.setattr(greyed.Flags, "close", lambda self: closed.append(self) or real_close(self))
    pool = listen_world(monkeypatch, entries_of(COLOR), late=True)
    side_world(monkeypatch, SideCam(grey=(), refuse=()))
    assert len(closed) == 1 and pool.asked and all(a.future.cancelled() for a in closed[0].asks)
    stuck = SideCam(grey=(), refuse=())
    stuck.read = lambda: SimpleNamespace(kind="submenu", bar=(236, 282))     # Right opens no side list: the row fails
    job = {"path": ["Picture Profile", "PP4", "Color Mode"], "values": COLOR, "plan": list(range(len(COLOR)))}
    with pytest.raises(P.Failed):
        SL.prove_side_row(stuck, SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")), None, job, Path("s.DAT"),
                          io.StringIO())
    assert len(closed) == 2
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(P, "place", lambda c: "here")
    monkeypatch.setattr(P, "which_option", lambda c, job: None)              # the list row fails too
    with pytest.raises(P.Failed):
        P.prove_row(ListCam(grey=(), refuse=()), SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")),
                    SimpleNamespace(dir=Path("pass2")), {"path": ["Flash Sync Spd. Prty."], "kind": "list",
                                                        "labels": SHUTTER}, Path("base.DAT"), io.StringIO())
    assert len(closed) == 3


def test_closing_a_rows_flags_leaves_the_grey_worker_only_the_question_it_is_asking(monkeypatch):
    """On the real worker: three questions queued behind a slow one; closing the row cancels the three, so that the
    next row's first question, and a run's end, wait for the slow one alone."""
    import threading

    from camkit import reading
    from proving import greyed
    gate = threading.Event()

    def slow(frame):
        gate.wait(5)
        return reading.Asked({"entries": []}, "fake second", "m", "")
    monkeypatch.setattr(greyed, "ask_entries", slow)
    monkeypatch.setattr(greyed, "band_options", lambda cam, labels: [cam.k])
    flags = greyed.Flags([f"Zqx {j}" for j in range(4)])
    for k in range(4):
        flags.look(Visit(k=k, frame=SimpleNamespace(path=Path(f"{k:05d}_down.png"), image=None)), k)
    flags.close()
    gate.set()
    first, *queued = [a.future for a in flags.asks]
    assert all(f.cancelled() for f in queued) and not first.cancelled()
    assert first.result(timeout=5).answer == {"entries": []}


@pytest.mark.parametrize("answered_by, taken", [("RedHatAI/Qwen3.8-27B-INT4", True), ("Qwen3.8-27B-4bit", True),
                                                 ("glm-4.6v-flash", False), ("google/gemma-4-26b", False),
                                                 (None, True)])
def test_an_answer_under_the_second_readers_name_from_another_model_family_is_dropped(monkeypatch, answered_by, taken):
    """A server that answers the second reader's name with another family's model (camkit.reading.model_id) gives no
    flag, on a list as on a carousel; another build of the second's own model does."""
    from camkit import vlm
    from proving import greyed
    monkeypatch.setattr(vlm, "role", lambda name: {"name": "qwen", "model": "Qwen3.8-27B"})
    monkeypatch.setattr(vlm, "standing_in", lambda name: None)
    answer = {"entries": [{"label": "Movie", "greyed": True}], "selected": "ISO 100", "greyed": True}
    monkeypatch.setattr(greyed.reading, "ask", lambda frame, prompt, timeout, role="second":
                        greyed.reading.Asked(answer, "qwen", answered_by, ""))
    got = greyed.ask_entries(SimpleNamespace(path=Path("00001_down.png"), image=None))
    assert (got.answer is not None) is taken and (got.why == greyed.NO_STAND_IN) is (not taken)
    cam = SimpleNamespace(frame=SimpleNamespace(path=Path("00002_right.png"), image=None),
                          read=lambda: SimpleNamespace(kind="dialog"))
    said, kept = greyed.reader_grey(cam)
    assert (said is True) is taken and (kept.get("why") == greyed.NO_STAND_IN) is (not taken)


def test_a_reader_standing_in_for_the_second_is_never_asked_about_grey(monkeypatch):
    from camkit import vlm
    from proving import greyed
    monkeypatch.setattr(vlm, "role", lambda name: {"name": "qwen"})
    monkeypatch.setattr(vlm, "standing_in", lambda name: {"name": "glm"})
    monkeypatch.setattr(greyed.reading, "ask", lambda *a, **k: pytest.fail("a stand-in was asked"))
    got = greyed.ask_entries(SimpleNamespace(path=Path("00001_down.png"), image=None))
    assert got.answer is None and got.why == greyed.NO_STAND_IN
    cam = SimpleNamespace(frame=SimpleNamespace(path=Path("00002_right.png"), image=None),
                          read=lambda: SimpleNamespace(kind="dialog"))
    assert greyed.reader_grey(cam) == (None, {"not_asked": greyed.NO_STAND_IN})
    monkeypatch.setattr(vlm, "standing_in", lambda name: None)
    monkeypatch.setattr(greyed.reading, "ask", lambda frame, prompt, timeout, role="second":
                        greyed.reading.Asked({"entries": []}, "glm", "glm-model", ""))    # answered by another
    assert greyed.ask_entries(SimpleNamespace(path=Path("00003_down.png"), image=None)).why == greyed.NO_STAND_IN


def test_a_reader_calling_grey_options_white_presses_nothing_the_pixels_alone_would_not(monkeypatch):
    """judge's two-eye rule (the reader's answer given outright): PP4's Color Mode with Gamma on HLG, the reader reading
    every option white (or giving no answer): the camera gets exactly the keys it gets with no reader at all, and every
    grey line says the pixels told it."""
    alone = SideCam()
    lines0, _, _ = side_world(monkeypatch, alone)
    for answer in (False, None):
        cam = SideCam()
        asked = said_by_reader(monkeypatch, cam, dict.fromkeys(range(len(COLOR)), answer), OUTRIGHT)
        lines, said, guides = side_world(monkeypatch, cam)
        assert cam.keys == alone.keys, answer
        assert [x["label"] for x in lines] == [x["label"] for x in lines0]
        grey = [x for x in lines if x.get("greyed") == "drawn"]
        assert len(grey) == 3 and all(x["greyed_by"] == "pixels" for x in grey), grey
        # asked only about 709, where its answer could change what is pressed: never on the options the pixels call
        # grey, nor on BT.2020, the value the row was saved on
        assert sorted(set(asked)) == [3], asked
        got = by_label(lines)
        assert got["709"]["grey_readings"]["reader"] is answer and "not_asked" not in got["709"]["grey_readings"]
        for x in (*grey, got["BT.2020"]):
            assert x["grey_readings"]["reader"] is None and x["grey_readings"]["not_asked"], x["label"]


def test_an_option_only_the_reader_calls_grey_is_never_chosen(monkeypatch):
    """Movie drawn white by its pixels, the reader calling it grey, and the camera refusing it: the row's first grey
    option it is, so it gets the camera's Help and the row's one Enter, to read why, never an Enter to choose it; Still
    and S-Cinetone, drawn grey, get no key at all once that reason is read (with no reader, Still took the Enter)."""
    alone = SideCam(grey=(1, 2), refuse=(0, 1, 2))
    side_world(monkeypatch, alone)
    cam = SideCam(grey=(1, 2), refuse=(0, 1, 2))
    said_by_reader(monkeypatch, cam, {0: True}, OUTRIGHT)
    lines, said, guides = side_world(monkeypatch, cam)
    got = by_label(lines)
    assert guides == [("Picture Profile > PP4 > Color Mode: Movie", 0)]
    assert enters_on(cam, {1, 2}) == 0 < enters_on(alone, {1, 2}) and enters_on(cam, {0}) == 1
    assert (got["Movie"]["greyed"], got["Movie"]["greyed_by"], got["Movie"]["entered"]) == ("drawn", "reader",
                                                                                           "for its reason")
    assert got["Movie"]["grey_readings"]["pixels"] is False and got["Movie"]["grey_readings"]["reader"] is True
    assert all(got[x]["greyed_by"] == "pixels" and got[x]["dat"] is None for x in ("Still", "S-Cinetone"))
    assert "'Movie': drawn grey: the camera's Help on it, to read why (told by the reader; the pixels read it white" in said


def test_a_reader_that_misjudged_never_opens_the_pixels_grey_options(monkeypatch):
    """The reader calls Movie grey, the camera applies it after all: the reader misjudged this row, and the options
    drawn grey by their pixels are judged as with no reader at all (the first one Help and the one Enter for the
    reason, the other no key), never entered as misjudged."""
    alone = SideCam(grey=(1, 2), refuse=(1, 2))
    side_world(monkeypatch, alone)
    cam = SideCam(grey=(1, 2), refuse=(1, 2))
    said_by_reader(monkeypatch, cam, {0: True, 1: False, 2: False, 3: True}, OUTRIGHT)
    lines, said, guides = side_world(monkeypatch, cam)
    got = by_label(lines)
    assert enters_on(cam, {1, 2}) == enters_on(alone, {1, 2}) == 1 and enters_on(cam, {2}) == 0
    assert got["Movie"]["applied"] and "greyed" not in got["Movie"] and got["Movie"]["grey_readings"]["reader"] is True
    assert got["Still"]["entered"] == "for its reason" and got["Still"]["greyed_by"] == "pixels"
    assert got["S-Cinetone"]["dat"] is None and got["709"]["applied"]       # 709: the reader no longer heard, or asked
    assert got["709"]["grey_readings"] == {"pixels": False, "level": 225.0, "reader": None,
                                           "not_asked": "the reader misjudged an option of this row, and is not heard "
                                                        "on it"}
    assert [x[0] for x in guides] == ["Picture Profile > PP4 > Color Mode: Movie",
                                      "Picture Profile > PP4 > Color Mode: Still"]
    assert "'Movie' was drawn grey, yet the camera applied it (told by the reader)" in said


def test_pixels_that_misjudged_leave_the_readers_grey_judged(monkeypatch):
    """The pixels call Movie grey alone, the camera applies it: the pixels misjudged this row, and Still, which only
    the pixels call grey, is entered as before; S-Cinetone, which the reader calls grey, is still never chosen."""
    cam = SideCam(grey=(0, 1), refuse=(2,))
    said_by_reader(monkeypatch, cam, {2: True}, OUTRIGHT)
    lines, said, guides = side_world(monkeypatch, cam)
    got = by_label(lines)
    assert got["Movie"]["applied"] and got["Still"]["applied"] and "greyed" not in got["Still"]
    assert (got["S-Cinetone"]["greyed"], got["S-Cinetone"]["greyed_by"], got["S-Cinetone"]["applied"]) == (
        "drawn", "reader", False)
    assert "'Still': drawn grey, told by the pixels alone, which misjudged an option of this row" in said


def test_where_the_pixels_cannot_tell_the_reader_decides(monkeypatch):
    """Still's text measures 170 (cannot be told): the reader calling it grey keeps it from being chosen; the reader
    calling it white, or giving no answer, enters it as before."""
    for answer, chosen in ((True, False), (False, True), (None, True)):
        cam = SideCam(grey=(), refuse=(1,), unsure=(1,))
        said_by_reader(monkeypatch, cam, {1: answer}, OUTRIGHT)
        lines, said, guides = side_world(monkeypatch, cam)
        got = by_label(lines)["Still"]
        assert ("greyed" not in got or got.get("entered") == "for its reason") is True
        assert (got.get("greyed_by") == "reader") is (not chosen), answer
        assert got["grey_readings"] == {"pixels": None, "level": 170.0, "reader": answer, "question": "lit.v2.grey",
                                        "reader_name": "fake", **({"why": "no answer"} if answer is None else {})}
        assert ("the pixels cannot tell whether it is drawn grey (its text reads 170); the reader reads it white"
                in said) is (answer is False)


@pytest.mark.parametrize("pixels", [(), (0,), (1, 2), (0, 1, 2), (0, 2, 3), (0, 1, 2, 3)])
@pytest.mark.parametrize("reader", [(), (3,), (0, 3), (1, 2, 3), (0, 1, 2, 3)])
@pytest.mark.parametrize("refuse", ["pixels", "both", "none"])
def test_the_reader_never_adds_an_enter_on_an_option_the_pixels_call_grey(monkeypatch, pixels, reader, refuse):
    """Whatever the two eyes say and whatever the camera refuses, the options the pixels call grey get no more Enters
    with the reader's answers than without them, nor does the row as a whole: the reader only ever takes an Enter
    away (its Help aside). An option the reader alone calls grey gets at most the row's one try, but where the reader
    misjudged the row (the camera applied one it called grey), when its others are entered as with no reader."""
    pixel_grey, reader_grey = set(pixels), set(reader)
    refused = {"pixels": pixel_grey, "both": pixel_grey | reader_grey, "none": set()}[refuse]
    alone = SideCam(grey=pixel_grey, refuse=refused)
    side_world(monkeypatch, alone)
    cam = SideCam(grey=pixel_grey, refuse=refused)
    said_by_reader(monkeypatch, cam, {o: o in reader_grey for o in range(len(COLOR))}, OUTRIGHT)
    lines, said, guides = side_world(monkeypatch, cam)
    assert enters_on(cam, pixel_grey - {4}) <= enters_on(alone, pixel_grey - {4}), (cam.keys, alone.keys)
    assert cam.keys.count("enter") <= alone.keys.count("enter"), (cam.keys, alone.keys)
    reader_only = reader_grey - pixel_grey - {4}
    if not any(x["applied"] and COLOR.index(x["label"]) in reader_only for x in lines):
        assert enters_on(cam, reader_only) <= 1, cam.keys


class CarouselCam(ListCam):
    """A carousel (SHUTTER) as prove_row meets it: its options' pixels are not judged (drawn_grey gives nothing)."""

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "dialog", "notice": "notice"}[self.where], bar=None)


def test_on_a_carousel_the_reader_alone_tells_an_option_grey(monkeypatch, tmp_path):
    """prove_row on a carousel: On, which the reader calls grey and the camera refuses, gets the camera's Help and its
    one Enter for the reason, written greyed as drawn by the reader; Off and Auto are proved as before; with no answer
    from the reader every option is entered as today."""
    import prove_run as P
    from proving import greyed
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(P, "carousel_text", lambda c: SHUTTER[c.option])
    cam = CarouselCam(grey=(), refuse=(1,), saved=0)
    asked = said_by_reader(monkeypatch, cam, {1: True, 2: False, 0: False})
    lines, said, guides = list_world(monkeypatch, cam, kind="dialog")
    assert greyed.drawn_grey(cam) == (None, None)                       # a carousel's pixels are not judged
    on = by_label(lines)["On"]
    assert (on["greyed"], on["greyed_by"], on["entered"], on["applied"]) == ("drawn", "reader", "for its reason", False)
    assert guides == ["Flash Sync Spd. Prty.: On"] and sorted(set(asked)) == [1, 2]     # Auto: the put-back
    assert by_label(lines)["Off"]["applied"] and by_label(lines)["Off"]["grey_readings"]["reader"] is False
    cam2 = CarouselCam(grey=(), refuse=(1,), saved=0)
    said_by_reader(monkeypatch, cam2, {})
    lines2, said2, guides2 = list_world(monkeypatch, cam2, kind="dialog")
    assert guides2 == [] and cam2.keys.count("enter") == 3 and "greyed" not in by_label(lines2)["On"]


def test_on_a_carousel_the_lit_icon_tells_and_the_reader_is_asked_only_where_it_cannot(monkeypatch, tmp_path):
    """prove_row on a carousel: On's lit icon dim (grey), Off's bright (white), so neither is asked about; Auto, the
    put-back, never is; the line says the icon told it. An icon that cannot tell (Off) asks the reader, as before."""
    import prove_run as P
    from proving import greyed
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(P, "carousel_text", lambda c: SHUTTER[c.option])
    cam = CarouselCam(grey=(), refuse=(1,), saved=0)
    cam.icon = {1: (True, 110.0), 2: (False, 230.0), 0: (False, 230.0)}
    asked = said_by_reader(monkeypatch, cam, {1: False, 2: True})
    lines, said, guides = list_world(monkeypatch, cam, kind="dialog")
    got = by_label(lines)
    assert asked == [] and guides == ["Flash Sync Spd. Prty.: On"]
    assert (got["On"]["greyed_by"], got["On"]["entered"]) == ("pixels", "for its reason")
    assert got["Off"]["applied"] and got["Off"]["grey_readings"] == {"pixels": False, "level": 230.0, "reader": None,
                                                                     "not_asked": greyed.ICON_TELLS}
    cam2 = CarouselCam(grey=(), refuse=(1,), saved=0)
    cam2.icon = {1: (True, 110.0), 2: (None, 170.0)}
    asked2 = said_by_reader(monkeypatch, cam2, {2: True})
    lines2, _, _ = list_world(monkeypatch, cam2, kind="dialog")
    assert asked2 == [2] and by_label(lines2)["Off"]["greyed_by"] == "reader"


def icon_frame(colour):
    """A carousel's frame: its column of icons at the left, the lit one drawn in colour, the others white."""
    import numpy as np
    a = np.zeros((480, 640, 3), np.uint8)
    for y in (80, 150, 290):
        a[y:y + 30, 30:80] = (230, 230, 230)
    a[215:255, 25:85] = colour
    return a


def test_a_carousels_lit_icon_tells_grey_by_its_red():
    from proving import screens as PS
    assert PS.icon_grey(icon_frame((230, 60, 40)))[0] is False          # bright: the camera takes it
    assert PS.icon_grey(icon_frame((115, 30, 30)))[0] is True           # dim dark red: greyed
    assert PS.icon_grey(icon_frame((165, 50, 40)))[0] is None           # in between: cannot be told
    assert PS.icon_grey(icon_frame((230, 230, 230))) == (None, None)    # no red: none lit
    cam = SimpleNamespace(frame=SimpleNamespace(image=icon_frame((115, 30, 30))), read=lambda: SimpleNamespace(
        kind="dialog", bar=None))
    assert PS.drawn_grey(cam)[0] is True


@pytest.mark.parametrize("name, grey", [("119947_reread.png", True), ("123252_reread.png", True),
                                        ("115883_reread.png", True), ("226337_reread.png", True),
                                        ("119966_reread.png", False), ("119930_reread.png", False)])
def test_the_cameras_carousels_are_told_grey_by_their_lit_icon(name, grey):
    """ISO 100 under S-Cinetone and Flash Mode's options the camera refused (dim), ISO 125 and ISO AUTO it applied
    (bright), kit2_pass2."""
    from proving import screens as PS
    f = load(need(A1 / "kit2_pass2" / "shots" / name))
    s = screen.read(f)
    assert s.kind == "dialog" and PS.drawn_grey(SimpleNamespace(frame=f, read=lambda: s))[0] is grey, name


def test_the_list_prover_asks_its_whole_list_once_a_visit(monkeypatch, tmp_path):
    """prove_row on Flash Sync Spd. Prty.: one whole-list question for the row's visit; Off, white by its pixels and
    grey by the reader's flag, gets Help and the row's one Enter for its reason."""
    monkeypatch.chdir(tmp_path)
    cam = ListCam(grey=(), refuse=(2,), saved=0)
    pool = listen_world(monkeypatch, entries_of(SHUTTER, grey={2}))
    lines, said, guides = list_world(monkeypatch, cam)
    off = by_label(lines)["Off"]
    assert len(pool.asked) == 1 and guides == ["Flash Sync Spd. Prty.: Off"]
    assert (off["greyed_by"], off["entered"], off["grey_readings"]["question"]) == ("reader", "for its reason",
                                                                                   "entries.v2")
    assert by_label(lines)["On"]["applied"] and by_label(lines)["On"]["grey_readings"]["reader"] is False


def carousel_enters(cam, saved=0):
    """{option: the Enters it got} replayed from a ListCam's keys (its own moves), from the option it was saved on."""
    n = len(SHUTTER)
    out, where, option = {}, "row", saved
    for k in cam.keys:
        if k == "right":
            where, option = "list", saved
        elif k in ("down", "up") and where == "list":
            option = (option + (1 if k == "down" else -1)) % n
        elif k == "enter":
            out[option] = out.get(option, 0) + 1
            if option in cam.refuse:
                where = "notice"
            else:
                where, saved = "row", option
        elif k == "menu":
            where = "row"
    return out


@pytest.mark.parametrize("reader", [{}, {1: True}, {2: True}, {1: True, 2: True}, {0: True, 1: True, 2: True},
                                    {1: False, 2: False}, {1: None, 2: True}])
@pytest.mark.parametrize("refuse", [(), (1,), (2,), (1, 2)])
def test_on_a_carousel_the_reader_never_causes_an_enter_the_old_code_did_not_send(monkeypatch, tmp_path, reader, refuse):
    """b3afe42 entered every option of a carousel once, its pixels not judged; with the reader's answers, whatever they
    are and whatever the camera refuses, no option gets more Enters than that, and the row no more in all."""
    import prove_run as P
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(P, "carousel_text", lambda c: SHUTTER[c.option])
    old = CarouselCam(grey=(), refuse=refuse, saved=0)
    said_by_reader(monkeypatch, old, {})
    list_world(monkeypatch, old, kind="dialog")
    cam = CarouselCam(grey=(), refuse=refuse, saved=0)
    said_by_reader(monkeypatch, cam, reader)
    list_world(monkeypatch, cam, kind="dialog")
    before, after = carousel_enters(old), carousel_enters(cam)
    assert before == dict.fromkeys(range(len(SHUTTER)), 1), old.keys
    assert all(after.get(o, 0) <= before[o] for o in before) and sum(after.values()) <= sum(before.values()), cam.keys


def test_the_reader_is_asked_the_kinds_grey_question_about_the_frame_on_show(eyes):
    """proving.greyed.reader_grey: a carousel's option asked carousel.v2.grey through camkit.reading.ask, its "greyed"
    read by camkit.reading.greyed_of; a failure or an answer with no grey is no answer, said why; a list's and a side
    list's lit option asked nothing (its flag is the row's whole-list answer's: Flags), said so; any other screen asked
    nothing."""
    from proving import greyed
    lit = eyes.frame("00010_down.png", bar=(305, 236, 595, 282))
    eyes.answer("lit.v2.grey", {"selected": "Movie", "greyed": True})
    eyes.answer("carousel.v2.grey", {"selected": "ISO 100", "greyed": "false"})

    def on(kind, frame):
        return SimpleNamespace(frame=frame, read=lambda: SimpleNamespace(kind=kind))
    for kind in ("sidelist", "list"):        # no question about the lit option: the row's whole-list answers, none here
        assert greyed.reader_grey(on(kind, lit)) == (None, {"not_asked": "no whole-list answers kept for this row"})
    assert greyed.reader_grey(on("dialog", lit)) == (False, {"question": "carousel.v2.grey",
                                                             "reader_name": "fake second", "read": "ISO 100"})
    assert eyes.asked == ["carousel.v2.grey"]
    other = eyes.frame("00011_down.png", bar=(110, 236, 556, 282))
    assert greyed.reader_grey(on("checklist", other)) == (None, {}) and greyed.reader_grey(on("menu", other)) == (None, {})
    eyes.answer("carousel.v2.grey", {"selected": "none", "greyed": True})
    said, kept = greyed.reader_grey(on("dialog", eyes.frame("00012_right.png")))
    assert said is None and kept["why"] == "the answer says nothing of grey"
    eyes.answer("carousel.v2.grey", RuntimeError("down"))
    said, kept = greyed.reader_grey(on("dialog", eyes.frame("00013_right.png")))
    assert said is None and "the reader failed" in kept["why"]
    eyes.models = {}                                                    # no reader configured
    said, kept = greyed.reader_grey(on("dialog", eyes.frame("00014_right.png")))
    assert said is None and kept["why"]
    assert greyed.reader_grey(SimpleNamespace(frame=None, read=lambda: SimpleNamespace(kind="dialog")))[0] is None


# what the readers are fed: an old refused line carrying another option's diff (kit2_pass2 8459-8460's shape, its
# record the row's own and one no setting covers, its readings agreeing), and a line of an option drawn grey that no key
# was pressed on (proving.greyed.line)
OLD_REFUSED = {"path": ["Bravo"], "kind": "list", "index": 1, "label": "On", "shown": "On", "vlm": "On",
               "chosen_frame": "00010_down.png", "row_frame": "00012_menu.png", "dat": "00013_Bravo-1.DAT",
               "base": "00001_base.DAT", "attempt": "A",
               "notice": {"text": "This operation or setting not available as follows Alpha On • OK", "frame": "00011_enter.png"},
               "changes": [{"key": "global:0x0101", "before": 0, "after": 1},
                           {"key": "global:0x0202", "before": 0, "after": 7}], "applied": False}
GREY_LINE = {"path": ["Bravo"], "kind": "list", "index": 0, "label": "Off", "shown": "Off", "vlm": "Off",
             "chosen_frame": "00020_down.png", "row_frame": "00020_down.png", "dat": None, "base": "00001_base.DAT",
             "attempt": "A", "changes": [], "notice": None, "applied": False, "greyed": "drawn",
             "blocker": {"row": "Alpha"}, "reason": {"from": "notice", "frame": "00011_enter.png", "entry": "On"}}


def test_the_ledger_never_credits_a_line_the_camera_did_not_apply(ledger_camera):
    """Both lines leave the row and its options greyed in state, the blocker named (the notice's, else the line's own);
    neither is a proof (valid, inferred or unchecked), a record changed, a choice with no change, nor an evidence bundle."""
    import json

    import test_coverage as T
    hand = ledger_camera.data / f"hand_tables_{T.CAM}.json"           # Bravo not proved by hand here
    hand.write_text(json.dumps({**json.loads(hand.read_text(encoding="utf-8")), "FRAME_PROOFS": {}}), encoding="utf-8")
    T.write_proofs(ledger_camera, "kit2_pass2", [OLD_REFUSED, GREY_LINE], attempts=["A"])
    led = T.ledger(validity=True)
    e = T.row(led, "Bravo")
    assert e["status"] == "greyed in state" and e["blocker"] == {"row": "Alpha"}
    assert {o["key"]: o for o in led.options}["global:0x0101"]["values"] == {0: "greyed in state", 1: "greyed in state"}
    assert {r["key"]: r for r in led.records}["global:0x0202"]["status"] == "unmapped, not examined"
    assert led.proof_summary["proofs"] == 0 and not [b for b in led.bundles if b["path"] == ["Bravo"]]
    assert not any(c["path"] == ["Bravo"] for c in led.proof_checks)


def test_the_rows_look_after_a_prove_run_is_refused_where_nothing_applied_changed(tmp_path):
    """camkit.coverage.ProveLooks: a row whose lines the camera refused or drew grey, beside a put-back that changed
    nothing, is refused with its blocker, never tested with no record changes; a refused line's diff is never a record
    the row changed; a row where an applied option changed a record is changed, as before."""
    import json

    from camkit import coverage
    from conftest import TEST_CAMERA
    run = SimpleNamespace(root=tmp_path / TEST_CAMERA, dir=tmp_path / TEST_CAMERA / "kit2_pass2")
    run.dir.mkdir(parents=True)
    proofs, fails = run.dir / "proofs.jsonl", run.dir / "failures.jsonl"
    looks = coverage.ProveLooks(run, proofs, fails)
    put_back = {**OLD_REFUSED, "index": 0, "label": "Off", "notice": None, "applied": True, "changes": []}
    proofs.write_text("".join(json.dumps(x) + "\n" for x in (OLD_REFUSED, GREY_LINE, put_back)), encoding="utf-8")
    looks.after({"path": ["Bravo"], "kind": "list"})
    with open(proofs, "a", encoding="utf-8") as f:
        f.write(json.dumps({**put_back, "label": "On", "changes": [{"key": "global:0x0101", "before": 0, "after": 1}]})
                + "\n")
    looks.after({"path": ["Bravo"], "kind": "list"})
    got = [json.loads(x) for x in coverage.looks_file(TEST_CAMERA).read_text(encoding="utf-8").splitlines()][-2:]
    assert (got[0]["result"], got[0]["blocker"], got[0]["records_changed"]) == ("refused", {"row": "Alpha"}, [])
    assert got[1]["result"] == "changed" and got[1]["records_changed"] == ["global:0x0101"]


def test_the_proof_viewer_shows_no_value_from_a_line_the_camera_did_not_apply(tmp_path, monkeypatch):
    """kit/tools/proof_viewer.py: the old refused line's diff (another option's) and the grey line show as no value's
    evidence; an applied line of the same record does, as before."""
    import collections
    import json

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import proof_viewer as pv
    run = tmp_path / "kit2_pass2"
    (run / "shots").mkdir(parents=True)
    applied = {**OLD_REFUSED, "label": "Off", "applied": True, "notice": None,
               "changes": [{"key": "global:0x0101", "before": 1, "after": 0}]}
    (run / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (OLD_REFUSED, GREY_LINE, applied)),
                                      encoding="utf-8")
    monkeypatch.setattr(pv, "RUN_ROOT", tmp_path)
    ev = collections.defaultdict(list)
    pv.from_proofs(run, pv.Keys([{"key": "global:0x0101"}, {"key": "global:0x0202"}]), tmp_path / "_viewer", ev)
    assert [(e["label"], e["v"]) for e in ev["global:0x0101"]] == [("Off", 0)] and not ev["global:0x0202"]


def report_line(label, index, changes, **kw):
    return {"path": ["Bravo"], "kind": "list", "index": index, "label": label, "shown": label, "vlm": label,
            "chosen_frame": f"{index:05d}_c.png", "row_frame": f"{index:05d}_r.png", "dat": f"{10 + index:05d}_d.DAT",
            "base": "00001_base.DAT", "attempt": "A", "notice": None, "applied": True, "changes": changes, **kw}


def test_the_report_credits_no_line_the_camera_did_not_apply():
    """kit/pass2_report.py: the option's applied proof stays its latest beside a later refused or grey line (rows_of);
    neither is credited (credited, values_of, record_runs, record_allowances), and a number field's refusal, which says
    what the camera kept, is credited as before."""
    import pass2_report as R
    on = report_line("On", 1, [{"key": "global:0x0101", "before": 0, "after": 1}], allowance="the owner allowed On")
    refused = {**OLD_REFUSED, "allowance": "the owner allowed it"}
    grey = {**GREY_LINE, "index": 1, "label": "On"}
    rows = R.rows_of(None, [on, refused, grey])
    assert rows["Bravo"][1] is on
    assert not R.credited(refused) and not R.credited(grey) and R.credited(on)
    assert R.credited({"kind": "fields", "applied": False, "kept": "10", "value": "11"})
    vals = R.values_of({0: {**refused, "index": 0, "label": "Off"}, 1: on})
    assert vals.get("global:0x0202") is None and "Off" not in (vals.get("global:0x0101") or {}), vals
    assert R.record_allowances({0: refused, 1: on}, {"On": 1}, {}) == ["the owner allowed On"]
    assert R.record_allowances({0: refused}, {"On": 1}, {}) == []


def test_a_grey_line_is_no_step_of_the_carried_over_sequence():
    """carried_over: A writes the two records, a grey option of the row is skipped, C keeps A's value of one record while
    the other moves: C's kept value is carried over (not C's), as it is without the grey line between them."""
    import pass2_report as R
    a = report_line("A", 0, [{"key": "global:0x0101", "before": 0, "after": 1}, {"key": "global:0x0103", "before": 0,
                                                                                 "after": 1}])
    grey = {**GREY_LINE, "index": 1, "label": "B", "chosen_frame": "00011_c.png"}
    c = report_line("C", 2, [{"key": "global:0x0101", "before": 0, "after": 1}, {"key": "global:0x0103", "before": 0,
                                                                                 "after": 2}],
                    chosen_frame="00012_c.png")
    d = report_line("D", 3, [{"key": "global:0x0101", "before": 0, "after": 3}], chosen_frame="00013_c.png")
    with_grey, without = R.carried_over([a, grey, c, d]), R.carried_over([a, c, d])
    assert with_grey == without and [x["label"] for x in with_grey] == ["C"], with_grey


def test_the_report_lists_what_was_not_applied_and_how():
    import pass2_report as R
    assert R.not_applied_entry(GREY_LINE) == {"label": "Off", "index": 0, "how": "greyed as drawn",
                                              "blocker": {"row": "Alpha"}, "reason_from": "notice"}
    tried = {**OLD_REFUSED, "greyed": "drawn", "entered": "for its reason", "changes": [], "blocker": {"row": "Alpha"},
             "reason": {"from": "notice", "frame": "00011_enter.png", "entry": "On"}}
    assert R.not_applied_entry(tried)["how"] == "entered for its reason"
    assert R.not_applied_entry(OLD_REFUSED) == {"label": "On", "index": 1, "how": "refused"}
    assert R.same_proof(GREY_LINE) is not None and R.same_proof({**GREY_LINE, "greyed": None}) is None
    # which eyes told it grey (proving.greyed, 2026-11-19), where the line says
    for who in ("pixels", "reader", "both"):
        assert R.not_applied_entry({**GREY_LINE, "greyed_by": who})["told"] == who
    assert "told" not in R.not_applied_entry({**GREY_LINE, "greyed_by": "a guess"})
    assert "told" not in R.not_applied_entry({**OLD_REFUSED, "greyed_by": "reader"})


# the reviewer's scenario (2026-11-20), on the made-up camera's Bravo row: On grey by its pixels and refused by the
# camera on the row's one Enter (its notice names Alpha), Off white by its pixels but grey by the second reader's flag,
# skipped with no key as the row's reason was known (proving.greyed.line: "greyed_by" "reader", no notice, the row's
# blocker beside it)
PIXEL_REFUSED = {**OLD_REFUSED, "changes": [], "greyed": "drawn", "greyed_by": "pixels", "entered": "for its reason",
                 "blocker": {"row": "Alpha"}, "reason": {"from": "notice", "frame": "00011_enter.png", "entry": "On"}}
READER_ALONE = {**GREY_LINE, "greyed_by": "reader"}


def test_an_option_only_the_reader_called_grey_is_no_refusal_for_the_writer_the_ledger_or_the_census(ledger_camera,
                                                                                                    tmp_path):
    """camkit.coverage.reader_alone, one rule for the three: Off, which only the reader called grey and nobody tried,
    gives the writer no blocked entry and the ledger no "greyed" value, and the census no grey truth; On, which the
    camera refused, still does all three."""
    import json

    import schema_update as SU
    import test_coverage as T
    from camkit import coverage
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import reader_census as rc
    assert coverage.reader_alone(READER_ALONE) and not coverage.reader_alone(PIXEL_REFUSED)
    assert not coverage.reader_alone({**READER_ALONE, "notice": {"text": "not available as follows Alpha"}})
    assert not coverage.reader_alone(GREY_LINE)                      # an older grey line, told by the pixels
    (tmp_path / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (PIXEL_REFUSED, READER_ALONE)),
                                           encoding="utf-8")
    assert dict(SU.blocked(tmp_path)) == {"Bravo": [("On", "This operation or setting not available as follows Alpha On")]}
    hand = ledger_camera.data / f"hand_tables_{T.CAM}.json"
    hand.write_text(json.dumps({**json.loads(hand.read_text(encoding="utf-8")), "FRAME_PROOFS": {}}), encoding="utf-8")
    T.write_proofs(ledger_camera, "kit2_pass2", [PIXEL_REFUSED, READER_ALONE], attempts=["A"])
    led = T.ledger(validity=True)
    values = {o["key"]: o for o in led.options}["global:0x0101"]["values"]
    assert values.get(1) == "greyed in state" and values.get(0) != "greyed in state", values
    assert T.row(led, "Bravo")["blocker"] == {"row": "Alpha"}
    assert rc.line_grey(READER_ALONE) == {} and rc.line_grey(PIXEL_REFUSED) == {"drawn": True, "refused": True}


def test_the_writer_reads_a_grey_lines_blocker_and_credits_no_refused_diff(tmp_path):
    """kit/schema_update.py: the grey line's option is blocked with its row's blocker in the camera's own sentence (the
    row alone, never a value); a refused line's diff names no record the row went through."""
    import json

    import schema_update as SU
    (tmp_path / "proofs.jsonl").write_text(json.dumps(GREY_LINE) + "\n", encoding="utf-8")
    assert SU.blocked(tmp_path)["Bravo"] == [("Off", "This operation or setting not available as follows Alpha")]
    assert not SU.proved_rows([OLD_REFUSED]) and SU.proved_rows([report_line("On", 1, [{"key": "global:0x0101",
                                                                                        "before": 0, "after": 1}])])


def test_replay_counts_a_line_the_camera_did_not_apply_apart(tmp_path):
    import json

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import replay_proofs
    (tmp_path / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (OLD_REFUSED, GREY_LINE)),
                                           encoding="utf-8")
    assert replay_proofs.replay(tmp_path) == ([], [], [], 2, 0)


# ---------------------------------------------------------------- 14. the ledger knows a row whose opening acts

def with_zoom_rows(camera):
    """The made-up camera's menu with a group Zoom of four rows: Zoom (its opening is the zoom itself), Zoom Range,
    Zoom Ring Rotate and Clear Image Zoom."""
    import json
    doc = json.loads(camera.defn.read_text(encoding="utf-8"))
    n = len(doc["menu"])
    doc["menu"] += [{"tab": "Shooting", "group": "Zoom", "label": lab, "order": n + i}
                    for i, lab in enumerate(["Zoom", "Zoom Range", "Zoom Ring Rotate", "Clear Image Zoom"])]
    camera.defn.write_text(json.dumps(doc), encoding="utf-8")


def test_the_ledger_takes_a_row_on_the_acts_on_open_list_for_an_action(ledger_camera):
    """Zoom, on safety's acts-on-open list and not on the never-open list: "action, nothing to map", inferred from its
    class, in the private form and the public one, even where a look saw it greyed; its class and opener stay None
    (rule_class, openers), and the to-do leaves it out."""
    import test_coverage as T
    from camkit import coverage
    with_zoom_rows(ledger_camera)
    T.add_looks(ledger_camera, T.look(["Zoom"], tab="Shooting", screen="notice", result="greyed",
                                      blocker={"row": "Zoom Range"}))
    led = T.ledger()
    e = T.row(led, "Zoom", group="Zoom")
    assert (e["status"], e.get("inferred"), e["rule"], e["opener"]) == ("action, nothing to map", "class", None, None)
    pub = {tuple(r["path"]): r for r in coverage.public_doc(led)["rows"]}[("Zoom",)]
    assert pub["status"] == "action, nothing to map" and pub["inferred"] == "class" and "rule" not in pub
    assert not [x for x in coverage.todo(led) if x["entry"]["path"] == ["Zoom"]]
    assert coverage.rule_class("Zoom") is None and coverage.openers("Zoom") == [] and safety.never_open("Zoom") is None


def test_the_rows_of_the_zoom_group_and_the_other_statuses_stay_as_they_were(ledger_camera):
    import test_coverage as T
    with_zoom_rows(ledger_camera)
    led = T.ledger()
    for label in ("Zoom Range", "Zoom Ring Rotate", "Clear Image Zoom"):
        e = T.row(led, label, group="Zoom")
        assert e["status"] == "not yet tried" and "inferred" not in e, label
    # an action of the never-open list and a row a look saw act keep their statuses and classes
    assert T.row(led, "Setting Reset")["status"] == "action, nothing to map"
    assert T.row(led, "Setting Reset")["rule"] == "action"


def test_a_row_on_the_acts_on_open_list_with_a_setting_placed_on_it_is_no_action(ledger_camera):
    """The status is an action's only where no setting is placed on the row, as for the never-open list's actions."""
    import json

    import test_coverage as T
    doc = json.loads(ledger_camera.defn.read_text(encoding="utf-8"))
    for s in doc["settings"]:
        if s["key"] == "global:0x0101":                    # Bravo's setting, placed on a row named Zoom instead
            s["row"] = ["Zoom"]
    doc["menu"].append({"tab": "Shooting", "group": "Zoom", "label": "Zoom", "order": len(doc["menu"])})
    ledger_camera.defn.write_text(json.dumps(doc), encoding="utf-8")
    assert T.row(T.ledger(), "Zoom", group="Zoom")["status"] != "action, nothing to map"


def test_the_a1_iis_public_build_says_zoom_is_an_action():
    """The a1 II's committed public sources (data/, editor/definitions/: in every clone): its public build's Zoom row,
    as kit/tools/coverage.py --print prints it, is an action, inferred from its class."""
    import json

    from camkit import coverage
    built = json.loads(coverage.public_build_text(paths.A1II))
    rows = {(r["mode"], r["tab"], r["group"], tuple(r["path"]), r.get("nth", 0)): r for r in built["rows"]}
    zoom = rows[("Stills", "Shooting", "Zoom", ("Zoom",), 0)]
    assert zoom["status"] == "action, nothing to map" and zoom["inferred"] == "class"
