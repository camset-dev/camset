"""One run root per camera (2026-11-05): runs/<model>_fw<fw>/, as data/ has, and the switch that picks the camera.

camkit.paths names the camera the kit works on (--camera, CAMSET_CAMERA, private/config.json's "camera" or its one
"cameras" entry, else the one camera folder with runs), stops on the kit's runs left at the top of runs/ with the
command that moves them, and kit/tools/migrate_runs.py moves them. Everything here is a tmp_path fixture with made-up
cameras and addresses; nothing talks to a camera (identify.py's link is kit/tests/fake_camlink.py).
"""
import functools
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camkit  # noqa: E402
from camkit import ROOT, camset, paths, provenance  # noqa: E402
from camkit.runs import Run  # noqa: E402
import migrate_runs  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"          # an ILCE-1M2 firmware 4.00 file
A1 = "ILCE-1M2_fw4.00"
A7 = "ILCE-7M5_fw1.00"                           # made up for the tests: a second body
FAKE = Path(__file__).resolve().parent / "fake_camlink.py"
# the stand-in, as fake_camlink.COMMAND starts it: -X utf8, which camkit needs on Windows
CAMLINK = [sys.executable, "-X", "utf8", str(FAKE)]


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Write private/config.json (a tmp one); no camera named by the environment."""
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "private" / "config.json")
    monkeypatch.delenv("CAMSET_CAMERA", raising=False)
    monkeypatch.setattr(paths, "_from_command_line", None)

    def write(doc):
        camkit.CONFIG.parent.mkdir(exist_ok=True)
        camkit.CONFIG.write_text(json.dumps(doc), encoding="utf-8")
    return write


def other_body(path: Path, model: bytes = b"ILCE-7M5") -> Path:
    """The sample with another model name in its header, written through its block (a test file; never uploaded)."""
    b = camset.block_of(A1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b.sealed(b.with_text(SAMPLE.read_bytes(), "model", model)))
    return path


# ---------------------------------------------------------------- which camera: config, environment, command line

def test_no_camera_named_stops_with_how_to_name_one(cfg, own_runs):
    with pytest.raises(paths.NoCamera, match='"camera": "<model>_fw<firmware>" in private/config.json') as e:
        paths.run_root()
    assert "--camera" in str(e.value) and "CAMSET_CAMERA" in str(e.value) and "identify.py --camera" in str(e.value)
    assert paths.run_root(required=False) is None
    cfg({"camera_ip": "192.0.2.10"})                         # today's single-camera keys, no camera named
    assert paths.run_root(required=False) is None


def test_the_config_names_the_camera(cfg, own_runs):
    cfg({"camera_ip": "192.0.2.10", "camera": A1})
    assert paths.run_root() == own_runs / A1
    assert camkit.config()["camera_ip"] == "192.0.2.10"           # today's keys work as they did


def test_one_listed_camera_is_the_one(cfg, own_runs):
    cfg({"cameras": [{"model": "ILCE-7M5", "firmware": "1.00", "camera_ip": "192.0.2.11"}]})
    assert paths.camera() == (A7, "private/config.json's one camera")
    assert camkit.config()["camera_ip"] == "192.0.2.11"


def test_the_switch_picks_a_cameras_own_keys(cfg, own_runs):
    cfg({"camera_ip": "192.0.2.10", "eyes": "osd", "camera": A7,
         "cameras": [{"model": "ILCE-1M2", "firmware": "4.00"},
                     {"model": "ILCE-7M5", "firmware": "1.00", "camera_ip": "192.0.2.11", "eyes": "hdmi"}]})
    c = camkit.config()
    assert (c["camera_ip"], c["eyes"]) == ("192.0.2.11", "hdmi") and paths.run_root() == own_runs / A7
    cfg({"camera_ip": "192.0.2.10", "eyes": "osd", "camera": A1,
         "cameras": [{"model": "ILCE-1M2", "firmware": "4.00"}, {"model": "ILCE-7M5", "firmware": "1.00",
                                                                  "camera_ip": "192.0.2.11"}]})
    assert (camkit.config()["camera_ip"], paths.run_root()) == ("192.0.2.10", own_runs / A1)


def test_two_listed_cameras_and_none_named_stop(cfg, own_runs):
    cfg({"cameras": [{"model": "ILCE-1M2", "firmware": "4.00"}, {"model": "ILCE-7M5", "firmware": "1.00"}]})
    with pytest.raises(paths.NoCamera, match="Which camera"):
        paths.run_root()


def test_a_camera_the_list_lacks_or_a_bad_key_stops(cfg, own_runs, monkeypatch):
    cfg({"camera": "ILCE-7M4_fw2.00", "cameras": [{"model": "ILCE-1M2", "firmware": "4.00"}]})
    with pytest.raises(paths.NoCamera, match="does not list"):
        paths.run_root()
    cfg({"camera": "a1 II"})
    with pytest.raises(paths.NoCamera, match="not a camera's key"):
        paths.run_root()
    cfg({"cameras": [{"model": "ILCE-1M2"}]})
    with pytest.raises(paths.NoCamera, match='needs "model" and "firmware"'):
        paths.run_root()


def test_the_environment_and_the_command_line_come_first(cfg, own_runs, monkeypatch):
    cfg({"camera": A1})
    monkeypatch.setenv("CAMSET_CAMERA", A7)
    assert paths.camera() == (A7, "CAMSET_CAMERA") and paths.run_root() == own_runs / A7
    argv = ["prove_run.py", "--rows", "Grid Line Display", "--camera", A1, "--limit", "1"]
    assert paths.take_command_line(argv) == A1
    assert argv == ["prove_run.py", "--rows", "Grid Line Display", "--limit", "1"]   # taken out before argparse
    assert paths.camera() == (A1, "--camera") and os.environ["CAMSET_CAMERA"] == A1  # and passed on to children
    argv = ["x.py", f"--camera={A7}"]
    assert paths.take_command_line(argv) == A7 and argv == ["x.py"]
    with pytest.raises(paths.NoCamera, match="not a camera's key"):
        paths.take_command_line(["x.py", "--camera", "ILCE1M2"])


def test_a_bare_camera_flag_is_left_for_identify(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_from_command_line", None)
    f = tmp_path / "x.DAT"
    f.write_bytes(b"")
    for argv in (["identify.py", "--camera"], ["identify.py", "--camera", "--verbose"], ["identify.py", "--camera", str(f)]):
        kept = list(argv)
        assert paths.take_command_line(argv) is None and argv == kept


def test_one_camera_folder_with_runs_is_taken_when_nothing_names_one(cfg, own_runs):
    (own_runs / A1 / "_viewer").mkdir(parents=True)            # a page alone: not a camera's runs
    assert paths.camera() is None
    (own_runs / A1 / "kit2_identify").mkdir()
    assert paths.camera() == (A1, f"the one camera in {own_runs.as_posix()}/") and paths.run_root() == own_runs / A1
    (own_runs / A7 / "kit2_identify").mkdir(parents=True)
    with pytest.raises(paths.NoCamera, match=f"holds {A1}, {A7}"):
        paths.run_root()


def test_a_kit_command_takes_camera_on_its_command_line(tmp_path, own_runs):
    """--camera on a kit command: its evidence goes into that camera's folder, whatever CAMSET_CAMERA says."""
    f = tmp_path / "start_by_hand.DAT"
    shutil.copy(SAMPLE, f)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "upload_check.py"), "--camera", A7, str(f)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "not a camera download" in r.stderr
    assert (own_runs / A7 / "kit2_pass2" / "dat").is_dir() and not (own_runs / "TEST-CAM_fw9.99").exists()


