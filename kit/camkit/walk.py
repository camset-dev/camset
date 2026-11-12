"""Walker logic: how each screen type is walked, written against a minimal camera interface so the
same code runs on the camera and on the menu twin (camkit.twin.TwinCamera).

The camera interface: press(key) and read() -> screen.Screen of the settled screen.

walk_cycle covers screens that move one step per Down and wrap round: list popups, carousel
dialogs, Picture Profile side lists, submenu pages. Positions are told apart by their pixel
signature (never by text; compared with screen.same_state, which tolerates live-view noise); each
position is left by Down exactly once, and the walk stops when the opening screen comes back. A budget only guards against a misread screen; reaching it is a failure,
never a finished walk.
"""
from dataclasses import dataclass, field

from .screen import same_state


@dataclass
class Walk:
    kind: str
    options: list = field(default_factory=list)   # signatures in list order (first option first)
    screens: dict = field(default_factory=dict)   # signature -> Screen
    wrapped: bool = False
    start_index: int = 0                          # where the cursor was when the walk began
    presses: int = 0
    complete: bool = False
    note: str = ""


OPPOSITE = {"down": "up", "up": "down", "right": "left", "left": "right"}


def walk_cycle(cam, budget: int = 60, forward: str = "down", strict_back: bool = True) -> Walk:
    """Down (or `forward`) until the opening screen comes back: n presses for n options, from
    wherever the cursor starts. Lists, carousels and side lists wrap (97 of 97 recorded ends,
    2026-10-28). Predict, then check: after a screen the reader marks as the last option, the next
    one must be the first.

    A press that changes nothing is an end, not a wrap (ISO Range Limit's minimum cannot pass its
    maximum): the walk then goes back the other way past its start, checking each known screen,
    until that direction stops too."""
    s = cam.read()
    start = s
    w = Walk(s.kind)
    order = [s.signature]
    w.screens[s.signature] = s
    while w.presses < budget:
        was_end = s.at_end is True
        prev = s
        cam.press(forward)
        w.presses += 1
        s = cam.read()
        if same_state(s, prev):
            back = OPPOSITE[forward]
            if start.kind == "fields" and start.glyphs.get(back) is False:
                w.options, w.complete = order, True      # it started at the other end: nothing beyond
                return w
            return _walk_back(cam, w, order, back, budget, strict_back)
        # (only where the whole list is on screen: in a list that scrolls, the reader's "last option"
        # can be wrong, and the repeat-period rule below takes over: Black Level -15..+15)
        if was_end and s.at_start is not True and s.kind in ("list", "dialog") and prev.scroll is None:
            w.note = f"after the last option the next screen is not the first ({w.presses} presses)"
            return w
        if same_state(s, w.screens[order[0]]):
            w.wrapped = w.complete = True
            first = next((i for i, sig in enumerate(order) if w.screens[sig].at_start is True), 0)
            w.options = order[first:] + order[:first]          # first option first
            w.start_index = (len(order) - first) % len(order)
            return w
        hit = next((i for i, sig in enumerate(order) if same_state(s, w.screens[sig])), None)
        if hit is not None and s.kind in ("list", "sidelist"):
            # a list that scrolls: one option can sit on another row depending on the way it was
            # reached, so the opening screen need not come back; an exact earlier screen does, and
            # the list's period is the presses between the two (Operation Area: 11 - 2 = 9 options;
            # Pre-Capture Rec Time 17, 2026-10-28). Pixel comparison across rows cannot tell options
            # apart reliably (a digit change can be closer than one option drawn on two rows).
            w.options = order[hit:]
            w.wrapped = w.complete = True
            w.start_index = (len(order) - hit) % len(w.options) if w.options else 0
            return w
        if hit is not None:
            w.note = f"came back to an earlier screen that is not the start (after {w.presses} presses)"
            return w
        order.append(s.signature)
        w.screens[s.signature] = s
    w.note = "budget reached"
    return w


def _walk_back(cam, w: Walk, order: list, back: str, budget: int, strict: bool = True) -> Walk:
    """`order` ran from the start to an end that does not wrap: go back past the start (the known
    screens must come back in reverse, unless `strict` is off: coupled number fields, where moving
    ISO Range Limit's maximum pushes the minimum along, 2026-10-28), then on until this direction
    stops too."""
    for expected in reversed(order[:-1]):
        cam.press(back)
        w.presses += 1
        if strict and not same_state(cam.read(), w.screens[expected]):
            w.note = f"going back, expected a known screen and got another ({w.presses} presses)"
            return w
    before = []
    while w.presses < budget:
        prev = cam.read()
        cam.press(back)
        w.presses += 1
        s = cam.read()
        if same_state(s, prev):
            w.options = before[::-1] + order
            w.start_index = len(before)
            w.complete = True
            return w
        if strict and any(same_state(s, x) for x in w.screens.values()):
            w.note = "going back came round to a known screen without stopping"
            return w
        before.append(s.signature)
        w.screens[s.signature] = s
    w.note = "budget reached going back"
    return w


