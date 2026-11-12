"""Offline tests: file format, safety rules, run numbering, pixel reader on archived frames.

Run: .venv/bin/python -m pytest kit/tests -q
Frames and settings files live under runs/ (not versioned), the a1 II's in runs/ILCE-1M2_fw4.00/ (camkit.paths); tests
that need them skip when absent.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, definitions, paths, safety, screen  # noqa: E402
from camkit.frames import load  # noqa: E402
from camkit.runs import Run  # noqa: E402

A1 = paths.a1ii_root()          # the a1 II's runs in this clone: the frames these tests read
DEFINITION = definitions.path(paths.A1II)          # the a1 II's definition, editor/definitions/ILCE-1M2_fw4.00.json
SAMPLE = definitions.sample(definitions.load(paths.A1II))          # and its sample, beside it
START = A1 / "explore_stills_pre20261027" / "START.DAT"
SHOTS = A1 / "explore_stills" / "shots"


def need(path: Path):
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


# ---------------------------------------------------------------- .DAT files

def test_camset_layout():
    sample = START if START.exists() else SAMPLE
    cs = camset.read(need(sample))
    assert cs.model == "ILCE-1M2"
    assert len(cs.sections) == 13
    assert len(cs.sections[0]) == 1415
    assert all(len(s) == 1057 for s in cs.sections[1:])
    assert cs.checksums_ok


def test_camset_edit_roundtrip(tmp_path):
    sample = START if START.exists() else SAMPLE
    cs = camset.read(need(sample))
    rec = cs.get(0, 0x0489)                     # Auto Monitor OFF, one byte
    new = bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]
    out = tmp_path / "edited.DAT"
    out.write_bytes(camset.with_values(cs, {(0, 0x0489): new}))
    edited = camset.read(out)
    assert edited.checksums_ok
    changes = camset.diff(cs, edited)
    assert [(c.section, c.id) for c in changes] == [(0, 0x0489)]
    assert camset.diff(cs, cs) == []


def test_diff_checksums_as_the_editor_has_them(tmp_path):
    """K-36: a file whose header checksum alone fails is compared (the editor opens it, flagged); one whose records'
    checksum fails is refused (the editor does not open it); read() itself refuses either by default; two bodies'
    files and two layouts are never compared in part."""
    cs = camset.read(SAMPLE)
    d = bytearray(cs.data)
    site = cs.block.header_checksum.at.n
    d[site] ^= 0xFF                                                   # the header checksum alone
    header = camset.parse(bytes(d), check=False)
    assert not header.header_ok and header.trailer_ok and not header.checksums_ok
    with pytest.raises(ValueError, match="checksum"):
        camset.parse(bytes(d))
    assert camset.diff(cs, header) == []
    rec = cs.get(0, 0x0489)
    d = bytearray(cs.data)
    d[rec.offset + 8] ^= 1                                            # a record's byte, the sum not worked out again
    body = camset.parse(bytes(d), check=False)
    assert body.header_ok and not body.trailer_ok
    with pytest.raises(ValueError, match="records checksum"):
        camset.diff(cs, body)
    with pytest.raises(ValueError, match="records checksum"):
        camset.diff(body, cs)
    other = camset.parse(cs.block.sealed(cs.block.with_text(cs.data, "model", "ILCE-7M5")), check=False)
    with pytest.raises(ValueError, match="two bodies"):
        camset.diff(cs, other)
    short = camset.Camset(model=cs.model, saved=cs.saved, sections=cs.sections[:5])
    with pytest.raises(ValueError, match="layouts differ"):
        camset.diff(cs, short)


# ---------------------------------------------------------------- safety

@pytest.mark.parametrize("label", ["Format", "  Delete", "Screen Reader", "Auto Power OFF Temp.", "Language",
                                   "Wired LAN Connect", "Cleaning Mode", "Area/Date/Time Setting", "Audio signals",
                                   "AF Illuminator", "Tally Lamp", "Save/Load Settings", "S Version",
                                   "Forced File Number Reset", "Send", "Select on Cam & Send", "Playback > Delete > Delete Slot1/2",
                                   "Setup > Setup Option > Auto Pixel Mapping", "Airplane Mode",
                                   "Playback/Monitor. Vol.", "Reset", "PP Reset", "Copy"])
def test_never_open(label):
    assert safety.never_open(label)


@pytest.mark.parametrize("label", ["File Format", "Focus Area", "Delete confirm.", "Time Code Preset",
                                   "S Focus Area Limit", "White Balance", "Drive Mode", "Auto Monitor OFF",
                                   "AF Area Auto Clear", "AF Area Registration", "Area Disp. dur Tracking",
                                   "File Number", "Folder Name", "Delete pressing twice",
                                   "Pre-Capture", "Playback > Delete > Delete confirm.",
                                   "Airplane", "Car/Train", "Insect"])           # Recognition Target subjects
def test_walked(label):
    assert safety.never_open(label) is None


def test_inputs():
    safety.check_input("down")
    safety.check_input("front")
    safety.check_input("delete", allow={"delete"})
    for name in ("movie", "af_on", "c1"):
        with pytest.raises(safety.Refused):
            safety.check_input(name, allow={name})
    with pytest.raises(safety.Refused):
        safety.check_input("delete")


def test_an_allowance_given_as_a_string_is_that_one_name():
    """allow="playback" allows Playback, never the names inside it ("back"): a string was read as its substrings."""
    safety.check_input("playback", allow="playback")
    for name in ("back", "c4"):
        with pytest.raises(safety.Refused):
            safety.check_input(name, allow="playback" if name == "back" else "c4 c5")


def test_a_block_with_a_magic_that_is_not_ascii_is_refused_by_name():
    block = json.loads(DEFINITION.read_text(encoding="utf-8"))["camera"]["file"]
    with pytest.raises(camset.BlockError, match="not ASCII"):
        camset.Block.parse({**block, "magic": {**block["magic"], "bytes": "CАMSET"}})


def test_confirmation_text():
    assert safety.confirmation("Format? All data will be deleted")
    assert safety.confirmation("Resets the still image file number and creates a new folder.")
    assert safety.confirmation("Shoot 4 Shots: Interval 1 Sec") is None
    # the File Format list is a setting, not a card format (2026-10-31); a real format still counts
    assert safety.confirmation("Shooting 6/61 File Format XAVC HS 8K XAVC HS 4K XAVC S 4K") is None
    assert safety.confirmation("Format Slot 1 All data will be deleted. Format? Enter Cancel")
    # Delete pressing twice On warns about the setting with only OK (frame 37079); any more words, or
    # the real delete screens, still count
    warn = ("If the delete button is pressed in the delete confirmation screen, the target image is deleted. "
            "Be careful not to accidently delete.")
    assert safety.confirmation(warn + " OK") is None
    assert safety.confirmation(warn + " Delete all images? OK Cancel")
    assert safety.confirmation("Delete this image? Delete Cancel")


# ---------------------------------------------------------------- run folders

def test_numbering_continues(tmp_path):
    r = Run("t", root=tmp_path)
    a = r.shot_path("open")
    a.write_bytes(b"x")
    b = Run("t", root=tmp_path).shot_path("down")      # a resumed run
    assert a.name.startswith("00001_") and b.name.startswith("00002_")
    assert not r.stop_requested()
    (tmp_path / "t" / "STOP").write_text("")
    assert r.stop_requested()


def test_jsonl_leaves_out_a_line_cut_short_at_the_end_only(tmp_path):
    """camkit.jsonl: a crash leaves the last line of a log cut short; a line damaged anywhere else is said."""
    from camkit import jsonl
    f = tmp_path / "x.jsonl"
    jsonl.append(f, {"a": 1})
    jsonl.append(f, {"a": 2})
    assert f.read_bytes() == b'{"a": 1}\n{"a": 2}\n'
    f.write_text('{"a": 1}\n\n{"a": 2}\n{"a": 3', encoding="utf-8")
    assert jsonl.read(f) == [{"a": 1}, {"a": 2}]
    f.write_text('{"a": 1}\n{"a"\n[3]\n{"a": 4}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        jsonl.read(f)
    assert jsonl.read(f, bad="skip") == [{"a": 1}, {"a": 4}]
    f.write_text('[3]\n{"a": 4}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not a JSON object"):
        jsonl.read(f)
    assert jsonl.read(tmp_path / "none.jsonl") == []
    # an entry added after a cut line starts a line of its own: it is not glued onto the cut one and lost with it
    f.write_text('{"a": 1}\n{"a": 2, "b', encoding="utf-8")
    jsonl.append(f, {"a": 3})
    assert jsonl.read(f, bad="skip") == [{"a": 1}, {"a": 3}]
    (tmp_path / "empty.jsonl").write_bytes(b"")
    jsonl.append(tmp_path / "empty.jsonl", {"a": 1})
    assert (tmp_path / "empty.jsonl").read_bytes() == b'{"a": 1}\n'


# ---------------------------------------------------------------- pixel reader

FRAMES = {
    # file: (kind, glyphs present, slots, at_start)
    "00002_m.png": ("menu", set(), None, None),
    "00001_m.png": ("shooting", set(), None, None),
    "00486_open.png": ("notice", set(), None, None),
    "06536_down.png": ("dialog", {"up", "down"}, ["icon", "icon", "selected", "icon", "icon"], False),
    "02478_right.png": ("dialog", {"up", "down", "side_left", "side_right", "strip_left", "strip_right"},
                        ["empty", "icon", "selected", "icon", "empty"], False),
    "03995_down.png": ("dialog", {"up", "down", "sub_box"}, ["icon", "icon", "selected", "icon", "icon"], False),
    "00694_open.png": ("dialog", {"up", "down"}, ["empty", "empty", "selected", "icon", "icon"], True),
    "06751_up.png": ("checkgrid", set(), None, None),   # checkbox grid (Focus Area Limit)
    "01097_down.png": ("fields", set(), None, None),    # number fields (Shooting Start Time)
}


@pytest.mark.parametrize("name", sorted(FRAMES))
def test_screen_reader(name):
    kind, glyphs, slots, at_start = FRAMES[name]
    s = screen.read(load(need(SHOTS / name)))
    assert s.kind == kind
    if kind == "dialog":
        assert {g for g, on in s.glyphs.items() if on} == glyphs
        assert s.slots == slots
        assert s.at_start == at_start
    if kind == "menu":
        assert s.row == 2


def test_menu_cursor_in_group_column():
    # expanded group column, no orange row bar: caught mid-way through the menu's opening animation
    # by a single early grab (the settled frame, 00115, has the cursor on a row). It is a menu with no focus
    # yet, not the group column: a Right sent to it opened the row the cursor landed on (2026-11-06)
    s = screen.read(load(need(A1 / "kit2_selftest" / "shots" / "00002_menu-open.png")))
    assert (s.kind, s.focus, s.group, s.row) == ("menu", None, 0, None)
    s = screen.read(load(need(SHOTS / "00002_m.png")))
    assert (s.kind, s.focus, s.group, s.row) == ("menu", "rows", 1, 2)
    # the group column at rest: the group names drawn in full, the rows panel from x~370
    s = screen.read(load(need(A1 / "kit2_hdmi_watch" / "shots" / "00561_seen.png")))
    assert (s.kind, s.focus, s.row) == ("menu", "groups", None)


def test_menu_focus_follows_the_rows_panel():
    """_menu: the rows panel's left edge says which column has the focus; between its two places the menu is
    moving and has no focus, whatever else the frame shows (synthetic pages: the group column's grey, the
    panel's lighter grey from PANEL, an orange row bar when BAR)."""
    import numpy as np

    def page(panel, bar=None):
        a = np.full((480, 640, 3), 16, np.uint8)
        a[:40, :] = 10                                   # the breadcrumb band
        a[45:425, panel:] = 33                           # the rows panel
        a[425:, :] = 10
        if bar:
            a[bar[0]:bar[1], panel + 5:636] = (180, 70, 0)
        return a

    for panel, bar, focus in ((136, (43, 95), "rows"), (136, None, None), (370, None, "groups"),
                              (216, None, None), (216, (43, 95), None), (290, None, None)):
        s = screen.Screen(kind="menu")
        screen._menu(page(panel, bar), s)
        assert s.focus == focus, (panel, bar, s.focus)
        assert screen._panel_x(screen._grey(page(panel, bar))) == panel


def test_each_frame_keeps_its_own_planes():
    """The pixel reader's planes are computed once per frame. They were one dict updated in place: a frame's planes
    became the next frame's under a caller still reading them, and pass1_labels reads frames on eight threads."""
    import threading
    import numpy as np
    one = np.zeros((480, 640, 3), np.uint8)
    one[100:150, 140:636] = (235, 90, 20)                           # an orange bar
    two = np.zeros((480, 640, 3), np.uint8)
    p1 = screen._planes(one)
    worker = threading.Thread(target=screen._planes, args=(two,))
    worker.start()
    worker.join()
    screen._planes(two)
    assert p1["a"] is one and p1["orange"][120, 300] and screen._orange(one)[120, 300]
    assert not screen._orange(two).any()


def test_dialog_signatures_differ():
    sigs = {screen.read(load(need(SHOTS / n))).signature for n in
            ("06536_down.png", "03995_down.png", "00694_open.png", "02478_right.png")}
    assert len(sigs) == 4


def test_hdmi_calibration():
    # a 1080p HDMI frame from the Cam Link 4K (2026-10-28): the config crop must land the menu on the
    # same 640x480 layout as the OSD (Setup > External Output, cursor on HDMI Info. Display)
    import numpy as np
    from PIL import Image
    from camkit import config
    from camkit.frames import Frame, canonical
    img = np.asarray(Image.open(need(A1 / "kit2_hdmi" / "calibration_1080p.png")).convert("RGB"))
    s = screen.read(Frame(canonical(img, tuple(config()["hdmi"]["crop"])), 0))
    assert (s.kind, s.focus, s.row) == ("menu", "rows", 2)


@pytest.mark.parametrize("name", ["00117_start-osd.png", "00118_start-hdmi.png"])
def test_shooting_screen_without_bottom_boxes(name):
    # 2026-10-28, lens cap on: OSD leaves the exposure readouts out, HDMI shows them; neither has boxes
    s = screen.read(load(need(A1 / "kit2_selftest" / "shots" / name)))
    assert s.kind == "shooting"


@pytest.mark.parametrize("name,kind", [("kit2_pass2/shots/117031_menu.png", "shooting"),
                                       ("kit2_orient/shots/00004_right.png", "unknown"),
                                       ("kit2_pass2/shots/117144_live-start.png", "shooting"),
                                       ("kit2_pass2/shots/117146_right.png", "unknown"),
                                       # Focus Map tints live view red: frame lines like a notice's
                                       ("kit2_pass2/shots/118760_after-download.png", "shooting")])
def test_turned_screens(name, kind):
    # 2026-10-30, camera held grip down, then grip up: HDMI shows the shooting screen turned (battery
    # top left / bottom right; grip up had read as a Custom Key page), and the Focus Area dialog turned
    # too, which the landscape readers must not take for anything
    s = screen.read(load(need(A1 / name)))
    assert s.kind == kind


def test_blinking_blocks_not_one_way_changes():
    # 2026-10-28: the readouts blink while connected; a mask learned across a menu opening hid the
    # next press. Only blocks that go back and forth count as blinking.
    import collections
    import threading
    import numpy as np
    from camkit.frames import HdmiSource
    h = HdmiSource.__new__(HdmiSource)                  # no device: feed the history by hand
    h._lock, h._hist = threading.Lock(), collections.deque()
    a, b, menu = np.zeros((60, 80)), np.zeros((60, 80)), np.full((60, 80), 50.0)
    b[55:58, 40:50] = 100                               # the readout strip toggles
    dialog = np.full((60, 80), 120.0)
    for frames, expected in (([a, b] * 6 + [menu] * 10, 30),          # the menu opening is not masked
                             ([a, b] * 15, 30),                         # the strip is
                             ([menu] * 5 + [dialog] * 5 + [menu] * 5, 0),   # menu -> dialog -> menu: nothing
                             ([menu, dialog] * 5, 0)):                  # repeated big changes: nothing
        h._hist.clear()
        h._hist.extend((i * 0.06, sm) for i, sm in enumerate(frames))
        assert int(h.noisy(len(frames) * 0.06).sum()) == expected


LISTS = {
    # file: (cursor slot, options visible, saved slot, scrollbar?, at_start, at_end, options estimate)
    "07320_down.png": (2, 3, 0, False, False, True, 3),      # JPEG/HEIF Switch
    "07237_open.png": (0, 2, 0, False, True, False, 2),      # Enlarge Initial Position (cursor on saved)
    "00010_down.png": (3, 5, 0, False, False, False, 5),     # Auto Monitor OFF
    "07501_right.png": (1, 6, None, True, False, False, 29), # Image Jump, Front dial (27 values known)
    "07330_down.png": (4, 6, 2, True, False, False, 9),      # Play Speed for Interval
}


@pytest.mark.parametrize("name", sorted(LISTS))
def test_list_popup(name):
    row, count, saved, scroll, start, end, est = LISTS[name]
    s = screen.read(load(need(SHOTS / name)))
    assert s.kind == "list"
    assert (s.row, s.count, s.current, s.scroll is not None) == (row, count, saved, scroll)
    assert (s.at_start, s.at_end, s.options_estimate) == (start, end, est)


@pytest.mark.parametrize("name,row", [("00312_right_late.png", 0),   # NR Shooting Settings
                                      ("00073_downx3.png", 3)])      # HDMI Output Settings, RAW Output
def test_submenu_page(name, row):
    s = screen.read(load(need(SHOTS / name)))
    assert (s.kind, s.focus, s.row) == ("submenu", "rows", row)


def test_submenu_wraps_old_walker():
    # the old walker pressed Down x3 in a 3-row submenu and came back to the same row every time
    sigs = {screen.read(load(need(SHOTS / f"{n}.png"))).signature for n in ("00314_downx3", "00316_downx3")}
    assert len(sigs) == 1


FIELDS = {
    # file: (active field, fields, ▲ shown, ▼ shown)
    "01097_down.png": (0, 2, True, True),     # Shooting Start Time: min | sec
    "03420_down.png": (0, 2, True, False),    # ISO Range Limit at ISO 102400: only ▲ (end of range)
    "01936_down.png": (0, 1, True, True),     # Shooting Interval, with an info panel
    "02261_down.png": (1, 4, True, True),     # Number of Shots: one box per digit
    "03081_down.png": (1, 3, True, True),     # Exposure Time, with the valid range in text
}


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_number_fields(name):
    s = screen.read(load(need(SHOTS / name)))
    assert s.kind == "fields"
    assert (s.field, s.count, s.glyphs["up"], s.glyphs["down"]) == FIELDS[name]


@pytest.mark.parametrize("name", ["00880_up.png", "04031_down.png", "05181_up.png", "07960_up.png", "08311_up.png"])
def test_number_fields_lookalikes(name):
    # checkbox list (title + footer lines, no field box), WB grid and Creative Look (no title line),
    # checkbox list with OK focused and the My Dial table (field-sized orange box, but no ▲/▼)
    assert screen.read(load(need(SHOTS / name))).kind != "fields"


def test_a_number_field_the_first_engine_skipped_is_read_again():
    """field_values: a field the first OCR engine left unread is read by the second engine on the same frame, else
    by the first on the field alone at three times its size (Apple Vision skipped "11 sec" on a frame it had read
    "10" on, 2026-11-06, and the row failed). A lone "0" can stay unread: field_at then tries the pass-1 pictures."""
    import prove_run as P
    from camkit import ocr
    if not ocr.available():
        pytest.skip("no OCR engine")
    f = load(need(A1 / "kit2_pass2" / "shots" / "210685_up.png"))
    s = screen.read(f)
    assert s.kind == "fields" and len(s.boxes) == 2
    cam = type("C", (), {"read": lambda self: s, "frame": f})()
    assert P.field_values(cam)[1] == "11"


CHECKLISTS = {
    # file: (focus, cursor row, ticks)
    "00880_up.png": ("rows", 1, [True] * 5),                        # Drive Mode Limit, bar cursor
    "07960_up.png": ("button", None, [True] * 5),                   # Different Set for Still/Mv, OK focused
    "08026_down.png": ("button", None, [True] * 4 + [False]),       # DISP Set > Monitor: OK at the right
    "03985_down.png": ("rows", 1, [False, False]),                  # Reg. Flash Shooting Set: frame cursor
}


@pytest.mark.parametrize("name", sorted(CHECKLISTS))
def test_checklist(name):
    focus, row, ticks = CHECKLISTS[name]
    s = screen.read(load(need(SHOTS / name)))
    assert (s.kind, s.focus, s.row) == ("checklist", focus, row)
    assert s.slots == ["ticked" if t else "empty" for t in ticks]


LOOKS = {
    # file: (cell: 0 = the Look, 1-8 = Contrast..Clarity; ⌃ shown, ⌄ shown, scale marker shown)
    "04972_right.png": (1, True, True, True),     # ST, Contrast ±0
    "05038_down.png": (4, True, False, True),     # ST, Fade at 0: can only go up
    "05062_right.png": (6, True, True, True),     # ST, Sharpness
    "05089_left.png": (8, True, True, True),      # ST, Clarity (last cell)
    "10504_down.png": (5, False, False, False),   # BW: Saturation is fixed (no scale, no arrows)
}


@pytest.mark.parametrize("name", sorted(LOOKS))
def test_creative_look_panel(name):
    cell, up, down, marker = LOOKS[name]
    s = screen.read(load(need(SHOTS / name)))
    assert s.kind == "look"
    assert (s.field, s.glyphs["up"], s.glyphs["down"], s.marker is not None) == (cell, up, down, marker)


SLIDERS = {
    # file: (◂ shown, ▸ shown, marker x)
    "02950_open.png": (True, True, 418),     # Aspect Marker Level 12 (half-width footer line)
    "02959_right.png": (True, False, 484),   # Aspect Marker Level at 15: the top of the range
    "03769_down.png": (True, True, 322),     # Exposure Comp. ±0.0 (orange icon beside the value)
    "03907_down.png": (True, True, 320),     # Flash Comp. ±0.0 (marker under the scale)
}


@pytest.mark.parametrize("name", sorted(SLIDERS))
def test_slider(name):
    left, right, marker = SLIDERS[name]
    s = screen.read(load(need(SHOTS / name)))
    assert (s.kind, s.glyphs["left"], s.glyphs["right"]) == ("slider", left, right)
    assert abs(s.marker - marker) <= 2


SIDELISTS = {
    # file: (cursor row, visible, at_start, at_end)
    "06088_replay.png": (0, 6, True, False),    # PP1 > Gamma: Movie, first of ~13
    "06073_right.png": (1, 3, False, False),    # Black Gamma > Range: Middle (no scrollbar)
    "06154_replay.png": (5, 6, False, True),    # PP1 > Gamma: HLG3, the last option
}


@pytest.mark.parametrize("name", sorted(SIDELISTS))
def test_picture_profile_side_list(name):
    row, count, start, end = SIDELISTS[name]
    s = screen.read(load(need(SHOTS / name)))
    assert (s.kind, s.row, s.count, s.at_start, s.at_end) == ("sidelist", row, count, start, end)


@pytest.mark.parametrize("name,dot,arrows", [
    ("04031_down.png", (478, 283), 4),     # Auto, A-B 0, G-M M2
    ("04684_nav.png", (461, 289), 4),      # B2, M2.75
    ("04051_down.png", (478, 329), 3),     # at the M end of the range: the ▽ box is gone
])
def test_white_balance_grid(name, dot, arrows):
    s = screen.read(load(need(SHOTS / name)))
    assert s.kind == "wbgrid"
    assert abs(s.marker[0] - dot[0]) <= 2 and abs(s.marker[1] - dot[1]) <= 2
    assert sum(s.glyphs.values()) == arrows


@pytest.mark.parametrize("name", ["08812_open.png",      # "Connected to Remote Shooting. Cannot be executed." (no OK)
                                  "02464_right.png",     # "not available as follows | Shoot Mode | Manual Exposure"
                                  "03811_nav.png"])      # "Adjust?" with OK preselected and Cancel
def test_notices_without_orange_ok_button(name):
    assert screen.read(load(need(SHOTS / name))).kind == "notice"


@pytest.mark.parametrize("name,row,col,boxes", [
    ("06814_open.png", 0, 0, 14),     # Wide
    ("06853_right.png", 0, 3, 14),    # Spot: XL
    ("06760_down.png", 1, 1, 10),     # Tracking: Custom 2 (second row)
])
def test_focus_area_limit_grid(name, row, col, boxes):
    s = screen.read(load(need(SHOTS / name)))
    assert (s.kind, s.focus, s.row, s.field, s.count) == ("checkgrid", "rows", row, col, boxes)


# --- HDMI frames (Cam Link 4K, 1080p cropped to 640x480), from the user's walk-through 2026-10-28.
# Thin lines come out ~15-20% dimmer and can shift by a pixel, which broke several OSD-tuned rules.
HDMI = A1 / "kit2_hdmi_watch" / "shots"


@pytest.mark.parametrize("name,kind,check", [
    ("00024_seen.png", "list", lambda s: (s.row, s.count, s.current) == (0, 2, 0)),          # Interval Shooting Off/On
    ("00060_seen.png", "fields", lambda s: (s.field, s.count) == (1, 2)),                      # Start Time: min | sec
    ("00077_seen.png", "fields", lambda s: (s.field, s.count) == (0, 4)),                      # Number of Shots
    ("00197_seen.png", "slider", lambda s: s.glyphs == {"left": True, "right": True}),         # Exposure Comp.
    ("00229_seen.png", "wbgrid", lambda s: sorted(k for k, v in s.glyphs.items() if v) == ["down", "right"]),  # B7/G7
    ("00437_seen.png", "look", lambda s: (s.field, s.glyphs["up"], s.glyphs["down"]) == (0, False, True)),  # the Look cell
    ("00417_seen.png", "notice", lambda s: True),            # not available as follows | Creative Look | BW
    ("00544_seen.png", "helppop", lambda s: (s.row, s.count) == (1, 2)),                       # In-Camera Guide selected
    ("00545_seen.png", "guide", lambda s: True),             # In-Camera Guide text for Picture Profile
    ("00543_seen.png", "menu", lambda s: s.row == 2),        # the page behind it
])
def test_hdmi_frames(name, kind, check):
    s = screen.read(load(need(HDMI / name)))
    assert s.kind == kind
    assert check(s)


@pytest.mark.parametrize("path,slots", [
    (SHOTS / "00002_m.png", ["normal", "greyed", "cursor", "normal"]),          # Power Save Start Time greyed
    (SHOTS / "00073_downx3.png", ["normal", "normal", "greyed", "cursor"]),     # 4K Output Set. greyed; info panel below
    (SHOTS / "00312_right_late.png", ["cursor", "normal", "normal"]),           # 3-row submenu
    (HDMI / "00061_seen.png", ["normal", "cursor", "normal", "normal", "normal"]),   # over HDMI, info panel below
])
def test_page_rows(path, slots):
    s = screen.read(load(need(path)))
    assert s.slots == slots


@pytest.mark.parametrize("name,row,col,span", [("03860_down.png", 0, 0, 1),     # Shutter Speed tile
                                               ("03861_down.png", 1, 0, 2),     # the media tile: opens Format
                                               ("03862_down.png", 2, 0, 1)])    # Aspect Ratio
def test_main_tiles(name, row, col, span):
    s = screen.read(load(need(A1 / "rip_stills" / "shots" / name)))
    assert (s.kind, s.focus, s.row, s.field, s.count) == ("tiles", "tiles", row, col, span)


# --- walker logic on the menu twin (the old explorer's recorded dialogs, runs/explore_stills)

@pytest.mark.parametrize("item", ["Drive Mode", "Power Save by Monitor", "Write Serial Number", "File Format"])
def test_walk_cycle_on_twin(item):
    from camkit.twin import TwinCamera, old_twins
    from camkit.walk import walk_cycle
    need(A1 / "explore_stills" / "graph.jsonl")
    twin = next(t for t in old_twins() if t.item == item)
    cam = TwinCamera(twin)
    w = walk_cycle(cam)
    assert w.complete and w.wrapped
    assert w.presses == len(w.options)                 # one press per option, wherever it started
    assert w.screens[w.options[0]].at_start in (True, None)


@pytest.mark.parametrize("item,values", [
    ("Interval Shoot Func. > Shooting Interval", [60]),          # 1-60 s, wraps
    ("Interval Shoot Func. > Number of Shots", [10, 10, 10, 10]),  # one field per digit
    ("SISO Range Limit", [34, 34]),                              # min and max stop at their ends
])
def test_walk_fields_on_twin(item, values):
    from camkit.twin import TwinCamera, old_twins
    from camkit.walk import walk_fields
    need(A1 / "explore_stills" / "graph.jsonl")
    w = walk_fields(TwinCamera(next(t for t in old_twins() if t.item == item)))
    assert w.complete
    assert [len(f.options) for f in w.fields] == values


def test_walk_slider_and_checklist_on_twin():
    from camkit.twin import TwinCamera, old_twins
    from camkit.walk import walk_axes, walk_cycle
    need(A1 / "explore_stills" / "graph.jsonl")
    twins = {t.item: t for t in old_twins()}
    w = walk_axes(TwinCamera(twins["Aspect Marker Level"]), [("right", "right"), ("left", "left")])
    assert w.complete and w.axes["right"][1] == "end"            # ▸ disappears at 15
    c = walk_cycle(TwinCamera(twins["Different Set for Still/Mv"]), budget=120)
    assert c.complete and c.wrapped and c.presses == len(c.options)


def test_crawl_end_to_end_on_menu_twin():
    """Pass 1 on the menu twin: today's page-scan cycle joined to the old item twins."""
    import json
    import camkit.crawl as C
    from camkit.twin import MenuTwin, Unrecorded, old_twins
    root = A1 / "kit2_page_scan"
    need(root / "scan_rekeyed.json")
    need(A1 / "explore_stills" / "graph.jsonl")
    cycle = json.loads((root / "scan_rekeyed.json").read_text(encoding="utf-8"))[:-1]
    for pos in cycle:                            # as the live runner does: screens from today's reader
        sc = screen.read(load(root / "shots" / pos["frame"]))
        pos.update(signature=sc.signature, kind=sc.kind, row=sc.row, screen=sc)
    model = {p["key"]: p for p in json.loads((root / "model.json").read_text(encoding="utf-8"))}
    labels = {i: model[p["page"]]["rows"][p["row"]]["label"] for i, p in enumerate(cycle)
              if p["kind"] == "menu" and p["page"] in model and p["row"] is not None
              and p["row"] < len(model[p["page"]]["rows"])}
    cam = MenuTwin(cycle, root / "shots", labels, old_twins())
    visit = C.visit_row

    def tolerant(cam_, *a, **kw):
        try:
            return visit(cam_, *a, **kw)
        except Unrecorded:                 # a row the old explorer never opened
            cam.item = None
            return C.RowResult("", 0, "", "no recorded item")
    C.visit_row = tolerant
    try:
        out = C.crawl(cam, cycle, model)
    finally:
        C.visit_row = visit
    assert out.stopped == ""                                       # the lap completed, never lost
    assert sum(r.outcome == "walked" for r in out.rows) >= 90
    assert all(r.outcome.startswith("skipped") for r in out.rows if r.label and safety.never_open(r.label))


# --- the crawl's control flow on a scripted fake menu (no images): submenus, live labels,
# never-open rows inside submenus, and a notice whose MENU throws the crawl out to the shooting
# screen and reopens the menu on the PARENT row (the worst case seen on the camera)

class _S:
    def __init__(self, kind, sig, row=None, at_start=None, at_end=None):
        self.kind, self.signature, self.row = kind, sig, row
        self.at_start, self.at_end = at_start, at_end
        self.glyphs, self.count, self.field, self.focus, self.slots = {}, None, None, "rows", []
        import numpy as np
        self.struct, self.bits = (kind, sig), np.zeros(0, np.uint8)


class FakeMenu:
    TOP = ["A", "Sub", "B"]                                   # page P rows
    SUB = ["S1", "S2 greyed", "Forced File Number Reset", "S4"]
    LISTS = {"A": 2, "B": 2, "S1": 3, "S4": 2}

    def __init__(self, reopen_at_parent=True):
        self.where = ("top", 0)          # ("top", row) | ("sub", row) | ("list", name, i) | ("notice", row) | ("shooting",)
        self.reopen_at_parent = reopen_at_parent
        self.last_menu = ("top", 0)
        self.pressed = []

    def press(self, key):
        self.pressed.append((self.where, key))
        w = self.where
        if w[0] == "top":
            if key == "down":
                self.where = ("top", (w[1] + 1) % 3)
            elif key == "right":
                name = self.TOP[w[1]]
                self.where = ("sub", 0) if name == "Sub" else ("list", name, 0)
            elif key == "menu":
                self.last_menu, self.where = w, ("shooting",)
        elif w[0] == "sub":
            name = self.SUB[w[1]]
            if key == "down":
                self.where = ("sub", (w[1] + 1) % len(self.SUB))
            elif key == "left":
                self.where = ("top", 1)
            elif key == "right":
                assert "Forced" not in name, "Right on a never-open row"
                self.where = ("notice", w[1]) if "greyed" in name else ("list", name, 0)
            elif key == "menu":
                self.where = ("top", 1)
        elif w[0] == "list":
            if key == "down":
                self.where = ("list", w[1], (w[2] + 1) % self.LISTS[w[1]])
            elif key == "menu":
                self.where = ("top", self.TOP.index(w[1])) if w[1] in self.TOP else ("sub", self.SUB.index(w[1]))
        elif w[0] == "notice" and key == "menu":
            self.last_menu = ("top", 1) if self.reopen_at_parent else ("sub", w[1])
            self.where = ("shooting",)
        elif w[0] == "shooting" and key == "menu":
            self.where = self.last_menu

    def read(self):
        w = self.where
        if w[0] == "top":
            return _S("menu", f"top{w[1]}", w[1])
        if w[0] == "sub":
            return _S("submenu", f"sub{w[1]}", w[1])
        if w[0] == "list":
            n = self.LISTS[w[1]]
            return _S("list", f"{w[1]}:{w[2]}", w[2], at_start=w[2] == 0, at_end=w[2] == n - 1)
        if w[0] == "notice":
            return _S("notice", f"notice{w[1]}")
        return _S("shooting", "shooting")

    def labels(self, cam):
        return ("subpage", list(self.SUB))


@pytest.mark.parametrize("reopen_at_parent", [True, False])
def test_crawl_submenus_on_fake_menu(reopen_at_parent):
    from camkit.crawl import crawl
    fake = FakeMenu(reopen_at_parent)
    cycle = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
                   "rows": [{"label": l, "never_open": None} for l in FakeMenu.TOP]}}
    out = crawl(fake, cycle, model, labels=fake.labels)
    assert out.stopped == ""
    outcomes = {r.label: r.outcome for r in out.rows}
    assert outcomes == {"A": "walked", "Sub": "submenu crawled", "B": "walked"}
    sub = next(r for r in out.rows if r.label == "Sub").walk
    sub_out = {r.label: r.outcome.split(":")[0] for r in sub.rows}
    assert sub_out == {"S1": "walked", "S2 greyed": "notice", "Forced File Number Reset": "skipped", "S4": "walked"}
    assert fake.read().signature == "top2"                     # ended on the last top-level row


