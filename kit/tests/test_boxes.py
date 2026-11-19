"""boxes_run on a row's own two-box screen (S&Q and Time-lapse Frame Rate Settings, Movie mode, 2026-11-17): a box that
draws a dash is not offered in this state, said in the run's failures as a blocked row and no failure; the OK that leaves
the screen goes by the screen's own consent (camkit.live.TwoBoxes); a run a refusal or a failure stopped exits non-zero.
Made-up frames, readings and sessions only: nothing here talks to a camera, a reader or a network.
"""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import boxes_run  # noqa: E402
from camkit import live, ocr, safety  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED  # noqa: E402

BOXES = boxes_run.LAYOUTS["framerate"]
PATH = ["S&Q Settings", "Frame Rate Settings"]
NAMES = ["Rec Frame Rate", "Frame Rate"]
# the screen's boxes as kit2_pass2's frames draw them: box 0 lit orange, box 1 dark with a grey border; a dash 7 x 3 px
# (240050_right.png, XAVC HS 8K), a value's glyphs 34 px tall (240079_down.png, XAVC HS 4K: "24p", "120fps")
ORANGE, DASH_LIT, DASH_DARK, INK, BORDER = (170, 51, 0), (198, 130, 96), (96, 96, 96), (215, 198, 191), (120, 120, 120)


def picture(*drawn) -> np.ndarray:
    """The two-box screen, each box's content one of "dash", "value" or "" (nothing drawn)."""
    a = np.zeros((480, 640, 3), np.uint8)
    for b, (x0, y0, x1, y1) in enumerate(BOXES):
        if b == 0:
            a[y0:y1, x0:x1] = ORANGE
        else:
            a[y0:y0 + 2, x0:x1] = a[y1 - 2:y1, x0:x1] = BORDER
            a[y0:y1, x0:x0 + 2] = a[y0:y1, x1 - 2:x1] = BORDER
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if drawn[b] == "dash":
            a[cy - 1:cy + 2, cx - 3:cx + 4] = DASH_LIT if b == 0 else DASH_DARK
        elif drawn[b] == "value":
            a[cy - 17:cy + 17, cx - 23:cx + 24:3] = INK
    return a


def at(image, reads=("", ""), name="00050_right.png"):
    """A camera whose frame is `image` and whose OCR reads `reads` in the two boxes (nothing where "")."""
    lines = [ocr.Line(t, 1.0, x0 + 80, y0 + 10, 60, 36) for t, (x0, y0, _, _) in zip(reads, BOXES, strict=True) if t]
    cam = SimpleNamespace(frame=SimpleNamespace(image=image, path=Path(name)), presses=[])
    cam.press = lambda key, **k: cam.presses.append(key)
    cam.lines = lines
    return cam


@pytest.fixture
def seen(monkeypatch):
    """boxes_run's OCR reading the made-up camera's lines, its row opened and closed without a menu (recorded)."""
    got = {"opened": 0, "closed": 0}
    monkeypatch.setattr(boxes_run, "lines", lambda cam: cam.lines)
    monkeypatch.setattr(boxes_run, "open_row", lambda cam, cycle, model, path: got.__setitem__("opened", got["opened"] + 1))
    monkeypatch.setattr(boxes_run, "close_screen", lambda cam, link: got.__setitem__("closed", got["closed"] + 1))
    return got


def test_a_box_that_draws_a_dash_is_told_from_one_that_shows_a_value(seen):
    """dashed: OCR reads no letter or digit in the box (the dash read as nothing, or as "-") and its ink, against the box's
    own colour (orange when lit), is a short flat stroke. A value's glyphs, a box drawn empty (a frame caught mid-draw),
    or a box OCR reads a digit in, are none: such a box is looked at as ever (and an empty reading fails there)."""
    dash = at(picture("dash", "dash"))
    assert boxes_run.dashed(dash, 0) and boxes_run.dashed(dash, 1)
    assert boxes_run.dashed(at(picture("dash", "dash"), reads=("-", "–")), 1)
    value = at(picture("value", "value"), reads=("24p", "120fps"))
    assert not boxes_run.dashed(value, 0) and not boxes_run.dashed(value, 1)
    assert not boxes_run.dashed(at(picture("", "")), 0), "a box drawn empty is no dash"
    assert not boxes_run.dashed(at(picture("dash", "dash"), reads=("1", "")), 0), "OCR read a digit: no dash"
    assert not boxes_run.dashed(at(picture("value", "dash")), 0), "glyphs OCR missed are no dash"


