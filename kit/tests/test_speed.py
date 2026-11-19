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


# ---------------------------------------------------------------- C: back to a submenu row by its place


class Submenu:
    """A made-up submenu of `labels` that comes round, the cursor on `at`; the camera at the row a proof's MENU left it
    on (the submenu's own row on the page above, with Right opening the submenu on its first row). Each press is read
    as LiveCamera reads it; `bars` counts the bar readings (OCR) and `pressed` the keys with the bar each went on."""
    def __init__(self, labels, at=0):
        self.labels, self.at, self.bars, self.pressed = list(labels), at, 0, []

    def read(self):
        return SimpleNamespace(kind="submenu", row=self.at % 6, page=self.at // 6)

    def press(self, key, **kw):
        self.pressed.append((key, self.labels[self.at]))
        if key == "down":
            self.at = (self.at + 1) % len(self.labels)


@pytest.fixture
def submenu(monkeypatch):
    from proving import nav

    def bar_text(cam):
        cam.bars += 1
        return cam.labels[cam.at]
    monkeypatch.setattr(nav, "bar_text", bar_text)
    monkeypatch.setattr(nav, "at_label", lambda cam, kind, label: cam.read().kind == kind and bar_text(cam) == label)
    monkeypatch.setattr(nav, "place", lambda cam: ("submenu", cam.at // 6, cam.at % 6))
    monkeypatch.setattr(nav, "same_place", lambda a, b: a == b)
    monkeypatch.setattr(nav, "same_state", lambda a, b: a.row == b.row and a.page == b.page)
    return nav


LABELS = ["Black Level", "Gamma", "Black Gamma", "Knee", "Color Mode", "Saturation", "Color Phase", "Color Depth",
          "Detail", "Copy", "Reset"]


def test_back_at_a_submenu_row_whose_place_is_known_the_label_is_read_once(submenu):
    """find_row with the row's place from this run (to_row's row_place): Down by place, no reading at each row, the
    label read once there, before the Right that follows (whose never-open check reads the live bar, as ever). Without
    a place, two readings a row (the check and the lap's), as before; the same Downs either way."""
    nav = submenu
    cam = Submenu(LABELS)
    assert nav.find_row(cam, "Color Depth") is True and cam.at == 7 and cam.bars == 15
    by_label = list(cam.pressed)
    cam = Submenu(LABELS)
    assert nav.find_row(cam, "Color Depth", at=("submenu", 1, 1)) is True and cam.at == 7 and cam.bars == 1
    assert cam.pressed == by_label


def test_a_known_place_that_does_not_read_as_the_row_falls_back_to_the_walk_by_label(submenu):
    """The place found but its bar reading another row (a submenu that scrolls keeps its page and cursor row): the walk
    by label goes on from there, a reading a row, and finds the row; a place never reached is walked by label too."""
    nav = submenu
    cam = Submenu(LABELS)
    assert nav.find_row(cam, "Color Depth", at=("submenu", 0, 3)) is True and cam.at == 7
    cam = Submenu(LABELS)
    assert nav.find_row(cam, "Copy", at=("submenu", 5, 0)) is True and cam.at == 9


def test_to_row_gives_the_rows_place_to_the_last_step_alone(monkeypatch):
    """to_row's walk back from the top-level row: Right into each submenu, the rows above found by label, the proved row
    by its place (enter_path, enter_pp)."""
    from proving import nav
    found = []
    monkeypatch.setattr(nav, "find_row", lambda cam, label, at=None: found.append((label, at)) or True)
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="submenu"))
    nav.enter_path(cam, ["Shooting", "Silent Mode Settings", "Target Function Settings", "Aperture Drive in AF"], 0,
                   at="the place")
    assert found == [("Silent Mode Settings", None), ("Target Function Settings", None),
                     ("Aperture Drive in AF", "the place")]


# ---------------------------------------------------------------- D: a box's step whose change was seen


def late_camera(monkeypatch, tmp_path, later_state="same"):
    """A LiveCamera after a press whose screen reads in the state it had before (a box's value is not in the state);
    its eyes count the looks again, and a look again reads `later_state`."""
    from camkit.runs import Run
    state = SimpleNamespace(kind="dialog", signature="boxes", struct="a", bits=np.zeros(4, bool))
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("late", root=tmp_path)
    cam.frame = SimpleNamespace(path=tmp_path / "00002_down.png", image=None)
    cam.screen = state
    looks = []

    def grab(tag, save=True):
        looks.append(tag)
        return SimpleNamespace(path=tmp_path / "late.png", image=None)
    cam.hdmi = SimpleNamespace(grab=grab, name="hdmi")
    cam.reading = lambda f: state if later_state == "same" else SimpleNamespace(kind="dialog", signature="moved",
                                                                                   struct="b", bits=np.ones(4, bool))
    clock = [0.0]                       # a clock that the waits move on
    monkeypatch.setattr(live.time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    monkeypatch.setattr(live.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(live, "keep", lambda *a, **k: None)
    return cam, state, looks


def test_a_box_step_whose_change_was_seen_goes_without_the_look_again(monkeypatch, tmp_path):
    """LiveCamera.look_late: with seen_enough (a box prover's step) and the settle having seen the screen change, the
    press ends there, no look again; with no change seen it looks again as before, and without the flag (every other
    press) it looks again as before, whether or not a change was seen."""
    cam, before, looks = late_camera(monkeypatch, tmp_path)
    assert cam.look_late("down", before, moved=True, seen_enough=True) is cam.frame and looks == []
    cam.look_late("down", before, moved=False, seen_enough=True)
    assert looks == ["down-late"]
    cam, before, looks = late_camera(monkeypatch, tmp_path)
    cam.look_late("down", before, moved=True)
    assert looks == ["down-late"]
    cam, before, looks = late_camera(monkeypatch, tmp_path, later_state="moved")
    got = cam.look_late("down", before, moved=False, seen_enough=True)
    assert looks == ["down-late"] and got.path.name == "late.png" and cam.screen.signature == "moved"


def test_the_box_provers_pass_the_flag_on_a_step_alone(monkeypatch):
    """optboxes_run's steps (Up, Down) pass seen_enough, its moves between boxes (Right, Left) do not; boxes_run's look
    and stepping pass it on Up and Down."""
    import boxes_run
    import optboxes_run as O
    sent = []
    cam = SimpleNamespace(press=lambda key, **k: sent.append((key, k.get("seen_enough", False))),
                          frame=SimpleNamespace(path=Path("00001_x.png")), hdmi=SimpleNamespace(name="hdmi"))
    monkeypatch.setattr(O, "in_box", lambda *a: None)
    for key in ("down", "up", "right", "left"):
        O.press_in(cam, key, "Custom 1", ["Type", "Standard", "Range"], 1)
    assert sent == [("down", True), ("up", True), ("right", False), ("left", False)]
    sent.clear()
    values = iter(["60p", "60p", "30p", "30p"])
    monkeypatch.setattr(boxes_run, "dashed", lambda cam, b: False)
    monkeypatch.setattr(boxes_run, "to_box", lambda cam, b: None)
    monkeypatch.setattr(boxes_run, "value", lambda cam, b: next(values))
    monkeypatch.setattr(boxes_run, "close_screen", lambda cam, link: None)
    with contextlib.suppress(Exception):
        boxes_run.look_open(cam, None, ["S&Q Settings", "Frame Rate"], 0)
    assert sent and all(flag for _, flag in sent)


# ---------------------------------------------------------------- E: waits nothing needs


def test_the_menu_lock_after_a_download_is_waited_only_for_what_is_left_of_it():
    """camkit.session.wait_lock (crawl_run's wait after its start download), where the measured lock does not apply:
    what is left of LOCK_S since the download returned, so a crawl whose ledger build took longer than the lock waits
    nothing more, one that took a second waits the rest; never less than the lock in all."""
    from camkit import session
    now, slept = [100.0 + 10.9], []                 # the ledger built in 10.9 s
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda s: slept.append(s) or now.__setitem__(0, now[0] + s))
    session.wait_lock(100.0, None, clock=clock)
    now[0] = 200.0 + 1.0
    session.wait_lock(200.0, None, clock=clock)
    assert slept == [pytest.approx(session.LOCK_S - 1.0)] and now[0] == pytest.approx(200.0 + session.LOCK_S)


def test_the_settings_downloads_go_once_the_shooting_screen_is_back_with_no_second_waited(monkeypatch, tmp_path):
    """boxes_run.choose, optboxes_run.keep's download and the session's end download as soon as the shooting screen is
    back: camlink waits up to 5 s for the camera to allow a settings download (sdk_session.h, downloadSettings) and the
    session's end tries four times; the lock after the download is waited as before."""
    import boxes_run
    import runner
    seq = []
    monkeypatch.setattr(boxes_run, "step_ok", lambda *a: {"chosen_frame": "c", "row_frame": "r", "vlm": ""})
    monkeypatch.setattr(boxes_run, "to_shooting", lambda *a: seq.append("shooting"))
    monkeypatch.setattr(boxes_run.time, "sleep", lambda s: seq.append(("sleep", s)))
    link = SimpleNamespace(download=lambda tag: seq.append("download") or tmp_path / f"{tag}.DAT")
    boxes_run.choose(None, link, None, None, None, ["Frame Rate"], 0, ["30p", "60p"], 1, ["A", "B"])
    from camkit import session
    assert seq[:2] == ["shooting", "download"] and seq[2][0] == "sleep" and len(seq) == 3
    assert seq[2][1] == pytest.approx(session.LOCK_S, abs=0.05), "no eyes: LOCK_S, as before"
    seq.clear()
    monkeypatch.setattr(runner.time, "sleep", lambda s: seq.append(("sleep", s)))
    monkeypatch.setattr(runner.session, "finish", lambda link, start, **k: seq.append("download"))
    runner.end_session(link, None, tmp_path / "start.DAT", reach=lambda link, eyes, why: seq.append("shooting"))
    assert seq == ["shooting", "download"]



# ---------------------------------------------------------------- F: the looks after a download, unsaved


def test_after_download_saves_only_the_look_that_decides(monkeypatch):
    """proving.nav.after_download: a look every 0.4 s until the lock has passed and the menu or the shooting screen is
    on show, none of them saved (LiveCamera.glance), then the deciding look saved and made the camera's frame
    (refresh(frame=)), and MENU where it is the shooting screen; the same waits and the same decision as before."""
    from proving import nav
    now = [0.0]
    monkeypatch.setattr(nav.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(nav.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    kinds = iter(["notice", "notice", "shooting", "shooting", "shooting", "shooting", "shooting", "shooting",
                  "shooting", "shooting", "shooting", "shooting"])
    looks, kept, pressed = [], [], []

    def glance(tag):
        f = SimpleNamespace(n=len(looks), kind=next(kinds))
        looks.append(f)
        return f, SimpleNamespace(kind=f.kind)

    def refresh(tag, frame=None):
        kept.append(frame)
        return SimpleNamespace(kind=frame.kind)
    cam = SimpleNamespace(glance=glance, refresh=refresh, press=lambda key, **k: pressed.append(key))
    nav.after_download(cam, 0.0)
    waited = 1.0 + 0.4 * (len(looks) - 1)
    assert waited > nav.LOCK_S and kept == [looks[-1]] and pressed == ["menu"]


def test_a_glance_is_not_saved_and_a_refresh_saves_the_glance_it_takes(tmp_path):
    """LiveCamera.glance grabs unsaved and leaves the camera's frame; refresh(frame=) saves that very frame under the
    run's shots (black while a row whose values are withheld is open) and reads it as the camera's screen."""
    from camkit.frames import Frame
    from camkit.runs import Run
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("looks", root=tmp_path)
    img = np.full((480, 640, 3), 40, np.uint8)
    saved = []
    cam.hdmi = SimpleNamespace(grab=lambda tag, save=True: saved.append(save) or Frame(img.copy(), 0.0, None, "hdmi"),
                               withheld=False)
    cam.frame, cam.screen = "before", "before"
    cam.rest = lambda tag: None
    cam._moves = lambda: 0
    cam._inside_after = lambda: None
    f, s = cam.glance("after-download")
    assert saved == [False] and f.path is None and cam.frame == "before" and s.kind
    cam.refresh("after-download", frame=f)
    assert cam.frame is f and f.path.exists() and f.path.parent == cam.run.dir / "shots" and saved == [False]
    cam.hdmi.withheld = True
    g, _ = cam.glance("after-download")
    cam.refresh("after-download", frame=g)
    from PIL import Image
    assert np.asarray(Image.open(g.path)).max() == 0, "withheld: saved black"



# ---------------------------------------------------------------- G: the page scan's extra look


class ScanReplay:
    """Eyes replaying a page scan's saved frames in the order the scan grabbed them: each settle takes the next saved
    frame of its tag, a late look (down-late) or a rest look (down-rest) the scan did not ask for passed over (`skipped`
    lists them); the settle's `moved` and `timing` are the scan's own (a Down moved; a late look moved where the scan's
    record took it)."""
    name = "hdmi"

    def __init__(self, shots, records):
        from camkit.frames import load
        self.load = load
        self.queue = sorted(shots.glob("*.png"))
        self.timing, self.skipped, self.presses = {}, [], 0
        self.took = {r["frame"] for r in records}
        self.timings = {r["n"]: r.get("timing") or {} for r in records}

    def _next(self, tag):
        while self.queue:
            p = self.queue.pop(0)
            if p.stem.split("_", 1)[1] == tag:
                return self.load(p)
            assert p.stem.split("_", 1)[1] in ("down-late", "down-rest"), f"passed over {p.name} for {tag}"
            self.skipped.append(p.name)
        raise AssertionError(f"no saved frame left for {tag}")

    def grab(self, tag="f", save=True):
        return self._next(tag)

    def settle(self, before, tag="f", expect_change=None, sent_at=None, **kw):
        f = self._next(tag)
        if tag == "down-late":
            return f, f.path.name in self.took
        self.timing = self.timings.get(self.presses, {})
        return f, True


class ScanPresses:
    """The page scan's camera link, counting its presses for the replay."""
    def __init__(self, eyes):
        self.eyes = eyes

    def press(self, button, screen=None):
        self.eyes.presses += 1


@pytest.mark.parametrize("scan_run", ["kit2_page_scan_1118p", "kit2_page_scan_movie_1108"])
def test_the_page_scan_over_its_saved_frames_gives_the_same_records_with_fewer_late_looks(tmp_path, scan_run):
    """page_scan.Scan over a scan's own frames (HDMI eyes; kit2_page_scan_1118p: 274 records, 67 page changes each given
    a late look then, none of which saw a later change; kit2_page_scan_movie_1108: the one late look that did, menu to
    the Main tiles, record 228): the scan made the new way, a late look only where the screen's kind changes on a page
    change (or on OSD eyes), writes the very records the camera's scan wrote, that one taken from its late look still,
    and asks for the late look on far fewer page changes."""
    import json

    import page_scan
    run_dir = RUNS / scan_run
    if not (run_dir / "shots").exists():
        pytest.skip(f"{run_dir} not present")
    records = [json.loads(x) for x in (run_dir / "scan.jsonl").read_text(encoding="utf-8").splitlines()]
    eyes = ScanReplay(run_dir / "shots", records)
    scan = page_scan.Scan.__new__(page_scan.Scan)
    scan.run, scan.link, scan.hdmi, scan.max = SimpleNamespace(dir=tmp_path, stop_requested=lambda: False), \
        ScanPresses(eyes), eyes, 400
    scan.out, scan.presses, scan.scan_id = tmp_path / "scan.jsonl", 0, records[0].get("scan")
    scan.run_scan()
    got = [json.loads(x) for x in (tmp_path / "scan.jsonl").read_text(encoding="utf-8").splitlines()]
    assert got == records
    changes = sum(1 for r in records if r.get("new_page"))
    asked = changes - len([n for n in eyes.skipped if n.endswith("down-late.png")])
    assert asked < changes // 5, f"late looks still asked: {asked} of {changes}"


# ---------------------------------------------------------------- H: two lines for the next review


def test_every_question_to_a_reader_logs_how_long_it_took(monkeypatch, tmp_path):
    """camkit.vlm.ask_role logs each question it sends ("reader_asked": the role, the reader's configured name, the
    seconds it took, whether it answered) in the run's events.jsonl, the stand-in's question too; nothing of the frame or
    the answer. A question never sent (no reader, held) logs nothing."""
    import json

    from camkit import vlm
    from camkit.runs import Run
    run = Run("asked", root=tmp_path)
    monkeypatch.setattr(vlm, "_RUN", run)
    monkeypatch.setattr(vlm, "_FAILING", set())
    monkeypatch.setattr(vlm, "playing", lambda name: {"name": "b70"})
    monkeypatch.setattr(vlm, "local_only", lambda cfg, name: None)
    monkeypatch.setattr(vlm, "_SKIPPED", set())

    class Reader:
        def __init__(self, fails=False):
            self.fails = fails

        def ask(self, image, prompt):
            if self.fails:
                raise TimeoutError("timed out")
            return {"selected": "Off"}
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, timeout: Reader())
    assert vlm.ask_role("second", b"frame", "a question", 25) == {"selected": "Off"}
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, timeout: Reader(fails=True))
    with pytest.raises(TimeoutError):
        vlm.ask_role("second", b"frame", "a question", 25)
    asked = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    asked = [e for e in asked if e["kind"] == "reader_asked"]
    assert [(e["role"], e["reader"], e["answered"]) for e in asked] == [("second", "b70", True), ("second", "b70", False)]
    assert all(isinstance(e["seconds"], float) and e["seconds"] >= 0 for e in asked)
    assert "Off" not in json.dumps(asked) and "a question" not in json.dumps(asked)


def test_the_link_open_line_says_when_the_runs_process_started(tmp_path, monkeypatch):
    """camkit.STARTED, set as camkit is imported (every kit program imports it before any other package), goes with the
    run's "link_open" line ("process_started"), so the time from the process's start to the open link can be measured."""
    import json

    import camkit
    import fake_camlink
    from camkit.link import Link
    from camkit.runs import Run
    monkeypatch.delenv("CAMSET_USB", raising=False)
    run = Run("started", root=tmp_path)
    with Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False):
        pass
    opened = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    opened = next(e for e in opened if e["kind"] == "link_open")
    assert opened["process_started"] == round(camkit.STARTED, 3) <= opened["t"]


# ---------------------------------------------------------------- the menu's lock after a download, as measured


class LockEyes:
    """Eyes on a fake clock after a download: the screen reads as each (kind, until) of `timeline` in turn, then as
    the shooting screen; by default the shooting screen until 0.3 s (before the notice comes), the notice until
    `ready_at` s, then the shooting screen. `grabs` counts the frames grabbed; `run` keeps the logged lines."""
    def __init__(self, now, ready_at=1.97, name="hdmi", timeline=None):
        self.now, self.name, self.grabs, self.logged = now, name, 0, []
        self.timeline = timeline if timeline is not None else [("shooting", 0.3), ("notice", ready_at)]
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    def kind(self):
        return next((k for k, until in self.timeline if self.now[0] < until), "shooting")

    def grab(self, tag="f", save=True):
        self.grabs += 1
        return SimpleNamespace(kind=self.kind())


def lock_clock(monkeypatch):
    """A fake clock from 0 (the download's reply), and camkit.session's screen reading the fake frames' kinds."""
    from camkit import session
    now = [0.0]
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(session, "screen", SimpleNamespace(read=lambda f: f))
    return session, now, clock


@pytest.mark.parametrize("timeline,ends,why", [
    (None, 1.97, "the shooting screen after the notice"),                      # the measured case: at once
    ([("shooting", 0.3), ("notice", 0.9)], 0.9, "the shooting screen after the notice"),   # a quick save: no floor
    ([("notice", 6.0)], 6.0, "the shooting screen after the notice"),          # a save that keeps its notice 6 s
    ([], 2.4, "the shooting screen, no notice seen, and 2.4 s"),               # the notice missed: 2.4 s as landed
    ([("unknown", 9.0)], 4.5, "4.5 s"),                                        # nothing seen: the old rule
    ([("notice", 99.0)], 25.05, "the notice still on show after 25 s")])       # a notice that never goes
def test_with_hdmi_eyes_in_stills_the_lock_ends_on_the_shooting_screen_after_the_notice(monkeypatch, timeline, ends,
                                                                                       why):
    """camkit.session.wait_lock, HDMI eyes, the scan's mode Stills (kit2_speed_lock's lock_seen.jsonl: MENU taken the
    moment the notice is gone): the shooting screen after the notice ends the wait at once, however soon (no floor) or
    late (a notice on show past LOCK_S is waited out); the shooting screen with no notice seen keeps LOCK_HDMI_S;
    nothing seen ends it at LOCK_S as before; a notice that never goes ends it at LOCK_NOTICE_LIMIT. Never before the
    shooting screen is seen after the notice, or the rule that ended it; one line logged per wait."""
    session, now, clock = lock_clock(monkeypatch)
    monkeypatch.setattr(session, "MODE", "Stills")
    eyes = LockEyes(now, timeline=timeline)
    assert session.wait_lock(0.0, eyes, clock=clock) == why
    assert now[0] == pytest.approx(ends, abs=0.06)
    assert eyes.logged == [("lock_wait", {"ended": why, "seconds": pytest.approx(ends, abs=0.06)})]


@pytest.mark.parametrize("eyes_name,mode", [("osd", "Stills"), ("osd", "Movie"), ("hdmi", "S&Q"), ("hdmi", None)])
def test_osd_eyes_s_and_q_or_no_mode_keep_the_old_lock(monkeypatch, eyes_name, mode):
    """OSD eyes (its picture lags, not measured), S&Q (not measured) and a run that cannot tell its mode keep LOCK_S, no
    frame looked at, the notice or not; a caller's own longer wait (prove_run's 5 s) is never cut short."""
    session, now, clock = lock_clock(monkeypatch)
    monkeypatch.setattr(session, "MODE", mode)
    eyes = LockEyes(now, 0.5, name=eyes_name)
    assert session.wait_lock(0.0, eyes, clock=clock) == "4.5 s" and now[0] == pytest.approx(4.5) and eyes.grabs == 0
    now[0] = 0.0
    session.wait_lock(0.0, None, "Stills", clock=clock, longest=5.0)
    assert now[0] == pytest.approx(5.0)
    assert session.lock_measured(SimpleNamespace(name="hdmi"), "Stills") and not session.lock_measured(None, "Stills")


def test_lock_over_is_the_old_rule_or_what_the_eyes_saw():
    """lock_over on what has been seen: past `longest` always, but where the measured rule applies and the notice is
    on show (up to LOCK_NOTICE_LIMIT); before it with HDMI eyes in a measured mode, the shooting screen after the notice
    at once, or the shooting screen with no notice once LOCK_HDMI_S has passed."""
    from camkit import session

    def seen(*kinds):
        s = session.LockSeen()
        for k in kinds:
            s.see(k)
        return s
    hdmi = SimpleNamespace(name="hdmi")
    assert session.lock_over(4.6, seen()) and not session.lock_over(4.4, seen("shooting"), hdmi)
    assert session.lock_over(0.5, seen("shooting", "notice", "shooting"), hdmi, "Stills")
    assert session.lock_over(0.5, seen("shooting", "notice", "shooting"), hdmi, "Movie")
    assert not session.lock_over(0.5, seen("shooting", "notice", "shooting"), hdmi, "S&Q")
    assert not session.lock_over(6.0, seen("notice"), hdmi, "Stills") and session.lock_over(6.0, seen("notice"), hdmi)
    assert session.lock_over(2.4, seen("shooting"), hdmi, "Stills") and not session.lock_over(2.3, seen("shooting"),
                                                                                              hdmi, "Stills")


def after_download_on(monkeypatch, ready_at, name="hdmi", mode="Stills", timeline=None):
    """proving.nav.after_download on a fake clock: the camera's screen as LockEyes' timeline (by default the
    shooting screen until 0.3 s, the notice until `ready_at`, then the shooting screen); (when it ended, the keys
    pressed, the lines logged)."""
    from camkit import session
    from proving import nav
    now = [0.0]
    monkeypatch.setattr(nav.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(nav.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(session, "MODE", mode)
    pressed = []
    eyes = LockEyes(now, ready_at, name=name, timeline=timeline)

    def glance(tag):
        kind = eyes.kind()
        return SimpleNamespace(kind=kind), SimpleNamespace(kind=kind)
    cam = SimpleNamespace(glance=glance, refresh=lambda tag, frame=None: SimpleNamespace(kind=frame.kind),
                          press=lambda key, **k: pressed.append(key), hdmi=eyes)
    nav.after_download(cam, 0.0)
    return now[0], pressed, eyes.logged


def test_after_download_ends_on_the_shooting_screen_after_the_notice_with_hdmi_in_stills(monkeypatch):
    """proving.nav.after_download: with HDMI eyes in Stills, its looks every 0.1 s from the reply, it ends at the
    first look on the shooting screen after the notice (2.0 s, the notice gone at 1.97 s), a notice on show 6 s waited
    out, and with no notice seen the shooting screen once 2.4 s have passed; so in Movie (kit2_speed_lock_mv); OSD eyes
    and S&Q end at the first look past LOCK_S, 4.6 s, as before; MENU after it every time, one line logged."""
    end, pressed, logged = after_download_on(monkeypatch, 1.97)
    assert end == pytest.approx(2.0, abs=0.01) and pressed == ["menu"]
    assert [f["ended"] for k, f in logged] == ["the shooting screen after the notice"]
    assert after_download_on(monkeypatch, 6.0)[0] == pytest.approx(6.0, abs=0.11)
    assert after_download_on(monkeypatch, 1.97, timeline=[])[0] == pytest.approx(2.4, abs=0.11)
    assert after_download_on(monkeypatch, 1.97, name="osd")[0] == pytest.approx(4.6)
    assert after_download_on(monkeypatch, 1.84, mode="Movie")[0] == pytest.approx(1.9, abs=0.01)
    assert after_download_on(monkeypatch, 1.97, mode="S&Q")[0] == pytest.approx(4.6)


def test_the_page_scans_wait_after_its_download_goes_by_its_mode(monkeypatch):
    """page_scan.after_download: the shooting screen after the notice in Stills and Movie over HDMI (1.97 s), LOCK_S
    in S&Q."""
    import page_scan
    for mode, ends in (("Stills", 1.97), ("Movie", 1.97), ("S&Q", 4.5)):
        now = [0.0]
        monkeypatch.setattr(page_scan.time, "monotonic", lambda now=now: now[0])
        monkeypatch.setattr(page_scan.time, "sleep", lambda s, now=now: now.__setitem__(0, now[0] + s))
        monkeypatch.setattr(page_scan.screen, "read", lambda f: f)
        eyes = LockEyes(now, 1.97)
        page_scan.after_download(eyes, 0.0, mode)
        assert now[0] == pytest.approx(ends, abs=0.41) and now[0] >= ends - 1e-9


def test_a_movie_scan_makes_the_runs_lock_the_measured_one(monkeypatch, tmp_path):
    """The mode a run's lock goes by is its page scan's: runner.load_scan sets camkit.session.MODE from the scan's own
    record, spelled as runner.SCAN_MODES spell it whatever word recorded it, so a Movie scan's run takes the measured
    lock with HDMI eyes (kit2_speed_lock_mv, 2026-11-18) and an S&Q scan's, or one that records no mode, LOCK_S."""
    import json
    import runner
    from camkit import session
    monkeypatch.setattr(session, "MODE", None)
    monkeypatch.setattr(runner, "load", lambda p: None)
    monkeypatch.setattr(runner, "screen", SimpleNamespace(read=lambda f: SimpleNamespace(signature="s", kind="menu",
                                                                                           row=0)))
    (tmp_path / "scan_rekeyed.json").write_text(json.dumps([{"frame": "1.png", "page": "p"}] * 2), encoding="utf-8")
    (tmp_path / "model.json").write_text(json.dumps([{"key": "p", "rows": []}]), encoding="utf-8")
    hdmi = SimpleNamespace(name="hdmi")
    for word, mode, measured in (("movie", "Movie", True), ("Stills", "Stills", True), ("S&Q Motion", "S&Q", False),
                                 (None, None, False)):
        (tmp_path / runner.SCAN_MODE_FILE).write_text(json.dumps({"mode": word}), encoding="utf-8")
        runner.load_scan(tmp_path)
        got = session.MODE
        assert got == mode and session.lock_measured(hdmi) is measured, word


def test_the_box_provers_wait_the_measured_lock_with_their_own_eyes(monkeypatch, tmp_path):
    """boxes_run.choose: after the download, the lock by camkit.session.wait_lock with the run's eyes, so HDMI eyes in
    Stills end it once the shooting screen is back after the notice (1.0 s here)."""
    import boxes_run
    from camkit import session
    session_, now, clock = lock_clock(monkeypatch)
    monkeypatch.setattr(session, "MODE", "Stills")
    monkeypatch.setattr(boxes_run, "time", clock)
    monkeypatch.setattr(boxes_run, "step_ok", lambda *a: {"chosen_frame": "c", "row_frame": "r", "vlm": ""})
    monkeypatch.setattr(boxes_run, "to_shooting", lambda *a: None)
    eyes = LockEyes(now, 1.0)
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    boxes_run.choose(None, link, eyes, None, None, ["Frame Rate"], 0, ["30p", "60p"], 1, ["A", "B"])
    assert now[0] == pytest.approx(1.0, abs=0.06) and eyes.grabs >= 1


def test_the_crawl_the_first_open_check_afreg_and_prove_run_go_through_the_one_wait(monkeypatch, tmp_path):
    """Every other caller changed waits through camkit.session.wait_lock with its own eyes: first_open's check (its
    `lock` the longest wait), afreg's waits before a MENU (after the setup, after an area's download, and an area
    put off), and prove_run's wait after a session's download (5 s the longest, as before)."""
    from camkit import first_open, session
    from proving import base
    import afreg_run
    calls = []

    def wait_lock(since, eyes=None, mode=None, clock=None, longest=session.LOCK_S, poll=0.1):
        calls.append((getattr(eyes, "name", None), longest))
        return "lock"
    monkeypatch.setattr(session, "wait_lock", wait_lock)
    monkeypatch.setattr(base, "wait_lock", wait_lock)
    # afreg: the setup's download, then an area put off (held already), then an area registered
    monkeypatch.setattr(afreg_run, "setup_steps", lambda *a: [])
    monkeypatch.setattr(afreg_run, "setup_rows", lambda *a: [])
    monkeypatch.setattr(afreg_run.time, "sleep", lambda s: None)
    import camkit.camset as camset
    import prove_run
    monkeypatch.setattr(camset, "read", lambda p: p)
    monkeypatch.setattr(camset, "diff", lambda a, b: [])
    monkeypatch.setattr(prove_run, "to_shooting", lambda *a, **k: None)
    hdmi = SimpleNamespace(name="hdmi")
    run = SimpleNamespace(dir=tmp_path)
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    afreg_run.prepare(None, link, hdmi, run, None, None, None, False, False, tmp_path / "start.DAT")
    t = {"label": "Wide", "code": 1, "own_key": "k", "expected": []}
    monkeypatch.setattr(afreg_run, "choose_area", lambda *a: {"shown": "Wide"})
    monkeypatch.setattr(prove_run, "held_value", lambda cs, k: 1)
    with pytest.raises(afreg_run.PutOff):
        afreg_run.register(None, link, hdmi, run, None, None, [], [], t, (0, "Wide", None), None, [], None)
    monkeypatch.setattr(prove_run, "held_value", lambda cs, k: 0)
    monkeypatch.setattr(afreg_run, "ready_to_hold", lambda *a, **k: None)
    monkeypatch.setattr(afreg_run, "hold_fn", lambda *a, **k: {"said": "registered", "frames": []})
    monkeypatch.setattr(afreg_run, "proof_line", lambda *a, **k: {"changes": [], "side_effects": [], "applied": True})
    afreg_run.register(None, link, hdmi, run, None, None, [], [], t, (0, "Wide", None), None, [], SimpleNamespace(
        write=lambda s: None, flush=lambda: None))
    assert calls == [("hdmi", session.LOCK_S)] * 3
    calls.clear()
    # first_open's check, its lock given as the crawl gives it
    fo = first_open.FirstOpens(SimpleNamespace(download=lambda tag: tmp_path / "f.DAT", call=lambda *a, **k: {}),
                               hdmi, SimpleNamespace(root=tmp_path, log=lambda *a, **k: None), tmp_path / "s.DAT",
                               first_open.Seen(), "", 3.5, wait=lambda *a, **k: "shooting")
    monkeypatch.setattr(first_open, "coverage", SimpleNamespace(append_look=lambda *a, **k: None))
    monkeypatch.setattr(session, "in_playback_now", lambda link: False)
    monkeypatch.setattr(session, "compared", lambda start, after, say=None: [])
    fo.pending = []
    fo._clean = lambda rows, how: None
    fo.settle(SimpleNamespace(press=lambda key, **k: None))
    assert calls == [("hdmi", 3.5)]


def test_the_crawl_and_prove_run_wait_after_their_download_through_the_one_wait():
    """crawl_run's wait after its start download and prove_run's after a session's download (5 s before, its longest
    still: runner.session_start's settle) are camkit.session.wait_lock with the run's eyes, measured from the
    download's reply (their mains need a camera: read off their source)."""
    import re
    crawl = (KIT / "crawl_run.py").read_text(encoding="utf-8")
    prove = (KIT / "prove_run.py").read_text(encoding="utf-8")
    start = (KIT / "runner.py").read_text(encoding="utf-8").split("def session_start", 1)[1].split("\ndef ", 1)[0]
    assert re.search(r'before = link\.download\("before"\)\n\s+downloaded = time\.monotonic\(\)', crawl)
    assert "wait_lock(downloaded, hdmi, clock=time)" in crawl and "lock_left" not in crawl
    assert re.search(r'here = session_start\(link, eyes, [^\n]*\n[^\n]*settle=5\.0', prove)
    assert "time.sleep(5)\n" not in prove
    assert re.search(r'start = link\.download\(tag\)\n\s+since = time\.monotonic\(\)', start)
    assert "session.wait_lock(since, eyes, clock=time, longest=settle)" in start and "time.sleep(" not in start


# ---------------------------------------------------------------- the camera after an upload, as measured


class RestartEyes:
    """HDMI eyes on a fake clock after an upload: the shooting screen until 1 s, the notice until 5 s, black until
    `back_at`, then the shooting screen (`notice` False: never the notice); a grab between 6 and 8 s fails, as a feed
    may while the camera restarts."""
    def __init__(self, now, back_at=16.0, notice=True, name="hdmi"):
        self.now, self.back_at, self.notice, self.name, self.grabs = now, back_at, notice, name, 0

    def grab(self, tag="f", save=True):
        self.grabs += 1
        t = self.now[0]
        if 6.0 <= t < 8.0:
            raise RuntimeError("no frames from the capture dongle")
        kind = ("shooting" if t < 1.0 else "notice" if t < 5.0 and self.notice else
                "unknown" if t < self.back_at else "shooting")
        return SimpleNamespace(kind=kind)


def restart_world(monkeypatch, fails=(), opened_at=None):
    """camkit.session on a fake clock from the upload's reply, its screen reading the fake frames' kinds; a link class
    whose tries fail as `fails` lists them in turn ("connect": LinkError before the link opened, "download": a failure
    once open), or, with `opened_at`, fail to connect until that time; (session, now, clock, link_class, tries, run)."""
    from camkit import session
    from camkit.link import LinkError
    now = [0.0]
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(session, "screen", SimpleNamespace(read=lambda f: f))
    monkeypatch.setattr(session, "compared", lambda start, after, say=None: [])
    tries, plan = [], list(fails)

    class Tried:
        def __init__(self, run):
            tries.append(round(now[0], 2))
            now[0] += 1.0                           # a try takes its time
            why = plan.pop(0) if plan else (None if opened_at is None or now[0] >= opened_at else "connect")
            if why == "connect":
                raise LinkError("camera link did not connect: fingerprint: Connect_SSH_GetFingerprintFailed",
                                opened=False)
            self.why = why

        def __enter__(self):
            if self.why == "download":
                raise RuntimeError("download: refused")
            return SimpleNamespace(download=lambda tag: "restored.DAT")

        def __exit__(self, *exc):
            return False
    logged = []
    run = SimpleNamespace(log=lambda kind, **f: logged.append((kind, f)))
    return session, now, clock, Tried, tries, run, logged


def test_the_restore_check_starts_on_the_shooting_screen_after_the_notice(monkeypatch):
    """camkit.session.restarted with HDMI eyes: the first try waits for a frame read as the shooting screen after one
    read as the notice (16 s here, not the shooting screen at 0.5 s before the notice, nor the failing grabs), or 20 s
    where the notice is never seen; with OSD eyes or none, 20 s, no frame grabbed."""
    session, now, clock, *_ = restart_world(monkeypatch)
    assert session.restarted(RestartEyes(now), clock) == "the shooting screen after the notice"
    assert now[0] == pytest.approx(16.0, abs=0.3)
    now[0] = 0.0
    assert session.restarted(RestartEyes(now, notice=False), clock) == "20 s" and now[0] == pytest.approx(20.0)
    for eyes in (RestartEyes(now, name="osd"), None):
        now[0] = 0.0
        assert session.restarted(eyes, clock) == "20 s" and now[0] == pytest.approx(20.0)
        assert eyes is None or eyes.grabs == 0


def test_a_try_that_does_not_connect_is_tried_again_3_s_later_and_the_wait_is_logged(monkeypatch):
    """verify_restore with HDMI eyes: the first try on the shooting screen (16 s), a try that did not connect tried
    again 3 s after it failed, the link that opens then checked as before (its ready wait, the download, the count);
    each wait in the run's events.jsonl with what it waited for and its seconds."""
    session, now, clock, Tried, tries, run, logged = restart_world(monkeypatch, fails=["connect", "connect"])
    eyes = RestartEyes(now)
    n = session.verify_restore(run, Path("start.DAT"), link_class=Tried, eyes=eyes, clock=clock, say=lambda m: None)
    assert n == 0 and tries == [pytest.approx(16.0, abs=0.3), pytest.approx(20.0, abs=0.3), pytest.approx(24.0, abs=0.3)]
    kinds = [(k, f.get("waited_for")) for k, f in logged]
    assert kinds[0] == ("restore_wait", "the shooting screen after the notice")
    assert kinds[1:3] == [("restore_wait", "the next try")] * 2 and kinds[3][0] == "restore_reconnected"
    assert logged[3][1]["tries"] == 3 and all("seconds" in f for _, f in logged)
    assert now[0] == pytest.approx(25.0 + 3.0, abs=0.3), "the ready wait after the link opened, as before"


def test_without_hdmi_eyes_the_first_try_is_at_20_s_and_other_failures_wait_as_before(monkeypatch):
    """No eyes: the first try at 20 s. A failure once the link opened (a download refused) is tried again `pause` s
    (15) later, as before."""
    session, now, clock, Tried, tries, run, logged = restart_world(monkeypatch, fails=["download"])
    assert session.verify_restore(run, Path("start.DAT"), link_class=Tried, clock=clock, say=lambda m: None) == 0
    assert tries == [pytest.approx(20.0), pytest.approx(36.0)]
    assert ("restore_wait", "the next try after a failure") in [(k, f.get("waited_for")) for k, f in logged]


def test_a_camera_that_never_answers_is_given_up_at_the_old_deadline(monkeypatch):
    """A link that never connects: tried every 3 s from 20 s, no try starting past the fixed wait's deadline (40 s plus
    six tries 15 s apart: 130 s from the call), then None, said and logged; never slower than the fixed wait."""
    session, now, clock, Tried, tries, run, logged = restart_world(monkeypatch, opened_at=1e9)
    assert session.verify_restore(run, Path("start.DAT"), link_class=Tried, clock=clock, say=lambda m: None) is None
    assert tries[0] == pytest.approx(20.0) and max(tries) <= 130.0 and len(tries) > 6
    assert all(b - a == pytest.approx(4.0) for a, b in zip(tries, tries[1:], strict=False)), "a try 1 s, then 3 s"
    assert logged[-1][0] == "restore_unreached" and now[0] <= 130.0 + 1.0
    # a check given no settle (the tests' own) tries at once
    session, now, clock, Tried, tries, run, logged = restart_world(monkeypatch)
    assert session.verify_restore(run, Path("start.DAT"), settle=0, ready=0, link_class=Tried, clock=clock,
                                  say=lambda m: None) == 0 and tries == [0.0]


def test_the_runs_that_still_hold_their_hdmi_eyes_hand_them_to_the_check(monkeypatch):
    """runner.prover_session's restore check (unless a walker asks it not to: watch_restart) and prove_run's
    (put_start_back, a session's end) pass their eyes, so an HDMI run starts its check on the shooting screen; a run
    that has closed its eyes passes none (20 s)."""
    runner_src = (KIT / "runner.py").read_text(encoding="utf-8")
    prove_src = (KIT / "prove_run.py").read_text(encoding="utf-8")
    assert 'restore_checked(run, ending, start, note, **({"eyes": eyes} if watch_restart else {}),' in runner_src
    assert "watch_restart: bool = True" in runner_src
    assert "verify_restore(run, ref, eyes=hdmi," in prove_src and "check_restore(run, ending, start, eyes=hdmi," in prove_src


# ---------------------------------------------------------------- a MENU from the shooting screen, watched


class MenuCamera:
    """A camera on a fake clock just after a MENU from the shooting screen: its screen the shooting screen until
    `menu_at` s (None: never), then a menu page; MENU presses counted; `fresh` the refreshes that grabbed a new frame,
    `taken` those that took a watched one."""
    def __init__(self, now, menu_at, name="hdmi"):
        self.now, self.menu_at, self.hdmi = now, menu_at, SimpleNamespace(name=name)
        self.pressed, self.fresh, self.taken, self.glances = [], [], [], 0
        self.screen = SimpleNamespace(kind="shooting")

    def kind(self):
        return "menu" if self.menu_at is not None and self.now[0] >= self.menu_at else "shooting"

    def read(self):
        return self.screen

    def glance(self, tag):
        self.glances += 1
        k = self.kind()
        return SimpleNamespace(kind=k, t=self.now[0]), SimpleNamespace(kind=k)

    def refresh(self, tag, frame=None):
        (self.fresh if frame is None else self.taken).append(round(self.now[0], 2))
        self.screen = SimpleNamespace(kind=frame.kind if frame is not None else self.kind())
        return self.screen

    def press(self, key, **k):
        self.pressed.append((key, round(self.now[0], 2)))
        if key == "menu" and self.menu_at is None:
            self.menu_at = self.now[0] + 99.0       # still not taken


def menu_clock():
    now = [0.0]
    return now, SimpleNamespace(monotonic=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))


def test_a_menu_page_that_comes_is_taken_at_once_and_one_that_does_not_is_judged_on_a_fresh_frame(monkeypatch):
    """runner.menu_check with HDMI eyes: the first frame that reads as a menu page ends the wait (0.4 s here, not
    1.5); where none comes, a fresh frame after the full MENU_LATE s decides, as before; OSD eyes: MENU_LATE s and a
    fresh frame, nothing watched."""
    import runner
    now, clock = menu_clock()
    cam = MenuCamera(now, 0.4)
    assert runner.menu_check(cam, clock=clock).kind == "menu" and cam.taken == [pytest.approx(0.4, abs=0.06)]
    assert now[0] < 0.46 and cam.fresh == []
    now[0] = 0.0
    cam = MenuCamera(now, None)
    assert runner.menu_check(cam, clock=clock).kind == "shooting"
    assert cam.fresh == [pytest.approx(runner.MENU_LATE, abs=0.06)] and cam.taken == []
    now[0] = 0.0
    cam = MenuCamera(now, 0.4, name="osd")
    assert runner.menu_check(cam, clock=clock).kind == "menu" and cam.glances == 0
    assert cam.fresh == [pytest.approx(runner.MENU_LATE)]


def test_no_second_menu_goes_before_a_fresh_frame_after_the_full_wait_shows_the_shooting_screen(monkeypatch):
    """runner.menu_from_shooting and proving.nav.to_row: a menu that comes 0.4 s after MENU is taken then, with no
    second MENU; a MENU not taken gets its second press only after a fresh frame at the full MENU_LATE s still shows
    the shooting screen (the rule of 2026-10-29), at most twice more."""
    import runner
    from proving import nav
    now, clock = menu_clock()
    monkeypatch.setattr(runner, "time", clock)
    cam = MenuCamera(now, 0.4)
    runner.menu_from_shooting(cam)
    assert [k for k, t in cam.pressed] == ["menu"] and now[0] == pytest.approx(0.4, abs=0.06)
    now[0] = 0.0
    cam = MenuCamera(now, None)
    runner.menu_from_shooting(cam)
    assert [t for k, t in cam.pressed] == [0.0, pytest.approx(1.5, abs=0.06), pytest.approx(3.0, abs=0.12),
                                           pytest.approx(4.5, abs=0.18)]
    assert all(f >= p for f, (k, p) in zip(cam.fresh, cam.pressed, strict=False))
    # nav.to_row's own loop, on the same rule
    now[0] = 0.0
    monkeypatch.setattr(nav, "time", clock)
    monkeypatch.setattr(nav, "place", lambda cam: "here")
    monkeypatch.setattr(nav, "same_place", lambda a, b: a == b)
    cam = MenuCamera(now, 0.6)
    nav.to_row(cam, ["Shooting"], None, "here")
    assert cam.pressed == [] and cam.taken == [pytest.approx(0.6, abs=0.06)] and now[0] < 0.7


class LateMenuCamera(MenuCamera):
    """A MenuCamera whose first MENU closes what is open (a notice, a row: the shooting screen at once) where
    `closes_first`, and whose next MENU opens the menu `late` s after it, the frame read after that press still showing
    the shooting screen (the shooting screen's own redraw ended its settle: kit2_pass2 250525-250527, 2026-11-18). Any
    other key on the shooting screen is recorded as a leak."""
    def __init__(self, now, late, closes_first=False):
        super().__init__(now, None)
        self.late, self.closes_first, self.leaks = late, closes_first, []
        if closes_first:
            self.screen = SimpleNamespace(kind="notice")

    def kind(self):
        if self.menu_at is not None and self.now[0] >= self.menu_at:
            return "menu"
        return self.screen.kind if self.screen.kind == "notice" else "shooting"

    def press(self, key, **k):
        self.pressed.append((key, round(self.now[0], 2)))
        if key != "menu":
            if self.kind() == "shooting":
                self.leaks.append(key)
            return
        if self.screen.kind == "notice":
            self.screen = SimpleNamespace(kind="shooting")
        elif self.kind() == "menu":
            self.menu_at, self.screen = None, SimpleNamespace(kind="shooting")     # a second MENU closes it
        elif self.menu_at is None:
            self.menu_at = self.now[0] + self.late                                  # read: still the shooting screen


def test_a_menu_that_opens_late_after_the_shooting_screens_redraw_gets_no_second_menu(monkeypatch):
    """The safety fix of 2026-11-18 (decision 21: a Left reached the shooting screen): a MENU from the shooting screen
    whose menu opens 0.3 s later, the frame read after the press still showing the shooting screen, gets no second MENU
    and no other key, through the one helper (camkit.live.menu_from_shooting) wherever a MENU goes from the shooting
    screen: runner's, proving.nav.to_row's and camkit.crawl.back_to's (whose first MENU closes a notice)."""
    import runner
    from camkit import crawl, live
    from proving import nav
    now, clock = menu_clock()
    for mod in (runner, live, nav):
        monkeypatch.setattr(mod, "time", clock)
    cam = LateMenuCamera(now, 0.3)
    runner.menu_from_shooting(cam)
    assert [k for k, t in cam.pressed] == ["menu"] and cam.read().kind == "menu" and not cam.leaks
    now[0] = 0.0
    cam = LateMenuCamera(now, 0.3, closes_first=True)
    monkeypatch.setattr(crawl, "same_state", lambda a, b: a.kind == b.kind)
    place = SimpleNamespace(screen=SimpleNamespace(kind="menu"), parent=None, index=0)
    assert crawl.back_to(cam, place) is True
    assert [k for k, t in cam.pressed] == ["menu", "menu"] and not cam.leaks
    now[0] = 0.0
    cam = LateMenuCamera(now, 0.3)
    cam.press("menu")                               # after_download's MENU, then to_row
    monkeypatch.setattr(nav, "place", lambda cam: "here")
    monkeypatch.setattr(nav, "same_place", lambda a, b: a == b)
    nav.to_row(cam, ["Shooting"], None, "here")
    assert [k for k, t in cam.pressed] == ["menu"] and not cam.leaks


class StaleEyes:
    """HDMI eyes whose every grab is a fresh frame showing `shown` (a kind); settle records the frame it was given
    (the press's reference) and ends on a frame of the press's result (kind "after")."""
    name = "hdmi"

    def __init__(self, shown):
        self.shown, self.grabs, self.settled_from, self.timing = shown, [], [], {}

    def grab(self, tag, save=True, shown=None):
        self.grabs.append(tag)
        import time
        return SimpleNamespace(image=None, t=time.monotonic(), path=Path(f"{len(self.grabs):05d}_{tag}.png"),
                               shown=shown or self.shown)

    def settle(self, before, tag, expect_change=None, sent_at=None, **k):
        self.settled_from.append(before)
        return self.grab(tag, shown="after"), True


def stale_camera(tmp_path, held, shown, age):
    """A LiveCamera whose frame, `age` s old, read as `held`, while the camera now shows `shown`; its link records the
    screen each press was judged on."""
    import time
    from camkit import live
    from camkit.runs import Run
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("stale", root=tmp_path)
    cam.hdmi = StaleEyes(shown)
    cam.frame = SimpleNamespace(image=None, t=time.monotonic() - age, path=tmp_path / "00000_old.png", shown=held)
    cam.reading = lambda f: SimpleNamespace(kind=f.shown, focus="rows", signature=f.path.name)
    cam.screen = cam.reading(cam.frame)
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open, cam.presses, cam._seen = frozenset(), 0, 0
    judged = []
    cam.link = SimpleNamespace(moves=0, menus=0,
                               press=lambda key, hold, screen=None, **k: judged.append((key, screen.kind)),
                               dial=lambda name, steps, screen=None, **k: judged.append((name, screen.kind)))
    return cam, judged


def test_a_press_is_judged_and_measured_on_a_frame_no_older_than_stale_s(tmp_path, monkeypatch):
    """Decision 21's safety fix of 2026-11-18: a frame older than live.STALE_S is looked at afresh before a press is
    judged and sent, so the screen the guards judge is the one on show (a menu read 4.7 s before that a MENU had since
    closed is the shooting screen now, where the link lets no unnamed key out) and settle's "moved" is measured from
    just before the press; a dial alike. A frame younger than that takes no extra grab (a press's normal path)."""
    import json
    from camkit import live
    monkeypatch.setattr(live.time, "sleep", lambda s: None)
    cam, judged = stale_camera(tmp_path, "menu", "shooting", 4.7)
    cam.press("left")
    assert judged == [("left", "shooting")] and cam.hdmi.grabs[0] == "fresh"
    assert cam.hdmi.settled_from[0].path.name.endswith("_fresh.png")
    assert any(e["kind"] == "frame_stale" for e in map(json.loads, (cam.run.dir / "events.jsonl").read_text(
        encoding="utf-8").splitlines()))
    cam, judged = stale_camera(tmp_path, "menu", "shooting", live.STALE_S / 4)
    cam.press("left")
    assert judged == [("left", "menu")] and "fresh" not in cam.hdmi.grabs
    cam, judged = stale_camera(tmp_path, "menu", "shooting", 2.0)
    cam.dial("front", 1)
    assert judged == [("front", "shooting")] and cam.hdmi.grabs[0] == "fresh"
    assert 0.2 <= live.STALE_S <= 1.0


def test_no_menu_goes_from_the_shooting_screen_without_a_fresh_look_before_it():
    """A source check, so the blind pattern does not come back: a MENU pressed where the lines just above judged the
    screen as the shooting screen, with no fresh look among them (a refresh, a watched check, the helper), as
    kit/prove_run.py's start did (a sleep, then MENU again: it closed a menu that had opened late, 2026-11-18)."""
    import ast
    import re
    check = re.compile(r"""kind\s*==\s*["']shooting["']|kind\s+in\s+\(["']shooting["']|shooting_like\(""")
    look = re.compile(r"refresh\(|menu_check\(|glance\(|menu_from_shooting\(|wait_for\(|screen\.read\(")
    menu = re.compile(r"""press\(\s*["']menu["']""")
    helper = next(n for n in ast.walk(ast.parse((KIT / "camkit" / "live.py").read_text(encoding="utf-8")))
                  if isinstance(n, ast.FunctionDef) and n.name == "menu_from_shooting")
    found = []
    for p in sorted(KIT.rglob("*.py")):
        if "tests" in p.parts:
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines):
            if p == KIT / "camkit" / "live.py" and helper.lineno <= i + 1 <= helper.end_lineno:
                continue                            # the one helper itself
            window = lines[max(0, i - 6):i]
            if menu.search(ln) and any(check.search(w) for w in window) and not any(look.search(w) for w in window):
                found.append(f"{p.relative_to(KIT)}:{i + 1}")
    assert found == [], f"a MENU after a shooting check with no fresh look: {found} (camkit.live.menu_from_shooting)"


class WatchFrame:
    """A frame of the fake camera below, grabbed at `t` on its fake clock; saved by name alone."""
    def __init__(self, kind, t, n):
        self.kind, self.t, self.image, self.path = kind, t, None, Path(f"{n:05d}_{kind}.png")

    def save(self, path, black=False):
        self.path = Path(path)
        return self.path


class WatchEyes:
    """Eyes on a fake clock: the shooting screen until `menu_at`, a menu page from then; a settle takes 0.2 s and ends on
    the shooting screen's own redraw while the menu is not drawn yet (kit2_pass2 250525-250527, 2026-11-18)."""
    def __init__(self, now, name):
        self.now, self.name, self.menu_at, self.grabs, self.timing = now, name, None, [], {}

    def grab(self, tag, save=True):
        self.grabs.append(tag)
        shown = "menu" if self.menu_at is not None and self.now[0] >= self.menu_at else "shooting"
        return WatchFrame(shown, self.now[0], len(self.grabs))

    def settle(self, before, tag, expect_change=None, sent_at=None, **k):
        self.now[0] += 0.2
        return self.grab(tag), True


def watch_camera(tmp_path, monkeypatch, name="hdmi", late=0.8):
    """A LiveCamera on the shooting screen and a fake clock whose MENU there opens the menu `late` s after it (None:
    never); its link records each press as (key, the screen judged, when)."""
    from camkit import live
    from camkit.runs import Run
    now, clock = menu_clock()
    monkeypatch.setattr(live, "time", clock)
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run(f"watch_{name}_{late}", root=tmp_path)
    cam.hdmi = eyes = WatchEyes(now, name)
    cam.reading = lambda f: SimpleNamespace(kind=f.kind, focus="rows", signature=f.path.name, struct=f.path.name)
    cam.frame = eyes.grab("start")
    cam.screen = cam.reading(cam.frame)
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open, cam.presses, cam._seen = frozenset(), 0, 0
    sent = []

    def press(key, hold, screen=None, **k):
        sent.append((key, screen.kind, round(now[0], 2)))
        if key == "menu" and screen.kind == "shooting" and late is not None:
            eyes.menu_at = now[0] + late

    cam.link = SimpleNamespace(moves=0, menus=0, press=press)
    return cam, sent, now, clock


def events_of(cam, kind):
    import json
    return [e for e in map(json.loads, (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines())
            if e["kind"] == kind]


def test_a_menu_from_the_shooting_screen_takes_its_result_from_the_menu_page_its_press_watched_for(tmp_path,
                                                                                                    monkeypatch):
    """With HDMI eyes, a MENU judged on the shooting screen whose settle ended on the shooting screen's own redraw is
    watched until a menu page shows (0.8 s here), up to MENU_LATE s from the press, and takes its result from it; the
    one helper then looks no more and sends no second MENU. The log tells which look saw the menu (menu_watch)."""
    from camkit import live
    cam, sent, now, clock = watch_camera(tmp_path, monkeypatch, late=0.8)
    cam.press("menu")
    assert cam.read().kind == "menu" and now[0] == pytest.approx(0.8, abs=0.06)
    assert cam.frame.path.parent == cam.run.dir / "shots"          # the frame the press ends on is saved evidence
    [watch] = events_of(cam, "menu_watch")
    assert watch["seen"] is True and watch["after"] == pytest.approx(0.8, abs=0.06)
    live.menu_from_shooting(cam, pressed=True, clock=clock)
    assert sent == [("menu", "shooting", 0.0)] and now[0] == pytest.approx(0.8, abs=0.06)


def test_a_menu_its_press_watched_for_in_vain_gets_its_second_menu_with_no_second_wait(tmp_path, monkeypatch):
    """A MENU the camera does not take: its press watches up to MENU_LATE s from the press and logs that it saw no
    menu; the helper's own look then returns at once (logged as the press's watch, menu_check by "press"), so the
    second MENU goes MENU_LATE s after the first, not twice that."""
    from camkit import live
    cam, sent, now, clock = watch_camera(tmp_path, monkeypatch, late=None)
    cam.press("menu")
    assert cam.read().kind == "shooting" and now[0] == pytest.approx(live.MENU_LATE, abs=0.06)
    assert [w["seen"] for w in events_of(cam, "menu_watch")] == [False]
    live.menu_from_shooting(cam, pressed=True, clock=clock, tries=1)
    assert [(k, s) for k, s, t in sent] == [("menu", "shooting")] * 2
    assert sent[1][2] == pytest.approx(live.MENU_LATE, abs=0.06)
    [check] = events_of(cam, "menu_check")
    assert check["by"] == "press" and check["seen"] is False and check["waited"] == 0


def test_osd_eyes_keep_the_helpers_own_look_and_the_press_watches_nothing(tmp_path, monkeypatch):
    """OSD eyes, unchanged: the press ends on its settle, nothing watched; the helper's own look waits MENU_LATE s and
    takes a fresh frame, and the log says the menu was seen by that look (menu_check by "look")."""
    from camkit import live
    cam, sent, now, clock = watch_camera(tmp_path, monkeypatch, name="osd", late=0.8)
    cam.press("menu")
    assert cam.read().kind == "shooting" and "menu-watch" not in cam.hdmi.grabs and not events_of(cam, "menu_watch")
    live.menu_from_shooting(cam, pressed=True, clock=clock)
    assert cam.read().kind == "menu" and len(sent) == 1
    [check] = events_of(cam, "menu_check")
    assert check["by"] == "look" and check["seen"] is True and check["waited"] == pytest.approx(live.MENU_LATE)


def test_a_menu_judged_on_a_menu_page_is_not_watched(tmp_path, monkeypatch):
    """Only a MENU judged on the shooting screen is watched: one that closes a menu page ends on its settle."""
    cam, sent, now, clock = watch_camera(tmp_path, monkeypatch, late=0.8)
    cam.hdmi.menu_at = 0.0
    cam.refresh("start")
    cam.hdmi.menu_at = None
    cam.press("menu")
    assert cam.read().kind == "shooting" and now[0] == pytest.approx(0.2) and not events_of(cam, "menu_watch")


class ReaderEyes:
    """HDMI eyes on a fake clock over a menu page whose lit row (`row`) OCR reads nothing in; `shown` the screen's kind
    (the menu has closed when it reads "shooting"). A frame's picture is (kind, lit row)."""
    name = "hdmi"

    def __init__(self, now):
        self.now, self.shown, self.row, self.grabs, self.settled_from, self.timing = now, "menu", 2, [], [], {}

    def grab(self, tag, save=True):
        self.grabs.append(tag)
        f = WatchFrame(self.shown, self.now[0], len(self.grabs))
        f.image = (self.shown, self.row)
        return f

    def settle(self, before, tag, expect_change=None, sent_at=None, **k):
        self.settled_from.append(before)
        self.now[0] += 0.2
        return self.grab(tag), True


def reader_camera(tmp_path, monkeypatch, takes, closes=False, moves_to=None, by_row=True, steps=False):
    """A LiveCamera on a fake clock, on a menu page whose lit row OCR reads nothing in, so Right asks the reader for
    its label; the fake reader takes `takes` s (one per question, the last for any more), and while it reads the menu
    closes (`closes`) or the cursor moves to row `moves_to` (with `steps`, down a row at every question). by_row: the screen's reading tells lit rows apart (as
    camkit.screen's structure does); otherwise only the lit row's box does. (camera, presses sent, labels judged by
    open_refused, frames the reader was asked about, the clock's now); cam.guarded, the keys the first guard
    (inside_refused) judged."""
    from camkit import live
    from camkit.runs import Run
    now, clock = menu_clock()
    now[0] = 10.0                           # a frame's time is a monotonic clock's, never 0
    monkeypatch.setattr(live, "time", clock)
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run(f"reader_{len(list(tmp_path.iterdir()))}", root=tmp_path)
    cam.hdmi = eyes = ReaderEyes(now)
    cam.reading = lambda f: SimpleNamespace(kind=f.image[0], focus="rows", signature=str(f.image if by_row else f.image[0]),
                                            struct=f.image if by_row else f.image[0])
    cam.frame = eyes.grab("start")
    cam.screen = cam.reading(cam.frame)
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open, cam.presses, cam._seen = frozenset(), 0, 0
    monkeypatch.setattr(live, "lit_text", lambda image, path: "")
    monkeypatch.setattr(live, "lit_box", lambda image, kind=None: (8, 40 + 32 * image[1], 600, 70 + 32 * image[1])
                        if image[0] == "menu" else None)
    sent, judged, asked, waits = [], [], [], list(takes) if isinstance(takes, list) else [takes]

    def reader(path, timeout=live.READER_TIMEOUT):
        asked.append(Path(path).name)
        now[0] += waits.pop(0) if len(waits) > 1 else waits[0]
        if closes:
            eyes.shown = "shooting"
        if moves_to is not None:
            eyes.row = moves_to
        if steps:
            eyes.row += 1
        return "Grid Line", ""

    real = live.open_refused

    def counted(lit, *a, **k):
        judged.append(lit)
        return real(lit, *a, **k)

    monkeypatch.setattr(live, "reader_label", reader)
    monkeypatch.setattr(live, "open_refused", counted)
    cam.guarded, inside = [], cam.inside_refused
    cam.inside_refused = lambda key, permit=None: (cam.guarded.append(key), inside(key, permit))[1]
    cam.link = SimpleNamespace(moves=0, menus=0, press=lambda key, hold, screen=None, **k: sent.append(
        (key, screen.kind, round(now[0], 2))))
    return cam, sent, judged, asked, now


def test_a_menu_that_closes_while_the_reader_names_its_lit_row_gets_no_right(tmp_path, monkeypatch):
    """Inside a press, the reader names the lit row OCR read nothing in (about a second): where the frame it read is by
    then older than STALE_S the screen is looked at again, and a menu that closed meanwhile refuses the press as a
    changed screen (safety.ScreenChanged): no key goes out on the shooting screen, and the fresh frame is the camera's."""
    from camkit import safety
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, 1.0, closes=True)
    with pytest.raises(safety.ScreenChanged):
        cam.press("right")
    assert sent == [] and len(asked) == 1 and judged == [] and cam.read().kind == "shooting"
    assert events_of(cam, "screen_changed_before_press") and events_of(cam, "press_refused")


def test_a_press_whose_reader_took_long_is_judged_again_on_a_fresh_frame_without_asking_again(tmp_path, monkeypatch):
    """The same screen after the reader's second: the press is judged again from the top on a fresh frame (every guard
    again, the never-open check on the fresh frame), the reader not asked again for the same lit row, and the press
    measured from that fresh frame. A reader that answers within STALE_S changes nothing; a lit row that moved while it read gets its own
    question, or the press is refused where the screen's reading tells the rows apart."""
    from camkit import live, safety
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, 1.0)
    cam.press("right")
    assert len(asked) == 1 and cam.guarded == ["right", "right"] and judged == ["Grid Line"]
    assert sent == [("right", "menu", 11.0)] and events_of(cam, "lit_row_label_kept")
    assert "right-judged" in cam.hdmi.settled_from[0].path.name and events_of(cam, "press_judged_again")
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, live.STALE_S / 5)
    cam.press("right")
    assert len(asked) == 1 and cam.guarded == ["right"] and judged == ["Grid Line"] and len(sent) == 1
    assert not events_of(cam, "press_judged_again")
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, 1.0, moves_to=3)
    with pytest.raises(safety.ScreenChanged):
        cam.press("right")
    assert sent == [] and len(asked) == 1
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, [1.0, 0.1], moves_to=3, by_row=False)
    cam.press("right")
    assert len(asked) == 2 and cam.guarded == ["right", "right"] and judged == ["Grid Line"] and len(sent) == 1
    # a lit row that moves at every slow question: judged at most 1 + REJUDGES times, then refused, nothing sent
    cam, sent, judged, asked, now = reader_camera(tmp_path, monkeypatch, 1.0, by_row=False, steps=True)
    with pytest.raises(safety.ScreenChanged):
        cam.press("right")
    assert sent == [] and judged == [] and len(asked) == len(cam.guarded) == 1 + live.REJUDGES


