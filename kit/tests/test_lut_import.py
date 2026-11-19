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
    for refusal in ("placeProblem", "check(", "enableProblem", "recordingProblem", "listProblem", "stateRefusal"):
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
    """What the tool's stand-in link, eyes and restore check see: the enable status get answers (None: the property
    cannot be read), what import_lut does (a reply dict to return, or an exception to raise), the records the camera's
    download after the import differs from the start file in, those a download at the end differs in whatever was
    imported (`drift`: another cause), those still differing after the restore (None: no reconnection), whether the
    start download is refused or the one at the end, the kind of screen the camera's own picture reads as before the
    end, and whether the camera says it is in Playback. `sent` lists what reached the camera, in order."""

    def __init__(self, status=1, imports=None, after=(SETS_BACK, STAYS), restored=(), start_refused=False,
                 after_refused=False, drift=(), screen="shooting", playback=False):
        self.status, self.imports, self.after, self.restored = status, imports, after, restored
        self.start_refused, self.after_refused, self.drift = start_refused, after_refused, drift
        self.screen, self.playback = screen, playback
        self.sent, self.imported = [], False


def stand_in(monkeypatch, cam: Camera):
    """The tool's Link, verify_restore, lock wait, screen check and hold for the owner stood in by `cam`, its LUT folder
    and its RESTORE_BY_HAND marker the test's own; returns the module."""
    import camkit
    import lut_import as T
    from camkit import paths
    monkeypatch.setattr(camkit, "RUNS", paths.runs_top())   # a marker in the test's own runs/ alone, never the clone's

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
            rids = () if tag == "start" else tuple(cam.drift) + (tuple(cam.after) if cam.imported else ())
            p.write_bytes(changed(*rids) if rids else SAMPLE.read_bytes())
            provenance.record(p, self.run.root, run=self.run.dir.name)          # a camera download, as Link's are
            return p

        def in_playback(self):
            return cam.playback

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
        cam.sent.append(f"verify expected={sorted(expected)}")
        if cam.restored is None:
            return None
        p = run.dat / f"{run.dat_name('restored')}.DAT"
        p.write_bytes(changed(*cam.restored) if cam.restored else SAMPLE.read_bytes())
        from camkit import camset
        return len([c for c in camset.diff(camset.read(start), camset.read(p)) if c.key not in expected])

    def screen_kind(link, eyes, tag="end-check"):
        cam.sent.append(f"look {tag}")
        return cam.screen

    def hold(link, eyes, start, why, **kw):
        from camkit.runs import mark_restore_by_hand
        cam.sent.append(f"hold: {why}")
        mark_restore_by_hand(link.run.root, link.run.dir.name, start, why)
        raise SystemExit(5)
    monkeypatch.setattr(T, "Link", StandIn)
    monkeypatch.setattr(T, "verify_restore", verify)
    monkeypatch.setattr(T, "screen_kind", screen_kind)
    monkeypatch.setattr(T, "hold_for_owner", hold)
    monkeypatch.setattr(T, "wait_lock", lambda since, eyes=None, **kw: cam.sent.append("lock"))
    monkeypatch.setattr(T, "PAUSE", 0)
    return T


ALLOW = ["--allow", "Manage User LUTs"]
EMPTY_ROWS = [f"User{n}: (No Import)" for n in range(11, 17)]       # the camera's table scrolled to User16, all empty
LOOK_PATH = ["Manage User LUTs", "Import/Edit"]


