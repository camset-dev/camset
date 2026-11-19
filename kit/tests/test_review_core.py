"""The engineering review of 2026-11-18, its kit-core findings: each test shows the finding it fixes (the review's
section 2 numbers them). Stand-ins only: an in-process camlink (its replies chosen per command), the camera's own
picture written as camlink writes it, made-up runs; no camera, no camlink, no owner's config.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import live  # noqa: E402
from camkit.frames import OsdFeed  # noqa: E402
from camkit.link import CameraRefused, Disconnected, Link, LinkError, parse_command  # noqa: E402
from camkit.runs import RESTORE_BY_HAND, Run, restore_pending  # noqa: E402
from test_owner_decisions import RESET_DECISION, RESET_MOVES, RESET_STATES, drive_run, scope_file  # noqa: E402,F401

GREY = 60                   # a screen the reader reads as no known kind, and not black (no OSD look of its own)
NO_OSD = {"ok": False, "error": "no OSD image"}             # camlink's reply to a failed OSD fetch (camlink.cpp)
DISCONNECTED = {"ok": False, "error": "disconnected"}       # camlink's reply to every command once the session dropped


class Stdin:
    """camlink's stdin: each line answered at once by `answer(verb, args)` (a reply without its id); an osd that is
    answered ok gets its picture written where it was asked for, as camlink writes it. Every command is kept."""
    def __init__(self, link, answer):
        self.link, self.answer, self.sent = link, answer, []

    def write(self, data):
        n, command = data.decode().strip().split(" ", 1)
        verb, args = parse_command(command)
        self.sent.append(command)
        r = dict(self.answer(verb, args))
        if verb == "osd" and r.get("ok"):
            Image.fromarray(np.full((480, 640, 3), GREY, np.uint8)).save(args[0], format="PNG")
            r["path"] = args[0]
        self.link._out.put(json.dumps({**r, "id": int(n[1:])}))

    def flush(self):
        pass


def link_on(tmp_path, answer):
    """A Link to the in-process stand-in, its process alive."""
    lk = Link(Run("core", root=tmp_path), ip="192.0.2.10", catch_signals=False)
    lk.proc = SimpleNamespace(poll=lambda: None, stdin=None)
    lk.proc.stdin = Stdin(lk, answer)
    return lk


def pressed(lk) -> list:
    return [c.split()[1] for c in lk.proc.stdin.sent if c.startswith("press ")]


# ---------------------------------------------------------------- finding 1: a failed read after a key went


def test_only_a_refused_press_dial_or_release_is_camera_refused():
    """Finding 1: "not accepted" means nothing was done only for the commands that act (press, dial, release): their
    refusal is CameraRefused. A failed screen picture, a failed download or any other failed read is a plain
    LinkError; a "disconnected" reply, whatever the command, is Disconnected (a LinkError, never CameraRefused); a
    button left held or camlink's last word after a signal stay plain LinkError."""
    lk = Link.__new__(Link)
    table = (("press down 60", {"ok": False, "error": "button not accepted"}, CameraRefused),
             ("press down 60", {"ok": False, "error": "refused", "cause": "refused"}, CameraRefused),
             ("dial rear 1", {"ok": False, "error": "button not accepted"}, CameraRefused),
             ("release", {"ok": False, "error": "not accepted"}, CameraRefused),
             ("press down 60", {"ok": False, "error": "held", "cause": "button_held"}, LinkError),
             ("press down 60", {"ok": False, "cause": "signal"}, LinkError),
             ('osd "x.png"', NO_OSD, LinkError),
             ('download "d" "n"', {"ok": False, "error": "camera does not allow a settings download now"}, LinkError),
             ("get CameraOperatingMode", {"ok": False, "error": "unknown property"}, LinkError),
             ("press down 60", DISCONNECTED, Disconnected),
             ('osd "x.png"', DISCONNECTED, Disconnected))
    for command, reply, kind in table:
        lk.call = lambda command, timeout=30.0, r=reply, **g: r
        with pytest.raises(LinkError) as e:
            lk._must(command)
        assert type(e.value) is kind, (command, reply, type(e.value))


def osd_camera(tmp_path, fail_after_press):
    """A LiveCamera on OSD eyes (camkit.frames.OsdFeed) over the stand-in: every press taken; the screen picture asked
    for right after the first press fails with `fail_after_press` (camlink's reply), every other one comes."""
    state = {"presses": 0, "failed": False}

    def answer(verb, args):
        if verb == "press":
            state["presses"] += 1
            return {"ok": True}
        if verb == "osd" and state["presses"] == 1 and not state["failed"]:
            state["failed"] = True
            return fail_after_press
        return {"ok": True}
    lk = link_on(tmp_path, answer)
    eyes = OsdFeed(lk.run)
    eyes.attach(lk)
    return live.LiveCamera(lk, eyes, lk.run), lk


