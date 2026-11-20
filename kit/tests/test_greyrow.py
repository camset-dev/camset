"""Why a menu row is grey, asked of the camera (proving.greyrow, kit/provers/greyrow_run.py; the owner, 2026-11-20): Help
first, then one Right for the camera's notice, only where Help was read and gave no reason, only on a row the kit may
open, never twice; after it MENU, or a notice's lone OK where it refuses MENU (camkit.live.leave_notice), never an
answer, no other Enter. Made-up cameras
for the rules; the camera's own frames replayed where runs/ holds them (skipped otherwise), the guides' words read from
the help walk's own file there, never written here (decision 13)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from camkit import paths, safety, screen  # noqa: E402
from camkit.link import CameraRefused, StopRequested  # noqa: E402
from proving import greyrow  # noqa: E402

RUNS = paths.a1ii_root()
DISABLED = "Sets how the function works. This function is currently disabled."
REFUSAL = "This operation or setting not available as follows Touch Operation Off"
FS = ("labels", "framing stabilizer")     # the key Framing Stabilizer's one Right is spent under


class Seen:
    """camkit.first_open.Seen's two questions: every row seen opened but those in `unseen` (paths, as tuples)."""

    def __init__(self, unseen=()):
        self.not_seen = {tuple(p) for p in unseen}

    def seen(self, path) -> bool:
        return tuple(path) not in self.not_seen

    def unseen(self, path) -> list:
        return [tuple(path[:i]) for i in range(1, len(path) + 1) if tuple(path[:i]) in self.not_seen]


class GreyCam:
    """A menu page with the row lit, as ask_why meets it: its label drawn grey (`grey`: True, False or None), the footer
    drawing the help button (`help_button`); C4 is the guide (help_run.guide, faked by world()); Right brings up
    `after`: "notice" (MENU closes it and the menu, as on the a1 II), "asking notice" (a notice that asks, which refuses
    MENU: CameraRefused), "question" (a dialog with a question, MENU cancels it back to the row), "list" (the row opened
    after all, MENU back to the row), "lost" (the row opened, and MENU leaves a screen of no known kind), "shooting" (the
    menu closed), "nothing" (no change). `stop`: a STOP file seen, so any press but a cleanup one is refused before it
    goes out (camkit.link)."""

    KINDS = {"row": "menu", "notice": "notice", "asking notice": "notice", "question": "dialog", "list": "list",
             "lost": "list", "shooting": "shooting", "unknown": "unknown", "playback": "playback",
             "lone notice": "notice"}

    def __init__(self, after="notice", grey=True, help_button=True, label="Framing Stabilizer"):
        self.after, self.grey, self.help_button, self.label = after, grey, help_button, label
        self.where, self.keys, self.n, self.stop, self.lit = "row", [], 1, False, label
        self.frame = SimpleNamespace(path=Path("00001_row.png"), image=None)

    def shoot(self, tag):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{tag}.png"), image=None)

    def refresh(self, tag):
        self.shoot(tag)
        return self.read()

    def read(self):
        return SimpleNamespace(kind=self.KINDS[self.where], bar=(202, 254), row=3, where=self.where)

    def press(self, key, **kw):
        if self.stop:
            raise StopRequested("STOP file")
        if key == "menu" and self.where in ("asking notice", "lone notice"):
            raise CameraRefused("button not accepted")
        self.keys.append(key)
        if key == "right" and self.where == "row":
            self.where = {"nothing": "row"}.get(self.after, self.after)
        elif key == "enter" and self.where == "lone notice" and kw.get("require_notice"):
            self.where = "row"                  # the notice's lone OK, given only as leave_notice gives it
        elif key == "menu":
            self.where = {"notice": "shooting", "question": "row", "list": "row", "lost": "unknown",
                          "row": "shooting"}.get(self.where, self.where)
        self.shoot(key)

    def cancel_to_menu(self):
        return True


