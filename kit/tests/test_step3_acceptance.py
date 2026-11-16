# acceptance version 2
"""Acceptance tests for step 3 of the guard rewrite (the look lap), written before the code from the design.

D1  a run given --network (crawl_run.py, drive.py) may open, to look at only, every menu row with no owner decision
    naming it, except (a) the rows of the safety.OWNER_NEVER list (never; the list, not the function, which also names
    sound, light and motion: O-1) and the Screen Reader (O-2), (b) the short destructive list, a row never_open names
    whose name holds format, delete or reset (O-12): their first open on a body stays the owner's own run; once this
    body's own records show the row seen opened with nothing changed, a look lap opens it like any other row, and (c) a
    row safety.acts_on_open names, never opened by a look lap, seen or not (O-10). What a look lap opens that this body's
    records have not seen opened goes under the first-open procedure (camkit.first_open), unchanged. A --network run
    with no reviewed scope stops before connecting (O-11), and --panels with --network is refused (O-15).
D2  inside a row the look lap looks, leaves with MENU, chooses only an option a dated decision names, answers no
    question, withholds as a --network run does; every row safety blanks for the owner route has its frames saved
    black, whatever a decision says of values (O-8, O-9); inside a credentials row or an address screen, MENU alone
    (O-6, O-7).
Version 2 adds a test for each open case the coordinator decided (OPEN_CASES.txt, each decision written there).
D3  ordinary runs and provers are unchanged, but an opening check judges the ROW, not a known value shown beside it.
D4  "lifts": "network" decisions stay valid: they let a look lap choose a named option.

The tests drive kit/crawl_run.py's and kit/drive.py's main() end to end over a simulated camera: the real Link to the
stand-in camlink (fake_camlink.py, every line it receives logged), the real LiveCamera, crawl, first_open and every
guard; only what stands for the camera's screen is simulated (camkit.screen.read, camkit.ocr.read, camkit.live.lit_found
and the eyes), plus the seams the existing tests fake (load_scan, Run, Link's binary, check_readers, the session's end).
They assert behaviour, never a name the author has yet to choose: which keys reach the stand-in camera and in what
order, whether RESTORE_BY_HAND.json is there at a Right, a row's outcome class in rows.jsonl, exit statuses, and what is
and is not written to events.jsonl, rows.jsonl, the frames and the console. Where an outcome's words are matched, the
comment says what wording is accepted.

ordinary_expected.json (beside this file) holds main's verdicts at commit 043ea93 for every a1 II row label and value,
written by the function make_ordinary_expected below; test_ordinary_* compare the code with it mechanically.
"""
import ast
import contextlib
import io
import json
import os
import re
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fake_camlink  # noqa: E402
from camkit import coverage, live, ocr, safety, screen, vlm  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.runs import RESTORE_BY_HAND, Run  # noqa: E402
from conftest import TEST_CAMERA  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DAY = "2026-11-15"
BLANK = {"date": DAY, "cards": "blank", "why": "typed by the owner"}
CRUMB = "Setup > Test Group"
OPENERS = ("right", "enter", "ms_right", "ms_enter")
ENTERS = ("enter", "ms_enter")
LOOK_KEYS = {"up", "down", "ms_up", "ms_down", "menu"}
SHOOTING_LINES = ["1/250", "F4.0", "ISO 100"]


# =============================================================================================== the simulated camera

def srow(label, value="", kind="list", options=("On", "Off"), lines=(), current=0, scan_value=None, bar=None):
    """One menu row of the simulated camera: its label and the value its bar shows beside it, and what Right opens: a
    screen of `kind` (camkit.screen's kinds: list, dialog, checklist, notice, unknown, keyset...) showing `lines` and its
    `options` (a list's options, a question's buttons; a notice's OK), the cursor on `current`. scan_value: the value the
    page scan recorded beside the row (by default the one shown now); bar: the lit bar's text read as one line, where
    the camera draws label and value run together (by default the label and the value as two lines)."""
    return {"label": label, "value": value, "kind": kind, "options": list(options), "lines": list(lines),
            "current": current, "scan_value": value if scan_value is None else scan_value, "bar": bar}


class Sim:
    """The camera behind the stand-in camlink: a menu page of `rows` in a Down cycle, the shooting screen, and the screen
    each row opens. MENU toggles the menu (and leaves any screen opened from it), Down and Up move round the page or a
    screen's options, Right or Enter on a menu row opens it; Enter on an opened screen chooses its lit option (recorded
    in `chosen`) or answers its question (`answered`), and the page comes back."""

    def __init__(self, rows, root: Path, crumb=CRUMB):
        assert len(rows) <= 10, "one page of at most ten rows"
        self.rows, self.root, self.crumb = rows, Path(root), crumb
        self.mode, self.pos, self.opt = "shooting", 0, 0
        self.trace = []             # (key, mode before, row, option, RESTORE_BY_HAND there)
        self.chosen, self.answered = [], []
        self.states, self.ids, self.names = [], {}, {}

    # ---- keys
    def key(self, key):
        marker = (self.root / RESTORE_BY_HAND).exists()
        self.trace.append((key, self.mode, self.pos, self.opt, marker))
        r = self.rows[self.pos]
        if self.mode == "shooting":
            if key == "menu":
                self.mode = "menu"
        elif self.mode == "menu":
            if key == "menu":
                self.mode = "shooting"
            elif key in ("down", "ms_down"):
                self.pos = (self.pos + 1) % len(self.rows)
            elif key in ("up", "ms_up"):
                self.pos = (self.pos - 1) % len(self.rows)
            elif key in OPENERS:
                self.mode, self.opt = "open", r["current"]
        elif self.mode == "open":
            n = len(r["options"])
            if key == "menu":
                self.mode = "menu"
            elif key in ("down", "ms_down") and n:
                self.opt = (self.opt + 1) % n
            elif key in ("up", "ms_up") and n:
                self.opt = (self.opt - 1) % n
            elif key in ENTERS:
                (self.chosen if r["kind"] in ("list", "dialog", "checklist", "sidelist") else self.answered).append(
                    (r["label"], r["options"][self.opt] if n else None))
                self.mode = "menu"

    # ---- what the camera shows
    def state(self) -> tuple:
        return (self.mode, self.pos, self.opt if self.mode == "open" else None)

    def state_id(self, state=None) -> int:
        st = state or self.state()
        if st not in self.ids:
            self.ids[st] = len(self.states)
            self.states.append(st)
        return self.ids[st]

    def image(self, sid: int):
        a = np.full((480, 640, 3), 24, np.uint8)
        a[0, 0, :] = (sid & 0xFF, (sid >> 8) & 0xFF, 7)
        return a

    def of_image(self, image) -> tuple:
        try:
            px = image[0, 0]
            if int(px[2]) == 7:
                return self.states[int(px[0]) | (int(px[1]) << 8)]
        except Exception:
            pass
        return self.state()

    def of_path(self, path) -> tuple:
        sid = self.names.get(Path(path).name)
        return self.states[sid] if sid is not None else self.state()

    def menu_y(self, i: int) -> int:
        return 60 + 40 * i

    def lines(self, st) -> list:
        mode, pos, opt = st
        L = ocr.Line
        if mode == "shooting":
            return [L(t, 0.99, 20 + 120 * i, 440, 100, 20) for i, t in enumerate(SHOOTING_LINES)]
        if mode == "menu":
            out = [L(self.crumb, 0.99, 10, 10, 400, 20)]
            for i, r in enumerate(self.rows):
                y = self.menu_y(i)
                if r["bar"] is not None:
                    out.append(L(r["bar"], 0.99, 60, y, 540, 20))
                    continue
                out.append(L(r["label"], 0.99, 60, y, 300, 20))
                if r["value"]:
                    out.append(L(r["value"], 0.99, 380, y, 220, 20))
            return out
        r = self.rows[pos]
        out = [L(r["label"], 0.99, 10, 10, 400, 20)]
        out += [L(t, 0.99, 60, 40 + 22 * i, 500, 18) for i, t in enumerate(r["lines"])]
        out += [L(t, 0.99, 60, 200 + 40 * j, 300, 20) for j, t in enumerate(r["options"])]
        return out

    def lit_box(self, st):
        mode, pos, opt = st
        if mode == "menu":
            y = self.menu_y(pos)
            return (30, y - 6, 620, y + 26)
        if mode == "open" and self.rows[pos]["options"]:
            y = 200 + 40 * opt
            return (30, y - 6, 620, y + 26)
        return None

    def screen(self, st):
        mode, pos, opt = st
        sig = f"{mode}:{pos}:{opt}"
        if mode == "shooting":
            return screen.Screen(kind="shooting", signature=sig, struct=(mode,))
        if mode == "menu":
            return screen.Screen(kind="menu", focus="rows", row=pos, signature=sig, struct=(mode, pos))
        r = self.rows[pos]
        n = len(r["options"])
        tracks = r["kind"] in screen.TRACKS
        return screen.Screen(kind=r["kind"], row=opt if tracks else None, count=n if tracks else None, scroll=None,
                             signature=sig, struct=(mode, pos, opt))

    def texts(self, st) -> list:
        return [ln.text for ln in self.lines(st)]

    # ---- the scan the crawl and drive.py are given
    def scan(self):
        cycle = [{"page": "P", "row": i, "signature": f"menu:{i}:None", "kind": "menu",
                  "screen": self.screen(("menu", i, None))} for i in range(len(self.rows))]
        model = {"P": {"breadcrumb": self.crumb, "page": "1/1",
                       "rows": [{"slot": i, "label": r["label"], "value": r["scan_value"] or None,
                                 "readings": {"label": {"ocr": r["label"]},
                                              "value": {"ocr": r["scan_value"]} if r["scan_value"] else {}},
                                 "never_open": safety.never_open(r["label"])}
                                for i, r in enumerate(self.rows)]}}
        return cycle, model

    # ---- what the trace says
    def opened(self, i: int) -> bool:
        return any(k in OPENERS and m == "menu" and p == i for k, m, p, _, _ in self.trace)

    def marked_at_open(self, i: int):
        return next((mk for k, m, p, _, mk in self.trace if k in OPENERS and m == "menu" and p == i), None)

    def inside(self, i: int) -> list:
        return [k for k, m, p, _, _ in self.trace if m == "open" and p == i]


class Eyes:
    """The run's eyes over the simulated camera: every frame a picture of the state it shows (its id in a pixel) and,
    saved, a file holding the screen's text, or BLACK while the camera has its eyes withhold (LiveCamera.withhold sets
    `withheld`, as camkit.frames' eyes take it)."""
    name = "hdmi"

    def __init__(self, sim, run):
        self.sim, self.run, self.timing, self.withheld = sim, run, {}, False

    def attach(self, link):
        pass

    def close(self):
        pass

    def close_private(self):
        pass

    def grab(self, tag="grab", save=True):
        return self._frame(tag, save)

    def settle(self, before, tag, expect_change=True, sent_at=None, quiet=None, timeout=None, **kw):
        return self._frame(tag, True), True

    def _frame(self, tag, save):
        st = self.sim.state()
        sid = self.sim.state_id(st)
        path = self.run.shot_path(str(tag))
        self.sim.names[path.name] = sid
        if save:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"BLACK" if self.withheld else "\n".join(self.sim.texts(st)).encode("utf-8"))
        return SimpleNamespace(image=self.sim.image(sid), path=path)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def sleep(self, s):
        self.now += float(s or 0)

    def monotonic(self):
        return self.now

    def time(self):
        return self.now


def wire(monkeypatch, sim, tmp_path):
    """The simulated screen under camkit (screen.read, ocr.read, live.lit_found), a clock for camkit.live's waits, and
    the factory of the real Link to the stand-in camlink whose presses move the simulated camera."""
    log = tmp_path / "camlink.log"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.setattr(screen, "read", lambda f: sim.screen(sim.of_image(getattr(f, "image", None))))
    monkeypatch.setattr(ocr, "read", lambda paths, eng=None: {Path(p): sim.lines(sim.of_path(p)) for p in paths})
    monkeypatch.setattr(live, "lit_found", lambda image, kind=None: (lambda b: (b, b is not None))(
        sim.lit_box(sim.of_image(image))))
    monkeypatch.setattr(live, "time", Clock())
    from camkit import session
    monkeypatch.setattr(session, "wait_for", lambda *a, **k: None)
    from camkit import vlm as _vlm
    monkeypatch.setattr(_vlm, "ask_role", lambda *a, **k: (_ for _ in ()).throw(_vlm.NoReader("no reader in the test")))
    with contextlib.suppress(AttributeError):
        monkeypatch.setattr(live, "ask_role", lambda *a, **k: (_ for _ in ()).throw(_vlm.NoReader("no reader")))

    class SimLink(Link):
        def press(self, button, *a, **kw):
            r = super().press(button, *a, **kw)
            sim.key(button)
            return r

    def factory(r, **kw):
        kw.pop("link_class", None)
        return SimLink(r, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False)
    return log, factory


