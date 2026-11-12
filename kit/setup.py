#!/usr/bin/env python3
"""The kit's setup command: Sony's SDK zip dropped into kit/sdk/, then one command sets up the rest.
(Not a setuptools file: the kit is run from the clone, never installed as a package.)

    python3 kit/setup.py [SDK_ZIP] [--check] [--force] [--editor]        (Windows: py kit\\setup.py ...)

The steps, in order. Each prints one line: OK (in place), DO (yours to do, with the exact command), FAIL (what and
why), or -- (not asked for, or not run with --check):
 1. The SDK zip: SDK_ZIP, else the newest kit/sdk/CrSDK_v<version>_<date>_<OS>.zip for this machine, checked by
    its contents. With none, a kit/sdk/SimpleCli/ already unpacked is used as it is.
 2. Unpacking it into kit/sdk/ only: the zip's files, then SimpleCli/, CrSDK_API_Reference_v<version>/ and, on
    Windows, Driver/. A file already there with the same size and CRC is kept. Whether it is unpacked rests only on
    what the kit uses (SimpleCli/app/, SimpleCli/external/crsdk/, the API reference, Driver/); the zip's other files
    are written too, and only counted.
 3. The tools: Python 3.11 or newer, cmake, a C++ compiler, the OS packages, cargo (for --editor), ffmpeg (for an
    HDMI capture dongle). It never runs sudo or an installer: it prints the command, and checks again next time.
 4. On Linux without libxml2.so.2 (Sony's libCr_Core.so needs it): libxml2 2.13.9, its SHA-256 checked, built in
    kit/sdk/.build/ and copied beside the SDK's libraries.
 5. .venv with kit/requirements.txt (made with the newest installed Python the packages install on), and the
    pre-commit hooks.
 6. The builds: the camera link (kit/link), the editor's camera helper (kit/probe), on macOS the OCR helper
    (kit/ocr), and with --editor the editor. cmake and cargo are always run, as they rebuild only what changed, and
    each says "built" or "up to date"; the OCR helper is built again when kit/ocr/ocr.swift is newer than it. With
    --check, a program already there is OK and rebuilt on a run if its sources changed. --force builds from clean.
 7. Camera access: the udev rule on Linux, Sony's USB driver on Windows.
 8. The kit's tests.
 9. The proof viewer, runs/<model>_fw<fw>/_viewer/index.html (the definition's camera's folder), built as
    kit/tools/build_docs.py builds it (no --pack, no --open), only where the kit has run on the camera the config
    names (camkit.paths): it shows that camera's own screens, so it is for whoever mapped their camera, never part of
    a submission. A fresh clone gets no page: proof_viewer.py refuses (exit status 3) and the line says why and what
    makes it available. A failed build is reported with its reason (the kit's runs from before per-camera folders:
    the command that moves them). Neither fails the setup.
Then a table: each piece, its state and what next. Exit status: 0 when nothing required is missing or failed, 1 when
something is, 2 when there is no SDK zip to use.

Standard library only: it runs with the system's Python, before .venv exists. The same steps by hand are in
docs/PORTING.md, "Setup per OS". Sony's SDK is used under Sony's agreement: it stays in kit/sdk/, which git ignores
but for its README, and is never committed or shared (docs/RELEASING.md).
"""
from __future__ import annotations  # keeps this file readable by an old Python, so it can say it is too old

import argparse
import hashlib
import io
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

KIT = Path(__file__).resolve().parent
ROOT = KIT.parent
SONY_PAGE = "https://support.d-imaging.sony.co.jp/app/sdk/l/index.php"     # the README, "The camera helper"
NAME_RE = re.compile(r"^CrSDK_v(?P<ver>\d+(?:\.\d+)+)_(?P<date>[0-9A-Za-z]+)_(?P<os>Mac|Linux64PC|Linux64ARMv8|Win64)\.zip$")
API_RE = re.compile(r"^CrSDK_API_Reference_v(?P<ver>\d+(?:\.\d+)+)\.zip$")
INNER = {"SimpleCli.zip": "SimpleCli", "Driver.zip": "Driver"}      # the API reference goes to a folder of its own name
ELF_CPU = {62: "Linux64PC", 183: "Linux64ARMv8"}                     # e_machine: x86-64, AArch64
CR_CORE = {"Mac": "libCr_Core.dylib", "Linux64PC": "libCr_Core.so", "Linux64ARMv8": "libCr_Core.so", "Win64": "Cr_Core.dll"}
# libxml2 2.13.9, the last series whose library is libxml2.so.2 (docs/PORTING.md, Linux). The hash is the one
# download.gnome.org publishes beside the tarball (libxml2-2.13.9.sha256sum), checked against the tarball itself
# on 2026-11-04.
LIBXML2_URL = "https://download.gnome.org/sources/libxml2/2.13/libxml2-2.13.9.tar.xz"
LIBXML2_SHA256 = "a2c9ae7b770da34860050c309f903221c67830c86e4a7e760692b803df95143a"
LIBXML2_FLAGS = ["--without-python", "--without-zlib", "--without-lzma", "--without-icu"]
LDCONFIG_CPU = {"x86_64": "x86-64", "amd64": "x86-64", "aarch64": "AArch64", "arm64": "AArch64"}
UDEV_RULE = Path("/etc/udev/rules.d/60-sony-camera.rules")
# the camera's USB device to the user at the seat (systemd-logind's uaccess; the file sorts before 73-seat-late.rules),
# not to every local user and process as MODE="0666" did: the camera takes uploads (security review S-16, 2026-11-05)
UDEV_LINE = 'SUBSYSTEM=="usb", ATTR{idVendor}=="054c", TAG+="uaccess"'
USBFS = Path("/sys/module/usbcore/parameters/usbfs_memory_mb")
# pkg-config name -> the Debian/Ubuntu package that has it
PACKAGES = {"libudev": "libudev-dev", "libxml-2.0": "libxml2-dev"}
EDITOR_PACKAGES = {"xkbcommon": "libxkbcommon-dev", "wayland-client": "libwayland-dev", "xcb-render": "libxcb-render0-dev",
                   "xcb-shape": "libxcb-shape0-dev", "xcb-xfixes": "libxcb-xfixes0-dev"}
TAIL = 40
# The newest Python every package in kit/requirements.txt installs on: onnxruntime (RapidOCR's) had no build for 3.15
# on 2026-11-04. Only a preference: .venv is made with the newest installed Python up to this one, else with the one
# running this script.
NEWEST_PY = (3, 14)


class Refused(Exception):
    """A zip or tar entry that would land outside its folder."""


@dataclass
class Row:
    piece: str
    state: str                  # "OK", "DO", "FAIL" or "--"
    what: str
    next: str = "-"             # the table's "what next"
    blocking: bool = False      # a DO that stops the setup (a missing tool), not a reminder