def world(monkeypatch, cam, help_text=DISABLED, after_text=REFUSAL, guide_fails=False, stop_after_help=False):
    """ask_why's seams faked round `cam`; returns the guides asked for."""
    import drive as D
    import help_run
    guides = []

    def guide(c, name):
        guides.append(name)
        c.keys.append("c4")
        c.shoot("guide")
        if guide_fails:
            raise greyrow.Failed(f"{name}: the help popup's lit entry reads 'Add to My Menu', not In-Camera Guide")
        c.shoot("ok")
        if stop_after_help:
            c.stop = True               # the STOP file came while the guide was read: the next press is refused
        return {"title": c.label, "text": help_text, "frames": ["00003_guide.png"], "popup": True}
    monkeypatch.setattr(help_run, "guide", guide)
    monkeypatch.setattr(D, "help_refused", lambda kind, image: "" if cam.help_button else "the footer shows no help button")
    monkeypatch.setattr(greyrow, "row_grey", lambda c: ((c.grey, {True: 120.0, False: 230.0, None: 170.0}[c.grey])
                                                        if c.read().kind == "menu" else (None, None)))
    monkeypatch.setattr(greyrow, "lit_of", lambda c: c.lit if c.read().kind == "menu" else "")
    monkeypatch.setattr(greyrow, "read_text", lambda c: {"question": "Execute? OK Cancel",
                                                         "asking notice": "Format the memory card? OK"}.get(c.where, after_text))
    monkeypatch.setattr(greyrow, "place", lambda c: (c.read().kind, c.where))
    monkeypatch.setattr(greyrow, "same_place", lambda a, b: a == b)
    monkeypatch.setattr(greyrow, "same_state", lambda a, b: getattr(a, "where", None) == getattr(b, "where", None))
    return guides


def ask(cam, path=None, seen=None, tried=None, stored=None, labels=("Touch Operation",)):
    said = []
    tried = set() if tried is None else tried
    line = greyrow.ask_why(cam, path or [cam.label], seen=seen or Seen(), tried=tried, stored=stored, labels=labels,
                           say=said.append)
    return line, said, tried


def after_right(cam):
    return cam.keys[cam.keys.index("right") + 1:] if "right" in cam.keys else None


# ---------------------------------------------------------------- the procedure: what goes out, and when

def test_help_first_then_one_right_then_the_notice_left_with_menu(monkeypatch):
    """Framing Stabilizer as on 2026-11-19: drawn grey, its Help says only that it is disabled, so one Right, and the
    camera's notice names the row that shuts it (Touch Operation, never its value), left with MENU."""
    cam = GreyCam()
    guides = world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert cam.keys == ["c4", "right", "menu"] and guides == ["Framing Stabilizer"]
    assert (line["outcome"], line["right"], line["blocker"]) == (greyrow.NOTICE, True, {"row": "Touch Operation"})
    assert line["after"]["left_by"] == "menu" and line["notice"]["text"] == REFUSAL and line["help"]["text"] == DISABLED
    assert "Off" not in json.dumps(line["blocker"]) and tried == {FS}
    assert any("one Right, to read the camera's notice, not to choose" in s for s in said)


@pytest.mark.parametrize("how", ["no button", "guide fails", "nothing read"])
def test_the_right_never_goes_without_help_read_first(monkeypatch, how):
    """No help button drawn: nothing at all is pressed ("help not offered"). A guide that could not be read, or read
    nothing: no Right."""
    cam = GreyCam(help_button=how != "no button")
    world(monkeypatch, cam, help_text="" if how == "nothing read" else DISABLED, guide_fails=how == "guide fails")
    if how == "guide fails":
        with pytest.raises(greyrow.RowFailed) as e:
            ask(cam)
        assert e.value.line["right"] is False and e.value.line["outcome"] == greyrow.FAILED
    else:
        line, said, tried = ask(cam)
        assert line["outcome"] == (greyrow.NO_HELP if how == "no button" else greyrow.REASON) and not tried
    assert "right" not in cam.keys
    assert cam.keys == ([] if how == "no button" else ["c4"])


