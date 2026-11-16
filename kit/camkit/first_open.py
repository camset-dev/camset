"""A menu row's first open on a body: a row the kit has not yet seen opened on this camera may drop the link or act as
it opens (IP Address Setting dropped the a1 II's wired LAN link when opened and left with MENU, 2026-11-14), so its first
open goes under the link-loss procedure (docs/decisions/0015): RESTORE_BY_HAND written before the press (camkit.runs: no
link opens while it is there), a look saying the open is not yet checked (PENDING) written before it too, the row looked
at and left with MENU, then the settings downloaded and compared with the run's start file. Only when the link answered
and no record differs is the marker taken away and the row's clean look written, which makes the next open a plain one.
A lost link or a record that differs leaves the marker, and the run exits EXIT_RESTORE_BY_HAND saying what the owner
does. Such a run needs the owner's blank-cards statement (camkit.statements); without it each unseen row is skipped and
recorded (SKIPPED). It lifts no guard.

Seen opened, on the camera's own records (seen_record): its looks file (camkit.coverage: a look that opened the row,
"looked" or "no_change", or chose in it, "no_change" or "changed"; a look retracted counts for nothing), its crawls'
rows.jsonl (an outcome whose screen opened and was left, OPENED) and its proofs.jsonl (a proof chose in the row), each
row seen with the rows above it, told by its labels from the top-level row compared as safety.plain compares them, in
any tab and mode. The row's latest open look overrides them: "changed" or "acted" (a first open that failed: ACTED) and
a first open not yet checked, or one a page's check could not clear (not_reached with PENDING or PAGE), leave it unseen.
A clean check writes its clean look before the crawl's look of the row where that one does not say the opening was seen
but shows the Right left the row's page for a screen of its own (own_screen), whatever the kit made of it: on
2026-11-15 the a1 II's Cont. Play for Interval showed its playback view, an unknown screen, and came under the
procedure on every lap. The crawl's look stays the ledger's latest (kit cannot read), and seen_record reads the clean
one. A notice, a Right that did nothing or a look that did not reach the row leaves it unseen.
A look's did is "open" only where nothing but up, down and MENU followed the opening press (kit/drive.py's look:
camkit.coverage.drive_look); a run that pressed anything else inside the row chose, and a record a choice changed leaves
the row seen (2026-11-15: a slider moved and cancelled on a row seen opened many times made it unseen).
A crawl skips a row whose first open failed (only kit/drive.py --press right opens it again) and opens a row a page's
check could not clear alone, asking under its label and the name a look lap keeps of it; a failure under a placeholder
(placeholder()), a name rows share, stands until retracted, whatever look follows it. A row the records hold greyed
whose Right brings up a notice again costs no download of its own: the link is asked, the marker stays, and the next
check or the run's end download clears it with the rest (a record that then differs makes each such row one a page's
check could not clear).
"""
import time
from pathlib import Path

from . import coverage, jsonl, paths, safety
from .link import StopRequested
from .runs import clear_restore_by_hand, mark_restore_by_hand

SEEN_RESULTS = {"open": ("looked", "no_change"), "choose": ("no_change", "changed")}
ACTED = ("changed", "acted")
# camkit.crawl.visit_row's outcomes of a row whose own screen opened and was left with the crawl back on its row
OPENED = ("walked", "submenu", "left for kit/table_walk.py", "network row:", "notice passed", "unknown screen")
PENDING = "first open, not yet checked"
PAGE = "a page's first-open check found a record that differed: opened alone next"
# a crawl's row a first open's rule left out, recorded so (camkit.coverage.crawl_skipped and kit/pass1_map.py count it)
UNSEEN = "not seen opened on this body"           # opening()'s refusals lead with it
SKIPPED = f"skipped: {UNSEEN}"


def key(path) -> tuple:
    return tuple(safety.plain(str(x)) for x in path or ())


def _with_parents(k: tuple) -> set:
    return {k[:i] for i in range(1, len(k) + 1)}


