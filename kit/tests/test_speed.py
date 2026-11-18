"""The speed-ups that only remove waste (the speed review of 2026-11-18): each one keeps what the kit
reads, judges and refuses before a press exactly as it was. Stored frames where runs/ holds them (skipped otherwise);
made-up cameras otherwise.
"""
import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from camkit import live, ocr, paths, screen  # noqa: E402

RUNS = paths.a1ii_root()


def frames_in(run, first, last, kind=None):
    """The saved frames of `run` numbered first..last, in order (those read as `kind` where given); skipped where the
    run is not here."""
    shots = RUNS / run / "shots"
    if not shots.exists():
        pytest.skip(f"{shots} not present")
    from camkit.frames import load
    out = []
    for p in sorted(shots.glob("*.png")):
        n = int(p.name[:5])
        if first <= n <= last:
            f = load(p)
            if kind is None or screen.read(f).kind == kind:
                out.append(f)
    return out


# ---------------------------------------------------------------- A: a submenu page's labels read once per view


class Replay:
    """A camera showing saved frames one after another; its run's log kept."""
    def __init__(self, frames):
        self.frames, self.i, self.logged = list(frames), 0, []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))
        self.show(0)

    def show(self, i):
        self.i, self.frame = i, self.frames[i]
        self.screen = screen.read(self.frame)

    def read(self):
        return self.screen


def test_a_submenu_views_labels_are_read_once_and_are_the_same_as_read_fresh(monkeypatch):
    """camkit.live.PageLabels (crawl_run's label reader) on the breadth crawl's own frames (kit2_breadth_crawl
    00356-00439: Subject Recognition's Recog. Target, a submenu that scrolls, with its cursor moving): each frame's rows
    (label, never-open, readings) are exactly what submenu_labels reads on that frame afresh, while the reader is asked
    once per view of the page (its rows as OCR reads them) instead of once per frame; a scroll is a new view. The calls
    and hits are logged."""
    frames = frames_in("kit2_breadth_crawl", 356, 439, kind="submenu")
    asked = []

    def ask_role(role, image, prompt, timeout):         # the reader names each row as OCR reads it on that frame
        f = next(f for f in frames if f.path.read_bytes() == image)
        s = screen.read(f)
        asked.append(f.path.name)
        return {"rows": [{"label": t.upper()} for t in live.submenu_texts(ocr.read([f.path])[f.path], s)]}
    monkeypatch.setattr(live, "ask_role", ask_role)
    cam = Replay(frames)
    fresh = []
    for i in range(len(frames)):
        cam.show(i)
        fresh.append(live.submenu_labels(cam)[1])
    per_frame = len(asked)
    asked.clear()
    reader = live.PageLabels()
    cam = Replay(frames)
    for i in range(len(frames)):
        cam.show(i)
        assert reader(cam)[1] == fresh[i], frames[i].path.name
    views = {(screen.page_key(f.image), tuple(live.submenu_texts(ocr.read([f.path])[f.path], screen.read(f))))
             for f in frames}
    assert per_frame == len(frames) and len(asked) == len(views) < len(frames) // 3
    assert len({v[1][0] for v in views}) >= 3, "the scrolled views (first row Auto, Human, Animal/Bird) are apart"
    logged = [f for k, f in cam.logged if k == "page_labels"]
    assert len(logged) == len(frames) and logged[-1]["calls"] == len(views)
    assert logged[-1]["hits"] == len(frames) - len(views)


def test_a_view_is_read_again_where_ocr_left_a_row_unread_or_the_reader_did_not_answer(monkeypatch, tmp_path):
    """No view is kept from a reading the reader did not answer (each later row asks it again, as before), nor keyed
    where OCR read a row as nothing (two views could share that key)."""
    rows = [(60, 100), (100, 140)]
    state = {"texts": ["Shading Comp.", "Distortion Comp."], "answer": None}
    monkeypatch.setattr(live.ocr, "read", lambda paths: {p: [] for p in paths})
    monkeypatch.setattr(live, "submenu_texts", lambda lines, s: list(state["texts"]))
    calls = []

    def ask_role(role, image, prompt, timeout):
        calls.append(1)
        if state["answer"] is None:
            raise TimeoutError("no answer")
        return {"rows": [{"label": t} for t in state["answer"]]}
    monkeypatch.setattr(live, "ask_role", ask_role)
    shot = tmp_path / "00001_down.png"
    shot.write_bytes(b"x")
    cam = SimpleNamespace(frame=SimpleNamespace(path=shot, image=np.zeros((480, 640, 3), "uint8")),
                          screen=SimpleNamespace(rows=rows, count=2, row=0),
                          run=SimpleNamespace(log=lambda kind, **f: None))
    cam.read = lambda: cam.screen
    reader = live.PageLabels()
    reader(cam)
    reader(cam)
    assert len(calls) == 2, "the reader did not answer: asked again on the next row"
    state["answer"] = ["Shading Comp.", "Distortion Comp."]
    reader(cam)
    reader(cam)
    assert len(calls) == 3, "answered once: the view's labels kept"
    state["texts"] = ["Shading Comp.", ""]
    reader(cam)
    reader(cam)
    assert len(calls) == 5, "a row OCR read as nothing: no key, read every time"


