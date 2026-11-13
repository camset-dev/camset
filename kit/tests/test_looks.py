"""Creative Look's panels (kit/proving/looks.py), off the camera: the scale's ends read as the camera draws them, and a
cell that does not read as the value chosen read by the vision reader before the row fails (the owner, 2026-11-06).
2026-11-08: OCR read Highlights' top end "+9" as "49", the scale became 9..49, the walk pressed Down twenty times from
0 and failed on "the cell shows 8, not 9" with the cell reading "-9". 2026-11-13: Apple's OCR since macOS 27.2 reads no
top end at all on that run's frames, and misses an end on about half of the look frames; an end it misses may come
from the scale's tick marks, only where their count alone leaves one scale, every end read agrees, and the run has
read both ends beside as many ticks. Fakes stand in for the camera, OCR and the reader; the a1 II's own frames of that
run are read where they are on disk."""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ocr, paths, screen  # noqa: E402
from proving import looks  # noqa: E402
from proving.base import Failed  # noqa: E402

# the cells as OCR read them on frame 00516 of the failed run: Highlights lit (cell 2), the marker at 0
CELLS = [("•‡0", 100, 363, 57, 26), ("H +0", 172, 364, 56, 26), ("S", 237, 367, 16, 19)]
NAME = ("Highlights", 240, 292, 150, 34)


def lines(*items):
    return [ocr.Line(text=t, conf=0.99, x=x, y=y, w=w, h=h) for t, x, y, w, h in items]


def panel(tmp_path, monkeypatch, read, field=2, marker=170, ticks=None):
    """A look panel whose OCR reads `read` (text, x, y, w, h each), its cell `field` lit, its marker at y=marker and
    `ticks` tick marks counted on its scale (None: not counted)."""
    path = tmp_path / "00516_right.png"
    path.write_bytes(b"a frame")
    monkeypatch.setattr(looks.ocr, "read", lambda ps, eng=None: {p: lines(*read) for p in ps})
    return SimpleNamespace(frame=SimpleNamespace(path=path),
                           read=lambda: SimpleNamespace(field=field, marker=marker, ticks=ticks),
                           refresh=lambda tag: None)


@pytest.mark.parametrize("text,end", [("+9", 9), ("49", 9), ("-9", 9), ("9", 9), ("-0", 0), ("0", 0), ("5", 5),
                                      ("1", 1), ("t9", 9), ("", None), ("+", None)])
def test_a_scale_end_is_its_last_digit(text, end):
    assert looks.scale_end(text) == end


def test_a_plus_read_as_a_four_still_makes_the_scale_symmetric(tmp_path, monkeypatch):
    """Frame 00516's readings: the top end "+9" read "49", the bottom "-9". The scale is -9..+9 and the cell 0."""
    cam = panel(tmp_path, monkeypatch, [("49", 595, 88, 38, 25), ("-9", 612, 234, 22, 20), *CELLS, NAME])
    assert looks.look_cell(cam) == (0, "Highlights", (-9, 9), 0, "ends")
    assert looks.look_value(cam) == (0, "Highlights", (-9, 9), "ends")
    # frame 00536: the walk at the bottom, the cell "-9", the marker at the bottom end
    bottom = [("+9", 596, 88, 40, 30), ("-9", 612, 234, 22, 20), ("H", 171, 367, 17, 19), ("-9", 195, 366, 25, 22), NAME]
    cam = panel(tmp_path, monkeypatch, bottom, marker=242)
    assert looks.look_value(cam, (-9, 9)) == (-9, "Highlights", (-9, 9), "ends")
    # the other scales stay as they were: 0..9 (an end read "-0" by its tick) and 1..5
    for top, bot, rng in (("9", "-0", (0, 9)), ("5", "1", (1, 5)), ("9", "9", (-9, 9))):
        cam = panel(tmp_path, monkeypatch, [(top, 600, 88, 20, 25), (bot, 612, 234, 22, 20), NAME])
        assert looks.look_cell(cam)[2] == rng, (top, bot)