# ---------------------------------------------------------------- runs at the top of runs/: never used silently

def test_runs_at_the_top_stop_every_user_with_one_message(cfg, own_runs):
    cfg({"camera": A1})
    other_body(own_runs / "kit2_pass2" / "dat" / "00001_before.DAT", b"ILCE-1M2")
    (own_runs / "_viewer").mkdir()
    for use in (paths.run_root, lambda: Run("kit2_crawl"), lambda: provenance.entries(),
                lambda: paths.run_path("kit2_crawl/map.json")):
        with pytest.raises(paths.Leftovers) as e:
            use()
        said = str(e.value).replace(own_runs.as_posix(), "runs")
        assert said == (f"runs/kit2_pass2 sits at the top of runs/ (with 1 more of the kit's); run "
                        f"`python3 kit/tools/migrate_runs.py --camera {A1}` to move the {A1}'s runs under runs/{A1}/ "
                        "(--dry-run shows the plan first). Until then the kit does not use them.")
    assert not (own_runs / A1).exists()


def test_a_run_path_is_the_cameras_and_no_other(cfg, own_runs):
    cfg({"camera": A1})
    assert paths.run_path("kit2_crawl/map.json") == own_runs / A1 / "kit2_crawl" / "map.json"
    (own_runs / A7 / "kit2_crawl").mkdir(parents=True)
    with pytest.raises(paths.NoCamera, match=f"--camera {A7}"):
        paths.run_path(own_runs / A7 / "kit2_crawl")
    assert paths.run_path(SAMPLE) == SAMPLE                   # a file elsewhere is as given


