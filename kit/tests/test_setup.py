"""Offline tests of kit/setup.py, the kit's setup command: synthetic SDK zips in temporary folders, no network, no
builds (every tool it would run is replaced; the builds' stand-in writes a program only when its sources changed).

The script is loaded from its path under the name camset_setup, so it never meets another module called setup.
"""
import ast
import importlib.util
import io
import os
import platform
import stat
import sys
import time
import zipfile
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("camset_setup", KIT / "setup.py")
kitsetup = importlib.util.module_from_spec(_spec)
sys.modules["camset_setup"] = kitsetup              # dataclasses look their module up there
_spec.loader.exec_module(kitsetup)


@pytest.fixture(autouse=True)
def own_temp(tmp_path, monkeypatch):
    """No test here empties the computer's real temporary folder for the setup's tests (tests_folder): when the setup
    itself runs these tests, that folder is the one they are running in, and a test that reached step_tests emptied
    it under every test after it (2026-11-12: 113 errors, FileNotFoundError, in a run of `kit/setup.py`)."""
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))


def test_no_test_here_reaches_the_real_temporary_folder(tmp_path):
    assert Path(kitsetup.tests_folder()[0]).parent == tmp_path / "temp"


def elf(cpu: int) -> bytes:
    return b"\x7fELF" + bytes(14) + cpu.to_bytes(2, "little") + bytes(44)


LIBS = {"Mac": [("libCr_Core.dylib", b"\xcf\xfa\xed\xfe" + bytes(60))],
        "Linux64PC": [("libCr_Core.so", elf(62))],
        "Linux64ARMv8": [("libCr_Core.so", elf(183))],
        "Win64": [("Cr_Core.dll", b"MZ" + bytes(62)), ("Cr_Core.lib", b"!<arch>\n")]}


def zbytes(entries: dict, links: dict | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
        for name, target in (links or {}).items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, target)
    return buf.getvalue()


def simplecli(os_tag: str, extra: dict | None = None, links: dict | None = None) -> bytes:
    files = {"CMakeLists.txt": "# Sony's sample", "app/CRSDK/CameraRemote_SDK.h": "// header",
             "app/CrDebugString.cpp": "// source", "external/crsdk/CrAdapter/adapter.bin": b"\0"}
    files.update({f"external/crsdk/{n}": d for n, d in LIBS[os_tag]})
    files.update(extra or {})
    return zbytes(files, links)


def sdk_zip(folder: Path, os_tag: str = "Mac", ver: str = "2.02.00", date: str = "20260610a", name: str | None = None,
            inner: bytes | None = None, outer_extra: dict | None = None, api: bool = True) -> Path:
    files = {"Camera_Remote_SDK_Readme.pdf": b"%PDF", "SimpleCli.zip": inner or simplecli(os_tag),
             "RemoteCli.zip": zbytes({"x": "y"})}
    if api:
        files[f"CrSDK_API_Reference_v{ver}.zip"] = zbytes({"html/index.html": "<html></html>"})
    if os_tag == "Win64":
        files["Driver.zip"] = zbytes({"srcameradriver.inf": "; inf", "amd64/libusbK.dll": b"\0"})
    files.update(outer_extra or {})
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name or f"CrSDK_v{ver}_{date}_{os_tag}.zip")
    path.write_bytes(zbytes(files))
    return path


def env_for(root: Path, system: str = "Darwin", machine: str = "arm64", **kw):
    return kitsetup.Env(root=root, system=system, machine=machine, **kw)


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if not p.is_dir()}


@pytest.fixture
def no_tools(monkeypatch):
    """Every tool found, and every tool run answers 0 with a version line; the calls are recorded."""
    calls = []

    def run(cmd, cwd=None):
        calls.append([str(c) for c in cmd])
        return 0, "cmake version 3.31.6\n"
    monkeypatch.setattr(kitsetup, "run", run)
    monkeypatch.setattr(kitsetup, "which", lambda name: f"/usr/bin/{name}")
    return calls


class Builder:
    """cmake, cargo and swiftc as an incremental build behaves: every call recorded; a build writes its program only
    when its sources changed (its folder in `changed`) or it starts clean."""
    PROGRAMS = {"kit/link": "camlink", "kit/probe": "camset_probe"}

    def __init__(self):
        self.calls, self.changed = [], set()

    @staticmethod
    def write(program: Path) -> None:
        """The program written anew, with a time later than the one it had: two writes within one tick of the clock
        (Windows' is coarse) would leave the time as it was, and the setup tells a build by the program's time."""
        before = program.stat().st_mtime_ns if program.exists() else None
        program.write_bytes(b"new")
        if before is not None and program.stat().st_mtime_ns <= before:
            os.utime(program, ns=(before + 1_000_000_000, before + 1_000_000_000))

    def __call__(self, cmd, cwd=None):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        if cmd[:2] == ["cmake", "--build"]:
            folder = cmd[2][:-len("/build")]
            if folder in self.changed or "--clean-first" in cmd:
                self.write(Path(cwd) / cmd[2] / self.PROGRAMS[folder])
        elif cmd[:2] == ["cargo", "clean"]:
            self.changed.add("editor")
        elif cmd[:3] == ["cargo", "build", "--release"] and "editor" in self.changed:
            self.write(Path(cwd) / "target" / "release" / "camset_editor")
        elif cmd[0] == "swiftc":
            self.write(Path(cwd) / cmd[-1])
        return 0, ""

    def builds(self) -> list:
        """The calls that configure, build or clean."""
        return [c for c in self.calls if c[:2] in (["cmake", "-S"], ["cmake", "--build"], ["cargo", "build"],
                                                   ["cargo", "clean"]) or c[0] == "swiftc"]


@pytest.fixture
def builder(monkeypatch):
    b = Builder()
    monkeypatch.setattr(kitsetup, "run", b)
    return b


def ready(root: Path, **kw):
    """A Mac with the SDK unpacked and every tool in place."""
    env = env_for(root, **kw)
    env.sdk_ok = True
    env.tools.update(cmake=True, cxx=True, cargo=True)
    return env


