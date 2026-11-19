"""A run's session with the camera, the parts every runner shares (docs/decisions/0015: every run starts from a known
file and ends restoring it).

    wait_for(eyes, kinds, why, link=link)   wait for the shooting screen (or another kind) before a download; never
                                            longer than WAIT_LIMIT, and given up when a STOP arrives meanwhile; returns
                                            the kind found ("playback" where kinds names it: playback_kind)
    playback_kind(link, kind)               the one place a screen read as the shooting screen is told from the camera's
                                            playback view, on the camera's word (Link.in_playback): every place that
                                            waits for or acts on the shooting screen asks it (kind_seen, wait_for,
                                            proving.nav.to_shooting, camkit.live.LiveCamera's readings, runner's end)
    finish(link, start)                     the session's end: download, list the records that differ from the start
                                            file (ended) and, when any do, upload the start file (put_back; the
                                            camera restarts); neither while the camera says it is in Playback
                                            (held_in_playback: RESTORE_BY_HAND, exit 5)
    check_restore(run, ending, start)       after that upload: reconnect, download again and count what still differs
    expected={"set1:0x023c", ...}           finish and check_restore leave out records a settings file does not set
                                            which the run is known to write (a memory slot's registration marks):
                                            said by key, never counted, never a reason to upload
    compared(start, after)                  the records that differ, said after one warning line when a file frames a
                                            record id twice in a section (camset.duplicates_note)

crawl_run, drive, prove_run, pass3_run, help_run, table_walk, axis_walk, card_actions, the provers in kit/provers/ and
upload_check (which a chain's upload steps run) end through finish and check_restore, so no runner leaves the
camera changed without saying so, and none restores in a way of its own.
"""
import contextlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import camset, screen
from .frames import load
from .link import Link, LinkError, StopRequested

WAIT_LIMIT = 900        # s a run waits for a screen before it gives up: a run nobody watches must not hold the camera

# The menu's lock after a settings download: a MENU sent too soon is not taken. LOCK_S is the wait the kit has always
# made (proving.base.LOCK_S is this one). LOCK_HDMI_S, measured on the a1 II (runs/ILCE-1M2_fw4.00/kit2_speed_lock,
# 2026-11-18: HDMI eyes at 1080p, Stills mode M, from the shooting screen, MENU the only key, 60 trials): the lock is
# the camera's saving notice. 1.6 s after the download's reply the notice was on show 10 of 10 times and MENU was
# taken 5 of 10; at 2.0, 2.4, 2.8, 3.2 and 3.6 s the shooting screen was on show 50 of 50 times and MENU was taken 50
# of 50, 0.13 to 0.30 s after the press. Then kit2_speed_lock/lock_seen.jsonl (48 trials, the same setup): MENU sent
# 0.0 to 0.3 s after the first frame that read as the shooting screen after the notice opened the menu 12 of 12 times
# at each step, 0.18 to 0.23 s after the press, the shooting screen back 1.92 to 2.06 s after the reply (median 1.97):
# the camera takes MENU the moment the notice is gone. Movie mode behaves alike (runs/ILCE-1M2_fw4.00/
# kit2_speed_lock_mv, 2026-11-18: HDMI eyes at 1080p, Movie mode P, the same two measurements): lock_seen.jsonl (16
# trials), MENU sent 0.00 to 0.01 s after the shooting screen came back, 1.79 to 1.84 s after the reply, opened the menu
# 8 of 8 times, 0.18 to 0.46 s after the press, and sent 0.31 s after it 8 of 8; lock.jsonl (18 trials), MENU 1.6, 2.0
# and 2.4 s after the reply opened it 6 of 6 times each. So with HDMI eyes in a mode measured (LOCK_MEASURED) the wait
# ends as soon as a frame reads as the shooting screen (or a menu page) after one read as the notice, with no floor;
# where no notice was seen (the looks began after it had gone, or missed it), once the shooting screen has been seen
# and LOCK_HDMI_S has passed (2.0 measured good, plus 0.4). A save that takes longer keeps its notice up, and the wait
# goes on while the notice is on show, past LOCK_S, up to LOCK_NOTICE_LIMIT. S&Q is not measured, nor the OSD picture,
# which lags: there, and where the mode is not known, LOCK_S as before. A MENU that is not taken all the same is caught
# by the callers' own guarded retry. The watched rule is MENU's alone until another key is measured: a wait before any
# other key on the shooting screen (afreg_run's Fn hold, framepos_run's and orient_run's multi-selector moves) keeps
# LOCK_S as its floor (lock_over's and wait_lock's floor), since a key the camera drops silently there is counted all
# the same (a put-back one move too many, the focus frame a step off, which no file puts back) or proves nothing.
LOCK_S = 4.5
LOCK_HDMI_S = 2.4
LOCK_NOTICE_LIMIT = 25.0    # s a wait goes on while the notice stays on show (proving.nav.after_download's limit)
LOCK_MEASURED = frozenset({"Stills", "Movie"})             # runner.SCAN_MODES' spelling, as session.MODE holds it
LOCK_READY = ("shooting", "menu", "submenu", "tiles")       # the screens whose sight says the notice has gone
LOCK_NOTICE = "notice"                                      # the saving notice's kind (camkit.screen)
# the shooting mode the camera is in by the kit's own record: the one the run's page scan was made in (runner.load_scan
# sets it; kit/page_scan.py its --mode), and, where a run changes it, the one it left the camera in (kit/provers/
# mode_switch.py, and back once its start file is put back): the mode lock_measured goes by when a caller names none;
# None, not known, keeps LOCK_S
MODE = None


