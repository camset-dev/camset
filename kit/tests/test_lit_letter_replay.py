"""The lit one-letter row in the prover's real order of calls, replayed on the frames pp_colordepth_sqc recorded
(2026-11-21, kit2_pass2): each row was visited twice in its session; the first visit walked by label and found M through
lit_letter (304652 -> 304653, the second reader's kept answer "M"), and recorded the row's place; the second, the proof's,
went by that place (find_row's `at`) and asked at_label there with no frame before (304672), so the lit M got no label,
and the walk by label that followed began on M and stopped when the lap came back to it (304678) before reading it again:
"no row 'M'". PP4's Y the same (304877, and back on Y at 304884). Here the real find_row gets the recorded frames in
the order the camera showed them, one per Down, the second reader answering as its kept answers did (M on an M frame, Y
on a Y frame) or not at all, and it finds the row only where both signs agree. lit_letter says each outcome in the run's
log. Nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
from camkit import paths, screen  # noqa: E402

SHOTS = paths.a1ii_root() / "kit2_pass2" / "shots"
# the frames of each second visit, one per Down, as the camera showed them after Right into Color Depth (R lit)
PP2_M = [304668, 304669, 304670, 304671, 304672, 304673, 304674, 304675, 304676, 304677, 304678]
PP4_Y = [304872, 304873, 304874, 304875, 304876, 304877, 304878, 304879, 304880, 304881, 304882, 304884]
LIT = {304672: "M", 304678: "M", 304653: "M", 304676: "M", 304882: "M", 304877: "Y", 304884: "Y", 304673: "Y"}


def shot(n: int) -> Path:
    found = sorted(SHOTS.glob(f"{n}_*.png")) if SHOTS.exists() else []
    if not found:
        pytest.skip(f"kit2_pass2 frame {n} is not here")
    return found[0]


class Replay:
    """The camera as the prover meets it, replayed: the frame on show, read as the kit reads it, and one recorded
    frame further on each Down; any other key, or a Down past the last frame, fails the test."""

    def __init__(self, numbers):
        from camkit.frames import load
        self.frames = [load(shot(n)) for n in numbers]
        self.i, self.presses, self.events = 0, [], []
        self.run = SimpleNamespace(log=lambda kind, **f: self.events.append({"kind": kind, **f}))
        self._read = {}

    @property
    def frame(self):
        return self.frames[self.i]

    def read(self):
        if self.i not in self._read:
            self._read[self.i] = screen.read(self.frame)
        return self._read[self.i]

    def press(self, key, **kw):
        assert key == "down", f"the replay has no frame for {key!r}"
        self.presses.append(key)
        self.i += 1
        assert self.i < len(self.frames), "a Down past the last frame the camera recorded"


def place_at(n: int):
    from camkit.frames import load
    from proving import screens
    f = load(shot(n))
    return screens.place(SimpleNamespace(frame=f, read=lambda: screen.read(f)))


@pytest.fixture
def reader(monkeypatch):
    from camkit import live
    from proving import base

    def answers(mode):
        def said(path, timeout=None):
            n = int(Path(path).name[:6])
            got = LIT.get(n, "") if mode == "kept" else mode
            return (got, "" if got else "the vision reader marked 0 rows as the one with the orange bar")
        monkeypatch.setattr(live, "reader_label", said)
    monkeypatch.setattr(base, "ROW_BY", {})
    return answers


def test_the_proofs_visit_finds_m_at_its_known_place_with_the_frame_before(reader):
    from proving import base, nav
    reader("kept")
    cam = Replay(PP2_M)
    assert nav.find_row(cam, "M", at=place_at(304653))
    assert len(cam.presses) == 4 and cam.frame.path.name.startswith("304672")
    assert base.ROW_BY == {"M": "lit letter"}
    said = [e for e in cam.events if e["kind"] == "lit_letter"]
    assert said[-1]["label"] == "M" and said[-1]["frame"].startswith("304672") and said[-1]["before"].startswith("304671")


def test_y_whose_frame_before_ocr_misses_is_found_when_the_lap_comes_back_to_it(reader):
    from proving import base, nav
    reader("kept")
    cam = Replay(PP4_Y)
    assert nav.find_row(cam, "Y", at=place_at(304877))
    assert len(cam.presses) == 11 and cam.frame.path.name.startswith("304884")
    assert base.ROW_BY == {"Y": "lit letter"}
    said = [e for e in cam.events if e["kind"] == "lit_letter"]
    # at Y's place first: OCR read nothing at its place on the frame before (304876), so no label and no reader asked
    assert said[0]["frame"].startswith("304877") and "frame before" in said[0]["why"] and "reader" not in said[0]
    assert said[-1]["label"] == "Y" and said[-1]["before"].startswith("304882")


@pytest.mark.parametrize("mode", ["Y", ""])
def test_a_reader_that_disagrees_or_says_nothing_leaves_no_row(reader, mode):
    from proving import base, nav
    reader(mode)
    cam = Replay(PP2_M)
    assert not nav.find_row(cam, "M", at=place_at(304653))
    assert len(cam.presses) == 10                       # to the place, then one lap back to M: no Down past it
    assert base.ROW_BY == {}
    said = [e for e in cam.events if e["kind"] == "lit_letter"]
    assert said and all("label" not in e for e in said)
    assert any(("differ" if mode else "reader") in e["why"] for e in said)


def test_the_log_withholds_every_text_on_a_local_only_run(reader, monkeypatch):
    from camkit import vlm
    from proving import nav
    reader("kept")
    monkeypatch.setattr(vlm, "LOCAL_ONLY", True)
    cam = Replay(PP2_M)
    assert nav.find_row(cam, "M", at=place_at(304653))
    said = [e for e in cam.events if e["kind"] == "lit_letter"]
    assert said and all(e.get("label") in (None, "(withheld)") and e.get("ocr") in (None, "(withheld)")
                        and e.get("reader") in (None, "(withheld)") for e in said)
