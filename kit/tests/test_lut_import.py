"""A user LUT into the camera (the owner's approval of 2026-11-19): camlink's importlut (Sony's ImportLUTFile), its
checks made in C++ before the SDK is asked (kit/common/lut_file.h, compiled and run here with no SDK), and its command
line; Link.import_lut (kit/camkit/link.py), its checks made in Python before the line goes out, against the stand-in
camlink (kit/tests/fake_camlink.py). No camera."""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, provenance, safety  # noqa: E402
from camkit import link as L  # noqa: E402
from camkit.link import Link, LinkError, LutNotImported, StopRequested, quoted  # noqa: E402
from camkit.runs import Run  # noqa: E402
import fake_camlink  # noqa: E402

CUBE = ("#a test's LUT\n\nTITLE \"test\"\nLUT_3D_SIZE 2\n\n" +
        "".join(f"{r}.0 {g}.0 {b}.0\n" for b in (0, 1) for g in (0, 1) for r in (0, 1)))
NAME = "1_test_look_to_709.cube"


@pytest.fixture
def luts(tmp_path, monkeypatch):
    """(a run, the stand-in's log, the LUT folder the link takes files from, a LUT in it): the folder is the test's own
    (camkit.link.LUT_DIR), with a space in its path, as a clone's may have."""
    folder = tmp_path / "First Last" / "clone" / "private" / "lut"
    lut = folder / "Look Pack" / NAME
    lut.parent.mkdir(parents=True)
    lut.write_text(CUBE, encoding="utf-8")
    monkeypatch.setattr(L, "LUT_DIR", folder)
    run = Run("kit2_lut", root=tmp_path / "runs" / "TEST-CAM_fw9.99")
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.delenv("CAMSET_USB", raising=False)
    return run, log, folder, lut


def opened(run) -> Link:
    return Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False)