@dataclass
class Env:
    """Where and how this run works; the tests give their own."""
    root: Path = ROOT
    system: str = field(default_factory=platform.system)
    machine: str = field(default_factory=platform.machine)
    check: bool = False
    force: bool = False
    editor: bool = False
    rows: list = field(default_factory=list)
    sdk_ok: bool = False        # kit/sdk/SimpleCli/ holds a complete SDK for this machine
    sdk_pending: bool = False   # --check: a run would unpack it first
    tools: dict = field(default_factory=dict)

    @property
    def sdk(self) -> Path:
        return self.root / "kit" / "sdk"

    @property
    def crsdk(self) -> Path:
        return self.sdk / "SimpleCli" / "external" / "crsdk"

    @property
    def os_tag(self) -> str | None:
        return machine_os(self.system, self.machine)

    @property
    def windows(self) -> bool:
        return self.system == "Windows"

    @property
    def me(self) -> str:
        return "py kit\\setup.py" if self.windows else "python3 kit/setup.py"

    def venv_bin(self, name: str) -> Path:
        return self.root / ".venv" / ("Scripts" if self.windows else "bin") / (name + (".exe" if self.windows else ""))

    def rel(self, path: Path) -> str:
        try:
            return Path(path).relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def add(self, piece: str, state: str, what: str, next: str = "-", blocking: bool = False) -> Row:
        row = Row(piece, state, what, next, blocking)
        self.rows.append(row)
        print(f"{state:<4} {piece}: {what}", flush=True)
        return row


# ---------------------------------------------------------------- small helpers (the tests replace run and which)

def run(cmd: list, cwd: Path | None = None) -> tuple[int, str]:
    """A tool's exit code and its output, stdout and stderr together."""
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace")
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout


def which(name: str) -> str | None:
    return shutil.which(name)


def note(text: str) -> None:
    print(f"     {text}", flush=True)


def tail(output: str) -> None:
    """The last lines of a failed tool's output."""
    for line in output.rstrip().splitlines()[-TAIL:]:
        print(f"     | {line}", flush=True)


def shown(cmd: list) -> str:
    return " ".join(str(c) for c in cmd)


def machine_os(system: str, machine: str) -> str | None:
    """The OS tag of Sony's download for this machine: Mac, Linux64PC, Linux64ARMv8 or Win64."""
    m = machine.lower()
    if system == "Darwin":
        return "Mac"
    if system == "Windows":
        return "Win64"
    if system == "Linux":
        return {"x86_64": "Linux64PC", "amd64": "Linux64PC", "aarch64": "Linux64ARMv8", "arm64": "Linux64ARMv8"}.get(m)
    return None


def built(folder: Path, name: str, system: str) -> Path:
    """A helper the kit builds, as camkit.built finds it: folder/name, or name.exe (in Release/ after a Visual Studio
    build) on Windows."""
    tries = [f"{name}.exe", f"Release/{name}.exe"] if system == "Windows" else [name]
    return next((folder / t for t in tries if (folder / t).exists()), folder / tries[0])