def lock_measured(eyes, mode=None) -> bool:
    """Whether the measured lock (LOCK_HDMI_S) applies: HDMI eyes, in a shooting mode it was measured in (`mode`, else
    MODE)."""
    return getattr(eyes, "name", "") == "hdmi" and (MODE if mode is None else mode) in LOCK_MEASURED


class LockSeen:
    """What the looks after a download have seen since its reply (see each frame's kind in turn): the notice, a
    shooting screen or menu page, one of those after the notice, and whether the notice is on show now."""

    def __init__(self):
        self.notice = self.ready = self.after_notice = self.notice_now = False

    def see(self, kind) -> None:
        self.notice_now = kind == LOCK_NOTICE
        self.notice = self.notice or self.notice_now
        if kind in LOCK_READY:
            self.ready = True
            self.after_notice = self.after_notice or self.notice


def lock_over(waited: float, seen: LockSeen, eyes=None, mode=None, longest: float = LOCK_S, floor: float = 0.0) -> str:
    """Whether the menu's lock after a download is over, `waited` s after the download's reply, given what the looks
    have `seen` since: what ended it, or "" while it lasts. With HDMI eyes in a mode measured (lock_measured): the
    shooting screen or a menu page after the notice ends it at once; the notice on show keeps it, past `longest`, up to
    LOCK_NOTICE_LIMIT; the shooting screen seen with no notice ends it once LOCK_HDMI_S has passed. In every case
    `longest`, the wait the caller made before (LOCK_S), ends it once passed. Never before `floor` s: a wait before a
    key that is not MENU gives floor=LOCK_S (the comment above LOCK_S). The one rule every wait after a download goes by
    (wait_lock, and the callers that look at the screen themselves: proving.nav.after_download, kit/page_scan.py,
    afreg_run.ready_to_hold)."""
    if waited < floor:
        return ""
    measured = lock_measured(eyes, mode)
    if measured and seen.after_notice:
        return "the shooting screen after the notice"
    if measured and seen.notice_now:
        return f"the notice still on show after {LOCK_NOTICE_LIMIT:g} s" if waited > LOCK_NOTICE_LIMIT else ""
    if waited > longest:
        return f"{longest:g} s"
    if measured and seen.ready and waited >= LOCK_HDMI_S:
        return f"the shooting screen, no notice seen, and {LOCK_HDMI_S:g} s"
    return ""


def lock_log(eyes, why: str, waited: float) -> None:
    """One line per wait after a download in the run's events.jsonl ("lock_wait": what ended it, the seconds since
    the download's reply), through the eyes' run where they have one."""
    log = getattr(getattr(eyes, "run", None), "log", None)
    if log:
        with contextlib.suppress(Exception):
            log("lock_wait", ended=why, seconds=round(waited, 3))


