"""The engineering review of 2026-11-18, finding 10 (track 2's B2 and B10, proposal P2): one step after OK,
proving.commit.after_ok, says what the camera did with a choice, and prove_row, prove_axis_row, pass 3's switch and the
provers that pressed OK and wrote "applied" however the camera answered decide "applied" through it. No camera: fakes,
and the a1 II's saved frames where this clone has them (skipped without them)."""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from camkit import ocr, paths  # noqa: E402

REFUSAL = "This operation or setting not available as follows: Shoot Mode •OK"
INFORMATION = "The focusing speed may decrease. OK"
QUESTION = "Execute? Cancel OK"


def lines_of(text: str) -> list:
    """OCR's lines for a screen that reads `text`, one line in the top left corner (inside every box read)."""
    return [ocr.Line(text=text, conf=0.9, x=0, y=0, w=10, h=10)] if text else []


def reads(monkeypatch, text_of):
    """OCR reads text_of(path) on every frame (camkit.ocr.read faked)."""
    monkeypatch.setattr(ocr, "read", lambda frames, eng=None: {f: lines_of(text_of(f)) for f in frames})


class AfterOk:
    """A camera just after an OK: its screen of `kind`, reading `text`; MENU takes it to `then`. Every press recorded,
    and each shows a new frame."""

    def __init__(self, kind, text="", then="menu"):
        self.kind, self.text, self.then, self.presses = kind, text, then, []
        self.frame = SimpleNamespace(path=Path("00010_enter.png"), image=None)

    def press(self, key, **kw):
        self.presses.append(key)
        self.frame = SimpleNamespace(path=Path(f"{10 + len(self.presses):05d}_{key}.png"), image=None)
        if key == "menu":
            self.kind, self.text = self.then, ""

    def read(self):
        return SimpleNamespace(kind=self.kind)


@pytest.fixture
def step(monkeypatch):
    """after_ok on an AfterOk camera, OCR reading the camera's text: step(kind, text, **after_ok's keywords) gives
    (the outcome, the camera)."""
    from proving import commit

    def run(kind, text="", then="menu", **kw):
        cam = AfterOk(kind, text, then)
        reads(monkeypatch, lambda f: cam.text)
        return commit.after_ok(cam, "Made-up Row", **kw), cam
    return run


# ------------------------------------------------------------------------------------------------ the step itself

@pytest.mark.parametrize("kind, text, kw, outcome, applied, notice, presses", [
    ("submenu", "", {"back": lambda: True}, "applied", True, None, []),
    ("notice", REFUSAL, {}, "refused", False, {"text": REFUSAL, "frame": "00010_enter.png"}, ["menu"]),
    ("notice", INFORMATION, {}, "notice-closed", True, {"text": INFORMATION, "frame": "00010_enter.png"}, ["menu"]),
    ("shooting", "", {}, "menu-closed", True, {"text": "the menu closed after OK", "frame": "00010_enter.png"}, []),
    ("menu", "", {"page": lambda: True, "back": lambda: False}, "back-on-page", True,
     {"text": "the camera went back to the menu page after OK", "frame": "00010_enter.png"}, []),
    ("menu", "", {}, "applied", True, None, []),                      # no row place given: a menu page is the row's
], ids=["applied", "refused", "notice-closed", "menu-closed", "back-on-page", "applied-on-a-menu-page"])
def test_the_step_after_ok_tells_each_outcome(step, kind, text, kw, outcome, applied, notice, presses):
    """A refusal ("not available", "invalid") and an information notice are each closed with MENU, never OK, and only
    the refusal is no applied choice; the menu closed, back on the page and back on the row are applied, nothing
    pressed."""
    got, cam = step(kind, text, **kw)
    assert (got.kind, got.applied, got.refused, got.notice, cam.presses) == (outcome, applied, not applied, notice,
                                                                             presses)


def test_a_question_after_ok_raises_with_nothing_pressed(step):
    """A screen after OK that asks a question is answered by nobody: the step raises (commit.Asked, a Failed), naming
    the frame and the label, and the caller cancels it with MENU."""
    from proving import commit
    from proving.base import Failed
    with pytest.raises(commit.Asked, match=r"Made-up Row: after OK on 'On' a confirmation came up "
                                           r"\(confirmation text: Execute; 00010_enter.png\)") as e:
        step("notice", QUESTION, label="On")
    assert isinstance(e.value, Failed) and e.value.frame == "00010_enter.png"


def test_a_screen_after_ok_that_is_none_of_them_fails_with_nothing_pressed(step, monkeypatch):
    """The list still open, or a screen of no known kind where information screens are not taken (info False: a prover
    whose own screen reads so), is no outcome: Failed, nothing pressed."""
    from proving import commit, screens
    from proving.base import Failed
    taken = []
    monkeypatch.setattr(screens, "info_notice_ok", lambda *a, **k: taken.append(a) or {})
    for kind, kw in (("list", {}), ("unknown", {"info": False}), ("dialog", {"back": lambda: False})):
        cam = AfterOk(kind)
        with pytest.raises(Failed, match=f"Made-up Row: after OK the screen is {kind} \\(00010_enter.png\\), not the row"):
            commit.after_ok(cam, "Made-up Row", **kw)
        assert cam.presses == []
    assert taken == []


def test_an_information_screen_after_ok_is_left_by_the_information_notices_rules(monkeypatch):
    """A screen of no known kind, or a table, after OK and not the row is an information screen: left as prove_row
    leaves one (proving.screens.info_notice_ok: MENU first, its OK only where the camera refuses MENU or the screen's
    kind takes it), and a table must be back on the row after it."""
    from proving import commit, screens
    from proving.base import Failed
    asked = []

    def info(cam, name, kinds=("notice", "unknown"), **k):
        asked.append(kinds)
        cam.kind = cam.then
        return {"text": "an information screen", "frame": "00010_enter.png", "left_by": "menu"}
    monkeypatch.setattr(screens, "info_notice_ok", info)
    cam = AfterOk("unknown")
    got = commit.after_ok(cam, "Made-up Row", back=lambda: False)
    assert (got.kind, got.applied, got.notice["left_by"]) == ("info-ok", True, "menu")
    cam = AfterOk("table", then="submenu")
    got = commit.after_ok(cam, "Made-up Row", back=lambda: cam.kind == "submenu")
    assert got.kind == "info-ok" and asked == [("notice", "unknown"), ("table",)]
    cam = AfterOk("table", then="menu")
    with pytest.raises(Failed, match="after the information's OK the screen is menu"):
        commit.after_ok(cam, "Made-up Row", back=lambda: False)


def test_a_network_rows_notice_keeps_only_what_withhold_keeps_and_says_nothing(step, capsys):
    """Inside a network row the notice's text is neither kept nor said: what `withhold` keeps of OCR's lines, with the
    frame; the refusal still told from the words."""
    kept = []
    got, cam = step("notice", REFUSAL, withhold=lambda lines: kept.append(lines) or {"fields": []}, say=None)
    assert got.kind == "refused" and got.notice == {"fields": [], "frame": "00010_enter.png"}
    assert [ln.text for ln in kept[0]] == [REFUSAL] and cam.presses == ["menu"]
    assert capsys.readouterr().out == ""


