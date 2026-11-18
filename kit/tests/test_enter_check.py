"""The camera's own check of what a screen asks, after its review (2026-11-14, step C1): the screen is looked at again
just before the press and the link carries the move count it was judged at; retries never re-arm a consent on a screen
nobody judged; a notice's lone OK must read OK and be that very notice; the way back to the shooting screen and the
session's end judge a fresh frame; and the cases the review's mutants found untested. Made-up cameras, frames and
links only: nothing here talks to a camera, a reader or a network.
"""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import live, ocr, safety, screen  # noqa: E402
from camkit.frames import Frame  # noqa: E402
from camkit.link import CameraRefused, LinkError  # noqa: E402
from camkit.runs import Run  # noqa: E402

FAKE = [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parent / "fake_camlink.py")]
NOT_AVAILABLE = "This operation or setting not available as follows Picture Profile OK"


class Sent(Exception):
    pass


def camera(tmp_path, monkeypatch, kind, text, lit="OK", lone="", body=None, stale=""):
    """A LiveCamera on a screen read as `kind` whose text is `text` (above its footer `body`, the whole text when not
    given), lit text `lit`, a notice's lone OK verdict `lone`, and the screen looked at again `stale` (live.look_again's
    reason, "" when unchanged). Its link refuses MENU as the camera does (CameraRefused) and raises Sent for any other
    key, with what the press carried."""
    for name, value in (("text_of", text), ("body_of", text if body is None else body), ("title_of", "")):
        monkeypatch.setattr(live, name, lambda cam, v=value: v)
    monkeypatch.setattr(live, "lit_text", lambda image, path: lit)
    monkeypatch.setattr(live, "lone_of", lambda image, path: lone)
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: (stale, None))
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("enter", root=tmp_path)
    cam.screen = SimpleNamespace(kind=kind)
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_x.png")
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open = frozenset()

    def press(key, *a, **k):
        if key == "menu":
            raise CameraRefused("press menu 60: button not accepted")
        raise Sent(k)
    cam.link = SimpleNamespace(press=press, moves=0, menus=0)
    return cam


def events(cam) -> list:
    path = cam.run.dir / "events.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


# ---------------------------------------------------------------- 1: the screen looked at again before the press

def frame(white: bool = False) -> Frame:
    a = np.zeros((480, 640, 3), np.uint8)
    if white:
        a[150:330, 100:540] = 255                   # a box drawn: another screen
    return Frame(image=a, t=0.0)


class Eyes:
    """Eyes that give the frames `frames` in turn (the last one again after), named `name` (osd or hdmi)."""
    def __init__(self, frames, name="hdmi"):
        self.frames, self.name, self.grabbed = list(frames), name, 0

    def grab(self, tag, save=True):
        self.grabbed += 1
        return self.frames.pop(0) if len(self.frames) > 1 else self.frames[0]


def test_look_again_takes_a_fresh_frame_and_refuses_one_that_moved(monkeypatch):
    """Fix 1 of the review: the screen judged is compared with a fresh grab (screen.same_state): the same picture goes, a
    changed one (a question the camera raised by itself, a popup drawn after the settle) or a grab that fails refuses."""
    judged = screen.read(frame())
    assert live.look_again(Eyes([frame()]), judged, "enter")[0] == ""
    assert "changed since it was judged" in live.look_again(Eyes([frame(True)]), judged, "enter")[0]

    class Gone:
        name = "hdmi"

        def grab(self, tag, save=True):
            raise RuntimeError("the capture stopped")
    assert "could not be looked at again" in live.look_again(Gone(), judged, "enter")[0]
    assert "could not be looked at again" in live.look_again(None, judged, "enter")[0]


def test_on_osd_eyes_the_look_waits_out_the_lag_since_the_kits_last_move(monkeypatch):
    """The camera's own picture can lag the screen by seconds: on OSD eyes the one grab waits until OSD_LAG has passed
    since the kit's own last move (Link.moved_at), so the frame shows that move's outcome; on HDMI, or long after the
    move, it waits for nothing (a fake clock)."""
    slept = []
    monkeypatch.setattr(live.time, "sleep", slept.append)
    monkeypatch.setattr(live.time, "monotonic", lambda: 100.0)
    judged = screen.read(frame())
    for name, moved_at, wait in (("osd", 98.83, 2.33), ("osd", 90.0, None), ("osd", None, None), ("hdmi", 99.9, None)):
        slept.clear()
        eyes = Eyes([frame()], name=name)
        assert live.look_again(eyes, judged, "enter", moved_at)[0] == "" and eyes.grabbed == 1
        assert slept == ([] if wait is None else [pytest.approx(wait)]), (name, moved_at)
    assert live.osd_wait(99.0, now=100.0) == pytest.approx(2.5) and live.osd_wait(96.5, now=100.0) == 0.0
    assert live.osd_wait(None, now=100.0) == 0.0 and live.OSD_LAG > 3.25          # longer than the 3.25 s freeze seen
    why = live.look_again(Eyes([frame(True)], name="osd"), judged, "enter", 98.0)[0]
    assert "changed since it was judged" in why


def test_the_link_marks_when_it_last_moved_and_the_camera_looks_by_it(tmp_path, monkeypatch):
    """Link.call records moved_at once a moving command (a press, a dial, a download, an upload) is answered, never for
    a read; LiveCamera hands it to look_again."""
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.moved_at is None
        lk.download("first")
        first = lk.moved_at
        assert isinstance(first, float)
        lk.call("ping")
        assert lk.moved_at == first                 # a read moves nothing
        lk.press("menu")
        assert lk.moved_at > first
    seen = []
    cam = camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting")
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: seen.append(moved_at) or ("", None))
    cam.link.moved_at = 123.5
    with pytest.raises(Sent):
        cam.press("enter")
    assert seen == [123.5]


def test_no_way_past_lifts_the_fresh_look(tmp_path, monkeypatch):
    """The owner route's word (confirm_once), an armed permit or a consent: none answers a screen that moved since it
    was judged."""
    for way in ("confirm", "permit", "answer"):
        cam = camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting", stale="it moved")
        cam.confirm_once = "--confirm" if way == "confirm" else False
        cam.permit = {"row": "Format", "what": "confirm"} if way == "permit" else None
        cam.answer_once = "--allow 'Camera Set. Memory'" if way == "answer" else None
        with pytest.raises(safety.Refused, match="it moved"):
            cam.press("enter")


def test_the_press_carries_the_move_count_it_was_judged_at(tmp_path, monkeypatch):
    """LiveCamera hands the link its count of moving commands at the look (judged), for an Enter and a trash button
    alike; other keys carry none."""
    cam = camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting")
    cam.link.moves = 7
    for key in ("enter", "ms_enter"):
        with pytest.raises(Sent) as got:
            cam.press(key)
        assert got.value.args[0]["judged"] == 7
    cam.hdmi = SimpleNamespace(settle=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sent")))
    with pytest.raises(Sent) as got:
        cam.press("c4", allow={"c4"})
    assert got.value.args[0]["judged"] == 7
    with pytest.raises(Sent) as got:
        cam.press("down")
    assert "judged" not in got.value.args[0]


def fake_link(tmp_path, monkeypatch):
    from camkit import link as L
    monkeypatch.delenv("CAMSET_USB", raising=False)
    return L.Link(Run("enter", root=tmp_path), ip="192.0.2.10", binary=FAKE, catch_signals=False)


def test_the_link_refuses_a_judgement_that_is_stale_or_no_count(tmp_path, monkeypatch):
    """Fix 1 and 8: an Enter, the multi-selector's centre or a trash button goes only with the link's own move count at
    the judgement: a count from before a later command (a download moved the screen), a bare True or none is refused."""
    with fake_link(tmp_path, monkeypatch) as lk:
        judged = lk.moves
        lk.download("between")                      # a moving command after the judgement
        for key, allow in (("enter", ()), ("ms_enter", ()), ("c4", {"c4"}), ("delete", {"delete"})):
            for given in (judged, True, None, "7"):
                with pytest.raises(safety.Refused, match="judged the screen on show"):
                    lk.press(key, allow=allow, screen=SimpleNamespace(kind="menu"), judged=given)
            assert lk.press(key, allow=allow, screen=SimpleNamespace(kind="menu"), judged=lk.moves)["ok"]


# ---------------------------------------------------------------- the frame looked at again is the frame judged

def fresh_camera(tmp_path, monkeypatch, old_text, new_text, stale=""):
    """A LiveCamera whose screen reads as a list both before and after the look (the same state: a list compares its
    title strip and lit row), its text `old_text` on the frame its caller read and `new_text` on the frame look_again
    grabbed (`stale`: look_again's reason)."""
    cam = camera(tmp_path, monkeypatch, "list", old_text, "Single Shooting")
    listed = SimpleNamespace(kind="list")
    monkeypatch.setattr(live.screen, "read", lambda f: listed)
    cam.screen = listed
    fresh = frame()

    def text(c):
        return new_text if c.frame is fresh else old_text
    monkeypatch.setattr(live, "text_of", text)
    monkeypatch.setattr(live, "body_of", text)
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: (stale, fresh))
    return cam, fresh


def test_the_text_is_judged_on_the_fresh_frame_not_the_one_read_before(tmp_path, monkeypatch):
    """Finding 2 of the second review: "same state" is no proof of the same words: an overlay over a list's other rows
    keeps the kind and the lit row. The question mark and the rest are judged on the frame look_again grabbed, saved as
    evidence."""
    cam, fresh = fresh_camera(tmp_path, monkeypatch, "Drive Mode Single Shooting", "Format the card? OK Cancel")
    with pytest.raises(safety.Refused, match="question mark"):
        cam.press("enter")
    assert cam.frame is fresh and fresh.path.exists() and fresh.path.parent == cam.run.shots
    cam, fresh = fresh_camera(tmp_path, monkeypatch, "Drive Mode Single Shooting", "Drive Mode Continuous Shooting")
    with pytest.raises(Sent):
        cam.press("enter")


def test_a_screen_changed_since_its_reading_is_refused_whatever_it_shows(tmp_path, monkeypatch):
    """Finding 2 of the third review: the caller chose the press and judged its words on the screen it read, so a screen
    that changed since is refused (safety.ScreenChanged, a refusal), whether it asks or not, a way past named or not
    (so no list of ways past can leave one out, mutant Y4); nothing goes out, and the camera keeps the fresh frame and reading for a caller that
    reads again."""
    moved = "the screen changed since it was judged (now 'list')"
    for way in ("", "confirm", "answer", "lift", "permit"):
        for new in ("Drive Mode Continuous Shooting", "Clear registered faces? OK"):
            cam, fresh = fresh_camera(tmp_path, monkeypatch, "Drive Mode Single Shooting", new, moved)
            cam.may_open_exact = (lambda f, lit: True) if way == "lift" else None
            cam.confirm_once = "--confirm" if way == "confirm" else False
            cam.answer_once = "--allow 'Camera Set. Memory'" if way == "answer" else None
            cam.permit = {"row": "Format", "what": "confirm"} if way == "permit" else None
            with pytest.raises(safety.ScreenChanged, match="choose afresh"):
                cam.press("enter")
            assert cam.frame is fresh and fresh.path.exists(), (way, new)
    assert issubclass(safety.ScreenChanged, safety.Refused)
    assert "screen_changed_before_press" in [e["kind"] for e in events(cam)]


