"""optboxes_run.step_to judges each reading against where a press can land (close_zebra_sq, 2026-11-20): Zebra Level >
Custom 1's Range stepped from ±10 down to ±4 in S&Q mode read "±7" as "‡1" (kit2_pass2 275820, 275823, 275826, 275831),
a value of the box, which step_to took without the reader; ±1 being below ±4 it pressed Up, and went round ±7 and ±8
until its presses ran out ("box 2: '±4' never came up"). A reading no press from the last value can bring is put to
the reader before it counts. Made-up camera and reader; the run's own frames where this clone has them. Nothing talks to
a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import optboxes_run as O  # noqa: E402
from camkit import paths  # noqa: E402

RANGE = [f"±{i}" for i in range(1, 11)]          # the Range box's values in Up order (the probe's)
MISREAD = {"±7": "‡1"}                            # OCR's reading of the box on the run's frames


class RangeBox:
    """Box 2 of Zebra Level's Custom 1 at `held`: Up and Down step it one value, an end staying; OCR reads it as the
    camera's OCR read it (MISREAD), the reader reads it rightly."""

    def __init__(self, held="±10"):
        self.i, self.keys, self.asked = RANGE.index(held), [], 0
        self.frame = SimpleNamespace(path=Path("00001_x.png"))

    @property
    def value(self):
        return RANGE[self.i]


def seams(monkeypatch, box):
    monkeypatch.setattr(O, "in_box", lambda cam, option, name, b: None)
    monkeypatch.setattr(O, "read_at", lambda cam, b: MISREAD.get(box.value, box.value))

    def ask(cam):
        box.asked += 1
        return box.value, "vllm", False
    monkeypatch.setattr(O, "ask_box", ask)

    def press(cam, key, option, names, b, vals=None):
        box.keys.append(key)
        box.i = min(len(RANGE) - 1, box.i + 1) if key == "up" else max(0, box.i - 1)
    monkeypatch.setattr(O, "press_in", press)


def test_a_misread_value_no_press_can_bring_goes_to_the_reader_and_the_target_comes_up(monkeypatch):
    box = RangeBox("±10")
    seams(monkeypatch, box)
    O.step_to(box, 2, RANGE, "±4", ["Type", "Standard", "Range"], "Custom 1")
    assert box.value == "±4" and box.keys == ["down"] * 6, box.keys
    assert box.asked == 1, "the reader asked once, on the misread ±7"


def test_a_plain_walk_asks_no_reader(monkeypatch):
    box = RangeBox("±1")
    seams(monkeypatch, box)
    O.step_to(box, 2, RANGE, "±4", ["Type", "Standard", "Range"], "Custom 1")
    assert box.value == "±4" and box.keys == ["up"] * 3 and box.asked == 0


def test_the_first_reading_is_judged_as_before(monkeypatch):
    """Before any press, any value of the box is taken from OCR alone, as step_to always did."""
    box = RangeBox("±4")
    seams(monkeypatch, box)
    O.step_to(box, 2, RANGE, "±4", ["Type", "Standard", "Range"], "Custom 1")
    assert box.keys == [] and box.asked == 0


def test_ocr_reads_the_runs_seven_as_a_one():
    f = paths.a1ii_root() / "kit2_pass2" / "shots" / "275820_down.png"
    if not f.exists():
        pytest.skip("kit2_pass2's frames are not here")
    from camkit import live, ocr
    lines = ocr.read([f])[f]
    box = [ln.text for ln in lines if ln.x > 480 and 330 < ln.y < 420]
    assert box and live.box_value(box[0], "±4") == "±1", box