def wait_lock(since: float, eyes=None, mode=None, clock=time, longest: float = LOCK_S, poll: float = 0.05,
              floor: float = 0.0) -> str:
    """Wait out the menu's lock after a download whose reply came at `since` (clock.monotonic(); clock: the caller's
    time module): lock_over's rule, never ending before `floor` s (LOCK_S before a key that is not MENU). Where it can
    end early (lock_measured), frames are grabbed unsaved every `poll` s and each one's kind seen (LockSeen; a frame
    that cannot be grabbed or read is none); else it sleeps what is left of `longest`. Logs the wait (lock_log) and
    returns what ended it."""
    if not lock_measured(eyes, mode):
        longest = max(longest, floor)
        left = longest - (clock.monotonic() - since)
        if left > 0:
            clock.sleep(left)
        why = f"{longest:g} s"
        lock_log(eyes, why, clock.monotonic() - since)
        return why
    seen = LockSeen()
    while True:
        try:
            kind = screen.read(eyes.grab(save=False)).kind
        except Exception:       # noqa: BLE001 (a frame that cannot be read is neither)
            kind = None
        seen.see(kind)
        waited = clock.monotonic() - since
        why = lock_over(waited, seen, eyes, mode, longest, floor)
        if why:
            lock_log(eyes, why, waited)
            return why
        clock.sleep(poll)


def _say(msg: str):
    print(msg, flush=True)


def osd_shooting(link, f) -> bool:
    """HDMI black (Auto Framing On blanked it in Movie mode and the run gave up before its restore,
    2026-10-30): the SDK's own picture of the screen says whether the camera is on the shooting
    screen. Only for a black frame: anything drawn over HDMI is read from HDMI."""
    if float(f.image.mean()) > 6:
        return False
    import tempfile
    # this process's own file, removed after: two runs (or two users) never read each other's picture
    path = Path(tempfile.gettempdir()) / f"camkit_osd_{os.getpid()}.png"
    try:
        return screen.read(load(link.osd(path))).kind == "shooting"
    except Exception:
        return False
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


PLAYBACK = "playback"       # the kind of the camera's playback view (playback_kind)
# what the owner is told where the camera says it is in Playback when a run would download or upload its settings
# (runner.restorable_now, held_in_playback): no download or upload is asked then, whatever the screen reads as
LEAVE_BY_HAND = "leave the camera's playback view by hand (its Playback button, or a half-press of the shutter)"
PLAYBACK_HELD = f"the camera says it is in Playback, where it refuses a settings download: {LEAVE_BY_HAND}"


def in_playback_now(link) -> bool:
    """Whether the camera says it is in Playback now: link.in_playback() True, asked afresh; False where it says another
    mode or cannot say (None), and for no link or one that cannot ask."""
    asked = getattr(link, "in_playback", None) if link is not None else None
    return callable(asked) and asked() is True


def playback_kind(link, kind):
    """The kind a screen read as `kind` is for whatever waits for or acts on the shooting screen: PLAYBACK where the
    reader read the shooting screen and the camera says it is in Playback (in_playback_now, asked afresh on every
    call), since the camera's playback view (one picture with its file name, date and exposure along the bottom)
    reads as the shooting screen, and there a download is refused and a key changes the picture shown or acts on it
    (docs/decisions/0021); else `kind` as read, also where the camera's word is not had (no link, a link that cannot
    ask, a body that lists no operating mode, a read that fails: in_playback None)."""
    return PLAYBACK if kind == "shooting" and in_playback_now(link) else kind


def held_in_playback(link, start: Path, say=_say) -> None:
    """Where the camera says it is in Playback (in_playback_now) when the session's end would download or upload its
    settings (ended, put_back): nothing is asked of it; RESTORE_BY_HAND is written for `start` (camkit.runs: no link
    opens until kit/tools/upload_check.py has put it back), the owner is told to leave the playback view by hand and
    then to put the start file back, and the run exits EXIT_RESTORE_BY_HAND (kit/exit_status.py), as over a screen no
    restore may go over (runner.hold_for_owner). Returns where the camera does not say Playback."""
    if not in_playback_now(link):
        return
    from exit_status import EXIT_RESTORE_BY_HAND

    from .runs import mark_restore_by_hand
    run = link.run
    try:
        marker = mark_restore_by_hand(run.root, run.dir.name, start, PLAYBACK_HELD)
    except OSError as e:
        marker = f"RESTORE_BY_HAND (not written: {e}; start no run before the upload below)"
    run.log("restore_held_playback", marker=str(marker))
    try:
        shown = Path(start).relative_to(run.root).as_posix()
    except ValueError:
        shown = str(start)
    say(f"{PLAYBACK_HELD}: no settings download or upload was asked. Once the camera shows its shooting screen, put the "
        f"start file back with\n  .venv/bin/python -u kit/tools/upload_check.py {shown}\n({marker} names it; "
        "docs/decisions/0015)")
    raise SystemExit(EXIT_RESTORE_BY_HAND)