class LongFakeMenu(FakeMenu):
    SUB = [f"S{i}" for i in range(1, 19)] + ["S19 greyed", "S20"]
    LISTS = {"A": 2, "B": 2, **{f"S{i}": 2 for i in range(1, 21)}}


def test_a_submenu_row_past_the_sixteenth_is_found_again():
    """The way back to a submenu row after MENU threw the crawl out to the parent row: Right into the submenu, then
    Down to the row, as many Downs as its place and 16 more. A row's place was not handed down (0), so a row past the
    sixteenth was lost."""
    from camkit.crawl import crawl
    fake = LongFakeMenu(reopen_at_parent=True)
    cycle = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
                   "rows": [{"label": l, "never_open": None} for l in FakeMenu.TOP]}}
    out = crawl(fake, cycle, model, labels=fake.labels)
    assert out.stopped == ""
    sub = next(r for r in out.rows if r.label == "Sub").walk
    assert sub.stopped == "" and len(sub.rows) == 20
    assert {r.label: r.outcome for r in sub.rows}["S19 greyed"] == "notice"


class ReopeningFakeMenu(FakeMenu):
    """A submenu of 30 rows that reopens, after the first time, on the row it last showed (here row 6)."""
    SUB = ["S1", "S2", "S3 greyed"] + [f"S{i}" for i in range(4, 31)]
    LISTS = {"A": 2, "B": 2, **{f"S{i}": 2 for i in range(1, 31)}}
    entered = False

    def press(self, key):
        entering = self.where == ("top", 1) and key == "right"
        super().press(key)
        if entering and self.entered:
            self.where = ("sub", 5)
        self.entered = self.entered or entering


def test_a_submenu_row_is_found_again_from_wherever_the_submenu_reopens():
    """The way back counts Downs from where the submenu reopens, which can be past the row: from row 6 back round to
    row 3 of 30 takes 27 Downs, more than the row's place and 16."""
    from camkit.crawl import crawl
    fake = ReopeningFakeMenu(reopen_at_parent=True)
    cycle = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
                   "rows": [{"label": l, "never_open": None} for l in FakeMenu.TOP]}}
    out = crawl(fake, cycle, model, labels=fake.labels)
    assert out.stopped == ""
    sub = next(r for r in out.rows if r.label == "Sub").walk
    assert sub.stopped == "" and len(sub.rows) == 30


# --- live replays: the camera's own frames and presses from the 4-row crawl (2026-10-28), where the
# ISO carousel's revisited options carried live-view noise and ISO Range Limit's fields are coupled

def _live_replay(first, last):
    import json
    crawl = A1 / "kit2_crawl"
    need(crawl / "events.jsonl")
    names = {f"{n:05d}" for n in range(first, last + 1)}
    steps = [e for e in map(json.loads, (crawl / "events.jsonl").read_text(encoding="utf-8").splitlines())
             if "key" in e and e["frame"][:5] in names]

    class Replay:
        def __init__(self):
            self.i = 0
            self.s = screen.read(load(crawl / "shots" / steps[0]["frame"]))

        def press(self, key):
            self.i += 1
            assert self.i < len(steps) and steps[self.i]["key"] == key, f"walker pressed {key!r} off the recording"
            self.s = screen.read(load(crawl / "shots" / steps[self.i]["frame"]))

        def read(self):
            return self.s
    return Replay()


def test_live_iso_carousel_wraps_despite_noise():
    from camkit.walk import walk_cycle
    w = walk_cycle(_live_replay(83, 122), budget=120)
    assert w.complete and w.wrapped and len(w.options) == 35 and w.presses == 35


def test_live_iso_range_limit_coupled_fields():
    from camkit.walk import walk_fields
    w = walk_fields(_live_replay(125, 196))
    assert w.complete and [len(f.options) for f in w.fields] == [34, 34]


@pytest.mark.parametrize("name,row,count,pitch", [
    ("00811_right.png", 0, 6, 60),    # Recognition Target: radio rows with › Detail boxes, 61 px rows
    ("00825_down.png", 3, 6, 61),     # Auto Recog. Target: checkbox rows with Details, scrolls
])
def test_submenu_with_detail_boxes(name, row, count, pitch):
    s = screen.read(load(need(A1 / "kit2_crawl" / "shots" / name)))
    assert (s.kind, s.row, s.count) == ("submenu", row, count)
    assert abs(s.pitch - pitch) <= 1


def test_live_scrolling_list_wraps_by_option():
    # Pre-Capture Rec Time: a list that scrolls; after going round, the opening option sits on another row
    from camkit.walk import walk_cycle
    w = walk_cycle(_live_replay(2587, 2606), budget=120)
    assert w.complete and w.wrapped and len(w.options) == 17


def test_live_scrolling_list_period_operation_area():
    from camkit.walk import walk_cycle
    w = walk_cycle(_live_replay(3630, 3641), budget=120)
    assert w.complete and len(w.options) == 9


def test_crawl_recovers_when_the_menu_closes_by_itself():
    from camkit.crawl import crawl
    fake = FakeMenu()
    real_press = fake.press

    def press(key):                       # the second Down on the top page lands on the shooting screen
        real_press(key)
        if key == "down" and fake.where == ("top", 2) and not getattr(fake, "dropped", False):
            fake.dropped, fake.last_menu, fake.where = True, ("top", 2), ("shooting",)
    fake.press = press
    cycle = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
                   "rows": [{"label": l, "never_open": None} for l in FakeMenu.TOP]}}
    out = crawl(fake, cycle, model, labels=fake.labels)
    assert out.stopped == "" and out.recoveries == [2]
    assert [r.outcome for r in out.rows] == ["walked", "submenu crawled", "walked"]


def test_creative_look_cell_zero_is_not_a_menu_page():
    s = screen.read(load(need(A1 / "kit2_panels" / "shots" / "00333_right.png")))
    assert (s.kind, s.field) == ("look", 0)          # IN (Instant): the Look cell selected, at the far left


# --- screens pass 1 could not read (2026-10-29): tables, the function picker, Custom Key, Fn Menu

@pytest.mark.parametrize("path,check", [
    # Image Quality Settings: SLOT 1 File Format cell; the OK button (Rec. Media Settings beside it)
    (A1 / "kit2_pass1" / "shots" / "00093_right.png",
     lambda s: (s.kind, s.focus, s.marker) == ("table", "cell", (379, 123))),
    (A1 / "iq_map" / "00011_btn.png", lambda s: (s.kind, s.focus) == ("table", "button")),
    # My Dial Settings: Front dial / My Dial 1, before and after a function was assigned
    (A1 / "kit2_pass1" / "shots" / "02439_right.png",
     lambda s: (s.kind, s.focus, s.marker) == ("table", "cell", (448, 149))),
    (A1 / "dg_mydial" / "shots" / "00033_assigned.png", lambda s: (s.kind, s.focus) == ("table", "cell")),
    # Custom Key/Dial Set.: the Dial/Wheel page's grid is a table inside the key pages
    (A1 / "dg_wheel" / "shots" / "00018_cell.png",
     lambda s: (s.kind, s.focus, s.group) == ("keyset", "cell", 5)),
    (A1 / "ck_keys1" / "shots" / "00017_right.png", lambda s: (s.kind, s.focus, s.group) == ("keyset", "tabs", 0)),
    (A1 / "ck_keys1" / "shots" / "00018_key.png",
     lambda s: (s.kind, s.focus, s.row, s.group) == ("keyset", "keys", 0, 0)),
    # Playback's Custom Key Setting: three tabs; tab focus had passed as a menu page, the sixth key
    # (y 370) as a table button
    (A1 / "ck_play_keys" / "shots" / "00020_right.png", lambda s: (s.kind, s.focus, s.group) == ("keyset", "tabs", 0)),
    (A1 / "ck_play_keys2" / "shots" / "00058_key.png",
     lambda s: (s.kind, s.focus, s.row, s.group) == ("keyset", "keys", 5, 0)),
    # the function picker: My Dial's last page (Not set, saved), a page further on, Fn Menu, keys
    (A1 / "dg_mydial" / "shots" / "00031_picker.png",
     lambda s: (s.kind, s.row, s.count, s.current, s.field, s.group) == ("picker", 0, 1, 0, 3, 0)),
    (A1 / "dg_mydial" / "shots" / "00032_next.png",
     lambda s: (s.kind, s.row, s.count, s.current, s.field) == ("picker", 4, 5, None, 2)),
    (A1 / "fn_run1" / "shots" / "00037_picker.png",
     lambda s: (s.kind, s.row, s.count, s.current, s.field, s.group) == ("picker", 3, 4, 3, 0, 6)),
    (A1 / "ck_play_keys" / "shots" / "00022_picker.png",
     lambda s: (s.kind, s.row, s.count, s.current, s.field, s.group) == ("picker", 0, 5, 0, 0, 5)),
    # Fn Menu Settings: Still upper 1 (its orange tile colours the left edge like a menu tab)
    (A1 / "kit2_pass1" / "shots" / "02382_right.png", lambda s: (s.kind, s.row, s.field) == ("fnmenu", 0, 0)),
    (A1 / "fn_run1" / "shots" / "00756_slot.png", lambda s: (s.kind, s.row, s.field) == ("fnmenu", 3, 5)),
    # Mode Dial Control Set: its three rows are cells (each opens Set with Dial / Set with Menu)
    (A1 / "kit2_pass1" / "shots" / "02554_right.png",
     lambda s: (s.kind, s.focus, s.marker) == ("table", "cell", (214, 135))),
    (A1 / "dial_ctrl3" / "00010_applied.png", lambda s: (s.kind, s.focus, s.marker) == ("table", "cell", (214, 239))),
    # a look-alike that stays what it was: Display Media Info.'s slot buttons
    (A1 / "kit2_pass1" / "shots" / "00178_right.png", lambda s: s.kind == "unknown"),
])
def test_assignment_screens(path, check):
    s = screen.read(load(need(path)))
    assert check(s), (s.kind, s.focus, s.row, s.field, s.group, s.count, s.current, s.marker)


class FakeTable:
    """A 2 x 2 table over an OK button, each cell opening a 3-option list (table_walk's moves)."""
    CELLS = {(0, 0): (380, 124), (0, 1): (548, 124), (1, 0): (380, 177), (1, 1): (548, 177)}

    def __init__(self):
        self.at, self.opened, self.option, self.presses, self.enters = (0, 0), False, 0, [], []
        self.frame = type("F", (), {"path": Path("fake.png")})()

    def press(self, key):
        self.presses.append(key)
        if self.opened:
            if key == "down":
                self.option = (self.option + 1) % 3
            elif key == "menu":
                self.opened = False
            return
        if key == "enter":
            assert self.at != "ok", "Enter on the table's OK"
            self.enters.append(self.at)
            self.opened, self.option = True, 0
        elif self.at == "ok":
            self.at = (1, 0) if key == "up" else "ok"
        else:
            r, c = self.at
            r, c = {"down": (r + 1, c), "up": (max(r - 1, 0), c), "right": (r, min(c + 1, 1)),
                    "left": (r, max(c - 1, 0))}[key]
            self.at = "ok" if r == 2 else (r, c)

    def read(self):
        if self.opened:
            sig = f"o{self.option}"
            return screen.Screen(kind="list", row=self.option, count=3, signature=sig, struct=(sig.encode(),))
        if self.at == "ok":
            return screen.Screen(kind="table", focus="button", marker=(484, 367), signature="ok", struct=(b"ok",))
        return screen.Screen(kind="table", focus="cell", marker=self.CELLS[self.at], signature=str(self.at),
                             struct=(str(self.at).encode(),))