def sent_keys(log: Path) -> list:
    """The keys of every press the stand-in camlink received, in order."""
    out = []
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8").splitlines():
        words = ast.literal_eval(line).decode("utf-8", "replace").split()
        if words and words[0].startswith("@"):
            words = words[1:]
        if len(words) >= 2 and words[0] == "press":
            out.append(words[1])
    return out


def look(path, did="open", result="looked", **kw):
    return {"t": f"{DAY}T10:00:00", "by": "crawl", "path": list(path), "did": did, "result": result, **kw}


def seen_on(camera: str, *labels):
    """This body's own records show each row seen opened with nothing changed (a clean look, as a crawl writes)."""
    for label in labels:
        assert coverage.append_look(camera, look([label] if isinstance(label, str) else label))


@pytest.fixture
def scope(own_runs, monkeypatch):
    """write(*decisions): the camera's reviewed scope with those decisions (and statements), where the kit reads it."""
    from proving import base
    pass1 = own_runs / TEST_CAMERA / "kit2_pass1"
    monkeypatch.setattr(base, "PASS1", pass1)

    def write(*decisions):
        pass1.mkdir(parents=True, exist_ok=True)
        f = pass1 / "pass2_scope_draft.json"
        f.write_text(json.dumps({"prove": [], "exclude": {}, "decisions": list(decisions)}), encoding="utf-8")
        return f
    write.file = pass1 / "pass2_scope_draft.json"
    return write


def nothing_but(monkeypatch, module, sim, run, eyes, link_factory, model_scan, seen_local):
    """The seams of crawl_run.py and drive.py the existing tests fake, faked alike."""
    for name, value in (("load_scan", lambda scan=None: model_scan),
                        ("Run", lambda name: run),
                        ("check_readers", lambda: seen_local.append(vlm.LOCAL_ONLY)),
                        ("eyes_from_config", lambda r: eyes),
                        ("Link", link_factory),
                        ("wait_for", lambda *a, **k: None),
                        ("time", Clock()),
                        ("close_for_restore", lambda cam, link, start: live.close(cam, link)),
                        ("restore_checked", lambda r, e, before, **kw: True)):
        monkeypatch.setattr(module, name, value)


class Ran(SimpleNamespace):
    """What a run did: code, console, keys (as the stand-in camlink got them), sim, run, rows (rows.jsonl by slot), events
    (events.jsonl's text), local (vlm.LOCAL_ONLY when the readers were checked, before the link opened)."""

    def row(self, i: int) -> dict:
        return self.rows.get(i) or {}

    def outcome(self, i: int) -> str:
        return str(self.row(i).get("outcome") or "")


def run_main(module, argv):
    sys_argv = sys.argv
    out, code = io.StringIO(), 0
    sys.argv = [f"{module.__name__}.py", *argv]
    try:
        with contextlib.redirect_stdout(out):
            try:
                module.main()
            except SystemExit as e:
                code = e.code
    finally:
        sys.argv = sys_argv
    return code, out.getvalue()


def crawl_lap(tmp_path, monkeypatch, rows, argv=(), seen=()):
    """kit/crawl_run.py's main() over the simulated camera whose page holds `rows`, `seen` the labels this body's records
    show opened cleanly. Returns a Ran."""
    import crawl_run as C
    root = tmp_path / "cam"
    root.mkdir(parents=True, exist_ok=True)
    run = Run("kit2_crawl", root=root)
    sim = Sim(rows, root)
    seen_on(root.name, *seen)
    log, factory = wire(monkeypatch, sim, tmp_path)
    eyes = Eyes(sim, run)
    local = []
    nothing_but(monkeypatch, C, sim, run, eyes, factory, sim.scan(), local)
    monkeypatch.setattr(C, "LOCK_S", 0)
    monkeypatch.setattr(C, "end_session", lambda *a, **k: SimpleNamespace(after=root / "after.DAT", uploaded=False,
                                                                           changes=[]))
    code, out = run_main(C, list(argv))
    rows_file = run.dir / "rows.jsonl"
    got = [json.loads(x) for x in rows_file.read_text(encoding="utf-8").splitlines()] if rows_file.exists() else []
    events = (run.dir / "events.jsonl").read_text(encoding="utf-8") if (run.dir / "events.jsonl").exists() else ""
    keys = sent_keys(log)
    assert keys == [k for k, *_ in sim.trace], (keys, sim.trace)      # the harness: every press the camlink got moved it
    return Ran(code=code, out=out, keys=keys, sim=sim, run=run, rows={r.get("slot"): r for r in got}, events=events,
               local=local, eyes=eyes, root=root)


def drive_run(tmp_path, monkeypatch, rows, path, presses, extra=(), seen=(), root=None):
    """kit/drive.py's main() over the simulated camera, its --path and --press as given (and `extra` arguments, such as
    --network); `seen` the labels the camera's records show opened cleanly (TEST_CAMERA's, which drive.py reads);
    `root` the run root (by default one no coverage gate reads; TEST_CAMERA's own under runs_top for one that does)."""
    import drive as D
    root = root or tmp_path / "cam"
    root.mkdir(parents=True, exist_ok=True)
    run = Run("kit2_drive", root=root)
    sim = Sim(rows, root)
    seen_on(TEST_CAMERA, *seen)
    log, factory = wire(monkeypatch, sim, tmp_path)
    eyes = Eyes(sim, run)
    local = []
    nothing_but(monkeypatch, D, sim, run, eyes, factory, sim.scan(), local)
    ending = SimpleNamespace(after=root / "after.DAT", uploaded=False, changes=[])
    monkeypatch.setattr(D, "session", SimpleNamespace(ended=lambda link, before, **k: ending,
                                                      put_back=lambda link, e, before: e))
    argv = [*extra, *[x for p in path for x in ("--path", p)], *[x for p in presses for x in ("--press", p)]]
    code, out = run_main(D, argv)
    lines = (run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines() if (run.dir / "drive.jsonl").exists() \
        else []
    events = (run.dir / "events.jsonl").read_text(encoding="utf-8") if (run.dir / "events.jsonl").exists() else ""
    keys = sent_keys(log)
    assert keys == [k for k, *_ in sim.trace], (keys, sim.trace)
    return Ran(code=code, out=out, keys=keys, sim=sim, run=run, line=json.loads(lines[-1]) if lines else None,
               events=events, local=local, eyes=eyes, root=root, rows={})


DRIVE_MODE = srow("Drive Mode", "Single Shooting", options=("Single Shooting", "Cont. Shooting", "Self-timer"))
ISO = srow("ISO", "Auto", options=("Auto", "100", "200"))


# ================================================================================================ harness sanity

def test_harness_an_ordinary_lap_opens_seen_rows_and_skips_a_never_open_one(tmp_path, monkeypatch, scope):
    """The harness itself: on main an ordinary lap opens two seen ordinary rows and skips Language, nothing pressed."""
    lap = crawl_lap(tmp_path, monkeypatch, [DRIVE_MODE, srow("Language", "English", options=("English", "Français")),
                                            ISO], seen=["Drive Mode", "Language", "ISO"])
    assert lap.code in (0, None), lap.out
    assert lap.sim.opened(0) and lap.sim.opened(2) and not lap.sim.opened(1)
    assert lap.outcome(1).startswith("skipped")
    assert "enter" not in lap.keys


# ======================================================================================= helpers the groups share

NETWORK = ["--network"]
NETWORK_DECISION = {"date": DAY, "lifts": "network", "why": "the owner: the kit may choose Off there",
                    "rows": ["Bluetooth Function"], "options": {"Bluetooth Function": ["Off"]}}
# A dated network decision naming a row that is on none of these pages: on main it lets a --network run start (main
# stops one with no decision before it connects), so a test of what must STILL be refused runs a real lap on main and
# passes there; after step 3 it changes nothing (D4: a decision only lets a look lap choose a named option)
UNRELATED = {"date": DAY, "lifts": "network", "why": "the owner: Bluetooth Function", "rows": ["Bluetooth Function"]}


def lap_with(tmp_path, monkeypatch, target, seen_target, argv=NETWORK):
    """A look lap (or the lap `argv` says) over Drive Mode, `target`, ISO: the two ordinary rows seen opened, the target
    as `seen_target` says."""
    seen = ["Drive Mode", "ISO"] + ([target["label"]] if seen_target else [])
    return crawl_lap(tmp_path, monkeypatch, [DRIVE_MODE, target, ISO], argv=argv, seen=seen)


def assert_lap_went_on(lap):
    """The lap ran to its end: exit 0, both ordinary rows opened, nothing chosen or answered, no Enter sent."""
    assert lap.code in (0, None), lap.out[-2000:]
    assert lap.sim.opened(0) and lap.sim.opened(2), lap.keys
    assert not lap.sim.chosen and not lap.sim.answered and not set(lap.keys) & set(ENTERS), lap.keys


def assert_looked_only(lap, i):
    """Inside row i only up, down and MENU went out (D2: looked at, left with MENU), and it was left with MENU."""
    inside = lap.sim.inside(i)
    assert inside and set(inside) <= LOOK_KEYS and inside[-1] == "menu", inside


def assert_skipped_untouched(lap, i):
    """Row i: no Right or Enter on it, recorded as skipped."""
    assert not lap.sim.opened(i), lap.keys
    assert lap.outcome(i).startswith("skipped"), lap.row(i)


# ================================================================== D1: the look lap opens what main never opened

# Each row as the camera shows it when Right opens it. A secret on a screen is a made-up value that must never be kept.
SECRET_USER, SECRET_PW, SECRET_IP, SECRET_MAC = "camuser7", "hunter2pass", "192.0.2.77", "00:11:22:33:44:55"
SECRET_NAME, SECRET_SERIAL, SECRET_DATE = "ILCE-1M2-made-up-name", "X9-made-up-serial", "2026/11/15 10:22"
LOOK_OPENS = {
    # by-hand identity rows
    "Language": srow("Language", "English", options=("English", "Français", "Deutsch")),
    "USB Connection Mode": srow("USB Connection Mode", "MTP", options=("MTP", "Mass Storage", "PC Remote")),
    "NTSC/PAL Selector": srow("NTSC/PAL Selector", "NTSC", kind="unknown", lines=("Change to PAL?",
                                                                                 "The camera will restart."),
                              options=("Enter", "Cancel"), current=1),
    "Area/Date/Time Setting": srow("Area/Date/Time Setting", "", kind="unknown",
                                   lines=("Area Setting", "Date/Time", SECRET_DATE), options=()),
    # Wi-Fi and Bluetooth settings
    "Wi-Fi Frequency Band": srow("Wi-Fi Frequency Band", "2.4GHz", options=("2.4GHz", "5GHz")),
    "Airplane Mode": srow("Airplane Mode", "Off"),
    # address screens
    "Display Wi-Fi Info.": srow("Display Wi-Fi Info.", "", kind="unknown",
                                lines=("MAC Address", SECRET_MAC, "IP Address", SECRET_IP), options=()),
    # connection rows
    "Wi-Fi Connect": srow("Wi-Fi Connect", "Off"),
    "Bluetooth Function": srow("Bluetooth Function", "Off"),
    # credentials
    "Access Authen. Info": srow("Access Authen. Info", "", kind="unknown",
                                lines=("User Name", SECRET_USER, "Password", SECRET_PW), options=()),
    "Password": srow("Password", "", kind="keyset", lines=(SECRET_PW, "abc", "Done"), options=()),
    # sound and light
    "Audio signals": srow("Audio signals", "On"),
    "AF Illuminator": srow("AF Illuminator", "Auto", options=("Auto", "Off")),
    # actions that destroy nothing
    "Rating": srow("Rating", "", kind="notice", lines=("There are no images.",), options=("OK",)),
    "Protect": srow("Protect", "", kind="notice", lines=("There are no images.",), options=("OK",)),
    "Slide Show": srow("Slide Show", "", kind="unknown", lines=("Start the slide show?",),
                       options=("Enter", "Cancel"), current=0),
    "Display Serial Number": srow("Display Serial Number", "", kind="unknown",
                                  lines=("Serial Number", SECRET_SERIAL), options=()),
    "Privacy Notice": srow("Privacy Notice", "", kind="unknown",
                           lines=("Privacy Notice", "How the camera handles information."), options=("OK",)),
}
CREDENTIAL_ROWS = ("Access Authen. Info", "Password")
# version 2: IP Address Setting left LOOK_OPENS (D1 (c), O-10: safety.acts_on_open names it, never opened by a look lap);
# the crawl takes Display Wi-Fi Info. too (O-6): CRAWL_OPENS is LOOK_OPENS
CRAWL_OPENS = list(LOOK_OPENS)


@pytest.mark.parametrize("label", CRAWL_OPENS)
def test_look_lap_opens_a_seen_never_open_row_with_right_and_no_marker(tmp_path, monkeypatch, scope, label):
    """D1: a row main never opens, seen opened on this body, opens on a look lap with no decision, plainly (no marker)."""
    scope()                                             # a reviewed scope with no decision and no statement
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS[label], seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1), (label, lap.row(1), lap.out[-1500:])
    assert lap.sim.marked_at_open(1) is False                # a seen row: no RESTORE_BY_HAND at its Right
    assert_looked_only(lap, 1)
    assert not lap.outcome(1).startswith(("skipped", "error", "lost")), lap.row(1)
    assert not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", CRAWL_OPENS)