TOP_9, TOP_PLUS9, TOP_5, TOP_6 = ("9", 618, 90, 14, 20), ("+9", 610, 92, 20, 16), ("5", 619, 89, 14, 20), \
    ("6", 619, 89, 14, 20)
TOP_PLUS5 = ("+5", 610, 89, 22, 20)                  # 1..5's "5" with a tick read as its plus
BOTTOM_9, BOTTOM_0, BOTTOM_1 = ("-9", 611, 233, 23, 17), ("-• 0", 590, 234, 40, 18), ("1", 620, 234, 12, 20)
HIGHLIGHTS, FADE, SHARPNESS_RANGE, CLARITY = 2, 4, 7, 8      # the a1 II's cells: -9..+9, 0..9, 1..5, 0..9
SEEN_19, SEEN_10, SEEN_5 = {(HIGHLIGHTS, 19): {(-9, 9)}}, {(FADE, 10): {(0, 9)}}, {(SHARPNESS_RANGE, 5): {(1, 5)}}


@pytest.mark.parametrize("ends,ticks,rng", [
    ([TOP_PLUS5], 5, None),                  # was -5..+5: five ticks are not eleven steps
    ([TOP_PLUS5], None, (-5, 5)),            # the ticks not counted: the ends decide, as before
    ([TOP_PLUS9, BOTTOM_9], 10, None),       # -9..+9 beside ten ticks: one of them is wrong
    ([TOP_PLUS9, BOTTOM_9], 19, (-9, 9)), ([TOP_9, BOTTOM_0], 10, (0, 9)), ([TOP_5, BOTTOM_1], 5, (1, 5)),
])
def test_ends_and_ticks_that_disagree_leave_the_scale_unread(tmp_path, monkeypatch, ends, ticks, rng):
    cam = panel(tmp_path, monkeypatch, [*ends, NAME], ticks=ticks)
    got = looks.look_cell(cam, seen={})
    assert (got[2], got[4]) == ((rng, "ends") if rng else ((None, None), None))


@pytest.mark.parametrize("ends,field,ticks,seen,rng", [
    ([BOTTOM_9], HIGHLIGHTS, 19, SEEN_19, (-9, 9)),   # frame 00516 as OCR reads it since macOS 27.2, the run's ticks seen
    ([TOP_9], FADE, 10, SEEN_10, (0, 9)), ([BOTTOM_0], FADE, 10, SEEN_10, (0, 9)),
    ([TOP_9], HIGHLIGHTS, 19, SEEN_19, (-9, 9)),      # the "+" lost as well: nineteen ticks are -9..+9
    ([], HIGHLIGHTS, 19, SEEN_19, (-9, 9)), ([], FADE, 10, SEEN_10, (0, 9)),
    ([BOTTOM_9], HIGHLIGHTS, 19, None, None),         # no run (a check off the camera): never from the ticks
    ([BOTTOM_9], HIGHLIGHTS, 19, {}, None),           # the run has not read both ends beside nineteen ticks yet
    ([BOTTOM_9], HIGHLIGHTS, 19, SEEN_10, None),      # only another parameter's, beside ten
    # another parameter with as many ticks proves nothing of this one: Fade's 0..9 for Clarity, Contrast's for Highlights
    ([TOP_9], CLARITY, 10, SEEN_10, None), ([BOTTOM_9], HIGHLIGHTS, 19, {(1, 19): {(-9, 9)}}, None),
    ([BOTTOM_9], HIGHLIGHTS, 19, {(HIGHLIGHTS, 19): {(-9, 9), (0, 9)}}, None),   # read as two scales: not trusted
    ([BOTTOM_9], HIGHLIGHTS, None, SEEN_19, None),    # the ticks not counted
    # an end read vetoes the ticks' scale, never chooses another: the top's number, and the bottom's digit
    ([TOP_5], FADE, 10, SEEN_10, None), ([BOTTOM_1], FADE, 10, SEEN_10, None), ([BOTTOM_9], FADE, 10, SEEN_10, None),
    # five ticks fit seven scales (0..4, 1..5 ... 5..9, -2..+2): an end would choose, so they never answer
    ([TOP_5], SHARPNESS_RANGE, 5, SEEN_5, None), ([BOTTOM_1], SHARPNESS_RANGE, 5, SEEN_5, None),
    ([], SHARPNESS_RANGE, 5, SEEN_5, None),
    ([TOP_6], SHARPNESS_RANGE, 5, SEEN_5, None),      # 1..5's "5" read "6": was 2..6
])
def test_an_end_ocr_misses_comes_from_the_ticks_only_where_they_alone_tell_the_scale(tmp_path, monkeypatch, ends,
                                                                                    field, ticks, seen, rng):
    cam = panel(tmp_path, monkeypatch, [*ends, NAME], field=field, ticks=ticks)
    got = looks.look_cell(cam, seen=seen)
    if rng:
        assert (got[2], got[4]) == (rng, "ticks")
    else:
        assert None in got[2] and got[4] is None