def test_table_walk_explores_every_cell_once_per_arrow(monkeypatch):
    import table_walk as T
    cam = FakeTable()
    grid = T.Grid(T.pos_of(cam.read()))
    T.explore(cam, grid)
    assert {p for p in grid.seen if p[0] == "cell"} == {("cell", x // 4 * 4, y // 4 * 4) for x, y in FakeTable.CELLS.values()}
    assert len(grid.moves) == 4 * len(grid.seen)             # every arrow once at every place
    assert cam.enters == []
    cam.press("enter")
    monkeypatch.setattr(T, "bar_text", lambda c: f"option {c.read().row}")   # no OCR on the fake
    w = T.walk_options(cam, "list", 10)
    assert w["wrapped"] and [o["label"] for o in w["options"]] == ["option 0", "option 1", "option 2"]


class FakeMyDial(FakeTable):
    """My Dial Settings as the camera did it (2026-10-29): 3 columns x 4 rows over an OK button.
    Left/Right wrap round a row; Up from the top row and Down from the bottom go to the button; the
    button keeps a column it does not show, Left/Right on it move that column, and Up/Down leave
    into it (bottom / top row)."""
    CELLS = {(r, c): (448 + 70 * c, 148 + 50 * r) for r in range(4) for c in range(3)}

    def __init__(self):
        super().__init__()
        self.col = 0

    def press(self, key):
        self.presses.append(key)
        if self.opened or key == "enter":
            return FakeTable.press(self, key) if key != "enter" or self.at != "ok" else None
        if self.at == "ok":
            if key in ("left", "right"):
                self.col = (self.col + (1 if key == "right" else -1)) % 3
            else:
                self.at = (3 if key == "up" else 0, self.col)
            return
        r, c = self.at
        if key in ("left", "right"):
            self.at = (r, (c + (1 if key == "right" else -1)) % 3)
        elif (key == "up" and r == 0) or (key == "down" and r == 3):
            self.at, self.col = "ok", c
        else:
            self.at = (r + (1 if key == "down" else -1), c)


def test_table_walk_copes_with_a_button_that_keeps_a_hidden_column():
    import table_walk as T
    cam = FakeMyDial()
    grid = T.Grid(T.pos_of(cam.read()))
    here = T.explore(cam, grid)
    cells = {("cell", x // 4 * 4, y // 4 * 4) for x, y in FakeMyDial.CELLS.values()}
    assert {p for p in grid.seen if p[0] == "cell"} == cells
    for p in sorted(cells, key=lambda q: (q[2], q[1])):        # the walk's order, through the button too
        here = grid.travel(cam, here, p)
        assert T.pos_of(cam.read()) == p
    assert cam.enters == []


def test_table_prover_reaches_cells_and_only_the_ok_button(monkeypatch):
    import prove_run as P
    cam = FakeTable()
    P.to_cell(cam, FakeTable.CELLS[(1, 1)])
    assert cam.at == (1, 1)
    P.to_cell(cam, FakeTable.CELLS[(0, 0)])
    assert cam.at == (0, 0)
    monkeypatch.setattr(P.proving.tables, "table_button", lambda c: "OK" if c.at == "ok" else "")
    P.to_ok(cam)
    assert cam.at == "ok" and cam.enters == []
    with pytest.raises(P.Failed):                         # a cell that is not there: the cursor stops
        P.to_cell(cam, (700, 124))


class FakeKeyset:
    """Custom Key/Dial Set. as the old kit's frames show it: six page tabs that wrap; Enter on a tab
    goes into its keys (or the Dial/Wheel grid), Enter on a key opens the picker (3 functions here),
    MENU in the picker goes back to the key, MENU in the keys leaves to the menu row."""
    KEYS = [5, 5, 3, 2, 1]                    # pages 0-4; page 5 is the 4 x 2 grid

    def __init__(self):
        import numpy as np
        self.where, self.page, self.row, self.cell, self.option = "row", 0, 0, (0, 0), 0
        self.enters = []
        self.frame = type("F", (), {"path": Path("fake.png"), "image": np.zeros((480, 640, 3), np.uint8)})()

    def press(self, key):
        w = self.where
        if w == "row":
            if key == "right":
                self.where = "tabs"
        elif w == "tabs":
            if key == "down":
                self.page = (self.page + 1) % 6
            elif key == "enter":
                self.where, self.row, self.cell = ("keys" if self.page < 5 else "grid"), 0, (0, 0)
            elif key == "menu":
                self.where = "row"
        elif w in ("keys", "grid"):
            if key == "enter":
                self.enters.append((self.page, self.row if w == "keys" else self.cell))
                self.where, self.back, self.option = "picker", w, 0
            elif key == "menu":
                self.where = "row"
            elif w == "keys" and key == "down":
                self.row = (self.row + 1) % self.KEYS[self.page]
            elif w == "grid":
                r, c = self.cell
                self.cell = {"down": (min(r + 1, 3), c), "right": (r, min(c + 1, 1)), "left": (r, max(c - 1, 0)),
                             "up": (max(r - 1, 0), c)}.get(key, (r, c))
        elif w == "picker":
            if key == "down":
                self.option = (self.option + 1) % 3
            elif key == "menu":
                self.where = self.back

    def read(self):
        w = self.where
        sig = f"{w}{self.page}{self.row}{self.cell}{self.option}"
        if w == "row":
            return screen.Screen(kind="menu", row=2, signature="row", struct=(b"row",))
        if w == "picker":
            return screen.Screen(kind="picker", row=self.option, count=3, signature=sig, struct=(sig.encode(),))
        if w == "tabs":
            return screen.Screen(kind="keyset", focus="tabs", group=self.page, signature=sig, struct=(sig.encode(),))
        if w == "keys":
            return screen.Screen(kind="keyset", focus="keys", group=self.page, row=self.row, bar=(110, 160),
                                 signature=sig, struct=(sig.encode(),))
        r, c = self.cell
        return screen.Screen(kind="keyset", focus="cell", group=5, marker=(168 + 120 * c, 218 + 52 * r),
                             signature=sig, struct=(sig.encode(),))


def test_custom_key_walk_visits_every_key_and_grid_cell(monkeypatch):
    import table_walk as T
    stub = type("O", (), {"read": staticmethod(lambda paths: {p: [] for p in paths}),
                          "text_in": staticmethod(lambda lines, box: "")})
    monkeypatch.setattr(T, "ocr", stub)
    monkeypatch.setattr(T, "picker_text", lambda c: f"fn {c.read().row}")
    monkeypatch.setattr(T, "picker_where", lambda c: {})
    monkeypatch.setattr(T, "key_info", lambda c: {"key": "", "value": "", "frame": ""})
    cam = FakeKeyset()
    out = T.walk_keyset(cam, "Custom Key/Dial Set.", 10)
    assert [p["tab"] for p in out["pages"]] == [0, 1, 2, 3, 4, 5]
    assert [len(p["items"]) for p in out["pages"]] == FakeKeyset.KEYS + [8]
    assert all(len(i["options"]) == 3 and i["wrapped"] for p in out["pages"] for i in p["items"])
    assert sorted(cam.enters[-8:], key=lambda e: e[1]) == [(5, (r, c)) for r in range(4) for c in range(2)]
    assert cam.where == "row"


@pytest.mark.parametrize("name,stars", [("00987_right.png", None), ("00988_down.png", 0), ("00989_down.png", 1),
                                        ("00991_down.png", 3), ("00993_down.png", 5)])
def test_rating_stars_counted_from_pixels(name, stars):
    # Selection/Memo Shot > Top Image: Off, Divider Frame (|→), Rating (★) ... Rating (★★★★★)
    f = load(need(A1 / "kit2_pass1" / "shots" / name))
    assert screen.count_stars(f.image, screen.read(f).bar) == stars


@pytest.mark.parametrize("name,stars", [("147167_down.png", None), ("146448_down.png", 1)])
def test_rating_stars_not_counted_in_digits(name, stars):
    # Image Jump Setting: "By 10 minutes" (a tall narrow "1", no brackets), "Rating Only ( ★ )"
    f = load(need(A1 / "kit2_pass2" / "shots" / name))
    assert screen.count_stars(f.image, screen.read(f).bar) == stars


@pytest.mark.parametrize("name,row,stars", [("00068_right.png", 0, 1), ("00069_down.png", 1, 2), ("00070_down.png", 2, 3),
                                            ("00071_down.png", 3, 4), ("00072_down.png", 4, 5), ("00073_down.png", None, None)])
def test_rating_set_boxes_in_two_columns(name, row, stars):
    # Rating Set(Custom Key): 1-3 stars down the left column, 4-5 down the right; Down goes 1..5,
    # Enter, Cancel. Only the cursor row's x range tells the columns' boxes apart
    f = load(need(A1 / "kit2_play2" / "shots" / name))
    s = screen.read(f)
    assert s.kind == "checklist" and s.count == 5 and s.slots == ["ticked"] + ["empty"] * 4
    assert s.row == row and screen.box_stars(f.image, s) == stars
    assert s.focus == ("button" if row is None else "rows")


def test_rating_set_labels_come_from_star_counts(monkeypatch):
    # pass 1's readers said "* ** *", "1 star", "4 stars"; the job relabels from the saved frames
    import json
    import prove_run as P
    m = json.loads(Path(need(A1 / "kit2_play2" / "map.json")).read_text(encoding="utf-8"))
    monkeypatch.setattr(P.proving.base, "RUN_ROOT", A1)              # the a1 II's frames, whichever camera the tests' kit works on
    monkeypatch.setattr(P.proving.base, "FRAME_DIRS", (A1 / "kit2_pass1" / "shots", A1 / "kit2_panels" / "shots"))
    monkeypatch.setattr(P.proving.base, "_FRAME_RUN", {})
    row = next(r for r in m["rows"] if r["path"] == ["Rating Set(Custom Key)"])
    assert P.check_job(row)["labels"] == ["★" * n for n in range(1, 6)]


def test_table_jobs_keep_which_row_of_a_repeated_label(tmp_path, monkeypatch):
    # two menu rows read "Fn Menu Settings" (stills/movies, then playback): the job carries nth so
    # the prover steps Down to the second
    import json
    import prove_run as P
    cell = {"pos": [0, 0], "row_label": "Playback Upper", "col_label": "1", "opens": "picker", "wrapped": True,
            "options": [{"label": "Protect"}, {"label": "Rotate"}]}
    f = tmp_path / "tables.json"
    f.write_text(json.dumps({"Fn Menu Settings (playback)": {"path": ["Fn Menu Settings"], "screen": "fnmenu",
                                                             "nth": 1, "cells": [cell]}}))
    monkeypatch.setattr(P.proving.base, "TABLES", f)
    [j] = P.table_jobs()
    assert (j["nth"], j["option"], j["screen"]) == (1, "Playback Upper / 1", "fnmenu")


def test_saved_function_left_out_unless_planned():
    # a slot saved on a passed-over function (Recall Custom hold) or outside the sample is chosen
    # last only to put it back; its label would tell the user's assignment, so the report drops it
    import pass2_report as R
    import prove_run as P
    job = {"labels": ["AF-On", "Recall Custom hold 1", "Rating", "Protect"], "plan": [0, 2]}
    assert [P.table_planned(job, k) for k in range(4)] == [True, False, True, False]
    ch = {"key": "global:0x1234", "before": 7, "after": 3}
    opts = {0: {"kind": "table", "label": "AF-On", "changes": [ch], "applied": True, "planned": True},
            1: {"kind": "table", "label": "Recall Custom hold 1", "changes": [], "applied": True, "planned": False}}
    assert R.values_of(opts) == {"global:0x1234": {"AF-On": 3}}


def test_hold_speed_named_by_the_continuous_rows_only():
    # a hold keeps its continuous speed (0x0bf1) when a bracket is registered: that option says
    # nothing about it, while Drive Mode (0x0bed) takes every option (2026-10-31)
    import pass2_report as R

    def opt(label, bed=None, bf1=None):
        ch = [{"key": "global:0x0bed", "before": [4, 0, 0, 4], "after": [bed, 0, 0, bed]}] if bed is not None else []
        ch += [{"key": "global:0x0bf1", "before": [2, 1, 1, 2], "after": [bf1, 1, 1, bf1]}] if bf1 is not None else []
        return {"kind": "list", "label": label, "changes": ch, "applied": True}

    # made-up bases: the row started on Mid (4 in 0x0bed, 2 in 0x0bf1), its option that changes nothing
    opts = {0: opt("Cont. Shooting: Hi+", 2, 0), 1: opt("Cont. Bracket", 6), 2: opt("Cont. Shooting: Mid")}
    got = R.values_of(opts)
    assert got["global:0x0bf1[0]"] == {"Cont. Shooting: Hi+": 0, "Cont. Shooting: Mid": 2}
    assert got["global:0x0bed[0]"] == {"Cont. Shooting: Hi+": 2, "Cont. Bracket": 6, "Cont. Shooting: Mid": 4}


def test_seen_change_outranks_nothing_changed_and_each_run_keeps_its_start():
    import pass2_report as R
    ch = lambda b, a: [{"key": "global:0x02b5", "before": b, "after": a}]
    # a visit that missed its option (nothing changed) after one that set it: the change stands
    opts = {0: {"kind": "list", "label": "Self-timer(Single)", "changes": ch(0, 5), "applied": True, "base": "a"},
            1: {"kind": "list", "label": "Self-timer(Single)", "changes": [], "applied": True, "base": "a"}}
    assert R.values_of(opts)["global:0x02b5"] == {"Self-timer(Single)": 5}
    # a home visit with no change takes its own run's starting value, not another run's (made-up starts)
    opts = {0: {"kind": "list", "label": "31", "changes": ch(10, 31), "applied": True, "base": "a"},
            1: {"kind": "list", "label": "60", "changes": ch(25, 60), "applied": True, "base": "b"},
            2: {"kind": "list", "label": "25", "changes": [], "applied": True, "base": "b"}}
    assert R.values_of(opts)["global:0x02b5"] == {"31": 31, "60": 60, "25": 25}


def test_a_box_keeps_its_own_records_not_the_ones_it_pushes():
    # ISO AUTO Minimum above Maximum raises Maximum too (Movie mode, 2026-11-01): Maximum's records
    # moved on 3 of Minimum's visits, so they are Maximum's row's, not Minimum's
    import pass2_report as R

    def opt(i, mn, mx=None):
        ch = [{"key": "global:0x0dfa", "before": 3, "after": mn}]
        ch += [{"key": "global:0x0e00", "before": 26, "after": mx}] if mx is not None else []
        return {"kind": "list", "label": f"ISO{i}", "changes": ch, "applied": True, "boxes": True}

    opts = {k: opt(k, 6 + k) for k in range(21)}
    opts.update({k: opt(k, 6 + k, 6 + k) for k in range(21, 25)})
    got = R.values_of(opts)
    assert set(got) == {"global:0x0dfa"} and got["global:0x0dfa"]["ISO24"] == 30


def test_two_value_axis_keeps_its_own_record_and_inferred_labels_are_listed():
    import pass2_report as R
    # WB Bracket Hi/Lo: one test visit (Hi), the held Lo last. The carousel's own row chose the option
    # and wrote 0x02b5 = 11; the axis visit also wrote 0x04ca, which is the axis's
    opts = {1: {"kind": "axis", "option": "White Balance Bracket", "label": "White Balance Bracket: Hi",
                "final": False, "applied": True,
                "changes": [{"key": "global:0x02b5", "before": 0, "after": 11},
                            {"key": "global:0x04ca", "before": 1, "after": 0}]},
            0: {"kind": "axis", "option": "White Balance Bracket", "label": "White Balance Bracket: Lo",
                "final": True, "applied": True, "changes": []}}
    got = R.values_of(opts, own={"global:0x02b5": 11})
    assert got == {"global:0x04ca": {"White Balance Bracket: Hi": 0}}
    assert R.values_of(opts) == {}                           # nothing to tell the option's own by
    rows = {"Drive Mode": {4: {"kind": "dialog", "label": "White Balance Bracket: Lo", "applied": True,
                               "changes": [{"key": "global:0x02b5", "before": 0, "after": 11}]}},
            "Drive Mode / White Balance Bracket": opts}
    assert R.own_records(rows, "Drive Mode / White Balance Bracket", opts) == {"global:0x02b5": 11}
    # two options that left a record alone: both listed as inferred (one is the row's start)
    ch = lambda a: [{"key": "global:0x0fde", "before": 18, "after": a}]
    opts = {0: {"kind": "list", "label": "ISO 100", "changes": ch(5), "applied": True},
            1: {"kind": "list", "label": "ISO 2000", "changes": [], "applied": True},
            2: {"kind": "list", "label": "ISO AUTO", "changes": [], "applied": True}}
    inferred = {}
    R.values_of(opts, inferred=inferred)
    assert inferred == {"global:0x0fde": ["ISO 2000", "ISO AUTO"]}


def test_name_rule_weighs_the_map_the_ocr_and_the_vision_reading(monkeypatch):
    # the map's label L, the bar's OCR S and the vision model's V (2026-11-07): OCR never wins alone, vision breaks
    # ties, and a reading far from both is a dispute beside the map's label
    import pass2_report as R
    monkeypatch.setattr(R, "ROW_NAMES", set())
    o = lambda label, shown=None, vlm=None: {"kind": "list", "label": label, "shown": shown, "vlm": vlm}
    assert R.name_of(o("Low", "Lw", "Low")) == ("Low", "two readers", None)                       # V ~ L
    assert R.name_of(o("Standard", "Stand-by", "Stand-by")) == ("Stand-by", "two readers", None)  # V ~ S, S != L
    name, src, seen = R.name_of(o("F11", None, "Focus Mode"))                                      # V far from both
    assert (name, src, seen["vlm"]) == ("F11", "disputed", "Focus Mode")
    assert R.name_of(o("1 (Narrow)", "1(Narrow)")) == ("1 (Narrow)", "one reader (map)", None)    # no V, S ~ L
    name, src, seen = R.name_of(o("Off", "Focus Mode"))                                           # no V, S far
    assert (name, src, seen["shown"]) == ("Off", "ocr disagrees", "Focus Mode")
    # the shipped name: OCR of two slot icons read "1/7"; the vision model's "1 / 2" backs the map's label
    assert R.name_of(o("⏮ / ⏭ This Image", "1/7 This Image", "1 / 2 This Image"))[:2] == ("⏮ / ⏭ This Image",
                                                                                         "two readers")
    # a vision reading that names a menu row read the screen, not the option: it does not count
    monkeypatch.setattr(R, "ROW_NAMES", {R.norm("Focus Mode")})
    assert R.name_of(o("F11", None, "Focus Mode")) == ("F11", "one reader (map)", None)
    # an icon glued on in the map ("LRight 1/2"), carousels keep the shown axis value, side lists the lap's label
    assert R.name_of(o("LRight 1/2", "Right 1/2"))[0] == "Right 1/2"
    assert R.name_of({**o("Continuous Shooting: Mid", "Continuous Shooting: Hi"), "kind": "dialog"})[0] == \
        "Continuous Shooting: Hi"
    assert R.name_of({**o("-3", "3"), "kind": "sidelist"})[0] == "-3"
    # a word is never dropped as an icon, and the OCR's fuller name stands; a stray capital on both is dropped
    assert R.name_of(o("Compressed", "RAW Compressed"))[0] == "RAW Compressed"
    assert R.name_of(o("EUpper Right", "HUpper Right"))[0] == "Upper Right"
    assert R.name_of(o("EUpper Right", "Upper Right", "Upper Right"))[:2] == ("Upper Right", "two readers")
    # a button the vision model read is no reading of the option
    monkeypatch.setattr(R, "ROW_NAMES", set())
    assert R.name_of(o("Manual Focus", None, "Register")) == ("Manual Focus", "one reader (map)", None)


def test_a_value_carried_over_from_the_option_before_is_not_credited():
    # one attempt of a list row: C moves 0x0001 only, A also writes 0x0002 = 5, B leaves 0x0002 where A put it while
    # 0x0001 moves on; the saved option comes back last and changes nothing. 0x0002 = 5 is A's, not B's
    import pass2_report as R
    ch = lambda **kv: [{"key": f"global:{k[1:]}", "before": 0, "after": v} for k, v in kv.items()]
    row = lambda i, label, dat, changes: {"path": ["Row"], "kind": "list", "index": i, "label": label, "attempt": "t",
                                         "dat": dat, "changes": changes}
    proofs = [row(3, "C", "00005_c.DAT", ch(_0x0001=3)), row(1, "A", "00010_a.DAT", ch(_0x0001=1, _0x0002=5)),
              row(2, "B", "00020_b.DAT", ch(_0x0001=2, _0x0002=5)), row(0, "Saved", "00030_s.DAT", [])]
    [c] = R.carried_over(proofs)
    assert (c["row"], c["key"], c["label"], c["value"]) == ("Row", "global:0x0002", "B", 5)
    opts = {p["index"]: p for p in proofs}
    got = R.values_of(opts, carried=frozenset({(c["dat"], c["key"])}))
    assert got["global:0x0002"] == {"C": 0, "A": 5, "Saved": 0} and got["global:0x0001"]["B"] == 2
    assert R.values_of(opts)["global:0x0002"]["B"] == 5                  # without the verdict, B took it
    # another proof of B writing 5 from elsewhere: a value of B's own
    assert R.carried_over(proofs + [{**proofs[2], "attempt": "u", "dat": "00040_b.DAT"}]) == []
    # a value every option that moved anything wrote (HEIF 4:2:0 and 4:2:2 alike) is shared, not carried
    assert R.carried_over(proofs[1:]) == []


def test_an_option_that_changed_nothing_is_credited_with_its_own_sessions_start_value(monkeypatch):
    # a first session's saved function changed nothing, so the record's start was its code; a later put-back of
    # "Follow" (the saved one then, 882) in a session of its own changed nothing either. befores knows only the bases
    # of proofs that moved the record, so the later base is read from its file: "Follow" is 882, never the first
    # session's code (Fn Menu Movie Lower 6, 2026-11-07; the first session's function and code made up)
    import pass2_report as R
    o = lambda i, label, base, changes: {"path": ["Fn Menu Settings"], "kind": "table", "option": "Movie Lower / 6",
                                        "opens": "picker", "index": i, "label": label, "shown": label, "applied": True,
                                        "planned": True, "base": base, "changes": changes}
    key = "global:0x0451[11]"
    opts = {0: o(0, "Image Quality Settings", "oct_base.DAT", []),
            7: o(7, "Silent Mode", "oct_base.DAT", [{"key": key, "before": 10, "after": 183}]),
            50: o(50, "Follow Fnct Menu", "today_base.DAT", [])}
    files = {("today_base.DAT", key): 882}
    monkeypatch.setattr(R, "base_value", lambda base, k: files.get((base, k)))
    got = R.values_of(opts)[key]
    assert got == {"Image Quality Settings": 10, "Silent Mode": 183, "Follow Fnct Menu": 882}
    # the record's own base file, by key and by slot
    assert R.base_value("nothing.DAT", key) is None                  # no base dirs set: nothing read


def test_picker_twins_keep_their_own_values():
    # "• AEL hold" is listed twice (42 and 44) with two codes: each keeps its own, named by its place
    import pass2_report as R
    o = lambda i, code: {"path": ["Custom Key Setting"], "kind": "table", "option": "AEL Button", "opens": "picker",
                         "index": i, "label": "• AEL hold", "shown": "AEL hold", "applied": True, "planned": True,
                         "changes": [{"key": "global:0x041c", "before": 1, "after": code}]}
    opts = {42: o(42, 808), 44: o(44, 810)}
    assert R.values_of(opts) == {"global:0x041c": {"AEL hold": 808, "AEL hold (2)": 810}}
    names = R.picker_names(opts)
    row = R.row_name(opts[42])
    assert R.not_one_to_one(list(opts.values()), row, "global:0x041c", {}, {"table"}, label_of=names) == []
    assert R.not_one_to_one(list(opts.values()), row, "global:0x041c", {}, {"table"})[0]["kind"] == "not one to one"


def test_judge_takes_a_contained_label_only_when_no_other_holds_it():
    import pass2_report as R
    # the schema's "Hi" under the camera's "Cont. Shooting: Hi+" is no agreement while "...: Hi" is proved too
    vals = {"Cont. Shooting: Hi": 1, "Cont. Shooting: Hi+": 2}
    assert R.judge(vals, {1: "Hi", 2: "Hi"})[0] == "conflict"
    assert R.judge({"5(Wide)": 4, "1 (Narrow)": 0}, {4: "5", 0: "1"})[0] == "agrees"     # a whole word
    assert R.judge({"Medium": 1}, {1: "M"})[0] != "agrees"                                 # a letter, not a word
    assert R.judge({"FINE Fine": 1, "X.FINE Extra fine": 0}, {1: "FINE", 0: "X.FINE"})[0] == "wording"
    assert R.judge({"Self-timer(Single): 10 sec": 0}, {0: "10 sec"})[0] == "agrees"
    # an abbreviation of the camera's words is wording, not a conflict, when no other label fits it as well
    modes = {"Movie: Program Auto": 2, "Movie: Aperture Priority": 3, "Movie: Shutter Priority": 4,
             "Movie: Manual Exposure": 5}
    assert R.judge(modes, {2: "P", 3: "A", 4: "S", 5: "M"})[0] == "wording"
    assert R.judge({"Medium": 1, "Small": 2, "Large": 0}, {1: "M", 2: "S", 0: "L"})[0] == "wording"
    assert [n["kind"] for n in R.judge(vals, {1: "Hi"})[1] if n["value"] == 1] == ["wording"]   # better than "Hi+"
    assert R.judge({"Large": 0, "Low": 1}, {0: "L"})[0] == "conflict"   # fits both: no telling
    assert R.judge({"P": 2, "A": 3}, {2: "Program Auto", 3: "Aperture Priority"})[0] == "wording"   # the other way
    # two options share a value and the schema names it after one of them: no conflict
    assert R.judge({"HEIF(4:2:0)": 2, "HEIF(4:2:2)": 2}, {2: "HEIF(4:2:2)"})[0] == "agrees"


def test_table_order_starts_after_the_saved_option_and_resumes(monkeypatch):
    import prove_run as P
    monkeypatch.setattr(P.proving.tables, "OWN_FILE", Path("/nonexistent/own_screen.json"))
    job = {"labels": ["AF-On", "Recall Custom hold 1", "Rating", "Protect", "Rotate"], "kind": "table", "saved": 2}
    assert P.table_order(job, 2) == [3, 4, 0, 1, 2]           # a Recall Custom hold is proved like any function (2026-11-07)
    job["done"] = [3, 4]                                      # an earlier session got that far
    assert P.table_order(job, 2) == [0, 1, 2]
    job["done"] = [0, 1, 2, 3, 4]                             # the saved one is chosen last in any case
    assert P.table_order(job, 2) == [2]
    assert P.planned(job) == {0, 1, 2, 3, 4}
    # a saved Recall Custom hold is left for the session's upload: never chosen back; it stays in the plan, which a
    # display proof of the key's start value fills (prove_table_row), since the walk's saved one can be stale
    job = {"labels": ["Recall Custom hold 3", "AF-On", "Rating"], "kind": "table", "saved": 0}
    assert P.table_order(job, 0) == [1, 2]
    assert P.planned(job) == {0, 1, 2}
    # a function learned to open a screen of its own that MENU does not leave is passed over
    learned = Path(__file__).parent / "_own_screen_test.json"
    learned.write_text('[{"screen": "Custom Key/Dial Set.#0", "name": "rating", "label": "Rating"}]', encoding="utf-8")
    try:
        monkeypatch.setattr(P.proving.tables, "OWN_FILE", learned)
        job = {"labels": ["AF-On", "Rating", "Protect"], "kind": "table", "saved": 0, "path": ["Custom Key/Dial Set."]}
        assert P.table_order(job, 0) == [2, 0]
        assert P.planned(job) == {0, 2}
    finally:
        learned.unlink()


def test_a_screen_of_a_functions_own_is_left_by_menu_or_its_saved_option(monkeypatch):
    # a Recall Custom hold's registration (checklist) and My Dial Settings (table) are left with MENU; a radio list
    # open on its saved option (Cnt Sht Spd Bst Settings) with Enter on that option; a way out that does not bring
    # the key back on its cell learns the function and fails the cell (2026-11-07)
    import prove_run as P
    from types import SimpleNamespace as NS

    class Cam:
        def __init__(self, kind, row=0, current=None, back=True):
            self.screens = [NS(kind=kind, row=row, current=current), NS(kind="keyset" if back else "picker")]
            self.frame = NS(path=Path("/tmp/228934_enter.png"))
            self.pressed = []

        def read(self):
            return self.screens[0]

        def press(self, key):
            self.pressed.append(key)
            self.screens.pop(0)

    monkeypatch.setattr(P.ocr, "read", lambda paths: {paths[0]: "img"})
    monkeypatch.setattr(P.ocr, "text_in", lambda img, box: "Recall Custom hold 1")
    monkeypatch.setattr(P.proving.tables, "on_cell", lambda cam, job: cam.read().kind == "keyset")
    learned = []
    monkeypatch.setattr(P.proving.tables, "learn_own_screen", lambda label, screen: learned.append(label))
    job = {"path": ["Custom Key/Dial Set."], "cell": [0, "key", 0], "screen": "keyset"}
    cam = Cam("checklist")
    own = P.leave_own_screen(cam, job, "AEL", "Recall Custom hold 1")
    assert cam.pressed == ["menu"] and own["left_by"] == "menu" and own["kind"] == "checklist"
    cam = Cam("table")
    assert P.leave_own_screen(cam, job, "AEL", "My Dial 1 during Hold")["left_by"] == "menu"
    cam = Cam("list", row=0, current=0)
    assert P.leave_own_screen(cam, job, "AEL", "Cnt Sht Spd Bst w/ Hold")["left_by"] == "enter on its saved option"
    assert cam.pressed == ["enter"]
    cam = Cam("list", row=1, current=0)                      # not on its saved option: MENU, never a choice
    assert P.leave_own_screen(cam, job, "AEL", "Cnt Sht Spd Bst w/ Hold")["left_by"] == "menu"
    cam = Cam("list", row=0, current=0, back=False)
    with pytest.raises(P.Failed, match="passed over"):
        P.leave_own_screen(cam, job, "AEL", "Send")
    assert learned == ["Send"]


def test_a_function_with_a_screen_of_its_own_is_credited_with_the_keys_record_alone():
    # choosing a Recall Custom hold on a key opens its registration, which copies the hold into the working slot
    # (0x18cb[3]); MENU leaves it and the key holds the function (2026-11-07): the key's record is the function's
    # value, the working copy is the screen's doing and credited to nothing
    import pass2_report as R
    key = lambda a, b: {"key": "global:0x041c", "before": 600, "after": a} if b is None else \
        {"key": "global:0x18cb[3]", "before": 5, "after": a}
    opts = {1: {"kind": "table", "label": "AF-On", "applied": True, "dat": "1.DAT", "planned": True,
                "changes": [key(4, None)]},
            2: {"kind": "table", "label": "Recall Custom hold 1", "applied": True, "dat": "2.DAT", "planned": True,
                "own_screen": {"kind": "checklist", "frame": "2_enter.png", "title": "Recall Custom hold 1"},
                "changes": [key(769, None), key(9, 1)]},
            3: {"kind": "table", "label": "Recall Custom hold 2", "applied": True, "dat": "3.DAT", "planned": True,
                "own_screen": {"kind": "checklist", "frame": "3_enter.png", "title": "Recall Custom hold 2"},
                "changes": [key(770, None), key(10, 1)]}}
    got = R.values_of(opts)
    assert got == {"global:0x041c": {"AF-On": 4, "Recall Custom hold 1": 769, "Recall Custom hold 2": 770}}
    # a record a plain function wrote only as a value carried over from the hold before is not the key's either
    opts[4] = {"kind": "table", "label": "Rating", "applied": True, "dat": "4.DAT", "planned": True,
               "changes": [key(8, None), {"key": "global:0x18cb[3]", "before": 5, "after": 10}]}
    got = R.values_of(opts, carried=frozenset({("4.DAT", "global:0x18cb[3]")}))
    assert "global:0x18cb[3]" not in got


def test_picker_codes_checked_across_slots():
    # sampled slots rest on one code per function everywhere; a slot that breaks it is named
    import pass2_report as R
    rep = [{"row": "Fn Menu Settings / Still Upper / 1", "records": {"global:0x0445[0]": {"proved": {"Zebra Level": 289, "AF-On": 4}}}},
           {"row": "Fn Menu Settings / Still Upper / 2", "records": {"global:0x0445[1]": {"proved": {"Zebra Level": 289}}}},
           {"row": "Fn Menu Settings / Movie Upper / 1", "records": {"global:0x0451[0]": {"proved": {"Zebra Level": 290}}}},
           {"row": "Image Quality Settings / SLOT 1 / File Format", "records": {"global:0x01e6": {"proved": {"AF-On": 1}}}}]
    rows = {e["row"] for e in rep[:3]}
    [(lab, codes)] = R.code_clashes(rep, rows)
    assert codes == {289: ["Fn Menu Settings / Still Upper / 1", "Fn Menu Settings / Still Upper / 2"],
                     290: ["Fn Menu Settings / Movie Upper / 1"]}


class _At:
    """Just enough of a LiveCamera for the OCR readers: the frame on screen."""
    def __init__(self, path):
        from camkit.frames import load
        self.frame = load(need(path))


def test_scale_value_leaves_out_the_arrow():
    # 2026-10-30: the ◂ beside AF Subj. Shift Sensitivity's 5 read as "1", and "15" stopped the run
    import scale_run
    assert scale_run.value(_At(A1 / "kit2_pass2" / "shots" / "118922_right.png")) == "5"
    assert scale_run.value(_At(A1 / "kit2_pass2" / "shots" / "118915_right.png")) == "3"


def test_boxes_read_both_values_and_the_focus():
    # S&Q Frame Rate Settings in the Movie crawl: Rec Frame Rate 30p (focused, OCR's Cyrillic "р"), 120fps
    import boxes_run
    cam = _At(A1 / "kit2_crawl_movie" / "shots" / "00032_right.png")
    assert (boxes_run.value(cam, 0), boxes_run.value(cam, 1), boxes_run.focus(cam)) == ("30p", "120fps", 0)


class _Dat:
    """A download in a made-up prove: its name, and the records it holds ({key: value}) for a made-up camset.diff."""
    def __init__(self, name, values):
        self.name, self.values = name, values


def _box_camera(monkeypatch, boxes):
    """boxes_run's look and choose over a made-up two-box screen, {box: [values], held} per box: each choice makes a
    download whose records are the boxes' values now; camset.read gives that, camset.diff the records that differ."""
    import types
    import boxes_run
    held = {b: h for b, (_, h) in boxes.items()}
    downloads = []

    def look(cam, link, cycle, model, path, b):
        return list(boxes[b][0]), held[b]

    def choose(cam, link, hdmi, cycle, model, path, b, vals, target):
        held[b] = vals[target]
        dat = _Dat(f"{len(downloads) + 2:05d}_{b}_{target}.DAT", dict(held))
        downloads.append(dat)
        return {"chosen_frame": "c.png", "row_frame": "r.png", "dat": dat, "vlm": vals[target]}

    def diff(a, b):
        return [types.SimpleNamespace(key=k, before=a[k], after=b[k]) for k in a if a[k] != b[k]]
    monkeypatch.setattr(boxes_run, "look", look)
    monkeypatch.setattr(boxes_run, "choose", choose)
    monkeypatch.setattr(boxes_run, "camset", types.SimpleNamespace(read=lambda d: d.values, diff=diff))
    return boxes_run, downloads


class _Lines(list):
    def write(self, line):
        self.append(json.loads(line))

    def flush(self):
        pass


def test_boxes_first_takes_one_box_and_one_value():
    """boxes_run --first BOX=VALUE: the box one of --boxes, a value after the "="; without it, None."""
    import boxes_run
    args = ["--row", "S&Q Settings > Frame Rate Settings", "--boxes", "Rec Frame Rate, Frame Rate"]
    a, path, names, first = boxes_run.arguments(args + ["--first", "Rec Frame Rate = 25p", "--only", "Frame Rate"])
    assert (path, names, first, a.only) == (["S&Q Settings", "Frame Rate Settings"], ["Rec Frame Rate", "Frame Rate"],
                                            ("Rec Frame Rate", "25p"), "Frame Rate")
    assert boxes_run.arguments(args)[3] is None
    for bad in ("Rec Frame Rate", "Shutter=1", "Frame Rate="):
        with pytest.raises(SystemExit, match="BOX=VALUE"):
            boxes_run.arguments(args + ["--first", bad])
    with pytest.raises(SystemExit, match="--only"):
        boxes_run.arguments(args + ["--only", "Shutter"])


def test_boxes_first_proves_from_the_state_it_chose(monkeypatch):
    """With --first, the value is chosen in its box before the proofs, and every proof is compared with the download
    made then (its "base"), so the value the box held before (50p) is proved as a change and the last proof, back on
    the chosen value, changes nothing; the start file is not what they are compared with (the caller still puts it
    back). Without --first, the base is the start and the held value is the one left unproved."""
    start = _Dat("00001_before.DAT", {0: "50p", 1: "100fps"})
    boxes_run, downloads = _box_camera(monkeypatch, {0: (["50p", "25p"], "50p"), 1: (["100fps", "50fps"], "100fps")})
    out = _Lines()
    names = ["Rec Frame Rate", "Frame Rate"]
    base = boxes_run.prove(None, None, None, [], {}, ["S&Q"], names, "Rec Frame Rate", ("Rec Frame Rate", "25p"), start, out)
    assert base is downloads[0] and base is not start
    assert [(r["label"], r["base"], [(c["before"], c["after"]) for c in r["changes"]]) for r in out] == [
        ("50p", base.name, [("25p", "50p")]), ("25p", base.name, [])]
    plain = _Lines()
    boxes_run2, _ = _box_camera(monkeypatch, {0: (["50p", "25p"], "50p"), 1: (["100fps", "50fps"], "100fps")})
    assert boxes_run2.prove(None, None, None, [], {}, ["S&Q"], names, "Rec Frame Rate", None, start, plain) is start
    assert [(r["label"], r["base"], len(r["changes"])) for r in plain] == [("25p", start.name, 1), ("50p", start.name, 0)]
    with pytest.raises(boxes_run.Failed, match="not one value"):
        boxes_run.prove(None, None, None, [], {}, ["S&Q"], names, None, ("Frame Rate", "60fps"), start, _Lines())


def test_prove_run_first_takes_an_axis_job_and_one_value():
    """prove_run --first "ROW / OPTION=VALUE": the axis job's name before the "=", its value after; one without " / "
    or with no value is refused before anything reaches the camera."""
    import prove_run as P
    assert P.first_values(["Drive Mode / Self-timer(Cont.) = 5 Sec. 3 Img."]) == {
        "Drive Mode / Self-timer(Cont.)": "5 Sec. 3 Img."}
    assert P.first_values(None) == {}
    for bad in ("Drive Mode=5 Sec. 3 Img.", "Drive Mode / Self-timer(Cont.)", "Drive Mode / Self-timer(Cont.)= "):
        with pytest.raises(SystemExit, match="ROW / OPTION=VALUE"):
            P.first_values([bad])


class FakeCarousel:
    """A carousel with a second axis on one option, for prove_run.prove_axis_row: Right on the row opens it on the
    saved option, Down/Up move between options, Right/Left on the axis option step its value (it wraps, and keeps
    the value it is left on), OK commits the option and the value and goes back to the row. Its title is the axis value on the axis option, else the
    option's name."""
    OPTIONS = ["Single Shooting", "Cont. Shooting", "Self-timer(Cont.)"]
    AXIS = 2

    def __init__(self, vals, held=0):
        import numpy as np
        self.vals, self.saved, self.held = vals, 0, held
        self.where, self.opt, self.value, self.keys, self.n = "row", 0, held, [], 0
        self.frame = type("F", (), {"path": Path("00000_fake.png"), "image": np.zeros((480, 640, 3), np.uint8)})()

    def press(self, key):
        self.keys.append(key)
        self.n += 1
        self.frame.path = Path(f"{self.n:05d}_{key}.png")
        if self.where == "row":
            if key == "right":
                self.where, self.opt, self.value = "dialog", self.saved, self.held
        elif key == "down":
            self.opt = (self.opt + 1) % len(self.OPTIONS)
        elif key == "up":
            self.opt = (self.opt - 1) % len(self.OPTIONS)
        elif key in ("right", "left") and self.opt == self.AXIS:
            self.value = (self.value + (1 if key == "right" else -1)) % len(self.vals)
        elif key == "enter":                       # the axis keeps the value it was left on, whichever option
            self.where, self.saved, self.held = "row", self.opt, self.value

    def read(self):
        return screen.Screen(kind="dialog" if self.where == "dialog" else "menu", row=3)

    def title(self):
        return self.vals[self.value] if self.opt == self.AXIS else self.OPTIONS[self.opt]


def _axis_camera(monkeypatch, cam):
    """prove_axis_row over FakeCarousel: each download holds the option and the axis value now (camset.read gives them,
    camset.diff the ones that differ); the place on the menu is the screen's kind."""
    import types
    import prove_run as P
    downloads = []

    def download(name):
        dat = _Dat(f"{len(downloads) + 2:05d}_{name}.DAT", {"option": cam.saved, "axis": cam.held})
        downloads.append(dat)
        return dat

    def diff(a, b):
        return [types.SimpleNamespace(key=k, before=a[k], after=b[k]) for k in a if a[k] != b[k]]
    monkeypatch.setattr(P, "axis_title", lambda c: c.title())
    monkeypatch.setattr(P, "vlm_option", lambda c: "")
    monkeypatch.setattr(P, "place", lambda c: c.read().kind)
    monkeypatch.setattr(P, "same_place", lambda a, b, tol=2: a == b)
    monkeypatch.setattr(P, "to_row", lambda *a, **k: None)
    monkeypatch.setattr(P, "after_download", lambda c, done: None)
    monkeypatch.setattr(P, "camset", types.SimpleNamespace(read=lambda d: d.values, diff=diff))
    return P, types.SimpleNamespace(download=download), downloads


def test_axis_first_proves_from_the_value_it_chose(monkeypatch):
    """With --first, the value is chosen first and every later proof is compared with the download made then, so the
    value the axis held (10 Sec.) is proved as a change too; the last proof, back on the chosen value, changes nothing,
    and the carousel, which now opens on the axis option, is backed up by none (its saved title the chosen value).
    Without it, the held value is the one left unproved and the carousel is backed up to the option it opened on."""
    vals = ["10 Sec. 3 Img.", "5 Sec. 3 Img.", "2 Sec. 3 Img."]
    job = {"path": ["Drive Mode"], "kind": "axis", "option": "Self-timer(Cont.)", "values": vals}
    start = _Dat("00001_start.DAT", {"option": 0, "axis": 0})
    cam = FakeCarousel(vals)
    P, link, downloads = _axis_camera(monkeypatch, cam)
    monkeypatch.setitem(P.FIRST, "Drive Mode / Self-timer(Cont.)", "2 Sec. 3 Img.")
    out = _Lines()
    last = P.prove_axis_row(cam, link, None, job, start, out)
    assert last is downloads[-1] and len(out) == 4
    first = downloads[0]
    assert [(r["label"], r["base"], r["final"], [(c["key"], c["before"], c["after"]) for c in r["changes"]])
            for r in out] == [
        ("2 Sec. 3 Img.", start.name, False, [("option", 0, 2), ("axis", 0, 2)]),
        ("10 Sec. 3 Img.", first.name, False, [("axis", 2, 0)]),
        ("5 Sec. 3 Img.", first.name, False, [("axis", 2, 1)]),
        ("2 Sec. 3 Img.", first.name, True, [])]
    assert "up" not in cam.keys                                       # the carousel opens on the axis option now
    assert (cam.saved, cam.held) == (2, 2)                            # the start file puts the rest back (the caller)

    plain = FakeCarousel(vals)
    P, link, downloads = _axis_camera(monkeypatch, plain)
    monkeypatch.delitem(P.FIRST, "Drive Mode / Self-timer(Cont.)")
    out = _Lines()
    P.prove_axis_row(plain, link, None, job, start, out)
    assert [(r["label"], r["base"], len(r["changes"])) for r in out] == [
        ("5 Sec. 3 Img.", start.name, 2), ("2 Sec. 3 Img.", start.name, 2), ("10 Sec. 3 Img.", start.name, 0)]
    assert plain.keys.count("up") == 2 and (plain.saved, plain.held) == (0, 0)


def test_axis_first_refuses_a_value_the_axis_does_not_have(monkeypatch):
    vals = ["10 Sec. 3 Img.", "5 Sec. 3 Img."]
    job = {"path": ["Drive Mode"], "kind": "axis", "option": "Self-timer(Cont.)", "values": vals}
    cam = FakeCarousel(vals)
    P, link, downloads = _axis_camera(monkeypatch, cam)
    monkeypatch.setitem(P.FIRST, "Drive Mode / Self-timer(Cont.)", "3 Sec. 3 Img.")
    with pytest.raises(P.Failed, match="not one of its values"):
        P.prove_axis_row(cam, link, None, job, _Dat("00001_start.DAT", {"option": 0, "axis": 0}), _Lines())
    assert downloads == [] and "enter" not in cam.keys


# the a1 II's Focus Area axes in the camera's Right order (the axis walk's spellings), each from the definition's first
# value of the axis (Spot S, Custom 1, Tracking: Wide): the order is a cycle, so where a list starts changes nothing
FOCUS_AXES = {
    "Spot": ["Spot: S", "Spot: XS", "Spot: XL", "Spot: L", "Spot: M"],
    "Custom": ["Custom 1", "Custom 2", "Custom 3"],
    "Tracking": ["Tracking: Wide", "Tracking: Zone", "Tracking: Center Fix", "Tracking: Spot XL", "Tracking: Spot L",
                 "Tracking: Spot M", "Tracking: SpotS", "Tracking: Spot XS", "Tracking: Expand Spot",
                 "Tracking: Custom 1", "Tracking: Custom 2", "Tracking: Custom 3"]}


def test_an_axis_strips_cells_name_the_lit_value_by_their_short_text_and_place(monkeypatch):
    """proving.screens.strip_value, on readings given: each cell's short text names a value ("C3" Custom 3, "XL" Spot: XL
    and Tracking: Spot XL), and with its place one for the lit cell ("C2" one left of it: Custom 3). Every reading must
    name the same value, none a short text the axis lacks; the title must read as the option's (a Tracking title is
    never the Custom axis's); an axis whose cells are icons, as most are, is never read off the frame at all."""
    from proving import screens
    assert [screens.cell_code(v) for v in FOCUS_AXES["Tracking"]] == [
        None, None, None, "XL", "L", "M", "S", "XS", None, "C1", "C2", "C3"]
    assert [screens.cell_code(v) for v in FOCUS_AXES["Custom"] + ["Wide", "Spot: Standard", "10 Sec. 3 Img."]] == [
        "C1", "C2", "C3", None, None, None]
    reads = {"C2": "C2", "#C1": "C1", "••• M": "M", "®*ХS": "XS", "XL.": "XL", "(1": "C1", "#СЗ": "C3", "c3": "C3",
             "EСЗ": None, "L ]": None, "L] >": None, "OXL": None, "TX": None, "10": None, "": None}
    assert {t: screens.cell_text_code(t) for t in reads} == reads
    cells = []
    monkeypatch.setattr(screens, "axis_lit_x", lambda image: 380.0)
    monkeypatch.setattr(screens, "axis_cells", lambda f, lit_x: list(cells))
    cam = type("Cam", (), {"frame": type("F", (), {"image": None, "path": Path("00206_reread.png")})()})()
    custom, tracking, spot = FOCUS_AXES["Custom"], FOCUS_AXES["Tracking"], FOCUS_AXES["Spot"]
    cells[:] = [("apple", "C2", -1), ("rapidocr", "(1", -2)]
    got, how = screens.strip_value(cam, custom, "Customß 7")
    assert got == 2 and how == {"read_by": "axis cell", "cell_readings": [
        {"reader": "apple", "text": "C2", "offset": -1}, {"reader": "rapidocr", "text": "(1", "offset": -2}]}
    assert screens.strip_value(cam, custom, "Customß 7", "C3")[0] == 2           # the vision model's "C3" agrees
    assert screens.strip_value(cam, custom, "Customß 7", "C1") == (None, {})     # and when it does not, nothing
    assert screens.strip_value(cam, tracking, "Customß 7") == (None, {})         # not the Tracking option's title
    assert screens.strip_value(cam, custom, "Tracking: Custom4") == (None, {})   # nor the Custom option's
    cells[:] = [("apple", "XS", 1)]
    assert screens.strip_value(cam, custom, "Customß 7") == (None, {})           # a size on the Custom strip
    cells[:] = [("apple", "#C1", -2), ("apple", ":C2", -1), ("apple", "#CЗ", 0)]
    assert tracking[screens.strip_value(cam, tracking, "Tracking: Custom4")[0]] == "Tracking: Custom 3"
    cells[:] = [("apple", "XL", 0), ("rapidocr", "M", 2)]
    assert spot[screens.strip_value(cam, spot, "Spot: X?")[0]] == "Spot: XL"
    cells[:] = []
    assert screens.strip_value(cam, spot, "Spot: X?") == (None, {})              # nothing read: nothing named
    monkeypatch.setattr(screens, "axis_lit_x", lambda image: None)
    cells[:] = [("apple", "C2", -1)]
    assert screens.strip_value(cam, custom, "Customß 7") == (None, {})           # no lit cell: a greyed strip
    blind = type("Cam", (), {})()                                                # no frame: never looked at
    assert screens.strip_value(blind, ["10 Sec. 3 Img.", "5 Sec. 3 Img."], "1 Sec. 3 Img.") == (None, {})


def test_an_axis_proof_says_when_the_strips_lit_cell_read_its_value(monkeypatch):
    """prove_axis_row: a value whose title names none, read off the strip's lit cell instead (prove_run.axis_reading
    falls back to proving.screens.strip_value), is proved as any other, and its proof line says so ("read_by": "axis
    cell", with the cell readings); the lines read by their title carry neither."""
    vals = ["Custom 1", "Custom 2", "Custom 3"]
    job = {"path": ["Focus Area"], "kind": "axis", "option": "Custom 1", "values": vals}
    cam = FakeCarousel(vals)
    P, link, downloads = _axis_camera(monkeypatch, cam)
    monkeypatch.setattr(P, "axis_title", lambda c: "Customß 7" if c.title() == "Custom 3" else c.title())
    how = {"read_by": "axis cell", "cell_readings": [{"reader": "apple", "text": "C2", "offset": -1}]}
    monkeypatch.setattr(P, "strip_value", lambda c, v, t, vlm: (2, dict(how)) if t == "Customß 7" else (None, {}))
    out = _Lines()
    P.prove_axis_row(cam, link, None, job, _Dat("00001_start.DAT", {"option": 0, "axis": 0}), out)
    assert [(r["label"], r.get("read_by"), r.get("cell_readings")) for r in out] == [
        ("Custom 2", None, None), ("Custom 3", "axis cell", how["cell_readings"]), ("Custom 1", None, None)]


@pytest.mark.parametrize("name, axis, title_reads", [
    ("kit2_afreg2/shots/00206_reread.png", "Custom", None), ("kit2_pass2/shots/234940_reread.png", "Custom", None),
    ("kit2_pass2/shots/34442_reread.png", "Tracking", None), ("kit2_afreg2/shots/00204_reread.png", "Custom", "Custom 2"),
    ("kit2_afreg2/shots/00065_reread.png", "Spot", "Spot: XL"), ("kit2_pass2/shots/34331_reread.png", "Tracking", "Tracking: SpotS")],
    ids=["custom-3-2026-11-09", "custom-3-2026-11-08", "tracking-custom-3", "custom-2", "spot-xl", "tracking-spot-s"])
def test_the_cameras_own_strips_read_as_their_titles(monkeypatch, name, axis, title_reads):
    """The a1 II's Focus Area frames, read by this computer's OCR (skipped without runs/ or an OCR engine): Custom 3's box
    drawn over its title ("Customß 7", 2026-11-08 and 2026-11-09; "Tracking: Custom4") is read off the strip's lit cell
    as Custom 3, and the run's failing frame, 00206, through prove_run.axis_reading as a run reads it; where the title
    names its value, axis_reading takes the title (no "read_by") and the strip, read alone, names the same value. The
    other options' axes never read a frame of this one."""
    import prove_run as P
    from camkit import ocr
    from proving import screens
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = load(need(A1 / name))
    cam = type("Cam", (), {"frame": f, "refresh": lambda self, tag: None})()
    monkeypatch.setattr(P, "vlm_option", lambda c: "")                    # no vision model: the strip alone decides
    monkeypatch.setattr(P, "axis_title", lambda c: screens.carousel_text(c))
    vals = FOCUS_AXES[axis]
    want = title_reads or {"Custom": "Custom 3", "Tracking": "Tracking: Custom 3"}[axis]
    title = screens.carousel_text(cam)
    got, how = screens.strip_value(cam, vals, title)
    assert got is not None and vals[got] == want and how["read_by"] == "axis cell", (title, how)
    got, how = P.axis_reading(cam, vals)
    named = P.option_key(title) == P.option_key(want)              # the title read whole (this computer's OCR)
    assert vals[got] == want and how == ({} if named else {**how, "read_by": "axis cell"}), (title, how)
    assert named or not title_reads, f"the title {title!r} no longer names {want!r}"
    for other in set(FOCUS_AXES) - {axis}:
        assert screens.strip_value(cam, FOCUS_AXES[other], title) == (None, {}), other


class FakeMenuOpening:
    """The camera as prove_run.session meets it: MENU answered or not (the lock after a download: `locked` presses go
    unanswered), and the menu reopening with the focus in the group column or on the rows."""
    def __init__(self, locked=0, focus="rows", known=True, right_opens=None):
        import numpy as np
        self.locked, self.focus, self.known, self.kind, self.keys = locked, focus, known, "shooting", []
        self.right_opens = right_opens              # what Right opens when the cursor was really on a row
        self.frame = type("F", (), {"path": Path("00000_fake.png"), "image": np.zeros((480, 640, 3), np.uint8)})()
        self.may_open = frozenset()

    def press(self, key):
        self.keys.append(key)
        if key == "menu" and self.kind == "shooting":
            if self.locked:
                self.locked -= 1
            else:
                self.kind = "menu"
        elif key == "menu" and self.kind not in ("menu", "shooting"):
            self.kind = "menu"                      # MENU cancels what Right opened
        elif key == "right" and self.kind == "menu":
            if self.right_opens:
                self.kind = self.right_opens
            else:
                self.focus = "rows"

    def read(self):
        return screen.Screen(kind=self.kind, focus=self.focus if self.kind == "menu" else None,
                             signature="known" if self.known else "elsewhere")

    def cancel_to_menu(self):
        return True


def _session(monkeypatch, cam):
    import types
    import prove_run as P
    slept, pressed = [], []
    monkeypatch.setattr(P, "LiveCamera", lambda *a, **k: cam)
    monkeypatch.setattr(P, "same_position", lambda s, p: s.kind == "menu" and s.focus == "rows" and s.signature == p)
    monkeypatch.setattr(P.time, "sleep", slept.append)
    link = types.SimpleNamespace(press=lambda key, cleanup=False: pressed.append(key))
    status = P.session(link, None, None, [{"screen": "known"}], {}, [], None, _Lines(), _Lines())
    return P, status, slept, pressed


def test_session_waits_out_the_menu_lock_and_leaves_the_group_column(monkeypatch):
    """session(): MENU that leaves the shooting screen up (the lock after a download) is pressed once more after
    LOCK_S; a menu that reopens with the focus in the group column gets one Right, onto the page's rows, before the scan
    is matched. A menu that opens on the rows straight away gets neither."""
    cam = FakeMenuOpening(locked=1, focus="groups")
    P, status, slept, pressed = _session(monkeypatch, cam)
    assert status == "done" and cam.keys == ["menu", "menu", "right"] and slept == [P.LOCK_S]
    assert pressed == ["menu"]                                          # the session closes the menu at its end
    cam = FakeMenuOpening()
    P, status, slept, _ = _session(monkeypatch, cam)
    assert status == "done" and cam.keys == ["menu"] and slept == []
    cam = FakeMenuOpening(locked=2)                                     # still locked after the wait: no third MENU
    P, status, slept, _ = _session(monkeypatch, cam)
    assert status == "error" and cam.keys == ["menu", "menu"] and slept == [P.LOCK_S]
    cam = FakeMenuOpening(known=False)                                  # a page the scan does not know: fails closed
    P, status, _, _ = _session(monkeypatch, cam)
    assert status == "error" and cam.keys == ["menu"]
    # the cursor was really on a row and Right opened it (a Drive Mode screen, 2026-11-06): MENU cancels it at
    # once, nothing chosen, and the session stops rather than walk on
    cam = FakeMenuOpening(focus="groups", right_opens="dialog")
    P, status, _, _ = _session(monkeypatch, cam)
    assert status == "error" and cam.keys == ["menu", "right", "menu"] and cam.kind == "menu"


class FakeSlidingEyes:
    """Eyes whose frames read as a menu with no focus for the first `moving` settles, then as a page at rest."""
    def __init__(self, moving: int):
        self.moving, self.settles = moving, []

    def frame_of(self, focus):
        return type("F", (), {"path": Path(f"{len(self.settles):05d}_f.png"), "focus": focus})()

    def settle(self, before, tag, expect_change=None, quiet=0.2, timeout=3.0, **_):
        self.settles.append((tag, quiet))
        self.moving -= 1
        return self.frame_of(None if self.moving >= 0 else "rows"), True


def test_session_steps_off_a_never_open_group_before_entering_the_rows(monkeypatch):
    # the menu reopened with Accessibility (the Screen Reader's group) lit in the group column, where failed attempts
    # left it (2026-11-07): Right there is refused by the guard, so the session goes Up first
    import prove_run as P
    cam = FakeMenuOpening(focus="groups")
    lit = {"n": 0}
    real_press = cam.press
    def press(key):
        if key == "up":
            lit["n"] += 1
        real_press(key)
    cam.press = press
    monkeypatch.setattr(P, "lit_text", lambda image, path: "Accessibility" if lit["n"] == 0 else "Touch Operation")
    monkeypatch.setattr(P, "open_refused", lambda text, may_open=frozenset(): "never" if "Accessib" in text else "")
    P, status, _, _ = _session(monkeypatch, cam)
    assert status == "done" and cam.keys == ["menu", "up", "right"], cam.keys


def test_live_camera_looks_again_while_the_menu_slides(monkeypatch):
    """LiveCamera.rest: a menu read with no focus (the rows panel between its two places) is looked at again, with a
    longer quiet window, until it is at rest, at most three times; a menu at rest is left alone."""
    from camkit import live
    monkeypatch.setattr(live.screen, "read", lambda f: screen.Screen(kind="menu", focus=f.focus))
    cam = live.LiveCamera.__new__(live.LiveCamera)
    eyes = FakeSlidingEyes(moving=2)
    cam.hdmi, cam.frame, cam.screen = eyes, eyes.frame_of(None), screen.Screen(kind="menu", focus=None)
    assert cam.rest("menu-rest").focus == "rows"
    assert [t for t, _ in eyes.settles] == ["menu-rest", "menu-rest", "menu-rest"] and all(q >= 0.5 for _, q in eyes.settles)
    eyes = FakeSlidingEyes(moving=9)
    cam.hdmi, cam.frame, cam.screen = eyes, eyes.frame_of(None), screen.Screen(kind="menu", focus=None)
    assert cam.rest("menu-rest").focus is None and len(eyes.settles) == 3
    eyes = FakeSlidingEyes(moving=0)
    cam.hdmi, cam.frame, cam.screen = eyes, eyes.frame_of("rows"), screen.Screen(kind="menu", focus="rows")
    assert cam.rest("menu-rest").focus == "rows" and eyes.settles == []


def test_osd_settle_waits_two_renewals(monkeypatch):
    """OsdSource.settle: the SDK's OSD image renews every 0.25-0.37 s, so the quiet window is never shorter than QUIET
    (two renewals with the same picture), whatever a caller asks; a press that shows nothing is given LATE before it
    counts as ignored; a picture that changes once more after a short pause (a menu sliding in) is waited out."""
    import numpy as np
    from camkit import frames

    class Clock:
        t = 0.0

    def tick(dt):
        Clock.t += dt

    monkeypatch.setattr(frames.time, "monotonic", lambda: Clock.t)
    monkeypatch.setattr(frames.time, "sleep", tick)
    pictures = [(0.0, 0), (0.33, 1), (0.66, 2), (0.99, 3)]      # (from when, which picture): a menu sliding in
    src = frames.OsdSource.__new__(frames.OsdSource)
    src.run = type("R", (), {"shot_path": staticmethod(lambda tag: Path("/dev/null"))})()
    shown = []

    def peek():
        which = max(w for t0, w in pictures if t0 <= Clock.t)
        shown.append(which)
        f = frames.Frame(np.full((480, 640, 3), which * 30, np.uint8), Clock.t, None, "osd")
        tick(0.01)
        return f
    monkeypatch.setattr(src, "peek", peek)
    monkeypatch.setattr(frames.Frame, "save", lambda self, path: path)
    before = peek()
    f, moved = src.settle(before, "x", expect_change=True, quiet=0.2)
    assert moved and shown[-1] == 3 and Clock.t >= 0.99 + frames.OsdSource.QUIET     # quiet=0.2 stopped on picture 1
    # nothing changes: a change expected is waited for LATE, not 1 s
    Clock.t, shown[:] = 100.0, []
    pictures[:] = [(0.0, 7)]
    before = peek()
    t0 = Clock.t
    f, moved = src.settle(before, "x", expect_change=True)
    assert not moved and Clock.t - t0 >= frames.OsdSource.LATE


def test_a_single_option_lists_records_are_the_ones_proved_in_the_closest_state():
    """display_records: of the settings proved through the row, those whose proof context is wholly part of the run's
    and names the most of it; a context the run is not in (another file format) never counts; none proved through the
    row gives none."""
    import prove_run as P
    row = "Movie Settings > Rec Frame Rate"
    settings = [{"key": "global:0x0001", "proved": {"menu": [row]}},
                {"key": "global:0x0002", "proved": {"menu": [f"{row} [Movie mode, File Format XAVC HS 8K]"]}},
                {"key": "global:0x0003", "proved": {"menu": [f"{row} [Movie mode, PAL, File Format XAVC HS 4K]",
                                                             f"{row} [Movie mode, File Format XAVC HS 4K]"]}},
                {"key": "global:0x0004", "proved": {"menu": [f"{row} [Movie mode]"]}},
                {"key": "global:0x0005", "proved": {"menu": ["File Format [Movie mode, File Format XAVC HS 8K]"]}},
                {"key": "global:0x0006"}]
    path = row.split(" > ")
    assert P.display_records(settings, path, "Movie mode, PAL, File Format XAVC HS 8K") == ["global:0x0002"]
    assert P.display_records(settings, path, "Movie mode, PAL") == ["global:0x0004"]
    assert P.display_records(settings, path, None) == ["global:0x0001"]
    assert P.display_records(settings, ["Shoot Mode"], "Movie mode") == []


class FakeOneOption:
    """A list row whose list offers one option: Right opens it, MENU (cancel_to_menu) closes it with nothing chosen;
    OK is never expected."""
    def __init__(self):
        import numpy as np
        self.kind, self.keys = "submenu", []
        self.frame = type("F", (), {"path": Path("00010_row.png"), "image": np.zeros((480, 640, 3), np.uint8)})()

    def press(self, key):
        self.keys.append(key)
        if key == "right":
            self.kind, self.frame.path = "list", Path("00011_right.png")

    def read(self):
        return screen.Screen(kind=self.kind, count=1 if self.kind == "list" else None, row=0)

    def cancel_to_menu(self):
        self.keys.append("menu")
        self.kind, self.frame.path = "submenu", Path("00012_menu.png")
        return True


def _one_option(monkeypatch, tmp_path, ocr_text="25p", vlm_text="25p", context="Movie mode, PAL, File Format XAVC HS 8K"):
    """prove_row on FakeOneOption with a made-up definition that proved the row's 8K rate record (global:0x0202) under
    File Format XAVC HS 8K; the proof starts from the definition's sample. Returns (prove_run, cam, the proofs, the
    value 0x0202 holds in the sample, what prove_row returned)."""
    import types
    import prove_run as P
    row = "Movie Settings > Rec Frame Rate"
    doc = {"settings": [{"key": "global:0x0202", "proved": {"menu": [f"{row} [Movie mode, File Format XAVC HS 8K]"]}},
                        {"key": "global:0x0204", "proved": {"menu": [f"{row} [Movie mode, File Format XAVC HS 4K]"]}}]}
    (tmp_path / "def.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(P.definitions, "active", lambda required=True: tmp_path / "def.json")
    monkeypatch.setattr(P, "CONTEXT", context)
    monkeypatch.setattr(P, "bar_text", lambda c: ocr_text)
    monkeypatch.setattr(P, "vlm_option", lambda c: vlm_text)
    monkeypatch.setattr(P, "place", lambda c: c.read().kind)
    rowed = []
    monkeypatch.setattr(P, "to_row", lambda cam, path, top=None, row_place=None: rowed.append(path))
    cam, out = FakeOneOption(), _Lines()

    def no_download(name):
        raise AssertionError("a display proof downloads nothing")
    link = types.SimpleNamespace(download=no_download)
    run = types.SimpleNamespace(dir=tmp_path)
    job = {"path": ["Movie Settings", "Rec Frame Rate"], "labels": ["25p"], "kind": "list"}
    got = P.prove_row(cam, link, run, job, SAMPLE, out)
    assert rowed == [job["path"]]                                     # back on the row, as after any proof
    return P, cam, out, camset.read(SAMPLE).get(0, 0x0202).value(), got


def test_a_single_option_list_is_proved_by_its_display(monkeypatch, tmp_path):
    """A list that opens with one option: nothing is chosen (no OK, no download), MENU leaves it, and one proof line,
    "proof": "display", holds the option's label, both readings, and the value the row's record in this state holds in
    the file the proof starts from ("dat" and "base" both); the attempt is recorded as finished."""
    P, cam, out, held, got = _one_option(monkeypatch, tmp_path)
    assert got == SAMPLE and cam.keys == ["right", "menu"] and "enter" not in cam.keys
    (r,) = out
    assert (r["kind"], r["proof"], r["index"], r["label"], r["shown"], r["vlm"]) == ("list", "display", 0, "25p", "25p", "25p")
    assert r["held"] == [{"key": "global:0x0202", "value": held}] and r["changes"] == [] and r["applied"] is True
    assert r["dat"] == r["base"] == SAMPLE.name and (r["chosen_frame"], r["row_frame"]) == ("00011_right.png", "00012_menu.png")
    done = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(a["attempt"], a["row"]) for a in done] == [(r["attempt"], "Movie Settings > Rec Frame Rate")]


@pytest.mark.parametrize("ocr_text, vlm_text, context, words", [
    ("25p", "", "Movie mode, PAL, File Format XAVC HS 8K", "the vision model read"),
    ("50p", "25p", "Movie mode, PAL, File Format XAVC HS 8K", "OCR read"),
    ("25p", "25p", "Movie mode, PAL, File Format XAVC S HD", "no record of the definition")])
def test_a_single_option_display_proof_needs_both_readers_and_a_known_record(monkeypatch, tmp_path, ocr_text, vlm_text,
                                                                             context, words):
    """Both readers must name the one option, and the definition must have proved a record of the row in a state the
    run is in: otherwise the row fails and nothing is written."""
    import prove_run as P
    with pytest.raises(P.Failed, match=words):
        _one_option(monkeypatch, tmp_path, ocr_text, vlm_text, context)
    assert not (tmp_path / "attempts.jsonl").exists()


def test_pass3_pal_entries_name_what_a_walk_needs():
    """pass3_run's PAL entries (the owner set NTSC/PAL to PAL by hand, 2026-11-06): each names its menu switch (a row
    and the option), the map its labels come from, the OSD scan, a run folder of its own, the context, the rows it
    proves, and runs only when --only names it; an entry with "first" names the state chosen before (row, option,
    map), and its map is the walk an earlier PAL entry made. None is switched by a file (decision 6)."""
    import pass3_run
    pal = [b for b in pass3_run.BLOCKERS if b.get("name", "").startswith("PAL ")]
    assert len(pal) == 13
    for b in pal:
        assert {"row", "to", "map", "walk", "scan", "run", "context", "rows"} <= set(b) and "set" not in b, b["name"]
        assert b["on_request"] is True and b["prove_eyes"] == "osd-all" and b["scan"].endswith("_osd"), b["name"]
        assert all(isinstance(r, str) and " > " in r for r in b["rows"]) and "PAL" in b["context"], b["name"]
    assert len({b["run"] for b in pal}) == len(pal)                     # no two walks into one folder
    runs = {b["run"] for b in pal}
    later = [b for b in pal if b.get("first")]
    assert len(later) == 5
    for b in later:
        assert all({"row", "to", "map"} <= set(pre) for pre in b["first"]), b["name"]
        assert b["map"].split("/")[0] in runs and b["run"] != b["map"].split("/")[0], b["name"]


def test_pass3_only_selects_the_named_entries():
    """--only runs the blockers it names (by name, else the first label of the row); without it every blocker but
    those run only on request, so no PAL entry runs unasked."""
    import pass3_run
    assert [b["name"] for b in pass3_run.selected(["PAL XAVC S 4K", "PAL S&Q"])] == ["PAL XAVC S 4K", "PAL S&Q"]
    assert [b["row"] for b in pass3_run.selected(["Shutter Type"])] == [["Shutter Type"]]
    plain = pass3_run.selected(None)
    assert plain and not any(b.get("on_request") for b in plain)
    assert not any(b.get("name", "").startswith("PAL") for b in plain)


def test_pass3_walk_steps_and_the_first_states(monkeypatch):
    """A blocker's walk: one crawl per walked row, the labels, the third reader, the run's own map (--own, never pass
    1's map_all.json), the proofs over that map in the blocker's scan, context, eyes and rows. The third reader failing
    stops nothing; the labels failing stops the map and the proofs. Its state: each "first" switch, then its own."""
    import pass3_run
    calls, codes = [], {}

    def step(args, log):
        calls.append(args[1:])
        return codes.get(Path(next(a for a in args[1:] if a.startswith("kit/"))).stem, 0)
    monkeypatch.setattr(pass3_run, "step", step)
    b = next(b for b in pass3_run.BLOCKERS if b.get("name") == "PAL XAVC S 4K from 25p")
    folder, scan = pass3_run.RUN_ROOT / b["run"], str(pass3_run.RUN_ROOT / b["scan"])
    codes["tiebreak"] = 1
    assert pass3_run.walk_and_prove(b, None) == 0
    assert calls == [
        ["-u", "kit/crawl_run.py", "--run", b["run"], "--start-label", "Movie Settings", "--limit", "1", "--scan", scan],
        ["kit/pass1_labels.py", str(folder)],
        ["-u", "kit/tiebreak.py", str(folder)],
        ["kit/pass1_map.py", "--own", str(folder)],
        ["-u", "kit/prove_run.py", "--map", str(folder / "map.json"), "--retry-failed", "--scan", scan,
         "--context", b["context"], "--eyes", "osd-all", "--rows", "Movie Settings > Rec Frame Rate"]]
    calls.clear()
    codes.update(pass1_labels=1)
    assert pass3_run.walk_and_prove(b, None) == 1
    assert [c[1] if c[0] == "-u" else c[0] for c in calls] == ["kit/crawl_run.py", "kit/pass1_labels.py"]
    switched = []
    monkeypatch.setattr(pass3_run, "switch", lambda link, hdmi, run, cycle, model, x: switched.append((x["row"], x["to"])))
    monkeypatch.setattr(pass3_run.time, "sleep", lambda s: None)
    pass3_run.enter_state(None, None, None, [], {}, b)
    assert switched == [(["File Format"], "XAVC S 4K"), (["Movie Settings", "Rec Frame Rate"], "25p")]
    switched.clear()
    pass3_run.enter_state(None, None, None, [], {}, next(x for x in pass3_run.BLOCKERS if x.get("name") == "PAL S&Q"))
    assert switched == [(["File Format"], "XAVC S 4K")]


def test_apple_helper_lines_go_to_the_file_they_name():
    """The Apple helper prints one line per image naming its "file": a line a library prints in between, or the lines
    in another order, never put one frame's text on another (they were zipped onto the paths by position); an image
    the output names nowhere is an error."""
    from camkit import ocr
    a, b = Path("/runs/x/00001_a.png"), Path("/runs/x/00002_b.png")
    line = lambda p, text: json.dumps({"file": str(p), "lines": [{"text": text}]})          # noqa: E731
    out = "\n".join(["2026-11-07 a library's warning", line(b, "B"), line(a, "A")])
    assert ocr._apple_lines(out, [a, b]) == ({a: [{"text": "A"}], b: [{"text": "B"}]}, "")
    found, failed = ocr._apple_lines(line(a, "A"), [a, b])
    assert found == {a: [{"text": "A"}]} and "00002_b.png (no reading)" in failed
    # a line carrying "error" is a failed reading, not a frame without text, and the helper's words say why, also
    # from an error line that names no file
    broken = json.dumps({"file": str(b), "lines": [], "error": "the image could not be read"})
    found, failed = ocr._apple_lines(line(a, "A") + "\n" + broken, [a, b])
    assert found == {a: [{"text": "A"}]} and "00002_b.png (the image could not be read)" in failed
    found, failed = ocr._apple_lines(json.dumps({"error": "the result could not be written", "lines": []}), [a])
    assert not found and "the helper said: the result could not be written" in failed


def test_ocr_read_keeps_what_the_helper_read_and_says_what_it_could_not(tmp_path, monkeypatch):
    from camkit import ocr
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(b"one")
    b.write_bytes(b"two")
    out = "\n".join([json.dumps({"file": str(a), "lines": [{"text": "A", "conf": 1, "x": 0, "y": 0, "w": 1, "h": 1}]}),
                     json.dumps({"file": str(b), "lines": [], "error": "Vision: busy"})])
    monkeypatch.setattr(ocr.subprocess, "run", lambda *args, **kw: type("R", (), {"stdout": out})())
    monkeypatch.setattr(ocr, "_cache", {})
    with pytest.raises(RuntimeError, match="Vision: busy"):
        ocr.read([a, b], "apple")
    assert [ln.text for ln in ocr.read([a], "apple")[a]] == ["A"]          # kept: not asked again


def test_rapidocr_lines_in_reading_order(monkeypatch):
    """RapidOCR's boxes come back in the Apple helper's shape: a row's lines left to right, rows
    top to bottom (lines within 8 px share a row)."""
    from camkit import ocr

    def box(x0, y0, x1, y1):
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    found = [(box(470, 104, 560, 130), "Standard", 0.9), (box(140, 50, 300, 78), "File Format", 0.95),
             (box(140, 100, 320, 128), "Movie Settings", 0.9), (box(500, 52, 600, 76), "XAVC S 4K", 0.8)]
    monkeypatch.setattr(ocr, "_rapid", lambda path: (found, None))
    lines = ocr._rapidocr(Path("unused.png"))
    assert [ln["text"] for ln in lines] == ["File Format", "XAVC S 4K", "Movie Settings", "Standard"]
    assert lines[0] == {"text": "File Format", "conf": 0.95, "x": 140, "y": 50, "w": 160, "h": 28}


def test_capture_input_per_os(monkeypatch):
    from camkit import frames
    monkeypatch.setattr(frames.sys, "platform", "darwin")
    assert frames.capture_input("Cam Link 4K", (1920, 1080), 59.94)[-2:] == ["-i", "Cam Link 4K:none"]
    monkeypatch.setattr(frames.sys, "platform", "linux")
    args = frames.capture_input("/dev/video2", (1920, 1080), 60)
    assert args[:2] == ["-f", "v4l2"] and args[-2:] == ["-i", "/dev/video2"]
    monkeypatch.setattr(frames.sys, "platform", "win32")
    monkeypatch.setattr(frames.os, "name", "nt")
    args = frames.capture_input("Cam Link 4K", (1920, 1080), 60)
    assert args[:2] == ["-f", "dshow"] and args[-2:] == ["-i", "video=Cam Link 4K"]


DISP_LOOK = A1 / "kit2_disp_look"


@pytest.mark.parametrize("frame,radio,chosen", [
    ("00018_right.png", False, None),       # a plain box: the radio reader stays out
    ("00020_down.png", True, True),         # Exposure: On, the chosen dot under the bar
    ("00021_down.png", True, False),        # Exposure: TimeOut, not chosen
])
def test_disp_radio_dots(frame, radio, chosen):
    """DISP Set's radio sub-options (2026-10-30): an indented bar with no slot; the dot is red when
    chosen, grey when not, under the bar or not."""
    import prove_run

    class Cam:
        def __init__(self, f):
            self.frame = load(need(DISP_LOOK / "shots" / f))

        def read(self):
            return screen.read(self.frame)
    cam = Cam(frame)
    assert prove_run.on_radio(cam) is radio
    assert prove_run.radio_state(cam) is chosen


def test_ok_button_beside_a_ticked_row():
    """DISP Set's OK sits level with "For viewfinder": the row's red tick must not widen the button."""
    import prove_run

    class Cam:
        frame = load(need(A1 / "kit2_disp_look2" / "shots" / "00008_right.png"))

        def read(self):
            return screen.read(self.frame)
    assert prove_run.focused_button(Cam()) == "OK"


def test_custom_shoot_hold_screen():
    """A Recall Custom hold's screen: the cursor on a label or on its tick, and Register under the list."""
    import customshoot_run as cs

    class Cam:
        def __init__(self, name):
            self.frame = load(need(A1 / "kit2_drive" / "shots" / name))

        def read(self):
            return screen.read(self.frame)
    assert not cs.on_ticks(Cam("00385_right.png")) and cs.on_ticks(Cam("00503_left.png"))
    assert cs.on_ticks(Cam("00505_down.png")) and cs.tick(Cam("00504_enter.png")) is False
    assert cs.orange(Cam("00530_down.png"), cs.REGISTER_BOX) > 0.5


def test_custom_shoot_focus_area_named_by_order():
    # a hold's Focus Area list: the plain rows OCR can read must stand where the camera's order has
    # them; "Spot:" and "Tracking:" rows (an icon after the colon) take their names from it
    import customshoot_values as V
    order = ["Wide", "Zone", "Spot: L", "Custom 1", "Tracking: Wide", "Tracking: Spot: L"]
    read = ["o Wide", "Zone", "Spot: E", "Custom 1", "Tracking: E", "Tracking:"]
    assert V.name_by_order(read, order) == order
    assert V.name_by_order(read[:-1], order) is None                       # one row short
    assert V.name_by_order(["Zone", "Wide"] + read[2:], order) is None     # a readable row out of place


def test_custom_shoot_focus_area_counted_round(monkeypatch):
    # a hold's Focus Area list comes round: Regist Focus Area on top of the camera's 24 options
    # (2026-10-31). A popup of six rows; scrolling keeps the cursor on the fifth until the end.
    import types
    import customshoot_values as V
    rows = ["Regist Focus Area"] + [o if ":" not in o else o.split(":")[0] + ":" for o in V.ORDER]

    class Popup:
        def __init__(self, at):
            self.c, self.t = at, max(0, min(at - 2, len(rows) - 6))

        def read(self):
            return types.SimpleNamespace(kind="list", row=self.c - self.t)

        def refresh(self, why):
            pass

        def press(self, key):
            assert key == "down"
            self.c += 1
            if self.c == len(rows):
                self.c = self.t = 0
            elif self.c - self.t > 4 and self.t + 6 < len(rows):
                self.t += 1

    for at in (14, 0, 24, 3):
        cam = Popup(at)
        monkeypatch.setattr(V, "open_item", lambda *a: None)
        monkeypatch.setattr(V, "close_screen", lambda *a: None)
        monkeypatch.setattr(V, "option_now", lambda c: rows[c.c])
        monkeypatch.setattr(V.time, "sleep", lambda s: None)
        read, s0 = V.look_by_count(cam, None, None, None, 1, 0)
        assert read == rows and s0 == at
        names = V.order_names(read)
        assert names == ["Regist Focus Area"] + V.ORDER and names[s0] == names[at]
    assert V.order_names(rows[:-1]) is None


def test_custom_shoot_reads_a_row_ocr_leaves_empty_with_the_reader(monkeypatch):
    """option_now on the camera's frames of hold 3's Shutter Speed list (2026-11-08): on 235558 OCR reads the lit row,
    10"; on 235559 it reads the rows above and below (10", 6") and leaves the lit row empty, a short "8"" on the
    orange bar, where the look once ended the list at 29 options of about 56. The vision reader is asked then, and
    its reading is the row's; a row OCR reads asks it nothing. Skipped without runs/ or an OCR engine."""
    import types
    import customshoot_values as V
    from camkit import ocr
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    asked = []
    monkeypatch.setattr(V, "vlm_option", lambda cam: asked.append(cam.frame.path.name) or '8"')
    shots = A1 / "kit2_pass2" / "shots"
    for name, want, reader in (("235558_down.png", '10"', []), ("235559_down.png", '8"', ["235559_down.png"])):
        f = load(need(shots / name))
        f.path = shots / name
        cam = types.SimpleNamespace(frame=f, read=lambda f=f: screen.read(f))
        assert V.option_now(cam) == want and asked == reader, (name, asked)
        asked.clear()
    f = load(shots / "235559_down.png")
    f.path = shots / "235559_down.png"
    y = V.POP_Y0 + V.POP_DY * screen.read(f).row
    assert ocr.text_in(ocr.read([f.path])[f.path], (80, y - 24, 560, y + 24)) == "", "OCR leaves the lit row empty"


def test_custom_shoot_look_counts_a_row_no_reader_can_read(monkeypatch):
    """look: a row neither OCR nor the vision reader can read is no end of the list while the popup moved; it keeps
    its place (UNREAD with its place, which no reading matches), so the list is counted whole, the bottom is still
    found where the popup stops, and the Up pass still adds the options above the hold's own. Before, the first unread
    row ended the look with neither the bottom nor a wrap seen, and hold 3's Shutter Speed list was taken as whole at
    29 options (2026-11-08). The hold's own row unread at open keeps its place too, and a late frame that still shows
    the row before a press is read again, not taken for the bottom (review 4). A made-up list of speeds."""
    import types
    import customshoot_values as V
    rows = ['1/250', '1/200', '15"', '10"', '8"', '6"', '5"']

    class Popup:
        """A list that does not come round (Down and Up stop at its ends), or one that does (`rounds`, as hold 3's
        Shutter Speed list: 1/250 down to 1/32000, BULB, 30" and on to 1/200); `unread` rows read as nothing."""
        def __init__(self, at, unread, rounds=False, late=()):
            self.c, self.unread, self.rounds, self.frame = at, unread, rounds, types.SimpleNamespace(path=Path("f.png"))
            self.late, self.presses, self.stale = set(late), 0, None      # presses after which a late frame shows

        def read(self):
            return types.SimpleNamespace(kind="list", row=min(self.c, 4))

        def refresh(self, why):
            self.stale = None

        def press(self, key):
            before, self.presses = self.c, self.presses + 1
            if self.rounds:
                self.c = (self.c + (1 if key == "down" else -1)) % len(rows)
            else:
                self.c = min(self.c + 1, len(rows) - 1) if key == "down" else max(self.c - 1, 0)
            self.stale = before if self.presses in self.late else None

        def reading(self):
            at = self.c if self.stale is None else self.stale
            return None if at in self.unread else rows[at]

    monkeypatch.setattr(V, "open_item", lambda *a: None)
    monkeypatch.setattr(V, "close_screen", lambda *a: None)
    monkeypatch.setattr(V, "option_now", lambda c: c.reading())
    monkeypatch.setattr(V, "popup_image", lambda c: c.c)             # what moves when the cursor moves
    monkeypatch.setattr(V, "moved", lambda c, before: c.c != before)
    monkeypatch.setattr(V.time, "sleep", lambda s: None)
    for at, unread in ((2, {4}), (3, {1, 4}), (2, {6}), (2, set())):
        opts, start, wrapped = V.look(Popup(at, unread), None, None, None, 3, 0)
        assert len(opts) == len(rows) and (start, wrapped) == (at, False), (at, unread, opts)
        assert [o for i, o in enumerate(opts) if i not in unread] == [r for i, r in enumerate(rows) if i not in unread]
        assert all(V.unread(opts[i]) for i in unread) and len(set(opts)) == len(opts), opts
    # the list comes round: Down goes on past the unread row to the hold's own value again, a whole lap; the row
    # after the hold's own unread too leaves the check that the lap came round nothing to compare, and passes
    for unread in ({4}, {1}, {1, 4}, {0}):
        opts, start, wrapped = V.look(Popup(0, unread, rounds=True), None, None, None, 3, 0)
        assert (len(opts), start, wrapped) == (len(rows), 0, True), (unread, opts)
        assert [V.unread(o) for o in opts] == [i in unread for i in range(len(rows))] and opts[5] == '6"'
    # the hold's own row unread at open, in a list that does not come round: a stand-in, not None, in its place
    opts, start, wrapped = V.look(Popup(2, {2}), None, None, None, 3, 0)
    assert (len(opts), start, wrapped) == (len(rows), 2, False) and V.unread(opts[2]) and None not in opts, opts
    # a late frame after the third Down still shows the row before: read again, the list comes round whole; the same
    # on the way down and in the Up pass of a list that does not come round (presses 1-4 Down to the bottom, 5-7 Up
    # back to the hold's own, then the Up pass from 8: its second Up, press 9, is late)
    opts, start, wrapped = V.look(Popup(0, set(), rounds=True, late={3}), None, None, None, 3, 0)
    assert (opts, start, wrapped) == (rows, 0, True), opts
    opts, start, wrapped = V.look(Popup(3, set(), late={2, 9}), None, None, None, 3, 0)
    assert (opts, start, wrapped) == (rows, 3, False), opts


def test_short_first_word_kept():
    # "Av" and "Tv" are cleaned away as icons: the rows must still be told apart (2026-10-31)
    import prove_run as P
    assert not P.keeps_lead("Av Auto/Manual Switch", "Tv Auto/Manual Switch")
    assert P.keeps_lead("Tv Auto/Manual Switch", "Tv Auto/Manual Switch")
    assert P.keeps_lead("SAF Frame Move Amt", "AF Frame Move Amt")          # an icon glued in front
    assert P.keeps_lead("Focus Area", "Focus Area")                         # no short first word
    assert P.keeps_lead("QLo(E-Shutter)", "Lo (E-Shutter)")                 # the space dropped before "("
    assert not P.keeps_lead("QHi(E-Shutter)", "Lo (E-Shutter)")


def test_closest_row_takes_the_one_ending_with_the_label():
    # "uir Rear Dial R": the icon read as a word in front, which by ratio is no closer to the label
    # than "t7Rear Dial L" (Image Jump Setting, 2026-10-31)
    import prove_run as P
    texts = ["#Front dial", "t7Rear Dial L", "uir Rear Dial R"]
    assert P.closest_row(texts, "Rear Dial R") == 2
    assert P.closest_row(texts, "Rear Dial L") == 1
    assert P.closest_row(["Shoot Mode", "Drive Mode"], "Mode") is None            # two end with it
    assert P.closest_row(["Pre-Rec Long Mode"], "Mode") is None                   # more than an icon in front


def test_custom_shoot_option_match():
    """Popup options match through OCR slips, and an ambiguous label matches nothing."""
    import customshoot_values as cv
    opts = ["Off", "30 images/s", "20 images/s", "15 images/s", "10 images/s", "5 images/s"]
    assert cv.index_of(opts, "• 20 images/s".lstrip("• ")) == 2
    assert cv.index_of(opts, "1O images/s") == 4
    assert cv.index_of(["AF Lvl for Crossing", "AF Trk for Spd Chng"], "AF Lvlfor Crossing") == 0
    assert cv.index_of(["Spot: Large", "Spot: Small"], "Spot") is None
    # numbers match exactly: "1/4000" once passed for "1/400" and the wrong speed was registered
    assert not cv.same("1/4000", "1/400") and not cv.same("-0.3", "+0.3")
    assert cv.same("‡0.0", "±0.0") and cv.index_of(["±0.0", "-0.3"], "I0.0") == 0 and cv.same("‡0.0", "+0.0")
    assert not cv.same("1/10000", "1/1000")              # option_key turns these digits into letters
    assert cv.same("10.0", "‡0.0") and not cv.same("10", "0")
    # a decimal point counts: Aperture's list comes round F90, F1, F1.1, F1.3, and with the dots
    # dropped F1.1 and F1.3 passed for F11 and F13, so the look stopped at F72 (2026-10-31)
    assert not cv.same("F1.1", "F11") and cv.index_of(["F8", "F9", "F10", "F11", "F13"], "F1.1") is None
    # Drive Mode's speeds differ in their last word only (2026-10-31)
    drive = ["Single Shooting", "Cont. Shooting: Hi+", "Cont. Shooting: Hi", "Cont. Shooting: Mid",
             "Cont. Shooting: Lo", "Cont. Bracket", "Single Bracket", "WB bracket", "DRO Bracket"]
    assert not cv.same("Cont. Shooting: Hi+", "Cont. Shooting: Lo")
    assert not cv.same("Cont. Shooting: Hi", "Cont. Shooting: Hi+")
    assert not cv.same("Cont. Shooting: Mid", "Cont. Shooting: Lo")
    assert cv.index_of(drive, "Cont. Shooting: Hi+") == 1 and cv.index_of(drive, "o Cont. Shooting: Mid") == 3
    assert cv.same("WB Bracket", "WB bracket") and cv.same("DRO Brackel", "DRO Bracket")
    assert cv.same("Continuous AF", "Contlnuous AF") and cv.same("o Standard", "Standard")
    assert cv.clean_option("4 O") == "4" and cv.index_of(["1 (Locked on)", "2", "3(Standard)", "4"], "4 O") == 3
    assert cv.clean_option("Cont. Shooting: Lo") == "Cont. Shooting: Lo"
    # a look-alike letter beside a decimal point goes to the vision model ("F2.8" read "F2.o")
    assert [bool(cv.SHAKY.search(x)) for x in ("F2.o", "F1.l", "F2.8", "F20", "1/400")] == [True, True, False, False, False]
    assert cv.index_of(["F1", "F1.1", "F11"], "F1.1") == 1
    # the hold's own value carries a radio ring that OCR reads as a letter or a zero
    assert [cv.clean_option(x) for x in ("O -2.0", "02", "o 5 images/s", "• 30 images/s")] == \
        ["-2.0", "2", "5 images/s", "30 images/s"]
    # shutter times (hold 3's Shutter Speed, 2026-11-08): the seconds mark however a reader draws it, and the
    # times that differ by a decimal point or a digit kept apart
    assert cv.same("8''", '8"') and cv.same('8”', '8"') and cv.same("Bulb", "BULB")
    assert not cv.same('1.3"', '13"') and not cv.same("1/3", "1/30") and not cv.same('0.8"', '8"')
    assert not cv.same('3.2"', '32"') and not cv.same('1"', "1/1")


def test_custom_shoot_option_asks_the_reader_where_ocr_is_unsure(monkeypatch):
    """option_now: OCR's reading of the cursor row, the vision reader's where OCR leaves the row empty (8" on the
    orange bar, 2026-11-08) or reads a zero glued to the digits, the radio ring ("02") or a lost decimal point ("08""
    for 0.8", which cleaned would pass for 8"). With no answer from the reader, OCR's reading stands, and an empty row
    is None."""
    import types
    import customshoot_values as V
    cam = types.SimpleNamespace(read=lambda: types.SimpleNamespace(kind="list", row=4))
    for raw, says, want, asked in (('10"', '10"', '10"', False), ("", '8"', '8"', True), ('08"', '0.8"', '0.8"', True),
                                   ("02", "2", "2", True), ('08"', "", '8"', True), ("", "", None, True),
                                   ("O 1/250", "1/250", "1/250", False), ("F2.o", "F2.8", "F2.8", True)):
        calls = []
        monkeypatch.setattr(V, "lines", lambda c: [])
        monkeypatch.setattr(V.ocr, "text_in", lambda lines, box, raw=raw: raw)
        monkeypatch.setattr(V, "vlm_option", lambda c, says=says, calls=calls: calls.append(1) or says)
        assert (V.option_now(cam), bool(calls)) == (want, asked), (raw, says)


def test_page_model_vote_drops_an_icon_one_engine_kept():
    """Over the OSD one OCR engine reads a row's icon as "•" that the other drops: the clean one wins,
    and a VLM reading still comes first."""
    import page_model
    assert page_model.vote({"ocr": "• Movie Settings", "ocr2": "Movie Settings"})[0] == "Movie Settings"
    assert page_model.vote({"ocr2": "Movie Settings", "ocr": "• Movie Settings"})[0] == "Movie Settings"
    assert page_model.vote({"vllm": "Movie Settings", "ocr": "• Movie Settings"})[0] == "Movie Settings"


def test_a_torn_answer_in_the_cache_is_asked_again_and_kept_whole(tmp_path, monkeypatch):
    """The readers' cache: a file a crash (or a second thread keeping the same frame) left half written used to make
    every later read of that frame raise; now the frame is asked again and its answer replaces the file whole. A
    server's answer with no content (a reasoning model's "content": null) is no JSON, asked again, never a crash."""
    import io
    from camkit import vlm
    answers = [{"choices": [{"message": {"content": '{"title": "Drive Mode"}'}}]},
               {"choices": [{"message": {"content": None}}]}]
    monkeypatch.setattr(vlm.urllib.request, "urlopen",
                        lambda req, timeout: io.BytesIO(json.dumps(answers.pop(0)).encode()))
    monkeypatch.setattr(vlm, "CACHE", tmp_path)
    reader = vlm.make_reader({"name": "local", "url": "http://127.0.0.1:8000/v1", "model": "m"})
    key = vlm.cache_key(b"frame", "prompt", "m")
    (tmp_path / f"{key}.json").write_text('{"title": "Dri', encoding="utf-8")
    assert reader.ask(b"frame", "prompt") == {"title": "Drive Mode"}
    assert json.loads((tmp_path / f"{key}.json").read_text(encoding="utf-8")) == {"title": "Drive Mode"}
    assert reader.ask(b"frame", "prompt") == {"title": "Drive Mode"} and answers           # from the cache
    assert reader.ask(b"other", "prompt") == {"_unparsed": ""}
    assert not (tmp_path / f"{vlm.cache_key(b'other', 'prompt', 'm')}.json").exists()
    assert not list(tmp_path.glob("*.part"))


def test_a_cache_that_cannot_be_written_never_loses_the_answer(tmp_path, monkeypatch):
    """The cache is best effort: when the answer cannot be kept (a full disk; on Windows, replacing a file another
    reader thread has open), the answer still goes back, paid for as it may be, and no part file is left."""
    from camkit import vlm
    monkeypatch.setattr(vlm, "CACHE", tmp_path)

    def refused(self, target):
        raise PermissionError(13, "in use", str(target))
    monkeypatch.setattr(vlm.Path, "replace", refused)
    assert vlm.keep("k", {"title": "Drive Mode"}) == {"title": "Drive Mode"}
    assert not list(tmp_path.iterdir())
    monkeypatch.setattr(vlm, "CACHE", tmp_path / "a file" / "under a file")
    (tmp_path / "a file").write_text("x", encoding="utf-8")
    assert vlm.keep("k", {"title": "Drive Mode"}) == {"title": "Drive Mode"}


def test_a_role_given_for_the_process_is_the_one_playing(monkeypatch):
    from camkit import vlm
    readers = [{"name": "remote", "url": "http://192.0.2.1/v1", "model": "m"},
               {"name": "omlx", "url": "http://127.0.0.1:8000/v1", "model": "m"}]
    monkeypatch.setattr(vlm, "config", lambda: {"readers": readers})
    monkeypatch.setattr(vlm, "_STANDING_IN", {})
    assert vlm.playing("second")["name"] == "remote" and vlm.standing_in("second") is None
    vlm.assign_role("second", readers[1])
    assert vlm.standing_in("second") is readers[1]
    assert vlm.playing("second")["name"] == "omlx" and vlm._STANDING_IN["second"] is readers[1]
    assert vlm.reader_for("second").name == "omlx"


def test_the_batch_tools_that_build_their_own_readers_are_named():
    """camkit.vlm's docstring: every question a run asks about a frame goes through ask_role (a stand-in when the
    reader will not connect); the batch tools that build their own readers are listed there by name, all of them."""
    import re
    from camkit import vlm
    callers = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kit").rglob("*.py")
                     if "tests" not in p.parts and p.name != "vlm.py" and "__pycache__" not in p.parts
                     and re.search(r"\bmake_reader\(", p.read_text(encoding="utf-8")))
    assert callers == ["kit/help_reads.py", "kit/page_model.py", "kit/pass1_labels.py", "kit/tiebreak.py"]
    assert all(c in " ".join(vlm.__doc__.split()) for c in callers)


def test_a_role_given_to_no_reader_says_so(monkeypatch):
    from camkit import vlm
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [{"name": "omlx"}], "roles": {"second": "claude"}})
    with pytest.raises(ValueError, match="'claude', which no entry of \"readers\" names \\('omlx'\\)"):
        vlm.role("second")


def test_a_hosted_reader_sends_its_key_from_the_environment(tmp_path, monkeypatch):
    """An OpenAI-compatible reader with "api_key_env" sends the key that variable holds as a bearer token; one
    without it sends none, and one whose variable is unset refuses to ask (no network: urlopen is a stub)."""
    import io
    from camkit import vlm
    sent = []

    def urlopen(req, timeout):
        sent.append(req)
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"title": "Grid Line Display"}'}}]}).encode())
    monkeypatch.setattr(vlm.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(vlm, "CACHE", tmp_path)
    monkeypatch.setenv("CAMSET_TEST_READER_KEY", "sk-test")
    hosted = vlm.make_reader({"name": "hosted", "url": "https://example.invalid/v1/", "model": "m",
                              "api_key_env": "CAMSET_TEST_READER_KEY"})
    assert hosted.ask(b"frame 1", "prompt") == {"title": "Grid Line Display"}
    assert sent[-1].full_url == "https://example.invalid/v1/chat/completions"
    assert sent[-1].get_header("Authorization") == "Bearer sk-test"
    local = vlm.make_reader({"name": "local", "url": "http://127.0.0.1:8000/v1", "model": "m"})
    local.ask(b"frame 2", "prompt")
    assert not sent[-1].has_header("Authorization")
    monkeypatch.delenv("CAMSET_TEST_READER_KEY")
    with pytest.raises(RuntimeError, match="CAMSET_TEST_READER_KEY is not set"):
        hosted.ask(b"frame 3", "prompt")
    assert len(sent) == 2
    assert "sk-test" not in "".join(f.read_text() for f in tmp_path.glob("*.json"))


def test_wait_for_reads_a_black_feed_on_the_osd_and_gives_up_in_time(monkeypatch):
    """Auto Framing On blanks HDMI: a crawl waited 2.5 h for a shooting screen it could not see
    (2026-10-31). A black frame is read on the SDK's OSD, and with a limit the wait ends in an error."""
    import numpy as np
    from camkit import session as C

    class Frame:
        image = np.zeros((480, 640, 3), np.uint8)

    class Eyes:
        def grab(self, save=True):
            return Frame()

    class Link:
        def __init__(self, osd_kind):
            self.osd_kind = osd_kind

        def osd(self, path):
            return self.osd_kind

    monkeypatch.setattr(C, "load", lambda p: p)
    monkeypatch.setattr(C.screen, "read", lambda f: type("S", (), {"kind": f if isinstance(f, str) else "unknown"})())
    C.wait_for(Eyes(), ("shooting",), "a test", grace=0, link=Link("shooting"), limit=1)
    with pytest.raises(RuntimeError, match="gave up waiting"):
        C.wait_for(Eyes(), ("shooting",), "a test", grace=0, link=Link("menu"), limit=0.3)


def test_option_key_folds_cyrillic_lookalikes():
    """The stills map read "С.Temp./Filter" with a Cyrillic С; the Movie carousel reads it in Latin,
    and the White Balance grid stopped at "could not tell which preset" (2026-10-31)."""
    from prove_run import option_key
    assert option_key("С.Temp./Filter") == option_key("C.Temp./Filter")
    assert option_key("120р") == option_key("120p")
    assert option_key("C.Temp./Filter") != option_key("Custom 1")


def test_chain_runner_steps_stop_files_and_failures(tmp_path):
    # no camera: shell steps only, no end file (2026-10-31)
    import subprocess
    stop = tmp_path / "STEP_STOP"
    chain = tmp_path / "c.toml"
    chain.write_text(f'''name = "t"
[[step]]
title = "one"
run = ["sh", "-c", "echo one; echo two"]
log = "{tmp_path / 'one.log'}"
show = "one"
[[step]]
title = "waits for its stop file"
run = ["sh", "-c", "while [ ! -e {stop} ]; do sleep 0.2; done; echo stopped"]
limit = 1
stop = "{stop}"
[[step]]
title = "fails"
run = ["sh", "-c", "exit 3"]
''')
    py = sys.executable
    out = subprocess.run([py, str(ROOT / "kit" / "tools" / "chain.py"), str(chain), "--stop", str(tmp_path / "STOP_CHAIN")],
                         capture_output=True, text=True, timeout=60).stdout
    assert "   one" in out and "   two" not in out          # the log's matching lines only
    assert "asked it to stop" in out and not stop.exists()  # touched past its limit, removed after
    assert "step 3 exited 3" in out and "steps that failed: [3]" in out
    (tmp_path / "STOP_CHAIN").touch()
    r = subprocess.run([py, str(ROOT / "kit" / "tools" / "chain.py"), str(chain), "--stop", str(tmp_path / "STOP_CHAIN")],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode != 0 and "remove it" in r.stderr


# every option slip the a1 II produced: (reading, label, should match)
MATCH_TABLE = [
    ("1/4000", "1/400", False), ("1/10000", "1/1000", False), ("-0.3", "+0.3", False),
    ("F1.1", "F11", False), ("F1.3", "F13", False), ("F81", "F81", True),
    ("Cont. Shooting: Hi+", "Cont. Shooting: Lo", False), ("Cont. Shooting: Hi", "Cont. Shooting: Hi+", False),
    ("Cont. Shooting: Mid", "Cont. Shooting: Lo", False), ("Lo", "10", False), ("10", "Lo", False),
    ("O", "0", False),
    ("С.Temp./Filter", "C.Temp./Filter", True), ("120р", "120p", True),
    ("o Standard", "Standard", True), ("4 O", "4", True), ("O ISO 50", "ISO 50", True), ("02", "2", True),
    ("‡0.0", "±0.0", True), ("I0.0", "±0.0", True), ("10.0", "±0.0", True), ("+0.0", "±0.0", True),
    ("Contlnuous AF", "Continuous AF", True), ("WB bracket", "WB Bracket", True),
    ("DRO Brackel", "DRO Bracket", True), ("1 Sec.", "1 Sec", True), ("l(Locked on)", "1(Locked on)", True),
    ("Lo (E-Shutter)", "Hi(E-Shutter)", False), ("Mid (E-Shutter)", "Hi(E-Shutter)", False),
    ("Hi (E-Shutter)", "Hi+(E-Shutter)", False), ("Mld(E-Shutter)", "Mid (E-Shutter)", True),
]


@pytest.mark.parametrize("reading,label,want", MATCH_TABLE)
def test_option_match_table(reading, label, want):
    from camkit import match
    assert match.same(reading, label) is want, (reading, label)


def test_option_index_of_picks_one_or_none():
    from camkit import match
    drive = ["Single Shooting", "Cont. Shooting: Hi+", "Cont. Shooting: Hi", "Cont. Shooting: Mid",
             "Cont. Shooting: Lo", "Cont. Bracket", "Single Bracket", "WB bracket", "DRO Bracket"]
    assert match.index_of(drive, "Cont. Shooting: Hi+") == 1 and match.index_of(drive, "o Cont. Shooting: Mid") == 3
    assert match.index_of(["F8", "F9", "F10", "F11", "F13"], "F1.1") is None
    assert match.index_of(["1(Locked on)", "2", "3(Standard)", "4", "5(Responsive)"], "4 O") == 3
    assert match.index_of(["Lo", "10"], "10") == 1 and match.index_of(["Lo", "10"], "Lo") == 0


def test_bracket_fields_read_and_label():
    import bracket_run as B
    assert [B.step_of(t) for t in ("1.0EV", "1.OEV", "O.7EV", "O.ZEV", "1.SEV", "0,3EV", "3.0 EV", "", "5 Images")] == \
        [1.0, 1.0, 0.7, 0.7, 1.5, 0.3, 3.0, None, None]
    # Down lowers both fields: the images run 9, 7, 5, 3, 2 (-), 2 (+)
    order = [(9, ""), (7, ""), (5, ""), (3, ""), (2, "-"), (2, "+")]
    assert sorted(order, key=lambda v: B.rank("images", v), reverse=True) == order
    assert [B.images_of(t) for t in ("5 lmages", "9 Images", "2 Images +", "2 Images -", "1.0EV")] == \
        [(5, ""), (9, ""), (2, "+"), (2, "-"), None]
    assert B.label(0.3, (2, "+")) == "0.3 EV 2 Img. +" and B.label(1.0, (5, "")) == "1.0 EV 5 Img."
    # the schema's labels for the live record are in this form
    import json
    s = {x["key"]: x for x in json.loads(Path(DEFINITION).read_text(encoding="utf-8"))["settings"]}
    assert "1.0 EV 5 Img." in dict((v, l) for v, l in s["global:0x04c6"]["values"]).values()


def test_bracket_field_search_on_a_simulated_strip(monkeypatch):
    import bracket_run as B
    steps = [0.3, 0.5, 0.7, 1.0, 1.3, 1.5, 1.7, 2.0, 2.3, 2.5, 2.7, 3.0]

    class Cam:
        def __init__(self, at, misread=()):
            self.i, self.presses, self.misread = steps.index(at), [], set(misread)
            self.frame = type("F", (), {"path": Path("x.png")})()

        def press(self, key):
            self.presses.append(key)
            self.i = max(0, self.i - 1) if key == "down" else min(len(steps) - 1, self.i + 1)

        def refresh(self, why):
            self.misread.discard(steps[self.i])         # the late frame reads it

    def fields(cam):
        v = steps[cam.i]
        return {"step": "O.ZEV" if v in cam.misread else f"{v:.1f}EV", "images": "3 Images", "next": ""}

    monkeypatch.setattr(B, "fields", fields)
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    cam = Cam(0.5)
    B.set_field(cam, "step", 0.7, B.step_of)
    assert cam.presses == ["up"]                        # 0.7 is above 0.5: Up, not Down first
    cam = Cam(1.0)
    B.set_field(cam, "step", 0.5, B.step_of)
    assert cam.presses == ["down", "down"]
    cam = Cam(0.5, misread={0.7})
    B.set_field(cam, "step", 0.7, B.step_of)             # "O.ZEV" is read again, then 0.7
    assert cam.presses == ["up"]
    with pytest.raises(B.Failed):
        B.set_field(Cam(0.5), "step", 4.0, B.step_of)    # not in the list: both ways, then stop


def test_sdk_set_takes_exposure_properties_only():
    import subprocess
    for bad in ("DriveMode=1", "FocusArea=2", "ShutterSpeed"):
        r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "sdk_set.py"), bad], capture_output=True, text=True, timeout=30)
        assert r.returncode != 0 and "NAME=VALUE" in r.stderr


