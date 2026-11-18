"""optboxes_run: an option of a list row that draws a row of boxes of its own (the a1 II's Zebra Level > Custom 1 and
Custom 2, 2026-11-18): reading the screen, walking a box to its ends, the read-only probe, the proof run with its base,
the OK judged on the screen's own shape (camkit.live.OptionBoxes), the Standard 30 / Range ±5 rule on OSD eyes, and
the exit statuses. Stored frames where runs/ holds them (skipped otherwise); made-up cameras and sessions otherwise.
"""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import optboxes_run as O  # noqa: E402
from camkit import live, ocr, paths, safety  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED  # noqa: E402

RUNS = paths.a1ii_root()
# Custom 1 with its Standard box lit at 70 as OCR read it (kit2_look_zebra_a 00014_right.png, OSD eyes)
STD70 = [("& Zebra Level", 129, 10, 206, 38), ("Custom 1", 128, 67, 135, 34), ("100", 37, 85, 34, 22),
         ("100+", 33, 153, 44, 20), ("C1", 41, 217, 25, 21), ("C2", 41, 281, 28, 24), ("Standard", 313, 291, 134, 35),
         ("Std+Range", 173, 357, 169, 40), ("70", 419, 355, 42, 38), ("‡5", 537, 359, 50, 33), ("?", 319, 441, 13, 26),
         ("MENU Cancel", 387, 437, 126, 31), ("• OK", 561, 437, 64, 28)]


def stored(rel):
    p = RUNS / rel
    if not p.exists():
        pytest.skip(f"{p} not present")
    from camkit.frames import load
    return load(p)


def ocr_lines(rows):
    return [ocr.Line(t, 1.0, x, y, w, h) for t, x, y, w, h in rows]


# ---------------------------------------------------------------- reading the screen (stored frames)


@pytest.mark.parametrize("rel,word,lit,values", [
    ("kit2_look_zebra_a/shots/00012_down.png", "", None, ["Std+Range", "70", "±5"]),
    ("kit2_look_zebra_a/shots/00013_right.png", "Type", 0, ["Std+Range", "70", "±5"]),
    ("kit2_look_zebra_a/shots/00014_right.png", "Standard", 1, ["Std+Range", "70", "±5"]),
    ("kit2_zebra_split/shots/range6.png", "Range", 2, ["Std+Range", "29", "±6"]),
    ("kit2_zebra_split/shots/std29.png", "Standard", 1, ["Std+Range", "29", "±5"])])
def test_the_stored_frames_read_as_the_option_its_lit_box_and_values(rel, word, lit, values):
    """On the camera's own frames (OSD eyes): the title reads Custom 1, the word above the lit box names it, the lit
    box is found by its orange, each box's value reads with OCR's "‡" taken for "±" and its spaces out."""
    f = stored(rel)
    cam = SimpleNamespace(frame=f)
    assert O.title(cam) == "Custom 1" and O.word(cam) == word and O.lit_place(cam) == lit
    assert [O.read_at(cam, b) for b in range(3)] == values and O.drawn(cam) == 3


@pytest.mark.parametrize("name,option,word,b,why", [
    ("241720_right.png", "Custom 1", "Lower Limit", 1, ""),                        # in Custom 1's Lower Limit box
    ("241721_right.png", "Custom 1", "Lower Limit", 1, "no box of the row is lit"),   # one Right more: out, on the list
    ("241724_down.png", "Custom 1", "Lower Limit", 1, "not Custom 1"),            # the list's cursor on Custom 2
    ("241752_right.png", "Custom 2", "Lower Limit", 1, "no box of the row is lit"),
    ("241753_down.png", "Custom 2", "Lower Limit", 1, "not Custom 2"),            # the list's cursor on 70
    ("241754_down.png", "Custom 2", "Lower Limit", 1, "not Custom 2"),            # and on 75
    ("241491_down.png", "Custom 1", "Standard", 1, ""),
    ("241429_down.png", "Custom 1", "Range", 2, ""),
    ("241426_down.png", "Custom 1", "Range", 2, ""),
    ("241491_down.png", "Custom 1", "Range", 2, "box 2 of the row is lit, not box 3")])
def test_check_1_tells_a_box_with_the_cursor_in_it_from_the_list(name, option, word, b, why):
    """The check after every press inside the boxes (camkit.live.in_box_refused, by pixels for the lit box): the probe's
    frames where it walked off the boxes (241721 one Right past the last box, 241724 the list's cursor on Custom 2,
    241752-241754 on C2, 70 and 75) each fail it with words that say so; the frames in a box pass it."""
    from camkit import ocr as camkit_ocr
    f = stored(f"kit2_pass2/shots/{name}")
    lines = camkit_ocr.read([f.path])[f.path]
    got = live.in_box_refused(option, word, b, O.PLACES, lines, f.image)
    assert (got == "") if not why else (why in got), got


def test_a_box_value_keeps_its_words_and_closes_the_spaces_ocr_puts_by_a_sign(monkeypatch):
    """read_at: "Lower Limit" stays two words (a proof's label), while "Std +Range", "‡ 5" and "100 +" close up."""
    def reads(rows):
        return lambda cam, box, expect="text": ocr.text_in(ocr_lines(rows), box)
    monkeypatch.setattr(O, "_read", reads([("Lower Limit", 173, 357, 169, 40), ("100 +", 419, 359, 40, 33),
                                           ("‡ 5", 537, 359, 50, 33)]))
    assert [O.read_at(None, b) for b in range(3)] == ["Lower Limit", "100+", "±5"]
    monkeypatch.setattr(O, "_read", reads([("Std +Range", 173, 357, 169, 40)]))
    assert O.read_at(None, 0) == "Std+Range"