def walk_to_end(cam, key: str, arrow: str, budget: int = 120, kind: str | None = None) -> tuple[list, str, int]:
    """Press `key` until the reader stops showing `arrow` (the end of that axis), the screen stops
    changing, or it comes round to a screen already seen (it wraps). With `kind`, it also stops the
    moment the screen is no longer of that type ("left"): a carousel left through a panel commits
    its option (2026-10-28). (signatures, how, presses)."""
    first = cam.read()
    seen, screens = [first.signature], [first]
    presses = 0
    for _ in range(budget):
        s = cam.read()
        if s.glyphs.get(arrow) is False:
            return seen, "end", presses
        cam.press(key)
        presses += 1
        now = cam.read()
        if kind is not None and now.kind != kind:
            return seen, "left", presses
        if same_state(now, s):
            return seen, "stuck", presses
        if any(same_state(now, x) for x in screens):
            return seen, "wraps", presses
        seen.append(now.signature)
        screens.append(now)
    return seen, "budget", presses


@dataclass
class FieldsWalk:
    fields: list = field(default_factory=list)    # per field: Walk of its values (Up, wrapping)
    presses: int = 0
    complete: bool = False
    note: str = ""


def walk_fields(cam, budget_per_field: int = 120) -> FieldsWalk:
    """Number fields: for each field (Right moves to the next), Up until the value it started on
    comes back. Number fields wrap (Shooting Interval 59 -> 60 -> 1 with both arrows shown, HDMI
    2026-10-28), so this sees every value once; values are read from the saved frames afterwards.
    Leave with MENU: it cancels (controlled test 2026-10-28)."""
    fw = FieldsWalk()
    s = cam.read()
    n = s.count or 1
    start_field = s.field or 0
    for k in range(n):
        w = walk_cycle(cam, budget=budget_per_field, forward="up", strict_back=False)
        fw.presses += w.presses
        fw.fields.append(w)
        if not w.complete:
            fw.note = f"field {(start_field + k) % n}: {w.note}"
            return fw
        if k < n - 1:
            before = cam.read().field
            cam.press("right")
            fw.presses += 1
            after = cam.read().field
            if after == before:
                fw.note = f"Right did not move to the next field (still {after})"
                return fw
    fw.complete = True
    return fw


@dataclass
class AxisWalk:
    axes: dict = field(default_factory=dict)      # key -> (signatures, how it ended)
    presses: int = 0
    complete: bool = False
    note: str = ""


def walk_axes(cam, pairs, budget: int = 120, kind: str | None = None) -> AxisWalk:
    """Sliders and the White Balance grid: for each (key, arrow) go to the end of that axis, i.e.
    until the arrow disappears. pairs e.g. [("right", "right"), ("left", "left")] for a slider;
    the WB grid adds ("up", "up") and ("down", "down"). Leave with MENU."""
    aw = AxisWalk()
    for key, arrow in pairs:
        seen, how, presses = walk_to_end(cam, key, arrow, budget, kind)
        aw.axes[key] = (seen, how)
        aw.presses += presses
        if how in ("budget", "left"):
            aw.note = f"{key}: {'budget reached' if how == 'budget' else 'left the screen'}"
            return aw
    aw.complete = True
    return aw


def walk_look(cam, budget: int = 40) -> AxisWalk:
    """Creative Look panel: Right across the cells until the first comes back, noting for each
    whether it can move (⌃/⌄ shown; a fixed cell has neither, e.g. BW Saturation). Ranges per
    parameter come from walk_axes on that cell (up/down) when needed."""
    aw = AxisWalk()
    w = walk_cycle(cam, budget=budget, forward="right")
    aw.presses = w.presses
    aw.axes["cells"] = ([w.screens[sig] for sig in w.options], "wraps" if w.wrapped else w.note)
    aw.complete = w.complete
    aw.note = w.note
    return aw



@dataclass
class GridWalk:
    rows: list = field(default_factory=list)      # per grid row: Walk of its cells (Right, wrapping)
    presses: int = 0
    complete: bool = False
    note: str = ""

    @property
    def options(self):
        return [sig for r in self.rows for sig in r.options]


def walk_grid(cam, budget: int = 300) -> GridWalk:
    """Checkbox grid (Focus Area Limit): Right across a row wraps within that row (7 cells,
    2026-10-28), so each row is a walk_cycle with Right; Down moves to the next row, and the walk ends
    when the row it started on comes round again (or Down reaches the OK/Cancel buttons)."""
    gw = GridWalk()
    first_row = cam.read().row
    for _ in range(12):
        w = walk_cycle(cam, budget=budget, forward="right")
        gw.presses += w.presses
        gw.rows.append(w)
        if not w.complete:
            gw.note = f"row {cam.read().row}: {w.note}"
            return gw
        cam.press("down")
        gw.presses += 1
        s = cam.read()
        if s.focus != "rows" or s.row == first_row:
            gw.complete = True
            return gw
    gw.note = "more than 12 rows"
    return gw