def test_every_check_of_the_press_reads_the_fresh_frame(tmp_path, monkeypatch):
    """The look comes before every check of an Enter (LiveCamera.look_before), so a menu page whose lit row reads as a
    never-open row on the frame grabbed (the same state as the caller's reading) is refused by the never-open check
    on that frame, never pressed on the old reading's row."""
    cam, fresh = fresh_camera(tmp_path, monkeypatch, "Drive Mode Single Shooting", "Format")
    page = SimpleNamespace(kind="submenu")
    monkeypatch.setattr(live.screen, "read", lambda f: page)
    cam.screen = page
    monkeypatch.setattr(live, "lit_text", lambda image, path: "Format" if path == fresh.path else "Drive Mode")
    with pytest.raises(safety.Refused, match="Format"):
        cam.press("enter")
    assert cam.frame is fresh


def test_a_fresh_frame_the_same_picture_keeps_the_callers_frame_and_its_text(tmp_path, monkeypatch):
    """Where the frame grabbed is the caller's own picture, pixel for pixel, the caller's frame stays: no frame is saved
    again and its text, read already, is not read again (the second OCR saved)."""
    cam = camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting")
    old = frame()
    old.path = tmp_path / "00001_down.png"
    cam.frame = old
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", frame()))
    with pytest.raises(Sent):
        cam.press("enter")
    assert cam.frame is old and not list(cam.run.shots.glob("*judged*"))
    assert live.same_picture(frame(), frame()) and not live.same_picture(frame(), frame(True))
    assert not live.same_picture(SimpleNamespace(image=None), SimpleNamespace(image=None))


def test_a_retry_after_a_changed_screen_goes_only_on_the_state_the_caller_judged(monkeypatch):
    """live.press: a press refused as ScreenChanged is tried once more, and only where the screen read afresh is again
    the state the caller judged; else, or a second time, the refusal stands."""
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    changed = safety.ScreenChanged("enter: the screen changed since it was judged")
    back = RetryCam([changed])
    live.press(back, "enter")
    assert [k for k, _, _ in back.presses] == ["enter", "enter"]
    still = RetryCam([changed], after=SimpleNamespace(kind="list", signature="other"))
    with pytest.raises(safety.ScreenChanged):
        live.press(still, "enter")
    assert len(still.presses) == 1
    twice = RetryCam([changed, changed])
    with pytest.raises(safety.ScreenChanged):
        live.press(twice, "enter")
    assert len(twice.presses) == 2


def test_prove_runs_enter_reads_its_choice_again_after_a_changed_screen(monkeypatch):
    """prove_run.enter_chosen: after a ScreenChanged the loop's check of its choice is made on the fresh screen and the
    Enter tried once more, the proof taking that evidence; a choice that no longer holds fails the row (Failed), and a
    second change stands."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import prove_run
    from proving.base import Failed

    class Cam:
        def __init__(self, errors):
            self.errors, self.pressed = list(errors), 0

        def press(self, key):
            self.pressed += 1
            if self.errors:
                raise self.errors.pop(0)
    changed = safety.ScreenChanged("enter: the screen changed since it was judged")
    assert prove_run.enter_chosen(Cam([]), ("old",), lambda: ("new",)) == ("old",)
    cam = Cam([changed])
    assert prove_run.enter_chosen(cam, ("old",), lambda: ("new",)) == ("new",) and cam.pressed == 2

    def gone():
        raise Failed("the cursor is not on 'Single Shooting'")
    cam = Cam([changed])
    with pytest.raises(Failed):
        prove_run.enter_chosen(cam, ("old",), gone)
    assert cam.pressed == 1
    with pytest.raises(safety.ScreenChanged):
        prove_run.enter_chosen(Cam([changed, changed]), ("old",), lambda: ("new",))


# ---------------------------------------------------------------- 3: a retry never answers a screen nobody judged

class RetryCam:
    """A camera whose presses raise `errors` in turn, then go; its screen after a refresh is `after` (the very
    reading kept when None). Every press is kept with the consent it carried."""
    def __init__(self, errors, after=None):
        self.errors, self.after, self.presses = list(errors), after, []
        self.screen = SimpleNamespace(kind="notice")
        self.confirm_once, self.answer_once = False, None

    def refresh(self, tag):
        if self.after is not None:
            self.screen = self.after

    def press(self, key, **kw):
        self.presses.append((key, self.confirm_once, self.answer_once))
        self.confirm_once, self.answer_once = False, None
        if self.errors:
            raise self.errors.pop(0)


def test_a_retry_rearms_a_consent_only_on_the_screen_judged(monkeypatch):
    """Fix 3: live.press tries again only after the camera's own refusal (CameraRefused), and gives the consent again
    only when the screen read afresh is the one judged."""
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    refused = CameraRefused("press enter 60: button not accepted")
    same = RetryCam([refused])
    live.press(same, "enter", confirm="--confirm", answer="--confirm 'x'")
    assert same.presses == [("enter", "--confirm", "--confirm 'x'")] * 2
    moved = RetryCam([refused], after=SimpleNamespace(kind="list", signature="other"))
    live.press(moved, "enter", confirm="--confirm", answer="--confirm 'x'")
    assert moved.presses == [("enter", "--confirm", "--confirm 'x'"), ("enter", False, None)]


@pytest.mark.parametrize("error", [LinkError("press enter 60: button enter not accepted: its release was refused three "
                                             "times, so it may still be held"),
                                   LinkError("press enter 60: no reply within 30 s")])
def test_a_held_or_unanswered_press_is_never_pressed_again(monkeypatch, error):
    """Fix 3: "not accepted" also says a button left held (it went down and may have acted): only CameraRefused is
    tried again; a held button or no reply raises at once."""
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam = RetryCam([error])
    with pytest.raises(LinkError):
        live.press(cam, "enter", confirm="--confirm")
    assert len(cam.presses) == 1


# ---------------------------------------------------------------- 4, N3: the way back to the shooting screen

def to_shooting(tmp_path, monkeypatch, kind, error, stale="", below=()):
    """proving.nav.to_shooting on a screen of `kind` whose MENU answers `error`, the notice's lines a lone OK (and the
    lines `below` under it: a second button), the screen looked at again after the refusal `stale`; returns the Enter
    presses sent."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving import nav
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    kinds = iter([kind] + ["shooting"] * 3)
    monkeypatch.setattr(nav.screen, "read", lambda f: SimpleNamespace(kind=next(kinds, "shooting")))
    monkeypatch.setattr(nav, "run_tmp_png", lambda f: tmp_path / "notice.png")
    lines = [ocr.Line(text="This operation or setting not available", conf=0.9, x=40, y=120, w=560, h=30),
             ocr.Line(text="OK", conf=0.9, x=300, y=352, w=40, h=30),
             *(ocr.Line(text=t, conf=0.9, x=290, y=410, w=60, h=30) for t in below)]
    monkeypatch.setattr(nav.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})
    monkeypatch.setattr(live, "lit_found", lambda image, kind=None: ((200, 340, 440, 395), True))
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: (stale, SimpleNamespace(image=None)))
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    with fake_link(tmp_path, monkeypatch) as lk:
        real = lk.press

        def press(key, **kw):
            if key == "menu":
                raise error
            return real(key, **kw)
        lk.press = press
        nav.to_shooting(lk, SimpleNamespace(grab=lambda save=False: SimpleNamespace(image=None)), "the test", tries=1)
    return [l for l in log.read_text(encoding="utf-8").splitlines() if "press enter" in l] if log.exists() else []


def test_to_shooting_sends_ok_only_on_a_real_refusal_on_the_same_notice(tmp_path, monkeypatch):
    """Fix 4: the OK goes only where the camera refused MENU (CameraRefused, never a held button's LinkError, whose
    words also say "not accepted"), on the notice looked at again after it and found the same; and never on another
    kind (N3): a refused MENU vouches for a notice's OK alone."""
    refused = CameraRefused("press menu 60: button not accepted")
    held = LinkError("press menu 60: button menu not accepted: its release was refused three times, so it may still be "
                     "held")
    assert len(to_shooting(tmp_path / "a", monkeypatch, "notice", refused)) == 1
    assert to_shooting(tmp_path / "b", monkeypatch, "notice", held) == []
    assert to_shooting(tmp_path / "c", monkeypatch, "notice", refused, stale="the screen changed") == []
    assert to_shooting(tmp_path / "d", monkeypatch, "list", refused) == []
    assert to_shooting(tmp_path / "e", monkeypatch, "notice", refused, below=("Abbrechen",)) == []   # a second button
    assert "not a notice" in live.menu_refused_enter("list", None, tmp_path / "x.png")


# ---------------------------------------------------------------- 5: a lone OK reads OK

@pytest.mark.parametrize("text,lit", [("Image database file error Recover", "Recover"),
                                      ("Pixel-Mapping Ausfuhren", "Ausfuhren"), ("Pixel mapping Execute", "Execute"),
                                      ("This operation is not available", "Enter")])
def test_a_lone_lit_button_that_is_no_ok_is_never_pressed_as_a_way_out(tmp_path, monkeypatch, text, lit):
    """Fix 5: after a refused MENU a notice's only lit button must read OK: a lone "Recover" or "Ausführen" acts. On a
    camera whose OK reads otherwise the kit stops on the notice (fail closed)."""
    assert "not OK" in safety.enter_refused("notice", text, lit, None, live.MENU_REFUSED, "")
    assert safety.enter_refused("notice", text.replace(lit, "OK"), "OK", None, live.MENU_REFUSED, "") == ""
    cam = camera(tmp_path, monkeypatch, "notice", text, lit)
    with pytest.raises(safety.Refused, match="not OK"):
        live.leave_notice(cam)


# ---------------------------------------------------------------- 6: no restore over a screen nobody judged

def test_the_sessions_end_holds_for_the_owner_over_a_screen_that_asks(tmp_path, monkeypatch, capsys):
    """Fix 6: where the shooting screen does not come, the screen on show is looked at afresh; over one that asks
    nothing is downloaded or uploaded: RESTORE_BY_HAND is written, the link stays open while the owner clears the
    screen, and the run exits EXIT_RESTORE_BY_HAND once the shooting screen is back."""
    import runner
    from camkit.runs import RESTORE_BY_HAND
    # a run root named as no camera is: the marker goes there alone, never into the clone's own runs/ (camkit.runs)
    run = Run("kit2_end", root=tmp_path / "runs" / "end-test")
    looks = iter([(None, "the notice does not show its lit button as its only one"), (None, "still asks"),
                  ("shooting", "")])
    looked = []
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: looked.append(1) or next(looks))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    finished = []
    monkeypatch.setattr(runner.session, "finish", lambda *a, **k: finished.append(a) or "end")

    def gives_up(link, eyes, why):
        raise RuntimeError("no shooting screen after MENU and 5 minutes")
    link = SimpleNamespace(run=run)
    with pytest.raises(SystemExit) as stop:
        runner.end_session(link, "eyes", tmp_path / "start.DAT", reach=gives_up)
    assert stop.value.code == runner.EXIT_RESTORE_BY_HAND and finished == []
    assert len(looked) == 3                         # it waited until the shooting screen was back
    assert (run.root / RESTORE_BY_HAND).exists() and not (Path(runner.__file__).parents[1] / "runs" / "end-test").exists()
    kinds = [json.loads(l)["kind"] for l in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[-2:] == ["restore_held", "restore_held_cleared"]
    out = capsys.readouterr().out
    assert "clear it on the camera by hand" in out and "upload_check.py" in out
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: ("menu", ""))      # a menu page: restored
    assert runner.end_session(link, "eyes", tmp_path / "start.DAT", reach=gives_up) == "end" and len(finished) == 1


