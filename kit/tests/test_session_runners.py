"""kit/drive.py's and kit/crawl_run.py's sessions against a stand-in camera: camlink is kit/tests/fake_camlink.py for
every link a run opens (its restore check's among them), the eyes made-up frames whose kind the test scripts, the clock
the test's own (a sleep is noted, never slept). Everything between is the kit's own: the start through runner's session
(the shooting screen, the start download, the menu's lock after it), the end (runner.end_session, camkit.session.finish,
the restore and its check), the exit status. Only what the run does on its row is made up (the scan, the camera's own
checks, the lit text), as the guard tests make it up. Each pin was written against the runners as they were before
their start moved onto runner.session_start, and holds after it; the one change made on purpose is the restore's check
after an upload, which with HDMI eyes now watches for the camera's restart as every prover's does
(camkit.session.restarted) where it waited a fixed RESTART_FIRST s."""
import ast
import contextlib
import io
import json
import os
import signal
import stat
import sys
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import camkit
import crawl_run
import drive
import fake_camlink
from camkit import camset, first_open, screen, session, vlm
from camkit import link as camlink
from camkit.link import Link, StopRequested
from camkit.runs import RESTORE_BY_HAND, Run
from conftest import TEST_CAMERA

IP = "192.0.2.10"
DAY = "2026-11-15"
BLANK = {"date": DAY, "cards": "blank", "why": "typed"}
REAL_SLEEP = time.sleep


class AllSeen:
    """Every row seen opened on this body, as on a body the kit has crawled (conftest.rows_seen's)."""
    opened: set = set()

    def seen(self, path) -> bool:
        return bool(path)

    def unseen(self, path) -> list:
        return []

    def lit_row(self, parent, lit, known=()) -> tuple:
        return (*parent, lit)

    def skips(self, path, why="") -> bool:
        return False


class Frame:
    """A frame the made-up eyes grab: what the screen reads as (screen.read, made up below), and a grey picture (no black
    frame for camkit.session.osd_shooting to read on the camera's own picture)."""
    image = np.full((8, 8, 3), 128, np.uint8)
    path = None

    def __init__(self, kind: str):
        self.kind = kind


class Eyes:
    """The run's eyes: HDMI or OSD by name, each grab the camera's next scripted kind (Camera.kind_now)."""

    def __init__(self, camera, name: str, run):
        self.camera, self.name, self.run = camera, name, run
        camera.said.append("eyes made")

    def attach(self, link):
        self.link = link

    def grab(self, tag="f", save=True):
        return Frame(self.camera.kind_now())

    def close(self):
        self.camera.said.append("eyes closed")


class Cam:
    """camkit.live.LiveCamera made up: a menu page on show, each press sent to the link as the camera's would be (the
    link's own guards and its STOP check judge it)."""

    def __init__(self, camera, link):
        self.camera, self.link, self.run = camera, link, link.run
        self.frame = SimpleNamespace(path=Path("00001_menu.png"), image=None)

    def read(self):
        return SimpleNamespace(kind="menu", focus="rows")

    def refresh(self, tag="f", frame=None):
        return self.read()

    def press(self, key, **kw):
        self.camera.before_press(key)
        self.camera.pressed.append((key, self.camera.marker.exists()))
        self.link.press(key, screen="menu")


