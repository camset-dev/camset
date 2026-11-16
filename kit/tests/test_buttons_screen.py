"""Pixel reader: boxed options alone, the "buttons" kind (2026-11-16).

The a1 II's Playback > Playback Option > Image Index opens a title, two wide boxes ("9 Images", "30 Images"), the
current one filled orange, and the menu footer. It read as no known kind, so a row's first open through kit/drive.py
stopped there with RESTORE_BY_HAND and left it open. Now it is "buttons", read last, only where every other rule reads
unknown: a row's first open reads it and leaves it with MENU (safety.FIRST_OPEN_KINDS), and no Enter goes on it by its
kind, since a question can be drawn so with no question mark: Enter stays as on a screen of no known kind.

Run: .venv/bin/python -m pytest kit/tests/test_buttons_screen.py -q
The camera's frames live under runs/ (not versioned); the tests that read them skip when absent, the ones on drawn
pictures run everywhere.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive  # noqa: E402
from camkit import paths, safety, screen  # noqa: E402
from camkit.frames import Frame, load  # noqa: E402

A1 = paths.a1ii_root()
IMAGE_INDEX = [(A1 / "kit2_a1chk_imageindex_look" / "shots" / "00018_after-armed.png", 0, "9 Images"),
               (A1 / "kit2_hdmi_watch" / "shots" / "05764_seen.png", 1, "30 Images")]
IDS = ["first-lit", "second-lit"]


def need(path: Path):
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


# ---------------------------------------------------------------- the camera's own frames

@pytest.mark.parametrize("path, lit, text", IMAGE_INDEX, ids=IDS)
def test_image_index_reads_as_boxed_options(path, lit, text):
    """Both frames: two boxes x 96-543, 58 px tall, the lit one's index as `row` and its span as `bar`."""
    s = screen.read(load(need(path)))
    assert s.kind == "buttons"
    assert (s.count, s.row, len(s.rows)) == (2, lit, 2)
    assert s.rows == [(178, 235), (250, 307)] and s.bar == s.rows[lit]
    assert s.boxes == [(96, 543)] * 2


@pytest.mark.parametrize("path, lit, text", IMAGE_INDEX, ids=IDS)
def test_image_index_lit_option_is_read_as_the_kit_reads_a_lit_option(path, lit, text):
    """camkit.live.lit_text, what drive.py and the camera's own check read as the lit text, on the same frames (skipped
    without runs/ or this computer's OCR): the lit box is found as a bar, and its text alone is read."""
    from camkit import live, ocr
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = load(need(path))
    assert live.lit_box(f.image) == (96, (178, 250)[lit], 544, (236, 308)[lit])
    assert live.lit_text(f.image, path) == text


def test_the_two_frames_are_two_states_of_one_screen():
    """The same title and options, the lit box elsewhere: never the same state (same_state), as the walkers need."""
    a, b = (screen.read(load(need(p))) for p, _, _ in IMAGE_INDEX)
    assert a.kind == b.kind == "buttons" and not screen.same_state(a, b)


# ---------------------------------------------------------------- drawn pictures: where the kind begins and ends

GREY_EDGE, FILL, BORDER, WHITE = 85, (170, 51, 0), (221, 85, 0), 221


def _glyph(name: str) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(Path(screen.__file__).parent / "glyphs" / f"{name}.png").convert("L"))


def _text(a, y0, y1, x0, x1):
    """Letter-like white strokes (4 px wide, 6 px apart) across x0..x1."""
    for x in range(x0, x1, 10):
        a[y0:y1, x:x + 4] = WHITE