def kind_seen(link, f, s=None) -> str:
    """The kind of the screen on frame `f` (its reading `s`, read here when None) for whatever waits for or acts on the
    shooting screen: the reader's, a black frame the camera's own picture reads as the shooting screen taken for one
    (osd_shooting), and the shooting screen told from the playback view (playback_kind)."""
    kind = (s if s is not None else screen.read(f)).kind
    if kind != "shooting" and link is not None and osd_shooting(link, f):
        kind = "shooting"
    return playback_kind(link, kind)


def wait_for(eyes, kinds, why, grace=2.0, link=None, limit=WAIT_LIMIT, stop=None):
    """Wait for a screen of one of `kinds`, and return the kind found. With `link`, a black HDMI frame is read on the
    SDK's OSD instead, and a screen read as the shooting screen while the camera says it is in Playback is the playback
    view, PLAYBACK, never the shooting screen (kind_seen): a caller that names PLAYBACK among `kinds` gets it back and
    leaves the view itself (proving.nav.leave_playback: first_open's check, runner.wait_shooting); for any other the
    wait goes on as on any screen not asked for.

    Never longer than `limit` s (WAIT_LIMIT when None): then RuntimeError, since a run nobody watches must not hold
    the camera (a crawl waited 2.5 h on a black feed with Auto Framing On, 2026-10-31). `stop` (by default the link's
    run's STOP check) ends the wait with StopRequested when a stop is asked for while it waits; a stop already asked
    for when the wait began does not, since a stopping run waits here on its way to its restore."""
    limit = WAIT_LIMIT if limit is None else limit
    if stop is None:
        run = getattr(link, "run", None)
        stop = run.stop_requested if run is not None else (lambda: False)
    stopped_before = stop()
    said = False
    start = time.monotonic()
    end_grace = start + grace                     # a MENU just pressed may still be closing the menu
    while True:
        f = eyes.grab(save=False)
        s = screen.read(f)
        kind = kind_seen(link, f, s) if "shooting" in kinds else s.kind
        if kind in kinds:
            return kind
        if time.monotonic() < end_grace:
            time.sleep(0.2)
            continue
        if not stopped_before and stop():
            raise StopRequested(f"a stop was asked for while waiting ({why}) on a {kind!r} screen: the wait ends here")
        if time.monotonic() - start > limit:
            raise RuntimeError(f"gave up waiting ({why}) after {limit} s on a {kind!r} screen")
        if not said:
            todo = ("leave Playback by hand with the camera's Playback button" if kind == PLAYBACK
                    else "close the menu by hand")
            _say(f"waiting ({why}): please {todo} (at most {limit:.0f} s)")
            said = True
        time.sleep(0.5)


@dataclass
class Ending:
    """How a session ended: the download at its end (None: the camera kept refusing it, so nothing was restored), the
    records that differ from the start file, and whether the start file was uploaded (check_restore next)."""
    after: Path | None
    changes: list = field(default_factory=list)
    uploaded: bool = False