def test_sdk_set_says_what_the_camera_refused_and_what_to_do(monkeypatch, capsys):
    """2026-11-08: the camera answered "not writable now" (the mode dial on A) and the owner saw a traceback. The set's
    line is printed with the camera's answer, then what to do, and the exit is 1; a set that takes still prints ok."""
    import sdk_set
    from camkit.link import LinkError

    class FakeLink:
        refuse = True

        def __init__(self, run):
            self.sets = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, name):
            return {"ok": True, "current": 65786}

        def set(self, name, value):
            self.sets.append((name, value))
            if FakeLink.refuse:
                raise LinkError(f"set {name} {value}: not writable now")
            return {"ok": True, "current": value}
    monkeypatch.setattr(sdk_set, "Link", FakeLink)
    monkeypatch.setattr(sdk_set, "Run", lambda name: name)
    monkeypatch.setattr(sys, "argv", ["sdk_set.py", "ShutterSpeed=66036", "FNumber=800"])
    with pytest.raises(SystemExit) as stop:
        sdk_set.main()
    out = capsys.readouterr().out
    assert stop.value.code == 1
    assert "ShutterSpeed: 65786 -> 66036 not set (set ShutterSpeed 66036: not writable now)" in out
    assert "on the mode dial's A, P or Auto the camera sets ShutterSpeed itself: turn the dial to S or M" in out
    assert "FNumber" not in out and "Traceback" not in out             # it stops at the first refusal
    FakeLink.refuse = False
    monkeypatch.setattr(sys, "argv", ["sdk_set.py", "FNumber=800"])
    sdk_set.main()
    assert capsys.readouterr().out == "FNumber: 65786 -> 800 (ok)\n"


