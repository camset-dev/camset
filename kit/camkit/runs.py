"""Run folders: evidence numbering that never overwrites, the STOP file, and an event log.

A run folder, runs/<model>_fw<fw>/<name>/ (the camera's run root, camkit.paths), holds shots/NNNNN_tag.png,
dat/NNNNN_tag.DAT and events.jsonl. Numbers continue from the highest number already in the folder, so resuming a
run never overwrites earlier evidence. Create the run's STOP file, runs/<model>_fw<fw>/<name>/STOP (or
runs/<model>_fw<fw>/STOP for every run of that camera, runs/STOP for every run) to stop a run cleanly; the walker
cancels any open dialog before it exits, because a dropped session applies the dialog on screen. Ctrl-C (or a
tool's SIGTERM) while a camera link is open does the same: request_stop (camkit.link catches the signal).
"""
import contextlib
import json
import os
import re
import stat
import sys
import threading
import time
from pathlib import Path

from . import jsonl, paths

_NUMBERED = re.compile(r"^(\d{5,})_")          # five digits, more past 99999 (2026-10-29)
MAIN_RUN = "kit2_pass2"         # the camera's main proof run, which kit/schema_update.py writes the definition from
# a run folder holding this file is one of the camera's proof runs: kit/pass2_report.py reads its proofs.jsonl beside the
# main run's (mark_proof_run). A prover that keeps its proofs in a run of its own writes it (kit/provers/afreg_run.py,
# filter_run.py --run); a run made to check the kit never holds it, and removing it takes a run out of the report
PROOF_RUN = "proof_run.json"


# The file a run that may drop its link writes in the camera's run root (runs/<model>_fw<fw>/), naming its start file:
# kit/drive.py --owner, before a last press an owner decision allowed with "link_loss" (the intent, kept when that press
# may have gone: EXIT_RESTORE_BY_HAND, kit/exit_status.py). While it is there camkit.link.Link opens no link
# (restore_pending_any), so no new run starts from a camera whose settings nobody put back (docs/decisions/0015);
# kit/tools/upload_check.py puts that very file back, checks it took, and removes it (clear_restore_by_hand). Where
# CAMSET_RUNS points elsewhere it is written, looked for and removed in the clone's own runs/<model>_fw<fw>/ too
# (marker_places), so a later run with the other folder never passes it
RESTORE_BY_HAND = "RESTORE_BY_HAND.json"


def marker_places(root: Path, writing: bool = False) -> list:
    """The run roots a RESTORE_BY_HAND of the camera whose run root is `root` is kept in: `root`, and, where CAMSET_RUNS
    points elsewhere, the clone's own runs/ folder for the same camera key. Writing, that second place only for a
    camera's key (paths.KEY), never a folder of another name. A marker under another camera key names another camera,
    and is not this one's."""
    from . import RUNS
    root = Path(root)
    places = [root]
    usual = Path(RUNS) / root.name
    try:
        apart = usual.resolve() != root.resolve()
    except OSError:
        apart = True
    if apart and (not writing or paths.KEY.match(root.name)):
        places.append(usual)
    return places


def restore_pending(root: Path) -> dict | None:
    """What the camera's run root `root` says must be restored by hand first ({"run", "start", "since", "why"}), or
    None. A file that cannot be read counts as pending too: nothing then says the camera is back."""
    f = Path(root) / RESTORE_BY_HAND
    if not f.exists():
        return None
    try:
        got = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"run": None, "start": None, "since": None, "why": f"{f} cannot be read"}
    return got if isinstance(got, dict) else {"run": None, "start": None, "since": None, "why": f"{f} is not an object"}


def restore_pending_any(root: Path) -> tuple | None:
    """(the run root holding it, what it says) of the RESTORE_BY_HAND that keeps a camera unrestored, or None: looked
    for in every place marker_places names (the run root given, and the clone's own runs/ for the same camera key), so
    a run that sets CAMSET_RUNS, or one that does not after one that did, never passes a pending restore."""
    for where in marker_places(root):
        got = restore_pending(where)
        if got is not None:
            return where, got
    return None