def test_the_refusal_words_are_the_callers(step):
    """The a1 II's checkbox grid refuses to leave no cell ticked with "Item not selected.": a refusal where the caller
    gives words that hold it (kit/provers/grid_run.py), an information notice by prove_row's words."""
    import re
    assert step("notice", "Item not selected. OK")[0].kind == "notice-closed"
    words = re.compile(r"not available|invalid|not selected", re.I)
    assert step("notice", "Item not selected. OK", refusal=words)[0].kind == "refused"
    assert step("notice", "The input value is invalid. Please verify and input again. OK")[0].kind == "refused"


A1 = paths.a1ii_root()
SHOTS = A1 / "kit2_pass2" / "shots"


@pytest.mark.parametrize("name, row, outcome", [
    ("14374_enter.png", None, "refused"), ("17960_enter.png", None, "refused"),
    ("14494_enter.png", None, "notice-closed"), ("03070_enter.png", None, "menu-closed"),
    ("166074_enter.png", "page", "back-on-page"), ("175676_enter.png", "175655_menu-check.png", "applied")],
    ids=["refused-list", "refused-side-list", "information", "menu-closed", "page", "back-on-the-row"])
def test_the_outcomes_on_the_cameras_saved_frames(name, row, outcome):
    """The a1 II's frames just after OK (kit2_pass2), read by the pixel reader and this computer's OCR: a refusal of a
    list and of a side list, an information notice, the menu closed (Focus Area), back on the page, and Drive Mode's
    carousel back on its row (its place the place before it opened). Skipped without the frames or an OCR engine."""
    from camkit import frames, screen
    from proving import commit
    from proving.screens import place, same_place
    if not (SHOTS / name).exists():
        pytest.skip(f"{SHOTS / name} not present")
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")

    class Saved:
        def __init__(self, n):
            self.frame, self.presses = frames.load(SHOTS / n), []

        def read(self):
            return screen.read(self.frame)

        def press(self, key, **kw):
            self.presses.append(key)

    cam = Saved(name)
    here = place(cam)
    kw = {"page": lambda: True} if row == "page" else \
        {"back": lambda: same_place(here, place(Saved(row)))} if row else {}
    got = commit.after_ok(cam, "saved", say=None, **kw)
    assert got.kind == outcome and cam.presses == (["menu"] if outcome in ("refused", "notice-closed") else [])


# ------------------------------------------------------------------------------------------------ prove_row

class TwoOptionList:
    """prove_row's camera on a two-option list (On, Off) saved on Off: the cursor where which_option says; OK on an
    option in `refuse` brings the camera's refusal, whose MENU leaves the saved option as it was; any other OK keeps it
    and goes back to the row."""

    def __init__(self, refuse=()):
        self.where, self.option, self.saved, self.refuse, self.keys = "row", 1, 1, set(refuse), []
        self.frame = SimpleNamespace(path=Path("00001_row.png"), image=None)

    def press(self, key, **kw):
        self.keys.append(key)
        self.frame = SimpleNamespace(path=Path(f"{len(self.keys) + 1:05d}_{key}.png"), image=None)
        if key == "right":
            self.where, self.option = "list", self.saved
        elif key in ("down", "up") and self.where == "list":
            self.option = 1 - self.option
        elif key == "enter":
            if self.option in self.refuse:
                self.where = "notice"
            else:
                self.where, self.saved = "row", self.option
        elif key == "menu":
            self.where = "row"

    def read(self):
        return SimpleNamespace(kind={"row": "submenu", "list": "list", "notice": "notice"}[self.where])

    def text(self):
        return REFUSAL if self.where == "notice" else ""


def prove_list(monkeypatch, tmp_path, cam):
    """prove_run.prove_row on `cam` with its seams faked as the kit's tests fake them; its proof lines."""
    import prove_run as P
    from camkit.runs import Run
    for name, value in (("place", lambda c: "here"), ("same_place", lambda a, b: True), ("to_row", lambda *a: None),
                        ("which_option", lambda c, job: c.option), ("vlm_option", lambda c: "On"),
                        ("bar_text", lambda c: ["On", "Off"][c.option]), ("after_download", lambda c, done: None),
                        ("finish_attempt", lambda *a, **k: None)):
        monkeypatch.setattr(P, name, value)
    monkeypatch.setattr(P.camset, "read", lambda p: SimpleNamespace())
    monkeypatch.setattr(P.camset, "diff", lambda a, b: [])
    reads(monkeypatch, lambda f: cam.text())
    out = io.StringIO()
    P.prove_row(cam, SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT"), Run("pass2", root=tmp_path),
                {"path": ["Made-up Row"], "kind": "list", "labels": ["On", "Off"]}, tmp_path / "base.DAT", out)
    return [json.loads(x) for x in out.getvalue().splitlines()]


def test_prove_row_records_a_refusal_as_before(tmp_path, monkeypatch):
    """prove_row through the step: the refused option's line "applied": false with the notice and its frame, the MENU
    on the notice its only press there, and the next visit expects the list on the option that was saved."""
    cam = TwoOptionList(refuse={0})
    lines = prove_list(monkeypatch, tmp_path, cam)
    assert [(x["label"], x["applied"], x["notice"]) for x in lines] == [
        ("On", False, {"text": REFUSAL, "frame": "00004_enter.png"}), ("Off", True, None)]
    assert cam.keys == ["right", "down", "enter", "menu", "right", "enter"]


# ------------------------------------------------------------------------------------------------ pass 3's switch

class Blocker:
    """A LiveCamera for pass3_run.switch: Right opens the blocker's list (its cursor `at`), and after Enter the screen
    is `after`; MENU on anything but the shooting screen goes back to the menu; every press recorded."""

    def __init__(self, after: str):
        self.after, self.presses, self.kind, self.at = after, [], "menu", 0
        self.frame = SimpleNamespace(path=Path("00042_enter.png"), image=None)

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "right":
            self.kind = "list"
        elif key == "enter":
            self.kind = self.after
        elif key == "menu" and self.kind != "shooting":
            self.kind = "menu"

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def cancel_to_menu(self):
        if self.kind not in ("menu", "shooting"):
            self.presses.append("menu")
            self.kind = "menu"


def blocker_world(monkeypatch, after: str, notice: str = ""):
    """pass3_run.switch's seams on a Blocker camera: the scan's route, the list's labels and cursor, OCR's notice."""
    import pass3_run
    cam = Blocker(after)
    for name, value in (("LiveCamera", lambda link, hdmi, run: cam), ("same_position", lambda a, b: True),
                        ("go_to", lambda c, cycle, model, j, label: 0), ("enter_any", lambda c, path, i: None),
                        ("labels_of", lambda path, mp=None: (["Electronic Shutter", "Mechanical Shutter"], "list")),
                        ("option_index", lambda c, labels, kind: c.at),
                        ("move_to", lambda c, cur, k, n, kind: setattr(c, "at", k)),
                        ("to_shooting", lambda link, hdmi, why: None), ("notice_text", lambda c: notice)):
        monkeypatch.setattr(pass3_run, name, value)
    return pass3_run, cam


BLOCKER = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}