# OCR's readings of the Range box during the probe's walk (kit2_pass2 241424-241440, HDMI eyes, 2026-11-18): from ±5,
# Down five times (±1 stayed), then Up eleven times (±10 stayed); the ± read as "+", "÷", "¢", "‡", a 3 as Cyrillic З
RANGE_WALK = ["‡5", "÷4", "‡З", "+2", "‡1", "‡1", "+2", "‡З", "÷4", "¢5", "‡6", "‡7", "‡8", "‡9", "+10", "÷10", "÷10"]


def test_the_normaliser_alone_puts_the_runs_readings_in_the_boxs_shape():
    """camkit.live.box_value: in a box whose held value is a sign and digits, the sign is the box's (±, whatever glyph
    OCR read for it: +, ÷, ¢, ‡) and the digits are mapped from their look-alikes (Cyrillic З, О and O, l and I); a plain
    number box gets the digits mapped, its trailing "+" kept; a box of words (Type) is left as read."""
    shaped = [live.box_value(t, "±5") for t in RANGE_WALK]
    assert shaped == ["±5", "±4", "±3", "±2", "±1", "±1", "±2", "±3", "±4", "±5", "±6", "±7", "±8", "±9", "±10", "±10",
                      "±10"]
    assert live.box_value("¢5", "¢5") == "±5" and live.box_value("З0", "70") == "30" and live.box_value("7O", "70") == "70"
    assert live.box_value("1OO +", "100+") == "100+" and live.box_value("Lower Limit", "Std+Range") == "LowerLimit"
    assert live.box_number("÷10", "±5") == 10 and live.box_number("±?", "±5") is None
    assert live.box_value("±?", "±5") == "±?", "no clean digits: left as read, for the walk to judge"


def frames_cam(frames):
    """A camera replaying stored frames: each press shows the next one."""
    from camkit.frames import load
    cam = SimpleNamespace(frames=list(frames), i=0, hdmi=SimpleNamespace(name="hdmi"), presses=[])
    cam.frame = load(cam.frames[0])

    def press(key, **k):
        cam.presses.append(key)
        cam.i += 1
        cam.frame = load(cam.frames[cam.i])
    cam.press = press
    return cam


def test_the_range_walk_on_the_stored_frames_gives_1_to_10_with_5_held(monkeypatch):
    """The probe's Range walk replayed on its own frames (241424 lit on ±5, then 241425-241440): ±1 to ±10 with ±5 held,
    five Downs and ten Ups (the camera's run pressed eleven, taking "+10" and "÷10" for two values: read in the box's
    shape they are one, the end that stayed). OCR's readings alone make the walk; the second reader is asked about the
    held value and each end alone (always asked there: they decide what is written down), its answers stubbed."""
    shots = RUNS / "kit2_pass2" / "shots"
    names = ["241424_right.png"] + [f"{n}_down.png" for n in range(241425, 241430)] + \
            [f"{n}_up.png" for n in range(241430, 241441)]
    frames = [shots / n for n in names]
    if not all(f.exists() for f in frames):
        pytest.skip(f"{shots} does not hold the probe's frames")
    said = {"241424_right.png": "±5", "241429_down.png": "±1", "241439_up.png": "±10"}
    asked = []
    monkeypatch.setattr(O, "box_answer", lambda cam: asked.append(cam.frame.path.name) or
                        (said.get(cam.frame.path.name), "vllm", False))
    cam = frames_cam(frames)
    w = O.walk(cam, 2, ["Type", "Standard", "Range"], "Custom 1")
    assert (w.values, w.held, w.wraps) == ([f"±{v}" for v in range(1, 11)], "±5", False)
    assert cam.presses == ["down"] * 5 + ["up"] * 10 and asked == list(said)


# the second reader's answers to the box question (PROMPTS["box"]) on four frames of the probe, measured with the b70
# reader on 2026-11-18: 241491 is the frame OCR read nothing in (Standard lit at 64, Range left on ±10)
BOX_SAID = {"241491_down.png": "64", "241490_down.png": "65", "241440_up.png": "±10", "241426_down.png": "±3"}