def test_look_lap_opens_an_unseen_row_under_the_first_open_procedure(tmp_path, monkeypatch, scope, label):
    """D1: the same row not yet seen on this body opens on a look lap only under 21bf67e's procedure: RESTORE_BY_HAND
    there at its Right, a clean check after, the marker gone, the row seen from then on where the lap kept its name; a
    row whose name it withheld (kit/crawl_run.py kept_label: no definition names it here) stays unseen, so its first
    open runs under the procedure again on the next lap."""
    from camkit import first_open
    scope(BLANK)
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS[label], seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, (label, lap.row(1))
    assert lap.sim.marked_at_open(0) is False and lap.sim.marked_at_open(2) is False
    assert_looked_only(lap, 1)
    assert not (lap.root / RESTORE_BY_HAND).exists()
    assert lap.row(1)["label"] in (label, "(withheld)"), lap.row(1)
    assert first_open.seen_record(lap.root.name).seen([label]) is (lap.row(1)["label"] == label)


@pytest.mark.parametrize("label", CRAWL_OPENS)
def test_look_lap_skips_an_unseen_row_without_the_cards_statement(tmp_path, monkeypatch, scope, label):
    """D1: without the owner's blank-cards statement an unseen row is skipped, nothing pressed on it, and the lap goes on
    (outcome: "skipped" and "not seen" in it, as first_open.SKIPPED words it today)."""
    scope()
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS[label], seen_target=False)
    assert_lap_went_on(lap)
    assert_skipped_untouched(lap, 1)
    assert "not seen" in lap.outcome(1), lap.row(1)


@pytest.mark.parametrize("label", list(LOOK_OPENS))
def test_drive_look_lap_opens_a_seen_never_open_row(tmp_path, monkeypatch, scope, label):
    """D1, kit/drive.py: --network opens a seen row of any of these classes with no decision naming it, looks (Down),
    leaves with MENU; nothing is chosen."""
    scope()
    target = LOOK_OPENS[label]
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, target, ISO], [label], ["right", "down", "menu"], extra=NETWORK,
                  seen=[label])
    assert d.code in (0, None), d.out[-1500:]
    assert d.sim.opened(1), (label, d.out[-1500:])
    assert not set(d.keys) & set(ENTERS) and not d.sim.chosen and not d.sim.answered
    assert set(d.sim.inside(1)) <= LOOK_KEYS, d.sim.inside(1)
    assert d.sim.mode != "open"                                  # left: the run closed what it opened
    assert not (d.root / RESTORE_BY_HAND).exists()


# drive.py's first open (21bf67e, as built) keeps RESTORE_BY_HAND and exits 5 where the screen after the Right has no kind the kit reads or no readable text (its frames kept black); the crawl makes the look lap's first open of these rows
DRIVE_FIRST_OPEN_BY_HAND = ("Language", "USB Connection Mode", "NTSC/PAL Selector", "Area/Date/Time Setting",
                            "Display Wi-Fi Info.", "Access Authen. Info", "Password", "Slide Show",
                            "Display Serial Number", "Privacy Notice")
DRIVE_FIRST_OPEN_BLANKED = ("Language", "USB Connection Mode", "NTSC/PAL Selector", "Area/Date/Time Setting",
                            "Access Authen. Info", "Password", "Display Serial Number")


@pytest.mark.parametrize("label", list(LOOK_OPENS))
def test_drive_look_lap_opens_an_unseen_row_with_the_marker_first(tmp_path, monkeypatch, scope, label):
    """D1, kit/drive.py: an unseen row's Right goes with RESTORE_BY_HAND there (the --path's first open, --press right
    alone), which a clean end takes away; where drive.py cannot read the screen after it (DRIVE_FIRST_OPEN_BY_HAND), the
    marker stays, nothing more is pressed, the run exits 5 and says how the start file goes back, and a blanked row's
    secrets are in no file and no line it printed."""
    scope(BLANK)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, LOOK_OPENS[label], ISO], [label], ["right"], extra=NETWORK)
    if label in DRIVE_FIRST_OPEN_BY_HAND:
        from exit_status import EXIT_RESTORE_BY_HAND
        assert d.code == EXIT_RESTORE_BY_HAND, (d.code, d.out[-1500:])
        assert d.sim.opened(1) and d.sim.marked_at_open(1) is True, (label, d.out[-1500:])
        assert (d.root / RESTORE_BY_HAND).exists()
        assert d.sim.inside(1) == [], d.sim.inside(1)
        assert not d.sim.chosen and not d.sim.answered
        assert "kit/tools/upload_check.py" in d.out, d.out[-1500:]
        if label in DRIVE_FIRST_OPEN_BLANKED:
            kept = d.out + "".join(p.read_bytes().decode("utf-8", "replace") for p in d.root.rglob("*") if p.is_file())
            for secret in (SECRET_USER, SECRET_PW, SECRET_IP, SECRET_MAC, SECRET_NAME, SECRET_SERIAL, SECRET_DATE):
                assert secret not in kept, secret
        return
    assert d.code in (0, None), d.out[-1500:]
    assert d.sim.opened(1) and d.sim.marked_at_open(1) is True, (label, d.out[-1500:])
    assert not (d.root / RESTORE_BY_HAND).exists()


# drive.py's first open over an option screen MENU leaves that SHOWN_KINDS does not hold (2026-11-15: Exposure Comp.'s
# slider, kit2_a1fin_expcomp_look, kept RESTORE_BY_HAND and was left open on the camera): safety.FIRST_OPEN_KINDS
FIRST_OPEN_READ = {
    "slider": srow("Lima Slider", "+0.0", kind="slider", options=(), lines=("-3", "0", "+3")),
    "fields": srow("Mike Fields", "10:30", kind="fields", options=(), lines=("10", ":", "30")),
    "table": srow("November Table", "", kind="table", options=("Alpha", "Bravo")),
}


@pytest.mark.parametrize("kind", list(FIRST_OPEN_READ))
def test_drive_first_open_goes_on_over_an_option_screen_menu_leaves(tmp_path, monkeypatch, scope, kind):
    """kit/drive.py, an ordinary run: an unseen row's Right (RESTORE_BY_HAND there) that shows a slider, number fields
    or a table is a screen the first open reads: MENU alone inside, the check clean, the marker gone, the row seen
    opened from then on, exit 0."""
    import camkit
    from camkit import first_open, paths
    scope(BLANK)
    monkeypatch.setattr(first_open, "other_body", lambda link, camera: "")
    target = FIRST_OPEN_READ[kind]
    root = paths.runs_top() / TEST_CAMERA              # where drive.py's coverage gate reads the run's drive.jsonl
    monkeypatch.setattr(camkit, "RUNS", paths.runs_top())     # its marker in the test's own runs/ alone, never the clone's
    assert not first_open.seen_record().seen([target["label"]])
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, target, ISO], [target["label"]], ["right"], root=root)
    assert d.code in (0, None), (kind, d.out[-1500:])
    assert d.sim.opened(1) and d.sim.marked_at_open(1) is True, (kind, d.out[-1500:])
    assert d.sim.inside(1) == ["menu"] and not d.sim.chosen and not d.sim.answered, d.sim.inside(1)
    assert not (root / RESTORE_BY_HAND).exists()
    assert d.line["first_open"] is True and d.line["screens"][0]["kind"] == kind, d.line
    assert "opens as any row from now on" in d.out, d.out[-1500:]
    assert first_open.seen_record().seen([target["label"]])


@pytest.mark.parametrize("case", ["unknown", "guide", "helppop", "black", "no text"])
def test_drive_first_open_still_stops_over_a_screen_it_cannot_read(tmp_path, monkeypatch, scope, case):
    """kit/drive.py, an ordinary run: an unseen row's Right that shows a screen of no kind safety.FIRST_OPEN_KINDS holds
    (unknown, a guide, a help popup), a black frame or no text keeps RESTORE_BY_HAND, presses nothing more and exits 5."""
    import drive as D
    from exit_status import EXIT_RESTORE_BY_HAND
    from camkit import first_open
    scope(BLANK)
    kind = case if case in ("unknown", "guide", "helppop") else "slider"
    target = srow("Oscar Row", "", kind=kind, options=(), lines=("Some", "Words"))
    real_black, real_text = D.black, D.screen_text
    if case == "black":             # the slider's frame black, every other as it is
        monkeypatch.setattr(D, "black", lambda frame: screen.read(frame).kind == "slider" or real_black(frame))
    if case == "no text":           # nothing read on the slider, every other screen read as it is
        monkeypatch.setattr(D, "screen_text", lambda cam, grip: "" if cam.read().kind == "slider"
                            else real_text(cam, grip))
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, target, ISO], ["Oscar Row"], ["right"])
    assert d.code == EXIT_RESTORE_BY_HAND, (case, d.code, d.out[-1500:])
    assert d.sim.opened(1) and d.sim.marked_at_open(1) is True and d.sim.inside(1) == [], (case, d.sim.trace)
    assert d.keys[-1] == "right" and (d.root / RESTORE_BY_HAND).exists()
    assert d.line["restore"] == "by hand" and "kit/tools/upload_check.py" in d.out
    assert not first_open.seen_record().seen(["Oscar Row"])


# =========================================================================== D1: what the look lap still refuses

# OWNER_NEVER's kinds (safety.OWNER_NEVER: a firmware update or Version, anything that loads, sensor, shutter or lens
# motion, Initialize), each with the readings OCR makes of it: one space dropped, every space dropped (run together), a
# word split, and a slip ("rn" for m, 0 for o, 1 for l, l for a capital I)
OWNER_NEVER_ROWS = ["Version", "Firmware Update", "Load Settings", "Recall Camera Setting", "Import Root Certificate",
                    "Register IPTC Info", "Cleaning Mode", "Pixel Mapping", "Anti-dust Function", "Preset Focus/Zoom",
                    "Initialize"]


def slip(label: str) -> str:
    """One OCR slip in `label`, of the kinds the kit undoes (safety.deslip, test_guards.py's SLIPS): the first of m read
    as rn, o as 0 after a letter, l as 1 between letters, a capital I at a word's start as l; the label itself when none
    applies. (1 read for i: O-4 decided it for the look lap's own checks alone; the version 2 tests below add it there,
    and ordinary_expected.json keeps main's verdicts without it.)"""
    for pat, rep in ((r"m", "rn"), (r"(?<=[A-Za-z])o", "0"), (r"(?<=[A-Za-z])l(?=[a-z])", "1"), (r"\bI", "l")):
        t, n = re.subn(pat, rep, label, count=1)
        if n:
            return t
    return label


def split(label: str) -> str:
    """The label with a space put inside its longest word, as OCR splits a word."""
    words = label.split(" ")
    k = max(range(len(words)), key=lambda i: len(words[i]))
    w = words[k]
    words[k] = w[:len(w) // 2] + " " + w[len(w) // 2:] if len(w) > 3 else w
    return " ".join(words)


def readings_of(label: str) -> list:
    """The label as written, one space dropped, all dropped, a word split, one slip, and the slip run together."""
    out = [label, label.replace(" ", "", 1), label.replace(" ", ""), split(label), slip(label),
           slip(label).replace(" ", "")]
    return list(dict.fromkeys(out))


def page_of(readings, kind="list") -> list:
    return [srow(r, "", kind=kind, options=("A", "B")) for r in readings]


@pytest.mark.parametrize("label", OWNER_NEVER_ROWS)
@pytest.mark.parametrize("seen", [False, True], ids=["unseen", "seen-recorded"])
def test_look_lap_never_opens_an_owner_never_row_in_any_reading(tmp_path, monkeypatch, scope, label, seen):
    """D1 (a): OWNER_NEVER's rows are never opened on a look lap, whatever reading OCR gives of them, with the cards
    statement given and even where this body's records say the row was seen opened (a record never unlocks them)."""
    scope(BLANK, UNRELATED)
    rows = page_of(readings_of(label)) + [ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["ISO", *(readings_of(label) if seen else [])])
    assert lap.code in (0, None, 7), lap.out[-1500:]       # 7: a refusal that stopped the lap is accepted too
    for i, r in enumerate(rows[:-1]):
        assert not lap.sim.opened(i), (r["label"], lap.keys)
    assert lap.code == 7 or lap.sim.opened(len(rows) - 1), lap.keys      # the lap ran: not a run that never started
    assert not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", OWNER_NEVER_ROWS)
def test_drive_look_lap_never_opens_an_owner_never_row(tmp_path, monkeypatch, scope, label):
    """D1 (a), kit/drive.py: --network --path <owner-never row> --press right sends no Right onto it, seen or not."""
    scope(BLANK, UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow(label, "", options=("A", "B")), ISO], [label], ["right"],
                  extra=NETWORK, seen=[label])
    assert not d.sim.opened(1), (label, d.keys)
    assert not (d.root / RESTORE_BY_HAND).exists()