def test_pass3s_switch_reads_the_screen_after_ok_through_the_step(monkeypatch):
    """Pass 3's switch through the step: a refusal still fails the blocker in plain words, MENU its one press on the
    notice; an information screen after OK is now left by info_notice_ok's rules (a cleanup MENU cancelled it) and the
    switch goes on; the list still open after OK fails the switch (it went on as a switch made), MENU cancelling it."""
    from proving import screens
    from proving.base import Failed
    pass3_run, cam = blocker_world(monkeypatch, "notice", REFUSAL)
    with pytest.raises(Failed, match=r"the camera refused 'Mechanical Shutter' .*: the blocker was not switched"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, BLOCKER)
    assert cam.presses == ["menu", "right", "enter", "menu"]
    taken = []

    def info(c, name, kinds=("notice", "unknown"), **k):
        taken.append((name, kinds))
        c.kind = "menu"
        return {"text": "an information screen", "frame": "00042_enter.png", "left_by": "menu"}
    monkeypatch.setattr(screens, "info_notice_ok", info)
    pass3_run, cam = blocker_world(monkeypatch, "unknown")
    assert pass3_run.switch(None, None, None, [{"screen": None}], {}, BLOCKER) is True
    assert taken == [("Shutter Type", ("notice", "unknown"))] and cam.presses == ["menu", "right", "enter"]
    pass3_run, cam = blocker_world(monkeypatch, "list")
    with pytest.raises(Failed, match=r"Shutter Type: after OK on 'Mechanical Shutter' the screen is list"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, BLOCKER)
    assert cam.presses == ["menu", "right", "enter", "menu"]


def pass3_world(monkeypatch, tmp_path, calls):
    """pass3_run.run_blockers with no camera: a link that downloads made-up files, the switch made (enter_state), its
    check passed, the restore checked; every step's command (crawl_run, the labels, the map, prove_run) kept in
    `calls`, none run."""
    import pass3_run
    from camkit import models

    class Link:
        def __init__(self, run):
            pass

        def __enter__(self):
            return SimpleNamespace(download=lambda tag: tmp_path / f"00001_{tag}.DAT")

        def __exit__(self, *exc):
            return False
    for name, value in (("Link", Link), ("eyes_from_config", lambda run: SimpleNamespace(attach=lambda link: None,
                                                                                        close=lambda: None)),
                        ("to_shooting", lambda link, eyes, why: None), ("enter_state", lambda *a: []),
                        ("restore", lambda run, start: 0), ("step", lambda args, log: calls.append(args[1:]) or 0)):
        monkeypatch.setattr(pass3_run, name, value)
    monkeypatch.setattr(pass3_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(pass3_run.camset, "read", lambda p: SimpleNamespace(model=models.A1II, get=lambda *a: None))
    monkeypatch.setattr(pass3_run.camset, "diff", lambda a, b: [])
    return pass3_run


def test_pass3s_walk_and_proofs_take_the_scan_the_run_was_given(monkeypatch, tmp_path):
    """pass3_run --scan drove the blocker's switch alone: the walk (kit/crawl_run.py) and the proofs (kit/prove_run.py)
    it starts took their own default scan (kit2_page_scan: another state of the camera, other eyes) unless the blocker
    named one, and the run of 2026-11-19 stopped there ("the menu opened on a page the scan does not match", exit 8).
    Now they take the run's scan, a blocker's own where it names one; the labels and the map read no scan; the steps
    inherit the run's eyes (their environment and config are the run's)."""
    from camkit import paths
    calls = []
    pass3_run = pass3_world(monkeypatch, tmp_path, calls)
    given = str(paths.run_root(required=False) / "kit2_page_scan_1118p")
    walk = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    prove = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "prove": ["Long Exposure NR"], "context": "made up"}
    own = {"row": ["Drive Mode"], "to": "Continuous Shooting", "walk": "Pre-Capture Settings", "scan": "kit2_own_scan"}
    assert pass3_run.run_blockers("run", [], {}, [walk, prove, own], None, scan=given) is True
    scans = [(c[c.index("-u") + 1] if "-u" in c else c[0], c[c.index("--scan") + 1] if "--scan" in c else None)
             for c in calls]
    mine = str(pass3_run.RUN_ROOT / "kit2_own_scan")
    assert scans == [("kit/crawl_run.py", given), ("kit/pass1_labels.py", None), ("kit/tiebreak.py", None),
                     ("kit/pass1_map.py", None), ("kit/prove_run.py", given),
                     ("kit/prove_run.py", given),
                     ("kit/crawl_run.py", mine), ("kit/pass1_labels.py", None), ("kit/tiebreak.py", None),
                     ("kit/pass1_map.py", None), ("kit/prove_run.py", mine)]
    assert pass3_run.with_run_scan(walk, None) is walk and pass3_run.with_run_scan(own, given) is own


def test_pass3s_main_hands_its_scan_to_the_blockers(monkeypatch, tmp_path):
    """main: the scan --scan names is the one the switch navigates by and the one run_blockers hands the walk."""
    import pass3_run
    from camkit import models, paths
    got = {}
    given = paths.run_root(required=False) / "kit2_page_scan_1118p"
    for name, value in (("load_scan", lambda scan: got.setdefault("loaded", scan) and ([], {})),
                        ("check_readers", lambda: None), ("P3", tmp_path),
                        ("run_blockers", lambda run, cycle, model, chosen, log, scan=None:
                         got.update(chosen=[b["row"] for b in chosen], scan=scan) or True)):
        monkeypatch.setattr(pass3_run, name, value)
    monkeypatch.setattr(pass3_run.models, "current", lambda: models.A1II)
    monkeypatch.setattr(sys, "argv", ["pass3_run.py", "--only", "Shutter Type", "--scan", str(given)])
    pass3_run.main()
    assert got == {"loaded": str(given), "chosen": [["Shutter Type"]], "scan": str(given)}


# ------------------------------------------------------------------------------------------------ the provers

class Shots:
    """What every made-up camera below shares: each press shows a new frame and is recorded; `kind` and `text` are the
    screen on show and what OCR reads on it."""

    def __init__(self):
        self.kind, self.text, self.presses, self.n = "menu", "", [], 1
        self.frame = SimpleNamespace(path=Path("00001_start.png"), image=None)

    def shot(self, key):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{key}.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def refresh(self, tag):
        self.shot(tag)

    def refused_here(self):
        """The camera's refusal on show (OK on a value it refuses)."""
        self.kind, self.text = "notice", REFUSAL


@contextlib.contextmanager
def session_of(cam, link):
    """runner.prover_session as the provers use it, with no link: the camera and link given, a made-up start file."""
    yield SimpleNamespace(cam=cam, link=link, start=Path("00001_before.DAT"))


def downloads():
    """A link whose downloads are numbered made-up files; camset.read and diff are faked by each test."""
    got = []
    return SimpleNamespace(download=lambda tag: got.append(tag) or Path(f"{len(got) + 1:05d}_{tag}.DAT"), got=got)


def proof_lines() -> list:
    """The proofs a prover wrote in this test's runs (CAMSET_RUNS): kit2_pass2/proofs.jsonl of the made-up camera."""
    from camkit.runs import Run
    f = Run("kit2_pass2").dir / "proofs.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def no_diffs(monkeypatch, module):
    monkeypatch.setattr(module.camset, "read", lambda p: SimpleNamespace(path=p))
    monkeypatch.setattr(module.camset, "diff", lambda a, b: [])