@pytest.mark.parametrize("path, stored, unseen, lit, want, keys", [
    (["Format"], None, (), None, greyrow.PASSED, []),                               # an action
    (["Select on Cam & Send"], None, (), None, greyrow.PASSED, []),                 # its opening acts
    (["Wi-Fi Connect"], None, (), None, greyrow.PASSED, []),                        # a network setting
    (["Screen Reader"], None, (), None, greyrow.PASSED, []),                        # decision 3's own route
    (["Framing Stabilizer"], "action: made up", (), None, greyrow.PASSED, []),      # the page model's stored reason
    (["Auto Framing Settings", "Framing Tracking Speed"], None, [("Auto Framing Settings",)], None, greyrow.PASSED, []),
    (["Framing Stabilizer"], None, [("Framing Stabilizer",)], None, greyrow.HELP_ONLY, ["c4"]),   # not seen opened
    (["Framing Stabilizer"], None, (), "Format", greyrow.HELP_ONLY, ["c4"]),        # the bar read as never-open
])
def test_the_right_never_goes_on_a_row_the_kit_may_not_open(monkeypatch, path, stored, unseen, lit, want, keys):
    """Every check that stops an open stops the Right: a never-open row, one whose opening acts, the Screen Reader, a
    stored reason, a row above it not seen opened (reaching it would open that one) get no key at all, not even Help; a
    row not seen opened itself, or whose lit bar reads as never-open, gets its Help and no Right."""
    cam = GreyCam(label=path[-1])
    world(monkeypatch, cam)
    if lit is not None:
        cam.lit = path[-1]

        def lit_after_help(c):
            return lit if "c4" in c.keys else c.label
        monkeypatch.setattr(greyrow, "lit_of", lit_after_help)
        monkeypatch.setattr("help_run.on_label", lambda got, label: True)
    line, said, tried = ask(cam, path=path, seen=Seen(unseen), stored=stored)
    assert (line["outcome"], line["right"], cam.keys, tried) == (want, False, keys, set()), line
    assert line["why"]


@pytest.mark.parametrize("path, lit", [
    (["File/Folder Settings", "Create New Fold"], "Create New Folder"),     # typed short: the bar acts as it opens
    (["Framing Stabilizer"], "Format"),                                     # the bar a format
    (["Framing Stabilizer"], "Zoom"),                                       # the bar a row whose opening acts
    (["Framing Stabilizer"], "")])                                          # the bar reads nothing
def test_the_lit_bar_is_judged_before_help_and_a_refused_one_gets_no_key(monkeypatch, path, lit):
    """The path as typed may pass where the bar the cursor stands on does not (help_run.on_label takes a 12-letter
    prefix): the bar read on the fresh frame is judged as an open of it would be, and one refused, or one that reads
    nothing, gets no key at all, not even Help (the review's probe: C4 went on Create New Folder)."""
    import help_run
    cam = GreyCam(label=path[-1])
    world(monkeypatch, cam)
    cam.lit = lit
    monkeypatch.setattr("help_run.on_label", help_run.on_label)             # the real, loose match
    line, said, tried = ask(cam, path=path)
    assert (line["outcome"], line["right"], cam.keys, tried) == (greyrow.PASSED, False, [], set()), line
    assert "lit row" in line["why"]


def test_never_twice_on_a_row_in_the_run(monkeypatch):
    """The row's one Right is spent before it goes out: asked again in the run (or a row the run's file says was
    spent), its Help is read and no Right goes."""
    cam = GreyCam()
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert line["right"] and cam.keys.count("right") == 1
    cam.where, cam.keys = "row", []
    again, said, tried = ask(cam, tried=tried)
    assert (again["outcome"], again["right"], cam.keys) == (greyrow.TRIED, False, ["c4"])


@pytest.mark.parametrize("spelled", ["framing stabilizer", "Framing  Stabilizer", " FRAMING STABILIZER "])
def test_one_row_spelled_another_way_is_the_same_row_and_gets_no_second_right(monkeypatch, spelled):
    """The row's key is its labels folded as camkit.first_open.Seen folds them, the way the kit finds the row: another
    spelling of one row is that row, its Right spent."""
    cam = GreyCam()
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    cam.where, cam.keys = "row", []
    again, said, tried = ask(cam, path=[spelled], tried=tried)
    assert (again["outcome"], again["right"], cam.keys) == (greyrow.TRIED, False, ["c4"]) and tried == {FS}
    assert greyrow.label_key([spelled]) == FS


@pytest.mark.parametrize("text", [
    "Sets how the function works. This operation or setting not available as follows Touch Operation Off",
    "Sets how the function works. Turn on the touch panel first.",
    "Sets how the function works.",
    "This function is currently disabled. Turn on the touch panel first."])
def test_never_when_help_gave_a_reason(monkeypatch, text):
    """A guide that names a blocker, or whose last sentence is anything but the camera's reasonless one, counts as a
    reason: no Right. A named blocker is kept, the row label alone."""
    cam = GreyCam()
    world(monkeypatch, cam, help_text=text)
    line, said, tried = ask(cam)
    assert (line["outcome"], line["right"], cam.keys) == (greyrow.REASON, False, ["c4"])
    assert line.get("blocker") == ({"row": "Touch Operation"} if "as follows" in text else None)


