"""Client for kit/link/build/camlink: one camera connection, one command at a time.

Every command is logged to the run's events.jsonl with its reply and duration. Every command, whichever method or
caller sends it, goes through one choke point (Link.call), where the guards are: a button or dial only from the
safety lists (camkit.safety: C4 and the other guarded buttons only where the caller allows them; C1-C3, C5-C7, Movie
and the rest never), held at most safety.MAX_HOLD_MS, and C4 only on the menu, option, panel and editor screens the
caller read last, never on the shooting screen, in Playback or with a picture displayed (c4_refused, decision 7), nor,
on a body that lists its operating mode, when that mode cannot be read; on a screen read as the shooting screen no
button or dial but MENU unless the caller names that key for the press (on_shooting), and with no screen given none
but MENU at all, named or not (safety.shooting_refused, decision 21); a property set only when it is live exposure,
and never one that
makes sound, light or motion, holds credentials or identity, or acts (safety.check_property; no text property is
set); an upload only of the camera's own download (camkit.provenance), with that download's SHA-256 on the line, which
camlink checks the bytes it reads against, so a file swapped in after the check is never sent ("hash_mismatch"), and
a link opens only to a camlink that says so in its ready line ("upload_sha256"); and before anything that changes the
camera (press, dial, set, setstr), the STOP file. A command the kit does not send is refused. camlink refuses the never
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

from . import LINK_BIN, ConfigMissing, config, provenance, safety
from .runs import RESTORE_BY_HAND, Run, restore_pending_any


class LinkError(Exception):
    pass


class CameraRefused(LinkError):
    """A reply came back and said the command was not taken ("button not accepted": the camera did nothing; camlink's
    own guard refused it): kit/drive.py takes an armed press refused so as not gone, closes with MENU and restores.
    No reply, a timeout, a dead camlink, a button left held: LinkError, after which the press may have acted."""


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
CHANGES = frozenset({"press", "dial", "set", "setstr"})
# CameraOperatingMode as the SDK numbers it (CrCameraOperatingMode_Playback): C4 deletes the picture shown there
PLAYBACK_MODE = 2
# The property C4's check reads (c4_refused). camlink answers get with "unknown property NAME" both when the body does
# not list a property and when the SDK's read of a listed one fails (kit/link/camlink.cpp cmdGet), so the words of the
# answer never say which: whether the body lists it is learnt from props, once per open link (mode_listed)
MODE_PROPERTY = "CameraOperatingMode"
# Commands that can change the screen without a LiveCamera seeing it: the link counts them (moves), and LiveCamera reads
# the screen afresh before judging a press when the count has moved since its last read (camkit.live)
MOVES = frozenset({"press", "dial", "download", "upload"})
# Link.open's refusal of a camlink whose ready line does not say "upload_sha256" (one built before 2026-11-08)
OLD_CAMLINK = ("camlink is older than the kit: it does not take the SHA-256 the kit now sends with every upload, so a "
               "run could not put the camera back. Nothing was sent to the camera. Rebuild it with python3 kit/setup.py, "
               "then start again.")


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


# The runs whose links this process opened: a signal asks each to stop. The handlers stay for the life of the
# process once a link has opened (a runner's next link, and its restore, come after a stop).
_RUNS: list = []
_SIGNALS = [getattr(signal, n) for n in ("SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP") if hasattr(signal, n)]
_PREVIOUS: dict = {}


def _on_signal(signum, frame):
    if any(r.stop_requested() and getattr(r, "_stop_why", None) for r in _RUNS):
        for s, h in _PREVIOUS.items():               # asked twice: stop at once, as the user wants
            signal.signal(s, h)
        raise KeyboardInterrupt
    name = signal.Signals(signum).name
    for r in _RUNS:
        r.request_stop(f"signal {name}")
    print(f"\n{name}: stopping cleanly; the run cancels any dialog and puts its start file back. "
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
                 catch_signals: bool = True, pending_restore: bool = False):
        """binary: camlink, or a command line that starts one (the tests' stand-in: [python, script]). pending_restore:
        kit/tools/upload_check.py's alone, putting back the start file a run's RESTORE_BY_HAND names (open)."""
        self.run = run
        self.catch_signals = catch_signals
        self.pending_restore = bool(pending_restore)
        # CAMSET_USB=1: USB remote shooting instead of the LAN (after the camera's Initialize wiped its
        # network setup, 2026-10-30); every script then connects over USB unchanged
        usb = usb or os.environ.get("CAMSET_USB") == "1"
        cmd = [str(x) for x in binary] if isinstance(binary, (list, tuple)) else [str(binary)]
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
        self.proc = None
        self._out = queue.Queue()
        self._seq = 0             # the last request id sent ("@N"; camlink's reply echoes it)
        self.model = None
        self.events = []          # SDK events (disconnects, warnings) as they arrive
        self.moves = 0            # commands sent that can change the screen (MOVES), LiveCamera's own among them
        # MENU presses sent, a cleanup's among them: a network row's lock (camkit.live.LiveCamera.network_left) ends only
        # after one, however it was sent
        self.menus = 0
        self._mode_listed = None  # whether the body lists MODE_PROPERTY, once props has said (mode_listed)

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
            raise LinkError(why)
        # a process group of its own: a terminal's Ctrl-C reaches this process only, which stops the run cleanly
        own_group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                     else {"start_new_session": True})
        if self.catch_signals:
            _catch_signals(self.run)
        # bytes both ways (see the module docstring); buffered, and every command is flushed
        self.proc = subprocess.Popen(self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, **own_group)
        threading.Thread(target=self._pump, args=(self.proc.stdout, self._out.put), daemon=True).start()
        threading.Thread(target=self._pump, args=(self.proc.stderr, self._event), daemon=True).start()
        first = self._reply(timeout)
        self.run.log("link_open", args=self.args[1:], reply=first)
        if not first.get("ok"):
            self.proc.wait(5)
            raise LinkError(f"camera link did not connect: {first.get('error')}")
        if first.get("upload_sha256") is not True:
            # an older camlink refuses every upload line the kit now sends, so a run would change the camera and fail
            # at its put-back: it is refused here, before anything is sent
            self.run.log("link_refused", why=OLD_CAMLINK)
            self.close()
            raise LinkError(OLD_CAMLINK)
        self.model = first.get("ready")
        self._mode_listed = None                # learnt afresh for every link opened
        return self

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
             on_shooting=frozenset(), logged=None) -> dict:
        """The one way a command reaches camlink, whoever sends it: the guards (_guard) first, then the line.
        allow: the guarded buttons the caller names (safety.GUARDED_INPUTS); cleanup: a press that cancels a dialog
        after a STOP; screen: the screen read last (camkit.screen.Screen, or its kind), which C4 and every button or
        dial but MENU need; on_shooting: the keys the caller names for this press on the shooting screen (decision 21);
        logged: what the run's log keeps of the reply, for a question the kit asks of its own (the whole reply when
        None)."""
        if "\n" in command or "\r" in command:
            raise ValueError(f"{command!r}: a command is one line")
        verb, args = parse_command(command)
        try:
            self._guard(verb or "", args, allow, cleanup, screen, on_shooting)
        except (safety.Refused, StopRequested, LinkError) as e:
            self.run.log("cmd_refused", cmd=command, why=f"{type(e).__name__}: {e}")
            raise
        if not self.proc:
            raise LinkError("link is not open")
        if verb in MOVES:
            self.moves += 1                     # sent, answered or not: the screen may have moved
        t0, n = time.monotonic(), self._next_id()
        try:
            self.proc.stdin.write(f"@{n} {command}".encode() + b"\n")      # the reply echoes the id
            self.proc.stdin.flush()
        except OSError:
            pass                # camlink has exited (a signal): its last reply, if any, is waiting in the queue
        r = self._reply(timeout, want=n)
        if verb == "press" and args[:1] == ["menu"] and isinstance(r, dict) and r.get("ok"):
            self.menus += 1                     # a MENU the camera took: one it refused, or no answer, counts none
        self.run.log("cmd", cmd=command, id=n, reply=r if logged is None else logged(r),
                     ms=round((time.monotonic() - t0) * 1000))
        return r

    def _guard(self, verb: str, args: list, allow, cleanup: bool, screen=None, on_shooting=frozenset()):
        """Raises when the command may not go out (the module docstring's guards); returns when it may."""
        if verb == "press":
            if not args or len(args) > 3 or args[2:] not in ([], ["allowed"]):
                raise safety.Refused(f"press takes BUTTON [HOLD_MS] [allowed], not {' '.join(args)!r}")
            safety.check_input(args[0], allow)
            safety.check_hold(args[1] if len(args) > 1 else 60)
            if args[0] == "c4":
                why = self.c4_refused(screen)
                if why:
                    raise safety.Refused(f"C4 refused: {why} (docs/decisions/0007)")
            self._shooting_checked(args[0], screen, on_shooting)
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

    def _must(self, command: str, timeout=30.0, **guard) -> dict:
        """The command's reply when camlink answers ok; LinkError otherwise. A reply that came back saying the camera
        (or camlink's own guard) did not take the command ("button not accepted": nothing done) is CameraRefused; a
        button whose release was refused ("button_held": it went down, and may have acted) and camlink's last word
        after a signal are plain LinkError, as no reply at all is."""
        r = self.call(command, timeout, **guard)
        if not r.get("ok"):
            kind = LinkError if r.get("cause") in ("button_held", "signal") else CameraRefused
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
              on_shooting=frozenset()) -> dict:
        """One button press. cleanup=True skips the STOP check (used to cancel a dialog on stop). A guarded button
        the caller allows goes out marked so ("allowed"): camlink presses no guarded button without it. screen: the
        screen the caller read last (camkit.screen.Screen, or its kind), which C4 needs (safety.c4_refused) and every
        button but MENU (safety.shooting_refused, decision 21: none on the shooting screen unless on_shooting names it
        for this press, and none with no screen given, named or not). The button's name must be written as the guards read it
        ("down", never " Down" or '"down"'): name_refused."""
        self._name_checked("press", button)
        mark = " allowed" if button in safety.GUARDED_INPUTS and button in allow else ""
        return self._must(f"press {button} {int(hold_ms)}{mark}", allow=allow, cleanup=cleanup, screen=screen,
                          on_shooting=on_shooting)

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
        listed, why_not = self.mode_listed()
        if listed is None:
            return (f"whether the camera lists its operating mode could not be read (props: {why_not}): a link in "
                    "trouble is no ground for the trash button")
        if not listed:
            return ""                           # the body does not list it: the screen alone decides (decision 7)
        try:
            mode = self.call(f"get {MODE_PROPERTY}")
        except (LinkError, ValueError) as e:
            mode = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        current = mode.get("current") if mode.get("ok") else None
        if not isinstance(current, int) or isinstance(current, bool):
            return (f"the camera lists its operating mode but did not give it ({mode.get('error') or current!r}): a "
                    "link in trouble is no ground for the trash button")
        if current == PLAYBACK_MODE:
            return "the camera says it is in Playback, where C4 deletes the picture shown"
        return ""

    def mode_listed(self) -> tuple:
        """(whether the body lists MODE_PROPERTY, "") from props, asked the first time C4 is judged on this link and
        kept for it; (None, why) when props fails, gives no list or cannot be read, which is kept for nothing (the next
        C4 asks again). The run's log keeps only what was asked for (mode_answer): the count of properties and whether
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
        return path

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
