"""The SDK's network error (NetworkErrorOccurred, then NetworkErrorRecovered about 55 s later) during a run: the link
keeps the state from camlink's events, sends nothing while it lasts, and the run's cleanup waits for the recovery, then
cancels with MENU and restores, where it once pressed MENU at once, had it refused (button_held) and closed the link
with the camera unrestored (kit2_zebra_split, 2026-11-18). An in-process stand-in for camlink and an injected clock:
nothing here waits real seconds or talks to a camera.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import live  # noqa: E402
from camkit.link import RECOVER_SETTLE, RECOVER_TIMEOUT, Link, LinkError, NetworkError  # noqa: E402
from camkit.runs import Run  # noqa: E402

# camlink's stderr lines for the SDK's warnings, as kit2_zebra_split's events.jsonl logged them
ERROR = json.dumps({"event": "warning", "code": 131079, "text": "NetworkErrorOccurred"})
RECOVERED = json.dumps({"event": "warning", "code": 131080, "text": "NetworkErrorRecovered"})
DISCONNECTED = json.dumps({"event": "disconnected", "code": 33282, "text": "disconnected"})
HELD = {"ok": False, "error": "its release was refused three times", "cause": "button_held"}


class Clock:
    """Time that moves only when the code sleeps; events scheduled at a time are fed in as the clock passes it."""
    def __init__(self):
        self.t, self.due = 0.0, []

    def now(self):
        return self.t

    def at(self, t, act):
        self.due.append((t, act))
        self.due.sort(key=lambda x: x[0])

    def sleep(self, s):
        end = self.t + max(0.0, s)
        while self.due and self.due[0][0] <= end:
            t, act = self.due.pop(0)
            self.t = max(self.t, t)
            act()
        self.t = end


class Stdin:
    """camlink's stdin: each command line answered at once by `answer(command, t)` (a reply without its id), the reply
    queued as camlink's stdout would carry it; every line kept with the time it was sent."""
    def __init__(self, link, clock, answer):
        self.link, self.clock, self.answer, self.sent = link, clock, answer, []

    def write(self, data):
        line = data.decode().strip()
        n, command = line.split(" ", 1)
        self.sent.append((self.clock.t, command))
        self.link._out.put(json.dumps({**self.answer(command, self.clock.t), "id": int(n[1:])}))

    def flush(self):
        pass


def link_on(tmp_path, clock, answer=lambda command, t: {"ok": True}):
    """A Link to the stand-in: its process alive, its clock and sleep the test's."""
    lk = Link(Run("net", root=tmp_path), ip="192.0.2.10", catch_signals=False)
    lk.proc = SimpleNamespace(poll=lambda: None, stdin=None)
    lk.proc.stdin = Stdin(lk, clock, answer)
    lk._clock, lk._sleep = clock.now, clock.sleep
    return lk


def events(lk) -> list:
    path = lk.run.dir / "events.jsonl"
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


# ---------------------------------------------------------------- the link's state and its wait


def test_the_link_keeps_the_network_error_from_its_events_and_it_is_no_disconnect(tmp_path):
    """NetworkErrorOccurred puts the link in the error state, NetworkErrorRecovered takes it out; gone() stays "" all
    the while (the session is there: camlink says no "disconnected"), and a new session starts clear."""
    clock = Clock()
    lk = link_on(tmp_path, clock)
    assert lk.network_error() == ""
    lk._event(ERROR)
    assert lk.network_error() and lk.gone() == ""
    clock.sleep(55.3)
    lk._event(RECOVERED)
    assert lk.network_error() == "" and lk.gone() == ""
    lk._event(ERROR)
    lk._net_reset()
    assert lk.network_error() == ""


def test_no_command_goes_out_until_the_link_recovers_and_settles(tmp_path):
    """(a) In the error state wait_recovered sends nothing, waits for NetworkErrorRecovered (55.3 s after the error, as
    measured), then RECOVER_SETTLE more (a key sent at the recovery was refused, one 2.0 s after it taken); its
    constants are the measured ones."""
    assert (RECOVER_TIMEOUT, RECOVER_SETTLE) == (75.0, 2.0)
    clock = Clock()
    lk = link_on(tmp_path, clock)
    lk._event(ERROR)
    clock.at(55.3, lambda: lk._event(RECOVERED))
    assert lk.wait_recovered() is True
    assert clock.t >= 55.3 + RECOVER_SETTLE and lk.proc.stdin.sent == []
    assert [e["outcome"] for e in events(lk) if e["kind"] == "network_wait"] == ["recovered"]
    lk.press("menu", cleanup=True)
    assert lk.proc.stdin.sent == [(clock.t, "press menu 60")]