def test_the_run_keeps_both_ends_read_beside_their_ticks(tmp_path, monkeypatch):
    seen = {}
    # one end read is no evidence (its other end only inferred by the sign), nor ends without ticks
    for ends, field, ticks in (([TOP_PLUS9], HIGHLIGHTS, 19), ([TOP_PLUS5], SHARPNESS_RANGE, 5),
                               ([TOP_9, BOTTOM_0], FADE, None)):
        looks.look_cell(panel(tmp_path, monkeypatch, [*ends, NAME], field=field, ticks=ticks), seen=seen)
    assert seen == {}
    # both ends read are kept by cell and count, and so are ends that disagree with their ticks, so that cell and count
    # are never trusted
    for ends, field, ticks in (([TOP_PLUS9, BOTTOM_9], HIGHLIGHTS, 19), ([TOP_PLUS5, BOTTOM_1], SHARPNESS_RANGE, 5)):
        looks.look_cell(panel(tmp_path, monkeypatch, [*ends, NAME], field=field, ticks=ticks), seen=seen)
    assert seen == {(HIGHLIGHTS, 19): {(-9, 9)}, (SHARPNESS_RANGE, 5): {(-5, 5)}}
    monkeypatch.setattr(looks, "_SEEN", {})
    run = SimpleNamespace(dir=tmp_path / "kit2_pass2")
    looks.scales_seen(run)[(HIGHLIGHTS, 19)] = {(-9, 9)}
    assert looks.scales_seen(SimpleNamespace(dir=tmp_path / "kit2_pass2")) == SEEN_19        # the run's, kept
    assert looks.scales_seen(SimpleNamespace(dir=tmp_path / "another")) == {}
    assert looks.scales_seen(None) is None                                  # no run: nothing gathered, nothing trusted


def test_a_frame_with_no_cell_lit_keeps_nothing_and_takes_no_scale_from_the_ticks(tmp_path, monkeypatch):
    """No cell lit names no parameter: frames of any parameter would share its evidence."""
    seen = {}
    got = looks.look_cell(panel(tmp_path, monkeypatch, [TOP_9, BOTTOM_0, NAME], field=None, ticks=10), seen=seen)
    assert (got[2], got[4]) == ((0, 9), "ends") and seen == {}               # its ends still read; nothing kept
    got = looks.look_cell(panel(tmp_path, monkeypatch, [TOP_9, NAME], field=None, ticks=10), seen=seen)
    assert None in got[2] and got[4] is None                                  # one end beside ten ticks: unread
    got = looks.look_cell(panel(tmp_path, monkeypatch, [TOP_9, NAME], field=None, ticks=10), seen={(None, 10): {(0, 9)}})
    assert None in got[2] and got[4] is None                                  # nor from evidence kept under no cell
    got = looks.look_cell(panel(tmp_path, monkeypatch, [TOP_PLUS9, BOTTOM_9, NAME], field=None, ticks=10), seen={})
    assert (got[2], got[4]) == ((None, None), None)                          # ends still held to the ticks beside them


