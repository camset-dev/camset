"""A row's own question answered with OK on the owner's word for that row alone (2026-11-21): Exposure Std. Adjust on the
a1 II asks "This function adjusts the standard of optimum exposure. Generally, adjustment is not necessary. Adjust?"
with OK and Cancel (Cancel lit) before it opens. The owner's words, whole: "Exposure adjust is ok, just put it back to
where it was at the end." Only a run that names the row (--allow "Exposure Std. Adjust") answers it, only on that row's
path, only where the screen read IS that question (safety.row_question: its words as the camera's frames show them,
its two buttons and nothing else), with the cursor moved onto OK first; the camera's own Enter check judges that one
Enter again on the screen read afresh (camkit.live's ("row_question", ROW)). Any other screen, any other row, and
every run without the flag: as before (the notice gets MENU). Nothing talks to a camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
from camkit import live, paths, safety  # noqa: E402
from camkit.runs import Run  # noqa: E402

ROW = "Exposure Std. Adjust"
QUESTION = ("This function adjusts the standard of optimum exposure. Generally, adjustment is not necessary. Adjust? "
            "OK Cancel")
# the question as OCR reads it on the camera's own frames, line by line (kit2_drive's, kit2_crawl_sq_1120's and the
# look laps' in Movie and S&Q: all 49 frames read alike)
LINES = ["This function adjusts the standard of", "optimum exposure.", "Generally, adjustment is not necessary.",
         "Adjust?", "OK", "Cancel"]
TEXT = " ".join(LINES)
# the camera's own frames of it: Cancel lit as Right opens it, OK lit after one Up (kit2_drive, Stills), and as the
# crawls and look laps met it in S&Q and Movie
FRAMES = [("kit2_drive/shots/01213_right.png", "Cancel"), ("kit2_drive/shots/01214_up.png", "OK"),
          ("kit2_drive/shots/01354_right.png", "Cancel"), ("kit2_drive/shots/01355_up.png", "OK"),
          ("kit2_crawl_sq_1120/shots/00601_right.png", "Cancel")]


# ---------------------------------------------------------------- safety.row_question: the words, measured

def test_the_rows_own_question_is_known_by_its_whole_words_and_two_buttons():
    assert safety.row_question(QUESTION, ROW) == ""
    assert safety.row_question(TEXT, ROW) == ""
    assert safety.row_question("This function adjusts the standard of optimum exposure. Generally, adjustment is "
                               "not necessary. Adjust? Cancel OK", ROW) == ""     # the buttons in either order


@pytest.mark.parametrize("text, why", [
    ("", "no text"),
    ("This function adjusts the standard of optimum exposure. Adjust? OK Cancel", "not the question's"),
    (QUESTION.replace("Adjust?", "Adjust all?"), "more than its two buttons"),
    (QUESTION.replace("optimum", "the best"), "not the question's"),
    (QUESTION + " Later", "more than its two buttons"),
    (QUESTION.replace("OK Cancel", "OK"), "more than its two buttons"),
    (QUESTION + " Format", "whatever is allowed: format"),
    ("Format the memory card? OK Cancel", "whatever is allowed: format"),
    ("Reset PP1 to the default setting? OK Cancel", "reads as a confirmation"),
    ("This operation or setting not available as follows Shoot Mode S&Q Motion OK", "not the question's"),
    (QUESTION.replace("optimum exposure", "optimum exposure Initialize"), "whatever is allowed: initialize"),
])
def test_any_other_screen_is_not_that_question(text, why):
    got = safety.row_question(text, ROW)
    assert got and why.lower() in got.lower(), got


def test_a_row_with_no_known_question_answers_nothing():
    assert "no question the kit may answer" in safety.row_question(QUESTION, "Exposure Comp.")
    assert "no question the kit may answer" in safety.row_question(QUESTION, "Format")
    assert set(safety.ROW_QUESTIONS) == {ROW}


def test_the_cameras_frames_read_as_that_question():
    """On the camera's own frames, as the kit's OCR reads them: each the row's question, its lit button as recorded."""
    from camkit import ocr
    from camkit.frames import load
    from proving.screens import notice_lit
    a1 = paths.a1ii_root()
    found = [(a1 / rel, lit) for rel, lit in FRAMES if (a1 / rel).exists()]
    if not found:
        pytest.skip("the camera's frames are not here")
    for f, lit in found:
        text = ocr.text_in(ocr.read([f])[f], (0, 0, 640, 480))
        assert safety.row_question(text, ROW) == "", (f.name, text)
        frame = load(f)
        assert notice_lit(SimpleNamespace(frame=frame)).strip() == lit, f.name


