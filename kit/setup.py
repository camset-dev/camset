#!/usr/bin/env python3
"""The kit's setup command: Sony's SDK zip dropped into kit/sdk/, then one command sets up the rest.
(Not a setuptools file: the kit is run from the clone, never installed as a package.)

    python3 kit/setup.py [SDK_ZIP] [--check] [--force] [--editor]        (Windows: py kit\\setup.py ...)

The steps, in order. Each prints one line: OK (in place), DO (yours to do, with the exact command; one that needs
another window or administrator rights as numbered steps), FAIL (what and why), or -- (not asked for, or not run with
--check). It never waits for a DO: it carries on with the other steps and lists what is left at the end. A step that
can take more than a few seconds says so first, with a rough time, and shows a progress line while it runs:
 0. On Windows, Python's UTF-8 mode, without which no kit program starts: on with PYTHONUTF8=1, or with PYTHONUTF8
    not set when the kit's Python is 3.15 or newer (on by default there); off with PYTHONUTF8=0. A run stops here when
    it is off, with the three steps that turn it on.
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
 5. .venv with kit/requirements.txt (made with the newest installed Python the packages install on; one whose making
    was stopped is removed, and one without a working pip gets it back with ensurepip), and the pre-commit hooks.
 6. The builds: the camera link (kit/link), the editor's camera helper (kit/probe), on macOS the OCR helper
    (kit/ocr), and with --editor the editor. cmake and cargo are always run, as they rebuild only what changed, and
    each says "built" or "up to date"; the OCR helper is built again when kit/ocr/ocr.swift is newer than it. With
    --check, a program already there is OK and rebuilt on a run if its sources changed. --force builds from clean.
 7. Camera access: the udev rule on Linux; on Windows Sony's USB driver, found installed by pnputil /enum-drivers
    (no administrator rights needed), else the steps that install it as administrator.
 8. The kit's tests, in a temporary folder of the setup's own (tests_folder).
 9. The proof viewer, runs/<model>_fw<fw>/_viewer/index.html (the definition's camera's folder), built as
    kit/tools/build_docs.py builds it (no --pack, no --open), only where the kit has run on the camera the config
    names (camkit.paths): it shows that camera's own screens, so it is for whoever mapped their camera, never part of
    a submission. A fresh clone gets no page: proof_viewer.py refuses (exit status 3) and the line says why and what
    makes it available. A failed build is reported with its reason (the kit's runs from before per-camera folders:
    the command that moves them). Neither fails the setup.
Then a table: each piece, its state and what next; and the last words: everything is in place, or what is left for
you to do, numbered in order, and "Then run <this command> again". Ctrl+C stops it at any time; nothing is lost.
Exit status: 0 when nothing required is missing or failed, 1 when something is (on Windows, UTF-8 mode not on), 2 when
there is no SDK zip to use, 130 when stopped with Ctrl+C. Run one setup at a time, in one clone and on one computer:
two at once share the tests' scratch folder (tests_folder) and would empty it under each other.

Standard library only: it runs with the system's Python, before .venv exists. The same steps by hand are in
docs/PORTING.md, "Setup per OS". Sony's SDK is used under Sony's agreement: it stays in kit/sdk/, which git ignores
but for its README, and is never committed or shared (docs/RELEASING.md).
"""
from __future__ import annotations  # keeps this file readable by an old Python, so it can say it is too old

import argparse
import codecs
import contextlib
import hashlib
import io
import locale
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
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
# How long the long steps take, as the person is told before each starts, and when (seconds) its progress line says
# it is taking unusually long: a generous multiple, never a stop. The tests: 2133 in 3 min 12 s on an Apple M2 Max
# (2026-11-12, the full suite with the mapper's own evidence; a fresh clone skips some); on 2026-11-12 the first run on
# a Windows 11 PC was still going after several minutes, where the old hint said "under a minute". Windows' virus
# scanner checks every file written and every program started, and the tests start many Pythons.
LONGER = "a first run, a slower computer or a busy disk can take several times longer"
UNPACK_TIME, UNPACK_SLOW = f"usually under a minute; on Windows, where the virus scanner checks every file, a few minutes; {LONGER}", 20 * 60
VENV_TIME, VENV_SLOW = "usually under a minute", 10 * 60
PIP_TIME, PIP_SLOW = f"some minutes the first time, as it downloads the packages; seconds after; {LONGER}", 30 * 60
CMAKE_TIME, CMAKE_SLOW = f"usually 1 to 3 minutes the first time, seconds after; {LONGER}", 20 * 60
SWIFT_TIME, SWIFT_SLOW = "usually under a minute", 10 * 60
EDITOR_TIME, EDITOR_SLOW = f"usually 5 to 15 minutes the first time, as it compiles some hundred libraries; a minute or less after; {LONGER}", 60 * 60
TESTS_TIME, TESTS_SLOW = f"about 3 minutes on a fast computer, 5 to 15 minutes on many; {LONGER}", 30 * 60
VIEWER_TIME, VIEWER_SLOW = "seconds; a minute or two where the kit has run on a camera", 15 * 60
LIBXML2_TIME, LIBXML2_SLOW = f"a minute or two; {LONGER}", 20 * 60


class Refused(Exception):
    """A zip or tar entry that would land outside its folder."""


