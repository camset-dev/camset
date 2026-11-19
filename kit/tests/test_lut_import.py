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
import time
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
    for word in ("importlut PATH 16 SHA256", "not_a_lut", "import_disabled", "import_refused", "import_unconfirmed",
                 "ImportLUTFile_Result_OK", "docs/decisions/0026"):
        assert word in head, word
    assert src.count("SCRSDK::ImportLUTFile(") == 1
    body = src.split("static void cmdImportLut", 1)[1].split("\n}\n", 1)[0]
    for call in ("UploadSettingFile", "DownloadSettingFile", "SetDeviceProperty", "DeleteUserBaseLook_All", "Firmware",
                 "SendCommand"):
        assert call not in body, call
    # the decisions are lut_file.h's, tested there: camlink reads, asks plan(), sends the copy's path, asks judge()
    assert "lut_file::plan(" in body and "lut_file::judge(" in body
    assert "crPath(plan.copy.path)" in body and "crPath(plan.file" not in body and "u8path(path))" not in body.split(
        "lut_file::plan(", 1)[1].split(";", 1)[1]
    for refusal in ("placeProblem", "check(", "enableProblem", "recordingProblem", "placeHeld", "stateRefusal"):
        assert f"lut_file::{refusal}" not in body, refusal                      # made in plan(), never beside it
    # the clone's own LUT folder is built in (MEDIUM 1): camlink's CAMSET_LUT_DIR, from this clone's private/lut
    cmake = (ROOT / "kit" / "link" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "CAMSET_LUT_DIR" in cmake and "../../private/lut" in cmake and "fs::u8path(CAMSET_LUT_DIR)" in body


# ---------------------------------------------------------------- Link.import_lut

def test_a_lut_goes_by_its_real_path_into_place_16_with_its_hash(luts):
    """The one line that goes out: the file's real path, quoted, place 16, and the SHA-256 of its bytes, which camlink
    checks the bytes it reads against. The run's log keeps the file's name, size, place and hash, never its content;
    the camera's answer comes back as it is."""
    run, log, folder, lut = luts
    digest = hashlib.sha256(CUBE.encode()).hexdigest()
    with opened(run) as link:
        r = link.import_lut(folder / "Look Pack" / ".." / "Look Pack" / NAME)
        assert r["ok"] and r["result"] == L.LUT_OK and r["place"] == 16 and r["sha256"] == digest
    sent = received(log)
    assert sent == [f"@1 importlut {quoted(lut.resolve())} 16 {digest}\n".encode(), b"quit\n"]
    kept = [e for e in events(run) if e["kind"] == "lut_import"]
    assert [(e["file"], e["sha256"], e["bytes"], e["place"]) for e in kept] == [(NAME, digest, len(CUBE), 16)]
    assert "LUT_3D_SIZE" not in (run.dir / "events.jsonl").read_text(encoding="utf-8")


def test_place_16_alone(luts):
    """The owner approved user place 16 alone (docs/decisions/0026): Link.import_lut takes no place, and a line naming
    another, however written, is refused before a byte goes out."""
    import inspect
    run, log, _, lut = luts
    assert list(inspect.signature(Link.import_lut).parameters) == ["self", "path"] and L.LUT_PLACE == 16
    digest = hashlib.sha256(CUBE.encode()).hexdigest()
    with opened(run) as link:
        for place in ("1", "3", "15", "17", "0", "016", "0x10", "-16", "16.0"):
            with pytest.raises(safety.Refused, match="16"):
                link.call(f"importlut {quoted(lut.resolve())} {place} {digest}")
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
                     f"importlut {quoted(other)} 16 {digest}", f"importlut {quoted(real)} 15 {digest}",
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
    for words in ("no settings file", "docs/decisions/0006", "docs/decisions/0026", "from a card", "ImportLUTFile"):
        assert words in doc, words
    assert "2026-11-19" not in doc                       # the record is cited, not the day (the review, MINE 2)


# ---------------------------------------------------------------- kit/tools/lut_import.py

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
SETS_BACK = 0x0050          # a record a settings file sets back
STAYS = 0x1126              # one it does not (on the ILCE-1M2: upload_check.KNOWN_LEFT)
ELSEWHERE = 0x0051          # a record the import does not change


def changed(*rids) -> bytes:
    """The sample's bytes with the first byte of each record `rids` names changed."""
    from camkit import camset
    cs = camset.read(SAMPLE)
    out = {}
    for rid in rids:
        raw = bytearray(cs.get(0, rid).raw)
        raw[0] ^= 1
        out[(0, rid)] = bytes(raw)
    return camset.with_values(cs, out)


class Camera:
    """What the tool's stand-in link and restore check see: the enable status get answers (None: the property cannot be
    read), what import_lut does (a reply dict to return, or an exception to raise), the records the camera's download
    after the import differs from the start file in, those still differing after the restore (None: no reconnection),
    and whether the start download is refused. `sent` lists what reached the camera, in order."""

    def __init__(self, status=1, imports=None, after=(SETS_BACK, STAYS), restored=(STAYS,), start_refused=False,
                 after_refused=False):
        self.status, self.imports, self.after, self.restored = status, imports, after, restored
        self.start_refused, self.after_refused = start_refused, after_refused
        self.sent, self.imported = [], False


def stand_in(monkeypatch, cam: Camera):
    """The tool's Link and verify_restore stood in by `cam`, its LUT folder the test's own; returns the module."""
    import lut_import as T

    class StandIn:
        def __init__(self, run, **kw):
            self.run = run

        def __enter__(self):
            cam.sent.append("open")
            return self

        def __exit__(self, *exc):
            cam.sent.append("close")
            return False

        def download(self, tag):
            cam.sent.append(f"download {tag}")
            if (tag == "start" and cam.start_refused) or (tag != "start" and cam.after_refused):
                raise LinkError("download: camera does not allow a settings download now")
            p = self.run.dat / f"{self.run.dat_name(tag)}.DAT"
            p.write_bytes(changed(*cam.after) if cam.imported and tag != "start" else SAMPLE.read_bytes())
            provenance.record(p, self.run.root, run=self.run.dir.name)          # a camera download, as Link's are
            return p

        def get(self, name):
            cam.sent.append(f"get {name}")
            if cam.status is None:
                raise LinkError(f"get {name}: unknown property {name}")
            return {"ok": True, "current": cam.status}

        def import_lut(self, path):
            place = 16
            cam.sent.append(f"importlut {Path(path).name} {place}")
            if isinstance(cam.imports, BaseException):
                cam.imported = getattr(cam.imports, "called", False)
                raise cam.imports
            cam.imported = True
            return cam.imports or {"ok": True, "result": L.LUT_OK, "place": place, "called": True, "ms": 1200}

        def upload(self, f):
            cam.sent.append(f"upload {Path(f).name}")
            return {"ok": True}

    def verify(run, start, expected=frozenset(), **kw):
        cam.sent.append("verify")
        if cam.restored is None:
            return None
        p = run.dat / f"{run.dat_name('restored')}.DAT"
        p.write_bytes(changed(*cam.restored))
        from camkit import camset
        return len([c for c in camset.diff(camset.read(start), camset.read(p)) if c.key not in expected])
    monkeypatch.setattr(T, "Link", StandIn)
    monkeypatch.setattr(T, "verify_restore", verify)
    return T


def tool(monkeypatch, luts, cam: Camera, *args) -> int:
    run, _, folder, lut = luts
    T = stand_in(monkeypatch, cam)
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(lut), *args])
    return T.main()


