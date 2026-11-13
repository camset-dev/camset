"""Pixel reader: screen type, position and on-screen key hints, from a canonical 640x480 frame.

Deterministic and fast (a few ms); text is read elsewhere (ocr.py, vlm.py). Position never comes
from text. Layout facts below were measured on ILCE-1M2 OSD frames composited onto black
(frames.load); HDMI frames are cropped/scaled into the same layout.

Screen types:
  menu      menu page: coloured tab column at x 0-47; the cursor is on the rows when the orange
            row bar (x 140-636) is drawn, otherwise in the group column
  submenu   a row's own page of rows ("Shooting > Drive Mode > Interval Shoot Func."): no tab or group
            columns, the left column is empty but for ‹ (Left goes back), rows and the orange bar
            start at x 55; same row pitch as menu pages; may have n/N pages and an info line
  fields    number-field form ("Shooting Interval", "ISO Range Limit"): title line at y 53, footer
            line at y 426 (MENU Cancel, ● OK); the active field is an orange-filled box, the others
            are boxes with grey borders on the same line; ▲/▼ boxes over/under the active field show
            which way it can still move (one missing = the end of the range); when the camera draws no
            outlines round its controls (see "Outlines" below) the ▲/▼ stand alone, without their boxes
  checklist checkbox list ("Drive Mode Limit", "Different Set for Still/Mv", DISP Set > Monitor):
            title and footer lines, solid light checkbox squares (orange ✓ inside when ticked) near
            the left edge, OK/Cancel buttons; layouts vary (pitch 50-54 px, OK under the rows or at
            the right, radio sub-options under some boxes; Rating Set(Custom Key) has a second column,
            boxes counted down the first, then the second). The cursor is an orange row bar or an
            orange button; on a button Enter would apply, so the walker leaves with MENU (Cancel)
  look      Creative Look parameter panel (over live view, so no title line): a framed strip of 8
            parameter cells (y 350-403), the selected one orange with ⌃/⌄ over/under it where the
            value can still move; an orange ▶ on the vertical scale at the right marks the value, and
            the scale's tick marks (on the a1 II, one a step) run from its top end (y 99) to its bottom (y 243).
            Cell 0, the Look itself, shows at the left only while selected (▲▼ boxes, no scale)
  slider    one value on a horizontal scale (Aspect Marker Level, Exposure Comp., Flash Comp.), over
            live view: − and + boxes (92 px wide, mirrored about x 320, y ~316-378; without outlines the
            − and + alone, mirrored the same way), an orange 13x13
            marker above or below the scale, the value in orange between ◂ ▸ (one goes at an end)
  sidelist  Picture Profile parameter list (PP1 > Gamma, Black Gamma > Range), over live view: ↩ box at
            the left (x 19-81; the ↩ alone without outlines), rows on the right (orange bar x 303-597,
            50 px pitch from y 86), a dim scrollbar at x 607 on long lists
  wbgrid    White Balance Adjustment: colour grid with △▽◁▷ boxes round it (the triangles alone without
            outlines); the orange dot is the A-B/G-M position (snapped to grid cells), the readouts below
            give the exact values
  checkgrid checkbox grid (Focus Area Limit): title and footer lines, a subtitle naming the area under
            the cursor, icons in 7 columns (82 px pitch) with a checkbox above each, 2 rows visible
            (115 px pitch), OK/Cancel under the grid; the cursor is an 80x102 orange cell or a button
  tiles     the Main tab's tile grid (4 columns x 5 rows, lines at x 261/386/511, y 119/196/273/350;
            in Movie mode Main1 has two-column tiles above two rows of four, Main2 three rows only):
            tiles open items directly (one is Format), so nothing but Down/Up/Left/Right is pressed
            here; the orange tile (1-2 cells wide) is the cursor; Down cycles the tiles, then moves on
  helppop   the Help (trash) button's popup over a menu page: framed panel (x 320-631, y 114-348) with
            "Add to My Menu" and "In-Camera Guide" (52 px pitch from y 123). Its orange bar once read
            as a menu row (2026-10-28): Enter there could add the item to My Menu, so it is checked
            before menu pages and the walker reads the highlighted entry before any Enter
  guide     In-Camera Guide text: the item name in orange at the top left, a description, ● OK in the
            footer (OK only closes it)
  dialog    item dialog: light divider at x 112, icon carousel at x 20-105 (the selected option is
            always the centre slot, empty slots above/below mean the start/end of the list)
  list      radio-button list popup: framed panel (1-px lines at x 64/577, y 9/470) over the dimmed
            menu, up to 6 rows; the orange bar is the cursor, the radio with an orange centre is the
            value currently saved; a scrollbar (x 564) on long lists gives the window position
  picker    function picker (Custom Key, Fn Menu Settings and My Dial slots): a menu-like page with a
            grey title bar (title, n/N), colour tabs at x 0-48 (52 px pitch from y 46), group names
            at x 55-335 (53 px pitch from y 48) and the options in a lighter panel at x 340-636 (53 px
            pitch from y 48, up to 7, radio at x 358, orange bar x 339-635). The saved function's
            radio has an orange centre. Down runs through every page; Enter assigns
  table     a grid of setting cells over a dark breadcrumb bar (Image Quality Settings' SLOT 1/2,
            My Dial Settings, Custom Key's Dial/Wheel page): the cursor is an orange cell (44-62 px
            tall, 56-200 wide, or as wide as its column: Image Quality Settings with one slot has one
            336 px column, its edges carried on by the grid's lines) or an orange button under the grid
            (OK, Rec. Media Settings); Enter on a cell opens its own list or picker, the grid's OK
            applies, MENU leaves it
  keyset    Custom Key/Dial Set. (and Playback's Custom Key Setting, three tabs): page tabs as icons at
            x 0-54 (63 px pitch from y 46), key rows
            (orange bar x 64-363, 52 px pitch from y 110) beside a drawing of the body. The cursor is
            an orange tab box (Enter goes into the keys), a key row (Enter opens the picker) or, on
            the Dial/Wheel page, a grid cell
  fnmenu    Fn Menu Settings: two sections (Still, Movie) of 2 x 6 icon tiles (107 px pitch, tops at
            y 110/171/298/359); the orange tile is the slot under the cursor, its function named in
            orange at the top right; Enter opens the picker
  notice    framed message (1-px lines at x 30/609), usually with an orange OK button; some have none
            ("Connected to Remote Shooting. Cannot be executed.")
  shooting  the shooting screen: the battery icon at top right (the readouts along the bottom vary
            with the display mode and the source; the OSD leaves shutter/aperture/ISO out)
  unknown   anything else: the walker backs out and flags it (fail closed)

Outlines: the boxes round the controls are touch targets, and with Touch Operation Off the camera leaves
them out (kit2_review_list, 2026-11-08: the footer's buttons, the ▲/▼ boxes of a number field, the side
list's ↩ box, the WB grid's arrow boxes, a slider's − and + boxes and a dialog's › box all bare). The glyph inside sits on the same
pixels either way, so a control counts with its box, or as its glyph alone: solid, in its place, and
nothing else lit round it. Those readings, and a table cell as wide as its column, come after the old ones:
classify tries a screen with the boxes alone first and takes the glyphs alone only when that reads unknown,
and a cell test that matched before still decides the focus. So a screen the old rules placed keeps its kind,
with one exception: a table read by its low button alone becomes a side list when the glyphs alone read one
(a side list's bar on the bottom row is button-sized), and never anything else (review, 2026-11-08).
"""
import dataclasses
import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .frames import Frame

# picture cells two readings of one screen may differ by: live-view noise flipped 1 cell (ISO carousel
# revisited over HDMI), while the closest genuinely different screens differ by 4 (twin) or 6 (live)
SAME_TOL = 2

# --- measured layout (canonical 640x480) ---------------------------------------------------
MENU_ROW_TOP, MENU_ROW_PITCH = 45, 53          # first menu row's top edge, row height
DIALOG_SLOTS = [(55, 105), (120, 170), (185, 240), (250, 305), (315, 370)]   # icon carousel bands
CENTRE = 2                                      # index of the selected slot
# glyph regions: (x0, y0, x1, y1)
GLYPHS = {
    "up": (44, 26, 68, 46),            # ▲ more options above
    "down": (44, 378, 68, 398),        # ▼ more options below
    "side_left": (0, 195, 20, 230),    # ‹ at the selected option: Left/Right move a second axis
    "side_right": (89, 195, 110, 230),
    "strip_left": (132, 340, 158, 375),   # ‹ › around a value strip under the title
    "strip_right": (597, 340, 623, 375),
}
SUB_BOX = (125, 176, 185, 250)         # › box: Right opens a sub-panel
BATTERY = (556, 0, 640, 40)            # shooting screen: battery icon (template = its left end, no digits)
# held vertically the camera turns the shooting screen on HDMI too (2026-10-30): grip down puts the
# battery at the top left, read bottom to top; grip up at the bottom right (each template cut from
# the camera's own frame: turning the grip-down one round scored only 0.84)
# the viewfinder's shooting screen (the finder in use, the eye sensor covered and the monitor folded in: the SDK's
# display image is the finder's layout then) draws a smaller battery further right and higher; its template is that icon's
# left end, its first 8 columns, cut from the camera's own frame (kit2_pass2 239508, 2026-11-11): the percentage starts
# right after them, and a 10-column cut scored 0.834 where the battery read less than 100. Measured 2026-11-11: the 139
# finder shooting frames saved (kit2_pass2, kit2_hdmi_watch, vf_bright, vf_bright2, vf_bright3, vf_map, dist_map; the
# battery at 100 and lower) all score 0.9995 or more; the other 240,000 frames of those runs at most 0.532, and a random
# 20,000 of the other runs' frames at most 0.479, none of them changing kind. Seen in the Level-gauge mode and in a mode with no
# gauge, always with the USB power plug drawn beside the battery; never seen in Histogram, in No Disp. Info (which may
# draw no battery and read "unknown"), with a Viewfinder Magnifi. other than Standard, or on battery power without the
# plug. It is read with the turned ones, as a battery in another place
BATTERY_V = {"battery_gripdown": (5, 56, 33, 66), "battery_gripup": (607, 414, 635, 424),
             "battery_finder": (588, 0, 596, 26)}
LIST_ROW_TOP, LIST_ROW_PITCH, LIST_ROWS = 95, 50, 6   # list popup rows (orange bar 48 px tall)
LIST_RADIO_X = 102                     # radio circle centre x; centre y = row top + 23
LIST_SCROLL = (563, 568, 95, 394)      # scrollbar x0, x1, track y0, y1: thumb grey ~221 on track ~102
# White Balance arrow boxes, by the edges measured on the camera's frames: (axis, edge, edge, from, to).
# "h": light rows at y=edge (and +1) across x from..to; "v": light columns at x=edge across y from..to
WB_ARROWS = {"up": ("h", 118, 170, 457, 498), "down": ("h", 355, 407, 457, 498),
             "left": ("v", 342, 394, 244, 284), "right": ("v", 559, 611, 244, 284)}