def test_a_recovery_just_past_is_still_given_its_settle(tmp_path):
    """Recovered half a second before the wait was asked: the wait still gives the rest of RECOVER_SETTLE; long after
    it, or with no error at all, it returns at once."""
    clock = Clock()
    lk = link_on(tmp_path, clock)
    lk._event(ERROR)
    clock.sleep(55.0)
    lk._event(RECOVERED)
    clock.sleep(0.5)
    assert lk.wait_recovered() is True and clock.t == pytest.approx(57.0)
    clock.sleep(30)
    t = clock.t
    assert lk.wait_recovered() is True and clock.t == t


def test_a_drop_or_no_recovery_in_time_ends_the_wait_false(tmp_path):
    """(c) A disconnect during the wait ends it at once, False; no recovery within the timeout ends it False at the
    timeout; neither sends anything."""
    clock = Clock()
    lk = link_on(tmp_path, clock)
    lk._event(ERROR)
    clock.at(10.0, lambda: lk._event(DISCONNECTED))
    assert lk.wait_recovered() is False and clock.t < 11.0 and lk.proc.stdin.sent == []
    clock2 = Clock()
    lk2 = link_on(tmp_path, clock2)
    lk2._event(ERROR)
    assert lk2.wait_recovered() is False and clock2.t == pytest.approx(RECOVER_TIMEOUT)
    assert [e["outcome"] for e in events(lk2) if e["kind"] == "network_wait"][-1] == "timed out"


def test_a_command_refused_in_the_error_state_says_so_in_plain_words(tmp_path):
    """A press or an osd the camera does not take while the link is in the error state raises NetworkError, in plain
    words (no SDK word), the camera's own reply in the run's log only; outside it the error is as before."""
    clock = Clock()
    lk = link_on(tmp_path, clock, lambda command, t: HELD if command.startswith("press") else
                 {"ok": False, "error": "no OSD image"})
    with pytest.raises(LinkError) as before:
        lk.press("menu", cleanup=True)
    assert not isinstance(before.value, NetworkError) and "release was refused" in str(before.value)
    lk._event(ERROR)
    for send in (lambda: lk.press("menu", cleanup=True), lambda: lk.osd(tmp_path / "x.png")):
        with pytest.raises(NetworkError) as got:
            send()
        said = str(got.value)
        assert "network error" in said and "NetworkError" not in said and "release was refused" not in said
    logged = [e for e in events(lk) if e["kind"] == "cmd"]
    assert logged[-2]["reply"]["cause"] == "button_held" and logged[-1]["reply"]["error"] == "no OSD image"


# ---------------------------------------------------------------- the run's cleanup (camkit.live.close)


class Cam:
    """Just enough of a LiveCamera for camkit.live.close: MENU from the screen on show leaves for a menu page, a second
    MENU for the shooting screen; a MENU the link refuses moves nothing."""
    def __init__(self, link, kind="unknown"):
        self.link, self.kind = link, kind
        self.frame = SimpleNamespace(path=Path("00012_down.png"))

    def cancel_to_menu(self, tries=3):
        if self.kind in ("menu", "tiles", "shooting", "playback"):
            return True
        self.link.press("menu", cleanup=True)
        self.kind = "menu"
        return True

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def refresh(self, tag):
        if self.kind == "menu" and self.link.menus >= 2:
            self.kind = "shooting"
        return self.read()


@pytest.fixture
def clocked(monkeypatch):
    """The test's clock, its sleep also camkit.live's (close's own pauses)."""
    clock = Clock()
    monkeypatch.setattr(live.time, "sleep", clock.sleep)
    return clock


def held_in_error(lk):
    """MENU refused (button_held) while the link is in the error state; taken otherwise."""
    return lambda command, t: HELD if lk.network_error() else {"ok": True}


def test_the_cleanup_after_a_failure_in_the_error_state_waits_then_cancels(tmp_path, clocked, capsys):
    """(b) The run's cleanup (camkit.live.close, runner.close_for_restore's) on a link in the error state: it says so in
    plain words, waits for the recovery and its settle with nothing sent, then MENU, MENU, and the shooting screen, so
    the run's restore follows; the frame on show is named, no SDK word printed."""
    answers = {}
    lk = link_on(tmp_path, clocked, lambda command, t: answers["f"](command, t))
    answers["f"] = held_in_error(lk)
    lk._event(ERROR)
    clocked.at(55.3, lambda: lk._event(RECOVERED))
    cam = Cam(lk)
    live.close(cam, lk)
    sent = lk.proc.stdin.sent
    assert [c for _, c in sent] == ["press menu 60", "press menu 60"] and sent[0][0] >= 55.3 + RECOVER_SETTLE
    assert cam.kind == "shooting"
    out = capsys.readouterr().out
    assert "remote link reported a network error" in out and "00012_down.png" in out and "recovered" in out
    assert "may be one whose picture the camera cannot send" in out and "NetworkError" not in out