class Panel:
    """A look panel the camera holds at `value` on `scale`, Up and Down moving it within; OCR reads the cell's number,
    the name and the ends given (None: missed), the screen the marker's place and `ticks` ticks."""
    def __init__(self, tmp_path, monkeypatch, field, scale, value, top, bottom, ticks):
        (self.lo, self.hi), self.v, self.field, self.ticks = scale, value, field, ticks
        self.presses, self.held = [], []
        self.frame = SimpleNamespace(path=tmp_path / "01803_down.png")
        self.frame.path.write_bytes(b"a frame")
        ends = [e for e in ((top, 619, 89, 14, 20), (bottom, 611, 233, 23, 17)) if e[0] is not None]
        x = screen.LOOK_CELLS[field] + 20
        monkeypatch.setattr(looks.ocr, "read", lambda ps, eng=None: {p: lines(*ends, (self.cell(), x, 365, 24, 20), NAME)
                                                                     for p in ps})

    def cell(self):
        return str(self.v) if self.lo >= 0 else f"{self.v:+d}" if self.v else "±0"

    def read(self):
        marker = round(240 - (self.v - self.lo) / (self.hi - self.lo) * 140)
        return SimpleNamespace(kind="look", glyphs={"up": True, "down": True}, field=self.field, marker=marker,
                               ticks=self.ticks)

    def press(self, key):
        self.presses.append(key)
        self.v = min(self.hi, self.v + 1) if key == "up" else max(self.lo, self.v - 1) if key == "down" else self.v
        if key == "enter":
            self.held.append(self.v)

    def refresh(self, tag):
        return self.read()