@dataclass
class Row:
    piece: str
    state: str                  # "OK", "DO", "FAIL" or "--"
    what: str
    next: str = "-"             # the table's "what next"
    blocking: bool = False      # a DO that stops the setup (a missing tool), not a reminder
    steps: list = field(default_factory=list)   # a DO's numbered steps, for one that needs another window or rights
    again: str = ""             # the step after them, when "Then run <me> again." is not enough (a new window)
    yours: bool = False         # a DO for the person, not one that only says what a run of the setup would do
    after: str = ""             # a last line after the numbered steps, unnumbered (that the old window may be closed)


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
    told_no_wait: bool = False  # the run has said it does not wait for a DO

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

    @property
    def move_aside(self) -> str:
        """The command that moves a broken .venv out of the way, in this system's words."""
        return "move .venv .venv.old" if self.windows else "mv .venv .venv.old"

    def rel(self, path: Path) -> str:
        try:
            return Path(path).relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def native(self, text: str) -> str:
        """A path to type, with this system's slashes: Command Prompt reads a / in a command as an option."""
        return text.replace("/", "\\") if self.windows else text

    def add(self, piece: str, state: str, what: str, next: str = "-", blocking: bool = False, steps: list | None = None,
            again: str = "", after: str = "") -> Row:
        yours = state == "DO" and not next.startswith(self.me)
        row = Row(piece, state, what, next, blocking, list(steps or []), again, yours, after)
        self.rows.append(row)
        print(f"{state:<4} {piece}: {what}", flush=True)
        if row.steps:
            for line in numbered(row.steps + [again or f"Then run {self.me} again."]):
                note(line)
            if after:
                note(after)
        if yours and not self.told_no_wait:
            self.told_no_wait = True
            note("(This setup does not wait for you to do that: it carries on with the other steps now, and lists "
                 "what is left for you at the end.)")
        return row


# ---------------------------------------------------------------- small helpers (the tests replace run and which)

def run(cmd: list, cwd: Path | None = None) -> tuple[int, str]:
    """A tool's exit code and its output, stdout and stderr together. Inside a long step (Progress), the output is
    read as it comes, so the step's progress line can show how far the tool is."""
    if PROGRESS is not None:
        return watched(cmd, cwd, PROGRESS)
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors="replace")
    except OSError as e:
        return 127, str(e)
    return p.returncode, p.stdout


