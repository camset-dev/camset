"""mode_switch --set on a row whose Right opens a side-strip dialog (Picture Profile on the a1 II: a column of icons at
the left, the entry's name in orange under the title; calib_grey_looks 2026-11-21, kit2_calib_mv 00060_right.png),
not a list: Down until the title names the option by the labels the mode's map gives the row (dialog_labels; the
provers' own dialog reading, proving.options.option_index), the entry judged on the frame Enter would go on
(proving.greyed.choice_refused: drawn grey or not told is no choice, MENU alone), then OK. Made-up cameras, and the
camera's own frames where they are here; nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import load  # noqa: E402

A1 = paths.a1ii_root()
PP = ["Off", "PP1", "PP2", "PP3", "PP4", "PP5", "PP6", "PP10", "PP11", "User1: (No Import)", "User2: (No Import)",
      "User3: (No Import)", "User4: (No Import)"]             # kit2_crawl_movie's map, Picture Profile in Movie


class DialogCam:
    """A made-up camera on a menu row whose Right opens a dialog of `options` on `start`; Down moves round it, OK
    chooses and leaves for the menu page (or, with stuck=True, leaves the dialog open); MENU closes it unchosen."""

    def __init__(self, options, start=0, stuck=False):
        self.options, self.at, self.stuck, self.kind = options, start, stuck, "menu"
        self.presses, self.logged, self.chosen, self.n = [], [], None, 0
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    @property
    def frame(self):
        return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def refresh(self, tag):
        return self.read()

    def press(self, key, **kw):
        self.presses.append(key)
        self.n += 1
        if key == "right":
            self.kind = "dialog"
        elif key == "down":
            self.at = (self.at + 1) % len(self.options)
        elif key == "enter" and not self.stuck:
            self.chosen, self.kind = self.options[self.at], "menu"
        elif key == "menu":
            self.kind = "menu"


@pytest.fixture
def ms(monkeypatch):
    import mode_switch
    from proving import greyed
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "row_drawn", lambda cam: (False, 240.0))
    monkeypatch.setattr(mode_switch, "dialog_labels", lambda path, mode="Stills": PP)
    monkeypatch.setattr(mode_switch, "dialog_at", lambda cam, labels: cam.at)
    monkeypatch.setattr(mode_switch, "dialog_title", lambda cam: f"title of {cam.options[cam.at]}")
    monkeypatch.setattr(greyed, "choice_refused", lambda cam, name, label: "")
    return mode_switch


def test_a_dialog_row_is_set_by_its_title_and_ok(ms):
    """--set "Picture Profile=PP11" on the PP dialog opened on Off: Right, Down until the title names PP11 (the map's
    ninth label), OK; the choice said as a list's is."""
    said = []
    cam = DialogCam(PP, start=0)
    ms.set_row(cam, None, None, ["Picture Profile"], "PP11", said.append, mode="Movie")
    assert cam.chosen == "PP11" and cam.presses == ["right"] + ["down"] * 8 + ["enter"]
    assert said == ["Picture Profile: choosing 'PP11'"]


def test_a_dialog_already_on_the_option_takes_ok_at_once(ms):
    cam = DialogCam(PP, start=8)
    ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert cam.chosen == "PP11" and cam.presses == ["right", "enter"]


def test_an_entry_drawn_grey_in_the_dialog_is_not_chosen_and_menu_closes_it(ms, monkeypatch):
    """The entry under the cursor judged on the frame Enter would go on (greyed.choice_refused): its refusal is the
    run's failure, MENU the only press after the Downs, no Enter."""
    from prove_run import Failed
    from proving import greyed
    monkeypatch.setattr(greyed, "choice_refused", lambda cam, name, label: (
        f"{name}: {label!r} is drawn grey (its lit icon, it reads 102, x.png), and a greyed entry is never entered to "
        "choose it: nothing was pressed on it"))
    cam = DialogCam(PP, start=0)
    with pytest.raises(Failed, match="'PP11' is drawn grey") as e:
        ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert "enter" not in cam.presses and cam.presses[-1] == "menu" and cam.chosen is None
    assert "MENU closed the dialog" in str(e.value)


def test_an_option_the_map_does_not_list_is_refused_before_any_down(ms, monkeypatch):
    """No label for the option (or no map of the mode holding the row as a dialog): nothing walked, MENU, the failure
    names what was missing."""
    from prove_run import Failed
    cam = DialogCam(PP, start=0)
    with pytest.raises(Failed, match="PP9.*not among the labels"):
        ms.set_row(cam, None, None, ["Picture Profile"], "PP9", lambda m: None, mode="Movie")
    assert cam.presses == ["right", "menu"]
    monkeypatch.setattr(ms, "dialog_labels", lambda path, mode="Stills": None)
    cam = DialogCam(PP, start=0)
    with pytest.raises(Failed, match="no map of the Movie menu holds 'Picture Profile' as a dialog"):
        ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert cam.presses == ["right", "menu"]