@pytest.mark.parametrize("after, outcome", [("question", greyrow.QUESTION), ("list", greyrow.OPENED)])
def test_a_question_or_a_row_that_opens_after_all_gets_menu_alone(monkeypatch, after, outcome):
    """After the Right a question gets MENU and no answer; a row that opened after all (its grey misjudged) is left with
    MENU alone, back on its page: no Enter, no second Right, nothing else."""
    cam = GreyCam(after=after)
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert after_right(cam) == ["menu"] and (line["outcome"], line["right"]) == (outcome, True)
    assert line["after"]["then"] == "menu" and (line["after"].get("asks") is not None) == (after == "question")


def test_a_notice_that_asks_is_never_answered(monkeypatch):
    """A notice whose words ask: MENU, never leave_notice's OK, even where the camera refuses that MENU (the run stops
    there, its close and restore after it), and no Enter goes."""
    cam = GreyCam(after="asking notice")
    world(monkeypatch, cam)
    with pytest.raises(CameraRefused):
        ask(cam)
    assert after_right(cam) == [] and "enter" not in cam.keys


def test_a_notice_that_refuses_menu_gets_its_lone_ok_the_one_enter(monkeypatch):
    """What the docs say: after the Right, MENU, or the notice's lone OK where it refuses MENU (camkit.live.leave_notice,
    bound to that notice: require_notice); that OK is the one Enter that goes, and the camera's own check judges it."""
    cam = GreyCam(after="lone notice")
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert after_right(cam) == ["enter"] and (line["outcome"], line["after"]["left_by"]) == (greyrow.NOTICE, "ok")


def test_menu_that_leaves_an_unknown_screen_fails_the_row_with_its_right_said(monkeypatch):
    cam = GreyCam(after="lost")
    world(monkeypatch, cam)
    with pytest.raises(greyrow.RowFailed) as e:
        ask(cam)
    assert e.value.line["right"] is True and after_right(cam) == ["menu"]


@pytest.mark.parametrize("after, outcome", [("shooting", greyrow.MENU_CLOSED), ("nothing", greyrow.NO_RESPONSE)])
def test_a_right_that_closed_the_menu_or_did_nothing_gets_no_key_after_it(monkeypatch, after, outcome):
    cam = GreyCam(after=after)
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert after_right(cam) == [] and line["outcome"] == outcome


def test_a_right_that_brings_up_the_playback_view_ends_the_run_with_nothing_pressed_there(monkeypatch):
    """The camera's playback view after the Right: no key there (the link lets MENU alone out, and MENU there opens the
    menu over the view), and the run ends, its line said, so the session's close leaves the view (proving.nav)."""
    cam = GreyCam(after="playback")
    world(monkeypatch, cam)
    with pytest.raises(greyrow.StopsRun) as e:
        ask(cam)
    assert after_right(cam) == [] and (e.value.line["outcome"], e.value.line["right"]) == (greyrow.PLAYBACK, True)
    assert isinstance(e.value, greyrow.RowFailed)


def test_a_stop_between_help_and_right_leaves_the_camera_on_the_menu(monkeypatch):
    """The STOP file seen after the guide: the Right is refused before it goes out, and the camera is still on the row's
    menu page for the session's close."""
    cam = GreyCam()
    world(monkeypatch, cam, stop_after_help=True)
    with pytest.raises(StopRequested):
        ask(cam)
    assert cam.keys == ["c4"] and cam.read().kind == "menu"


@pytest.mark.parametrize("grey, outcome", [(False, greyrow.NOT_GREY), (None, greyrow.UNSURE)])
def test_a_row_not_drawn_grey_now_gets_no_key(monkeypatch, grey, outcome):
    cam = GreyCam(grey=grey)
    world(monkeypatch, cam)
    line, said, tried = ask(cam)
    assert (line["outcome"], cam.keys) == (outcome, [])


def test_the_cameras_own_refusal_of_the_right_is_said_and_spent(monkeypatch):
    cam = GreyCam()
    world(monkeypatch, cam)

    def press(key, **kw):
        if key == "right":
            raise safety.RowRefused("right: the lit row 'Framing Stabilizer' is never opened (made up)")
        GreyCam.press(cam, key, **kw)
    monkeypatch.setattr(cam, "press", press)
    line, said, tried = ask(cam)
    assert (line["outcome"], line["right"], tried) == (greyrow.REFUSED, False, {FS})


