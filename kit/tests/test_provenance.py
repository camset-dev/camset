"""Upload provenance (docs/decisions/0006): only bytes the camera wrote go back to it.

The link records each download's SHA-256 in its camera's downloads.jsonl (runs/<model>_fw<fw>/, camkit.paths);
Link.upload and kit/tools/upload_check.py refuse any file whose bytes are not a download's, whatever folder it is in,
and a download of one camera is not taken for another's. Nothing here talks to a camera: the link is never opened.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, provenance  # noqa: E402
from camkit.link import Link, LinkError  # noqa: E402
from camkit.runs import Run  # noqa: E402
import conftest  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"          # the ILCE-1M2 definition's sample


@pytest.fixture
def run(tmp_path):
    return Run("kit2_test", root=tmp_path / "runs")


def downloaded(run: Run, name: str = "00001_before") -> Path:
    """A stand-in for Link.download: the camera's file lands in dat/ and is recorded."""
    path = run.dat / f"{name}.DAT"
    shutil.copy(SAMPLE, path)
    provenance.record(path, run.root, run=run.dir.name)
    return path


def link_for(run: Run) -> Link:
    return Link(run, ip="192.0.2.10", binary=Path("/nonexistent/camlink"))


def test_a_download_and_a_copy_of_it_pass(run, tmp_path):
    d = downloaded(run)
    assert provenance.check(d, run.root)["sha256"] == provenance.sha256(d)
    copy = tmp_path / "elsewhere" / "start_quiet.DAT"
    copy.parent.mkdir()
    shutil.copy(d, copy)
    assert provenance.check(copy, run.root)            # the same bytes: the camera wrote them
    with pytest.raises(LinkError, match="link is not open"):
        link_for(run).upload(copy)                     # past the provenance check, then no connection


def test_a_file_with_values_written_in_is_refused_even_in_dat(run):
    d = downloaded(run)
    cs = camset.read(d)
    rec = cs.get(0, 0x0489)
    crafted = run.dat / "00002_p3-set.DAT"             # where pass3_run.file_switch used to write it
    crafted.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
    with pytest.raises(provenance.NotADownload, match="0006"):
        provenance.check(crafted, run.root)
    with pytest.raises(LinkError, match="not a camera download"):
        link_for(run).upload(crafted)
    refused = [json.loads(l) for l in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in refused[-2:]] == ["upload_refused", "cmd_refused"]      # the choke point logs it too


def test_a_download_edited_in_place_is_refused(run):
    d = downloaded(run)
    cs = camset.read(d)
    rec = cs.get(0, 0x0489)
    d.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
    with pytest.raises(provenance.NotADownload, match="changed after the camera wrote it"):
        provenance.check(d, run.root)


def test_make_sample_output_in_a_dat_folder_is_refused(run):
    # the "download" carries a file-name prefix of its own, which make_sample puts back to DSC
    cs = camset.read(SAMPLE)
    d = run.dat / "00001_before.DAT"
    d.write_bytes(camset.with_values(cs, {(0, 0x0B5B): b"QZX\0"}))
    provenance.record(d, run.root, run=run.dir.name)
    out = run.dat / "x.DAT"
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "make_sample.py"), str(d), "--out", str(out)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    with pytest.raises(LinkError, match="not a camera download"):
        link_for(run).upload(out)


def test_pass3_file_switch_is_retired():
    """pass3_run's blockers "switched by a file" wrote values into the start file and uploaded it."""
    import pass3_run

    class NoUploads:
        def upload(self, path):
            raise AssertionError(f"uploaded {path}")
    with pytest.raises(pass3_run.Failed, match="0006"):
        pass3_run.file_switch(NoUploads(), SAMPLE, {0x01d8: 1})
    assert "change the setting on the camera" in pass3_run.RETIRED


def test_upload_check_refuses_a_file_not_in_the_manifest(tmp_path, own_runs):
    f = tmp_path / "dat" / "start_by_hand.DAT"
    f.parent.mkdir()
    shutil.copy(SAMPLE, f)                             # a valid file in a dat/ folder, but no download
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "upload_check.py"), str(f), "--run", "kit2_test_provenance"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "not a camera download" in r.stderr and "0006" in r.stderr
    assert (own_runs / conftest.TEST_CAMERA / "kit2_test_provenance").is_dir()   # the test's runs, not the clone's


def test_the_manifest_is_the_cameras_own(tmp_path, own_runs, monkeypatch):
    """Downloads are recorded in the camera's run root; one camera's download is no download of another's."""
    a1 = Run("kit2_pass2", root=own_runs / "ILCE-1M2_fw4.00")
    d = downloaded(a1)
    assert provenance.manifest_path(a1.root) == own_runs / "ILCE-1M2_fw4.00" / "downloads.jsonl"
    assert provenance.entries(a1.root)[0]["path"] == "kit2_pass2/dat/00001_before.DAT"      # relative to the root
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-1M2_fw4.00")
    assert provenance.check(d)["sha256"] == provenance.sha256(d)          # the root of the camera the kit works on
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")
    with pytest.raises(provenance.NotADownload):
        provenance.check(d)                                                # not a download of this camera
    assert Run("kit2_pass2").root == own_runs / "ILCE-7M5_fw1.00"
    assert not (own_runs / "downloads.jsonl").exists()


