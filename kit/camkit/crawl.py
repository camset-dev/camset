"""Pass 1, part 2: open every safe top-level row, walk its screen by type, back out with MENU.

Camera-agnostic (press/read), so it runs on the camera and on the menu twin. The route is the page
scan's own Down cycle: every position is visited in order, so travel is one Down per position, and
before acting at a position the screen must match what the scan recorded there (predict, then
check). A mismatch stops the crawl.

At each row: skip it if it is out of scope, on the never-open list (by its confirmed label from the
page model), or the Main tile page; otherwise Right, read the screen, walk it with that type's
walker (camkit.walk), press MENU and check the row is back. Submenus are opened and their rows
crawled the same way when a label reader is given (labels for safety come from it before any
Right); without one they are recorded and left.

A Wi-Fi or Bluetooth setting, or an identity or connection row, a dated owner decision names is walked too when the
crawl is given those rows (network: kit/crawl_run.py --network, docs/decisions/0008), on network_open's terms: never an
address screen, never a row whose stored reason or any reading says another class. On a look lap (look: every
kit/crawl_run.py --network run, docs/decisions/0024) every other never-open row is walked so too, no decision naming it,
but what safety.look_lap_refused refuses in its label or any reading kept beside it, never-open or not: OWNER_NEVER's
rows and the Screen Reader, a row whose opening acts, and a format, delete or reset this body's records have not shown
opened (seen), skipped with nothing pressed. Such a row is looked at
only: Down round its list or carousel (LOOK_WALKED), never a second axis, a panel or a submenu, with --panels too, and
not even that where the camera holds MENU alone (a blanked row, an address screen, a screen naming identity); the
camera's own check (camkit.live.LiveCamera) refuses anything else there besides. A row whose Right brings up the
camera's playback view (camkit.live's reading: a screen read as the shooting screen while the camera says it is in
Playback) is left with MENU alone, never walked, "a playback view, left unwalked".

A row whose Right opens an information notice is recorded as "notice", nothing pressed on it but MENU; only where the run
names the row and the notice's words (info_ok: kit/crawl_run.py --info-ok, runner.info_ok_or_exit) is its OK taken,
once, by the caller's judgement (proving.screens.pass_named_notice), and the screen behind it walked when it is one the
walkers know (WALKERS); never on a row a network decision opened.

A row whose Right the camera refuses because of the lit row itself (safety.RowRefused, raised before the press goes
out: the lit row read as one the run may not open, or read by no reader) is skipped, "skipped: refused (...)", and the
crawl goes on: nothing was pressed on it. Any other refusal at that Right (a look-only lock still on, the link's own
guard), any refusal while a row a network decision opened is still open, and a refusal after a press on a row (inside
its walk) is raised, and the lap is cancelled (kit/crawl_run.py).
"""
from dataclasses import dataclass, field

from . import safety, screen
from .screen import same_position, same_state
from .walk import walk_axes, walk_cycle, walk_fields, walk_grid, walk_look

WALKERS = {
    "list": lambda cam: walk_cycle(cam, budget=120),
    "dialog": lambda cam: walk_cycle(cam, budget=120),
    "sidelist": lambda cam: walk_cycle(cam, budget=120),
    "checklist": lambda cam: walk_cycle(cam, budget=120),
    "checkgrid": walk_grid,
    "fields": walk_fields,
    "slider": lambda cam: walk_axes(cam, [("right", "right"), ("left", "left")]),
    "wbgrid": lambda cam: walk_axes(cam, [("right", "right"), ("left", "left"), ("up", "up"), ("down", "down")]),
    "look": walk_look,
}


@dataclass
class RowResult:
    page: str
    slot: int
    label: str
    outcome: str                    # walked | skipped: ... | notice | no response | unknown screen | error: ...
    kind: str = ""
    walk: object = None
    presses: int = 0
    # the class a network decision lifted the row from (safety.lift_class), for a row the crawl opened because one names
    # it (network_open); "" for every other row. kit/crawl_run.py writes it as "network": the batch tools that read the
    # row's frames later ask local readers only (its run folder is marked: camkit.vlm.local_only_runs), and of an
    # identity or connection row's frames keep no reader's text (kit/pass1_labels.py leaves them out)
    network: str = ""
    # a Wi-Fi or Bluetooth setting's notice, the row greyed ("This function is currently disabled."), as the kit keeps it
    # (safety.notice_kept: a notice it knows, naming no identity or credentials); on a plain crawl (no --network) any
    # row's notice, as notice_named keeps it (what it names: a blocking row's label, equipment, a remote session); ""
    # for every other row
    notice: str = ""
    # the decided row a network decision opened it as (network_row: "IP Address Setting" for a row the page model
    # labels "LANIP Address Setting"); "" for every other row. kit/crawl_run.py keeps it as the row's label on a run
    # that withholds the labels it does not know (kept_row)
    decided: str = ""
    # the information notice taken with its OK before the row's screen (--info-ok): {"row": the row named, "frame": the
    # notice's frame}; None for every other row
    info_ok: dict | None = None
    # a submenu row whose label the camera draws an icon before (icon_entry): page_model.icon_label's record, the label as
    # read, OCR's reading right of the icon, and what was left out of the label, or "kept" with why; None for any other
    icon: dict | None = None