def test_a_row_no_longer_lit_or_grey_after_help_gets_no_right(monkeypatch):
    cam = GreyCam()
    world(monkeypatch, cam)
    monkeypatch.setattr(greyrow, "lit_of", lambda c: c.label if "c4" not in c.keys else "Focal Length")
    line, said, tried = ask(cam)
    assert (line["outcome"], line["right"], cam.keys, tried) == (greyrow.MOVED, False, ["c4"], set())


def test_a_lit_bar_that_is_another_row_gets_no_help(monkeypatch):
    """The cursor on another row than the one named, a harmless one (the scan's position or find_row's guess wrong):
    the row fails before any key, so C4 never goes on whatever row is lit."""
    cam = GreyCam()
    world(monkeypatch, cam)
    cam.lit = "Focal Length"
    with pytest.raises(greyrow.RowFailed) as e:
        ask(cam)
    assert cam.keys == [] and e.value.line["right"] is False and "not 'Framing Stabilizer'" in str(e.value)


def test_a_guide_that_does_not_leave_the_cursor_on_the_row_fails_it_with_no_right(monkeypatch):
    """After the guide's OK the cursor must be back where it was before Help (proving.screens.place): elsewhere, the
    row fails and no Right goes, wherever the cursor now is."""
    cam = GreyCam()
    world(monkeypatch, cam)
    import help_run
    guide = help_run.guide

    def moved(c, name):
        got = guide(c, name)
        c.where = "elsewhere"
        return got
    monkeypatch.setattr(help_run, "guide", moved)
    monkeypatch.setitem(GreyCam.KINDS, "elsewhere", "menu")
    with pytest.raises(greyrow.RowFailed) as e:
        ask(cam)
    assert cam.keys == ["c4"] and e.value.line["right"] is False and "not back on the row" in str(e.value)


@pytest.mark.parametrize("grey, outcome", [(True, greyrow.DRAWN_GREY), (False, greyrow.NOT_GREY),
                                           (None, greyrow.UNSURE)])
def test_a_look_reads_the_rows_grey_and_presses_nothing_on_it(monkeypatch, grey, outcome):
    """--look: drawn grey, white or unsure on a frame grabbed afresh, and no key at all on the row, Help's neither; its
    line is a look's, which spends no Right."""
    import help_run
    cam = GreyCam(grey=grey)
    guides = world(monkeypatch, cam)
    monkeypatch.setattr(help_run, "guide", lambda *a: pytest.fail("Help on a look"))
    line = greyrow.look(cam, ["Framing Stabilizer"], seen=Seen(), say=lambda m: None)
    assert (line["kind"], line["outcome"], cam.keys, guides) == ("look", outcome, [], [])
    assert "right" not in line and "spent" not in line and line["row_frame"] == "00002_look-row.png"


@pytest.mark.parametrize("path, lit, outcome", [(["Format"], "Format", greyrow.PASSED),
                                                (["Framing Stabilizer"], "Create New Folder", greyrow.PASSED),
                                                (["Framing Stabilizer"], "Focal Length", greyrow.FAILED)])
def test_a_look_checks_the_row_as_the_procedure_does_before_its_help(monkeypatch, path, lit, outcome):
    """A row the kit may not open or reach, or a lit bar refused, is passed over; a lit bar that is another row fails:
    no key in any of them."""
    cam = GreyCam(label=path[-1])
    world(monkeypatch, cam)
    cam.lit = lit
    try:
        line = greyrow.look(cam, path, seen=Seen(), say=lambda m: None)
    except greyrow.RowFailed as e:
        line = e.line
    assert (line["kind"], line["outcome"], cam.keys) == ("look", outcome, [])


def test_the_screen_must_be_the_rows_menu_page(monkeypatch):
    cam = GreyCam()
    world(monkeypatch, cam)
    cam.where = "list"
    with pytest.raises(greyrow.RowFailed):
        ask(cam)
    assert cam.keys == []


# ---------------------------------------------------------------- the reasonless sentence, as the camera writes it