def version_key(text: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", text))


def inside(path: Path, base: Path) -> bool:
    try:
        b = str(base.resolve())
        return os.path.commonpath([str(path.resolve()), b]) == b
    except ValueError:                                 # another drive on Windows
        return False


def unsafe(name: str) -> bool:
    """An archive entry that is absolute or climbs out of its folder (zip-slip)."""
    n = name.replace("\\", "/")
    return n.startswith("/") or bool(re.match(r"^[A-Za-z]:", n)) or ".." in n.split("/") or "\0" in n


# ---------------------------------------------------------------- 1. the SDK zip

def lib_os(names, head) -> str | None:
    """Which OS an SDK's external/crsdk/ is for, from its Cr_Core library: names are the folder's file names and
    head(name) a file's first bytes (an ELF header names the CPU)."""
    if "libCr_Core.dylib" in names:
        return "Mac"
    if "Cr_Core.dll" in names:
        return "Win64"
    if "libCr_Core.so" in names:
        h = head("libCr_Core.so")
        if h[:4] == b"\x7fELF" and len(h) >= 20:
            return ELF_CPU.get(int.from_bytes(h[18:20], "little"))
    return None


@dataclass
class SdkZip:
    path: Path
    os: str | None = None
    version: str | None = None
    problem: str = ""


def inspect_zip(path: Path) -> SdkZip:
    """Sony's download, known by its contents: SimpleCli.zip and an API reference zip, and in SimpleCli.zip the
    Cr_Core library that says which OS it is for."""
    z = SdkZip(path)
    try:
        with zipfile.ZipFile(path) as outer:
            names = outer.namelist()
            bad = next((n for n in names if unsafe(n)), None)
            if bad:
                z.problem = f"refused: its entry {bad!r} would land outside kit/sdk/"
                return z
            refs = sorted((n for n in names if API_RE.match(n)), key=version_key)
            if "SimpleCli.zip" not in names or not refs:
                z.problem = "not Sony's Camera Remote SDK download (no SimpleCli.zip and API reference in it)"
                return z
            z.version = API_RE.match(refs[-1]).group("ver")
            with zipfile.ZipFile(io.BytesIO(outer.read("SimpleCli.zip"))) as inner:
                lib = "external/crsdk/"
                files = {n[len(lib):]: n for n in inner.namelist() if n.startswith(lib) and "/" not in n[len(lib):]}

                def head(name):
                    with inner.open(files[name]) as f:
                        return f.read(20)
                z.os = lib_os(set(files), head)
    except (zipfile.BadZipFile, OSError, KeyError, EOFError) as e:
        z.problem = f"not a readable zip ({e})"
        return z
    if z.os is None:
        z.problem = "its SimpleCli.zip holds no Cr_Core library for a known OS"
    return z


def name_os(path: Path) -> str | None:
    m = NAME_RE.match(path.name)
    return m.group("os") if m else None


def newest(paths: list) -> Path:
    def key(p):
        m = NAME_RE.match(p.name)
        return (version_key(m.group("ver")), m.group("date")) if m else ((), "")
    return max(paths, key=key)


def get_it(env: Env) -> None:
    tag = env.os_tag
    note(f"Download Sony's Camera Remote SDK for {tag} from Sony's page (free, by application; you accept Sony's")
    note(f"agreement when downloading): {SONY_PAGE}")
    note(f"The file is named CrSDK_v<version>_<date>_{tag}.zip. Put it, as it is, into kit/sdk/ ({env.sdk})")
    note(f"and run: {env.me}")


def step_sdk(env: Env, arg: str | None) -> tuple[SdkZip | None, int]:
    """The zip to unpack, or none; and 2 when there is no SDK to use."""
    want = env.os_tag
    if want is None:
        env.add("SDK zip", "FAIL", f"Sony's SDK has no download for this machine ({env.system} {env.machine})")
        return None, 2
    if arg:
        p = Path(arg).expanduser().resolve()
        if not p.is_file():
            env.add("SDK zip", "FAIL", f"{arg}: no such file")
            return None, 2
        z = inspect_zip(p)
        if z.problem:
            env.add("SDK zip", "FAIL", f"{p.name}: {z.problem}", "the zip from Sony's page, as downloaded")
            return None, 2
        if z.os != want:
            env.add("SDK zip", "FAIL", f"{p.name} is Sony's SDK for {z.os}; this machine needs the {want} download",
                    f"the {want} zip from Sony's page")
            get_it(env)
            return None, 2
        env.add("SDK zip", "OK", f"{p.name}: Sony's SDK v{z.version} for {want}, checked by its contents")
        return z, 0
    found = sorted(env.sdk.glob("CrSDK_v*_*.zip")) if env.sdk.is_dir() else []
    mine = []
    for p in found:
        tag = name_os(p) or inspect_zip(p).os
        if tag == want:
            mine.append(p)
        else:
            env.add("SDK zip", "--", f"kit/sdk/{p.name} is for {tag or 'no OS the kit knows'}, not this machine "
                                     f"({want}); left alone")
    if mine:
        p = newest(mine)
        z = inspect_zip(p)
        if z.problem or z.os != want:
            env.add("SDK zip", "FAIL", f"kit/sdk/{p.name}: {z.problem or f'its contents are for {z.os}, not {want}'}",
                    f"the {want} zip from Sony's page")
            return None, 2
        env.add("SDK zip", "OK", f"kit/sdk/{p.name}: Sony's SDK v{z.version} for {want}, checked by its contents")
        return z, 0
    if env.crsdk.is_dir():
        env.add("SDK zip", "OK", "no zip in kit/sdk/; using kit/sdk/SimpleCli/, already unpacked")
        return None, 0
    env.add("SDK zip", "FAIL", f"no SDK zip for {want} in kit/sdk/", f"put CrSDK_v<version>_<date>_{want}.zip into kit/sdk/")
    get_it(env)
    return None, 2


# ---------------------------------------------------------------- 2. unpacking, into kit/sdk/ only

def is_link(info: zipfile.ZipInfo) -> bool:
    return info.create_system == 3 and stat.S_ISLNK(info.external_attr >> 16)


def crc32(path: Path) -> int:
    crc = 0
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            crc = zlib.crc32(block, crc)
    return crc


def extract(zf: zipfile.ZipFile, dest: Path, limit: Path, skip_same: bool = False, dry: bool = False) -> tuple[list, int]:
    """Every entry of zf into dest, inside limit: (the entries written, the number kept). Any entry that is absolute
    or climbs out, or a link that points out of its folder, refuses the whole archive before anything is written.
    With skip_same, a file already there with the same size and CRC (a link: the same target) is kept. With dry,
    nothing is written."""
    infos = zf.infolist()
    links = {}
    for i in infos:
        if unsafe(i.filename) or not inside(dest / i.filename, limit):
            raise Refused(i.filename)
        if is_link(i):
            target = zf.read(i).decode("utf-8", "replace")
            if unsafe(target) or "/" in target or "\\" in target:
                raise Refused(f"{i.filename} -> {target}")
            links[i.filename] = target
    written, kept = [], 0
    for i in infos:
        out = dest / i.filename
        if i.is_dir():
            if not dry:
                out.mkdir(parents=True, exist_ok=True)
            continue
        if skip_same:
            if i.filename in links and os.name != "nt":      # a link: the same target
                same = out.is_symlink() and os.readlink(out) == links[i.filename]
            else:
                same = (out.is_file() and not out.is_symlink() and out.stat().st_size == i.file_size
                        and crc32(out) == i.CRC)
            if same:
                kept += 1
                continue
        written.append(i.filename)
        if dry:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if not inside(out, limit):                     # a link already on disk would carry it out
            raise Refused(i.filename)
        if out.is_symlink() or out.is_file():
            out.unlink()
        if i.filename in links and os.name != "nt":
            os.symlink(links[i.filename], out)
            continue
        with zf.open(i) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        mode = (i.external_attr >> 16) & 0o777 if i.create_system == 3 else 0
        if mode:
            os.chmod(out, (mode | 0o600) & 0o755)
    return written, kept


def check_unpacked(env: Env) -> str:
    """What is missing from kit/sdk/SimpleCli/ for this machine, or ''."""
    simple = env.sdk / "SimpleCli"
    need = ["app/CRSDK/CameraRemote_SDK.h", "app/CrDebugString.cpp", "external/crsdk/CrAdapter",
            f"external/crsdk/{CR_CORE[env.os_tag]}"]
    missing = [n for n in need if not (simple / n).exists()]
    if missing:
        return "kit/sdk/SimpleCli/ has no " + ", ".join(missing)
    if env.windows and not (env.crsdk / "Cr_Core.lib").exists():
        return "kit/sdk/SimpleCli/ has no external/crsdk/Cr_Core.lib"

    def head(name):
        with open(env.crsdk / name, "rb") as f:
            return f.read(20)
    tag = lib_os({p.name for p in env.crsdk.iterdir()}, head)
    if tag != env.os_tag:
        return f"kit/sdk/SimpleCli/ holds Sony's SDK for {tag or 'no OS the kit knows'}, not {env.os_tag}"
    return ""


def used(folder: str, entry: str) -> bool:
    """Whether an entry of an inner zip is one the kit uses: in SimpleCli/ the headers and sources it builds with
    (app/) and the libraries (external/crsdk/); the API reference and Driver/ whole."""
    return not (folder == "SimpleCli" and not entry.startswith(("app/", "external/crsdk/")))


def step_unpack(env: Env, z: SdkZip | None) -> bool:
    """The zip's files into kit/sdk/, then its inner zips into their folders, each file written only when the one
    there differs (size and CRC). The state rests only on the files the kit uses (used()); the zip's other files are
    written too, and only counted. True when SimpleCli/'s headers or libraries were written (the builds then start
    clean)."""
    sdk, would, unpacked, other = env.sdk, [], [], []

    def inner(name, src):
        folder = INNER.get(name) or name[:-len(".zip")]
        with zipfile.ZipFile(src) as zf:
            written, _ = extract(zf, sdk / folder, sdk, skip_same=not env.force, dry=env.check)
        if not any(used(folder, n) for n in written):
            other.extend(written)
        elif env.check:
            would.append(f"{name} into {folder}/")
        else:
            unpacked.append(folder + "/")

    try:
        if z is not None:                            # every inner zip, read from Sony's zip itself
            if not env.check:
                note(f"comparing {z.path.name} with kit/sdk/ and writing what differs ...")
            with zipfile.ZipFile(z.path) as outer:
                written, _ = extract(outer, sdk, sdk, skip_same=not env.force, dry=env.check)
                other.extend(written)
                for name in sorted(n for n in outer.namelist() if n in INNER or API_RE.match(n)):
                    inner(name, io.BytesIO(outer.read(name)))
        elif sdk.is_dir():                           # no zip: an inner zip already in kit/sdk/, when its folder is not
            for name in sorted(n for n in os.listdir(sdk) if n in INNER or API_RE.match(n)):
                if env.force or not (sdk / (INNER.get(name) or name[:-len(".zip")])).is_dir():
                    inner(name, sdk / name)
    except Refused as e:
        env.add("SDK unpacked", "FAIL", f"refused: the entry {e} would land outside kit/sdk/; nothing of it was written",
                "the zip from Sony's page, as downloaded")
        return False
    except (zipfile.BadZipFile, OSError) as e:
        env.add("SDK unpacked", "FAIL", f"could not unpack: {e}", f"{env.me} --force")
        return False
    if would:
        env.sdk_pending = True
        env.add("SDK unpacked", "DO", "would unpack " + "; ".join(would) + f": {env.me}", env.me)
        note("Sony's SDK is used under Sony's agreement: it stays in kit/sdk/ and is never committed or shared.")
        return False
    if not env.check and not env.crsdk.is_dir():
        env.add("SDK unpacked", "FAIL", "kit/sdk/SimpleCli/ is missing: unpack the SDK zip (docs/PORTING.md)",
                f"put the SDK zip into kit/sdk/; {env.me}")
        return False
    problem = check_unpacked(env) if env.crsdk.is_dir() else "kit/sdk/SimpleCli/ is missing"
    if problem:
        env.add("SDK unpacked", "FAIL", f"{problem}; put Sony's {env.os_tag} zip into kit/sdk/ and run {env.me} --force",
                f"{env.me} --force")
        return False
    env.sdk_ok = True
    folders = sorted(p.name + "/" for p in sdk.iterdir() if p.is_dir() and (p.name in INNER.values()
                                                                             or p.name.startswith("CrSDK_API_Reference_v")))
    if unpacked:
        what = "unpacked " + ", ".join(unpacked) + (f" from {z.path.name}" if z is not None else "") + " into kit/sdk/"
    elif z is not None:
        what = f"{z.path.name} is already unpacked in kit/sdk/ ({', '.join(folders)}); kept as it is"
    else:
        what = "already in kit/sdk/: " + ", ".join(folders)
    if other:
        what += (f"; a run also writes {len(other)} other files of the zip" if env.check else
                 f"; {len(other)} other files of the zip written") + ", which the kit does not use"
    env.add("SDK unpacked", "OK", what)
    note("Sony's SDK is used under Sony's agreement: it stays in kit/sdk/ and is never committed or shared.")
    if not any(f.startswith("CrSDK_API_Reference_v") for f in folders):
        env.add("API reference", "DO", "kit/sdk/ has no CrSDK_API_Reference_v<version>/, which kit/tools/sdk_support.py "
                f"reads for the body check: put Sony's SDK zip into kit/sdk/ and run {env.me}", env.me)
    return "SimpleCli/" in unpacked


# ---------------------------------------------------------------- 3. the tools

def tool_version(cmd: list) -> str:
    code, out = run(cmd)
    return out.strip().splitlines()[0] if code == 0 and out.strip() else ""


def install_hint(env: Env, mac: str, apt: str, win: str, other: str) -> str:
    if env.system == "Darwin":
        return mac if which("brew") or not mac.startswith("brew ") else other
    if env.windows:
        return win
    return apt if which("apt-get") else other


def vswhere_path() -> Path:
    """vswhere.exe, which the Visual Studio Installer keeps, and which says where Visual Studio's C++ tools are."""
    return Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"  # noqa: SIM112 (Windows reads names case-blind)


def step_tools(env: Env) -> None:
    t = env.tools
    v = sys.version_info
    env.add("Python", "OK", f"{v.major}.{v.minor}.{v.micro} ({sys.executable})")
    # cmake
    t["cmake"] = False
    low = (3, 21) if env.windows else (3, 16)
    get = install_hint(env, "brew install cmake", "sudo apt install cmake", "winget install Kitware.CMake",
                       "install CMake from https://cmake.org/download/")
    if which("cmake"):
        ver = tool_version(["cmake", "--version"])
        found = version_key(ver)[:2]
        if found and found < low:
            env.add("cmake", "DO", f"{ver} is older than {low[0]}.{low[1]}; install a newer one: {get}", get, blocking=True)
        else:
            t["cmake"] = True
            env.add("cmake", "OK", ver or "found")
    else:
        env.add("cmake", "DO", f"not found; install it: {get}", get, blocking=True)
    # a C++ compiler
    t["cxx"] = False
    if env.system == "Darwin":
        code, out = run(["xcode-select", "-p"])
        if code == 0:
            t["cxx"] = True
            env.add("C++ compiler", "OK", f"Xcode command line tools ({out.strip()})")
        else:
            env.add("C++ compiler", "DO", "the Xcode command line tools are missing; install them: xcode-select --install",
                    "xcode-select --install", blocking=True)
    elif env.windows:
        vs = ""
        if which("cl"):
            vs = "cl on the PATH"
        else:
            where = vswhere_path()
            if where.exists():
                code, out = run([where, "-latest", "-products", "*", "-requires",
                                 "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"])
                vs = out.strip().splitlines()[0] if code == 0 and out.strip() else ""
        if vs:
            t["cxx"] = True
            env.add("C++ compiler", "OK", f"Visual Studio C++ tools ({vs})")
        else:
            get = ('winget install Microsoft.VisualStudio.2022.Community --override '
                   '"--add Microsoft.VisualStudio.Workload.NativeDesktop --includeRecommended --passive"')
            env.add("C++ compiler", "DO", "Visual Studio 2022 or 2026 with the C++ workload is missing; install it: " + get,
                    get, blocking=True)
    else:
        cxx = next((c for c in ("c++", "g++", "clang++") if which(c)), None)
        if cxx:
            t["cxx"] = True
            env.add("C++ compiler", "OK", f"{cxx} ({which(cxx)})")
        else:
            get = install_hint(env, "", "sudo apt install build-essential", "",
                               "install g++ (or clang++) and make with your distribution's packages")
            env.add("C++ compiler", "DO", f"not found; install one: {get}", get, blocking=True)
    # the OS packages (Linux)
    if env.system == "Linux":
        step_packages(env)
    # cargo, for the editor
    t["cargo"] = bool(which("cargo"))
    rustup = ("winget install Rustlang.Rustup" if env.windows
              else "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
    if t["cargo"]:
        env.add("cargo", "OK", tool_version(["cargo", "--version"]) or "found")
    elif env.editor:
        env.add("cargo", "DO", f"not found; the editor needs Rust: {rustup}", rustup, blocking=True)
    else:
        env.add("cargo", "--", f"not found; needed only with --editor (Rust: {rustup})", "only for --editor")
    # ffmpeg, for a capture dongle
    if which("ffmpeg"):
        env.add("ffmpeg", "OK", "found (for an HDMI capture dongle)")
    else:
        get = install_hint(env, "brew install ffmpeg", "sudo apt install ffmpeg", "winget install Gyan.FFmpeg",
                           "install ffmpeg 5.1 or later")
        env.add("ffmpeg", "--", f"not found; needed only with an HDMI capture dongle: {get}", "only for a dongle")


def step_packages(env: Env) -> None:
    want = dict(PACKAGES)
    if env.editor:
        want.update(EDITOR_PACKAGES)
    if not which("pkg-config"):
        get = install_hint(env, "", "sudo apt install pkg-config", "", "install pkg-config")
        env.add("OS packages", "DO", f"pkg-config is missing, so they cannot be checked: {get}", get, blocking=env.editor)
        return
    missing = [name for name in want if run(["pkg-config", "--exists", name])[0] != 0]
    if not missing:
        env.add("OS packages", "OK", "found: " + ", ".join(want))
        return
    apt = "sudo apt install " + " ".join(want[n] for n in missing)
    get = apt if which("apt-get") else "install your distribution's packages for: " + ", ".join(missing)
    env.add("OS packages", "DO", f"missing {', '.join(missing)}; install them: {get}", get,
            blocking=any(n in EDITOR_PACKAGES for n in missing))


# ---------------------------------------------------------------- 4. libxml2.so.2 on Linux

def ldconfig_has(out: str, machine: str) -> bool:
    """Whether `ldconfig -p` lists a libxml2.so.2 for this CPU."""
    cpu = LDCONFIG_CPU.get(machine.lower())
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("libxml2.so.2 "):
            flags = s[len("libxml2.so.2 "):].split("=>")[0]
            if cpu is None or cpu in flags:
                return True
    return False


def libxml2_needed(env: Env, ldconfig_out: str | None) -> bool:
    """Linux only: no libxml2.so.2 on the system (ldconfig) and none beside the SDK's libraries."""
    if env.system != "Linux" or (env.crsdk / "libxml2.so.2").exists():
        return False
    return not (ldconfig_out and ldconfig_has(ldconfig_out, env.machine))


def ldconfig() -> str | None:
    exe = which("ldconfig") or next((p for p in ("/sbin/ldconfig", "/usr/sbin/ldconfig") if Path(p).exists()), None)
    if not exe:
        return None
    code, out = run([exe, "-p"])
    return out if code == 0 else None


def download(url: str, dest: Path, sha256: str) -> str:
    """url into dest, kept only when its SHA-256 is sha256; '' or what went wrong."""
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(part, "wb") as f:
            for block in iter(lambda: r.read(1 << 20), b""):
                h.update(block)
                f.write(block)
    except OSError as e:
        part.unlink(missing_ok=True)
        return f"could not download {url}: {e}"
    if h.hexdigest() != sha256:
        part.unlink()
        return f"{url}: SHA-256 {h.hexdigest()}, expected {sha256}; not used"
    part.replace(dest)
    return ""


def untar(tarball: Path, dest: Path) -> None:
    with tarfile.open(tarball) as t:
        for m in t.getmembers():
            if unsafe(m.name) or not (m.isfile() or m.isdir()):
                raise Refused(m.name)
        if hasattr(tarfile, "data_filter"):
            t.extractall(dest, filter="data")
        else:
            t.extractall(dest)


def step_libxml2(env: Env) -> None:
    if env.system != "Linux" or not env.sdk_ok:
        return
    if (env.crsdk / "libxml2.so.2").exists():
        env.add("libxml2.so.2", "OK", "beside the SDK's libraries (kit/sdk/SimpleCli/external/crsdk/)")
        return
    if not libxml2_needed(env, ldconfig()):
        env.add("libxml2.so.2", "OK", "the system's (ldconfig -p)")
        return
    why = "Sony's libCr_Core.so needs libxml2.so.2, which this system lacks (Ubuntu 25.10 and later ship libxml2.so.16)"
    build, prefix = env.sdk / ".build", env.sdk / ".build" / "libxml2-2.13"
    if env.check:
        env.add("libxml2.so.2", "DO", f"would build libxml2 2.13.9 in kit/sdk/.build/ and copy it beside the SDK's "
                f"libraries, because {why}: {env.me}", env.me)
        return
    if not (prefix / "lib" / "libxml2.so.2").exists() or env.force:
        if not (which("make") and (which("cc") or which("gcc"))):
            get = install_hint(env, "", "sudo apt install build-essential", "", "install make and a C compiler")
            env.add("libxml2.so.2", "DO", f"{why}; building it needs make and a C compiler: {get}", get, blocking=True)
            return
        build.mkdir(parents=True, exist_ok=True)
        tarball = build / "libxml2-2.13.9.tar.xz"
        if not tarball.exists() or hashlib.sha256(tarball.read_bytes()).hexdigest() != LIBXML2_SHA256:
            note(f"downloading {LIBXML2_URL} ...")
            problem = download(LIBXML2_URL, tarball, LIBXML2_SHA256)
            if problem:
                env.add("libxml2.so.2", "FAIL", problem, "docs/PORTING.md, Linux, libxml2 (by hand)")
                return
        src = build / "libxml2-2.13.9"
        try:
            if not (src / "configure").exists() or env.force:
                untar(tarball, build)
        except (Refused, tarfile.TarError, OSError) as e:
            env.add("libxml2.so.2", "FAIL", f"could not unpack {tarball.name}: {e}", "docs/PORTING.md, Linux, libxml2")
            return
        note("building libxml2 2.13.9 (a minute or two) ...")
        for cmd in (["./configure", f"--prefix={prefix}", *LIBXML2_FLAGS], ["make", f"-j{os.cpu_count() or 2}"],
                    ["make", "install"]):
            code, out = run(cmd, cwd=src)
            if code:
                env.add("libxml2.so.2", "FAIL", f"{shown(cmd)} failed (exit {code}) in kit/sdk/.build/libxml2-2.13.9/",
                        "docs/PORTING.md, Linux, libxml2 (by hand)")
                tail(out)
                return
    for p in sorted((prefix / "lib").glob("libxml2.so.2*")):
        out = env.crsdk / p.name
        if out.is_symlink() or out.exists():
            out.unlink()
        if p.is_symlink():
            os.symlink(os.readlink(p), out)
        else:
            shutil.copy2(p, out)
    if not (env.crsdk / "libxml2.so.2").exists():
        env.add("libxml2.so.2", "FAIL", f"the build made no libxml2.so.2 in {env.rel(prefix / 'lib')}",
                "docs/PORTING.md, Linux, libxml2 (by hand)")
        return
    env.add("libxml2.so.2", "OK", f"built libxml2 2.13.9 (SHA-256 checked) and copied libxml2.so.2 beside the SDK's "
            f"libraries, because {why}")


# ---------------------------------------------------------------- 5. .venv and the hooks

def venv_python(env: Env, current: tuple | None = None) -> tuple[str, str]:
    """The Python to make .venv with, and a word on why when it is not the one running this script."""
    current = current or tuple(sys.version_info[:2])
    if current <= NEWEST_PY:
        return sys.executable, ""
    why = f"the kit's packages (onnxruntime) have no build for Python {current[0]}.{current[1]} yet"
    for minor in range(NEWEST_PY[1], 10, -1):
        if env.windows and which("py"):
            code, out = run(["py", f"-3.{minor}", "-c", "import sys; print(sys.executable)"])
            if code == 0 and out.strip():
                return out.strip().splitlines()[-1], f"Python 3.{minor}: {why}"
        elif which(f"python3.{minor}"):
            return which(f"python3.{minor}"), f"python3.{minor}: {why}"
    return sys.executable, ""


def newer_python_hint(env: Env, ver: str) -> str:
    want = f"{NEWEST_PY[0]}.{NEWEST_PY[1]}"
    get = install_hint(env, f"brew install python@{want}", f"sudo apt install python{want} python{want}-venv",
                       f"winget install Python.Python.{want}", f"install Python {want} from python.org")
    return (f"pip found no build of a package for .venv's Python {ver} (onnxruntime lags new Pythons): move .venv "
            f"aside (mv .venv .venv.old) and run {env.me} again, which makes it with Python {want} or older when one "
            f"is installed ({get})")


def step_venv(env: Env) -> None:
    venv, py = env.root / ".venv", env.venv_bin("python")
    if not py.exists():
        if venv.exists():
            env.add("venv", "DO", f".venv has no Python in it: move it aside (mv .venv .venv.old) and run {env.me}",
                    "mv .venv .venv.old", blocking=True)
            return
        if env.check:
            env.add("venv", "DO", f"would make .venv and install kit/requirements.txt: {env.me}", env.me)
            step_hooks(env)
            return
        exe, why = venv_python(env)
        note(f"making .venv{' with ' + why if why else ''} ...")
        code, out = run([exe, "-m", "venv", venv], cwd=env.root)
        if code:
            shutil.rmtree(venv, ignore_errors=True)      # the half-made one, from this run
            if "ensurepip" in out or "python3-venv" in out:
                env.add("venv", "DO", "Python's venv module is missing: sudo apt install python3-venv",
                        "sudo apt install python3-venv", blocking=True)
            else:
                env.add("venv", "FAIL", f"{exe} -m venv .venv failed (exit {code})", "the output above")
            tail(out)
            return
    code, out = run([py, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    ver = out.strip() if code == 0 else "?"
    if code or version_key(ver) < (3, 11):
        env.add("venv", "DO", f".venv's Python ({ver}) is older than 3.11 or broken: move it aside (mv .venv .venv.old) "
                f"and run {env.me}", "mv .venv .venv.old", blocking=True)
        return
    env.add("venv", "OK", f".venv (Python {ver})")
    if env.windows and os.environ.get("PYTHONUTF8") != "1":
        # the kit refuses to run on Windows without UTF-8 mode (camkit/__init__.py): its text is UTF-8, cp1252 is not
        env.add("UTF-8 mode", "DO", "the kit runs in Python's UTF-8 mode on Windows: setx PYTHONUTF8 1, then open a "
                "new terminal", "setx PYTHONUTF8 1")
    if env.check:
        env.add("packages", "--", "not checked with --check; a run installs kit/requirements.txt", env.me)
    else:
        note("installing kit/requirements.txt into .venv (some minutes the first time) ...")
        code, out = run([py, "-m", "pip", "install", "-q", "-r", "kit/requirements.txt"], cwd=env.root)
        if code:
            env.add("packages", "FAIL", f"pip install -r kit/requirements.txt failed (exit {code})", "the output above")
            tail(out)
            if version_key(ver)[:2] > NEWEST_PY and ("No matching distribution" in out or "ResolutionImpossible" in out):
                env.add("packages", "DO", newer_python_hint(env, ver), "mv .venv .venv.old", blocking=True)
            env.add("hooks", "--", "wait for the packages (pre-commit is one of them)", env.me)
            return
        env.add("packages", "OK", "kit/requirements.txt installed in .venv")
    step_hooks(env)


def step_hooks(env: Env) -> None:
    git = env.root / ".git"
    if not git.exists():
        env.add("hooks", "--", "not a git clone; no pre-commit hooks")
    elif (git / "hooks" / "pre-commit").exists():
        env.add("hooks", "OK", "pre-commit hooks installed")
    elif env.check:
        env.add("hooks", "DO", f"would install the pre-commit hooks: {env.me}", env.me)
    else:
        code, out = run([env.venv_bin("pre-commit"), "install"], cwd=env.root)
        if code:
            get = f"{env.rel(env.venv_bin('pre-commit'))} install"
            env.add("hooks", "DO", f"pre-commit install failed (exit {code}); run it yourself: {get}", get)
            tail(out)
        else:
            env.add("hooks", "OK", "pre-commit hooks installed")


# ---------------------------------------------------------------- 6. the builds

def beside(env: Env, exe: Path) -> bool:
    """The SDK's Cr_Core library sits beside a built program, as its build copies it."""
    return (exe.parent / CR_CORE[env.os_tag]).exists()


def mtime(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def outcome(before: int | None, out: Path) -> str:
    """'built' when the build wrote the program, 'up to date' when its own check found nothing to do: the program's
    time is the one way to tell that is the same for make, ninja, MSBuild and cargo."""
    return "up to date" if before is not None and mtime(out) == before else "built"


def step_cmake(env: Env, piece: str, folder: str, name: str, rebuild: bool) -> None:
    """Configured and built on every run: cmake rebuilds only what changed (a pull that changes the source, a newer
    SDK). rebuild (--force, or SimpleCli/ unpacked afresh) builds from clean (--clean-first), as does a program without
    the SDK's libraries beside it, since its build copies them only when it links."""
    src = env.root / folder
    out = built(src / "build", name, env.system)
    there = out.exists() and beside(env, out)
    if env.check:
        if there and not rebuild:
            env.add(piece, "OK", f"built ({env.rel(out)}); a run rebuilds it if its sources changed "
                                 "(cmake --build, incremental)")
            return
        later = "" if (env.sdk_ok or env.sdk_pending) and env.tools.get("cmake") and env.tools.get("cxx") else \
            " once the tools above are in place"
        again = env.me + (" --force" if env.force else "")
        how = "rebuild" if out.exists() else "build"
        env.add(piece, "DO", f"would {how} {env.rel(out)}{' from clean' if out.exists() else ''}{later}: {again}", again)
        return
    needs = [w for w, ok in (("the SDK", env.sdk_ok), ("cmake", env.tools.get("cmake")),
                             ("a C++ compiler", env.tools.get("cxx"))) if not ok]
    if needs:
        old = f"; {env.rel(out)} is from an earlier build" if out.exists() else ""
        env.add(piece, "FAIL", f"not built: it needs {' and '.join(needs)} (above){old}", "the lines above")
        return
    clean = rebuild or (out.exists() and not there)
    before = mtime(out) if there else None
    note(f"building {folder} ({'from clean' if clean else 'only what changed'}) ...")
    configure = ["cmake", "-S", folder, "-B", f"{folder}/build"]
    code, log = run(configure, cwd=env.root)
    if code:
        env.add(piece, "FAIL", f"{shown(configure)} failed (exit {code})", "the output above")
        tail(log)
        if env.windows:
            hint = f"cmake -S {folder} -B {folder}/build -A x64 -T v143,host=x64"
            env.add(piece, "DO", f"with Visual Studio 2022, clear the build (cmake -E rm -rf {folder}/build), configure "
                    f"it by hand once ({hint}), then run {env.me} again", hint, blocking=True)
        return
    cmd = ["cmake", "--build", f"{folder}/build", "--config", "Release"] + (["--clean-first"] if clean else [])
    code, log = run(cmd, cwd=env.root)
    out = built(src / "build", name, env.system)
    if code or not out.exists():
        env.add(piece, "FAIL", f"{shown(cmd)} failed (exit {code})", "the output above")
        tail(log)
        return
    env.add(piece, "OK", f"{outcome(before, out)} ({env.rel(out)})")


def step_ocr(env: Env, rebuild: bool) -> None:
    """macOS: swiftc has no check of its own, so the helper is built when it is missing, when kit/ocr/ocr.swift is
    newer than it (a pull that changed it) or with --force."""
    if env.system != "Darwin":
        return
    src, out = env.root / "kit" / "ocr" / "ocr.swift", env.root / "kit" / "ocr" / "build" / "ocr"
    stale = out.exists() and (mtime(src) or 0) > (mtime(out) or 0)
    if out.exists() and not stale and not rebuild:
        env.add("OCR helper", "OK", f"up to date ({env.rel(out)}, newer than {env.rel(src)})")
        return
    if env.check:
        why = f", older than {env.rel(src)}" if stale else " (--force)" if out.exists() else ""
        again = env.me + (" --force" if env.force else "")
        env.add("OCR helper", "DO", f"would {'rebuild' if out.exists() else 'build'} {env.rel(out)}{why}: {again}",
                again)
        return
    if not env.tools.get("cxx"):
        env.add("OCR helper", "FAIL", "not built: it needs the Xcode command line tools (above)", "xcode-select --install")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["swiftc", "-O", "kit/ocr/ocr.swift", "-o", "kit/ocr/build/ocr"]
    note("building kit/ocr ...")
    code, log = run(cmd, cwd=env.root)
    if code or not out.exists():
        env.add("OCR helper", "FAIL", f"{shown(cmd)} failed (exit {code})", "the output above")
        tail(log)
        return
    env.add("OCR helper", "OK", f"built ({env.rel(out)})" + (f", as {env.rel(src)} was newer" if stale else ""))


def step_editor(env: Env, rebuild: bool) -> None:
    """With --editor, cargo build --release on every run: cargo rebuilds only what changed. --force first removes the
    editor's own compiled crate (cargo clean -p camset-editor --release), so it is compiled again; the libraries it
    uses are kept."""
    out = built(env.root / "editor" / "target" / "release", "camset_editor", env.system)
    again = f"{env.me} --editor"
    if not env.editor:
        if out.exists():
            env.add("editor", "--", f"not asked for; {env.rel(out)} is from an earlier build: {again} rebuilds it if its "
                    "sources changed", again)
        else:
            env.add("editor", "--", f"not asked for; {again} builds it", again)
        return
    if env.check:
        if out.exists() and not rebuild:
            env.add("editor", "OK", f"built ({env.rel(out)}); a run with --editor rebuilds it if its sources changed "
                                    "(cargo build --release, incremental)")
        else:
            again += " --force" if rebuild else ""
            how = "rebuild" if out.exists() else "build"
            env.add("editor", "DO", f"would {how} {env.rel(out)}{' from clean' if out.exists() else ''}: {again}", again)
        return
    if not env.tools.get("cargo"):
        old = f"; {env.rel(out)} is from an earlier build" if out.exists() else ""
        env.add("editor", "FAIL", f"not built: it needs cargo (above){old}", "install Rust (above)")
        return
    editor, before = env.root / "editor", mtime(out)
    if rebuild:
        clean = ["cargo", "clean", "-p", "camset-editor", "--release"]
        code, log = run(clean, cwd=editor)
        if code:
            env.add("editor", "FAIL", f"{shown(clean)} failed (exit {code}) in editor/", "the output above")
            tail(log)
            return
    note("building the editor (cargo build --release: only what changed; some minutes the first time) ...")
    code, log = run(["cargo", "build", "--release"], cwd=editor)
    out = built(editor / "target" / "release", "camset_editor", env.system)
    if code or not out.exists():
        env.add("editor", "FAIL", f"cargo build --release failed (exit {code}) in editor/", "the output above")
        tail(log)
        return
    env.add("editor", "OK", f"{outcome(before, out)} ({env.rel(out)})")


# ---------------------------------------------------------------- 7. camera access

def step_access(env: Env) -> None:
    if env.system == "Darwin":
        env.add("camera access", "OK", "nothing to install on macOS (the link stops ptpcamerad before each attempt)")
    elif env.windows:
        inf = env.sdk / "Driver" / "srcameradriver.inf"
        get = r"pnputil /add-driver kit\sdk\Driver\srcameradriver.inf /install"
        if inf.exists():
            env.add("camera access", "DO", f"Sony's USB driver, once per PC, in a prompt run as administrator: {get}", get)
        else:
            env.add("camera access", "DO", r"Sony's USB driver is not in kit\sdk\Driver\: put Sony's Win64 zip into "
                    f"kit\\sdk\\ and run {env.me}; then, as administrator, once per PC: {get}", get)
    elif env.system == "Linux":
        get = (f"echo '{UDEV_LINE}' | sudo tee {UDEV_RULE} && sudo udevadm control --reload-rules "
               "&& sudo udevadm trigger")
        try:
            had = UDEV_RULE.read_text(encoding="utf-8") if UDEV_RULE.exists() else None
        except OSError:
            had = ""
        if had is None:
            env.add("camera access", "DO", f"if a normal user cannot see the camera over USB, a udev rule: {get}", get)
        elif "0666" in had:
            env.add("camera access", "DO", f"{UDEV_RULE} opens the camera to every local user (MODE=\"0666\"); to the "
                    f"user at the seat only: {get}", get)
        else:
            env.add("camera access", "OK", f"{UDEV_RULE} is there")
        try:
            mb = int(USBFS.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            mb = None
        if mb is not None and 0 < mb < 150:
            env.add("USB buffer", "--", f"usbfs_memory_mb is {mb}; Sony asks for 150: add usbcore.usbfs_memory_mb=150 to "
                    "GRUB_CMDLINE_LINUX_DEFAULT in /etc/default/grub, run sudo update-grub and reboot",
                    "docs/PORTING.md, Linux, USB buffer")


# ---------------------------------------------------------------- 8. the tests

def summary(output: str) -> str:
    """'N passed, M skipped' from pytest's last line."""
    counts = re.findall(r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)", output.strip().splitlines()[-1]
                        if output.strip() else "")
    return ", ".join(f"{n} {w}" for n, w in counts) or "no summary"


def step_tests(env: Env) -> None:
    if env.check:
        env.add("tests", "--", "not run with --check", env.me)
        return
    py = env.venv_bin("python")
    if not py.exists():
        env.add("tests", "FAIL", "not run: there is no .venv (above)", "the venv line above")
        return
    note("running the kit's tests (under a minute) ...")
    code, out = run([py, "-X", "utf8", "-m", "pytest", "kit/tests", "-q"], cwd=env.root)
    if code:
        env.add("tests", "FAIL", f"{summary(out)} (exit {code})", "the output above; docs/PORTING.md, First day, step 1")
        tail(out)
        return
    env.add("tests", "OK", summary(out))


# ---------------------------------------------------------------- 9. the proof viewer

VIEWER_NO_RUNS = 3          # kit/tools/proof_viewer.py's exit status when the camera has no runs here (its NO_RUNS)


def step_viewer(env: Env) -> None:
    """runs/<model>_fw<fw>/_viewer/index.html where the kit has run on the active camera, with its frames; none in a
    fresh clone (2026-11-06, the owner: "Proof view shouldn't be available if the kit has never been run on a
    camera"), where proof_viewer.py refuses and says why. Never --pack (that copies thousands of frames) and never
    --open. Optional: a refused or failed build is a "--" with its reason, so it fails nothing."""
    if env.check:
        env.add("proof viewer", "--", "not built with --check", env.me)
        return
    py = env.venv_bin("python")
    if not py.exists():
        env.add("proof viewer", "--", "not built: there is no .venv (above)", "the venv line above")
        return
    note("building the proof viewer page, if the kit has run on a camera here ...")
    code, out = run([py, env.root / "kit" / "tools" / "proof_viewer.py"], cwd=env.root)
    lines = out.strip().splitlines()
    if code == VIEWER_NO_RUNS:          # "No proof viewer for <camera>: <why>. <what would make it available>"
        said = lines[-1].strip() if lines else ""
        note(said)
        why = said.split(": ", 1)[-1].split(". ", 1)[0].rstrip(".")
        env.add("proof viewer", "--", f"not built: {why}",
                "none: it shows your camera's own screens once the kit has run on it (the line above)")
        return
    if code or not lines:
        why = lines[-1].strip() if lines else "no output"
        env.add("proof viewer", "--", f"not built: kit/tools/proof_viewer.py failed (exit {code}): {why}",
                "the output above")
        tail(out)
        return
    page = env.rel(Path(lines[-1].strip()))
    env.add("proof viewer", "OK", f"built ({page})", f"open {page} in a browser")


# ---------------------------------------------------------------- the table, and main

def table(rows: list) -> str:
    head = ("Piece", "State", "What next")
    seen, cells = set(), []
    for r in rows:                                   # one line per piece: the last word on it
        if r.piece in seen:
            cells = [c for c in cells if c[0] != r.piece]
        seen.add(r.piece)
        cells.append((r.piece, r.state, r.next))     # "-" for an OK row, unless it names something to open
    w0 = max(len(head[0]), *(len(c[0]) for c in cells)) if cells else len(head[0])
    w1 = max(len(head[1]), *(len(c[1]) for c in cells)) if cells else len(head[1])
    lines = [f"{head[0]:<{w0}}  {head[1]:<{w1}}  {head[2]}", f"{'-' * w0}  {'-' * w1}  {'-' * 9}"]
    lines += [f"{a:<{w0}}  {b:<{w1}}  {c}" for a, b, c in cells]
    return "\n".join(lines)


def exit_code(rows: list, no_sdk: bool) -> int:
    if no_sdk:
        return 2
    return 1 if any(r.state == "FAIL" or (r.state == "DO" and r.blocking) for r in rows) else 0


def parse(argv: list | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="kit/setup.py",
        description="Set up the mapping kit: Sony's SDK zip, dropped into kit/sdk/, unpacked; the tools checked; .venv; "
                    "the camera link, the camera helper and (macOS) the OCR helper built; the tests run; the proof "
                    "viewer built where the kit has run on a camera.",
        epilog="Each step prints OK, DO (yours to do, with the command), FAIL or --, then a table. Exit status 0: "
               "nothing required missing; 1: something is; 2: no SDK zip. By hand: docs/PORTING.md, Setup per OS.")
    ap.add_argument("zip", nargs="?", metavar="SDK_ZIP",
                    help="Sony's CrSDK_v<version>_<date>_<OS>.zip (default: the newest for this machine in kit/sdk/)")
    ap.add_argument("--check", action="store_true", help="change nothing: say what is in place and what a run would do")
    ap.add_argument("--force", action="store_true",
                    help="unpack the SDK again and build from clean (cmake --build --clean-first; for the editor, "
                         "cargo clean -p camset-editor --release first)")
    ap.add_argument("--editor", action="store_true", help="also build the editor (cargo build --release in editor/)")
    return ap.parse_args(argv)


def main(argv: list | None = None, env: Env | None = None) -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 (says so under older Pythons)
        v = sys.version_info
        print(f"FAIL Python: {v[0]}.{v[1]}.{v[2]} ({sys.executable}); the kit needs Python 3.11 or newer.")
        print("DO   install Python 3.11 to 3.14 and run this again with it: on a Mac, brew install python@3.14, then "
              "python3.14 kit/setup.py; on Ubuntu 22.04, sudo apt install python3.11 python3.11-venv, then "
              "python3.11 kit/setup.py; on Windows, winget install Python.Python.3.14, then py -3.14 kit\\setup.py; "
              "or from python.org")
        return 1
    args = parse(argv)
    env = env or Env()
    env.check, env.force, env.editor = args.check, args.force, args.editor
    print(f"Camset kit setup in {env.root}" + (" (--check: nothing is changed)" if env.check else ""), flush=True)
    z, code = step_sdk(env, args.zip)
    rebuild = env.force
    if code != 2:
        rebuild = step_unpack(env, z) or rebuild
    step_tools(env)
    if code != 2:
        step_libxml2(env)
        step_venv(env)
        step_cmake(env, "link", "kit/link", "camlink", rebuild)
        step_cmake(env, "probe", "kit/probe", "camset_probe", rebuild)
        step_ocr(env, env.force)                    # neither of these two uses the SDK
        step_editor(env, env.force)
        step_access(env)
        step_tests(env)
        step_viewer(env)
    print("\n" + table(env.rows), flush=True)
    result = exit_code(env.rows, code == 2)
    if result == 0 and not env.check:
        print("\nThe kit is set up. Next: docs/QUICKSTART.md, the body check at the end of step 1 if not done yet, "
              "then step 2.")
    return result


if __name__ == "__main__":
    sys.exit(main())