def test_the_box_question_is_asked_of_the_lit_box_on_the_stored_frames(monkeypatch):
    """proving.screens.box_answer asks the second reader about the lit box itself (PROMPTS["box"], not the option
    question, whose "item under the cursor" is the list's Custom 1 on this screen) and takes its one "value"; on
    241491, where OCR read the Standard box as nothing, the reader's 64 is taken and logged with OCR's reading."""
    import proving.screens as screens
    from camkit import vlm
    shots = RUNS / "kit2_pass2" / "shots"
    frames = {n: shots / n for n in BOX_SAID}
    if not all(f.exists() for f in frames.values()):
        pytest.skip(f"{shots} does not hold the probe's frames")
    by_bytes = {f.read_bytes(): BOX_SAID[n] for n, f in frames.items()}
    prompts = []
    monkeypatch.setattr(screens, "ask_second", lambda image, prompt, timeout: prompts.append(prompt) or
                        {"value": by_bytes[image]})
    monkeypatch.setattr(vlm, "playing", lambda role: {"name": "vllm"})
    from camkit.frames import load
    for n, f in frames.items():
        assert screens.box_answer(SimpleNamespace(frame=load(f))) == (BOX_SAID[n], "vllm", False)
    assert set(prompts) == {vlm.PROMPTS["box"]} and '{"value": null}' in vlm.PROMPTS["box"]
    logged = []
    cam = SimpleNamespace(frame=load(frames["241491_down.png"]), hdmi=SimpleNamespace(name="hdmi"),
                          run=SimpleNamespace(log=lambda kind, **f: logged.append((kind, f))))
    O.in_box(cam, "Custom 1", "Standard", 1)
    got = O.value_read(cam, 1, "65", O._stepped("65", "65", "down", 1))
    assert (got.value, got.ocr, got.vlm, got.reader, got.by) == ("64", "", "64", "vllm", "vlm")
    assert [f for k, f in logged if k == "box_reading"] == [{"box": 1, "frame": "241491_down.png", "ocr": "",
                                                              "vlm": "64", "taken": "64", "reader": "vllm"}]
    monkeypatch.setattr(screens, "ask_second", lambda image, prompt, timeout: {"value": None})
    assert screens.box_answer(cam)[0] is None, "a reader that says no box is orange gives no answer"


class Reads:
    """A made-up box whose OCR reads `ocr` in turn (one per frame) and whose second reader reads `vlm` in turn (None:
    no answer); check 1 fails on the frames `out` names (the cursor gone from the box)."""
    def __init__(self, ocr, vlm=None, out=()):
        self.ocr, self.vlm, self.i, self.presses, self.asked = list(ocr), list(vlm or []), 0, [], []
        self.out = set(out)
        self.hdmi = SimpleNamespace(name="hdmi")
        self.frame = SimpleNamespace(path=Path("00100_x.png"), image=None)
        self.logged = []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    def press(self, key, **k):
        self.presses.append(key)
        self.i += 1
        self.frame = SimpleNamespace(path=Path(f"{100 + self.i:05d}_{key}.png"), image=None)


@pytest.fixture
def reads(monkeypatch):
    monkeypatch.setattr(O, "read_at", lambda cam, b: cam.ocr[min(cam.i, len(cam.ocr) - 1)])
    monkeypatch.setattr(O, "box_answer", lambda cam: cam.asked.append(cam.i) or
                        (cam.vlm[cam.i] if cam.i < len(cam.vlm) else None, "vllm", False))
    monkeypatch.setattr(O.time, "sleep", lambda s: None)

    monkeypatch.setattr(O, "cursor_refused", lambda cam, option, name, b: "no box of the row is lit" if cam.i in cam.out
                        else "")
    return Reads


ROW = ["Type", "Standard", "Range"]


def test_a_reading_no_stepped_box_gives_goes_to_the_second_reader(reads):
    """A reading that breaks the walk (no clean value, or not one step from the last): the second reader is asked on
    that frame and its value taken where it fits; it is asked too about the held value and each end. Every asked frame
    is logged with both readings and the one taken; OCR's other readings never ask it."""
    cam = reads(["±3", "±2", "±?", "±1", "±2", "±3", "±3"], vlm=["±3", None, "±1", "±1", None, None, "±3"])
    w = O.walk(cam, 2, ROW, "Custom 1")
    assert (w.values, w.held, w.wraps) == (["±1", "±2", "±3"], "±3", False)
    assert cam.asked == [0, 2, 3, 6]
    logged = [f for k, f in cam.logged if k == "box_reading"]
    assert [(f["ocr"], f["vlm"], f["taken"]) for f in logged] == [("±3", "±3", "±3"), ("±?", "±1", "±1"),
                                                                 ("±1", "±1", "±1"), ("±3", "±3", "±3")]


def test_a_reading_that_fits_no_walk_stops_naming_its_frame(reads):
    """±3, ±2, then ±7 by OCR and by the second reader alike: no stepped box gives it, and the walk stops naming the
    frame, as before."""
    cam = reads(["±3", "±2", "±7"], vlm=["±3", None, "±7"])
    with pytest.raises(O.Failed, match=r"00102_down\.png"):
        O.walk(cam, 2, ROW, "Custom 1")


def test_a_wrapping_list_and_a_box_with_ends_are_recorded_as_read(reads):
    """walk records what it reads, assuming no step: a box whose Down brings back a value already seen (the one held)
    is a list that comes round, recorded with no ends, in the order Up shows it from the value held; a box that stays
    on a further press has an end there. The reader confirms each end and the value come round. Lower Limit (no
    constant step held) may step unevenly; Range (STEPPED) must step evenly."""
    cam = reads(["100+", "95+", "85+", "70+", "100+"], vlm=["100+", None, None, None, "100+"])
    w = O.walk(cam, 1, ["Type", "Lower Limit"], "Custom 2")
    assert (w.values, w.held, w.wraps) == (["100+", "70+", "85+", "95+"], "100+", True)
    assert cam.presses == ["down"] * 4 and cam.asked == [0, 4]
    cam = reads(["95+", "85+", "85+", "95+", "100+", "100+"], vlm=["95+", None, "85+", None, None, "100+"])
    w = O.walk(cam, 1, ["Type", "Lower Limit"], "Custom 2")
    assert (w.values, w.held, w.wraps) == (["85+", "95+", "100+"], "95+", False)
    assert cam.presses == ["down", "down", "up", "up", "up"] and cam.asked == [0, 2, 5]
    cam = reads(["±3", "±2", "±3"], vlm=["±3", None, "±3"])
    w = O.walk(cam, 2, ROW, "Custom 1")
    assert (w.values, w.wraps) == (["±3", "±2"], True), "a STEPPED box that comes round is recorded so, not refused"


