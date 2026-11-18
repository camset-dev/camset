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
    """proving.base.lock_left (crawl_run's wait after its start download): what is left of LOCK_S since the download
    returned, so a crawl whose ledger build took longer than the lock waits nothing more, one that took a second waits
    the rest; never less than the lock in all."""
    from proving import base
    now, slept = [100.0 + 10.9], []                 # the ledger built in 10.9 s
    clock = SimpleNamespace(monotonic=lambda: now[0], sleep=lambda s: slept.append(s) or now.__setitem__(0, now[0] + s))
    base.lock_left(100.0, clock)
    now[0] = 200.0 + 1.0
    base.lock_left(200.0, clock)
    assert slept == [pytest.approx(base.LOCK_S - 1.0)] and now[0] == pytest.approx(200.0 + base.LOCK_S)


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
    assert seq == ["shooting", "download", ("sleep", boxes_run.LOCK_S)]
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