def look(root: Path, rows=None, ago: float = 600.0, path=LOOK_PATH, title="Import/Edit", run="kit2_lut_look",
         name="00034_down.png", now=None, text=None) -> Path:
    """A look at the camera's Import/Edit table, as kit/drive.py leaves it in its run: the frame in shots/, its press in
    events.jsonl `ago` s before `now`, and drive.jsonl's line naming the path, the frame and the screen's text as the
    kit's OCR read it (the title, the column heads, the rows, the footer, joined by spaces, as kit2_fin_lut_table's
    00034_down.png has it), or `text` as given."""
    now = time.time() if now is None else now
    d = root / run
    (d / "shots").mkdir(parents=True, exist_ok=True)
    frame = d / "shots" / name
    frame.write_bytes(b"\x89PNG\r\n\x1a\n a made-up frame " + name.encode() + str(now - ago).encode())
    if text is None:
        text = " ".join(([title] if title else []) + ["User LUT Input AE Level Offset"]
                        + list(EMPTY_ROWS if rows is None else rows) + ["IMENU D"])
    with open(d / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now - ago, "kind": "press", "key": "down", "frame": name, "screen": "unknown"}) + "\n")
    with open(d / "drive.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"path": path, "presses": ["right", "down", "menu"], "completed": True,
                            "screens": [{"after": "down", "frame": name, "kind": "unknown", "text": text}]}) + "\n")
    return frame


def tool(monkeypatch, luts, cam: Camera, *args, allow=ALLOW, seen="look") -> int:
    """The tool run on the test's LUT with the owner's word and, unless `seen` says otherwise, a look at an empty table
    taken just now (look()), so after any import a run before it in the test asked for."""
    from camkit import paths
    run, _, folder, lut = luts
    T = stand_in(monkeypatch, cam)
    seen_args = ["--seen-empty", str(look(paths.run_root(), ago=0) if seen == "look" else seen)] if seen else []
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(lut), *allow, *seen_args, *args])
    return T.main()


def jsonl_lines() -> list:
    """The tool's lut_import.jsonl lines, in the test's runs/ (the tool's run: kit2_lut)."""
    p = Run("kit2_lut").dir / "lut_import.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def marker() -> dict | None:
    from camkit.runs import restore_pending
    return restore_pending(Run("kit2_lut").root)


def key(rid) -> str:
    return f"global:0x{rid:04x}"


def test_the_lut_goes_in_its_records_are_said_and_the_start_file_goes_back(monkeypatch, luts, capsys):
    """The whole run: the start download, the menu's lock waited out, the enable status read and said, the import, the
    camera's own picture of its screen looked at, the download after the import and every record that differs from the
    start file said with its values, the start file put back, the restore checked with the import's records left out of
    its count, every record back. Exit 0; the allowance in both logs. No key pressed."""
    cam = Camera()
    assert tool(monkeypatch, luts, cam) == 0
    assert cam.sent == ["open", "download start", "lock", "get BaseLookImportOperationEnableStatus",
                        f"importlut {NAME} 16", "look end-check", "download after-lut", "upload 00001_start.DAT", "close",
                        f"verify expected={[key(SETS_BACK), key(STAYS)]}"]
    out = capsys.readouterr().out
    assert "operator allowed these never-open rows: 'Manage User LUTs'" in out
    assert "BaseLookImportOperationEnableStatus reads 1 (Enable)" in out
    assert f"{L.LUT_OK}: {NAME} is in user place 16" in out
    assert "2 records differ from the start file" in out and "as the import left them" in out
    assert f"   {key(SETS_BACK)}" in out and f"   {key(STAYS)}" in out and " -> " in out
    assert "the restore put back every record that differed (2)" in out
    assert "until the owner deletes it on the camera by hand" in out
    line = jsonl_lines()[-1]
    assert line["file"] == NAME and line["place"] == 16 and line["result"] == L.LUT_OK and line["exit"] == 0
    assert line["records_changed"] == [key(SETS_BACK), key(STAYS)] and line["confirmed"] is True
    assert "Manage User LUTs" in line["allowance"]
    assert line["sha256"] == hashlib.sha256(CUBE.encode()).hexdigest()
    assert "LUT_3D_SIZE" not in json.dumps(line)
    logged = [e for e in events(Run("kit2_lut")) if e["kind"] == "lut_allowance"]
    assert logged and logged[-1]["allow"] == ["Manage User LUTs"]