@dataclass
class Crawl:
    rows: list = field(default_factory=list)
    presses: int = 0
    stopped: str = ""
    recoveries: list = field(default_factory=list)     # positions where the menu had closed by itself


def _at(s, pos: dict) -> bool:
    """Whether a screen is the one the scan recorded at a position: its screen, matched as a place in the Down cycle,
    else its exact signature."""
    return same_position(s, pos["screen"]) if "screen" in pos else s.signature == pos["signature"]


class Counted:
    """Wraps a camera to count presses."""

    def __init__(self, cam):
        self.cam, self.presses = cam, 0

    def press(self, key, **kw):
        self.presses += 1
        self.cam.press(key, **kw)           # kw: the camera's (a notice --info-ok names: notice_ok)

    def read(self):
        return self.cam.read()

    def __getattr__(self, name):          # anything else (the live camera's current frame...) passes through
        return getattr(self.cam, name)


LAP_TABS = ("Shooting", "Exposure/Color", "Focus", "Network", "Setup")      # the tabs a lap crawls unless told


def lap_rows(cycle: list, model: dict, tabs=LAP_TABS, network=frozenset(), start=None, limit=None,
             opens=None, look: bool = False, seen=None) -> list | None:
    """The names of the top-level rows a lap of crawl() reaches, in its order, each once: a menu page of `tabs`' rows
    that visit_row does not skip as never-open, a row a network decision opens by its decided name (closed_row). From
    the cycle's position `start` round to the one before it (None: the whole cycle, wherever it starts) as far as the
    row that brings the rows opened to `limit` (crawl()'s max_rows; None: no limit), a row counting toward it where
    `opens(name)` (None: every row; a row a first open's rule skips counts toward none). None where the rows reached
    depend on where the menu opens: a limit with no start. look, seen: a look lap's (closed_row)."""
    if limit is not None and start is None:
        return None
    out, opened = [], 0
    for pos in (cycle[start:] + cycle[:start]) if start is not None else cycle:
        if limit is not None and opened >= limit:
            break
        page = model.get(pos.get("page"))
        if pos.get("kind") == "tiles" or page is None or not str(page.get("breadcrumb") or "").startswith(tabs):
            continue
        rows = page.get("rows") or []
        row = rows[pos["row"]] if pos.get("row") is not None and pos["row"] < len(rows) else None
        label = (row or {}).get("label") or ""
        why, decided = closed_row(page, row or {}, network, look, seen)
        if label and not (why and decided is None):
            out.append(decided or label)
            opened += opens is None or bool(opens(decided or label))
    return list(dict.fromkeys(out))


def closed_row(page: dict, row: dict, network=frozenset(), look: bool = False, seen=None, path=()) -> tuple:
    """(why, decided) of a page model row: why it is never-open (its stored reason, else safety.never_open of its
    label; empty when it is not) and, for such a row, the decided row a network decision opens it as (network_row),
    else, on a look lap (`look`), the row's own label, else None. On a look lap a row look_open refuses, never-open or
    not, gives (the look lap's refusal, None). visit_row leaves the row unopened where there is a why and no decided
    row. seen(path): whether this body's records show the row at `path` (labels from the top-level row: `path` and the
    row's label, or a reading of it: look_open) opened (camkit.first_open.Seen.seen); None: nothing seen."""
    if look:
        refused = look_open(row, seen, path)
        if refused:
            return refused, None
    why = row.get("never_open") or safety.never_open(row.get("label") or "")
    if not why:
        return why, None
    decided = network_row(row, network, _group(page))
    if decided is None and look:
        return why, row.get("label") or None
    return why, decided


def _group(page: dict) -> str:
    """The group of a page model's page: its breadcrumb's second part ("Network > Wired LAN" is Wired LAN), or ""."""
    crumb = str(page.get("breadcrumb") or "").split(" > ")
    return crumb[1] if len(crumb) > 1 else ""


def look_open(row: dict, seen=None, path=()) -> str | None:
    """Why a look lap (docs/decisions/0024) leaves the row `row` unopened, or None: safety.look_lap_refused on its label
    or on any reading kept beside it (row_readings), a refusal in any of them winning, never-open or not, each judged
    by seen(path + its own text): whether this body's records show that row opened (None: not seen)."""
    label = row.get("label") or ""
    for t in dict.fromkeys((label, *row_readings(row))):
        why = safety.look_lap_refused(t, bool(seen and t and seen((*path, t))))
        if why:
            return why
    return None


def left_unopened(page: dict, row: dict, network=frozenset(), first=None, look: bool = False) -> bool:
    """Whether visit_row leaves the top-level row unopened, nothing pressed, by a rule known before its Right: never-open
    with no network decision opening it (closed_row), or not seen opened on this body where a first open's rule skips
    it (camkit.first_open.FirstOpens.skips). A refusal at the press itself (safety.RowRefused) is known only then."""
    why, decided = closed_row(page, row, network, look, seen_of(first))
    if why and decided is None:
        return True
    skips = getattr(first, "skips", None)
    return bool(skips and skips(((decided or row.get("label") or ""),)))