class BracketCam(Shots):
    """Drive Mode's carousel on Cont. Bracket with its step and images fields, holding 1.0 EV 5 Img.; OK on a setting
    in `refuse` brings the camera's refusal (Bracket greyed by another setting), which MENU closes with the menu;
    another OK keeps the setting and goes back to the menu page."""

    def __init__(self, refuse=()):
        super().__init__()
        self.saved, self.refuse = (1.0, (5, "")), set(refuse)
        self.now = list(self.saved)

    def open(self):
        self.kind, self.now = "dialog", list(self.saved)

    def fields(self):
        st, (n, sign) = self.now
        return {"step": f"{st:.1f}EV", "images": f"{n} Images{' ' + sign if sign else ''}", "next": ""}

    def press(self, key, **kw):
        self.presses.append(key)
        self.shot(key)
        if key == "enter" and tuple(self.now) in self.refuse:
            self.refused_here()
        elif key == "enter":
            self.kind, self.saved = "menu", tuple(self.now)
        elif key == "menu":
            self.kind, self.text = "shooting", ""


def bracket_world(monkeypatch, cam, link):
    """bracket_run's seams on a BracketCam: the look's lists given, the fields read and set on the made-up carousel."""
    import bracket_run as B
    reads(monkeypatch, lambda f: cam.text)
    no_diffs(monkeypatch, B)
    for name, value in (("load_scan", lambda scan: ([], {})), ("eyes_from_config", lambda run: None),
                        ("prover_session", lambda run, hdmi, **kw: session_of(cam, link)),
                        ("look", lambda c, cycle, model, option: {1.0: [(5, ""), (3, "")], 0.3: [(3, "")]}),
                        ("close_screen", lambda c, link: None), ("open_carousel", lambda c, cycle, model, o: c.open()),
                        ("right_to", lambda c, field: None),
                        ("set_field", lambda c, field, want, read: c.now.__setitem__(field == "images", want)),
                        ("fields", lambda c: c.fields()), ("focus", lambda c: None),
                        ("title", lambda c: "Cont. Bracket" if c.kind == "dialog" else "Shooting"),
                        ("to_shooting", lambda link, hdmi, why: None)):
        monkeypatch.setattr(B, name, value)
    monkeypatch.setattr(B.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["bracket_run.py", "--option", "Cont. Bracket", "--scan", "made-up"])
    return B


def test_bracket_records_a_refused_setting_as_refused(monkeypatch):
    """bracket_run took any title change after OK for the setting kept and wrote "applied": true, a refusal crediting
    the label with the base's value; now the screen after OK is read by the step: the refused setting's line says
    "applied": false with the camera's notice, closed with MENU before the download, and the others are as before. A
    base whose OK is refused proves nothing."""
    cam, link = BracketCam(refuse={(0.3, (3, ""))}), downloads()
    B = bracket_world(monkeypatch, cam, link)
    B.main()
    lines = proof_lines()
    assert [(x["label"], x["applied"], x.get("notice", {}).get("text")) for x in lines] == [
        ("0.3 EV 3 Img.", False, REFUSAL), ("1.0 EV 5 Img.", True, None), ("1.0 EV 3 Img.", True, None)]
    assert "notice" not in lines[1] and cam.presses.count("menu") == 1 and cam.saved == (1.0, (3, ""))
    cam, link = BracketCam(refuse={(1.0, (5, ""))}), downloads()
    B = bracket_world(monkeypatch, cam, link)
    with pytest.raises(B.Failed, match=r"Cont. Bracket: the camera refused it as its fields stood"):
        B.main()
    assert len(proof_lines()) == 3 and link.got == []


class ScaleCam(Shots):
    """A made-up scale 0..4 holding 3: Left and Right step its number while it is open, stopping at the ends; OK keeps
    the number and goes back to the menu row, OK on a number in `refuse` brings the camera's refusal, whose MENU leaves
    the number kept before. OCR reads each frame as it was shot (`seen`): the number where the scale draws it, or the
    notice."""

    def __init__(self, refuse=()):
        super().__init__()
        self.saved = self.pos = 3
        self.refuse, self.seen = set(refuse), {}

    def open(self):
        self.kind, self.pos = "slider", self.saved
        self.shot("right")

    def shot(self, key):
        super().shot(key)
        self.seen[self.frame.path] = (self.kind, self.pos, self.text)

    def press(self, key, **kw):
        self.presses.append(key)
        if key in ("left", "right") and self.kind == "slider":
            self.pos = max(0, min(4, self.pos + (1 if key == "right" else -1)))
        elif key == "enter" and self.pos in self.refuse:
            self.refused_here()
        elif key == "enter":
            self.kind, self.saved = "menu", self.pos
        elif key == "menu":
            self.kind, self.text, self.pos = "menu", "", self.saved
        self.shot(key)

    def ocr(self, frames, eng=None):
        out = {}
        for f in frames:
            kind, pos, text = self.seen.get(f, ("menu", None, ""))
            out[f] = [ocr.Line(text=str(pos), conf=1.0, x=311, y=287, w=18, h=29)] if kind == "slider" else lines_of(text)
        return out


def test_scale_records_a_refused_number_as_refused_and_goes_on(monkeypatch):
    """scale_run went to the download straight after OK and wrote "applied": true, so a refusal credited the label with
    the number kept before, and the next choice, expecting the scale on the refused number, stopped the row. Now the
    refused number's line says "applied": false with the notice (closed with MENU), the next choice expects the number
    kept before, and the row goes on to the end."""
    import time as clock

    import scale_run as S
    cam, link = ScaleCam(refuse={1}), downloads()
    monkeypatch.setattr(ocr, "read", cam.ocr)
    no_diffs(monkeypatch, S)
    for name, value in (("load_scan", lambda scan: ([], {})), ("eyes_from_config", lambda run: None),
                        ("prover_session", lambda run, hdmi, **kw: session_of(cam, link)),
                        ("ends", lambda c, link, cycle, model, path, panel=False: (["0", "1", "2", "3", "4"], "3")),
                        ("open_row", lambda c, cycle, model, path, panel=False: c.open()),
                        ("option_answer", lambda c: None), ("close_screen", lambda c, link: None),
                        ("to_shooting", lambda link, hdmi, why: None), ("_said", {}), ("_by_reader", set()),
                        ("time", SimpleNamespace(sleep=lambda s: None, time_ns=clock.time_ns, monotonic=lambda: 0.0))):
        monkeypatch.setattr(S, name, value)
    monkeypatch.setattr(sys, "argv", ["scale_run.py", "--row", "Made-up Scale", "--scan", "made-up"])
    S.main()
    lines = proof_lines()
    assert [(x["label"], x["applied"], x.get("notice", {}).get("text")) for x in lines] == [
        ("0", True, None), ("1", False, REFUSAL), ("2", True, None), ("4", True, None), ("3", True, None)]
    assert "notice" not in lines[0] and cam.saved == 3 and cam.presses.count("menu") == 1


class PortraitCam(Shots):
    """Focus Area's carousel held vertically, saved on Wide: Up steps back through Wide, Zone, Center Fix (round); OK
    keeps the option and closes the menu (the shooting screen, as the a1 II's Focus Area does); OK on an option in
    `refuse` brings the camera's refusal, `turned` its words read only upright (a notice drawn in portrait)."""
    LABELS = ["Wide", "Zone", "Center Fix"]

    def __init__(self, refuse=(), turned=False):
        super().__init__()
        self.saved = self.at = 0
        self.refuse, self.turned = set(refuse), turned

    def open(self):
        self.kind, self.at = "dialog", self.saved
        self.shot("right")

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "up" and self.kind == "dialog":
            self.at = (self.at - 1) % len(self.LABELS)
        elif key == "enter" and self.at in self.refuse:
            self.refused_here()
        elif key == "enter":
            self.kind, self.saved = "shooting", self.at
        elif key == "menu":
            self.kind, self.text = "shooting", ""
        self.shot(key)

    def level(self):
        return "Ⅎ⅁ʇou ʎɐʍ" if self.turned and self.text else self.text