# ---------------------------------------------------------------- a carousel's title, read once its strip is still


def title_feed(monkeypatch, changes_at=(), blink=False):
    """camkit.frames.HdmiSource with a made-up feed on a fake clock, 30 frames a second: the title strip (TITLE_BOX)
    drawn anew at each time of `changes_at`, otherwise still; with `blink`, a block inside the strip that changes on
    every frame, as a blinking readout does, also before the wait; (the eyes, the clock's now, the prior image)."""
    from camkit import frames
    from camkit.frames import Frame
    now = [0.0]
    monkeypatch.setattr(frames.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(frames.time, "sleep", lambda s: now.__setitem__(0, now[0] + max(s, 1 / 30)))
    eyes = frames.HdmiSource.__new__(frames.HdmiSource)

    def picture(t):
        img = np.zeros((480, 640, 3), np.uint8)
        n = sum(1 for c in changes_at if t >= c)          # how many redraws have happened by t
        img[64:108, 120:600] = 40 + 30 * (n % 6)           # the title strip's text, a different grey per redraw
        if blink and int(t * 30) % 2:
            img[64:72, 128:136] = 250                      # one block that blinks
        return img

    def latest():
        t = round(now[0] * 30) / 30
        img = picture(t)
        return Frame(img, t, None, "hdmi", frames._small(img))
    eyes.latest = latest
    eyes.noisy = lambda until, level=6.0: (np.zeros((60, 80), bool) if not blink else
                                           np.pad(np.ones((1, 1), bool), ((8, 51), (16, 63))))
    eyes.grab = lambda tag="f", save=True: latest()
    return eyes, now, picture(-1.0)


@pytest.mark.parametrize("changes_at,ends,changed", [
    ((0.3,), 0.45, True),               # the title redraws 0.3 s after the press settled: read 0.15 s after that
    ((0.0,), 0.15, True),               # already redrawn: read once it has been still 0.15 s
    (tuple(0.2 + k / 30 for k in range(55)), 2.15, True),     # still changing frame by frame until 2 s
    ((), 3.5, False)])                  # never redrawn from the frame the press was made on: read at the deadline
def test_the_title_strip_is_read_once_it_has_changed_from_the_pressed_frame_and_stopped(monkeypatch, changes_at,
                                                                                        ends, changed):
    """HdmiSource.settle_box over the title strip with the frame the press was made on: the wait ends once the strip
    differs from that frame and has been still TITLE_QUIET s, never before it changes; at the deadline (TITLE_LATE,
    3.5 s) where it never does."""
    from proving import screens
    eyes, now, prior = title_feed(monkeypatch, changes_at)
    f, moved = eyes.settle_box(screens.TITLE_BOX, prior, quiet=screens.TITLE_QUIET, timeout=screens.TITLE_LATE)
    assert moved == changed and now[0] == pytest.approx(ends, abs=0.07)
    assert now[0] >= (max(changes_at) if changes_at else screens.TITLE_LATE) - 1e-9


def test_a_block_that_blinks_by_itself_in_the_strip_is_ignored(monkeypatch):
    """A block of the strip that changed by itself before the wait (HdmiSource.noisy) is left out, as settle leaves it
    out: the strip, redrawn at 0.3 s, is read 0.15 s later, not at the deadline."""
    from proving import screens
    eyes, now, prior = title_feed(monkeypatch, (0.3,), blink=True)
    f, moved = eyes.settle_box(screens.TITLE_BOX, prior, quiet=screens.TITLE_QUIET, timeout=screens.TITLE_LATE)
    assert moved and now[0] == pytest.approx(0.45, abs=0.07)


class TitleCam:
    """A camera on a carousel for proving.screens.title_settled: HDMI or OSD eyes whose settle_box is recorded, the
    frame the last press was made on (a carousel frame, or the menu page it was opened from)."""
    def __init__(self, name="hdmi", opened=False):
        self.calls, self.refreshed = [], []
        self.hdmi = SimpleNamespace(name=name, settle_box=self.settle_box)
        self.frame = SimpleNamespace(image="after", kind="dialog")
        self.pressed_from = SimpleNamespace(image="before", kind="menu" if opened else "dialog")

    def settle_box(self, box, prior, quiet, timeout):
        self.calls.append((prior, quiet, timeout))
        return SimpleNamespace(image="settled", kind="dialog"), True

    def read(self):
        return SimpleNamespace(kind=self.frame.kind)

    def refresh(self, tag, frame=None):
        self.refreshed.append(frame)
        self.frame = frame if frame is not None else SimpleNamespace(image="fresh", kind="dialog")
        return self.read()


def test_the_title_wait_watches_over_hdmi_and_reads_the_same_frame_once(monkeypatch):
    """proving.screens.title_settled: over HDMI, after a step within the carousel, the strip must change from the
    pressed frame and be still TITLE_QUIET s; just opened, still TITLE_OPEN_QUIET s (0.4, today's wait) with nothing to
    change from; a second call with no press or grab between takes the same frame, nothing waited. OSD eyes: 0.4 s and
    a fresh grab every time, as before."""
    from proving import screens
    monkeypatch.setattr(screens.screen, "read", lambda f: SimpleNamespace(kind=f.kind))
    cam = TitleCam()
    assert screens.title_settled(cam) is False and cam.calls == [("before", screens.TITLE_QUIET, screens.TITLE_LATE)]
    assert cam.frame.image == "settled" and screens.title_settled(cam) is True and len(cam.calls) == 1
    cam = TitleCam(opened=True)
    screens.title_settled(cam)
    assert cam.calls == [(None, screens.TITLE_OPEN_QUIET, screens.TITLE_LATE)]
    slept = []
    monkeypatch.setattr(screens.time, "sleep", slept.append)
    cam = TitleCam(name="osd")
    assert screens.title_settled(cam) is False and screens.title_settled(cam) is False
    assert slept == [0.4, 0.4] and cam.calls == [] and cam.refreshed == [None, None]


def test_a_second_reading_of_the_same_carousel_frame_is_the_first_ones(monkeypatch):
    """option_index (a carousel's option by its title) and prove_run.axis_title over HDMI: read again with no press
    between, they take the first reading, no wait, no OCR or reader asked again; after a press, read afresh."""
    import prove_run
    from proving import options, screens
    monkeypatch.setattr(screens.screen, "read", lambda f: SimpleNamespace(kind=f.kind))
    read = []
    monkeypatch.setattr(options, "carousel_text", lambda cam: read.append(cam.frame.image) or "Auto")
    monkeypatch.setattr(prove_run, "carousel_text", lambda cam: read.append(cam.frame.image) or "Auto")
    cam = TitleCam()
    assert options.option_index(cam, ["Auto", "Manual"], "dialog") == 0
    assert options.option_index(cam, ["Auto", "Manual"], "dialog") == 0
    assert len(cam.calls) == 1 and read == ["settled"]
    cam.pressed_from, cam.frame = cam.frame, SimpleNamespace(image="next", kind="dialog")     # a press went out
    assert options.option_index(cam, ["Auto", "Manual"], "dialog") == 0 and len(cam.calls) == 2
    read.clear()
    cam.frame = SimpleNamespace(image="again", kind="dialog")
    prove_run.axis_title(cam)
    prove_run.axis_title(cam)
    assert len(cam.calls) == 3 and len(read) == 2, "the OCR of the same frame is OCR's own cache; no second wait"


class CarouselCam(TitleCam):
    """TitleCam on a menu page whose Right opens a carousel (and Right in the carousel its panel, a submenu), each press
    making a new frame and remembering the one it was made on."""
    def __init__(self, name="hdmi"):
        super().__init__(name)
        self.frame, self.kind_now, self.pressed = SimpleNamespace(image="menu", kind="menu"), "menu", []

    def read(self):
        return SimpleNamespace(kind=self.kind_now)

    def press(self, key, **kw):
        self.pressed.append(key)
        self.pressed_from = self.frame
        if key == "right":
            self.kind_now = "dialog" if self.kind_now == "menu" else "submenu"
        self.frame = SimpleNamespace(image=f"after {len(self.pressed)}", kind=self.kind_now)


@pytest.mark.parametrize("name", ["hdmi", "osd"])
def test_the_carousel_readings_left_wait_for_the_title_strip_as_option_index_does(monkeypatch, name):
    """The review's 13 left three carousel readings sleeping a fixed 0.4 s and grabbing again: axis_walk's title, the
    Picture Profile carousel's walk (proving.nav.enter_pp) and Creative Look's icon (proving.options.icon_index; the
    side strip it reads redraws before the title). Each goes through proving.screens.title_settled, as option_index and
    prove_run.axis_title do: over HDMI the title strip watched, no fixed sleep; over OSD 0.4 s and a fresh grab, as
    before."""
    import axis_walk
    from proving import nav, options, screens
    monkeypatch.setattr(screens.screen, "read", lambda f: SimpleNamespace(kind=f.kind))
    monkeypatch.setattr(screens, "_TITLED", [])
    slept = []
    monkeypatch.setattr(screens.time, "sleep", slept.append)      # one time module: every caller's sleep
    monkeypatch.setattr(axis_walk, "carousel_text", lambda cam: "Spot: L")
    cam = TitleCam(name=name)
    assert axis_walk.title(cam) == "Spot: L"
    monkeypatch.setattr(options, "_ICONS", {"Creative Look": [np.zeros(4), np.ones(4)]})
    monkeypatch.setattr(options, "icon_bits", lambda frame: np.ones(4))
    cam2 = TitleCam(name=name)
    assert options.icon_index(cam2, {"path": ["Creative Look"], "icon_frames": [], "labels": ["ST", "PT"]}, 1) == 1
    pp = CarouselCam(name=name)
    monkeypatch.setattr(nav, "at_label", lambda cam, kind, label: True)
    monkeypatch.setattr(nav, "carousel_text", lambda cam: "PP1" if "down" not in pp.pressed else "PP2")
    nav.enter_pp(pp, ["Picture Profile", "PP2"])
    assert pp.pressed == ["right", "down", "right"]
    calls = len(cam.calls) + len(cam2.calls) + len(pp.calls)
    if name == "hdmi":
        assert 0.4 not in slept and calls == 4
    else:
        assert slept.count(0.4) == 4 and calls == 0


# ---------------------------------------------------------------- I: a run's start before its link opens


def test_work_beside_the_start_is_joined_with_its_answer_or_what_it_raised():
    """camkit.budget.beside: the work runs on a thread of its own (named as its phase) while the caller goes on; join()
    gives what it returned, or raises in the caller's thread what it raised, a SystemExit among them (the readers'
    check stops a run so), and the caller's wait for it is timed."""
    import threading

    from camkit import budget
    assert budget.beside("readers check", lambda: threading.current_thread().name)() == "readers check"

    def stop():
        raise SystemExit("no reader listed")
    join = budget.beside("readers check", stop)
    with pytest.raises(SystemExit, match="no reader listed"):
        join()
    assert set(budget.taken()["phases"]) == {"readers check waited"}


def test_the_link_open_writes_what_the_start_took_before_it(tmp_path, monkeypatch):
    """The first link a run opens writes its start's budget into events.jsonl ("start_budget", right after
    "link_open"): each phase timed before it (the imports, the page scan and a note of its cache, the link's own open);
    the next link writes only what was timed since."""
    import json

    import fake_camlink
    from camkit import budget
    from camkit.link import Link
    from camkit.runs import Run
    monkeypatch.delenv("CAMSET_USB", raising=False)
    budget.main_started()
    with budget.phase("page scan"):
        pass
    budget.note("page scan", "cached")
    run = Run("started", root=tmp_path)
    for _ in range(2):
        with Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False):
            pass
    lines = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    kinds = [e["kind"] for e in lines]
    first, second = [e for e in lines if e["kind"] == "start_budget"]
    assert kinds[kinds.index("link_open") + 1] == "start_budget"
    assert set(first["phases"]) == {"imports", "page scan", "link open"} and first["notes"] == {"page scan": "cached"}
    assert all(isinstance(v, float) and v >= 0 for v in first["phases"].values())
    assert set(second["phases"]) == {"link open"} and "notes" not in second