def seen_of(first):
    """The seen(path) a first open's record gives (camkit.first_open.FirstOpens' seen.seen), or None."""
    return getattr(getattr(first, "seen", None), "seen", None)


def crawl(cam, cycle: list, model: dict, tabs=LAP_TABS, stop=lambda: False, max_rows: int | None = None, on_row=None,
          labels=None, panels=False, network=frozenset(), notices=None, info_ok=None, skip=None, first=None,
          look: bool = False, refind=None) -> Crawl:
    """cycle: the page scan's positions in Down order, each {"page": key, "row": slot, "signature",
    "kind"}; model: page key -> {"breadcrumb", "page", "rows": [{"label", "never_open", ...}]}.
    max_rows: stop after opening that many rows (skipped rows do not count). on_row(result) is
    called after each row (the live run writes its results file from it). network: the Wi-Fi and Bluetooth settings a
    dated owner decision opens ({row: date}, crawl_run.py --network; network_open). notices: (read(cam), the screen's
    text now: camkit.live.text_of; the row labels the kit knows; the values it knows by row label: runner.known_labels,
    runner.row_values), for the notice such a setting answers with (visit_row); None reads none. info_ok: the notice a
    run names to pass (visit_row); None passes none. skip(page, row, opened=): why the coverage ledger says the row is
    settled (camkit.coverage.CrawlGate.skip, only on a kit/crawl_run.py --skip-settled run), or None: such a row is not
    opened, "skipped: <why>"; `opened` False where the lap leaves the row unopened all the same (left_unopened), so the
    ledger's line never says it is opened. look: a look lap (kit/crawl_run.py --network, docs/decisions/0024): a
    never-open row no decision names opens to look at where safety.look_lap_refused lets it (closed_row). first: a row's
    first open on the body (camkit.first_open.FirstOpens):
    opening(path) before each Right (visit_row), and after a top-level row whose visit left a first open pending, where
    due(), settle(cam), which checks it and reopens the menu; the lap stops where the menu is then not back on the row.
    refind(cam, pos): where it is not, the run's own way back to the position `pos`, called once (kit/crawl_run.py
    back_to_row: from a plain menu page the scan knows alone, else nothing pressed), the row then checked as before;
    None: none, the lap stops at once."""
    cam = Counted(cam)
    out = Crawl()
    opened = 0
    for i, pos in enumerate(cycle):
        if stop():
            out.stopped = "stop requested"
            break
        if max_rows is not None and opened >= max_rows:
            out.stopped = f"row limit ({max_rows}) reached"
            break
        s = cam.read()
        if not _at(s, pos) and s.kind in ("shooting", "playback"):
            # the camera left the menu by itself (2026-10-28: a CautionDisplay warning came with it, no
            # message stayed on screen): MENU reopens on the same row (the one helper: once more only after a fresh
            # look); check the position again (MENU alone on the playback view too, as while it read as the shooting
            # screen)
            from .live import menu_from_shooting
            menu_from_shooting(cam, shooting=lambda x: x.kind in ("shooting", "playback"))
            s = cam.read()
            out.recoveries.append(i)
        if not _at(s, pos):
            out.stopped = f"position {i}: the screen is not the one the scan recorded here"
            break
        page = model.get(pos["page"])
        if pos["kind"] != "tiles" and page is not None and page["breadcrumb"].startswith(tabs):
            row = page["rows"][pos["row"]] if pos["row"] is not None and pos["row"] < len(page["rows"]) else None
            settled = (skip(page, row, opened=not left_unopened(page, row, network, first, look))
                       if skip is not None and row is not None else None)
            if settled:
                out.rows.append(RowResult(page.get("page", ""), pos["row"], row.get("label") or "",
                                          f"skipped: {settled}"))
                if on_row:
                    on_row(out.rows[-1])
            elif row is not None:
                out.rows.append(visit_row(cam, s, page, pos["row"], row, labels, panels=panels, network=network,
                                          notices=notices, info_ok=info_ok, first=first, look=look))
                opened += not out.rows[-1].outcome.startswith("skipped")
                if on_row:
                    on_row(out.rows[-1])
                if out.rows[-1].outcome.startswith("error") or out.rows[-1].outcome == "lost":
                    out.stopped = f"position {i}: {out.rows[-1].outcome}"
                    break
        if first is not None and first.pending and first.due(pos, cycle[i + 1] if i + 1 < len(cycle) else None):
            first.settle(cam)                       # raises when the check fails: the marker stays
            if not _at(cam.read(), pos) and refind is not None:
                # the check left the menu open elsewhere (a Playback row's view left with its button, and MENU reopened
                # the menu on the page last used before it, 2026-11-15): once, the run's own way back to the position
                refind(cam, pos)
            if not _at(cam.read(), pos):
                out.stopped = f"position {i}: after a first open's check the menu is not back on its row"
                break
        if i < len(cycle) - 1:
            cam.press("down")
    out.presses = cam.presses
    return out