def orient_world(monkeypatch, cam, link):
    """orient_run's seams on a PortraitCam: the map's options, no second axis, the portrait readings made up (OCR on
    the level frame reads cam.level(), made upright cam.text)."""
    import orient_run as O
    reads(monkeypatch, lambda f: cam.level())
    no_diffs(monkeypatch, O)
    for name, value in (("load_scan", lambda scan: ([], {})), ("eyes_from_config", lambda run: None),
                        ("prover_session", lambda run, hdmi, **kw: session_of(cam, link)),
                        ("labels_of", lambda path: (PortraitCam.LABELS, "dialog")), ("read_json", lambda p: {}),
                        ("open_row", lambda c, cycle, model, row, k, shots: c.open()),
                        ("reading", lambda c, k, shots: ("Focus Area", PortraitCam.LABELS[c.at])),
                        ("upright", lambda c, k, shots: lines_of(c.text)), ("vlm_option", lambda c: "made up"),
                        ("close_screen", lambda c, link: None), ("to_shooting", lambda link, hdmi, why: None)):
        monkeypatch.setattr(O, name, value)
    monkeypatch.setattr(O.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["orient_run.py", "--grip", "down", "--scan", "made-up"])
    return O


@pytest.mark.parametrize("turned", [False, True], ids=["level", "portrait"])
def test_orient_records_a_refused_option_as_refused(monkeypatch, turned):
    """orient_run went to the download straight after OK and wrote "applied": true, a refusal crediting the label with
    the option kept before. Now the screen after OK goes through the step, the notice's words read level and made
    upright (a notice drawn either way): the refused option's line says "applied": false with the notice, closed with
    MENU; the others say the menu closed after OK, as Focus Area's OK does."""
    cam, link = PortraitCam(refuse={1}, turned=turned), downloads()
    O = orient_world(monkeypatch, cam, link)
    O.main()
    lines = proof_lines()
    closed = "the menu closed after OK"
    assert [(x["label"], x["applied"], x.get("notice", {}).get("text")) for x in lines] == [
        ("Zone", False, REFUSAL), ("Center Fix", True, closed), ("Wide", True, closed)]
    assert cam.presses.count("menu") == 1 and cam.saved == 0


class BoxesCam(Shots):
    """S&Q's Frame Rate Settings: two boxes, Rec Frame Rate (60p, 24p, 120p) and Frame Rate, holding 60p; Down steps the
    lit box on, Up back; OK leaves for the row's page, OK with a value in `refuse` lit brings the camera's refusal."""
    VALUES = ["60p", "24p", "120p"]

    def __init__(self, refuse=()):
        super().__init__()
        self.at, self.lit, self.refuse, self.answer_once = 0, 0, set(refuse), None

    def open(self):
        self.kind = "unknown"                   # the two-box screen reads as no known kind
        self.shot("right")

    def press(self, key, **kw):
        self.presses.append(key)
        if key in ("down", "up"):
            self.at = max(0, min(2, self.at + (1 if key == "down" else -1)))
        elif key == "enter" and self.VALUES[self.at] in self.refuse:
            self.refused_here()
        elif key in ("enter", "menu"):
            self.kind, self.text = "submenu", ""
        self.shot(key)


def boxes_world(monkeypatch, cam):
    """boxes_run's seams on a BoxesCam: the row opened, the lit box read off the made-up screen, no second reader."""
    import boxes_run as B
    reads(monkeypatch, lambda f: cam.text)
    no_diffs(monkeypatch, B)
    for name, value in (("open_row", lambda c, cycle, model, path: c.open()), ("to_box", lambda c, b: None),
                        ("read_box", lambda c, b, vals=None, row="": BoxesCam.VALUES[c.at]),
                        ("focus", lambda c: c.lit), ("box_reading", lambda c, b: "made up"),
                        ("look", lambda c, link, cycle, model, path, b, seen=None: (list(BoxesCam.VALUES), "60p")),
                        ("look_open", lambda c, link, path, b, seen=None: (list(BoxesCam.VALUES), "60p")),
                        ("drawn_names", lambda c, names: list(names)),
                        ("to_shooting", lambda link, hdmi, why: None), ("wait_lock", lambda *a, **k: None)):
        monkeypatch.setattr(B, name, value)
    return B


def test_boxes_record_a_refused_value_as_refused(monkeypatch):
    """boxes_run left the screen with OK and wrote "applied": true whatever came up; now the screen after OK goes
    through the step: a value whose OK the camera refuses says "applied": false with the notice, closed with MENU; the
    others are as before. mode_switch's box setting (set_value) stops on such a refusal, naming the frame, never the
    notice's words."""
    cam = BoxesCam(refuse={"24p"})
    B = boxes_world(monkeypatch, cam)
    out = io.StringIO()
    path, names = ["S&Q Settings", "Frame Rate Settings"], ["Rec Frame Rate", "Frame Rate"]
    B.prove(cam, downloads(), None, [], {}, path, names, "Rec Frame Rate", None, Path("00001_before.DAT"), out)
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [(x["label"], x["applied"], x.get("notice", {}).get("text")) for x in lines] == [
        ("24p", False, REFUSAL), ("120p", True, None), ("60p", True, None)]
    assert "notice" not in lines[1] and cam.presses.count("menu") == 1
    cam = BoxesCam(refuse={"24p"})
    B = boxes_world(monkeypatch, cam)
    with pytest.raises(B.Failed, match=r"Rec Frame Rate = 24p: the camera refused it after OK \(its notice on "
                                       r"\d+_enter.png\)$"):
        B.set_value(cam, None, [], {}, path, names, "Rec Frame Rate", "24p")


class ZebraCam(Shots):
    """Zebra Level's Custom 1 with its row of boxes: the box stepped to `target` (step_to, faked) is kept with OK, which
    goes back to the menu row; OK with a value in `refuse` brings the camera's refusal."""

    def __init__(self, refuse=()):
        super().__init__()
        self.target, self.refuse, self.answer_once = None, set(refuse), None

    def open(self):
        self.kind = "dialog"
        self.shot("right")

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "enter" and self.target in self.refuse:
            self.refused_here()
        elif key in ("enter", "menu"):
            self.kind, self.text = "menu", ""
        self.shot(key)


ZEBRA = {"types": {"Std+Range": ["Type", "Standard", "Range"]},
         "boxes": {"Type": {"values": ["Std+Range", "Lower Limit"], "held": "Std+Range", "wraps": True},
                   "Standard": {"values": ["69", "70", "71"], "held": "70", "type": "Std+Range"},
                   "Range": {"values": ["±4", "±5", "±6"], "held": "±5", "type": "Std+Range"}}}