def test_a_record_left_off_after_a_confirmed_import_fails_the_restore(monkeypatch, luts, capsys):
    """HIGH 2 (with an import): the camera took the LUT and a record it changed did not go back. No record is named yet
    as holding a user LUT (camkit.not_by_file.USER_LUT), so the run says which, to be looked at on the camera, and exits
    4, never 0, so a chain stops with the camera off the owner's file. Once the record is named there, it may stay."""
    from camkit import not_by_file
    from exit_status import EXIT_UNRESTORED
    assert tool(monkeypatch, luts, Camera(restored=(STAYS,))) == EXIT_UNRESTORED
    out = capsys.readouterr().out
    assert f"did not go back to the start file: {key(STAYS)}" in out and "Look at these settings on the camera" in out
    assert jsonl_lines()[-1]["exit"] == EXIT_UNRESTORED
    monkeypatch.setitem(not_by_file.USER_LUT, "ILCE-1M2", (key(STAYS),))
    import lut_import as T
    monkeypatch.setattr(T, "USER_LUT", not_by_file.USER_LUT)
    assert tool(monkeypatch, luts, Camera(restored=(STAYS,))) == 0
    assert f"each one camkit.not_by_file.USER_LUT names as holding a user LUT: {key(STAYS)}" in capsys.readouterr().out
    # a record the import did not change left off fails it whatever USER_LUT names
    assert tool(monkeypatch, luts, Camera(restored=(STAYS, ELSEWHERE))) == EXIT_UNRESTORED
    assert f"did not go back to the start file: {key(ELSEWHERE)}" in capsys.readouterr().out


def test_a_record_left_off_without_an_import_is_never_called_the_lut_s(monkeypatch, luts, capsys):
    """HIGH 2 (without an import): the enable status read Disable, nothing was imported, and a record changed by another
    cause did not go back. Nothing is excused (no expected records for the restore check), nothing is said to be the
    import's or a LUT's, and the run exits 4, not 8 (which says the camera is on its start file again)."""
    from exit_status import EXIT_UNRESTORED
    cam = Camera(status=0, drift=(ELSEWHERE,), restored=(ELSEWHERE,))
    assert tool(monkeypatch, luts, cam) == EXIT_UNRESTORED
    assert "verify expected=[]" in cam.sent and not [s for s in cam.sent if s.startswith("importlut")]
    out = capsys.readouterr().out
    assert f"did not go back to the start file: {key(ELSEWHERE)}" in out and "Look at these settings on the camera" in out
    assert "as the import left them" not in out and "user LUT" not in out.split("records did not go back")[1]


@pytest.mark.parametrize("status,said", [(0, "reads 0 (Disable)"), (2, "reads 2"), (None, "could not be read")])
def test_an_import_the_camera_does_not_enable_is_not_tried(monkeypatch, luts, capsys, status, said):
    """BaseLookImportOperationEnableStatus not Enable, or unreadable: said plainly with what the camera reads, nothing
    imported, the session ended as ever (a download compared with the start file: nothing to put back). Exit 8."""
    from exit_status import EXIT_INCOMPLETE
    cam = Camera(status=status)
    assert tool(monkeypatch, luts, cam) == EXIT_INCOMPLETE
    assert not [s for s in cam.sent if s.startswith(("importlut", "upload", "verify"))]
    assert cam.sent[-3:] == ["look end-check", "download after", "close"]
    out = capsys.readouterr().out
    assert said in out and "nothing was imported" in out and "Movie" in out
    assert "0 records differ from the start file" in out