def watched(cmd: list, cwd: Path | None, progress: Progress) -> tuple[int, str]:
    """run(), with the output handed to progress as it arrives. The pipe is read by a thread and this one waits in short
    sleeps, which Ctrl+C interrupts on Windows too. On Ctrl+C the progress line stops first (no "still running" while
    the tool stops), the tool gets a moment to stop on its own (Ctrl+C reached it too, as it shares the terminal), and
    then it and what it started are ended (stop_tree), even when a second Ctrl+C cuts that moment short; the setup
    stops."""
    try:
        p = subprocess.Popen([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as e:
        return 127, str(e)
    decode = codecs.getincrementaldecoder(locale.getpreferredencoding(False))(errors="replace")
    parts = []

    def read():
        for block in iter(lambda: p.stdout.read1(1 << 16), b""):
            text = decode.decode(block)
            parts.append(text)
            progress.feed(text)
        parts.append(decode.decode(b"", final=True))
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        while reader.is_alive():
            time.sleep(0.1)
        p.wait()
    except KeyboardInterrupt:
        progress.stop()
        with contextlib.suppress(subprocess.TimeoutExpired):
            p.wait(timeout=STOP_GRACE)
        raise
    finally:
        if p.poll() is None:                          # still running: Ctrl+C, and it did not stop in time
            stop_tree(p)
        reader.join(timeout=2)                        # the pipe ends with the tool, unless something it started holds it
        if not reader.is_alive():
            p.stdout.close()
    return p.returncode, "".join(parts).replace("\r\n", "\n")


STOP_GRACE = 5              # seconds a tool has to stop on its own after Ctrl+C, before it is ended


def tree_kill_command(pid: int) -> list:
    """Windows: the command that ends a program and every program it started (a stopped pytest's stand-in camera link
    and kit programs, MSBuild's compilers), which would otherwise go on holding files and temporary folders."""
    return ["taskkill", "/T", "/F", "/PID", str(pid)]


def stop_tree(p, windows: bool | None = None) -> None:
    """Ends a tool that did not stop on Ctrl+C. On Windows with taskkill, the whole tree (tree_kill_command); where
    taskkill is missing, fails or hangs, and elsewhere, the tool itself. On macOS and Linux the programs it started
    in the terminal's group got the terminal's Ctrl+C already (one in a session of its own, as the kit's camera link,
    ends when its input closes); the tool is not put in a group of its own, as then closing the terminal would no
    longer end it."""
    windows = os.name == "nt" if windows is None else windows
    if windows:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(tree_kill_command(p.pid), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    if p.poll() is None:
        p.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        p.wait(timeout=10)


def which(name: str) -> str | None:
    return shutil.which(name)


def note(text: str) -> None:
    print(f"     {text}", flush=True)


def numbered(steps: list) -> list:
    """'1. ...', '2. ...': a DO's steps as the person reads them."""
    return [f"{i}. {s}" for i, s in enumerate(steps, 1)]


# ---------------------------------------------------------------- progress: a long step shows it is alive

PROGRESS = None             # the long step running now (Progress), whose line run() feeds with the tool's output
PERCENT_RE = re.compile(r"\[\s*(\d{1,3})%\]")                  # pytest -q's "[ 43%]", make's "[ 43%] Building ..."
NINJA_RE = re.compile(r"^\[(\d+)/(\d+)\] ", re.M)              # ninja's "[12/40] Building ..."
CARGO_RE = re.compile(r"^\s*Compiling \S+ v", re.M)            # cargo's "   Compiling serde v1.0.219"


def elapsed_text(seconds: float) -> str:
    """'45 s', '1 min 05 s', '1 h 02 min'."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60:02d} s"
    return f"{s // 3600} h {s % 3600 // 60:02d} min"


def pytest_progress(output: str) -> str:
    """How far pytest -q is, from the percentage it prints at the end of each line of dots: '43 % done', or ''."""
    found = PERCENT_RE.findall(output)
    return f"{int(found[-1])} % done" if found else ""


def build_progress(output: str) -> str:
    """How far a build is: make's percentage, ninja's count or the crates cargo has compiled; '' for Visual Studio's
    MSBuild, which prints no count."""
    steps = NINJA_RE.findall(output)
    if steps:
        return f"step {steps[-1][0]} of {steps[-1][1]}"
    found = PERCENT_RE.findall(output)
    if found:
        return f"{int(found[-1])} % done"
    crates = len(CARGO_RE.findall(output))
    return f"{crates} crates compiled" if crates else ""


def pip_progress(output: str) -> str:
    """What pip is doing: the package it is fetching, or installing them; '' before it says."""
    for line in reversed(output.splitlines()):
        s = line.strip()
        if s.startswith("Installing collected packages"):
            return "installing the packages"
        if s.startswith("Collecting "):
            return "fetching " + s.split()[1]
        if s.startswith("Requirement already satisfied"):
            return "checking the packages already there"
    return ""


def live_line(stream, environ=None) -> bool:
    """Whether a progress line can be rewritten in place (a terminal: a plain carriage return goes back to the line's
    start, in Command Prompt and PowerShell too) or is printed as a plain line now and then (a pipe, a log file, CI)."""
    environ = os.environ if environ is None else environ
    try:
        return bool(stream.isatty()) and environ.get("TERM") != "dumb"
    except (AttributeError, ValueError, OSError):
        return False


class Progress:
    """A long step's sign of life. On a terminal one line, rewritten every second: "... the kit's tests: 43 % done
    (1 min 05 s)"; in a pipe or a log, a plain line every PLAIN_EVERY seconds. Past `slow` seconds it says once that the
    step is taking unusually long, that waiting is fine, and how to stop it safely. Used as `with Progress(...):`
    around the step's run() calls, which hand it the tool's output (parse reads how far it is from that); a step that
    works in this process sets .detail itself."""
    SHOW_AFTER = 3          # seconds before a terminal's line appears: a quick step shows none
    PLAIN_EVERY = 30        # seconds between plain lines

    def __init__(self, label: str, typical: str, slow: float, me: str, parse=None, stream=None, live: bool | None = None,
                 columns=None):
        self.label, self.typical, self.slow, self.me, self.parse = label, typical, slow, me, parse
        self.stream = stream or sys.stdout
        self.live = live_line(self.stream) if live is None else live
        # the terminal's width now, asked at every tick, as a window can be narrowed while a step runs (the tests give
        # their own)
        self.columns = columns or (lambda: shutil.get_terminal_size((80, 24)).columns)
        self.chunks, self.detail, self.width, self.last, self.warned = [], "", 0, 0.0, False
        self._stop, self._lock, self._thread, self._start = threading.Event(), threading.Lock(), None, 0.0

    def feed(self, text: str) -> None:
        self.chunks.append(text)

    def status(self, elapsed: float) -> str:
        detail = (self.parse("".join(self.chunks)) if self.parse and self.chunks else "") or self.detail
        return f"     ... {self.label}: {detail or 'still running'} ({elapsed_text(elapsed)})"

    def slow_words(self) -> list:
        return [f"     This is taking longer than usual ({self.typical}). You may keep waiting: it has not stopped.",
                f"     To stop it safely, press Ctrl+C: nothing is lost, and {self.me} picks up again when you run it.",
                "     If it is just as slow next time, send the last lines shown here and how long it ran."]

    def tick(self, elapsed: float) -> None:
        """What a second's tick prints, given the time since the step began."""
        if self.slow and elapsed >= self.slow and not self.warned:
            self.warned = True
            self.clear()
            self._write("\n".join(self.slow_words()) + "\n")
        if self.live:
            if elapsed >= self.SHOW_AFTER:
                # one column short of the width: a line that fills it, or one wider than a narrowed window, would wrap,
                # and the carriage return would then rewrite only its last part
                cols = max(1, self.columns() - 1)
                line = self.status(elapsed)[:cols].ljust(min(self.width, cols))     # padded over a longer one
                self._write("\r" + line)
                self.width = len(line)
        elif elapsed - self.last >= self.PLAIN_EVERY:
            self.last = elapsed
            self._write(self.status(elapsed) + "\n")

    def clear(self) -> None:
        """Blanks a terminal's progress line, so the next print starts on a clean line."""
        if self.live and self.width:
            self._write("\r" + " " * self.width + "\r")
            self.width = 0

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text)
            self.stream.flush()
        except (OSError, ValueError):
            pass

    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            with self._lock:
                self.tick(time.monotonic() - self._start)

    def __enter__(self) -> Progress:
        global PROGRESS
        PROGRESS, self._start = self, time.monotonic()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """No more ticks, and the line blanked: at the step's end, or at once on Ctrl+C while its tool stops."""
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join()
        with self._lock:
            self.clear()

    def __exit__(self, *exc) -> None:
        global PROGRESS
        PROGRESS = None
        self.stop()


def long_step(env: Env, announce: str, label: str, typical: str, slow: float, parse=None) -> Progress:
    """Says a long step is starting and roughly how long it takes, and gives the Progress that shows it alive."""
    note(f"{announce} ({typical}) ...")
    return Progress(label, typical, slow, env.me, parse)


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


# ---------------------------------------------------------------- 0. Python's UTF-8 mode, on Windows

def go_to(root: Path) -> str:
    """The step into the camset folder in a new window, in words for both of Windows' terminals, so the person need not
    know which one they have: Command Prompt's cd changes to another drive (D:\\camset from C:\\) only with /d."""
    return f'go to the camset folder (in Command Prompt: cd /d "{root}"; in PowerShell: cd "{root}")'


def utf8_steps(env: Env) -> dict:
    """The three steps that turn UTF-8 mode on, as Env.add's steps, again and after: setx writes PYTHONUTF8 for the
    windows opened after it, never for the one it runs in. setx answers in the PC's language, so its answer is
    described, not quoted. This window stays open until the new one runs the setup, as it holds the steps."""
    return {"steps": ["In this window, run: setx PYTHONUTF8 1   (it answers that the value was saved)",
                      "Open a new terminal (Command Prompt or PowerShell) and keep this window open for now: the "
                      "setting reaches only windows opened after it. To check the new window, run echo %PYTHONUTF8% in "
                      "Command Prompt, or echo $env:PYTHONUTF8 in PowerShell: it prints 1."],
            "again": f"In the new window, {go_to(env.root)} and run {env.me} again.",
            "after": CLOSE_OLD}


CLOSE_OLD = "Once it runs there, you can close this window."      # the last line after a new window's steps


UTF8_DEFAULT = (3, 15)      # the first Python with UTF-8 mode on unless PYTHONUTF8 is 0 (PEP 686)


def kit_python_version(env: Env) -> tuple | None:
    """(major, minor) of the Python that runs the kit's programs: .venv's when it is there and answers, else the one
    this setup would make .venv with (venv_python); None when neither can say."""
    def asked(exe) -> tuple | None:
        if Path(exe) == Path(sys.executable):
            return tuple(sys.version_info[:2])
        code, out = run([exe, "-c", "import sys; print('%d.%d' % sys.version_info[:2])"])
        found = version_key(out.strip().splitlines()[-1]) if code == 0 and out.strip() else ()
        return found[:2] if len(found) >= 2 else None
    py = env.venv_bin("python")
    return (asked(py) if py.exists() else None) or asked(venv_python(env)[0])


def started_in_utf8_mode() -> bool:
    """Whether this run was started in UTF-8 mode by hand (py -X utf8): its own mode is on on a Python that has it off
    by default. The tests replace it."""
    return bool(sys.flags.utf8_mode) and tuple(sys.version_info[:2]) < UTF8_DEFAULT


def step_utf8(env: Env) -> bool:
    """Windows: every kit program refuses to start without Python's UTF-8 mode (camkit/__init__.py: its text is
    UTF-8, cp1252 is not), the tests that start kit programs fail, and so does the proof viewer. So a run stops here,
    with the three steps as its last words, rather than spend minutes on steps that then fail; --check goes on, as it
    only reports. True when the run stops. It is on for the kit's programs when PYTHONUTF8 is 1, or when PYTHONUTF8 is
    not set and the kit's Python (kit_python_version) is 3.15 or newer, which has it on by default; PYTHONUTF8=0 turns
    it off on every Python. What reaches the kit's programs is checked, not this run's own mode: a setup started as
    py -X utf8 is in UTF-8 mode itself, but the programs it starts are not."""
    if not env.windows:
        return False
    said = os.environ.get("PYTHONUTF8", "")
    if said == "1":
        env.add("UTF-8 mode", "OK", "PYTHONUTF8 is 1 in this window")
        return False
    if said == "0":
        why = ("PYTHONUTF8 is set to 0 in this window, which turns off Python's UTF-8 mode; the kit runs only with it "
               "on, on Windows: the steps below set it to 1")
    else:
        ver = kit_python_version(env) if not said else None
        if ver is not None and ver >= UTF8_DEFAULT:
            env.add("UTF-8 mode", "OK", f"on by default in Python {ver[0]}.{ver[1]}, which runs the kit "
                                        "(PYTHONUTF8 is not set in this window)")
            return False
        if started_in_utf8_mode():
            why =("this setup was started in Python's UTF-8 mode (-X utf8), but the kit's programs it starts are not "
                   "in it: on Windows they need PYTHONUTF8 set to 1 in this window, which it is not")
        else:
            why = "the kit runs only in Python's UTF-8 mode on Windows, which is not on in this window"
    stop = not env.check
    env.told_no_wait = env.told_no_wait or stop          # it does not carry on, so it does not say it does
    env.add("UTF-8 mode", "DO", why, "the steps below the table", blocking=True, **utf8_steps(env))
    if stop:
        note("The setup stops here: nothing else was checked or changed. Do the steps above first.")
    return stop


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
    note(f"The file is named CrSDK_v<version>_<date>_{tag}.zip. Put it, as it is, into {env.native('kit/sdk/')} "
         f"({env.sdk})")
    note(f"and run, in this window: {env.me}")


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
    env.add("SDK zip", "FAIL", f"no SDK zip for {want} in {env.native('kit/sdk/')}",
            f"put CrSDK_v<version>_<date>_{want}.zip into {env.native('kit/sdk/')}")
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


def extract(zf: zipfile.ZipFile, dest: Path, limit: Path, skip_same: bool = False, dry: bool = False,
            name: str = "") -> tuple[list, int]:
    """Every entry of zf into dest, inside limit: (the entries written, the number kept). Any entry that is absolute
    or climbs out, or a link that points out of its folder, refuses the whole archive before anything is written.
    With skip_same, a file already there with the same size and CRC (a link: the same target) is kept. With dry,
    nothing is written. name is the archive's, for the progress line."""
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
    for k, i in enumerate(infos, 1):
        if PROGRESS is not None and k % 50 == 0:      # the progress line: how far into this archive
            PROGRESS.detail = f"{name or 'the zip'}: {k} of {len(infos)} files"
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
            written, _ = extract(zf, sdk / folder, sdk, skip_same=not env.force, dry=env.check, name=name)
        if not any(used(folder, n) for n in written):
            other.extend(written)
        elif env.check:
            would.append(f"{name} into {folder}/")
        else:
            unpacked.append(folder + "/")

    try:
        if z is not None:                            # every inner zip, read from Sony's zip itself
            with long_step(env, f"comparing {z.path.name} with kit/sdk/" + ("" if env.check else " and writing what differs"),
                           "unpacking", UNPACK_TIME, UNPACK_SLOW), zipfile.ZipFile(z.path) as outer:
                written, _ = extract(outer, sdk, sdk, skip_same=not env.force, dry=env.check, name=z.path.name)
                other.extend(written)
                for name in sorted(n for n in outer.namelist() if n in INNER or API_RE.match(n)):
                    inner(name, io.BytesIO(outer.read(name)))
        elif sdk.is_dir():                           # no zip: an inner zip already in kit/sdk/, when its folder is not
            names = sorted(n for n in os.listdir(sdk) if (n in INNER or API_RE.match(n))
                           and (env.force or not (sdk / (INNER.get(n) or n[:-len(".zip")])).is_dir()))
            if names:
                with long_step(env, "unpacking " + ", ".join(names) + " in kit/sdk/", "unpacking", UNPACK_TIME, UNPACK_SLOW):
                    for name in names:
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
                f"reads for the body check: put Sony's SDK zip into kit/sdk/ and run {env.me}",
                f"put Sony's SDK zip into {env.native('kit/sdk/')}")
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


def new_window(env: Env, get: str) -> dict:
    """Windows: the steps of an install whose program reaches only the windows opened after it (winget puts it on the
    PATH of new windows), as Env.add's steps, again and after; elsewhere none."""
    if not env.windows:
        return {}
    return {"steps": [f"Run: {get}",
                      "When it has finished, open a new terminal and keep this window open for now: what winget "
                      "installs reaches only windows opened after it."],
            "again": f"In the new window, {go_to(env.root)} and run {env.me} again.",
            "after": CLOSE_OLD}


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
            env.add("cmake", "DO", f"{ver} is older than {low[0]}.{low[1]}; install a newer one: {get}", get, blocking=True,
                    **new_window(env, get))
        else:
            t["cmake"] = True
            env.add("cmake", "OK", ver or "found")
    else:
        env.add("cmake", "DO", f"not found; install it: {get}", get, blocking=True, **new_window(env, get))
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
                    get, blocking=True,
                    steps=[f"Run: {get}",
                           "Windows asks for administrator permission: say Yes. The Visual Studio Installer then "
                           "downloads several GB and works on its own for a while (often 15 to 30 minutes); wait until "
                           "its window closes."])
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
        env.add("cargo", "DO", f"not found; the editor needs Rust: {rustup}", rustup, blocking=True,
                **new_window(env, rustup))
    else:
        env.add("cargo", "--", f"not found; needed only with --editor (Rust: {rustup})", "only for --editor")
    # ffmpeg, for a capture dongle
    if which("ffmpeg"):
        env.add("ffmpeg", "OK", "found (for an HDMI capture dongle)")
    else:
        get = install_hint(env, "brew install ffmpeg", "sudo apt install ffmpeg", "winget install Gyan.FFmpeg",
                           "install ffmpeg 5.1 or later")
        then = " (then open a new terminal: what winget installs reaches only windows opened after it)" if env.windows else ""
        env.add("ffmpeg", "--", f"not found; needed only with an HDMI capture dongle: {get}{then}", "only for a dongle")


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
        with long_step(env, "building libxml2 2.13.9", "building libxml2", LIBXML2_TIME, LIBXML2_SLOW, build_progress):
            for cmd in (["./configure", f"--prefix={prefix}", *LIBXML2_FLAGS], ["make", f"-j{os.cpu_count() or 2}"],
                        ["make", "install"]):
                code, out = run(cmd, cwd=src)
                if code:
                    break
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
            f"aside ({env.move_aside}) and run {env.me} again, which makes it with Python {want} or older when one "
            f"is installed ({get})")


