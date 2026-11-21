"""The menu opened on the Main tab's page (2026-11-21): the camera reopens its menu where it was last closed, and once a
run closed it on Main (tco_1fps_look's tab-column jump at S&Q 1fps, kit2_greyrow 04494 to 04498, two tabs a press),
the next run's MENU opened on "Main 2/63" (kit2_pp_cd_sq 00004), a page of tiles and headings no page scan holds.
mode_switch's Right (meant to step from the group column into the rows) moved onto the "1 Main" heading (00005), and
its find, which took only an exact scan position, stopped. Now crawl_run.find_position knows the Main page by its
breadcrumb and goes off it by the columns: Left only where the group bar is lit (a heading), Down in the tab column
checked to read Shooting, Right into the Shooting tab's group column, then from_groups as for any menu opened there.
Never an Enter, never a press on a tile. mode_switch.find falls back to it; open_menu presses no Right on the Main page.
The camera's own frames where the runs hold them; nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths  # noqa: E402

import crawl_run  # noqa: E402

# the frames as the kit reads them: (breadcrumb text, lit bar text, kind, focus)
MAIN_TAB = ("Main 2/63 Main ISO 1/250 F5.6", "", "menu", "groups")             # kit2_pp_cd_sq 00004: the tab lit
MAIN_HEADING = ("Main 2/63 Main ISO 1/250 F5.6", "Main", "menu", "groups")      # 00005: the "1 Main" heading lit
SHOOTING_TAB = ("Shooting 4/59 Image Quality/Rec", "", "menu", "groups")       # kit2_greyrow 04493: the tab lit
SHOOTING_GROUP = ("Shooting 4/59 Image Quality/Rec", "Image Quality/Rec", "menu", "groups")   # 04492: a group lit
MY_MENU_TAB = ("My Menu 1/59 My Menu Setting", "", "menu", "groups")          # 04497


@pytest.mark.parametrize("rel, main, lit", [
    ("kit2_pp_cd_sq/shots/00004_menu-watch.png", True, False),
    ("kit2_pp_cd_sq/shots/00005_right.png", True, True),
    ("kit2_greyrow/shots/04498_down.png", True, False),          # Main 2/59, the S&Q menu's
    ("kit2_greyrow/shots/04497_down.png", False, False),         # My Menu 1/59
    ("kit2_greyrow/shots/04493_left.png", False, False),         # Shooting 4/59, its tab lit
    ("kit2_greyrow/shots/04492_left.png", False, True),          # Shooting 4/59, a group lit
    ("kit2_greyrow/shots/04494_down.png", False, False),         # Exposure/Color 17/59
])
def test_the_cameras_frames_read_as_main_or_not(rel, main, lit):
    from camkit import ocr
    from camkit.frames import load
    from camkit.live import lit_text
    f = paths.a1ii_root() / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    frame = load(f)
    text = ocr.text_in(ocr.read([frame.path])[frame.path], (0, 0, 640, 480))
    assert crawl_run.on_main(text) is main, text[:40]
    assert bool(lit_text(frame.image, frame.path).strip()) is lit


def test_the_tab_column_frames_name_their_tab():
    assert crawl_run.tab_shown(SHOOTING_TAB[0]) == "Shooting"
    assert crawl_run.tab_shown(MAIN_TAB[0]) is None               # no page scan holds the Main tab
    assert crawl_run.on_main("Main 2/59 Main1 60p 1fps") and not crawl_run.on_main("My Menu 1/59")
    assert not crawl_run.on_main("Shooting > Main Settings 3/63")


class Walk:
    """A menu whose screens follow `script`: {state: {key: next state}}; every press is recorded."""

    def __init__(self, start, script):
        self.state, self.script, self.pressed = start, script, []
        self.frame = SimpleNamespace(image=None, path=Path("00001_x.png"))

    def read(self):
        return SimpleNamespace(kind=self.state[2], focus=self.state[3])

    def press(self, key, **kw):
        self.pressed.append(key)
        nxt = self.script.get(self.state, {}).get(key)
        if nxt is None:
            raise AssertionError(f"no press {key!r} expected on {self.state[0][:20]!r} ({self.state[1]!r} lit)")
        self.state = nxt


@pytest.fixture
def walk(monkeypatch):
    seen = []

    def make(start, script, groups=7):
        cam = Walk(start, script)
        monkeypatch.setattr(crawl_run, "menu_text", lambda c: c.state[0])
        monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: cam.state[1])

        def from_groups(c, cycle, model):
            seen.append(c.state)
            return groups
        monkeypatch.setattr(crawl_run, "from_groups", from_groups)
        return cam
    make.seen = seen
    return make


ON_THE_WAY = {MAIN_HEADING: {"left": MAIN_TAB}, MAIN_TAB: {"down": SHOOTING_TAB}, SHOOTING_TAB: {"right": SHOOTING_GROUP}}


def test_from_the_main_heading_left_down_right_then_the_groups_way(walk):
    cam = walk(MAIN_HEADING, ON_THE_WAY)
    assert crawl_run.from_main(cam, [], {}) == 7
    assert cam.pressed == ["left", "down", "right"]
    assert walk.seen == [SHOOTING_GROUP]                      # from_groups from the Shooting tab's group column


def test_from_the_main_tab_no_left(walk):
    cam = walk(MAIN_TAB, ON_THE_WAY)
    assert crawl_run.from_main(cam, [], {}) == 7
    assert cam.pressed == ["down", "right"]


@pytest.mark.parametrize("script, pressed", [
    ({MAIN_TAB: {"down": MY_MENU_TAB}}, ["down"]),                                   # Down read another tab
    ({MAIN_TAB: {"down": SHOOTING_GROUP}}, ["down"]),                                # a bar lit after the Down
    ({MAIN_TAB: {"down": SHOOTING_TAB}, SHOOTING_TAB: {"right": SHOOTING_TAB}}, ["down", "right"]),  # no group lit
    ({MAIN_TAB: {"down": ("Shooting 4/59", "", "dialog", None)}}, ["down"]),          # not a menu
])
def test_anything_else_on_the_way_stops_with_nothing_more_pressed(walk, script, pressed):
    cam = walk(MAIN_TAB, script)
    assert crawl_run.from_main(cam, [], {}) is None
    assert cam.pressed == pressed and "enter" not in cam.pressed
    assert walk.seen == []


def test_a_left_that_leaves_a_bar_lit_stops_there(walk):
    cam = walk(MAIN_HEADING, {MAIN_HEADING: {"left": MAIN_HEADING}})
    assert crawl_run.from_main(cam, [], {}) is None
    assert cam.pressed == ["left"]


def test_find_position_takes_the_main_page_off_by_the_columns(walk, monkeypatch):
    monkeypatch.setattr(crawl_run, "same_position", lambda screen, p: False)
    cam = walk(MAIN_HEADING, ON_THE_WAY)
    assert crawl_run.find_position(cam, [{"screen": None, "page": "x"}], {}) == 7
    assert cam.pressed == ["left", "down", "right"]


def test_mode_switch_find_falls_back_to_find_position(monkeypatch):
    import mode_switch
    calls = []
    monkeypatch.setattr(mode_switch, "scan_position", lambda cam, cycle: None)
    monkeypatch.setattr(mode_switch, "find_position", lambda cam, cycle, model: calls.append("fp") or 3)
    monkeypatch.setattr(mode_switch, "go_to", lambda cam, cycle, model, j, label: calls.append(("go", j, label)) or 9)
    mode_switch.find(SimpleNamespace(), [], {}, "Mode Dial Control Set")
    assert calls == ["fp", ("go", 3, "Mode Dial Control Set")]
    monkeypatch.setattr(mode_switch, "find_position", lambda cam, cycle, model: None)
    with pytest.raises(mode_switch.Failed, match="could not reach"):
        mode_switch.find(SimpleNamespace(read=lambda: SimpleNamespace(kind="menu"),
                                         frame=SimpleNamespace(path=Path("00005_right.png"))), [], {}, "X")


def test_open_menu_presses_no_right_on_the_main_page(monkeypatch):
    import mode_switch
    cam = Walk(MAIN_TAB, {})
    cam.may_open = frozenset()
    monkeypatch.setattr(mode_switch, "menu_from_shooting", lambda c: None)
    monkeypatch.setattr(mode_switch, "text", lambda c: c.state[0])
    mode_switch.open_menu(cam)
    assert cam.pressed == []