def test_the_reasonless_sentence_is_the_guides_last():
    for text in ("This function is currently disabled.", "Sets X.  This function is currently disabled",
                 "Sets X.\nthis function is CURRENTLY disabled.", "Sets “X”. This function is currently disabled."):
        assert greyrow.reasonless(text), text
    for text in ("", None, "Sets X.", "This function is currently disabled. Turn on Y.",
                 "Sets X. This operation or setting not available as follows Y This function is currently disabled.",
                 "Sets X. Not available while Y is on. This function is currently disabled.",
                 "Sets X. It cannot be set during Y. This function is currently disabled.",
                 "Sets X This function is currently disabled."):     # a full stop OCR dropped: no sentence of its own
        assert not greyrow.reasonless(text), text


def guides():
    """The help walk's guides (runs/<a1 II>/kit2_help/help.jsonl), skipped without them: (text, the row's guide said
    the camera's state)."""
    f = RUNS / "kit2_help" / "help.jsonl"
    if not f.exists():
        pytest.skip(f"{f} not present")
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_every_recorded_guide_of_a_grey_row_is_reasonless_and_no_other_is():
    """On the a1 II's own guides as OCR read them (kit2_help, 2026-11-01): each that ends with the state line is taken
    for no reason; none of the rest (white rows' guides) is."""
    rows = [r for r in guides() if r.get("text")]
    grey = [r for r in rows if "currently disabled" in r["text"].lower()]
    assert len(grey) >= 50 and all(greyrow.reasonless(r["text"]) for r in grey)
    assert not any(greyrow.reasonless(r["text"]) for r in rows if r not in grey)


# ---------------------------------------------------------------- the camera's own frames, replayed

def frames_needed(*rels):
    got = [RUNS / r for r in rels]
    missing = [str(p) for p in got if not p.exists()]
    if missing:
        pytest.skip(f"{missing[0]} not present")
    return got


class FrameCam:
    """A camera replaying the a1 II's stored frames: each key moves from the frame on show to the one `moves` names for
    it, the screen read by the kit's own pixel reader; a key it does not name for that frame fails the test."""

    def __init__(self, first, moves, label):
        from camkit.frames import load
        self.load, self.moves, self.keys, self.label = load, moves, [], label
        self.frame = load(first)

    def read(self):
        return screen.read(self.frame)

    def refresh(self, tag):
        return self.read()

    def press(self, key, **kw):
        nxt = self.moves.get((self.frame.path.name, key))
        assert nxt is not None, f"{key} on {self.frame.path.name}, which the replay does not hold"
        self.keys.append(key)
        self.frame = self.load(nxt)

    def cancel_to_menu(self):
        return True


def replay_world(monkeypatch, label, guide_frames, text, notice=""):
    """The real ask_why, help_run.guide, drive.help_refused, row_grey and the place checks on the frames; OCR's part
    (the lit bar, the guide's words, the notice's) stood in for: the guide's from the help walk's own file."""
    import help_run
    monkeypatch.setattr(greyrow, "lit_of", lambda c: label if c.read().kind == "menu" else "")
    monkeypatch.setattr(help_run, "highlighted", lambda image, path: "In-Camera Guide")
    monkeypatch.setattr(help_run, "read_guide", lambda f: (label, text) if f.path.name in guide_frames else ("", ""))
    monkeypatch.setattr(greyrow, "read_text", lambda c: notice)


def guide_text(frame: str) -> str:
    return next(r["text"] for r in guides() if (r.get("frames") or [None])[0] == frame)


def test_the_replayed_grey_row_gets_help_then_one_right_and_its_notice_left_with_menu(monkeypatch):
    """S&Q Shoot Mode in Movie mode: drawn grey (its label 130 on kit2_help's 00919), the footer's help button, the
    camera's popup and guide (00920-00922), OK back onto the row (00924); the one Right brings up the camera's refusal
    (kit2_a1fin_look_movie 00008, the same row grey in the same mode), MENU closes it and the menu (00009)."""
    h, m = "kit2_help/shots/", "kit2_a1fin_look_movie/shots/"
    row, pop, g1, g2, back, notice, shooting = frames_needed(
        h + "00919_down.png", h + "00920_c4.png", h + "00921_enter.png", h + "00922_down.png", h + "00924_enter.png",
        m + "00008_right.png", m + "00009_menu.png")
    text = guide_text("00921_enter.png")
    cam = FrameCam(row, {("00919_down.png", "c4"): pop, ("00920_c4.png", "enter"): g1, ("00921_enter.png", "down"): g2,
                         ("00922_down.png", "enter"): back, ("00924_enter.png", "right"): notice,
                         ("00008_right.png", "menu"): shooting}, "S&Q Shoot Mode")
    replay_world(monkeypatch, "S&Q Shoot Mode", {"00921_enter.png", "00922_down.png"}, text,
                 "This operation or setting not available as follows Shoot Mode")
    line, said, tried = ask(cam, labels=("Shoot Mode", "S&Q Shoot Mode"))
    assert cam.keys == ["c4", "enter", "down", "enter", "right", "menu"]
    assert (line["outcome"], line["right"], line["blocker"]) == (greyrow.NOTICE, True, {"row": "Shoot Mode"})
    assert 110 < line["grey"] < 140 and line["after"] == {"screen": "notice", "frame": "00008_right.png", "left_by": "menu"}
    assert line["help"]["frames"] == ["00921_enter.png"]


