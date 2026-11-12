"""The scale prover (kit/provers/scale_run.py) off the camera: its number read by OCR, else by the vision reader (one
question a frame, an answer that is no number counting as none), both cleaned alike and compared by key, which of the
two read the value chosen, and the look and a choice on a made-up scale where OCR reads some numbers and gives nothing
for others (2026-11-09): every number read in order, or the row stopped naming the frame no one read, its screen
closed; a number only the reader read never decides an end or a choice alone, so a reader one off gives a look that
fails or the whole scale, and a choice that fails or lands where it should. Every scale, frame and reading here is
made up; nothing talks to a camera or a reader."""
import itertools
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
import scale_run as S  # noqa: E402
from camkit.ocr import Line  # noqa: E402

PATH = ["Made-up Scale"]
VALS = ["0", "1", "2", "3", "4"]


class Scale:
    """A made-up scale 0..4 with 3 held: Left and Right step the number, stopping at the ends; every press, a refresh
    (a frame grabbed without a press) and the shooting screen a close comes back to, is a new frame."""

    def __init__(self, held=3, top=4):
        self.pos, self.top, self.n, self.truth, self.presses = held, top, 0, {}, []
        self.shoot()

    def shoot(self):
        self.n += 1
        p = Path(f"{self.n:05d}_scale.png")
        self.truth[p] = self.pos
        self.frame = SimpleNamespace(path=p)

    def press(self, key):
        self.presses.append(key)
        if key == "left":
            self.pos = max(0, self.pos - 1)
        elif key == "right":
            self.pos = min(self.top, self.pos + 1)
        self.shoot()

    def refresh(self, tag):
        self.shoot()


def answer(said):
    """The reader's whole answer to the option question as a made-up reader gives it: a text is its "selected" (the
    value field empty), an object is passed as it is, None is a reader that failed."""
    return {"title": PATH[0], "selected": said, "value": ""} if isinstance(said, str) else said


def digit(text) -> Line:
    """A number as OCR finds it between the ◂ ▸: centred near x 320, digit-tall."""
    return Line(text=text, conf=1.0, x=311, y=287, w=18, h=29)


@pytest.fixture
def rig(monkeypatch):
    """rig(cam, ocr_reads, reader, shown): OCR reads shown(true number) on the frames whose true number is in
    ocr_reads (or, a function, where ocr_reads(frame path, true number) says so) and nothing on the others; the reader
    answers reader(true number): its "selected", or its whole answer (answer). Returns the log: the frames the reader
    was asked about, the closes."""
    def setup(cam, ocr_reads, reader=str, shown=str):
        log = SimpleNamespace(asked=[], closes=[], downloads=[])
        monkeypatch.setattr(S, "_said", {})
        monkeypatch.setattr(S, "_by_reader", set())
        reads = ocr_reads if callable(ocr_reads) else (lambda p, true: true in ocr_reads)

        def read(paths, eng=None):
            return {p: [digit(shown(cam.truth[p]))] if p in cam.truth and reads(p, cam.truth[p]) else []
                    for p in paths}

        def option_answer(c):
            log.asked.append(c.frame.path)
            return answer(reader(cam.truth[c.frame.path]))

        def close_screen(c, link):
            log.closes.append(c.frame.path)
            cam.shoot()                      # back on the shooting screen: another frame

        monkeypatch.setattr(S.ocr, "read", read)
        monkeypatch.setattr(S, "option_answer", option_answer)
        monkeypatch.setattr(S, "open_row", lambda c, cycle, model, path, panel=False: None)
        monkeypatch.setattr(S, "close_screen", close_screen)
        monkeypatch.setattr(S, "to_shooting", lambda link, hdmi, why: None)
        monkeypatch.setattr(S, "time", SimpleNamespace(sleep=lambda s: None))
        log.link = SimpleNamespace(download=lambda name: log.downloads.append(name) or Path(f"{name}.DAT"))
        return log
    return setup


# ---------------------------------------------------------------- one frame's number

def test_a_number_ocr_reads_asks_no_reader(rig):
    cam = Scale()
    log = rig(cam, {0, 1, 2, 3, 4})
    assert S.value(cam) == "3" and S.read_by(cam) == "ocr"
    assert log.asked == []


def test_where_ocr_reads_nothing_the_reader_gives_the_number(rig):
    cam = Scale()
    log = rig(cam, set())
    assert S.ocr_value(cam) == ""
    assert S.value(cam) == "3" and S.read_by(cam) == "reader"
    assert log.asked == [cam.frame.path]


@pytest.mark.parametrize("said, got", [("±0", "0"), ("+2", "+2"), ("-1", "-1"), ("−1", "-1"), (" 6 ", "6"),
                                       ("0.5", "0.5"), ("80%", "80%"), ("12", "12"),
                                       ("Cancel", ""), ("", ""), ("6/15", ""), ("1234", ""), ("Vol 6", "")])
def test_the_readers_answer_is_cleaned_as_ocrs_and_counts_only_as_a_number(rig, said, got):
    cam = Scale()
    rig(cam, set(), reader=lambda true: said)
    assert S.reader_value(cam) == got
    assert S.value(cam) == got
    assert S.read_by(cam) == ("reader" if got else "ocr")


def test_the_reader_is_asked_once_a_frame_however_often_it_is_read(rig):
    cam = Scale()
    log = rig(cam, set())
    first = cam.frame.path
    assert [S.value(cam) for _ in range(5)] == ["3"] * 5
    assert S.reader_said(S.asked(cam))[0] == "3"        # the second reading a proof keeps: the same answer
    cam.press("left")
    assert S.value(cam) == S.value(cam) == "2"
    assert log.asked == [first, cam.frame.path]


def test_a_reader_that_gives_nothing_is_not_asked_again_on_that_frame(rig):
    cam = Scale()
    log = rig(cam, set(), reader=lambda true: "")
    assert [S.value(cam) for _ in range(3)] == [""] * 3
    assert len(log.asked) == 1


# ---------------------------------------------------------------- the look

def test_the_look_reads_every_number_in_order_where_ocr_reads_only_some(rig):
    """OCR reads 0 and 3 and nothing on the other frames: the reader gives 1, 2 and 4, one question a frame, and the
    look comes back with the five numbers, low to high, and the one held."""
    cam = Scale()
    log = rig(cam, {0, 3})
    assert S.ends(cam, log.link, None, None, PATH) == (VALS, "3")
    assert len(log.asked) == len(set(log.asked)), "a frame asked about twice"
    assert all(cam.truth[p] not in (0, 3) for p in log.asked), "the reader asked where OCR read a number"
    # each end is confirmed by one more press (Left at 0, Right at 4), and Left from the high end reads the 3
    assert cam.presses == ["left"] * 4 + ["left"] + ["right"] * 5 + ["right", "left"]
    assert len(log.closes) == 1


def test_the_look_stops_naming_the_frame_no_one_reads_a_number_on(rig):
    """OCR reads only the number held and the reader gives no number: the first frame after Left is no number, never
    taken for the end of the scale; the row stops naming that frame, its screen closed first."""
    cam = Scale()
    log = rig(cam, {3}, reader=lambda true: "")
    with pytest.raises(S.Failed, match=r"Made-up Scale: no number read on the scale on frame 00002_scale\.png"):
        S.ends(cam, log.link, None, None, PATH)
    assert log.closes == [Path("00002_scale.png")]
    assert cam.presses == ["left"]


# ---------------------------------------------------------------- a choice

def test_a_choice_the_reader_read_says_so(rig):
    cam = Scale()
    log = rig(cam, {3})
    got = S.choose(cam, log.link, None, None, None, PATH, VALS, 1)
    assert cam.presses == ["left", "left", "enter"]
    assert got["read_by"] == "reader" and got["vlm"] == "1"
    assert got["chosen_frame"] == "00003_scale.png" and got["row_frame"] == "00004_scale.png"
    assert log.asked.count(Path("00003_scale.png")) == 1, "the chosen frame asked about once, for both readings"
    assert log.downloads == ["Made-up Scale-1"] and log.closes == []


def test_a_choice_ocr_read_says_so_and_still_keeps_the_readers_reading(rig):
    cam = Scale()
    log = rig(cam, {0, 1, 2, 3, 4})
    got = S.choose(cam, log.link, None, None, None, PATH, VALS, 4)
    assert cam.presses == ["right", "enter"]
    assert got["read_by"] == "ocr" and got["vlm"] == "4"
    assert log.asked == [Path("00002_scale.png")]


def test_a_choice_stops_naming_the_frame_no_one_reads_a_number_on(rig):
    cam = Scale()
    log = rig(cam, {3}, reader=lambda true: "Cancel")
    with pytest.raises(S.Failed, match=r"no number read on the scale on frame 00002_scale\.png"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 1)
    assert log.closes == [Path("00002_scale.png")]
    assert "enter" not in cam.presses and log.downloads == []


# ---------------------------------------------------------------- signs, and the key readings are compared by

DASH_CHARS = ["−", "–", "‐", "‑", "—", "﹣", "－", "-"]


@pytest.mark.parametrize("dash", DASH_CHARS)
def test_every_dash_is_a_minus_sign_whoever_read_it(rig, dash):
    """OCR's reading and the reader's are cleaned alike: a minus sign drawn as any dash stays a minus sign, so "−1" is
    "-1" from OCR as from the reader (OCR's dropped it before 2026-11-09, the reader's kept it: "1" against "-1")."""
    assert S.clean(f"{dash}1") == "-1" and S.clean(f" {dash}2 ") == "-2"
    cam = Scale()
    rig(cam, {3}, shown=lambda true: f"{dash}{true}")
    assert S.ocr_value(cam) == "-3" and S.read_by(cam) == "ocr"
    cam = Scale()
    rig(cam, set(), reader=lambda true: f"{dash}{true}")
    assert S.value(cam) == "-3" and S.read_by(cam) == "reader"


@pytest.mark.parametrize("dash", ["−", "—", "-", "+", "%"])
def test_a_sign_alone_is_no_number_from_ocr_and_the_reader_is_asked(rig, dash):
    cam = Scale()
    log = rig(cam, {3}, shown=lambda true: dash)
    assert S.ocr_value(cam) == ""
    assert S.value(cam) == "3" and S.read_by(cam) == "reader" and len(log.asked) == 1


@pytest.mark.parametrize("a, b", [("+2", "2"), ("+0", "0"), ("-0", "0"), ("0", "0"), ("80%", "80"), ("+5%", "5"),
                                  ("-1", "-1"), ("0.5", "0.5"), ("+0.5", "0.5")])
def test_the_key_takes_a_sign_style_or_a_percent_for_one_number(a, b):
    assert S.key(a) == S.key(b) == b