def row_readings(row: dict) -> list:
    """Every reading of a row's label a page model or a live page read keeps beside the label: page_model's
    {"readings": {"label": {reader: text}}}, camkit.live.submenu_labels' {"readings": [texts]}."""
    got = row.get("readings")
    if isinstance(got, dict):
        got = (got.get("label") or {}).values() if isinstance(got.get("label"), dict) else []
    return [str(t) for t in got or [] if t]


def network_open(row: dict, network, group: str = "") -> bool:
    """Whether the crawl opens a never-open row because a dated owner decision names it (network, crawl_run.py
    --network): the label is of a class a network decision lifts (safety.lift_class: a Wi-Fi or Bluetooth setting, or an
    identity or connection row), never an address screen; the row's stored reason (the page model's or the live read's,
    if any) is of the same kind as a fresh never_open of its label, so a page model built before the Wi-Fi and Bluetooth
    class existed ("by hand only: bluetooth function") fails closed; every reading kept beside the label is harmless or
    of the same class; and the decision names the row (safety.network_lifted), its label or, read with an icon of its
    page glued on, where another reading of the row is the decided row exactly and the glued letters are a word of the
    page's group (`group`, the page's breadcrumb's second part: safety.lifted_readings)."""
    return network_row(row, network, group) is not None


def network_row(row: dict, network, group: str = "") -> str | None:
    """The decided row (of `network`) the crawl opens the never-open row `row` as, on network_open's terms, or None."""
    label = row.get("label") or ""
    cls, fresh, stored = safety.lift_class(label), safety.never_open(label), row.get("never_open")
    if not network or cls in (None, safety.LIFT_ADDRESS):
        return None
    if stored and stored.split(":", 1)[0] != fresh.split(":", 1)[0]:
        return None
    if any(safety.never_open(t) and safety.lift_class(t) != cls for t in row_readings(row)):
        return None
    entry = {"group": group or "", "readings": [label, *row_readings(row)]}
    return safety.network_lifted_row(label, network, readings={r: [entry] for r in network})