@pytest.mark.parametrize("reply", [NO_OSD, DISCONNECTED], ids=["no-osd-image", "disconnected"])
def test_a_failed_screen_read_after_a_press_never_sends_the_key_again(tmp_path, monkeypatch, reply):
    """Finding 1, the reviewer's reproduction (scripts/double_press.py) on the real Link and OSD eyes: the camera took
    the Down, and the picture asked for after it failed. live.press (the retrying one) once took that for "the camera
    refused the key" (CameraRefused) and sent Down a second time. Now the key goes once and the error says it went."""
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam, lk = osd_camera(tmp_path, reply)
    with pytest.raises(LinkError) as e:
        live.press(cam, "down")
    assert pressed(lk) == ["down"], pressed(lk)
    assert not isinstance(e.value, CameraRefused)
    assert "the press went" in str(e.value) and "could not be read" in str(e.value)


def test_drives_armed_press_whose_screen_read_meets_a_dropped_session_keeps_the_marker(tmp_path, monkeypatch,
                                                                                      scope_file):  # noqa: F811
    """Finding 1, drive.py's branch (b): an armed press that may drop the link (Reset Network Set., link_loss) went,
    and the session dropped under it: the picture asked for after the key is answered "disconnected". What the real
    LiveCamera raises then reaches drive.py's armed press, which once took it for "refused before it went" and removed
    RESTORE_BY_HAND, then tried a remote restore. Now the marker stays, nothing more is pressed and the run exits 5."""
    from exit_status import EXIT_RESTORE_BY_HAND
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam, _ = osd_camera(tmp_path / "live", DISCONNECTED)
    raised = {}
    try:
        cam.press("down")
    except Exception as e:                          # what the real camera raises after a key that went
        raised["e"] = e
    assert "e" in raised and not isinstance(raised["e"], CameraRefused)

    def went_then_dropped(state, key, fake):
        if state == "page" and key == "right":
            fake.handed += 1                        # handed to the link: it went
            raise raised["e"]
    pressed_keys, line, _, code, restore, out, _ = drive_run(
        tmp_path, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
        RESET_MOVES, more=["--confirm"], fails=went_then_dropped)
    assert code == EXIT_RESTORE_BY_HAND and restore == [] and restore_pending(tmp_path) is not None
    assert pressed_keys == ["menu"] and line["restore"] == "by hand" and "handed to the link" in line["outcome"]
    assert (tmp_path / RESTORE_BY_HAND).exists() and "upload_check.py" in out


# ---------------------------------------------------------------- finding 8: drive.py's end is runner.end_session


def test_drives_end_restores_after_a_stop_or_a_link_error_while_it_waits_for_the_shooting_screen(tmp_path, monkeypatch,
                                                                                               scope_file):  # noqa: F811
    """Finding 8: drive.py ended its run with an old copy of runner.end_session, which took only a RuntimeError from the
    wait for the shooting screen: a STOP (or a first Ctrl-C) during that wait, or a link error there (OSD eyes), left
    the restore undone and exited 4. Through end_session the restore goes on all the same, over a screen it may go
    over (restorable_now: a menu page here)."""
    import drive as D
    import runner
    from camkit import safety
    from camkit.link import NET_ERROR_SAID, NetworkError, StopRequested
    monkeypatch.setattr(runner, "restorable_now", lambda link, eyes: ("menu", ""))
    monkeypatch.setattr(runner, "hold_for_owner", lambda *a, **k: pytest.fail("held for the owner over a menu page"))

    def refused(state, key, cam):
        if state == "page" and key == "right":
            raise safety.Refused("right: the camera's own check refused it")
    for name, raised in (("stop", StopRequested("a stop was asked for while waiting")),
                         ("link", NetworkError(NET_ERROR_SAID))):
        def wait(link, eyes, why, wait=None, raised=raised):
            raise raised
        monkeypatch.setattr(D, "wait_shooting", wait)
        _, line, _, code, restore, out, _ = drive_run(
            tmp_path / name, monkeypatch, scope_file, ["right"], ["Reset Network Set."], RESET_DECISION, RESET_STATES,
            RESET_MOVES, more=["--confirm"], fails=refused)
        assert code == 0 and restore == ["closed", "ended"], (name, code, restore)
        assert "restoring all the same" in out and line["completed"] is False and line["before"]