def test_a_walk_that_finds_neither_an_end_nor_its_values_coming_round_stops_at_the_cap(reads):
    """MAX_WALK presses with every reading new: the walk stops in plain words, no value assumed."""
    cam = reads(["300+"] + [f"{299 - k}+" for k in range(O.MAX_WALK + 5)], vlm=["300+"])
    with pytest.raises(O.Failed, match=f"neither an end .* within {O.MAX_WALK} Down presses"):
        O.walk(cam, 1, ["Type", "Lower Limit"], "Custom 2")
    assert cam.presses == ["down"] * O.MAX_WALK


def test_a_walk_stops_at_once_when_check_1_fails_and_the_reader_is_not_asked_there(reads):
    """After the second Down check 1 fails (the cursor gone from the box): the walk stops naming the box and the frame,
    no key goes after it, and the second reader is not asked on that frame, nor on any frame check 1 has not passed."""
    cam = reads(["±3", "±2", "±1", "±1"], vlm=["±3", "±2", "70+", "70+"], out={2})
    with pytest.raises(O.Failed, match=r"no longer in Custom 1's Range \(00102_down\.png\)"):
        O.walk(cam, 2, ROW, "Custom 1")
    assert cam.presses == ["down", "down"] and 2 not in cam.asked
    cam = reads(["±3"], vlm=["±3"])
    cam.press("down")                   # a frame no check has passed
    with pytest.raises(O.Failed, match="check 1 has not passed"):
        O.value_read(cam, 2, "±3", always=True)
    assert cam.asked == []


def test_ocr_reading_nothing_takes_the_readers_value_once_it_answers(reads, monkeypatch):
    """OCR read nothing in the box (241491's case): the reader's 64 is taken and logged; a reader that does not answer
    is asked once more after a short wait and its answer then taken."""
    cam = reads(["65", ""], vlm=[None, "64"])
    cam.i = 1
    O.in_box(cam, "Custom 1", "Standard", 1)
    got = O.value_read(cam, 1, "65", O._stepped("65", "65", "down", 1))
    assert (got.value, got.by, cam.asked) == ("64", "vlm", [1])
    answers = iter([(None, "vllm", False), ("64", "vllm", False)])
    calls = []
    monkeypatch.setattr(O, "box_answer", lambda c: calls.append(1) or next(answers))
    got = O.value_read(cam, 1, "65", O._stepped("65", "65", "down", 1))
    assert got.value == "64" and len(calls) == 2


def test_a_reader_that_does_not_answer_twice_stops_the_walk_in_plain_words(reads):
    """No answer, then none on the retry: the walk stops saying the second reader did not answer, never a guess."""
    cam = reads(["65", ""], vlm=[None, None])
    cam.i = 1
    O.in_box(cam, "Custom 1", "Standard", 1)
    with pytest.raises(O.Failed, match="second reader did not answer"):
        O.value_read(cam, 1, "65", O._stepped("65", "65", "down", 1))
    assert cam.asked == [1, 1]
    cam = reads(["±5"], vlm=[None])
    with pytest.raises(O.Failed, match="did not answer"):
        O.walk(cam, 2, ROW, "Custom 1")       # the held value is always asked: no answer stops it


def test_the_ok_consent_passes_on_its_own_screen_and_refuses_any_other():
    """camkit.live.option_boxes_refused, the OK's judge (the prover's before every OK, the camera's on a screen of no
    known kind): the title holds the option, the word above the lit box is the box's, that box is lit and holds the
    value, the footer draws the OK key, no question mark or confirmation word above it."""
    f = stored("kit2_look_zebra_a/shots/00014_right.png")
    lines = ocr_lines(STD70)
    ok = live.OptionBoxes("made up", "Custom 1", "Standard", "70", O.PLACES[1], tuple(O.PLACES))
    assert live.option_boxes_refused(ok, lines, f.image) == ""
    row = tuple(O.PLACES)
    for consent, why in ((live.OptionBoxes("x", "Custom 2", "Standard", "70", O.PLACES[1], row), "title"),
                         (live.OptionBoxes("x", "Custom 1", "Range", "70", O.PLACES[1], row), "word above"),
                         (live.OptionBoxes("x", "Custom 1", "Standard", "71", O.PLACES[1], row), "reads"),
                         (live.OptionBoxes("x", "Custom 1", "Standard", "70", O.PLACES[2], row), "box 2 of the row is lit"),
                         (live.OptionBoxes("x", "Custom 1", "Standard", "70", O.PLACES[2]), "no box of the row is lit")):
        assert why in live.option_boxes_refused(consent, lines, f.image)
    asks = [r if r[0] != "Std+Range" else ("Delete all settings?", *r[1:]) for r in STD70]
    assert "question mark" in live.option_boxes_refused(ok, ocr_lines(asks), f.image)
    no_ok = f.image.copy()
    no_ok[430:480, 540:640] = 0
    assert "OK key" in live.option_boxes_refused(ok, lines, no_ok)
    two = f.image.copy()
    two[349:404, 502:620] = two[349:404, 382:500]                  # Range drawn lit as well
    assert "2 boxes are lit" in live.option_boxes_refused(ok, lines, two)