def key(rid) -> str:
    return f"global:0x{rid:04x}"


def test_the_lut_goes_in_its_records_are_said_and_the_start_file_goes_back(monkeypatch, luts, capsys):
    """The whole run: the start download, the enable status read and said, the import, the download after it and every
    record that differs from the start file said with its values, the start file put back, the restore checked with
    the import's records left out of the count, and those that did not go back said as expected: a user LUT is state
    no settings file puts back, and it stays in its place until the owner deletes it by hand. Exit 0. No key pressed."""
    cam = Camera()
    assert tool(monkeypatch, luts, cam) == 0
    assert cam.sent == ["open", "download start", "get BaseLookImportOperationEnableStatus", f"importlut {NAME} 16",
                        "download after-lut", "upload 00001_start.DAT", "close", "verify"]
    out = capsys.readouterr().out
    assert "BaseLookImportOperationEnableStatus reads 1 (Enable)" in out
    assert f"{L.LUT_OK}: {NAME} is in user place 16" in out
    assert "2 records differ from the start file" in out
    assert f"   {key(SETS_BACK)}" in out and f"   {key(STAYS)}" in out and " -> " in out
    assert f"did not go back: {key(STAYS)}" in out and "expected, not an error" in out
    assert "until the owner deletes it on the camera by hand" in out
    run = Run("kit2_lut")                                       # the tool's own run, in the test's runs/
    line = json.loads((run.dir / "lut_import.jsonl").read_text(encoding="utf-8"))
    assert line["file"] == NAME and line["place"] == 16 and line["result"] == L.LUT_OK and line["exit"] == 0
    assert line["records_changed"] == [key(SETS_BACK), key(STAYS)] and line["not_back"] == [key(STAYS)]
    assert line["sha256"] == hashlib.sha256(CUBE.encode()).hexdigest()
    assert "LUT_3D_SIZE" not in json.dumps(line)