WB_GRID = (403, 180, 553, 347)         # the colour grid
GRID_X0, GRID_DX, GRID_Y0, GRID_DY = 61, 82, 135, 115   # Focus Area Limit: first checkbox, pitches
TILE_COLS = [137, 261, 386, 511, 636]  # Main tab tile grid edges
TILE_ROWS = [45, 119, 196, 273, 350, 425]
HELP_POP = (320, 114, 631, 348)        # Help popup frame: x0, y0, x1, y1
HELP_ROW_TOP, HELP_ROW_PITCH = 123, 52  # its entries
SIDE_ROW_TOP, SIDE_ROW_PITCH = 86, 50   # Picture Profile side list rows
SIDE_SCROLL = (607, 86, 383)           # side list scrollbar x, track y0, y1: thumb grey ~85 on track ~51
TRACKS = {"list": (LIST_SCROLL[2], LIST_SCROLL[3]), "sidelist": (SIDE_SCROLL[1], SIDE_SCROLL[2])}
# Creative Look strip cell edges (x): cell 0 is the Look itself (ST, PT...), drawn at x 14-91 only while
# it is selected; cells 1-8 are the parameters, Contrast to Clarity
LOOK_CELLS = [14, 92, 162, 232, 302, 372, 442, 504, 566, 628]
LOOK_MARKER = (550, 578, 80, 260)      # the scale's orange ▶: x0, x1, y0, y1
LOOK_TICKS = (586, 600, 85, 255)       # its tick marks, between the ▶ and the end numbers: x0, x1, y0, y1
LOOK_TICK_ENDS = (99, 243)             # y of the top and bottom ticks, beside the end numbers
PICK_ROW_TOP, PICK_ROW_PITCH, PICK_ROWS = 48, 53, 7    # function picker options (right panel)
PICK_RADIO_X = 358
PICK_TAB_TOP, PICK_TAB_PITCH = 46, 52  # its tabs
KEY_TAB_TOP, KEY_TAB_PITCH = 46, 63    # Custom Key/Dial Set.: page tabs (icons at x 0-54)
KEY_ROW_TOP, KEY_ROW_PITCH = 110, 52   # its key rows
FN_TILE_DX, FN_TILE_ROWS = 107, [110, 171, 298, 359]  # Fn Menu Settings tiles: Still upper/lower, Movie upper/lower


@dataclass
class Screen:
    kind: str
    features: dict = field(default_factory=dict)
    glyphs: dict = field(default_factory=dict)      # dialog: name -> present
    slots: list = field(default_factory=list)       # dialog: per carousel slot, "empty" | "icon" | "selected"
    bar: tuple | None = None                        # menu: (y0, y1) of the orange row bar
    row: int | None = None                          # menu: row slot of the bar on its page
    group: int | None = None                        # menu: visible slot of the current group
    focus: str | None = None                        # menu: "rows" | "groups"
    field: int | None = None                        # fields/look: index of the active field or cell
    pitch: int | None = None                        # menu/submenu: row height (53, or 61 on some submenus)
    rows: list = dataclasses.field(default_factory=list)   # menu/submenu: (top, bottom) of each row
    boxes: list = dataclasses.field(default_factory=list)  # fields: (x0, x1) of each field
    marker: int | None = None                       # look: y of the value marker; slider: its x
    ticks: int | None = None                        # look: the scale's tick marks counted (_look_ticks)
    count: int | None = None                        # list: options visible
    current: int | None = None                      # list: slot of the saved value (orange radio), if visible
    scroll: tuple | None = None                     # list: scrollbar thumb (y0, y1); None = whole list visible
    signature: str = ""
    struct: tuple = ()                              # exact parts of the signature (see same_state)
    bits: np.ndarray = dataclasses.field(default_factory=lambda: np.zeros(0, np.uint8))   # picture cells
    page: np.ndarray = dataclasses.field(default_factory=lambda: np.zeros(0, np.uint8))   # page_bits, unpacked

    @property
    def at_start(self) -> bool | None:
        """The cursor is on the list's first option (dialog carousel or list popup)."""
        if self.kind in TRACKS:
            return self.row == 0 and (self.scroll is None or self.scroll[0] <= TRACKS[self.kind][0] + 1)
        if self.kind != "dialog" or not self.slots:
            return None
        return all(s == "empty" for s in self.slots[:CENTRE])

    @property
    def at_end(self) -> bool | None:
        if self.kind in TRACKS:
            return self.row == self.count - 1 and (self.scroll is None or self.scroll[1] >= TRACKS[self.kind][1] - 1)
        if self.kind != "dialog" or not self.slots:
            return None
        return all(s == "empty" for s in self.slots[CENTRE + 1:])

    @property
    def options_estimate(self) -> int | None:
        """List popup: total options from the scrollbar thumb's length (a budget prior, not a count)."""
        if self.kind not in TRACKS or not self.count:
            return None
        if self.scroll is None:
            return self.count
        track = TRACKS[self.kind][1] - TRACKS[self.kind][0] + 1
        return round(self.count * track / (self.scroll[1] - self.scroll[0] + 1))


# --- pixel helpers -------------------------------------------------------------------------

_PLANES = threading.local()


def _planes(a):
    """Grey, orange mask and saturation of one frame, computed once and shared by every check
    (recomputing them per check made read() ~30 ms; 2026-10-28). Each thread keeps its own last frame's:
    kit/pass1_labels.py reads frames on eight threads, and one shared set handed one frame another's orange."""
    got = getattr(_PLANES, "last", None)
    if got is None or got["a"] is not a:
        r, g, b = (a[..., i].astype(np.int16) for i in range(3))
        got = {"a": a, "grey": (r + g + b).astype(np.float32) / 3,
               "orange": (r > 150) & (g > 30) & (g < 140) & (b < 70) & (r - g > 70),
               "sat": np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)}
        _PLANES.last = got
    return got


def _grey(a):
    return _planes(a)["grey"]


def _orange(a):
    return _planes(a)["orange"]


def _sat(a):
    return _planes(a)["sat"]


def _box(a, box):
    x0, y0, x1, y1 = box
    return a[y0:y1, x0:x1]


_TEMPLATES = {}


def _template(name):
    """Glyph templates cut from the camera's own screens (glyphs/*.png), as float grey."""
    if name not in _TEMPLATES:
        from PIL import Image
        with Image.open(Path(__file__).parent / "glyphs" / f"{name}.png") as im:
            _TEMPLATES[name] = np.asarray(im.convert("L"), np.float32)
    return _TEMPLATES[name]


def _glyph(g, name, box, pad=6) -> float:
    """Best normalised correlation of the glyph template inside its region (+pad)."""
    import cv2
    x0, y0, x1, y1 = box
    sub = g[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].astype(np.float32)
    t = _template(name)
    if sub.shape[0] < t.shape[0] or sub.shape[1] < t.shape[1] or sub.std() < 1:
        return 0.0
    return float(cv2.matchTemplate(sub, t, cv2.TM_CCOEFF_NORMED).max())


def help_glyph(image) -> str | None:
    """The Help (trash) button in a menu page's footer: "help_key" (trash and a list with "?": the
    popup offers Add to My Menu and In-Camera Guide) or "help_only" (trash and "?": the guide alone,
    the Playback tab's rows), else None. Every menu page of both scans shows one of them and no
    shooting frame does (2026-11-01): the Delete key is pressed only where one is drawn."""
    import cv2
    g = np.asarray(image, np.float32)
    if g.ndim == 3:
        g = g[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)      # as PIL's "L", the glyphs' cut
    band = g[415:480, :]
    best, name = 0.0, None
    for n in ("help_key", "help_only"):
        sc = float(cv2.matchTemplate(band, _template(n), cv2.TM_CCOEFF_NORMED).max())
        if sc > best:
            best, name = sc, n
    return name if best > 0.9 else None


def _sig(s, *parts):
    """Set s.signature (exact) and what tolerant matching needs (same_state): s.struct, the parts
    that must match exactly (type tags, cursor position, counts, glyphs...), and s.bits, the
    binarized pictures (packbits uint8 arrays), which may differ by a few cells. Over HDMI, screens
    drawn over live view carry sensor noise even with the lens cap on (up to ~31 levels per pixel,
    more while the ISO dialog previews high ISO), which flips a cell or two at the edges of icons
    and text: the ISO carousel's first options got new signatures on the second visit (2026-10-28)."""
    s.signature = _hash(*parts)
    struct, pics = [], []
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            struct.append(bytes(p))
        elif isinstance(p, np.ndarray) and p.dtype == np.uint8:
            pics.append(p)
        else:
            struct.append(np.asarray(p).tobytes())
    s.struct = tuple(struct)
    s.bits = np.unpackbits(np.concatenate(pics)) if pics else np.zeros(0, np.uint8)


def same_state(a: "Screen", b: "Screen", tol: int = SAME_TOL) -> bool:
    """The same screen state: same type and structure exactly, pictures within `tol` cells."""
    if a is None or b is None or a.kind != b.kind:
        return False
    if a.signature == b.signature:
        return True
    if a.struct != b.struct or a.bits.shape != b.bits.shape:
        return False
    return int(np.count_nonzero(a.bits != b.bits)) <= tol


def same_position(a: "Screen", b: "Screen", tol: int = SAME_TOL) -> bool:
    """The same place in the menu's Down cycle: same_state, or a menu page with the same breadcrumb,
    n/N counter and cursor row whose rows look different. A row greys out or lights up when a card
    goes in or out (Select REC Folder, 2026-10-29); the cursor's path through the rows stays the same."""
    if same_state(a, b, tol):
        return True
    if a is None or b is None or a.kind != b.kind or a.kind not in ("menu", "tiles") or a.row is None \
            or a.row != b.row or a.field != b.field:
        return False
    # the Main tiles show live values (cards' remaining shots, battery): the focused tile and the
    # breadcrumb naming it place them (2026-10-29)
    return a.page.shape == b.page.shape and a.page.size > 0 and int(np.count_nonzero(a.page != b.page)) <= tol


def _hash(*arrays) -> str:
    h = hashlib.sha1()
    for x in arrays:
        h.update(np.ascontiguousarray(x).tobytes())
    return h.hexdigest()[:12]


def _binarize_small(g, box, size=(48, 12), level=120):
    """Coarse binary picture of a region: stable against compression noise and anti-aliasing.
    A cell is set when over a quarter of its pixels are brighter than `level`."""
    sub = (_box(g, box) > level).astype(np.int32)
    h, w = sub.shape
    ys = np.linspace(0, h, min(size[1], h) + 1).astype(int)
    xs = np.linspace(0, w, min(size[0], w) + 1).astype(int)
    sums = np.add.reduceat(np.add.reduceat(sub, ys[:-1], axis=0), xs[:-1], axis=1)
    return np.packbits(sums > 0.25 * np.outer(np.diff(ys), np.diff(xs)))


# --- features ------------------------------------------------------------------------------