def test_an_import_the_camera_refused_is_said_as_that(monkeypatch, luts, capsys):
    """The camera's refusal before the SDK was asked (place 16 held): never a success, nothing changed, the session
    ended as ever with nothing to put back. Exit 8."""
    from exit_status import EXIT_INCOMPLETE
    reply = {"ok": False, "cause": "import_refused", "called": False, "error": "place 16 already holds a LUT"}
    cam = Camera(imports=LutNotImported(f"the import of {NAME} into place 16 is not confirmed: {reply['error']}", reply))
    assert tool(monkeypatch, luts, cam) == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "no import confirmed" in out and reply["error"] in out and L.LUT_OK + ":" not in out
    assert "stays in user place" not in out and "coverage.py --record" not in out
    assert "download after" in cam.sent and not [s for s in cam.sent if s.startswith(("upload", "verify"))]


def test_an_unconfirmed_import_sends_nothing_more_and_is_restored_by_hand(monkeypatch, luts, capsys):
    """LOW 1: the camera's answer did not come (camlink's "import_unconfirmed"): the import may still be running, so no
    download and no upload (which restarts the camera) is sent; RESTORE_BY_HAND names the start file, the owner is told
    to look at Manage User LUTs, and the link closes over the shooting screen. Exit 5."""
    from exit_status import EXIT_RESTORE_BY_HAND
    reply = {"ok": False, "cause": "import_unconfirmed", "called": True, "error": "no answer within 120 s"}
    cam = Camera(imports=LutNotImported(f"the import of {NAME} into place 16 is not confirmed: {reply['error']}", reply))
    assert tool(monkeypatch, luts, cam) == EXIT_RESTORE_BY_HAND
    assert cam.sent[-3:] == [f"importlut {NAME} 16", "look end-check", "close"]
    assert not [s for s in cam.sent if s.startswith(("download after", "upload", "verify"))]
    out = capsys.readouterr().out
    assert "Manage User LUTs > Import/Edit" in out and "kit/tools/upload_check.py kit2_lut/dat/00001_start.DAT" in out
    assert marker()["start"].endswith("00001_start.DAT") and jsonl_lines()[-1]["exit"] == EXIT_RESTORE_BY_HAND
    # over any other screen the link is not closed but held for the owner, the marker kept
    cam = Camera(imports=LutNotImported("not confirmed", reply), screen="dialog")
    with pytest.raises(SystemExit) as e:
        tool(monkeypatch, luts, cam)
    assert e.value.code == EXIT_RESTORE_BY_HAND and any(s.startswith("hold: ") for s in cam.sent)


@pytest.mark.parametrize("raised,code", [(LinkError("importlut: no reply within 150 s"), 8),
                                         (StopRequested("the STOP file asks the run to stop"), 0),
                                         (RuntimeError("an error of the kit's own"), 8)])
def test_the_end_runs_whatever_the_import_raised(monkeypatch, luts, capsys, raised, code):
    """MEDIUM 4 and 5(d): no answer at all (a LinkError), a STOP, or any other error after the link opened: the end runs
    as ever, the screen looked at, the download at the end, the start file uploaded where anything differs, the restore
    checked, the jsonl line written, and the exit status the kit's (8, 0 for a STOP, 8), never 1."""
    cam = Camera(imports=raised, drift=(SETS_BACK,))
    assert tool(monkeypatch, luts, cam) == code
    tag = "after" if isinstance(raised, StopRequested) else "after-lut"
    assert cam.sent[-5:] == ["look end-check", f"download {tag}", "upload 00001_start.DAT", "close", "verify expected=[]"]
    assert jsonl_lines()[-1]["exit"] == code


def test_a_restore_that_does_not_check_out_exits_unrestored(monkeypatch, luts, capsys):
    """No reconnection after the upload, or the download at the end refused every time: exit 4, saying how the start
    file goes back."""
    from exit_status import EXIT_UNRESTORED
    assert tool(monkeypatch, luts, Camera(restored=None)) == EXIT_UNRESTORED
    assert "did not answer after its restart" in capsys.readouterr().out
    cam = Camera(after_refused=True)
    assert tool(monkeypatch, luts, cam) == EXIT_UNRESTORED
    assert "kit/tools/upload_check.py" in capsys.readouterr().out
    assert not [s for s in cam.sent if s.startswith("upload")]