def walk(tmp_path, monkeypatch, cam, seen):
    """prove_look_row on the panel's one parameter with every other camera step faked, in a run whose scales_seen
    holds `seen`: (the proof lines written, or the failure's words)."""
    for name in ("open_look_panel", "look_to_cell", "after_download", "to_row"):
        monkeypatch.setattr(looks, name, lambda *a, **k: None)
    monkeypatch.setattr(looks, "place", lambda cam: "the row")
    monkeypatch.setattr(looks, "same_place", lambda a, b: True)
    monkeypatch.setattr(looks, "vlm_option", lambda cam: "")
    monkeypatch.setattr(looks, "camset", SimpleNamespace(read=lambda p: p, diff=lambda a, b: []))
    monkeypatch.setattr(looks, "LOOK_PARAMS", [cam.field])
    monkeypatch.setattr(looks, "ask_second", Reader(OSError("the reader is off")))
    monkeypatch.setattr(looks, "_SEEN", {})
    run = SimpleNamespace(dir=tmp_path / "kit2_pass2")
    looks.scales_seen(run).update(seen)
    out = io.StringIO()
    job = {"path": ["Creative Look"], "look": 0, "labels": ["ST(Standard)"], "option": "panel 0", "kind": "look"}
    try:
        looks.prove_look_row(cam, SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT")), run, job, Path("b.DAT"), out)
    except Failed as e:
        return str(e)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_a_misread_end_on_five_ticks_stops_the_row_and_proves_nothing(tmp_path, monkeypatch):
    """Sharpness Range held at 3 on 1..5, OCR reading its top end "5" as "6" and missing the bottom: the walk stops
    before a press, where reading the scale as 2..6 would have written 2, 6 and 4 while the camera held 1, 5 and 3."""
    cam = Panel(tmp_path, monkeypatch, 7, (1, 5), 3, "6", None, 5)
    assert walk(tmp_path, monkeypatch, cam, SEEN_5) == "Creative Look 'ST(Standard)' cell 7: value 3, range None..6 not readable"
    assert cam.presses == [] and cam.held == []


def test_a_proof_says_how_its_scale_was_read(tmp_path, monkeypatch):
    """Highlights held at 0, OCR missing the top end as it does since macOS 27.2: read by its ticks where the run has
    read both ends beside nineteen, the walk proves -9, +9 and 0 as the camera holds them; by its ends where it reads
    them; and stops, as before, where neither tells the scale."""
    cam = Panel(tmp_path, monkeypatch, 2, (-9, 9), 0, None, "-9", 19)
    got = walk(tmp_path, monkeypatch, cam, SEEN_19)
    assert [(p["value"], p["range"], p["range_from"]) for p in got] == [(-9, [-9, 9], "ticks"), (9, [-9, 9], "ticks"),
                                                                       (0, [-9, 9], "ticks")]
    assert cam.held == [-9, 9, 0]
    cam = Panel(tmp_path, monkeypatch, 2, (-9, 9), 0, "+9", "-9", 19)
    assert {p["range_from"] for p in walk(tmp_path, monkeypatch, cam, {})} == {"ends"}
    cam = Panel(tmp_path, monkeypatch, 2, (-9, 9), 0, None, "-9", 19)
    assert "not readable" in walk(tmp_path, monkeypatch, cam, {}) and cam.presses == []


def ticked(n, top=99, bottom=243, missing=(), thick=2):
    """A grey frame with the look scale's n tick marks, `thick` px each, drawn evenly from y=top to y=bottom, but those
    in `missing`."""
    g = np.zeros((480, 640), np.uint8)
    for i, y in enumerate(np.linspace(top, bottom, n).round().astype(int)):
        if i not in missing:
            g[y:y + thick, 587:596] = 240
    return g


def test_the_tick_marks_counted_on_a_drawn_scale():
    assert [screen._look_ticks(ticked(n)) for n in (19, 10, 5)] == [19, 10, 5]
    assert screen._look_ticks(ticked(10, thick=4)) == 10
    assert screen._look_ticks(np.zeros((480, 640), np.uint8)) is None            # no scale
    bright = ticked(10)
    bright[85:255, 586:600] = 200                                                 # something bright behind the panel
    assert screen._look_ticks(bright) is None
    assert screen._look_ticks(ticked(10, thick=6)) is None                        # bars, not ticks
    assert screen._look_ticks(ticked(10, missing=(4,))) is None                   # unevenly spaced
    assert screen._look_ticks(ticked(10, bottom=200)) is None                     # short of the bottom end
    assert screen._look_ticks(ticked(8, top=131)) is None                         # short of the top end


@pytest.mark.parametrize("name,ticks", [("00516_right.png", 19), ("01566_up.png", 10), ("01830_up.png", 5)])
def test_the_tick_marks_on_the_cameras_own_frames(name, ticks):
    """Opt-in: Highlights (-9..+9), Fade (0..9) and Sharpness Range (1..5) on the a1 II's frames (skipped without them)."""
    from camkit.frames import load
    p = paths.a1ii_root() / "kit2_review_list" / "shots" / name
    if not p.exists():
        pytest.skip("the a1 II's kit2_review_list frames are not in this clone")
    s = screen.read(load(p))
    assert (s.kind, s.ticks) == ("look", ticks)


def test_the_failed_runs_own_frames_read_as_the_camera_shows_them():
    """Opt-in: the a1 II's frames of the failed run, read by this computer's OCR (skipped without them, as in CI).
    Since macOS 27.2 Apple's OCR reads no top end on the failed frames. Contrast's frame before them, both ends read
    beside nineteen ticks, proves nothing of Highlights: the first failed frame is read by its ends or stays unread.
    A frame of Highlights itself with both ends read (one of the walk's, 00523) lets the ticks tell the failed frames'
    scale; an OCR that leaves the run without that evidence leaves a scale whose ends it misses unread, never
    another."""
    from camkit.frames import load
    shots = paths.a1ii_root() / "kit2_review_list" / "shots"
    names = ("00498_down.png", "00523_down.png", "00516_right.png", "00536_down.png")
    contrast, highlights, first, bottom = (shots / n for n in names)
    if not all((shots / n).exists() for n in names):
        pytest.skip("the a1 II's kit2_review_list frames are not in this clone")
    seen = {}

    def read(p, known=None):
        f = load(p)
        return looks.look_value(SimpleNamespace(frame=f, read=lambda: screen.read(f), refresh=lambda tag: None), known,
                                seen)

    read(contrast)
    got = read(first)
    assert (got[3] == "ends" and got[:3] == (0, "Highlights", (-9, 9))) or None in got[2]
    read(highlights)
    trusted = seen.get((HIGHLIGHTS, 19)) == {(-9, 9)}
    for p, known, want in ((first, None, 0), (bottom, (-9, 9), -9), (bottom, None, -9)):
        got = read(p, known)
        if known or trusted or got[3] == "ends":
            assert got[:3] == (want, "Highlights", (-9, 9)), p.name
        else:
            assert None in got[2], p.name


class Reader:
    """The vision reader as screens.ask_second asks it: answers `answer` (or raises it), counting the questions."""
    def __init__(self, answer):
        self.answer, self.asked = answer, []

    def __call__(self, image, prompt, timeout):
        self.asked.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def fields(active, value):
    row = ["±0", "±0", "±0", "0", "±0", "4", "3", "1"]
    row[active] = value
    return {"title": "Creative Look", "fields": row, "active": active}


@pytest.mark.parametrize("answer,want", [(fields(1, "-9"), -9), (fields(1, "−9"), -9), (fields(1, "±0"), 0),
                                         (fields(0, "+3"), 3), (fields(2, "Highlights"), None),
                                         ({"fields": ["-9"], "active": True}, None), ({"fields": ["-9"], "active": 1}, None),
                                         ({"fields": "-9", "active": 0}, None), ({"_unparsed": "no"}, None),
                                         (OSError("the reader is off"), None)])
def test_the_reader_reads_the_orange_cell(tmp_path, monkeypatch, answer, want):
    reader = Reader(answer)
    monkeypatch.setattr(looks, "ask_second", reader)
    cam = panel(tmp_path, monkeypatch, [])
    assert looks.reader_cell(cam) == want
    assert reader.asked == [looks.PROMPTS["fields"]]                 # the number-box question, asked once


def test_the_reader_decides_before_a_cell_fails(tmp_path, monkeypatch, capsys):
    cam = panel(tmp_path, monkeypatch, [])
    reader = Reader(fields(1, "-9"))
    monkeypatch.setattr(looks, "ask_second", reader)
    assert looks.look_checked(cam, -9, -9, "Highlights", (-9, 9)) == (-9, "") and reader.asked == []  # agreed: not asked
    got, said = looks.look_checked(cam, 8, -9, "Highlights", (-9, 9))
    assert got == -9 and said == "OCR and the marker read 8, the vision reader -9" and len(reader.asked) == 1
    assert "Highlights: OCR and the marker read 8, the vision reader -9 (wanted -9, 00516_right.png)" in capsys.readouterr().out
    monkeypatch.setattr(looks, "ask_second", Reader(OSError("the reader is off")))
    assert looks.look_checked(cam, 8, -9, "Highlights", (-9, 9)) == (8, "OCR and the marker read 8, the vision reader nothing")
    # a reading no cell of this scale can show never stands for the cell
    monkeypatch.setattr(looks, "ask_second", Reader(fields(1, "12")))
    assert looks.look_checked(cam, 8, -9, "Highlights", (-9, 9)) == (
        8, "OCR and the marker read 8, the vision reader 12, off the scale -9..9")
    assert looks.reader_on_scale(cam, (0, 9)) == (None, "12, off the scale 0..9")
    monkeypatch.setattr(looks, "ask_second", Reader(fields(1, "5")))
    assert looks.reader_on_scale(cam, (1, 5)) == (5, "5")


# ---------------------------------------------------------------- the prover, with every camera step faked

class Cam:
    def __init__(self, tmp_path):
        self.presses = []
        self.frame = SimpleNamespace(path=tmp_path / "00530_down.png")
        self.frame.path.write_bytes(b"a frame")

    def press(self, key):
        self.presses.append(key)

    def read(self):
        return SimpleNamespace(kind="look", glyphs={"up": True, "down": True})


def prover(tmp_path, monkeypatch, readings, reader):
    """prove_look_row on one parameter (Highlights, cell 2), OCR and the marker giving `readings` in turn."""
    for name in ("open_look_panel", "look_to_cell", "after_download", "to_row"):
        monkeypatch.setattr(looks, name, lambda *a, **k: None)
    monkeypatch.setattr(looks, "place", lambda cam: "the row")
    monkeypatch.setattr(looks, "same_place", lambda a, b: True)
    monkeypatch.setattr(looks, "vlm_option", lambda cam: "")
    monkeypatch.setattr(looks, "camset", SimpleNamespace(read=lambda p: p, diff=lambda a, b: []))
    monkeypatch.setattr(looks, "LOOK_PARAMS", [2])
    monkeypatch.setattr(looks, "ask_second", reader)
    left = list(readings)
    monkeypatch.setattr(looks, "look_value", lambda cam, known=None, seen=None: (left.pop(0), "Highlights", (-9, 9),
                                                                               "ends"))
    link = SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT"))
    job = {"path": ["Creative Look"], "look": 0, "labels": ["ST(Standard)"], "option": "panel 0", "kind": "look"}
    out, cam = io.StringIO(), Cam(tmp_path)
    return cam, out, lambda: looks.prove_look_row(cam, link, None, job, Path("base.DAT"), out)


def test_a_short_digit_ocr_drops_is_read_by_the_reader_and_the_row_goes_on(tmp_path, monkeypatch, capsys):
    """The walk to -9 reads 8 (a short digit OCR lost); the reader reads -9 and the row goes on to +9 and back to 0."""
    reader = Reader(fields(1, "-9"))
    cam, out, run = prover(tmp_path, monkeypatch, [0, 8, -9, 9, 9, 0], reader)
    run()
    proofs = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [p["value"] for p in proofs] == [-9, 9, 0] and [p["range"] for p in proofs] == [[-9, 9]] * 3
    assert {p["range_from"] for p in proofs} == {"ends"}
    assert cam.presses == ["down"] * 9 + ["enter"] + ["up"] * 18 + ["enter"] + ["down"] * 9 + ["enter"]
    assert len(reader.asked) == 1
    assert "OCR and the marker read 8, the vision reader -9" in capsys.readouterr().out


def test_a_cell_the_reader_reads_otherwise_fails_naming_both(tmp_path, monkeypatch):
    cam, out, run = prover(tmp_path, monkeypatch, [0, 8], Reader(fields(1, "-8")))
    with pytest.raises(Failed, match=r"the cell shows -8, not -9 \(OCR and the marker read 8, the vision reader -8\)"):
        run()
    assert out.getvalue() == "" and "enter" not in cam.presses               # nothing chosen on a wrong reading


def test_a_start_ocr_could_not_read_is_asked_of_the_reader(tmp_path, monkeypatch):
    reader = Reader(fields(1, "±0"))
    cam, out, run = prover(tmp_path, monkeypatch, [None, -9, -9, 9, 9, 0], reader)
    run()
    assert [json.loads(line)["value"] for line in out.getvalue().splitlines()] == [-9, 9, 0] and len(reader.asked) == 1


def test_an_off_scale_reading_sets_no_press_count(tmp_path, monkeypatch):
    """OCR read no start and the reader answers 12 on -9..+9: the walk would have pressed Down 21 times. No press goes
    out, and the failure names the reading."""
    cam, out, run = prover(tmp_path, monkeypatch, [None], Reader(fields(1, "12")))
    with pytest.raises(Failed, match=r"value None, range -9\.\.9 not readable \(the vision reader: 12, off the scale "
                                     r"-9\.\.9\)"):
        run()
    assert cam.presses == [] and out.getvalue() == ""
    cam, out, run = prover(tmp_path, monkeypatch, [0, 8], Reader(fields(1, "12")))
    with pytest.raises(Failed, match=r"the cell shows 8, not -9 \(OCR and the marker read 8, the vision reader 12, off "
                                     r"the scale -9\.\.9\)"):
        run()
    assert "enter" not in cam.presses and out.getvalue() == ""
