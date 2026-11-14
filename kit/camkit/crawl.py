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
address screen, never a row whose stored reason or any reading says another class. Such a row is looked at only: Down round its list or
carousel (LOOK_WALKED), never a second axis, a panel or a submenu, with --panels too; the camera's own check
(camkit.live.LiveCamera) refuses anything else there besides.
"""
from dataclasses import dataclass, field

from . import safety
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

    def press(self, key):
        self.presses += 1
        self.cam.press(key)

    def read(self):
        return self.cam.read()

    def __getattr__(self, name):          # anything else (the live camera's current frame...) passes through
        return getattr(self.cam, name)


def crawl(cam, cycle: list, model: dict, tabs=("Shooting", "Exposure/Color", "Focus", "Network", "Setup"),
          stop=lambda: False, max_rows: int | None = None, on_row=None, labels=None, panels=False,
          network=frozenset()) -> Crawl:
    """cycle: the page scan's positions in Down order, each {"page": key, "row": slot, "signature",
    "kind"}; model: page key -> {"breadcrumb", "page", "rows": [{"label", "never_open", ...}]}.
    max_rows: stop after opening that many rows (skipped rows do not count). on_row(result) is
    called after each row (the live run writes its results file from it). network: the Wi-Fi and Bluetooth settings a
    dated owner decision opens ({row: date}, crawl_run.py --network; network_open)."""
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
        if not _at(s, pos) and s.kind == "shooting":
            # the camera left the menu by itself (2026-10-28: a CautionDisplay warning came with it, no
            # message stayed on screen): MENU reopens on the same row; check the position again
            cam.press("menu")
            s = cam.read()
            out.recoveries.append(i)
        if not _at(s, pos):
            out.stopped = f"position {i}: the screen is not the one the scan recorded here"
            break
        page = model.get(pos["page"])
        if pos["kind"] != "tiles" and page is not None and page["breadcrumb"].startswith(tabs):
            row = page["rows"][pos["row"]] if pos["row"] is not None and pos["row"] < len(page["rows"]) else None
            if row is not None:
                out.rows.append(visit_row(cam, s, page, pos["row"], row, labels, panels=panels, network=network))
                opened += not out.rows[-1].outcome.startswith("skipped")
                if on_row:
                    on_row(out.rows[-1])
                if out.rows[-1].outcome.startswith("error") or out.rows[-1].outcome == "lost":
                    out.stopped = f"position {i}: {out.rows[-1].outcome}"
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


def network_open(row: dict, network) -> bool:
    """Whether the crawl opens a never-open row because a dated owner decision names it (network, crawl_run.py
    --network): the label is of a class a network decision lifts (safety.lift_class: a Wi-Fi or Bluetooth setting, or an
    identity or connection row), never an address screen; the row's stored reason (the page model's or the live read's,
    if any) is of the same kind as a fresh never_open of its label, so a page model built before the Wi-Fi and Bluetooth
    class existed ("by hand only: bluetooth function") fails closed; every reading kept beside the label is harmless or
    of the same class; and the decision names the row (safety.network_lifted)."""
    label = row.get("label") or ""
    cls, fresh, stored = safety.lift_class(label), safety.never_open(label), row.get("never_open")
    if not network or cls in (None, safety.LIFT_ADDRESS):
        return False
    if stored and stored.split(":", 1)[0] != fresh.split(":", 1)[0]:
        return False
    if any(safety.never_open(t) and safety.lift_class(t) != cls for t in row_readings(row)):
        return False
    return safety.network_lifted(label, network)


def visit_row(cam, row_screen, page, slot, row, labels=None, path=(), parent=None, panels=False,
              index: int = 0, network=frozenset()) -> RowResult:
    """Open one row (Right), walk what opens, come back to the row. `parent` is how to get back
    here if MENU throws us out (camkit.crawl.Place), and `index` the row's place in its submenu (Downs from its
    first row), which that way back counts; `labels(cam)` -> (page key, [labels]) reads a
    submenu page's labels live, so submenu rows are checked against the never-open list before
    any Right; without it submenus are recorded and left. network: the Wi-Fi and Bluetooth settings a dated owner
    decision opens (network_open)."""
    label = row.get("label") or ""
    r = RowResult(page.get("page", ""), slot, label, "")
    why = row.get("never_open") or safety.never_open(label)
    if why and not network_open(row, network):
        r.outcome = f"skipped: {why}"
        return r
    looked_at = bool(why)           # a row a network decision opens: its options are read, nothing is committed
    if looked_at:
        r.network = safety.lift_class(label) or ""
    p0 = cam.presses
    cam.press("right")
    s = cam.read()
    r.kind = s.kind
    if same_state(s, row_screen):
        r.outcome = "no response to Right"
    elif looked_at:
        if s.kind in LOOK_WALKED:
            # Down round its options only: no second axis, no panel, no submenu, whatever --panels says
            try:
                r.walk = walk_cycle(cam, budget=120)
                r.outcome = "walked (network row, looked at only)" if r.walk.complete else f"incomplete: {r.walk.note}"
            except Exception as e:
                r.outcome = f"incomplete: {type(e).__name__}"
        else:
            r.outcome = f"network row: a {s.kind} screen, left unwalked (looked at only)"
    elif s.kind == "notice":
        r.outcome = "notice"                     # the frame is the evidence (blocker and its value)
    elif s.kind in WALKERS:
        try:
            if s.kind == "dialog" and labels is not None:
                r.walk = walk_dialog_deep(cam, labels, path + (label,), panels=panels, network=network)
            else:
                r.walk = WALKERS[s.kind](cam)
            r.outcome = "walked" if getattr(r.walk, "complete", False) else f"incomplete: {r.walk.note}"
        except Exception as e:                   # the twin raises for moves nobody recorded
            r.outcome = f"incomplete: {type(e).__name__}"
    elif s.kind == "submenu" and labels is not None and len(path) < MAX_DEPTH:
        here = Place(row_screen, parent, index)
        sub = crawl_submenu(cam, labels, path + (label,), here, network=network)
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
    if r.outcome != "no response to Right" and not back_to(cam, Place(row_screen, parent, index)):
        r.outcome = "lost"
    r.presses = cam.presses - p0
    return r


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
    MENU; on the parent row -> Right into the submenu and Down to the row's position."""
    cam.press("menu")
    for _ in range(tries):
        s = cam.read()
        if same_state(s, place.screen):
            return True
        if s.kind == "shooting":
            cam.press("menu")
            continue
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