def test_the_ledger_is_built_once_on_its_own_thread_and_the_gate_waits_for_it(tmp_path, monkeypatch):
    """camkit.coverage.warm builds the camera's ledger on a thread of its own while a run's start goes on; a gate asking
    ledger_for meanwhile waits for that build rather than making its own, and gets the same ledger."""
    import threading

    from camkit import coverage
    there = tmp_path / "there.json"
    there.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(coverage.definitions, "path", lambda camera: there)
    monkeypatch.setattr(coverage, "looks_file", lambda camera: there)
    led, calls, building, release = SimpleNamespace(stale=lambda: False), [], threading.Event(), threading.Event()

    def build(camera, **k):
        calls.append(threading.current_thread().name)
        building.set()
        assert release.wait(5)
        return led
    monkeypatch.setattr(coverage, "build", build)
    coverage.warm("TEST-CAM_fw9.99")
    assert building.wait(5)
    threading.Timer(0.2, release.set).start()
    assert coverage.ledger_for("TEST-CAM_fw9.99") is led
    assert calls == ["ledger"]


class StartEyes:
    """A run's eyes for the start-order tests: making them is noted (and lets a readers' check waiting for them go on),
    and so is closing them."""
    def __init__(self, events, made):
        self.events = events
        events.append("eyes")
        made.set()

    def attach(self, link):
        pass

    def grab(self, save=False):
        return None

    def close(self):
        self.events.append("eyes closed")


