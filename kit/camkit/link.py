"""Client for kit/link/build/camlink: one camera connection, one command at a time.

Every command is logged to the run's events.jsonl with its reply and duration. Every command, whichever method or
caller sends it, goes through one choke point (Link.call), where the guards are: a button or dial only from the
safety lists (camkit.safety: C4 and the other guarded buttons only where the caller allows them; C1-C3, C5-C7, Movie
and the rest never), held at most safety.MAX_HOLD_MS, and C4 only on the menu, option, panel and editor screens the
caller read last, never on the shooting screen, in Playback or with a picture displayed (c4_refused, decision 7), nor,
on a body that lists its operating mode, when that mode cannot be read; on a screen read as the shooting screen no
button or dial but MENU unless the caller names that key for the press (on_shooting), and with no screen given none
but MENU at all, named or not (safety.shooting_refused, decision 21); on the camera's playback view (a screen read as
the shooting screen while the camera says it is in Playback: in_playback, camkit.session.playback_kind) none but MENU,
named or not, and the Playback button once, only to leave it (press_playback, judged at the press by
playback_refused: proving.nav.leave_playback's alone); an Enter, the multi-selector's centre or a trash
button only with the link's count of moving commands when the camera layer's check of what the screen asks looked at
the screen (judged: camkit.live, safety.enter_refused, 2026-11-14), and only while nothing has moved since, so no Enter
is sent past that check or on a screen it did not judge; a property set only when it is live exposure,
and never one that
makes sound, light or motion, holds credentials or identity, or acts (safety.check_property; no text property is
set); the shutter released only on a link opened for kit/tools/take_picture.py, once, on the shooting screen
(PICTURE_ONLY); an upload only of the camera's own download (camkit.provenance), with that download's SHA-256 on the
line, which
camlink checks the bytes it reads against, so a file swapped in after the check is never sent ("hash_mismatch"), and
a link opens only to a camlink that says so in its ready line ("upload_sha256"); a user LUT (import_lut,
docs/decisions/0026) only a .cube file under the clone's own private/lut/ (LUT_DIR, lut_refused), by its real path,
into user place 16 alone, with its bytes' SHA-256 on the line, which camlink checks the bytes it reads against, and
never on a link opened for the picture; before anything that changes the
camera (press, dial, set, setstr), the STOP file; and while the SDK reports a network error on the remote link, nothing
at all until it recovers (_net_wait). A command the kit does not send is refused. camlink refuses the never
buttons, an unallowed guarded button and the never-set properties itself too (kit/common/never_touch.h, written from
camkit/safety.py). On StopRequested the caller must cancel any open dialog (press("menu", cleanup=True)) before
closing: a dropped session applies the dialog on screen.

Ctrl-C and a tool's timeout (SIGTERM) must not kill camlink in the middle of a command, nor skip the
run's cancel and restore (docs/decisions/0015). So camlink runs in a process group of its own, which a
terminal's Ctrl-C does not reach, and once a link is open the first SIGINT/SIGTERM this process gets only
asks the run to stop (Run.request_stop), as a STOP file would: the command in progress finishes, the
next press raises StopRequested, and the run's own stop path cancels and restores. A second one raises
KeyboardInterrupt (not safe; the message says so); closing the link then still sends quit, so camlink
finishes its command and disconnects instead of dying with a dialog open.

The pipe carries bytes: each command is UTF-8 with a bare "\n" (a text pipe on Windows would write
"\r\n"), and every path or text argument is quoted (quoted(): \" and \\ escaped), so a folder with a
space in its name and a Windows path arrive whole (kit/link/protocol.h reads them). Replies that are not
valid UTF-8 are decoded with replacement characters rather than stopping the reader. Every command carries a request
id ("@N"), which camlink's reply echoes: a reply is matched to its command by it, and any other line on camlink's
stdout (the SDK's or a library's, or a late reply to a command that timed out) is logged as stray and skipped.
"""
import contextlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import LINK_BIN, ROOT, STARTED, ConfigMissing, budget, config, paths, provenance, safety
from .runs import RESTORE_BY_HAND, Run, restore_pending_any


class LinkError(Exception):
    """opened: False for one Link.open raised before the link opened (camlink not started, no ready line, or one the
    kit refuses), when nothing was sent to the camera; True for every other."""
    opened = True

    def __init__(self, *args, opened: bool = True):
        super().__init__(*args)
        self.opened = opened


class NetworkError(LinkError):
    """A command the camera did not take while the SDK reported a network error on the remote link (Link.network_error):
    said in plain words, the camera's own reply in the run's log alone. Never a CameraRefused: nothing says the camera
    itself refused it (a MENU refused so is no notice's refusal, proving.nav.to_shooting)."""


# The SDK's warnings on the remote link, as camlink writes them on stderr ({"event": "warning", "code", "text"}): one
# screen (Zebra Level > Custom 1 with its Standard box lit at 30, while OSD Image Mode was on) stalled the session, the
# error came 10-36 s after it appeared, and, the session kept, the recovery 55.3 s after each error (55.39, 55.29,
# 55.40 and 55.37 s, measured four times on 2026-11-18, kit2_zebra_split). A key sent at the instant of the recovery was
# refused (button_held, the camera did not act); one sent 2.0 s after it was taken and the link stayed up
NET_ERROR = (131079, "NetworkErrorOccurred")
NET_RECOVERED = (131080, "NetworkErrorRecovered")
RECOVER_TIMEOUT = 75.0          # s: the most wait_recovered waits for the recovery (55.3 s measured, and some margin)
RECOVER_SETTLE = 2.0            # s: after the recovery, before the next key (at once was refused; 2.0 s was taken)
RECOVER_POLL = 0.25             # s: how often the wait looks at the link's state (its events come on their own thread)
NET_ERROR_SAID = ("the camera's remote link reported a network error while this screen was on show, and the camera "
                  "did not take the command: the kit sends nothing more until the link recovers (about a minute), then "
                  "cancels with MENU and restores")
# What Link.call says while it holds a command back in the error state (_net_wait), and when the error is over
NET_WAIT_SAID = ("the camera's remote link reported a network error: the kit sends nothing until it recovers (about a "
                 f"minute, at most {RECOVER_TIMEOUT:.0f} s), then goes on")
# (the helper turns OSD Image Mode on at its first osd request and never back, kit/common/sdk_session.h saveOsd; HDMI
# eyes ask for the camera's own picture where the HDMI picture cannot decide: camkit.live.LiveCamera.osd_seen,
# camkit.session.osd_shooting, runner.osd_picture)
NET_BACK_SAID = ("the link recovered after {s:.0f} s: going on. The screen on show may be one whose picture the camera "
                 "cannot send while OSD Image Mode is on: the kit turns it on at its first request for the camera's own "
                 "picture, and it stays on until the link closes; OSD eyes ask for that picture always, HDMI eyes only "
                 "where the HDMI picture cannot decide (a black frame, among others)")
# ... and when it does not recover in time: the command is not sent, nor any other while that error lasts
NET_LOST_SAID = ("the camera's remote link reported a network error {s:.0f} s ago and has not recovered within the "
                 f"{RECOVER_TIMEOUT:.0f} s the kit waits (it came back after 55 s each time it was measured): nothing "
                 "more is sent on this link while the error lasts. Look at the camera and cancel by hand whatever it "
                 "still shows (MENU, never OK); the run's last lines say how its start file goes back")


def _is(ev: dict, which: tuple) -> bool:
    """Whether camlink's event `ev` is the SDK's warning `which` ((code, text)), by its code or its text."""
    return ev.get("event") == "warning" and (ev.get("code") == which[0] or ev.get("text") == which[1])


class CameraRefused(LinkError):
    """A reply to a press, a dial or the shutter's release (ACTS) came back and said it was not taken ("button not
    accepted": the camera did nothing; camlink's own guard refused it): kit/drive.py takes an armed press refused so as
    not gone, closes with MENU and restores, and camkit.live.press tries it again. Never for a read (a screen picture,
    a download, a property: their failure says nothing of a key) nor for a "disconnected" reply (Disconnected). No
    reply, a timeout, a dead camlink, a button left held: LinkError, after which the press may have acted."""