@pytest.mark.parametrize("status,said", [(0, "reads 0 (Disable)"), (2, "reads 2"), (None, "could not be read")])
def test_an_import_the_camera_does_not_enable_is_not_tried(monkeypatch, luts, capsys, status, said):
    """BaseLookImportOperationEnableStatus not Enable, or unreadable: said plainly with what the camera reads, nothing
    imported, the session ended as ever (a download compared with the start file: nothing to put back). Exit 8."""
    from exit_status import EXIT_INCOMPLETE
    cam = Camera(status=status)
    assert tool(monkeypatch, luts, cam) == EXIT_INCOMPLETE
    assert not [s for s in cam.sent if s.startswith(("importlut", "upload", "verify"))]
    assert cam.sent[-2:] == ["download after", "close"]
    out = capsys.readouterr().out
    assert said in out and "nothing was imported" in out and "Movie" in out
    assert "0 records differ from the start file" in out


@pytest.mark.parametrize("called", [False, True])
def test_an_import_the_camera_refused_or_left_unconfirmed_is_said_as_that(monkeypatch, luts, capsys, called):
    """The camera's refusal before the SDK was asked (nothing changed), or an answer that never came after it was (the
    camera may have changed: its download is compared, and anything that differs put back): never a success. Exit 8,
    the start file back."""
    from exit_status import EXIT_INCOMPLETE
    reply = ({"ok": False, "cause": "import_unconfirmed", "called": True, "error": "no answer within 120 s"} if called
             else {"ok": False, "cause": "import_refused", "called": False, "error": "place 16 already holds a LUT"})
    cam = Camera(imports=LutNotImported(f"the import of {NAME} into place 16 is not confirmed: {reply['error']}", reply))
    assert tool(monkeypatch, luts, cam) == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "no import confirmed" in out and reply["error"] in out and L.LUT_OK + ":" not in out
    assert "stays in user place" not in out
    if called:
        assert "may have changed" in out and "upload 00001_start.DAT" in cam.sent and "verify" in cam.sent
    else:
        assert not [s for s in cam.sent if s.startswith(("upload", "verify"))]