class StartLink:
    """A link for the start-order tests: opening it is noted, and its start download stops the run there."""
    class Downloaded(Exception):
        pass

    def __init__(self, events):
        self.events = events

    def __call__(self, run, **k):
        return self

    def __enter__(self):
        self.events.append("link")
        return SimpleNamespace(call=lambda *a, **k: {"ok": True, "props": []},
                               press=lambda key, **k: self.events.append(f"press {key}"), download=self.download)

    def __exit__(self, *exc):
        return False

    def download(self, tag):
        self.events.append("download")
        raise self.Downloaded()


def start_run(which, tmp_path, monkeypatch, readers, events=None, link=None, clock=None, kinds=None):
    """drive.main() or crawl_run.main() as far as its start download (with `link`, as far as that link lets it), its
    seams faked, `readers(events, made)` standing in for the readers' check, the screen reading as `kinds()` (else the
    shooting screen), the clock standing at clock[0]: (the events in order, what the run raised). A sleep is an event
    ("sleep", s), so are a press ("press menu") and the wait for the shooting screen ("wait shooting")."""
    import threading

    import crawl_run
    import drive
    from camkit import coverage
    from camkit.runs import Run
    mod = drive if which == "drive" else crawl_run
    events = [] if events is None else events
    made = threading.Event()
    link = link or StartLink(events)
    for name, value in (("load_scan", lambda *a, **k: ([], {})), ("Run", lambda name, **k: Run(name, root=tmp_path)),
                        ("check_readers", lambda: readers(events, made)),
                        ("eyes_from_config", lambda run: StartEyes(events, made)), ("Link", link),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind=kinds() if kinds else "shooting"))),
                        ("wait_for", lambda *a, **k: events.append("wait shooting")),
                        ("time", SimpleNamespace(sleep=lambda s: events.append(("sleep", s)),
                                                 monotonic=lambda: clock[0] if clock else 0.0))):
        monkeypatch.setattr(mod, name, value)
    monkeypatch.setattr(coverage, "settled", lambda *a, **k: events.append("gate") or coverage.Verdict(False, "x"))
    monkeypatch.setattr(coverage, "crawl_gate", lambda *a, **k: events.append("gate"))
    argv = ["drive.py", "--path", "Drive Mode", "--press", "down"] if which == "drive" else ["crawl_run.py"]
    monkeypatch.setattr(sys, "argv", argv)
    try:
        mod.main()
    except BaseException as e:      # noqa: BLE001 (what the run raised is the result)
        return events, e
    return events, None