def visit_row(cam, row_screen, page, slot, row, labels=None, path=(), parent=None, panels=False,
              index: int = 0, network=frozenset(), notices=None, info_ok=None, first=None,
              look: bool = False) -> RowResult:
    """Open one row (Right), walk what opens, come back to the row. `parent` is how to get back
    here if MENU throws us out (camkit.crawl.Place), and `index` the row's place in its submenu (Downs from its
    first row), which that way back counts; `labels(cam)` -> (page key, [labels]) reads a
    submenu page's labels live, so submenu rows are checked against the never-open list before
    any Right; without it submenus are recorded and left. network: the Wi-Fi and Bluetooth settings a dated owner
    decision opens (network_open). notices, (read(cam), the row labels the kit knows, the values it knows by row label):
    a Wi-Fi or Bluetooth setting (never an identity row or an address screen) a decision opened that answers Right with
    a notice keeps the notice's text, where it is one the kit knows and names no identity or credentials, and what it
    names after "as follows" only where that is a known row label with its value (safety.notice_kept, RowResult.notice);
    any other keeps none. info_ok(cam, name, frame): for a row (never one a network decision opened) whose Right opened a
    notice, called once with the row's name ("A > B" inside a submenu) and the frame read before Right (the camera's
    `frame`, None without one): None where the run names no notice for the row, {"refused": why} where it pressed
    nothing, {"row", "frame"} where it took the notice's OK (kit/crawl_run.py's info_ok_pass); the screen behind it is
    walked only when it is one WALKERS knows, else left with MENU. first: crawl()'s; a row it refuses to open the first
    time on this body is skipped, "skipped: <why>", nothing pressed. look: a look lap's (closed_row): a never-open row
    no decision names opens as one a decision opened with no option named, its class safety.look_class's."""
    label = row.get("label") or ""
    r = RowResult(page.get("page", ""), slot, label, "")
    why, decided = closed_row(page, row, network, look, seen_of(first), path)
    if why and decided is None:
        r.outcome = f"skipped: {why}"
        return r
    looked_at = bool(why)           # a row a network decision or a look lap opens: its options are read, nothing committed
    by_look = looked_at and network_row(row, network, _group(page)) is None
    if looked_at:
        # a row a look lap opened: its class (safety.look_class), and no decided name, since its label as the page
        # model read it can carry a value (kit/crawl_run.py keeps a label only where it is one the kit knows)
        r.network = safety.look_class(label) if by_look else safety.lift_class(label) or ""
        r.decided = "" if by_look else decided
    refused = first.opening((*path, decided or label)) if first is not None else None
    if refused:
        r.outcome = f"skipped: {refused}"
        return r
    p0 = cam.presses
    before = getattr(cam, "frame", None) if info_ok is not None and not looked_at else None
    # on a look lap the camera is told which row this Right opens: the one name Seen and the pending first opens were
    # asked about, and whether its whole path is seen opened or under its first open (camkit.live.bar_is_row,
    # docs/decisions/0024)
    where = (*path, decided or label)
    told = {"row": {"expected": (where[-1],),
                    "seen": bool(seen_of(first) and seen_of(first)(where)),
                    "first": first is not None and tuple(where) in getattr(first, "pending", ())}} if look else {}
    try:
        cam.press("right", **told)
    except safety.RowRefused as e:
        # refused before it went out because of the lit row itself (the camera's own check): nothing was pressed on this
        # row, so it is skipped and the lap goes on, the reason's quoted texts withheld (a bar can carry a value); never
        # while a row a network decision opened is still open (its lock refuses what is no row's own refusal)
        if any(getattr(cam, attr, None) is not None for attr in ("network_open", "identity_open", "address_open")):
            raise
        if hasattr(cam, "presses"):
            cam.presses = p0
        if first is not None:
            first.not_opened((*path, decided or label))     # nothing went out: no first open to check
        r.outcome = f"skipped: refused ({safety.quoted_withheld(e)})"
        return r
    except safety.Refused:
        # refused before it went out for another reason (the screen changed since it was read, a look that failed:
        # camkit.live.look_before_right), as every refusal of a press is (camkit.live, camkit.link's guards): nothing was
        # pressed on this row, so it is no first open, never one written checked; the lap is cancelled as before
        if first is not None:
            first.not_opened((*path, decided or label))
        raise
    s = cam.read()
    r.kind = s.kind
    not_passed = ""
    if s.kind == "notice" and info_ok is not None and not looked_at:
        # a notice the run names for this row (--info-ok): its OK, once, by the caller's judgement; else left as ever
        got = info_ok(cam, " > ".join((*path, label)), before) or {}
        if got.get("frame"):
            r.info_ok = {"row": got.get("row") or label, "frame": got["frame"]}
            s = cam.read()
            r.kind = s.kind
        else:
            not_passed = str(got.get("refused") or "")
    if r.info_ok is not None and s.kind not in WALKERS:
        r.outcome = f"notice passed: a {s.kind} screen after its OK, left unwalked"
    elif same_state(s, row_screen):
        r.outcome = "no response to Right"
    elif looked_at:
        if s.kind in LOOK_WALKED and not menu_alone(cam):
            # Down round its options only: no second axis, no panel, no submenu, whatever --panels says
            try:
                r.walk = walk_cycle(cam, budget=120)
                r.outcome = "walked (network row, looked at only)" if r.walk.complete else f"incomplete: {r.walk.note}"
            except safety.Refused:
                raise                            # after a press on the row: the lap is cancelled
            except Exception as e:
                r.outcome = f"incomplete: {type(e).__name__}"
        else:
            # the camera's playback view (a Playback row's own screen, camkit.live's reading) is left with MENU alone,
            # never walked: there a key changes the picture shown or acts on it (the link lets none but MENU out)
            seen = "playback view" if s.kind == "playback" else f"{s.kind} screen"
            r.outcome = f"network row: a {seen}, left unwalked (looked at only)"
            if s.kind == "notice" and r.network == safety.LIFT_NETWORK and notices is not None:
                read, words, told = notices
                try:
                    r.notice = safety.notice_kept(read(cam), words, told)
                except Exception:                # a text that cannot be read keeps nothing, as before
                    r.notice = ""
    elif s.kind == "notice":
        # the frame is the evidence (blocker and its value); the --info-ok that would pass it is said (notice_hint)
        r.outcome = "notice" + (f" (named, not passed: {not_passed})" if not_passed else "")
        notice_hint(cam, "(withheld)" if look else " > ".join((*path, label)), network or look)
        if notices is not None and not network and not look:
            # a plain crawl keeps what the notice names, as a look lap and drive.py's look keep it (notice_named)
            read, words, told = notices
            try:
                r.notice = notice_named(read(cam), words, told)
            except Exception:                    # a text that cannot be read keeps nothing
                r.notice = ""
    elif s.kind in WALKERS:
        try:
            if s.kind == "dialog" and labels is not None:
                r.walk = walk_dialog_deep(cam, labels, path + (label,), panels=panels, network=network, look=look)
            else:
                r.walk = WALKERS[s.kind](cam)
            r.outcome = "walked" if getattr(r.walk, "complete", False) else f"incomplete: {r.walk.note}"
        except safety.Refused:
            raise                                # after a press on the row: the lap is cancelled
        except Exception as e:                   # the twin raises for moves nobody recorded
            r.outcome = f"incomplete: {type(e).__name__}"
    elif s.kind == "submenu" and labels is not None and len(path) < MAX_DEPTH:
        here = Place(row_screen, parent, index)
        sub = crawl_submenu(cam, labels, path + (label,), here, network=network, notices=notices, info_ok=info_ok,
                            first=first, look=look)
        r.walk, r.outcome = sub, ("submenu crawled" if not sub.stopped else f"submenu: {sub.stopped}")
        if sub.stopped.startswith("lost"):
            r.outcome = "lost"
            r.presses = cam.presses - p0
            return r
        r.presses = cam.presses - p0
        if not leave_submenu(cam, here):
            r.outcome = "lost"
        r.presses = cam.presses - p0
        return r
    elif s.kind == "submenu":
        r.outcome = "submenu (not crawled yet)"
    elif s.kind in ("table", "fnmenu", "keyset", "picker"):
        r.outcome = "left for kit/table_walk.py"   # cells that open lists or the function picker
    else:
        r.outcome = "unknown screen"
        if first_time(cam, s.kind):
            notice_hint(cam, "(withheld)" if look else " > ".join((*path, label)), network or look)   # a first-time screen
    if r.outcome != "no response to Right" and not back_to(cam, Place(row_screen, parent, index)):
        r.outcome = "lost"
    r.presses = cam.presses - p0
    return r