def test_the_look_on_a_dashed_box_presses_nothing_and_says_it_is_not_offered(seen):
    """XAVC HS 8K: both boxes draw a dash (kit2_pass2 240050), and Up on one raised the camera's "not available as
    follows: File Format" (240051). The look now reads the box once opened, presses nothing on it, leaves with MENU and
    says it is not offered (NotOffered, naming the frame); a box with a value is looked at as ever."""
    cam = at(picture("dash", "dash"))
    with pytest.raises(boxes_run.NotOffered) as got:
        boxes_run.look(cam, None, None, None, PATH, 0)
    assert got.value.frame == "00050_right.png" and cam.presses == [] and seen == {"opened": 1, "closed": 1}


def test_a_dashed_screen_is_written_as_not_offered_in_this_state_and_no_proof(seen):
    """prove on the dash screen: one line per box asked in the run's failures, a blocked row as prove_run writes one
    (camkit.coverage: greyed in state; pass2_report: a row the camera would not open), keyed like the box's proofs (the
    row's path and the box's name); no proof line, no failure, the start the base. --only asks one box."""
    out, fails = Lines(), Lines()
    cam = at(picture("dash", "dash"))
    start = SimpleNamespace(name="00043_before.DAT")
    assert boxes_run.prove(cam, None, None, None, None, PATH, NAMES, None, None, start, out, fails) is start
    assert out == [] and [(r["path"], r["blocked"], r["frame"]) for r in fails] == [
        (PATH + [n], boxes_run.NOT_OFFERED, "00050_right.png") for n in NAMES]
    assert "not offered in this state" in boxes_run.NOT_OFFERED and fails[0]["why"].startswith(
        "S&Q Settings > Frame Rate Settings > Rec Frame Rate: not offered in this state")
    only = Lines()
    boxes_run.prove(at(picture("dash", "dash")), None, None, None, None, PATH, NAMES, "Frame Rate", None, start, Lines(),
                    only)
    assert [r["path"][-1] for r in only] == ["Frame Rate"]
    first = Lines()
    assert boxes_run.prove(at(picture("dash", "dash")), None, None, None, None, PATH, NAMES, None,
                           ("Rec Frame Rate", "24p"), start, Lines(), first) is start
    assert [r["path"][-1] for r in first] == ["Rec Frame Rate"], "--first's box not offered: nothing else is tried"


def test_the_row_screens_consent_passes_the_hs_4k_screen_and_choose_hands_it_before_ok(seen, monkeypatch):
    """The OK on the HS 4K screen, refused by the shape check (240079, no known kind), goes by the consent boxes_run
    builds for its row (screen_consent: the row's name, the two boxes' names and where they stand), judged on the
    screen's own shape with its three lines under the boxes; choose hands it to the camera for that one OK, after it
    has stepped the box to the value it proves."""
    from test_enter_check import SQ_LINES, footer_picture, ocr_lines
    consent = boxes_run.screen_consent(PATH, NAMES)
    assert isinstance(consent, live.TwoBoxes) and (consent.row, consent.boxes, consent.at) == (
        "Frame Rate Settings", tuple(NAMES), tuple(BOXES))
    assert live.two_boxes_refused(consent, ocr_lines(SQ_LINES), footer_picture()) == ""
    cam = at(picture("value", "value"), reads=("24p", "120fps"), name="00079_down.png")
    handed = []
    cam.press = lambda key, **k: handed.append((key, getattr(cam, "answer_once", None)))
    monkeypatch.setattr(boxes_run, "focus", lambda c: 0)
    monkeypatch.setattr(boxes_run, "vlm_option", lambda c: "24p")
    monkeypatch.setattr(boxes_run, "to_shooting", lambda *a: None)
    monkeypatch.setattr(boxes_run.time, "sleep", lambda s: None)
    link = SimpleNamespace(download=lambda tag: SimpleNamespace(name=f"{tag}.DAT"))
    got = boxes_run.choose(cam, link, None, None, None, PATH, 0, ["60p", "24p", "120p"], 1, NAMES)
    assert handed == [("enter", consent)] and got["chosen_frame"] == "00079_down.png"


# Time-lapse Frame Rate Settings as OCR read it on kit2_pass2 240575_right.png (2026-11-18), the row opened again after
# its first proof: the footer's "● OK" drawn as ever, read not at all, its "?" alone; the run stopped there ("Right on
# 'Frame Rate Settings' did not open its boxes (breadcrumb ..., footer '?')", exit 8)
TL_575_LINES = [("Shooting > Image Qua... > Frame Rate Settings", 0, 3, 514, 36), ("t Rec Frame Rate", 127, 65, 205, 28),
                ("tInterval Time", 381, 67, 185, 28), ("24p", 191, 189, 53, 38), ("1 s", 455, 189, 40, 30),
                ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
                ("0 h 02 min 00 s", 67, 383, 146, 24), ("?", 509, 441, 13, 26)]
