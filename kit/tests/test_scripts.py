"""The kit's runners off the camera: drive.py's press arguments refused before anything connects, the shared session
end that restores its start file even when the shooting screen does not come back (docs/decisions/0015), the prover
session every prover in kit/provers/ runs, a blocker of pass 3 put back whatever part of its switch applied, and a
results file written whole. Fakes stand in for the link, the eyes and the camera; nothing talks to a camera."""
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, models, session  # noqa: E402
from camkit.link import StopRequested  # noqa: E402

import runner  # noqa: E402


# ---------------------------------------------------------------- drive.py's press arguments

@pytest.mark.parametrize("press", ["enter@367", "ms_enter@200", "right@232", "ms_right@232", "help@300", "c4set@1",
                                   "c4reset@1", "dial.front.1@200", "enter@367:Setting Reset"])
def test_key_at_y_takes_no_key_that_opens_chooses_or_turns(press):
    """"key@y" pressed its key up to 8 times with no Enter guard at all: "enter@367" sent Enter on whatever dialog
    stood there, Initialize's confirmation included (2026-11-07). Only cursor moves are taken in that form."""
    import drive
    assert "only moves the cursor" in drive.press_args_refused(["right", press])


@pytest.mark.parametrize("presses,words", [(["enter"], "Enter needs a regex"), (["ms_enter"], "Enter needs a regex"),
                                           (["dial.front.2"], "a dial turn needs a regex"),
                                           (["down@top"], "a screen row")])
def test_enter_of_either_kind_and_a_dial_need_a_regex(presses, words):
    """The multi-selector's centre is an Enter too: it needed no regex, and the help popup's check (In-Camera Guide,
    never Add to My Menu) looked at "enter" alone."""
    import drive
    assert words in drive.press_args_refused(presses)


@pytest.mark.parametrize("raw", [" enter", "enter ", "\tenter", '"enter"', "'enter'", "Enter", "ENTER", "еnter",
                                 "ｅｎｔｅｒ", '"ms_enter"', " Ms_Enter "])
def test_a_padded_quoted_upper_case_or_look_alike_enter_is_judged_as_enter(raw):
    """The link's parser drops spaces and quotes before it sends a button, so " enter" passed every Enter guard here
    (no regex, no lit-text, Initialize or confirmation check) and still reached the camera as Enter (review 1). The key
    is now folded once and judged, and sent, in that form."""
    import drive
    canon = drive.canonical_key(raw)
    assert canon in drive.ENTERS
    assert "Enter needs a regex" in drive.press_args_refused([raw])
    assert "only moves the cursor" in drive.press_args_refused([f"{raw}@367"])
    assert drive.parse_press(f"{raw}:Drive Mode") == (canon, None, "Drive Mode")
    assert drive.press_refused(raw, "Initialize", "Setting Reset Camera Settings Reset Initialize", "dialog", True)
    assert drive.press_refused(raw, "", "OK", "dialog")                  # an unreadable button: never Enter
    assert drive.press_refused(f" {raw} ", "OK", "Some Setting OK", "list") == ""


@pytest.mark.parametrize("raw", [" right", '"right"', "RIGHT", " ms_right"])
def test_a_padded_or_quoted_right_is_judged_as_right(raw):
    import drive
    assert drive.canonical_key(raw) in drive.RIGHTS
    assert "only moves the cursor" in drive.press_args_refused([f"{raw}@232"])
    assert drive.press_refused(raw, "", "", "menu")                       # an unreadable row is not opened
    assert drive.press_refused(raw, "Access Authen. Info", "", "submenu", allow=["Access Authen. Info"])


@pytest.mark.parametrize("raw", ["13", "c4", "C4@5", "fn", "playback", "delete", "movie", "en ter", "enterr", "",
                                 "dial.front", "dial.mode.1:x", "dial.front.x:Aspect", "help me"])
def test_anything_that_is_no_key_is_refused_before_connecting(raw):
    import drive
    assert "not a key drive.py sends" in drive.press_args_refused(["right", raw])
    assert drive.press_refused(raw, "OK", "OK", "list")


def test_a_screen_row_is_ascii_digits():
    import drive
    assert "a screen row" in drive.press_args_refused(["down@²"]) and "a screen row" in drive.press_args_refused(["down@-1"])
    assert drive.press_args_refused([" down @ 367 "]) == "" and drive.parse_press("Down@367") == ("down", "367", "")


def test_cursor_moves_and_guarded_presses_pass_the_argument_check():
    import drive
    assert drive.press_args_refused(["right", "down@367", "up@232:Ext. Flash", "enter:Flash Mode", "ms_enter:OK",
                                     "dial.front.1:Aspect", "help", "c4set:Custom 1"]) == ""


def test_drive_refuses_enter_at_y_before_it_connects():
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "drive.py"), "--path", "Drive Mode", "--press", "enter@367"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "only moves the cursor" in r.stderr


# ---------------------------------------------------------------- the session's end

def test_the_session_end_restores_when_the_shooting_screen_does_not_come(monkeypatch, capsys):
    """end_session: prove_run's to_shooting giving up (Failed after 5 minutes) or the feed gone (RuntimeError) once
    skipped finish, and the camera stayed changed. The restore is tried all the same."""
    from proving.base import Failed
    finished = []
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.session, "finish", lambda link, start, tag="after": finished.append((start, tag)) or "end")

    def gives_up(link, eyes, why):
        raise Failed(f"no shooting screen for {why} after MENU and 5 minutes")
    assert runner.end_session("link", "eyes", Path("start.DAT"), "the download", tag="x", reach=gives_up) == "end"
    assert finished == [(Path("start.DAT"), "x")] and "restoring all the same" in capsys.readouterr().out

    def feed_gone(link, eyes, why):
        raise RuntimeError("the capture stopped")
    runner.end_session("link", "eyes", Path("start.DAT"), reach=feed_gone)
    assert len(finished) == 2


STOPPED_WAIT = "STOP file: the wait for the shooting screen ends here; restoring all the same"


def test_a_stop_while_waiting_for_the_shooting_screen_still_restores(monkeypatch, capsys):
    """A STOP while the session's end waits for the shooting screen ends that wait as its other failures do, and the
    restore goes on (2026-11-08: it left the camera unrestored and exited EXIT_UNRESTORED)."""
    finished = []
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.session, "finish", lambda link, start, tag="after": finished.append((start, tag)) or "end")

    def stopped(link, eyes, why):
        raise StopRequested("a stop was asked for while waiting (a test) on a 'menu' screen: the wait ends here")
    assert runner.end_session("link", "eyes", Path("start.DAT"), tag="x", reach=stopped) == "end"
    assert finished == [(Path("start.DAT"), "x")]
    out = capsys.readouterr().out
    assert STOPPED_WAIT in out and "may not be on its start file" not in out


def test_a_stop_in_the_last_wait_restores_with_the_link_and_still_refuses_presses(tmp_path, monkeypatch, capsys):
    """Through the link (the stand-in camlink) with the run's STOP file there: the end download and the start file's
    upload go out, as a restore needs, and a press is still refused."""
    import camkit.link as L
    from camkit import camset
    from camkit.runs import Run
    fake = [sys.executable, "-X", "utf8", str(Path(__file__).resolve().parent / "fake_camlink.py")]
    sample = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
    cs = camset.read(sample)
    rec = cs.get(0, 0x0489)
    changed = tmp_path / "changed.DAT"                 # the stand-in's end download, one record apart; never sent
    changed.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
    monkeypatch.setenv("FAKE_CAMLINK_AFTER", str(changed))
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(tmp_path / "received.txt"))
    monkeypatch.delenv("CAMSET_USB", raising=False)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    run = Run("kit2_stop", root=tmp_path / "runs" / "TEST-CAM_fw9.99")

    def stop_arrives(link, eyes, why):
        (run.dir / "STOP").write_text("", encoding="utf-8")
        raise StopRequested("a stop was asked for while waiting")
    with L.Link(run, ip="192.0.2.10", binary=fake, catch_signals=False) as lk:
        start = lk.download("before")
        ending = runner.end_session(lk, "eyes", start, reach=stop_arrives)
        assert ending.uploaded and [c.key for c in ending.changes] == ["global:0x0489"]
        with pytest.raises(StopRequested):
            lk.press("down", screen="menu")
    sent = (tmp_path / "received.txt").read_text(encoding="utf-8")
    assert " upload " in sent and start.name in sent and "press down" not in sent
    assert STOPPED_WAIT in capsys.readouterr().out


def test_a_prover_stopped_in_its_last_wait_restores_and_exits_restored(monkeypatch, capsys):
    """prover_session: a STOP while the session's end waits for the shooting screen. The start file goes back on
    (finish) and its restore is checked; when it took, the prover does not exit EXIT_UNRESTORED."""
    import proving.nav
    log, eyes = _prover_world(monkeypatch), FakeEyes()

    def to_shooting(link, eyes, why):
        if why == "the settings download after the rows":           # the session's end, not the start download
            raise StopRequested("a stop was asked for while waiting")
    monkeypatch.setattr(proving.nav, "to_shooting", to_shooting)
    with runner.prover_session("run", eyes) as s:
        pass
    assert s.restored is True and log["finished"] == [s.start] and log["checked"] == [s.start] and eyes.closed == 1
    assert STOPPED_WAIT in capsys.readouterr().out


def test_an_upload_that_fails_in_the_restore_exits_unrestored(monkeypatch, capsys):
    """finish's upload refused or unanswered (a LinkError) was a traceback, exit 1, and the chain went on."""
    from camkit.link import LinkError
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    def refused(link, start, tag="after"):
        raise LinkError("upload: no reply in 150 s")
    monkeypatch.setattr(runner.session, "finish", refused)
    with pytest.raises(SystemExit) as stop:
        runner.end_session("link", "eyes", Path("start.DAT"), reach=lambda link, eyes, why: None)
    assert stop.value.code == runner.EXIT_UNRESTORED
    assert "LinkError: upload: no reply in 150 s" in capsys.readouterr().out


