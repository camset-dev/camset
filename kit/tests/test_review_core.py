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


# ---------------------------------------------------------------- finding 15: the link stall waited out in Link.call

NET_ERROR_EV = json.dumps({"event": "warning", "code": 131079, "text": "NetworkErrorOccurred"})
NET_RECOVERED_EV = json.dumps({"event": "warning", "code": 131080, "text": "NetworkErrorRecovered"})


class Clock:
    """Time that moves only when the code sleeps; what is due at a time is done as the clock passes it."""
    def __init__(self):
        self.t, self.due = 0.0, []

    def now(self):
        return self.t

    def at(self, t, act):
        self.due = sorted([*self.due, (t, act)], key=lambda x: x[0])

    def sleep(self, s):
        end = self.t + max(0.0, s)
        while self.due and self.due[0][0] <= end:
            t, act = self.due.pop(0)
            self.t = max(self.t, t)
            act()
        self.t = end


def clocked_link(tmp_path, answer=lambda verb, args: {"ok": True}):
    """The stand-in Link on the test's clock, every command's time of sending kept (sent_at)."""
    clock = Clock()
    lk = link_on(tmp_path, answer)
    lk._clock, lk._sleep = clock.now, clock.sleep
    stdin, sent_at = lk.proc.stdin, []
    write = stdin.write

    def timed(data):
        sent_at.append((clock.t, data.decode().split(" ", 1)[1].strip()))
        write(data)
    stdin.write = timed
    return lk, clock, sent_at


def test_every_command_waits_at_the_link_for_the_recovery_and_its_settle(tmp_path, capsys):
    """Finding 15: the wait the camera's link stall needs (sending nothing until NetworkErrorRecovered, then 2 s) was
    taken only in camkit.live.close, so a run's end on OSD eyes failed on its first frame, and session.ended gave up its
    downloads after about 30 s. Now every command waits where every command passes (Link.call): a screen picture, a
    download, a cleanup MENU; and a command less than 2 s after a recovery gets the rest of the settle. Said in plain
    words, no SDK word."""
    import shutil

    from camkit import session
    from fake_camlink import SAMPLE

    def answer(verb, args):
        if verb == "download":
            shutil.copy(SAMPLE, Path(args[0]) / f"{args[1]}.DAT")
            return {"ok": True, "path": str(Path(args[0]) / f"{args[1]}.DAT")}
        return {"ok": True}
    lk, clock, sent_at = clocked_link(tmp_path, answer)
    start = tmp_path / "start.DAT"
    shutil.copy(SAMPLE, start)
    lk._event(NET_ERROR_EV)
    clock.at(55.3, lambda: lk._event(NET_RECOVERED_EV))
    lk.osd(tmp_path / "x.png")
    assert sent_at[0][0] >= 55.3 + 2.0 and sent_at[0][1].startswith("osd")
    out = capsys.readouterr().out
    assert "network error" in out and "recovered" in out and "NetworkError" not in out
    # the session's end: its download waits out a new error, far past the 4 tries 10 s apart it once gave up after
    lk._event(NET_ERROR_EV)
    t0 = clock.t
    clock.at(t0 + 55.3, lambda: lk._event(NET_RECOVERED_EV))
    ending = session.ended(lk, start, say=lambda m: None)
    downloads = [t for t, c in sent_at if c.startswith("download")]
    assert ending.after is not None and downloads and downloads[0] >= t0 + 55.3 + 2.0
    # a cleanup MENU half a second after a recovery waits the rest of the settle
    lk._event(NET_ERROR_EV)
    lk._event(NET_RECOVERED_EV)
    clock.sleep(0.5)
    t1 = clock.t
    lk.press("menu", cleanup=True)
    assert sent_at[-1] == (pytest.approx(t1 + 1.5), "press menu 60")


def test_a_stop_during_the_wait_refuses_a_key_and_the_cleanup_menu_still_waits(tmp_path):
    """Finding 15: a STOP (its file, or a first Ctrl-C) asked for while a key waits for the recovery ends that key's
    wait, nothing sent (StopRequested), so the run's stop path goes on; its cleanup MENU, which a STOP never refuses,
    waits for the recovery and its settle in turn, then goes."""
    from camkit.link import StopRequested
    lk, clock, sent_at = clocked_link(tmp_path)
    lk._event(NET_ERROR_EV)
    clock.at(20.0, lambda: lk.run.request_stop("STOP file"))
    clock.at(55.3, lambda: lk._event(NET_RECOVERED_EV))
    with pytest.raises(StopRequested):
        lk.press("down", screen="menu")
    assert sent_at == [] and clock.t == pytest.approx(20.0, abs=0.3)
    lk.press("menu", cleanup=True)
    assert sent_at == [(pytest.approx(57.3, abs=0.3), "press menu 60")]


