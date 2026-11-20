"""A row's label where the camera draws an icon before it (camkit.screen.label_icons, page_model's covered_readings,
icon_vote, page_labels and icon_label, camkit.crawl.icon_entry): OCR read the a1 II's S&Q box as "Saa", "Sea" or "S&Q"
and the reader as "S&Q" on some frames, so two crawls of S&Q Settings minutes apart named its second row "Record
Setting" and two others "S&Q Record Setting" (runs/ILCE-1M2_fw4.00/kit2_plan3_crawl_shd30, _shd24, _shd120, _shd120b,
2026-11-19), and every page scan left S&Q Settings, ISO and IP Address Setting unlabelled. The label is now read to
the right of the icon, and stays as read wherever that cannot be told. The camera's frames where runs/ holds them
(skipped otherwise; the OCR ones also without the OCR helper); made-up rows otherwise. Nothing talks to a camera or a
reader."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import page_model as pm  # noqa: E402
from camkit import ocr, paths, screen  # noqa: E402
from camkit.crawl import RowResult, icon_entry  # noqa: E402
from camkit.frames import load  # noqa: E402

RUNS = paths.a1ii_root()
DARK, ORANGE, LIGHT, INK = (32, 32, 32), (178, 44, 0), (238, 238, 238), (221, 221, 221)


def frame(run, name):
    p = RUNS / run / "shots" / name
    if not p.exists():
        pytest.skip(f"{p} not present")
    return load(p)


def need_ocr():
    if ocr.engine() not in ocr.available():
        pytest.skip(f"the OCR engine {ocr.engine()!r} is not here")


# ---------------------------------------------------------------- made-up rows

BAND = (100, 153)          # a row's top and bottom


def page(bg=DARK):
    a = np.zeros((480, 640, 3), np.uint8)
    a[:, :] = DARK
    a[BAND[0] + 1:BAND[1] - 1, 55:636] = bg
    return a


def letters(a, x, n=4, colour=INK):
    """Letter-like strokes from x: each a 2 px outline 12 px wide and 26 tall, 3 px apart (no filled block, no light box
    with marks in it); the x after them."""
    for _ in range(n):
        a[114:140, x:x + 2] = colour
        a[114:116, x:x + 12] = colour
        a[126:128, x:x + 10] = colour
        x += 15
    return x


def box(a, x, w=23, h=20, colour=LIGHT, marks=True):
    """A light box at x, its marks (dark, the box's background) inside unless marks is False."""
    y = 116
    a[y:y + h, x:x + w] = colour
    if marks:
        for mx in (x + 4, x + 10, x + 16):
            a[y + 4:y + h - 4, mx:mx + 3] = a[BAND[0] + 2, 56]
    return x + w


def test_a_light_box_with_marks_in_it_is_an_icon_and_the_label_starts_after_it():
    a = page()
    end = box(a, 62)
    letters(a, end + 6)
    boxes, text_x = screen.label_icons(a, BAND, 55)
    assert boxes == ((62, end),) and text_x == end + 6


def test_letters_alone_are_no_icon():
    a = page()
    letters(a, 60, 6)
    assert screen.label_icons(a, BAND, 55) == ((), None)


def test_a_solid_mark_is_an_icon_and_two_icons_in_a_row_are_both_found():
    """The movie mark (a solid square) and then the S box of with Shutter Button."""
    a = page()
    a[118:134, 146:160] = LIGHT                  # solid
    end = box(a, 166, w=17)
    letters(a, end + 7)
    boxes, text_x = screen.label_icons(a, BAND, 140)
    assert boxes == ((146, 160), (166, end)) and text_x == end + 7


def test_a_light_box_on_the_orange_bar_is_an_icon():
    """On the lit row the box's marks are the bar's orange showing through."""
    a = page(ORANGE)
    end = box(a, 62)
    letters(a, end + 6)
    assert screen.label_icons(a, BAND, 55) == (((62, end),), end + 6)


def test_a_greyed_rows_box_on_the_orange_bar_is_an_icon():
    """A greyed row lit: its text and its box are grey 119 on the bar, below the light the bar's ink is otherwise."""
    grey = (119, 119, 119)
    a = page(ORANGE)
    end = box(a, 62, colour=grey)
    letters(a, end + 6, colour=grey)
    assert screen.label_icons(a, BAND, 55) == (((62, end),), end + 6)


def test_a_second_box_is_an_icon_only_close_after_the_first():
    """The movie mark and the S box are 6-7 px apart; a check box's text starts 20 px after it, and a B in that larger
    font can be a light box with marks in it."""
    for gap, want in ((7, 2), (20, 1)):
        a = page()
        a[118:134, 146:160] = LIGHT
        end = box(a, 160 + gap, w=17)
        letters(a, end + 7)
        boxes, text_x = screen.label_icons(a, BAND, 140)
        assert len(boxes) == want and text_x == (end + 7 if want == 2 else 160 + gap), gap


def test_a_box_too_narrow_or_with_no_room_after_it_is_none():
    """A box under 16 px with marks is a letter's size (B, R); a box with nothing after it gives no label to read."""
    a = page()
    end = box(a, 62, w=12)
    letters(a, end + 6)
    assert screen.label_icons(a, BAND, 55) == ((), None)
    a = page()
    box(a, 62)
    assert screen.label_icons(a, BAND, 55) == ((), None)


def test_covering_paints_the_icon_in_the_rows_colour_and_nothing_else():
    for bg in (DARK, ORANGE):
        a = page(bg)
        end = box(a, 62)
        letters(a, end + 6)
        boxes, _ = screen.label_icons(a, BAND, 55)
        out = screen.cover_icons(a, BAND, boxes)
        assert (out[BAND[0] + 2:BAND[1] - 2, 61:end + 1] == bg).all()
        assert (out[:, end + 2:] == a[:, end + 2:]).all() and (a[116:136, 62:end] != bg).any()


# ---------------------------------------------------------------- the text rules

def test_icon_lead_says_what_a_reading_has_in_front_of_the_label_right_of_the_icon():
    assert pm.icon_lead("Saa Record Setting", "Record Setting") == ("Record Setting", "Saa", False)
    assert pm.icon_lead("S&Q S&Q Settings", "S&Q Settings") == ("S&Q Settings", "S&Q", False)
    assert pm.icon_lead("RISO", "ISO") == ("ISO", "R", True)
    assert pm.icon_lead("LAN IP Address Setting", "IP Address Setting") == ("IP Address Setting", "LAN", False)
    assert pm.icon_lead("S&Q Settings", "S&Q Settings") is None                  # nothing in front
    assert pm.icon_lead("Frame Rate Settings", "Record Setting") is None          # another label
    assert pm.icon_lead("Saa Record Setting", "") is None


def test_a_crawls_label_loses_what_it_read_of_the_icon_and_says_so():
    new, rec = pm.icon_label("S&Q Record Setting", "Record Setting", [(62, 85)], ["Frame Rate Settings"])
    assert new == "Record Setting"
    assert rec == {"icons": [[62, 85]], "read": "S&Q Record Setting", "covered": "Record Setting", "left_out": "S&Q"}


def test_a_crawls_label_read_whole_stays_and_a_real_word_after_the_icon_is_kept():
    """"S&Q Settings" is a label that itself follows an S&Q box: OCR right of the box reads all of it."""
    for label in ("Record Setting", "S&Q Settings"):
        new, rec = pm.icon_label(label, label, [(62, 85)])
        assert new == label and "left_out" not in rec and "kept" not in rec


@pytest.mark.parametrize("label,covered,others,why", [
    ("Animal/Bird", "Bird", [], "glued"),                          # a checkbox before Bird; the label's own slash
    ("RISO", "ISO", [], "glued"),
    ("SteadyShot Adjust.", "Adjust.", [], "longer than the icon"),
    ("S&Q Shoot Mode", "Shoot Mode", ["Shoot Mode"], "the icon tells them apart"),
    ("S&Q Record Setting", "", [], "reads nothing"),
    ("Focal Length", "(W)Focal Length", [], "does not end"),
])
def test_a_crawls_label_stays_as_read_where_it_cannot_tell(label, covered, others, why):
    new, rec = pm.icon_label(label, covered, [(62, 85)], others)
    assert new == label and why in rec["kept"] and "left_out" not in rec


def test_a_pages_vote_takes_the_label_right_of_the_icon_where_a_reader_agrees():
    """S&Q Settings as every scan read it (kit2_page_scan_movie_1118, page 4/59 row 2) without the label read by eye."""
    labels = {"ocr": "Sea S&Q Settings", "ocr2": "S&Q S&Q Settings", "vllm": "S&Q Settings"}
    assert pm.vote(labels) == (None, [])
    covered = {"ocr": "S&Q Settings", "ocr2": "S&Q Settings"}
    label, by, rec = pm.icon_vote(labels, covered, None, [], [(145, 168)])
    assert (label, by) == ("S&Q Settings", ["ocr", "ocr2", "vllm"]) and "kept" not in rec
    assert rec["left_out"] == {"ocr": "Sea", "ocr2": "S&Q"}


def test_a_pages_vote_leaves_out_what_the_reader_read_of_the_icon_too():
    labels = {"ocr": "MR Camera Set. Memory", "ocr2": "MR Camera Set. Memory", "vllm": "MR Camera Set. Memory"}
    covered = {"ocr": "Camera Set. Memory", "ocr2": "Camera Set. Memory"}
    label, by, rec = pm.icon_vote(labels, covered, *pm.vote(labels), [(145, 168)])
    assert label == "Camera Set. Memory" and "vllm" in by and rec["left_out"]["vllm"] == "MR"


@pytest.mark.parametrize("labels,covered,old,why", [
    # an icon found where there is none: the first letter painted over; the reader reads the word whole
    ({"ocr": "Wired LAN Connect", "ocr2": "Wired LAN Connect", "vllm": "Wired LAN Connect"},
     {"ocr": "ired LAN Connect", "ocr2": "ired LAN Connect"}, "Wired LAN Connect", "only OCR"),
    # no reader but OCR (an OSD scan read without one)
    ({"ocr": "AD IP Address Setting", "ocr2": "LANIP Address Setting"},
     {"ocr": "IP Address Setting", "ocr2": "IP Address Setting"}, None, "only OCR"),
    # the reader reads its own slip ("Circr."): nothing agrees with it
    ({"ocr": "& Circ. of Focus Point", "ocr2": "Circ. of Focus Point", "vllm": "Circr. of Focus Point"},
     {"ocr": "Circ. of Focus Point", "ocr2": "Circ. of Focus Point"}, "Circ. of Focus Point", "only OCR"),
    # a new label that is not the old one with something in front left out
    ({"ocr": "Proxy Settings", "vllm": "Proxy Settings"}, {"ocr": "Proxy Settings"}, "Log Shooting Setting",
     "is not the label voted before"),
])
def test_a_pages_vote_keeps_the_label_voted_before_where_it_cannot_tell(labels, covered, old, why):
    label, by, rec = pm.icon_vote(labels, covered, old, ["x"], [(145, 168)])
    assert label == old and by == ["x"] and why in rec["kept"]


def test_a_page_keeps_the_icon_where_it_tells_two_rows_apart():
    """The a1 II's Shooting Mode page: Shoot Mode, and the Shoot Mode an S&Q box and a dial are drawn before
    (kit2_diffset_movie_scan, page 8/59)."""
    readings = [{"ocr": "Shoot Mode", "ocr2": "Shoot Mode", "vllm": "Shoot Mode"},
                {"ocr": "&QI Shoot Mode", "ocr2": "S&Q Shoot Mode", "vllm": "S&Q Shoot Mode"}]
    icons = {1: ((147, 201), ((146, 168),), 180)}
    covered = {1: {"ocr": "Shoot Mode", "ocr2": "Shoot Mode"}}
    (l0, _, i0), (l1, by1, i1) = pm.page_labels(readings, icons, covered)
    assert (l0, i0, l1) == ("Shoot Mode", None, "S&Q Shoot Mode") and "vllm" in by1
    assert "the icon tells them apart" in i1["kept"]


# ---------------------------------------------------------------- the camera's frames

@pytest.mark.parametrize("run,name,row,count,text_x", [
    ("kit2_plan3_crawl_shd120", "00008_down.png", 0, 1, 91),       # S&Q box, a submenu row
    ("kit2_plan3_crawl_shd120", "00008_down.png", 1, 1, 92),       # the same on the orange bar
    ("kit2_page_scan_movie_1118", "00242_down.png", 0, 1, 172),    # the movie mark
    ("kit2_page_scan_movie_1118", "00242_down.png", 2, 1, 174),    # S&Q box before S&Q Settings, lit
    ("kit2_page_scan_movie_1118", "00242_down.png", 5, 1, 175),    # Px box
    ("kit2_page_scan_1118p", "00102_down.png", 1, 1, 172),         # the stills mark before ISO
    ("kit2_page_scan_1118p", "00256_down.png", 1, 1, 172),         # LAN box
    ("kit2_page_scan", "00219_down.png", 1, 2, 199),               # the movie mark, then the S box
    ("kit2_proxy3_crawl", "00019_down.png", 2, 1, 92),             # Px box of a greyed row on the orange bar
    ("kit2_page_scan_1118p", "00057_down.png", 0, 1, 176),         # MR box of a greyed row on the orange bar
    ("kit2_breadth_crawl", "00505_down.png", 2, 1, 117),           # a check box; the B of Bird (larger font) is no icon
])
def test_the_icons_on_the_cameras_frames(run, name, row, count, text_x):
    f = frame(run, name)
    s = screen.read(f)
    boxes, got = screen.label_icons(f.image, s.rows[row], 55 if s.kind == "submenu" else 140)
    assert len(boxes) == count and abs(got - text_x) <= 2


@pytest.mark.parametrize("run,name,rows", [
    ("kit2_page_scan_1118p", "00102_down.png", (0, 3)),            # BULB Timer Settings; ISO AUTO Min. SS, greyed
    ("kit2_page_scan_1118p", "00256_down.png", (0, 2)),            # Wired LAN Connect (a wide W); Display Wired LAN Info.
    ("kit2_page_scan_movie_1118", "00242_down.png", (4,)),         # Log Shooting Setting
])
def test_rows_with_no_icon_on_the_cameras_frames(run, name, rows):
    f = frame(run, name)
    s = screen.read(f)
    for row in rows:
        assert screen.label_icons(f.image, s.rows[row], 140) == ((), None), row


@pytest.mark.parametrize("run,name,row,want", [
    ("kit2_plan3_crawl_shd120", "00008_down.png", 1, "Record Setting"),
    ("kit2_plan3_crawl_shd30", "00010_down.png", 1, "Record Setting"),
    ("kit2_plan3_crawl_shd120", "00008_down.png", 0, "Frame Rate Settings"),
    ("kit2_page_scan_movie_1118", "00242_down.png", 2, "S&Q Settings"),
    ("kit2_page_scan_1118p", "00102_down.png", 1, "ISO"),
    ("kit2_page_scan_1118p", "00256_down.png", 1, "IP Address Setting"),
    ("kit2_page_scan", "00219_down.png", 1, "with Shutter Button"),
])
def test_ocr_right_of_the_icon_on_the_cameras_frames(run, name, row, want):
    need_ocr()
    f = frame(run, name)
    s = screen.read(f)
    column = pm.SUBMENU_LABEL if s.kind == "submenu" else pm.MENU_LABEL
    boxes, text_x = screen.label_icons(f.image, s.rows[row], column[0])
    got = pm.covered_readings({0: (f.image, {row: (s.rows[row], boxes, text_x)})}, column, {"ocr": None})
    assert pm._key(got[0][row]["ocr"]) == pm._key(want)


def test_a_reading_that_kept_a_piece_of_the_icon_is_no_reading(monkeypatch):
    """OCR's first line in the row starting left of the painted icon's end (a piece of the icon read as a letter) or
    past where the text starts (the label's first word lost) gives nothing: the label stays as read."""
    f = frame("kit2_plan3_crawl_shd120", "00008_down.png")
    s = screen.read(f)
    band = s.rows[1]
    rows = {1: (band, ((62, 85),), 92)}
    for x in (70, 120):
        monkeypatch.setattr(pm.ocr, "read", lambda paths, eng=None, x=x: {
            p: [ocr.Line("Record Setting", 1.0, x, band[0] + 10, 160, 34)] for p in paths})
        assert pm.covered_readings({0: (f.image, rows)}, pm.SUBMENU_LABEL, {"ocr": None}) == {0: {}}
    monkeypatch.setattr(pm.ocr, "read", lambda paths, eng=None: {
        p: [ocr.Line("Record Setting", 1.0, 87, band[0] + 10, 160, 34)] for p in paths})
    assert pm.covered_readings({0: (f.image, rows)}, pm.SUBMENU_LABEL, {"ocr": None}) == {0: {1: {"ocr": "Record Setting"}}}


def test_ocr_right_of_the_icons_is_one_batch_an_engine(monkeypatch):
    """Every covered frame of a scan read in one call per engine, as page_model reads the frames themselves."""
    a = page()
    end = box(a, 62)
    letters(a, end + 6)
    rows = {0: (BAND, ((62, end),), end + 6)}
    calls = []

    def read(paths, eng=None):
        calls.append((len(paths), eng))
        return {p: [ocr.Line("Text", 1.0, end + 2, BAND[0] + 10, 60, 30)] for p in paths}
    monkeypatch.setattr(pm.ocr, "read", read)
    got = pm.covered_readings({n: (a, rows) for n in range(5)}, pm.SUBMENU_LABEL, {"ocr": None, "ocr2": "rapidocr"})
    assert calls == [(5, None), (5, "rapidocr")]
    assert all(got[n] == {0: {"ocr": "Text", "ocr2": "Text"}} for n in range(5))


@pytest.mark.parametrize("run,name", [("kit2_plan3_crawl_shd120", "00008_down.png"),
                                      ("kit2_plan3_crawl_shd30", "00010_down.png")])
@pytest.mark.parametrize("read", ["S&Q Record Setting", "Saa Record Setting", "Record Setting"])
def test_the_crawl_names_s_and_q_settings_second_row_one_way_whatever_the_readers_read(run, name, read):
    """The four crawls of 2026-11-19: the reader read the S&Q box into the row's label on kit2_plan3_crawl_shd120's
    frame (and _shd120b's, the same picture, answered from the reader's cache) and not on _shd30's or _shd24's; OCR
    read "Saa" on all of them. The label is the camera's own each time, and the row's record says what was left out."""
    need_ocr()
    f = frame(run, name)
    cam = SimpleNamespace(frame=f)
    s = screen.read(f)
    entry = {"label": read, "never_open": None, "readings": ["Sea Record Setting"]}      # a reading other than the label
    got = icon_entry(cam, s, 1, entry, [{"label": "Frame Rate Settings"}, entry])
    assert got["label"] == "Record Setting" and got["icon"]["read"] == read
    assert got["icon"].get("left_out") == (None if read == "Record Setting" else read.split()[0])
    assert got["readings"] == ["Sea Record Setting", read]          # the label as read joins them: the safety checks read


@pytest.mark.parametrize("raw,rest", [("Clip Flag", "Flag"), ("Add Item", "Item"), ("FTP Function", "Function")])
def test_a_bare_label_shortened_past_the_word_the_never_open_list_names_stays_unopened(monkeypatch, raw, rest):
    """labels(cam) may give a bare label, with no never-open reason stored: the reason is then the label as read judged,
    never the shortened label, which can leave out the word the list names (the review of 2026-11-20)."""
    from camkit import crawl as C
    from camkit import safety
    assert safety.never_open(raw) and not safety.never_open(rest)
    f = frame("kit2_plan3_crawl_shd120", "00008_down.png")
    s = screen.read(f)
    band = s.rows[1]
    monkeypatch.setattr(pm.ocr, "read", lambda paths, eng=None: {
        p: [ocr.Line(rest, 1.0, 92, band[0] + 10, 160, 30)] for p in paths})
    entry = {"label": raw, "readings": [raw]}
    got = icon_entry(SimpleNamespace(frame=f), s, 1, entry, [{"label": "Frame Rate Settings"}, entry])
    assert got["label"] == rest and got["never_open"] == safety.never_open(raw)
    why, decided = C.closed_row({"page": "S&Q Settings"}, got)
    assert why and decided is None


def test_the_crawl_reads_no_icon_without_a_saved_frame(tmp_path):
    """The menu twin (no frame) and a frame that cannot be loaded: the entry as read."""
    entry = {"label": "S&Q Record Setting", "readings": ["S&Q Record Setting"]}
    s = SimpleNamespace(rows=[(45, 97), (97, 150)])
    assert icon_entry(SimpleNamespace(), s, 1, entry, [entry]) is entry
    bad = tmp_path / "00001_down.png"
    bad.write_bytes(b"not a picture")
    assert icon_entry(SimpleNamespace(frame=SimpleNamespace(path=bad)), s, 1, entry, [entry]) is entry


def test_a_crawl_on_a_network_run_or_a_look_lap_reads_no_icon(monkeypatch):
    """They keep no text read off the screen: the crawl asks icon_entry nothing there."""
    from camkit import crawl as C
    asked = []
    monkeypatch.setattr(C, "icon_entry", lambda *a, **k: asked.append(1) or a[3])
    monkeypatch.setattr(C, "visit_row", lambda cam, s, page, slot, entry, *a, **k: RowResult(page["page"], slot,
                                                                                              entry["label"], "walked"))

    class Cam:
        presses = 0

        def __init__(self):
            self.n = 0

        def read(self):
            return SimpleNamespace(row=self.n % 2, signature=f"s{self.n % 2}", struct=(), bits=np.zeros(0),
                                   kind="submenu")

        def press(self, key, **kw):
            self.n += 1
    monkeypatch.setattr(C, "same_state", lambda a, b, tol=2: a.signature == b.signature)
    labels = lambda cam: ("k", ["A", "B"])                 # noqa: E731
    for kw, want in (({}, 2), ({"look": True}, 0), ({"network": {"Wi-Fi": "2026-11-13"}}, 0)):
        asked.clear()
        out = C.crawl_submenu(Cam(), labels, ("Sub",), C.Place(None), **kw)
        assert len(out.rows) == 2 and len(asked) == want, kw


def test_crawl_run_writes_the_icon_record_and_a_withholding_walk_drops_it():
    import crawl_run
    r = RowResult("S&Q Settings", 1, "Record Setting", "walked", kind="list",
                  icon={"icons": [[62, 85]], "read": "S&Q Record Setting", "covered": "Record Setting", "left_out": "S&Q"})
    row = crawl_run.summary(r)
    assert row["icon"]["left_out"] == "S&Q"
    assert "icon" not in crawl_run.kept_row(row, {"Record Setting"})
    assert "icon" not in crawl_run.summary(RowResult("S&Q Settings", 0, "Frame Rate Settings", "walked"))


# ---------------------------------------------------------------- the page scans, as page_model reads them now

@pytest.mark.parametrize("run,page_no,row,leave_out,want", [
    ("kit2_page_scan_movie_1118", "4/59", 2, "eye", "S&Q Settings"),
    ("kit2_page_scan_1118p", "17/63", 1, "eye", "ISO"),
    ("kit2_page_scan_1118p", "45/63", 1, "eye", "IP Address Setting"),
    ("kit2_page_scan_1118p", "7/63", 1, None, "Camera Set. Memory"),
    ("kit2_diffset_movie_scan", "8/59", 4, None, "S&Q Shoot Mode"),         # kept: the icon tells it from Shoot Mode
])
def test_the_page_scans_labels_read_right_of_the_icon(run, page_no, row, leave_out, want):
    """Each page's readings as model.json keeps them (the label read by eye left out where named), voted as page_model
    votes them now on the page's own frame."""
    need_ocr()
    model = RUNS / run / "model.json"
    if not model.exists():
        pytest.skip(f"{model} not present")
    p = next(p for p in json.loads(model.read_text(encoding="utf-8")) if p["page"] == page_no)
    path = RUNS / run / "shots" / p["frame"]
    readings = [{k: v for k, v in r["readings"]["label"].items() if k != leave_out} for r in p["rows"]]
    icons = {path: pm.page_icons(path, len(readings))}
    engines = {"ocr": None, **({"ocr2": ocr.second()} if ocr.second() else {})}
    covered = pm.covered_readings(icons, pm.MENU_LABEL, engines)
    labels = pm.page_labels(readings, icons[path][1], covered[path])
    assert labels[row][0] == want