@pytest.mark.parametrize("name,count,lit", [("241717_up.png", 3, [1]), ("241720_right.png", 2, [1]),
                                            ("241721_right.png", 2, []), ("241724_down.png", 2, []),
                                            ("241753_down.png", 0, []), ("241491_down.png", 3, [1]),
                                            ("241429_down.png", 3, [2]), ("241745_down.png", 3, [0])])
def test_the_rows_boxes_are_counted_by_their_outlines_and_the_lit_one_by_its_orange(name, count, lit):
    """camkit.live.boxes_drawn and boxes_lit, by pixels alone: three boxes under Std+Range, two under Lower Limit,
    none where the list's cursor is on a plain level (241753); the lit one by its orange, none with the list's cursor
    moving."""
    f = stored(f"kit2_pass2/shots/{name}")
    assert live.boxes_drawn(f.image, O.PLACES) == count and live.boxes_lit(f.image, O.PLACES) == lit


# ---------------------------------------------------------------- a made-up camera on the option's boxes


class Cam:
    """A made-up camera on Zebra Level, as the a1 II's frames show it (kit2_pass2 241717-241754): Right on the menu row
    opens the list on `start`; Down/Up step the list's cursor (it comes round); with an option that draws boxes lit,
    Right from the list enters them at the first box and Left from the list at the last; in the boxes Right lights the
    next and Left the one before, but Right on the last box (and, not seen on the camera, Left on the first) leaves
    them for the list, whose cursor Up and Down then move to another option. Up/Down step the lit box (Standard and
    Range stop at their ends, Type and, where `lower_wraps`, Lower Limit come round); OK keeps it all and closes; MENU
    (close) cancels the screen's changes. Each press shows a new frame. `off_ends` counts the presses that left the
    boxes so; `records` is what a download holds: Zebra Level's option and each box's value."""
    LIST = ["70", "75", "80", "85", "90", "95", "100", "100+", "Custom 1", "Custom 2"]
    TYPES = ["Std+Range", "Lower Limit"]

    def __init__(self, start="70", eyes="hdmi", lower_wraps=False):
        self.level, self.at, self.lit, self.open = start, 0, None, False
        self.saved = {"Custom 1": {"Type": "Std+Range", "Standard": 70, "Range": 5, "Lower Limit": 100},
                      "Custom 2": {"Type": "Lower Limit", "Standard": 70, "Range": 5, "Lower Limit": 100}}
        self.edit = None
        self.lower_wraps = lower_wraps
        self.presses, self.consents, self.shown, self.off_ends = [], [], [], []
        self.hdmi = SimpleNamespace(name=eyes)
        self.frame = SimpleNamespace(path=Path("00001_x.png"), image=None)
        self.answer_once = None

    # what the screen shows
    def option(self):
        return self.LIST[self.at]

    def boxes(self):
        if not self.open or not self.option().startswith("Custom"):
            return []
        v = self.edit or self.saved[self.option()]
        if v["Type"] == "Std+Range":
            return [("Type", v["Type"]), ("Standard", str(v["Standard"])), ("Range", f"±{v['Range']}")]
        return [("Type", v["Type"]), ("Lower Limit", f"{v['Lower Limit']}+")]

    def press(self, key, **k):
        self.presses.append(key)
        self.frame = SimpleNamespace(path=Path(f"{len(self.presses) + 1:05d}_{key}.png"), image=None)
        if not self.open:
            if key == "right":
                self.open, self.at = True, self.LIST.index(self.level)
            return
        boxes = self.boxes()
        if key in ("right", "left") and self.lit is None:
            if boxes:                   # from the list: Right enters at the first box, Left at the last
                self.edit = self.edit or dict(self.saved[self.option()])
                self.lit = 0 if key == "right" else len(boxes) - 1
        elif key in ("right", "left"):
            to = self.lit + (1 if key == "right" else -1)
            if 0 <= to < len(boxes):
                self.lit = to
            else:                       # off the row's end: the cursor goes to the list
                self.off_ends.append((key, self.lit, self.frame.path.name))
                self.lit = None
        elif key in ("up", "down"):
            if self.lit is None:
                self.at = (self.at + (1 if key == "down" else -1)) % len(self.LIST)
                self.edit = None
            else:
                name = boxes[self.lit][0]
                if name == "Type":
                    i = self.TYPES.index(self.edit["Type"])
                    self.edit["Type"] = self.TYPES[(i + 1) % 2]
                elif name == "Lower Limit" and self.lower_wraps:
                    self.edit[name] = 50 + (self.edit[name] - 50 + (1 if key == "up" else -1)) % 60
                else:
                    lo, hi = {"Standard": (0, 109), "Range": (1, 10), "Lower Limit": (50, 109)}[name]
                    self.edit[name] = max(lo, min(hi, self.edit[name] + (1 if key == "up" else -1)))
        elif key == "enter":
            self.consents.append(self.answer_once)
            self.answer_once = None
            self.level = self.option()
            if self.edit:
                self.saved[self.option()] = dict(self.edit)
            self.close()
        self.shown.append((self.lit, tuple(self.boxes())))

    def close(self):
        self.open, self.lit, self.edit = False, None, None

    def records(self):
        out = {"global:0x0379": self.LIST.index(self.level)}
        for o, base in (("Custom 1", 0x0dde), ("Custom 2", 0x0de6)):
            v = self.saved[o]
            out.update({f"global:0x{base:04x}": self.TYPES.index(v["Type"]), f"global:0x{base + 2:04x}": v["Lower Limit"],
                        f"global:0x{base + 4:04x}": v["Standard"], f"global:0x{base + 6:04x}": v["Range"]})
        return out