# ---------------------------------------------------------------- finding 16: a page scan records its eyes


def whole_scan(root: Path, name: str, when: float, mode: str = "Stills", eyes: str | None = None) -> Path:
    """A made-up whole page scan of `mode`, its lap written at `when`, made with `eyes` (None: a scan from before scans
    recorded them)."""
    import os

    import runner
    d = root / name
    d.mkdir(parents=True)
    (d / "scan_rekeyed.json").write_text("[]", encoding="utf-8")
    (d / "model.json").write_text("[]", encoding="utf-8")
    runner.record_mode(d, mode, **({"eyes": eyes} if eyes else {}))
    os.utime(d / "scan_rekeyed.json", (when, when))
    return d


def test_the_default_scan_is_the_latest_of_this_runs_eyes_and_a_named_scan_of_other_eyes_stops(own_runs, tmp_path,
                                                                                               monkeypatch, capsys):
    """Finding 16: a page scan matches only frames from the eyes it was made with, and latest_scan picked by mode alone:
    an OSD run was handed the newer HDMI scan and failed after its start download with a message about screens. Now
    a scan records its eyes, the default is the latest scan of this run's eyes (CAMSET_EYES, else the config's), and a
    named scan of other eyes stops in plain words before the link opens. A scan from before (no eyes recorded) is
    taken as before, said in one line."""
    import runner
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    osd = whole_scan(root, "kit2_page_scan_osd", 1_000, eyes="osd")
    hdmi = whole_scan(root, "kit2_page_scan_hdmi", 2_000, eyes="hdmi")
    monkeypatch.setenv("CAMSET_EYES", "osd")
    assert runner.current_eyes() == "osd" and runner.latest_scan("Stills") == osd
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills")) == osd
    with pytest.raises(SystemExit) as stop:
        runner.scan_dir(runner.in_mode(str(hdmi), "Stills"))
    said = str(stop.value.code)
    assert "made with HDMI eyes" in said and "Nothing was sent to the camera" in said and "CAMSET_EYES=hdmi" in said
    monkeypatch.setenv("CAMSET_EYES", "hdmi")
    assert runner.current_eyes() == "hdmi" and runner.latest_scan("Stills") == hdmi
    with pytest.raises(SystemExit, match="made with OSD eyes"):
        runner.scan_dir(runner.in_mode(str(osd), "Stills"))
    # a scan from before scans recorded their eyes: taken as before (by its lap's time), named or by default, and said
    capsys.readouterr()
    old = whole_scan(root, "kit2_page_scan_old", 3_000)
    assert runner.latest_scan("Stills") == old and runner.scan_dir(runner.in_mode(str(old), "Stills")) == old
    assert capsys.readouterr().out.count("records no eyes") == 1
    # page_scan.py records the eyes it scans with, before its first press: the ones camkit.frames opens by that rule
    import page_scan
    from camkit.frames import eyes_from_config
    monkeypatch.setenv("CAMSET_EYES", "osd")
    assert eyes_from_config(Run("eyes", root=tmp_path)).name == runner.current_eyes() == "osd"
    monkeypatch.setattr(page_scan, "eyes_from_config", lambda run: SimpleNamespace(name="osd", close=lambda: None))
    monkeypatch.setattr(page_scan, "Link", lambda run: (_ for _ in ()).throw(LinkError("no camera here", opened=False)))
    monkeypatch.setattr(sys, "argv", ["page_scan.py", "--mode", "Stills", "--run", "kit2_page_scan_new"])
    with pytest.raises(LinkError):
        page_scan.main()
    assert runner.scan_record(root / "kit2_page_scan_new")["eyes"] == "osd"


# ---------------------------------------------------------------- finding 17: page_scan's Right and its fresh frames


class ScanCamera:
    """A made-up camera for kit/page_scan.py's Scan: `screens` in turn ({kind, focus, row}), each settled frame the
    next one after a press; a frame is `age` s old when handed over (its capture time), every grab a fresh one. The link
    keeps what it is sent, with the screen each press was judged on."""
    name = "hdmi"

    def __init__(self, tmp_path, screens, age=0.0):
        self.tmp, self.screens, self.at, self.age, self.n = tmp_path, list(screens), 0, age, 0
        self.timing, self.sent, self.grabs = {}, [], []
        self.moves, self.moved_at, self.menus = 0, None, 0

    def frame(self, tag, age):
        import time
        self.n += 1
        path = self.tmp / f"{self.n:05d}_{tag}.png"
        Image.fromarray(np.full((480, 640, 3), GREY, np.uint8)).save(path)
        return SimpleNamespace(image=np.full((480, 640, 3), GREY, np.uint8), t=time.monotonic() - age, path=path,
                               screen=self.screens[self.at])

    def grab(self, tag="f", save=True):
        self.grabs.append(tag)
        return self.frame(tag, 0.0)

    def settle(self, before, tag="f", expect_change=None, sent_at=None, **kw):
        return self.frame(tag, self.age), True

    def press(self, button, hold_ms=60, screen=None, **kw):          # the link's
        self.sent.append((button, getattr(screen, "kind", screen)))
        self.moves += 1
        self.at = min(self.at + 1, len(self.screens) - 1)
        return {"ok": True}