def received(log: Path) -> list:
    return [ast.literal_eval(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def events(run) -> list:
    return [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def compiled(tmp_path, name: str) -> Path:
    """kit/common/<name>.cpp built with -Wall -Wextra -Werror (skipped without a C++ compiler)."""
    cxx = next((c for c in ("c++", "clang++", "g++") if shutil.which(c)), None)
    if not cxx:
        pytest.skip("no C++ compiler")
    exe = tmp_path / name
    r = subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "kit" / "common"),
                        str(ROOT / "kit" / "common" / f"{name}.cpp"), "-o", str(exe)],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return exe


def test_the_cpp_lut_checks(tmp_path):
    """Every refusal camlink makes before it asks the SDK to import (the file, the place, the camera's state, the
    command line), each checked with no camera: kit/common/lut_file_test.cpp, its files in the test's own folder."""
    exe = compiled(tmp_path, "lut_file_test")
    work = tmp_path / "work"
    work.mkdir()
    env = {**os.environ, "TMPDIR": str(work), "TMP": str(work), "TEMP": str(work)}
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stderr
    assert "all checks passed" in r.stdout
    assert not list(work.iterdir())                         # it took its files away


def test_the_lut_folder_is_a_place_the_public_files_may_name():
    """kit/tools/check_public.py refuses a public file that names a folder of private/ the docs do not tell everyone to
    use: private/lut/, the one folder the import takes a LUT from, is one now; a folder beside it still is not."""
    import sys
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    import check_public as C
    assert not C.private_path_problems("a.py", "LUT_DIR = private/lut/SonyLookProfiles/1_x.cube\n")
    mine = "private"                        # written apart, so this file names no such folder itself
    assert C.private_path_problems("a.py", mine + "/lutx/1_x.cube\n")
    assert C.private_path_problems("a.py", mine + "/archive/lut/1_x.cube\n")
    assert "private/lut/" in C.PRIVATE_OK_WORDS


def test_camlink_says_its_import_command_and_its_answers():
    """camlink's header names the command, its refusals' causes and the one SDK call it makes for it; the command asks
    the SDK for nothing else that sends a file (no settings upload by another door, no firmware, nothing that deletes)."""
    src = (ROOT / "kit" / "link" / "camlink.cpp").read_text(encoding="utf-8")
    head = src.split("#include", 1)[0]
    for word in ("importlut PATH PLACE [SHA256]", "not_a_lut", "import_disabled", "import_refused", "import_unconfirmed",
                 "ImportLUTFile_Result_OK"):
        assert word in head, word
    assert src.count("SCRSDK::ImportLUTFile(") == 1
    body = src.split("static void cmdImportLut", 1)[1].split("\n}\n", 1)[0]
    for call in ("UploadSettingFile", "DownloadSettingFile", "SetDeviceProperty", "DeleteUserBaseLook_All", "Firmware",
                 "SendCommand"):
        assert call not in body, call


# ---------------------------------------------------------------- Link.import_lut

def test_a_lut_goes_by_its_real_path_into_place_16_with_its_hash(luts):
    """The one line that goes out: the file's real path, quoted, place 16 unless named, and the SHA-256 of its bytes,
    which camlink checks the bytes it reads against. The run's log keeps the file's name, size, place and hash, never
    its content; the camera's answer comes back as it is."""
    run, log, folder, lut = luts
    digest = hashlib.sha256(CUBE.encode()).hexdigest()
    with opened(run) as link:
        r = link.import_lut(folder / "Look Pack" / ".." / "Look Pack" / NAME)
        assert r["ok"] and r["result"] == L.LUT_OK and r["place"] == 16 and r["sha256"] == digest
        assert link.import_lut(lut, place=3)["place"] == 3
    sent = received(log)
    assert sent[0] == f"@1 importlut {quoted(lut.resolve())} 16 {digest}\n".encode()
    assert sent[1] == f"@2 importlut {quoted(lut.resolve())} 3 {digest}\n".encode()
    kept = [e for e in events(run) if e["kind"] == "lut_import"]
    assert [(e["file"], e["sha256"], e["bytes"], e["place"]) for e in kept] == [(NAME, digest, len(CUBE), 16),
                                                                               (NAME, digest, len(CUBE), 3)]
    assert "LUT_3D_SIZE" not in (run.dir / "events.jsonl").read_text(encoding="utf-8")


def test_the_place_is_a_user_place(luts):
    run, log, _, lut = luts
    with opened(run) as link:
        for place in (0, 17, -1, 256, True, "16", 16.0, None):
            with pytest.raises(safety.Refused, match="no user place"):
                link.import_lut(lut, place=place)
    assert not [raw for raw in received(log) if b"importlut" in raw]


def made(folder: Path, name: str, text: str = CUBE) -> Path:
    p = folder / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_only_a_cube_lut_under_the_clones_own_lut_folder_goes(luts, tmp_path):
    """Refused before a byte goes out: a file outside private/lut/ (beside it, in another clone's, up a ".."), a link
    out of it or within it, a folder, a name Sony's reference does not take or another extension than .cube, 3,000,000
    bytes or more, no .cube LUT's text, a file that is not there; and a clone with no LUT folder at all."""
    run, log, folder, lut = luts
    clone = folder.parent.parent
    outside = [made(clone / "private" / "data", NAME), made(clone, NAME), made(tmp_path / "other" / "private" / "lut", NAME),
               made(clone / "private" / "lutx", NAME)]
    (folder / "out.cube").symlink_to(outside[0])
    (folder / "in.cube").symlink_to(lut)
    (folder / "pack").symlink_to(outside[2].parent, target_is_directory=True)
    (folder / "folder.cube").mkdir()
    bad = {"not under": outside + [folder / ".." / "data" / NAME, folder / "pack" / NAME],
           "link": [folder / "out.cube", folder / "in.cube"],
           "not a file": [folder / "folder.cube"],
           "not there": [folder / "missing.cube"],
           ".cube": [made(folder, "x.cub"), made(folder, "x.CUBE"), made(folder, "x.txt"), made(folder, "x.cube.txt")],
           "63": [made(folder, "a" * 59 + ".cube")],
           "period": [made(folder, ".x.cube")],
           "character": [made(folder, "a!b.cube"), made(folder, "café.cube"), made(folder, "a:b.cube")],
           "3,000,000": [made(folder, "big.cube", CUBE + " " * (L.LUT_MAX_BYTES - len(CUBE)))],
           "LUT_3D_SIZE": [made(folder, "words.cube", "only words\n"), made(folder, "nul.cube", "LUT_3D_SIZE 2\n\0")]}
    assert not L.lut_refused(made(folder, "a" * 58 + ".cube"))                     # 63 with ".cube": taken
    assert not L.lut_refused(made(folder, "ok.cube", CUBE + " " * (L.LUT_MAX_BYTES - 1 - len(CUBE))))
    with opened(run) as link:
        for said, files in bad.items():
            for f in files:
                with pytest.raises(safety.Refused, match=said.replace(".", r"\.").replace("(", r"\(")):
                    link.import_lut(f)
    assert not [raw for raw in received(log) if b"importlut" in raw]
    assert sum(e["kind"] == "lut_refused" for e in events(run)) == sum(len(f) for f in bad.values())
    assert "there is no folder" in L.lut_refused(lut, folder=folder.parent / "no lut here")


def test_a_line_written_by_hand_goes_through_the_same_guard(luts):
    """Link.call is the one way to camlink: an importlut line not as import_lut writes it (no hash, another file's
    hash, a path not resolved, a file outside the folder, a place out of range or written oddly, a word too many) is
    refused before a byte goes out."""
    run, log, folder, lut = luts
    real, digest = lut.resolve(), hashlib.sha256(CUBE.encode()).hexdigest()
    other = made(folder.parent / "data", NAME).resolve()
    with opened(run) as link:
        for line in (f"importlut {quoted(real)} 16", f"importlut {quoted(real)} 16 {'0' * 64}",
                     f"importlut {quoted(folder / 'Look Pack' / '..' / 'Look Pack' / NAME)} 16 {digest}",
                     f"importlut {quoted(other)} 16 {digest}", f"importlut {quoted(real)} 17 {digest}",
                     f"importlut {quoted(real)} 016 {digest}", f"importlut {quoted(real)} x {digest}",
                     f"importlut {quoted(real)} 16 {digest} more", "importlut"):
            with pytest.raises(safety.Refused):
                link.call(line)
        assert link.call(f"importlut {quoted(real)} 16 {digest}")["ok"]
    assert [raw for raw in received(log) if b"importlut" in raw] == [f"@1 importlut {quoted(real)} 16 {digest}\n".encode()]


def test_a_stop_and_a_picture_link_import_nothing(luts):
    run, log, _, lut = luts
    with opened(run) as link:
        (run.dir / "STOP").write_text("", encoding="utf-8")
        with pytest.raises(StopRequested):
            link.import_lut(lut)
    (run.dir / "STOP").unlink()
    with Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False, picture=True) as link, \
            pytest.raises(safety.Refused, match="imports nothing"):
        link.import_lut(lut)
    assert not [raw for raw in received(log) if b"importlut" in raw]