@pytest.fixture
def fake(monkeypatch):
    """optboxes_run's camera seams on a Cam: its readers read the made-up state, the menu, the scan's route and the
    shooting screen made up; the OK judge passes on a screen whose state holds what the consent names."""
    monkeypatch.setattr(O, "title", lambda cam: cam.option() if cam.open else "")
    monkeypatch.setattr(O, "word", lambda cam: cam.boxes()[cam.lit][0] if cam.lit is not None else "")
    monkeypatch.setattr(O, "lit_place", lambda cam: cam.lit)
    monkeypatch.setattr(O, "read_at", lambda cam, b: cam.boxes()[b][1] if b < len(cam.boxes()) else "")
    monkeypatch.setattr(O, "drawn", lambda cam: len(cam.boxes()))

    def cursor(cam, option, name, b):   # check 1 on the made-up screen: the option, its box b the one lit, its word
        if not cam.open or cam.option() != option:
            return f"its title line reads {cam.option() if cam.open else ''!r}, not {option}"
        if cam.lit is None:
            return "no box of the row is lit"
        if cam.lit != b:
            return f"box {cam.lit + 1} of the row is lit, not box {b + 1}"
        return "" if name is None or cam.boxes()[b][0] == name else f"the word above the row is not {name}"
    monkeypatch.setattr(O, "cursor_refused", cursor)
    monkeypatch.setattr(O, "menu_from_shooting", lambda cam: None)
    monkeypatch.setattr(O, "scan_position", lambda cam, cycle: 0)
    monkeypatch.setattr(O, "go_to", lambda *a: True)
    monkeypatch.setattr(O, "close_screen", lambda cam, link: cam.close())
    monkeypatch.setattr(O, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(O.time, "sleep", lambda s: None)

    def judged(cam, consent, read=None):
        boxes = cam.boxes()
        ok = cam.option() == consent.option and cam.lit is not None and boxes[cam.lit] == (consent.word, consent.value)
        return "" if ok else "not that screen"
    monkeypatch.setattr(O, "ok_refused", judged)
    # the second reader reads the lit box as drawn, in its own words (a range with its sign): what a proof line keeps
    monkeypatch.setattr(O, "box_answer", lambda cam: (cam.boxes()[cam.lit][1] if cam.lit is not None else None,
                                                      "vllm", False))
    return Cam


def link_for(cam):
    """A link whose downloads hold the made-up camera's records at that moment."""
    downloads = []

    def download(tag):
        downloads.append(SimpleNamespace(name=f"{len(downloads) + 2:05d}_{tag}.DAT", values=cam.records()))
        return downloads[-1]
    return SimpleNamespace(download=download, downloads=downloads)


def test_a_number_box_is_walked_to_both_ends_and_type_once_round(fake):
    """walk: Down until a further press changes nothing (the low end) or comes round, then Up the same way, the values in
    Up order; Standard from 70 gives 0 to 109, Type (two options that come round) both, the held value kept."""
    cam = fake()
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, ROW, "Custom 1")
    w = O.walk(cam, 1, ROW, "Custom 1")
    assert w.held == "70" and w.values == [str(v) for v in range(110)] and not w.wraps
    cam = fake()
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 0, ROW, "Custom 1")
    assert O.walk(cam, 0, ["Type"], "Custom 1") == (["Std+Range", "Lower Limit"], "Std+Range", True)


@pytest.mark.parametrize("lower_wraps", [False, True])
def test_the_probe_reads_every_box_under_each_type_and_chooses_nothing(fake, lower_wraps):
    """--probe: the option lit, each Type's row of boxes counted as drawn and named, each box walked (Range before
    Standard, so Standard never passes 30 with Range at ±5), MENU at the end; no OK pressed, the camera's saved values
    untouched. A Lower Limit with ends is recorded with them, one that comes round as a list with no ends."""
    cam = fake(lower_wraps=lower_wraps)
    got = O.probe(cam, None, None, None, "Zebra Level", "Custom 1")
    assert got["types"] == {"Std+Range": ["Type", "Standard", "Range"], "Lower Limit": ["Type", "Lower Limit"]}
    assert got["boxes"]["Type"] == {"values": ["Std+Range", "Lower Limit"], "held": "Std+Range", "wraps": True}
    assert got["boxes"]["Standard"]["values"][0] == "0" and got["boxes"]["Standard"]["values"][-1] == "109"
    assert got["boxes"]["Range"] == {"values": [f"±{v}" for v in range(1, 11)], "held": "±5", "type": "Std+Range",
                                     "wraps": False}
    lower = got["boxes"]["Lower Limit"]
    assert lower["type"] == "Lower Limit" and lower["wraps"] == lower_wraps and len(lower["values"]) == 60
    assert lower["values"][:2] == (["100+", "101+"] if lower_wraps else ["50+", "51+"])
    assert O.probe_refused(got) == ""
    assert "enter" not in cam.presses and cam.saved["Custom 1"]["Standard"] == 70
    assert not any(lit == 1 and boxes[1:] == (("Standard", "30"), ("Range", "±5")) for lit, boxes in cam.shown)