@pytest.mark.parametrize("a, b", [("-1", "1"), ("-2", "+2"), ("0.5", "5"), ("1", "11")])
def test_the_key_keeps_numbers_apart_that_differ(a, b):
    assert S.key(a) != S.key(b)


def test_a_sign_ocr_draws_and_the_reader_leaves_out_is_one_number_at_the_end_of_the_scale(rig):
    """A scale −2 .. +2 with ±0 held: OCR reads every number with its sign, but on the frames after the first at +2 it
    reads nothing, and the reader says "2". The "2" is the "+2" OCR read (by key), so the high end is seen (one more
    Right confirms it, and Left from it reads +1), never appended as a sixth value; the labels stay as first read."""
    labels = {0: "−2", 1: "−1", 2: "±0", 3: "+1", 4: "+2"}
    cam = Scale(held=2)
    first_top = []

    def ocr_reads(path, true):
        if true != 4:
            return True
        first_top.append(path) if not first_top else None
        return path == first_top[0]
    log = rig(cam, ocr_reads, reader=lambda true: labels[true].lstrip("+"), shown=lambda true: labels[true])
    vals, held = S.ends(cam, log.link, None, None, PATH)
    assert vals == ["-2", "-1", "0", "+1", "+2"] and held == "0"
    assert cam.presses == ["left"] * 3 + ["left"] + ["right"] * 5 + ["right", "left"]
    assert [S.key(v) for v in vals] == ["-2", "-1", "0", "1", "2"] and len(log.closes) == 1


def test_a_choice_takes_the_number_by_key_whoever_read_it(rig):
    """The look's "+1" (OCR) is the reader's "1" on the frame chosen: the choice stops there, counted, and says so."""
    labels = {0: "-2", 1: "-1", 2: "0", 3: "+1", 4: "+2"}
    cam = Scale(held=2)
    log = rig(cam, {0, 1, 2}, reader=lambda true: labels[true].lstrip("+"), shown=lambda true: labels[true])
    got = S.choose(cam, log.link, None, None, None, PATH, list(labels.values()), 3, 2)
    assert cam.presses == ["right", "enter"] and got["read_by"] == "reader" and got["vlm"] == "1"


# ---------------------------------------------------------------- a reader one off never decides alone

def one_off(at, by):
    """A reader that reads the number at true position `at` `by` off (the next number), every other one right."""
    return lambda true: str(true + by) if true == at else str(true)


def test_a_reader_one_too_high_where_the_number_stops_changing_is_caught_by_one_more_press(rig):
    """Left from 3: OCR reads only the 3; the reader reads 2, then (one too high) 2 again at 1, as if the scale ended
    there, and again on a fresh frame (00004). One more Left reads 0: the end was not the end, and the row stops naming
    the frames, never a scale of 2, 3, 4."""
    cam = Scale()
    log = rig(cam, {3}, reader=one_off(1, +1))
    with pytest.raises(S.Failed, match=r"'2' \(00002_scale\.png\) and '2' \(00004_scale\.png\) read as the low end, but "
                                       r"one more Left read '0' \(00005_scale\.png\): a press went unanswered, or the "
                                       r"readings disagree"):
        S.ends(cam, log.link, None, None, PATH)
    assert cam.presses == ["left"] * 3 and log.closes == [Path("00005_scale.png")]


def test_a_reader_one_too_high_just_below_the_high_end_is_caught_by_left_from_it(rig):
    """OCR reads only the 0; the reader reads the 3 as 4, so 4 and 4 look like the high end and one more Right reads 4
    again: Left from it must read the number before, 2, and reads 4 (the misread 3): the row stops, never a scale of
    0, 1, 2, 4."""
    cam = Scale(held=2)
    log = rig(cam, {0}, reader=one_off(3, +1))
    with pytest.raises(S.Failed, match=r"read as the high end, but Left from it read '4' \(\d+_scale\.png\), not '2'"):
        S.ends(cam, log.link, None, None, PATH)
    assert len(log.closes) == 1


def test_a_reader_one_too_high_at_the_high_end_reads_steps_that_are_uneven(rig):
    """The reader reads the 4 at the high end as 5 every time and OCR never reads it: nothing on the camera tells the
    end was misread but the steps, 0, 1, 2, 3, 5: whole numbers the reader helped read must step evenly."""
    cam = Scale()
    log = rig(cam, {0, 1, 2, 3}, reader=one_off(4, +1))
    with pytest.raises(S.Failed, match=r"the look read \['0', '1', '2', '3', '5'\], whole numbers stepping unevenly"):
        S.ends(cam, log.link, None, None, PATH)
    assert len(log.closes) == 1


def test_a_held_number_the_reader_misread_stands_where_the_left_presses_counted_it(rig):
    """Only the frame the scale opens on is misread (the held 2 as 3); the look reads 0 .. 4 right, but 3 is three
    places above the low end where two Left presses changed the number: the readings disagree."""
    cam = Scale(held=2)
    calls = []

    def reader(true):
        calls.append(true)
        return str(true + 1) if len(calls) == 1 else str(true)
    log = rig(cam, set(), reader=reader)
    with pytest.raises(S.Failed, match=r"the reader read '3' held \(00001_scale\.png\), 3 places above the low end, "
                                       r"but 2 Left presses changed the number"):
        S.ends(cam, log.link, None, None, PATH)
    assert len(log.closes) == 1


def look_or_fail(rig, held, ocr, reader):
    cam = Scale(held=held)
    log = rig(cam, set(ocr), reader=reader)
    try:
        got = S.ends(cam, log.link, None, None, PATH)
    except S.Failed:
        got = None
    assert len(log.closes) == 1, "the screen closed once, whatever the look found"
    return got


@pytest.mark.parametrize("held", range(5))
def test_with_the_reader_right_every_look_reads_the_whole_scale(rig, held):
    for k in range(6):
        for ocr in itertools.combinations(range(5), k):
            assert look_or_fail(rig, held, ocr, str) == (VALS, str(held)), (held, ocr)


@pytest.mark.parametrize("by", [+1, -1])
@pytest.mark.parametrize("held", range(5))
def test_a_reader_one_off_at_one_number_gives_a_look_that_fails_or_the_whole_scale(rig, held, by):
    """The reader reads one number one off (the next number, above or below) wherever it is asked about it, on every
    frame OCR misses; whatever OCR reads of the rest and wherever the scale is held, the look stops or comes back with
    the whole scale and the right held number, never a shortened or a misread one."""
    for at in range(5):
        others = [n for n in range(5) if n != at]
        for k in range(5):
            for ocr in itertools.combinations(others, k):
                got = look_or_fail(rig, held, ocr, one_off(at, by))
                assert got in (None, (VALS, str(held))), (held, at, by, ocr, got)


@pytest.mark.parametrize("held", range(5))
def test_a_reader_one_off_on_one_frame_only_gives_a_look_that_fails_or_the_whole_scale(rig, held):
    """The reader errs once, on its n-th answer, one too high or one too low; OCR reads nothing. The look stops or
    reads the whole scale, and the held number is right but in one case: the frame the scale opens on, held at the low
    end or next to it, misread by one while the reader reads that place right on a later frame. No press of the look
    can tell; main's first choice can (test_a_held_number_misread_where_the_scale_opens_stops_the_row_before_any_line)."""
    for n in range(16):
        for by in (+1, -1):
            calls = []

            def reader(true, n=n, by=by, calls=calls):
                calls.append(true)
                return str(true + by) if len(calls) == n + 1 else str(true)
            got = look_or_fail(rig, held, (), reader)
            assert got is None or got[0] == VALS, (held, n, by, got)
            if got and got[1] != str(held):
                assert n == 0 and {held, held + by} == {0, 1} and got[1] == str(held + by), (held, n, by, got)


def test_a_choice_whose_reader_read_number_the_count_does_not_reach_is_never_made(rig):
    """From the held 3 (OCR) to 1: the reader reads the 1 as 2 and the 0 as 1, so the number reads 1 at the low end.
    The presses counted from the 3 put the scale on 0, not 1: the screen is closed, no OK, no download."""
    cam = Scale()
    log = rig(cam, {3}, reader=lambda true: str(true + 1) if true in (0, 1) else str(true))
    with pytest.raises(S.Failed, match=r"the reader read '1' on frame 00005_scale\.png, but the presses counted put the "
                                       r"scale on '0': the readings disagree, no OK"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 1, 3)
    assert cam.presses == ["left"] * 3 and log.closes == [Path("00005_scale.png")]
    assert "enter" not in cam.presses and log.downloads == []


def test_a_choice_counts_from_where_the_scale_opens_when_the_reader_misreads_that_frame(rig):
    """Opened on 3 (the value chosen before) the reader reads it as 4, the target: the scale must open on the value
    chosen last, so the 4 is refused before any press, never OK on the 3 under the 4's label."""
    cam = Scale()
    log = rig(cam, set(), reader=one_off(3, +1))
    with pytest.raises(S.Failed, match=r"the scale opened on '4' \(frame 00001_scale\.png, read by the reader\), not on "
                                       r"'3', the value last chosen"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 4, 3)
    assert cam.presses == [] and log.downloads == []


@pytest.mark.parametrize("start", range(5))
def test_a_choice_with_a_reader_one_off_fails_or_lands_on_its_number(rig, start):
    """Whatever OCR reads, wherever the reader is one off: a choice that is made is made on the number asked for."""
    for target in range(5):
        for at in range(5):
            for by in (+1, -1):
                for k in range(6):
                    for ocr in itertools.combinations([n for n in range(5) if n != at], k):
                        cam = Scale(held=start)
                        log = rig(cam, set(ocr), reader=one_off(at, by))
                        try:
                            got = S.choose(cam, log.link, None, None, None, PATH, VALS, target, start)
                        except S.Failed:
                            assert "enter" not in cam.presses and log.downloads == []
                            continue
                        chosen = next(p for p in cam.truth if p.name == got["chosen_frame"])
                        assert cam.truth[chosen] == target, (start, target, at, by, ocr)


# ---------------------------------------------------------------- the report counts a reader-only line as one reader