class Disconnected(LinkError):
    """camlink answered "disconnected": the camera's session has dropped (camlink answers so to every command once the
    SDK's OnDisconnected has run), so nothing more reaches the camera on this link. Never a CameraRefused, whatever the
    command: a dropped session says nothing about whether the key before it acted."""


# The commands whose "not accepted" means the camera did nothing (CameraRefused): the ones that act
ACTS = frozenset({"press", "dial", "release"})


def quoted(text) -> str:
    """One argument for camlink, quoted (kit/link/protocol.h): spaces and backslashes arrive as they are."""
    t = str(text)
    if "\n" in t or "\r" in t:
        raise ValueError(f"{t!r}: an argument is one line")
    return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _word(s: str, i: int) -> tuple:
    """protocol::word: (argument, next index); a word, or a quoted string with \\" and \\\\ inside."""
    while i < len(s) and s[i] in " \t":
        i += 1
    if i >= len(s):
        return None, i
    if s[i] != '"':
        j = i
        while j < len(s) and s[j] not in " \t":
            j += 1
        return s[i:j], j
    out, i = [], i + 1
    while i < len(s):
        c = s[i]
        if c == '"':
            return "".join(out), i + 1
        if c == "\\" and i + 1 < len(s):
            d = s[i + 1]
            out.append(d if d in '"\\' else c + d)
            i += 2
            continue
        out.append(c)
        i += 1
    raise ValueError("a quoted argument has no closing quote")


def _rest(s: str, i: int) -> str:
    """protocol::rest: a quoted string (nothing after it), or the rest of the line, trimmed."""
    while i < len(s) and s[i] in " \t":
        i += 1
    if i < len(s) and s[i] == '"':
        out, j = _word(s, i)
        if s[j:].strip():
            raise ValueError("text after the quoted argument: " + s[j:].strip())
        return out
    return s[i:].rstrip(" \t")


# a SHA-256 written as hex (protocol::isSha256): upload's second argument
SHA256 = re.compile(r"[0-9a-fA-F]{64}")


def _path_and_hash(s: str, i: int) -> list:
    """protocol::pathAndHash, upload's PATH [SHA256]: [path] or [path, hash]. A quoted path may be followed by the hash
    and nothing else (another word there is refused); an unquoted one is the rest of the line, whose last word is the
    hash when it is 64 hex digits."""
    while i < len(s) and s[i] in " \t":
        i += 1
    if i < len(s) and s[i] == '"':
        path, j = _word(s, i)
        more = s[j:].split(None, 2)                     # the words after it as they come, as the C++ ">>" reads them
        if not more:
            return [path]
        if not SHA256.fullmatch(more[0]):
            raise ValueError("not a SHA-256 (64 hex digits) after the path: " + more[0])
        if len(more) > 1:
            raise ValueError("text after the SHA-256: " + more[1])
        return [path, more[0]]
    line = _rest(s, i)
    gap = max(line.rfind(" "), line.rfind("\t"))
    if gap >= 0 and SHA256.fullmatch(line[gap + 1:]):
        return [line[:gap].rstrip(" \t"), line[gap + 1:]]
    return [line]


def parse_command(line: str) -> tuple:
    """(command, arguments) as camlink reads the line (kit/link/protocol.h); ValueError on a quote left open."""
    line = line[:-1] if line.endswith("\r") else line
    cmd, i = _word(line, 0)
    if cmd == "osd":
        return cmd, [_rest(line, i)]
    if cmd == "upload":
        return cmd, _path_and_hash(line, i)
    if cmd in ("download", "setstr"):
        first, i = _word(line, i)
        return cmd, [first, _rest(line, i)]
    args = []
    while True:
        w, i = _word(line, i)
        if w is None:
            return cmd, args
        args.append(w)


# Commands that only read the camera, sent whatever the run's state; a command named neither here nor below is refused
READS = frozenset({"hello", "ping", "props", "get", "osd", "download"})
# Commands that change the camera: none after a STOP, except a cleanup press (MENU to cancel a dialog)
CHANGES = frozenset({"press", "dial", "set", "setstr", "release", "importlut"})
# The shutter released once (camlink's release, Sony's Release command down and up): kit/tools/take_picture.py's alone,
# on a link opened with picture=True, which starts camlink with --picture and sends no press but MENU, no dial and no
# property; on any other link it is refused, and camlink without --picture refuses it too (docs/decisions/0002)
PICTURE_ONLY = "release"
# CameraOperatingMode as the SDK numbers it (CrCameraOperatingMode_Playback): C4 deletes the picture shown there
PLAYBACK_MODE = 2
# The property C4's check and in_playback read (operating_mode). camlink answers get with "unknown property NAME" both
# when the body does not list a property and when the SDK's read of a listed one fails (kit/link/camlink.cpp cmdGet), so the words of the
# answer never say which: whether the body lists it is learnt from props, once per open link (mode_listed)
MODE_PROPERTY = "CameraOperatingMode"
# Commands that can change the screen without a LiveCamera seeing it: the link counts them (moves), and LiveCamera reads
# the screen afresh before judging a press when the count has moved since its last read (camkit.live)
MOVES = frozenset({"press", "dial", "download", "upload", "release", "importlut"})
# Link.open's refusal of a camlink whose ready line does not say "upload_sha256" (one built before 2026-11-08)
OLD_CAMLINK = ("camlink is older than the kit: it does not take the SHA-256 the kit now sends with every upload, so a "
               "run could not put the camera back. Nothing was sent to the camera. Rebuild it with python3 kit/setup.py, "
               "then start again.")
# Link.open's words when camlink printed its usage line and exited before its ready line: it was started with an option
# it does not know (--picture, before 2026-11-15), so it was built before the kit asked for it
OLD_HELPER = ("the camera helper ({helper}) is older than the kit and does not know an option this tool needs: rebuild it "
              "with  python3 kit/setup.py  and run this again. Nothing was sent to the camera.")
USAGE = "usage: camlink"            # how camlink's usage line starts (kit/link/camlink.cpp main, on stderr)

# A user LUT into the camera (import_lut: camlink's importlut, Sony's ImportLUTFile), as docs/decisions/0026 allows it:
# only a .cube file under the clone's own private/lut/, into user place 16 alone. The file's rules are camlink's own
# (kit/common/lut_file.h), checked here first: Sony's API reference takes a name of 63 characters at most with its
# extension, not starting with a period, of single-byte letters, digits, spaces and the signs below, and less than 3 MB,
# read as 3,000,000 bytes, the stricter reading; the kit takes ".cube" alone and a .cube LUT's text (a LUT_3D_SIZE or
# LUT_1D_SIZE line), so that no other file renamed .cube goes
LUT_DIR = ROOT / "private" / "lut"
LUT_SUFFIX = ".cube"
LUT_MAX_BYTES = 3_000_000           # a file this size or larger is refused
LUT_MAX_NAME = 63
LUT_PLACE = 16                      # the one user place decision 26 allows (CrBaseLookNumber_16)
LUT_NAME = re.compile(r"[A-Za-z0-9 #$%&'()+,\-.;=@\[\]^`{}~_]+")
LUT_SIZE_LINE = re.compile(rb"^[ \t]*LUT_[13]D_SIZE[ \t]+\d", re.M)
LUT_OK = "ImportLUTFile_Result_OK"  # the camera's one answer that says the LUT went in (camlink's "result")
LUT_TIMEOUT = 150.0                 # s: camlink waits up to 120 s for the camera's answer, after its reads
OLD_LUT_CAMLINK = ("camlink is older than the kit: it does not know importlut, so nothing was sent to the camera. "
                   "Rebuild it with python3 kit/setup.py, then run this again.")