def test_a_close_that_gives_up_exits_unrestored_without_a_restore(monkeypatch, capsys):
    """camkit.live.close's SystemExit (8 tries, "close it on the camera by hand") passed through close_for_restore
    as exit 1. With no screen to judge (this camera has no frame), it exits EXIT_UNRESTORED, with no restore tried
    over a screen it could not close."""
    from proving.base import Failed
    log, eyes = _prover_world(monkeypatch), FakeEyes()

    def gives_up(cam, link):
        raise SystemExit("could not get back to the shooting screen: please close it on the camera by hand")
    monkeypatch.setattr(runner, "close", gives_up)
    with pytest.raises(SystemExit) as stop, runner.prover_session("run", eyes):
        raise Failed("the cursor is not on 'ISO 400'")
    assert stop.value.code == runner.EXIT_UNRESTORED and log["finished"] == [] and eyes.closed == 1
    assert "please close it on the camera by hand" in capsys.readouterr().out


GAVE_UP = "could not get back to the shooting screen: please close it on the camera by hand"


def last_screen(kind, text="Grid Line Display  Rule of 3rds Grid  Square Grid  Diag. + Square Grid  Off"):
    """A camera whose last frame the reader read as `kind`, OCR reading `text` on it (an exception: no text)."""
    return types.SimpleNamespace(read=lambda: types.SimpleNamespace(kind=kind), frame=None, text=text)


def gives_up_on(monkeypatch, cam, how=SystemExit):
    def close(c, link):
        raise how(GAVE_UP)
    monkeypatch.setattr(runner, "close", close)

    def text_of(c):
        if isinstance(c.text, Exception):
            raise c.text
        return c.text
    monkeypatch.setattr(runner, "text_of", text_of)


@pytest.mark.parametrize("kind", sorted(runner.RESTORABLE_KINDS))
@pytest.mark.parametrize("how", [SystemExit, runner.CloseGaveUp])
def test_a_close_that_gives_up_on_a_known_screen_restores_all_the_same(monkeypatch, capsys, kind, how):
    """2026-11-08 (the owner, after a restore over an open option list checked out on the camera): when camkit.live.close
    gives up on a screen the reader knows that reads as no confirmation, the session goes on to its restore."""
    cam = last_screen(kind)
    gives_up_on(monkeypatch, cam, how)
    runner.close_for_restore(cam, "link")
    assert f"closing gave up on a {kind} screen; restoring all the same" in capsys.readouterr().out


@pytest.mark.parametrize("cam,why", [
    (last_screen("unknown"), "reads as 'unknown', not a menu, list, panel or notice"),
    (last_screen("dialog"), "reads as 'dialog'"),
    (last_screen("picker"), "reads as 'picker'"),
    (last_screen("list", "Format  Execute  Cancel  All data will be deleted. Format?"), "reads as a confirmation"),
    (last_screen("notice", "Initialize? Execute"), "reads as a confirmation"),
    (last_screen("menu", ""), "no text could be read"),
    (last_screen("list", RuntimeError("the capture stopped")), "cannot be read (RuntimeError: the capture stopped)"),
    (types.SimpleNamespace(read=lambda: (_ for _ in ()).throw(RuntimeError("no frame")), text=""),
     "its last screen cannot be read (RuntimeError: no frame)"),
])
@pytest.mark.parametrize("how", [SystemExit, runner.CloseGaveUp])
def test_a_close_that_gives_up_elsewhere_exits_unrestored(monkeypatch, capsys, cam, why, how):
    """An unknown screen, a dialog, a confirmation or no readable frame: as before, no restore is tried over it, the
    run says so and exits EXIT_UNRESTORED, and a person looks."""
    gives_up_on(monkeypatch, cam, how)
    with pytest.raises(SystemExit) as stop:
        runner.close_for_restore(cam, "link")
    assert stop.value.code == runner.EXIT_UNRESTORED
    out = capsys.readouterr().out
    assert why in out and "no restore is tried over it" in out and "may not be on its start file" in out


def test_a_prover_whose_close_gives_up_on_an_open_list_restores_and_exits_restored(monkeypatch, capsys):
    """Through prover_session: the body fails, closing gives up on an open option list, the start file goes back on
    and the restore is checked; the run exits as restored."""
    from proving.base import Failed
    log, eyes = _prover_world(monkeypatch), FakeEyes()
    cam = last_screen("list")
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, run, may_open=(): cam)
    gives_up_on(monkeypatch, cam)
    with runner.prover_session("run", eyes) as s:
        raise Failed("the cursor is not on 'Square Grid'")
    assert s.restored is True and log["finished"] == [s.start] and log["checked"] == [s.start]
    assert "closing gave up on a list screen; restoring all the same" in capsys.readouterr().out


def test_a_close_in_a_body_that_gives_up_is_an_error_the_session_restores_after(monkeypatch, capsys):
    """camkit.live.close's SystemExit inside a prover's body (its own close after a look) ended the process with exit
    1 and no restore (review 4). close_screen makes it CloseGaveUp, which prover_session takes as any failed body:
    closed again, and the start file restored."""
    log, eyes = _prover_world(monkeypatch), FakeEyes()
    calls = []

    def gives_up_once(cam, link):
        calls.append(cam)
        if len(calls) == 1:
            raise SystemExit("could not get back to the shooting screen: please close it on the camera by hand")
    monkeypatch.setattr(runner, "close", gives_up_once)
    with runner.prover_session("run", eyes) as s:
        runner.close_screen(s.cam, s.link)                   # the body's own close, as boxes_run's look does
    assert len(calls) == 2 and log["finished"] == [s.start] and s.restored is True
    assert "stopped: CloseGaveUp: could not get back" in capsys.readouterr().out
    monkeypatch.setattr(runner, "close", lambda cam, link: (_ for _ in ()).throw(SystemExit(0)))
    with pytest.raises(SystemExit) as done:                  # a plain exit 0 is left as it is
        runner.close_screen(None, None)
    assert done.value.code == 0


def test_pass_threes_restore_that_cannot_connect_exits_unrestored(monkeypatch):
    import pass3_run
    from camkit.link import LinkError

    def no_link(run):
        raise LinkError("the camera does not answer")
    monkeypatch.setattr(pass3_run, "Link", no_link)
    monkeypatch.setattr(pass3_run, "eyes_from_config", lambda run: FakeEyes())
    with pytest.raises(SystemExit) as stop:
        pass3_run.restore("run", Path("00001_p3-start.DAT"))
    assert stop.value.code == runner.EXIT_UNRESTORED


class FakeLink:
    def __init__(self, run, downloads):
        self.run, self.downloads = run, downloads

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, tag):
        self.downloads.append(tag)
        return Path(f"0000{len(self.downloads)}_{tag}.DAT")


class FakeEyes:
    def __init__(self):
        self.closed = 0

    def attach(self, link):
        pass

    def close(self):
        self.closed += 1


def _prover_world(monkeypatch, uploaded=True, restored=0):
    import proving.nav
    log = {"downloads": [], "closed": [], "finished": [], "checked": []}
    monkeypatch.setattr(runner, "check_readers", lambda: None)      # readers listed (the check's own test is below)
    monkeypatch.setattr(runner, "Link", lambda run: FakeLink(run, log["downloads"]))
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, run, may_open=(): types.SimpleNamespace(may_open=may_open))
    monkeypatch.setattr(runner, "close", lambda cam, link: log["closed"].append(cam))
    monkeypatch.setattr(proving.nav, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    ending = session.Ending(Path("after.DAT"), ["a change"], uploaded)
    monkeypatch.setattr(runner.session, "finish", lambda link, start, tag="after": log["finished"].append(start) or ending)
    monkeypatch.setattr(runner.session, "check_restore", lambda run, e, start: log["checked"].append(start) or restored)
    return log


def test_a_prover_session_closes_and_restores_after_its_body_fails(monkeypatch, capsys):
    """prover_session: the session every prover ran by hand. A body that fails is said and the camera closed, the start
    file goes back on (finish) and the restore is checked; the eyes are closed."""
    from proving.base import Failed
    log, eyes = _prover_world(monkeypatch), FakeEyes()
    with runner.prover_session("run", eyes, may_open={"Reg. Custom Shoot Set"}) as s:
        assert s.start.name == "00001_before.DAT" and s.cam.may_open == {"Reg. Custom Shoot Set"}
        raise Failed("the cursor is not on 'ISO 400'")
    said = capsys.readouterr().out
    assert "stopped: Failed: the cursor is not on" in said and len(log["closed"]) == 1
    assert log["finished"] == [s.start] and log["checked"] == [s.start] and eyes.closed == 1


def test_a_prover_session_with_no_reader_listed_presses_nothing(tmp_path, monkeypatch):
    """private/config.json lists no reader: the session stops before it opens the link (camkit.vlm.check_readers),
    saying what to put there, so nothing is pressed, downloaded or uploaded, and the eyes are closed. Until 2026-11-13
    such a session opened the link and went on with OCR alone."""
    import camkit
    from camkit import vlm
    log, eyes = _prover_world(monkeypatch), FakeEyes()
    monkeypatch.setattr(runner, "check_readers", vlm.check_readers)       # the real check, which _prover_world stubs
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    camkit.CONFIG.write_text(json.dumps({"eyes": "osd", "readers": []}), encoding="utf-8")
    opened = []
    monkeypatch.setattr(runner, "Link", lambda run: opened.append(run))
    with pytest.raises(camkit.ConfigMissing, match="lists no reader"), runner.prover_session("run", eyes):
        raise AssertionError("the session's body ran")
    assert opened == [] and log["downloads"] == [] and eyes.closed == 1


def test_a_crawl_with_no_reader_listed_presses_nothing(tmp_path, monkeypatch):
    """crawl_run with no reader listed stops before its eyes or its link open (check_readers), saying what to do."""
    import camkit
    import crawl_run

    def never(*a, **k):
        raise AssertionError("the crawl opened its eyes or the link")
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    camkit.CONFIG.write_text(json.dumps({"eyes": "osd", "readers": []}), encoding="utf-8")
    monkeypatch.setattr(crawl_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(crawl_run, "eyes_from_config", never)
    monkeypatch.setattr(crawl_run, "Link", never)
    monkeypatch.setattr(sys, "argv", ["crawl_run.py"])
    with pytest.raises(camkit.ConfigMissing, match="lists no reader"):
        crawl_run.main()


def test_a_reader_missing_mid_run_is_a_failure_the_session_closes_and_restores_after(tmp_path, monkeypatch, capsys):
    """Inside a run a missing reader list is an ordinary exception (camkit.vlm.NoReader), never a SystemExit that would
    skip the cleanup: a walker's question takes it as a reader that could not answer and goes on with OCR alone
    (live.reader_label: no label, and why), and one that reaches the session's body is said, the camera closed
    (close_for_restore) and the start file put back and checked (end_session), as after any failure."""
    from camkit import live, vlm
    log, eyes = _prover_world(monkeypatch), FakeEyes()
    monkeypatch.setattr(vlm, "config", lambda: {"readers": []})
    monkeypatch.setattr(vlm, "_STANDING_IN", {})
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"a frame")
    with runner.prover_session("run", eyes) as s:
        label, why = live.reader_label(frame)
        assert label == "" and "NoReader" in why and "lists no reader" in why
        vlm.ask_role("second", b"a frame", "prompt", 5)
    said = capsys.readouterr().out
    assert "stopped: NoReader: private/config.json lists no reader" in said and len(log["closed"]) == 1
    assert log["finished"] == [s.start] and log["checked"] == [s.start] and s.restored is True and eyes.closed == 1


def test_every_run_that_drives_the_menus_checks_its_readers_before_its_link():
    """Every script that builds a LiveCamera, whose walkers ask the readers, calls camkit.vlm.check_readers before it
    opens the link for that camera, and runner.prover_session does it for every prover: a config that lists no reader
    stops the run before anything is pressed. A restore (mode_switch --restore, pass 3's restore()) asks nothing of a
    reader and is not checked; prove_run checks only when it has rows to prove, so with none its start file (--start)
    goes back with no reader (the test below)."""
    builders = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kit").rglob("*.py")
                      if "tests" not in p.parts and p.parent.name != "camkit" and "__pycache__" not in p.parts
                      and "LiveCamera(" in p.read_text(encoding="utf-8"))
    assert "kit/runner.py" in builders and "kit/crawl_run.py" in builders and len(builders) >= 15
    for rel in builders:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "from camkit.vlm import check_readers" in text and "check_readers()" in text, rel
    session = (ROOT / "kit" / "runner.py").read_text(encoding="utf-8").split("def prover_session", 1)[1]
    assert session.index("check_readers()") < session.index("with Link(run) as link:")