@pytest.mark.parametrize("lit,restores", [("OK", True), ("Recover", False), ("", False)])
def test_no_restore_over_a_notice_whose_lone_button_is_no_ok(monkeypatch, lit, restores):
    """Fix 5 at the restore: a notice that refused every MENU close is restored over only where its lone lit button
    reads OK; a lone "Recover" acts, and a session dropped with it open could apply it."""
    import runner
    cam = SimpleNamespace(read=lambda: SimpleNamespace(kind="notice"), frame=SimpleNamespace(image=None, path=None))
    monkeypatch.setattr(runner, "text_of", lambda c: "Image database file error " + (lit or "OK"))
    monkeypatch.setattr(runner, "body_of", lambda c: "Image database file error " + (lit or "OK"))
    monkeypatch.setattr(runner, "lone_of", lambda image, path: "")
    monkeypatch.setattr(runner, "lit_text", lambda image, path: lit)
    kind, why = runner.restorable_after_close(cam)
    assert (kind == "notice") is restores, why


def test_restorable_now_judges_a_fresh_frame(tmp_path, monkeypatch):
    """The frame grabbed now: the shooting screen as it is; any other judged as a last screen is (restorable_after_close),
    its picture written into the run's own folder for OCR and taken away after."""
    import runner
    run = Run("kit2_end", root=tmp_path)
    link = SimpleNamespace(run=run)
    eyes = SimpleNamespace(grab=lambda save=False: frame())
    monkeypatch.setattr(runner.screen, "read", lambda f: SimpleNamespace(kind="shooting"))
    assert runner.restorable_now(link, eyes) == ("shooting", "")
    monkeypatch.setattr(runner.screen, "read", lambda f: SimpleNamespace(kind="unknown"))
    kind, why = runner.restorable_now(link, eyes)
    assert kind is None and "unknown" in why and not list(run.dir.glob("_restore_check_*"))
    gone = SimpleNamespace(grab=lambda save=False: (_ for _ in ()).throw(RuntimeError("the capture stopped")))
    assert runner.restorable_now(link, gone)[0] is None


def test_restorable_now_asks_the_cameras_own_picture_where_hdmi_is_black_or_the_eyes_are_gone(tmp_path, monkeypatch):
    """Finding 1b of the second review and 3 of the third: a black HDMI frame (Auto Framing) is read on the camera's own
    picture (session.osd_shooting); where the eyes cannot grab at all, the camera's own picture (osd_picture) is judged
    as an HDMI frame is: the shooting screen, a plain menu that asks nothing (restored over, as before the hold came),
    and nothing where that picture cannot be fetched either."""
    import runner
    link = SimpleNamespace(run=Run("kit2_end", root=tmp_path))
    monkeypatch.setattr(runner.screen, "read", lambda f: SimpleNamespace(kind="unknown"))
    asked = []
    monkeypatch.setattr(runner.session, "osd_shooting", lambda lk, f: asked.append(f) or True)
    assert runner.restorable_now(link, SimpleNamespace(grab=lambda save=False: frame())) == ("shooting", "")
    assert len(asked) == 1
    monkeypatch.setattr(runner.session, "osd_shooting", lambda lk, f: False)
    gone = SimpleNamespace(grab=lambda save=False: (_ for _ in ()).throw(RuntimeError("the capture stopped")))
    for seen, kind in (("shooting", "shooting"), ("menu", "menu"), (None, None)):
        picture = (frame(), SimpleNamespace(kind=seen)) if seen else (None, None)
        monkeypatch.setattr(runner, "osd_picture", lambda lk, v=picture: v)
        monkeypatch.setattr(runner, "restorable_after_close", lambda cam: (cam.read().kind, ""))
        got, why = runner.restorable_now(link, gone)
        assert got == kind and (got or "nor the camera's own picture" in why), (seen, why)


def test_osd_picture_fetches_into_the_runs_folder_and_takes_it_away(tmp_path, monkeypatch):
    import runner
    run = Run("kit2_end", root=tmp_path)
    seen = []

    def osd(path):
        seen.append(path)
        frame().save(path)
        return path
    f, s = runner.osd_picture(SimpleNamespace(run=run, osd=osd))
    assert f is not None and s is not None and seen[0].parent == run.dir and not seen[0].exists()
    assert runner.osd_picture(SimpleNamespace(run=run, osd=lambda p: (_ for _ in ()).throw(LinkError("disconnected")))) \
        == (None, None)


def held(tmp_path, monkeypatch, looks, gone=None, clock=None):
    """runner.hold_for_owner on a link whose screen reads `looks` in turn (restorable_now's answers), which `gone`
    (Link.gone's answers, "" while it is there) says has gone; returns (the exit or exception, the run, the looks made,
    the sleeps). The run's root is named as no camera is: its marker goes there alone."""
    import runner
    run = Run("kit2_end", root=tmp_path / "runs" / "end-test")
    looks, made, slept = iter(looks), [], []
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: made.append(1) or next(looks))
    monkeypatch.setattr(runner.time, "sleep", lambda s: slept.append(s))
    if clock is not None:
        monkeypatch.setattr(runner.time, "monotonic", clock)
    link = SimpleNamespace(run=run, **({"gone": gone} if gone is not None else {}))
    try:
        runner.hold_for_owner(link, "eyes", tmp_path / "start.DAT", "it asks", poll=5.0, say_every=120.0)
    except (SystemExit, KeyboardInterrupt) as e:
        return e, run, made, slept
    raise AssertionError("hold_for_owner returned")


def kinds_of(run) -> list:
    return [json.loads(l)["kind"] for l in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_the_hold_leaves_when_the_link_has_gone_with_the_marker_kept(tmp_path, monkeypatch, capsys):
    """Finding 1b: camlink gone (an auto power off, a dropped session, its output ended) ends the wait at once, exit
    EXIT_RESTORE_BY_HAND, the marker kept: nothing can be kept open, and the screen may still be up."""
    import runner
    from camkit.runs import RESTORE_BY_HAND
    answers = iter(["", "", "camlink has exited (status 1)"])
    e, run, made, _ = held(tmp_path, monkeypatch, [(None, "asks")] * 5, gone=lambda: next(answers))
    assert isinstance(e, SystemExit) and e.code == runner.EXIT_RESTORE_BY_HAND and len(made) == 2
    assert (run.root / RESTORE_BY_HAND).exists() and kinds_of(run)[-1] == "restore_held_link_gone"
    assert "the link has gone (camlink has exited (status 1))" in capsys.readouterr().out


def test_the_hold_leaves_on_the_shooting_screen_alone(tmp_path, monkeypatch):
    """Mutant Y9 of the third review: a screen a restore may go over (a menu page) does not end the hold; only the
    shooting screen does, once the owner has cleared what asked."""
    import runner
    e, run, made, _ = held(tmp_path, monkeypatch, [("menu", ""), ("list", ""), ("shooting", "")])
    assert e.code == runner.EXIT_RESTORE_BY_HAND and len(made) == 3


def test_link_gone_on_a_disconnect_camlink_survives(tmp_path, monkeypatch):
    """Finding 1 of the third review: the camera's session drops (a power-off, a cable out, a Wi-Fi drop) while camlink
    runs on and answers "disconnected" to everything: Link.gone says so from the SDK's event alone, and from a reply
    saying "disconnected" alone (ping: "connected": false); a command answered again clears it."""
    import time as T
    monkeypatch.setenv("FAKE_CAMLINK_STDERR", json.dumps([json.dumps({"event": "disconnected", "code": 33282})]))
    with fake_link(tmp_path / "event", monkeypatch) as lk:
        for _ in range(100):
            if lk.events:
                break
            T.sleep(0.02)
        assert lk.gone() == "the SDK reported the camera disconnected"
        assert lk.call("ping")["ok"] and lk.gone() == ""        # a command answered: the session is there
    monkeypatch.delenv("FAKE_CAMLINK_STDERR")
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT", "props")
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT_SILENT", "1")
    with fake_link(tmp_path / "reply", monkeypatch) as lk:
        assert lk.gone() == ""
        assert lk.call("props") == {"ok": False, "error": "disconnected", "id": lk._seq}
        assert lk.gone() == "camlink answers that the camera is disconnected" and not lk.events
        assert lk.call("ping")["connected"] is False and lk.gone() != ""


def test_the_hold_on_osd_eyes_leaves_when_the_camera_disconnects(tmp_path, monkeypatch):
    """The hold on OSD eyes over a camera whose session dropped: the grab and the camera's own picture both fail on
    "disconnected", and the next look at the link ends the wait, the marker kept (it waited for ever before)."""
    import runner
    from camkit.runs import RESTORE_BY_HAND
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT", "osd")
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT_SILENT", "1")
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    with fake_link(tmp_path / "hold", monkeypatch) as lk:
        eyes = SimpleNamespace(name="osd", grab=lambda save=False: lk.osd(tmp_path / "live.png"))
        with pytest.raises(SystemExit) as stop:
            runner.hold_for_owner(lk, eyes, tmp_path / "start.DAT", "it asks")
        assert stop.value.code == runner.EXIT_RESTORE_BY_HAND and "disconnected" in lk.gone()
        assert (lk.run.root / RESTORE_BY_HAND).exists()


def test_moved_at_is_set_when_a_moving_command_is_refused_or_unanswered(tmp_path, monkeypatch):
    """Mutant Y6 of the third review: the screen may have moved whatever came back, so moved_at is set for a moving
    command the camera refused and for one camlink never answered (its exit)."""
    from camkit.link import CameraRefused as Refused
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT", "press")
    monkeypatch.setenv("FAKE_CAMLINK_DISCONNECT_SILENT", "1")
    with fake_link(tmp_path / "refused", monkeypatch) as lk:
        with pytest.raises(Refused):
            lk.press("menu")
        assert isinstance(lk.moved_at, float)
    monkeypatch.delenv("FAKE_CAMLINK_DISCONNECT")
    monkeypatch.setenv("FAKE_CAMLINK_EXIT", "download")
    with fake_link(tmp_path / "exit", monkeypatch) as lk:
        with pytest.raises(LinkError):
            lk.download("x")
        assert isinstance(lk.moved_at, float)


def test_link_gone_says_why(tmp_path, monkeypatch):
    """Link.gone: "" while camlink answers; its exit, or the link closed, said."""
    monkeypatch.setenv("FAKE_CAMLINK_EXIT", "ping")
    lk = fake_link(tmp_path, monkeypatch)
    with lk:
        assert lk.gone() == "" and lk.output_ended is False
        lk.output_ended = True                  # its output ended while the process still runs
        assert lk.gone() == "camlink's output has ended"
        lk.output_ended = False
        with pytest.raises(LinkError):
            lk.call("ping")                     # the stand-in exits on it, status 3
        lk.proc.wait(10)
        assert "exited (status 3)" in lk.gone()
        assert lk.output_ended is True          # its stdout's end, read by the pump, marked
    assert lk.gone() == "the link is closed"


def test_a_stop_in_the_hold_is_said_once_and_ends_nothing(tmp_path, monkeypatch, capsys):
    """Finding 1c: a STOP (its file, or a first Ctrl-C) is said once: the link stays open until the screen is cleared,
    since closing could apply it; the wait goes on until the shooting screen is back."""
    import runner
    from camkit.runs import Run as R
    monkeypatch.setattr(R, "stop_requested", lambda self: True)
    e, run, made, _ = held(tmp_path, monkeypatch, [(None, "asks"), (None, "asks"), (None, "asks"), ("shooting", "")])
    assert e.code == runner.EXIT_RESTORE_BY_HAND and len(made) == 4
    out = capsys.readouterr().out
    assert out.count("a stop was asked for") == 1 and "A second Ctrl-C closes it anyway" in out
    assert kinds_of(run).count("restore_held_stop") == 1 and kinds_of(run)[-1] == "restore_held_cleared"


def test_a_second_ctrl_c_in_the_hold_closes_it_with_the_marker_kept(tmp_path, monkeypatch, capsys):
    import runner
    from camkit.runs import RESTORE_BY_HAND
    run_sleep = []

    def interrupted(s):
        run_sleep.append(s)
        raise KeyboardInterrupt
    looks = iter([(None, "asks")] * 3)
    run = Run("kit2_end", root=tmp_path / "runs" / "end-test")
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: next(looks))
    monkeypatch.setattr(runner.time, "sleep", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.hold_for_owner(SimpleNamespace(run=run), "eyes", tmp_path / "start.DAT", "it asks")
    assert (run.root / RESTORE_BY_HAND).exists() and kinds_of(run)[-1] == "restore_held_interrupted"
    assert "a second Ctrl-C: the link closes" in capsys.readouterr().out


def test_the_hold_closes_on_no_timer_and_says_the_request_again(tmp_path, monkeypatch, capsys):
    """No time limit closes the link (closing could apply the screen): an unattended run keeps waiting, the request said
    again every say_every seconds (a fake clock, a minute a look), until the shooting screen is back."""
    import runner
    t = iter(range(0, 100000, 60))
    e, run, made, _ = held(tmp_path, monkeypatch, [(None, "asks")] * 30 + [("shooting", "")], clock=lambda: float(next(t)))
    assert e.code == runner.EXIT_RESTORE_BY_HAND and len(made) == 31
    assert capsys.readouterr().out.count("still waiting") >= 10


def test_closing_that_gives_up_over_a_question_holds_for_the_owner(tmp_path, monkeypatch, capsys):
    """Finding 1a: camkit.live.close giving up on a screen restorable_after_close refuses no longer closes the link over
    it (exit 4): RESTORE_BY_HAND is written for the run's start file, the link stays open while the owner clears the
    screen, exit EXIT_RESTORE_BY_HAND."""
    import runner
    from camkit.runs import RESTORE_BY_HAND
    run = Run("kit2_end", root=tmp_path / "runs" / "end-test")

    def gives_up(cam, link):
        raise SystemExit("closing gave up after 8 tries: close it on the camera by hand")
    monkeypatch.setattr(runner, "close", gives_up)
    monkeypatch.setattr(runner, "restorable_after_close", lambda cam: (None, "its last screen asks or may ask"))
    looks = iter([(None, "asks"), ("shooting", "")])
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: next(looks))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    cam = SimpleNamespace(hdmi="eyes", network=None, owner=None)
    link = SimpleNamespace(run=run, close=lambda: pytest.fail("the link was closed over the question"))
    with pytest.raises(SystemExit) as stop:
        runner.close_for_restore(cam, link, tmp_path / "start.DAT")
    assert stop.value.code == runner.EXIT_RESTORE_BY_HAND
    marker = json.loads((run.root / RESTORE_BY_HAND).read_text(encoding="utf-8"))
    assert marker["start"].endswith("start.DAT") and kinds_of(run)[-2:] == ["restore_held", "restore_held_cleared"]
    out = capsys.readouterr().out
    assert "no restore is tried over it" in out and "clear it on the camera by hand" in out


