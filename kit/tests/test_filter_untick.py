"""The pure parts of filter_run --untick: no camera, made-up screen states."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provers"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import filter_run as fr  # noqa: E402


def test_box_column_state():
    # the square on a box: focus rows, a row, no bar across it (boxes empty)
    assert fr.box_column_state("checklist", "rows", 4, [], ["empty"] * 4 + ["ticked", "empty"]) is True
    assert fr.box_column_state("checklist", "rows", 2, [], ["empty"] * 4 + ["ticked", "empty"]) is False
    # the value column: a bar across the row
    assert fr.box_column_state("checklist", "rows", 4, [(20, 600)], ["empty"] * 4 + ["ticked"]) is None
    assert fr.box_column_state("list", "rows", 4, [], ["ticked"] * 5) is None
    assert fr.box_column_state("checklist", "button", None, [], ["empty"]) is None
    assert fr.box_column_state("checklist", "rows", 9, [], ["empty"]) is None


def test_box_key_and_applied():
    d = {"settings": [{"key": "global:0x1294", "name": "Playback Filter Condition: Protect (box)"},
                      {"key": "global:0x12be", "name": "Playback Filter Condition: Protect never set"}]}
    assert fr.box_key(d, "Protect") == "global:0x1294"
    assert fr.box_key(d, "Rating") is None
    ch = [{"key": "global:0x1294", "before": 1, "after": 0}, {"key": "global:0x12be", "before": 0, "after": 1}]
    assert fr.untick_applied(ch, "global:0x1294")
    assert not fr.untick_applied(ch[1:], "global:0x1294")
    assert not fr.untick_applied([{"key": "global:0x1294", "before": 0, "after": 1}], "global:0x1294")
    assert fr.untick_applied(ch, None)


class FakeFilter:
    """Playback Filter Condition as untick_item meets it, in made-up states: the menu, the checklist with its cursor in
    the box column (a square on the box: no bar) or the value column (a bar across the row), and the chooser. Left and
    Right move between the columns; Enter in the box column ticks or unticks the box, in the value column opens the
    chooser, whose Enter chooses its option in force: the box ticked, the cursor back in the value column."""

    def __init__(self, item: int, ticked: bool, column: str = "value"):
        self.item, self.ticked, self.column, self.kind, self.n = item, ticked, column, "menu", 0
        self.keys, self.held = [], {}
        self.frame = type("F", (), {"path": Path("00000.png")})()

    def read(self):
        from types import SimpleNamespace
        slots = ["empty"] * len(fr.ITEMS)
        slots[self.item] = "ticked" if self.ticked else "empty"
        return SimpleNamespace(kind=self.kind, focus="rows", row=self.item,
                               boxes=[(20, 600)] if self.column == "value" else [], slots=slots, bar=(100, 140))

    def press(self, key):
        self.keys.append(key)
        self.n += 1
        self.frame = type("F", (), {"path": Path(f"{self.n:05d}_{key}.png")})()
        if self.kind == "checklist":
            if key == "left":
                self.column = "box"
            elif key == "right" and self.column == "box":
                self.column = "value"
            elif key in ("right", "enter") and self.column == "value":
                self.kind = "list"
            elif key == "enter":
                self.ticked = not self.ticked
            elif key == "menu":
                self.kind = "menu"
        elif self.kind == "list" and key == "enter":
            self.kind, self.column, self.ticked = "checklist", "value", True


def run_untick(monkeypatch, cam):
    """untick_item on cam with the camera's other parts made up: each download holds the box's state then."""
    import io
    from types import SimpleNamespace
    held = {}

    def download(link, name, say):
        held[name] = int(cam.ticked)
        return Path(f"{len(held):05d}_{name}.DAT")

    def diff(a, b):
        before, after = held[a.stem.split("_", 1)[1]], held[b.stem.split("_", 1)[1]]
        return [SimpleNamespace(key="global:0x0001", before=before, after=after)] if before != after else []

    def open_row(c, cycle, model):
        assert c.kind == "menu"
        c.kind = "checklist"                     # it reopens in the column used last
    monkeypatch.setattr(fr, "download", download)
    monkeypatch.setattr(fr, "after_download", lambda c, t: None)
    monkeypatch.setattr(fr, "open_row", open_row)
    monkeypatch.setattr(fr, "to_box", lambda c, i: None)
    monkeypatch.setattr(fr, "box_label", lambda c: fr.ITEMS[c.item] if c.kind == "checklist" else "")
    monkeypatch.setattr(fr, "vlm_option", lambda c: "")
    monkeypatch.setattr(fr, "camset", SimpleNamespace(read=lambda path: path, diff=diff))
    finished = []
    monkeypatch.setattr(fr, "finish_attempt", lambda run, attempt, name, notes: finished.append(name))
    out = io.StringIO()
    run = SimpleNamespace(dir=Path("kit2_made_up"))
    applied = fr.untick_item(cam, None, run, None, None, cam.item, "global:0x0001", out, lambda m: None)
    import json
    return applied, [json.loads(x) for x in out.getvalue().splitlines()], held, finished


def test_untick_item_unticks_a_ticked_box_and_proves_value_0(monkeypatch):
    protect = fr.ITEMS.index("Protect")
    cam = FakeFilter(protect, ticked=True)
    applied, lines, held, finished = run_untick(monkeypatch, cam)
    assert applied and not cam.ticked and "right" not in cam.keys, "no chooser opened: the box was ticked"
    (line,) = lines
    assert (line["label"], line["index"], line["untick"], line["applied"]) == ("Not ticked", 0, True, True)
    assert line["changes"] == [{"key": "global:0x0001", "before": 1, "after": 0}] and finished


def test_untick_item_ticks_an_unticked_box_again_from_its_chooser_first(monkeypatch):
    protect = fr.ITEMS.index("Protect")
    cam = FakeFilter(protect, ticked=False)
    applied, lines, held, finished = run_untick(monkeypatch, cam)
    assert applied and not cam.ticked
    assert list(held.values()) == [0, 1, 0], "the first download unticked, the second ticked again, the last unticked"
    (line,) = lines
    assert line["base"].endswith("untick-before2.DAT") and line["changes"][0]["before"] == 1


def test_untick_item_will_not_tick_ratings_grid_again(monkeypatch):
    import pytest
    cam = FakeFilter(fr.ITEMS.index("Rating"), ticked=False)
    with pytest.raises(fr.Failed, match="Rating"):
        run_untick(monkeypatch, cam)