def features(a: np.ndarray) -> dict:
    g = _grey(a)
    sat = _sat(a)
    o = _orange(a)
    divider = max(float((g[5:420, x] > 140).mean()) for x in range(110, 115))
    # a notice is framed by 1-px dim grey lines at x 30 and x 609
    # (grey ~68 on OSD frames; thin lines come out ~15-20% dimmer over HDMI)
    frame_l = max(float((g[25:400, x] > 40).mean()) for x in range(28, 33))
    frame_r = max(float((g[25:400, x] > 40).mean()) for x in range(607, 612))
    # a popup panel is framed by 1-px light lines at x 64/577 and y 9/470: grey ~102 on OSD frames,
    # ~85 on HDMI (scaling blurs 1-px lines; 2026-10-28), and the bottom line can be as faint as 70
    # (Color Space list, 2026-10-29); the panel's surroundings are 0
    popup = min(max(float((g[15:465, x] > 50).mean()) for x in (63, 64, 65)),
                max(float((g[15:465, x] > 50).mean()) for x in (576, 577, 578)),
                max(float((g[y, 70:570] > 50).mean()) for y in (8, 9, 10)),
                max(float((g[y, 70:570] > 50).mean()) for y in (469, 470, 471)))
    cell = _cell_box(o)
    field_box = _active_field(o)
    arrows = _arrow_found(g, field_box) if field_box else (None, None)
    slider_boxed = _slider_boxes(g) is not None
    back = _back_box(g)
    wb = _wb_found(g)
    return {
        "divider": round(divider, 3),
        "tab_sat": round(float(sat[45:425, 0:47].mean()), 1),
        # 0.93+ on every shooting screen in the corpus and on HDMI, at most 0.48 on anything else
        "battery": round(_glyph(g, "battery", BATTERY, pad=0), 3),
        # 1.0 on the frames they were cut from, at most 0.65 on 5,000 saved frames of every type
        "battery_v": round(max(_glyph(g, name, box, pad=4) for name, box in BATTERY_V.items()), 3),
        "ok_button": round(float(o[345:390, 205:435].mean()), 3),
        "notice_frame": round(min(frame_l, frame_r), 3),
        "menu_bar_rows": int(((o[:, 140:636].sum(axis=1)) > 250).sum()),
        "popup_frame": round(popup, 3),
        # menu pages have a black breadcrumb bar on top (>= 0.82 dark); live view does not (<= 0.27)
        "top_bar": round(float((g[2:38, :] < 25).mean()), 3),
        "help_frame": round(min(float((g[HELP_POP[1] + 6:HELP_POP[3] - 6, x0:x0 + 2] > 70).max(axis=1).mean())
                                for x0 in (HELP_POP[0], HELP_POP[2] - 1)), 3),
        "title_orange": int(o[5:42, 30:600].sum()),
        "tile_lines": sum(max(float(((g[50:420, x] > 40) & (g[50:420, x] < 120)).mean()) for x in (c - 2, c - 1, c, c + 1, c + 2)) > 0.5
                          for c in TILE_COLS[1:-1]),
        # the same lines beside the bottom two tile rows only: Movie mode's Main page has two-column
        # tiles above four-column ones, so only the middle line runs the full height (2026-10-30)
        "tile_lines_low": sum(max(float(((g[300:420, x] > 40) & (g[300:420, x] < 120)).mean()) for x in (c - 2, c - 1, c, c + 1, c + 2)) > 0.5
                              for c in TILE_COLS[1:-1]),
        # and beside the top three rows only: Movie mode's second Main page stops half way down
        "tile_lines_top": sum(max(float(((g[50:230, x] > 40) & (g[50:230, x] < 120)).mean()) for x in (c - 2, c - 1, c, c + 1, c + 2)) > 0.5
                              for c in TILE_COLS[1:-1]),
        "left_dark": round(float((g[45:420, 2:50] < 20).mean()), 3),
        # the same column below grey 40: S-Log3 lifts the capped lens's noise into the see-through
        # menu background (left_dark 0.76, this 0.99 on a submenu); menu pages stay under 0.6, Custom
        # Key Setting's three tabs at 0.80, submenus over 0.95 (2026-10-29)
        "dark_col": round(float((g[60:420, 0:50] < 40).mean()), 3),
        "title_line": _neutral_line(a, g, range(51, 56)),
        "footer_line": _neutral_line(a, g, range(424, 429)),
        "field_arrows": sum(k is not None for k in arrows),
        "field_arrows_boxed": sum(k == "box" for k in arrows),
        "checkboxes": len(_checkboxes(g, o)),
        "grid_columns": len({round((x - GRID_X0) / GRID_DX) for x, *_ in _grid_boxes(g, o)}),
        "slider_buttons": slider_boxed or _bare_signs(g) is not None,
        "slider_buttons_boxed": slider_boxed,
        # ↩ box at the left (Creative Look, Picture Profile lists) and an orange bar at x 303-597
        "back_box": back is not None,
        "back_box_boxed": back == "box",
        # a long label ("ITU709 Matrix") covers most of the bar: its right end is orange whatever the text
        "side_bar": bool(((o[:, 305:595].mean(axis=1)) > 0.6).sum() > 20 or
                         ((o[:, 560:595].mean(axis=1)) > 0.9).sum() > 30),
        "wb_arrows": sum(k is not None for k in wb.values()),
        "wb_arrows_boxed": sum(k == "box" for k in wb.values()),
        "wb_grid_sat": round(float(sat[WB_GRID[1] + 10:WB_GRID[3] - 10, WB_GRID[0] + 10:WB_GRID[2] - 10].mean()), 1),
        # Creative Look strip frame at y 350 and 402 (the orange cell counts as drawn)
        "look_strip": round(min(float(((g[y, 100:620] > 150) | o[y, 100:620]).mean()) for y in (350, 402)), 3),
        "sub_bar": _sub_bar(o),
        "radios": len(_radios(g, o)),
        "pick_panel": _pick_panel(g, o),
        "icon_tabs": len(_icon_tabs(g, o)),
        # Custom Key/Dial Set.'s icon column ends at x 52, its keys start at x 64: nothing light between
        # (a table's row labels run across: Image Quality Settings 0.11, My Dial 0.15)
        "icon_gap": round(float((g[50:420, 52:62] > 120).mean()), 3),
        # its unselected tabs are plain grey icons; menu tabs are tinted (sat 22-43) even unselected
        "grey_tabs": sum(float(sat[KEY_TAB_TOP + KEY_TAB_PITCH * i + 8:KEY_TAB_TOP + KEY_TAB_PITCH * i + 55, 2:52].mean()) < 8
                         for i in range(6)),
        "cell_box": cell,
        "cell_grid": _grid_column(g, cell),
    }


def _pick_panel(g, o) -> bool:
    """The function picker's option panel: a strip at x 341-344 (left of the radios) evenly lighter
    (~34) than the group column's right end (~17); the orange bar is left out."""
    strip, keep = g[60:420, 341:345], ~o[60:420, 341:345]
    if keep.sum() < 400:
        return False
    panel, left = float(np.median(strip[keep])), float(np.median(g[60:420, 331:337]))
    return 22 <= panel <= 90 and panel - left >= 8 and float((np.abs(strip[keep] - panel) < 6).mean()) > 0.9


def _icon_tabs(g, o) -> list:
    """Icon bands (more than 10 px tall) in the column at x 4-50, top to bottom: Custom Key/Dial Set.
    draws its six page tabs there, dim (grey ~60-150) except the selected one."""
    col = ((g[:, 4:50] > 50) | o[:, 4:50]).sum(axis=1)
    bands = []
    for y in range(50, 425):
        if col[y] > 3:
            if bands and y - bands[-1][1] <= 6:
                bands[-1][1] = y
            else:
                bands.append([y, y])
    return [(t, b) for t, b in bands if b - t > 10]


