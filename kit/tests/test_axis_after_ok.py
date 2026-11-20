"""The axis job on a row whose screen blanks HDMI and answers OK with an information screen: the a1 II's Framing
Stabilizer in Movie mode (2026-11-19), a carousel of Off and On whose On option has a second axis, On: Center and
On: Manual. Its list job passed; its axis job failed twice for the kit's own reasons, the camera restored each time:
  - with --eyes osd the axis job read its title off the HDMI picture, which the row's preview blanks whenever On is lit
    (kit2_pass2 264795-264892: a black frame, the camera's own picture saying "dialog"), where the list job of the same
    row read the camera's own picture: proving.jobs gave the list job {"eyes": "osd"}, a row of the reviewed scope's OSD
    group, and the axis job nothing;
  - through the camera's own picture (--eyes osd-all), OK on On: Manual brought up an information screen, its "Don't
    show this again." box lit over its OK (264911_enter.png), which the list job passes (proving.commit.after_ok's
    info-ok: proving.screens.info_notice_ok, the cursor taken off the box by Down, then MENU) and the axis job, which
    gave after_ok info=False, failed on.
Fake cameras, and the run's own frames where this clone has them (skipped without them or an OCR engine). An Enter on
the lit box ticks it, which no settings file puts back: every test here that reaches the screen fails on one. Nothing
here reaches a camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))

from camkit import ocr, paths, screen  # noqa: E402

ROW, OPTION, JOB_KEY = "Framing Stabilizer", "On", "Framing Stabilizer / On"
VALUES = ["On: Center", "On: Manual"]                   # the axis walk's, in Right order (kit2_axes/axes.json)
OPTION_KEY, AXIS_KEY = "global:0x116a", "global:0x1188"  # On 0, Off 1; Center 0, Manual 1 (the runs' own diffs)
# the fake camera's information screen after OK on On, its lines made up (the run's own frames are read below), then its
# box and its OK as the camera draws them (264911_enter.png)
INFO = ["What the option just chosen", "does, in a few lines."]
BOX, OK = "Don't show this again.", "OK"
OSD_GROUP = "could take the menus off HDMI or blank a screen"
DRIVE = "Drive Mode / Self-timer(Cont.)"


def axis_job(**more) -> dict:
    return {"path": [ROW], "kind": "axis", "option": OPTION, "values": list(VALUES), **more}


class Dat:
    """A download: its name and the records it holds, for a made-up camset.read and camset.diff."""

    def __init__(self, name, values):
        self.name, self.values = name, values


class Lines(list):
    """A proofs or failures file: each line written, as JSON."""

    def write(self, line):
        self.append(json.loads(line))

    def flush(self):
        pass


class FramingStabilizer:
    """The a1 II's Framing Stabilizer row in Movie mode, as the axis job meets it. Right on the row opens the carousel on
    the saved option, Down and Up move between Off and On, Right and Left on On step its axis (it wraps, and keeps the
    value it is left on), and OK commits the option and the axis value. OK on On brings up the information screen (no
    notice's frame lines: no known kind) with its "Don't show this again." box lit over its OK: Down lights the OK, Up
    the box; Enter on the lit box ticks it (`ticked`, `enter_on_box`), Enter on the lit OK or MENU leaves it for the
    row. The frames come from the eyes the run gives it (`hdmi`, named "hdmi" or "osd"): over HDMI the carousel with On
    lit is a black frame of no known kind, its title nothing. The records: global:0x116a the option (On 0, Off 1),
    global:0x1188 the axis value committed last (Center 0, Manual 1) or, `sticky`, 1 from the first OK on On: Manual on
    (a flag that stays, as an old note calls it). Every key is kept, and each frame's eyes and screen (`seen`)."""

    def __init__(self, saved="Off", held=0, sticky=False, eyes="osd"):
        self.saved, self.held, self.sticky, self.manual_seen = saved, held, sticky, False
        self.where, self.opt, self.value, self.lit_line, self.ticked = "menu", saved, held, BOX, False
        self.hdmi = SimpleNamespace(name=eyes)
        self.keys, self.enter_on_box, self.seen, self.texts, self.n = [], [], [], {}, 0
        self.frame = None
        self._show("start")

    @property
    def eyes(self) -> str:
        return getattr(self.hdmi, "name", "hdmi")

    @property
    def blank(self) -> bool:
        """The row's preview has blanked HDMI: the carousel with On lit, seen over HDMI."""
        return self.where == "dialog" and self.opt == "On" and self.eyes == "hdmi"

    def _show(self, tag):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{tag}.png"), image=np.zeros((480, 640, 3), np.uint8))
        self.seen.append((self.eyes, self.where, self.opt if self.where == "dialog" else None))
        if self.where == "info":
            self.texts[self.frame.path] = INFO + [BOX, OK]

    def press(self, key, **kw):
        self.keys.append(key)
        if self.where == "menu" and key == "right":
            self.where, self.opt, self.value = "dialog", self.saved, self.held
        elif self.where == "dialog":
            if key in ("down", "up"):
                self.opt = "On" if self.opt == "Off" else "Off"
            elif key in ("right", "left") and self.opt == "On":
                self.value = (self.value + (1 if key == "right" else -1)) % len(VALUES)
            elif key == "enter":
                self.saved, self.held = self.opt, self.value
                self.manual_seen |= self.opt == "On" and self.value == 1
                self.where, self.lit_line = ("info" if self.opt == "On" else "menu"), BOX
            elif key == "menu":
                self.where = "menu"
        elif self.where == "info":
            if key == "down":
                self.lit_line = OK
            elif key == "up":
                self.lit_line = BOX
            elif key == "enter" and self.lit_line == BOX:
                self.ticked = not self.ticked
                self.enter_on_box.append(self.frame.path.name)
            elif key in ("enter", "menu"):
                self.where = "menu"
        self._show(key)

    def read(self):
        if self.where == "menu":
            return screen.Screen(kind="menu", focus="rows", row=3)
        return screen.Screen(kind="unknown" if self.where == "info" or self.blank else "dialog")

    def title(self) -> str:
        """The carousel's title line as OCR reads it: nothing on a blank frame."""
        if self.where != "dialog" or self.blank:
            return ""
        return VALUES[self.value] if self.opt == "On" else "Off"

    def lines(self, path) -> list:
        return [ocr.Line(text=t, conf=0.9, x=40, y=60 + 50 * i, w=560, h=34)
                for i, t in enumerate(self.texts.get(Path(path), []))]

    def lit(self) -> str:
        """The information screen's lit line (proving.screens.notice_lit), "" off it."""
        return self.lit_line if self.where == "info" else ""

    def records(self) -> dict:
        axis = (1 if self.manual_seen else 0) if self.sticky else self.held
        return {OPTION_KEY: 0 if self.saved == "On" else 1, AXIS_KEY: axis}

    def refresh(self, tag, frame=None):
        self._show(tag)
        return self.read()

    def cancel_to_menu(self):
        self.where = "menu"
        return True


def proof_seams(monkeypatch, cam, title=None):
    """prove_run's axis job over `cam`, its seams faked as the axis tests fake them: the title read as `title(cam)` (the
    camera's own by default), no vision model, the way back to the row and the wait after a download the camera's own,
    each download the camera's records now. The fake camera's OCR and lit line are given unless `title` reads the
    frames (the run's own). Returns (prove_run, the link, its downloads)."""
    import prove_run as P
    from proving import screens
    downloads = []

    def download(name):
        dat = Dat(f"{len(downloads) + 2:05d}_{name}.DAT", cam.records())
        downloads.append(dat)
        return dat

    def diff(a, b):
        return [SimpleNamespace(key=k, before=a[k], after=b[k]) for k in a if a[k] != b[k]]
    monkeypatch.setattr(P, "axis_title", title or (lambda c: c.title()))
    monkeypatch.setattr(P, "vlm_option", lambda c: "")
    monkeypatch.setattr(P, "to_row", lambda *a, **k: None)
    monkeypatch.setattr(P, "after_download", lambda c, done: None)
    monkeypatch.setattr(P, "camset", SimpleNamespace(read=lambda d: d.values, diff=diff))
    if title is None:
        monkeypatch.setattr(P, "carousel_labels", lambda path: [])
        monkeypatch.setattr(P, "place", lambda c: c.read().kind)
        monkeypatch.setattr(P, "same_place", lambda a, b, tol=2: a == b)
        monkeypatch.setattr(ocr, "read", lambda frames, eng=None: {f: cam.lines(f) for f in frames})
        monkeypatch.setattr(screens, "notice_lit", lambda c: c.lit())
    else:
        monkeypatch.setattr(P, "carousel_labels", lambda path: ["On: Center", "Off"])     # the crawl's own map
    return P, SimpleNamespace(download=download, press=lambda key, cleanup=False: None), downloads


def said(lines) -> list:
    return [(r["label"], r["base"], r["final"], [(c["key"], c["before"], c["after"]) for c in r["changes"]])
            for r in lines]


# ------------------------------------------------------------------------------------- the step after OK

def test_the_fake_camera_ticks_its_box_on_an_enter_while_the_box_is_lit():
    """The camera these tests use: Enter on the information screen while its box is lit ticks the box, and the tests
    below would see it; Down then Enter takes the OK and leaves the box as it was."""
    cam = FramingStabilizer()
    for key in ("right", "down", "enter", "enter"):
        cam.press(key)
    assert cam.ticked and cam.enter_on_box == ["00004_enter.png"] and cam.where == "info"
    cam = FramingStabilizer()
    for key in ("right", "down", "enter", "down", "enter"):
        cam.press(key)
    assert not cam.ticked and cam.enter_on_box == [] and cam.where == "menu"


def test_the_axis_job_leaves_the_information_screen_after_ok_by_the_list_jobs_step(monkeypatch):
    """OK on On: Manual brings up the information screen, its box lit: the axis job takes the cursor off the box with
    Down and leaves the screen with MENU (proving.screens.info_notice_ok, the list job's step), never Enter on the box,
    and its proof line keeps the notice as the list job's keeps it (proving.commit.after_ok on the same screen) with
    the records the choice wrote. The last visit, Off with the axis back on Center, wrote nothing."""
    from proving import commit
    cam = FramingStabilizer()
    P, link, downloads = proof_seams(monkeypatch, cam)
    start = Dat("00001_start.DAT", cam.records())
    out = Lines()
    assert P.prove_axis_row(cam, link, None, axis_job(), start, out) is downloads[-1]
    assert cam.enter_on_box == [] and not cam.ticked
    assert cam.keys == ["right", "down", "right", "enter", "down", "menu", "right", "right", "up", "enter"]
    assert said(out) == [("On: Manual", start.name, False, [(OPTION_KEY, 1, 0), (AXIS_KEY, 0, 1)]),
                         ("On: Center", start.name, True, [])]
    assert [r["applied"] for r in out] == [True, True] and out[1]["notice"] is None
    # the list job's step on the same screen: its notice, as prove_row writes it
    other = FramingStabilizer()
    for key in ("right", "down", "right", "enter"):
        other.press(key)
    monkeypatch.setattr(ocr, "read", lambda frames, eng=None: {f: other.lines(f) for f in frames})
    listed = commit.after_ok(other, ROW, label="On: Manual", back=lambda: other.read().kind == "menu")
    assert listed.kind == commit.INFO_OK and other.enter_on_box == []
    assert out[0]["notice"] == listed.notice == {"text": " ".join(INFO + [BOX, OK]), "frame": "00005_enter.png",
                                                 "left_by": "menu"}


@pytest.mark.parametrize("sticky", [False, True], ids=["axis-record", "flag-that-stays"])
def test_with_first_on_manual_center_chosen_after_it_is_proved_whatever_its_record_does(monkeypatch, sticky):
    """--first "Framing Stabilizer / On=On: Manual": Manual is chosen first, then Center against it, then Manual again;
    whether global:0x1188 goes back to 0 at Center (the axis's record) or stays at 1 (a flag that stays) the Center line
    shows it (the change, or none) and the run does not fail on it, the last visit back on Manual writing nothing.
    Without --first, Center is never chosen after Manual: the last visit chooses Off with the axis moved back, and a
    flag that stays fails that visit's empty diff."""
    cam = FramingStabilizer(sticky=sticky)
    P, link, downloads = proof_seams(monkeypatch, cam)
    monkeypatch.setitem(P.FIRST, JOB_KEY, "On: Manual")
    start = Dat("00001_start.DAT", cam.records())
    out = Lines()
    P.prove_axis_row(cam, link, None, axis_job(), start, out)
    first = downloads[0].name
    assert said(out) == [("On: Manual", start.name, False, [(OPTION_KEY, 1, 0), (AXIS_KEY, 0, 1)]),
                         ("On: Center", first, False, [] if sticky else [(AXIS_KEY, 1, 0)]),
                         ("On: Manual", first, True, [])]
    assert [r["notice"]["left_by"] for r in out] == ["menu"] * 3 and cam.enter_on_box == []
    plain = FramingStabilizer(sticky=sticky)
    P, link, downloads = proof_seams(monkeypatch, plain)
    monkeypatch.delitem(P.FIRST, JOB_KEY)
    out = Lines()
    if sticky:
        with pytest.raises(P.Failed, match="axis and option back, 1 records still differ"):
            P.prove_axis_row(plain, link, None, axis_job(), Dat("00001_start.DAT", plain.records()), out)
    else:
        P.prove_axis_row(plain, link, None, axis_job(), Dat("00001_start.DAT", plain.records()), out)
    assert [r["label"] for r in out] == ["On: Manual", "On: Center"] and plain.enter_on_box == []


# ------------------------------------------------------------------------------------- the run's own frames

A1 = paths.a1ii_root()
SHOTS = A1 / "kit2_pass2" / "shots"


def run_frames(*names):
    """Skips without the run's frames (runs/ is the owner's, in their clone alone) or without this computer's OCR."""
    missing = [n for n in names if not (SHOTS / n).exists()]
    if missing:
        pytest.skip(f"{SHOTS / missing[0]} not present")
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")


class Replay:
    """The run's own frames one after another, read by the pixel reader and this computer's OCR: a key takes the frame
    `after` names for it, any other key fails the test, and an Enter on `box_lit` is kept (`enter_on_box`)."""

    def __init__(self, name, after=None, box_lit=None):
        from camkit import frames
        self.load, self.after, self.box_lit, self.presses, self.enter_on_box = frames.load, after or {}, box_lit, [], []
        self.name, self.frame = name, frames.load(SHOTS / name)

    def read(self):
        return screen.read(self.frame)

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "enter" and self.name == self.box_lit:
            self.enter_on_box.append(self.name)
        nxt = self.after.get(self.name, {}).get(key)
        if nxt is None:
            pytest.fail(f"{key} on {self.name}: a key the run's frames do not answer")
        self.name, self.frame = nxt, self.load(SHOTS / nxt)


@pytest.mark.parametrize("box_lit, value", [("264911_enter.png", "On: Manual"), ("264769_enter.png", "On: Center")],
                         ids=["manual-run-3", "center-run-1"])
def test_the_information_screen_after_ok_on_the_runs_own_frames(box_lit, value):
    """The information screens the run met after OK on On, through the camera's own picture: no known kind, the box lit
    over the OK. The step after OK the axis job now shares with the list job presses Down, which lit the OK
    (264770_down.png: the list job's own frame after its Down on the Center screen; the Manual screen's was never taken,
    the axis job having failed there), then MENU, back on the row (264771_menu.png, which matches the row's place before
    Right, 264901_menu.png); an Enter while the box is lit fails the test."""
    from proving import commit
    from proving.screens import place, same_place
    run_frames(box_lit, "264770_down.png", "264771_menu.png", "264901_menu.png")
    row = place(Replay("264901_menu.png"))
    cam = Replay(box_lit, {box_lit: {"down": "264770_down.png"},
                           "264770_down.png": {"up": box_lit, "menu": "264771_menu.png", "enter": "264771_menu.png"}},
                 box_lit=box_lit)
    assert cam.read().kind == "unknown"
    got = commit.after_ok(cam, ROW, label=value, back=lambda: same_place(place(cam), row))
    assert cam.enter_on_box == [] and cam.presses == ["down", "menu"]
    assert (got.kind, got.applied, got.notice["frame"], got.notice["left_by"]) == (commit.INFO_OK, True, box_lit, "menu")
    assert got.notice["text"].startswith("Enables shooting of a movie")
    assert same_place(place(cam), row)