@pytest.mark.parametrize("name,advice", [
    ("FNumber", "on the mode dial's S, P or Auto the camera sets FNumber itself: turn the dial to A or M"),
    ("IsoSensitivity", "the camera does not take IsoSensitivity in its present mode: check the mode dial and the "
                       "settings that set IsoSensitivity automatically, then try again"),
])
def test_sdk_set_gives_each_property_its_own_advice(monkeypatch, capsys, name, advice):
    """The aperture's advice names the dial positions where the camera sets it; any other property gets the general
    words, which claim nothing about it. Exit 1, no traceback."""
    import sdk_set
    from camkit.link import LinkError

    class Refusing:
        def __init__(self, run):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, name):
            return {"ok": True, "current": 1}

        def set(self, name, value):
            raise LinkError(f"set {name} {value}: not writable now")
    monkeypatch.setattr(sdk_set, "Link", Refusing)
    monkeypatch.setattr(sdk_set, "Run", lambda name: name)
    monkeypatch.setattr(sys, "argv", ["sdk_set.py", f"{name}=400"])
    with pytest.raises(SystemExit) as stop:
        sdk_set.main()
    out = capsys.readouterr().out
    assert stop.value.code == 1 and out == f"{name}: 1 -> 400 not set (set {name} 400: not writable now)\n{advice}\n"