def test_a_line_the_reader_alone_read_is_one_reader_in_the_report(monkeypatch):
    """A scale line whose number the reader alone read on the frame chosen holds that one answer as label, shown and
    vlm: kit/pass2_report.py's name_of credits it to the vision model alone, never to two readers; read by OCR, the
    same line with the reader's agreeing answer is two readers, as before."""
    import pass2_report as R
    from writer.proofs import reader_source
    monkeypatch.setattr(R, "ROW_NAMES", set())
    line = {"path": PATH, "kind": "list", "index": 3, "label": "6", "shown": "6", "vlm": "6", "read_by": "reader",
            "applied": True, "scale": True}
    assert R.name_of(line) == ("6", "vision model", None)
    assert reader_source(R.name_of(line)[1]) == "vision model"
    assert R.name_of({**line, "vlm": "Fast"}) == ("6", "vision model", None)
    assert R.name_of({**line, "read_by": "ocr"}) == ("6", "two readers", None)
    assert R.name_of({k: v for k, v in line.items() if k != "read_by"}) == ("6", "two readers", None)


@pytest.mark.parametrize("vlm, src", [("6", "two readers"), ("+6", "two readers"), (" 6 ", "two readers"),
                                      ("5", "one reader (ocr)"), ("-6", "one reader (ocr)"), ("Fast", "one reader (ocr)"),
                                      ("", "one reader (ocr)"), (None, "one reader (ocr)")])
def test_a_scale_line_ocr_read_is_two_readers_only_when_the_vision_model_read_the_same_number(monkeypatch, vlm, src):
    """An OCR-read scale line's label and shown are one OCR reading, so its readers are OCR and the vision model: two
    only when the vision model's reading is the same number, cleaned and keyed as scale_run compares numbers; its word
    for a scale's end ("Fast") or the next number leaves OCR alone, "one reader (ocr)" (the writer's "one reader"). A
    line that is no scale line keeps the old rule (the map and the bar's OCR alike are two readers)."""
    import pass2_report as R
    from writer.proofs import reader_source
    monkeypatch.setattr(R, "ROW_NAMES", set())
    line = {"path": PATH, "kind": "list", "index": 3, "label": "6", "shown": "6", "vlm": vlm, "read_by": "ocr",
            "applied": True, "scale": True}
    assert R.name_of(line) == ("6", src, None)
    assert R.name_of({k: v for k, v in line.items() if k != "read_by"}) == ("6", src, None), "an older line, untagged"
    assert reader_source(src) == ("two readers" if src == "two readers" else "one reader")
    if vlm in ("5", "Fast"):
        assert R.name_of({k: v for k, v in line.items() if k != "scale"})[1] == "two readers"


def test_the_prover_and_the_report_read_a_scale_number_alike():
    """scale_run walks a scale with the report's own cleaning and key (one source): the same function objects."""
    import pass2_report as R
    assert S.clean is R.scale_clean and S.key is R.scale_key


# ---------------------------------------------------------------- main, on a made-up slider

class Slider:
    """A made-up scale 0 .. top with a true setting: the row opens on the setting, Left and Right move the slider on the
    scale screen and stop at its ends, a close (MENU) leaves the setting as it was, OK applies the slider's place, a
    download holds the setting; every press, open and close is a new frame, truth[frame] the place it shows (None off
    the scale screen). A panel (panel True) opens on its setup row (the pixel reader's "submenu"), whose option is
    `setup`, and Down goes to the slider (unless down_works is False); a key pressed on the setup row is noted in
    setup_touched and does nothing else."""

    def __init__(self, held, top=4, drop=None, slow=None, panel=False, setup="Manual", down_works=True, reverts=()):
        self.setting, self.pos, self.top, self.screen = held, held, top, "shooting"
        self.n, self.truth, self.presses, self.oks, self.dropped = 0, {}, [], [], []
        self.drop = drop or (lambda cam, key: False)         # drop(slider, key): the camera ignores this press
        self.slow = slow or (lambda cam, key: False)         # slow(slider, key): its first frame shows the place before
        self.panel, self.setup, self.down_works, self.lit, self.lit_at, self.setup_touched = \
            panel, setup, down_works, None, {}, []
        self.state, self.reverts = 0, set(reverts)       # a second record, which a --set changes (setter)
        self.stale = None
        self.shoot()

    def shoot(self):
        self.n += 1
        p = Path(f"{self.n:05d}_slider.png")
        self.truth[p] = (self.pos if self.stale is None else self.stale) if self.screen == "scale" else None
        self.lit_at[p] = self.lit if self.screen == "scale" else None
        self.stale = None
        self.frame = SimpleNamespace(path=p)

    def read(self):
        on_setup = self.screen == "scale" and self.lit == "setup"
        return SimpleNamespace(kind="submenu" if on_setup else "unknown" if self.screen == "scale" else self.screen)

    def press(self, key):
        self.presses.append(key)
        if key == "right" and self.screen == "menu":          # Right on the row: its scale opens on the setting
            self.screen, self.pos, self.lit = "scale", self.setting, ("setup" if self.panel else None)
            self.shoot()
            return
        if self.screen == "scale" and self.lit == "setup":
            if key == "down" and self.down_works:
                self.lit = "slider"
            elif key != "down":
                self.setup_touched.append(key)
            self.shoot()
            return
        if key in ("left", "right") and self.screen == "scale" and self.drop(self, key):
            self.shoot()
            self.dropped.append(self.frame.path)              # a new frame, the slider where it was
            return
        if self.screen == "scale":
            if key in ("left", "right") and self.slow(self, key):
                self.stale = self.pos
            if key == "left":
                self.pos = max(0, self.pos - 1)
            elif key == "right":
                self.pos = min(self.top, self.pos + 1)
            elif key == "enter":
                self.oks.append(self.pos)
                self.setting, self.screen, self.lit = self.pos, "menu", None
                if self.pos in self.reverts:
                    self.state = 0                  # this value's OK puts the set record back as it was
        self.shoot()

    def refresh(self, tag):
        self.shoot()


@pytest.fixture
def drive(monkeypatch, tmp_path):
    """drive(held, ocr_reads, reader, top, cam, footer, sees, title): scale_run.main() on a Slider (cam, else a plain
    one), its proofs and attempts in a run folder of its own (the real proofs file and finish_attempt). OCR reads the
    frames whose true place is in ocr_reads (or where ocr_reads(frame path, place) says so); the reader answers
    reader(place, i) on its i-th question. With footer, the real open_row runs (the menu's way to the row made up, its
    Right opening the scale): OCR reads `title` at the top of every scale frame and footer(frame path, place) at its
    bottom, and the reader's footer answer is sees(frame path, place). Returns the slider, the lines, those
    pass2_report counts (unfinished), the attempts finished, what main printed and the frames the reader was asked
    about the footer. A panel slider (cam.panel), or as_panel (the row given as --panel-row), runs the real open_row
    too, OCR reading the panel's setup option and its number where a panel draws them (shown(place): the number's
    text); args go on the command line after the row (--set, --allow, --context); index is the definition's settings
    by key a --set is verified against (none: not verified in the file). A panel run whose args set no row inside the
    panel gets its setup row's --set (PATH[0] > Setup Row=Manual: a --panel-row run must be given it, panel_set_refused)
    with a setup that changes nothing, unless auto_set is False."""
    import contextlib
    import io
    import time as real_time

    import pass2_report as R
    from camkit import jsonl

    def run(held, ocr_reads, reader, top=4, cam=None, footer=None, sees=None, title=PATH[0], shown=str, as_panel=None,
            args=(), index=None, auto_set=True):
        cam = cam or Slider(held, top)
        as_panel = cam.panel if as_panel is None else as_panel
        if as_panel and auto_set and not any(str(x).startswith(f"{PATH[0]} > ") for x in args):
            args = ["--set", f"{PATH[0]} > Setup Row={PANEL_WORD}", *args]
            monkeypatch.setattr(S, "setup", lambda c, link, hdmi, cycle, model, start, sets, panels=frozenset(): start)
        real_open = footer is not None or cam.panel or as_panel
        footer = footer or (lambda p, place: CANCEL_OK)
        sees = sees or (lambda p, place: None)
        reads = ocr_reads if callable(ocr_reads) else (lambda p, place: place in ocr_reads)
        asked, dats, footer_asked = [], {}, []
        start = Path("start.DAT")
        dats[start] = {SCALE_KEY: held, STATE_KEY: cam.state}
        folder = tmp_path / f"run{held}_{len(list(tmp_path.iterdir()))}"
        folder.mkdir()
        monkeypatch.setattr(S, "_said", {})
        monkeypatch.setattr(S, "_by_reader", set())

        def read(paths, eng=None):
            out = {}
            for p in paths:
                place = cam.truth.get(p)
                if place is None:
                    out[p] = []
                    continue
                number = Line(text=shown(place), conf=1.0, x=297, y=153, w=50, h=31) if cam.panel else digit(shown(place))
                out[p] = [number] if reads(p, place) else []
                if real_open:
                    out[p].append(Line(text=title, conf=1.0, x=210, y=12, w=210, h=26))
                    foot = "? MENU D" if cam.lit_at.get(p) == "setup" else footer(p, place)
                    if foot:
                        out[p].append(Line(text=foot, conf=1.0, x=380, y=440, w=230, h=22))
                    if cam.panel:
                        out[p].append(Line(text=cam.setup, conf=1.0, x=530, y=83, w=86, h=30))
            return out

        def option_answer(c):
            asked.append(c.frame.path)
            return answer(reader(cam.truth[c.frame.path], len(asked) - 1))

        def open_row(c, cycle, model, path, panel=False):
            cam.screen, cam.pos = "scale", cam.setting
            cam.shoot()
            if not S.value(c):
                raise S.Failed(f"{path[-1]}: no number read on the scale on frame {cam.frame.path.name}")

        def close_screen(c, link):
            if cam.screen == "scale":
                cam.pos = cam.setting                # MENU: the slider's place not applied
            cam.screen = "shooting"
            cam.shoot()

        def to_shooting(link, hdmi, why):
            cam.screen = "shooting"
            cam.shoot()

        def download(name):
            p = Path(f"{len(dats):05d}_{name}.DAT")
            dats[p] = {SCALE_KEY: cam.setting, STATE_KEY: cam.state}
            return p

        @contextlib.contextmanager
        def session(run, hdmi, may_open=()):
            ps = SimpleNamespace(cam=cam, link=SimpleNamespace(download=download), start=start)
            try:
                yield ps
            except Exception as e:                   # as runner.prover_session: said, then the restore
                print(f"stopped: {type(e).__name__}: {e}", flush=True)
            finally:
                # the session's restore: the file the session downloaded first goes back, whatever the body did
                cam.restored_from = ps.start
                cam.setting, cam.state = dats[ps.start][SCALE_KEY], dats[ps.start][STATE_KEY]

        def to_menu(c):
            cam.screen = "menu"
            cam.shoot()

        def reader_footer(c):
            footer_asked.append(c.frame.path)
            return sees(c.frame.path, cam.truth[c.frame.path])

        monkeypatch.setattr(S, "_number_box", S.VALUE)
        if not real_open:
            monkeypatch.setattr(S, "open_row", open_row)
        else:
            for name, value in (("menu_from_shooting", to_menu), ("scan_position", lambda c, cycle: 0),
                                ("go_to", lambda c, cycle, model, j, label: True),
                                ("enter_any", lambda c, path, i: None), ("reader_footer", reader_footer)):
                monkeypatch.setattr(S, name, value)
        monkeypatch.setattr(S, "definition_index", lambda: index or {})
        monkeypatch.setattr(S, "held_value", lambda cs, k: cs.get(k))
        for name, value in (("option_answer", option_answer), ("close_screen", close_screen),
                            ("to_shooting", to_shooting), ("prover_session", session),
                            ("load_scan", lambda scan: (None, None)), ("Run", lambda name: SimpleNamespace(dir=folder)),
                            ("eyes_from_config", lambda r: None),
                            ("time", SimpleNamespace(sleep=lambda s: None, time_ns=real_time.time_ns)),
                            ("camset", SimpleNamespace(read=lambda p: dats[p], diff=lambda a, b: [
                                SimpleNamespace(key=k, before=a[k], after=b[k]) for k in sorted(a) if a[k] != b[k]])),
                            ("changes_of", lambda ch: [{"key": c.key, "before": c.before, "after": c.after} for c in ch])):
            monkeypatch.setattr(S, name, value)
        monkeypatch.setattr(S.ocr, "read", read)
        monkeypatch.setattr(sys, "argv", ["scale_run.py", "--panel-row" if as_panel else "--row", PATH[0], *args])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            S.main()
        lines = jsonl.read(folder / "proofs.jsonl")
        skip = R.unfinished(lines, R.attempts_done(folder), {})
        return SimpleNamespace(cam=cam, lines=lines, counted=[ln for i, ln in enumerate(lines) if i not in skip],
                               attempts=jsonl.read(folder / "attempts.jsonl"), out=out.getvalue(), asked=asked,
                               shown=[cam.truth[Path(ln["chosen_frame"])] for ln in lines], footer_asked=footer_asked,
                               dats={q.name: v for q, v in dats.items()})
    return run