def test_prove_run_puts_its_start_file_back_with_no_reader_when_nothing_is_left(tmp_path, monkeypatch):
    """prove_run --start FILE with no reader listed: when no row is left to prove, no reader is asked, so the start
    file goes back all the same (a put-back never needs a reader); with a row to prove, the run stops before its eyes
    or the link open (check_readers), and nothing is touched."""
    import camkit
    import prove_run
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    camkit.CONFIG.write_text(json.dumps({"eyes": "osd", "readers": []}), encoding="utf-8")
    put_back, eyes = [], []
    monkeypatch.setattr(prove_run.models, "current", lambda root: models.A1II)
    monkeypatch.setattr(prove_run, "jobs", lambda scope=None: [])
    monkeypatch.setattr(prove_run, "axis_jobs", lambda scope=None: [])
    monkeypatch.setattr(prove_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(prove_run, "eyes_from_config", lambda run: eyes.append(FakeEyes()) or eyes[-1])
    monkeypatch.setattr(prove_run, "put_start_back", lambda run, hdmi, ref: put_back.append(ref.name) or True)
    monkeypatch.setattr(prove_run, "Link", lambda run: (_ for _ in ()).throw(AssertionError("a session's link")))
    start = tmp_path / "00007_start.DAT"
    start.write_bytes(b"a settings file")
    monkeypatch.setattr(sys, "argv", ["prove_run.py", "--start", str(start)])
    prove_run.main()
    assert put_back == ["00007_start.DAT"] and len(eyes) == 1 and eyes[0].closed == 1
    row = {"kind": "list", "path": ["Drive Mode"], "labels": ["Single Shooting", "Continuous Shooting"]}
    monkeypatch.setattr(prove_run, "jobs", lambda scope=None: [row])
    with pytest.raises(camkit.ConfigMissing, match="lists no reader"):
        prove_run.main()
    assert put_back == ["00007_start.DAT"] and len(eyes) == 1


def test_the_batch_tools_stop_with_a_sentence_when_no_reader_fits(tmp_path, monkeypatch):
    """The batch tools that read a run's saved frames with no camera (pass1_labels, tiebreak) stop with a sentence,
    not a traceback, when private/config.json lists no reader, before anything is read; and tiebreak, whose third
    reader is the second one listed (or the one "roles" names), says so when only one is listed."""
    import camkit
    import pass1_labels
    import tiebreak
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    camkit.CONFIG.write_text(json.dumps({"readers": []}), encoding="utf-8")
    (tmp_path / "rows.jsonl").write_text(json.dumps({"label": "Drive Mode", "kind": "list", "frames": ["00001_r.png"]})
                                         + "\n", encoding="utf-8")

    def never(*a, **k):
        raise AssertionError("a frame was read")
    monkeypatch.setattr(pass1_labels, "read_frames", never)
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(tmp_path)])
    with pytest.raises(camkit.ConfigMissing, match="lists no reader"):
        pass1_labels.main()
    monkeypatch.setattr(sys, "argv", ["tiebreak.py", str(tmp_path)])
    with pytest.raises(camkit.ConfigMissing, match="lists no reader"):
        tiebreak.main()
    one = {"name": "omlx", "url": "http://127.0.0.1:8000/v1", "model": "m"}
    camkit.CONFIG.write_text(json.dumps({"readers": [one]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="lists one reader, and the third role needs another"):
        tiebreak.main()
    assert not (tmp_path / "tiebreak.jsonl").exists()


def test_a_prover_session_says_when_the_restore_did_not_take(monkeypatch, capsys):
    """A start file that did not take is said, and the prover exits 1 (a chain stops there), unless it has a second
    session to run (customshoot's put the working copy back)."""
    log, eyes = _prover_world(monkeypatch, restored=3), FakeEyes()
    with runner.prover_session("run", eyes, note="the start file left records apart", close_eyes=False,
                               exit_unrestored=False) as s:
        pass
    assert s.restored is False                    # carried to the prover's own exit after its second session
    assert "the start file left records apart" in capsys.readouterr().out
    assert log["closed"] == [] and eyes.closed == 0
    with pytest.raises(SystemExit) as stop, runner.prover_session("run", eyes):
        pass
    assert stop.value.code == runner.EXIT_UNRESTORED and eyes.closed == 1


def test_a_prover_session_restores_when_closing_fails_too(monkeypatch, capsys):
    """An unguarded close after the body failed (the eyes' feed gone: a RuntimeError) skipped the restore, where
    bracket_run had guarded it (review 1). The restore is tried all the same."""
    log, eyes = _prover_world(monkeypatch), FakeEyes()

    def feed_gone(cam, link):
        raise RuntimeError("the capture stopped")
    monkeypatch.setattr(runner, "close", feed_gone)
    with runner.prover_session("run", eyes) as s:
        raise StopRequested("STOP file")
    assert s.restored is True
    said = capsys.readouterr().out
    assert "stopped: StopRequested" in said and "closing: RuntimeError" in said and "restoring all the same" in said
    assert log["finished"] == [s.start] and log["checked"] == [s.start] and eyes.closed == 1


# ---------------------------------------------------------------- pass 3: a blocker's switch put back

def test_a_blocker_whose_switch_failed_part_way_is_put_back(monkeypatch, capsys):
    """pass3_run: a Failed after the switch applied (the second of a blocker's "first" states, a choice before
    to_shooting gave up) went on to the next blocker with the camera switched; only a RuntimeError was put back. Now
    every failure after the start download restores the start file, and a restore that does not check out stops."""
    import pass3_run
    from proving.base import Failed
    restored, switched = [], []
    monkeypatch.setattr(pass3_run, "Link", lambda run: FakeLink(run, []))
    monkeypatch.setattr(pass3_run, "eyes_from_config", lambda run: FakeEyes())
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(pass3_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(pass3_run.camset, "read", lambda p: types.SimpleNamespace(model=models.A1II, get=lambda *a: None))

    def enter_state(link, hdmi, run, cycle, model, b):
        switched.append(b["to"])
        raise Failed("no shooting screen for after the switch after MENU and 5 minutes")
    monkeypatch.setattr(pass3_run, "enter_state", enter_state)
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: restored.append(start.name) or 0)
    blockers = [{"row": ["Drive Mode"], "to": "Continuous Shooting", "walk": "x"},
                {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "y"}]
    pass3_run.run_blockers("run", [], {}, blockers, None)
    assert switched == ["Continuous Shooting", "Mechanical Shutter"]
    assert restored == ["00001_p3-start.DAT", "00001_p3-start.DAT"]
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: restored.append(start.name) or 2)
    restored.clear()
    switched.clear()
    pass3_run.run_blockers("run", [], {}, blockers, None)
    assert switched == ["Continuous Shooting"] and "the camera may still be switched" in capsys.readouterr().out
    # a STOP (or a first Ctrl-C) at a press of the switch: cancelled with cleanup presses, the start file put back,
    # and the run stops there, as the STOP file asks (review 1: it escaped with the switch's list still open)
    cancels = []
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, eyes, why: cancels.append(why))
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: restored.append(start.name) or 0)

    def stopped(link, hdmi, run, cycle, model, b):
        switched.append(b["to"])
        raise StopRequested("STOP file")
    monkeypatch.setattr(pass3_run, "enter_state", stopped)
    restored.clear()
    switched.clear()
    pass3_run.run_blockers("run", [], {}, blockers, None)
    assert switched == ["Continuous Shooting"] and restored == ["00001_p3-start.DAT"]
    assert "the cancel after a stop" in cancels and "as the STOP file asks" in capsys.readouterr().out