# The short destructive list: Format, Delete, and anything named a reset; with OCR's readings of each
DESTRUCTIVE_ROWS = ["Format", "Delete", "Delete All", "Setting Reset", "Camera Settings Reset", "Reset Network Set.",
                    "SSID/PW Reset", "Factory Reset", "Series Counter Reset", "Reset Transfer Status",
                    "Forced File Number Reset"]
DESTRUCTIVE_SLIPS = ["Forrnat", "F0rmat", "Fоrmat", "De1ete", "Delete AII", "DeleteAll", "De lete", "Setting Rese t",
                     "SettingReset", "ResetNetwork Set.", "Reset Netw0rk Set.", "SSID/PWReset", "Factory Re set",
                     "Series CounterReset", "ResetTransfer Status"]
# what each opens when a run that may opens it: a slot list, a list of items, a reset's target list, a question
DESTRUCTIVE_SCREENS = {
    "Format": srow("Format", "", options=("Slot 1", "Slot 2")),
    "Delete": srow("Delete", "", options=("Multiple Img.", "All in this Folder", "All with this date")),
    "Delete All": srow("Delete All", "", kind="unknown", lines=("Delete all images?",), options=("Delete", "Cancel")),
    "Setting Reset": srow("Setting Reset", "", options=("Camera Settings Reset", "Initialize")),
    "Camera Settings Reset": srow("Camera Settings Reset", "", kind="unknown", lines=("Reset camera settings?",),
                                  options=("Enter", "Cancel")),
    "Reset Network Set.": srow("Reset Network Set.", "", kind="unknown", lines=("Reset network settings?",),
                               options=("Enter", "Cancel")),
    "SSID/PW Reset": srow("SSID/PW Reset", "", kind="unknown", lines=("Reset the SSID and password?",),
                          options=("OK", "Cancel")),
    "Factory Reset": srow("Factory Reset", "", kind="unknown", lines=("Return to factory settings?",),
                          options=("Enter", "Cancel")),
    "Series Counter Reset": srow("Series Counter Reset", "", kind="unknown", lines=("Reset the counter?",),
                                 options=("Enter", "Cancel")),
    "Reset Transfer Status": srow("Reset Transfer Status", "", kind="unknown", lines=("Reset transfer status?",),
                                  options=("OK", "Cancel")),
    "Forced File Number Reset": srow("Forced File Number Reset", "", kind="unknown",
                                     lines=("Create a new folder and reset the file number?",),
                                     options=("OK", "Cancel"), current=0),
}


@pytest.mark.parametrize("label", DESTRUCTIVE_ROWS + DESTRUCTIVE_SLIPS)
def test_look_lap_presses_nothing_on_an_unseen_destructive_row(tmp_path, monkeypatch, scope, label):
    """D1 (b): a destructive row (or a slipped reading of one) this body has not seen opened is never opened by a look
    lap, not even under the first-open procedure (the cards statement given): nothing pressed on it, no marker, the lap
    goes on."""
    scope(BLANK, UNRELATED)
    target = DESTRUCTIVE_SCREENS.get(label, srow(label, "", options=("A", "B")))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=False)
    assert_lap_went_on(lap)
    assert_skipped_untouched(lap, 1)
    assert lap.sim.marked_at_open(1) is None and not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", DESTRUCTIVE_ROWS + DESTRUCTIVE_SLIPS[:4])
def test_look_lap_says_an_unseen_destructive_row_is_the_owners_run(tmp_path, monkeypatch, scope, label):
    """D1 (b): the skipped destructive row's outcome points to the owner's own run (accepted: "owner" in the outcome,
    e.g. "drive.py --owner" or "the owner's own run"; on main it says only why the row is never opened)."""
    scope(BLANK, UNRELATED)
    target = DESTRUCTIVE_SCREENS.get(label, srow(label, "", options=("A", "B")))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=False)
    assert_skipped_untouched(lap, 1)
    assert "owner" in lap.outcome(1).lower(), lap.row(1)


@pytest.mark.parametrize("label", [x for x in DESTRUCTIVE_ROWS if x != "Forced File Number Reset"])   # v2: D1 (c)
def test_look_lap_opens_a_destructive_row_once_seen_opened_unchanged(tmp_path, monkeypatch, scope, label):
    """D1 (b): once this body's records show the destructive row seen opened with nothing changed, a look lap opens it
    like any other row: Right, looked at with up, down and MENU only, nothing chosen or answered."""
    scope(BLANK)
    lap = lap_with(tmp_path, monkeypatch, DESTRUCTIVE_SCREENS[label], seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is False, (label, lap.row(1))
    assert_looked_only(lap, 1)


def test_look_lap_takes_no_seen_record_of_another_destructive_row_for_this_one(tmp_path, monkeypatch, scope):
    """D1 (b): a record of Format seen opened opens Format alone: Delete, never seen, stays the owner's."""
    scope(BLANK)
    rows = [DESTRUCTIVE_SCREENS["Format"], DESTRUCTIVE_SCREENS["Delete"], ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["Format", "ISO"])
    assert lap.code in (0, None) and lap.sim.opened(0) and not lap.sim.opened(1), lap.keys


def test_look_lap_takes_no_record_that_says_the_row_changed_something(tmp_path, monkeypatch, scope):
    """D1 (b): "seen opened with nothing changed": a record whose latest open says it changed a record or acted is no
    licence (first_open.Seen's acting rows): the row stays the owner's."""
    scope(BLANK, UNRELATED)
    root = tmp_path / "cam"
    root.mkdir(parents=True)
    assert coverage.append_look(root.name, look(["Format"]))
    assert coverage.append_look(root.name, look(["Format"], result="changed", records_changed=["global:0x0001"]))
    lap = lap_with(tmp_path, monkeypatch, DESTRUCTIVE_SCREENS["Format"], seen_target=False)
    assert not lap.sim.opened(1) and lap.sim.opened(2), lap.keys


@pytest.mark.parametrize("label", ["Format", "Delete", "Setting Reset", "Reset Network Set.", "SSID/PW Reset"])
def test_drive_look_lap_presses_nothing_on_an_unseen_destructive_row(tmp_path, monkeypatch, scope, label):
    """D1 (b), kit/drive.py: --network --path <destructive, unseen> --press right sends no Right onto it, the cards
    statement given, and leaves no marker."""
    scope(BLANK, UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, DESTRUCTIVE_SCREENS[label], ISO], [label], ["right"],
                  extra=NETWORK)
    assert not d.sim.opened(1), (label, d.keys)
    assert not (d.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", ["Format", "Delete", "Setting Reset", "Reset Network Set.", "SSID/PW Reset"])
def test_drive_look_lap_says_an_unseen_destructive_row_is_the_owners_run(tmp_path, monkeypatch, scope, label):
    """D1 (b), kit/drive.py: and says the owner's run is the way (accepted: "--owner" in the console or the exit
    message, the flag that run takes)."""
    scope(BLANK, UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, DESTRUCTIVE_SCREENS[label], ISO], [label], ["right"],
                  extra=NETWORK)
    assert not d.sim.opened(1)
    assert "--owner" in (d.out + str(d.code)), (d.code, d.out[-1500:])


@pytest.mark.parametrize("label", ["Format", "Delete", "Setting Reset", "Reset Network Set.", "SSID/PW Reset"])
def test_drive_look_lap_opens_a_seen_destructive_row_and_sends_no_enter(tmp_path, monkeypatch, scope, label):
    """D1 (b) and D2, kit/drive.py: a destructive row seen opened opens on --network; an Enter asked for inside it is
    refused (no Enter reaches the camera), nothing chosen or answered."""
    scope()
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, DESTRUCTIVE_SCREENS[label], ISO], [label],
                  ["right", "enter:."], extra=NETWORK, seen=[label])
    assert d.sim.opened(1), (label, d.out[-1500:])
    assert "enter" not in d.keys and not d.sim.chosen and not d.sim.answered, d.keys


@pytest.mark.parametrize("bar", ["Version", "Format", "Initialize", "Reset Network Set.", "Forrnat"])
def test_look_lap_judges_the_lit_bar_not_the_page_model(tmp_path, monkeypatch, scope, bar):
    """D1: the page model says the cursor is on a seen ordinary row, the lit bar reads an owner-never row or an unseen
    destructive one (the menu shifted, a row appeared): no Right goes out on it."""
    scope(BLANK, UNRELATED)
    target = srow("Grid Line", "", bar=bar, options=("A", "B"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert not lap.sim.opened(1), (bar, lap.keys)
    assert lap.sim.opened(2), lap.keys


@pytest.mark.parametrize("bar", ["Language", "Access Authen. Info", "Display Serial Number", "Wi-Fi Connect"])
def test_look_lap_opens_a_lit_bar_it_has_not_seen_only_under_the_first_open_procedure(tmp_path, monkeypatch, scope,
                                                                                       bar):
    """D1: the page model's row is seen, but the lit bar reads another row, one this body has not seen opened: it is not
    opened as the seen row; either not opened, or opened with RESTORE_BY_HAND there (as its own first open)."""
    scope(BLANK, UNRELATED)
    target = srow("Grid Line", "", bar=bar, options=("A", "B"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert not lap.sim.opened(1) or lap.sim.marked_at_open(1) is True, (bar, lap.keys)


@pytest.mark.parametrize("label,option", [("Format", "Slot 1"), ("Setting Reset", "Camera Settings Reset"),
                                          ("Delete", "Multiple Img.")])
def test_a_decision_naming_options_of_a_destructive_row_chooses_nothing(tmp_path, monkeypatch, scope, label, option):
    """D2/D4: nothing about choosing gets looser: a "lifts": "network" decision naming an option of a destructive row
    (seen opened) lets no Enter go there (the run may stop before it connects, or refuse the Enter: either)."""
    scope({"date": DAY, "lifts": "network", "why": "x", "rows": [label], "options": {label: [option]}})
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, DESTRUCTIVE_SCREENS[label], ISO], [label],
                  ["right", f"enter:{re.escape(option)}"], extra=NETWORK, seen=[label])
    assert "enter" not in d.keys and not d.sim.chosen and not d.sim.answered, d.keys


def test_a_decision_naming_an_owner_never_row_opens_nothing(tmp_path, monkeypatch, scope):
    """D1 (a)/D4: a "lifts": "network" decision naming Version (with an option) opens it on no run."""
    scope({"date": DAY, "lifts": "network", "why": "x", "rows": ["Version"], "options": {"Version": ["OK"]}})
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow("Version", "", options=("OK",)), ISO], ["Version"],
                  ["right", "enter:OK"], extra=NETWORK, seen=["Version"])
    assert not d.sim.opened(1) and "enter" not in d.keys, d.keys


def test_look_lap_first_open_whose_check_finds_a_change_keeps_the_marker_and_exits_5(tmp_path, monkeypatch, scope):
    """D1: the first-open procedure is unchanged on a look lap: a record that differs after the row's first open keeps
    RESTORE_BY_HAND, the run exits EXIT_RESTORE_BY_HAND (5) and the row is not seen opened afterwards."""
    from camkit import first_open, session
    from exit_status import EXIT_RESTORE_BY_HAND
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    scope(BLANK)
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS["Language"], seen_target=False)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, lap.keys
    assert lap.code == EXIT_RESTORE_BY_HAND, (lap.code, lap.out[-1500:])
    assert (lap.root / RESTORE_BY_HAND).exists()
    assert not first_open.seen_record(lap.root.name).seen(["Language"])


# ====================================================================== D2: the look lap never chooses or answers