def test_the_end_holds_over_a_screen_that_is_not_the_shooting_screen(monkeypatch, luts, capsys):
    """MEDIUM 5(c): before the download at the end the camera's own picture is looked at; where it does not read as the
    shooting screen nothing is downloaded or uploaded, and the run holds for the owner as runner.end_session does
    (hold_for_owner: RESTORE_BY_HAND, exit 5), the jsonl line written."""
    for screen_seen in ("dialog", "menu", None):
        cam = Camera(screen=screen_seen)
        with pytest.raises(SystemExit) as e:
            tool(monkeypatch, luts, cam)
        assert e.value.code == 5
        assert not [s for s in cam.sent if s.startswith(("download after", "upload", "verify"))]
        assert any(s.startswith("hold: ") for s in cam.sent) and marker() is not None
        assert jsonl_lines()[-1]["exit"] == 5


def test_the_camera_in_playback_is_held_by_session_ended(monkeypatch, luts, capsys):
    """MEDIUM 5(a): the download at the end is camkit.session.ended's, which asks the camera's word on Playback first:
    there no download or upload is asked, RESTORE_BY_HAND is written, exit 5."""
    cam = Camera(playback=True)
    with pytest.raises(SystemExit) as e:
        tool(monkeypatch, luts, cam)
    assert e.value.code == 5 and marker() is not None
    assert not [s for s in cam.sent if s.startswith(("download after", "upload"))]
    assert "the camera says it is in Playback" in capsys.readouterr().out


def test_the_screen_check_keeps_the_camera_s_picture_and_reads_its_kind(monkeypatch, tmp_path):
    """screen_kind: the OSD eyes' grab, kept under its tag, read by camkit.screen, the playback view told apart by the
    camera's word (session.kind_seen); a picture that cannot be had is None."""
    from types import SimpleNamespace

    import numpy as np

    import lut_import as T
    from camkit import screen
    grabs = []
    frame = SimpleNamespace(image=np.full((10, 10, 3), 200, "uint8"))

    class Eyes:
        def grab(self, tag):
            grabs.append(tag)
            return frame
    monkeypatch.setattr(screen, "read", lambda f: SimpleNamespace(kind="shooting"))
    link = SimpleNamespace(in_playback=lambda: False)
    assert T.screen_kind(link, Eyes()) == "shooting" and grabs == ["end-check"]
    assert T.screen_kind(SimpleNamespace(in_playback=lambda: True), Eyes()) == "playback"

    class Blind:
        def grab(self, tag):
            raise RuntimeError("no OSD image")
    assert T.screen_kind(link, Blind()) is None


def test_the_lock_after_the_start_download_is_waited_out(monkeypatch, luts):
    """MEDIUM 5(b): the menu's lock after the start download is waited out before the enable status is read."""
    cam = Camera(status=0)
    tool(monkeypatch, luts, cam)
    assert cam.sent[1:4] == ["download start", "lock", "get BaseLookImportOperationEnableStatus"]


def test_the_owner_s_word_travels_with_the_run(monkeypatch, luts, capsys):
    """MINE 1: without --allow "Manage User LUTs", or with any other allowance beside it, the tool stops before anything
    connects, as a prover does without its row's allowance."""
    for allow in ([], ["--allow", "Camera Set. Memory"], ["--allow", "Manage User LUTs", "--allow", "Format"]):
        cam = Camera()
        with pytest.raises(SystemExit) as e:
            tool(monkeypatch, luts, cam, allow=allow)
        assert "Manage User LUTs" in str(e.value.code) and cam.sent == []