def program(path: Path, lib: bool = True, age: float = 3600) -> Path:
    """A program built `age` seconds ago, with the SDK's library beside it as its build copies it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"old")
    if lib:
        (path.parent / "libCr_Core.dylib").write_bytes(b"")
    old = time.time() - age
    os.utime(path, (old, old))
    return path


# ---------------------------------------------------------------- the zip

def test_machine_os_names_sonys_downloads():
    assert kitsetup.machine_os("Darwin", "arm64") == "Mac"
    assert kitsetup.machine_os("Darwin", "x86_64") == "Mac"
    assert kitsetup.machine_os("Linux", "x86_64") == "Linux64PC"
    assert kitsetup.machine_os("Linux", "aarch64") == "Linux64ARMv8"
    assert kitsetup.machine_os("Windows", "AMD64") == "Win64"
    assert kitsetup.machine_os("Linux", "riscv64") is None


def test_finds_the_newest_zip_for_this_machine_and_names_the_others(tmp_path, capsys):
    sdk = tmp_path / "kit" / "sdk"
    sdk_zip(sdk, "Mac", "2.01.00", "20250101a")
    want = sdk_zip(sdk, "Mac", "2.02.00", "20260610a")
    sdk_zip(sdk, "Win64", "2.03.00", "20270101a")
    env = env_for(tmp_path)
    z, code = kitsetup.step_sdk(env, None)
    assert code == 0 and z.path == want and z.os == "Mac" and z.version == "2.02.00"
    out = capsys.readouterr().out
    assert "is for Win64, not this machine (Mac)" in out and "OK   SDK zip: kit/sdk/CrSDK_v2.02.00" in out
    z, code = kitsetup.step_sdk(env_for(tmp_path, "Windows", "AMD64"), None)
    assert code == 0 and z.os == "Win64" and z.version == "2.03.00"


def test_a_zip_for_another_os_is_refused(tmp_path, capsys):
    sdk = tmp_path / "kit" / "sdk"
    win = sdk_zip(sdk, "Win64")
    z, code = kitsetup.step_sdk(env_for(tmp_path), None)
    out = capsys.readouterr().out
    assert z is None and code == 2
    assert "is for Win64, not this machine (Mac)" in out and "no SDK zip for Mac in kit/sdk/" in out
    assert kitsetup.SONY_PAGE in out and "CrSDK_v<version>_<date>_Mac.zip" in out
    z, code = kitsetup.step_sdk(env_for(tmp_path), str(win))         # given by name
    assert z is None and code == 2 and "is Sony's SDK for Win64; this machine needs the Mac" in capsys.readouterr().out
    # the ELF header tells the two Linux downloads apart, whatever the file is called
    arm = sdk_zip(tmp_path / "dl", "Linux64ARMv8", name="CrSDK_v2.02.00_20260610a_Linux64PC.zip")
    assert kitsetup.inspect_zip(arm).os == "Linux64ARMv8"
    z, code = kitsetup.step_sdk(env_for(tmp_path, "Linux", "x86_64"), str(arm))
    assert code == 2 and "for Linux64ARMv8" in capsys.readouterr().out


def test_the_zip_is_known_by_its_contents(tmp_path):
    good = kitsetup.inspect_zip(sdk_zip(tmp_path, "Linux64PC", name="renamed.zip"))
    assert not good.problem and good.os == "Linux64PC" and good.version == "2.02.00"
    no_api = kitsetup.inspect_zip(sdk_zip(tmp_path / "a", "Mac", api=False))
    assert "not Sony's Camera Remote SDK download" in no_api.problem
    not_zip = tmp_path / "CrSDK_v2.02.00_20260610a_Mac.zip"
    not_zip.write_bytes(b"not a zip")
    assert "not a readable zip" in kitsetup.inspect_zip(not_zip).problem
    no_lib = kitsetup.inspect_zip(sdk_zip(tmp_path / "b", "Mac", inner=zbytes({"app/x.h": ""})))
    assert "no Cr_Core library" in no_lib.problem


def test_no_zip_but_an_unpacked_sdk_is_used(tmp_path):
    (tmp_path / "kit" / "sdk" / "SimpleCli" / "external" / "crsdk").mkdir(parents=True)
    z, code = kitsetup.step_sdk(env_for(tmp_path), None)
    assert z is None and code == 0


# ---------------------------------------------------------------- unpacking

def test_zip_slip_is_refused_before_anything_is_written(tmp_path):
    sdk = tmp_path / "kit" / "sdk"
    sdk.mkdir(parents=True)
    for bad in ("../evil.txt", "/abs/evil.txt", "C:/evil.txt", "a/../../evil.txt", "a\\..\\..\\evil.txt"):
        assert kitsetup.unsafe(bad)
        with zipfile.ZipFile(io.BytesIO(zbytes({"fine.txt": "ok", bad: "x"}))) as z, pytest.raises(kitsetup.Refused):
            kitsetup.extract(z, sdk / "SimpleCli", sdk)
    assert not kitsetup.unsafe("app/CRSDK/CrTypes.h") and not kitsetup.unsafe("html/a..b.html")
    assert not (sdk / "SimpleCli").exists() and not (tmp_path / "kit" / "evil.txt").exists()
    # a link that points out of its folder
    with zipfile.ZipFile(io.BytesIO(zbytes({"a.txt": "ok"}, links={"lib.so": "../../../etc/passwd"}))) as z, pytest.raises(kitsetup.Refused):
        kitsetup.extract(z, sdk / "SimpleCli", sdk)
    # an outer zip with such an entry is not taken for the SDK at all
    bad = sdk_zip(tmp_path / "dl", "Mac", outer_extra={"../escape.txt": "x"})
    assert "would land outside kit/sdk/" in kitsetup.inspect_zip(bad).problem
    # and one inside SimpleCli.zip fails the unpack, writing none of it
    sneaky = sdk_zip(sdk, "Mac", inner=simplecli("Mac", extra={"../../escape.txt": "x"}))
    env = env_for(tmp_path)
    z, code = kitsetup.step_sdk(env, None)
    assert code == 0 and z.path == sneaky
    kitsetup.step_unpack(env, z)
    assert env.rows[-1].state == "FAIL" and "refused" in env.rows[-1].what
    assert not (sdk / "SimpleCli").exists() and not (tmp_path / "escape.txt").exists()


def test_a_link_to_a_neighbour_is_kept(tmp_path):
    if sys.platform == "win32":
        pytest.skip("links are written as files on Windows")
    dest = tmp_path / "out"
    with zipfile.ZipFile(io.BytesIO(zbytes({"libx.so.2.1": "lib"}, links={"libx.so.2": "libx.so.2.1"}))) as z:
        kitsetup.extract(z, dest, tmp_path)
        assert (dest / "libx.so.2").is_symlink() and (dest / "libx.so.2").read_text() == "lib"
        assert kitsetup.extract(z, dest, tmp_path, skip_same=True) == ([], 2)     # the same link is kept


def test_unpacking_twice_keeps_what_is_there(tmp_path, capsys):
    sdk = tmp_path / "kit" / "sdk"
    sdk_zip(sdk, "Win64")
    env = env_for(tmp_path, "Windows", "AMD64")
    z, _ = kitsetup.step_sdk(env, None)
    assert kitsetup.step_unpack(env, z) is True                    # SimpleCli/ unpacked afresh: build again
    assert env.sdk_ok and env.rows[-1].state == "OK"
    for p in ("SimpleCli/external/crsdk/Cr_Core.dll", "SimpleCli/app/CRSDK/CameraRemote_SDK.h",
              "CrSDK_API_Reference_v2.02.00/html/index.html", "Driver/srcameradriver.inf", "RemoteCli.zip"):
        assert (sdk / p).exists(), p
    assert not (sdk / "RemoteCli").exists()                         # not used, not unpacked
    before = snapshot(tmp_path)
    env2 = env_for(tmp_path, "Windows", "AMD64")
    z, _ = kitsetup.step_sdk(env2, None)
    assert kitsetup.step_unpack(env2, z) is False
    assert snapshot(tmp_path) == before
    assert "is already unpacked in kit/sdk/" in env2.rows[-1].what
    env3 = env_for(tmp_path, "Windows", "AMD64", force=True)       # --force writes it all again
    z, _ = kitsetup.step_sdk(env3, None)
    assert kitsetup.step_unpack(env3, z) is True
    assert "unpacked CrSDK_API_Reference_v2.02.00/, Driver/, SimpleCli/ from CrSDK_v2.02.00" in env3.rows[-1].what


def test_unpacked_rests_on_what_the_kit_uses(tmp_path):
    sdk = tmp_path / "kit" / "sdk"
    sdk_zip(sdk, "Linux64PC")
    env = env_for(tmp_path, "Linux", "x86_64")
    z, _ = kitsetup.step_sdk(env, None)
    kitsetup.step_unpack(env, z)
    # kit/sdk/ made again by hand with only what the kit uses: the zip's documents and inner zips, and SimpleCli's
    # own CMake file, gone; a libxml2.so.2 built beside the libraries (step 4), which is not in the zip
    for p in ("Camera_Remote_SDK_Readme.pdf", "SimpleCli.zip", "RemoteCli.zip", "CrSDK_API_Reference_v2.02.00.zip",
              "SimpleCli/CMakeLists.txt"):
        (sdk / p).unlink()
    (sdk / "SimpleCli/external/crsdk/libxml2.so.2").write_bytes(b"built here")
    header = sdk / "SimpleCli/app/CRSDK/CameraRemote_SDK.h"
    before, files = header.stat().st_mtime_ns, snapshot(tmp_path)
    check = env_for(tmp_path, "Linux", "x86_64", check=True)
    z, _ = kitsetup.step_sdk(check, None)
    assert kitsetup.step_unpack(check, z) is False and not check.sdk_pending
    assert check.rows[-1].state == "OK" and "is already unpacked in kit/sdk/" in check.rows[-1].what
    assert "a run also writes 5 other files of the zip, which the kit does not use" in check.rows[-1].what
    assert snapshot(tmp_path) == files
    run = env_for(tmp_path, "Linux", "x86_64")                       # a run writes the rest, and nothing else
    z, _ = kitsetup.step_sdk(run, None)
    assert kitsetup.step_unpack(run, z) is False                    # no headers or libraries changed: no clean build
    assert run.rows[-1].state == "OK" and "; 5 other files of the zip written" in run.rows[-1].what
    assert (sdk / "RemoteCli.zip").is_file() and (sdk / "SimpleCli/CMakeLists.txt").is_file()
    assert header.stat().st_mtime_ns == before
    assert (sdk / "SimpleCli/external/crsdk/libxml2.so.2").read_bytes() == b"built here"
    # a header that differs from the zip's is one the kit uses: a run would unpack SimpleCli.zip again
    header.write_text("// changed by hand")
    check = env_for(tmp_path, "Linux", "x86_64", check=True)
    z, _ = kitsetup.step_sdk(check, None)
    kitsetup.step_unpack(check, z)
    assert check.rows[-1].state == "DO" and check.sdk_pending
    assert "would unpack SimpleCli.zip into SimpleCli/:" in check.rows[-1].what


def test_a_newer_sdk_replaces_simplecli(tmp_path):
    sdk = tmp_path / "kit" / "sdk"
    old = sdk_zip(sdk, "Mac", "2.02.00")
    env = env_for(tmp_path)
    kitsetup.step_unpack(env, kitsetup.inspect_zip(old))
    new = sdk_zip(sdk, "Mac", "2.03.00", "20270101a",
                  inner=simplecli("Mac", extra={"app/CRSDK/CameraRemote_SDK.h": "// newer header"}))
    env = env_for(tmp_path)
    z, _ = kitsetup.step_sdk(env, None)
    assert z.path == new
    assert kitsetup.step_unpack(env, z) is True
    assert (sdk / "SimpleCli/app/CRSDK/CameraRemote_SDK.h").read_text() == "// newer header"
    assert (sdk / "CrSDK_API_Reference_v2.03.00").is_dir()


def test_an_unpacked_sdk_for_another_os_is_named(tmp_path):
    sdk = tmp_path / "kit" / "sdk"
    sdk_zip(sdk, "Linux64PC")
    env = env_for(tmp_path, "Linux", "x86_64")
    z, _ = kitsetup.step_sdk(env, None)
    kitsetup.step_unpack(env, z)
    env = env_for(tmp_path, "Linux", "aarch64")
    for p in sdk.glob("*.zip"):
        p.unlink()
    z, code = kitsetup.step_sdk(env, None)
    kitsetup.step_unpack(env, z)
    assert not env.sdk_ok and "holds Sony's SDK for Linux64PC, not Linux64ARMv8" in env.rows[-1].what


# ---------------------------------------------------------------- libxml2.so.2 on Linux

LDCONFIG_OLD = """1234 libs found in cache `/etc/ld.so.cache'
\tlibxml2.so.2 (libc6,x86-64) => /lib/x86_64-linux-gnu/libxml2.so.2
\tlibxml2.so (libc6,x86-64) => /lib/x86_64-linux-gnu/libxml2.so
"""
LDCONFIG_NEW = """1234 libs found in cache `/etc/ld.so.cache'
\tlibxml2.so.16 (libc6,x86-64) => /lib/x86_64-linux-gnu/libxml2.so.16
"""
LDCONFIG_I386 = "\tlibxml2.so.2 (libc6) => /lib/i386-linux-gnu/libxml2.so.2\n"
LDCONFIG_ARM = "\tlibxml2.so.2 (libc6,AArch64) => /lib/aarch64-linux-gnu/libxml2.so.2\n"


def test_libxml2_is_built_only_where_none_is_found(tmp_path):
    linux = env_for(tmp_path, "Linux", "x86_64")
    assert not kitsetup.libxml2_needed(linux, LDCONFIG_OLD)          # Ubuntu up to 24.04
    assert kitsetup.libxml2_needed(linux, LDCONFIG_NEW)              # Ubuntu 25.10 and later: only libxml2.so.16
    assert kitsetup.libxml2_needed(linux, LDCONFIG_I386)             # another CPU's copy does not count
    assert kitsetup.libxml2_needed(linux, None)                      # no ldconfig to ask
    assert not kitsetup.libxml2_needed(env_for(tmp_path, "Linux", "aarch64"), LDCONFIG_ARM)
    assert not kitsetup.libxml2_needed(env_for(tmp_path, "Darwin", "arm64"), None)
    linux.crsdk.mkdir(parents=True)
    (linux.crsdk / "libxml2.so.2").write_bytes(b"")                 # a copy beside the SDK's libraries
    assert not kitsetup.libxml2_needed(linux, LDCONFIG_NEW)


def test_libxml2_under_check_only_says_it_would_build(tmp_path, monkeypatch, no_tools):
    env = env_for(tmp_path, "Linux", "x86_64", check=True)
    env.crsdk.mkdir(parents=True)
    env.sdk_ok = True
    monkeypatch.setattr(kitsetup, "ldconfig", lambda: LDCONFIG_NEW)
    monkeypatch.setattr(kitsetup, "download", lambda *a: pytest.fail("--check downloads nothing"))
    kitsetup.step_libxml2(env)
    assert env.rows[-1].state == "DO" and "would build libxml2 2.13.9" in env.rows[-1].what
    assert not (env.sdk / ".build").exists() and no_tools == []


def test_libxml2_with_the_wrong_hash_is_not_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(kitsetup.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(b"not libxml2"))
    dest = tmp_path / "libxml2-2.13.9.tar.xz"
    problem = kitsetup.download(kitsetup.LIBXML2_URL, dest, kitsetup.LIBXML2_SHA256)
    assert "expected " + kitsetup.LIBXML2_SHA256 in problem and list(tmp_path.iterdir()) == []


def test_a_built_libxml2_is_copied_with_its_links(tmp_path, monkeypatch, no_tools):
    if sys.platform == "win32":
        pytest.skip("Linux only")
    env = env_for(tmp_path, "Linux", "x86_64")
    env.crsdk.mkdir(parents=True)
    env.sdk_ok = True
    lib = env.sdk / ".build" / "libxml2-2.13" / "lib"
    lib.mkdir(parents=True)
    (lib / "libxml2.so.2.13.9").write_bytes(b"\x7fELF")
    (lib / "libxml2.so.2").symlink_to("libxml2.so.2.13.9")
    (lib / "libxml2.so").symlink_to("libxml2.so.2.13.9")
    monkeypatch.setattr(kitsetup, "ldconfig", lambda: LDCONFIG_NEW)
    kitsetup.step_libxml2(env)
    assert env.rows[-1].state == "OK" and "built libxml2 2.13.9" in env.rows[-1].what
    assert (env.crsdk / "libxml2.so.2").is_symlink() and (env.crsdk / "libxml2.so.2").read_bytes() == b"\x7fELF"
    assert not (env.crsdk / "libxml2.so").exists() and no_tools == []   # nothing built again


def test_libxml2_is_pinned():
    assert kitsetup.LIBXML2_URL.endswith("/libxml2-2.13.9.tar.xz")
    assert len(kitsetup.LIBXML2_SHA256) == 64 and int(kitsetup.LIBXML2_SHA256, 16)


# ---------------------------------------------------------------- .venv

def test_venv_is_made_with_a_python_the_packages_install_on(tmp_path, monkeypatch):
    env = env_for(tmp_path)
    newest = f"python{kitsetup.NEWEST_PY[0]}.{kitsetup.NEWEST_PY[1]}"
    monkeypatch.setattr(kitsetup, "which", lambda name: f"/opt/bin/{name}" if name == newest else None)
    assert kitsetup.venv_python(env, kitsetup.NEWEST_PY) == (sys.executable, "")
    exe, why = kitsetup.venv_python(env, (kitsetup.NEWEST_PY[0], kitsetup.NEWEST_PY[1] + 1))
    assert exe == f"/opt/bin/{newest}" and "no build for Python" in why
    monkeypatch.setattr(kitsetup, "which", lambda name: None)       # none older installed: the running one
    assert kitsetup.venv_python(env, (3, 99)) == (sys.executable, "")


# ---------------------------------------------------------------- the builds

def test_cmake_runs_even_when_the_program_is_there(tmp_path, builder):
    env = ready(tmp_path)
    program(tmp_path / "kit/link/build/camlink")
    program(tmp_path / "kit/probe/build/camset_probe")
    kitsetup.step_cmake(env, "link", "kit/link", "camlink", False)
    assert builder.calls == [["cmake", "-S", "kit/link", "-B", "kit/link/build"],
                             ["cmake", "--build", "kit/link/build", "--config", "Release"]]
    assert (env.rows[-1].state, env.rows[-1].what) == ("OK", "up to date (kit/link/build/camlink)")
    builder.changed.add("kit/probe")                                 # a pull changed kit/probe/camset_probe.cpp
    kitsetup.step_cmake(env, "probe", "kit/probe", "camset_probe", False)
    assert (env.rows[-1].state, env.rows[-1].what) == ("OK", "built (kit/probe/build/camset_probe)")
    assert (tmp_path / "kit/probe/build/camset_probe").read_bytes() == b"new"
    builder.calls.clear()                                            # --force, or SimpleCli/ unpacked afresh
    kitsetup.step_cmake(env, "link", "kit/link", "camlink", True)
    assert builder.calls[-1] == ["cmake", "--build", "kit/link/build", "--config", "Release", "--clean-first"]
    assert env.rows[-1].what == "built (kit/link/build/camlink)"


def test_a_program_without_the_sdk_beside_it_is_built_from_clean(tmp_path, builder):
    env = ready(tmp_path)
    program(tmp_path / "kit/link/build/camlink", lib=False)          # its build copies the libraries when it links
    kitsetup.step_cmake(env, "link", "kit/link", "camlink", False)
    assert builder.calls[-1][-1] == "--clean-first" and env.rows[-1].what == "built (kit/link/build/camlink)"


def test_cmake_without_its_tools_fails_and_names_them(tmp_path, builder):
    env = ready(tmp_path)
    env.tools["cmake"] = False
    program(tmp_path / "kit/link/build/camlink")
    kitsetup.step_cmake(env, "link", "kit/link", "camlink", False)
    assert env.rows[-1].state == "FAIL" and "it needs cmake" in env.rows[-1].what
    assert "kit/link/build/camlink is from an earlier build" in env.rows[-1].what and builder.calls == []


def test_the_editor_runs_cargo_even_when_it_is_built(tmp_path, builder):
    env = ready(tmp_path, editor=True)
    program(tmp_path / "editor/target/release/camset_editor", lib=False)
    kitsetup.step_editor(env, False)
    assert builder.calls == [["cargo", "build", "--release"]]
    assert (env.rows[-1].state, env.rows[-1].what) == ("OK", "up to date (editor/target/release/camset_editor)")
    builder.changed.add("editor")                                    # a pull changed editor/src/main.rs
    kitsetup.step_editor(env, False)
    assert env.rows[-1].what == "built (editor/target/release/camset_editor)"
    builder.calls.clear()
    builder.changed.clear()
    kitsetup.step_editor(env, True)                                  # --force: the editor's crate compiled again
    assert builder.calls == [["cargo", "clean", "-p", "camset-editor", "--release"], ["cargo", "build", "--release"]]
    assert env.rows[-1].what == "built (editor/target/release/camset_editor)"
    builder.calls.clear()
    plain = ready(tmp_path)                                          # not asked for: not built, and not called OK
    kitsetup.step_editor(plain, False)
    assert builder.calls == [] and plain.rows[-1].state == "--"
    assert "is from an earlier build: python3 kit/setup.py --editor rebuilds it if its sources changed" in plain.rows[-1].what


def test_the_ocr_helper_is_built_when_its_source_is_newer(tmp_path, builder):
    env = ready(tmp_path)
    src = tmp_path / "kit/ocr/ocr.swift"
    out = program(tmp_path / "kit/ocr/build/ocr", lib=False, age=60)
    src.write_text("// source")
    os.utime(src, (time.time() - 3600,) * 2)
    kitsetup.step_ocr(env, False)
    assert builder.calls == [] and env.rows[-1].state == "OK"
    assert env.rows[-1].what == "up to date (kit/ocr/build/ocr, newer than kit/ocr/ocr.swift)"
    # a pull changed ocr.swift: newer than the program (a minute old), yet seconds before the build to come, as a
    # file written in the very tick of the build can read as newer than what the build wrote (Windows' file times)
    os.utime(src, (time.time() - 5,) * 2)
    check = ready(tmp_path, check=True)
    kitsetup.step_ocr(check, False)
    assert builder.calls == [] and check.rows[-1].state == "DO"
    assert check.rows[-1].what == "would rebuild kit/ocr/build/ocr, older than kit/ocr/ocr.swift: python3 kit/setup.py"
    kitsetup.step_ocr(env, False)
    assert builder.calls == [["swiftc", "-O", "kit/ocr/ocr.swift", "-o", "kit/ocr/build/ocr"]]
    assert env.rows[-1].what == "built (kit/ocr/build/ocr), as kit/ocr/ocr.swift was newer" and out.read_bytes() == b"new"
    kitsetup.step_ocr(env, True)                                     # --force
    assert len(builder.calls) == 2 and env.rows[-1].what == "built (kit/ocr/build/ocr)"
    linux = ready(tmp_path, system="Linux", machine="x86_64")        # macOS only
    kitsetup.step_ocr(linux, True)
    assert linux.rows == [] and len(builder.calls) == 2


def test_check_builds_nothing_and_says_what_a_run_does(tmp_path, builder):
    env = ready(tmp_path, check=True, editor=True)
    for path in ("kit/link/build/camlink", "kit/probe/build/camset_probe", "editor/target/release/camset_editor"):
        program(tmp_path / path)
    (tmp_path / "kit/ocr").mkdir(parents=True)
    (tmp_path / "kit/ocr/ocr.swift").write_text("// source")
    program(tmp_path / "kit/ocr/build/ocr", lib=False, age=-60)
    kitsetup.step_cmake(env, "link", "kit/link", "camlink", False)
    kitsetup.step_cmake(env, "probe", "kit/probe", "camset_probe", False)
    kitsetup.step_ocr(env, False)
    kitsetup.step_editor(env, False)
    assert builder.calls == [] and [r.state for r in env.rows] == ["OK"] * 4
    assert env.rows[0].what == ("built (kit/link/build/camlink); a run rebuilds it if its sources changed "
                                "(cmake --build, incremental)")
    assert env.rows[3].what == ("built (editor/target/release/camset_editor); a run with --editor rebuilds it if its "
                                "sources changed (cargo build --release, incremental)")
    (tmp_path / "kit/probe/build/camset_probe").unlink()
    forced = ready(tmp_path, check=True, editor=True, force=True)
    kitsetup.step_cmake(forced, "probe", "kit/probe", "camset_probe", False)
    kitsetup.step_cmake(forced, "link", "kit/link", "camlink", True)
    kitsetup.step_editor(forced, True)
    assert builder.calls == [] and [r.state for r in forced.rows] == ["DO"] * 3
    assert forced.rows[0].what == "would build kit/probe/build/camset_probe: python3 kit/setup.py --force"
    assert forced.rows[1].what == "would rebuild kit/link/build/camlink from clean: python3 kit/setup.py --force"
    assert forced.rows[2].what == ("would rebuild editor/target/release/camset_editor from clean: "
                                   "python3 kit/setup.py --editor --force")


# ---------------------------------------------------------------- --check, the table, the exit status

def test_check_changes_nothing(tmp_path, capsys, no_tools):
    sdk_zip(tmp_path / "kit" / "sdk", "Linux64PC")
    (tmp_path / "kit" / "requirements.txt").write_text("pytest\n")
    before = snapshot(tmp_path)
    code = kitsetup.main(["--check"], env_for(tmp_path, "Linux", "x86_64"))
    out = capsys.readouterr().out
    assert snapshot(tmp_path) == before and sorted(p.name for p in tmp_path.iterdir()) == ["kit"]
    assert code == 0
    assert "would unpack" in out and "would make .venv" in out and "would build kit/link/build/camlink" in out
    assert "tests: not run with --check" in out
    assert not any("venv" in c or "pip" in c or "pytest" in c for call in no_tools for c in call)
    assert not any(c[:2] in (["cmake", "-S"], ["cmake", "--build"], ["cargo", "build"], ["cargo", "clean"])
                   or c[0] == "swiftc" for c in no_tools)


def test_no_zip_exits_2_and_says_where_to_get_it(tmp_path, capsys, no_tools):
    assert kitsetup.main(["--check"], env_for(tmp_path, "Windows", "AMD64")) == 2
    out = capsys.readouterr().out
    assert "CrSDK_v<version>_<date>_Win64.zip" in out and kitsetup.SONY_PAGE in out
    assert "py kit\\setup.py" in out


def test_the_table_has_one_line_per_piece():
    rows = [kitsetup.Row("SDK zip", "--", "for Win64", "-"), kitsetup.Row("SDK zip", "OK", "Mac zip"),
            kitsetup.Row("cmake", "DO", "not found", "brew install cmake", blocking=True),
            kitsetup.Row("link", "FAIL", "cmake failed", "the output above"),
            kitsetup.Row("camera access", "DO", "driver", r"pnputil /add-driver x.inf /install")]
    lines = kitsetup.table(rows).splitlines()
    assert lines[0].split() == ["Piece", "State", "What", "next"]
    assert [ln.split("  ")[0].strip() for ln in lines[2:]] == ["SDK zip", "cmake", "link", "camera access"]
    assert lines[2].endswith("OK     -") and lines[3].endswith("brew install cmake")
    assert len({ln.index(ln.split()[-1]) for ln in lines[2:4]}) <= 2   # the columns line up
    col = lines[0].index("State")
    assert all(ln[col:col + 5].strip() in ("State", "-----", "OK", "DO", "FAIL", "--") for ln in lines)
    assert kitsetup.exit_code(rows, False) == 1
    assert kitsetup.exit_code([rows[1], rows[4]], False) == 0       # a reminder (the driver) does not fail it
    assert kitsetup.exit_code([rows[1]], True) == 2


def test_pytest_summary_is_read():
    assert kitsetup.summary("....\n281 passed, 3 skipped in 26.19s\n") == "281 passed, 3 skipped"
    assert kitsetup.summary("F.\n1 failed, 280 passed in 20s\n") == "1 failed, 280 passed"


def test_built_finds_what_camkit_finds(tmp_path):
    sys.path.insert(0, str(KIT))
    from camkit import built
    (tmp_path / "camlink").write_text("")
    (tmp_path / "Release").mkdir()
    (tmp_path / "Release" / "camlink.exe").write_text("")
    assert kitsetup.built(tmp_path, "camlink", platform.system()) == built(tmp_path, "camlink")
    assert kitsetup.built(tmp_path, "camlink", "Windows") == tmp_path / "Release" / "camlink.exe"
    assert kitsetup.built(tmp_path, "camlink", "Linux") == tmp_path / "camlink"


def test_the_publish_guard_refuses_sonys_files():
    from check_public import sony_sdk
    assert not sony_sdk("kit/sdk/README.md")
    assert not sony_sdk("kit/setup.py") and not sony_sdk("docs/PORTING.md")
    for path in ("kit/sdk/SimpleCli/app/CRSDK/CameraRemote_SDK.h", "kit/sdk/.build/libxml2-2.13.9.tar.xz",
                 "kit/sdk/CrSDK_v2.02.00_20260610a_Mac.zip", "kit/CrSDK_v2.02.00_20260610a_Mac.zip",
                 "kit/link/build/libCr_Core.dylib", "elsewhere/Cr_Core.dll", "vendor/CameraRemote_SDK.h"):
        assert sony_sdk(path), path


# ---------------------------------------------------------------- 9. the proof viewer

def venv_python(root: Path) -> Path:
    py = env_for(root).venv_bin("python")
    py.parent.mkdir(parents=True)
    py.write_text("")
    return py


def test_the_proof_viewer_is_built_without_pack_and_its_path_reported(tmp_path, monkeypatch, capsys):
    calls = []

    def run(cmd, cwd=None):
        calls.append([str(c) for c in cmd])
        return 0, ("wrote the proof viewer: 2055 records, 1793 proved, 1740 with pictures, 35359 frame links, from "
                   "runs/ILCE-1M2_fw4.00/; values from runs/ILCE-1M2_fw4.00/kit2_pass2/dat/reference_session_start.DAT\n"
                   f"{tmp_path / 'runs' / 'ILCE-1M2_fw4.00' / '_viewer' / 'index.html'}\n")
    monkeypatch.setattr(kitsetup, "run", run)
    py = venv_python(tmp_path)
    env = env_for(tmp_path)
    kitsetup.step_viewer(env)
    assert calls == [[str(py), str(tmp_path / "kit" / "tools" / "proof_viewer.py")]]   # never --pack, never --open
    row = env.rows[-1]
    assert (row.piece, row.state) == ("proof viewer", "OK")
    assert row.what == "built (runs/ILCE-1M2_fw4.00/_viewer/index.html)"
    assert kitsetup.table(env.rows).splitlines()[-1].split() == ["proof", "viewer", "OK", "open",
                                                                 "runs/ILCE-1M2_fw4.00/_viewer/index.html", "in", "a",
                                                                 "browser"]


def test_a_fresh_clone_gets_no_proof_viewer_and_is_told_why(tmp_path, monkeypatch, capsys):
    """The owner's rule (2026-11-06): no proof viewer where the kit has never run on a camera. proof_viewer.py refuses
    (exit status 3) with why; the setup says so plainly and fails nothing. Its line says the definition viewer needs no
    runs, which every refusal ends with (kit/tests/test_proof_viewer.py: no camera named, no runs, another camera)."""
    public = ("The definition viewer needs no runs: it shows a settings file's values by name, in a browser; "
              "kit/tools/proof_viewer.py --public --out site/viewer builds it here, and https://camset-dev.github.io/camset/viewer/ has it online.")
    refusals = {"no camera's runs are on this computer (no camera is named)":
                "No proof viewer for ILCE-1M2_fw4.00: no camera's runs are on this computer (no camera is named). The page "
                "shows the camera's own screens from the kit's runs, so it is only for whoever ran the kit on their camera. " + public,
                "the kit works on ILCE-7M5_fw1.00 (CAMSET_CAMERA), and another camera's runs are never shown on this definition (docs/decisions/0019)":
                "No proof viewer for ILCE-1M2_fw4.00: the kit works on ILCE-7M5_fw1.00 (CAMSET_CAMERA), and another camera's runs are "
                "never shown on this definition (docs/decisions/0019). For ILCE-7M5_fw1.00's own page: kit/tools/proof_viewer.py "
                "--definition ILCE-7M5_fw1.00. " + public}
    venv_python(tmp_path)
    for why, said in refusals.items():
        monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None, said=said: (3, said + "\n"))
        env = env_for(tmp_path)
        kitsetup.step_viewer(env)
        row = env.rows[-1]
        assert (row.piece, row.state) == ("proof viewer", "--")
        assert row.what == f"not built: {why}"
        assert row.next == ("none: it shows your camera's own screens once the kit has run on it; the definition viewer needs no runs "
                            "(the line above)")
        assert said in capsys.readouterr().out          # the whole reason, above the table, the definition viewer's words in it
        assert kitsetup.exit_code(env.rows, False) == 0


def test_a_failed_proof_viewer_build_fails_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: (1, "Traceback ...\nKeyError: 'settings'\n"))
    venv_python(tmp_path)
    env = env_for(tmp_path)
    kitsetup.step_viewer(env)
    row = env.rows[-1]
    assert row.state == "--" and row.what.endswith("(exit 1): KeyError: 'settings'")
    assert kitsetup.exit_code(env.rows, False) == 0


def test_the_proof_viewer_waits_for_the_venv_and_is_not_built_with_check(tmp_path, monkeypatch):
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: pytest.fail("nothing is run"))
    env = env_for(tmp_path)
    kitsetup.step_viewer(env)
    assert env.rows[-1].what == "not built: there is no .venv (above)"
    venv_python(tmp_path)
    env = env_for(tmp_path, check=True)
    kitsetup.step_viewer(env)
    assert (env.rows[-1].state, env.rows[-1].what) == ("--", "not built with --check")


@pytest.mark.parametrize("piece, state, why", [("packages", "FAIL", "the kit's packages are not installed"),
                                               ("packages", "DO", "the kit's packages are not installed"),
                                               ("venv", "DO", ".venv is not ready")])
def test_the_proof_viewer_waits_for_the_packages(tmp_path, monkeypatch, piece, state, why):
    """Without the kit's packages proof_viewer.py stops and says to run kit/setup.py (camkit/start.py), which is what
    is running: its last line as the reason, and its steps in the tail, would send the person round in a circle. The
    reason is the line above that stopped it: the packages, or a .venv too old or without pip (no packages line then)."""
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: pytest.fail("nothing is run"))
    venv_python(tmp_path)
    env = env_for(tmp_path)
    env.add("venv", "OK", ".venv (Python 3.14.3)")
    env.add(piece, state, "a step that did not go through")
    kitsetup.step_viewer(env)
    row = env.rows[-1]
    assert (row.piece, row.state, row.what) == ("proof viewer", "--", f"not built: {why} (above)")
    assert row.next == f"the {piece} line above" and kitsetup.exit_code([row], False) == 0


def test_windows_finds_the_cpp_tools_through_vswhere(tmp_path, monkeypatch, capsys):
    """Without cl on the PATH (outside a Developer prompt, the usual case), setup asks vswhere.exe under
    %ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer where Visual Studio is. 2026-11-08: a comment cut the path
    after "Program Files (x86)", so setup ran the folder and said the C++ tools were missing."""
    pf = tmp_path / "Program Files (x86)"
    vswhere = pf / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    vswhere.parent.mkdir(parents=True)
    vswhere.write_bytes(b"MZ")
    monkeypatch.setenv("ProgramFiles(x86)", str(pf))
    assert kitsetup.vswhere_path() == vswhere
    calls = []

    def run(cmd, cwd=None):
        calls.append([str(c) for c in cmd])
        if str(cmd[0]).endswith("vswhere.exe"):
            return 0, "C:\\VS\\2022\\Community\n"
        return 0, "cmake version 3.31.6\n"
    monkeypatch.setattr(kitsetup, "run", run)
    monkeypatch.setattr(kitsetup, "which", lambda name: None if name == "cl" else f"C:\\bin\\{name}.exe")
    env = env_for(tmp_path, system="Windows", machine="AMD64")
    kitsetup.step_tools(env)
    asked = [c for c in calls if c[0].endswith("vswhere.exe")]
    assert asked and asked[0][0] == str(vswhere) and "-latest" in asked[0]
    row = next(r for r in env.rows if r.piece == "C++ compiler")
    assert row.state == "OK" and "C:\\VS\\2022\\Community" in row.what and env.tools["cxx"] is True


# ---------------------------------------------------------------- Windows: the USB driver, UTF-8 mode, the wording

# pnputil /enum-drivers as Windows prints it, made up: one entry per driver in the store
PNPUTIL_WITH = """Microsoft PnP Utility