# ---------------------------------------------------------------- 7: leave_notice's OK is bound to its notice

def test_leave_notices_ok_goes_on_that_notice_alone(tmp_path, monkeypatch):
    """Fix 7: after a refused MENU the screen read afresh as an option kind gets no Enter (it would open or choose)."""
    cam = camera(tmp_path, monkeypatch, "list", "Drive Mode Single Shooting", "Single Shooting")
    with pytest.raises(safety.Refused, match="not that notice"):
        live.leave_notice(cam)
    cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE)
    with pytest.raises(Sent):
        live.leave_notice(cam)


# ---------------------------------------------------------------- the reviewer's surviving mutants

def test_l5_a_refused_menu_vouches_for_the_very_next_press_alone(tmp_path, monkeypatch):
    cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE)
    with pytest.raises(CameraRefused):
        cam.press("menu")
    with pytest.raises(Sent):
        cam.press("down")                           # a press between: the refusal vouches for nothing after it
    with pytest.raises(safety.Refused, match="a notice"):
        cam.press("enter")


def test_l6_l12_a_menu_failing_otherwise_is_no_refusal(tmp_path, monkeypatch):
    """A MENU with no reply (or a button left held) may have gone: it records no refusal, so the next Enter on the notice
    is refused, and leave_notice raises without any OK."""
    cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE)
    sent = []

    def press(key, *a, **k):
        sent.append(key)
        if key == "menu":
            raise LinkError("press menu 60: no reply within 30 s")
        raise Sent(k)
    cam.link.press = press
    with pytest.raises(LinkError):
        cam.press("menu")
    with pytest.raises(safety.Refused, match="a notice"):
        cam.press("enter")
    with pytest.raises(LinkError):
        live.leave_notice(cam)
    assert "enter" not in sent


def test_l11_only_an_owner_permit_for_a_step_or_an_armed_press_lifts_the_check(tmp_path, monkeypatch):
    for what, lifts in (("option", False), ("open", False), ("step", True), ("confirm", True), ("final", True)):
        cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE)
        cam.permit = {"row": "Format", "what": what}
        if lifts:
            with pytest.raises(Sent):
                cam.press("enter")
        else:
            with pytest.raises(safety.Refused, match="a notice"):
                cam.press("enter")


def test_l16_a_notice_lone_of_cannot_read_is_no_lone_ok(tmp_path):
    assert "cannot be read" in live.lone_of(None, tmp_path / "missing.png")


def test_d1_a_consent_never_lifts_the_confirmation_words():
    import drive
    for consent in ("--confirm 'format all data ok cancel'", "--allow 'Camera Set. Memory'"):
        assert "confirmation" in drive.press_refused("enter", "OK", "Format all data? OK Cancel", "notice",
                                                     consent=consent)


def test_s5_l13_a_notices_question_mark_counts_below_the_footer_cut_and_the_cut_sits_at_415(tmp_path, monkeypatch):
    """The footer is left out of the question mark check on option screens only (camkit.screen's help glyph draws one
    there); a notice is judged on its whole text. body_of keeps what lies above y 415, nothing under it."""
    assert safety.enter_refused("notice", "Clear registered faces OK ?", "OK", "Clear registered faces OK",
                                live.MENU_REFUSED, "")
    assert safety.enter_refused("list", "Drive Mode Single Shooting ?", "x", "Drive Mode Single Shooting") == ""
    lines = [ocr.Line(text="Drive Mode", conf=0.9, x=150, y=380, w=200, h=30),
             ocr.Line(text="?", conf=0.9, x=600, y=420, w=20, h=30)]
    monkeypatch.setattr(live.ocr, "read", lambda paths, eng=None: {p: lines for p in paths})
    cam = SimpleNamespace(frame=SimpleNamespace(path=tmp_path / "00001_x.png"))
    assert live.FOOTER_TOP == 415 and live.body_of(cam) == "Drive Mode"


def test_s12_a_question_mark_known_only_once_folded():
    """The small and the vertical question marks fold to "?" (NFKC): caught though not listed."""
    for mark in ("﹖", "︖"):
        assert safety.question_mark(f"Clear registered faces{mark}")
        assert safety.enter_refused("list", f"Clear registered faces{mark} OK", "OK")


def test_s14_a_line_reading_cancel_among_others_is_a_second_button():
    box = (200, 340, 440, 395)
    ok = ("OK", 300, 352, 40, 30)
    assert "reads as a button" in safety.lone_ok("OK", [("MENU Cancel", 100, 280, 200, 30), ok], box)
    assert "reads as a button" in safety.lone_ok("OK", [("x Cance1", 100, 280, 200, 30), ok], box)
    assert safety.lone_ok("OK", [("This operation is not available", 100, 280, 400, 30), ok], box) == ""


class NoticeCam:
    """A notice whose lit item reads `lits` in turn (proving.screens.notice_lit), whose MENU the camera refuses or takes
    (`refuses`); every press kept."""
    def __init__(self, tmp_path, lits, refuses):
        self.lits, self.refuses, self.pressed = list(lits), refuses, []
        self.frame = SimpleNamespace(path=tmp_path / "00003_notice.png", image=None)

    def read(self):
        return SimpleNamespace(kind="notice")

    def press(self, key, **kw):
        self.pressed.append(key)
        if key == "down" and len(self.lits) > 1:
            self.lits.pop(0)
        if key == "menu" and self.refuses:
            raise CameraRefused("press menu 60: button not accepted")


def test_c2_c3_a_note_is_passed_only_where_menu_is_refused_after_the_box_is_left(tmp_path, monkeypatch):
    """proving.screens.pass_note without --info-ok: the cursor off "Don't show this again." first (Down, never ticking
    it), then MENU; a MENU the camera takes cancels the row and passes nothing; a refused one leads to the lone OK."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving import screens
    taken = NoticeCam(tmp_path, ["OK"], refuses=False)
    monkeypatch.setattr(screens, "notice_lit", lambda cam: cam.lits[0])
    assert "took MENU" in screens.pass_note(taken, "Mode Dial Control Set", "")["refused"]
    assert taken.pressed == ["menu"]
    boxed = NoticeCam(tmp_path, ["Don't show this again.", "OK"], refuses=True)
    got = screens.pass_note(boxed, "Mode Dial Control Set", "")
    assert "refused" not in got and boxed.pressed == ["down", "menu", "enter"]


def test_p4_table_walk_answers_only_the_cameras_refusal_with_its_lone_ok(tmp_path, monkeypatch):
    """table_walk.open_and_walk: an information notice after Enter on a cell gets MENU alone (never an OK, even where
    MENU is refused); the camera's refusal ("not available") is left as leave_notice leaves a notice."""
    import table_walk
    for text, pressed in (("You can set the dial in Custom Key OK", ["enter", "menu"]),
                          ("This operation or setting not available as follows OK", ["enter", "menu", "enter"])):
        monkeypatch.setattr(table_walk.ocr, "read", lambda paths, eng=None: {p: [] for p in paths})
        monkeypatch.setattr(table_walk.ocr, "text_in", lambda lines, box, t=text: t)
        cam = NoticeCam(tmp_path, ["OK"], refuses=True)
        with contextlib.suppress(CameraRefused):    # MENU refused on an information notice: the walk stops there
            table_walk.open_and_walk(cam, {}, 5)
        assert cam.pressed == pressed, text


# ---------------------------------------------------------------- the second review's findings 3 and 5, and X21

@pytest.mark.parametrize("phrase,goes", [("Wireless Remote", False), ("Picturesque Mountainside", False),
                                         ("Abcd Efgh Ijk", False), ("Abcd Efgh Ijkl", True),
                                         ("Drive Mode Single", True)])
def test_a_confirm_phrase_names_three_words_and_twelve_letters_at_least(phrase, goes):
    """--confirm "SCREEN TEXT" without --owner: fewer than INFO_OK_WORDS words or INFO_OK_MIN letters is no screen's
    whole text (mutant X10)."""
    import runner
    assert (runner.INFO_OK_WORDS, runner.INFO_OK_MIN) == (3, 12)
    if goes:
        assert runner.confirm_phrase_or_exit(phrase) == runner.notice_words(phrase)
    else:
        with pytest.raises(SystemExit, match="at least 3 words and 12 letters"):
            runner.confirm_phrase_or_exit(phrase)


