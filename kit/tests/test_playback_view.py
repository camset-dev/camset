"""The camera's playback view is not the shooting screen (docs/decisions/0021, 2026-11-15): the first look lap over the
Playback tab (runs/ILCE-1M2_fw4.00/kit2_a1fin_look_playback) took the playback view a Playback row opens for the
shooting screen, asked for a download there, which the camera refused, and exited 5. The camera's word
(Link.in_playback), the one place a screen read as the shooting screen is told from that view
(camkit.session.playback_kind, in camkit.live's readings, wait_for, proving.nav.to_shooting and the run's end), the one
press that leaves it (proving.nav.leave_playback, Link.press_playback) and where it is used (the first open's check,
the run's end, a look lap's row), on the stand-in camlink and the existing tests' fakes."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import crawl, first_open, live, paths, safety, screen, session  # noqa: E402
from camkit.link import LinkError, StopRequested  # noqa: E402
from camkit.runs import restore_pending  # noqa: E402
from exit_status import EXIT_RESTORE_BY_HAND  # noqa: E402
from test_first_open import first_opens  # noqa: E402
from test_guards import fake_link, sent_lines  # noqa: E402

PLAYBACK, RECORD = 2, 1                 # CameraOperatingMode as the SDK numbers it (camkit.link.PLAYBACK_MODE)
LISTED = json.dumps([{"name": "CameraOperatingMode"}])
BRIGHT = np.full((480, 640, 3), 100, np.uint8)      # a drawn frame: never black, so no OSD picture is asked


def mode_file(tmp_path, mode) -> Path:
    """The stand-in camlink's answer to get CameraOperatingMode, read afresh on every get ($FAKE_CAMLINK_GET_FILE):
    `mode`, or none at all (a listed mode whose read fails) for None."""
    f = tmp_path / "mode.json"
    f.write_text(json.dumps({} if mode is None else {"CameraOperatingMode": {"current": mode}}), encoding="utf-8")
    return f


def in_mode(tmp_path, monkeypatch, mode, listed=True) -> Path:
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    if listed:
        monkeypatch.setenv("FAKE_CAMLINK_PROPS", LISTED)
    monkeypatch.setenv("FAKE_CAMLINK_GET_FILE", str(mode_file(tmp_path, mode)))
    return log


def asked(log) -> int:
    return sum("get CameraOperatingMode" in line for line in log.read_text(encoding="utf-8").splitlines())


class Body:
    """A camera stand-in for proving.nav and camkit.session, link and eyes at once: what the screen reads (`kind`), the
    camera's word on Playback (`said`: True, False or None), every key sent. MENU on a menu closes it onto
    `closes_to`, MENU elsewhere opens the menu; the Playback button leaves Playback where `leaves`."""

    def __init__(self, kind="shooting", said=True, leaves=True, closes_to="shooting"):
        self.kind, self.said, self.leaves, self.closes_to = kind, said, leaves, closes_to
        self.sent, self.judged, self.asked = [], [], 0
        self.run = SimpleNamespace(stop_requested=lambda: False)

    def in_playback(self):
        self.asked += 1
        return self.said

    def press(self, key, cleanup=False, **kw):
        self.sent.append(key)
        if key == "menu":
            self.kind = self.closes_to if self.kind == "menu" else "menu"

    def press_playback(self, screen):
        self.sent.append("playback")
        self.judged.append(screen)
        if self.leaves:
            self.said = False

    def grab(self, tag="grab", save=True):
        return SimpleNamespace(image=BRIGHT, path=None)


class Clock:
    """test_step3_acceptance's clock: a sleep moves it on, nothing waits."""

    def __init__(self):
        self.now = 1000.0

    def sleep(self, s):
        self.now += float(s or 0)

    def monotonic(self):
        return self.now


def read_as(monkeypatch, body):
    """camkit.screen's reading of every frame: the kind `body` shows now."""
    monkeypatch.setattr(screen, "read", lambda f: screen.Screen(kind=body.kind))


# ----------------------------------------------------------------------------------------------- the camera's word