Published Name:     oem7.inf
Original Name:      examplenet.inf
Provider Name:      Example Corp
Class Name:         Network adapters
Driver Version:     01/01/2025 1.0.0.0
Signer Name:        Microsoft Windows Hardware Compatibility Publisher

Published Name:     oem42.inf
Original Name:      srcameradriver.inf
Provider Name:      Sony
Class Name:         libusbK Usb Devices
Driver Version:     01/01/2024 3.1.0.0
Signer Name:        Microsoft Windows Hardware Compatibility Publisher
"""
PNPUTIL_WITHOUT = PNPUTIL_WITH.split("\nPublished Name:     oem42.inf")[0] + "\n"
# the same on a German Windows: the labels change, the file name does not
PNPUTIL_GERMAN = """Microsoft-PnP-Dienstprogramm

Veröffentlichter Name:   oem42.inf
Originalname:            SRCameraDriver.inf
Anbietername:            Sony
Klassenname:             libusbK Usb Devices
"""


def test_the_driver_is_found_in_pnputils_list_in_any_language():
    assert kitsetup.driver_installed(PNPUTIL_WITH)
    assert not kitsetup.driver_installed(PNPUTIL_WITHOUT)
    assert not kitsetup.driver_installed("")
    assert kitsetup.driver_installed(PNPUTIL_GERMAN)                  # localised labels, the name in another case


def windows(root: Path, **kw):
    return env_for(root, "Windows", "AMD64", **kw)


def test_an_installed_driver_is_ok_on_windows(tmp_path, monkeypatch):
    """2026-11-12, the first run on a Windows 11 PC: the DO for the driver came back after it was installed, as the
    setup never looked. pnputil /enum-drivers lists it, without administrator rights."""
    monkeypatch.setattr(kitsetup, "driver_listing", lambda: (PNPUTIL_WITH, ""))
    env = windows(tmp_path)
    kitsetup.step_access(env)
    row = env.rows[-1]
    assert (row.piece, row.state) == ("camera access", "OK")
    assert row.what == "Sony's USB driver is installed (srcameradriver.inf)"


def test_a_missing_driver_is_numbered_steps_as_administrator(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kitsetup, "driver_listing", lambda: (PNPUTIL_WITHOUT, ""))
    env = windows(tmp_path)
    inf = env.sdk / "Driver" / "srcameradriver.inf"
    inf.parent.mkdir(parents=True)
    inf.write_text("; inf")
    kitsetup.step_access(env)
    row = env.rows[-1]
    assert row.state == "DO" and row.yours and not row.blocking and kitsetup.exit_code(env.rows, False) == 0
    assert "not installed yet" in row.what and "administrator" in row.what and "could not check" not in row.what
    assert "Run as administrator" in row.steps[0]
    assert f'pnputil /add-driver "{inf}" /install' in row.steps[1]  # the whole path: an administrator window opens elsewhere
    out = capsys.readouterr().out
    assert "     1. Open a terminal as administrator" in out and "     4. Then run py kit\\setup.py again." in out
    assert "does not wait for you" in out


def test_a_driver_that_cannot_be_checked_is_still_a_reminder(tmp_path, monkeypatch):
    monkeypatch.setattr(kitsetup, "driver_listing", lambda: (None, "pnputil could not be started (not found)"))
    env = windows(tmp_path)
    kitsetup.step_access(env)                                        # and no Driver\ folder either
    row = env.rows[-1]
    assert row.state == "DO" and not row.blocking and kitsetup.exit_code(env.rows, False) == 0
    assert "is not in kit\\sdk\\Driver\\" in row.what
    assert "could not check whether it is installed: pnputil could not be started (not found)" in row.what
    assert "Win64 SDK zip" in row.steps[0] and str(env.sdk) in row.steps[0]


def test_pnputil_that_fails_or_hangs_is_no_crash(monkeypatch):
    monkeypatch.setattr(kitsetup, "which", lambda name: None)

    def answer(result):
        def fake(cmd, **kw):
            assert cmd[1:] == ["/enum-drivers"] and kw["timeout"] == 60
            if isinstance(result, BaseException):
                raise result
            return result
        return fake
    cases = [(FileNotFoundError(2, "No such file"), "could not be started"),
             (kitsetup.subprocess.TimeoutExpired("pnputil", 60), "no answer within 60 s"),
             (kitsetup.subprocess.CompletedProcess([], 5, "Access denied\n"), "failed (exit 5)"),
             (kitsetup.subprocess.CompletedProcess([], 0, "\n"), "printed nothing")]
    for result, why in cases:
        monkeypatch.setattr(kitsetup.subprocess, "run", answer(result))
        listing, said = kitsetup.driver_listing()
        assert listing is None and why in said, said
    monkeypatch.setattr(kitsetup.subprocess, "run", answer(kitsetup.subprocess.CompletedProcess([], 0, PNPUTIL_WITH)))
    assert kitsetup.driver_listing() == (PNPUTIL_WITH, "")


def test_without_utf8_mode_a_windows_run_stops_with_the_three_steps(tmp_path, monkeypatch, capsys, no_tools):
    """2026-11-12: "it asked me to open a new terminal and set it but after that it wasn't clear". Without PYTHONUTF8
    no kit program starts, so the tests and the proof viewer would fail after minutes of work: the run stops at once,
    and its last words are the steps, in order."""
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.setattr(kitsetup, "kit_python_version", lambda env: (3, 12))   # whichever Python runs the tests
    monkeypatch.setattr(kitsetup, "started_in_utf8_mode", lambda: False)
    sdk_zip(tmp_path / "kit" / "sdk", "Win64")
    code = kitsetup.main([], windows(tmp_path))
    out = capsys.readouterr().out
    assert code == 1 and no_tools == [] and not (tmp_path / "kit" / "sdk" / "SimpleCli").exists()
    assert "SDK zip" not in out and "does not wait" not in out and "The setup stops here" in out
    tail_lines = out.rstrip().splitlines()[-6:]
    assert tail_lines[0] == "1 thing is left for you to do:"
    assert tail_lines[1] == "  1. UTF-8 mode: the kit runs only in Python's UTF-8 mode on Windows, which is not on in this window"
    assert tail_lines[2].startswith("     1. In this window, run: setx PYTHONUTF8 1") and "(it answers that the value was saved)" in tail_lines[2]
    # the new window is opened first and this one kept, as it holds the steps: the folder and the command come after
    assert tail_lines[3].startswith("     2. Open a new terminal (Command Prompt or PowerShell) and keep this window open "
                                    "for now: the setting reaches only windows opened after it.")
    assert "echo %PYTHONUTF8%" in tail_lines[3] and "echo $env:PYTHONUTF8" in tail_lines[3]
    assert tail_lines[4] == (f'     3. In the new window, go to the camset folder (in Command Prompt: cd /d "{tmp_path}"; '
                             f'in PowerShell: cd "{tmp_path}") and run py kit\\setup.py again.')
    assert tail_lines[5] == "Once it runs there, you can close this window."
    # the same three numbered steps as the run printed them at the UTF-8 line
    for line in tail_lines[2:5]:
        assert out.count(line + "\n") == 2, line
    # --check only reports, so it goes on; with PYTHONUTF8=1 the line is OK
    kitsetup.main(["--check"], windows(tmp_path))
    out = capsys.readouterr().out
    assert "DO   UTF-8 mode" in out and "SDK zip" in out
    monkeypatch.setenv("PYTHONUTF8", "1")
    env = windows(tmp_path)
    assert kitsetup.step_utf8(env) is False and env.rows[-1].state == "OK"
    mac = env_for(tmp_path)
    assert kitsetup.step_utf8(mac) is False and mac.rows == []


def test_the_end_lists_what_is_left_in_order(tmp_path, capsys):
    env = windows(tmp_path)
    env.add("cmake", "DO", "not found; install it: winget install Kitware.CMake", "winget install Kitware.CMake",
            blocking=True, **kitsetup.new_window(env, "winget install Kitware.CMake"))
    env.add("link", "FAIL", "not built: it needs cmake (above)", "the lines above")
    env.add("tests", "--", "not run", env.me)
    env.add("camera access", "DO", "Sony's USB driver is not installed yet", "the steps below the table",
            steps=["Open a terminal as administrator.", "Run the command."])
    out = capsys.readouterr().out
    assert out.count("does not wait for you") == 1                    # said once, at the first DO
    lines = kitsetup.ending(env, kitsetup.exit_code(env.rows, False))
    assert lines == [
        "1 step failed: link (FAIL above, with its reason, and the last lines of a tool's output where it printed any).",
        "2 things are left for you to do, in this order:",
        "  1. cmake: not found; install it: winget install Kitware.CMake",
        "     1. Run: winget install Kitware.CMake",
        "     2. When it has finished, open a new terminal and keep this window open for now: what winget installs "
        "reaches only windows opened after it.",
        "  2. camera access: Sony's USB driver is not installed yet",
        "     1. Open a terminal as administrator.",
        "     2. Run the command.",
        f'In the new window, go to the camset folder (in Command Prompt: cd /d "{tmp_path}"; in PowerShell: cd '
        f'"{tmp_path}") and run py kit\\setup.py again.',          # after both: the last thing to do
        "Once it runs there, you can close this window."]
    done = env_for(tmp_path)
    done.add("cmake", "OK", "found")
    assert kitsetup.ending(done, 0)[-1].startswith("Everything is in place: the kit is set up.")
    reminder = env_for(tmp_path)
    reminder.add("hooks", "DO", "pre-commit install failed", ".venv/bin/pre-commit install")
    assert kitsetup.ending(reminder, 0)[:2] == ["The kit is set up, but 1 thing is left for you to do:",
                                                "  1. hooks: pre-commit install failed"]
    assert kitsetup.ending(reminder, 0)[-1] == "Then run python3 kit/setup.py again."
    check = env_for(tmp_path, check=True)
    check.add("link", "DO", "would build kit/link/build/camlink: python3 kit/setup.py", "python3 kit/setup.py")
    assert not check.rows[-1].yours
    assert kitsetup.ending(check, 0)[0] == "Nothing was changed (--check). A run of python3 kit/setup.py would see to: link."


def test_windows_commands_are_in_windows_words(tmp_path, monkeypatch):
    """No mv, no forward slashes in a path to type into Command Prompt, and a winget install says to open a new
    window, as winget's programs reach only the windows opened after it."""
    env = windows(tmp_path)
    (tmp_path / ".venv").mkdir()
    kitsetup.step_venv(env)
    assert env.rows[-1].next == "move .venv .venv.old" and "(move .venv .venv.old)" in env.rows[-1].what
    assert env_for(tmp_path).move_aside == "mv .venv .venv.old"
    assert env.native(env.rel(env.venv_bin("pre-commit"))) == ".venv\\Scripts\\pre-commit.exe"
    assert env_for(tmp_path).native("kit/sdk/") == "kit/sdk/"
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: (0, ""))
    monkeypatch.setattr(kitsetup, "which", lambda name: None)
    monkeypatch.setattr(kitsetup, "vswhere_path", lambda: tmp_path / "none" / "vswhere.exe")
    tools = windows(tmp_path)
    kitsetup.step_tools(tools)
    cmake = next(r for r in tools.rows if r.piece == "cmake")
    assert cmake.steps[0] == "Run: winget install Kitware.CMake" and "open a new terminal" in cmake.steps[1]
    assert cmake.again.startswith("In the new window, go to the camset folder")
    cxx = next(r for r in tools.rows if r.piece == "C++ compiler")
    assert "administrator permission" in cxx.steps[1] and cxx.blocking
    mac = env_for(tmp_path)
    kitsetup.step_tools(mac)
    assert all(not r.steps for r in mac.rows)