def test_nothing_is_sent_for_a_file_or_place_the_kit_does_not_import(monkeypatch, luts, capsys, tmp_path):
    """A file outside the clone's LUT folder: refused before any link opens, exit 1; the tool takes no other place than
    16 (no --place: argparse stops it, exit 2); a camera that refuses the start download: said, nothing imported,
    exit 1."""
    from camkit import paths
    cam = Camera()
    outside = made(tmp_path / "elsewhere", NAME)
    T = stand_in(monkeypatch, cam)
    frame = str(look(paths.run_root()))
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(outside), *ALLOW, "--seen-empty", frame])
    assert T.main() == 1
    assert capsys.readouterr().out.count("nothing was sent") == 1
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(luts[3]), *ALLOW, "--seen-empty", frame, "--place", "15"])
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
    import camkit
    from camkit import paths
    monkeypatch.setattr(camkit, "RUNS", paths.runs_top())
    monkeypatch.setattr(T, "Link", linked)
    monkeypatch.setattr(T, "verify_restore", functools.partial(session.verify_restore, link_class=linked, clock=Clock))
    monkeypatch.setattr(T, "wait_lock", lambda since, eyes=None, **kw: None)
    # the stand-in camlink writes no picture for osd: the screen it shows stood in as the shooting screen
    monkeypatch.setattr(T, "screen_kind", lambda link, eyes, tag="end-check": "shooting")
    monkeypatch.setattr(sys, "argv", ["lut_import.py", str(lut), *ALLOW, "--seen-empty", str(look(paths.run_root()))])
    monkeypatch.setitem(T.USER_LUT, "ILCE-1M2", (key(STAYS),))     # as once the first run has named it
    assert T.main() == 0
    verbs = [raw.split(b" ", 2)[1].strip() for raw in received(log) if raw.startswith(b"@")]
    assert set(verbs) <= {b"download", b"get", b"props", b"importlut", b"upload"}
    assert [v for v in verbs if v in (b"download", b"importlut", b"upload")] == \
        [b"download", b"importlut", b"download", b"upload", b"download"]
    assert verbs[1] == b"get" and verbs.count(b"importlut") == 1 and verbs.count(b"upload") == 1
    out = capsys.readouterr().out
    assert f"names as holding a user LUT: {key(STAYS)}" in out and "after the restore: 0 records differ" in out


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
    assert tool(monkeypatch, luts, Camera(imports=LutNotImported("not confirmed", reply))) == 5
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


# ---------------------------------------------------------------- the look that says place 16 is empty (--seen-empty)

def seen(monkeypatch, frame, root, now=None, last=None):
    """lut_import.seen_empty on `frame`: its result, or the refusal's words."""
    import lut_import as T
    try:
        return T.seen_empty(frame, root, time.time() if now is None else now, last)
    except T.NotSeenEmpty as e:
        return str(e)


def test_a_look_at_an_empty_row_16_says_place_16_is_empty(monkeypatch, tmp_path):
    """The camera's own Import/Edit table, seen: the frame under the camera's runs, its look's time and path from its
    run's own records, the kit's OCR reading the title and User16's own row as "(No Import)". The result names the frame
    from the camera's run root, its SHA-256, the row as read and when the look was."""
    root = tmp_path / "TEST-CAM_fw9.99"
    now = time.time()
    frame = look(root, now=now)
    got = seen(monkeypatch, frame, root, now)
    assert got["frame"] == "kit2_lut_look/shots/00034_down.png" and got["row"] == "User16: (No Import)"
    assert got["sha256"] == hashlib.sha256(frame.read_bytes()).hexdigest() and abs(got["look_t"] - (now - 600)) < 1
    assert seen(monkeypatch, "kit2_lut_look/shots/00034_down.png", root, now)["row"] == "User16: (No Import)"
    # OCR's spacing and a dropped colon are the same row
    for n, row in enumerate(("User 16 : ( No Import )", "User16 (No Import)", "user16: (no import)")):
        f = look(root, rows=["User15: (No Import)", row], now=now, name=f"0004{n}_down.png")
        assert seen(monkeypatch, f, root, now)["row"] == row