def menu_alone(cam) -> bool:
    """Whether the camera holds MENU alone on the screen a row opened (camkit.live.LiveCamera's address_open or
    identity_open: an address screen, a blanked row, a screen naming identity or credentials): the walk then presses
    nothing there, so the row is left with MENU rather than the lap cancelled by a refused Down. A camera without them
    (the menu twin) holds none."""
    return bool(getattr(cam, "address_open", None) or getattr(cam, "identity_open", None))


def first_time(cam, kind) -> bool:
    """Whether the screen on show is a first-time screen (safety.first_time_screen: no known kind, a "Don't show this
    again." box), read by OCR on the camera's own frame; False where it cannot be read (a twin camera's)."""
    try:
        from .live import text_of
        return safety.first_time_screen(kind, text_of(cam))
    except Exception:
        return False


def notice_named(text, labels=(), values=None) -> str:
    """What a plain crawl keeps of the notice a row answered Right with (RowResult.notice, which the coverage ledger reads
    through camkit.coverage.blocker_of), exactly as much as a look lap and drive.py's look keep and no more: the notice
    as a look lap keeps it (safety.notice_kept: a notice the kit knows, or the blocker form with the row label it names
    after "as follows", never that row's value), where it gives the blocker drive.py's look gives the whole text
    (blocker_of); else what gives that blocker alone: the blocker form with the row label blocker_of found ("... as
    follows HDMI Info. Display", never "On"), or the notice's own words that ask for equipment or say a remote session
    is open (safety.NOTICE_EQUIPMENT, safety.NOTICE_REMOTE: "Invalid with this lens", "shoe"). Nothing where the whole
    text holds a question, reads as a confirmation or names identity or credentials or what no allowance opens (as
    notice_kept), nor where none of that gives the same blocker again: never free text of the screen."""
    from .coverage import blocker_of
    t = " ".join(safety.fold(text).split())
    if not t or "?" in t or safety.confirmation_refused(t) or safety.identity_screen(t) or safety.never_lifted(t):
        return ""
    kept = safety.notice_kept(text, labels, values)
    want = blocker_of(t, labels)
    if not want or blocker_of(kept, labels) == want:
        return kept
    if want.get("row"):
        named = f"{kept} {want['row']}" if kept else want["row"]
    else:
        rxs = [rx for rx, _ in safety.NOTICE_EQUIPMENT] if want.get("equipment") else [safety.NOTICE_REMOTE]
        named = next((m.group(0) for m in (rx.search(t) for rx in rxs) if m), "")
    return named if named and blocker_of(named, labels) == want else kept


def notice_hint(cam, name: str, network=frozenset()) -> None:
    """A notice (or a first-time screen) the crawl leaves on the row `name`, nothing pressed on it but MENU: the --info-ok
    that would pass it printed, its text withheld on a --network crawl, and the refusal logged in the run's events.jsonl
    (camkit.live.info_ok_hint); nothing where the camera has no frame of its own (a twin camera's)."""
    try:
        from .live import info_ok_hint, info_ok_text
        frame = cam.frame.path.name
        print(f"   {name}: a notice not passed; {info_ok_hint(cam, name, frame, info_ok_text(cam), not network)}",
              flush=True)
    except Exception:
        return


MAX_DEPTH = 4                  # Picture Profile > PPn > Knee > Auto Set (2026-10-28)
# the screens a row a network decision opens is walked on, by Down round its options alone (walk_cycle): never a second
# axis, a panel or a submenu, which Right or Left reach and which can commit an option
LOOK_WALKED = frozenset({"list", "dialog", "sidelist", "checklist"})
SUBMENU_ROWS = 40              # rows a submenu may hold before the crawl takes it for one it misreads (~14 seen)


@dataclass
class Place:
    """A row's screen and the place above it: enough to find it again (compared with same_state)."""
    screen: object
    parent: "Place | None" = None
    index: int = 0                                 # position in its submenu (Downs from its first row)