def optboxes_world(monkeypatch, cam):
    """optboxes_run's seams on a ZebraCam: the option and its boxes reached, the box stepped and read as asked, the OK
    judge passing; the downloads made up."""
    import optboxes_run as O
    reads(monkeypatch, lambda f: cam.text)
    no_diffs(monkeypatch, O)
    for name, value in (("open_option", lambda c, cycle, model, row, option: c.open()),
                        ("enter_box", lambda c, index, names, option: None),
                        ("step_to", lambda c, b, vals, target, names, option: setattr(c, "target", target)),
                        ("in_box", lambda c, option, name, b: None), ("ok_refused", lambda c, consent, read=None: ""),
                        ("value_read", lambda c, b, like, fits=None, always=False, need="":
                         O.BoxRead(like, like, like, "made up", "both")),
                        ("to_shooting", lambda link, hdmi, why: None), ("wait_lock", lambda *a, **k: None)):
        monkeypatch.setattr(O, name, value)
    return O


def test_optboxes_record_a_refused_value_as_refused(monkeypatch):
    """optboxes_run kept each value with OK and wrote "applied": true whatever came up, a refusal crediting the label
    with its base's value; now the screen after OK goes through the step: the refused value's line says "applied":
    false with the notice, closed with MENU; a base whose OK the camera refuses proves nothing."""
    cam = ZebraCam(refuse={"±4"})
    O = optboxes_world(monkeypatch, cam)
    out = io.StringIO()
    O.prove(cam, downloads(), None, [], {}, "Zebra Level", "Custom 1", ZEBRA, "Range", Path("00001_before.DAT"), out)
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [(x["label"], x["applied"], x.get("notice", {}).get("text")) for x in lines] == [
        ("±4", False, REFUSAL), ("±6", True, None), ("±5", True, None)]
    assert "notice" not in lines[1] and cam.presses.count("menu") == 1
    cam = ZebraCam(refuse={"Std+Range"})
    O = optboxes_world(monkeypatch, cam)
    with pytest.raises(O.Failed, match=r"the base: the camera refused Zebra Level > Custom 1 > Type = Std\+Range"):
        O.prove(cam, downloads(), None, [], {}, "Zebra Level", "Custom 1", ZEBRA, "Range", Path("00001_before.DAT"),
                io.StringIO())


GRID_REFUSAL = "Item not selected. OK"          # the a1 II's words where a grid's OK would leave a cell it will not


class GridCam(Shots):
    """A checkbox grid of three cells (A, B, C), all ticked: Enter on a cell flips it; Enter on the OK button keeps the
    ticks and goes back to the menu row, except that with B unticked the camera refuses ("Item not selected.", the
    ticks as they were) and with C unticked it keeps them behind an information notice. MENU closes a notice."""

    def __init__(self):
        super().__init__()
        self.saved, self.ticks, self.cursor, self.on_ok = [True] * 3, [True] * 3, 0, False

    def open(self):
        self.kind, self.ticks, self.cursor, self.on_ok = "checkgrid", list(self.saved), 0, False
        self.shot("right")

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "enter" and self.kind == "checkgrid" and not self.on_ok:
            self.ticks[self.cursor] = not self.ticks[self.cursor]
        elif key == "enter" and self.kind == "checkgrid" and not self.ticks[1]:
            self.kind, self.text = "notice", GRID_REFUSAL
        elif key == "enter" and self.kind == "checkgrid":
            self.saved = list(self.ticks)
            self.kind, self.text = ("notice", INFORMATION) if not self.ticks[2] else ("menu", "")
        elif key == "menu":
            self.kind, self.text = "menu", ""
        self.shot(key)

    def cancel_to_menu(self):
        if self.kind not in ("menu", "shooting"):
            self.press("menu")


def test_the_grid_tells_a_refusal_from_an_information_notice(monkeypatch):
    """grid_run took any notice after OK for a refusal ("applied": notice is None), so a cell whose OK the camera kept
    behind an information notice lost its value. Now the step tells them apart, with the grid's own refusal words
    ("Item not selected."): the refused visit says "applied": false and puts back nothing after it, the information
    notice's visit "applied": true with the notice, both closed with MENU."""
    import grid_run as G
    cam, link = GridCam(), downloads()
    reads(monkeypatch, lambda f: cam.text)
    no_diffs(monkeypatch, G)
    for name, value in (("load_scan", lambda scan: ([], {})), ("eyes_from_config", lambda run: None),
                        ("prover_session", lambda run, hdmi, **kw: session_of(cam, link)),
                        ("labels_of", lambda path: ["A", "B", "C"]), ("open_grid", lambda c, cycle, model, path: c.open()),
                        ("to_cell", lambda c, labels, k: setattr(c, "cursor", k)),
                        ("tick", lambda c: c.ticks[c.cursor] if c.kind == "checkgrid" else None),
                        ("to_ok", lambda c: setattr(c, "on_ok", True)), ("vlm_option", lambda c: "OK"),
                        ("to_shooting", lambda link, hdmi, why: None)):
        monkeypatch.setattr(G, name, value)
    monkeypatch.setattr(G.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["grid_run.py", "--row", "Made-up Grid", "--scan", "made-up"])
    G.main()
    lines = proof_lines()
    assert [(x["label"], [b["box"] for b in x["boxes"]], x["applied"], (x["notice"] or {}).get("text"))
            for x in lines] == [("A", [0], True, None), ("B", [0, 1], False, GRID_REFUSAL),
                                ("C", [2], True, INFORMATION), ("(all back)", [2], True, None)]
    assert cam.presses.count("menu") == 2


class ModeCam(Shots):
    """The Shoot Mode chooser with the dial set by the menu: the stills family's modes Intelligent Auto, Program Auto
    and Aperture Priority, Right stepping them round from the one remembered (the first); OK closes the menu (the
    shooting screen), behind the camera's refusal for a mode in `refuse` and an information notice for one in
    `inform`; MENU on a notice closes it and the menu."""
    MODES = ["Intelligent Auto", "Program Auto", "Aperture Priority"]

    def __init__(self, refuse=(), inform=()):
        super().__init__()
        self.kind, self.mode, self.refuse, self.inform = "shooting", 0, set(refuse), set(inform)

    def open(self):
        self.kind, self.mode = "dialog", 0
        self.shot("right")

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "right" and self.kind == "dialog":
            self.mode = (self.mode + 1) % len(self.MODES)
        elif key == "enter" and self.mode in self.refuse:
            self.refused_here()
        elif key == "enter" and self.mode in self.inform:
            self.kind, self.text = "notice", INFORMATION
        elif key in ("enter", "menu"):
            self.kind, self.text = "shooting", ""
        self.shot(key)

    def cancel_to_menu(self):
        if self.kind not in ("menu", "shooting"):
            self.press("menu")