def test_screen_named_leaves_ten_letters_over_and_no_more():
    """runner.screen_named: the screen's letters and digits beyond the phrase, at most INFO_OK_SLACK (10) of them, in
    words too short to be anything but an icon read as letters (mutant X12)."""
    import runner
    phrase = "Drive Mode Single Shooting"

    def lines(extra):
        return [ocr.Line(text=f"{phrase} {extra}", conf=0.9, x=10, y=10, w=300, h=30)]
    assert runner.INFO_OK_SLACK == 10
    assert runner.screen_named(phrase, lines("ab cd ef")) == ""             # 10 over, the phrase's own matching included
    assert "11 letters or digits beyond" in runner.screen_named(phrase, lines("ab cd ef g"))


def test_pp_resets_way_past_covers_its_own_question_alone(tmp_path, monkeypatch):
    """Finding 5: pp_reset_run passes ("profile_reset", "PPn"), which lifts nothing by itself: the camera reads the screen
    afresh and lets the Enter go only on that profile's own reset question (safety.profile_reset_dialog)."""
    for text, goes in (("Reset PP1 to the default setting? OK Cancel", True),
                       ("Reset PP2 to the default setting? OK Cancel", False),
                       ("Format the memory card? OK Cancel", False), ("", False)):
        cam = camera(tmp_path, monkeypatch, "dialog", text, "OK")
        cam.confirm_once = ("profile_reset", "PP1")
        if goes:
            with pytest.raises(Sent):
                cam.press("enter")
            assert "PP1's own reset question" in events(cam)[-1]["by"]
        else:
            with pytest.raises(safety.Refused, match="not PP1's own reset question"):
                cam.press("enter")
    cam = camera(tmp_path, monkeypatch, "dialog", "Reset PP1 to the default setting? OK Cancel", "OK")
    cam.confirm_once = ("anything", "PP1")
    with pytest.raises(safety.Refused, match="no way past this camera knows"):
        cam.press("enter")


def test_x21_a_consent_never_answers_leave_notices_ok(tmp_path, monkeypatch):
    """An OK meant for the notice that has just refused MENU (require_notice) is judged as that notice alone: a consent
    set beside it lifts nothing (a second button under its OK)."""
    cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE, lone="another line reads as a button ('Abbrechen')")
    cam.menu_refused = {"moves": cam.link.moves, "screen": cam.screen, "frame": "00001_x.png"}
    cam.answer_once = "--allow 'Camera Set. Memory'"
    with pytest.raises(safety.Refused, match="reads as a button"):
        cam.press("enter", require_notice=True)


# ---------------------------------------------------------------- a portrait dialog's Enter, read upright (2026-11-16)

# Focus Area's dialog held vertically with Vertical Display On, as orient_run.dialog_reading reads its frame made upright
# (kit2_a1fin_framepos_edges_gripdown_vdon2's 00051_up_upright.png): title (its icon read as "&"), the lit option, the
# whole text with the footer's help glyph and keys, and the text above the footer
UPRIGHT = ("& Focus Area", "Spot: M", "& Focus Area Spot: M XL L M S XS M C1 ? MENU Cancel OK",
           "& Focus Area Spot: M XL L M S XS M C1")
UPRIGHT_NAME = "Focus Area's own dialog, read upright, held vertically (grip down)"


def upright_consent(seen=None, fails=None, **changed):
    """afreg_run.choose_area's consent for the Enter on Focus Area's portrait dialog, its reading UPRIGHT with `changed`
    put in (title, lit, text, body); `seen` collects the frames it was asked to read, `fails` an exception it raises."""
    got = dict(zip(("title", "lit", "text", "body"), UPRIGHT, strict=True)) | changed

    def read(cam):
        if seen is not None:
            seen.append(cam.frame.path.name)
        if fails:
            raise fails
        return got["title"], got["lit"], got["text"], got["body"]
    return live.UprightDialog(UPRIGHT_NAME, "Focus Area", read)


def test_a_portrait_dialogs_enter_goes_by_its_consent_judged_as_a_level_dialogs_on_the_upright_reading(tmp_path,
                                                                                                   monkeypatch):
    """Held vertically with Vertical Display On, Focus Area's dialog is drawn in its portrait arrangement, which
    camkit.screen reads as no known kind: its Enter is refused as one (the run of 2026-11-16 stopped there). The prover's
    consent for that one Enter (UprightDialog) lets it go judged as a level dialog's is (safety.enter_refused as a
    dialog, then the confirmation words) on the judged frame read upright, its title the row's own, the help glyph's "?"
    in the footer counting for nothing as on a level dialog; the press is logged with the consent's words, and the
    consent is spent by it."""
    cam = camera(tmp_path, monkeypatch, "unknown", "Focus Area Spot: M ? MENU Cancel OK", "")
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("enter")
    seen = []
    cam = camera(tmp_path, monkeypatch, "unknown", "Focus Area Spot: M ? MENU Cancel OK", "")
    cam.answer_once = upright_consent(seen)
    with pytest.raises(Sent):
        cam.press("enter")
    assert seen == ["00001_x.png"], "read on the frame judged, once"
    passed = [e for e in events(cam) if e["kind"] == "enter_passed"]
    assert [e["by"] for e in passed] == [UPRIGHT_NAME] and passed[0]["screen"] == "unknown"
    assert cam.answer_once is None
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("enter")                                  # spent: the next Enter has no consent


@pytest.mark.parametrize("changed,why", [
    ({"body": UPRIGHT[3] + " Clear registered faces?"}, "holds a question mark"),
    ({"body": UPRIGHT[3] + " Cancel"}, "asks \\(Cancel\\)"),
    ({"lit": ""}, "a lit text that cannot be read"),
    ({"lit": "OK"}, "the lit button 'ok'"),
    ({"text": UPRIGHT[2].replace("Spot: M", "Format the memory card"), "lit": "Wide"}, "reads as a confirmation"),
    ({"text": "", "body": ""}, "nothing on the dialog screen can be read"),
    ({"title": "& Focus Area Limit"}, "is not Focus Area's"),
    ({"title": "Delete"}, "is not Focus Area's"),
    ({"title": ""}, "is not Focus Area's"),
    ({"fails": RuntimeError("no frame")}, "cannot be read \\(RuntimeError\\)")])
def test_a_portrait_dialogs_consent_still_refuses_what_a_level_dialog_would_refuse(tmp_path, monkeypatch, changed, why):
    """The upright reading judged as a level dialog's: a question mark above the footer, a Cancel or a button pair there,
    a lit option that cannot be read or is a button's word, a confirmation's words, a reading of nothing, or one that
    fails, each refuses; so does a title read upright that is not the row's own (another row, a question, nothing)."""
    cam = camera(tmp_path, monkeypatch, "unknown", "Focus Area Spot: M", "")
    cam.answer_once = upright_consent(**changed)
    with pytest.raises(safety.Refused, match=why):
        cam.press("enter")


def test_a_portrait_dialogs_consent_answers_no_other_screen_nor_key(tmp_path, monkeypatch):
    """The consent answers one Enter on a screen of no known kind and nothing else: on a notice, a first-time screen, a
    dialog that asks or a list it lifts nothing and is never read (the screen's own judgement stands), and the trash
    button meets the shape check as ever."""
    for kind, text, lit, why in (("notice", NOT_AVAILABLE, "OK", "is a notice"),
                                 ("unknown", FIRST_TIME, "OK", "is a notice"),
                                 ("dialog", "Delete this image? OK Cancel", "OK", "question mark"),
                                 ("list", "", "", "nothing on the list screen")):
        seen = []
        cam = camera(tmp_path, monkeypatch, kind, text, lit)
        cam.answer_once = upright_consent(seen)
        with pytest.raises(safety.Refused, match=why):
            cam.press("enter")
        assert seen == [], kind
    cam = camera(tmp_path, monkeypatch, "unknown", "Focus Area Spot: M", "")
    cam.answer_once = upright_consent()
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("c4", allow=frozenset({"c4"}))


# ---------------------------------------------------------------- the fourth review: first-time screens, --info-ok for tables

FIRST_TIME = ("In the next setting screen, you can check the function assigned to a specific button by pressing that "
              "button on the device. Don't show this again. OK")


def test_the_camera_judges_a_first_time_screen_as_a_notice(tmp_path, monkeypatch):
    """A first-time screen reads as no known kind (no notice's frame lines) with a "Don't show this again." box: the
    camera judges it as a notice (safety.first_time_screen), so its OK goes by a way past alone (a refused MENU, a
    lone OK; --info-ok), and a screen of no known kind without the box is still refused as one."""
    assert safety.first_time_screen("unknown", FIRST_TIME)
    assert not safety.first_time_screen("unknown", FIRST_TIME.replace("Don't show this again. ", ""))
    assert not safety.first_time_screen("list", FIRST_TIME)
    cam = camera(tmp_path, monkeypatch, "unknown", FIRST_TIME, "OK")
    with pytest.raises(Sent):
        live.leave_notice(cam)                     # MENU refused, its OK alone: the a1 II's way out of it
    cam = camera(tmp_path, monkeypatch, "unknown", FIRST_TIME, "OK")
    with pytest.raises(safety.Refused, match="is a notice"):
        cam.press("enter")                         # no way past
    cam = camera(tmp_path, monkeypatch, "unknown", FIRST_TIME, "OK")
    with pytest.raises(Sent):
        cam.press("enter", notice_ok="Custom Key/Dial Set.")
    cam = camera(tmp_path, monkeypatch, "unknown", FIRST_TIME, "Don't show this again.")
    with pytest.raises(safety.Refused, match="not OK"):
        cam.press("enter", notice_ok="Custom Key/Dial Set.")      # the box lit: never Enter on it
    cam = camera(tmp_path, monkeypatch, "unknown", FIRST_TIME.replace("Don't show this again. ", ""), "OK")
    with pytest.raises(safety.Refused, match="not that notice"):
        live.leave_notice(cam)


def table_job():
    return {"path": ["Custom Key/Dial Set."], "labels": ["AF-ON", "AEL hold"], "opens": "picker", "screen": "keyset",
            "option": "AF-ON Button", "cell": [0, "key", 0]}


class TableCam:
    """A camera on the Custom Key row: Right shows `after` (a first-time screen read as "unknown"), and the screen
    behind it once notice_before passed it."""
    def __init__(self, tmp_path, after="unknown"):
        self.kind, self.after, self.keys = "menu", after, []
        self.frame = SimpleNamespace(image=None, path=tmp_path / "00001_menu.png")

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def press(self, key, **kw):
        self.keys.append(key)
        if key == "right":
            self.kind = self.after