SCALE_KEY, STATE_KEY = "global:0x0abc", "global:0x0def"     # the scale's record; a record a --set changes


def order(held, top=4):
    """The values main chooses, by index: every one but the held, then the held (the put-back)."""
    return [i for i in range(top + 1) if i != held] + [held]


@pytest.mark.parametrize("held", range(5))
def test_main_with_the_reader_right_lands_every_ok_and_finishes_the_row(drive, held):
    """With the reader right, whatever OCR reads: every OK lands on its value, every line's label is the number on the
    frame it was chosen on, the put-back ends on the held value, and the row's attempt is finished, so every line
    counts (pass2_report.unfinished)."""
    for k in range(6):
        for ocr in itertools.combinations(range(5), k):
            got = drive(held, set(ocr), lambda place, i: str(place))
            assert "stopped" not in got.out, (held, ocr, got.out)
            assert got.cam.oks == order(held), (held, ocr)          # the held value last: the put-back
            assert [ln["label"] for ln in got.lines] == [str(i) for i in order(held)]
            assert got.shown == order(held), "every label the number on its frame"
            assert [ln["changes"] == [] for ln in got.lines] == [i == held for i in order(held)]
            (done,) = got.attempts
            assert done["complete"] and done["row"] == PATH[0] and {ln["attempt"] for ln in got.lines} == {done["attempt"]}
            assert got.counted == got.lines
            assert all(ln["read_by"] == ("ocr" if s in ocr else "reader") for ln, s in zip(got.lines, got.shown,
                                                                                          strict=True))


def test_main_three_misreads_stop_the_row_and_none_of_its_lines_counts(drive):
    """The held 1 read as 0 where the look opens and again where the first choice opens, then a 2 read as 1 once: the
    first choice counts its way onto the 2 and takes it as the 1 (no press can tell), but the next choice opens on the
    2 where the value last chosen was the 1, and stops the row. The wrong line was written; the row's attempt never
    finished, so none of its lines counts (pass2_report.unfinished), and no attempt is recorded."""
    seen = {"ones": 0, "twos": 0}

    def reader(place, i):
        if place == 1:
            seen["ones"] += 1
            if seen["ones"] in (1, 3):               # the look's first frame; the first choice's first frame
                return "0"
        if place == 2 and seen["ones"] >= 3 and not seen["twos"]:
            seen["twos"] += 1
            return "1"
        return str(place)
    got = drive(1, set(), reader)
    assert "Made-up Scale: ['0', '1', '2', '3', '4'], held '0'" in got.out
    assert ("Made-up Scale stopped: Failed: Made-up Scale: the scale opened on '2' (frame 00021_slider.png, read by the "
            "reader), not on '1', the value last chosen") in got.out
    assert [(ln["label"], ln["read_by"]) for ln in got.lines] == [("1", "reader")] and got.shown == [2]
    assert got.attempts == [] and got.counted == []


@pytest.mark.parametrize("held", range(5))
def test_main_a_wrong_start_and_one_more_misread_never_take_a_wrong_value(drive, held):
    """The held number misread by one where the look opens hands the first choice a wrong start; one more misread,
    one too high or one too low on any later answer, and OCR reading none, one or two of the places: no OK is taken
    on a value other than the one its line names (every line true to the screen)."""
    for d0 in (+1, -1):
        for ocr in ((), (3,), (0, 4), (2,)):
            if held in ocr:
                continue
            base = len(drive(held, set(ocr), lambda place, i: str(place)).asked)
            for n in range(1, base + 6):
                for d in (+1, -1):
                    got = drive(held, set(ocr), lambda place, i, n=n, d=d, d0=d0:
                                str(place + d0) if i == 0 else str(place + d) if i == n else str(place))
                    assert got.shown == [int(ln["label"]) for ln in got.lines], (held, d0, ocr, n, d)
                    assert len(got.cam.oks) == len(got.lines)


@pytest.mark.parametrize("held, by", [(0, +1), (1, -1)])
@pytest.mark.parametrize("ocr_later", [False, True])
def test_a_held_number_misread_where_the_scale_opens_stops_the_row_before_any_line(drive, held, by, ocr_later):
    """The case no press of the look can tell: held at the low end or next to it, misread by one on the frame the scale
    opens on and read right on a later frame of that place. The first choice must open on the held value as the look
    read it: read again by the reader (OCR having missed that place) or by OCR, its number is another, and the row
    stops before any OK or line."""
    first = []

    def ocr(path, place):
        first.append(path) if not first else None
        return ocr_later and path != first[0]          # OCR misses the look's first frame; else every frame, or none
    got = drive(held, ocr, lambda place, i: str(place + by) if i == 0 else str(place))
    assert f"held '{held + by}'" in got.out and "stopped" in got.out
    assert f"not on '{held + by}', the value last chosen" in got.out
    assert ("read by OCR" if ocr_later else "read by the reader") in got.out
    assert got.cam.oks == [] and got.lines == [] and got.attempts == []


def test_main_with_ocr_reading_every_number_presses_as_before_and_three_more(drive):
    """OCR reads every number: the presses are as they were before the reader was asked (Left to the low end and once
    more, Right to the high end and once more, then each value straight from the one before, OK), and three more since
    every end is confirmed (2026-11-10): one more Left at the low end, one more Right at the high end and Left from it.
    The reader is asked only on the frames chosen (the second reading a line keeps), and the lines carry read_by "ocr"
    and the row's attempt, finished."""
    held, top = 2, 5
    got = drive(held, set(range(top + 1)), lambda place, i: str(place), top=top)
    want, at = ["left"] * (held + 1) + ["left"] + ["right"] * (top + 1) + ["right", "left"], held
    for i in order(held, top):
        want += ["right" if i > at else "left"] * abs(i - at) + ["enter"]
        at = i
    assert got.cam.presses == want
    assert len(got.asked) == top + 1 and all(Path(ln["chosen_frame"]) in got.asked for ln in got.lines)
    assert {ln["read_by"] for ln in got.lines} == {"ocr"} and got.counted == got.lines and len(got.attempts) == 1
    assert set(got.lines[0]) == {"path", "kind", "index", "label", "shown", "chosen_frame", "row_frame", "vlm", "dat",
                                 "base", "applied", "scale", "changes", "read_by", "attempt"}


def test_choose_stops_where_ocr_reads_another_number_than_the_count(rig):
    """A known start the camera is not on (handed 1, the slider on 2): OCR reads 2 where the scale opens, and the
    choice stops there, the screen closed, the frame and both numbers named, rather than taking OCR's number for the
    count's and going on."""
    cam = Scale(held=2)
    log = rig(cam, {2})
    with pytest.raises(S.Failed, match=r"the scale opened on '2' \(frame 00001_scale\.png, read by OCR\), not on '1', "
                                       r"the value last chosen: the last OK did not take, or the readings disagree; no OK"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 3, 1)
    assert cam.presses == [] and log.closes == [Path("00001_scale.png")] and log.downloads == []


def test_choose_presses_again_after_a_press_the_camera_drops_where_ocr_reads(rig):
    """A press the camera drops: OCR reads the same number before and after it, so the count does not move, the walk
    presses again, and the choice lands as it did before the count was kept."""
    cam = Scale(held=1)
    dropped = []
    real = cam.press

    def press(key):
        if key == "right" and not dropped:
            dropped.append(key)
            cam.presses.append(key)
            cam.shoot()                              # a new frame, the slider where it was
            return
        real(key)
    cam.press = press
    log = rig(cam, set(range(5)))
    got = S.choose(cam, log.link, None, None, None, PATH, VALS, 3, 1)
    assert cam.presses == ["right", "right", "right", "enter"] and got["read_by"] == "ocr"
    assert log.downloads == ["Made-up Scale-3"]


def test_choose_stops_after_a_press_the_camera_drops_where_only_the_reader_reads(rig):
    """The same dropped press where OCR reads nothing: the reader's same number may be a misread as much as a press
    that went nowhere, so the press is counted, and the count and the reader disagree before OK: the row stops, no
    value taken."""
    cam = Scale(held=1)
    dropped = []
    real = cam.press

    def press(key):
        if key == "right" and not dropped:
            dropped.append(key)
            cam.presses.append(key)
            cam.shoot()
            return
        real(key)
    cam.press = press
    log = rig(cam, set())
    with pytest.raises(S.Failed, match="the presses counted put the scale on"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 3, 1)
    assert "enter" not in cam.presses and log.downloads == []


# ---------------------------------------------------------------- a press dropped or late, a look of one value