@pytest.mark.parametrize("rows,said", [
    ([f"User{n}: (No Import)" for n in range(1, 7)], "User16's row is not on this frame"),        # User1 is not 16
    (["User1: (No Import)", "User16: 1_test_look_to_709 S-Gamut3.Cine/S-Log3 0.0"], "User16 reads"),
    (["User16: (No lmport)x"], "User16 reads"),
    (["Userl6: (No Import)"], "User16's row is not on this frame"),
    (["User160: (No Import)"], "User16's row is not on this frame"),
])
def test_a_row_16_not_read_as_empty_refuses(monkeypatch, tmp_path, rows, said):
    root = tmp_path / "TEST-CAM_fw9.99"
    got = seen(monkeypatch, look(root, rows=rows), root)
    assert isinstance(got, str) and said in got


def test_a_frame_that_is_not_such_a_look_refuses(monkeypatch, tmp_path):
    """Refused, saying why: a frame outside the camera's runs, a link, not in a run's shots/, not a picture, not there;
    no title "Import/Edit"; a look whose run does not record when it was taken or that it was Manage User LUTs >
    Import/Edit; one whose run kept no text for it."""
    root = tmp_path / "TEST-CAM_fw9.99"
    now = time.time()
    good = look(root, now=now)
    elsewhere = look(tmp_path / "OTHER-CAM_fw1.00", now=now)
    assert "not under this camera's runs" in seen(monkeypatch, elsewhere, root, now)
    (good.parent / "link.png").symlink_to(good)
    assert "a link" in seen(monkeypatch, good.parent / "link.png", root, now)
    stray = root / "kit2_lut_look" / "00034_down.png"
    stray.write_bytes(good.read_bytes())
    assert "a run's shots/" in seen(monkeypatch, stray, root, now)
    assert "not there" in seen(monkeypatch, root / "kit2_lut_look" / "shots" / "00099_down.png", root, now)
    text = good.with_name("00035_down.txt")
    text.write_text("x", encoding="utf-8")
    assert "not a .png" in seen(monkeypatch, text, root, now)
    assert "Import/Edit" in seen(monkeypatch, look(root, title=None, now=now, name="00036_down.png"), root, now)
    assert "Manage User LUTs > Import/Edit" in seen(monkeypatch, look(root, path=["Select LUT"], run="kit2_other",
                                                                      now=now), root, now)
    bare = root / "kit2_bare" / "shots" / "00001_down.png"
    bare.parent.mkdir(parents=True)
    bare.write_bytes(b"\x89PNG")
    assert "does not say when" in seen(monkeypatch, bare, root, now)
    assert "kept no text" in seen(monkeypatch, look(root, now=now, name="00037_down.png", text=""), root, now)


def test_a_look_too_old_another_day_or_before_the_last_import_refuses(monkeypatch, tmp_path):
    """The look must be no more than an hour before the import, on the same day, not ahead of the clock, and after the
    last import the SDK was asked for (lut_import.jsonl's asked_at), whatever its answer."""
    import datetime
    root = tmp_path / "TEST-CAM_fw9.99"
    now = time.time()
    assert "more than an hour" in seen(monkeypatch, look(root, ago=3700, now=now, name="00001_down.png"), root, now)
    assert "ahead of" in seen(monkeypatch, look(root, ago=-120, now=now, name="00002_down.png"), root, now)
    midnight = datetime.datetime.combine(datetime.date.today(), datetime.time(0, 10)).timestamp()
    assert "another day" in seen(monkeypatch, look(root, ago=1200, now=midnight, name="00003_down.png"), root, midnight)
    frame = look(root, ago=600, now=now, name="00004_down.png")
    assert "after the last import" in seen(monkeypatch, frame, root, now, last=now - 300)
    assert seen(monkeypatch, frame, root, now, last=now - 900)["row"] == "User16: (No Import)"