def test_a_table_job_passes_its_rows_first_time_screen_or_says_the_info_ok_to_add(tmp_path, monkeypatch):
    """proving.tables.prove_table_row: Right on the row (Custom Key/Dial Set.) opening a first-time screen hands it to
    notice_before with the row's path and the lit bar read before Right; one not passed fails the cell with the
    --info-ok that would name it; one passed goes on into the keys."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving import tables
    from proving.base import Failed
    seen = []
    monkeypatch.setattr(tables.camset, "read", lambda p: {})
    monkeypatch.setattr(tables, "place", lambda cam: "row")
    monkeypatch.setattr(tables, "lit_text", lambda image, path: "Custom Key/Dial Set.")
    hint = '--info-ok "Custom Key/Dial Set.=In the next setting screen, you can check ..."'

    def refused(cam, row, lit, words=True):
        seen.append((row, lit))
        return {"refused": f"the notice (00002_right.png) took MENU, which cancels it: add {hint}"}
    monkeypatch.setattr(tables, "notice_before", refused)
    with pytest.raises(Failed, match="not passed: the notice .* took MENU") as e:
        tables.prove_table_row(TableCam(tmp_path), None, None, table_job(), tmp_path / "base.DAT", None)
    assert hint in str(e.value) and seen == [("Custom Key/Dial Set.", "Custom Key/Dial Set.")]

    class Inside(Exception):
        pass

    def passed(cam, row, lit, words=True):
        cam.kind = "keyset"
        return {"row": row, "frame": "00002_right.png", "by": "--info-ok"}
    monkeypatch.setattr(tables, "notice_before", passed)
    monkeypatch.setattr(tables, "to_key", lambda cam, cell: (_ for _ in ()).throw(Inside()))
    with pytest.raises(Inside):
        tables.prove_table_row(TableCam(tmp_path), None, None, table_job(), tmp_path / "base.DAT", None)


def test_info_ok_names_a_table_row_for_prove_run_and_table_walk(tmp_path, monkeypatch):
    """--info-ok is taken for a table job's row (a checklist's as before; any other kind refused), named by --rows as the
    row or as one of its cells ("<row> / <cell>"); table_walk takes it too, and its Right on the row passes the first-time
    screen or stops saying what to add."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import prove_run
    import runner
    import table_walk
    from proving.base import Failed
    named = {"Custom Key/Dial Set.": "in the next setting screen"}
    prove_run.info_ok_jobs_or_exit([{"path": ["Custom Key/Dial Set."], "kind": "table"}], named)
    prove_run.info_ok_jobs_or_exit([{"path": ["Custom Key/Dial Set."], "kind": "checklist"}], named)
    with pytest.raises(SystemExit, match="a checklist or a table only"):
        prove_run.info_ok_jobs_or_exit([{"path": ["Custom Key/Dial Set."], "kind": "list"}], named)
    value = f"Custom Key/Dial Set.={FIRST_TIME.split(' Don')[0]}"
    for rows in (["Custom Key/Dial Set."], ["Custom Key/Dial Set. / AF-ON Button"]):
        assert runner.info_ok_or_exit([value], rows, labels={"Custom Key/Dial Set."})
    with pytest.raises(SystemExit, match="not one of the rows"):
        runner.info_ok_or_exit([value], ["Drive Mode"], labels={"Custom Key/Dial Set."})
    cam = TableCam(tmp_path)
    got = []
    monkeypatch.setattr(table_walk, "lit_text", lambda image, path: "Custom Key/Dial Set.")
    monkeypatch.setattr(table_walk.screens, "notice_before",
                        lambda c, row, lit: got.append((row, lit)) or {"refused": "add --info-ok \"Custom Key/Dial Set.=...\""})
    with pytest.raises(Failed, match="not passed: add --info-ok"):
        table_walk.right_on_row(cam, "Custom Key/Dial Set. (movie)")
    assert got == [("Custom Key/Dial Set.", "Custom Key/Dial Set.")] and cam.keys == ["right"]
    monkeypatch.setattr(table_walk.screens, "notice_before", lambda c, row, lit: None)
    table_walk.right_on_row(cam, "Custom Key/Dial Set.")
    table_walk.right_on_row(cam, "")
    assert cam.keys == ["right"] * 3


# ---------------------------------------------------------------- the fourth review: the link's drop, raced

def test_a_drop_learnt_while_an_earlier_ok_was_on_its_way_stays(tmp_path, monkeypatch):
    """Link.gone: the SDK's "disconnected" landing while a reply made before the drop is on its way (its "ok" read
    after the event) clears nothing; a request sent after the drop, answered, does; open() starts with nothing of the
    last session's drop."""
    with fake_link(tmp_path / "race", monkeypatch) as lk:
        real = lk._reply

        def late(timeout, want=None):
            r = real(timeout, want)
            lk._event(json.dumps({"event": "disconnected", "code": 33282}))    # learnt as that "ok" comes in
            return r
        lk._reply = late
        assert lk.call("ping")["ok"]
        assert lk.gone() == "the SDK reported the camera disconnected"
        lk._reply = real
        assert lk.call("ping")["ok"] and lk.gone() == ""     # sent after the drop and answered: the session is there
    fresh = fake_link(tmp_path / "fresh", monkeypatch)
    fresh.disconnected, fresh._dropped_after = "camlink answers that the camera is disconnected", 99
    with fresh:                                              # open(): a new session, nothing of an earlier drop
        assert fresh.gone() == "" and fresh._dropped_after == -1


def test_the_hold_pings_the_link_on_every_look(tmp_path, monkeypatch):
    """runner.hold_for_owner sends a ping (a read) before each look, so a camera whose session dropped says so even on
    HDMI eyes, where nothing else asks the link."""
    import runner
    pings = []
    run = Run("kit2_end", root=tmp_path / "runs" / "end-test")
    looks = iter([(None, "asks"), (None, "asks"), ("shooting", "")])
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: next(looks))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    link = SimpleNamespace(run=run, gone=lambda: "", call=lambda cmd, timeout=30.0: pings.append((cmd, timeout)))
    with pytest.raises(SystemExit):
        runner.hold_for_owner(link, "eyes", tmp_path / "start.DAT", "it asks")
    assert pings == [("ping", 5)] * 3


# ---------------------------------------------------------------- a notice's words, withheld where a run promises it

FIRST_TIME_LINES = [ocr.Line(text="In the next setting screen, you can check", conf=0.9, x=53, y=113, w=535, h=38),
                    ocr.Line(text="the function assigned to a specific button", conf=0.9, x=52, y=161, w=536, h=32),
                    ocr.Line(text="by pressing that button on the device.", conf=0.9, x=74, y=207, w=490, h=34),
                    ocr.Line(text="Don't show this again.", conf=0.9, x=175, y=352, w=286, h=33),
                    ocr.Line(text="OK", conf=0.9, x=297, y=414, w=46, h=37)]


class NoteCam:
    """A first-time screen (read as no known kind) whose MENU the camera takes; every press kept; a run of its own."""
    def __init__(self, tmp_path, name, **kw):
        self.keys, self.run = [], Run(name, root=tmp_path)
        self.frame = SimpleNamespace(path=tmp_path / "00002_right.png", image=None)
        for k, v in kw.items():
            setattr(self, k, v)

    def read(self):
        return SimpleNamespace(kind="unknown")

    def press(self, key, **kw):
        self.keys.append(key)


def test_pass_note_withholds_a_notices_words_where_the_run_asks(tmp_path, monkeypatch):
    """pass_note with words=False (afreg_run's and framepos_run's setup, a --network prove run; decision 16: a notice can
    name another setting's value): its text is in no message, only in the run's events.jsonl ("notice_not_passed", with
    the row and the frame; on a --network or --owner run only what safety.notice_kept keeps), and the message names the
    frame and the row and says where the text is, so the owner can still build the --info-ok. words=True as before."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving import screens
    monkeypatch.setattr(screens.ocr, "read", lambda paths, eng=None: {p: list(FIRST_TIME_LINES) for p in paths})
    monkeypatch.setattr(screens, "notice_lit", lambda cam: "OK" if "down" in cam.keys else "Don't show this again.")
    monkeypatch.setattr(screens, "INFO_OK", {})
    row = "Custom Key/Dial Set."
    cam = NoteCam(tmp_path / "a", "kit2_afreg")
    refused = screens.pass_note(cam, row, row, words=False)["refused"]
    assert cam.keys == ["down", "menu"]
    assert "00002_right.png" in refused and row in refused and "events.jsonl" in refused, refused
    assert "setting screen" not in refused and "pressing" not in refused, refused
    [kept] = [e for e in events(cam) if e["kind"] == "notice_not_passed"]
    assert kept["row"] == row and kept["frame"] == "00002_right.png" and kept["notice"].startswith("In the next setting")
    cam = NoteCam(tmp_path / "b", "kit2_pass2", network={"Bluetooth Function": "2026-11-13"})
    screens.pass_note(cam, row, row, words=False)
    [kept] = [e for e in events(cam) if e["kind"] == "notice_not_passed"]
    assert kept["notice"] == safety.notice_kept(" ".join(ln.text for ln in FIRST_TIME_LINES[:3]))
    assert "setting screen" not in kept["notice"]              # no shape the kit knows: nothing of it kept
    cam = NoteCam(tmp_path / "c", "kit2_tables")
    refused = screens.pass_note(cam, row, row)["refused"]
    assert f'--info-ok "{row}=In the next setting screen' in refused
    assert [e["notice"][:27] for e in events(cam) if e["kind"] == "notice_not_passed"] == ["In the next setting screen,"]


def test_afreg_and_framepos_pass_the_dial_note_with_its_words_withheld(tmp_path, monkeypatch):
    """afreg_run.focus_dial_by_menu (framepos_run's dial step too) hands Mode Dial Control Set's note to pass_note with
    words=False, and its failure names the frame alone, as its docstring promises."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provers"))
    import afreg_run
    import mode_switch
    from camkit import live as L
    from proving import screens
    from proving.base import Failed
    seen = []
    monkeypatch.setattr(afreg_run, "dial_cell", lambda dial: [1, 2])
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, row: None)
    monkeypatch.setattr(mode_switch, "text", lambda cam: "Set the Mode Dial to change the setting. OK")
    monkeypatch.setattr(L, "lit_text", lambda image, path: afreg_run.DIAL_ROW)
    monkeypatch.setattr(screens, "pass_note", lambda cam, row, lit, **kw: seen.append(kw) or {"refused": "not passed"})
    cam = NoteCam(tmp_path, "kit2_afreg")
    cam.read = lambda: SimpleNamespace(kind="notice")
    with pytest.raises(Failed) as e:
        afreg_run.focus_dial_by_menu(cam, [], {})
    assert seen == [{"words": False}] and "Mode Dial to change" not in str(e.value)


def test_a_table_job_withholds_the_words_on_a_network_run(tmp_path, monkeypatch):
    """prove_table_row: notice_before with words=not proving.jobs.NETWORK, so a --network prove run prints no screen's
    text there."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving import jobs, tables
    from proving.base import Failed
    seen = []
    monkeypatch.setattr(tables.camset, "read", lambda p: {})
    monkeypatch.setattr(tables, "place", lambda cam: "row")
    monkeypatch.setattr(tables, "lit_text", lambda image, path: "Custom Key/Dial Set.")
    monkeypatch.setattr(tables, "notice_before", lambda cam, row, lit, words=True: seen.append(words) or {"refused": "x"})
    for network, words in (({}, True), ({"Bluetooth Function": "2026-11-13"}, False)):
        monkeypatch.setattr(jobs, "NETWORK", network)
        with pytest.raises(Failed):
            tables.prove_table_row(TableCam(tmp_path), None, None, table_job(), tmp_path / "base.DAT", None)
        assert seen[-1] is words


# ---------------------------------------------------------------- the camera session: prose is no second button

# the a1 II's Custom Key/Dial Set. first-time screen after Down (kit2_c1cam_ckey_info's 00005_down.png), as OCR read it,
# its lit OK's box as camkit.live finds it
CKEY_LINES = [("In the next setting screen, you can check", 53, 113, 535, 38),
              ("the function assigned to a specific button", 52, 161, 536, 33),
              ("by pressing that button on the device.", 74, 207, 490, 34),
              ("Don't show this again", 175, 351, 285, 35), ("OK", 297, 413, 46, 38)]
CKEY_BOX = (60, 404, 580, 462)


def test_a_sentence_holding_can_c_is_no_second_button():
    """The camera session's false refusal (2026-11-15): "you can check" read run together ("youcancheck") holds "canc",
    and lone_ok took that line for a Cancel button, so the first-time screen had no way past at all. A second button is
    a line of its own (safety.button_line): the screen, its text and its OK, passes now, and the camera's whole check
    with --info-ok as its way past goes."""
    assert safety.lone_ok("OK", CKEY_LINES, CKEY_BOX) == ""
    text = " ".join(t for t, *_ in CKEY_LINES)
    assert safety.first_time_screen("unknown", text)
    assert safety.enter_refused("notice", text, "OK", text, "--info-ok Custom Key/Dial Set.", "") == ""
    for prose in ("Limits the ISO values you can choose to a", "Only the Custom Looks can change it; each",
                  "you can check", "You can set different settings for still", "image mode and movie mode in the next",
                  "The setting set for  is independent.", "by pressing that button on the device."):
        assert not safety.button_line(prose), prose
    # prose that holds a Cancel as OCR may give it fails closed (CANCEL_SEEN), as does one ending in a button's word
    for closed in ("The recording was cancelled by the camera.", "you can celebrate", "the level you set"):
        assert safety.button_line(closed), closed


def test_a_named_notices_other_lines_name_a_button_by_its_whole_word():
    """proving.screens.NOT_BESIDE_OK (pass_named_notice): a button's word counts whole ("No", "Back", "Start"), never as
    the start of prose ("not available", "starts", "background"); an action's word counts inflected too ("deleted")."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving.screens import NOT_BESIDE_OK
    for said in ("No", "Back", "Start", "Close", "Enter", "Yes", "deleted", "Executed.", "x Cancel", "overwritten"):
        assert NOT_BESIDE_OK.search(said.lower()), said
    for prose in ("this operation or setting not available as follows", "the movie starts at once", "background",
                  "a normal noise level", "enters the state"):
        assert not NOT_BESIDE_OK.search(prose), prose


