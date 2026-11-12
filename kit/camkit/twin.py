"""Menu twin: replay recorded camera behaviour so walker logic can be tested offline.

A twin holds, for one menu item, the screens seen (a screenshot per state) and the recorded moves
between them: (state, input) -> state. TwinCamera answers press(input) from those moves and
read() with the pixel reader, at thousands of presses a second. A move nobody recorded raises
Unrecorded: a walker that needs it is pressing something the real camera was never seen to do.

Source today: runs/ILCE-1M2_fw4.00/explore_stills/graph.jsonl, the old explorer's per-item dialog graphs on the a1 II
(271 items, 2,014 states, 11,652 presses; state keys were OCR-based, so a few may be merged or split).
"""
from dataclasses import dataclass, field
from pathlib import Path

from . import jsonl, paths, screen
from .frames import Frame, load


class Unrecorded(Exception):
    pass


class LeftScreen(Exception):
    """The recorded move closed the screen (the old graphs' EXIT state)."""


@dataclass
class Twin:
    item: str
    root: str
    shots: dict                                   # state -> screenshot path
    moves: dict = field(default_factory=dict)     # (state, input) -> state
    status: str = ""

    @classmethod
    def from_old_graph(cls, g: dict, shots_dir: Path):
        shots = {k: shots_dir / n["shot"] for k, n in g["nodes"].items() if n.get("shot")}
        moves = {(a, key): b for a, key, b in g.get("edges", [])}
        return cls(g["item"], g["root"], shots, moves, g.get("status", ""))

    @property
    def states(self):
        return set(self.shots)


def old_twins(path: Path = None) -> list[Twin]:
    path = Path(path) if path else paths.a1ii_root() / "explore_stills" / "graph.jsonl"
    shots_dir = path.parent / "shots"
    if not path.is_file():
        raise FileNotFoundError(f"{path}: the old explorer's graphs are not in this clone")
    return [Twin.from_old_graph(g, shots_dir) for g in jsonl.read(path)
            if g.get("nodes") and g.get("root") in g["nodes"]]


class TwinCamera:
    """The parts of the camera a walker uses (press, frame, read), answered from a twin.

    infer_wrap: lists, carousels and side lists wrap (every recorded Down at a last option went to
    the first one: 97 of 97, 2026-10-28), so where the old explorer never pressed Down at the end,
    the move is filled in to the item's first option (and Up at the first to the last). Counted in
    .inferred."""

    def __init__(self, twin: Twin, infer_wrap: bool = True):
        self.twin = twin
        self.state = twin.root
        self.presses = 0
        self.inferred = 0
        self.infer_wrap = infer_wrap
        self.visited = {twin.root}
        self._cache: dict = {}

    def _ends(self):
        """(first, last) states by the reader's at_start/at_end, if each is unique."""
        firsts = [k for k in self.twin.shots if self._read(k).at_start is True]
        lasts = [k for k in self.twin.shots if self._read(k).at_end is True]
        return (firsts[0] if len(firsts) == 1 else None), (lasts[0] if len(lasts) == 1 else None)

    def _read(self, state):
        if state not in self._cache:
            self._cache[state] = screen.read(load(self.twin.shots[state]))
        return self._cache[state]

    def press(self, key: str):
        nxt = self.twin.moves.get((self.state, key))
        if nxt is None and self.infer_wrap and key in ("down", "up"):
            # a cursor move in a list can be undone: if Up took B to A, Down takes A to B
            opposite = "up" if key == "down" else "down"
            back = [b for (b, k), a in self.twin.moves.items() if k == opposite and a == self.state]
            if len(back) == 1:
                nxt = back[0]
                self.inferred += 1
        if nxt is None and self.infer_wrap and key in ("down", "up"):
            # a list that fits on one screen: Down from row r is the same list with the cursor on r+1
            here = self._read(self.state)
            if here.kind == "list" and here.scroll is None and here.row is not None:
                want = here.row + (1 if key == "down" else -1)
                same = [k for k in self.twin.shots if k != self.state
                        and (lambda o: o.kind == "list" and o.scroll is None and o.count == here.count
                             and o.row == want)(self._read(k))]
                if len(same) == 1:
                    nxt = same[0]
                    self.inferred += 1
        if nxt is None and self.infer_wrap and key in ("down", "up"):
            first, last = self._ends()
            here = self._read(self.state)
            if key == "down" and here.at_end is True and first:
                nxt = first
            elif key == "up" and here.at_start is True and last:
                nxt = last
            if nxt is not None:
                self.inferred += 1
        if nxt is None:
            raise Unrecorded(f"{self.twin.item}: {key!r} from {self.state} was never recorded")
        self.presses += 1
        if nxt not in self.twin.shots:
            raise LeftScreen(f"{self.twin.item}: {key!r} from {self.state} left the screen ({nxt})")
        self.state = nxt
        self.visited.add(nxt)

    def frame(self) -> Frame:
        return load(self.twin.shots[self.state])

    def read(self) -> screen.Screen:
        return self._read(self.state)


class MenuTwin:
    """The whole menu, offline: the page scan's Down cycle (camera frames from today) joined to the
    old explorer's item twins. Right on a row enters that row's item twin, matched by label; MENU
    inside an item returns to the row (MENU cancels: tested on the camera 2026-10-28). Moves inside
    an item are TwinCamera's (with its inferred wraps)."""

    def __init__(self, cycle: list, shots_dir: Path, labels: dict, twins: list):
        self.cycle, self.shots_dir, self.labels = cycle, shots_dir, labels
        self.i = 0
        self.item: TwinCamera | None = None
        self._cache: dict = {}
        from page_model import same_text  # noqa: E402  (kit/ on sys.path)
        self._same = same_text
        self._twins = twins

    def _twin_for(self, label):
        for t in self._twins:
            if self._same(t.item, label):
                return t
        return None

    def press(self, key):
        if self.item is not None:
            if key == "menu":
                self.item = None
                return
            self.item.press(key)
            return
        if key == "down":
            self.i = (self.i + 1) % len(self.cycle)
        elif key == "up":
            self.i = (self.i - 1) % len(self.cycle)
        elif key == "right":
            label = self.labels.get(self.i)
            t = self._twin_for(label) if label else None
            if t is None:
                raise Unrecorded(f"no recorded item for {label!r}")
            self.item = TwinCamera(t)
        else:
            raise Unrecorded(f"{key!r} on a menu page was never recorded")

    def read(self) -> screen.Screen:
        if self.item is not None:
            return self.item.read()
        if self.i not in self._cache:
            self._cache[self.i] = screen.read(load(self.shots_dir / self.cycle[self.i]["frame"]))
        return self._cache[self.i]
