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


def verify_restore(run, start: Path, settle: float = 40.0, tries: int = 6, pause: float = 15.0, link_class=Link,
                   ready: float = 3.0, say=_say, show: int = 20, expected=frozenset(), keys: bool = False) -> int | None:
    """After an upload the camera restarts: wait `settle` s, reconnect (`tries` times, `pause` s apart), give it
    `ready` s more, download and count the records that differ from `start`, saying the first `show` of them (0: the
    count only, for a run whose start file holds a value it never prints; with keys, their keys too: said_keys); None
    when no connection came. The records `expected` names (ended) are said by key and not counted."""
    time.sleep(settle)
    for attempt in range(tries):
        try:
            with link_class(run) as link:
                time.sleep(ready)
                ch, known = _apart(compared(start, link.download("restored"), say), expected)
                say(f"after the restore: {len(ch)} records differ from the start file{_besides(known)}")
                for c in ch[:show]:
                    say(f"   {c.key}: {c.before!r} -> {c.after!r}")
                if keys and not show:
                    said_keys(ch, say)
                return len(ch)
        except Exception as e:
            say(f"reconnect {attempt + 1} failed: {str(e)[:80]}")
            time.sleep(pause)
    return None


def check_restore(run, ending: Ending | None, start: Path, **kw) -> int | None:
    """The records that differ from `start` once the session has ended: 0 when nothing had changed, the count after
    the restore when the start file was uploaded, None when it is not known (no download at the end, or no
    reconnection): a caller treats anything but 0 as a restore that did not check out."""
    if ending is None or ending.after is None:
        return None
    return verify_restore(run, start, **kw) if ending.uploaded else 0