def nth_arrow(m):
    """drop/slow(slider, key): true for the m-th Left or Right press made on the scale screen, counted from 0."""
    seen = []

    def hit(cam, key):
        seen.append(key)
        return len(seen) - 1 == m
    return hit


def test_a_dropped_first_right_press_never_finishes_a_row_on_a_short_scale(drive):
    """Held at the low end, OCR reading every number: the camera drops the first Right press, so OCR reads the 0 twice
    (and on a fresh frame). That once ended the look on one value and the row finished on it; now one more Right must
    read the 0 again, it reads 1, and the row stops with no line."""
    cam = Slider(0, drop=lambda c, key: key == "right" and not c.dropped)
    got = drive(0, set(range(5)), lambda place, i: str(place), cam=cam)
    assert len(cam.dropped) == 1 and "a press went unanswered, or the readings disagree" in got.out
    assert got.lines == [] and got.attempts == []


@pytest.mark.parametrize("held", range(5))
@pytest.mark.parametrize("ocr", [(), (0, 2, 4), (0, 1, 2, 3, 4)])
def test_any_one_press_dropped_or_late_leaves_the_whole_scale_or_no_finished_row(drive, held, ocr):
    """Any one Left or Right press dropped by the camera, or answered late (its first frame still showing the place
    before), wherever it falls in the row: the row finishes with the whole scale, every line true to its frame, or it
    stops and none of its lines counts. A late press is read again on a fresh frame and costs nothing."""
    base = drive(held, set(ocr), lambda place, i: str(place))
    arrows = sum(k in ("left", "right") for k in base.cam.presses)
    for m in range(arrows + 1):
        for fault in ("drop", "slow"):
            cam = Slider(held, **{fault: nth_arrow(m)})
            got = drive(held, set(ocr), lambda place, i: str(place), cam=cam)
            if got.attempts:
                assert got.shown == [int(ln["label"]) for ln in got.lines] == order(held), (held, ocr, m, fault)
            else:
                assert got.counted == [], (held, ocr, m, fault)
            if fault == "slow":
                assert got.attempts, (held, ocr, m, "a late press stopped the row")


def test_a_look_of_one_value_stops_the_row(drive):
    """The reader reads the same wrong number on every frame near the held value (0, 1 and 2 all read as 2; OCR
    reads nothing): each end is confirmed by its extra press and Left from the high end reads the same, so the look
    holds together on one value. A scale has two values at least: the row stops and nothing is written."""
    got = drive(2, set(), lambda place, i: "2" if place <= 2 else str(place))
    assert "the look read one value only, '2'" in got.out
    assert got.lines == [] and got.attempts == [] and got.cam.oks == []


def test_a_dropped_press_and_a_misread_at_the_top_never_finish_a_wrong_row(drive):
    """Choosing 3 from 2 on a scale 0 .. 4 (held 0): the Right press is dropped and the reader reads the unchanged
    frame as 3, so the count and the reading agree and OK lands on the 2 under the 3's label (no press can tell). The
    next choice must open on the 3 it was told was chosen; it opens on the 2, and the row stops: the wrong line was
    written, its attempt never finished, and none of the row's lines counts."""
    cam = Slider(0, drop=lambda c, key: key == "right" and len(c.oks) == 2 and not c.dropped)

    def reader(place, i):
        return "3" if cam.frame.path in cam.dropped else str(place)
    got = drive(0, set(), reader, cam=cam)
    assert [(ln["label"], s) for ln, s in zip(got.lines, got.shown, strict=True)] == [("1", 1), ("2", 2), ("3", 2)]
    assert "the scale opened on '2'" in got.out and "not on '3', the value last chosen" in got.out
    assert got.attempts == [] and got.counted == []


@pytest.mark.parametrize("held", range(5))
def test_a_dropped_press_read_as_the_number_it_should_have_reached_never_finishes_a_wrong_row(drive, held):
    """Any one Left or Right press dropped, and the reader reading its unchanged frame as the number the press should
    have reached (OCR reading nothing): no finished row holds a line whose label is not the value truly chosen."""
    base = drive(held, set(), lambda place, i: str(place))
    arrows = sum(k in ("left", "right") for k in base.cam.presses)
    for m in range(arrows + 1):
        hit = nth_arrow(m)
        cam = Slider(held, drop=lambda c, key, hit=hit: hit(c, key) and (c.missed.append(key) or True))
        cam.missed = []

        def reader(place, i, cam=cam):
            if cam.frame.path in cam.dropped:
                return str(place + (1 if cam.missed[-1] == "right" else -1))
            return str(place)
        got = drive(held, set(), reader, cam=cam)
        if got.attempts:
            assert got.shown == [int(ln["label"]) for ln in got.lines] == order(held), (held, m)


def test_numbers_that_step_unevenly_stop_an_ocr_only_look(rig):
    """OCR reads every number but always reads the 4 as 6: 0, 1, 2, 3, 6 step unevenly, and the look stops, though
    the reader never read a number (every scale the kit has met counts in whole numbers, evenly)."""
    cam = Scale(held=2)
    log = rig(cam, set(range(5)), shown=lambda true: "6" if true == 4 else str(true))
    with pytest.raises(S.Failed, match=r"the look read \['0', '1', '2', '3', '6'\], whole numbers stepping unevenly"):
        S.ends(cam, log.link, None, None, PATH)
    assert log.asked == [] and len(log.closes) == 1


def test_the_key_of_no_reading_is_empty():
    import pass2_report as R
    assert R.scale_key(None) == R.scale_clean(None) == "" and S.key("") == ""


# ---------------------------------------------------------------- the scale's OK, where OCR drops it

@pytest.mark.parametrize("foot, ok", [("MENU Cancel • ОK", True), ("MENU Cancel •Ок", True), ("MENU Cancel•OK", True),
                                      ("MENU Cancel •OK", True), ("MENU Cancel 0K", True), ("ok", True),
                                      ("MENU Cancel", False), ("MENU Back", False), ("Look", False),
                                      ("10K", False), ("", False), (None, False)])
def test_the_footers_ok_is_read_through_the_look_alikes(foot, ok):
    """OCR's readings of the scale's "MENU Cancel ●OK": Cyrillic О and К, the small к too ("Ок"), and a 0 for the O,
    count; OK inside a word or a number does not."""
    from camkit import match
    assert match.offers_ok(foot) is ok


CANCEL_OK = "MENU Cancel • ОK"
READER_OK = {"title": PATH[0], "selected": "", "values": [], "footer": ["MENU Cancel", "OK"]}


def drops_ok_at(place):
    """OCR reads the footer as "MENU Cancel" alone on every frame showing `place` (as it did on one number's frames,
    2026-11-10), and with its OK on the others."""
    return lambda path, shown: "MENU Cancel" if shown == place else CANCEL_OK


def test_an_ok_ocr_drops_on_the_frame_and_a_fresh_one_is_taken_from_the_reader(drive):
    """Held 0: the choice of 4 opens on the 3 chosen before, where OCR reads "MENU Cancel" alone, on the frame and on
    a fresh one. The reader, asked once about the fresh frame, reads the OK: the scale is open, and the row finishes,
    every line true to its frame. No other opening frame asks the reader."""
    got = drive(0, set(range(5)), lambda place, i: str(place), footer=drops_ok_at(3), sees=lambda p, place: READER_OK)
    assert "stopped" not in got.out and len(got.attempts) == 1 and got.counted == got.lines
    assert got.shown == [int(ln["label"]) for ln in got.lines] == order(0)
    (frame,) = got.footer_asked
    assert got.cam.truth[frame] == 3 and got.cam.truth[Path(f"{int(frame.name[:5]) - 1:05d}_slider.png")] == 3


@pytest.mark.parametrize("answer, said", [({"footer": ["MENU Cancel"]}, "read none"),
                                          ({"title": PATH[0], "footer": []}, "read none"),
                                          (None, "gave no answer it could use"),
                                          ("OK", "gave no answer it could use"),
                                          ({"title": PATH[0]}, "gave no answer it could use")])
def test_an_ok_neither_ocr_nor_the_reader_reads_stops_the_row(drive, answer, said):
    """The same frames with a reader that reads no OK, fails, or answers anything else: the scale does not count as
    open, the row stops there with the screen closed and nothing more chosen, the message names who was asked, and
    the row's attempt never finishes, so none of its lines counts."""
    got = drive(0, set(range(5)), lambda place, i: str(place), footer=drops_ok_at(3), sees=lambda p, place: answer)
    assert "did not open its scale" in got.out
    assert f"and the reader, asked about {got.footer_asked[0].name}, {said}" in got.out
    assert got.cam.oks == [1, 2, 3] and got.cam.screen == "shooting"
    assert got.attempts == [] and got.counted == [] and len(got.footer_asked) == 1


def test_an_ok_read_with_a_small_cyrillic_k_needs_no_reader(drive):
    """OCR reads every footer as "MENU Cancel •Ок": the OK is taken as it is, the reader never asked about it."""
    got = drive(2, set(range(5)), lambda place, i: str(place), footer=lambda p, place: "MENU Cancel •Ок",
                sees=lambda p, place: pytest.fail("the reader asked about a footer OCR read an OK in"))
    assert len(got.attempts) == 1 and got.counted == got.lines and got.footer_asked == []


def test_a_title_not_the_rows_stops_before_any_fresh_frame_or_reader(drive):
    """A screen whose title is not the row's never asks the reader about its footer, whatever the footer reads."""
    got = drive(2, set(range(5)), lambda place, i: str(place), footer=lambda p, place: "MENU Cancel",
                sees=lambda p, place: READER_OK, title="Another Row")
    assert "did not open its scale (title 'Another Row', footer 'MENU Cancel')" in got.out
    assert got.footer_asked == [] and got.lines == [] and got.attempts == []


# ---------------------------------------------------------------- the reader's number in "value"

@pytest.mark.parametrize("said, got", [
    ({"selected": "", "value": "4"}, ("4", "4")),
    ({"selected": PATH[0], "value": "4"}, ("4", "4")),
    ({"selected": "Fast", "value": "−1"}, ("−1", "-1")),
    ({"selected": "3", "value": ""}, ("3", "3")),
    ({"selected": "3", "value": "3"}, ("3", "3")),
    ({"selected": "+2", "value": "2"}, ("+2", "+2")),
    ({"selected": "3", "value": "4"}, ("selected 3; value 4", "")),
    ({"selected": "Vol 6", "value": "6"}, ("Vol 6", "")),
    ({"selected": "6/15", "value": ""}, ("6/15", "")),
    ({"selected": "", "value": "6/15"}, ("6/15", "")),
    ({"selected": "Fast", "value": ""}, ("Fast", "")),
    ({"selected": "", "value": ""}, ("", "")),
    ({"selected": 0, "value": None}, ("0", "0")),               # a bare number, a zero too, is a number
    ({"selected": None, "value": 0}, ("0", "0")),
    ({"selected": False, "value": 4}, ("4", "4")),
    ({}, ("", "")), (None, ("", "")), ("3", ("", "")), (["3"], ("", ""))])