def test_in_playback_is_the_cameras_word_asked_afresh_on_every_call(tmp_path, monkeypatch):
    """True for Playback, False for another mode, None for a listed mode whose read fails: a get on every call, props
    once per link (what C4's check reads, the one way of asking), and None once the link is closed."""
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.in_playback() is True
        mode_file(tmp_path, RECORD)
        assert lk.in_playback() is False
        mode_file(tmp_path, PLAYBACK)
        assert lk.in_playback() is True
        mode_file(tmp_path, None)
        assert lk.in_playback() is None
    assert asked(log) == 4 and sum(" props" in line for line in log.read_text(encoding="utf-8").splitlines()) == 1
    assert lk.in_playback() is None


def test_after_one_failed_props_in_playback_asks_nothing_more_and_c4s_check_still_asks(tmp_path, monkeypatch):
    """The review of 7e8eda9: where props fails, in_playback asked it again (60 s at most) on every screen read as the
    shooting screen. Once failed on this open link it is remembered for in_playback alone; C4's check keeps asking,
    and refusing; a link opened again asks afresh."""
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    monkeypatch.setenv("FAKE_CAMLINK_PROPS_FAIL", "1")

    def props_sent():
        return sum(" props" in line for line in log.read_text(encoding="utf-8").splitlines())
    with fake_link(tmp_path, monkeypatch) as lk:
        assert [session.playback_kind(lk, "shooting") for _ in range(5)] == ["shooting"] * 5
        assert props_sent() == 1 and asked(log) == 0
        for _ in range(2):
            with pytest.raises(safety.Refused, match="could not be read .props"):
                lk.press("c4", allow={"c4"}, screen=SimpleNamespace(kind="menu"), judged=lk.moves)
        assert props_sent() == 3 and lk.in_playback() is None and props_sent() == 3
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.in_playback() is None
    assert props_sent() == 4


@pytest.mark.parametrize("how", ["not listed", "props fails"])
def test_in_playback_is_none_where_the_body_lists_no_mode_or_props_fails(tmp_path, monkeypatch, how):
    log = in_mode(tmp_path, monkeypatch, PLAYBACK, listed=how != "not listed")
    if how == "props fails":
        monkeypatch.setenv("FAKE_CAMLINK_PROPS_FAIL", "1")
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.in_playback() is None and lk.in_playback() is None
    assert asked(log) == 0


# ------------------------------------------------------------------------------------------------ the screen's kind

@pytest.mark.parametrize("said,want", [(True, "playback"), (False, "shooting"), (None, "shooting")])
def test_a_screen_read_as_the_shooting_screen_is_the_playback_view_only_on_the_cameras_word(said, want):
    body = Body(said=said)
    assert session.playback_kind(body, "shooting") == want and body.asked == 1
    for kind in ("menu", "dialog", "notice", "unknown", "playback"):
        assert session.playback_kind(body, kind) == kind
    assert body.asked == 1                                  # asked for a shooting screen alone
    assert session.playback_kind(None, "shooting") == "shooting"
    assert session.playback_kind(SimpleNamespace(), "shooting") == "shooting"          # a link that cannot ask


@pytest.mark.parametrize("said,want", [(True, "playback"), (False, "shooting"), (None, "shooting")])
def test_wait_for_and_the_live_camera_see_the_playback_view(monkeypatch, said, want):
    body = Body(said=said)
    read_as(monkeypatch, body)
    assert session.wait_for(body, ("shooting", "playback"), "the test", link=body) == want
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link = body
    assert cam.reading(body.grab()).kind == want


def test_wait_for_the_shooting_screen_waits_on_the_playback_view_and_says_how_to_leave_it(monkeypatch, capsys):
    body = Body(said=True)
    read_as(monkeypatch, body)
    monkeypatch.setattr(session, "time", Clock())
    with pytest.raises(RuntimeError, match="on a 'playback' screen"):
        session.wait_for(body, ("shooting",), "the test", grace=0, link=body, limit=0)
    assert "Playback button" in capsys.readouterr().out and body.sent == []


def test_to_shooting_leaves_the_playback_view_menu_left_it_on_instead_of_another_menu(monkeypatch):
    from proving import nav
    monkeypatch.setattr(nav, "time", Clock())
    body = Body(kind="menu", said=True)
    read_as(monkeypatch, body)
    nav.to_shooting(body, body, "the test")
    assert body.sent == ["menu", "playback"] and body.judged == ["playback"]
    body = Body(kind="menu", said=None)                     # no word from the camera: as before
    read_as(monkeypatch, body)
    nav.to_shooting(body, body, "the test")
    assert body.sent == ["menu"]