def test_a_replayed_row_not_seen_opened_gets_its_help_and_no_right(monkeypatch):
    """Framing Stabilizer grey (kit2_help 01033-01038): its guide read, back on the row, and no Right, the row taken as
    one this body has not been seen to open."""
    h = "kit2_help/shots/"
    row, pop, g1, g2, back = frames_needed(h + "01033_down.png", h + "01034_c4.png", h + "01035_enter.png",
                                           h + "01036_down.png", h + "01038_enter.png")
    cam = FrameCam(row, {("01033_down.png", "c4"): pop, ("01034_c4.png", "enter"): g1, ("01035_enter.png", "down"): g2,
                         ("01036_down.png", "enter"): back}, "Framing Stabilizer")
    replay_world(monkeypatch, "Framing Stabilizer", {"01035_enter.png", "01036_down.png"}, guide_text("01035_enter.png"))
    line, said, tried = ask(cam, seen=Seen([("Framing Stabilizer",)]))
    assert (line["outcome"], line["right"], cam.keys) == (greyrow.HELP_ONLY, False, ["c4", "enter", "down", "enter"])
    assert "not seen opened on this body" in line["why"]


def test_a_replayed_white_row_gets_no_key(monkeypatch):
    """Framing Stabilizer drawn white with Touch Operation On (kit2_plan4_look_touch_on 00026, its label 244)."""
    (row,) = frames_needed("kit2_plan4_look_touch_on/shots/00026_down.png")
    cam = FrameCam(row, {}, "Framing Stabilizer")
    replay_world(monkeypatch, "Framing Stabilizer", set(), "")
    line, said, tried = ask(cam)
    assert (line["outcome"], cam.keys) == (greyrow.NOT_GREY, []) and line["grey"] > 200


@pytest.mark.parametrize("rel, outcome", [("kit2_help/shots/00919_down.png", greyrow.DRAWN_GREY),
                                          ("kit2_plan4_look_touch_on/shots/00026_down.png", greyrow.NOT_GREY)])
def test_a_replayed_look_reads_grey_or_white_and_presses_nothing(monkeypatch, rel, outcome):
    (row,) = frames_needed(rel)
    label = "S&Q Shoot Mode" if "00919" in rel else "Framing Stabilizer"
    cam = FrameCam(row, {}, label)
    replay_world(monkeypatch, label, set(), "")
    line = greyrow.look(cam, [label], seen=Seen(), say=lambda m: None)
    assert (line["kind"], line["outcome"], cam.keys, line["row_frame"]) == ("look", outcome, [], Path(rel).name)


@pytest.mark.parametrize("rel, grey", [("kit2_help/shots/00919_down.png", True), ("kit2_help/shots/01033_down.png", True),
                                       ("kit2_a1fin_look_movie/shots/00007_down.png", True),
                                       ("kit2_plan4_look_touch_on/shots/00025_down.png", True),
                                       ("kit2_help/shots/00925_down.png", False),
                                       ("kit2_plan4_look_touch_on/shots/00023_right.png", False),
                                       ("kit2_plan4_look_touch_on/shots/00026_down.png", False)])
def test_the_lit_rows_grey_is_told_on_the_cameras_frames(rel, grey):
    (f,) = frames_needed(rel)
    from camkit.frames import load
    frame = load(f)
    got, p = greyrow.row_grey(SimpleNamespace(frame=frame, read=lambda: screen.read(frame)))
    assert got is grey, (rel, p)