# ---------------------------------------------------------------- page_scan: the restore after a scan that stopped

def test_a_page_scan_that_stops_still_restores(monkeypatch, capsys):
    """page_scan: an exception inside the scan (a STOP at a press, a dropped link) left the with block before finish."""
    import page_scan

    class Stops:
        def __init__(self, *a):
            pass

        def run_scan(self):
            raise StopRequested("STOP file")
    ended = []
    monkeypatch.setattr(page_scan, "Scan", Stops)
    monkeypatch.setattr(page_scan, "Link", lambda run: FakeLink(run, []))
    monkeypatch.setattr(page_scan, "eyes_from_config", lambda run: FakeEyes())
    monkeypatch.setattr(page_scan, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(page_scan, "after_download", lambda eyes, t: None)
    monkeypatch.setattr(page_scan, "end_session", lambda link, eyes, start, why: ended.append(start.name)
                        or session.Ending(Path("after.DAT")))
    monkeypatch.setattr(sys, "argv", ["page_scan.py", "--run", "kit2_scan_test", "--mode", "Stills"])
    page_scan.main()
    assert ended == ["00001_before.DAT"] and "the scan stopped: StopRequested" in capsys.readouterr().out
    # a restore that did not check out ends the walk with the runners' own exit status (runner.EXIT_UNRESTORED)
    monkeypatch.setattr(page_scan, "restore_checked", lambda run, ending, start: False)
    with pytest.raises(SystemExit) as stop:
        page_scan.main()
    assert stop.value.code == runner.EXIT_UNRESTORED


def test_a_frame_the_ocr_helper_cannot_read_is_named_not_taken_for_one_without_text(tmp_path, monkeypatch):
    """camkit.ocr.read now raises when the Apple helper cannot read a frame (a line carrying "error"), where the frame
    came back without text before: one torn PNG would end pass1_labels' batch of thousands. read_frames reads the
    others and names the one, with the helper's reason, for the caller to record as unread."""
    from camkit import ocr
    good, bad = tmp_path / "00001_down.png", tmp_path / "00002_down.png"
    good.write_bytes(b"good frame")
    bad.write_bytes(b"torn frame")

    def helper(cmd, **kw):
        out = []
        for f in cmd[1:]:
            if f.endswith("00002_down.png"):
                out.append(json.dumps({"file": f, "error": "could not load the image"}))
            else:
                out.append(json.dumps({"file": f, "lines": [{"text": "Drive Mode", "conf": 0.99, "x": 140, "y": 212,
                                                              "w": 200, "h": 30}]}))
        return types.SimpleNamespace(stdout="\n".join(out) + "\n")
    monkeypatch.setattr(ocr.subprocess, "run", helper)
    lines, unread = runner.read_frames([good, bad], "apple")
    assert [ln.text for ln in lines[good]] == ["Drive Mode"] and bad not in lines
    assert list(unread) == [bad] and "could not load the image" in unread[bad]
    lines, unread = runner.read_frames([good], "apple")                  # nothing failed: one batch
    assert unread == {} and good in lines


@pytest.mark.parametrize("error", [ImportError("No module named 'rapidocr_onnxruntime'"),
                                   FileNotFoundError(2, "No such file or directory", "/kit/ocr/build/ocr"),
                                   RuntimeError("the OCR helper could not read every frame")])
def test_an_ocr_engine_that_cannot_run_is_not_every_frame_unread(tmp_path, monkeypatch, error):
    """An engine that will not run (its library missing, its helper missing, not one frame read) once marked every
    frame unread, and pass1_labels and page_model wrote their files over the old ones with nothing read (review 4):
    it is OcrUnavailable, and the callers stop before writing."""
    from camkit import ocr
    frames = [tmp_path / "a.png", tmp_path / "b.png"]

    def read(paths, eng=None):
        raise error
    monkeypatch.setattr(ocr, "read", read)
    with pytest.raises(runner.OcrUnavailable):
        runner.read_frames(frames, "apple")


def test_pass1_labels_and_page_model_stop_before_writing_when_the_ocr_engine_cannot_run(tmp_path, monkeypatch):
    import page_model
    import pass1_labels

    def unavailable(paths, eng=None):
        raise runner.OcrUnavailable("the OCR helper is not there (/kit/ocr/build/ocr): build it with kit/setup.py")
    (tmp_path / "rows.jsonl").write_text(json.dumps({"label": "Drive Mode", "kind": "list", "frames": ["00001_r.png"]})
                                         + "\n", encoding="utf-8")
    (tmp_path / "options.jsonl").write_text('{"frame": "kept"}\n', encoding="utf-8")
    monkeypatch.setattr(pass1_labels, "read_frames", unavailable)
    monkeypatch.setattr(pass1_labels, "readers", lambda stop=False: [{}])        # a reader listed
    monkeypatch.setattr(pass1_labels, "role", lambda name: {})
    monkeypatch.setattr(pass1_labels, "make_reader", lambda cfg: None)
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(tmp_path)])
    with pytest.raises(SystemExit, match="options.jsonl left as it is"):
        pass1_labels.main()
    assert (tmp_path / "options.jsonl").read_text(encoding="utf-8") == '{"frame": "kept"}\n'
    (tmp_path / "scan_rekeyed.json").write_text(json.dumps([{"kind": "menu", "page": "p1", "frame": "00001_r.png"}]),
                                                encoding="utf-8")
    (tmp_path / "model.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(page_model, "read_frames", unavailable)
    monkeypatch.setattr(sys, "argv", ["page_model.py", str(tmp_path)])
    with pytest.raises(SystemExit, match="model.json left as it is"):
        page_model.main()
    assert (tmp_path / "model.json").read_text(encoding="utf-8") == "[]"


def test_an_engine_error_of_any_kind_leaves_one_frame_unread(tmp_path, monkeypatch):
    """RapidOCR (the first engine on Linux and Windows) raises its own LoadImageError, a plain Exception, for an image
    it cannot load: that frame is unread too, and the batch goes on (review 3)."""
    from camkit import ocr
    good, bad = tmp_path / "a.png", tmp_path / "b.png"

    class LoadImageError(Exception):
        pass

    def read(paths, eng=None):
        if any(p == bad for p in paths):
            raise LoadImageError(f"{bad} is not an image")
        return {p: [] for p in paths}
    monkeypatch.setattr(ocr, "read", read)
    lines, unread = runner.read_frames([good, bad], "rapidocr")
    assert list(lines) == [good] and "LoadImageError" in unread[bad]


def test_the_report_is_not_made_without_proofs(tmp_path):
    """pass2_report on a folder with no proofs.jsonl wrote an empty report over the one before (review 2)."""
    (tmp_path / "report.json").write_text('[{"row": "kept"}]', encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(tmp_path), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0 and "no proofs.jsonl" in r.stderr
    assert (tmp_path / "report.json").read_text(encoding="utf-8") == '[{"row": "kept"}]'


def test_a_symbolic_link_is_written_through(tmp_path):
    target = tmp_path / "real.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:                  # Windows without Developer Mode or administrator rights makes no links
        pytest.skip("no symbolic links here")
    runner.write_json(link, {"written": True})
    assert link.is_symlink() and json.loads(target.read_text(encoding="utf-8")) == {"written": True}


# ---------------------------------------------------------------- files written whole, the page scan loaded

def test_a_results_file_is_written_whole_or_left_as_it_was(tmp_path, monkeypatch):
    """write_json: table_walk's tables.json (hours of walks) and the other results were rewritten in place, so a stop
    mid-write left them cut short. The new file replaces the old in one rename; a failure leaves the old one and no
    temporary file."""
    p = tmp_path / "tables.json"
    runner.write_json(p, {"Image Quality Settings": {"cells": []}}, indent=1)
    assert json.loads(p.read_text(encoding="utf-8")) == {"Image Quality Settings": {"cells": []}}

    def no_rename(src, dst):
        raise OSError("the disk filled up")
    monkeypatch.setattr(runner.os, "replace", no_rename)
    with pytest.raises(OSError):
        runner.write_json(p, {"lost": True})
    assert json.loads(p.read_text(encoding="utf-8")) == {"Image Quality Settings": {"cells": []}}
    assert [x.name for x in tmp_path.iterdir()] == ["tables.json"]


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no Unix permission bits: a file there is read-only or "
                    "not, and the one mkstemp makes is writable as any other, so there is no owner-only file to undo")
def test_a_file_written_whole_keeps_its_permissions(tmp_path):
    """mkstemp makes its file 0600 and the rename kept that, so every results file turned owner-only (review 1)."""
    import os
    import stat
    p = tmp_path / "axes.json"
    p.write_text("{}", encoding="utf-8")
    os.chmod(p, 0o644)
    runner.write_json(p, {"Drive Mode": {}})
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o644
    new = tmp_path / "model.json"
    runner.write_json(new, [])
    mask = os.umask(0o022)
    os.umask(mask)
    assert stat.S_IMODE(os.stat(new).st_mode) == 0o666 & ~mask


def test_a_read_only_file_refused_leaves_no_temporary_file(tmp_path, monkeypatch):
    """Windows, faked: a read-only file is not replaced (os.replace refuses) and a read-only file is not deleted. The
    temporary file, made read-only as the file it stands in for, has its bit cleared before it is deleted, so nothing
    is left beside the file, which keeps its contents."""
    import os
    import stat
    p = tmp_path / "axes.json"
    p.write_text("{}", encoding="utf-8")
    os.chmod(p, 0o444)
    real_unlink = runner.os.unlink

    def replace(src, dst):
        raise PermissionError(5, "Access is denied", str(dst))

    def unlink(f):
        if not os.stat(f).st_mode & stat.S_IWRITE:
            raise PermissionError(5, "Access is denied", str(f))
        real_unlink(f)
    monkeypatch.setattr(runner.os, "replace", replace)
    monkeypatch.setattr(runner.os, "unlink", unlink)
    try:
        with pytest.raises(PermissionError):
            runner.write_json(p, {"Drive Mode": {}})
    finally:
        monkeypatch.undo()
        os.chmod(p, 0o644)
    assert [x.name for x in tmp_path.iterdir()] == ["axes.json"] and p.read_text(encoding="utf-8") == "{}"


def test_pass_one_steps_stop_without_their_input(tmp_path, monkeypatch):
    """camkit.jsonl.read gives [] for a missing file, where open() stopped: pass1_labels would then write an empty
    options.jsonl over the old one, and pass1_map an empty map over the crawl's own (review 1). Both stop and say so."""
    import pass1_labels
    import pass1_map
    (tmp_path / "options.jsonl").write_text('{"frame": "x"}\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["pass1_labels.py", str(tmp_path)])
    with pytest.raises(SystemExit, match="no rows.jsonl"):
        pass1_labels.main()
    assert (tmp_path / "options.jsonl").read_text(encoding="utf-8") == '{"frame": "x"}\n'
    with pytest.raises(SystemExit, match="no options.jsonl"):
        pass1_map.build(tmp_path / "elsewhere")


def test_the_page_scan_loads_with_each_position_read_again(tmp_path):
    """load_scan, once in every runner: the cycle without its last record (the first again), each position's screen read
    by today's reader, and the page model by key."""
    shots = tmp_path / "shots"
    shots.mkdir()
    Image.fromarray(np.zeros((480, 640, 3), np.uint8)).save(shots / "00001_down.png")
    (tmp_path / "scan_rekeyed.json").write_text(json.dumps(
        [{"frame": "00001_down.png", "page": "p1"}, {"frame": "00001_down.png", "page": "p2"},
         {"frame": "00001_down.png", "page": "p1"}]), encoding="utf-8")
    (tmp_path / "model.json").write_text(json.dumps([{"key": "p1", "rows": []}, {"key": "p2", "rows": []}]),
                                         encoding="utf-8")
    cycle, model = runner.load_scan(tmp_path)
    assert [p["page"] for p in cycle] == ["p1", "p2"] and set(model) == {"p1", "p2"}
    assert all(p["screen"].kind == p["kind"] and "signature" in p for p in cycle)


def test_the_proofs_file_closes_and_tags_each_line(tmp_path):
    run = types.SimpleNamespace(dir=tmp_path)
    with runner.proofs_file(run, "Movie mode") as out:
        out.write(json.dumps({"path": ["ISO"], "index": 1}) + "\n")
    assert json.loads((tmp_path / "proofs.jsonl").read_text(encoding="utf-8")) == {"path": ["ISO"], "index": 1,
                                                                                  "context": "Movie mode"}
    assert out.f.closed


# ---------------------------------------------------------------- the page scan a runner takes by default

def a_scan(root: Path, name: str, when: float, model: bool = True, mode: str = None) -> Path:
    """A made-up page scan folder: its lap (scan_rekeyed.json) written at `when`, its page model unless not, and the
    shooting mode it records (runner.SCAN_MODE_FILE) when one is given."""
    import os
    d = root / name
    d.mkdir(parents=True)
    (d / "scan_rekeyed.json").write_text("[]", encoding="utf-8")
    if model:
        (d / "model.json").write_text("[]", encoding="utf-8")
    if mode:
        runner.record_mode(d, mode)
    os.utime(d / "scan_rekeyed.json", (when, when))
    return d


def test_page_scans_are_ordered_by_the_lap_their_record_says_was_written(own_runs):
    """Review 4 (2026-11-11): runner.page_scans orders the scans by their record's "lap_written" (kept through a copy
    or a restore of the folders, which resets the files' times), and by the lap file's time only for a scan whose
    record has none."""
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    newer = a_scan(root, "scan_b", 1_000, mode="Stills")              # its file the oldest: copied back, say
    runner.write_json(newer / runner.SCAN_MODE_FILE, {"mode": "Stills", "lap": runner.LAP_WHOLE,
                                                      "lap_written": "2026-11-10 12:00:00"}, indent=1)
    older = a_scan(root, "scan_a", 9_000_000_000, mode="Stills")      # its file the newest
    runner.write_json(older / runner.SCAN_MODE_FILE, {"mode": "Stills", "lap": runner.LAP_WHOLE,
                                                      "lap_written": "2026-11-09 12:00:00"}, indent=1)
    plain = a_scan(root, "scan_c", 2_000, mode="Stills")              # no lap_written: its file's time
    assert runner.page_scans() == [plain, older, newer]


def test_the_default_scan_is_the_latest_of_the_mode_the_runner_works_in(own_runs):
    """--scan's default (runner.LATEST_SCAN) is the camera's latest page scan made in the shooting mode the runner works
    in, whatever its name: on the a1 II the newest scan is a Movie scan, which a Stills prover must never drive the
    menus by. A scan without its page model (load_scan reads both) is passed over, and so is a folder that is no scan."""
    import argparse
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    a_scan(root, "kit2_page_scan", 1_000, mode="Stills")
    stills = a_scan(root, "menus_after_the_update", 3_000, mode="stills")          # any case
    movie = a_scan(root, "kit2_page_scan_movie", 5_000, mode="Movie")              # the newest of all
    sq = a_scan(root, "kit2_page_scan_sq", 4_000, mode="S&Q Motion")               # Shoot Mode's own name for S&Q
    a_scan(root, "kit2_page_scan_2", 6_000, model=False, mode="Stills")           # a lap whose page model is not made yet
    (root / "kit2_pass2").mkdir()
    assert runner.latest_scan("Stills") == stills == runner.latest_scan("Stills", root)
    assert runner.latest_scan("Movie") == movie and runner.latest_scan("S&Q") == sq
    assert runner.recorded_mode(sq) == "S&Q" and runner.scan_mode("Time-lapse") == "S&Q"          # the switch's S&Q
    ap = argparse.ArgumentParser()
    runner.add_scan_argument(ap, default=runner.LATEST_SCAN, mode="Stills")
    got = ap.parse_args([]).scan
    assert got == runner.LATEST_SCAN and got.mode == "Stills" and runner.scan_dir(got) == stills, "found when read"
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Movie")) == movie          # a mode known after parsing
    named = ap.parse_args(["--scan", "kit2_page_scan"]).scan
    assert named == str(root / "kit2_page_scan") and runner.scan_dir(named) == root / "kit2_page_scan"
    # a runner with the default and no mode is a mistake of the kit's, said when the parser is made
    with pytest.raises(ValueError, match="shooting mode"):
        runner.add_scan_argument(argparse.ArgumentParser(), default=runner.LATEST_SCAN)
    with pytest.raises(SystemExit, match="works in none of its own"):
        runner.scan_dir(runner.LATEST_SCAN)                      # --scan latest on a runner that names no mode
    with pytest.raises(ValueError, match="no shooting mode"):
        runner.scan_mode("Playback")


def test_scan_latest_on_a_runner_that_names_no_mode_stops_in_plain_words(own_runs, capsys):
    """prove_run, crawl_run and drive.py name no shooting mode: their --scan latest is refused when the arguments are
    read, in plain words naming --scan <run>, never a traceback; their own default and a named scan still parse."""
    import argparse
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    a_scan(root, "kit2_page_scan", 1_000, mode="Stills")
    ap = argparse.ArgumentParser()
    runner.add_scan_argument(ap)                                  # as prove_run, crawl_run and drive.py take it
    with pytest.raises(SystemExit) as e:
        ap.parse_args(["--scan", runner.LATEST_SCAN])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "--scan latest takes the latest page scan" in err and "--scan <run>" in err and "Traceback" not in err
    assert ap.parse_args([]).scan == str(root / "kit2_page_scan")
    assert ap.parse_args(["--scan", "./latest"]).scan == str(root / "latest")      # a folder of that name, by a path


def test_a_scan_that_records_no_mode_is_never_taken_by_default(own_runs):
    """Every scan made before scans recorded their mode, here and on other mappers' machines: never taken by default,
    whatever its name or age; the run stops before anything is sent, listing the camera's scans (name, lap time, mode)
    and the two ways on: --scan <run>, or record the mode with kit/page_model.py --mode. Named with --scan, such a scan
    is taken as the mapper's word; a named scan that records another mode stops."""
    import argparse
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    old = a_scan(root, "kit2_page_scan", 1_000)                     # called the Stills scan, records nothing
    a_scan(root, "kit2_page_scan_movie_1108", 2_000, mode="Movie")
    assert runner.latest_scan("Stills") is None
    ap = argparse.ArgumentParser()
    runner.add_scan_argument(ap, default=runner.LATEST_SCAN, mode="Stills")
    got = ap.parse_args([]).scan
    for read in (runner.scan_dir, runner.load_scan):
        with pytest.raises(SystemExit) as e:
            read(got)
        said = str(e.value)
        assert "no whole page scan of the Stills mode menu" in said and "Nothing was sent to the camera" in said
        assert "--scan <run>" in said and "kit/page_model.py --mode Stills <run>" in said
        lines = said.splitlines()
        movie_line = next(x for x in lines if "kit2_page_scan_movie_1108" in x)
        old_line = next(x for x in lines if x.strip().startswith("kit2_page_scan "))
        assert lines.index(movie_line) < lines.index(old_line), "newest first"
        assert movie_line.rstrip().endswith("Movie mode") and old_line.rstrip().endswith("mode not recorded")
        assert "lap written 19" in old_line or "lap written 20" in old_line          # its time, local
    assert runner.scan_dir(ap.parse_args(["--scan", "kit2_page_scan"]).scan) == old          # named: the mapper's word
    with pytest.raises(SystemExit, match="was made in Movie mode, and this run works in Stills mode"):
        runner.scan_dir(ap.parse_args(["--scan", "kit2_page_scan_movie_1108"]).scan)


def test_with_no_page_scan_the_default_stops_in_plain_words_naming_scan(own_runs):
    """No page scan at all: parsing the default passes (a runner's own refusals come first, and a run that reads no scan
    needs none); reading it (load_scan, scan_dir) stops in plain words naming --scan and kit/page_scan.py --mode."""
    import argparse
    from conftest import TEST_CAMERA
    (own_runs / TEST_CAMERA / "kit2_pass2").mkdir(parents=True)
    assert runner.latest_scan("Movie") is None and runner.page_scans() == []
    ap = argparse.ArgumentParser()
    runner.add_scan_argument(ap, default=runner.LATEST_SCAN, mode="Movie")
    got = ap.parse_args([]).scan
    for read in (runner.scan_dir, runner.load_scan):
        with pytest.raises(SystemExit) as e:
            read(got)
        assert "no page scan yet" in str(e.value) and "--scan" in str(e.value)
        assert "kit/page_scan.py --mode Movie" in str(e.value)


def test_page_model_records_the_mode_of_a_scan_named_and_nothing_else(own_runs, monkeypatch, capsys):
    """kit/page_model.py --mode MODE <run>: the one field written (runner.SCAN_MODE_FILE), model.json and the lap left
    as they are; only for a scan named, and a scan keeps the mode it records."""
    import page_model
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    d = a_scan(root, "kit2_page_scan_1108", 1_000)
    before = {f.name: f.read_bytes() for f in d.iterdir()}
    monkeypatch.setattr(page_model, "read_frames", lambda *a, **k: pytest.fail("--mode reads no frame"))
    monkeypatch.setattr(sys, "argv", ["page_model.py", "--mode", "stills", "kit2_page_scan_1108"])
    page_model.main()
    assert json.loads((d / runner.SCAN_MODE_FILE).read_text(encoding="utf-8")) == {"mode": "Stills"}
    assert {f.name: f.read_bytes() for f in d.iterdir() if f.name != runner.SCAN_MODE_FILE} == before
    assert "recorded as a Stills mode page scan" in capsys.readouterr().out
    assert runner.latest_scan("Stills") == d
    monkeypatch.setattr(sys, "argv", ["page_model.py", "--mode", "Stills", "kit2_page_scan_1108"])
    page_model.main()                                                           # the same again: no harm
    for argv, said in ((["--mode", "Movie", "kit2_page_scan_1108"], "records Stills mode already"),
                       (["--mode", "Movie"], "the mode of the scan named"),
                       (["--mode", "Movie", "--vlm", "kit2_page_scan_1108"], "only records the scan's mode"),
                       (["--mode", "Movie", "kit2_pass2"], "no whole lap")):
        (root / "kit2_pass2").mkdir(exist_ok=True)
        monkeypatch.setattr(sys, "argv", ["page_model.py", *argv])
        with pytest.raises(SystemExit, match=said):
            page_model.main()
    assert runner.recorded_mode(d) == "Stills" and not (root / "kit2_pass2" / runner.SCAN_MODE_FILE).exists()
    monkeypatch.setattr(sys, "argv", ["page_model.py", "--mode", "Playback", "kit2_page_scan_1108"])
    with pytest.raises(SystemExit):
        page_model.main()                                                       # argparse: no such mode


def test_a_page_scan_needs_its_mode_and_records_it_before_anything_is_sent(own_runs, monkeypatch):
    """kit/page_scan.py --mode, required: the scan records it before the link opens; a run folder that records another
    mode is refused before the link opens."""
    import page_scan
    from conftest import TEST_CAMERA
    monkeypatch.setattr(page_scan, "Link", lambda run: pytest.fail("no link before the mode is recorded"))
    monkeypatch.setattr(page_scan, "eyes_from_config", lambda run: pytest.fail("no eyes before the mode is recorded"))
    monkeypatch.setattr(sys, "argv", ["page_scan.py", "--run", "kit2_scan_mode"])
    with pytest.raises(SystemExit):
        page_scan.main()                                                         # argparse: --mode is required
    run = own_runs / TEST_CAMERA / "kit2_scan_mode"
    assert not (run / runner.SCAN_MODE_FILE).exists()
    run.mkdir(parents=True)
    runner.record_mode(run, "Movie")
    monkeypatch.setattr(sys, "argv", ["page_scan.py", "--run", "kit2_scan_mode", "--mode", "Stills"])
    with pytest.raises(SystemExit, match="records Movie mode already"):
        page_scan.main()


class Sent(Exception):
    """A made-up stand-in for the first thing a page scan does after its record: no link is opened in these tests."""


def scan_until_eyes(monkeypatch, *argv):
    """kit/page_scan.py's main run with `argv` up to where it would open the eyes and the link (Sent), or its refusal
    (SystemExit): what it refused or recorded before anything could be sent."""
    import page_scan
    monkeypatch.setattr(page_scan, "Link", lambda run: pytest.fail("no link in these tests"))
    monkeypatch.setattr(page_scan, "eyes_from_config", lambda run: (_ for _ in ()).throw(Sent()))
    monkeypatch.setattr(sys, "argv", ["page_scan.py", *argv])
    page_scan.main()


def test_a_page_scan_refuses_a_folder_holding_a_scan_of_no_mode_or_another(own_runs, monkeypatch):
    """2026-11-11 review: page_scan.py --mode Movie without --run once labelled the default folder's old Stills lap as
    Movie before scanning, and a scan stopped early left the Stills map the Movie default. A folder holding a lap or a
    page model of a scan that records no mode or another mode is refused before anything is sent, saying the two ways
    on; a folder named latest is refused (--scan latest could never name it); a folder of the same mode is scanned
    again, and is no default while its new lap is unfinished."""
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    old = a_scan(root, "kit2_page_scan", 1_000)                                  # the default folder, no mode
    for argv in (["--mode", "Movie"], ["--mode", "Movie", "--run", "kit2_page_scan"]):
        with pytest.raises(SystemExit) as e:
            scan_until_eyes(monkeypatch, *argv)
        said = str(e.value)
        assert "records no mode" in said and "Nothing was sent to the camera" in said and "new --run" in said
        assert "kit/page_model.py --mode <Stills|Movie|S&Q> kit2_page_scan" in said
    assert not (old / runner.SCAN_MODE_FILE).exists(), "the old scan is not labelled"
    (old / "scan_rekeyed.json").unlink()
    with pytest.raises(SystemExit, match="records no mode"):
        scan_until_eyes(monkeypatch, "--mode", "Movie")                          # a page model alone counts too
    stills = a_scan(root, "kit2_page_scan_1108", 2_000, mode="Stills")
    with pytest.raises(SystemExit, match="records Stills mode, and this scan is of the Movie mode menu"):
        scan_until_eyes(monkeypatch, "--mode", "Movie", "--run", "kit2_page_scan_1108")
    with pytest.raises(SystemExit, match="could never be named"):
        scan_until_eyes(monkeypatch, "--mode", "Movie", "--run", "latest")
    assert not (root / "latest").exists()
    assert runner.latest_scan("Stills") == stills
    with pytest.raises(Sent):
        scan_until_eyes(monkeypatch, "--mode", "Stills", "--run", "kit2_page_scan_1108")      # the same mode: again
    got = json.loads((stills / runner.SCAN_MODE_FILE).read_text(encoding="utf-8"))
    assert got["mode"] == "Stills" and got["lap"] == runner.LAP_SCANNING and "switch" not in got
    assert runner.latest_scan("Stills") is None, "a scan begun again is no default until its lap is whole"
    assert "its scan has not finished a lap" in runner.no_scan_message("Stills")


def a_lap(d: Path, earlier: bool = False) -> None:
    """scan.jsonl as kit/page_scan.py appends it: a full lap of three positions (the last the first again), each record
    carrying the id of the scan its record (runner.SCAN_MODE_FILE) holds, after the records of an earlier scan that
    stopped part way when `earlier` (another id)."""
    from camkit import jsonl
    d.mkdir(parents=True, exist_ok=True)
    scan_id = runner.scan_record(d).get(runner.SCAN_ID)
    if earlier:
        for r in ({"page": "x", "signature": "s9", "start": True}, {"page": "y", "signature": "s8"}):
            jsonl.append(d / "scan.jsonl", {**r, "scan": "an-earlier-scan"})
    for r in ({"page": "a", "signature": "s1", "start": True}, {"page": "a", "signature": "s2"},
              {"page": "b", "signature": "s3"}, {"page": "a", "signature": "s1"}):
        jsonl.append(d / "scan.jsonl", {**r, "scan": scan_id})


def test_a_scan_is_a_default_only_once_its_lap_is_whole_and_its_model_newer(own_runs):
    """The scan's record says unfinished from before its first press until its full lap is written (write_cycle,
    runner.mark_lap_whole); then the page model (kit/page_model.py) must be built from that lap. A scan that stops early
    is never a default, nor is a lap written again over an older model. The lap is this scan's own records: an earlier
    scan's that stopped part way in the same folder are left out."""
    import os
    import page_scan
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    d = root / "kit2_page_scan_movie"
    d.mkdir(parents=True)
    runner.record_mode(d, "Movie", scanning=True)
    a_lap(d, earlier=True)
    (d / "model.json").write_text("[]", encoding="utf-8")
    os.utime(d / "model.json", (1_000, 1_000))
    assert page_scan.write_cycle(d)
    lap = json.loads((d / "scan_rekeyed.json").read_text(encoding="utf-8"))
    assert [r["signature"] for r in lap] == ["s1", "s2", "s3", "s1"], "the last scan's records alone"
    assert runner.scan_record(d)["lap"] == runner.LAP_WHOLE
    assert runner.latest_scan("Movie") is None and runner.scan_unready(d) == "its page model is older than its lap"
    (d / "model.json").write_text("[]", encoding="utf-8")                        # kit/page_model.py, after the lap
    runner.record_model(d, lap)
    assert runner.latest_scan("Movie") == d
    runner.record_mode(d, "Movie", scanning=True)                                # scanned again, stopped early
    from camkit import jsonl
    jsonl.append(d / "scan.jsonl", {"page": "c", "signature": "s7", "start": True,
                                    "scan": runner.scan_record(d)[runner.SCAN_ID]})
    assert not page_scan.write_cycle(d)
    assert runner.latest_scan("Movie") is None
    runner.record_mode(d, "Movie")                                               # page_model.py --mode: kept as it is
    assert runner.scan_record(d)["lap"] == runner.LAP_SCANNING


def test_a_rescan_that_records_nothing_never_writes_the_old_lap_again(own_runs, capsys):
    """2026-11-11 review: a scan made again in a folder of the same mode that stopped before its first record made
    write_cycle slice from the previous scan's start, write scan_rekeyed.json again with a fresh time and mark the lap
    whole, so the old lap became the newest default. Now each scan's records carry its id (runner.SCAN_ID, in its
    record): a scan with none of its own writes nothing, and its folder stays no default."""
    import page_scan
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    d = root / "kit2_page_scan"
    d.mkdir(parents=True)
    runner.record_mode(d, "Stills", scanning=True)
    a_lap(d)
    assert page_scan.write_cycle(d)
    lap = json.loads((d / "scan_rekeyed.json").read_text(encoding="utf-8"))
    (d / "model.json").write_text("[]", encoding="utf-8")
    runner.record_model(d, lap)
    assert runner.latest_scan("Stills") == d
    before = (d / "scan_rekeyed.json").read_bytes(), (d / "scan_rekeyed.json").stat().st_mtime_ns
    runner.record_mode(d, "Stills", scanning=True)                               # again, stopped before a record
    assert runner.scan_record(d)[runner.SCAN_ID] != lap[0]["scan"]
    assert not page_scan.write_cycle(d)
    assert "recorded no screen" in capsys.readouterr().out
    assert ((d / "scan_rekeyed.json").read_bytes(), (d / "scan_rekeyed.json").stat().st_mtime_ns) == before
    assert runner.scan_record(d)["lap"] == runner.LAP_SCANNING and runner.latest_scan("Stills") is None


def test_a_page_model_counts_by_the_lap_it_was_built_from_not_by_file_times(own_runs):
    """runs/ copied without file times can make any page model look older (or newer) than its lap. A scan made since
    2026-11-11 records which lap it wrote ("lap_of") and which lap its page model was built from ("model_of",
    kit/page_model.py: runner.record_model), and is judged by those; a record without them by the files' times, as
    before."""
    import os
    import page_scan
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    d = root / "kit2_page_scan"
    d.mkdir(parents=True)
    runner.record_mode(d, "Stills", scanning=True)
    a_lap(d)
    assert page_scan.write_cycle(d)
    lap = json.loads((d / "scan_rekeyed.json").read_text(encoding="utf-8"))
    (d / "model.json").write_text("[]", encoding="utf-8")
    runner.record_model(d, lap)
    for when in ((1_000, 1_000), (9_999_999_999, 9_999_999_999)):              # the model "older", then "newer"
        os.utime(d / "model.json", when)
        assert runner.scan_unready(d) is None and runner.latest_scan("Stills") == d
    rec = runner.scan_record(d)
    runner.write_json(d / runner.SCAN_MODE_FILE, {**rec, "model_of": "another-lap"})
    os.utime(d / "model.json", (9_999_999_999, 9_999_999_999))
    assert runner.scan_unready(d) == "its page model is older than its lap", "built from another lap, whatever the time"
    old = a_scan(root, "kit2_page_scan_old", 2_000, mode="Stills")              # a record from before: file times
    assert runner.scan_unready(old) is None
    os.utime(old / "model.json", (1_000, 1_000))
    assert runner.scan_unready(old) == "its page model is older than its lap"


def test_a_scan_made_in_intelligent_auto_is_the_default_only_while_that_switch_waits(own_runs, monkeypatch):
    """Intelligent Auto's menu is not known to be P/A/S/M's (runner.AUTO): a scan made while a kept mode_switch left
    the camera there records the switch, is never the default for a camera in P/A/S/M, and is the default while such a
    switch waits, when a plain Stills scan is not. A scan made under a switch to S is a plain Stills scan."""
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    stills = a_scan(root, "kit2_page_scan", 1_000, mode="Stills")
    (root / "kit2_pass2").mkdir()
    kept = root / "kit2_pass2" / runner.SWITCH_KEPT
    runner.write_json(kept, {"start": "/x/s.DAT", "to": "Auto", "title": "Intelligent Auto", "scan_mode": "Stills",
                             "t": "2026-11-11 10:00:00"})
    with pytest.raises(SystemExit) as e:
        runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills"))
    assert "in Intelligent Auto" in str(e.value) and "kit/page_scan.py --mode Stills" in str(e.value)
    with pytest.raises(Sent):
        scan_until_eyes(monkeypatch, "--mode", "Stills", "--run", "kit2_page_scan_iauto")
    auto = root / "kit2_page_scan_iauto"
    rec = runner.scan_record(auto)
    assert rec["switch"] == {"run": "kit2_pass2", "to": "Auto", "title": "Intelligent Auto", "t": "2026-11-11 10:00:00"}
    with pytest.raises(SystemExit, match="Movie mode"):
        scan_until_eyes(monkeypatch, "--mode", "Movie", "--run", "kit2_page_scan_m")   # the record says Stills
    a_lap(auto)
    import page_scan
    assert page_scan.write_cycle(auto)
    (auto / "model.json").write_text("[]", encoding="utf-8")
    runner.record_model(auto, json.loads((auto / "scan_rekeyed.json").read_text(encoding="utf-8")))
    assert runner.scan_auto(auto) and runner.latest_scan("Stills") == stills, "never the plain Stills default"
    assert runner.latest_scan("Stills", auto=True) == auto
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills")) == auto
    runner.write_json(kept, {"start": "/x/s.DAT", "to": "S", "title": "Shutter Priority", "scan_mode": "Stills"})
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills")) == stills
    assert runner.is_auto({"to": "Movie", "mode": "Auto"}) and runner.is_auto({"to": "Movie", "title": "Intelligent  Auto"})
    assert not runner.is_auto({"to": "P", "title": "Program Auto"})


def test_a_stale_switch_record_is_forgotten_before_any_restore_is_offered(own_runs, monkeypatch, capsys):
    """A kept switch every run stops on may be stale (the camera put back by hand or by a later session's restore),
    and --restore would upload that run's old start file over everything changed since: the message gives the record's
    time, target and start mode, says first to look at the camera's screen (or ask its owner) which mode it shows, then
    how to forget a stale record (mode_switch.py --forget --shows <mode>, which only renames it), and only then the
    restore, with what it uploads. --forget sends nothing."""
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import mode_switch
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    a_scan(root, "kit2_page_scan", 1_000, mode="Stills")
    (root / "kit2_pass2").mkdir()
    kept = root / "kit2_pass2" / runner.SWITCH_KEPT
    record = {"start": "/x/dat/00160_before.DAT", "to": "Movie", "title": "Program Auto", "scan_mode": "Movie",
              "t": "2026-11-09 07:09:58"}
    runner.write_json(kept, record)
    with pytest.raises(SystemExit) as e:
        runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills"))
    said = str(e.value)
    assert "2026-11-09 07:09:58" in said and "a switch to Movie (Program Auto) from Stills mode" in said
    look = said.index("look at the camera's screen (or ask its owner) which mode it shows")
    forget = said.index("mode_switch.py --forget --shows <the mode it shows> --run kit2_pass2")
    restore = said.index("--restore --run kit2_pass2")
    assert look < said.index("this record is stale") < forget < restore, "look first, stale next, the restore last"
    assert "00160_before.DAT" in said and "undone" in said and "/x/dat" not in said
    monkeypatch.setattr(mode_switch, "Link", lambda run: pytest.fail("--forget sends nothing"))
    monkeypatch.setattr(mode_switch, "eyes_from_config", lambda run: pytest.fail("--forget opens no eyes"))

    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["mode_switch.py", *argv, "--run", "kit2_pass2"])
        mode_switch.main()
    for argv in (["--forget", "--restore"], ["--forget", "--to", "Movie"]):
        with pytest.raises(SystemExit, match="give it alone"):
            run(*argv)
    with pytest.raises(SystemExit, match="needs --shows MODE"):                  # the user's word alone is not enough
        run("--forget")
    with pytest.raises(SystemExit, match="goes with --forget only"):
        run("--shows", "Stills", "--restore")
    with pytest.raises(SystemExit) as e:                                         # the switch is still in effect
        run("--forget", "--shows", "movie")
    assert "the screen shows Movie, where this switch left the camera" in str(e.value)
    assert "--restore --run kit2_pass2" in str(e.value) and kept.exists()
    run("--forget", "--shows", "Stills")
    out = capsys.readouterr().out
    assert not kept.exists() and runner.switch_waiting() == []
    gone = list((root / "kit2_pass2").glob("mode_switch.forgotten-*.json"))
    assert len(gone) == 1
    note = json.loads(gone[0].read_text(encoding="utf-8"))
    assert {k: note[k] for k in record} == record and note["forgotten"]["shows"] == "Stills" and note["forgotten"]["t"]
    assert f"rename it back: mv '{gone[0]}' '{kept}'" in out and f'ren "{gone[0]}" "{kept.name}"' in out
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills")) == root / "kit2_page_scan"
    with pytest.raises(SystemExit, match="nothing to forget"):
        run("--forget", "--shows", "Stills")


def test_forget_refuses_while_the_screen_shows_where_the_switch_went(own_runs):
    """runner.forget_refused: the screen showing the mode the switch went to, which is not the one it started from,
    means the switch is still in effect; Intelligent Auto chosen by the switch counts as its own mode; a record from
    before "from" started in Stills."""
    movie = {"to": "Movie", "scan_mode": "Movie"}
    assert runner.forget_refused(movie, "Movie", "Movie") and not runner.forget_refused(movie, "Stills", "Movie")
    assert not runner.forget_refused(movie, "S&Q", "Movie")
    back = {"to": "P", "scan_mode": "Stills", "from": "Movie"}
    assert runner.forget_refused(back, "Stills", "Stills") and not runner.forget_refused(back, "Movie", "Stills")
    auto = {"to": "Auto", "title": "Intelligent Auto", "scan_mode": "Stills"}
    assert runner.forget_refused(auto, "Stills Auto", "Stills") and not runner.forget_refused(auto, "Stills P", "Stills")
    assert runner.shown_mode("stills intelligent auto") == "Stills Auto" and runner.shown_mode("s&q motion") == "S&Q"
    with pytest.raises(ValueError, match="what the camera's screen shows"):
        runner.shown_mode("Playback")


def test_forget_takes_every_mode_a_switch_can_target_and_refuses_its_target(own_runs, capsys, monkeypatch):
    """Review 4 (2026-11-11): --shows takes every mode --to can go to (P, A, S, M, Auto, the families, S&Q Motion and
    Time-lapse as S&Q); a switch within Stills (to S from Stills) is refused while the screen shows S, its target, or
    only "Stills"; a family's --mode counts as its target; an old record with no "from" is refused while the screen
    shows the very family it went to; an empty or unreadable record is refused in plain words saying how to remove it
    by hand."""
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import mode_switch
    assert [runner.shown_mode(w) for w in ("stills p", "Stills A", "movie s", "S&Q Motion M", "Movie Auto",
                                           "Time-lapse", "Stills Program Auto", "movie")] == \
        ["Stills P", "Stills A", "Movie S", "S&Q M", "Movie Auto", "S&Q", "Stills P", "Movie"]
    within = {"to": "S", "scan_mode": "Stills", "from": "Stills"}
    assert "where this switch left the camera" in runner.forget_refused(within, "Stills S", "Stills")
    assert "say the exposure mode" in runner.forget_refused(within, "Stills", "Stills")
    assert not runner.forget_refused(within, "Stills A", "Stills") and not runner.forget_refused(within, "Movie", "Stills")
    assert runner.forget_refused({"to": "Movie", "mode": "M", "scan_mode": "Movie", "from": "Stills"}, "Movie M", "Movie")
    old = {"to": "S", "scan_mode": "Stills"}                         # no "from": made before records said it
    assert runner.forget_refused(old, "Stills", "Stills")
    assert "does not say it started there" in runner.forget_refused({"scan_mode": "Stills", "to": "Still Mode"},
                                                                     "Stills", "Stills")
    assert not runner.forget_refused(old, "Stills A", "Stills")
    assert "empty or cannot be read" in runner.forget_refused({}, "Stills", None)
    from conftest import TEST_CAMERA
    (own_runs / TEST_CAMERA / "kit2_pass2").mkdir(parents=True)
    kept = own_runs / TEST_CAMERA / "kit2_pass2" / runner.SWITCH_KEPT
    for broken in ("", "{not json", "[]"):
        kept.write_text(broken, encoding="utf-8")
        with pytest.raises(SystemExit) as e:
            mode_switch.forget(kept, "Stills", print)
        words = str(e.value)
        assert "empty or cannot be read" in words and f"rm '{kept}'" in words and f'del "{kept}"' in words
        assert kept.exists()
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--forget", "--shows", "Stills P", "--run", "kit2_pass2"])
    runner.write_json(kept, {"start": "s.DAT", "to": "Movie", "scan_mode": "Movie", "from": "Stills"})
    mode_switch.main()                                               # --shows "Stills P" parses, and is no refusal here
    assert not kept.exists()


def test_forget_takes_the_family_first_and_an_exposure_letter_alone_is_refused(own_runs, monkeypatch):
    """Fix round 5 (2026-11-11): Movie's and S&Q's screens show an exposure letter too, so --shows M on a switch to
    Movie from Stills, the camera still in Movie, was forgotten as if the screen showed Stills M (and S on a switch to
    S&Q). --shows now takes the family first and the exposure mode as a second word: a letter alone is refused in plain
    words asking for the family first, before the record is touched; the family the switch went to is refused whatever
    exposure mode is said, and another family is not."""
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import mode_switch
    movie = {"to": "Movie", "scan_mode": "Movie", "from": "Stills"}
    sq = {"to": "S&Q Motion", "scan_mode": "S&Q", "from": "Stills"}
    for letter in ("M", "S", "Auto", "manual exposure"):
        with pytest.raises(ValueError, match='family first.*"Stills .*" or "Movie '):
            runner.shown_mode(letter)
    assert runner.forget_refused(movie, "Movie M", "Movie") and runner.forget_refused(movie, "Movie", "Movie")
    assert runner.forget_refused(sq, "S&Q S", "S&Q") and runner.forget_refused(sq, "S&Q", "S&Q")
    assert not runner.forget_refused(movie, "Stills M", "Movie") and not runner.forget_refused(sq, "Stills S", "S&Q")
    from conftest import TEST_CAMERA
    (own_runs / TEST_CAMERA / "kit2_pass2").mkdir(parents=True)
    kept = own_runs / TEST_CAMERA / "kit2_pass2" / runner.SWITCH_KEPT
    for record, letter in ((movie, "M"), (sq, "S")):
        runner.write_json(kept, {"start": "s.DAT", **record})
        monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--forget", "--shows", letter, "--run", "kit2_pass2"])
        with pytest.raises(SystemExit) as e:
            mode_switch.main()
        assert "say the family first" in str(e.value) and "Nothing was changed" in str(e.value) and kept.exists()
        family = runner.switch_left(record)
        monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--forget", "--shows", f"{family} {letter}", "--run",
                                          "kit2_pass2"])
        with pytest.raises(SystemExit, match="still in effect"):
            mode_switch.main()
        assert kept.exists()