def test_the_readers_number_is_its_selected_else_its_value(said, got):
    """reader_said: (what a proof keeps as the reader's reading, the number). "selected" when it holds the number;
    "value" when "selected" holds no digit (a word, the title, nothing); two numbers that differ are no reading, both
    kept; digits in "selected" that are no one number are none; an answer that is no object is nothing."""
    assert S.reader_said(said) == got


def test_a_number_in_value_with_selected_empty_is_read_where_ocr_reads_none(rig):
    """The stand-in reader's answer on a scale frame OCR read no number on (2026-11-10): the number in "value",
    "selected" empty. The frame reads that number, by the reader; a word in "selected" changes nothing."""
    cam = Scale()
    rig(cam, set(), reader=lambda true: {"title": PATH[0], "selected": "", "value": str(true)})
    assert S.value(cam) == "3" and S.read_by(cam) == "reader"
    cam = Scale()
    rig(cam, set(), reader=lambda true: {"title": PATH[0], "selected": PATH[0], "value": str(true)})
    assert S.value(cam) == "3" and S.read_by(cam) == "reader"


def test_main_reads_a_scale_whose_numbers_the_reader_gives_in_value(drive):
    """OCR reads no number and the reader gives every one in "value", "selected" empty: the row goes on and finishes,
    every line true to its frame, read by the reader, its "vlm" the number as the reader wrote it in "value", and the
    report counts each as one reader (the vision model); an OCR-read line the reader backs through "value" is two."""
    import pass2_report as R
    got = drive(1, set(), lambda place, i: {"title": PATH[0], "selected": "", "value": str(place)})
    assert "stopped" not in got.out and len(got.attempts) == 1 and got.counted == got.lines
    assert got.shown == [int(ln["label"]) for ln in got.lines] == order(1)
    assert all(ln["read_by"] == "reader" and ln["vlm"] == ln["label"] for ln in got.lines)
    assert {R.name_of(ln)[1] for ln in got.lines} == {"vision model"}
    got = drive(1, set(range(5)), lambda place, i: {"title": PATH[0], "selected": "", "value": str(place)})
    assert all(ln["read_by"] == "ocr" and ln["vlm"] == ln["label"] for ln in got.lines)
    assert {R.name_of(ln)[1] for ln in got.lines} == {"two readers"}


def test_main_stops_where_the_reader_gives_two_numbers_that_differ(drive):
    """On the frames showing 2, OCR reads nothing and the reader says 2 in "selected" and 3 in "value": no reading, so
    the row stops at the first such frame, naming it, and none of its lines counts."""
    got = drive(0, {0, 1, 3, 4}, lambda place, i: {"title": PATH[0], "selected": str(place), "value": str(place + 1)}
                if place == 2 else str(place))
    assert "no number read on the scale on frame" in got.out and "by OCR or the reader" in got.out
    assert got.attempts == [] and got.counted == []


# ---------------------------------------------------------------- a panel's slider (--panel-row)

SIGNED = {0: "-2", 1: "-1", 2: "‡0", 3: "+1", 4: "+2"}         # OCR's spelling of a scale around zero (± read as ‡)
SIGNED_LABELS = ["-2", "-1", "±0", "+1", "+2"]                  # the camera's labels, the definition's own


def on_slider(place, i):
    """The reader on a panel whose slider is lit: the setup row's option in "selected", the number in "value"."""
    return {"title": PATH[0], "selected": PANEL_WORD, "value": SIGNED[place].replace("‡", "±")}


PANEL_WORD = "Manual"


@pytest.mark.parametrize("held", range(5))
def test_a_panel_opens_on_its_setup_row_goes_down_to_the_slider_and_proves_every_value(drive, held):
    """--panel-row: the panel opens on its setup row (reading Manual), Down goes to the slider, and the row is proved as
    any scale: every value chosen, the held one last, each line labelled as the camera writes the scale around zero,
    whoever read it; nothing pressed on the setup row but Down."""
    cam = Slider(held, panel=True)
    got = drive(held, {0, 2, 4}, on_slider, cam=cam, shown=lambda place: SIGNED[place])
    assert "stopped" not in got.out and len(got.attempts) == 1 and got.counted == got.lines
    assert got.shown == order(held) and cam.oks == order(held)
    assert [ln["label"] for ln in got.lines] == [SIGNED_LABELS[i] for i in order(held)]
    assert {ln["label"]: ln["read_by"] for ln in got.lines}["-1"] == "reader"
    assert cam.setup_touched == []
    downs = [i for i, k in enumerate(cam.presses) if k == "down"]
    assert len(downs) == 1 + len(order(held)), "one Down each time the row opened: the look and every choice"
    assert all(cam.presses[i - 1] == "right" for i in downs), "Down only right after the row opened"


def test_a_panel_whose_setup_row_does_not_read_manual_stops_before_any_press_but_right(drive):
    """The setup row reads another option (made up here): the slider is not there, and the run never changes the
    option, so the row stops after the opening Right alone, its message naming no option but Manual."""
    cam = Slider(2, panel=True, setup="Option Z")
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place])
    assert "its panel's setup row does not read Manual" in got.out and "Option Z" not in got.out
    assert cam.presses == ["right"] and got.lines == [] and got.attempts == []


def test_a_panel_whose_down_brings_no_ok_stops_before_any_choice(drive):
    """Down leaves the cursor on the setup row: no OK in the footer, on a fresh frame either, and the reader reads none:
    the row stops with nothing but Right and Down pressed."""
    cam = Slider(2, panel=True, down_works=False)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place],
                sees=lambda p, place: {"footer": ["MENU"]})
    assert "did not open its scale" in got.out and "the reader, asked about" in got.out
    assert cam.presses == ["right", "down"] and cam.setup_touched == [] and got.lines == []


def test_a_plain_scale_given_as_a_panel_stops_before_any_choice(drive):
    cam = Slider(2)
    got = drive(2, set(range(5)), lambda place, i: str(place), cam=cam, as_panel=True)
    assert "does not read Manual" in got.out and "or this is no panel" in got.out
    assert cam.presses == ["right"] and got.lines == [] and got.attempts == []


def test_a_panel_given_as_a_plain_row_stops_before_any_choice(drive):
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], as_panel=False)
    assert "opened a panel or a submenu, not a scale" in got.out and "--panel-row" in got.out
    assert cam.presses == ["right"] and cam.setup_touched == [] and got.lines == []


@pytest.mark.parametrize("zero", ["‡0", "+0", "0", "+-0", "±0", "-0", "−0"])
def test_zero_is_labelled_plus_minus_however_ocr_spelled_it(drive, zero):
    cam = Slider(1, panel=True)
    got = drive(1, set(range(5)), on_slider, cam=cam, shown=lambda place: zero if place == 2 else SIGNED[place])
    assert len(got.attempts) == 1 and [ln["label"] for ln in got.lines] == [SIGNED_LABELS[i] for i in order(1)]
    assert {ln["label"]: ln["read_by"] for ln in got.lines}["±0"] == "ocr"


@pytest.mark.parametrize("said", ["0", "±0", "+0"])
def test_zero_the_reader_reads_is_labelled_plus_minus(drive, said):
    """OCR reads no number at zero; the reader says "0", "±0" or "+0": the line is "±0", read by the reader, and the
    report counts it as one reader (the vision model)."""
    import pass2_report as R
    cam = Slider(3, panel=True)

    def reader(place, i):
        return {"title": PATH[0], "selected": PANEL_WORD, "value": said if place == 2 else SIGNED[place]}
    got = drive(3, {0, 1, 3, 4}, reader, cam=cam, shown=lambda place: SIGNED[place])
    line = next(ln for ln in got.lines if ln["label"] == "±0")
    assert len(got.attempts) == 1 and line["read_by"] == "reader" and R.name_of(line)[1] == "vision model"


def test_a_reader_that_leaves_out_the_plus_still_gives_signed_labels(drive):
    """OCR reads nothing; the reader writes +1 and +2 without their sign ("1", "2"): by the key they are +1 and +2, and
    the lines carry the camera's labels."""
    cam = Slider(0, panel=True)

    def reader(place, i):
        return {"title": PATH[0], "selected": PANEL_WORD, "value": SIGNED[place].replace("‡", "±").lstrip("+")}
    got = drive(0, set(), reader, cam=cam, shown=lambda place: SIGNED[place])
    assert len(got.attempts) == 1 and [ln["label"] for ln in got.lines] == [SIGNED_LABELS[i] for i in order(0)]


def test_a_reader_that_leaves_out_a_minus_is_never_taken_for_a_plus(drive):
    """The reader writes -1 as "1" where OCR reads nothing: the look reads 1 twice (for -1 and +1) and stops; no line,
    no sign guessed."""
    cam = Slider(4, panel=True)

    def reader(place, i):
        return {"title": PATH[0], "selected": PANEL_WORD, "value": "1" if place == 1 else SIGNED[place].replace("‡", "±")}
    got = drive(4, {0, 2, 4}, reader, cam=cam, shown=lambda place: SIGNED[place])
    assert "stopped" in got.out and got.lines == [] and got.attempts == []


def test_a_panel_read_through_the_cameras_own_display_image(drive):
    """Over the camera's own display image (the "osd" eyes) the footer reads "›OK" where HDMI gives "• OK", and the
    numbers are read as over HDMI: the row is proved the same."""
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place],
                footer=lambda p, place: "MENU D ›OK")
    assert len(got.attempts) == 1 and [ln["label"] for ln in got.lines] == [SIGNED_LABELS[i] for i in order(2)]
    assert got.footer_asked == []


def test_the_labels_of_a_scale_with_no_negative_number_stay_as_read():
    assert S.labels_of(["0", "1", "2", "3"]) == ["0", "1", "2", "3"]
    assert S.labels_of(["-2", "-1", "0", "1", "2"]) == SIGNED_LABELS
    assert S.labels_of(["-2", "-1", "+0", "+1", "+2"]) == SIGNED_LABELS


# ---------------------------------------------------------------- --set: a state put on before the rows