def test_to_shooting_ends_at_a_failed_leave_with_no_key_after_it(monkeypatch):
    """The review of 7e8eda9: after a leave that failed, to_shooting's five-minute wait sent MENU about every 20 s on
    the playback view and could end on a menu opened over it. It now ends there, Failed, nothing more pressed."""
    from proving import base, nav
    monkeypatch.setattr(nav, "time", Clock())
    body = Body(kind="menu", said=True, leaves=False)
    read_as(monkeypatch, body)
    with pytest.raises(base.Failed, match="stayed in its playback view"):
        nav.to_shooting(body, body, "the test")
    assert body.sent == ["menu", "playback"] and body.kind == "shooting" and body.said is True


# ------------------------------------------------------------------------------------------------- leaving the view

def test_leave_playback_presses_the_playback_button_once_and_waits_for_the_shooting_screen(monkeypatch):
    from proving import nav
    monkeypatch.setattr(nav, "time", Clock())
    body = Body(said=True)
    read_as(monkeypatch, body)
    assert nav.leave_playback(body, body) is True
    assert body.sent == ["playback"] and body.judged == ["playback"] and body.said is False


@pytest.mark.parametrize("kind,said", [("menu", True), ("dialog", True), ("notice", True), ("unknown", True),
                                       ("list", True), ("shooting", False), ("shooting", None)])
def test_leave_playback_presses_nothing_off_the_playback_view(monkeypatch, kind, said):
    """Over a menu, a dialog, a notice, a screen of no known kind, or with the camera not saying Playback: nothing."""
    from proving import nav
    monkeypatch.setattr(nav, "time", Clock())
    body = Body(kind=kind, said=said)
    read_as(monkeypatch, body)
    assert nav.leave_playback(body, body) is False and body.sent == []


def test_leave_playback_gives_up_after_one_press_when_the_camera_stays_in_playback(monkeypatch, capsys):
    from proving import nav
    monkeypatch.setattr(nav, "time", Clock())
    body = Body(said=True, leaves=False)
    read_as(monkeypatch, body)
    assert nav.leave_playback(body, body) is False and body.sent == ["playback"]
    assert "still shows its playback view" in capsys.readouterr().out


def test_leave_playback_over_the_stand_in_camlink(tmp_path, monkeypatch):
    """The press the link sends, marked allowed, once; the camera's word read again after it: still Playback, False
    with nothing more pressed; Playback left, True."""
    from proving import nav
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    eyes = Body()
    read_as(monkeypatch, eyes)
    monkeypatch.setattr(nav, "time", Clock())
    with fake_link(tmp_path, monkeypatch) as lk:
        assert nav.leave_playback(lk, eyes) is False
    pressed = sent_lines(log)
    assert len(pressed) == 1 and " press playback 60 allowed" in pressed[0] and asked(log) > 2

    clock = Clock()

    def camera_leaves(s):
        mode_file(tmp_path, RECORD)
        clock.sleep(s)
    monkeypatch.setattr(nav, "time", SimpleNamespace(sleep=camera_leaves, monotonic=clock.monotonic))
    mode_file(tmp_path, PLAYBACK)
    log.unlink()
    with fake_link(tmp_path, monkeypatch) as lk:
        assert nav.leave_playback(lk, eyes) is True
    assert len(sent_lines(log)) == 1


# --------------------------------------------------------------------------------------------- the link's own guard

def test_the_link_refuses_the_playback_button_to_every_other_caller(tmp_path, monkeypatch):
    """In Playback, on the playback view: press, call and an unallowed press are each refused, nothing sent."""
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    with fake_link(tmp_path, monkeypatch) as lk:
        with pytest.raises(safety.Refused, match="only to leave the camera's playback view"):
            lk.press("playback", allow={"playback"}, screen="playback")
        with pytest.raises(safety.Refused, match="only to leave the camera's playback view"):
            lk.call("press playback 60 allowed", allow={"playback"}, screen="playback")
        with pytest.raises(safety.Refused, match="explicit allowance"):
            lk.press("playback", screen="playback")
    assert sent_lines(log) == []