TL_PATH = ["Time-lapse Settings", "Frame Rate Settings"]


def opened(monkeypatch, rows, picture, name="240575_right.png"):
    """boxes_run.open_row over a made-up camera whose screen, once Right is pressed, reads `rows` and draws `picture`:
    the menu, the scan's route and the submenu's Enter made up (nothing reached)."""
    from test_enter_check import ocr_lines
    cam = SimpleNamespace(frame=SimpleNamespace(image=picture, path=Path(name)), presses=[], lines=ocr_lines(rows))
    cam.press = lambda key, **k: cam.presses.append(key)
    monkeypatch.setattr(boxes_run, "lines", lambda c: c.lines)
    monkeypatch.setattr(boxes_run, "menu_from_shooting", lambda c: None)
    monkeypatch.setattr(boxes_run, "scan_position", lambda c, cycle: 0)
    monkeypatch.setattr(boxes_run, "go_to", lambda *a: True)
    monkeypatch.setattr(boxes_run, "enter_any", lambda c, path, i: None)
    boxes_run.open_row(cam, [], {}, TL_PATH)
    return cam


def test_the_boxes_opened_is_judged_by_the_ok_key_drawn_not_by_ocr_finding_it(monkeypatch):
    """240575: Right opened the Time-lapse boxes, their footer's "● OK" drawn as on every frame, and OCR read its "?"
    alone, so the run took the screen for not opened and stopped. open_row judges the footer's OK as drawn
    (camkit.screen.footer_keys, as the consent judges it), so that reading opens; ISO AUTO's two boxes, whose footer
    draws MENU Cancel beside its OK (kit2_pass2 206963), open as ever."""
    from test_enter_check import footer_picture
    cam = opened(monkeypatch, TL_575_LINES, footer_picture())
    assert cam.presses == ["right"]
    iso = footer_picture(stray=(389, 440, 500, 465))           # "MENU Cancel" beside the OK, as ISO AUTO's footer
    opened(monkeypatch, TL_575_LINES, iso)


@pytest.mark.parametrize("rows,keys,why", [
    (TL_575_LINES[:7] + [("? • OK", 509, 441, 120, 26)], ("help_only",), "no OK key drawn"),
    (TL_575_LINES, (), "no OK key drawn"),
    ([("Shooting > Image Qua... > Time-lapse Settings", 0, 3, 514, 36)] + TL_575_LINES[1:], ("help_only", "ok_key"),
     "did not open its boxes")])
def test_a_screen_whose_footer_draws_no_ok_or_whose_title_is_another_is_not_the_boxes(monkeypatch, rows, keys, why):
    """No OK key drawn in the footer (OCR reading "• OK" there or not), or a breadcrumb that is not the row's: the boxes
    did not open, and the row stops before anything but Right is pressed."""
    from test_enter_check import footer_picture
    with pytest.raises(boxes_run.Failed, match=why):
        opened(monkeypatch, rows, footer_picture(keys=keys))


class Lines(list):
    def write(self, line):
        self.append(json.loads(line))

    def flush(self):
        pass


