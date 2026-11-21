"""kit/crawl_run.py --leave PATH: a row the run names is left unopened, its rows with it, nothing pressed on it, and its
outcome says so (camkit.crawl.LEFT), which the run's rows.jsonl keeps and the menu tree reads as a row left on
purpose, not one missed. For File Settings without Title Name Settings, whose entries open keyboards (never opened).
The scripted fake menu of test_core; nothing talks to a camera."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "tests"))
sys.path.insert(2, str(ROOT / "kit" / "tools"))
from test_core import FakeMenu  # noqa: E402


def lap(monkeypatch, leave, menu=None):
    import camkit.crawl as C
    monkeypatch.setattr(C, "LEAVE", tuple(tuple(p) for p in leave))
    fake = menu or FakeMenu(True)
    cycle = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
                   "rows": [{"label": x, "never_open": None} for x in FakeMenu.TOP]}}
    return C, fake, C.crawl(fake, cycle, model, labels=fake.labels)


def rights_on(fake, where) -> int:
    return sum(1 for w, k in fake.pressed if w == where and k == "right")


def test_a_submenu_row_the_run_names_is_left_unopened_and_said(monkeypatch):
    C, fake, out = lap(monkeypatch, [("Sub", "S1")])
    sub = {r.label: r.outcome for r in next(r for r in out.rows if r.label == "Sub").walk.rows}
    assert sub["S1"] == f"skipped: {C.LEFT}" and rights_on(fake, ("sub", 0)) == 0
    assert sub["S4"] == "walked" and out.stopped == ""


def test_a_top_row_the_run_names_is_left_with_every_row_under_it(monkeypatch):
    C, fake, out = lap(monkeypatch, [("Sub",)])
    outcomes = {r.label: r.outcome for r in out.rows}
    assert outcomes == {"A": "walked", "Sub": f"skipped: {C.LEFT}", "B": "walked"}
    assert rights_on(fake, ("top", 1)) == 0 and not any(w[0] == "sub" for w, k in fake.pressed)


class GluedMenu(FakeMenu):
    SUB = ["S1", "S2 greyed", "Forced File Number Reset", "Px S4"]     # an icon read as letters before S4
    LISTS = {**FakeMenu.LISTS, "Px S4": 2}


def test_a_live_label_read_with_an_icon_glued_on_is_still_the_row_named(monkeypatch):
    """The live label is a reading: matched as the scan's rows are (page_model.same_text), so an icon OCR reads as a
    capital and a small letter before the label does not let the row open."""
    C, fake, out = lap(monkeypatch, [("Sub", "S4")], GluedMenu(True))
    sub = {r.label: r.outcome for r in next(r for r in out.rows if r.label == "Sub").walk.rows}
    assert sub["Px S4"] == f"skipped: {C.LEFT}" and rights_on(fake, ("sub", 3)) == 0


def test_nothing_named_leaves_the_lap_as_before(monkeypatch):
    C, fake, out = lap(monkeypatch, [])
    assert {r.label: r.outcome for r in out.rows} == {"A": "walked", "Sub": "submenu crawled", "B": "walked"}


def test_the_menu_tree_reads_a_left_row_as_left_on_purpose():
    import camkit.crawl as C
    import menu_tree
    assert menu_tree.state_of({"outcome": f"skipped: {C.LEFT}"}, False) == ("never", C.LEFT)


def test_a_path_the_kit_does_not_know_is_refused_before_the_link_opens():
    """--leave names rows by their paths; one whose top row the scan does not hold, or whose path neither this body's
    records nor the definition know, is a typo that would let the row open: refused, nothing sent."""
    import crawl_run
    model = {"P": {"rows": [{"label": "File Settings"}, {"label": "Shoot Mode"}]}}
    doc = {"settings": [{"row": ["File Settings", "Title Name Settings"]}, {"row": ["File Settings", "File Number"]}]}
    seen = type("Seen", (), {"seen": staticmethod(lambda path: False)})()
    assert crawl_run.leave_paths(["File Settings > Title Name Settings"], model, seen, doc) == \
        (("File Settings", "Title Name Settings"),)
    with pytest.raises(SystemExit, match="File Setings"):
        crawl_run.leave_paths(["File Setings > Title Name Settings"], model, seen, doc)
    with pytest.raises(SystemExit, match="Title Nme Settings"):
        crawl_run.leave_paths(["File Settings > Title Nme Settings"], model, seen, doc)
    seen_all = type("Seen", (), {"seen": staticmethod(lambda path: True)})()
    assert crawl_run.leave_paths(["Shoot Mode > Whatever Seen"], model, seen_all, {"settings": []}) == \
        (("Shoot Mode", "Whatever Seen"),)