class Camera:
    """The stand-in camera and the run's made-up seams (see the module's docstring). `eyes`: their name; `mode`: the
    shooting mode the page scan records (session.MODE: the lock is watched in a mode measured); `changed`: the end
    download differs from the start in one record (a stand-in file, never sent anywhere), so the start file goes back;
    `notice`: the saving notice shows after a download and after an upload, then the shooting screen; `kinds`: the
    screen's kinds before the start, one a grab; `on_press`: {key: what happens just before it goes} ("stop": the STOP
    file, "ctrl-c": the first Ctrl-C, through camkit.link's own handler)."""

    def __init__(self, tmp_path, monkeypatch, own_runs):
        self.mp, self.tmp, self.root = monkeypatch, tmp_path, own_runs / TEST_CAMERA
        self.eyes, self.mode, self.notice, self.on_press, self.on_grab = "osd", None, False, {}, {}
        self.kinds, self.kind = deque(), "shooting"
        self.said, self.pressed, self.slept, self.closed, self.runs = [], [], [], [], []
        self.t, self.grabs = 1000.0, 0
        self.log = tmp_path / "camlink.txt"
        monkeypatch.setenv("FAKE_CAMLINK_LOG", str(self.log))
        monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "ModelName", "text": "TEST-CAM"},
                                                             {"name": "SoftwareVersion", "text": "9.99"}]))
        monkeypatch.delenv("CAMSET_USB", raising=False)
        # RESTORE_BY_HAND's second place (camkit.runs.marker_places: the clone's own runs/ for a camera's key) the test's
        # own, as its runs are
        monkeypatch.setattr(camkit, "RUNS", tmp_path / "clone_runs")
        # every link the run opens, its restore check's among them, starts the stand-in (no signal handler in the tests)
        ip, usb, _binary, _signals, pending, picture = Link.__init__.__defaults__
        monkeypatch.setattr(Link.__init__, "__defaults__", (IP, usb, fake_camlink.COMMAND, False, pending, picture))
        download, upload = Link.download, Link.upload

        def downloaded(link, tag):
            got = download(link, tag)
            if self.notice and tag == "before":         # the start download's saving notice
                self.kinds.extend(["notice", "shooting"])
            return got

        def uploaded(link, path):
            got = upload(link, path)
            if self.notice:
                self.kinds.extend(["notice", "notice", "shooting"])
            return got
        monkeypatch.setattr(Link, "download", downloaded)
        monkeypatch.setattr(Link, "upload", uploaded)
        monkeypatch.setattr(time, "monotonic", lambda: self.t)
        monkeypatch.setattr(time, "sleep", self.sleep)
        monkeypatch.setattr(screen, "read", lambda f: SimpleNamespace(kind=getattr(f, "kind", "unknown"), focus=None))
        monkeypatch.setattr(first_open, "seen_record", lambda camera=None: AllSeen())
        monkeypatch.setattr(vlm, "LOCAL_ONLY", vlm.LOCAL_ONLY)
        for mod in (drive, crawl_run):
            monkeypatch.setattr(mod, "check_readers", lambda: self.said.append("readers checked"))
            monkeypatch.setattr(mod, "eyes_from_config", lambda run: Eyes(self, self.eyes, run))
            monkeypatch.setattr(mod, "load_scan", self.load_scan)
            monkeypatch.setattr(mod, "LiveCamera", lambda link, eyes, run, **kw: Cam(self, link))
            monkeypatch.setattr(mod, "close_for_restore", lambda cam, link, start: self.said.append("closed"))
            monkeypatch.setattr(mod, "Run", self.new_run)
        for name, value in (("find_position", lambda cam, cycle, model: 0), ("go_to", lambda *a, **k: True),
                            ("enter_any", lambda cam, path, i: None),
                            ("screen_text", lambda cam, grip: "Drive Mode  Single Shooting"),
                            ("screen_lines", lambda cam, grip: ["Drive Mode", "Single Shooting"]),
                            ("highlighted", lambda image, path: "Drive Mode"),
                            ("page_labels", lambda now, cycle, model: []),
                            ("submenu_labels", lambda cam: ("page", [])),
                            ("after_armed", lambda cam, grip, kinds=None: ("list", "Single Shooting", ""))):
            monkeypatch.setattr(drive, name, value)
        monkeypatch.setattr(crawl_run, "crawl_from_menu", self.lap)

    # ------------------------------------------------------------------ the made-up seams

    def sleep(self, s):
        """time.sleep: the kit's sleeps on the main thread noted and the clock moved on at once; another thread's, and
        subprocess's own polls while a camlink exits, slept."""
        if threading.current_thread() is threading.main_thread() and \
                sys._getframe(1).f_globals.get("__name__") != "subprocess":
            self.slept.append(round(s, 2))
            self.t += max(float(s), 0.0)
        else:
            REAL_SLEEP(s)

    def kind_now(self) -> str:
        self.grabs += 1
        what = self.on_grab.pop(self.grabs, None)
        if what is not None:
            what()
        return self.kinds.popleft() if self.kinds else self.kind

    def load_scan(self, scan, **kw):
        session.MODE = self.mode
        return [], {}

    def new_run(self, name, **kw):
        run = Run(name, **kw)
        self.runs.append(run)
        return run

    @property
    def run(self) -> Run:
        return self.runs[-1]

    @property
    def marker(self) -> Path:
        return self.root / RESTORE_BY_HAND

    def stop(self) -> None:
        (self.run.dir / "STOP").write_text("", encoding="utf-8")

    def ctrl_c(self) -> None:
        """The first Ctrl-C once the link is open, as camkit.link's own handler takes it."""
        self.mp.setattr(camlink, "_RUNS", [self.run])
        camlink._on_signal(signal.SIGINT, None)

    def before_press(self, key) -> None:
        what = self.on_press.pop(key, None)
        if what == "stop":
            self.stop()
        elif what == "ctrl-c":
            self.ctrl_c()

    def lap(self, cam, link, *a, **k):
        """crawl_run.crawl_from_menu made up: MENU, Down, Up on the camera, then the menu closed (a cleanup MENU)."""
        for key in ("menu", "down", "up"):
            cam.press(key)
        link.press("menu", cleanup=True)
        return True

    def changes_end(self) -> None:
        """The end download differs from the start file in one record: a stand-in file the test makes, never uploaded
        (the upload is the start file, the camera's own download)."""
        cs = camset.read(fake_camlink.SAMPLE)
        rec = cs.get(0, 0x0489)
        changed = self.tmp / "changed.DAT"
        changed.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
        self.mp.setenv("FAKE_CAMLINK_DOWNLOADS", json.dumps({"_after": str(changed)}))

    def scope(self, *decisions) -> None:
        """The camera's reviewed scope with those decisions (runner.reviewed_scope)."""
        from proving import base
        pass1 = self.root / "kit2_pass1"
        self.mp.setattr(base, "PASS1", pass1)
        pass1.mkdir(parents=True, exist_ok=True)
        (pass1 / "pass2_scope_draft.json").write_text(json.dumps({"prove": [], "exclude": {},
                                                                  "decisions": list(decisions)}), encoding="utf-8")

    # ------------------------------------------------------------------ a run and what it left

    def main(self, module, *argv) -> tuple:
        """module.main() with these arguments: (its exit status, or the exception it raised; what it printed)."""
        self.mp.setattr(sys, "argv", [f"{module.__name__}.py", *argv])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                module.main()
                code = None
            except SystemExit as e:
                code = e.code
            except Exception as e:      # noqa: BLE001 (what the run raised is the result)
                code = e
        self.err = err.getvalue()
        return code, out.getvalue()

    def sent(self) -> list:
        """What reached camlink, every link's in turn: the command's verb, a download's or an upload's tag, a press's
        button."""
        if not self.log.exists():
            return []
        out = []
        for line in self.log.read_text(encoding="utf-8").splitlines():
            words = ast.literal_eval(line).decode().strip().split(" ")
            words = words[1:] if words[0].startswith("@") else words
            if words[0] in ("download", "upload"):
                name = words[2] if words[0] == "download" else Path(words[1].strip('"')).stem
                out.append(f"{words[0]} {name.strip(chr(34)).split('_', 1)[1]}")
            elif words[0] == "press":
                out.append(f"press {words[1]}")
            else:
                out.append(words[0])
        return out

    def events(self, *kinds) -> list:
        """The run's events.jsonl lines of those kinds (every one without), in order."""
        f = self.run.dir / "events.jsonl"
        lines = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []
        return [e for e in lines if not kinds or e["kind"] in kinds]

    def kinds_of(self, *kinds) -> list:
        return [e["kind"] for e in self.events(*kinds)]

    def result(self, name: str) -> dict:
        lines = (self.run.dir / name).read_text(encoding="utf-8").splitlines() if (self.run.dir / name).exists() else []
        return json.loads(lines[-1]) if lines else {}


