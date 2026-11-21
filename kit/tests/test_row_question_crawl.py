"""The row's own question in the crawl's real order of calls (2026-11-21, expstd_movie_sqb, kit2_crawl_expstd_mvb 00012
and 00013): camkit.crawl wraps the live camera in Counted, and the way past pass_row_question set on that wrapper
(cam.confirm_once) stayed on the wrapper, so the live camera's Enter check met an Enter with none and refused it ("the
notice screen holds a question mark"), the lap cancelled. The tests before passed a camera to pass_row_question
directly. Here the words a caller sets for one press (confirm_once, answer_once, may_open_exact, permit) reach the
camera through Counted, the crawl's visit answers the question through it, and with no way past the Enter is still
refused. Nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "tests"))
from camkit import crawl, safety  # noqa: E402
from test_row_question import QUESTION, ROW, TEXT, Sent, camera  # noqa: E402


def test_the_way_past_set_on_the_crawls_camera_reaches_the_live_camera(tmp_path, monkeypatch):
    live = camera(tmp_path, monkeypatch, "notice", QUESTION, "OK")
    cam = crawl.Counted(live)
    cam.confirm_once = ("row_question", ROW)
    assert live.confirm_once == ("row_question", ROW) and "confirm_once" not in vars(cam)
    with pytest.raises(Sent):
        cam.press("enter")
    assert cam.presses == 1 and live.confirm_once is False      # spent by that press


def test_without_the_way_past_the_crawls_enter_is_refused_as_before(tmp_path, monkeypatch):
    cam = crawl.Counted(camera(tmp_path, monkeypatch, "notice", QUESTION, "OK"))
    with pytest.raises(safety.Refused, match="question mark"):
        cam.press("enter")


@pytest.mark.parametrize("name", ["confirm_once", "answer_once", "may_open_exact", "permit"])
def test_every_one_press_word_goes_through_to_the_camera(name):
    inner = SimpleNamespace()
    cam = crawl.Counted(inner)
    setattr(cam, name, "x")
    assert getattr(inner, name) == "x" and getattr(cam, name) == "x"
    cam.presses = 5                                     # the wrapper's own count stays its own
    assert not hasattr(inner, "presses") and cam.presses == 5


class Inner:
    """The live camera as the crawl meets it: Right on the row opens its question, Cancel lit; Up lights OK; Enter goes
    only with the row's way past set on THIS camera (as camkit.live's check asks), then an unknown screen shows."""

    def __init__(self):
        self.kind, self.lit, self.pressed, self.confirm_once = "submenu", "Cancel", [], False
        self.frame = SimpleNamespace(path=Path("00011_down.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind, key=self.kind)

    def press(self, key, **kw):
        confirmed, self.confirm_once = self.confirm_once, False
        if key == "enter" and confirmed != ("row_question", ROW):
            raise safety.Refused("the notice screen holds a question mark: it asks")
        self.pressed.append(key)
        self.frame = SimpleNamespace(path=Path(f"000{len(self.pressed) + 11}_{key}.png"), image=None)
        if key == "right":
            self.kind = "notice"
        elif key == "up":
            self.lit = "OK"
        elif key == "enter":
            self.kind = "unknown"


def test_the_crawls_visit_answers_the_rows_question_through_its_counted_camera(monkeypatch):
    import crawl_run
    from proving import screens
    monkeypatch.setattr(screens, "ROW_QUESTION", set())
    monkeypatch.setattr(screens, "notice_lit", lambda c: c.lit)
    monkeypatch.setattr(screens, "screen_text", lambda c: TEXT)
    monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: ROW)
    inner = Inner()
    cam = crawl.Counted(inner)
    r = crawl.visit_row(cam, SimpleNamespace(kind="submenu", key="submenu"), {"page": "p"}, 0, {"label": ROW},
                        path=("Exposure/Color", "Exposure"), info_ok=crawl_run.info_ok_pass({}, frozenset({ROW})))
    assert inner.pressed[:3] == ["right", "up", "enter"]
    assert r.info_ok and r.info_ok["row"].endswith(ROW)