@pytest.mark.parametrize("kind,mode", [("shooting", PLAYBACK), ("menu", PLAYBACK), ("notice", PLAYBACK),
                                       (None, PLAYBACK), ("playback", RECORD), ("playback", None)])
def test_press_playback_is_refused_off_the_playback_view_or_without_the_cameras_word(tmp_path, monkeypatch, kind, mode):
    log = in_mode(tmp_path, monkeypatch, mode)
    with fake_link(tmp_path, monkeypatch) as lk, pytest.raises(safety.Refused, match="Playback refused"):
        lk.press_playback(screen=kind)
    assert sent_lines(log) == []


def test_press_playback_goes_on_the_playback_view_while_the_camera_says_playback(tmp_path, monkeypatch):
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    with fake_link(tmp_path, monkeypatch) as lk:
        assert lk.press_playback(screen=SimpleNamespace(kind="playback"))["args"] == ["playback", "60", "allowed"]
        lk.run.request_stop("the test")
        with pytest.raises(StopRequested):                  # no cleanup press: a STOP refuses it
            lk.press_playback(screen="playback")
    assert len(sent_lines(log)) == 1


@pytest.mark.parametrize("key,kw", [("c4", {"allow": {"c4"}}), ("delete", {"allow": {"delete"}}), ("down", {}),
                                    ("down", {"on_shooting": {"down"}}), ("enter", {}), ("right", {"on_shooting": {"right"}})])
def test_on_the_playback_view_no_key_but_menu_goes_named_or_not_c4_and_delete_among_them(tmp_path, monkeypatch, key,
                                                                                          kw):
    log = in_mode(tmp_path, monkeypatch, PLAYBACK)
    with fake_link(tmp_path, monkeypatch) as lk:
        judged = {"judged": lk.moves} if key in safety.ENTER_KEYS | safety.TRASH_KEYS else {}
        with pytest.raises(safety.Refused):
            lk.press(key, screen=SimpleNamespace(kind="playback"), **kw, **judged)
        with pytest.raises(safety.Refused, match="playback view"):
            lk.dial("front", 1, screen="playback", on_shooting={"front"})
        assert lk.press("menu", screen="playback")["ok"]
    went = sent_lines(log)
    assert len(went) == 1 and " press menu 60" in went[0]


def test_drive_refuses_every_key_but_menu_on_the_playback_view_named_or_not():
    import drive
    assert drive.shooting_press_refused("menu", "playback", frozenset()) == ""
    for key, named in (("down", frozenset()), ("down", {"down"}), ("dial.front.1", {"front"}), ("help", {"help"})):
        assert "playback view" in drive.shooting_press_refused(key, "playback", named)


# ------------------------------------------------------------------------------------------ where the view is left

def test_a_first_opens_check_leaves_the_playback_view_before_its_download(tmp_path):
    fo, sent, run = first_opens(tmp_path)
    fo.opening(("Rating",))
    kinds = []
    fo.wait = lambda eyes, k, why, link=None: kinds.append(tuple(k)) or "playback"
    fo.leave = lambda link, eyes: sent.append("leave") or True
    pressed = []
    fo.settle(SimpleNamespace(press=pressed.append))
    assert kinds == [("shooting", "playback")] and sent == ["leave", "first-open"] and pressed == ["menu", "menu"]
    assert not restore_pending(tmp_path) and fo.marker is None
    assert first_open.seen_record(run.root.name).seen(["Rating"])


def test_a_first_opens_check_that_cannot_leave_the_playback_view_downloads_nothing_and_keeps_the_marker(tmp_path):
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("Rating",))
    fo.wait = lambda eyes, k, why, link=None: "playback"
    fo.leave = lambda link, eyes: sent.append("leave") and False
    with pytest.raises(first_open.FirstOpenFailed, match="playback view"):
        fo.settle(SimpleNamespace(press=lambda key: None))
    assert sent == ["leave"] and restore_pending(tmp_path) and fo.marker is not None and fo.failed == [("Rating",)]