@pytest.fixture
def camera(tmp_path, monkeypatch, own_runs):
    return Camera(tmp_path, monkeypatch, own_runs)


DRIVE = ("--path", "Drive Mode", "--press", "down", "--press", "up", "--run", "kit2_pin_drive")
CRAWL = ("--run", "kit2_pin_crawl")
SESSION_KINDS = ("link_open", "start_budget", "lock_wait", "link_close", "restore_wait", "restore_reconnected",
                 "restore_unreached", "stop_requested", "cmd_refused")
DRIVE_START = ["props", "props", "download before"]      # the camera named, its mode asked, the start download


# ---------------------------------------------------------------- the start and the end as they were

def test_a_drive_look_starts_and_ends_as_it_did(camera):
    """drive.py's look, nothing changed on the camera: the readers checked beside the eyes, then the link (the camera
    named, its mode asked), the start download, the menu's lock after it (4.5 s with no mode measured, LOCK_S), the
    presses, the --wait after them, the end download, nothing uploaded and no reconnection; no start line printed; the
    link's start budget and drive's own (the ledger's wait) in events.jsonl."""
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert camera.sent() == [*DRIVE_START, "press menu", "press down", "press up", "download after", "quit"]
    assert camera.slept == pytest.approx([4.5, 1.0], abs=0.05)
    assert camera.kinds_of(*SESSION_KINDS) == ["link_open", "start_budget", "start_budget", "lock_wait", "link_close"]
    first, ours = camera.events("start_budget")
    assert {"imports", "readers check waited", "link open"} <= set(first["phases"])
    assert set(ours["phases"]) == {"ledger waited"}
    assert camera.events("lock_wait")[0]["ended"] == "4.5 s"
    assert "start file: " not in out and "records differ from the start file" in out
    # the readers' check runs beside the eyes being made (either may come first), then the run
    assert sorted(camera.said[:2]) == ["eyes made", "readers checked"] and camera.said[2:] == ["closed", "eyes closed"]
    line = camera.result("drive.jsonl")
    assert line["completed"] is True and line["changes"] == [] and line["before"] == "00001_before.DAT"