class Seen:
    """The rows seen opened on one camera (seen_record): seen(path) and unseen(path) (the path's prefixes that are not,
    a row above first); acting, the rows whose first open failed; alone, the rows a page's check could not clear;
    greyed, the rows the records hold greyed. A path with a label read as nothing (a page model row no vote named) or a
    placeholder is never seen: one such row's clean first open would else stand for every other."""

    def __init__(self, opened=(), acting=(), unchecked=(), alone=(), greyed=()):
        self.opened, self.acting, self.unchecked = set(opened), set(acting), set(unchecked)
        self.alone, self.greyed = set(alone), set(greyed)

    def seen(self, path) -> bool:
        k = key(path)
        return (bool(k) and all(k) and not placeholder(k) and k in self.opened and k not in self.acting
                and k not in self.unchecked)

    def unseen(self, path) -> list:
        return [tuple(path[:i]) for i in range(1, len(path or ()) + 1) if not self.seen(path[:i])]

    def skips(self, path, skip_why: str) -> bool:
        """Whether a lap leaves the row at `path` unopened by the first open's rule, as FirstOpens.opening refuses it
        before writing anything: not seen, and its first open failed or the run makes none (`skip_why`)."""
        return not self.seen(path) and (key(path) in self.acting or bool(skip_why))

    def lit_row(self, parent, lit: str, known=()) -> tuple | None:
        """The path of the row a lit bar's text `lit` names under `parent` (labels from the top-level row): the longest
        label of `known` (the labels the kit knows) or of a row seen under `parent` that the text starts with, alone or
        before what is no letter or digit of a longer word (a value after it); None when none is."""
        seen = safety.plain(lit or "")
        here = key(parent)
        names = {safety.plain(x) for x in known if isinstance(x, str)}
        names |= {k[-1] for k in self.opened if len(k) == len(here) + 1 and k[:-1] == here}
        hits = [n for n in names if n and seen.startswith(n) and not seen[len(n):len(n) + 1].isalnum()]
        return (*parent, max(hits, key=len)) if hits else None


def placeholder(k) -> bool:
    """Whether a path (labels) holds a placeholder a withholding run writes for a label it does not keep ("(withheld)":
    kit/crawl_run.py kept_label): such a path is never seen, so a clean first open runs again on the next lap; one
    that failed, or that a page's check could not clear, stands for every row written under it until retracted
    (seen_record)."""
    return any(str(x).startswith("(") for x in k or ())


def own_screen(look: dict) -> bool:
    """Whether a pending row's look the coverage gate held (FirstOpens.takes) shows its Right left the row's page for a
    screen of the row's own: a screen kind recorded that is no row page (safety.ROW_PAGES: a Right that did nothing
    proves nothing of opening the row later), the result neither a notice's (greyed) nor one that did not reach the
    row (not_reached: a walk cut short, a lost row, of which the looks file says nothing)."""
    kind = look.get("screen")
    return bool(kind) and kind not in safety.ROW_PAGES and look.get("result") not in ("greyed", "not_reached")


def _crawl_rows(row: dict, parent: tuple, opened: set, greyed: set) -> None:
    label = row.get("decided") or row.get("label") or ""
    if not isinstance(label, str) or not label.strip() or label.startswith("("):
        return
    k = (*parent, safety.plain(label))
    out = str(row.get("outcome") or "")
    if out.startswith(OPENED):
        opened |= _with_parents(k)
    elif coverage.refused_notice(out):
        greyed.add(k)
    for sub in row.get("submenu") or []:
        if isinstance(sub, dict):
            _crawl_rows(sub, k, opened, greyed)


def seen_record(camera: str | None = None) -> Seen:
    """The rows seen opened on the camera `camera` (by default the one the kit works on), from its own records (the
    module's docstring); none for a camera with no records yet, a new body."""
    camera = camera or (paths.camera() or (None,))[0]
    if not camera:
        return Seen()
    looks = coverage.read_looks(camera)
    gone = set(coverage.retracted(looks))
    opened, greyed, latest = set(), set(), {}
    stuck = {"acting": set(), "alone": set()}
    for _line, lk in looks:
        k, did, res = key(lk.get("path")), lk.get("did"), lk.get("result")
        if k and placeholder(k):
            # a name rows share (placeholder()): never seen or greyed; a first open that failed under it, or that a
            # page's check could not clear, stands whatever look follows, until a retraction (read in the file's order)
            if did == "open" and res == "retract":
                stuck["acting"].discard(k)
                stuck["alone"].discard(k)
            elif did == "open" and res in ACTED:
                stuck["acting"].add(k)
            elif did == "open" and res == "not_reached" and lk.get("note") == PAGE:
                stuck["alone"].add(k)
            continue
        if not k or (k, did) in gone:
            continue
        if res in SEEN_RESULTS.get(did, ()):
            opened |= _with_parents(k)
        if res == "greyed":
            greyed.add(k)
        # the latest open look that says how an opening went: clean, acted, or a first open's own not_reached (a notice,
        # a kit's failure or a plain not_reached says nothing of it)
        if did == "open" and (res in ACTED or res in SEEN_RESULTS["open"]
                              or (res == "not_reached" and lk.get("note") in (PENDING, PAGE))):
            latest[k] = lk
    root = paths.runs_top() / camera
    for run in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else ():
        for row in jsonl.read(run / "rows.jsonl", bad="skip"):
            _crawl_rows(row, (), opened, greyed)
        for proof in jsonl.read(run / "proofs.jsonl", bad="skip"):
            if isinstance(proof.get("path"), list) and key(proof["path"]):
                opened |= _with_parents(key(proof["path"]))
    return Seen(opened, {k for k, lk in latest.items() if lk.get("result") in ACTED} | stuck["acting"],
                {k for k, lk in latest.items() if lk.get("result") == "not_reached"},
                {k for k, lk in latest.items() if lk.get("note") == PAGE} | stuck["alone"], greyed)


