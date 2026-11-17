"""An option named from a list row's reading where the row draws an icon OCR reads as text (camkit.match.icon_named) and
mode_switch.set_row choosing such an option: the a1 II's Aspect Ratio list draws a boxed ratio before each ratio, and
its lit bar reads "3:2 3:2" (runs/ILCE-1M2_fw4.00/kit2_a1fin_probe_keep 00082_down.png, 2026-11-17). Made-up cameras;
nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import match  # noqa: E402

RATIOS = ["3:2", "4:3", "16:9", "1:1"]          # pass 1's labels for Aspect Ratio


@pytest.mark.parametrize("i,label", list(enumerate(RATIOS)))
def test_a_ratio_read_twice_names_that_ratio(i, label):
    """The icon read as the label in front of it: the reading names the label, its radio ring in front or not."""
    assert match.icon_named(RATIOS, f"{label} {label}") == i
    assert match.icon_named(RATIOS, f"o {label} {label}") == i
    assert match.icon_named(RATIOS, label) == i


def test_a_near_miss_names_no_other_ratio():
    """Digits are compared exactly: "1:1" read twice is 1:1, never 16:9; "6:9" (a 1 lost) names no ratio, read once or
    twice; an icon and a label that name two ratios name none."""
    assert match.icon_named(RATIOS, "1:1 1:1") == 3
    assert match.icon_named(RATIOS, "6:9") is None and match.icon_named(RATIOS, "6:9 6:9") is None
    assert match.icon_named(RATIOS, "4:3 16:9") is None
    assert match.icon_named(RATIOS, "") is None


def test_a_plain_list_row_is_named_as_before():
    """A row with no icon: named whole as camkit.match.index_of names it, the radio ring left out; a reading that names
    one option whole is never cut ("Auto Manual" is that option, not Manual)."""
    dial = ["Set with Dial", "Set with Menu"]
    assert match.icon_named(dial, "o Set with Dial") == 0 and match.icon_named(dial, "Set with Menu") == 1
    assert match.icon_named(["Auto", "Manual", "Auto Manual"], "Auto Manual") == 2
    assert match.icon_named(dial, "Set with Wheel") is None


class ListCam:
    """A made-up camera on a menu row whose list holds `options`, its bar read as `bar(option)`; Right opens the list on
    `start`, Down moves the cursor round it, OK chooses and leaves for the menu page."""

    def __init__(self, options, start=0, bar=lambda o: f"{o} {o}"):
        self.options, self.at, self.bar, self.kind = options, start, bar, "menu"
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
            self.kind = "list"
        elif key == "down":
            self.at = (self.at + 1) % len(self.options)
        elif key == "enter":
            self.chosen, self.kind = self.options[self.at], "menu"


@pytest.fixture
def ms(monkeypatch):
    import mode_switch
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "bar_text", lambda cam: cam.bar(cam.options[cam.at]))
    monkeypatch.setattr(mode_switch, "list_labels", lambda path: RATIOS if path == ["Aspect Ratio"] else None)
    return mode_switch


@pytest.mark.parametrize("want", RATIOS)
def test_set_row_chooses_a_ratio_its_bar_reads_twice(ms, want):
    """--set "Aspect Ratio=16:9": Down until the bar reading names the option by pass 1's labels for the row
    (list_labels), OK on it; a row already on it is found at once."""
    cam = ListCam(RATIOS)
    ms.set_row(cam, None, None, ["Aspect Ratio"], want, lambda m: None)
    assert cam.chosen == want and cam.presses == ["right"] + ["down"] * RATIOS.index(want) + ["enter"]
    cam = ListCam(RATIOS, start=RATIOS.index(want))
    ms.set_row(cam, None, None, ["Aspect Ratio"], want, lambda m: None)
    assert cam.chosen == want and cam.presses == ["right", "enter"]


def test_set_row_with_no_labels_for_the_row_matches_as_before_and_fails_closed(ms):
    """A row pass 1's map does not hold: the bar is compared with the option as before (the radio ring left out), so a
    doubled reading never comes round and the step stops as now, the bar's text in the run's events alone."""
    from prove_run import Failed
    cam = ListCam(RATIOS)
    with pytest.raises(Failed, match=r"'Made-up Ratio': '16:9' did not come round in its list") as got:
        ms.set_row(cam, None, None, ["Made-up Ratio"], "16:9", lambda m: None)
    assert "3:2" not in str(got.value) and cam.chosen is None
    assert [f["bar"] for k, f in cam.logged if k == "set_row_missed"] == ["3:2 3:2"]
    plain = ListCam(["Set with Dial", "Set with Menu"], bar=lambda o: f"o {o}" if o == "Set with Dial" else o)
    ms.set_row(plain, None, None, ["Made-up Dial"], "Set with Menu", lambda m: None)
    assert plain.chosen == "Set with Menu" and plain.presses == ["right", "down", "enter"]


def test_set_row_never_takes_a_near_miss_for_the_option(ms):
    """A list whose bars read "6:9" (a 1 lost) or "1:1 1:1" never names 16:9: the step goes round and stops."""
    from prove_run import Failed
    cam = ListCam(RATIOS, bar=lambda o: "6:9 6:9" if o == "16:9" else f"{o} {o}")
    with pytest.raises(Failed, match="did not come round"):
        ms.set_row(cam, None, None, ["Aspect Ratio"], "16:9", lambda m: None)
    assert cam.chosen is None