def drawn(n=2, lit=(0,), outline=True, top=178, h=58, pitch=72, x0=96, x1=543, tabs=False, rows=False,
          prose=False, battery=False) -> np.ndarray:
    """Image Index as the camera draws it: a title at the top left over its rule (y 53), `n` boxes x x0..x1 from y
    `top`, the ones in `lit` filled orange, the others outlined (or not: `outline`), text in each, the footer's rule
    (y 426) and help button. tabs: a coloured tab column at the left; rows: a row list under the boxes; prose: a line of
    text over them; battery: the finder's battery icon at the top right (camkit.screen.BATTERY_V)."""
    a = np.zeros((480, 640, 3), np.uint8)
    _text(a, 14, 40, 21, 191)                                   # the title
    a[53, 5:635] = 102
    a[426, 5:635] = 119
    g = _glyph("help_only")
    a[440:440 + g.shape[0], 470:470 + g.shape[1]] = g[..., None]
    for i in range(n):
        t = top + pitch * i
        b = t + h - 1
        if i in lit:
            a[t:b + 1, x0:x1 + 1] = BORDER
            a[t + 2:b - 1, x0 + 2:x1 - 1] = FILL
        elif outline:
            a[t:t + 2, x0:x1 + 1] = a[b - 1:b + 1, x0:x1 + 1] = GREY_EDGE
            a[t:b + 1, x0:x0 + 2] = a[t:b + 1, x1 - 1:x1 + 1] = GREY_EDGE
        _text(a, t + 16, t + 42, 250, 390)
    if tabs:
        for i in range(7):                                      # the menu's coloured tabs, x 0-47
            a[46 + 52 * i:90 + 52 * i, 2:46] = ((200, 40, 40), (40, 160, 60), (40, 80, 200), (200, 160, 30),
                                                (150, 50, 160), (30, 160, 170), (200, 90, 30))[i]
    if rows:
        for i in range(2):                                      # rows of a list under the boxes, their separators
            y = 330 + 45 * i
            _text(a, y + 8, y + 30, 60, 300)
            a[y + 40, 55:600] = 80
    if prose:
        _text(a, 110, 134, 60, 580)                             # a line of a question over the boxes
    if battery:
        x, y = screen.BATTERY_V["battery_finder"][:2]
        icon = _glyph("battery_finder")
        a[y:y + icon.shape[0], x:x + icon.shape[1]] = icon[..., None]
    return a


def read(a) -> screen.Screen:
    return screen.read(Frame(image=a, t=0.0))


@pytest.mark.parametrize("n, lit", [(2, 0), (2, 1), (3, 2), (4, 0), (4, 3)])
def test_two_to_four_boxes_one_lit_read_as_buttons(n, lit):
    top, h, pitch = (178, 58, 72) if n < 4 else (100, 58, 72)
    s = read(drawn(n, (lit,), top=top, h=h, pitch=pitch))
    assert s.kind == "buttons"
    assert s.count == n and s.row == lit and s.rows == [(top + pitch * i, top + pitch * i + h - 1) for i in range(n)]


@pytest.mark.parametrize("case, a", [
    ("one box", lambda: drawn(1)),
    ("five boxes", lambda: drawn(5, top=80, h=50, pitch=60)),
    ("none lit", lambda: drawn(2, ())),
    ("two lit", lambda: drawn(2, (0, 1))),
    ("three lit of three", lambda: drawn(3, (0, 1, 2))),
    ("an unlit box without its outline", lambda: drawn(2, outline=False)),
    ("a line of prose over the boxes", lambda: drawn(2, prose=True)),
    ("off centre", lambda: drawn(2, x0=150, x1=597)),
], ids=lambda v: v if isinstance(v, str) else "")
def test_what_is_not_boxed_options_alone_stays_unknown(case, a):
    """One box, five, none or more than one lit, a box drawn without its outline, prose on the screen (a question's
    words), boxes off centre: the screen reads as it did before the kind, unknown."""
    f = screen.features(a())
    assert f["option_boxes"] is None, case
    assert screen.classify(f) == "unknown", case


def test_a_tab_column_keeps_the_menu_page_its_kind():
    """Boxes beside a coloured tab column: a menu page, as the rules above the kind read it; the boxes are not looked for."""
    f = screen.features(drawn(2, tabs=True))
    assert f["option_boxes"] is None and screen.classify(f) == "menu"


def test_a_row_list_keeps_its_kind():
    """Rows of a list under the boxes: what the reader made of it without the kind, never "buttons"."""
    f = screen.features(drawn(2, rows=True))
    assert f["option_boxes"] is None
    assert screen.classify(f) == screen.classify({**f, "option_boxes": None}) != "buttons"


def test_the_kind_never_takes_a_screen_another_rule_places():
    """Boxed options alone with the finder's battery icon at the top right, outside every box: the boxes are found, and
    the screen is still the shooting screen, the rule that places it read first. Reading the boxes before any other
    rule would make it "buttons"."""
    f = screen.features(drawn(2, battery=True))
    assert f["option_boxes"] is not None
    assert screen.classify(f) == "shooting"


def test_a_feature_dict_without_the_boxes_reads_as_before():
    """classify on features made without option_boxes (a caller's own dict) is unchanged: unknown stays unknown."""
    f = screen.features(drawn(2))
    f.pop("option_boxes")
    assert screen.classify(f) == "unknown"