# ---------------------------------------------------------------- B: a proof's evidence reading in the background


class TwoOptions:
    """prove_row's camera for a two-option list (On, Off) opened from its row, the cursor where which_option says; each
    press shows a new frame (its name counts the presses)."""
    def __init__(self, tmp_path):
        self.where, self.option, self.keys, self.tmp = "row", 1, [], tmp_path
        self.frame = SimpleNamespace(path=tmp_path / "00001_start.png", image=None)

    def press(self, key, **kw):
        self.keys.append(key)
        self.frame = SimpleNamespace(path=self.tmp / f"{len(self.keys) + 1:05d}_{key}.png", image=None)
        if key == "right":
            self.where = "list"
        elif key in ("down", "up") and self.where == "list":
            self.option = 1 - self.option
        elif key in ("enter", "menu"):
            self.where = "row"

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "list"}[self.where])


def prove_two(tmp_path, monkeypatch, read, on_download=None, job=None):
    """prove_run.prove_row on TwoOptions with `read` as its vlm_option: (its proof lines, the order of its downloads
    and after_downloads). on_download() runs as each download goes out."""
    import io
    import json

    import prove_run as P
    from camkit.runs import Run
    events = []
    for name, value in (("place", lambda cam: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("which_option", lambda cam, job: cam.option), ("vlm_option", read),
                        ("bar_text", lambda cam: ["On", "Off"][cam.option]),
                        ("after_download", lambda cam, done: events.append("after_download")),
                        ("finish_attempt", lambda *a, **k: None)):
        monkeypatch.setattr(P, name, value)
    monkeypatch.setattr(P.camset, "read", lambda p: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [])
    monkeypatch.setattr(P.time, "time_ns", lambda: 1)

    def download(tag):
        events.append("download")
        if on_download:
            on_download()
        return tmp_path / f"{tag}.DAT"
    out = io.StringIO()
    with contextlib.suppress(P.RestoreAfter):           # a network row ends with the session's upload
        P.prove_row(TwoOptions(tmp_path), SimpleNamespace(download=download), Run("pass2", root=tmp_path),
                    job or {"path": ["Silent Mode"], "kind": "list", "labels": ["On", "Off"]}, tmp_path / "base.DAT", out)
    return [json.loads(x) for x in out.getvalue().splitlines()], events


def test_the_evidence_reading_goes_on_while_the_proof_does_and_its_line_is_as_before(tmp_path, monkeypatch):
    """prove_row asks the second reader about the chosen option on a worker thread, from the frame it was chosen on:
    the reader is still reading while Enter, the download and the wait after it go out (here it answers only once the
    download has gone out, which a reading asked in line could never see), and each proof line is the one written with
    the reader answering in line, in the same order, its "vlm" the answer about its own chosen frame."""
    import threading
    lines, events = prove_two(tmp_path, monkeypatch, lambda cam: f"seen {cam.frame.path.name}")
    downloaded, asked = threading.Event(), []

    def slow(cam):
        asked.append((threading.current_thread().name, cam.frame.path.name))
        downloaded.wait(5)
        return f"seen {cam.frame.path.name}" if downloaded.is_set() else "asked in line"
    background, events2 = prove_two(tmp_path, monkeypatch, slow, on_download=downloaded.set)
    assert background == lines and events2 == events == ["download", "after_download"] * 2
    assert [p["vlm"] for p in lines] == [f"seen {p['chosen_frame']}" for p in lines]
    assert asked and all(name.startswith("evidence") for name, _ in asked)
    assert [frame for _, frame in asked] == [p["chosen_frame"] for p in lines]


def test_the_evidence_reading_that_fails_is_kept_empty_and_a_network_rows_is_kept_as_before(tmp_path, monkeypatch):
    """A reading that fails (raises) is the empty answer the reader's failure always gave, and the line is written; a
    network row's reading is joined, then cut to the map's own option names (kept_option), as it was before."""
    import prove_run as P

    def broken(cam):
        raise RuntimeError("no reader")
    lines, _ = prove_two(tmp_path, monkeypatch, broken)
    assert [p["vlm"] for p in lines] == ["", ""]
    job = {"path": ["Bluetooth Function"], "kind": "list", "labels": ["On", "Off"], "choose": [0, 1],
           "network_row": "Bluetooth Function"}
    lines, _ = prove_two(tmp_path, monkeypatch, lambda cam: "Off DIRECT-madeup", job=job)
    assert [p["vlm"] for p in lines] == [P.kept_option("Off DIRECT-madeup", ["On", "Off"])] * 2
    assert "DIRECT" not in str(lines)