@pytest.mark.parametrize("answer,called,said", [
    ({"ok": False, "cause": "import_disabled", "called": False, "enable_status": 0,
      "error": "not imported: BaseLookImportOperationEnableStatus reads 0 (Disable)"}, False, "reads 0"),
    ({"ok": False, "cause": "import_refused", "called": True, "result": "ImportLUTFile_Result_NG",
      "error": "not imported: the camera answered ImportLUTFile_Result_NG"}, True, "ImportLUTFile_Result_NG"),
    ({"ok": False, "cause": "import_unconfirmed", "called": True,
      "error": "no answer from the camera within 120 s: whether the LUT went in is not known"}, True, "not known"),
    ({"ok": True, "result": "ImportLUTFile_Result_Invalid"}, True, "not confirmed"),        # ok without the camera's OK
    ({"sha256": "0" * 64}, True, "not the bytes"),                                          # another file's bytes went
    ({"ok": False, "error": "unknown command importlut", "called": None}, False, "older than the kit"),
])
def test_an_import_the_camera_did_not_confirm_is_never_a_success(luts, monkeypatch, answer, called, said):
    """Only the camera's ImportLUTFile_Result_OK, for the bytes the kit checked, is a success: every other answer raises
    LutNotImported, which carries camlink's answer and whether the SDK was asked (the tool restores whenever it was);
    an older camlink that does not know the command is told apart, nothing having been sent."""
    run, _, _, lut = luts
    monkeypatch.setenv("FAKE_CAMLINK_IMPORTLUT", json.dumps(answer))
    with opened(run) as link, pytest.raises(LutNotImported, match=said) as e:
        link.import_lut(lut)
    assert e.value.called is called and isinstance(e.value, LinkError)
    assert e.value.reply.get("cause") == answer.get("cause")


def test_a_lut_swapped_after_the_check_is_not_imported(luts, monkeypatch):
    """The kit hashes the file, camlink reads it again: one written between the two is refused by camlink
    ("hash_mismatch"), nothing imported, and said so."""
    run, log, _, lut = luts
    real = provenance.sha256
    seen = []

    def hash_then_swap(path):
        digest = real(path)
        seen.append(digest)
        if len(seen) == 2:                                       # the guard's: camlink reads what comes after it
            Path(path).write_text(CUBE + "# written after the check\n", encoding="utf-8")
        return digest
    monkeypatch.setattr(provenance, "sha256", hash_then_swap)
    with opened(run) as link, pytest.raises(LutNotImported, match="written after") as e:
        link.import_lut(lut)
    assert e.value.called is False and e.value.reply["cause"] == "hash_mismatch"


def test_a_lut_is_no_settings_file_and_never_an_upload(luts):
    """The import does not go through Link.upload's check, which is for the camera's own settings files (decision 6),
    and a LUT does not pass that check either: it is no download of the camera's. Link.import_lut's docstring says why
    a look-up table is another thing."""
    run, log, _, lut = luts
    with opened(run) as link, pytest.raises(LinkError, match="not a camera download"):
        link.upload(lut)
    assert not [raw for raw in received(log) if b"upload" in raw]
    doc = " ".join(Link.import_lut.__doc__.split())
    for words in ("no settings file", "docs/decisions/0006", "from a card", "ImportLUTFile"):
        assert words in doc, words