def test_a_run_whose_press_meets_the_error_waits_cancels_restores_and_says_why(tmp_path, clocked, capsys, monkeypatch):
    """(b) A prover's session (runner.prover_session, whose cleanup is runner.close_for_restore, drive.py's too): a press
    in the error state stops the body with the plain-words error; the cleanup waits for the recovery, MENU goes out
    after it, and only then the restore (end_session) and its check; no SDK word is printed."""
    import contextlib

    import proving.nav
    import runner
    order = []
    lk = link_on(tmp_path, clocked)
    lk.proc.stdin.answer = held_in_error(lk)
    lk.download = lambda tag: Path(f"00001_{tag}.DAT")
    clocked.at(40.0 + 55.3, lambda: lk._event(RECOVERED))
    monkeypatch.setattr(runner, "check_readers", lambda: None)
    monkeypatch.setattr(runner, "Link", lambda run: contextlib.nullcontext(lk))
    monkeypatch.setattr(proving.nav, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, run, may_open=(): Cam(link))
    monkeypatch.setattr(runner, "end_session", lambda *a, **k: order.append(("restore", clocked.t)) or "ending")
    monkeypatch.setattr(runner, "restore_checked", lambda *a, **k: order.append(("checked", clocked.t)) or True)
    eyes = SimpleNamespace(attach=lambda link: None, close=lambda: None)
    with runner.prover_session(lk.run, eyes) as s:
        clocked.sleep(40.0)
        lk._event(ERROR)                    # the screen stalls the session 10-36 s after it appears
        s.link.press("down", screen="menu")
    menus = [t for t, c in lk.proc.stdin.sent if c == "press menu 60"]
    assert menus and menus[0] >= 40.0 + 55.3 + RECOVER_SETTLE
    assert [k for k, _ in order] == ["restore", "checked"] and order[0][1] > menus[-1]
    out = capsys.readouterr().out
    assert "stopped: NetworkError: the camera's remote link reported a network error" in out
    assert "NetworkErrorOccurred" not in out and "button_held" not in out and "release was refused" not in out


def test_a_drop_or_no_recovery_during_the_cleanup_closes_as_before(tmp_path, clocked, capsys):
    """(c) The error then a disconnect, or no recovery within the timeout: the wait ends False and close goes on as it
    did before (MENU at once after the wait, its failures retried as ever), saying the link did not recover."""
    lk = link_on(tmp_path, clocked)
    lk._event(ERROR)
    clocked.at(5.0, lambda: lk._event(DISCONNECTED))
    lk.proc.stdin.answer = lambda command, t: {"ok": True}
    cam = Cam(lk)
    live.close(cam, lk)
    assert lk.proc.stdin.sent[0][0] == pytest.approx(5.0, abs=0.5) and cam.kind == "shooting"
    assert "did not recover" in capsys.readouterr().out
    clock2_start = clocked.t
    lk2 = link_on(tmp_path, clocked)
    lk2._event(ERROR)
    live.close(Cam(lk2), lk2)
    assert lk2.proc.stdin.sent[0][0] == pytest.approx(clock2_start + RECOVER_TIMEOUT, abs=0.5)


def test_a_menu_still_held_after_the_wait_is_reported_as_before_not_waited_on_again(tmp_path, clocked, capsys):
    """(d) Recovered, settled, and MENU still answers button_held, the error back: close says it and tries again as it
    always did, with no second wait (one wait per close), until it gives up as before."""
    lk = link_on(tmp_path, clocked, lambda command, t: HELD)
    lk._event(ERROR)
    clocked.at(55.3, lambda: lk._event(RECOVERED))
    clocked.at(58.0, lambda: lk._event(ERROR))
    with pytest.raises(SystemExit, match="could not get back to the shooting screen"):
        live.close(Cam(lk), lk)
    assert [e["outcome"] for e in events(lk) if e["kind"] == "network_wait"] == ["recovered"]
    assert len(lk.proc.stdin.sent) == 8 and "trying again" in capsys.readouterr().out


def test_an_ordinary_failed_press_closes_as_before_with_no_wait(tmp_path, clocked, capsys):
    """(e) No network error: a MENU refused once is retried as before, at once (no wait, nothing said of the network)."""
    replies = iter([HELD, {"ok": True}, {"ok": True}])
    lk = link_on(tmp_path, clocked, lambda command, t: next(replies))
    cam = Cam(lk)
    live.close(cam, lk)
    assert [t for t, _ in lk.proc.stdin.sent][0] == 0.0 and cam.kind == "shooting"
    assert not [e for e in events(lk) if e["kind"] == "network_wait"]
    out = capsys.readouterr().out
    assert "network error" not in out and "trying again" in out