@pytest.fixture
def setter(monkeypatch):
    """The menu steps of --set made up: mode_switch.open_menu does nothing, and set_row says what it chooses (as the
    real one: the option asked for) and fails for a row named in `fails`, its message naming the option the list was
    on, as the real one does (afreg_run.set_setup_row takes that out). Returns the calls."""
    import afreg_run
    import mode_switch
    calls, fails, lost = [], set(), set()

    def set_row(cam, cycle, model, path, option, say):
        calls.append((" > ".join(path), option))
        if " > ".join(path) in fails:
            raise S.Failed(f"{' > '.join(path)!r}: {option!r} did not come round in its list (on 'Option B')")
        say(f"{' > '.join(path)}: choosing {option!r}")
        if " > ".join(path) not in lost:
            cam.state = 1                            # the set row's record now holds the option asked for
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "set_row", set_row)
    monkeypatch.setattr(afreg_run, "set_setup_row", afreg_run.set_setup_row)
    return SimpleNamespace(calls=calls, fails=fails, lost=lost)


# the definition's word on the set rows of these tests: Made-up Panel > Setup Row (and the scale's panel's own, Made-up
# Scale > Setup Row: a --panel-row run must set it) writes STATE_KEY, Manual 1; its menu row names the scale's panel
SET_INDEX = {STATE_KEY: {"key": STATE_KEY, "name": "Setup Row", "values": [[0, "Option Z"], [1, "Manual"]],
                         "row": [PATH[0], "Setup Row"],
                         "proved": {"menu": ["Made-up Panel > Setup Row [by hand]", f"{PATH[0]} > Setup Row [by hand]"]}}}
SETUP = f"{PATH[0]} > Setup Row"            # the --panel-row's own setup row, as the set tests through main() set it


def test_set_puts_each_row_on_its_option_in_order_and_the_proofs_name_the_state(drive, setter):
    """--set twice: each row set in the order given, after the start download and before the row; the proofs' context
    names each, before --context's words; the option each row held is printed nowhere."""
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], index=SET_INDEX,
                args=["--set", "Made-up Select=Option A", "--set", f"{SETUP}=Manual",
                      "--context", "made up"])
    assert setter.calls == [("Made-up Select", "Option A"), (SETUP, "Manual")]
    assert "Made-up Select = Option A: not verified in the file" in got.out
    assert f"{SETUP} = Manual: not verified" not in got.out
    assert len(got.attempts) == 1 and {ln["context"] for ln in got.lines} == {
        f"Made-up Select = Option A, {SETUP} = Manual, made up"}
    assert "choosing 'Option A'" in got.out and "Option B" not in got.out
    assert got.out.index("set through the menu") < got.out.index(f"{PATH[0]}: [")
    assert all(ln["base"].endswith("after-set.DAT") for ln in got.lines), "choices compared with the set state"


def test_a_set_that_fails_stops_the_run_before_any_row_and_says_no_option_held(drive, setter):
    setter.fails.add("Made-up Select")
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place],
                args=["--set", "Made-up Select=Option A", "--set", f"{SETUP}=Manual"])
    assert "stopped: Failed:" in got.out and "did not come round in its list" in got.out
    assert "Option B" not in got.out, "the option the list was on is the owner's"
    assert setter.calls == [("Made-up Select", "Option A")] and cam.presses == [] and got.lines == []


@pytest.mark.parametrize("item, allowed, why", [
    ("Made-up Volume=3", [], "never-open"),
    ("NTSC/PAL Selector=Option A", ["NTSC/PAL Selector"], "whatever is allowed"),
    ("Language=Option A", ["Language"], "whatever is allowed"),
    ("USB Connection=Option A", ["USB Connection"], "whatever is allowed"),
    ("Area/Date/Time Setting=Option A", [], "whatever is allowed"),
    ("No Option Here", [], "ROW=OPTION"), ("Row=", [], "ROW=OPTION")])
def test_a_set_row_is_judged_as_a_row_and_never_the_cameras_identity(item, allowed, why):
    with pytest.raises(SystemExit, match=why):
        S.parse_set(item, allowed)


def test_a_set_row_the_owner_allowed_is_taken():
    assert S.parse_set("Made-up Volume=3", ["Made-up Volume"]) == (["Made-up Volume"], "3")
    assert S.parse_set("Made-up Panel > Setup Row=Manual", []) == (["Made-up Panel", "Setup Row"], "Manual")


def test_a_refused_set_stops_before_anything_connects(drive, setter):
    cam = Slider(2)
    with pytest.raises(SystemExit, match="whatever is allowed"):
        drive(2, set(range(5)), lambda place, i: str(place), cam=cam,
              args=["--set", "NTSC/PAL Selector=Option A", "--allow", "NTSC/PAL Selector"])
    assert cam.presses == [] and setter.calls == []


def test_a_set_state_is_the_base_the_choices_and_the_put_back_are_compared_with(drive, setter):
    """The --set changes a record of its own (STATE_KEY). The choices are compared with the download after the set, so
    no line names that record; the put-back is checked against that file, and passes, though against the start file it
    would fail; and the session's end puts back the true start file, the set record with it."""
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place],
                args=["--set", f"{SETUP}=Manual"])
    assert len(got.attempts) == 1
    assert all({c["key"] for c in ln["changes"]} <= {SCALE_KEY} for ln in got.lines), "the set's record is no value's"
    last = got.dats[got.lines[-1]["dat"]]
    assert got.lines[-1]["changes"] == [] and last[STATE_KEY] != got.dats["start.DAT"][STATE_KEY], \
        "put back against the set state, which the start file does not hold"
    assert cam.restored_from == Path("start.DAT") and cam.state == got.dats["start.DAT"][STATE_KEY]


def test_a_choice_that_puts_the_set_record_back_shows_it_as_a_change(drive, setter):
    """A value whose OK also puts the set record back as the start file had it: its line names that record's change,
    and the put-back, which then finds it still changed, stops the row (none of its lines counts)."""
    cam = Slider(0, panel=True, reverts={3})
    got = drive(0, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place],
                args=["--set", f"{SETUP}=Manual"])
    line = next(ln for ln in got.lines if ln["label"] == "+1")
    assert {"key": STATE_KEY, "before": 1, "after": 0} in line["changes"]
    assert "still differ from the file the row started from" in got.out and got.attempts == []


class PanelMenu:
    """A made-up camera for the real mode_switch.set_row on a panel's setup row: the menu row, then Right opens the panel
    (its setup row lit: "submenu"), Right on that row opens its list lit on the option it holds, Down steps the list, OK
    sets the option and brings the panel back with its slider lit ("unknown", OK in the footer), as the hand frames of
    2026-11-02 show (kit2_hdmi_watch 02361 -> 02362 -> 02363). OCR reads what each screen shows; the slider's number is
    made up (SLIDER), the option held at the start too."""
    OPTIONS = ["Option Z", "Manual"]
    SLIDER = "+1"

    def __init__(self, held="Option Z", takes=True, answers=True):
        self.screen, self.option, self.lit, self.takes, self.presses, self.n, self.logged = "menu", held, 0, takes, [], 0, []
        self.answers = answers                       # False: OK goes unanswered, the list stays open
        self.run = SimpleNamespace(log=lambda kind, **kw: self.logged.append((kind, kw)))
        self.shoot()

    def shoot(self):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_panel.png"), image=None)

    def read(self):
        return {"menu": SimpleNamespace(kind="menu", bar=(103, 141), focus="rows"),
                "panel": SimpleNamespace(kind="submenu", bar=(75, 122), focus="rows"),
                "list": SimpleNamespace(kind="list", bar=(145, 193), focus=None),
                "slider": SimpleNamespace(kind="unknown", bar=None, focus=None)}[self.screen]

    def lines(self):
        title = Line(text="Made-up Panel", conf=1.0, x=17, y=8, w=250, h=40)
        if self.screen == "list":
            return [Line(text="Setup Row", conf=1.0, x=73, y=28, w=200, h=40),
                    Line(text=self.OPTIONS[self.lit], conf=1.0, x=150, y=150, w=150, h=33)]
        if self.screen in ("panel", "slider"):
            foot = "? MENU D" if self.screen == "panel" else "MENU D • OK"
            return [title, Line(text="Setup Row", conf=1.0, x=23, y=80, w=200, h=40),
                    Line(text=self.option, conf=1.0, x=528, y=83, w=88, h=30),
                    Line(text=self.SLIDER, conf=1.0, x=297, y=153, w=50, h=31),
                    Line(text=foot, conf=1.0, x=460, y=440, w=160, h=24)]
        return [Line(text="Made-up Panel", conf=1.0, x=139, y=103, w=200, h=36)]

    def press(self, key):
        self.presses.append(key)
        if self.screen == "menu" and key == "right":
            self.screen = "panel"
        elif self.screen == "panel" and key == "right":
            self.screen, self.lit = "list", self.OPTIONS.index(self.option)
        elif self.screen == "list" and key == "down":
            self.lit = (self.lit + 1) % len(self.OPTIONS)
        elif self.screen == "list" and key == "enter" and self.answers:
            self.option = self.OPTIONS[self.lit] if self.takes else self.option
            self.screen = "slider"
        self.shoot()

    def refresh(self, tag):
        self.shoot()
        return self.read()