def _cell_box(o):
    """The largest orange-filled box 44-62 px tall under the title (x, y, w, h), or None: a table's
    cell or button, an Fn Menu tile, a key row."""
    import cv2
    m = o.astype(np.uint8)
    m[:45] = 0
    m[424:] = 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    best = None
    for i, (x, y, w, h, area) in enumerate(st[1:], 1):
        if not (44 <= h <= 62 and 40 <= w <= 600) or (best is not None and area <= best[4]):
            continue
        fill = area / (w * h)
        if 0.4 < fill <= 0.6:
            # two lines of text in a small cell ("Av/Tv [M]" on My Dial, 2026-10-29): the box's
            # outline, holes and all, still fills its bounding box; a big icon that reaches the edge
            # (Fn Menu's Recognition Target tile, 2026-10-29) still leaves all four edges orange
            sub = lab[y:y + h, x:x + w] == i
            cs, _ = cv2.findContours(sub.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            outline = max((cv2.contourArea(c) for c in cs), default=0) / (w * h)
            edges = min(sub[0].mean(), sub[-1].mean(), sub[:, 0].mean(), sub[:, -1].mean())
            fill = 1.0 if outline > 0.9 or edges >= 0.85 else 0
        if fill > 0.6:
            best = (int(x), int(y), int(w), int(h), int(area))
    return best and best[:4]


def _is_keyset(f) -> bool:
    """Custom Key/Dial Set. (six tabs) and Playback's Custom Key Setting (three): grey icon tabs (one
    orange box while the tabs have the focus, which makes the column colourful enough for a menu
    page), clear of the key rows, no title line."""
    return (f["top_bar"] > 0.6 and f["title_line"] < 0.5 and f["icon_tabs"] >= 3 and f["icon_gap"] < 0.02
            and f["grey_tabs"] >= 5)


def _table_focus(f) -> str | None:
    """A table's cursor: "cell" (a cell clear of the left column, or one of Mode Dial Control Set's
    three row bars at x 64, which have no icon tabs beside them) or "button" (low on the screen; that
    screen's Set All buttons have the rows' shape, from y ~296). None when it is neither."""
    if not f["cell_box"]:
        return None
    x, y, w, h = f["cell_box"]
    if 56 <= w <= 200 and x >= 100:
        return "cell"
    if abs(x - 64) <= 4 and 280 <= w <= 310 and f["icon_tabs"] < 3:
        return "cell" if y < 280 else "button"
    if y >= 330 and 200 <= w <= 330:
        return "button"
    # last, so it never overrides a test above: a cell as wide as its column, the grid's lines carrying its edges
    # on (Image Quality Settings with one slot draws one 336 px column, 2026-11-08); a side list's bar (294 px)
    # has no lines under it
    if w <= 400 and x >= 100 and f.get("cell_grid"):
        return "cell"
    return None


def _table_cursor(f) -> bool:
    return _table_focus(f) is not None


def _fn_tile(f) -> tuple | None:
    """(tile row, column) of an Fn Menu Settings tile cursor, or None."""
    if not f["cell_box"]:
        return None
    x, y, w, h = f["cell_box"]
    c = round(x / FN_TILE_DX)
    r = next((i for i, t in enumerate(FN_TILE_ROWS) if abs(y - t) <= 6), None)
    if r is None or not 0 <= c < 6 or abs(x - c * FN_TILE_DX) > 5 or not 96 <= w <= 112 or not 50 <= h <= 62:
        return None
    return r, c


def _neutral_line(a, g, ys) -> float:
    """Best share of a thin grey (not orange) line across the screen at one of the rows `ys`."""
    sat = _sat(a)
    return round(max(float(((g[y, 5:635] > 50) & (g[y, 5:635] < 160) & (sat[y, 5:635] < 25)).mean())
                     for y in ys), 3)


def _active_field(o):
    """The number form's active field: an orange-filled box 40-70 px tall, 50-260 wide (x, y, w, h)."""
    import cv2
    m = o.astype(np.uint8)
    m[:58] = 0
    m[420:] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    best = None
    for x, y, w, h, area in st[1:]:
        if 40 <= h <= 70 and 50 <= w <= 260 and area / (w * h) > 0.6 and (best is None or area > best[4]):
            best = (int(x), int(y), int(w), int(h), int(area))
    return best and best[:4]


def _arrow_boxes(g, box) -> tuple[bool, bool]:
    """Whether the ▲ and the ▼ are drawn over/under the active field, boxed or alone (_arrow_found). A number
    field can always move at least one way; checkbox lists with OK/Cancel focused and the My Dial table have a
    field-sized orange box but never these arrows (features counts them as field_arrows)."""
    return tuple(k is not None for k in _arrow_found(g, box))


def _arrow_found(g, box) -> tuple:
    """How the ▲ and the ▼ over/under the active field are drawn: "box", "lone" or None each.
    ▲/▼ boxes are centred on the active field and can be narrower than it (ISO Range Limit).
    A box only counts with its triangle inside: the Fn Menu Settings grid has field-sized cells
    above and below its orange slot, holding icons (2026-10-28). Without outlines (module docstring)
    the triangle stands alone on the same pixels: ISO Range Limit at ISO 50 drew one bare ▼ (2026-11-08)."""
    x, y, w, h = box
    cx = min(max(x + w // 2, 30), 609)     # a field at the screen edge must not slice past it

    def edge(y0, y1):
        return any(((g[yy, cx - 30:cx + 30] > 60) & (g[yy, cx - 30:cx + 30] < 200)).mean() > 0.9
                   for yy in range(max(58, y0), min(420, y1)))

    def arrow(y0, y1, up):
        if edge(y0, y1) and _triangle(g, cx, y0, y1, up=up):
            return "box"
        if _lone_triangle(g, (cx - 16, max(58, y0), cx + 17, min(420, y1)), "up" if up else "down"):
            return "lone"
        return None
    return arrow(y - 80, y - 4, True), arrow(y + h + 4, y + h + 80, False)


def _triangle(g, cx, y0, y1, up: bool) -> bool:
    """A small light ▲ (rows widen downwards) or ▼ (rows narrow) centred near x=cx within y0..y1."""
    import cv2
    y0, y1 = max(0, y0), min(480, y1)
    m = (g[y0:y1, cx - 16:cx + 17] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    for bx, by, bw, bh, _area in st[1:]:
        if 7 <= bw <= 22 and 5 <= bh <= 16 and abs(bx + bw / 2 - 16) <= 6:
            widths = (m[by:by + bh, bx:bx + bw] > 0).sum(axis=1)
            if not up:
                widths = widths[::-1]
            if widths[0] <= widths[-1] - 4 and np.all(np.diff(widths) >= -1):
                return True
    return False


def _lone_triangle(g, region, point: str, alone: bool = True) -> bool:
    """A small light triangle pointing `point` (up, down, left or right) inside region (x0, y0, x1, y1),
    drawn on its own, as the camera draws a control's glyph when it leaves the outlines out (module
    docstring): solid (every line across it one run, widening steadily from the tip), centred in the
    region across its axis, and nothing else lit (grey > 60) within 10 px of it. Text does not pass: a
    letter has neighbours, holes or strokes that stop widening. alone=False leaves the last test out, for a
    glyph beside other ink by design (a slider's ◂ ▸ beside its value)."""
    import cv2
    x0, y0, x1, y1 = max(0, region[0]), max(0, region[1]), min(640, region[2]), min(480, region[3])
    if x1 - x0 < 8 or y1 - y0 < 8:
        return False
    m = (g[y0:y1, x0:x1] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    vertical = point in ("up", "down")
    for bx, by, bw, bh, _area in st[1:]:
        across, along = (bw, bh) if vertical else (bh, bw)
        if not (7 <= across <= 22 and 5 <= along <= 16):
            continue
        centre, span = (bx + bw / 2, x1 - x0) if vertical else (by + bh / 2, y1 - y0)
        if abs(centre - span / 2) > 6:
            continue
        t = m[by:by + bh, bx:bx + bw] > 0
        t = {"up": t, "down": t[::-1], "left": t.T, "right": t[:, ::-1].T}[point]   # tip first
        widths = t.sum(axis=1)
        runs = [int(np.flatnonzero(r)[-1] - np.flatnonzero(r)[0]) + 1 if r.any() else 0 for r in t]
        if not (widths[0] <= widths[-1] - 4 and np.all(np.diff(widths) >= -1) and np.array_equal(widths, runs)):
            continue
        if not alone or _alone(g, (x0 + bx, y0 + by, bw, bh)):
            return True
    return False


def _alone(g, box, pad: int = 10) -> bool:
    """Nothing lit (grey > 60) within `pad` px of the glyph's box (x, y, w, h), its own 2 px fringe left out:
    a control's glyph drawn without its outline stands alone, a letter or an icon part does not."""
    x, y, w, h = box
    X0, Y0 = max(0, x - pad), max(0, y - pad)
    near = g[Y0:y + h + pad, X0:x + w + pad] > 60
    near[max(0, y - 2) - Y0:y + h + 2 - Y0, max(0, x - 2) - X0:x + w + 2 - X0] = False
    return not near.any()


def _back_box(g) -> str | None:
    """The ↩ at the left of a Picture Profile side list or the Creative Look panel: "box" for its box (light
    edges at x 19 and 81, y 185-240), "lone" for the ↩ alone on the same pixels without outlines (module
    docstring): one light glyph about 26 px square centred near (50, 212), a stroke (a quarter of its box lit),
    and nothing else lit (grey > 60) within 12 px of it (PP1 > Black Level, 2026-11-08). None for neither."""
    if min(float((g[185:240, x] > 120).mean()) for x in (19, 81)) > 0.9:
        return "box"
    import cv2
    x0, y0, x1, y1 = 0, 150, 110, 280
    m = (g[y0:y1, x0:x1] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    glyphs = [r for r in st[1:] if r[4] >= 10]
    if len(glyphs) != 1:
        return None
    bx, by, bw, bh, area = (int(v) for v in glyphs[0])
    if not (20 <= bw <= 32 and 20 <= bh <= 33 and abs(bx + bw / 2 - 50) <= 5 and abs(y0 + by + bh / 2 - 212) <= 5
            and 0.15 <= area / (bw * bh) <= 0.4):
        return None
    return "lone" if _alone(g, (x0 + bx, y0 + by, bw, bh), pad=12) else None


def _grid_column(g, box) -> bool:
    """The orange box is one column of a grid: on each side a thin grey line (grey 40-200 down 90 % of the run,
    in any of the columns x-4..x on the left and x+w-1..x+w+3 on the right) carries the box's edge on over the
    neighbouring row, at least 40 px of it (y 45-424 only). Below the box is tried first, then above, for any
    box: one on the bottom row has only the lines above it. Image Quality Settings with one slot draws one
    column 336 px wide (2026-11-08); a side list's bar, a submenu's or a checklist's row bar has nothing under
    or over its ends."""
    if not box:
        return False
    x, y, w, h = box

    def line(xs, y0, y1):
        return any(float(((g[y0:y1, xx] > 40) & (g[y0:y1, xx] < 200)).mean()) > 0.9 for xx in xs if 0 <= xx < 640)
    for y0, y1 in ((y + h + 2, y + h + 48), (y - 48, y - 2)):
        y0, y1 = max(45, y0), min(424, y1)
        if y1 - y0 >= 40 and line(range(x - 4, x + 1), y0, y1) and line(range(x + w - 1, x + w + 4), y0, y1):
            return True
    return False


def _checkboxes(g, o, x0=0) -> list:
    """Checkbox squares near the left edge (or near x0, for a second column), top to bottom:
    [(x, y, w, h, ticked)]. Solid light grey (~187) with a darker border; a tick is orange inside
    the square."""
    import cv2
    m = ((g > 120) | o).astype(np.uint8)
    m[:56] = 0
    m[424:] = 0
    m[:, :x0] = 0
    m[:, x0 + 70:] = 0
    n, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    out = []
    for x, y, w, h, area in st[1:]:
        if 22 <= w <= 34 and 22 <= h <= 34 and abs(w - h) <= 5 and area / (w * h) > 0.8 and x < x0 + 45:
            out.append((int(x), int(y), int(w), int(h), bool(o[y + 3:y + h - 3, x + 3:x + w - 3].sum() > 30)))
    return sorted(out, key=lambda t: t[1])


def _slider_buttons(g):
    """x of the slider's − box (_slider_boxes), else of the − alone (_bare_signs), else None."""
    x = _slider_boxes(g)
    if x is not None:
        return x
    signs = _bare_signs(g)
    return None if signs is None else signs[0]


def _slider_boxes(g):
    """x of the slider's − box when it and the mirrored + box are both drawn: vertical light edges
    92 px apart (x, x+90) over y 320-375, mirrored about x 320."""
    lit = (g[320:375] > 120).mean(axis=0) > 0.9

    def edge(x):      # within ±1 px: over HDMI the mirrored edge can land one pixel off (2026-10-28)
        return bool(lit[max(0, x - 1):min(640, x + 2)].any())
    for x in range(0, 230):
        if lit[x] and edge(x + 90) and edge(min(639, 640 - x - 2)) and edge(640 - x - 92):
            return x
    return None


def _bare_signs(g):
    """The box (x, y, w, h) of the slider's − when it and the + stand alone, or None (module docstring): a solid
    bar 18-36 px wide and 2-7 tall at the left, a + of the same size at the right (its middle row and column lit
    end to end, its corners dark), on one line (centres within 3 px) mirrored about x 320, and nothing else lit
    round either (AF Transition Speed, 2026-11-08). The sliders drawn with 64 px boxes (Framing Tracking Speed,
    the volumes) pass too: their box edges are further than 10 px from the signs."""
    import cv2
    y0 = 290
    m = (g[y0:410] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    minus, plus = [], []
    for x, y, w, h, area in (tuple(int(v) for v in r) for r in st[1:]):
        if not 18 <= w <= 36:
            continue
        if 2 <= h <= 7 and area >= 0.85 * w * h and x + w <= 230:
            minus.append((x, y0 + y, w, h))
        elif 18 <= h <= 36 and abs(w - h) <= 5 and x >= 410 and 0.15 <= area / (w * h) <= 0.45:
            t = m[y:y + h, x:x + w] > 0
            if t[h // 2].all() and t[:, w // 2].all() and not (t[:4, :4].any() or t[:4, -4:].any()
                                                                or t[-4:, :4].any() or t[-4:, -4:].any()):
                plus.append((x, y0 + y, w, h))
    for mb in minus:
        for pb in plus:
            if abs(mb[0] + mb[2] / 2 + pb[0] + pb[2] / 2 - 640) <= 4 and abs(mb[1] + mb[3] / 2 - pb[1] - pb[3] / 2) <= 3 \
                    and _alone(g, mb) and _alone(g, pb):
                return mb
    return None


def _wb_found(g) -> dict:
    """How each White Balance arrow is drawn, {up, down, left, right: "box" | "lone" | None}: "box" with both of
    its box's measured edges, "lone" for its triangle alone inside where the box would be, without outlines
    (module docstring; White Balance Adjustment, 2026-11-08). Lone arrows count only two or more together:
    every grid position leaves at least two (a corner keeps ▷ and ▽), while S&Q's Frame Rate Settings put one
    field ▲ alone in the up box's place (kit2_pass2 122583, review 2026-11-08)."""
    def found(spec, point):
        axis, e0, e1, a, b = spec
        if axis == "h":
            if min(max(float((g[y, a:b] > 150).mean()) for y in (e, e + 1)) for e in (e0, e1)) > 0.8:
                return "box"
            return "lone" if _lone_triangle(g, (a, e0 + 3, b, e1 - 1), point) else None
        if min(max(float((g[a:b, x] > 150).mean()) for x in (e, e + 1)) for e in (e0, e1)) > 0.8:
            return "box"
        return "lone" if _lone_triangle(g, (e0 + 3, a, e1 - 1, b), point) else None
    out = {k: found(spec, k) for k, spec in WB_ARROWS.items()}
    if sum(v == "lone" for v in out.values()) < 2:
        out = {k: None if v == "lone" else v for k, v in out.items()}
    return out


def _grid_boxes(g, o) -> list:
    """Checkbox squares on the Focus Area Limit grid (x >= 50, y 120-345): [(x, y, w, h, ticked)]."""
    import cv2
    m = ((g > 120) | o).astype(np.uint8)
    m[:120] = 0
    m[345:] = 0
    m[:, :50] = 0
    m[:, 615:] = 0
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
    out = []
    for x, y, w, h, area in st[1:]:
        if 22 <= w <= 34 and 22 <= h <= 34 and abs(w - h) <= 5 and area / (w * h) > 0.8:
            out.append((int(x), int(y), int(w), int(h), bool(o[y + 3:y + h - 3, x + 3:x + w - 3].sum() > 30)))
    return sorted(out, key=lambda t: (t[1], t[0]))


def _sub_bar(o) -> float:
    """How much of x 56-66 is orange near the top of the row bar (above the label, which starts at
    x 60): submenu bars start at x 55, menu-page bars at x 138."""
    rows = [y for y in range(45, 425) if o[y, 140:636].mean() > 0.6]
    return round(float(o[rows[min(3, len(rows) - 1)], 56:66].mean()), 3) if rows else 0.0


def _radios(g, o) -> dict:
    """List popup radio circles: {slot: saved?}. A plain radio has ~250 light pixels around a grey
    centre; the saved value's has a light ring (~120 px) round an orange centre, on the cursor row too."""
    out = {}
    for i in range(LIST_ROWS):
        cy, cx = LIST_ROW_TOP + LIST_ROW_PITCH * i + 23, LIST_RADIO_X
        if (g[cy - 8:cy + 9, cx - 10:cx + 11] > 150).sum() > 80:
            out[i] = bool(o[cy - 3:cy + 4, cx - 4:cx + 5].sum() > 30)
    return out


# the readings the glyphs alone add (module docstring, "Outlines"), each beside the one the boxes alone give
_ALONE_KEYS = {"field_arrows": "field_arrows_boxed", "slider_buttons": "slider_buttons_boxed",
               "back_box": "back_box_boxed", "wb_arrows": "wb_arrows_boxed"}


def classify(f: dict) -> str:
    """The screen's type. First as the boxes alone read it, then, only if that is unknown, with the glyphs alone
    and the column-wide table cell too: the first rule that matches wins, so a reading that only adds could
    otherwise move a screen the old rules placed to an earlier rule (review, 2026-11-08). So every kind the boxes
    alone give is kept, but for one: a table read by its low button alone becomes a side list when the second
    reading says side list, and stays a table otherwise. That table rule is the catch-all the side list is
    checked before, because a side list's bar on the bottom row is button-sized; without outlines the side
    list's ↩ is only found alone (PP1 > Black Level at -10, 2026-11-08). Real tables read by their buttons (My
    Dial's and Image Quality Settings' OK, Rec. Media Settings, Mode Dial Control Set's Set All) can become
    nothing else."""
    boxed = {**f, **{k: f[b] for k, b in _ALONE_KEYS.items() if b in f}, "cell_grid": False}
    kind = _classify(boxed)
    if kind == "unknown":
        return _classify(f)
    if kind == "table" and _table_focus(boxed) == "button" and _classify(f) == "sidelist":
        return "sidelist"
    return kind


def _classify(f: dict) -> str:
    # the turned shooting screen first: grip up its readouts fill the left column, where the Custom
    # Key reader looks for its page tabs (2026-10-30)
    # and the viewfinder's shooting screen, its battery in a place of its own (BATTERY_V, 2026-11-11)
    if f["battery_v"] > 0.85:
        return "shooting"
    # the battery before a notice's frame lines: Focus Map tints live view red, which drew both
    # frame lines (0.94) on the shooting screen; on 8,000 saved frames only those had the battery
    # (above 0.7) without reading as the shooting screen (2026-10-30)
    if f["battery"] > 0.7:
        return "shooting"
    # Creative Look previewing SH (Soft Highkey) in Movie lifts the black behind it to grey, which draws
    # a notice's frame lines (0.94-0.96); the carousel's divider or the look's parameter strip says
    # otherwise. Of the 475 frames the runs logged as notices, only those two have either (2026-11-02)
    if f["notice_frame"] > 0.8 and f["divider"] <= 0.85 and not (f["footer_line"] > 0.9 and f["look_strip"] > 0.9):
        return "notice"
    if f["popup_frame"] > 0.8 and f["radios"] > 0:
        return "list"
    if f["help_frame"] > 0.9 and f["tab_sat"] > 20:          # over a menu page: before "menu"
        return "helppop"
    if f["divider"] > 0.85:
        return "dialog"
    # the Creative Look strip is unmistakable; with its Look cell selected (x 14-91, orange, with ⌃)
    # the left column is colourful enough to pass as menu tabs (IN look, 2026-10-28)
    if f["footer_line"] > 0.9 and f["look_strip"] > 0.9:
        return "look"
    # colour tabs like a menu page, but a grey title bar and the lighter option panel
    if f["tab_sat"] > 20 and f["top_bar"] < 0.5 and f["pick_panel"]:
        return "picker"
    if f["tab_sat"] > 20 and f["top_bar"] > 0.6 and f["dark_col"] < 0.9 and \
            (f["tile_lines"] >= 3 or (f["tile_lines"] >= 1 and f["tile_lines_low"] >= 3) or f["tile_lines_top"] >= 3):
        return "tiles"
    if _is_keyset(f):
        return "keyset"
    # live view in the left column is colourful too; noise lifted by S-Log3 is colourful but dark
    if f["tab_sat"] > 20 and f["top_bar"] > 0.6 and f["dark_col"] < 0.9:
        # Fn Menu Settings' orange tile in the first column makes the left edge colourful
        if f["title_line"] > 0.9 and f["footer_line"] > 0.9 and _fn_tile(f):
            return "fnmenu"
        return "menu"
    if f["sub_bar"] > 0.8 and (f["left_dark"] > 0.9 or f["dark_col"] > 0.95):
        return "submenu"
    if f["title_line"] > 0.9 and f["footer_line"] > 0.9 and _fn_tile(f):
        return "fnmenu"
    if f["title_line"] > 0.9 and f["footer_line"] > 0.9 and f["field_arrows"] > 0:
        return "fields"
    if f["title_line"] > 0.9 and f["footer_line"] > 0.9 and f["checkboxes"] > 0:
        return "checklist"
    if f["title_line"] > 0.9 and f["footer_line"] > 0.9 and f["grid_columns"] >= 3:
        return "checkgrid"
    if f["footer_line"] > 0.9 and f["look_strip"] > 0.9:
        return "look"
    if f["footer_line"] > 0.45 and f["slider_buttons"]:      # Aspect Marker Level: half a footer line
        return "slider"
    if f["footer_line"] > 0.8 and f["back_box"] and f["side_bar"]:
        return "sidelist"
    # at a corner of the grid only two arrow boxes are left (B7/G7: ▷ and ▽; HDMI 2026-10-28)
    if f["footer_line"] > 0.9 and f["wb_arrows"] >= 1 and f["wb_grid_sat"] > 60:
        return "wbgrid"
    # a short title is a few orange pixels: an option "2" (Fixed Speed STBY's) has 111, a name ~1,600;
    # between 40 and 150 the corpus held only notices, read before this (2026-11-01)
    if f["footer_line"] > 0.9 and f["title_line"] < 0.5 and f["title_orange"] > 40:
        return "guide"
    # after the side list: its bar near the bottom is button-sized
    # Image Quality Settings' Rec. Media Settings button reaches the left edge (x 16), which makes the
    # tab column colourful (2026-10-29): a wide button low on the screen is allowed that
    low_button = _table_focus(f) == "button" and f["cell_box"][1] >= 330
    if (f["tab_sat"] < 8 or (low_button and f["tab_sat"] < 20)) and f["top_bar"] > 0.6 and _table_cursor(f) \
            and f["checkboxes"] == 0 and f["battery"] <= 0.7:
        return "table"
    if f["battery"] > 0.7:
        return "shooting"
    return "unknown"


# --- per type ------------------------------------------------------------------------------

def _dialog(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    lit = np.where(o, 255, g)          # orange text and icons count as ink too
    for name, box in GLYPHS.items():
        s.glyphs[name] = _glyph(g, name, box) > 0.7
    # › box: two tall light edges near x 129 and x 178
    x0, y0, x1, y1 = SUB_BOX
    left = max(float((g[y0 + 7:y1 - 7, x] > 150).mean()) for x in range(x0, x0 + 10))
    right = max(float((g[y0 + 7:y1 - 7, x] > 150).mean()) for x in range(x1 - 12, x1))
    s.glyphs["sub_box"] = min(left, right) > 0.8
    for (t, b) in DIALOG_SLOTS:
        region = (slice(t, b), slice(20, 88))
        if o[region].sum() > 60:
            s.slots.append("selected")
        elif (g[region] > 120).sum() > 40:
            s.slots.append("icon")
        else:
            s.slots.append("empty")
    centre = DIALOG_SLOTS[CENTRE]
    _sig(s, b"dialog",
                        # at twice the old resolution: neighbouring Picture Profile options (PP3/PP4) were
                        # 3-6 cells apart against 1-2 of live-view noise; now 21-35 against 1-2 (2026-10-28)
                        _binarize_small(lit, (20, centre[0], 88, centre[1]), (34, 28)),   # selected icon
                        _binarize_small(lit, (120, 60, 636, 110), (128, 16)),             # orange title line
                        # the body under the title: a second axis changes a value here (Pixel Shift)
                        _binarize_small(lit, (120, 110, 636, 400), (64, 30), 150),
                        np.array([s.glyphs[k] for k in sorted(s.glyphs)]))


def _list(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    radios = _radios(g, o)
    s.count = len(radios)
    s.current = next((i for i, saved in radios.items() if saved), None)
    bar = np.nonzero(o[:, 90:550].sum(axis=1) > 300)[0]
    if len(bar):
        s.bar = (int(bar.min()), int(bar.max()))
        s.row = int(((s.bar[0] + s.bar[1]) / 2 - LIST_ROW_TOP) // LIST_ROW_PITCH)
    x0, x1, t, b = LIST_SCROLL
    col = g[t:b + 1, x0:x1].max(axis=1)
    if (col > 60).mean() > 0.9:                       # a track is drawn: the list is longer than 6 rows
        thumb = np.nonzero(col > 180)[0]
        if len(thumb):
            s.scroll = (int(t + thumb.min()), int(t + thumb.max()))
    # white text on the orange bar: plain grey, not orange-as-ink
    _sig(s, b"list", np.array([s.row if s.row is not None else -1, s.count, -1 if s.current is None else s.current]),
                        np.array(s.scroll or (0, 0)),
                        _binarize_small(g, (66, 12, 576, 72), (64, 8)),                   # title
                        _binarize_small(g, (120, *(s.bar or (0, 0))[:1], 550, (s.bar or (0, 40))[1] + 1), (64, 6), 150))


def _fields(a, s: Screen):
    g = _grey(a)
    x, y, w, h = _active_field(_orange(a))
    # the other fields: grey border runs on the active box's top line, which is on the same row over
    # HDMI and one row lower on OSD frames, so rows y-1..y+2 are combined
    line = ((g[y - 1:y + 3] > 60) & (g[y - 1:y + 3] < 200)).any(axis=0)
    boxes, start = [(x, x + w - 1)], None
    for xx in range(641):
        on = xx < 640 and line[xx] and not (x - 3 <= xx <= x + w + 3)
        if on and start is None:
            start = xx
        elif not on and start is not None:
            if xx - start > 30:
                boxes.append((start, xx - 1))
            start = None
    boxes.sort()
    s.count, s.field = len(boxes), boxes.index((x, x + w - 1))
    s.bar = (y, y + h - 1)
    s.boxes = boxes                                  # each field's (x0, x1), left to right
    up, down = _arrow_boxes(g, (x, y, w, h))
    s.glyphs = {"up": up, "down": down}
    _sig(s, b"fields", np.array([s.count, s.field, s.glyphs["up"], s.glyphs["down"]]),
                        _binarize_small(g, (0, 0, 640, 52), (80, 6)),                    # title
                        # every field's value and the info panel under the fields: at the coarse size
                        # "58 sec" and "56 sec" were one picture (old twin, 2026-10-28)
                        _binarize_small(g, (0, y, 640, y + h), (160, 14), 150),
                        _binarize_small(g, (0, 315, 640, 425), (160, 22), 150))


def _checklist(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    # Rating Set(Custom Key) has a second column (4 and 5 stars), which Down reaches after the first
    boxes = _checkboxes(g, o)
    if boxes:
        boxes += _checkboxes(g, o, 310)
    s.count = len(boxes)
    s.slots = ["ticked" if t else "empty" for *_, t in boxes]
    # the cursor: an orange row bar (385-593 px wide along its top edge, above the text; 310 in a
    # column) or an orange OK/Cancel/Enter button (240 px wide or less)
    lit = np.nonzero(o[56:424, :].sum(axis=1) > 150)[0]
    if len(lit):
        y0, y1 = 56 + int(lit.min()), 56 + int(lit.max())
        s.bar = (y0, y1)
        if o[y0 + 3].sum() > 300:
            s.focus = "rows"
            xs = np.nonzero(o[y0 + 3])[0]
            s.boxes = [(int(xs.min()), int(xs.max()))]
            inside = [i for i, (x, y, w, h, _) in enumerate(boxes)
                      if y0 - 4 <= y + h // 2 <= y1 + 4 and xs.min() - 40 <= x <= xs.max()]
            s.row = inside[0] if inside else None      # None: a radio sub-option row (DISP Set)
        else:
            s.focus = "button"
    else:
        # Reg. Flash Shooting Set: the cursor is an orange frame round one checkbox, not a bar
        for i, (x, y, w, h, _) in enumerate(boxes):
            ring = o[max(0, y - 7):y + h + 7, max(0, x - 7):x + w + 7].sum() - o[y:y + h, x:x + w].sum()
            if ring > 60:
                s.focus, s.row, s.bar = "rows", i, (y - 7, y + h + 6)
                break
    _sig(s, b"checklist", np.array([s.row if s.row is not None else -1, s.count]),
                        np.array([t for *_, t in boxes]), np.array(s.bar or (0, 0)),
                        _binarize_small(g, (0, 0, 640, 52), (80, 6)),
                        _binarize_small(g, (0, *(s.bar or (0, 0))[:1], 640, (s.bar or (0, 40))[1] + 1), (64, 6), 150),
                        # every visible row: a scrolled list can keep a similar cursor row (Rating Set)
                        _binarize_small(np.where(o, 255, g), (0, 56, 640, 345), (80, 30), 150),
                        # the buttons (under the rows, at the right, or in the footer), orange as ink
                        _binarize_small(np.where(o, 255, g), (0, 340, 640, 480), (64, 14), 150))


def _look(a, s: Screen):
    import bisect
    g = _grey(a)
    o = _orange(a)
    cols = np.nonzero(o[360:395, 10:632].mean(axis=0) > 0.6)[0]
    if len(cols):
        cx = 10 + int((cols.min() + cols.max()) // 2)
        s.field = bisect.bisect_right(LOOK_CELLS, cx) - 1
        s.bar = (349, 404)
        s.glyphs = {"up": int((g[344:350, cx - 10:cx + 11] > 150).sum()) > 12,
                    "down": int((g[404:410, cx - 10:cx + 11] > 150).sum()) > 12}
    s.count = len(LOOK_CELLS) - 1
    x0, x1, y0, y1 = LOOK_MARKER
    mk = np.nonzero(o[y0:y1, x0:x1].sum(axis=1) > 3)[0]
    if len(mk):
        s.marker = y0 + int((mk.min() + mk.max()) // 2)
    s.ticks = _look_ticks(g)
    _sig(s, b"look", np.array([s.field if s.field is not None else -1, (s.marker or 0) // 2]),
                        np.array([s.glyphs.get("up", False), s.glyphs.get("down", False)]),
                        _binarize_small(g, (18, 60, 330, 115), (40, 6), 150),          # the look's name
                        _binarize_small(g, (10, 352, 628, 402), (155, 12), 150))       # every cell's value


def _look_ticks(g) -> int | None:
    """The look scale's tick marks counted, or None when what is lit there is not a row of thin (at most 4 px), evenly
    spaced ticks from the top end to the bottom (something bright behind the panel, BW's greyed Saturation, or no
    scale). The a1 II's panel draws one a step: 19 on -9..+9, 10 on 0..9, 5 on 1..5, the count on every look frame of
    its runs that gives one (2026-11-13); another body's may not, so proving.looks trusts a count only once the run
    has read both ends of the same parameter beside it."""
    x0, x1, y0, y1 = LOOK_TICKS
    lit = np.nonzero((g[y0:y1, x0:x1] > 150).sum(axis=1) >= 4)[0]
    if len(lit) < 2:
        return None
    runs = np.split(lit, np.nonzero(np.diff(lit) > 1)[0] + 1)
    mids = np.array([y0 + (r[0] + r[-1]) / 2 for r in runs])
    gaps = np.diff(mids)
    top, bottom = LOOK_TICK_ENDS
    if len(runs) < 2 or max(len(r) for r in runs) > 4 or gaps.max() - gaps.min() > 2 \
            or abs(mids[0] - top) > 4 or abs(mids[-1] - bottom) > 4:
        return None
    return len(runs)


def _slider(a, s: Screen):
    import cv2
    g = _grey(a)
    o = _orange(a)
    signs = _bare_signs(g) if _slider_boxes(g) is None else None
    m = o.astype(np.uint8)
    m[:290] = 0
    m[410:] = 0
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if signs is None:
        marks = [r for r in st[1:] if 9 <= r[2] <= 17 and 9 <= r[3] <= 17]
    else:
        # found by its signs: the marker lies below the value line, where an orange ◂ ▸ never is (Finder Color
        # Temp.'s ◂ ▸ are orange, its marker a 28 px square on a dot scale; 2026-11-08)
        line = signs[1] + signs[3] // 2 - 40
        marks = [r for r in st[1:] if 9 <= r[2] <= 32 and 9 <= r[3] <= 32 and r[1] >= line]
    if marks:
        x, y, w, h, _ = marks[0]
        s.marker = int(x + w // 2)
    lit = np.where(o, 255, g)
    if signs is None:
        # ◂ ▸ round the value: small light triangles (9x12) on the value's line; one goes at an end.
        # Found by shape, because an orange icon can sit beside the value (Exposure Comp.)
        t = (g > 150).astype(np.uint8)
        t[:228] = 0
        t[280:] = 0
        _, _, st, _ = cv2.connectedComponentsWithStats(t, connectivity=8)
        s.glyphs = {"left": False, "right": False}
        for x, y, w, h, area in st[1:]:
            if 4 <= w <= 14 and 7 <= h <= 18 and area < 120:
                cs = (t[y:y + h, x:x + w] > 0).sum(axis=0)
                s.glyphs["left" if cs[0] < cs[-1] else "right"] = True
        value = (150, 215, 490, 290), (85, 18)
    else:
        # found by its signs (64 px boxes or none): the value and its ◂ ▸ sit 55-61 px above the signs' line
        # (AF Transition Speed, the volumes, Finder Color Temp., whose ◂ ▸ are orange; 2026-11-08), lower than
        # the band above. The ◂ left of the value, the ▸ right of it, each a solid triangle (the "o" of Slow
        # and Fast is neither, and further out). Neither found is no reading at all, never both ends: a walk
        # stops on an arrow read False (walk.walk_to_end; review, 2026-11-08)
        cy = signs[1] + signs[3] // 2
        left = _lone_triangle(lit, (230, cy - 76, 305, cy - 40), "left", alone=False)
        right = _lone_triangle(lit, (335, cy - 76, 410, cy - 40), "right", alone=False)
        s.glyphs = {"left": left, "right": right} if left or right else {}
        value = (150, cy - 82, 490, cy - 38), (85, 11)
    _sig(s, b"slider", np.array([(s.marker or 0) // 2]),
                        np.array([s.glyphs.get("left", False), s.glyphs.get("right", False)]),
                        _binarize_small(g, (0, 0, 640, 52), (80, 6), 150),               # title
                        _binarize_small(lit, *value, 150))                              # the value


def _sidelist(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    rows = np.nonzero(o[:, 305:595].mean(axis=1) > 0.6)[0]
    s.bar = (int(rows.min()), int(rows.max()))
    s.row = int(((s.bar[0] + s.bar[1]) / 2 - SIDE_ROW_TOP) // SIDE_ROW_PITCH)
    s.count = sum(1 for i in range(6)
                  if i == s.row or int((g[SIDE_ROW_TOP + SIDE_ROW_PITCH * i + 8:SIDE_ROW_TOP + SIDE_ROW_PITCH * i + 40,
                                         310:590] > 150).sum()) > 30)
    x, t, b = SIDE_SCROLL
    col = g[t:b + 1, x - 2:x + 4].max(axis=1)
    # the track is faint (grey ~30 over live view); at > 30 noise dropped it on one frame (2026-10-28)
    if (col > 20).mean() > 0.85:
        thumb = np.nonzero(col > 70)[0]
        if len(thumb):
            s.scroll = (int(t + thumb.min()), int(t + thumb.max()))
    _sig(s, b"sidelist", np.array([s.row, s.count]), np.array(s.scroll or (0, 0)),
                        _binarize_small(g, (0, 0, 640, 75), (80, 8), 150),               # PP number + title
                        _binarize_small(g, (303, s.bar[0], 597, s.bar[1] + 1), (48, 6), 150))


def _wbgrid(a, s: Screen):
    import cv2
    g = _grey(a)
    o = _orange(a)
    s.glyphs = {k: v is not None for k, v in _wb_found(g).items()}
    x0, y0, x1, y1 = WB_GRID
    m = o[y0:y1, x0:x1].astype(np.uint8)
    _, _, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    # the cursor dot (~140 px, round); the grid's own orange cells near A are ~43 px squares
    dots = [(c, r) for r, c in zip(st[1:], cen[1:], strict=True) if 90 <= r[4] <= 260 and abs(int(r[2]) - int(r[3])) <= 4]
    if dots:
        c, _ = max(dots, key=lambda d: d[1][4])
        s.marker = (x0 + int(round(c[0])), y0 + int(round(c[1])))
    lit = np.where(o, 255, g)            # the axis last moved is orange: same value, same picture
    _sig(s, b"wbgrid", np.array(s.marker or (0, 0)) // 3,
                        np.array([s.glyphs[k] for k in sorted(s.glyphs)]),
                        _binarize_small(lit, (0, 0, 640, 110), (80, 10), 150),          # title + WB mode
                        _binarize_small(lit, (60, 300, 400, 420), (85, 30), 150))       # A-B / G-M readouts


def _checkgrid(a, s: Screen):
    import cv2
    g = _grey(a)
    o = _orange(a)
    boxes = _grid_boxes(g, o)
    cells = {(round((y - GRID_Y0) / GRID_DY), round((x - GRID_X0) / GRID_DX)): t for x, y, w, h, t in boxes}
    s.count = len(cells)
    s.slots = ["ticked" if cells[k] else "empty" for k in sorted(cells)]
    m = o.astype(np.uint8)
    m[:120] = 0
    m[420:] = 0
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    big = [r for r in st[1:] if r[4] > 2000]
    if big:
        x, y, w, h, _ = max(big, key=lambda r: r[4])
        s.bar = (int(y), int(y + h - 1))
        if 70 <= w <= 90 and 90 <= h <= 110:          # a grid cell
            s.focus = "rows"
            r, c = round((y + 7 - GRID_Y0) / GRID_DY), round((x + 27 - GRID_X0) / GRID_DX)
            s.row, s.field = int(r), int(c)
        else:
            s.focus = "button"
    _sig(s, b"checkgrid", np.array([s.row if s.row is not None else -1, s.field if s.field is not None else -1]),
                        np.array([cells[k] for k in sorted(cells)]),
                        _binarize_small(g, (0, 0, 640, 120), (80, 12), 150),            # title + area name
                        _binarize_small(g, (615, 120, 640, 345), (4, 24), 60),          # scrollbar
                        _binarize_small(g, (40, 120, 615, 345), (56, 20), 150),         # the visible icons
                        # OK / Cancel, orange as ink: which button is selected (old twin, 2026-10-28)
                        _binarize_small(np.where(o, 255, g), (0, 345, 640, 425), (64, 8), 150))


def _tiles(a, s: Screen):
    import bisect
    import cv2
    g = _grey(a)
    m = _orange(a).astype(np.uint8)
    m[:45] = 0
    m[425:] = 0
    m[:, :136] = 0
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    big = [r for r in st[1:] if r[4] > 3000]
    s.focus = "tiles"
    if big:
        x, y, w, h, _ = max(big, key=lambda r: r[4])
        s.bar = (int(y), int(y + h - 1))
        s.row = bisect.bisect_right(TILE_ROWS, y + h // 2) - 1
        s.field = bisect.bisect_right(TILE_COLS, x + 10) - 1
        s.count = round(w / (TILE_COLS[1] - TILE_COLS[0]))        # cells the tile spans
    _sig(s, b"tiles", np.array([s.row if s.row is not None else -1, s.field if s.field is not None else -1]),
                        _binarize_small(g, (0, 0, 640, 40), (80, 6)),
                        _binarize_small(g, (137, 45, 636, 425), (50, 38), 150))


def _picker(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    sat = _sat(a)
    rows = np.nonzero(o[:, 345:630].mean(axis=1) > 0.6)[0]
    if len(rows):
        s.bar = (int(rows.min()), int(rows.max()))
        s.row = int(((s.bar[0] + s.bar[1]) / 2 - PICK_ROW_TOP) // PICK_ROW_PITCH)
    radios = {}
    for i in range(PICK_ROWS):
        cy, cx = PICK_ROW_TOP + PICK_ROW_PITCH * i + 26, PICK_RADIO_X
        if (g[cy - 10:cy + 11, cx - 11:cx + 12] > 150).sum() > 100:
            radios[i] = bool(o[cy - 3:cy + 4, cx - 4:cx + 5].sum() > 30)
    s.count = len(radios)
    s.current = next((i for i, saved in radios.items() if saved), None)
    # the selected tab is the one in full colour; the selected group's number box too
    tabs = [float(sat[PICK_TAB_TOP + PICK_TAB_PITCH * i + 4:PICK_TAB_TOP + PICK_TAB_PITCH * i + 48, 2:46].mean())
            for i in range(7)]
    s.field = int(np.argmax(tabs)) if max(tabs) > 100 else None
    groups = [float(sat[PICK_ROW_TOP + PICK_ROW_PITCH * i + 14:PICK_ROW_TOP + PICK_ROW_PITCH * i + 40, 63:90].mean())
              for i in range(PICK_ROWS)]
    s.group = int(np.argmax(groups)) if max(groups) > 100 else None
    s.focus = "rows"
    _sig(s, b"picker", np.array([s.row if s.row is not None else -1, s.count, -1 if s.current is None else s.current,
                                 -1 if s.field is None else s.field, -1 if s.group is None else s.group]),
                        _binarize_small(g, (0, 0, 520, 40), (65, 6)),                   # the slot or key's name
                        _binarize_small(g, (520, 0, 640, 40), (60, 20)),                # n/N
                        # the option under the cursor: white text on the bar
                        _binarize_small(g, (370, *(s.bar or (0, 0))[:1], 636, (s.bar or (0, 40))[1] + 1), (66, 6), 150),
                        _binarize_small(g, (340, 45, 636, 420), (74, 35), 150))         # every option shown


def _table(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    x, y, w, h = _cell_box(o)
    s.bar = (y, y + h - 1)
    s.boxes = [(x, x + w - 1)]
    s.marker = (x + w // 2, y + h // 2)
    s.focus = _table_focus({"cell_box": (x, y, w, h), "icon_tabs": len(_icon_tabs(g, o)),
                            "cell_grid": _grid_column(g, (x, y, w, h))})
    lit = np.where(o, 255, g)
    _sig(s, b"table", np.array([s.marker[0] // 4, s.marker[1] // 4, s.focus == "cell"]),
                        _binarize_small(g, (0, 0, 640, 52), (80, 6)),                    # breadcrumb or title
                        # every cell's value and the name line over the grid (My Dial: the function
                        # under the cursor, in orange); orange counts as ink
                        _binarize_small(lit, (0, 52, 640, 424), (128, 46), 150))


def _keyset(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    box = _cell_box(o)
    tab = [i for i in range(6) if o[KEY_TAB_TOP + KEY_TAB_PITCH * i + 8:KEY_TAB_TOP + KEY_TAB_PITCH * i + 55, 2:52].mean() > 0.3]
    if tab:
        s.focus, s.group = "tabs", tab[0]
        s.bar = (KEY_TAB_TOP + KEY_TAB_PITCH * tab[0], KEY_TAB_TOP + KEY_TAB_PITCH * (tab[0] + 1) - 1)
    elif box and abs(box[0] - 64) <= 4 and 280 <= box[2] <= 310:
        x, y, w, h = box
        s.focus, s.bar, s.boxes = "keys", (y, y + h - 1), [(x, x + w - 1)]
        s.row = int(((y + h / 2) - KEY_ROW_TOP) // KEY_ROW_PITCH)
    elif box and box[2] <= 200:
        x, y, w, h = box
        s.focus, s.bar, s.boxes = "cell", (y, y + h - 1), [(x, x + w - 1)]
        s.marker = (x + w // 2, y + h // 2)
    elif box:                                   # anything wider (the Dial/Wheel checkbox row?): never Enter
        x, y, w, h = box
        s.focus, s.bar = "other", (y, y + h - 1)
    # the page shown: its tab icon is the brightest (orange-filled while the tabs have the focus)
    if s.group is None:
        bright = [int((g[KEY_TAB_TOP + KEY_TAB_PITCH * i + 8:KEY_TAB_TOP + KEY_TAB_PITCH * i + 55, 4:50] > 180).sum())
                  for i in range(6)]
        s.group = int(np.argmax(bright)) if max(bright) > 40 else None
    lit = np.where(o, 255, g)
    _sig(s, b"keyset", np.array([{"tabs": 0, "keys": 1, "cell": 2, "other": 3}.get(s.focus, -1),
                                 s.row if s.row is not None else -1, s.group if s.group is not None else -1,
                                 *((np.array(s.marker) // 4) if s.marker else (-1, -1))]),
                        _binarize_small(g, (0, 0, 640, 40), (80, 6)),                    # title + n/N
                        _binarize_small(lit, (55, 45, 640, 424), (116, 46), 150))        # page header, keys, drawing


def _fnmenu(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    s.row, s.field = _fn_tile({"cell_box": _cell_box(o)})
    s.bar = (FN_TILE_ROWS[s.row], FN_TILE_ROWS[s.row] + 57)
    s.focus = "tiles"
    lit = np.where(o, 255, g)
    _sig(s, b"fnmenu", np.array([s.row, s.field]),
                        _binarize_small(g, (0, 0, 640, 52), (80, 6)),
                        _binarize_small(lit, (330, 55, 640, 105), (62, 10), 150),       # the slot's function name
                        _binarize_small(lit, (0, 105, 640, 424), (120, 60), 150))       # every tile's icon


def _helppop(a, s: Screen):
    g = _grey(a)
    o = _orange(a)
    x0, y0, x1, y1 = HELP_POP
    rows = np.nonzero(o[y0:y1, x0 + 8:x1 - 8].mean(axis=1) > 0.6)[0]
    if len(rows):
        s.bar = (y0 + int(rows.min()), y0 + int(rows.max()))
        s.row = int(((s.bar[0] + s.bar[1]) / 2 - HELP_ROW_TOP) // HELP_ROW_PITCH)
    s.focus = "rows"
    s.count = sum(1 for i in range(3) if i == s.row or      # entries sit above the panel's MENU ↩ footer
                  int((g[HELP_ROW_TOP + HELP_ROW_PITCH * i + 10:HELP_ROW_TOP + HELP_ROW_PITCH * i + 42,
                         x0 + 10:x1 - 10] > 150).sum()) > 40)
    _sig(s, b"helppop", np.array([s.row if s.row is not None else -1, s.count]),
                        _binarize_small(g, (x0, y0, x1, y1), (40, 20), 150))


def _row_bands(a, s: Screen, x0: int) -> list:
    """Rows of a menu or submenu page as (top, bottom) bands, from the separator lines under them.
    The orange bar hides the separators next to it, so its edges stand in for them. A row is 45-70
    px tall (53 on standard pages, 61 on submenus with › Detail boxes: Recognition Target,
    2026-10-28); a gap of another size (an info panel's border) ends the list."""
    g, sat = _grey(a), _sat(a)
    band = (g[:, x0 + 10:530] > 40) & (g[:, x0 + 10:530] < 130) & (sat[:, x0 + 10:530] < 25)
    ys = [y for y in range(MENU_ROW_TOP + 30, 428) if band[y].mean() > 0.8]
    if s.bar:
        ys += [s.bar[0] - 1, s.bar[1]]
    ys = sorted(ys)
    marks = [y for i, y in enumerate(ys) if i == 0 or y - ys[i - 1] > 3]          # one y per line
    def has_text(t, b_):
        """A label at the left (normal ~221, greyed ~119) or a value at the right. The ⌄ "more" mark
        sits mid-screen and is left out, so short labels count too (Color Depth's "C", 2026-10-28)."""
        if s.bar is not None and t <= (s.bar[0] + s.bar[1]) / 2 <= b_:
            return True
        label = int((g[t + 6:b_ - 6, x0:x0 + 250] > 100).sum())
        value = int((g[t + 6:b_ - 6, 520:636] > 100).sum())
        return label > 60 or value > 40
    gaps = [b_ - a_ for a_, b_ in zip(marks, marks[1:]) if 45 <= b_ - a_ <= 70]  # noqa: B905 (pairs each mark with next)
    typical = int(np.median(gaps)) if gaps else MENU_ROW_PITCH
    rows, top = [], MENU_ROW_TOP
    for y in marks:
        if y - top < 45:
            if not rows:
                top = y          # a header line: rows start under it (Picture Profile's PP1 page, y 76)
            continue
        if not rows and y - top > 70 and y - typical >= MENU_ROW_TOP:
            top = y - typical    # the first row's top is not drawn as a line (PP1 with the cursor lower)
        k = round((y - top) / typical)
        if y - top > 70 and k >= 2 and abs((y - top) - k * typical) <= 6:
            # separators not detected in between (PP1 scrolled to Saturation): k rows of the same height
            step = (y - top) / k
            parts = [(round(top + i * step), round(top + (i + 1) * step)) for i in range(k)]
            if not all(has_text(t, b_) for t, b_ in parts):
                break
            rows.extend(parts)
            top = y
            continue
        if y - top > 70 or not has_text(top, y):
            break
        rows.append((top, y))
        top = y
    else:
        # the last visible row of a list that scrolls has no separator under it
        if rows:
            pitch = rows[-1][1] - rows[-1][0]
            if top + pitch <= 428 and has_text(top, top + pitch):
                rows.append((top, top + pitch))
    return rows


def _page_rows(a, s: Screen, x0: int):
    """Row states on a menu or submenu page, top to bottom: "normal" | "greyed" | "cursor", from its
    row bands (s.rows). Label text peaks at grey ~221-225 on normal rows and ~119 on greyed ones
    (OSD and HDMI)."""
    g = _grey(a)
    o = _orange(a)
    s.rows = _row_bands(a, s, x0)
    if s.bar:
        mid = (s.bar[0] + s.bar[1]) / 2
        s.row = next((i for i, (t, b) in enumerate(s.rows) if t <= mid <= b), s.row)
    s.count = len(s.rows)
    s.pitch = int(np.median([b - t for t, b in s.rows])) if s.rows else MENU_ROW_PITCH
    s.slots = []
    for i, (t, b) in enumerate(s.rows):
        if i == s.row:
            s.slots.append("cursor")
            continue
        band, ob = g[t + 8:b - 8, x0:420], o[t + 8:b - 8, x0:420]
        text = band[(band > 60) & ~ob]
        s.slots.append("normal" if len(text) and np.percentile(text, 95) > 170 else "greyed")


def _rows_pictures(g, s: Screen, x0: int) -> tuple:
    """A page's rows for its signature: the selected row's value, and every other row. The selected
    row's LABEL is left out: the camera scrolls a label too long for the row ("Operation in Vertical
    Orientation", Touch Pad Settings, 2026-10-28), so it changes while the cursor sits there."""
    others = g.copy()
    if s.bar:
        others[s.bar[0]:s.bar[1] + 1, :] = 0
        value = _binarize_small(g, (430, s.bar[0], 636, s.bar[1] + 1), (26, 6))
    else:
        value = _binarize_small(g, (430, 0, 636, 1), (1, 1))
    return value, _binarize_small(others, (x0, MENU_ROW_TOP, 636, 425), (64, 38), 150)


def _submenu(a, s: Screen):
    o = _orange(a)
    rows = np.nonzero(o[:, 140:636].sum(axis=1) > 250)[0]
    s.bar = (int(rows.min()), int(rows.max()))
    s.row = int(((s.bar[0] + s.bar[1]) / 2 - MENU_ROW_TOP) // MENU_ROW_PITCH)     # refined from the row bands
    s.focus = "rows"
    _page_rows(a, s, 60)
    g = _grey(a)
    _sig(s, b"submenu", np.array([s.row]),
                        _binarize_small(g, (0, 0, 640, 40), (80, 6)),          # breadcrumb + n/N
                        *_rows_pictures(g, s, 55))


MENU_PANEL_ROWS, MENU_PANEL_GROUPS = 160, 300       # the rows panel begins left of one, right of the other


def _panel_x(g) -> int:
    """Where a menu page's rows panel begins: the first column from x=100 whose background (the column's median
    over the page's height, text being a minority of each column) is the panel's lighter grey (~32) and not the
    group column's (~16). 640 when none is."""
    med = np.median(g[45:425, :], axis=0)
    lit = med[100:] >= 26
    run = np.convolve(lit, np.ones(8), "valid") >= 8          # eight lit columns in a row: a panel, not a line
    where = np.nonzero(run)[0]
    return int(where[0]) + 100 if len(where) else 640


def _menu(a, s: Screen):
    o = _orange(a)
    rows = np.nonzero(o[:, 140:636].sum(axis=1) > 250)[0]
    if len(rows):
        s.bar = (int(rows.min()), int(rows.max()))
        s.row = int(((s.bar[0] + s.bar[1]) / 2 - MENU_ROW_TOP) // MENU_ROW_PITCH)
    # the current group's number box is filled with the tab colour; the cursor is on the rows only
    # when the orange row bar is drawn, otherwise it is in the group column
    sat = _sat(a)
    box = np.nonzero((sat[45:425, 58:95] > 80).mean(axis=1) > 0.6)[0]
    if len(box):
        s.group = int(((box.min() + box.max()) / 2) // MENU_ROW_PITCH)
    # where the rows panel begins says which column has the focus, and whether the menu is still moving: the
    # panel's background is lighter than the group column's, and it starts at x~135 with the cursor on the
    # rows, at x~370 with the cursor in the group column (the group names drawn in full), and anywhere between
    # while the menu slides in (2026-11-06: a frame caught mid-slide, no row bar yet, read as the group column;
    # the Right meant to step into the rows opened the row the cursor was on). No focus until it stops.
    panel = _panel_x(_grey(a))
    if panel >= MENU_PANEL_GROUPS:
        s.focus = "groups"
    elif panel <= MENU_PANEL_ROWS and s.bar:
        s.focus = "rows"
    else:
        s.focus = None                      # moving, or the panel in place with no row bar drawn yet
    _page_rows(a, s, 145)
    g = _grey(a)
    _sig(s, b"menu", np.array([s.row if s.row is not None else -1, s.group if s.group is not None else -1]),
                        _binarize_small(g, (0, 0, 640, 40), (80, 6)),          # breadcrumb + n/N
                        *_rows_pictures(g, s, 140))


def count_stars(a: np.ndarray, bar) -> int | None:
    """Rating stars on a list popup's cursor row: Sony draws "Rating (★★★)" as star clusters (one
    large ★, then 2-5 small stars in a pattern), which OCR and the VLMs miscount, so the star-sized
    blobs between the parentheses are counted. None when the row has no parentheses ("Off"); 0 for
    other text in them ("Divider Frame (|→)")."""
    import cv2
    if not bar:
        return None
    m = (_grey(a)[bar[0] + 2:bar[1] - 1, 110:556] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    comps = [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in st[1:] if area >= 6]
    # a bracket is 38 px tall, taller than any letter or digit (30): "1" and "l" are as narrow
    # ("By 10 minutes" counted 4 stars, 2026-10-31)
    parens = sorted(c for c in comps if c[3] >= 34 and c[2] <= 9)
    if len(parens) < 2:
        return None
    lo, hi = parens[-2][0] + parens[-2][2], parens[-1][0]
    return sum(1 for x, y, w, h in comps if lo <= x and x + w <= hi and 4 <= w <= 32 and 4 <= h <= 32)


def box_stars(a: np.ndarray, s: Screen) -> int | None:
    """Stars after the checkbox on a checklist's cursor row (Rating Set(Custom Key) shows only a star
    cluster, 1-5); None when the row has anything else (text) or no cursor row."""
    import cv2
    if s.kind != "checklist" or s.focus != "rows" or not s.bar or not s.boxes:
        return None
    (x0, x1), (y0, y1) = s.boxes[0], s.bar
    m = (_grey(a)[y0 + 2:y1 - 1, x0 + 45:x1 - 4] > 150).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    comps = [(int(w), int(h)) for x, y, w, h, area in st[1:] if area >= 6]
    if not comps or len(comps) > 5 or any(not (8 <= w <= 20 and 10 <= h <= 25) for w, h in comps):
        return None
    return len(comps)


def rows_key(a: np.ndarray) -> str:
    """The visible rows' text (white, at grey > 150, so the orange cursor bar hardly matters) plus the
    page key: a submenu that scrolls instead of paging keeps its breadcrumb while its rows change
    (Auto Recog. Target, 2026-10-28), so labels read for one view must not be reused for another."""
    g = _grey(a)
    return _hash(page_key(a).encode(), _binarize_small(g, (60, 45, 540, 420), (60, 47), 150))


def page_key(a: np.ndarray) -> str:
    """The breadcrumb bar as a coarse picture plus the n/N counter at a finer one: one key per page
    ("5/65" and "6/65" share a breadcrumb; at the coarse size alone they were one picture)."""
    return _hash(*page_bits(a))


def page_bits(a: np.ndarray) -> tuple:
    """page_key's pictures, unhashed, to compare with a tolerance: a counter cell can sit right at the
    threshold and flip between frames of the same page ("6/65", 2026-10-29)."""
    g = _grey(a)
    return _binarize_small(g, (0, 0, 520, 40), (65, 6)), _binarize_small(g, (520, 0, 640, 40), (60, 20))


def read(frame: Frame) -> Screen:
    a = frame.image
    f = features(a)
    s = Screen(kind=classify(f), features=f)
    if s.kind == "dialog":
        _dialog(a, s)
    elif s.kind == "list":
        _list(a, s)
    elif s.kind == "submenu":
        _submenu(a, s)
    elif s.kind == "fields":
        _fields(a, s)
    elif s.kind == "checklist":
        _checklist(a, s)
    elif s.kind == "look":
        _look(a, s)
    elif s.kind == "slider":
        _slider(a, s)
    elif s.kind == "sidelist":
        _sidelist(a, s)
    elif s.kind == "wbgrid":
        _wbgrid(a, s)
    elif s.kind == "checkgrid":
        _checkgrid(a, s)
    elif s.kind == "helppop":
        _helppop(a, s)
    elif s.kind == "tiles":
        _tiles(a, s)
    elif s.kind == "picker":
        _picker(a, s)
    elif s.kind == "table":
        _table(a, s)
    elif s.kind == "keyset":
        _keyset(a, s)
    elif s.kind == "fnmenu":
        _fnmenu(a, s)
    elif s.kind == "menu":
        _menu(a, s)
    else:
        # orange counts as ink: on a question notice the orange moves between OK and Cancel
        lit = np.where(_orange(a), 255, _grey(a))
        _sig(s, s.kind.encode(), _binarize_small(lit, (0, 0, 640, 480), (64, 48)))
    s.page = np.unpackbits(np.concatenate(page_bits(a)))
    return s