def test_the_last_import_asked_for_is_read_from_every_run(tmp_path):
    """lut_import.jsonl in any run of the camera: the latest import the SDK was asked for (asked_at; a line from before
    the field, its t), confirmed or not; a run that asked nothing counts for none."""
    import datetime

    import lut_import as T
    root = tmp_path / "TEST-CAM_fw9.99"
    for run, lines in (("kit2_lut", [{"t": "2026-11-19T15:00:00", "called": False},
                                     {"t": "2026-11-19T16:00:00", "called": True, "asked_at": 1795130000.0}]),
                       ("kit2_lut2", [{"t": "2026-11-19T17:00:00", "confirmed": True, "result": L.LUT_OK}])):
        (root / run).mkdir(parents=True)
        (root / run / "lut_import.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    assert T.last_import_asked(root) == max(datetime.datetime(2026, 11, 19, 17).timestamp(), 1795130000.0)
    assert T.last_import_asked(tmp_path / "none") is None


def a1_look() -> Path:
    from camkit import paths
    return paths.a1ii_root() / "kit2_fin_lut_table"


@pytest.mark.skipif(not (a1_look() / "shots" / "00034_down.png").exists(), reason="the a1 II's runs are not here")
def test_the_camera_s_own_table_reads_empty_and_a_frame_without_row_16_refuses():
    """The look made on the a1 II (2026-11-19, Movie): the kit's own OCR reads User16's row on 00034_down.png as empty,
    and 00019_right.png, which shows User1 to User6, is refused."""
    import lut_import as T
    from camkit import paths
    root, d = paths.a1ii_root(), a1_look()
    looked = next(json.loads(x)["t"] for x in (d / "events.jsonl").read_text(encoding="utf-8").splitlines()
                  if json.loads(x).get("frame") == "00034_down.png")
    got = T.seen_empty(d / "shots" / "00034_down.png", root, looked + 120, None)
    assert got["row"].replace(" ", "") == "User16:(NoImport)" and got["frame"] == "kit2_fin_lut_table/shots/00034_down.png"
    with pytest.raises(T.NotSeenEmpty, match="User16's row is not on this frame"):
        T.seen_empty(d / "shots" / "00019_right.png", root, looked + 120, None)


def test_the_tool_needs_the_look_and_logs_it(monkeypatch, luts, capsys):
    """The tool takes --seen-empty: without it argparse stops it; a look refused stops it before anything connects,
    with how to make one; a good one goes into events.jsonl and lut_import.jsonl (frame, SHA-256, row), and after a
    confirmed import the next steps include the same look again, so the row's new reading is on record."""
    from camkit import paths
    cam = Camera()
    with pytest.raises(SystemExit) as e:
        tool(monkeypatch, luts, cam, seen=None)
    assert e.value.code == 2 and cam.sent == []
    old = look(paths.run_root(), ago=7200, name="00001_down.png")
    assert tool(monkeypatch, luts, cam, seen=old) == 1 and cam.sent == []
    out = capsys.readouterr().out
    assert "nothing was sent" in out and "more than an hour" in out
    assert "kit/drive.py" in out and "--path 'Manage User LUTs' --path Import/Edit" in out
    assert tool(monkeypatch, luts, Camera()) == 0
    out = capsys.readouterr().out
    line = jsonl_lines()[-1]
    assert line["seen_empty"]["row"] == "User16: (No Import)" and line["seen_empty"]["frame"].endswith("00034_down.png")
    assert isinstance(line["asked_at"], float) and isinstance(line["imported_at"], float)
    logged = [x for x in events(Run("kit2_lut")) if x["kind"] == "lut_seen_empty"]
    assert logged and logged[-1]["row"] == "User16: (No Import)" and len(logged[-1]["sha256"]) == 64
    after = out.split("ImportLUTFile_Result_OK", 1)[1]
    assert "kit/drive.py" in after and "Import/Edit" in after and "--press down" in after and "CAMSET_EYES=osd" in after