def test_a_restore_that_does_not_check_out_exits_unrestored(monkeypatch, luts, capsys):
    """A record the import did not change still differing after the restore, or no reconnection, or the download after
    the import refused every time: exit 4, saying how the start file goes back."""
    from exit_status import EXIT_UNRESTORED
    assert tool(monkeypatch, luts, Camera(restored=(STAYS, ELSEWHERE))) == EXIT_UNRESTORED
    assert "did not check out" in capsys.readouterr().out
    assert tool(monkeypatch, luts, Camera(restored=None)) == EXIT_UNRESTORED
    assert "did not answer after its restart" in capsys.readouterr().out
    monkeypatch.setattr("lut_import.PAUSE", 0)
    cam = Camera(after_refused=True)
    assert tool(monkeypatch, luts, cam) == EXIT_UNRESTORED
    assert "kit/tools/upload_check.py" in capsys.readouterr().out
    assert not [s for s in cam.sent if s.startswith("upload")]


def test_nothing_is_sent_for_a_file_or_place_the_kit_does_not_import(monkeypatch, luts, capsys, tmp_path):
    """A file outside the clone's LUT folder: refused before any link opens, exit 1; the tool takes no other place than
    16 (no --place: argparse stops it, exit 2); a camera that refuses the start download: said, nothing imported,
    exit 1."""
    cam = Camera()
    outside = made(tmp_path / "elsewhere", NAME)
    T = stand_in(monkeypatch, cam)
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(outside)])
    assert T.main() == 1
    assert capsys.readouterr().out.count("nothing was sent") == 1
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(luts[3]), "--place", "15"])
    with pytest.raises(SystemExit) as e:
        T.main()
    assert e.value.code == 2 and cam.sent == []
    cam = Camera(start_refused=True)
    assert tool(monkeypatch, luts, cam) == 1
    assert cam.sent == ["open", "download start", "close"]
    assert "shooting screen" in capsys.readouterr().out


def test_the_whole_run_through_the_link_and_the_stand_in_camlink(monkeypatch, luts, tmp_path, capsys):
    """The tool with the kit's own Link and restore check, the stand-in camlink answering: what reaches camlink is the
    start download, the enable status's get, one importlut, the download after it, the start file's upload (the
    camera's word on Playback asked first, a read) and the restore check's download on a new link: no press, no dial,
    no set, and nothing but the import and the upload that changes the camera."""
    import functools
    from camkit import session
    import lut_import as T
    run, log, _, lut = luts
    after, restored = tmp_path / "after.DAT", tmp_path / "restored.DAT"
    after.write_bytes(changed(SETS_BACK, STAYS))
    restored.write_bytes(changed(STAYS))
    monkeypatch.setenv("FAKE_CAMLINK_GET", json.dumps({"BaseLookImportOperationEnableStatus": {"current": 1}}))
    monkeypatch.setenv("FAKE_CAMLINK_DOWNLOADS", json.dumps({"_after-lut": str(after), "_restored": str(restored)}))
    linked = functools.partial(Link, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False)

    class Clock:                                       # the restart waited for without waiting
        @staticmethod
        def monotonic():
            return time.monotonic()

        @staticmethod
        def sleep(s):
            pass
    monkeypatch.setattr(T, "Link", linked)
    monkeypatch.setattr(T, "verify_restore", functools.partial(session.verify_restore, link_class=linked, clock=Clock))
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(lut)])
    assert T.main() == 0
    verbs = [raw.split(b" ", 2)[1].strip() for raw in received(log) if raw.startswith(b"@")]
    assert set(verbs) <= {b"download", b"get", b"props", b"importlut", b"upload"}
    assert [v for v in verbs if v in (b"download", b"importlut", b"upload")] == \
        [b"download", b"importlut", b"download", b"upload", b"download"]
    assert verbs[1] == b"get" and verbs.count(b"importlut") == 1 and verbs.count(b"upload") == 1
    out = capsys.readouterr().out
    assert f"did not go back: {key(STAYS)}" in out and "after the restore: 0 records differ" in out