# Screens a look lap meets inside rows it opens (each row seen on the body so that it opens)
INSIDE_SCREENS = [
    srow("Language", "English", options=("English", "Français")),                                   # a list
    srow("Audio signals", "On", kind="dialog", options=("On", "Off")),                               # a carousel
    srow("AF Illuminator", "Auto", kind="checklist", options=("Auto", "Off")),                       # a checklist
    srow("Wi-Fi Connect", "Off", kind="dialog", lines=("Connect to the access point?",),             # a dialog asking
         options=("OK", "Cancel")),
    srow("Format", "", kind="unknown", lines=("Format Slot 1?", "All data will be deleted."),        # Format's question
         options=("Enter", "Cancel"), current=0),
    srow("Format", "", options=("Slot 1", "Slot 2")),                                                # Format's slots
    srow("Setting Reset", "", options=("Camera Settings Reset", "Initialize")),                      # a reset's targets
]


@pytest.mark.parametrize("target", INSIDE_SCREENS, ids=lambda r: f"{r['label']}-{r['kind']}-{len(r['lines'])}")
def test_drive_look_lap_sends_no_enter_inside_a_row_no_decision_names_options_of(tmp_path, monkeypatch, scope, target):
    """D2: with no decision naming an option, no Enter goes out inside any row a look lap opened (drive.py's
    "enter:REGEX" refused there): nothing chosen, nothing answered."""
    scope()
    for i, keys in enumerate((["right", "enter:."], ["right", "down", "enter:."], ["right", "ms_enter:."])):
        d = drive_run(tmp_path / str(i), monkeypatch, [DRIVE_MODE, target, ISO], [target["label"]], keys,
                      extra=NETWORK, seen=[target["label"]] if i == 0 else [])
        assert d.sim.opened(1), (target["label"], d.out[-1200:])
        assert not set(d.keys) & set(ENTERS) and not d.sim.chosen and not d.sim.answered, (keys, d.keys)


@pytest.mark.parametrize("target", INSIDE_SCREENS, ids=lambda r: f"{r['label']}-{r['kind']}-{len(r['lines'])}")
def test_crawl_look_lap_walks_inside_with_up_down_and_menu_alone(tmp_path, monkeypatch, scope, target):
    """D2: the crawl inside a row a look lap opened sends only up, down and MENU (no Right or Left onto a carousel's
    second axis or a panel, no Enter), and leaves with MENU."""
    scope()
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1)
    assert_looked_only(lap, 1)


def test_drive_look_lap_chooses_the_option_a_decision_names_and_no_other(tmp_path, monkeypatch, scope):
    """D2/D4: a dated network decision naming Off of Bluetooth Function lets Enter choose Off, as today; On, which it does
    not name, is never chosen."""
    scope(NETWORK_DECISION)
    row = srow("Bluetooth Function", "On", options=("On", "Off"), current=0)
    d = drive_run(tmp_path / "off", monkeypatch, [DRIVE_MODE, row, ISO], ["Bluetooth Function"],
                  ["right", "down", "enter:Off"], extra=NETWORK, seen=["Bluetooth Function"])
    assert d.sim.chosen == [("Bluetooth Function", "Off")], (d.keys, d.out[-1500:])
    d = drive_run(tmp_path / "on", monkeypatch, [DRIVE_MODE, row, ISO], ["Bluetooth Function"], ["right", "enter:On"],
                  extra=NETWORK)
    assert d.sim.chosen == [] and "enter" not in d.keys, d.keys


@pytest.mark.parametrize("label,option", [("Wi-Fi Connect", "On"), ("Airplane Mode", "On"), ("Language", "Français"),
                                          ("USB Connection Mode", "Mass Storage")])
def test_a_never_choose_row_is_never_chosen_whatever_a_decision_names(tmp_path, monkeypatch, scope, label, option):
    """D2: safety.never_choose's rows: a decision naming one of their options lets no Enter go there (the run may stop
    before it connects, or refuse the Enter inside: either is accepted)."""
    scope({"date": DAY, "lifts": "network", "why": "x", "rows": [label], "options": {label: [option]}})
    row = srow(label, "Off", options=("Off", option), current=1)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, row, ISO], [label], ["right", f"enter:{re.escape(option)}"],
                  extra=NETWORK, seen=[label])
    assert d.sim.chosen == [] and "enter" not in d.keys, d.keys


# ============================================================================================ D2: withholding

WITHHELD_ROWS = ["Access Authen. Info", "Password", "Area/Date/Time Setting", "Display Wi-Fi Info.",
                 "Display Serial Number"]       # version 2: IP Address Setting out (O-10), Display Wi-Fi Info. in (O-6)
SECRETS = (SECRET_USER, SECRET_PW, SECRET_IP, SECRET_MAC, SECRET_DATE, SECRET_SERIAL)      # never the link's own 192.0.2.10


def _run_files_text(run) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in run.dir.rglob("*.jsonl"))


def test_look_lap_keeps_and_prints_no_secret_and_asks_local_readers_only(tmp_path, monkeypatch, scope):
    """D2: a look lap over credentials, identity and address screens keeps none of their text in events.jsonl or
    rows.jsonl, prints none, set local readers only before the link opened, marks its folder for local readers, and
    keeps it owner-only."""
    scope()
    rows = [LOOK_OPENS[x] for x in WITHHELD_ROWS] + [ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=[*WITHHELD_ROWS, "ISO"])
    assert lap.code in (0, None), lap.out[-1500:]
    assert all(lap.sim.opened(i) for i in range(len(rows))), lap.keys
    kept = _run_files_text(lap.run) + lap.out
    for secret in SECRETS:
        assert secret not in kept, secret
    assert lap.local and lap.local[0] is True                  # local readers only, before the link opened
    assert vlm.LOCAL_ONLY is True
    assert (lap.run.dir / vlm.LOCAL_MARKER).exists()
    if os.name == "posix":
        assert stat.S_IMODE(lap.run.dir.stat().st_mode) & 0o077 == 0
        for f in ("events.jsonl", "rows.jsonl"):
            assert stat.S_IMODE((lap.run.dir / f).stat().st_mode) & 0o077 == 0, f


@pytest.mark.parametrize("label", CREDENTIAL_ROWS)
def test_look_lap_saves_a_credentials_screens_frames_black(tmp_path, monkeypatch, scope, label):
    """D2 (new): every frame saved while a credentials row a look lap opened is open is black: no frame file holds the
    user name or the password (the eyes save black while LiveCamera has them withhold, as camkit.frames does)."""
    scope()
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS[label], seen_target=True)
    assert lap.sim.opened(1), lap.keys
    for f in lap.run.dir.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            assert SECRET_PW.encode() not in data and SECRET_USER.encode() not in data, f.name


@pytest.mark.parametrize("label", WITHHELD_ROWS)
def test_drive_look_lap_keeps_and_prints_no_secret(tmp_path, monkeypatch, scope, label):
    """D2, kit/drive.py: an identity, address, serial number or credentials screen opened on --network with no decision:
    none of its values in the console, drive.jsonl or events.jsonl; local readers only, set before the link opened."""
    scope()
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, LOOK_OPENS[label], ISO], [label], ["right", "down", "menu"],
                  extra=NETWORK, seen=[label])
    assert d.sim.opened(1), d.out[-1500:]
    kept = d.out + _run_files_text(d.run)
    for secret in SECRETS:
        assert secret not in kept, secret
    assert d.local and d.local[0] is True


@pytest.mark.parametrize("label", CREDENTIAL_ROWS)
def test_drive_look_lap_withholds_a_credentials_screen(tmp_path, monkeypatch, scope, label):
    """D2, kit/drive.py: a credentials row opened on --network: no secret in drive.jsonl, events.jsonl, the console or
    any saved frame; local readers only; owner-only folder."""
    scope()
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, LOOK_OPENS[label], ISO], [label], ["right", "menu"],
                  extra=NETWORK, seen=[label])
    assert d.sim.opened(1), d.out[-1500:]
    everything = d.out + "".join(p.read_bytes().decode("utf-8", "replace") for p in d.run.dir.rglob("*") if p.is_file())
    assert SECRET_PW not in everything and SECRET_USER not in everything
    assert d.local and d.local[0] is True
    if os.name == "posix":
        assert stat.S_IMODE(d.run.dir.stat().st_mode) & 0o077 == 0


# ===================================================================================== D3: a value beside a row

# The lit bars the guard inventory found refused on the a1 II although their row is open (measure.py over
# editor/definitions/ILCE-1M2_fw4.00.json, regenerated on 043ea93): (row, value). The other two of the nineteen stay
# refused (O-3 decided (B): a value that is itself an action word never splits off): VALUE_BARS_WHOLE, tested below.
VALUE_BARS = [("Custom Key Setting", "Voice Memo hold"), ("Custom Key Setting", "Voice Memo toggle"),
              ("Custom Key/Dial Set.", "Audio Signal Volume"), ("Custom Key/Dial Set.", "Audio Signal(Shooting)"),
              ("Custom Key/Dial Set.", "SteadyShot"), ("Custom Key/Dial Set.", "SteadyShot Adjust."),
              ("Custom Key/Dial Set.", "SteadyShot Select"), ("Custom Key/Dial Set.", "Streaming"),
              ("Custom Key/Dial Set.", "Streaming Output/Stop"), ("Custom Key/Dial Set.", "Wireless Test Flash"),
              ("Custom Key/Dial Set.", "Write IPTC Info"), ("Fn Menu Settings", "Audio Signal Volume"),
              ("Fn Menu Settings", "Audio Signal(Shooting)"), ("Fn Menu Settings", "SteadyShot"),
              ("Fn Menu Settings", "SteadyShot Adjust."), ("Fn Menu Settings", "Voice Memo"),
              ("Fn Menu Settings", "Write IPTC Info")]
VALUE_BARS_WHOLE = [("File Number", "Reset"),
                    ("Px Proxy Rec. Settings", "9M 4:2:0 10bit (the reset value; no menu choice writes it)")]


@pytest.mark.parametrize("row,value", VALUE_BARS, ids=lambda x: str(x))
def test_ordinary_lap_opens_an_open_row_whose_bar_shows_a_known_value(tmp_path, monkeypatch, scope, row, value):
    """D3: an ordinary lap opens an open row whose lit bar is its label and a value the page model knows for it."""
    scope()
    target = srow(row, value, options=(value, "Off"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True, argv=())
    assert lap.code in (0, None), lap.out[-1500:]
    assert lap.sim.opened(1), (row, value, lap.row(1))


@pytest.mark.parametrize("sep", ["two lines", "one line"])
def test_drive_opens_an_open_row_whose_bar_shows_a_known_value(tmp_path, monkeypatch, scope, sep):
    """D3, kit/drive.py without --network: the same, the bar read as two lines or as one line with two spaces."""
    scope()
    row, value = "Custom Key Setting", "Voice Memo hold"
    target = srow(row, value, options=(value, "Off"), bar=f"{row}  {value}" if sep == "one line" else None)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, target, ISO], [row], ["right", "menu"], seen=[row])
    assert d.sim.opened(1), d.out[-1500:]


NEVER_OPEN_WITH_VALUES = [("Language", "English"), ("Audio signals", "On"), ("Wi-Fi Connect", "Off"),
                          ("Access Authen. Info", "Off"), ("AF Illuminator", "Auto"), ("SteadyShot", "On"),
                          ("Format", "Slot 1"), ("Version", "4.00"), ("Setting Reset", "Camera Settings Reset")]


@pytest.mark.parametrize("row,value", NEVER_OPEN_WITH_VALUES, ids=lambda x: str(x))
def test_ordinary_lap_keeps_a_never_open_row_refused_whatever_value_is_beside_it(tmp_path, monkeypatch, scope, row,
                                                                                   value):
    """D3: a row that IS never-open stays refused on an ordinary lap whatever known value stands beside it."""
    scope(BLANK)
    lap = lap_with(tmp_path, monkeypatch, srow(row, value, options=(value, "X")), seen_target=True, argv=())
    assert not lap.sim.opened(1), (row, value, lap.keys)


@pytest.mark.parametrize("row,value", [("Version", "4.00"), ("Format", "Slot 1"), ("Initialize", "Enter")],
                         ids=lambda x: str(x))