def step_venv(env: Env) -> None:
    venv, py = env.root / ".venv", env.venv_bin("python")
    if not py.exists():
        if venv.exists():
            env.add("venv", "DO", f".venv has no Python in it: move it aside ({env.move_aside}) and run {env.me}",
                    env.move_aside, blocking=True)
            return
        if env.check:
            env.add("venv", "DO", f"would make .venv and install kit/requirements.txt: {env.me}", env.me)
            step_hooks(env)
            return
        exe, why = venv_python(env)
        try:
            with long_step(env, f"making .venv{' with ' + why if why else ''}", "making .venv", VENV_TIME, VENV_SLOW):
                code, out = run([exe, "-m", "venv", venv], cwd=env.root)
        except KeyboardInterrupt:                     # stopped half way: none is left, so the next run makes it afresh
            shutil.rmtree(venv, ignore_errors=True)
            raise
        if code:
            shutil.rmtree(venv, ignore_errors=True)      # the half-made one, from this run
            if env.system == "Linux" and ("ensurepip" in out or "python3-venv" in out):
                env.add("venv", "DO", "Python's venv module is missing: sudo apt install python3-venv",
                        "sudo apt install python3-venv", blocking=True)
            else:
                env.add("venv", "FAIL", f"{exe} -m venv .venv failed (exit {code})", "the output above")
            tail(out)
            return
    code, out = run([py, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"])
    ver = out.strip() if code == 0 else "?"
    if code or version_key(ver) < (3, 11):
        env.add("venv", "DO", f".venv's Python ({ver}) is older than 3.11 or broken: move it aside ({env.move_aside}) "
                f"and run {env.me}", env.move_aside, blocking=True)
        return
    if not venv_pip(env, py, ver):
        return
    env.add("venv", "OK", f".venv (Python {ver})")
    if env.check:
        env.add("packages", "--", "not checked with --check; a run installs kit/requirements.txt", env.me)
    else:
        # -u: pip's lines arrive as it prints them, for the progress line (a pipe would hold them back)
        with long_step(env, "installing kit/requirements.txt into .venv", "installing the packages", PIP_TIME, PIP_SLOW,
                       pip_progress):
            code, out = run([py, "-u", "-m", "pip", "install", "-r", "kit/requirements.txt"], cwd=env.root)
        if code:
            env.add("packages", "FAIL", f"pip install -r kit/requirements.txt failed (exit {code})", "the output above")
            tail(out)
            if version_key(ver)[:2] > NEWEST_PY and ("No matching distribution" in out or "ResolutionImpossible" in out):
                env.add("packages", "DO", newer_python_hint(env, ver), env.move_aside, blocking=True)
            env.add("hooks", "--", "wait for the packages (pre-commit is one of them)", env.me)
            return
        env.add("packages", "OK", "kit/requirements.txt installed in .venv")
    step_hooks(env)


def venv_pip(env: Env, py: Path, ver: str) -> bool:
    """Whether .venv's pip works, as the packages are installed with it. A .venv whose making was stopped half way (by
    an older setup, or a Ctrl+C this one could not clean up after) has its Python but no pip, or part of one: a run
    puts pip back with Python's own ensurepip and asks again; when that does not help, the .venv is moved aside by
    hand, as a broken one is. --check only says so. False when the step ends here."""
    code, _ = run([py, "-m", "pip", "--version"])
    if code == 0:
        return True
    if env.check:
        env.add("venv", "DO", f".venv (Python {ver}) has no working pip, as when its making was stopped half way: a run "
                f"of {env.me} puts it back", env.me)
        step_hooks(env)                           # its row too, as when there is no .venv yet
        return False
    with long_step(env, ".venv has no working pip (its making was stopped half way?): putting it back", "repairing .venv",
                   VENV_TIME, VENV_SLOW):
        code, out = run([py, "-m", "ensurepip", "--upgrade", "--default-pip"], cwd=env.root)
        if not code:
            code, out = run([py, "-m", "pip", "--version"])
    if code:
        env.add("venv", "DO", f".venv (Python {ver}) has no working pip, and Python's ensurepip could not put it back: "
                f"move .venv aside ({env.move_aside}) and run {env.me}", env.move_aside, blocking=True)
        tail(out)
        return False
    note("pip was put back into .venv (python -m ensurepip)")
    return True


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
            get = f"{env.native(env.rel(env.venv_bin('pre-commit')))} install"
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
    configure = ["cmake", "-S", folder, "-B", f"{folder}/build"]
    cmd = ["cmake", "--build", f"{folder}/build", "--config", "Release"] + (["--clean-first"] if clean else [])
    with long_step(env, f"building {folder} ({'from clean' if clean else 'only what changed'})", f"building {folder}",
                   CMAKE_TIME, CMAKE_SLOW, build_progress):
        code, log = run(configure, cwd=env.root)
        if not code:
            code, log = run(cmd, cwd=env.root)
            configure = None                          # it went through: a failure now is the build's
    if configure is not None:
        env.add(piece, "FAIL", f"{shown(configure)} failed (exit {code})", "the output above")
        tail(log)
        if env.windows:
            hint = f"cmake -S {folder} -B {folder}/build -A x64 -T v143,host=x64"
            env.add(piece, "DO", "with Visual Studio 2022, the build is configured by hand once", hint, blocking=True,
                    steps=[f"Clear the build: cmake -E rm -rf {folder}/build", f"Configure it: {hint}"])
        return
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
    with long_step(env, "building kit/ocr", "building kit/ocr", SWIFT_TIME, SWIFT_SLOW):
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
    with long_step(env, "building the editor (cargo build --release: only what changed)", "building the editor",
                   EDITOR_TIME, EDITOR_SLOW, build_progress):
        code, log = run(["cargo", "build", "--release"], cwd=editor)
    out = built(editor / "target" / "release", "camset_editor", env.system)
    if code or not out.exists():
        env.add("editor", "FAIL", f"cargo build --release failed (exit {code}) in editor/", "the output above")
        tail(log)
        return
    env.add("editor", "OK", f"{outcome(before, out)} ({env.rel(out)})")


# ---------------------------------------------------------------- 7. camera access

DRIVER_INF = "srcameradriver.inf"      # Sony's USB driver, in the Win64 zip's Driver.zip


def driver_installed(listing: str) -> bool:
    """Whether `pnputil /enum-drivers` lists Sony's USB driver. Each driver in the store is listed with its
    "Original Name" (for Sony's, srcameradriver.inf) beside the oemNN.inf Windows gave it; the labels are in the PC's
    language, the file name is not, so the name alone is looked for."""
    return DRIVER_INF in listing.lower()


def driver_listing() -> tuple[str | None, str]:
    """The drivers Windows holds, as `pnputil /enum-drivers` lists them (no administrator rights needed); or None and
    why they could not be listed (no pnputil, a failure, no answer in 60 s)."""
    exe = which("pnputil") or str(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "pnputil.exe")
    try:
        p = subprocess.run([exe, "/enum-drivers"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        return None, "pnputil /enum-drivers gave no answer within 60 s"
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"pnputil could not be started ({e})"
    if p.returncode:
        return None, f"pnputil /enum-drivers failed (exit {p.returncode})"
    if not p.stdout.strip():
        return None, "pnputil /enum-drivers printed nothing"
    return p.stdout, ""


def step_access(env: Env) -> None:
    if env.system == "Darwin":
        env.add("camera access", "OK", "nothing to install on macOS (the link stops ptpcamerad before each attempt)")
    elif env.windows:
        listing, why = driver_listing()
        if listing is not None and driver_installed(listing):
            env.add("camera access", "OK", f"Sony's USB driver is installed ({DRIVER_INF})")
            return
        inf = env.sdk / "Driver" / DRIVER_INF
        unsure = "" if listing is not None else (f" (the setup could not check whether it is installed: {why}; if you "
                                                 "have installed it already, you can ignore this line)")
        if inf.exists():
            get = f'pnputil /add-driver "{inf}" /install'
            state = "is not installed yet" if listing is not None else "may not be installed yet"
            env.add("camera access", "DO", f"Sony's USB driver {state}; it is installed once per PC, as "
                    "administrator" + unsure, "the steps below the table",
                    steps=["Open a terminal as administrator: open the Start menu, type Terminal (or Command Prompt, "
                           "on Windows 10), right-click it and choose Run as administrator; say Yes when Windows asks.",
                           f"In that administrator window, run: {get}",
                           "When it says the driver package was added (or that it is already there), close that window "
                           "and come back to this one."])
        else:
            env.add("camera access", "DO", "Sony's USB driver is not in kit\\sdk\\Driver\\, so it cannot be installed "
                    "yet" + unsure, "the steps below the table",
                    steps=[f"Put Sony's Win64 SDK zip (CrSDK_v<version>_<date>_Win64.zip) into kit\\sdk\\ ({env.sdk}). "
                           "The next run unpacks the driver and says how to install it."])
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
    base, own = tests_folder()
    # -u: pytest's lines of dots, each ending in its percentage, arrive as it prints them (a pipe would hold them back)
    try:
        with long_step(env, "running the kit's tests", "the kit's tests", TESTS_TIME, TESTS_SLOW, pytest_progress):
            code, out = run([py, "-X", "utf8", "-u", "-m", "pytest", "kit/tests", "-q", f"--basetemp={base}"],
                            cwd=env.root)
    finally:
        if own:
            shutil.rmtree(base, ignore_errors=True)
    if code:
        said = summary(out)
        what = (f"{said} (exit {code})" if said != "no summary" else
                f"the tests did not finish (exit {code}): pytest stopped before it could count them, and its last "
                "lines, below, say why")
        env.add("tests", "FAIL", what, "the output above; docs/PORTING.md, First day, step 1")
        tail(out)
        return
    env.add("tests", "OK", summary(out))


TESTS_TMP = "camset-kit-tests"      # the setup's own folder for its run of the tests, in the system's temp folder


def tests_folder() -> tuple[Path, bool]:
    """The folder pytest works in for the setup's run of the tests (--basetemp), and whether it is a fresh one of this
    run's own, to remove afterwards. pytest's own choice, numbered folders under pytest-of-<user> with a pytest-current
    link, crashed on Windows in its clean-up after a stopped run (PermissionError: a program the stopped run left
    behind still had a folder open), so the setup gives it one folder of its own, which pytest empties as it starts.
    It is emptied here first: when that fails, as it does while such a program still holds it, the person is told
    which folder and how to free it, and the tests use a new folder this time. Only the setup does this: a default
    folder for every run of the tests would let two runs at once delete each other's files. A link or a Windows
    junction of that name is removed itself, never followed: what it points at is left alone."""
    base = Path(tempfile.gettempdir()) / TESTS_TMP
    try:
        # Path.is_junction is from Python 3.12; a junction is never a symlink to is_symlink, and rmtree refuses it
        if base.is_symlink() or getattr(base, "is_junction", lambda: False)() or base.is_file():
            base.unlink()
        elif base.exists():
            shutil.rmtree(base)
        return base, False
    except OSError:
        fresh = Path(tempfile.mkdtemp(prefix=TESTS_TMP + "-"))
        note(f"The folder {base} could not be emptied: a program from an earlier run of the kit is probably still "
             "using it. Closing other terminals that run the kit, or restarting the computer, frees it. The tests use "
             f"a new folder this time: {fresh}")
        return fresh, True


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
    # without the packages proof_viewer.py would only say to run this setup, which is running
    unready = [r.piece for r in last_rows(env.rows) if r.piece in ("venv", "packages") and r.state in ("FAIL", "DO")]
    if unready:
        why = ".venv is not ready" if unready[0] == "venv" else "the kit's packages are not installed"
        env.add("proof viewer", "--", f"not built: {why} (above)", f"the {unready[0]} line above")
        return
    with long_step(env, "building the proof viewer page, if the kit has run on a camera here", "the proof viewer",
                   VIEWER_TIME, VIEWER_SLOW):
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


def last_rows(rows: list) -> list:
    """Each piece's last row, in the order the pieces first came: what the table shows."""
    last = {}
    for r in rows:
        last.pop(r.piece, None)
        last[r.piece] = r
    return list(last.values())


def ending(env: Env, result: int) -> list:
    """The run's last words, after the table: everything is in place, or what is left for the person, numbered in the
    order to do it (the order of the steps, which is the order things depend on), and the run that follows."""
    rows = last_rows(env.rows)
    todo = [r for r in rows if r.state == "DO" and r.yours]
    failed = [r.piece for r in rows if r.state == "FAIL"]
    would = [r.piece for r in rows if r.state == "DO" and not r.yours]
    lines = []
    if env.check:
        lines.append("Nothing was changed (--check)." + (f" A run of {env.me} would see to: {', '.join(would)}."
                                                         if would else ""))
    if failed:
        many = len(failed) > 1
        lines.append(f"{len(failed)} step{'s' if many else ''} failed: {', '.join(failed)} (FAIL above, "
                     f"{'each ' if many else ''}with its reason, and the last lines of a tool's output where it printed "
                     "any).")
    if todo:
        head = f"{len(todo)} thing{'s are' if len(todo) > 1 else ' is'} left for you to do"
        if result == 0 and not env.check:
            head = "The kit is set up, but " + head
        lines.append(head + (", in this order:" if len(todo) > 1 else ":"))
        # the step in a new window: numbered as its item's last step when it is the one thing left, as during the run;
        # after several, the last line, as it comes once all of them are done
        again = next((r.again for r in todo if r.again), "")
        for i, r in enumerate(todo, 1):
            lines.append(f"  {i}. {r.piece}: {r.what}")
            lines += [f"     {s}" for s in numbered(r.steps + ([r.again] if r.again and len(todo) == 1 else []))]
        if not again:
            lines.append(f"Then run {env.me} again.")
        elif len(todo) > 1:
            lines.append(again)
        lines += [r.after for r in todo if r.after][:1]
    elif failed:
        lines.append(f"When {'they are' if len(failed) > 1 else 'it is'} fixed, run {env.me} again.")
    elif result == 0 and not env.check:
        lines.append("Everything is in place: the kit is set up. Next: docs/QUICKSTART.md, the body check at the end of "
                     "step 1 if not done yet, then step 2.")
    elif env.check:
        lines.append(f"Nothing is missing that you need to do by hand. Run {env.me} to "
                     f"{'do the rest' if would else 'finish the setup'}: it also installs the packages and runs the "
                     "tests, which --check does not.")
    return lines


def parse(argv: list | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="kit/setup.py",
        description="Set up the mapping kit: Sony's SDK zip, dropped into kit/sdk/, unpacked; the tools checked; .venv; "
                    "the camera link, the camera helper and (macOS) the OCR helper built; the tests run; the proof "
                    "viewer built where the kit has run on a camera.",
        epilog="Each step prints OK, DO (yours to do, with the command), FAIL or --, then a table and what is left for "
               "you, in order. It never waits for a DO. Exit status 0: nothing required missing; 1: something is; 2: no "
               "SDK zip; 130: stopped with Ctrl+C. By hand: docs/PORTING.md, Setup per OS.")
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
    try:
        code = all_steps(env, args.zip)
    except KeyboardInterrupt:                       # Ctrl+C, which the progress lines offer
        print(f"\n\nStopped (Ctrl+C). Nothing is lost: run {env.me} again when you are ready; it keeps what is done "
              "and goes on from there.", flush=True)
        return 130
    print("\n" + table(env.rows), flush=True)
    result = exit_code(env.rows, code == 2)
    print("\n" + "\n".join(ending(env, result)), flush=True)
    return result


def all_steps(env: Env, zip_arg: str | None) -> int:
    """The steps in order; 2 when there is no SDK zip to use."""
    if step_utf8(env):
        return 0
    z, code = step_sdk(env, zip_arg)
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
    return code


if __name__ == "__main__":
    sys.exit(main())