IDENTITY = ("ModelName", "SoftwareVersion")       # the SDK's properties a camera's key is made of (kit/tools/identify.py)


def other_body(link, camera: str) -> str:
    """Why the camera at the end of `link` is not the one whose key `camera` names, or "": its ModelName and
    SoftwareVersion, read from the SDK's properties as kit/tools/identify.py reads them (the run's log keeps neither,
    nor any other property: their list holds the serial number), make another key, or cannot be read. A second body run
    from the same clone never reads the first's records; a camera camlink built from the address (its --model) says its
    own model all the same. A run folder not named by a camera's key (a test's) is not judged."""
    if not paths.KEY.match(str(camera or "")):
        return ""
    try:
        reply = link.call("props", timeout=60, logged=lambda r: {"ok": r.get("ok"), "asked": list(IDENTITY)})
        props = {str(p.get("name") or "").removeprefix("CrDeviceProperty_"): str(p.get("text") or "").strip()
                 for p in reply.get("props") or [] if isinstance(p, dict)}
    except Exception as e:      # noqa: BLE001 (a camera that cannot say which it is: no run on it)
        props, reply = {}, {"error": f"{type(e).__name__}: {e}"}
    model, firmware = (props.get(n, "") for n in IDENTITY)
    if not model or not firmware:
        why = reply.get("error") or "no ModelName or SoftwareVersion among its properties"
        return f"the camera did not say its model and firmware ({why}), so it cannot be told to be {camera}"
    if paths.key(model, firmware) != camera:
        return (f"the camera connected is {paths.key(model, firmware)}, and the kit works on {camera}: name the "
                "connected camera (private/config.json's \"camera\", or --camera), so its own records are the ones read")
    return ""


def failed_look(camera: str, run: str, path, result: str, records=(), note=None, private: bool = False) -> bool:
    """A first open's look (result "changed" with the records that differ, "acted" with the link gone, or not_reached
    with PENDING or PAGE): the row's latest open look, which keeps it unseen (Seen)."""
    return coverage.append_look(camera, {"t": coverage.now(), "run": run, "kit": coverage.kit_commit(), "by": "crawl",
                                         "path": [str(x) for x in path], "option": None, "did": "open",
                                         "result": result, "records_changed": [k for k in records
                                                                              if coverage.RECORD_KEY.match(k)],
                                         "note": note}, private=private)


class FirstOpenFailed(RuntimeError):
    """A first open's check did not come out clean: `changes`, the keys of the records that differ from the run's start
    file; none where the check itself failed (the link, the download). RESTORE_BY_HAND stays."""

    def __init__(self, why: str, changes=()):
        super().__init__(why)
        self.changes = list(changes)