@pytest.mark.parametrize("which", ["drive", "crawl"])
def test_the_readers_are_checked_beside_the_eyes_and_the_link_opens_only_after(tmp_path, monkeypatch, which):
    """drive.py's and crawl_run.py's start: the readers' check runs on a thread of its own while the eyes are made (it
    waits here until they are, which a check made in line before them never could), the link opens only once it has
    answered, and the coverage ledger's word, built meanwhile, comes once the link is open, before the start download
    (crawl_run's gate came after it, and still does: it needs the start file)."""
    import threading

    def readers(events, made):
        events.append(("readers", threading.current_thread().name, made.wait(5)))
        events.append("readers answered")
    events, raised = start_run(which, tmp_path, monkeypatch, readers)
    assert isinstance(raised, StartLink.Downloaded), raised
    assert ("readers", "readers check", True) in events
    order = [e for e in events if isinstance(e, str)]
    assert order.index("eyes") < order.index("readers answered") < order.index("link") < order.index("download")
    if which == "drive":
        assert order.index("link") < order.index("gate") < order.index("download")
    assert order[-1] == "eyes closed"


@pytest.mark.parametrize("which", ["drive", "crawl"])
def test_a_readers_check_that_stops_the_run_stops_it_before_the_link_with_the_eyes_closed(tmp_path, monkeypatch, which):
    """No reader listed (camkit.vlm.check_readers' ConfigMissing): the run stops with its words before the link opens,
    nothing pressed or downloaded, and the eyes made meanwhile are closed."""
    from camkit import ConfigMissing

    def readers(events, made):
        raise ConfigMissing("no reader is listed in private/config.json")
    events, raised = start_run(which, tmp_path, monkeypatch, readers)
    assert isinstance(raised, ConfigMissing) and "no reader is listed" in str(raised.code)
    assert "link" not in events and "download" not in events and events[-1] == "eyes closed"