def test_the_prover_never_presses_past_either_end_of_the_row(fake, monkeypatch):
    """On a camera where Right on the last box leaves the boxes for the list (241721, 241750) and Left from there
    lights the last box again (241722, 241751): the probe and the proof run count the row's boxes from what is drawn
    and move between them by that count, so no Right is ever sent on the last box, nor a Left on the first."""
    cam = fake()
    probed = O.probe(cam, None, None, None, "Zebra Level", "Custom 1")
    assert cam.off_ends == []
    monkeypatch.setattr(O.camset, "read", lambda d: d.values)
    monkeypatch.setattr(O.camset, "diff", lambda a, b: [])
    start = SimpleNamespace(name="00001_before.DAT", values=cam.records())
    O.prove(cam, link_for(cam), None, None, None, "Zebra Level", "Custom 1", probed, None, start, Lines())
    assert cam.off_ends == [] and cam.consents


def test_a_press_that_leaves_the_boxes_stops_the_run_before_another_key(fake):
    """The cursor gone from the box after a press (here a camera whose second box is not drawn as counted, so the
    Right to it lands on the list): check 1 stops the run at once in plain words, and no key goes after it."""
    cam = fake()
    O.open_option(cam, None, None, "Zebra Level", "Custom 2")       # Lower Limit: Type and one box
    O.enter_box(cam, 0, ["Type", "Lower Limit"], "Custom 2")
    O.go(cam, "Custom 2", ["Type", "Lower Limit"], 0, 1)
    sent = len(cam.presses)
    with pytest.raises(O.Failed, match=r"the cursor is no longer in Custom 2's Range .*no box of the row is lit"):
        O.go(cam, "Custom 2", ["Type", "Lower Limit", "Range"], 1, 2)
    assert len(cam.presses) == sent + 1 and cam.presses[-1] == "right"
    with pytest.raises(O.Failed, match="no box 4"):
        O.go(cam, "Custom 2", ROW, 0, 3)


def test_the_proof_values_take_the_ends_the_neighbours_a_middle_and_the_held_last():
    """values_for: both ends, the held value's neighbours, one in the middle, then the held value, which must change
    nothing; Standard 30 is never among them while Range is ±5."""
    vals = [str(v) for v in range(110)]
    assert O.values_for("Standard", vals, "70", range_held="±6") == ["0", "109", "69", "71", "55", "70"]
    std = O.values_for("Standard", vals, "31", range_held="±5")
    assert "30" not in std and std[-1] == "31"
    assert O.values_for("Type", ["Std+Range", "Lower Limit"], "Std+Range") == ["Lower Limit", "Std+Range"]
    ring = ["100+", "101+", "102+", "50+", "51+", "52+"]       # a list that comes round, from the value held
    assert O.values_for("Lower Limit", ring, "100+", wraps=True) == ["52+", "101+", "50+", "100+"]


def test_standard_30_with_range_5_is_refused_on_osd_eyes_and_crossed_safely_otherwise(fake):
    """The screen "Standard lit at 30, Range ±5" stalls the remote link while the kit reads the screen through it (OSD
    eyes): stepping onto it there is refused in plain words; with HDMI eyes it is stepped across as any value."""
    cam = fake(eyes="osd")
    cam.saved["Custom 1"]["Standard"] = 32
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, ROW, "Custom 1")
    with pytest.raises(O.Refused, match="stalls the camera's remote link"):
        O.step_to(cam, 1, [str(v) for v in range(110)], "20", ROW, "Custom 1")
    assert O.read_at(cam, 1) == "31"
    cam = fake(eyes="hdmi")
    cam.saved["Custom 1"]["Standard"] = 32
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, ROW, "Custom 1")
    O.step_to(cam, 1, [str(v) for v in range(110)], "20", ROW, "Custom 1")
    assert O.read_at(cam, 1) == "20"


def probe_of(cam):
    return O.probe(cam, None, None, None, "Zebra Level", "Custom 1")


class Lines(list):
    def write(self, line):
        self.append(json.loads(line))

    def flush(self):
        pass


def test_the_proof_run_proves_each_box_from_its_own_base(fake, monkeypatch):
    """prove: a base first (the option chosen as it stands: Zebra Level's own record moves there, never in a box's
    proof), then each box's values, the held one last; Lower Limit from a base with Type on Lower Limit; on OSD eyes
    Standard from a base with Range one step off ±5. Each proof line in boxes_run's shape (path row > option > box,
    kind list, its index among the probe's values), its changes the box's record alone."""
    for eyes in ("hdmi", "osd"):
        cam = fake(eyes=eyes)
        probed = probe_of(fake(eyes=eyes))
        link = link_for(cam)
        monkeypatch.setattr(O.camset, "read", lambda d: d.values)
        monkeypatch.setattr(O.camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a[k], after=b[k])
                                                            for k in a if a[k] != b[k]])
        out = Lines()
        start = SimpleNamespace(name="00001_before.DAT", values=cam.records())
        O.prove(cam, link, None, None, None, "Zebra Level", "Custom 1", probed, None, start, out)
        by_box = {}
        for r in out:
            assert r["path"][:2] == ["Zebra Level", "Custom 1"] and r["kind"] == "list" and r["boxes"] is True
            assert r["index"] == probed["boxes"][r["path"][2]]["values"].index(r["label"])
            assert "global:0x0379" not in [c["key"] for c in r["changes"]]
            by_box.setdefault(r["path"][2], []).append(r)
        assert set(by_box) == {"Type", "Standard", "Range", "Lower Limit"}
        assert all(r["vlm"] == r["shown"] == r["label"] for r in out), "OCR's reading and the second reader's, both kept"
        assert all(r["vlm_reader"] == "vllm" and r["read_by"] == "both" for r in out), "the reader of each kept value"
        assert [c["key"] for c in by_box["Standard"][0]["changes"]] == ["global:0x0de2"]
        assert [c["key"] for c in by_box["Lower Limit"][0]["changes"]] == ["global:0x0de0"]
        assert all(r["changes"] == [] for r in (rows[-1] for rows in by_box.values())), "the held value changes nothing"
        bases = {r["base"] for r in by_box["Standard"]}
        assert len(bases) == 1 and (bases != {r["base"] for r in by_box["Range"]}) == (eyes == "osd")