def test_a_first_opens_check_leaves_the_view_with_nav_leave_playback_by_default(tmp_path, monkeypatch):
    from proving import nav
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("Rating",))
    fo.wait = lambda eyes, k, why, link=None: "playback"
    monkeypatch.setattr(nav, "leave_playback", lambda link, eyes: sent.append("nav") or True)
    fo.settle(SimpleNamespace(press=lambda key: None))
    assert sent == ["nav", "first-open"] and not restore_pending(tmp_path)


def test_the_runs_end_leaves_the_playback_view_before_its_download(monkeypatch):
    import runner
    from proving import nav
    left = []
    monkeypatch.setattr(nav, "leave_playback", lambda link, eyes: left.append(True) or left[0])
    kinds = []

    def wait(eyes, k, why, link=None):
        kinds.append(tuple(k))
        return "playback"
    runner.wait_shooting("link", "eyes", "the test", wait=wait)
    assert kinds == [("shooting", "playback")] and left == [True]
    left[:] = []
    monkeypatch.setattr(nav, "leave_playback", lambda link, eyes: left.append(False) or False)
    with pytest.raises(RuntimeError, match="stayed in its playback view"):
        runner.wait_shooting("link", "eyes", "the test", wait=wait)
    monkeypatch.setattr(session, "wait_for", lambda eyes, k, why, link=None: "shooting")
    runner.wait_shooting("link", "eyes", "the test")
    assert left == [False]                                  # the shooting screen: nothing left


@pytest.mark.parametrize("said", [True, False])
def test_no_restore_goes_over_the_playback_view(monkeypatch, said):
    import runner
    body = Body(said=said)
    read_as(monkeypatch, body)
    kind, why = runner.restorable_now(body, body)
    assert (kind, "Playback button" in why) == ((None, True) if said else ("shooting", False))


class Refusing(Body):
    """Body with a run of its own, and a settings download and upload the camera refuses while it says Playback: each
    asked is kept (the review of 7e8eda9's Camera)."""

    def __init__(self, root, **kw):
        from camkit.runs import Run
        super().__init__(**kw)
        self.run, self.asked_for = Run("end", root=root), []

    def download(self, tag):
        self.asked_for.append(("download", self.said))
        if self.said:
            raise LinkError("download refused (Playback)")
        return Path("x.DAT")

    def upload(self, path):
        self.asked_for.append(("upload", self.said))
        return {"ok": True}


@pytest.mark.parametrize("left_on", ["the view after a failed leave", "a menu"])
def test_the_runs_end_in_playback_asks_no_download_and_exits_5_with_the_marker(tmp_path, monkeypatch, capsys, left_on):
    """The review of 7e8eda9: the leave failed, to_shooting's wait ended on a menu opened over the playback view,
    restorable_now took that menu, and the download was asked four times while the camera said Playback, exit 4, no
    RESTORE_BY_HAND. Now the camera's word comes first: nothing is restorable in Playback, whatever the screen reads
    as (the view to_shooting now stops on after its failed leave, or a menu that would be restored over here); the
    marker is written, the owner told how to leave the view, and once they have (on the first look) the run exits 5
    with no download asked."""
    import runner
    from proving import base, nav
    clock = Clock()
    monkeypatch.setattr(nav, "time", clock)
    body = Refusing(tmp_path, kind="menu", said=True, leaves=False)

    def owner_leaves(s):
        clock.sleep(s)
        body.said, body.kind = False, "shooting"
    monkeypatch.setattr(runner, "time", SimpleNamespace(sleep=owner_leaves, monotonic=clock.monotonic))
    monkeypatch.setattr(runner, "restorable_after_close", lambda cam: (cam.read().kind, ""))
    read_as(monkeypatch, body)

    def gave_up_on_a_menu(link, eyes, why):
        raise base.Failed(f"no shooting screen for {why} after MENU and 5 minutes")
    reach = {} if left_on.startswith("the view") else {"reach": gave_up_on_a_menu}
    with pytest.raises(SystemExit) as e:
        runner.end_session(body, body, tmp_path / "start.DAT", **reach)
    assert e.value.code == EXIT_RESTORE_BY_HAND and body.asked_for == [] and restore_pending(tmp_path)
    assert body.sent == ([] if reach else ["menu", "playback"])
    out = capsys.readouterr().out
    assert "half-press of the shutter" in out and "upload_check.py" in out and "(MENU, or Cancel)" not in out