def crawl_submenu(cam, labels, path: tuple, parent: "Place", network=frozenset()) -> SubCrawl:
    """Every row of the submenu just opened: Down until its first screen comes back (submenus wrap
    like lists). At each row its label is read live first (labels(cam) -> (page key, [rows]),
    each row a label or {"label", "never_open"}, cached per page) and checked against the
    never-open list; a row with no label read is not opened. Then the row is visited like a
    top-level one, with recovery to this exact row if MENU throws us out."""
    out = SubCrawl()
    s = cam.read()
    first = s
    cache: dict = {}
    for index in range(SUBMENU_ROWS):               # a guard: submenus have at most ~14 rows
        s = cam.read()
        key, page_rows = labels(cam)
        cache.setdefault(key, page_rows)
        slot = s.row if s.row is not None else 0
        entry = cache[key][slot] if slot < len(cache[key]) else {"label": ""}
        if isinstance(entry, str):
            entry = {"label": entry}
        page = {"page": " > ".join(path)}
        here = Place(s, parent, index)
        if not entry.get("label"):  # noqa: SIM108 (two long arms read apart)
            res = RowResult(page["page"], slot, "", "skipped: no label read")
        else:
            res = visit_row(cam, s, page, slot, entry, labels, path, parent, index=index, network=network)
        out.rows.append(res)
        if res.outcome == "lost":
            out.stopped = f"lost at {entry.get('label')!r}"
            return out
        if not same_state(cam.read(), here.screen) and not back_to(cam, here):
            out.stopped = f"lost after {entry.get('label')!r}"
            return out
        cam.press("down")
        if same_state(cam.read(), first):
            return out
    out.stopped = f"more than {SUBMENU_ROWS} rows: not a submenu the reader understood"
    return out


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


def walk_dialog_deep(cam, labels, path, panels: bool = False, network=frozenset()) -> DeepWalk:
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
            info = open_panel(cam, here, labels, path + (f"option {k}",), walked, network=network)
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


def open_panel(cam, here, labels, path, walked: set, network=frozenset()):
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
        info = {"panel": kind, "walk": crawl_submenu(cam, labels, path, Place(here), network=network)}
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