def ended(link, start: Path, tag: str = "after", tries: int = 4, pause: float = 10.0, show: int = 20,
          say=_say, expected=frozenset(), keys: bool = False) -> Ending:
    """The session's last download, on the shooting screen (a card going in or out made the camera refuse one once,
    2026-10-29: `tries` times, `pause` s apart), and the records that differ from `start`. put_back next.
    expected: keys ("set1:0x023c") of records no settings file sets which the run is known to write (registering a
    memory slot marks the slot filled, its family and its exposure mode, and an upload leaves them: runs/<model>_fw<fw>/
    kit2_small_1109, 00159_restored.DAT and 00289_restored.DAT, 2026-11-09). They are said by key and left out of the
    changes, so they alone never make an upload, which could not put them back. keys (with show=0): the records that
    differ said by their keys alone, never a value (said_keys: a --network or --owner run, whose records can hold an
    address, an identity or a credential). Before each try the camera's word is asked: where it says it is in Playback,
    no download is asked (held_in_playback: RESTORE_BY_HAND, the owner told, exit EXIT_RESTORE_BY_HAND)."""
    after = None
    for attempt in range(tries):
        held_in_playback(link, start, say)
        try:
            after = link.download(tag)
            break
        except LinkError as e:
            if attempt == tries - 1:
                break
            say(f"settings download refused ({e}); trying again")
            time.sleep(pause)
    if after is None:
        say("the camera kept refusing the settings download: the start file is not restored; put it back with "
            f"kit/tools/upload_check.py {start}")
        return Ending(None)
    changes, known = _apart(compared(start, after, say), expected)
    say(f"{len(changes)} records differ from the start file {start.name}{_besides(known)}")
    for c in changes[:show]:
        say(f"   {c.key}: {c.before!r} -> {c.after!r}")
    if keys and not show:
        said_keys(changes, say)
    return Ending(after, changes)


KEYS_SAID = 40          # the most record keys said_keys lists on its line


def said_keys(changes: list, say=_say) -> None:
    """The records that differ said by their keys alone, on one line ("   records: global:0x0123, set1:0x0456"), never a
    value; nothing when none differ."""
    if changes:
        more = f" (and {len(changes) - KEYS_SAID} more)" if len(changes) > KEYS_SAID else ""
        say(f"   records: {', '.join(c.key for c in changes[:KEYS_SAID])}{more}")


def _apart(changes: list, expected) -> tuple:
    """(the changes, the ones `expected` names): records no settings file sets, which the run is known to write."""
    expected = frozenset(expected or ())
    return [c for c in changes if c.key not in expected], [c for c in changes if c.key in expected]


def _besides(known: list) -> str:
    """The expected changes said by key, never by value: " (besides 2 no settings file sets: set1:0x023c, ...)"."""
    return (f" (besides {len(known)} no settings file sets, which the run writes: {', '.join(c.key for c in known)})"
            if known else "")


def compared(start: Path, after: Path, say=_say) -> list:
    """The records that differ between two settings files (camset.diff), with one warning line said first when either
    frames a record id twice in a section (camset.duplicates_note): the comparison then sees the last copy only."""
    a, b = camset.read(start), camset.read(after)
    note = camset.duplicates_note({Path(start).name: a, Path(after).name: b})
    if note:
        say(note)
    return camset.diff(a, b)


def put_back(link, ending: Ending, start: Path, say=_say) -> Ending:
    """`start` uploaded when anything differs from it: the run's changes never stay on the camera (decision 15). The
    camera restarts after an upload and the link drops: check_restore next, with the link closed. Never while the
    camera says it is in Playback (held_in_playback)."""
    if ending.after is not None and ending.changes:
        held_in_playback(link, start, say)
        say(f"restoring the start file {start.name}")
        say(str(link.upload(start)))
        ending.uploaded = True
    return ending


def finish(link, start: Path, tag: str = "after", say=_say, **kw) -> Ending:
    """The session's end: ended, then put_back."""
    return put_back(link, ended(link, start, tag, say=say, **kw), start, say=say)


# The camera after an upload, measured on the a1 II (runs/ILCE-1M2_fw4.00/kit2_speed_restart, 2026-11-18, 3 trials):
# the upload answers in 0.2 s, HDMI shows the notice at about 1 s and the shooting screen again 15.1 to 17.8 s after the
# upload's reply; a link tried while the camera restarts fails cleanly before any login (camlink: "fingerprint:
# Connect_SSH_GetFingerprintFailed") and does no harm, and the try that opened took 9.3 to 14.1 s by itself (the
# camera's network comes up some seconds after its screen): a link open at 29.9 to 37.9 s, against the 51 to 52 s of a
# fixed 40 s wait. RESTART_FIRST: the latest the first try waits; RESTART_RETRY: between tries that did not connect.
RESTART_FIRST = 20.0
RESTART_RETRY = 3.0


