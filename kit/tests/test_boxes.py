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
    from test_enter_check import SQ_LINES, ocr_lines
    consent = boxes_run.screen_consent(PATH, NAMES)
    assert isinstance(consent, live.TwoBoxes) and (consent.row, consent.boxes, consent.at) == (
        "Frame Rate Settings", tuple(NAMES), tuple(BOXES))
    assert live.two_boxes_refused(consent, ocr_lines(SQ_LINES)) == ""
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