def test_a_value_whose_records_did_not_move_is_kept_as_not_proved(fake, monkeypatch, capsys):
    """A value chosen whose download differs in no record from its base: the line keeps it with no changes (the report
    credits it nothing), and the run says it was not proved, never guessing a record."""
    cam = fake()
    probed = probe_of(fake())
    monkeypatch.setattr(O.camset, "read", lambda d: d.values)
    monkeypatch.setattr(O.camset, "diff", lambda a, b: [])
    out = Lines()
    start = SimpleNamespace(name="00001_before.DAT", values=cam.records())
    O.prove(cam, link_for(cam), None, None, None, "Zebra Level", "Custom 1", probed, "Range", start, out)
    assert out and all(r["changes"] == [] for r in out) and "not proved" in capsys.readouterr().out


def run_main(monkeypatch, tmp_path, body, args=()):
    @contextlib.contextmanager
    def session(run, eyes):
        try:
            yield SimpleNamespace(cam=None, link=None, start=tmp_path / "00001_before.DAT")
        except Exception as e:
            print(f"stopped: {type(e).__name__}: {e}")
    monkeypatch.setattr(O, "load_scan", lambda scan: (None, None))
    monkeypatch.setattr(O, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    monkeypatch.setattr(O, "eyes_from_config", lambda run: None)
    monkeypatch.setattr(O, "prover_session", session)
    monkeypatch.setattr(O, "latest_probe", lambda run, row, option: {
        "types": {"Std+Range": ["Type"]}, "boxes": {"Type": {"values": ["Std+Range"], "held": "Std+Range"}}})
    monkeypatch.setattr(O, "prove", body)
    monkeypatch.setattr(O, "probe", body)
    O.main(["--row", "Zebra Level", "--option", "Custom 1", "--scan", str(tmp_path), *args])


def raises(e):
    def body(*a, **k):
        raise e
    return body


@pytest.mark.parametrize("args", [(), ("--probe",)])
def test_a_stopped_run_exits_as_the_other_provers_do(monkeypatch, tmp_path, args):
    """Once the session has restored the start file: a refusal exits 7, any other stop 8, a run that ends or a STOP 0."""
    for e, code in ((safety.Refused("enter refused"), EXIT_REFUSED), (O.Failed("its title does not read Custom 1"),
                                                                      EXIT_INCOMPLETE)):
        with pytest.raises(SystemExit) as got:
            run_main(monkeypatch, tmp_path, raises(e), args)
        assert got.value.code == code
    run_main(monkeypatch, tmp_path, lambda *a, **k: None, args)
    run_main(monkeypatch, tmp_path, raises(StopRequested("STOP")), args)


def test_a_probe_writes_its_line_only_when_it_read_every_box(monkeypatch, tmp_path, capsys):
    """--probe: a probe that ends writes its one line (PROBES); one stopped part way (check 1 failing, a reader
    that does not answer) writes nothing and says so."""
    with pytest.raises(SystemExit):
        run_main(monkeypatch, tmp_path, raises(O.Failed("the cursor is no longer in Custom 1's Lower Limit")), ["--probe"])
    assert not (tmp_path / O.PROBES).exists() and f"nothing was written to {O.PROBES}" in capsys.readouterr().out
    got = {"row": "Zebra Level", "option": "Custom 1", "types": {"Std+Range": ["Type"]},
           "boxes": {"Type": {"values": ["Std+Range", "Lower Limit"], "held": "Std+Range", "wraps": True}}}
    run_main(monkeypatch, tmp_path, lambda *a, **k: got, ["--probe"])
    lines = (tmp_path / O.PROBES).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["types"] == got["types"]
    assert "a list that comes round" in capsys.readouterr().out


def test_a_proof_run_with_no_probe_stops_before_the_link(monkeypatch, tmp_path, no_camera):
    """The proof run plans from the option's probe: with none in the run, it stops naming the probe command; with a
    probe line that lacks a box of a Type's row (written before the probe wrote only whole probes), it stops naming the
    box. Nothing reached either way."""
    monkeypatch.setattr(O, "load_scan", lambda scan: (None, None))
    monkeypatch.setattr(O, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    with pytest.raises(SystemExit, match="--probe"):
        O.main(["--row", "Zebra Level", "--option", "Custom 1", "--scan", str(tmp_path)])
    part = {"row": "Zebra Level", "option": "Custom 1", "types": {"Std+Range": ROW, "Lower Limit": ["Type", "Lower Limit"]},
            "boxes": {n: {"values": ["x"], "held": "x"} for n in ("Type", "Standard", "Range")}}
    (tmp_path / O.PROBES).write_text(json.dumps(part) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="lacks the walk of Lower Limit"):
        O.main(["--row", "Zebra Level", "--option", "Custom 1", "--scan", str(tmp_path)])
    assert O.probe_refused({"types": {}, "boxes": {}}) == "it records no row of boxes"
