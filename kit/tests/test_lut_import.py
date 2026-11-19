"""A user LUT into the camera (the owner's approval of 2026-11-19): camlink's importlut (Sony's ImportLUTFile), its
checks made in C++ before the SDK is asked (kit/common/lut_file.h, compiled and run here with no SDK), and its command
line. No camera."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from camkit import ROOT


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
