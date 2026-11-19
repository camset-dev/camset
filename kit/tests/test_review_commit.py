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
                        ("time", SimpleNamespace(sleep=lambda s: None, time_ns=clock.time_ns))):
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