def test_a_drive_look_with_hdmi_eyes_waits_the_lock_by_the_screen(camera):
    """HDMI eyes in a mode measured: the lock after the start download ends on the shooting screen after the saving
    notice (one poll), not 4.5 s."""
    camera.eyes, camera.mode, camera.notice = "hdmi", "Stills", True
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert camera.slept == pytest.approx([0.05, 1.0], abs=0.05)
    assert camera.events("lock_wait")[0]["ended"] == "the shooting screen after the notice"


def test_a_drive_that_meets_a_menu_closes_it_alone_before_its_start_download(camera):
    """A menu page on show at the start: one cleanup MENU, then the wait for the shooting screen (its grace covers the
    menu closing: no second slept), the start download."""
    camera.kinds.extend(["menu"])
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert camera.sent()[:4] == ["props", "press menu", "props", "download before"]
    assert camera.slept == pytest.approx([4.5, 1.0], abs=0.05)


def test_a_drive_that_changed_a_record_puts_the_start_file_back_and_checks_it(camera):
    """The end download differs: the start file is uploaded, the link closes, the check waits RESTART_FIRST s for the
    restart (OSD eyes need the link the upload closed), reconnects, gives the camera `ready` s, downloads and counts
    nothing differing: exit 0."""
    camera.changes_end()
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert camera.sent() == [*DRIVE_START, "press menu", "press down", "press up", "download after", "upload before",
                             "quit", "download restored", "quit"]
    assert camera.slept == pytest.approx([4.5, 1.0, 20.0, 3.0], abs=0.05)
    assert [e.get("waited_for") for e in camera.events("restore_wait")] == ["20 s"]
    assert "global:0x0489" in out and "after the restore: 0 records differ from the start file" in out
    assert camera.result("drive.jsonl")["changes"][0]["key"] == "global:0x0489"