def restarted(eyes, clock=time, longest: float = RESTART_FIRST, poll: float = 0.25) -> str:
    """Wait for the camera to come back after an upload: with HDMI eyes until a frame reads as the shooting screen
    after one has read as the notice (the restart's), or `longest` s, whichever comes first; with OSD eyes (they need
    the link the upload closed) or none, `longest` s. A frame that cannot be grabbed or read counts as neither. What it
    waited for: "the shooting screen after the notice" or f"{longest:g} s"."""
    start = clock.monotonic()
    if getattr(eyes, "name", "") == "hdmi":
        notice = False
        while clock.monotonic() - start < longest:
            try:
                kind = screen.read(eyes.grab(save=False)).kind
            except Exception:       # noqa: BLE001 (a feed that drops while the camera restarts: no frame)
                kind = None
            notice = notice or kind == "notice"
            if notice and kind == "shooting":
                return "the shooting screen after the notice"
            clock.sleep(min(poll, max(longest - (clock.monotonic() - start), 0.0)))
        return f"{longest:g} s"
    left = longest - (clock.monotonic() - start)
    if left > 0:
        clock.sleep(left)
    return f"{longest:g} s"


def _connect_failed(e: BaseException) -> bool:
    """A try that did not connect: the link never opened (camkit.link.LinkError opened False: camlink's "camera link
    did not connect", the fingerprint not fetched while the camera restarts), nothing sent to the camera."""
    return isinstance(e, LinkError) and not getattr(e, "opened", True)


def verify_restore(run, start: Path, settle: float = 40.0, tries: int = 6, pause: float = 15.0, link_class=Link,
                   ready: float = 3.0, say=_say, show: int = 20, expected=frozenset(), keys: bool = False, eyes=None,
                   clock=time) -> int | None:
    """After an upload the camera restarts: wait for it (restarted: with HDMI `eyes` the shooting screen back after
    the notice, else RESTART_FIRST s, never longer than `settle`), reconnect, give it `ready` s more, download and count
    the records that differ from `start`, saying the first `show` of them (0: the count only, for a run whose start file
    holds a value it never prints; with keys, their keys too: said_keys); None when no connection came. A try that did
    not connect (_connect_failed) is tried again RESTART_RETRY s later, any other failure `pause` s later, as before;
    no try starts past the deadline the fixed wait gave (`settle` plus `tries` times `pause` from the call), so it is
    never slower than that wait. The records `expected` names (ended) are said by key and not counted. Each wait is in
    the run's events.jsonl ("restore_wait": what it waited for and the seconds; "restore_reconnected" or
    "restore_unreached" with the tries and the seconds from the call)."""
    log = getattr(run, "log", None) or (lambda kind, **f: None)
    t0 = clock.monotonic()
    deadline = t0 + settle + tries * pause
    waited = restarted(eyes, clock, min(RESTART_FIRST, settle))
    log("restore_wait", waited_for=waited, seconds=round(clock.monotonic() - t0, 3))
    attempt = 0
    while True:
        attempt += 1
        try:
            with link_class(run) as link:
                log("restore_reconnected", tries=attempt, seconds=round(clock.monotonic() - t0, 3))
                clock.sleep(ready)
                ch, known = _apart(compared(start, link.download("restored"), say), expected)
                say(f"after the restore: {len(ch)} records differ from the start file{_besides(known)}")
                for c in ch[:show]:
                    say(f"   {c.key}: {c.before!r} -> {c.after!r}")
                if keys and not show:
                    said_keys(ch, say)
                return len(ch)
        except Exception as e:
            say(f"reconnect {attempt} failed: {str(e)[:80]}")
            gap = RESTART_RETRY if _connect_failed(e) else pause
            if clock.monotonic() + gap > deadline:
                log("restore_unreached", tries=attempt, seconds=round(clock.monotonic() - t0, 3))
                return None
            log("restore_wait", waited_for="the next try" + ("" if gap == RESTART_RETRY else " after a failure"),
                seconds=gap)
            clock.sleep(gap)


def check_restore(run, ending: Ending | None, start: Path, **kw) -> int | None:
    """The records that differ from `start` once the session has ended: 0 when nothing had changed, the count after
    the restore when the start file was uploaded, None when it is not known (no download at the end, or no
    reconnection): a caller treats anything but 0 as a restore that did not check out."""
    if ending is None or ending.after is None:
        return None
    return verify_restore(run, start, **kw) if ending.uploaded else 0