def test_look_lap_keeps_owner_never_and_unseen_destructive_rows_refused_with_a_value(tmp_path, monkeypatch, scope, row,
                                                                                      value):
    """D1 with D3: on a look lap an owner-never row, and a destructive row unseen, stay refused with a value beside."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow(row, value, options=(value, "X")), seen_target=row != "Format")
    assert not lap.sim.opened(1) and lap.sim.opened(2), (row, lap.keys)


def test_a_bar_whose_value_part_is_no_known_value_of_the_row_is_judged_whole(tmp_path, monkeypatch, scope):
    """D3: the page model knows Custom Key Setting's value as Off; the bar shows Voice Memo hold, which the kit does not
    know for it: judged whole, refused (as on main)."""
    scope()
    target = srow("Custom Key Setting", "Voice Memo hold", options=("Off",), scan_value="Off")
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True, argv=())
    assert not lap.sim.opened(1), lap.keys
    target = srow("Custom Key Setting", "Voice Memo hold", options=("Off",), scan_value="")
    lap = lap_with(tmp_path / "none", monkeypatch, target, seen_target=True, argv=())
    assert not lap.sim.opened(1), lap.keys


# A never-open row whose label is "a known label + a known value" of another row: the whole reading is judged too, and
# a refusal wins. Each case: the page (the row the cursor is on first, then the row the kit also knows), the bar there.
# HARD: the whole reading is a destructive row (or reads as one): refused on every lap. SOFT: another never-open row:
# refused on an ordinary lap; on a look lap, where that row would open under the first-open procedure, either not opened
# or opened with RESTORE_BY_HAND there (never as the seen row it splits into)
COLLISIONS = {
    "File Number + Reset vs File Number Reset": (
        [srow("File Number", "Reset", options=("Series", "Reset")), srow("File Number Reset", "")], None),
    "Del + ete vs Delete": ([srow("Del", "ete", options=("ete", "x")), srow("Delete", "")], None),
    "Del + ete read as one word": ([srow("Del", "ete", options=("ete", "x"), bar="Delete"), srow("Delete", "")], None),
    "Display + Serial Number vs Display Serial Number": (
        [srow("Display", "Serial Number", options=("Serial Number", "x")), srow("Display Serial Number", "")], None),
    "Camera Settings + Reset vs Camera Settings Reset": (
        [srow("Camera Settings", "Reset", options=("Reset", "Keep")), srow("Camera Settings Reset", "")], None),
    "Access Authen. + Info vs Access Authen. Info": (
        [srow("Access Authen.", "Info", options=("Info", "x")), srow("Access Authen. Info", "")], None),
    "Wi-Fi + Connect vs Wi-Fi Connect": (
        [srow("Wi-Fi", "Connect", options=("Connect", "x")), srow("Wi-Fi Connect", "")], None),
    "Slip: File Number read Fi1e Number + Reset": (
        [srow("File Number", "Reset", options=("Series", "Reset"), bar="Fi1e Number Reset"),
         srow("File Number Reset", "")], None),
}


SOFT_COLLISIONS = ("Display + Serial Number vs Display Serial Number", "Access Authen. + Info vs Access Authen. Info",
                   "Wi-Fi + Connect vs Wi-Fi Connect")


@pytest.mark.parametrize("case", list(COLLISIONS))
@pytest.mark.parametrize("argv", [(), ("--network",)], ids=["ordinary", "look-lap"])
def test_a_never_open_row_that_reads_as_another_rows_label_and_value_is_refused(tmp_path, monkeypatch, scope, case,
                                                                                argv):
    """D3: the bar on the first row (seen) reads, whole, as the label of a never-open row the kit knows (the second row,
    unseen): a refusal wins on an ordinary lap; on a look lap too where that row is destructive, and otherwise it opens
    only as that unseen row would, under the first-open procedure (RESTORE_BY_HAND at the Right)."""
    scope(BLANK, UNRELATED)
    rows, _ = COLLISIONS[case]
    lap = crawl_lap(tmp_path, monkeypatch, [*rows, ISO], argv=argv, seen=[rows[0]["label"], "ISO"])
    assert lap.sim.opened(2), lap.keys                                  # the lap ran
    if argv and case in SOFT_COLLISIONS:
        assert not lap.sim.opened(0) or lap.sim.marked_at_open(0) is True, (case, lap.keys, lap.row(0))
    else:
        assert not lap.sim.opened(0), (case, lap.keys, lap.row(0))
    if not argv or case not in SOFT_COLLISIONS:
        assert not lap.sim.opened(1), (case, lap.keys)


# ================================================================================ D3: ordinary runs, mechanically

EXPECTED = HERE / "ordinary_expected.json"


def _ordinary_verdicts(labels_or_bars, kind, known_groups=()):
    """main's entry points for an ordinary run (no --network, no --owner, no --allow, no decision), each True where it
    refuses or skips: crawl: camkit.crawl's skip of a page model row (left_unopened); drive_path: drive.py's refusal
    of a --path label before it connects (allow_refused, never_open); prover: proving.jobs's never-open check
    (path_refused); group: the group column's (group_refused); bar: LiveCamera's opening check of a lit bar
    (live.open_refused); drive_bar: drive.py's of a Right on it (press_refused)."""
    from camkit import crawl
    import drive
    out = {}
    if kind == "label":
        for v in labels_or_bars:
            out[v] = "".join("1" if x else "0" for x in (
                crawl.left_unopened({"breadcrumb": CRUMB}, {"label": v}),
                bool(safety.allow_refused(v) or safety.never_open(v)),
                bool(safety.path_refused([v])),
                bool(safety.group_refused(v, known_groups))))
    else:
        for b in labels_or_bars:
            out[b] = "".join("1" if x else "0" for x in (bool(live.open_refused(b)),
                                                          bool(drive.press_refused("right", b, "", "submenu"))))
    return out