def mark_restore_by_hand(root: Path, run: str, start: Path, why: str) -> Path:
    """RESTORE_BY_HAND written in every place marker_places names for writing: the run, its start file (relative to
    each place where it is in it, else whole) and why. Returns the run root's. A place it cannot be written in raises
    (OSError): the caller then presses nothing."""
    start, since = Path(start), time.strftime("%Y-%m-%d %H:%M:%S")
    written = []
    for where in marker_places(root, writing=True):
        try:
            shown = start.resolve().relative_to(where.resolve()).as_posix()
        except ValueError:
            shown = str(start)
        where.mkdir(parents=True, exist_ok=True)
        f = where / RESTORE_BY_HAND
        f.write_text(json.dumps({"run": run, "start": shown, "since": since, "why": why}, indent=1) + "\n",
                     encoding="utf-8", newline="\n")
        written.append(f)
    return written[0]


def clear_restore_by_hand(root: Path) -> bool:
    """RESTORE_BY_HAND removed from every place marker_places names (once its start file is back, checked, or the press
    it was written for was refused before it went). True when one was there."""
    gone = False
    for where in marker_places(root):
        f = Path(where) / RESTORE_BY_HAND
        if f.exists():
            f.unlink()
            gone = True
    return gone


def mark_proof_run(run_dir: Path, by: str) -> bool:
    """Mark a run folder (not the main run) as one of the camera's proof runs (PROOF_RUN), saying which tool marked it
    and when; a mark already there stays. True when the folder is marked now."""
    run_dir = Path(run_dir)
    if run_dir.name == MAIN_RUN:
        return False
    f = run_dir / PROOF_RUN
    if not f.exists():
        f.write_text(json.dumps({"by": by, "since": time.strftime("%Y-%m-%d")}) + "\n", encoding="utf-8", newline="\n")
    return True


# A private run's folder (a --network or --owner run: its frames, its drive.jsonl and its downloads can hold addresses,
# credentials or values the owner chose to log, 2026-11-14): its folders 0700 and every file in it 0600, on POSIX. On
# Windows the modes are left as they are: the folder is the user's own profile's (docs/decisions/0009)
PRIVATE_DIR, PRIVATE_FILE = 0o700, 0o600
# the umask a private run sets for its process, whatever the person's own umask (os.umask): every file the run, its
# eyes, its OCR and the camera's helper (which inherits it) create is 0600 and every folder 0700; kit/runner.write_text
# reads it, so a file it writes new is no looser. 0 until a private run starts
UMASK_FLOOR = 0
POLL_LEFT = ("_live.png", "_live.png.part")     # the eyes' polling target at the top of a run folder (camkit.frames)


def private_modes() -> bool:
    """Whether this system takes POSIX modes (a private run's are set there alone)."""
    return os.name == "posix"