@pytest.mark.parametrize("takes", [True, False])
def test_the_real_set_row_sets_a_panels_setup_row_and_says_no_screen_word(monkeypatch, capsys, takes):
    """scale_run.setup through the real afreg_run.set_setup_row and mode_switch.set_row on a made-up panel: Right into
    the panel, its setup row found there, Right opens the list, Down to Manual, OK; the panel coming back with its
    slider lit is the choice made (no information screen to take). Then the setup row must read the option asked for,
    else the run stops. Nothing printed names the slider's number or the option held at the start."""
    import afreg_run
    import mode_switch
    cam = PanelMenu(takes=takes)
    monkeypatch.setattr(S.ocr, "read", lambda paths, eng=None: {p: cam.lines() for p in paths})
    monkeypatch.setattr(mode_switch, "open_menu", lambda c: None)
    monkeypatch.setattr(mode_switch, "find", lambda c, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "info_notice_ok", lambda *a, **k: pytest.fail("the panel taken for an information"))
    monkeypatch.setattr(afreg_run, "set_setup_row", afreg_run.set_setup_row)
    closes, dats = [], {Path("start.DAT"): {STATE_KEY: 0}}

    def download(name):
        dats[Path(f"{name}.DAT")] = {STATE_KEY: int(cam.option == "Manual")}
        return Path(f"{name}.DAT")
    monkeypatch.setattr(S, "close_screen", lambda c, link: closes.append(c.frame.path))
    monkeypatch.setattr(S, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(S, "time", SimpleNamespace(sleep=lambda s: None))
    monkeypatch.setattr(S, "camset", SimpleNamespace(read=lambda p: dats[p], diff=lambda a, b: [
        SimpleNamespace(key=k, before=a[k], after=b[k]) for k in a if a[k] != b[k]]))
    monkeypatch.setattr(S, "definition_index", lambda: SET_INDEX)
    monkeypatch.setattr(S, "held_value", lambda cs, k: cs.get(k))
    sets, panels = [(["Made-up Panel", "Setup Row"], "Manual")], {"Made-up Panel"}
    if takes:
        base = S.setup(cam, SimpleNamespace(download=download), None, None, None, Path("start.DAT"), sets, panels)
        assert base == Path("after-set.DAT") and cam.option == "Manual"
    else:
        with pytest.raises(S.Failed, match=r"after OK the panel's setup row does not read Manual \(\d+_panel\.png\)$"):
            S.setup(cam, SimpleNamespace(download=download), None, None, None, Path("start.DAT"), sets, panels)
    assert cam.presses == ["right", "right", "down", "enter"] and len(closes) == 1
    said = capsys.readouterr().out
    assert "choosing 'Manual'" in said and PanelMenu.SLIDER not in said and "Option Z" not in said


def test_set_row_missing_its_option_names_no_option_the_list_was_on(monkeypatch):
    """mode_switch.set_row (its own --set too): an option that never comes round in the list stops the step with the
    frame named; what the list's bar read, which can be the owner's option, goes to the run's events only."""
    import mode_switch
    cam = PanelMenu()
    cam.OPTIONS = ["Option Z", "Option Y"]
    monkeypatch.setattr(S.ocr, "read", lambda paths, eng=None: {p: cam.lines() for p in paths})
    monkeypatch.setattr(mode_switch, "find", lambda c, cycle, model, label: None)
    with pytest.raises(S.Failed) as got:
        mode_switch.set_row(cam, None, None, ["Made-up Panel", "Setup Row"], "Manual", print)
    assert "did not come round in its list" in str(got.value) and "Option" not in str(got.value)
    assert any(kind == "set_row_missed" for kind, _ in cam.logged)


# ---------------------------------------------------------------- a scale counts up to the right

def test_a_look_whose_number_falls_on_right_stops_the_row(drive):
    """A scale of -3, -2, -1 where OCR reads nothing and the reader leaves out every minus: it reads 3, 2, 1, evenly
    stepped, but falling on Right; a scale counts up to the right, so the row stops before any choice."""
    labels = {0: "-3", 1: "-2", 2: "-1"}
    cam = Slider(1, top=2)
    got = drive(1, set(), lambda place, i: labels[place].lstrip("-"), cam=cam, shown=lambda place: labels[place])
    assert "the number falling on Right" in got.out and got.lines == [] and cam.oks == []


def test_a_choice_whose_number_moves_the_wrong_way_stops_before_ok(rig):
    """In a choice the reader reads the number after a Right press lower than before (a sign or a digit misread): the
    screen is closed and no OK is pressed."""
    cam = Scale(held=1)
    log = rig(cam, {1}, reader=lambda true: "0" if true == 2 else str(true))
    with pytest.raises(S.Failed, match=r"Right moved the number the wrong way .* no OK"):
        S.choose(cam, log.link, None, None, None, PATH, VALS, 3, 1)
    assert "enter" not in cam.presses and log.downloads == [] and len(log.closes) == 1


def test_a_set_the_file_does_not_hold_stops_the_run_before_any_row(drive, setter):
    """The set row's OK seemed to take, but its record in the file after the setting does not hold the option's code
    (the definition names both): the run stops before any row, naming the row, the option asked for and the record."""
    setter.lost.add(SETUP)
    cam = Slider(2, panel=True)
    got = drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], index=SET_INDEX,
                args=["--set", f"{SETUP}=Manual"])
    assert (f"stopped: Failed: {SETUP}: the file after the setting does not hold Manual "
            f"({STATE_KEY})") in got.out
    assert cam.presses == [] and got.lines == []


def test_a_submenu_rows_set_is_not_judged_as_a_panels(monkeypatch, capsys):
    """A --set on a submenu's row: OK brings the submenu page back, its breadcrumb holding the submenu's name and its
    first row's value where a panel shows its setup option (as kit2_pass2 145809_menu.png reads). That page is no
    panel of the run's, so the set is not judged there; with no record for it in the definition it is said to be not
    verified in the file, and the run goes on."""
    import afreg_run
    import mode_switch
    page = [Line(text="Shooting > Made-up Group > »•Made-up Settings", conf=1.0, x=0, y=3, w=468, h=34),
            Line(text="First Row", conf=1.0, x=57, y=57, w=172, h=31), Line(text="Value 7a", conf=1.0, x=561, y=59, w=73, h=33),
            Line(text="Second Row", conf=1.0, x=53, y=105, w=167, h=40),
            Line(text="Value 2b", conf=1.0, x=461, y=110, w=176, h=34)]
    cam = SimpleNamespace(frame=SimpleNamespace(path=Path("00001_page.png")), presses=[],
                          read=lambda: SimpleNamespace(kind="submenu"), run=SimpleNamespace(log=lambda *a, **k: None))
    monkeypatch.setattr(S.ocr, "read", lambda paths, eng=None: {q: page for q in paths})
    monkeypatch.setattr(mode_switch, "open_menu", lambda c: None)
    monkeypatch.setattr(mode_switch, "set_row", lambda c, cycle, model, path, option, say: say(f"choosing {option!r}"))
    monkeypatch.setattr(afreg_run, "set_setup_row", afreg_run.set_setup_row)
    monkeypatch.setattr(S, "close_screen", lambda c, link: None)
    monkeypatch.setattr(S, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(S, "time", SimpleNamespace(sleep=lambda s: None))
    monkeypatch.setattr(S, "definition_index", lambda: {})
    monkeypatch.setattr(S, "camset", SimpleNamespace(read=lambda q: {}, diff=lambda a, b: []))
    sets = [(["Made-up Settings", "Second Row"], "Option A")]
    base = S.setup(cam, SimpleNamespace(download=lambda name: Path(f"{name}.DAT")), None, None, None, Path("start.DAT"),
                   sets, {"Made-up Panel"})
    assert base == Path("after-set.DAT")
    assert "Made-up Settings > Second Row = Option A: not verified in the file" in capsys.readouterr().out


def test_set_row_whose_ok_leaves_its_list_open_stops(monkeypatch):
    """OK on the option goes unanswered: one fresh look, the list still open, and the step stops naming the frame (no
    second OK, as prove_run stops a row whose OK leaves the list open)."""
    import mode_switch
    cam = PanelMenu(answers=False)
    monkeypatch.setattr(S.ocr, "read", lambda paths, eng=None: {p: cam.lines() for p in paths})
    monkeypatch.setattr(mode_switch, "find", lambda c, cycle, model, label: None)
    with pytest.raises(S.Failed, match=r"OK on 'Manual' went unanswered, its list still open \(\d+_panel\.png\)"):
        mode_switch.set_row(cam, None, None, ["Made-up Panel", "Setup Row"], "Manual", lambda m: None)
    assert cam.presses == ["right", "right", "down", "enter"]


# ---------------------------------------------------------------- a panel's setup row is always set by the run

def test_a_panel_row_without_its_setup_rows_set_is_refused_before_anything_connects(drive, setter):
    """--panel-row with no --set inside its panel: refused before anything connects, the refusal giving the exact
    --set, the setup row's label taken from the definition (the setting one row inside the panel with Manual among its
    values); a proof made on the option the camera stood on would tell it (decision 16)."""
    cam = Slider(2, panel=True)
    with pytest.raises(SystemExit, match=f'add --set "{SETUP}=Manual"$'):
        drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], index=SET_INDEX, auto_set=False,
              args=["--set", "Made-up Select=Option A"])
    assert cam.presses == [] and setter.calls == []


def test_a_panel_row_whose_setup_row_the_definition_does_not_name_gets_the_sets_form(drive, setter):
    cam = Slider(2, panel=True)
    with pytest.raises(SystemExit, match=r'add --set "Made-up Scale > <its setup row>=Manual" \(the definition names '
                                         r'no setup row'):
        drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], auto_set=False)
    assert cam.presses == [] and setter.calls == []


def test_a_panel_rows_setup_row_set_to_another_option_is_refused(drive, setter):
    cam = Slider(2, panel=True)
    with pytest.raises(SystemExit, match="set to 'Option Z', not Manual"):
        drive(2, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], index=SET_INDEX, auto_set=False,
              args=["--set", f"{SETUP}=Option Z"])
    assert cam.presses == [] and setter.calls == []


def test_a_panel_runs_proofs_name_its_setup_row_in_their_context(drive, setter):
    """With the setup row's --set the run sets it through the menu before the rows, and every line's context names it."""
    cam = Slider(1, panel=True)
    got = drive(1, set(range(5)), on_slider, cam=cam, shown=lambda place: SIGNED[place], index=SET_INDEX,
                args=["--set", f"{SETUP}=Manual", "--context", "made up"])
    assert setter.calls == [(SETUP, "Manual")] and len(got.attempts) == 1
    assert {ln["context"] for ln in got.lines} == {f"{SETUP} = Manual, made up"}


def test_the_setup_rows_label_is_the_definitions_own():
    """The label comes from the definition's settings (their menu row and values), never from a body's name in the
    prover: a made-up body's setup row is found by the same rule, and a row with no Manual, or one row deeper, is not."""
    index = {"a": {"row": ["Made-up Panel", "Made-up Setup"], "values": [[0, "Auto"], [1, "Manual"]]},
             "b": {"row": ["Made-up Panel", "Made-up Level"], "values": [[0, "-1"], [1, "+1"]]},
             "c": {"row": ["Made-up Panel", "Made-up Setup", "Deeper"], "values": [[1, "Manual"]]},
             "d": {"row": ["Other Panel", "Setup"], "values": [[1, "Manual"]]}}
    assert S.setup_rows_named(["Made-up Panel"], index) == ["Made-up Setup"]
    assert S.setup_rows_named(["made-up  panel"], index) == ["Made-up Setup"]
    assert S.setup_rows_named(["No Such Panel"], index) == []
    assert S.panel_set_refused([("Made-up Panel", True)], [(["Made-up Panel", "Made-up Setup"], "Manual")], index) == ""
    assert S.panel_set_refused([("Made-up Panel", False)], [], index) == "", "a plain scale needs no set"
    why = S.panel_set_refused([("Made-up Panel", True)], [(["Other Panel", "Setup"], "Manual")], index)
    assert why.endswith('add --set "Made-up Panel > Made-up Setup=Manual"')