def _cube_text(data: bytes) -> bool:
    """Whether the bytes are a .cube LUT's text, as camlink reads it (lut_file.h cubeText): no NUL, and a line that
    starts with LUT_3D_SIZE or LUT_1D_SIZE and a number (spaces first, a byte order mark before the first line)."""
    if b"\0" in data:
        return False
    data = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    return bool(LUT_SIZE_LINE.search(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")))


def lut_refused(path, folder=None) -> str:
    """Why `path` may not go to the camera as a user LUT, "" when it may: the file not a link, and where its path really
    ends (".." and a folder that is a link followed) inside the clone's own LUT folder (`folder`, LUT_DIR by default), a
    regular file whose name ends ".cube", of 63 characters at most, not starting with a period, of the characters Sony's
    reference takes, under 3,000,000 bytes, a .cube LUT's text. camlink checks the same again before the SDK is asked
    (kit/common/lut_file.h), against the clone's folder it was built with, and reads the file once."""
    folder = Path(LUT_DIR if folder is None else folder)
    p = Path(path)
    try:
        top = folder.resolve(strict=True)
    except (OSError, RuntimeError):
        return (f"there is no folder {paths.shown(folder)}/ in this clone: the import takes a LUT from that folder "
                "alone (the owner's own, private/lut/)")
    if p.is_symlink():
        return f"{p} is a link, which is not followed: name the file itself"
    try:
        real = p.resolve(strict=True)
    except (OSError, RuntimeError):
        return f"{p} is not there"
    if real == top or not real.is_relative_to(top):
        return (f"{p} is not under {paths.shown(folder)}/, the owner's own LUT folder, the only one the import takes "
                f"a LUT from (where its path really ends: {real})")
    if not real.is_file():
        return f"{p} is not a file"
    name = real.name
    if not name.endswith(LUT_SUFFIX) or name == LUT_SUFFIX:
        return f"{name}: its name does not end in {LUT_SUFFIX!r} (the import takes .cube files alone)"
    if len(name) > LUT_MAX_NAME:
        return f"{name}: its name is {len(name)} characters; Sony's reference takes {LUT_MAX_NAME} at most, the extension counted"
    if name.startswith("."):
        return f"{name}: its name starts with a period, which Sony's reference does not take"
    if not LUT_NAME.fullmatch(name):
        return (f"{name}: its name holds a character Sony's reference does not take (single-byte letters, digits, "
                "spaces and # $ % & ' ( ) + , - . ; = @ [ ] ^ ` { } ~ _ alone)")
    size = real.stat().st_size
    if size >= LUT_MAX_BYTES:
        return f"{name} is {size:,} bytes; Sony's reference takes less than 3 MB ({LUT_MAX_BYTES:,} bytes, the stricter reading)"
    if not _cube_text(real.read_bytes()):
        return f"{name} is not a .cube LUT's text (no LUT_3D_SIZE or LUT_1D_SIZE line, or not text)"
    return ""


class LutNotImported(LinkError):
    """Link.import_lut's answer when the camera did not say the LUT went in (anything but camlink's ok with the camera's
    ImportLUTFile_Result_OK for the bytes the kit checked): `reply` camlink's answer as it came, `called` whether camlink
    says it asked the SDK (then the camera may have changed, and the run restores and looks at what it holds)."""

    def __init__(self, why: str, reply: dict):
        super().__init__(why)
        self.reply = reply if isinstance(reply, dict) else {}
        self.called = self.reply.get("called") is True


def lists_mode(reply: dict) -> bool | None:
    """Whether a props reply lists MODE_PROPERTY (by the name camlink gives it, "CrDeviceProperty_" or not); None when
    the reply failed or holds no list."""
    props = reply.get("props") if isinstance(reply, dict) else None
    if not isinstance(props, list) or not reply.get("ok"):
        return None
    return any(isinstance(p, dict) and str(p.get("name") or "").removeprefix("CrDeviceProperty_") == MODE_PROPERTY
               for p in props)


def mode_answer(reply: dict) -> dict:
    """What the run's log keeps of the props reply Link.mode_listed asks for: its ok and error, the count of properties
    and whether the mode is listed; no property's value or name."""
    props = reply.get("props") if isinstance(reply, dict) else None
    return {"ok": reply.get("ok"), **({"error": reply["error"]} if reply.get("error") else {}),
            "count": len(props) if isinstance(props, list) else None, "mode_listed": lists_mode(reply),
            **({"id": reply["id"]} if "id" in reply else {})}


class StopRequested(Exception):
    pass


# The commands this process has sent to a camlink (Link.call, every one: a read too), whichever link: none means the run
# has sent nothing to the camera, so a failure before its first command left the camera as it was (runner.restoring)
SENT = 0

# The runs whose links this process opened: a signal asks each to stop. The handlers stay for the life of the
# process once a link has opened (a runner's next link, and its restore, come after a stop).
_RUNS: list = []
_SIGNALS = [getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP") if hasattr(signal, n)]
_PREVIOUS: dict = {}
# What a first signal's line says instead of the usual one while the process waits on something a stop does not cut
# short (camkit.session.verify_restore's check after an upload, which reads and changes nothing): None otherwise
WAITING_ON: str | None = None

_SLOW_DOC: dict = {}            # slow_doc's: the definition as read, by its file, size and time


def slow_doc() -> dict:
    """The definition camkit.slow_states names its states by: the camera's (camkit.definitions.active), read again
    only when its file changed; {} where there is none or it cannot be read (then nothing is known: silent)."""
    from . import definitions
    try:
        target = definitions.active(required=False)
        st = target.stat() if target is not None else None
    except Exception:
        return {}
    if st is None:
        return {}
    key = (str(target), st.st_mtime_ns, st.st_size)
    if _SLOW_DOC.get("key") != key:
        try:
            doc = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        _SLOW_DOC.update(key=key, doc=doc if isinstance(doc, dict) else {})
    return _SLOW_DOC["doc"]


def _on_signal(signum, frame):
    if any(r.stop_requested() and getattr(r, "_stop_why", None) for r in _RUNS):
        for s, h in _PREVIOUS.items():               # asked twice: stop at once, as the user wants
            signal.signal(s, h)
        raise KeyboardInterrupt
    name = signal.Signals(signum).name
    for r in _RUNS:
        r.request_stop(f"signal {name}")
    print(f"\n{name}: {WAITING_ON}" if WAITING_ON else
          f"\n{name}: stopping cleanly; the run cancels any dialog and puts its start file back. "
          "Press Ctrl-C again only to stop at once, which can leave the camera changed or a dialog open.",
          file=sys.stderr, flush=True)


def _catch_signals(run):
    if run not in _RUNS:
        _RUNS.append(run)
    if _PREVIOUS or threading.current_thread() is not threading.main_thread():
        return
    for s in _SIGNALS:
        with contextlib.suppress(OSError, ValueError):
            _PREVIOUS[s] = signal.signal(s, _on_signal)


class Link:
    def __init__(self, run: Run, ip: str | None = None, usb: bool = False, binary: Path | list = LINK_BIN,
                 catch_signals: bool = True, pending_restore: bool = False, picture: bool = False):
        """binary: camlink, or a command line that starts one (the tests' stand-in: [python, script]). pending_restore:
        kit/tools/upload_check.py's alone, putting back the start file a run's RESTORE_BY_HAND names (open). picture:
        kit/tools/take_picture.py's alone, the one link that may release the shutter, once (PICTURE_ONLY)."""
        self.run = run
        self.catch_signals = catch_signals
        self.pending_restore = bool(pending_restore)
        self.picture, self.released = bool(picture), False
        # CAMSET_USB=1: USB remote shooting instead of the LAN (after the camera's Initialize wiped its
        # network setup, 2026-10-30); every script then connects over USB unchanged
        usb = usb or os.environ.get("CAMSET_USB") == "1"
        cmd = [str(x) for x in binary] if isinstance(binary, (list, tuple)) else [str(binary)]
        self.helper = Path(cmd[-1])         # camlink, or the script a command line starts (OLD_HELPER names it)
        # the camera's address is your config's (private/config.json; refused without one), unless given
        if not usb and not ip:
            ip = config().get("camera_ip")
            if not ip:
                raise ConfigMissing("private/config.json has no \"camera_ip\": put your camera's address there "
                                    "(docs/QUICKSTART.md), or connect over USB (CAMSET_USB=1)")
        self.args = cmd + (["--usb"] if usb else ["--ip", ip])
        model = None if usb else config(required=False).get("camera_model")
        if model:                                  # the SDK's model number, for a LAN body (default ILCE-1M2)
            self.args += ["--model", model]
        if self.picture:
            self.args += ["--picture"]
        self.proc = None
        self._out = queue.Queue()
        self._seq = 0             # the last request id sent ("@N"; camlink's reply echoes it)
        self.model = None
        # "lan" or "usb", the first word of camlink's ready reply's "connection" ("lan A.B.C.D"), "" before it says: the
        # windows measured over one kind of link apply over that kind alone (camkit.frames.link_connection)
        self.connection = ""
        self.events = []          # SDK events (disconnects, warnings) as they arrive
        # why nothing but MENU is pressed: this link's last download held a state in which the camera acts on one press
        # twice (camkit.slow_states.after_download, set by download, cleared by one without it), else ""
        self.slow = ""
        self.moves = 0            # commands sent that can change the screen (MOVES), LiveCamera's own among them
        # when the last of them was answered (time.monotonic(); None before any): an OSD frame is no older than the kit's
        # own last move only once camkit.live.OSD_LAG has passed since (camkit.live.look_again)
        self.moved_at = None
        self.output_ended = False     # camlink's output has ended (it exited, or its pipe broke): no reply comes again
        # the camera's session dropped while camlink runs on (gone): why, from the SDK's "disconnected" event or a reply
        # saying "disconnected" (camlink answers so to every command once OnDisconnected has run; the SDK is connected
        # with reconnecting off, kit/common/sdk_session.h), "" again once a request sent after it is answered
        self.disconnected = ""
        # the last request id sent when the drop was learnt: a reply to that request or an earlier one, its "ok" made
        # before the drop, clears nothing (2026-11-15, a review: the event can land while such a reply is on its way)
        self._dropped_after = -1
        # MENU presses sent, a cleanup's among them: a network row's lock (camkit.live.LiveCamera.network_left) ends only
        # after one, however it was sent
        self.menus = 0
        self._mode_listed = None  # whether the body lists MODE_PROPERTY, once props has said (mode_listed)
        self._props_failed = False    # props failed on this open link: in_playback asks it no more (C4's check does)
        # the SDK's network error on the remote link (NET_ERROR, NET_RECOVERED): in error since when (the clock's time),
        # recovered when; no disconnect (gone stays ""), and over once the recovery comes (network_error, wait_recovered)
        self._clock, self._sleep = time.monotonic, time.sleep       # the tests' own clock and sleep stand in
        self._net_reset()

    # -------------------------------------------------------------- lifetime

    def open(self, timeout=40.0):
        # a run that may have dropped its link left the camera unrestored (kit/drive.py --owner, "link_loss": camkit.runs
        # RESTORE_BY_HAND): no link opens, so no run starts from it, until kit/tools/upload_check.py has put that run's
        # start file back and removed the file (docs/decisions/0015); refused before camlink starts
        found = None if getattr(self, "pending_restore", False) else restore_pending_any(self.run.root)
        if found is not None:
            where, pending = found
            why = (f"{where / RESTORE_BY_HAND} says a run ({pending.get('run')}) may have dropped the link and "
                   f"left the camera unrestored: cancel on the camera by hand whatever screen it still shows (MENU or "
                   f"Cancel, never Enter or OK), then put its start file back, by hand once the camera is reachable, "
                   f"with kit/tools/upload_check.py {pending.get('start')} (docs/decisions/0015); no link opens until "
                   "then")
            self.run.log("link_refused", why=why)
            raise LinkError(why, opened=False)
        # a process group of its own: a terminal's Ctrl-C reaches this process only, which stops the run cleanly
        own_group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                     else {"start_new_session": True})
        if self.catch_signals:
            _catch_signals(self.run)
        # bytes both ways (see the module docstring); buffered, and every command is flushed
        opening = time.monotonic()
        self.proc = subprocess.Popen(self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, **own_group)
        self.output_ended = False
        self.disconnected, self._dropped_after = "", -1      # a new session: nothing of the last one's drop
        self._net_reset()                                    # nor of its network error
        threading.Thread(target=self._pump, args=(self.proc.stdout, self._stdout_line), daemon=True).start()
        self._stderr_pump = threading.Thread(target=self._pump, args=(self.proc.stderr, self._event), daemon=True)
        self._stderr_pump.start()
        try:
            first = self._reply(timeout)
        except LinkError as e:
            raise LinkError(self._not_ready(str(e)), opened=False) from None
        self.run.log("link_open", args=self.args[1:], reply=first, process_started=round(STARTED, 3))
        # what the start took before this link opened, and its own open, timed (camkit.budget): one line
        budget.add("link open", time.monotonic() - opening)
        budget.report(self.run)
        if not first.get("ok"):
            self.proc.wait(5)
            raise LinkError(f"camera link did not connect: {first.get('error')}", opened=False)
        if first.get("upload_sha256") is not True:
            # an older camlink refuses every upload line the kit now sends, so a run would change the camera and fail
            # at its put-back: it is refused here, before anything is sent
            self.run.log("link_refused", why=OLD_CAMLINK)
            self.close()
            raise LinkError(OLD_CAMLINK, opened=False)
        self.model = first.get("ready")
        self.connection = (str(first.get("connection") or "").split() or [""])[0].lower()
        self._mode_listed, self._props_failed = None, False     # learnt afresh for every link opened
        return self

    def _not_ready(self, why: str) -> str:
        """Why no ready line came: OLD_HELPER when camlink exited after printing its usage line (an option it does not
        know), naming the helper started (inside the repository, from its root); else `why` as it was."""
        if not self.output_ended:
            return why                  # no reply in time: camlink runs on
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.proc.wait(5)
        self._stderr_pump.join(5)       # its stderr read to the end, the usage line among the events
        if any(ev.get("event") == "text" and str(ev.get("text") or "").startswith(USAGE) for ev in list(self.events)):
            return OLD_HELPER.format(helper=paths.shown(self.helper))
        return why

    def use_run(self, run: Run):
        """Go on in another run folder: kit/tools/identify.py opens the link before the camera has said which it is,
        and then keeps its evidence in that camera's own folder (camkit.paths)."""
        self.run.log("run_moved", to=str(run.dir))
        if self.run in _RUNS:
            _RUNS.remove(self.run)
        self.run = run
        if self.catch_signals:
            _catch_signals(run)
        run.log("run_continued", args=self.args[1:], model=self.model)

    def close(self):
        """Clean disconnect. Callers must have closed any dialog first (see module docstring). camlink
        finishes the command in progress before it reads quit; terminate() asks it the same way (SIGTERM)."""
        if not self.proc:
            return
        try:
            self.proc.stdin.write(b"quit\n")
            self.proc.stdin.flush()
            self.proc.wait(30)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        with contextlib.suppress(OSError):
            self.proc.stdin.close()     # its stdout and stderr close as the pumps reach their end
        self.run.log("link_close")
        self.proc = None

    def __enter__(self):
        return self.open()

    def __exit__(self, kind, value, tb):
        if kind is KeyboardInterrupt:
            self.run.log("interrupted", note="a second Ctrl-C: the link closes after camlink's command in progress")
        self.close()

    # -------------------------------------------------------------- plumbing

    @staticmethod
    def _pump(stream, sink):
        with stream:                    # closed here once camlink's side ends, not left to the garbage collector
            for raw in stream:
                sink(raw.decode("utf-8", errors="replace"))
        sink(None)

    def _stdout_line(self, line):
        """A line of camlink's stdout into the reply queue; None, its end, also marks the output ended (gone)."""
        if line is None:
            self.output_ended = True
        self._out.put(line)

    def gone(self) -> str:
        """Why camlink can do nothing more on the camera, or "": its process has exited, its output has ended, the link
        was closed, or the camera's session dropped while camlink runs on (disconnected: a power-off, a cable out, a
        Wi-Fi drop; camlink then answers "disconnected" to everything). runner.hold_for_owner leaves its wait on it: a
        link that has gone cannot be kept open over a screen."""
        proc = getattr(self, "proc", None)
        if proc is None:
            return "the link is closed"
        code = proc.poll()
        if code is not None:
            return f"camlink has exited (status {code})"
        if getattr(self, "output_ended", False):
            return "camlink's output has ended"
        return getattr(self, "disconnected", "")

    def _net_reset(self) -> None:
        self.net_error_since, self.net_recovered_at = None, None
        self._net_lost = None           # the error (its start) _net_wait gave up on: no second wait for it

    def _now(self) -> float:
        return getattr(self, "_clock", time.monotonic)()

    def network_error(self) -> str:
        """Why the camera's remote link is in the SDK's network-error state, in plain words, or "" when it is not: from
        NetworkErrorOccurred until NetworkErrorRecovered (_event). It is no disconnect (gone stays ""): the session comes
        back by itself, about a minute later, if the kit keeps it and sends nothing (wait_recovered)."""
        since = getattr(self, "net_error_since", None)
        if since is None:
            return ""
        return f"the camera's remote link reported a network error {max(0.0, self._now() - since):.0f} s ago"

    def _settling(self) -> bool:
        """The SDK's network error recovered less than RECOVER_SETTLE s ago (a key sent at the recovery was refused)."""
        rec = getattr(self, "net_recovered_at", None)
        return getattr(self, "net_error_since", None) is None and rec is not None and self._now() - rec < RECOVER_SETTLE

    def wait_recovered(self, timeout: float = RECOVER_TIMEOUT, settle: float = RECOVER_SETTLE, stop=None) -> bool:
        """Sending nothing, until the SDK's network error is over: in the error state, waits for NetworkErrorRecovered,
        then `settle` s more (a key sent at the recovery was refused, one 2.0 s after it taken: RECOVER_SETTLE), and
        returns True; False at once on a disconnect or camlink's end (gone), as soon as `stop()` says so (Link.call's
        STOP for a command a STOP refuses), and at `timeout` s with no recovery. A recovery less than `settle` s past is
        given the rest of it; with no error at all it returns True at once. Each wait is logged ("network_wait": its
        outcome and seconds)."""
        sleep = getattr(self, "_sleep", time.sleep)
        start = self._now()
        waited = getattr(self, "net_error_since", None) is not None
        outcome = "recovered"
        while getattr(self, "net_error_since", None) is not None:
            if self.gone():
                outcome = f"dropped ({self.gone()})"
                break
            if stop is not None and stop():
                outcome = "stopped"
                break
            left = timeout - (self._now() - start)
            if left <= 0:
                outcome = "timed out"
                break
            sleep(min(RECOVER_POLL, left))
        if getattr(self, "net_error_since", None) is None:
            rec = getattr(self, "net_recovered_at", None)
            if rec is not None and self._now() - rec < settle:
                sleep(settle - (self._now() - rec))
                waited = True
        if waited:
            self.run.log("network_wait", outcome=outcome, s=round(self._now() - start, 1))
        return outcome == "recovered"

    def _event(self, line):
        """An SDK event from camlink's stderr, kept and logged. camlink writes objects ({"event": ...}); anything else
        a library prints there is kept as text. Nothing here may raise: this runs on the thread that drains stderr,
        and with it gone camlink blocks on a full pipe while holding its output lock, so every reply stops."""
        if line is None:
            return
        try:
            ev = json.loads(line)
        except ValueError:
            ev = None
        if not isinstance(ev, dict):
            ev = {"event": "text", "text": line.strip()}
        self.events.append(ev)
        if ev.get("event") == "disconnected":
            self._dropped_after = self._seq
            self.disconnected = "the SDK reported the camera disconnected"
        elif _is(ev, NET_ERROR):
            self.net_error_since = self._now()          # no disconnect: the session may come back (wait_recovered)
        elif _is(ev, NET_RECOVERED):
            self.net_error_since, self.net_recovered_at = None, self._now()
        try:
            # the log's own keys ("t", "kind") are kept apart from the event's
            self.run.log("sdk_event", **{(f"event_{k}" if k in ("t", "kind") else k): v for k, v in ev.items()})
        except Exception as e:          # a log that cannot be written must not stop the draining
            print(f"camlink event not logged ({type(e).__name__}: {e}): {line.strip()[:200]}", file=sys.stderr)

    def _reply(self, timeout, want: int | None = None) -> dict:
        """The reply to request `want` (its "id"), or with want None the first reply ("ok" in it: the ready line).
        Any other line on camlink's stdout, from the SDK or a library, or a reply to another request, is logged as
        stray and skipped, so it cannot shift every later reply onto the wrong command. camlink's last word after a
        signal ("cause": "signal") is taken whatever its id."""
        end = time.monotonic() + timeout
        while True:
            try:
                line = self._out.get(timeout=max(0.0, end - time.monotonic()))
            except queue.Empty:
                raise LinkError(f"no reply within {timeout:.0f} s") from None
            if line is None:
                self._out.put(None)         # camlink's output has ended: every later command fails at once too
                raise LinkError("camera link exited")
            try:
                r = json.loads(line)
            except ValueError:
                r = None
            if isinstance(r, dict) and "ok" in r and (r.get("id") == want or r.get("cause") == "signal"):
                return r
            self.run.log("stray_output", line=line.strip()[:500], waiting_for=want)

    def _next_id(self) -> int:
        self._seq += 1
        return self._seq

    def call(self, command: str, timeout=30.0, allow=frozenset(), cleanup=False, screen=None,
             on_shooting=frozenset(), logged=None, judged=None, leaving=False) -> dict:
        """The one way a command reaches camlink, whoever sends it: the guards (_guard) first, then the line.
        allow: the guarded buttons the caller names (safety.GUARDED_INPUTS); cleanup: a press that cancels a dialog
        after a STOP; screen: the screen read last (camkit.screen.Screen, or its kind), which C4 and every button or
        dial but MENU need; on_shooting: the keys the caller names for this press on the shooting screen (decision 21);
        logged: what the run's log keeps of the reply, for a question the kit asks of its own (the whole reply when
        None); judged: for an Enter or a trash button, the link's count of moving commands (moves) when the camera
        layer's check of what the screen asks looked at the screen: it goes only while that count is still the link's
        (_guard), so neither a judgement made on a screen that has moved since nor a word given without one goes out.
        leaving: press_playback's alone, the one press of the Playback button (playback_refused)."""
        if "\n" in command or "\r" in command:
            raise ValueError(f"{command!r}: a command is one line")
        verb, args = parse_command(command)
        try:
            self._guard(verb or "", args, allow, cleanup, screen, on_shooting, judged, leaving)
        except (safety.Refused, StopRequested, LinkError) as e:
            self.run.log("cmd_refused", cmd=command, why=f"{type(e).__name__}: {e}")
            raise
        if not self.proc:
            raise LinkError("link is not open")
        if self.network_error() or self._settling():
            self._net_wait(command, verb or "", cleanup)     # nothing goes out while the SDK's network error lasts
        if verb == PICTURE_ONLY:
            self.released = True                # once per link, answered or not
        if verb in MOVES:
            self.moves += 1                     # sent, answered or not: the screen may have moved
        global SENT
        SENT += 1                               # this run has sent the camera something (runner.restoring)
        t0, n = time.monotonic(), self._next_id()
        try:
            self.proc.stdin.write(f"@{n} {command}".encode() + b"\n")      # the reply echoes the id
            self.proc.stdin.flush()
        except OSError:
            pass                # camlink has exited (a signal): its last reply, if any, is waiting in the queue
        try:
            r = self._reply(timeout, want=n)
        finally:
            if verb in MOVES:
                self.moved_at = time.monotonic()    # answered or not: the screen may have moved until now
        if verb == "press" and args[:1] == ["menu"] and isinstance(r, dict) and r.get("ok"):
            self.menus += 1                     # a MENU the camera took: one it refused, or no answer, counts none
        if isinstance(r, dict) and (r.get("error") == "disconnected" or (verb == "ping" and r.get("connected") is False)):
            self.disconnected = "camlink answers that the camera is disconnected"
        elif isinstance(r, dict) and r.get("ok") and n > self._dropped_after:
            self.disconnected = ""              # a request sent after the drop answered: the session is there
        self.run.log("cmd", cmd=command, id=n, reply=r if logged is None else logged(r),
                     ms=round((time.monotonic() - t0) * 1000))
        return r

    def _net_wait(self, command: str, verb: str, cleanup: bool) -> None:
        """call's hold while the SDK reports a network error on the remote link (network_error), every command alike,
        a read among them: nothing is sent until the error is over (wait_recovered: the recovery, then RECOVER_SETTLE;
        one screen of the a1 II stalls the session so while OSD Image Mode is on, and a MENU sent at once was refused
        and the link closed over it, the camera left unrestored: kit2_zebra_split, 2026-11-18), the wait said in plain
        words. A command a STOP refuses (CHANGES, a cleanup press aside) raises StopRequested as soon as a stop is asked
        for meanwhile, so the run's stop path cancels, its cleanup MENU waiting in turn; a drop raises Disconnected; no
        recovery within RECOVER_TIMEOUT raises NetworkError saying so (NET_LOST_SAID), nothing sent, and so does every
        command after it while that same error lasts, with no second wait. Each refusal is logged ("cmd_refused")."""
        since = getattr(self, "net_error_since", None)
        if since is None:
            self.wait_recovered()           # a recovery less than RECOVER_SETTLE s past: the rest of it, nothing said
            return
        gone = self.gone()
        if gone:
            self.run.log("cmd_refused", cmd=command, why=f"dropped during a network error ({gone})")
            raise Disconnected(f"the camera's session dropped during its network error ({gone}): nothing more reaches "
                               "the camera on this link")
        if getattr(self, "_net_lost", None) == since:
            why = NET_LOST_SAID.format(s=self._now() - since)
            self.run.log("cmd_refused", cmd=command, why="network error not recovered")
            raise NetworkError(why)
        stops = verb in CHANGES and not (cleanup and verb == "press")
        stop = self.run.stop_requested if stops else None
        print(NET_WAIT_SAID, flush=True)
        start = self._now()
        if self.wait_recovered(stop=stop):
            print(NET_BACK_SAID.format(s=self._now() - start), flush=True)
            return
        if stop is not None and stop():
            self.run.log("cmd_refused", cmd=command, why="StopRequested during a network error")
            raise StopRequested(self.run.stop_reason())
        gone = self.gone()
        if gone:
            self.run.log("cmd_refused", cmd=command, why=f"dropped during a network error ({gone})")
            raise Disconnected(f"the camera's session dropped during its network error ({gone}): nothing more reaches "
                               "the camera on this link")
        self._net_lost = since
        self.run.log("cmd_refused", cmd=command, why="network error not recovered")
        raise NetworkError(NET_LOST_SAID.format(s=self._now() - since))

    def _guard(self, verb: str, args: list, allow, cleanup: bool, screen=None, on_shooting=frozenset(), judged=None,
               leaving: bool = False):
        """Raises when the command may not go out (the module docstring's guards); returns when it may."""
        self.slow_guard(verb, args)
        picture = getattr(self, "picture", False)
        if picture and (verb in ("dial", "set", "setstr") or (verb == "press" and args[:1] != ["menu"])):
            raise safety.Refused("a picture link (kit/tools/take_picture.py) sends no press but MENU, no dial and no "
                                 "property")
        if picture and verb == "importlut":
            raise safety.Refused("a picture link (kit/tools/take_picture.py) imports nothing")
        if verb == PICTURE_ONLY:
            if not picture:
                raise safety.Refused("the shutter is released only by kit/tools/take_picture.py, on a link opened for "
                                     "it (docs/decisions/0002)")
            if args or getattr(self, "released", False):
                raise safety.Refused("release takes no argument and goes once per link")
            if getattr(screen, "kind", screen) != "shooting":
                raise safety.Refused(f"the shutter is released only on the shooting screen, not on a "
                                     f"{getattr(screen, 'kind', screen)!r} screen")
        elif verb == "press":
            if not args or len(args) > 3 or args[2:] not in ([], ["allowed"]):
                raise safety.Refused(f"press takes BUTTON [HOLD_MS] [allowed], not {' '.join(args)!r}")
            safety.check_input(args[0], allow)
            safety.check_hold(args[1] if len(args) > 1 else 60)
            if args[0] == "c4":
                why = self.c4_refused(screen)
                if why:
                    raise safety.Refused(f"C4 refused: {why} (docs/decisions/0007)")
            if args[0] == "playback":
                why = self.playback_refused(screen, leaving)
                if why:
                    raise safety.Refused(f"Playback refused: {why} (docs/decisions/0021)")
            self._shooting_checked(args[0], screen, on_shooting)
            if args[0] in safety.ENTER_KEYS | safety.TRASH_KEYS and (
                    isinstance(judged, bool) or not isinstance(judged, int) or judged != self.moves):
                # an Enter (or the trash button) answers whatever the screen asks: it goes only with the link's count of
                # moving commands at the moment the camera layer's check looked at the screen (camkit.live.LiveCamera.
                # press; proving.nav.to_shooting, live.menu_refused_enter), and only while nothing has moved since
                raise safety.Refused(f"{args[0]} refused: no Enter goes out unless camkit.live's check of what the "
                                     "screen asks judged the screen on show (its count of moving commands "
                                     f"{judged!r}, the link's now {self.moves})")
        elif verb == "dial":
            if len(args) != 2 or not re.fullmatch(r"-?\d+", args[1]):
                raise safety.Refused(f"dial takes DIAL STEPS, not {' '.join(args)!r}")
            safety.check_input(args[0])
            self._shooting_checked(args[0], screen, on_shooting)
        elif verb == "set":
            if len(args) != 2:
                raise safety.Refused(f"set takes NAME VALUE, not {' '.join(args)!r}")
            safety.check_property(args[0])
        elif verb == "setstr":
            safety.check_property(args[0] if args else "", allowed=frozenset())     # no text property is set
        elif verb == "upload":
            self._upload_checked(args)
        elif verb == "importlut":
            self._lut_checked(args)
        elif verb not in READS:
            raise safety.Refused(f"{verb!r} is not a command the kit sends")
        if verb in CHANGES and not (cleanup and verb == "press") and self.run.stop_requested():
            raise StopRequested(self.run.stop_reason())

    @staticmethod
    def _shooting_checked(key: str, screen, on_shooting):
        """Refuses a key other than MENU on a screen read as the shooting screen, unless the caller names it for this
        press, and on no screen at all, named or not (safety.shooting_refused, decision 21)."""
        why = safety.shooting_refused(key, getattr(screen, "kind", screen), on_shooting)
        if why:
            raise safety.Refused(f"{key} refused: {why} (docs/decisions/0021)")

    def _upload_checked(self, args: list):
        """An upload only of a file the camera wrote: its bytes a download's in the manifest (camkit.provenance), and the
        line carrying those bytes' SHA-256, which camlink checks the bytes it reads against (kit/common/settings_file.h),
        so the bytes sent are the bytes checked here. 2026-11-01 a file edited by hand boot-looped the camera in Movie
        mode (docs/decisions/0006). Raises LinkError, logged as upload_refused, when it may not go."""
        path = Path(args[0]) if args else Path("")
        try:
            digest = provenance.check(path, self.run.root).get("sha256")
            if len(args) < 2:
                raise provenance.NotADownload(
                    f"{path}: not sent: the upload carries no SHA-256, which camlink checks the bytes it reads against. "
                    "Send it with Link.upload, which adds it")
            if args[1].lower() != digest:
                raise provenance.NotADownload(
                    f"{path}: not sent: its bytes are not the ones the SHA-256 on the line names: something wrote the "
                    "file after that hash was taken. Stop whatever writes there and upload it again: the kit checks it "
                    "afresh")
        except provenance.NotADownload as e:
            self.run.log("upload_refused", path=str(path), why=str(e))
            raise LinkError(str(e)) from None

    @staticmethod
    def _lut_checked(args: list):
        """An importlut line only as import_lut writes it: PATH 16 SHA256, the path a file lut_refused takes, named by
        its real path (what camlink copies for the SDK is what was checked here), user place 16 written so and no other
        (docs/decisions/0026), and the SHA-256 that of the file's bytes now, which camlink checks the bytes it reads
        against. Raises safety.Refused."""
        if len(args) != 3 or not SHA256.fullmatch(args[2]):
            raise safety.Refused(f"importlut takes PATH {LUT_PLACE} SHA256 (as Link.import_lut writes it), not "
                                 f"{' '.join(args)!r}")
        if args[1] != str(LUT_PLACE):
            raise safety.Refused(f"importlut goes into user place {LUT_PLACE} alone (docs/decisions/0026), not "
                                 f"place {args[1]!r}")
        path = Path(args[0])
        why = lut_refused(path)
        if why:
            raise safety.Refused(why)
        if not path.is_absolute() or path != path.resolve():
            raise safety.Refused(f"importlut names a LUT by its real path (Link.import_lut sends it so), not {path}")
        if provenance.sha256(path) != args[2].lower():
            raise safety.Refused(f"{path.name}: its bytes are not the ones the SHA-256 on the line names: something "
                                 "wrote the file after that hash was taken. Import it again: the kit checks it afresh")

    def _must(self, command: str, timeout=30.0, **guard) -> dict:
        """The command's reply when camlink answers ok; LinkError otherwise. A press, dial or release (ACTS) whose reply
        came back saying the camera (or camlink's own guard) did not take it ("button not accepted": nothing done) is
        CameraRefused; a failed read (a screen picture: "no OSD image", a download, a property) is a plain LinkError,
        which says nothing of a key (2026-11-18, the review's finding 1: a picture that failed after a key went was
        taken for that key refused, and the key sent again); a "disconnected" reply, whatever the command, is
        Disconnected; a button whose release was refused ("button_held": it went down, and may have acted) and camlink's
        last word after a signal are plain LinkError, as no reply at all is. One the camera did not take while the SDK
        reported a network error on the link (network_error) is NetworkError, in plain words, its reply in the run's log
        alone."""
        r = self.call(command, timeout, **guard)
        if not r.get("ok"):
            if self.network_error() and r.get("cause") != "signal":
                raise NetworkError(NET_ERROR_SAID)
            if r.get("error") == "disconnected" and r.get("cause") != "signal":
                raise Disconnected(f"{command}: the camera's session has dropped (camlink answers \"disconnected\")")
            acts = command.split(" ", 1)[0] in ACTS
            kind = CameraRefused if acts and r.get("cause") not in ("button_held", "signal") else LinkError
            raise kind(f"{command}: {r.get('error')}")
        return r

    # -------------------------------------------------------------- inputs

    def _name_checked(self, verb: str, name):
        """Refuses a key's name not written as the guards read it (safety.name_refused): camlink's parser would drop
        the spaces or quotation marks round it and press the key a caller's own check never saw."""
        why = safety.name_refused(name)
        if why:
            self.run.log("cmd_refused", cmd=f"{verb} {name!r}", why=f"Refused: {why}")
            raise safety.Refused(why)

    def press(self, button: str, hold_ms=60, allow=frozenset(), cleanup=False, screen=None,
              on_shooting=frozenset(), judged=None) -> dict:
        """One button press. cleanup=True skips the STOP check (used to cancel a dialog on stop). A guarded button
        the caller allows goes out marked so ("allowed"): camlink presses no guarded button without it. screen: the
        screen the caller read last (camkit.screen.Screen, or its kind), which C4 needs (safety.c4_refused) and every
        button but MENU (safety.shooting_refused, decision 21: none on the shooting screen unless on_shooting names it
        for this press, and none with no screen given, named or not). judged: an Enter, the multi-selector's centre or a
        trash button goes only with the link's count of moving commands at the moment the camera layer's check of what
        the screen asks looked at the screen (camkit.live, 2026-11-14), and only while it is still the link's count: a
        press sent past that check, or judged on a screen that has moved since, is refused here. The button's name must
        be written as the guards read it ("down", never " Down" or '"down"'): name_refused."""
        self._name_checked("press", button)
        mark = " allowed" if button in safety.GUARDED_INPUTS and button in allow else ""
        return self._must(f"press {button} {int(hold_ms)}{mark}", allow=allow, cleanup=cleanup, screen=screen,
                          on_shooting=on_shooting, judged=judged)

    def c4_refused(self, screen) -> str:
        """Why C4 may not go out now, or "": the screen read last must be a menu, option, panel or editor screen
        (safety.c4_refused), and, when the body lists CameraOperatingMode (mode_listed: learnt from props once per open
        link), the camera must give that mode, and not Playback, where C4 deletes the picture shown. When it is listed,
        any get that gives no integer mode refuses C4, whatever its words: camlink answers "unknown property" for a
        failed read as for a property not listed. When props itself fails or cannot be read, C4 is refused: a link in
        trouble is no ground for the trash button (2026-11-10). When the body does not list it, the screen alone
        decides, as decision 7 says."""
        why = safety.c4_refused(getattr(screen, "kind", screen))
        if why or not self.proc:
            return why
        listed, current, why_not = self.operating_mode()
        if listed is None:
            return (f"whether the camera lists its operating mode could not be read (props: {why_not}): a link in "
                    "trouble is no ground for the trash button")
        if not listed:
            return ""                           # the body does not list it: the screen alone decides (decision 7)
        if current is None:
            return (f"the camera lists its operating mode but did not give it ({why_not}): a link in trouble is no "
                    "ground for the trash button")
        if current == PLAYBACK_MODE:
            return "the camera says it is in Playback, where C4 deletes the picture shown"
        return ""

    def operating_mode(self) -> tuple:
        """(listed, mode, why) of the camera's CameraOperatingMode, the one way the kit asks it (c4_refused, in_playback):
        listed as mode_listed gives it (None when props failed, why saying so; False when the body does not list it),
        and, where listed, the integer mode a get gives, asked afresh on every call, or None with why (the read failed,
        or gave no integer: camlink answers "unknown property" for a failed read as for a property not listed)."""
        listed, why_not = self.mode_listed()
        if not listed:
            return listed, None, why_not
        try:
            mode = self.call(f"get {MODE_PROPERTY}")
        except (LinkError, ValueError) as e:
            mode = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        current = mode.get("current") if mode.get("ok") else None
        if not isinstance(current, int) or isinstance(current, bool):
            return True, None, str(mode.get("error") or repr(current))
        return True, current, ""

    def in_playback(self) -> bool | None:
        """The camera's word on whether it is in Playback, asked afresh on every call (operating_mode, never kept across
        presses): True when the body lists its operating mode and the camera gives Playback (PLAYBACK_MODE), False when
        it gives another, None when the body lists none, the link is not open, or the read fails. The camera's playback
        view (one picture with its file name, date and exposure along the bottom) reads as the shooting screen to the
        reader: where this says True, the kit takes such a screen for the playback view (camkit.session.playback_kind,
        docs/decisions/0021). A props that failed once on this open link is remembered for this question alone: from
        then on it is None with nothing asked (each screen read as the shooting screen would else wait on props again);
        C4's check still asks, and refuses (c4_refused)."""
        if not getattr(self, "proc", None) or getattr(self, "_props_failed", False):
            return None
        listed, current, _ = self.operating_mode()
        if listed is None:
            self._props_failed = True
        if not listed or current is None:
            return None
        return current == PLAYBACK_MODE

    def playback_refused(self, screen, leaving: bool = False) -> str:
        """Why the Playback button may not go out now, or "": only to leave the camera's playback view (`leaving`:
        press_playback's, for proving.nav.leave_playback alone), judged at the press as C4 is, on the screen the caller
        read last, which must be the playback view (kind "playback": camkit.session.playback_kind), and on the camera's
        word, asked again here, that it is in Playback (in_playback True; False or None refuses)."""
        if not leaving:
            return ("the Playback button goes out only to leave the camera's playback view (proving.nav.leave_playback, "
                    "Link.press_playback)")
        kind = getattr(screen, "kind", screen)
        if kind != "playback":
            return f"the screen read last is {kind!r}, not the camera's playback view"
        if self.in_playback() is not True:
            return "the camera does not say it is in Playback"
        return ""

    def press_playback(self, screen) -> dict:
        """The Playback button pressed once, marked allowed, to leave the camera's playback view: proving.nav.
        leave_playback's alone (playback_refused judges it at the press: the screen read last, `screen`, is the playback
        view and the camera says it is in Playback). Every other request for the Playback button is refused, and C4 and
        Delete stay refused there (safety.c4_refused, safety.shooting_refused). Not a cleanup press: after a STOP it is
        refused (StopRequested)."""
        return self._must("press playback 60 allowed", allow=frozenset({"playback"}), screen=screen, leaving=True)

    def mode_listed(self) -> tuple:
        """(whether the body lists MODE_PROPERTY, "") from props, asked the first time the mode is (operating_mode: C4
        judged, or in_playback) on this link and kept for it; (None, why) when props fails, gives no list or cannot be
        read, which is kept for nothing (the next question asks again). The run's log keeps only what was asked for (mode_answer): the count of properties and whether
        the mode is listed, never a property's value (props holds the body's serial number, the photographer's and the
        copyright texts) nor another name; Link.props() and identify.py log their own replies as before.
        Matched by name only: camlink names each property through the SDK's table (camlink.cpp propName), and the
        repository holds no code for CameraOperatingMode to match it by (the SDK's headers are not in it). So on an SDK
        whose table does not name it, the entry carries no such name, the body reads as not listing it, and the screen
        decides C4 alone, as for a body that truly does not list it."""
        if self._mode_listed is not None:
            return self._mode_listed, ""
        try:
            r = self.call("props", timeout=60, logged=mode_answer)
        except (LinkError, ValueError) as e:
            return None, f"{type(e).__name__}: {e}"
        listed = lists_mode(r)
        if listed is None:
            return None, str(r.get("error") or "no list of properties")
        self._mode_listed = listed
        return listed, ""

    def dial(self, dial: str, steps: int, screen=None, on_shooting=frozenset()) -> dict:
        """A dial turned `steps` on the screen the caller read last (screen), which every dial needs: on the shooting
        screen a dial changes the live exposure (safety.shooting_refused, decision 21: refused there unless on_shooting
        names the dial, and with no screen given, named or not)."""
        self._name_checked("dial", dial)
        return self._must(f"dial {dial} {int(steps)}", screen=screen, on_shooting=on_shooting)

    def release(self, screen) -> dict:
        """The shutter released once, on the shooting screen the caller read last (`screen`): on a link opened with
        picture=True alone (PICTURE_ONLY, kit/tools/take_picture.py), once per link."""
        return self._must(PICTURE_ONLY, screen=screen)

    # -------------------------------------------------------------- reads and files

    def osd(self, path: Path) -> Path:
        return Path(self._must(f"osd {quoted(path)}")["path"])

    def props(self) -> list[dict]:
        return self._must("props", timeout=60)["props"]

    def get(self, name: str) -> dict:
        return self._must(f"get {name}")

    def set(self, name: str, value: int) -> dict:
        """A live exposure value (safety.SET_PROPERTIES), which camlink reads back."""
        return self._must(f"set {name} {int(value)}")

    def download(self, tag: str) -> Path:
        """Settings file into the run's dat/ folder, numbered like the shots. Its SHA-256 goes into the runs
        folder's downloads manifest (camkit.provenance): what upload() accepts."""
        name = self.run.dat_name(tag)
        path = Path(self._must(f"download {quoted(self.run.dat)} {quoted(name)}", timeout=90)["path"])
        provenance.record(path, self.run.root, run=self.run.dir.name, camera=self.model)
        # a run's own choice can put the camera where it acts on one press twice (S&Q Frame Rate 1fps on the a1 II):
        # every download is judged, and one in such a state leaves this link pressing nothing but MENU (slow_guard)
        from . import slow_states
        self.slow = slow_states.after_download(slow_doc(), path)
        if self.slow:
            self.run.log("slow_state", file=path.name, why=self.slow)
        return path

    def slow_guard(self, verb: str, args: list):
        """Refused: any press but MENU, and any dial, while this link's last download held a state in which the camera
        acts on one press twice (self.slow). MENU, the way back to the shooting screen, and the restore's upload, which
        presses nothing, still go; the run's restore takes the camera out of the state."""
        why = getattr(self, "slow", "")
        if why and (verb == "dial" or (verb == "press" and args[:1] != ["menu"])):
            raise safety.Refused(why)

    def upload(self, path: Path) -> dict:
        """Replace every camera setting with this file. The camera restarts and the link drops.
        Only a file the camera wrote is sent: its bytes must be a download's in the manifest
        (camkit.provenance), wherever it sits. 2026-11-01 a file edited by hand boot-looped the camera
        in Movie mode, and the owner's rule since is to change settings on the camera and watch, never
        to write values into a file (docs/decisions/0006). The check is the choke point's (_guard), which
        takes the file's SHA-256 sent with it to be the hash it checked; camlink reads the file once and
        sends those bytes only when they have that hash, so a file swapped in after the check is never
        sent: camlink answers "hash_mismatch", and this raises LinkError."""
        path = Path(path).resolve()
        digest = provenance.sha256(path) if path.is_file() else ""         # none: the guard says why (no such file)
        command = f"upload {quoted(path)} {digest}".rstrip()
        r = self.call(command, timeout=150)
        if r.get("cause") == "hash_mismatch":
            why = (f"{path}: not uploaded: something wrote this file while it was being sent (camlink read bytes "
                   "without the SHA-256 the kit checked), so camlink sent nothing. Stop whatever writes there and "
                   "upload it again: the kit checks it afresh, and if its bytes are no longer a download's it refuses "
                   f"it and says what to do ({provenance.DECISION}).")
            self.run.log("upload_refused", path=str(path), why=why, reply=r)
            raise LinkError(why)
        if not r.get("ok"):
            raise LinkError(f"{command}: {r.get('error')}")
        if r.get("sha256") != digest:
            # camlink names the SHA-256 of the bytes it sent: none, or another, means they were not checked against
            # the kit's, and the camera may have taken them all the same
            why = (f"{path}: the upload was answered without the SHA-256 the kit checked (camlink said "
                   f"{r.get('sha256')!r}), so the bytes sent were not checked against it, and the camera may already "
                   "have taken the file. Rebuild camlink with python3 kit/setup.py, then download the camera's "
                   "settings and compare them with this file before going on.")
            self.run.log("upload_unconfirmed", path=str(path), why=why, reply=r)
            raise LinkError(why)
        return r

    def import_lut(self, path) -> dict:
        """One user LUT (a .cube look-up table) into user place 16 of the camera, the one place docs/decisions/0026
        allows: camlink's importlut, which calls Sony's ImportLUTFile. Returns camlink's answer when the camera said the
        LUT went in (ImportLUTFile_Result_OK, for the bytes the kit checked); raises LutNotImported, with camlink's
        answer and whether the SDK was asked, for any other, and safety.Refused for a file it does not send. The owner's
        word for the run is the caller's to carry (kit/tools/lut_import.py's --allow).

        A look-up table is not a settings file, and this is not Link.upload by another door: upload sends back only a
        settings file the camera itself wrote, its bytes one of the camera's downloads (docs/decisions/0006: a settings
        file edited by hand boot-looped the camera). A LUT replaces no setting: it is data the camera's own menu imports
        from a card (Manage User LUTs > Import), here Sony's own published look profiles, and Sony's API reference
        documents ImportLUTFile for the purpose. So it goes through checks of its own, none of upload's: lut_refused
        here (the clone's own LUT folder, LUT_DIR, where the path really ends, never through a link; ".cube"; the name
        and size Sony's reference takes; a .cube LUT's text), then the guard on the line (_lut_checked) and camlink's
        own (kit/common/lut_file.h: the same again against the clone's folder it was built with, the file read once
        with the SHA-256 sent, then the camera's state: the import enabled, not recording, place 16 not one it lists as
        holding a LUT), and camlink gives the SDK a copy of the bytes it checked, never the file. The run's events.jsonl
        keeps the file's name, size, SHA-256 and place ("lut_import"), never its content. No key is pressed. A LUT in
        the camera is state no settings file puts back: it stays there until the owner deletes it by hand."""
        place = LUT_PLACE
        why = lut_refused(path)
        if why:
            self.run.log("lut_refused", file=Path(path).name, place=place, why=why)
            raise safety.Refused(why)
        real = Path(path).resolve()
        digest = provenance.sha256(real)
        self.run.log("lut_import", file=real.name, bytes=real.stat().st_size, sha256=digest, place=place)
        r = self.call(f"importlut {quoted(real)} {place} {digest}", timeout=LUT_TIMEOUT)
        if r.get("ok") and r.get("result") == LUT_OK and r.get("sha256") == digest:
            return r
        if not r.get("ok") and str(r.get("error") or "").startswith("unknown command importlut"):
            why = OLD_LUT_CAMLINK
        elif not r.get("ok"):
            why = (f"the import of {real.name} into place {place} is not confirmed: {r.get('error')} "
                   f"({r.get('cause') or 'no cause given'})")
        elif r.get("result") != LUT_OK:
            why = (f"camlink answered without the camera's {LUT_OK} (it said {r.get('result')!r}): the import of "
                   f"{real.name} is not confirmed")
        else:
            why = (f"the camera said {LUT_OK}, but camlink's answer names the SHA-256 of {r.get('sha256')!r}, not the "
                   f"bytes the kit checked ({digest}): which bytes went into place {place} is not known")
        self.run.log("lut_not_imported", file=real.name, place=place, why=why, reply=r)
        raise LutNotImported(why, r)