@pytest.mark.parametrize("script,args", [
    ("drive.py", ["--path", "Format", "--allow", "Format"]),
    ("drive.py", ["--path", "Delete Slot1/2", "--allow", "Delete Slot1/2", "--press", "right"]),
    ("tools/card_actions.py", ["run", "Format", "--press", "right"]),
])
def test_cards_are_never_formatted_or_deleted(script, args):
    """2026-11-01 (user): "Please don't delete the cards." Refused before any connection."""
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "kit" / script), *args], capture_output=True, text=True, timeout=30)
    assert r.returncode != 0 and ("formatted or deleted" in r.stderr or "not a card action" in r.stderr)


# ---------------------------------------------------------------- synthetic screens (K-25)
# The safety checks below read frames; made-up frames with the camera's colours stand in when the a1 II's are not on
# disk, so the checks run on every clone (the a1 II's own frames are checked too where they are).

ORANGE = (235, 90, 20)                  # the cursor's orange (screen._planes: r > 150, 30 < g < 140, b < 70)


def frame_with(bars=(), glyph=None):
    """A 640 x 480 dark screen with orange bars [(x0, y0, x1, y1)] and a footer glyph (camkit/glyphs/<name>.png)
    pasted into the footer band."""
    import numpy as np
    from PIL import Image
    a = np.full((480, 640, 3), 24, np.uint8)
    for x0, y0, x1, y1 in bars:
        a[y0:y1, x0:x1] = ORANGE
    if glyph:
        g = np.asarray(Image.open(ROOT / "kit" / "camkit" / "glyphs" / f"{glyph}.png").convert("L"), np.uint8)
        a[430:430 + g.shape[0], 520:520 + g.shape[1]] = g[..., None]
    return a


def lines_at(*items):
    """OCR's lines as camkit.ocr reads them: (text, x0, y0, x1, y1) each."""
    from camkit import ocr
    return [ocr.Line(text=t, conf=0.99, x=x0, y=y0, w=x1 - x0, h=y1 - y0) for t, x0, y0, x1, y1 in items]


def test_enter_never_on_initialize(monkeypatch, tmp_path):
    """drive.py reads the lit button before Enter; Initialize and Reset Network Set. are never pressed. Setting Reset's
    two buttons: the lit one is read inside the orange cursor only."""
    import drive
    from camkit import live
    assert drive.NEVER_ENTER.search("Initialize") and drive.NEVER_ENTER.search("Reset Network Set.")
    assert not drive.NEVER_ENTER.search("Camera Settings Reset") and not drive.NEVER_ENTER.search("OK")
    texts = lines_at(("Camera Settings Reset", 120, 205, 520, 235), ("Initialize", 120, 265, 520, 295))
    monkeypatch.setattr(live.ocr, "read", lambda paths, eng=None: {p: texts for p in paths})
    f = tmp_path / "00118_right.png"
    upper, lower = frame_with([(100, 200, 540, 240)]), frame_with([(100, 260, 540, 300)])
    assert drive.highlighted(upper, f) == "Camera Settings Reset"
    assert drive.highlighted(lower, f) == "Initialize"
    assert drive.highlighted(frame_with(), f) == ""                   # nothing lit
    screen_text = "Setting Reset Camera Settings Reset Initialize"
    assert drive.press_refused("enter", drive.highlighted(lower, f), screen_text, "dialog", confirm=True)
    assert drive.press_refused("enter", "", screen_text, "dialog", confirm=True)
    real = A1 / "kit2_csr" / "shots" / "00118_right.png"            # the a1 II's own frame, where it is on disk
    if real.exists():
        monkeypatch.undo()
        from camkit.frames import load
        assert drive.highlighted(load(real).image, real) == "Camera Settings Reset"


def test_cursor_row_on_dialog_buttons():
    """key@y finds a dialog's narrow button as well as a menu row's bar."""
    import drive
    button = frame_with([(330, 352, 540, 382)])                     # Enter / Cancel, Cancel lit: a third of the width
    row = frame_with([(140, 212, 560, 252)])                        # a menu row's bar: two thirds of it
    for a, at, not_at in ((button, 367, (301, 150)), (row, 232, (72, 127, 180))):
        assert drive.lit_at(a, at) and not any(drive.lit_at(a, y) for y in not_at)
    f = A1 / "kit2_csr" / "shots" / "00131_enter.png"
    g = A1 / "kit2_pass2" / "shots" / "178936_down.png"
    if f.exists() and g.exists():                                   # the a1 II's own frames, where they are on disk
        from camkit.frames import load
        a, b = load(f).image, load(g).image
        assert drive.lit_at(a, 367) and not drive.lit_at(a, 301) and not drive.lit_at(a, 150)
        assert drive.lit_at(b, 232) and not any(drive.lit_at(b, y) for y in (72, 127, 180))


def test_short_first_word_rows():
    """Cont. Shooting Speed's rows on screen: only the Lo row is "Lo (E-Shutter)"."""
    import prove_run as P
    from page_model import same_text
    readings = ["Hi+(E-Shutter)", "Hi(E-Shutter)", "1Mid(E-Shutter)", "9Lo(E-Shutter)"]
    for label, want in (("Lo (E-Shutter)", 3), ("Mid (E-Shutter)", 2), ("Hi (E-Shutter)", 1), ("Hi+ (E-Shutter)", 0)):
        hits = [i for i, t in enumerate(readings) if same_text(t, P.glued(label)) and P.keeps_lead(t, label)]
        assert hits == [want], (label, hits)
        assert P.closest_row(readings, P.glued(label)) == want, label


def test_upload_refuses_files_that_change_the_profile_in_use(own_runs):
    """2026-11-01: a test file that rewrote PP11 while Movie had it in use boot-looped the camera. A made-up run in the
    test's own runs: the owner's file and a quiet start file, both the camera's downloads (in the manifest), and a file
    with PP11's parameter rewritten, which no camera wrote: the in-use check names it, and upload_check refuses it
    before any connection. The records that hold the profile in use are the camera file's picture_profile_in_use."""
    import subprocess
    import upload_check as U
    from camkit import camset, provenance
    a1 = paths.EXAMPLE                                             # the ILCE-1M2's camera file and definition
    assert U.in_use_records(a1) == {"model": "ILCE-1M2", "ids": (0x0053, 0x0E12, 0x0E14)}
    cs = camset.read(SAMPLE)
    pp = sorted(U.pp_param_ids(a1))[0]                             # a profile parameter: one element per profile
    rec = cs.get(0, pp)

    def element(raw, i, v):                                       # element i of the record set to v
        out = bytearray(raw)
        out[i * rec.size:(i + 1) * rec.size] = v.to_bytes(rec.size, "little", signed=True)
        return bytes(out)
    in_use = {(0, rid): bytes([11]) for rid in U.in_use_records(a1)["ids"]}     # PP11 in use, stills and movie
    run = Run("kit2_pass2", root=own_runs / "TEST-CAM_fw9.99")
    owner_f, quiet_f, scrambled_f = run.dat / "00001_owner.DAT", run.dat / "00002_quiet.DAT", run.dir / "start_pp11.DAT"
    owner_f.write_bytes(camset.with_values(cs, in_use))
    quiet_f.write_bytes(camset.with_values(cs, {**in_use, (0, pp): element(rec.raw, 0, 5)}))           # PP1's: not in use
    scrambled_f.write_bytes(camset.with_values(cs, {**in_use, (0, pp): element(rec.raw, 10, 5)}))      # PP11's
    for f in (owner_f, quiet_f):
        provenance.record(f, run.root, run=run.dir.name, camera="ILCE-1M2")
    owner, quiet, scrambled = (camset.read(f) for f in (owner_f, quiet_f, scrambled_f))
    assert U.in_use_changes(scrambled, owner, a1) == [(pp, 10)]   # PP11's parameter changed: named
    assert U.in_use_changes(quiet, owner, a1) == []               # the quiet start file passes
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "upload_check.py"), str(scrambled_f)],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode != 0 and "not a camera download" in r.stderr
    d = A1 / "kit2_pass2"                                         # the a1 II's own files, where they are on disk
    files = [d / "dat" / "owner_stills_2026-10-31.DAT", d / "start_movie_ppcopies_2026-11-01.DAT",
             d / "start_reg_stills_2026-10-30.DAT"]
    if all(f.exists() for f in files):
        owner, scrambled, quiet = (camset.read(f) for f in files)
        assert U.in_use_changes(scrambled, owner, a1) and not U.in_use_changes(quiet, owner, a1)


def test_upload_check_says_when_the_camera_file_names_no_profile_records(own_runs, monkeypatch, tmp_path, capsys):
    """picture_profile_in_use is optional: a camera file without it (or a camera without a camera file) has no
    in-use check, and upload_check --check-in-use says so in one line before it goes on to the upload."""
    import conftest
    import upload_check as U
    from camkit import camset, definitions, provenance
    assert U.in_use_records() is None                              # the tests' made-up camera has no camera file
    facts = json.loads(definitions.camera_file(paths.EXAMPLE).read_text(encoding="utf-8"))
    facts.pop("picture_profile_in_use")
    bare = tmp_path / "camera_TEST-CAM_fw9.99.json"
    bare.write_text(json.dumps(facts), encoding="utf-8")
    monkeypatch.setattr(definitions, "camera_file", lambda camera: bare)
    cs = camset.read(SAMPLE)
    assert U.in_use_records() is None and U.in_use_changes(cs, cs) is None
    run = Run("kit2_pass2", root=own_runs / conftest.TEST_CAMERA)
    ref, f = run.dat / "00001_owner.DAT", run.dat / "00002_quiet.DAT"
    for x in (ref, f):
        x.write_bytes(SAMPLE.read_bytes())
        provenance.record(x, run.root, run=run.dir.name)

    class NoCamera:                                                # the upload is past what this test checks
        def __init__(self, run):
            raise RuntimeError("no camera in this test")
    monkeypatch.setattr(U, "Link", NoCamera)
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(f), "--check-in-use", "--ref", str(ref)])
    with pytest.raises(RuntimeError, match="no camera in this test"):
        U.main()
    out = capsys.readouterr().out.splitlines()
    assert out == [f"note: the Picture Profile in-use check is skipped: {conftest.TEST_CAMERA}'s camera file names no "
                   f"picture_profile_in_use (data/<model>_fw<fw>/camera_<model>_fw<fw>.json)"]


def test_upload_check_diff_names_the_elements_of_an_array_that_moved(tmp_path, monkeypatch, capsys):
    """--diff REF TAG: an array record's changed elements are listed by index (its before and after are one record's,
    of one length: zip(strict=True))."""
    import upload_check as U
    cs = camset.read(SAMPLE)
    rec = next(r for r in cs.sections[0].values() if r.count > 2 and r.size == 1)
    raw = bytearray(rec.raw)
    raw[1] = (raw[1] + 1) % 128
    got = tmp_path / "00002_now.DAT"                  # the camera's download as the fake link hands it over
    got.write_bytes(camset.with_values(cs, {(0, rec.id): bytes(raw)}))

    class FakeLink:
        def __init__(self, run):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            return got
    monkeypatch.setattr(U, "Link", FakeLink)
    monkeypatch.setattr(U, "setting_names", lambda: {})
    monkeypatch.setattr(sys, "argv", ["upload_check.py", "--diff", str(SAMPLE), "now"])
    U.main()
    out = capsys.readouterr().out
    assert "00002_now.DAT 1 records differ from" in out
    assert f"global:0x{rec.id:04x} ? [1 elements] [1] {rec.values()[1]}->{camset.parse(got.read_bytes()).get(0, rec.id).values()[1]}" in out


def test_only_camera_downloads_are_uploaded(tmp_path):
    """2026-11-01 (owner): settings are changed on the camera and watched, never written into a file."""
    import subprocess
    f = tmp_path / "start_by_hand.DAT"
    f.write_bytes(b"not sent")
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "upload_check.py"), str(f)], capture_output=True, text=True,
                       timeout=30)
    assert r.returncode != 0 and "not a camera download" in r.stderr


def test_c4_only_as_help_on_screens_that_draw_it():
    # C4 (trash) opens the In-Camera Guide where the footer draws the help button (decision 7)
    import drive
    from camkit.frames import load
    with pytest.raises(safety.Refused):
        safety.check_input("c4")
    safety.check_input("c4", {"c4"})
    for k in ("c1", "c3", "c5", "c7"):
        with pytest.raises(safety.Refused):
            safety.check_input(k, {k})
    # made-up screens: a menu whose footer draws the help button (the camera's own glyph), and a bare one
    for glyph in ("help_key", "help_only"):
        assert drive.help_refused("menu", frame_with(glyph=glyph)) == ""
    bare = frame_with()
    assert drive.help_refused("menu", bare) == "the footer shows no help button"
    assert drive.help_refused("shooting", frame_with(glyph="help_key"))
    assert drive.help_refused("tiles", frame_with(glyph="help_key"))
    m, sh = (A1 / "kit2_page_scan" / "shots" / n for n in ("00003_down.png", "00001_start.png"))
    if not (m.exists() and sh.exists()):                          # the a1 II's own frames, where they are on disk
        return
    menu, shooting = load(m), load(sh)
    assert drive.help_refused("menu", menu.image) == ""
    assert drive.help_refused("shooting", shooting.image)
    assert drive.help_refused("tiles", menu.image)
    assert drive.help_refused("menu", shooting.image)
    # number fields: only where the footer draws it (ISO Range Limit does, BULB's Exposure Time does not)
    iso, bulb = (A1 / "kit2_pass2" / "shots" / n for n in ("23202_down.png", "12986_up.png"))
    if iso.exists() and bulb.exists():
        assert drive.help_refused("fields", load(iso).image) == ""
        assert drive.help_refused("fields", load(bulb).image) == "the footer shows no help button"


def test_a_carousel_previewing_a_grey_look_is_no_notice():
    # Creative Look's carousel on SH (Soft Highkey) in Movie: the preview greys live view (2026-11-02)
    from camkit.frames import load
    sh, panel, notice = (A1 / n for n in ("kit2_pass2/shots/207586_up.png", "kit2_pass2/shots/207744_down.png",
                                                      "kit2_drive/shots/00265_right.png"))
    if not (sh.exists() and panel.exists() and notice.exists()):
        pytest.skip("frames not on disk")
    assert screen.read(load(sh)).kind == "dialog"
    assert screen.read(load(panel)).kind == "look"            # SH's own parameter panel
    assert screen.read(load(notice)).kind == "notice"


def test_c4_as_set_only_on_focus_areas_custom_boxes():
    # the owner, 2026-11-02: C4 opens a Custom box's size editor there; it deletes in Playback
    import drive
    assert drive.c4set_refused("dialog", "Focus Area Custom 1 SET C1 C2 C3 MENU Cancel OK") == ""
    assert drive.c4set_refused("dialog", "Focus Area Zone MENU Cancel OK")
    assert drive.c4set_refused("shooting", "Focus Area Custom 1")
    assert drive.c4set_refused("unknown", "Delete this image? Cancel OK")
    assert drive.c4set_refused("unknown", "Custom 1 Reset MENU Cancel OK") == ""      # the size editor's Reset


def test_help_walk_reads_the_lit_row_through_ocr_slips():
    import help_run
    assert help_run.on_label("•m Initill Focus Mag. x1.0", "Initial Focus Mag.")
    assert help_run.on_label("S Grid Line Display Off", "Grid Line Display")
    assert not help_run.on_label("S Grid Line Type Rule of 3rds Grid", "Initial Focus Mag.")


def test_help_goes_to_the_setting_and_its_options_by_value(tmp_path, monkeypatch):
    # the In-Camera Guide read by kit/help_run.py (a row) and prove_run --help-text (its options)
    import schema_update as U
    monkeypatch.setattr(U, "HELP", tmp_path)
    (tmp_path / "help.jsonl").write_text(json.dumps(
        {"context": "Movie mode", "breadcrumb": "Shooting > Shooting Display", "label": "Grid Line Display",
         "text": "Shows or hides the framing guide lines on screen. This function is currently disabled."}) + "\n")
    (tmp_path / "option_help.jsonl").write_text("".join(json.dumps(
        {"path": ["Grid Line Display"], "index": i, "label": lab, "text": t, "context": "Movie mode"}) + "\n"
        for i, (lab, t) in enumerate([("Off", "Hides the framing guide lines."),
                                      ("On", "Draws the framing guide lines on the monitor.")])))
    doc = {"settings": [{"key": "global:0x0068", "name": "Grid Line Display",     # an earlier OCR slip, replaced
                         "option_help": [[0, "Hides the framing guide 1ines."]],
                         "proved": {"menu": ["Grid Line Display [Movie mode]"]}}]}
    report = [{"row": "Grid Line Display [Movie mode]",
               "records": {"global:0x0068": {"verdict": "agrees", "proved": {"Off": 0, "On": 1}}}}]
    assert U.attach_help(doc, report) == (1, 1)
    s = doc["settings"][0]
    assert s["help"] == "Shows or hides the framing guide lines on screen."      # read greyed: no state in the help
    assert s["option_help"] == [[0, "Hides the framing guide lines."], [1, "Draws the framing guide lines on the monitor."]]


def test_a_rewrite_keeps_help_that_is_still_the_guide_of_a_row_the_record_was_proved_through(tmp_path, monkeypatch):
    """2026-11-11: an S&Q exposure-mode record's help was its S&Q row's guide, from proofs that row's later proofs (made
    in another state) replaced in the report; its "proved" menu lost the row, and the rewrite gave it the next row's
    general guide. A setting's help that is still word for word the guide of a row one of its counted proofs went
    through is kept; one that is no row's guide any more (a reading corrected since) is replaced as before. Made-up
    texts."""
    import schema_update as U
    monkeypatch.setattr(U, "HELP", tmp_path)
    (tmp_path / "help.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
        {"context": "Movie mode", "label": "Fast Shoot Mode", "text": "Picks the exposure for fast shooting."},
        {"context": "Stills mode", "label": "Shoot Mode", "text": "Picks how the camera shoots."}]))
    menu = ["Mode dial [Fast mode]", "Shoot Mode / Fast [Mode Dial Control Set = Set with Menu]"]
    doc = {"settings": [{"key": "global:0x13e2", "name": "Exposure mode (fast)", "proved": {"menu": list(menu)},
                         "help": "Picks the exposure for fast shooting."},
                        {"key": "global:0x13e9", "name": "Exposure mode (other)", "proved": {"menu": list(menu)},
                         "help": "Picks the exposure for fast shootlng."}]}           # an old OCR slip
    old = {"path": ["Fast Shoot Mode"], "kind": "list", "context": "Fast mode", "index": 0, "label": "A",
           "changes": [{"key": "global:0x13e2", "before": 0, "after": 1}]}
    U.attach_help(doc, [], [old])
    fast, other = doc["settings"]
    assert fast["help"] == "Picks the exposure for fast shooting.", "its row's guide still: kept"
    assert other["help"] == "Picks how the camera shoots.", "no row's guide: the first menu row's, as before"
    doc["settings"][0]["help"] = "Picks the exposure for fast shooting."
    U.attach_help(doc, [], [])
    assert doc["settings"][0]["help"] == "Picks how the camera shoots.", "no proof through the row: as before"


def test_option_help_matches_labels_read_with_lookalikes_or_icon_text(tmp_path, monkeypatch):
    # proofs read "120р" (a Cyrillic р) and "XAVCS XAVC S HD HD" (the icon's text too), 2026-11-02
    import schema_update as U
    monkeypatch.setattr(U, "HELP", tmp_path)
    (tmp_path / "option_help.jsonl").write_text("".join(json.dumps(
        {"path": p, "index": i, "label": lab, "text": t, "context": "Movie mode"}) + "\n" for p, i, lab, t in [
        (["Rec Frame Rate"], 3, "120p", "Captures video at 120 progressive frames per second."),
        (["File Format"], 0, "XAVC S HD", "Uses the standard HD container."), (["File Format"], 1, "XAVC S-I HD", "Uses the intra-frame HD container."),
        (["File Format"], 2, "HD", "too short to stand for a label"),
        (["Focus Area"], 0, "Wide", "Covers the entire frame area.")]))
    doc = {"settings": [{"key": "global:0x0206", "name": "Rec Frame Rate"}, {"key": "global:0x0200", "name": "File Format"},
                        {"key": "global:0x16ae", "name": "HD flag"}, {"key": "global:0x0f46", "name": "Focus Area"}]}
    report = [{"row": "Rec Frame Rate [Movie mode]", "records": {"global:0x0206": {"verdict": "agrees", "proved": {"120р": 5}}}},
              {"row": "File Format [Movie mode]", "records": {
                  "global:0x0200": {"verdict": "agrees", "proved": {"XAVCS XAVC S HD HD": 8, "XAVCS XAVC S-I HD HD": 10,
                                                                    "XAVC S 4K": 7}},
                  # two options with different help stored as one value: neither text stands for it
                  "global:0x16ae": {"verdict": "agrees", "proved": {"XAVCS XAVC S HD HD": 1, "XAVCS XAVC S-I HD HD": 1}}}},
              {"row": "Focus Area [Movie mode]", "records": {"global:0x0f46": {"verdict": "agrees", "proved": {
                  "Tracking: Wide": 12, "Wide": 0}}}}]
    U.attach_help(doc, report)
    rate, fmt, flag, area = doc["settings"]
    assert rate["option_help"] == [[5, "Captures video at 120 progressive frames per second."]]
    assert fmt["option_help"] == [[8, "Uses the standard HD container."], [10, "Uses the intra-frame HD container."]]
    assert "option_help" not in flag
    assert area["option_help"] == [[0, "Covers the entire frame area."]]   # "Tracking: Wide" is not Wide


