"""The session helper every runner ends through (camkit/session.py, K-33, K-26): the end download and the restore, and
waiting for a screen with a limit and an ear for STOP. Against the stand-in camlink (fake_camlink.py) and stand-in
eyes; nothing talks to a camera.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, session  # noqa: E402
from camkit.link import Link, LinkError, StopRequested  # noqa: E402
from camkit.runs import Run  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_camlink.py"
# the stand-in, as fake_camlink.COMMAND starts it: -X utf8, which camkit needs on Windows
CAMLINK = [sys.executable, "-X", "utf8", str(FAKE)]
SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.delenv("CAMSET_USB", raising=False)
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(tmp_path / "received.txt"))
    return Run("kit2_session", root=tmp_path / "runs" / "TEST-CAM_fw9.99")


def link(run):
    return Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False)


def sent(tmp_path) -> str:
    return (tmp_path / "received.txt").read_text(encoding="utf-8")


def test_nothing_changed_nothing_uploaded(run, tmp_path):
    with link(run) as lk:
        start = lk.download("before")
        ending = session.finish(lk, start)
    assert ending.after.name.endswith("_after.DAT") and ending.changes == [] and not ending.uploaded
    assert "upload" not in sent(tmp_path)
    assert session.check_restore(run, ending, start) == 0


def test_a_change_puts_the_start_file_back_and_the_restore_is_checked(run, tmp_path, monkeypatch):
    """The camera's end download differs (a stand-in file with one record changed, never sent anywhere): the start
    file, a download, is uploaded, and check_restore reconnects and counts what still differs."""
    cs = camset.read(SAMPLE)
    rec = cs.get(0, 0x0489)
    changed = tmp_path / "changed.DAT"
    changed.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
    monkeypatch.setenv("FAKE_CAMLINK_AFTER", str(changed))
    with link(run) as lk:
        start = lk.download("before")
        ending = session.finish(lk, start)
    assert [c.key for c in ending.changes] == ["global:0x0489"] and ending.uploaded
    assert [line for line in sent(tmp_path).splitlines() if " upload " in line and start.name in line]
    monkeypatch.delenv("FAKE_CAMLINK_AFTER")
    assert session.check_restore(run, ending, start, settle=0, ready=0, link_class=link) == 0


def test_a_download_refused_every_time_restores_nothing_and_says_so(run, capsys):
    class Refusing:
        def download(self, tag):
            raise LinkError("download: camera does not allow a settings download now")

    ending = session.finish(Refusing(), SAMPLE, tries=3, pause=0)
    assert ending.after is None and not ending.uploaded
    assert "upload_check.py" in capsys.readouterr().out
    assert session.check_restore(run, ending, SAMPLE) is None          # not known: no caller takes it for 0


class Frame:
    image = np.full((480, 640, 3), 128, np.uint8)


class Eyes:
    def grab(self, save=True):
        return Frame()


def test_wait_for_always_has_a_limit(monkeypatch):
    monkeypatch.setattr(session.screen, "read", lambda f: SimpleNamespace(kind="menu"))
    monkeypatch.setattr(session, "WAIT_LIMIT", 0.3)
    with pytest.raises(RuntimeError, match="gave up waiting"):
        session.wait_for(Eyes(), ("shooting",), "a test", grace=0, limit=None)


def test_wait_for_ends_on_a_stop_asked_for_while_it_waits(monkeypatch, tmp_path):
    monkeypatch.setattr(session.screen, "read", lambda f: SimpleNamespace(kind="menu"))
    asked = iter([False, False, True])
    with pytest.raises(StopRequested, match="while waiting"):
        session.wait_for(Eyes(), ("shooting",), "a test", grace=0, limit=5, stop=lambda: next(asked, True))
    # through the link's run: its STOP file
    r = Run("kit2_wait", root=tmp_path)
    lk = SimpleNamespace(run=r, osd=lambda p: (_ for _ in ()).throw(LinkError("no OSD")))
    t = [0]

    def read(f):
        t[0] += 1
        if t[0] == 3:
            (r.dir / "STOP").write_text("", encoding="utf-8")
        return SimpleNamespace(kind="menu")
    monkeypatch.setattr(session.screen, "read", read)
    with pytest.raises(StopRequested):
        session.wait_for(Eyes(), ("shooting",), "a test", grace=0, link=lk, limit=5)


def test_a_stopping_run_still_waits_for_its_restore(monkeypatch, tmp_path):
    """A stop already asked for when the wait began (the run cancelling on its way to its restore) does not end the
    wait: the shooting screen comes and the wait returns."""
    kinds = iter(["menu", "menu", "shooting"])
    monkeypatch.setattr(session.screen, "read", lambda f: SimpleNamespace(kind=next(kinds)))
    session.wait_for(Eyes(), ("shooting",), "the restore", grace=0, limit=5, stop=lambda: True)


def test_every_runner_ends_through_the_helper():
    """No runner keeps a restore of its own: the copied download-diff-upload block and the old verify_restore and
    restore_check are gone from every script (camkit/session.py is the one place)."""
    import re
    scripts = [p for p in sorted((ROOT / "kit").rglob("*.py")) if "tests" not in p.parts and "sdk" not in p.parts]
    for p in scripts:
        text = p.read_text(encoding="utf-8")
        if p.name == "session.py":
            continue
        assert not re.search(r"def (verify_restore|restore_check)\b", text), p
        assert not re.search(r"print\(link\.upload\((start|before)\)", text), p
    users = {p.name for p in scripts if "session" in p.read_text(encoding="utf-8")}
    assert {"crawl_run.py", "drive.py", "prove_run.py", "pass3_run.py", "help_run.py", "table_walk.py", "axis_walk.py",
            "card_actions.py", "upload_check.py", "scale_run.py", "boxes_run.py", "grid_run.py", "orient_run.py",
            "customshoot_run.py", "customshoot_values.py", "bracket_run.py", "shootmode_run.py"} <= users


def test_the_osd_check_writes_a_file_of_this_process_only(monkeypatch):
    """A black HDMI frame is checked on the SDK's own picture of the screen, written to a temporary file: one of this
    process's own, never one name every run (and every user) on the computer shares, and removed after."""
    import os
    asked = []

    def osd(p):
        asked.append(p)
        p.write_bytes(b"not a picture")                # camlink wrote it; the reader cannot read it
        return p
    lk = SimpleNamespace(osd=osd)
    assert session.osd_shooting(lk, SimpleNamespace(image=np.zeros((480, 640, 3), np.uint8))) is False
    assert asked and asked[0].name == f"camkit_osd_{os.getpid()}.png" and not asked[0].exists()
    assert session.osd_shooting(lk, SimpleNamespace(image=np.full((480, 640, 3), 90, np.uint8))) is False
    assert len(asked) == 1                             # a frame with a picture is read from HDMI itself