def test_the_finding_is_kept_in_the_coverage_ledger_by_the_record_commands_it_prints(monkeypatch, luts, capsys):
    """Once the camera took the LUT, the tool prints the two kit/tools/coverage.py --record commands that keep the
    finding in the looks file for Manage User LUTs and its Import/Edit (Movie, Exposure/Color, Color/Tone), with the
    run's start download and the one after the import, both the camera's own: records changed, --did act (a hand
    check that changed a record: "proved by hand"); none changed, --did choose ("tested, no record changes"). Never
    for an import the camera did not confirm. The commands run as printed: coverage.py's record() takes them."""
    import shlex
    assert tool(monkeypatch, luts, Camera()) == 0
    out = capsys.readouterr().out
    lines = [x.strip() for x in out.splitlines() if "kit/tools/coverage.py --record" in x]
    assert len(lines) == 2
    first, second = (shlex.split(x) for x in lines)
    for words in (first, second):
        assert words[words.index("--mode") + 1] == "Movie" and words[words.index("--did") + 1] == "act"
        assert words[words.index("--start") + 1].endswith("_start.DAT")
        assert words[words.index("--end") + 1].endswith("_after-lut.DAT")
    assert first[first.index("--path") + 1] == "Exposure/Color > Color/Tone > Manage User LUTs > Import/Edit"
    assert first[first.index("--option") + 1] == "User16"
    assert second[second.index("--path") + 1] == "Exposure/Color > Color/Tone > Manage User LUTs"
    assert "--option" not in second
    assert tool(monkeypatch, luts, Camera(after=())) == 0
    lines = [x for x in capsys.readouterr().out.splitlines() if "kit/tools/coverage.py --record" in x]
    assert len(lines) == 2 and all("--did choose" in x for x in lines) and "--option User16" in lines[0]
    reply = {"ok": False, "cause": "import_unconfirmed", "called": True, "error": "no answer within 120 s"}
    assert tool(monkeypatch, luts, Camera(imports=LutNotImported("not confirmed", reply))) == 8
    assert "coverage.py --record" not in capsys.readouterr().out


def test_the_printed_record_command_writes_a_look_with_keys_alone(monkeypatch, luts, capsys):
    """The first printed command, run through kit/tools/coverage.py's own record(), writes one look by hand into the
    test's own looks file: the row, did act, the option, the records that changed by key alone, never a value."""
    import runpy
    import shlex
    from camkit import coverage as ledger, paths
    assert tool(monkeypatch, luts, Camera()) == 0
    line = next(x.strip() for x in capsys.readouterr().out.splitlines() if "coverage.py --record" in x)
    words = shlex.split(line)
    assert words[:2] == [".venv/bin/python", "kit/tools/coverage.py"]
    # the made-up camera has no definition: the ledger stood in by one that knows the tab and finds no row (record()
    # says so and records the look all the same)
    monkeypatch.setattr(ledger, "build", lambda camera, public=True: type("Led", (), {
        "src": type("Src", (), {"definition": {"tabs": ["Exposure/Color"]}})(), "find": lambda self, *a: []})())
    monkeypatch.setattr(sys, "argv", ["coverage.py", *words[2:]])
    runpy.run_path(str(ROOT / "kit" / "tools" / "coverage.py"), run_name="__main__")
    camera = paths.camera()[0]
    looks = [json.loads(x) for x in ledger.looks_file(camera).read_text(encoding="utf-8").splitlines()]
    assert len(looks) == 1
    lk = looks[0]
    assert (lk["by"], lk["did"], lk["result"], lk["option"], lk["mode"]) == ("hand", "act", "changed", "User16", "Movie")
    assert (lk["tab"], lk["group"], lk["path"]) == ("Exposure/Color", "Color/Tone", ["Manage User LUTs", "Import/Edit"])
    assert lk["records_changed"] == [key(SETS_BACK), key(STAYS)]
    assert "ImportLUTFile" in lk["note"] and " -> " not in json.dumps(lk)