def test_a_waiting_mode_switch_stops_a_run_of_another_mode(own_runs, capsys):
    """kit/provers/mode_switch.py --keep leaves the camera in another mode until --restore (its record in a run folder,
    runner.SWITCH_KEPT): a run of another mode stops before anything is sent, saying which and how to put it back; a
    run of the mode it left goes on. An older record names only --to: P/A/S/M/Auto are Stills."""
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    stills = a_scan(root, "kit2_page_scan", 1_000, mode="Stills")
    movie = a_scan(root, "kit2_page_scan_movie", 2_000, mode="Movie")
    (root / "kit2_pass2").mkdir()
    runner.write_json(root / "kit2_pass2" / runner.SWITCH_KEPT, {"start": "s.DAT", "to": "S"})
    assert runner.switch_waiting() == [(root / "kit2_pass2", "Stills")]
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Stills")) == stills
    runner.write_json(root / "kit2_pass2" / runner.SWITCH_KEPT, {"start": "s.DAT", "to": "Movie", "scan_mode": "Movie"})
    for scan in (runner.in_mode(runner.LATEST_SCAN, "Stills"), runner.in_mode(stills, "Stills")):
        with pytest.raises(SystemExit) as e:
            runner.scan_dir(scan)
        said = str(e.value)
        assert "A mode switch is waiting" in said and "left the camera in Movie mode" in said
        assert "works in Stills mode" in said and "mode_switch.py --restore --run kit2_pass2" in said
        assert "Nothing was sent to the camera" in said
    assert runner.scan_dir(runner.in_mode(runner.LATEST_SCAN, "Movie")) == movie
    assert runner.scan_dir(stills) == stills          # a runner that names no mode (prove_run's own --scan) is not judged