def ordinary_inputs():
    """Every row label of the a1 II's definition (its menu and every setting's row path) and of
    data/ILCE-1M2_fw4.00/ (the coverage ledger's paths, the Help Guide's menu items, the seen facts' paths, the settings
    reset's names), each as written, one space dropped, every space dropped and with one OCR slip; and each label's own
    values beside it (the definition's), with each of those readings of the label."""
    d = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    data = ROOT / "data" / "ILCE-1M2_fw4.00"
    labels = {m["label"] for m in d.get("menu") or [] if isinstance(m.get("label"), str)}
    values = {}
    for s in d.get("settings") or []:
        row = [x for x in s.get("row") or [] if isinstance(x, str)]
        labels |= set(row)
        if row:
            values.setdefault(row[-1], set()).update(str(v[1]) for v in s.get("values") or []
                                                     if isinstance(v, list) and len(v) > 1 and isinstance(v[1], str))
    cov = json.loads((data / "coverage_ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    labels |= {x for r in cov.get("rows") or [] for x in r.get("path") or [] if isinstance(x, str)}
    seen = json.loads((data / "seen_ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    labels |= {x for r in seen.get("facts") or [] for x in r.get("path") or [] if isinstance(x, str)}
    for line in (data / "help_guide_menu_ILCE-1M2_fw4.00.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line).get("item")
        if isinstance(item, str):
            labels.add(item)
    reset = json.loads((data / "settings_reset_ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    labels |= {r.get("name") for r in (reset.get("records") or {}).values() if isinstance(r.get("name"), str)}
    labels = sorted(x for x in labels if x.strip())
    groups = sorted({m["group"] for m in d.get("menu") or [] if isinstance(m.get("group"), str)})
    variants = {}
    for x in labels:
        variants[x] = list(dict.fromkeys([x, x.replace(" ", "", 1), x.replace(" ", ""), slip(x)]))
    bars = set()
    for x in labels:
        for v in variants[x]:
            bars.add(v)
            for val in sorted(values.get(x, ())):
                bars.add(f"{v}  {val}")
    return labels, variants, sorted(bars), groups


def make_ordinary_expected(path=EXPECTED):
    """Write main's verdicts (run once on 043ea93's code; never rewrite them from the code under test)."""
    labels, variants, bars, groups = ordinary_inputs()
    flat = sorted({v for vs in variants.values() for v in vs})
    doc = {"about": "main's (043ea93) ordinary-run verdicts, 1 = refused or skipped. labels: crawl skip, drive.py "
                    "--path refusal, prover path_refused, group column group_refused. bars: LiveCamera open_refused, "
                    "drive.py press_refused on Right.",
           "groups": groups, "labels": _ordinary_verdicts(flat, "label", groups), "bars": _ordinary_verdicts(bars, "bar"),
           "groups_refused": {g: bool(safety.group_refused(g, groups)) for g in groups}}
    path.write_text(json.dumps(doc, indent=0, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return doc


@pytest.fixture(scope="module")
def expected():
    if not EXPECTED.exists():
        pytest.fail(f"{EXPECTED.name} is missing: copy it beside this file")
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


def test_ordinary_labels_are_refused_or_skipped_exactly_as_on_main(expected):
    """D3: for every a1 II row label in four readings, an ordinary crawl's skip, drive.py's --path refusal, a prover's
    path_refused and the group column's refusal are as on main."""
    got = _ordinary_verdicts(list(expected["labels"]), "label", expected["groups"])
    diff = {k: (expected["labels"][k], got[k]) for k in expected["labels"] if got[k] != expected["labels"][k]}
    assert not diff, f"{len(diff)} labels judged otherwise than on main, e.g. {list(diff.items())[:12]}"


def test_ordinary_bars_without_known_values_are_judged_as_on_main(expected):
    """D3: every a1 II lit bar (a label in four readings, alone and with each of its own values beside it), judged with
    no values given (so no split is possible), is refused or let through by LiveCamera and drive.py as on main."""
    got = _ordinary_verdicts(list(expected["bars"]), "bar")
    diff = {k: (expected["bars"][k], got[k]) for k in expected["bars"] if got[k] != expected["bars"][k]}
    assert not diff, f"{len(diff)} bars judged otherwise than on main, e.g. {list(diff.items())[:12]}"


ORDINARY_E2E = ["Language", "Wi-Fi Connect", "Access Authen. Info", "Audio signals", "Display Serial Number", "Format",
                "Version", "Setting Reset", "Display Wi-Fi Info.", "Rating"]


def test_ordinary_lap_still_skips_every_never_open_row_seen_or_not(tmp_path, monkeypatch, scope):
    """D3: an ordinary lap (no --network), the cards statement given and every row recorded seen, opens none of the
    never-open rows: nothing pressed on any (as on main)."""
    scope(BLANK)
    rows = [srow(x, "", options=("A", "B")) for x in ORDINARY_E2E[:8]] + [ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, seen=[*ORDINARY_E2E, "ISO"])
    assert lap.code in (0, None), lap.out[-1500:]
    for i in range(len(rows) - 1):
        assert not lap.sim.opened(i), (rows[i]["label"], lap.keys)
    assert lap.sim.opened(len(rows) - 1)


@pytest.mark.parametrize("label", ORDINARY_E2E)
def test_ordinary_drive_still_refuses_a_never_open_path_before_it_connects(tmp_path, monkeypatch, scope, label):
    """D3: drive.py without --network refuses a never-open --path before anything is pressed (as on main)."""
    scope(BLANK)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow(label, "", options=("A", "B")), ISO], [label], ["right"],
                  seen=[label])
    assert d.keys == [] and d.code not in (0, None), (d.code, d.keys)


# ============================================================================================== regressions

QUESTIONS = ["Clear registered faces? OK Cancel", "Format Slot 1? All data will be deleted.", "Initialize all settings?",
             "Proceed with the operation?", "初期化しますか？", "Start the slide show?"]


@pytest.mark.parametrize("question", QUESTIONS)
@pytest.mark.parametrize("argv", [(), ("--network",)], ids=["ordinary", "look-lap"])
def test_enter_on_a_question_is_refused_on_a_look_lap_and_everywhere(tmp_path, monkeypatch, scope, question, argv):
    """Regression (the Enter check of 44c1287): a seen ordinary row whose Right brings up a question: Enter, lit on its
    Enter or OK button, never reaches the camera, on an ordinary run and on a look lap alike; the row did open."""
    scope(UNRELATED)
    for i, (kind, buttons) in enumerate((("unknown", ("Enter", "Cancel")), ("dialog", ("OK", "Cancel")),
                                         ("notice", ("OK", "Cancel")))):
        row = srow("Grid Line", "", kind=kind, lines=(question,), options=buttons, current=0)
        d = drive_run(tmp_path / str(i), monkeypatch, [DRIVE_MODE, row, ISO], ["Grid Line"], ["right", "enter:."],
                      extra=argv, seen=["Grid Line"] if i == 0 else [])
        assert d.sim.opened(1), (kind, d.out[-1200:])
        assert "enter" not in d.keys and not d.sim.answered, (kind, d.keys)


def test_a_dated_network_decision_still_reads_and_names_its_options():
    """D4: a decision with "lifts": "network" stays valid: network_decided takes it, network_options gives its options."""
    rows, refusals = safety.network_decided({"decisions": [NETWORK_DECISION]})
    assert rows == {"Bluetooth Function": DAY} and refusals == []
    assert safety.network_options({"decisions": [NETWORK_DECISION]}) == {"Bluetooth Function": ["Off"]}


def test_the_group_column_judges_groups_as_on_main(expected):
    """Regression: the group jump's refusal of a group's name (group_refused) is part of the labels' verdicts above;
    here the never-open groups the a1 II's group column holds stay refused, the others not."""
    groups = expected["groups"]
    got = {g: bool(safety.group_refused(g, groups)) for g in groups}
    assert got == expected["groups_refused"]
    assert safety.group_refused("FTP Transter", groups) and safety.group_refused("Accessibility", groups)


# ======================================================== version 2: the open cases, as the coordinator decided them

# O-1, O-2: sound, light and motion rows open on a look lap, to look only (D1 (a) is the OWNER_NEVER list); the Screen
# Reader's row does not (decision 3's own route)
SOUND_LIGHT_MOTION = {
    "Pre-AF": srow("Pre-AF", "Off"),
    "Eye-Start AF": srow("Eye-Start AF", "Off"),
    "SteadyShot": srow("SteadyShot", "On"),
    "Shutter When Pwr OFF": srow("Shutter When Pwr OFF", "Off"),
    "Volume Settings": srow("Volume Settings", "", options=("Volume 1", "Volume 2")),
    "Video Light Mode": srow("Video Light Mode", "Power Link", options=("Power Link", "REC Link")),
}


@pytest.mark.parametrize("label", list(SOUND_LIGHT_MOTION))
def test_v2_look_lap_opens_a_seen_sound_light_or_motion_row_to_look_only(tmp_path, monkeypatch, scope, label):
    """O-1, O-2: a sound, light or motion row seen on this body opens on a look lap with Right, no marker, up, down and
    MENU alone inside, nothing chosen."""
    scope()
    lap = lap_with(tmp_path, monkeypatch, SOUND_LIGHT_MOTION[label], seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is False, (label, lap.row(1))
    assert_looked_only(lap, 1)


@pytest.mark.parametrize("label", list(SOUND_LIGHT_MOTION))
def test_v2_look_lap_opens_an_unseen_sound_light_or_motion_row_under_the_procedure(tmp_path, monkeypatch, scope,
                                                                                    label):
    """O-1, O-2: the same row unseen opens under the first-open procedure (RESTORE_BY_HAND at its Right)."""
    scope(BLANK)
    lap = lap_with(tmp_path, monkeypatch, SOUND_LIGHT_MOTION[label], seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, (label, lap.row(1))
    assert not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", ["Pre-AF", "SteadyShot"])
def test_v2_drive_look_lap_opens_a_motion_row(tmp_path, monkeypatch, scope, label):
    """O-2, kit/drive.py: --network opens a seen motion row, looks, chooses nothing."""
    scope()
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, SOUND_LIGHT_MOTION[label], ISO], [label],
                  ["right", "down", "menu"], extra=NETWORK, seen=[label])
    assert d.sim.opened(1), d.out[-1500:]
    assert set(d.sim.inside(1)) <= LOOK_KEYS and not d.sim.chosen and "enter" not in d.keys


@pytest.mark.parametrize("seen", [False, True], ids=["unseen", "seen-recorded"])
def test_v2_look_lap_never_opens_the_screen_reader(tmp_path, monkeypatch, scope, seen):
    """O-2: the Screen Reader's row is never opened by a look lap, in any reading, the cards statement given and even
    recorded seen; the lap goes on."""
    scope(BLANK, UNRELATED)
    readings = readings_of("Screen Reader")
    rows = page_of(readings) + [ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["ISO", *(readings if seen else [])])
    assert all(not lap.sim.opened(i) for i in range(len(readings))), lap.keys
    assert lap.sim.opened(len(rows) - 1), lap.keys


def test_v2_drive_look_lap_never_opens_the_screen_reader(tmp_path, monkeypatch, scope):
    """O-2, kit/drive.py: --network --path "Screen Reader" --press right sends no Right onto it, seen or not."""
    scope(BLANK, UNRELATED)
    for i, seen in enumerate(([], ["Screen Reader"])):
        d = drive_run(tmp_path / str(i), monkeypatch, [DRIVE_MODE, srow("Screen Reader", "Off"), ISO],
                      ["Screen Reader"], ["right"], extra=NETWORK, seen=seen)
        assert not d.sim.opened(1), d.keys


# O-3: a value that is itself an action word never splits off: the bar is judged whole, refused as on main
@pytest.mark.parametrize("row,value", VALUE_BARS_WHOLE, ids=lambda x: str(x)[:20])
@pytest.mark.parametrize("argv", [(), ("--network",)], ids=["ordinary", "look-lap"])
def test_v2_a_value_that_is_an_action_word_never_splits_off(tmp_path, monkeypatch, scope, row, value, argv):
    """O-3 (B): "File Number" + "Reset" and the Proxy value whose name says "reset" (the inventory's two others of the
    19): the row is seen and the page model knows the value, yet the bar is judged whole and nothing is pressed on it,
    on an ordinary lap and on a look lap."""
    scope(BLANK, UNRELATED)
    target = srow(row, value, options=(value, "Off"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True, argv=argv)
    assert not lap.sim.opened(1), (row, value, lap.keys)
    assert lap.sim.opened(2), lap.keys


def test_v2_drive_judges_a_value_that_is_an_action_word_whole(tmp_path, monkeypatch, scope):
    """O-3 (B), kit/drive.py without --network: --path "File Number" --press right, the bar "File Number  Reset":
    no Right."""
    scope(BLANK)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow("File Number", "Reset", options=("Series", "Reset")), ISO],
                  ["File Number"], ["right"], seen=["File Number"])
    assert not d.sim.opened(1), d.keys


# O-4: the look lap's own checks also read a 1 between letters as i (ordinary runs unchanged in this step)
I_SLIPS_OWNER_NEVER = ["In1tialize", "1nitialize", "Clean1ng Mode", "Pixel Mapp1ng", "Vers1on", "Anti-dust Funct1on",
                       "Preset Focus/Zoom"]
I_SLIPS_DESTRUCTIVE = ["Sett1ng Reset", "Ser1es Counter Reset", "Camera Sett1ngs Reset", "Forced F1le Number Reset"]


@pytest.mark.parametrize("seen", [False, True], ids=["unseen", "seen-recorded"])
def test_v2_look_lap_never_opens_an_owner_never_row_read_with_1_for_i(tmp_path, monkeypatch, scope, seen):
    """O-4: OWNER_NEVER's rows read with a 1 for an i are never opened by a look lap (on main never_open and owner_never
    both miss "In1tialize", "1nitialize", "Clean1ng Mode", "Pixel Mapp1ng", "Vers1on"), seen-recorded or not."""
    scope(BLANK, UNRELATED)
    rows = page_of(I_SLIPS_OWNER_NEVER) + [ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["ISO", *(I_SLIPS_OWNER_NEVER if seen else [])])
    opened = [r["label"] for i, r in enumerate(rows[:-1]) if lap.sim.opened(i)]
    assert not opened, opened
    assert lap.sim.opened(len(rows) - 1), lap.keys


@pytest.mark.parametrize("label", I_SLIPS_DESTRUCTIVE)
def test_v2_look_lap_presses_nothing_on_an_unseen_destructive_row_read_with_1_for_i(tmp_path, monkeypatch, scope,
                                                                                     label):
    """O-4: a destructive row read with a 1 for an i is still destructive: unseen, nothing pressed, no marker."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow(label, "", options=("A", "B")), seen_target=False)
    assert_lap_went_on(lap)
    assert_skipped_untouched(lap, 1)
    assert not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("bar", ["In1tialize", "Vers1on", "Clean1ng Mode", "Sett1ng Reset"])
def test_v2_look_lap_refuses_a_lit_bar_read_with_1_for_i(tmp_path, monkeypatch, scope, bar):
    """O-4: the lit bar on a seen ordinary row reads an owner-never or destructive row with a 1 for an i: no Right."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow("Grid Line", "", bar=bar, options=("A", "B")), seen_target=True)
    assert not lap.sim.opened(1), (bar, lap.keys)
    assert lap.sim.opened(2), lap.keys


@pytest.mark.parametrize("label", ["Vers1on", "In1tialize"])
def test_v2_drive_look_lap_refuses_an_owner_never_path_read_with_1_for_i(tmp_path, monkeypatch, scope, label):
    """O-4, kit/drive.py: --network --path <owner-never row with a 1 for an i> --press right: no Right, seen or not."""
    scope(BLANK, UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow(label, "", options=("A", "B")), ISO], [label], ["right"],
                  extra=NETWORK, seen=[label])
    assert not d.sim.opened(1), d.keys


# O-6: the look lap's crawl opens address screens, MENU alone inside, field names alone kept
ADDRESS_ROWS = ["Display Wi-Fi Info.", "Display Wired LAN Info.", "Disp Device Address"]


@pytest.mark.parametrize("label", ADDRESS_ROWS)
def test_v2_look_lap_opens_an_address_screen_and_presses_menu_alone_inside(tmp_path, monkeypatch, scope, label):
    """O-6: a seen address screen opens on a look lap's crawl; inside it nothing but MENU goes out (a list there is not
    walked), and none of its addresses is kept or printed."""
    scope()
    target = srow(label, "", options=("MAC Address", SECRET_MAC, "IP Address", SECRET_IP))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.inside(1) == ["menu"], (label, lap.sim.inside(1))
    kept = _run_files_text(lap.run) + lap.out
    assert SECRET_MAC not in kept and SECRET_IP not in kept


# O-7: inside a credentials row a look lap opened, MENU alone
CREDENTIAL_LISTS = {"Access Authen. Info": srow("Access Authen. Info", "", options=("Off", "On"),
                                                lines=("User Name", SECRET_USER, "Password", SECRET_PW)),
                    "Password": srow("Password", "", options=("Show", "Hide"), lines=(SECRET_PW,))}


@pytest.mark.parametrize("label", CREDENTIAL_ROWS)
def test_v2_look_lap_presses_menu_alone_inside_a_credentials_row(tmp_path, monkeypatch, scope, label):
    """O-7: a credentials row a look lap opened, even one that shows a list, gets MENU alone from its opening."""
    scope()
    lap = lap_with(tmp_path, monkeypatch, CREDENTIAL_LISTS[label], seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.inside(1) == ["menu"], (label, lap.sim.inside(1))


@pytest.mark.parametrize("label", CREDENTIAL_ROWS)
def test_v2_drive_look_lap_presses_menu_alone_inside_a_credentials_row(tmp_path, monkeypatch, scope, label):
    """O-7, kit/drive.py: inside a credentials row --network opened, a Down asked for is refused; only MENU goes out."""
    scope()
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, CREDENTIAL_LISTS[label], ISO], [label],
                  ["right", "down", "menu"], extra=NETWORK, seen=[label])
    assert d.sim.opened(1) and d.sim.inside(1) == ["menu"], (label, d.sim.inside(1), d.out[-1200:])


# O-8: "values": "logged" is honoured only on an --owner run: a look lap blanks whatever a decision says
OWNER_LOGGED = {"date": DAY, "lifts": "owner", "why": "the owner: log the values", "rows": ["Access Authen. Info"],
                "values": "logged"}
NETWORK_LOGGED = {"date": DAY, "lifts": "network", "why": "the owner: log the values", "rows": ["Access Authen. Info"],
                  "values": "logged"}


def _no_secret_in_files(run):
    for f in run.dir.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            assert SECRET_PW.encode() not in data and SECRET_USER.encode() not in data, f.name


def test_v2_look_lap_blanks_a_credentials_row_whatever_a_decision_says_of_values(tmp_path, monkeypatch, scope):
    """O-8 (2): an owner decision saying "values": "logged" for Access Authen. Info does not reach a look lap: the row
    opens (seen) and no frame or file of the run holds its user name or password. A network decision saying so either
    stops the run before it connects or is ignored alike."""
    scope(OWNER_LOGGED)
    lap = lap_with(tmp_path / "owner", monkeypatch, LOOK_OPENS["Access Authen. Info"], seen_target=True)
    assert lap.sim.opened(1), lap.out[-1500:]
    _no_secret_in_files(lap.run)
    scope(NETWORK_LOGGED)
    lap = lap_with(tmp_path / "network", monkeypatch, LOOK_OPENS["Access Authen. Info"], seen_target=True)
    assert lap.keys == [] or lap.sim.opened(1), lap.keys
    _no_secret_in_files(lap.run)


def test_v2_drive_look_lap_blanks_a_credentials_row_whatever_a_decision_says_of_values(tmp_path, monkeypatch, scope):
    """O-8 (2), kit/drive.py --network (no --owner): the owner decision's "values": "logged" is not honoured: no secret
    in any file of the run (drive.jsonl and the frames among them) nor in the console."""
    scope(OWNER_LOGGED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, LOOK_OPENS["Access Authen. Info"], ISO], ["Access Authen. Info"],
                  ["right", "menu"], extra=NETWORK, seen=["Access Authen. Info"])
    assert d.sim.opened(1), d.out[-1500:]
    _no_secret_in_files(d.run)
    assert SECRET_PW not in d.out and SECRET_USER not in d.out


# O-9: every row the owner route blanks (safety.BLANKED's classes on 043ea93: credentials, the serial-number screen,
# the closed identity rows) has its frames saved black on a look lap. Each screen shows a line no other screen shows.
BLANKED_ROWS = ["Access Authen. Info", "Password", "Wi-Fi Direct Info.", "Display Serial Number", "Edit Device Name",
                "Copyright Info", "Language", "Area/Date/Time Setting", "USB Connection Mode", "Server Setting"]


@pytest.mark.parametrize("label", BLANKED_ROWS)
def test_v2_look_lap_saves_black_every_frame_of_a_row_the_owner_route_blanks(tmp_path, monkeypatch, scope, label):
    """O-9 (1): while such a row a look lap opened is open, no saved frame holds its screen (the eyes save black)."""
    scope()
    marker = "SCREEN-ONLY-TEXT-7731"
    target = srow(label, "", options=("Off", "On"), lines=(marker,))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert lap.sim.opened(1), (label, lap.out[-1500:])
    for f in lap.run.dir.rglob("*"):
        if f.is_file():
            assert marker.encode() not in f.read_bytes(), (label, f.name)


# O-10: D1 (c): a row safety.acts_on_open names is never opened by a look lap, seen or not: the owner's own run
ACTS_ON_OPEN_ROWS = ["WPS Push", "WPS PIN", "Pairing", "Access Point Set.", "Select on Cam & Send",
                     "Smartphone Connection", "Cloud Connection", "Network Streaming", "Tethering Connection",
                     "FTP Function", "FTP Transfer", "Send", "Create New Folder", "IP Address Setting",
                     "Forced File Number Reset"]


@pytest.mark.parametrize("label", ACTS_ON_OPEN_ROWS)
@pytest.mark.parametrize("seen", [False, True], ids=["unseen", "seen-recorded"])
def test_v2_look_lap_presses_nothing_on_a_row_whose_opening_acts(tmp_path, monkeypatch, scope, label, seen):
    """O-10, D1 (c): nothing pressed on it, no marker, the lap goes on: unseen, and with a clean seen record too."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow(label, "", options=("A", "B")), seen_target=seen)
    assert_lap_went_on(lap)
    assert_skipped_untouched(lap, 1)
    assert not (lap.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", ACTS_ON_OPEN_ROWS)
def test_v2_look_lap_says_a_row_whose_opening_acts_is_the_owners_run(tmp_path, monkeypatch, scope, label):
    """O-10: the skipped row's outcome points to the owner's own run, seen or not (accepted: "owner" in the outcome)."""
    scope(BLANK, UNRELATED)
    for i, seen in enumerate((False, True)):
        lap = lap_with(tmp_path / str(i), monkeypatch, srow(label, "", options=("A", "B")), seen_target=seen)
        assert_skipped_untouched(lap, 1)
        assert "owner" in lap.outcome(1).lower(), (seen, lap.row(1))


@pytest.mark.parametrize("label", ["WPS Push", "Pairing", "Send", "Create New Folder", "IP Address Setting"])
def test_v2_drive_look_lap_never_opens_a_row_whose_opening_acts(tmp_path, monkeypatch, scope, label):
    """O-10, kit/drive.py: --network --path <row whose opening acts> --press right: no Right, seen or not."""
    scope(BLANK, UNRELATED)
    for i, seen in enumerate(([], [label])):
        d = drive_run(tmp_path / str(i), monkeypatch, [DRIVE_MODE, srow(label, "", options=("A", "B")), ISO], [label],
                      ["right"], extra=NETWORK, seen=seen)
        assert not d.sim.opened(1), (label, seen, d.keys)
        assert not (d.root / RESTORE_BY_HAND).exists()


@pytest.mark.parametrize("label", ["WPS Push", "Create New Folder", "IP Address Setting"])
def test_v2_drive_look_lap_says_a_row_whose_opening_acts_is_the_owners_run(tmp_path, monkeypatch, scope, label):
    """O-10, kit/drive.py: and says the owner's run is the way (accepted: "--owner" in the console or exit message)."""
    scope(BLANK, UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, srow(label, "", options=("A", "B")), ISO], [label], ["right"],
                  extra=NETWORK, seen=[label])
    assert not d.sim.opened(1)
    assert "--owner" in (d.out + str(d.code)), (d.code, d.out[-1500:])


# O-11: a --network run with no reviewed scope stops before connecting, saying how a scope is started
def test_v2_a_look_lap_with_no_reviewed_scope_stops_before_connecting(tmp_path, monkeypatch, scope):
    """O-11 (2): no scope file: crawl_run.py --network and drive.py --network press nothing and exit non-zero."""
    assert not scope.file.exists()
    lap = lap_with(tmp_path / "crawl", monkeypatch, LOOK_OPENS["Language"], seen_target=True)
    assert lap.keys == [] and lap.code not in (0, None), (lap.code, lap.keys)
    d = drive_run(tmp_path / "drive", monkeypatch, [DRIVE_MODE, ISO], ["ISO"], ["right"], extra=NETWORK, seen=["ISO"])
    assert d.keys == [] and d.code not in (0, None), (d.code, d.keys)


def test_v2_a_look_lap_with_no_reviewed_scope_says_how_one_is_started(tmp_path, monkeypatch, scope):
    """O-11: its message says how a scope is started: the owner's kit/tools/owner_statement.py cards (accepted:
    "owner_statement.py" in the exit message or the console)."""
    lap = lap_with(tmp_path / "crawl", monkeypatch, LOOK_OPENS["Language"], seen_target=True)
    assert "owner_statement.py" in f"{lap.code} {lap.out}", (lap.code, lap.out[-800:])
    d = drive_run(tmp_path / "drive", monkeypatch, [DRIVE_MODE, ISO], ["ISO"], ["right"], extra=NETWORK, seen=["ISO"])
    assert "owner_statement.py" in f"{d.code} {d.out}", (d.code, d.out[-800:])


# O-12: D1 (b) is a row main never opens whose name holds format, delete or reset: ordinary rows with a card word open
@pytest.mark.parametrize("label", ["File Format", "Delete confirm."])
def test_v2_look_lap_takes_an_ordinary_row_with_a_card_word_for_no_destructive_row(tmp_path, monkeypatch, scope, label):
    """O-12 (1): an unseen "File Format" or "Delete confirm." opens on a look lap under the first-open procedure, as on
    any lap."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow(label, "RAW", options=("RAW", "JPEG")), seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, (label, lap.row(1))


# O-13: a destructive row recorded seen whose lit bar reads with a slip is not that seen row
@pytest.mark.parametrize("bar", ["Forrnat", "F0rmat", "Fоrmat"])
def test_v2_look_lap_takes_no_slipped_bar_for_the_seen_destructive_row(tmp_path, monkeypatch, scope, bar):
    """O-13: Format is recorded seen; its lit bar reads "Forrnat" (or another slip): unseen and destructive, no Right."""
    scope(BLANK, UNRELATED)
    target = srow("Format", "", bar=bar, options=("Slot 1", "Slot 2"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert not lap.sim.opened(1), (bar, lap.keys)
    assert lap.sim.opened(2), lap.keys


# O-14: the never-open list's own whole names count for D3's whole-reading override, known to the page model or not
WHOLE_NAMES = {"Camera Settings + Reset": ("Camera Settings", "Reset"), "Factory + Reset": ("Factory", "Reset"),
               "Series Counter + Reset": ("Series Counter", "Reset"),
               "Display + Serial Number": ("Display", "Serial Number")}


@pytest.mark.parametrize("case", list(WHOLE_NAMES))
@pytest.mark.parametrize("argv", [(), ("--network",)], ids=["ordinary", "look-lap"])
def test_v2_a_bar_that_reads_whole_as_a_never_open_name_of_the_list_is_refused(tmp_path, monkeypatch, scope, case,
                                                                                argv):
    """O-14 (2): the row (seen) and its value are known, no row of the whole name is: the bar reads whole as an action
    the never-open list names, so it is refused (on a look lap the non-destructive Display Serial Number may open only as
    its own unseen row would, with RESTORE_BY_HAND there)."""
    scope(BLANK, UNRELATED)
    row, value = WHOLE_NAMES[case]
    lap = lap_with(tmp_path, monkeypatch, srow(row, value, options=(value, "Keep")), seen_target=True, argv=argv)
    assert lap.sim.opened(2), lap.keys
    if argv and row == "Display":
        assert not lap.sim.opened(1) or lap.sim.marked_at_open(1) is True, lap.keys
    else:
        assert not lap.sim.opened(1), (case, lap.keys)


# O-15: --panels with --network is refused before connecting
def test_v2_panels_with_network_is_refused_before_connecting(tmp_path, monkeypatch, scope):
    """O-15: crawl_run.py --network --panels presses nothing and exits non-zero (a decision in the scope, so main would
    run it)."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, LOOK_OPENS["Language"], seen_target=True, argv=("--network", "--panels"))
    assert lap.keys == [] and lap.code not in (0, None), (lap.code, lap.keys)


# ============================================================== boxed options alone ("buttons", 2026-11-16)

# camkit.screen's "buttons" (the a1 II's Image Index: a title, two to four boxed options, one lit), read as no known kind
# until 2026-11-16, when its first open stopped with RESTORE_BY_HAND and left the screen open
BOXES = srow("Papa Boxes", "", kind="buttons", options=("Nine Tiles", "Thirty Tiles"))


def test_drive_first_open_goes_on_over_boxed_options(tmp_path, monkeypatch, scope):
    """kit/drive.py, an ordinary run: an unseen row's Right (RESTORE_BY_HAND there) that shows boxed options alone is a
    screen the first open reads: MENU alone inside, nothing chosen or answered, the check clean, the marker gone, the
    row seen opened from then on, exit 0."""
    import camkit
    from camkit import first_open, paths
    scope(BLANK)
    monkeypatch.setattr(first_open, "other_body", lambda link, camera: "")
    root = paths.runs_top() / TEST_CAMERA
    monkeypatch.setattr(camkit, "RUNS", paths.runs_top())
    assert not first_open.seen_record().seen([BOXES["label"]])
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, BOXES, ISO], [BOXES["label"]], ["right"], root=root)
    assert d.code in (0, None), d.out[-1500:]
    assert d.sim.opened(1) and d.sim.marked_at_open(1) is True, d.out[-1500:]
    assert d.sim.inside(1) == ["menu"] and not d.sim.chosen and not d.sim.answered, d.sim.inside(1)
    assert not (root / RESTORE_BY_HAND).exists()
    assert d.line["first_open"] is True and d.line["screens"][0]["kind"] == "buttons", d.line
    assert first_open.seen_record().seen([BOXES["label"]])