def test_adopt_finds_a_log_written_before_the_move(tmp_path, own_runs):
    """A download logged at runs/kit2_x/... is found under the camera's folder once the runs moved there."""
    run = Run("kit2_x", root=own_runs / "ILCE-1M2_fw4.00")
    f = run.dat / "00001_before.DAT"
    shutil.copy(SAMPLE, f)
    old = Path("/elsewhere/camset/runs/kit2_x/dat/00001_before.DAT")      # where it was when the log was written
    with open(run.dir / "events.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"t": time.time() + 60, "kind": "cmd", "cmd": "download",
                             "reply": {"ok": True, "path": str(old), "bytes": SAMPLE.stat().st_size}}) + "\n")
    assert [e["path"] for e in provenance.adopt(run.root)] == ["kit2_x/dat/00001_before.DAT"]
    later = Run("kit2_y", root=own_runs / "ILCE-1M2_fw4.00")
    g = later.dat / "00001_before.DAT"
    shutil.copy(SAMPLE, g)
    g.write_bytes(g.read_bytes()[:-1] + b"\1")                              # other bytes: a download of its own
    new = Path("/elsewhere/camset/runs/ILCE-1M2_fw4.00/kit2_y/dat/00001_before.DAT")   # a clone that moved since
    with open(later.dir / "events.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"t": time.time() + 60, "kind": "cmd", "cmd": "download",
                             "reply": {"ok": True, "path": str(new), "bytes": SAMPLE.stat().st_size}}) + "\n")
    assert [e["path"] for e in provenance.adopt(run.root)] == ["kit2_y/dat/00001_before.DAT"]