def back_to(cam, place: "Place", tries: int = 4) -> bool:
    """Back to a row's own screen after walking what it opened: MENU, then recover.

    MENU on a notice closes the notice and the whole menu (2026-10-28), and MENU then reopens on
    the same row; inside a submenu it may reopen on the parent row instead, so: shooting screen ->
    MENU (the one helper, camkit.live.menu_from_shooting: a MENU from the shooting screen once more only after a fresh
    look, never right after the last one); on the parent row -> Right into the submenu and Down to the row's position."""
    from .live import menu_from_shooting
    cam.press("menu")
    sent = False            # the last press was a MENU from the shooting screen: the next one looks first
    for _ in range(tries):
        s = cam.read()
        if same_state(s, place.screen):
            if getattr(cam, "network_open", None) is None:
                return True
            # the camera still holds the row's look lock on its page (a blanked row's frames are never read, so only the
            # shooting screen ends it: camkit.live.LiveCamera.network_left): MENU closes the menu, and MENU opens it again
            cam.press("menu")
            sent = False
            continue
        if s.kind == "shooting":
            menu_from_shooting(cam, pressed=sent)
            sent = True
            continue
        sent = False
        if place.parent is not None and same_state(s, place.parent.screen):
            # back into the submenu; it may reopen on its first row or the last one used, and it
            # wraps, so Down until this row comes round (bounded: past its place, from wherever it reopens, and at
            # least as far as crawl_submenu's own guard; each step checks the screen, so the bound costs nothing)
            cam.press("right")
            for _ in range(max(place.index + 16, SUBMENU_ROWS)):
                if same_state(cam.read(), place.screen):
                    return True
                cam.press("down")
            return same_state(cam.read(), place.screen)
        if s.kind not in ("menu", "submenu", "tiles"):
            cam.press("menu")                         # still inside something: one more level out
            continue
        return False
    return same_state(cam.read(), place.screen)


def leave_submenu(cam, parent_row: "Place") -> bool:
    """From inside a submenu back to the row that opened it: Left (the ‹ glyph), then MENU-style
    recovery if that did not land on it."""
    cam.press("left")
    if same_state(cam.read(), parent_row.screen):
        return True
    return back_to(cam, parent_row)


@dataclass
class SubCrawl:
    rows: list = field(default_factory=list)
    stopped: str = ""


def crawl_submenu(cam, labels, path: tuple, parent: "Place", network=frozenset(), notices=None,
                  info_ok=None, first=None, look: bool = False) -> SubCrawl:
    """Every row of the submenu just opened: Down until its first screen comes back (submenus wrap
    like lists). At each row its label is read live first (labels(cam) -> (page key, [rows]),
    each row a label or {"label", "never_open"}, cached per page) and checked against the
    never-open list; a row with no label read is not opened. Then the row is visited like a
    top-level one, with recovery to this exact row if MENU throws us out."""
    out = SubCrawl()
    s = cam.read()
    top = s
    cache: dict = {}
    for index in range(SUBMENU_ROWS):               # a guard: submenus have at most ~14 rows
        s = cam.read()
        key, page_rows = labels(cam)
        cache.setdefault(key, page_rows)
        slot = s.row if s.row is not None else 0
        entry = cache[key][slot] if slot < len(cache[key]) else {"label": ""}
        if isinstance(entry, str):
            entry = {"label": entry}
        if not (network or look):
            entry = icon_entry(cam, s, slot, entry, cache[key])
        page = {"page": " > ".join(path)}
        here = Place(s, parent, index)
        if not entry.get("label"):  # noqa: SIM108 (two long arms read apart)
            res = RowResult(page["page"], slot, "", "skipped: no label read")
        else:
            res = visit_row(cam, s, page, slot, entry, labels, path, parent, index=index, network=network,
                            notices=notices, info_ok=info_ok, first=first, look=look)
        res.icon = entry.get("icon")
        out.rows.append(res)
        if res.outcome == "lost":
            out.stopped = f"lost at {entry.get('label')!r}"
            return out
        if not same_state(cam.read(), here.screen) and not back_to(cam, here):
            out.stopped = f"lost after {entry.get('label')!r}"
            return out
        cam.press("down")
        if same_state(cam.read(), top):
            return out
    out.stopped = f"more than {SUBMENU_ROWS} rows: not a submenu the reader understood"
    return out


def icon_entry(cam, s, slot: int, entry: dict, rows) -> dict:
    """The submenu row `entry` (labels(cam)'s, the row lit at `slot` on the screen `s`) with its label read to the right
    of the icon the camera draws before it (camkit.screen.label_icons): OCR reads the row again with the icon painted
    over (page_model.covered_readings), and what the label as read has in front of that reading is left out where
    page_model.icon_label can tell it is the icon ("S&Q Record Setting" is Record Setting, 2026-11-19), else the label
    stays as read; either way "icon" says what was read, left out or kept, and why. The label as read stays among the
    row's readings, which the never-open and look lap checks read (row_readings). The picture is the frame as the run
    saved it (a frame the eyes withheld is black there, and gives nothing), never one in memory only; crawl_submenu asks
    nothing of the kind on a --network run or a look lap, which keep no text read off the screen. The entry as it is
    where the camera gives no saved frame (the menu twin), the row starts with no icon, or the reading fails. rows: the
    page's labels (labels(cam)'s), none of which the label may become."""
    label = entry.get("label") or ""
    saved = getattr(getattr(cam, "frame", None), "path", None)
    if not label or saved is None or slot >= len(getattr(s, "rows", None) or ()):
        return entry
    try:
        from page_model import SUBMENU_LABEL, covered_readings, icon_label  # (kit/ on sys.path)

        from .frames import load
        image = load(saved).image
        band = s.rows[slot]
        boxes, text_x = screen.label_icons(image, band, SUBMENU_LABEL[0])
        if not boxes:
            return entry
        got = covered_readings({0: (image, {slot: (band, boxes, text_x)})}, SUBMENU_LABEL, {"ocr": None})
        others = [r.get("label") if isinstance(r, dict) else r for i, r in enumerate(rows) if i != slot]
        new, record = icon_label(label, got[0].get(slot, {}).get("ocr", ""), boxes, others)
    except Exception:                   # no icon read: the label as read
        return entry
    readings = entry.get("readings")
    if not isinstance(readings, dict):                   # a live page read's list (camkit.live.submenu_labels)
        readings = [*(readings or ()), *([label] if label not in (readings or ()) else [])]
    return {**entry, "label": new, "icon": record, "readings": readings}