def test_a_number_fields_guide_follows_the_rows_help(tmp_path, monkeypatch):
    # ISO Range Limit: the row's guide, then each field's own (2026-11-02); a rerun adds nothing
    import schema_update as U
    monkeypatch.setattr(U, "HELP", tmp_path)
    (tmp_path / "help.jsonl").write_text(json.dumps(
        {"context": "Stills mode", "label": "ISO Range Limit", "text": "Chooses the allowed bounds for manual ISO selection."}) + "\n")
    (tmp_path / "field_help.jsonl").write_text(json.dumps(
        {"context": "Stills mode", "path": ["ISO Range Limit"], "field": 1, "label": "Maximum",
         "text": "Picks the upper bound.", "frames": ["fields_00027_c4.png"]}) + "\n")
    doc = {"settings": [{"key": "global:0x0b63", "name": "ISO Range Limit (upper)",
                         "proved": {"menu": ["ISO Range Limit [field 1]"]}},
                        {"key": "global:0x0b65", "name": "ISO Range Limit",
                         "proved": {"menu": ["ISO Range Limit [field 0]"]}}]}
    report = [{"row": "ISO Range Limit [field 1]", "records": {"global:0x0b63": {"verdict": "agrees", "proved": {}}}},
              {"row": "ISO Range Limit [field 0]", "records": {"global:0x0b65": {"verdict": "agrees", "proved": {}}}}]
    for _ in range(2):
        U.attach_help(doc, report)
    upper, lower = doc["settings"]
    assert upper["help"] == "Chooses the allowed bounds for manual ISO selection. Maximum: Picks the upper bound."
    assert lower["help"] == "Chooses the allowed bounds for manual ISO selection."     # no guide read for field 0 here


def test_help_extras_counts_fields_and_reads_the_family():
    # ISO Range Limit's drive (runs/kit2_help_fields): Right opens the fields, the next Right moves on
    import help_extras as X
    screens = [{"after": a, "kind": k, "frame": f} for a, k, f in [
        ("right", "fields", "1"), ("help:minimum", "guide", "2"), ("enter:^(?!x)", "fields", "3"),
        ("right:minimum", "fields", "4"), ("help:maximum", "guide", "5"), ("left", "fields", "6"),
        ("help", "guide", "7")]]
    assert [(k, s["frame"]) for k, s in X.field_guides(screens)] == [(0, "2"), (1, "5"), (0, "7")]
    assert X.field_guides([{"after": "help", "kind": "guide", "frame": "1"}]) == []     # not in fields
    assert X.family("Example description for S&Q < Motion mode.") == "S&Q"
    assert X.family("Example description for Time- lapse mode.") == "Time-lapse"
    assert X.family("Example description for still image shooting.") == "Stills"
    assert X.family("Example description for video recording.") == "Movie"


def test_help_extras_tells_a_rows_guide_from_its_options():
    # the Screen Reader drives (runs/kit2_help_sr, 2026-11-02): the row's guide, then each option's
    import help_extras as X
    screens = [{"after": a, "kind": k, "frame": f} for a, k, f in [
        ("help", "helppop", "1"), ("down", "helppop", "2"), ("enter:in-camera guide", "guide", "3"),
        ("down", "guide", "4"), ("enter:^x", "submenu", "5"), ("right", "list", "6"), ("help", "guide", "7"),
        ("enter:^off", "list", "8"), ("up", "list", "9"), ("help", "guide", "10")]]
    assert [(o, s["frame"]) for o, s in X.guide_screens(screens)] == [(False, "3"), (True, "7"), (True, "10")]


def test_shoot_mode_descriptions_go_on_each_familys_mode_record(tmp_path, monkeypatch):
    # the carousel's own text per mode (2026-11-02): by the record's labels, letters or full names
    import schema_update as U
    monkeypatch.setattr(U, "HELP", tmp_path)
    (tmp_path / "carousel_help.jsonl").write_text("".join(json.dumps(
        {"family": f, "label": lab, "text": t, "frames": [fr]}) + "\n" for f, lab, t, fr in [
        ("Movie", "Manual Exposure", "Lets you pick both aperture and shutter speed yourself.", "shootmode_1.png"),
        ("Movie", "Intelligent Auto", "Records video with automatic exposure.", "shootmode_2.png"),
        ("Time-lapse", "Intelligent Auto", "Captures a sequence of frames for a time-lapse.", "shootmode_3.png"),
        ("Stills", "Manual Exposure", "Captures still photos with manual exposure.", "shootmode_4.png")]))
    doc = {"settings": [{"key": "global:0x13e1", "name": "Exposure mode (movie)",
                         "values": [[0, "Intelligent Auto"], [2, "P"], [5, "M"]]},
                        {"key": "global:0x13e3", "name": "Exposure mode (time-lapse)", "values": [[2, "P"], [5, "M"]]},
                        {"key": "global:0x0bd5[0]", "name": "Shoot Mode", "values": [[3, "Manual Exposure"]]},
                        {"key": "global:0x10b6", "name": "Exposure mode (P/A/S/M)", "values": [[4, "M"]]}]}
    U.attach_help(doc, [])
    movie, lapse, hold, in_use = doc["settings"]
    assert movie["option_help"] == [[0, "Records video with automatic exposure."], [5, "Lets you pick both aperture and shutter speed yourself."]]
    assert "option_help" not in lapse                  # no Intelligent Auto value on the record
    assert hold["option_help"] == [[3, "Captures still photos with manual exposure."]]
    assert "option_help" not in in_use


def test_help_text_two_readers_decide():
    # OCR read "trame" where the guide says "frame" (AF Frame Move Amt, 2026-11-01)
    import help_reads as H
    assert H.decide("focus area trame.", "focus area frame.", lambda: "focus area frame.") == \
        ("focus area frame.", "two vision readers")
    assert H.decide('Sets "Spot".', 'Sets "Spot" .', lambda: None) == ('Sets "Spot" .', "agreed")
    assert H.decide("Sets a b", "Sets a c", lambda: "Sets a b") == ("Sets a b", "OCR and the second reader")
    assert H.decide("Sets a b", "Sets a c", lambda: "Sets a d")[1] == "review"
    assert H.decide("the actual frame rate is 119.88fps.", "the actual frame rate is 119.8fps.",
                    lambda: "the actual frame rate is 119.8fps.") == ("the actual frame rate is 119.88fps.", "OCR (digits)")


def test_menu_jump_groups_and_tabs():
    # the columns route (crawl_run.jump): a tab's groups from the Down cycle, multi-page groups as one
    from crawl_run import page_groups, tab_shown
    crumbs = ["Shooting > Zoom", "Exposure/Color > Exposure", "Exposure/Color > Exposure", "Exposure/Color > ISO",
              "Focus > AF/MF", "Main", "Shooting > Image Quality/Rec", "Shooting > Image Quality/Rec", "Shooting > Media"]
    model = {f"p{i}": {"breadcrumb": b} for i, b in enumerate(crumbs)}
    cycle = [{"kind": "menu", "page": f"p{i}"} for i in range(len(crumbs)) for _ in range(2)]
    g = page_groups(cycle, model)
    assert g["p6"] == g["p7"] == ("Shooting", 0) and g["p8"] == ("Shooting", 1) and g["p0"] == ("Shooting", 2)
    assert g["p1"] == g["p2"] == ("Exposure/Color", 0) and g["p3"] == ("Exposure/Color", 1)
    assert "p5" not in g                                   # not a tab the column route goes through
    assert tab_shown("Exposure / Color 19/61 Exposure") == "Exposure/Color"
    assert tab_shown("Shooting > Focus Mode") == "Shooting" and tab_shown("12 34") is None


def test_proof_viewer_keys():
    """The viewer files a change under the schema's own key: array elements, set records, blob fields."""
    from proof_viewer import Keys
    keys = Keys([{"key": "global:0x05db[9]"}, {"key": "global:0x05db[10]"}, {"key": "set:0x0b8d"},
                 {"key": "global:0x018c@1220", "size": 2}, {"key": "global:0x122e"}])
    assert keys.of("global:0x05db", [0] * 11, [0] * 9 + [-7, 0]) == [("global:0x05db[9]", -7)]
    assert keys.of("set3:0x0b8d", 1, 3) == [("set:0x0b8d", 3)]
    blob_before, blob_after = [0] * 1300, [0] * 1300
    blob_after[1221] = 5
    assert keys.of("global:0x018c", blob_before, blob_after) == [("global:0x018c@1220", None)]
    assert keys.of("global:0x122e", 1, 0) == [("global:0x122e", 0)]
    assert keys.of("global:0x9999", 0, 1) == []


def test_c4reset_only_on_a_look_panel():
    """C4 as Reset only on a Creative Look panel with Reset in its footer (2026-11-03)."""
    from drive import c4reset_refused
    panel = "Creative Look PT(Portrait) Contrast -9 Reset MENU Cancel OK"
    assert c4reset_refused("unknown", panel) == ""
    assert c4reset_refused("shooting", panel)
    assert c4reset_refused("menu", "Shooting > Image Quality/Rec 5/65 JPEG/HEIF Switch")
    assert c4reset_refused("dialog", "Playback Delete Multiple Img. Cancel OK")
    assert c4reset_refused("unknown", "Creative Look PT(Portrait) Look ? MENU Cancel OK")   # no Reset: the Look cell


def test_camset_ksy_matches_the_reader():
    """The hand-written format's header ends where the reference definition's block starts the sections, and the
    generated names are valid (the full tie of the .ksy to the block: test_definitions.py)."""
    import re
    from camset_ksy import format_spec, ksy, width
    spec = format_spec()
    off = 0
    for f in spec["seq"]:
        if f["id"] == "sections":
            break
        off += width(spec, f)
    block = camset.block_of(definitions.REFERENCE)
    assert off == block.sections_start.n
    assert spec["types"]["record"]["seq"][1]["contents"] == list(block.marker.to_bytes(2, "little"))
    k = ksy(json.loads(Path(DEFINITION).read_text(encoding="utf-8")))
    ids = [v["id"] for v in k["enums"]["setting"].values()]
    assert len(ids) == len(set(ids)) and all(re.match(r"^[a-z][a-z0-9_]*$", i) for i in ids)
    assert k["enums"]["setting"][0x01D8]["id"] == "jpeg_heif_switch"


def test_camera_json_matches_the_schema_copy():
    """Each data/<model>_fw<fw>/camera_<model>_fw<fw>.json and its definition's "camera" section are one set of facts
    kept twice: they must agree (the schema's had the movie memories' names, 2026-11-03, when the data file did not),
    the container block included (docs/decisions/0020)."""
    for p, doc in definitions.every():
        data = json.loads(Path(definitions.camera_file(p.stem)).read_text(encoding="utf-8"))
        data.pop("_comment", None)
        data.pop("$schema", None)
        assert data == doc["camera"], p.name


def test_volatile_records_have_one_source():
    """camset.VOLATILE and the volatile_records of every data/<model>_fw<fw>/camera_<model>_fw<fw>.json (which the editor reads through the schema)
    are the same set: the editor lacked 0x04e2, the camera-position record, while the kit ignored it (2026-11-04)."""
    from camkit import camset
    ids = set()
    for f in camset.CAMERA_FILES:
        ids |= set(json.loads(Path(f).read_text(encoding="utf-8"))["volatile_records"])
    assert {(0, rid) for rid in ids} == camset.VOLATILE
    assert 0x04E2 in ids


def test_reader_follows_the_format(tmp_path):
    """camset.read reads through the camera's container block: the a1 II definition's sample (the reference file,
    personal values removed) reads whole, and a record with a wrong marker is refused (2026-11-03)."""
    d = SAMPLE.read_bytes()
    cs = camset.read(SAMPLE)
    assert len(cs.sections) == 13 and len(cs.sections[0]) == 1415 and cs.checksums_ok
    r = cs.sections[0][0x01D8]
    assert d[r.offset:r.offset + 4] == bytes([0xD8, 0x01, 0xCF, 0x02])
    bad = bytearray(d)
    bad[r.offset + 2] = 0x00
    (tmp_path / "bad.DAT").write_bytes(bytes(bad))
    with pytest.raises(ValueError):
        camset.read(tmp_path / "bad.DAT")


def schema_checked() -> list:
    """(file, JSON Schema) of every definition and every data folder's files that have one: the same list the hook
    and CI check (docs/DATA_CONTRACTS.md, "What a mapping delivers")."""
    out = [(p.relative_to(ROOT).as_posix(), "definition") for p in sorted((ROOT / "editor" / "definitions").glob("*.json"))]
    for kind, schema in (("camera", "camera"), ("help", "help-file"), ("settings_reset", "settings-reset")):
        out += [(p.relative_to(ROOT).as_posix(), schema) for p in sorted((ROOT / "data").glob(f"*/{kind}_*_fw*.json"))]
    # the mapper's own menu trees, private whole (camkit.datafiles), where this computer has them
    out += [(p.as_posix(), "menu-tree") for p in sorted(definitions.EVIDENCE_DIR.glob("*/menu_tree_*_fw*.json"))]
    return out


@pytest.mark.parametrize("data, schema", schema_checked())
def test_data_files_match_their_json_schema(data, schema):
    """The definitions and the data files against their JSON Schemas (schemas/), with the standard validator
    (2026-11-03)."""
    import jsonschema
    from referencing import Registry, Resource
    def doc(p):
        return json.loads(Path(p).read_text(encoding="utf-8"))
    path = ROOT / "schemas" / f"{schema}.schema.json"
    reg = Registry().with_resources((p.name, Resource.from_contents(doc(p))) for p in (ROOT / "schemas").glob("*.json"))
    jsonschema.Draft202012Validator(doc(path), registry=reg).validate(doc(ROOT / data))


def test_help_files_take_and_give_back():
    """Help leaves the schema's settings for a help file and comes back the same (docs/decisions/0018)."""
    from camkit import help_files
    doc = {"model": "M", "layouts": [{"firmware": "1.00"}],
           "settings": [{"key": "a", "help": "Text.", "option_help": [[1, "One."]]}, {"key": "b"}]}
    assert help_files.name(doc) == "help_M_fw1.00.json"
    table = help_files.taken(doc)
    assert table == {"a": {"help": "Text.", "option_help": [[1, "One."]]}}
    assert all("help" not in s and "option_help" not in s for s in doc["settings"])
    assert help_files.put(doc, table) == 1 and doc["settings"][0]["help"] == "Text."


def test_a_help_file_is_read_only_for_the_camera_it_says_it_is_for(tmp_path, capsys):
    """A help file's own model and firmware decide whose it is, never its name: one named for the camera but carrying
    another model, or another firmware of the same model, or naming neither, or not a help file, is refused, its text
    not read, and a line says why, once (kit/camkit/help_files.py; the editor's Schema::apply_help does the same)."""
    from camkit import help_files
    doc = {"model": "M", "layouts": [{"firmware": "1.00"}], "settings": [{"key": "a"}]}
    table = {"a": {"help": "Text.", "option_help": [[1, "One."]]}}
    p = tmp_path / help_files.name(doc)
    assert help_files.refused(p, doc) is None and help_files.read(p, doc) == {}          # no file
    p.write_text(json.dumps({"model": "M", "firmware": "1.00", "source": "a test", "settings": table}), encoding="utf-8")
    assert help_files.refused(p, doc) is None and help_files.read(p, doc) == table
    assert capsys.readouterr().out == ""
    neither = "it does not say which camera it is for (its model and firmware)"
    for i, (head, why) in enumerate([({"model": "N", "firmware": "1.00"}, "it is for the N firmware 1.00, not the M firmware 1.00"),
                                     ({"model": "M", "firmware": "2.00"}, "it is for the M firmware 2.00, not the M firmware 1.00"),
                                     ({}, neither), ({"model": "M"}, neither), (None, "it does not read as a help file")]):
        q = tmp_path / str(i) / help_files.name(doc)          # named for M firmware 1.00, whatever it holds
        q.parent.mkdir()
        q.write_text("{ not json" if head is None else json.dumps({**head, "source": "a test", "settings": table}), encoding="utf-8")
        assert help_files.refused(q, doc) == why
        assert help_files.read(q, doc) == {} and help_files.read(q, doc) == {}
        assert capsys.readouterr().out == f"help: {q.as_posix()} is not used: {why}\n"          # said once
        assert help_files.put(doc, help_files.read(q, doc)) == 0 and "help" not in doc["settings"][0]


def test_check_public_catches_a_close_rewording():
    """Eight words in a row shared with the camera's text are refused; the same meaning in other words is not."""
    from check_public import runs
    camera = "Chooses which dial or wheel changes the exposure value while framing a new shot."
    close = "This chooses which dial or wheel changes the exposure value on the camera body."
    own = "Which control wheel adjusts exposure compensation when you are in a shooting mode."
    assert runs(close) & runs(camera)
    assert not runs(own) & runs(camera)


def test_check_public_finds_the_cameras_text_in_the_kits_strings(tmp_path, monkeypatch):
    """A string in kit/*.py that holds eight words in a row of the camera's In-Camera Guide text is refused, with its
    file and line; a string too short to hold eight words, or worded otherwise, is not (one test for the condition
    ruff's SIM102 folded into one if, 2026-11-08)."""
    import check_public
    from camkit import help_files
    camera = "Chooses which dial or wheel changes the exposure value while framing a new shot."
    (tmp_path / "kit").mkdir()
    (tmp_path / "kit" / "a.py").write_text(
        f"x = 1\nHELP = {camera!r}\nSHORT = 'which dial or wheel changes'\n"
        "OWN = 'Which control wheel adjusts exposure compensation when you are in a shooting mode.'\n", encoding="utf-8")
    doc = {"model": "M", "layouts": [{"firmware": "1.00"}], "settings": [{"key": "a", "name": "Dial"}]}
    monkeypatch.setattr(check_public, "ROOT", tmp_path)
    monkeypatch.setattr(help_files, "OWN", tmp_path / "data")
    monkeypatch.setattr(help_files, "PRIVATE", tmp_path / "private" / "help")
    help_files.PRIVATE.mkdir(parents=True)
    (help_files.PRIVATE / help_files.name(doc)).write_text(json.dumps(
        {"model": "M", "firmware": "1.00", "source": "a test", "settings": {"a": {"help": camera}}}), encoding="utf-8")
    assert check_public.definition_help_problems(tmp_path / "editor" / "definitions" / "M_fw1.00.json", doc, []) == [
        f"{Path('kit/a.py')}:2: shares 8 words in a row with the camera's In-Camera Guide text"]


def test_published_schema_has_only_the_projects_own_help():
    """No definition carries help text but its data/<model>_fw<fw>/help_<model>_fw<fw>.json's (docs/decisions/0018)."""
    from check_public import problems
    assert [p for p in problems() if "editor/definitions/" in p] == []


def test_check_public_refuses_another_cameras_help_file(tmp_path, monkeypatch, capsys):
    """A definition's own help file that says it is another camera's is one problem, said once, not every setting's
    text differing from it."""
    import check_public
    from camkit import help_files
    monkeypatch.setattr(help_files, "OWN", tmp_path)
    monkeypatch.setattr(help_files, "PRIVATE", tmp_path / "private")
    doc = {"model": "M", "layouts": [{"firmware": "1.00"}], "settings": [{"key": "a", "help": "A."}, {"key": "b", "help": "B."}]}
    own = help_files.own_path(doc)
    own.parent.mkdir()
    own.write_text(json.dumps({"model": "N", "firmware": "1.00", "source": "a test", "settings": {"a": {"help": "A."}}}), encoding="utf-8")
    assert check_public.definition_help_problems(ROOT / "editor" / "definitions" / "M_fw1.00.json", doc, []) == [
        f"{own.as_posix()}: not this definition's help file: it is for the N firmware 1.00, not the M firmware 1.00"]


def test_raw_stops_cannot_be_proved_in_the_movie_sq_and_time_lapse_memories():
    """One schema key covers a field in all twelve memory sets; where the live copy says no proof can reach a set's
    field, the set field says so for those sets (2026-11-03), and the live copy is named by the memories."""
    doc = json.loads(Path(DEFINITION).read_text(encoding="utf-8"))
    by = {s["key"]: s for s in doc["settings"]}
    for off in (260, 262):
        assert by[f"set:0x0180@{off}"]["unproved_sets"]["sets"] == list(range(4, 13))
    assert "unproved_sets" not in by["set:0x0180@288"]
    assert by["global:0x018c@1248"]["name"].startswith("Movie Memory 1: ")


def test_camset_read_validates_checksums(tmp_path):
    orig = SAMPLE.read_bytes()

    # Header checksum corruption at its site (0x39 on the a1 II)
    bad_hdr = bytearray(orig)
    bad_hdr[camset.block_of(paths.A1II).header_checksum.at.n] ^= 0xFF
    p1 = tmp_path / "bad_hdr.DAT"
    p1.write_bytes(bad_hdr)
    with pytest.raises(ValueError, match="checksum mismatch"):
        camset.read(p1)
    cs1 = camset.read(p1, check=False)
    assert not cs1.checksums_ok

    # Body checksum corruption at the last byte
    bad_body = bytearray(orig)
    bad_body[-1] ^= 0xFF
    p2 = tmp_path / "bad_body.DAT"
    p2.write_bytes(bad_body)
    with pytest.raises(ValueError, match="checksum mismatch"):
        camset.read(p2)
    cs2 = camset.read(p2, check=False)
    assert not cs2.checksums_ok


def with_a_repeated_id(data: bytes, section: int = 0, copies: int = 1) -> bytes:
    """The sample's bytes, in memory only (decision 6: no hand-made settings file is ever written), with the record
    after the section's first given the first one's id (copies of them), both checksums worked out again."""
    b = camset.block_of(paths.A1II)
    recs = b.frame(data)[section]
    out = bytearray(data)
    for _, _, _, off in recs[1:1 + copies]:
        out[off:off + 2] = recs[0][0].to_bytes(2, "little")
    return b.sealed(out)


def test_a_record_id_framed_twice_is_noted_never_refused(monkeypatch, capsys):
    """camset.parse keeps the last of a repeated record id in a section (the editor reads such a file as it always
    has); the kit's read (check=True) notes each repeat in Camset.duplicates, and camkit.session's compare and
    upload_check's read say so in one warning line. Nothing raises."""
    import upload_check as U
    from camkit import session
    orig = SAMPLE.read_bytes()
    first = camset.block_of(paths.A1II).frame(orig)[0][0][0]
    twice = camset.parse(with_a_repeated_id(orig), name="twice")
    assert twice.duplicates == [(0, first)] and twice.checksums_ok
    assert len(twice.sections[0]) == len(camset.parse(orig).sections[0]) - 1
    assert camset.parse(orig).duplicates == []
    assert camset.parse(with_a_repeated_id(orig), check=False).duplicates == []      # noted on the kit's read only
    thrice = camset.parse(with_a_repeated_id(orig, copies=2))
    assert thrice.duplicates == [(0, first), (0, first)]
    note = camset.duplicates_note({"after.DAT": thrice, "start.DAT": camset.parse(orig)})
    assert note == (f"warning: a record id appears twice in one section of after.DAT (global:0x{first:04x}): the "
                    f"comparison reads the last copy only, so a change in the first goes unseen. A camera's file has "
                    f"not done this before: keep the file and say so in the report.")
    assert camset.duplicates_note({"start.DAT": camset.parse(orig)}) == ""
    files = {"start.DAT": twice, "after.DAT": camset.parse(with_a_repeated_id(orig)), "clean.DAT": camset.parse(orig),
             "thrice.DAT": thrice}
    monkeypatch.setattr(camset, "read", lambda p, **kw: files[Path(p).name])          # read from memory, not a disk
    said = []
    assert session.compared(Path("start.DAT"), Path("after.DAT"), say=said.append) == []
    assert said == [camset.duplicates_note({"start.DAT": twice, "after.DAT": files["after.DAT"]})]
    assert f"start.DAT (global:0x{first:04x}); after.DAT (global:0x{first:04x})" in said[0]
    said.clear()
    session.compared(Path("clean.DAT"), Path("clean.DAT"), say=said.append)
    assert said == []
    got = U.read_noted("clean.DAT", "thrice.DAT")
    assert got == [files["clean.DAT"], thrice]
    assert capsys.readouterr().out.splitlines() == [camset.duplicates_note({"thrice.DAT": thrice})]
    U.read_noted("clean.DAT", "clean.DAT")
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("definition", sorted((ROOT / "editor" / "definitions").glob("*.json")), ids=lambda p: p.stem)
def test_schema_no_overlaps_or_dangling_links(definition):
    doc = json.loads(Path(definition).read_text(encoding="utf-8"))

    # 1. no setting lists the records a proof wrote together (the report's, decision 16)
    assert not [s["key"] for s in doc["settings"] if "written_with" in s]

    # 2. No two settings overlap within (area, id)
    by_rec = {}
    for s in doc["settings"]:
        by_rec.setdefault((s["area"], s["id"]), []).append(s)

    for (area, rid), group in by_rec.items():
        if len(group) == 1:
            continue
        whole = [s for s in group if s.get("index") is None and "@" not in s["key"]]
        assert not whole, f"Whole-record setting overlaps with other settings in {area} 0x{rid:04x}"

        seen_indices = set()
        covered_bytes = set()
        for s in group:
            if "@" in s["key"]:
                off = int(s["key"].split("@")[1])
                sz = s.get("field_size") or (s.get("size") if s.get("size") and s.get("size") < 8 else 2)
                rng = set(range(off, off + sz))
                assert not (covered_bytes & rng), f"Overlapping @offset bytes in {s['key']}"
                covered_bytes |= rng
            elif s.get("index") is not None:
                assert s["index"] not in seen_indices, f"Duplicate index {s['index']} in {s['key']}"
                seen_indices.add(s["index"])

    # 3. Integer values within signed bounds for size in (1, 2, 4)
    for s in doc["settings"]:
        sz = s.get("size")
        if sz in (1, 2, 4):
            lo = -(1 << (8 * sz - 1))
            hi = 1 << (8 * sz - 1)
            for pair in s.get("values") or []:
                v = pair[0] if isinstance(pair, list) else pair
                if isinstance(v, int):
                    assert lo <= v < hi, f"{s['key']} value {v} out of bounds for size {sz}"
            for v in s.get("range") or []:
                if isinstance(v, int):
                    assert lo <= v < hi, f"{s['key']} range {v} out of bounds for size {sz}"
            for v in s.get("refused") or []:
                if isinstance(v, int):
                    assert lo <= v < hi, f"{s['key']} refused {v} out of bounds for size {sz}"




# --- prove_run: the one-time notice, a table cell in scope, the Fn Menu walk's late frames

class FakeNoticeCamera:
    """A camera whose screen is one saved frame; presses are recorded and change nothing."""
    def __init__(self, path: Path):
        self.frame, self.keys = type("F", (), {"path": path})(), []

    def press(self, key):
        self.keys.append(key)


def test_first_time_notice_is_okayed_and_nothing_else_is():
    """first_time_notice: the camera's one-time notice before the Custom Key screen ("In the next setting screen, you
    can check the function assigned ...", "Don't show this again" / OK) is answered Down to OK and Enter, the box
    never ticked; an ordinary menu page is left alone."""
    import prove_run as P
    from camkit import ocr
    if not ocr.available():
        pytest.skip("no OCR engine")
    cam = FakeNoticeCamera(need(A1 / "kit2_pass2" / "shots" / "215457_right.png"))
    assert P.first_time_notice(cam) is True and cam.keys == ["down", "enter"]
    shots = sorted(need(A1 / "kit2_page_scan_osd3" / "shots").glob("*.png"))
    page = next((f for f in shots[:60] if screen.read(load(f)).kind == "menu"), None)
    if page is None:
        pytest.skip("no menu page among the scan's first frames")
    cam = FakeNoticeCamera(page)
    assert P.first_time_notice(cam) is False and cam.keys == []


def test_a_table_cell_is_in_scope_by_its_job_key_or_its_tables_row_key():
    """in_scope: --rows names a cell by "<path> / <cell>" (the job key --list prints) or by the tables file's own row
    key, which carries the screen for a second screen of one row; the row alone names all its cells."""
    import prove_run as P
    t = {"path": ["Fn Menu Settings"]}
    row, cell = "Fn Menu Settings (playback)", "Playback Lower / 6"
    assert P.in_scope({"Fn Menu Settings / Playback Lower / 6"}, row, t, cell)          # the job key
    assert P.in_scope({"Fn Menu Settings (playback) / Playback Lower / 6"}, row, t, cell)   # the tables row key
    assert P.in_scope({"Fn Menu Settings (playback)"}, row, t, cell)                     # the whole row
    assert not P.in_scope({"Fn Menu Settings / Playback Lower / 5"}, row, t, cell)
    assert not P.in_scope({"Fn Menu Settings"}, row, t, cell)        # the path alone is not the row's key here
    t = {"path": ["Custom Key/Dial Set."]}
    assert P.in_scope({"Custom Key/Dial Set. / AEL Button @0.key.0"}, "Custom Key/Dial Set.", t, "AEL Button @0.key.0")


class FakeLateTiles:
    """The Fn Menu as to_tile meets it: the cursor at (row, field); a press moves it one tile, but the OSD frame shows
    the move only after `late` refreshes (a stale picture), or never when `stuck`."""
    def __init__(self, late=0, stuck=False):
        self.at, self.late, self.stuck, self.keys, self.pending, self.wait = [0, 0], late, stuck, [], None, 0
        self.frame = type("F", (), {"path": Path("00000_fake.png")})()

    def press(self, key):
        self.keys.append(key)
        if self.stuck:
            return
        d = {"right": (0, 1), "left": (0, -1), "down": (1, 0), "up": (-1, 0)}[key]
        self.pending, self.wait = [self.at[0] + d[0], self.at[1] + d[1]], self.late
        self.late = 0                   # only the first press is seen late
        self._land()

    def _land(self):
        if self.pending is not None and self.wait <= 0:
            self.at, self.pending = self.pending, None

    def refresh(self, tag):
        self.wait -= 1
        self._land()

    def read(self):
        return screen.Screen(kind="fnmenu", row=self.at[0], field=self.at[1])


def test_to_tile_waits_out_a_late_frame_and_fails_a_cursor_that_never_moves(monkeypatch):
    """to_tile: a Right whose move the frame shows only two looks later is waited out (TILE_STALL_S) and the walk goes
    on; a cursor that never moves fails the walk after the second stall, not before."""
    import prove_run as P
    monkeypatch.setattr(P.proving.tables, "TILE_STALL_S", 0.05)
    monkeypatch.setattr(P.time, "sleep", lambda s: None)
    cam = FakeLateTiles(late=2)
    P.to_tile(cam, (0, 2))
    assert cam.at == [0, 2] and cam.keys == ["right", "right"]
    cam = FakeLateTiles(stuck=True)
    with pytest.raises(P.Failed, match="did not move"):
        P.to_tile(cam, (0, 2))
    assert cam.keys == ["right", "right"]