class FirstOpens:
    """camkit.crawl's `first`, for kit/crawl_run.py: opening(path) before each Right on a row; takes(look), the coverage
    gate's hold on a pending row's look until its check; due(pos, next) and settle(cam) after a top-level row's visit
    (per "row", or per "page": the check made once the lap leaves the page, a row a page's check could not clear
    checked alone); ended(restored, ending) at the run's end. `seen`: seen_record's; `skip_why`: why no first open is
    made on this run (no current blank-cards statement, --panels), "" when they are; `lock`: the menu's lock after a
    download (proving.base.LOCK_S); `wait`: camkit.session.wait_for; `leave`: proving.nav.leave_playback (None: that
    one, found when first needed)."""

    def __init__(self, link, eyes, run, start: Path, seen: Seen, skip_why: str, lock: float, wait=None,
                 private: bool = False, per: str = "row", name=None, leave=None):
        from .session import wait_for
        self.link, self.eyes, self.run, self.start = link, eyes, run, Path(start)
        self.seen, self.skip_why, self.lock, self.private, self.per = seen, skip_why, lock, private, per
        self.wait, self.leave = wait or wait_for, leave
        self.marker, self.pending, self.deferred, self.notices = None, [], [], set()
        self.failure, self.failed = "", []         # why a check failed, and the rows it was for: the marker stays
        self.held = []                              # rows greyed again: checked by the next download, or the run's end
        # what a look lap writes of a label (kit/crawl_run.py kept_label: the label it knows, or its placeholder) in
        # events.jsonl, the looks file, RESTORE_BY_HAND and the console; the label as read stays in memory (pending)
        self.name = name

    def kept(self, path) -> list:
        """The path as this run writes it: each label as `name` keeps it (a look lap's), else as given."""
        return [self.name(str(x)) if self.name else str(x) for x in path]

    def _failed_before(self, path) -> bool:
        """Whether the records hold a failed first open of the row at `path`, under its label or the name kept of it."""
        return key(path) in self.seen.acting or key(self.kept(path)) in self.seen.acting

    def _look(self, path, result, **kw) -> bool:
        return failed_look(self.run.root.name, self.run.dir.name, self.kept(path), result, private=self.private, **kw)

    def skips(self, path) -> bool:
        """Whether opening(path) refuses the row with nothing written (Seen.skips, the name kept of it asked too), asked
        before it (camkit.crawl's left_unopened: the coverage gate's line then never says the row is opened)."""
        return self.seen.skips(path, self.skip_why) or (not self.seen.seen(path) and self._failed_before(path))

    def opening(self, path) -> str | None:
        """Before Right on the row at `path` (labels from the top-level row): None to open it, the row then pending
        until settle (RESTORE_BY_HAND and its PENDING look written first), or why it is skipped, nothing pressed (UNSEEN
        leads it; camkit.crawl's outcome is then SKIPPED): a row whose first open failed, a run that makes no first open,
        a marker or a look not written."""
        if self.seen.seen(path):
            return None
        if self._failed_before(path):
            if self.kept(path) != [str(x) for x in path]:      # a name withheld: no label as read in what is written
                return (f"{UNSEEN} (a first open under the name kept of it, which rows share, changed a record or lost "
                        "the link: kit/drive.py --path with the row's own name and --press right opens it again)")
            return (f"{UNSEEN} (its first open changed a record or lost the link: kit/drive.py --path "
                    f"{' --path '.join(map(repr, path))} --press right opens it again)")
        if self.skip_why:
            return f"{UNSEEN} ({self.skip_why})"
        if self.marker is None:
            try:
                self.marker = mark_restore_by_hand(self.run.root, self.run.dir.name, self.start,
                                                   f"the first open of {' > '.join(self.kept(path))!r} on this body "
                                                   "may drop the link or act")
            except Exception as e:      # noqa: BLE001 (any place unwritten: nothing is pressed, what was written goes)
                clear_restore_by_hand(self.run.root)
                return f"{UNSEEN} (RESTORE_BY_HAND could not be written: {type(e).__name__}: {e})"
        if not self._look(path, "not_reached", note=PENDING):
            if not self.pending and not self.held:
                clear_restore_by_hand(self.run.root)
                self.marker = None
            return f"{UNSEEN} (its pending look could not be recorded)"
        self.pending.append(tuple(path))
        self.run.log("first_open", path=self.kept(path), marker=str(self.marker))
        return None

    def not_opened(self, path) -> None:
        """The Right opening() let through for `path` was refused before it went out (safety.RowRefused): the row is no
        longer pending, and with nothing else pending the marker goes, since nothing was pressed."""
        if tuple(path) in self.pending:
            self.pending.remove(tuple(path))
            if not self.pending and not self.held and not self.failure and self.marker is not None:
                clear_restore_by_hand(self.run.root)
                self.marker = None

    def takes(self, look: dict) -> bool:
        """camkit.coverage.CrawlGate.after's hold: a pending row's look is kept back until its check comes out clean
        (True); a pending row the records hold greyed whose look says greyed again is noted as no first open."""
        k = key(look.get("path"))
        if not any(key(p) == k for p in self.pending):
            return False
        if look.get("result") == "greyed" and k in self.seen.greyed:
            self.notices.add(k)
        self.deferred.append(look)
        return True

    def due(self, pos: dict, nxt) -> bool:
        """Whether the pending first opens are checked after the top-level row at `pos` (`nxt`: the next position, None
        at the lap's end): per row always; per page once the lap leaves the page, and at once for a row a page's check
        could not clear."""
        if self.per != "page" or nxt is None or nxt.get("page") != pos.get("page"):
            return True
        return any(key(p) in self.seen.alone or key(self.kept(p)) in self.seen.alone for p in self.pending)

    def settle(self, cam) -> None:
        """The pending first opens checked, the crawl back on its row's page. Where every pending row brought up its
        greyed notice again, the link is asked (ping) and the rows are held, the marker kept, for the next check or the
        run's end (ended): no download of their own. Else MENU closes the menu, the
        settings are downloaded on the shooting screen and compared with the start file (the body's volatile records
        aside); with none differing the marker goes, the held looks are written (the rows are seen) and after `lock` s
        MENU reopens the menu, where crawl() checks the position. Where MENU leaves the camera on its playback view
        (camkit.session.wait_for gives "playback": a Playback row's own screen, where the camera refuses a download), the
        view is left first (leave: proving.nav.leave_playback, the Playback button once); one not left, or a camera that
        still says it is in Playback just before the download (camkit.session.in_playback_now, whatever the screen
        reads as), is a check that cannot be made, no download asked. Raises FirstOpenFailed, the marker kept, when a record
        differs (each row's look says "changed", or PAGE where the rows of a page cannot be told apart) or the check
        cannot be made; a STOP leaves them pending for the run's end (ended)."""
        from .session import PLAYBACK_HELD, compared, in_playback_now
        rows = list(self.pending)
        if all(key(p) in self.notices for p in rows):
            try:
                answer = self.link.call("ping", timeout=10)
            except Exception as e:      # noqa: BLE001
                answer = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if answer.get("ok") and answer.get("connected", True):
                for lk in self.deferred:
                    coverage.append_look(self.run.root.name, lk, private=self.private)
                self.held += rows
                self.run.log("first_open_held", paths=[self.kept(p) for p in rows], how="greyed again")
                self.pending, self.deferred = [], []
                return
        try:
            cam.press("menu")
            seen = self.wait(self.eyes, ("shooting", "playback"), "a first open's check", link=self.link)
            if seen == "playback" and not self.left_playback():
                raise RuntimeError("the camera stayed in its playback view, where it refuses a settings download")
            if in_playback_now(self.link):          # whatever the screen read as: no download in Playback
                raise RuntimeError(f"{PLAYBACK_HELD}: no download was asked")
            after = self.link.download("first-open")
            changes = compared(self.start, after, say=lambda m: None)
        except StopRequested:
            raise                       # still pending: the run's end decides by its own download (ended)
        except Exception as e:
            self.failure = f"its check could not be made ({type(e).__name__}: {e})"
            self.failed, self.pending, self.deferred = self.held + rows, [], []
            raise FirstOpenFailed(self.failure) from e
        if changes:
            keys = [c.key for c in changes]
            self._fail(rows, keys)
            self.failure = f"{len(keys)} records then differed from the start file ({', '.join(keys[:8])})"
            raise FirstOpenFailed(self.failure, keys)
        self._clean(rows, "checked")
        time.sleep(self.lock)
        cam.press("menu")

    def left_playback(self) -> bool:
        """The camera's playback view left (leave, by default proving.nav.leave_playback, found here: camkit stays free
        of the provers' parts until it needs one): its answer."""
        leave = self.leave
        if leave is None:
            from proving.nav import leave_playback as leave
        return bool(leave(self.link, self.eyes))

    def _clean(self, rows, how: str) -> None:
        """The check of `rows` (the pending rows) came out clean, at settle or at the run's end (ended): each row's clean
        look ("looked", note "first open checked", under the path opening() recorded its pending look by) written where
        _seen_now says so, then the held looks after them, and the marker taken away. The clean look goes first so that
        the ledger's latest look of the row stays the crawl's (camkit.coverage.latest_looks: an unknown screen stays
        "kit cannot read"), while seen_record reads the clean one (a kit_failed look says nothing of the opening)."""
        for p in rows:
            if self._seen_now(p):
                self._look(p, "looked", note="first open checked")
        for lk in self.deferred:
            coverage.append_look(self.run.root.name, lk, private=self.private)
        clear_restore_by_hand(self.run.root)
        self.run.log("first_open_checked", paths=[self.kept(p) for p in self.held + rows], how=how)
        self.seen.opened |= {key(p) for p in rows if key(p) not in self.notices and not placeholder(self.kept(p))}
        self.marker, self.pending, self.deferred, self.notices, self.held = None, [], [], set(), []

    def _seen_now(self, p) -> bool:
        """Whether a clean check writes the pending row `p` its own clean look: never a row whose Right brought up a
        notice the records hold (notices); else where the coverage gate held no look of it (its label withheld on a look
        lap, kit/crawl_run.py kept_row: docs/decisions/0024), or none of its held looks says the opening was seen and
        each shows a screen of the row's own (own_screen): an unknown screen counts, whatever the kit made of it."""
        if key(p) in self.notices:
            return False
        held = [lk for lk in self.deferred if key(lk.get("path")) == key(self.kept(p))]
        return not any(lk.get("result") in SEEN_RESULTS["open"] for lk in held) and all(map(own_screen, held))

    def _fail(self, rows, keys) -> None:
        """The looks of rows whose check found `keys` differing: "changed" where they are one top-level row's (its
        submenu's with it), PAGE where several top-level rows, or rows held greyed again, were checked at once and
        cannot be told apart."""
        rows = self.held + list(rows)
        one = len({key(p)[:1] for p in rows}) == 1 and not self.held
        for p in rows:
            if one:
                self._look(p, "changed", records=keys)
            else:
                self._look(p, "not_reached", note=PAGE)
        self.failed, self.pending, self.deferred, self.held = rows, [], [], []

    def lost(self, why: str) -> None:
        """The link went while a first open was pending, held or being checked: the row open when it went (the last
        pending, else the last checked) says it acted, the others PAGE (none can be blamed), and the owner is told what
        to do. The marker stays."""
        rows = self.held + self.pending + self.failed
        last = (self.pending or self.failed or [None])[-1]
        for p in rows:
            if p == last:
                self._look(p, "acted", note="the link went during its first open")
            else:
                self._look(p, "not_reached", note=PAGE)
        print(owner_words([self.kept(p) for p in rows] or ["(a row)"], why, self.marker, self.start, self.run),
              flush=True)

    def ended(self, restored: bool, ending) -> bool:
        """At the run's end, while the marker is still there: after a failed check (settle) it stays; with first opens
        still pending (a crawl stopped before their check) it goes, their held looks written, when the start file is
        back and checked and no record differs, the end's own download being the check. Where it stays the owner is told
        what to do. True when it stays."""
        if self.marker is None:
            return False
        changes = [c.key for c in getattr(ending, "changes", None) or []]
        back = "the start file is back and checked" if restored else "the start file was not put back and checked"
        if self.failure:
            print(owner_words([self.kept(p) for p in self.failed], f"{self.failure}; {back}", self.marker, self.start,
                              self.run), flush=True)
            return True
        rows = list(self.pending)
        if restored and getattr(ending, "after", None) is not None and not changes:
            self._clean(rows, "at the run's end")
            return False
        self._fail(rows, changes)
        rows = self.failed
        why = f"{len(changes)} records differed from the start file at the run's end; {back}" if changes else back
        print(owner_words([self.kept(p) for p in rows] or ["(a row)"], why, self.marker, self.start, self.run),
              flush=True)
        return True


def owner_words(rows, why: str, marker, start: Path, run) -> str:
    """What the owner is told when a first open leaves RESTORE_BY_HAND: what happened, then what they do."""
    names = ", ".join(repr(" > ".join(r) if isinstance(r, (list, tuple)) else str(r)) for r in rows)
    try:
        shown = Path(start).relative_to(run.root).as_posix()
    except ValueError:
        shown = str(start)
    return (f"the first open of {names} on this body: {why}. {marker} names the start file, and no run opens a link "
            "until it is back. Look at the camera first: whatever it still shows is closed there by hand, with MENU or "
            "Cancel, never OK. Once the camera is reachable again, put the start file back with\n"
            f"  .venv/bin/python -u kit/tools/upload_check.py {shown}\n(docs/decisions/0015)")