def test_a_drive_with_hdmi_eyes_watches_the_restart_after_its_upload(camera):
    """The one change made on purpose: with HDMI eyes the check after the upload ends its wait on the shooting screen
    after the restart's notice (camkit.session.restarted), as every prover's check does, where it waited a fixed 20 s."""
    camera.eyes, camera.mode, camera.notice = "hdmi", "Stills", True
    camera.changes_end()
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert [e.get("waited_for") for e in camera.events("restore_wait")] == ["the shooting screen after the notice"]
    assert camera.slept == pytest.approx([0.05, 1.0, 0.25, 0.25, 3.0], abs=0.05)
    assert "after the restore: 0 records differ from the start file" in out


def test_a_drive_whose_check_does_not_take_exits_unrestored(camera, monkeypatch):
    """The start file uploaded and the camera still differing after it: exit EXIT_UNRESTORED (4)."""
    from exit_status import EXIT_UNRESTORED
    camera.changes_end()
    monkeypatch.setenv("FAKE_CAMLINK_DOWNLOADS", json.dumps({"_after": str(camera.tmp / "changed.DAT"),
                                                             "_restored": str(camera.tmp / "changed.DAT")}))
    code, out = camera.main(drive, *DRIVE)
    assert code == EXIT_UNRESTORED and "THE START FILE DID NOT TAKE" in out
    assert "after the restore: 1 records differ from the start file" in out


# ---------------------------------------------------------------- STOP and Ctrl-C

def test_a_stop_during_drives_start_wait_ends_the_run_there_with_nothing_downloaded(camera):
    """A dialog on show at the start (no MENU closes it: the wait asks for a hand) and the STOP file put down meanwhile:
    the wait ends with StopRequested once its grace is over, nothing downloaded or pressed, the link closed and the
    eyes too; no result line."""
    camera.kinds.extend(["dialog"] * 40)
    camera.on_grab[2] = camera.stop             # once the wait has begun (a STOP there before it ends no wait)
    code, out = camera.main(drive, *DRIVE)
    assert isinstance(code, StopRequested), (code, out)
    assert camera.sent() == ["props", "quit"]
    assert camera.slept and set(camera.slept) == {0.2} and sum(camera.slept) == pytest.approx(2.0, abs=0.25)
    assert "please close the menu by hand" not in out and camera.said[-1] == "eyes closed"
    assert camera.result("drive.jsonl") == {}


@pytest.mark.parametrize("how", ["stop", "ctrl-c"])
def test_a_stop_or_the_first_ctrl_c_during_drives_presses_cancels_and_restores(camera, how):
    """The STOP file, or the first Ctrl-C (camkit.link's handler asks the run to stop), before the second press: the link
    refuses it, the run cancels (its cleanup) and ends as ever, the end download made (a STOP holds for presses alone),
    the run's line saying it did not complete; exit 0, nothing having changed."""
    camera.on_press["up"] = how
    code, out = camera.main(drive, *DRIVE)
    assert code is None, (code, out)
    assert camera.sent() == [*DRIVE_START, "press menu", "press down", "download after", "quit"]
    assert "error: StopRequested" in out and "closed" in camera.said
    assert camera.result("drive.jsonl")["completed"] is False
    assert camera.kinds_of("stop_requested", "cmd_refused") == (["stop_requested", "cmd_refused"] if how == "ctrl-c"
                                                               else ["cmd_refused"])
    if how == "ctrl-c":
        assert "SIGINT: stopping cleanly" in camera.err