# ---------------------------------------------------------------- what the kit may do on it

def test_a_first_open_reads_it_and_nothing_else_lets_a_key_through():
    """A row's first open reads it (FIRST_OPEN_KINDS); no set that lets Enter, C4, a confirmation or a choice go, or
    shows the screen's text inside a network row, holds it."""
    assert "buttons" in safety.FIRST_OPEN_KINDS
    for name in ("ENTER_KINDS", "LIST_KINDS", "OPTION_KINDS", "SHOWN_KINDS", "CONFIRM_KINDS", "C4_SCREENS",
                 "C4_HELP_SCREENS"):
        assert "buttons" not in getattr(safety, name), name
    assert safety.c4_refused("buttons")
    why = safety.enter_refused("buttons", "Image Index 9 Images 30 Images", "9 Images")
    assert "not one whose Enter chooses or opens" in why, why


# a made-up screen of the same layout: Image Index's own title names a row the never-open list holds (an action), on
# which no vouch goes at all (below)
TEXT = "Grid Size 9 Tiles 30 Tiles"
CONSENT = "--confirm 'Grid Size 9 Tiles 30 Tiles'"


def decide(p, lit, kind, confirm=False, consent="", text=TEXT):
    """drive.py's press_decision as main() calls it, after the press arguments were checked."""
    assert not drive.press_args_refused([p]), p
    return drive.press_decision(p, drive.parse_press(p)[0], lit, text, kind, confirm, (), consent=consent)


@pytest.mark.parametrize("lit", ["", "9 Tiles"], ids=["nothing-lit-read", "lit-read"])
def test_enter_on_boxed_options_is_refused_unless_vouched_and_named_as_on_an_unknown_screen(lit):
    """Enter on a "buttons" screen is judged as on a screen of no known kind, today's verdict on this very screen:
    refused plain; refused with the operator's vouch (enter!:REGEX) alone, which lifts an unreadable lit text and
    never the shape check; it goes once --confirm names the screen (or the owner route), vouched where nothing lit
    was read."""
    plain, vouched = decide("enter:tiles", lit, "buttons"), decide("enter!:tiles", lit, "buttons")
    assert plain[0] and not plain[1], plain
    assert vouched[0] and not vouched[1], vouched
    if lit:
        assert "not one whose Enter chooses or opens" in plain[0], plain
    else:
        assert "nothing lit can be read" in plain[0] and "not one whose Enter chooses or opens" in vouched[0], vouched
    assert decide("enter!:tiles", lit, "buttons", confirm=True) == ("", not lit)
    assert decide("enter!:tiles", lit, "buttons", consent=CONSENT) == ("", not lit)
    assert decide("enter:tiles", lit, "buttons", confirm=True) == (("", False) if lit else plain)
    for p in ("enter:tiles", "enter!:tiles"):
        for confirm in (False, True):
            assert bool(decide(p, lit, "buttons", confirm)[0]) == bool(decide(p, lit, "unknown", confirm)[0]), \
                (p, confirm)


def test_no_vouch_goes_on_image_index_itself():
    """Image Index's own text names a never-open row (an action): a vouched Enter where nothing lit is read is refused
    there whatever is confirmed, as on a screen of no known kind (drive.py, safety.screen_refused)."""
    text = "Image Index 9 Images 30 Images"
    for kind in ("buttons", "unknown"):
        why, vouched = decide("enter!:images", "", kind, confirm=True, text=text)
        assert "no vouching there" in why and not vouched, (kind, why)


def test_right_with_nothing_lit_read_is_refused_as_on_an_unknown_screen():
    """drive.py's ROW_KINDS: Right on a screen whose lit item cannot be read is refused there, as on an unknown one."""
    for kind in ("buttons", "unknown"):
        assert "nothing lit can be read" in drive.press_refused("right", "", TEXT, kind), kind
    assert drive.press_refused("right", "", TEXT, "slider") == ""


def test_inside_a_network_row_it_takes_menu_alone_as_an_unknown_screen():
    """Inside a row a network decision opened, boxed options alone get MENU alone and no reader, as a screen of no known
    kind did (safety.inside_menu_only), in every class of row."""
    for cls in (safety.LIFT_NETWORK, safety.LIFT_IDENTITY, safety.LIFT_ADDRESS):
        assert safety.inside_menu_only(cls, "buttons", TEXT), cls
        assert safety.inside_menu_only(cls, "unknown", TEXT), cls
    assert safety.network_withheld("buttons", TEXT)