@pytest.mark.parametrize("line", [("Cancel", 290, 280, 60, 30), ("Cance1", 290, 280, 60, 30), ("Can cel", 280, 280, 80, 30),
                                  ("x Cance1", 100, 280, 200, 30), ("MENU Cancel", 100, 280, 200, 30),
                                  ("Cancel>", 290, 280, 60, 30), ("Execute", 290, 280, 60, 30), ("Yes", 290, 280, 60, 30),
                                  ("No", 290, 280, 40, 30), ("Delete all data Cancel", 60, 280, 500, 30),
                                  ("Press MENU to cancel this operation", 53, 113, 535, 38),
                                  # the review of 84a00fa: a Cancel as OCR gives it, run together or not, in a longer line
                                  ("Back to the menu Cance1", 60, 280, 500, 30), ("Return to the menu Canc el", 60, 280, 500, 30),
                                  ("Use this setting now Can cel", 60, 280, 500, 30), ("Cancelar y volver atras", 60, 280, 500, 30),
                                  ("Back to the menu Cance!", 60, 280, 500, 30), ("Back to the menu Cancei", 60, 280, 500, 30),
                                  # the words the lists never had, alone
                                  *((w, 290, 280, 80, 30) for w in ("Return", "Stop", "Start", "Resume", "Retry", "Later",
                                                                   "Abort", "Quit", "Not now")),
                                  # a button OCR merged onto the right end of a prose line: its last word, or two
                                  ("Delete all data Yes", 60, 280, 500, 30), ("Proceed with this Execute No", 60, 280, 500, 30),
                                  ("Try again in a moment Not now", 60, 280, 500, 30)])
def test_a_second_button_above_a_lone_ok_still_refuses(line):
    """The reviewers' cases stay refused: a button's word alone (the lists' new words too: Return, Stop, Start, Resume,
    Retry, Later, Abort, Quit, Not now), or as the line's last word or two (merged onto prose), and a Cancel as OCR may
    give it anywhere in any reading ("Cance1", "Can cel", "Cancelar"); beside or below the OK, the layout refuses
    whatever the words."""
    box, ok = (200, 340, 440, 395), ("OK", 300, 352, 40, 30)
    assert "reads as a button" in safety.lone_ok("OK", [line, ok], box), line
    assert "beside or below" in safety.lone_ok("OK", [("Something", 460, 352, 60, 30), ok], box)


def test_a_cancel_split_across_two_lines_above_the_ok_refuses():
    """lone_ok reads the lines above its lit OK joined too, so a Cancel OCR split across two lines ("...Can" / "cel") is
    caught; the a1 II's Custom Key screen, its lines joined, holds none ("...youcancheck...")."""
    box, ok = (200, 340, 440, 395), ("OK", 300, 352, 40, 30)
    split = [("Back to the menu Can", 60, 240, 500, 30), ("cel", 60, 280, 60, 30), ok]
    assert "joined, as a Cancel" in safety.lone_ok("OK", split, box)
    assert safety.lone_ok("OK", CKEY_LINES, CKEY_BOX) == ""


def test_a_named_notices_other_lines_name_the_new_button_words_whole():
    """NOT_BESIDE_OK takes the words the lists never had, whole: Return, Stop, Resume, Retry, Later, Abort, Quit, Not
    now; never as the start of prose ("returned", "stopped", "lateral")."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from proving.screens import NOT_BESIDE_OK
    for said in ("return", "stop", "resume", "retry", "later", "abort", "quit", "not now", "try again later"):
        assert NOT_BESIDE_OK.search(said), said
    for prose in ("the file was returned", "recording stopped", "a lateral move", "resumed earlier"):
        assert not NOT_BESIDE_OK.search(prose), prose


# ---------------------------------------------------------------- a Custom box's size editor, its OK (2026-11-17)

# Custom 1's size editor as OCR reads it (kit2_freesize's 00225_c4.png and 00394_c4.png, HDMI): its title, nothing else
# above the footer but the dials' icons, and the footer's three buttons, Reset on the trash button
EDITOR_TEXTS = ("Custom 1", "Custom 1", "iReset MENU Cancel OK")
EDITOR_NAME = "Custom 1's size editor: OK keeps its size (Focus Area's SET, the owner's word)"


def editor_camera(tmp_path, monkeypatch, kind="unknown", texts=EDITOR_TEXTS, box="Custom 1"):
    """A camera on Custom 1's size editor (a screen of no known kind) whose title, text above the footer and footer read
    `texts`, its Enter carrying the size editor's consent for `box`."""
    cam = camera(tmp_path, monkeypatch, kind, " ".join(texts[1:]), "")
    monkeypatch.setattr(live, "editor_texts", lambda c: texts)
    cam.answer_once = live.BoxEditor(EDITOR_NAME, box)
    return cam


def test_a_size_editors_ok_goes_by_its_consent_judged_on_the_editors_own_shape(tmp_path, monkeypatch):
    """A Custom box's size editor reads as no known kind, and its footer's Reset is a confirmation's word, so neither the
    shape check nor a named consent lets its OK go: the editor's consent (BoxEditor) judges it on the editor's own shape,
    its title the box's, nothing above the footer but the title, the footer the editor's three buttons, and the
    confirmation words on what stands above the footer; logged with the consent's words, spent by its press."""
    cam = camera(tmp_path, monkeypatch, "unknown", "Custom 1 iReset MENU Cancel OK", "")
    cam.answer_once = "--allow \"Focus Area's SET\""
    with pytest.raises(safety.Refused, match="reads as a confirmation"):
        cam.press("enter")                                  # a named consent keeps the word list: Reset refuses
    cam = editor_camera(tmp_path, monkeypatch)
    with pytest.raises(Sent):
        cam.press("enter")
    assert [e["by"] for e in events(cam) if e["kind"] == "enter_passed"] == [EDITOR_NAME]
    assert cam.answer_once is None
    for texts in (("Custom 1", "Custom 1 L", "Reset MEN Cancel •OK"), ("S Custom 1", "S Custom 1", "Reset MENU Cancel OK")):
        cam = editor_camera(tmp_path, monkeypatch, texts=texts)
        with pytest.raises(Sent):
            cam.press("enter")                              # an icon's glyph, a key's word cut short: still the editor


@pytest.mark.parametrize("texts,why", [
    (("Custom 2", "Custom 2", "Reset MENU Cancel OK"), "is not Custom 1's"),
    (("", "", "Reset MENU Cancel OK"), "is not Custom 1's"),
    (("Custom 1", "Custom 1 Clear the box?", "Reset MENU Cancel OK"), "question mark"),
    (("Custom 1", "Custom 1 Format the memory card", "Reset MENU Cancel OK"), "more than its title"),
    (("Custom 1", "Custom 1", "MENU Cancel OK"), "lacks the editor's 'reset'"),
    (("Custom 1", "Custom 1", "Reset MENU OK"), "lacks the editor's 'cancel'"),
    (("Custom 1", "Custom 1", "Reset MENU Cancel Execute OK"), "'execute'")])
def test_a_size_editors_consent_refuses_any_screen_not_shaped_as_that_boxs_editor(tmp_path, monkeypatch, texts, why):
    """Another box's editor, a title that cannot be read, a question mark, words above the footer besides the title, a
    footer short of Reset, Cancel or OK or holding any other button's word: no OK."""
    cam = editor_camera(tmp_path, monkeypatch, texts=texts)
    with pytest.raises(safety.Refused, match=why):
        cam.press("enter")


def test_a_size_editors_consent_answers_no_other_screen_nor_key(tmp_path, monkeypatch):
    """On a notice, a dialog or a list the editor's consent lifts nothing and the editor's texts are never read; the
    trash button (the editor's Reset) meets the shape check as ever, and the link's C4 guard besides."""
    read = []
    for kind, text, lit, why in (("notice", NOT_AVAILABLE, "OK", "is a notice"),
                                 ("dialog", "Delete this image? OK Cancel", "OK", "question mark"),
                                 ("list", "", "", "nothing on the list screen")):
        cam = camera(tmp_path, monkeypatch, kind, text, lit)
        monkeypatch.setattr(live, "editor_texts", lambda c: read.append(1) or EDITOR_TEXTS)
        cam.answer_once = live.BoxEditor(EDITOR_NAME, "Custom 1")
        with pytest.raises(safety.Refused, match=why):
            cam.press("enter")
    assert read == []
    cam = editor_camera(tmp_path, monkeypatch)
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("c4", allow=frozenset({"c4"}))


# ---------------------------------------------------------------- a Custom box's size editor, its Reset (2026-11-17)

RESET_NAME = "Custom 1's size editor: Reset puts the default size back (Custom box Reset, the owner's word, 2026-11-17)"


def reset_camera(tmp_path, monkeypatch, kind="unknown", texts=EDITOR_TEXTS, box="Custom 1"):
    """editor_camera, its C4 carrying the size editor's Reset consent for `box` (BoxReset)."""
    cam = editor_camera(tmp_path, monkeypatch, kind, texts, box)
    cam.answer_once = live.BoxReset(RESET_NAME, box)
    return cam


def test_the_size_editors_reset_goes_only_under_its_consent_on_that_editor(tmp_path, monkeypatch):
    """C4 on a Custom box's size editor (no known kind) is refused, as decision 7 has it: the link takes C4 on menu,
    option and panel screens alone. Under boxsize_run's Reset consent (BoxReset), the screen judged as that box's own
    editor (box_editor_refused: its title, its footer's three buttons, no question mark, nothing above the footer but the
    title), the camera hands the link the size editor's own kind for that one press (safety.C4_BOX_EDITOR, which decision
    7's list names), logged with the consent's words; the consent is spent by it."""
    cam = editor_camera(tmp_path, monkeypatch)
    cam.answer_once = None
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("c4", allow=frozenset({"c4"}))
    cam = reset_camera(tmp_path, monkeypatch)
    with pytest.raises(Sent) as sent:
        cam.press("c4", allow=frozenset({"c4"}))
    assert sent.value.args[0]["screen"] == safety.C4_BOX_EDITOR == "boxeditor"
    assert safety.c4_refused(safety.C4_BOX_EDITOR) == "" and safety.c4_refused("unknown")
    assert [e["by"] for e in events(cam) if e["kind"] == "enter_passed"] == [RESET_NAME]
    assert cam.answer_once is None