def test_stop_files_for_a_run_its_camera_and_every_camera(own_runs):
    run = Run("kit2_crawl", root=own_runs / A1)
    assert not run.stop_requested()
    for stop in (run.dir / "STOP", own_runs / A1 / "STOP", own_runs / "STOP"):
        stop.touch()
        assert run.stop_requested()
        stop.unlink()


# ---------------------------------------------------------------- the migration: a fixture only

@pytest.fixture
def old_runs(own_runs):
    """runs/ as it was before 2026-11-05: the a1 II's runs at the top, with what the kit made and others."""
    top = own_runs
    pass2 = top / "kit2_pass2"
    (pass2 / "shots").mkdir(parents=True)
    (pass2 / "shots" / "00002_right.png").write_bytes(b"png")
    dl = other_body(pass2 / "dat" / "00001_before.DAT", b"ILCE-1M2")
    (top / "kit2_disp_look.log").write_text("a log\n", encoding="utf-8")
    (top / "_viewer").mkdir()
    (top / "_viewer" / "index.html").write_text('<img src="../kit2_pass2/shots/00002_right.png">', encoding="utf-8")
    (top / "_cache" / "vlm").mkdir(parents=True)
    (top / "calibration_2026-10-26").mkdir()
    (top / "explore_stills" / "shots").mkdir(parents=True)
    (top / "cb_run1").mkdir()
    (top / "notes.log").write_text("the owner's\n", encoding="utf-8")
    (top / "STOP_CHAIN").touch()
    entries = [{"t": 1.0, "path": "kit2_pass2/dat/00001_before.DAT", "sha256": provenance.sha256(dl), "bytes": 1},
               {"t": 2.0, "path": str(dl.resolve()), "sha256": "00", "bytes": 1,
                "adopted_from": str((pass2 / "events.jsonl").resolve())},
               {"t": 3.0, "path": "/elsewhere/start.DAT", "sha256": "11", "bytes": 1}]
    (top / "downloads.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return top


def migrate(*args) -> int:
    return migrate_runs.main(list(args))


def test_the_dry_run_prints_the_plan_and_moves_nothing(old_runs, cfg, capsys):
    before = sorted(p.name for p in old_runs.iterdir())
    assert migrate("--dry-run") == 0
    out = capsys.readouterr().out
    assert f"camera {A1} (the runs' own downloads)" in out
    for n in ("kit2_pass2", "kit2_disp_look.log", "_viewer", "_cache", "calibration_2026-10-26", "explore_stills",
              "downloads.jsonl"):
        assert f"  move   {n}\n" in out
    assert "  leave  cb_run1  (not the kit's" in out and "  leave  notes.log" in out and "  stay   STOP_CHAIN" in out
    assert "dry run: nothing moved" in out
    assert sorted(p.name for p in old_runs.iterdir()) == before


def test_the_move_renames_into_the_cameras_folder(old_runs, cfg, capsys, monkeypatch):
    shot = old_runs / "kit2_pass2" / "shots" / "00002_right.png"
    inode = shot.stat().st_ino
    assert migrate("--camera", A1) == 0
    root = old_runs / A1
    assert sorted(p.name for p in old_runs.iterdir()) == sorted([A1, "cb_run1", "notes.log", "STOP_CHAIN"])
    moved = root / "kit2_pass2" / "shots" / "00002_right.png"
    assert moved.stat().st_ino == inode                       # renamed, not copied
    lines = [json.loads(x) for x in (root / "downloads.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["path"] for e in lines] == ["kit2_pass2/dat/00001_before.DAT"] * 2 + ["/elsewhere/start.DAT"]
    assert lines[1]["adopted_from"] == "kit2_pass2/events.jsonl"
    assert "made 2 paths" in capsys.readouterr().out
    assert provenance.check(root / "kit2_pass2" / "dat" / "00001_before.DAT", root)        # the manifest still holds
    monkeypatch.delenv("CAMSET_CAMERA")                    # the --camera above, for this process: now nothing names one
    assert paths.leftovers() == [] and paths.camera() == (A1, f"the one camera in {old_runs.as_posix()}/")
    assert paths.run_root() == root
    assert migrate() == 0 and "nothing to move" in capsys.readouterr().out               # twice: nothing more


def test_all_moves_what_the_kit_does_not_know(old_runs, cfg):
    assert migrate("--camera", A1, "--all") == 0
    assert sorted(p.name for p in old_runs.iterdir()) == [A1, "STOP_CHAIN"]
    assert (old_runs / A1 / "cb_run1").is_dir() and (old_runs / A1 / "notes.log").is_file()


def test_nothing_moves_when_a_target_is_there(old_runs, cfg, capsys):
    (old_runs / A1 / "_cache").mkdir(parents=True)
    assert migrate("--camera", A1) == 1
    assert "refused: already in" in capsys.readouterr().err
    assert (old_runs / "kit2_pass2").is_dir() and (old_runs / "_viewer").is_dir()
    assert not any((old_runs / A1).glob("kit2_*"))


def test_nothing_moves_when_runs_are_another_bodys(old_runs, cfg, capsys):
    other_body(old_runs / "kit2_a7" / "dat" / "00001_before.DAT")
    assert migrate("--camera", A1) == 1
    err = capsys.readouterr().err
    assert "another camera than ILCE-1M2_fw4.00: ILCE-7M5 firmware 4.00: kit2_a7" in err
    assert (old_runs / "kit2_pass2").is_dir() and not (old_runs / A1).exists()


def test_the_config_names_the_camera_to_move_into(old_runs, cfg, capsys):
    cfg({"camera": A1})
    assert migrate("--dry-run") == 0
    assert f"camera {A1} (private/config.json)" in capsys.readouterr().out


def test_the_known_names_cover_what_the_tests_read():
    """Every a1 II run the tests read (A1 / "<name>") is one the migration moves, so they find it after it."""
    import re
    text = "".join((ROOT / "kit" / "tests" / f).read_text(encoding="utf-8") for f in ("test_core.py", "score_screen.py"))
    names = set(re.findall(r'A1 / "([^"/]+)"', text)) | set(re.findall(r'a1ii_root\(\) / "([^"/]+)"', text))
    assert names and all(migrate_runs.known(n) for n in names), sorted(n for n in names if not migrate_runs.known(n))


# ---------------------------------------------------------------- identify.py starts a camera's folder

@pytest.fixture
def fake_link(monkeypatch):
    from camkit import link
    monkeypatch.delenv("CAMSET_USB", raising=False)
    monkeypatch.setattr(link, "Link", functools.partial(link.Link, ip="192.0.2.10", binary=CAMLINK,
                                                        catch_signals=False))

    def says(model, firmware):
        monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "ModelName", "text": model},
                                                             {"name": "SoftwareVersion", "text": firmware},
                                                             {"name": "LensModelName", "text": "a made-up lens"}]))
    return says