def tiny_scan(tmp_path, n=3):
    """A page scan of `n` positions made from kit2_page_scan_1118p's saved frames (its model.json as it is), in the
    test's own folder; skipped where the run is not here."""
    import json
    import shutil
    src = RUNS / "kit2_page_scan_1118p"
    if not (src / "scan_rekeyed.json").exists():
        pytest.skip(f"{src} not present")
    cycle = json.loads((src / "scan_rekeyed.json").read_text(encoding="utf-8"))[:n]
    scan = tmp_path / "kit2_page_scan_tiny"
    (scan / "shots").mkdir(parents=True)
    for pos in cycle:
        shutil.copy(src / "shots" / pos["frame"], scan / "shots" / pos["frame"])
    (scan / "scan_rekeyed.json").write_text(json.dumps(cycle + cycle[:1]), encoding="utf-8")
    shutil.copy(src / "model.json", scan / "model.json")
    return scan, cycle


def same_screen(a, b) -> bool:
    """Two screens read alike, field by field (their pictures by value)."""
    return vars(a).keys() == vars(b).keys() and all(
        np.array_equal(x, y) if isinstance(x, np.ndarray) else x == y for x, y in ((vars(a)[k], vars(b)[k]) for k in vars(a)))


def test_a_page_scans_screens_are_read_once_and_kept_until_a_frame_or_the_kit_changes(tmp_path, monkeypatch):
    """runner.load_scan reads each position's saved frame with the kit's screen reader once and keeps the screens in the
    camera's cache (runs/<model>_fw<fw>/_cache/scan_reads/): the next run's cycle is the same, field by field, with
    nothing read; a frame changed, the kit's code changed, or a cache that cannot be read is read afresh."""
    import runner
    from camkit import paths
    scan, cycle = tiny_scan(tmp_path)
    real, reads = runner.screen.read, []
    monkeypatch.setattr(runner.screen, "read", lambda f: reads.append(1) or real(f))
    first, model = runner.load_scan(scan)
    assert len(reads) == len(cycle) and len(first) == len(cycle)
    again, model2 = runner.load_scan(scan)
    assert len(reads) == len(cycle) and model2 == model
    for a, b in zip(first, again, strict=True):
        assert (a["signature"], a["kind"], a["row"]) == (b["signature"], b["kind"], b["row"])
        assert same_screen(a["screen"], b["screen"])
    shots = scan / "shots"
    (shots / cycle[0]["frame"]).write_bytes((shots / cycle[1]["frame"]).read_bytes())
    changed, _ = runner.load_scan(scan)
    assert len(reads) == 2 * len(cycle) and same_screen(changed[0]["screen"], changed[1]["screen"])
    monkeypatch.setattr(runner, "kit_digest", lambda: "another kit")
    runner.load_scan(scan)
    assert len(reads) == 3 * len(cycle)
    for p in (paths.run_root() / "_cache" / runner.SCAN_READS).iterdir():
        p.write_bytes(b"not a cache")
    runner.load_scan(scan)
    assert len(reads) == 4 * len(cycle)