@pytest.mark.parametrize("texts,why", [
    (("Custom 2", "Custom 2", "Reset MENU Cancel OK"), "is not Custom 1's"),
    (("Custom 1", "Custom 1 Clear the box?", "Reset MENU Cancel OK"), "question mark"),
    (("Custom 1", "Custom 1 Format the memory card", "Reset MENU Cancel OK"), "more than its title"),
    (("Custom 1", "Custom 1", "MENU Cancel OK"), "lacks the editor's 'reset'"),
    (("Custom 1", "Custom 1", "Delete MENU Cancel OK"), "'delete'")])
def test_the_size_editors_reset_is_refused_on_any_screen_not_shaped_as_that_boxs_editor(tmp_path, monkeypatch, texts,
                                                                                       why):
    """Another box's editor, a question mark, words above the footer besides the title, a footer without Reset or with
    another button's word (a Delete on the trash button): no C4."""
    cam = reset_camera(tmp_path, monkeypatch, texts=texts)
    with pytest.raises(safety.Refused, match=why):
        cam.press("c4", allow=frozenset({"c4"}))


def test_the_size_editors_reset_consent_lifts_nothing_anywhere_else(tmp_path, monkeypatch):
    """The Reset consent answers C4 alone, on a screen of no known kind alone: on a dialog or a list the press is judged
    as it would be without it (the link gets that screen's own kind, never the editor's), on a notice it is refused as
    ever, and neither Enter nor the Delete key on the editor goes by it; the editor's texts are read for none of them."""
    read = []
    for kind, text in (("dialog", "Focus Area Custom 1 SET C1 C2 C3"), ("list", "Drive Mode Single Shooting")):
        cam = camera(tmp_path, monkeypatch, kind, text, "")
        monkeypatch.setattr(live, "editor_texts", lambda c: read.append(1) or EDITOR_TEXTS)
        cam.answer_once = live.BoxReset(RESET_NAME, "Custom 1")
        with pytest.raises(Sent) as sent:
            cam.press("c4", allow=frozenset({"c4"}))
        assert sent.value.args[0]["screen"].kind == kind
    cam = camera(tmp_path, monkeypatch, "notice", NOT_AVAILABLE, "OK")
    monkeypatch.setattr(live, "editor_texts", lambda c: read.append(1) or EDITOR_TEXTS)
    cam.answer_once = live.BoxReset(RESET_NAME, "Custom 1")
    with pytest.raises(safety.Refused, match="notice"):
        cam.press("c4", allow=frozenset({"c4"}))
    for key in ("enter", "delete"):
        cam = reset_camera(tmp_path, monkeypatch)
        monkeypatch.setattr(live, "editor_texts", lambda c: read.append(1) or EDITOR_TEXTS)
        with pytest.raises(safety.Refused, match="reads as 'unknown'"):
            cam.press(key, allow=frozenset({"delete"}))
    assert read == []


def test_only_boxsize_run_gives_the_reset_consent_and_only_the_camera_names_the_editors_kind():
    """The size editor's Reset is boxsize_run's alone: no other program of the kit builds the consent, and no module
    but camkit.safety (its list) and camkit.live (which hands it to the link under the consent) names the editor's kind."""
    import re
    kit = Path(__file__).resolve().parents[1]
    for f in sorted(kit.rglob("*.py")):
        if "tests" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(kit).as_posix()
        if re.search(r"\bBoxReset\(", text):
            assert rel in ("camkit/live.py", "provers/boxsize_run.py"), rel
        if re.search(r"C4_BOX_EDITOR|[\"']boxeditor[\"']", text):
            assert rel in ("camkit/safety.py", "camkit/live.py"), rel


# ---------------------------------------------------------------- a row's own two-box screen, its OK (2026-11-17)

# S&Q Frame Rate Settings under XAVC HS 4K as OCR reads it (kit2_pass2 240079_down.png, HDMI): the breadcrumb, each box's
# name above its box (its icon read as letters), the two values, the screen's own three lines under the boxes, and the
# footer (the trash icon read as nothing, its help glyph's "?", OK)
SQ_LINES = [("Shooting > Image Qua... > S&0 Frame Rate Settings", 0, 3, 516, 33), ("Sad Rec Frame Rate", 115, 65, 218, 28),
            ("S&Q Frame Rate", 389, 67, 167, 28), ("24p", 191, 189, 53, 38), ("120fps", 424, 184, 98, 46),
            ("x5 Slow Motion", 65, 317, 150, 21),
            ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
            ("0 h 00 min 01 s", 67, 383, 146, 25), ("?", 509, 441, 16, 24), ("• OK", 563, 437, 62, 28)]
# Time-lapse Frame Rate Settings (kit2_pass2 122685_down.png): its second box is Interval Time, its footer OK alone
TL_LINES = [("Shooting > Image Qua... > Frame Rate Settings", 0, 1, 518, 36), ("t Rec Frame Rate", 127, 65, 206, 28),
            ("ü Interval Time", 383, 65, 184, 30), ("30р", 191, 189, 56, 37), ("1 s", 455, 189, 40, 30),
            ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
            ("0 h 02 min 30 s", 65, 381, 150, 26), ("OK", 583, 437, 44, 30)]
FRAME_BOXES = ((100, 178, 339, 233), (356, 178, 595, 233))      # boxes_run.LAYOUTS["framerate"]
BOXES_NAME = "Frame Rate Settings's own two-box screen: OK leaves it on the values its boxes show"


def ocr_lines(rows) -> list:
    return [ocr.Line(t, 1.0, x, y, w, h) for t, x, y, w, h in rows]


def boxes_camera(tmp_path, monkeypatch, rows=SQ_LINES, kind="unknown", names=("Rec Frame Rate", "Frame Rate"),
                 row="Frame Rate Settings"):
    """A camera on a row's two-box screen (no known kind) whose OCR lines are `rows`, its Enter carrying that screen's
    consent (TwoBoxes) for `row` and the boxes `names`."""
    text = " ".join(r[0] for r in rows)
    cam = camera(tmp_path, monkeypatch, kind, text, "", body=" ".join(r[0] for r in rows if r[2] + r[4] / 2 < 415))
    monkeypatch.setattr(live, "boxes_lines", lambda c: ocr_lines(rows))
    cam.answer_once = live.TwoBoxes(BOXES_NAME, row, tuple(names), FRAME_BOXES)
    return cam


def test_a_two_box_screens_ok_goes_by_its_consent_judged_on_the_screens_own_shape(tmp_path, monkeypatch):
    """S&Q Frame Rate Settings reads as no known kind, so its OK was refused (kit2_pass2 240079, 2026-11-17): the row's
    two-box consent (TwoBoxes) lets it go judged on the screen's own shape, the three lines under the boxes its own
    explanation; logged with the consent's words and spent by its press. The Time-lapse screen, its second box Interval
    Time and its footer OK alone, and readings that glue the icon on or lose the help glyph pass alike."""
    cam = boxes_camera(tmp_path, monkeypatch)
    cam.answer_once = None
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("enter")                                  # the guard as it stopped the run
    cam = boxes_camera(tmp_path, monkeypatch)
    with pytest.raises(Sent):
        cam.press("enter")
    assert [e["by"] for e in events(cam) if e["kind"] == "enter_passed"] == [BOXES_NAME]
    assert cam.answer_once is None
    glued = [("Shooting > Image Qua... > S&0Frame Rate Settings", *SQ_LINES[0][1:])] + SQ_LINES[1:8] + [SQ_LINES[9]]
    for rows, names in ((TL_LINES, ("Rec Frame Rate", "Interval Time")), (glued, ("Rec Frame Rate", "Frame Rate"))):
        cam = boxes_camera(tmp_path, monkeypatch, rows, names=names)
        with pytest.raises(Sent):
            cam.press("enter")


def _with(rows, i, text):
    return [*rows[:i], (text, *rows[i][1:]), *rows[i + 1:]]


@pytest.mark.parametrize("rows,why", [
    (_with(SQ_LINES, 6, "Shooting time required for 5-second movie recording?"), "question mark"),
    (_with(SQ_LINES, 5, "x5 Slow Motion?"), "question mark"),
    (_with(SQ_LINES, 6, "Delete all movies on the card"), "reads as a confirmation"),
    (_with(SQ_LINES, 7, "Format the memory card"), "reads as a confirmation"),
    (_with(SQ_LINES, 0, "Shooting > Image Qua... > S&Q Settings"), "does not end with Frame Rate Settings"),
    (_with(SQ_LINES, 2, "S&Q Interval Time"), "is not Frame Rate"),
    (_with(SQ_LINES, 1, ""), "is not Rec Frame Rate"),
    (_with(SQ_LINES, 3, "-"), "reads no value"),
    (_with(SQ_LINES, 9, "MENU Cancel • OK"), "'menu'"),
    (_with(SQ_LINES, 9, "Execute"), "'execute'"),
    (SQ_LINES[:9], "offers no OK"),
    (SQ_LINES + [("Recording will begin", 200, 130, 240, 28)], "stands where its screen draws none")])
def test_a_two_box_screens_consent_refuses_any_screen_not_shaped_as_that_rows(tmp_path, monkeypatch, rows, why):
    """A question mark or a confirmation's word in the lines under the boxes (or anywhere above the footer), a title that
    does not end with the row's name, a box whose name above it is another's or cannot be read, a box that reads no
    value, a footer with any word but OK or with no OK, a line where the screen draws none: no OK."""
    cam = boxes_camera(tmp_path, monkeypatch, rows)
    with pytest.raises(safety.Refused, match=why):
        cam.press("enter")


def test_a_two_box_screens_consent_answers_no_other_screen_nor_key(tmp_path, monkeypatch):
    """On a notice, a dialog or a list the two-box consent lifts nothing and the screen's lines are never read for it; the
    trash button on the two-box screen meets the shape check as ever."""
    read = []
    for kind, text, lit, why in (("notice", NOT_AVAILABLE, "OK", "is a notice"),
                                 ("dialog", "Delete this image? OK Cancel", "OK", "question mark"),
                                 ("list", "", "", "nothing on the list screen")):
        cam = camera(tmp_path, monkeypatch, kind, text, lit)
        monkeypatch.setattr(live, "boxes_lines", lambda c: read.append(1) or ocr_lines(SQ_LINES))
        cam.answer_once = live.TwoBoxes(BOXES_NAME, "Frame Rate Settings", ("Rec Frame Rate", "Frame Rate"), FRAME_BOXES)
        with pytest.raises(safety.Refused, match=why):
            cam.press("enter")
    assert read == []
    cam = boxes_camera(tmp_path, monkeypatch)
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("c4", allow=frozenset({"c4"}))


def test_only_boxes_run_gives_the_two_box_consent():
    """The two-box screen's consent is boxes_run's alone: no other program of the kit builds it."""
    import re
    kit = Path(__file__).resolve().parents[1]
    for f in sorted(kit.rglob("*.py")):
        if "tests" not in f.parts and re.search(r"\bTwoBoxes\(", f.read_text(encoding="utf-8")):
            assert f.relative_to(kit).as_posix() in ("camkit/live.py", "provers/boxes_run.py"), f