# ---------------------------------------------------------------- progress

def test_elapsed_time_reads_plainly():
    assert kitsetup.elapsed_text(0) == "0 s" and kitsetup.elapsed_text(45.9) == "45 s"
    assert kitsetup.elapsed_text(65) == "1 min 05 s" and kitsetup.elapsed_text(600) == "10 min 00 s"
    assert kitsetup.elapsed_text(3720) == "1 h 02 min"


def test_how_far_a_tool_is_is_read_from_its_output():
    dots = "." * 72
    assert kitsetup.pytest_progress(f"{dots} [  3%]\n{dots} [ 43%]\n....") == "43 % done"
    assert kitsetup.pytest_progress(f"{dots} [100%]\n\n2132 passed in 191.80s\n") == "100 % done"
    assert kitsetup.pytest_progress("") == "" and kitsetup.pytest_progress("collecting ...") == ""
    assert kitsetup.build_progress("[ 12%] Building CXX object x.o\n[ 45%] Linking CXX executable camlink\n") == "45 % done"
    assert kitsetup.build_progress("[3/40] Building CXX object a.o\n[12/40] Building CXX object b.o\n") == "step 12 of 40"
    assert kitsetup.build_progress("   Compiling serde v1.0.219\n   Compiling egui v0.31.1\n") == "2 crates compiled"
    assert kitsetup.build_progress("  camlink.cpp\n  camlink.vcxproj -> C:\\x\\camlink.exe\n") == ""   # MSBuild: no count
    assert kitsetup.pip_progress("Collecting numpy\n  Downloading numpy-2.3.0.whl (13 MB)\n") == "fetching numpy"
    assert kitsetup.pip_progress("Collecting numpy\nInstalling collected packages: numpy\n") == "installing the packages"
    assert kitsetup.pip_progress("Requirement already satisfied: numpy in ./.venv\n") == "checking the packages already there"