# ---------------------------------------------------------------- J: the lock after a download, every runner alike


# a runner left as it was: kit/tools/take_picture.py, whose waits come before the owner's one release (the lock was
# measured for MENU, not for the shutter, and a release not answered cleanly ends in RESTORE_BY_HAND)
LOCK_LEFT = ("take_picture.py",)


def test_no_runner_sleeps_a_fixed_lock_after_a_download_nor_a_bare_second_before_one():
    """Every wait for the menu's lock after a settings download is camkit.session.wait_lock (watched with HDMI eyes in a
    mode measured, LOCK_S its deadline): no runner sleeps LOCK_S, nor loops on it, any more; and no runner sleeps a
    second just before a download, which camlink's own wait covers (it asks the camera's SaveOperationEnableStatus 50
    times 100 ms apart, commit 9dca367), unless a comment on that line says what else it waits for (a mode change)."""
    import re
    files = [p for d in ("", "provers", "proving", "tools") for p in sorted((KIT / d).glob("*.py"))
             if p.name not in LOCK_LEFT]
    assert len(files) > 60
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert "time.sleep(LOCK_S)" not in text and "< LOCK_S:" not in text, p.name
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "link.download(" in line and i and re.fullmatch(r"\s*time\.sleep\((1|1\.0)\)", lines[i - 1]):
                pytest.fail(f"{p.name}:{i}: a bare second slept before a download")