def test_shoot_mode_tells_a_refusal_from_an_information_notice(monkeypatch, tmp_path):
    """shootmode_run took any notice after OK for a refusal, so a mode the camera kept behind an information notice lost
    its value. Now the step tells them apart: the refused mode says "applied": false, the information notice's mode
    "applied": true with the notice (both closed with MENU), and the family's own line counts the applied ones."""
    import shootmode_run as S
    cam, link = ModeCam(refuse={2}, inform={1}), downloads()

    class Link:
        def __init__(self, run):
            pass

        def __enter__(self):
            return link

        def __exit__(self, *exc):
            return False
    reads(monkeypatch, lambda f: cam.text)
    no_diffs(monkeypatch, S)
    for name, value in (("load_scan", lambda scan: ([], {})), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda run: SimpleNamespace(attach=lambda link: None, close=lambda: None)),
                        ("Link", Link), ("LiveCamera", lambda link, hdmi, run: cam),
                        ("look", lambda c, link, cycle, model, f: list(ModeCam.MODES)),
                        ("open_row", lambda c, cycle, model: c.open()), ("mode_name", lambda c: ModeCam.MODES[c.mode]),
                        ("vlm_option", lambda c: "made up"), ("close_screen", lambda c, link: None),
                        ("to_shooting", lambda link, hdmi, why: None), ("verify_restore", lambda run, start: 0)):
        monkeypatch.setattr(S, name, value)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    start = tmp_path / "00001_dialmenu.DAT"
    start.write_bytes(b"made up")
    monkeypatch.setattr(sys, "argv", ["shootmode_run.py", "--start", str(start), "--scan", "made-up", "--families", "0"])
    S.main()
    lines = proof_lines()
    closed = "the menu closed after OK"
    assert [(x["label"], x["applied"], (x.get("notice") or {}).get("text")) for x in lines] == [
        ("Stills: Program Auto", True, INFORMATION), ("Stills: Aperture Priority", False, REFUSAL),
        ("Stills: Intelligent Auto", True, closed), ("Stills", True, None)]
    assert lines[-1]["family_of"] == [1, 0] and cam.presses.count("menu") == 2


# ------------------------------------------------------------------------------------------------ a panel's slider OK

class Sent(Exception):
    """The camera's link reached: the press went (what it carried)."""


# Monitor Brightness with its slider lit, as OCR read kit2_pass2 252551 (2026-11-19): the title, the setup row and its
# option, the slider's number, the footer's MENU key (its arrow read "D") and OK; the Help button's "?" read as nothing
PANEL_ROWS = [("Monitor Brightness", 17, 9, 278, 44), ("Brightness Setup", 23, 79, 216, 47), ("Manual", 530, 83, 86, 30),
              ("-2", 302, 153, 35, 30), ("MENU D", 461, 443, 65, 24), ("• OK", 563, 437, 63, 28)]
# where that footer draws its keys: the Help button (trash and "?"), the MENU key with its arrow, and OK
PANEL_FOOTER = {"help_only": (376, 437), "menu_back": (462, 437), "ok_key": (561, 436)}
ORANGE = (170, 51, 0)


def panel_picture(lit="slider", keys=tuple(PANEL_FOOTER), stray=None):
    """A panel's picture as far as its consent looks: the slider lit (an orange line across its top and its bottom) or
    the setup row lit (an orange bar), the footer's line, the key hints `keys` drawn from the kit's own glyphs where the
    camera draws them, and `stray`, a block of ink besides (a second button)."""
    import numpy as np
    from PIL import Image

    from camkit import screen
    a = np.zeros((480, 640, 3), np.uint8)
    a[:415] = 10                                    # as dark as the camera's screen, no black frame (live.black)
    if lit == "slider":
        a[138:140, 88:553] = ORANGE
        a[265:267, 88:553] = ORANGE
    elif lit == "setup":
        a[75:123, 18:623] = ORANGE
    a[425:428, :] = 90
    for k in keys:
        with Image.open(Path(screen.__file__).parent / "glyphs" / f"{k}.png") as im:
            g = np.asarray(im.convert("L"))
        x, y = PANEL_FOOTER[k]
        a[y:y + g.shape[0], x:x + g.shape[1]] = g[..., None]
    if stray:
        x0, y0, x1, y1 = stray
        a[y0:y1, x0:x1] = 230
    return a


def panel_camera(tmp_path, monkeypatch, rows=PANEL_ROWS, picture=None, kind="unknown", consent=True):
    """A LiveCamera on a panel read as `kind` (no known kind, as the a1 II's is), its OCR lines `rows`, its picture
    panel_picture's by default; its Enter carrying scale_run's consent for Monitor Brightness where `consent`. Its link
    refuses MENU as the camera does and raises Sent for any other key."""
    from camkit import live
    from camkit.link import CameraRefused
    from camkit.runs import Run

    import scale_run as S
    text = " ".join(r[0] for r in rows)
    for name, value in (("text_of", text), ("body_of", " ".join(r[0] for r in rows if r[2] + r[4] / 2 < 415)),
                        ("title_of", "")):
        monkeypatch.setattr(live, name, lambda cam, v=value: v)
    monkeypatch.setattr(live, "lit_text", lambda image, path: "")
    monkeypatch.setattr(live, "lone_of", lambda image, path: "")
    monkeypatch.setattr(live, "look_again", lambda eyes, judged, tag, moved_at=None: ("", None))
    monkeypatch.setattr(live, "boxes_lines", lambda c: [ocr.Line(t, 1.0, x, y, w, h) for t, x, y, w, h in rows])
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.run = Run("enter", root=tmp_path)
    cam.screen = SimpleNamespace(kind=kind)
    cam.frame = SimpleNamespace(image=panel_picture() if picture is None else picture, path=tmp_path / "00001_x.png")
    cam.network, cam.owner, cam.permit, cam.network_open, cam.may_open_exact = frozenset(), {}, None, None, None
    cam.may_open = frozenset()

    def press(key, *a, **k):
        if key == "menu":
            raise CameraRefused("press menu 60: button not accepted")
        raise Sent(k)
    cam.link = SimpleNamespace(press=press, moves=0, menus=0)
    cam.answer_once = S.panel_consent(["Monitor Brightness"]) if consent else None
    return cam


def enter_passed(cam) -> list:
    f = cam.run.dir / "events.jsonl"
    return [e["by"] for e in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if e["kind"] == "enter_passed"] \
        if f.exists() else []


def test_a_panels_ok_goes_by_its_consent_judged_on_the_panels_own_shape(tmp_path, monkeypatch):
    """Monitor Brightness's panel reads as no known kind, so the camera's shape check refused its OK (the run of
    2026-11-19 stopped there; the proofs of 2026-11-10 pressed it before that check, 2026-11-15). scale_run's consent
    for that one OK (camkit.live.PanelSlider) lets it go judged on the panel's own shape: its title, its slider lit, its
    footer's Help button, MENU key and OK drawn and nothing else; logged with the consent's words, spent by its press."""
    from camkit import safety
    cam = panel_camera(tmp_path, monkeypatch, consent=False)
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("enter")                                  # the guard as it stopped the run
    cam = panel_camera(tmp_path, monkeypatch)
    with pytest.raises(Sent):
        cam.press("enter")
    assert enter_passed(cam) == ["Monitor Brightness's own slider: OK keeps the number it shows (scale_run)"]
    assert cam.answer_once is None
    glued = [*PANEL_ROWS[:4], ("iMENU", 461, 443, 65, 24), ("cOK", 563, 437, 63, 28)]       # read over the OSD picture
    for rows in (glued, PANEL_ROWS[:4], [*PANEL_ROWS[:2], ("Manua", 530, 83, 86, 30), *PANEL_ROWS[3:]]):
        cam = panel_camera(tmp_path, monkeypatch, rows)
        with pytest.raises(Sent):
            cam.press("enter")


def _rows_with(i, text):
    return [*PANEL_ROWS[:i], (text, *PANEL_ROWS[i][1:]), *PANEL_ROWS[i + 1:]]