def test_identify_files_the_download_in_the_cameras_own_folder(fake_link, cfg, own_runs, capsys):
    import identify
    fake_link("ILCE-1M2", "4.00")
    lines = identify.ask_camera()
    root = own_runs / A1
    got = root / "kit2_identify" / "dat" / "00001_identify.DAT"
    assert got.exists() and provenance.check(got, root)
    kinds = [json.loads(x)["kind"] for x in (root / "kit2_identify" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[0] == "link_open" and "run_continued" in kinds and kinds[-1] == "link_close"
    assert lines[0] == f"this camera is {A1}: its runs go to {root.as_posix()}/"
    assert any(f'put "camera": "{A1}" in private/config.json' in ln for ln in lines)
    assert "camera: ILCE-1M2 firmware 4.00, lens a made-up lens" in capsys.readouterr().out


def test_identify_says_when_the_config_names_another_camera(fake_link, cfg, own_runs):
    import identify
    cfg({"camera": A1})
    fake_link("ILCE-7M5", "1.00")
    lines = identify.ask_camera()
    assert (own_runs / A7 / "kit2_identify" / "dat" / "00001_identify.DAT").exists()
    assert not (own_runs / A1).exists()
    assert any("note: the file's header says ILCE-1M2_fw4.00" in ln for ln in lines)     # the sample is an a1 II's
    assert any(f'private/config.json names {A1}, not this camera: set "camera": "{A7}"' in ln for ln in lines)