def test_a_title_that_never_names_the_option_stops_after_one_round_its_reading_in_the_events(ms, monkeypatch):
    """The title read as no one label all round (the dialog wraps): one round and two more Downs at most, then MENU;
    what the title read (which can be the owner's entry) goes to the run's events.jsonl only."""
    from prove_run import Failed
    monkeypatch.setattr(ms, "dialog_at", lambda cam, labels: None)
    cam = DialogCam(PP, start=3)
    with pytest.raises(Failed, match="did not come round in its dialog") as e:
        ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert cam.presses.count("down") == len(PP) + 2 and cam.presses[-1] == "menu" and "enter" not in cam.presses
    last = PP[(3 + len(PP) + 2) % len(PP)]              # the entry on show when the round gave up
    assert last not in str(e.value) and "PP3" not in str(e.value)
    assert cam.logged and cam.logged[0][0] == "set_row_missed" and cam.logged[0][1]["title"] == f"title of {last}"


def test_an_ok_the_dialog_leaves_unanswered_stops_the_step(ms):
    from prove_run import Failed
    cam = DialogCam(PP, start=8, stuck=True)
    with pytest.raises(Failed, match="OK on 'PP11' went unanswered, its dialog still open"):
        ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert cam.presses == ["right", "enter"]


def test_a_screen_neither_list_nor_dialog_still_stops_as_before(ms):
    from prove_run import Failed

    class Other(DialogCam):
        def press(self, key, **kw):
            super().press(key, **kw)
            if key == "right":
                self.kind = "unknown"
    cam = Other(PP)
    with pytest.raises(Failed, match="opened unknown, not a list or a dialog"):
        ms.set_row(cam, None, None, ["Picture Profile"], "PP11", lambda m: None, mode="Movie")
    assert cam.presses == ["right"]


def test_dialog_labels_are_the_maps_labels_for_a_dialog_row_only(monkeypatch):
    """dialog_labels: the labels of the mode's map where it holds the row as a dialog (pass3_run.labels_of), None for a
    list row or no map; list_labels keeps answering None for a dialog row (a list's walk never takes them)."""
    import mode_switch
    import pass3_run
    import framepos_run
    monkeypatch.setattr(framepos_run, "mode_map", lambda mode, path=None: "map.json")
    kinds = {("Picture Profile",): (PP, "dialog"), ("File Format",): (["XAVC S HD"], "list")}
    monkeypatch.setattr(pass3_run, "labels_of", lambda path, mp: kinds[tuple(path)])
    assert mode_switch.dialog_labels(["Picture Profile"], "Movie") == PP
    assert mode_switch.dialog_labels(["File Format"], "Movie") is None
    assert mode_switch.list_labels(["Picture Profile"], "Movie") is None
    monkeypatch.setattr(framepos_run, "mode_map", lambda mode, path=None: None)
    assert mode_switch.dialog_labels(["Picture Profile"], "Movie") is None


@pytest.mark.parametrize("run, name, grey", [
    ("kit2_calib_mv", "00060_right.png", False),          # Picture Profile's dialog in Movie, opened on Off
    ("kit2_calib_flash", "00019_down.png", True),         # Flash Mode in Stills M: Flash Off, greyed by the mode
    ("kit2_calib_flash", "00020_down.png", True),         # Autoflash, greyed by the mode
    ("kit2_calib_flash", "00018_down.png", False),        # Rear Sync., taken
])
def test_the_cameras_own_dialogs_read_as_dialogs_and_their_lit_icon_as_the_camera_draws_it(run, name, grey):
    """calib_grey_looks' frames (2026-11-21): the PP dialog reads as a dialog, its lit icon white; Flash Mode's dialog
    in Stills M with Flash Off and Autoflash lit reads them grey (102, 116) and Rear Sync. white (218), the grey the
    camera draws on demand that choice_refused judges a dialog's entry by."""
    from proving import greyed
    f = A1 / run / "shots" / name
    if not f.exists():
        pytest.skip(f"{f.name} is not here")
    frame = load(f)
    cam = SimpleNamespace(frame=frame, read=lambda: screen.read(frame))
    assert cam.read().kind == "dialog"
    got, level, how = greyed.choice_drawing(cam)
    assert got is grey and level is not None and how == "its lit icon"