@pytest.mark.parametrize("rows,picture,why", [
    (PANEL_ROWS, panel_picture(lit="setup"), "its slider is not lit"),
    (PANEL_ROWS, panel_picture(lit=None), "its slider is not lit"),
    (PANEL_ROWS, panel_picture(keys=("help_only", "menu_back")), "offers no OK"),
    (PANEL_ROWS, panel_picture(keys=("help_only", "ok_key")), "lacks its Help button .* or its MENU key"),
    (PANEL_ROWS, panel_picture(keys=("menu_back", "ok_key")), "lacks its Help button"),
    (PANEL_ROWS, panel_picture(stray=(20, 436, 140, 470)), "draws more than its Help button, MENU and OK"),
    (_rows_with(0, "Viewfinder Bright."), None, "is not Monitor Brightness's"),
    (_rows_with(0, "Setup > Finder/Monitor"), None, "is not Monitor Brightness's"),
    (_rows_with(3, "Reset all settings?"), None, "question mark"),
    (PANEL_ROWS + [("Format the memory card", 120, 330, 300, 30)], None, "reads as a confirmation"),
    (PANEL_ROWS + [("Recording will begin", 10, 380, 70, 28)], None, "stands where its panel draws none"),
    (_rows_with(4, "Reset"), None, "'reset'"),
    (_rows_with(5, "Cancel • OK"), None, "'cancel'")])
def test_a_panels_consent_refuses_any_screen_not_shaped_as_that_panel(tmp_path, monkeypatch, rows, picture, why):
    """The setup row lit or nothing lit, no OK key drawn, no MENU key or Help button, ink besides them, another title, a
    question mark or a confirmation's word above the footer, a line where the panel draws none, a footer word but MENU
    and OK: no OK."""
    from camkit import safety
    cam = panel_camera(tmp_path, monkeypatch, rows, picture)
    with pytest.raises(safety.Refused, match=why):
        cam.press("enter")


def test_a_flat_footer_matches_no_key_whatever_opencv_scores_there(monkeypatch):
    """On x86-64 OpenCV scored a flat black window 0.90 to 1.0 against the footer's keys (arm64: 0.0), so footer_keys
    found an OK key never drawn and the panel case above refused for stray ink instead of "offers no OK". A flat window
    holds no glyph: with every place scored 1.0, as that noise can, a flat footer still finds no key."""
    import cv2
    import numpy as np

    from camkit import live, screen
    monkeypatch.setattr(cv2, "matchTemplate", lambda band, t, method: np.ones(
        (band.shape[0] - t.shape[0] + 1, band.shape[1] - t.shape[1] + 1), np.float32))
    for level in (0, 10, 200):                     # black, the screen's dark grey, all lit (_lit_key's 0/1 pixels)
        a = np.full((480, 640, 3), level, np.uint8)
        assert screen.footer_keys(a) == {} and screen.help_glyph(a) is None and live.menu_back_key(a) is None
        assert screen._menu_back_alone(a) is None and screen._lit_key(a, "ok_key") == 0.0


def test_a_panels_consent_answers_no_other_screen_nor_key(tmp_path, monkeypatch):
    """On a notice the panel's consent lifts nothing (the notice's own judgement stands); the trash button on the panel
    meets the shape check as ever; and only scale_run builds the consent."""
    import re

    from camkit import safety
    cam = panel_camera(tmp_path, monkeypatch, [("Not available as follows: Shoot Mode", 50, 200, 500, 30),
                                               ("• OK", 563, 437, 63, 28)], kind="notice")
    with pytest.raises(safety.Refused, match="is a notice"):
        cam.press("enter")
    cam = panel_camera(tmp_path, monkeypatch)
    with pytest.raises(safety.Refused, match="reads as 'unknown'"):
        cam.press("c4", allow=frozenset({"c4"}))
    for f in sorted(KIT.rglob("*.py")):
        if "tests" not in f.parts and re.search(r"\bPanelSlider\(", f.read_text(encoding="utf-8")):
            assert f.relative_to(KIT).as_posix() in ("camkit/live.py", "provers/scale_run.py"), f


class PanelCam(ScaleCam):
    """ScaleCam on a panel's slider: what its OK carried (answer_once) is kept, press by press."""

    def __init__(self):
        super().__init__()
        self.answer_once, self.handed = None, []

    def press(self, key, **kw):
        if key == "enter":
            self.handed.append(self.answer_once)
            self.answer_once = None
        super().press(key, **kw)


def test_the_scale_prover_hands_a_panel_its_consent_with_the_ok_and_a_plain_scale_none(monkeypatch):
    """scale_run.choose on a --panel-row gives the camera the panel's consent (PanelSlider, named for the row, the
    slider's place and the setup row's) with its one OK, after the number is read; on a plain scale (read as a slider,
    whose Enter the shape check takes) it gives none."""
    from camkit import live

    import scale_run as S
    for panel, want in ((True, live.PanelSlider), (False, type(None))):
        cam = PanelCam()
        monkeypatch.setattr(ocr, "read", cam.ocr)
        no_diffs(monkeypatch, S)
        for name, value in (("open_row", lambda c, cycle, model, path, panel=False: c.open()),
                            ("option_answer", lambda c: None), ("close_screen", lambda c, link: None),
                            ("to_shooting", lambda link, hdmi, why: None), ("_said", {}), ("_by_reader", set()),
                            ("time", SimpleNamespace(sleep=lambda s: None, monotonic=lambda: 0.0))):
            monkeypatch.setattr(S, name, value)
        S.choose(cam, downloads(), None, None, None, ["Monitor Brightness"], ["0", "1", "2", "3", "4"], 2, 3, panel)
        assert [type(h) for h in cam.handed] == [want]
        if panel:
            assert (cam.handed[0].row, cam.handed[0].slider, cam.handed[0].setup_at) == (
                "Monitor Brightness", S.PANEL_SLIDER, S.PANEL_SETUP)


@pytest.mark.parametrize("name, row, passes", [
    ("252551_fresh.png", "Monitor Brightness", True), ("239309_left.png", "Monitor Brightness", True),
    ("239651_left.png", "Viewfinder Bright.", True), ("252547_right.png", "Monitor Brightness", False),
    ("239652_enter.png", "Monitor Brightness", False), ("240079_down.png", "Monitor Brightness", False),
    ("252551_fresh.png", "Viewfinder Bright.", False)],
    ids=["refused-on-2026-11-19", "monitor-2026-11-10", "viewfinder-over-osd", "setup-row-lit", "menu-page",
         "two-box-screen", "another-panel"])
def test_the_panels_consent_on_the_cameras_saved_frames(name, row, passes):
    """The a1 II's frames (kit2_pass2), read by this computer's OCR and judged as the camera judges the consent: the
    frame the run of 2026-11-19 was refused on, Monitor Brightness proved on 2026-11-10 over HDMI and Viewfinder Bright.
    over the OSD picture pass; the panel with its setup row lit, a menu page, the two-box screen and another panel's
    title do not. Skipped without the frames or an OCR engine."""
    from camkit import frames, live

    import scale_run as S
    if not (SHOTS / name).exists():
        pytest.skip(f"{SHOTS / name} not present")
    if ocr.engine() not in ocr.available():
        pytest.skip(f"no {ocr.engine()} OCR on this computer")
    f = frames.load(SHOTS / name)
    why = live.panel_slider_refused(S.panel_consent([row]), ocr.read([f.path])[f.path], f.image)
    assert (why == "") is passes, why