def run_main(monkeypatch, tmp_path, body, args=()):
    """boxes_run.main over a made-up session that ends as runner.prover_session does: an exception in the body is said
    and the start file restored, never raised past it; `body` stands in for prove."""
    @contextlib.contextmanager
    def session(run, eyes):
        try:
            yield SimpleNamespace(cam=None, link=None, start=tmp_path / "00001_before.DAT")
        except Exception as e:
            print(f"stopped: {type(e).__name__}: {e}")
    monkeypatch.setattr(boxes_run, "load_scan", lambda scan: (None, None))
    monkeypatch.setattr(boxes_run, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    monkeypatch.setattr(boxes_run, "eyes_from_config", lambda run: None)
    monkeypatch.setattr(boxes_run, "prover_session", session)
    monkeypatch.setattr(boxes_run, "prove", body)
    boxes_run.main(["--row", " > ".join(PATH), "--boxes", ", ".join(NAMES), "--context", "Movie mode, made up",
                    "--scan", str(tmp_path), *args])


def raises(e):
    def body(*a, **k):
        raise e
    return body


def test_a_run_a_failure_or_a_refusal_stopped_exits_as_crawl_run_does(monkeypatch, tmp_path):
    """The session says the stop and restores the start file; then a refusal exits EXIT_REFUSED (7) and any other stop
    EXIT_INCOMPLETE (8), as kit/crawl_run.py does, so kit/tools/chain.py stops there; a run that ends, a STOP, and a row
    not offered in this state exit 0."""
    for e, code in ((safety.Refused("enter: the screen reads as 'unknown'"), EXIT_REFUSED),
                    (boxes_run.Failed("Frame Rate Settings box 0: the look read ['']"), EXIT_INCOMPLETE),
                    (RuntimeError("the eyes' feed has gone"), EXIT_INCOMPLETE)):
        with pytest.raises(SystemExit) as got:
            run_main(monkeypatch, tmp_path, raises(e))
        assert got.value.code == code, e
    run_main(monkeypatch, tmp_path, lambda *a, **k: None)
    run_main(monkeypatch, tmp_path, raises(StopRequested("STOP file")))


def test_a_run_on_a_dashed_screen_writes_its_lines_tagged_and_exits_0(monkeypatch, tmp_path, seen):
    """main on the dash screen: the run's failures.jsonl holds a not-offered line per box, tagged with the run's
    --context as its proofs are (proving.base.Tagged), and the run ends with status 0, the chain going on."""
    def look(cam, link, cycle, model, path, b):
        raise boxes_run.NotOffered("00050_right.png")
    monkeypatch.setattr(boxes_run, "look", look)
    run_main(monkeypatch, tmp_path, boxes_run.prove)
    lines = [json.loads(x) for x in (tmp_path / "failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(r["path"][-1], r["blocked"], r["context"]) for r in lines] == [
        (n, boxes_run.NOT_OFFERED, "Movie mode, made up") for n in NAMES]


# ---------------------------------------------------------------- the arrows a lit box draws, read glued to its value

# ISO AUTO Minimum's values (Movie mode), and OCR's readings of the lit box over HDMI on kit2_pass2 248934 and 248980
# (2026-11-18): the box's Up arrow above the value read as a caret glued in front of it, on some frames only
ISO_VALS = ["ISO100", "ISO125", "ISO160", "ISO200", "ISO250", "ISO320", "ISO400", "ISO500", "ISO640"]


class WalkCam:
    """A two-box screen whose box 0 walks `vals` (Down one on, Up one back, stopping at the ends), OCR reading the value
    as `glued[(value, look)]` on its look-th frame of a step (a fresh frame, no press, a look more), else as it is."""
    def __init__(self, vals, at=0, glued=None):
        self.vals, self.i, self.glued, self.looks, self.presses = list(vals), at, dict(glued or {}), 0, []
        self.frame = SimpleNamespace(image=picture("value", "value"), path=Path("00001_right.png"))

    @property
    def lines(self):
        v = self.vals[self.i]
        t = self.glued.get((v, self.looks), v)
        return [ocr.Line(t, 1.0, BOXES[0][0] + 80, BOXES[0][1] + 10, 60, 36)]

    def press(self, key, **kw):
        self.presses.append(key)
        self.looks = 0
        if key == "down":
            self.i = min(self.i + 1, len(self.vals) - 1)
        elif key == "up":
            self.i = max(self.i - 1, 0)

    def refresh(self, tag):
        self.looks += 1

    @property
    def run(self):
        logged = self.__dict__.setdefault("logged", [])
        return SimpleNamespace(log=lambda kind, **f: logged.append((kind, f)))


def test_an_arrow_read_glued_to_a_boxs_value_is_left_off_only_where_a_value_is_left(seen):
    """The lit box draws an arrow above and below its value, which OCR reads glued to it at an end ("^ISO500"): left off
    only where what is left is exactly one of the box's values, never a guess; in the look, where the values are not
    known yet, the box is read again on a fresh frame (no press) until no arrow sign is left at an end."""
    assert boxes_run.box_value("^ISO200", ISO_VALS) == "ISO200"
    assert boxes_run.box_value("ISO200v", ISO_VALS) == "ISO200" and boxes_run.box_value("vISO200^", ISO_VALS) == "ISO200"
    assert boxes_run.box_value("∧ISO640", ISO_VALS) == "ISO640"            # LOGICAL AND, the arrow's other reading
    assert boxes_run.box_value("^ISO999", ISO_VALS) == "^ISO999"                 # no value left: as read
    assert boxes_run.box_value("A24p", ["A24p", "24p"]) == "A24p"                # a value as read stays itself
    assert boxes_run.box_value("vAv", ["Av", "vA"]) == "vAv"                     # two values left: none taken
    cam = WalkCam(ISO_VALS, glued={("ISO500", 0): "^ISO500"})
    vals, held = boxes_run.look(cam, None, None, None, ["ISO"], 0)
    assert vals == ISO_VALS and held == "ISO100" and "^ISO500" not in vals


def test_an_arrow_every_fresh_frame_keeps_is_left_off_where_the_second_reader_agrees(seen, monkeypatch):
    """kit2_pass2 249674-249677 (2026-11-18): ISO500 read "^ISO500" on the step's frame and on every fresh frame after
    it. The look leaves the arrow's sign off (signs only: a v or an A stays) and asks the second reader what the lit box
    shows on that frame: the value is taken where the two readings agree as a proof's two readings are judged
    (camkit.match.same), both readings logged in the run's events; two that disagree, or no answer, stop the look as
    before, naming both."""
    asked = []

    def reader(answer):
        monkeypatch.setattr(boxes_run, "vlm_option", lambda c: asked.append(c.frame.path.name) or answer)
    glued = {("ISO500", k): "^ISO500" for k in range(9)}
    reader("ISO 500")
    cam = WalkCam(ISO_VALS, glued=glued)
    vals, held = boxes_run.look(cam, None, None, None, ["ISO"], 0)
    assert vals == ISO_VALS and asked
    kind, f = cam.logged[-1]
    assert kind == "box_read_by_both" and (f["ocr"], f["cleaned"], f["second"], f["agree"]) == (
        "^ISO500", "ISO500", "ISO 500", True)
    for answer, said in (("ISO 640", "'ISO 640'"), ("", "no answer")):
        reader(answer)
        with pytest.raises(boxes_run.Failed, match=rf"'\^ISO500'.*{said}"):
            boxes_run.look(WalkCam(ISO_VALS, glued=glued), None, None, None, ["ISO"], 0)
    reader("ISO 500")
    letter = WalkCam(ISO_VALS, glued={("ISO500", k): "vISO500" for k in range(9)})
    vals, _ = boxes_run.look(letter, None, None, None, ["ISO"], 0)
    assert "vISO500" in vals, "a letter is never left off without the box's values"


def test_the_saved_frames_of_iso500_read_with_its_arrow_give_iso500_with_the_reader(monkeypatch):
    """The camera's own frames (kit2_pass2 249674 and the three fresh frames after it), read by this computer's OCR:
    every one reads "^ISO500"; with the second reader answering "ISO 500" for the frame, box 0 is ISO500 (skipped
    without the a1 II's runs or an OCR engine)."""
    from camkit import paths
    from camkit.frames import load
    shots = paths.a1ii_root() / "kit2_pass2" / "shots"
    names = ["249674_down.png", "249675_reread.png", "249676_reread.png", "249677_reread.png"]
    if not all((shots / n).exists() for n in names):
        pytest.skip(f"{shots} does not hold the frames")
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    frames = [load(shots / n) for n in names]
    cam = SimpleNamespace(frame=frames[0], logged=[], at=[0])

    def refresh(tag):
        cam.at[0] = min(cam.at[0] + 1, len(frames) - 1)
        cam.frame = frames[cam.at[0]]
    cam.refresh = refresh
    cam.run = SimpleNamespace(log=lambda kind, **f: cam.logged.append((kind, f)))
    monkeypatch.setattr(boxes_run, "BOXES", boxes_run.LAYOUTS["iso"])
    monkeypatch.setattr(boxes_run, "vlm_option", lambda c: "ISO 500")
    assert boxes_run.value(cam, 0) == "^ISO500"
    assert boxes_run.read_box(cam, 0, row="ISO") == "ISO500" and cam.frame is frames[-1]
    assert cam.logged[-1][1]["frame"] == "249677_reread.png"


def test_the_proving_pass_takes_the_value_with_the_arrow_left_off(seen, monkeypatch):
    """step_ok on kit2_pass2 248980's reading: the box on ISO200, read "^ISO200", is ISO200 (one of its values once the
    arrow is left off), stepped to and left with OK, where it stopped the run on 2026-11-18; the second reader's reading
    is kept beside OCR's as before."""
    cam = WalkCam(ISO_VALS, at=3, glued={("ISO200", 0): "^ISO200", ("ISO250", 0): "^ISO250"})
    monkeypatch.setattr(boxes_run, "focus", lambda c: 0)
    monkeypatch.setattr(boxes_run, "vlm_option", lambda c: "ISO 250")
    got = boxes_run.step_ok(cam, None, None, ["ISO"], 0, ISO_VALS, 4, ["ISO AUTO Minimum", "ISO AUTO Maximum"])
    assert cam.presses == ["down", "enter"] and boxes_run.settled(got["vlm"]) == "ISO 250"