def test_a_vision_reading_of_one_part_or_beside_two_agreeing_readers_is_no_dispute(monkeypatch):
    """The vision model reading one axis of a two-part name ("5 Images" of the bracket's "2.0 EV 5 Img.") backs the
    map's label as one reader; one reading something else on the screen ("Fast", the scale's end) while the map and
    the bar's OCR read the name alike leaves two readers; a vision reading far from a lone map label is still a
    dispute (2026-11-07, with the offline re-read's 1,304 readings)."""
    import pass2_report as R
    monkeypatch.setattr(R, "ROW_NAMES", set())
    o = lambda label, shown=None, vlm=None: {"kind": "list", "label": label, "shown": shown, "vlm": vlm}
    assert R.part_of("5 Images", "2.0 EV 5 Img.") and R.part_of("2 Images (+)", "0.3 EV 2 Img. +")
    assert not R.part_of("2 Images (+)", "0.5 EV 2 Img. -") and not R.part_of("Fast", "5")
    assert R.name_of(o("2.0 EV 5 Img.", None, "5 Images")) == ("2.0 EV 5 Img.", "one reader (map)", None)
    assert R.name_of(o("5", "5", "Fast")) == ("5", "two readers", None)
    assert R.name_of(o("F11", None, "Focus Mode"))[1] == "disputed"


def test_an_add_item_proofs_vision_reading_of_another_row_or_a_group_does_not_count(monkeypatch, tmp_path):
    # the picker's option is a menu row itself: the reader's "AF/MF" (the page's group) or "Composite RAW Sht." (the
    # row beside it) over "Preset Focus/Zoom" is the header or a neighbour read, not a dispute (2026-11-07)
    import pass2_report as R
    monkeypatch.setattr(R, "ROW_NAMES", set())
    monkeypatch.setattr(R, "MENU_NAMES", {R.norm("AF/MF"), R.norm("Composite RAW Sht."), R.norm("Preset Focus/Zoom")})
    o = lambda label, shown, vlm, mm=True: {"kind": "list", "label": label, "shown": shown, "vlm": vlm,
                                           **({"my_menu": {"page": 1, "slot": 0, "code": 1}} if mm else {})}
    assert R.name_of(o("Preset Focus/Zoom", "Preset Focus/Zoom", "AF/MF")) == ("Preset Focus/Zoom", "one reader (map)", None)
    assert R.name_of(o("Pixel Shift Multi Shoot.", "[01 Image Quality/Rec Pixel Shift Multi Shoot.", "Composite RAW Sht.")) \
        == ("Pixel Shift Multi Shoot.", "one reader (map)", None)
    # the same readings on any other proof stay a dispute: there the option is not a row
    assert R.name_of(o("Preset Focus/Zoom", None, "AF/MF", mm=False))[1] == "disputed"
    tree = {"tabs": [{"tab": "Focus", "pages": [{"group": "AF/MF", "rows": [{"label": "Preset Focus/Zoom"}]}]}],
            "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": [{"group": "Image Quality/Rec",
                                                                              "rows": [{"label": "Composite RAW Sht."}]}]}]}]}
    f = tmp_path / "menu_tree_test.json"
    f.write_text(json.dumps(tree), encoding="utf-8")
    assert R.menu_names(f) == {R.norm(x) for x in ("AF/MF", "Preset Focus/Zoom", "Image Quality/Rec", "Composite RAW Sht.")}
    assert R.menu_names(None) == set() and R.menu_names(f.with_name("none.json")) == set()


def test_a_picker_item_is_named_against_the_cameras_own_rows(tmp_path):
    # kit/provers/mymenu_run.py (2026-11-07): the OCR of the lit row carries icon noise and, on a page's first row, the
    # group's name; the reader now and then answers with the group's name. The menu tree's rows settle it
    sys.path.insert(0, str(ROOT / "kit" / "provers"))
    import mymenu_run as M
    rows = {M.squash(x): x for x in ("JPEG/HEIF Switch", "Preset Focus/Zoom", "Shoot Mode", "S&Q Shoot Mode",
                                     "Camera Set. Memory", "MR Camera Set. Memory", "Zoom", "Fn Menu Settings",
                                     "Reg. Flash Shooting Set", "Flash Mode", "with Shutter Button", "S with Shutter Button")}
    name = lambda lit, vlm: M.item_name(lit, vlm, rows)
    assert name("Image Quality/Rec JPEG/HEIF Switch", "Image Quality/Rec") == ("JPEG/HEIF Switch", "map")  # the group read
    assert name("Preset Focus/Zoom", "AF/MF") == ("Preset Focus/Zoom", "map")
    assert name("Reg. Flash Shooting Set", "Flash") == ("Reg. Flash Shooting Set", "map")              # the longest ending
    assert name("MR Camera Set. Memory", "Camera Set. Memory") == ("Camera Set. Memory", "map")       # the reader's, of two endings
    assert name("•I S with Shutter Button", "with Shutter Button") == ("with Shutter Button", "map")
    assert name("$ Shoot Mode S&Q", "Shoot Mode") == ("S&Q Shoot Mode", "map")        # the reader's words grown by the OCR's
    assert name("Shooting Mode 4 Shoot Mode", "Shoot Mode") == ("Shoot Mode", "map")
    assert name("Audio Recording &Zoom 8", "Zoom") == ("Zoom", "vision")                # no ending: the reader's row
    assert name("Priority in Multi Metering", "Priority in Multi Metering") == ("Priority in Multi Metering", "reading")
    assert name("•Something Else", "") == ("Something Else", "reading")
    # twins are numbered by their place in the picker
    items = [{"label": "Fn Menu Settings"}, {"label": "Zoom"}, {"label": "Fn Menu Settings"}, {"label": "Fn Menu Settings"}]
    assert [x["label"] for x in M.twin_names(items)] == ["Fn Menu Settings", "Zoom", "Fn Menu Settings (2)", "Fn Menu Settings (3)"]
    # --relabel names a run's proofs again from the readings they kept, in picker order, keeping the file before
    proofs = tmp_path / "proofs.jsonl"
    recs = [{"path": M.PATH, "kind": "list", "index": 0, "label": "AF/MF", "shown": "Preset Focus/Zoom", "vlm": "AF/MF",
             "picker_page": 2, "applied": True, "my_menu": {"page": 1, "slot": 0, "code": 2330}},
            {"path": ["Other"], "kind": "list", "label": "Off"},
            {"path": M.PATH, "kind": "list", "index": 1, "label": "Fn Menu Settings", "shown": "8 Fn Menu Settings",
             "vlm": "Fn Menu Settings", "picker_page": 3, "applied": True, "my_menu": {"page": 1, "slot": 1, "code": 2497}},
            {"path": M.PATH, "kind": "list", "index": 2, "label": "Fn Menu Settings", "shown": "Fn Menu Settings",
             "vlm": "Fn Menu Settings", "picker_page": 3, "applied": True, "my_menu": {"page": 1, "slot": 2, "code": 2096}}]
    proofs.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    said = []
    assert M.relabel(proofs, rows, said.append) == 2
    got = [json.loads(line) for line in proofs.read_text(encoding="utf-8").splitlines()]
    assert [r["label"] for r in got] == ["Preset Focus/Zoom", "Off", "Fn Menu Settings", "Fn Menu Settings (2)"]
    assert got[0]["label_from"] == "map" and "label_from" not in got[1]
    assert len(list(tmp_path.glob("proofs.jsonl.*.bak"))) == 1
    assert M.relabel(proofs, rows, said.append) == 0 and len(list(tmp_path.glob("proofs.jsonl.*.bak"))) == 1


def test_records_a_put_back_leaves_are_told_kept_or_not_offered():
    # prove_run.put_back_leftovers (2026-11-07): after the saved option is chosen back, a record the camera has held
    # since an earlier option is "kept", one whose start value no option gave back is "not offered"; anything else
    # is a failed put-back
    import prove_run as P
    ch = lambda key, before, after: camset.Change(0, int(key.split("0x")[1], 16), before, after)
    # S&Q Shoot Mode: the exposure-mode record took 5 at S&Q Motion and held it through Time-lapse (the put-back)
    hist = [{"global:0x118b": 0, "global:0x13e2": 5}, {"global:0x13e2": 5}]
    assert P.put_back_leftovers([ch("global:0x13e2", 0, 5)], hist) == {"kept": ["global:0x13e2"], "not_offered": []}
    # made-up records and values: a start value that is not among the options the list offers (a list of two)
    hist = [{"global:0x0002": 1}, {"global:0x0002": 0}]
    assert P.put_back_leftovers([ch("global:0x0002", 7, 0)], hist) == {"kept": [], "not_offered": ["global:0x0002"]}
    # a start value no option gave back (a list the mode refuses it on): 2 set first, then other values, then 2 again
    hist = [{"global:0x0003": 2}, {"global:0x0003": 3}, {"global:0x0003": 5}, {"global:0x0003": 2}]
    assert P.put_back_leftovers([ch("global:0x0003", 6, 2)], hist) == {"kept": [], "not_offered": ["global:0x0003"]}
    # a record that went back and forth and ends elsewhere is a failed put-back
    hist = [{"global:0x0001": 1}, {}, {"global:0x0001": 1}]
    assert P.put_back_leftovers([ch("global:0x0001", 0, 1)], hist) is None
    # the put-back alone setting a value no earlier option set, while the start value was offered, is a failure too
    hist = [{"global:0x0001": 1}, {"global:0x0001": 2}]
    assert P.put_back_leftovers([ch("global:0x0001", 1, 2)], hist) is None


def test_a_checklists_leftover_that_mirrors_a_box_is_no_failed_put_back():
    # Rating Set(Custom Key) (2026-11-07): five second copies, 0 in the start file, mirror each box's tick from the
    # first save on (1 ticked, 0 not); with every box back they all read 1. Visits: ★ off, ★ on + ★★ off, ... , all back
    import prove_run as P
    labels = ["★", "★★", "★★★"]
    ch = lambda key, before, after: camset.Change(0, int(key.split("0x")[1], 16), before, after)
    copies = ["global:0x16bd", "global:0x16be", "global:0x16bf"]
    flips = [{0: False}, {0: True, 1: False}, {1: True, 2: False}, {2: True}]
    history = [{k: (0 if copies.index(k) in fl and not fl[copies.index(k)] else 1) for k in copies} for fl in flips]
    for h in history:                               # a 0 is the start value: not in the download's changes
        for k in list(h):
            if h[k] == 0:
                del h[k]
    rest = [ch(k, 0, 1) for k in copies]
    assert P.put_back_leftovers(rest, history) is None
    assert P.mirrored_boxes(rest, history, flips, labels) == {"kept": [], "not_offered": [],
                                                              "mirrors": {k: {"box": b, "ticked": 1} for k, b in zip(copies, labels, strict=True)}}
    # a record that follows no box is a failure still
    odd = [{"global:0x0001": 1}, {"global:0x0001": 2}, {"global:0x0001": 1}, {"global:0x0001": 2}]
    assert P.mirrored_boxes([ch("global:0x0001", 0, 2)], odd, flips, labels) is None


def test_option_keys_take_any_seconds_mark_alike():
    # 2", 2″ and 2” are one shutter time however the reader draws the mark (2026-11-07)
    from camkit import match
    assert match.key('2"') == match.key("2″") == match.key("2”") and match.key('0.5"') == match.key("0.5″")
    assert match.key('2"') != match.key('4"')


def test_a_groups_name_matches_without_the_icon_glyph_each_reader_glues_on():
    # the lit group's text and the scan's model glue different icon glyphs to one name ("ICnct./Remote Sht." against
    # "DCnct./Remote Sht.", 2026-11-07): the group is still told
    import crawl_run as C
    names = ["DCnct./Remote Sht.", "FTP Transfer", "Streaming"]
    assert C.group_shown("ICnct./Remote Sht.", names) == 0 and C.group_shown("Network > FTP Transfer", names) == 1
    assert C.unglued("DCnct./Remote Sht.") == "Cnct./Remote Sht." and C.unglued("FTP Transfer") == "FTP Transfer"
    assert C.unglued("ISO") == "ISO"


def test_the_report_credits_kept_side_records_to_no_option_and_mirrored_copies_to_their_box(monkeypatch):
    # prove_run's put-back notes (attempts.jsonl "put_back", 2026-11-07): Exposure Ctrl Type = Flexible Exp. Mode
    # reassigns keys the camera then keeps; Rating Set(Custom Key)'s second copies mirror each box's tick
    import pass2_report as R
    monkeypatch.setattr(R, "PUT_BACK", {
        "a1": {"kept": ["global:0x0421"], "not_offered": []},
        "a2": {"kept": [], "not_offered": [], "mirrors": {"global:0x16be": {"box": "★★", "ticked": 1}}}})
    o = lambda i, label, changes, **kw: {"kind": "list", "path": ["Exposure Ctrl Type"], "index": i, "label": label,
                                        "applied": True, "attempt": "a1", "dat": f"{i}.DAT", "base": "b.DAT",
                                        "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes], **kw}
    opts = {1: o(1, "Flexible Exp. Mode", [("global:0x02b0", 0, 1), ("global:0x0421", 861, 805)]),
            0: o(0, "P/A/S/M Mode", [("global:0x0421", 861, 805)])}
    vals = R.values_of(opts)
    assert set(vals) == {"global:0x02b0"} and vals["global:0x02b0"] == {"Flexible Exp. Mode": 1, "P/A/S/M Mode": 0}
    box = lambda i, label, boxes, changes: {"kind": "checklist", "path": ["Rating Set(Custom Key)"], "index": i,
                                            "label": label, "applied": True, "attempt": "a2", "base": "b.DAT",
                                            "boxes": boxes, "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes]}
    opts = {0: box(0, "★", [{"box": 0, "label": "★", "ticked": False}],
                   [("global:0x0f96", 0, 1), ("global:0x16be", 0, 1)]),
            1: box(1, "★★", [{"box": 0, "label": "★", "ticked": True}, {"box": 1, "label": "★★", "ticked": False}],
                   [("global:0x0f97", 0, 1), ("global:0x16bd", 0, 1)]),
            2: box(2, "(all back)", [{"box": 1, "label": "★★", "ticked": True}],
                   [("global:0x16bd", 0, 1), ("global:0x16be", 0, 1)])}
    vals = R.values_of(opts)
    assert vals["global:0x16be"] == {"★★: ticked": 1, "★★: unticked": 0}
    assert vals["global:0x0f96"] == {"★: unticked": 1, "★: ticked": 0}


def test_a_side_write_to_another_rows_record_is_not_this_rows_value():
    # pass2_report.values_of (2026-11-07): ISO Auto/Manual Set = Auto puts ISO on AUTO; what ISO held before is the
    # ISO row's, not "Manual"'s. S&Q Shoot Mode's two options both carry the S&Q exposure mode the camera set on
    # entering S&Q Motion: not the row's. A record the row takes through several values, or one named for the row,
    # stays the row's
    import pass2_report as R
    o = lambda path, i, label, changes: {"kind": "list", "path": path, "index": i, "label": label, "applied": True,
                                        "dat": f"{label}.DAT", "base": "b.DAT",
                                        "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes]}
    names = {"global:0x0334": "ISO", "global:0x033c": "ISO Auto/Manual Set", "global:0x13e2": "Exposure mode (S&Q Motion)",
             "global:0x118b": "S&Q Shoot Mode: Motion or Time-lapse", "global:0x103a": "Subject Recognition Person Tracking Subject Shift Range"}
    opts = {0: o(["Auto/Manual Swt. Set.", "ISO Auto/Manual Set"], 0, "Auto", [("global:0x033c", 1, 0), ("global:0x0334", 26, 0)]),
            1: o(["Auto/Manual Swt. Set.", "ISO Auto/Manual Set"], 1, "Manual", [])}
    vals = R.values_of(opts, frozenset({"global:0x0334"}), names)
    assert vals["global:0x033c"] == {"Auto": 0, "Manual": 1} and vals["global:0x0334"] == {"Auto": 0}
    opts = {0: o(["S&Q Shoot Mode"], 0, "S&Q Motion", [("global:0x118b", 1, 0), ("global:0x13e2", 0, 5)]),
            1: o(["S&Q Shoot Mode"], 1, "Time-lapse", [("global:0x13e2", 0, 5)])}
    vals = R.values_of(opts, frozenset({"global:0x118b", "global:0x13e2"}), names)
    assert vals == {"global:0x118b": {"S&Q Motion": 0, "Time-lapse": 1}}
    opts = {i: o(["Recognition Target", "Human", "Tracking Shift Range"], i, lab, ch) for i, (lab, ch) in enumerate(
        [("1 (Narrow)", [("global:0x103a", 2, 0)]), ("2", [("global:0x103a", 2, 1)]), ("3(Standard)", []), ("4", [("global:0x103a", 2, 3)])])}
    vals = R.values_of(opts, frozenset({"global:0x103a"}), names)
    assert vals["global:0x103a"] == {"1 (Narrow)": 0, "2": 1, "3(Standard)": 2, "4": 3}


def test_filter_condition_reads_the_item_from_either_cursor_column(monkeypatch):
    # the box column's crop can read the value alone on the orange bar ("Yes" for "Protect  Yes", 2026-11-07): the
    # read that names an item wins; in the value column only the wide band is read
    from types import SimpleNamespace as NS
    sys.path.insert(0, str(ROOT / "kit" / "provers"))
    import filter_run as F
    monkeypatch.setattr(F.ocr, "read", lambda paths: {paths[0]: "img"})
    cam = NS(read=lambda: NS(kind="checklist", bar=(258, 305), focus="rows"), frame=NS(path=Path("/tmp/x.png")))
    monkeypatch.setattr(F, "check_box_label", lambda cam: "Yes")
    monkeypatch.setattr(F.ocr, "text_in", lambda img, box: "Protect")
    assert F.box_label(cam) == "Protect"
    monkeypatch.setattr(F, "check_box_label", lambda cam: "Still Images/Movies")
    assert F.box_label(cam) == "Still Images/Movies"
    cam = NS(read=lambda: NS(kind="checklist", bar=(258, 305), focus="values"), frame=NS(path=Path("/tmp/x.png")))
    assert F.box_label(cam) == "Protect"
    assert F.box_label(NS(read=lambda: NS(kind="list", bar=None, focus=None), frame=None)) == ""


def test_the_hdmi_feed_reads_ffmpeg_errors_as_they_come(tmp_path):
    """ffmpeg's stderr was a pipe nobody read: 64 KB of repeated errors blocked ffmpeg in its next write, and the feed
    stopped. A stand-in for ffmpeg writes 200 KB of errors, then a frame: the frame arrives, the last error is kept."""
    import time
    from camkit import frames
    src = frames.HdmiSource.__new__(frames.HdmiSource)
    src.run, src.size, src.crop, src.out = Run("hdmi", root=tmp_path), (640, 480), (0, 0, 640, 480), (640, 480)
    src._lock, src._latest, src._hist, src._restarted = frames.threading.Lock(), None, frames.deque(), 0.0
    src.errors = frames.deque(maxlen=20)
    script = ("import sys\n"
              "for i in range(2000): sys.stderr.write('error %d: a dongle repeating itself' % i + 'x' * 60 + '\\n')\n"
              "sys.stderr.flush()\n"
              "sys.stdout.buffer.write(bytes(640 * 480 * 3)); sys.stdout.flush()\n"
              "import time; time.sleep(30)\n")
    src.cmd = [sys.executable, "-c", script]
    src._start()
    try:
        end = time.monotonic() + 20
        while (src._latest is None or not src.errors or not src.errors[-1].startswith("error 1999")) \
                and time.monotonic() < end:
            time.sleep(0.05)
        assert src._latest is not None and src._latest.image.shape == (480, 640, 3)
        assert src.errors[-1].startswith("error 1999")
        t0 = time.monotonic()
    finally:
        src.close()
    assert src.proc.poll() is not None and time.monotonic() - t0 < 2.5      # stopped at once, not after 3 s


# ---------------------------------------------------------------- unseen values: the report's line rule and held axes

def test_a_scale_number_reads_kelvin_ev_sixths_and_nothing_else():
    """scale_number: the numbers a menu lists as a scale, with an option's name in front, OCR's Cyrillic letters, ± for
    zero and a signed fraction; a frame rate, a shutter speed or a word is no scale (pass2_report.scale_line)."""
    import pass2_report as R
    assert R.scale_number("С.Temp./Filter: 6000 K") == (6000.0, "K"), "Cyrillic С and the option's name in front"
    assert R.scale_number("-0.3 EV") == (-0.3, "EV") and R.scale_number("±0") == (0.0, "")
    assert R.scale_number("+2/6") == (pytest.approx(1 / 3), "") and R.scale_number("-6/6") == (-1.0, "")
    assert R.scale_number("12") == (12.0, "") and R.scale_number("92.5%") == (92.5, "%")
    for text in ("60p", "1/250", "2/6", "Auto", "ISO 400", '0.5"'):
        assert R.scale_number(text) is None, f"{text!r} is no scale"


def test_a_sampled_list_or_axis_of_numbers_gets_the_line_rule():
    """scale_verdict: a list or carousel axis of numbers in one unit that sampled the definition's longer list gets
    linear (the colour temperature: 2500/3200/6000/9900 K stored (K - 2500) / 100), one off the line False, and a
    list proved whole none, whatever its numbers; labels of two units or words give none."""
    import pass2_report as R
    temp = {"T: 2500 K": 0, "T: 3200 K": 7, "T: 6000 K": 35, "T: 9900 K": 74}
    s = {"values": [[v, f"{2500 + 100 * v} K"] for v in range(75)]}
    axis = {0: {"kind": "axis"}}
    assert R.scale_verdict(axis, {"axis"}, "k", temp, s, {}) is True
    assert R.scale_verdict(axis, {"axis"}, "k", {**temp, "T: 6000 K": 36}, s, {}) is False
    whole = {"values": [[v, lab] for lab, v in temp.items()]}
    assert R.scale_verdict(axis, {"axis"}, "k", temp, whole, {}) is None, "every value proved: no sample"
    assert R.scale_verdict(axis, {"axis"}, "k", {"A": 0, "B": 1, "C": 2}, s, {}) is None
    assert R.scale_verdict(axis, {"axis"}, "k", {"1 K": 0, "2 EV": 1, "3 K": 2}, s, {}) is None, "two units"
    # a sampled number field keeps its own rule; a grid takes its line from grid_lines
    assert R.scale_verdict({0: {"kind": "fields", "sampled": True}}, {"fields"}, "k", {"-3": 0, "0": 3, "3": 6}, s, {})
    grid = {0: {"kind": "wbgrid", "preset": 4, "context": "Movie mode"}}
    assert R.scale_verdict(grid, {"wbgrid"}, "k", {"A7": 7000}, s, {(4, "Movie mode", "k"): True}) is True


def wbgrid(preset, axis, value, changes, context=None, back=False):
    """A White Balance grid proof as kit/provers/grid_run.py writes it (made-up records)."""
    r = {"path": ["White Balance"], "kind": "wbgrid", "option": f"grid {preset}", "preset": preset, "axis": axis,
         "index": [preset, axis, "back" if back else value], "value": value, "applied": True,
         "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes]}
    return {**r, "context": context} if context else r


def test_the_white_balance_grid_is_checked_within_one_preset_and_context(tmp_path):
    """grid_independence and grid_lines group a preset's proofs by context: the stills grid and Movie mode's share the
    record in use but start from other values, so a stills corner said nothing of the Movie grid's own record and the
    report printed "20 records off the axis lines" for presets 0-11 (2026-11-08). Within one context the corners and
    the inside point lie on each axis's line, and a point off it is still caught. Made-up records, preset and starts
    (the Movie grid's -2500 included)."""
    import pass2_report as R
    use, still, movie = "global:0x0001", "global:0x0002", "global:0x0003"
    proofs = []
    for ctx, own, start in ((None, still, 0), ("Movie mode", movie, -2500)):
        for x in (-7000, 7000):
            proofs.append(wbgrid(9, "A-B", x, [(use, start, -x), (own, start, -x)], ctx))
        proofs.append(wbgrid(9, "A-B", 0, [], ctx, back=True))
        for ab, gm in ((-7000, -7000), (7000, 7000), (-3500, 2250)):
            proofs.append(wbgrid(9, "corner", [ab, gm], [(use, start, -ab), (own, start, -ab)], ctx))
    (tmp_path / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in proofs), encoding="utf-8")
    got = R.grid_independence(tmp_path)
    assert [(p, n, bad) for p, n, bad in got] == [(9, 3, []), ("9 [Movie mode]", 3, [])]
    lines = R.grid_lines(proofs)
    assert lines[(9, "", still)] is True and lines[(9, "Movie mode", movie)] is True and lines[(9, "", use)] is True
    proofs[-1]["changes"][1]["after"] = 3000                 # the Movie inside point off its line
    (tmp_path / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in proofs), encoding="utf-8")
    assert R.grid_independence(tmp_path)[1][2] == [(-3500, 2250, movie, 3500, 3000)]
    assert R.grid_lines(proofs)[(9, "Movie mode", movie)] is False


def test_an_axis_credits_the_value_it_held_to_its_last_visit(monkeypatch):
    """held_axis_value, by axis_values: the last visit put the axis back on the value it held, which, on a record only
    the axis writes, is that label's, as a list's own start is (a made-up axis: Faster 4, Slower 0, Slow 1 and Fast 3
    written, then Standard put back with nothing changed: the value the axis held, 2). Not on a record the carousel's
    own row writes (Focus Area's full memory holds the option it opened on) or a live readout (ISO in use), nor when
    another label wrote that value, nor with the row unknown. With no visit of the last visit's own attempt, the value
    is read from its base file, never taken from another attempt's start."""
    import pass2_report as R
    key, full = "global:0x0001", "global:0x0002"
    o = lambda label, after, final=False: {
        "kind": "axis", "option": "Auto", "label": label, "final": final, "applied": True, "base": "b.DAT",
        "changes": [] if final else [{"key": key, "before": 2, "after": after}, {"key": full, "before": 0, "after": 9 + after}]}
    opts = {4: o("Faster", 4), 0: o("Slower", 0), 1: o("Slow", 1), 3: o("Fast", 3), 2: o("Standard", None, final=True)}
    got = R.axis_values(opts, main_keys=frozenset({full}))
    assert got[key] == {"Faster": 4, "Slower": 0, "Slow": 1, "Fast": 3, "Standard": 2}
    assert "Standard" not in got[full], "a record the carousel's own options write: its value before is no axis value"
    assert "Standard" not in R.axis_values(opts)[key], "the carousel's own row unknown: no credit"
    opts[3] = o("Fast", 2)
    assert "Standard" not in R.axis_values(opts, main_keys=frozenset())[key], "Fast was seen writing 2"
    rows = {"Speed [ctx]": {0: {"kind": "list", "applied": True, "label": "1\"",
                                "changes": [{"key": "global:0x0003", "before": 0, "after": 18}]}},
            "Speed / Auto [ctx]": opts}
    assert R.main_row_keys(rows, "Speed / Auto [ctx]", opts) == frozenset({"global:0x0003"})
    assert R.main_row_keys(rows, "Speed [ctx]", rows["Speed [ctx]"]) is None
    readout = frozenset({"global:0x0004"})
    assert R.no_credit(rows, "Speed / Auto [ctx]", opts, readout) == frozenset({"global:0x0003", "global:0x0004"})
    assert R.no_credit(rows, "Speed [ctx]", rows["Speed [ctx]"], readout) is None
    opts[3] = o("Fast", 3)
    opts[2] = {**o("Standard", None, final=True), "base": "own.DAT"}     # the put-back in a session of its own
    assert "Standard" not in R.axis_values(opts, main_keys=frozenset({full}))[key], "its base not here: no credit"
    monkeypatch.setattr(R, "base_value", lambda base, k: 5 if (base, k) == ("own.DAT", key) else None)
    assert R.axis_values(opts, main_keys=frozenset({full}))[key]["Standard"] == 5, "read from its own base file"


def test_a_value_a_hand_rule_names_is_still_no_plain_options_write():
    """screen_records with kept_over: the records only a function's own screen wrote stay that screen's when the next
    option kept them, a hand rule naming them or not. Rating's copies (0x16bd...), which Rating Set's screen writes
    and the AEL key's next option kept, were credited to the key once KEEP_LABELS named them, and every playback key
    took "Ticked" as a function (2026-11-08)."""
    import pass2_report as R
    copy = "global:0x16bd"
    opts = {0: {"kind": "table", "label": "Rating", "own_screen": {"kind": "checklist"}, "dat": "a.DAT",
                "changes": [{"key": "global:0x0441", "before": 354, "after": 337}, {"key": copy, "before": 0, "after": 1}]},
            1: {"kind": "table", "label": "Image Index", "dat": "b.DAT",
                "changes": [{"key": "global:0x0441", "before": 354, "after": 354}, {"key": copy, "before": 0, "after": 1}]},
            2: {"kind": "table", "label": "Protect", "dat": "c.DAT",
                "changes": [{"key": "global:0x0441", "before": 354, "after": 336}]}}
    kept = frozenset({("b.DAT", copy)})
    assert R.screen_records(opts) == set(), "without the carried value, Image Index looks like it wrote the copy"
    assert R.screen_records(opts, kept) == {copy}
    assert copy not in R.values_of(opts, kept_over=kept)


def test_the_clone_guard_says_a_kit_writer_running_meanwhile_can_cause_it():
    """conftest.guard_the_clones_files fails a test that changed the clone's data/ or private/evidence/; its words say
    that a kit command writing those files at the same time as the tests (schema_update.py --write in another
    terminal) can cause it too, so the person runs the tests again rather than hunting the test."""
    from conftest import guard_words
    words = guard_words(["data/X/settings_reset_X.json"])
    assert "data/X/settings_reset_X.json" in words and "at the same time as the tests" in words
    assert "kit/schema_update.py --write" in words
