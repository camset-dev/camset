"""Pixel reader on screens drawn without their outlines, and a table of one column (2026-11-08).

The camera can draw its touchable controls without the outline boxes round them (camkit.screen, "Outlines"): a
number field's ▲/▼, the side list's ↩, the WB grid's arrows, a slider's − and + stand alone on the same pixels. Each
detector takes the box with its glyph, or the glyph alone. Image Quality Settings with one slot draws a single column, 336 px wide.

Run: .venv/bin/python -m pytest kit/tests/test_screen_edges.py -q
The camera's frames live under runs/ (not versioned); the tests that read them skip when absent, the ones on drawn
pictures run everywhere.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import paths, screen  # noqa: E402
from camkit.frames import Frame, load  # noqa: E402

A1 = paths.a1ii_root()
REVIEW = A1 / "kit2_review_list" / "shots"          # the run that drew no outlines
PASS2 = A1 / "kit2_pass2" / "shots"                 # October: the same screens with them
SHOTS = A1 / "explore_stills" / "shots"


def need(path: Path):
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def read(path: Path) -> screen.Screen:
    return screen.read(load(need(path)))


def painted_out(path: Path, box, keep) -> screen.Screen:
    """The camera's own frame with one control's outline painted out round its glyph, as the camera draws it
    without outlines: everything lit in `box` (x0, y0, x1, y1) but `keep` (the glyph's) goes black."""
    f = load(need(path))
    a = f.image.copy()
    x0, y0, x1, y1 = box
    k0, l0, k1, l1 = keep
    region = a[y0:y1, x0:x1]
    mask = np.ones(region.shape[:2], bool)
    mask[l0 - y0:l1 - y0, k0 - x0:k1 - x0] = False
    region[mask] = 0
    return screen.read(Frame(image=a, t=0.0))


# ---------------------------------------------------------------- number fields

def test_fields_at_the_minimum_without_outlines():
    # ISO Range Limit, Minimum = ISO 50: one bare ▼ under the field, no ▲ (the end of the range), no boxes
    s = read(REVIEW / "00106_right.png")
    assert s.kind == "fields"
    assert (s.field, s.count, s.glyphs["up"], s.glyphs["down"]) == (0, 2, False, True)
    assert s.bar == (244, 298) and s.boxes == [(74, 312), (327, 566)]


def test_fields_mid_range_with_outlines():
    # the same screen at ISO 2500, October: boxed ▲ and ▼
    s = read(PASS2 / "23202_down.png")
    assert s.kind == "fields"
    assert (s.field, s.count, s.glyphs["up"], s.glyphs["down"]) == (0, 2, True, True)
    assert s.bar == (244, 298) and s.boxes == [(74, 312), (327, 566)]


@pytest.mark.parametrize("name, field", [("00600_down.png", 0), ("00614_right.png", 0), ("00662_right.png", 1)])
def test_fields_at_the_maximum_without_outlines(name, field):
    # the symmetric case, on the camera's own frames: ISO Range Limit's Minimum at ISO 102400 and the Maximum field
    # at its top, one bare ▲ over the field and no ▼
    s = read(REVIEW / name)
    assert s.kind == "fields"
    assert (s.field, s.count, s.glyphs["up"], s.glyphs["down"]) == (field, 2, True, False)


def test_fields_at_the_maximum_painted():
    # the same state made from October's outlined frame (only the ▲ box) with that box painted out round its ▲:
    # it reads as the camera's own bare frame does
    s = painted_out(SHOTS / "03420_down.png", (129, 174, 257, 232), (183, 194, 202, 212))
    assert s.kind == "fields"
    assert (s.field, s.count, s.glyphs["up"], s.glyphs["down"]) == (0, 2, True, False)


def test_fields_with_no_arrow_at_all_fail_closed():
    # the ▲ painted out too: nothing says which way the field moves, so it is not read as one
    assert painted_out(SHOTS / "03420_down.png", (129, 174, 257, 232), (0, 0, 0, 0)).kind != "fields"


# ---------------------------------------------------------------- side lists

def test_sidelist_at_the_top_without_outlines():
    # PP1 > Black Level on 0, the first row: the ↩ at the left with no box round it
    s = read(REVIEW / "00146_right.png")
    assert s.kind == "sidelist"
    assert (s.row, s.count, s.bar) == (0, 6, (86, 133))
    assert s.scroll == (232, 286)


@pytest.mark.parametrize("name, row", [("14866_down.png", 0), ("14898_down.png", 5)])
def test_sidelist_with_outlines(name, row):
    # October: +15 on the first row, 0 on the last, the ↩ boxed
    s = read(PASS2 / name)
    assert s.kind == "sidelist" and s.row == row and s.count == 6


def test_sidelist_at_the_bottom_without_outlines():
    # the symmetric case, on the camera's own frame: PP1 > Black Level at -10, the bar on the last row, which is
    # button-sized, so the boxed reading takes it for a table's button (it did, before 2026-11-08); classify lets
    # that reading give way to the side list's lone ↩
    s = read(REVIEW / "00820_down.png")
    assert s.kind == "sidelist" and (s.row, s.bar) == (5, (336, 382))


def test_sidelist_at_the_bottom_painted():
    # the same state made from October's outlined frame with its ↩ box painted out round the ↩
    s = painted_out(PASS2 / "14898_down.png", (14, 177, 86, 248), (33, 195, 67, 230))
    assert s.kind == "sidelist" and s.row == 5


# ---------------------------------------------------------------- tables

def test_table_of_one_column():
    # Image Quality Settings with one slot: SLOT 1 alone, its cell (File Format) 336 px wide
    s = read(REVIEW / "00376_right.png")
    assert s.kind == "table" and s.focus == "cell"
    assert s.bar == (97, 149) and s.boxes == [(296, 631)] and s.marker == (464, 123)


def test_a_table_read_by_its_button_stays_that_table():
    # Image Quality Settings with OK focused: the table rule takes it by its low button alone, the one old reading
    # classify lets give way, and only to a side list; this real table reads exactly as before 2026-11-08
    s = read(A1 / "kit2_tables" / "shots" / "00682_down.png")
    assert (s.kind, s.focus, s.boxes, s.bar) == ("table", "button", [(344, 623)], (340, 394))
    assert s.signature == "8ce0aa003954"


def test_table_of_two_columns():
    # October: SLOT 1 and SLOT 2, the cursor on SLOT 1's File Format
    s = read(PASS2 / "83071_right.png")
    assert s.kind == "table" and s.focus == "cell"
    assert s.bar == (97, 149) and s.boxes == [(296, 462)] and s.marker == (379, 123)


# ---------------------------------------------------------------- White Balance grid

@pytest.mark.parametrize("path", [REVIEW / "00397_right.png", PASS2 / "24943_right.png"], ids=["bare", "boxed"])
def test_wbgrid_arrows_with_and_without_outlines(path):
    # Auto at the origin both times: the arrows bare in the review run, boxed in October
    s = read(path)
    assert s.kind == "wbgrid"
    assert s.glyphs == {"up": True, "down": True, "left": True, "right": True}
    assert s.marker == (478, 263)


def test_one_lone_arrow_is_not_a_wbgrid():
    # S&Q Frame Rate Settings: its field's ▲ stands alone where the WB grid's up box would be; a lone arrow counts
    # only beside another, so this stays what it was (unknown), whatever colour is under the grid's place
    s = read(PASS2 / "122583_down.png")
    assert s.kind != "wbgrid" and s.features["wb_arrows"] == 0


# ---------------------------------------------------------------- sliders

@pytest.mark.parametrize("name, marker, glyphs", [("233754_right.png", 158, {"left": False, "right": True}),     # at 1
                                                   ("233741_right.png", 480, {"left": True, "right": False})])    # at 7
def test_slider_without_outlines(name, marker, glyphs):
    # AF Transition Speed: the − and + alone, mirrored about x 320; the orange ▼ marks the value; at an end of the
    # scale one of ◂ ▸ goes (they sit on a line 60 px above the signs, below the 92 px boxes' band)
    s = read(PASS2 / name)
    assert s.kind == "slider" and s.marker == marker and s.glyphs == glyphs


def test_slider_with_outlines():
    # Aspect Marker Level at 15: the − and + boxes, ◂ only (the end of the scale)
    s = read(SHOTS / "02961_up.png")
    assert s.kind == "slider" and s.marker == 484 and s.glyphs == {"left": True, "right": False}


def test_slider_with_small_boxes():
    # Framing Tracking Speed (October, outlines on): − and + in 64 px boxes, which the 92 px box rule never matched
    # (the movie crawl logged these rows "unknown screen"); the signs inside them are read as the bare ones are
    s = read(PASS2 / "119059_right.png")
    assert s.kind == "slider" and s.marker == 400 and s.glyphs == {"left": True, "right": True}


def test_slider_marker_below_the_value_line():
    # Finder Color Temp. at -1: its ◂ ▸ are orange, its marker the orange square on the second dot of five; the
    # marker is looked for below the value line, so the ◂ is not taken for it
    s = read(A1 / "kit2_hdmi_watch" / "shots" / "02376_ready.png")
    assert s.kind == "slider" and s.marker == 266 and s.glyphs == {"left": True, "right": True}


def test_slider_values_differ_in_the_signature():
    # Playback/Monitor Vol. at 9 and at 7: a bar meter, no orange marker, so only the value line tells them apart
    a, b = read(A1 / "gen_run3" / "shots" / "00150_pick.png"), read(A1 / "gen_run3" / "shots" / "00234_pick.png")
    assert a.kind == b.kind == "slider" and a.marker is None and b.marker is None
    assert not screen.same_state(a, b)


def test_slider_arrows_unread_are_no_reading():
    # a slider found by its signs whose ◂ ▸ are not found reads no arrows at all, never both ends: a walk stops on
    # an arrow read False. The value line painted out of AF Transition Speed at 1 (its ▸ goes)
    s = painted_out(PASS2 / "233754_right.png", (230, 270, 410, 318), (0, 0, 0, 0))
    assert s.kind == "slider" and s.glyphs == {}


# ---------------------------------------------------------------- the rules, on drawn pictures (no frames needed)

def triangle(g, x, y, size=11, point="down"):
    """A solid light triangle `size` px across, its bounding box's top left at (x, y)."""
    rows = (size + 1) // 2
    t = np.zeros((rows, size), bool)
    for i in range(rows):
        t[i, i:size - i] = True                     # widest row first: ▼
    t = {"down": t, "up": t[::-1], "right": t.T, "left": t.T[:, ::-1]}[point]
    g[y:y + t.shape[0], x:x + t.shape[1]][t] = 255
    return t.shape


@pytest.mark.parametrize("point", ["up", "down", "left", "right"])
def test_a_lone_triangle_counts(point):
    g = np.zeros((480, 640), np.float32)
    h, w = triangle(g, 300, 200, point=point)
    region = (300 + w // 2 - 20, 200 + h // 2 - 20, 300 + w // 2 + 21, 200 + h // 2 + 21)
    assert screen._lone_triangle(g, region, point)
    other = {"up": "down", "down": "up", "left": "right", "right": "left"}[point]
    assert not screen._lone_triangle(g, region, other)


def test_a_triangle_among_other_ink_does_not():
    g = np.zeros((480, 640), np.float32)
    triangle(g, 300, 200)
    g[200:210, 318:322] = 200                       # a letter's stroke 7 px to its right
    assert not screen._lone_triangle(g, (285, 185, 326, 226), "down")


def test_a_hollow_triangle_does_not():
    g = np.zeros((480, 640), np.float32)
    triangle(g, 300, 200, size=15)
    g[201:204, 304:311] = 0                         # a hole: an "A" or a "V", not a ▲/▼
    assert not screen._lone_triangle(g, (287, 185, 328, 226), "down")


def test_bare_signs_mirrored_and_alone():
    g = np.zeros((480, 640), np.float32)
    g[355:359, 62:89] = 255                          # −, centred on x 75.5
    g[343:371, 562:565] = 255                        # +, centred on x 563.5: 75.5 + 563.5 = 639
    g[355:359, 551:576] = 255
    assert screen._bare_signs(g) == (62, 355, 27, 4)
    g[355:359, 95:99] = 200                          # ink 6 px beside the −: not a lone sign
    assert screen._bare_signs(g) is None


def test_an_old_match_wins():
    # classify tries the boxes alone first: a checklist whose page also holds a lone ▲ by its orange box stays a
    # checklist, though the fields rule comes first; the same with the boxed reading unknown reads fields
    f = screen.features(np.zeros((480, 640, 3), np.uint8))
    f.update(title_line=1.0, footer_line=1.0, field_arrows=1, field_arrows_boxed=0, checkboxes=2)
    assert screen.classify(f) == "checklist"
    f.update(checkboxes=0)
    assert screen.classify(f) == "fields"
    # and the column-wide cell is tried after the button test: a wide box low on the screen stays a button
    assert screen._table_focus({"cell_box": (345, 340, 278, 50), "cell_grid": True, "icon_tabs": 0}) == "button"
    assert screen._table_focus({"cell_box": (296, 97, 336, 53), "cell_grid": True, "icon_tabs": 0}) == "cell"


def test_a_grid_column_and_a_bar_with_nothing_under_it():
    g = np.full((480, 640), 31, np.float32)          # the table's panel grey
    for x in (294, 632):
        g[97:312, x] = 58                            # the grid's vertical lines
    assert screen._grid_column(g, (296, 97, 336, 53))
    assert screen._grid_column(g, (296, 258, 336, 53))          # the bottom row: the lines run above it
    assert not screen._grid_column(np.zeros((480, 640), np.float32), (304, 86, 294, 48))


# ---------------------------------------------------------------- the lit item drawn without a bar (camkit.live)

ORANGE = (230, 90, 20)                               # the camera's cursor orange, as screen._orange takes it


def drawn(*boxes) -> np.ndarray:
    """A black frame with orange filled where each box (x0, y0, x1, y1) says."""
    a = np.zeros((480, 640, 3), np.uint8)
    for x0, y0, x1, y1 in boxes:
        a[y0:y1, x0:x1] = ORANGE
    return a


def test_a_lit_item_without_a_bar_is_found_only_where_one_may_be():
    """live.lit_box finds the cursor as a bar first; a dialog or table that lights its item as orange text or a narrow
    cell (no bar) gets the largest orange region, the word's letters merged, its whole line; a menu page never does,
    for there a lit row is a bar and its orange texts are values on unlit rows: with no bar it stays unlit (drive.py
    refuses), and with one the bar wins over the value texts. Drawn pictures, run everywhere."""
    from camkit import live
    word = drawn(*((132 + 22 * i, 70, 148 + 22 * i, 100) for i in range(6)), (300, 70, 330, 100), (32, 200, 60, 226))
    assert live.lit_box(word, "dialog") == (132, 70, 330, 100), "the letters and the word after the gap, one line"
    assert live.lit_box(word, "table") == (132, 70, 330, 100)
    assert live.lit_box(word, "menu") is None and live.lit_box(word, "submenu") is None, "no bar on a row page"
    assert live.lit_box(word, "shooting") is None and live.lit_box(word, "unknown") is None
    assert live.lit_box(drawn((50, 50, 52, 52)), "dialog") is None, "a speck is nothing lit"
    page = drawn((138, 43, 636, 95), (544, 108, 631, 131), (556, 161, 629, 190))   # a row's bar, two value texts
    assert live.lit_box(page, "menu") == live.lit_box(page, "dialog") == (138, 43, 636, 95), "the bar wins"


def test_a_lit_item_is_read_as_its_whole_text_line():
    """live.line_box: the box of a lit item drawn without a bar widens to every OCR text run it touches on its line,
    so a label only part of which was orange is judged whole by the never-open check ("Direct Info." alone passes
    it, "Wi-Fi Direct Info." does not); a run elsewhere on the line (a table's row label, another slot) stays out."""
    from camkit import live, ocr, safety
    lines = [ocr.Line("Wi-Fi Direct Info.", 0.99, 130, 70, 260, 30), ocr.Line("File Format", 0.99, 8, 110, 180, 30),
             ocr.Line("HEIF", 0.99, 360, 112, 40, 26), ocr.Line("HEIF", 0.99, 530, 112, 40, 26)]
    part = (300, 68, 390, 102)                                  # the label's end alone was orange: its centre is out
    assert ocr.text_in(lines, part) == "" and safety.never_open("Direct Info.") is None
    whole = ocr.text_in(lines, live.line_box(part, lines))
    assert whole == "Wi-Fi Direct Info." and safety.never_open(whole)
    cell = (296, 97, 463, 150)                                  # slot 1's cell on the File Format row
    assert ocr.text_in(lines, live.line_box(cell, lines)) == "HEIF", "not the row label, not slot 2"


WB_MOVIE = A1 / "kit2_wbmovie2" / "shots"           # the White Balance chooser in Movie mode: orange text, no bar
QUALITY = A1 / "kit2_quality2" / "shots"            # Image Quality Settings, two slots and one


@pytest.mark.parametrize("path, box", [
    (WB_MOVIE / "00055_down.png", (132, 69, 340, 106)), (WB_MOVIE / "00072_down.png", (132, 69, 340, 106)),
    (WB_MOVIE / "00062_right.png", (132, 70, 197, 99)), (QUALITY / "00028_right.png", (296, 97, 463, 150)),
    (QUALITY / "00036_right.png", (296, 97, 463, 150)), (QUALITY / "00014_right.png", (296, 97, 632, 150)),
    (A1 / "kit2_wbmovie" / "shots" / "00047_right.png", (138, 43, 636, 95)), (QUALITY / "00050_right.png", (82, 145, 555, 192))],
    ids=["wb-ctemp", "wb-ctemp-again", "wb-auto", "two-slots", "two-slots-again", "one-slot", "menu-row", "list-row"])
def test_the_cursor_is_found_on_the_cameras_own_frames(path, box):
    """The camera's frames (2026-11-08): the White Balance chooser's orange text and the two-slot table's narrow cell
    (no bar; once nothing lit, so drive.py refused Enter) and the bars that worked before (the one-slot table's cell,
    a menu row, a list row). Skipped without runs/."""
    from camkit import live
    assert live.lit_box(load(need(path)).image) == box


UNLIT_VALUES = ("Standard", "Fast", "Large")          # the orange values on the menu page's unlit rows (factory)


@pytest.mark.parametrize("path, want, exact, absent", [
    (WB_MOVIE / "00055_down.png", "C.Temp./Filter", False, ()),
    (WB_MOVIE / "00072_down.png", "C.Temp./Filter", False, ()),
    (WB_MOVIE / "00062_right.png", "Auto", False, ()), (QUALITY / "00028_right.png", "HEIF", True, ()),
    (QUALITY / "00036_right.png", "HEIF", True, ()), (QUALITY / "00014_right.png", "HEIF", True, ()),
    (A1 / "kit2_wbmovie" / "shots" / "00047_right.png", "White Balance", False, UNLIT_VALUES),
    (QUALITY / "00050_right.png", "HEIF(4:2:0)", False, ())],
    ids=["wb-ctemp", "wb-ctemp-again", "wb-auto", "two-slots", "two-slots-again", "one-slot", "menu-row", "list-row"])
def test_the_lit_text_on_the_cameras_own_frames(path, want, exact, absent):
    """live.lit_text on the same frames, read by this computer's OCR (skipped without runs/ or an OCR engine): the
    chooser's lit item, the two-slot table's cell alone (not its row label or the other slot), the one-slot table and
    the list as before, and the menu row's own item, without the orange values of the unlit rows. The menu row's value
    is the camera's own setting of that day, so only its item name is checked (decision 16). The item name is compared
    as the guards fold it: OCR may add a stray glyph."""
    from camkit import live, ocr, safety
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = load(need(path))
    got = live.lit_text(f.image, path)
    fold = lambda t: safety.clean_label(safety.fold(t))           # noqa: E731
    assert (got == want) if exact else (fold(want) in fold(got)), got
    assert not [v for v in absent if fold(v) in fold(got)], f"an unlit row's value in the lit text: {got!r}"


def test_the_viewfinders_shooting_screen_is_the_shooting_screen():
    """The finder's layout (the eye sensor covered) draws its battery smaller, further right and higher: with that icon
    where the finder draws it a frame reads as the shooting screen, and a black frame without it does not."""
    from PIL import Image
    icon = np.asarray(Image.open(Path(screen.__file__).parent / "glyphs" / "battery_finder.png").convert("L"))
    assert screen.classify(screen.features(np.zeros((480, 640, 3), np.uint8))) != "shooting"
    a = np.zeros((480, 640, 3), np.uint8)       # a frame of its own: the reader keeps a frame's planes by the array
    x0, y0 = screen.BATTERY_V["battery_finder"][:2]
    a[y0:y0 + icon.shape[0], x0:x0 + icon.shape[1]] = icon[..., None]
    f = screen.features(a)
    assert f["battery_v"] > 0.85 and screen.classify(f) == "shooting"


@pytest.mark.parametrize("path", [PASS2 / "239508_closing.png", A1 / "vf_bright2" / "shots" / "00005_settled.png"],
                         ids=["battery-100", "battery-lower"])
def test_the_viewfinders_shooting_screen_on_the_cameras_own_frames(path):
    """The finder's shooting screen on the camera's own frames (skipped without runs/): the frame the template was cut
    from (2026-11-11, the battery at 100, the Level gauge drawn) and an older one with a lower battery, whose
    percentage starts where a wider cut ended, and no gauge."""
    assert read(path).kind == "shooting"