def test_a_stop_during_crawls_start_wait_ends_the_run_there_with_nothing_downloaded(camera):
    camera.kinds.extend(["dialog"] * 40)
    camera.on_grab[2] = camera.stop
    code, out = camera.main(crawl_run, *CRAWL)
    assert isinstance(code, StopRequested), (code, out)
    assert camera.sent() == ["props", "quit"] and set(camera.slept) == {0.2}
    assert camera.said[-1] == "eyes closed" and camera.result("rows.jsonl") == {}


@pytest.mark.parametrize("how", ["stop", "ctrl-c"])
def test_a_stop_or_the_first_ctrl_c_during_the_lap_cancels_and_restores(camera, how):
    """crawl_run.py: the lap's press refused for the stop, "STOP file: cancelling", the camera closed, the end download,
    exit 0 (a STOP ends a lap as asked)."""
    camera.on_press["up"] = how
    code, out = camera.main(crawl_run, *CRAWL)
    assert code is None, (code, out)
    assert camera.sent() == [*DRIVE_START, "press menu", "press down", "download after", "quit"]
    assert "STOP file: cancelling" in out and "closed" in camera.said


# ---------------------------------------------------------------- crawl_run.py

def test_a_crawl_starts_and_ends_as_it_did(camera):
    """crawl_run.py's lap, nothing changed: the start download said ("settings saved"), the ledger's gate and the first
    opens made while the menu's lock runs from the download's reply (4.5 s with no mode measured), the lap, the end
    download, nothing uploaded; the link's start budget and the gate's in events.jsonl."""
    code, out = camera.main(crawl_run, *CRAWL)
    assert code is None, (code, out)
    assert camera.sent() == [*DRIVE_START, "press menu", "press down", "press up", "press menu", "download after", "quit"]
    assert camera.slept == pytest.approx([4.5], abs=0.05)
    assert camera.kinds_of(*SESSION_KINDS) == ["link_open", "start_budget", "start_budget", "lock_wait", "link_close"]
    assert "settings saved: 00001_before.DAT" in out and "start file:" not in out
    first, ours = camera.events("start_budget")
    assert {"imports", "readers check waited", "link open"} <= set(first["phases"])
    assert set(ours["phases"]) == {"ledger waited"} and camera.events("lock_wait")[0]["ended"] == "4.5 s"
    assert sorted(camera.said[:2]) == ["eyes made", "readers checked"] and camera.said[2:] == ["eyes closed"]


def test_a_crawl_with_hdmi_eyes_waits_the_lock_by_the_screen_and_watches_the_restart(camera):
    camera.eyes, camera.mode, camera.notice = "hdmi", "Stills", True
    camera.changes_end()
    code, out = camera.main(crawl_run, *CRAWL)
    assert code is None, (code, out)
    assert camera.events("lock_wait")[0]["ended"] == "the shooting screen after the notice"
    assert [e.get("waited_for") for e in camera.events("restore_wait")] == ["the shooting screen after the notice"]
    assert camera.slept == pytest.approx([0.05, 0.25, 0.25, 3.0], abs=0.05)


def test_a_crawl_that_changed_a_record_puts_the_start_file_back_and_checks_it(camera):
    camera.changes_end()
    code, out = camera.main(crawl_run, *CRAWL)
    assert code is None, (code, out)
    assert camera.sent()[-5:] == ["download after", "upload before", "quit", "download restored", "quit"]
    assert camera.slept == pytest.approx([4.5, 20.0, 3.0], abs=0.05)


# ---------------------------------------------------------------- refusals before anything connects

@pytest.mark.parametrize("argv,said", [
    (("--path", "Drive Mode", "--press", "jump"), "jump"),
    (("--path", "Format"), "Format"),
    (("--path", "Drive Mode", "--allow", "Format"), "--allow 'Format'"),
    (("--path", "Drive Mode", "--network", "--info-ok", "Drive Mode=a b c d e f"), "--info-ok passes no notice"),
    (("--path", "Drive Mode", "--press", "c4set"), "--c4-press"),
])
def test_drives_refusals_come_before_anything_connects(camera, argv, said):
    code, out = camera.main(drive, *argv)
    assert said in str(code), code
    assert camera.sent() == [] and not camera.log.exists() and "eyes made" not in camera.said


