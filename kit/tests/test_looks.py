"""Creative Look's panels (kit/proving/looks.py), off the camera: the scale's ends read as the camera draws them, and a
cell that does not read as the value chosen read by the vision reader before the row fails (the owner, 2026-11-06).
2026-11-08: OCR read Highlights' top end "+9" as "49", the scale became 9..49, the walk pressed Down twenty times from
0 and failed on "the cell shows 8, not 9" with the cell reading "-9". Fakes stand in for the camera, OCR and the
reader; the a1 II's own frames of that run are read where they are on disk."""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ocr, paths  # noqa: E402
from proving import looks  # noqa: E402
from proving.base import Failed  # noqa: E402

# the cells as OCR read them on frame 00516 of the failed run: Highlights lit (cell 2), the marker at 0
CELLS = [("•‡0", 100, 363, 57, 26), ("H +0", 172, 364, 56, 26), ("S", 237, 367, 16, 19)]
NAME = ("Highlights", 240, 292, 150, 34)


def lines(*items):
    return [ocr.Line(text=t, conf=0.99, x=x, y=y, w=w, h=h) for t, x, y, w, h in items]


def panel(tmp_path, monkeypatch, read, field=2, marker=170):
    """A look panel whose OCR reads `read` (text, x, y, w, h each), its cell `field` lit and its marker at y=marker."""
    path = tmp_path / "00516_right.png"
    path.write_bytes(b"a frame")
    monkeypatch.setattr(looks.ocr, "read", lambda ps, eng=None: {p: lines(*read) for p in ps})
    return SimpleNamespace(frame=SimpleNamespace(path=path), read=lambda: SimpleNamespace(field=field, marker=marker),
                           refresh=lambda tag: None)


@pytest.mark.parametrize("text,end", [("+9", 9), ("49", 9), ("-9", 9), ("9", 9), ("-0", 0), ("0", 0), ("5", 5),
                                      ("1", 1), ("t9", 9), ("", None), ("+", None)])
def test_a_scale_end_is_its_last_digit(text, end):
    assert looks.scale_end(text) == end


def test_a_plus_read_as_a_four_still_makes_the_scale_symmetric(tmp_path, monkeypatch):
    """Frame 00516's readings: the top end "+9" read "49", the bottom "-9". The scale is -9..+9 and the cell 0."""
    cam = panel(tmp_path, monkeypatch, [("49", 595, 88, 38, 25), ("-9", 612, 234, 22, 20), *CELLS, NAME])
    assert looks.look_cell(cam) == (0, "Highlights", (-9, 9), 0)
    assert looks.look_value(cam) == (0, "Highlights", (-9, 9))
    # frame 00536: the walk at the bottom, the cell "-9", the marker at the bottom end
    bottom = [("+9", 596, 88, 40, 30), ("-9", 612, 234, 22, 20), ("H", 171, 367, 17, 19), ("-9", 195, 366, 25, 22), NAME]
    cam = panel(tmp_path, monkeypatch, bottom, marker=242)
    assert looks.look_value(cam, (-9, 9)) == (-9, "Highlights", (-9, 9))
    # the other scales stay as they were: 0..9 (an end read "-0" by its tick) and 1..5
    for top, bot, rng in (("9", "-0", (0, 9)), ("5", "1", (1, 5)), ("9", "9", (-9, 9))):
        cam = panel(tmp_path, monkeypatch, [(top, 600, 88, 20, 25), (bot, 612, 234, 22, 20), NAME])
        assert looks.look_cell(cam)[2] == rng, (top, bot)


def test_the_failed_runs_own_frames_read_as_the_camera_shows_them():
    """Opt-in: the a1 II's frames of the failed run, read by this computer's OCR (skipped without them, as in CI)."""
    from camkit import screen
    from camkit.frames import load
    shots = paths.a1ii_root() / "kit2_review_list" / "shots"
    first, bottom = shots / "00516_right.png", shots / "00536_down.png"
    if not (first.exists() and bottom.exists()):
        pytest.skip("the a1 II's kit2_review_list frames are not in this clone")
    for p, known, want in ((first, None, 0), (bottom, (-9, 9), -9), (bottom, None, -9)):
        f = load(p)
        cam = SimpleNamespace(frame=f, read=lambda f=f: screen.read(f), refresh=lambda tag: None)
        assert looks.look_value(cam, known) == (want, "Highlights", (-9, 9)), p.name


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
    monkeypatch.setattr(looks, "look_value", lambda cam, known=None: (left.pop(0), "Highlights", (-9, 9)))
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