class Stream(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


def test_a_terminal_gets_one_line_rewritten_and_a_pipe_plain_lines():
    assert kitsetup.live_line(Stream(True), {}) and not kitsetup.live_line(Stream(False), {})
    assert not kitsetup.live_line(Stream(True), {"TERM": "dumb"})
    assert not kitsetup.live_line(object(), {})                       # no isatty at all
    pipe = Stream(False)
    p = kitsetup.Progress("the kit's tests", "about 3 minutes", 600, "py kit\\setup.py", kitsetup.pytest_progress,
                          stream=pipe)
    for second in range(1, 70):
        p.tick(second)
    assert pipe.getvalue().splitlines() == ["     ... the kit's tests: still running (30 s)",
                                            "     ... the kit's tests: still running (1 min 00 s)"]
    p.feed("." * 72 + " [ 43%]\n")
    p.tick(90)
    assert pipe.getvalue().splitlines()[-1] == "     ... the kit's tests: 43 % done (1 min 30 s)"
    term = Stream(True)
    t = kitsetup.Progress("building kit/link", "1 to 3 minutes", 600, "python3 kit/setup.py", stream=term,
                          columns=lambda: 200)                         # whatever this terminal's width
    t.tick(1)
    assert term.getvalue() == ""                                      # a quick step shows nothing
    t.tick(3)
    t.detail = "made by hand"
    t.tick(4)
    first = "     ... building kit/link: still running (3 s)"
    assert term.getvalue() == ("\r" + first + "\r     ... building kit/link: made by hand (4 s) ")   # padded over the longer one
    t.clear()
    assert term.getvalue().endswith("\r" + " " * len(first) + "\r")


def test_a_step_far_beyond_its_time_says_so_once():
    pipe = Stream(False)
    p = kitsetup.Progress("the kit's tests", "about 3 minutes", 1800, "py kit\\setup.py", stream=pipe)
    p.tick(1799)
    assert "longer than usual" not in pipe.getvalue()
    p.tick(1800)
    p.tick(1830)
    said = pipe.getvalue()
    assert said.count("This is taking longer than usual (about 3 minutes). You may keep waiting") == 1
    assert "press Ctrl+C: nothing is lost, and py kit\\setup.py picks up again" in said
    assert "send the last lines shown here" in said


def test_a_long_tools_output_reaches_the_progress_line_as_it_comes(tmp_path):
    """run() inside a Progress reads the tool's output as it arrives (a real Python here) and still gives the whole
    output and the exit code, for the FAIL lines."""
    script = "import sys\nprint('. [ 50%]', flush=True)\nprint('. [100%]')\nsys.exit(3)\n"
    pipe = Stream(False)
    with kitsetup.Progress("a tool", "seconds", 60, "python3 kit/setup.py", kitsetup.pytest_progress, stream=pipe) as p:
        assert kitsetup.PROGRESS is p
        code, out = kitsetup.run([sys.executable, "-c", script], cwd=tmp_path)
    assert kitsetup.PROGRESS is None
    assert code == 3 and out == ". [ 50%]\n. [100%]\n" and kitsetup.pytest_progress("".join(p.chunks)) == "100 % done"
    with kitsetup.Progress("a tool", "seconds", 60, "python3 kit/setup.py", stream=pipe):
        assert kitsetup.run([str(tmp_path / "no-such-tool")])[0] == 127


def test_the_long_steps_say_how_long_before_they_start(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: (0, "2132 passed in 191.80s\n"))
    venv_python(tmp_path)
    env = env_for(tmp_path)
    kitsetup.step_tests(env)
    out = capsys.readouterr().out
    assert f"running the kit's tests ({kitsetup.TESTS_TIME}) ..." in out and "under a minute" not in out
    assert env.rows[-1].what == "2132 passed"


def test_a_narrow_terminal_gets_a_line_one_column_short_of_its_width():
    """A line as wide as the terminal, or wider, wraps, and the carriage return then rewrites only its last part: the
    line is cut to the width asked at each tick, less one, so a window narrowed while a step runs stays clean."""
    term, cols = Stream(True), [30]
    t = kitsetup.Progress("the kit's tests", "minutes", 600, "python3 kit/setup.py", stream=term,
                          columns=lambda: cols[0])
    t.tick(3)
    assert term.getvalue() == "\r" + "     ... the kit's tests: still running (3 s)"[:29]
    cols[0] = 20                                                      # narrowed while it runs
    t.tick(4)
    assert term.getvalue().split("\r")[-1] == "     ... the kit's tests: still running (4 s)"[:19]
    assert t.width == 19
    t.clear()
    assert term.getvalue().endswith("\r" + " " * 19 + "\r")


# ---------------------------------------------------------------- Ctrl+C: the tool stopped, the progress line quiet

class FakeOut:
    """A tool's output pipe that gives nothing until the tool ends."""
    def __init__(self, ended):
        self.ended, self.closed = ended, False

    def read1(self, n):
        self.ended.wait(10)
        return b""

    def close(self):
        self.closed = True


class StubbornTool:
    """A tool that does not stop on Ctrl+C. second_ctrl_c: a second Ctrl+C comes while the setup waits for it."""
    pid = 4321

    def __init__(self, progress, second_ctrl_c):
        self.progress, self.second = progress, second_ctrl_c
        self.ended = kitsetup.threading.Event()
        self.stdout, self.returncode, self.seen = FakeOut(self.ended), None, {}

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None and timeout == kitsetup.STOP_GRACE:          # the moment it is given to stop
            self.seen["ticking"] = self.progress._thread.is_alive()
            if self.second:
                raise KeyboardInterrupt
            raise kitsetup.subprocess.TimeoutExpired("tool", timeout)
        return self.returncode

    def kill(self):
        self.returncode = -9
        self.ended.set()


@pytest.mark.parametrize("second_ctrl_c", [False, True], ids=["one-ctrl-c", "second-ctrl-c-in-the-wait"])
def test_ctrl_c_stops_the_progress_line_and_always_ends_the_tool(monkeypatch, second_ctrl_c):
    """On Ctrl+C the progress line stops before the wait (no "still running" while the tool stops), and a tool still
    running after it is ended, even when a second Ctrl+C cuts the wait short; its pipe is closed."""
    pipe = Stream(False)
    progress = kitsetup.Progress("a tool", "seconds", 60, "python3 kit/setup.py", stream=pipe)
    tools = []

    def popen(cmd, **kw):
        tools.append(StubbornTool(progress, second_ctrl_c))
        return tools[-1]
    monkeypatch.setattr(kitsetup.subprocess, "Popen", popen)
    stopped = []
    monkeypatch.setattr(kitsetup, "stop_tree", lambda p: (stopped.append(p), p.kill()))
    sleeps = []

    def sleep(seconds):                                               # Ctrl+C while the setup waits for the tool
        sleeps.append(seconds)
        raise KeyboardInterrupt
    with progress:
        monkeypatch.setattr(kitsetup.time, "sleep", sleep)
        with pytest.raises(KeyboardInterrupt):
            kitsetup.watched(["tool"], None, progress)
        monkeypatch.undo()
    tool = tools[0]
    assert sleeps and tool.seen == {"ticking": False} and progress._stop.is_set()
    assert stopped == [tool] and tool.returncode == -9 and tool.stdout.closed


def test_a_tool_that_stops_on_ctrl_c_is_not_killed(monkeypatch):
    pipe = Stream(False)
    progress = kitsetup.Progress("a tool", "seconds", 60, "python3 kit/setup.py", stream=pipe)

    class Polite(StubbornTool):
        def wait(self, timeout=None):
            self.kill()                                               # it stops on the Ctrl+C it got too
            return self.returncode
    monkeypatch.setattr(kitsetup.subprocess, "Popen", lambda cmd, **kw: Polite(progress, False))
    monkeypatch.setattr(kitsetup, "stop_tree", lambda p: pytest.fail("it stopped on its own"))
    with progress:
        monkeypatch.setattr(kitsetup.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            kitsetup.watched(["tool"], None, progress)


class Ended:
    """A tool for stop_tree: alive until killed, or until taskkill has ended it (gone_after_taskkill)."""
    pid = 4321

    def __init__(self):
        self.returncode, self.killed = None, False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed, self.returncode = True, -9

    def wait(self, timeout=None):
        return self.returncode


def test_windows_ends_the_whole_tree_and_falls_back_to_the_tool_itself(monkeypatch):
    """Windows: taskkill /T /F ends the tool and what it started (pytest's stand-ins, MSBuild's compilers), which
    would hold files and temporary folders; where taskkill is missing or hangs, the tool itself is ended. Elsewhere
    the tool alone (the programs it started got the terminal's Ctrl+C)."""
    assert kitsetup.tree_kill_command(4321) == ["taskkill", "/T", "/F", "/PID", "4321"]
    calls = []

    def taskkill(result):
        def run(cmd, **kw):
            calls.append((cmd, kw.get("timeout")))
            if isinstance(result, BaseException):
                raise result
            tool.returncode = 1                                       # taskkill ended it
            return kitsetup.subprocess.CompletedProcess(cmd, 0)
        return run
    tool = Ended()
    monkeypatch.setattr(kitsetup.subprocess, "run", taskkill(None))
    kitsetup.stop_tree(tool, windows=True)
    assert calls == [(["taskkill", "/T", "/F", "/PID", "4321"], 10)] and not tool.killed
    for failure in (FileNotFoundError(2, "taskkill"), kitsetup.subprocess.TimeoutExpired("taskkill", 10)):
        tool = Ended()
        monkeypatch.setattr(kitsetup.subprocess, "run", taskkill(failure))
        kitsetup.stop_tree(tool, windows=True)
        assert tool.killed
    calls.clear()
    tool = Ended()
    kitsetup.stop_tree(tool, windows=False)
    assert tool.killed and calls == []


# ---------------------------------------------------------------- .venv stopped half way

def test_ctrl_c_while_venv_is_made_leaves_no_half_made_venv(tmp_path, monkeypatch, capsys):
    """2026-11-12 review: a .venv whose making was stopped had its Python but no pip, the next run called it OK and
    pip then failed with no remedy, though the Ctrl+C message said nothing was lost."""
    env = env_for(tmp_path)
    monkeypatch.setattr(kitsetup, "venv_python", lambda env: (sys.executable, ""))

    def run(cmd, cwd=None):
        py = env.venv_bin("python")
        py.parent.mkdir(parents=True)
        py.write_text("")                                             # Python copied, pip not yet
        raise KeyboardInterrupt
    monkeypatch.setattr(kitsetup, "run", run)
    with pytest.raises(KeyboardInterrupt):
        kitsetup.step_venv(env)
    assert not (tmp_path / ".venv").exists()


def venv_without_pip(tmp_path, monkeypatch, ensurepip_ok: bool):
    """A .venv with its Python but a pip that does not start, and the calls made."""
    venv_python(tmp_path)
    calls, repaired = [], []

    def run(cmd, cwd=None):
        cmd = [str(c) for c in cmd]
        calls.append(cmd[1:])
        if cmd[1:] == ["-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"]:
            return 0, "3.12.4\n"
        if cmd[1:] == ["-m", "pip", "--version"]:
            return (0, "pip 25.0\n") if repaired else (1, "No module named pip\n")
        if cmd[1:3] == ["-m", "ensurepip"]:
            if ensurepip_ok:
                repaired.append(True)
                return 0, "Successfully installed pip-25.0\n"
            return 1, "ensurepip is disabled\n"
        return 0, ""
    monkeypatch.setattr(kitsetup, "run", run)
    return calls


def test_a_venv_without_a_working_pip_is_repaired(tmp_path, monkeypatch, capsys):
    calls = venv_without_pip(tmp_path, monkeypatch, ensurepip_ok=True)
    env = env_for(tmp_path)
    kitsetup.step_venv(env)
    assert ["-m", "ensurepip", "--upgrade", "--default-pip"] in calls
    assert ["-u", "-m", "pip", "install", "-r", "kit/requirements.txt"] in calls
    rows = {r.piece: r for r in env.rows}
    assert rows["venv"].state == "OK" and rows["packages"].state == "OK"
    assert "pip was put back into .venv" in capsys.readouterr().out


def test_a_venv_whose_pip_cannot_be_put_back_is_moved_aside_by_hand(tmp_path, monkeypatch):
    calls = venv_without_pip(tmp_path, monkeypatch, ensurepip_ok=False)
    env = env_for(tmp_path)
    kitsetup.step_venv(env)
    row = env.rows[-1]
    assert (row.piece, row.state) == ("venv", "DO") and row.blocking and row.next == "mv .venv .venv.old"
    assert "has no working pip" in row.what and "(mv .venv .venv.old)" in row.what
    assert not any(c[:2] == ["-u", "-m"] for c in calls)              # no pip install with no pip
    assert kitsetup.exit_code(env.rows, False) == 1


def test_check_only_says_a_venv_without_pip_would_be_repaired(tmp_path, monkeypatch):
    calls = venv_without_pip(tmp_path, monkeypatch, ensurepip_ok=True)
    env = env_for(tmp_path, check=True)
    kitsetup.step_venv(env)
    rows = {r.piece: r for r in env.rows}
    assert rows["venv"].state == "DO" and not rows["venv"].yours and "puts it back" in rows["venv"].what
    assert rows["hooks"].state == "--"                               # its row too, as when there is no .venv yet
    assert not any("ensurepip" in c for call in calls for c in call)


# ---------------------------------------------------------------- UTF-8 mode: what reaches the kit's programs

def utf8_row(tmp_path, monkeypatch, value, kit_version=(3, 12), started=False, check=False):
    if value is None:
        monkeypatch.delenv("PYTHONUTF8", raising=False)
    else:
        monkeypatch.setenv("PYTHONUTF8", value)
    asked = []
    monkeypatch.setattr(kitsetup, "kit_python_version", lambda env: asked.append(1) or kit_version)
    monkeypatch.setattr(kitsetup, "started_in_utf8_mode", lambda: started)
    env = windows(tmp_path, check=check)
    stop = kitsetup.step_utf8(env)
    return stop, env.rows[-1], asked


def test_utf8_mode_is_on_by_default_from_python_3_15(tmp_path, monkeypatch):
    """PEP 686: Python 3.15 and newer have UTF-8 mode on unless PYTHONUTF8 is 0, and camkit asks sys.flags.utf8_mode,
    so a kit Python that new needs no PYTHONUTF8."""
    stop, row, _ = utf8_row(tmp_path, monkeypatch, None, kit_version=(3, 15))
    assert not stop and row.state == "OK"
    assert row.what == "on by default in Python 3.15, which runs the kit (PYTHONUTF8 is not set in this window)"
    stop, row, _ = utf8_row(tmp_path, monkeypatch, "", kit_version=(3, 16))      # set but empty: as not set
    assert not stop and row.state == "OK"
    stop, row, _ = utf8_row(tmp_path, monkeypatch, None, kit_version=(3, 14))
    assert stop and row.state == "DO" and row.blocking and "not on in this window" in row.what
    stop, row, _ = utf8_row(tmp_path, monkeypatch, None, kit_version=None)       # the kit's Python could not say
    assert stop and row.state == "DO"
    stop, row, asked = utf8_row(tmp_path, monkeypatch, "1", kit_version=(3, 12))
    assert not stop and row.what == "PYTHONUTF8 is 1 in this window" and asked == []


def test_pythonutf8_0_is_off_on_every_python(tmp_path, monkeypatch):
    stop, row, asked = utf8_row(tmp_path, monkeypatch, "0", kit_version=(3, 15))
    assert stop and row.state == "DO" and asked == []
    assert row.what.startswith("PYTHONUTF8 is set to 0 in this window, which turns off Python's UTF-8 mode")
    assert "set it to 1" in row.what and row.steps[0].startswith("In this window, run: setx PYTHONUTF8 1")


def test_a_setup_started_with_x_utf8_still_stops_and_says_why(tmp_path, monkeypatch):
    """py -X utf8 kit\\setup.py with PYTHONUTF8 unset on Python 3.14: the setup itself is in UTF-8 mode, the kit's
    programs it starts are not, so it stops, in words that are true for it."""
    stop, row, _ = utf8_row(tmp_path, monkeypatch, None, kit_version=(3, 14), started=True)
    assert stop and row.state == "DO" and row.blocking
    assert row.what.startswith("this setup was started in Python's UTF-8 mode (-X utf8), but the kit's programs")
    stop, row, _ = utf8_row(tmp_path, monkeypatch, None, kit_version=(3, 14), started=True, check=True)
    assert not stop and row.state == "DO"                             # --check reports and goes on


def test_the_kits_python_is_venvs_else_the_one_the_venv_would_be_made_with(tmp_path, monkeypatch):
    env = windows(tmp_path)
    answers = {}

    def run(cmd, cwd=None):
        return answers.get(str(cmd[0]), (1, "not found"))
    monkeypatch.setattr(kitsetup, "run", run)
    monkeypatch.setattr(kitsetup, "venv_python", lambda env: ("C:\\Python314\\python.exe", "Python 3.14: ..."))
    answers["C:\\Python314\\python.exe"] = (0, "3.14\n")
    assert kitsetup.kit_python_version(env) == (3, 14)                # no .venv yet
    py = env.venv_bin("python")
    py.parent.mkdir(parents=True)
    py.write_text("")
    answers[str(py)] = (0, "3.15\n")
    assert kitsetup.kit_python_version(env) == (3, 15)                # .venv's
    answers[str(py)] = (1, "broken")
    assert kitsetup.kit_python_version(env) == (3, 14)                # a broken one: the one a new .venv gets
    monkeypatch.setattr(kitsetup, "venv_python", lambda env: (sys.executable, ""))
    assert kitsetup.kit_python_version(env) == tuple(sys.version_info[:2])


def test_the_new_window_step_works_in_both_windows_terminals(tmp_path):
    """Command Prompt's cd changes drive (D:\\camset from C:\\) only with /d, PowerShell's always: both are named, so
    the person need not know which terminal they have."""
    env = windows(tmp_path)
    for again in (kitsetup.utf8_steps(env)["again"], kitsetup.new_window(env, "winget install Kitware.CMake")["again"]):
        assert f'in Command Prompt: cd /d "{tmp_path}"' in again and f'in PowerShell: cd "{tmp_path}"' in again
    # camkit's UTF-8 message, and its words for a Python without the kit's packages, take the step from camkit.start,
    # which says the same: this script runs before .venv exists and never imports camkit (camkit stops without UTF-8 mode)
    from camkit import start
    assert start.go_to(tmp_path, windows=True) == kitsetup.go_to(tmp_path)
    camkit = (KIT / "camkit" / "__init__.py").read_text(encoding="utf-8")
    assert "{start.go_to(ROOT, windows=True)} and run the same command again" in camkit
    assert "SUCCESS" not in camkit and "(it answers that the value was saved)" in camkit
    tree = ast.parse((KIT / "setup.py").read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Import) and any(a.name.startswith("camkit") for a in n.names)
                or isinstance(n, ast.ImportFrom) and (n.module or "").startswith("camkit")]


# ---------------------------------------------------------------- the driver, when pnputil cannot be asked

def test_a_driver_that_could_not_be_checked_may_not_be_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(kitsetup, "driver_listing", lambda: (None, "pnputil /enum-drivers failed (exit 5)"))
    env = windows(tmp_path)
    inf = env.sdk / "Driver" / "srcameradriver.inf"
    inf.parent.mkdir(parents=True)
    inf.write_text("; inf")
    kitsetup.step_access(env)
    row = env.rows[-1]
    assert row.state == "DO" and not row.blocking
    assert row.what.startswith("Sony's USB driver may not be installed yet;") and "is not installed" not in row.what
    assert row.what.endswith("pnputil /enum-drivers failed (exit 5); if you have installed it already, you can ignore "
                             "this line)")
    assert f'pnputil /add-driver "{inf}" /install' in row.steps[1]
    assert "(or Command Prompt, on Windows 10)" in row.steps[0]


# ---------------------------------------------------------------- the tests' own temporary folder

def test_the_tests_run_in_a_temporary_folder_of_the_setups_own(tmp_path, monkeypatch):
    """pytest's own numbered folders and their pytest-current link crashed its clean-up on Windows after a stopped run
    (PermissionError): the setup's run of the tests gets a folder of its own, emptied first."""
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    base = tmp_path / "temp" / "camset-kit-tests"
    (base / "pytest-old").mkdir(parents=True)
    (base / "pytest-old" / "left.txt").write_text("from a stopped run")
    calls = []

    def run(cmd, cwd=None):
        calls.append([str(c) for c in cmd])
        return 0, "2132 passed in 191.80s\n"
    monkeypatch.setattr(kitsetup, "run", run)
    venv_python(tmp_path)
    env = env_for(tmp_path)
    kitsetup.step_tests(env)
    assert calls[0][-1] == f"--basetemp={base}" and calls[0][-4:-1] == ["pytest", "kit/tests", "-q"]
    assert not base.exists() and env.rows[-1].state == "OK"           # emptied first (pytest makes it again)


def test_a_temporary_folder_that_cannot_be_emptied_is_named_and_another_used(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    monkeypatch.setattr(kitsetup.tempfile, "tempdir", str(tmp_path / "temp"))
    base = tmp_path / "temp" / "camset-kit-tests"
    base.mkdir(parents=True)

    def locked(path, *a, **kw):
        raise PermissionError(13, "The process cannot access the file because it is being used by another process")
    real_rmtree = kitsetup.shutil.rmtree
    used = []

    def run(cmd, cwd=None):
        used.append(Path(str(cmd[-1]).split("=", 1)[1]))
        assert used[-1].is_dir()
        return 0, "2132 passed in 191.80s\n"
    monkeypatch.setattr(kitsetup, "run", run)
    venv_python(tmp_path)
    env = env_for(tmp_path)
    monkeypatch.setattr(kitsetup.shutil, "rmtree", lambda p, ignore_errors=False: (
        real_rmtree(p, ignore_errors=ignore_errors) if ignore_errors else locked(p)))
    kitsetup.step_tests(env)
    out = capsys.readouterr().out
    assert f"The folder {base} could not be emptied" in out and "Closing other terminals that run the kit" in out
    assert used[0] != base and used[0].name.startswith("camset-kit-tests-") and str(used[0]) in out
    assert not used[0].exists() and env.rows[-1].state == "OK"        # the fresh one removed after the run


def test_tests_that_did_not_finish_say_so_plainly(tmp_path, monkeypatch, capsys):
    """2026-11-12: pytest crashed in its own clean-up and the setup said "FAIL tests: no summary" under a long
    traceback."""
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    crash = "....\nTraceback (most recent call last):\nPermissionError: [WinError 5] Access is denied: 'pytest-current'\n"
    monkeypatch.setattr(kitsetup, "run", lambda cmd, cwd=None: (1, crash))
    venv_python(tmp_path)
    env = env_for(tmp_path)
    kitsetup.step_tests(env)
    row = env.rows[-1]
    assert row.state == "FAIL" and "no summary" not in row.what
    assert row.what == ("the tests did not finish (exit 1): pytest stopped before it could count them, and its last "
                        "lines, below, say why")
    assert "     | PermissionError: [WinError 5] Access is denied: 'pytest-current'" in capsys.readouterr().out


# ---------------------------------------------------------------- the last words

def test_the_last_words_read_true_for_one_failure_and_for_check(tmp_path):
    one = env_for(tmp_path)
    one.add("link", "FAIL", "cmake failed", "the output above")
    assert kitsetup.ending(one, 1) == [
        "1 step failed: link (FAIL above, with its reason, and the last lines of a tool's output where it printed any).",
        "When it is fixed, run python3 kit/setup.py again."]
    two = env_for(tmp_path)
    two.add("link", "FAIL", "cmake failed", "the output above")
    two.add("probe", "FAIL", "cmake failed", "the output above")
    assert kitsetup.ending(two, 1) == [
        "2 steps failed: link, probe (FAIL above, each with its reason, and the last lines of a tool's output where it "
        "printed any).", "When they are fixed, run python3 kit/setup.py again."]
    check = env_for(tmp_path, check=True)
    check.add("cmake", "OK", "found")
    assert kitsetup.ending(check, 0) == [
        "Nothing was changed (--check).",
        "Nothing is missing that you need to do by hand. Run python3 kit/setup.py to finish the setup: it also installs "
        "the packages and runs the tests, which --check does not."]


def test_a_junction_named_as_the_tests_folder_is_removed_not_followed(tmp_path, monkeypatch):
    """Windows: a directory junction is no symlink to is_symlink, and rmtree refuses it, so every later run would take
    a fresh folder with an untrue note. Faked here with a link that only is_junction owns to (Python 3.12's
    Path.is_junction; the kit's 3.11 has none, which the setup allows for)."""
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    base = tmp_path / "temp" / "camset-kit-tests"
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "keep.txt").write_text("not the setup's")
    base.parent.mkdir()
    base.symlink_to(target, target_is_directory=True)
    real = kitsetup.Path.is_symlink
    monkeypatch.setattr(kitsetup.Path, "is_symlink", lambda self: False if self == base else real(self))
    monkeypatch.setattr(kitsetup.Path, "is_junction", lambda self: self == base, raising=False)
    assert kitsetup.tests_folder() == (base, False)                  # the usual folder, no fallback
    assert not os.path.lexists(base) and (target / "keep.txt").read_text() == "not the setup's"


def test_a_link_named_as_the_tests_folder_is_removed_not_followed(tmp_path, monkeypatch):
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    base = tmp_path / "temp" / "camset-kit-tests"
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "keep.txt").write_text("not the setup's")
    base.parent.mkdir()
    try:
        base.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this Windows account may not make symbolic links")
    assert kitsetup.tests_folder() == (base, False)
    assert not os.path.lexists(base) and (target / "keep.txt").read_text() == "not the setup's"


