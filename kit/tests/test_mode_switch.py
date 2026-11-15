"""kit/provers/mode_switch.py's Mode Dial Control Set step (dial_by_menu) off the camera. Right on the row gives a
two-option list, or, on the a1 II (2026-11-15, kit2_a1fin_movie_m 00016_right.png), a table: one cell per dial and the
Set All buttons below, where only the Shooting Mode Dial's cell is put on Set with Menu and no Set All button ever gets
Enter (the playbook's rule 8). A made-up camera drawn as the a1 II draws the table, then the camera's own frames
(skipped without the a1 II's runs or an OCR engine)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths  # noqa: E402

FULL = (0, 0, 640, 480)
NAME_BOX = (380, 320, 640, 370)
DIALS = ["Shooting Mode Dial", "Drive Mode Dial", "Focus Mode Dial"]
# the table as the a1 II draws it and the table walk found it (kit2_tables): the cells' and the buttons' centres
CELL_Y, BUTTON_Y = [132, 184, 236], [320, 388]
ITEMS = [("cell", y) for y in CELL_Y] + [("button", y) for y in BUTTON_Y]
BUTTONS = ["Set All with Dial", "Set All with Menu"]
DIAL, MENU_OPT = "Set with Dial", "Set with Menu"


@pytest.fixture
def ms():
    import mode_switch
    return mode_switch


class DialCam:
    """A camera on Mode Dial Control Set's menu row. Right opens `right` ("table", "list" or another kind). In the table
    Up and Down move the lit item round the three cells and the two buttons (`lit`: where it starts), Enter on a cell
    opens its two-option list on the saved option (`enter_opens`: another kind instead), Down moves in the list, Enter
    chooses (unless `ignores_choice`) and the table comes back; MENU goes from a screen the table opened back to it, from
    the table to the menu page, and from there to the shooting screen. Enter on a Set All button fails the test. OCR
    reads the dial's name at the right from `names` (`button_name` where a button is lit), the whole table as
    `table_text` when given. Every press is kept, the link's too (runner.close_screen's)."""

    def __init__(self, right="table", lit=0, values=(DIAL, DIAL, DIAL), names=DIALS, button_name="",
                 enter_opens="list", ignores_choice=False, table_text=None):
        self.kind, self.right, self.at, self.values = "menu", right, lit, list(values)
        self.names, self.button_name, self.table_text = list(names), button_name, table_text
        self.enter_opens, self.ignores_choice = enter_opens, ignores_choice
        self.option, self.keys, self.logged, self.n = 0, [], [], 1
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))
        self.link = SimpleNamespace(press=lambda key, **kw: self._press(key))

    @property
    def frame(self):
        return SimpleNamespace(path=Path(f"{self.n:05d}_{self.keys[-1] if self.keys else 'menu'}.png"), image=None)

    def read(self):
        if self.kind == "table":
            what, y = ITEMS[self.at]
            return SimpleNamespace(kind="table", focus=what, marker=(214, y + 3), bar=(y - 22, y + 28),
                                   boxes=[(64, 363)])
        if self.kind == "list":
            y = 95 + 50 * self.option
            return SimpleNamespace(kind="list", focus=None, marker=None, bar=(y, y + 47), boxes=[])
        return SimpleNamespace(kind=self.kind, focus=None, marker=None, bar=None, boxes=[])

    def refresh(self, tag=""):
        return self.read()

    def press(self, key, **kw):
        self._press(key)

    def _press(self, key):
        self.keys.append(key)
        self.n += 1
        if self.kind == "menu":
            self.kind = {"right": self.right, "menu": "shooting"}.get(key, "menu")
        elif self.kind == "table":
            if key in ("up", "down"):
                self.at = (self.at + (1 if key == "down" else -1)) % len(ITEMS)
            elif key == "enter":
                assert ITEMS[self.at][0] == "cell", f"Enter on {BUTTONS[self.at - 3]!r}: the playbook's rule 8"
                self.kind, self.option = self.enter_opens, [DIAL, MENU_OPT].index(self.values[self.at])
            elif key == "menu":
                self.kind = "menu"
        elif self.kind == "list":
            if key == "down":
                self.option = (self.option + 1) % 2
            elif key == "enter":
                if not self.ignores_choice:
                    self.values[self.at] = [DIAL, MENU_OPT][self.option]
                self.kind = "table" if self.right == "table" else "menu"
            elif key == "menu":
                self.kind = "table" if self.right == "table" else "menu"
        elif self.kind != "shooting" and key == "menu":
            self.kind = "table" if self.right == "table" else "menu"

    def cancel_to_menu(self, tries=3):
        """camkit.live.LiveCamera's: MENU until a menu page."""
        for _ in range(tries):
            if self.kind in ("menu", "tiles", "shooting"):
                return True
            self._press("menu")
        return self.kind in ("menu", "tiles", "shooting")

    def words(self, box) -> str:
        """What OCR reads in `box`: the whole screen, the lit cell's dial named at the right, or the lit item."""
        box = tuple(box)
        if self.kind == "table":
            what = ITEMS[self.at][0]
            name = self.names[self.at] if what == "cell" else self.button_name
            if box == FULL:
                cells = " ".join(f"{i + 1} {v}" for i, v in enumerate(self.values))
                return self.table_text or f"Mode Dial Control Set {cells} {BUTTONS[0]} {name} {BUTTONS[1]}"
            if box == NAME_BOX:
                return name
            return f"{self.at + 1} {self.values[self.at]}" if what == "cell" else BUTTONS[self.at - 3]
        if self.kind == "list":
            if box == FULL:
                return f"Shooting Mode Dial o {DIAL} • {MENU_OPT} MENU"
            saved = [DIAL, MENU_OPT].index(self.values[self.at])
            return f"{'o' if self.option == saved else '•'} {[DIAL, MENU_OPT][self.option]}"
        if self.kind == "menu":
            return "Setup > Accessibility Screen Reader Mode Dial Control Set MENU"
        return "Made-up screen"