# ---------------------------------------------------------------- the camera's own Enter check

class Sent(Exception):
    pass


def camera(tmp_path, monkeypatch, kind, text, lit="OK"):
    """A LiveCamera on a screen read as `kind` whose whole text is `text` and lit text `lit` (test_enter_check's)."""
    for name in ("text_of", "body_of"):
        monkeypatch.setattr(live, name, lambda cam, v=text: v)
    monkeypatch.setattr(live, "title_of", lambda cam: "")
    monkeypatch.setattr(live, "lit_text", lambda image, path: lit)
    monkeypatch.setattr(live, "lone_of", lambda image, path: "")
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", None))
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("rowq", root=tmp_path)
    cam.screen = SimpleNamespace(kind=kind)
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_x.png")
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open = frozenset()

    def press(key, *a, **k):
        raise Sent(k)
    cam.link = SimpleNamespace(press=press, moves=0, menus=0)
    return cam


def events(cam) -> list:
    p = cam.run.dir / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_without_the_runs_word_the_question_gets_no_enter(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, "notice", QUESTION)
    with pytest.raises(safety.Refused):
        cam.press("enter")


def test_the_rows_way_past_goes_on_its_own_question_with_ok_lit_alone(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, "notice", QUESTION, "OK")
    cam.confirm_once = ("row_question", ROW)
    with pytest.raises(Sent):
        cam.press("enter")
    passed = [e for e in events(cam) if e["kind"] == "enter_passed"]
    assert passed and ROW in passed[-1]["by"] and "OK lit" in passed[-1]["by"]
    assert cam.confirm_once is False                        # spent by that press
    with pytest.raises(safety.Refused):
        cam.press("enter")                                  # the next Enter has no way past


@pytest.mark.parametrize("kind, text, lit, key, why", [
    ("notice", QUESTION, "Cancel", "enter", "not OK"),
    ("notice", QUESTION, "", "enter", "not OK"),
    ("notice", "Format the memory card? OK Cancel", "OK", "enter", "not Exposure Std. Adjust's own question"),
    ("notice", QUESTION + " Delete", "OK", "enter", "not Exposure Std. Adjust's own question"),
    ("notice", QUESTION + " Later", "OK", "enter", "not Exposure Std. Adjust's own question"),
    ("dialog", QUESTION, "OK", "enter", "not a notice"),
    ("unknown", QUESTION, "OK", "enter", "not a notice"),
    ("notice", QUESTION, "OK", "c4", "Enter alone"),
])
def test_the_rows_way_past_refuses_every_other_screen_key_or_lit_button(tmp_path, monkeypatch, kind, text, lit, key,
                                                                         why):
    cam = camera(tmp_path, monkeypatch, kind, text, lit)
    cam.confirm_once = ("row_question", ROW)
    with pytest.raises(safety.Refused, match=why):
        cam.press(key)


def test_the_way_past_names_one_row_and_lifts_nothing_for_another(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, "notice", QUESTION, "OK")
    cam.confirm_once = ("row_question", "Exposure Comp.")
    with pytest.raises(safety.Refused, match="no question the kit may answer"):
        cam.press("enter")


# ---------------------------------------------------------------- the prover's pass: the cursor onto OK, one Enter