@pytest.mark.parametrize("ending", ["ctrl-c", "failed"])
def test_the_fresh_tests_folder_is_removed_however_the_tests_end(tmp_path, monkeypatch, capsys, ending):
    """The new folder taken when the usual one cannot be emptied is the run's own: removed after an interrupted or a
    failed run too, not left to pile up."""
    monkeypatch.setattr(kitsetup.tempfile, "gettempdir", lambda: str(tmp_path / "temp"))
    monkeypatch.setattr(kitsetup.tempfile, "tempdir", str(tmp_path / "temp"))
    (tmp_path / "temp" / "camset-kit-tests").mkdir(parents=True)
    real_rmtree = kitsetup.shutil.rmtree
    used = []

    def rmtree(p, ignore_errors=False):
        if not ignore_errors:
            raise PermissionError(13, "in use")                       # the usual folder is held by a leftover program
        real_rmtree(p, ignore_errors=True)

    def run(cmd, cwd=None):
        used.append(Path(str(cmd[-1]).split("=", 1)[1]))
        assert used[-1].is_dir()
        if ending == "ctrl-c":
            raise KeyboardInterrupt
        return 1, "F.\n1 failed, 1 passed in 1.00s\n"
    monkeypatch.setattr(kitsetup, "run", run)
    venv_python(tmp_path)
    env = env_for(tmp_path)
    monkeypatch.setattr(kitsetup.shutil, "rmtree", rmtree)
    if ending == "ctrl-c":
        with pytest.raises(KeyboardInterrupt):
            kitsetup.step_tests(env)
    else:
        kitsetup.step_tests(env)
        assert env.rows[-1].state == "FAIL" and env.rows[-1].what == "1 failed, 1 passed (exit 1)"
    assert used and used[0].name.startswith("camset-kit-tests-") and not used[0].exists()