def test_mode_switch_navigates_by_the_scan_of_the_mode_the_camera_is_in():
    """mode_switch: the switch navigates the menu the camera shows, Stills unless --in says otherwise; --set, the menu
    the waiting switch left up (its record's scan_mode, else its --to)."""
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import mode_switch
    assert [mode_switch.switched_mode(x) for x in ("P", "Auto", "Stills", "Movie", "S&Q Motion", "Time-lapse")] == \
        ["Stills", "Stills", "Stills", "Movie", "S&Q", "S&Q"]
    text = (ROOT / "kit" / "provers" / "mode_switch.py").read_text(encoding="utf-8")
    assert 'load_scan(in_mode(a.scan, now))' in text and 'load_scan(in_mode(a.scan, a.in_mode or "Stills"))' in text
    assert '"scan_mode": switched_mode(a.to)' in text and "load_scan(a.scan)" not in text


def test_each_runner_with_the_default_scan_names_its_mode():
    """The provers and tools that take the latest scan by default name the mode they work in: the Stills-only ones
    Stills, My Menu and the Playback filter the mode --in names (Stills by default), mode_switch the mode the camera is
    in; set_twins' --evidenced has no default of one camera's runs."""
    kit = ROOT / "kit"
    for name in ("tools/card_actions.py", "provers/memreg_run.py", "provers/afreg_run.py", "provers/framepos_run.py"):
        assert 'add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")' in (kit / name).read_text(encoding="utf-8")
    for name in ("provers/mymenu_run.py", "provers/filter_run.py"):
        text = (kit / name).read_text(encoding="utf-8")
        assert "add_in_argument(ap)" in text and "load_scan(in_mode(a.scan, a.in_mode))" in text
        assert "load_scan(a.scan)" not in text
    assert 'type=scan_type("Stills")' in (kit / "tools" / "set_twins.py").read_text(encoding="utf-8")
    sys.path.insert(1, str(kit / "tools"))
    import set_twins
    assert not hasattr(set_twins, "EVIDENCED")
    with pytest.raises(SystemExit):
        set_twins.main([])                                                         # argparse: --evidenced is required


def test_no_runner_defaults_to_a_scan_only_the_a1_ii_has():
    """The provers and tools take --scan by default as runner.LATEST_SCAN, never a folder of the a1 II's own runs
    (kit2_page_scan_1108, kit2_page_scan_osd3: card_actions, memreg_run, afreg_run, framepos_run, mymenu_run,
    filter_run, mode_switch, set_twins). The plain kit2_page_scan, which kit/page_scan.py writes by default, stays the
    generic runners' default."""
    import re
    kit = ROOT / "kit"
    for f in sorted(kit.rglob("*.py")):
        if "tests" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"default=[\"']kit2_page_scan_\w+[\"']", text), f
        assert "set_twins.SCAN" not in text and not re.search(r"^SCAN = ", text, re.M), f
    for name in ("tools/card_actions.py", "provers/memreg_run.py", "provers/afreg_run.py", "provers/framepos_run.py",
                 "provers/mymenu_run.py", "provers/filter_run.py", "provers/mode_switch.py", "tools/set_twins.py"):
        assert "LATEST_SCAN" in (kit / name).read_text(encoding="utf-8"), name