class Cam:
    """A camera whose screen is the question with `lit` lit; Up lights OK; it records every press and the
    confirm_once set at each."""

    def __init__(self, lit="Cancel", kind="notice", text=TEXT, up_lights="OK"):
        self.lit, self.kind, self.text, self.up_lights = lit, kind, text, up_lights
        self.pressed, self.confirm_once = [], False
        self.frame = SimpleNamespace(path=Path("00601_right.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def press(self, key, **kw):
        self.pressed.append((key, self.confirm_once))
        if key == "up":
            self.lit = self.up_lights
        if key == "enter":
            self.confirm_once = False
            self.kind = "submenu"


@pytest.fixture
def pass_with(monkeypatch):
    from proving import screens

    def make(cam, allowed=(ROW,)):
        monkeypatch.setattr(screens, "ROW_QUESTION", set(allowed))
        monkeypatch.setattr(screens, "notice_lit", lambda c: c.lit)
        monkeypatch.setattr(screens, "screen_text", lambda c: c.text)
        return screens.pass_row_question
    return make


def test_the_pass_moves_onto_ok_and_presses_enter_once_with_the_way_past(pass_with):
    cam = Cam()
    got = pass_with(cam)(cam, ROW, ROW)
    assert got == {"row": ROW, "frame": "00601_right.png", "by": f"--allow {ROW!r}"}
    assert cam.pressed == [("up", False), ("enter", ("row_question", ROW))]


def test_the_pass_with_ok_lit_already_presses_enter_alone(pass_with):
    cam = Cam(lit="OK")
    assert "refused" not in pass_with(cam)(cam, ROW, ROW)
    assert cam.pressed == [("enter", ("row_question", ROW))]


@pytest.mark.parametrize("cam, name, lit_before, why", [
    (Cam(kind="dialog"), ROW, ROW, "not a notice"),
    (Cam(text="Format the memory card? OK Cancel"), ROW, ROW, "not Exposure Std. Adjust's own question"),
    (Cam(), ROW, "Exposure Comp.", "lit bar read before Right is not the row"),
    (Cam(up_lights="Cancel"), ROW, ROW, "OK could not be lit"),
])
def test_the_pass_refuses_with_no_enter(pass_with, cam, name, lit_before, why):
    got = pass_with(cam)(cam, name, lit_before)
    assert why in got.get("refused", ""), got
    assert all(k != "enter" for k, _ in cam.pressed)


def test_a_row_the_run_does_not_name_is_not_its_business(pass_with):
    cam = Cam()
    assert pass_with(cam, allowed=())(cam, ROW, ROW) is None
    assert pass_with(cam)(cam, "Exposure Comp.", "Exposure Comp.") is None
    assert cam.pressed == []


# ---------------------------------------------------------------- the runs' flag

def test_the_flag_names_only_a_row_whose_question_the_kit_knows():
    import runner
    assert runner.row_questions_or_exit([ROW]) == {ROW}
    assert runner.row_questions_or_exit([]) == set()
    with pytest.raises(SystemExit, match="no question the kit may answer"):
        runner.row_questions_or_exit(["Format"], only=True)
    assert runner.row_questions_or_exit(["Camera Set. Memory", ROW]) == {ROW}     # prove_run's other --allow rows


def test_crawl_run_takes_the_flag_for_such_a_row_alone_and_never_on_a_look_lap():
    src = (ROOT / "kit" / "crawl_run.py").read_text(encoding="utf-8")
    assert "row_questions_or_exit(a.allow, only=True)" in src
    assert "--allow answers no question on a --network run" in src


def test_crawls_pass_answers_the_named_rows_question_and_leaves_every_other_row(monkeypatch):
    """crawl_run's info_ok: a row --allow names goes to pass_row_question, the lit bar read on the frame before Right; a
    row it does not name, with no --info-ok, is left as ever (None)."""
    import crawl_run
    from proving import screens
    calls = []
    monkeypatch.setattr(screens, "pass_row_question", lambda cam, name, lit: calls.append((name, lit)) or {"row": name})
    monkeypatch.setattr(screens, "ROW_QUESTION", set())
    monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: ROW)
    assert crawl_run.info_ok_pass({}, frozenset()) is None
    passed = crawl_run.info_ok_pass({}, frozenset({ROW}))
    before = SimpleNamespace(image=None, path=Path("00009_x.png"))
    assert passed(object(), ROW, before) == {"row": ROW} and calls == [(ROW, ROW)]
    assert passed(object(), "Exposure Comp.", before) is None and len(calls) == 1


# ---------------------------------------------------------------- the way into the row's rows (proving.nav.enter_path)

class PathCam:
    """Right on the row opens its question; the pass (made up here) leaves the row's submenu; find_row finds any row."""

    def __init__(self):
        self.kind, self.pressed = "submenu", []
        self.frame = SimpleNamespace(path=Path("00010_x.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def press(self, key, **kw):
        self.pressed.append(key)
        if key == "right":
            self.kind = "notice"


def test_the_way_in_answers_the_question_only_for_the_row_the_run_named(monkeypatch):
    from proving import base, nav, screens
    calls = []

    def passed(cam, name, lit):
        calls.append((name, lit))
        cam.kind = "submenu"
        return {"row": name, "frame": "00011_x.png", "by": "--allow"}
    monkeypatch.setattr(screens, "pass_row_question", passed)
    monkeypatch.setattr(nav.live, "lit_text", lambda image, path: ROW)
    monkeypatch.setattr(nav, "find_row", lambda cam, label, at=None: True)
    monkeypatch.setattr(screens, "ROW_QUESTION", {ROW})
    cam = PathCam()
    nav.enter_path(cam, [ROW, "Multi"], 0)
    assert calls == [(ROW, ROW)] and cam.pressed == ["right"]
    monkeypatch.setattr(screens, "ROW_QUESTION", set())          # a run that does not name the row: as before
    cam, calls[:] = PathCam(), []
    with pytest.raises(base.Failed, match="opened notice, not its submenu"):
        nav.enter_path(cam, [ROW, "Multi"], 0)
    assert calls == []