def scan_on(tmp_path, monkeypatch, screens, lit="Image Quality/Rec", age=0.0):
    """page_scan.Scan over ScanCamera, the screen read from each frame's made-up state and the lit bar read `lit`."""
    import page_scan
    from camkit import screen as screen_mod

    def read(f):
        st = getattr(f, "screen", {"kind": "unknown"})
        return SimpleNamespace(kind=st["kind"], focus=st.get("focus"), row=st.get("row"), field=None,
                               count=st.get("count", 5), slots=None, signature=f"{st['kind']}{st.get('row')}",
                               page=st.get("page", "p"))
    monkeypatch.setattr(screen_mod, "read", read)
    monkeypatch.setattr(page_scan, "page_key", lambda f: getattr(f, "screen", {}).get("page", "p"))
    monkeypatch.setattr(screen_mod, "same_state", lambda a, b: (a.kind, a.row) == (b.kind, b.row))
    monkeypatch.setattr(live, "lit_text", lambda image, path: lit)
    cam = ScanCamera(tmp_path, screens, age)
    run = Run("kit2_page_scan_t", root=tmp_path)
    return page_scan.Scan(run, cam, cam, 3), cam


GROUPS = {"kind": "menu", "focus": "groups", "row": 0}


def rows(n, page="p"):
    return {"kind": "menu", "focus": "rows", "row": n, "page": page}


def test_page_scans_right_into_the_rows_is_judged_as_any_opening_press(tmp_path, monkeypatch, capsys):
    """Finding 17: the scan's one Right "into the rows" (the menu opened with its cursor in the group column) went
    straight to the link, past the never-open check every other opening press meets, on the first program a new body
    runs: a focus misread would open the lit row. Now it is judged as LiveCamera judges an opening press: the lit bar
    read first, and a bar that must not be opened (here Format) refused, nothing sent but the scan's closing MENU."""
    scan, cam = scan_on(tmp_path, monkeypatch, [GROUPS, rows(0)], lit="Format")
    scan.run_scan()
    assert [k for k, _ in cam.sent] == ["menu"], cam.sent           # the close's MENU alone, never the Right
    assert "never opened" in capsys.readouterr().out
    scan, cam = scan_on(tmp_path / "ok", monkeypatch, [GROUPS, rows(0), rows(1), rows(2), rows(0)])
    (tmp_path / "ok").mkdir(exist_ok=True)
    scan.run_scan()
    assert cam.sent[0] == ("right", "menu") and [k for k, _ in cam.sent[1:]].count("down") >= 1


def test_page_scans_presses_are_judged_on_a_frame_no_older_than_stale_s(tmp_path, monkeypatch):
    """Finding 17: a press is judged on a frame no older than live.STALE_S (the screen can change with nothing sent):
    a Down whose frame is older gets one fresh look first, judged and measured from that; where the fresh look is no
    longer the menu page it was read as, nothing is sent."""
    import page_scan
    scan, cam = scan_on(tmp_path, monkeypatch, [rows(0), rows(1)], age=live.STALE_S + 1)
    before = cam.frame("old", live.STALE_S + 1)
    scan.press("down", before, "down")
    assert cam.grabs == ["down-fresh"] and cam.sent == [("down", "menu")]
    cam2 = ScanCamera(tmp_path, [rows(0)], 0.0)
    scan2 = page_scan.Scan(scan.run, cam2, cam2, 3)
    old = cam2.frame("old", live.STALE_S + 1)
    cam2.screens[0] = {"kind": "shooting"}                         # the menu closed by itself meanwhile
    with pytest.raises(Exception, match="changed"):
        scan2.press("down", old, "down")
    assert cam2.sent == []
    fresh = cam2.frame("new", 0.0)
    scan2.press("menu", fresh, "menu-close")                       # a frame young enough: no extra look
    assert cam2.grabs == ["down-fresh"] and cam2.sent == [("menu", "shooting")]