@dataclass
class DeepWalk:
    """A carousel walked twice: its options (main), then per option what Right does there."""
    main: object = None
    details: dict = field(default_factory=dict)    # option index -> {"axis": AxisWalk} | {"panel": (kind, walk)}
    presses: int = 0
    complete: bool = False
    note: str = ""

    @property
    def options(self):
        return self.main.options if self.main else []


def walk_dialog_deep(cam, labels, path, panels: bool = False, network=frozenset(), look: bool = False) -> DeepWalk:
    """Carousels whose options lead further (Drive Mode, Focus Area, White Balance...). First the
    options, by walk_cycle. Then once more round: at each option that SHOWS a second axis (side or
    strip ‹ ›), Right to its end and Left to the other end, by those marks.

    Nothing else is pressed inside a carousel in pass 1. Leaving a carousel through a panel or a
    submenu COMMITS its current option: Right across Cont. Bracket's fields reached its › and opened
    Bracket Settings, and drive mode, bracket step and shot count were written (5 records,
    2026-10-28; restored by upload). So › boxes and panels are recorded, not opened (pass 2 proves
    them deliberately), Right is never tried where no axis is shown, and an axis walk stops the
    moment the screen type changes."""
    d = DeepWalk()
    p0 = cam.presses
    d.main = walk_cycle(cam, budget=120)
    if not d.main.complete:
        d.note, d.presses = d.main.note, cam.presses - p0
        return d
    n = len(d.main.options)
    walked = set()                 # panels mode: panel types walked fully in this dialog
    for k in range(n):
        here = cam.read()
        g = here.glyphs
        side = g.get("side_right") or g.get("strip_right") or g.get("side_left") or g.get("strip_left")
        if panels and not side:
            # panels mode (a run that restores the start file afterwards): Right may open a panel,
            # which COMMITS this option; Picture Profile's ›, White Balance's ›, Creative Look's looks
            info = open_panel(cam, here, labels, path + (f"option {k}",), walked, network=network, look=look)
            if info is not None:
                d.details[k] = info
            if cam.read().kind != here.kind:
                d.note = f"option {k}: back from the panel landed on {cam.read().kind}"
                d.presses = cam.presses - p0
                return d
        elif g.get("sub_box"):
            d.details[k] = {"panel": "› (not opened in pass 1)"}
        if side:
            r = "side_right" if g.get("side_right") else "strip_right"
            l = "side_left" if g.get("side_left") else "strip_left"
            axis = walk_axes(cam, [("right", r), ("left", l)], kind=here.kind)
            d.details.setdefault(k, {})["axis"] = axis
            if cam.read().kind != here.kind:
                d.note = f"option {k}: the second axis left the dialog ({cam.read().kind})"
                d.presses = cam.presses - p0
                return d
        if k < n - 1:
            cam.press("down")
            if cam.read().kind != here.kind:
                d.note = f"Down after option {k} left the dialog ({cam.read().kind})"
                d.presses = cam.presses - p0
                return d
    d.complete = True
    d.presses = cam.presses - p0
    return d


def open_panel(cam, here, labels, path, walked: set, network=frozenset(), look: bool = False):
    """Right from a carousel option; if a panel opens, walk it by its type (fully the first time a
    type is met in this dialog, else record its first screen) and come back (Left from a submenu,
    MENU otherwise). None when Right changed nothing; {"axis": ...} when it moved a second axis."""
    cam.press("right")
    s = cam.read()
    if same_state(s, here):
        return None
    if s.kind == here.kind:                     # a second axis without marks: walk it to its ends
        return {"axis": walk_axes(cam, [("right", "side_right"), ("left", "side_left")], kind=here.kind)}
    kind = s.kind
    if kind in walked:
        info = {"panel": kind, "walked": "same type as before: first screen recorded",
                "frame": getattr(s, "frame_path", None)}
    elif kind == "submenu":
        info = {"panel": kind, "walk": crawl_submenu(cam, labels, path, Place(here), network=network, look=look)}
    elif kind in WALKERS and kind != "dialog":
        info = {"panel": kind, "walk": WALKERS[kind](cam)}
    else:
        info = {"panel": kind, "walked": "unknown screen", "frame": getattr(s, "frame_path", None)}
    walked.add(kind)
    if kind == "submenu" and cam.read().kind == "submenu":
        cam.press("left")
    else:
        cam.press("menu")
    return info