@pytest.mark.parametrize("press", ["enter:Tiles", "enter!:Tiles"])
@pytest.mark.parametrize("lit", [True, False], ids=["lit-read", "nothing-lit"])
def test_drive_sends_no_enter_on_boxed_options_plain_or_vouched(tmp_path, monkeypatch, scope, press, lit):
    """A seen row whose Right shows boxed options alone: Enter never reaches the camera, plain or vouched, its lit box
    read or not (a vouch lifts an unreadable lit text alone, never the shape check: a question can be drawn so), on an
    ordinary run as on a screen of no known kind."""
    scope(UNRELATED)
    row = BOXES if lit else {**BOXES, "options": []}
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, row, ISO], [row["label"]], ["right", press], seen=[row["label"]])
    assert d.sim.opened(1), d.out[-1500:]
    assert "enter" not in d.keys and not d.sim.answered and not d.sim.chosen, d.keys


def test_drive_sends_enter_on_boxed_options_only_where_confirm_names_the_screen(tmp_path, monkeypatch, scope):
    """The one way past for an ordinary run, as on a screen of no known kind: --confirm giving the screen's whole text
    lets one Enter go on it."""
    scope(UNRELATED)
    d = drive_run(tmp_path, monkeypatch, [DRIVE_MODE, BOXES, ISO], [BOXES["label"]], ["right", "enter:Tiles"],
                  extra=["--confirm", "Papa Boxes Nine Tiles Thirty Tiles"], seen=[BOXES["label"]])
    assert d.keys.count("enter") == 1 and d.sim.answered == [("Papa Boxes", "Nine Tiles")], (d.keys, d.out[-1500:])


if __name__ == "__main__":
    make_ordinary_expected()
    print(f"wrote {EXPECTED}")