class Run:
    def __init__(self, name: str, root: Path = None, private: bool = False):
        """root: the camera's run root (camkit.paths.run_root()) unless given. private: a --network or --owner run's
        folder (PRIVATE_DIR, PRIVATE_FILE): the process's umask set to 0077 before anything is written, the folder and its
        subfolders made 0700 and what an earlier run left in it 0600; seal() checks it at the run's end."""
        self.root = Path(root) if root is not None else paths.run_root()
        self.dir = self.root / name
        self.shots = self.dir / "shots"
        self.dat = self.dir / "dat"
        self.private = False
        if private:
            self.make_private()
        for d in (self.shots, self.dat):
            d.mkdir(parents=True, exist_ok=True)        # 0700 on a private run: its umask is set
        self._lock = threading.Lock()
        self._n = self._highest()
        self._stop_why = None                  # a stop asked for in this process (a signal), not by a file
        # a STOP file already there when the run starts is left from an earlier stop: the run refuses its first press
        # (StopRequested, naming the file) and says so now, rather than stopping without a word
        self._left = [p for p in (d / "STOP" for d in self._stop_dirs()) if p.exists()]
        for p in self._left:
            print(f"{p} is there from an earlier stop: a run presses nothing while it is there. Remove it to run.",
                  file=sys.stderr, flush=True)
            self.log("stop_left_over", path=str(p))

    def make_private(self) -> list:
        """The run made private (a --network or --owner run, decided once its flags are read, before its link opens or
        anything is written in its folder but the folders themselves): on POSIX the process's umask set to 0077 or
        tighter (UMASK_FLOOR), whatever the person's own, and the folder made owner-only now (tighten). The paths
        tightened."""
        global UMASK_FLOOR
        self.private = True
        if not private_modes():
            return []
        UMASK_FLOOR = 0o077
        os.umask(os.umask(0o077) | 0o077)           # read and set at once: tighter than before, never looser
        return self.tighten()

    def tighten(self) -> list:
        """A private run's folder made owner-only, on POSIX: every folder in it 0700 and every file 0600 (symbolic links
        left as they are, never followed). The paths whose modes were looser, relative to the folder; [] elsewhere."""
        if not private_modes() or not self.dir.is_dir():
            return []
        fixed = []
        for p in [self.dir, *sorted(self.dir.rglob("*"))]:
            try:
                if p.is_symlink():
                    continue
                st = p.stat()
                want = PRIVATE_DIR if p.is_dir() else PRIVATE_FILE
                if stat.S_IMODE(st.st_mode) & 0o077:
                    os.chmod(p, want)
                    fixed.append(p.relative_to(self.dir).as_posix() or ".")
            except OSError:
                continue
        return fixed

    def seal(self) -> list:
        """A private run's end: the eyes' polling target left at the top of the folder taken away (POLL_LEFT: a real
        frame of whatever was polled last), then the folder checked (tighten), and anything that was group- or
        world-readable fixed and said. The paths fixed; [] for a run that is not private."""
        if not self.private:
            return []
        for name in POLL_LEFT:
            with contextlib.suppress(OSError):
                (self.dir / name).unlink()
        fixed = self.tighten()
        if fixed:
            print(f"{len(fixed)} path(s) in {self.dir.name} were readable by other users and are owner-only now: "
                  f"{', '.join(fixed[:6])}{' ...' if len(fixed) > 6 else ''}", flush=True)
            self.log("private_modes_fixed", paths=fixed[:50], count=len(fixed))
        return fixed

    def _highest(self) -> int:
        top = 0
        for d in (self.shots, self.dat):
            for f in d.iterdir():
                m = _NUMBERED.match(f.name)
                if m:
                    top = max(top, int(m.group(1)))
        return top

    def _next(self) -> int:
        with self._lock:
            self._n += 1
            return self._n

    def shot_path(self, tag: str) -> Path:
        return self.shots / f"{self._next():05d}_{_safe(tag)}.png"

    def dat_name(self, tag: str) -> str:
        """Base name (no extension) for the next settings download in self.dat."""
        return f"{self._next():05d}_{_safe(tag)}"

    def log(self, kind: str, **fields):
        with self._lock:
            jsonl.append(self.dir / "events.jsonl", {"t": round(time.time(), 3), "kind": kind, **fields})

    def request_stop(self, why: str):
        """Stop as a STOP file would: the next press raises StopRequested, and the run cancels and restores."""
        if not self._stop_why:
            self._stop_why = why
            self.log("stop_requested", why=why)

    def stop_requested(self) -> bool:
        return bool(self._stop_why) or any((d / "STOP").exists() for d in self._stop_dirs())

    def stop_reason(self) -> str:
        """Why the run stops, in words: the signal, or the STOP file (and whether it was there before the run)."""
        if self._stop_why:
            return self._stop_why
        for p in (d / "STOP" for d in self._stop_dirs()):
            if p.exists():
                return (f"{p} was there before this run started (an earlier stop): remove it to run"
                        if p in self._left else f"{p} asks the run to stop")
        return ""

    def _stop_dirs(self):
        yield self.dir
        yield self.root
        if paths.KEY.match(self.root.name):            # a camera's folder: runs/STOP stops every camera's runs
            yield self.root.parent


def _safe(tag: str) -> str:
    return re.sub(r"[^A-Za-z0-9.+-]+", "-", tag).strip("-")[:40] or "x"