def test_drive_waits_the_lock_after_its_start_download_and_no_second_after_closing_a_menu(tmp_path, monkeypatch):
    """drive.py's start: a menu page closed with one MENU, then the shooting screen waited for (camkit.session.wait_for,
    whose grace covers the menu closing: no second slept), the start download, and the menu's lock after it by
    camkit.session.wait_lock from the download's reply, not 5 s."""
    import drive
    events = []

    class Done(Exception):
        pass
    import time
    kinds = iter(["menu"])
    downloaded = []
    monkeypatch.setattr(drive, "wait_lock", lambda since, eyes, clock=None, **k: events.append(
        ("lock", downloaded[0] <= since <= clock.monotonic())) or (_ for _ in ()).throw(Done()))
    link = StartLink(events)
    link.download = lambda tag: events.append("download") or downloaded.append(time.monotonic()) or tmp_path / "b.DAT"
    _, raised = start_run("drive", tmp_path, monkeypatch, lambda events, made: None, events=events, link=link,
                          kinds=lambda: next(kinds, "shooting"))
    assert isinstance(raised, Done), raised
    order = [e for e in events if e != "eyes closed"]
    at = order.index("press menu")
    assert order[at:at + 4] == ["press menu", "wait shooting", "download", ("lock", True)]
    assert not [e for e in events if isinstance(e, tuple) and e[0] == "sleep"]
    slept = []
    monkeypatch.setattr(drive, "time", SimpleNamespace(sleep=slept.append))       # a test's stand-in, as the guards'
    drive.LOCK_CLOCK.sleep(4.5)
    assert slept == [4.5], "the lock's clock sleeps through drive's own time.sleep"


def test_memregs_download_waits_the_measured_lock(monkeypatch, tmp_path):
    """memreg_run.download: back to the shooting screen, the download at once, then the lock by wait_lock with the
    run's eyes (HDMI in Stills: over at 1.0 s, the notice gone)."""
    import memreg_run
    import prove_run
    import runner
    from camkit import session
    session_, now, clock = lock_clock(monkeypatch)
    monkeypatch.setattr(session, "MODE", "Stills")
    monkeypatch.setattr(memreg_run, "time", clock)
    monkeypatch.setattr(prove_run, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    eyes = LockEyes(now, 1.0)
    got = memreg_run.download(None, SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT"), eyes, "slot1")
    assert got.name == "slot1.DAT" and now[0] == pytest.approx(1.0, abs=0.06) and eyes.grabs >= 1


def test_mymenus_way_back_to_the_picker_waits_the_lock_by_the_one_rule(monkeypatch):
    """mymenu_run.back_to_picker: the lock after the add's download is camkit.session.wait_lock from the download's
    reply with the camera's eyes, no loop of its own on LOCK_S."""
    import mymenu_run

    class Done(Exception):
        pass
    got = []
    monkeypatch.setattr(mymenu_run, "wait_lock", lambda since, eyes, clock=None, **k: got.append((since, eyes))
                        or (_ for _ in ()).throw(Done()))
    eyes = SimpleNamespace(name="hdmi")
    with pytest.raises(Done):
        mymenu_run.back_to_picker(SimpleNamespace(hdmi=eyes), 12.5)
    assert got == [(12.5, eyes)]


@pytest.mark.parametrize("name,mode,ends", [("hdmi", "Stills", 1.0), ("osd", "Stills", 4.6), ("hdmi", "S&Q", 4.6)])
def test_afregs_wait_before_a_hold_ends_once_the_notice_has_gone(monkeypatch, name, mode, ends):
    """afreg_run.ready_to_hold (framepos_run's too): the lock by camkit.session.lock_over on what its looks see, so
    with HDMI eyes in a mode measured it ends at the first look on the shooting screen after the notice (1.0 s), with
    OSD eyes or in S&Q at the first look past LOCK_S as before; and never while the words of the download's message
    ("Saving to the connected device...") can still be read on the shooting screen."""
    import afreg_run
    from camkit import live, session
    now = [0.0]
    monkeypatch.setattr(afreg_run.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(afreg_run.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(session, "MODE", mode)
    eyes = LockEyes(now, 1.0, name=name)
    saying = {"until": 0.0}
    monkeypatch.setattr(live, "text_of", lambda cam: "Saving to the connected device..." if now[0] < saying["until"]
                        else "ISO AUTO")

    def glance(tag):
        k = eyes.kind()
        return SimpleNamespace(kind=k), SimpleNamespace(kind=k)
    cam = SimpleNamespace(hdmi=eyes, glance=glance, refresh=lambda tag, frame=None: SimpleNamespace(
        kind=frame.kind if frame is not None else eyes.kind()), frame=SimpleNamespace(path=SimpleNamespace(name="f")))
    afreg_run.ready_to_hold(cam, 0.0)
    assert now[0] == pytest.approx(ends, abs=0.11)
    if name == "hdmi" and mode == "Stills":
        now[0], saying["until"] = 0.0, 1.5             # the message's words still read on the shooting screen
        afreg_run.ready_to_hold(cam, 0.0)
        assert now[0] == pytest.approx(1.5, abs=0.11)


def test_the_waits_between_sessions_and_fills_are_the_lock_rule_or_gone():
    """customshoot_run and customshoot_values put the hold's working copy back in a session of their own: its first
    MENU waits the menu's lock from the end of the session before (wait_lock, measured from when it closed), not 4 s then
    5 s; mymenu_run's next fill starts at once (its session's start waits for the shooting screen and its own lock: the
    10 s between fills waited for nothing the kit could name)."""
    for name in ("customshoot_run.py", "customshoot_values.py"):
        text = (KIT / "provers" / name).read_text(encoding="utf-8")
        assert "time.sleep(4)" not in text and "time.sleep(5)" not in text, name
        assert "wait_lock(ended, hdmi, clock=time)" in text, name
    assert "time.sleep(10)" not in (KIT / "provers" / "mymenu_run.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- K: a lap's readings on workers


class Picker:
    """A made-up Add Item picker that comes round: settle_items' state for the lit item (its OCR text, "" where OCR
    reads nothing in it), Down to the next; each step its own frame, whose item `on` names."""
    def __init__(self, lits):
        self.lits, self.at, self.n, self.pressed, self.on = list(lits), 0, 1, [], {}
        self._frame()

    def _frame(self):
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_lap.png"))
        self.on[self.frame.path.name] = self.at

    def press(self, key, **kw):
        self.pressed.append(key)
        self.at, self.n = (self.at + 1) % len(self.lits), self.n + 1
        self._frame()

    def state(self):
        return {"kind": "items", "page": self.at // 3 + 1, "pages": 2, "lit": self.lits[self.at], "text": ""}


def test_mymenus_lap_asks_the_reader_on_workers_and_names_each_item_once_every_answer_is_in(monkeypatch):
    """mymenu_run.lap: the reader's reading of an item OCR has read only names it, so it goes out on a worker while the
    lap steps on (here every such answer waits until the lap has pressed its last Down, which a question asked in line
    could never see) and every answer is joined, in the lap's order, before any item is named: each item's "vlm" is the
    answer about its own frame and its name the one item_name gives from it. An item OCR read nothing in is keyed by
    the reader's words, so that question is asked in line. The presses are the lap's as before."""
    import threading

    import mymenu_run as M
    from proving import screens
    lits = ["Shoot Mode", "", "ISO", "Drive Mode", "Grid Line Display"]
    rows = {M.squash(x): x for x in ("Shoot Mode", "Focus Mode", "ISO", "Drive Mode", "Grid Line Display")}
    cam = Picker(lits)
    words = {0: "Shoot Mode", 1: "Focus Mode", 2: "ISO", 3: "AF/MF", 4: "Grid Line Display"}
    last_down, asked = threading.Event(), []

    def vlm_option(c):
        i = cam.on[c.frame.path.name]
        asked.append((threading.current_thread().name.startswith("lap"), i))
        if lits[i]:
            last_down.wait(5)
        return words[i] if (not lits[i] or last_down.is_set()) else "asked in line"
    monkeypatch.setattr(M, "settle_items", lambda c, why: c.state())
    monkeypatch.setattr(M, "vlm_option", vlm_option)
    monkeypatch.setattr(M, "lap_workers", lambda: 3)
    real_press = cam.press
    cam.press = lambda key, **k: real_press(key) or (len(cam.pressed) == len(lits) and last_down.set())
    items = M.lap(cam, rows, lambda m: None)
    assert cam.pressed == ["down"] * len(lits)
    assert [it["vlm"] for it in items] == [words[i] for i in range(len(lits))]
    assert [it["lit"] for it in items] == ["Shoot Mode", "Focus Mode", "ISO", "Drive Mode", "Grid Line Display"]
    assert [it["label"] for it in items] == [M.item_name(it["lit"], it["vlm"], rows)[0] for it in items]
    assert [it["frame"] for it in items] == [f"{n:05d}_lap.png" for n in range(1, len(lits) + 1)]
    assert sorted(asked) == [(False, 1)] + [(True, i) for i in (0, 2, 3, 4)]
    assert screens.lap_workers() >= 1


def test_a_cached_lap_is_taken_only_in_the_mode_and_scan_it_was_made_with(tmp_path):
    """mymenu_run's cached lap (mymenu_items.json) keeps the mode and the page scan it was made with: taken in that
    mode with that scan; a lap of another mode or scan, or one kept before it said either, is made again, said in one
    line, never taken (a Movie lap taken in Stills failed a whole lap later, 2026-11-19)."""
    import mymenu_run as M
    from runner import write_json
    kept, said = tmp_path / "mymenu_items.json", []
    items = [{"page": 1, "lit": "ISO", "label": "ISO"}]
    write_json(kept, M.lap_kept(items, "Movie", "kit2_page_scan_movie_1108"), indent=1)
    assert M.kept_lap(kept, "Movie", "kit2_page_scan_movie_1108", said.append) == items and not said
    assert M.kept_lap(kept, "Stills", "kit2_page_scan_movie_1108", said.append) is None
    assert M.kept_lap(kept, "Movie", "kit2_page_scan_1118p", said.append) is None
    write_json(kept, items, indent=1)                   # kept before it said its mode and scan
    assert M.kept_lap(kept, "Stills", "kit2_page_scan_1118p", said.append) is None
    assert M.kept_lap(tmp_path / "none.json", "Stills", "x", said.append) is None
    assert len(said) == 3 and all(s.count("\n") == 0 and "lapped again" in s for s in said)
    assert "made in Movie mode with kit2_page_scan_movie_1108" in said[0] and "this run's Stills" in said[0]