def test_the_sessions_end_asks_no_download_or_upload_while_the_camera_says_playback(tmp_path, capsys):
    body = Refusing(tmp_path, said=True)
    with pytest.raises(SystemExit) as e:
        session.finish(body, tmp_path / "start.DAT")
    assert e.value.code == EXIT_RESTORE_BY_HAND and body.asked_for == [] and restore_pending(tmp_path)
    assert "half-press of the shutter" in capsys.readouterr().out
    ending = session.Ending(tmp_path / "after.DAT", [SimpleNamespace(key="global:0x0001")])
    with pytest.raises(SystemExit):
        session.put_back(body, ending, tmp_path / "start.DAT")
    assert body.asked_for == [] and not ending.uploaded


def test_a_first_opens_check_asks_no_download_while_the_camera_says_playback_whatever_the_screen(tmp_path):
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("Rating",))
    fo.link.in_playback = lambda: True                    # the screen read as the shooting screen (wait gave no kind)
    with pytest.raises(first_open.FirstOpenFailed, match="says it is in Playback"):
        fo.settle(SimpleNamespace(press=lambda key: None))
    assert sent == [] and restore_pending(tmp_path) and fo.marker is not None


def test_closing_stops_on_the_playback_view_and_cancels_nothing_there(tmp_path):
    from camkit.runs import Run
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link, cam.run, cam.screen = Body(), Run("close", root=tmp_path), SimpleNamespace(kind="playback")
    assert cam.cancel_to_menu() is True and cam.link.sent == []
    view = SimpleNamespace(kind="playback")
    link = Body()
    live.close(SimpleNamespace(cancel_to_menu=lambda: True, read=lambda: view, refresh=lambda tag: view), link)
    assert link.sent == []


class PlaybackRow:
    """A Playback row (crawl's fake camera, as test_look_lap's TellingCamera): Right brings up the camera's playback
    view (kind "playback", camkit.live's reading) with a footer, MENU there the plain view, MENU again the menu page with
    the row lit. Keeps every key."""

    def __init__(self):
        self.sent, self.presses, self.at = [], 0, "row"
        self.screens = {name: SimpleNamespace(kind=kind, signature=name, struct=(name,), bits=np.zeros(0, np.uint8),
                                              row=0, page=np.zeros(0, np.uint8))
                        for name, kind in (("row", "menu"), ("view", "playback"), ("plain", "playback"))}

    def press(self, key, **kw):
        self.sent.append(key)
        self.at = {("row", "right"): "view", ("view", "menu"): "plain", ("plain", "menu"): "row"}.get((self.at, key),
                                                                                                     self.at)

    def read(self):
        return self.screens[self.at]


def test_a_look_laps_row_that_opens_the_playback_view_is_left_with_menu_alone():
    cam = PlaybackRow()
    row = {"label": "Rating", "never_open": safety.never_open("Rating")}
    r = crawl.visit_row(cam, cam.read(), {"page": "Playback"}, 0, row, look=True)
    assert r.outcome == "network row: a playback view, left unwalked (looked at only)" and r.kind == "playback"
    assert cam.sent == ["right", "menu", "menu"] and r.outcome.startswith(first_open.OPENED)


# ------------------------------------------------------------------------------------------ the camera's own frame

def test_the_playback_view_the_look_lap_met_is_told_apart_on_the_cameras_word():
    """runs/ILCE-1M2_fw4.00/kit2_a1fin_look_playback, 00145_closing.png: the playback view the lap's closing MENU left
    the camera on (one picture, its file name, date and exposure along the bottom), which the reader reads as the
    shooting screen, as it did then; the shared decision calls it the playback view where the camera says Playback, and
    the shooting screen as before where it says another mode or nothing. Skipped without the run."""
    from camkit.frames import load
    path = paths.a1ii_root() / "kit2_a1fin_look_playback" / "shots" / "00145_closing.png"
    if not path.exists():
        pytest.skip(f"{path} not present")
    f = load(path)
    assert screen.read(f).kind == "shooting"
    assert session.kind_seen(Body(said=True), f) == "playback"
    assert session.kind_seen(Body(said=False), f) == "shooting" and session.kind_seen(Body(said=None), f) == "shooting"
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link = Body(said=True)
    assert cam.reading(f).kind == "playback"