@pytest.mark.parametrize("argv,said", [
    (("--panels", "--network"), "--panels opens no panel on a --network run"),
    (("--network", "--info-ok", "Drive Mode=a b c d e f"), "--info-ok passes no notice"),
])
def test_crawls_refusals_come_before_anything_connects(camera, argv, said):
    code, out = camera.main(crawl_run, *argv)
    assert said in str(code), code
    assert not camera.log.exists() and "eyes made" not in camera.said


def test_another_body_stops_the_run_before_its_start_download(camera, monkeypatch):
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "ModelName", "text": "ILCE-7M4"},
                                                         {"name": "SoftwareVersion", "text": "2.00"}]))
    for module, argv in ((drive, DRIVE), (crawl_run, CRAWL)):
        camera.log.unlink(missing_ok=True)
        code, out = camera.main(module, *argv)
        assert "the camera connected is ILCE-7M4_fw2.00" in str(code) and "nothing was sent" in str(code)
        assert camera.sent() == ["props", "quit"]


# ---------------------------------------------------------------- a look lap, and a first open

def test_a_drive_look_lap_asks_local_readers_keeps_no_value_and_its_folder_owner_only(camera):
    """--network: a look lap asks local readers only, its folder is owner-only, and its end and its check say the
    records that differ by their keys alone, never a value."""
    camera.scope(BLANK)
    camera.changes_end()
    code, out = camera.main(drive, *DRIVE, "--network")
    assert code is None, (code, out)
    assert vlm.LOCAL_ONLY is True
    assert "records: global:0x0489" in out and "global:0x0489: " not in out
    assert "after the restore: 0 records differ from the start file" in out
    assert camera.result("drive.jsonl")["changes"] == [{"key": "global:0x0489"}]
    if os.name == "posix":
        assert stat.S_IMODE(camera.run.dir.stat().st_mode) == 0o700


def test_a_crawl_look_lap_says_the_records_by_their_keys_alone(camera):
    camera.scope(BLANK)
    camera.changes_end()
    code, out = camera.main(crawl_run, *CRAWL, "--network")
    assert code is None, (code, out)
    assert vlm.LOCAL_ONLY is True and "records: global:0x0489" in out and "global:0x0489: " not in out


def test_a_drives_first_open_marks_before_its_press_and_clears_after_a_clean_check(camera, monkeypatch):
    """A row this body has not been seen to open, the owner's blank-cards statement given: RESTORE_BY_HAND written
    before its Right, the restore checked, the marker taken away and the row said seen from now on."""
    camera.scope(BLANK)
    monkeypatch.setattr(first_open, "seen_record", lambda camera=None: first_open.Seen(set()))
    code, out = camera.main(drive, "--path", "Drive Mode", "--press", "right", "--run", "kit2_pin_first")
    assert code is None, (code, out)
    assert camera.pressed[-1] == ("right", True) and not camera.marker.exists()
    assert "opens as any row from now on" in out


def test_a_drives_first_open_that_changed_a_record_keeps_the_marker_and_exits_5(camera, monkeypatch):
    """The first open changed a record: the start file goes back and its check reconnects as upload_check's does (the
    marker being there), the marker stays, exit EXIT_RESTORE_BY_HAND (5)."""
    from exit_status import EXIT_RESTORE_BY_HAND
    camera.scope(BLANK)
    camera.changes_end()
    monkeypatch.setattr(first_open, "seen_record", lambda camera=None: first_open.Seen(set()))
    code, out = camera.main(drive, "--path", "Drive Mode", "--press", "right", "--run", "kit2_pin_first")
    assert code == EXIT_RESTORE_BY_HAND, (code, out)
    assert camera.marker.exists() and "global:0x0489" in out and "put back and checked" in out
    assert camera.sent()[-4:] == ["upload before", "quit", "download restored", "quit"]