def test_adopt_takes_only_logged_unchanged_downloads(run):
    good, late, short = (run.dat / f"{n}.DAT" for n in ("00001_before", "00002_after", "00003_x"))
    for f in (good, late, short):
        shutil.copy(SAMPLE, f)
    cs = camset.read(late)
    rec = cs.get(0, 0x0489)
    late.write_bytes(camset.with_values(cs, {(0, 0x0489): bytes([(rec.raw[0] + 1) % 4]) + rec.raw[1:]}))
    shutil.copy(SAMPLE, short)
    with open(short, "ab") as fh:
        fh.write(b"\0")
    t = time.time()
    old = t - 3600
    for f in (good, short):
        os.utime(f, (old, old))
    os.utime(late, (t, t))                             # written an hour after its logged download
    with open(run.dir / "events.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in (good, late, short):
            fh.write(json.dumps({"t": old + 1, "kind": "cmd", "cmd": f"download {run.dat} {f.stem}",
                                 "reply": {"ok": True, "path": str(f), "bytes": SAMPLE.stat().st_size}}) + "\n")
        fh.write(json.dumps({"t": old + 2, "kind": "cmd", "cmd": "press menu 60", "reply": {"ok": True}}) + "\n")
    added = provenance.adopt(run.root)
    assert [e["path"] for e in added] == [f"kit2_test/dat/{good.name}"]
    assert provenance.check(good, run.root)
    for f in (late, short):
        with pytest.raises(provenance.NotADownload):
            provenance.check(f, run.root)
    assert provenance.adopt(run.root) == []            # twice: nothing new


def test_a_manifest_line_that_is_no_entry_is_passed_over(run):
    """A line cut short by a crash, or one that parses but is no object, is no entry: the others still count. A line
    of the second kind used to stop check() with AttributeError, refusing every upload with a crash, not a reason."""
    d = downloaded(run)
    with open(provenance.manifest_path(run.root), "a", encoding="utf-8", newline="\n") as fh:
        fh.write('[1, 2]\n"text"\n{"t": 1, "path": "kit2_test/dat/x.DAT", "sha2\n')
    assert provenance.check(d, run.root)["sha256"] == provenance.sha256(d)
    assert len(provenance.entries(run.root)) == 1
    downloaded(run, "00002_after")                     # a new entry after the cut line still counts
    assert len(provenance.entries(run.root)) == 2


def test_only_a_settings_file_is_recorded_and_an_empty_file_never_passes(run):
    """record() notes a file only when camset.peek reads it as a settings file: an empty download, one cut short or
    another kind of file is refused in plain words and left out of the manifest. check() refuses an empty file
    whatever the manifest holds (an older kit recorded one, and every empty file then passed)."""
    empty, short, text = run.dat / "00001_empty.DAT", run.dat / "00002_short.DAT", run.dat / "00003_text.DAT"
    empty.write_bytes(b"")
    short.write_bytes(SAMPLE.read_bytes()[:20])
    text.write_text("not a settings file\n", encoding="utf-8")
    for f in (empty, short, text):
        with pytest.raises(provenance.NotADownload, match="not recorded as a camera download: it is not a settings file"):
            provenance.record(f, run.root, run=run.dir.name)
    assert provenance.entries(run.root) == []
    with open(provenance.manifest_path(run.root), "a", encoding="utf-8", newline="\n") as fh:     # an older kit's entry
        fh.write(json.dumps({"t": 1.0, "path": "kit2_test/dat/00001_empty.DAT", "sha256": provenance.sha256(empty),
                             "bytes": 0}) + "\n")
    with pytest.raises(provenance.NotADownload, match=r"empty \(0 bytes\)"):
        provenance.check(empty, run.root)
    with pytest.raises(LinkError, match="not a camera download: it is empty"):
        link_for(run).upload(empty)
    assert provenance.check(downloaded(run, "00004_before"), run.root)          # a settings file still is recorded


def test_adopt_names_a_download_that_is_no_settings_file_and_takes_in_the_rest(own_runs):
    """A logged download that is no settings file (cut short, its size the logged one) once ended upload_check --adopt
    with a traceback, and every download after it went unadopted. It is now named, "not adopted: ...", and the rest
    are taken in."""
    root = own_runs / conftest.TEST_CAMERA
    old = Run("kit2_old", root=root)
    cut, good = old.dat / "00001_cut.DAT", old.dat / "00002_good.DAT"
    cut.write_bytes(SAMPLE.read_bytes()[:40])
    shutil.copy(SAMPLE, good)
    t = time.time() + 60
    with open(old.dir / "events.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in (cut, good):
            fh.write(json.dumps({"t": t, "kind": "cmd", "cmd": f"download {old.dat} {f.stem}",
                                 "reply": {"ok": True, "path": str(f), "bytes": f.stat().st_size}}) + "\n")
    said = []
    added = provenance.adopt(root, say=said.append)
    assert [e["path"] for e in added] == ["kit2_old/dat/00002_good.DAT"]
    assert len(said) == 1 and said[0].startswith(f"not adopted: {cut}: not recorded as a camera download: it is not a "
                                                 f"settings file (40 bytes;")
    provenance.manifest_path(root).unlink()                  # again through the tool, from an empty manifest
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "upload_check.py"), "--adopt", "--run", "kit2_old"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr
    assert f"not adopted: {cut}" in r.stdout and "adopted kit2_old/dat/00002_good.DAT" in r.stdout
    assert "1 downloads adopted" in r.stdout


def test_the_newest_start_file_is_the_last_downloaded_not_the_last_name_as_text(tmp_path):
    """camkit.provenance.newest_start: the manifest's order is the order of download. Sorted as text, "93438_before.DAT"
    came after "239606_before.DAT" and kit/schema_update.py read a new record's layout and its decision-16 fill from an
    old download (2026-11-11); set_twins' --file default and schema_update.run_start take this one helper. A start file
    gone from the disk is passed over; under= keeps to one run folder; no start file at all is None."""
    pass2, other = Run("kit2_pass2", root=tmp_path / "runs"), Run("kit2_other", root=tmp_path / "runs")
    root = pass2.root
    assert provenance.newest_start(root) is None
    for r, name in ((pass2, "93438_before"), (pass2, "239465_before"), (pass2, "239466_after"),
                    (pass2, "239606_before"), (other, "00012_before")):
        downloaded(r, name)
    assert sorted(p.name for p in pass2.dat.glob("*_before.DAT"))[-1] == "93438_before.DAT", "the text order"
    assert provenance.newest_start(root) == other.dat / "00012_before.DAT"
    assert provenance.newest_start(root, under=pass2.dir) == pass2.dat / "239606_before.DAT"
    (pass2.dat / "239606_before.DAT").unlink()
    assert provenance.newest_start(root, under=pass2.dir) == pass2.dat / "239465_before.DAT"
    assert provenance.newest_start(root, under=tmp_path / "elsewhere") is None


def test_schema_update_reads_new_records_from_the_runs_newest_start_file(tmp_path, monkeypatch):
    import schema_update as U
    pass2 = Run("kit2_pass2", root=tmp_path / "runs")
    monkeypatch.setattr(U, "RUN_ROOT", pass2.root)
    monkeypatch.setattr(U, "RUN", pass2.dir)
    with pytest.raises(SystemExit, match="no start file of kit2_pass2"):
        U.run_start()
    for name in ("93438_before", "239606_before"):
        downloaded(pass2, name)
    assert U.run_start() == pass2.dat / "239606_before.DAT"
    assert "glob(\"*_before.DAT\"))[-1]" not in (ROOT / "kit" / "schema_update.py").read_text(encoding="utf-8")