@pytest.fixture
def camera(ms, monkeypatch, tmp_path):
    """A DialCam maker: OCR reads it, the menu row is found, the table walk is a file of the test's own."""
    from camkit import live, ocr
    from proving import base
    walk = tmp_path / "tables.json"
    walk.write_text(json.dumps({"Mode Dial Control Set": {"cells": [
        {"pos": [212, y], "row_label": d} for y, d in zip(CELL_Y, DIALS, strict=True)]}}), encoding="utf-8")
    monkeypatch.setattr(base, "TABLES", walk)
    monkeypatch.setattr(ms, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(ms, "lit_text", lambda image, path: "Mode Dial Control Set")
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    made = {}

    def make(**kw):
        made["cam"] = DialCam(**kw)
        return made["cam"]
    monkeypatch.setattr(ocr, "read", lambda ps, eng=None: {p: made["cam"] for p in ps})
    monkeypatch.setattr(ocr, "text_in", lambda cam, box: cam.words(box))
    return make


def closed_by_menu_alone(cam):
    """runner.close_screen after a failed dial_by_menu, as main() closes it: every key it sends is MENU."""
    import runner
    before = len(cam.keys)
    runner.close_screen(cam, cam.link)
    sent = cam.keys[before:]
    assert sent and set(sent) == {"menu"} and cam.kind == "shooting", sent


def test_the_table_puts_the_shooting_mode_dials_cell_alone_on_set_with_menu(ms, camera):
    """Right gives the table, lit on the Shooting Mode Dial's cell (00016_right.png): Enter on that cell, Down to Set
    with Menu, Enter, the table back with the cell on it, MENU to the menu page; nothing else goes out, and the other
    dials keep theirs."""
    cam, said = camera(), []
    ms.dial_by_menu(cam, None, None, said.append)
    assert cam.keys == ["right", "enter", "down", "enter", "menu"] and cam.kind == "menu"
    assert cam.values == [MENU_OPT, DIAL, DIAL]
    assert said == ["Mode Dial Control Set / Shooting Mode Dial: choosing 'Set with Menu'"]


def test_a_cell_already_on_set_with_menu_gets_no_enter(ms, camera):
    cam, said = camera(values=(MENU_OPT, DIAL, DIAL)), []
    ms.dial_by_menu(cam, None, None, said.append)
    assert cam.keys == ["right", "menu"] and cam.kind == "menu"
    assert said == ["Mode Dial Control Set / Shooting Mode Dial: already 'Set with Menu', nothing chosen"]


def test_a_table_lit_on_set_all_with_menu_is_stepped_to_the_cell_and_entered_there_alone(ms, camera):
    """The table opened lit on Set All with Menu: Up to the Shooting Mode Dial's cell (proving.tables.to_cell, the
    walk's place) and Enter there alone; the made-up camera fails the test on any Enter on a button."""
    cam = camera(lit=4)
    ms.dial_by_menu(cam, None, None, lambda m: None)
    assert cam.keys == ["right", "up", "up", "up", "up", "enter", "down", "enter", "menu"]
    assert cam.values == [MENU_OPT, DIAL, DIAL]


def test_a_set_all_button_read_beside_the_dials_name_gets_no_enter(ms, camera, monkeypatch):
    """Even with the way to the cell taken for done and the Shooting Mode Dial's name read beside a lit Set All with
    Menu, the lit item is a button, no cell: the switch stops, no Enter, and only MENU follows."""
    from prove_run import Failed
    from proving import tables
    cam = camera(lit=4, button_name="Shooting Mode Dial")
    monkeypatch.setattr(tables, "to_cell", lambda cam, cell, **kw: None)
    with pytest.raises(Failed, match="the lit cell is not the Shooting Mode Dial"):
        ms.dial_by_menu(cam, None, None, lambda m: None)
    assert cam.keys == ["right"] and cam.values == [DIAL, DIAL, DIAL]
    closed_by_menu_alone(cam)


@pytest.mark.parametrize("kw,match,keys", [
    # the walk's place for the Shooting Mode Dial holds a cell whose name reads another dial
    ({"names": ["Drive Mode Dial", "Shooting Mode Dial", "Focus Mode Dial"]}, "the lit cell is not the Shooting Mode Dial",
     ["right"]),
    ({"names": ["", "", ""]}, "the lit cell is not the Shooting Mode Dial", ["right"]),          # its name unread
    ({"values": ("Made-up", DIAL, DIAL)}, "reads neither", ["right"]),                          # its option unread
    ({"enter_opens": "unknown"}, "Enter opened unknown, not its list", ["right", "enter"]),
    ({"enter_opens": "notice"}, "Enter opened notice, not its list", ["right", "enter"]),
    # the choice not taken: the cell still on Set with Dial when the table comes back
    ({"ignores_choice": True}, "after OK its cell does not read 'Set with Menu'", ["right", "enter", "down", "enter"]),
], ids=["other-dial", "name-unread", "option-unread", "enter-unknown", "enter-notice", "choice-not-taken"])
def test_what_cannot_be_verified_stops_the_switch_and_only_menu_follows(ms, camera, kw, match, keys):
    from prove_run import Failed
    cam = camera(**kw)
    with pytest.raises(Failed, match=match) as got:
        ms.dial_by_menu(cam, None, None, lambda m: None)
    assert cam.keys == keys
    assert "Made-up" not in str(got.value)          # the cell's reading, the camera's own, is never in the message
    if "values" in kw:
        assert cam.logged == [("dial_cell_unread", {"step": "Mode Dial Control Set / Shooting Mode Dial",
                                                    "frame": "00002_right.png", "cell": "1 Made-up"})]
    closed_by_menu_alone(cam)


def test_a_dial_table_needs_the_table_walk(ms, camera, monkeypatch, tmp_path):
    """No walk of Mode Dial Control Set (kit2_tables): the switch stops on the table with nothing pressed there."""
    from prove_run import Failed
    from proving import base
    monkeypatch.setattr(base, "TABLES", tmp_path / "none.json")
    cam = camera()
    with pytest.raises(Failed, match="is not in the table walk"):
        ms.dial_by_menu(cam, None, None, lambda m: None)
    assert cam.keys == ["right"]
    closed_by_menu_alone(cam)


def test_another_table_is_refused_as_before(ms, camera, monkeypatch):
    """A table without the Set All buttons' words is no dial table: handed to pass_note, which refuses it, as before."""
    from prove_run import Failed
    from proving import screens
    cam = camera(table_text="Mode Dial Control Set Made-up table")
    monkeypatch.setattr(screens, "pass_note", lambda cam, row, lit, **kw: {"refused": "not a notice (table)"})
    with pytest.raises(Failed, match="showed a note not passed: not a notice"):
        ms.dial_by_menu(cam, None, None, lambda m: None)
    assert cam.keys == ["right"]


def test_the_list_path_is_as_it_was(ms, camera):
    """Right gives the two-option list: Down to Set with Menu, OK, as before the table."""
    cam, said = camera(right="list"), []
    ms.dial_by_menu(cam, None, None, said.append)
    assert cam.keys == ["right", "down", "enter"] and cam.kind == "menu"
    assert said == ["Mode Dial Control Set: choosing 'Set with Menu'"]


def test_a_cells_option_is_read_without_its_dials_number():
    from proving import tables
    for read in ("1 Set with Menu", "① Set with Menu", "(1) Set with Menu", "Set with Menu", "I Set with Menu"):
        assert tables.dial_option(read) == "Set with Menu", read
    assert tables.dial_option("3 Set with Dial") == "Set with Dial"


# ---------------------------------------------------------------- the camera's own frames

A1 = paths.a1ii_root()
TODAY = A1 / "kit2_a1fin_movie_m" / "shots" / "00016_right.png"          # the table as Right opens it, 2026-11-15
SWITCH = A1 / "kit2_diffset_movie_switch_m" / "shots"                      # drive.py's presses one by one, 2026-11-14
BUTTON = A1 / "kit2_tables" / "shots" / "08440_down.png"                   # the table walk's: Set All with Menu lit
KINDS = [(TODAY, "table"), (SWITCH / "00020_right.png", "table"), (SWITCH / "00021_enter.png", "list"),
         (SWITCH / "00022_down.png", "list"), (SWITCH / "00023_enter.png", "table"), (SWITCH / "00026_menu.png", "menu")]


def need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def frame_cam(path: Path):
    from camkit import screen
    from camkit.frames import load
    f = load(need(path))
    s = screen.read(f)
    return SimpleNamespace(frame=f, read=lambda: s)


@pytest.mark.parametrize("path,kind", KINDS, ids=[p.name for p, _ in KINDS])
def test_the_frames_read_as_the_steps_kinds(path, kind):
    """Right: the table; Enter on the lit cell: its list; Down: Set with Menu lit; Enter: the table; MENU: the menu."""
    assert frame_cam(path).read().kind == kind


def test_the_frames_pass_the_tables_recognition_and_the_dials_check(ms):
    """On the camera's frames, read by this computer's OCR: 00016_right.png is the dial table, lit on the Shooting Mode
    Dial's cell (not the Drive Mode Dial's), on Set with Dial, reading as no confirmation; Down in its list lights Set
    with Menu; after OK the cell reads Set with Menu; and the walk's frame with Set All with Menu lit is no dial's cell."""
    from camkit import ocr, safety
    from prove_run import Failed
    from proving import tables
    need(TODAY)
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    for path, option in ((TODAY, DIAL), (SWITCH / "00020_right.png", DIAL), (SWITCH / "00023_enter.png", MENU_OPT)):
        cam = frame_cam(path)
        assert tables.dial_table(cam.read().kind, ms.text(cam)), path.name
        assert not safety.confirmation(ms.text(cam)), path.name
        tables.on_dial_cell(cam, "Shooting Mode Dial")
        assert ms.option_key(tables.dial_option(tables.cell_value(cam))) == ms.option_key(option), path.name
        with pytest.raises(Failed, match="not the Drive Mode Dial"):
            tables.on_dial_cell(cam, "Drive Mode Dial")
    assert ms.option_key(ms.bar_text(frame_cam(SWITCH / "00022_down.png"))) == ms.option_key(MENU_OPT)
    assert ms.option_key(ms.bar_text(frame_cam(SWITCH / "00021_enter.png"))) != ms.option_key(MENU_OPT)
    button = frame_cam(BUTTON)
    assert tables.dial_table(button.read().kind, ms.text(button)) and button.read().focus == "button"
    with pytest.raises(Failed, match="the lit cell is not the Shooting Mode Dial"):
        tables.on_dial_cell(button, "Shooting Mode Dial")
