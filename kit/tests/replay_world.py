"""A made-up link and eyes that answer a real camkit.live.LiveCamera from the camera's own recorded frames (no tests
here; the replay tests import it). The world is a graph: each state is one saved frame and the keys it answers, each to
the next state; a key the graph does not answer fails the test, as a press the camera was never seen to answer would be.
Every frame is read as a run reads it (camkit.screen, this computer's OCR), and every press goes through the camera's own
checks (LiveCamera.press, the link's word list aside), so a replay runs the kit's code in the camera's real order."""
from pathlib import Path

import pytest

from camkit import paths

RUNS = paths.a1ii_root()


def shot(rel: str) -> Path:
    """A saved frame of the a1 II's runs ("kit2_drive/shots/01218_down.png"), or the test is skipped where it is not."""
    p = RUNS / rel
    if not p.is_file():
        pytest.skip(f"{rel} is not here")
    return p


class FrameWorld:
    """The link and the eyes of a LiveCamera, from `graph`: {state: (frame path, {key: next state})}, starting at
    `start`. `sent` keeps every key that reached the link, with the state it went out on."""

    def __init__(self, graph: dict, start: str):
        from camkit.frames import load
        self.load, self.graph, self.state, self.sent, self.moves, self.menus = load, graph, start, [], 0, None
        for frame, _ in graph.values():
            if not Path(frame).is_file():
                pytest.skip(f"{frame} is not here")

    # the link
    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset(),
              judged=None):
        nxt = self.graph[self.state][1].get(key)
        self.sent.append((key, self.state))
        if nxt is None:
            raise AssertionError(f"{key} on {self.state}: a key the recorded frames do not answer")
        self.state = nxt
        self.moves += 1

    def dial(self, *a, **k):
        raise AssertionError("a dial in a replay: the recorded frames answer keys only")

    # the eyes
    timing = None
    name = "hdmi"

    def snapshot(self, tag):
        return self.load(Path(self.graph[self.state][0]))

    def grab(self, tag, save=True):
        return self.snapshot(tag)

    def settle(self, frame, key, expect_change=True, sent_at=None, **kw):
        return self.snapshot(key), True


def camera(world, tmp_path, may_open=()):
    """A real LiveCamera over the world, logging into a run folder under tmp_path."""
    from camkit import live
    from camkit.runs import Run
    return live.LiveCamera(world, world, Run("replay", root=tmp_path), may_open=may_open)
