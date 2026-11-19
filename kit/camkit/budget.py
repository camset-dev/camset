"""A run's start, timed: how long each piece of the work a runner does before its link opens took (the page scan's
screens, the rows seen opened, the readers' check, the eyes, the coverage ledger, the link's own open), so that a slow
start is measured, not guessed (the speed review of 2026-11-18 could only estimate the 17.4 s a one-press look spent
before its link opened). Each phase is timed where the kit's shared start work is done (runner.load_scan,
camkit.first_open.seen_record, camkit.vlm.check_readers, camkit.frames.eyes_from_config, camkit.coverage.ledger_for),
so every runner's start is timed alike; camkit.link writes what has been timed into the run's events.jsonl as each
link opens ("start_budget", after "link_open"), and a runner that waits for a phase after that (the ledger, built on a
thread of its own while the link opens: camkit.coverage.warm) writes the rest with report().

    with phase("page scan"): ...         a phase, timed (several of one name add up); @timed("eyes") times a function
    note("page scan", "cached")          a word about a phase (a cache's hit)
    main_started()                       the program's own work begins: "imports", the seconds since camkit was imported
    join = beside("readers check", fn)   fn started now on a thread of its own (named so); join() waits for it and gives
                                         what it returned, or raises what it raised, a SystemExit among them, in the
                                         caller's thread ("readers check waited": how long the caller waited)
    taken()                              what has been timed since the last time, as {"phases": {name: s}, "notes": ...}
    report(run)                          taken() as one events.jsonl line ("start_budget"); nothing when nothing was

Python runs one thread at a time: work beside the start gains only while the start waits (a reader's answer over the
network, the camera's link), never against other work in Python."""
import contextlib
import functools
import threading
import time

from . import STARTED

_LOCK = threading.Lock()
_TIMED: dict = {}       # phase -> seconds since the last taken()
_NOTES: dict = {}       # phase -> a word about it


def add(name: str, seconds: float) -> None:
    with _LOCK:
        _TIMED[name] = round(_TIMED.get(name, 0.0) + max(seconds, 0.0), 3)


@contextlib.contextmanager
def phase(name: str):
    t = time.monotonic()
    try:
        yield
    finally:
        add(name, time.monotonic() - t)


def timed(name: str):
    """A function's every call timed as the phase `name` (a decorator: the shared start work's own)."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kw):
            with phase(name):
                return fn(*args, **kw)
        return inner
    return wrap


def note(name: str, word: str) -> None:
    with _LOCK:
        _NOTES[name] = word


def main_started() -> None:
    add("imports", time.time() - STARTED)


def beside(name: str, fn, *args, **kw):
    """fn(*args, **kw) started on a thread of its own named `name`; the function returned joins it (see the module's
    docstring). Nothing of fn's is timed here but the caller's wait: fn times itself where it is the kit's own."""
    box = {}

    def run():
        try:
            box["value"] = fn(*args, **kw)
        except BaseException as e:      # noqa: BLE001 (raised again in the caller's thread, a SystemExit among them)
            box["error"] = e
    th = threading.Thread(target=run, name=name, daemon=True)
    th.start()

    def join():
        with phase(f"{name} waited"):
            th.join()
        if "error" in box:
            raise box["error"]
        return box.get("value")
    return join


def taken() -> dict:
    with _LOCK:
        out = ({"phases": dict(_TIMED), **({"notes": dict(_NOTES)} if _NOTES else {})} if _TIMED or _NOTES else {})
        _TIMED.clear()
        _NOTES.clear()
    return out


def report(run, kind: str = "start_budget") -> None:
    """taken() as one line of the run's events.jsonl; a log that cannot be written changes nothing."""
    got = taken()
    log = getattr(run, "log", None)
    if got and log is not None:
        with contextlib.suppress(Exception):
            log(kind, **got)
